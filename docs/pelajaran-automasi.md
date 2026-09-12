# Pelajaran automasi installer

Catatan dari kejadian nyata saat membangun alur Paket G (situs contoh:
jasakontraktorindo.com). Semuanya pernah benar-benar menggigit — bukan teori.
Baca sebelum menambah langkah otomatis baru.

## Empat aturan untuk setiap langkah otomatis

1. **Idempoten.** Dijalankan dua kali hasilnya sama, tidak menggandakan apa pun.
2. **Menandai dirinya.** Simpan penanda di opsi WordPress (`velocity_*`) supaya
   langkah itu tahu ia sudah pernah jalan — dan supaya audit bisa membedakan
   hasil installer dari hasil kerja manusia.
3. **Tidak pernah menimpa kerja manusia.** Yang boleh ditimpa hanya yang
   ditandai sebagai buatan installer (contoh: logo contoh boleh tergeser logo
   asli; logo yang dipasang PM tidak pernah disentuh).
4. **Bisa diaudit.** Keadaan akhirnya harus bisa dibaca ulang belakangan —
   itulah gunanya `scripts/site-audit`.

## Jangan percaya "perintahnya jalan" — periksa hasilnya

Beberapa kegagalan paling mahal di sini semuanya **diam**: perintah selesai
tanpa error, tetapi tidak melakukan apa-apa.

- **`wp menu item list --field=db_id` tidak dikenal** di WP-CLI versi server ini
  (hanya `--fields`, jamak). Loop penghapusan jadi memproses teks error, item
  lama tidak pernah terhapus, dan menu diam-diam menumpuk jadi 15 item.
  Pakai `--fields=db_id --format=csv | tail -n +2`, lalu **hitung ulang** hasilnya.
- **Alias `cp -i` / `rm -i` di shell root.** Tanpa TTY, salinan dibatalkan diam-diam.
  Selalu `command cp -f` / `command rm -f`. (Ini sempat menimpa isi
  `theme-data.php` klien dengan isian awal template.)
- **`WP_Theme::get('Stylesheet')` selalu kosong** — 'Stylesheet' bukan header tema.
  Gunakan `get_stylesheet()`. Audit sempat melaporkan "child theme tanpa induk"
  padahal induknya ada.

Aturan turunannya: setiap langkah yang mengubah sesuatu harus diikuti pembacaan
ulang keadaan, dan angkanya dibandingkan dengan yang diharapkan.

## Nilai turunan jangan ditebak dua kali — baca dari sumbernya

Awalan fungsi & kelas child theme (`jki_`, `jasa_`, ...) dihitung generator dari
nama domain kalau tidak disebut. Tema jasakontraktorindo.com dibuat dengan
`--prefix jki`, tetapi `paket-g-setup` menghitung ulang sendiri dan mendapat
`jasa` — sehingga halaman Galeri dan Hubungi Kami terisi `[jasa_kontak]`,
`[jasa_galeri]`, `[jasa_pemesanan]`: shortcode tanpa fungsi, yang **tercetak apa
adanya ke pengunjung**.

Pelajarannya: kalau sebuah nilai bisa dihitung di dua tempat, dua tempat itu
cepat atau lambat akan berbeda. Sekarang `paket-g-setup` dan `site-audit`
menanyakannya ke situs (shortcode `*_pemesanan` yang benar-benar terdaftar,
tipe post `*_pemesanan` yang benar-benar ada), dan tebakan generator hanya jadi
cadangan.

`site-audit` menandai `shortcode_tanpa_fungsi:<tag>@<halaman>`, dan
`paket-g-setup` membuang blok desain berawalan salah sebelum memasang yang
benar — jadi menjalankan ulang langkahnya sekaligus memperbaiki kerusakannya.

## Peta: alamat klien sering tidak dikenali

Iframe `google.com/maps?q=<alamat>` hanya berguna kalau alamatnya dikenali peta.
Alamat klien biasanya memuat nama gedung, lantai, singkatan jalan, dan kode pos
— dan gabungan itu sering tidak ketemu, sehingga yang tampil peta kosong.

`scripts/velocity-map` mencari titiknya bertahap dan **selalu mengembalikan
koordinat**, jadi iframe-nya dijamin menampilkan sesuatu:

1. alamat lengkap → 2. kota/kabupaten → 3. provinsi → 4. titik tengah Indonesia

Selain kata kunci "Kota"/"Provinsi" (yang tidak selalu ada di alamat yang sudah
dirapikan manusia), pencarian juga dipersempit bertahap dengan membuang bagian
terdepan alamat — nama gedung dulu, lalu nama jalan — sampai tersisa wilayah
yang dikenali. Contoh nyata: "Sequis Center 9th Floor No. 902, Jl. Jend.
Sudirman No. 71, Jakarta Selatan, DKI Jakarta" tidak ketemu sebagai alamat, tapi
"Jakarta Selatan, DKI Jakarta" ketemu.

Hasilnya disimpan di opsi `velocity_map` dan dipakai tema. `site-audit`
menandai `peta_tidak_spesifik` kalau yang ketemu cuma titik Indonesia — peta
selebar negara tidak berguna untuk pengunjung, dan itu tanda alamat klien perlu
diperbaiki atau titiknya diisi manual.

Geocodernya Nominatim (OpenStreetMap): wajib User-Agent yang jelas, maksimal
satu permintaan per detik, dan hasilnya disimpan per domain agar pemasangan
ulang tidak menembak layanan itu berkali-kali.

## Urutan langkah itu bagian dari kebenaran

- `site-finish` menulis ulang halaman **Galeri** dan **Hubungi Kami** (galeri +
  peta). Kalau shortcode blok desain dipasang sebelum itu, isinya hilang. Karena
  itu `paket-g-setup` berjalan **sesudah** `site-finish`.
- Child theme harus aktif **sebelum** 1-Click Setup: lokasi menu disimpan per
  tema aktif.
- Maintenance mode dinyalakan **paling akhir**, sesudah QA — QA membaca situs
  sebagai pengunjung.

## Bash & shell

- `set -Eeuo pipefail` + `[[ kondisi ]] && var=1` **menghentikan skrip** saat
  kondisinya salah. Pakai `if ... then ... fi`.
- `install_from_zip` menghapus folder tujuan sebelum menyalin. Tema yang isinya
  hasil kerja desainer wajib dilindungi pemeriksaan "folder sudah ada".

## Pakai yang sudah ada di velocity-addons, jangan bikin ulang

Child theme sempat membuat tombol WhatsApp mengambang sendiri, padahal plugin
velocity-addons sudah punya. Hasilnya dua tombol menumpuk di sudut layar, dan
yang buatan tema tidak muncul di wp-admin sehingga PM tidak bisa mengubah nomor,
teks, atau posisinya.

Aturan: **sebelum menulis fitur di tema, periksa dulu apakah plugin sudah
menyediakannya.** Yang sudah ada di velocity-addons:

| Fitur | Cara pakai | Diisi installer |
|---|---|---|
| Tombol WhatsApp mengambang | Opsi `floating_whatsapp`, `nomor_whatsapp`, `nomor_whatsapp_contacts`, `whatsapp_text`, `whatsapp_message`, `whatsapp_position` | ya, `site-finish` dari "Kontak utk di web" |
| Tombol kembali ke atas | Opsi `scrolltotop_position` | — |
| Maintenance mode | Opsi `maintenance_mode` + `maintenance_mode_data` | ya, `site-finish --maintenance` |
| Galeri | Shortcode `[vdgallery]`, `[vdgalleryslide]` | — |
| Captcha | Shortcode `[velocity_captcha]` + `Velocity_Addons_Captcha::verify()`, opsi `captcha_velocity` | ya, `site-finish` menyalakan penyedia `image` |
| Statistik & hits | `[velocity-statistics]`, `[velocity-hits]` | — |
| Bagikan tulisan | `[velocity-sharepost]` | — |
| Breadcrumb | `[vd-breadcrumbs]` (tema induk juga mencetaknya lewat hook) | — |

`site-audit` menegakkan aturan ini: ia menandai `tombol_whatsapp_ganda` kalau
berkas tema mendaftarkan `wp_footer` yang memuat tautan `wa.me`. Komentar
dibuang dulu dengan `php_strip_whitespace` — versi pertama pemeriksaan ini
justru menuduh template sendiri gara-gara membaca komentar penjelasnya.

### Semua form pakai captcha velocity-addons

Form kiriman pengunjung (pemesanan, kontak) wajib memakai captcha plugin —
`[velocity_captcha]` untuk tampilannya dan `Velocity_Addons_Captcha::verify()`
untuk memeriksanya — bukan penyaring buatan sendiri. Plugin sudah menyediakan
dua penyedia (gambar dan Google reCAPTCHA), halaman pengaturannya di wp-admin,
dan verifikasinya. Honeypot, nonce, dan batas satu kiriman per menit tetap
dipasang sebagai lapisan tambahan, bukan pengganti.

Dua jebakan yang ditemukan saat menyambungkannya:

1. **Plugin memuat kelas captcha lewat `require_once` di dalam sebuah method**,
   sehingga `$captcha_handler` miliknya tidak pernah menjadi global. Memanggil
   `global $captcha_handler` hanya menghasilkan null — dan karena `verify()`
   tidak pernah terpanggil, form lolos tanpa captcha padahal tampak terlindungi.
   Jalan yang dipakai: `new Velocity_Addons_Captcha()` di dalam pemroses form.
2. **Opsi `captcha_velocity` tidak ada di situs baru**, dan tanpa opsi itu
   captcha mati diam-diam. `site-finish` kini menyalakannya sekali dengan
   penyedia `image` (jalan tanpa kunci); untuk Google reCAPTCHA, PM tinggal
   mengisi sitekey/secretkey lalu mengganti provider — opsinya tidak ditimpa lagi.

`site-audit` menandai `captcha_tidak_aktif`, `recaptcha_google_tanpa_kunci`
(plugin mematikan sendiri captcha Google tanpa kunci, jadi pengaturannya tampak
menyala padahal form tanpa penyaring), dan `form_tanpa_captcha` kalau berkas
tema memproses `$_POST` tanpa memanggil captcha plugin.

### Tulisan tombol WhatsApp = ajakan, bukan nama web

Untuk satu kontak, plugin mencetak **nama kontak** sebagai tulisan tombol
(`$contact['name'] ?: $whatsapp_text`). `site-finish` dulu mengisinya dengan
`site_title`, sehingga tombol mengambangnya berbunyi nama perusahaan — padahal
pengunjung sudah tahu sedang membuka situs siapa, dan tombol itu gunanya
mengajak menghubungi.

Sekarang nama kontak dan `whatsapp_text` sama-sama diisi label ajakan
(`WA_LABEL = 'Hubungi Kami'`; "Kontak Kami" atau "Konsultasi" sama baiknya).
Nama perusahaan tetap dipakai di `whatsapp_message` — itu kalimat yang dikirim
pengunjung, jadi memang perlu menyebut tujuannya.

`site-audit` menandai `tombol_whatsapp_bernama_situs` kalau labelnya kembali
menjadi nama situs atau nama domain. Perbandingannya men-decode entitas HTML
lebih dulu: `blogname` tersimpan sebagai "Jasa Kontraktor &amp; Interior ...",
dan tanpa decode pemeriksaannya diam-diam tidak pernah menyala.

## CSS: spesifisitas mengalahkan urutan

Aturan judul global `body.<prefix> h1..h4 { color: ink }` bernilai (0,1,2),
sedangkan aturan komponen `.<prefix>-hero__judul { color: putih }` hanya (0,1,0).
Yang global menang, jadi **semua judul di latar gelap tampil hitam** — termasuk
judul hero — dan menaruh aturan lebih akhir di berkas tidak menolong sama sekali.

Jebakan yang sama menggigit dua kali lagi: aturan global `body.<prefix> img
{ height: auto }` mengalahkan `.<prefix>-figure img { height: 100% }`, sehingga
foto tidak pernah mengisi kartunya dan menyisakan ruang kosong — `object-fit:
cover` tidak menolong karena tidak ada tinggi yang harus diisi.

Pelajarannya: "ada aturan warnanya di CSS" bukan bukti warnanya berlaku. Hitung
aturan mana yang benar-benar menang. `scripts/cek-warna-tema` melakukan itu
otomatis dan dipasang sebagai penjaga di `deploy.sh`. Rinciannya di
[warna-dan-kontras.md](warna-dan-kontras.md).

## Menguji tanpa merusak milik orang

- **Jangan pernah mengirim email uji ke alamat klien.** Cegat di `pre_wp_mail`,
  periksa isinya, lalu hapus arsip ujinya.
- Situs yang belum diserahkan tertutup maintenance mode. Untuk memeriksa
  tampilan, render template lewat `wp eval-file` di CLI — jangan mematikan
  maintenance, dan jangan membuat cookie login.
- Untuk menilai hasil visual (logo di header, kontras warna), susun SVG
  pembanding lalu rasterisasi dengan `rsvg-convert` dan lihat gambarnya.
  Tulisan gelap di header gelap baru ketahuan hilang lewat cara ini.

## Yang membuat QA tidak cukup, dan kenapa ada audit

`site-qa` memeriksa dari luar lewat HTTP/REST. Begitu maintenance mode menyala,
beranda yang terbaca adalah halaman perawatan — logo, menu, dan galeri otomatis
terbaca "tidak ada" padahal terpasang. QA juga berjalan **sebelum** maintenance
dinyalakan, jadi ia tidak bisa menjadi penjaga keadaan akhir.

`scripts/site-audit` mengisi celah itu: membaca dari **dalam** situs lewat
WP-CLI, jadi tetap akurat meski situs tertutup. Ia membandingkan yang dijanjikan
automation dengan yang benar-benar ada — tema, halaman, menu, form pemesanan,
logo/favicon (termasuk apakah masih logo contoh), widget, jumlah foto, sisa teks
contoh template, dan maintenance mode.

Temuan `maintenance_mati_setelah_dinyalakan_installer` sengaja ada: pernah
terjadi maintenance mode mati sendiri di tengah pengerjaan sehingga situs
sempat terbuka untuk umum, dan `site-finish --maintenance` **tidak** akan
menyalakannya lagi karena penanda `velocity_installer_maintenance` sudah ada.
Pemulihannya manual: `wp option update maintenance_mode 1`.

## Ukur dampaknya sebelum menyempitkan atau memperluas saringan

Sebelum mengubah aturan penyaringan apa pun, sajikan angka "sebelum vs sesudah"
ke user. Contoh: penopang membaca paket dari nama file form diperiksa dulu atas
22 folder antrean — 5 file bernama "paket g" (4 memang Paket G di CRM, 1
paketnya kosong), nol tabrakan dengan paket lain, dan hanya menambah 1 domain.
