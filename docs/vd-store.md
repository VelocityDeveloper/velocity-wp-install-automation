# VD Store — acuan instalasi toko online

Semua paket toko online (Toko Online Custom maupun biasa) memakai plugin **VD Store** buatan
Velocity Developer (`scripts/vd-store`, sumber: API plugin Velocity, slug `vd-store`). Sebelum
menambah fitur produk/katalog di tema, generator, atau agen desain, ikuti data milik plugin ini —
jangan membuat struktur produk sendiri. Dibaca dari VD Store 1.4.12 (2026-09-23).

## Data milik VD Store

| Hal | Nilai |
|---|---|
| Produk | post type `store_product` (menu wp-admin "Produk" di bawah menu VD Store) |
| Kategori | taksonomi `store_product_cat`, hierarkis, URL `/kategori-produk/<slug>/` |
| Merek | taksonomi `brand`, URL `/brand/<slug>/` |
| Pesanan / kupon | `store_order`, `store_coupon` (tidak publik) |
| Arsip produk | `/produk/` — pindah ke `/produk-list/` bila ada **halaman** ber-slug `produk` |
| Meta produk | `_store_price`, `_store_sale_price`, `_store_flashsale_until`, `_store_stock`, `_store_sku`, `_store_weight_kg`, `_store_min_order`, `_store_product_type`, `_store_label`, `_store_gallery_ids`, `_store_options`, `_store_advanced_options` |
| Pengaturan | opsi `wp_store_settings` (diisi `scripts/vd-store-settings`) |
| Konstanta | `WP_STORE_VERSION` terdefinisi bila plugin aktif |

Template arsip/single/taksonomi dirender plugin (`template_include`); tema bisa menimpanya lewat
`<tema>/vd-store/<template>.php`. Tema FSE velocity-fse merender halaman ber-shortcode VD Store
lewat jalur klasik (`inc/vd-store/halaman-toko.php`) karena wptexturize tema blok merusak atribut
Alpine.

## Cakupan (keputusan user 2026-09-23)

Aturan ini dipakai installer hanya untuk **Paket Toko Online Custom yang memakai VD Store** (bukan
WooCommerce) — satu-satunya paket toko di jalur FSE (`paket_desain_custom` di `installer-runner`,
`toko_custom()` di `fse-apply`, flag `vd_store` di bahan agen desain Claude). Toko Online biasa
untuk saat ini tidak memakai jalur ini (tetap child theme klasik). Situs yang sudah terpasang tidak
diperbarui otomatis.

## Toko Online biasa (keputusan user 2026-09-23)

Alur installer paket Toko Online **biasa** (child theme klasik, bukan FSE), `scripts/toko-biasa`:

1. VD Store dipasang + pengaturan + halaman toko digenerate (`vd-store`, `vd-store-settings`).
2. `toko-biasa --menu`: menu utama = Beranda, Produk (arsip `store_product`), Pricelist, Keranjang,
   Cek Ongkir, Tracking Order, Berita. Halaman Pricelist dibuat bila belum ada (template
   `page-pricelist.php` bila tema punya, selain itu `[wp_store_catalog]`). Menu yang sudah disunting
   orang dibiarkan; `theme-paket-biasa` tidak lagi menyisipkan "Layanan" ke menu toko.
3. Konten AI, lalu `site-finish`: logo dari kiriman klien. Gambar lepas berlatar polos (mis. JPEG
   "WhatsApp Image ...") dipastikan Claude (`scripts/claude_vision.py`) sebagai logo; tidak ada logo
   = logo contoh. Folder produk tidak ikut dicari sebagai logo, dan logo tidak ikut jadi foto galeri.
4. `toko-biasa --produk`: folder berpola `produk`/`product` di folder klien → satu `store_product`
   per produk (subfolder = produk; nama berkas jelas = produk, harga dari nama berkas; foto bernama
   generik & dokumen daftar produk dikenali Claude, harga hanya bila tertulis). Gambar dikompres
   < 100 KB. Tanpa folder produk: 5 produk contoh ("Contoh – ...", meta `_velocity_contoh`) berfoto
   Pexels; produk contoh dihapus otomatis begitu produk asli diimpor.
5. Alur lama (bersih-bersih, tampilan klasik, foto artikel, QA, maintenance).

Situs yang sudah ter-deploy (log berisi `SUCCESS: COMPLETE`) dilewati langkah 2–4 dan aturan logo
baru; `toko-biasa --paksa` hanya dengan persetujuan user.

## VD Ongkir & asal pengiriman (keputusan user 2026-09-24)

Semua paket toko online (custom maupun biasa), sesudah VD Store terpasang, `scripts/vd-store-settings`:

- mengisi `wp_store_settings.rajaongkir_api_key` dengan kunci VD Ongkir dari
  `/etc/velocity/secrets/vd_ongkir_api_key` (base URL `https://ongkir.velocitydeveloper.co/api/v3`)
  — hanya bila masih kosong, kunci isian PM tidak ditimpa; log `ongkir_api_key:diisi`;
- mengisi asal pengiriman (`shipping_origin_province/city/subdistrict`): ID manifest
  `shipping_origin_*_id` bila ada, selain itu dicari lewat API dari isian form "asal pengiriman"
  (cadangan: alamat toko). Pencocokan per kata utuh provinsi → kota → kecamatan; kecamatan tak disebut
  → perkiraan (kecamatan bernama kota / pertama, log `origin:perkiraan`). Asal yang sudah terisi tidak
  ditimpa. Log: `origin:api_lookup:<kec> / <kota> / <prov>`, `origin:tidak_ditemukan:<teks>`.

## Menampilkan produk

Selalu lewat shortcode VD Store (blok `core/shortcode`):

- `[wp_store_shop per_page="8"]` — grid produk berharga + tombol keranjang
- `[wp_store_products_carousel per_row="4" per_page="10"]` — slider produk
- `[wp_store_taxonomies_carousel columns="4" rows="1"]` — ubin kategori (`store_product_cat`)
- `[wp_store_catalog]`, `[wp_store_categories]` — katalog / daftar kategori
- halaman toko dibuat `SettingsController::generate_pages()`: Katalog, Cek Ongkir, Profil Saya,
  Keranjang, Checkout, Terima Kasih, Tracking Order

Menu "Produk" = arsip `/produk/` dengan submenu `store_product_cat` (`menu_produk()` di
`scripts/fse-apply`).

## Yang tidak boleh

- Mendaftarkan CPT produk lain (`product`, `produk`, dsb.) atau taksonominya. Tema velocity-fse
  kini melewati CPT `product` dan `produk` selama `WP_STORE_VERSION` terdefinisi (kecuali CPT
  `product` yang sudah terlanjur berisi, supaya datanya tidak hilang dari wp-admin).
- Query Loop `postType: product` / kartu produk statis tulisan tangan di situs toko: tidak berharga,
  tidak bisa masuk keranjang, dan pemilik situs melihat dua menu "Produk".
- Membuat halaman ber-slug `produk` (menggeser arsip VD Store).
- Manifest `cpt_produk=1` diabaikan untuk paket toko (`fse-apply` mencetak `cpt_produk dilewati`).

Kasus asal: kopibalidewiseri.com (Toko Online Custom, 2026-09-23) mendapat CPT `product` dari tema
di samping `store_product`, sehingga wp-admin punya dua menu "Produk".
