// Bersama untuk halaman alur project Laravel (Installer > Laravel). API: scripts/laravel_proyek.py lewat /api/laravel.
import { ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { kirim } from './api.js'

// Nama pengisi dicatat di riwayat tiap aksi (tanpa login; dashboard hanya LAN/Tailscale).
// Bawaan Dwi Ernawati (PM utama, permintaan user 1 Okt); pilihan lain tetap tersimpan per browser.
export const NAMA_BAWAAN = 'Dwi Ernawati'
export const namaSaya = ref(NAMA_BAWAAN)
try { namaSaya.value = localStorage.getItem('laravel-oleh') || NAMA_BAWAAN } catch { /* penyimpanan diblokir */ }
watch(namaSaya, (v) => { try { localStorage.setItem('laravel-oleh', v) } catch { /* abaikan */ } })
// Tautan "Isi Nama Anda" di mana pun → gulir & fokus ke kolom nama (id="nama-saya")
export function keNama() {
  const el = document.getElementById('nama-saya')
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.focus({ preventScroll: true })
}

export const TAHAP = [
  { kunci: 'brief', label: 'Brief', ket: 'Saran platform + PRD' },
  { kunci: 'estimasi', label: 'Estimasi', ket: 'Fitur & jam' },
  { kunci: 'install', label: 'Install', ket: 'Kerangka + repo' },
  { kunci: 'agen', label: 'Agen', ket: 'Claude mengerjakan' },
  { kunci: 'review', label: 'Review', ket: 'Checklist webmaster' },
]
export const indeksTahap = (t) => (t === 'selesai' ? TAHAP.length : TAHAP.findIndex((x) => x.kunci === t))

// Status project (5 Okt): brief tidak deal → Batal/Ditunda, rampung → Selesai; keluar dari daftar aktif. Nilai = scripts/laravel_proyek.py STATUS_PROYEK
export const STATUS_PROYEK = {
  aktif: { label: 'Aktif', ket: 'Project berjalan seperti biasa.' },
  selesai: { label: 'Selesai', ket: 'Project rampung / sudah serah terima; bisa diaktifkan lagi bila ada pekerjaan.', kelas: 'info' },
  ditunda: { label: 'Ditunda', ket: 'Menunggu keputusan klien; bisa diaktifkan lagi.', kelas: 'waspada' },
  batal: { label: 'Batal', ket: 'Tidak deal; data tetap tersimpan.', kelas: 'bahaya' },
}

// Status server dev (scripts/server_dev.py → /api/laravel/server)
export const KONDISI_SERVER = {
  nyala: { label: 'Nyala', kelas: 'baik' },
  perlu_restart: { label: 'Perlu restart', kelas: 'waspada' },
  mati: { label: 'Mati', kelas: 'mati' },
  tidak_ada: { label: 'Layanan tidak ada', kelas: 'bahaya' },
}

export const STATUS_FITUR = {
  antre: ['abu', 'Antre'], jalan: ['kuning', 'Dikerjakan'], dites: ['biru', 'Siap dicek'],
  gagal: ['merah', 'Gagal'], ok: ['hijau', 'OK'], revisi: ['kuning', 'Revisi'],
}

const PESAN = {
  server_tidak_dikenal: 'Server tidak ada di config/local-projects.json.',
  server_selalu_nyala: 'Server ini ditandai selalu nyala (produksi); tidak bisa dimatikan dari sini.',
  systemctl_gagal: 'systemctl gagal menjalankan perintah; cek journalctl layanannya.',
  proyek_nonaktif: 'Project berstatus Batal/Ditunda. Aktifkan kembali dulu untuk melanjutkan.',
  konfirmasi_salah: 'Ketik ID project persis untuk konfirmasi hapus.',
  status_tidak_sah: 'Status tidak dikenal.',
  invalid_judul: 'Judul wajib diisi, tanpa tanda kutip, $, \\, |, &, ;, < atau >.',
  invalid_klien: 'Nama klien memuat karakter terlarang.',
  invalid_oleh: 'Isi nama Anda dulu (kolom "Nama Anda").',
  invalid_domain: 'Domain tidak sah (contoh: namaklien.com).',
  invalid_app: 'Nama aplikasi: huruf kecil, angka, tanda hubung; 3–32 karakter, diawali huruf.',
  onprogress_tidak_ada: 'Folder On Progress tidak ditemukan.',
  sedang_berjalan: 'Masih ada proses berjalan untuk project ini. Tunggu sampai selesai.',
  sudah_dikunci: 'Estimasi sudah dikunci. Buka kunci dulu untuk mengubah DESIGN.md, PRD, atau fitur.',
  sudah_diinstall: 'Project sudah/sedang di-install; identitas & estimasi tidak bisa diubah lagi.',
  catatan_kosong: 'Tempel dan simpan catatan diskusi, atau unggah dokumen klien dulu.',
  arahan_kosong: 'Tulis arahan revisi dulu: bagian mana yang diubah dan seperti apa.',
  halaman_tidak_sah: 'Halaman contoh tidak dikenal.',
  contoh_beda_platform: 'Contoh dibuat untuk platform lain; pakai Buat ulang.',
  dokumen_jenis: 'Format tidak didukung. Pakai PDF, Word, Excel .xlsx, PowerPoint, TXT/CSV, atau gambar (file .xls/.rtf: simpan ulang sebagai .xlsx/PDF).',
  dokumen_terlalu_banyak: 'Maksimal 30 dokumen per project; hapus yang tidak dipakai.',
  dokumen_kosong_isi: 'Berkas kosong (0 byte).',
  prd_kosong: 'PRD masih kosong.',
  saran_belum_ada: 'Minta saran platform dulu.',
  opsi_tidak_ada: 'Opsi tidak ditemukan; muat ulang halaman.',
  platform_belum_dipilih: 'Pilih salah satu opsi di Saran platform dulu sebelum menyusun PRD.',
  khusus_laravel: 'Install otomatis dan agen hanya untuk platform Laravel + Vue.',
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
  payload_too_large: 'Terlalu besar (dokumen maks 25 MB).',
  contoh_belum_ada: 'Buat contoh tampilan dulu.',
  preview_belum_diatur: 'Server preview nglorok.com belum diatur (akses SSH VPS Sumopod).',
}
// Review dianggap mendesak (merah) bila agen tertahan gerbang review atau ada fitur menunggu lebih dari sehari
export const reviewMendesak = (r) => !!(r?.tertahan || (r?.tertua && Date.now() / 1000 - r.tertua > 86400))

export const pesanGalat = (e) => PESAN[String(e?.message || e).split(':')[0]] || String(e?.message || e)

export const aksi = (id, nama, body = {}) => kirim(`/api/laravel/p/${id}/${nama}`, { oleh: namaSaya.value.trim(), ...body })
// Di bawah 1 jam ditulis menit: jam agen per fitur kini ±0,1–0,5 jam (kalibrasi data nyata 1 Okt)
export const jam = (n) => {
  const x = Number(n || 0)
  if (x > 0 && x < 1) return `${Math.round(x * 60)} mnt`
  return `${x.toLocaleString('id-ID', { maximumFractionDigits: 1 })} jam`
}
// Token ringkas: 196.951.220 → "197 jt", 73.486 → "73 rb"
export const angkaToken = (n) => n >= 1e6 ? `${(n / 1e6).toLocaleString('id-ID', { maximumFractionDigits: 1 })} jt` : n >= 1e3 ? `${Math.round(n / 1e3).toLocaleString('id-ID')} rb` : String(n || 0)
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
// Jalur Laravel + Vue (install & agen otomatis); project lama tanpa pilihan platform ikut Laravel (L.jalur_laravel)
export const jalurLaravel = (d) => !d?.saran?.pilihan || d.saran.pilihan.jalur === 'laravel_vue'

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

// Tab yang tersimpan di query URL (?nama=nilai) supaya tautan yang dibagikan langsung membuka tab itu.
// Nilai bawaan tidak ditulis ke URL; pindah tab memakai router.replace (tidak menumpuk riwayat Back).
// sendiri = true: query lain (tab bagian dalam tahap sebelumnya) dibuang saat tab ini berganti.
// boleh = daftar nilai sah; nilai lain di URL (tautan lama/salah ketik) jatuh ke bawaan.
let queryTunda = null
export function tabUrl(nama, bawaan = '', { sendiri = false, boleh = null } = {}) {
  const route = useRoute()
  const router = useRouter()
  return computed({
    get: () => {
      const v = route.query[nama]
      return typeof v === 'string' && v && (!boleh || boleh.includes(v)) ? v : bawaan
    },
    set: (v) => {
      // Beberapa set dalam satu klik (mis. ?tahap= lalu ?hal=1): route.query belum berubah sampai navigasi selesai,
      // jadi pakai query yang sedang dikirim supaya set kedua tidak menghapus hasil set pertama.
      const query = sendiri ? {} : { ...(queryTunda || route.query) }
      if (!v || v === bawaan) delete query[nama]
      else query[nama] = v
      queryTunda = query
      router.replace({ query, hash: route.hash }).finally(() => { if (queryTunda === query) queryTunda = null })
    },
  })
}
