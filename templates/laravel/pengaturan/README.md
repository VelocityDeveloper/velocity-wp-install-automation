# Pengaturan aplikasi (dipasang installer Laravel)

Berkas di folder ini disalin apa adanya ke aplikasi baru oleh `scripts/laravel-pengaturan`
(langkah "Pengaturan aplikasi" di `scripts/laravel-installer`). Skrip yang sama menambal berkas
starter kit (rute, HandleInertiaRequests, app.blade.php, app.ts, layout) serta membuat logo & favicon contoh
dari inisial nama aplikasi.

Isi: nama aplikasi, deskripsi aplikasi, unggah logo, unggah favicon (Pengaturan > Aplikasi, `/settings/aplikasi`),
footer "Design by Velocity Developer" di semua layout, serta bagian "Mesin pencari": sakelar izinkan mesin pencari
(`search_engine_indexing`) dan kode verifikasi Google Search Console (`google_site_verification`, ditempel sesudah
deploy produksi). `SitemapController` menyajikan `/sitemap.xml` (rute GET publik + `contentUrls()`) dan `/robots.txt`;
`public/robots.txt` bawaan Laravel dibuang supaya rutenya terpakai.

Model `Setting` (tabel `settings`: `key` string 64 primary, `value` text nullable) adalah satu-satunya tempat
pengaturan aplikasi: kunci bawaan `app_name`, `app_description`, `logo_path`, `favicon_path`,
`search_engine_indexing`, `google_site_verification`; pengaturan tambahan
(alamat, kontak, sosmed, warna, sakelar fitur) ditambahkan sebagai kunci baru lewat `Setting::value`/`Setting::put`,
bukan tabel/kolom/`.env` baru. Aturan lengkap di `templates/laravel/CLAUDE.md`.
