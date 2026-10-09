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
- Gambar: tidak ada gambar dari internet. Visual = HTML/CSS/SVG (ilustrasi, pola, gradasi). Gambar klien yang boleh
  dipakai (mis. logo, foto produk) ada di daftar di bawah; rujuk dengan path persis seperti tertulis, dan sebutkan
  di `aset`.
{{ASET}}
- JavaScript secukupnya (Chart.js, buka/tutup menu HP, tab). Tanpa fetch/API. Tanpa `localStorage`.
- Responsif 360px–1440px, tanpa gulir horizontal halaman. Kontras teks cukup. Tanpa emoji sebagai ikon.
- Menu header WAJIB satu baris di layar 1280px (`white-space: nowrap`); bila tidak muat, kurangi item atau pindahkan
  ke dropdown "Lainnya". Nama/logo di header tidak boleh terlipat menabrak menu. Kartu/lencana melayang (hero)
  tidak boleh menutupi teks kartu lain.
- Ukuran wajar: masing-masing ±20–60 KB.

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

## Keluaran JSON
- `nama_aplikasi`: nama situs/sistem yang ditampilkan.
- `landing_html`: isi berkas HTML lengkap halaman depan.
- `dashboard_html`: {{KELUARAN_DASHBOARD}}
- `aset`: path gambar klien yang dipakai (subset daftar di atas), boleh kosong.
- `catatan`: 2–5 poin singkat untuk PM (asumsi yang diambil, hal yang sebaiknya dikonfirmasi ke klien).
