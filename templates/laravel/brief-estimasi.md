{{PLATFORM}}

Aturan:
- Fitur pertama selalu **Fondasi**: {{FONDASI}}
- Urutkan sesuai ketergantungan (data master sebelum transaksi, transaksi sebelum laporan).
- Satu fitur = hasil yang bisa diperiksa sendiri.
  Pecah fitur PRD yang besar; gabungkan yang terlalu kecil. Ukuran: {{UKURAN}}.
- `halaman`: sel Matriks peran × halaman (di PRD) yang dibangun fitur ini: `halaman` disalin PERSIS dari kolom
  pertama matriks, `peran` = nama kolom peran yang selnya bukan `–`. SETIAP sel berakses di matriks wajib masuk
  minimal satu fitur — periksa ulang per peran sebelum selesai (celah paling sering: halaman admin/pemantau untuk
  data yang dibuat peran lain). Bila PRD tidak punya matriks, isi dari bagian Peran pengguna & Fitur.
- `kriteria`: salin/turunkan dari kriteria terima PRD, tiap poin BISA DIUJI ({{UJI}}),
  3–8 poin per fitur. Tambahkan hanya kriteria yang tersirat tapi penting agar fitur itu benar (validasi, hak akses per peran), bukan fitur baru.
- `jam_agen`: {{JAM_AGEN}}
- `jam_webmaster`: {{JAM_WEBMASTER}}
- `deskripsi`: {{DESKRIPSI}}

Selain fitur, isi `tambahan` = pekerjaan DI LUAR fitur sampai aplikasi diserahkan ke klien. Wajib ada:
penyesuaian dari jawaban klien atas pertanyaan terbuka PRD, UAT (klien mencoba & mengumpulkan revisi),
revisi hasil UAT (±20–30% dari total jam fitur, sesuaikan dengan kerumitan & banyaknya pertanyaan terbuka),
deploy produksi, serta serah terima & pelatihan. Tambahkan impor data awal bila klien punya data lama
(Excel dsb.) atau PRD menyebutnya. Per baris: `jam_agen` dan `jam_webmaster` (jam kerja saja, tanpa waktu menunggu klien).

{{CAKUPAN}}

{{KONTEN}}
Bila tanda PM di atas mewajibkan konten bersekat/page builder tetapi PRD belum memuat fiturnya, tetap buat fitur itu.

<prd>
{{PRD}}
</prd>

<design>
{{DESIGN}}
</design>

<database>
{{DATABASE}}
</database>
