Anda memecah PRD aplikasi Laravel menjadi daftar fitur yang akan dikerjakan agen Claude Code satu per satu
(satu sesi agen per fitur, berurutan), lalu diperiksa webmaster. Estimasi ini untuk INTERNAL tim.

Stack tetap: `laravel new --vue` (Laravel 13, Inertia, Vue 3 + TypeScript, Tailwind 4, shadcn-vue/reka-ui,
Fortify: login, registrasi, lupa sandi, verifikasi email, 2FA, halaman profil & sandi SUDAH ADA dari starter kit —
jangan dijadikan fitur kecuali PRD meminta perubahan).

Aturan:
- Fitur pertama selalu **Fondasi**: terapkan DESIGN.md ke tema (warna, font, radius) dan tata letak aplikasi,
  bahasa Indonesia untuk antarmuka & pesan validasi (lang/id), zona waktu, peran & hak akses dasar dari PRD,
  serta menu navigasi kerangka.
- Urutkan sesuai ketergantungan (data master sebelum transaksi, transaksi sebelum laporan).
- Satu fitur = hasil yang bisa diperiksa sendiri, cukup kecil untuk satu sesi agen (idealnya ≤ 2 jam agen).
  Pecah fitur PRD yang besar; gabungkan yang terlalu kecil.
- `kriteria`: salin/turunkan dari kriteria terima PRD, tiap poin BISA DIUJI (tes Pest atau dicek di browser),
  3–8 poin per fitur. Tambahkan kriteria yang tersirat tapi penting (validasi, hak akses per peran).
- `jam_agen`: perkiraan waktu kerja agen (menulis kode + tes), angka desimal jam.
- `jam_webmaster`: perkiraan waktu webmaster memeriksa di browser + merapikan hal kecil, angka desimal jam.
- `deskripsi`: apa yang dibangun (halaman, tabel/migrasi, aturan bisnis), cukup jelas untuk agen.

Selain fitur, isi `tambahan` = pekerjaan DI LUAR fitur sampai aplikasi diserahkan ke klien. Wajib ada:
penyesuaian dari jawaban klien atas pertanyaan terbuka PRD, UAT (klien mencoba & mengumpulkan revisi),
revisi hasil UAT (±20–30% dari total jam fitur, sesuaikan dengan kerumitan & banyaknya pertanyaan terbuka),
deploy produksi, serta serah terima & pelatihan. Tambahkan impor data awal bila klien punya data lama
(Excel dsb.) atau PRD menyebutnya. Per baris: `jam_agen` dan `jam_webmaster` (jam kerja saja, tanpa waktu menunggu klien).

<prd>
{{PRD}}
</prd>

<design>
{{DESIGN}}
</design>

<database>
{{DATABASE}}
</database>
