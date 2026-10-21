## Situs ini memakai plugin Velocity Donasi (wajib dipatuhi)

- Program donasi = post type `donasi` (kategori: taksonomi `kategori-donasi`), arsip `/donasi/`,
  detail `/donasi/<slug>/` (form donasi, tab kabar & donatur dari plugin). Halaman "Donasi Saya"
  (`/donasi-saya/`, shortcode `[halaman-donatur]`) = cek status invoice donatur — jangan ditulis ulang.
  **Jangan** membuat halaman ber-slug `donasi` (bentrok dengan arsip) atau post type lain untuk program.
- Seksi program donasi di beranda (bila referensi punya seksi program/campaign/donasi, atau situs ini
  yayasan/lembaga sosial) = `core/query` `{"query":{"postType":"donasi","perPage":3,"inherit":false}}`
  yang `core/post-template`-nya berisi SATU grup kosong ini (diganti kartu program oleh tema: foto,
  judul, progres terkumpul/target, tombol "Donasi Sekarang"):
  `<!-- wp:group {"className":"vf-donasi-kartu","layout":{"type":"default"}} --><div class="wp-block-group vf-donasi-kartu"></div><!-- /wp:group -->`
  Tombol "Lihat Semua Program" menaut ke `/donasi/`.
- Jangan memakai shortcode `[velocity-donasi-loop]`/`[velocity-progress-donasi]` di beranda (butuh
  Bootstrap dan di template blok semua kartu jadi program yang sama), dan jangan menulis kartu program
  statis — angka terkumpul harus dari plugin. Gaya kartu boleh disesuaikan lewat kelas
  `.vf-donasi-kartu`, `__foto`, `__judul`, `__progres`, `__angka`, `__tombol` di `gaya.css`.
- Program yang judulnya diawali "Contoh – " adalah CONTOH; tetap ditampilkan (diganti pemilik di
  wp-admin → Donasi).

