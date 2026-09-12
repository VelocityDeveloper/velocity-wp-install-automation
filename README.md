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
- `GET /api/servers` — daftar server dari `/var/lib/velocity/servers.json` (managed panel `/server/`) atau fallback `config/servers.json` / env `INSTALLER_SERVERS`.
- `GET /api/installer` — daftar domain + validasi manifest + cronjobs summary (cache 30s, tidak bocor raw crontab) + state/log per-domain dari `/var/lib/velocity/installer`.
- `POST /api/installer/run` — body `{"domain":"example.com","mode":"dry-run"|"apply"|"finish"|"maintenance"|"child-theme"}`. Validasi domain + manifest, tolak `already_running`, spawn `scripts/installer-runner` detached (log ke `/var/lib/velocity/installer/<domain>.log`). Browser pakai endpoint ini untuk tombol install/retry. Saat `apply`, service menyetel `WP_INSTALL_SSH_KEY_FILE` (auto-detect `/etc/velocity/secrets/ssh_key` atau `/root/.ssh/id_ed25519`/`id_rsa`) + `WP_INSTALL_DB_PASSWORD_FILE`/`WP_INSTALL_ADMIN_PASSWORD_FILE` per-domain dari `/etc/velocity/secrets/`.
- `POST /api/installer/generate` — body `{"domain":"example.com"}`. Auto-generate manifest (da_user/db dari label domain, admin_email dari `notes-credentials.txt` bila ada) + secret password random per-domain (tidak pernah menimpa yang sudah ada). Domain tanpa manifest valid bisa langsung di-generate dari tombol `[ generate ]` di halaman installer.

Auth: jika `INSTALLER_API_TOKEN` di-set, semua `/api/*` butuh `Authorization: Bearer <token>`. Rate-limit 30 req/60s per IP. Jangan expose port 9121 langsung — via reverse proxy (blok location referensi: `config/nginx-installer.conf`).

## Manage server page (`web/server/index.html`)

Terminal-style `/server/`. Read/write `/var/lib/velocity/servers.json` via `GET/PUT /api/servers` (server-registry service di port 9122). Form validasi + edit modal, sumber data installer & panel ini.

## Installer page (`web/installer/index.html`)

Terminal-style `/installer/`.

- pilih server tujuan (dari `/api/servers`)
- lihat validasi manifest (READY vs `missing_*/invalid_*`) + log 30 baris terakhir
- tombol `[ generate ]` — domain tanpa manifest valid (NO_MANIFEST/missing_*/invalid_*) → auto-generate manifest + secret password → status jadi READY
- tombol `[ install ]` (status READY/SUCCESS) atau `[ retry ]` merah (status FAILED/installer_error) → modal konfirmasi dengan pilihan mode: **Dry run** (validasi saja) atau **Apply** (eksekusi nyata) → `POST /api/installer/run`
- tombol `[ log ]` → popup detail log 30 baris terakhir
- polling 10s, pause saat `document.hidden`

## Workflow (`workflows/website-install-workflow.json`)

Import ke n8n. Trigger: Manual Trigger dengan `{"domain":"example.com"}`. Node `Execute Command` pakai wrapper `scripts/installer-runner` (validasi & escape domain, cegah injection, tulis STATE).

Timeouts: dry-run 30s, apply 300s. Dry-run retry 2x.

## Alur apply lengkap

`installer-runner` (mode `apply`): install WordPress → cek HTTP → konten AI (`ai-content-generator.py`) → finishing (`site-finish`) → hapus tema & plugin bawaan yang tidak dipakai (`site-finish --cleanup`) → pemeriksaan akhir (`site-qa`) → maintenance mode (`site-finish --maintenance`) → laporan Telegram ✅ selesai, atau 🟡 "perlu dicek" beserta daftar masalah.

- **Pembersihan** hanya pada run yang memasang WordPress dari awal (bukan apply ulang situs lama, bukan mode finish/maintenance): tema `twenty*` dan plugin `akismet`/`hello` yang tidak aktif. Tema aktif dan induknya tidak pernah dihapus; tema/plugin non-bawaan tidak disentuh.

- **Maintenance mode** (plugin velocity-addons, opsi `maintenance_mode` + `maintenance_mode_data`) dinyalakan sebagai langkah terakhir, sesudah pemeriksaan akhir (yang membaca situs sebagai pengunjung). Hanya sekali per situs (penanda opsi `velocity_installer_maintenance`) dan tidak kalau opsinya sudah pernah diatur orang, jadi apply ulang setelah PM mematikannya saat serah terima tidak menyalakannya lagi. `site-qa` mengenali halaman perawatan dan melewati pemeriksaan berbasis beranda.
- **Akun DirectAdmin selalu dibuat manual oleh PM.** Kalau dry-run autopilot gagal karena akun/folder domain belum ada, domain masuk fase `waiting_da`: dry-run diulang tiap 30 menit (maks. 14 hari) tanpa notifikasi, lalu instalasi berlanjut otomatis begitu akun dibuat.
- **Tahap dry-run tidak dilaporkan ke Telegram** (diambil alih, dry-run gagal/macet, situs sudah berisi, menunggu akun DirectAdmin). Statusnya terlihat di jurnal `/var/lib/velocity/installer/autopilot.json` dan halaman installer. Telegram hanya untuk hasil apply: selesai, perlu dicek, atau gagal.

- **Konten AI** dibersihkan `content_sanitize.py` (tanpa `<img>`/`<iframe>`/`<form>`/placeholder). Halaman tulisan installer ditandai meta `_velocity_content_md5`; apply ulang hanya menimpa halaman yang belum disunting orang. Konten tersimpan di `/var/lib/velocity/ai/generated/` dipakai ulang.
- **Bahan AI**: isi FORM ISIAN + dokumen di folder Drive (`client_docs.py`); PDF hasil scan dibaca OCR (`tesseract`, bahasa ind+eng).
- **`site-finish`**: logo (+favicon bila persegi) & foto klien ke Media Library, galeri `[gallery]` di halaman Galeri, tagline (slogan form / AI), warna tema (Additional CSS dari "WARNA TEMA WEB"), tombol WhatsApp velocity-addons (dari "Kontak utk di web"), peta Google Maps di Hubungi Kami. Tidak menimpa pengaturan yang sudah diubah orang.
- **`site-qa`**: SSL valid untuk domain, gambar tidak 404, tanpa teks placeholder, menu Tentang Kami/Hubungi Kami ada, artikel tidak di Uncategorized.

Mode `finish` (`POST /api/installer/run` `{"domain":..., "mode":"finish"}`) menjalankan ulang konten + finishing + QA untuk situs yang sudah terpasang, tanpa install ulang dan tanpa notifikasi.

**Backup:** instalasi tidak membackup `public_html` yang masih kosong (isi bawaan DirectAdmin) atau WordPress hasil installer sendiri (apply ulang). Backup `/home/<user>/backup/pre-install-*.tar.gz` hanya dibuat kalau `public_html` berisi situs lain (bukan bawaan DirectAdmin, dan `wp-config.php` tidak memakai DB_NAME manifest). Backup lama dari instalasi sebelumnya tidak dihapus otomatis oleh installer.

Mode `maintenance` (`{"domain":..., "mode":"maintenance"}`) hanya menyalakan maintenance mode velocity-addons untuk situs yang terpasang sebelum langkah itu ada (sekali per situs, dilewati kalau sudah diatur manual).

Mode `child-theme` (`{"domain":..., "mode":"child-theme"}`) hanya memasang & mengaktifkan child theme untuk situs yang sudah terpasang — lihat [Paket G](#paket-g-child-theme-dibuat-otomatis-bernama-project).

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

### Paket G: child theme dibuat otomatis bernama project

Paket G tidak memilih template — desainnya custom per project, jadi form klien tidak pernah memuat referensi dan dulu situsnya berhenti di tema induk. Sekarang installer membuat child theme kosong sendiri (`paket=Paket G` di manifest memicunya; dibaca dari CRM saat manifest dibuat).

- Slug & folder: `velocity-<label domain>` (jasakontraktorindo.com → `velocity-jasakontraktorindo`), Theme Name "Velocity Jasakontraktorindo", `Template: velocity`, versi 1.0.0.
- Isinya scaffold minimal: `style.css` (header + catatan), `functions.php` (enqueue `parent-style` tema induk + `css/custom.css`), `css/custom.css` kosong, `screenshot.png`. Desain PHP/CSS-nya dikerjakan desainer — template yang perlu diubah disalin sendiri dari tema induk.
- Zip disimpan di `/var/lib/velocity/packages/child-themes/<slug>-1.0.0.zip` (isinya deterministik, jadi generate ulang tidak mengubah apa pun).
- **Tidak pernah ditimpa.** Apply ulang hanya mengaktifkannya (`child_theme_kept:<slug>`) kalau folder temanya sudah ada di server — `install_from_zip` menghapus folder tujuan sebelum menyalin, jadi tanpa pengaman ini hasil kerja desainer hilang.
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

Mode ini hanya memasang + mengaktifkan child theme (`scripts/child-theme-apply`) — tanpa install ulang, tanpa konten AI, tanpa notifikasi, dan tanpa mengubah status instalasi di `<domain>.json`.

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

## Ambil alih (klaim)

CRM belum punya API tulis, jadi klaim dicatat lokal di `/var/lib/velocity/installer/claims.json` — status di CRM tetap "Belum dikerjakan". Domain yang diklaim tidak lagi tampil sebagai `belum diambil`.

- `POST /api/installer/claim` — body `{"domain":"example.com","by":"manual"|"autopilot"}`. Idempoten.
- `POST /api/installer/release` — body `{"domain":"example.com"}`.
- Halaman installer: menu **Ambil alih** / **Lepas klaim**, badge `DIAMBIL: MANUAL|AUTOPILOT`.

## Autopilot (`scripts/installer-autopilot`)

`installer-autopilot.timer` tiap 10 menit. Satu putaran:

1. Domain yang sedang dipegang autopilot dilanjutkan: dry-run OK + `site=empty` → apply. Dry-run gagal, situs sudah berisi (`site=wordpress|not_empty`), atau run macet >2 jam → fase `manual` (tanpa notifikasi untuk tahap dry-run; apply yang gagal tetap dilaporkan).
2. Kalau tidak ada run berjalan, ambil **satu** project `belum diambil` yang lolos saringan (deadline terdekat dulu): klaim → generate manifest → dry-run.

Saringan: folder Drive sudah tersinkron, jenis `Pembuatan`/`Pembuatan apk biasa`/`Pembuatan Tanpa Domain` (Redesign tidak), deadline belum terlewat, FORM ISIAN klien terbaca, belum pernah ditangani autopilot.

Mode di `/etc/velocity/installer-autopilot.env`: `AUTOPILOT_MODE=observe` (default — hanya mencatat rencana ke `/var/lib/velocity/installer/autopilot-last.json` + journald) atau `AUTOPILOT_MODE=active`. Jejak per domain: `/var/lib/velocity/installer/autopilot.json`.

## Sync Google Drive (`scripts/onprogress-sync`)

`onprogress-sync-queue.timer` — tiap 10 menit, hanya folder domain berstatus `belum diambil` yang deadline-nya belum terlewat. Tidak ada sync penuh: Drive berisi ±10 ribu folder yang tidak dibutuhkan installer.

Selalu `rclone copy` (tidak pernah menghapus file lokal).

## Pasang unit systemd

```bash
install -m 644 config/onprogress-sync@.service config/onprogress-sync-queue.timer \
  config/installer-autopilot.service config/installer-autopilot.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now onprogress-sync-queue.timer installer-autopilot.timer
```
