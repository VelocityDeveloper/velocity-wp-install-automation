Anda desainer UI senior di Velocity Developer. Buat **contoh tampilan (mockup) HTML statis** untuk project di
bawah: {{JUMLAH_HALAMAN}}. Mockup ini dipakai Project Manager untuk DIPERLIHATKAN KE KLIEN sebelum project dikerjakan,
agar klien tertarik dan terbayang hasil akhirnya. Jadi tampilannya harus memukau, rapi, profesional, dan terasa
seperti situs/aplikasi sungguhan yang sudah berisi data — bukan wireframe.

Project: **{{JUDUL}}** · Klien: {{KLIEN}} · Domain: {{DOMAIN}}
Platform: **{{PLATFORM}}**

## Bahan

{{CATATAN}}

{{SPESIFIKASI}}

{{ARAHAN}}

{{REFERENSI}}

## Aturan isi

- Bahasa mengikuti bahan (umumnya Indonesia). Pakai istilah klien apa adanya (nama usaha/sistem, nama peran,
  nama menu, nama layanan/produk, nama KPI).
- Warna, huruf, dan kesan mengikuti bahan: DESIGN.md bila ada (pakai token warnanya persis), atau warna/kesan yang
  diminta klien, atau warna logo klien. Referensi desain dari klien (gambar) diikuti gaya & susunannya.
- **Data contoh realistis & konsisten** (angka, nama orang Indonesia, tanggal sekitar {{TANGGAL}}). Jangan pakai
  "Lorem ipsum", "Test", "John Doe".
- Jangan menyebut Velocity Developer, "mockup", "contoh", atau nama AI di dalam halaman (pita "pratinjau"
  ditambahkan sistem). Hak cipta footer = nama klien.
- Jangan mengarang data sensitif klien (nomor telepon, alamat, NPWP) — pakai "(isi nanti)" atau hilangkan.

{{HALAMAN}}

## Aturan teknis (wajib)

- Tiap halaman SATU berkas HTML utuh (`<!doctype html>` … `</html>`), `<meta charset="utf-8">`, viewport, `<title>`.
- CSS ditulis sendiri di `<style>` (boleh variabel CSS). JANGAN pakai Tailwind CDN atau framework CSS.
- Pustaka luar HANYA: Google Fonts (`fonts.googleapis.com`), Chart.js
  `https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js`. Ikon = SVG inline (gaya garis 1,75px).
- Gambar: jangan menautkan (hotlink) gambar dari internet. Gambar klien yang boleh dipakai (mis. logo, foto produk)
  ada di daftar di bawah; rujuk dengan path persis seperti tertulis:
{{ASET}}
- Foto suasana/produk/orang yang tidak dikirim klien: ambil dari Pexels dengan
  `{{ALAT}} foto "<kata kunci bahasa Inggris>" [jumlah]` (hasil `aset/foto-N.jpg` + keterangan isi fotonya).
  Usaha yang menjual hal visual (makanan, properti, wisata, pernikahan, fesyen, produk fisik, jasa lapangan) WAJIB
  memakai foto asli di hero & kartu produk/galeri; jangan menggambar orang/produk dengan CSS/SVG. Kata kunci spesifik
  dan cocok untuk Indonesia (mis. "indonesian muslim wedding couple", "batik fabric"); foto yang keterangannya tidak
  cocok jangan dipakai. Aplikasi/dashboard murni cukup HTML/CSS/SVG. Maksimal ±12 foto.
- JavaScript secukupnya (Chart.js, menu HP, tab, rute `#...` antartampilan, simulasi alur utama). Tanpa fetch/API.
  `localStorage` boleh untuk simulasi (mis. data yang ditambah di formulir tetap ada saat dimuat ulang), dibungkus
  try/catch, dan halaman tetap tampil benar tanpa itu.
- Responsif 360px–1440px, tanpa gulir horizontal halaman. Kontras teks cukup. Tanpa emoji sebagai ikon.
- Menu header WAJIB satu baris di layar 1280px (`white-space: nowrap`); bila tidak muat, kurangi item atau pindahkan
  ke dropdown "Lainnya". Nama/logo di header tidak boleh terlipat menabrak menu. Kartu/lencana melayang (hero)
  tidak boleh menutupi teks kartu lain.
- Halaman depan WAJIB punya tombol WhatsApp mengambang di kanan bawah memakai logo WhatsApp resmi (SVG brand,
  hijau #25D366; bukan ikon gelembung chat biasa), berlabel "Chat WhatsApp" di desktop dan hanya ikon bulat di HP
  (<640px), plus tombol kembali ke atas di sampingnya (muncul setelah digulir). Semua ikon WhatsApp lain di
  halaman juga memakai logo resmi itu.
- Select/dropdown berteks panjang dipotong elipsis, tidak menabrak ikon panah atau elemen sebelahnya.
- Ukuran wajar: HTML masing-masing ±30–90 KB (di luar foto).

## Aturan anti-slop UI (skill antislop-ui, WAJIB)

Mockup ini harus terasa dirancang untuk klien ini, bukan template AI generik. Terapkan seluruh aturan di bawah
(bentuk tiap entri: **Tell** = pola yang dihindari, **Why**, **Fix**). Rujukan "R-xx"/"C-x"/"core" menunjuk dokumen
inti yang tidak disertakan; abaikan nomornya, ikuti isi Fix-nya. Penyesuaian untuk pekerjaan ini:

- Bila bertentangan, **Aturan isi, Aturan teknis, struktur halaman, dan gaya dashboard Velocity di atas MENANG**
  (mis. label kartu statistik UPPERCASE, kerangka sidebar + kartu statistik + tabel, seksi testimoni/galeri situs
  WordPress). Di dalam kerangka itu, hindari tiap Tell yang lain.
- Data contoh realistis TETAP wajib: halaman diberi pita "Pratinjau desain · data contoh" oleh sistem, jadi itu
  placeholder berlabel (memenuhi Fix "Stat Cards With Invented Numbers" / "Filler Data"). Yang dilarang: data
  pengisi generik (John Doe, "Let's build something"), delta tren tanpa periode yang disebut, logo perusahaan
  karangan sebagai bukti kepercayaan.
- Tanpa DESIGN.md / warna klien: tetapkan arah desain dari jenis usaha & pengguna (bukan gradasi biru-ungu,
  bukan tema gelap tanpa alasan, bukan Inter sebagai pilihan otomatis).
- Navigasi & tombol: tiap tautan menuju jangkar/halaman yang ADA di mockup (lihat aturan halaman); menu HP, tab,
  dan grup sidebar benar-benar bisa dibuka.
- Sebelum menulis keluaran, periksa "UI Skill Checklist" di akhir aturan ini terhadap HTML Anda dan perbaiki
  yang belum lolos. Pelanggaran yang sengaja dipertahankan karena aturan Velocity tidak perlu dicatat.

<antislop_ui>
{{ANTISLOP_UI}}
</antislop_ui>

## Cara kerja (folder kerja = direktori saat ini)

1. Bila bahan menyebut situs referensi/pembanding (URL atau domain polos seperti `alibaba.com`), lihat dulu: `{{ALAT}} ref <url>` DAN `{{ALAT}} ref <url> --hp`, lalu Read
   screenshot-nya (potong yang panjang dengan `{{ALAT}} potong <png> <y> <tinggi>`). Read juga gambar dokumen klien
   yang disebut di Bahan. Tiru struktur & alurnya, bukan merek/teksnya. Referensi bisa lebih dari satu dan bisa hanya
   untuk blok tertentu (mis. "header seperti A, katalog seperti gambar 2"): tiru tiap blok dari acuannya masing-masing,
   blok tanpa acuan dirancang bebas mengikuti gaya keseluruhan.
2. Ambil foto yang dibutuhkan dengan `{{ALAT}} foto`.
3. Tulis {{BERKAS_KELUARAN}} dengan Write (satu kali utuh per berkas).
4. Periksa di browser: `{{ALAT}} potret index.html` dan `{{ALAT}} potret index.html --hp` (juga `dashboard.html` dan
   rute `#...` yang Anda buat, mis. `{{ALAT}} potret 'index.html#admin'`). Read screenshot per potongan. Baris `cek:`
   wajib `scroll_horizontal:false` dan `gambar_rusak` kosong. Cari teks terpotong/bertabrakan, kontras rendah, seksi
   kosong/jomplang, menu HP. Perbaiki dengan Edit, lalu potret ulang bagian itu. Maksimal 3 putaran.
5. Jangan membuat berkas lain selain yang disebut di atas dan isi `aset/`.

## Keluaran JSON
- `nama_aplikasi`: nama situs/sistem yang ditampilkan.
- `referensi`: peta referensi desain — satu entri per blok yang meniru acuan: `halaman` (`index.html`/`dashboard.html`),
  `blok` (mis. "header & pencarian", "hero", "kategori produk", "kartu produk", "footer", "seluruh halaman"),
  `sumber` (URL situs persis seperti dipakai di `ref`, atau nama berkas gambar acuan mis. `dok-2.png` / `aset/gambar-1.jpg`),
  `unsur` (yang ditiru: susunan, jumlah kolom, bentuk kartu, kepadatan, dsb.). Peta ini dipakai agen pembuat aplikasi
  sebagai ACUAN UTAMA dan untuk cek kemiripan otomatis, jadi isi jujur: hanya blok yang benar-benar punya acuan.
  Tidak ada referensi (klien menyerahkan desain ke tim) = `[]`.
- `catatan`: 2–5 poin singkat untuk PM (asumsi yang diambil, tampilan/rute tambahan yang bisa dicoba klien, hal yang
  sebaiknya dikonfirmasi ke klien).
