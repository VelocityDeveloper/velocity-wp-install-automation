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
