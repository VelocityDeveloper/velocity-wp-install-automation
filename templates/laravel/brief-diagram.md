{{PLATFORM}}

Diagram ditulis dengan **Mermaid** dan harus bisa dirender Mermaid versi 11 TANPA galat. Patuhi aturan sintaks
di bawah dengan ketat.

**Batas panjang (WAJIB, hemat token — dokumen ini dibaca ulang di estimasi dan setiap sesi agen):**
DATABASE.md maksimal ±9.000 karakter, FLOWCHART.md maksimal ±7.000 karakter. Hanya tabel & proses yang ada di
PRD; tulis padat tanpa paragraf pengantar.

## 1. DATABASE.md — relasi database

Susunan:
- `# Relasi Database — <judul>` lalu 1–2 kalimat ringkas.
- `## Diagram` berisi satu atau beberapa blok ```mermaid erDiagram```. Bila lebih dari ±12 tabel, pecah per
  kelompok (mis. `### Master`, `### Stok`, `### Penjualan`); tabel penghubung antarkelompok boleh muncul di dua
  diagram. Tabel bawaan framework (sessions, cache, jobs, password_reset_tokens, migrations) TIDAK digambar.
- `## Tabel` — untuk tiap tabel: `### <nama_tabel>` + fungsi (1 kalimat), lalu tabel Markdown
  `| Kolom | Tipe | Keterangan |` berisi kolom milik aplikasi saja (`id`, `created_at`/`updated_at` tidak perlu
  ditulis ulang). Keterangan singkat: PK, FK → tabel.kolom + perilaku hapus (`restrict`/`cascade`/`null`), unik,
  nullable, default — tanpa kalimat alasan panjang.
- `## Aturan integritas` — maks. 6 poin, hanya yang penting (mis. stok tidak boleh minus, nomor faktur unik per cabang).

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
- Satu `## <nama proses>` hanya untuk proses bisnis yang punya langkah/keputusan berarti (mis. transaksi kasir,
  persetujuan, pembatalan); CRUD biasa dan laporan sederhana TIDAK perlu diagram. Umumnya 2–5 proses. Tiap proses:
  1–2 kalimat penjelasan, lalu satu blok ```mermaid flowchart TD```
  dengan `subgraph` per peran yang terlibat, keputusan (validasi, hak akses, stok cukup?) sebagai belah ketupat,
  dan jalur gagal/penolakan juga digambar. Sebutkan tabel yang ditulis bila penting (mis. "Simpan ke sales & stock_movements").

Aturan sintaks flowchart (WAJIB):
- Baris pertama blok: `flowchart TD`.
- ID simpul hanya huruf/angka (mis. `K1`, `G3`), unik dalam satu diagram; jangan pakai kata `end` sebagai ID.
- Semua label dalam tanda kutip ganda: `K1["Kasir cari barang"]`, keputusan `K2{"Stok cukup?"}`,
  mulai/selesai `S(["Mulai"])`. Di dalam label jangan ada tanda kutip ganda; pakai `#quot;` bila perlu.
- Subgraph: `subgraph kasir["Kasir"]` … `end` (ID subgraph huruf kecil tanpa spasi).
- Panah berlabel: `K2 -->|"Ya"| K3`.

{{CAKUPAN}}

{{DOKUMEN_LAMA}}

<prd>
{{PRD}}
</prd>

Isi `catatan` dengan 2–5 poin untuk PM: keputusan desain data yang penting dan hal di PRD yang ternyata belum
jelas saat dipetakan ke tabel/alur.
