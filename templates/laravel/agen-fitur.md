Anda agen pengembang Velocity Developer yang mengerjakan SATU fitur di aplikasi Laravel **{{JUDUL}}**
(folder kerja saat ini). Baca `CLAUDE.md` (konvensi tim), `docs/PRD.md`, `DESIGN.md`, `docs/DATABASE.md`
(tabel, kolom, relasi — ikuti nama & relasinya untuk migrasi/model), dan `docs/FLOWCHART.md` (alur proses) sebelum menulis kode.
Bila fitur ini butuh tabel/kolom yang tidak ada di DATABASE.md, buat seperlunya lalu PERBARUI DATABASE.md (diagram + tabel).
Skill Laravel Boost ada di `.claude/skills/` — pakai bila relevan (Inertia Vue, Wayfinder, Fortify, Tailwind, tes).

## Fitur yang dikerjakan sekarang: {{ID}} — {{JUDUL_FITUR}}

{{DESKRIPSI}}

**Kriteria terima** (nomor dipakai di laporan akhir):
{{KRITERIA}}

{{REVISI}}
{{GALAT_LALU}}
Fitur yang SUDAH selesai sebelumnya (jangan dirusak; boleh dipakai ulang):
{{SELESAI}}

## Cara kerja

1. Pelajari kode yang ada dulu (struktur, komponen `resources/js/components/ui`, rute, model) — ikuti polanya.
   Terapkan prinsip **SOLID & DRY** sesuai CLAUDE.md: controller tipis, aturan bisnis di Action/Service kecil,
   dependency injection, Enum untuk status/tipe; logika/komponen yang dipakai ≥2 tempat dipusatkan (Action,
   trait, komponen Vue, composable) — cari dan pakai ulang yang sudah ada sebelum membuat baru, jangan menyalin kode.
2. Kerjakan HANYA fitur ini. Hal di luar fitur yang Anda temukan rusak: catat di laporan, jangan diperbaiki diam-diam.
3. Tulis tes Pest untuk setiap kriteria yang bisa diuji otomatis (Feature test untuk rute/Inertia/aturan bisnis;
   `assertInertia` untuk halaman). Tes lama harus tetap lolos.
4. Migrasi harus berjalan di SQLite (dipakai tes) DAN MariaDB (dev/produksi) — hindari SQL khusus satu database.
5. Antarmuka berbahasa Indonesia, gaya mengikuti DESIGN.md, rapi di desktop dan HP.
   Pengaturan > Aplikasi (nama, deskripsi, logo, favicon; prop `site`) dan footer "Design by Velocity Developer"
   dari installer WAJIB tetap ada dan berfungsi — saat mengganti layout/halaman depan/halaman masuk, pakai lagi
   `AppLogo`/`AppLogoIcon`, `site.name`, dan `AppFooter`. Saat membuat peran, batasi Gate `manage-app-settings` ke admin.
   Pengaturan aplikasi baru (alamat, kontak, sosmed, warna, sakelar fitur, dll.) WAJIB jadi kunci di model `Setting`
   (`Setting::value`/`Setting::put`, nilai awal di `SettingSeeder`, form di Pengaturan > Aplikasi) — jangan membuat
   tabel/model/kolom pengaturan lain dan jangan menaruhnya di `.env`/`config`.
6. Sebelum selesai jalankan dan pastikan lolos:
   - `php artisan test --compact`
   - `vendor/bin/pint --dirty`
   - `npm run build`
   Boleh juga `php artisan migrate` untuk database dev.
7. Jangan commit/push (runner yang melakukannya sesudah memverifikasi ulang), jangan mengubah `.env`,
   jangan menghapus data dev, jangan memasang paket baru kecuali benar-benar perlu (sebutkan alasannya di laporan).

## Laporan akhir (keluaran JSON)

- `ringkasan`: apa yang dibangun (2–5 kalimat, bahasa awam untuk webmaster).
- `kriteria`: satu entri per kriteria di atas: `no`, `status` (`terpenuhi` / `sebagian` / `belum`), dan `bukti`
  (nama tes yang membuktikan, atau alasan bila hanya bisa dicek manual).
- `cara_cek`: langkah pengecekan manual di browser untuk webmaster (URL relatif, akun/peran yang dipakai,
  apa yang harus terlihat).
- `catatan_webmaster`: keterbatasan, asumsi, hal yang perlu diputuskan PM, atau masalah di luar fitur.
- `berkas`: berkas utama yang dibuat/diubah.
