========================================================================
 GOW SBK TOOLS BY NICHO  -  v1.1
 Editor audio SBK / SBP untuk file WAD God of War 1 & 2 (PS2)
========================================================================

ISI PAKET
  Readme-Indo.txt        : petunjuk ini (Bahasa Indonesia)
  Informasi-Indo.txt     : apa yang bisa dan tidak bisa dilakukan tool ini
  Readme-Eng.txt / Information-Eng.txt      : versi English
  Leia-me-Br.txt / Informacoes-Br.txt       : versi Português (Brasil)
  Katalog_SBK.txt        : daftar semua SBK/SBP beserta nama suaranya
  SBK Tools\             : folder programnya (SBK_Tools.exe + file pendukung)

PENTING: jangan memindahkan SBK_Tools.exe saja ke tempat lain. Exe ini butuh
DLL dan file lain di sebelahnya. Bawa dan simpan SELURUH folder "SBK Tools".

APA ITU?
Tool PC (Windows dan Wine/Winlator) untuk mengedit audio di dalam file WAD God of War 1
dan God of War 2 (PS2). Buka ISO game (atau satu WAD, atau folder WAD), pilih SBK, lalu
putar / export / ganti suaranya dengan WAV milikmu, dan SIMPAN.

CARA PAKAI (singkat)
  1. Jalankan SBK_Tools.exe. Saat pertama dibuka kamu memilih bahasa (Indonesia / English /
     Português); bisa diganti kapan saja lewat kotak "Bahasa".
  2. Buka sumbernya:
       Buka ISO         : baca ISO God of War 1 atau 2. Klik tanda > di PART1.PAK / PART2.PAK
                          untuk melihat daftar WAD (dibaca lewat GODOFWAR.TOC di ISO).
                          Hanya WAD yang berisi suara yang tampil; VPK, VAG, PSS/PSW dan WAD
                          tanpa SBK disembunyikan.
       Buka WAD         : membuka satu file .WAD lepas.
       Buka folder WAD  : menampilkan semua .WAD di sebuah folder.
     Kalau dialog file bermasalah di Wine, tempel lokasi file (.iso atau .wad) di kolom path
     lalu klik "Buka path". Tidak tahu suara ada di WAD mana? Klik "Katalog SBK", cari, lalu
     "Buka WAD ini" (kalau ISO sudah terbuka, tool langsung menuju WAD itu).
  3. Klik sebuah WAD di pohon "Sumber" (kiri); daftar SBK-nya muncul di kanan.
  4. Pilih SBK lalu klik "Edit audio" (atau klik dua kali).
  5. Pilih satu sampel lalu:
       Putar            = dengar sampel asli
       Export WAV       = simpan sampel asli sebagai WAV
       Dengar WAV       = dengar WAV-mu dulu sebelum dimasukkan
       Replace dari WAV = ganti sampel dengan WAV-mu
  6. Klik SAVE di jendela utama:
       WAD lepas : hasil ditulis ke file aslinya; salinan asli disimpan sekali sebagai
                   NAMA.WAD.bak.
       Dari ISO  : WAD ditulis langsung ke ISO, ke SEMUA lokasi salinannya, dan isi aslinya
                   disimpan di NAMA.iso.sbkbak. Tombol "Kembalikan ISO" memulihkan semuanya.
     "Simpan sebagai" menulis WAD yang dipilih ke file lain.

SAMPLE RATE
  - Bank VAG: sample rate asli dibaca dari file, tidak perlu diatur.
  - Bank audio internal: rate asli tidak tersimpan di file. Tool memakai 22050 Hz sebagai
    tebakan. Klik Putar; kalau terlalu lambat / cepat, ubah angka "Sample rate" sampai normal,
    lalu pakai angka yang sama saat Replace.

JIKA WAV-MU LEBIH PANJANG DARI SLOT ASLI
Pilih mode di kotak "Jika audio lebih panjang dari slot":
  - Perbesar WAD : audio tidak dipotong, WAD jadi lebih besar. Hanya untuk WAD LEPAS (tidak
                   tersedia untuk WAD dari ISO, karena ukuran WAD di ISO harus tetap).
                   Di sebagian kecil sampel mode ini DITOLAK dengan aman (header SBK tidak
                   bisa digeser dengan aman) dan WAD tidak diubah.
  - Turunkan rate: ukuran WAD tetap; kualitas lebih rendah (hanya bank VAG).
  - Potong       : ukuran WAD tetap; bagian yang berlebih dibuang.
WAV yang lebih pendek dari slot selalu aman (sisanya diisi senyap, ukuran WAD tidak berubah).

CATATAN ISO
  - GoW 1 mencatat satu WAD di beberapa tempat (PART1 dan PART2), dan GoW 2 juga menyimpan
    sebagian WAD lebih dari satu salinan. Tool menulis semua salinan supaya konsisten.
  - Sebelum menulis, tool memeriksa penanda WAD di tiap lokasi; kalau tidak cocok, tidak ada
    yang ditulis.
  - Kerjakan di SALINAN ISO, dan tutup program lain yang sedang memakai ISO itu.

TIPS UNTUK PEMULA
  - Selalu kerja di SALINAN. Simpan ISO aslimu.
  - Ubah satu hal per percobaan, lalu tes di game. Jangan menumpuk banyak perubahan.
  - Mulai dari WAV yang lebih pendek dari aslinya (paling aman).

JIKA ADA ERROR / BUG
Tool mencatat error ke gow_tool_error.txt (di samping exe) dan menampilkan lokasinya di
jendela error. Kirim teks error (atau fotonya) beserta nama WAD dan SBK yang kamu buka.

WINLATOR / WINE
Pakai versi folder ini (bukan exe satu file). Kalau tampilan atau dialog file bermasalah,
pakai kolom path + tombol "Buka path".

========================================================================
 Gow SBK Tools by Nicho
========================================================================
