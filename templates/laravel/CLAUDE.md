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
- Akun contoh lokal/dev (juga di kartu **Project Lokal** http://192.168.88.211/projects): satu akun per peran,
  email `<peran>@example.com` (mis. `admin@example.com`, `guru@example.com`), sandi `password`.
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
  (`@/routes`, `@/actions`), bukan URL ditulis tangan. Jangan pakai `Route::redirect`/`Route::permanentRedirect`/
  `Route::any` (mendaftarkan verb QUERY yang belum dikenal Wayfinder → `vue-tsc` gagal); pengalihan pakai
  `Route::get('a', fn () => to_route('b'))`.
- **Unggahan**: whitelist `extensions` + `mimes`, simpan di disk privat dan sajikan lewat controller yang
  memeriksa hak akses. Jangan simpan berkas pengguna di `public/`.
  **Gambar yang diunggah (jpg/png/gif/bmp) WAJIB disimpan sebagai WebP**: konversi di satu layanan bersama
  (mis. `app/Support/ImageToWebp.php`, GD `imagewebp`, kualitas ±80, sisi terpanjang maks 1920px, transparansi
  PNG tetap), berlaku untuk semua unggahan (logo, foto, galeri, gambar di editor). Pengecualian: SVG, favicon
  `.ico`, dan berkas bukan gambar (PDF, dokumen) disimpan apa adanya.
- **Pustaka media (bila app butuh banyak gambar)**: bila PRD punya banyak gambar yang dikelola admin (galeri, foto
  produk/kamar/kegiatan, banner, gambar di isian editor, logo/favicon dipilih ulang), pakai pola pustaka media
  seperti project `/home/hotel-booking`: paket `spatie/laravel-medialibrary` (^11) + model `Asset` (`HasMedia`,
  koleksi `file` singleFile, kolom `title`/`alt`/`caption`/`uploaded_by`/`width`/`height`, `Asset::store()` untuk
  simpan + konversi WebP, konversi `thumb`/`large`/`preview` WebP nonQueued, `toLibraryArray()` untuk prop).
  Halaman admin Media (`/admin/media`: grid, unggah banyak, ubah judul/alt, hapus, info "dipakai di") lewat
  `AssetController`; SATU komponen pemilih bersama (`MediaBrowser.vue` + field `AppImageField.vue`) dipakai di
  semua form gambar dan di `RichTextEditor` (sisip gambar dari pustaka). Tabel lain menyimpan `asset_id`
  (FK `nullOnDelete`), bukan path berkas; gambar contoh seeder ikut masuk pustaka (seeder lewat `Asset::store`).
  Disk `public` (URL relatif `/storage`, jalankan `storage:link`) khusus gambar tampilan publik; berkas pribadi
  pengguna tetap disk privat. App yang hanya punya 1–2 unggahan (mis. logo + foto profil) TIDAK perlu pustaka ini.
- **Seeder**: setiap model wajib punya factory + seeder (`database/seeders/<Model>Seeder.php`) yang dipanggil
  `DatabaseSeeder` berurutan sesuai relasi, berisi data contoh realistis — `php artisan migrate:fresh --seed`
  harus mengisi semua tabel model. Seeder aman diulang (`firstOrCreate`/`updateOrCreate`). Data demo dipisah
  dari data wajib; seeder tidak boleh menimpa sandi akun yang sudah ada dan data demo tidak boleh jalan di production.
  Akun contoh non-production selalu `@example.com` dengan sandi `password` (di production sandi dari env/acak).
- **Rahasia**: `.env`, sandi, dan token tidak pernah masuk repo, log, atau pesan commit.
- **Pengaturan aplikasi (wajib, dari installer — jangan dihapus)**: Pengaturan > Aplikasi (`/settings/aplikasi`,
  `AppSettingController`, model `Setting` kunci–nilai) untuk nama aplikasi, deskripsi aplikasi, unggah logo, dan
  unggah favicon; dibagikan ke semua halaman sebagai prop `site` (`name`, `description`, `logo_url`, `favicon_url`,
  `can_manage`). Tanpa unggahan dipakai logo & favicon contoh (`public/images/logo-contoh.png`, `public/favicon.ico`).
  Logo/nama aplikasi di mana pun ambil dari `site` (`AppLogo`/`AppLogoIcon`), bukan teks/ikon ditulis tangan.
  Hak kelola = Gate `manage-app-settings` (`AppSettingServiceProvider`): sesudah peran dibuat, pastikan hanya admin.
  Pengaturan tambahan dari PRD (mis. alamat, kontak, warna) ditambahkan ke halaman & model yang sama.
- **Sitemap & Google Search Console (wajib, dari installer — jangan dihapus)**: `/sitemap.xml` dan `/robots.txt`
  (`SitemapController`) dibentuk otomatis dari rute GET publik tanpa parameter (rute ber-middleware `auth`/`guest`/
  `verified` tidak ikut). Konten publik ber-slug (artikel, produk, halaman, dll.) WAJIB ditambahkan di
  `SitemapController::contentUrls()` (`loc` + `lastmod`). Jangan membuat `public/robots.txt` (menutupi rute).
  Pengaturan > Aplikasi bagian "Mesin pencari": sakelar `search_engine_indexing` (`'0'` = app internal → robots
  `Disallow: /`, sitemap 404, meta noindex) dan `google_site_verification` (isi `content` tag meta, tampil di
  `<head>`). Aplikasi internal yang seluruhnya wajib login: matikan sakelar di `SettingSeeder`. Kode verifikasi
  ditempel dan sitemap dikirim ke Search Console SESUDAH deploy produksi, bukan saat pengembangan.
- **Model `Setting` = satu-satunya tempat pengaturan aplikasi (wajib)**: tabel `settings` berkolom `key` (string 64,
  primary) dan `value` (text, nullable). SEMUA pengaturan tingkat aplikasi yang bisa diubah admin — identitas,
  kontak, alamat, sosmed, warna, teks halaman depan, sakelar fitur, dll. — disimpan sebagai baris kunci–nilai di
  sini: baca `Setting::value('kunci')`, tulis `Setting::put('kunci', $nilai)` (cache otomatis dibersihkan).
  Jangan membuat tabel/model pengaturan lain (`app_settings`, `school_settings`, …), kolom pengaturan di tabel lain,
  atau menyimpannya di `.env`/`config`. Kunci `snake_case`; berkas unggahan disimpan sebagai path di kunci
  `<nama>_path` (pola `Setting::IMAGES`/`replaceImage`). Kunci bawaan: `app_name`, `app_description`, `logo_path`,
  `favicon_path`, `search_engine_indexing`, `google_site_verification`. Nilai awal kunci baru diisi di `SettingSeeder`; nilai bukan teks disimpan sebagai string
  (bool `'1'`/`'0'`, angka, JSON) dan dikonversi di method kecil di model `Setting` (seperti `appName()`).
- **Perilaku UI wajib (semua app)**:
  - *Menu navigasi*: klik item menu → laci/menu langsung menutup sendiri lalu halaman tujuan tampil, dengan
    transisi halus ±200ms (ease-out, tanpa hentakan). Di HP pakai `setOpenMobile(false)` dari `useSidebar()`
    saat item diklik; menu halaman publik (hamburger) juga menutup otomatis saat pindah halaman.
  - *Mode gelap*: tombol ikon matahari/bulan `AppearanceToggle.vue` (dipasang installer di `AppSidebarHeader`
    dan `AppHeader`) ada di header, pojok kanan atas — di header dashboard dan di header halaman publik. Bukan
    di sidebar atau menu pengguna. Menu Pengaturan > Tampilan sengaja dibuang installer; jangan dibuat lagi.
  - *Header dashboard sticky di HP*: di layar kecil (<768px) header dashboard menempel di atas saat digulir
    (`max-md:sticky max-md:top-0 max-md:z-30 max-md:bg-background`, sudah dipasang installer). Layout/header
    dashboard baru wajib mempertahankannya.
  - *Tombol "Lihat situs"*: app yang punya situs publik (halaman depan/katalog/profil untuk tamu) wajib punya
    tombol "Lihat situs" di header dashboard, di samping tombol mode gelap — `LihatSitusButton.vue` (dipasang
    installer, buka halaman publik `home()` di tab baru; di HP tinggal ikon). App tanpa situs publik (halaman
    depan langsung ke login) membuang tombol ini dari `AppSidebarHeader`/`AppHeader`.
  - *Tombol Simpan sticky*: form panjang (Pengaturan dan form ber-field banyak) memakai bar aksi yang menempel
    di bawah layar (`sticky bottom-0`, latar kartu, garis atas tipis) berisi Simpan (+ Batal bila ada),
    sehingga tidak perlu menggulir ke bawah untuk menyimpan. Buat sekali sebagai komponen bersama, pakai ulang.
  - *Select tidak menabrak*: pilihan yang teksnya panjang tidak boleh meluber/menabrak ikon chevron atau field
    sebelah. Trigger `SelectTrigger` diberi `w-full min-w-0`, teks nilai `truncate` (+ `title` berisi teks
    lengkap); daftar opsi (`SelectContent`) dibatasi lebar layar dan opsi panjang terlipat rapi
    (`whitespace-normal break-words`), bukan memotong layar. Berlaku juga untuk combobox/multiselect dan di HP.
  - *Halaman masuk bervariasi*: halaman login/daftar/lupa sandi JANGAN dibiarkan polos (form kecil di latar
    kosong). Pakai `AuthSplitLayout` atau kartu dengan panel visual: warna/gradasi dari token DESIGN.md, logo +
    `site.name` + `site.description`, ilustrasi/pola SVG atau foto yang sesuai jenis usaha klien, tagline
    singkat. Tiap project dibuat berbeda (sesuai DESIGN.md), tetap rapi di HP (panel visual diringkas di atas form).
  - *Editor teks berformat*: field konten di dashboard (deskripsi, isi, konten, profil, syarat & ketentuan,
    pengumuman, dll.) pakai SATU komponen bersama `RichTextEditor.vue` (Tiptap: `@tiptap/vue-3` +
    `@tiptap/starter-kit`, + `@tiptap/extension-image` bila perlu gambar — unggahan gambarnya ikut jadi WebP),
    bukan `<textarea>`. HTML disanitasi di server sebelum disimpan (kelas `App\Support\RichTextSanitizer`,
    `symfony/html-sanitizer`: buang script, atribut `on*`, `style`, `javascript:`) lalu ditampilkan dengan
    `v-html` + gaya tipografi. `<textarea>` hanya untuk teks polos: alamat, catatan/alasan singkat, meta
    description, kode/embed, isian yang dikirim ke WA/SMS.
  - *Halaman publik bisa diatur*: isi halaman publik yang wajar diubah klien (judul & teks hero, gambar/banner,
    tentang kami, layanan unggulan, kontak, alamat, jam buka, peta, sosmed, nomor WhatsApp, teks footer) TIDAK
    di-hardcode di Vue — jadikan kunci `Setting` dan form-nya di Pengaturan (kelompokkan, mis. tab "Halaman
    Depan"/"Kontak"), nilai awal di `SettingSeeder`. Yang tetap boleh statis: struktur/tata letak dan label UI.
  - *Tidak bisa hapus akun sendiri*: secara bawaan TIDAK ADA pengguna yang bisa menghapus akunnya sendiri,
    termasuk admin utama — installer sudah membuang rute `profile.destroy`, `DeleteUser.vue`, dan
    `ProfileDeleteRequest`; jangan dibuat lagi. Sistem harus selalu punya minimal satu super admin: di
    manajemen pengguna admin tidak bisa menghapus, menonaktifkan, atau menurunkan peran akunnya sendiri, dan
    super admin terakhir tidak bisa dihapus/dinonaktifkan/diturunkan perannya oleh siapa pun (cek di server
    + tombol disembunyikan, ada tesnya). Bila PRD meminta pengguna non-admin boleh menghapus akun, buka lewat
    kunci `Setting` `allow_self_delete` (bawaan `'0'`), tetap tidak berlaku untuk super admin terakhir.
  - *WhatsApp mengambang*: halaman publik punya tombol WhatsApp mengambang di kanan bawah (nomor & pesan awal
    dari `Setting`, mis. `whatsapp_number`/`whatsapp_message`, tautan `https://wa.me/<62…>?text=…` tab baru).
    Di desktop berbentuk pil ikon + label (mis. "Chat WhatsApp"); di HP (<640px) label disembunyikan, tinggal
    tombol bulat ikon. Tidak tampil bila nomor kosong. Satu komponen bersama, dipasang di layout publik.
  - *Ikon WhatsApp = logo resmi*: SEMUA ikon WhatsApp (tombol mengambang, kontak, footer, tombol "Hubungi via
    WA", tabel) memakai logo WhatsApp asli (SVG path brand, mis. dari Simple Icons, warna #25D366 atau putih di
    atas hijau) lewat satu komponen `WhatsAppIcon.vue` — bukan ikon lucide `MessageCircle`/`Phone`.
  - *Kembali ke atas*: halaman publik punya tombol mengambang "kembali ke atas" (ikon panah atas, ukuran dan
    tinggi sejajar tombol WhatsApp mengambang, posisinya di sebelah kanan tombol WA), muncul setelah digulir
    ±400px, menggulir halus ke atas (`behavior: 'smooth'`, langsung bila `prefers-reduced-motion`).
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
