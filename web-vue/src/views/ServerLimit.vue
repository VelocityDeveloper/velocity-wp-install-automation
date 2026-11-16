<script setup>
// Limit Resource (VelocityGuard): pengganti LVE CloudLinux untuk server DirectAdmin non-CloudLinux (sanke).
// Limit = DA User Cgroups (systemd user-UID.slice), nilai default dari preset Kecil/Sedang/Tinggi di
// /etc/velocity-cg/preset yang diterapkan velocity-cg-default ke semua user DA (kecuali admin; nilai kustom dipertahankan).
// Data: GET /api/servers/limit (installer_status.py → scripts/server_limit_agent.py). Ganti preset: POST /api/servers/limit/aksi
// → job latar (cadangan → terapkan → verifikasi slice → kembalikan bila gagal). Override per akun: POST yang sama
// {user, nilai} → /etc/velocity-cg/user/USER (menang atas preset; nilai null = kembali ke preset).
import Dialog from '../components/Dialog.vue'
import PilihServer from '../components/PilihServer.vue'
import { pilihServer } from '../jenisServer.js'
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import Ikon from '../components/Ikon.vue'
import PelakuAkun from '../components/PelakuAkun.vue'
import { namaAkun } from '../akun.js'
import { konfirmasi } from '../konfirmasi.js'
import { minta, kirim, pakaiPolling } from '../api.js'

const lim = pakaiPolling('/api/servers/limit', 300000)
const segarkan = ref(false)
async function muatSegar() {
  segarkan.value = true
  try { lim.data.value = await minta('/api/servers/limit?segar=1'); lim.galat.value = null }
  catch (e) { lim.galat.value = e }
  finally { segarkan.value = false }
}
// Hanya server DA non-CloudLinux (CloudLinux memakai LVE sendiri)
const servers = computed(() => (lim.data.value?.servers || []).filter((s) => !s.ok || s.didukung))
const pilih = pilihServer()
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || servers.value[0] || null)
const oleh = namaAkun

// Daftar akun: Sanke 2.330 akun — render semua sekaligus bikin halaman berat. Cari + saring + paginasi.
const UKURAN = 50
const cari = ref('')
const saring = ref('semua') // semua | belum | khusus
const hal = ref(1)
const akunTersaring = computed(() => {
  const k = cari.value.trim().toLowerCase()
  return (terpilih.value?.users || []).filter((u) => (!k || u.user.includes(k))
    && (saring.value === 'semua' || (saring.value === 'belum' ? !u.sesuai : u.kecuali || Object.keys(u.override || {}).length || u.kustom.length)))
})
const jumlahHal = computed(() => Math.max(1, Math.ceil(akunTersaring.value.length / UKURAN)))
const akunTampil = computed(() => akunTersaring.value.slice((hal.value - 1) * UKURAN, hal.value * UKURAN))
const jumlahBelum = computed(() => (terpilih.value?.users || []).filter((u) => !u.sesuai).length)
watch(() => [cari.value, saring.value, terpilih.value?.host], () => { hal.value = 1 })
watch(jumlahHal, (n) => { if (hal.value > n) hal.value = n }) // data segar bisa memendekkan daftar

// ---- Tab: Monitoring (pemakaian nyata dari cgroup) | Setting (preset & limit per akun) ----
const tab = ref(['setting', 'sering'].includes(localStorage.getItem('limit-tab')) ? localStorage.getItem('limit-tab') : 'monitoring')
watch(tab, (t) => localStorage.setItem('limit-tab', t))

// Monitoring: GET /api/servers/limit/pakai?server=host[&live=1] (agen aksi 'pakai'; cache backend bersama 30 dtk, live 4 dtk)
// Mode segar: '30' (default, tiap 30 dtk) | 'live' (tiap 5 dtk, mati sendiri sesudah 15 mnt) | 'mati'. Tab tersembunyi = berhenti.
const pakai = { data: ref(null), galat: ref(null) }
const pakaiSegar = ref(false)
const MODE = { live: 5000, 30: 30000 }
const LIVE_MAKS = 15 * 60 * 1000
const modeSegar = ref('30')
const liveSisa = ref(0)
let liveSampai = 0
let timerPakai = null
let timerSisa = null
const sebelum = ref({}) // {user: cpu} ukuran sebelumnya → panah naik/turun
let nomorMinta = 0
let timerTua = null
let ulangTua = 0
async function muatPakai(segar = false) {
  const host = terpilih.value?.host
  if (!host || tab.value !== 'monitoring' || !terpilih.value.terpasang) return
  const n = ++nomorMinta
  if (segar) pakaiSegar.value = true
  try {
    const d = await minta(`/api/servers/limit/pakai?server=${encodeURIComponent(host)}${segar ? '&segar=1' : ''}${modeSegar.value === 'live' ? '&live=1' : ''}`)
    if (n === nomorMinta) {
      const lama = pakai.data.value
      if (lama?.host === d.host && lama.diambil !== d.diambil) sebelum.value = Object.fromEntries((lama.users || []).map((u) => [u.user, u.cpu]))
      else if (lama?.host !== d.host) sebelum.value = {}
      pakai.data.value = d; pakai.galat.value = null
      // data benih (cache dari disk sesudah restart, ≤5 mnt) → backend menyegarkan di latar; minta ulang cepat, maks 3×
      clearTimeout(timerTua)
      ulangTua = d.diambil && Date.now() / 1000 - d.diambil > 60 && ulangTua < 3 ? ulangTua + 1 : 0
      if (ulangTua) timerTua = setTimeout(() => { if (!document.hidden) muatPakai() }, 6000)
    }
  } catch (e) {
    if (n === nomorMinta) pakai.galat.value = e
  } finally {
    if (segar) pakaiSegar.value = false
  }
}
// setTimeout berantai (bukan setInterval): jadwal berikut dihitung sesudah jawaban datang, jadi permintaan tidak menumpuk
function jadwalPakai() {
  clearTimeout(timerPakai)
  const jeda = MODE[modeSegar.value]
  if (!jeda) return
  timerPakai = setTimeout(async () => {
    if (modeSegar.value === 'live' && Date.now() > liveSampai) { modeSegar.value = '30'; return }
    if (!document.hidden) await muatPakai()
    jadwalPakai()
  }, jeda)
}
watch(modeSegar, (m) => {
  clearInterval(timerSisa)
  if (m === 'live') {
    liveSampai = Date.now() + LIVE_MAKS
    const hitung = () => { liveSisa.value = Math.max(0, Math.ceil((liveSampai - Date.now()) / 60000)) }
    hitung(); timerSisa = setInterval(hitung, 15000)
    muatPakai()
  }
  jadwalPakai()
})
jadwalPakai()
onBeforeUnmount(() => { clearTimeout(timerPakai); clearTimeout(timerTua); clearInterval(timerSisa) })
const segarPakai = () => muatPakai(true)
const arah = (u) => { const a = sebelum.value[u.user]; return a == null ? '' : u.cpu - a >= 10 ? 'naik' : a - u.cpu >= 10 ? 'turun' : '' }
// data milik server lain tidak ditampilkan saat pindah server
const pk = computed(() => (pakai.data.value?.host === terpilih.value?.host ? pakai.data.value : null))
watch(() => [terpilih.value?.host, tab.value, terpilih.value?.terpasang], () => muatPakai(), { immediate: true })

const cariP = ref('')
const urutP = ref('cpu')
const saringP = ref('semua')
const halP = ref(1)
const mentokCpu = (u) => u.cpu_kena > 0
const mentokRam = (u) => u.mem_kena > 0 || u.oom > 0
const KUNCI_URUT = { cpu: (u) => u.cpu, mem: (u) => u.mem || 0, io: (u) => u.io_baca + u.io_tulis, proses: (u) => u.proses || 0, tahan: (u) => u.cpu_tahan_dtk }
const pakaiTersaring = computed(() => {
  const k = cariP.value.trim().toLowerCase()
  const f = { semua: () => true, cpu: mentokCpu, ram: mentokRam, mentok: (u) => mentokCpu(u) || mentokRam(u) || u.proses_kena > 0 }[saringP.value]
  const urut = KUNCI_URUT[urutP.value]
  return (pk.value?.users || []).filter((u) => (!k || u.user.includes(k)) && f(u)).sort((a, b) => urut(b) - urut(a))
})
const jumlahHalP = computed(() => Math.max(1, Math.ceil(pakaiTersaring.value.length / UKURAN)))
const pakaiTampil = computed(() => pakaiTersaring.value.slice((halP.value - 1) * UKURAN, halP.value * UKURAN))
watch(() => [cariP.value, urutP.value, saringP.value, terpilih.value?.host], () => { halP.value = 1 })
watch(jumlahHalP, (n) => { if (halP.value > n) halP.value = n })
const hitungMentok = computed(() => (pk.value?.users || []).filter(mentokCpu).length)
const hitungRam = computed(() => (pk.value?.users || []).filter(mentokRam).length)
const hitungProses = computed(() => (pk.value?.users || []).filter((u) => u.proses_kena > 0).length)

const persen = (a, b) => (b ? Math.round((a / b) * 100) : 0)
const gb = (b) => `${(b / 1073741824).toFixed(1)} GB`
const lebar = (v, maks) => `${maks ? Math.min(100, Math.round(((v || 0) / maks) * 100)) : 0}%`
const kelasBar = (v, maks) => { const p = maks ? (v || 0) / maks : 0; return p >= 0.9 ? 'merah' : p >= 0.7 ? 'kuning' : '' }
const laju = (b) => (!b ? '0' : b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB/dtk` : `${Math.max(1, Math.round(b / 1024))} KB/dtk`)
const durasi = (s) => (s >= 3600 ? `${Math.floor(s / 3600)} j ${Math.round((s % 3600) / 60)} m` : s >= 60 ? `${Math.round(s / 60)} m` : `${s} dtk`)
const waktuJam = (t) => (t ? new Date(t * 1000).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—')
function aturDariMonitor(user) {
  tab.value = 'setting'
  const u = terpilih.value?.users?.find((x) => x.user === user)
  if (u && !u.kecuali) bukaForm(u)
  else cari.value = user
}

// ---- Tab Sering Kena Batas: GET /api/servers/limit/sering?server=host&hari=N (rekap timer server-limit-riwayat tiap 5 mnt) ----
const sering = { data: ref(null), galat: ref(null), memuat: ref(false) }
const hariS = ref(7)
const cariS = ref('')
const urutS = ref('jam')
const saringS = ref('semua')
const halS = ref(1)
async function muatSering() {
  const host = terpilih.value?.host
  if (!host || tab.value !== 'sering') return
  sering.memuat.value = true
  try {
    const d = await minta(`/api/servers/limit/sering?server=${encodeURIComponent(host)}&hari=${hariS.value}`)
    if (host === terpilih.value?.host) { sering.data.value = d; sering.galat.value = null }
  } catch (e) {
    sering.galat.value = e
  } finally {
    sering.memuat.value = false
  }
}
watch(() => [terpilih.value?.host, tab.value, hariS.value], muatSering, { immediate: true })
const timerSering = setInterval(() => { if (tab.value === 'sering' && !document.hidden) muatSering() }, 300000)
onBeforeUnmount(() => clearInterval(timerSering))
const sr = computed(() => (sering.data.value?.host === terpilih.value?.host ? sering.data.value : null))
const limitAkun = computed(() => Object.fromEntries((terpilih.value?.users || []).map((u) => [u.user, u])))
const URUT_S = { jam: (u) => u.jam_kena * 1e9 + u.tahan_dtk, tahan: (u) => u.tahan_dtk, ram: (u) => u.oom * 1e6 + u.mem, proses: (u) => u.proses, terakhir: (u) => u.terakhir }
const seringTersaring = computed(() => {
  const k = cariS.value.trim().toLowerCase()
  const f = { semua: () => true, cpu: (u) => u.tahan_dtk >= 60, ram: (u) => u.mem || u.oom, proses: (u) => u.proses }[saringS.value]
  const urut = URUT_S[urutS.value]
  return (sr.value?.users || []).filter((u) => (!k || u.user.includes(k)) && f(u)).sort((a, b) => urut(b) - urut(a))
})
const jumlahHalS = computed(() => Math.max(1, Math.ceil(seringTersaring.value.length / UKURAN)))
const seringTampil = computed(() => seringTersaring.value.slice((halS.value - 1) * UKURAN, halS.value * UKURAN))
watch(() => [cariS.value, urutS.value, saringS.value, hariS.value, terpilih.value?.host], () => { halS.value = 1 })
watch(jumlahHalS, (n) => { if (halS.value > n) halS.value = n })
// "jam kena" dibanding jam yang terekam dengan kriteria jam kena sekarang (ukur_jam; riwayat baru → pembagi tidak 24×hari)
const jamTerekam = computed(() => Math.max(1, Math.round(((sr.value?.ukur_jam ?? sr.value?.ukur ?? 0) * (sr.value?.interval_mnt || 5)) / 60)))
const cukupRiwayat = computed(() => jamTerekam.value >= 6) // < 6 jam: persentase belum mewakili, hanya OOM/RAM yang ditandai
const parah = (u) => (u.oom || (cukupRiwayat.value && u.jam_kena / jamTerekam.value >= 0.5) ? 'merah'
  : u.mem || (cukupRiwayat.value && u.jam_kena / jamTerekam.value >= 0.2) ? 'kuning' : '')
const hitS = computed(() => {
  const d = sr.value?.users || []
  return { total: d.length, sering: d.filter((u) => parah(u) === 'merah').length, ram: d.filter((u) => u.mem || u.oom).length, proses: d.filter((u) => u.proses).length }
})
const maksHarian = (u) => Math.max(1, ...u.harian)
const tglPendek = (t) => new Date(`${t}T00:00:00`).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })
const waktuLengkap = (t) => (t ? new Date(t * 1000).toLocaleString('id-ID', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—')
const labelLimit = (user) => {
  const u = limitAkun.value[user]
  if (!u) return ''
  if (u.kecuali) return 'dikecualikan'
  if (Object.keys(u.override || {}).length) return 'per akun'
  return u.kustom.length ? 'kustom' : `preset ${terpilih.value?.preset || ''}`
}

const PRESET = [
  { k: 'kecil', label: 'Kecil', ket: 'Situs company profile / blog ringan' },
  { k: 'sedang', label: 'Sedang', ket: 'Toko online / berita dengan trafik sedang' },
  { k: 'tinggi', label: 'Tinggi', ket: 'Situs ramai, banyak plugin / cron berat' },
]
const BARIS = [
  { k: 'CPUQuota', label: 'CPU', f: (v) => `${v} (${Number.parseInt(v) / 100} core)` },
  { k: 'MemoryMax', label: 'RAM maksimal', f: (v) => `${v}B` },
  { k: 'IOReadBandwidthMax', label: 'IO baca', f: (v) => `${v}B/dtk` },
  { k: 'IOWriteBandwidthMax', label: 'IO tulis', f: (v) => `${v}B/dtk` },
  { k: 'IOReadIOPSMax', label: 'IOPS baca', f: (v) => v },
  { k: 'IOWriteIOPSMax', label: 'IOPS tulis', f: (v) => v },
  { k: 'TasksMax', label: 'Proses / thread', f: (v) => v },
  { k: 'EP', label: 'PHP serentak (EP)', f: (v) => `${v} request` },
  { k: 'MySQLConn', label: 'Koneksi MySQL', f: (v) => `${v} per user database` },
  { k: 'MySQLTime', label: 'Lama query MySQL', f: (v) => `maks ${v} dtk` },
]
// ringkas batas MySQL semua akun database user: "15 kon · 30 dtk" (nilai berbeda digabung "15/7")
const sqlRingkas = (akun) => {
  if (!akun?.length) return '—'
  const u = (k) => [...new Set(akun.map((x) => (x[k] === '0' ? '∞' : x[k])))].join('/')
  return `${u('koneksi')} kon · ${u('query')} dtk`
}
const PESAN = {
  invalid_oleh: 'Masuk dulu lewat tombol "Masuk dengan VD.net" di kanan atas — setiap perubahan dicatat atas nama akun Anda.',
  login_diperlukan: 'Sesi login habis atau belum masuk. Klik "Masuk dengan VD.net" di kanan atas.',
  server_tidak_dikenal: 'Server tidak dikenal; muat ulang halaman.',
  aksi_sedang_jalan: 'Masih ada perubahan berjalan di server ini. Tunggu selesai dulu.',
  preset_tidak_dikenal: 'Preset tidak dikenal.',
  velocity_cg_belum_terpasang: 'Mekanisme limit belum terpasang di server ini (build/sanke/cgroup/pasang.sh).',
  kunci_sibuk: 'Timer/hook limit di server masih berjalan lebih dari 10 menit — tidak ada yang diubah. Coba lagi nanti.',
  verifikasi_gagal: 'Nilai limit (slice, EP, atau MySQL) tidak sesuai sesudah diterapkan — semua dikembalikan ke preset lama.',
  galat: 'Agen berhenti karena galat — keadaan bisa setengah jadi. Muat ulang dan periksa kolom Status akun; cadangan ada di /root/velocity-cadangan/limit-resource-*.',
  bukan_directadmin: 'Bukan server DirectAdmin.',
  cloudlinux_pakai_lve: 'Server CloudLinux — limit memakai LVE.',
  job_tidak_ada: 'Status perubahan hilang (layanan dashboard di-restart). Muat ulang.',
  forbidden: 'Ditolak: hanya bisa dijalankan dari halaman dashboard ini.',
  user_tidak_ada: 'User DA tidak ada di server ini.',
  user_dikecualikan: 'Akun ini dikecualikan (tanpa batas) — tidak bisa diatur per akun.',
  nilai_tidak_sah: 'Ada nilai yang tidak sah (harus angka bulat positif; MySQL boleh 0 = tanpa batas).',
  timeout: 'Server tidak menjawab (timeout) — keadaan bisa setengah jadi. Muat ulang dan periksa kolom Status akun.',
}
const pesanGalat = (e) => PESAN[e] || e || 'gagal'
const pesan = reactive({ teks: '', galat: false })
const dipilih = ref('')
watch(() => [terpilih.value?.host, terpilih.value?.preset], ([, p]) => { dipilih.value = p || '' }, { immediate: true })

const ringkas = (n) => (n == null ? 'tanpa batas' : n)
const mem = (b) => (b == null ? 'tanpa batas' : `${Math.round(b / 1048576)} MB`)

// ---- Form limit per akun (satuan form → nilai user.conf/override) ----
// Default LVE server Cahyadi (lvectl list, 25 Okt 2026): SPEED 100, PMEM 1024M, EP 20, NPROC 100, IO 1024 KB/s, IOPS 1024; tanpa MySQL Governor
const LVE_CAHYADI = { cpu: 100, ram: 1024, ioBaca: 1024, ioTulis: 1024, iopsBaca: 1024, iopsTulis: 1024, proses: 100, ep: 20, sqlKon: 0, sqlDtk: 0 }
const ISIAN = [
  { k: 'cpu', label: 'CPU (%)', ket: '100 = 1 core', min: 1 },
  { k: 'ram', label: 'RAM maksimal (MB)', min: 1 },
  { k: 'ioBaca', label: 'IO baca (KB/dtk)', min: 1 },
  { k: 'ioTulis', label: 'IO tulis (KB/dtk)', min: 1 },
  { k: 'iopsBaca', label: 'IOPS baca', min: 1 },
  { k: 'iopsTulis', label: 'IOPS tulis', min: 1 },
  { k: 'proses', label: 'Proses / thread', min: 1 },
  { k: 'ep', label: 'PHP serentak (EP)', min: 1 },
  { k: 'sqlKon', label: 'Koneksi MySQL', ket: '0 = tanpa batas', min: 0 },
  { k: 'sqlDtk', label: 'Lama query MySQL (dtk)', ket: '0 = tanpa batas', min: 0 },
]
const KB = (v) => { const m = /^(\d+)([KMG]?)$/.exec(v || ''); return m ? Number(m[1]) * { '': 0.001, K: 1, M: 1000, G: 1e6 }[m[2]] : null }
const MB = (v) => { const m = /^(\d+)([MG])$/.exec(v || ''); return m ? Number(m[1]) * (m[2] === 'G' ? 1024 : 1) : null }
function keForm(u, preset) {
  const n = { ...preset, ...u.nilai, ...u.override }
  const sql = u.mysql?.[0]
  return {
    cpu: Number.parseInt(n.CPUQuota), ram: MB(n.MemoryMax), ioBaca: KB(n.IOReadBandwidthMax), ioTulis: KB(n.IOWriteBandwidthMax),
    iopsBaca: Number(n.IOReadIOPSMax), iopsTulis: Number(n.IOWriteIOPSMax), proses: Number(n.TasksMax),
    ep: Number(u.override?.EP || u.ep?.[0] || preset.EP),
    sqlKon: Number(u.override?.MySQLConn ?? sql?.koneksi ?? preset.MySQLConn), sqlDtk: Number(u.override?.MySQLTime ?? sql?.query ?? preset.MySQLTime),
  }
}
const dariForm = (f) => ({
  CPUQuota: `${f.cpu}%`, MemoryMax: f.ram % 1024 ? `${f.ram}M` : `${f.ram / 1024}G`, IOReadBandwidthMax: `${f.ioBaca}K`,
  IOWriteBandwidthMax: `${f.ioTulis}K`, IOReadIOPSMax: String(f.iopsBaca), IOWriteIOPSMax: String(f.iopsTulis),
  TasksMax: String(f.proses), EP: String(f.ep), MySQLConn: String(f.sqlKon), MySQLTime: String(f.sqlDtk),
})
const form = reactive({ buka: false, user: null, data: {} })
function bukaForm(u) {
  Object.assign(form, { buka: true, user: u, data: keForm(u, terpilih.value.daftar[terpilih.value.preset]) })
}

async function kirimUser(user, nilai, teksJalan) {
  if (!oleh.value.trim()) { Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true }); return }
  const s = terpilih.value
  try {
    const j = await kirim('/api/servers/limit/aksi', { server: s.host, user, nilai, oleh: oleh.value.trim() })
    jobs.value = { ...jobs.value, [s.host]: j }
    Object.assign(pesan, { teks: `${s.name}: ${teksJalan}…`, galat: false })
    form.buka = false
    pantau()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  }
}
function simpanUser() {
  const f = form.data
  if (ISIAN.some((i) => !Number.isInteger(f[i.k]) || f[i.k] < i.min)) { Object.assign(pesan, { teks: PESAN.nilai_tidak_sah, galat: true }); return }
  kirimUser(form.user.user, dariForm(f), `mengatur limit ${form.user.user}`)
}
async function kembaliPreset(u) {
  const ya = await konfirmasi({
    judul: `Kembalikan ${u.user} ke preset ${terpilih.value.preset}?`, tombol: 'Kembalikan',
    teks: 'Limit khusus akun ini dihapus; CPU, RAM, IO, proses, EP, dan batas MySQL kembali mengikuti preset server. Cadangan dibuat.',
  })
  if (ya) kirimUser(u.user, null, `mengembalikan ${u.user} ke preset`)
}

// ---- Job terapkan (per host; gagal ambil status sekali = coba lagi, bukan dianggap gagal) ----
const jobs = ref({})
let timer = null
const job = computed(() => jobs.value[terpilih.value?.host] || null)
watch(() => lim.data.value?.job, (d) => { for (const j of d || []) jobs.value = { ...jobs.value, [j.host]: j }; pantau() })
const berjalan = computed(() => job.value?.status === 'berjalan')
let galatBeruntun = 0
function pantau() {
  const aktif = () => Object.values(jobs.value).find((j) => j.status === 'berjalan')
  if (timer || !aktif()) return
  timer = setInterval(async () => {
    const j = aktif()
    if (!j) { clearInterval(timer); timer = null; return }
    let baru
    try {
      baru = await minta(`/api/servers/limit/job?id=${j.id}`); galatBeruntun = 0
    } catch (e) {
      if (++galatBeruntun < 5) return
      baru = { ...j, status: 'gagal', hasil: { error: e.message } }
    }
    jobs.value = { ...jobs.value, [j.host]: baru }
    if (baru.status !== 'berjalan') {
      clearInterval(timer); timer = null
      Object.assign(pesan, baru.status === 'selesai'
        ? { teks: baru.user ? `${baru.server}: limit ${baru.user} diterapkan.` : `${baru.server}: preset ${baru.preset} diterapkan.`, galat: false }
        : { teks: `${baru.server}: ${pesanGalat(baru.hasil?.error)}`, galat: true })
      muatSegar()
      pantau() // job server lain masih berjalan
    }
  }, 3000)
}
onBeforeUnmount(() => clearInterval(timer))

async function terapkan() {
  if (!oleh.value.trim()) { Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true }); return }
  const s = terpilih.value
  const p = s.daftar[dipilih.value]
  const ya = await konfirmasi({
    judul: `Terapkan preset ${dipilih.value} di ${s.name}?`, tombol: 'Terapkan',
    teks: `Semua user DA (kecuali admin dan nilai kustom) dibatasi CPU ${p.CPUQuota}, RAM ${p.MemoryMax}, IO ${p.IOReadBandwidthMax}B/dtk, ${p.TasksMax} proses, ${p.EP} request PHP serentak, ${p.MySQLConn} koneksi MySQL & query maks ${p.MySQLTime} dtk. Berlaku langsung tanpa restart; user baru & hasil restore ikut. Cadangan dibuat, bila verifikasi gagal dikembalikan otomatis.`,
  })
  if (!ya) return
  try {
    const j = await kirim('/api/servers/limit/aksi', { server: s.host, preset: dipilih.value, oleh: oleh.value.trim() })
    jobs.value = { ...jobs.value, [s.host]: j }
    Object.assign(pesan, { teks: `${s.name}: menerapkan preset ${dipilih.value}…`, galat: false })
    pantau()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  }
}
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Limit Resource <span class="merek-guard">VelocityGuard</span></h1>
        <p class="redup">Pengganti LVE CloudLinux untuk server DirectAdmin biasa: batas CPU, RAM, IO, dan proses per akun lewat cgroup DirectAdmin.</p>
      </div>
      <div class="kepala-aksi">
        <div class="nama-saya"><span class="redup">Dicatat sebagai</span><PelakuAkun id="nama-limit" /></div>
        <button type="button" class="tombol kecil" :disabled="segarkan || (lim.memuat.value && !lim.data.value)" @click="muatSegar"><Ikon nama="ulang" :ukuran="16" /> {{ segarkan ? 'Membaca…' : 'Muat ulang' }}</button>
      </div>
    </header>

    <p v-if="lim.memuat.value && !lim.data.value" class="redup" role="status">Membaca limit semua server lewat SSH…</p>
    <p v-else-if="lim.galat.value && !lim.data.value" class="pesan-status bahaya">Gagal memuat: {{ lim.galat.value.message }}</p>
    <p v-else-if="lim.data.value?.error" class="pesan-status bahaya">Gagal memuat: {{ pesanGalat(lim.data.value.error) }}</p>
    <p v-else-if="lim.data.value && !servers.length" class="redup">Tidak ada server DirectAdmin non-CloudLinux.</p>

    <template v-else-if="terpilih">
      <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>
      <PilihServer :servers="servers" :model-value="terpilih.name" :titik="terpilih.terpasang ? 'baik' : 'abu'" @update:model-value="pilih = $event" />

      <section class="kartu" aria-labelledby="judul-limit">
        <div class="kartu-judul">
          <h2 id="judul-limit"><Ikon nama="server" :ukuran="16" /> {{ terpilih.name }}
            <span v-if="terpilih.terpasang" class="lencana hijau">Preset aktif: {{ terpilih.preset }}</span>
          </h2>
        </div>
        <div class="tab" role="tablist" aria-label="Bagian Limit Resource">
          <button type="button" role="tab" :aria-selected="tab === 'monitoring'" :class="{ aktif: tab === 'monitoring' }" @click="tab = 'monitoring'"><Ikon nama="pantau" :ukuran="14" /> Monitoring</button>
          <button type="button" role="tab" :aria-selected="tab === 'sering'" :class="{ aktif: tab === 'sering' }" @click="tab = 'sering'"><Ikon nama="peringatan" :ukuran="14" /> Sering Kena Batas</button>
          <button type="button" role="tab" :aria-selected="tab === 'setting'" :class="{ aktif: tab === 'setting' }" @click="tab = 'setting'"><Ikon nama="sunting" :ukuran="14" /> Setting</button>
        </div>
        <p v-if="!terpilih.ok" class="pesan-status bahaya">Tidak bisa dibaca: {{ pesanGalat(terpilih.error) }} {{ terpilih.pesan || '' }}</p>
        <p v-else-if="!terpilih.terpasang" class="pesan-status waspada">{{ PESAN.velocity_cg_belum_terpasang }}</p>

        <!-- ===== Monitoring pemakaian ===== -->
        <template v-else-if="tab === 'monitoring'">
          <p v-if="!pk && pakai.galat.value" class="pesan-status bahaya">Gagal membaca pemakaian: {{ pesanGalat(pakai.galat.value.message) }}</p>
          <p v-else-if="pk?.ok === false || pk?.error" class="pesan-status bahaya">Gagal membaca pemakaian: {{ pesanGalat(pk.error) }} {{ pk.pesan || '' }}</p>
          <p v-else-if="!pk" class="redup" role="status">Mengukur pemakaian akun di {{ terpilih.name }} (sampel 3 detik)…</p>
          <template v-else>
            <div class="ringkas-grid">
              <div class="ringkas-k"><small>Load server</small><b>{{ pk.load?.[0] ?? '—' }}</b><span class="redup">{{ pk.cpu_inti }} inti · 15 mnt {{ pk.load?.[2] }}</span></div>
              <div class="ringkas-k"><small>RAM server terpakai</small><b>{{ persen(pk.ram_total - pk.ram_tersedia, pk.ram_total) }}%</b><span class="redup">{{ gb(pk.ram_total - pk.ram_tersedia) }} / {{ gb(pk.ram_total) }}</span></div>
              <div class="ringkas-k"><small>Akun aktif</small><b>{{ pk.users.length }}</b><span class="redup">dari {{ pk.akun_total }} akun (punya proses)</span></div>
              <div class="ringkas-k" :class="{ waspada: hitungMentok }"><small>Sedang mentok CPU</small><b>{{ hitungMentok }}</b><span class="redup">ditahan saat sampel</span></div>
              <div class="ringkas-k" :class="{ bahaya: hitungRam }"><small>Pernah mentok RAM / OOM</small><b>{{ hitungRam }}</b><span class="redup">sejak slice aktif</span></div>
              <div class="ringkas-k" :class="{ waspada: hitungProses }"><small>Pernah mentok proses</small><b>{{ hitungProses }}</b><span class="redup">sejak slice aktif</span></div>
            </div>

            <div class="saring-akun">
              <input v-model="cariP" type="search" placeholder="Cari user DA…" aria-label="Cari user DA (monitoring)">
              <select v-model="urutP" aria-label="Urutkan">
                <option value="cpu">Urut CPU</option>
                <option value="mem">Urut RAM</option>
                <option value="io">Urut IO</option>
                <option value="proses">Urut proses</option>
                <option value="tahan">Urut lama CPU ditahan</option>
              </select>
              <select v-model="saringP" aria-label="Saring monitoring">
                <option value="semua">Semua akun aktif</option>
                <option value="mentok">Kena batas apa saja</option>
                <option value="cpu">Sedang mentok CPU</option>
                <option value="ram">Pernah mentok RAM / OOM</option>
              </select>
              <span class="isi" />
              <div class="tab tab-kecil" role="radiogroup" aria-label="Segarkan otomatis">
                <button type="button" role="radio" :aria-checked="modeSegar === 'live'" :class="{ aktif: modeSegar === 'live' }" title="Ukur tiap 5 detik, berhenti sendiri sesudah 15 menit" @click="modeSegar = 'live'"><span class="titik-live" :class="{ nyala: modeSegar === 'live' }" aria-hidden="true" /> Live</button>
                <button type="button" role="radio" :aria-checked="modeSegar === '30'" :class="{ aktif: modeSegar === '30' }" @click="modeSegar = '30'">30 dtk</button>
                <button type="button" role="radio" :aria-checked="modeSegar === 'mati'" :class="{ aktif: modeSegar === 'mati' }" @click="modeSegar = 'mati'">Mati</button>
              </div>
              <button type="button" class="tombol garis kecil" :disabled="pakaiSegar" @click="segarPakai"><Ikon nama="ulang" :ukuran="14" /> {{ pakaiSegar ? 'Mengukur…' : 'Ukur sekarang' }}</button>
            </div>
            <p class="redup kecil-p" aria-live="polite">Diukur {{ waktuJam(pk.diambil) }}<template v-if="modeSegar === 'live'"> · <b class="teks-live">Live tiap 5 dtk</b>, mati sendiri ±{{ liveSisa }} mnt lagi</template> · CPU & IO = rata-rata {{ pk.jeda }} dtk terakhir; 100% = 1 core; ▲▼ = CPU berubah ≥10 poin dari ukuran sebelumnya. Akun tanpa proses berjalan tidak tampil.</p>

            <div class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">User</th><th scope="col">CPU</th><th scope="col">RAM</th><th scope="col">Proses</th><th scope="col">IO baca / tulis</th><th scope="col">Kena batas</th><th scope="col" /></tr></thead>
                <tbody>
                  <tr v-for="u in pakaiTampil" :key="u.user">
                    <td><b>{{ u.user }}</b></td>
                    <td class="sel-bar"><div class="bar" :class="kelasBar(u.cpu, u.cpu_max)"><i :style="{ width: lebar(u.cpu, u.cpu_max) }" /></div>{{ u.cpu }}%<span v-if="arah(u)" class="arah" :class="arah(u)" :title="`sebelumnya ${sebelum[u.user]}%`">{{ arah(u) === 'naik' ? '▲' : '▼' }}</span><small class="kecil">batas {{ u.cpu_max == null ? '∞' : `${u.cpu_max}%` }}</small></td>
                    <td class="sel-bar"><div class="bar" :class="kelasBar(u.mem, u.mem_max)"><i :style="{ width: lebar(u.mem, u.mem_max) }" /></div>{{ mem(u.mem) }}<small class="kecil">puncak {{ mem(u.mem_peak) }} · batas {{ mem(u.mem_max) }}</small></td>
                    <td>{{ u.proses ?? '—' }}<small class="kecil">batas {{ u.proses_max ?? '∞' }}</small></td>
                    <td>{{ laju(u.io_baca) }}<small class="kecil">tulis {{ laju(u.io_tulis) }}</small></td>
                    <td>
                      <span v-if="u.cpu_kena" class="lencana kuning" :title="`${u.cpu_kena} periode CPU ditahan selama sampel`">CPU</span>
                      <span v-if="u.oom" class="lencana merah" :title="`${u.oom} proses dimatikan OOM sejak slice aktif`">OOM {{ u.oom }}</span>
                      <span v-else-if="u.mem_kena" class="lencana merah" :title="`${u.mem_kena}× menyentuh batas RAM sejak slice aktif`">RAM {{ u.mem_kena }}×</span>
                      <span v-if="u.proses_kena" class="lencana kuning" :title="`${u.proses_kena}× menyentuh batas proses (fork ditolak) sejak slice aktif`">Proses {{ u.proses_kena }}×</span>
                      <small v-if="u.cpu_tahan_dtk" class="kecil" title="Total waktu CPU ditahan sejak slice aktif">ditahan {{ durasi(u.cpu_tahan_dtk) }}</small>
                      <span v-if="!u.cpu_kena && !u.mem_kena && !u.oom && !u.proses_kena && !u.cpu_tahan_dtk" class="redup">—</span>
                    </td>
                    <td><button type="button" class="tombol garis kecil" @click="aturDariMonitor(u.user)">Atur</button></td>
                  </tr>
                  <tr v-if="!pakaiTersaring.length"><td colspan="7" class="redup">Tidak ada akun yang cocok.</td></tr>
                </tbody>
              </table>
            </div>
            <div v-if="pakaiTersaring.length > UKURAN" class="paginasi">
              <span class="redup">{{ (halP - 1) * UKURAN + 1 }}–{{ Math.min(halP * UKURAN, pakaiTersaring.length) }} dari {{ pakaiTersaring.length }} akun · halaman {{ halP }}/{{ jumlahHalP }}</span>
              <span>
                <button type="button" class="tombol garis kecil" :disabled="halP <= 1" @click="halP = 1">Awal</button>
                <button type="button" class="tombol garis kecil" :disabled="halP <= 1" @click="halP--">Sebelumnya</button>
                <button type="button" class="tombol garis kecil" :disabled="halP >= jumlahHalP" @click="halP++">Berikutnya</button>
                <button type="button" class="tombol garis kecil" :disabled="halP >= jumlahHalP" @click="halP = jumlahHalP">Akhir</button>
              </span>
            </div>
          </template>
        </template>

        <!-- ===== Sering kena batas (riwayat) ===== -->
        <template v-else-if="tab === 'sering'">
          <p v-if="!sr && sering.galat.value" class="pesan-status bahaya">Gagal membaca riwayat: {{ pesanGalat(sering.galat.value.message) }}</p>
          <p v-else-if="!sr" class="redup" role="status">Membaca riwayat kena batas…</p>
          <template v-else>
            <div class="ringkas-grid">
              <div class="ringkas-k"><small>Akun pernah kena batas</small><b>{{ hitS.total }}</b><span class="redup">dari {{ sr.akun_terukur }} akun aktif terukur</span></div>
              <div class="ringkas-k" :class="{ bahaya: hitS.sering }"><small>Sangat sering (≥50% jam / OOM)</small><b>{{ hitS.sering }}</b><span class="redup">kandidat naik limit / cek situs</span></div>
              <div class="ringkas-k" :class="{ bahaya: hitS.ram }"><small>Kena batas RAM / OOM</small><b>{{ hitS.ram }}</b><span class="redup">akun</span></div>
              <div class="ringkas-k" :class="{ waspada: hitS.proses }"><small>Kena batas proses</small><b>{{ hitS.proses }}</b><span class="redup">akun</span></div>
            </div>

            <div class="saring-akun">
              <input v-model="cariS" type="search" placeholder="Cari user DA…" aria-label="Cari user DA (riwayat)">
              <select v-model="urutS" aria-label="Urutkan riwayat">
                <option value="jam">Urut paling sering</option>
                <option value="tahan">Urut lama CPU ditahan</option>
                <option value="ram">Urut kena RAM / OOM</option>
                <option value="proses">Urut kena batas proses</option>
                <option value="terakhir">Urut terakhir kena</option>
              </select>
              <select v-model="saringS" aria-label="Saring riwayat">
                <option value="semua">Semua batas</option>
                <option value="cpu">CPU</option>
                <option value="ram">RAM / OOM</option>
                <option value="proses">Proses</option>
              </select>
              <span class="isi" />
              <div class="tab tab-kecil" role="radiogroup" aria-label="Rentang riwayat">
                <button v-for="h in [1, 7, 30]" :key="h" type="button" role="radio" :aria-checked="hariS === h" :class="{ aktif: hariS === h }" @click="hariS = h">{{ h === 1 ? 'Hari ini' : `${h} hari` }}</button>
              </div>
            </div>
            <p class="redup kecil-p">Dicatat tiap {{ sr.interval_mnt }} menit sejak {{ sr.mulai ? tglPendek(sr.mulai) : '—' }} ({{ sr.ukur }} ukuran ≈ {{ jamTerekam }} jam terekam di rentang ini). <b>Jam kena</b> = jumlah jam yang akun itu ditahan CPU ≥30 detik dalam 5 menit, atau menyentuh batas RAM / proses ({{ jamTerekam }} jam terekam dengan kriteria ini). Grafik kecil = lama CPU ditahan per hari.</p>
            <p v-if="!cukupRiwayat" class="pesan-status waspada">Riwayat baru {{ jamTerekam }} jam — label "sangat sering" baru dihitung sesudah 6 jam terekam; makin lama makin akurat.</p>

            <div class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">User</th><th scope="col">Jam kena</th><th scope="col">CPU ditahan</th><th scope="col">RAM</th><th scope="col">Proses</th><th scope="col">Puncak</th><th scope="col">Terakhir kena</th><th scope="col" /></tr></thead>
                <tbody>
                  <tr v-for="u in seringTampil" :key="u.user">
                    <td><b>{{ u.user }}</b><small class="kecil">{{ labelLimit(u.user) }}</small></td>
                    <td><span class="lencana" :class="parah(u) === 'merah' ? 'merah' : parah(u) === 'kuning' ? 'kuning' : 'abu'">{{ u.jam_kena }} jam</span><small class="kecil">{{ persen(u.jam_kena, jamTerekam) }}% · {{ u.hari_kena }} hari</small></td>
                    <td>
                      <div class="spark" :title="sr.tanggal.map((t, i) => `${tglPendek(t)}: ${durasi(u.harian[i])}`).join('\n')" aria-hidden="true">
                        <i v-for="(v, i) in u.harian" :key="i" :style="{ height: `${Math.max(v ? 8 : 2, Math.round((v / maksHarian(u)) * 100))}%` }" :class="{ nol: !v }" />
                      </div>
                      {{ durasi(u.tahan_dtk) }}<small class="kecil">{{ u.mentok }}× sempat ditahan saat sampel</small>
                    </td>
                    <td><span v-if="u.oom" class="lencana merah">OOM {{ u.oom }}</span><span v-if="u.mem" class="lencana kuning">{{ u.mem }}×</span><span v-if="!u.oom && !u.mem" class="redup">—</span></td>
                    <td><span v-if="u.proses" class="lencana kuning">{{ u.proses }}×</span><span v-else class="redup">—</span></td>
                    <td>CPU {{ u.cpu_puncak }}%<small class="kecil">RAM {{ u.mem_puncak }}% batas</small></td>
                    <td>{{ waktuLengkap(u.terakhir) }}</td>
                    <td><button type="button" class="tombol garis kecil" @click="aturDariMonitor(u.user)">Atur</button></td>
                  </tr>
                  <tr v-if="!seringTersaring.length"><td colspan="8" class="redup">{{ sr.users.length ? 'Tidak ada akun yang cocok.' : 'Belum ada akun yang kena batas di rentang ini.' }}</td></tr>
                </tbody>
              </table>
            </div>
            <div v-if="seringTersaring.length > UKURAN" class="paginasi">
              <span class="redup">{{ (halS - 1) * UKURAN + 1 }}–{{ Math.min(halS * UKURAN, seringTersaring.length) }} dari {{ seringTersaring.length }} akun · halaman {{ halS }}/{{ jumlahHalS }}</span>
              <span>
                <button type="button" class="tombol garis kecil" :disabled="halS <= 1" @click="halS = 1">Awal</button>
                <button type="button" class="tombol garis kecil" :disabled="halS <= 1" @click="halS--">Sebelumnya</button>
                <button type="button" class="tombol garis kecil" :disabled="halS >= jumlahHalS" @click="halS++">Berikutnya</button>
                <button type="button" class="tombol garis kecil" :disabled="halS >= jumlahHalS" @click="halS = jumlahHalS">Akhir</button>
              </span>
            </div>
          </template>
        </template>

        <!-- ===== Setting (preset & per akun) ===== -->
        <template v-else>
          <div class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">Per akun</th><th v-for="p in PRESET" :key="p.k" scope="col" :class="{ aktif: p.k === terpilih.preset }">
                <label class="pilih"><input v-model="dipilih" type="radio" name="preset" :value="p.k" :disabled="berjalan"> {{ p.label }}</label>
                <small class="redup blok-t">{{ p.ket }}</small></th></tr></thead>
              <tbody>
                <tr v-for="b in BARIS" :key="b.k"><th scope="row">{{ b.label }}</th>
                  <td v-for="p in PRESET" :key="p.k" :class="{ aktif: p.k === terpilih.preset }">{{ b.f(terpilih.daftar[p.k][b.k]) }}</td></tr>
              </tbody>
            </table>
          </div>
          <p class="redup kecil-p">Akun <code>admin</code> tidak dibatasi. Nilai yang diubah manual per user/paket di DirectAdmin (selain nilai preset) dipertahankan. Swap per akun 0. EP = <code>pm.max_children</code> PHP-FPM per versi PHP (request lebih antre, bukan error 508). Batas MySQL berlaku per user database (akun DB sistem tidak dibatasi); query yang melewati batas waktu dihentikan.</p>

          <div v-if="job" class="job" :class="job.status" role="status">
            <span v-if="berjalan" class="putar besar" aria-hidden="true" />
            <Ikon v-else :nama="job.status === 'selesai' ? 'centang' : 'peringatan'" :ukuran="20" />
            <div>
              <b>{{ berjalan ? 'Menerapkan…' : job.status === 'selesai' ? 'Berhasil' : 'Gagal' }}</b> · {{ job.user ? `akun ${job.user}` : `preset ${job.preset}` }}
              <span v-if="job.status === 'gagal'" class="blok-t">{{ pesanGalat(job.hasil?.error) }}</span>
              <small v-if="job.hasil?.hasil?.cadangan" class="redup blok-t">Cadangan: {{ job.hasil.hasil.cadangan }}</small>
            </div>
          </div>
          <div class="aksi">
            <button type="button" class="tombol" :disabled="berjalan || !dipilih || dipilih === terpilih.preset" @click="terapkan">Terapkan preset {{ dipilih }}</button>
          </div>

          <h3 class="sub">Akun ({{ terpilih.users.length }}<template v-if="jumlahBelum"> · {{ jumlahBelum }} belum diterapkan</template>)</h3>
          <div class="saring-akun">
            <input v-model="cari" type="search" placeholder="Cari user DA…" aria-label="Cari user DA">
            <select v-model="saring" aria-label="Saring akun">
              <option value="semua">Semua akun</option>
              <option value="belum">Belum diterapkan</option>
              <option value="khusus">Per akun / kustom / dikecualikan</option>
            </select>
            <span class="redup">{{ akunTersaring.length }} cocok</span>
          </div>
          <div class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">User</th><th scope="col">CPU</th><th scope="col">RAM</th><th scope="col">Proses</th><th scope="col">EP</th><th scope="col">MySQL</th><th scope="col">Status</th><th scope="col">Atur</th></tr></thead>
              <tbody>
                <tr v-for="u in akunTampil" :key="u.user">
                  <td><b>{{ u.user }}</b> <span v-if="u.kecuali" class="lencana abu">dikecualikan</span><span v-if="Object.keys(u.override || {}).length" class="lencana ungu" title="Limit khusus akun ini (bukan preset)">per akun</span><span v-else-if="u.kustom.length" class="lencana ungu" :title="u.kustom.join(', ')">kustom</span></td>
                  <td>{{ u.nyata.cpu == null ? 'tanpa batas' : `${u.nyata.cpu}%` }}</td>
                  <td>{{ mem(u.nyata.mem) }}</td>
                  <td>{{ ringkas(u.nyata.tasks) }}</td>
                  <td>{{ u.ep?.length ? u.ep.join('/') : '—' }}</td>
                  <td :title="(u.mysql || []).map((x) => `${x.akun}: ${x.koneksi} koneksi, ${x.query} dtk`).join('\n')">{{ sqlRingkas(u.mysql) }}</td>
                  <td><span class="lencana" :class="u.sesuai ? 'hijau' : 'kuning'">{{ u.sesuai ? 'sesuai' : 'belum diterapkan' }}</span></td>
                  <td class="aksi-u">
                    <template v-if="!u.kecuali">
                      <button type="button" class="tombol garis kecil" :disabled="berjalan" @click="bukaForm(u)">Atur</button>
                      <button v-if="Object.keys(u.override || {}).length" type="button" class="tombol garis kecil" :disabled="berjalan" @click="kembaliPreset(u)">Ke preset</button>
                    </template>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="akunTersaring.length > UKURAN" class="paginasi">
            <span class="redup">{{ (hal - 1) * UKURAN + 1 }}–{{ Math.min(hal * UKURAN, akunTersaring.length) }} dari {{ akunTersaring.length }} akun · halaman {{ hal }}/{{ jumlahHal }}</span>
            <span>
              <button type="button" class="tombol garis kecil" :disabled="hal <= 1" @click="hal = 1">Awal</button>
              <button type="button" class="tombol garis kecil" :disabled="hal <= 1" @click="hal--">Sebelumnya</button>
              <button type="button" class="tombol garis kecil" :disabled="hal >= jumlahHal" @click="hal++">Berikutnya</button>
              <button type="button" class="tombol garis kecil" :disabled="hal >= jumlahHal" @click="hal = jumlahHal">Akhir</button>
            </span>
          </div>
        </template>
      </section>
    </template>

    <Dialog :buka="form.buka" :judul="`Limit akun ${form.user?.user || ''}`" lebar="640px" @tutup="form.buka = false">
      <form class="form-limit" @submit.prevent="simpanUser">
        <p class="redup kecil-p">Berlaku hanya untuk akun ini dan tetap dipakai walau preset server diganti. Diisi dari nilai sekarang.</p>
        <div class="dua">
          <label v-for="i in ISIAN" :key="i.k" class="isian"><span>{{ i.label }}</span>
            <input v-model.number="form.data[i.k]" type="number" :min="i.min" step="1" required>
            <small v-if="i.ket">{{ i.ket }}</small></label>
        </div>
        <div class="aksi">
          <button type="button" class="tombol garis kecil" @click="form.data = { ...LVE_CAHYADI }">Isi seperti LVE Cahyadi</button>
          <span class="isi" />
          <button type="button" class="tombol garis kecil" @click="form.buka = false">Batal</button>
          <button type="submit" class="tombol kecil" :disabled="berjalan">Simpan</button>
        </div>
      </form>
    </Dialog>
  </div>
</template>

<style scoped>
.kecil-p { margin: 0; font-size: 13px; line-height: 1.55; }
.blok-t { display: block; }
th.aktif, td.aktif { background: var(--aksen-lembut); }
.pilih { display: inline-flex; gap: 6px; align-items: center; cursor: pointer; font-weight: 700; }
.sub { margin: 18px 0 8px; font-size: 15px; }
.job { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 12px; align-items: center; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--garis); margin: 12px 0; }
.job.selesai > svg { color: var(--baik); }
.job.gagal { border-color: color-mix(in srgb, var(--bahaya) 50%, transparent); }
.job.gagal > svg { color: var(--bahaya); }
.putar { width: 18px; height: 18px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: putar .8s linear infinite; }
@keyframes putar { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .putar { animation: none; } }
.aksi-u { white-space: nowrap; }
.saring-akun { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
.saring-akun input[type=search] { flex: 1 1 220px; max-width: 320px; width: auto; }
.saring-akun select { flex: 0 0 auto; width: auto; }
.saring-akun .pilih { white-space: nowrap; }
.saring-akun input[type=checkbox] { width: auto; }
.tab { display: inline-flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); margin-bottom: 14px; }
.tab button { display: inline-flex; gap: 6px; align-items: center; border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 7px 14px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.spark { display: flex; align-items: flex-end; gap: 2px; height: 22px; width: 90px; margin-bottom: 4px; }
.spark i { flex: 1; min-width: 2px; background: var(--bahaya); border-radius: 2px 2px 0 0; opacity: .8; }
.spark i.nol { background: var(--garis); opacity: 1; }
.tab-kecil { margin-bottom: 0; }
.tab-kecil button { padding: 5px 10px; font-size: 12px; }
.titik-live { width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); }
.titik-live.nyala { background: #ff4d4f; animation: kedip 1.2s ease-in-out infinite; }
@keyframes kedip { 50% { opacity: .35; } }
@media (prefers-reduced-motion: reduce) { .titik-live.nyala { animation: none; } }
.teks-live { color: var(--bahaya); }
.arah { margin-left: 4px; font-size: 11px; }
.arah.naik { color: var(--bahaya); }
.arah.turun { color: var(--baik); }
.ringkas-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 14px; }
.ringkas-k { display: grid; gap: 2px; padding: 10px 12px; border: 1px solid var(--garis); border-radius: 12px; }
.ringkas-k small { color: var(--teks-3); font-size: 12px; }
.ringkas-k b { font-size: 20px; }
.ringkas-k span { font-size: 12px; }
.ringkas-k.waspada { border-color: color-mix(in srgb, var(--waspada, #d99a00) 55%, transparent); }
.ringkas-k.bahaya { border-color: color-mix(in srgb, var(--bahaya) 55%, transparent); }
.saring-akun .isi { flex: 1; }
.kecil-l { font-weight: 500; font-size: 13px; }
.sel-bar { min-width: 130px; }
.bar { height: 5px; border-radius: 3px; background: var(--kartu-2); margin-bottom: 4px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--aksen); }
.bar.kuning i { background: var(--waspada, #d99a00); }
.bar.merah i { background: var(--bahaya); }
.tabel td .lencana + .lencana { margin-left: 4px; }
.paginasi { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.paginasi span:last-child { display: flex; gap: 8px; flex-wrap: wrap; }
.aksi-u .tombol + .tombol { margin-left: 6px; }
.form-limit { display: grid; gap: 12px; }
.form-limit .dua { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.form-limit .isi { flex: 1; }
@media (max-width: 560px) { .form-limit .dua { grid-template-columns: minmax(0, 1fr); } }
.aksi { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
</style>
