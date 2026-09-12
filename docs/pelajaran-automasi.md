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
