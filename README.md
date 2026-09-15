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
- `POST /api/installer/run` — body `{"domain":"example.com","mode":"dry-run"|"apply"|"finish"|"maintenance"|"child-theme"|"audit"}`. Validasi domain + manifest, tolak `already_running`, spawn `scripts/installer-runner` detached (log ke `/var/lib/velocity/installer/<domain>.log`). Browser pakai endpoint ini untuk tombol install/retry. Saat `apply`, service menyetel `WP_INSTALL_SSH_KEY_FILE` (auto-detect `/etc/velocity/secrets/ssh_key` atau `/root/.ssh/id_ed25519`/`id_rsa`) + `WP_INSTALL_DB_PASSWORD_FILE`/`WP_INSTALL_ADMIN_PASSWORD_FILE` per-domain dari `/etc/velocity/secrets/`.
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
- **Bagan proses** (panel "Proses berjalan" di atas filter + aksi "Bagan proses" per domain): simpul tiap langkah `installer-runner` (validasi, install WordPress, cek HTTP, VD Store, tema FSE, konten AI, finishing, bersih-bersih, foto slot, halaman blok, foto artikel, cek visual, QA, maintenance, selesai) dengan status menunggu/berjalan/selesai/gagal/dilewati dan durasi, dibaca dari penanda log run terakhir (mulai `RUNNING: VALIDATING`). Domain berstatus RUNNING dipantau tiap 3 detik lewat `GET /api/installer?domain=<domain>` (satu baris, log 1500 baris, tetap bisa dibaca setelah domain terpasang dan hilang dari antrean); kartu yang selesai bertahan 10 menit. Menambah langkah di runner = menambah satu entri di `ALUR` pada halaman ini.

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

`installer-runner` (mode `apply`): install WordPress → cek HTTP → konten AI (`ai-content-generator.py`) → finishing (`site-finish`) → hapus tema & plugin bawaan yang tidak dipakai (`site-finish --cleanup`) → [alur Paket G](#alur-paket-g-baku) bila `paket=Paket G` → pemeriksaan akhir (`site-qa`) → maintenance mode (`site-finish --maintenance`) → laporan Telegram ✅ selesai, atau 🟡 "perlu dicek" beserta daftar masalah.

- **Pembersihan** hanya pada run yang memasang WordPress dari awal (bukan apply ulang situs lama, bukan mode finish/maintenance): tema `twenty*` dan plugin `akismet`/`hello` yang tidak aktif. Tema aktif dan induknya tidak pernah dihapus; tema/plugin non-bawaan tidak disentuh.

- **Maintenance mode** (plugin velocity-addons, opsi `maintenance_mode` + `maintenance_mode_data`) dinyalakan sebagai langkah terakhir, sesudah pemeriksaan akhir (yang membaca situs sebagai pengunjung). Hanya sekali per situs (penanda opsi `velocity_installer_maintenance`) dan tidak kalau opsinya sudah pernah diatur orang, jadi apply ulang setelah PM mematikannya saat serah terima tidak menyalakannya lagi. `site-qa` mengenali halaman perawatan dan melewati pemeriksaan berbasis beranda.
- **Akun DirectAdmin selalu dibuat manual oleh PM.** Kalau dry-run autopilot gagal karena akun/folder domain belum ada, domain masuk fase `waiting_da`: dry-run diulang tiap 30 menit (maks. 14 hari) tanpa notifikasi, lalu instalasi berlanjut otomatis begitu akun dibuat.
- **Tahap dry-run tidak dilaporkan ke Telegram** (diambil alih, dry-run gagal/macet, situs sudah berisi, menunggu akun DirectAdmin). Statusnya terlihat di jurnal `/var/lib/velocity/installer/autopilot.json` dan halaman installer. Telegram hanya untuk hasil apply: selesai, perlu dicek, atau gagal.

- **Konten AI** dibersihkan `content_sanitize.py` (tanpa `<img>`/`<iframe>`/`<form>`/placeholder). Halaman tulisan installer ditandai meta `_velocity_content_md5`; apply ulang hanya menimpa halaman yang belum disunting orang. Konten tersimpan di `/var/lib/velocity/ai/generated/` dipakai ulang.
- **Bahan AI**: isi FORM ISIAN + dokumen di folder Drive (`client_docs.py`); PDF hasil scan dibaca OCR (`tesseract`, bahasa ind+eng).
- **`site-finish`**: logo (+favicon, lihat "Favicon") & foto klien ke Media Library, galeri `[gallery]` di halaman Galeri, tagline (slogan form / AI), warna tema (Additional CSS dari "WARNA TEMA WEB"), tombol WhatsApp velocity-addons (dari "Kontak utk di web"), peta Google Maps di Hubungi Kami. Tidak menimpa pengaturan yang sudah diubah orang.
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

### Paket G: child theme dibuat otomatis bernama project (TIDAK DIPAKAI LAGI)

> **Sejak 2026-09-15 paket custom (Paket G & Portal Berita Custom) hanya FSE** — keputusan user "kedepan pakai FSE saja". Installer tidak lagi merender child theme ataupun memasang tema induk `velocity` untuk paket ini (log `child_theme:skipped_fse::`, `tema_induk_dilewati:fse`); lihat [Tema FSE](#tema-fse-untuk-desain-custom-scriptsfse-apply-templatestema-fse). Bagian ini tinggal sebagai catatan situs lama yang child theme klasiknya masih aktif (jasakontraktorindo.com, ptmitraajegselaras.com) — installer melewatinya sampai manifest diberi `tema_desain=fse`. Pencocokan child theme dari API di atas tetap berlaku untuk paket lain.

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
- menyimpan hasilnya di `/var/lib/velocity/fse-rencana/<domain>/referensi.json` (tidak diulang tiap run) dan menulis `gaya`, `referensi`, `font_teks`, `font_judul` ke opsi `velocity_situs`,
- `paket-g-cek-visual` ikut memotret halaman referensi (`referensi-beranda-*.png`) di folder yang sama dengan hasil — **bandingkan keduanya sebelum melapor selesai**.

Gaya yang ada: `klasik` (portal padat + kolom samping) dan `sorotan` (majalah foto: pita judul berikon, kartu foto selebar layar berjudul serif, grid 2 kolom per rubrik, header putih, pita kaki hitam — dari referensi anaksegalabangsa.com, ourgrandfatherstory.com). Font referensi dipakai kalau dibawa tema (`FONT_LOKAL`: Plus Jakarta Sans, Montserrat, PT Serif). Referensi yang tata letaknya tidak cocok dengan gaya mana pun perlu gaya baru di `templates/tema-fse/style.css` + builder di `fse-apply`.

**Email & ikon media sosial wajib** (aturan user 2026-09-14, semua build): footer (`parts/footer.html`) dan halaman Hubungi Kami memuat blok `velocity/kontak` (email publik klien sebagai mailto) dan `core/social-links` ikon saja — Facebook, Instagram, X, YouTube, TikTok dengan tautan bawaan ke beranda platform (PM menggantinya dengan akun klien). Email biodata pemilik tidak pernah ditampilkan otomatis; kalau klien tidak memberi email publik, tanyakan dulu ke user.

Belum ada di jalur FSE (masih milik child Paket G): susunan beranda mengikuti urutan halaman company profile (`inc/compro.php`) dan foto contoh per slot desain perusahaan (`paket-g-foto` hanya dipakai untuk foto utama artikel).

## Alur Paket G baku

Disepakati user 2026-09-13 dari uji ptmitraajegselaras.com ("project paket G nanti seperti itu alurnya"). Di `installer-runner` terbagi dua fungsi: `paket_g_tema` (langkah 1–3, sebelum konten AI) dan `paket_g_isi` (langkah 4–7, sesudah `site-finish`), dipakai mode `apply`, `finish`, dan `child-theme` (yang juga menjalankan generator artikel di antaranya). Berlaku untuk Paket G dan Paket Portal Berita Custom:

| # | Langkah | Hasil |
|---|---|---|
| 1 | `compro-klien <domain>` | Company profile PDF → susunan bagian, prakata, warna, latar, logo, foto (`/var/lib/velocity/compro/<domain>/`). Tanpa PDF: dilewati |
| 2 | `paket-g-konten <manifest>` | Isi contoh dari form + dokumen; disesuaikan dengan compro (layanan tertulis, slogan, prakata, motto) |
| 3 | `fse-apply --tema <manifest>` | Pasang/aktifkan velocity-fse, data situs, palet, rubrik (sebelum konten AI) |
| 4 | `fse-apply --isi <manifest>` | Halaman berupa blok + menu `wp_navigation` (harus sesudah `site-finish`) |
| 5 | `paket-g-foto <manifest>` | Hanya portal berita: foto utama artikel |
| 6 | `paket-g-cek-visual <manifest>` | Screenshot desktop & HP ke `/var/lib/velocity/visual/<domain>/<waktu>/` + cek HTTP/layar kosong; `site-audit` membaca temuannya |

Sejak 2026-09-15 langkah 3–4 hanya FSE. Langkah lama jalur child (`child-theme-apply --perbarui`, `paket-g-foto` per slot, `paket-g-setup`, `site-finish --widget`) tidak dipanggil lagi untuk paket custom.

Semua langkah boleh gagal tanpa menggagalkan instalasi (kecuali pemasangan tema di mode `child-theme`). Hasilnya tetap dilihat manusia/Claude lewat screenshot sebelum dilaporkan selesai — kesalahan tampilan tidak terlihat dari HTML. Audit terkait: `tema_belum_mengikuti_compro`, `tombol_whatsapp_tanpa_nomor`, `visual:<temuan>`.

## Portal Berita Custom = desain custom (varian berita)

Keputusan user 2026-09-14: "paket G = paket custom design, untuk portal berita custom juga sama dengan paket G". `Paket Portal Berita Custom` kini dikenali sebagai paket desain custom di `installer-runner`, `website-install-from-manifest`, `velocity-child-theme`, dan `site-audit`, dan menjalankan alur yang sama — tetapi hasilnya **portal berita**, bukan web company profile.

- **Isi** (`paket-g-konten`, `jenis=berita`): rubrik dibaca kode dari susunan menu FORM ISIAN (isian bernilai "berisi berita-berita …"); warna dari gambar contoh warna klien — kode hex hasil OCR, atau warna dominan gambar yang dipotret Chromium headless (server tanpa pengurai JPEG); AI hanya menulis nama tampil (huruf & urutan harus sama dengan nama di form), slogan, tentang, dan pedoman redaksi. Tidak mengarang nama awak redaksi, badan hukum, nomor verifikasi, atau jumlah pembaca.
- **Tema** (`inc/berita.php`, `single.php`, `archive.php`, `home.php`; body class `<prefix>--berita`): topbar tanggal + slogan, beranda berita utama + terbaru + blok per rubrik dengan kolom samping (terpopuler, rubrik, tentang), arsip & indeks berita, halaman artikel dengan berita terkait, `[<prefix>_redaksi]`, dan form "Kirim Pesan ke Redaksi". Situs non-berita tetap memakai single/archive/index tema induk.
- **Artikel** (`ai-content-generator.py`): kategori = rubrik tema; `articles_per_rubrik` (bawaan 3) artikel per rubrik bergaya **tulisan informatif, bukan laporan peristiwa** — tanpa kejadian, nama orang, kutipan, angka, atau tanggal karangan. Artikel tersimpan yang kategorinya tidak cocok dengan situs dibuat ulang; artikel contoh lama dihapus hanya bila belum pernah disunting.
- **Foto** (`paket-g-foto`): foto utama tiap artikel tanpa thumbnail dari Openverse (CC0/PDM), kata kunci per artikel dari AI dengan cadangan per rubrik.
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

Keputusan user 2026-09-14, berlaku untuk semua paket (tema klasik, child theme, maupun FSE). Situs belum boleh dilaporkan selesai sebelum keempatnya terpenuhi.

1. **Favicon wajib ada.** `site-finish` memasangnya: logo klien kalau ada, ikon logo contoh kalau tidak (bagian [Favicon](#favicon) dan [Logo contoh](#logo-contoh-scriptsvelocity-logo)). Situs FSE yang temanya dipasang manual juga wajib diperiksa. Audit: `favicon_belum_terpasang`.
2. **Halaman kebijakan privasi (Privacy Policy) wajib ada dan terbit.** `website-install-from-manifest` membuat halaman "Kebijakan Privasi" berstatus publish dan menetapkannya sebagai `wp_page_for_privacy_policy` (Pengaturan → Privasi). Draft "Privacy Policy" bawaan WordPress tidak dihitung. Audit: `halaman_privasi_tidak_ada` / `halaman_privasi_belum_terbit:<status>`.
3. **Tampilan desktop dan mobile wajib rapi, terutama padding dan margin.** Periksa lewat screenshot di lebar desktop (1366px) dan HP (390px), jangan hanya HTTP 200. `paket-g-cek-visual` sudah memotret keduanya. Daftar periksa dan contoh kasus nyata ada di [`docs/pelajaran-automasi.md`](docs/pelajaran-automasi.md#kerapian-padding--margin-desktop-dan-mobile).
4. **Featured image (foto utama) setiap post wajib punya caption.** Caption = kolom *Keterangan* attachment (`post_excerpt`, dibaca `wp_get_attachment_caption()`), dan **wajib tampil** di halaman artikel di bawah foto. Isinya harus benar: keterangan dari klien, atau sumber/kredit foto contoh (mis. judul & pembuat dari Openverse). Jangan mengarang peristiwa, nama orang, atau lokasi. Keadaan saat ini (2026-09-14): `paket-g-foto` memasang foto utama lewat `wp media import --featured_image` **tanpa** caption, `templates/child-theme-paket-g/single.php` hanya `the_post_thumbnail()`, dan blok `core/post-featured-image` di tema FSE tidak mencetak caption. Ketiganya perlu disesuaikan. Audit: `foto_utama_tanpa_caption:<jumlah>`.

## Favicon

**Kalau klien punya logo, favicon selalu logo klien** (keputusan 2026-09-14, berlaku untuk semua paket). Logo klien = gambar bernama `logo*` di folder klien, atau logo yang dipotong `compro-klien` dari company profile.

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

Audit tidak mengubah apa pun — status instalasi di `<domain>.json` dan notifikasi Telegram tidak disentuh.

Temuan `maintenance_mati_setelah_dinyalakan_installer` sengaja ada: pernah terjadi maintenance mode mati sendiri sehingga situs yang belum diserahkan sempat terbuka untuk umum, dan `site-finish --maintenance` tidak akan menyalakannya lagi (penanda `velocity_installer_maintenance` sudah ada). Pemulihannya manual: `wp option update maintenance_mode 1`.

Pelajaran lain dari pembangunan alur ini dicatat di [`docs/pelajaran-automasi.md`](docs/pelajaran-automasi.md) — baca sebelum menambah langkah otomatis baru. Khusus soal palet warna dan keterbacaan: [`docs/warna-dan-kontras.md`](docs/warna-dan-kontras.md), dengan penjaganya `scripts/cek-warna-tema` (ikut dijalankan `deploy.sh`).

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

## Autopilot (`scripts/installer-autopilot`)

`installer-autopilot.timer` tiap 10 menit. Satu putaran:

1. Domain yang sedang dipegang autopilot dilanjutkan: dry-run OK + `site=empty` → apply. Dry-run gagal, situs sudah berisi (`site=wordpress|not_empty`), atau run macet >2 jam → fase `manual` (tanpa notifikasi untuk tahap dry-run; apply yang gagal tetap dilaporkan).
2. Kalau tidak ada run berjalan, ambil **satu** project `belum diambil` yang lolos saringan: klaim → generate manifest → dry-run.

Saringan: folder Drive sudah tersinkron, jenis `Pembuatan`/`Pembuatan apk biasa`/`Pembuatan Tanpa Domain` (Redesign tidak), FORM ISIAN klien terbaca, belum pernah ditangani autopilot, dan aturan deadline sesuai `AUTOPILOT_PRIORITAS`:

- `terlama` (bawaan, keputusan user 2026-09-13): hanya project yang deadline-nya **sudah lewat** (minimal `AUTOPILOT_MIN_TELAT_DAYS`, bawaan 1 hari), yang paling lama lewat diambil dulu. Project yang deadline-nya belum lewat sedang dikerjakan manual oleh webmaster selama masa uji coba, jadi dilewati (`deadline_belum_lewat_dikerjakan_webmaster`). Saat diterapkan kandidat berubah dari 0 menjadi 12.
- `terdekat` (perilaku lama): deadline terdekat dulu; yang lewat lebih dari `AUTOPILOT_DEADLINE_GRACE_DAYS` (10) hari dilewati.

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
