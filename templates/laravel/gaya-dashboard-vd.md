Gaya dashboard WAJIB meniru aplikasi Laravel buatan Velocity yang sudah jadi (SIA VD, e-learning, expedisi):
kerangka starter kit Laravel + shadcn-vue (sidebar), tenang, bersih, dan rapi — BUKAN gaya template admin
yang ramai. Klien harus melihat tampilan yang nanti benar-benar mereka terima. Warna aksen, huruf, dan nama
menu mengikuti bahan project; kerangka dan ukuran di bawah ini tetap.

Kerangka halaman
- Sidebar kiri putih selebar 256px, garis kanan 1px #e6e6e6, tinggi penuh (sticky).
  - Atas: kotak logo 32px (radius 8px, latar warna utama, ikon/inisial putih) + nama aplikasi tebal 14px dan
    subjudul kecil (nama instansi) di bawahnya.
  - Menu dikelompokkan: label seksi kecil (12px, abu #615d59, contoh "Admin", "Laporan"); di dalamnya item
    tunggal ("Dashboard") dan grup yang bisa dilipat (ikon + judul + chevron kanan; anak menjorok dengan
    garis vertikal tipis di kiri). Tinggi item 32px, radius 6px, ikon garis 16px (gaya lucide), teks 14px
    #31302e. Item aktif: latar #f6f5f4 (atau versi sangat muda warna utama), teks hitam, font-medium.
  - Bawah: kartu pengguna (avatar bulat 32px berinisial, nama 14px semibold, email 12px abu, ikon
    chevrons-up-down di kanan).
  - HP (<768px): sidebar tersembunyi jadi laci (drawer) dengan latar gelap transparan, dibuka tombol di header.
    Klik item menu → laci langsung menutup sendiri (transisi halus ±200ms) lalu halaman tujuan tampil.
- Header konten: tinggi 56px, latar putih, garis bawah #e6e6e6, isi = tombol ikon panel-left (buka/tutup
  sidebar) + breadcrumb ("Dashboard" atau "Beranda › Dashboard") 14px; pojok kanan atas = tombol ikon mode
  gelap (matahari/bulan). Tanpa kolom cari besar/banner warna.
- Form panjang/Pengaturan: tombol Simpan ada di bar aksi yang menempel di bawah layar (sticky), selalu terlihat.
- Area konten: latar #f6f5f4, isi dibatasi max-width 1200px di tengah, padding 24px (32px di layar lebar),
  jarak antar-bagian 24px.

Isi dashboard
- Kepala halaman: judul "Dashboard <Peran>" 24px bold (letter-spacing -0.5px, hitam) + deskripsi 14px abu
  #615d59; di kanan boleh satu kartu kecil konteks (periode aktif, proyek terpilih) berikon warna utama.
- Kartu statistik: grid auto-fit min 160px, jarak 12px. Kartu putih, border 1px #e6e6e6, radius 12px, bayangan
  sangat halus (0 1px 2px rgba(0,0,0,.05)), padding 12px 16px. Label 12px UPPERCASE letter-spacing .06em abu +
  ikon 16px abu #a39e98 di kanan; angka 24px bold tabular-nums hitam; catatan kecil opsional.
- Bawah statistik: grid 3 kolom (kiri 2/3, kanan 1/3), jarak 24px.
  - Kiri: kartu "Perlu ditindaklanjuti" (judul 16px semibold + pil jumlah oranye muda #fff6e0/#8a5a00; daftar
    baris ber-divider #e6e6e6: pil angka bulat, judul medium + keterangan abu, chevron kanan) dan tabel data
    terbaru.
  - Kanan: kartu ringkasan (batang proporsi bertumpuk + legenda titik warna, daftar angka per status), kartu
    "Hari ini", grafik kecil.
- Tabel: dibungkus kartu radius 12px; header latar #f6f5f4, teks 12px UPPERCASE semibold abu #615d59; sel 14px
  padding 12px 16px, garis antarbaris #e6e6e6; kolom angka rata kanan; bisa digeser horizontal di HP.
- Badge status: pil kecil 12px medium berlatar muda — hijau #f0faf2/#17702b, biru #f2f8fe/#0b5cad,
  oranye #fdf3ec/#a84400, abu #f6f5f4/#31302e.
- Grafik (Chart.js): tampilan tenang — garis/batang warna utama + 1–2 warna pendamping, grid tipis #eeeeee,
  tanpa latar berwarna, legenda kecil di bawah. Maksimal 2 grafik; data utama tetap kartu & tabel.
- Huruf: 'Instrument Sans' (Google Fonts) kecuali DESIGN.md menentukan lain. Warna utama bawaan #0075de bila
  bahan tidak menentukan. Tanpa gradasi mencolok, tanpa banner warna penuh di atas konten.
