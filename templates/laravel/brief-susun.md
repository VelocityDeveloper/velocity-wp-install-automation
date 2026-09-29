Anda membantu Project Manager Velocity Developer menyiapkan spesifikasi aplikasi web Laravel untuk klien.
Aplikasi akan dibangun dengan stack tetap: `laravel new --vue` (Laravel 13, Inertia, Vue 3 + TypeScript,
Tailwind 4, komponen shadcn-vue/reka-ui, auth Fortify, Pest). Yang mengerjakan kode nanti agen Claude Code,
fitur demi fitur, lalu webmaster memeriksa hasilnya memakai kriteria terima di PRD.

Project: **{{JUDUL}}** · Klien: {{KLIEN}} · Domain: {{DOMAIN}}

Tugas: dari CATATAN DISKUSI di bawah, susun dua dokumen Markdown berbahasa Indonesia.

## 1. PRD.md

Susunan wajib:
- `# PRD — <judul>` lalu **Ringkasan** (2–4 kalimat: masalah klien & hasil yang diharapkan).
- `## Tujuan` (poin terukur bila catatan memberi angka).
- `## Peran pengguna` — tiap peran: siapa, apa yang boleh/tidak boleh.
- `## Fitur` — tiap fitur sebagai `### <judul fitur>` berisi deskripsi singkat, lalu
  `**Kriteria terima:**` berupa daftar poin yang BISA DIUJI (perilaku yang terlihat atau data yang tersimpan,
  mis. "Admin dapat menonaktifkan pengguna; pengguna nonaktif tidak bisa masuk"). Hindari kata kabur
  ("mudah", "cepat", "bagus") tanpa ukuran.
- `## Data utama` — entitas dan kolom penting beserta relasinya.
- `## Di luar cakupan` — yang sengaja TIDAK dikerjakan (dari catatan, atau yang wajar diasumsikan).
- `## Pertanyaan terbuka` — hal yang belum jelas di catatan dan perlu ditanyakan ke klien.
  JANGAN mengarang jawaban untuk hal penting; tulis sebagai pertanyaan. Asumsi kecil boleh, tandai "(asumsi)".

## 2. DESIGN.md

Ikuti FORMAT contoh di bawah (front matter YAML berisi token: colors, typography, rounded, spacing, components;
lalu bagian prosa Overview, Colors, Typography, Layout, Elevation & Depth, Shapes, Components, Do's and Don'ts,
Responsive). Isi tokennya sesuai karakter klien dari catatan (warna brand, logo, kesan yang diminta). Bila
catatan tidak menyebut desain, pilih gaya aplikasi bisnis yang tenang dan mudah dibaca, sebutkan di Overview
bahwa itu usulan. Font harus tersedia gratis (Google Fonts). Aplikasi dipakai di desktop dan HP.
Contoh ini hanya acuan FORMAT — jangan menyalin warna/nama Notion.

<contoh_format_design>
{{CONTOH_DESIGN}}
</contoh_format_design>

{{DOKUMEN_LAMA}}

<catatan_diskusi>
{{CATATAN}}
</catatan_diskusi>

Isi `ringkasan_pm` dengan 3–6 poin untuk PM: keputusan/asumsi penting yang Anda ambil dan pertanyaan paling
mendesak untuk klien.
