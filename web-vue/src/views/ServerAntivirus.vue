<script setup>
// Antivirus server hosting (sub-menu Server): scan berkas akun dengan tanda tangan Velocity (VD.*), deteksi cPGuard
// 30 hari sebagai pembanding, dan karantina manual. Data: GET /api/servers/antivirus (installer_status.py →
// scripts/server_antivirus_agent.py lewat SSH), scan: GET/POST /api/servers/antivirus/scan, aksi karantina:
// POST /api/servers/antivirus/aksi (dicatat di riwayat). Tidak ada karantina otomatis — semua temuan hanya dilaporkan.
import PilihServer from '../components/PilihServer.vue'
import { pilihServer } from '../jenisServer.js'
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import Ikon from '../components/Ikon.vue'
import PelakuAkun from '../components/PelakuAkun.vue'
import { namaAkun } from '../akun.js'
import Info from '../components/Info.vue'
import Dialog from '../components/Dialog.vue'
import GrafikBatangTumpuk from '../components/GrafikBatangTumpuk.vue'
import { konfirmasi } from '../konfirmasi.js'
import { minta, kirim, pakaiPolling, tanggalWaktu, waktuLalu, angka, ukuranBerkas } from '../api.js'
import { tabUrl } from '../laravel.js'

const av = pakaiPolling('/api/servers/antivirus', 300000)
const daftarScan = pakaiPolling('/api/servers/antivirus/scan', 0)
const riwayat = pakaiPolling('/api/servers/antivirus/riwayat', 0)
const segarkan = ref(false)
async function muatSegar() {
  segarkan.value = true
  try { av.data.value = await minta('/api/servers/antivirus?segar=1'); av.galat.value = null }
  catch (e) { av.galat.value = e }
  finally { segarkan.value = false }
  daftarScan.muatUlang()
  riwayat.muatUlang()
}
const servers = computed(() => av.data.value?.servers || [])
const pilih = pilihServer()
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || servers.value[0] || null)
const TAB = ['scan', 'analisis-ai', 'cpguard', 'karantina', 'riwayat']
const tab = tabUrl('tab', 'scan', { boleh: [...TAB, 'judi'] })
// Tautan lama ?tab=judi (notif Telegram sebelum 19 Okt) → nama baru
if (tab.value === 'judi') tab.value = 'analisis-ai'

// Nama pelaku dipakai bersama halaman Proteksi
// Pelaku di riwayat = akun yang masuk ke dash.velocity.ai.id (backend menggantinya dari cookie sesi)
const oleh = namaAkun

const PESAN = {
  invalid_oleh: 'Masuk dulu lewat tombol "Masuk dengan VD.net" di kanan atas — setiap scan & karantina dicatat atas nama akun Anda.',
  login_diperlukan: 'Sesi login habis atau belum masuk. Klik "Masuk dengan VD.net" di kanan atas.',
  server_tidak_dikenal: 'Server tidak dikenal; muat ulang halaman.',
  akun_tidak_dikenal: 'Akun tidak ada di server ini.',
  hari_tidak_sah: 'Scan semua akun wajib dibatasi berkas yang berubah N hari terakhir.',
  semua_akun_perlu_batas_hari: 'Scan semua akun wajib dibatasi berkas yang berubah N hari terakhir.',
  scan_sedang_jalan: 'Masih ada scan berjalan di server ini. Tunggu selesai atau hentikan dulu.',
  scan_tidak_jalan: 'Scan sudah tidak berjalan.',
  path_tidak_sah: 'Hanya berkas di /home/<akun>/domains/ yang bisa dikarantina.',
  berkas_tidak_ada: 'Berkas sudah tidak ada (mungkin sudah dihapus/dikarantina).',
  lokasi_asal_terisi: 'Lokasi asal sudah berisi berkas lain — tidak ditimpa.',
  folder_asal_hilang: 'Folder asal sudah tidak ada.',
  karantina_tidak_ada: 'Entri karantina tidak ditemukan.',
  bukan_aman: 'Berkas ini tidak sedang ditandai aman.',
  salin_gagal: 'Salinan karantina tidak cocok — berkas asli tidak disentuh.',
  bukan_hitam: 'Sudah tidak ada di daftar ingat karantina.',
  berkas_berubah: 'Isi berkas sudah berubah sejak scan — tidak dikarantina.',
  admin_asli_tidak_ada: 'Semua admin terpilih untuk dihapus — sisakan minimal satu admin asli.',
  multisite_tidak_didukung: 'WordPress multisite belum didukung — bersihkan manual.',
  cadangan_gagal: 'Cadangan database gagal — tidak ada yang diubah.',
  user_tidak_ada: 'Sebagian admin sudah tidak ada — muat ulang hasil scan.',
  wp_config_tidak_terbaca: 'wp-config.php tidak terbaca (DB_NAME/prefix tidak ditemukan).',
  id_user_tidak_sah: 'ID admin tidak sah.',
  terputus: 'Terputus (layanan dashboard di-restart saat scan berjalan).',
  dihentikan: 'Dihentikan.',
  waktu_habis: 'Berhenti karena batas waktu 58 menit — sebagian berkas belum dipindai.',
  maks_temuan: 'Berhenti di 3.000 temuan.',
  forbidden: 'Ditolak: hanya bisa dijalankan dari halaman dashboard ini.',
  timeout: 'Server tidak menjawab (timeout).',
  da_gagal: 'DirectAdmin menolak perintah suspend/unsuspend.',
  sedang_berjalan: 'Analisis AI masih berjalan di server ini.',
  tidak_berjalan: 'Penilaian sudah selesai.',
  scan_tidak_ada: 'Scan tidak ditemukan atau belum selesai.',
  bukan_putih: 'Path ini tidak ada di whitelist.',
  mode_tidak_sah: 'Mode tidak dikenal.',
}
const pesanGalat = (e) => PESAN[e] || e || 'gagal'
const pesan = reactive({ teks: '', galat: false })
const proses = ref(false)

function perluNama() {
  if (oleh.value.trim()) return false
  Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true })
  document.getElementById('nama-antivirus')?.focus()
  return true
}

// ---- Ringkasan semua server ----
const tglLokal = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const hariLalu = (n) => tglLokal(new Date(Date.now() - n * 86400000))
const cpgJumlah = (s, n) => Object.entries(s?.cpguard?.per_hari || {}).reduce((a, [t, v]) => a + (t >= hariLalu(n - 1) ? v : 0), 0)
const scanServer = (host) => (daftarScan.data.value?.scan || []).filter((j) => j.host === host)
const scanTerakhir = (host) => scanServer(host).find((j) => j.status === 'selesai')
// Ringkasan kartu untuk server terpilih saja
// Virus/curiga/besar = gabungan semua scan yang belum ditangani (bukan aman, bukan kini bersih, bukan dikarantina)
const total = computed(() => {
  const s = terpilih.value
  const g = gabungan.value?.host === s.host ? gabungan.value : null
  const belum = (g?.temuan || []).filter((t) => !t.aman && !karantinaPath.value.has(t.path))
  const virus = belum.filter((t) => t.tingkat === 'virus').length
  return {
    virus,
    curiga: belum.length - virus,
    besar: (g?.besar || []).filter((b) => !karantinaPath.value.has(b.path)).length,
    gabung: g?.gabung || 0,
    karantina: s.karantina?.length || 0,
  }
})
function tingkat(s) {
  if (!s.ok) return 'bahaya'
  if (scanTerakhir(s.host)?.jumlah_virus || cpgJumlah(s, 1)) return 'bahaya'
  if (scanTerakhir(s.host)?.jumlah_temuan || cpgJumlah(s, 7)) return 'waspada'
  return 'baik'
}

// ---- Scan ----
const RENTANG = [
  { nilai: 1, label: '24 jam' }, { nilai: 3, label: '3 hari' }, { nilai: 7, label: '7 hari' },
  { nilai: 30, label: '30 hari' }, { nilai: 0, label: 'Semua berkas' },
]
const form = reactive({ akun: 'semua', hari: 1 })
watch(pilih, () => { form.akun = 'semua'; form.hari = 1; lihatId.value = ''; filterTingkat.value = ''; filterJenis.value = ''; filterAi.value = ''; cariTemuan.value = '' })
const akunServer = computed(() => terpilih.value?.akun || [])
const ringkasAtur = computed(() => {
  const j = jadwal.value
  const otomatis = [j.harian && 'harian', j.mingguan && 'mingguan'].filter(Boolean)
  return `scan otomatis ${otomatis.length ? otomatis.join(' + ') : 'mati'} · realtime ${realtime.value.hidup ? `aktif (${rtSetelan.value.mode === 'otomatis' ? 'karantina otomatis' : 'laporan'})` : 'tidak aktif'}`
})
function labelScan(j) {
  const nama = j.akun === 'realtime' ? 'Realtime' : j.akun === 'semua' ? 'Semua akun' : j.akun
  const hasil = j.status === 'berjalan' ? 'berjalan…' : j.status === 'gagal' ? ({ terputus: 'terputus', dihentikan: 'dihentikan' }[j.error] || 'gagal')
    : j.jumlah_temuan ? [j.jumlah_virus && `${j.jumlah_virus} virus`, j.jumlah_temuan - j.jumlah_virus && `${j.jumlah_temuan - j.jumlah_virus} curiga`].filter(Boolean).join(', ') : 'bersih'
  return `${tanggalWaktu(j.mulai)} · ${nama} (${j.akun === 'realtime' ? 'hari ini' : j.ringan ? 'DB & beranda' : labelRentang(j.hari)}) · ${hasil}`
}
const jalanDiServer = computed(() => scanServer(terpilih.value?.host).find((j) => j.status === 'berjalan'))

async function mulaiScan() {
  if (form.akun === 'semua' && form.hari === 0) return fullScan()
  if (perluNama()) return
  proses.value = true
  try {
    const j = await kirim('/api/servers/antivirus/scan', { server: terpilih.value.host, akun: form.akun, hari: form.hari, oleh: oleh.value.trim() })
    Object.assign(pesan, { teks: `Scan dimulai di ${terpilih.value.name}.`, galat: false })
    await daftarScan.muatUlang()
    lihatId.value = j.id
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
async function fullScan() {
  if (perluNama()) return
  const ya = await konfirmasi({
    judul: `Full scan ${terpilih.value.name}?`,
    teks: `Semua akun (${akunServer.value.length}) dan semua berkas, tanpa batas tanggal. Bisa berjam-jam (berhenti sendiri setelah 8 jam), prioritas rendah. Selama berjalan scan lain di server ini tidak bisa dimulai.`,
    tombol: 'Mulai full scan',
  })
  if (!ya) return
  proses.value = true
  try {
    const j = await kirim('/api/servers/antivirus/scan', { server: terpilih.value.host, akun: 'semua', hari: 0, penuh: true, oleh: oleh.value.trim() })
    Object.assign(pesan, { teks: `Full scan dimulai di ${terpilih.value.name}.`, galat: false })
    await daftarScan.muatUlang()
    lihatId.value = j.id
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
async function hentikan(j) {
  const ya = await konfirmasi({ judul: 'Hentikan scan?', teks: 'Berkas yang sudah dipindai tidak disimpan sebagai hasil.', tombol: 'Hentikan', kelas: 'bahaya' })
  if (!ya) return
  try { await kirim('/api/servers/antivirus/henti', { id: j.id }) } catch (e) { Object.assign(pesan, { teks: pesanGalat(e.message), galat: true }) }
  setTimeout(() => daftarScan.muatUlang(), 1500)
}

// Detail scan yang sedang dilihat; scan berjalan disegarkan tiap 3 dtk
const lihatId = ref('')
const detail = ref(null)
// Temuan detail: berkas yang dikarantina sesudah scan penemunya = sudah ditangani (kini 'dikarantina'), sama seperti kartu ringkasan
const temuanDetail = computed(() => {
  const dikarantina = new Map((terpilih.value?.karantina || []).map((k) => [k.path, k.waktu]))
  const mulai = detail.value?.mulai || 0
  return (detail.value?.temuan || []).map((t) => (!t.kini && (karantinaPath.value.has(t.path) || dikarantina.get(t.path) > (t.scan || mulai))
    ? { ...t, kini: 'dikarantina' } : t))
})
const temuanJudol = computed(() => temuanDetail.value.filter((t) => !t.aman && !t.kini && jenisTemuan(t).some((j) => j.label === 'Judi online')))
let timerScan = null
// "Semua scan": temuan semua scan selesai server ini jadi satu daftar; path sama → dari scan terbaru (daftar sudah urut terbaru)
const SEMUA = 'semua'
const scanSelesai = computed(() => scanServer(terpilih.value?.host).filter((j) => j.status === 'selesai'))
async function muatGabungan() {
  const hasil = await Promise.all(scanSelesai.value.map((j) => minta(`/api/servers/antivirus/scan?id=${j.id}`)))
  const temuan = new Map()
  const besar = new Map()
  for (const d of hasil) {
    for (const t of d.temuan || []) if (!temuan.has(t.path) && !t.kini) temuan.set(t.path, { ...t, scan: d.mulai })
    for (const b of d.besar || []) if (!besar.has(b.path)) besar.set(b.path, b)
  }
  // Berkas yang dikarantina sesudah scan yang menemukannya tidak ditampilkan lagi
  const dikarantina = new Map((terpilih.value?.karantina || []).map((k) => [k.path, k.waktu]))
  return {
    id: SEMUA, status: 'selesai', gabung: hasil.length, host: terpilih.value?.host,
    temuan: [...temuan.values()].filter((t) => !(dikarantina.get(t.path) > t.scan)),
    besar: [...besar.values()], hasil: { besar: besar.size },
  }
}
// Gabungan untuk kartu ringkasan, terpisah dari scan yang sedang dilihat
const gabungan = ref(null)
async function muatKartu() {
  if (!scanSelesai.value.length) { gabungan.value = null; return }
  try { gabungan.value = await muatGabungan() } catch { /* kartu tetap angka lama */ }
}
watch(() => `${terpilih.value?.host}|${scanSelesai.value.map((j) => j.id).join()}|${(terpilih.value?.karantina || []).length}`, muatKartu, { immediate: true })
async function muatDetail() {
  if (!lihatId.value) { detail.value = null; return }
  try {
    const d = lihatId.value === SEMUA ? await muatGabungan() : await minta(`/api/servers/antivirus/scan?id=${lihatId.value}`)
    if (d.id === lihatId.value) detail.value = d
    if (d.status !== 'berjalan') {
      clearInterval(timerScan); timerScan = null
      daftarScan.muatUlang()
    }
  } catch (e) { Object.assign(pesan, { teks: pesanGalat(e.message), galat: true }) }
}
// Sesudah aksi berhasil: ringkasan, daftar temuan, kartu, dan riwayat dimuat ulang tanpa refresh halaman
async function segarkanSesudahAksi() {
  // Aksi selesai → jendela aksi ditutup; ringkasan hasil tetap di pesan status atas
  bersih.buka = pratinjau.buka = aksiK.buka = false
  riwayat.muatUlang()
  // Daftar karantina terbaru dulu: "Semua scan" menyaring berkas yang dikarantina sesudah scan penemunya
  await av.muatUlang()
  muatDetail()
  muatKartu()
}
watch([lihatId, () => terpilih.value?.host], () => { // host ikut: ganti server saat "semua" tetap "semua"
  clearInterval(timerScan); timerScan = null
  detail.value = null
  muatDetail()
  timerScan = setInterval(muatDetail, 3000)
})
// Scan berjalan di server lain/terpilih dipantau dari daftar
const timerDaftar = setInterval(() => { if (scanServer(terpilih.value?.host).some((j) => j.status === 'berjalan')) daftarScan.muatUlang() }, 5000)
onBeforeUnmount(() => { clearInterval(timerScan); clearInterval(timerDaftar) })
// Bila belum memilih: buka gabungan semua scan (atau scan berjalan bila belum ada yang selesai)
watch([terpilih, () => daftarScan.data.value], () => {
  if (!lihatId.value && terpilih.value) {
    const j = scanServer(terpilih.value.host)[0]
    if (scanSelesai.value.length) lihatId.value = SEMUA
    else if (j) lihatId.value = j.id
  }
}, { immediate: true })
// Gabungan dimuat ulang saat ada scan baru selesai
watch(() => scanSelesai.value.map((j) => j.id).join(), (baru, lama) => { if (lihatId.value === SEMUA && lama !== undefined && baru !== lama) muatDetail() })

const filterTingkat = ref('')
const cariTemuan = ref('')
const tampilSemua = ref(false)
const karantinaPath = ref(new Set())
const relatif = (p) => (p || '').replace(/^\/home\/[^/]+\/domains\//, '')
// Jenis temuan dari id tanda tangan VD.*; yang pertama cocok menang, sisanya = Malware
// Judi online = TANDA_JUDI di services/server_judi.py (cloaking/alih Google dinilai Judi AI juga)
const JENIS = [
  { re: /Judi|Cloaking|AlihGoogle/, label: 'Judi online', kelas: 'ungu' },
  { re: /Webshell|Uploader|EvalInput|EvalUnduh|LoginPaksa|PluginPalsu/, label: 'Backdoor', kelas: 'teal' },
  { re: /Deface/, label: 'Deface', kelas: 'abu' },
  { re: /AlihReferer|Backlink|LinkHelper/, label: 'SEO spam', kelas: 'abu' },
]
const MALWARE = { label: 'Malware', kelas: 'biru' }
const jenisTemuan = (t) => [...new Map(t.tanda.map((x) => {
  const j = JENIS.find((j) => j.re.test(x.id)) || MALWARE
  return [j.label, j]
})).values()]
const filterJenis = ref('')
const filterAi = ref('')
const AI_PUTUSAN = { berbahaya: ['merah', 'berbahaya'], positif_palsu: ['hijau', 'positif palsu'], cek_manual: ['kuning', 'cek manual'] }
const hitungAi = computed(() => {
  const n = {}
  for (const t of temuanDetail.value) if (!t.aman && !t.kini) { const k = t.ai?.putusan || 'belum'; n[k] = (n[k] || 0) + 1 }
  return n
})
const AI_SARAN = { karantina: 'Karantina', bersihkan_wp: 'Bersihkan WP', bersihkan_db: 'bersihkan lewat wp-admin', tandai_aman: 'Tandai aman', cek_manual: 'cek manual' }
// Hitungan per jenis untuk tombol saring (temuan belum ditandai aman, ikut saring tingkat)
const hitungJenis = computed(() => {
  const out = new Map()
  for (const t of temuanDetail.value) {
    if (t.aman || t.kini || (filterTingkat.value && filterTingkat.value !== 'aman' && t.tingkat !== filterTingkat.value)) continue
    for (const j of jenisTemuan(t)) out.set(j.label, (out.get(j.label) || 0) + 1)
  }
  return [...JENIS, MALWARE].filter((j) => out.has(j.label)).map((j) => ({ ...j, n: out.get(j.label) }))
})
const temuanTersaring = computed(() => {
  const q = cariTemuan.value.trim().toLowerCase()
  return temuanDetail.value
    .filter((t) => (filterTingkat.value === 'kini' ? t.kini : filterTingkat.value === 'aman' ? t.aman && !t.kini
      : !t.aman && !t.kini && (!filterTingkat.value || t.tingkat === filterTingkat.value))
      && (!filterJenis.value || jenisTemuan(t).some((j) => j.label === filterJenis.value))
      && (!filterAi.value || (filterAi.value === 'belum' ? !t.ai : t.ai?.putusan === filterAi.value))
      && (!q || t.path.toLowerCase().includes(q) || t.tanda.some((x) => x.id.toLowerCase().includes(q))
        || jenisTemuan(t).some((j) => j.label.toLowerCase().includes(q))))
    .sort((a, b) => (a.tingkat === b.tingkat ? b.mtime - a.mtime : a.tingkat === 'virus' ? -1 : 1))
})
const hitungTingkat = computed(() => {
  const out = { virus: 0, curiga: 0, aman: 0, kini: 0 }
  for (const t of temuanDetail.value) out[t.kini ? 'kini' : t.aman ? 'aman' : t.tingkat]++
  return out
})
const labelRentang = (h) => (h ? `berubah ${RENTANG.find((r) => r.nilai === h)?.label || `${h} hari`}` : 'semua berkas')
const durasi = (j) => {
  const d = (j.selesai || Math.floor(Date.now() / 1000)) - j.mulai
  return d >= 60 ? `${Math.floor(d / 60)} mnt ${d % 60} dtk` : `${d} dtk`
}

async function karantina(path, alasan) {
  if (perluNama()) return
  const ya = await konfirmasi({
    judul: 'Karantina berkas ini?',
    teks: `${relatif(path)} dipindah ke /root/velocity-karantina di ${terpilih.value.name}. Bila berkas ini dipakai situs (mis. index.php, functions.php), halaman bisa error sampai dibersihkan atau dikembalikan.`,
    tombol: 'Karantina', kelas: 'bahaya',
  })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/antivirus/aksi', { aksi: 'karantina', server: terpilih.value.host, path, alasan, oleh: oleh.value.trim() })
    if (!r.ok) throw new Error(r.error)
    karantinaPath.value = new Set([...karantinaPath.value, path])
    Object.assign(pesan, { teks: `${relatif(path)} dikarantina.`, galat: false })
    segarkanSesudahAksi()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}

// ---- Pratinjau isi berkas (baca saja, tidak dicatat) ----
const pratinjau = reactive({ buka: false, judul: '', path: '', kid: '', alasan: '', bukti: [], memuat: false, data: null, galat: '' })
async function lihatBerkas(path, kid, bukti = [], alasan = '') {
  Object.assign(pratinjau, { buka: true, judul: relatif(path), path, kid: kid || '', alasan, bukti, memuat: true, data: null, galat: '' })
  try {
    const q = new URLSearchParams({ server: terpilih.value.host, path: kid ? '' : path, id: kid || '' })
    const r = await minta(`/api/servers/antivirus/baca?${q}`)
    if (!r.ok) throw new Error(r.error)
    pratinjau.data = r
  } catch (e) {
    pratinjau.galat = pesanGalat(e.message)
  } finally {
    pratinjau.memuat = false
  }
}

// ---- Scan otomatis (per server; jadwal di backend: tiap hari jam_jadwal, Minggu = mingguan) ----
const jadwal = computed(() => av.data.value?.jadwal?.[terpilih.value?.host] || {})
// Watcher realtime (velocity_av_realtime.py) — sama dengan realtime_aktif() di backend: active + detak < 15 mnt
const realtime = computed(() => {
  const st = av.data.value?.realtime?.[terpilih.value?.host] || {}
  const detak = st.detak || null
  const hidup = st.aktif === 'active' && !!detak && Date.now() / 1000 - detak.t < 900
  return { st, detak, hidup, ada: !!detak || st.aktif === 'active' || st.aktif === 'failed', usang: hidup && detak.sidik !== av.data.value?.sidik_agen }
})
// ---- Judi AI (services/server_judi.py): penilaian AI temuan judi sesudah scan otomatis ----
const judi = ref(null)
const judiPutih = ref('')
async function muatJudi() {
  if (!terpilih.value) return
  try {
    judi.value = await minta(`/api/servers/judi?server=${encodeURIComponent(terpilih.value.host)}`)
    judiPutih.value = judi.value.setelan.daftar_putih.join('\n')
  } catch (e) { Object.assign(pesan, { teks: pesanGalat(e.message), galat: true }) }
}
watch([tab, () => terpilih.value?.host], () => { if (tab.value === 'analisis-ai') { judi.value = null; muatJudi() } }, { immediate: true })
// Selama penilaian berjalan: kemajuan dimuat ulang tiap 5 dtk
let timerJudi = null
watch(() => tab.value === 'analisis-ai' && !!judi.value?.berjalan, (jalan) => {
  clearInterval(timerJudi); timerJudi = jalan ? setInterval(muatJudi, 5000) : null
})
onBeforeUnmount(() => clearInterval(timerJudi))
async function bersihkanRiwayatJudi() {
  if (perluNama()) return
  const ya = await konfirmasi({ judul: 'Bersihkan riwayat penilaian?', teks: `Riwayat penilaian AI ${terpilih.value.name} dikosongkan dari tab ini (dipindah ke arsip di server dashboard, tidak dihapus). Tombol "Batalkan suspend" untuk akun yang disuspend AI ikut hilang dari daftar. Saran AI per berkas di daftar scan tetap ada.`, tombol: 'Bersihkan', kelas: 'bahaya' })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/judi/bersihkan', { server: terpilih.value.host, oleh: oleh.value.trim() })
    if (!r.ok) throw new Error(r.error)
    Object.assign(pesan, { teks: `Riwayat dibersihkan (${r.dipindah} baris diarsipkan).`, galat: false })
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
    muatJudi()
  }
}
async function hentiJudi() {
  if (perluNama()) return
  try {
    await kirim('/api/servers/judi/henti', { server: terpilih.value.host, oleh: oleh.value.trim() })
    Object.assign(pesan, { teks: 'Penilaian berhenti sesudah akun yang sedang dinilai selesai. Hasil yang sudah ada tetap tersimpan.', galat: false })
  } catch (e) { Object.assign(pesan, { teks: pesanGalat(e.message), galat: true }) }
  muatJudi()
}
async function aturJudi(ubah, teks) {
  if (perluNama()) return muatJudi()
  if (ubah.mode === 'otomatis') {
    const ya = await konfirmasi({ judul: 'Aktifkan mode otomatis?', teks: `Sesudah scan malam di ${terpilih.value.name}, akun yang dinilai situs judi (yakin ≥90%, tanpa tanda cloaking, beranda pengunjung berisi judi) langsung disuspend — maks ${judi.value.setelan.maks_suspend} per malam — dan berkas penyusup situs yang diretas dikarantina.`, tombol: 'Aktifkan', kelas: 'bahaya' })
    if (!ya) return muatJudi()
  }
  proses.value = true
  try {
    const r = await kirim('/api/servers/judi/setelan', { server: terpilih.value.host, ...ubah, oleh: oleh.value.trim() })
    judi.value = { ...judi.value, setelan: r.setelan }
    Object.assign(pesan, { teks: teks || 'Setelan Judi AI disimpan.', galat: false })
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
    muatJudi()
  }
}
const simpanPutih = () => aturJudi({ daftar_putih: judiPutih.value.split(/[\s,]+/).filter(Boolean) }, 'Daftar putih Judi AI disimpan.')
// semua = temuan judi semua scan yang belum ditangani (bukan aman/dikarantina/akun tersuspend), digabung di backend
async function nilaiUlangJudi(semua = false) {
  if (perluNama()) return
  const scan = semua ? { id: 'semua' } : scanTerakhir(terpilih.value.host)
  const mode = judi.value.setelan.mode
  const ya = await konfirmasi({ judul: semua ? 'Nilai semua temuan yang belum ditangani?' : 'Nilai scan terakhir sekarang?', teks: `${semua ? `Temuan dari ${scanSelesai.value.length} scan digabung (berkas ditandai aman, dikarantina, sudah dinilai, dan akun tersuspend dilewati), lalu dinilai AI per akun — akun judi & virus terbanyak dulu, bisa dihentikan kapan saja.` : `Temuan scan ${tanggalWaktu(scan.mulai)} dinilai AI.`} Saran per berkas tampil di daftar scan. Judi mode ${mode}: ${mode === 'otomatis' ? 'suspend/karantina judi DIJALANKAN bila memenuhi syarat.' : 'hanya laporan, tidak ada yang diubah.'}`, tombol: 'Nilai', kelas: mode === 'otomatis' ? 'bahaya' : '' })
  if (!ya) return
  try {
    await kirim('/api/servers/judi/nilai', { server: terpilih.value.host, scan: scan.id, oleh: oleh.value.trim() })
    Object.assign(pesan, { teks: 'Penilaian berjalan di latar — muat ulang tab ini sebentar lagi.', galat: false })
  } catch (e) { Object.assign(pesan, { teks: pesanGalat(e.message), galat: true }) }
  setTimeout(muatJudi, 2000)
}
async function suspendJudi(d, aksi) {
  if (perluNama()) return
  const ya = await konfirmasi({ judul: aksi === 'suspend' ? `Suspend akun ${d.user}?` : `Batalkan suspend ${d.user}?`, teks: aksi === 'suspend' ? `Semua situs akun ${d.user} di ${terpilih.value.name} berhenti tayang (suspend DirectAdmin).` : `Akun ${d.user} di ${terpilih.value.name} diaktifkan lagi.`, tombol: aksi === 'suspend' ? 'Suspend' : 'Unsuspend', kelas: aksi === 'suspend' ? 'bahaya' : '' })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/judi/aksi', { server: terpilih.value.host, user: d.user, aksi, oleh: oleh.value.trim() })
    Object.assign(pesan, r.ok ? { teks: `${d.user} ${aksi === 'suspend' ? 'disuspend' : 'aktif lagi'}.`, galat: false } : { teks: pesanGalat(r.error), galat: true })
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
    muatJudi()
  }
}
const JENIS_JUDI = { situs_judi: ['merah', 'Situs judi'], diretas: ['kuning', 'Diretas'], berita: ['hijau', 'Berita'], aman: ['hijau', 'Aman'] }
const AKSI_JUDI = { suspend: 'Suspend akun', karantina: 'Karantina berkas', laporan: 'Laporan', dilewati: 'Daftar putih' }
const CATAT_JUDI = { ringkas: 'Penilaian selesai', setelan: 'Setelan diubah', manual: 'Aksi manual', galat: 'Penilaian gagal' }
// Penilaian terbaru per akun (keputusan sudah urut terbaru dulu), paling perlu ditangani di atas
const filterJudi = ref('')
const URUT_JUDI = { situs_judi: 0, diretas: 1, berita: 3, aman: 4 }
const judiAkun = computed(() => {
  const m = new Map()
  for (const d of judi.value?.keputusan || []) if (d.jenis_catat === 'nilai' && !m.has(d.user)) m.set(d.user, d)
  return [...m.values()].sort((a, b) => (URUT_JUDI[a.ai?.jenis] ?? 2) - (URUT_JUDI[b.ai?.jenis] ?? 2)
    || (b.analisis?.berbahaya || 0) - (a.analisis?.berbahaya || 0) || b.t - a.t)
})
// Status tangani per akun dari gabungan semua scan: sisa = temuan belum aman/dikarantina/kini bersih, kecuali positif palsu AI
const filterTangani = ref('')
const sisaAkun = computed(() => {
  const g = gabungan.value?.host === terpilih.value?.host ? gabungan.value : null
  if (!g) return null
  const m = new Map()
  for (const t of g.temuan) {
    if (t.aman || karantinaPath.value.has(t.path)) continue
    const x = m.get(t.user) || { sisa: 0, fp: 0 }
    if (t.ai?.putusan === 'positif_palsu') x.fp++
    else x.sisa++
    m.set(t.user, x)
  }
  return m
})
const tersuspend = (d) => (d.dijalankan === 'suspend' && d.ok) || (d.aksi === 'dilewati' && d.catatan === 'akun sudah tersuspend')
// null = gabungan scan belum termuat
function statusTangani(d) {
  if (tersuspend(d)) return { sudah: true, label: 'Ditangani · tersuspend', sisa: 0, fp: 0 }
  if (!sisaAkun.value) return null
  const x = sisaAkun.value.get(d.user) || { sisa: 0, fp: 0 }
  return { ...x, sudah: !x.sisa, label: x.sisa ? `Belum ditangani · ${x.sisa} sisa` : 'Ditangani' }
}
const judiAkunTersaring = computed(() => judiAkun.value
  .filter((d) => !filterJudi.value || d.ai?.jenis === filterJudi.value)
  .filter((d) => !filterTangani.value || statusTangani(d)?.sudah === (filterTangani.value === 'sudah'))
  // Belum ditangani di atas; urutan jenis dari judiAkun tetap (sort stabil)
  .sort((a, b) => (statusTangani(a)?.sudah ? 1 : 0) - (statusTangani(b)?.sudah ? 1 : 0)))
const jumlahTangani = (sudah) => judiAkun.value.filter((d) => statusTangani(d)?.sudah === sudah).length
const judiLog = computed(() => (judi.value?.keputusan || []).filter((d) => d.jenis_catat !== 'nilai'))
function labelAksiJudi(d) {
  if (d.judi === false) return 'Saran saja'
  if (d.aksi === 'dilewati' && d.catatan === 'akun sudah tersuspend') return 'Sudah tersuspend'
  const a = AKSI_JUDI[d.aksi] || d.aksi
  if (!d.dijalankan) return d.mode === 'laporan' && ['suspend', 'karantina'].includes(d.aksi) ? `Rencana: ${a}` : a
  return `${a} ${d.ok ? '✓' : '✗'}`
}

// ---- Saran aksi per penilaian Judi AI: disusun aturan tetap dari jenis penilaian + temuan scan akun itu ----
const saran = reactive({ buka: false, d: null, memuat: false, galat: '', temuan: [] })
const domainDari = (p) => (p || '').match(/\/domains\/([^/#]+)/)?.[1] || ''
async function bukaSaran(d) {
  Object.assign(saran, { buka: true, d, memuat: true, galat: '', temuan: [] })
  try {
    const job = d.scan === SEMUA ? await muatGabungan() : await minta(`/api/servers/antivirus/scan?id=${d.scan}`)
    saran.temuan = (job.temuan || []).filter((t) => t.user === d.user && !t.aman)
  } catch (e) {
    saran.galat = `Temuan scan tidak bisa dimuat (${pesanGalat(e.message)}) — saran umum saja.`
  } finally {
    saran.memuat = false
  }
}
const langkahSaran = computed(() => {
  const d = saran.d
  if (!d) return []
  const jenis = d.ai?.jenis
  const db = saran.temuan.filter((t) => t.db)
  const web = saran.temuan.filter((t) => t.web)
  const berkas = saran.temuan.filter((t) => !t.db && !t.web)
  const cloak = (d.tanda || []).some((x) => /Cloaking|AlihGoogle|AlihReferer/.test(x))
  const L = []
  // Saran per berkas dari Analisis AI (label "AI: …" di tab Scan); temuan DB tidak bisa ditandai aman
  const ai = (k) => [...berkas, ...db].filter((t) => t.ai?.putusan === k && !karantinaPath.value.has(t.path))
  const fp = ai('positif_palsu')
  if (fp.length) L.push({ judul: `Positif palsu menurut AI: ${fp.length} temuan`, teks: 'Periksa isinya (Lihat), lalu Tandai aman. Pakai Laporkan positif palsu bila polanya sering salah — tim server mendapat notif untuk memperbaiki aturan VD.*. Keduanya terikat isi berkas: bila berubah, terdeteksi lagi.', berkas: fp, mode: 'aman' })
  const jahat = ai('berbahaya').filter((t) => !t.db && !BERKAS_INTI_JUDI.test(t.path))
  if (jahat.length) L.push({ judul: `Berbahaya menurut AI: ${jahat.length} berkas`, teks: 'Lihat isinya dulu, lalu karantina (bisa dikembalikan dari tab Karantina).', berkas: jahat })
  const cek = [...ai('cek_manual'), ...ai('berbahaya').filter((t) => t.db || BERKAS_INTI_JUDI.test(t.path))]
  if (cek.length) L.push({ judul: `Cek manual: ${cek.length} temuan`, teks: 'Berkas sah yang mungkin disisipi kode, entri database berisi spam, atau bukti AI kurang — buka dan bersihkan bagian jahatnya (entri database lewat wp-admin).', berkas: cek, manual: true })
  const semua = [...berkas, ...db]
  if (semua.length && semua.every((t) => t.ai?.putusan === 'positif_palsu') && !web.length) {
    L.push({ judul: 'Tidak ada yang perlu dibersihkan', teks: 'Semua temuan akun ini dinilai AI sebagai positif palsu.' })
    return L
  }
  if (d.judi === false && jenis !== 'diretas') return L.length ? L : [{ judul: 'Belum ada saran per berkas', teks: 'Temuan akun ini belum dinilai AI per berkas — jalankan "Nilai semua yang belum ditangani".' }]
  if (jenis === 'berita' || jenis === 'aman') {
    L.push({ judul: 'Tidak perlu dibersihkan', teks: 'Kata judi berasal dari konten sah (artikel berita, imbauan, atau daftar spam plugin), bukan sisipan penyusup.' })
    L.push({ judul: 'Hentikan penilaian ulang', teks: 'Bila akun ini selalu dinilai ulang (mis. portal berita), masukkan ke daftar putih Analisis AI. Temuan per entri bisa ditandai aman di langkah atas.', putih: true })
    return L
  }
  if (jenis === 'situs_judi') {
    L.push({ judul: 'Pastikan pemilik akun', teks: 'Situs ini sendiri situs judi, bukan korban. Cek data klien di CRM/WHMCS sebelum bertindak.' })
    L.push({ judul: 'Suspend akun', teks: 'Pakai tombol Suspend manual di baris penilaian bila memang bukan klien sah / melanggar S&K.' })
  }
  if (jenis === 'diretas' || jenis === 'situs_judi') {
    for (const t of db) {
      const dom = domainDari(t.path)
      const post = /_posts$/.test(t.db.tabel) && dom
      L.push({
        judul: `Bersihkan database: ${t.db.tabel} #${t.db.id}`,
        teks: `${t.db.judul || '(tanpa judul)'} — hapus teks/tautan judi${post ? ' lewat editor WordPress' : ' lewat phpMyAdmin (bukan tabel posts)'}. Bukti: ${t.tanda.map((x) => x.bukti).join(' … ').slice(0, 160)}`,
        tautan: post ? `https://${dom}/wp-admin/post.php?post=${t.db.id}&action=edit` : '',
      })
    }
    for (const t of web) {
      L.push({ judul: `Cari sumber sisipan di beranda ${t.web.domain}`, teks: 'Konten judi tampil di beranda: periksa widget/menu, footer & header tema (footer.php, header.php, functions.php), opsi Customizer, dan berkas yang baru diubah.', tautan: `https://${t.web.domain}/` })
    }
    const virus = berkas.filter((t) => t.tingkat === 'virus' && !t.ai && !BERKAS_INTI_JUDI.test(t.path))
    if (virus.length) L.push({ judul: `Karantina ${virus.length} berkas penyusup`, teks: 'Berkas di bawah seluruhnya berbahaya menurut tanda tangan VD.* — lihat isinya dulu, lalu karantina.', berkas: virus })
    const inti = berkas.filter((t) => BERKAS_INTI_JUDI.test(t.path))
    if (inti.length) L.push({ judul: `Bersihkan manual ${inti.length} berkas inti`, teks: 'index.php / wp-config.php / .htaccess / wp-admin / wp-includes jangan dikarantina (situs mati) — hapus sisipannya, atau ganti wp-admin & wp-includes dengan salinan WordPress asli.', berkas: inti, manual: true })
    if (cloak) L.push({ judul: 'Hapus cloaking & minta Google index ulang', teks: 'Situs menampilkan isi berbeda ke Googlebot/pengunjung dari Google: cek .htaccess dan kode yang memeriksa User-Agent/Referer. Sesudah bersih, URL Inspection → Request indexing di Google Search Console.' })
    L.push({ judul: 'Tutup celah masuk', teks: 'Ganti sandi admin WordPress & akun hosting, hapus admin tak dikenal, perbarui plugin/tema rentan (lihat Kerentanan CMS).', tautan: '/server/cms' })
    L.push({ judul: 'Scan ulang akun ini', teks: `Sesudah dibersihkan, jalankan scan akun ${d.user} (semua berkas) di tab Scan untuk memastikan bersih.`, scan: true })
  }
  if (!L.length) L.push({ judul: 'Tidak ada saran', teks: 'Penilaian belum lengkap (bukti gagal diambil / tanpa penilaian AI). Jalankan penilaian ulang.' })
  return L
})
const BERKAS_INTI_JUDI = /(^|\/)(index\.php|wp-config\.php|\.htaccess)$|\/wp-admin\/|\/wp-includes\//
async function putihkanSaran() {
  const user = saran.d.user
  judiPutih.value = [...new Set([...judi.value.setelan.daftar_putih, user])].join('\n')
  await simpanPutih()
  saran.buka = false
}
function scanSaran() {
  form.akun = saran.d.user
  form.hari = 0
  lihatId.value = ''
  saran.buka = false
  tab.value = 'scan'
}

async function aturJadwal(jenis, nilai) {
  if (perluNama()) return
  if (jenis === 'mingguan' && nilai) {
    const ya = await konfirmasi({ judul: 'Aktifkan scan mingguan?', teks: `Tiap Minggu ${av.data.value?.jam_jadwal} semua berkas semua akun di ${terpilih.value.name} dipindai (bisa beberapa jam, prioritas rendah).`, tombol: 'Aktifkan' })
    if (!ya) return
  }
  proses.value = true
  try {
    const r = await kirim('/api/servers/antivirus/jadwal', { server: terpilih.value.host, [jenis]: nilai, oleh: oleh.value.trim() })
    av.data.value = { ...av.data.value, jadwal: r.jadwal }
    Object.assign(pesan, { teks: `Scan ${jenis} ${terpilih.value.name} ${nilai ? 'diaktifkan' : 'dimatikan'}.`, galat: false })
    riwayat.muatUlang()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}

// ---- Tandai aman (buatan sendiri / false positive) ----
// Disimpan di dashboard terikat sha256 isi saat ini; berkas yang berubah terdeteksi lagi di scan berikutnya.
// shortcut: label AMAN di tab cPGuard hanya mencocokkan path (cPGuard tak memberi hash), cek ulang bila berkas berubah.
const amanServer = computed(() => av.data.value?.aman?.[terpilih.value?.host] || {})
async function tandaiAman(path, aksi = 'aman', alasan = '', sha256 = '') {
  if (perluNama()) return
  const ya = await konfirmasi(aksi === 'aman'
    ? { judul: 'Tandai berkas ini aman?', teks: `${relatif(path)} tidak dihitung lagi sebagai temuan selama isinya sama persis. Bila berkas berubah, akan terdeteksi lagi.`, tombol: 'Tandai aman' }
    : { judul: 'Batalkan status aman?', teks: `${relatif(path)} kembali dihitung sebagai temuan.`, tombol: 'Batalkan aman', kelas: 'bahaya' })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/antivirus/aksi', { aksi, server: terpilih.value.host, path, alasan, sha256, oleh: oleh.value.trim() })
    if (!r.ok) throw new Error(r.error)
    Object.assign(pesan, { teks: aksi === 'aman' ? `${relatif(path)} ditandai aman.` : `Status aman ${relatif(path)} dibatalkan.`, galat: false })
    pratinjau.buka = false
    if (aksi === 'aman') saran.temuan = saran.temuan.filter((x) => x.path !== path)
    segarkanSesudahAksi()
    daftarScan.muatUlang()
    riwayat.muatUlang()
    muatDetail()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}

// Cek ulang temuan satu akun sekarang (hanya baca) — tanpa menunggu periksa ulang harian
const cekUlangAkun = ref('')
async function cekUlang(akun) {
  cekUlangAkun.value = akun
  try {
    const r = await kirim('/api/servers/antivirus/cek_ulang', { server: terpilih.value.host, akun })
    if (!r.ok) throw new Error(r.error)
    Object.assign(pesan, { teks: `Akun ${akun}: ${r.diperiksa} temuan diperiksa ulang.`, galat: false })
    muatDetail()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    cekUlangAkun.value = ''
  }
}

// Laporan positif palsu dari temuan scan (berkas masih di tempat): ditandai aman + notif tim server
async function laporFpTemuan(t) {
  if (perluNama()) return
  const ya = await konfirmasi({ judul: 'Laporkan positif palsu?', teks: `${relatif(t.path)} ditandai aman (selama isinya sama) dan dilaporkan ke Telegram tim server untuk perbaikan aturan ${t.tanda.map((x) => x.id).join(', ')}.`, tombol: 'Laporkan' })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/antivirus/aksi', { aksi: 'laporan_fp', server: terpilih.value.host, path: t.path, sha256: t.db ? t.sha256 : '', tanda: t.tanda.map((x) => x.id).join(', '),
      alasan: `AI: ${t.ai?.alasan || '-'}`.slice(0, 300), oleh: oleh.value.trim() })
    if (!r.ok) throw new Error(r.error)
    Object.assign(pesan, { teks: `${relatif(t.path)} dilaporkan positif palsu & ditandai aman.`, galat: false })
    saran.temuan = saran.temuan.filter((x) => x.path !== t.path)
    segarkanSesudahAksi()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}

// ---- Karantina ----
async function aksiKarantina(k, aksi) {
  if (perluNama()) return
  const ya = await konfirmasi(aksi === 'kembalikan'
    ? { judul: 'Kembalikan berkas?', teks: `${relatif(k.path)} dipulihkan ke lokasi asal dengan pemilik & izin semula.`, tombol: 'Kembalikan' }
    : { judul: 'Hapus permanen?', teks: `Salinan karantina ${relatif(k.path)} dihapus dan tidak bisa dikembalikan.`, tombol: 'Hapus permanen', kelas: 'bahaya' })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/antivirus/aksi', { aksi, server: terpilih.value.host, id: k.id, oleh: oleh.value.trim() })
    if (!r.ok) throw new Error(r.error)
    Object.assign(pesan, { teks: aksi === 'kembalikan' ? `${relatif(k.path)} dikembalikan.` : 'Salinan karantina dihapus.', galat: false })
    if (aksi === 'kembalikan') karantinaPath.value = new Set([...karantinaPath.value].filter((p) => p !== k.path))
    segarkanSesudahAksi()
    riwayat.muatUlang()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}

// ---- Aksi karantina lewat dialog: lihat, kembalikan, hapus, laporkan positif palsu, whitelist berkas/folder, batal ----
const aksiK = reactive({ buka: false, k: null, pilih: '', catatan: '', folder: '' })
const PILIHAN_K = [
  { k: 'lihat', label: 'Lihat isi', teks: 'Baca salinan di karantina (tidak mengubah apa pun).' },
  { k: 'kembalikan', label: 'Kembalikan', teks: 'Pulihkan ke lokasi asal dengan pemilik & izin semula. Scan berikutnya bisa menandainya lagi.' },
  { k: 'hapus', label: 'Hapus permanen', teks: 'Salinan karantina dihapus, tidak bisa dikembalikan.', bahaya: true },
  { k: 'fp', label: 'Laporkan positif palsu', teks: 'Dicatat & dikirim ke Telegram tim server untuk perbaikan aturan, berkas dikembalikan dan ditandai aman (selama isinya sama).' },
  { k: 'putih_berkas', label: 'Whitelist berkas', teks: 'Berkas dikembalikan dan path ini tidak pernah diperiksa lagi (watcher, scan, periksa ulang) walau isinya berubah.' },
  { k: 'putih_folder', label: 'Whitelist folder', teks: 'Berkas dikembalikan dan semua isi folder di bawah ini tidak pernah diperiksa lagi.' },
]
function bukaAksiK(k) {
  Object.assign(aksiK, { buka: true, k, pilih: '', catatan: '', folder: k.path.split('/').slice(0, -1).join('/') })
}
async function jalankanAksiK() {
  const { k, pilih } = aksiK
  if (pilih === 'lihat') { aksiK.buka = false; return lihatBerkas(k.path, k.id) }
  if (pilih === 'kembalikan' || pilih === 'hapus') { aksiK.buka = false; return aksiKarantina(k, pilih) }
  if (perluNama()) return
  const folder = pilih === 'putih_folder'
  const data = pilih === 'fp'
    ? { aksi: 'laporan_fp', id: k.id, path: k.path, tanda: k.alasan, alasan: aksiK.catatan }
    : { aksi: 'putih', id: k.id, path: folder ? aksiK.folder.trim() : k.path, jenis: folder ? 'folder' : 'berkas', alasan: aksiK.catatan }
  proses.value = true
  try {
    const r = await kirim('/api/servers/antivirus/aksi', { ...data, server: terpilih.value.host, oleh: oleh.value.trim() })
    if (!r.ok) throw new Error(r.error)
    Object.assign(pesan, { teks: pilih === 'fp' ? `Positif palsu dilaporkan — ${relatif(k.path)} dikembalikan & ditandai aman.`
      : `${relatif(data.path)} masuk whitelist ${data.jenis} — ${relatif(k.path)} dikembalikan.`, galat: false })
    karantinaPath.value = new Set([...karantinaPath.value].filter((p) => p !== k.path))
    aksiK.buka = false
    segarkanSesudahAksi()
    riwayat.muatUlang()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
// ---- Bersihkan WP (temuan VD.DB.Admin*): karantina plugin samaran, hapus admin siluman, ganti salt + putus sesi ----
const KINI = {
  bersih: ['KINI BERSIH', 'Diperiksa ulang dengan aturan VD.* terbaru: tidak terdeteksi lagi'],
  hilang: ['BERKAS HILANG', 'Berkas sudah tidak ada di server'],
  dikarantina: ['DIKARANTINA', 'Berkas sudah dipindah ke karantina sesudah scan ini'],
  dibersihkan: ['SUDAH DIBERSIHKAN', 'Admin ini sudah dihapus / dijadikan subscriber lewat Bersihkan WP sesudah scan ini'],
  admin_hilang: ['SUDAH DITANGANI', 'Diperiksa ulang: admin ini sudah tidak ada / bukan administrator lagi, atau WordPress-nya (wp-config.php) sudah hilang'],
}
const adminTemuan = (t) => t.db && t.tanda.some((x) => /^VD\.DB\.Admin/.test(x.id))
// Per admin: hapus | subscriber | '' (biarkan). Bawaan: siluman (virus) dihapus, pola nama+angka (curiga) jadi subscriber
const bersih = reactive({ buka: false, akar: '', admin: [], aksiUser: {}, plugin: true, salt: true, hasil: null })
const bersihId = (aksi) => Object.keys(bersih.aksiUser).filter((id) => bersih.aksiUser[id] === aksi)
function bukaBersih(t) {
  const akar = t.path.split('#')[0]
  const admin = temuanDetail.value.filter((x) => adminTemuan(x) && !x.kini && x.path.split('#')[0] === akar)
  const aksiUser = Object.fromEntries(admin.map((x) => [x.db.id, x.tingkat === 'virus' ? 'hapus' : 'subscriber']))
  Object.assign(bersih, { buka: true, akar, admin, aksiUser, plugin: true, salt: true, hasil: null })
}
async function jalankanBersih() {
  if (perluNama()) return
  const ya = await konfirmasi({
    judul: 'Bersihkan WordPress ini?',
    teks: `${relatif(bersih.akar)}: hapus ${bersihId('hapus').length} admin (postingannya dialihkan ke admin asli), jadikan subscriber ${bersihId('subscriber').length}${bersih.plugin ? ', karantina plugin samaran' : ''}${bersih.salt ? ', ganti salt & semua pengguna logout' : ''}. Tabel users/usermeta & wp-config.php dicadangkan dulu di /root/velocity-bersih.`,
    tombol: 'Bersihkan', kelas: 'bahaya',
  })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/antivirus/aksi', { aksi: 'bersihkan_wp', server: terpilih.value.host, akar: bersih.akar, hapus_user: bersihId('hapus'), turunkan_user: bersihId('subscriber'),
      plugin: bersih.plugin, salt: bersih.salt, oleh: oleh.value.trim() })
    bersih.hasil = r
    if (r.error === 'user_tidak_ada') throw new Error(`Admin #${(r.id || []).join(', #')} sudah tidak ada di database (sudah dihapus sebelumnya). Tutup jendela ini; daftar temuan dimuat ulang.`)
    if (!r.ok) throw new Error(r.error)
    for (const k of r.karantina || []) if (k.ok) karantinaPath.value = new Set([...karantinaPath.value, k.path])
    Object.assign(pesan, { teks: `${relatif(bersih.akar)} dibersihkan — ${r.hapus_user.length} admin dihapus, ${(r.turun_user || []).length} jadi subscriber, ${(r.karantina || []).filter((k) => k.ok).length} berkas dikarantina, salt ${r.salt}/8. Jalankan scan akun ini lagi untuk memastikan.`, galat: false })
    segarkanSesudahAksi()
    riwayat.muatUlang()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
    if (bersih.hasil?.error === 'user_tidak_ada') muatDetail()
  } finally {
    proses.value = false
  }
}
const rtSetelan = computed(() => av.data.value?.rt_setelan?.[terpilih.value?.host] || {})
const putihServer = computed(() => rtSetelan.value.putih || [])
const daftarHitam = computed(() => Object.entries(av.data.value?.hitam || {}).map(([sha256, h]) => ({ sha256, ...h })).sort((a, b) => (b.t || 0) - (a.t || 0)))
async function lupakanHitam(h) {
  if (perluNama()) return
  const ya = await konfirmasi({ judul: 'Lupakan karantina ini?', teks: `Berkas berisi sama dengan ${relatif(h.path)} tidak lagi dikarantina otomatis (tetap terdeteksi scan bila kena aturan VD.*).`, tombol: 'Lupakan', kelas: 'bahaya' })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/antivirus/aksi', { aksi: 'lupakan', server: terpilih.value.host, sha256: h.sha256, oleh: oleh.value.trim() })
    if (!r.ok) throw new Error(r.error)
    Object.assign(pesan, { teks: `${relatif(h.path)} dilupakan.`, galat: false })
    segarkanSesudahAksi()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
async function hapusPutih(w) {
  if (perluNama()) return
  const ya = await konfirmasi({ judul: 'Keluarkan dari whitelist?', teks: `${relatif(w.path)} kembali diperiksa watcher & scan.`, tombol: 'Keluarkan', kelas: 'bahaya' })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/antivirus/aksi', { aksi: 'batal_putih', server: terpilih.value.host, path: w.path, oleh: oleh.value.trim() })
    if (!r.ok) throw new Error(r.error)
    Object.assign(pesan, { teks: `${relatif(w.path)} dikeluarkan dari whitelist.`, galat: false })
    segarkanSesudahAksi()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
async function aturRtMode(mode) {
  if (perluNama()) return av.muatUlang()
  if (mode === 'otomatis') {
    const ya = await konfirmasi({ judul: 'Aktifkan karantina otomatis?', teks: `Berkas di ${terpilih.value.name} yang kena aturan sangat yakin (eval kode unduhan, include unduhan, webshell, plugin samaran, eksekusi input, login paksa) langsung dikarantina begitu ditulis. Berkas inti (index.php, wp-config.php, .htaccess, wp-admin, wp-includes) tetap hanya dilaporkan. Semua bisa dikembalikan dari tab Karantina.`, tombol: 'Aktifkan', kelas: 'bahaya' })
    if (!ya) return av.muatUlang()
  }
  proses.value = true
  try {
    await kirim('/api/servers/antivirus/realtime', { server: terpilih.value.host, mode, oleh: oleh.value.trim() })
    Object.assign(pesan, { teks: `Karantina otomatis ${mode === 'otomatis' ? 'aktif' : 'mati (laporan saja)'} di ${terpilih.value.name} — berlaku di server ≤ 3 menit.`, galat: false })
    segarkanSesudahAksi()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}

// ---- Deteksi cPGuard ----
// Arti cleanup_status ditebak dari pola data (bukan dokumentasi resmi) → label + kode asli di tooltip
const CLEANUP = { '-1': ['ungu', 'Ditindak'], '100': ['hijau', 'Dibersihkan'], '-100': ['merah', 'Dihapus'], '0': ['abu', 'Dilaporkan'] }
const labelCleanup = (c) => CLEANUP[String(c)] || ['abu', c == null ? '-' : `Kode ${c}`]
const cariCpg = ref('')
const tampilSemuaCpg = ref(false)
watch(pilih, () => { cariCpg.value = ''; tampilSemuaCpg.value = false })
const cpgTersaring = computed(() => {
  const q = cariCpg.value.trim().toLowerCase()
  return (terpilih.value?.cpguard?.deteksi || []).filter((d) => !q || d.path.toLowerCase().includes(q)
    || (d.definisi || '').toLowerCase().includes(q) || (d.user || '').includes(q))
})
const cpgAkun = computed(() => (terpilih.value?.cpguard?.per_akun || []).slice(0, 8))
const SERI_CPG = [{ kunci: 'n', label: 'Deteksi cPGuard', warna: '#cc7a33' }]
const cpgHari = computed(() => {
  const per = terpilih.value?.cpguard?.per_hari || {}
  return Array.from({ length: 30 }, (_, i) => { const t = hariLalu(29 - i); return { tgl: t, nilai: { n: per[t] || 0 } } })
})
const puncakCpg = computed(() => [...cpgHari.value].sort((a, b) => b.nilai.n - a.nilai.n).filter((h) => h.nilai.n).slice(0, 3).map((h) => h.tgl))
const formatTgl = (t) => new Date(`${t}T00:00`).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })
const ringkasDefinisi = (d) => (d || '').replace(/^\{(HEX|CPG)\}/, '').replace(/\.UNOFFICIAL$/, '').replace(/^Malware\.Expert\./, '')

const riwayatServer = computed(() => (riwayat.data.value?.riwayat || []).filter((r) => !terpilih.value || r.host === terpilih.value.host))
const AKSI_LABEL = { karantina: ['merah', 'Karantina'], kembalikan: ['hijau', 'Kembalikan'], hapus: ['abu', 'Hapus permanen'], aman: ['hijau', 'Tandai aman'], batal_aman: ['abu', 'Batal aman'], jadwal: ['biru', 'Scan otomatis'], bersihkan_wp: ['merah', 'Bersihkan WP'], lupakan: ['abu', 'Lupakan karantina'] }
const namaTanda = (id) => (terpilih.value?.tanda || []).find((t) => t.id === id)?.nama || id
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Antivirus Server <span class="merek-guard">VelocityGuard</span></h1>
        <p class="redup">Pindai berkas situs klien dengan tanda tangan Velocity, bandingkan dengan deteksi cPGuard, dan karantina berkas jahat secara manual.</p>
      </div>
      <div class="kepala-aksi">
        <div class="nama-saya"><span class="redup">Dicatat sebagai</span><PelakuAkun id="nama-antivirus" /></div>
        <button type="button" class="tombol kecil" :disabled="segarkan || (av.memuat.value && !av.data.value)" @click="muatSegar"><Ikon nama="ulang" :ukuran="16" /> {{ segarkan ? 'Membaca…' : 'Muat ulang' }}</button>
      </div>
    </header>

    <div v-if="av.memuat.value && !av.data.value" class="skeleton" aria-busy="true">
      <p class="redup status-muat" role="status">Membaca data antivirus semua server lewat SSH (±5–20 detik)…</p>
      <div class="ringkas">
        <div v-for="i in 4" :key="i" class="kartu tile"><span class="sk sk-ikon" /><div><span class="sk sk-teks" /><span class="sk sk-angka" /><span class="sk sk-teks pendek" /></div></div>
      </div>
      <div class="sk-menu"><span v-for="i in 5" :key="i" class="sk sk-pil" /></div>
      <section class="kartu">
        <span class="sk sk-judul" />
        <div v-for="i in 5" :key="i" class="sk-baris"><span v-for="j in 5" :key="j" class="sk" /></div>
      </section>
    </div>

    <p v-else-if="av.galat.value && !av.data.value" class="pesan-status bahaya">Gagal memuat: {{ av.galat.value.message }}</p>
    <p v-else-if="av.data.value?.error" class="pesan-status bahaya">Gagal memuat: {{ pesanGalat(av.data.value.error) }}</p>

    <template v-else-if="av.data.value">
      <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>

      <PilihServer v-if="terpilih" :servers="servers" :model-value="terpilih?.name" :titik="tingkat(terpilih)" :teks="(s) => s.name + (scanServer(s.host).some((j) => j.status === 'berjalan') ? ' · scan berjalan' : '')" @update:model-value="pilih = $event" />

      <template v-if="terpilih">
        <section v-if="!terpilih.ok" class="kartu">
          <p class="pesan-status bahaya">Tidak bisa dibaca: {{ pesanGalat(terpilih.error) }}</p>
        </section>
        <div v-if="terpilih.ok" class="ringkas">
            <div class="kartu tile">
              <span class="tile-ikon merah"><Ikon nama="virus" :ukuran="20" /></span>
              <div><span class="redup">Virus belum ditangani</span><b>{{ angka(total.virus) }}</b><small class="redup">{{ angka(total.curiga) }} berkas mencurigakan · {{ angka(total.gabung) }} scan</small></div>
            </div>
            <div class="kartu tile">
              <span class="tile-ikon kuning"><Ikon nama="peringatan" :ukuran="20" /></span>
              <div><span class="redup">Berkas besar</span><b>{{ angka(total.besar) }}</b><small class="redup">hanya awal+akhir dibaca, cek manual</small></div>
            </div>
            <div class="kartu tile">
              <span class="tile-ikon ungu"><Ikon nama="kunci" :ukuran="20" /></span>
              <div><span class="redup">Dikarantina Velocity</span><b>{{ angka(total.karantina) }}</b><small class="redup">bisa dikembalikan</small></div>
            </div>
            <div class="kartu tile">
              <span class="tile-ikon hijau"><Ikon nama="server" :ukuran="20" /></span>
              <div><span class="redup">cPGuard</span><b>{{ terpilih.cpguard_jalan ? 'Jalan' : 'Mati' }}</b><small class="redup">dibaca {{ waktuLalu(av.data.value.diambil) }}</small></div>
            </div>
          </div>
        <section v-if="terpilih.ok" class="kartu" aria-labelledby="judul-detail">
          <div class="kartu-judul">
            <h2 id="judul-detail"><Ikon nama="virus" :ukuran="16" /> {{ terpilih.name }}
              <small class="redup">{{ terpilih.akun.length }} akun · cPGuard {{ terpilih.cpguard ? (terpilih.cpguard_jalan ? 'jalan' : 'TIDAK jalan') : 'tidak terpasang' }}</small>
            </h2>
            <div class="tab" role="tablist" aria-label="Bagian antivirus">
              <button v-for="t in [
                { k: 'scan', label: 'Scan' },
                { k: 'analisis-ai', label: 'Analisis AI' },
                { k: 'cpguard', label: 'Deteksi cPGuard', n: terpilih.cpguard?.deteksi?.length },
                { k: 'karantina', label: 'Karantina', n: terpilih.karantina.length },
                { k: 'riwayat', label: 'Riwayat', n: riwayatServer.length },
              ]" :key="t.k" type="button" role="tab" :aria-selected="tab === t.k" :class="{ aktif: tab === t.k }" @click="tab = t.k">
                {{ t.label }} <span v-if="t.n !== undefined" class="hitung">{{ t.n }}</span>
              </button>
            </div>
          </div>

          <!-- ================= Scan ================= -->
          <template v-if="tab === 'scan'">
            <details class="atur-scan" :open="!scanServer(terpilih.host).length">
              <summary><b>Scan manual &amp; otomatis</b> <span class="redup">· {{ ringkasAtur }}</span></summary>
            <form class="form-scan" @submit.prevent="mulaiScan">
              <label class="isian"><span>Akun</span>
                <select v-model="form.akun">
                  <option value="semua">Semua akun ({{ terpilih.akun.length }})</option>
                  <option v-for="a in akunServer" :key="a.user" :value="a.user">{{ a.user }} — {{ a.domain.filter((d) => !['default', 'sharedip', 'suspended'].includes(d)).join(', ') || '-' }}</option>
                </select>
              </label>
              <fieldset class="pil-durasi">
                <legend>Berkas yang dipindai
                  <Info label="Tentang rentang scan"><p>Berkas yang dibuat/diubah dalam rentang ini (mtime atau ctime). "Semua akun" + "Semua berkas" = full scan (bisa berjam-jam, batas 8 jam). Scan berjalan dengan prioritas rendah (nice/ionice) dan berhenti sendiri setelah 58 menit.</p></Info>
                </legend>
                <label v-for="r in RENTANG" :key="r.nilai" :class="{ aktif: form.hari === r.nilai }">
                  <input v-model="form.hari" type="radio" class="sr" :value="r.nilai"> {{ r.label }}
                </label>
              </fieldset>
              <button type="submit" class="tombol" :disabled="proses || !!jalanDiServer"><Ikon nama="cari" :ukuran="16" /> {{ jalanDiServer ? 'Scan berjalan…' : 'Mulai scan' }}</button>
            </form>
            <p class="redup kaki-form">Hanya melapor — tidak ada berkas yang diubah sampai Anda menekan <b>Karantina</b>. {{ (terpilih.tanda || []).length }} tanda tangan
              <Info label="Daftar tanda tangan"><ul class="daftar-tanda"><li v-for="t in terpilih.tanda" :key="t.id"><span class="lencana" :class="t.tingkat === 'virus' ? 'merah' : 'kuning'">{{ t.tingkat === 'virus' ? 'VIRUS' : 'CURIGA' }}</span> {{ t.nama }}</li></ul></Info>
            </p>

            <fieldset class="jadwal">
              <legend>Scan otomatis <small class="redup">· virus dikirim ke Telegram tim server</small></legend>
              <label class="cek"><input type="checkbox" :checked="!!jadwal.harian" :disabled="proses" @change="aturJadwal('harian', $event.target.checked)">
                <span>Harian {{ av.data.value?.jam_jadwal }} <small class="redup blok">berkas yang berubah 24 jam<template v-if="jadwal.terakhir?.harian"> · terakhir {{ jadwal.terakhir.harian }}</template></small></span></label>
              <label class="cek"><input type="checkbox" :checked="!!jadwal.mingguan" :disabled="proses" @change="aturJadwal('mingguan', $event.target.checked)">
                <span>Mingguan (Minggu {{ av.data.value?.jam_jadwal }}) <small class="redup blok">semua berkas, menggantikan harian hari itu<template v-if="jadwal.terakhir?.mingguan"> · terakhir {{ jadwal.terakhir.mingguan }}</template></small></span></label>
              <p class="realtime-status">
                <span class="titik" :class="realtime.hidup ? 'baik' : realtime.ada ? 'bahaya' : 'abu'" aria-hidden="true" />
                <span><b>Realtime</b>
                  <template v-if="realtime.hidup"> aktif · {{ angka(realtime.detak.diperiksa) }} berkas diperiksa sejak {{ tanggalWaktu(realtime.detak.mulai) }}<template v-if="realtime.detak.overflow"> · <b class="merah-teks">{{ realtime.detak.overflow }}× antrean penuh</b></template>
                    <span v-if="realtime.usang" class="lencana kuning">aturan perlu diperbarui</span></template>
                  <template v-else-if="realtime.ada"> <b class="merah-teks">mati</b> ({{ realtime.st.aktif || realtime.st.galat || 'tanpa detak' }}) — scan harian kembali memeriksa berkas</template>
                  <template v-else> belum terpasang di server ini</template>
                  <small class="redup blok">Berkas yang selesai ditulis langsung diperiksa VD.*; bila aktif, scan harian hanya memeriksa database &amp; beranda.</small></span>
              </p>
              <fieldset class="pil-mode">
                <legend>Saat watcher menemukan malware</legend>
                <label :class="{ aktif: (rtSetelan.mode || 'laporan') === 'laporan' }"><input type="radio" name="mode-rt" class="sr" :checked="(rtSetelan.mode || 'laporan') === 'laporan'" :disabled="proses" @change="aturRtMode('laporan')">
                  <b>Laporan saja</b><small class="redup">Dicatat di daftar & Telegram, karantina manual.</small></label>
                <label :class="{ aktif: rtSetelan.mode === 'otomatis', bahaya: rtSetelan.mode === 'otomatis' }"><input type="radio" name="mode-rt" class="sr" :checked="rtSetelan.mode === 'otomatis'" :disabled="proses" @change="aturRtMode('otomatis')">
                  <b>Karantina otomatis</b><small class="redup">Aturan sangat yakin langsung dikarantina (berkas inti tidak). Bisa dikembalikan.</small></label>
              </fieldset>
              <small v-if="realtime.hidup && rtSetelan.mode === 'otomatis' && realtime.detak.mode !== 'otomatis'" class="redup">Menunggu watcher memakai setelan baru…</small>
            </fieldset>
            </details>

            <!-- Pilih sumber temuan: bawaan "Semua scan" = daftar yang perlu ditangani -->
            <div v-if="scanServer(terpilih.host).length" class="pilih-scan">
              <label class="isian"><span>Tampilkan temuan dari</span>
                <select v-model="lihatId">
                  <option v-if="scanSelesai.length" :value="SEMUA">Semua scan — daftar yang perlu ditangani</option>
                  <option v-for="j in scanServer(terpilih.host).slice(0, 30)" :key="j.id" :value="j.id">{{ labelScan(j) }}</option>
                </select>
              </label>
              <button v-if="jalanDiServer && lihatId !== jalanDiServer.id" type="button" class="tombol garis kecil" @click="lihatId = jalanDiServer.id"><span class="putar" aria-hidden="true" /> Scan berjalan · lihat kemajuan</button>
            </div>
            <p v-else class="redup">Belum pernah di-scan dari dashboard. Mulai dari "Scan manual &amp; otomatis" di atas.</p>

            <!-- Detail scan -->
            <div v-if="detail" class="detail-scan">
              <template v-if="detail.status === 'berjalan'">
                <div class="kemajuan" role="status">
                  <span class="putar besar" aria-hidden="true" />
                  <div>
                    <b>Memindai {{ detail.kemajuan?.akun || '…' }}</b>
                    <span class="redup"> akun {{ detail.kemajuan?.ke || 0 }}/{{ detail.kemajuan?.dari || '?' }} · {{ angka(detail.kemajuan?.berkas) }} berkas dilihat · {{ angka(detail.kemajuan?.dibaca) }} dibaca · {{ angka(detail.kemajuan?.temuan) }} temuan · {{ durasi(detail) }}</span>
                    <div class="garis-jalan"><span :style="{ width: `${detail.kemajuan ? (detail.kemajuan.ke / detail.kemajuan.dari) * 100 : 3}%` }" /></div>
                  </div>
                  <button type="button" class="tombol bahaya kecil" @click="hentikan(detail)">Hentikan</button>
                </div>
              </template>
              <p v-else-if="detail.status === 'gagal'" class="pesan-status bahaya">Scan gagal: {{ pesanGalat(detail.error) }} {{ detail.pesan || '' }}</p>
              <template v-else>
                <p v-if="detail.akun === 'realtime'" class="ringkas-scan"><b>Realtime</b> · berkas yang ditulis {{ tanggalWaktu(detail.selesai).split(' ')[0] }} dan langsung diperiksa saat disimpan · {{ angka(detail.temuan.length) }} temuan</p>
                <p v-else-if="detail.gabung" class="ringkas-scan"><b>{{ angka(hitungTingkat.virus + hitungTingkat.curiga) }} berkas perlu ditangani</b> · gabungan {{ detail.gabung }} scan (berkas yang sama diambil dari scan terbaru)</p>
                <p v-else class="ringkas-scan">
                  <span v-if="detail.ringan" class="lencana biru">DB &amp; beranda</span>
                  <b>{{ detail.akun === 'semua' ? `${detail.hasil.jumlah_akun} akun` : detail.akun }}</b> · {{ labelRentang(detail.hari) }} ·
                  {{ angka(detail.hasil.dibaca) }} berkas dibaca dari {{ angka(detail.hasil.berkas) }} ({{ ukuranBerkas(detail.hasil.byte) }}) · {{ durasi(detail) }}
                  <span v-if="detail.hasil.terpotong" class="lencana kuning">{{ pesanGalat(detail.hasil.terpotong) }}</span>
                </p>
                <template v-if="!detail.temuan.length">
                  <p class="bersih"><Ikon nama="centang" :ukuran="18" /> Bersih dari virus — tidak ada berkas jahat atau mencurigakan.</p>
                  <p v-if="!detail.gabung" class="bersih"><Ikon nama="centang" :ukuran="18" /> Bersih dari judi online (judol) — berkas, database, dan beranda {{ angka(detail.hasil.situs || 0) }} situs (versi pengunjung &amp; Googlebot).</p>
                </template>
                <template v-else>
                  <p v-if="!temuanJudol.length" class="bersih"><Ikon nama="centang" :ukuran="18" /> Bersih dari judi online (judol) — temuan di bawah bukan judol.</p>
                  <p v-else class="pesan-status bahaya">{{ temuanJudol.length }} temuan judi online (judol) — lihat tab Analisis AI untuk penilaian per akun.</p>
                  <p class="langkah">Cara menangani: klik <b>Lihat</b> untuk memeriksa isi berkas, lalu <b>Karantina</b> bila virus (bisa dikembalikan dari tab Karantina) atau <b>Tandai aman</b> bila berkas milik klien.</p>
                  <div class="alat">
                    <input v-model="cariTemuan" type="search" placeholder="Cari path / aturan / jenis" aria-label="Cari temuan">
                    <select v-model="filterTingkat" aria-label="Saring tingkat">
                      <option value="">Semua tingkat ({{ hitungTingkat.virus + hitungTingkat.curiga }})</option>
                      <option value="virus">Virus ({{ hitungTingkat.virus }})</option>
                      <option value="curiga">Curiga ({{ hitungTingkat.curiga }})</option>
                      <option v-if="hitungTingkat.aman || filterTingkat === 'aman'" value="aman">Aman ({{ hitungTingkat.aman }})</option>
                      <option v-if="hitungTingkat.kini || filterTingkat === 'kini'" value="kini">Sudah ditangani / bersih / hilang ({{ hitungTingkat.kini }})</option>
                    </select>
                    <select v-model="filterJenis" aria-label="Saring jenis">
                      <option value="">Semua jenis</option>
                      <option v-for="j in hitungJenis" :key="j.label" :value="j.label">{{ j.label }} ({{ j.n }})</option>
                      <option v-if="filterJenis && !hitungJenis.some((j) => j.label === filterJenis)" :value="filterJenis">{{ filterJenis }} (0)</option>
                    </select>
                    <select v-model="filterAi" aria-label="Saring saran AI">
                      <option value="">Semua saran AI</option>
                      <option v-for="(v, k) in AI_PUTUSAN" :key="k" :value="k">AI: {{ v[1] }} ({{ hitungAi[k] || 0 }})</option>
                      <option value="belum">Belum dinilai AI ({{ hitungAi.belum || 0 }})</option>
                    </select>
                  </div>
                  <div class="tabel-wadah">
                    <table class="tabel">
                      <thead><tr><th scope="col">Berkas</th><th scope="col">Masalah</th><th scope="col">Diubah</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                      <tbody>
                        <tr v-for="t in (tampilSemua ? temuanTersaring : temuanTersaring.slice(0, 100))" :key="t.path">
                          <td class="ket berkas">
                            <span class="lencana" :class="t.tingkat === 'virus' ? 'merah' : 'kuning'">{{ t.tingkat === 'virus' ? 'VIRUS' : 'CURIGA' }}</span>
                            <span v-if="t.kini" class="lencana hijau" :title="KINI[t.kini]?.[1]">{{ KINI[t.kini]?.[0] }}</span>
                            <span v-for="j in jenisTemuan(t)" :key="j.label" class="lencana" :class="j.kelas">{{ j.label }}</span>
                            <span v-if="t.hitam" class="lencana ungu" :title="`Isi sama dengan berkas yang dikarantina ${t.hitam.oleh} · ${tanggalWaktu(t.hitam.t)} (${t.hitam.server}: ${t.hitam.path})`">PERNAH DIKARANTINA</span>
                            <template v-if="t.db"><code>{{ relatif(t.path.split('#')[0]) }} · {{ t.db.tabel }} #{{ t.db.id }}</code>
                              <small class="redup blok">{{ t.user }} <button type="button" class="cek-ulang" :disabled="cekUlangAkun === t.user" :aria-label="`Cek ulang temuan akun ${t.user}`" title="Cek ulang temuan akun ini sekarang (berkas hilang/bersih, admin sudah dihapus)" @click="cekUlang(t.user)"><Ikon nama="ulang" :ukuran="13" /></button> · database {{ t.db.nama }} · {{ t.db.jenis }} · {{ t.db.judul }}</small></template>
                            <template v-else-if="t.web"><code><a :href="`https://${t.web.domain}/`" target="_blank" rel="noopener noreferrer">{{ t.web.domain }}</a> · beranda</code>
                              <small class="redup blok">{{ t.user }} · browser {{ t.web.kode }} · Googlebot {{ t.web.kode_bot }}{{ t.web.alih_bot ? ` → ${t.web.alih_bot}` : '' }} · HP dari Google {{ t.web.kode_hp }}{{ t.web.alih_hp ? ` → ${t.web.alih_hp}` : '' }}</small></template>
                            <template v-else><code>{{ relatif(t.path) }}</code>
                              <small class="redup blok">{{ t.user }} <button type="button" class="cek-ulang" :disabled="cekUlangAkun === t.user" :aria-label="`Cek ulang temuan akun ${t.user}`" title="Cek ulang temuan akun ini sekarang (berkas hilang/bersih, admin sudah dihapus)" @click="cekUlang(t.user)"><Ikon nama="ulang" :ukuran="13" /></button> · {{ ukuranBerkas(t.ukuran) }} · izin {{ t.izin }}</small></template>
                          </td>
                          <td class="ket">
                            <span v-for="x in t.tanda" :key="x.id" class="blok" :title="x.bukti"><b>{{ x.nama }}</b> <small class="redup">{{ x.id }}</small>
                              <code v-if="t.db || t.web" class="bukti">{{ x.bukti }}</code></span>
                            <span v-if="t.ai" class="blok saran-ai" :title="`${t.ai.model} · dinilai ${tanggalWaktu(t.ai.t)}`">
                              <span class="lencana" :class="AI_PUTUSAN[t.ai.putusan]?.[0]">AI: {{ AI_PUTUSAN[t.ai.putusan]?.[1] }} {{ t.ai.yakin }}%</span>
                              saran <b>{{ AI_SARAN[t.ai.saran] || t.ai.saran }}</b><small class="redup blok">{{ t.ai.alasan }}</small></span>
                          </td>
                          <td class="nowrap">{{ tanggalWaktu(t.mtime) }}<small v-if="t.scan" class="redup blok">ditemukan scan {{ tanggalWaktu(t.scan) }}</small><small v-if="Math.abs(t.ctime - t.mtime) > 86400" class="redup blok" title="ctime = saat berkas terakhir ditulis/diubah izinnya; mtime bisa dipalsukan">ctime {{ tanggalWaktu(t.ctime) }}</small></td>
                          <td class="kanan">
                            <small v-if="t.kini === 'dibersihkan'" class="redup">Sudah dihapus / dijadikan subscriber lewat Bersihkan WP</small>
                            <small v-else-if="t.kini === 'admin_hilang'" class="redup">Sudah ditangani manual / situs sudah hilang</small>
                            <button v-else-if="adminTemuan(t)" type="button" class="tombol bahaya kecil" :disabled="proses" @click="bukaBersih(t)">Bersihkan WP</button>
                            <template v-else-if="t.db && !t.aman"><small class="redup blok">Bersihkan lewat wp-admin situs</small>
                              <button type="button" class="tombol garis kecil" :disabled="proses" @click="tandaiAman(t.path, 'aman', t.ai ? `AI: ${t.ai.alasan}`.slice(0, 200) : '', t.sha256)">Tandai aman</button></template>
                            <small v-else-if="t.web" class="redup">Cari sumbernya di temuan berkas/DB akun ini</small>
                            <span v-else-if="karantinaPath.has(t.path)" class="lencana ungu">DIKARANTINA</span>
                            <template v-else-if="t.aman"><span class="lencana hijau" :title="`Ditandai ${t.aman.oleh} · ${tanggalWaktu(t.aman.waktu)}${t.aman.kembar ? ` · positif palsu, isi sama dengan ${relatif(t.aman.kembar)}` : ''}`">{{ t.aman.kembar ? 'AMAN · KEMBAR' : 'AMAN' }}</span>
                              <!-- Kembar ikut berkas yang dilaporkan: batalkan aman di berkas asal -->
                              <button v-if="!t.aman.kembar" type="button" class="tombol garis kecil" :disabled="proses" @click="tandaiAman(t.path, 'batal_aman')">Batal aman</button></template>
                            <template v-else><button type="button" class="tombol garis kecil" @click="lihatBerkas(t.path, '', t.tanda.map((x) => x.bukti), t.tanda.map((x) => x.id).join(', '))">Lihat</button>
                            <button type="button" class="tombol bahaya kecil" :disabled="proses" @click="karantina(t.path, t.tanda.map((x) => x.id).join(', '))">Karantina</button></template>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <button v-if="!tampilSemua && temuanTersaring.length > 100" type="button" class="tombol garis kecil lagi" @click="tampilSemua = true">Tampilkan semua {{ temuanTersaring.length }}</button>
                </template>
                <details v-if="detail.hasil.besar || detail.hasil.besar_gambar" class="besar">
                  <summary>Dilewati karena besar: {{ angka(detail.hasil.besar || 0) }} berkas<template v-if="detail.hasil.besar_gambar"> · {{ angka(detail.hasil.besar_gambar) }} gambar &gt; 256 KB (hanya dihitung)</template></summary>
                  <p class="redup">PHP &gt; 3 MB, html/js/txt/loader tersembunyi &gt; 1 MB: hanya awal + akhir yang dibaca (inti WP asli dicocokkan checksum dan tidak dicatat). Cek manual satu per satu.<template v-if="(detail.besar || []).length < (detail.hasil.besar || 0)"> Ditampilkan {{ angka(detail.besar.length) }} pertama.</template></p>
                  <div v-if="(detail.besar || []).length" class="tabel-wadah">
                    <table class="tabel">
                      <thead><tr><th scope="col">Berkas</th><th scope="col">Ukuran</th><th scope="col">Diubah</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                      <tbody>
                        <tr v-for="b in [...detail.besar].sort((x, y) => y.ukuran - x.ukuran)" :key="b.path">
                          <td class="ket berkas"><code>{{ relatif(b.path) }}</code><small class="redup blok">{{ b.user }} · izin {{ b.izin }}</small>
                            <span v-if="b.tanda?.length" class="lencana merah" :title="b.tanda.join(', ')">BERTANDA · {{ b.tanda.join(', ') }}</span>
                            <span v-else-if="b.sebagian === 'bersih'" class="lencana hijau" title="Hanya 256 KB awal + 256 KB akhir yang dibaca; bagian tengah belum dipindai">BERSIH · cek awal+akhir</span></td>
                          <td class="nowrap">{{ ukuranBerkas(b.ukuran) }}<small class="redup blok">batas {{ ukuranBerkas(b.batas) }}</small></td>
                          <td class="nowrap">{{ tanggalWaktu(b.mtime) }}<small v-if="Math.abs(b.ctime - b.mtime) > 86400" class="redup blok">ctime {{ tanggalWaktu(b.ctime) }}</small></td>
                          <td class="kanan">
                            <span v-if="karantinaPath.has(b.path)" class="lencana ungu">DIKARANTINA</span>
                            <template v-else><button type="button" class="tombol garis kecil" @click="lihatBerkas(b.path, '', [], 'Dilewati karena besar')">Lihat</button>
                            <button type="button" class="tombol bahaya kecil" :disabled="proses" @click="karantina(b.path, 'Dilewati karena besar')">Karantina</button></template>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </details>
              </template>
            </div>
          </template>

          <!-- ================= Deteksi cPGuard ================= -->
          <template v-else-if="tab === 'cpguard'">
            <p v-if="!terpilih.cpguard" class="redup">cPGuard tidak terpasang di server ini.</p>
            <p v-else-if="terpilih.cpguard.error" class="pesan-status bahaya">scanner.db tidak terbaca: {{ terpilih.cpguard.error }}</p>
            <template v-else>
              <div class="grafik">
                <div class="grafik-kepala">
                  <b>Deteksi malware cPGuard per hari</b>
                  <span class="redup">30 hari: <b>{{ angka(cpgJumlah(terpilih, 30)) }}</b> · seluruhnya {{ angka(terpilih.cpguard.total) }}</span>
                </div>
                <GrafikBatangTumpuk judul="Deteksi malware cPGuard per hari" :hari="cpgHari" :seri="SERI_CPG" :format="angka" :format-tanggal="formatTgl"
                  :label-nilai="puncakCpg" satuan="deteksi" />
              </div>
              <div v-if="cpgAkun.length" class="akun-teratas">
                <span class="redup">Akun terbanyak:</span>
                <button v-for="[u, n] in cpgAkun" :key="u" type="button" class="chip" @click="cariCpg = u">{{ u }} <b>{{ n }}</b></button>
              </div>
              <div class="alat">
                <input v-model="cariCpg" type="search" :placeholder="`Cari path / definisi / akun di ${angka(terpilih.cpguard.deteksi.length)} deteksi terbaru`" aria-label="Cari deteksi cPGuard">
                <span class="redup">
                  Status ditebak dari pola data cPGuard
                  <Info label="Tentang status cPGuard" rata="kanan"><p>Kolom cleanup_status scanner.db tidak terdokumentasi. Ditindak = −1 (berkas bisa masih ada — dibersihkan di tempat atau dipulihkan), Dibersihkan = 100, Dihapus = −100 (umumnya .zip), Dilaporkan = 0. "Masih ada" dicek langsung ke disk saat dibaca.</p></Info>
                </span>
              </div>
              <p v-if="!cpgTersaring.length" class="redup">Tidak ada deteksi dalam 30 hari terakhir.</p>
              <div v-else class="tabel-wadah">
                <table class="tabel">
                  <thead><tr><th scope="col">Berkas</th><th scope="col">Definisi</th><th scope="col">Status</th><th scope="col">Waktu</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                  <tbody>
                    <tr v-for="d in (tampilSemuaCpg ? cpgTersaring : cpgTersaring.slice(0, 100))" :key="d.id">
                      <td class="ket berkas"><code>{{ relatif(d.path) }}</code><small class="redup blok">{{ d.user || '-' }} · {{ d.alasan }}</small></td>
                      <td class="ket"><span :title="d.definisi">{{ ringkasDefinisi(d.definisi) }}</span></td>
                      <td class="nowrap">
                        <span class="lencana" :class="labelCleanup(d.cleanup)[0]" :title="`cleanup_status ${d.cleanup}, file_status ${d.file_status}`">{{ labelCleanup(d.cleanup)[1] }}</span>
                        <span v-if="d.ada" class="lencana merah" title="Berkas masih ada di lokasi asal">MASIH ADA</span>
                      </td>
                      <td class="nowrap">{{ tanggalWaktu(d.waktu.replace(' ', 'T')) }}</td>
                      <td class="kanan">
                        <span v-if="karantinaPath.has(d.path)" class="lencana ungu">DIKARANTINA</span>
                        <template v-else-if="d.ada && amanServer[d.path]"><span class="lencana hijau">AMAN</span>
                          <button type="button" class="tombol garis kecil" :disabled="proses" @click="tandaiAman(d.path, 'batal_aman')">Batal aman</button></template>
                        <button v-else-if="d.ada" type="button" class="tombol garis kecil" @click="lihatBerkas(d.path, '', [], `cPGuard ${d.definisi}`)">Lihat</button>
                        <button v-if="d.ada && !karantinaPath.has(d.path) && !amanServer[d.path]" type="button" class="tombol bahaya kecil" :disabled="proses" @click="karantina(d.path, `cPGuard ${d.definisi}`)">Karantina</button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <button v-if="!tampilSemuaCpg && cpgTersaring.length > 100" type="button" class="tombol garis kecil lagi" @click="tampilSemuaCpg = true">Tampilkan semua {{ cpgTersaring.length }}</button>
            </template>
          </template>

          <!-- ================= Judi AI ================= -->
          <template v-else-if="tab === 'analisis-ai'">
            <p v-if="!judi" class="redup">Memuat…</p>
            <template v-else>
              <fieldset class="jadwal">
                <legend>Analisis AI <small class="redup">· model <b>{{ judi.model }}</b> — ganti di <RouterLink to="/ai">AI Model</RouterLink> · sesudah scan otomatis selesai</small>
                  <Info label="Tentang Analisis AI"><p><b>Semua temuan</b> (malware, backdoor, admin siluman, SEO spam, judi) dinilai AI per berkas: <b>berbahaya</b>, <b>positif palsu</b>, atau <b>cek manual</b> + saran aksi — tampil di daftar scan sebagai saran saja, eksekusi tetap klik manual. Berkas yang isinya sudah pernah dinilai tidak dikirim lagi.</p><p>Khusus judi: temuan judi/slot/togel/cloaking dari scan dikelompokkan per akun, lalu AI menilai: <b>situs judi</b>, <b>diretas</b>, <b>berita</b>, atau <b>aman</b>. Keputusan tetap oleh aturan kode: suspend hanya bila AI yakin ≥90%, ada tanda tingkat virus, tidak ada tanda cloaking/alih, dan beranda versi pengunjung sendiri berisi judi. Situs diretas → berkas penyusup pilihan AI dikarantina (index.php, wp-config.php, .htaccess, wp-admin/, wp-includes/ tidak pernah — bersihkan manual). Hasil dikirim ke Telegram tim server.</p></Info>
                </legend>
                <label class="cek"><input type="checkbox" :checked="judi.setelan.aktif" :disabled="proses" @change="aturJudi({ aktif: $event.target.checked })">
                  <span>Aktif di {{ terpilih.name }} <small class="redup blok">butuh scan otomatis harian (tab Scan)<template v-if="judi.setelan.aktif && !jadwal.harian"> — <b class="merah-teks">scan harian belum aktif</b></template></small></span></label>
                <fieldset class="pil-mode">
                  <legend>Mode</legend>
                  <label :class="{ aktif: judi.setelan.mode === 'laporan' }"><input type="radio" name="mode-judi" class="sr" :checked="judi.setelan.mode === 'laporan'" :disabled="proses" @change="aturJudi({ mode: 'laporan' })">
                    <b>Laporan saja</b><small class="redup">Rencana aksi dicatat &amp; dikirim Telegram, tidak ada yang diubah.</small></label>
                  <label :class="{ aktif: judi.setelan.mode === 'otomatis', bahaya: judi.setelan.mode === 'otomatis' }"><input type="radio" name="mode-judi" class="sr" :checked="judi.setelan.mode === 'otomatis'" :disabled="proses" @change="aturJudi({ mode: 'otomatis' })">
                    <b>Otomatis</b><small class="redup">Suspend akun situs judi (maks {{ judi.setelan.maks_suspend }}/malam) &amp; karantina berkas situs diretas.</small></label>
                </fieldset>
                <label class="isian"><span>Daftar putih <small class="redup">akun atau domain, satu per baris — tidak pernah dinilai/diubah</small></span>
                  <textarea v-model="judiPutih" rows="3" spellcheck="false" /></label>
                <div class="kepala-aksi">
                  <button type="button" class="tombol garis kecil" :disabled="proses" @click="simpanPutih">Simpan daftar putih</button>
                  <button type="button" class="tombol garis kecil" :disabled="proses || judi.berjalan || !scanTerakhir(terpilih.host)" @click="nilaiUlangJudi()">{{ judi.berjalan ? 'Menilai…' : 'Nilai scan terakhir sekarang' }}</button>
                  <button type="button" class="tombol garis kecil" :disabled="proses || judi.berjalan || !scanTerakhir(terpilih.host)" @click="nilaiUlangJudi(true)">Nilai semua yang belum ditangani</button>
                  <button type="button" class="tombol garis kecil" :disabled="proses" @click="muatJudi">Muat ulang</button>
                </div>
                <div v-if="judi.berjalan" class="kemajuan" role="status">
                  <span class="putar" aria-hidden="true" />
                  <div><b>Menilai akun {{ judi.kemajuan?.ke || '…' }}/{{ judi.kemajuan?.dari || '?' }}</b>
                    <span class="redup"> {{ judi.kemajuan?.user || '' }} · sejak {{ judi.kemajuan ? tanggalWaktu(judi.kemajuan.mulai) : '-' }} · oleh {{ judi.kemajuan?.oleh || '-' }}</span>
                    <div class="garis-jalan"><span :style="{ width: `${judi.kemajuan ? (judi.kemajuan.ke / judi.kemajuan.dari) * 100 : 3}%` }" /></div>
                  </div>
                  <button type="button" class="tombol bahaya kecil" @click="hentiJudi">Hentikan</button>
                </div>
              </fieldset>
              <div class="kepala-riwayat">
                <h3 class="sub-judul">Hasil penilaian per akun <span class="redup">({{ judiAkun.length }})</span>
                  <Info label="Tentang hasil penilaian"><p>Satu baris per akun hosting = penilaian AI terbaru. Urut dari yang paling perlu ditangani: belum ditangani dulu, lalu situs judi, diretas, lainnya.</p><p><b>Status</b> dihitung dari gabungan semua scan: <b>Belum ditangani</b> = masih ada temuan yang belum dikarantina, belum ditandai aman, dan belum bersih di scan terbaru (positif palsu menurut AI tidak dihitung). <b>Ditangani</b> = sisa 0 atau akun tersuspend. Saran per berkas ada di tab Scan (label "AI: …").</p></Info></h3>
                <div class="alat">
                  <select v-model="filterJudi" aria-label="Saring hasil penilaian">
                    <option value="">Semua ({{ judiAkun.length }})</option>
                    <option v-for="(v, k) in JENIS_JUDI" :key="k" :value="k">{{ v[1] }} ({{ judiAkun.filter((d) => d.ai?.jenis === k).length }})</option>
                  </select>
                  <select v-model="filterTangani" aria-label="Saring status penanganan" :disabled="!sisaAkun">
                    <option value="">Semua status</option>
                    <option value="belum">Belum ditangani ({{ jumlahTangani(false) }})</option>
                    <option value="sudah">Sudah ditangani ({{ jumlahTangani(true) }})</option>
                  </select>
                  <button v-if="judi.keputusan.length" type="button" class="tombol garis kecil" :disabled="proses || judi.berjalan" @click="bersihkanRiwayatJudi">Bersihkan riwayat</button>
                </div>
              </div>
              <p v-if="!judiAkun.length" class="redup">Belum ada penilaian di server ini. Tekan "Nilai semua yang belum ditangani" di atas.</p>
              <div v-else class="tabel-wadah">
                <table class="tabel">
                  <thead><tr><th scope="col">Akun</th><th scope="col">Status</th><th scope="col">Penilaian AI</th><th scope="col">Temuan</th><th scope="col">Tindakan</th></tr></thead>
                  <tbody>
                    <tr v-for="d in judiAkunTersaring" :key="d.user">
                      <td class="ket"><b>{{ d.user }}</b><small class="redup blok">{{ (d.domain || []).join(', ') || '-' }}</small></td>
                      <td class="ket">
                        <template v-if="statusTangani(d)">
                          <span class="lencana" :class="statusTangani(d).sudah ? 'hijau' : 'merah'">{{ statusTangani(d).label }}</span>
                          <small v-if="statusTangani(d).fp" class="redup blok">{{ statusTangani(d).fp }} positif palsu belum ditandai aman</small>
                        </template>
                        <span v-else class="redup">…</span>
                      </td>
                      <td class="ket">
                        <span v-if="d.ai" class="lencana" :class="JENIS_JUDI[d.ai.jenis]?.[0]">{{ JENIS_JUDI[d.ai.jenis]?.[1] }} {{ d.ai.yakin }}%</span>
                        <span v-else class="lencana abu">Belum dinilai</span>
                        <small class="blok">{{ d.ai?.alasan || d.catatan }}</small>
                      </td>
                      <td class="nowrap" :title="(d.tanda || []).join(', ')">{{ d.temuan }} temuan
                        <small v-if="d.analisis" class="blok"><span v-if="d.analisis.berbahaya" class="merah-teks">{{ d.analisis.berbahaya }} berbahaya</span>
                          <span v-if="d.analisis.cek_manual" class="kuning-teks">{{ d.analisis.cek_manual }} cek manual</span>
                          <span v-if="d.analisis.positif_palsu" class="hijau-teks">{{ d.analisis.positif_palsu }} positif palsu</span></small>
                      </td>
                      <td class="ket">
                        <span class="lencana" :class="d.dijalankan && !d.ok ? 'merah' : d.aksi === 'suspend' ? 'merah' : d.aksi === 'karantina' ? 'kuning' : ''">{{ labelAksiJudi(d) }}</span>
                        <small v-if="d.ai && d.catatan && d.judi !== false" class="redup blok">{{ d.catatan }}</small>
                        <small v-if="d.berkas?.length" class="redup blok">Berkas: <code v-for="b in d.berkas" :key="b">{{ relatif(b) }} </code></small>
                        <small v-if="d.error" class="merah-teks blok">{{ pesanGalat(d.error) }}</small>
                        <span class="kepala-aksi">
                          <button v-if="d.ai" type="button" class="tombol garis kecil" @click="bukaSaran(d)">Saran aksi</button>
                          <button v-if="d.dijalankan === 'suspend' && d.ok" type="button" class="tombol garis kecil" :disabled="proses" @click="suspendJudi(d, 'unsuspend')">Batalkan suspend</button>
                          <button v-else-if="d.ai?.jenis === 'situs_judi'" type="button" class="tombol bahaya kecil" :disabled="proses" @click="suspendJudi(d, 'suspend')">Suspend manual</button>
                        </span>
                        <small class="redup blok">{{ tanggalWaktu(d.t) }} · {{ d.oleh }}</small>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <details v-if="judiLog.length" class="log-judi">
                <summary>Log aktivitas <span class="redup">({{ judiLog.length }}) · penilaian selesai, setelan, aksi manual</span></summary>
                <ul class="kejadian">
                  <li v-for="(d, i) in judiLog" :key="i">
                    <span class="titik" :class="d.jenis_catat === 'galat' ? 'bahaya' : 'abu'" aria-hidden="true" />
                    <div>
                      <b>{{ CATAT_JUDI[d.jenis_catat] || d.jenis_catat }}</b>
                      <template v-if="d.user"> {{ d.user }} · {{ d.dijalankan }}<span v-if="!d.ok" class="lencana merah">GAGAL · {{ pesanGalat(d.error) }}</span></template>
                      <small class="redup blok">{{ d.oleh || '' }}<template v-if="d.alasan"> · {{ d.alasan }}</template></small>
                    </div>
                    <time class="redup">{{ tanggalWaktu(d.t) }}</time>
                  </li>
                </ul>
              </details>
            </template>
          </template>

          <!-- ================= Karantina ================= -->
          <template v-else-if="tab === 'karantina'">
            <p class="redup kaki-form">Berkas disimpan di <code>/root/velocity-karantina/</code> server ini (hanya root) beserta pemilik, izin, dan waktu aslinya.</p>
            <p v-if="!terpilih.karantina.length" class="redup">Karantina kosong.</p>
            <div v-else class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">Berkas asal</th><th scope="col">Alasan</th><th scope="col">Dikarantina</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                <tbody>
                  <tr v-for="k in terpilih.karantina" :key="k.id">
                    <td class="ket berkas"><code>{{ relatif(k.path) }}</code><small class="redup blok">{{ k.user }} · {{ ukuranBerkas(k.ukuran) }} · sha256 {{ k.sha256.slice(0, 12) }}…</small></td>
                    <td class="ket">{{ (k.alasan || '-').split(', ').map(namaTanda).join(', ') }}</td>
                    <td class="nowrap">{{ tanggalWaktu(k.waktu) }}<small class="redup blok">{{ k.oleh || '-' }} <span v-if="/^(Realtime|Otomatis)/.test(k.oleh || '')" class="lencana ungu">OTOMATIS</span></small></td>
                    <td class="kanan">
                      <button type="button" class="tombol garis kecil" :disabled="proses" @click="bukaAksiK(k)">Aksi…</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <h3 class="sub-judul">Whitelist <span class="redup">({{ putihServer.length }})</span>
              <Info label="Tentang whitelist"><p>Path di sini tidak pernah diperiksa watcher realtime, scan, maupun periksa ulang — walau isinya berubah. Pakai hanya untuk berkas/folder yang pasti aman (mis. pustaka yang selalu positif palsu). Untuk satu versi berkas saja, pakai "Laporkan positif palsu" (tanda aman terikat isi).</p></Info></h3>
            <p v-if="!putihServer.length" class="redup">Belum ada.</p>
            <ul v-else class="daftar-putih">
              <li v-for="w in putihServer" :key="w.path">
                <span class="lencana" :class="w.jenis === 'folder' ? 'biru' : 'abu'">{{ w.jenis === 'folder' ? 'FOLDER' : 'BERKAS' }}</span>
                <code>{{ relatif(w.path) }}{{ w.jenis === 'folder' ? '/' : '' }}</code>
                <small class="redup blok">{{ w.oleh }} · {{ tanggalWaktu(w.t) }}<template v-if="w.alasan"> · {{ w.alasan }}</template></small>
                <button type="button" class="tombol garis kecil" :disabled="proses" @click="hapusPutih(w)">Keluarkan</button>
              </li>
            </ul>
            <h3 class="sub-judul">Ingat karantina <span class="redup">({{ daftarHitam.length }})</span>
              <Info label="Tentang ingat karantina"><p>Isi (sha256) berkas yang pernah dikarantina manual atau lewat Bersihkan WP, di server mana pun. Berkas berisi persis sama yang muncul lagi di scan/realtime langsung dikarantina otomatis — kecuali wp-admin, wp-includes, index.php, wp-config.php, .htaccess (hanya diberi label). Kembalikan, positif palsu, tandai aman, atau "Lupakan" mengeluarkannya dari daftar.</p></Info></h3>
            <p v-if="!daftarHitam.length" class="redup">Belum ada.</p>
            <div v-else class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">Berkas asal</th><th scope="col">Alasan</th><th scope="col">Dikarantina</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                <tbody>
                  <tr v-for="h in daftarHitam" :key="h.sha256">
                    <td class="ket berkas"><code>{{ relatif(h.path) }}</code><small class="redup blok">{{ h.server }} · sha256 {{ h.sha256.slice(0, 12) }}…</small></td>
                    <td class="ket">{{ (h.tanda || '-').split(', ').map(namaTanda).join(', ') }}</td>
                    <td class="nowrap">{{ tanggalWaktu(h.t) }}<small class="redup blok">{{ h.oleh || '-' }}</small></td>
                    <td class="kanan"><button type="button" class="tombol garis kecil" :disabled="proses" @click="lupakanHitam(h)">Lupakan</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>

          <!-- whitelist & ingat karantina ditampilkan di tab Karantina -->
          <!-- ================= Riwayat ================= -->
          <template v-else-if="tab === 'riwayat'">
            <p v-if="!riwayatServer.length" class="redup">Belum ada aksi karantina dari dashboard.</p>
            <ul v-else class="kejadian">
              <li v-for="(r, i) in riwayatServer" :key="i">
                <span class="titik" :class="r.ok ? AKSI_LABEL[r.aksi]?.[0] : 'abu'" aria-hidden="true" />
                <div>
                  <b>{{ AKSI_LABEL[r.aksi]?.[1] || r.aksi }}</b> <code>{{ relatif(r.path) }}</code>
                  <span v-if="!r.ok" class="lencana merah">GAGAL · {{ pesanGalat(r.error) }}</span>
                  <small class="redup blok">{{ r.oleh }}<template v-if="r.alasan"> · {{ r.alasan }}</template></small>
                </div>
                <time class="redup">{{ tanggalWaktu(r.t) }}</time>
              </li>
            </ul>
          </template>
        </section>
      </template>
    </template>

    <Dialog :buka="aksiK.buka" :judul="aksiK.k ? `Aksi · ${relatif(aksiK.k.path)}` : 'Aksi'" lebar="620px" @tutup="aksiK.buka = false">
      <template v-if="aksiK.k">
        <p class="redup kecil-teks">{{ (aksiK.k.alasan || '-').split(', ').map(namaTanda).join(', ') }} · dikarantina {{ tanggalWaktu(aksiK.k.waktu) }} oleh {{ aksiK.k.oleh || '-' }}</p>
        <fieldset class="pil-aksi">
          <legend class="sr">Pilih aksi</legend>
          <label v-for="o in PILIHAN_K" :key="o.k" :class="{ aktif: aksiK.pilih === o.k, bahaya: o.bahaya && aksiK.pilih === o.k }">
            <input v-model="aksiK.pilih" type="radio" name="aksi-k" class="sr" :value="o.k" :disabled="o.k !== 'lihat' && o.k !== 'hapus' && aksiK.k.asal_terisi">
            <b>{{ o.label }}</b><small class="redup">{{ o.teks }}</small></label>
        </fieldset>
        <p v-if="aksiK.k.asal_terisi" class="pesan-status bahaya">Lokasi asal sudah berisi berkas lain — hanya Lihat atau Hapus.</p>
        <label v-if="aksiK.pilih === 'putih_folder'" class="isian"><span>Folder</span><input v-model="aksiK.folder" type="text" spellcheck="false"></label>
        <label v-if="['fp', 'putih_berkas', 'putih_folder'].includes(aksiK.pilih)" class="isian"><span>Catatan <small class="redup">kenapa aman (untuk tim)</small></span><textarea v-model="aksiK.catatan" rows="2" /></label>
        <div class="aksi-pratinjau">
          <button type="button" class="tombol garis" @click="aksiK.buka = false">Batal</button>
          <button type="button" class="tombol" :class="{ bahaya: aksiK.pilih === 'hapus' }" :disabled="!aksiK.pilih || proses" @click="jalankanAksiK">Lanjut</button>
        </div>
      </template>
    </Dialog>
    <Dialog :buka="bersih.buka" :judul="`Bersihkan WP · ${relatif(bersih.akar)}`" lebar="620px" @tutup="bersih.buka = false">
      <p class="redup kecil-teks">Tanpa menjalankan PHP situs. Cadangan tabel users/usermeta, wp-config.php & daftar post yang dialihkan disimpan di /root/velocity-bersih.</p>
      <fieldset class="pil-aksi">
        <legend>Admin mencurigakan</legend>
        <div v-for="a in bersih.admin" :key="a.db.id" class="admin-baris" :class="{ aktif: !!bersih.aksiUser[a.db.id] }">
          <span><b>#{{ a.db.id }} {{ a.db.judul }}</b>
            <small class="redup blok">{{ a.tingkat === 'virus' ? 'Admin siluman' : 'Curiga (pola nama+angka) — bisa saja milik klien' }} · terdaftar {{ tanggalWaktu(a.mtime) }}</small></span>
          <select v-model="bersih.aksiUser[a.db.id]" :aria-label="`Aksi untuk admin #${a.db.id}`">
            <option value="subscriber">Jadikan subscriber</option>
            <option value="hapus">Hapus</option>
            <option value="">Biarkan</option>
          </select></div>
      </fieldset>
      <label class="isian"><span><input v-model="bersih.plugin" type="checkbox"> Karantina plugin samaran (wp-cachepress dkk.) di plugins & mu-plugins</span></label>
      <label class="isian"><span><input v-model="bersih.salt" type="checkbox"> Ganti salt wp-config & hapus semua sesi login</span></label>
      <template v-if="bersih.hasil">
        <p v-if="!bersih.hasil.ok" class="pesan-status bahaya">{{ pesanGalat(bersih.hasil.error) }} {{ bersih.hasil.pesan || '' }}</p>
        <ul class="kecil-teks">
          <li v-for="k in bersih.hasil.karantina || []" :key="k.path">{{ k.ok ? 'Dikarantina' : `Gagal (${k.error})` }}: <code>{{ relatif(k.path) }}</code> · {{ k.tanda.join(', ') }}</li>
          <li v-if="bersih.hasil.ok && !(bersih.hasil.karantina || []).length && bersih.plugin">Tidak ada plugin samaran tersisa.</li>
          <li v-for="u in bersih.hasil.hapus_user || []" :key="u.id">Dihapus: #{{ u.id }} {{ u.login }} &lt;{{ u.email }}&gt;</li>
          <li v-for="u in bersih.hasil.turun_user || []" :key="`t${u.id}`">Jadi subscriber (sesi diputus): #{{ u.id }} {{ u.login }} &lt;{{ u.email }}&gt;</li>
          <li v-if="bersih.hasil.dialihkan_ke">{{ bersih.hasil.post_dialihkan }} post dialihkan ke admin #{{ bersih.hasil.dialihkan_ke }}</li>
          <li v-if="bersih.hasil.cadangan">Cadangan: <code>{{ bersih.hasil.cadangan }}</code></li>
        </ul>
      </template>
      <div class="aksi-pratinjau">
        <button type="button" class="tombol garis" @click="bersih.buka = false">Tutup</button>
        <button type="button" class="tombol bahaya" :disabled="proses || (!bersihId('hapus').length && !bersihId('subscriber').length && !bersih.plugin && !bersih.salt) || bersih.hasil?.ok" @click="jalankanBersih">Bersihkan</button>
      </div>
    </Dialog>
    <Dialog :buka="saran.buka" :judul="saran.d ? `Saran aksi · ${saran.d.user}` : 'Saran aksi'" lebar="760px" @tutup="saran.buka = false">
      <template v-if="saran.d">
        <p class="saran-kepala"><span class="redup">{{ (saran.d.domain || []).join(', ') }}</span>
          <span v-if="saran.d.ai" class="lencana" :class="JENIS_JUDI[saran.d.ai.jenis]?.[0]">{{ JENIS_JUDI[saran.d.ai.jenis]?.[1] }} {{ saran.d.ai.yakin }}%</span>
          <small v-if="saran.d.ai" class="blok">{{ saran.d.ai.alasan }}</small></p>
        <p v-if="saran.memuat" class="redup">Memuat temuan scan…</p>
        <template v-else>
          <p v-if="saran.galat" class="pesan-status bahaya">{{ saran.galat }}</p>
          <ol class="saran">
            <li v-for="(l, i) in langkahSaran" :key="i">
              <b>{{ l.judul }}</b>
              <small class="blok">{{ l.teks }}</small>
              <ul v-if="l.berkas" class="saran-berkas">
                <li v-for="t in l.berkas" :key="t.path"><code>{{ t.db ? `${relatif(t.path.split('#')[0])} · ${t.db.tabel} #${t.db.id}` : relatif(t.path) }}</code>
                  <small v-if="t.db" class="redup blok">database · {{ t.db.jenis }} · "{{ t.db.judul }}"</small>
                  <span class="saran-aksi">
                    <a v-if="t.db && /_posts$/.test(t.db.tabel) && domainDari(t.path)" class="tombol garis kecil" :href="`https://${domainDari(t.path)}/wp-admin/post.php?post=${t.db.id}&action=edit`" target="_blank" rel="noopener noreferrer">Buka di wp-admin</a>
                    <button v-if="!t.db" type="button" class="tombol garis kecil" @click="lihatBerkas(t.path, '', t.tanda.map((x) => x.bukti), t.tanda.map((x) => x.id).join(', '))">Lihat</button>
                    <span v-if="karantinaPath.has(t.path)" class="lencana ungu">DIKARANTINA</span>
                    <template v-else-if="l.mode === 'aman'">
                      <button type="button" class="tombol garis kecil" :disabled="proses" @click="tandaiAman(t.path, 'aman', `AI: ${t.ai?.alasan || 'positif palsu'}`.slice(0, 200), t.db ? t.sha256 : '')">Tandai aman</button>
                      <button type="button" class="tombol garis kecil" :disabled="proses" @click="laporFpTemuan(t)">Laporkan positif palsu</button>
                    </template>
                    <button v-else-if="!l.manual" type="button" class="tombol bahaya kecil" :disabled="proses" @click="karantina(t.path, t.tanda.map((x) => x.id).join(', '))">Karantina</button>
                  </span>
                  <small v-if="t.ai" class="redup blok">AI: {{ t.ai.alasan }}</small></li>
              </ul>
              <span v-if="l.tautan || l.putih || l.scan" class="saran-aksi">
                <a v-if="l.tautan" class="tombol garis kecil" :href="l.tautan" :target="l.tautan.startsWith('http') ? '_blank' : null" rel="noopener noreferrer">{{ l.tautan.startsWith('http') ? 'Buka' : 'Buka halaman' }}</a>
                <button v-if="l.putih" type="button" class="tombol garis kecil" :disabled="proses || judi.setelan.daftar_putih.includes(saran.d.user)" @click="putihkanSaran">{{ judi.setelan.daftar_putih.includes(saran.d.user) ? 'Sudah di daftar putih' : 'Tambah ke daftar putih' }}</button>
                <button v-if="l.scan" type="button" class="tombol garis kecil" @click="scanSaran">Siapkan scan akun</button>
              </span>
            </li>
          </ol>
          <p class="redup kaki-form">Saran disusun aturan tetap dari penilaian AI &amp; temuan scan — periksa dulu sebelum mengubah situs klien.</p>
        </template>
      </template>
    </Dialog>
    <Dialog :buka="pratinjau.buka" :judul="pratinjau.judul" lebar="1100px" @tutup="pratinjau.buka = false">
      <p v-if="pratinjau.memuat" class="redup">Membaca berkas…</p>
      <p v-else-if="pratinjau.galat" class="pesan-status bahaya">{{ pratinjau.galat }}</p>
      <template v-else-if="pratinjau.data">
        <small class="redup blok">{{ pratinjau.data.path }} · {{ ukuranBerkas(pratinjau.data.ukuran) }} · diubah {{ tanggalWaktu(pratinjau.data.mtime) }}</small>
        <p v-if="pratinjau.data.terpotong" class="pesan-status waspada">Hanya 512 KB pertama yang ditampilkan.</p>
        <p v-if="pratinjau.data.biner" class="pesan-status waspada">Berkas biner — karakter tak terbaca diganti �.</p>
        <div v-for="(b, i) in pratinjau.bukti" :key="i" class="bukti-pratinjau"><span class="redup">Bukti:</span> <code>{{ b }}</code></div>
        <pre class="isi-berkas">{{ pratinjau.data.isi }}</pre>
        <div v-if="!pratinjau.kid" class="aksi-pratinjau">
          <span class="redup">Buatan sendiri / bukan malware?</span>
          <button type="button" class="tombol garis kecil" :disabled="proses" @click="tandaiAman(pratinjau.path, 'aman', pratinjau.alasan)">Tandai aman</button>
          <button type="button" class="tombol bahaya kecil" :disabled="proses" @click="pratinjau.buka = false; karantina(pratinjau.path, pratinjau.alasan)">Karantina</button>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.isi-berkas { margin-top: 10px; max-height: 65vh; overflow: auto; padding: 12px; border-radius: 8px; background: var(--kartu-2); border: 1px solid var(--garis); font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
.pesan-status.waspada { color: var(--waspada); }
.jadwal { display: grid; gap: 6px; margin: 14px 0 4px; padding: 12px 14px; border: 1px solid var(--garis); border-radius: 10px; }
.jadwal .cek { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: start; gap: 10px; font-size: 13.5px; cursor: pointer; }
.jadwal .cek input { margin: 3px 0 0; }
.jadwal .cek small { margin-top: 2px; font-size: 12px; }
.pil-mode { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 4px 0 0; padding: 0; border: 0; min-width: 0; }
.pil-mode legend { padding: 0; margin-bottom: 6px; font-size: 12.5px; font-weight: 400; color: var(--teks-2); }
.pil-mode label { position: relative; display: grid; align-content: start; gap: 3px; padding: 10px 12px; border: 1px solid var(--garis); border-radius: 9px; font-size: 13.5px; cursor: pointer; }
.pil-mode label small { font-size: 12px; line-height: 1.4; }
.pil-mode label.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); }
.pil-mode label.aktif b { color: var(--aksen-terang); }
.pil-mode label.bahaya { background: transparent; border-color: var(--bahaya); }
.pil-mode label.bahaya b { color: var(--bahaya); }
.pil-mode label:focus-within { outline: 2px solid var(--aksen-terang); outline-offset: 2px; }
.pil-aksi { display: grid; gap: 6px; margin: 0 0 10px; padding: 0; border: 0; min-width: 0; }
.pil-aksi label { position: relative; display: grid; gap: 2px; padding: 9px 12px; border: 1px solid var(--garis); border-radius: 9px; font-size: 13.5px; cursor: pointer; }
.pil-aksi label small { font-size: 12px; line-height: 1.4; }
.pil-aksi label.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); }
.pil-aksi label.aktif b { color: var(--aksen-terang); }
.pil-aksi .admin-baris { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 12px; border: 1px solid var(--garis); border-radius: 9px; font-size: 13.5px; }
.pil-aksi .admin-baris > span { min-width: 0; flex: 1 1 260px; overflow-wrap: anywhere; }
.pil-aksi .admin-baris small { font-size: 12px; line-height: 1.4; }
.pil-aksi .admin-baris.aktif { border-color: var(--aksen-terang); }
.pil-aksi label.bahaya { border-color: var(--bahaya); background: transparent; }
.pil-aksi label.bahaya b { color: var(--bahaya); }
.pil-aksi label:has(input:disabled) { opacity: .45; cursor: not-allowed; }
.pil-aksi label:focus-within { outline: 2px solid var(--aksen-terang); outline-offset: 2px; }
.kecil-teks { margin: 0 0 10px; font-size: 12.5px; }
.sub-judul { display: flex; align-items: center; gap: 6px; margin: 18px 0 8px; font-size: 14px; }
.daftar-putih { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; font-size: 13px; }
.daftar-putih li { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 4px 8px; align-items: center; overflow-wrap: anywhere; }
.daftar-putih li small { grid-column: 2; }
.daftar-putih li button { grid-column: 3; grid-row: 1; }
.jadwal legend { padding: 0 6px; font-weight: 700; font-size: 13px; }
.realtime-status { display: grid; grid-template-columns: 8px minmax(0, 1fr); gap: 10px; align-items: start; margin: 4px 0 0; padding-top: 8px; border-top: 1px solid var(--garis); font-size: 13.5px; }
.realtime-status .titik { margin-top: 6px; }
.realtime-status small { margin-top: 2px; font-size: 12px; }
.aksi-pratinjau { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.bukti-pratinjau { margin-top: 6px; font-size: 12px; word-break: break-all; }
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.kepala-aksi { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.saran-kepala { margin: 0 0 12px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
.saran-kepala small { flex-basis: 100%; font-size: 12.5px; }
.saran { display: grid; gap: 12px; margin: 0; padding-left: 20px; font-size: 13.5px; }
.saran > li small { margin-top: 2px; font-size: 12.5px; line-height: 1.45; overflow-wrap: anywhere; }
.saran-berkas { display: grid; gap: 6px; margin: 8px 0 0; padding: 0; list-style: none; font-size: 12px; }
.saran-berkas li { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px; overflow-wrap: anywhere; }
.saran-aksi { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; }
.saran-berkas .saran-aksi { margin-top: 0; }
.nama-saya { display: grid; gap: 4px; font-size: 12px; }

.ringkas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.kartu-judul { flex-wrap: wrap; gap: 10px; }
.kartu-judul h2 { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.kartu-judul h2 small { font-size: 12.5px; font-weight: 400; }
.tile { display: flex; gap: 14px; align-items: center; }
.tile > div { display: grid; gap: 3px; min-width: 0; }
.tile b { font-size: 24px; color: var(--teks-kuat); }
.tile small { font-size: 12px; }
.tile-ikon { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; }
.tile-ikon.merah { color: var(--bahaya); background: color-mix(in srgb, var(--bahaya) 15%, transparent); }
.tile-ikon.kuning { color: var(--waspada); background: color-mix(in srgb, var(--waspada) 15%, transparent); }
.tile-ikon.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 15%, transparent); }
.tile-ikon.hijau { color: var(--baik); background: color-mix(in srgb, var(--baik) 15%, transparent); }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); vertical-align: 1px; }
.titik.baik, .titik.hijau { background: var(--baik); }
.titik.waspada, .titik.kuning { background: var(--waspada); }
.titik.bahaya, .titik.merah { background: var(--bahaya); }
.titik.biru { background: var(--aksen-terang); }
.titik.ungu { background: var(--ungu); }
.lencana.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 14%, transparent); }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
/* Form scan */
.form-scan { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 14px; align-items: end; }
.form-scan .isian { display: grid; gap: 6px; font-size: 12.5px; color: var(--teks-2); min-width: 0; }
.form-scan select { width: 100%; min-width: 0; }
.form-scan .tombol { min-height: 42px; }
.pil-durasi { display: flex; flex-wrap: wrap; gap: 6px; margin: 0; padding: 0; border: 0; min-width: 0; }
.pil-durasi legend { display: inline-flex; align-items: center; gap: 4px; padding: 0; margin-bottom: 6px; font-size: 12.5px; color: var(--teks-2); }
.pil-durasi label { border: 1px solid var(--garis); border-radius: 9px; padding: 9px 12px; font-size: 13px; cursor: pointer; color: var(--teks-2); }
.pil-durasi label.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); color: var(--aksen-terang); font-weight: 600; }
.pil-durasi label.mati { opacity: .45; cursor: not-allowed; }
.pil-durasi label:focus-within { outline: 2px solid var(--aksen-terang); outline-offset: 2px; }
.kaki-form { margin: 10px 0 16px; font-size: 13px; display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.daftar-tanda { list-style: none; margin: 0; padding: 0; display: grid; gap: 5px; font-size: 12.5px; }
/* Daftar scan */
.atur-scan { margin-bottom: 16px; padding: 10px 14px; border: 1px solid var(--garis); border-radius: 10px; }
.atur-scan > summary { cursor: pointer; font-size: 13.5px; }
.atur-scan[open] > summary { margin-bottom: 12px; }
.pilih-scan { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin-bottom: 16px; }
.pilih-scan .isian { display: grid; gap: 6px; flex: 1 1 320px; min-width: 0; font-size: 12.5px; color: var(--teks-2); }
.pilih-scan select { width: 100%; min-width: 0; }
.saran-ai { margin-top: 6px; font-size: 12.5px; }
.saran-ai small { margin-top: 2px; }
.kepala-riwayat { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
.kepala-riwayat .sub-judul { margin: 0; }
.kepala-riwayat .alat { margin: 0; }
.log-judi { margin-top: 16px; }
.log-judi > summary { cursor: pointer; font-size: 13.5px; font-weight: 600; margin-bottom: 8px; }
.langkah { margin: 0 0 10px; font-size: 13px; color: var(--teks-2); }
.scan-teks { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 8px; min-width: 0; font-size: 13px; overflow-wrap: anywhere; }
.scan-teks small { font-size: 11.5px; }
.scan-hasil { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 2px 8px; font-size: 12.5px; text-align: right; }
.merah-teks { color: var(--bahaya); }
.kuning-teks { color: var(--waspada); }
.hijau-teks { color: var(--baik); }
/* Detail scan */
.detail-scan { display: grid; gap: 12px; border-top: 1px solid var(--garis); padding-top: 16px; }
.ringkas-scan { margin: 0; font-size: 13.5px; }
.bersih { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--baik); font-weight: 600; }
.kemajuan { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 14px; align-items: center; padding: 14px; border-radius: 12px; background: var(--kartu-2); font-size: 13.5px; }
.garis-jalan { height: 6px; border-radius: 3px; background: var(--garis); overflow: hidden; margin-top: 8px; }
.garis-jalan span { display: block; height: 100%; background: var(--aksen); border-radius: 3px; transition: width .4s; }
.putar { display: inline-block; width: 12px; height: 12px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: putar .8s linear infinite; vertical-align: -1px; }
.putar.besar { width: 22px; height: 22px; color: var(--aksen-terang); }
@keyframes putar { to { transform: rotate(360deg); } }
.berkas { min-width: 260px; }
.berkas code { overflow-wrap: anywhere; }
.bukti { display: block; margin-top: 3px; padding: 4px 6px; border-radius: 6px; background: var(--kartu-2); font-size: 11.5px; color: var(--teks-2); overflow-wrap: anywhere; white-space: pre-wrap; max-height: 4.5em; overflow: hidden; }
/* cPGuard */
.grafik { display: grid; gap: 8px; margin-bottom: 14px; }
.grafik-kepala { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; font-size: 13.5px; }
.akun-teratas { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; font-size: 13px; }
.chip { border: 1px solid var(--garis); background: transparent; color: var(--teks-2); font: inherit; font-size: 12.5px; padding: 4px 10px; border-radius: 999px; cursor: pointer; }
.chip:hover { border-color: var(--aksen-terang); color: var(--teks-kuat); }
.alat { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; font-size: 13px; }
.alat input[type="search"] { flex: 1 1 220px; min-width: 0; }
.alat select { flex: 0 1 auto; width: auto; min-width: 0; }
.ket { font-size: 13px; color: var(--teks-2); overflow-wrap: anywhere; min-width: 180px; }
.blok { display: block; }
.lagi { margin-top: 10px; }
.kejadian { list-style: none; margin: 0; padding: 0; display: grid; }
.kejadian li { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 2px; border-bottom: 1px solid var(--garis); font-size: 13.5px; }
.kejadian li:last-child { border-bottom: 0; }
.kejadian li > div { overflow-wrap: anywhere; }
.kejadian time { font-size: 12.5px; white-space: nowrap; }
.nowrap { white-space: nowrap; }
.kanan { text-align: right; white-space: nowrap; }
.kanan .tombol + .tombol { margin-left: 6px; }
.tabel-wadah { position: relative; overflow-x: auto; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
/* Skeleton */
.skeleton { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; }
.status-muat { margin: 0; }
.skeleton .tile > div { flex: 1; }
.skeleton .tile { min-height: 112px; }
.sk { --sk-dasar: color-mix(in srgb, var(--kartu-2), var(--teks) 7%); --sk-kilap: color-mix(in srgb, var(--kartu-2), var(--teks) 15%);
  display: block; border-radius: 6px; background: linear-gradient(90deg, var(--sk-dasar) 25%, var(--sk-kilap) 50%, var(--sk-dasar) 75%); background-size: 200% 100%; animation: sk-kilau 1.4s ease-in-out infinite; }
.sk-ikon { flex: none; width: 44px; height: 44px; border-radius: 12px; }
.sk-teks { height: 11px; width: 60%; margin: 4px 0; }
.sk-teks.pendek { width: 40%; }
.sk-angka { height: 22px; width: 45%; margin: 4px 0; }
.sk-menu { display: flex; gap: 8px; padding: 8px; border-radius: 12px; background: var(--kartu); border: 1px solid var(--garis); overflow: hidden; }
.sk-pil { flex: none; height: 30px; width: 96px; border-radius: 9px; }
.sk-judul { height: 14px; width: 200px; max-width: 60%; margin-bottom: 18px; }
.sk-baris { display: grid; grid-template-columns: 2fr 1.2fr .8fr .8fr .6fr; gap: 16px; padding: 14px 0; border-top: 1px solid var(--garis); }
.sk-baris .sk { height: 12px; }
@keyframes sk-kilau { from { background-position: 100% 0; } to { background-position: -100% 0; } }
@media (prefers-reduced-motion: reduce) { .sk, .putar { animation: none; } .garis-jalan span { transition: none; } }
@media (max-width: 900px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
  .form-scan { grid-template-columns: 1fr; }
  .form-scan .tombol { justify-self: start; }
}
@media (max-width: 560px) {
  .pil-mode { grid-template-columns: minmax(0, 1fr); }
  .ringkas { grid-template-columns: 1fr; }
  .nama-saya { width: 100%; }
  .kepala-aksi { width: 100%; }
  .sk-baris { grid-template-columns: 1fr 1fr 1fr; }
  .kejadian li { grid-template-columns: 8px minmax(0, 1fr); }
  .kejadian time { grid-column: 2; }
  .kemajuan { grid-template-columns: auto minmax(0, 1fr); }
  .kemajuan .tombol { grid-column: 1 / -1; justify-self: start; }
  .berkas, .ket { min-width: 0; }
  .tabel { min-width: 560px; }
}
.besar { margin-top: 16px; }
.besar summary { cursor: pointer; font-weight: 600; }
.besar > p { margin: 8px 0; }
.cek-ulang { display: inline-grid; place-items: center; width: 20px; height: 20px; padding: 0; border: 0; border-radius: 6px; background: transparent; color: var(--teks-3); cursor: pointer; vertical-align: middle; }
.cek-ulang:hover { background: var(--kartu-2); color: var(--teks-kuat); }
.cek-ulang:disabled { opacity: .5; cursor: wait; }
</style>
