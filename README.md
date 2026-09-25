# Velocity WordPress install automation

n8n-driven WordPress installer for DirectAdmin servers only. cPanel is not supported.

## Arsitektur

```
n8n (Manual Trigger {domain}) → Dry-run validate → IF dry_run ok? → Apply install → IF applied? → Success
                                   ↓ fail              ↓ fail
                              validation_failed    failed(apply)
```

Secrets tidak ada di workflow JSON — masuk via file terproteksi (env `*_FILE`).

## Required n8n environment contract

Set di n8n service environment, bukan di workflow JSON:

- `WP_INSTALL_SSH_KEY_FILE` — path private key (perm 0400/0600, owned root)
- `WP_INSTALL_DB_PASSWORD_FILE` — file berisi DB password
- `WP_INSTALL_ADMIN_PASSWORD_FILE` — file berisi WP admin password
- `WP_INSTALL_GITHUB_TOKEN_FILE` — opsional; untuk private repo Velocity

Secret files harus **not world-readable** (others=0), validator akan reject jika `perms` = `*44/*45/*46/*47`.

## Manifest

Location: `/home/project/<domain>/<domain>.txt`.

```ini
target_host=103.103.175.182
ssh_port=22
ssh_user=deploy
da_user=directadmin_user
domain=example.com
db_name=example_wp
db_user=example_wp
admin_user=admin
admin_email=admin@example.com
site_title=Example
velocity_addons_repo=https://github.com/VelocityDeveloper/velocity-addons.git
velocity_theme_repo=https://github.com/VelocityDeveloper/velocity-theme.git
```

Validasi: `target_host`, `domain` (FQDN), `da_user/ssh_user` (linux user), `db_name/db_user` (alnum+_), `admin_email`, `ssh_port` 1-65535. Repos harus `https://...`.

### Staging untuk klien berhosting di luar (`docroot=` + `site_url=`)

Klien yang hostingnya bukan milik kita (domain "LUAR" di catatan PM) tidak bisa dipasangi
installer di tempatnya. Pekerjaannya dikerjakan di staging `velocitydeveloper.co/<domain>`
dengan dua kunci tambahan:

```ini
docroot=/home/vdco/domains/velocitydeveloper.co/public_html/example.com
site_url=https://velocitydeveloper.co/example.com
```

- `website-install-from-manifest` memasang WordPress di `docroot` itu (bukan
  `/home/<da_user>/domains/<domain>/public_html`), memakai `site_url` untuk `wp core install`,
  dan menulis `.htaccess` dengan `RewriteBase /<subfolder>/`. Dry-run juga memeriksa folder
  dan sertifikat SSL milik host staging.
- `installer-runner` menurunkan `VELOCITY_LOKAL_DOCROOT`, `VELOCITY_LOKAL_SSH` (skrip
  pembungkus ssh yang dibuat otomatis) dan `VELOCITY_LOKAL_URL` dari kedua kunci itu, jadi
  `fse-apply`, `site-finish`, `site-audit`, `paket-g-foto`, `paket-g-cek-visual`,
  `fse-audit-kemiripan` dan `ai-content-generator.py` bekerja di staging — bukan di situs
  klien yang asli.
- Tanpa kedua kunci itu perilakunya persis seperti sebelumnya.

Database harus sudah ada. `apply` menginstall WordPress di `public_html` target, membuat `wp-config.php` (tanpa `--skip-check`), `wp core install` idempoten (skip jika sudah installed), dan install plugin/theme via `git clone` + `wp plugin/theme activate` (bukan `wp plugin install <git-url>`).

## Manual dry run

```bash
INSTALL_MODE=dry-run \
MANIFEST=/home/project/example.com/example.com.txt \
./scripts/website-install-from-manifest
# atau via wrapper
./scripts/n8n-run-install dry-run example.com
```

## Apply

Hanya via n8n setelah dry-run OK:

```bash
INSTALL_MODE=apply \
MANIFEST=/home/project/example.com/example.com.txt \
WP_INSTALL_SSH_KEY_FILE=/run/secrets/wp-install-ssh-key \
WP_INSTALL_DB_PASSWORD_FILE=/run/secrets/wp-install-db-password \
WP_INSTALL_ADMIN_PASSWORD_FILE=/run/secrets/wp-install-admin-password \
./scripts/website-install-from-manifest
```

Behavior apply:
- `flock` per-domain cegah paralel apply
- cek `wp-cli`, `git`, `php` ada di remote
- cek disk space ≥500MB
- backup `public_html` → `/home/<da_user>/backup/pre-install-<domain>-<timestamp>.tar.gz` jika tidak kosong
- secrets di-inject via `export` di stdin (single-quote escaped), bukan di `ps` argv

Destruktif: tulis file WP & DB state di target. Backup dibuat otomatis; rollback operator: `tar -xzf backup.tar.gz -C public_html`.

## Development workflow

Develop anywhere:

```bash
git clone https://github.com/VelocityDeveloper/velocity-wp-install-automation.git
cd velocity-wp-install-automation
# edit files
git add .
git commit -m "Describe change"
git push origin main
```

Update server with one command:

```bash
cd /opt/velocity-wp-install-automation
git pull --ff-only origin main
./deploy.sh
```

`deploy.sh` validates Bash and workflow JSON, installs runtime files, restarts status API, checks Nginx, and reloads Nginx. It never changes credential files or n8n encryption settings. Keep server-only secrets outside repository.

## Installer status API (`services/installer_status.py`)

Loopback `127.0.0.1:9121`.

Service dijalankan **langsung dari file repo ini** (lihat `config/installer-status.service`), sama seperti script di `scripts/` — tidak ada salinan di `/usr/local/bin`. Jadi menerapkan perubahan cukup `systemctl restart installer-status.service`. Pasang/perbarui unit-nya sekali dengan:

```bash
install -m 644 config/installer-status.service /etc/systemd/system/installer-status.service
systemctl daemon-reload && systemctl restart installer-status.service
```

`deploy.sh` menolak jalan kalau unit masih menunjuk path lama, supaya deploy tidak sukses semu tanpa mengubah apa pun.

Endpoints:
- `GET /health` — no auth
- `GET /api/servers` — daftar server dari `/var/lib/velocity/servers.json` (managed panel `/server/`) atau fallback `config/servers.json` / env `INSTALLER_SERVERS`, plus `index`, `default` (urutan pertama = tujuan manifest baru) dan `domains` (jumlah manifest ber-`target_host` itu).
- `POST /api/servers` (tambah; dengan `index` = edit di tempat), `/api/servers/delete`, `/api/servers/default`, `/api/servers/test` (SSH dengan kunci installer: hostname + ada/tidaknya DirectAdmin) — semuanya memakai `index`.
- `GET /api/installer` — daftar domain + validasi manifest + cronjobs summary (cache 30s, tidak bocor raw crontab) + state/log per-domain dari `/var/lib/velocity/installer`.
- `POST /api/installer/run` — body `{"domain":"example.com","mode":"dry-run"|"apply"|"finish"|"maintenance"|"child-theme"|"audit"}`. Validasi domain + manifest, tolak `already_running`, spawn `scripts/installer-runner` detached (log ke `/var/lib/velocity/installer/<domain>.log`). Browser pakai endpoint ini untuk tombol install/retry. Saat `apply`, service menyetel `WP_INSTALL_SSH_KEY_FILE` (auto-detect `/etc/velocity/secrets/ssh_key` atau `/root/.ssh/id_ed25519`/`id_rsa`) + `WP_INSTALL_DB_PASSWORD_FILE`/`WP_INSTALL_ADMIN_PASSWORD_FILE` per-domain dari `/etc/velocity/secrets/`.
- `POST /api/installer/generate` — body `{"domain":"example.com"}`. Auto-generate manifest (da_user/db dari label domain, admin_email dari `notes-credentials.txt` bila ada) + secret password random per-domain (tidak pernah menimpa yang sudah ada). Domain tanpa manifest valid bisa langsung di-generate dari tombol `[ generate ]` di halaman installer.

Auth: jika `INSTALLER_API_TOKEN` di-set, semua `/api/*` butuh `Authorization: Bearer <token>`. Rate-limit 30 req/60s per IP. Jangan expose port 9121 langsung — via reverse proxy (blok location referensi: `config/nginx-installer.conf`).

## Manage server page (`web/server/index.html`)

Terminal-style `/server/`, API-nya di `installer_status.py` (sejak 2026-09-18; `server-registry.service` / `/usr/local/bin/server_registry.py` port 9122 dimatikan). Nginx: `location /api/servers` -> 9121 di kedua blok server. Aturan:
- Edit per posisi (`index`), urutan tidak berubah. Dulu simpan = hapus + tambah di akhir, sehingga mengedit server pertama diam-diam mengganti tujuan default installer, dan ganti IP membuat entri ganda.
- Urutan hanya berubah lewat `[ jadikan default ]`. Host tidak boleh ganda.
- Hapus ditolak bila masih ada manifest yang memakai host itu, atau bila tinggal satu server. Ganti host server yang dipakai manifest harus dikonfirmasi (`pindah_host`), dan manifest lama tetap menunjuk host lama.
- `[ tes SSH ]` mencoba SSH dengan kunci installer.
- Galat simpan ditampilkan di form/modal. Mutasi memakai `_check_auth` (token wajib dari luar LAN).

## Installer page (`web/installer/index.html`)

Terminal-style `/installer/`.

- pilih server tujuan (dari `/api/servers`)
- lihat validasi manifest (READY vs `missing_*/invalid_*`) + log 30 baris terakhir
- tombol `[ generate ]` — domain tanpa manifest valid (NO_MANIFEST/missing_*/invalid_*) → auto-generate manifest + secret password → status jadi READY
- tombol `[ install ]` (status READY/SUCCESS) atau `[ retry ]` merah (status FAILED/installer_error) → modal konfirmasi dengan pilihan mode: **Dry run** (validasi saja) atau **Apply** (eksekusi nyata) → `POST /api/installer/run`
- tombol `[ log ]` → popup detail log 30 baris terakhir
- polling 10s, pause saat `document.hidden`
- **Isi daftar = halaman `project_list` CRM.** Antrean ditarik dari `GET /api/api/public/project-list` untuk **dua** status sekaligus (`CRM_STATUSES`): `Belum dikerjakan` → baris berstatus `belum diambil`, dan `Dalam pengerjaan` → baris berstatus `dikerjakan webmaster` (ikon `◑`, badge `WM: <nama>`, aksi **Ambil alih** memakai konfirmasi karena ada orang yang sedang memegangnya). Autopilot & `onprogress-sync` hanya menyentuh `belum diambil`, jadi baris webmaster tampil tanpa pernah ditabrak. Saringan jenisnya `INSTALL_JENIS` dan nilainya **harus persis sama** dengan opsi `jenis_project` di CRM (`DataOpsiController::jenis_project`) — `Pembuatan Tanpa Domain` sempat ditulis di sini padahal nilai aslinya `Pembuatan Tanpa Domain+Hosting`, dan barisnya tidak pernah muncul sama sekali tanpa galat apa pun. `Pengembangan` sengaja di luar daftar: situsnya sudah hidup, bukan pekerjaan pasang baru (keputusan user 2026-09-16).
- Filter deadline bawaannya **semua deadline** (2026-09-16) — bawaan lama "deadline belum terlewat" menyembunyikan 11 dari 26 baris, sehingga daftar di layar tidak pernah cocok dengan `project_list` walau datanya benar.
- **Bukan project** (mis. server host kantor sendiri): daftar dirakit dari folder `/home/On Progress` + folder `/home/project` + antrean CRM, sehingga folder yang kebetulan ada di `/home/project` ikut terbawa walau bukan pekerjaan klien. Domain di `BUKAN_PROJECT_BAWAAN` (`services/installer_status.py`, saat ini `fahmi.hutara.com`) dan baris di `/etc/velocity/installer-bukan-project` (satu domain per baris, `#` komentar) disembunyikan dari daftar **sekaligus** ditolak `claim` & `run` dengan galat `bukan_project` — menyembunyikan saja tidak cukup, karena `POST /api/installer/run` menerima domain apa pun dan `apply` di host server berarti menimpanya dengan WordPress. Manifest tanpa `paket=` sengaja TIDAK dipakai sebagai penanda otomatis: `arusaraadventure.com` & `pondokbungaadi.com` juga tanpa `paket=` dan keduanya project sungguhan yang sudah terpasang.
- **Bagan proses** (panel "Proses berjalan" di atas filter + aksi "Bagan proses" per domain): simpul tiap langkah `installer-runner` (validasi, install WordPress, cek HTTP, baca referensi desain, tema FSE, VD Store, konten AI, finishing, bersih-bersih, foto slot, halaman blok, foto artikel, cek visual, QA, maintenance, selesai) dengan status menunggu/berjalan/selesai/gagal/dilewati dan durasi, dibaca dari penanda log run terakhir (mulai `RUNNING: VALIDATING`). Domain berstatus RUNNING dipantau tiap 3 detik lewat `GET /api/installer?domain=<domain>` (satu baris, log 1500 baris, tetap bisa dibaca setelah domain terpasang dan hilang dari antrean); kartu yang selesai bertahan 10 menit. Cabang paket yang ada: desain custom (G / Portal Berita Custom / Toko Online Custom) → referensi desain + tema FSE, **Paket E → child theme baku `velocity-pakete`**, Paket F & paket lain → child theme dari referensi form, toko online biasa → child theme lalu VD Store.

  **Aturan tetap (permintaan user 2026-09-16): setiap penambahan atau perubahan alur di `installer-runner` wajib langsung disusulkan ke bagan ini dalam perubahan yang sama** — simpul baru di `SIMPUL`, garisnya di `GARIS`, dan cabang paket baru di `konteksRun` (`web/installer/index.html`). Bagan inilah yang dibaca PM & webmaster; alur yang tidak tergambar sama saja dengan alur yang tidak terlihat. Setelah menyunting halaman, pasang ke web root (`./deploy.sh`, atau `install -m 644 web/installer/index.html /usr/share/nginx/html/installer/index.html`) dan cek hasilnya di `http://192.168.88.211/installer/` — menyunting berkas repo saja tidak mengubah halaman yang dilihat orang.

## Package Manager (`web/packages/index.html`)

Sejak 2026-09-18 paket tidak dikelola di sini (upload/URL/hapus dan endpoint `POST`/`DELETE /api/packages` dihapus). Tema induk `velocity` dan plugin `velocity-addons` yang dipasang installer disinkronkan dari API Velocity (`api.velocitydeveloper.co/api/v1/themes|plugins`, header `signature` = md5 tanggal WIB) ke `/var/lib/velocity/packages/<slug>.zip`. Sinkron berjalan paling cepat tiap 10 menit saat halaman dibuka dan saat manifest digenerate, atau dipaksa lewat `[ sinkron sekarang ]` (`POST /api/packages/sync`). Zip diunduh ulang hanya bila versi API berubah dan harus berisi `<slug>/style.css` (tema) atau `<slug>/<slug>.php` (plugin). Kalau API gagal, zip terakhir tetap dipakai. Halaman menampilkan paket installer serta daftar tema & plugin di API (baca saja).

## Model AI & pemakaian token (`web/ai/index.html`)

Terminal-style `/ai/`: daftar model (`/var/lib/velocity/ai/models.json`), model per fungsi installer, dan pemakaian token per domain.

- Setiap `ai_call()` (`ai-content-generator.py`, dipakai juga `paket-g-konten`, `paket-g-foto`, `fse-apply`) menulis satu baris ke `/var/lib/velocity/ai/usage.jsonl`: `ts, domain, run, mode, peran, script, model_id, model` (model yang benar-benar menjawab), `prompt_tokens, completion_tokens, total_tokens, ok`. Panggilan gagal tetap tercatat (`ok:false`, token 0).
- `installer-runner` mengekspor `VELOCITY_DOMAIN` dan `VELOCITY_RUN_ID` (`<tanggal>-<jam>-<mode>`), jadi semua script AI dalam satu run terkumpul di run yang sama. Script yang dijalankan manual memakai nama manifest sebagai domain dan masuk run "(di luar installer-runner)".
- `GET /api/ai/usage` menjumlah per domain → per run → per fungsi. Angka token berasal dari field `usage` respons endpoint; gateway yang tidak mengirim `usage` tercatat 0.
- Pencatatan dimulai 2026-09-15; run sebelumnya tidak punya data token.

## Workflow (`workflows/website-install-workflow.json`)

Import ke n8n. Trigger: Manual Trigger dengan `{"domain":"example.com"}`. Node `Execute Command` pakai wrapper `scripts/installer-runner` (validasi & escape domain, cegah injection, tulis STATE).

Timeouts: dry-run 30s, apply 300s. Dry-run retry 2x.

## Alur apply lengkap

`installer-runner` (mode `apply`): install WordPress (termasuk child theme: referensi form, atau `velocity-pakete` untuk [Paket E](#paket-e-child-theme-baku-velocity-pakete)) → cek HTTP → terbitkan SSL (`site-ssl`) → konten AI (`ai-content-generator.py`) → finishing (`site-finish`) → hapus tema & plugin bawaan yang tidak dipakai (`site-finish --cleanup`) → [alur Paket G](#alur-paket-g-baku) bila `paket=Paket G` → pemeriksaan akhir (`site-qa`) → maintenance mode (`site-finish --maintenance`) → laporan Telegram ✅ selesai, atau 🟡 "perlu dicek" beserta daftar masalah.

- **Pembersihan** hanya pada run yang memasang WordPress dari awal (bukan apply ulang situs lama, bukan mode finish/maintenance): tema `twenty*` dan plugin `akismet`/`hello` yang tidak aktif. Tema aktif dan induknya tidak pernah dihapus; tema/plugin non-bawaan tidak disentuh.

- **Kepemilikan `wp-content`** (`scripts/pemilik_wp.py`, 2026-09-18): WP-CLI installer berjalan sebagai root, sedangkan `chown -R` docroot hanya ada di akhir `website-install-from-manifest`. Berkas yang dibuat langkah sesudahnya jadi milik root — terutama `wp-content/upgrade` dari `wp theme/plugin install <zip>`, yang membuat pasang/perbarui plugin & tema dari wp-admin gagal (layananhipnoterapi.com: Site Kit & WPCode; 14 situs di server Farnaz). Sekarang setiap skrip langkah yang memanggil WP-CLI (site-finish, fse-apply, fse-dealer, fse-klinik, child-theme-apply, vd-store, vd-store-settings, paket-g-setup, paket-g-konten, paket-g-foto, paket-tour, theme-paket-biasa, ai-content-generator.py) diakhiri `pemilik_wp.rapikan()` (`try/finally`, jadi tetap jalan saat langkahnya gagal), dan `installer-runner` menjalankan `pemilik_wp.py <manifest>` sekali lagi di trap EXIT (juga mode `child-theme`). Pemiliknya = pemilik `wp-content` (atau docroot); `chown -R -h`, tidak mengikuti symlink; dilewati pada dry-run, `--coba`/`--deteksi`, dan bila pemiliknya root. Log: `pemilik: wp_content_dirapikan:<user:grup>:<jumlah>` / `sudah_benar` / `dilewati:<alasan>`. Situs lama tidak dirapikan otomatis; pekerjaan manual sebagai root (termasuk sesi AI) wajib diakhiri `scripts/pemilik_wp.py <manifest>`.

- **Maintenance mode** (plugin velocity-addons, opsi `maintenance_mode` + `maintenance_mode_data`) dinyalakan sebagai langkah terakhir, sesudah pemeriksaan akhir (yang membaca situs sebagai pengunjung). Hanya sekali per situs (penanda opsi `velocity_installer_maintenance`) dan tidak kalau opsinya sudah pernah diatur orang, jadi apply ulang setelah PM mematikannya saat serah terima tidak menyalakannya lagi. `site-qa` mengenali halaman perawatan dan melewati pemeriksaan berbasis beranda.
- **Akun DirectAdmin selalu dibuat manual oleh PM.** Kalau dry-run autopilot gagal karena akun/folder domain belum ada, domain masuk fase `waiting_da`: dry-run diulang tiap 30 menit (maks. 14 hari) tanpa notifikasi, lalu instalasi berlanjut otomatis begitu akun dibuat.
- **Tahap dry-run tidak dilaporkan ke Telegram** (diambil alih, dry-run gagal/macet, situs sudah berisi, menunggu akun DirectAdmin). Statusnya terlihat di jurnal `/var/lib/velocity/installer/autopilot.json` dan halaman installer. Telegram hanya untuk hasil apply: selesai, perlu dicek, atau gagal.

- **Konten AI** dibersihkan `content_sanitize.py` (tanpa `<img>`/`<iframe>`/`<form>`/placeholder). Halaman tulisan installer ditandai meta `_velocity_content_md5`; apply ulang hanya menimpa halaman yang belum disunting orang. Konten tersimpan di `/var/lib/velocity/ai/generated/` dipakai ulang.
- **Bahan AI**: isi FORM ISIAN + dokumen di folder Drive (`client_docs.py`); PDF hasil scan dibaca OCR (`tesseract`, bahasa ind+eng).
- **`site-finish`**: logo (+favicon, lihat "Favicon") & foto klien ke Media Library, galeri `[gallery]` di halaman Galeri, tagline (slogan form / AI), warna tema (Additional CSS dari "WARNA TEMA WEB"), tombol WhatsApp velocity-addons (dari "Kontak utk di web"), peta Google Maps di Hubungi Kami. Tidak menimpa pengaturan yang sudah diubah orang.
- **Foto dari dokumen Word/PowerPoint klien** (`site-finish` `foto_dokumen()`, permintaan user 2026-09-24): banyak klien menempel foto proyek di dalam materi `.docx`/`.pptx`, bukan mengirim berkas gambar (cahayaratupetir.com: 36 foto hanya ada di "Materi Website Profil - Rev1.docx", sehingga banner/layanan jatuh ke foto bank dan Galeri kosong). Gambar `word/media`/`ppt/media` diekstrak ke `/var/lib/velocity/foto-dokumen/<domain>/` dan mengisi sisa kuota `MAX_PHOTOS` sesudah berkas gambar lepas: foto lanskap ≥900 px dulu (bahan banner), sisanya tersebar merata dari awal sampai akhir dokumen. Dibuang: sisi terpendek <400 px, gambar yang >55% putih (tabel, tangkapan teks, diagram), berciri logo, duplikat (md5), berkas di luar 20 KB–8 MB. Dokumen bernama/berfolder identitas atau legal (KTP, NPWP, akta, legalitas, izin, sertifikat, surat, invoice, bukti transfer, FORM ISIAN, biodata) tidak pernah diambil fotonya. Ambang foto klien di tampilan klasik (`theme-paket-biasa foto_klien`) diturunkan 500 → 400 px karena foto WhatsApp yang ditempel di Word umumnya ±470×600.
- **Kontak publik** (`velocity-child-theme data_klien()` / `biodata_publik()`, keputusan user 2026-09-24): "Kontak utk di web" & dokumen klien dulu; bila kosong, WA/telepon/email/alamat dari BIODATA PEMILIK di FORM ISIAN (nama pemilik tidak pernah) — kecuali klien menulis tidak mau biodatanya tampil (`TOLAK_BIODATA`: "jangan tampilkan no hp saya", "biodata tidak usah dicantumkan", "alamat rumah dirahasiakan"). Dipakai tampilan klasik, tema FSE (Data Situs), dan tombol WhatsApp `site-finish`. Dulu biodata tidak pernah tampil, sehingga form versi lama tanpa "Kontak utk di web" menghasilkan situs tanpa kontak (cahayaratupetir.com).
- **Permintaan klien di form** (`scripts/permintaan-form`, keputusan user 2026-09-24 "data2 di form itu adalah acuan pengerjaannya"): isi bagian PESAN TAMBAHAN (FORM 5, `client_form.pesan_tambahan()`) sudah dibaca AI sebagai bahan tulisan, tetapi instruksi kerjanya (buat halaman, ambil data/gambar dari situs lain, ganti logo, dsb.) tidak dieksekusi installer. Sesudah QA, runner menjalankan `permintaan-form <manifest>`; selama belum ditandai selesai (`scripts/permintaan-form <domain> --selesai "catatan"`, status di `/var/lib/velocity/installer/permintaan-form/<domain>.json`, md5 isi — isi berubah = belum lagi) situs dilaporkan 🟡 "perlu dicek" (`permintaan_form_klien`) dan pesan Telegram memuat isi permintaannya. Kasus asal: cahayaratupetir.com meminta halaman paket & hasil pekerjaan dari totalantipetir.com — dikerjakan dengan plugin `templates/plugins/velocity-paket` (CPT `paket` + Meta Box: harga, kelengkapan, kategori; shortcode `[velocity_paket]`) dan galeri berketerangan.
- **Agen permintaan klien** (`scripts/permintaan-claude` + `scripts/permintaan-claude-alat` + `scripts/permintaan-ambil`, prompt `templates/permintaan-claude/tugas.md`, permintaan user 2026-09-24): permintaan PESAN TAMBAHAN yang belum selesai dikerjakan Claude Code (Opus terbaru, antrean & kunci sama dengan agen desain). Urutan: bahan di `/var/lib/velocity/permintaan-claude/<domain>/` (permintaan, form tanpa baris sandi, `situs.json`, daftar materi Drive) → cadangan database di server (`~/velocity-cadangan/<domain>-permintaan-*.sql.gz`, 5 terakhir) → agen bekerja dengan alat satu-satunya: `wp`/`php` **sebagai user hosting situs (runuser), bukan root** — perintah merusak ditolak (hapus/impor DB, core/config, pengguna, ganti tema, siteurl/home, hapus plugin, search-replace tanpa `--dry-run`); `unggah` (gambar diperkecil ≤1600 px, JPEG 82); `plugin <slug>` dari `templates/plugins` (prasyarat "Requires Plugins" dipasang dulu); `mu-plugin` (dicabut lagi bila WordPress gagal termuat); `ambil <url>` (Playwright: teks berurutan + gambar diunduh dalam sesi browser, hanya alamat publik); `bahan` (materi Drive tanpa video/KTP/NPWP/akta/berkas akun; teks docx/pptx/pdf + foto di dalamnya); `potret` desktop/HP (situs maintenance lewat cookie admin sementara). Agen menulis `laporan.json` (butir: selesai / perlu_manusia / tidak_bisa + URL); installer memeriksa sendiri tiap URL (post terbit atau HTTP 200). Semua butir selesai → `permintaan-form --selesai` otomatis + baris 📝 di laporan ✅; ada sisa → tetap 🟡 "perlu dicek" dengan daftar butir & alasannya di Telegram. Sisa yang hanya `perlu_manusia` tidak dikerjakan ulang tiap run (`--paksa` untuk mengulang). Manual: `WP_INSTALL_SSH_KEY_FILE=/root/.ssh/id_ed25519 scripts/permintaan-claude <domain> [--coba] [--paksa] [--menit=N]` — situs yang sudah SUCCESS: COMPLETE hanya dengan persetujuan user. Uji di rig lokal (`/var/lib/velocity/tools/wp-uji`): `VELOCITY_ON_PROGRESS=<folder form uji>` + `VELOCITY_LOKAL_*` + `--tanpa-cadangan`; uji 2026-09-24 (3 paket totalantipetir.com + menu, tema FSE) selesai 3/3 dalam 2,5 menit, ±US$0,76.
- **Pengurai FORM ISIAN** (`scripts/client_form.py`, audit 2026-09-24 atas 2.882 form di Drive: 2.388 .doc, 482 .docx, 10 PDF, 1 .odt, 1 .xlsx): `fields` = "Label: isi" (`parse_fields`) + isian di bawah judul bagian template (`parse_sections`: NAMA DOMAIN, NAMA PERUSAHAAN ANDA / PERUSAHAAN/ INSTANSI / INSTANSI PENDIDIKAN, NAMA MEDIA, SLOGAN, KONTAK / INSTANSI · KONTAK MEDIA · KONTAK YG DITAMPILKAN → `Kontak untuk di web`, SUSUNAN & ISI MENU ATAS, DATA TAMBAHAN, LAYANAN / PRODUK, DESIGN/TEMPLATE YANG DIPILIH, website referensi, WARNA TEMA WEB). Isian judul hanya MENGISI label yang belum ada; nama FORM 1 template paket biasa lama (`Nama Perusahaan Anda`) hanya cadangan bila "Nama Perusahaan:" biodata kosong (diukur pada 94 proyek: bila keduanya terisi, biodata lebih sering tepat). Perbaikan lain: contoh template "Misal: warna dasar ... biru dan hijau" tidak lagi terbaca sebagai warna klien (form 2025+: 86 dari 1.056 form warnanya berubah, hampir semuanya kebocoran contoh ini — mis. "Hijau" dulu jadi biru+hijau); `<w:br/>` .docx = baris baru & entitas `&amp;` dikembalikan; "Email:" dengan alamat di baris berikut terbaca; label sampah .doc biner ("FKb") & daftar "Pilihan N" template dibuang; form PDF (pdftotext) & .odt kini terbaca. Dampak pada 94 proyek installer (`data_klien`): hanya nama cahayaratupetir.com ("Cahaya ratu petir") & hidmal.net ("Pondok Pesantren Hidayatul Muhajirin") berubah; judul situs manifest baru: 15 form 2025+ tidak lagi jatuh ke tebakan nama domain.
- **Form dibaca agen Claude Code** (`scripts/baca-form-claude`, prompt `templates/baca-form-claude/tugas.md`, keputusan user 2026-09-25): teks semua FORM ISIAN (tanpa sisa biner .doc & baris sandi) dikirim ke `claude -p` (Opus terbaru, `--tools ''`, `--json-schema`) yang memisahkan isian klien dari teks template dan mengisi skema tetap: nama usaha, slogan, kontak web (WA/telepon/email/alamat/maps/sosmed), biodata, tolak biodata tampil, menu, desain dipilih, referensi desain vs referensi ISI, warna, rubrik portal, data toko, layanan, pesan tambahan, `catatan` (hal ragu/bertentangan). Hasil `/var/lib/velocity/form-claude/<folder>.json` berlaku selama md5 berkas form sama. Dipanggil saat manifest dibuat (`generate_manifest`, judul situs sudah dari hasil agen; autopilot menunggu s.d. 480 dtk) dan di awal installer-runner (simpul bagan "Baca form klien"). `client_form.read_client_form` memakai hasil ini (`sumber: claude`, `data`) dengan label field lama (`fields_dari_claude`, nomor dirapikan tanpa spasi) + field pola yang tidak dikenal skema; tanpa hasil → pengurai pola (`sumber: pola`). `referensi_desain.referensi_form`, slogan `site-finish` & `permintaan-form` (tanda selesai md5 versi pola tetap diakui) memakai hasil agen. Saklar `BACA_FORM_CLAUDE=0` mematikan. Uji 2026-09-25 pada 96 proyek installer: semua terbaca, ±US$0,09 & 16 detik per form (total US$9); dibanding pola: nama 21 berubah (mis. "Apotekmedikaindofarma" → "Apotek Medika Indofarma", "Sinar Globalindo" → "PT SINAR PANCA KAWAT"), referensi desain 6 (apotekmedikaindofarma → plotterpolaindonesia.com, ruangaksaralearn → cakram.id), WA 6 (bimbelppkgardamedika kini nomor "Kontak utk di web" yang memang disetujui), warna 7 portal berita yang dulu terlewat.
- **Hemat media** (`templates/mu-plugins/velocity-hemat-media.php`): tanpa ukuran turunan 1536/2048 px, foto asli maks 1600 px, JPEG 80. Dipasang manual di cahayaratupetir.com (paket hosting 150 MB penuh: inti WordPress ±100 MB, satu foto artikel Pexels 10,6 MB); belum dipasang otomatis oleh installer.
- **Pemeriksaan beranda adaptor AI** (`adaptor_tema.periksa_beranda`): beranda yang TIDAK BISA dibuka (SSL belum terbit, jaringan, masih halaman maintenance) = `adaptor_ai_tidak_bisa_diperiksa`, hasil tetap terpasang. Dulu dianggap gagal lalu isi beranda dicabut (cahayaratupetir.com 2026-09-22 selesai sebagai halaman teks polos) dan adaptor tema ikut dicap gagal. Verifikasi sertifikat dimatikan di pemeriksaan ini — yang diperiksa isi halaman.
- **`site-ssl`** (permintaan user 2026-09-23): sampai saat itu installer hanya MEMBACA status sertifikat (`ssl_cert:mismatch` di dry-run, `ssl_tidak_valid` di QA) dan tidak pernah memintanya, jadi situs selesai tanpa HTTPS sampai ada yang memasangnya manual di panel (swan-jaya.com, winskokoa.com, advokatsugriwossmgroup.com, pemdeslampok.com: sertifikatnya baru terbit berjam-jam sesudah run). Sekarang sesudah cek HTTP — sebelum tema, konten, screenshot & QA — satu koneksi SSH: (1) A record domain & `www` diresolve DI SINI lewat resolver publik (1.1.1.1/8.8.8.8, jatuh ke resolver sistem bila gagal) lalu dicocokkan dengan SEMUA IP server tujuan, karena domain klien sering diarahkan ke IP alias (103.103.175.183/184), bukan `target_host`; (2) sertifikat yang masih berlaku >30 hari dan memuat nama domainnya dibiarkan; (3) `letsencrypt.sh request <domain>` DirectAdmin (sekali lagi dengan `<domain>,www.<domain>` bila SAN-nya belum memuat apex); (4) berkas `.cert` dibaca ulang — keluaran skrip tidak dipercaya; (5) sertifikat diperiksa lagi dari luar lewat koneksi TLS. Tidak pernah menggagalkan instalasi. DNS belum mengarah = `dilewati:dns_belum_mengarah` (tidak menghabiskan rate limit Let's Encrypt), run berikutnya mencoba lagi; staging `docroot=`/`site_url=` dilewati. Opsi: `--paksa` (minta baru walau masih berlaku), `--coba` (periksa saja). Log: `ssl: terbit|sudah_ada|dilewati:<alasan>|gagal:<alasan>` + `ssl: publik:<hasil cek dari luar>`.
- **`site-qa`**: SSL valid untuk domain, gambar tidak 404, tanpa teks placeholder, menu Tentang Kami/Hubungi Kami ada, artikel tidak di Uncategorized.

Mode `finish` (`POST /api/installer/run` `{"domain":..., "mode":"finish"}`) menjalankan ulang konten + finishing + QA untuk situs yang sudah terpasang, tanpa install ulang dan tanpa notifikasi.

**Backup:** instalasi tidak membackup `public_html` yang masih kosong (isi bawaan DirectAdmin) atau WordPress hasil installer sendiri (apply ulang). Backup `/home/<user>/backup/pre-install-*.tar.gz` hanya dibuat kalau `public_html` berisi situs lain (bukan bawaan DirectAdmin, dan `wp-config.php` tidak memakai DB_NAME manifest). Backup lama dari instalasi sebelumnya tidak dihapus otomatis oleh installer.

Mode `maintenance` (`{"domain":..., "mode":"maintenance"}`) hanya menyalakan maintenance mode velocity-addons untuk situs yang terpasang sebelum langkah itu ada (sekali per situs, dilewati kalau sudah diatur manual).

Mode `child-theme` (`{"domain":..., "mode":"child-theme"}`) memasang/memperbarui child theme situs yang sudah terpasang; untuk Paket G menjalankan seluruh [alur Paket G](#alur-paket-g-baku).

**SSL belum otomatis.** Kalau QA melaporkan `ssl_tidak_valid` (domain baru menyajikan sertifikat domain lain), terbitkan di server DirectAdmin tujuan:

```bash
/usr/local/directadmin/scripts/letsencrypt.sh request domain.com,www.domain.com
```

(`www` hanya kalau mengarah ke IP yang sama.) Dry-run mencatat `ssl_cert` (match/mismatch/none), `le_script`, dan `da_ssl` untuk mengecek kesiapan.

Paket sistem di server installer: `poppler-utils`, `tesseract`, `tesseract-langpack-ind`, `tesseract-langpack-eng`.

## Child theme (`scripts/velocity-child-theme`)

Saat apply, installer membaca referensi desain pilihan klien di FORM ISIAN (label "Template yang dipilih" / "DESIGN YANG DIPILIH", mis. `https://beritab2.velocitydeveloper.com/`) lalu mencocokkannya dengan daftar tema `GET https://api.velocitydeveloper.co/api/v1/themes` (header `signature: md5(dmY)`, tanggal WIB). Referensi `beritab2` cocok dengan child theme ber-slug `velocity-beritab2` atau bernama "Velocity Berita B2".

- Cocok → zip diunduh ke `/var/lib/velocity/packages/child-themes/<slug>-<versi>.zip`, dikirim ke server, dipasang, dan diaktifkan sebelum 1-Click Setup (lokasi menu disimpan per tema aktif).
- Tidak cocok / API gagal → tema induk tetap dipakai; child theme yang sudah aktif di situs tidak dimatikan saat apply ulang.
- Override manual: tambahkan `velocity_child_theme=<slug>` di manifest. Override selalu menang, termasuk atas pembuatan otomatis di bawah.
- Log: `child_theme:<status>:<referensi>:<slug>` dan `active_theme:<tema>`; laporan Telegram "Instalasi selesai" memuat baris Tema.

### Paket E: child theme baku `velocity-pakete`

Keputusan user 2026-09-16: **kalau `paket=Paket E`, child theme-nya sudah pasti `velocity-pakete`** — form kliennya tidak perlu memuat referensi desain, dan referensi yang kebetulan ada di form diabaikan.

- Urutannya sama dengan paket lain yang bertema induk: paket dicek → `velocity-child-theme` mengambil `velocity-pakete` dari API tema (`type: wp_theme_child`, versi ikut API) → zip dikirim & diaktifkan di `website-install-from-manifest` **sebelum 1-Click Setup** → **baru konten AI** (`ai-content-generator.py`) menulis halaman & artikel di atas tema itu.
- Log: `child_theme:matched:paket-e:velocity-pakete`. Bagan proses halaman installer punya cabang sendiri "Child theme Paket E".
- Override manual `velocity_child_theme=<slug>` di manifest tetap menang.
- Situs Paket E yang sudah terpasang: `INSTALL_MODE=child-theme scripts/installer-runner <domain>` (tanpa install ulang, tanpa notifikasi).
- Kalau unduhan zip gagal tapi versi lama tema yang sama masih ada di `/var/lib/velocity/packages/child-themes/`, zip tembolok itu dipakai (`error=unduhan_gagal_pakai_tembolok:…`) — kalau tidak ada, status `download_failed` dan situs tetap di tema induk `velocity`.

> **Belum bisa diunduh otomatis (16 Sep 2026):** API tema mencantumkan `velocity-pakete` 2.1.0 dengan `package_external_url` ke rilis GitHub `VelocityDeveloper/velocity-pakete`, tetapi repo/rilis itu **privat** — unduhan anonim dari server installer menjawab 404 (bandingkan `velocity-beritab1`, yang publik dan berhasil). Perbaikannya salah satu: rilis GitHub dibuat publik, zip-nya diunggah ke storage API (`package_file_url`, seperti `velocity-sekolah`), atau server installer diberi token GitHub (butuh jalur unduhan lewat API aset GitHub — belum dibuat).

### Paket G: child theme dibuat otomatis bernama project (TIDAK DIPAKAI LAGI)

> **Sejak 2026-09-15 paket custom (Paket G & Portal Berita Custom) hanya FSE** — keputusan user "kedepan pakai FSE saja". Installer tidak lagi merender child theme ataupun memasang tema induk `velocity` untuk paket ini (log `child_theme:skipped_fse::`, `tema_induk_dilewati:fse`); lihat [Tema FSE](#tema-fse-untuk-desain-custom-scriptsfse-apply-templatestema-fse). Bagian ini tinggal sebagai catatan situs lama yang child theme klasiknya masih aktif (jasakontraktorindo.com) — installer melewatinya sampai manifest diberi `tema_desain=fse` (ptmitraajegselaras.com dipindah ke velocity-fse 2026-09-17). Pencocokan child theme dari API di atas tetap berlaku untuk paket lain.

Paket G tidak memilih template — desainnya custom per project, jadi form klien tidak pernah memuat referensi dan dulu situsnya berhenti di tema induk. Sekarang installer membuat child theme kosong sendiri (`paket=Paket G` di manifest memicunya; dibaca dari CRM saat manifest dibuat).

- Slug & folder: `velocity-<label domain>` (jasakontraktorindo.com → `velocity-jasakontraktorindo`), Theme Name "Velocity Jasakontraktorindo", `Template: velocity`.
- Isinya **kerangka desain lengkap**, bukan child theme kosong — dirender dari `templates/child-theme-paket-g/` (lihat bagian berikutnya).
- Zip disimpan di `/var/lib/velocity/packages/child-themes/<slug>-<versi>.zip` (isinya deterministik, jadi generate ulang tidak mengubah apa pun).
- **Tidak pernah ditimpa utuh, tapi diperbarui per berkas.** `install_from_zip` menghapus folder tujuan, jadi installer hanya mengaktifkan tema yang sudah ada (`child_theme_kept:<slug>`). Pembaruannya lewat `child-theme-apply --perbarui`: setiap tema membawa `.velocity-render.json` (sidik berkas hasil render); berkas yang masih sama dengan catatan diganti versi baru, berkas yang disunting orang dipertahankan, dan gabungan PHP-nya diuji (`php -l` + `cek-fungsi-tema`) — gagal berarti pembaruan ditahan (`child_theme_update_ditahan`). Awalan dibaca dari tema terpasang. Tema lama tanpa catatan: `inc/theme-data.php` dianggap milik situs.
- Zip selalu dirender ulang (tidak dari cache), sehingga perbaikan template & data compro terbaru selalu ikut.
- Status `generated` di log; laporan Telegram menulis `Tema: <slug> (child theme baru, desain custom)`.
- Kalau form Paket G ternyata memuat referensi desain yang ada di API, yang dari API tetap dipakai; scaffold hanya dibuat saat tidak ada yang cocok (termasuk saat API tema mati).
- Penopang kalau manifest tidak punya `paket=` (CRM tidak terbaca saat manifest dibuat): paket dibaca dari nama file form di folder klien (`FORM ISIAN WEBSITE - paket g.doc`). Hanya dipakai saat `paket=` kosong. Diperiksa 2026-09-12 atas 22 folder antrean — 5 file bernama "paket g" (4 memang Paket G di CRM, 1 paketnya kosong), tidak ada paket E/F/Portal/Toko yang filenya bernama begitu, dan penopang ini hanya menambah 1 domain (5 → 6).

Situs Paket G yang sudah terpasang sebelum aturan ini ada tidak perlu install ulang: mode `child-theme` memasangnya saja.

```bash
curl -X POST http://127.0.0.1:9121/api/installer/run -d '{"domain":"jasakontraktorindo.com","mode":"child-theme"}'
# atau langsung di server installer:
INSTALL_MODE=child-theme WP_INSTALL_SSH_KEY_FILE=/root/.ssh/id_ed25519 \
  scripts/installer-runner jasakontraktorindo.com
```

Untuk paket lain mode ini hanya memasang + mengaktifkan child theme (`scripts/child-theme-apply`). Untuk Paket G menjalankan [alur Paket G](#alur-paket-g-baku). Keduanya tanpa install ulang, tanpa konten AI, tanpa notifikasi, dan tanpa mengubah status instalasi di `<domain>.json`.

## Palet warna tema FSE (`scripts/cek-palet-fse`)

Palet ditulis `fse-apply --tema` dari warna klien (`hitung_palet`). Ada dua bentuk: **biasa** (latar terang `#f7f8fa`, `putih` = `#ffffff`) dan **gelap** (seluruh halaman gelap, `latar #16191e`, `putih` dipakai ulang sebagai latar halaman `#0d0f12`) — yang gelap **hanya** untuk gaya `dealer`.

Dua jebakan yang sudah diperbaiki 2026-09-16 (bumiairchemitech.com):

- **Parameter `gelap` tertimpa variabel warna bernama sama** di dalam `hitung_palet()`, sehingga `if gelap:` selalu benar dan **semua** situs FSE berlatar hitam. Variabelnya kini `utama_gelap`. Penjaganya `scripts/cek-palet-fse` (dijalankan `deploy.sh`) memeriksa **nilai** palet: situs biasa harus `putih = #ffffff` dan latar vs judul ≥ 7:1, palet dealer harus gelap, dan teks di atas warna utama/aksen ≥ 4.5:1.
- **Teks kusam di tombol berwarna** — `perbaiki_kontras()` memakai opsi pertama yang lolos 4.5:1, jadi untuk hijau `#009A4B` teks yang dipilih hitam (4.68:1): sah menurut WCAG, tapi tombolnya terlihat kusam. Aturan **versi 2** (`permukaan_terang()`, keputusan user 2026-09-16): kalau teks gelap lolos dengan kontras < 6 dan warnanya bisa digelapkan sedikit sampai teks putih lolos, warna itu digelapkan dan teksnya jadi putih. Warna yang memang nyaman dengan teks gelap (amber `#fca311` 8.49, oranye `#ff7f00` 6.78) tidak tersentuh — diukur atas 22 situs paket custom, hanya 1 yang berubah.

  Aturan ini **hanya berlaku untuk build berikutnya**: manifest baru ditulis dengan `velocity_palet_versi=2` (`generate_manifest`), sedangkan manifest situs yang sudah jadi tidak punya baris itu dan tetap memakai aturan versi 1, sehingga tampilannya tidak berubah walau di-`finish` ulang. Situs lama yang ingin ikut aturan baru: tambahkan sendiri `velocity_palet_versi=2` ke manifest-nya.

  Angka yang sama dipakai sebagai **versi aturan tampilan**: `fse-apply --tema` menulisnya ke `velocity_fse_desain.tampilan_versi`, dan `functions.php` menambahkan kelas body `vf-tampilan-2`. Aturan CSS baru dipasang di balik kelas itu — situs versi 1 tetap memakai tampilan lamanya meski temanya diperbarui.

  Yang sudah memakai jalur ini: **tampilan statistik pengunjung di footer** (permintaan user 2026-09-16). Shortcode-nya tetap `[velocity-statistics style="list"]`, tetapi tampilannya kini mengikuti token desain referensi klien: angka memakai font judul + `font-variant-numeric: tabular-nums`, garis pemisah & baris selang-seling dari `currentColor` (kelas Bootstrap `border-bottom` milik plugin tidak pernah aktif di tema blok), sudut mengikuti `--vf-kartu-radius`, dan warna angka mengikuti footer terang/gelap (`aksen-teks` / `aksen-di-primary`) supaya tetap 4.5:1.
- **Teks di atas foto tidak boleh memakai token `putih`**, karena di palet gelap token itu berarti latar halaman — judul hero pernah tampil hitam di atas foto gelap. Pakai `di-primary` (selalu `#ffffff`): berlaku untuk `.vf-hero-foto`, `.vf-ajakan-foto`, dan `.vf-pita-foto`.

## Tema FSE untuk desain custom (`scripts/fse-apply`, `templates/tema-fse/`)

Keputusan user 2026-09-14: **FSE dulu, tidak pakai child theme.** Child theme klasik dinilai kurang efektif karena isi dinamis terkunci di PHP. Paket G & Portal Berita Custom kini memakai block theme generik `velocity-fse` — kerangka sama untuk semua klien, isi khas klien di database sehingga PM bisa menyunting dari wp-admin:

| Isi | Rumah | Disunting di |
|---|---|---|
| nama, slogan, tentang, kontak publik, rubrik/layanan | opsi `velocity_situs` | Tampilan → Data Situs |
| palet warna klien (penjaga kontras WCAG sama dengan child Paket G) | `wp_global_styles` | Site Editor → Gaya |
| Beranda (Query Loop per rubrik / seksi perusahaan), Redaksi, Layanan, Produk, Pemesanan, Hubungi Kami | post_content berupa blok | editor halaman |
| menu utama | `wp_navigation` (header/footer tanpa `ref` memakai yang terbaru) | Site Editor → Navigasi |
| header, footer, kolom samping, template | `parts/`, `templates/` | Site Editor |

Blok dinamis tema: `velocity/topbar` (tanggal/slogan), `velocity/populer`, `velocity/kontak`, `velocity/form-kirim` (form → email + menu Pesan Masuk, captcha velocity-addons), `velocity/hak-cipta`, `velocity/judul-arsip`.

Formulir situs = **Contact Form 7** (sejak 2026-09-19, supaya kolom bisa ditambah/diubah/dihapus sendiri): `fse-apply --isi` memasang & mengaktifkan plugin, tema (`inc/cf7.php`) membuat satu form bawaan dari kolom form lama (opsi `velocity_fse_cf7_form`), lalu halaman diisi blok `contact-form-7/contact-form-selector`. Captcha tetap velocity-addons lewat tag `[velocity_captcha]` — plugin itu hanya menampilkannya, pemeriksaannya ada di `inc/cf7.php` (filter `wpcf7_validate`). Kiriman tetap diarsipkan ke Pesan Masuk. Bila CF7 gagal dipasang, blok lama `velocity/form-kirim` yang dipakai (dan blok itu menampilkan form CF7 bila ada).

**Jalur tema** (`fse-apply --deteksi`, dipanggil `installer-runner`): `fse` untuk situs baru, manifest `tema_desain=fse`, atau velocity-fse sudah aktif; `lewati` untuk block theme buatan tangan dan untuk situs lama yang child theme klasik Paket G-nya masih aktif (`child_klasik_belum_dipindah`, tidak dimigrasi otomatis karena desain compro & foto per slot belum ada di velocity-fse). Jalur `child` (`tema_desain=child`, `velocity_child_theme=`) dihapus 2026-09-15. Memindahkan situs lama = tulis `tema_desain=fse` lalu jalankan mode `finish` atau `child-theme`; uji dulu dengan `fse-apply --tema/--isi <manifest> --coba`.

Installer (`website-install-from-manifest`) tidak memasang tema induk `velocity` maupun child theme untuk paket custom; WordPress baru memakai tema bawaan sampai `fse-apply --tema` mengaktifkan velocity-fse (laporan Telegram membaca baris `fse: tema_siap:`), lalu `site-finish --cleanup` menghapus tema twenty* yang tidak aktif.

- `fse-apply --tema` (di `paket_g_tema`, sebelum konten AI): validasi template (`scripts/cek-blok` + `php -l`), pasang zip bila versi `style.css` template lebih baru, aktifkan (logo → opsi `site_logo`, tema lama dicatat di `velocity_fse_tema_sebelumnya` untuk rollback), tulis data situs, palet, rubrik → kategori.
- `fse-apply --isi` (di `paket_g_isi`, sesudah `site-finish`): susun halaman & menu, validasi markup dengan parser editor WordPress sebelum ditulis (rencana di `/var/lib/velocity/fse-rencana/<domain>/`), buang shortcode child lama yang tercetak mentah, lalu cek HTTP tiap halaman. Portal berita lanjut `paket-g-foto` (foto utama artikel), semua lanjut `paket-g-cek-visual`.
- **Tidak menimpa kerja orang**: halaman ber-`_velocity_fse_md5`, opsi `velocity_situs_md5`, palet `velocity_fse_warna_md5`, menu ber-md5 — ditimpa hanya kalau masih persis tulisan installer. Generator AI melewati halaman FSE (`page_kept_fse`), Beranda (`_velocity_fse_layout`) tidak pernah.
- `--coba` menyusun & memvalidasi tanpa menulis ke situs.
- Validator blok butuh modul node di `/var/lib/velocity/tools/blockval` (`@wordpress/blocks`, `@wordpress/block-library`, `global-jsdom`); tanpa itu validasi dilewati dengan catatan `cek_blok_dilewati`.
- Menyempurnakan desain semua situs FSE = sunting `templates/tema-fse/` dan naikkan `Version` di `style.css`.

**Desain mengikuti referensi klien** (permintaan user 2026-09-14: "pastikan desain yang dibuat sama dengan referensi yang diminta"). Dulu installer mengabaikan isian "website yang ingin dicontoh" — hanya referensi yang cocok dengan API tema Velocity yang dipakai. Sekarang `fse-apply`:
- membaca URL + catatan klien dari FORM ISIAN (`referensi_form`; contoh isian template & tautan Velocity diabaikan),
- membaca ciri HTML halaman referensi (kolom samping, kartu selebar layar, grid dua kolom, font Google) dan meminta AI memilih gaya beranda terdekat dari katalog `GAYA` (cadangan: heuristik); manifest `gaya_beranda=klasik|sorotan` selalu menang,
- **font teks diambil dari font yang paling banyak terlihat**, bukan dari default `<body>` (perbaikan 2026-09-16). erhaeschemical.com memakai Inter hanya di strip topbar — 1 elemen, 0,4% luas teks — sementara 60 elemen lain memakai Poppins, sehingga bumiairchemitech.com sempat berteks Inter dan tidak mirip referensinya. Pengukur kini menimbang luas piksel tiap font (font ikon diabaikan) dan memakai `<body>` hanya sebagai cadangan. Situs yang sudah terukur tidak berubah: hasil pengukuran ditembolok per URL + `VERSI` di `referensi_desain.py`, dan `VERSI` sengaja tidak dinaikkan supaya aturan baru hanya berlaku untuk build berikutnya,
- menyimpan hasilnya di `/var/lib/velocity/fse-rencana/<domain>/referensi.json` (tidak diulang tiap run) dan menulis `gaya`, `referensi`, `font_teks`, `font_judul` ke opsi `velocity_situs`,
- `paket-g-cek-visual` ikut memotret halaman referensi (`referensi-beranda-*.png`) di folder yang sama dengan hasil — **bandingkan keduanya sebelum melapor selesai**.

Gaya yang ada: `klasik` (portal padat + kolom samping) dan `sorotan` (majalah foto: pita judul berikon, kartu foto selebar layar berjudul serif, grid 2 kolom per rubrik, header putih, pita kaki hitam — dari referensi anaksegalabangsa.com, ourgrandfatherstory.com). Font referensi dipakai kalau dibawa tema (`FONT_LOKAL`: Plus Jakarta Sans, Montserrat, PT Serif). Referensi yang tata letaknya tidak cocok dengan gaya mana pun perlu gaya baru di `templates/tema-fse/style.css` + builder di `fse-apply`.

**Email & ikon media sosial wajib** (aturan user 2026-09-14, semua build): footer (`parts/footer.html`) dan halaman Hubungi Kami memuat blok `velocity/kontak` (email publik klien sebagai mailto) dan `core/social-links` ikon saja — Facebook, Instagram, X, YouTube, TikTok dengan tautan bawaan ke beranda platform (PM menggantinya dengan akun klien). Email biodata pemilik tidak pernah ditampilkan otomatis; kalau klien tidak memberi email publik, tanyakan dulu ke user.

Belum ada di jalur FSE (masih milik child Paket G): susunan beranda mengikuti urutan halaman company profile (`inc/compro.php`) dan foto contoh per slot desain perusahaan (`paket-g-foto` hanya dipakai untuk foto utama artikel).

### Referensi versi 5: struktur, bukan hanya gaya (2026-09-17)

Pelajaran jasakontraktorindo.com (referensi kontraktorhijau.com) — hasil manual yang mirip datang dari meniru **struktur** referensi:

- **Deteksi referensi**: `referensi_form()` menerima domain polos (`kontraktorhijau.com`) dan kalimat "contoh/seperti/samakan X" di kolom lain (bukan "materi/isi samakan X"). Dampak di 61 proyek (2026-09-17): 12 → 22 terdeteksi.
- **Pengukur** (`referensi-desain.js`): pohon menu + submenu, font menu, detail kartu (border, padding, jarak, kartu tengah disorot, tombol per kartu, keterangan foto), bar di dasar hero, kotak berlatar, header melayang, dan **lebar wadah di layar 1366 & 1920** (tetap px vs persen). Header/footer/elemen fixed tidak dihitung saat memecah seksi; gulir pelan untuk foto lazy-load.
- **Klasifikasi** (`referensi_desain.py`): baris judul page builder digabung dengan baris isinya (`gabung_kepala`); jenis baru `paket`; "tahapan", "kepuasan klien", "bukti kualitas" dikenali; deret foto berketerangan = galeri; pita gelap foto|teks = ajakan terbelah. Rencana memuat `menu`, `wadah`/`wadah_px`/`wadah_maks`, `halaman.layanan_detail`, `halaman.faq`.
- **Pustaka komponen** (`fse-apply` + `templates/tema-fse/inc/referensi-komponen.php` + `assets/css/referensi-komponen.css`, aktif hanya untuk rencana v5 lewat `body.vf-ref-v5`): header melayang, bar konsultasi hero, judul seksi bertombol, kartu ikon bertombol, tentang dalam kotak, galeri berketerangan, keunggulan s.d. 8, **pilihan layanan pengganti paket harga (tanpa angka)**, tahapan akordeon (+foto), seksi form, ajakan terbelah, grid kolom tetap (`vf-kolom-N`).
- **Menu & halaman dari menu referensi** (`menu_referensi`, `halaman_menu_referensi`): submenu layanan → halaman anak `/layanan/<slug>/` per layanan klien, submenu blog → kategori, FAQ disusun dari fakta klien (layanan, area, alur, kontak). Tidak aktif untuk portal berita, dealer, toko, atau manifest bermenu manual (`label_menu=` / `tanpa_halaman=`).
- **Warna**: kolom "WARNA TEMA" yang meminta beda dari web contoh → warna referensi tidak dipakai.

**Rig uji lokal** (`/var/lib/velocity/tools/wp-uji/`, lihat README.txt di sana): WordPress + SQLite + WP-CLI dilayani `php -S 127.0.0.1:8099 -t situs router.php`; `fse-apply` diarahkan ke sana dengan `VELOCITY_LOKAL_SSH`/`VELOCITY_LOKAL_DOCROOT`, rencana ke folder uji dengan `VELOCITY_FSE_RENCANA`, dan isi contoh dengan `VELOCITY_AI_GENERATED`. Situs klien tidak tersentuh.

**Cek visual** (`paket-g-cek-visual` + `potret-halaman` + `banding-potret`): semua halaman dipotret Playwright (gulir pelan), halaman diambil dari menu situs, HP diperiksa (scroll horizontal, tombol menu HP ada & membuka menu, gambar rusak), dan referensi dipotret desktop + HP lalu digabung berdampingan (`banding-beranda-*.png`). `notify-telegram.py` mengirim album perbandingan itu (maks 6 desktop + 4 HP) bersama laporan SUCCESS/CHECK.

## Alur Paket G baku

Disepakati user 2026-09-13 dari uji ptmitraajegselaras.com ("project paket G nanti seperti itu alurnya"). Di `installer-runner` terbagi dua fungsi: `paket_g_tema` (langkah 1–3, sebelum konten AI) dan `paket_g_isi` (langkah 4–7, sesudah `site-finish`), dipakai mode `apply`, `finish`, dan `child-theme` (yang juga menjalankan generator artikel di antaranya). Berlaku untuk Paket G dan Paket Portal Berita Custom:

| # | Langkah | Hasil |
|---|---|---|
| 1 | `compro-klien <domain>` | Company profile PDF → susunan bagian, prakata, warna, latar, logo, foto (`/var/lib/velocity/compro/<domain>/`). Tanpa PDF: dilewati |
| 2 | `paket-g-konten <manifest>` | Isi contoh dari form + dokumen; disesuaikan dengan compro (layanan tertulis, slogan, prakata, motto) |
| 3 | `fse-apply --tema <manifest>` | Pasang/aktifkan velocity-fse, data situs, palet, rubrik (sebelum konten AI) |
| 3a | `desain-claude --tahap=tema --paksa <manifest>` | **Tema FSE dikerjakan agen Claude** (keputusan user 2026-09-21; hanya bila `DESAIN_CLAUDE=1`, referensi terbaca, bukan portal berita, tanpa `gaya_beranda` manual): di atas dasar langkah 3, Claude Code menyusun header, footer & `gaya.css` dari referensi, audit header+footer+gaya sendiri (skor turun → tiga berkas itu dicabut). Halaman belum ada, jadi `pasang` tidak menyentuh halaman. Log berawalan `desain_claude_tema:`; catatan desain di `fse-rencana/<domain>/claude/kerja/rencana.md` dilanjutkan tahap halaman (`desain-claude --paksa` sesudah foto artikel). Gerbang 3b & audit 7 dilewati. Batas bawaan 5 putaran / 45 menit |
| 3b | `fse-cek-referensi <manifest>` | **Gerbang sebelum konten AI** (keputusan user 2026-09-16): bandingkan hasil langkah tema dengan rencana referensi. Belum sesuai → ulangi langkah 3 (maks `FSE_CEK_MAKS`, bawaan 3), sesuai → lanjut |
| 4 | `fse-apply --isi <manifest>` | Halaman berupa blok + menu `wp_navigation` (harus sesudah `site-finish`) |
| 5 | `paket-g-foto <manifest>` | Hanya portal berita: foto utama artikel |
| 6 | `paket-g-cek-visual <manifest>` | Screenshot desktop & HP ke `/var/lib/velocity/visual/<domain>/<waktu>/` + cek HTTP/layar kosong; `site-audit` membaca temuannya |
| 7 | `fse-audit-kemiripan <manifest>` | **Audit kemiripan tampilan** (permintaan user 2026-09-17): situs jadi diukur dengan pengukur referensi, dinilai per bagian & per seksi. Belum mirip → `fse-apply --tema` (+ gerbang 3b) dan `fse-apply --isi` digenerate ulang lalu diaudit lagi (`audit_kemiripan`, maks `FSE_MIRIP_MAKS`, bawaan 3 generate; berhenti lebih awal kalau skor header+footer+beranda tidak naik). Masih belum mirip → laporan Telegram "perlu dicek" memuat catatan `desain_belum_mirip_referensi:<bagian>` **dan daftar yang perlu diperbaiki** (per cek & per seksi: nilai situs → nilai referensi, skor, folder screenshot); pratinjau: `notify-telegram.py --perbaikan <domain>` |

**Gerbang tema vs referensi** (`scripts/fse-cek-referensi`, langkah 3b): membaca situs lewat WP-CLI lalu membandingkan dengan `fse-rencana/<domain>/desain-referensi.json` — tema aktif & versinya (harus = versi template repo), gaya beranda, font teks & judul, token header/footer (gelap, posisi logo & menu), radius tombol & kartu, serta palet (`primary`, `aksen`, `di-primary`, `di-aksen`, `putih`). Kode keluar 0 = sesuai atau tidak ada referensi, 1 = belum sesuai, 2 = tidak bisa diperiksa. `installer-runner` mengulang `fse-apply --tema` selama hasilnya 1, maksimal `FSE_CEK_MAKS` percobaan, lalu tetap lanjut ke konten AI dengan catatan `fse_cek: masih belum sesuai setelah N percobaan` — pemeriksaan ini tidak pernah menggagalkan instalasi. Log: `fse_cek: sesuai|belum_sesuai:<daftar beda>|tidak_ada_referensi|gagal:<alasan>`.

**Desain kiriman klien didahulukan** (centralimpex.com 2026-09-17: form tanpa website contoh, tetapi klien mengirim folder `desain/` berisi ekspor HTML 8 halaman). `referensi_form()` kini memanggil `desain_lokal()` lebih dulu: folder bernama desain/design/mockup/template/tampilan/layout (≤3 tingkat) berisi `index.html`, atau zip bernama serupa (diekstrak ke `fse-rencana/<domain>/desain-klien/`, tanpa jalur keluar folder) → URL `file://` yang diukur pengukur yang sama; halaman dalam dikenali dari nama berkasnya. Rencana mencatat `sumber_referensi: desain_klien`. Saat diperkenalkan hanya 1 dari ±3.000 folder proyek yang terkena. `cari_logo.py` juga memakai logo di folder desain bila nama berkasnya memuat nama domain klien (`central-impex-logo.png`); logo situs contoh perusahaan lain tetap diabaikan.

Pengenal seksi (`jenis_seksi`) membaca juga nama kelas seksi (`inquiry-cta`, `intro-section`, `markets-section`) dan teks label kecil di atas judul ("PRODUCT SCOPE", "WHY WORK WITH US"); jenis baru `pasar` (jangkauan pasar/negara tujuan — tanpa data klien dilewati `fse-apply` dan dicatat di `beranda-dilewati.json`). Latar bergradien (`background-image: linear-gradient`) dibaca warnanya, dan perataan banner diukur dari posisi teks judul, bukan kotak `<h1>`.

Token tema VERSI 4 (velocity-fse 1.10.13): `tanpa_cari` (kotak cari header & topbar disembunyikan), `footer_logo` (logo situs menggantikan nama di kolom pertama footer, berlatar putih di footer gelap), `footer_bawah_rata` (`vf-hak-cipta-terbelah|tengah`), `footer_judul_kapital`, `banner_latar|rata|tinggi|remah` (banner judul halaman dalam: gelap/aksen/foto dari slot hero/terang, rata, tinggi, breadcrumb). Beranda referensi berlabel memberi label kecil (teks milik situs) dan judul seksi rata kiri (`vf-rata-kiri`) bila referensinya begitu.

**Pembacaan referensi yang diperdalam** (permintaan user 2026-09-17, `referensi_desain.py` `VERSI = 4` + `referensi-desain.js`). Rencana `desain-referensi.json` kini memuat:
- `header`: terang/gelap, posisi logo & menu, satu/dua baris, tinggi, tinggi logo, ukuran/ketebalan/warna menu (`menu_berwarna`), kotak cari, dropdown, tombol ajakan (ikon keranjang & lencana tidak dihitung) + sudutnya, ikon keranjang, garis bawah, lengket, topbar (latar & isi: telepon/email/sosmed/alamat/jam);
- `footer`: latar, jumlah kolom (baris kolom yang mengisi ≥55% lebar footer; kolom bersarang tidak dihitung), isi tiap kolom (`kolom_isi`: logo/tentang/menu/kontak/sosmed/statistik/peta/form/galeri) & judulnya, baris hak cipta (`bawah_rata`, `bawah_beda_latar`, `pita` = latar sendiri selebar layar), judul kapital;
- `seksi[]` beranda: selain jenis/latar/kolom/rata, juga `label` (teks kecil di atas judul), `foto_posisi` (kiri/kanan pada seksi berdampingan; kolom yang dirata-tengah vertikal tetap terbaca berdampingan), `ruang` (rapat/sedang/lega), `kartu_bingkai`. Blok `core/cover` (foto + lapisan + isi yang saling menimpa) dibaca sebagai SATU seksi;
- `halaman{}`: halaman dalam referensi dari menunya (tentang/layanan/produk/galeri/kontak/artikel, satu per jenis) diukur dalam satu browser — `banner` judul (ada, latar foto/warna/terang, rata, breadcrumb, tinggi), susunan seksi, isi form/peta & apakah berdampingan.

Pengukur mencatat juga `kontras_rendah` (teks/tautan berkontras < 2,2 di header, footer, tiap seksi) — dipakai audit, bukan rencana. `referensi-desain.js` menerima banyak halaman sekaligus (`<url> <json> <png|-> ...`) dan `VELOCITY_UKUR_COOKIE` (cookie Playwright) untuk membaca situs yang sedang maintenance; admin bar disembunyikan.

**Audit kemiripan** (`scripts/fse-audit-kemiripan <manifest|domain> [--json] [--ambang=80]`, langkah 7). Beda dengan gerbang 3b yang hanya membaca opsi WordPress: audit ini membaca **tampilan** situs jadi (beranda + halaman yang padanannya ada di referensi) dengan pengukur yang sama, lalu memberi skor 0–100:
- `header` (ambang 80): latar, posisi logo & menu, baris, ajakan, topbar & isinya, lengket, huruf & warna menu, cari, keranjang, tinggi, logo, garis bawah, teks tak terbaca;
- `footer` (80): latar, jumlah kolom (±1, kolom Statistik wajib), isi & urutan kolom, baris hak cipta (rata, latar, pita), teks tak terbaca, **sama di semua halaman**;
- `beranda` (80): urutan jenis seksi (LCS; seksi yang `fse-apply` lewati karena klien tak punya datanya — `fse-rencana/<domain>/beranda-dilewati.json` — tidak dihitung), lalu per pasangan seksi: kelompok latar (terang/abu = terang, gelap/aksen = warna, foto), rata, kolom kartu, berdampingan & sisi foto, label, varian hero; teks tak terbaca. Seksi situs dikenali dari kelas `vf-ref-<jenis>`;
- `gaya` (80): font teks & judul, sudut tombol, judul kapital;
- `halaman_<jenis>` (70): halaman ada, banner (latar, rata, breadcrumb, tinggi), isi kontak & form|peta berdampingan, susunan, teks tak terbaca.

Yang sengaja tidak dihitung: warna (warna klien menang), kolom Statistik, email + sosmed di footer, isi teks/foto. Gaya beranda dari manifest (dealer/klinik/katalog) hanya dinilai header/footer/gaya. Situs maintenance dibaca sebagai admin: token sesi 15 menit dibuat & dihapus lewat WP-CLI, tidak pernah dicetak. Hasil: `fse-rencana/<domain>/audit-kemiripan.json` + `audit/situs-*.json|png` (bandingkan dengan `referensi-potret*.png`). Log: `kemiripan: header=.. footer=.. beranda=..`, `kemiripan: beda <bagian>.<cek>: situs=.. referensi=..`, `kemiripan: seksi <n>.<jenis> (<skor>): ...`, `kemiripan: sesuai|belum_mirip:<bagian>|tidak_ada_referensi|gagal:<alasan>`. Kode keluar 0/1/2 seperti gerbang 3b; tidak pernah menggagalkan instalasi.

Sejak 2026-09-15 langkah 3–4 hanya FSE. Langkah lama jalur child (`child-theme-apply --perbarui`, `paket-g-foto` per slot, `paket-g-setup`, `site-finish --widget`) tidak dipanggil lagi untuk paket custom.

Semua langkah boleh gagal tanpa menggagalkan instalasi (kecuali pemasangan tema di mode `child-theme`). Hasilnya tetap dilihat manusia/Claude lewat screenshot sebelum dilaporkan selesai — kesalahan tampilan tidak terlihat dari HTML. Audit terkait: `tema_belum_mengikuti_compro`, `tombol_whatsapp_tanpa_nomor`, `visual:<temuan>`.

## Portal Berita Custom = desain custom (varian berita)

Keputusan user 2026-09-14: "paket G = paket custom design, untuk portal berita custom juga sama dengan paket G". `Paket Portal Berita Custom` kini dikenali sebagai paket desain custom di `installer-runner`, `website-install-from-manifest`, `velocity-child-theme`, dan `site-audit`, dan menjalankan alur yang sama — tetapi hasilnya **portal berita**, bukan web company profile.

- **Isi** (`paket-g-konten`, `jenis=berita`): rubrik dibaca kode dari susunan menu FORM ISIAN (isian bernilai "berisi berita-berita …"); warna dari gambar contoh warna klien — kode hex hasil OCR, atau warna dominan gambar yang dipotret Chromium headless (server tanpa pengurai JPEG); AI hanya menulis nama tampil (huruf & urutan harus sama dengan nama di form), slogan, tentang, dan pedoman redaksi. Tidak mengarang nama awak redaksi, badan hukum, nomor verifikasi, atau jumlah pembaca.
- **Tema** (`inc/berita.php`, `single.php`, `archive.php`, `home.php`; body class `<prefix>--berita`): topbar tanggal + slogan, beranda berita utama + terbaru + blok per rubrik dengan kolom samping (terpopuler, rubrik, tentang), arsip & indeks berita, halaman artikel dengan berita terkait, `[<prefix>_redaksi]`, dan form "Kirim Pesan ke Redaksi". Situs non-berita tetap memakai single/archive/index tema induk.
- **Artikel** (`ai-content-generator.py`): kategori = rubrik tema; `articles_per_rubrik` (bawaan 3) artikel per rubrik bergaya **tulisan informatif, bukan laporan peristiwa** — tanpa kejadian, nama orang, kutipan, angka, atau tanggal karangan. Artikel tersimpan yang kategorinya tidak cocok dengan situs dibuat ulang; artikel contoh lama dihapus hanya bila belum pernah disunting.
- **Foto** (`paket-g-foto --artikel`): foto utama tiap artikel tanpa thumbnail dari **Pexels** (kunci `/home/pexel/api-key.txt`, env `VELOCITY_PEXELS_KEY_FILE`; kunci tidak pernah dicetak), cadangan Openverse (CC0/PDM) → Commons bila Pexels kosong, menolak (401/403/429), atau tak ada yang layak. Kata kunci per artikel dari AI dengan cadangan per rubrik; caption "Foto ilustrasi: <alt> — <fotografer>, Pexels". `--ganti-artikel` mencarikan ulang artikel yang masih memakai foto contoh bank foto lama / `sampul-*` installer (foto klien tidak disentuh) dan menghapus lampiran lama yang tak dipakai lagi — dipakai untuk rmbrentcar.com 2026-09-17.
- **Halaman & menu** (`paket-g-setup`): kategori rubrik (slug sama dengan theme-data), halaman Redaksi, blok kontak + form di Hubungi Kami, menu Home → rubrik → Redaksi → Kontak Kami.
- **Urutan**: di situs lama tanpa child theme, tema harus dipasang **sebelum** generator artikel (`paket_g_tema` → konten AI & `site-finish` → `paket_g_isi`); kalau terbalik, generator tidak melihat rubrik dan artikel tetap satu kategori "Blog".

## Kerangka desain Paket G (`templates/child-theme-paket-g/`)

Child theme Paket G lahir sudah berbentuk situs perusahaan, bukan folder kosong. Isi template dirender dengan mengganti placeholder `{{KUNCI}}`:

| Berkas | Isi |
|---|---|
| `header.php` | Header sendiri: logo, menu utama, tombol "Hubungi Kami" (langsung membuka WhatsApp, jadi nomornya tidak ditulis lagi di sebelahnya). Di HP jadi panel geser dengan tombol sendiri — **tanpa Bootstrap tema induk** |
| `footer.php` | Footer 4 kolom (identitas, layanan, halaman, kontak) + baris hak cipta berkredit "Design by Velocity Developer" |
| `front-page.php` | Beranda 8 seksi: hero, layanan, keunggulan, tentang, galeri, produk, alur kerja, pemesanan, kontak |
| `inc/theme-data.php` | **Satu-satunya tempat menyunting isi.** Nama, WhatsApp, telepon, email, alamat, dan area diisi otomatis dari FORM ISIAN klien |
| `inc/shortcodes.php` | `[<prefix>_layanan] [<prefix>_produk] [<prefix>_galeri] [<prefix>_alur] [<prefix>_pemesanan] [<prefix>_kontak]` untuk dipakai di halaman dalam |
| `inc/order-form.php` | Form pemesanan → email + arsip post privat `<prefix>_pemesanan` (captcha velocity-addons, nonce, honeypot, batas 1 kiriman/menit per IP) |
| `inc/images.php` | Peta foto → Media Library lewat opsi `<prefix>_images`; slot yang fotonya belum ada tampil sebagai blok bertekstur, bukan gambar rusak |
| `css/custom.css` | Desain mobile-first; seluruh warna dari token di `:root` |
| `js/custom.js` | Menu HP, header mengecil saat digulir, gulir halus ke `#pemesanan` |

Yang **tidak** dibuat di tema karena plugin velocity-addons sudah menyediakannya: tombol WhatsApp mengambang, tombol kembali ke atas, maintenance mode, galeri, captcha, statistik. Daftar lengkapnya beserta cara pakainya ada di [`docs/pelajaran-automasi.md`](docs/pelajaran-automasi.md).

Placeholder yang diisi generator: awalan fungsi & kelas CSS (`--prefix`, bawaannya 4 huruf pertama label domain), nama tema, domain, data klien, dan palet warna (`--primary` / `--accent`; turunan gelap-terang serta varian RGB dihitung sendiri). Tanpa argumen warna, palet bawaannya navy `#14213d` + amber `#fca311`.

**Widget bawaan WordPress dihapus untuk paket ini.** Desainnya tidak memakai area widget sama sekali: `functions.php` melepas seluruh sidebar tema induk, dan `installer-runner` menjalankan `site-finish --widget` (hanya kalau `paket=Paket G`) untuk membuang instance widget yang tertinggal di basis data. Pembersihan itu sekali per situs (penanda opsi `velocity_widget_bersih`) dan **hanya menyentuh widget di sidebar yang tidak lagi terdaftar** — situs paket lain yang temanya memang memakai widget tidak terpengaruh.

Menyempurnakan desain untuk semua situs Paket G berikutnya = menyunting `templates/child-theme-paket-g/`, bukan menyalin-nempel per situs.

## Paket G tanpa maintenance mode (masa pembelajaran)

Keputusan user 2026-09-13: selama alur Paket G masih dipelajari, situsnya **tidak** ditutup maintenance mode supaya hasil otomatisasi mudah dipantau langsung. `installer-runner` melewati `site-finish --maintenance` untuk `paket=Paket G` dan menjalankan `site-finish --tandai-tanpa-maintenance`, yang menulis opsi `velocity_maintenance_paket_g` — `site-audit` membacanya sebagai "mati (sengaja)", bukan temuan `maintenance_mati_setelah_dinyalakan_installer`.

Menyalakan lagi untuk Paket G: `PAKET_G_MAINTENANCE=1` di lingkungan installer (mis. `/etc/velocity/installer-autopilot.env`). Paket lain tidak terpengaruh.

## Isi & foto contoh Paket G (`scripts/paket-g-konten`, `scripts/paket-g-foto`)

Keputusan user 2026-09-13: situs Paket G **selalu dibuatkan contoh dulu — konten dan gambar — tetapi tetap sesuai FORM ISIAN klien dan dokumen tambahan**. Isian netral seperti "Layanan Utama" atau slot foto kosong tidak boleh terbit.

**Konten** — `paket-g-konten <manifest> [--segar] [--pasang]` menulis `/var/lib/velocity/ai/generated/<domain>-tema.json` dari form + dokumen klien (company profile, katalog, catatan): hero, 4 layanan, 4 produk, 4 keunggulan, 5 alur kerja, 6 judul galeri, kata kunci foto per slot, frasa foto umum sektor usaha, dan warna. Fakta klien didahulukan; bagian tanpa data diisi contoh yang spesifik ke bidang usahanya. Tetap dilarang mengarang angka, harga, tahun, penghargaan, sertifikat, nama klien, atau testimoni.

- Dijalankan `website-install-from-manifest` **sebelum** child theme dirender, karena `inc/theme-data.php` dibuat dari JSON ini. Tanpa JSON, tema jatuh ke isian netral dan `site-audit` menandainya.
- `--pasang` mengirim theme-data.php hasil render ke situs yang **sudah** terpasang — hanya kalau berkas di situs masih isian netral (belum disunting orang). Mode `child-theme` di installer-runner memakainya.
- Dua penjagaan di kode, bukan di prompt, karena AI terbukti melanggarnya: label "CONTOH:" / "(contoh)" dibuang dari teks, dan warna dari AI dibuang kalau isian "WARNA TEMA WEB" berupa teks contoh template ("Misal: … biru dan hijau") — AI membacanya sebagai pilihan klien dua kali berturut-turut meski dilarang.

**Foto** — `paket-g-foto <manifest> [--coba]` mengisi setiap slot gambar (hero, tentang, layanan, produk, galeri) setelah `site-finish`:

1. slot yang sudah terisi tidak disentuh — kecuali slot berisi foto contoh bila company profile klien punya foto (foto contoh yang tergeser dihapus kalau tidak dirujuk di mana pun);
2. foto kiriman klien (diimpor site-finish, meta `_velocity_source`) didahulukan untuk hero/tentang/galeri;
3. foto tertanam di company profile (`compro-klien`) dibagikan AI ke slot sesuai judul halamannya; hero hanya menerima foto lanskap (rasio 1.3–2.2), logo tidak pernah dianggap foto;
4. sisanya foto contoh dari **Openverse**, lisensi CC0 / Public Domain Mark saja (bebas komersial tanpa atribusi). Asal-usulnya dicatat di meta `_velocity_foto_contoh`.

Kandidat diambil dari kata kunci slot plus kolam frasa umum sektor (`foto_umum`), lalu **dipilih AI** dari judul & tag kandidat. Pencocokan kata saja tidak cukup: kata "jumbo" (dari jumbo bag) pernah mendatangkan foto *Jumbo Rocks Campground*, dan "finished packaging products" foto Jeep. Tanpa model AI, pemilihan jatuh ke pencocokan kata kunci penting. Pencarian ditembolok per kata kunci karena Openverse tanpa kunci dibatasi ±200 permintaan/hari (±20 per situs).

**Kontak publik** di theme-data hanya dari "Kontak utk di web" atau dokumen tambahan klien (alamat peran seperti info@/cs@ didahulukan). WhatsApp & email di biodata pemilik — di form berlabel "untuk pemberitahuan perpanjangan" — tidak pernah tampil; email pemilik hanya dipakai sebagai penerima form pemesanan (`email` vs `email_publik`). Tidak ada kontak publik → `site-audit` menandai `kontak_publik_kosong`.

## Desain dari company profile klien (`scripts/compro-klien`)

Kalau folder klien berisi PDF company profile, itulah referensi desain Paket G. `compro-klien <domain> [--segar]` menulis `/var/lib/velocity/compro/<domain>/` — `compro.json` (slogan, warna, daftar foto per judul halaman), `logo.png` (dipotong dari gambar halaman sampul), dan `foto-NN.*`. Dijalankan otomatis oleh `website-install-from-manifest` dan mode `child-theme`/`apply`/`finish` di installer-runner.

- **Warna** diambil dari piksel logo (warna gelap = utama, rona lain = aksen), bukan warna vektor halaman yang tercemar teks & foto. Prioritas: manifest → pilihan klien di form → compro → bawaan; penjaga kontras tetap berlaku.
- **Isi**: `paket-g-konten` menyalin profil, visi, misi, moto, target, struktur organisasi, customer, dan legalitas dari dokumen (isian yang tidak ditemukan di teks sumber dibuang — tidak boleh dicontohkan AI), plus `judul_seksi` beranda sesuai bidang usaha. Semua yang dikirim klien ditampilkan; biodata pemilik di FORM ISIAN tetap internal.
- **Tema** menampilkannya lewat seksi Visi & Misi dan "Dipercaya oleh" di beranda, serta `[<prefix>_profil][<prefix>_struktur][<prefix>_customer][<prefix>_legalitas]` di Tentang Kami (dipasang `paket-g-setup`, yang juga membuang bagian tulisan AI yang jadi dobel). Shortcode tidak mencetak apa pun bila datanya kosong.
- **Logo & slogan**: `site-finish` memakai logo compro kalau folder klien tidak punya logo, dan slogan compro sebagai tagline.
- **Layout**: `compro.json` memuat `seksi` — urutan halaman compro (sampul, prakata, visi-misi, layanan, bagian foto, customer, target, …) beserta foto tiap halaman. Bila ada, tema memakai `inc/compro.php` (body class `<prefix>--compro`): beranda berurutan sesuai compro, header nama + subjudul di sebelah logo, judul bagian di tengah bergaris bawah dengan tab nomor, latar warna halaman compro, dan pita kaki hitam bersudut aksen. Struktur, informasi perusahaan, dan legalitas tampil di Tentang Kami. Situs tanpa compro tetap memakai susunan bawaan.
- **Foto**: `paket-g-foto` membagikan foto compro tanpa AI mengikuti halamannya (sampul → hero, halaman layanan → kartu layanan, "Gambar & Referensi" → produk, area/produksi → galeri) dan mengisi opsi `<prefix>_seksi_foto` + `<prefix>_foto_potongan` (potongan produk transparan tampil utuh). Foto bermask dijadikan PNG transparan; hiasan (panah, bentuk polos) dibuang.
- **Alamat & WhatsApp**: alamat publik diambil dari kaki halaman compro (bukan biodata form). Tanpa nomor WhatsApp publik, semua tombol WA disembunyikan dan "Hubungi Kami" menuju halaman kontak.

Penjaga render: `scripts/cek-fungsi-tema <folder> [prefix]` menolak tema yang memanggil fungsi berawalan tema yang tidak didefinisikan (HTTP 500 yang lolos `php -l`). Dijalankan `velocity-child-theme` pada setiap zip dan oleh `deploy.sh`.

## Artikel per kategori layanan

Artikel dulu menumpuk di satu kategori (`Blog`), sehingga pengunjung tidak bisa menelusuri tulisan per layanan. Sekarang `ai-content-generator.py` membuat kategori mengikuti **layanan yang benar-benar ada di child theme situs** — judulnya dibaca lewat WP-CLI dari `<prefix>_data('layanan')`, bukan ditebak dari template di installer.

- Jumlah artikel per layanan: `articles_per_category` di manifest (bawaan **2**).
- Tema tanpa daftar layanan (paket selain G) kembali ke perilaku lama: satu kategori dari `article_category`.
- Kategori dibuat/dicari per artikel saat publikasi, jadi satu situs bisa punya beberapa kategori sekaligus. Kategori yang gagal dibuat membuat artikelnya dibiarkan tanpa kategori — bukan dimasukkan ke kategori yang salah.
- Topik artikel **dibatasi ke layanannya**: judul + keterangan layanan dikirim ke AI sebagai syarat, karena tanpa itu AI menulis artikel umum dan kategorinya jadi tidak nyambung (artikel interior masuk kategori "Bangun Baru").
- Halaman **Berita** ditunjuk sebagai arsip artikel (`page_for_posts`) oleh `site-finish`. Tanpa itu halaman tersebut hanya halaman biasa berisi satu kalimat, sehingga `/berita/` tampak kosong padahal artikelnya ada — masing-masing hanya bisa ditemukan lewat arsip kategorinya.
- Konten tersimpan di `/var/lib/velocity/ai/generated/<domain>-articles.json` tetap dipakai ulang saat apply ulang (tanpa biaya AI lagi); hapus berkas itu kalau ingin membuat ulang.

`site-audit` melaporkan `artikel_per_layanan` (mis. `4/4 layanan punya kategori`) dan `arsip_artikel`, serta menandai `artikel_tanpa_kategori_layanan`, `kategori_layanan_tanpa_artikel`, atau `arsip_artikel_belum_ditentukan`.

## Titik peta (`scripts/velocity-map`)

Alamat klien sering tidak dikenali peta (nama gedung, lantai, kode pos), dan iframe `maps?q=<alamat>` yang tidak ketemu tampil sebagai peta kosong. Titiknya karena itu dicari bertahap dan **selalu berakhir sebagai koordinat**:

1. alamat lengkap → 2. kota/kabupaten → 3. provinsi → 4. titik tengah Indonesia

```bash
scripts/velocity-map <domain> --alamat "…"        # [--segar] untuk mengabaikan hasil tersimpan
```

`site-finish` memanggilnya, menyimpan hasilnya di opsi `velocity_map` (`{status, lat, lon, zoom, label, q}`), dan memakai koordinat itu di iframe — termasuk `z=` yang menyesuaikan ketelitian. Child theme membaca opsi yang sama. Geocodernya Nominatim (OpenStreetMap); hasilnya disimpan per domain di `/var/lib/velocity/geocode/`.

`site-audit` menandai `peta_tidak_spesifik` kalau yang ketemu hanya titik Indonesia — tanda alamat klien perlu diperbaiki.

## Kredit footer "Design by Velocity Developer"

Keputusan user 2026-09-14: semua situs buatan installer menampilkan kredit di baris hak cipta footer, dengan "Velocity Developer" sebagai tautan tab baru ke `https://velocitydeveloper.com` (`target="_blank" rel="noopener"`).

- **Tema induk `velocity`** (dan child theme yang tidak mengganti footer): `site-finish` memasang mu-plugin `wp-content/mu-plugins/velocity-footer-credit.php`. Tema mencetak baris hak cipta langsung di `justg_the_footer_content` tanpa filter, jadi mu-plugin membungkus kait `justg_do_footer` dan menyisipkan kredit ke `.site-info`. Footer yang sudah memuat `velocitydeveloper.com` tidak disentuh. Berkas ini milik installer dan ditimpa setiap finishing.
- **Paket G / Portal Berita Custom**: ditulis langsung di `templates/child-theme-paket-g/footer.php` (footer biasa & footer gaya compro). Situs terpasang ikut berubah lewat `child-theme-apply --perbarui`, kecuali `footer.php`-nya sudah disunting.
- **Tema FSE**: tulis kreditnya di `parts/footer.html` (aturan di skill `wp-fse`).
- **Audit**: `site-audit` menandai `kredit_footer_tidak_ada`.

## Wajib di setiap situs

Keputusan user 2026-09-14, berlaku untuk semua paket (tema klasik, child theme, maupun FSE). Situs belum boleh dilaporkan selesai sebelum semua butir di bawah terpenuhi.

1. **Favicon wajib ada.** `site-finish` memasangnya: logo klien kalau ada, ikon logo contoh kalau tidak (bagian [Favicon](#favicon) dan [Logo contoh](#logo-contoh-scriptsvelocity-logo)). Situs FSE yang temanya dipasang manual juga wajib diperiksa. Audit: `favicon_belum_terpasang`.
2. **Halaman kebijakan privasi (Privacy Policy) wajib ada dan terbit.** `website-install-from-manifest` membuat halaman "Kebijakan Privasi" berstatus publish dan menetapkannya sebagai `wp_page_for_privacy_policy` (Pengaturan → Privasi). Draft "Privacy Policy" bawaan WordPress tidak dihitung — karena itu `site-finish` (2026-09-16) menerbitkan draf itu dan mengganti judulnya kalau situs sudah terpasang tanpa halaman privasi. Audit: `halaman_privasi_tidak_ada` / `halaman_privasi_belum_terbit:<status>`.
3. **Tampilan desktop dan mobile wajib rapi, terutama padding dan margin.** Periksa lewat screenshot di lebar desktop (1366px) dan HP (390px), jangan hanya HTTP 200. `paket-g-cek-visual` sudah memotret keduanya. Daftar periksa dan contoh kasus nyata ada di [`docs/pelajaran-automasi.md`](docs/pelajaran-automasi.md#kerapian-padding--margin-desktop-dan-mobile).
4. **Featured image (foto utama) setiap post wajib punya caption.** Caption = kolom *Keterangan* attachment (`post_excerpt`, dibaca `wp_get_attachment_caption()`), dan **wajib tampil** di halaman artikel di bawah foto. Isinya harus benar: keterangan dari klien, atau sumber/kredit foto contoh (mis. judul & pembuat dari Openverse). Jangan mengarang peristiwa, nama orang, atau lokasi. Keadaan saat ini (2026-09-14): `paket-g-foto` memasang foto utama lewat `wp media import --featured_image` **tanpa** caption, `templates/child-theme-paket-g/single.php` hanya `the_post_thumbnail()`, dan blok `core/post-featured-image` di tema FSE tidak mencetak caption. Ketiganya perlu disesuaikan. Audit: `foto_utama_tanpa_caption:<jumlah>`.
5. **Statistik pengunjung di footer, sebagai kolom.** Keputusan user 2026-09-15, dipertegas 2026-09-16: shortcode velocity-addons `[velocity-statistics style="list" show="all" with_online="1" …]` dipasang di **satu kolom footer** sejajar kolom Menu/Kontak, dengan **judul kolom** "Statistik Pengunjung" dan **isi cukup list** (label di kiri, angka di kanan) — tanpa ikon, kotak, atau pita selebar footer. Markup plugin memakai kelas Bootstrap (`list-group`, `d-flex`, `fw-bold`) yang tidak dimuat tema blok, jadi daftarnya ditata CSS tema (`.vf-statistik` di `templates/tema-fse/style.css`, kolom keempat di `templates/tema-fse/parts/footer.html`). Versi plugin lama mencetak `<div>` per baris, versi baru `<li>` — keduanya ditangani.
6. **Email publik + ikon media sosial** di halaman Kontak Kami dan footer (keputusan user 2026-09-14): `core/social-links` ikon saja (facebook, instagram, x, youtube, tiktok) dengan URL bawaan platform sampai klien memberi akun. Kalau form hanya memuat email biodata pemilik, tanya user dulu; jawabannya ditulis di manifest (`email_publik=`).
7. **Setiap tema wajib punya `screenshot.jpg`.** Keputusan user 2026-09-16, untuk tema FSE maupun child theme: berkas `screenshot.jpg` ukuran **1200x900**, latar **polos gelap**, tulisan **putih** berisi **nama tema** (Theme Name). Tanpa itu tema tampil sebagai kotak kosong di Tampilan → Tema. Alatnya `scripts/tema-screenshot <nama tema> <keluaran.jpg> [warna latar]` (Node + Chromium, karena server ini tidak punya PIL/ImageMagick dan librsvg tidak bisa menulis JPEG). `velocity-fse` membawa `templates/tema-fse/screenshot.jpg` di repo (dijaga `deploy.sh`), child theme membuatnya per situs saat render (`screenshot_tema` di `scripts/velocity-child-theme`, latar = warna utama klien digelapkan).
8. **Latar video wajib menutupi penuh (cover) di desktop maupun HP.** Keputusan user 2026-09-17: setiap seksi berlatar video (YouTube/Vimeo lewat `core/cover` `backgroundType: embed-video`, atau `<video>` mandiri) harus memenuhi seluruh seksi tanpa pita hitam, di 1366px dan 390px. Jebakan: CSS core WP 7.1 memberi iframe ukuran `100vw x 100vh`, jadi video 16:9 hanya pas bila layarnya juga 16:9 — di HP 390px video tampil 390x219 di tengah hero setinggi 620px (xpengjakartaindonesia.com). `templates/tema-fse/style.css` (v1.10.36) menanganinya untuk semua cover: `.wp-block-cover__embed-background { container-type: size }` + iframe `width: max(100cqw, 177.78cqh); height: max(100cqh, 56.25cqw)`. Untuk `<video>` mandiri cukup `object-fit: cover` + ukuran 100%. Tema lain/child theme yang memakai latar video wajib membawa aturan setara. Periksa dengan mengukur kotak iframe/video vs kotak seksi di 1366px dan 390px (bukan hanya melihat desktop), dan pastikan tidak muncul geser mendatar.
9. **Foto galeri bisa diklik → popup dengan tombol Previous/Next.** Keputusan user 2026-09-21 (minionscooterrentallombok.com), berlaku untuk semua jenis tema. `site-finish` memasang mu-plugin `velocity-galeri-popup.php` (sumber `templates/mu-plugins/velocity-galeri-popup.php`, ditimpa setiap finishing): lightbox bawaan core WP 7.x dinyalakan saat render untuk **semua** gambar di blok `core/gallery` — termasuk galeri yang ditambah klien sendiri di editor — sehingga klik foto membuka popup berlatar gelap dengan tombol Prev/Next, panah keyboard, geser di HP, dan Esc untuk menutup (navigasi per galeri lewat konteks `galleryId`). Tautan ke file/lampiran diganti popup; lightbox yang sengaja dimatikan dan tautan custom dihormati. Shortcode `[gallery]` tema klasik (halaman Galeri `site-finish`) dirender sebagai blok Galeri yang sama. Log: `galeri_popup_set` / `galeri_popup_gagal:php_lint`. Galeri buatan sendiri (tema mandiri/agen desain) wajib memakai `core/gallery` berisi `core/image`, bukan grid HTML/`<a href>` ke file.

## Logo klien dicari di semua kiriman klien (`scripts/cari_logo.py`)

Keputusan user 2026-09-16: **logo dicari lebih dulu di berkas yang diupload klien — company profile, compro, atau berkas apa pun — dan logo contoh baru dibuat kalau benar-benar tidak ada.** Dulu hanya dua sumber (gambar bernama `logo*` dan potongan dari satu PDF compro terpilih), sehingga klien yang logonya "hanya" ada di dalam docx atau di PDF kedua tetap dapat logo contoh.

Urutan pencarian (`cari_logo.cari(domain, folder, compro)`), berhenti di yang pertama ketemu:

| # | Sumber | Catatan |
|---|---|---|
| 1 | gambar di folder klien yang namanya menyebut `logo`/`lambang`/`brand` | perilaku lama, PNG diutamakan |
| 2 | potongan company profile (`compro-klien`) | logo bertransparansi dari halaman 1 |
| 3 | gambar tertanam di **PDF lain** di folder klien | proposal, katalog, compro yang tidak terpilih |
| 4 | gambar tertanam di **dokumen Office** (`.docx`/`.pptx`) | logo kop surat & sampul proposal |
| 5 | gambar lepas lain yang berciri logo | PNG bertransparansi, tidak mendatar, ≤2000px |
| — | tidak ada → `scripts/velocity-logo` | logo contoh (bagian di bawah) |

Sumber 3–5 wajib lolos `mirip_logo()`: latar tembus pandang (≥15%) atau palet ≤24 warna, total ≤60 warna, ada tinta yang tergambar (≥5%), dan bukan bidang rata. Tanpa saringan itu ikut terambil **tangkapan layar situs contoh** di dalam docx dan **kotak bayangan hiasan** dari PDF (keduanya terjadi 2026-09-16). Subfolder bernama `contoh`/`referensi`/`desain`/`screenshot` tidak pernah dibaca — isinya logo perusahaan lain.

Diperiksa atas 43 folder antrean: 8 domain punya berkas bernama logo, 2 dari company profile, 1 dari docx (medikaklinikteknologi.com), sisanya memang tidak mengirim logo.

Log `site-finish`: `finish: logo dari <sumber>` (mis. `dokumen:Company profil untuk website.docx`) atau `finish: logo klien tidak ditemukan di kiriman klien`.

## Favicon

**Kalau klien punya logo, favicon selalu logo klien** (keputusan 2026-09-14, berlaku untuk semua paket). Logo klien dicari lewat `cari_logo.py` di atas.

- Logo tidak dipakai mentah: `site-finish` menaruhnya utuh di tengah kanvas transparan 512×512 (`favicon_klien`, lewat `rsvg-convert`), karena WordPress butuh ikon persegi ≥512px dan logo klien sering mendatar atau kecil. Media-nya bertanda `_velocity_source=favicon-klien:…`.
- Favicon yang dipasang installer (ikon logo contoh, logo mentah dari versi lama) digeser favicon logo klien. Favicon yang diunggah orang lewat Customizer (tanpa `_velocity_source`) tidak pernah ditimpa.
- WebP tidak bisa dibaca `rsvg-convert` di server installer (tidak ada loader gdk-pixbuf): logo dipakai langsung dan log mencatat `favicon_persegi_gagal:.webp`.
- Klien tanpa logo tetap memakai ikon dari logo contoh (bagian berikut).

## Logo contoh (`scripts/velocity-logo`)

Klien sering menulis "logo menyusul", dan situsnya jadi tampil tanpa identitas sama sekali. Kalau folder klien tidak berisi logo, `site-finish` membuatkan logo contoh dari nama perusahaan + warna tema situs (diambil dari "WARNA TEMA WEB" di form; bawaannya navy `#14213d` + amber `#fca311`).

```bash
scripts/velocity-logo <domain> [--nama NAMA] [--primary #hex] [--accent #hex] [--out DIR] [--no-png]
```

Hasilnya di `/var/lib/velocity/logos/<domain>/`:

| Berkas | Untuk |
|---|---|
| `logo.svg` / `logo.png` | Logo mendatar, tulisan gelap — header berlatar terang |
| `logo-terang.svg` / `logo-terang.png` | Varian tulisan putih — header berlatar gelap |
| `icon.svg` / `icon.png` | Badge persegi 512px untuk favicon |

Bentuknya netral: badge inisial (kata yang tidak mewakili usaha seperti "jasa", "pt", "cv" dilewati) + nama perusahaan + domain. SVG-nya disediakan supaya desainer bisa langsung menyuntingnya; PNG dibuat karena WordPress menolak SVG tanpa plugin tambahan dan favicon wajib raster ≥512px. Rasterisasi memakai `rsvg-convert` di server installer — kalau alat itu tidak ada, SVG tetap dibuat dan langkah PNG-nya saja yang dilewati.

**Logo contoh selalu kalah dari logo sungguhan.** Id-nya dicatat di opsi `velocity_logo_contoh` / `velocity_icon_contoh`, dan aturannya: logo dipasang hanya kalau belum ada logo sama sekali, atau kalau yang terpasang masih logo contoh buatan installer. Jadi logo asli klien (dan logo yang dipasang PM lewat Customizer) tidak pernah tertimpa, sementara logo contoh lama boleh digeser logo contoh baru saat nama atau warna situs berubah.

Catatan desain: logo bertulisan gelap tidak terbaca di header berlatar gelap. Child theme yang header-nya gelap perlu memberi alas putih pada `.navigation-brand-logo img`, atau memakai varian `logo-terang`.

## Audit situs (`scripts/site-audit`)

`site-qa` adalah gerbang saat instalasi dan memeriksa dari luar (HTTP/REST). Begitu maintenance mode menyala, yang terbaca hanyalah halaman perawatan — logo, menu, dan galeri ikut terbaca "tidak ada" padahal terpasang. QA juga berjalan sebelum maintenance dinyalakan, jadi ia tidak bisa menjaga keadaan akhir.

`site-audit` membaca dari **dalam** situs lewat WP-CLI, jadi tetap akurat meski situs tertutup:

```bash
scripts/site-audit <domain|manifest> [--json]        # butuh WP_INSTALL_SSH_KEY_FILE
curl -X POST http://127.0.0.1:9121/api/installer/run -d '{"domain":"contoh.com","mode":"audit"}'
```

Yang dibandingkan: tema aktif vs child theme yang seharusnya, halaman wajib (Paket G ikut Layanan/Produk/Pemesanan), jumlah item menu, form pemesanan benar-benar terpasang beserta captcha velocity-addons-nya (aktif, penyedianya, dan kunci Google kalau dipakai), **shortcode yang dipakai halaman tapi tidak ada fungsinya** (tercetak apa adanya ke pengunjung), logo & favicon (termasuk **apakah masih logo contoh**), artikel per kategori layanan, titik peta (alamat / kota / provinsi / Indonesia), tombol WhatsApp velocity-addons (aktif, nomornya terisi, tulisannya berupa ajakan dan bukan nama situs, sekaligus menandai kalau tema membuat tombol tandingan), widget nyasar, jumlah foto, sisa teks contoh template, maintenance mode, SSL, dan HTTP aset inti. Keluarannya ringkasan untuk dibaca manusia + satu baris JSON `{"audit": "ok"|"temuan", ...}`.

Kepemilikan: `wp_content_milik_root`, atau `pemilik_wp_content_salah:<n>` bila ada berkas di `wp-content` yang pemilik/grupnya beda dari `wp-content` (info `pemilik_wp_content` menyebut 3 contoh). Perbaikannya `scripts/pemilik_wp.py <manifest>`.

Audit tidak mengubah apa pun — status instalasi di `<domain>.json` dan notifikasi Telegram tidak disentuh.

Pemeriksaan tambahan 2026-09-17 (pelajaran jasakontraktorindo.com & centralimpex.com): `referensi_form_terlewat` (form menyebut web contoh — termasuk domain polos atau "contoh seperti X" di kolom lain — tetapi rencana tercatat tanpa referensi), `artikel_tanpa_foto_utama`, `statistik_footer_tidak_ada`, `sosmed_footer_tidak_ada`, `seo_dasar_kosong`, `teks_catatan_ai` (kalimat seperti "... belum tersedia dalam data perusahaan" tampil), `judul_ganda` (h1/h2 sama tercetak dua kali), dan `kontak_biodata_tampil` (email/alamat BIODATA PEMILIK tampil di beranda/kontak; lolos bila tercantum di "Kontak utk di web", dokumen klien selain form, atau disetujui di manifest `email_publik=` / `alamat_publik=`). Form pemesanan dikenali dari blok `wp:*/form` mana pun, dan halaman wajib menerima slug padanan (about/profil, portofolio/gallery, blog/insights, kontak/contact); situs `tema_fse=` hanya dituntut halaman kontak.

### Audit susulan (`scripts/audit-susulan`, halaman `/installer/susulan/`)

Situs yang sudah jadi tidak otomatis ikut aturan yang lahir sesudahnya. `audit-susulan` menjalankan `site-audit` (hanya membaca) untuk semua manifest berstatus SUCCESS/CHECK, memisahkan temuan "belum ikut aturan" dari temuan lain, dan menyimpan `/var/lib/velocity/installer/audit-susulan.json` → `/api/installer/susulan` → halaman `/installer/susulan/` (filter per aturan). Perbaikan tetap diputuskan manusia karena sebagian situs sedang dikerjakan webmaster. Timer `audit-susulan.timer` menjalankannya tiap hari 03:40.

```bash
WP_INSTALL_SSH_KEY_FILE=/root/.ssh/id_ed25519 scripts/audit-susulan [--paralel 4] [domain ...]
```

Temuan `maintenance_mati_setelah_dinyalakan_installer` sengaja ada: pernah terjadi maintenance mode mati sendiri sehingga situs yang belum diserahkan sempat terbuka untuk umum, dan `site-finish --maintenance` tidak akan menyalakannya lagi (penanda `velocity_installer_maintenance` sudah ada). Pemulihannya manual: `wp option update maintenance_mode 1`.

Pelajaran lain dari pembangunan alur ini dicatat di [`docs/pelajaran-automasi.md`](docs/pelajaran-automasi.md) — baca sebelum menambah langkah otomatis baru. Khusus soal palet warna dan keterbacaan: [`docs/warna-dan-kontras.md`](docs/warna-dan-kontras.md), dengan penjaganya `scripts/cek-warna-tema` (ikut dijalankan `deploy.sh`). Paket toko online: struktur produk milik plugin VD Store (`store_product`, arsip `/produk/`, shortcode katalog) ada di [`docs/vd-store.md`](docs/vd-store.md) — tema, generator, dan agen desain tidak membuat CPT produk sendiri.

## Halaman & menu Paket G (`scripts/paket-g-setup`)

Child theme Paket G membawa blok desain berupa shortcode; halaman pemakainya dibuat otomatis sesudah `site-finish` (urutannya penting — finishing menulis ulang halaman Galeri & Hubungi Kami):

- **Layanan, Produk, Pemesanan** → halaman baru berisi teks pembuka + shortcode. Halaman yang sudah disunting orang tidak ditimpa.
- **Galeri, Hubungi Kami** → blok desain ditambahkan di bawah teks yang sudah ada.
- **Shortcode berawalan salah dibuang** lebih dulu. Awalan tema (`jki_`, `jasa_`, …) dibaca dari situs — shortcode `*_pemesanan` yang benar-benar terdaftar — bukan ditebak ulang dari nama domain, karena tebakan yang berbeda pernah mengisi halaman dengan `[jasa_kontak]` yang tidak ada fungsinya.
- **Menu utama** disusun sekali (penanda `velocity_paket_g_menu`), mengikuti susunan yang ditulis klien di FORM ISIAN: Beranda · Profil · Layanan · Produk · Pemesanan · Galeri Foto · Berita · Kontak Kami.

## Ambil alih (klaim)

CRM belum punya API tulis, jadi klaim dicatat lokal di `/var/lib/velocity/installer/claims.json` — status di CRM tetap "Belum dikerjakan". Domain yang diklaim tidak lagi tampil sebagai `belum diambil`.

- `POST /api/installer/claim` — body `{"domain":"example.com","by":"manual"|"autopilot"}`. Idempoten.
- `POST /api/installer/release` — body `{"domain":"example.com"}`.
- Halaman installer: menu **Ambil alih** / **Lepas klaim**, badge `DIAMBIL: MANUAL|AUTOPILOT`.
- Domain berstatus `dikerjakan webmaster` tetap bisa diklaim (installer memang pernah mengerjakan project yang di CRM sudah ditugaskan, mis. `popcreativeprint.com`), tapi tombolnya minta konfirmasi berisi nama webmasternya supaya tidak ada yang ditabrak tanpa sadar.

## Autopilot (`scripts/installer-autopilot`)

`installer-autopilot.timer` tiap 10 menit. Satu putaran:

1. Domain yang sedang dipegang autopilot dilanjutkan: dry-run OK + `site=empty` → apply. Dry-run gagal, situs sudah berisi (`site=wordpress|not_empty`), atau run macet >2 jam → fase `manual` (tanpa notifikasi untuk tahap dry-run; apply yang gagal tetap dilaporkan).
2. Kalau tidak ada run berjalan, ambil **satu** project `belum diambil` yang lolos saringan: klaim → generate manifest → dry-run.

Saringan: folder Drive sudah tersinkron, jenis `Pembuatan`/`Pembuatan apk biasa`/`Pembuatan Tanpa Domain` (Redesign tidak), FORM ISIAN klien terbaca, belum pernah ditangani autopilot, dan **deadline belum terlewat**.

**Aturan deadline (keputusan user 2026-09-16, menggantikan mode `terlama`):** autopilot hanya mengambil project yang deadline-nya **belum terlewat**, yang paling dekat lebih dulu (deadline hari ini masih terhitung belum lewat; baris tanpa deadline ikut diambil, diurutkan paling belakang). Project yang deadline-nya sudah lewat **dibiarkan** untuk dikerjakan manusia — alasannya `deadline_sudah_terlewat_biarkan_manual`. `AUTOPILOT_PRIORITAS`, `AUTOPILOT_MIN_TELAT_DAYS`, dan `AUTOPILOT_DEADLINE_GRACE_DAYS` tidak lagi dipakai autopilot (`AUTOPILOT_DEADLINE_GRACE_DAYS` masih dibaca `onprogress-sync` untuk menentukan folder mana yang ditarik dari Drive).

Aturan lama `terlama` (2026-09-13) memakai deadline sebagai tebakan "ini sedang dipegang webmaster". Tebakan itu tidak diperlukan lagi sejak daftar menarik status `Dalam pengerjaan` dari CRM: project yang sudah ditugaskan ke webmaster berstatus `dikerjakan webmaster` dan tidak pernah masuk hitungan autopilot, jadi yang tersisa di `belum diambil` memang benar-benar belum dipegang siapa pun.

> Catatan 2026-09-16: `AUTO_JENIS` masih menulis `Pembuatan Tanpa Domain`, padahal nilai di CRM adalah `Pembuatan Tanpa Domain+Hosting` — jadi jenis itu **tidak pernah** benar-benar diambil autopilot (`jenis_redesign_atau_lain`). `INSTALL_JENIS` (daftar di halaman) sudah diperbaiki; `AUTO_JENIS` sengaja dibiarkan karena memperbaikinya berarti autopilot mulai mengambil kategori project yang selama ini tidak pernah disentuhnya — keputusan user.

Mode di `/etc/velocity/installer-autopilot.env`: `AUTOPILOT_MODE=observe` (default — hanya mencatat rencana ke `/var/lib/velocity/installer/autopilot-last.json` + journald) atau `AUTOPILOT_MODE=active`. Jejak per domain: `/var/lib/velocity/installer/autopilot.json`.

## Sync Google Drive (`scripts/onprogress-sync`)

`onprogress-sync-queue.timer` — tiap 10 menit. Tidak ada sync penuh: Drive berisi ±10 ribu folder yang tidak dibutuhkan installer.

**Disalin berkala selama project masih berjalan, bukan sekali saat masuk antrean** (permintaan user 2026-09-16: klien kerap menambah berkas di Drive sesudah project diambil alih). Saringan lama hanya `belum diambil`, jadi begitu autopilot mengklaim sebuah domain foldernya berhenti disinkron dan tambahan data klien tidak pernah sampai — 19 dari 33 folder yang sekarang ikut adalah project yang sudah diklaim/dipegang webmaster dan selama ini terlewat.

Yang ikut: semua baris di daftar installer, kecuali (a) status `RUNNING` — jangan mengubah data sumber di tengah instalasi, ikut lagi putaran berikutnya; (b) `belum diambil` yang deadline-nya lewat lebih dari `AUTOPILOT_DEADLINE_GRACE_DAYS` (10) hari. Project yang sudah terpasang penuh (SUCCESS/COMPLETE) hilang dari daftar, jadi berhenti disinkron dengan sendirinya. Dampak saat diterapkan: 14 → 33 folder.

Selalu `rclone copy` (tidak pernah menghapus file lokal) — menyalin ulang folder yang sudah ada murah, rclone hanya memindahkan berkas baru/berubah.

## Tampilan paket biasa / child theme klasik (`scripts/theme-paket-biasa`)

Permintaan user 2026-09-17 (sedotwcsrirejeki.com, rmbrentcar.com): paket non-custom harus terpasang serapi situs yang dirapikan manual (sobirin-advokat.com). Alur `installer-runner` untuk paket biasa kini:

1. `paket-g-konten` (sebelum konten AI) → `<domain>-tema.json`: hero, layanan, keunggulan, profil. Layanannya jadi **kategori artikel** (`kategori_isi_contoh` di `ai-content-generator.py`); artikel "Blog" lama yang belum disunting dipensiunkan.
2. `theme-paket-biasa` (sesudah site-finish, satu koneksi SSH, `wp eval-file` sebagai user DA):
   - beranda memakai template "Home Template" child theme + pengaturan temanya lewat adaptor: `velocity-pakete` (banner_*, judul_layanan, services_list) dan `velocity-perusahaan2` (home_banner, *_banner, sambutan, layanan_repeater, title_homelogo). Tema lain: `tampilan: beranda_tema_belum_didukung:<slug>`.
   - halaman **Layanan** (anchor per layanan) + menu; blok kontak `<!-- velocity-kontak -->` di Hubungi Kami (telepon, WhatsApp, email publik, ikon sosial Bootstrap Icons); widget sidebar (hubungi, layanan, artikel terbaru) & footer (tentang + email + ikon sosial, kontak, `[velocity-statistics]`); CSS di antara `/* velocity-tampilan-klasik */`; `statistik_velocity=1` sekali.
   - gambar: foto klien bergilir → foto bank (pemilih `paket-g-foto`) → banner gradasi. Tembolok `/var/lib/velocity/tampilan/<domain>/` supaya run ulang tidak mengunggah media baru.
   - tidak menimpa kerja orang: nilai bawaan tema dianggap kosong; pengaturan/widget/halaman hanya ditulis bila kosong, bawaan, atau masih persis tulisan langkah ini (opsi `velocity_tampilan_klasik`, meta `_velocity_content_md5`).
3. `paket-g-foto --artikel` lalu `theme-paket-biasa --foto-artikel`: sisa artikel tanpa foto bank yang layak diberi foto klien bergilir atau sampul bertuliskan kategori (caption selalu ada).

`paket-g-foto` menolak calon foto berupa kartun/satire/karikatur/politik, gambar teknik/peta/denah, dan arsip lawas (`bukan_foto`). Mode `child-theme` untuk paket biasa ikut menjalankan langkah 1–3. Uji tanpa SSH: `scripts/theme-paket-biasa <manifest> --coba`.

**Adaptor beranda buatan AI** (`scripts/adaptor_tema.py`, permintaan user 2026-09-17): tema yang belum punya adaptor buatan tangan tidak lagi dilewati. `theme-paket-biasa` mengambil semua file PHP child theme yang TERPASANG di situs (satu koneksi SSH), memberikannya ke AI (fungsi `tema` di halaman `/ai/`), lalu AI menjawab adaptor JSON: template beranda, pengaturan (`mods`) berpenanda data klien (`{{hero_judul}}`, `{{id:hero}}`, perulangan `{"__untuk__": "layanan", ...}`), nilai bawaan tema, dan teks contoh tema untuk diperiksa. Kode memvalidasi (nama pengaturan harus ada di kode tema, template harus ada, penanda dikenal) dan merapikan bentuk perulangan yang lazim ditulis AI. Sesudah diterapkan, beranda dibuka lewat pratinjau: nama/judul & judul layanan harus tampil, teks contoh tema tidak boleh tampil. Gagal -> pengaturan & template lama dikembalikan (`velocity_tampilan_klasik.cadangan`), adaptor ditandai gagal dan dibuat ulang di run berikutnya dengan alasannya (maks 3 kali). Adaptor tersimpan per tema + versi + sidik file di `/var/lib/velocity/tampilan/_adaptor/`, status `belum_diperiksa` / `terverifikasi` / `gagal`. Uji: `theme-paket-biasa <manifest> --coba --paksa-ai` (paksa AI walau tema punya adaptor buatan tangan; `--coba` menulis `mods.json` tanpa menerapkan). Selain hero/tentang/layanan, adaptor punya foto pendamping `{{id:foto1}}`..`{{id:foto3}}` (gambar kecil banner) dan perulangan `{"__untuk__": "galeri"}` berisi hingga 8 foto klien (`galeri-<n>.jpg`); tanpa foto klien daftar galeri kosong. Gambar yang diunggah hanya slot yang dirujuk pengaturan tema aktif (`tampilan: aset_dipakai=... unggah=N`), dan potongan yang isinya identik di dua slot memakai satu lampiran — dulu semua 16 slot selalu diunggah (wisesayasatidar.com 2026-09-18: 16 lampiran dari 7 foto, `velocity-pakete` hanya memakai hero).

**Paket tour** (`scripts/paket-tour`, sadewatourstravel.com 2026-09-17): child theme tour (`velocity-tour1`) menampilkan "Paket Wisata" dari CPT `paket-tour` milik plugin `velocity-tour-travel` (repo `VelocityDeveloper/velocity-tour-travel`, tidak ada di API plugin). Sesudah `theme-paket-biasa`, bila file tema aktif menyebut `paket-tour`: plugin dipasang dari clone GitHub (tembolok `/var/lib/velocity/packages/plugins/`) & diaktifkan, AI menyalin paket dari dokumen klien (tabel harga per peserta, fasilitas, tidak termasuk, rundown) ke `/var/lib/velocity/ai/generated/<domain>-paket-tour.json`, lalu tiap paket jadi post `paket-tour` (meta harga mulai/durasi/lokasi/itinerary/fasilitas/galeri, taksonomi kategori/destinasi/durasi, foto klien bergilir), `no_pemesanan` = WhatsApp bila kosong, menu "Paket Tour". Post yang sudah disunting (`_velocity_content_md5`) dibiarkan. Tema lain: `paket_tour: dilewati`. Uji tanpa SSH: `scripts/paket-tour <manifest> --coba`.

Belum tercakup: kontak publik hanya dari "Kontak utk di web"/company profile — email & alamat biodata pemilik tidak pernah tampil, jadi situs tanpa data itu hanya menampilkan WhatsApp.

## Token GitHub & pengingat kedaluwarsa (`scripts/cek-token-github`)

Token organisasi di `/etc/velocity/secrets/github_token` (600) dipakai dua hal: `velocity-child-theme` (rilis repo privat seperti `velocity-pakete` dibalas 404 tanpa login, lalu diulang lewat API aset GitHub) dan git repo ini (credential helper; URL remote tanpa token). Mengganti token cukup menimpa file itu.

`velocity-token-github.timer` tiap 09:00 WIB membaca tanggal kedaluwarsa dari header GitHub dan mengirim pengingat Telegram (tujuan sama dengan notifikasi installer) setiap hari mulai `GITHUB_TOKEN_BATAS_HARI` (bawaan 7) hari sebelum kedaluwarsa, atau langsung bila token ditolak/hilang. GitHub yang tak terjangkau tidak memicu pesan. `scripts/cek-token-github --cetak` menampilkan pesan tanpa mengirim.

## Pasang unit systemd

```bash
install -m 644 config/onprogress-sync@.service config/onprogress-sync-queue.timer \
  config/installer-autopilot.service config/installer-autopilot.timer \
  config/velocity-token-github.service config/velocity-token-github.timer \
  config/audit-susulan.service config/audit-susulan.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now onprogress-sync-queue.timer installer-autopilot.timer velocity-token-github.timer audit-susulan.timer
```
