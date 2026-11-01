"""
GoW WAD SBK Tool  (God of War 1 & 2, PS2)
Buka WAD -> pilih SBK -> Edit audio (Replace dari WAV) -> SAVE.

Jalankan:  python gow_wad_sbk_tool.py     (Python 3.8+, tanpa library tambahan)

Layout WAD (dari analisis 216 WAD GoW 1), stream berurutan:
  [u32 tag][u32 size][char name[24]]   header 0x20 byte
  [data sebanyak size]                 lalu padding ke kelipatan 0x10
Tag tanpa data (size hanya parameter): 0x18, 0x28, 0x32, 0x3E7, 0x29A.
File = tag 0x1E. SBK dikenali dari 4 byte pertama data: 0x18/0x15 (bank
dengan audio di dalamnya) atau 0x40018 (bank berisi file VAG terpisah).
"""
import os
import shutil
import struct
import sys
import tempfile
import traceback
import wave
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

HDR = 0x20
ALIGN = 0x10
TAG_FILE = 0x1E
NODATA_TAGS = (0x18, 0x28, 0x32, 0x3E7, 0x29A)
SBK_MAGICS = (0x18, 0x15, 0x40018)
SBK_VAG = 0x40018
MAX_WAD_SIZE = 128 * 1024 * 1024  # WAD GoW 1 terbesar sekitar 8 MB; PAK jauh lebih besar


def looks_like_wad(head):
    """WAD GoW diawali entry tag 0x378 bernama 'WAD_xxx'."""
    return len(head) >= HDR and (
        (struct.unpack_from("<I", head, 0)[0] & 0xFFFF) == 0x378 or head[8:12] == b"WAD_")


class Entry:
    def __init__(self, hdr_off, tag, size, name, magic=0):
        self.hdr_off = hdr_off
        self.size_off = hdr_off + 4
        self.data_off = hdr_off + HDR
        self.tag = tag
        self.size = size
        self.name = name
        self.magic = magic

    @property
    def is_file(self):
        return (self.tag & 0xFFFF) == TAG_FILE and self.size > 0

    @property
    def is_sbk(self):
        return self.is_file and (self.name.lower().startswith("sbk_")
                                 or self.magic in SBK_MAGICS)


def scan(buf):
    """Jalan sepanjang WAD; berhenti kalau struktur tidak masuk akal."""
    entries, off, n = [], 0, len(buf)
    while off + HDR <= n:
        tag, size = struct.unpack_from("<II", buf, off)
        dsz = 0 if (tag & 0xFFFF) in NODATA_TAGS else size
        if dsz > n - off - HDR:
            break
        name = bytes(buf[off + 8:off + HDR]).split(b"\0")[0].decode("latin1")
        magic = struct.unpack_from("<I", buf, off + HDR)[0] if dsz >= 4 else 0
        entries.append(Entry(off, tag, dsz, name, magic))
        off += HDR + ((dsz + ALIGN - 1) & ~(ALIGN - 1))
    return entries


# ======================= AUDIO: PS-ADPCM + SBK =======================
PS_K = [(0, 0), (60, 0), (115, -52), (98, -55), (122, -60)]
DUMMY = b"\x77" * 14  # frame penutup standar Sony


def ps_decode(data):
    """PS-ADPCM (16 byte/frame -> 28 sampel) ke list int16 mono."""
    s1 = s2 = 0
    out = []
    for i in range(0, len(data) - 15, 16):
        sh = data[i] & 0xF
        fi = (data[i] >> 4) & 0xF
        if fi > 4:
            fi = 0
        if sh > 12:
            sh = 9
        k1, k2 = PS_K[fi]
        for j in range(14):
            byte = data[i + 2 + j]
            for n in (byte & 0xF, byte >> 4):
                if n > 7:
                    n -= 16
                v = ((n << 12) >> sh) + ((k1 * s1 + k2 * s2) >> 6)
                v = -32768 if v < -32768 else 32767 if v > 32767 else v
                out.append(v)
                s2, s1 = s1, v
    return out


def ps_encode(pcm, nframes):
    """list int16 -> list[(byte0, 14 byte)] sebanyak nframes (dipotong/diisi nol)."""
    total = nframes * 28
    pcm = list(pcm[:total]) + [0] * max(0, total - len(pcm))
    s1 = s2 = 0
    frames = []
    for f in range(nframes):
        blk = pcm[f * 28:(f + 1) * 28]
        best = None
        for fi, (k1, k2) in enumerate(PS_K):
            h1, h2, maxd = s1, s2, 0
            for x in blk:
                d = x - ((k1 * h1 + k2 * h2) >> 6)
                if d < 0:
                    d = -d
                if d > maxd:
                    maxd = d
                h2, h1 = h1, x
            sh = 12
            while sh > 0 and maxd > 7 * (1 << (12 - sh)):
                sh -= 1
            step = 1 << (12 - sh)
            c1, c2, err, nib = s1, s2, 0, []
            for x in blk:
                p = (k1 * c1 + k2 * c2) >> 6
                n = (x - p + (step >> 1)) // step
                n = -8 if n < -8 else 7 if n > 7 else n
                r = n * step + p
                r = -32768 if r < -32768 else 32767 if r > 32767 else r
                err += (x - r) ** 2
                nib.append(n & 0xF)
                c2, c1 = c1, r
            if best is None or err < best[0]:
                best = (err, fi, sh, nib, c1, c2)
        _, fi, sh, nib, s1, s2 = best
        data = bytes(nib[2 * j] | (nib[2 * j + 1] << 4) for j in range(14))
        frames.append(((fi << 4) | sh, data))
    return frames


def _blk_info(buf, off, size):
    """Bank 0x18/0x15: audio ada di 'stream block' di dalam SBK."""
    cnt = struct.unpack_from("<I", buf, off + 4)[0]
    if cnt == 0 or cnt > 512:
        raise ValueError("Jumlah suara di header tidak masuk akal (%d)." % cnt)
    base = 8 + 28 * cnt
    if base + 0x18 > size:
        raise ValueError("Header SBK terpotong.")
    names = []
    for i in range(cnt):
        raw = bytes(buf[off + 8 + 28 * i: off + 8 + 28 * i + 24])
        names.append(raw.split(b"\0")[0].decode("latin1"))
    _hs, _hz, ss, sz = struct.unpack_from("<4I", buf, off + base + 8)
    st = base + ss
    if sz == 0 or sz % 16 or st + sz > size:
        raise ValueError("SBK ini tidak punya data audio sendiri (hanya daftar/referensi). "
                         "Audionya ada di SBK pasangan (tipe VAG) atau di luar WAD.")
    n = sz // 16
    flags = [buf[off + st + i * 16 + 1] for i in range(n)]
    samples, loops, s0, i = [], [], 0, 0
    while i < n:
        if flags[i] & 1:  # end flag; gabungkan end-frame berurutan
            j = i
            while j + 1 < n and flags[j + 1] & 1:
                j += 1
            samples.append((st + s0 * 16, j + 1 - s0))
            loops.append(any(f in (4, 6) for f in flags[s0:j + 1]))
            s0 = i = j + 1
        else:
            i += 1
    if s0 < n:
        samples.append((st + s0 * 16, n - s0))
        loops.append(any(f in (4, 6) for f in flags[s0:n]))
    return {"kind": "blk", "names": names, "samples": samples, "loops": loops,
            "rates": [None] * len(samples), "labels": [""] * len(samples),
            "st": st, "stream_size": sz}


def _vag_info(buf, off, size):
    """Bank 0x40018: kumpulan file VAGp (sample rate asli ada di header VAG)."""
    cnt = struct.unpack_from("<I", buf, off + 4)[0]
    if cnt == 0 or cnt > 4096 or 8 + 28 * cnt > size:
        raise ValueError("Jumlah file VAG tidak masuk akal (%d)." % cnt)
    samples, labels, rates, vos = [], [], [], []
    for i in range(cnt):
        e = off + 8 + 28 * i
        name = bytes(buf[e:e + 24]).split(b"\0")[0].decode("latin1")
        vo = struct.unpack_from("<I", buf, e + 24)[0]
        if vo + 0x30 > size or bytes(buf[off + vo:off + vo + 4]) != b"VAGp":
            raise ValueError("File VAG '%s' tidak ditemukan di offset %#x." % (name, vo))
        dlen = struct.unpack_from(">I", buf, off + vo + 12)[0]
        rate = struct.unpack_from(">I", buf, off + vo + 16)[0]
        dlen -= dlen % 16
        if dlen == 0 or vo + 0x30 + dlen > size:
            raise ValueError("Ukuran VAG '%s' tidak masuk akal." % name)
        samples.append((vo + 0x30, dlen // 16))
        labels.append(name)
        rates.append(rate)
        vos.append(vo)
    return {"kind": "vag", "names": labels, "samples": samples, "loops": [False] * cnt,
            "rates": rates, "labels": labels, "vo": vos}


def parse_sbk(buf, off, size):
    """Baca SBK. samples = [(offset byte relatif awal data, jumlah frame)]."""
    if size < 0x20:
        raise ValueError("SBK ini kosong (tidak ada data audio).")
    magic = struct.unpack_from("<I", buf, off)[0]
    return _vag_info(buf, off, size) if magic == SBK_VAG else _blk_info(buf, off, size)


def has_audio(buf, e):
    """True kalau SBK ini punya data audio sendiri yang bisa diedit."""
    try:
        parse_sbk(buf, e.data_off, e.size)
        return True
    except (ValueError, struct.error):
        return False


def sample_bytes(buf, off, info, idx):
    s, n = info["samples"][idx]
    return bytes(buf[off + s: off + s + n * 16])


def slot_layout(buf, off, info, idx):
    """(alamat awal, frame_awal_dilewati, frame_yang_ditulis)."""
    s, n = info["samples"][idx]
    a = off + s
    lead = 1 if n > 2 and bytes(buf[a:a + 16]) == b"\x00" * 16 else 0
    last = a + (n - 1) * 16
    tail = 1 if bytes(buf[last + 2:last + 16]) == DUMMY else 0
    return a, lead, n - lead - tail


def capacity(buf, off, info, idx):
    return slot_layout(buf, off, info, idx)[2] * 28


def replace_sample(buf, off, info, idx, pcm):
    """Tulis audio baru ke slot (ukuran tetap; byte flag loop/end tidak diubah)."""
    a, lead, body = slot_layout(buf, off, info, idx)
    for k, (b0, dt) in enumerate(ps_encode(pcm, body)):
        o = a + (lead + k) * 16
        buf[o] = b0
        buf[o + 2:o + 16] = dt
    return body * 28


def _flag_for(of, k, nb):
    """Flag frame ke-k untuk sampel yang diperpanjang (meniru pola flag asli)."""
    ob = len(of)
    if k == nb - 1:
        return of[-1]
    if k < ob - 1:
        return of[k]
    return of[ob - 2] if ob >= 2 else of[0]


def _plan_patches(buf, off, info, idx, delta):
    """Daftar (posisi relatif entry, nilai, format) yang harus diubah di header SBK
    supaya ukuran/offset sampel konsisten setelah sampel idx membesar delta byte."""
    P = {}

    def put(pos, val, fmt):
        if pos in P and P[pos] != (val, fmt):
            raise ValueError("Header SBK ambigu (field dipakai ganda); perbesar dibatalkan.")
        P[pos] = (val, fmt)

    if info["kind"] == "vag":
        vo = info["vo"]
        old = struct.unpack_from(">I", buf, off + vo[idx] + 12)[0]
        put(vo[idx] + 12, old + delta, ">I")
        for j in range(len(vo)):
            if vo[j] > vo[idx]:
                put(8 + 28 * j + 24, vo[j] + delta, "<I")
    else:
        st, total = info["st"], info["stream_size"]
        words = struct.unpack_from("<%dI" % (st // 4), buf, off)
        found = 0
        for j, (s, n) in enumerate(info["samples"]):
            ro, so = s - st, n * 16
            for p in range(len(words) - 1):
                if words[p] == ro and words[p + 1] == so:
                    if j == idx:
                        put((p + 1) * 4, so + delta, "<I")
                        found += 1
                    elif j > idx:
                        put(p * 4, ro + delta, "<I")
        if not found:
            raise ValueError("Referensi sampel tidak ditemukan di header SBK; "
                             "tidak bisa diperbesar dengan aman.")
        for p, w in enumerate(words):
            if w == total:
                put(p * 4, total + delta, "<I")
    return [(p, v, f) for p, (v, f) in P.items()]


def grow_sample(buf, e, info, idx, pcm):
    """Perbesar slot sampel agar muat seluruh pcm. buf (WAD) dan e.size ikut membesar,
    isi setelahnya bergeser. Return jumlah byte tambahan."""
    off = e.data_off
    a, lead, ob = slot_layout(buf, off, info, idx)
    nb = max(ob, -(-len(pcm) // 28))
    delta = (nb - ob) * 16
    if delta == 0:
        replace_sample(buf, off, info, idx, pcm)
        return 0
    patches = _plan_patches(buf, off, info, idx, delta)  # error di sini = buf belum diubah
    of = [buf[a + (lead + k) * 16 + 1] for k in range(ob)]
    buf[a + (lead + ob) * 16:a + (lead + ob) * 16] = bytes(delta)
    for k, (b0, dt) in enumerate(ps_encode(pcm, nb)):
        o = a + (lead + k) * 16
        buf[o] = b0
        buf[o + 1] = _flag_for(of, k, nb)
        buf[o + 2:o + 16] = dt
    e.size += delta
    struct.pack_into("<I", buf, e.size_off, e.size)
    for pos, val, fmt in patches:
        struct.pack_into(fmt, buf, off + pos, val)
    return delta


def set_vag_rate(buf, off, info, idx, rate):
    struct.pack_into(">I", buf, off + info["vo"][idx] + 16, rate)


def play_pcm(pcm, rate):
    """Putar audio. Windows/Wine: winsound. Linux/mac: paplay/aplay/afplay/ffplay."""
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    write_wav(tmp, pcm, rate)
    try:
        import winsound
        winsound.PlaySound(tmp, winsound.SND_FILENAME | winsound.SND_ASYNC)
        return True
    except ImportError:
        pass
    import subprocess
    for cmd in (["paplay"], ["aplay", "-q"], ["afplay"],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]):
        if shutil.which(cmd[0]):
            subprocess.Popen(cmd + [tmp])
            return True
    return False


def stop_audio():
    try:
        import winsound
        winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:
        pass


def read_wav(path, target_rate):
    try:
        with wave.open(path, "rb") as w:
            ch, sw, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
    except wave.Error as ex:
        raise ValueError("WAV tidak didukung (pakai PCM 8/16/24/32-bit): %s" % ex)
    if sw == 1:
        v = [(x - 128) << 8 for x in raw]
    elif sw == 2:
        v = list(struct.unpack("<%dh" % (len(raw) // 2), raw))
    elif sw == 3:
        v = [int.from_bytes(raw[i:i + 3], "little", signed=True) >> 8
             for i in range(0, len(raw) - 2, 3)]
    elif sw == 4:
        v = [x >> 16 for x in struct.unpack("<%di" % (len(raw) // 4), raw)]
    else:
        raise ValueError("Sample width %d tidak didukung." % sw)
    if ch > 1:
        v = [sum(v[i:i + ch]) // ch for i in range(0, len(v) - ch + 1, ch)]
    if rate != target_rate and v:
        n = int(len(v) * target_rate / rate)
        step = rate / target_rate
        out = []
        for i in range(n):
            p = i * step
            j = int(p)
            fr = p - j
            a = v[j]
            b = v[j + 1] if j + 1 < len(v) else a
            out.append(int(a + (b - a) * fr))
        v = out
    return v, rate


def write_wav(path, pcm, rate):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(pcm), *pcm))


class SbkSession:
    """Logika edit satu SBK tanpa GUI (dipakai dialog dan ganti-massal satu WAD).
    mode: 'grow' (perbesar), 'rate' (turunkan rate, VAG), 'cut' (potong)."""

    def __init__(self, app, hdr_off, mode="grow", user_rate=22050):
        self.app, self.hdr_off, self.mode, self.user_rate = app, hdr_off, mode, user_rate
        self.reload()

    def reload(self):
        self.e = next(x for x in self.app.entries if x.hdr_off == self.hdr_off)
        self.info = parse_sbk(self.app.buf, self.e.data_off, self.e.size)

    def rate_of(self, i):
        return self.info["rates"][i] or self.user_rate

    def wav_name(self, i):
        lab = self.info["labels"][i] or "sampel"
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in lab)
        return "%02d_%s.wav" % (i + 1, safe)

    def pcm_of(self, i):
        return ps_decode(sample_bytes(self.app.buf, self.e.data_off, self.info, i))

    def apply(self, i, path, confirm=None):
        """Ganti sampel i dari WAV. confirm(judul, teks)->bool dipanggil sebelum WAD membesar."""
        r = self.rate_of(i)
        if not r or not 4000 <= r <= 96000:
            raise ValueError("Sample rate harus 4000-96000.")
        buf, off, info = self.app.buf, self.e.data_off, self.info
        pcm, src_rate = read_wav(path, r)
        cap = capacity(buf, off, info, i)
        if len(pcm) <= cap:
            replace_sample(buf, off, info, i, pcm)
            return "%.2f dtk, %d Hz -> %d Hz" % (len(pcm) / r, src_rate, r)
        if self.mode == "grow":
            extra = (-(-len(pcm) // 28) * 28 - cap) // 28 * 16
            if confirm and not confirm(
                    "WAD akan membesar",
                    "Audio %.2f dtk > slot %.2f dtk.\nWAD membesar sekitar %d byte dan isi "
                    "setelahnya bergeser; ISO harus di-rebuild. Lanjut?" % (
                        len(pcm) / r, cap / r, extra)):
                raise RuntimeError("dibatalkan")
            grown = grow_sample(buf, self.e, info, i, pcm)
            self.app.entries = scan(buf)
            self.reload()
            return "diperbesar %d byte (%.2f dtk)" % (grown, len(pcm) / r)
        if self.mode == "rate":
            if info["kind"] != "vag":
                raise ValueError("Mode Turunkan rate hanya untuk bank VAG.")
            new_rate = int(r * cap / len(pcm))
            if new_rate < 4000:
                raise ValueError("Audio terlalu panjang: rate yang dibutuhkan (%d Hz) terlalu "
                                 "rendah. Pakai mode Perbesar." % new_rate)
            pcm2, _ = read_wav(path, new_rate)
            replace_sample(buf, off, info, i, pcm2)
            set_vag_rate(buf, off, info, i, new_rate)
            self.reload()
            return "rate diturunkan %d -> %d Hz agar muat (kualitas lebih rendah)" % (r, new_rate)
        replace_sample(buf, off, info, i, pcm)  # cut
        return "dipotong ke %.2f dtk" % (cap / r)

class SbkDialog(tk.Toplevel):
    """Editor audio di dalam satu SBK: putar / export / replace per sampel."""

    MODES_BLK = [("Perbesar WAD (tidak dipotong)", "grow"), ("Potong sesuai slot", "cut")]
    MODES_VAG = [("Perbesar WAD (tidak dipotong)", "grow"), ("Turunkan rate (ukuran tetap)", "rate"),
                 ("Potong sesuai slot", "cut")]

    def __init__(self, app, entry):
        sess = SbkSession(app, entry.hdr_off)  # ValueError -> ke pemanggil
        super().__init__(app)
        self.app, self.sess = app, sess
        self.e, self.info = sess.e, sess.info
        self.title("Edit audio: " + entry.name)
        self.geometry("700x500")
        info = self.info
        kind = "bank VAG (rate asli dari header)" if info["kind"] == "vag" else "bank audio internal"
        ttk.Label(self, wraplength=670, text="%s - %d sampel. %s" % (
            kind, len(info["samples"]), "Suara: " + ", ".join(info["names"][:12])
            + (" ..." if len(info["names"]) > 12 else ""))).pack(anchor="w", padx=8, pady=(8, 2))

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=4)
        self.rate = tk.StringVar(value="22050")
        if info["kind"] == "blk":
            ttk.Label(top, text="Sample rate (Hz):").pack(side="left")
            ttk.Entry(top, textvariable=self.rate, width=8).pack(side="left", padx=4)
            ttk.Label(top, text="(rate asli tidak ada di header; atur sampai terdengar normal)"
                      ).pack(side="left")
            self.rate.trace_add("write", lambda *a: self.fill())

        mrow = ttk.Frame(self)
        mrow.pack(fill="x", padx=8, pady=2)
        ttk.Label(mrow, text="Jika audio lebih panjang dari slot:").pack(side="left")
        self.modes = self.MODES_VAG if info["kind"] == "vag" else self.MODES_BLK
        self.mode = ttk.Combobox(mrow, state="readonly", width=34, values=[m[0] for m in self.modes])
        self.mode.current(0)
        self.mode.pack(side="left", padx=6)

        cols = ("no", "nama", "offset", "byte", "rate", "durasi", "loop")
        self.tv = ttk.Treeview(self, columns=cols, show="headings", height=10)
        for c, t, w in zip(cols, ("No", "Nama", "Offset WAD", "Byte", "Rate", "Durasi", "Loop"),
                           (36, 150, 90, 80, 60, 70, 50)):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8))
        self.tv.pack(fill="both", expand=True, padx=(8, 0))

        bt = ttk.Frame(self)
        bt.pack(fill="x", padx=8, pady=6)
        ttk.Button(bt, text="Putar", command=self.play).pack(side="left")
        ttk.Button(bt, text="Stop", command=stop_audio).pack(side="left", padx=2)
        ttk.Button(bt, text="Dengar WAV", command=self.preview).pack(side="left", padx=2)
        ttk.Button(bt, text="Export WAV", command=self.export).pack(side="left", padx=2)
        ttk.Button(bt, text="Replace dari WAV", command=self.replace).pack(side="left", padx=2)
        ttk.Button(bt, text="Tutup", command=self.destroy).pack(side="right")

        self.msg = ttk.Label(self, wraplength=670, justify="left",
                             text="Putar = dengar sampel asli. Dengar WAV = dengar file WAV-mu sebelum "
                                  "dimasukkan. Setelah Replace, klik SAVE di jendela utama.")
        self.msg.pack(fill="x", padx=8, pady=4)
        self.fill()

    # ---- sinkron dengan session ----
    def _sync(self):
        s = self.sess
        try:
            s.user_rate = int(self.rate.get())
        except ValueError:
            s.user_rate = None
        s.mode = self.modes[self.mode.current()][1]

    def _after(self):
        self.e, self.info = self.sess.e, self.sess.info
        self.app.refresh()
        self.fill()

    def user_rate(self):
        try:
            r = int(self.rate.get())
            if 4000 <= r <= 96000:
                return r
        except ValueError:
            pass
        return None

    def rate_of(self, i):
        return self.info["rates"][i] or self.user_rate()

    def fill(self):
        sel = self.tv.selection()
        self.tv.delete(*self.tv.get_children())
        for i, (s, n) in enumerate(self.info["samples"]):
            r = self.rate_of(i) or 22050
            self.tv.insert("", "end", iid=str(i), values=(
                i + 1, self.info["labels"][i], hex(self.e.data_off + s), n * 16, r,
                "%.2f s" % (n * 28 / r), "ya" if self.info["loops"][i] else "-"))
        if sel and self.tv.exists(sel[0]):
            self.tv.selection_set(sel[0])

    def pick(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("Info", "Pilih satu sampel dulu.", parent=self)
            return None
        i = int(sel[0])
        r = self.rate_of(i)
        if r is None:
            messagebox.showinfo("Info", "Sample rate harus 4000-96000.", parent=self)
            return None
        return i, r

    def pcm_of(self, i):
        return self.sess.pcm_of(i)

    def export(self):
        p = self.pick()
        if not p:
            return
        i, r = p
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".wav",
            initialfile="%s_%d.wav" % (self.info["labels"][i] or self.e.name, i + 1))
        if path:
            write_wav(path, self.pcm_of(i), r)
            self.msg.config(text="Export OK: %s (%d Hz)" % (os.path.basename(path), r))

    def _play(self, pcm, r):
        try:
            if not play_pcm(pcm, r):
                messagebox.showinfo("Putar", "Tidak ada pemutar audio yang bisa dipakai. "
                                             "Pakai Export WAV lalu putar di player lain.", parent=self)
        except Exception:
            messagebox.showerror("Gagal memutar", traceback.format_exc(), parent=self)

    def play(self):
        p = self.pick()
        if p:
            self._play(self.pcm_of(p[0]), p[1])

    def preview(self):
        p = self.pick()
        if not p:
            return
        path = filedialog.askopenfilename(
            parent=self, title="WAV untuk didengar", filetypes=[("WAV", "*.wav"), ("Semua", "*.*")])
        if not path:
            return
        try:
            pcm, _ = read_wav(path, p[1])
            self.msg.config(text="WAV-mu: %.2f dtk pada %d Hz (slot: %.2f dtk)." % (
                len(pcm) / p[1], p[1], capacity(self.app.buf, self.e.data_off, self.info, p[0]) / p[1]))
            self._play(pcm, p[1])
        except Exception as ex:
            messagebox.showerror("Gagal", str(ex), parent=self)

    def replace(self):
        p = self.pick()
        if not p:
            return
        i, _r = p
        path = filedialog.askopenfilename(
            parent=self, title="WAV pengganti", filetypes=[("WAV", "*.wav"), ("Semua", "*.*")])
        if not path:
            return
        self._sync()
        try:
            note = self.sess.apply(i, path, confirm=lambda t, m: messagebox.askyesno(t, m, parent=self))
        except RuntimeError:
            return
        except Exception as ex:
            messagebox.showerror("Gagal replace", str(ex), parent=self)
            return
        self.app.dirty = True
        self._after()
        self.msg.config(text="Sampel %d diganti: %s. Klik SAVE di jendela utama." % (i + 1, note))
        self.app.status.config(text=self.e.name + ": audio diganti. Klik SAVE.")

# ======================= KATALOG SBK (GoW 1) =======================
# Hasil pindai 216 WAD GoW 1: hanya SBK yang berisi audio (status ok) yang ditampilkan;
# WAD tanpa SBK dan 7 SBK tanpa audio (ref/kosong) disembunyikan.
# Format per baris: WAD|SBK|tipe|jumlah sampel|ukuran|status|nama suara (dipisah koma)
# status: ok = bisa diedit, ref = hanya referensi (audio di tempat lain), kosong = tidak ada data
CATALOG_TXT = """ARENA06.WAD|SBK_Arena00|blk|4|92576|ok|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
ARENA08.WAD|SBK_Arena00|blk|4|92576|ok|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
ARENA09.WAD|SBK_Arena00|blk|4|92576|ok|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
ARENA10.WAD|SBK_Arena00|blk|4|92576|ok|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
ARENA12.WAD|SBK_Arena12|blk|24|182776|ok|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_BALISTA_COCK_LP,SND_BALISTA_COCKED,SND_BALLISTA_FIRE,SND_RELOAD,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_BALLISTA_HIT,SND_M_AREC12_2
ARENA14.WAD|SBK_Arena14|blk|5|96584|ok|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_HOVER_LP,SND_M_AREC14_2
ARENA19.WAD|SBK_Arena00|blk|4|92576|ok|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
ARENA20.WAD|SBK_Arena00|blk|4|92576|ok|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
ARENA26.WAD|SBK_Arena00|blk|4|92576|ok|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
ARENA27.WAD|SBK_Arena36|blk|5|96664|ok|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_HOVER_LP,SND_DRAIN_ARENA_LP,SND_M_AREC27_2,SND_M_AREQ99_2
ATHN01A.WAD|SBK_Athn01A|blk|16|159828|ok|SND_OCEANSTORM_LP,SND_POSTSTORMAMB_LP,SND_WAVECRASH,SND_FABRICFLAP_LP,SND_LIFTHATCH_GRAB,SND_LIFTHATCH_STOP,SND_LIFTHATCH_REST,SND_HATCHBURST,SND_HATCHCLOSE,SND_HATCHBANG,SND_HATCH_CHAIN,SND_LOOKATME,SND_MI_A01MI09,SND_MI_A01MI10,SND_HL_A01HL19,SND_HL_A01HL20,SND_MI_A01MI11,SND_M_ATH1C1_4,SND_M_ATH1Q1_2,SND_RAIN_LP,SND_MI_THUNDER,SND_M_ATH1E4_2
ATHN01B.WAD|SBK_Athn01B|blk|20|202976|ok|SND_OCEANSTORMINT_LP,SND_DEADBOSSINTAMB_LP,SND_WATERHULL_LP,SND_WATER_DECK_LP,SND_CRATEAMB_LP,SND_HULLCRASH,SND_HL_A01HL22,SND_HYDRA_HEADSLAM,SND_HULLSMACK,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_WATER_DECK_L1,SND_HYDBABH_VODEFEATED,SND_HDYBABH_BITE,SND_M_ATH1C1_4,SND_M_ATH1Q1_2,SND_M_ATH1C2_2,SND_M_ATH1E4_2,SND_M_ATH1Q5_2,SND_M_ATH1E5_2
ATHN01C.WAD|SBK_Athn01C|blk|22|206672|ok|SND_OCEANSTORMINT_LP,SND_OCEANSTORM_LP,SND_POSTSTORMAMB_LP,SND_DEADBOSSINTAMB_LP,SND_WATERHULL_LP,SND_KEELCRASH,SND_BETWEENDABOATS,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_DOORKICK,SND_BEAMSCARE_LP,SND_HDYBABV_BITE,SND_MI_A01MI01,SND_MI_A01MI02,SND_MI_A01MI08,SND_HL_A01HL01,SND_HL_A01HL02,SND_HL_A01HL03,SND_HL_A01HL04,SND_HL_A01HL05,SND_MALESCREAM,SND_M_ATH1E5_2,SND_M_ATH1C3_2,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_RAIN_LP,SND_BHB_SWEEP_SCREAM,SND_HYDRA_HEADSLAM,SND_HDYBABV_BITE2,SND_HDYBABV_BITE3,SND_DISTANTSCREAM,SND_HL_PANIC,SND_AMBFILL_LP,SND_KEELCRASH2,SND_BHB_STRUGGLE2_LP,SND_M_ATH1E6_2,SND_HL_A01HL06,SND_MALEVO_GETHIT_CS
ATHN01D.WAD|SBK_Athn01D|blk|22|202920|ok|SND_OCEANSTORM_LP,SND_POSTSTORMAMB_LP,SND_DEADBOSSINTAMB_LP,SND_WAVECRASH,SND_LIFTDOOR_LP,SND_WATER_DECK_LP,SND_PULLBOX_LP,SND_ROPEZIP_LP,SND_TRAPPED_MEN,SND_WINDWHISTLES_LOOP,SND_DOORKICK,SND_PULLBOXCLUNK,SND_A01HL10,SND_UNLOCKDOOR,SND_HL_A01HL27,SND_M_ATH1C4_2,SND_M_ATH1E1_2,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_M_ATH1C5_2,SND_M_ATH1Q1_2,SND_M_ATH1E4_2,SND_M_ATH1E7_2,SND_M_ATH1Q7_2,SND_M_ATH1E6_2
ATHN01E.WAD|SBK_Athn01E|blk|19|199844|ok|SND_OCEANSTORM_LP,SND_OCEANSTORMINT_LP,SND_POSTSTORMAMB_LP,SND_DEADBOSSINTAMB_LP,SND_HYDRAMOUTHAMB_LP,SND_ROPEZIP_LP,SND_WATER_MAST_LP,SND_BREAKTRUSS,SND_NECKLACE,SND_ANCHORFALL_LP,SND_DECKSMASH,SND_MASTCRACK,SND_MASTBREAK,SND_POSDOOR_LP,SND_ANCHOR_HYDRA,SND_HL_A01HL14,SND_HL_A01HL14A,SND_HL_A01HL14B,SND_HL_A01HL14C,SND_HL_A01HL14D,SND_HL_A01HL14E,SND_HL_A01HL15,SND_SS_POSMAG06,SND_M_ATH1C7_2,SND_M_ATH1C2_2,SND_M_ATH1E2_2,SND_M_AQMAGC_Q,SND_KEELCRASH,SND_HL_A01HL14O,SND_HL_A01HL14AO,SND_HL_A01HL14BO,SND_HL_A01HL14CO,SND_HL_A01HL14DO,SND_HL_A01HL14EO,SND_HYDRA_HEADSLAM,SND_HDYBABV_BITE,SND_HDYBABV_BITE2,SND_HDYBABV_BITE3,SND_AHA_MASTBITE,SND_AHA_BITE,SND_WINDWHISTLES_LOOP,SND_M_ATH1Q3_2,SND_M_ATH1Q4_2,SND_M_ATH1E1_2,SND_CAP_STRUGGLE_LP,SND_M_ATH1E7_2,SND_M_ATH1Q6_2,SND_SCREAMWIND_LOOP
ATHN01EE.WAD|SBK_Athn01EE|blk|11|199632|ok|SND_BHA_STRUGGLEVO_LP,SND_BHB_SWEEP_SCREAM,SND_AHA_ATTKLONG_VO,SND_AHA_CHOMP,SND_AHA_GILLFLAP,SND_HYDBAB_GILLFLAP
ATHN01F.WAD|SBK_Athn01F|blk|22|197428|ok|SND_OCEANAMB_LP,SND_SHIPCABINAMB_LP,SND_WATERFALL_LP,SND_MI_A02MI01,SND_MI_A02MI02,SND_MI_A02MI023,SND_DOORKICK,SND_HL_A02HL01,SND_HL_A02HL01A,SND_HL_A02HL01B,SND_HL_A02HL01C,SND_HL_A02HL02A,SND_HL_A02HL02B,SND_HL_A02HL02C,SND_HL_A02HL02D,SND_M_ATH1E3_2,SND_SS_MOAN_01,SND_SS_MOAN_02,SND_SS_MOAN_03,SND_SS_MOAN_04,SND_SS_MOAN_05,SND_SS_MOAN_06,SND_SS_MOAN_07,SND_SS_MOAN_08,SND_SS_MOAN_09,SND_SS_MOAN_10,SND_SS_MOAN_11,SND_SS_MOAN_12,SND_SS_MOAN_13,SND_SS_MOAN_14,SND_SS_MOAN_15,SND_SS_MOAN_16,SND_SS_MOAN_17,SND_SS_MOAN_18,SND_SS_MOAN_19,SND_SS_MOAN_20,SND_SS_MOAN_21,SND_SS_MOAN_22,SND_SS_MOAN_23,SND_SS_MOAN_24,SND_SS_MOAN_25,SND_SS_MOAN_26,SND_SS_MOAN_27,SND_SS_MOAN_28,SND_SS_MOAN_29,SND_SS_MOAN_30,SND_SS_MOAN_31,SND_SS_MOAN_32,SND_SS_MOAN_33,SND_SS_MOAN_34,SND_SS_MOAN_35,SND_SS_MOAN_36,SND_SS_MOAN_37,SND_SS_MOAN_38,SND_SS_MOAN_39,SND_SS_MOAN_40,SND_SS_MOAN_41,SND_SS_MOAN_42,SND_SS_MOAN_43,SND_SS_MOAN_44,SND_SS_MOAN_45,SND_SS_MOAN_46,SND_SS_MOAN_47,SND_SS_MOAN_48,SND_SS_MOAN_49,SND_SS_MOAN_50,SND_SS_MOAN_51,SND_SS_MOAN_52,SND_SS_MOAN_53,SND_SS_MOAN_54,SND_SS_MOAN_55,SND_SS_MOAN_56,SND_SS_MOAN_57,SND_SS_MOAN_58,SND_BED_THUMPS,SND_BED_BREAK,SND_VASE_ROCK,SND_VASE_STABLE,SND_VASE_CRASH
ATHN02A.WAD|SBK_Athn02A|blk|18|187684|ok|SND_OCEANAMB_LP,SND_DISTANTSURFAMB_LP,SND_FLIESBUZZ_LP,SND_LAPPINGWAT_LP,SND_BOATCREAK_LP,SND_WATERFALL_LP,SND_BEHIND_FALLS_LP,SND_ROPECREAK_LP,SND_ELEVATOR_LP,SND_ELEVATOR_STOP,SND_MI_A02MI03,SND_MI_A02MI04,SND_MI_DOCKING,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_M_ATH2C1_4,SND_M_ATH2C2_2,SND_M_ATH2Q3_2,SND_DOCKRUBS_LP,SND_M_ATH2Q9_2,SND_M_ATH2E32_2,SND_M_ATH2E1_2
ATHN02B.WAD|SBK_Athn02B|blk|26|189832|ok|SND_CLIFFTOPAMB_LP,SND_DISTANTSURFAMB_LP,SND_INDOORAMB_LP,SND_FLIESBUZZ_LP,SND_ELEVATOR_LP,SND_ELEVATOR_STOP,SND_BALISTA_COCK_LP,SND_BALISTA_COCKED,SND_BALLISTA_FIRE,SND_BOLT_ZIPIN,SND_BOLT_HITWALL,SND_FABRICFLAP_LP,SND_METLIFTGATE_LP,SND_METLIFTDOOR_GRAB,SND_METLIFTDOOR_STOP,SND_BALLISTA2_FIRE,SND_LADDERPUSH_LP,SND_LADDER_STOP,SND_STATUE_PUSH_LP,SND_COLUMNBREAK,SND_HL_A02HL07,SND_HL_A02HL09,SND_M_ATH2C3_2,SND_M_ATH2E1_2,SND_M_ATH2Q4_2,SND_M_ATH2Q2_2,SND_STATUEWHOOSH,SND_STATUEHIT,SND_STRAINVOC,SND_PUSHGRUNTVOC,SND_M_ATH2C4_2,SND_M_ATH2Q5_2,SND_M_ATH2C5_2,SND_M_ATH2E3_2,SND_M_ATH2C9_2,SND_M_ATH2C0_2,SND_M_ATH2C8_4,SND_M_ATH2Q7_2,SND_M_ATH2E2_2
ATHN02C.WAD|SBK_Athn02C|blk|32|206188|ok|SND_INDOORAMB_LP,SND_CLIFFTOPAMB_LP,SND_OUTDOORAMB_LP,SND_BALISTA_COCK_LP,SND_BALISTA_COCKED,SND_BALLISTA_FIRE,SND_BOLT_ZIPIN,SND_BOLT_HITWALL,SND_BOLT_HITDOORS,SND_PLATFORM_LP,SND_METALGRIND_LP1,SND_METALGRIND_LP2,SND_STONEDOOR_LOOP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_MINOTAUR_HITDOOR,SND_BOLTFLY_ZOOM,SND_WOODCRATE_SHATTER,SND_WOODCRATE_HITGROUND,SND_FLIESBUZZ_LP,SND_M_ATH2C4_2,SND_M_ATH2C6_2,SND_M_ATH2C5_2,SND_M_ATH2E1_2,SND_M_ATH2Q1_2,SND_M_ATH2Q5_2,SND_RELOAD,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_ATH2Q6_2,SND_PILLARSLAM,SND_WINDWHISTLES_LOOP,SND_M_ATH2Q7_2,SND_M_ATH2E2_2,SND_M_ATH2E3_2,SND_M_ATH2Q8_2,SND_M_ATH2C0_2
ATHN02D.WAD|SBK_Athn02D|blk|11|177480|ok|SND_INDOORAMB_LP,SND_GODDOOR_LP,SND_MI_A02MI98,SND_MI_A02MI99,SND_M_AQMAGC_Q,SND_MED_CLAWSTR_WINDUP,SND_MED_EMERGE,SND_MED_EYEBEAM_FINISH,SND_MED_EYEBEAM_WINDUP,SND_MED_HEADRIP_SHRIEK,SND_MED_SHATTERSHRIEK
ATHN03A.WAD|SBK_Athn03A|blk|24|204156|ok|SND_OUTDOORAMB_LP,SND_OUTDOOR8AMB_LP,SND_OUTDOOR5AMB_LP,SND_SANDSTORMAMB_LP,SND_EXPLOSION,SND_STONEPEDESTAL_LP,SND_METALGATE_LP,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_SEWERGRATE,SND_FIREBALL,SND_CRASHDEBRIS,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_GATEBASH,SND_DOORSMASH,SND_MALESCREAM,SND_FEMALE_SCREAM,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_FEMALEVO_GETHIT,SND_FEMALEVO_DIE,SND_M_ATH3Q1_2,SND_M_ATH3C1_2,SND_M_ATH3Q2_2,SND_M_ATH3C2_2,SND_M_ATH3E1_2,SND_GATETRAP,SND_HL_A03HL01A,SND_HL_A03HL01B,SND_HL_A03HL01C,SND_HL_A03HL01D,SND_HL_A03HL01E,SND_HL_A03HL01F,SND_HL_A03HL01G,SND_ARES_STOMP,SND_FIREBALL_SPEC,SND_MALEVO_GETHIT_CS,SND_FEMALEVO_GETHIT_CS
ATHN03AA.WAD|SBK_Athn03AA|blk|19|113668|ok|SND_INDOORAMB_LP,SND_OUTDOORAMB_LP,SND_OUTDOOR8AMB_LP,SND_M_ATH3Q1_2,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_BIGFLAP_LP,SND_HL_A03HL01A,SND_HL_A03HL01B,SND_HL_A03HL01D,SND_HL_A03HL01C,SND_HL_A03HL01E,SND_HL_A03HL01F,SND_HL_A03HL01G,SND_ARES_STOMP,SND_FIREBALL_SPEC
ATHN03C.WAD|SBK_Athn03C|blk|19|203064|ok|SND_OUTDOOR9AMB_LP,SND_OUTDOOR5AMB_LP,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_EXPLOSION,SND_CRASHDEBRIS,SND_FIREBALL,SND_WOODDOORBREAK,SND_GATEBASH,SND_DOORSMASH,SND_MALESCREAM,SND_FEMALE_SCREAM,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_FEMALEVO_GETHIT,SND_FEMALEVO_DIE,SND_M_ATH3C2_2,SND_SMALL_WOODBREAK,SND_M_ATH3Q3_2,SND_SHAKE_BIG,SND_RUMBLE_BIG,SND_M_ATH3Q5_2,SND_HL_A03HL01A,SND_HL_A03HL01B,SND_HL_A03HL01C,SND_HL_A03HL01D,SND_HL_A03HL01E,SND_HL_A03HL01F,SND_HL_A03HL01G,SND_ARES_STOMP,SND_FIREBALL_SPEC,SND_MALEVO_GETHIT_CS,SND_FEMALEVO_GETHIT_CS
ATHN03D.WAD|SBK_Athn03D|blk|20|175704|ok|SND_OUTDOORAMB_LP,SND_OUTDOOR8AMB_LP,SND_SEWERAMB_LP,SND_TEMPLEAMB_LP,SND_STAIRCASE,SND_M_ATH3Q3_2,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_MI_A06MI02,SND_BIGFLAP_LP,SND_M_SEW2Q6_2,SND_ARES_STOMP,SND_FIREBALL_SPEC,SND_HL_A03HL01A,SND_HL_A03HL01B,SND_HL_A03HL01C,SND_HL_A03HL01D,SND_HL_A03HL01E,SND_HL_A03HL01F,SND_HL_A03HL01G
ATHN03E.WAD|SBK_Athn03E|blk|14|172352|ok|SND_OUTDOORAMB_LP,SND_OUTDOOR8AMB_LP,SND_OUTDOOR5AMB_LP,SND_SANDSTORMAMB_LP,SND_STONEPEDESTAL_LP,SND_METALGATE_LP,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_SEWERGRATE,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_GATEBASH,SND_DOORSMASH,SND_M_ATH3Q3_2,SND_ARES_STOMP,SND_FIREBALL_SPEC,SND_HL_A03HL01A,SND_HL_A03HL01B,SND_HL_A03HL01C,SND_HL_A03HL01D,SND_HL_A03HL01E,SND_HL_A03HL01F,SND_HL_A03HL01G
ATHN04A.WAD|SBK_Athn04A|blk|25|188784|ok|SND_OUTDOOR9AMB_LP,SND_OUTDOOR5AMB_LP,SND_INSIDEAMB_LP,SND_UNDERWATAMB_LP,SND_FIREBALL,SND_EXPLOSION,SND_ELEVATOR_STOP,SND_PEDESTAL_LP,SND_BRIDGE_COLLAPSE,SND_STATUEFALL,SND_STATUE_BOUNCE,SND_KEY_PICKUP,SND_FOOTSTEP_METAL,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTHATCH_GRAB,SND_LIFTHATCH_STOP,SND_DOORSMASH,SND_M_ATH4C2_4,SND_M_ATH4C1_2,SND_M_ATH4E1_2,SND_M_ATH4E2_2,SND_MALESCREAM,SND_FEMALE_SCREAM,SND_UNLOCKDOOR,SND_HL_A04HL04,SND_HL_A04HL08,SND_HL_A04HL11,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_FEMALEVO_GETHIT,SND_FEMALEVO_DIE,SND_M_ATH4Q1_2,SND_M_ATH4Q4_2,SND_M_ATH5E2_2,SND_M_ATH5C7_2,SND_M_ATH4Q7_2,SND_MALEVO_GETHIT_CS,SND_FEMALEVO_GETHIT_CS
ATHN04B.WAD|SBK_Athn04B|blk|16|72352|ok|SND_OUTDOOR5AMB_LP,SND_INSIDEAMB_LP,SND_SWORDHIT_BUSH,SND_CHASEGIRL,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_DOORSMASH,SND_HL_A04MI01,SND_HL_A04MI02,SND_MI_A04MI06,SND_M_ATH4Q1_2,SND_M_ATH4Q4_2,SND_M_ATH4C2_4,SND_M_ATH4C1_2,SND_M_ATH4E1_2,SND_M_ATH4E2_2
ATHN04C.WAD|SBK_Athn04C|blk|26|200772|ok|SND_OUTDOOR5AMB_LP,SND_INSIDEAMB_LP,SND_OUTDOOR6AMB_LP,SND_CEILING_COLLAPSE,SND_DRIPS,SND_HL_A04HL10,SND_M_ATH4Q4_2,SND_HITSHIELD,SND_BLADEBLOCK,SND_LIFTGATE_GRAB,SND_LIFTGATE_LP,SND_LIFTGATE_STOP
ATHN04D.WAD|SBK_Athn04D|blk|0|416|ref|SND_OUTDOOR5AMB_LP,SND_OUTDOOR2AMB_LP,SND_M_ATH5C7_2,SND_M_ATH6Q5_2
ATHN05A.WAD|SBK_Athn05A|blk|17|203016|ok|SND_OUTDOOR6AMB_LP,SND_INSIDEAMB_LP,SND_FIREBALL,SND_EXPLOSION,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_HL_A05HL04,SND_HL_A05HL09,SND_HL_A05HL11,SND_BREAKABLE_DOOR,SND_EXPLODEBRIS,SND_M_ATH5Q1_2,SND_M_ATH5C1_2,SND_M_ATH5Q2_2,SND_ARES_STOMP,SND_ARES_SWING,SND_ARES_SMASH,SND_ARESMOVES1,SND_ARESMOVES2,SND_ARES_FS,SND_HL_A05HL17,SND_M_ATH5C5_2,SND_A5FIGHTAMB_LP,SND_M_ATH5E3_2,SND_EXPLOSION_BIG
ATHN05AA.WAD|SBK_Athn05AA|blk|1|60200|ok|SND_M_ATH5Q1_2,SND_M_ATH5C1_2,SND_M_ATH5Q2_2,SND_HL_A05HL18
ATHN05B.WAD|SBK_Athn05B|blk|22|198760|ok|SND_OUTDOOR6AMB_LP,SND_INSIDEAMB_LP,SND_FIREBALL,SND_EXPLOSION,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_METALGATE_LP,SND_BIGSTONEDOOR_LP,SND_BALISTA_COCK_LP,SND_BALISTA_COCKED,SND_BALLISTA_FIRE,SND_BALLISTAROLL_LP,SND_DOORKICK,SND_DOORSMASH,SND_ARMSMOVE_UP,SND_ARMSMOVE_DOWN,SND_ARMSLOCK_DOWN,SND_ARMSLOCK_UP,SND_BOLT_HITWALL,SND_RELOAD,SND_M_ATH5E1_2,SND_M_ATH5C2_2,SND_M_ATH5C4_2,SND_M_ATH5Q3_2,SND_GODDOOR_LP,SND_M_AQMAGC_Q,SND_M_ATH5C5_2,SND_M_ATH5C6_2,SND_M_ATH5Q6_2,SND_MI_A05MI90,SND_M_ATH5E2_2,SND_BALLISTA_CLUNK
ATHN05BB.WAD|SBK_Athn05BB|blk|11|170104|ok|SND_OUTDOORAMB_LP,SND_INSIDEAMB_LP,SND_METALGATE_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_BIGSTONEDOOR_LP,SND_LADDERMOVE_LP,SND_BOLT_HITDOORS,SND_BREAKABLE_DOOR,SND_GODDOOR_OFF,SND_M_AQMAGC_Q,SND_M_ATH5E1_2,SND_M_ATH5C2_2,SND_M_ATH5Q3_2,SND_M_ATH5Q4_2
ATHN05C.WAD|SBK_Athn05C|blk|10|197576|ok|SND_OUTDOOR6AMB_LP,SND_INSIDEAMB_LP,SND_FIREBALL,SND_EXPLOSION,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_EXPLODEBRIS,SND_MED_EXPLO,SND_DOORKICK,SND_DOORSMASH,SND_M_ATH5C4_2,SND_M_ATH5Q5_2,SND_MI_A05MI99,SND_M_ATH5C2_2,SND_M_ATH5C6_2,SND_M_ATH5E1_2,SND_M_ATH5Q3_2,SND_MALEVO_DIE,SND_MENSCREAM,SND_BRIDGERAISE,SND_M_ATH5E2_2,SND_BRIDGE_KICK,SND_M_ATH5Q7_2,SND_M_ATH5E3_2
ATHN05D.WAD|SBK_Athn05D|blk|4|78332|ok|SND_INSIDEAMB_LP,SND_ELEVATOR_LP,SND_PEDESTAL_LP,SND_M_ATH5C4_2,SND_M_ATH5Q5_2,SND_M_ATH4Q9_2,SND_M_ATH5E2_2,SND_M_ATH6Q5_2,SND_M_ATH5C7_2
ATHN06A.WAD|SBK_Athn06A|blk|13|176332|ok|SND_OUTDOOR2AMB_LP,SND_OUTDOOR5AMB_LP,SND_TEMPLEAMB_LP,SND_FOUNTAIN_SM1_LP,SND_FOUNTAIN_SM2_LP,SND_MI_A06MI01,SND_MI_A06MI01A,SND_HL_A06HL01,SND_SHOVEL_TOSS,SND_SHOVEL_DIG,SND_BIG_FOUNTAIN_LP,SND_FOLIAGE_LP,SND_M_ATH6C1_2,SND_M_ATH6Q1_2,SND_M_ATH6C3_2,SND_M_ATH6Q5_2
ATHN06B.WAD|SBK_Athn06B|blk|25|204000|ok|SND_TEMPLEAMB_LP,SND_OUTSIDEAMB_LP,SND_OUTDOOR2AMB_LP,SND_STATUESLIDE_LOOP,SND_STATUEHITGROUND,SND_FOUNTAIN_LRG_LP,SND_FOUNTAIN_SM1_LP,SND_FOUNTAIN_SM2_LP,SND_BEAM_BREAKFALL,SND_BEAM_HITGROUND,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_STATUEWOBBLE,SND_WINDOWBREAK,SND_M_ATH6E1_2,SND_M_ATH6Q3_2,SND_M_ATH6Q2_2,SND_STATUE_SUCCESS,SND_M_ATH6C3_2,SND_M_ATH6E2_2,SND_SS_HARPYS,SND_M_ATH6E3_2,SND_M_ATH6Q6_2,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP
ATHN06C.WAD|SBK_Athn06C|blk|26|206668|ok|SND_OUTSIDEAMB_LP,SND_OCEANAMB_LP,SND_TEMPLEAMB_LP,SND_ELEVATOR_LP,SND_WINDWHISTLES_LOOP,SND_WATERFALL_LP,SND_BIGFALLS_LP,SND_STATUESLIDE_LOOP,SND_BEAM_TOTTER_LP,SND_WHEEL1TURN,SND_WHEEL2TURN,SND_WHEEL3TURN,SND_STATUEHITGROUND,SND_STONEDOOR_LOOP,SND_MI_A06MI02,SND_MI_A06MI05,SND_HL_A06HL02,SND_HL_A06HL02A,SND_HL_A06HL02B,SND_HL_A06HL02C,SND_HL_A06HL02D,SND_HL_A06HL02E,SND_HL_A06HL02F,SND_HL_A06HL02G,SND_HL_A06HL03,SND_HL_A06SS04,SND_SS_A06SS02A,SND_HL_A06HL04,SND_FOUNTAIN_SM1_LP,SND_FOOTSTEP_GRASS,SND_FOOTSTEP_GRASSSTEP,SND_FOOTSTEP_GRASSWALK,SND_FOOTSTEP_GRASSRUN,SND_FOOTSTEP_GRASSLAND,SND_M_ATH6C2_2,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_ORACLE_SHORT,SND_ORACLE_LONG,SND_M_ATH6E2_2,SND_M_ATH6E3_2,SND_M_ATH6Q6_2
ATHN07.WAD|SBK_Athn07A|blk|12|142280|ok|SND_OUTSIDEAMB_LP,SND_CLIFFSIDEAMB_LP,SND_OCEANAMB_LP,SND_SEWERAMB_LP,SND_FABRICFLAP_LP,SND_TIMEWARP_LP,SND_BIGFALLS_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_ATH7Q1_2,SND_M_ATH7Q2_2
ATHN07B.WAD|SBK_Athn07B|blk|12|142520|ok|SND_OUTSIDEAMB_LP,SND_CLIFFSIDEAMB_LP,SND_OCEANAMB_LP,SND_SEWERAMB_LP,SND_FABRICFLAP_LP,SND_TIMEWARP_LP,SND_BIGFALLS_LP,SND_MI_A07MI01,SND_MI_A07MI07,SND_MI_A07MI08,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_ATH7Q1_2,SND_M_ATH7Q2_2
ATHN08A.WAD|SBK_Athn08A|blk|21|206184|ok|SND_BIGHARBORAMB_LP,SND_ARESBAT_44,SND_ARESBAT_46,SND_ARESWILD_01A,SND_ARESWILD_03A,SND_ARESWILD_02C,SND_ARESWILD_04A,SND_ARESWILD_05A,SND_ARESWILD_06A,SND_ARESWILD_06B,SND_ARESWILD_07A,SND_ARESWILD_08A,SND_ARESWILD_09A,SND_ARESWILD_10A,SND_M_ATH8C1_2,SND_BIGFIRE_LP,SND_CROWD_PANIC_LP,SND_SWORDHIT_GIANTROCK,SND_FOOTSTEP_OCEAN,SND_FOOTSTEP_OCEANSTEP,SND_FOOTSTEP_OCEANWALK,SND_FOOTSTEP_OCEANRUN,SND_FOOTSTEP_OCEANLAND,SND_SWORDBLOCK_HIGH,SND_SWORDBLOCK_NORM,SND_CLAWSOPEN,SND_CRAPENDAGE_SLOW,SND_CRAPENDAGE_MEDIUM,SND_CRAPENDAGE_FAST,SND_BAR_WHOOSH_FAST,SND_BAR_WHOOSH_MED,SND_BAR_WHOOSH_SLOW,SND_BAR_SHLING_NORMAL,SND_BAR_SHLING_LOW,SND_PARRY_START,SND_PARRY_ATTACK,SND_PARRY_END,SND_OCEANAMB_LP,SND_HL_A08HL02A,SND_HL_A08HL02B,SND_ARESCOMBATVO,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S
ATHN08B.WAD|SBK_Athn08B|blk|17|183208|ok|SND_M_ATH8C2_2,SND_STONEBREAK,SND_EVILK1AMB_LP,SND_EVILK2AMB_LP,SND_FAMILY_VOGETHIT,SND_FAMILY_VODIE,SND_QUAKELP,SND_FAMILY_TAUNT,SND_KRATOS,SND_HEALTHCHARGE,SND_HL_A08HL01A,SND_HL_A08HL01B,SND_FLOORBREAK,SND_ROOFBREAK,SND_BEAMBREAK
ATHN08C.WAD|SBK_Athn08C|blk|21|205944|ok|SND_BIGHARBORAMB_LP,SND_ARESBAT_44,SND_ARESBAT_46,SND_ARESWILD_01A,SND_ARESWILD_02C,SND_ARESWILD_03A,SND_ARESWILD_04A,SND_ARESWILD_05A,SND_ARESWILD_06A,SND_ARESWILD_06B,SND_ARESWILD_07A,SND_ARESWILD_08A,SND_ARESWILD_09A,SND_ARESWILD_10A,SND_M_ATH8C3_2,SND_BIGFIRE_LP,SND_CROWD_PANIC_LP,SND_SWORDHIT_GIANTROCK,SND_FOOTSTEP_OCEAN,SND_FOOTSTEP_OCEANSTEP,SND_FOOTSTEP_OCEANWALK,SND_FOOTSTEP_OCEANRUN,SND_FOOTSTEP_OCEANLAND,SND_SWORDBLOCK_HIGH,SND_SWORDBLOCK_NORM,SND_CLAWSOPEN,SND_CRAPENDAGE_SLOW,SND_CRAPENDAGE_MEDIUM,SND_CRAPENDAGE_FAST,SND_BAR_WHOOSH_FAST,SND_BAR_WHOOSH_MED,SND_BAR_WHOOSH_SLOW,SND_BAR_SHLING_NORMAL,SND_BAR_SHLING_LOW,SND_PARRY_START,SND_PARRY_ATTACK,SND_PARRY_END,SND_ARESCOMBATVO,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S
ATRET01A.WAD|SBK_Atrt01A|blk|14|191748|ok|SND_OUTDOOR5AMB_LP,SND_OUTDOOR2AMB_LP,SND_TEMPLEAMB_LP,SND_FOUNTAIN_SM1_LP,SND_FOUNTAIN_SM2_LP,SND_BIG_FOUNTAIN_LP,SND_FOLIAGE_LP,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_M_ATR1E1_2,SND_SHOVEL_TOSS,SND_SHOVEL_DIG
ATRET01B.WAD|SBK_Atrt01B|blk|26|201184|ok|SND_TEMPLEAMB_LP,SND_OUTSIDEAMB_LP,SND_OUTDOOR2AMB_LP,SND_STATUESLIDE_LOOP,SND_STATUEHITGROUND,SND_FOUNTAIN_LRG_LP,SND_FOUNTAIN_SM1_LP,SND_FOUNTAIN_SM2_LP,SND_BEAM_BREAKFALL,SND_BEAM_HITGROUND,SND_BEAM_TOTTER_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_STATUEWOBBLE,SND_WINDOWBREAK,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_M_ATR1C1_2,SND_M_ATR1Q1_2,SND_M_ATR1E1_2
ATRET01C.WAD|SBK_Atrt01C|blk|20|200824|ok|SND_OUTSIDEAMB_LP,SND_OCEANAMB_LP,SND_TEMPLEAMB_LP,SND_ELEVATOR_LP,SND_WINDWHISTLES_LOOP,SND_WATERFALL_LP,SND_BIGFALLS_LP,SND_STATUESLIDE_LOOP,SND_BEAM_TOTTER_LP,SND_WHEEL1TURN,SND_WHEEL2TURN,SND_WHEEL3TURN,SND_STATUEHITGROUND,SND_STONEDOOR_LOOP,SND_MI_A06MI03,SND_MI_A06MI04,SND_MI_A06MI05,SND_FOUNTAIN_SM1_LP,SND_FOOTSTEP_GRASS,SND_FOOTSTEP_GRASSSTEP,SND_FOOTSTEP_GRASSWALK,SND_FOOTSTEP_GRASSRUN,SND_FOOTSTEP_GRASSLAND,SND_M_ATH6C1_2,SND_M_ATH6E1_2,SND_M_ATH6C2_2,SND_M_ATH6Q1_2,SND_M_ATH6Q2_2,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_M_ATR1E1_2,SND_M_ATR1Q1_2
DEST00.WAD|SBK_Dest00|blk|0|416|ref|SND_SANDSTORMAMB_LP,SND_OUTDOOR8AMB_LP,SND_M_DES1C1_2,SND_M_DES1Q1_2
DEST01.WAD|SBK_Dest01|blk|10|203024|ok|SND_SANDSTORMAMB_LP,SND_FOLIAGE_LP,SND_LONE_SHRUB,SND_LEAF_RUN_LP,SND_FABRICFLAP_LP,SND_STONEDOOR_LP,SND_DOORSPARKLE,SND_MI_D01MI01,SND_MI_D01MI02A,SND_MI_D01MI02B,SND_MI_D01MI02C,SND_MI_D01MI02D,SND_MI_D01MI02E,SND_MI_D01MI02F,SND_M_DES1C1_2,SND_M_DES1Q1_2,SND_M_DES1Q2_2,SND_M_DES1Q5_2,SND_M_DES1Q6_2,SND_M_DES1Q7_2,SND_MI_D01MI03,SND_SIRSCEAM,SND_SIRSUMMON,SND_SIRFIRESUM,SND_SIRLITSUM,SND_SIRSOUL,SND_SIRSCREAM_B_LP
DEST02.WAD|SBK_Dest02|blk|17|196856|ok|SND_SANDSTORMAMB_LP,SND_EXTSANDSTORMAMB_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOOR2_GRAB,SND_LIFTDOOR2_LIFT_LP,SND_LIFTDOOR2_STOP,SND_CRUSHBOX,SND_CRUSHER_LP,SND_PLANKS_LP,SND_GEARS1_LP,SND_GEARS2_LP,SND_BOXPUSH_LP,SND_BOXLAND,SND_BOXSTOP,SND_CHAIN_LP,SND_M_DES2C1_2,SND_M_DES2E1_2,SND_CONVEYOR_BREAK
DEST03.WAD|SBK_Dest03|blk|18|202496|ok|SND_SANDSTORMAMB_LP,SND_HOLLOWSTORMAMB_LP,SND_GIANTHORN1_LP,SND_GIANTHORN2_LP,SND_SANDWALL_LP,SND_WALLAWAY_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_M_DES3C1_2,SND_MI_D01MI02,SND_MI_D01MI05,SND_M_DES3Q1_2,SND_M_DES3Q2_2
HDES01A.WAD|SBK_Hade01A|blk|15|141112|ok|SND_HADESAMB_LP,SND_SLITHER_LP,SND_BREATHING_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1E2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
HDES01B.WAD|SBK_Hade01B|blk|23|177892|ok|SND_HADESAMB_LP,SND_FLESHLOGS_LP,SND_BLADEPASS,SND_SLITHER_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1Q2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
HDES01C.WAD|SBK_Hade01C|blk|20|201616|ok|SND_HADESAMB_LP,SND_COLUMNSPIN1_LP,SND_HIDEBLADE,SND_BLADEPASS,SND_HADESWIND_LP,SND_HOVER_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1E1_2,SND_M_HAD1Q2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
HDES01D.WAD|SBK_Hade01D|blk|13|98456|ok|SND_HADESAMB_LP,SND_SLITHER_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_FLESH,SND_M_HAD1C1_2,SND_M_HAD1C2_2,SND_M_HAD1E1_2,SND_M_HAD1E2_2,SND_M_HAD1Q2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
HDES01E.WAD|SBK_Hade01E|blk|16|192136|ok|SND_HADESAMB_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1C2_2,SND_M_HAD1E2_2,SND_M_HAD1Q2_2,SND_PLATFORM_RISE,SND_SCREAMS,SND_M_HAD1Q3_2,SND_KRATOSFALLSCREAM
HDES01F.WAD|SBK_Hade01F|blk|13|98680|ok|SND_HADESAMB_LP,SND_SLITHER_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1C2_2,SND_M_HAD1E1_2,SND_M_HAD1E2_2,SND_M_HAD1Q2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
HDES01G.WAD|SBK_Hade01G|blk|13|113568|ok|SND_HADESAMB_LP,SND_TIMEWARP_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1C2_2,SND_M_HAD1E1_2,SND_M_HAD1E2_2,SND_M_HAD1Q2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
OLYMP01.WAD|SBK_OLYM01|blk|20|191780|ok|SND_CLIFFSAMB_LP,SND_TEMPLEAMB_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_DOOR_OPEN,SND_DOOR_CLOSE,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_OLY1E1_2,SND_TIMEWARP_LP,SND_M_OLY1Q1_2
OLYMP02.WAD|SBK_OLYM02|blk|23|139368|ok|SND_CLIFFSAMB_LP,SND_TEMPLEAMB_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_DOOR_OPEN,SND_DOOR_CLOSE,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_STATUESMASH,SND_METALGATE_LP,SND_M_OLY1E1_2,SND_M_CREDITS1,SND_M_OLY1Q1_2
OLYMP04.WAD|SBK_OLYM91|blk|0|256|ref|SND_M_OLY1E2_2,SND_OUTSIDEAMB_LP
PAND00A.WAD|SBK_Pand00A|blk|20|202464|ok|SND_SANDSTORM_LOOP,SND_FLYINGBIRD_LP,SND_HAWK,SND_BUZZARDSQUAK_LP,SND_HAWKLP,SND_FLIESBUZZ_LP,SND_FABRICFLAP_LP,SND_M_PAN0Q1_2,SND_M_PAN0C1_2,SND_M_PAN0Q2_2,SND_M_PAN0E1_2,SND_M_PAN0Q3_2,SND_BIRDDIE_VOC,SND_SIRSCEAM,SND_SIRSUMMON,SND_SIRFIRESUM,SND_SIRLITSUM,SND_SIRSCREAM_B_LP,SND_TITANSTEP
PAND00B.WAD|SBK_Pand00B|blk|33|205756|ok|SND_SANDSTORM_LOOP,SND_STONEDOOR_LP,SND_ROCKSPULL_LP,SND_FLIESBUZZ_LP,SND_ROCKSPULL_STOP,SND_HAWKLP,SND_ROCKSPULL_SMALLSTOP,SND_SMALLDOOR1_LP,SND_SMALLDOOR2_LP,SND_FABRICFLAP_LP,SND_HL_P00HL01,SND_HL_P00HL02,SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_DRAG_FOOTSTEPS,SND_DRAGBODY_LP,SND_BODYDROP,SND_M_PAN0Q1_2,SND_M_PAN0C1_2,SND_M_PAN0Q2_2,SND_M_PAN0E1_2,SND_M_PAN0Q3_2,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_M_PAN0Q4_2,SND_M_PAN0Q5_2,SND_M_PAN0Q6_2,SND_M_PAN0C2_2
PAND00C.WAD|SBK_Pand00C|blk|14|204036|ok|SND_STONEDOOR_LP,SND_SKULLDOOR2_LP,SND_PRESSUREPLATE_LP,SND_HEADTURN_FOWARDLP,SND_HEADTURN_BACKWARDLP,SND_HEADTURNSTOP,SND_EYEBEAM_LP,SND_RINGTURN_LP,SND_RINGTURN_STOP,SND_WATERDRAIN_LOOP,SND_AUGER_LP,SND_ELEVATOR_SMALL_LP,SND_ELEVATOR_BIG_LP,SND_ELEVATOR_BIG_STOP,SND_INSERTGEM,SND_RING1AMB_LP,SND_RING2AMB_LP,SND_RING3AMB_LP,SND_CRANKLOWER_LP,SND_EYEDOOR_LP,SND_EYEDOOR_STOP,SND_SUNDOOR1_LP,SND_SUNDOOR2_LP,SND_EYEDOORLEVER_LP,SND_BIGSTONEDOOR_ROLL_L,SND_RINGTURN_SMALLSTOP,SND_SUNDOOR_LIGHT,SND_SUNDOOR_LIGHT_LAST,SND_M_PAN0Q1_2,SND_M_PAN0C1_2,SND_M_PAN0Q2_2,SND_M_PAN0E1_2,SND_M_PAN0Q3_2,SND_M_PAN0Q4_2,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LP,SND_LIFTDOOR_STOP,SND_M_PAN0Q5_2,SND_M_PAN0Q6_2,SND_M_PAN0C2_2,SND_MI_P00MI99,SND_MI_P00NA02,SND_M_PAN3E1_2,SND_M_PAN4E1_2,SND_M_PAN3E3_2,SND_M_PAN0Q7_2,SND_M_PAN0C5_2,SND_INSERTGEM_UW,SND_M_PAN0Q8_2,SND_OUTSIDEAMB_LP
PAND00D.WAD|SBK_Pand00D|blk|18|200664|ok|SND_SANDSTORM_LOOP,SND_CAVEAMB_LP,SND_STONEDOOR_LP,SND_CRUSHERSTART_FAST,SND_CRUSHERSTART_SLOW,SND_CRUSHERHIT_FAST,SND_CRUSHERHIT_SLOW,SND_PRESSUREPLATE_LP,SND_EYEBEAM_LP,SND_EYEDOOR_LP,SND_RING1AMB_LP,SND_EYEDOORAMB_LP,SND_CRUSHERSLIDE_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_BLUESPARKLE_LP,SND_REDSPARKLE_LP,SND_GREENSPARKLE_LP,SND_M_PAN0Q1_2,SND_M_PAN0C1_2,SND_M_PAN0Q2_2,SND_M_PAN0E1_2,SND_M_PAN0Q3_2,SND_M_PAN0Q4_2,SND_M_PAN0Q5_2,SND_M_PAN0Q6_2,SND_M_PAN0C2_2,SND_M_PAN4E1_2,SND_M_PAN1C9_2,SND_M_PAN1E3_2,SND_M_PAN1QD_2,SND_M_PAN3E3_2,SND_M_PAN0Q7_2,SND_M_PAN0C5_2,SND_GOLD_MAGIC,SND_M_PAN0Q8_2,SND_M_PAN0E3_2,SND_MUSEKEY,SND_MUSEDOOR_LP
PAND00E.WAD|SBK_Pand00E|blk|22|136136|ok|SND_SANDSTORM_LOOP,SND_MI_P00MI01D,SND_MI_P00MI01E,SND_BONFIRE_LP,SND_HL_P00HL05,SND_FIRST_POKE,SND_SECOND_POKE,SND_SLOW_POKE,SND_RND_CRACKLE,SND_POLE_DIRT,SND_FOOTSTEP1,SND_FOOTSTEP2,SND_STOKE_GRUNTS,SND_BODYDROP2,SND_CHAIN_LP,SND_M_PAN3E3_2,SND_M_PAN0Q7_2
PAND01A.WAD|SBK_Pand01A|blk|14|196680|ok|SND_GEARSPIN_LP,SND_BLOCKSLIDE_LOOP,SND_STONEPEDESTAL_LP,SND_ALTERSPIN_LP,SND_SHIELDDOOR_LP,SND_ROPELOWER_LOOP,SND_SHIELDINSERT,SND_ROPELOWER_STOP,SND_BATTLEAMB_LP,SND_CAVEAMB_LP,SND_WATERFALL_LP,SND_SOLDIERSHOT1,SND_SOLDIERSHOT2,SND_METALGATE_LP,SND_ZEUS_PICKUP,SND_SHIELDGLOW_LP,SND_PUSHBLOCKCLUNK,SND_GODDOOR_LP,SND_M_AQMAGC_Q,SND_M_PAN1C1_2,SND_M_PAN1C2_2,SND_M_PAN1C3_2,SND_M_PAN1E1_2,SND_M_PAN1Q1_2,SND_M_PAN1Q2_2,SND_M_PAN1Q3_2,SND_MI_P01MI99
PAND01B.WAD|SBK_Pand01B|blk|19|211520|ok|SND_GEARSPIN_LP,SND_SAWBLADE_LP,SND_BIGWOODDOOR_OPEN,SND_BIGWOODDOOR_CLOSE,SND_STONEBARS_LP,SND_CONVEYOR_LP,SND_CRUSHERSTART_FAST,SND_CRUSHERSTART_SLOW,SND_CRUSHERHIT_FAST,SND_CRUSHERHIT_SLOW,SND_STONEPEDESTAL_LP,SND_CAVEAMB_LP,SND_SAWBLADE_EXT_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_M_PAN1C5_2,SND_M_PAN1Q3_2,SND_M_PAN1Q6_2,SND_M_PAN1C7_2,SND_M_PAN1C4_2,SND_M_PAN1Q4_2,SND_M_PAN1E2_2
PAND01BB.WAD|SBK_Pand01BB|blk|16|193992|ok|SND_BIGLOGPOKER,SND_BOULDERRAISE_LOOP,SND_BOULDER_STOP,SND_CAVEAMB_LP,SND_ATLASAMB_LP,SND_BIGFIRE_LP,SND_COFFINSLAB_LP,SND_SANDSTORM_LOOP,SND_COFFINMOVE_LOOP,SND_BIGFIRE2_LP,SND_SLABBREAK,SND_HEADRIPOFF_LP,SND_HEADRIPOFF,SND_COFFINSLAB2_LP,SND_SKULLKEY_PUP,SND_M_PAN1C7_2,SND_M_PAN1E2_2,SND_M_PAN1E3_2,SND_M_PAN1Q6_2,SND_M_PAN1Q7_2,SND_M_PAN1Q8_2,SND_M_PAN1Q9_2,SND_M_PAN1QC_2,SND_M_PAN1C9_2,SND_M_PAN1QD_2,SND_M_AQMAGC_Q
PAND01C.WAD|SBK_Pand01C|blk|18|183508|ok|SND_WINDWHISTLES_LOOP,SND_GEARSLOW_LP,SND_GEARMED_LP,SND_GEARHIGH_LP,SND_FLOORBUCKLE,SND_FLOOROPEN,SND_CHAINLOWER_LOOP,SND_TRAPROOMDOOR_LP,SND_SANDSTORM_LOOP,SND_CAVEAMB_LP,SND_CONVEYOR_LP,SND_FLOORRAISE_LP,SND_GEARSTOP,SND_FABRICFLAP_LP,SND_HANDGRAB_CHAIN,SND_SLIDECHAIN_LP,SND_HANDLE_PICKUP,SND_M_PAN1C5_2,SND_M_PAN1C6_2,SND_M_PAN1Q4_2,SND_M_PAN1Q5_2,SND_M_PAN1C8_2,SND_M_PAN1QA_2,SND_M_PAN1QB_2,SND_M_AQMAGC_Q
PAND01CC.WAD|SBK_Pand01CC|blk|5|150632|ok|SND_SIRSCEAM,SND_SIRSUMMON,SND_SIRFIRESUM,SND_SIRLITSUM,SND_SIRSCREAM_B_LP
PAND01D.WAD|SBK_Pand01D|blk|8|139524|ok|SND_STONEPEDESTAL_LP,SND_PUSHER_LP,SND_FIGHTMOVIE,SND_BATTLEAMB_LP,SND_CAVEAMB_LP,SND_FALLSCREAM,SND_PUSHER_STOP,SND_PUSHER_BACK_LP,SND_WATERFALL2_LP,SND_HADES_PICKUP,SND_SHIELDGLOW_LP,SND_M_PAN1C2_2,SND_M_PAN1Q1_2,SND_M_PAN1Q2_2,SND_M_PAN1QA_2,SND_M_PAN1QB_2,SND_M_PAN1C8_2,SND_M_AQMAGC_Q
PAND02A.WAD|SBK_Pand02A|blk|4|49084|ok|SND_OUTSIDEAMB_LP,SND_BLOCKSLIDE_LOOP,SND_STONE_THUD,SND_M_PAN2C1_2,SND_M_PAN2Q1_2,SND_M_PAN2E1_2,SND_RING2AMB_LP
PAND02AA.WAD|SBK_Pand02AA|blk|16|195660|ok|SND_SPINROOMDOOR_LOOP,SND_SPINROOM_LP,SND_OUTSIDEAMB_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_SPIKETRAP,SND_GRATECLOSE_LP,SND_LEVERUP_LP,SND_M_PAN2C1_2,SND_M_PAN2E1_2,SND_M_PAN2Q1_2,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND
PAND02B.WAD|SBK_Pand02B|blk|16|187184|ok|SND_SPINROOMDOOR_LOOP,SND_STONEPEDESTAL_LP,SND_OUTSIDEAMB_LP,SND_WINDWHISTLES_LOOP,SND_STONEDOOR_LP,SND_DOORSLIDE_LOOP,SND_DOORFALL_WHOOSH,SND_DOORFALL_LAND,SND_CREAKING_LP,SND_M_PAN2C2_2,SND_M_PAN2E1_2,SND_M_PAN2Q5_2,SND_M_PAN2Q0_2,SND_TITAN_FS,SND_CHAIN_HIT,SND_CHAIN_LP,SND_CAGEHALLAMB_LP,SND_M_AQMAGC_Q
PAND02C.WAD|SBK_Pand02C|blk|16|199152|ok|SND_FLMTHROWERS_L_LP,SND_FLMTHROWERS_R_LP,SND_FLMTHROW_LMOVE_LP,SND_FLMTHROW_RMOVE_LP,SND_STONEBUTTON_LP,SND_HANGINGCAGES_LP,SND_CAGEHITGROUND,SND_CAGEDRAG_LP,SND_STONEDOOR_LP,SND_FLAMES_L_LOOP,SND_FLAMES_R_LOOP,SND_CAGELOWER_LP,SND_CAGEHALLAMB_LP,SND_GENERALAMB_LP,SND_HANDLE_PICKUP,SND_CAGE_CLUNK,SND_HL_P02HL06,SND_HL_P02HL07,SND_HL_P02HL08,SND_HL_P02HL08A,SND_HL_P02HL09,SND_HL_P02HL09A,SND_HL_P02HL10,SND_HL_P02HL11,SND_HL_P02HL11A,SND_INTROMOANS,SND_M_PAN2C2_2,SND_M_PAN2C3_2,SND_M_PAN2E2_2,SND_M_PAN2Q2_2,SND_M_PAN2Q5_2,SND_SS_P02MP03,SND_M_PAN2E1_2,SND_OUTSIDEAMB_LP,SND_CAGEBANG,SND_PLATECLOSE,SND_FOUNTAIN_LP,SND_M_PAN2C1_2
PAND02D.WAD|SBK_Pand02D|blk|16|198912|ok|SND_GENERALAMB_LP,SND_TRIDENTHOLD_LP,SND_TRIDENTLIFT_LP,SND_TRIDENTREMOVE,SND_GATE_LP,SND_M_PAN2C4_2,SND_M_PAN2E3_2,SND_M_PAN2E4_2,SND_M_PAN2Q4_2,SND_M_PAN2Q3_2,SND_DASHDOOR_BREAK,SND_BLOCKSLIDE_LP,SND_M_PAN2Q6_2,SND_UNDERWATAMB_LP,SND_M_AQMAGC_Q,SND_M_PAN2C1_2
PAND02DD.WAD|SBK_Pand02DD|blk|5|48088|ok|SND_GENERALAMB_LP,SND_M_PAN2E3_2,SND_M_PAN2Q6_2,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_M_PAN2C4_2,SND_UNDERWATAMB_LP,SND_M_PAN2C1_2
PAND02F.WAD|SBK_Pand02F|blk|10|147768|ok|SND_UNDERWATAMB_LP,SND_GENERALAMB_LP,SND_BUBBLES,SND_DIRTFALL,SND_FOUNTAIN_LP,SND_WATERFILL_LOOP,SND_M_PAN2C4_2,SND_M_PAN2E4_2,SND_DASHDOOR_BREAK,SND_M_PAN2E3_2,SND_M_PAN2C1_2
PAND02G.WAD|SBK_Pand02G|blk|14|182704|ok|SND_UNDERWATAMB_LP,SND_GENERALAMB_LP,SND_BUBBLES,SND_DIRTFALL,SND_CONSTRICT_CLOSE_LP,SND_CONSTRICTOR_THUD,SND_BLADEROTATE_ONESHOT,SND_BLADEROTATE_LP,SND_CONSTRICTOR_STOP,SND_CONSTRICT_OPEN_LP,SND_LEVERWATERFALL_LP,SND_MINIWATERFALL_LP,SND_STONEDOOR_UW_LOOP,SND_SPIKEOUT,SND_M_PAN2C4_2,SND_M_PAN2E4_2,SND_M_PAN2E3_2,SND_M_PAN2C1_2
PAND02H.WAD|SBK_Pand02H|blk|13|156736|ok|SND_UNDERWATAMB_LP,SND_GENERALAMB_LP,SND_BUBBLES,SND_DIRTFALL,SND_STONEDOOR_UW_LOOP,SND_PUSHERBLOCKS_LP,SND_STATUERAISE_LP,SND_WATERFALL_LOOP,SND_CHAIN_LP,SND_M_PAN2C4_2,SND_M_PAN2E4_2,SND_M_PAN2C1_2
PAND02I.WAD|SBK_Pand02I|blk|6|112240|ok|SND_UNDERWATAMB_LP,SND_GENERALAMB_LP,SND_BUBBLES,SND_DIRTFALL,SND_STONEDOOR_UW_LOOP,SND_WATERFILL_LOOP,SND_STONECOL1_LOOP,SND_STONECOL1_UW_LOOP,SND_STONECOL2_LOOP,SND_STONECOL2_UW_LOOP,SND_STONECOL3_LOOP,SND_STONECOL3_UW_LOOP,SND_STONECOL4_LOOP,SND_STONECOL4_UW_LOOP,SND_WATERFALL1_LP,SND_WATERFALL2_LP,SND_WATERFALL3_LP,SND_WATERFALL4_LP,SND_UW_WATFALL1_LP,SND_UW_WATFALL2_LP,SND_UW_WATFALL3_LP,SND_UW_WATFALL4_LP,SND_CHAINLOOP_LP,SND_LEVERWATER_LP,SND_M_PAN2C4_2,SND_M_PAN2E4_2,SND_M_PAN2C2_2,SND_M_PAN2E5_2,SND_M_PAN2Q5_2,SND_M_PAN2Q7_2,SND_M_PAN2Q8_2,SND_M_PAN2C1_2
PAND03A.WAD|SBK_Pand03A|blk|17|198404|ok|SND_LAVAFLOW_LP,SND_BIGFIRE_LP,SND_STONEPEDESTAL_LP,SND_UNDERWATER_LEVER,SND_STATUERAISE_LP,SND_STATLIGHTBEAM_LP,SND_HEADTURN_FOWARDLP,SND_HEADTURN_BACKWARDLP,SND_HEADTURNSTOP,SND_BLOCKSLIDE_LOOP,SND_LAVAAMB_LP,SND_RUMBLEAMB_LP,SND_STONEDOOR_LP,SND_SACRIFICE,SND_STONEBARS_LP,SND_RINGAPPEAR,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_PAN3E1_2,SND_M_PAN3E2_2,SND_M_PAN3E3_2,SND_M_PAN3C1_2,SND_M_PAN3Q1_2,SND_M_PAN3Q2_2,SND_M_PAN3Q3_2,SND_M_PAN3Q4_2,SND_GRATE_RISE_LP,SND_M_PAN3Q7_2,SND_M_PAN3Q9_2,SND_M_PAN3E7_2,SND_SACRIFICEPUME_LP,SND_M_PAN3C2_2,SND_M_PAN3C9_2,SND_LIGHTONESHOT
PAND03B.WAD|SBK_Pand03B|blk|20|201120|ok|SND_LAVAFLOW_LP,SND_STONEPEDESTAL_LP,SND_STONEDOOR_LP,SND_FOUNTAIN_LP,SND_ELEVATORUP_LOOP,SND_ELEVATORDOWN_LOOP,SND_ELEVATOR_STOP,SND_BLOCKSLIDE_LOOP,SND_STONEBLOCK_LP,SND_STONEBLOCKHIT,SND_STONEBLOCKCHAIN_LP,SND_LAVAAMB_LP,SND_RUMBLEAMB_LP,SND_STONEDOOROPEN,SND_SPEARWHOOSH,SND_WOODBARS_LP,SND_STONEPUSH_LP,SND_STONE_FALL,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_M_PAN3E2_2,SND_M_PAN3C2_2,SND_M_PAN3Q2_2,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_PAN3E7_2
PAND03C.WAD|SBK_Pand03C|blk|19|193808|ok|SND_LAVAFLOW_LP,SND_BOULDERROLL_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_GEARROOM_AMB_LP,SND_LAVAFALLS_LP,SND_BLDR_BOUNCE,SND_BWAYAMB_LP,SND_RUMBLEAMB_LP,SND_BIGFIRE_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_PAN3C3_2,SND_M_PAN3C4_2
PAND03D.WAD|SBK_Pand03D|blk|13|127104|ok|SND_LAVAFLOW_LP,SND_AR_BIGGEARS_LP,SND_CAGEFORWARD_LP,SND_CAGEBACK_LP,SND_CAGE_STOP,SND_GONDOLA_LP,SND_AR_BIGGEARS_L_LP,SND_AR_BIGGEARS_R_LP,SND_LAVAAMB_LP,SND_RUMBLEAMB_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_PAN3E4_2,SND_M_PAN3C4_2,SND_M_PAN3Q5_2,SND_M_PAN3E7_2
PAND03E.WAD|SBK_Pand03E|blk|15|180148|ok|SND_LAVAAMB_LP,SND_LAVAFLOW_LP,SND_BIGFIRE_LP,SND_SPINWHEEL_LP,SND_SPINBLADE_LP,SND_STATLIGHTBEAM_LP,SND_M_PAN3E4_2,SND_M_PAN3Q5_2,SND_LAVAFALL1_LP,SND_LAVAFALL2_LP,SND_ROPEZIP_LP,SND_M_PAN3Q8_2,SND_M_PAN3E7_2,SND_KRATOSFALLSCREAM,SND_STATUEBEAM_ON,SND_M_AQMAGC_Q
PAND03F.WAD|SBK_Pand03F|blk|13|153096|ok|SND_LAVAHALLAMB_LP,SND_LAVAGRATE_LP,SND_STAIR_CRASH,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_WATERFALL_LP,SND_M_PAN3E5_2,SND_M_PAN3E4_2,SND_M_PAN3C5_2,SND_M_PAN3Q6_2,SND_MI_P03MI99,SND_POSDOOR_LP,SND_M_PAN3E1_2,SND_TURNWHEEL,SND_MB_LAVAAMB_LP,SND_SMALL_LAVAFALL1_LP,SND_SMALL_LAVAFALL2_LP,SND_M_PAN3E7_2,SND_M_PAN3C9_2,SND_LAVAAMB_LP
PAND03G.WAD|SBK_Pand03G|blk|32|204952|ok|SND_MB_LAVAAMB_LP,SND_LAVAPOOL_LP,SND_LAVAGRATE_LP,SND_WATERFALL_LP,SND_SMALL_LAVAFALL1_LP,SND_SMALL_LAVAFALL2_LP,SND_BIG_LAVAFALL1_LP,SND_BIG_LAVAFALL2_LP,SND_BIG_LAVAFALL3_LP,SND_LOGROLL_LP,SND_LOG_FALL,SND_GATE_SLAM,SND_DOORCRASH,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_LOGSHATTER,SND_M_PAN3E5_2,SND_M_PAN3C5_2,SND_MB_FOOTSTEP,SND_MB_STEP_ARMOR,SND_MB_STEP_NOARMOR,SND_MB_JUMP_LAND,SND_M_PAN3C4_2,SND_BMIDOOR_THUD,SND_M_PAN3E7_2,SND_M_PAN3C6_2,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_M_PAN3C9_2
PAND03GG.WAD|SBK_Pand03GG|blk|11|201760|ok|SND_MB_VOWIN,SND_MB_VOSTAGGER_ABC,SND_MB_VOSTAGGER_A,SND_MB_VOSTAGGER_B,SND_MB_VOSTAGGER_C,SND_MB_VOGENTAUNT,SND_MB_VOPLATFORMTAUNT,SND_MB_VOLOGHIT_ABC,SND_MB_VOLOGHIT_A,SND_MB_VOLOGHIT_B,SND_MB_VOLOGHIT_C,SND_MB_VOARMORBREAK,SND_MB_2AXEHITGROUND,SND_MB_2AXEHITMETAL,SND_MB_1AXEHITGROUND
PAND03H.WAD|SBK_Pand03H|blk|21|163800|ok|SND_MB_LAVAAMB_LP,SND_LAVAAMB_LP,SND_WATERFALL_LP,SND_LAVAPOOL_LP,SND_LAVAGRATE_LP,SND_LEVER_PULLOUT_LP,SND_LEVER_SLIDEIN_LP,SND_LEVER_STOP,SND_SMALL_LAVAFALL1_LP,SND_SMALL_LAVAFALL2_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_COFFINSLAB2_LP,SND_SLABBREAK,SND_HEADRIPOFF_LP,SND_HEADRIPOFF,SND_BIG_LAVAFALL1_LP,SND_BIG_LAVAFALL2_LP,SND_BIG_LAVAFALL3_LP,SND_SKULLKEY_PUP,SND_M_PAN3E5_2,SND_M_PAN3C5_2,SND_M_PAN3E4_2,SND_M_PAN3E7_2,SND_M_PAN3QA_2,SND_M_PAN3C9_2,SND_M_AQMAGC_Q
PAND03I.WAD|SBK_Pand03I|blk|15|151096|ok|SND_MB_LAVAAMB_LP,SND_LAVAAMB_LP,SND_WATERFALL_LP,SND_LAVAPOOL_LP,SND_LAVAGRATE_LP,SND_LEVER_PULLOUT_LP,SND_LEVER_SLIDEIN_LP,SND_LEVER_STOP,SND_SMALL_LAVAFALL1_LP,SND_SMALL_LAVAFALL2_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_BIG_LAVAFALL1_LP,SND_BIG_LAVAFALL2_LP,SND_BIG_LAVAFALL3_LP,SND_POSDOOR_LP,SND_MI_P03MI99,SND_M_PAN3E5_2,SND_M_PAN3Q6_2,SND_M_PAN3E1_2,SND_M_PAN3E7_2,SND_M_PAN3C9_2,SND_M_AQMAGC_Q
PAND03J.WAD|SBK_Pand03J|blk|23|180368|ok|SND_MB_LAVAAMB_LP,SND_LAVAAMB_LP,SND_WATERFALL_LP,SND_LAVAPOOL_LP,SND_LAVAGRATE_LP,SND_SMALL_LAVAFALL1_LP,SND_SMALL_LAVAFALL2_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_BIG_LAVAFALL1_LP,SND_BIG_LAVAFALL2_LP,SND_LOGROLL_LP,SND_LOG_FALL,SND_DOORCRASH,SND_LEVER_PULLOUT_LP,SND_LEVER_SLIDEIN_LP,SND_LEVER_STOP,SND_M_PAN3E1_2,SND_M_PAN3Q6_2,SND_M_PAN3Q1_2,SND_M_PAN3E2_2,SND_M_PAN3E7_2,SND_M_PAN3C9_2,SND_LOGSHATTER
PAND04AA.WAD|SBK_Pand04AA|blk|9|134904|ok|SND_CLIFFSAMB_LP,SND_HANDS_LP,SND_HANDS_SHIFT,SND_WINDWHISTLES_LOOP,SND_ELEVATOR_BIG_LP,SND_ELEVATOR_BIG_STOP,SND_MI_P00MI98,SND_M_PAN4C1_2,SND_M_PAN4E1_2,SND_M_PAN4Q1_2,SND_M_PAN4Q2_2,SND_M_PAN4QE_2,SND_M_PAN4C2_2,SND_M_PAN4C9_2,SND_M_PAN4QZ_2
PAND04C.WAD|SBK_Pand04C|blk|19|202468|ok|SND_ELEVATOR_LP,SND_ELEVATOR_STOP,SND_BIRDS_LOOP,SND_WINDWHISTLES_LOOP,SND_CLIFFS2AMB_LP,SND_CAVERN1AMB_LP,SND_STONEPEDESTAL_LP,SND_DOORSLIDE_LOOP,SND_DOORSLIDE_STOP,SND_WOODLIFTDOOR_LP,SND_WOODLIFTDOOR_GRAB,SND_WOODLIFTDOOR_STOP,SND_BLOCKLOWER_LP,SND_WOODBARS_LP,SND_WOODGATE_LP,SND_SPIKETRAP,SND_SPIKE_DOWN,SND_PUSHBLOCK_LP,SND_BLOCK_CLUNK,SND_BLOCKSHATTER,SND_NECKLACE,SND_M_PAN4C1_2,SND_M_PAN4C3_2,SND_M_PAN4C5_2,SND_M_PAN4C6_2,SND_M_PAN4E3_2,SND_M_PAN4Q1_2,SND_M_PAN4Q2_2,SND_M_PAN4Q3_2,SND_GEARSLOW_LP,SND_GEARMED_LP,SND_GEARHIGH_LP,SND_M_PAN4Q4_2,SND_M_PAN4Q5_2,SND_M_PAN4C2_2,SND_M_PAN4E6_2,SND_CLIFFSAMB_LP,SND_M_ATH1E5_2,SND_M_PAN4E4_2,SND_M_AQMAGC_Q
PAND04D.WAD|SBK_Pand04D|blk|5|85552|ok|SND_PLATFORMSPIN_LP,SND_CLIFFS2AMB_LP,SND_PLATFORM_STOP,SND_PLATFORM_START,SND_PLATFORM2SPIN_LP,SND_PLATFORM2_STOP,SND_PLATFORM2_START,SND_CAVERN2AMB_LP,SND_M_PAN4C1_2,SND_M_PAN4E2_2,SND_M_PAN4E4_2,SND_M_PAN4Q2_2,SND_M_ATH1E5_2
PAND04E.WAD|SBK_Pand04E|blk|21|203076|ok|SND_CAVERN2AMB_LP,SND_PUZZLEROOMAMB_LP,SND_CLIFFS2AMB_LP,SND_BIRDS_LOOP,SND_WINDWHISTLES_LOOP,SND_ROPEZIP_LP,SND_WATERFALL_LOOP,SND_DISTWATERFALL_LOOP,SND_BRIDGE1_LP,SND_BRIDGE2_LP,SND_BRIDGE3_LP,SND_BRIDGE4_LP,SND_BRIDGE1_LOCK,SND_BRIDGE2_LOCK,SND_BRIDGE3_LOCK,SND_BRIDGE4_LOCK,SND_M_PAN4C1_2,SND_M_PAN4C4_2,SND_M_PAN4E4_2,SND_M_PAN4E5_2,SND_M_PAN4Q2_2,SND_M_PAN4Q5_2,SND_M_PAN4E2_2,SND_DISCSPIN_LP,SND_DISC_LOCK,SND_M_PAN4C8_2,SND_M_PAN4QJ_2,SND_M_PAN4E6_2,SND_M_PAN4QG_2,SND_M_PAN4QH_2,SND_M_PAN4QI_2,SND_M_PAN4C6_2,SND_M_PAN4QK_2,SND_M_AQMAGC_Q,SND_M_ATH1E5_2
PAND04EE.WAD|SBK_Pand04EE|blk|18|200636|ok|SND_CAVERN1AMB_LP,SND_PUZZLEROOMAMB_LP,SND_DOORSLIDE_LOOP,SND_STONEBARS_LP,SND_BIGBLOCK_LP,SND_MEDBLOCK_LP,SND_SMALLBLOCK_LP,SND_BLOCK_CLUNK,SND_NECKLACE,SND_FLAMEJETS,SND_ALTERLOWER_LP,SND_PUZZLEDOOR_LP,SND_STONESLOP,SND_M_PAN4C1_2,SND_M_PAN4C4_2,SND_M_PAN4E5_2,SND_M_PAN4Q0_2,SND_M_PAN4Q4_2,SND_M_PAN4Q7_2,SND_M_PAN4Q8_2,SND_DISCSPIN_LP,SND_DISC_LOCK,SND_LADDER_LOWER,SND_BLOCK_INSERT,SND_M_AQMAGC_Q
PAND04F.WAD|SBK_Pand04F|blk|12|154272|ok|SND_BLADESBLOCKSAMB_LP,SND_CLIFFS2AMB_LP,SND_ELEVATOR_LP,SND_ELEVATOR_STOP,SND_GATECLOSE,SND_WINDWHISTLES_LOOP,SND_FABRICFLAP_LP,SND_M_PAN4E4_2,SND_M_PAN4E6_2
PAND04G.WAD|SBK_Pand04G|blk|17|201556|ok|SND_WINDWHISTLEAMB_LP,SND_BLADESBLOCKSAMB_LP,SND_ARCHROOMAMB_LP,SND_OUTSIDEAMB_LP,SND_STONEPEDESTAL_LP,SND_ROPEBLADE_LP,SND_CRANETURN_LP,SND_LIFTGATE_GRAB,SND_LIFTGATE_LP,SND_LIFTGATE_STOP,SND_BLOCKLOWER_LP,SND_BLOCKRAISE_LP,SND_STATUESLIDE_LOOP,SND_STATUEHITGROUND,SND_DOOR1_LP,SND_DOOR1_STOP,SND_DOOR2_LP,SND_DOOR2_STOP,SND_DOOR3_LP,SND_DOOR3_STOP,SND_M_PAN4C7_2,SND_M_PAN4E6_2,SND_M_PAN4E7_2,SND_M_PAN4E8_2,SND_M_PAN4QA_2,SND_M_PAN4QB_2,SND_M_PAN4QC_2,SND_TIMER_LP,SND_TIMER_STOP,SND_M_PAN4QD_2,SND_SKULLHIT
PAND04H.WAD|SBK_Pand04H|blk|10|66904|ok|SND_WINDWHISTLEAMB_LP,SND_FABRICFLAP_LP,SND_M_PAN4E8_2,SND_INSIDEAMB_LP,SND_ARCHROOMAMB_LP,SND_INSERT_SKULL,SND_HEADRIPOFF,SND_HEADRIPOFF_LP,SND_FLIESBUZZ_LP,SND_M_PAN4E7_2
PAND04IB.WAD|SBK_Pand04IB|blk|16|145564|ok|SND_WINDWHISTLEAMB_LP,SND_INSIDEAMB_LP,SND_CAVERN2AMB_LP,SND_M_PAN4E8_2,SND_BARREL_LP,SND_PLATES_LP,SND_BUMPS_LP,SND_M_PAN4CZ_2
PAND04J.WAD|SBK_Pand04J|blk|21|199052|ok|SND_OUTDOORAMB_LP,SND_INSIDEAMB_LP,SND_CAVERN2AMB_LP,SND_STORMAMB_LP,SND_BARREL_LP,SND_PLATES_LP,SND_BUMPS_LP,SND_M_PAN4C7_2,SND_M_PAN4QB_2,SND_M_PAN4QC_2,SND_M_PAN5Q5_2,SND_M_PAN5E1_2,SND_M_PAN4E8_2,SND_FLAME_WARN1,SND_FLAME_WARN2,SND_FLAMEBLAST,SND_DOOROPEN,SND_DOORCLOSE,SND_M_PAN4CZ_2
PAND05A.WAD|SBK_Pand05A|blk|28|224184|ok|SND_CAVERN2AMB_LP,SND_STORMAMB_LP,SND_FABRICFLAP_LP,SND_BOX_OPEN,SND_ELEVATORDOWN_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_BOXPUSH_LP,SND_LEVERPULL_LP,SND_LEVERPULL_DONE,SND_M_PAN5E1_2,SND_M_PAN5Q1_2,SND_M_PAN5Q2_2,SND_M_PAN5Q3_2,SND_PBOX_LP,SND_M_PAN5Q5_2,SND_BOXHIT,SND_DOORKICK
PAND05B.WAD|SBK_Pand05B|blk|19|191056|ok|SND_SANDSTORM_LOOP,SND_ELEVATORDOWN_LP,SND_ELEVATORUP_LP,SND_ELEVATOR_STOP,SND_SS_P05HL02,SND_SS_P05HL02A,SND_STONEDOOR_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_BOXPUSH_LP,SND_M_PAN5E1_2,SND_M_PAN5Q1_2,SND_M_PAN5Q2_2,SND_M_PAN5Q3_2,SND_PBOX_LP
R_A1A.WAD|a1a|vag|5|92484|ok|AREBAT01,AREBAT02,AREBAT06,AREBAT34,AREBAT36
R_A1A.WAD|SBK_A1A_Ares1A|blk|6|98856|ok|SND_VOATTK_BUILDSHORT,SND_VOATTK_BUILDMED,SND_VOATTK_LONG,SND_ANGRYGROWL,SND_BAR2HITAXE_START,SND_BAR2HITAXE_END,SND_AXEUPPERCUT_START,SND_AXEUPPERCUT_END,SND_HAMMERATK_START,SND_HAMMERATK_END,SND_VOATTK_BUILDSHORT_A,SND_VOATTK_BUILDMED_A
R_A1B.WAD|a1b|vag|3|86556|ok|AREBAT03,AREBAT04,AREBAT28
R_A1B.WAD|SBK_A1B_Ares1B|blk|6|88736|ok|SND_VOATTK_BUILDLONG,SND_LABOREDBREATHING,SND_FIREBALLSPELLSTART,SND_FIREBALL,SND_MULTIBLADES_START,SND_MULTIBLADES_ATK,SND_ARESTELEPORT,SND_FIREBALL_BLOCK,SND_VOATTK_BUILDLONG_A,SND_HAMMERSWING_FAST,SND_HAMMERSWING_MED,SND_HAMMERSWING_SLOW,SND_VOSTRUGGLE_LP
R_A1C.WAD|a1c|vag|9|61220|ok|AREBAT07,AREBAT14,AREBAT15,AREBAT18,AREHIT08,AREHIT09,AREHIT12,AREHIT13,AREHIT19
R_A1C.WAD|SBK_A1C_Ares1C|blk|5|108440|ok|SND_VOATTK_SHORT,SND_VOATTK_MEDIUM,SND_HAMMER_WAVE,SND_HAMMERSHOVE_A,SND_HAMMERSHOVE_B,SND_HAMMERSHOVE_C,SND_VORTEXWEATHER,SND_VOGETHIT,SND_VOGETHIT_A,SND_VOATTK_SHORT_A,SND_VOATTK_MEDIUM_A
R_A2A.WAD|a2a|vag|5|92484|ok|AREBAT01,AREBAT02,AREBAT06,AREBAT34,AREBAT36
R_A2A.WAD|SBK_A2A_Ares2A|blk|5|101848|ok|SND_VOATTK_BUILDSHORT,SND_VOATTK_BUILDMED,SND_VOATTK_LONG,SND_ANGRYGROWL,SND_BAR2HITAXE_START,SND_BAR2HITAXE_END,SND_AXEUPPERCUT_START,SND_AXEUPPERCUT_END,SND_VOATTK_BUILDSHORT_A,SND_VOATTK_BUILDMED_A,SND_VOATTK_LONG_A,SND_SWORDSCRAPE_LP
R_A2B.WAD|a2b|vag|3|86556|ok|AREBAT03,AREBAT04,AREBAT28
R_A2B.WAD|SBK_A2B_Ares2B|blk|6|108776|ok|SND_VOATTK_BUILDLONG,SND_LABOREDBREATHING,SND_FIREBALLSPELLSTART,SND_FIREBALL,SND_MULTIBLADES_START,SND_MULTIBLADES_ATK,SND_ARESTELEPORT,SND_FIREBALL_BLOCK,SND_VOATTK_BUILDLONG_A,SND_HAMMERSWING_FAST,SND_HAMMERSWING_MED,SND_HAMMERSWING_SLOW,SND_VOSTRUGGLE_LP,SND_VORTEXWEATHER
R_A2C.WAD|a2c|vag|9|61220|ok|AREBAT07,AREBAT14,AREBAT15,AREBAT18,AREHIT08,AREHIT09,AREHIT12,AREHIT13,AREHIT19
R_A2C.WAD|SBK_A2C_Ares2C|blk|5|101976|ok|SND_VOATTK_SHORT,SND_VOATTK_MEDIUM,SND_MAGICPILLARS_A,SND_MAGICPILLARS_B,SND_VOGETHIT,SND_VOGETHIT_A,SND_SWARM_SHOT,SND_SWARM_LP,SND_SWARM_HIT,SND_SWORDPROJ_SHOT,SND_SWORDPROJ_LP,SND_SWORDPROJ_HIT,SND_VOATTK_SHORT_A,SND_VOATTK_MEDIUM_A,SND_SWARMBUILD_LP
R_AB2.WAD|ab2|vag|3|49580|ok|BMIATKL1,BMIATKL2,BMIATKL3
R_AB2.WAD|SBK_BM2_MinoBoss2|blk|7|110848|ok|SND_MB_VOATKLONG,SND_MB_VOATKLONG_A,SND_MB_VENTSHOT,SND_MB_VENT1_LP,SND_MB_VENT2_LP,SND_MB_VENT3_LP,SND_MB_VENT4_LP,SND_MB_FIREBREATH,SND_MB_FIREPLUME,SND_MB_LOGHIT,SND_MB_FIREWAV,SND_MB_FIREWAV2
R_AB3.WAD|ab3|vag|0|8|kosong|
R_AB3.WAD|SBK_BM3_MinoBoss3|blk|7|91600|ok|SND_MB_ARMORDAMAGE,SND_MB_PUNCHATTACK,SND_MB_GRABATTACK,SND_MB_HORNSATTACK,SND_MB_AXESWING_LOW,SND_MB_AXESWING_HIGH
R_AB4.WAD|ab4|vag|0|8|kosong|
R_AB4.WAD|SBK_BM4_MinoBoss4|blk|9|94752|ok|SND_MB_CLAPATTACK,SND_MB_ARMORNOISE,SND_MB_CLAWSCRAPE,SND_MB_GROUNDSLAM,SND_MB_GROUNDRIP
R_AEV.WAD|aev|vag|13|72244|ok|EVI_ATK1,EVI_ATK2,EVI_ATK3,EVI_ATK4,EVI_ATK5,EVI_ATK6,EVI_DIE1,EVI_DIE2,EVI_HIT1,EVI_HIT2,EVI_HIT3,EVI_HIT4,EVI_HIT5
R_AEV.WAD|SBK_AEV_EvilKratos|blk|0|1464|ref|SND_AEV_VOATTACK,SND_AEV_VOATTACK_A,SND_AEV_VOGETHIT,SND_AEV_VOGETHIT_A,SND_AEV_VODIE
R_AH2.WAD|ah2|vag|12|100072|ok|BHB_ATT1,BHB_ATT2,BHB_ATT3,BHB_ATT4,BHB_HIT1,BHB_HIT2,BHB_HIT3,BHB_HIT5,BHB_IDL1,BHB_IDL3,BHB_IDL5,BHB_IDL6
R_AH2.WAD|SBK_AH2_HydraBabyV2|blk|7|111480|ok|SND_BHB_GROWL,SND_BHB_WHOOSHHIGH,SND_BHB_WHOOSHMID,SND_BHB_WHOOSHLOW,SND_BHB_BREATH,SND_BHB_BREATHSCREAM_LP,SND_BHB_EMERGE_SCREAM,SND_BHB_TAUNT_SCREAM,SND_BHB_VOATTACK,SND_BHB_VOGETHIT,SND_BHB_FALL_SCREAM,SND_BHB_VOPINNED1,SND_BHB_HEAL_LP,SND_BHB_VOPINNED2,SND_BHB_PINNED_SCREAM
R_AH3.WAD|ah3|vag|9|98308|ok|BHA_ATK1,BHA_ATK2,BHA_ATK3,BHA_ATK4,BHA_HIT1,BHA_HIT2,BHA_HIT3,BHA_HIT4,BHA_KIL1
R_AH3.WAD|SBK_AH3_HydraBoss2|blk|3|89592|ok|SND_BOSSSHORTSCREAM,SND_BHA_KILLSCREAM_1,SND_BHA_KILLSCREAM_2
R_AHA.WAD|aha|vag|9|98308|ok|BHA_ATK1,BHA_ATK2,BHA_ATK3,BHA_ATK4,BHA_HIT1,BHA_HIT2,BHA_HIT3,BHA_HIT4,BHA_KIL1
R_AHA.WAD|SBK_HydraBoss|blk|7|107492|ok|SND_HYDBOSS_SCREAM,SND_HYD_WHOOSHHIGH,SND_HYD_WHOOSHMID,SND_HYD_WHOOSHLOW,SND_EYEGLOW,SND_HYDBOSS_SNORT,SND_HYDBOSS_TAUNT,SND_AHA_BREATH,SND_AHA_VOATTACK,SND_AHA_VOGETHIT,SND_AHA_VOKILLFAIL,SND_AHA_STUNBREATH
R_AHB.WAD|ahb|vag|11|97820|ok|BHB_ATT1,BHB_ATT2,BHB_ATT3,BHB_ATT4,BHB_ATT5,BHB_HIT1,BHB_HIT2,BHB_HIT3,BHB_HIT4,BHB_HIT5,BHB_RET
R_AHB.WAD|SBK_HydraBabyV|blk|7|111452|ok|SND_BHB_GROWL,SND_BHB_WHOOSHHIGH,SND_BHB_WHOOSHMID,SND_BHB_WHOOSHLOW,SND_BHB_STRUGGLE_LP,SND_BHB_BREATH,SND_BHB_BREATHSCREAM_LP,SND_BHB_EMERGE_SCREAM,SND_BHB_TAUNT_SCREAM,SND_BHB_VOATTACK,SND_BHB_VOGETHIT,SND_BHB_VORETREAT,SND_BHB_MGWIN_SCREAM,SND_HL_A01HL07,SND_BREATH,SND_GROWL,SND_EMERGE_SCREAM,SND_VOATTACK
R_AHH.WAD|ahh|vag|9|99092|ok|HH_ATK1,HH_ATK2,HH_ATK3,HH_ATK4,HH_ATK5,HH_HIT1,HH_HIT2,HH_HIT3,HH_HIT4
R_AHH.WAD|SBK_HydraBabyH|blk|9|113216|ok|SND_HYDBABH_BURSTIN,SND_HYDBABH_GROWL,SND_HYDBABH_WHOOSHTHICK,SND_HYDBABH_WHOOSHFAST,SND_HYDBABH_VOGETHIT,SND_HYDBABH_BREATH,SND_HYDBABH_DAZEBREATH,SND_HYDBABH_TAUNT,SND_EYEGLOW,SND_HYDBAB_BARK,SND_HYDBABH_VODAZED,SND_HYDBAB_GILLFLAP,SND_HL_HYDRA1,SND_HL_HYDRA2,SND_HYDBABH_GROWL_A,SND_HYDBARK_NODUCK
R_AM3.WAD|me3|vag|11|100316|ok|MEDATK02,MEDATK04,MEDDIE01,MEDDIE02,MEDHIT01,MEDHIT02,MEDHIT03,MEDHIT04,MEDHIT05,MEDHITB1,MEDULAFF
R_AM3.WAD|SBK_ME3_Medusa3|blk|13|114048|ok|SND_MEDUSA_IDLE,SND_MEDUSA_MOVESLOW,SND_MEDUSA_MOVEREG,SND_MEDUSA_MOVEFAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_MEDUSA_VOATTACK,SND_MEDUSA_VOATTACK_A,SND_MEDUSA_VOGETHIT,SND_MEDUSA_VOGETHIT_A,SND_MEDUSA_VOGETHITB_A,SND_MEDUSA_VODIE,SND_MEDUSA_BODYFAL_SLAM,SND_MEDUSA_BODYFAL_HEV,SND_MEDUSA_BODYFAL_MED,SND_MEDUSA_BODYFAL_LIMB,SND_MEDUSA_BODYFAL_HEAD,SND_MEDUSA_EVADE,SND_MEDUSA_LAUGH,SND_MED_SNAKESTRIKE,SND_MED_CLAWSTRIKE,SND_MED_TAILSPIN,SND_MED_HEADRIPOFF,SND_HEADRIP,SND_MEDUSA_NAVCYCLE,SND_MEDUSA_NAVSOUND,SND_MEDUSA_MOVEPHASE
R_AMI.WAD|ami|vag|11|86652|ok|BMI_HIT1,BMI_HIT2,BMI_HIT3,BMI_HIT4,BMI_HIT5,BMI_HIT6,BMIATKS1,BMIATKS2,BMIATKS3,BMIATKS4,BMIATKS5
R_AMI.WAD|SBK_BMI_MinoBoss|blk|9|110680|ok|SND_MB_VOGETHIT,SND_MB_VOGETHIT_A,SND_MB_VOATKSHORT,SND_MB_VOATKSHORT_A,SND_MB_VOIDLE_NORMAL,SND_MB_VOIDLE_STUN,SND_MB_ARMORCRACK,SND_MB_VOVICTORY,SND_BMIBEHINDDOOR_LP
R_CEA.WAD|cea|vag|10|98736|ok|CER_TCA1,CER_TCA2,CER_TCA3,CER_TCA4,CER_TCAL,CER_DIE1,CER_TCH1,CER_TCH2,CER_TCH3,CER_TCH4
R_CEA.WAD|SBK_CEA_Cerebus|blk|14|107944|ok|SND_CERBUS_STEPLIGHT,SND_CERBUS_STEPHEAVY,SND_CERBUS_STEPLAND,SND_CERBUS_IDLESNARL,SND_PRETAUNTGROWL,SND_CERBUS_FIREBALL,SND_CERBUS_FIREBALL_LP,SND_CERBUS_VOATTACK,SND_CERBUS_VOATTACK_A,SND_CERBUS_VOATTACK_L,SND_CERBUS_VOGETHIT,SND_CERBUS_VOGETHIT_A,SND_CERBUS_VODIE,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CEA_FIREBALL_EXPLO,SND_CEA_BODYFALL_NORM,SND_CEA_BODYFALL_SLAM,SND_CEA_BODYFALL_LIGHT,SND_CERBUS_VOMIT,SND_CER_FIREBALL_BLOCK,SND_CEA_LEAPATKVO,SND_CERBUS_VOFIREATTK
R_CEP.WAD|cep|vag|10|98448|ok|CEP_CATK,CEP_LATK,CEP_TCA1,CEP_TCA3,CEP_TCD1,CEP_TCH1,CEP_TCH2,CEP_TCH3,CEP_TCH4,CEP_TRAN
R_CEP.WAD|SBK_CEP_CerebPup|blk|13|112408|ok|SND_CERPUP_STEPLIGHT,SND_CERPUP_STEPHEAVY,SND_CERPUP_STEPLAND,SND_SNARL,SND_BREATH,SND_TRANSFORM_A,SND_TRANSFORM_B,SND_FLIPATTK,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CERPUP_VOATTACK,SND_CERPUP_VOATTACK_A,SND_CERPUP_VOGETHIT,SND_CERPUP_VOGETHIT_A,SND_CERPUP_VODIE,SND_CERPUP_BARK,SND_CERPUP_HEADSTOMP,SND_CERPUP_VO_CATTACK,SND_CERPUP_VO_CATTACK_A,SND_CERPUP_VO_LATTACK,SND_CERPUP_VO_LATTACK_A
R_CNM.WAD|cnm|vag|11|99404|ok|CNMDIEN,CNMDIEX,CNMHIT1,CNMHIT2,CNMHIT3,CNMYELL1,CNMYELL2,CNMYELL3,CNMYELL4,CNMYELL5,CNMYELL7
R_CNM.WAD|SBK_CNM_Centaur1|blk|21|115112|ok|SND_CENT_STEPLIGHT,SND_CENT_STEPHEAVY,SND_CENT_STEPLAND,SND_CENT_BODYFALL_HEAVY,SND_CENT_BODYFALL_MED,SND_CENT_BODYFALL_HEAD,SND_CENT_BODYFALL_LIMB,SND_CNM_BOWDRAW_FAST,SND_CNM_BOWDRAW_SLOW,SND_CNM_BOW_FIRE,SND_CNM_ARR_FLIGHT,SND_CNM_ARR_BLOCK,SND_CNM_ARR_HITFLESH,SND_CNM_ARR_HITWATER,SND_CNM_ARR_HITDIRT,SND_CNM_ARR_HITSTONE,SND_CNM_ARR_HITWOOD,SND_CNM_ARR_HITGEN,SND_CNM_BOW_FIRE_M,SND_CNM_ARR_FLIGHT_M,SND_CNM_ARR_BLOCK_M,SND_CNM_ARR_HITFLESH_M,SND_CNM_ARR_HITWATER_M,SND_CNM_ARR_HITDIRT_M,SND_CNM_ARR_HITSTONE_M,SND_CNM_ARR_HITWOOD_M,SND_CNM_ARR_HITGEN_M,SND_BOWBLOCKSWORD,SND_CNM_VOATTACK,SND_CNM_VOGETHIT,SND_CNM_TAUNTLAUGH,SND_CNM_VODIE,SND_CNM_VOATTACK_A,SND_CNM_VOGETHIT_A,SND_CNM_VODIE_EXT,SND_CNM_VOATTACKLONG_A,SND_CNM_SLICELEGSOFF,SND_SHOCKWAVE,SND_CENT_BODYFALL_SLAM,SND_CNM_DRAW_LP
R_CY2.WAD|cy2|vag|11|98844|ok|CY2LNG_A,CY2LUNGE,CY2SNORT,CY2TNT_2,CYCLATK1,CYCLATK2,CYCLDIE2,CYCLHIT1,CYCLHIT2,CYCLHIT3,CYCLHIT4
R_CY2.WAD|SBK_CY2_Cyclops2|blk|16|114656|ok|SND_CYCLOPS_STEPLIGHT,SND_CYCLOPS_STEPWALK,SND_CYCLOPS_STEPRUN,SND_CYCLOPS_IDLELOOP,SND_CYCLOPS_SWIPEW,SND_CYCLOPS_WHOOSH_F1,SND_CYCLOPS_WHOOSH_F2,SND_CYCLOPS_WHOOSH_M1,SND_CYCLOPS_WHOOSH_M2,SND_CYCLOPS_WHOOSH_S,SND_CYCLOPS_HITEYE,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CYCLOPS_BODYFALL,SND_CYCLOPS_VOATTACK,SND_CYCLOPS_VOGETHIT,SND_CYCLOPS_VOGETHITBIG,SND_CYCLOPS_VODIE,SND_CYCLOPS_VOSCREAM,SND_CYCLOPS_NOISE,SND_CYCLOPS_BUCKWHOOSH,SND_CYCLOPS_VOATTACK_A,SND_CYCLOPS_VOGETHIT_A,SND_CYCLOPS_VOGETHITB_A,SND_CYCLOPS_BFALL_KNEE,SND_CYL2_BALLWINDUP,SND_CYL2_BALLSPIN_LP,SND_CYL2_BALLSHOOT,SND_CYL2_BALLIMPACT,SND_CYL2_BALLPULL,SND_CYL2_BALLRELEASE,SND_CY2_BALLRETRACT,SND_CYL2_BALLGRAB,SND_CYL2_VO_SLAMWINDUP,SND_CYL2_VO_SLAM,SND_CYL2_VO_LUNGEWINDUP,SND_CYL2_VO_LUNGE
R_CY3.WAD|cy3|vag|9|69204|ok|CYCLATK1,CYCLATK2,CYCLATK3,CYCLATK4,CYCLDIE1,CYCLHIT1,CYCLHIT2,CYCLHIT3,CYCLHIT4
R_CY3.WAD|SBK_CY3_Cyclops3|blk|14|109176|ok|SND_CYCLOPS_STEPLIGHT,SND_CYCLOPS_STEPWALK,SND_CYCLOPS_STEPRUN,SND_CYCLOPS_IDLELOOP,SND_CYCLOPS_SWIPEW,SND_CYCLOPS_GROUNDP,SND_CYCLOPS_FOOTSMASH,SND_CYCLOPS_WHOOSH_F1,SND_CYCLOPS_WHOOSH_F2,SND_CYCLOPS_WHOOSH_M1,SND_CYCLOPS_WHOOSH_M2,SND_CYCLOPS_WHOOSH_S,SND_CYCLOPS_HITEYE,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CYCLOPS_BODYFALL,SND_CYCLOPS_VOATTACK,SND_CYCLOPS_VOGETHIT,SND_CYCLOPS_VOGETHITBIG,SND_CYCLOPS_VODIE,SND_CYCLOPS_VOSCREAM,SND_CYCLOPS_NOISE,SND_CYCLOPS_BUCKWHOOSH,SND_CYCLOPS_VOATTACK_A,SND_CYCLOPS_VOGETHIT_A,SND_CYCLOPS_VOGETHITB_A,SND_CYCLOPS_BFALL_KNEE,SND_RAMSCREAM,SND_CYCLOPS_STEPSTOMP
R_CYW.WAD|cyw|vag|10|87456|ok|CYCLATK1,CYCLATK2,CYCLATK3,CYCLATK4,CYCLDIE1,CYCLDIE2,CYCLHIT1,CYCLHIT2,CYCLHIT3,CYCLHIT4
R_CYW.WAD|SBK_CYW_Cyclops1|blk|15|113656|ok|SND_CYCLOPS_STEPLIGHT,SND_CYCLOPS_STEPWALK,SND_CYCLOPS_STEPRUN,SND_CYCLOPS_IDLELOOP,SND_CYCLOPS_SWIPEW,SND_CYCLOPS_GROUNDP,SND_CYCLOPS_FOOTSMASH,SND_CYCLOPS_WHOOSH_F1,SND_CYCLOPS_WHOOSH_F2,SND_CYCLOPS_WHOOSH_M1,SND_CYCLOPS_WHOOSH_M2,SND_CYCLOPS_WHOOSH_S,SND_CYCLOPS_HITEYE,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CYCLOPS_BODYFALL,SND_CYCLOPS_VOATTACK,SND_CYCLOPS_VOGETHIT,SND_CYCLOPS_VOGETHITBIG,SND_CYCLOPS_VODIE,SND_CYCLOPS_VOSCREAM,SND_CYCLOPS_NOISE,SND_CYCLOPS_BUCKWHOOSH,SND_CYCLOPS_VOATTACK_A,SND_CYCLOPS_VOGETHIT_A,SND_CYCLOPS_VOGETHITB_A,SND_CYCLOPS_BFALL_KNEE
R_HA2.WAD|ha2|vag|12|95704|ok|HARPATK1,HARPATK2,HARPATK3,HARPATK4,HARPDIE1,HARPDIE2,HARPHIT1,HARPHIT2,HARPHIT3,HARPHIT4,HARPLAF2,HARPTNT1
R_HA2.WAD|SBK_HA2_Harpy2|blk|17|114096|ok|SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_HARP_WHOOSH_S1,SND_HARP_WHOOSH_S2,SND_HARP_WHOOSH_M1,SND_HARP_WHOOSH_M2,SND_HARP_WHOOSH_F1,SND_HARP_WHOOSH_F2,SND_HARP_HITGROUND,SND_HARP_HITWALL,SND_HARP_SLAMGROUND,SND_HARP_WINGTEAR,SND_HARP_GRABHERO,SND_HARP_VOATTACK,SND_HARP_VOATTACK_A,SND_HARP_VOATTACKBIG_A,SND_HARP_VOGETHIT,SND_HARP_VOGETHIT_A,SND_HARP_VODIE,SND_HARP_VOTAUNT_A,SND_HARP_VOLAFF_A,SND_HARP_FIRESLAM,SND_HARP_FIRESLAM_PRE,SND_HARP_FIREATK_LP
R_HAF.WAD|haf|vag|12|95704|ok|HARPATK1,HARPATK2,HARPATK3,HARPATK4,HARPDIE1,HARPDIE2,HARPHIT1,HARPHIT2,HARPHIT3,HARPHIT4,HARPLAF2,HARPTNT1
R_HAF.WAD|SBK_HAF_HarpyF|blk|18|114408|ok|SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_HARP_WHOOSH_S1,SND_HARP_WHOOSH_S2,SND_HARP_WHOOSH_M1,SND_HARP_WHOOSH_M2,SND_HARP_WHOOSH_F1,SND_HARP_WHOOSH_F2,SND_HARP_HITGROUND,SND_HARP_HITWALL,SND_HARP_SLAMGROUND,SND_HARP_WINGTEAR,SND_HARP_GRABHERO,SND_HARP_VOATTACK,SND_HARP_VOATTACK_A,SND_HARP_VOATTACKBIG_A,SND_HARP_VOGETHIT,SND_HARP_VOGETHIT_A,SND_HARP_VODIE,SND_HARP_VOTAUNT_A,SND_HARP_FIRESLAM,SND_HAF_FIRE_LP,SND_HARP_VOLAFF_A,SND_HARP_FIREATK_LP,SND_HARP_FIRESLAM_PRE
R_HAR.WAD|har|vag|12|95704|ok|HARPATK1,HARPATK2,HARPATK3,HARPATK4,HARPDIE1,HARPDIE2,HARPHIT1,HARPHIT2,HARPHIT3,HARPHIT4,HARPLAF2,HARPTNT1
R_HAR.WAD|SBK_HAR_Harpy1|blk|20|113508|ok|SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_HARP_WHOOSH_S1,SND_HARP_WHOOSH_S2,SND_HARP_WHOOSH_M1,SND_HARP_WHOOSH_M2,SND_HARP_WHOOSH_F1,SND_HARP_WHOOSH_F2,SND_HARP_HITGROUND,SND_HARP_HITWALL,SND_HARP_SLAMGROUND,SND_HARP_WINGTEAR,SND_HARP_GRABHERO,SND_HARP_VOATTACK,SND_HARP_VOATTACK_A,SND_HARP_VOATTACKBIG_A,SND_HARP_VOGETHIT,SND_HARP_VOGETHIT_A,SND_HARP_VODIE,SND_HARP_VOTAUNT_A,SND_HARP_VOLAFF_A,SND_HL_A01HL04F,SND_HL_A01HL05F
R_ME2.WAD|me2|vag|11|100316|ok|MEDATK02,MEDATK04,MEDDIE01,MEDDIE02,MEDHIT01,MEDHIT02,MEDHIT03,MEDHIT04,MEDHIT05,MEDHITB1,MEDULAFF
R_ME2.WAD|SBK_ME2_Medusa2|blk|13|114048|ok|SND_MEDUSA_IDLE,SND_MEDUSA_MOVESLOW,SND_MEDUSA_MOVEREG,SND_MEDUSA_MOVEFAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_MEDUSA_VOATTACK,SND_MEDUSA_VOATTACK_A,SND_MEDUSA_VOGETHIT,SND_MEDUSA_VOGETHIT_A,SND_MEDUSA_VOGETHITB_A,SND_MEDUSA_VODIE,SND_MEDUSA_BODYFAL_SLAM,SND_MEDUSA_BODYFAL_HEV,SND_MEDUSA_BODYFAL_MED,SND_MEDUSA_BODYFAL_LIMB,SND_MEDUSA_BODYFAL_HEAD,SND_MEDUSA_EVADE,SND_MEDUSA_LAUGH,SND_MED_SNAKESTRIKE,SND_MED_CLAWSTRIKE,SND_MED_TAILSPIN,SND_MED_HEADRIPOFF,SND_HEADRIP,SND_MEDUSA_NAVCYCLE,SND_MEDUSA_NAVSOUND,SND_MEDUSA_MOVEPHASE
R_MEW.WAD|mew|vag|11|100316|ok|MEDATK02,MEDATK04,MEDDIE01,MEDDIE02,MEDHIT01,MEDHIT02,MEDHIT03,MEDHIT04,MEDHIT05,MEDHITB1,MEDULAFF
R_MEW.WAD|SBK_MEW_Medusa1|blk|13|114048|ok|SND_MEDUSA_IDLE,SND_MEDUSA_MOVESLOW,SND_MEDUSA_MOVEREG,SND_MEDUSA_MOVEFAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_MEDUSA_VOATTACK,SND_MEDUSA_VOATTACK_A,SND_MEDUSA_VOGETHIT,SND_MEDUSA_VOGETHIT_A,SND_MEDUSA_VOGETHITB_A,SND_MEDUSA_VODIE,SND_MEDUSA_BODYFAL_SLAM,SND_MEDUSA_BODYFAL_HEV,SND_MEDUSA_BODYFAL_MED,SND_MEDUSA_BODYFAL_LIMB,SND_MEDUSA_BODYFAL_HEAD,SND_MEDUSA_EVADE,SND_MEDUSA_LAUGH,SND_MED_SNAKESTRIKE,SND_MED_CLAWSTRIKE,SND_MED_TAILSPIN,SND_MED_HEADRIPOFF,SND_HEADRIP,SND_MEDUSA_NAVCYCLE,SND_MEDUSA_NAVSOUND,SND_MEDUSA_MOVEPHASE
R_MI2.WAD|mi2|vag|10|100448|ok|MINATK_2,MINATK_3,MINATK_4,MINDIE_1,MINDIEB1,MINHIT_1,MINHIT_2,MINHIT_3,MINHIT_4,MINHITB1
R_MI2.WAD|SBK_MI2_Mntaur2|blk|20|114848|ok|SND_MINO_STEPLIGHT,SND_MINO_STEPHEAVY,SND_MINO_STEPLAND,SND_MINO_BODYFALL_HEAVY,SND_MINO_BODYFALL_MED,SND_MINO_BODYFALL_LIMB,SND_MINO_SNORT,SND_MINO_VOATTACK,SND_MINO_VOATTACK_A,SND_MINO_VOGETHIT,SND_MINO_VOGETHIT_A,SND_MINO_VOGETHITBIG,SND_MINO_VOGETHITB_A,SND_MINO_VOTAUNT1,SND_MINO_VOTAUNT2,SND_MINO_VOTAUNT3,SND_MINO_VODIE,SND_MINO_VODIEBIG,SND_MINO_AXEDROP,SND_AXESWING_NORMAL,SND_AXESWING_SLOW,SND_AXESWING_MEDIUM,SND_AXESWING_FAST,SND_HAMMERHITGROUND,SND_MINO_AGRO_LP,SND_MINO_GROWL,SND_MINO_STRUGGLE_LP_A,SND_MINO_STRUGGLE_LP_B,SND_MIN_NAVSOUND_CYCLE,SND_MIN_HEADCUT_VO,SND_MINO_VOBRUTALDIE,SND_MINO_VODIEBIG2,SND_SHOCKWAVE,SND_HAMHITGROUND_SOFT
R_MI4.WAD|mi4|vag|10|100448|ok|MINATK_2,MINATK_3,MINATK_4,MINDIE_1,MINDIEB1,MINHIT_1,MINHIT_2,MINHIT_3,MINHIT_4,MINHITB1
R_MI4.WAD|SBK_MI4_Mntaur4|blk|21|116096|ok|SND_MINO_STEPLIGHT,SND_MINO_STEPHEAVY,SND_MINO_STEPLAND,SND_MINO_BODYFALL_HEAVY,SND_MINO_BODYFALL_MED,SND_MINO_BODYFALL_LIMB,SND_MINO_SNORT,SND_MINO_VOATTACK,SND_MINO_VOATTACK_A,SND_MINO_VOGETHIT,SND_MINO_VOGETHIT_A,SND_MINO_VOGETHITBIG,SND_MINO_VOGETHITB_A,SND_MINO_VOTAUNT1,SND_MINO_VOTAUNT3,SND_MINO_VODIE,SND_MINO_VODIEBIG,SND_MINO_AXEDROP,SND_AXESWING_NORMAL,SND_AXESWING_SLOW,SND_AXESWING_MEDIUM,SND_AXESWING_FAST,SND_AXEHITGROUND,SND_AXEPULLOUTGROUND,SND_MINO_AGRO_LP,SND_MINO_GROWL,SND_MINO_STRUGGLE_LP_A,SND_MINO_STRUGGLE_LP_B,SND_MIN_NAVSOUND_CYCLE,SND_MIN_HEADCUT_VO,SND_MINO_VOBRUTALDIE,SND_MINO_VODIEBIG2,SND_MINO_HORNGOUGE,SND_MINO_FOOTSCRAPE,SND_MINO_CHARGEVO
R_MI5.WAD|mi5|vag|10|100448|ok|MINATK_2,MINATK_3,MINATK_4,MINDIE_1,MINDIEB1,MINHIT_1,MINHIT_2,MINHIT_3,MINHIT_4,MINHITB1
R_MI5.WAD|SBK_MI5_Mntaur5|blk|20|116036|ok|SND_MINO_STEPLIGHT,SND_MINO_STEPHEAVY,SND_MINO_STEPLAND,SND_MINO_BODYFALL_HEAVY,SND_MINO_BODYFALL_MED,SND_MINO_BODYFALL_LIMB,SND_MINO_SNORT,SND_MINO_VOATTACK,SND_MINO_VOATTACK_A,SND_MINO_VOGETHIT,SND_MINO_VOGETHIT_A,SND_MINO_VOGETHITBIG,SND_MINO_VOGETHITB_A,SND_MINO_VOTAUNT1,SND_MINO_VOTAUNT2,SND_MINO_VOTAUNT3,SND_MINO_VODIE,SND_MINO_VODIEBIG,SND_MINO_AXEDROP,SND_AXESWING_NORMAL,SND_AXESWING_SLOW,SND_AXESWING_MEDIUM,SND_AXESWING_FAST,SND_HAMMERHITGROUND,SND_MINO_AGRO_LP,SND_MINO_GROWL,SND_MINO_STRUGGLE_LP_A,SND_MINO_STRUGGLE_LP_B,SND_MIN_NAVSOUND_CYCLE,SND_MIN_HEADCUT_VO,SND_MINO_VOBRUTALDIE,SND_MINO_VODIEBIG2,SND_HAMHITGROUND_SOFT,SND_SHOCKWAVE
R_MIF.WAD|SBK_MI4_Mntaur4|blk|21|116096|ok|SND_MINO_STEPLIGHT,SND_MINO_STEPHEAVY,SND_MINO_STEPLAND,SND_MINO_BODYFALL_HEAVY,SND_MINO_BODYFALL_MED,SND_MINO_BODYFALL_LIMB,SND_MINO_SNORT,SND_MINO_VOATTACK,SND_MINO_VOATTACK_A,SND_MINO_VOGETHIT,SND_MINO_VOGETHIT_A,SND_MINO_VOGETHITBIG,SND_MINO_VOGETHITB_A,SND_MINO_VOTAUNT1,SND_MINO_VOTAUNT3,SND_MINO_VODIE,SND_MINO_VODIEBIG,SND_MINO_AXEDROP,SND_AXESWING_NORMAL,SND_AXESWING_SLOW,SND_AXESWING_MEDIUM,SND_AXESWING_FAST,SND_AXEHITGROUND,SND_AXEPULLOUTGROUND,SND_MINO_AGRO_LP,SND_MINO_GROWL,SND_MINO_STRUGGLE_LP_A,SND_MINO_STRUGGLE_LP_B,SND_MIN_NAVSOUND_CYCLE,SND_MIN_HEADCUT_VO,SND_MINO_VOBRUTALDIE,SND_MINO_VODIEBIG2,SND_MINO_HORNGOUGE,SND_MINO_FOOTSCRAPE,SND_MINO_CHARGEVO
R_MIN.WAD|min|vag|10|100448|ok|MINATK_2,MINATK_3,MINATK_4,MINDIE_1,MINDIEB1,MINHIT_1,MINHIT_2,MINHIT_3,MINHIT_4,MINHITB1
R_MIN.WAD|SBK_MIN_Mntaur1|blk|22|115568|ok|SND_MINO_STEPLIGHT,SND_MINO_STEPHEAVY,SND_MINO_STEPLAND,SND_MINO_BODYFALL_HEAVY,SND_MINO_BODYFALL_MED,SND_MINO_BODYFALL_LIMB,SND_MINO_SNORT,SND_MINO_VOATTACK,SND_MINO_VOATTACK_A,SND_MINO_VOGETHIT,SND_MINO_VOGETHIT_A,SND_MINO_VOGETHITBIG,SND_MINO_VOGETHITB_A,SND_MINO_VOTAUNT1,SND_MINO_VOTAUNT3,SND_MINO_VODIE,SND_MINO_VODIEBIG,SND_MINO_AXEDROP,SND_AXESWING_NORMAL,SND_AXESWING_SLOW,SND_AXESWING_MEDIUM,SND_AXESWING_FAST,SND_AXEHITGROUND,SND_AXEPULLOUTGROUND,SND_MINO_AGRO_LP,SND_MINO_GROWL,SND_MINO_STRUGGLE_LP_A,SND_MINO_STRUGGLE_LP_B,SND_MIN_NAVSOUND_CYCLE,SND_MIN_HEADCUT_VO,SND_MINO_VOBRUTALDIE,SND_MINO_VODIEBIG2
R_NYA.WAD|SBK_NYA_Nyad1|blk|5|109232|ok|SND_NYAD_KISS_A,SND_NYAD_KISS_B,SND_NYA_SWIMSOUND
R_PERM.WAD|GENERAL|blk|137|1159844|ok|SND_FOOTSTEP_DIRT,SND_FOOTSTEP_DIRTSTEP,SND_FOOTSTEP_DIRTWALK,SND_FOOTSTEP_DIRTRUN,SND_FOOTSTEP_DIRTLAND,SND_FOOTSTEP_PLANK,SND_FOOTSTEP_PLANKSTEP,SND_FOOTSTEP_PLANKWALK,SND_FOOTSTEP_PLANKRUN,SND_FOOTSTEP_PLANKLAND,SND_FOOTSTEP_STONE,SND_FOOTSTEP_STONESTEP,SND_FOOTSTEP_STONEWALK,SND_FOOTSTEP_STONERUN,SND_FOOTSTEP_STONELAND,SND_CLIFFCLIMB_GRAB,SND_CLIFFCLIMB_STEP,SND_CLIFFJUMP_LAND,SND_FOOTSTEP_BEAM,SND_FOOTSTEP_BEAMSTEP,SND_FOOTSTEP_BEAMWALK,SND_FOOTSTEP_BEAMRUN,SND_FOOTSTEP_BEAMLAND,SND_FOOTSTEP_WATER,SND_FOOTSTEP_WATERSTEP,SND_FOOTSTEP_WATERWALK,SND_FOOTSTEP_WATERRUN,SND_FOOTSTEP_WATERLAND,SND_FOOTSTEP_PUDDLE,SND_FOOTSTEP_PUDDLESTEP,SND_FOOTSTEP_PUDDLEWALK,SND_FOOTSTEP_PUDDLERUN,SND_FOOTSTEP_PUDDLELAND,SND_FOOTSTEP_VINEWALL,SND_VINEWALL_CATCH,SND_VINEWALL_GRAB,SND_VINEWALL_STEP,SND_VINEWALL_LAND,SND_FOOTSTEP_ROPEWALL,SND_ROPEWALL_CATCH,SND_ROPEWALL_GRAB,SND_ROPEWALL_STEP,SND_ROPEWALL_LAND,SND_FOOTSTEP_LADDER,SND_HANDGRAB_LADDER,SND_LADDERSLIDE_LP,SND_HANDGRAB_ROPE,SND_SLIDEROPE_LP,SND_ROPE_SWINGSHOT,SND_KNEEDEEPWATER,SND_INTOWATER_SPLASH,SND_JUMPOUTWATER,SND_SWIMSPLASH,SND_SWIM_STROKE,SND_SWIM_UW_STROKE,SND_STATUERAISE_SPLASH,SND_WHOOSHMID_SLOW,SND_WHOOSHMID_MEDIUM,SND_WHOOSHMID_FAST,SND_WHOOSHLOW_SLOW,SND_WHOOSHLOW_MEDIUM,SND_WHOOSHLOW_FAST,SND_WHOOSHMID_S_A,SND_WHOOSHMID_M_A,SND_WHOOSHMID_F_A,SND_WHOOSHLOW_S_A,SND_WHOOSHLOW_M_A,SND_WHOOSHLOW_F_A,SND_CHAINSNAP_A,SND_CHAINSNAP_WCLANK_A,SND_CHAINRETURN,SND_BLADEBLOCK,SND_SWORDHIT_SWORDHEV,SND_SWORDHIT_SHIELD,SND_SWORDHIT_STONE,SND_SWORDHIT_WOOD,SND_SWORD_HITMETAL,SND_SWORDHIT_CHEST,SND_SWORD_IMPALE,SND_SWORD_CUTTHEAD,SND_SWDSPECIALATK1,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_HERO_JUMPVOC,SND_HERO_JUMPVOC_A,SND_HERO_JUMPVOCAL,SND_HERO_JUMPVOCAL_A,SND_BODYFALL_ROLL,SND_BODYFALL_SLAM,SND_BODYFALL_HEAVY,SND_BODYFALL_LIGHT,SND_BODYFALL_LIMB,SND_PICKUPS_ORBS_H,SND_PICKUPS_ORBS_M,SND_PICKUPS_ORBS_E,SND_CRANKFORWARD,SND_CRANKBACKWARD,SND_CRANK_STOP,SND_LGCLUNK_UP,SND_LGCLUNK_DN,SND_PUNCH,SND_MINIGAME_HIT,SND_MINIGAME_AVAILABLE,SND_TORCH_LOOP,SND_BLOODSPURT,SND_DMCDOOR_LP,SND_DMCDOOR_STOP,SND_DMCDOOR_START,SND_SPAWN_LP,SND_DIEPOOF,SND_POTTERYSMASH,SND_CHESTGRAB,SND_CHESTOPEN,SND_LEVER,SND_LEVER_RELEASE,SND_MEDUSA_RAY_SHOT,SND_MEDUSA_RAY_LOOP,SND_MEDUSA_TURNTOSTONE,SND_MEDUSA_TURNTOFLESH,SND_RAISEDEAD_SHOT,SND_RAISEDEAD_LP,SND_BOLT_RAISE,SND_BOLT_LP,SND_BOLT_FIRE,SND_BOLT_HIT,SND_LIGHTNING360_START,SND_LIGHTNING360_LP,SND_LIGHTNING360_BOLT,SND_GODMODESHOT,SND_TRANSFORM_LP,SND_TRANSFORM_END,SND_BERZBLADE_DRAW,SND_BERZBLADE_LP,SND_BERZBLADE_FAST,SND_BERZBLADE_MED,SND_BERZBLADE_SLOW,SND_BERZBLADE_HIT,SND_IG_NAV_L,SND_IG_NAV_R,SND_IG_POPUP,SND_IG_POPUP_NO,SND_IG_BARGROW_LP,SND_IG_MAGICOUT,SND_IG_YOUAREDEAD,SND_MM_POPUP,SND_MM_CONTINUE,SND_MM_NAV_UPDN,SND_MM_NAV_LR,SND_MM_SELECT,SND_MM_BACK,SND_MM_RESTART_YES,SND_MM_QUIT_YES,SND_MM_SFX_SLIDER,SND_MM_NEGATIVE,SND_PU_R1,SND_PU_L1,SND_PU_NAV_UPDN,SND_PU_EMPTY,SND_PU_TRANSFER_LP,SND_PU_POWERUP,SND_IG_COOL100,SND_IG_COOLPROG,SND_IG_LOSECOOL,SND_P01B_CRUSHERHIT_B,SND_TRUSSBREAK,SND_INSERTCRANK,SND_STATUEBREAK,SND_BREAKABLEDOOR1,SND_BREAKABLEDOOR2,SND_GROUNDBREAK,SND_LOGSHOOT,SND_BIGDEBRIS,SND_HOISTANCHOR_LP,SND_LOWHEALTH,SND_P4C_BLOCKSMASH,SND_SHARDCOLLECT,SND_SHARDCOMPLETE,SND_ICON,SND_STATUEMOUNT,SND_SWDSPECIALATK1_PRE,SND_CNM_SLAMGROUND,SND_P03GRATESPLASH,SND_BLOODGEYSER,SND_BLOODGUSH,SND_BARRELSMASH,SND_BUCKETSMASH,SND_SWORDHIT_SANDBAG,SND_FRUITBASKETSMASH,SND_SELECT_RTD,SND_SELECT_BOLT,SND_SELECT_LIGHTNING,SND_SELECT_MEDUSA,SND_SELECT_NULL,SND_BEAT1,SND_BEAT2,SND_ARROWFIRE_LP,SND_BIGDEBRISCRASH,SND_STATUEHITWALL,SND_SAVEPOINT_LP,SND_MAI_STRUGGLEVO_LP,SND_DMCDOOR2_STOP,SND_DMCDOOR2_START,SND_HUGESPLASH,SND_SKD_BURROW,SND_SKD_BURROW_LP,SND_BONECRUNCH_BIG,SND_MINIGAME_BUTTON,SND_KICKCHARGEVO_LP,SND_SWIM_UW_LOOP,SND_CHARGE_LP,SND_BOLTCHARGE_LP,SND_UPGRADEWHOOSH,SND_SWIMDASH,SND_MEDUSA_NUKE,SND_ROCKHIT,SND_BAR_FIREBALLIMPACT,SND_HB_POSTMOVIE,SND_MM_NAV_UPDN_LP
R_PERM.WAD|GENERAL2|blk|0|2864|ref|SND_DUMMY,SND_SHAKE_SMALL,SND_SHAKE_MEDIUM,SND_SHAKE_BIG,SND_RUMBLE_SMALL,SND_RUMBLE_MEDIUM,SND_RUMBLE_BIG,SND_RUMBLE_SPECIAL,SND_SHAKE_SPECIAL,SND_HERO_LIFTVOC,SND_HERO_DIEVOC,SND_HERO_GETHITVOC,SND_HERO_GETHITVOC_A,SND_HERO_ATTKVOC_SHORT,SND_HERO_ATKVOC_SHORT_A,SND_HERO_ATTKVOC_LONG,SND_HERO_ATKVOC_LONG_A,SND_MI_RAGEMIME,SND_SHAKE_HUGE,SND_RUMBLE_HUGE,SND_M_SAVE_MUS
R_PERM.WAD|Hero|vag|16|99192|ok|DIEVOC1,H_ATTKL1,H_ATTKL2,H_ATTKS1,H_ATTKS2,H_ATTKS3,H_ATTKS4,H_DMG1,H_DMG2,H_DMG3,H_DMG4,H_DMG5,H_DMG6,JUMPVOC1,JUMPVOC2,LIFTVOC1
R_SAF.WAD|saf|vag|9|99428|ok|SATATK01,SATATK02,SATATK03,SATDIE01,SATHIT01,SATHIT02,SATHIT03,SATHIT04,SATTAUNT
R_SAF.WAD|SBK_SAF_SatyrF|blk|24|113672|ok|SND_SAT_STEPLIGHT,SND_SAT_STEPHEAVY,SND_SAT_STEPLAND,SND_SAT_STAFFSPIN_HIGH,SND_SAT_STAFFSPIN_MED,SND_SAT_STAFFSPIN_LOW,SND_SAT_ATTKWHOOSH1,SND_SAT_ATTKWHOOSH2,SND_SAT_ATTKWHOOSH3,SND_SAT_ATTKWHOOSH4,SND_SAT_BLADEHITGROUND,SND_SAT_BODYFALL_HEAVY,SND_SAT_BODYFALL_MED,SND_SAT_BODYFALL_LIMB,SND_SAT_BODYFALL_HEAD,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_SAT_SNORT,SND_SAT_VOATTACK,SND_SAT_VOGETHIT,SND_SAT_VOGETHITBIG,SND_SAT_VOTAUNT,SND_SAT_VODIE,SND_SAT_VOATTACK_A,SND_SAT_VOGETHIT_A,SND_SAT_VOGETHITB_A,SND_SAT_BLADEDROP,SND_SAT_BLADESCRAPE
R_SAT.WAD|sat|vag|9|99428|ok|SATATK01,SATATK02,SATATK03,SATDIE01,SATHIT01,SATHIT02,SATHIT03,SATHIT04,SATTAUNT
R_SAT.WAD|SBK_SAT_Satyr1|blk|24|113672|ok|SND_SAT_STEPLIGHT,SND_SAT_STEPHEAVY,SND_SAT_STEPLAND,SND_SAT_STAFFSPIN_HIGH,SND_SAT_STAFFSPIN_MED,SND_SAT_STAFFSPIN_LOW,SND_SAT_ATTKWHOOSH1,SND_SAT_ATTKWHOOSH2,SND_SAT_ATTKWHOOSH3,SND_SAT_ATTKWHOOSH4,SND_SAT_BLADEHITGROUND,SND_SAT_BODYFALL_HEAVY,SND_SAT_BODYFALL_MED,SND_SAT_BODYFALL_LIMB,SND_SAT_BODYFALL_HEAD,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_SAT_SNORT,SND_SAT_VOATTACK,SND_SAT_VOGETHIT,SND_SAT_VOGETHITBIG,SND_SAT_VOTAUNT,SND_SAT_VODIE,SND_SAT_VOATTACK_A,SND_SAT_VOGETHIT_A,SND_SAT_VOGETHITB_A,SND_SAT_BLADEDROP,SND_SAT_BLADESCRAPE
R_SD2.WAD|sd2|vag|12|100632|ok|SKD_ATK1,SKD_ATK2,SKD_ATK3,SKD_ATK4,SKD_DIE1,SKD_DIE2,SKD_HIT1,SKD_HIT2,SKD_HIT3,SKD_HIT5,SKDCACK,SKDDIEB1
R_SD2.WAD|SBK_SD2_Dive2|blk|13|113552|ok|SND_SKELDIV_SLASHFAST,SND_SKELDIV_SLASHMEDIUM,SND_SKELDIV_SLASHSLOW,SND_SKELDIV_SLASHSLOWES,SND_SKELSOL_BODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELDIV_VOATTACK,SND_SKELDIV_VOATTACK_A,SND_SKELDIV_VOATKBIG_A,SND_SKELDIV_VOGETHIT,SND_SKELDIV_VOGETHIT_A,SND_SKELDIV_VODIE,SND_SKELDIV_VODIEBRUTAL,SND_SKD_CACKLE,SND_SKD_VODIVE,SND_SKD_SPINATKVO,SND_ARMRIPOFF,SND_SKD_SWORDHIT,SND_SKD_SWORDHITGROUND,SND_SKD_SWORDHITFINAL,SND_SKD_IDLE,SND_SKD_NAVSOUND,SND_SKD_SWORDDROP
R_SHELL.WAD|SBK_Title01|blk|2|111768|ok|SND_HL_A07HL02,SND_M_TIT1E1_2,SND_M_TIT1Q1_2,SND_M_CREDITS1
R_SID.WAD|sid|vag|10|99040|ok|SIR_ATK1,SIR_ATK2,SIR_ATK3,SIR_HIT1,SIR_HIT2,SIR_HIT3,SIR_HIT4,SIR_LAF2,SIR_LAF3,TAUNT02
R_SID.WAD|SBK_SID_Siren2|blk|10|111880|ok|SND_M_SSONG1LP,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_SIREN_FIREBALL,SND_SIR_ELECSHOT,SND_SIR_ELECSHOTBIG,SND_SIR_ELECBLOCK,SND_SIR_ELECEXPLO,SND_SIR_VOLAUGH_SMALL,SND_SIREN_VOATTACK,SND_SIREN_VOATTACK_A,SND_SIREN_VOGETHIT,SND_SIREN_VOGETHIT_A,SND_SIREN_VODIE,SND_SIREN_TAUNT1,SND_SIREN_TAUNT2,SND_SIREN_TAUNT3,SND_SIR_IDLE,SND_SIR_NAVSOUND
R_SIR.WAD|sir|vag|10|99040|ok|SIR_ATK1,SIR_ATK2,SIR_ATK3,SIR_HIT1,SIR_HIT2,SIR_HIT3,SIR_HIT4,SIR_LAF2,SIR_LAF3,TAUNT02
R_SIR.WAD|SBK_SIR_Siren1|blk|10|111880|ok|SND_M_SSONG1LP,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_SIREN_FIREBALL,SND_SIR_ELECSHOT,SND_SIR_ELECSHOTBIG,SND_SIR_ELECBLOCK,SND_SIR_ELECEXPLO,SND_SIR_VOLAUGH_SMALL,SND_SIREN_VOATTACK,SND_SIREN_VOATTACK_A,SND_SIREN_VOGETHIT,SND_SIREN_VOGETHIT_A,SND_SIREN_VODIE,SND_SIREN_TAUNT1,SND_SIREN_TAUNT2,SND_SIREN_TAUNT3,SND_SIR_IDLE,SND_SIR_NAVSOUND
R_SK2.WAD|sk2|vag|12|73112|ok|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
R_SK2.WAD|SBK_SK2_Archer2|blk|19|115300|ok|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_WHOOSH_FAST,SND_WHOOSH_MEDIUM,SND_WHOOSH_SLOW,SND_WHOOSH_SLOWEST,SND_SKELSOL_GETUP,SND_BOW_DRAWBACK_FAST,SND_BOW_DRAWBACK_SLOW,SND_BOW_FIRE,SND_SKELSOL_VODIE,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHIT_A,SND_SKEL_VOGRUNT,SND_SKELARC_TAUNT00,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKA_ARR_FLIGHTSHOT,SND_SKA_ARR_BLOCK,SND_SKA_ARR_HITFLESH,SND_SKA_ARR_HITWATER,SND_SKA_ARR_HITDIRT,SND_SKA_ARR_HITSTONE,SND_SKA_ARR_HITWOOD,SND_SKA_ARR_HITGEN,SND_SKA_ARR_EXPLODE
R_SK3.WAD|sk3|vag|12|73112|ok|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
R_SK3.WAD|SBK_SK3_ArcherF|blk|22|116304|ok|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_WHOOSH_FAST,SND_WHOOSH_MEDIUM,SND_WHOOSH_SLOW,SND_WHOOSH_SLOWEST,SND_SKELSOL_GETUP,SND_BOW_DRAWBACK_FAST,SND_BOW_DRAWBACK_SLOW,SND_BOW_FIRE,SND_SKELSOL_VODIE,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHIT_A,SND_SKEL_VOGRUNT,SND_SKELARC_TAUNT00,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKA_ARR_FLIGHTSHOT,SND_SKA_ARR_BLOCK,SND_SKA_ARR_HITFLESH,SND_SKA_ARR_HITWATER,SND_SKA_ARR_HITDIRT,SND_SKA_ARR_HITSTONE,SND_SKA_ARR_HITWOOD,SND_SKA_ARR_HITGEN,SND_SKA_ARR_EXPLODE
R_SK4.WAD|sk4|vag|9|86148|ok|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELHIT1,SKELHIT2,SKELHIT3
R_SK4.WAD|SBK_SK4_Skel4|blk|28|114416|ok|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHFAST,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHITBIG,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SKEL_VOGRUNT,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKELFALLSCREAM,SND_SKELSOL_CHOKE,SND_SKELSOL_CACKLE,SND_SKELFLIP_A,SND_SKELFLIP_B
R_SK5.WAD|sk5|vag|12|73112|ok|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
R_SK5.WAD|SBK_SKF_Skel3|blk|26|114368|ok|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHFAST,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHITBIG,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SKEL_VOGRUNT,SND_SKF_FLIPYELL,SND_SKF_VOEXTDEATH
R_SKA.WAD|SKA|vag|12|73112|ok|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
R_SKA.WAD|SBK_SKA_Archer1|blk|26|114976|ok|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_WHOOSH_FAST,SND_WHOOSH_MEDIUM,SND_WHOOSH_SLOW,SND_WHOOSH_SLOWEST,SND_SKELSOL_GETUP,SND_BOW_DRAWBACK_FAST,SND_BOW_DRAWBACK_SLOW,SND_BOW_FIRE,SND_SKELSOL_VODIE,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHIT_A,SND_SKEL_VOGRUNT,SND_SKELARC_TAUNT00,SND_SKELARC_TAUNT01,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKA_ARR_FLIGHTSHOT,SND_SKA_ARR_BLOCK,SND_SKA_ARR_HITFLESH,SND_SKA_ARR_HITWATER,SND_SKA_ARR_HITDIRT,SND_SKA_ARR_HITSTONE,SND_SKA_ARR_HITWOOD,SND_SKA_ARR_HITGEN
R_SKB.WAD|skb|vag|12|73112|ok|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
R_SKB.WAD|SBK_SKB_SkelSh|blk|27|114840|ok|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SHIELDBASH,SND_SKELSOL_SLASHFAST,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SHSKEL_SHIELDBREAK,SND_SHSKEL_CACKLE,SND_SKEL_VOGRUNT,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKELSOL_CHOKE,SND_DASHPOWERUP,SND_SHIELDBLOCK2,SND_SKB_TAUNT,SND_SKELFLIP_A,SND_SKELFLIP_B
R_SKC.WAD|skc|vag|9|86148|ok|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELHIT1,SKELHIT2,SKELHIT3
R_SKC.WAD|SBK_SKC_Skel2|blk|28|114600|ok|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHFAST,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHITBIG,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SKEL_VOGRUNT,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKELFALLSCREAM,SND_SKELSOL_CHOKE,SND_PICKAWHOOSH,SND_SKELSOL_CACKLE,SND_SKELFLIP_A,SND_SKELFLIP_B
R_SKD.WAD|skd|vag|12|100632|ok|SKD_ATK1,SKD_ATK2,SKD_ATK3,SKD_ATK4,SKD_DIE1,SKD_DIE2,SKD_HIT1,SKD_HIT2,SKD_HIT3,SKD_HIT5,SKDCACK,SKDDIEB1
R_SKD.WAD|SBK_SKD_Dive1|blk|13|113552|ok|SND_SKELDIV_SLASHFAST,SND_SKELDIV_SLASHMEDIUM,SND_SKELDIV_SLASHSLOW,SND_SKELDIV_SLASHSLOWES,SND_SKELSOL_BODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELDIV_VOATTACK,SND_SKELDIV_VOATTACK_A,SND_SKELDIV_VOATKBIG_A,SND_SKELDIV_VOGETHIT,SND_SKELDIV_VOGETHIT_A,SND_SKELDIV_VODIE,SND_SKELDIV_VODIEBRUTAL,SND_SKD_CACKLE,SND_SKD_VODIVE,SND_SKD_SPINATKVO,SND_ARMRIPOFF,SND_SKD_SWORDHIT,SND_SKD_SWORDHITGROUND,SND_SKD_SWORDHITFINAL,SND_SKD_IDLE,SND_SKD_NAVSOUND,SND_SKD_SWORDDROP
R_SKF.WAD|skf|vag|10|79440|ok|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
R_SKF.WAD|SBK_SKF_Skel3|blk|26|114368|ok|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHFAST,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHITBIG,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SKEL_VOGRUNT,SND_SKF_FLIPYELL,SND_SKF_VOEXTDEATH
R_SKS.WAD|sks|vag|12|73112|ok|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
R_SKS.WAD|SBK_SKS_Skel1|blk|27|115452|ok|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHFAST,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHITBIG,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SKELSOL_CACKLE,SND_SKEL_VOGRUNT,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKELFALLSCREAM,SND_SKELSOL_CHOKE
SEWR01.WAD|SBK_Sewr01|blk|24|153336|ok|SND_SEWERAMB_LP,SND_TOWERAMB_LP,SND_OCEANAMB_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_SEWERDRIPS_LP,SND_BIGFALLS_LP,SND_MEDFALLS_LP,SND_SMALLFALLS_LP,SND_BIGDRIPS_LP,SND_RAT_SQUEAKS_LP,SND_M_SEW1C1_2,SND_M_SEW1C2_2,SND_M_SEW1E1_2,SND_M_SEW1Q1_2,SND_M_SEW2Q6_2,SND_M_SEW1Q7_2
SEWR02.WAD|SBK_Sewr02|blk|28|204104|ok|SND_SEWERAMB_LP,SND_OUTDOORAMB_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_SEWERDRIPS_LP,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_BIGFALLS_LP,SND_MEDFALLS_LP,SND_SMALLFALLS_LP,SND_BIGDRIPS_LP,SND_PISTONMOVE_LP,SND_RAT_SQUEAKS_LP,SND_M_SEW2C3_2,SND_M_SEW2Q5_2,SND_M_SEW1C1_2,SND_M_SEW2Q6_2,SND_M_SEW1Q7_2,SND_M_SEW1E1_2"""

_CATALOG = []


def load_catalog():
    if not _CATALOG:
        for line in CATALOG_TXT.split("\n"):
            f = line.split("|")
            if len(f) == 7 and f[5] == "ok":  # SBK tanpa audio tidak dimasukkan
                _CATALOG.append((f[0], f[1], f[2], int(f[3]), int(f[4]), f[5],
                                 [x for x in f[6].split(",") if x]))
    return _CATALOG


def catalog_search(rows, query):
    """Cocokkan query (huruf besar/kecil diabaikan) ke nama WAD, SBK, atau nama suara."""
    q = query.strip().lower()
    if not q:
        return list(rows)
    return [r for r in rows if q in (r[0] + " " + r[1] + " " + " ".join(r[6])).lower()]


class CatalogDialog(tk.Toplevel):
    STATUS = {"ok": "bisa diedit", "ref": "hanya referensi (tanpa audio)", "kosong": "kosong"}

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.rows = load_catalog()
        self.shown = []
        self.title("Katalog SBK GoW 1")
        self.geometry("740x540")
        wads = len({r[0] for r in self.rows})
        ttk.Label(self, wraplength=710, text=(
            "%d SBK di %d WAD GoW 1. WAD tanpa SBK dan SBK tanpa audio tidak dimasukkan. Cari "
            "berdasarkan nama WAD, nama SBK, atau nama suara." % (len(self.rows), wads))).pack(
            anchor="w", padx=8, pady=(8, 2))
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=4)
        ttk.Label(top, text="Cari:").pack(side="left")
        self.q = tk.StringVar(value="")
        ttk.Entry(top, textvariable=self.q).pack(side="left", fill="x", expand=True, padx=6)
        self.q.trace_add("write", lambda *a: self.fill())

        cols = ("wad", "sbk", "tipe", "sampel", "status")
        self.tv = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c, t, w in zip(cols, ("WAD", "SBK", "Tipe", "Sampel", "Status"), (110, 160, 70, 60, 230)):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8))
        self.tv.pack(fill="both", expand=True, padx=(8, 0))
        self.tv.bind("<<TreeviewSelect>>", lambda e: self.show())

        self.detail = ttk.Label(self, wraplength=710, justify="left", text="Pilih satu SBK.")
        self.detail.pack(fill="x", padx=8, pady=4)
        bt = ttk.Frame(self)
        bt.pack(fill="x", padx=8, pady=6)
        ttk.Button(bt, text="Buka WAD ini", command=self.open_selected).pack(side="left")
        ttk.Button(bt, text="Tutup", command=self.destroy).pack(side="right")
        self.fill()

    def fill(self):
        self.shown = catalog_search(self.rows, self.q.get())
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(self.shown):
            self.tv.insert("", "end", iid=str(i), values=(
                r[0], r[1], "VAG" if r[2] == "vag" else "SBK", r[3] or "-",
                self.STATUS.get(r[5], r[5])))

    def current(self):
        sel = self.tv.selection()
        return self.shown[int(sel[0])] if sel else None

    def show(self):
        r = self.current()
        if not r:
            return
        names = ", ".join(r[6])
        if len(names) > 1200:
            names = names[:1200] + " ..."
        self.detail.config(text="%s / %s - %d byte. Suara (%d): %s" % (
            r[0], r[1], r[4], len(r[6]), names or "-"))

    def open_selected(self):
        r = self.current()
        if not r:
            messagebox.showinfo("Info", "Pilih satu SBK dulu.", parent=self)
            return
        dirs = []
        if self.app.path:
            dirs.append(os.path.dirname(self.app.path))
        if getattr(self.app, "last_dir", None):
            dirs.append(self.app.last_dir)
        for d in dirs:
            for name in (r[0], r[0].lower(), r[0].upper()):
                path = os.path.join(d, name)
                if os.path.isfile(path):
                    self.app.open_path(path)
                    self.app.select_sbk(r[1])
                    return
        messagebox.showinfo(
            "WAD tidak ditemukan",
            "Letakkan %s di folder yang sama dengan WAD yang tadi kamu buka, atau buka lewat "
            "Open WAD." % r[0], parent=self)


def log_error(text):
    """Catat error ke gow_tool_error.txt (di samping exe/script; cadangan: folder temp)."""
    base = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                           else __file__))
    for d in (base, tempfile.gettempdir()):
        try:
            path = os.path.join(d, "gow_tool_error.txt")
            with open(path, "a", encoding="utf-8") as f:
                f.write(text + "\n" + "-" * 60 + "\n")
            return path
        except OSError:
            continue
    return None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GoW WAD SBK Tool")
        self.geometry("760x500")
        try:  # tema "clam" tampil konsisten di Windows asli maupun Wine
            ttk.Style(self).theme_use("clam")
        except tk.TclError:
            pass
        self.buf = None
        self.path = None
        self.entries = []
        self.dirty = False
        self.last_dir = None

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Button(bar, text="Open WAD", command=self.open_wad).pack(side="left")
        ttk.Button(bar, text="Edit audio", command=self.edit_audio).pack(side="left", padx=4)
        ttk.Button(bar, text="Export", command=self.export).pack(side="left")
        ttk.Button(bar, text="Replace file", command=self.replace).pack(side="left", padx=4)
        ttk.Button(bar, text="SAVE", command=self.save).pack(side="left")
        ttk.Button(bar, text="Save As", command=self.save_as).pack(side="left", padx=4)
        ttk.Button(bar, text="Debug", command=self.debug).pack(side="left", padx=4)
        ttk.Label(bar, text="Filter:").pack(side="left", padx=(12, 4))
        self.filter = ttk.Combobox(bar, width=8, state="readonly", values=["SBK", "File", "Semua"])
        self.filter.current(0)
        self.filter.pack(side="left")
        self.filter.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        # kolom path manual: berguna kalau dialog file Wine bermasalah
        row = ttk.Frame(self)
        row.pack(fill="x", padx=8)
        self.path_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.path_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Buka path", command=lambda: self.open_path(
            self.path_var.get().strip().strip('"'))).pack(side="left", padx=4)
        ttk.Button(row, text="Katalog SBK", command=lambda: CatalogDialog(self)).pack(side="left")

        cols = ("name", "type", "offset", "size")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c, t, w in zip(cols, ("Nama", "Tipe", "Offset", "Ukuran"), (280, 90, 110, 100)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8))
        self.tree.pack(fill="both", expand=True, padx=(8, 0))
        self.tree.bind("<Double-1>", lambda ev: self.edit_audio())
        self.status = ttk.Label(self, text="Buka file WAD dulu.")
        self.status.pack(fill="x", side="bottom", padx=8, pady=6)

    def report_callback_exception(self, exc, val, tb):
        text = "".join(traceback.format_exception(exc, val, tb))
        path = log_error(text)
        messagebox.showerror("Error", text[-1500:] + ("\n\nTercatat di: %s" % path if path else ""))

    # ---- helpers ----
    @staticmethod
    def kind(e):
        if e.is_sbk:
            return "SBK-VAG" if e.magic == SBK_VAG else "SBK"
        return hex(e.tag & 0xFFFF)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        mode = self.filter.get()
        for i, e in enumerate(self.entries):
            if mode == "SBK" and not (e.is_sbk and has_audio(self.buf, e)):
                continue
            if mode == "File" and not e.is_file:
                continue
            self.tree.insert("", "end", iid=str(i),
                             values=(e.name, self.kind(e), hex(e.data_off), e.size))

    def select_sbk(self, name):
        """Pilih baris SBK bernama `name` di daftar (setelah WAD dibuka dari katalog)."""
        for iid in self.tree.get_children():
            if self.tree.item(iid, "values")[0] == name:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                return

    def selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Pilih satu file dulu.")
            return None
        return self.entries[int(sel[0])]

    # ---- actions ----
    def open_wad(self):
        try:
            p = filedialog.askopenfilename(
                title="Pilih WAD", filetypes=[("Semua file", "*.*"), ("WAD", "*.wad")])
        except Exception:
            messagebox.showerror("Dialog error", traceback.format_exc())
            return
        if p:
            self.open_path(p)

    def open_path(self, p):
        try:
            if not p or not os.path.isfile(p):
                messagebox.showerror("Error", "File tidak ditemukan:\n%s" % p)
                return
            size = os.path.getsize(p)
            if size > MAX_WAD_SIZE:
                messagebox.showerror(
                    "Bukan WAD",
                    "File ini %d MB, terlalu besar untuk sebuah WAD (kemungkinan file PAK).\n"
                    "Tool ini hanya membuka file .WAD. Ekstrak dulu WAD-nya dari PAK "
                    "(misalnya dengan GoW browser), lalu buka WAD itu." % (size // (1024 * 1024)))
                return
            with open(p, "rb") as f:
                head = f.read(HDR)
                if not looks_like_wad(head):
                    messagebox.showerror(
                        "Bukan WAD",
                        "File ini tidak dikenali sebagai WAD God of War.\n"
                        "Tool hanya membuka file .WAD (bukan PAK, ISO, atau TOC).")
                    return
                f.seek(0)
                self.buf = bytearray(f.read())
            self.path = p
            self.last_dir = os.path.dirname(p)
            self.path_var.set(p)
            self.entries = scan(self.buf)
            self.dirty = False
            self.refresh()
            total = sum(1 for e in self.entries if e.is_sbk)
            n = sum(1 for e in self.entries if e.is_sbk and has_audio(self.buf, e))
            self.status.config(text="%s (%d byte): %d entry, %d SBK berisi audio%s" % (
                os.path.basename(p), len(self.buf), len(self.entries), n,
                " (%d SBK tanpa audio disembunyikan)" % (total - n) if total > n else ""))
            if not self.entries:
                messagebox.showwarning(
                    "Entry tidak terdeteksi",
                    "File terbuka, tapi layout WAD tidak cocok dengan parser.\n"
                    "Klik tombol Debug dan kirim hasilnya.")
            elif n == 0:
                messagebox.showinfo("Tidak ada SBK",
                                    "WAD ini tidak berisi SBK yang punya audio, jadi tidak ada yang bisa "
                                    "diedit di sini. Pilih filter File/Semua kalau mau melihat isinya.")
        except Exception:
            messagebox.showerror("Gagal buka WAD", traceback.format_exc())

    def debug(self):
        if self.buf is None:
            messagebox.showinfo("Debug", "Buka WAD dulu.")
            return
        b = bytes(self.buf[:0x100])
        lines = []
        for i in range(0, len(b), 16):
            c = b[i:i + 16]
            lines.append("%04X  %-47s  %s" % (
                i, " ".join("%02X" % x for x in c),
                "".join(chr(x) if 32 <= x < 127 else "." for x in c)))
        w = tk.Toplevel(self)
        w.title("Debug: 256 byte pertama")
        t = tk.Text(w, width=84, height=20, font=("Courier", 9))
        t.pack(fill="both", expand=True)
        t.insert("end", "File: %s\nUkuran: %d byte\nEntry terdeteksi: %d\n\n%s" % (
            self.path, len(self.buf), len(self.entries), "\n".join(lines)))

    def edit_audio(self):
        e = self.selected()
        if not e:
            return
        try:
            SbkDialog(self, e)
        except ValueError as ex:
            messagebox.showerror("Tidak bisa edit audio", str(ex))
        except Exception:
            messagebox.showerror("Error", traceback.format_exc())

    def export(self):
        e = self.selected()
        if not e:
            return
        p = filedialog.asksaveasfilename(initialfile=e.name)
        if p:
            with open(p, "wb") as f:
                f.write(self.buf[e.data_off:e.data_off + e.size])
            self.status.config(text="Export %s OK" % e.name)

    def replace(self):
        e = self.selected()
        if not e:
            return
        if not e.is_file:
            messagebox.showinfo("Info", "Entry ini bukan file data.")
            return
        p = filedialog.askopenfilename(title="File pengganti untuk %s" % e.name,
                                       filetypes=[("Semua file", "*.*")])
        if not p:
            return
        with open(p, "rb") as f:
            new = f.read()
        old = e.size
        old_slot = (old + ALIGN - 1) & ~(ALIGN - 1)
        if len(new) <= old:
            # lebih kecil/sama: isi nol, ukuran asli dipertahankan -> offset lain tidak bergeser
            blob, size_field = new + b"\x00" * (old_slot - len(new)), old
        else:
            if not messagebox.askyesno(
                    "Lebih besar",
                    "File baru (%d byte) lebih besar dari asli (%d byte).\n"
                    "WAD akan membesar dan semua file setelahnya bergeser. "
                    "ISO harus di-rebuild dan game bisa crash.\nLanjut?" % (len(new), old)):
                return
            new_slot = (len(new) + ALIGN - 1) & ~(ALIGN - 1)
            blob, size_field = new + b"\x00" * (new_slot - len(new)), len(new)
        self.buf[e.data_off:e.data_off + old_slot] = blob
        struct.pack_into("<I", self.buf, e.size_off, size_field)
        self.entries = scan(self.buf)
        self.dirty = True
        self.refresh()
        self.status.config(text="%s diganti (%d byte). Klik SAVE." % (e.name, len(new)))

    def save(self):
        """Tulis hasil edit ke file WAD asli; salinan asli disimpan sebagai .bak (sekali)."""
        if self.buf is None:
            messagebox.showinfo("Info", "Buka WAD dulu.")
            return
        try:
            bak = self.path + ".bak"
            made = not os.path.exists(bak)
            if made:
                shutil.copy2(self.path, bak)
            with open(self.path, "wb") as f:
                f.write(self.buf)
            self.dirty = False
            self.status.config(text="Tersimpan: %s" % os.path.basename(self.path))
            messagebox.showinfo(
                "Tersimpan",
                "Hasil edit ditulis ke:\n%s\n\n%s" % (
                    self.path,
                    ("Salinan WAD asli (sebelum diedit) disimpan di:\n" + bak) if made else
                    ("Backup lama tetap dipakai (tidak ditimpa):\n" + bak)))
        except Exception:
            messagebox.showerror("Gagal simpan", traceback.format_exc())

    def save_as(self):
        """Simpan hasil edit ke nama/lokasi lain; WAD asli tidak disentuh."""
        if self.buf is None:
            messagebox.showinfo("Info", "Buka WAD dulu.")
            return
        try:
            p = filedialog.asksaveasfilename(
                title="Simpan WAD sebagai", initialfile=os.path.basename(self.path))
            if not p:
                return
            with open(p, "wb") as f:
                f.write(self.buf)
            self.dirty = False
            self.status.config(text="Tersimpan: %s" % os.path.basename(p))
            messagebox.showinfo("Tersimpan", "Hasil edit ditulis ke:\n%s\n\nWAD asli tidak diubah." % p)
        except Exception:
            messagebox.showerror("Gagal simpan", traceback.format_exc())


def main():
    try:
        app = App()
        if len(sys.argv) > 1:
            app.after(200, lambda: app.open_path(sys.argv[1]))
        app.mainloop()
    except Exception:
        text = traceback.format_exc()
        path = log_error(text)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Gagal start", text[-1500:] + (
                "\n\nTercatat di: %s" % path if path else ""))
        except Exception:
            print(text)
        sys.exit(1)


if __name__ == "__main__":
    main()
