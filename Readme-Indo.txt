========================================================================
 GOW SBK TOOLS BY NICHO  -  v1.0
 Editor audio SBK / SBP untuk file WAD God of War 1 & 2 (PS2)
========================================================================

APA ITU?
Tool PC (jalan di Windows dan di Wine/Winlator) untuk mengedit audio yang
ada di dalam file WAD God of War 1 dan God of War 2 (PS2): buka WAD, pilih
SBK, putar / export / ganti suaranya dengan WAV milikmu, lalu SAVE.

ISI PAKET
  Readme-Indo.txt        : petunjuk ini (Bahasa Indonesia)
  Informasi-Indo.txt     : apa yang bisa dan tidak bisa dilakukan tool ini
  Readme-Eng.txt / Information-Eng.txt      : versi English
  Leia-me-Br.txt / Informacoes-Br.txt       : versi Português (Brasil)
  Katalog_SBK.txt        : daftar semua SBK/SBP beserta nama suaranya
  SBK Tools\             : folder programnya (SBK_Tools.exe + file pendukung)

PENTING: jangan memindahkan SBK_Tools.exe saja ke tempat lain. Exe ini butuh
DLL dan file lain di sebelahnya. Bawa dan simpan SELURUH folder "SBK Tools".

CARA PAKAI (singkat)
  1. Siapkan file .WAD. Tool ini TIDAK membuka PAK, TOC, atau ISO. Ekstrak
     dulu WAD dari PAK dengan tool lain (misalnya God of War Browser).
  2. Jalankan SBK_Tools.exe. Saat pertama dibuka kamu diminta memilih bahasa
     (Indonesia / English / Português). Bisa diganti kapan saja dari kotak
     "Bahasa" di jendela utama.
  3. Klik "Buka WAD" lalu pilih file WAD. Kalau dialog file bermasalah di
     Wine, tempel lokasi file di kolom path lalu klik "Buka path".
     Tidak tahu WAD mana yang berisi suara yang kamu cari? Klik
     "Katalog SBK" lalu cari nama WAD / SBK / suara.
  4. Pilih SBK di daftar, lalu klik "Edit audio" (atau klik dua kali).
  5. Pilih satu sampel lalu:
       Putar        = dengar sampel asli
       Export WAV   = simpan sampel asli sebagai file WAV
       Dengar WAV   = dengar WAV-mu dulu sebelum dimasukkan
       Replace dari WAV = ganti sampel dengan WAV-mu
  6. Klik SAVE di jendela utama. Hasil edit ditulis ke WAD aslinya dan
     salinan WAD asli otomatis disimpan sebagai NAMA.WAD.bak (sekali saja).
     Mau hasilnya di file lain? Pakai "Save As".
  7. Masukkan WAD hasil edit kembali ke PAK / ISO game dengan tool lain.

SAMPLE RATE
  - Bank VAG: sample rate asli dibaca dari file, tidak perlu diatur.
  - Bank audio internal: rate asli tidak tersimpan di file. Tool memakai
    22050 Hz sebagai tebakan. Klik Putar; kalau suara terdengar terlalu
    lambat / cepat, ubah angka "Sample rate" sampai normal, lalu pakai
    angka yang sama saat Replace.

JIKA WAV-MU LEBIH PANJANG DARI SLOT ASLI
Pilih satu mode di kotak "Jika audio lebih panjang dari slot":
  - Perbesar WAD : audio tidak dipotong, WAD jadi lebih besar. ISO perlu
                   di-rebuild dan game bisa crash kalau terlalu besar.
                   Di sebagian kecil sampel mode ini DITOLAK dengan aman
                   (header SBK tidak bisa digeser dengan aman) dan WAD
                   tidak diubah. Pakai mode lain untuk sampel itu.
  - Turunkan rate: ukuran WAD tetap; kualitas lebih rendah (hanya bank VAG).
  - Potong       : ukuran WAD tetap; bagian yang berlebih dibuang.
WAV yang lebih pendek dari slot selalu aman (sisanya diisi senyap dan
ukuran WAD tidak berubah).

TIPS UNTUK PEMULA
  - Selalu kerja di SALINAN. Simpan PAK / ISO aslimu.
  - Ubah satu hal per percobaan, lalu tes di game. Jangan menumpuk banyak
    perubahan sekaligus; kalau crash, kamu tidak tahu penyebabnya.
  - Mulai dari WAV yang lebih pendek dari aslinya (paling aman).

JIKA ADA ERROR / BUG
Tool mencatat error ke file  gow_tool_error.txt  (di samping exe) dan
menampilkan lokasinya di jendela error. Kirim teks error itu (atau fotonya)
beserta nama WAD dan SBK yang kamu buka ke pembuat tool.

WINLATOR / WINE
Pakai versi folder ini (bukan exe satu file). Kalau tampilan atau dialog
file bermasalah, pakai kolom path + tombol "Buka path".

========================================================================
 Gow SBK Tools by Nicho
========================================================================
