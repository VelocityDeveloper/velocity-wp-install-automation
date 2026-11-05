// Tahap pengerjaan project untuk rekap token (/token dan /token/proyek). Data alur dari /api/ai/token-proyek.
// Aplikasi Custom mengikuti langkah installer Laravel (Brief → Review, tanpa Install karena tahap itu tidak memakai AI); WordPress memakai kelompok alur dari token_alur.py.
// Warna = slot kategori tetap (--seri-N di style.css), mengikuti tahap, bukan peringkat.

export const TAHAP = {
  laravel: [
    { kunci: 'brief', label: 'Brief', ket: 'Saran platform, rangkuman, contoh tampilan, PRD, ERD & flowchart' },
    { kunci: 'estimasi', label: 'Estimasi', ket: 'Fitur & jam' },
    { kunci: 'agen', label: 'Agen', ket: 'Agen per fitur & cek kemiripan aplikasi' },
    { kunci: 'review', label: 'Review', ket: 'Run agen untuk revisi dari webmaster. Revisi lewat sesi Claude di luar installer belum termasuk' },
    { kunci: 'lain', label: 'Lainnya', ket: 'Alur yang belum dipetakan ke tahap' },
  ],
  wordpress: [
    { kunci: 'Persiapan', label: 'Persiapan', ket: 'Baca form klien' },
    { kunci: 'Desain', label: 'Desain', ket: 'Agen desain, tampilan tema, FSE' },
    { kunci: 'Konten', label: 'Konten', ket: 'Konten AI, foto, artikel, redaksi klien' },
    { kunci: 'Permintaan', label: 'Permintaan', ket: 'Agen permintaan dari form' },
    { kunci: 'Baca gambar', label: 'Baca gambar', ket: 'Logo, produk, dan gambar lain' },
    { kunci: 'Lainnya', label: 'Lainnya', ket: 'Alur yang belum dipetakan ke tahap' },
  ],
}
for (const daftar of Object.values(TAHAP)) daftar.forEach((t, i) => { t.warna = `var(--seri-${i + 1})` })

const BRIEF_LARAVEL = new Set(['saran', 'rangkuman', 'contoh', 'contoh_revisi', 'kemiripan_contoh', 'susun', 'diagram'])

export function tahapAlur(jenis, a) {
  if (jenis === 'laravel') {
    if (a.kunci.startsWith('review:')) return 'review'
    if (a.kunci.startsWith('agen:') || a.kunci === 'kemiripan_app') return 'agen'
    if (a.kunci === 'estimasi') return 'estimasi'
    if (BRIEF_LARAVEL.has(a.kunci)) return 'brief'
    return 'lain'
  }
  return TAHAP.wordpress.some((t) => t.kunci === a.kelompok) ? a.kelompok : 'Lainnya'
}

// Daftar project (jenis sama) → [{ ...tahap, total, biaya, alur: [{label, total}] }] urut tahap.
// Tahap "Lainnya" hanya muncul bila ada isinya; tahap tanpa catatan tetap ada dengan total 0.
export function rekapTahap(jenis, proyek) {
  const hasil = TAHAP[jenis].map((t) => ({ ...t, total: 0, biaya: 0, alur: {} }))
  const per = Object.fromEntries(hasil.map((t) => [t.kunci, t]))
  for (const p of proyek) {
    for (const a of p.alur) {
      const t = per[tahapAlur(jenis, a)]
      t.total += a.total
      t.biaya += a.biaya_usd || 0
      const nama = a.kunci.startsWith('agen:') ? 'Agen per fitur' : a.kunci.startsWith('review:') ? 'Revisi per fitur' : a.label
      t.alur[nama] = (t.alur[nama] || 0) + a.total
    }
  }
  return hasil
    .filter((t) => t.total || !['lain', 'Lainnya'].includes(t.kunci))
    .map((t) => ({ ...t, alur: Object.entries(t.alur).map(([label, total]) => ({ label, total })).sort((a, b) => b.total - a.total) }))
}

export function persenTahap(n, total) {
  if (!total || !n) return '0%'
  const v = n / total * 100
  if (v < 0.1) return '<0,1%'
  return `${v.toLocaleString('id-ID', { maximumFractionDigits: v < 10 || v > 99 ? 1 : 0 })}%`
}
