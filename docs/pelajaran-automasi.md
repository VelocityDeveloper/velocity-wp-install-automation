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

## Contoh boleh, mengarang tidak — dan penjagaannya harus di kode

Situs Paket G selalu diberi isi dan foto contoh, tetapi tiga pelajaran dari uji
pada form klien sungguhan:

1. **Aturan di prompt dilanggar AI secara konsisten.** Isian "WARNA TEMA WEB"
   yang dibiarkan klien berisi teks template "Misal: … biru dan hijau", dan AI
   memberi warna biru + hijau dua kali berturut-turut meski dilarang. AI juga
   menempelkan label "CONTOH:" di teks yang akan dibaca pengunjung. Keduanya
   kini dibuang oleh kode setelah jawaban AI diterima.
2. **Bagian biodata pemilik bukan kontak publik.** WhatsApp dan email di sana
   berlabel "untuk pemberitahuan perpanjangan". Versi pertama generator tema
   memakainya sebagai kontak situs — pelanggaran aturan yang sudah ada. Hanya
   jasakontraktorindo.com yang punya "Kontak utk di web"; tiga form Paket G lain
   yang diuji tidak punya, sehingga masalahnya tidak kelihatan di situs contoh.
   Isian "0812… / 0821…" juga dulu digabung digitnya menjadi nomor rusak.
3. **Metadata bank foto berisik.** Pencocokan kata di judul/tag meloloskan
   "Jumbo Rocks Campground" untuk pabrik jumbo bag, sedangkan saringan yang
   diperketat membuat 13 dari 16 slot kosong. Yang berhasil: kolam frasa visual
   umum sektor usaha + model bahasa yang memilih kandidat.

Pelajaran umumnya: menguji di satu situs contoh tidak cukup — jalankan generator
pada beberapa form klien yang masih antre sebelum alurnya dianggap jadi.

## Isi situs mengikuti layanan klien, bukan daftar bawaan

Artikel AI dulu semuanya masuk satu kategori `Blog`. Isinya tidak salah, tapi
situsnya jadi tidak punya struktur: pengunjung yang mencari "renovasi" tidak
bisa menelusuri tulisan tentang renovasi saja.

Kategori kini diambil dari layanan yang benar-benar terpasang di child theme
situs (`<prefix>_data('layanan')` dibaca lewat WP-CLI), dan artikel dibuat per
kategori — bawaannya 2 artikel per layanan, diatur lewat `articles_per_category`
di manifest. Sama seperti pelajaran sebelumnya: sumber kebenarannya situs, bukan
tebakan dari sisi installer.

Dua hal yang membuat artikel "ada tapi tidak terlihat":

1. **Halaman Berita bukan arsip artikel.** Installer membuatnya sebagai halaman
   biasa berisi satu kalimat pembuka, sehingga `/berita/` tampak kosong padahal
   artikelnya terbit — masing-masing hanya bisa ditemukan lewat arsip
   kategorinya. WordPress punya mekanismenya: halaman itu ditunjuk sebagai
   Posts page (`page_for_posts`), dan `site-finish` kini mengisinya sekali.
2. **Kategori tanpa batasan topik hanya label.** Versi pertama mengirim nama
   kategori ke AI sebagai field JSON belaka, hasilnya artikel umum yang
   kategorinya tidak nyambung — artikel interior masuk kategori "Bangun Baru".
   Sekarang judul + keterangan layanan dikirim sebagai syarat topik, dan tiap
   artikel diminta mengambil sudut pandang berbeda dari layanan yang sama.

`site-audit` menandai `artikel_tanpa_kategori_layanan` kalau artikel kembali
menumpuk di satu kategori umum, `kategori_layanan_tanpa_artikel` kalau ada
layanan yang kategorinya kosong, dan `arsip_artikel_belum_ditentukan` kalau
halaman arsipnya tidak pernah ditunjuk.

### Jangan menilai gambar dinamis seperti berkas statis

Captcha plugin dicetak sebagai `<img src="?vd_captcha_image&token=…">` — gambar
yang dilayani WordPress, bukan berkas di folder uploads. Saat maintenance mode
menyala, URL seperti itu dibalas 503, dan `site-qa` melaporkannya sebagai
"gambar rusak" padahal situsnya sehat. Pemeriksaan gambar kini melewati URL yang
punya query string; isinya memang berubah tiap muat dan tidak bisa dinilai
dengan cara yang sama seperti foto unggahan.

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

## Desain mengikuti company profile (compro) klien

Kalau klien mengirim PDF company profile, itulah referensi desain Paket G.
`scripts/compro-klien <domain>` membacanya jadi `/var/lib/velocity/compro/<domain>/`
(compro.json, logo.png, foto-NN.*); `paket-g-konten`, `velocity-child-theme`,
`site-finish`, dan `paket-g-foto` memakainya otomatis.

- **Warna merek dari piksel logo, bukan dari warna vektor halaman.** Percobaan
  pertama membaca warna isian SVG tiap halaman: hasilnya merah tua #910000 karena
  teks judul kuning dan foto ikut terhitung. Logo adalah sinyal merek paling
  bersih — warna lebih gelap jadi utama, rona lain yang cukup jauh jadi aksen.
  Penjaga kontras tetap boleh menggeser aksen (#eb1a22 → #d8181f untuk teks putih).
- **Laporan harus membaca nilai yang benar-benar dipakai.** `kontras=` sempat
  melaporkan warna bawaan (argumen mentah) padahal CSS sudah memakai warna logo;
  kini keduanya lewat `warna_tema()` yang sama.
- **Semua yang dikirim klien ditampilkan** (struktur/staf, customer, legalitas
  termasuk NPWP & rekening, visi/misi/target) — keputusan user. Data perusahaan
  **disalin**, tidak boleh dicontohkan AI; `saring_data_perusahaan` membuang
  isian yang tidak ada di dokumen. Pengecualian: biodata pemilik di FORM ISIAN
  ("untuk administrasi kami") tetap internal.
- **Template membawa teks bidang lain.** Judul seksi kontraktor ("Layanan
  Renovasi" dsb.) ikut ke situs packaging; kini judul seksi datang dari
  `judul_seksi` di tema.json dengan bawaan netral.
- **AI mengulang slogan sebagai moto** kalau judul MOTO di PDF kosong → moto yang
  sama dengan slogan dibuang, supaya kalimat tidak tampil dua kali.
- **Isi halaman buatan AI + seksi tema = tampil dobel.** Beranda kini hanya
  mencetak pembuka sebelum H2 pertama; Tentang Kami membuang bagian AI
  (Visi/Misi/Struktur/Pelanggan/Legalitas) hanya bila shortcode data
  perusahaannya benar-benar menghasilkan isi (`profil_dobel_dibuang`).

### Foto company profile

- Foto klien menggeser foto contoh Openverse; foto contoh yang tergeser dihapus
  otomatis bila tidak dirujuk konten/thumbnail/opsi.
- **Logo compro bukan foto.** Penanda `_velocity_source` logo sempat
  `compro-logo:` sehingga lolos saringan "bukan logo" dan dipasang jadi hero.
  Penanda logo harus berawalan `logo` (`logo-compro:`).
- **Hero butuh foto lanskap suasana** (rasio 1.3–2.2). Foto potret potongan
  produk berlatar hitam dan banner strip 3549x354 terpotong habis oleh cover.
- AI boleh melewati slot; aturan kata kunci/urutan tetap mengisi slot yang
  dilewati, dan foto compro yang sudah menempati slot tidak dibagikan lagi.
- `--coba` tidak membaca keadaan situs: semua slot tampak kosong, jadi hasilnya
  bukan gambaran run sungguhan.

## `php -l` lolos, situs tetap 500: fungsi yang hilang

2026-09-13 jasakontraktorindo.com sempat HTTP 500 beberapa menit. Template baru
memanggil `jki_judul()`, sedangkan `inc/theme-data.php` situs itu ditimpa dari
salinan build lama (demi mempertahankan isi khas kontraktornya) yang belum punya
helper tersebut. `php -l` hanya memeriksa sintaks per berkas, jadi lolos.

- Setiap render child theme kini dijaga `scripts/cek-fungsi-tema <folder> [prefix]`:
  semua fungsi berawalan tema yang dipanggil harus terdefinisi di salah satu berkas.
- Kalau mempertahankan theme-data.php milik situs saat template berubah, bawa
  juga helper baru dari template — isi (array data) boleh milik situs, fungsi
  milik template.
- Setelah deploy, cek HTTP beranda **dan** halaman lain: di sini hanya beranda
  yang 500 (front-page.php), halaman lain tetap 200.
- Salah satu upaya perbaikan hampir mengirim berkas rusak; yang menahannya
  adalah `php -l` di server + `set -e` sebelum menyalin. Pertahankan urutan itu.

## Layout mengikuti company profile, bukan hanya warnanya

Pertanyaan user 2026-09-13 "untuk layout apa sudah sesuai desain refrensi?" —
jawabannya belum: tema hanya diganti warna/isi, kerangkanya tetap landing page
umum. Perbandingan 19 halaman compro dengan screenshot situs menunjukkan pola
tetap compro (kepala halaman nama merah + subjudul, judul tengah bergaris bawah,
tab nomor, latar krem, pita kaki hitam bersudut merah) dan urutan bagiannya.

- `compro-klien` kini membaca **susunan** PDF: `seksi` berurutan (jenis, judul,
  foto per halaman), `prakata` + penanda tangan, `subjudul`, `alamat`, `email`,
  warna `latar` halaman, dan warna `sorot` desainer (biru muda, kuning).
- Tema: bila `seksi` ada, `inc/compro.php` menyusun beranda sesuai urutan itu
  (body class `<prefix>--compro`); situs tanpa compro tetap susunan bawaan.
- **Selalu cek hasil dengan screenshot** (Chromium Playwright headless +
  pemotong PNG murni Python di `compro-klien`) — tidak ada yang ketahuan dari
  HTML: foto sampul gelap, menu terlipat, gambar teknik di kartu layanan.

Jebakan yang ditemukan:
- **Judul halaman dua baris** ("TARGET PENCAPAIAN" / "PERUSAHAAN") digabung
  hanya bila titik tengahnya sejajar (±6 kolom); tanpa itu dua halaman "MARKING
  AREA & FINISH" / "MARKING AREA AND" tampak dua bagian berbeda.
- **Smask PDF punya tiga arti**: bentuk potongan produk (terapkan → PNG
  transparan; tanpa itu sudutnya hitam), opasitas (foto sampul semi-transparan —
  mask serba redup/seragam diabaikan), dan hiasan (panah merah: sedikit piksel
  tampak + satu rona dominan → dibuang).
- **Batas ukuran foto 400x300 terlalu besar**: foto karung sak (364x360) di
  halaman layanan terbuang dan panah hiasan dipasang di kartunya.
- **"produk" cocok dengan "Produksi"** — slot produk sempat terisi foto area
  produksi. Cocokkan kata utuh.
- **Layanan karangan AI** ("Packaging Industri") lolos pemeriksaan per kata;
  kini judul layanan harus tertulis sebagai frasa berurutan di compro.
- **Aksen sebagai teks**: merah di atas navy (menu aktif, label hero) lolos
  karena penjaga hanya menguji teks di atas latar berwarna. Kini ada token
  `--aksen-teks` / `--aksen-di-primary` / `--sorot-teks` yang dihitung generator
  dan diuji `cek-warna-tema`. Penguji kaskade tidak mengenal leluhur tag (`li`)
  — tulis selector dengan kelas.
- **Tombol WhatsApp tanpa nomor** jatuh ke `mailto:`; kini disembunyikan dan
  "Hubungi Kami" menuju halaman kontak.
- **Helper jangan di theme-data.php** (lihat bagian 500 di atas): semua fungsi
  gaya compro tinggal di `inc/compro.php` milik template.
- Slot foto bekas run lama (asal contoh/compro) yang tidak ada di rencana baru
  harus dikosongkan, bukan dibiarkan.

## Alur Paket G dibakukan (hasil uji ptmitraajegselaras.com)

User 2026-09-13: "ujicoba untuk project paket G nanti seperti itu alurnya".
Semua langkah yang tadinya dikerjakan tangan kini satu fungsi `paket_g_alur` di
`installer-runner`, dipakai mode `apply`, `finish`, dan `child-theme`:

1. `compro-klien` → 2. `paket-g-konten` → 3. `child-theme-apply --perbarui` →
4. `paket-g-foto` → 5. `paket-g-setup` → 6. `site-finish --widget` →
7. `paket-g-cek-visual`.

Yang harus diubah supaya langkah tangan bisa jadi otomatis:
- **Zip tema tidak boleh dari cache.** `velocity-child-theme` dulu memakai ulang
  zip lama selama berkasnya ada, sehingga perbaikan template tidak pernah sampai.
  Kini selalu dirender (deterministik, md5 sama bila isinya sama).
- **Tema terpasang diperbarui per berkas, bukan dilarang ditimpa.** Aturan lama
  "scaffold tidak pernah ditimpa" membuat situs tak pernah menerima perbaikan.
  Setiap tema kini membawa `.velocity-render.json` (sidik berkas render). Berkas
  yang masih sama dengan catatan → diganti; yang disunting → dipertahankan;
  gabungan PHP diuji `php -l` + `cek-fungsi-tema` sebelum dikirim, dan
  pembaruan DITAHAN kalau gagal (terbukti menahan render berawalan salah di
  jasakontraktorindo.com tanpa merusak situs). Tema lama tanpa catatan:
  theme-data.php dianggap milik situs.
- **Awalan dibaca dari tema terpasang** (`function <prefix>_data`), bukan ditebak
  dari domain — jebakan `jki` vs `jasa` terulang di langkah pembaruan tema.
- **compro.json bervers**i (`VERSI`); hasil tersimpan format lama dibaca ulang.
- **Cek visual** menyimpan screenshot di `/var/lib/velocity/visual/<domain>/`
  (5 run terakhir); `site-audit` membaca temuan terakhirnya, dan menandai
  `tema_belum_mengikuti_compro` serta `tombol_whatsapp_tanpa_nomor`.

## Portal Berita Custom ikut alur desain custom (anaksegalabangsa.com)

User 2026-09-14: "paket G = paket custom design, untuk portal berita custom juga
sama dengan paket G". Saya sempat menahan eksekusi karena CRM menulis paket lain —
yang benar: bedakan **alur** (sama: desain custom per project) dari **bentuk
situs** (company profile vs portal berita). Template tetap satu, variannya lewat
`jenis` di theme-data.

- **Contoh berita tidak boleh berupa laporan peristiwa karangan.** Portal berita
  yang menerbitkan kejadian, nama, atau kutipan fiktif = menyebar hoaks, walau
  "hanya contoh". Artikel contoh berupa tulisan informatif per rubrik.
- **Warna dari gambar contoh klien**: "orange mclaren dan maroon" + dua kartu
  warna. OCR tesseract membaca "#550000" hanya dengan `--psm 11 --dpi 300`, dan
  sama sekali tidak membaca tulisan kecil "#FF8000" di kartu orange. Server
  installer tidak punya PIL/ImageMagick/djpeg, dan ffmpeg bawaan Playwright tidak
  bisa membuka JPEG maupun PNG — Chromium headless memotret gambarnya ke PNG,
  lalu warna dominannya dibaca pembaca PNG murni Python (hasil #ff7f00).
- **Urutan tema vs generator artikel.** Generator membaca layanan/rubrik dari
  child theme yang TERPASANG. Pada instalasi baru tema sudah ada; pada situs lama
  tanpa child theme, generator jalan duluan dan artikelnya tetap "Blog". Alur
  dipecah `paket_g_tema` (sebelum konten AI) dan `paket_g_isi` (sesudah finishing).
- **Artikel tersimpan bisa basi**: `<domain>-articles.json` berkategori "Blog"
  dipakai ulang selamanya. Kini dibuat ulang bila tidak satu pun kategorinya ada di
  situs, dan artikel lama dihapus hanya bila `post_modified_gmt == post_date_gmt`.
- **Nama media menyambung** ("anaksegalabangsa") boleh ditampilkan berspasi dari
  AI hanya bila huruf & urutannya identik — nama klien tidak boleh berubah.

### Temuan uji akhir anaksegalabangsa.com

- **Biodata pemilik terbit lewat tulisan AI.** Halaman Hubungi Kami hasil instalasi
  11 September memuat "Alamat Media: Desa Kedanyang RT 4 RW 1" — alamat rumah dari
  bagian biodata FORM ISIAN — padahal prompt melarangnya, dan theme-data juga
  sempat menaruh alamat itu di footer. Kini dua lapis di kode: `data_klien` tidak
  memakai alamat biodata bila form punya bagian biodata, dan
  `buang_data_pemilik` di generator membuang paragraf/butir yang memuat alamat,
  nama, WhatsApp, atau email pemilik (beserta judulnya) sebelum terbit.
- **Peta dobel karena urutan.** `site-finish` menambah iframe peta ke Hubungi Kami
  karena blok `[<prefix>_kontak]` belum ada; sesudah `paket-g-setup` menambah blok
  itu, halaman punya dua peta dan ruang kosong besar. `paket-g-setup` kini membuang
  iframe `velocity-map` bila blok kontak tema sudah terpasang.
- **Foto contoh berisi orang/kutipan lolos saringan judul.** "ABOUT TESFAYE TSTAPP
  CANADA" (potret) dan poster kutipan "Labor automation…" terpasang sebagai foto
  artikel. Foto berita kini dipilih AI dari 8 kandidat dengan larangan potret,
  teks/kutipan, dan tokoh/peristiwa; AI boleh menolak semua lalu kata kunci
  cadangan dicoba.
- **Keluaran AI berkolom kosong disimpan diam-diam.** Tiga artikel Pendidikan
  bertitel & berisi kosong masuk `articles.json` dan tidak pernah terbit; rubrik
  Ekonomi gagal tanpa log. Kini artikel dinormalkan (judul/isi/ringkasan),
  yang kurang dari 120 kata dibuang, dicoba ulang, dan kategori yang masih kosong
  dilengkapi pada run berikutnya.
- **"Belum disunting" bukan soal tanggal.** Artikel contoh lama berbeda
  `post_modified` karena installer sendiri menerbitkannya ulang; yang benar
  membandingkan isi dengan versi generator (md5).

## Kerapian padding & margin desktop dan mobile

Keputusan user 2026-09-14: tampilan wajib rapi di desktop **dan** HP, terutama
padding dan margin. HTML valid dan HTTP 200 tidak membuktikan apa pun soal ini —
semua temuan di bawah hanya ketahuan dari screenshot. Periksa setiap halaman
utama di lebar 1366px dan 390px (Playwright, `scripts/potret-halaman`), lalu
lihat hasilnya sebelum melapor selesai.

Daftar periksa:
- **Gutter kiri-kanan** minimal ±16px di HP; teks, tombol, dan kartu tidak
  menempel ke tepi layar atau ke tepi kartunya sendiri.
- **Tidak ada scroll horizontal** (`document.documentElement.scrollWidth` ≤
  `clientWidth`). Pelakunya biasanya gambar/iframe ber-lebar tetap atau
  `min-width` yang lebih lebar dari layar.
- **Jarak antarseksi konsisten** — pakai preset spacing tema, bukan angka acak
  per seksi — dan tidak ada ruang kosong besar atau pita putih yang tak disengaja.
- **Kartu dalam satu baris seragam**: gambar satu rasio (`aspect-ratio` +
  `object-fit: cover`), isi kartu punya padding yang sama.
- **Elemen melayang** (tombol WhatsApp, scroll-to-top) tidak menutupi tombol,
  teks, atau baris hak cipta footer di HP.
- **Ornamen dekoratif** (lingkaran, pola) tidak menimpa teks di layar sempit.
- Judul besar tidak pecah jadi satu kata per baris di HP; kurangi ukurannya
  dengan `clamp()`.

Kasus nyata:
- **Pita putih 16px di atas footer** (layananhipnoterapi.com): `blockGap` di
  theme.json memberi `<footer>` margin atas. Tidak terlihat selama seksi di atasnya
  berupa kartu, langsung kelihatan begitu seksi itu dibuat penuh berlatar navy.
  Solusinya `.wp-site-blocks > footer.wp-block-template-part { margin-block-start: 0 }`.
- **Ornamen menimpa teks di HP** (seksi ajakan konsultasi yang sama): lingkaran
  hiasan 280px pas di desktop tapi melintasi paragraf di lebar 390px — dikecilkan
  lewat media query.
- **Ruang kosong besar karena peta dobel** (anaksegalabangsa.com, bagian di atas).
- **Kartu tidak seragam**: satu kartu lokasi berisi blok gradien sementara dua
  lainnya foto — diganti gambar dengan rasio yang sama.
