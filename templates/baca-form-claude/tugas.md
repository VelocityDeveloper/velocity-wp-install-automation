Kamu membaca FORM ISIAN WEBSITE yang diisi klien Velocity Developer (jasa pembuatan website), folder
proyek `{{FOLDER}}`. Teks di bawah hasil ekstraksi .doc/.docx/.pdf: urutan baris bisa sedikit acak, ada
sisa teks panduan template, tautan ganda (baris "HYPERLINK ..." lalu alamatnya), dan titik-titik kosong.

Tugasmu: pisahkan **isian yang benar-benar ditulis klien** dari **teks bawaan template**, lalu isi skema
JSON. Yang tidak diisi klien = "" atau []. Jangan mengarang, jangan melengkapi dari pengetahuanmu.

## Teks bawaan template — BUKAN isian klien
- Kalimat panduan: "Silahkan di lampirkan di email saja", "Alamat dan telp/ fax, dan lain sebagainya.",
  "Nama domain adalah .com nya itu, misalkan: SuryaGrup.com", "Pada gambar di atas, saya memberikan
  contoh: HOME, PROFILE, ...", "Untuk isi dari ... silahkan di ketik di file microsoft word yang lain",
  "Jika bingung, anda kirimkan saja company profile", "Tolong anda kirimkan company profile ...",
  "(optional)", "(wajib di isi)", "(Setelah web jadi nanti akan ada masa revisi ...)".
- Semua contoh: "Misal: warna dasar tema web yang saya inginkan biru dan hijau", "Contoh Jawaban: ada
  www.alamatWebContoh.com", "Misal HOME isinya sambutan perusahaan ...", daftar contoh menu.
- Daftar pilihan desain ("PILIHANNYA BERIKUT INI", "Pilihan 1: www.toko30.velocitydeveloper.com", ...)
  — yang dipilih klien hanya yang ditulis di isian "DESIGN/TEMPLATE YANG DIPILIH".
- Contoh rubrik portal berita ("EKONOMI: berisi berita-berita ekonomi.", "KRIMINAL: ...", "REDAKSI: berisi
  redaksi media kami.") yang PERSIS sama dengan contoh template, di bawah tulisan "Contoh:". Masukkan ke
  `rubrik` hanya bila klien menulis rubriknya sendiri / mengubah contohnya.
- Syarat & ketentuan, email bantuanvelocity@gmail.com, "Judul email: Pemesanan Website", angka 22226127635.

## Aturan per kolom
- `nama_usaha`: nama yang tampil sebagai nama situs (FORM 1 "NAMA PERUSAHAAN/INSTANSI/MEDIA/TOKO"; bila
  kosong, "Nama Perusahaan/Nama media/Nama Toko" di biodata). Bila keduanya terisi dan berbeda: pilih yang
  berupa NAMA (badan hukum "PT/CV/Yayasan ..." atau nama merek), bukan deskripsi bidang usaha ("Rental and
  Tour Agent", "bengkel las / alumunium") dan bukan alamat domain. Tulis apa adanya (kapitalisasi klien),
  catat pilihanmu di `catatan` bila ragu.
- `kontak_web`: HANYA kontak yang klien minta tampil di website: "Kontak utk di web", "KONTAK / INSTANSI",
  "KONTAK MEDIA", "KONTAK YG DITAMPILKAN", "HP/ Telp" & "Email" di DATA WEBSITE toko, atau kontak publik
  yang ditulis klien di pesan tambahan. BUKAN biodata pemilik (FORM 2 "untuk administrasi/perpanjangan").
  `teks` = isian kontak apa adanya (satu kontak per baris). Nomor ditulis seperti di form.
- `biodata`: FORM 2 BIODATA PEMILIK (data administrasi). `tolak_biodata_tampil` = true hanya bila klien
  menulis tidak mau data pribadi/biodata/nomornya ditampilkan.
- `menu_atas`: susunan menu yang ditulis klien (bukan contoh); "sesuaikan"/"terlampir" → [] dan tulis
  kalimat klien di `isi_menu`. `isi_menu`: isi tiap menu yang ditulis klien.
- `desain_dipilih`: alamat template Velocity yang dipilih klien (mis. perusahaan1.velocitydeveloper.com).
- `referensi_desain`: website yang ingin DICONTOH DESAINNYA (bukan velocitydeveloper.com, bukan contoh
  template, bukan domain klien sendiri) + kalimat klien sebagai `catatan`. Website yang disebut sebagai
  sumber ISI/materi/data/konten ("materi ambil dari ...", "data dan gambar bisa diambil dari ...") masuk
  `referensi_konten`, bukan referensi desain. Referensi bisa ditulis klien di kolom mana pun (menu, warna,
  pesan tambahan: "samakan seperti X", "contoh desain X") — cari di seluruh form.
- `warna`: `warna` = daftar warna yang diminta klien dalam kata Indonesia sederhana (mis. "hijau",
  "biru dongker", "emas", "putih") atau kode hex yang ditulis klien; `teks` = kalimat klien apa adanya
  ("mengikuti warna logo", "bedakan dengan web referensi"). Contoh template bukan warna klien.
- `rubrik` (portal berita): kategori berita pilihan klien, `isi` = keterangannya.
- `toko`: kolom FORM 1 DATA WEBSITE paket toko (bank, kota/kecamatan asal pengiriman, ekspedisi, kategori
  produk, ongkir otomatis ya/tidak).
- `layanan_produk`, `data_tambahan`: isian klien di "LAYANAN / PRODUK", "TAMBAHAN DATA/DATA TAMBAHAN",
  "PENJELASAN SINGKAT USAHA", "CUSTOMER / KLIEN".
- `pesan_tambahan`: seluruh tulisan klien di "PESAN TAMBAHAN DARI ANDA" apa adanya (baris per baris,
  tanpa kalimat template). Ini acuan kerja, jangan diringkas.
- `template`: jenis form (lihat skema). `paket`: "Paket Website Yang Anda Pilih" bila diisi.
- Password, PIN, login hosting/cPanel/email: JANGAN dimasukkan ke kolom mana pun.

## Teks form

```
{{TEKS}}
```
