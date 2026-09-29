// Bersama untuk halaman alur project Laravel (Installer > Laravel). API: scripts/laravel_proyek.py lewat /api/laravel.
import { ref, watch } from 'vue'
import { kirim } from './api.js'

// Nama pengisi dicatat di riwayat tiap aksi (tanpa login; dashboard hanya LAN/Tailscale)
export const namaSaya = ref('')
try { namaSaya.value = localStorage.getItem('laravel-oleh') || '' } catch { /* penyimpanan diblokir */ }
watch(namaSaya, (v) => { try { localStorage.setItem('laravel-oleh', v) } catch { /* abaikan */ } })
// Tautan "Isi Nama Anda" di mana pun → gulir & fokus ke kolom nama (id="nama-saya")
export function keNama() {
  const el = document.getElementById('nama-saya')
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.focus({ preventScroll: true })
}

export const TAHAP = [
  { kunci: 'brief', label: 'Brief', ket: 'DESIGN.md + PRD' },
  { kunci: 'estimasi', label: 'Estimasi', ket: 'Fitur & jam' },
  { kunci: 'install', label: 'Install', ket: 'Kerangka + repo' },
  { kunci: 'agen', label: 'Agen', ket: 'Claude mengerjakan' },
  { kunci: 'review', label: 'Review', ket: 'Checklist webmaster' },
]
export const indeksTahap = (t) => (t === 'selesai' ? TAHAP.length : TAHAP.findIndex((x) => x.kunci === t))

export const STATUS_FITUR = {
  antre: ['abu', 'Antre'], jalan: ['kuning', 'Dikerjakan'], dites: ['biru', 'Siap dicek'],
  gagal: ['merah', 'Gagal'], ok: ['hijau', 'OK'], revisi: ['kuning', 'Revisi'],
}

const PESAN = {
  invalid_judul: 'Judul wajib diisi, tanpa tanda kutip, $, \\, |, &, ;, < atau >.',
  invalid_klien: 'Nama klien memuat karakter terlarang.',
  invalid_oleh: 'Isi nama Anda dulu (kolom "Nama Anda").',
  invalid_domain: 'Domain tidak sah (contoh: namaklien.com).',
  invalid_app: 'Nama aplikasi: huruf kecil, angka, tanda hubung; 3–32 karakter, diawali huruf.',
  onprogress_tidak_ada: 'Folder On Progress tidak ditemukan.',
  sedang_berjalan: 'Masih ada proses berjalan untuk project ini. Tunggu sampai selesai.',
  sudah_dikunci: 'Estimasi sudah dikunci. Buka kunci dulu untuk mengubah DESIGN.md, PRD, atau fitur.',
  sudah_diinstall: 'Project sudah/sedang di-install; identitas & estimasi tidak bisa diubah lagi.',
  catatan_kosong: 'Tempel dan simpan catatan diskusi dulu.',
  prd_kosong: 'PRD masih kosong.',
  dokumen_kosong: 'DESIGN.md dan PRD.md harus terisi sebelum estimasi dikunci.',
  fitur_kosong: 'Belum ada fitur.',
  fitur_tanpa_judul: 'Setiap fitur harus punya judul.',
  fitur_tanpa_kriteria: 'Setiap fitur harus punya minimal satu kriteria terima.',
  invalid_jam: 'Jam harus berupa angka.',
  estimasi_belum_dikunci: 'Kunci estimasi dulu.',
  folder_exists: 'Nama aplikasi sudah dipakai (folder /home atau project lain).',
  db_root_missing: 'Kredensial root MariaDB installer belum ada.',
  no_port: 'Tidak ada port kosong di rentang 8050–8999.',
  belum_diinstall: 'Project belum terpasang.',
  fitur_tidak_gagal: 'Fitur ini tidak berstatus gagal.',
  catatan_revisi_kosong: 'Tulis catatan revisi untuk agen.',
  kriteria_belum_dicentang: 'Centang semua kriteria dulu sebelum menandai OK.',
  fitur_belum_dites: 'Fitur belum selesai dikerjakan agen.',
  terlalu_panjang: 'Teks terlalu panjang (maks 400 ribu karakter).',
  forbidden: 'Hanya bisa dari jaringan kantor/Tailscale.',
  payload_too_large: 'Isian terlalu besar.',
}
export const pesanGalat = (e) => PESAN[String(e?.message || e).split(':')[0]] || String(e?.message || e)

export const aksi = (id, nama, body = {}) => kirim(`/api/laravel/p/${id}/${nama}`, { oleh: namaSaya.value.trim(), ...body })
export const jam = (n) => `${Number(n || 0).toLocaleString('id-ID', { maximumFractionDigits: 1 })} jam`
// Jam kerja webmaster dalam hari kerja (1 hari = 7 jam): 14,5 → "2 hari 0,5 jam"
export const JAM_SEHARI = 7
export const hariJam = (n) => {
  const t = Math.round(Number(n || 0) * 10) / 10
  const hari = Math.floor(t / JAM_SEHARI)
  const sisa = Math.round((t - hari * JAM_SEHARI) * 10) / 10
  if (!hari) return jam(sisa)
  return sisa ? `${hari} hari ${jam(sisa)}` : `${hari} hari`
}

// Jadwal perkiraan (hari kerja ke-N) dengan batas nyata (keputusan user 2026-09-25):
// - mesin nyala 07.00–22.00, tapi agen TIDAK memakai mesin penuh: kuota langganan Claude dipakai bersama webmaster
//   & agen lain. Jatah per project per hari = min(jam_agen_per_project_per_hari [6], jam_agen_total_per_hari [10] /
//   (1 + project lain di tahap Agen)) — config/laravel-jadwal.json, sama dengan L.jatah_agen_harian() yang ditegakkan runner.
// - webmaster 7 jam/hari (08–12, 13–16), mereview tiap fitur begitu agen selesai — paralel dengan agen.
export const SLOT_WM = [[8, 12], [13, 16]]
// fitur: [{jam_agen, jam_webmaster}] berurutan; tambahan: pekerjaan di luar fitur [{jam_agen, jam_webmaster}]
// yang dikerjakan berurutan SESUDAH semua fitur direview. Waktu menunggu klien tidak dihitung (keputusan user 2026-09-25).
export function jadwal(fitur, cfg = {}, tambahan = []) {
  const mulai = cfg.mesin_mulai ?? 7
  const jendela = (cfg.mesin_selesai ?? 22) - 0.25 - mulai          // fitur harus selesai sebelum 21.45
  const perProject = Math.min(jendela, cfg.jam_agen_per_project_per_hari ?? 6)
  const efektif = cfg.jam_agen_total_per_hari ?? 10
  const porsi = Math.min(perProject, efektif / (1 + (cfg.project_agen_lain || 0)))   // jatah agen per hari project ini
  const jamKe = (pakai) => mulai + pakai * (jendela / porsi)        // pemakaian kapasitas → jam dinding
  const A = { hari: 0, pakai: 0 }                                    // penunjuk agen
  const W = { hari: 0, jam: SLOT_WM[0][0] }                          // penunjuk webmaster
  const waktuA = () => A.hari * 24 + jamKe(A.pakai)
  const waktuW = () => W.hari * 24 + W.jam
  const rapikanW = () => {
    for (;;) {
      const slot = SLOT_WM.find(([, b]) => W.jam < b)
      if (!slot) { W.hari++; W.jam = SLOT_WM[0][0]; continue }
      if (W.jam < slot[0]) W.jam = slot[0]
      return
    }
  }
  const agenMulaiPaling = (t) => {   // agen tidak bisa mulai sebelum waktu t
    if (waktuA() >= t) return
    A.hari = Math.floor(t / 24)
    A.pakai = Math.min(porsi, Math.max(0, (t % 24 - mulai) * porsi / jendela))
  }
  const kerjaAgen = (jamAgen) => {
    let a = Math.max(0, Number(jamAgen) || 0)
    if (!a) return
    // Fitur tidak dimulai bila tidak muat di sisa kapasitas hari ini (kecuali lebih besar dari sehari)
    if (A.pakai > 0 && A.pakai + a > porsi && a <= porsi) { A.hari++; A.pakai = 0 }
    while (A.pakai + a > porsi + 1e-9) { a -= porsi - A.pakai; A.hari++; A.pakai = 0 }
    A.pakai += a
  }
  const kerjaWebmaster = (jamWm, siap) => {
    if (waktuW() < siap) { W.hari = Math.floor(siap / 24); W.jam = siap % 24 }
    let w = Math.max(0, Number(jamWm) || 0)
    rapikanW()
    while (w > 1e-9) {
      const slot = SLOT_WM.find(([x, y]) => W.jam >= x && W.jam < y)
      const pakai = Math.min(w, slot[1] - W.jam)
      W.jam += pakai; w -= pakai
      if (w > 1e-9) rapikanW()
    }
  }
  for (const f of fitur) {
    kerjaAgen(f.jam_agen)
    kerjaWebmaster(f.jam_webmaster, waktuA())
  }
  const hasilFitur = { hariAgen: A.hari + 1, agenSelesai: waktuA() % 24, hariFitur: W.hari + 1, fiturJam: W.jam }
  for (const t of tambahan) {
    const awal = Math.max(waktuA(), waktuW())
    agenMulaiPaling(awal)
    kerjaAgen(t.jam_agen)
    kerjaWebmaster(t.jam_webmaster, Math.max(awal, Number(t.jam_agen) ? waktuA() : awal))
  }
  const pukul = (h) => `${String(Math.floor(h)).padStart(2, '0')}.${String(Math.round((h % 1) * 60) % 60).padStart(2, '0')}`
  const akhirTotal = Math.max(waktuA(), waktuW())
  return {
    porsi: Math.round(porsi * 10) / 10, efektif, perProject, lain: cfg.project_agen_lain || 0,
    hariAgen: hasilFitur.hariAgen, agenSelesai: pukul(hasilFitur.agenSelesai),
    hariFitur: hasilFitur.hariFitur, fiturJam: pukul(hasilFitur.fiturJam),
    hariSelesai: Math.floor(akhirTotal / 24) + 1, selesaiJam: pukul(akhirTotal % 24),
  }
}
