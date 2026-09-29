# {{JUDUL}}

Aplikasi Laravel standar tim Velocity, dibuat installer Laravel dashboard kantor pada {{TANGGAL}}.
Klien: {{KLIEN}} · Domain produksi: {{DOMAIN}} · Repo: https://github.com/{{GITHUB}}

**Spesifikasi dari PM (wajib dibaca sebelum mengubah apa pun):** `docs/PRD.md` (peran, fitur, kriteria terima),
`DESIGN.md` (token warna, tipografi, komponen), `docs/DATABASE.md` (tabel & relasi, ERD Mermaid), dan
`docs/FLOWCHART.md` (alur proses per peran). Keduanya hasil diskusi dengan klien; bila kode dan dokumen
bertentangan, dokumen yang menang — tanyakan ke PM, jangan menebak.

## Stack (jangan diganti tanpa persetujuan lead)

Installer resmi `laravel new --vue`: Laravel + Inertia + Vue 3 (TypeScript) + Tailwind 4, komponen UI
shadcn-vue/reka-ui di `resources/js/components/ui`, auth Fortify, rute ke frontend lewat Wayfinder, tes Pest,
Laravel Boost untuk agen AI. Database MariaDB. Tambah paket baru hanya bila benar-benar perlu, dan tulis alasannya
di pesan commit.

## Lingkungan dev (Local PC 192.168.88.211)

- Aplikasi: {{URL}} · folder `/home/{{SLUG}}` · database `{{SLUG}}` (nama dengan `_`), kredensial di `.env`.
- Layanan systemd `{{SLUG}}-dev` (artisan serve) dan `{{SLUG}}-queue` berjalan sebagai user sistem `{{PENGGUNA}}`.
- Sesudah menjalankan `artisan`, `composer`, atau tes sebagai root: `chown -R {{PENGGUNA}}:{{PENGGUNA}} storage bootstrap/cache`,
  kalau tidak, aplikasi gagal menulis log/cache.
- Perbarui dev dari GitHub + build + migrasi + restart: `/root/{{SLUG}}/deploy-dev.sh`.
- Akun uji ada di kartu **Project Lokal** dashboard (http://192.168.88.211/projects), bukan di kode.
- Batas unggah PHP layanan: `/etc/{{SLUG}}/php.d/` (flag `php -d` tidak diwarisi `artisan serve`).

## Konvensi tim

- **Bahasa**: semua teks yang dilihat pengguna berbahasa Indonesia (locale `id`). Pesan validasi butuh berkas
  terjemahan di `lang/id/` — tanpa itu pengguna melihat kunci mentah seperti `validation.required`.
- **Waktu**: zona `Asia/Jakarta` (`APP_TIMEZONE`). Jam yang dikirim ke frontend harus ber-offset +07:00;
  jangan menampilkan tanggal UTC mentah.
- **Nama**: tabel, model, dan kolom boleh berbahasa Indonesia bila itu istilah bisnis klien, tapi konsisten
  dalam satu modul. Ikuti struktur yang sudah ada sebelum membuat folder baru.
- **Backend**: validasi di Form Request, otorisasi di Policy/Gate, logika bisnis di model atau kelas layanan kecil —
  controller tetap tipis. Kueri daftar wajib `with()` untuk relasi yang ditampilkan (hindari N+1) dan dipaginasi.
- **Props Inertia**: kirim hanya kolom yang dipakai halaman (`only()`/Resource), jangan seluruh model.
- **Frontend**: pakai komponen di `components/ui` dulu sebelum membuat sendiri; rute lewat Wayfinder
  (`@/routes`, `@/actions`), bukan URL ditulis tangan.
- **Unggahan**: whitelist `extensions` + `mimes`, simpan di disk privat dan sajikan lewat controller yang
  memeriksa hak akses. Jangan simpan berkas pengguna di `public/`.
- **Seeder**: data demo dipisah dari data wajib; seeder tidak boleh menimpa sandi akun yang sudah ada dan
  tidak boleh jalan di production.
- **Rahasia**: `.env`, sandi, dan token tidak pernah masuk repo, log, atau pesan commit.

## Sebelum commit

```bash
composer lint       # Pint merapikan PHP
composer ci:check   # npm run check (format/lint JS) + vue-tsc + Pint --test + PHPStan + Pest
```

Pesan commit bergaya Conventional Commits berbahasa Indonesia, mis. `feat(presensi): rekap per pertemuan`,
`fix(krs): batas SKS dari IPS semester lalu`. Satu commit = satu perubahan yang utuh; push ke `main` di
`{{GITHUB}}` hanya bila tes lolos.
