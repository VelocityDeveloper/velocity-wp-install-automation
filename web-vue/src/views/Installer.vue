<script setup>
// Website Installer: antrean domain dari Drive "On Progress" + CRM, install lewat wizard
// (manifest → mode → konfirmasi), log live & bagan alur per domain. API sama dengan dashboard lama.
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { RouterLink } from 'vue-router'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import MenuAksi from '../components/MenuAksi.vue'
import BaganAlur from '../components/BaganAlur.vue'
import { kirim } from '../api.js'
import { konfirmasi } from '../konfirmasi.js'

const UKURAN_HALAMAN = 25
const data = ref(null)
const galat = ref('')
const cari = ref('')
const status = ref('')
const deadline = ref('semua')
const halaman = ref(1)
const catatan = ref({ teks: '', jenis: '' })
const detail = ref(null)
const menu = ref(null)

// Data dibaca tiap 4 detik; selama menu aksi terbuka pembaruan ditahan supaya item menu tidak bergeser.
let tertunda = null
async function muat() {
  try {
    const r = await fetch('/api/installer', { cache: 'no-store' })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const d = await r.json()
    galat.value = ''
    if (menu.value?.buka) tertunda = d
    else data.value = d
  } catch (e) {
    galat.value = `API tidak tersedia: ${e.message}`
  }
}
let timer = null
const saatTerlihat = () => { if (!document.hidden) muat() }
onMounted(() => {
  muat()
  timer = setInterval(() => { if (!document.hidden) muat() }, 4000)
  document.addEventListener('visibilitychange', saatTerlihat)
})
onBeforeUnmount(() => { clearInterval(timer); clearInterval(pollLog); clearInterval(pollAlur); document.removeEventListener('visibilitychange', saatTerlihat) })
watch(() => menu.value?.buka, (b) => { if (!b && tertunda) { data.value = tertunda; tertunda = null } })

const domains = computed(() => data.value?.domains || [])
const daftarStatus = computed(() => [...new Set(domains.value.map((x) => x.status).filter(Boolean))].sort())
// Tanggal lokal, bukan toISOString() (UTC) yang di WIB bisa meleset sehari
const hariIni = () => { const n = new Date(), p = (x) => String(x).padStart(2, '0'); return `${n.getFullYear()}-${p(n.getMonth() + 1)}-${p(n.getDate())}` }
const tersaring = computed(() => {
  const q = cari.value.trim().toLowerCase(), t = hariIni()
  return domains.value.filter((x) => {
    if (q && !x.domain.toLowerCase().includes(q)) return false
    if (status.value && x.status !== status.value) return false
    if (deadline.value === 'semua') return true
    // Tanpa deadline (mis. domain di luar CRM) bukan "terlewat"
    const lewat = !!x.deadline && x.deadline < t
    return deadline.value === 'lewat' ? lewat : !lewat
  })
})
const jumlahHalaman = computed(() => Math.max(1, Math.ceil(tersaring.value.length / UKURAN_HALAMAN)))
watch([cari, status, deadline], () => { halaman.value = 1 })
watch(jumlahHalaman, (n) => { if (halaman.value > n) halaman.value = n })
const barisHalaman = computed(() => tersaring.value.slice((halaman.value - 1) * UKURAN_HALAMAN, halaman.value * UKURAN_HALAMAN))
watch(daftarStatus, (d) => { if (status.value && !d.includes(status.value)) status.value = '' })
function reset() { cari.value = ''; status.value = ''; deadline.value = 'semua' }

const ringkas = computed(() => {
  const h = { jalan: 0, gagal: 0, selesai: 0, antre: 0 }
  for (const x of domains.value) {
    if (x.status === 'RUNNING') h.jalan++
    else if (jenis(x) === 'gagal') h.gagal++
    else if (x.source === 'selesai') h.selesai++
    else h.antre++
  }
  return h
})

// ---- tampilan per baris ----
function jenis(x) {
  if (x.status === 'RUNNING') return 'jalan'
  if (x.status === 'FAILED' || x.status === 'installer_error') return 'gagal'
  if (x.status === 'READY' || x.status === 'SUCCESS') return 'siap'
  if (x.status === 'dikerjakan webmaster') return 'wm'
  if (x.status === 'belum diambil') return 'belum'
  return 'lain'
}
const LABEL_STATUS = { jalan: ['Berjalan', 'biru'], gagal: ['Gagal', 'merah'], siap: ['Siap', 'hijau'], wm: ['Webmaster', 'kuning'], belum: ['Belum diambil', 'abu'], lain: ['Perlu dicek', 'kuning'] }
function labelStatus(x) {
  const [l, k] = LABEL_STATUS[jenis(x)]
  return [x.source === 'selesai' && jenis(x) === 'siap' ? 'Selesai' : jenis(x) === 'lain' ? x.status : l, k]
}
const statusLengkap = (x) => x.status + (x.stage ? ` / ${x.stage}` : '') + (x.agen && x.message ? ` — ${x.message}` : '')
  + (jenis(x) === 'wm' && x.webmaster ? ` (${x.webmaster})` : '')
function target(x) {
  const t = x.target_host, def = data.value?.default_target
  if (!t) return def?.host ? { host: def.host, label: `calon: ${def.name || def.host}`, kelas: 'abu' } : null
  if ((data.value?.local_ips || []).includes(t)) return { host: t, label: 'Server ini', kelas: 'biru' }
  const s = (data.value?.servers || []).find((y) => y.host === t)
  return s ? { host: t, label: s.name || s.host, kelas: 'hijau' } : { host: t, label: 'Tidak terdaftar', kelas: 'kuning' }
}

function aksiBaris(x) {
  const j = jenis(x), selesai = x.source === 'selesai'
  const bisaJalan = j === 'siap' || j === 'gagal'
  const acts = [{
    label: j === 'gagal' ? 'Ulangi install' : selesai ? 'Jalankan ulang' : 'Siapkan install',
    danger: j === 'gagal' || selesai,
    disabled: !bisaJalan,
    title: bisaJalan ? '' : 'Generate manifest dulu',
    run: async () => {
      if (selesai && !(await konfirmasi({
        judul: 'Situs sudah terpasang', kelas: 'waspada', tombol: 'Lanjut',
        teks: `${x.domain} sudah terpasang (${(x.updated_at || '').slice(0, 10)}). Mode apply memasang ulang dan menimpa situs; pakai mode finish untuk merapikan saja.`,
      }))) return
      bukaWizard(x)
    },
  }]
  const bisaGenerate = x.status === 'NO_MANIFEST' || x.manifest === null || x.status.startsWith('missing_') || x.status.startsWith('invalid_')
  if (bisaGenerate) acts.push({ label: 'Generate manifest', disabled: x.folder === false, title: x.folder === false ? 'Folder Drive belum tersinkron' : '', run: () => generate(x.domain) })
  if (j === 'belum') acts.unshift({ label: 'Ambil alih', run: () => klaim(x.domain, 'claim') })
  else if (j === 'wm') acts.unshift({
    label: 'Ambil alih', danger: true,
    run: async () => {
      if (await konfirmasi({ judul: 'Ambil alih dari webmaster?', kelas: 'waspada', tombol: 'Ambil alih', teks: `${x.domain} sedang dikerjakan ${x.webmaster || 'seorang webmaster'} menurut CRM.` })) klaim(x.domain, 'claim')
    },
  })
  else if (x.claim) acts.push({ label: 'Lepas klaim', danger: true, run: () => klaim(x.domain, 'release') })
  acts.push({ label: 'Bagan proses', run: () => bukaAlur(x.domain) })
  if (x.log?.length || x.status === 'RUNNING' || x.ada_log) acts.push({ label: x.status === 'RUNNING' ? 'Lihat log (live)' : 'Lihat log', run: () => bukaLog(x.domain) })
  return acts
}

// ---- aksi ----
const tunda = (ms) => new Promise((r) => setTimeout(r, ms))
async function generate(domain) {
  catatan.value = { teks: `Generate manifest untuk ${domain}…`, jenis: '' }
  try {
    const j = await kirim('/api/installer/generate', { domain })
    catatan.value = { teks: j.generated === false ? `Manifest ${domain} sudah valid.` : `Manifest ${domain} digenerate.`, jenis: 'baik' }
    tunda(500).then(muat)
  } catch (e) {
    catatan.value = { teks: `Generate gagal: ${e.message}`, jenis: 'bahaya' }
    detail.value = { error: e.message, domain }
  }
}
async function klaim(domain, aksi) {
  const ambil = aksi === 'claim'
  if (!ambil && !(await konfirmasi({ judul: 'Lepas klaim?', kelas: 'bahaya', tombol: 'Lepas klaim', teks: `${domain} kembali ke antrean "belum diambil".` }))) return
  catatan.value = { teks: `${ambil ? 'Mengambil alih' : 'Melepas klaim'} ${domain}…`, jenis: '' }
  try {
    await kirim(`/api/installer/${aksi}`, { domain, by: 'manual' })
    catatan.value = { teks: `${ambil ? 'Diambil alih' : 'Klaim dilepas'}: ${domain}`, jenis: 'baik' }
    tunda(500).then(muat)
  } catch (e) {
    catatan.value = { teks: `${ambil ? 'Ambil alih' : 'Lepas klaim'} gagal: ${e.message}`, jenis: 'bahaya' }
  }
}

// ---- wizard install ----
const wiz = ref({ buka: false, langkah: 1, domain: '', mode: 'dry-run', gen: true, tampilGen: true, info: '', infoKelas: '' })
const MODE = [
  { nilai: 'dry-run', nama: 'Dry run', ket: 'Validasi manifest & cek server tujuan saja. Aman.' },
  { nilai: 'apply', nama: 'Apply', ket: 'Eksekusi nyata: menimpa public_html & menulis database.' },
  { nilai: 'finish', nama: 'Finish', ket: 'Rapikan ulang situs terpasang (konten, aset klien, QA) tanpa install ulang.' },
]
async function bukaWizard(x) {
  wiz.value = { buka: true, langkah: 1, domain: x.domain, mode: 'dry-run', gen: true, tampilGen: true, info: 'Memeriksa manifest…', infoKelas: '' }
  try {
    const r = await fetch(`/api/installer?domain=${encodeURIComponent(x.domain)}`, { cache: 'no-store' })
    const d = (await r.json()).domain_row || x
    const w = wiz.value
    if (d.source === 'selesai') Object.assign(w, { info: 'Situs sudah terpasang. Pilih mode finish untuk merapikan tanpa install ulang.', infoKelas: 'waspada', tampilGen: false, gen: false })
    else if (d.status === 'READY') Object.assign(w, { info: 'Manifest sudah valid.', infoKelas: 'baik', tampilGen: false })
    else if (jenis(d) === 'gagal') Object.assign(w, { info: 'Install sebelumnya gagal. Generate ulang manifest?', infoKelas: 'waspada' })
    else Object.assign(w, { info: 'Belum ada manifest valid.', infoKelas: '' })
  } catch {
    wiz.value.info = 'Gagal memeriksa manifest.'
  }
}
function wizardLanjut() {
  const w = wiz.value
  if (w.langkah < 3) { w.langkah++; return }
  w.buka = false
  jalankan({ domain: w.domain, mode: w.mode, gen: w.gen })
}
async function jalankan({ domain, mode, gen }) {
  catatan.value = { teks: `Menyiapkan install untuk ${domain}…`, jenis: '' }
  try {
    if (gen) await kirim('/api/installer/generate', { domain }).catch((e) => { throw new Error(`generate gagal: ${e.message}`) })
    const j = await kirim('/api/installer/run', { domain, mode })
    if (j.status !== 'started') throw new Error(j.status || 'tidak dimulai')
    catatan.value = { teks: `${mode} ${domain} dimulai (PID ${j.pid}).`, jenis: 'baik' }
    detail.value = { info: `${mode} dimulai`, ...j }
    tunda(1500).then(muat)
  } catch (e) {
    catatan.value = { teks: `Gagal memulai: ${e.message}`, jenis: 'bahaya' }
    detail.value = { error: e.message, domain, mode }
  }
}

// ---- log & bagan (dibaca ulang per domain selama dialog terbuka) ----
async function ambilDomain(domain) {
  const r = await fetch(`/api/installer?domain=${encodeURIComponent(domain)}`, { cache: 'no-store' })
  const d = await r.json().catch(() => ({}))
  if (!r.ok || !d.domain_row) throw new Error(d.error || `HTTP ${r.status}`)
  return d.domain_row
}
const log = ref({ buka: false, domain: '', row: null })
const kotakLog = ref(null)
let pollLog = null
async function segarkanLog() {
  if (document.hidden) return
  try {
    const el = kotakLog.value
    const diBawah = !el || el.scrollHeight - el.scrollTop - el.clientHeight < 40
    log.value.row = await ambilDomain(log.value.domain)
    if (diBawah) requestAnimationFrame(() => { if (kotakLog.value) kotakLog.value.scrollTop = kotakLog.value.scrollHeight })
  } catch { /* coba lagi di detak berikut */ }
}
function bukaLog(domain) {
  log.value = { buka: true, domain, row: domains.value.find((x) => x.domain === domain) || null }
  requestAnimationFrame(() => { if (kotakLog.value) kotakLog.value.scrollTop = kotakLog.value.scrollHeight })
  clearInterval(pollLog)
  pollLog = setInterval(segarkanLog, 3000)
  segarkanLog()
}
function tutupLog() { log.value.buka = false; clearInterval(pollLog) }
const teksLog = computed(() => log.value.row?.log?.length ? log.value.row.log.join('\n') : '(log kosong)')

const alur = ref({ buka: false, domain: '', row: null, galat: '' })
let pollAlur = null
async function segarkanAlur() {
  try {
    const row = await ambilDomain(alur.value.domain)
    if (!alur.value.buka) return
    alur.value.row = row
    alur.value.galat = ''
    if (row.status === 'RUNNING' && !pollAlur) pollAlur = setInterval(segarkanAlur, 2000)
    if (row.status !== 'RUNNING') { clearInterval(pollAlur); pollAlur = null }
  } catch (e) {
    alur.value.galat = e.message
  }
}
function bukaAlur(domain) { alur.value = { buka: true, domain, row: null, galat: '' }; segarkanAlur() }
function tutupAlur() { alur.value.buka = false; clearInterval(pollAlur); pollAlur = null }
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Website Installer</h1>
        <p class="redup">Antrean dari Drive <code>/home/On Progress/</code> dan CRM, diperbarui tiap 4 detik. Situs yang sudah terpasang berlabel Selesai.</p>
      </div>
      <RouterLink to="/installer/susulan" class="tombol garis"><Ikon nama="berkas" :ukuran="18" />Susulan aturan</RouterLink>
    </header>

    <section class="ringkas" aria-label="Ringkasan antrean">
      <div class="kartu angka"><span class="redup">Berjalan</span><b :class="{ biru: ringkas.jalan }">{{ ringkas.jalan }}</b></div>
      <div class="kartu angka"><span class="redup">Gagal</span><b :class="{ merah: ringkas.gagal }">{{ ringkas.gagal }}</b></div>
      <div class="kartu angka"><span class="redup">Antrean</span><b>{{ ringkas.antre }}</b></div>
      <div class="kartu angka"><span class="redup">Selesai</span><b>{{ ringkas.selesai }}</b></div>
    </section>

    <p v-if="catatan.teks" class="pesan-status" :class="catatan.jenis" role="status">{{ catatan.teks }}</p>
    <details v-if="detail" class="detail">
      <summary>Detail respons</summary>
      <pre>{{ JSON.stringify(detail, null, 2) }}</pre>
    </details>

    <section class="kartu">
      <div class="saring" role="search">
        <input v-model="cari" type="search" placeholder="Cari domain…" aria-label="Cari domain" autocomplete="off">
        <select v-model="status" aria-label="Saring status">
          <option value="">Semua status</option>
          <option v-for="s in daftarStatus" :key="s" :value="s">{{ s }}</option>
        </select>
        <select v-model="deadline" aria-label="Saring deadline">
          <option value="semua">Semua deadline</option>
          <option value="aktif">Deadline belum terlewat</option>
          <option value="lewat">Deadline terlewat</option>
        </select>
        <button type="button" class="tombol garis" @click="reset">Reset</button>
      </div>

      <p v-if="galat" class="pesan-status bahaya" role="alert">{{ galat }}</p>
      <div class="tabel-wadah">
        <table class="tabel">
          <thead>
            <tr><th>Domain</th><th class="sembunyi-hp">Paket</th><th class="sembunyi-hp">Deadline</th><th class="sembunyi-hp">Target</th><th>Status</th><th><span class="sr">Tindakan</span></th></tr>
          </thead>
          <tbody>
            <tr v-if="!data && !galat"><td colspan="6" class="redup">Memuat…</td></tr>
            <tr v-else-if="data && !domains.length"><td colspan="6" class="redup">Belum ada berkas domain.txt.</td></tr>
            <tr v-else-if="data && !barisHalaman.length"><td colspan="6" class="redup">Tidak ada domain yang cocok.</td></tr>
            <tr v-for="x in barisHalaman" :key="x.domain">
              <td class="kol-domain">
                <a :href="`https://${x.domain}`" target="_blank" rel="noopener noreferrer" class="domain">{{ x.domain }}</a>
                <a :href="`https://${x.domain}/wp-admin`" target="_blank" rel="noopener noreferrer" class="wpadmin" :aria-label="`wp-admin ${x.domain}`" title="Buka wp-admin"><Ikon nama="luar" :ukuran="14" /></a>
                <span class="lencana-baris">
                  <span v-if="x.source === 'crm'" class="lencana kuning" title="Ada di CRM tapi folder Drive belum tersinkron">Tanpa folder</span>
                  <span v-if="jenis(x) === 'wm'" class="lencana kuning" title="Status CRM: Dalam pengerjaan">WM{{ x.webmaster ? `: ${x.webmaster}` : '' }}</span>
                  <span v-if="x.agen" class="lencana biru" :title="`Agen desain Claude sejak ${x.agen.mulai || ''}${x.message ? ` — ${x.message}` : ''}`">Agen Claude</span>
                  <span v-if="x.source === 'selesai'" class="lencana hijau" :title="`Terpasang ${x.updated_at || ''}${x.crm_status ? ` — CRM: ${x.crm_status}` : ''}`">Selesai {{ (x.updated_at || '').slice(0, 10) }}</span>
                  <span v-if="x.claim && x.source !== 'selesai'" class="lencana" :class="x.claim.by === 'autopilot' ? 'biru' : 'hijau'" :title="`Diambil alih ${x.claim.at || ''}`">{{ x.claim.by === 'autopilot' ? 'Autopilot' : 'Manual' }}</span>
                </span>
                <span class="kecil hanya-hp">{{ x.paket || '' }}</span>
              </td>
              <td class="sembunyi-hp">{{ x.paket || '-' }}</td>
              <td class="sembunyi-hp nowrap">{{ x.deadline || '-' }}</td>
              <td class="sembunyi-hp">
                <template v-if="target(x)"><code>{{ target(x).host }}</code><span class="lencana" :class="target(x).kelas">{{ target(x).label }}</span></template>
                <span v-else class="redup">-</span>
              </td>
              <td>
                <span class="status" :class="labelStatus(x)[1]" :title="statusLengkap(x)">
                  <i v-if="jenis(x) === 'jalan'" class="putar" aria-hidden="true" />{{ labelStatus(x)[0] }}
                </span>
                <span v-if="x.stage && jenis(x) !== 'siap'" class="kecil tahap">{{ x.stage }}</span>
              </td>
              <td class="kol-aksi">
                <button type="button" class="tombol garis kecil" aria-haspopup="menu" @click="menu.tampilkan($event.currentTarget, aksiBaris(x))">Aksi <span aria-hidden="true">▾</span></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="paginasi">
        <span class="redup">{{ tersaring.length ? `${(halaman - 1) * UKURAN_HALAMAN + 1}–${Math.min(halaman * UKURAN_HALAMAN, tersaring.length)} dari ${tersaring.length} domain` : '0 domain' }}</span>
        <span>
          <button type="button" class="tombol garis kecil" :disabled="halaman <= 1" @click="halaman--">Sebelumnya</button>
          <button type="button" class="tombol garis kecil" :disabled="halaman >= jumlahHalaman" @click="halaman++">Berikutnya</button>
        </span>
      </div>
    </section>

    <MenuAksi ref="menu" />

    <Dialog :buka="wiz.buka" :judul="`Install: ${wiz.domain}`" lebar="520px" @tutup="wiz.buka = false">
      <ol class="langkah" aria-label="Langkah">
        <li v-for="(n, i) in ['Manifest', 'Mode', 'Konfirmasi']" :key="n" :class="{ aktif: wiz.langkah === i + 1, lewat: wiz.langkah > i + 1 }">{{ n }}</li>
      </ol>
      <div v-if="wiz.langkah === 1">
        <p class="pesan-status" :class="wiz.infoKelas">{{ wiz.info }}</p>
        <label v-if="wiz.tampilGen" class="centang"><input v-model="wiz.gen" type="checkbox"> Generate manifest otomatis jika belum ada</label>
      </div>
      <fieldset v-else-if="wiz.langkah === 2" class="pilihan-mode">
        <legend class="sr">Mode install</legend>
        <label v-for="m in MODE" :key="m.nilai" :class="{ pilih: wiz.mode === m.nilai, bahaya: m.nilai === 'apply' }">
          <input v-model="wiz.mode" type="radio" name="mode" :value="m.nilai">
          <span><b>{{ m.nama }}</b><small>{{ m.ket }}</small></span>
        </label>
        <p class="redup">Apply bersifat destruktif; backup otomatis dibuat di <code>/home/&lt;da_user&gt;/backup/</code>.</p>
      </fieldset>
      <dl v-else class="ringkasan-wiz">
        <dt>Domain</dt><dd>{{ wiz.domain }}</dd>
        <dt>Mode</dt><dd :class="{ merah: wiz.mode === 'apply' }">{{ MODE.find((m) => m.nilai === wiz.mode).nama }}</dd>
        <dt>Generate manifest</dt><dd>{{ wiz.gen ? 'Ya' : 'Tidak' }}</dd>
      </dl>
      <div class="aksi-dialog">
        <button type="button" class="tombol garis" @click="wiz.langkah > 1 ? wiz.langkah-- : (wiz.buka = false)">{{ wiz.langkah > 1 ? 'Kembali' : 'Batal' }}</button>
        <button type="button" class="tombol" :class="{ bahaya: wiz.langkah === 3 && wiz.mode === 'apply' }" @click="wizardLanjut">{{ wiz.langkah === 3 ? 'Jalankan' : 'Lanjut' }}</button>
      </div>
    </Dialog>

    <Dialog :buka="log.buka" :judul="`Log: ${log.domain}`" lebar="980px" @tutup="tutupLog">
      <p v-if="log.row?.status === 'RUNNING'" class="pesan-status jalan"><i class="putar" aria-hidden="true" />{{ log.row.stage === 'AGEN DESAIN CLAUDE' ? 'Agen Claude bekerja' : `Berjalan${log.row.stage ? `: ${log.row.stage}` : ''}` }}</p>
      <pre ref="kotakLog" class="log" tabindex="0">{{ teksLog }}</pre>
    </Dialog>

    <Dialog :buka="alur.buka" :judul="`Bagan proses: ${alur.domain}`" lebar="1100px" @tutup="tutupAlur">
      <BaganAlur :row="alur.row" :galat="alur.galat" />
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; min-width: 0; }
.ringkas { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.angka { display: grid; gap: 2px; padding: 14px 18px; }
.angka b { font-size: 26px; font-weight: 700; }
.angka b.biru { color: var(--aksen-terang); }
.angka b.merah { color: var(--bahaya); }
.saring { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr) auto; gap: 10px; margin-bottom: 14px; }
.kol-domain { min-width: 200px; }
.domain { font-weight: 600; color: var(--teks); }
.domain:hover { color: var(--aksen-terang); }
.wpadmin { display: inline-grid; place-items: center; width: 26px; height: 26px; margin-left: 2px; vertical-align: -6px; border-radius: 6px; color: var(--teks-3); }
.wpadmin:hover { background: var(--kartu-2); color: #fff; }
.lencana-baris { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.lencana-baris:empty { display: none; }
.nowrap { white-space: nowrap; }
td code { display: block; font-size: 12.5px; color: var(--teks-2); margin-bottom: 3px; }
.status { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.status.biru { color: var(--aksen-terang); background: var(--aksen-lembut); }
.status.hijau { color: var(--baik); background: rgba(52, 199, 123, .12); }
.status.merah { color: var(--bahaya); background: rgba(255, 107, 107, .12); }
.status.kuning { color: var(--waspada); background: rgba(232, 181, 74, .12); }
.status.abu { color: var(--teks-2); background: var(--kartu-2); }
.tahap { max-width: 180px; margin-top: 4px; overflow-wrap: anywhere; }
.kol-aksi { text-align: right; width: 1%; white-space: nowrap; }
.putar { width: 11px; height: 11px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: putar .8s linear infinite; flex: none; }
@keyframes putar { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .putar { animation: none; } }
.paginasi { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.paginasi span:last-child { display: flex; gap: 8px; }
.detail { font-size: 12.5px; color: var(--teks-2); }
.detail summary { cursor: pointer; }
.detail pre { margin: 8px 0 0; padding: 12px; border-radius: 10px; background: var(--panel); border: 1px solid var(--garis); overflow: auto; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.hanya-hp { display: none; }

.langkah { display: flex; gap: 6px; margin: 0 0 16px; padding: 0; list-style: none; counter-reset: l; }
.langkah li { flex: 1; padding: 8px 0 0; border-top: 3px solid var(--garis); font-size: 12.5px; color: var(--teks-3); counter-increment: l; }
.langkah li::before { content: counter(l) ". "; }
.langkah li.aktif { border-color: var(--aksen); color: var(--teks); font-weight: 600; }
.langkah li.lewat { border-color: var(--aksen-terang); border-top-color: rgba(91, 140, 255, .5); }
.centang { display: flex; align-items: center; gap: 10px; margin-top: 14px; cursor: pointer; }
.pesan-status.waspada { color: var(--waspada); }
.pesan-status.jalan { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; color: var(--aksen-terang); }
.pilihan-mode { display: grid; gap: 10px; margin: 0; padding: 0; border: 0; }
.pilihan-mode label { display: flex; gap: 12px; align-items: flex-start; padding: 12px 14px; border: 1px solid var(--garis); border-radius: 12px; cursor: pointer; }
.pilihan-mode label.pilih { border-color: var(--aksen-terang); background: var(--aksen-lembut); }
.pilihan-mode label.pilih.bahaya { border-color: var(--bahaya); background: rgba(255, 107, 107, .08); }
.pilihan-mode input { width: 18px; min-height: 18px; margin-top: 2px; accent-color: var(--aksen); flex: none; }
.pilihan-mode small { display: block; color: var(--teks-3); font-size: 12.5px; }
.ringkasan-wiz { display: grid; grid-template-columns: auto 1fr; gap: 8px 18px; margin: 0; padding: 14px 16px; border-radius: 12px; background: var(--panel); border: 1px solid var(--garis); }
.ringkasan-wiz dt { color: var(--teks-3); }
.ringkasan-wiz dd { margin: 0; font-weight: 600; overflow-wrap: anywhere; }
.ringkasan-wiz .merah { color: var(--bahaya); }
.log { margin: 0; padding: 14px; max-height: 64vh; overflow: auto; border-radius: 12px; background: var(--latar); border: 1px solid var(--garis); color: var(--teks-2); font: 12px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: pre-wrap; word-break: break-word; }

@media (max-width: 900px) {
  .ringkas { grid-template-columns: repeat(2, 1fr); }
  .saring { grid-template-columns: 1fr 1fr; }
  .saring input { grid-column: 1 / -1; }
}
@media (max-width: 700px) {
  .hanya-hp { display: block; }
  .kol-domain { min-width: 0; overflow-wrap: anywhere; }
  .saring .tombol { grid-column: 1 / -1; }
}
</style>
