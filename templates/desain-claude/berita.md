## Situs ini PORTAL BERITA (aturan tambahan)

Keputusan pemilik 2026-09-28: portal berita tidak lagi memakai gaya siap pakai (klasik/sorotan);
tata letaknya kamu susun sendiri mengikuti referensi, seperti situs perusahaan.

- **Beranda harus dinamis.** Berita di beranda selalu dari `vb/posts` (atur `layout`: overlay,
  slider, list, excerpt, grid, dll. — pilihan lengkap di `assets/editor.js`; `category`, `count`,
  `offset`, `orderBy` date/popular, `columns*`, `imageHeight`, `titleSize`), judul seksi/rubrik dari
  `vb/news-heading` (tautan "Lihat Lainnya" ke arsip rubrik), kelompok kolom samping dari `vb/box`,
  dan tata kolom dari `vb/grid` (mis. `ratio` "2-1" untuk isi + kolom samping). Jangan menulis judul,
  foto, atau tautan artikel tertentu secara manual, karena beritanya akan berganti setiap hari.
- **Susunan ikut referensi.** Ukur urutan seksinya: slider/berita utama, deret kartu, berita terbaru,
  blok per rubrik, pita judul, kolom samping (terpopuler, rubrik), iklan, dll. Pakai rubrik situs ini
  (ID kategori ada di `kerja/awal/beranda.html` hasil generator dan `kerja/isi.json`), bukan nama rubrik
  referensi. Seksi yang butuh data yang tidak dimiliki situs (video, e-paper, polling) dilewati.
  Ruang iklan boleh ada bila referensi punya: pakai blok `velocity/iklan` (lihat poin Iklan).
- **Header portal** mengikuti referensi: logo, tanggal, kotak cari, dan bar menu rubrik yang bisa
  digeser di HP bila referensi begitu. Menu tetap `core/navigation` dari installer.
- **Kolom samping** (`bagian-sidebar.html`, template part `sidebar`) boleh kamu tulis. Isinya dipakai
  halaman indeks/arsip rubrik/pencarian (template tema), jadi harus ikut gaya referensi: Terpopuler
  dari `vb/posts` `orderBy:"popular"`, rubrik pilihan, dan sebagainya. Titik awalnya ada di
  `kerja/awal/tema-parts/sidebar.html`. Di tahap tema berkas ini boleh ditulis bersama header/footer.
- **Arsip & artikel global** (`bagian-arsip.html` → part `arsip`, `bagian-artikel.html` → part
  `artikel`; titik awal di `kerja/awal/tema-parts/arsip.html` dan `artikel.html`). Satu part `arsip`
  dipakai SEMUA daftar tulisan (rubrik, tag, penulis, tanggal, pencarian, indeks); yang berbeda
  hanya query-nya. Karena itu tulis `core/query` dengan `"inherit":true` (jangan isi `categoryIds`,
  `search`, atau ID tertentu), judul dari `velocity/judul-arsip` (`"cari":true` = kotak cari di
  halaman pencarian), dan daftar dari `core/post-template` + `core/post-*`. Tiru arsip rubrik
  referensi (`halaman.arsip_rubrik` di `desain-referensi.json`, potret `potret-ref` URL-nya): kartu
  atau daftar, posisi foto, urutan label rubrik/judul/tanggal/ringkasan, kolom samping, paginasi.
  Part `artikel` meniru artikel tunggal referensi (`halaman.single`): label rubrik, judul, meta
  penulis/tanggal, tombol bagikan (`velocity/bagikan`), foto utama, `core/post-content`, tag,
  berita terkait (`core/query` biasa dengan `excludeCurrent`), kolom samping. Keduanya dinilai audit
  sebagai `halaman_arsip_rubrik` dan `halaman_single`. Jangan menulis judul/isi artikel statis.
- **Iklan** memakai blok `velocity/iklan` dengan atribut `slot`: `atas`, `sela-1`…`sela-4`
  (beranda), `arsip`, `artikel`, `samping`. Gambar iklan diganti pemilik di wp-admin → Tampilan →
  Iklan; tanpa gambar blok ini tampil sebagai kotak "Ruang Iklan" ke Hubungi Kami. Pasang di tempat
  referensi punya iklan. Jangan membuat gambar iklan palsu.
- Jangan menulis `berita.html` karena halaman arsip berita diisi template tema. Halaman profil
  (tentang-kami, redaksi, hubungi-kami, galeri) tetap mengikuti aturan umum.
- Bila semua berita tampil kosong ("Belum ada berita."), periksa `category` dan `offset`; jangan
  menggantinya dengan teks statis.
