<script setup>
// Kerentanan CMS / WordPress (sub-menu Server): versi inti, plugin, dan tema setiap instalasi WP di server hosting
// dicocokkan dengan basis data publik wpvulnerability.net. Data: GET /api/servers/cms (ringkas, tanpa SSH),
// GET /api/servers/cms?server=<host> (detail), POST /api/servers/cms/scan (SSH hanya baca + cocokkan; thread latar).
// cPGuard "CMS Threat" (cms.db) ditampilkan sebagai pembanding selama cPGuard masih jalan.
// Tombol Perbaiki (per situs / per akun) → dialog daftar pekerjaan → POST /api/servers/cms/perbaiki
// (cadangan, WP-CLI update komponen rentan, rollback bila beranda 5xx, lalu scan ulang akun itu).
import PilihServer from '../components/PilihServer.vue'
import { pilihServer } from '../jenisServer.js'
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import Ikon from '../components/Ikon.vue'
import PelakuAkun from '../components/PelakuAkun.vue'
import { namaAkun } from '../akun.js'
import Info from '../components/Info.vue'
import Dialog from '../components/Dialog.vue'
import { konfirmasi } from '../konfirmasi.js'
import { minta, kirim, pakaiPolling, tanggalWaktu, waktuLalu, angka } from '../api.js'
import { tabUrl } from '../laravel.js'

const cms = pakaiPolling('/api/servers/cms', 0)
const riwayat = pakaiPolling('/api/servers/cms/riwayat', 0)
const servers = computed(() => cms.data.value?.servers || [])
const job = computed(() => cms.data.value?.job || null)
const berjalan = computed(() => job.value?.status === 'berjalan')
const pilih = pilihServer()
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || servers.value[0] || null)
const TAB = ['situs', 'komponen', 'cpguard', 'riwayat']
const tab = tabUrl('tab', 'situs', { boleh: TAB })

// Pelaku di riwayat = akun yang masuk ke dash.velocity.ai.id (backend menggantinya dari cookie sesi)
const oleh = namaAkun

const PESAN = {
  invalid_oleh: 'Masuk dulu lewat tombol "Masuk dengan VD.net" di kanan atas — setiap scan dicatat atas nama akun Anda.',
  login_diperlukan: 'Sesi login habis atau belum masuk. Klik "Masuk dengan VD.net" di kanan atas.',
  server_tidak_dikenal: 'Server tidak dikenal; muat ulang halaman.',
  scan_sedang_jalan: 'Masih ada scan CMS berjalan. Tunggu sampai selesai.',
  kunci_ssh_installer_tidak_ada: 'Kunci SSH installer tidak ditemukan di PC dashboard.',
  forbidden: 'Ditolak: hanya bisa dijalankan dari halaman dashboard ini.',
  timeout: 'Server tidak menjawab (timeout).',
  akun_tidak_sah: 'Nama akun tidak sah.',
  tidak_ada_yang_diperbaiki: 'Tidak ada komponen rentan yang bisa diperbarui (hasil scan mungkin sudah berubah; muat ulang).',
  wp_cli_tidak_tersedia: 'WP-CLI/PHP tidak tersedia di server.',
  path_tidak_sah: 'Path situs tidak sah.',
  wp_config_tidak_terbaca: 'wp-config.php tidak terbaca.',
  cadangan_db_gagal: 'Cadangan database gagal — situs tidak diubah.',
  akun_disuspend: 'Akun hosting sedang disuspend (database terkunci) — tidak dikerjakan.',
}
const pesanGalat = (e) => PESAN[e] || e || 'gagal'
const pesan = reactive({ teks: '', galat: false })
const proses = ref(false)

// ---- Tingkat keparahan ----
const TINGKAT = {
  kritis: { label: 'Kritis', kelas: 'merah', urut: 0 },
  tinggi: { label: 'Tinggi', kelas: 'oranye', urut: 1 },
  sedang: { label: 'Sedang', kelas: 'kuning', urut: 2 },
  rendah: { label: 'Rendah', kelas: 'abu', urut: 3 },
  tidak_diketahui: { label: 'Belum dinilai', kelas: 'abu', urut: 4 },
}
const tk = (t) => TINGKAT[t] || TINGKAT.tidak_diketahui
const JENIS = { core: 'Inti WP', plugin: 'Plugin', theme: 'Tema' }

function tingkatServer(s) {
  const r = s.ringkas
  if (!r) return 'abu'
  if (r.kritis) return 'bahaya'
  if (r.tinggi || r.sedang) return 'waspada'
  return 'baik'
}
// ---- Scan ----
async function mulaiScan(server) {
  if (!oleh.value.trim()) {
    Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true })
    document.getElementById('nama-cms')?.focus()
    return
  }
  const semua = server === 'semua'
  const ya = await konfirmasi({
    judul: semua ? 'Scan CMS semua server?' : `Scan CMS ${terpilih.value.name}?`,
    teks: 'Server hanya dibaca (daftar instalasi WordPress, versi plugin & tema) dengan prioritas rendah, lalu dicocokkan dengan basis data kerentanan. Tidak ada berkas yang diubah. Biasanya 1–5 menit.',
    tombol: 'Mulai scan',
  })
  if (!ya) return
  proses.value = true
  try {
    await kirim('/api/servers/cms/scan', { server: semua ? 'semua' : terpilih.value.host, oleh: oleh.value.trim() })
    Object.assign(pesan, { teks: 'Scan dimulai.', galat: false })
    await cms.muatUlang()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
// Scan otomatis harian per server (backend: tiap hari jam_jadwal; kerentanan kritis/tinggi baru → Telegram)
const jadwal = computed(() => cms.data.value?.jadwal?.[terpilih.value?.host] || {})
async function aturJadwal(nilai) {
  if (!oleh.value.trim()) {
    Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true })
    return
  }
  proses.value = true
  try {
    const r = await kirim('/api/servers/cms/jadwal', { server: terpilih.value.host, harian: nilai, oleh: oleh.value.trim() })
    cms.data.value = { ...cms.data.value, jadwal: r.jadwal }
    Object.assign(pesan, { teks: `Scan CMS harian ${terpilih.value.name} ${nilai ? 'diaktifkan' : 'dimatikan'}.`, galat: false })
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
// Selama scan berjalan: muat ulang ringkas tiap 3 dtk; sesudah selesai muat detail & riwayat
const timer = setInterval(() => { if (berjalan.value) cms.muatUlang() }, 3000)
onBeforeUnmount(() => clearInterval(timer))
watch(berjalan, (now, dulu) => {
  if (dulu && !now) {
    muatDetail()
    riwayat.muatUlang()
    const j = job.value
    if (j?.jenis === 'perbaiki') {
      const n = j.situs?.length || 0
      const gagal = (j.situs || []).filter((h) => !h.ok).length
      Object.assign(pesan, { teks: `Perbaikan akun ${j.user} ${j.status === 'gagal' ? `bermasalah: ${pesanGalat(j.error)}` : 'selesai'} — ${n - gagal}/${n} situs berhasil${j.akun ? `; sesudah scan ulang ${j.akun.rentan} dari ${j.akun.situs} situs akun ini masih rentan` : ''}.`, galat: j.status === 'gagal' || !!gagal })
    } else if (j?.status === 'gagal') Object.assign(pesan, { teks: `Scan gagal: ${j.error}`, galat: true })
    else if (j) Object.assign(pesan, { teks: `Scan selesai${j.galat_api ? ` (${j.galat_api} komponen gagal dicek ke basis data kerentanan — dicoba lagi di scan berikutnya)` : ''}.`, galat: !!j.galat_api })
  }
})
const labelKemajuan = computed(() => {
  const k = job.value?.kemajuan
  if (!k) return 'Menyiapkan…'
  if (k.tahap === 'perbaiki') return `Memperbaiki ${k.domain} (${k.ke}/${k.dari} situs selesai) — cadangan, update, cek beranda…`
  if (job.value?.jenis === 'perbaiki' && k.tahap === 'inventaris') return `Scan ulang akun ${job.value.user}…`
  return k.tahap === 'inventaris'
    ? `Membaca instalasi WordPress di server (${k.ke}/${k.dari} server selesai)…`
    : `Mencocokkan ${angka(k.dari)} komponen dengan basis data kerentanan (${angka(k.ke)}/${angka(k.dari)})…`
})
const persenKemajuan = computed(() => {
  const k = job.value?.kemajuan
  if (!k || !k.dari) return 3
  if (job.value?.jenis === 'perbaiki') return k.tahap === 'perbaiki' ? 3 + (k.ke / k.dari) * 80 : k.tahap === 'inventaris' ? 85 : 88 + (k.ke / k.dari) * 12
  return k.tahap === 'inventaris' ? (k.ke / k.dari) * 40 + 3 : 43 + (k.ke / k.dari) * 57
})

// ---- Detail server terpilih ----
const detail = ref(null)
const memuatDetail = ref(false)
// Hasil scan per host disimpan selama tab terbuka (kunci = waktu scan): pindah server/tab/halaman tidak memuat ulang.
// Sesudah server terpilih tampil, hasil server lain diambil diam-diam satu per satu.
async function ambilHasil(s) {
  const c = cacheHasil.get(s.host)
  if (c && c.diambil === s.diambil) return c
  const d = await minta(`/api/servers/cms?server=${encodeURIComponent(s.host)}`)
  if (d.diambil) cacheHasil.set(s.host, d)
  return d
}
async function muatDetail() {
  const s = terpilih.value
  if (!s) return
  if (!s.diambil) { detail.value = { host: s.host, belum: true }; return }
  memuatDetail.value = true
  try {
    const d = await ambilHasil(s)
    if (d.host === terpilih.value?.host) detail.value = d
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    memuatDetail.value = false
  }
  for (const lain of servers.value) {
    if (lain.diambil && lain.host !== s.host) { try { await ambilHasil(lain) } catch { /* dicoba lagi saat dipilih */ } }
  }
}
watch(() => [terpilih.value?.host, terpilih.value?.diambil], () => {
  if (detail.value?.host !== terpilih.value?.host) detail.value = null
  muatDetail()
}, { immediate: true })
watch(pilih, () => { cari.value = ''; filter.value = 'rentan'; buka.value = new Set(); bukaKomp.value = '' })

const kamus = computed(() => detail.value?.kerentanan || {})
const terbaru = computed(() => detail.value?.wp_terbaru)
const lebihLama = (a, b) => {
  const pa = String(a || '').split('.').map(Number); const pb = String(b || '').split('.').map(Number)
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i] || 0; const y = pb[i] || 0
    if (x !== y) return x < y
  }
  return false
}
const intiUsang = (s) => terbaru.value && lebihLama(s.versi, terbaru.value)
const alamat = (s) => `${s.domain}${s.sub || ''}`

// Situs + ringkas keparahan
const situs = computed(() => (detail.value?.situs || []).map((s) => {
  const ids = s.temuan.flatMap((t) => t.id)
  const hitung = { kritis: 0, tinggi: 0, sedang: 0, rendah: 0, tidak_diketahui: 0 }
  for (const i of ids) hitung[kamus.value[i]?.tingkat || 'tidak_diketahui']++
  const terburuk = Object.keys(hitung).find((k) => hitung[k]) || null
  const skor = Math.max(0, ...ids.map((i) => kamus.value[i]?.skor || 0))
  return { ...s, ids, hitung, terburuk, skor, eksploit: ids.some((i) => kamus.value[i]?.dieksploitasi), ditutup: s.temuan.filter((t) => t.ditutup) }
}))
const cari = ref('')
const filter = ref('rentan')
const FILTER = computed(() => [
  { k: 'rentan', label: 'Rentan', n: situs.value.filter((s) => s.ids.length).length },
  { k: 'kritis', label: 'Kritis', n: situs.value.filter((s) => s.hitung.kritis).length },
  { k: 'tinggi', label: 'Tinggi', n: situs.value.filter((s) => s.hitung.tinggi).length },
  { k: 'usang', label: 'Inti WP usang', n: situs.value.filter(intiUsang).length },
  { k: 'ditutup', label: 'Plugin ditutup', n: situs.value.filter((s) => s.ditutup.length).length },
  { k: 'semua', label: 'Semua situs', n: situs.value.length },
])
const situsTersaring = computed(() => {
  const q = cari.value.trim().toLowerCase()
  const f = filter.value
  return situs.value
    .filter((s) => (f === 'semua' || (f === 'rentan' && s.ids.length) || (f === 'kritis' && s.hitung.kritis) || (f === 'tinggi' && s.hitung.tinggi)
      || (f === 'usang' && intiUsang(s)) || (f === 'ditutup' && s.ditutup.length)))
    .filter((s) => !q || alamat(s).toLowerCase().includes(q) || s.user.includes(q)
      || s.temuan.some((t) => t.slug.includes(q) || (t.nama || '').toLowerCase().includes(q)))
    .sort((a, b) => (TINGKAT[a.terburuk]?.urut ?? 9) - (TINGKAT[b.terburuk]?.urut ?? 9) || b.skor - a.skor || b.ids.length - a.ids.length || alamat(a).localeCompare(alamat(b)))
})
const tampil = ref(60)
watch([cari, filter], () => { tampil.value = 60 })
const buka = ref(new Set())
const semuaVuln = ref(new Set())
const urutVuln = (ids) => [...ids].sort((a, b) => tk(kamus.value[a]?.tingkat).urut - tk(kamus.value[b]?.tingkat).urut || (kamus.value[b]?.skor || 0) - (kamus.value[a]?.skor || 0))
const alihBuka = (p) => { const n = new Set(buka.value); n.has(p) ? n.delete(p) : n.add(p); buka.value = n }

// Komponen rentan digabung lintas situs (untuk update massal)
const komponen = computed(() => {
  const peta = new Map()
  for (const s of situs.value) {
    for (const t of s.temuan) {
      if (!t.id.length && !t.ditutup) continue
      const k = `${t.jenis}|${t.slug}|${t.versi}`
      if (!peta.has(k)) peta.set(k, { ...t, situs: [] })
      peta.get(k).situs.push(s)
    }
  }
  return [...peta.values()].map((k) => {
    const v = k.id.map((i) => kamus.value[i]).filter(Boolean)
    const terburuk = v.map((x) => x.tingkat).sort((a, b) => tk(a).urut - tk(b).urut)[0] || null
    return { ...k, v, terburuk, skor: Math.max(0, ...v.map((x) => x.skor || 0)), perbaiki: versiAman(v) }
  }).sort((a, b) => tk(a.terburuk).urut - tk(b.terburuk).urut || b.situs.length - a.situs.length)
})
const cariKomp = ref('')
const komponenTersaring = computed(() => {
  const q = cariKomp.value.trim().toLowerCase()
  return komponen.value.filter((k) => !q || k.slug.includes(q) || (k.nama || '').toLowerCase().includes(q))
})
const bukaKomp = ref('')
// Versi minimum yang menutup semua kerentanan yang diketahui (null bila ada yang belum diperbaiki/tak diketahui)
function versiAman(v) {
  if (!v.length || v.some((x) => x.belum_diperbaiki)) return null
  const angkaVersi = v.map((x) => x.perbaiki).filter((p) => p && !p.startsWith('>'))
  if (!angkaVersi.length) return null
  return angkaVersi.reduce((a, b) => (lebihLama(a, b) ? b : a))
}

// ---- Perbaiki kerentanan (mengubah situs klien) ----
// Plugin/tema rentan diperbarui ke rilis terbaru (kecuali yang ditutup di wordpress.org); inti WP hanya update minor
// di cabang yang sama. Backend menyaring ulang daftar ini dengan hasil scan tersimpan.
function rencanaSitus(s) {
  const r = { s, plugin: [], tema: [], core: null, lewat: [] }
  for (const t of s.temuan) {
    if (!t.id.length) continue
    if (t.jenis === 'core') { r.core = { dari: t.versi, cabang: t.versi.split('.').slice(0, 2).join('.'), rentan: true }; continue }
    const item = { slug: t.slug, nama: t.nama || t.slug, dari: t.versi, ke: versiAman(t.id.map((i) => kamus.value[i]).filter(Boolean)) }
    if (t.ditutup) r.lewat.push({ ...item, alasan: 'ditutup di wordpress.org — tidak disentuh, cek manual dulu (jangan langsung dihapus)' })
    else (t.jenis === 'plugin' ? r.plugin : r.tema).push(item)
  }
  if (!r.core && intiUsang(s)) r.core = { dari: s.versi, cabang: s.versi.split('.').slice(0, 2).join('.'), rentan: false }
  return r
}
const bisaDiperbaiki = (r) => r.plugin.length || r.tema.length || r.core?.rentan
// Situs/akun yang sedang dikerjakan job perbaikan berjalan (termasuk tahap scan ulang) → tombolnya jadi loading
const jobPerbaiki = computed(() => (berjalan.value && job.value?.jenis === 'perbaiki' && job.value.target === terpilih.value?.host ? job.value : null))
const sedangDiperbaiki = (s) => !!jobPerbaiki.value?.rencana?.some((r) => r.path === s.path)
const labelLoading = computed(() => (jobPerbaiki.value?.kemajuan?.tahap === 'perbaiki' ? 'Memperbaiki…' : 'Scan ulang…'))
const MAKS_PERBAIKI = 30
// inti: {path: 'lewati'|'minor'|'terbaru'} — bawaan minor bila inti rentan, lewati bila hanya usang
const perb = reactive({ buka: false, user: '', satu: false, daftar: [], cek: null, memeriksa: false, galatCek: '', blokir: '', pilih: new Set(), inti: {} })
// Kunci centang satu komponen; hanya yang dicentang ikut dikirim
const kunciKomp = (path, jenis, slug) => `${path}|${jenis}|${slug}`
const isiKomp = (r) => [...r.plugin.map((x) => ['plugin', x.slug]), ...r.tema.map((x) => ['theme', x.slug])]
const modeInti = (r) => (r.core ? perb.inti[r.s.path] || 'lewati' : 'lewati')
function alihPilih(k) { const n = new Set(perb.pilih); n.has(k) ? n.delete(k) : n.add(k); perb.pilih = n }
const situsAkun = (user) => situs.value.filter((s) => s.user === user && s.ids.length).map(rencanaSitus).filter(bisaDiperbaiki)
const dipilih = (r, j, sl) => perb.pilih.has(kunciKomp(r.s.path, j, sl))
const kirimanSitus = (semua = false) => perb.daftar.slice(0, MAKS_PERBAIKI)
  .map((r) => ({ path: r.s.path, plugin: r.plugin.map((x) => x.slug).filter((sl) => semua || dipilih(r, 'plugin', sl)),
    tema: r.tema.map((x) => x.slug).filter((sl) => semua || dipilih(r, 'theme', sl)),
    core: semua ? (r.core ? 'cek' : false) : (modeInti(r) === 'lewati' ? false : modeInti(r)) }))
  .filter((x) => x.plugin.length || x.tema.length || x.core)
// Dialog dibuka → pengaman diperiksa di server (hanya baca): PHP web vs syarat wordpress.org, sisa kuota, Kirki di tabel MyISAM
async function bukaPerbaiki(s, akun) {
  const daftar = akun ? situsAkun(s.user) : [rencanaSitus(s)].filter(bisaDiperbaiki)
  const pilih = new Set(daftar.flatMap((r) => isiKomp(r).map(([j, sl]) => kunciKomp(r.s.path, j, sl))))
  const inti = Object.fromEntries(daftar.filter((r) => r.core).map((r) => [r.s.path, r.core.rentan ? 'minor' : 'lewati']))
  Object.assign(perb, { buka: true, user: s.user, satu: !akun, daftar, cek: null, memeriksa: true, galatCek: '', blokir: '', pilih, inti })
  try {
    const r = await kirim('/api/servers/cms/perbaiki/cek', { server: terpilih.value.host, user: s.user, situs: kirimanSitus(true) })
    if (perb.user === s.user) {
      perb.cek = r
      // Yang ditolak pengaman tidak dicentang (dan tidak bisa dicentang)
      perb.pilih = new Set([...perb.pilih].filter((k) => { const [path, j, sl] = k.split('|'); return putusan(path, j, sl)?.ok !== false }))
      for (const [path, m] of Object.entries(perb.inti)) if (m !== 'lewati' && putusan(path, 'core', m)?.ok === false) perb.inti[path] = 'lewati'
    }
  } catch (e) {
    perb.galatCek = pesanGalat(e.message)
    // Akun tersuspend: agen pasti menolak → jangan biarkan ada yang tercentang
    if (e.message === 'akun_disuspend') { perb.blokir = perb.galatCek; perb.pilih = new Set(); perb.inti = {} }
  } finally {
    perb.memeriksa = false
  }
}
const cekSitus = (path) => perb.cek?.situs?.find((x) => x.path === path)
// Keputusan pengaman satu komponen: { ok, alasan } atau undefined (belum/gagal diperiksa)
// Plugin/tema yang hanya terhalang cabang WP ikut lolos bila inti situs itu dipilih 'terbaru'
const lolosTerbaru = (path, k) => !k.ok && k.wp_butuh && perb.inti[path] === 'terbaru' && terbaru.value && !lebihLama(terbaru.value, k.wp_butuh)
function putusan(path, jenis, slug) {
  const k = cekSitus(path)?.keputusan?.find((x) => x.jenis === jenis && x.slug.toLowerCase() === slug.toLowerCase())
  return k && lolosTerbaru(path, k) ? { ...k, ok: true } : k
}
// Ganti mode inti: komponen yang terbuka/tertutup karena syarat WP ikut dicentang/dilepas
function gantiInti(r, mode) {
  perb.inti[r.s.path] = mode
  const n = new Set(perb.pilih)
  for (const k of cekSitus(r.s.path)?.keputusan || []) {
    if (!k.wp_butuh || k.jenis === 'core') continue
    const kunci = kunciKomp(r.s.path, k.jenis, (k.jenis === 'plugin' ? r.plugin : r.tema).find((x) => x.slug.toLowerCase() === k.slug.toLowerCase())?.slug || k.slug)
    lolosTerbaru(r.s.path, k) ? n.add(kunci) : n.delete(kunci)
  }
  perb.pilih = n
}
const jumlahKomp = computed(() => perb.daftar.slice(0, MAKS_PERBAIKI).reduce((n, r) => n + isiKomp(r).filter(([j, sl]) => dipilih(r, j, sl)).length
  + (modeInti(r) !== 'lewati' ? 1 : 0), 0))
async function jalankanPerbaiki() {
  if (!oleh.value.trim()) { Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true }); perb.buka = false; return }
  proses.value = true
  try {
    await kirim('/api/servers/cms/perbaiki', {
      server: terpilih.value.host, user: perb.user, oleh: oleh.value.trim(),
      situs: kirimanSitus(),
    })
    perb.buka = false
    Object.assign(pesan, { teks: `Perbaikan akun ${perb.user} dimulai.`, galat: false })
    await cms.muatUlang()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
// Hasil job perbaikan terakhir (berjalan atau selesai) untuk server terpilih
const hasilPerbaiki = computed(() => (job.value?.jenis === 'perbaiki' && job.value.target === terpilih.value?.host ? job.value : null))
const statusKomp = { Updated: 'diperbarui', 'Up to date': 'sudah terbaru', Error: 'gagal' }

// ---- cPGuard pembanding ----
const cpg = computed(() => detail.value?.cpguard)
const cpgSitus = computed(() => {
  const kita = new Map(situs.value.map((s) => [s.path, s]))
  return (cpg.value?.situs || [])
    .filter((c) => String(c.rating || 'safe').toLowerCase() !== 'safe')
    .map((c) => ({ ...c, kita: kita.get(c.path) }))
    .sort((a, b) => (parseFloat(b.skor) || 0) - (parseFloat(a.skor) || 0))
})
const cpgKelas = (r) => ({ critical: 'merah', high: 'oranye', medium: 'kuning', low: 'abu' }[String(r || '').toLowerCase()] || 'abu')
const relatif = (p) => (p || '').replace(/^\/home\/[^/]+\/domains\//, '').replace(/\/public_html/, '')

const riwayatServer = computed(() => (riwayat.data.value?.riwayat || []))
const durasi = (j) => {
  const d = (j.selesai || Math.floor(Date.now() / 1000)) - j.mulai
  return d >= 60 ? `${Math.floor(d / 60)} mnt ${d % 60} dtk` : `${d} dtk`
}
</script>

<script>
const cacheHasil = new Map()
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Kerentanan CMS <span class="merek-guard">VelocityGuard</span></h1>
        <p class="redup">Versi WordPress, plugin, dan tema setiap situs klien dicocokkan dengan basis data kerentanan publik. Tombol <b>Perbaiki</b> memperbarui komponen rentan per situs/akun (dengan cadangan) lalu scan ulang akun itu.</p>
      </div>
      <div class="kepala-aksi">
        <div class="nama-saya"><span class="redup">Dicatat sebagai</span><PelakuAkun id="nama-cms" /></div>
        <button type="button" class="tombol kecil" :disabled="proses || berjalan || !servers.length" @click="mulaiScan('semua')"><Ikon nama="cari" :ukuran="16" /> Scan semua server</button>
      </div>
    </header>

    <p v-if="cms.memuat.value && !cms.data.value" class="redup" role="status">Memuat…</p>
    <p v-else-if="cms.galat.value && !cms.data.value" class="pesan-status bahaya">Gagal memuat: {{ cms.galat.value.message }}</p>

    <template v-else-if="cms.data.value">
      <div v-if="berjalan" class="kemajuan kartu" role="status">
        <span class="putar besar" aria-hidden="true" />
        <div>
          <b v-if="job.jenis === 'perbaiki'">Perbaiki akun {{ job.user }} · {{ job.server.join(', ') }}</b>
          <b v-else>Scan CMS {{ job.target === 'semua' ? 'semua server' : job.server.join(', ') }}</b>
          <span class="redup"> · {{ job.oleh }} · {{ durasi(job) }}</span>
          <div class="redup kecil-teks">{{ labelKemajuan }}</div>
          <div class="garis-jalan"><span :style="{ width: `${persenKemajuan}%` }" /></div>
        </div>
      </div>

      <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>

      <section v-if="hasilPerbaiki?.situs?.length" class="kartu hasil-perb" aria-label="Hasil perbaikan">
        <div class="kartu-judul"><h2><Ikon nama="perisai" :ukuran="16" /> Hasil perbaikan akun {{ hasilPerbaiki.user }}
          <small class="redup">{{ hasilPerbaiki.oleh }} · {{ tanggalWaktu(hasilPerbaiki.mulai) }}</small></h2></div>
        <div v-for="h in hasilPerbaiki.situs" :key="h.path" class="perb-situs">
          <div class="rinci-kepala">
            <span class="titik" :class="h.ok ? 'baik' : 'bahaya'" aria-hidden="true" />
            <b>{{ relatif(h.path) || h.domain }}</b>
            <span v-if="h.error" class="lencana merah">{{ pesanGalat(h.error) }}</span>
            <span v-if="h.dikembalikan" class="lencana merah">BERANDA ERROR → PLUGIN/TEMA DIKEMBALIKAN</span>
            <small class="redup">beranda {{ h.http_sebelum ?? '-' }} → {{ h.http_sesudah ?? '-' }}<template v-if="h.http_akhir"> → {{ h.http_akhir }}</template></small>
          </div>
          <ul class="daftar-vuln">
            <li v-for="(l, i) in h.langkah || []" :key="i">
              <span class="lencana" :class="l.ok ? 'hijau' : 'merah'">{{ l.langkah }}</span>
              <template v-if="l.komponen?.length"><span v-for="k in l.komponen" :key="k.slug" class="komp">{{ k.slug }} <span class="redup">{{ k.dari }} → {{ k.ke }} · {{ statusKomp[k.status] || k.status }}</span></span></template>
              <small v-else class="redup">{{ l.pesan }}</small>
            </li>
          </ul>
          <ul v-if="h.cek?.keputusan?.some((k) => !k.ok)" class="daftar-vuln">
            <li v-for="k in h.cek.keputusan.filter((x) => !x.ok)" :key="k.jenis + k.slug" class="redup"><span class="lencana kuning">dilewati</span> {{ k.slug }} — {{ k.alasan }}</li>
          </ul>
          <small v-if="h.kosong" class="redup blok">Semua komponen dilewati pengaman — situs tidak diubah.</small>
          <small v-if="h.inti_dikembalikan" class="merah-teks blok">Inti WordPress dikembalikan ke versi sebelumnya (berkas); database tetap versi baru.</small>
          <small v-if="h.css_dipulihkan" class="hijau-teks blok">CSS Kirki ({{ h.css_dipulihkan.join(', ') }}) hilang sesudah update tema → dipulihkan ke CSS Tambahan.</small>
          <small v-if="h.cadangan" class="redup">Cadangan: <code>{{ h.cadangan }}</code></small>
          <small v-if="h.pesan" class="merah-teks blok">{{ h.pesan }}</small>
        </div>
      </section>

      <PilihServer v-if="terpilih" :servers="servers" :model-value="terpilih?.name" :titik="tingkatServer(terpilih)" :teks="(s) => s.name + (s.ringkas?.rentan ? ` · ${s.ringkas.rentan} rentan` : '')" @update:model-value="pilih = $event" />

      <!-- Ringkasan server terpilih (sesudah pernah di-scan) -->
      <div v-if="terpilih?.ringkas" class="ringkas">
        <div class="kartu tile">
          <span class="tile-ikon biru"><Ikon nama="cms" :ukuran="20" /></span>
          <div><span class="redup">Situs WordPress</span><b>{{ angka(terpilih.ringkas.situs) }}</b><small class="redup">scan {{ waktuLalu(terpilih.diambil) }}</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon merah"><Ikon nama="peringatan" :ukuran="20" /></span>
          <div><span class="redup">Situs rentan</span><b>{{ angka(terpilih.ringkas.rentan) }}</b><small class="redup">{{ angka(terpilih.ringkas.kritis) }} kritis · {{ angka(terpilih.ringkas.tinggi) }} tinggi</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon kuning"><Ikon nama="ulang" :ukuran="20" /></span>
          <div><span class="redup">Inti WP belum terbaru</span><b>{{ angka(terpilih.ringkas.inti_usang) }}</b><small class="redup">terbaru {{ terpilih.wp_terbaru || '-' }}</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon ungu"><Ikon nama="perisai" :ukuran="20" /></span>
          <div><span class="redup">Rentan menurut cPGuard</span><b>{{ angka(terpilih.ringkas.cpg_rentan) }}</b><small class="redup">pembanding</small></div>
        </div>
      </div>

      <section v-if="terpilih" class="kartu" aria-labelledby="judul-cms">
        <div class="kartu-judul">
          <h2 id="judul-cms"><Ikon nama="cms" :ukuran="16" /> {{ terpilih.name }}
            <small v-if="terpilih.diambil" class="redup">{{ angka(terpilih.ringkas?.situs) }} situs · scan {{ waktuLalu(terpilih.diambil) }} oleh {{ terpilih.oleh }}</small>
          </h2>
          <div class="judul-kanan">
            <div v-if="terpilih.diambil" class="tab" role="tablist" aria-label="Bagian CMS">
              <button v-for="t in [
                { k: 'situs', label: 'Situs', n: terpilih.ringkas?.rentan },
                { k: 'komponen', label: 'Komponen rentan', n: komponen.length },
                { k: 'cpguard', label: 'cPGuard', n: terpilih.ringkas?.cpg_rentan },
                { k: 'riwayat', label: 'Riwayat scan' },
              ]" :key="t.k" type="button" role="tab" :aria-selected="tab === t.k" :class="{ aktif: tab === t.k }" @click="tab = t.k">
                {{ t.label }} <span v-if="t.n !== undefined" class="hitung">{{ t.n }}</span>
              </button>
            </div>
            <button type="button" class="tombol garis kecil" :disabled="proses || berjalan" @click="mulaiScan(terpilih.host)"><Ikon nama="ulang" :ukuran="15" /> Scan server ini</button>
          </div>
        </div>
        <label class="cek-jadwal"><input type="checkbox" :checked="!!jadwal.harian" :disabled="proses" @change="aturJadwal($event.target.checked)">
          Scan otomatis harian {{ cms.data.value?.jam_jadwal }} <small class="redup">kerentanan kritis/tinggi baru dikirim ke Telegram tim server<template v-if="jadwal.terakhir"> · terakhir {{ jadwal.terakhir }}</template></small></label>

        <div v-if="!terpilih.diambil" class="kosong">
          <p><b>Server ini belum pernah di-scan.</b></p>
          <p class="redup">Tekan <b>Scan server ini</b> untuk membaca semua instalasi WordPress (hanya baca, prioritas rendah) lalu mencocokkannya dengan basis data kerentanan.</p>
        </div>
        <p v-else-if="!detail && memuatDetail" class="redup" role="status">Memuat hasil scan…</p>

        <template v-else-if="detail && !detail.belum">
          <p v-if="detail.terpotong" class="pesan-status bahaya">Daftar terpotong di 3.000 instalasi.</p>

          <!-- ================= Situs ================= -->
          <template v-if="tab === 'situs'">
            <div class="alat">
              <input v-model="cari" type="search" placeholder="Cari domain / akun / plugin" aria-label="Cari situs">
              <div class="chip-filter" role="group" aria-label="Saring situs">
                <button v-for="f in FILTER" :key="f.k" type="button" :class="{ aktif: filter === f.k }" @click="filter = f.k">{{ f.label }} {{ f.n }}</button>
              </div>
            </div>
            <p v-if="!situsTersaring.length" class="bersih"><Ikon nama="centang" :ukuran="18" /> {{ filter === 'semua' ? 'Tidak ada situs WordPress.' : 'Tidak ada situs di saringan ini.' }}</p>
            <div v-else class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">Situs</th><th scope="col">WordPress</th><th scope="col">Kerentanan</th><th scope="col">Komponen rentan</th><th scope="col"><span class="sr">Rincian</span></th></tr></thead>
                <tbody>
                  <template v-for="s in situsTersaring.slice(0, tampil)" :key="s.path">
                    <tr :class="{ dibuka: buka.has(s.path) }">
                      <td class="situs-sel">
                        <a :href="`https://${alamat(s)}`" target="_blank" rel="noopener noreferrer">{{ alamat(s) }}</a>
                        <small class="redup blok">{{ s.user }} · {{ s.plugin.length }} plugin · {{ s.tema.length }} tema</small>
                      </td>
                      <td class="nowrap">
                        {{ s.versi }}
                        <span v-if="intiUsang(s)" class="lencana kuning" :title="`Versi terbaru ${terbaru}`">USANG</span>
                      </td>
                      <td class="sel-lencana">
                        <template v-if="s.ids.length">
                          <span v-for="(n, t) in s.hitung" v-show="n" :key="t" class="lencana" :class="tk(t).kelas">{{ n }} {{ tk(t).label }}</span>
                          <span v-if="s.eksploit" class="lencana merah" title="Sudah dieksploitasi di dunia nyata (KEV / SSVC)">DIEKSPLOITASI</span>
                        </template>
                        <span v-else class="hijau-teks">Aman</span>
                      </td>
                      <td class="ket">
                        <span v-for="t in s.temuan.filter((x) => x.id.length || x.ditutup).slice(0, 4)" :key="t.jenis + t.slug" class="komp">{{ t.jenis === 'core' ? 'WordPress' : t.slug }} <span class="redup">{{ t.versi }}</span></span>
                        <span v-if="s.temuan.filter((x) => x.id.length || x.ditutup).length > 4" class="redup">+{{ s.temuan.filter((x) => x.id.length || x.ditutup).length - 4 }}</span>
                      </td>
                      <td class="kanan">
                        <button v-if="sedangDiperbaiki(s)" type="button" class="tombol kecil" disabled aria-busy="true"><span class="putar" aria-hidden="true" /> {{ labelLoading }}</button>
                        <button v-else-if="bisaDiperbaiki(rencanaSitus(s))" type="button" class="tombol kecil" :disabled="proses || berjalan" @click="bukaPerbaiki(s, false)"><Ikon nama="perisai" :ukuran="14" /> Perbaiki</button>
                        <button v-if="s.temuan.length" type="button" class="tombol garis kecil" :aria-expanded="buka.has(s.path)" @click="alihBuka(s.path)">{{ buka.has(s.path) ? 'Tutup' : 'Rincian' }}</button>
                      </td>
                    </tr>
                    <tr v-if="buka.has(s.path)" class="baris-rinci">
                      <td colspan="5">
                        <div class="rinci-isi">
                        <p class="redup kecil-teks"><code>{{ s.path }}</code><template v-if="s.mu_plugin.length"> · mu-plugins: {{ s.mu_plugin.join(', ') }}</template></p>
                        <button v-if="jobPerbaiki?.user === s.user" type="button" class="tombol garis kecil" disabled aria-busy="true"><span class="putar" aria-hidden="true" /> {{ labelLoading }} akun {{ s.user }}</button>
                        <button v-else-if="situsAkun(s.user).length > 1" type="button" class="tombol garis kecil" :disabled="proses || berjalan" @click="bukaPerbaiki(s, true)"><Ikon nama="perisai" :ukuran="14" /> Perbaiki semua situs akun {{ s.user }} ({{ situsAkun(s.user).length }})</button>
                        <div v-for="t in s.temuan" :key="t.jenis + t.slug" class="rinci-komp">
                          <div class="rinci-kepala">
                            <span class="lencana abu">{{ JENIS[t.jenis] }}</span>
                            <b>{{ t.nama || t.slug }}</b> <span class="redup">{{ t.slug }} · versi {{ t.versi || '?' }}</span>
                            <span v-if="t.ditutup" class="lencana merah" :title="t.alasan_tutup || ''">DITUTUP DI WORDPRESS.ORG{{ t.alasan_tutup ? ` · ${t.alasan_tutup}` : '' }}</span>
                            <span v-if="t.jenis !== 'core' && versiAman(t.id.map((i) => kamus[i]).filter(Boolean))" class="hijau-teks kecil-teks">perbarui ke ≥ {{ versiAman(t.id.map((i) => kamus[i]).filter(Boolean)) }}</span>
                            <span v-else-if="t.jenis === 'core' && terbaru" class="hijau-teks kecil-teks">perbarui ke {{ terbaru }}</span>
                          </div>
                          <ul class="daftar-vuln">
                            <li v-for="i in urutVuln(t.id).slice(0, semuaVuln.has(s.path + t.slug) ? undefined : 5)" :key="i">
                              <span class="lencana" :class="tk(kamus[i]?.tingkat).kelas">{{ kamus[i]?.skor ?? '–' }} {{ tk(kamus[i]?.tingkat).label }}</span>
                              <a v-if="kamus[i]?.link" :href="kamus[i].link" target="_blank" rel="noopener noreferrer">{{ kamus[i]?.judul }}</a><span v-else>{{ kamus[i]?.judul }}</span>
                              <small class="redup"> {{ kamus[i]?.cve.join(', ') }}<template v-if="kamus[i]?.perbaiki"> · diperbaiki {{ kamus[i].perbaiki }}</template><template v-if="kamus[i]?.belum_diperbaiki"> · <b class="merah-teks">belum ada perbaikan</b></template></small>
                            </li>
                          </ul>
                          <button v-if="t.id.length > 5 && !semuaVuln.has(s.path + t.slug)" type="button" class="tombol garis kecil lagi" @click="semuaVuln = new Set([...semuaVuln, s.path + t.slug])">Tampilkan semua {{ t.id.length }} kerentanan</button>
                        </div>
                        </div>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
            <button v-if="situsTersaring.length > tampil" type="button" class="tombol garis kecil lagi" @click="tampil += 200">Tampilkan lebih banyak ({{ situsTersaring.length - tampil }} lagi)</button>
          </template>

          <!-- ================= Komponen ================= -->
          <template v-else-if="tab === 'komponen'">
            <p class="redup kecil-teks">Plugin/tema/versi inti yang sama digabung — berguna untuk memperbarui satu plugin di banyak situs sekaligus.</p>
            <div class="alat"><input v-model="cariKomp" type="search" placeholder="Cari plugin / tema" aria-label="Cari komponen"></div>
            <p v-if="!komponenTersaring.length" class="bersih"><Ikon nama="centang" :ukuran="18" /> Tidak ada komponen rentan.</p>
            <div v-else class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">Komponen</th><th scope="col">Versi</th><th scope="col">Terburuk</th><th scope="col">Perbarui ke</th><th scope="col">Situs</th></tr></thead>
                <tbody>
                  <template v-for="k in komponenTersaring" :key="k.jenis + k.slug + k.versi">
                    <tr>
                      <td class="ket"><span class="lencana abu">{{ JENIS[k.jenis] }}</span> <b>{{ k.jenis === 'core' ? 'WordPress' : (k.nama || k.slug) }}</b>
                        <small class="redup blok">{{ k.slug }} · {{ k.v.length }} kerentanan<template v-if="k.ditutup"> · <b class="merah-teks">ditutup di wordpress.org</b></template></small></td>
                      <td class="nowrap">{{ k.versi || '?' }}</td>
                      <td class="nowrap"><span v-if="k.terburuk" class="lencana" :class="tk(k.terburuk).kelas">{{ k.skor || '–' }} {{ tk(k.terburuk).label }}</span></td>
                      <td class="nowrap">{{ k.jenis === 'core' ? terbaru : (k.perbaiki || (k.v.some((x) => x.belum_diperbaiki) ? 'belum ada' : '-')) }}</td>
                      <td class="nowrap"><button type="button" class="tombol garis kecil" :aria-expanded="bukaKomp === k.jenis + k.slug + k.versi" @click="bukaKomp = bukaKomp === k.jenis + k.slug + k.versi ? '' : k.jenis + k.slug + k.versi">{{ k.situs.length }} situs</button></td>
                    </tr>
                    <tr v-if="bukaKomp === k.jenis + k.slug + k.versi" class="baris-rinci">
                      <td colspan="5"><span v-for="s in k.situs" :key="s.path" class="komp">{{ alamat(s) }} <span class="redup">{{ s.user }}</span></span></td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </template>

          <!-- ================= cPGuard ================= -->
          <template v-else-if="tab === 'cpguard'">
            <p class="redup kecil-teks">"CMS Threat" cPGuard dari <code>cms.db</code> saat scan terakhir — pembanding selama cPGuard masih jalan ({{ detail.cpguard_jalan ? 'jalan' : 'TIDAK jalan' }}).
              <Info label="Tentang pembanding cPGuard" rata="kanan"><p>cPGuard memperbarui datanya tiap malam ±02:00 dan menyimpan isu komponen yang sudah tidak terpasang; yang ditampilkan hanya komponen yang masih terpasang. Selisih wajar terjadi karena basis data kerentanannya berbeda.</p></Info>
            </p>
            <p v-if="!cpg" class="redup">cPGuard tidak terpasang di server ini.</p>
            <p v-else-if="cpg.error" class="pesan-status bahaya">cms.db tidak terbaca: {{ cpg.error }}</p>
            <p v-else-if="!cpgSitus.length" class="bersih"><Ikon nama="centang" :ukuran="18" /> cPGuard tidak menandai situs mana pun.</p>
            <div v-else class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">Situs</th><th scope="col">cPGuard</th><th scope="col">Isu cPGuard</th><th scope="col">Scan Velocity</th></tr></thead>
                <tbody>
                  <tr v-for="c in cpgSitus" :key="c.path">
                    <td class="situs-sel"><code>{{ relatif(c.path) }}</code><small class="redup blok">WP {{ c.versi || '?' }} · {{ c.waktu }}<template v-if="c.galat"> · <span class="kuning-teks">ada galat refresh</span></template></small></td>
                    <td class="nowrap"><span class="lencana" :class="cpgKelas(c.rating)">{{ c.skor }} {{ c.rating }}</span></td>
                    <td class="ket">
                      <span v-for="(x, i) in c.isu.slice(0, 4)" :key="i" class="blok">{{ x.slug || 'inti' }} <span class="redup">{{ x.versi }}</span> — {{ x.judul }}<template v-if="x.patch"> <span class="hijau-teks">→ {{ x.patch }}</span></template></span>
                      <span v-if="c.isu.length > 4" class="redup">+{{ c.isu.length - 4 }} lainnya</span>
                    </td>
                    <td class="nowrap">
                      <span v-if="!c.kita" class="redup">tidak ditemukan</span>
                      <span v-else-if="c.kita.ids.length" class="lencana" :class="tk(c.kita.terburuk).kelas">{{ c.kita.ids.length }} temuan</span>
                      <span v-else class="hijau-teks">Aman</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>

          <!-- ================= Riwayat ================= -->
          <template v-else-if="tab === 'riwayat'">
            <p v-if="!riwayatServer.length" class="redup">Belum ada riwayat scan.</p>
            <ul v-else class="kejadian">
              <li v-for="r in riwayatServer" :key="r.id">
                <span class="titik" :class="r.status === 'selesai' ? 'baik' : 'bahaya'" aria-hidden="true" />
                <div>
                  <b>{{ r.jenis === 'perbaiki' ? `Perbaiki akun ${r.user} · ` : '' }}{{ r.target === 'semua' ? 'Semua server' : (r.hasil?.[0]?.server || r.target) }}</b>
                  <span v-if="r.jenis === 'perbaiki' && r.situs" class="redup kecil-teks"> {{ r.situs.filter((h) => h.ok).length }}/{{ r.situs.length }} situs berhasil<template v-if="r.akun"> · sisa rentan {{ r.akun.rentan }}/{{ r.akun.situs }}</template></span>
                  <span v-if="r.status !== 'selesai'" class="lencana merah">GAGAL · {{ r.error }}</span>
                  <small class="redup blok">{{ r.oleh }} · {{ durasi(r) }}<template v-for="h in r.hasil || []" :key="h.host"> · {{ h.server }}: {{ h.ok ? `${h.rentan}/${h.situs} rentan` : `gagal (${pesanGalat(h.error)})` }}</template></small>
                </div>
                <time class="redup">{{ tanggalWaktu(r.mulai) }}</time>
              </li>
            </ul>
          </template>

          <p class="redup kaki">Sumber: <a :href="cms.data.value.sumber" target="_blank" rel="noopener noreferrer">wpvulnerability.net</a> (CVE, Wordfence, WPScan, Patchstack), cache 24 jam.
            Plugin/tema premium atau buatan sendiri yang tidak ada di wordpress.org bisa tidak terdeteksi.</p>
        </template>
      </section>
    </template>

    <Dialog :buka="perb.buka" :judul="perb.satu ? `Perbaiki ${perb.daftar[0] ? alamat(perb.daftar[0].s) : ''}` : `Perbaiki akun ${perb.user}`" lebar="680px" @tutup="perb.buka = false">
      <p class="kecil-teks">Yang akan dikerjakan di <b>{{ terpilih?.name }}</b> ({{ perb.daftar.length }} situs, {{ jumlahKomp }} komponen dicentang):</p>
      <ol class="kecil-teks langkah-perb">
        <li>Pengaman: komponen dilewati bila butuh PHP/WordPress lebih tinggi dari PHP web situs, kuota akun tak cukup, atau Kirki di tabel MyISAM.</li>
        <li>Cadangan database + folder plugin/tema terkait ke <code>/root/velocity-cadangan/&lt;domain&gt;/cms-perbaiki-*</code> (gagal → situs dilewati).</li>
        <li>Update lewat WP-CLI sebagai pemilik akun: plugin/tema ke rilis terbaru, inti WP hanya update minor di cabangnya.</li>
        <li>Beranda dicek sebelum & sesudah; bila jadi error 5xx, plugin/tema dikembalikan dari cadangan. CSS Kirki yang hilang sesudah update tema dipulihkan ke CSS Tambahan.</li>
        <li>Scan ulang akun <b>{{ perb.user }}</b> agar status di halaman ini terbaru.</li>
      </ol>
      <p v-if="perb.memeriksa" class="redup kecil-teks" role="status"><span class="putar" aria-hidden="true" /> Memeriksa PHP web, kuota, dan tabel database di server…</p>
      <p v-else-if="perb.blokir" class="pesan-status bahaya" role="alert"><b>{{ perb.blokir }}</b> Aktifkan akun di DirectAdmin dulu bila memang perlu diperbaiki.</p>
      <p v-else-if="perb.galatCek" class="pesan-status bahaya">Pemeriksaan awal gagal ({{ perb.galatCek }}). Pengaman tetap dijalankan ulang saat perbaikan.</p>
      <p v-else-if="perb.cek?.kuota?.batas" class="kecil-teks">Kuota akun: <b>{{ angka(perb.cek.kuota.pakai) }} / {{ angka(perb.cek.kuota.batas) }} MB</b> <span class="redup">(kebutuhan per komponen = perkiraan)</span></p>
      <p v-if="perb.daftar.length > MAKS_PERBAIKI" class="pesan-status bahaya">Maksimal {{ MAKS_PERBAIKI }} situs sekali jalan — {{ perb.daftar.length - MAKS_PERBAIKI }} situs terakhir tidak ikut.</p>
      <div class="daftar-perb">
        <div v-for="r in perb.daftar.slice(0, MAKS_PERBAIKI)" :key="r.s.path" class="perb-situs">
          <b>{{ alamat(r.s) }}</b>
          <small v-if="cekSitus(r.s.path)" class="redup blok">PHP web {{ cekSitus(r.s.path).php || 'tak diketahui' }}<template v-if="cekSitus(r.s.path).php_sumber"> ({{ cekSitus(r.s.path).php_sumber }})</template> · beranda {{ cekSitus(r.s.path).http || 'tak terjangkau' }}<template v-if="r.tema.length && cekSitus(r.s.path).kirki_css"> · CSS Kirki dipulihkan bila hilang sesudah update tema</template></small>
          <small v-if="cekSitus(r.s.path)?.error" class="merah-teks blok">{{ pesanGalat(cekSitus(r.s.path).error) }}</small>
          <ul class="kecil-teks">
            <li v-if="r.core" :class="{ lewat: modeInti(r) === 'lewati' }">
              <span class="pilih-inti"><span class="lencana abu">Inti WP</span> {{ r.core.dari }}<template v-if="!r.core.rentan"> <span class="redup">(tidak rentan, usang)</span></template> →
                <select :value="modeInti(r)" :disabled="!!perb.blokir || perb.memeriksa" :aria-label="`Update inti WordPress ${alamat(r.s)}`" @change="gantiInti(r, $event.target.value)">
                  <option value="lewati">Lewati</option>
                  <option value="minor" :disabled="!r.core.rentan || putusan(r.s.path, 'core', 'minor')?.ok === false">Minor {{ r.core.cabang }}.x (aman)</option>
                  <option value="terbaru" :disabled="putusan(r.s.path, 'core', 'terbaru')?.ok === false">Terbaru {{ terbaru }}</option>
                </select></span>
              <span v-for="m in ['minor', 'terbaru']" v-show="putusan(r.s.path, 'core', m)?.ok === false" :key="m" class="kuning-teks blok">{{ m === 'minor' ? 'Minor' : 'Terbaru' }} tidak bisa: {{ putusan(r.s.path, 'core', m)?.alasan }}</span>
              <small v-if="modeInti(r) === 'terbaru'" class="redup blok">Berkas inti dicadangkan & dikembalikan bila beranda error. Tema/plugin lama bisa berubah tampilan tanpa error — cek situsnya sesudah selesai.</small></li>
            <li v-for="x in [...r.plugin.map((y) => ({ ...y, j: 'plugin' })), ...r.tema.map((y) => ({ ...y, j: 'theme' }))]" :key="x.j + x.slug" :class="{ lewat: putusan(r.s.path, x.j, x.slug)?.ok === false }"><label class="pilih-komp">
              <input type="checkbox" :checked="dipilih(r, x.j, x.slug)" :disabled="!!perb.blokir || putusan(r.s.path, x.j, x.slug)?.ok === false" @change="alihPilih(kunciKomp(r.s.path, x.j, x.slug))">
              <span><span class="lencana abu">{{ x.j === 'plugin' ? 'Plugin' : 'Tema' }}</span> {{ x.nama }} <span class="redup">{{ x.dari }} → {{ x.ke ? `terbaru (≥ ${x.ke})` : 'terbaru' }}</span>
              <span v-if="putusan(r.s.path, x.j, x.slug)?.ok === false" class="kuning-teks">— dilewati: {{ putusan(r.s.path, x.j, x.slug).alasan }}</span></span></label></li>
            <li v-for="x in r.lewat" :key="'l' + x.slug" class="redup"><s>{{ x.nama }} {{ x.dari }}</s> — dilewati: {{ x.alasan }}</li>
          </ul>
        </div>
      </div>
      <p class="redup kecil-teks">Plugin premium tanpa sumber update atau situs yang kuotanya penuh bisa gagal; hasil per situs tampil sesudah selesai.</p>
      <div class="aksi-dialog">
        <button type="button" class="tombol garis" @click="perb.buka = false">Batal</button>
        <button type="button" class="tombol bahaya" :disabled="proses || berjalan || perb.memeriksa || !jumlahKomp" @click="jalankanPerbaiki">Jalankan perbaikan</button>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
.cek-jadwal { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; margin: 0 0 12px; font-size: 13.5px; cursor: pointer; }
.cek-jadwal small { font-size: 12px; }
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.kepala-aksi { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.nama-saya { display: grid; gap: 4px; font-size: 12px; }

.ringkas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.tile { display: flex; gap: 14px; align-items: center; }
.tile > div { display: grid; gap: 3px; min-width: 0; }
.tile b { font-size: 24px; color: var(--teks-kuat); }
.tile small { font-size: 12px; }
.tile-ikon { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; }
.tile-ikon.merah { color: var(--bahaya); background: color-mix(in srgb, var(--bahaya) 15%, transparent); }
.tile-ikon.kuning { color: var(--waspada); background: color-mix(in srgb, var(--waspada) 15%, transparent); }
.tile-ikon.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 15%, transparent); }
.tile-ikon.biru { color: var(--aksen-terang); background: var(--aksen-lembut); }
.kartu-judul { flex-wrap: wrap; gap: 10px; }
.kartu-judul h2 { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.kartu-judul h2 small { font-size: 12.5px; font-weight: 400; }
.judul-kanan { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.hitung-menu { font-size: 11.5px; padding: 1px 7px; border-radius: 999px; background: color-mix(in srgb, var(--bahaya) 18%, transparent); color: var(--bahaya); }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); vertical-align: 1px; }
.titik.baik { background: var(--baik); }
.titik.waspada { background: var(--waspada); }
.titik.bahaya { background: var(--bahaya); }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
.lencana.oranye { color: #e0782f; background: color-mix(in srgb, #e0782f 15%, transparent); }
.lencana + .lencana { margin-left: 4px; }
.sel-lencana { max-width: 250px; line-height: 1.9; }
.sel-lencana .lencana { white-space: nowrap; }
.kosong { padding: 18px 4px; }
.kosong p { margin: 0 0 6px; }
.kemajuan { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 14px; align-items: center; font-size: 13.5px; }
.garis-jalan { height: 6px; border-radius: 3px; background: var(--garis); overflow: hidden; margin-top: 8px; }
.garis-jalan span { display: block; height: 100%; background: var(--aksen); border-radius: 3px; transition: width .4s; }
.putar { display: inline-block; width: 12px; height: 12px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: putar .8s linear infinite; }
.putar.besar { width: 22px; height: 22px; color: var(--aksen-terang); }
@keyframes putar { to { transform: rotate(360deg); } }
.alat { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; font-size: 13px; }
.alat input[type="search"] { flex: 1 1 220px; min-width: 0; }
.chip-filter { display: flex; gap: 4px; flex-wrap: wrap; }
.chip-filter button { border: 1px solid var(--garis); background: transparent; color: var(--teks-2); font: inherit; font-size: 12.5px; font-weight: 600; padding: 5px 10px; border-radius: 999px; cursor: pointer; }
.chip-filter button.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); color: var(--aksen-terang); }
.bersih { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--baik); font-weight: 600; }
.situs-sel { min-width: 220px; overflow-wrap: anywhere; }
.situs-sel a { color: var(--teks-kuat); font-weight: 600; text-decoration: none; }
.situs-sel a:hover { text-decoration: underline; }
.ket { font-size: 13px; color: var(--teks-2); overflow-wrap: anywhere; min-width: 180px; }
.komp { display: inline-block; margin: 0 8px 3px 0; font-size: 12.5px; }
.blok { display: block; }
.nowrap { white-space: nowrap; }
.kanan { text-align: right; white-space: nowrap; }
tr.dibuka td { border-bottom-color: transparent; }
.baris-rinci td { background: var(--kartu-2); padding: 12px 14px; }
.rinci-komp { padding: 8px 0; border-top: 1px solid var(--garis); }
.rinci-komp:first-of-type { border-top: 0; }
.rinci-kepala { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 13.5px; }
.daftar-vuln { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 5px; font-size: 13px; }
.daftar-vuln li { overflow-wrap: anywhere; }
.daftar-vuln .lencana { margin-right: 6px; }
.daftar-vuln small { margin-left: 4px; }
.daftar-vuln a { color: var(--teks); }
.kecil-teks { font-size: 12.5px; }
.merah-teks { color: var(--bahaya); }
.kuning-teks { color: var(--waspada); }
.hijau-teks { color: var(--baik); }
.lagi { margin-top: 10px; }
.kaki { margin: 16px 0 0; font-size: 12.5px; }
.kaki a { color: inherit; }
.kejadian { list-style: none; margin: 0; padding: 0; display: grid; }
.kejadian li { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 2px; border-bottom: 1px solid var(--garis); font-size: 13.5px; }
.kejadian li:last-child { border-bottom: 0; }
.kejadian li > div { overflow-wrap: anywhere; }
.kejadian time { font-size: 12.5px; white-space: nowrap; }
.tabel-wadah { position: relative; overflow-x: auto; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); overflow-wrap: anywhere; }
.langkah-perb { margin: 6px 0 12px; padding-left: 20px; display: grid; gap: 4px; }
.daftar-perb { max-height: 46vh; overflow-y: auto; border: 1px solid var(--garis); border-radius: 10px; padding: 4px 12px; }
.perb-situs { padding: 8px 0; border-top: 1px solid var(--garis); font-size: 13.5px; overflow-wrap: anywhere; }
.perb-situs:first-child { border-top: 0; }
.perb-situs ul { margin: 4px 0 0; padding: 0; list-style: none; display: grid; gap: 3px; }
.perb-situs li.lewat > .lencana, .perb-situs li.lewat > .redup { opacity: .55; }
.perb-situs li .kuning-teks { margin-left: 4px; }
.tombol[aria-busy="true"] { opacity: .85; }
.pilih-inti { display: inline-flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.pilih-inti select { font: inherit; font-size: 12.5px; padding: 3px 6px; }
.pilih-komp { display: flex; gap: 8px; align-items: baseline; cursor: pointer; }
.pilih-komp input { flex: none; }
li.lewat .pilih-komp { cursor: default; }
.aksi-dialog { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
.kanan .tombol + .tombol { margin-left: 6px; }
@media (prefers-reduced-motion: reduce) { .putar { animation: none; } .garis-jalan span { transition: none; } }
@media (max-width: 900px) { .ringkas { grid-template-columns: 1fr 1fr; } }
@media (max-width: 560px) {
  .ringkas { grid-template-columns: 1fr; }
  .nama-saya { width: 100%; }
  .kepala-aksi { width: 100%; }
  .kejadian li { grid-template-columns: 8px minmax(0, 1fr); }
  .kejadian time { grid-column: 2; }
  .situs-sel, .ket { min-width: 0; }
  .tabel { min-width: 620px; }
  /* Rincian tetap selebar layar walau tabel digulir menyamping */
  .rinci-isi { position: sticky; left: 14px; width: calc(100vw - 92px); }
}
</style>
