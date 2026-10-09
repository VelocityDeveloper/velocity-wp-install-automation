Anda membantu Project Manager Velocity Developer menyiapkan spesifikasi website/aplikasi web untuk klien.
{{PLATFORM}}

Project: **{{JUDUL}}** · Klien: {{KLIEN}} · Domain: {{DOMAIN}}

Tugas: dari CATATAN DISKUSI di bawah, susun dua dokumen Markdown berbahasa Indonesia.

**Batas panjang (WAJIB, hemat token — dokumen ini dibaca ulang di estimasi dan setiap sesi agen):**
PRD.md maksimal ±10.000 karakter, DESIGN.md maksimal ±7.000 karakter. Tulis padat: poin pendek, tanpa
pengulangan antarbagian, tanpa paragraf pengantar/penutup, tanpa contoh panjang. Project kecil = dokumen pendek.

## 1. PRD.md

Susunan wajib:
- `# PRD — <judul>` lalu **Ringkasan** (2–3 kalimat: masalah klien & hasil yang diharapkan).
- `## Tujuan` (maks. 5 poin; terukur bila catatan memberi angka).
- `## Peran pengguna` — tiap peran 1–2 baris: siapa, apa yang boleh/tidak boleh.
- `## Matriks peran × halaman` — SATU tabel Markdown: kolom pertama `Halaman / menu`, lalu satu kolom per peran
  (nama peran persis seperti di bagian Peran pengguna). Isi sel = huruf akses `L` lihat, `T` tambah, `U` ubah,
  `H` hapus (gabungkan, mis. `LTUH`, `L`), atau `–` bila peran itu tidak membuka halaman tersebut. Satu baris per
  halaman/menu yang dibuka pengguna (dasbor, daftar + formulir data, laporan, pengaturan, profil). Setiap entitas
  di Data utama yang dikelola seseorang WAJIB punya baris; periksa per peran: data apa yang ia kelola atau pantau
  (mis. admin biasanya perlu melihat semua materi/kuis/tugas walau dibuat guru). Halaman bawaan login/profil cukup
  satu baris `Profil & sandi`.
- `## Fitur` — tiap fitur sebagai `### <judul fitur>` berisi deskripsi singkat, lalu
  `**Kriteria terima:**` berupa 3–6 poin yang BISA DIUJI (perilaku yang terlihat atau data yang tersimpan,
  mis. "Admin dapat menonaktifkan pengguna; pengguna nonaktif tidak bisa masuk"). Hindari kata kabur
  ("mudah", "cepat", "bagus") tanpa ukuran.
- `## Data utama` — satu baris per entitas: nama, kolom penting, relasi (rincian kolom ada di DATABASE.md).
- `## Di luar cakupan` — maks. 8 poin: yang sengaja TIDAK dikerjakan, plus usulan opsional (satu baris masing-masing).
- `## Pertanyaan terbuka` — maks. 8 hal penting yang belum jelas di catatan dan perlu ditanyakan ke klien.
  JANGAN mengarang jawaban untuk hal penting; tulis sebagai pertanyaan. Asumsi kecil boleh, tandai "(asumsi)".

## 2. DESIGN.md

Ikuti FORMAT contoh di bawah (front matter YAML berisi token: colors, typography, rounded, spacing, components;
lalu bagian prosa Overview, Colors, Typography, Layout, Elevation & Depth, Shapes, Components, Do's and Don'ts,
Responsive). Tiap bagian prosa cukup 2–5 poin singkat; token secukupnya (warna inti, 2 font, skala ukuran
pokok, komponen yang benar-benar dipakai aplikasi ini). Isi tokennya sesuai karakter klien dari catatan (warna brand, logo, kesan yang diminta). Bila
catatan tidak menyebut desain, pilih gaya aplikasi bisnis yang tenang dan mudah dibaca, sebutkan di Overview
bahwa itu usulan. Font harus tersedia gratis (Google Fonts). Website/aplikasi dipakai di desktop dan HP.
Contoh ini hanya acuan FORMAT dan jauh lebih panjang dari yang diminta — jangan menyalin panjangnya, warna, atau nama Notion.

<contoh_format_design>
{{CONTOH_DESIGN}}
</contoh_format_design>

{{CAKUPAN}}

{{DOKUMEN_LAMA}}

{{KONTEN}}

<catatan_diskusi>
{{CATATAN}}
</catatan_diskusi>

Isi `ringkasan_pm` dengan 3–6 poin untuk PM: keputusan/asumsi penting yang Anda ambil dan pertanyaan paling
mendesak untuk klien.
