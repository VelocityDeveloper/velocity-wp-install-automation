Anda menyusun dua dokumen teknis berbahasa Indonesia untuk aplikasi Laravel **{{JUDUL}}**, turunan dari PRD
di bawah. Dokumen dipakai PM (menjelaskan ke klien), agen Claude Code (membuat migrasi, model, alur halaman),
dan webmaster (memeriksa). Stack: Laravel 13 + Inertia/Vue, database MariaDB, auth Fortify (tabel `users`
bawaan starter kit: id, name, email, email_verified_at, password, two_factor_*, remember_token, timestamps).

Diagram ditulis dengan **Mermaid** dan harus bisa dirender Mermaid versi 11 TANPA galat. Patuhi aturan sintaks
di bawah dengan ketat.

## 1. DATABASE.md — relasi database

Susunan:
- `# Relasi Database — <judul>` lalu 1–2 kalimat ringkas.
- `## Diagram` berisi satu atau beberapa blok ```mermaid erDiagram```. Bila lebih dari ±12 tabel, pecah per
  kelompok (mis. `### Master`, `### Stok`, `### Penjualan`); tabel penghubung antarkelompok boleh muncul di dua
  diagram. Tabel bawaan framework (sessions, cache, jobs, password_reset_tokens, migrations) TIDAK digambar.
- `## Tabel` — untuk tiap tabel: `### <nama_tabel>` + fungsi (1 kalimat), lalu tabel Markdown
  `| Kolom | Tipe | Keterangan |` (tandai PK, FK → tabel.kolom, unik, nullable, default), lalu baris
  **Indeks/unik** dan **Hapus**: perilaku FK (`restrict` / `cascade` / `null`) beserta alasannya.
- `## Aturan integritas` — aturan yang dijaga database/aplikasi (mis. stok tidak boleh minus, nomor faktur unik per cabang).

Konvensi: nama tabel snake_case jamak ala Laravel (`sales`, `sale_items`, atau bahasa Indonesia bila PRD memakainya —
konsisten), PK `id` bigint, FK `<tunggal>_id`, `created_at`/`updated_at`, uang `decimal(15,2)` → di diagram tulis `decimal`.

Aturan sintaks erDiagram (WAJIB):
- Nama entitas hanya huruf/angka/garis bawah, tanpa spasi.
- Atribut: `tipe nama PK|FK|UK "komentar"` — tipe satu kata tanpa kurung (`bigint`, `string`, `text`, `decimal`,
  `integer`, `boolean`, `date`, `datetime`, `json`); enum ditulis `string` dengan nilai di komentar.
  Kunci ganda dipisah koma: `bigint sale_id PK, FK`. Komentar dalam tanda kutip ganda, tanpa tanda kutip di dalamnya.
- Relasi: `users ||--o{ sales : "mencatat"` (label selalu dalam kutip). Kardinalitas: `||` tepat satu,
  `o|` nol/satu, `}o` nol/banyak, `}|` satu/banyak.

## 2. FLOWCHART.md — alur proses

Susunan:
- `# Flowchart — <judul>` lalu daftar isi proses.
- `## Alur umum` — satu diagram: masuk → dashboard per peran → menu utama tiap peran.
- Satu `## <nama proses>` untuk setiap proses bisnis utama di PRD (mis. transaksi kasir, barang masuk, mutasi,
  pembatalan, laporan). Tiap proses: 1–3 kalimat penjelasan, lalu satu blok ```mermaid flowchart TD```
  dengan `subgraph` per peran yang terlibat, keputusan (validasi, hak akses, stok cukup?) sebagai belah ketupat,
  dan jalur gagal/penolakan juga digambar. Sebutkan tabel yang ditulis bila penting (mis. "Simpan ke sales & stock_movements").

Aturan sintaks flowchart (WAJIB):
- Baris pertama blok: `flowchart TD`.
- ID simpul hanya huruf/angka (mis. `K1`, `G3`), unik dalam satu diagram; jangan pakai kata `end` sebagai ID.
- Semua label dalam tanda kutip ganda: `K1["Kasir cari barang"]`, keputusan `K2{"Stok cukup?"}`,
  mulai/selesai `S(["Mulai"])`. Di dalam label jangan ada tanda kutip ganda; pakai `#quot;` bila perlu.
- Subgraph: `subgraph kasir["Kasir"]` … `end` (ID subgraph huruf kecil tanpa spasi).
- Panah berlabel: `K2 -->|"Ya"| K3`.

{{DOKUMEN_LAMA}}

<prd>
{{PRD}}
</prd>

Isi `catatan` dengan 2–5 poin untuk PM: keputusan desain data yang penting dan hal di PRD yang ternyata belum
jelas saat dipetakan ke tabel/alur.
