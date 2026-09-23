## Situs ini TOKO ONLINE dengan plugin VD Store (wajib dipatuhi)

Semua data toko milik VD Store (acuan lengkap: `docs/vd-store.md` di repo installer):

- Produk = post type `store_product`, kategori = taksonomi `store_product_cat`, merek = `brand`.
  Arsip produk = `/produk/`, kategori = `/kategori-produk/<slug>/`. **Jangan** membuat atau memakai
  post type lain untuk produk (`product`, `produk`, CPT buatan sendiri), jangan Query Loop
  `postType: product`, dan jangan membuat halaman ber-slug `produk` (arsip VD Store pindah ke
  `/produk-list/` bila halaman itu ada).
- Tampilkan produk/kategori hanya lewat shortcode VD Store dalam blok `core/shortcode`:
  `[wp_store_shop per_page="8"]` (grid produk), `[wp_store_products_carousel per_row="4"]` (slider),
  `[wp_store_taxonomies_carousel columns="4" rows="1"]` (ubin kategori), `[wp_store_catalog]`,
  `[wp_store_categories]`. Tombol "Lihat Semua Produk" menaut ke `/produk/`.
- Kartu produk statis (gambar + judul ditulis tangan di HTML) bukan katalog: tidak punya harga,
  keranjang, maupun checkout. Seksi produk dari generator yang sudah memakai shortcode VD Store
  DIPERTAHANKAN. Toko belum berisi produk → shortcode tetap dipasang (produk ditambah pemilik di
  wp-admin → Produk); jangan menggantinya dengan kartu layanan/galeri berlabel "Produk".
- Halaman toko (Katalog, Keranjang, Checkout, Profil Saya, Terima Kasih, Tracking Order, Cek Ongkir)
  dibuat VD Store dan berisi shortcode-nya — jangan ditulis ulang. Ikon keranjang & akun di header
  disediakan tema.
