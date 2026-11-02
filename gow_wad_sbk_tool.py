"""
Gow SBK Tools by Nicho
God of War 1 & 2 (PS2): edit the audio of SBK/SBP sound banks inside .WAD files.
Open a WAD -> pick an SBK -> Edit audio (Replace from WAV) -> SAVE.
Languages: Bahasa Indonesia, English, Português (Brasil).

Run:  python gow_wad_sbk_tool.py      (Python 3.8+, no extra libraries)

WAD layout (stream of entries):
  [u32 tag][u32 size][char name[24]]   32-byte header
  [data of `size` bytes]               then padding to a multiple of 0x10
GoW 1: first tag 0x378, files = tag 0x1E.  GoW 2: first tag 0x15, files = tag 0x01.
SBK = first data dword 0x18 (GoW 1), 0x15 (GoW 2) or 0x40018 (VAG bank).
"""
import json
import os
import shutil
import struct
import sys
import tempfile
import traceback
import wave
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Ikon jendela (PNG 64 px, base64). Ikon exe dipasang saat build (icon.ico).
ICON_B64 = (
    "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"
)

# ======================= BAHASA / LANGUAGE / IDIOMA =======================
APP_NAME = "Gow SBK Tools by Nicho"
LANGS = (("id", "Bahasa Indonesia"), ("en", "English"), ("pt", "Português (Brasil)"))
LANG = "en"
_LI = {"id": 0, "en": 1, "pt": 2}

# kunci: (Indonesia, English, Português-BR)
I18N = {
    # ---- tombol & label jendela utama ----
    "btn_open": ("Buka WAD", "Open WAD", "Abrir WAD"),
    "btn_edit": ("Edit audio", "Edit audio", "Editar áudio"),
    "btn_export": ("Export", "Export", "Exportar"),
    "btn_replace_file": ("Replace file", "Replace file", "Substituir arquivo"),
    "btn_save": ("SAVE", "SAVE", "SALVAR"),
    "btn_save_as": ("Save As", "Save As", "Salvar como"),
    "btn_debug": ("Debug", "Debug", "Debug"),
    "btn_path": ("Buka path", "Open path", "Abrir caminho"),
    "btn_catalog": ("Katalog SBK", "SBK catalog", "Catálogo SBK"),
    "lbl_filter": ("Filter:", "Filter:", "Filtro:"),
    "lbl_lang": ("Bahasa:", "Language:", "Idioma:"),
    "flt_sbk": ("SBK", "SBK", "SBK"),
    "flt_file": ("File", "Files", "Arquivos"),
    "flt_all": ("Semua", "All", "Todos"),
    "col_name": ("Nama", "Name", "Nome"),
    "col_type": ("Tipe", "Type", "Tipo"),
    "col_offset": ("Offset", "Offset", "Offset"),
    "col_size": ("Ukuran", "Size", "Tamanho"),
    "status_none": ("Buka file WAD dulu.", "Open a WAD file first.", "Abra um arquivo WAD primeiro."),
    "info": ("Info", "Info", "Info"),
    "err_title": ("Error", "Error", "Erro"),
    "pick_file": ("Pilih satu file dulu.", "Select a file first.", "Selecione um arquivo primeiro."),
    "open_title": ("Pilih WAD", "Select WAD", "Selecionar WAD"),
    "ft_all": ("Semua file", "All files", "Todos os arquivos"),
    "dlg_err": ("Error dialog", "Dialog error", "Erro de diálogo"),
    "not_found": ("File tidak ditemukan:\n%s", "File not found:\n%s", "Arquivo não encontrado:\n%s"),
    "not_wad": ("Bukan WAD", "Not a WAD", "Não é um WAD"),
    "too_big": (
        "File ini %d MB, terlalu besar untuk sebuah WAD (kemungkinan file PAK).\nTool ini hanya membuka file .WAD. Ekstrak dulu WAD-nya dari PAK (misalnya dengan GoW browser), lalu buka WAD itu.",
        "This file is %d MB, too large for a WAD (probably a PAK file).\nThis tool only opens .WAD files. Extract the WAD from the PAK first (for example with GoW browser), then open that WAD.",
        "Este arquivo tem %d MB, grande demais para um WAD (provavelmente um arquivo PAK).\nEsta ferramenta só abre arquivos .WAD. Extraia primeiro o WAD do PAK (por exemplo com o GoW browser) e depois abra esse WAD."),
    "not_gow": (
        "File ini tidak dikenali sebagai WAD God of War.\nTool hanya membuka file .WAD (bukan PAK, ISO, atau TOC).",
        "This file is not recognized as a God of War WAD.\nThe tool only opens .WAD files (not PAK, ISO, or TOC).",
        "Este arquivo não é reconhecido como um WAD de God of War.\nA ferramenta só abre arquivos .WAD (não PAK, ISO ou TOC)."),
    "opened": (
        "%s [%s] (%d byte): %d entry, %d SBK berisi audio",
        "%s [%s] (%d bytes): %d entries, %d SBKs with audio",
        "%s [%s] (%d bytes): %d entradas, %d SBKs com áudio"),
    "opened_h": (
        "%s [%s] (%d byte): %d entry, %d SBK berisi audio (%d SBK tanpa audio disembunyikan)",
        "%s [%s] (%d bytes): %d entries, %d SBKs with audio (%d SBKs without audio hidden)",
        "%s [%s] (%d bytes): %d entradas, %d SBKs com áudio (%d SBKs sem áudio ocultos)"),
    "no_entries_t": ("Entry tidak terdeteksi", "No entries detected", "Nenhuma entrada detectada"),
    "no_entries": (
        "File terbuka, tapi layout WAD tidak cocok dengan parser.\nKlik tombol Debug dan kirim hasilnya.",
        "The file opened, but the WAD layout does not match the parser.\nClick the Debug button and send the result.",
        "O arquivo abriu, mas o layout do WAD não corresponde ao analisador.\nClique no botão Debug e envie o resultado."),
    "no_sbk_t": ("Tidak ada SBK", "No SBK", "Nenhum SBK"),
    "no_sbk": (
        "WAD ini tidak berisi SBK yang punya audio, jadi tidak ada yang bisa diedit di sini. Pilih filter File/Semua kalau mau melihat isinya.",
        "This WAD has no SBK with audio, so there is nothing to edit here. Choose the Files/All filter to see its contents.",
        "Este WAD não tem SBK com áudio, então não há nada para editar aqui. Escolha o filtro Arquivos/Todos para ver o conteúdo."),
    "open_fail": ("Gagal buka WAD", "Failed to open WAD", "Falha ao abrir o WAD"),
    "dbg_title": ("Debug: 256 byte pertama", "Debug: first 256 bytes", "Debug: primeiros 256 bytes"),
    "dbg_need": ("Buka WAD dulu.", "Open a WAD first.", "Abra um WAD primeiro."),
    "dbg_text": (
        "File: %s\nUkuran: %d byte\nEntry terdeteksi: %d\n\n%s",
        "File: %s\nSize: %d bytes\nEntries detected: %d\n\n%s",
        "Arquivo: %s\nTamanho: %d bytes\nEntradas detectadas: %d\n\n%s"),
    "edit_fail": ("Tidak bisa edit audio", "Cannot edit audio", "Não é possível editar o áudio"),
    "exported": ("Export %s OK", "Exported %s", "%s exportado"),
    "ask_replace_file": ("File pengganti untuk %s", "Replacement file for %s", "Arquivo de substituição para %s"),
    "not_data": ("Entry ini bukan file data.", "This entry is not a data file.", "Esta entrada não é um arquivo de dados."),
    "bigger_t": ("Lebih besar", "Larger", "Maior"),
    "bigger": (
        "File baru (%d byte) lebih besar dari asli (%d byte).\nWAD akan membesar dan semua file setelahnya bergeser. ISO harus di-rebuild dan game bisa crash.\nLanjut?",
        "The new file (%d bytes) is larger than the original (%d bytes).\nThe WAD will grow and every file after it will shift. The ISO must be rebuilt and the game may crash.\nContinue?",
        "O novo arquivo (%d bytes) é maior que o original (%d bytes).\nO WAD vai aumentar e todos os arquivos depois dele vão se deslocar. A ISO precisa ser reconstruída e o jogo pode travar.\nContinuar?"),
    "file_replaced": ("%s diganti (%d byte). Klik SAVE.", "%s replaced (%d bytes). Click SAVE.", "%s substituído (%d bytes). Clique em SALVAR."),
    "saved_t": ("Tersimpan", "Saved", "Salvo"),
    "saved_status": ("Tersimpan: %s", "Saved: %s", "Salvo: %s"),
    "saved_text": (
        "Hasil edit ditulis ke:\n%s\n\n%s",
        "The edited result was written to:\n%s\n\n%s",
        "O resultado editado foi gravado em:\n%s\n\n%s"),
    "bak_new": (
        "Salinan WAD asli (sebelum diedit) disimpan di:\n%s",
        "A copy of the original WAD (before editing) was saved at:\n%s",
        "Uma cópia do WAD original (antes da edição) foi salva em:\n%s"),
    "bak_old": (
        "Backup lama tetap dipakai (tidak ditimpa):\n%s",
        "The existing backup was kept (not overwritten):\n%s",
        "O backup existente foi mantido (não sobrescrito):\n%s"),
    "save_fail": ("Gagal simpan", "Save failed", "Falha ao salvar"),
    "saveas_title": ("Simpan WAD sebagai", "Save WAD as", "Salvar WAD como"),
    "saved_as": (
        "Hasil edit ditulis ke:\n%s\n\nWAD asli tidak diubah.",
        "The edited result was written to:\n%s\n\nThe original WAD was not changed.",
        "O resultado editado foi gravado em:\n%s\n\nO WAD original não foi alterado."),
    "logged": ("\n\nTercatat di: %s", "\n\nLogged at: %s", "\n\nRegistrado em: %s"),
    "start_fail": ("Gagal start", "Failed to start", "Falha ao iniciar"),
    # ---- dialog edit audio ----
    "d_title": ("Edit audio: %s", "Edit audio: %s", "Editar áudio: %s"),
    "d_kind_vag": ("bank VAG (rate asli dari header)", "VAG bank (original rate from the header)", "banco VAG (taxa original do cabeçalho)"),
    "d_kind_blk": ("bank audio internal", "internal audio bank", "banco de áudio interno"),
    "d_head": ("%s - %d sampel. Suara: %s", "%s - %d samples. Sounds: %s", "%s - %d amostras. Sons: %s"),
    "d_rate_lbl": ("Sample rate (Hz):", "Sample rate (Hz):", "Taxa de amostragem (Hz):"),
    "d_rate_hint": (
        "(rate asli tidak ada di header; atur sampai terdengar normal)",
        "(the original rate is not in the header; adjust until it sounds normal)",
        "(a taxa original não está no cabeçalho; ajuste até soar normal)"),
    "d_mode_lbl": ("Jika audio lebih panjang dari slot:", "If the audio is longer than the slot:", "Se o áudio for maior que o slot:"),
    "d_mode_grow": ("Perbesar WAD (tidak dipotong)", "Enlarge WAD (not cut)", "Ampliar WAD (sem cortar)"),
    "d_mode_rate": ("Turunkan rate (ukuran tetap)", "Lower rate (same size)", "Reduzir taxa (mesmo tamanho)"),
    "d_mode_cut": ("Potong sesuai slot", "Cut to the slot", "Cortar para caber no slot"),
    "c_no": ("No", "No.", "Nº"),
    "c_name": ("Nama", "Name", "Nome"),
    "c_offset": ("Offset WAD", "WAD offset", "Offset no WAD"),
    "c_bytes": ("Byte", "Bytes", "Bytes"),
    "c_rate": ("Rate", "Rate", "Taxa"),
    "c_dur": ("Durasi", "Duration", "Duração"),
    "c_loop": ("Loop", "Loop", "Loop"),
    "yes": ("ya", "yes", "sim"),
    "btn_play": ("Putar", "Play", "Reproduzir"),
    "btn_stop": ("Stop", "Stop", "Parar"),
    "btn_hear": ("Dengar WAV", "Hear WAV", "Ouvir WAV"),
    "btn_exp_wav": ("Export WAV", "Export WAV", "Exportar WAV"),
    "btn_repl_wav": ("Replace dari WAV", "Replace from WAV", "Substituir por WAV"),
    "btn_close": ("Tutup", "Close", "Fechar"),
    "d_help": (
        "Putar = dengar sampel asli. Dengar WAV = dengar file WAV-mu sebelum dimasukkan. Setelah Replace, klik SAVE di jendela utama.",
        "Play = hear the original sample. Hear WAV = hear your WAV before inserting it. After Replace, click SAVE in the main window.",
        "Reproduzir = ouvir a amostra original. Ouvir WAV = ouvir seu WAV antes de inseri-lo. Depois de Substituir, clique em SALVAR na janela principal."),
    "pick_sample": ("Pilih satu sampel dulu.", "Select a sample first.", "Selecione uma amostra primeiro."),
    "ask_wav_hear": ("WAV untuk didengar", "WAV to listen to", "WAV para ouvir"),
    "ask_wav_repl": ("WAV pengganti", "Replacement WAV", "WAV de substituição"),
    "exp_ok": ("Export OK: %s (%d Hz)", "Exported: %s (%d Hz)", "Exportado: %s (%d Hz)"),
    "no_player": (
        "Tidak ada pemutar audio yang bisa dipakai. Pakai Export WAV lalu putar di player lain.",
        "No audio player available. Use Export WAV and play it in another player.",
        "Nenhum reprodutor de áudio disponível. Use Exportar WAV e reproduza em outro player."),
    "play_title": ("Putar", "Play", "Reproduzir"),
    "play_fail": ("Gagal memutar", "Playback failed", "Falha ao reproduzir"),
    "fail": ("Gagal", "Failed", "Falha"),
    "repl_fail": ("Gagal replace", "Replace failed", "Falha ao substituir"),
    "hear_info": (
        "WAV-mu: %.2f dtk pada %d Hz (slot: %.2f dtk).",
        "Your WAV: %.2f s at %d Hz (slot: %.2f s).",
        "Seu WAV: %.2f s a %d Hz (slot: %.2f s)."),
    "repl_done": (
        "Sampel %d diganti: %s. Klik SAVE di jendela utama.",
        "Sample %d replaced: %s. Click SAVE in the main window.",
        "Amostra %d substituída: %s. Clique em SALVAR na janela principal."),
    "st_replaced": ("%s: audio diganti. Klik SAVE.", "%s: audio replaced. Click SAVE.", "%s: áudio substituído. Clique em SALVAR."),
    "n_same": ("%.2f dtk, %d Hz -> %d Hz", "%.2f s, %d Hz -> %d Hz", "%.2f s, %d Hz -> %d Hz"),
    "n_grown": ("diperbesar %d byte (%.2f dtk)", "enlarged by %d bytes (%.2f s)", "ampliado em %d bytes (%.2f s)"),
    "n_rate": (
        "rate diturunkan %d -> %d Hz agar muat (kualitas lebih rendah)",
        "rate lowered %d -> %d Hz to fit (lower quality)",
        "taxa reduzida %d -> %d Hz para caber (qualidade menor)"),
    "n_cut": ("dipotong ke %.2f dtk", "cut to %.2f s", "cortado para %.2f s"),
    "c_grow_t": ("WAD akan membesar", "The WAD will grow", "O WAD vai aumentar"),
    "c_grow": (
        "Audio %.2f dtk > slot %.2f dtk.\nWAD membesar sekitar %d byte dan isi setelahnya bergeser; ISO harus di-rebuild. Lanjut?",
        "Audio %.2f s > slot %.2f s.\nThe WAD grows by about %d bytes and everything after it shifts; the ISO must be rebuilt. Continue?",
        "Áudio %.2f s > slot %.2f s.\nO WAD aumenta cerca de %d bytes e tudo depois dele se desloca; a ISO precisa ser reconstruída. Continuar?"),
    # ---- katalog ----
    "k_title": ("Katalog SBK GoW 1 dan GoW 2", "SBK catalog - GoW 1 and GoW 2", "Catálogo SBK - GoW 1 e GoW 2"),
    "k_intro": (
        "%d SBK: %d WAD GoW 1 dan %d WAD GoW 2. WAD tanpa SBK dan SBK tanpa audio tidak dimasukkan. Cari berdasarkan nama WAD, nama SBK, atau nama suara.",
        "%d SBKs: %d GoW 1 WADs and %d GoW 2 WADs. WADs without SBK and SBKs without audio are not included. Search by WAD name, SBK name, or sound name.",
        "%d SBKs: %d WADs do GoW 1 e %d WADs do GoW 2. WADs sem SBK e SBKs sem áudio não estão incluídos. Pesquise pelo nome do WAD, do SBK ou do som."),
    "k_search": ("Cari:", "Search:", "Pesquisar:"),
    "k_game": ("Game", "Game", "Jogo"),
    "k_wad": ("WAD", "WAD", "WAD"),
    "k_sbk": ("SBK", "SBK", "SBK"),
    "k_samples": ("Sampel", "Samples", "Amostras"),
    "k_pick": ("Pilih satu SBK.", "Select an SBK.", "Selecione um SBK."),
    "k_detail": (
        "%s / %s / %s - %d byte. Suara (%d): %s",
        "%s / %s / %s - %d bytes. Sounds (%d): %s",
        "%s / %s / %s - %d bytes. Sons (%d): %s"),
    "k_open": ("Buka WAD ini", "Open this WAD", "Abrir este WAD"),
    "k_pick_first": ("Pilih satu SBK dulu.", "Select an SBK first.", "Selecione um SBK primeiro."),
    "k_nf_t": ("WAD tidak ditemukan", "WAD not found", "WAD não encontrado"),
    "k_nf": (
        "Letakkan %s di folder yang sama dengan WAD yang tadi kamu buka, atau buka lewat Buka WAD.",
        "Put %s in the same folder as the WAD you opened earlier, or open it with Open WAD.",
        "Coloque %s na mesma pasta do WAD aberto anteriormente, ou abra com Abrir WAD."),
    # ---- pilih bahasa ----
    "lang_pick": (
        "Pilih bahasa\nChoose your language\nEscolha o idioma",
        "Pilih bahasa\nChoose your language\nEscolha o idioma",
        "Pilih bahasa\nChoose your language\nEscolha o idioma"),
    # ---- pesan error dari fungsi inti ----
    "e_count": (
        "Jumlah suara di header tidak masuk akal (%d).",
        "The number of sounds in the header is not plausible (%d).",
        "O número de sons no cabeçalho não é plausível (%d)."),
    "e_hdr_cut": ("Header SBK terpotong.", "SBK header is truncated.", "O cabeçalho do SBK está truncado."),
    "e_no_audio": (
        "SBK ini tidak punya data audio sendiri (hanya daftar/referensi). Audionya ada di SBK pasangan (tipe VAG) atau di luar WAD.",
        "This SBK has no audio data of its own (only a list/references). The audio is in a paired SBK (VAG type) or outside the WAD.",
        "Este SBK não tem dados de áudio próprios (apenas lista/referências). O áudio está em um SBK pareado (tipo VAG) ou fora do WAD."),
    "e_empty": ("SBK ini kosong (tidak ada data audio).", "This SBK is empty (no audio data).", "Este SBK está vazio (sem dados de áudio)."),
    "e_vag_count": (
        "Jumlah file VAG tidak masuk akal (%d).",
        "The number of VAG files is not plausible (%d).",
        "O número de arquivos VAG não é plausível (%d)."),
    "e_vag_missing": (
        "File VAG '%s' tidak ditemukan di offset %#x.",
        "VAG file '%s' not found at offset %#x.",
        "Arquivo VAG '%s' não encontrado no offset %#x."),
    "e_vag_size": ("Ukuran VAG '%s' tidak masuk akal.", "VAG '%s' size is not plausible.", "O tamanho do VAG '%s' não é plausível."),
    "e_ambig": (
        "Header SBK ambigu (field dipakai ganda); perbesar dibatalkan.",
        "Ambiguous SBK header (a field is used twice); enlarging cancelled.",
        "Cabeçalho do SBK ambíguo (campo usado duas vezes); ampliação cancelada."),
    "e_ref_missing": (
        "Referensi sampel tidak ditemukan di header SBK; tidak bisa diperbesar dengan aman.",
        "Sample reference not found in the SBK header; it cannot be enlarged safely.",
        "Referência da amostra não encontrada no cabeçalho do SBK; não é possível ampliar com segurança."),
    "e_stray": (
        "Header SBK ini punya referensi lain ke sampel setelahnya yang tidak bisa digeser dengan aman. Pakai mode Potong atau Turunkan rate, atau WAV yang lebih pendek.",
        "This SBK header has other references to later samples that cannot be shifted safely. Use the Cut or Lower rate mode, or a shorter WAV.",
        "Este cabeçalho do SBK tem outras referências a amostras seguintes que não podem ser deslocadas com segurança. Use o modo Cortar ou Reduzir taxa, ou um WAV mais curto."),
    "e_wav": (
        "WAV tidak didukung (pakai PCM 8/16/24/32-bit): %s",
        "Unsupported WAV (use 8/16/24/32-bit PCM): %s",
        "WAV não suportado (use PCM de 8/16/24/32 bits): %s"),
    "e_width": ("Sample width %d tidak didukung.", "Sample width %d is not supported.", "Largura de amostra %d não suportada."),
    "e_rate_range": ("Sample rate harus 4000-96000.", "Sample rate must be 4000-96000.", "A taxa de amostragem deve ser 4000-96000."),
    "e_rate_vag_only": (
        "Mode Turunkan rate hanya untuk bank VAG.",
        "The Lower rate mode is only for VAG banks.",
        "O modo Reduzir taxa é só para bancos VAG."),
    "e_rate_low": (
        "Audio terlalu panjang: rate yang dibutuhkan (%d Hz) terlalu rendah. Pakai mode Perbesar.",
        "Audio too long: the required rate (%d Hz) is too low. Use the Enlarge mode.",
        "Áudio longo demais: a taxa necessária (%d Hz) é baixa demais. Use o modo Ampliar."),
}


def tr(key, *args):
    """Teks sesuai bahasa aktif; argumen opsional diformat dengan %."""
    t = I18N[key][_LI.get(LANG, 1)]
    return t % args if args else t


def _settings_dirs():
    base = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                           else __file__))
    return [base, tempfile.gettempdir()]


def load_lang():
    """Bahasa tersimpan (atau None kalau belum pernah dipilih)."""
    for d in _settings_dirs():
        try:
            with open(os.path.join(d, "sbk_tools_settings.json"), encoding="utf-8") as f:
                code = json.load(f).get("lang")
            if code in _LI:
                return code
        except (OSError, ValueError):
            continue
    return None


def save_lang(code):
    for d in _settings_dirs():
        try:
            with open(os.path.join(d, "sbk_tools_settings.json"), "w", encoding="utf-8") as f:
                json.dump({"lang": code}, f)
            return True
        except OSError:
            continue
    return False


HDR = 0x20
ALIGN = 0x10
SBK_MAGICS = (0x18, 0x15, 0x40018)  # bank audio internal (GoW 1: 0x18, GoW 2: 0x15) / bank VAG
SBK_VAG = 0x40018
MAX_WAD_SIZE = 128 * 1024 * 1024  # WAD terbesar sekitar 8 MB; PAK jauh lebih besar

# Penanda entry beda per game (tag = 16 bit bawah u32 pertama header)
GAMES = {
    1: {"name": "GoW 1", "first_tag": 0x378, "file_tag": 0x1E,
        "nodata": (0x18, 0x28, 0x32, 0x3E7, 0x29A), "prefix": ("sbk_",)},
    2: {"name": "GoW 2", "first_tag": 0x15, "file_tag": 0x01,
        "nodata": (0x00, 0x02, 0x03, 0x13, 0x16), "prefix": ("sbp_", "sbk_")},
}


def detect_game(head):
    """1 = GoW 1, 2 = GoW 2, 0 = bukan WAD GoW."""
    if len(head) < HDR or head[8:12] != b"WAD_":
        return 0
    tag = struct.unpack_from("<I", head, 0)[0] & 0xFFFF
    for g, d in GAMES.items():
        if tag == d["first_tag"]:
            return g
    return 0


def looks_like_wad(head):
    """WAD GoW diawali entry bernama 'WAD_xxx' (tag 0x378 di GoW 1, 0x15 di GoW 2)."""
    return detect_game(head) != 0


class Entry:
    def __init__(self, hdr_off, tag, size, name, magic=0, game=1):
        self.hdr_off = hdr_off
        self.size_off = hdr_off + 4
        self.data_off = hdr_off + HDR
        self.tag = tag
        self.size = size
        self.name = name
        self.magic = magic
        self.game = game

    @property
    def is_file(self):
        return (self.tag & 0xFFFF) == GAMES[self.game]["file_tag"] and self.size > 0

    @property
    def is_sbk(self):
        return self.is_file and (self.name.lower().startswith(GAMES[self.game]["prefix"])
                                 or self.magic in SBK_MAGICS)


def scan(buf):
    """Jalan sepanjang WAD; berhenti kalau struktur tidak masuk akal. Bukan WAD GoW -> []."""
    game = detect_game(bytes(buf[:HDR]))
    if not game:
        return []
    nodata = GAMES[game]["nodata"]
    entries, off, n = [], 0, len(buf)
    while off + HDR <= n:
        tag, size = struct.unpack_from("<II", buf, off)
        dsz = 0 if (tag & 0xFFFF) in nodata else size
        if dsz > n - off - HDR:
            break
        name = bytes(buf[off + 8:off + HDR]).split(b"\0")[0].decode("latin1")
        magic = struct.unpack_from("<I", buf, off + HDR)[0] if dsz >= 4 else 0
        entries.append(Entry(off, tag, dsz, name, magic, game))
        off += HDR + ((dsz + ALIGN - 1) & ~(ALIGN - 1))
    return entries


# ======================= AUDIO: PS-ADPCM + SBK =======================
PS_K = [(0, 0), (60, 0), (115, -52), (98, -55), (122, -60)]
DUMMY = b"\x77" * 14  # frame penutup standar Sony


def is_trailer(fr):
    """Frame penutup khusus GoW 2: ff ff ff ff + (28, jumlah sampel). Bukan data ADPCM."""
    return fr[0:4] == b"\xff\xff\xff\xff"


def ps_decode(data):
    """PS-ADPCM (16 byte/frame -> 28 sampel) ke list int16 mono."""
    s1 = s2 = 0
    out = []
    for i in range(0, len(data) - 15, 16):
        if is_trailer(data[i:i + 4]):
            continue
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


def _is_tail_frame(buf, o):
    """Frame akhir sampel: ada flag end (bit 0), frame dummy 0x77, atau penutup 0xFF GoW 2."""
    return bool(buf[o + 1] & 1) or bytes(buf[o + 2:o + 16]) == DUMMY or is_trailer(buf[o:o + 4])


def _blk_info(buf, off, size):
    """Bank 0x18/0x15: audio ada di 'stream block' di dalam SBK."""
    cnt = struct.unpack_from("<I", buf, off + 4)[0]
    if cnt == 0 or cnt > 512:
        raise ValueError(tr("e_count", cnt))
    base = 8 + 28 * cnt
    if base + 0x18 > size:
        raise ValueError(tr("e_hdr_cut"))
    names = []
    for i in range(cnt):
        raw = bytes(buf[off + 8 + 28 * i: off + 8 + 28 * i + 24])
        names.append(raw.split(b"\0")[0].decode("latin1"))
    _hs, _hz, ss, sz = struct.unpack_from("<4I", buf, off + base + 8)
    st = base + ss
    if sz == 0 or sz % 16 or st + sz > size:
        raise ValueError(tr("e_no_audio"))
    n = sz // 16
    a0 = off + st
    flags = [buf[a0 + i * 16 + 1] for i in range(n)]
    samples, loops, s0, i = [], [], 0, 0
    while i < n:
        if (flags[i] & 1) or is_trailer(buf[a0 + i * 16:a0 + i * 16 + 4]):
            j = i  # perluas sampai semua frame penutup berurutan (end/dummy/0xFF)
            while j + 1 < n and _is_tail_frame(buf, a0 + (j + 1) * 16):
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
        raise ValueError(tr("e_vag_count", cnt))
    samples, labels, rates, vos = [], [], [], []
    for i in range(cnt):
        e = off + 8 + 28 * i
        name = bytes(buf[e:e + 24]).split(b"\0")[0].decode("latin1")
        vo = struct.unpack_from("<I", buf, e + 24)[0]
        if vo + 0x30 > size or bytes(buf[off + vo:off + vo + 4]) != b"VAGp":
            raise ValueError(tr("e_vag_missing", name, vo))
        dlen = struct.unpack_from(">I", buf, off + vo + 12)[0]
        rate = struct.unpack_from(">I", buf, off + vo + 16)[0]
        dlen -= dlen % 16
        if dlen == 0 or vo + 0x30 + dlen > size:
            raise ValueError(tr("e_vag_size", name))
        samples.append((vo + 0x30, dlen // 16))
        labels.append(name)
        rates.append(rate)
        vos.append(vo)
    return {"kind": "vag", "names": labels, "samples": samples, "loops": [False] * cnt,
            "rates": rates, "labels": labels, "vo": vos}


def parse_sbk(buf, off, size):
    """Baca SBK. samples = [(offset byte relatif awal data, jumlah frame)]."""
    if size < 0x20:
        raise ValueError(tr("e_empty"))
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
    """(alamat awal, frame_awal_dilewati, frame_yang_ditulis, frame_penutup_dijaga)."""
    s, n = info["samples"][idx]
    a = off + s
    lead = 1 if n > 2 and bytes(buf[a:a + 16]) == b"\x00" * 16 else 0
    tail = 0
    while n - lead - tail > 1:
        o = a + (n - 1 - tail) * 16
        if bytes(buf[o + 2:o + 16]) == DUMMY or is_trailer(buf[o:o + 4]):
            tail += 1
        else:
            break
    return a, lead, n - lead - tail, tail


def capacity(buf, off, info, idx):
    return slot_layout(buf, off, info, idx)[2] * 28


def replace_sample(buf, off, info, idx, pcm):
    """Tulis audio baru ke slot (ukuran tetap; byte flag loop/end tidak diubah)."""
    a, lead, body, _tail = slot_layout(buf, off, info, idx)
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

    def put(pos, val, fmt="<I"):
        if pos in P and P[pos] != (val, fmt):
            raise ValueError(tr("e_ambig"))
        P[pos] = (val, fmt)

    if info["kind"] == "vag":
        vo = info["vo"]
        old = struct.unpack_from(">I", buf, off + vo[idx] + 12)[0]
        put(vo[idx] + 12, old + delta, ">I")
        for j in range(len(vo)):
            if vo[j] > vo[idx]:
                put(8 + 28 * j + 24, vo[j] + delta, "<I")
        return [(p, v, f) for p, (v, f) in P.items()]

    st, total = info["st"], info["stream_size"]
    words = struct.unpack_from("<%dI" % (st // 4), buf, off)
    smp = [(s - st, n * 16) for s, n in info["samples"]]

    def pairs(o, z):  # posisi kata tempat pasangan (offset, ukuran) persis ini muncul
        return [p for p in range(len(words) - 1) if words[p] == o and words[p + 1] == z]

    found = pairs(*smp[idx])
    if not found:
        raise ValueError(tr("e_ref_missing"))
    for p in found:
        put((p + 1) * 4, smp[idx][1] + delta)
    for j in range(idx + 1, len(smp)):   # sampel setelahnya bergeser
        o, z = smp[j]
        refs = pairs(o, z)
        if o:
            stray = [p for p, w in enumerate(words) if w == o and p not in refs]
            if stray:
                raise ValueError(tr("e_stray"))
        for p in refs:
            put(p * 4, o + delta)
    for p, w in enumerate(words):
        if w == total:
            put(p * 4, total + delta)
    return [(pp, v, f) for pp, (v, f) in P.items()]


def grow_sample(buf, e, info, idx, pcm):
    """Perbesar slot sampel agar muat seluruh pcm. buf (WAD) dan e.size ikut membesar,
    isi setelahnya bergeser. Return jumlah byte tambahan."""
    off = e.data_off
    a, lead, ob, tail = slot_layout(buf, off, info, idx)
    nb = max(ob, -(-len(pcm) // 28))
    delta = (nb - ob) * 16
    if delta == 0:
        replace_sample(buf, off, info, idx, pcm)
        return 0
    patches = _plan_patches(buf, off, info, idx, delta)  # error di sini = buf belum diubah
    n = info["samples"][idx][1]
    last = a + (n - 1) * 16
    trailer = last if is_trailer(buf[last:last + 4]) else None  # GoW 2: penutup berisi jumlah sampel
    of = [buf[a + (lead + k) * 16 + 1] for k in range(ob)]
    ins = a + (lead + ob) * 16
    buf[ins:ins] = bytes(delta)
    for k, (b0, dt) in enumerate(ps_encode(pcm, nb)):
        o = a + (lead + k) * 16
        buf[o] = b0
        buf[o + 1] = _flag_for(of, k, nb)
        buf[o + 2:o + 16] = dt
    if trailer is not None:
        pos = trailer + delta + 8
        struct.pack_into("<I", buf, pos, struct.unpack_from("<I", buf, pos)[0] + (nb - ob) * 28)
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
        raise ValueError(tr("e_wav", ex))
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
        raise ValueError(tr("e_width", sw))
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
    """Logika edit satu SBK tanpa GUI. mode: 'grow' (perbesar), 'rate' (turunkan rate, VAG), 'cut'."""

    def __init__(self, app, hdr_off, mode="grow", user_rate=22050):
        self.app, self.hdr_off, self.mode, self.user_rate = app, hdr_off, mode, user_rate
        self.reload()

    def reload(self):
        self.e = next(x for x in self.app.entries if x.hdr_off == self.hdr_off)
        self.info = parse_sbk(self.app.buf, self.e.data_off, self.e.size)

    def rate_of(self, i):
        return self.info["rates"][i] or self.user_rate

    def pcm_of(self, i):
        return ps_decode(sample_bytes(self.app.buf, self.e.data_off, self.info, i))

    def apply(self, i, path, confirm=None):
        """Ganti sampel i dari WAV. confirm(judul, teks)->bool dipanggil sebelum WAD membesar."""
        r = self.rate_of(i)
        if not r or not 4000 <= r <= 96000:
            raise ValueError(tr("e_rate_range"))
        buf, off, info = self.app.buf, self.e.data_off, self.info
        pcm, src_rate = read_wav(path, r)
        cap = capacity(buf, off, info, i)
        if len(pcm) <= cap:
            replace_sample(buf, off, info, i, pcm)
            return tr("n_same", len(pcm) / r, src_rate, r)
        if self.mode == "grow":
            extra = (-(-len(pcm) // 28) * 28 - cap) // 28 * 16
            if confirm and not confirm(tr("c_grow_t"), tr("c_grow", len(pcm) / r, cap / r, extra)):
                raise RuntimeError("cancelled")
            grown = grow_sample(buf, self.e, info, i, pcm)
            self.app.entries = scan(buf)
            self.reload()
            return tr("n_grown", grown, len(pcm) / r)
        if self.mode == "rate":
            if info["kind"] != "vag":
                raise ValueError(tr("e_rate_vag_only"))
            new_rate = int(r * cap / len(pcm))
            if new_rate < 4000:
                raise ValueError(tr("e_rate_low", new_rate))
            pcm2, _ = read_wav(path, new_rate)
            replace_sample(buf, off, info, i, pcm2)
            set_vag_rate(buf, off, info, i, new_rate)
            self.reload()
            return tr("n_rate", r, new_rate)
        replace_sample(buf, off, info, i, pcm)  # cut
        return tr("n_cut", cap / r)


class SbkDialog(tk.Toplevel):
    """Editor audio di dalam satu SBK: putar / export / replace per sampel."""

    MODES_BLK = (("grow", "d_mode_grow"), ("cut", "d_mode_cut"))
    MODES_VAG = (("grow", "d_mode_grow"), ("rate", "d_mode_rate"), ("cut", "d_mode_cut"))

    def __init__(self, app, entry):
        sess = SbkSession(app, entry.hdr_off)  # ValueError -> ke pemanggil
        super().__init__(app)
        self.app, self.sess = app, sess
        self.e, self.info = sess.e, sess.info
        self.title(tr("d_title", entry.name))
        self.geometry("700x500")
        info = self.info
        kind = tr("d_kind_vag") if info["kind"] == "vag" else tr("d_kind_blk")
        names = ", ".join(info["names"][:12]) + (" ..." if len(info["names"]) > 12 else "")
        ttk.Label(self, wraplength=670, text=tr("d_head", kind, len(info["samples"]), names)).pack(
            anchor="w", padx=8, pady=(8, 2))

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=4)
        self.rate = tk.StringVar(value="22050")
        if info["kind"] == "blk":
            ttk.Label(top, text=tr("d_rate_lbl")).pack(side="left")
            ttk.Entry(top, textvariable=self.rate, width=8).pack(side="left", padx=4)
            ttk.Label(top, text=tr("d_rate_hint")).pack(side="left")
            self.rate.trace_add("write", lambda *a: self.fill())

        mrow = ttk.Frame(self)
        mrow.pack(fill="x", padx=8, pady=2)
        ttk.Label(mrow, text=tr("d_mode_lbl")).pack(side="left")
        self.modes = self.MODES_VAG if info["kind"] == "vag" else self.MODES_BLK
        self.mode = ttk.Combobox(mrow, state="readonly", width=34, values=[tr(m[1]) for m in self.modes])
        self.mode.current(0)
        self.mode.pack(side="left", padx=6)

        cols = ("no", "nama", "offset", "byte", "rate", "durasi", "loop")
        self.tv = ttk.Treeview(self, columns=cols, show="headings", height=10)
        heads = (tr("c_no"), tr("c_name"), tr("c_offset"), tr("c_bytes"), tr("c_rate"),
                 tr("c_dur"), tr("c_loop"))
        for c, t, w in zip(cols, heads, (36, 150, 90, 80, 60, 70, 50)):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8))
        self.tv.pack(fill="both", expand=True, padx=(8, 0))

        bt = ttk.Frame(self)
        bt.pack(fill="x", padx=8, pady=6)
        ttk.Button(bt, text=tr("btn_play"), command=self.play).pack(side="left")
        ttk.Button(bt, text=tr("btn_stop"), command=stop_audio).pack(side="left", padx=2)
        ttk.Button(bt, text=tr("btn_hear"), command=self.preview).pack(side="left", padx=2)
        ttk.Button(bt, text=tr("btn_exp_wav"), command=self.export).pack(side="left", padx=2)
        ttk.Button(bt, text=tr("btn_repl_wav"), command=self.replace).pack(side="left", padx=2)
        ttk.Button(bt, text=tr("btn_close"), command=self.destroy).pack(side="right")

        self.msg = ttk.Label(self, wraplength=670, justify="left", text=tr("d_help"))
        self.msg.pack(fill="x", padx=8, pady=4)
        self.fill()

    # ---- sinkron dengan session ----
    def _sync(self):
        s = self.sess
        try:
            s.user_rate = int(self.rate.get())
        except ValueError:
            s.user_rate = None
        s.mode = self.modes[self.mode.current()][0]

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
                "%.2f s" % (n * 28 / r), tr("yes") if self.info["loops"][i] else "-"))
        if sel and self.tv.exists(sel[0]):
            self.tv.selection_set(sel[0])

    def pick(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo(tr("info"), tr("pick_sample"), parent=self)
            return None
        i = int(sel[0])
        r = self.rate_of(i)
        if r is None:
            messagebox.showinfo(tr("info"), tr("e_rate_range"), parent=self)
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
            self.msg.config(text=tr("exp_ok", os.path.basename(path), r))

    def _play(self, pcm, r):
        try:
            if not play_pcm(pcm, r):
                messagebox.showinfo(tr("play_title"), tr("no_player"), parent=self)
        except Exception:
            messagebox.showerror(tr("play_fail"), traceback.format_exc(), parent=self)

    def play(self):
        p = self.pick()
        if p:
            self._play(self.pcm_of(p[0]), p[1])

    def preview(self):
        p = self.pick()
        if not p:
            return
        path = filedialog.askopenfilename(
            parent=self, title=tr("ask_wav_hear"), filetypes=[("WAV", "*.wav"), (tr("ft_all"), "*.*")])
        if not path:
            return
        try:
            pcm, _ = read_wav(path, p[1])
            self.msg.config(text=tr("hear_info", len(pcm) / p[1], p[1],
                                    capacity(self.app.buf, self.e.data_off, self.info, p[0]) / p[1]))
            self._play(pcm, p[1])
        except Exception as ex:
            messagebox.showerror(tr("fail"), str(ex), parent=self)

    def replace(self):
        p = self.pick()
        if not p:
            return
        i, _r = p
        path = filedialog.askopenfilename(
            parent=self, title=tr("ask_wav_repl"), filetypes=[("WAV", "*.wav"), (tr("ft_all"), "*.*")])
        if not path:
            return
        self._sync()
        try:
            note = self.sess.apply(i, path, confirm=lambda t, m: messagebox.askyesno(t, m, parent=self))
        except RuntimeError:
            return
        except Exception as ex:
            messagebox.showerror(tr("repl_fail"), str(ex), parent=self)
            return
        self.app.dirty = True
        self._after()
        self.msg.config(text=tr("repl_done", i + 1, note))
        self.app.set_status("st_replaced", self.e.name)


# ======================= KATALOG SBK (GoW 1 dan GoW 2) =======================
# Hasil pindai WAD GoW 1 (216 WAD) dan GoW 2 (292 WAD): hanya SBK yang berisi audio.
# WAD tanpa SBK dan SBK tanpa audio tidak dimasukkan.
# Format per baris: game|WAD|SBK|tipe|jumlah sampel|ukuran|nama suara (dipisah koma)
CATALOG_TXT = """1|ARENA06.WAD|SBK_Arena00|blk|4|92576|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
1|ARENA08.WAD|SBK_Arena00|blk|4|92576|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
1|ARENA09.WAD|SBK_Arena00|blk|4|92576|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
1|ARENA10.WAD|SBK_Arena00|blk|4|92576|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
1|ARENA12.WAD|SBK_Arena12|blk|24|182776|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_BALISTA_COCK_LP,SND_BALISTA_COCKED,SND_BALLISTA_FIRE,SND_RELOAD,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_BALLISTA_HIT,SND_M_AREC12_2
1|ARENA14.WAD|SBK_Arena14|blk|5|96584|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_HOVER_LP,SND_M_AREC14_2
1|ARENA19.WAD|SBK_Arena00|blk|4|92576|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
1|ARENA20.WAD|SBK_Arena00|blk|4|92576|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
1|ARENA26.WAD|SBK_Arena00|blk|4|92576|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_DRAIN_ARENA_LP,SND_M_AREC06_2,SND_M_AREC08_2,SND_M_AREC09_2,SND_M_AREC19_2,SND_M_AREC10_2,SND_M_AREC20_2,SND_M_AREC26_2
1|ARENA27.WAD|SBK_Arena36|blk|5|96664|SND_ARENAAMB_LP,SND_BIGTORCH_LP,SND_HOVER_LP,SND_DRAIN_ARENA_LP,SND_M_AREC27_2,SND_M_AREQ99_2
1|ATHN01A.WAD|SBK_Athn01A|blk|16|159828|SND_OCEANSTORM_LP,SND_POSTSTORMAMB_LP,SND_WAVECRASH,SND_FABRICFLAP_LP,SND_LIFTHATCH_GRAB,SND_LIFTHATCH_STOP,SND_LIFTHATCH_REST,SND_HATCHBURST,SND_HATCHCLOSE,SND_HATCHBANG,SND_HATCH_CHAIN,SND_LOOKATME,SND_MI_A01MI09,SND_MI_A01MI10,SND_HL_A01HL19,SND_HL_A01HL20,SND_MI_A01MI11,SND_M_ATH1C1_4,SND_M_ATH1Q1_2,SND_RAIN_LP,SND_MI_THUNDER,SND_M_ATH1E4_2
1|ATHN01B.WAD|SBK_Athn01B|blk|20|202976|SND_OCEANSTORMINT_LP,SND_DEADBOSSINTAMB_LP,SND_WATERHULL_LP,SND_WATER_DECK_LP,SND_CRATEAMB_LP,SND_HULLCRASH,SND_HL_A01HL22,SND_HYDRA_HEADSLAM,SND_HULLSMACK,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_WATER_DECK_L1,SND_HYDBABH_VODEFEATED,SND_HDYBABH_BITE,SND_M_ATH1C1_4,SND_M_ATH1Q1_2,SND_M_ATH1C2_2,SND_M_ATH1E4_2,SND_M_ATH1Q5_2,SND_M_ATH1E5_2
1|ATHN01C.WAD|SBK_Athn01C|blk|22|206672|SND_OCEANSTORMINT_LP,SND_OCEANSTORM_LP,SND_POSTSTORMAMB_LP,SND_DEADBOSSINTAMB_LP,SND_WATERHULL_LP,SND_KEELCRASH,SND_BETWEENDABOATS,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_DOORKICK,SND_BEAMSCARE_LP,SND_HDYBABV_BITE,SND_MI_A01MI01,SND_MI_A01MI02,SND_MI_A01MI08,SND_HL_A01HL01,SND_HL_A01HL02,SND_HL_A01HL03,SND_HL_A01HL04,SND_HL_A01HL05,SND_MALESCREAM,SND_M_ATH1E5_2,SND_M_ATH1C3_2,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_RAIN_LP,SND_BHB_SWEEP_SCREAM,SND_HYDRA_HEADSLAM,SND_HDYBABV_BITE2,SND_HDYBABV_BITE3,SND_DISTANTSCREAM,SND_HL_PANIC,SND_AMBFILL_LP,SND_KEELCRASH2,SND_BHB_STRUGGLE2_LP,SND_M_ATH1E6_2,SND_HL_A01HL06,SND_MALEVO_GETHIT_CS
1|ATHN01D.WAD|SBK_Athn01D|blk|22|202920|SND_OCEANSTORM_LP,SND_POSTSTORMAMB_LP,SND_DEADBOSSINTAMB_LP,SND_WAVECRASH,SND_LIFTDOOR_LP,SND_WATER_DECK_LP,SND_PULLBOX_LP,SND_ROPEZIP_LP,SND_TRAPPED_MEN,SND_WINDWHISTLES_LOOP,SND_DOORKICK,SND_PULLBOXCLUNK,SND_A01HL10,SND_UNLOCKDOOR,SND_HL_A01HL27,SND_M_ATH1C4_2,SND_M_ATH1E1_2,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_M_ATH1C5_2,SND_M_ATH1Q1_2,SND_M_ATH1E4_2,SND_M_ATH1E7_2,SND_M_ATH1Q7_2,SND_M_ATH1E6_2
1|ATHN01E.WAD|SBK_Athn01E|blk|19|199844|SND_OCEANSTORM_LP,SND_OCEANSTORMINT_LP,SND_POSTSTORMAMB_LP,SND_DEADBOSSINTAMB_LP,SND_HYDRAMOUTHAMB_LP,SND_ROPEZIP_LP,SND_WATER_MAST_LP,SND_BREAKTRUSS,SND_NECKLACE,SND_ANCHORFALL_LP,SND_DECKSMASH,SND_MASTCRACK,SND_MASTBREAK,SND_POSDOOR_LP,SND_ANCHOR_HYDRA,SND_HL_A01HL14,SND_HL_A01HL14A,SND_HL_A01HL14B,SND_HL_A01HL14C,SND_HL_A01HL14D,SND_HL_A01HL14E,SND_HL_A01HL15,SND_SS_POSMAG06,SND_M_ATH1C7_2,SND_M_ATH1C2_2,SND_M_ATH1E2_2,SND_M_AQMAGC_Q,SND_KEELCRASH,SND_HL_A01HL14O,SND_HL_A01HL14AO,SND_HL_A01HL14BO,SND_HL_A01HL14CO,SND_HL_A01HL14DO,SND_HL_A01HL14EO,SND_HYDRA_HEADSLAM,SND_HDYBABV_BITE,SND_HDYBABV_BITE2,SND_HDYBABV_BITE3,SND_AHA_MASTBITE,SND_AHA_BITE,SND_WINDWHISTLES_LOOP,SND_M_ATH1Q3_2,SND_M_ATH1Q4_2,SND_M_ATH1E1_2,SND_CAP_STRUGGLE_LP,SND_M_ATH1E7_2,SND_M_ATH1Q6_2,SND_SCREAMWIND_LOOP
1|ATHN01EE.WAD|SBK_Athn01EE|blk|11|199632|SND_BHA_STRUGGLEVO_LP,SND_BHB_SWEEP_SCREAM,SND_AHA_ATTKLONG_VO,SND_AHA_CHOMP,SND_AHA_GILLFLAP,SND_HYDBAB_GILLFLAP
1|ATHN01F.WAD|SBK_Athn01F|blk|22|197428|SND_OCEANAMB_LP,SND_SHIPCABINAMB_LP,SND_WATERFALL_LP,SND_MI_A02MI01,SND_MI_A02MI02,SND_MI_A02MI023,SND_DOORKICK,SND_HL_A02HL01,SND_HL_A02HL01A,SND_HL_A02HL01B,SND_HL_A02HL01C,SND_HL_A02HL02A,SND_HL_A02HL02B,SND_HL_A02HL02C,SND_HL_A02HL02D,SND_M_ATH1E3_2,SND_SS_MOAN_01,SND_SS_MOAN_02,SND_SS_MOAN_03,SND_SS_MOAN_04,SND_SS_MOAN_05,SND_SS_MOAN_06,SND_SS_MOAN_07,SND_SS_MOAN_08,SND_SS_MOAN_09,SND_SS_MOAN_10,SND_SS_MOAN_11,SND_SS_MOAN_12,SND_SS_MOAN_13,SND_SS_MOAN_14,SND_SS_MOAN_15,SND_SS_MOAN_16,SND_SS_MOAN_17,SND_SS_MOAN_18,SND_SS_MOAN_19,SND_SS_MOAN_20,SND_SS_MOAN_21,SND_SS_MOAN_22,SND_SS_MOAN_23,SND_SS_MOAN_24,SND_SS_MOAN_25,SND_SS_MOAN_26,SND_SS_MOAN_27,SND_SS_MOAN_28,SND_SS_MOAN_29,SND_SS_MOAN_30,SND_SS_MOAN_31,SND_SS_MOAN_32,SND_SS_MOAN_33,SND_SS_MOAN_34,SND_SS_MOAN_35,SND_SS_MOAN_36,SND_SS_MOAN_37,SND_SS_MOAN_38,SND_SS_MOAN_39,SND_SS_MOAN_40,SND_SS_MOAN_41,SND_SS_MOAN_42,SND_SS_MOAN_43,SND_SS_MOAN_44,SND_SS_MOAN_45,SND_SS_MOAN_46,SND_SS_MOAN_47,SND_SS_MOAN_48,SND_SS_MOAN_49,SND_SS_MOAN_50,SND_SS_MOAN_51,SND_SS_MOAN_52,SND_SS_MOAN_53,SND_SS_MOAN_54,SND_SS_MOAN_55,SND_SS_MOAN_56,SND_SS_MOAN_57,SND_SS_MOAN_58,SND_BED_THUMPS,SND_BED_BREAK,SND_VASE_ROCK,SND_VASE_STABLE,SND_VASE_CRASH
1|ATHN02A.WAD|SBK_Athn02A|blk|18|187684|SND_OCEANAMB_LP,SND_DISTANTSURFAMB_LP,SND_FLIESBUZZ_LP,SND_LAPPINGWAT_LP,SND_BOATCREAK_LP,SND_WATERFALL_LP,SND_BEHIND_FALLS_LP,SND_ROPECREAK_LP,SND_ELEVATOR_LP,SND_ELEVATOR_STOP,SND_MI_A02MI03,SND_MI_A02MI04,SND_MI_DOCKING,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_M_ATH2C1_4,SND_M_ATH2C2_2,SND_M_ATH2Q3_2,SND_DOCKRUBS_LP,SND_M_ATH2Q9_2,SND_M_ATH2E32_2,SND_M_ATH2E1_2
1|ATHN02B.WAD|SBK_Athn02B|blk|26|189832|SND_CLIFFTOPAMB_LP,SND_DISTANTSURFAMB_LP,SND_INDOORAMB_LP,SND_FLIESBUZZ_LP,SND_ELEVATOR_LP,SND_ELEVATOR_STOP,SND_BALISTA_COCK_LP,SND_BALISTA_COCKED,SND_BALLISTA_FIRE,SND_BOLT_ZIPIN,SND_BOLT_HITWALL,SND_FABRICFLAP_LP,SND_METLIFTGATE_LP,SND_METLIFTDOOR_GRAB,SND_METLIFTDOOR_STOP,SND_BALLISTA2_FIRE,SND_LADDERPUSH_LP,SND_LADDER_STOP,SND_STATUE_PUSH_LP,SND_COLUMNBREAK,SND_HL_A02HL07,SND_HL_A02HL09,SND_M_ATH2C3_2,SND_M_ATH2E1_2,SND_M_ATH2Q4_2,SND_M_ATH2Q2_2,SND_STATUEWHOOSH,SND_STATUEHIT,SND_STRAINVOC,SND_PUSHGRUNTVOC,SND_M_ATH2C4_2,SND_M_ATH2Q5_2,SND_M_ATH2C5_2,SND_M_ATH2E3_2,SND_M_ATH2C9_2,SND_M_ATH2C0_2,SND_M_ATH2C8_4,SND_M_ATH2Q7_2,SND_M_ATH2E2_2
1|ATHN02C.WAD|SBK_Athn02C|blk|32|206188|SND_INDOORAMB_LP,SND_CLIFFTOPAMB_LP,SND_OUTDOORAMB_LP,SND_BALISTA_COCK_LP,SND_BALISTA_COCKED,SND_BALLISTA_FIRE,SND_BOLT_ZIPIN,SND_BOLT_HITWALL,SND_BOLT_HITDOORS,SND_PLATFORM_LP,SND_METALGRIND_LP1,SND_METALGRIND_LP2,SND_STONEDOOR_LOOP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_MINOTAUR_HITDOOR,SND_BOLTFLY_ZOOM,SND_WOODCRATE_SHATTER,SND_WOODCRATE_HITGROUND,SND_FLIESBUZZ_LP,SND_M_ATH2C4_2,SND_M_ATH2C6_2,SND_M_ATH2C5_2,SND_M_ATH2E1_2,SND_M_ATH2Q1_2,SND_M_ATH2Q5_2,SND_RELOAD,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_ATH2Q6_2,SND_PILLARSLAM,SND_WINDWHISTLES_LOOP,SND_M_ATH2Q7_2,SND_M_ATH2E2_2,SND_M_ATH2E3_2,SND_M_ATH2Q8_2,SND_M_ATH2C0_2
1|ATHN02D.WAD|SBK_Athn02D|blk|11|177480|SND_INDOORAMB_LP,SND_GODDOOR_LP,SND_MI_A02MI98,SND_MI_A02MI99,SND_M_AQMAGC_Q,SND_MED_CLAWSTR_WINDUP,SND_MED_EMERGE,SND_MED_EYEBEAM_FINISH,SND_MED_EYEBEAM_WINDUP,SND_MED_HEADRIP_SHRIEK,SND_MED_SHATTERSHRIEK
1|ATHN03A.WAD|SBK_Athn03A|blk|24|204156|SND_OUTDOORAMB_LP,SND_OUTDOOR8AMB_LP,SND_OUTDOOR5AMB_LP,SND_SANDSTORMAMB_LP,SND_EXPLOSION,SND_STONEPEDESTAL_LP,SND_METALGATE_LP,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_SEWERGRATE,SND_FIREBALL,SND_CRASHDEBRIS,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_GATEBASH,SND_DOORSMASH,SND_MALESCREAM,SND_FEMALE_SCREAM,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_FEMALEVO_GETHIT,SND_FEMALEVO_DIE,SND_M_ATH3Q1_2,SND_M_ATH3C1_2,SND_M_ATH3Q2_2,SND_M_ATH3C2_2,SND_M_ATH3E1_2,SND_GATETRAP,SND_HL_A03HL01A,SND_HL_A03HL01B,SND_HL_A03HL01C,SND_HL_A03HL01D,SND_HL_A03HL01E,SND_HL_A03HL01F,SND_HL_A03HL01G,SND_ARES_STOMP,SND_FIREBALL_SPEC,SND_MALEVO_GETHIT_CS,SND_FEMALEVO_GETHIT_CS
1|ATHN03AA.WAD|SBK_Athn03AA|blk|19|113668|SND_INDOORAMB_LP,SND_OUTDOORAMB_LP,SND_OUTDOOR8AMB_LP,SND_M_ATH3Q1_2,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_BIGFLAP_LP,SND_HL_A03HL01A,SND_HL_A03HL01B,SND_HL_A03HL01D,SND_HL_A03HL01C,SND_HL_A03HL01E,SND_HL_A03HL01F,SND_HL_A03HL01G,SND_ARES_STOMP,SND_FIREBALL_SPEC
1|ATHN03C.WAD|SBK_Athn03C|blk|19|203064|SND_OUTDOOR9AMB_LP,SND_OUTDOOR5AMB_LP,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_EXPLOSION,SND_CRASHDEBRIS,SND_FIREBALL,SND_WOODDOORBREAK,SND_GATEBASH,SND_DOORSMASH,SND_MALESCREAM,SND_FEMALE_SCREAM,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_FEMALEVO_GETHIT,SND_FEMALEVO_DIE,SND_M_ATH3C2_2,SND_SMALL_WOODBREAK,SND_M_ATH3Q3_2,SND_SHAKE_BIG,SND_RUMBLE_BIG,SND_M_ATH3Q5_2,SND_HL_A03HL01A,SND_HL_A03HL01B,SND_HL_A03HL01C,SND_HL_A03HL01D,SND_HL_A03HL01E,SND_HL_A03HL01F,SND_HL_A03HL01G,SND_ARES_STOMP,SND_FIREBALL_SPEC,SND_MALEVO_GETHIT_CS,SND_FEMALEVO_GETHIT_CS
1|ATHN03D.WAD|SBK_Athn03D|blk|20|175704|SND_OUTDOORAMB_LP,SND_OUTDOOR8AMB_LP,SND_SEWERAMB_LP,SND_TEMPLEAMB_LP,SND_STAIRCASE,SND_M_ATH3Q3_2,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_MI_A06MI02,SND_BIGFLAP_LP,SND_M_SEW2Q6_2,SND_ARES_STOMP,SND_FIREBALL_SPEC,SND_HL_A03HL01A,SND_HL_A03HL01B,SND_HL_A03HL01C,SND_HL_A03HL01D,SND_HL_A03HL01E,SND_HL_A03HL01F,SND_HL_A03HL01G
1|ATHN03E.WAD|SBK_Athn03E|blk|14|172352|SND_OUTDOORAMB_LP,SND_OUTDOOR8AMB_LP,SND_OUTDOOR5AMB_LP,SND_SANDSTORMAMB_LP,SND_STONEPEDESTAL_LP,SND_METALGATE_LP,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_SEWERGRATE,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_GATEBASH,SND_DOORSMASH,SND_M_ATH3Q3_2,SND_ARES_STOMP,SND_FIREBALL_SPEC,SND_HL_A03HL01A,SND_HL_A03HL01B,SND_HL_A03HL01C,SND_HL_A03HL01D,SND_HL_A03HL01E,SND_HL_A03HL01F,SND_HL_A03HL01G
1|ATHN04A.WAD|SBK_Athn04A|blk|25|188784|SND_OUTDOOR9AMB_LP,SND_OUTDOOR5AMB_LP,SND_INSIDEAMB_LP,SND_UNDERWATAMB_LP,SND_FIREBALL,SND_EXPLOSION,SND_ELEVATOR_STOP,SND_PEDESTAL_LP,SND_BRIDGE_COLLAPSE,SND_STATUEFALL,SND_STATUE_BOUNCE,SND_KEY_PICKUP,SND_FOOTSTEP_METAL,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTHATCH_GRAB,SND_LIFTHATCH_STOP,SND_DOORSMASH,SND_M_ATH4C2_4,SND_M_ATH4C1_2,SND_M_ATH4E1_2,SND_M_ATH4E2_2,SND_MALESCREAM,SND_FEMALE_SCREAM,SND_UNLOCKDOOR,SND_HL_A04HL04,SND_HL_A04HL08,SND_HL_A04HL11,SND_MALEVO_GETHIT,SND_MALEVO_DIE,SND_FEMALEVO_GETHIT,SND_FEMALEVO_DIE,SND_M_ATH4Q1_2,SND_M_ATH4Q4_2,SND_M_ATH5E2_2,SND_M_ATH5C7_2,SND_M_ATH4Q7_2,SND_MALEVO_GETHIT_CS,SND_FEMALEVO_GETHIT_CS
1|ATHN04B.WAD|SBK_Athn04B|blk|16|72352|SND_OUTDOOR5AMB_LP,SND_INSIDEAMB_LP,SND_SWORDHIT_BUSH,SND_CHASEGIRL,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_DOORSMASH,SND_HL_A04MI01,SND_HL_A04MI02,SND_MI_A04MI06,SND_M_ATH4Q1_2,SND_M_ATH4Q4_2,SND_M_ATH4C2_4,SND_M_ATH4C1_2,SND_M_ATH4E1_2,SND_M_ATH4E2_2
1|ATHN04C.WAD|SBK_Athn04C|blk|26|200772|SND_OUTDOOR5AMB_LP,SND_INSIDEAMB_LP,SND_OUTDOOR6AMB_LP,SND_CEILING_COLLAPSE,SND_DRIPS,SND_HL_A04HL10,SND_M_ATH4Q4_2,SND_HITSHIELD,SND_BLADEBLOCK,SND_LIFTGATE_GRAB,SND_LIFTGATE_LP,SND_LIFTGATE_STOP
1|ATHN05A.WAD|SBK_Athn05A|blk|17|203016|SND_OUTDOOR6AMB_LP,SND_INSIDEAMB_LP,SND_FIREBALL,SND_EXPLOSION,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_HL_A05HL04,SND_HL_A05HL09,SND_HL_A05HL11,SND_BREAKABLE_DOOR,SND_EXPLODEBRIS,SND_M_ATH5Q1_2,SND_M_ATH5C1_2,SND_M_ATH5Q2_2,SND_ARES_STOMP,SND_ARES_SWING,SND_ARES_SMASH,SND_ARESMOVES1,SND_ARESMOVES2,SND_ARES_FS,SND_HL_A05HL17,SND_M_ATH5C5_2,SND_A5FIGHTAMB_LP,SND_M_ATH5E3_2,SND_EXPLOSION_BIG
1|ATHN05AA.WAD|SBK_Athn05AA|blk|1|60200|SND_M_ATH5Q1_2,SND_M_ATH5C1_2,SND_M_ATH5Q2_2,SND_HL_A05HL18
1|ATHN05B.WAD|SBK_Athn05B|blk|22|198760|SND_OUTDOOR6AMB_LP,SND_INSIDEAMB_LP,SND_FIREBALL,SND_EXPLOSION,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_METALGATE_LP,SND_BIGSTONEDOOR_LP,SND_BALISTA_COCK_LP,SND_BALISTA_COCKED,SND_BALLISTA_FIRE,SND_BALLISTAROLL_LP,SND_DOORKICK,SND_DOORSMASH,SND_ARMSMOVE_UP,SND_ARMSMOVE_DOWN,SND_ARMSLOCK_DOWN,SND_ARMSLOCK_UP,SND_BOLT_HITWALL,SND_RELOAD,SND_M_ATH5E1_2,SND_M_ATH5C2_2,SND_M_ATH5C4_2,SND_M_ATH5Q3_2,SND_GODDOOR_LP,SND_M_AQMAGC_Q,SND_M_ATH5C5_2,SND_M_ATH5C6_2,SND_M_ATH5Q6_2,SND_MI_A05MI90,SND_M_ATH5E2_2,SND_BALLISTA_CLUNK
1|ATHN05BB.WAD|SBK_Athn05BB|blk|11|170104|SND_OUTDOORAMB_LP,SND_INSIDEAMB_LP,SND_METALGATE_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_BIGSTONEDOOR_LP,SND_LADDERMOVE_LP,SND_BOLT_HITDOORS,SND_BREAKABLE_DOOR,SND_GODDOOR_OFF,SND_M_AQMAGC_Q,SND_M_ATH5E1_2,SND_M_ATH5C2_2,SND_M_ATH5Q3_2,SND_M_ATH5Q4_2
1|ATHN05C.WAD|SBK_Athn05C|blk|10|197576|SND_OUTDOOR6AMB_LP,SND_INSIDEAMB_LP,SND_FIREBALL,SND_EXPLOSION,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_EXPLODEBRIS,SND_MED_EXPLO,SND_DOORKICK,SND_DOORSMASH,SND_M_ATH5C4_2,SND_M_ATH5Q5_2,SND_MI_A05MI99,SND_M_ATH5C2_2,SND_M_ATH5C6_2,SND_M_ATH5E1_2,SND_M_ATH5Q3_2,SND_MALEVO_DIE,SND_MENSCREAM,SND_BRIDGERAISE,SND_M_ATH5E2_2,SND_BRIDGE_KICK,SND_M_ATH5Q7_2,SND_M_ATH5E3_2
1|ATHN05D.WAD|SBK_Athn05D|blk|4|78332|SND_INSIDEAMB_LP,SND_ELEVATOR_LP,SND_PEDESTAL_LP,SND_M_ATH5C4_2,SND_M_ATH5Q5_2,SND_M_ATH4Q9_2,SND_M_ATH5E2_2,SND_M_ATH6Q5_2,SND_M_ATH5C7_2
1|ATHN06A.WAD|SBK_Athn06A|blk|13|176332|SND_OUTDOOR2AMB_LP,SND_OUTDOOR5AMB_LP,SND_TEMPLEAMB_LP,SND_FOUNTAIN_SM1_LP,SND_FOUNTAIN_SM2_LP,SND_MI_A06MI01,SND_MI_A06MI01A,SND_HL_A06HL01,SND_SHOVEL_TOSS,SND_SHOVEL_DIG,SND_BIG_FOUNTAIN_LP,SND_FOLIAGE_LP,SND_M_ATH6C1_2,SND_M_ATH6Q1_2,SND_M_ATH6C3_2,SND_M_ATH6Q5_2
1|ATHN06B.WAD|SBK_Athn06B|blk|25|204000|SND_TEMPLEAMB_LP,SND_OUTSIDEAMB_LP,SND_OUTDOOR2AMB_LP,SND_STATUESLIDE_LOOP,SND_STATUEHITGROUND,SND_FOUNTAIN_LRG_LP,SND_FOUNTAIN_SM1_LP,SND_FOUNTAIN_SM2_LP,SND_BEAM_BREAKFALL,SND_BEAM_HITGROUND,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_STATUEWOBBLE,SND_WINDOWBREAK,SND_M_ATH6E1_2,SND_M_ATH6Q3_2,SND_M_ATH6Q2_2,SND_STATUE_SUCCESS,SND_M_ATH6C3_2,SND_M_ATH6E2_2,SND_SS_HARPYS,SND_M_ATH6E3_2,SND_M_ATH6Q6_2,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP
1|ATHN06C.WAD|SBK_Athn06C|blk|26|206668|SND_OUTSIDEAMB_LP,SND_OCEANAMB_LP,SND_TEMPLEAMB_LP,SND_ELEVATOR_LP,SND_WINDWHISTLES_LOOP,SND_WATERFALL_LP,SND_BIGFALLS_LP,SND_STATUESLIDE_LOOP,SND_BEAM_TOTTER_LP,SND_WHEEL1TURN,SND_WHEEL2TURN,SND_WHEEL3TURN,SND_STATUEHITGROUND,SND_STONEDOOR_LOOP,SND_MI_A06MI02,SND_MI_A06MI05,SND_HL_A06HL02,SND_HL_A06HL02A,SND_HL_A06HL02B,SND_HL_A06HL02C,SND_HL_A06HL02D,SND_HL_A06HL02E,SND_HL_A06HL02F,SND_HL_A06HL02G,SND_HL_A06HL03,SND_HL_A06SS04,SND_SS_A06SS02A,SND_HL_A06HL04,SND_FOUNTAIN_SM1_LP,SND_FOOTSTEP_GRASS,SND_FOOTSTEP_GRASSSTEP,SND_FOOTSTEP_GRASSWALK,SND_FOOTSTEP_GRASSRUN,SND_FOOTSTEP_GRASSLAND,SND_M_ATH6C2_2,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_ORACLE_SHORT,SND_ORACLE_LONG,SND_M_ATH6E2_2,SND_M_ATH6E3_2,SND_M_ATH6Q6_2
1|ATHN07.WAD|SBK_Athn07A|blk|12|142280|SND_OUTSIDEAMB_LP,SND_CLIFFSIDEAMB_LP,SND_OCEANAMB_LP,SND_SEWERAMB_LP,SND_FABRICFLAP_LP,SND_TIMEWARP_LP,SND_BIGFALLS_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_ATH7Q1_2,SND_M_ATH7Q2_2
1|ATHN07B.WAD|SBK_Athn07B|blk|12|142520|SND_OUTSIDEAMB_LP,SND_CLIFFSIDEAMB_LP,SND_OCEANAMB_LP,SND_SEWERAMB_LP,SND_FABRICFLAP_LP,SND_TIMEWARP_LP,SND_BIGFALLS_LP,SND_MI_A07MI01,SND_MI_A07MI07,SND_MI_A07MI08,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_ATH7Q1_2,SND_M_ATH7Q2_2
1|ATHN08A.WAD|SBK_Athn08A|blk|21|206184|SND_BIGHARBORAMB_LP,SND_ARESBAT_44,SND_ARESBAT_46,SND_ARESWILD_01A,SND_ARESWILD_03A,SND_ARESWILD_02C,SND_ARESWILD_04A,SND_ARESWILD_05A,SND_ARESWILD_06A,SND_ARESWILD_06B,SND_ARESWILD_07A,SND_ARESWILD_08A,SND_ARESWILD_09A,SND_ARESWILD_10A,SND_M_ATH8C1_2,SND_BIGFIRE_LP,SND_CROWD_PANIC_LP,SND_SWORDHIT_GIANTROCK,SND_FOOTSTEP_OCEAN,SND_FOOTSTEP_OCEANSTEP,SND_FOOTSTEP_OCEANWALK,SND_FOOTSTEP_OCEANRUN,SND_FOOTSTEP_OCEANLAND,SND_SWORDBLOCK_HIGH,SND_SWORDBLOCK_NORM,SND_CLAWSOPEN,SND_CRAPENDAGE_SLOW,SND_CRAPENDAGE_MEDIUM,SND_CRAPENDAGE_FAST,SND_BAR_WHOOSH_FAST,SND_BAR_WHOOSH_MED,SND_BAR_WHOOSH_SLOW,SND_BAR_SHLING_NORMAL,SND_BAR_SHLING_LOW,SND_PARRY_START,SND_PARRY_ATTACK,SND_PARRY_END,SND_OCEANAMB_LP,SND_HL_A08HL02A,SND_HL_A08HL02B,SND_ARESCOMBATVO,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S
1|ATHN08B.WAD|SBK_Athn08B|blk|17|183208|SND_M_ATH8C2_2,SND_STONEBREAK,SND_EVILK1AMB_LP,SND_EVILK2AMB_LP,SND_FAMILY_VOGETHIT,SND_FAMILY_VODIE,SND_QUAKELP,SND_FAMILY_TAUNT,SND_KRATOS,SND_HEALTHCHARGE,SND_HL_A08HL01A,SND_HL_A08HL01B,SND_FLOORBREAK,SND_ROOFBREAK,SND_BEAMBREAK
1|ATHN08C.WAD|SBK_Athn08C|blk|21|205944|SND_BIGHARBORAMB_LP,SND_ARESBAT_44,SND_ARESBAT_46,SND_ARESWILD_01A,SND_ARESWILD_02C,SND_ARESWILD_03A,SND_ARESWILD_04A,SND_ARESWILD_05A,SND_ARESWILD_06A,SND_ARESWILD_06B,SND_ARESWILD_07A,SND_ARESWILD_08A,SND_ARESWILD_09A,SND_ARESWILD_10A,SND_M_ATH8C3_2,SND_BIGFIRE_LP,SND_CROWD_PANIC_LP,SND_SWORDHIT_GIANTROCK,SND_FOOTSTEP_OCEAN,SND_FOOTSTEP_OCEANSTEP,SND_FOOTSTEP_OCEANWALK,SND_FOOTSTEP_OCEANRUN,SND_FOOTSTEP_OCEANLAND,SND_SWORDBLOCK_HIGH,SND_SWORDBLOCK_NORM,SND_CLAWSOPEN,SND_CRAPENDAGE_SLOW,SND_CRAPENDAGE_MEDIUM,SND_CRAPENDAGE_FAST,SND_BAR_WHOOSH_FAST,SND_BAR_WHOOSH_MED,SND_BAR_WHOOSH_SLOW,SND_BAR_SHLING_NORMAL,SND_BAR_SHLING_LOW,SND_PARRY_START,SND_PARRY_ATTACK,SND_PARRY_END,SND_ARESCOMBATVO,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S
1|ATRET01A.WAD|SBK_Atrt01A|blk|14|191748|SND_OUTDOOR5AMB_LP,SND_OUTDOOR2AMB_LP,SND_TEMPLEAMB_LP,SND_FOUNTAIN_SM1_LP,SND_FOUNTAIN_SM2_LP,SND_BIG_FOUNTAIN_LP,SND_FOLIAGE_LP,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_M_ATR1E1_2,SND_SHOVEL_TOSS,SND_SHOVEL_DIG
1|ATRET01B.WAD|SBK_Atrt01B|blk|26|201184|SND_TEMPLEAMB_LP,SND_OUTSIDEAMB_LP,SND_OUTDOOR2AMB_LP,SND_STATUESLIDE_LOOP,SND_STATUEHITGROUND,SND_FOUNTAIN_LRG_LP,SND_FOUNTAIN_SM1_LP,SND_FOUNTAIN_SM2_LP,SND_BEAM_BREAKFALL,SND_BEAM_HITGROUND,SND_BEAM_TOTTER_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_STATUEWOBBLE,SND_WINDOWBREAK,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_M_ATR1C1_2,SND_M_ATR1Q1_2,SND_M_ATR1E1_2
1|ATRET01C.WAD|SBK_Atrt01C|blk|20|200824|SND_OUTSIDEAMB_LP,SND_OCEANAMB_LP,SND_TEMPLEAMB_LP,SND_ELEVATOR_LP,SND_WINDWHISTLES_LOOP,SND_WATERFALL_LP,SND_BIGFALLS_LP,SND_STATUESLIDE_LOOP,SND_BEAM_TOTTER_LP,SND_WHEEL1TURN,SND_WHEEL2TURN,SND_WHEEL3TURN,SND_STATUEHITGROUND,SND_STONEDOOR_LOOP,SND_MI_A06MI03,SND_MI_A06MI04,SND_MI_A06MI05,SND_FOUNTAIN_SM1_LP,SND_FOOTSTEP_GRASS,SND_FOOTSTEP_GRASSSTEP,SND_FOOTSTEP_GRASSWALK,SND_FOOTSTEP_GRASSRUN,SND_FOOTSTEP_GRASSLAND,SND_M_ATH6C1_2,SND_M_ATH6E1_2,SND_M_ATH6C2_2,SND_M_ATH6Q1_2,SND_M_ATH6Q2_2,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_M_ATR1E1_2,SND_M_ATR1Q1_2
1|DEST01.WAD|SBK_Dest01|blk|10|203024|SND_SANDSTORMAMB_LP,SND_FOLIAGE_LP,SND_LONE_SHRUB,SND_LEAF_RUN_LP,SND_FABRICFLAP_LP,SND_STONEDOOR_LP,SND_DOORSPARKLE,SND_MI_D01MI01,SND_MI_D01MI02A,SND_MI_D01MI02B,SND_MI_D01MI02C,SND_MI_D01MI02D,SND_MI_D01MI02E,SND_MI_D01MI02F,SND_M_DES1C1_2,SND_M_DES1Q1_2,SND_M_DES1Q2_2,SND_M_DES1Q5_2,SND_M_DES1Q6_2,SND_M_DES1Q7_2,SND_MI_D01MI03,SND_SIRSCEAM,SND_SIRSUMMON,SND_SIRFIRESUM,SND_SIRLITSUM,SND_SIRSOUL,SND_SIRSCREAM_B_LP
1|DEST02.WAD|SBK_Dest02|blk|17|196856|SND_SANDSTORMAMB_LP,SND_EXTSANDSTORMAMB_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOOR2_GRAB,SND_LIFTDOOR2_LIFT_LP,SND_LIFTDOOR2_STOP,SND_CRUSHBOX,SND_CRUSHER_LP,SND_PLANKS_LP,SND_GEARS1_LP,SND_GEARS2_LP,SND_BOXPUSH_LP,SND_BOXLAND,SND_BOXSTOP,SND_CHAIN_LP,SND_M_DES2C1_2,SND_M_DES2E1_2,SND_CONVEYOR_BREAK
1|DEST03.WAD|SBK_Dest03|blk|18|202496|SND_SANDSTORMAMB_LP,SND_HOLLOWSTORMAMB_LP,SND_GIANTHORN1_LP,SND_GIANTHORN2_LP,SND_SANDWALL_LP,SND_WALLAWAY_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_M_DES3C1_2,SND_MI_D01MI02,SND_MI_D01MI05,SND_M_DES3Q1_2,SND_M_DES3Q2_2
1|HDES01A.WAD|SBK_Hade01A|blk|15|141112|SND_HADESAMB_LP,SND_SLITHER_LP,SND_BREATHING_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1E2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
1|HDES01B.WAD|SBK_Hade01B|blk|23|177892|SND_HADESAMB_LP,SND_FLESHLOGS_LP,SND_BLADEPASS,SND_SLITHER_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1Q2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
1|HDES01C.WAD|SBK_Hade01C|blk|20|201616|SND_HADESAMB_LP,SND_COLUMNSPIN1_LP,SND_HIDEBLADE,SND_BLADEPASS,SND_HADESWIND_LP,SND_HOVER_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1E1_2,SND_M_HAD1Q2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
1|HDES01D.WAD|SBK_Hade01D|blk|13|98456|SND_HADESAMB_LP,SND_SLITHER_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_FLESH,SND_M_HAD1C1_2,SND_M_HAD1C2_2,SND_M_HAD1E1_2,SND_M_HAD1E2_2,SND_M_HAD1Q2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
1|HDES01E.WAD|SBK_Hade01E|blk|16|192136|SND_HADESAMB_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1C2_2,SND_M_HAD1E2_2,SND_M_HAD1Q2_2,SND_PLATFORM_RISE,SND_SCREAMS,SND_M_HAD1Q3_2,SND_KRATOSFALLSCREAM
1|HDES01F.WAD|SBK_Hade01F|blk|13|98680|SND_HADESAMB_LP,SND_SLITHER_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1C2_2,SND_M_HAD1E1_2,SND_M_HAD1E2_2,SND_M_HAD1Q2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
1|HDES01G.WAD|SBK_Hade01G|blk|13|113568|SND_HADESAMB_LP,SND_TIMEWARP_LP,SND_FOOTSTEP_BONE,SND_FOOTSTEP_BONESTEP,SND_FOOTSTEP_BONEWALK,SND_FOOTSTEP_BONERUN,SND_FOOTSTEP_BONELAND,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_M_HAD1C1_2,SND_M_HAD1C2_2,SND_M_HAD1E1_2,SND_M_HAD1E2_2,SND_M_HAD1Q2_2,SND_SCREAMS,SND_KRATOSFALLSCREAM
1|OLYMP01.WAD|SBK_OLYM01|blk|20|191780|SND_CLIFFSAMB_LP,SND_TEMPLEAMB_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_DOOR_OPEN,SND_DOOR_CLOSE,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_OLY1E1_2,SND_TIMEWARP_LP,SND_M_OLY1Q1_2
1|OLYMP02.WAD|SBK_OLYM02|blk|23|139368|SND_CLIFFSAMB_LP,SND_TEMPLEAMB_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_DOOR_OPEN,SND_DOOR_CLOSE,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_STATUESMASH,SND_METALGATE_LP,SND_M_OLY1E1_2,SND_M_CREDITS1,SND_M_OLY1Q1_2
1|PAND00A.WAD|SBK_Pand00A|blk|20|202464|SND_SANDSTORM_LOOP,SND_FLYINGBIRD_LP,SND_HAWK,SND_BUZZARDSQUAK_LP,SND_HAWKLP,SND_FLIESBUZZ_LP,SND_FABRICFLAP_LP,SND_M_PAN0Q1_2,SND_M_PAN0C1_2,SND_M_PAN0Q2_2,SND_M_PAN0E1_2,SND_M_PAN0Q3_2,SND_BIRDDIE_VOC,SND_SIRSCEAM,SND_SIRSUMMON,SND_SIRFIRESUM,SND_SIRLITSUM,SND_SIRSCREAM_B_LP,SND_TITANSTEP
1|PAND00B.WAD|SBK_Pand00B|blk|33|205756|SND_SANDSTORM_LOOP,SND_STONEDOOR_LP,SND_ROCKSPULL_LP,SND_FLIESBUZZ_LP,SND_ROCKSPULL_STOP,SND_HAWKLP,SND_ROCKSPULL_SMALLSTOP,SND_SMALLDOOR1_LP,SND_SMALLDOOR2_LP,SND_FABRICFLAP_LP,SND_HL_P00HL01,SND_HL_P00HL02,SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_DRAG_FOOTSTEPS,SND_DRAGBODY_LP,SND_BODYDROP,SND_M_PAN0Q1_2,SND_M_PAN0C1_2,SND_M_PAN0Q2_2,SND_M_PAN0E1_2,SND_M_PAN0Q3_2,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_M_PAN0Q4_2,SND_M_PAN0Q5_2,SND_M_PAN0Q6_2,SND_M_PAN0C2_2
1|PAND00C.WAD|SBK_Pand00C|blk|14|204036|SND_STONEDOOR_LP,SND_SKULLDOOR2_LP,SND_PRESSUREPLATE_LP,SND_HEADTURN_FOWARDLP,SND_HEADTURN_BACKWARDLP,SND_HEADTURNSTOP,SND_EYEBEAM_LP,SND_RINGTURN_LP,SND_RINGTURN_STOP,SND_WATERDRAIN_LOOP,SND_AUGER_LP,SND_ELEVATOR_SMALL_LP,SND_ELEVATOR_BIG_LP,SND_ELEVATOR_BIG_STOP,SND_INSERTGEM,SND_RING1AMB_LP,SND_RING2AMB_LP,SND_RING3AMB_LP,SND_CRANKLOWER_LP,SND_EYEDOOR_LP,SND_EYEDOOR_STOP,SND_SUNDOOR1_LP,SND_SUNDOOR2_LP,SND_EYEDOORLEVER_LP,SND_BIGSTONEDOOR_ROLL_L,SND_RINGTURN_SMALLSTOP,SND_SUNDOOR_LIGHT,SND_SUNDOOR_LIGHT_LAST,SND_M_PAN0Q1_2,SND_M_PAN0C1_2,SND_M_PAN0Q2_2,SND_M_PAN0E1_2,SND_M_PAN0Q3_2,SND_M_PAN0Q4_2,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LP,SND_LIFTDOOR_STOP,SND_M_PAN0Q5_2,SND_M_PAN0Q6_2,SND_M_PAN0C2_2,SND_MI_P00MI99,SND_MI_P00NA02,SND_M_PAN3E1_2,SND_M_PAN4E1_2,SND_M_PAN3E3_2,SND_M_PAN0Q7_2,SND_M_PAN0C5_2,SND_INSERTGEM_UW,SND_M_PAN0Q8_2,SND_OUTSIDEAMB_LP
1|PAND00D.WAD|SBK_Pand00D|blk|18|200664|SND_SANDSTORM_LOOP,SND_CAVEAMB_LP,SND_STONEDOOR_LP,SND_CRUSHERSTART_FAST,SND_CRUSHERSTART_SLOW,SND_CRUSHERHIT_FAST,SND_CRUSHERHIT_SLOW,SND_PRESSUREPLATE_LP,SND_EYEBEAM_LP,SND_EYEDOOR_LP,SND_RING1AMB_LP,SND_EYEDOORAMB_LP,SND_CRUSHERSLIDE_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_BLUESPARKLE_LP,SND_REDSPARKLE_LP,SND_GREENSPARKLE_LP,SND_M_PAN0Q1_2,SND_M_PAN0C1_2,SND_M_PAN0Q2_2,SND_M_PAN0E1_2,SND_M_PAN0Q3_2,SND_M_PAN0Q4_2,SND_M_PAN0Q5_2,SND_M_PAN0Q6_2,SND_M_PAN0C2_2,SND_M_PAN4E1_2,SND_M_PAN1C9_2,SND_M_PAN1E3_2,SND_M_PAN1QD_2,SND_M_PAN3E3_2,SND_M_PAN0Q7_2,SND_M_PAN0C5_2,SND_GOLD_MAGIC,SND_M_PAN0Q8_2,SND_M_PAN0E3_2,SND_MUSEKEY,SND_MUSEDOOR_LP
1|PAND00E.WAD|SBK_Pand00E|blk|22|136136|SND_SANDSTORM_LOOP,SND_MI_P00MI01D,SND_MI_P00MI01E,SND_BONFIRE_LP,SND_HL_P00HL05,SND_FIRST_POKE,SND_SECOND_POKE,SND_SLOW_POKE,SND_RND_CRACKLE,SND_POLE_DIRT,SND_FOOTSTEP1,SND_FOOTSTEP2,SND_STOKE_GRUNTS,SND_BODYDROP2,SND_CHAIN_LP,SND_M_PAN3E3_2,SND_M_PAN0Q7_2
1|PAND01A.WAD|SBK_Pand01A|blk|14|196680|SND_GEARSPIN_LP,SND_BLOCKSLIDE_LOOP,SND_STONEPEDESTAL_LP,SND_ALTERSPIN_LP,SND_SHIELDDOOR_LP,SND_ROPELOWER_LOOP,SND_SHIELDINSERT,SND_ROPELOWER_STOP,SND_BATTLEAMB_LP,SND_CAVEAMB_LP,SND_WATERFALL_LP,SND_SOLDIERSHOT1,SND_SOLDIERSHOT2,SND_METALGATE_LP,SND_ZEUS_PICKUP,SND_SHIELDGLOW_LP,SND_PUSHBLOCKCLUNK,SND_GODDOOR_LP,SND_M_AQMAGC_Q,SND_M_PAN1C1_2,SND_M_PAN1C2_2,SND_M_PAN1C3_2,SND_M_PAN1E1_2,SND_M_PAN1Q1_2,SND_M_PAN1Q2_2,SND_M_PAN1Q3_2,SND_MI_P01MI99
1|PAND01B.WAD|SBK_Pand01B|blk|19|211520|SND_GEARSPIN_LP,SND_SAWBLADE_LP,SND_BIGWOODDOOR_OPEN,SND_BIGWOODDOOR_CLOSE,SND_STONEBARS_LP,SND_CONVEYOR_LP,SND_CRUSHERSTART_FAST,SND_CRUSHERSTART_SLOW,SND_CRUSHERHIT_FAST,SND_CRUSHERHIT_SLOW,SND_STONEPEDESTAL_LP,SND_CAVEAMB_LP,SND_SAWBLADE_EXT_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_M_PAN1C5_2,SND_M_PAN1Q3_2,SND_M_PAN1Q6_2,SND_M_PAN1C7_2,SND_M_PAN1C4_2,SND_M_PAN1Q4_2,SND_M_PAN1E2_2
1|PAND01BB.WAD|SBK_Pand01BB|blk|16|193992|SND_BIGLOGPOKER,SND_BOULDERRAISE_LOOP,SND_BOULDER_STOP,SND_CAVEAMB_LP,SND_ATLASAMB_LP,SND_BIGFIRE_LP,SND_COFFINSLAB_LP,SND_SANDSTORM_LOOP,SND_COFFINMOVE_LOOP,SND_BIGFIRE2_LP,SND_SLABBREAK,SND_HEADRIPOFF_LP,SND_HEADRIPOFF,SND_COFFINSLAB2_LP,SND_SKULLKEY_PUP,SND_M_PAN1C7_2,SND_M_PAN1E2_2,SND_M_PAN1E3_2,SND_M_PAN1Q6_2,SND_M_PAN1Q7_2,SND_M_PAN1Q8_2,SND_M_PAN1Q9_2,SND_M_PAN1QC_2,SND_M_PAN1C9_2,SND_M_PAN1QD_2,SND_M_AQMAGC_Q
1|PAND01C.WAD|SBK_Pand01C|blk|18|183508|SND_WINDWHISTLES_LOOP,SND_GEARSLOW_LP,SND_GEARMED_LP,SND_GEARHIGH_LP,SND_FLOORBUCKLE,SND_FLOOROPEN,SND_CHAINLOWER_LOOP,SND_TRAPROOMDOOR_LP,SND_SANDSTORM_LOOP,SND_CAVEAMB_LP,SND_CONVEYOR_LP,SND_FLOORRAISE_LP,SND_GEARSTOP,SND_FABRICFLAP_LP,SND_HANDGRAB_CHAIN,SND_SLIDECHAIN_LP,SND_HANDLE_PICKUP,SND_M_PAN1C5_2,SND_M_PAN1C6_2,SND_M_PAN1Q4_2,SND_M_PAN1Q5_2,SND_M_PAN1C8_2,SND_M_PAN1QA_2,SND_M_PAN1QB_2,SND_M_AQMAGC_Q
1|PAND01CC.WAD|SBK_Pand01CC|blk|5|150632|SND_SIRSCEAM,SND_SIRSUMMON,SND_SIRFIRESUM,SND_SIRLITSUM,SND_SIRSCREAM_B_LP
1|PAND01D.WAD|SBK_Pand01D|blk|8|139524|SND_STONEPEDESTAL_LP,SND_PUSHER_LP,SND_FIGHTMOVIE,SND_BATTLEAMB_LP,SND_CAVEAMB_LP,SND_FALLSCREAM,SND_PUSHER_STOP,SND_PUSHER_BACK_LP,SND_WATERFALL2_LP,SND_HADES_PICKUP,SND_SHIELDGLOW_LP,SND_M_PAN1C2_2,SND_M_PAN1Q1_2,SND_M_PAN1Q2_2,SND_M_PAN1QA_2,SND_M_PAN1QB_2,SND_M_PAN1C8_2,SND_M_AQMAGC_Q
1|PAND02A.WAD|SBK_Pand02A|blk|4|49084|SND_OUTSIDEAMB_LP,SND_BLOCKSLIDE_LOOP,SND_STONE_THUD,SND_M_PAN2C1_2,SND_M_PAN2Q1_2,SND_M_PAN2E1_2,SND_RING2AMB_LP
1|PAND02AA.WAD|SBK_Pand02AA|blk|16|195660|SND_SPINROOMDOOR_LOOP,SND_SPINROOM_LP,SND_OUTSIDEAMB_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_SPIKETRAP,SND_GRATECLOSE_LP,SND_LEVERUP_LP,SND_M_PAN2C1_2,SND_M_PAN2E1_2,SND_M_PAN2Q1_2,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND
1|PAND02B.WAD|SBK_Pand02B|blk|16|187184|SND_SPINROOMDOOR_LOOP,SND_STONEPEDESTAL_LP,SND_OUTSIDEAMB_LP,SND_WINDWHISTLES_LOOP,SND_STONEDOOR_LP,SND_DOORSLIDE_LOOP,SND_DOORFALL_WHOOSH,SND_DOORFALL_LAND,SND_CREAKING_LP,SND_M_PAN2C2_2,SND_M_PAN2E1_2,SND_M_PAN2Q5_2,SND_M_PAN2Q0_2,SND_TITAN_FS,SND_CHAIN_HIT,SND_CHAIN_LP,SND_CAGEHALLAMB_LP,SND_M_AQMAGC_Q
1|PAND02C.WAD|SBK_Pand02C|blk|16|199152|SND_FLMTHROWERS_L_LP,SND_FLMTHROWERS_R_LP,SND_FLMTHROW_LMOVE_LP,SND_FLMTHROW_RMOVE_LP,SND_STONEBUTTON_LP,SND_HANGINGCAGES_LP,SND_CAGEHITGROUND,SND_CAGEDRAG_LP,SND_STONEDOOR_LP,SND_FLAMES_L_LOOP,SND_FLAMES_R_LOOP,SND_CAGELOWER_LP,SND_CAGEHALLAMB_LP,SND_GENERALAMB_LP,SND_HANDLE_PICKUP,SND_CAGE_CLUNK,SND_HL_P02HL06,SND_HL_P02HL07,SND_HL_P02HL08,SND_HL_P02HL08A,SND_HL_P02HL09,SND_HL_P02HL09A,SND_HL_P02HL10,SND_HL_P02HL11,SND_HL_P02HL11A,SND_INTROMOANS,SND_M_PAN2C2_2,SND_M_PAN2C3_2,SND_M_PAN2E2_2,SND_M_PAN2Q2_2,SND_M_PAN2Q5_2,SND_SS_P02MP03,SND_M_PAN2E1_2,SND_OUTSIDEAMB_LP,SND_CAGEBANG,SND_PLATECLOSE,SND_FOUNTAIN_LP,SND_M_PAN2C1_2
1|PAND02D.WAD|SBK_Pand02D|blk|16|198912|SND_GENERALAMB_LP,SND_TRIDENTHOLD_LP,SND_TRIDENTLIFT_LP,SND_TRIDENTREMOVE,SND_GATE_LP,SND_M_PAN2C4_2,SND_M_PAN2E3_2,SND_M_PAN2E4_2,SND_M_PAN2Q4_2,SND_M_PAN2Q3_2,SND_DASHDOOR_BREAK,SND_BLOCKSLIDE_LP,SND_M_PAN2Q6_2,SND_UNDERWATAMB_LP,SND_M_AQMAGC_Q,SND_M_PAN2C1_2
1|PAND02DD.WAD|SBK_Pand02DD|blk|5|48088|SND_GENERALAMB_LP,SND_M_PAN2E3_2,SND_M_PAN2Q6_2,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_M_PAN2C4_2,SND_UNDERWATAMB_LP,SND_M_PAN2C1_2
1|PAND02F.WAD|SBK_Pand02F|blk|10|147768|SND_UNDERWATAMB_LP,SND_GENERALAMB_LP,SND_BUBBLES,SND_DIRTFALL,SND_FOUNTAIN_LP,SND_WATERFILL_LOOP,SND_M_PAN2C4_2,SND_M_PAN2E4_2,SND_DASHDOOR_BREAK,SND_M_PAN2E3_2,SND_M_PAN2C1_2
1|PAND02G.WAD|SBK_Pand02G|blk|14|182704|SND_UNDERWATAMB_LP,SND_GENERALAMB_LP,SND_BUBBLES,SND_DIRTFALL,SND_CONSTRICT_CLOSE_LP,SND_CONSTRICTOR_THUD,SND_BLADEROTATE_ONESHOT,SND_BLADEROTATE_LP,SND_CONSTRICTOR_STOP,SND_CONSTRICT_OPEN_LP,SND_LEVERWATERFALL_LP,SND_MINIWATERFALL_LP,SND_STONEDOOR_UW_LOOP,SND_SPIKEOUT,SND_M_PAN2C4_2,SND_M_PAN2E4_2,SND_M_PAN2E3_2,SND_M_PAN2C1_2
1|PAND02H.WAD|SBK_Pand02H|blk|13|156736|SND_UNDERWATAMB_LP,SND_GENERALAMB_LP,SND_BUBBLES,SND_DIRTFALL,SND_STONEDOOR_UW_LOOP,SND_PUSHERBLOCKS_LP,SND_STATUERAISE_LP,SND_WATERFALL_LOOP,SND_CHAIN_LP,SND_M_PAN2C4_2,SND_M_PAN2E4_2,SND_M_PAN2C1_2
1|PAND02I.WAD|SBK_Pand02I|blk|6|112240|SND_UNDERWATAMB_LP,SND_GENERALAMB_LP,SND_BUBBLES,SND_DIRTFALL,SND_STONEDOOR_UW_LOOP,SND_WATERFILL_LOOP,SND_STONECOL1_LOOP,SND_STONECOL1_UW_LOOP,SND_STONECOL2_LOOP,SND_STONECOL2_UW_LOOP,SND_STONECOL3_LOOP,SND_STONECOL3_UW_LOOP,SND_STONECOL4_LOOP,SND_STONECOL4_UW_LOOP,SND_WATERFALL1_LP,SND_WATERFALL2_LP,SND_WATERFALL3_LP,SND_WATERFALL4_LP,SND_UW_WATFALL1_LP,SND_UW_WATFALL2_LP,SND_UW_WATFALL3_LP,SND_UW_WATFALL4_LP,SND_CHAINLOOP_LP,SND_LEVERWATER_LP,SND_M_PAN2C4_2,SND_M_PAN2E4_2,SND_M_PAN2C2_2,SND_M_PAN2E5_2,SND_M_PAN2Q5_2,SND_M_PAN2Q7_2,SND_M_PAN2Q8_2,SND_M_PAN2C1_2
1|PAND03A.WAD|SBK_Pand03A|blk|17|198404|SND_LAVAFLOW_LP,SND_BIGFIRE_LP,SND_STONEPEDESTAL_LP,SND_UNDERWATER_LEVER,SND_STATUERAISE_LP,SND_STATLIGHTBEAM_LP,SND_HEADTURN_FOWARDLP,SND_HEADTURN_BACKWARDLP,SND_HEADTURNSTOP,SND_BLOCKSLIDE_LOOP,SND_LAVAAMB_LP,SND_RUMBLEAMB_LP,SND_STONEDOOR_LP,SND_SACRIFICE,SND_STONEBARS_LP,SND_RINGAPPEAR,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_PAN3E1_2,SND_M_PAN3E2_2,SND_M_PAN3E3_2,SND_M_PAN3C1_2,SND_M_PAN3Q1_2,SND_M_PAN3Q2_2,SND_M_PAN3Q3_2,SND_M_PAN3Q4_2,SND_GRATE_RISE_LP,SND_M_PAN3Q7_2,SND_M_PAN3Q9_2,SND_M_PAN3E7_2,SND_SACRIFICEPUME_LP,SND_M_PAN3C2_2,SND_M_PAN3C9_2,SND_LIGHTONESHOT
1|PAND03B.WAD|SBK_Pand03B|blk|20|201120|SND_LAVAFLOW_LP,SND_STONEPEDESTAL_LP,SND_STONEDOOR_LP,SND_FOUNTAIN_LP,SND_ELEVATORUP_LOOP,SND_ELEVATORDOWN_LOOP,SND_ELEVATOR_STOP,SND_BLOCKSLIDE_LOOP,SND_STONEBLOCK_LP,SND_STONEBLOCKHIT,SND_STONEBLOCKCHAIN_LP,SND_LAVAAMB_LP,SND_RUMBLEAMB_LP,SND_STONEDOOROPEN,SND_SPEARWHOOSH,SND_WOODBARS_LP,SND_STONEPUSH_LP,SND_STONE_FALL,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_M_PAN3E2_2,SND_M_PAN3C2_2,SND_M_PAN3Q2_2,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_PAN3E7_2
1|PAND03C.WAD|SBK_Pand03C|blk|19|193808|SND_LAVAFLOW_LP,SND_BOULDERROLL_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_GEARROOM_AMB_LP,SND_LAVAFALLS_LP,SND_BLDR_BOUNCE,SND_BWAYAMB_LP,SND_RUMBLEAMB_LP,SND_BIGFIRE_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_PAN3C3_2,SND_M_PAN3C4_2
1|PAND03D.WAD|SBK_Pand03D|blk|13|127104|SND_LAVAFLOW_LP,SND_AR_BIGGEARS_LP,SND_CAGEFORWARD_LP,SND_CAGEBACK_LP,SND_CAGE_STOP,SND_GONDOLA_LP,SND_AR_BIGGEARS_L_LP,SND_AR_BIGGEARS_R_LP,SND_LAVAAMB_LP,SND_RUMBLEAMB_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_M_PAN3E4_2,SND_M_PAN3C4_2,SND_M_PAN3Q5_2,SND_M_PAN3E7_2
1|PAND03E.WAD|SBK_Pand03E|blk|15|180148|SND_LAVAAMB_LP,SND_LAVAFLOW_LP,SND_BIGFIRE_LP,SND_SPINWHEEL_LP,SND_SPINBLADE_LP,SND_STATLIGHTBEAM_LP,SND_M_PAN3E4_2,SND_M_PAN3Q5_2,SND_LAVAFALL1_LP,SND_LAVAFALL2_LP,SND_ROPEZIP_LP,SND_M_PAN3Q8_2,SND_M_PAN3E7_2,SND_KRATOSFALLSCREAM,SND_STATUEBEAM_ON,SND_M_AQMAGC_Q
1|PAND03F.WAD|SBK_Pand03F|blk|13|153096|SND_LAVAHALLAMB_LP,SND_LAVAGRATE_LP,SND_STAIR_CRASH,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_WATERFALL_LP,SND_M_PAN3E5_2,SND_M_PAN3E4_2,SND_M_PAN3C5_2,SND_M_PAN3Q6_2,SND_MI_P03MI99,SND_POSDOOR_LP,SND_M_PAN3E1_2,SND_TURNWHEEL,SND_MB_LAVAAMB_LP,SND_SMALL_LAVAFALL1_LP,SND_SMALL_LAVAFALL2_LP,SND_M_PAN3E7_2,SND_M_PAN3C9_2,SND_LAVAAMB_LP
1|PAND03G.WAD|SBK_Pand03G|blk|32|204952|SND_MB_LAVAAMB_LP,SND_LAVAPOOL_LP,SND_LAVAGRATE_LP,SND_WATERFALL_LP,SND_SMALL_LAVAFALL1_LP,SND_SMALL_LAVAFALL2_LP,SND_BIG_LAVAFALL1_LP,SND_BIG_LAVAFALL2_LP,SND_BIG_LAVAFALL3_LP,SND_LOGROLL_LP,SND_LOG_FALL,SND_GATE_SLAM,SND_DOORCRASH,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_LOGSHATTER,SND_M_PAN3E5_2,SND_M_PAN3C5_2,SND_MB_FOOTSTEP,SND_MB_STEP_ARMOR,SND_MB_STEP_NOARMOR,SND_MB_JUMP_LAND,SND_M_PAN3C4_2,SND_BMIDOOR_THUD,SND_M_PAN3E7_2,SND_M_PAN3C6_2,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_M_PAN3C9_2
1|PAND03GG.WAD|SBK_Pand03GG|blk|11|201760|SND_MB_VOWIN,SND_MB_VOSTAGGER_ABC,SND_MB_VOSTAGGER_A,SND_MB_VOSTAGGER_B,SND_MB_VOSTAGGER_C,SND_MB_VOGENTAUNT,SND_MB_VOPLATFORMTAUNT,SND_MB_VOLOGHIT_ABC,SND_MB_VOLOGHIT_A,SND_MB_VOLOGHIT_B,SND_MB_VOLOGHIT_C,SND_MB_VOARMORBREAK,SND_MB_2AXEHITGROUND,SND_MB_2AXEHITMETAL,SND_MB_1AXEHITGROUND
1|PAND03H.WAD|SBK_Pand03H|blk|21|163800|SND_MB_LAVAAMB_LP,SND_LAVAAMB_LP,SND_WATERFALL_LP,SND_LAVAPOOL_LP,SND_LAVAGRATE_LP,SND_LEVER_PULLOUT_LP,SND_LEVER_SLIDEIN_LP,SND_LEVER_STOP,SND_SMALL_LAVAFALL1_LP,SND_SMALL_LAVAFALL2_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_COFFINSLAB2_LP,SND_SLABBREAK,SND_HEADRIPOFF_LP,SND_HEADRIPOFF,SND_BIG_LAVAFALL1_LP,SND_BIG_LAVAFALL2_LP,SND_BIG_LAVAFALL3_LP,SND_SKULLKEY_PUP,SND_M_PAN3E5_2,SND_M_PAN3C5_2,SND_M_PAN3E4_2,SND_M_PAN3E7_2,SND_M_PAN3QA_2,SND_M_PAN3C9_2,SND_M_AQMAGC_Q
1|PAND03I.WAD|SBK_Pand03I|blk|15|151096|SND_MB_LAVAAMB_LP,SND_LAVAAMB_LP,SND_WATERFALL_LP,SND_LAVAPOOL_LP,SND_LAVAGRATE_LP,SND_LEVER_PULLOUT_LP,SND_LEVER_SLIDEIN_LP,SND_LEVER_STOP,SND_SMALL_LAVAFALL1_LP,SND_SMALL_LAVAFALL2_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_BIG_LAVAFALL1_LP,SND_BIG_LAVAFALL2_LP,SND_BIG_LAVAFALL3_LP,SND_POSDOOR_LP,SND_MI_P03MI99,SND_M_PAN3E5_2,SND_M_PAN3Q6_2,SND_M_PAN3E1_2,SND_M_PAN3E7_2,SND_M_PAN3C9_2,SND_M_AQMAGC_Q
1|PAND03J.WAD|SBK_Pand03J|blk|23|180368|SND_MB_LAVAAMB_LP,SND_LAVAAMB_LP,SND_WATERFALL_LP,SND_LAVAPOOL_LP,SND_LAVAGRATE_LP,SND_SMALL_LAVAFALL1_LP,SND_SMALL_LAVAFALL2_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_BIG_LAVAFALL1_LP,SND_BIG_LAVAFALL2_LP,SND_LOGROLL_LP,SND_LOG_FALL,SND_DOORCRASH,SND_LEVER_PULLOUT_LP,SND_LEVER_SLIDEIN_LP,SND_LEVER_STOP,SND_M_PAN3E1_2,SND_M_PAN3Q6_2,SND_M_PAN3Q1_2,SND_M_PAN3E2_2,SND_M_PAN3E7_2,SND_M_PAN3C9_2,SND_LOGSHATTER
1|PAND04AA.WAD|SBK_Pand04AA|blk|9|134904|SND_CLIFFSAMB_LP,SND_HANDS_LP,SND_HANDS_SHIFT,SND_WINDWHISTLES_LOOP,SND_ELEVATOR_BIG_LP,SND_ELEVATOR_BIG_STOP,SND_MI_P00MI98,SND_M_PAN4C1_2,SND_M_PAN4E1_2,SND_M_PAN4Q1_2,SND_M_PAN4Q2_2,SND_M_PAN4QE_2,SND_M_PAN4C2_2,SND_M_PAN4C9_2,SND_M_PAN4QZ_2
1|PAND04C.WAD|SBK_Pand04C|blk|19|202468|SND_ELEVATOR_LP,SND_ELEVATOR_STOP,SND_BIRDS_LOOP,SND_WINDWHISTLES_LOOP,SND_CLIFFS2AMB_LP,SND_CAVERN1AMB_LP,SND_STONEPEDESTAL_LP,SND_DOORSLIDE_LOOP,SND_DOORSLIDE_STOP,SND_WOODLIFTDOOR_LP,SND_WOODLIFTDOOR_GRAB,SND_WOODLIFTDOOR_STOP,SND_BLOCKLOWER_LP,SND_WOODBARS_LP,SND_WOODGATE_LP,SND_SPIKETRAP,SND_SPIKE_DOWN,SND_PUSHBLOCK_LP,SND_BLOCK_CLUNK,SND_BLOCKSHATTER,SND_NECKLACE,SND_M_PAN4C1_2,SND_M_PAN4C3_2,SND_M_PAN4C5_2,SND_M_PAN4C6_2,SND_M_PAN4E3_2,SND_M_PAN4Q1_2,SND_M_PAN4Q2_2,SND_M_PAN4Q3_2,SND_GEARSLOW_LP,SND_GEARMED_LP,SND_GEARHIGH_LP,SND_M_PAN4Q4_2,SND_M_PAN4Q5_2,SND_M_PAN4C2_2,SND_M_PAN4E6_2,SND_CLIFFSAMB_LP,SND_M_ATH1E5_2,SND_M_PAN4E4_2,SND_M_AQMAGC_Q
1|PAND04D.WAD|SBK_Pand04D|blk|5|85552|SND_PLATFORMSPIN_LP,SND_CLIFFS2AMB_LP,SND_PLATFORM_STOP,SND_PLATFORM_START,SND_PLATFORM2SPIN_LP,SND_PLATFORM2_STOP,SND_PLATFORM2_START,SND_CAVERN2AMB_LP,SND_M_PAN4C1_2,SND_M_PAN4E2_2,SND_M_PAN4E4_2,SND_M_PAN4Q2_2,SND_M_ATH1E5_2
1|PAND04E.WAD|SBK_Pand04E|blk|21|203076|SND_CAVERN2AMB_LP,SND_PUZZLEROOMAMB_LP,SND_CLIFFS2AMB_LP,SND_BIRDS_LOOP,SND_WINDWHISTLES_LOOP,SND_ROPEZIP_LP,SND_WATERFALL_LOOP,SND_DISTWATERFALL_LOOP,SND_BRIDGE1_LP,SND_BRIDGE2_LP,SND_BRIDGE3_LP,SND_BRIDGE4_LP,SND_BRIDGE1_LOCK,SND_BRIDGE2_LOCK,SND_BRIDGE3_LOCK,SND_BRIDGE4_LOCK,SND_M_PAN4C1_2,SND_M_PAN4C4_2,SND_M_PAN4E4_2,SND_M_PAN4E5_2,SND_M_PAN4Q2_2,SND_M_PAN4Q5_2,SND_M_PAN4E2_2,SND_DISCSPIN_LP,SND_DISC_LOCK,SND_M_PAN4C8_2,SND_M_PAN4QJ_2,SND_M_PAN4E6_2,SND_M_PAN4QG_2,SND_M_PAN4QH_2,SND_M_PAN4QI_2,SND_M_PAN4C6_2,SND_M_PAN4QK_2,SND_M_AQMAGC_Q,SND_M_ATH1E5_2
1|PAND04EE.WAD|SBK_Pand04EE|blk|18|200636|SND_CAVERN1AMB_LP,SND_PUZZLEROOMAMB_LP,SND_DOORSLIDE_LOOP,SND_STONEBARS_LP,SND_BIGBLOCK_LP,SND_MEDBLOCK_LP,SND_SMALLBLOCK_LP,SND_BLOCK_CLUNK,SND_NECKLACE,SND_FLAMEJETS,SND_ALTERLOWER_LP,SND_PUZZLEDOOR_LP,SND_STONESLOP,SND_M_PAN4C1_2,SND_M_PAN4C4_2,SND_M_PAN4E5_2,SND_M_PAN4Q0_2,SND_M_PAN4Q4_2,SND_M_PAN4Q7_2,SND_M_PAN4Q8_2,SND_DISCSPIN_LP,SND_DISC_LOCK,SND_LADDER_LOWER,SND_BLOCK_INSERT,SND_M_AQMAGC_Q
1|PAND04F.WAD|SBK_Pand04F|blk|12|154272|SND_BLADESBLOCKSAMB_LP,SND_CLIFFS2AMB_LP,SND_ELEVATOR_LP,SND_ELEVATOR_STOP,SND_GATECLOSE,SND_WINDWHISTLES_LOOP,SND_FABRICFLAP_LP,SND_M_PAN4E4_2,SND_M_PAN4E6_2
1|PAND04G.WAD|SBK_Pand04G|blk|17|201556|SND_WINDWHISTLEAMB_LP,SND_BLADESBLOCKSAMB_LP,SND_ARCHROOMAMB_LP,SND_OUTSIDEAMB_LP,SND_STONEPEDESTAL_LP,SND_ROPEBLADE_LP,SND_CRANETURN_LP,SND_LIFTGATE_GRAB,SND_LIFTGATE_LP,SND_LIFTGATE_STOP,SND_BLOCKLOWER_LP,SND_BLOCKRAISE_LP,SND_STATUESLIDE_LOOP,SND_STATUEHITGROUND,SND_DOOR1_LP,SND_DOOR1_STOP,SND_DOOR2_LP,SND_DOOR2_STOP,SND_DOOR3_LP,SND_DOOR3_STOP,SND_M_PAN4C7_2,SND_M_PAN4E6_2,SND_M_PAN4E7_2,SND_M_PAN4E8_2,SND_M_PAN4QA_2,SND_M_PAN4QB_2,SND_M_PAN4QC_2,SND_TIMER_LP,SND_TIMER_STOP,SND_M_PAN4QD_2,SND_SKULLHIT
1|PAND04H.WAD|SBK_Pand04H|blk|10|66904|SND_WINDWHISTLEAMB_LP,SND_FABRICFLAP_LP,SND_M_PAN4E8_2,SND_INSIDEAMB_LP,SND_ARCHROOMAMB_LP,SND_INSERT_SKULL,SND_HEADRIPOFF,SND_HEADRIPOFF_LP,SND_FLIESBUZZ_LP,SND_M_PAN4E7_2
1|PAND04IB.WAD|SBK_Pand04IB|blk|16|145564|SND_WINDWHISTLEAMB_LP,SND_INSIDEAMB_LP,SND_CAVERN2AMB_LP,SND_M_PAN4E8_2,SND_BARREL_LP,SND_PLATES_LP,SND_BUMPS_LP,SND_M_PAN4CZ_2
1|PAND04J.WAD|SBK_Pand04J|blk|21|199052|SND_OUTDOORAMB_LP,SND_INSIDEAMB_LP,SND_CAVERN2AMB_LP,SND_STORMAMB_LP,SND_BARREL_LP,SND_PLATES_LP,SND_BUMPS_LP,SND_M_PAN4C7_2,SND_M_PAN4QB_2,SND_M_PAN4QC_2,SND_M_PAN5Q5_2,SND_M_PAN5E1_2,SND_M_PAN4E8_2,SND_FLAME_WARN1,SND_FLAME_WARN2,SND_FLAMEBLAST,SND_DOOROPEN,SND_DOORCLOSE,SND_M_PAN4CZ_2
1|PAND05A.WAD|SBK_Pand05A|blk|28|224184|SND_CAVERN2AMB_LP,SND_STORMAMB_LP,SND_FABRICFLAP_LP,SND_BOX_OPEN,SND_ELEVATORDOWN_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_BOXPUSH_LP,SND_LEVERPULL_LP,SND_LEVERPULL_DONE,SND_M_PAN5E1_2,SND_M_PAN5Q1_2,SND_M_PAN5Q2_2,SND_M_PAN5Q3_2,SND_PBOX_LP,SND_M_PAN5Q5_2,SND_BOXHIT,SND_DOORKICK
1|PAND05B.WAD|SBK_Pand05B|blk|19|191056|SND_SANDSTORM_LOOP,SND_ELEVATORDOWN_LP,SND_ELEVATORUP_LP,SND_ELEVATOR_STOP,SND_SS_P05HL02,SND_SS_P05HL02A,SND_STONEDOOR_LP,SND_FOOTSTEP_MARBLE,SND_FOOTSTEP_MARBLESTEP,SND_FOOTSTEP_MARBLEWALK,SND_FOOTSTEP_MARBLERUN,SND_FOOTSTEP_MARBLELAND,SND_BOXPUSH_LP,SND_M_PAN5E1_2,SND_M_PAN5Q1_2,SND_M_PAN5Q2_2,SND_M_PAN5Q3_2,SND_PBOX_LP
1|R_A1A.WAD|SBK_A1A_Ares1A|blk|6|98856|SND_VOATTK_BUILDSHORT,SND_VOATTK_BUILDMED,SND_VOATTK_LONG,SND_ANGRYGROWL,SND_BAR2HITAXE_START,SND_BAR2HITAXE_END,SND_AXEUPPERCUT_START,SND_AXEUPPERCUT_END,SND_HAMMERATK_START,SND_HAMMERATK_END,SND_VOATTK_BUILDSHORT_A,SND_VOATTK_BUILDMED_A
1|R_A1A.WAD|a1a|vag|5|92484|AREBAT01,AREBAT02,AREBAT06,AREBAT34,AREBAT36
1|R_A1B.WAD|SBK_A1B_Ares1B|blk|6|88736|SND_VOATTK_BUILDLONG,SND_LABOREDBREATHING,SND_FIREBALLSPELLSTART,SND_FIREBALL,SND_MULTIBLADES_START,SND_MULTIBLADES_ATK,SND_ARESTELEPORT,SND_FIREBALL_BLOCK,SND_VOATTK_BUILDLONG_A,SND_HAMMERSWING_FAST,SND_HAMMERSWING_MED,SND_HAMMERSWING_SLOW,SND_VOSTRUGGLE_LP
1|R_A1B.WAD|a1b|vag|3|86556|AREBAT03,AREBAT04,AREBAT28
1|R_A1C.WAD|SBK_A1C_Ares1C|blk|5|108440|SND_VOATTK_SHORT,SND_VOATTK_MEDIUM,SND_HAMMER_WAVE,SND_HAMMERSHOVE_A,SND_HAMMERSHOVE_B,SND_HAMMERSHOVE_C,SND_VORTEXWEATHER,SND_VOGETHIT,SND_VOGETHIT_A,SND_VOATTK_SHORT_A,SND_VOATTK_MEDIUM_A
1|R_A1C.WAD|a1c|vag|9|61220|AREBAT07,AREBAT14,AREBAT15,AREBAT18,AREHIT08,AREHIT09,AREHIT12,AREHIT13,AREHIT19
1|R_A2A.WAD|SBK_A2A_Ares2A|blk|5|101848|SND_VOATTK_BUILDSHORT,SND_VOATTK_BUILDMED,SND_VOATTK_LONG,SND_ANGRYGROWL,SND_BAR2HITAXE_START,SND_BAR2HITAXE_END,SND_AXEUPPERCUT_START,SND_AXEUPPERCUT_END,SND_VOATTK_BUILDSHORT_A,SND_VOATTK_BUILDMED_A,SND_VOATTK_LONG_A,SND_SWORDSCRAPE_LP
1|R_A2A.WAD|a2a|vag|5|92484|AREBAT01,AREBAT02,AREBAT06,AREBAT34,AREBAT36
1|R_A2B.WAD|SBK_A2B_Ares2B|blk|6|108776|SND_VOATTK_BUILDLONG,SND_LABOREDBREATHING,SND_FIREBALLSPELLSTART,SND_FIREBALL,SND_MULTIBLADES_START,SND_MULTIBLADES_ATK,SND_ARESTELEPORT,SND_FIREBALL_BLOCK,SND_VOATTK_BUILDLONG_A,SND_HAMMERSWING_FAST,SND_HAMMERSWING_MED,SND_HAMMERSWING_SLOW,SND_VOSTRUGGLE_LP,SND_VORTEXWEATHER
1|R_A2B.WAD|a2b|vag|3|86556|AREBAT03,AREBAT04,AREBAT28
1|R_A2C.WAD|SBK_A2C_Ares2C|blk|5|101976|SND_VOATTK_SHORT,SND_VOATTK_MEDIUM,SND_MAGICPILLARS_A,SND_MAGICPILLARS_B,SND_VOGETHIT,SND_VOGETHIT_A,SND_SWARM_SHOT,SND_SWARM_LP,SND_SWARM_HIT,SND_SWORDPROJ_SHOT,SND_SWORDPROJ_LP,SND_SWORDPROJ_HIT,SND_VOATTK_SHORT_A,SND_VOATTK_MEDIUM_A,SND_SWARMBUILD_LP
1|R_A2C.WAD|a2c|vag|9|61220|AREBAT07,AREBAT14,AREBAT15,AREBAT18,AREHIT08,AREHIT09,AREHIT12,AREHIT13,AREHIT19
1|R_AB2.WAD|SBK_BM2_MinoBoss2|blk|7|110848|SND_MB_VOATKLONG,SND_MB_VOATKLONG_A,SND_MB_VENTSHOT,SND_MB_VENT1_LP,SND_MB_VENT2_LP,SND_MB_VENT3_LP,SND_MB_VENT4_LP,SND_MB_FIREBREATH,SND_MB_FIREPLUME,SND_MB_LOGHIT,SND_MB_FIREWAV,SND_MB_FIREWAV2
1|R_AB2.WAD|ab2|vag|3|49580|BMIATKL1,BMIATKL2,BMIATKL3
1|R_AB3.WAD|SBK_BM3_MinoBoss3|blk|7|91600|SND_MB_ARMORDAMAGE,SND_MB_PUNCHATTACK,SND_MB_GRABATTACK,SND_MB_HORNSATTACK,SND_MB_AXESWING_LOW,SND_MB_AXESWING_HIGH
1|R_AB4.WAD|SBK_BM4_MinoBoss4|blk|9|94752|SND_MB_CLAPATTACK,SND_MB_ARMORNOISE,SND_MB_CLAWSCRAPE,SND_MB_GROUNDSLAM,SND_MB_GROUNDRIP
1|R_AEV.WAD|aev|vag|13|72244|EVI_ATK1,EVI_ATK2,EVI_ATK3,EVI_ATK4,EVI_ATK5,EVI_ATK6,EVI_DIE1,EVI_DIE2,EVI_HIT1,EVI_HIT2,EVI_HIT3,EVI_HIT4,EVI_HIT5
1|R_AH2.WAD|SBK_AH2_HydraBabyV2|blk|7|111480|SND_BHB_GROWL,SND_BHB_WHOOSHHIGH,SND_BHB_WHOOSHMID,SND_BHB_WHOOSHLOW,SND_BHB_BREATH,SND_BHB_BREATHSCREAM_LP,SND_BHB_EMERGE_SCREAM,SND_BHB_TAUNT_SCREAM,SND_BHB_VOATTACK,SND_BHB_VOGETHIT,SND_BHB_FALL_SCREAM,SND_BHB_VOPINNED1,SND_BHB_HEAL_LP,SND_BHB_VOPINNED2,SND_BHB_PINNED_SCREAM
1|R_AH2.WAD|ah2|vag|12|100072|BHB_ATT1,BHB_ATT2,BHB_ATT3,BHB_ATT4,BHB_HIT1,BHB_HIT2,BHB_HIT3,BHB_HIT5,BHB_IDL1,BHB_IDL3,BHB_IDL5,BHB_IDL6
1|R_AH3.WAD|SBK_AH3_HydraBoss2|blk|3|89592|SND_BOSSSHORTSCREAM,SND_BHA_KILLSCREAM_1,SND_BHA_KILLSCREAM_2
1|R_AH3.WAD|ah3|vag|9|98308|BHA_ATK1,BHA_ATK2,BHA_ATK3,BHA_ATK4,BHA_HIT1,BHA_HIT2,BHA_HIT3,BHA_HIT4,BHA_KIL1
1|R_AHA.WAD|SBK_HydraBoss|blk|7|107492|SND_HYDBOSS_SCREAM,SND_HYD_WHOOSHHIGH,SND_HYD_WHOOSHMID,SND_HYD_WHOOSHLOW,SND_EYEGLOW,SND_HYDBOSS_SNORT,SND_HYDBOSS_TAUNT,SND_AHA_BREATH,SND_AHA_VOATTACK,SND_AHA_VOGETHIT,SND_AHA_VOKILLFAIL,SND_AHA_STUNBREATH
1|R_AHA.WAD|aha|vag|9|98308|BHA_ATK1,BHA_ATK2,BHA_ATK3,BHA_ATK4,BHA_HIT1,BHA_HIT2,BHA_HIT3,BHA_HIT4,BHA_KIL1
1|R_AHB.WAD|SBK_HydraBabyV|blk|7|111452|SND_BHB_GROWL,SND_BHB_WHOOSHHIGH,SND_BHB_WHOOSHMID,SND_BHB_WHOOSHLOW,SND_BHB_STRUGGLE_LP,SND_BHB_BREATH,SND_BHB_BREATHSCREAM_LP,SND_BHB_EMERGE_SCREAM,SND_BHB_TAUNT_SCREAM,SND_BHB_VOATTACK,SND_BHB_VOGETHIT,SND_BHB_VORETREAT,SND_BHB_MGWIN_SCREAM,SND_HL_A01HL07,SND_BREATH,SND_GROWL,SND_EMERGE_SCREAM,SND_VOATTACK
1|R_AHB.WAD|ahb|vag|11|97820|BHB_ATT1,BHB_ATT2,BHB_ATT3,BHB_ATT4,BHB_ATT5,BHB_HIT1,BHB_HIT2,BHB_HIT3,BHB_HIT4,BHB_HIT5,BHB_RET
1|R_AHH.WAD|SBK_HydraBabyH|blk|9|113216|SND_HYDBABH_BURSTIN,SND_HYDBABH_GROWL,SND_HYDBABH_WHOOSHTHICK,SND_HYDBABH_WHOOSHFAST,SND_HYDBABH_VOGETHIT,SND_HYDBABH_BREATH,SND_HYDBABH_DAZEBREATH,SND_HYDBABH_TAUNT,SND_EYEGLOW,SND_HYDBAB_BARK,SND_HYDBABH_VODAZED,SND_HYDBAB_GILLFLAP,SND_HL_HYDRA1,SND_HL_HYDRA2,SND_HYDBABH_GROWL_A,SND_HYDBARK_NODUCK
1|R_AHH.WAD|ahh|vag|9|99092|HH_ATK1,HH_ATK2,HH_ATK3,HH_ATK4,HH_ATK5,HH_HIT1,HH_HIT2,HH_HIT3,HH_HIT4
1|R_AM3.WAD|SBK_ME3_Medusa3|blk|13|114048|SND_MEDUSA_IDLE,SND_MEDUSA_MOVESLOW,SND_MEDUSA_MOVEREG,SND_MEDUSA_MOVEFAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_MEDUSA_VOATTACK,SND_MEDUSA_VOATTACK_A,SND_MEDUSA_VOGETHIT,SND_MEDUSA_VOGETHIT_A,SND_MEDUSA_VOGETHITB_A,SND_MEDUSA_VODIE,SND_MEDUSA_BODYFAL_SLAM,SND_MEDUSA_BODYFAL_HEV,SND_MEDUSA_BODYFAL_MED,SND_MEDUSA_BODYFAL_LIMB,SND_MEDUSA_BODYFAL_HEAD,SND_MEDUSA_EVADE,SND_MEDUSA_LAUGH,SND_MED_SNAKESTRIKE,SND_MED_CLAWSTRIKE,SND_MED_TAILSPIN,SND_MED_HEADRIPOFF,SND_HEADRIP,SND_MEDUSA_NAVCYCLE,SND_MEDUSA_NAVSOUND,SND_MEDUSA_MOVEPHASE
1|R_AM3.WAD|me3|vag|11|100316|MEDATK02,MEDATK04,MEDDIE01,MEDDIE02,MEDHIT01,MEDHIT02,MEDHIT03,MEDHIT04,MEDHIT05,MEDHITB1,MEDULAFF
1|R_AMI.WAD|SBK_BMI_MinoBoss|blk|9|110680|SND_MB_VOGETHIT,SND_MB_VOGETHIT_A,SND_MB_VOATKSHORT,SND_MB_VOATKSHORT_A,SND_MB_VOIDLE_NORMAL,SND_MB_VOIDLE_STUN,SND_MB_ARMORCRACK,SND_MB_VOVICTORY,SND_BMIBEHINDDOOR_LP
1|R_AMI.WAD|ami|vag|11|86652|BMI_HIT1,BMI_HIT2,BMI_HIT3,BMI_HIT4,BMI_HIT5,BMI_HIT6,BMIATKS1,BMIATKS2,BMIATKS3,BMIATKS4,BMIATKS5
1|R_CEA.WAD|SBK_CEA_Cerebus|blk|14|107944|SND_CERBUS_STEPLIGHT,SND_CERBUS_STEPHEAVY,SND_CERBUS_STEPLAND,SND_CERBUS_IDLESNARL,SND_PRETAUNTGROWL,SND_CERBUS_FIREBALL,SND_CERBUS_FIREBALL_LP,SND_CERBUS_VOATTACK,SND_CERBUS_VOATTACK_A,SND_CERBUS_VOATTACK_L,SND_CERBUS_VOGETHIT,SND_CERBUS_VOGETHIT_A,SND_CERBUS_VODIE,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CEA_FIREBALL_EXPLO,SND_CEA_BODYFALL_NORM,SND_CEA_BODYFALL_SLAM,SND_CEA_BODYFALL_LIGHT,SND_CERBUS_VOMIT,SND_CER_FIREBALL_BLOCK,SND_CEA_LEAPATKVO,SND_CERBUS_VOFIREATTK
1|R_CEA.WAD|cea|vag|10|98736|CER_TCA1,CER_TCA2,CER_TCA3,CER_TCA4,CER_TCAL,CER_DIE1,CER_TCH1,CER_TCH2,CER_TCH3,CER_TCH4
1|R_CEP.WAD|SBK_CEP_CerebPup|blk|13|112408|SND_CERPUP_STEPLIGHT,SND_CERPUP_STEPHEAVY,SND_CERPUP_STEPLAND,SND_SNARL,SND_BREATH,SND_TRANSFORM_A,SND_TRANSFORM_B,SND_FLIPATTK,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CERPUP_VOATTACK,SND_CERPUP_VOATTACK_A,SND_CERPUP_VOGETHIT,SND_CERPUP_VOGETHIT_A,SND_CERPUP_VODIE,SND_CERPUP_BARK,SND_CERPUP_HEADSTOMP,SND_CERPUP_VO_CATTACK,SND_CERPUP_VO_CATTACK_A,SND_CERPUP_VO_LATTACK,SND_CERPUP_VO_LATTACK_A
1|R_CEP.WAD|cep|vag|10|98448|CEP_CATK,CEP_LATK,CEP_TCA1,CEP_TCA3,CEP_TCD1,CEP_TCH1,CEP_TCH2,CEP_TCH3,CEP_TCH4,CEP_TRAN
1|R_CNM.WAD|SBK_CNM_Centaur1|blk|21|115112|SND_CENT_STEPLIGHT,SND_CENT_STEPHEAVY,SND_CENT_STEPLAND,SND_CENT_BODYFALL_HEAVY,SND_CENT_BODYFALL_MED,SND_CENT_BODYFALL_HEAD,SND_CENT_BODYFALL_LIMB,SND_CNM_BOWDRAW_FAST,SND_CNM_BOWDRAW_SLOW,SND_CNM_BOW_FIRE,SND_CNM_ARR_FLIGHT,SND_CNM_ARR_BLOCK,SND_CNM_ARR_HITFLESH,SND_CNM_ARR_HITWATER,SND_CNM_ARR_HITDIRT,SND_CNM_ARR_HITSTONE,SND_CNM_ARR_HITWOOD,SND_CNM_ARR_HITGEN,SND_CNM_BOW_FIRE_M,SND_CNM_ARR_FLIGHT_M,SND_CNM_ARR_BLOCK_M,SND_CNM_ARR_HITFLESH_M,SND_CNM_ARR_HITWATER_M,SND_CNM_ARR_HITDIRT_M,SND_CNM_ARR_HITSTONE_M,SND_CNM_ARR_HITWOOD_M,SND_CNM_ARR_HITGEN_M,SND_BOWBLOCKSWORD,SND_CNM_VOATTACK,SND_CNM_VOGETHIT,SND_CNM_TAUNTLAUGH,SND_CNM_VODIE,SND_CNM_VOATTACK_A,SND_CNM_VOGETHIT_A,SND_CNM_VODIE_EXT,SND_CNM_VOATTACKLONG_A,SND_CNM_SLICELEGSOFF,SND_SHOCKWAVE,SND_CENT_BODYFALL_SLAM,SND_CNM_DRAW_LP
1|R_CNM.WAD|cnm|vag|11|99404|CNMDIEN,CNMDIEX,CNMHIT1,CNMHIT2,CNMHIT3,CNMYELL1,CNMYELL2,CNMYELL3,CNMYELL4,CNMYELL5,CNMYELL7
1|R_CY2.WAD|SBK_CY2_Cyclops2|blk|16|114656|SND_CYCLOPS_STEPLIGHT,SND_CYCLOPS_STEPWALK,SND_CYCLOPS_STEPRUN,SND_CYCLOPS_IDLELOOP,SND_CYCLOPS_SWIPEW,SND_CYCLOPS_WHOOSH_F1,SND_CYCLOPS_WHOOSH_F2,SND_CYCLOPS_WHOOSH_M1,SND_CYCLOPS_WHOOSH_M2,SND_CYCLOPS_WHOOSH_S,SND_CYCLOPS_HITEYE,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CYCLOPS_BODYFALL,SND_CYCLOPS_VOATTACK,SND_CYCLOPS_VOGETHIT,SND_CYCLOPS_VOGETHITBIG,SND_CYCLOPS_VODIE,SND_CYCLOPS_VOSCREAM,SND_CYCLOPS_NOISE,SND_CYCLOPS_BUCKWHOOSH,SND_CYCLOPS_VOATTACK_A,SND_CYCLOPS_VOGETHIT_A,SND_CYCLOPS_VOGETHITB_A,SND_CYCLOPS_BFALL_KNEE,SND_CYL2_BALLWINDUP,SND_CYL2_BALLSPIN_LP,SND_CYL2_BALLSHOOT,SND_CYL2_BALLIMPACT,SND_CYL2_BALLPULL,SND_CYL2_BALLRELEASE,SND_CY2_BALLRETRACT,SND_CYL2_BALLGRAB,SND_CYL2_VO_SLAMWINDUP,SND_CYL2_VO_SLAM,SND_CYL2_VO_LUNGEWINDUP,SND_CYL2_VO_LUNGE
1|R_CY2.WAD|cy2|vag|11|98844|CY2LNG_A,CY2LUNGE,CY2SNORT,CY2TNT_2,CYCLATK1,CYCLATK2,CYCLDIE2,CYCLHIT1,CYCLHIT2,CYCLHIT3,CYCLHIT4
1|R_CY3.WAD|SBK_CY3_Cyclops3|blk|14|109176|SND_CYCLOPS_STEPLIGHT,SND_CYCLOPS_STEPWALK,SND_CYCLOPS_STEPRUN,SND_CYCLOPS_IDLELOOP,SND_CYCLOPS_SWIPEW,SND_CYCLOPS_GROUNDP,SND_CYCLOPS_FOOTSMASH,SND_CYCLOPS_WHOOSH_F1,SND_CYCLOPS_WHOOSH_F2,SND_CYCLOPS_WHOOSH_M1,SND_CYCLOPS_WHOOSH_M2,SND_CYCLOPS_WHOOSH_S,SND_CYCLOPS_HITEYE,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CYCLOPS_BODYFALL,SND_CYCLOPS_VOATTACK,SND_CYCLOPS_VOGETHIT,SND_CYCLOPS_VOGETHITBIG,SND_CYCLOPS_VODIE,SND_CYCLOPS_VOSCREAM,SND_CYCLOPS_NOISE,SND_CYCLOPS_BUCKWHOOSH,SND_CYCLOPS_VOATTACK_A,SND_CYCLOPS_VOGETHIT_A,SND_CYCLOPS_VOGETHITB_A,SND_CYCLOPS_BFALL_KNEE,SND_RAMSCREAM,SND_CYCLOPS_STEPSTOMP
1|R_CY3.WAD|cy3|vag|9|69204|CYCLATK1,CYCLATK2,CYCLATK3,CYCLATK4,CYCLDIE1,CYCLHIT1,CYCLHIT2,CYCLHIT3,CYCLHIT4
1|R_CYW.WAD|SBK_CYW_Cyclops1|blk|15|113656|SND_CYCLOPS_STEPLIGHT,SND_CYCLOPS_STEPWALK,SND_CYCLOPS_STEPRUN,SND_CYCLOPS_IDLELOOP,SND_CYCLOPS_SWIPEW,SND_CYCLOPS_GROUNDP,SND_CYCLOPS_FOOTSMASH,SND_CYCLOPS_WHOOSH_F1,SND_CYCLOPS_WHOOSH_F2,SND_CYCLOPS_WHOOSH_M1,SND_CYCLOPS_WHOOSH_M2,SND_CYCLOPS_WHOOSH_S,SND_CYCLOPS_HITEYE,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CYCLOPS_BODYFALL,SND_CYCLOPS_VOATTACK,SND_CYCLOPS_VOGETHIT,SND_CYCLOPS_VOGETHITBIG,SND_CYCLOPS_VODIE,SND_CYCLOPS_VOSCREAM,SND_CYCLOPS_NOISE,SND_CYCLOPS_BUCKWHOOSH,SND_CYCLOPS_VOATTACK_A,SND_CYCLOPS_VOGETHIT_A,SND_CYCLOPS_VOGETHITB_A,SND_CYCLOPS_BFALL_KNEE
1|R_CYW.WAD|cyw|vag|10|87456|CYCLATK1,CYCLATK2,CYCLATK3,CYCLATK4,CYCLDIE1,CYCLDIE2,CYCLHIT1,CYCLHIT2,CYCLHIT3,CYCLHIT4
1|R_HA2.WAD|SBK_HA2_Harpy2|blk|17|114096|SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_HARP_WHOOSH_S1,SND_HARP_WHOOSH_S2,SND_HARP_WHOOSH_M1,SND_HARP_WHOOSH_M2,SND_HARP_WHOOSH_F1,SND_HARP_WHOOSH_F2,SND_HARP_HITGROUND,SND_HARP_HITWALL,SND_HARP_SLAMGROUND,SND_HARP_WINGTEAR,SND_HARP_GRABHERO,SND_HARP_VOATTACK,SND_HARP_VOATTACK_A,SND_HARP_VOATTACKBIG_A,SND_HARP_VOGETHIT,SND_HARP_VOGETHIT_A,SND_HARP_VODIE,SND_HARP_VOTAUNT_A,SND_HARP_VOLAFF_A,SND_HARP_FIRESLAM,SND_HARP_FIRESLAM_PRE,SND_HARP_FIREATK_LP
1|R_HA2.WAD|ha2|vag|12|95704|HARPATK1,HARPATK2,HARPATK3,HARPATK4,HARPDIE1,HARPDIE2,HARPHIT1,HARPHIT2,HARPHIT3,HARPHIT4,HARPLAF2,HARPTNT1
1|R_HAF.WAD|SBK_HAF_HarpyF|blk|18|114408|SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_HARP_WHOOSH_S1,SND_HARP_WHOOSH_S2,SND_HARP_WHOOSH_M1,SND_HARP_WHOOSH_M2,SND_HARP_WHOOSH_F1,SND_HARP_WHOOSH_F2,SND_HARP_HITGROUND,SND_HARP_HITWALL,SND_HARP_SLAMGROUND,SND_HARP_WINGTEAR,SND_HARP_GRABHERO,SND_HARP_VOATTACK,SND_HARP_VOATTACK_A,SND_HARP_VOATTACKBIG_A,SND_HARP_VOGETHIT,SND_HARP_VOGETHIT_A,SND_HARP_VODIE,SND_HARP_VOTAUNT_A,SND_HARP_FIRESLAM,SND_HAF_FIRE_LP,SND_HARP_VOLAFF_A,SND_HARP_FIREATK_LP,SND_HARP_FIRESLAM_PRE
1|R_HAF.WAD|haf|vag|12|95704|HARPATK1,HARPATK2,HARPATK3,HARPATK4,HARPDIE1,HARPDIE2,HARPHIT1,HARPHIT2,HARPHIT3,HARPHIT4,HARPLAF2,HARPTNT1
1|R_HAR.WAD|SBK_HAR_Harpy1|blk|20|113508|SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_HARP_WHOOSH_S1,SND_HARP_WHOOSH_S2,SND_HARP_WHOOSH_M1,SND_HARP_WHOOSH_M2,SND_HARP_WHOOSH_F1,SND_HARP_WHOOSH_F2,SND_HARP_HITGROUND,SND_HARP_HITWALL,SND_HARP_SLAMGROUND,SND_HARP_WINGTEAR,SND_HARP_GRABHERO,SND_HARP_VOATTACK,SND_HARP_VOATTACK_A,SND_HARP_VOATTACKBIG_A,SND_HARP_VOGETHIT,SND_HARP_VOGETHIT_A,SND_HARP_VODIE,SND_HARP_VOTAUNT_A,SND_HARP_VOLAFF_A,SND_HL_A01HL04F,SND_HL_A01HL05F
1|R_HAR.WAD|har|vag|12|95704|HARPATK1,HARPATK2,HARPATK3,HARPATK4,HARPDIE1,HARPDIE2,HARPHIT1,HARPHIT2,HARPHIT3,HARPHIT4,HARPLAF2,HARPTNT1
1|R_ME2.WAD|SBK_ME2_Medusa2|blk|13|114048|SND_MEDUSA_IDLE,SND_MEDUSA_MOVESLOW,SND_MEDUSA_MOVEREG,SND_MEDUSA_MOVEFAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_MEDUSA_VOATTACK,SND_MEDUSA_VOATTACK_A,SND_MEDUSA_VOGETHIT,SND_MEDUSA_VOGETHIT_A,SND_MEDUSA_VOGETHITB_A,SND_MEDUSA_VODIE,SND_MEDUSA_BODYFAL_SLAM,SND_MEDUSA_BODYFAL_HEV,SND_MEDUSA_BODYFAL_MED,SND_MEDUSA_BODYFAL_LIMB,SND_MEDUSA_BODYFAL_HEAD,SND_MEDUSA_EVADE,SND_MEDUSA_LAUGH,SND_MED_SNAKESTRIKE,SND_MED_CLAWSTRIKE,SND_MED_TAILSPIN,SND_MED_HEADRIPOFF,SND_HEADRIP,SND_MEDUSA_NAVCYCLE,SND_MEDUSA_NAVSOUND,SND_MEDUSA_MOVEPHASE
1|R_ME2.WAD|me2|vag|11|100316|MEDATK02,MEDATK04,MEDDIE01,MEDDIE02,MEDHIT01,MEDHIT02,MEDHIT03,MEDHIT04,MEDHIT05,MEDHITB1,MEDULAFF
1|R_MEW.WAD|SBK_MEW_Medusa1|blk|13|114048|SND_MEDUSA_IDLE,SND_MEDUSA_MOVESLOW,SND_MEDUSA_MOVEREG,SND_MEDUSA_MOVEFAST,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_MEDUSA_VOATTACK,SND_MEDUSA_VOATTACK_A,SND_MEDUSA_VOGETHIT,SND_MEDUSA_VOGETHIT_A,SND_MEDUSA_VOGETHITB_A,SND_MEDUSA_VODIE,SND_MEDUSA_BODYFAL_SLAM,SND_MEDUSA_BODYFAL_HEV,SND_MEDUSA_BODYFAL_MED,SND_MEDUSA_BODYFAL_LIMB,SND_MEDUSA_BODYFAL_HEAD,SND_MEDUSA_EVADE,SND_MEDUSA_LAUGH,SND_MED_SNAKESTRIKE,SND_MED_CLAWSTRIKE,SND_MED_TAILSPIN,SND_MED_HEADRIPOFF,SND_HEADRIP,SND_MEDUSA_NAVCYCLE,SND_MEDUSA_NAVSOUND,SND_MEDUSA_MOVEPHASE
1|R_MEW.WAD|mew|vag|11|100316|MEDATK02,MEDATK04,MEDDIE01,MEDDIE02,MEDHIT01,MEDHIT02,MEDHIT03,MEDHIT04,MEDHIT05,MEDHITB1,MEDULAFF
1|R_MI2.WAD|SBK_MI2_Mntaur2|blk|20|114848|SND_MINO_STEPLIGHT,SND_MINO_STEPHEAVY,SND_MINO_STEPLAND,SND_MINO_BODYFALL_HEAVY,SND_MINO_BODYFALL_MED,SND_MINO_BODYFALL_LIMB,SND_MINO_SNORT,SND_MINO_VOATTACK,SND_MINO_VOATTACK_A,SND_MINO_VOGETHIT,SND_MINO_VOGETHIT_A,SND_MINO_VOGETHITBIG,SND_MINO_VOGETHITB_A,SND_MINO_VOTAUNT1,SND_MINO_VOTAUNT2,SND_MINO_VOTAUNT3,SND_MINO_VODIE,SND_MINO_VODIEBIG,SND_MINO_AXEDROP,SND_AXESWING_NORMAL,SND_AXESWING_SLOW,SND_AXESWING_MEDIUM,SND_AXESWING_FAST,SND_HAMMERHITGROUND,SND_MINO_AGRO_LP,SND_MINO_GROWL,SND_MINO_STRUGGLE_LP_A,SND_MINO_STRUGGLE_LP_B,SND_MIN_NAVSOUND_CYCLE,SND_MIN_HEADCUT_VO,SND_MINO_VOBRUTALDIE,SND_MINO_VODIEBIG2,SND_SHOCKWAVE,SND_HAMHITGROUND_SOFT
1|R_MI2.WAD|mi2|vag|10|100448|MINATK_2,MINATK_3,MINATK_4,MINDIE_1,MINDIEB1,MINHIT_1,MINHIT_2,MINHIT_3,MINHIT_4,MINHITB1
1|R_MI4.WAD|SBK_MI4_Mntaur4|blk|21|116096|SND_MINO_STEPLIGHT,SND_MINO_STEPHEAVY,SND_MINO_STEPLAND,SND_MINO_BODYFALL_HEAVY,SND_MINO_BODYFALL_MED,SND_MINO_BODYFALL_LIMB,SND_MINO_SNORT,SND_MINO_VOATTACK,SND_MINO_VOATTACK_A,SND_MINO_VOGETHIT,SND_MINO_VOGETHIT_A,SND_MINO_VOGETHITBIG,SND_MINO_VOGETHITB_A,SND_MINO_VOTAUNT1,SND_MINO_VOTAUNT3,SND_MINO_VODIE,SND_MINO_VODIEBIG,SND_MINO_AXEDROP,SND_AXESWING_NORMAL,SND_AXESWING_SLOW,SND_AXESWING_MEDIUM,SND_AXESWING_FAST,SND_AXEHITGROUND,SND_AXEPULLOUTGROUND,SND_MINO_AGRO_LP,SND_MINO_GROWL,SND_MINO_STRUGGLE_LP_A,SND_MINO_STRUGGLE_LP_B,SND_MIN_NAVSOUND_CYCLE,SND_MIN_HEADCUT_VO,SND_MINO_VOBRUTALDIE,SND_MINO_VODIEBIG2,SND_MINO_HORNGOUGE,SND_MINO_FOOTSCRAPE,SND_MINO_CHARGEVO
1|R_MI4.WAD|mi4|vag|10|100448|MINATK_2,MINATK_3,MINATK_4,MINDIE_1,MINDIEB1,MINHIT_1,MINHIT_2,MINHIT_3,MINHIT_4,MINHITB1
1|R_MI5.WAD|SBK_MI5_Mntaur5|blk|20|116036|SND_MINO_STEPLIGHT,SND_MINO_STEPHEAVY,SND_MINO_STEPLAND,SND_MINO_BODYFALL_HEAVY,SND_MINO_BODYFALL_MED,SND_MINO_BODYFALL_LIMB,SND_MINO_SNORT,SND_MINO_VOATTACK,SND_MINO_VOATTACK_A,SND_MINO_VOGETHIT,SND_MINO_VOGETHIT_A,SND_MINO_VOGETHITBIG,SND_MINO_VOGETHITB_A,SND_MINO_VOTAUNT1,SND_MINO_VOTAUNT2,SND_MINO_VOTAUNT3,SND_MINO_VODIE,SND_MINO_VODIEBIG,SND_MINO_AXEDROP,SND_AXESWING_NORMAL,SND_AXESWING_SLOW,SND_AXESWING_MEDIUM,SND_AXESWING_FAST,SND_HAMMERHITGROUND,SND_MINO_AGRO_LP,SND_MINO_GROWL,SND_MINO_STRUGGLE_LP_A,SND_MINO_STRUGGLE_LP_B,SND_MIN_NAVSOUND_CYCLE,SND_MIN_HEADCUT_VO,SND_MINO_VOBRUTALDIE,SND_MINO_VODIEBIG2,SND_HAMHITGROUND_SOFT,SND_SHOCKWAVE
1|R_MI5.WAD|mi5|vag|10|100448|MINATK_2,MINATK_3,MINATK_4,MINDIE_1,MINDIEB1,MINHIT_1,MINHIT_2,MINHIT_3,MINHIT_4,MINHITB1
1|R_MIF.WAD|SBK_MI4_Mntaur4|blk|21|116096|SND_MINO_STEPLIGHT,SND_MINO_STEPHEAVY,SND_MINO_STEPLAND,SND_MINO_BODYFALL_HEAVY,SND_MINO_BODYFALL_MED,SND_MINO_BODYFALL_LIMB,SND_MINO_SNORT,SND_MINO_VOATTACK,SND_MINO_VOATTACK_A,SND_MINO_VOGETHIT,SND_MINO_VOGETHIT_A,SND_MINO_VOGETHITBIG,SND_MINO_VOGETHITB_A,SND_MINO_VOTAUNT1,SND_MINO_VOTAUNT3,SND_MINO_VODIE,SND_MINO_VODIEBIG,SND_MINO_AXEDROP,SND_AXESWING_NORMAL,SND_AXESWING_SLOW,SND_AXESWING_MEDIUM,SND_AXESWING_FAST,SND_AXEHITGROUND,SND_AXEPULLOUTGROUND,SND_MINO_AGRO_LP,SND_MINO_GROWL,SND_MINO_STRUGGLE_LP_A,SND_MINO_STRUGGLE_LP_B,SND_MIN_NAVSOUND_CYCLE,SND_MIN_HEADCUT_VO,SND_MINO_VOBRUTALDIE,SND_MINO_VODIEBIG2,SND_MINO_HORNGOUGE,SND_MINO_FOOTSCRAPE,SND_MINO_CHARGEVO
1|R_MIN.WAD|SBK_MIN_Mntaur1|blk|22|115568|SND_MINO_STEPLIGHT,SND_MINO_STEPHEAVY,SND_MINO_STEPLAND,SND_MINO_BODYFALL_HEAVY,SND_MINO_BODYFALL_MED,SND_MINO_BODYFALL_LIMB,SND_MINO_SNORT,SND_MINO_VOATTACK,SND_MINO_VOATTACK_A,SND_MINO_VOGETHIT,SND_MINO_VOGETHIT_A,SND_MINO_VOGETHITBIG,SND_MINO_VOGETHITB_A,SND_MINO_VOTAUNT1,SND_MINO_VOTAUNT3,SND_MINO_VODIE,SND_MINO_VODIEBIG,SND_MINO_AXEDROP,SND_AXESWING_NORMAL,SND_AXESWING_SLOW,SND_AXESWING_MEDIUM,SND_AXESWING_FAST,SND_AXEHITGROUND,SND_AXEPULLOUTGROUND,SND_MINO_AGRO_LP,SND_MINO_GROWL,SND_MINO_STRUGGLE_LP_A,SND_MINO_STRUGGLE_LP_B,SND_MIN_NAVSOUND_CYCLE,SND_MIN_HEADCUT_VO,SND_MINO_VOBRUTALDIE,SND_MINO_VODIEBIG2
1|R_MIN.WAD|min|vag|10|100448|MINATK_2,MINATK_3,MINATK_4,MINDIE_1,MINDIEB1,MINHIT_1,MINHIT_2,MINHIT_3,MINHIT_4,MINHITB1
1|R_NYA.WAD|SBK_NYA_Nyad1|blk|5|109232|SND_NYAD_KISS_A,SND_NYAD_KISS_B,SND_NYA_SWIMSOUND
1|R_PERM.WAD|GENERAL|blk|137|1159844|SND_FOOTSTEP_DIRT,SND_FOOTSTEP_DIRTSTEP,SND_FOOTSTEP_DIRTWALK,SND_FOOTSTEP_DIRTRUN,SND_FOOTSTEP_DIRTLAND,SND_FOOTSTEP_PLANK,SND_FOOTSTEP_PLANKSTEP,SND_FOOTSTEP_PLANKWALK,SND_FOOTSTEP_PLANKRUN,SND_FOOTSTEP_PLANKLAND,SND_FOOTSTEP_STONE,SND_FOOTSTEP_STONESTEP,SND_FOOTSTEP_STONEWALK,SND_FOOTSTEP_STONERUN,SND_FOOTSTEP_STONELAND,SND_CLIFFCLIMB_GRAB,SND_CLIFFCLIMB_STEP,SND_CLIFFJUMP_LAND,SND_FOOTSTEP_BEAM,SND_FOOTSTEP_BEAMSTEP,SND_FOOTSTEP_BEAMWALK,SND_FOOTSTEP_BEAMRUN,SND_FOOTSTEP_BEAMLAND,SND_FOOTSTEP_WATER,SND_FOOTSTEP_WATERSTEP,SND_FOOTSTEP_WATERWALK,SND_FOOTSTEP_WATERRUN,SND_FOOTSTEP_WATERLAND,SND_FOOTSTEP_PUDDLE,SND_FOOTSTEP_PUDDLESTEP,SND_FOOTSTEP_PUDDLEWALK,SND_FOOTSTEP_PUDDLERUN,SND_FOOTSTEP_PUDDLELAND,SND_FOOTSTEP_VINEWALL,SND_VINEWALL_CATCH,SND_VINEWALL_GRAB,SND_VINEWALL_STEP,SND_VINEWALL_LAND,SND_FOOTSTEP_ROPEWALL,SND_ROPEWALL_CATCH,SND_ROPEWALL_GRAB,SND_ROPEWALL_STEP,SND_ROPEWALL_LAND,SND_FOOTSTEP_LADDER,SND_HANDGRAB_LADDER,SND_LADDERSLIDE_LP,SND_HANDGRAB_ROPE,SND_SLIDEROPE_LP,SND_ROPE_SWINGSHOT,SND_KNEEDEEPWATER,SND_INTOWATER_SPLASH,SND_JUMPOUTWATER,SND_SWIMSPLASH,SND_SWIM_STROKE,SND_SWIM_UW_STROKE,SND_STATUERAISE_SPLASH,SND_WHOOSHMID_SLOW,SND_WHOOSHMID_MEDIUM,SND_WHOOSHMID_FAST,SND_WHOOSHLOW_SLOW,SND_WHOOSHLOW_MEDIUM,SND_WHOOSHLOW_FAST,SND_WHOOSHMID_S_A,SND_WHOOSHMID_M_A,SND_WHOOSHMID_F_A,SND_WHOOSHLOW_S_A,SND_WHOOSHLOW_M_A,SND_WHOOSHLOW_F_A,SND_CHAINSNAP_A,SND_CHAINSNAP_WCLANK_A,SND_CHAINRETURN,SND_BLADEBLOCK,SND_SWORDHIT_SWORDHEV,SND_SWORDHIT_SHIELD,SND_SWORDHIT_STONE,SND_SWORDHIT_WOOD,SND_SWORD_HITMETAL,SND_SWORDHIT_CHEST,SND_SWORD_IMPALE,SND_SWORD_CUTTHEAD,SND_SWDSPECIALATK1,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_HERO_JUMPVOC,SND_HERO_JUMPVOC_A,SND_HERO_JUMPVOCAL,SND_HERO_JUMPVOCAL_A,SND_BODYFALL_ROLL,SND_BODYFALL_SLAM,SND_BODYFALL_HEAVY,SND_BODYFALL_LIGHT,SND_BODYFALL_LIMB,SND_PICKUPS_ORBS_H,SND_PICKUPS_ORBS_M,SND_PICKUPS_ORBS_E,SND_CRANKFORWARD,SND_CRANKBACKWARD,SND_CRANK_STOP,SND_LGCLUNK_UP,SND_LGCLUNK_DN,SND_PUNCH,SND_MINIGAME_HIT,SND_MINIGAME_AVAILABLE,SND_TORCH_LOOP,SND_BLOODSPURT,SND_DMCDOOR_LP,SND_DMCDOOR_STOP,SND_DMCDOOR_START,SND_SPAWN_LP,SND_DIEPOOF,SND_POTTERYSMASH,SND_CHESTGRAB,SND_CHESTOPEN,SND_LEVER,SND_LEVER_RELEASE,SND_MEDUSA_RAY_SHOT,SND_MEDUSA_RAY_LOOP,SND_MEDUSA_TURNTOSTONE,SND_MEDUSA_TURNTOFLESH,SND_RAISEDEAD_SHOT,SND_RAISEDEAD_LP,SND_BOLT_RAISE,SND_BOLT_LP,SND_BOLT_FIRE,SND_BOLT_HIT,SND_LIGHTNING360_START,SND_LIGHTNING360_LP,SND_LIGHTNING360_BOLT,SND_GODMODESHOT,SND_TRANSFORM_LP,SND_TRANSFORM_END,SND_BERZBLADE_DRAW,SND_BERZBLADE_LP,SND_BERZBLADE_FAST,SND_BERZBLADE_MED,SND_BERZBLADE_SLOW,SND_BERZBLADE_HIT,SND_IG_NAV_L,SND_IG_NAV_R,SND_IG_POPUP,SND_IG_POPUP_NO,SND_IG_BARGROW_LP,SND_IG_MAGICOUT,SND_IG_YOUAREDEAD,SND_MM_POPUP,SND_MM_CONTINUE,SND_MM_NAV_UPDN,SND_MM_NAV_LR,SND_MM_SELECT,SND_MM_BACK,SND_MM_RESTART_YES,SND_MM_QUIT_YES,SND_MM_SFX_SLIDER,SND_MM_NEGATIVE,SND_PU_R1,SND_PU_L1,SND_PU_NAV_UPDN,SND_PU_EMPTY,SND_PU_TRANSFER_LP,SND_PU_POWERUP,SND_IG_COOL100,SND_IG_COOLPROG,SND_IG_LOSECOOL,SND_P01B_CRUSHERHIT_B,SND_TRUSSBREAK,SND_INSERTCRANK,SND_STATUEBREAK,SND_BREAKABLEDOOR1,SND_BREAKABLEDOOR2,SND_GROUNDBREAK,SND_LOGSHOOT,SND_BIGDEBRIS,SND_HOISTANCHOR_LP,SND_LOWHEALTH,SND_P4C_BLOCKSMASH,SND_SHARDCOLLECT,SND_SHARDCOMPLETE,SND_ICON,SND_STATUEMOUNT,SND_SWDSPECIALATK1_PRE,SND_CNM_SLAMGROUND,SND_P03GRATESPLASH,SND_BLOODGEYSER,SND_BLOODGUSH,SND_BARRELSMASH,SND_BUCKETSMASH,SND_SWORDHIT_SANDBAG,SND_FRUITBASKETSMASH,SND_SELECT_RTD,SND_SELECT_BOLT,SND_SELECT_LIGHTNING,SND_SELECT_MEDUSA,SND_SELECT_NULL,SND_BEAT1,SND_BEAT2,SND_ARROWFIRE_LP,SND_BIGDEBRISCRASH,SND_STATUEHITWALL,SND_SAVEPOINT_LP,SND_MAI_STRUGGLEVO_LP,SND_DMCDOOR2_STOP,SND_DMCDOOR2_START,SND_HUGESPLASH,SND_SKD_BURROW,SND_SKD_BURROW_LP,SND_BONECRUNCH_BIG,SND_MINIGAME_BUTTON,SND_KICKCHARGEVO_LP,SND_SWIM_UW_LOOP,SND_CHARGE_LP,SND_BOLTCHARGE_LP,SND_UPGRADEWHOOSH,SND_SWIMDASH,SND_MEDUSA_NUKE,SND_ROCKHIT,SND_BAR_FIREBALLIMPACT,SND_HB_POSTMOVIE,SND_MM_NAV_UPDN_LP
1|R_PERM.WAD|Hero|vag|16|99192|DIEVOC1,H_ATTKL1,H_ATTKL2,H_ATTKS1,H_ATTKS2,H_ATTKS3,H_ATTKS4,H_DMG1,H_DMG2,H_DMG3,H_DMG4,H_DMG5,H_DMG6,JUMPVOC1,JUMPVOC2,LIFTVOC1
1|R_SAF.WAD|SBK_SAF_SatyrF|blk|24|113672|SND_SAT_STEPLIGHT,SND_SAT_STEPHEAVY,SND_SAT_STEPLAND,SND_SAT_STAFFSPIN_HIGH,SND_SAT_STAFFSPIN_MED,SND_SAT_STAFFSPIN_LOW,SND_SAT_ATTKWHOOSH1,SND_SAT_ATTKWHOOSH2,SND_SAT_ATTKWHOOSH3,SND_SAT_ATTKWHOOSH4,SND_SAT_BLADEHITGROUND,SND_SAT_BODYFALL_HEAVY,SND_SAT_BODYFALL_MED,SND_SAT_BODYFALL_LIMB,SND_SAT_BODYFALL_HEAD,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_SAT_SNORT,SND_SAT_VOATTACK,SND_SAT_VOGETHIT,SND_SAT_VOGETHITBIG,SND_SAT_VOTAUNT,SND_SAT_VODIE,SND_SAT_VOATTACK_A,SND_SAT_VOGETHIT_A,SND_SAT_VOGETHITB_A,SND_SAT_BLADEDROP,SND_SAT_BLADESCRAPE
1|R_SAF.WAD|saf|vag|9|99428|SATATK01,SATATK02,SATATK03,SATDIE01,SATHIT01,SATHIT02,SATHIT03,SATHIT04,SATTAUNT
1|R_SAT.WAD|SBK_SAT_Satyr1|blk|24|113672|SND_SAT_STEPLIGHT,SND_SAT_STEPHEAVY,SND_SAT_STEPLAND,SND_SAT_STAFFSPIN_HIGH,SND_SAT_STAFFSPIN_MED,SND_SAT_STAFFSPIN_LOW,SND_SAT_ATTKWHOOSH1,SND_SAT_ATTKWHOOSH2,SND_SAT_ATTKWHOOSH3,SND_SAT_ATTKWHOOSH4,SND_SAT_BLADEHITGROUND,SND_SAT_BODYFALL_HEAVY,SND_SAT_BODYFALL_MED,SND_SAT_BODYFALL_LIMB,SND_SAT_BODYFALL_HEAD,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_SAT_SNORT,SND_SAT_VOATTACK,SND_SAT_VOGETHIT,SND_SAT_VOGETHITBIG,SND_SAT_VOTAUNT,SND_SAT_VODIE,SND_SAT_VOATTACK_A,SND_SAT_VOGETHIT_A,SND_SAT_VOGETHITB_A,SND_SAT_BLADEDROP,SND_SAT_BLADESCRAPE
1|R_SAT.WAD|sat|vag|9|99428|SATATK01,SATATK02,SATATK03,SATDIE01,SATHIT01,SATHIT02,SATHIT03,SATHIT04,SATTAUNT
1|R_SD2.WAD|SBK_SD2_Dive2|blk|13|113552|SND_SKELDIV_SLASHFAST,SND_SKELDIV_SLASHMEDIUM,SND_SKELDIV_SLASHSLOW,SND_SKELDIV_SLASHSLOWES,SND_SKELSOL_BODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELDIV_VOATTACK,SND_SKELDIV_VOATTACK_A,SND_SKELDIV_VOATKBIG_A,SND_SKELDIV_VOGETHIT,SND_SKELDIV_VOGETHIT_A,SND_SKELDIV_VODIE,SND_SKELDIV_VODIEBRUTAL,SND_SKD_CACKLE,SND_SKD_VODIVE,SND_SKD_SPINATKVO,SND_ARMRIPOFF,SND_SKD_SWORDHIT,SND_SKD_SWORDHITGROUND,SND_SKD_SWORDHITFINAL,SND_SKD_IDLE,SND_SKD_NAVSOUND,SND_SKD_SWORDDROP
1|R_SD2.WAD|sd2|vag|12|100632|SKD_ATK1,SKD_ATK2,SKD_ATK3,SKD_ATK4,SKD_DIE1,SKD_DIE2,SKD_HIT1,SKD_HIT2,SKD_HIT3,SKD_HIT5,SKDCACK,SKDDIEB1
1|R_SHELL.WAD|SBK_Title01|blk|2|111768|SND_HL_A07HL02,SND_M_TIT1E1_2,SND_M_TIT1Q1_2,SND_M_CREDITS1
1|R_SID.WAD|SBK_SID_Siren2|blk|10|111880|SND_M_SSONG1LP,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_SIREN_FIREBALL,SND_SIR_ELECSHOT,SND_SIR_ELECSHOTBIG,SND_SIR_ELECBLOCK,SND_SIR_ELECEXPLO,SND_SIR_VOLAUGH_SMALL,SND_SIREN_VOATTACK,SND_SIREN_VOATTACK_A,SND_SIREN_VOGETHIT,SND_SIREN_VOGETHIT_A,SND_SIREN_VODIE,SND_SIREN_TAUNT1,SND_SIREN_TAUNT2,SND_SIREN_TAUNT3,SND_SIR_IDLE,SND_SIR_NAVSOUND
1|R_SID.WAD|sid|vag|10|99040|SIR_ATK1,SIR_ATK2,SIR_ATK3,SIR_HIT1,SIR_HIT2,SIR_HIT3,SIR_HIT4,SIR_LAF2,SIR_LAF3,TAUNT02
1|R_SIR.WAD|SBK_SIR_Siren1|blk|10|111880|SND_M_SSONG1LP,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_SIREN_FIREBALL,SND_SIR_ELECSHOT,SND_SIR_ELECSHOTBIG,SND_SIR_ELECBLOCK,SND_SIR_ELECEXPLO,SND_SIR_VOLAUGH_SMALL,SND_SIREN_VOATTACK,SND_SIREN_VOATTACK_A,SND_SIREN_VOGETHIT,SND_SIREN_VOGETHIT_A,SND_SIREN_VODIE,SND_SIREN_TAUNT1,SND_SIREN_TAUNT2,SND_SIREN_TAUNT3,SND_SIR_IDLE,SND_SIR_NAVSOUND
1|R_SIR.WAD|sir|vag|10|99040|SIR_ATK1,SIR_ATK2,SIR_ATK3,SIR_HIT1,SIR_HIT2,SIR_HIT3,SIR_HIT4,SIR_LAF2,SIR_LAF3,TAUNT02
1|R_SK2.WAD|SBK_SK2_Archer2|blk|19|115300|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_WHOOSH_FAST,SND_WHOOSH_MEDIUM,SND_WHOOSH_SLOW,SND_WHOOSH_SLOWEST,SND_SKELSOL_GETUP,SND_BOW_DRAWBACK_FAST,SND_BOW_DRAWBACK_SLOW,SND_BOW_FIRE,SND_SKELSOL_VODIE,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHIT_A,SND_SKEL_VOGRUNT,SND_SKELARC_TAUNT00,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKA_ARR_FLIGHTSHOT,SND_SKA_ARR_BLOCK,SND_SKA_ARR_HITFLESH,SND_SKA_ARR_HITWATER,SND_SKA_ARR_HITDIRT,SND_SKA_ARR_HITSTONE,SND_SKA_ARR_HITWOOD,SND_SKA_ARR_HITGEN,SND_SKA_ARR_EXPLODE
1|R_SK2.WAD|sk2|vag|12|73112|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
1|R_SK3.WAD|SBK_SK3_ArcherF|blk|22|116304|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_WHOOSH_FAST,SND_WHOOSH_MEDIUM,SND_WHOOSH_SLOW,SND_WHOOSH_SLOWEST,SND_SKELSOL_GETUP,SND_BOW_DRAWBACK_FAST,SND_BOW_DRAWBACK_SLOW,SND_BOW_FIRE,SND_SKELSOL_VODIE,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHIT_A,SND_SKEL_VOGRUNT,SND_SKELARC_TAUNT00,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKA_ARR_FLIGHTSHOT,SND_SKA_ARR_BLOCK,SND_SKA_ARR_HITFLESH,SND_SKA_ARR_HITWATER,SND_SKA_ARR_HITDIRT,SND_SKA_ARR_HITSTONE,SND_SKA_ARR_HITWOOD,SND_SKA_ARR_HITGEN,SND_SKA_ARR_EXPLODE
1|R_SK3.WAD|sk3|vag|12|73112|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
1|R_SK4.WAD|SBK_SK4_Skel4|blk|28|114416|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHFAST,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHITBIG,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SKEL_VOGRUNT,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKELFALLSCREAM,SND_SKELSOL_CHOKE,SND_SKELSOL_CACKLE,SND_SKELFLIP_A,SND_SKELFLIP_B
1|R_SK4.WAD|sk4|vag|9|86148|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELHIT1,SKELHIT2,SKELHIT3
1|R_SK5.WAD|SBK_SKF_Skel3|blk|26|114368|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHFAST,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHITBIG,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SKEL_VOGRUNT,SND_SKF_FLIPYELL,SND_SKF_VOEXTDEATH
1|R_SK5.WAD|sk5|vag|12|73112|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
1|R_SKA.WAD|SBK_SKA_Archer1|blk|26|114976|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_WHOOSH_FAST,SND_WHOOSH_MEDIUM,SND_WHOOSH_SLOW,SND_WHOOSH_SLOWEST,SND_SKELSOL_GETUP,SND_BOW_DRAWBACK_FAST,SND_BOW_DRAWBACK_SLOW,SND_BOW_FIRE,SND_SKELSOL_VODIE,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHIT_A,SND_SKEL_VOGRUNT,SND_SKELARC_TAUNT00,SND_SKELARC_TAUNT01,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKA_ARR_FLIGHTSHOT,SND_SKA_ARR_BLOCK,SND_SKA_ARR_HITFLESH,SND_SKA_ARR_HITWATER,SND_SKA_ARR_HITDIRT,SND_SKA_ARR_HITSTONE,SND_SKA_ARR_HITWOOD,SND_SKA_ARR_HITGEN
1|R_SKA.WAD|SKA|vag|12|73112|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
1|R_SKB.WAD|SBK_SKB_SkelSh|blk|27|114840|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SHIELDBASH,SND_SKELSOL_SLASHFAST,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SHSKEL_SHIELDBREAK,SND_SHSKEL_CACKLE,SND_SKEL_VOGRUNT,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKELSOL_CHOKE,SND_DASHPOWERUP,SND_SHIELDBLOCK2,SND_SKB_TAUNT,SND_SKELFLIP_A,SND_SKELFLIP_B
1|R_SKB.WAD|skb|vag|12|73112|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
1|R_SKC.WAD|SBK_SKC_Skel2|blk|28|114600|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHFAST,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHITBIG,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SKEL_VOGRUNT,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKELFALLSCREAM,SND_SKELSOL_CHOKE,SND_PICKAWHOOSH,SND_SKELSOL_CACKLE,SND_SKELFLIP_A,SND_SKELFLIP_B
1|R_SKC.WAD|skc|vag|9|86148|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELHIT1,SKELHIT2,SKELHIT3
1|R_SKD.WAD|SBK_SKD_Dive1|blk|13|113552|SND_SKELDIV_SLASHFAST,SND_SKELDIV_SLASHMEDIUM,SND_SKELDIV_SLASHSLOW,SND_SKELDIV_SLASHSLOWES,SND_SKELSOL_BODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELDIV_VOATTACK,SND_SKELDIV_VOATTACK_A,SND_SKELDIV_VOATKBIG_A,SND_SKELDIV_VOGETHIT,SND_SKELDIV_VOGETHIT_A,SND_SKELDIV_VODIE,SND_SKELDIV_VODIEBRUTAL,SND_SKD_CACKLE,SND_SKD_VODIVE,SND_SKD_SPINATKVO,SND_ARMRIPOFF,SND_SKD_SWORDHIT,SND_SKD_SWORDHITGROUND,SND_SKD_SWORDHITFINAL,SND_SKD_IDLE,SND_SKD_NAVSOUND,SND_SKD_SWORDDROP
1|R_SKD.WAD|skd|vag|12|100632|SKD_ATK1,SKD_ATK2,SKD_ATK3,SKD_ATK4,SKD_DIE1,SKD_DIE2,SKD_HIT1,SKD_HIT2,SKD_HIT3,SKD_HIT5,SKDCACK,SKDDIEB1
1|R_SKF.WAD|SBK_SKF_Skel3|blk|26|114368|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHFAST,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHITBIG,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SKEL_VOGRUNT,SND_SKF_FLIPYELL,SND_SKF_VOEXTDEATH
1|R_SKF.WAD|skf|vag|10|79440|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
1|R_SKS.WAD|SBK_SKS_Skel1|blk|27|115452|SND_SKELSOL_STEPLIGHT,SND_SKELSOL_STEPHEAVY,SND_SKELSOL_STEPLAND,SND_SKELSOL_ATTACKL,SND_SKELSOL_ATTACKR,SND_SKELSOL_SLASHSLOW,SND_SKELSOL_SLASHMEDIUM,SND_SKELSOL_SLASHFAST,SND_WHOOSH_SLOWEST,SND_WHOOSH_SLOW,SND_WHOOSH_MEDIUM,SND_WHOOSH_FAST,SND_SKELSOL_BIGJUMPLAND,SND_SKELSOL_DIEBODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_SKELSOL_GETUP,SND_SKELSOL_VOATTACK,SND_SKELSOL_VOGETHIT,SND_SKELSOL_VOGETHITBIG,SND_SKELE_NECKBREAK,SND_SKELSOL_VODIE,SND_SKELSOL_TAUNT,SND_SKELSOL_VOATTACK_A,SND_SKELSOL_VOGETHIT_A,SND_SKELSOL_VOGETHITB_A,SND_SKELSOL_CACKLE,SND_SKEL_VOGRUNT,SND_SKELSOL_TOSSYELL,SND_SKELSOL_RIP,SND_SKELFALLSCREAM,SND_SKELSOL_CHOKE
1|R_SKS.WAD|sks|vag|12|73112|SKELATK1,SKELATK2,SKELATK3,SKELATK4,SKELDIE1,SKELDIE2,SKELDIE3,SKELDIE4,SKELHIT1,SKELHIT2,SKELHIT3,SKELHIT4
1|SEWR01.WAD|SBK_Sewr01|blk|24|153336|SND_SEWERAMB_LP,SND_TOWERAMB_LP,SND_OCEANAMB_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_SEWERDRIPS_LP,SND_BIGFALLS_LP,SND_MEDFALLS_LP,SND_SMALLFALLS_LP,SND_BIGDRIPS_LP,SND_RAT_SQUEAKS_LP,SND_M_SEW1C1_2,SND_M_SEW1C2_2,SND_M_SEW1E1_2,SND_M_SEW1Q1_2,SND_M_SEW2Q6_2,SND_M_SEW1Q7_2
1|SEWR02.WAD|SBK_Sewr02|blk|28|204104|SND_SEWERAMB_LP,SND_OUTDOORAMB_LP,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_SEWERDRIPS_LP,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_BIGFALLS_LP,SND_MEDFALLS_LP,SND_SMALLFALLS_LP,SND_BIGDRIPS_LP,SND_PISTONMOVE_LP,SND_RAT_SQUEAKS_LP,SND_M_SEW2C3_2,SND_M_SEW2Q5_2,SND_M_SEW1C1_2,SND_M_SEW2Q6_2,SND_M_SEW1Q7_2,SND_M_SEW1E1_2
2|ATLAS210.WAD|SBP_ATLS210|blk|5|76032|SND_AMB_OUTDOOR_LP,SND_AMB_INDOOR_LP,SND_M_AT21001A,SND_M_AT21002Q,SND_LAVA_LP,SND_M_BG22502Q,SND_D_GA14,SND_D_ATGRUMBLE
2|ATLAS220.WAD|SBP_ATLS220|blk|14|154784|SND_AMB_OUTDOOR_LP,SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_M_AT22001S,SND_M_AT22002C,SND_M_AT22002E,SND_M_AT21001A,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_FLESHSLIDE_LP,SND_LAVA_LP,SND_ISLAND_SINK,SND_ISLAND_RISE,SND_BLOCKSLIDE_LP,SND_M_AT22003A,SND_TENTACLE_RETRACT
2|ATLAS230.WAD|SBP_ATLS230|blk|15|209952|SND_AMB_OUTDOOR_LP,SND_AMB_INDOOR_LP,SND_M_AT21001A,SND_M_AT22001S,SND_FOOTSTEP_FLESH,SND_FOOTSTEP_FLESHSTEP,SND_FOOTSTEP_FLESHWALK,SND_FOOTSTEP_FLESHRUN,SND_FOOTSTEP_FLESHLAND,SND_LAVA_LP,SND_ERRUPTION_LP,SND_ROCK_RELEASE,SND_ROCK_SPLASH,SND_BULB_EXPLODE,SND_WATERFALL_LP,SND_PLATFORM_SM_LP,SND_TENTACLE_RETRACT,SND_PLATFORM_LG_LP,SND_PLATFORM_LG_STOP,SND_M_AT22003A,SND_M_AT24002A,SND_M_AT23001S,SND_M_AT23002Q,SND_M_AT24001E,SND_D_ATGRUMBLE
2|ATLAS235.WAD|SBP_ATLS235|blk|7|101616|SND_AMB_OUTDOOR_LP,SND_AMB_INDOOR_LP,SND_M_AT21001A,SND_M_AT22001S,SND_BLOCKSLIDE_LP,SND_CHAIN_BREAK,SND_M_AT22003A,SND_M_AT24002A,SND_FALLING_ROCK_LP,SND_M_AT23001S,SND_ASS_SLIDE,SND_M_AT25005S
2|ATLAS240.WAD|SBP_ATLS240|blk|1|29344|SND_AMB_OUTDOOR_LP,SND_AMB_INDOOR_LP,SND_M_AT22001S,SND_STEAMVENT_LP,SND_M_AT22003A,SND_M_AT24001C,SND_M_AT24002A,SND_M_AT23001S,SND_M_AT24001E,SND_M_AT25005S
2|BOG05.WAD|SBP_BOG05|blk|11|124016|SND_AMB_OUTDOOR_LP,SND_M_BG1001S,SND_M_BG25003E,SND_BOGWATER_LP,SND_BOGSIZZLE_LP,SND_BOGGAS_LP,SND_LAPPINGWAT_LP,SND_HEAVYLAP_LP,SND_LIGHTLAP_LP,SND_BUBBLE_LP
2|BOG10.WAD|SBP_BOG10|blk|22|254640|SND_DOOR_RAY_LP,SND_WATERFALL_LP,SND_QUICKSAND_LP,SND_QUICKSAND2_LP,SND_BIRDFLYAWAY,SND_BOGWATER_LP,SND_BOGSIZZLE_LP,SND_LAPPINGWAT_LP,SND_HEAVYLAP_LP,SND_LIGHTLAP_LP,SND_BUBBLE_LP,SND_UNLOCK_DOOR,SND_BIRDFLYAW_2,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_M_BG1001S,SND_M_BG1002Q,SND_M_BG1003A,SND_M_BG2001Q,SND_M_BG2001A,SND_M_BG1004S,SND_M_BG1005A,SND_SPIKES_OUT,SND_SPIKES_IN,SND_AMB_OUTDOOR_LP,SND_AMB_OUTDOOR2_LP,SND_AMB_INDOOR_LP,SND_M_BG4502S
2|BOG20.WAD|SBP_BOG20|blk|18|197296|SND_BOGWATER_LP,SND_BLOCKSLIDE_LP,SND_BLOCKHITGROUND,SND_TEMPLEPUSH_LP,SND_TEMPLE_TEETER,SND_TEMPLE_STOP,SND_BOGSIZZLE_LP,SND_BOGGAS_LP,SND_LAPPINGWAT_LP,SND_HEAVYLAP_LP,SND_LIGHTLAP_LP,SND_BUBBLE_LP,SND_FLIESBUZZ1_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_TEMPLEPUSH_FLOURISH,SND_TEMPLESINK1,SND_TEMPLESINK2,SND_TEMPLESINK_BUBBLE1,SND_TEMPLESINK_BUBBLE2,SND_TEMPLESINK_SPLASH1,SND_TEMPLESINK_SPLASH2,SND_D_11D01JG,SND_D_11D02JG,SND_D_11D03JG,SND_M_BG1003A,SND_M_BG2001Q,SND_M_BG2001A,SND_M_BG2002S,SND_M_BG2003S,SND_M_BG2003E,SND_M_BG2004C,SND_M_BG2004E,SND_M_BG2005A,SND_M_BG3501C,SND_M_BG4003S,SND_M_BG2006A,SND_M_BG4501C,SND_M_BG1004S,SND_M_BG1005A,SND_H_BOG20A,SND_TEMPLE_PUSH,SND_AMB_OUTDOOR_LP,SND_AMB_OUTDOOR2_LP,SND_AMB_INDOOR_LP,SND_M_BG4502S,SND_M_BG2007A
2|BOG210.WAD|SBP_BOG210|blk|10|108832|SND_AMB_OUTDOOR_LP,SND_AMB_OUTDOOR2_LP,SND_AMB_INDOOR_LP,SND_STONEDOOR_LOOP,SND_STONEPEDESTAL_LP,SND_PUSHPULL_LP,SND_FLOORSPIN_LP,SND_PLATFORM_TEETER,SND_PLATFORM_STOP,SND_M_BG21001A,SND_M_BG21002S,SND_M_BG21002E,SND_M_IS4701A,SND_M_BG21003A,SND_M_BG21501C,SND_M_BG22002S,SND_CRANKCOVER_LP,SND_CRANKPLATFORM_LP
2|BOG215.WAD|SBP_BOG215|blk|9|226448|SND_AMB_OUTDOOR_LP,SND_AMB_OUTDOOR2_LP,SND_AMB_INDOOR_LP,SND_CRUMBLE_LP,SND_COLUMN_MOVE_LP,SND_COLUMN_SNAP,SND_KRATOS_COLUMN_JUMP,SND_M_BG21001A,SND_M_BG21501C,SND_M_BG21501E,SND_M_BG22002S
2|BOG245.WAD|SBP_BOG245|blk|14|158240|SND_AMB_OUTDOOR_LP,SND_BODYDRAG_LP,SND_BODYDRAG_NOISE_LP,SND_BODYDRAG_SHOTS_LP,SND_BOGWATER_LP,SND_BOGSIZZLE_LP,SND_LAPPINGWAT_LP,SND_HEAVYLAP_LP,SND_LIGHTLAP_LP,SND_BUBBLE_LP,SND_M_BG24502S,SND_M_BG25001I,SND_M_IS3002A,SND_M_IS3005A,SND_AMB_OUTDOOR2_LP
2|BOG250.WAD|SBP_BOG250|blk|9|155728|SND_AMB_OUTDOOR_LP,SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_BODYDRAG_LP,SND_BODYDRAG_NOISE_LP,SND_BODYDRAG_SHOTS_LP,SND_LEVELBREAK_EXPLO,SND_D_14E02BC,SND_M_BG25001C,SND_M_BG25001I,SND_M_BG24502S,SND_M_BG25001T,SND_M_BG25002C,SND_M_BG25002T,SND_M_BG25003C,SND_M_BG25003E,SND_M_BG1001S,SND_LEVELBREAK_FIRE,SND_LEVELBREAK_EXP2
2|BOG30.WAD|SBP_BOG30|blk|11|140032|SND_AMB_OUTDOOR_LP,SND_AMB_OUTDOOR2_LP,SND_AMB_INDOOR_LP,SND_INDOORFALLS_LP,SND_BOGWATER_LP,SND_BOGSIZZLE_LP,SND_LAPPINGWAT_LP,SND_HEAVYLAP_LP,SND_LIGHTLAP_LP,SND_BUBBLE_LP,SND_BOGGAS_LP,SND_M_BG2005A,SND_M_BG3501C,SND_M_BG4004S,SND_M_BG2003S
2|BOG35.WAD|SBP_BOG35|blk|15|96848|SND_AMB_INDOOR_LP,SND_AMB_OUTDOOR2_LP,SND_PILLAR_PUSH_LP,SND_GATE_LP,SND_STONEPEDESTAL_LP,SND_M_BG2005A,SND_M_BG3501C,SND_M_BG3501E,SND_M_BG3502A,SND_M_BG4001C,SND_RIVER_LP,SND_ASS_GRAB,SND_M_BG4004S,SND_M_BG2003S
2|BOG40.WAD|SBP_BOG40|blk|17|222800|SND_AMB_INDOOR_LP,SND_AMB_OUTDOOR2_LP,SND_BOGWATER_LP,SND_WATERLAP_LP,SND_WHEEL_LP,SND_WINDMILL,SND_SPLASH_WATER,SND_CONVEYOR_LP,SND_SPRING_LP,SND_MEDUSA_LP,SND_GEARSPIN_LP,SND_LILYPAD_CRANK_LP,SND_WATERLAP2_LP,SND_HL_B40HL04,SND_HL_B40HL05,SND_VO_MANDIE,SND_M_BG3502A,SND_M_BG4001C,SND_M_BG4002C,SND_M_BG4002E,SND_M_BG4003S,SND_M_BG2006A,SND_M_BG4004S,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM
2|BOG45.WAD|SBP_BOG45|blk|11|153680|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_BIGCRUSHER_LP,SND_SMALLCRUSHER_LP,SND_FLAME_PUFF,SND_FLMTHROWER_LP,SND_CRUSHER_BREAK,SND_GEARS2_LP,SND_CHAIN_LP,SND_D_11E01JG,SND_D_11E02JG,SND_D_11E03JG,SND_D_11E04aJG,SND_D_11E04JG,SND_D_11E05GA,SND_D_RANDOM,SND_WHEEL_DROP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_M_BG2006A,SND_M_BG4501C,SND_M_BG4501E,SND_M_BG4502S,SND_M_BG1004S,SND_AMB_OUTDOOR_LP,SND_D_JG04,SND_D_JG03,SND_D_JG02,SND_D_JG01
2|BOG70.WAD|SBP_BOG70|blk|8|82368|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_AMB_OUTDOOR_LP,SND_WATER_DRIP,SND_WATER_DRIP_LP,SND_D_12A01ME,SND_M_BG7002S,SND_M_BG1004S,SND_M_BG7001I,SND_M_BG7001C,SND_M_BG7001E,SND_M_BG8001Q,SND_M_BG2003S
2|BOG75.WAD|SBP_BOG75|blk|17|185504|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_AMB_CAVERN_LP,SND_CHAIN1_LP,SND_CHAIN2_LP,SND_ELEVATOR_LP,SND_ELEVATOR_STOP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_BLOCK_SLIDE_LP,SND_BLOCK_STOP,SND_PILLARS_SLIDE_LP,SND_D_12A02ME,SND_D_11G04aEG,SND_D_11G04EG,SND_M_BG7002S,SND_M_BG8001Q,SND_BLADE_AREA,SND_BLADE1,SND_BLADE2,SND_BLADE3,SND_BLADE4,SND_BLADE5,SND_BLADE6,SND_BLADE7,SND_BLADE8,SND_BIRDFLYAWAY,SND_BIRDFLYAW_2,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_H_BOG80A
2|BOG80.WAD|SBP_BOG80|blk|4|62416|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_INDOORFALLS_LP,SND_INDOORFALLS2_LP,SND_FLMTHROWERS_L_LP,SND_FLMTHROWERS_R_LP,SND_D_12A05ME,SND_D_12A06ME,SND_D_12A07ME,SND_D_12A08ME,SND_D_12A03ME,SND_D_FM_TAUNT,SND_D_FM_LAUGH,SND_M_BG8001Q,SND_M_BG8001C,SND_M_BG8001E,SND_M_BG8002S,SND_M_BG8003A,SND_M_BG8501C,SND_M_BG8002E,SND_H_BOG80A,SND_M_BG7002S,SND_GATE_LP
2|BOG85.WAD|SBP_BOG85|blk|20|233632|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_AMB_UNDERWATER_LP,SND_PILLARRAISE_LP,SND_PILLARRAISE_UW_LP,SND_PILLAR_STOP,SND_PILLAR_UW_STOP,SND_STONEDOOR_LP,SND_UNDERWATER_LEVER,SND_DASHDOOR_BREAK,SND_M_BG8003A,SND_M_BG8501C,SND_M_BG8502A,SND_M_BG8501E,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_STONEPEDESTAL_LP,SND_LADDERCOVER_LP,SND_WATERGATE_LP
2|BOG87.WAD|SBP_BOG87|blk|12|227248|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_FLOOR_LP,SND_FLOOR_STOP,SND_TNF_LP,SND_TNF_FLOURISH,SND_TNF_CLUNK,SND_TNF_CLUNK2,SND_STRESSCREAK,SND_M_BG8502A,SND_CEILINGGATE_LP,SND_METALGATE_LP,SND_GRINDGATE_LP,SND_GRINDGATE_STOP,SND_M_BG8703C,SND_M_BG8703E
2|BOG90.WAD|SBP_BOG90|blk|15|244368|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_STONEDOOR_LOOP,SND_FLOOR_LP,SND_FLOOR_STOP,SND_TNF_LP,SND_TNF_FLOURISH,SND_TNF_CLUNK,SND_TNF_CLUNK2,SND_STRESSCREAK,SND_M_IS3001A,SND_WATER_DRIP_LP,SND_WATER_DRIP_SLOW_LP,SND_M_BG8703E,SND_M_BG8704S,SND_M_BG9001E,SND_M_AT24001C,SND_M_BG9002E,SND_M_BG9002S
2|CMBT11.WAD|SBP_CMBT61|blk|10|165200|SND_M_BL6101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT12.WAD|SBP_CMBT61|blk|10|165200|SND_M_BL6101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT13.WAD|SBP_CMBT61|blk|10|165200|SND_M_BL6101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT21.WAD|SBP_CMBT31|blk|10|165200|SND_M_BL3101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT22.WAD|SBP_CMBT31|blk|10|165200|SND_M_BL3101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT23.WAD|SBP_CMBT31|blk|10|165200|SND_M_BL3101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT31.WAD|SBP_CMBT51|blk|10|165200|SND_M_BL5101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT32.WAD|SBP_CMBT51|blk|10|165200|SND_M_BL5101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT33.WAD|SBP_CMBT51|blk|10|165200|SND_M_BL5101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT41.WAD|SBP_CMBT21|blk|10|165200|SND_M_BL2101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT42.WAD|SBP_CMBT21|blk|10|165200|SND_M_BL2101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT43.WAD|SBP_CMBT21|blk|10|165200|SND_M_BL2101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT51.WAD|SBP_CMBT41|blk|10|165200|SND_M_BL4101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT52.WAD|SBP_CMBT41|blk|10|165200|SND_M_BL4101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT53.WAD|SBP_CMBT41|blk|10|165200|SND_M_BL4101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT61.WAD|SBP_CMBT11|blk|10|165200|SND_M_BL1301C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT62.WAD|SBP_CMBT11|blk|10|165200|SND_M_BL1301C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT63.WAD|SBP_CMBT11|blk|10|165200|SND_M_BL1301C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT71.WAD|SBP_CMBT71|blk|10|165200|SND_M_BL7101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT72.WAD|SBP_CMBT71|blk|10|165200|SND_M_BL7101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|CMBT73.WAD|SBP_CMBT71|blk|10|165200|SND_M_BL7101C,SND_AMB_ARENA1_LP,SND_AMB_ARENA2_LP,SND_AMB_ARENA3_LP,SND_SAC_SACRIFICE,SND_SAC_RINGAPPEAR,SND_SAC_PLUME_LP,SND_TIMER_TIC,SND_TIMER_FINALTICS,SND_WINGS_UP,SND_WINGS_DOWN
2|ISLE06.WAD|SBP_ISLE06|blk|17|186704|SND_AMB_WIND_LP,SND_GATE_LP,SND_GATESTOP,SND_WATERFALL_SMALL_LP,SND_SKELETON_SMASH,SND_M_IS0601A,SND_STONEPEDESTAL_LP,SND_M_IS0602S,SND_M_IS0602E,SND_M_IS0801A,SND_CHAIN_CREAK_LP,SND_CHAIN_CHUNKS_LP,SND_GATE_LONG_LP,SND_GATESTOP_LONG,SND_M_PG7901C,SND_M_PG7901E
2|ISLE08.WAD|SBP_ISLE08|blk|18|202464|SND_AMB_UNDERWATER_LP,SND_AMB_WIND_LP,SND_AMB_INDOOR_LP,SND_AMB_SEA_LP,SND_BLOCK_ELEVATOR_LP,SND_BLOCK_ELEV_STOP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_BRIDGE_LOWER,SND_STATUEWHOOSH,SND_STATUEHIT,SND_M_IS0602S,SND_M_IS0602E,SND_M_IS0801A,SND_M_IS0802A,SND_M_IS1001C,SND_FOUNTAIN_LP,SND_D_01GAA,SND_SLIDECHAIN_LP,SND_M_IS0803Q
2|ISLE10.WAD|SBP_ISLE10|blk|8|96208|SND_AMB_WIND_LP,SND_AMB_INDOOR,SND_ELEVATOR_LP,SND_ELEVATOR_STOP,SND_BLOCKHITGROUND,SND_BLOCKSLIDE_LP,SND_M_IS0802A,SND_M_IS1001C,SND_M_IS1001E,SND_M_IS1002A,SND_M_IS1201C
2|ISLE12.WAD|SBP_ISLE12|blk|19|210944|SND_AMB_SEA_LP,SND_AMB_INDOOR,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_STONEDOOR_LP,SND_METALGATE_LP,SND_CHAINSNAP_LARGE,SND_FLAME_PUFF,SND_FLAME_LP,SND_GEAR_SPIN_LP,SND_CHAIN_ROOM_LP,SND_D_GA11,SND_M_IS1002A,SND_M_IS1201C,SND_M_IS1201E,SND_M_IS1202Q,SND_M_IS1203A,SND_LIFTDOOR_GRAB
2|ISLE13.WAD|SBP_ISLE13|blk|5|30304|SND_AMB_SEA_LP,SND_M_IS1202Q,SND_M_IS1203A,SND_BIGCHAIN_CREAK,SND_CHAIN_CHUNKS_LP,SND_D_GA11
2|ISLE14.WAD|SBP_ISLE14|blk|11|197968|SND_AMB_WIND_LP,SND_AMB_SEA_LP,SND_BIGDOORKICK,SND_M_IS2008E,SND_M_IS1601A,SND_WATERFALL1_LP,SND_WATERFALL2_LP,SND_WATERFALL3_LP,SND_WATERFALL4_LP,SND_BIGCHAIN_CREAK,SND_CHAIN_CHUNKS_LP
2|ISLE15.WAD|SBP_ISLE15|blk|5|30224|SND_AMB_SEA_LP,SND_M_IS2008E,SND_M_IS1601A,SND_BIGCHAIN_CREAK,SND_CHAIN_CHUNKS_LP
2|ISLE16.WAD|SBP_ISLE16|blk|18|238128|SND_STONEPEDESTAL_LP,SND_STATUEWHOOSH,SND_STATUEHIT,SND_STATUE_ARMS_LP,SND_STATUE_ARMS_STOP,SND_STATUEHEAD_BOUNCE,SND_STATUEHEAD_ROLL_LP,SND_STATUESLIDE_LP,SND_AMPED1_LP,SND_AMPED2_LP,SND_AMPED3_LP,SND_AMPED4_LP,SND_GATE_HALFLOWER,SND_D_10E01GA,SND_AMB_UNDERWATER_LP,SND_AMB_INDOOR,SND_AMB_WIND_LP,SND_GLASS_SHATTER,SND_ARM_BREAK,SND_AMULET_RIP,SND_M_IS1601A,SND_M_IS1602Q,SND_M_IS1603A,SND_M_IS1604Q,SND_M_IS1605S,SND_M_IS1605E,SND_M_IS1606A,SND_D_10LAR,SND_D_8LAAR,SND_D_5LAAR,SND_D_7LAAR,SND_D_2LAAR,SND_PLANTER_IMPACT,SND_FOUNTAIN_LP
2|ISLE20.WAD|SBP_ISLE20|blk|30|417024|SND_AMB_SEA_LP,SND_BLINDER_BREAK,SND_HORSE_ELEVATOR,SND_HORSE_ELEV_STOP,SND_ROPEZIP_LP,SND_ROPEZIPNOISE_LP,SND_BLUEGLOW_LP,SND_HORSEEYE_LP,SND_METALGATE_OPEN,SND_BLUEGLOW_UNLOCK,SND_AMB_INDOOR_LP,SND_BINDERENERGY_LP,SND_D_11C01CR,SND_HORSE_SCREAMS,SND_ELEVATOR_DOWN,SND_ZIPLINE_LOWER,SND_GATE_LP,SND_DOORSLAM_OPEN,SND_DOORSLAM_SMALL,SND_DOOR_LP,SND_ORB_OPEN_LP,SND_ORB_CLOSE_LP,SND_CRANK_RAISE,SND_TIMER_1,SND_TIMER_2,SND_TIMER_3,SND_TIMER_4,SND_TIMER_5,SND_TIMER_6,SND_TIMER_7,SND_TIMER_8,SND_TIMER_9,SND_TIMER_10,SND_TIMER_11,SND_TIMER_12,SND_TIMER_13,SND_TIMER_14,SND_TIMER_15,SND_TIMER_16,SND_ZIPLINE_RAISE,SND_ARMBAND_RIP,SND_M_IS1202Q,SND_M_IS1203A,SND_M_IS2002C,SND_M_IS2003E,SND_M_IS2004A,SND_M_IS2005S,SND_M_IS2005E,SND_M_IS2006A,SND_M_IS2008S,SND_M_IS2008E,SND_M_IS1601A,SND_CRANK_LOWER,SND_M_IS2008C,SND_HORSE_ELEV_BAR,SND_FIRE_PUFF,SND_HORSE_ELEV_SWAY,SND_HORSE_ELEV_RUMBLE_L,SND_HORSE_ELEV_RIP,SND_D_02GAB,SND_ASS_GRAB,SND_ASS_SLIDE
2|ISLE30.WAD|SBP_ISLE30|blk|11|156864|SND_AMB_WIND_LP,SND_AMB_INDOOR_LP,SND_STATUESLIDE_LP,SND_STATUEHITGROUND,SND_FLOORGATE_LOOP,SND_ELEVATOR_LP,SND_EYEBEAM1_LP,SND_EYEBEAM2_LP,SND_DEFLECTBEAM,SND_FIREBALL,SND_FIREBALL_EXPLO,SND_FORCEFIELD_LP,SND_M_IS3001A,SND_M_IS1605E,SND_M_IS1606A,SND_M_IS3001Q,SND_M_IS3002A,SND_M_IS3003C,SND_M_IS3003E,SND_M_IS3004A,SND_M_IS3005A,SND_M_BG9002S,SND_M_BG9002E
2|ISLE40.WAD|SBP_ISLE40|blk|1|34048|SND_AMB_WIND_LP,SND_AMB_INDOOR_LP,SND_WATERFALL_LP,SND_WATERFALL2_LP,SND_M_IS3001A
2|ISLE42.WAD|SBP_ISLE42|blk|18|221776|SND_AMB_WIND_LP,SND_AMB_INDOOR_LP,SND_STATUESLIDE_LP,SND_STATUEHITGROUND,SND_STATUEHITLIGHT,SND_ROUND_ELEV_LP,SND_CHAINLOWER_LP,SND_BIGBLOCKSLIDE_LP,SND_BIGBLOCKHITGROUND,SND_ELEVATOR_STOP,SND_DEFLECTBEAM,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_D_13A01PE,SND_D_13A02PE,SND_D_13A03PE,SND_M_IS3001A,SND_M_IS4401E,SND_M_IS4503Q,SND_M_IS4201A,SND_M_IS4701A,SND_AMB_OUTDOOR_LP,SND_SLIDECHAIN_LP,SND_HANDGRAB_CHAIN,SND_FIREBALL,SND_SHIELD_SLAM,SND_EYEBEAM1_LP,SND_EYEBEAM2_LP,SND_FORCEFIELD_LP,SND_ASS_GRAB,SND_ASS_SLIDE
2|ISLE44.WAD|SBP_ISLE44|blk|12|135424|SND_AMB_WIND_LP,SND_AMB_INDOOR_LP,SND_BLOCKSLIDE_LP,SND_BLOCKHITGROUND,SND_SQUARE_ELEV_LP,SND_SQUARE_ELEV_STOP,SND_LIFTDOOR_SLAM,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_BLOCKHITLIGHT,SND_M_IS3001A,SND_M_IS4401C,SND_M_IS4401E,SND_M_IS4402A,SND_M_IS4201A,SND_M_IS4501S,SND_LIFTDOORLOCK,SND_M_IS4601S
2|ISLE45.WAD|SBP_ISLE45|blk|9|160704|SND_AMB_WIND_LP,SND_AMB_INDOOR_LP,SND_BIGDOORKICK_2,SND_BIGDOORKICK,SND_STATUESLIDE_LP,SND_STATUEHITGROUND,SND_STATUEHITLIGHT,SND_M_IS4402A,SND_M_IS4501S,SND_M_IS4502I,SND_M_IS4502C,SND_M_IS4502E,SND_M_IS4503Q,SND_M_IS4201A,SND_H_ISLE45
2|ISLE46.WAD|SBP_ISLE46|blk|13|176400|SND_AMB_WIND_LP,SND_AMB_INDOOR_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOOR_SLAM,SND_SHIELD_PICKUP,SND_BRIDGE1_LP,SND_BRIDGE2_LP,SND_BRIDGE3_LP,SND_BRIDGE4_LP,SND_WOOD_PEDESTAL_LP,SND_M_IS4201A,SND_M_IS4601S,SND_M_IS4601E,SND_LIFTDOORLOCK,SND_M_IS4502C,SND_M_IS4502I
2|ISLE47.WAD|SBP_ISLE47|blk|8|133152|SND_AMB_WIND_LP,SND_AMB_INDOOR_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOOR_SLAM,SND_SHIELD_PICKUP,SND_WOOD_PEDESTAL_LP,SND_M_IS4601E,SND_M_IS4701C,SND_M_IS4701E,SND_M_IS4701A,SND_D_13C01PE,SND_D_13C02PE,SND_D_13C03PE,SND_D_13C04PE,SND_D_13C06PE,SND_D_13C08PE,SND_D_13C09PE,SND_D_13C10PE,SND_D_13C11PE,SND_D_13C13PE,SND_D_13C14PE,SND_D_13C15PE,SND_D_13C16PE,SND_D_13C17PE,SND_D_13C19PE,SND_D_13C20APE,SND_D_PRS_TAUNT,SND_M_BG21001A,SND_LIFTDOORLOCK,SND_M_IS4601S
2|PAL05.WAD|SBP_PAL05|blk|9|126880|SND_ROOM_CRANK_LP,SND_ROOM_STOP,SND_GATE_LP,SND_STONEPEDESTAL_LP,SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_M_PA0501S,SND_M_PA0502C,SND_M_PA0502E,SND_M_PA0503A,SND_M_AT25004Q
2|PAL10.WAD|SBP_PAL10|blk|14|179792|SND_LARGE_PUSHPULL_LP,SND_ROOM_AUTO_LP,SND_ROOM_STOP,SND_SPIKES_WARNING,SND_SPIKES_OUT,SND_SPIKES_IN,SND_GATE_LP,SND_PEDESTALGATE_LP,SND_AMB_INDOOR_LP,SND_STONEDOOR_LOOP,SND_STONEPEDESTAL_LP,SND_ROOMSPEARS1,SND_ROOMSPEARS2,SND_ROOMSPEARS3,SND_M_PA0503A,SND_M_PA1001S,SND_M_PA1001E,SND_M_PA1002A
2|PAL15.WAD|SBP_PAL15|blk|18|283136|SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_STONEPEDESTAL_LP,SND_M_PA1002A,SND_M_PA2503A,SND_M_PA4002A,SND_FLOORPLATE_LP,SND_STEAMVENT_LP,SND_GEARSPIN_L_START,SND_GEARSPIN_R_START,SND_GEARSPIN_L_END,SND_GEARSPIN_R_END,SND_STONEDOOR_LOOP,SND_FLAME_L_LP,SND_FLAME_R_LP,SND_ERRUPTION_LP,SND_GIANTHORN_LP,SND_INSERT_EYE,SND_FACEDOOR_LP,SND_ELEVATOR_LP,SND_M_PA1501Q,SND_M_PA4004A,SND_M_PA1503C,SND_M_PA1503E,SND_M_PA1504A,SND_M_PA1505A,SND_M_PA1506A,SND_M_PA1701S,SND_H_PAL15A,SND_ASS_GRAB,SND_ASS_SLIDE,SND_M_PA8003S,SND_M_PA1510S
2|PAL17.WAD|SBP_PAL17|blk|11|183936|SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_STONEPEDESTAL_LP,SND_M_PA1701S,SND_M_PA1702C,SND_M_PA1702E,SND_FLOORPLATE_LP,SND_STEAMVENT_LP,SND_GEARSPIN_L_START,SND_GEARSPIN_R_START,SND_GEARSPIN_L_END,SND_GEARSPIN_R_END,SND_GLASS_SMASH,SND_D_YS01,SND_BRIDGE_SHOOT,SND_M_PA1703A,SND_M_PA1704C,SND_D_19D03KR,SND_D_19D04KR,SND_D_19D05AKR,SND_D_19D05BKR,SND_M_PA1506A,SND_M_PA1705C,SND_M_PA1706C,SND_M_PA1705T
2|PAL20.WAD|SBP_PAL20|blk|10|120176|SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_M_PA1002A,SND_GATEDOWN_LP,SND_GATEUP_LP,SND_STEAMVENT_LP,SND_M_PA2503A,SND_M_PA1510E,SND_M_PA1510S
2|PAL25.WAD|SBP_PAL25|blk|19|230720|SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_GATE_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_STONEDOOR_LOOP,SND_WATERFALL1_LP,SND_WATERFALL2_LP,SND_D_16G01KR,SND_D_16G08KR,SND_D_16G10KR,SND_D_16G13KR,SND_D_16G15KR,SND_D_16G03TR,SND_D_TRRAND,SND_D_16G06TR,SND_D_16G07TR,SND_D_16G09TR,SND_D_16G11TR,SND_D_16G12TR,SND_D_16G17TR,SND_D_HESTRUG_LP,SND_D_HESTRUG,SND_M_PA2502C,SND_M_PA2502E,SND_M_PA2503A,SND_D_T101,SND_D_T102,SND_D_T106,SND_D_T107,SND_D_T108,SND_D_T110,SND_D_T111,SND_D_T112_ALT,SND_D_T113_ALT,SND_D_T114,SND_D_T115,SND_BLOCKSLIDE_LP,SND_BLOCKHITGROUND,SND_D_TRRANDOM,SND_D_16G14KR,SND_M_PA2504A,SND_M_PA2505A
2|PAL30.WAD|SBP_PAL30|blk|17|204400|SND_AMB_INDOOR_LP,SND_GATE_PUSH_LP,SND_GATE_CRUSH,SND_M_PA2503A,SND_M_PA3001C,SND_M_PA3001E,SND_M_PA3002A,SND_AMB_WIND_LP,SND_GEARTURN_LP,SND_M_PA2505A,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_D_5LAAR
2|PAL40.WAD|SBP_PAL40|blk|18|265920|SND_AMB_INDOOR_LP,SND_AMB_UNDERWATER_LP,SND_AMB_WIND_LP,SND_FLAME_1L_LP,SND_FLAME_1R_LP,SND_FLAME_2L_LP,SND_FLAME_2R_LP,SND_FLAME_3L_LP,SND_FLAME_3R_LP,SND_SACRIFICE,SND_D_18H01TN,SND_D_18H02TN,SND_D_18H04TN,SND_D_18H05TN,SND_D_18H07TN,SND_D_18H03KR,SND_D_18H04KR,SND_D_18H07KR,SND_PORTAL_LP,SND_TELEPORT,SND_GATE_LP,SND_POUND_DOOR_LP,SND_PUSHPULL_LP,SND_D_18G01TN,SND_D_18G02TN,SND_M_PA3002A,SND_M_PA4001C,SND_M_PA4001E,SND_M_PA4002A,SND_D_T208,SND_D_T207,SND_D_T206,SND_D_T205,SND_D_T204,SND_D_T203,SND_D_T202,SND_D_T201,SND_D_T209,SND_D_TRRANDOM,SND_M_PA4003A,SND_M_PA4003S,SND_M_PA4004A,SND_M_PA4504S,SND_CHAIN_SNAP,SND_HANDGRAB_CHAIN,SND_SLIDECHAIN_LP,SND_ASS_GRAB,SND_ASS_SLIDE,SND_M_PA4505E,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_SAC_DOOR_LP
2|PAL45.WAD|SBP_PAL45|blk|18|294560|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_RING_TURN_LP,SND_RING_TURN_STOP,SND_PUSHPULL_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_STONEGRIND_LP,SND_CHAIN_LP,SND_M_PA4501S,SND_M_PA4501E,SND_M_PA4502C,SND_M_PA4502E,SND_M_PA4503S,SND_M_PA4503E,SND_DOOR_MELT,SND_LIGHT_REFLECT,SND_LIGHT_SHINE,SND_ICE_MELT,SND_PHEONIX_TORCH_LP,SND_TORCHSOUNDS_LP,SND_FLOOR_RAISE_LP,SND_FLOOR_STOP,SND_WATER_DRIP_LP,SND_M_PA4504A,SND_M_PA4003S,SND_M_PA4504S,SND_M_PA4002A
2|PAL50.WAD|SBP_PAL50|blk|4|37072|SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_AMB_INDOOR2_LP,SND_M_PA5001C,SND_M_PA5001E,SND_M_PA4002A,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_M_PA4003A
2|PAL55.WAD|SBP_PAL55|blk|8|113840|SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_STEAMVENT_LP,SND_STEAMVENT_HEAVY_LP,SND_ELEVATOR_LP,SND_ELEVATOR_STOP,SND_M_PA4002A,SND_VENTDOOR_LP,SND_VENTDOOR_STOP,SND_TILE_BREAK,SND_M_PA4004A
2|PAL60.WAD|SBP_PAL60|blk|15|227808|SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_M_PA4002A,SND_M_PA6001S,SND_M_PA6001E,SND_BIGFIRE1_LP,SND_BIGFIRE2_LP,SND_BIGFIRE3_LP,SND_BIGFIRE4_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_FLOOR_LP,SND_CEILING_LP,SND_CEILING_DROP,SND_CEILING_SHAKE,SND_FLOOR_STOP,SND_M_PA1504A,SND_M_PA7001S
2|PAL70.WAD|SBP_PAL70|blk|8|109872|SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_STEAMVENT_LP,SND_M_PA7001S,SND_M_PA7001E,SND_M_PA7002A,SND_LAVA_LP,SND_M_PA8001S,SND_ASS_GRAB
2|PAL80.WAD|SBP_PAL80|blk|12|207216|SND_AMB_WIND_LP,SND_AMB_INDOOR_LP,SND_BIGTHINGSPIN_LP,SND_GLOPS,SND_ERRUPTION,SND_STEAMVENT_LP,SND_CLAWCONVEYOR_LP,SND_M_PA8501S,SND_M_PA7002A,SND_AMB_INDOOR2_LP,SND_ELEVATOR_LP,SND_VASE_SET,SND_ERRUPTION_LP,SND_LAVA_LP,SND_VASE_PUSHPULL_LP,SND_VASE_DROPLAVA,SND_D_GA19,SND_M_PA8001S,SND_M_PA8505Q,SND_M_PA8002C,SND_M_PA8002E,SND_M_PA8003S,SND_M_PA7001E,SND_M_PA7001S
2|PAL85.WAD|SBP_PAL85|blk|20|257536|SND_AMB_INDOOR2_LP,SND_FIREBLOCK_LP,SND_FIREWALL_L_LP,SND_FIREWALL_1_LP,SND_FIREWALL_2_LP,SND_PUSHPULL_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_L,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_M_PA8501S,SND_GATE_LP,SND_FLOORSTEP_LP,SND_FLOORSPIKES_IN,SND_FLOORSPIKES_OUT,SND_ROOMSPEARS1,SND_ROOMSPEARS2,SND_ROOMSPEARS3,SND_SPEARS_DN1,SND_SPEARS_DN2,SND_SPEARS_DN3,SND_AMB_INDOOR_LP,SND_STATUE_RISE_LP,SND_TIMER_CLICK,SND_TIMER_END,SND_STONEPEDESTAL_LP,SND_M_PA8001S,SND_M_PA8502E,SND_M_PA8503A,SND_M_PA8504S,SND_M_PA8504E,SND_M_PA8505Q
2|PAL90.WAD|SBP_PAL90|blk|10|136752|SND_AMB_WIND_LP,SND_AMB_INDOOR_LP,SND_ERRUPTION_LP,SND_M_PA8003S,SND_PHOENIX_VOCAL,SND_PHOENIX_VOCAL_A,SND_PHOENIX_FLAP_UP,SND_PHOENIX_FLAP_DN,SND_ELEVATOR_LP
2|PAL95.WAD|SBP_PAL95|blk|9|131104|SND_AMB_WIND_LP,SND_AMB_INDOOR_LP,SND_BLOCK_ELEVATOR_LP,SND_BLOCK_ELEV_STOP,SND_CHAIN_BREAK,SND_GATE_LP,SND_COLUMN_RAISE_LP,SND_ROOM_TURN_LP,SND_ROOM_TURN_STOP,SND_BLOCKSLIDE_LP,SND_BLOCKHITGROUND,SND_M_PA1506A
2|PEGA10.WAD|SBP_PEGA10|blk|6|195024|SND_AMB_OUTDOOR_LP,SND_M_PG1001Q,SND_M_PG1002C,SND_M_PG3001E,SND_M_PG3002Q,SND_M_RH5002A,SND_D_8D01GA,SND_D_GA20,SND_THUNDER,SND_WIND_LP,SND_WINDTUNNEL_LP,SND_WIND_MEDIUM,SND_WIND_HEAVY
2|PEGA30.WAD|SBP_PEGA30|blk|7|171408|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_AMB_OUTDOOR_LP,SND_M_PG3002Q,SND_M_PG3001E,SND_M_PG4001S,SND_M_PG1002C,SND_M_PG3003Q,SND_WATERFALL_L_LP,SND_WATERFALL_R_LP,SND_TYPHON_MOVE,SND_WIND_LP,SND_D_TYFLBY08
2|PEGA35.WAD|SBP_PEGA35|blk|17|234832|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_BIGFIRE_LP,SND_TYPHON_GRABGROUND,SND_TYPHON_MOVE,SND_M_PG3001E,SND_M_PG3002Q,SND_M_PG4001S,SND_TYPHON_MOVE_2,SND_M_PG3003Q,SND_M_PG3004A,SND_TYPHON_INHALE_LP,SND_TYPHON_WINDFX_LP,SND_TYPHON_BREATH_LP,SND_ROCK_LP
2|PEGA40.WAD|SBP_PEGA40|blk|5|128256|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_M_PG3002Q,SND_M_PG4001S,SND_M_PG4001E,SND_M_PG4201A,SND_M_PG4501C,SND_M_PG4202S,SND_M_PG4002E,SND_M_PG6001A,SND_M_PG3003Q,SND_D_GA09,SND_D_GA04,SND_TYPHON_GRABGROUND,SND_TYPHON_FINGER_JAB,SND_TYPHON_FINGER_MOVE
2|PEGA42.WAD|SBP_PEGA42|blk|8|68960|SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_M_PG4001S,SND_M_PG4001E,SND_M_PG4201A,SND_M_PG4501C,SND_M_PG4504A,SND_M_PG4202S,SND_M_PG4002E,SND_M_PG6001A,SND_SLIDECHAIN_LP,SND_WATER_DRIP_LP,SND_WATER_DRIP_SLOW_LP,SND_ASS_GRAB,SND_ASS_SLIDE
2|PEGA45.WAD|SBP_PEGA45|blk|19|154272|SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_D_GA03,SND_D_GA01,SND_D_PR04,SND_D_PR03,SND_D_PRRANDOM,SND_M_PG4201A,SND_M_PG4501C,SND_M_PG4501E,SND_M_PG4502S,SND_M_PG4502E,SND_M_PG4503A,SND_M_PG5001C,SND_M_PG5005S,SND_M_PG4503C,SND_M_PG4503E,SND_M_PG4504A,SND_M_PG4202S,SND_BIGFIRE_LP,SND_SLIDECHAIN_LP,SND_SLIDECHAIN_SLOW_LP,SND_HANDGRAB_CHAIN,SND_CHAINSNAP_LARGE,SND_CHAIN_BODYFALL,SND_CHAIN_RAISE_LP,SND_WOOD_FALL,SND_CHAIN_FALL,SND_STONEDOOR_LOOP,SND_HANDGRAB_CHAIN_LARG,SND_ASS_SLIDE,SND_ASS_GRAB,SND_CHAIN_YANK,SND_PROM_CHOKE,SND_PROM_VOGETHIT,SND_PROM_VOGETHIT_A
2|PEGA47.WAD|SBP_PEGA47|blk|10|90016|SND_AMB_INDOOR_LP,SND_AMB_WIND_LP,SND_M_PG4503A,SND_M_PG5001C,SND_M_PG5005S,SND_M_PG4503C,SND_M_PG4502S,SND_M_PG5002A,SND_SLIDECHAIN_LP,SND_GATE_LP,SND_WATER_DRIP_LP,SND_WATER_DRIP_SLOW_LP,SND_ASS_GRAB,SND_ASS_SLIDE
2|PEGA50.WAD|SBP_PEGA50|blk|21|238560|SND_AMB_INDOOR_LP,SND_M_PG4503A,SND_M_PG5001C,SND_M_PG5001E,SND_M_PG5002A,SND_M_PG5003I,SND_M_PG5003C,SND_M_PG5003E,SND_M_PG5004C,SND_M_PG5004E,SND_M_PG5005S,SND_M_PG4503C,SND_D_TYP006,SND_D_TYP008,SND_D_TYP012,SND_D_TYP023,SND_D_TYP024,SND_D_TYP02402,SND_TYPHON_INHALE_LP,SND_TYPHON_WINDFX_LP,SND_TYPHON_BREATH_LP,SND_ROCK_LP,SND_WATERFALL_LOOP,SND_STAL_BREAK_LP,SND_STAL_SMASH,SND_STAL_BRIDGE_HIT,SND_BOW_DRAW,SND_EYE_RIP,SND_BRIDGE_RUMBLE_LP,SND_LOW_RUMBLE_LP
2|PEGA52.WAD|SBP_PEGA52|blk|5|104128|SND_AMB_INDOOR_LP,SND_BIGFIRE_LP,SND_FIRE_PUFF,SND_ICE_MELT
2|PEGA70.WAD|SBP_PEGA70|blk|5|151760|SND_AMB_OUTDOOR_LP,SND_M_PG6001A,SND_M_PG7001C,SND_M_PG7901C,SND_M_PG7901E,SND_M_PG7001E,SND_WIND_LP,SND_THUNDER
2|PEGA79.WAD|SBP_PEGA79|blk|6|167728|SND_AMB_OUTDOOR_LP,SND_M_PG7001C,SND_M_PG7901C,SND_M_PG7901E,SND_M_PG7001E,SND_M_IS0601A,SND_WINDTUNNEL_LP,SND_WIND_MEDIUM,SND_WIND_HEAVY,SND_THUNDER_LP,SND_WIND_LP
2|RHOD10.WAD|SBP_RHOD10|blk|20|309616|SND_AMB_DISTBATTLE,SND_AMB_MEDBATTLE,SND_M_RH1001C,SND_M_RH1001E,SND_M_RH1002S,SND_M_RH1501C,SND_M_RH1503A,SND_D_3B06DG,SND_D_3B09DG,SND_D_DG_RNDM_1,SND_D_DG_RNDM_2,SND_D_SOL_AMB_LP,SND_D_3A02KR,SND_D_1A01NA,SND_D_KRCMBT04,SND_D_KRCMBT03,SND_D_KRCMBT02,SND_D_KRCMBT01,SND_D_RSB08,SND_D_DRSB04,SND_D_RSB02,SND_D_RSA08,SND_D_RSA05,SND_D_RSA03,SND_D_RSA01,SND_D_SSB04,SND_D_SS04,SND_D_SS03,SND_D_SS02,SND_D_KRCMBTRAN,SND_D_KR15,SND_D_RSCWILD1,SND_D_RSCWILD2,SND_D_RSCWILD4,SND_D_SRAND10,SND_BIGDOOR_BREAK,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_COL_GROUNDHITHARD,SND_BOULDERSMASH,SND_COL_SHAKEGROUND,SND_COL_GRAB_HEAVY,SND_COL_GRAB_LIGHT,SND_CATAPULT_LOAD_LP,SND_CATAPULT_LAUNCH,SND_CATAPULT_FAIL,SND_COL_GROUNDHIT,SND_HAND_SCRAPEROCK,SND_GROUNDRIP_LP,SND_GLASS_SMASH,SND_COL_BUILDINGHIT,SND_COL_FOOTSTEP
2|RHOD15.WAD|SBP_RHOD15|blk|10|127712|SND_AMB_INDOOR_LP,SND_AMB_UNDERWATER_LP,SND_AMB_MEDBATTLE,SND_M_RH1503A,SND_M_RH1501C,SND_D_BH1_08,SND_D_BH1_06,SND_D_BH1_05,SND_D_BH1_02,SND_D_BH1_01,SND_D_BP2_07,SND_D_BP2_06,SND_D_BP2_05,SND_D_BP2_01,SND_D_BP_FAIL,SND_D_BP_HI,SND_D_BP_PRAISE,SND_D_BHRANDOM,SND_D_IWAS,SND_D_KRCMBTRAN,SND_WOMEN_IDLE_LP,SND_WOMEN_SEX_VO,SND_DASHDOOR_BREAK,SND_FOUNTAIN_LP,SND_FOUNTAIN_SHOT,SND_FOUNTAIN_BLOW
2|RHOD16.WAD|SBP_RHOD16|blk|11|189392|SND_AMB_INDOOR_LP,SND_AMB_UNDERWATER_LP,SND_AMB_INDOOR2_LP,SND_M_RH1503A,SND_M_RH2001S,SND_D_KRCMBTRAN,SND_CONVEYOR_LP,SND_WATERFALL_LP,SND_BIGFIRE1_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_WATERWHEEL_LP
2|RHOD20.WAD|SBP_RHOD20|blk|14|241936|SND_AMB_INDOOR2_LP,SND_AMB_MEDBATTLE,SND_AMB_INDOOR_LP,SND_M_RH1503A,SND_M_RH2001S,SND_M_RH2002Q,SND_M_RH2301S,SND_D_KRCMBTRAN,SND_D_RSA05,SND_D_SOL00511,SND_COL_GROUNDHITHARD,SND_COL_FOOTSMASH,SND_COL_GROUNDHIT,SND_BOULDERSMASH,SND_FALLING_DEBRIS,SND_WALLSMASH,SND_WATERFALL_LOW_LP,SND_WATERFALL_HIGH_LP,SND_GEARSPIN_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM
2|RHOD23.WAD|SBP_RHOD23|blk|8|154336|SND_AMB_INDOOR2_LP,SND_AMB_MEDBATTLE,SND_COL_GROUNDHITHARD,SND_COL_GRAB_HEAVY,SND_COL_GRAB_LIGHT,SND_M_RH2301S,SND_M_RH2302Q,SND_M_RH2501A,SND_COL_GROUNDHIT,SND_WATERWHEEL_SMASH,SND_BIGWOODSMASH,SND_D_KRCMBTRAN
2|RHOD24.WAD|SBP_RHOD24|blk|8|90640|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_AMB_DISTBATTLE,SND_AMB_MEDBATTLE,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_M_RH2501A,SND_D_KRCMBTRAN
2|RHOD25.WAD|SBP_RHOD25|blk|24|313248|SND_AMB_INDOOR_LP,SND_AMB_INDOOR2_LP,SND_AMB_DISTBATTLE,SND_AMB_MEDBATTLE,SND_M_RH2501A,SND_D_KRCMBTRAN,SND_D_RSCWILD2,SND_D_RSA05,SND_D_RSA03,SND_STONEPEDESTAL_LP,SND_GATE_LP,SND_GATE_SLAMSHUT,SND_BLOCK_ELEVATOR_LP,SND_BLOCK_ELEV_STOP,SND_PUSHPULL_LP,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_COL_MVMNT_LP,SND_COL_MVMNT2_LP,SND_ASS_GRAB,SND_ASS_SLIDE
2|RHOD27.WAD|SBP_RHOD27|blk|11|152048|SND_AMB_INDOOR_LP,SND_AMB_DISTBATTLE,SND_AMB_MEDBATTLE,SND_AMB_INDOOR2_LP,SND_M_RH2501A,SND_M_RH2701Q,SND_M_RH2702Q,SND_M_RH2703C,SND_M_RH2703E,SND_M_RH3001C,SND_D_5A07ZE,SND_D_ZE12,SND_D_SRAND27,SND_D_KRCMBTRAN,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM,SND_BIGDOORKICK,SND_BUILDING_TEETER,SND_BUILDING_HITGROUND,SND_BUILDING_SLAM,SND_BUILDING_SLAM2,SND_BUILDINGRUMBLE_LP,SND_COL_GROUNDHITHARD,SND_COL_GROUNDHIT,SND_COL_GRAB_HEAVY,SND_GLASS_SMASH
2|RHOD30.WAD|SBP_RHOD30|blk|12|230480|SND_AMB_INDOOR_LP,SND_AMB_DISTBATTLE,SND_AMB_MEDBATTLE,SND_M_RH3001C,SND_M_RH3001E,SND_D_ZE14,SND_D_KRCMBTRAN,SND_BRIDGE_SMASH,SND_FALLING_DEBRIS,SND_GROUNDRIP,SND_GROUNDEXPLO,SND_GROUNDRIP_LP,SND_BIGFIRE1_LP,SND_COL_GROUNDHITHARD,SND_COL_GROUNDHIT,SND_SWORDJAM,SND_SWORDPULL,SND_COL_FLAMETHROW_LP,SND_COL_FLAMETHROW_LP2
2|RHOD40.WAD|SBP_RHOD40|blk|21|286976|SND_AMB_DISTBATTLE,SND_AMB_MEDBATTLE,SND_AMB_INDOOR_LP,SND_WOOD_LAND,SND_FALLING_OBJECT_LP,SND_WOOD_SHATTER,SND_BIG_OBJECT_SMASH,SND_BIGFIRE_LP,SND_SMALLFIRE_LP,SND_BAG_SMASH,SND_M_RH3001C,SND_M_RH3001E,SND_M_RH4001S,SND_M_RH4002S,SND_COL_STEP,SND_CHAIN_BREAK,SND_M_RH4003C,SND_D_KRCMBTRAN,SND_D_SRAND40,SND_ASS_GRAB,SND_ASS_SLIDE,SND_STRUT_SHATTER,SND_WOOD_BREAKING_2,SND_ELECTRICAL_HIT,SND_COL_VOGETHITIN
2|RHOD45.WAD|SBP_RHOD45|blk|42|485872|SND_AMB_DISTBATTLE,SND_AMB_MEDBATTLE,SND_AMB_INDOOR_LP,SND_WOOD_LAND,SND_FALLING_OBJECT_LP,SND_BIGFIRE_LP,SND_SMALLFIRE_LP,SND_BAG_SMASH,SND_COL_STEP,SND_BEAM1_LP,SND_BEAM2_LP,SND_Beam_1,SND_Beam_2,SND_ARC,SND_BEAM_DEFLECT,SND_GEARS_TURN_LP,SND_PENDULUM_SWING,SND_SWORDJAM,SND_SWORDJAM_FINAL,SND_CHAIN_BREAK,SND_D_KRCMBTRAN,SND_M_RH4003C,SND_BIG_OBJECT_SMASH,SND_M_RH4002S,SND_WOOD_BREAKING,SND_WOOD_BREAKING_2,SND_COL_VOGETHITBIG,SND_ASS_GRAB,SND_ASS_SLIDE
2|RHOD50.WAD|SBP_RHOD50|blk|18|195392|SND_AMB_OUTDOOR_LP,SND_AMB_DISTBATTLE,SND_AMB_MEDBATTLE,SND_M_RH5006C,SND_M_RH5002A,SND_M_PG1002C,SND_M_PG1001Q,SND_M_RH5501C,SND_M_RH5001E,SND_M_RH4003C,SND_D_05D02S1,SND_D_05D01S1,SND_D_05D03S2,SND_D_5F01ZE,SND_D_5F03ZE,SND_D_5F02KR,SND_D_05D04S7,SND_D_6C01YS,SND_D_6C03YS,SND_D_6C05YS,SND_D_6C02KR,SND_D_6C04KR,SND_D_6C07KR,SND_D_6C06KR,SND_D_KRCMBTRAN,SND_D_YGOD,SND_WOOD_LAND,SND_FALLING_OBJECT_LP,SND_HOLE_CLOSE
2|RHOD55.WAD|SBP_RHOD55|blk|12|120944|SND_AMB_DISTBATTLE,SND_AMB_MEDBATTLE,SND_AMB_INDOOR_LP,SND_AMB_OUTDOOR_LP,SND_ARM_SWING,SND_M_RH5501C,SND_M_RH5001E,SND_D_KRCMBTRAN,SND_TORNADO_LP
2|R_ARCHER00.WAD|SBP_ARCHER00|blk|12|93920|SND_ARCHER00_WHSH_F,SND_ARCHER00_WHSH_S,SND_ARCHER00_BOWPULL,SND_ARCHER00_BOWFIRE,SND_ARCHER00_TAUNT01,SND_ARCHER00_TAUNT02,SND_ARCHER00_TOSSYELL,SND_ARCHER00_VOSPAWN,SND_ARCHER00_VOCHOKE,SND_ARCHER00_VODIE,SND_ARCHER00_VORIPDIE,SND_ARCHER00_VOFLYBACK,SND_ARCHER00_VOATTK,SND_ARCHER00_VOATTK_R,SND_ARCHER00_VOGETHIT,SND_ARCHER00_VOWINDUPA,SND_ARCHER00_VOWINDUPB,SND_ARCHER00_VOWINDUPC,SND_ARROWFIRE_LP
2|R_ARCHER10.WAD|SBP_ARCHER10|blk|12|93872|SND_ARCHER10_WHSH_F,SND_ARCHER10_WHSH_S,SND_ARCHER10_BOWPULL,SND_ARCHER10_BOWFIRE,SND_ARCHER10_TAUNT01,SND_ARCHER10_TAUNT02,SND_ARCHER10_TOSSYELL,SND_ARCHER10_VOSPAWN,SND_ARCHER10_VOCHOKE,SND_ARCHER10_VODIE,SND_ARCHER10_VORIPDIE,SND_ARCHER10_VOFLYBACK,SND_ARCHER10_VOATTK,SND_ARCHER10_VOATTK_R,SND_ARCHER10_VOGETHIT,SND_ARCHER10_VOWINDUPA,SND_ARCHER10_VOWINDUPB,SND_ARCHER10_VOWINDUPC
2|R_BARBARIAN.WAD|SBP_BARKING|blk|23|229552|SND_BKH_ATTK,SND_BKH_GETHIT,SND_BKH_DEATH,SND_BKH_REAR,SND_BKH_SNORT,SND_BKH_HOOF,SND_BK_ARFIRE,SND_BK_HMRDRAG,SND_BK_STEP_REG,SND_BK_STEP_LRG,SND_BK_BIGATTK,SND_BK_FSTATT_A,SND_BK_FSTATTK,SND_BK_BIGATT_A,SND_BK_HURT,SND_BK_HURT_A,SND_BK_STRGLS,SND_BK_STRGREL,SND_BK_TAUNT,SND_BK_DEATH,SND_BOATCAP_VOGRAB,SND_BOATCAP_VODIE,SND_BK_GROW
2|R_BKARMY00.WAD|SBP_BKARMY|blk|14|97360|SND_BKARMY_SWORDWHS,SND_BKARMY_VOATTK,SND_BKARMY_VOATTKA,SND_BKARMY_VOGETHT,SND_BKARMY_VOGETHTA,SND_BKARMY_VOWINDUP,SND_BKARMY_VODIE,SND_BKARMY_TAUNT,SND_BKARMY_STRUG_LP
2|R_BOAR00.WAD|SBP_BOAR|blk|9|61568|SND_BOAR_VO_GRUNT,SND_BOAR_VO_ATTACK,SND_BOAR_VO_DIE,SND_BOAR_VO_GETHIT,SND_BOAR_VO_GETHITA,SND_BOAR_VO_SCREAM,SND_BOAR_VO_TAUNT
2|R_BONES00.WAD|SBP_BONES|blk|13|109200|SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_BONES_STEPRUN,SND_BONES_STEPWALK,SND_BONES_SWING,SND_BONES_SMASH,SND_BONES_DIE,SND_BONES_SPAWN,SND_BONES_CACKLE,SND_BONES_VODIE,SND_BONES_VOATTACK,SND_BONES_VOGETHIT,SND_BONES_VOTAUNT
2|R_BUG10.WAD|SBP_BUG10|blk|7|98448|SND_BUG10_VOATTK,SND_BUG10_VOGETHIT,SND_BUG10_VOGETHITA,SND_BUG10_VODIE,SND_BUG10_SPIT,SND_BUG10_IMPACT,SND_BUG10_WEB,SND_BUG10_WING_LP
2|R_BUG20.WAD|SBP_BUG20|blk|8|93040|SND_BUG20_VOATTK,SND_BUG20_VOGETHIT,SND_BUG20_VOGETHITA,SND_BUG20_VODIE,SND_BUG20_FIRESHOT,SND_BUG20_FIREHIT,SND_BUG20_WING_LP
2|R_CAPTAN00.WAD|SBP_CAPTAN00|blk|10|98192|SND_CAPTAN00_SCYTHE_F,SND_CAPTAN00_SCYTHE_S,SND_CAPTAN00_SWORD_F,SND_CAPTAN00_SWORD_S,SND_CAPTAN00_VOWINDUPA,SND_CAPTAN00_VOWINDUPB,SND_CAPTAN00_VODIE,SND_CAPTAN00_VOCSDIE,SND_CAPTAN00_VOTOSS,SND_CAPTAN00_VOFLYBACK,SND_CAPTAN00_VOTAUNT,SND_CAPTAN00_VOGETHIT,SND_CAPTAN00_VOATTK,SND_CAPTAN00_VOATTK_R
2|R_CAPTAN10.WAD|SBP_CAPTAN10|blk|10|98192|SND_CAPTAN10_SCYTHE_F,SND_CAPTAN10_SCYTHE_S,SND_CAPTAN10_SWORD_F,SND_CAPTAN10_SWORD_S,SND_CAPTAN10_VOWINDUPA,SND_CAPTAN10_VOWINDUPB,SND_CAPTAN10_VODIE,SND_CAPTAN10_VOCSDIE,SND_CAPTAN10_VOTOSS,SND_CAPTAN10_VOFLYBACK,SND_CAPTAN10_VOTAUNT,SND_CAPTAN10_VOGETHIT,SND_CAPTAN10_VOATTK,SND_CAPTAN10_VOATTK_R
2|R_CERBUS00.WAD|SBP_CERBUS00|blk|16|150064|SND_CERBUS00_WINDUP_A,SND_CERBUS00_WINDUP_B,SND_CERBUS00_VOSNARL,SND_CERBUS00_VOSNRL_LP,SND_CERBUS00_VOBARK,SND_CERBUS00_VOTAUNT,SND_CERBUS00_VOSLASH,SND_CERBUS00_VOSWIPE,SND_CERBUS00_VOSNAP,SND_CERBUS00_VOGETHIT,SND_CERBUS00_VOGETHIT2,SND_CERBUS00_VODIE,SND_CERBUS00_VOHEADRIP,SND_CERBUS00_VOHEDSTAB,SND_CERBUS00_STEPWALK,SND_CERBUS00_STEPLAND,SND_CERBUS00_CLAWSWIPE,SND_CERBUS00_CLAWSLASH,SND_CERBUS00_FBALLSHOT,SND_CERBUS00_FBALLHIT,SND_CERBUS00_FBALLBLK
2|R_CERBUS10.WAD|SBP_CERBUS10|blk|16|150064|SND_CERBUS10_WINDUP_A,SND_CERBUS10_WINDUP_B,SND_CERBUS10_VOSNARL,SND_CERBUS10_VOSNRL_LP,SND_CERBUS10_VOBARK,SND_CERBUS10_VOTAUNT,SND_CERBUS10_VOSLASH,SND_CERBUS10_VOSWIPE,SND_CERBUS10_VOSNAP,SND_CERBUS10_VOGETHIT,SND_CERBUS10_VOGETHIT2,SND_CERBUS10_VODIE,SND_CERBUS10_VOHEADRIP,SND_CERBUS10_VOHEDSTAB,SND_CERBUS10_STEPWALK,SND_CERBUS10_STEPLAND,SND_CERBUS10_CLAWSWIPE,SND_CERBUS10_CLAWSLASH,SND_CERBUS10_FBALLSHOT,SND_CERBUS10_FBALLHIT,SND_CERBUS10_FBALLBLK
2|R_CERBUS20.WAD|SBP_CERBUS20|blk|16|157632|SND_CERBUS20_WINDUP_A,SND_CERBUS20_WINDUP_B,SND_CERBUS20_VOSNARL,SND_CERBUS20_VOSNRL_LP,SND_CERBUS20_VOBARK,SND_CERBUS20_VOTAUNT,SND_CERBUS20_VOSLASH,SND_CERBUS20_VOSWIPE,SND_CERBUS20_VOSNAP,SND_CERBUS20_VOGETHIT,SND_CERBUS20_VOGETHIT2,SND_CERBUS20_VODIE,SND_CERBUS20_VOHEADRIP,SND_CERBUS20_VOHEDSTAB,SND_CERBUS20_STEPWALK,SND_CERBUS20_STEPLAND,SND_CERBUS20_CLAWSWIPE,SND_CERBUS20_CLAWSLASH,SND_CERBUS20_FBALLSHOT,SND_CERBUS20_FBALLHIT,SND_CERBUS20_FBALLBLK,SND_CERBUS20_FLAME_LP
2|R_CERPUP00.WAD|SBP_CERPUP00|blk|10|102272|SND_CERP00_STEPLIGHT,SND_CERP00_STEPHEAVY,SND_CERP00_STEPLAND,SND_CERP00_HEADSTOMP,SND_TRANSFORM_A,SND_TRANSFORM_B,SND_SNARL,SND_BREATH,SND_FLIPATTK,SND_CERP00_VOATTACK,SND_CERP00_VOATTACK_A,SND_CERP00_VOGETHIT,SND_CERP00_VOGETHIT_A,SND_CERP00_VODIE,SND_CERP00_VO_CATTACK,SND_CERP00_VO_CATTACK_A,SND_CERP00_VO_LATTACK,SND_CERP00_VO_LATTACK_A,SND_CERP00_BARK
2|R_COLSUS00.WAD|SBP_COLOS00|blk|18|377200|SND_COL_VO1STSCREAM,SND_COL_VOPUNCHBALCONY,SND_COL_VOPUNCH,SND_COL_VOTAUNT,SND_COL_VOTAUNT2,SND_COL_VOCLAW,SND_COL_CLAWMVMNT,SND_COL_CLAWMVMNT2,SND_COL_CLAWSCRAPE,SND_COL_VOCANNON,SND_COL_VOGETHIT,SND_COL_MVMNT_SLOW,SND_COL_FISTIMPACT,SND_COL_FACESCRAPE,SND_COL_CSEYEOPEN,SND_COL_EYESTAB,SND_COL_VOEYESTAB,SND_SOLDIERDIE
2|R_COLSUS01.WAD|SBP_COLOS10|blk|20|427856|SND_COL_VOSTEP,SND_COL_VOFOOTWIN,SND_COL_VOTAUNT,SND_COL_VOATTK,SND_COL_VOGETHIT,SND_COL_VOTANTRUM,SND_COL_VOTRANSATTK,SND_COL_VOWALLPUNCH,SND_COL_WHEELENT,SND_COL_WHEELESCAPE,SND_COL_MVMNT_TOSS,SND_COL_MVMNT_SLOW,SND_COL_CLAWMVMNT,SND_COL_STRUGMVMNT,SND_COL_MVMNT_LP,SND_COL_FACESCRAPE,SND_COL_HANDSTAB,SND_COL_FACESTAB
2|R_COLSUS02.WAD|SBP_COLOS20|blk|4|90608|SND_COL_VOGETHIT,SND_COL_CLAWMVMNT,SND_COL_VOSLAM,SND_COL_VOENTER
2|R_COLSUS03.WAD|SBP_COLOS30|blk|15|292432|SND_COL_VOGETHIT,SND_COL_VOGETHITBIG,SND_COL_VOATTK,SND_COL_VOFIREATTK,SND_COL_VOTAUNT,SND_COL_MVMNT_SLOW,SND_COL_CLAWMVMNT,SND_FIST_SCRAPETHROW,SND_FIST_HITCOLOSUS
2|R_CYCLOP00.WAD|SBP_CYCLOP00|blk|19|153536|SND_CYCLOP00_STEPWALK,SND_CYCLOP00_STEPRUN,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CYCLOP00_CLUBIMPACT,SND_CYCLOP00_FOOTSTOMP,SND_CYCLOP00_BODYFALL,SND_CYCLOP00_WHOOSH_F,SND_CYCLOP00_WHOOSH_S,SND_CYCLOP00_VO_WU_A,SND_CYCLOP00_VO_WU_B,SND_CYCLOP00_VO_WU_C,SND_CYCLOP00_VO_WU_D,SND_CYCLOP00_VO_TAUNT1,SND_CYCLOP00_VO_GETHIT,SND_CYCLOP00_VO_ATTK_A,SND_CYCLOP00_VO_ATTK_B,SND_CYCLOP00_VO_SPIN,SND_CYCLOP00_VO_DIE,SND_CYCLOP00_VO_EYE,SND_CYCLOP00_VO_GROWL,SND_CYCLOP00_VO_GROWL2,SND_CYCLOP00_VO_STRG_LP,SND_CYCLOP00_VO_SPAWN,SND_CYCLOP00_VO_INTHIT,SND_CYCLOP00_VO_INTRO1,SND_CYCLOP00_VO_INTRO2,SND_CYCLOP00_VO_INTRO3,SND_CYCLOP00_VO_YELL,SND_CYCLOP00_VOMOUNT
2|R_CYCLOP01.WAD|SBP_CYCLOP01|blk|19|153536|SND_CYCLOP01_STEPWALK,SND_CYCLOP01_STEPRUN,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CYCLOP01_CLUBIMPACT,SND_CYCLOP01_FOOTSTOMP,SND_CYCLOP01_BODYFALL,SND_CYCLOP01_WHOOSH_F,SND_CYCLOP01_WHOOSH_S,SND_CYCLOP01_VO_WU_A,SND_CYCLOP01_VO_WU_B,SND_CYCLOP01_VO_WU_C,SND_CYCLOP01_VO_WU_D,SND_CYCLOP01_VO_TAUNT1,SND_CYCLOP01_VO_GETHIT,SND_CYCLOP01_VO_ATTK_A,SND_CYCLOP01_VO_ATTK_B,SND_CYCLOP01_VO_SPIN,SND_CYCLOP01_VO_DIE,SND_CYCLOP01_VO_EYE,SND_CYCLOP01_VO_GROWL,SND_CYCLOP01_VO_GROWL2,SND_CYCLOP01_VO_STRG_LP,SND_CYCLOP01_VO_INTHIT,SND_CYCLOP01_VO_INTRO1,SND_CYCLOP01_VO_INTRO2,SND_CYCLOP01_VO_INTRO3,SND_CYCLOP01_VO_YELL,SND_CYCLOP01_VOMOUNT,SND_CYCLOP01_VO_SPAWN
2|R_CYCLOP30.WAD|SBP_CYCLOP30|blk|19|153536|SND_CYCLOP30_STEPWALK,SND_CYCLOP30_STEPRUN,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_CYCLOP30_CLUBIMPACT,SND_CYCLOP30_FOOTSTOMP,SND_CYCLOP30_BODYFALL,SND_CYCLOP30_WHOOSH_F,SND_CYCLOP30_WHOOSH_S,SND_CYCLOP30_VO_WU_A,SND_CYCLOP30_VO_WU_B,SND_CYCLOP30_VO_WU_C,SND_CYCLOP30_VO_WU_D,SND_CYCLOP30_VOMOUNT,SND_CYCLOP30_VO_TAUNT1,SND_CYCLOP30_VO_GETHIT,SND_CYCLOP30_VO_ATTK_A,SND_CYCLOP30_VO_ATTK_B,SND_CYCLOP30_VO_SPIN,SND_CYCLOP30_VO_DIE,SND_CYCLOP30_VO_EYE,SND_CYCLOP30_VO_GROWL,SND_CYCLOP30_VO_GROWL2,SND_CYCLOP30_VO_STRG_LP,SND_CYCLOP30_VO_SPAWN,SND_CYCLOP30_VO_INTHIT,SND_CYCLOP30_VO_INTRO1,SND_CYCLOP30_VO_INTRO2,SND_CYCLOP30_VO_INTRO3,SND_CYCLOP30_VO_YELL
2|R_FATMED.WAD|SBP_FATMED|blk|19|298832|SND_FATMED_INTROSTART,SND_FATMED_VOENTER,SND_FATMED_VOTHROW,SND_FATMED_VOROAR,SND_FATMED_VOSTRIKE,SND_FATMED_VOSLAM,SND_FATMED_VOTAIL,SND_FATMED_VOBEAMSHOT,SND_FATMED_VOHEADRIP,SND_FATMED_VOEVADE,SND_FATMED_VOGETHIT,SND_FATMED_VOWINDUP_A,SND_FATMED_VOWINDUP_B,SND_FATMED_VOWINDUP_C,SND_FATMED_VOWINDUP_D,SND_FATMED_VOMOVE,SND_FATMED_VOSTRUG,SND_FATMED_VOSTRUG_LP,SND_FATMED_TAILWHSH,SND_FATMED_TAILSLAM,SND_FATMED_FISTSLAM,SND_FATMED_BODYFALL
2|R_GREEKF00.WAD|SBP_GREEKFEM|blk|8|100816|SND_GREEKFEM_VOCRY,SND_GREEKFEM_VODIE
2|R_GREEKM00.WAD|SBP_GREEKMAN|blk|11|95296|SND_GREEKMAN_VOCRY,SND_GREEKFEM_VODIE
2|R_GRIFIN10.WAD|SBP_GRIFIN02|blk|12|154336|SND_GRIFIN_VOATTACK,SND_GRIFIN_VOATTACK_A,SND_GRIFIN_VOGETHIT,SND_GRIFIN_VOGETHIT_A,SND_GRIFIN_VODEATH,SND_GRIFIN_VOWINGSCREAM,SND_GRIFIN_TAILSWIPE,SND_GRIFIN_FLAP_UP,SND_GRIFIN_FLAP_DWN,SND_GRIFIN_FLAP_UP_FAST,SND_GRIFIN_FLAP_DWN_FAS,SND_GRIFIN_BOOST
2|R_HARPY00.WAD|SBP_HARPY00|blk|9|47440|SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_HARP_GRABHERO,SND_HARP_VOATTACK,SND_HARP_VOGETHIT,SND_HARP_VODIE,SND_HARP_VOTAUNT
2|R_HARPY10.WAD|SBP_HARPY10|blk|12|60096|SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_HARP_GRABHERO,SND_HARP_VOATTACK,SND_HARP_VOGETHIT,SND_HARP_VODIE,SND_HARP_VOTAUNT
2|R_HARPY20.WAD|SBP_HARPY20|blk|12|75616|SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_HARP_GRABHERO,SND_HARP_VOATTACK,SND_HARP_VOGETHIT,SND_HARP_VODIE,SND_HARP_VOTAUNT,SND_HARP_FIRESLAM,SND_HAF_FIRE_LP,SND_HARP_FIREATK_LP
2|R_HARPY30.WAD|SBP_HARPY30|blk|12|63376|SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_HARP_GRABHERO,SND_HARP_VOATTACK,SND_HARP_VOGETHIT,SND_HARP_VODIE,SND_HARP_VOTAUNT
2|R_HARPY40.WAD|SBP_HARPY00|blk|9|47440|SND_HARP_WINGFLAP_SLOW,SND_HARP_WINGFLAP_FAST,SND_HARP_GRABHERO,SND_HARP_VOATTACK,SND_HARP_VOGETHIT,SND_HARP_VODIE,SND_HARP_VOTAUNT
2|R_ICARUS.WAD|SBP_ICARUS|blk|17|176144|SND_ICARUS_VOGETHIT,SND_ICARUS_VOGETHITA,SND_ICARUS_VOATTK,SND_ICARUS_VOSTRUG,SND_ICARUS_VOGRIND,SND_ICARUS_VOSCREAM,SND_ICARUS_VODIE,SND_KRATOS_ICARUS_FLIP,SND_KRATOSFALLSCREAM,SND_ICARUS_VOSCREAM2
2|R_KRAKEN.WAD|SBP_KRAKEN|blk|26|425136|SND_KRAK_VOBITE,SND_KRAK_VOVOMIT,SND_KRAK_VOATTK,SND_KRAK_VOATTK_A,SND_KRAK_VOSTUN,SND_KRAK_VOGETHITBIG,SND_KRAK_VOGETHIT_A,SND_KRAK_VOGETHIT,SND_KRAK_VOGROWL,SND_KRAK_VOTENTRIPL,SND_KRAK_VOTENTRIPR,SND_KRAK_VOROAR,SND_KRAK_VOBREATH,SND_KRAK_TENTWHSH,SND_KRAK_TENTWHSH_SLAM,SND_KRAK_SWIPESTART,SND_KRAK_SLAM,SND_KRAK_STAB,SND_KRAK_BITE
2|R_MEDUSA00.WAD|SBP_MEDUSA00|blk|12|101008|SND_MEDUSA_VOGETHIT,SND_MEDUSA_VODIE,SND_MEDUSA_VOHEADRIP,SND_MEDUSA_VOEVADE,SND_MEDUSA_VOTAUNT,SND_MEDUSA_VOTAILSWEEP,SND_MEDUSA_VOLUNGE,SND_MEDUSA_VODBLCLAW,SND_MEDUSA_VOMOVE,SND_MEDUSA_WHOOSH,SND_MEDUSA_HEADRIP,SND_MEDUSA_MOVE
2|R_MEDUSA10.WAD|SBP_MEDUSA00|blk|12|101008|SND_MEDUSA_VOGETHIT,SND_MEDUSA_VODIE,SND_MEDUSA_VOHEADRIP,SND_MEDUSA_VOEVADE,SND_MEDUSA_VOTAUNT,SND_MEDUSA_VOTAILSWEEP,SND_MEDUSA_VOLUNGE,SND_MEDUSA_VODBLCLAW,SND_MEDUSA_VOMOVE,SND_MEDUSA_WHOOSH,SND_MEDUSA_HEADRIP,SND_MEDUSA_MOVE
2|R_MEDUSA20.WAD|SBP_MEDUSA00|blk|12|101008|SND_MEDUSA_VOGETHIT,SND_MEDUSA_VODIE,SND_MEDUSA_VOHEADRIP,SND_MEDUSA_VOEVADE,SND_MEDUSA_VOTAUNT,SND_MEDUSA_VOTAILSWEEP,SND_MEDUSA_VOLUNGE,SND_MEDUSA_VODBLCLAW,SND_MEDUSA_VOMOVE,SND_MEDUSA_WHOOSH,SND_MEDUSA_HEADRIP,SND_MEDUSA_MOVE
2|R_MINTAR00.WAD|SBP_MINOTAUR00|blk|14|98224|SND_MIN00_VOATTK,SND_MIN00_VOATTKA,SND_MIN00_VOGETHIT,SND_MIN00_VOGETHITA,SND_MIN00_VOTAUNT,SND_MIN00_VODIE,SND_MIN00_VOCSDIE,SND_MIN00_VOGROWL,SND_MIN00_VOSTRG_LP,SND_MIN00_VOGRWL_LP,SND_MIN00_VOSPAWN,SND_MIN00_AXESWING,SND_MIN00_AXEHIT,SND_MIN00_AXEPULL,SND_MIN00_STEPWALK,SND_MIN00_STEPLAND
2|R_MINTAR30.WAD|SBP_MINOTAUR30|blk|13|115088|SND_MIN30_VOWINDUPA,SND_MIN30_VOWINDUPB,SND_MIN30_VOWINDUPC,SND_MIN30_VOSTRG_LP,SND_MIN30_VOSPAWN,SND_MIN30_VOTAUNT,SND_MIN30_VOIGNITE,SND_MIN30_VOATTK,SND_MIN30_VOATTK_A,SND_MIN30_VOGETHIT,SND_MIN30_VOGETHI_A,SND_MIN30_VOSNORT,SND_MIN30_VOGROWL,SND_MIN30_VODIE,SND_MIN30_VOCSDIE,SND_MIN30_IGNITE,SND_MIN30_WHOOSH,SND_MIN30_STEPWALK,SND_MIN30_STEPLAND,SND_MIN30_CLUBHIT
2|R_MINTAR40.WAD|SBP_MINOTAUR40|blk|14|98144|SND_MIN40_VOATTK,SND_MIN40_VOATTKA,SND_MIN40_VOGETHIT,SND_MIN40_VOGETHITA,SND_MIN40_VOTAUNT,SND_MIN40_VODIE,SND_MIN40_VOCSDIE,SND_MIN40_VOGROWL,SND_MIN40_VOSTRG_LP,SND_MIN40_VOGRWL_LP,SND_MIN40_VOSPAWN,SND_MIN40_AXESWING,SND_MIN40_AXEHIT,SND_MIN40_AXEPULL,SND_MIN40_STEPWALK,SND_MIN40_STEPLAND
2|R_MINTAR41.WAD|SBP_MINOTAUR41|blk|14|98144|SND_MIN41_VOATTK,SND_MIN41_VOATTKA,SND_MIN41_VOGETHIT,SND_MIN41_VOGETHITA,SND_MIN41_VOTAUNT,SND_MIN41_VODIE,SND_MIN41_VOCSDIE,SND_MIN41_VOGROWL,SND_MIN41_VOSTRG_LP,SND_MIN41_VOGRWL_LP,SND_MIN41_VOSPAWN,SND_MIN41_AXESWING,SND_MIN41_AXEHIT,SND_MIN41_AXEPULL,SND_MIN41_STEPWALK,SND_MIN41_STEPLAND
2|R_ORDERL00.WAD|SBP_ORDERL00|blk|15|84864|SND_ORDERL_VOATTK,SND_ORDERL_VOATTKA,SND_ORDERL_VOGETHT,SND_ORDERL_VOGETHTA,SND_ORDERL_VODIE,SND_ORDERL_VOTAUNT1,SND_ORDERL_VOTAUNT2,SND_ORDERL_VOWUP_A,SND_ORDERL_VOWUP_B,SND_ORDERL_STEPWALK,SND_ORDERL_STEPLAND,SND_ORDERL_MACEWHSH,SND_ORDERL_ARMORBRK,SND_ORDERL_ARMORHIT,SND_ORDERL_BODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S
2|R_ORDERL10.WAD|SBP_ORDERL10|blk|15|84656|SND_ORDERL_VOATTKA,SND_ORDERL_VOATTK,SND_ORDERL_VOGETHT,SND_ORDERL_VOGETHTA,SND_ORDERL_VODIE,SND_ORDERL_VOTAUNT1,SND_ORDERL_VOTAUNT2,SND_ORDERL_VOWUP_A,SND_ORDERL_VOWUP_B,SND_ORDERL_STEPWALK,SND_ORDERL_STEPLAND,SND_ORDERL_MACEWHSH,SND_ORDERL_ARMORBRK,SND_ORDERL_BODYFALL,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S
2|R_ORDERP00.WAD|SBP_ORDERP|blk|8|101584|SND_ORDERP_VOWINDUP_A,SND_ORDERP_VOWINDUP_B,SND_ORDERP_VOWINDUP_C,SND_ORDERP_VOATTACK,SND_ORDERP_VOGETHIT,SND_ORDERP_VODEATH,SND_ORDERP_VOFIREDIE,SND_ORDERP_VOCSDEATH,SND_ORDERP_SLASHFIRE,SND_ORDERP_FIRESTART,SND_ORDERP_FIRELOB,SND_ORDERP_FIRELOB_IMP,SND_ORDERP_FIREBLOCK,SND_ORDERP_DEATHEXPLO,SND_ORDERP_FIRECHRG_LP,SND_ORDERP_FIREDIE_LP
2|R_ORDERS00.WAD|SBP_ORDERS00|blk|12|97072|SND_ORDERS00_STEPWALK,SND_ORDERS00_STEPRUN,SND_ORDERS00_VO_WINDUPA,SND_ORDERS00_VO_WINDUPB,SND_ORDERS00_VO_SPAWN,SND_ORDERS00_VO_TAUNT,SND_ORDERS00_VO_ATTK,SND_ORDERS00_VO_GETHIT,SND_ORDERS00_VO_LAUNCH,SND_ORDERS00_VO_DIE,SND_ORDERS00_VO_CSRIP,SND_ORDERS00_VO_CSSTAB,SND_ORDERS00_TOSSYELL,SND_ORDERS00_CHOKE,SND_ORDERS_WHOOSH_F,SND_ORDERS_WHOOSH_S
2|R_ORDERS01.WAD|SBP_ORDERS00|blk|12|97072|SND_ORDERS00_STEPWALK,SND_ORDERS00_STEPRUN,SND_ORDERS00_VO_WINDUPA,SND_ORDERS00_VO_WINDUPB,SND_ORDERS00_VO_SPAWN,SND_ORDERS00_VO_TAUNT,SND_ORDERS00_VO_ATTK,SND_ORDERS00_VO_GETHIT,SND_ORDERS00_VO_LAUNCH,SND_ORDERS00_VO_DIE,SND_ORDERS00_VO_CSRIP,SND_ORDERS00_VO_CSSTAB,SND_ORDERS00_TOSSYELL,SND_ORDERS00_CHOKE,SND_ORDERS_WHOOSH_F,SND_ORDERS_WHOOSH_S
2|R_ORDERS02.WAD|SBP_ORDERS00|blk|12|97072|SND_ORDERS00_STEPWALK,SND_ORDERS00_STEPRUN,SND_ORDERS00_VO_WINDUPA,SND_ORDERS00_VO_WINDUPB,SND_ORDERS00_VO_SPAWN,SND_ORDERS00_VO_TAUNT,SND_ORDERS00_VO_ATTK,SND_ORDERS00_VO_GETHIT,SND_ORDERS00_VO_LAUNCH,SND_ORDERS00_VO_DIE,SND_ORDERS00_VO_CSRIP,SND_ORDERS00_VO_CSSTAB,SND_ORDERS00_TOSSYELL,SND_ORDERS00_CHOKE,SND_ORDERS_WHOOSH_F,SND_ORDERS_WHOOSH_S
2|R_ORDERS03.WAD|SBP_ORDERS00|blk|12|97072|SND_ORDERS00_STEPWALK,SND_ORDERS00_STEPRUN,SND_ORDERS00_VO_WINDUPA,SND_ORDERS00_VO_WINDUPB,SND_ORDERS00_VO_SPAWN,SND_ORDERS00_VO_TAUNT,SND_ORDERS00_VO_ATTK,SND_ORDERS00_VO_GETHIT,SND_ORDERS00_VO_LAUNCH,SND_ORDERS00_VO_DIE,SND_ORDERS00_VO_CSRIP,SND_ORDERS00_VO_CSSTAB,SND_ORDERS00_TOSSYELL,SND_ORDERS00_CHOKE,SND_ORDERS_WHOOSH_F,SND_ORDERS_WHOOSH_S
2|R_ORDERS05.WAD|SBP_ORDERS00|blk|12|97072|SND_ORDERS00_STEPWALK,SND_ORDERS00_STEPRUN,SND_ORDERS00_VO_WINDUPA,SND_ORDERS00_VO_WINDUPB,SND_ORDERS00_VO_SPAWN,SND_ORDERS00_VO_TAUNT,SND_ORDERS00_VO_ATTK,SND_ORDERS00_VO_GETHIT,SND_ORDERS00_VO_LAUNCH,SND_ORDERS00_VO_DIE,SND_ORDERS00_VO_CSRIP,SND_ORDERS00_VO_CSSTAB,SND_ORDERS00_TOSSYELL,SND_ORDERS00_CHOKE,SND_ORDERS_WHOOSH_F,SND_ORDERS_WHOOSH_S
2|R_ORDERS10.WAD|SBP_ORDERS00|blk|12|97072|SND_ORDERS00_STEPWALK,SND_ORDERS00_STEPRUN,SND_ORDERS00_VO_WINDUPA,SND_ORDERS00_VO_WINDUPB,SND_ORDERS00_VO_SPAWN,SND_ORDERS00_VO_TAUNT,SND_ORDERS00_VO_ATTK,SND_ORDERS00_VO_GETHIT,SND_ORDERS00_VO_LAUNCH,SND_ORDERS00_VO_DIE,SND_ORDERS00_VO_CSRIP,SND_ORDERS00_VO_CSSTAB,SND_ORDERS00_TOSSYELL,SND_ORDERS00_CHOKE,SND_ORDERS_WHOOSH_F,SND_ORDERS_WHOOSH_S
2|R_PEGASUS.WAD|SBP_PEGASUS|blk|16|165120|SND_PEGA_FLAPUP,SND_PEGA_FLAPDN,SND_PEGASUS_BOO,SND_PEGASUS_EVA,SND_PEGASUS_WHINNY,SND_PEGASUS_SNORT,SND_PEGASUS_STRUGGLE,SND_PEGASUS_HURT,SND_PEGASUS_HURT_A,SND_PEGASUS_DEATH,SND_PEGASUS_ATTK,SND_GRIFIN10_FBALLSHOT,SND_GRIFIN10_FBALLHIT,SND_PEGA_STRUG_CAM,SND_PEGA_HURT_CAM,SND_PEGA_DEATH_CAM
2|R_PERMA.WAD|SBP_general|blk|128|1162384|SND_FOOTSTEP_DIRT,SND_FOOTSTEP_DIRTSTEP,SND_FOOTSTEP_DIRTWALK,SND_FOOTSTEP_DIRTRUN,SND_FOOTSTEP_DIRTLAND,SND_FOOTSTEP_PLANK,SND_FOOTSTEP_PLANKSTEP,SND_FOOTSTEP_PLANKWALK,SND_FOOTSTEP_PLANKRUN,SND_FOOTSTEP_PLANKLAND,SND_FOOTSTEP_STONE,SND_FOOTSTEP_STONESTEP,SND_FOOTSTEP_STONEWALK,SND_FOOTSTEP_STONERUN,SND_FOOTSTEP_STONELAND,SND_FOOTSTEP_BEAM,SND_FOOTSTEP_BEAMSTEP,SND_FOOTSTEP_BEAMWALK,SND_FOOTSTEP_BEAMRUN,SND_FOOTSTEP_BEAMLAND,SND_FOOTSTEP_METAL,SND_FOOTSTEP_METALSTEP,SND_FOOTSTEP_METALWALK,SND_FOOTSTEP_METALRUN,SND_FOOTSTEP_METALLAND,SND_FOOTSTEP_WATER,SND_FOOTSTEP_WATERSTEP,SND_FOOTSTEP_WATERWALK,SND_FOOTSTEP_WATERRUN,SND_FOOTSTEP_WATERLAND,SND_FOOTSTEP_PUDDLE,SND_FOOTSTEP_PUDDLESTEP,SND_FOOTSTEP_PUDDLEWALK,SND_FOOTSTEP_PUDDLERUN,SND_FOOTSTEP_PUDDLELAND,SND_FOOTSTEP_VINEWALL,SND_VINEWALL_CATCH,SND_VINEWALL_GRAB,SND_VINEWALL_STEP,SND_VINEWALL_LAND,SND_FOOTSTEP_ROPEWALL,SND_ROPEWALL_CATCH,SND_ROPEWALL_GRAB,SND_ROPEWALL_STEP,SND_ROPEWALL_LAND,SND_FOOTSTEP_LADDER,SND_HANDGRAB_LADDER,SND_LADDERSLIDE_LP,SND_CLIFFCLIMB_GRAB,SND_CLIFFCLIMB_STEP,SND_CLIFFJUMP_LAND,SND_VINEWALLCLIMB_STEP,SND_VINEWALLCLIMB_LAND,SND_VINEWALLCLIMB_SL_LP,SND_ROCKWALLCLIMB_STEP,SND_ROPE_SWINGSHOT,SND_ROCKWALLCLIMB_LAND,SND_ROCKWALLCLIMB_SL_LP,SND_HANDGRAB_ROPE,SND_SLIDEROPE_LP,SND_KNEEDEEPWATER,SND_INTOWATER_SPLASH,SND_JUMPOUTWATER,SND_SWIMSPLASH,SND_HUGESPLASH,SND_SWIM_STROKE,SND_SWIMDASH,SND_SWIM_UW_STROKE,SND_SWIM_UW_LOOP,SND_GRAPPLE_SHOOT,SND_GRAPPLE_ATTACH,SND_GRAPPLE_RELEASE,SND_GRAPPLE_JUMP,SND_GRAPPLE_SWING,SND_GRAPPLE_360,SND_WHOOSHMID_SLOW,SND_WHOOSHMID_MEDIUM,SND_WHOOSHMID_FAST,SND_WHOOSHLOW_SLOW,SND_WHOOSHLOW_MEDIUM,SND_WHOOSHLOW_FAST,SND_WHOOSHMID_S_A,SND_WHOOSHMID_M_A,SND_WHOOSHMID_F_A,SND_WHOOSHLOW_S_A,SND_WHOOSHLOW_M_A,SND_WHOOSHLOW_F_A,SND_WHOOSHHIGH_WHIP,SND_UPGRADEWHOOSH,SND_SKELLY10_WHSH,SND_CHAINSNAP_A,SND_CHAINSNAP_WCLANK_A,SND_CHAINRETURN,SND_BLADEBLOCK,SND_SWORDHIT_SWORDHEV,SND_SWORDHIT_SHIELD,SND_SWORDHIT_STONEBRK,SND_SWORDHIT_STONE,SND_SWORDHIT_WOOD,SND_SWORD_HITMETAL,SND_SWORDHIT_CHEST,SND_SWORD_IMPALE,SND_SWORD_CUTTHEAD,SND_SWDSPECIALATK1,SND_ENEMY_GETHIT_L,SND_ENEMY_GETHIT_S,SND_HERO_JUMPVOC,SND_HERO_JUMPVOC_A,SND_HERO_JUMPVOCAL,SND_HERO_JUMPVOCAL_A,SND_BODYFALL_ROLL,SND_BODYFALL_ROLLAI,SND_BODYFALL_SLAM,SND_BODYFALL_HEAVY,SND_BODYFALL_LIGHT,SND_BODYFALL_LIMB,SND_PUNCH,SND_PICKUPS_ORBS_H,SND_PICKUPS_ORBS_M,SND_PICKUPS_ORBS_E,SND_PICKUPS_ORBS_A,SND_CRANKFORWARD,SND_CRANKBACKWARD,SND_CRANK_STOP,SND_LGCLUNK_UP,SND_LGCLUNK_DN,SND_TORCH_LOOP,SND_DMCDOOR_START,SND_DMCDOOR_STOP,SND_SPAWN_LP,SND_DIEPOOF,SND_CHESTGRAB,SND_CHESTOPEN,SND_LEVER,SND_LEVER_RELEASE,SND_GODMODESHOT,SND_TITANVORTEX,SND_TRANSFORM_LP,SND_TRANSFORM_END,SND_IG_NAV_L,SND_IG_NAV_R,SND_IG_POPUP,SND_IG_POPUP_NO,SND_IG_BARGROW_LP,SND_IG_MAGICOUT,SND_IG_YOUAREDEAD,SND_MM_POPUP,SND_MM_CONTINUE,SND_MM_NAV_UPDN,SND_MM_NAV_LR,SND_MM_SELECT,SND_MM_BACK,SND_MM_RESTART_YES,SND_MM_QUIT_YES,SND_MM_SFX_SLIDER,SND_MM_NEGATIVE,SND_MM_NAV_UPDN_LP,SND_PU_R1,SND_PU_L1,SND_PU_SUBWPN_UPDN,SND_PU_NAV_UPDN,SND_PU_EMPTY,SND_PU_TRANSFER_LP,SND_PU_POWERUP,SND_IG_COOL100,SND_IG_COOLPROG,SND_IG_LOSECOOL,SND_MINIGAME_BUTTON,SND_MINIGAME_AVAILABLE,SND_MINIGAME_FAIL,SND_MINIGAME_HIT,SND_LOWHEALTH,SND_SHARDCOLLECT,SND_SHARDCOMPLETE,SND_SWDSPECIALATK1_PRE,SND_BONECRUNCH_BIG,SND_BLOODGEYSER,SND_BLOODGUSH,SND_BLOODSPURT,SND_BLOODYIMPACT,SND_SELECT_WIND,SND_SELECT_LIGHTNING,SND_SELECT_EARTH,SND_SELECT_MEDUSA,SND_SELECT_NULL,SND_BEAT1,SND_BEAT2,SND_HB_POSTMOVIE,SND_SAVEPOINT_LP,SND_MAI_STRUGGLEVO_LP,SND_KICKCHARGEVO_LP,SND_ROCKHIT,SND_HERMES_START,SND_HERMES_LP,SND_HERMES_END,SND_BKHAMSWNG,SND_BKHAM360,SND_BKHAMIMPACT,SND_BKHAMMERSHOT,SND_BK_HMRWAVE,SND_BK_CLDUP,SND_BK_CLDDN,SND_RAISEDEAD_LP,SND_RAISEDEADHEAD1_LP,SND_RAISEDEADHEAD2_LP,SND_RAISEDEAD_SHOT,SND_BK_SOULBOMB,SND_BK_SOUL_RELEASE,SND_BK_SOUL_ABSORB,SND_BKARMY_SOUL,SND_STAFFWHSH,SND_STAFFWHSH_FAST,SND_STAFF_SHOTGUN,SND_STAFF_MINE_LP,SND_STAFF_POISONINJECT,SND_STAFF_POINSONEXP,SND_SWD_OLYMP_EXPLO,SND_SWD_OLYMP_BLAST,SND_SWD_OLYMP_WHSH,SND_SWD_OLYMP_SPHERE_LP,SND_WIND_BOW_ENTER,SND_WIND_CHRG_PULL,SND_WIND_CHRG_ENTER,SND_WIND_CHRG_LP,SND_WIND_BOW_SHOOT,SND_WIND_BOW_HIT,SND_WIND_TORNADO_SHOOT,SND_WIND_TEMPEST_SHOOT,SND_WIND_TEMPEST,SND_EARTH_STOMP,SND_EARTH_PUNCH,SND_EARTH_RAINHIT,SND_ELECTRIC_CORE_LP,SND_ELECTRIC_PULSE_LP,SND_ELECTRIC_EXPLO,SND_LIGHTNING360_LP,SND_LIGHTNING360_BOLT,SND_MEDUSA_RAY_SHOT,SND_MEDUSA_RAY_LOOP,SND_MEDUSA_BOMB,SND_MEDUSA_BOMBHIT,SND_MEDUSA_NUKE,SND_MEDUSA_NUKECHRG_LP,SND_MEDUSA_TURNTOSTONE,SND_MEDUSA_TURNTOFLESH,SND_FMED_PILRAYSTART,SND_FMED_PILRAY,SND_BREAKABLE_STONE_L,SND_BREAKABLE_STONE_M,SND_BREAKABLE_STONE_S,SND_BREAKABLE_POT_L,SND_BREAKABLE_POT_M,SND_BREAKABLE_POT_S,SND_DEBRIS_STONE_L,SND_DEBRIS_STONE_M,SND_DEBRIS_STONE_S,SND_TREE_CRACK,SND_WHOOSHCHOKE,SND_BREAK_TRUSS,SND_BREAK_WOODDOOR,SND_BREAK_STONEDOOR,SND_MAGICAQUIRE_LP,SND_GENERIC_PICKUP,SND_FLAMEPOOF,SND_FLEECE_ACTIVATE,SND_FLEECE_LP,SND_FLEECE_REFLECT,SND_FLEECE_REF_DOOR,SND_ICARUS_OUT,SND_ICARUS_IN,SND_ICARUSGRIND_LP,SND_ICARUSGRINDSHOTS,SND_ICARUSGRINDSHOTS2,SND_ICGRIND_NOISE_LP,SND_WOODBREAK,SND_COL_WHOOSH,SND_BREAK_BODY,SND_MINOFIRE_LP,SND_COL_EYESPARK_LP,SND_VOHEROCOLSTRUG_LP,SND_SWORDDRAIN_LP,SND_SWORDDRAIN_CHRG,SND_SIREN00_ELEC1_LP,SND_SIREN00_ELEC2_LP,SND_SIREN10_SCREAM_LP,SND_SIREN_WAVE,SND_KEY_PULL,SND_KEY_INSERT,SND_FISTSWING,SND_COLSUCK_LP,SND_PEGA_LAND,SND_BUGFIRE_LP,SND_BIGMTLCLANG,SND_THES_ICEGROUND,SND_PEGA_FS
2|R_PERSEUS.WAD|SBP_PERSEUS|blk|16|145072|SND_PERSEUS_VOATTK,SND_PERSEUS_VOGETHIT,SND_PERSEUS_VOGETHITA,SND_PERSEUS_VODROWN,SND_PERSEUS_VOYELL,SND_PERSEUS_VOGRAB,SND_PERSEUS_WHOOSH_S,SND_PERSEUS_WHOOSH_F,SND_PERSEUS_SLNGWSH,SND_PERSEUS_SLNGWSH_LP,SND_PERSEUS_BLINDSTART,SND_PERSEUS_BLIND_LP,SND_PERSEUS_SLNGTH,SND_PERSEUS_SLINGHIT,SND_PERSEUS_SHIELD,SND_PERSEUS_DISAPPEAR,SND_PERSEUS_MTLBREAK,SND_PERSEUS_MTLBREAK2,SND_PERSEUS_HELMETFALL
2|R_PHOENIX.WAD|SBP_PHOENIX|blk|13|150512|SND_PHOENIX_VOCALL,SND_PHOENIX_VOGETHIT,SND_PHOENIX_VOYELL,SND_PHOENIX_BY,SND_PHOENIX_FLAP_UP,SND_PHOENIX_FLAP_DN,SND_PHOENIX_BLOW,SND_PHOENIX_YELP
2|R_PRIEST10.WAD|SBP_PRIEST10|blk|12|184752|SND_PR10_SCROLLATTK,SND_PR10_SPELLCAST,SND_PR10_SPAWNATTK,SND_PR10_TELEAWAY,SND_PR10_TELEBACK,SND_PR10_GRAB,SND_PR10_GROUND_LP,SND_PR10_HAZARD_LP,SND_PR10_STRUG1_LP,SND_PR10_STRUG2_LP,SND_PR10_VODIE,SND_PR10_VOCSDI,SND_PR10_VOGE_2,SND_PR10_VOGETH,SND_PR10_VOCAST
2|R_RABDOG00.WAD|SBP_RABDOG|blk|11|61040|SND_RABDOG_VO_BARK,SND_RABDOG_VO_BITE,SND_RABDOG_VO_SNARL,SND_RABDOG_VO_GROWL,SND_RABDOG_VO_YELP,SND_RABDOG_VO_GETHIT,SND_RABDOG_VO_DIE,SND_RABDOG_VO_CSDIE
2|R_RHARCH00.WAD|SBP_RHARCH00|blk|6|36032|SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_RHARCH00_VOATTK,SND_RHARCH00_VODIE,SND_RHARCH00_VOGETHIT,SND_RHARCH00_BOWPULL,SND_RHARCH00_BOWFIRE
2|R_RHSOLD00.WAD|SBP_RHSOLD00|blk|7|41664|SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_RHSOLD00_WHSH_S,SND_RHSOLD00_WHSH_F,SND_RHSOLD00_VOATTK,SND_RHSOLD00_VODIE,SND_RHSOLD00_VOGETHIT,SND_RHSOLD00_STEPWALK,SND_RHSOLD00_STEPRUN,SND_RHSOLD00_BODYFALL,SND_RHARCH00_STEPWALK,SND_RHARCH00_STEPRUN,SND_RHARCH00_BODYFALL
2|R_RIDER00.WAD|SBP_RIDER10|blk|4|37344|SND_RIDER10_VO_ATTACK,SND_RIDER10_VO_ATTACK_A,SND_RIDER10_VO_DIE,SND_RIDER10_VO_GETHIT,SND_RIDER10_VO_GETHIT_A,SND_RIDER10_VO_TAUNT,SND_RIDER10_CHOKE
2|R_RIDER10.WAD|SBP_RIDER10|blk|4|37344|SND_RIDER10_VO_ATTACK,SND_RIDER10_VO_ATTACK_A,SND_RIDER10_VO_DIE,SND_RIDER10_VO_GETHIT,SND_RIDER10_VO_GETHIT_A,SND_RIDER10_VO_TAUNT,SND_RIDER10_CHOKE
2|R_ROCK00.WAD|SBP_ROCK00|blk|8|119888|SND_ROCK00_VODEATH,SND_ROCK00_VOGETHIT,SND_ROCK00_VOATTACK,SND_ROCK00_VOCSROAR,SND_ROCK00_VOSPAWN,SND_ROCK00_VOTAUNT,SND_ROCK00_VOCSSTAB,SND_ROCK00_VOTANTRUM,SND_ROCK00_SWINGWHOOSH,SND_ROCK00_SLAMDOUBLE,SND_ROCK00_SLAMSINGLE,SND_ROCK00_CSSTAB,SND_ROCK00_BODYFALL,SND_ROCK00_THROW,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L
2|R_ROCK01.WAD|SBP_ROCK00|blk|8|119888|SND_ROCK00_VODEATH,SND_ROCK00_VOGETHIT,SND_ROCK00_VOATTACK,SND_ROCK00_VOCSROAR,SND_ROCK00_VOSPAWN,SND_ROCK00_VOTAUNT,SND_ROCK00_VOCSSTAB,SND_ROCK00_VOTANTRUM,SND_ROCK00_SWINGWHOOSH,SND_ROCK00_SLAMDOUBLE,SND_ROCK00_SLAMSINGLE,SND_ROCK00_CSSTAB,SND_ROCK00_BODYFALL,SND_ROCK00_THROW,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L
2|R_ROCK10.WAD|SBP_ROCK00|blk|8|119888|SND_ROCK00_VODEATH,SND_ROCK00_VOGETHIT,SND_ROCK00_VOATTACK,SND_ROCK00_VOCSROAR,SND_ROCK00_VOSPAWN,SND_ROCK00_VOTAUNT,SND_ROCK00_VOCSSTAB,SND_ROCK00_VOTANTRUM,SND_ROCK00_SWINGWHOOSH,SND_ROCK00_SLAMDOUBLE,SND_ROCK00_SLAMSINGLE,SND_ROCK00_CSSTAB,SND_ROCK00_BODYFALL,SND_ROCK00_THROW,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L
2|R_SATYR00.WAD|SBP_SATYR00|blk|14|95152|SND_SAT00_VOWINDUP,SND_SAT00_VOEFFORT,SND_SAT00_VOEFFORT_LP,SND_SAT00_VOATTACK,SND_SAT00_VOATTACK_A,SND_SAT00_VOGETHIT,SND_SAT00_VOGETHIT_A,SND_SAT00_VODIE,SND_SAT00_VOCSDIE,SND_SAT00_VOSPAWNSTART,SND_SAT00_VOSPAWNEND,SND_SAT00_STEPWALK,SND_SAT00_STEPLAND,SND_SAT00_STAFFSPIN_H,SND_SAT00_STAFFSPIN_M,SND_SAT00_STAFFSPIN_L,SND_SAT00_ATTKWHSH1,SND_SAT00_ATTKWHSH2,SND_SAT00_ATTKWHSH3,SND_SAT00_ATTKWHSH4,SND_SAT00_BLDEHITGRND,SND_SAT00_BLADEDROP
2|R_SATYR10.WAD|SBP_SATYR10|blk|14|95152|SND_SAT10_VOWINDUP,SND_SAT10_VOEFFORT,SND_SAT10_VOEFFORT_LP,SND_SAT10_VOSPAWNSTART,SND_SAT10_VOSPAWNEND,SND_SAT10_VOATTACK,SND_SAT10_VOATTACK_A,SND_SAT10_VOGETHIT,SND_SAT10_VOGETHIT_A,SND_SAT10_VODIE,SND_SAT10_VOCSDIE,SND_SAT10_STEPWALK,SND_SAT10_STEPLAND,SND_SAT10_STAFFSPIN_H,SND_SAT10_STAFFSPIN_M,SND_SAT10_STAFFSPIN_L,SND_SAT10_ATTKWHSH1,SND_SAT10_ATTKWHSH2,SND_SAT10_ATTKWHSH3,SND_SAT10_ATTKWHSH4,SND_SAT10_BLDEHITGRND,SND_SAT10_BLADEDROP
2|R_SHELLA.WAD|SBP_SHELL|blk|9|99360|SND_M_HD1001Q,SND_M_HD1002Q,SND_TM_SELECT,SND_TM_BACK,SND_TM_NAV_UPDN1,SND_TM_NAV_UPDN2,SND_TM_STARTGAME,SND_H_KINTRO
2|R_SIREN00.WAD|SBP_SIREN00|blk|7|93808|SND_SIREN00_FIREBALL,SND_SIREN00_ELECSHOT,SND_SIREN00_ELECSHOTBG,SND_SIREN00_ELECBLOCK,SND_SIREN00_ELECEXPLO,SND_SIREN00_VOATTACK,SND_SIREN00_VOATTACK_A,SND_SIREN00_VOGETHIT,SND_SIREN00_VOGETHIT_A,SND_SIREN00_VODIE,SND_SIREN00_VOCSDIE,SND_SIREN00_VOGRAB,SND_SIREN00_VOWINDUP,SND_SIREN00_VOSPAWN,SND_SIREN00_TAUNT1,SND_SIREN00_TAUNT2,SND_SIREN00_TAUNT3,SND_SIREN00_VOLAUGH_S,SND_SIREN00_IDLE,SND_SIREN00_NAVSOUND
2|R_SIREN10.WAD|SBP_SIREN10|blk|5|110928|SND_SIREN10_VOATTACK,SND_SIREN10_VOATTACK_A,SND_SIREN10_VOGETHIT,SND_SIREN10_VOGETHIT_A,SND_SIREN10_VODIE,SND_SIREN10_VOCSDIE,SND_SIREN10_VOSCREAM,SND_SIREN10_VOCAST1,SND_SIREN10_VOCAST2,SND_SIREN10_VOCAST3,SND_SIREN10_VOCAST4,SND_SIREN10_VOSPAWN,SND_SIREN10_VOGRAB,SND_SIREN10_VOWINDUP
2|R_SISTER01.WAD|SBP_SISTER01|blk|19|298464|SND_SIS1_ELEC_LP,SND_SIS1_ELEC_LP_2,SND_SIS1_COLUMN_LP,SND_SIS1_COLUMN_LP2,SND_SIS1_DIVEATTK,SND_SIS1_ELECF,SND_SIS1_FIREBALLEXPLO,SND_SIS1_FIREBALLFIRE,SND_SIS1_GETUP,SND_SIS1_BOMB,SND_SIS1_CAPE,SND_SIS1_ATTKGRND,SND_SIS1_STFWSH,SND_SIS1_STFWSH_2,SND_SIS1_MOVUP,SND_SIS1_COLUMN_SHT,SND_SIS1_VOGETHIT,SND_SIS1_VOGETHIT_A,SND_SIS1_VOATTK,SND_SIS1_VOATTK_A,SND_SIS1_VODIE,SND_SIS_VO_EFFECT,SND_SIS_VO_EFFECT2
2|R_SISTER02.WAD|SBP_SISTER02|blk|11|187488|SND_SIS2_ELEC_LP,SND_SIS2_FBLEXPLO,SND_SIS2_FBALL,SND_SIS2_MOVWSH,SND_SIS2_VOGETHIT,SND_SIS2_VOGETHIT_A,SND_SIS2_VOATTK,SND_SIS2_VOATTK_A,SND_SIS2_VODIE,SND_SIS2_VOLAUGH,SND_SIS2_VOTAUNT
2|R_SISTER3A.WAD|SBP_SISTER03|blk|10|135648|SND_SIS3_GROSS_LP1,SND_SIS3_GROSS,SND_SIS3_VOGETHIT,SND_SIS3_VOGETHIT_A,SND_SIS3_VODIE,SND_SIS3_VOLAUGH,SND_SIS3_VOMOAN,SND_SIS3_VOSTABBED,SND_SIS3_VOATTK,SND_SIS3_VOATTK_A
2|R_SKELLY00.WAD|SBP_SKELLY00|blk|10|96080|SND_SKELLY00_SLASHF,SND_SKELLY00_SLASHS,SND_SKELLY00_TAUNT01,SND_SKELLY00_TAUNT02,SND_SKELLY00_VOCHOKE,SND_SKELLY00_TOSSYELL,SND_SKELLY00_VODIE,SND_SKELLY00_VORIPDIE,SND_SKELLY00_VOFLYBACK,SND_SKELLY00_VOATTK,SND_SKELLY00_VOATTK_R,SND_SKELLY00_VOGETHIT,SND_SKELLY00_VOWINDUP_A,SND_SKELLY00_VOWINDUP_B
2|R_SKELLY10.WAD|SBP_SKELLY10|blk|10|96080|SND_SKELLY10_SLASHF,SND_SKELLY10_SLASHS,SND_SKELLY10_TAUNT01,SND_SKELLY10_TAUNT02,SND_SKELLY10_VOCHOKE,SND_SKELLY10_TOSSYELL,SND_SKELLY10_VODIE,SND_SKELLY10_VORIPDIE,SND_SKELLY10_VOFLYBACK,SND_SKELLY10_VOATTK,SND_SKELLY10_VOATTK_R,SND_SKELLY10_VOGETHIT,SND_SKELLY10_VOWINDUP_A,SND_SKELLY10_VOWINDUP_B
2|R_SPARTAN.WAD|SBP_SPARTAN|blk|3|25632|SND_SPAR_SWORD,SND_SPAR_VOATTK,SND_SPAR_VOGETHIT,SND_SPAR_VODIE,SND_SPAR_VOGETHITA
2|R_THESEUS.WAD|SBP_THESEUS|blk|14|145792|SND_THES_VOATTK,SND_THES_VOATTK_A,SND_THES_VOGETHIT,SND_THES_VOGETHIT_A,SND_THES_VOSTRUG,SND_THES_VODIE,SND_THES_VOSTAB,SND_THES_VOHEADHIT,SND_THES_VOSUMMON,SND_THES_VOCHARGE,SND_THES_VOUNSTUN,SND_THES_VOLAUGH,SND_THES_STAFFWHSH,SND_ENEMY_GETHIT_S,SND_ENEMY_GETHIT_L,SND_THES_STAFFIMP,SND_THES_STAFFPWRUP,SND_THES_MAGIC_FIRE,SND_THES_ICEIMP,SND_THES_SUMMON
2|R_TRAIN00.WAD|SBP_TRAIN00|blk|9|83936|SND_TRAIN00_AXE_SWING,SND_TRAIN00_DOUBLSWIPE,SND_TRAIN00_VO_WU_A,SND_TRAIN00_VO_WU_B,SND_TRAIN00_VO_ATTACK,SND_TRAIN00_VO_FACE,SND_TRAIN00_VO_GET_HIT,SND_TRAIN00_VO_CSDIE,SND_TRAIN00_VO_DIE,SND_TRAIN00_VO_FLY,SND_TRAIN_HORN
2|R_TROLD00.WAD|SBP_TRANS2|blk|9|71328|SND_T2_VOSTRUG_LP,SND_T2_VOGETHIT,SND_T2_VOGETHITA,SND_T2_VODIE
2|R_WRAITH00.WAD|SBP_WRAITH00|blk|12|115152|SND_WRTH00_VOWUP,SND_WRTH00_VOATTK,SND_WRTH00_VOATTKA,SND_WRTH00_VOGETHT,SND_WRTH00_VOGETHTA,SND_WRTH00_VODIE,SND_WRTH00_VOCSDIE,SND_WRTH00_VODIVE,SND_WRTH00_VOEMERGE,SND_WRTH00_DIVE,SND_WRTH00_EMERGE,SND_WRTH00_SLASHFAST,SND_WRTH00_SLASHMEDIUM,SND_WRTH00_SLASHSLOW,SND_WRTH00_SLASHSLWST,SND_WRTH00_SWORDHIT,SND_WRTH00_SWRDHTGRND,SND_WRTH00_SWRDHTFNL
2|R_WRAITH10.WAD|SBP_WRAITH10|blk|12|115152|SND_WRTH10_VOWUP,SND_WRTH10_VOATTK,SND_WRTH10_VOATTKA,SND_WRTH10_VOGETHT,SND_WRTH10_VOGETHTA,SND_WRTH10_VODIE,SND_WRTH10_VOCSDIE,SND_WRTH10_VODIVE,SND_WRTH10_VOEMERGE,SND_WRTH10_DIVE,SND_WRTH10_EMERGE,SND_WRTH10_SLASHFAST,SND_WRTH10_SLASHMEDIUM,SND_WRTH10_SLASHSLOW,SND_WRTH10_SLASHSLWST,SND_WRTH10_SWORDHIT,SND_WRTH10_SWRDHTGRND,SND_WRTH10_SWRDHTFNL
2|R_ZEUS.WAD|SBP_ZEUS|blk|19|377792|SND_ZEUS_SHIELD,SND_ZEUS_WIND_CHRG_LP,SND_ZEUS_WIND_LP,SND_ZEUS_SPARKS,SND_ZEUS_SPARKS_2,SND_ZEUS_VOSTRUG_LP,SND_ZEUSB_VOSTRUG_L,SND_ZEUS_WINDWALL,SND_ZEUS_WIND_TORNADO,SND_ZEUS_FIST,SND_ZEUS_FIST_2,SND_ZEUS_ELEC_L,SND_ZEUS_ELEC_L_2,SND_ZEUS_ELEC_L_3,SND_ZEUS_THND_ATTK1,SND_ZEUS_ATTK_1_EXPLO,SND_ZEUS_THND_ATTK2,SND_ZEUS_ATTK_2_EXPLO,SND_ZEUS_BOLTHIT,SND_ZEUS_EVADE,SND_ZEUS_PUNCHWSH,SND_ZEUS_SHRINK,SND_ZEUS_GROW,SND_ZEUS_VODIE,SND_ZEUS_VOGETHIT,SND_ZEUS_VOGETHIT_A,SND_ZEUS_VOATTK,SND_ZEUS_VOATTK_A,SND_ZEUS_VOTAUNT,SND_ZEUS_VOSTRUG,SND_ZEUSB_VOGETHIT,SND_ZEUSB_VOGETHIT_A,SND_ZEUSB_VOATTK,SND_ZEUSB_VOATTK_A,SND_ZEUSB_VOTAUNT,SND_ZEUSB_VOSTRUG,SND_ZEUSB_VOGROWL
2|SPIR10.WAD|SBP_SPIR10|blk|17|265248|SND_AMB_INTERIOR_LP,SND_D_21A01GA,SND_D_21A02GA,SND_AMB_UNDERWATER_LP,SND_UNDERWATER_LEVER,SND_FACE_CRACK,SND_M_SP1001A,SND_WALL_SMASH,SND_BIGDEBRIS,SND_CRYSTAL_HIT,SND_CRYSTAL_SMASH,SND_PLATFORM_TURN,SND_PLATFORM_STOP,SND_CRANKONLY_TURN,SND_UW_PLATFORM_SHIFT,SND_UW_PLATFORM_LOCK,SND_BELLRING,SND_BELLRING2,SND_CRYSTAL_LP,SND_M_SP1002E,SND_M_SP1003A,SND_RAM_HITFACE
2|SPIR15.WAD|SBP_SPIR15|blk|5|58176|SND_AMB_INTERIOR_LP,SND_M_SP1001A,SND_M_SP1003A,SND_M_SP1002E,SND_M_SP2001C,SND_LIFTDOOR_GRAB,SND_LIFTDOOR_LIFT_LP,SND_LIFTDOOR_STOP,SND_LIFTDOORLOCK,SND_LIFTDOOR_SLAM
2|SPIR20.WAD|SBP_SPIR20|blk|6|130704|SND_AMB_INTERIOR_LP,SND_M_SP1001A,SND_M_SP2001C,SND_M_SP2001E,SND_M_SP2002S,SND_M_SP2002E,SND_M_SP2003A,SND_CLIFFSIDEAMB_LP,SND_TIMEPORTAL_LP,SND_GLASS_SMASH,SND_M_SP2004C,SND_SWORD_CRACK_BIG,SND_SWORD_CRACK_SMALL,SND_MIRROR_CRACK,SND_MIRROR_RESET
2|SPIR35.WAD|SBP_SPIR35|blk|8|138416|SND_AMB_INTERIOR_LP,SND_AMB_INTERIOR2_LP,SND_HOOK_RELEASE,SND_DOOR_LOCK_OPEN,SND_BIGDOOR_OPEN,SND_CLAW1_RELEASE,SND_CLAW2_RELEASE,SND_M_SP3501C,SND_M_SP3501E,SND_M_SP3502A,SND_M_SP4001Q,SND_M_SP2003A,SND_M_SP3503C,SND_M_SP3503E
2|SPIR40.WAD|SBP_SPIR40|blk|40|394224|SND_AMB_INTERIOR_LP,SND_AMB_INTERIOR2_LP,SND_AMB_INTERIOR3_LP,SND_D_CL05,SND_D_CL04,SND_D_CL03,SND_D_CL02,SND_D_CL01,SND_D_GA17,SND_D_2301GA,SND_D_2302GA,SND_D_2303GA,SND_M_SP2003A,SND_M_SP4001Q,SND_M_SP4002S,SND_M_SP4002E,SND_M_SP4003C,SND_M_SP4003E,SND_M_SP4004S,SND_M_SP4005S,SND_M_SP4005E,SND_M_SP4006S,SND_M_SP4007A,SND_M_SP4006E,SND_ARM_SWING,SND_ARM_SWINGWHOOSH,SND_ARM_GLOP,SND_ARM_HITGROUND,SND_BLADE1_SWING,SND_BLADE2_SWING,SND_STONEBARS_LP,SND_SPEARLOWER_LP,SND_FLOORDOOR_LP,SND_VASESLIDE_LP,SND_VASESLIDE_LOCK,SND_VASE_RAISE_LP,SND_VASE_RAISE_LOCK,SND_STONEPEDESTAL_LP,SND_ELEVATOR_LP,SND_BIGARM_SWING,SND_BIGARM_SWING_FAST,SND_BIGARM_HITGROUND,SND_BIGARMGLOP,SND_PULLEY_SLIDE_LP,SND_PULLEY_SPIN_LP,SND_PULLEY_BODYSTOP,SND_PULLEY_SPIN2_LP,SND_PULLEY_BLADESTOP,SND_BLADETURN_LP,SND_BLADELAUNCH,SND_BLADEHITSISTER,SND_SPEAR_IMPACT,SND_SPINDLE_POPUP,SND_SUCCESS,SND_FAIL,SND_HOURGLASS_LP,SND_BREATH_LP,SND_BREATH_LP_2,SND_BREATH_LP_3,SND_BREATH,SND_SPINDLESPIN_LP,SND_CHAINCREAK,SND_ASS_GRAB,SND_ASS_SLIDE,SND_NOTCH_LIGHT,SND_VASEHANDSE_LP
2|SPIR50.WAD|SBP_SPIR50|blk|17|287344|SND_AMB_INTERIOR_LP,SND_D_25H01GA,SND_BLOCK_ELEVATOR_LP,SND_BLOCK_ELEV_STOP,SND_MIRROR_LP,SND_D_GA16,SND_M_SP5001S,SND_HOURGLASS_LP,SND_BREATH_LP,SND_BREATH,SND_BREATH_LP_2,SND_BREATH_LP_3,SND_M_SP4004S,SND_EARTHQUAKE_LP,SND_MIRROR_RESET
2|ZEUS10.WAD|SBP_ZEUS10|blk|1|105120|SND_AMB_OUTDOOR_LP,SND_D_25B03ZE,SND_D_25B03aZE,SND_D_25B04ZE,SND_D_25B05ZE,SND_D_25B06ZE,SND_D_25B07ZE,SND_D_25B08ZE,SND_D_25C01ZE,SND_D_25D01ZE,SND_D_25D02ZE,SND_D_25D04ZE,SND_D_25D06ZE,SND_D_25D07ZE,SND_D_25D09ZE,SND_D_25D09aZE,SND_D_25B02KR,SND_D_KR08,SND_D_KR03ALT1,SND_D_KR02ALT1,SND_D_KR01ALT1,SND_D_ZE11,SND_D_ZE10,SND_D_ZE09,SND_D_ZE03,SND_RAIN_LP,SND_M_ZE1001C,SND_D_KR05,SND_D_ZERAND,SND_M_ZE1001Q,SND_M_ZE1002C"""

_CATALOG = []


def load_catalog():
    if not _CATALOG:
        for line in CATALOG_TXT.split("\n"):
            f = line.split("|")
            if len(f) == 7:
                _CATALOG.append((int(f[0]), f[1], f[2], f[3], int(f[4]), int(f[5]),
                                 [x for x in f[6].split(",") if x]))
    return _CATALOG


def catalog_search(rows, query):
    """Cocokkan query (huruf besar/kecil diabaikan) ke nama WAD, SBK, atau nama suara."""
    q = query.strip().lower()
    if not q:
        return list(rows)
    return [r for r in rows if q in (r[1] + " " + r[2] + " " + " ".join(r[6])).lower()]


class CatalogDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.rows = load_catalog()
        self.shown = []
        self.title(tr("k_title"))
        self.geometry("760x560")
        n1 = len({r[1] for r in self.rows if r[0] == 1})
        n2 = len({r[1] for r in self.rows if r[0] == 2})
        ttk.Label(self, wraplength=730, text=tr("k_intro", len(self.rows), n1, n2)).pack(
            anchor="w", padx=8, pady=(8, 2))
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=4)
        ttk.Label(top, text=tr("k_search")).pack(side="left")
        self.q = tk.StringVar(value="")
        ttk.Entry(top, textvariable=self.q).pack(side="left", fill="x", expand=True, padx=6)
        self.q.trace_add("write", lambda *a: self.fill())

        cols = ("game", "wad", "sbk", "tipe", "sampel")
        self.tv = ttk.Treeview(self, columns=cols, show="headings", height=14)
        heads = (tr("k_game"), tr("k_wad"), tr("k_sbk"), tr("col_type"), tr("k_samples"))
        for c, t, w in zip(cols, heads, (60, 150, 190, 70, 70)):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8))
        self.tv.pack(fill="both", expand=True, padx=(8, 0))
        self.tv.bind("<<TreeviewSelect>>", lambda e: self.show())

        self.detail = ttk.Label(self, wraplength=730, justify="left", text=tr("k_pick"))
        self.detail.pack(fill="x", padx=8, pady=4)
        bt = ttk.Frame(self)
        bt.pack(fill="x", padx=8, pady=6)
        ttk.Button(bt, text=tr("k_open"), command=self.open_selected).pack(side="left")
        ttk.Button(bt, text=tr("btn_close"), command=self.destroy).pack(side="right")
        self.fill()

    def fill(self):
        self.shown = catalog_search(self.rows, self.q.get())
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(self.shown):
            self.tv.insert("", "end", iid=str(i), values=(
                GAMES[r[0]]["name"], r[1], r[2], "VAG" if r[3] == "vag" else "SBK", r[4]))

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
        self.detail.config(text=tr("k_detail", GAMES[r[0]]["name"], r[1], r[2], r[5],
                                   len(r[6]), names or "-"))

    def open_selected(self):
        r = self.current()
        if not r:
            messagebox.showinfo(tr("info"), tr("k_pick_first"), parent=self)
            return
        dirs = []
        if self.app.path:
            dirs.append(os.path.dirname(self.app.path))
        if getattr(self.app, "last_dir", None):
            dirs.append(self.app.last_dir)
        for d in dirs:
            for name in (r[1], r[1].lower(), r[1].upper()):
                path = os.path.join(d, name)
                if os.path.isfile(path):
                    self.app.open_path(path)
                    self.app.select_sbk(r[2])
                    return
        messagebox.showinfo(tr("k_nf_t"), tr("k_nf", r[1]), parent=self)


def log_error(text):
    """Catat error ke gow_tool_error.txt (di samping exe/script; cadangan: folder temp)."""
    for d in _settings_dirs():
        try:
            path = os.path.join(d, "gow_tool_error.txt")
            with open(path, "a", encoding="utf-8") as f:
                f.write(text + "\n" + "-" * 60 + "\n")
            return path
        except OSError:
            continue
    return None


FILTERS = ("flt_sbk", "flt_file", "flt_all")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("780x520")
        try:  # tema "clam" tampil konsisten di Windows asli maupun Wine
            ttk.Style(self).theme_use("clam")
        except tk.TclError:
            pass
        self.set_icon()
        self.buf = None
        self.path = None
        self.entries = []
        self.dirty = False
        self.last_dir = None
        self._st = ("status_none", ())
        self.build_ui()

    def set_icon(self):
        try:
            self._icon = tk.PhotoImage(data=ICON_B64)
            self.iconphoto(True, self._icon)
        except Exception:
            pass

    # ---- tampilan ----
    def build_ui(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Button(bar, text=tr("btn_open"), command=self.open_wad).pack(side="left")
        ttk.Button(bar, text=tr("btn_edit"), command=self.edit_audio).pack(side="left", padx=4)
        ttk.Button(bar, text=tr("btn_export"), command=self.export).pack(side="left")
        ttk.Button(bar, text=tr("btn_replace_file"), command=self.replace).pack(side="left", padx=4)
        ttk.Button(bar, text=tr("btn_save"), command=self.save).pack(side="left")
        ttk.Button(bar, text=tr("btn_save_as"), command=self.save_as).pack(side="left", padx=4)
        ttk.Button(bar, text=tr("btn_debug"), command=self.debug).pack(side="left")
        ttk.Label(bar, text=tr("lbl_filter")).pack(side="left", padx=(12, 4))
        self.filter = ttk.Combobox(bar, width=9, state="readonly", values=[tr(k) for k in FILTERS])
        self.filter.current(0)
        self.filter.pack(side="left")
        self.filter.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        # kolom path manual: berguna kalau dialog file Wine bermasalah
        row = ttk.Frame(self)
        row.pack(fill="x", padx=8)
        self.path_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.path_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text=tr("btn_path"), command=lambda: self.open_path(
            self.path_var.get().strip().strip('"'))).pack(side="left", padx=4)
        ttk.Button(row, text=tr("btn_catalog"), command=lambda: CatalogDialog(self)).pack(side="left")

        row2 = ttk.Frame(self)
        row2.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Label(row2, text=tr("lbl_lang")).pack(side="left")
        self.lang_box = ttk.Combobox(row2, width=20, state="readonly", values=[n for _c, n in LANGS])
        self.lang_box.current([c for c, _n in LANGS].index(LANG))
        self.lang_box.pack(side="left", padx=6)
        self.lang_box.bind("<<ComboboxSelected>>", lambda e: self.change_language())

        cols = ("name", "type", "offset", "size")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        heads = (tr("col_name"), tr("col_type"), tr("col_offset"), tr("col_size"))
        for c, t, w in zip(cols, heads, (280, 90, 110, 100)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8))
        self.tree.pack(fill="both", expand=True, padx=(8, 0))
        self.tree.bind("<Double-1>", lambda ev: self.edit_audio())
        self.status = ttk.Label(self, text="")
        self.status.pack(fill="x", side="bottom", padx=8, pady=6)
        self.render_status()

    def set_status(self, key, *args):
        self._st = (key, args)
        self.render_status()

    def render_status(self):
        self.status.config(text=tr(self._st[0], *self._st[1]))

    def change_language(self):
        global LANG
        code = LANGS[self.lang_box.current()][0]
        if code == LANG:
            return
        LANG = code
        save_lang(code)
        keep_path, keep_filter = self.path_var.get(), self.filter.current()
        for w in list(self.winfo_children()):  # dialog yang terbuka ikut ditutup
            w.destroy()
        self.build_ui()
        self.path_var.set(keep_path)
        self.filter.current(keep_filter)
        self.refresh()

    def report_callback_exception(self, exc, val, tb):
        text = "".join(traceback.format_exception(exc, val, tb))
        path = log_error(text)
        messagebox.showerror(tr("err_title"), text[-1500:] + (tr("logged", path) if path else ""))

    # ---- helpers ----
    @staticmethod
    def kind(e):
        if e.is_sbk:
            return "SBK-VAG" if e.magic == SBK_VAG else "SBK"
        return hex(e.tag & 0xFFFF)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        mode = FILTERS[self.filter.current()]
        for i, e in enumerate(self.entries):
            if mode == "flt_sbk" and not (e.is_sbk and has_audio(self.buf, e)):
                continue
            if mode == "flt_file" and not e.is_file:
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
            messagebox.showinfo(tr("info"), tr("pick_file"))
            return None
        return self.entries[int(sel[0])]

    # ---- actions ----
    def open_wad(self):
        try:
            p = filedialog.askopenfilename(
                title=tr("open_title"), filetypes=[(tr("ft_all"), "*.*"), ("WAD", "*.wad")])
        except Exception:
            messagebox.showerror(tr("dlg_err"), traceback.format_exc())
            return
        if p:
            self.open_path(p)

    def open_path(self, p):
        try:
            if not p or not os.path.isfile(p):
                messagebox.showerror(tr("err_title"), tr("not_found", p))
                return
            size = os.path.getsize(p)
            if size > MAX_WAD_SIZE:
                messagebox.showerror(tr("not_wad"), tr("too_big", size // (1024 * 1024)))
                return
            with open(p, "rb") as f:
                head = f.read(HDR)
                if not looks_like_wad(head):
                    messagebox.showerror(tr("not_wad"), tr("not_gow"))
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
            gname = GAMES[self.entries[0].game]["name"] if self.entries else "?"
            if total > n:
                self.set_status("opened_h", os.path.basename(p), gname, len(self.buf),
                                len(self.entries), n, total - n)
            else:
                self.set_status("opened", os.path.basename(p), gname, len(self.buf),
                                len(self.entries), n)
            if not self.entries:
                messagebox.showwarning(tr("no_entries_t"), tr("no_entries"))
            elif n == 0:
                messagebox.showinfo(tr("no_sbk_t"), tr("no_sbk"))
        except Exception:
            messagebox.showerror(tr("open_fail"), traceback.format_exc())

    def debug(self):
        if self.buf is None:
            messagebox.showinfo(tr("btn_debug"), tr("dbg_need"))
            return
        b = bytes(self.buf[:0x100])
        lines = []
        for i in range(0, len(b), 16):
            c = b[i:i + 16]
            lines.append("%04X  %-47s  %s" % (
                i, " ".join("%02X" % x for x in c),
                "".join(chr(x) if 32 <= x < 127 else "." for x in c)))
        w = tk.Toplevel(self)
        w.title(tr("dbg_title"))
        t = tk.Text(w, width=84, height=20, font=("Courier", 9))
        t.pack(fill="both", expand=True)
        t.insert("end", tr("dbg_text", self.path, len(self.buf), len(self.entries), "\n".join(lines)))

    def edit_audio(self):
        e = self.selected()
        if not e:
            return
        try:
            SbkDialog(self, e)
        except ValueError as ex:
            messagebox.showerror(tr("edit_fail"), str(ex))
        except Exception:
            messagebox.showerror(tr("err_title"), traceback.format_exc())

    def export(self):
        e = self.selected()
        if not e:
            return
        p = filedialog.asksaveasfilename(initialfile=e.name)
        if p:
            with open(p, "wb") as f:
                f.write(self.buf[e.data_off:e.data_off + e.size])
            self.set_status("exported", e.name)

    def replace(self):
        e = self.selected()
        if not e:
            return
        if not e.is_file:
            messagebox.showinfo(tr("info"), tr("not_data"))
            return
        p = filedialog.askopenfilename(title=tr("ask_replace_file", e.name),
                                       filetypes=[(tr("ft_all"), "*.*")])
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
            if not messagebox.askyesno(tr("bigger_t"), tr("bigger", len(new), old)):
                return
            new_slot = (len(new) + ALIGN - 1) & ~(ALIGN - 1)
            blob, size_field = new + b"\x00" * (new_slot - len(new)), len(new)
        self.buf[e.data_off:e.data_off + old_slot] = blob
        struct.pack_into("<I", self.buf, e.size_off, size_field)
        self.entries = scan(self.buf)
        self.dirty = True
        self.refresh()
        self.set_status("file_replaced", e.name, len(new))

    def save(self):
        """Tulis hasil edit ke file WAD asli; salinan asli disimpan sebagai .bak (sekali)."""
        if self.buf is None:
            messagebox.showinfo(tr("info"), tr("dbg_need"))
            return
        try:
            bak = self.path + ".bak"
            made = not os.path.exists(bak)
            if made:
                shutil.copy2(self.path, bak)
            with open(self.path, "wb") as f:
                f.write(self.buf)
            self.dirty = False
            self.set_status("saved_status", os.path.basename(self.path))
            messagebox.showinfo(tr("saved_t"), tr("saved_text", self.path,
                                                  tr("bak_new", bak) if made else tr("bak_old", bak)))
        except Exception:
            messagebox.showerror(tr("save_fail"), traceback.format_exc())

    def save_as(self):
        """Simpan hasil edit ke nama/lokasi lain; WAD asli tidak disentuh."""
        if self.buf is None:
            messagebox.showinfo(tr("info"), tr("dbg_need"))
            return
        try:
            p = filedialog.asksaveasfilename(
                title=tr("saveas_title"), initialfile=os.path.basename(self.path))
            if not p:
                return
            with open(p, "wb") as f:
                f.write(self.buf)
            self.dirty = False
            self.set_status("saved_status", os.path.basename(p))
            messagebox.showinfo(tr("saved_t"), tr("saved_as", p))
        except Exception:
            messagebox.showerror(tr("save_fail"), traceback.format_exc())


def choose_language():
    """Jendela pilih bahasa saat pertama kali dibuka. None kalau ditutup tanpa memilih."""
    root = tk.Tk()
    root.title("Language / Bahasa / Idioma")
    root.geometry("340x250")
    chosen = {"v": None}

    def pick(code):
        chosen["v"] = code
        root.destroy()

    ttk.Label(root, text=I18N["lang_pick"][0], justify="center").pack(pady=14)
    for code, name in LANGS:
        ttk.Button(root, text=name, command=lambda c=code: pick(c)).pack(fill="x", padx=50, pady=5)
    root.mainloop()
    return chosen["v"]


def main():
    global LANG
    try:
        code = load_lang()
        if not code:
            code = choose_language() or "en"
            save_lang(code)
        LANG = code
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
            messagebox.showerror(tr("start_fail"), text[-1500:] + (tr("logged", path) if path else ""))
        except Exception:
            print(text)
        sys.exit(1)


if __name__ == "__main__":
    main()


