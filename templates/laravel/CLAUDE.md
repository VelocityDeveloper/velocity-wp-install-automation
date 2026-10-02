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
- **SOLID & DRY (wajib)**: kode ditulis mengikuti prinsip SOLID dan DRY, secukupnya tanpa abstraksi berlebihan.
  - *S* — satu kelas satu tanggung jawab: controller hanya menerima permintaan & mengembalikan respons; aturan
    bisnis di kelas Action/Service kecil (`app/Actions/<Modul>/<KataKerja>…`), validasi di Form Request, hak akses
    di Policy, kueri berulang di scope model.
  - *O* — tambah perilaku dengan kelas/enum/strategi baru, bukan menumpuk `if/switch` jenis di kode lama
    (mis. status & tipe pakai Enum PHP yang punya method `label()`).
  - *L* — implementasi interface/turunan bisa saling menggantikan tanpa mengubah pemanggil.
  - *I* — interface kecil dan spesifik; jangan memaksa kelas mengimplementasikan method yang tak dipakai.
  - *D* — bergantung pada abstraksi lewat dependency injection (constructor/method injection, service container),
    bukan `new` layanan di tengah logika; layanan luar (pembayaran, WA, email) dibungkus interface agar mudah di-fake di tes.
  - *DRY* — logika/kueri/aturan validasi/teks yang dipakai ≥2 tempat dipusatkan: trait atau Action bersama (PHP),
    komponen Vue / composable (`resources/js/composables`) / util (`resources/js/lib`) di frontend, konstanta &
    Enum untuk nilai tetap. Sebelum menulis baru, cari yang sudah ada dan pakai ulang. Jangan menyalin blok kode
    antar halaman/controller; jangan membuat komponen kembar yang beda sedikit — beri prop.
- **Props Inertia**: kirim hanya kolom yang dipakai halaman (`only()`/Resource), jangan seluruh model.
- **Frontend**: pakai komponen di `components/ui` dulu sebelum membuat sendiri; rute lewat Wayfinder
  (`@/routes`, `@/actions`), bukan URL ditulis tangan.
- **Unggahan**: whitelist `extensions` + `mimes`, simpan di disk privat dan sajikan lewat controller yang
  memeriksa hak akses. Jangan simpan berkas pengguna di `public/`.
- **Seeder**: data demo dipisah dari data wajib; seeder tidak boleh menimpa sandi akun yang sudah ada dan
  tidak boleh jalan di production.
- **Rahasia**: `.env`, sandi, dan token tidak pernah masuk repo, log, atau pesan commit.
- **Pengaturan aplikasi (wajib, dari installer — jangan dihapus)**: Pengaturan > Aplikasi (`/settings/aplikasi`,
  `AppSettingController`, model `Setting` kunci–nilai) untuk nama aplikasi, deskripsi aplikasi, unggah logo, dan
  unggah favicon; dibagikan ke semua halaman sebagai prop `site` (`name`, `description`, `logo_url`, `favicon_url`,
  `can_manage`). Tanpa unggahan dipakai logo & favicon contoh (`public/images/logo-contoh.png`, `public/favicon.ico`).
  Logo/nama aplikasi di mana pun ambil dari `site` (`AppLogo`/`AppLogoIcon`), bukan teks/ikon ditulis tangan.
  Hak kelola = Gate `manage-app-settings` (`AppSettingServiceProvider`): sesudah peran dibuat, pastikan hanya admin.
  Pengaturan tambahan dari PRD (mis. alamat, kontak, warna) ditambahkan ke halaman & model yang sama.
- **Model `Setting` = satu-satunya tempat pengaturan aplikasi (wajib)**: tabel `settings` berkolom `key` (string 64,
  primary) dan `value` (text, nullable). SEMUA pengaturan tingkat aplikasi yang bisa diubah admin — identitas,
  kontak, alamat, sosmed, warna, teks halaman depan, sakelar fitur, dll. — disimpan sebagai baris kunci–nilai di
  sini: baca `Setting::value('kunci')`, tulis `Setting::put('kunci', $nilai)` (cache otomatis dibersihkan).
  Jangan membuat tabel/model pengaturan lain (`app_settings`, `school_settings`, …), kolom pengaturan di tabel lain,
  atau menyimpannya di `.env`/`config`. Kunci `snake_case`; berkas unggahan disimpan sebagai path di kunci
  `<nama>_path` (pola `Setting::IMAGES`/`replaceImage`). Kunci bawaan: `app_name`, `app_description`, `logo_path`,
  `favicon_path`. Nilai awal kunci baru diisi di `SettingSeeder`; nilai bukan teks disimpan sebagai string
  (bool `'1'`/`'0'`, angka, JSON) dan dikonversi di method kecil di model `Setting` (seperti `appName()`).
- **Footer wajib**: `AppFooter` ("© tahun nama aplikasi · Design by Velocity Developer") tetap tampil di semua
  layout (aplikasi, halaman masuk, halaman depan). Layout baru juga memasangnya.

## Sebelum commit

```bash
composer lint       # Pint merapikan PHP
composer ci:check   # npm run check (format/lint JS) + vue-tsc + Pint --test + PHPStan + Pest
```

Pesan commit bergaya Conventional Commits berbahasa Indonesia, mis. `feat(presensi): rekap per pertemuan`,
`fix(krs): batas SKS dari IPS semester lalu`. Satu commit = satu perubahan yang utuh; push ke `main` di
`{{GITHUB}}` hanya bila tes lolos.
