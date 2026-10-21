<script setup>
// Log (sub-menu Server): semua log keamanan satu server dalam satu tabel bertag, untuk pencarian.
// Sumber = API yang sudah ada (tanpa SSH baru): /api/servers/firewall/log (lfd.log, csf.deny/tempban, SSH/fail2ban di PC)
// + /api/servers/firewall/waf (baris "ModSecurity:" error log LiteSpeed; hanya server hosting).
// Filter tag & kata kunci disimpan di URL (?s=&tag=&q=) supaya hasil pencarian bisa dibagikan.
import PilihServer from '../components/PilihServer.vue'
import { ref, computed, watch } from 'vue'
import Ikon from '../components/Ikon.vue'
import { pakaiPolling, tanggalWaktu, angka } from '../api.js'
import { tabUrl } from '../laravel.js'
import { pcKantor, pilihServer } from '../jenisServer.js'

const fw = pakaiPolling('/api/servers/firewall', 300000)
const servers = computed(() => fw.data.value?.servers || [])
const pilih = pilihServer()
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || servers.value[0] || null)
const hari = ref(1)

const urlLog = () => (terpilih.value ? `/api/servers/firewall/log?server=${encodeURIComponent(terpilih.value.host)}&hari=${hari.value}` : null)
const urlWaf = () => (terpilih.value && !pcKantor(terpilih.value) ? `/api/servers/firewall/waf?server=${encodeURIComponent(terpilih.value.host)}&hari=${hari.value}` : null)
const log = pakaiPolling(urlLog, 120000)
const waf = pakaiPolling(urlWaf, 120000)
watch(() => [terpilih.value?.host, hari.value], () => {
  for (const x of [log, waf]) { x.data.value = null; x.galat.value = null; x.memuat.value = true; x.muatUlang() }
})

// ---- Tag. Kelompok: sumber, aksi, jenis (kategori WAF / pemicu LFD), HTTP ----
const WARNA = {
  'Velocity WAF': 'teal', 'cPGuard WAF': 'kuning', 'Velocity BFM': 'teal', 'cPGuard BFM': 'kuning', LFD: 'biru', Dashboard: 'ungu',
  Manual: 'abu', fail2ban: 'biru', SSH: 'biru',
  Diblokir: 'merah', Dicatat: 'abu', Blokir: 'merah', Lepas: 'hijau', 'Login SSH': 'biru', Peringatan: 'kuning', Galat: 'merah', Sistem: 'abu',
}
const KAT_WAF = { ddos: 'Rate limit', eksploit: 'Eksploit', bot: 'Bot', lain: 'Lainnya' }
const JENIS_FW = { blokir: 'Blokir', login: 'Login SSH', peringatan: 'Peringatan', galat: 'Galat', lepas: 'Lepas', sistem: 'Sistem' }
const SUMBER_FW = { lfd: 'LFD', cpguard: 'cPGuard BFM', dashboard: 'Dashboard', manual: 'Manual', fail2ban: 'fail2ban', ssh: 'SSH' }
const PEMICU = {
  LF_SSHD: 'SSH', LF_FTPD: 'FTP', LF_SMTPAUTH: 'SMTP', LF_POP3D: 'POP3', LF_IMAPD: 'IMAP', LF_DIRECTADMIN: 'DirectAdmin',
  LF_MODSEC: 'ModSecurity', LF_HTACCESS: '.htaccess', LF_EXIMSYNTAX: 'Exim', CT_LIMIT: 'Koneksi', PS_LIMIT: 'Port scan',
  LF_DISTATTACK: 'Serangan terdistribusi', LF_CUSTOMTRIGGER: 'Velocity WAF', wordpress: 'WordPress', mod_security: 'ModSecurity',
}
const kelasTag = (t) => WARNA[t] || 'abu'

const baris = computed(() => {
  const out = []
  for (const s of waf.data.value?.servers || []) for (const e of s.acara || []) {
    const velocity = /^Velocity WAF/.test(e.msg) || /^77\d{5}$/.test(e.id)
    out.push({
      t: e.t, ip: e.ip,
      tag: [velocity ? 'Velocity WAF' : 'cPGuard WAF', e.kode === 'deteksi' ? 'Dicatat' : 'Diblokir', KAT_WAF[e.kategori] || 'Lainnya',
        ...(/^\d+$/.test(e.kode) ? [`HTTP ${e.kode}`] : [])],
      judul: e.domain || '-', detail: e.uri, aturan: (e.msg || '-').replace(/^(Malware\.Expert|cPGuard|Velocity WAF) - /, ''), id: e.id,
    })
  }
  for (const s of log.data.value?.servers || []) for (const e of s.acara || []) {
    const vbfm = /\(vwaf/i.test(e.pesan || '')
    out.push({
      t: e.t, ip: e.ip || '',
      tag: [vbfm ? 'Velocity BFM' : SUMBER_FW[e.sumber] || e.sumber, JENIS_FW[e.jenis] || e.jenis,
        ...(e.pemicu ? [PEMICU[e.pemicu] || e.pemicu] : []), ...(e.cc ? [e.cc] : []), ...(e.sementara ? ['Sementara'] : [])],
      judul: '', detail: e.pesan, aturan: '', id: '',
    })
  }
  for (const b of out) b.cari = [b.ip, b.judul, b.detail, b.aturan, b.id, ...b.tag].join(' ').toLowerCase()
  return out.sort((a, b) => b.t - a.t)
})

// ---- Filter: tag (semua harus cocok) + kata kunci (semua kata harus ada) ----
const tagUrl = tabUrl('tag', '')
const tagAktif = computed(() => (tagUrl.value ? tagUrl.value.split(',') : []))
const cariUrl = tabUrl('q', '')
const cari = ref(cariUrl.value)
let tunda = null
watch(cari, (v) => { clearTimeout(tunda); tunda = setTimeout(() => { cariUrl.value = v.trim() }, 300) })
function alihTag(t) {
  const s = new Set(tagAktif.value)
  s.has(t) ? s.delete(t) : s.add(t)
  tagUrl.value = [...s].join(',')
}
const batas = ref(100)
watch([tagUrl, cariUrl, () => terpilih.value?.host, hari], () => { batas.value = 100 })
const tersaring = computed(() => {
  const kata = cariUrl.value.toLowerCase().split(/\s+/).filter(Boolean)
  return baris.value.filter((b) => tagAktif.value.every((t) => b.tag.includes(t)) && kata.every((k) => b.cari.includes(k)))
})
// Hitungan tag dari hasil tersaring → chip menunjukkan berapa yang tersisa bila ditambahkan
const daftarTag = computed(() => {
  const n = {}
  for (const b of tersaring.value) for (const t of b.tag) n[t] = (n[t] || 0) + 1
  for (const t of tagAktif.value) n[t] = n[t] || 0
  return Object.entries(n).sort((a, b) => b[1] - a[1])
})
const tagSaran = computed(() => daftarTag.value.filter(([t]) => !tagAktif.value.includes(t)).slice(0, 24))

const memuat = computed(() => [[urlLog, log], [urlWaf, waf]].some(([u, x]) => u() && !x.data.value && !x.galat.value))
const galat = computed(() => [
  log.galat.value && `Log firewall: ${log.galat.value.message}`, log.data.value?.error && `Log firewall: ${log.data.value.error}`,
  waf.galat.value && `Log WAF: ${waf.galat.value.message}`, waf.data.value?.error && `Log WAF: ${waf.data.value.error}`,
  ...[...(log.data.value?.servers || []), ...(waf.data.value?.servers || [])].filter((s) => !s.ok).map((s) => `${s.name}: ${s.error}`),
].filter(Boolean))
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Log <span class="merek-guard">VelocityGuard</span></h1>
        <p class="redup">Semua log keamanan server dalam satu tabel: WAF (Velocity &amp; cPGuard), firewall LFD/CSF, brute force, dan login SSH. Saring dengan tag atau kata kunci.</p>
      </div>
    </header>

    <p v-if="fw.galat.value && !fw.data.value" class="pesan-status bahaya">Gagal memuat daftar server: {{ fw.galat.value.message }}</p>

    <PilihServer v-if="servers.length" :servers="servers" :model-value="terpilih?.name" @update:model-value="pilih = $event" />

    <section v-if="terpilih" class="kartu isi">
      <div class="alat">
        <div class="rentang" role="group" aria-label="Rentang log">
          <button type="button" :class="{ aktif: hari === 1 }" @click="hari = 1">24 jam</button>
          <button type="button" :class="{ aktif: hari === 7 }" @click="hari = 7">7 hari</button>
        </div>
        <label class="kotak-cari">
          <Ikon nama="cari" :ukuran="16" />
          <input v-model="cari" type="search" placeholder="Cari IP, domain, URL, aturan, id, pesan…" aria-label="Cari log">
        </label>
      </div>

      <div v-if="tagAktif.length || tagSaran.length" class="tag-filter" role="group" aria-label="Saring dengan tag">
        <button v-for="t in tagAktif" :key="'a' + t" type="button" class="chip aktif" :aria-pressed="true" @click="alihTag(t)">{{ t }} <span aria-hidden="true">×</span><span class="sr">hapus filter</span></button>
        <button v-for="[t, n] in tagSaran" :key="t" type="button" class="chip" :aria-pressed="false" @click="alihTag(t)">
          <span class="titik" :class="kelasTag(t)" aria-hidden="true" /> {{ t }} <small>{{ angka(n) }}</small>
        </button>
        <button v-if="tagAktif.length || cariUrl" type="button" class="tombol garis kecil" @click="tagUrl = ''; cari = ''">Hapus semua filter</button>
      </div>

      <div v-if="memuat" aria-busy="true">
        <p class="redup" role="status">Membaca log firewall &amp; WAF {{ terpilih.name }} lewat SSH (±10–40 detik)…</p>
        <span v-for="i in 8" :key="i" class="sk sk-baris" />
      </div>
      <template v-else>
        <p v-for="g in galat" :key="g" class="pesan-status bahaya">{{ g }}</p>
        <p class="redup jumlah" role="status">{{ angka(tersaring.length) }} dari {{ angka(baris.length) }} baris</p>
        <p v-if="!tersaring.length" class="redup">Tidak ada log yang cocok.</p>
        <div v-else class="tabel-wadah">
          <table class="tabel">
            <thead><tr><th scope="col">Waktu</th><th scope="col">Tag</th><th scope="col">IP</th><th scope="col">Detail</th></tr></thead>
            <tbody>
              <tr v-for="(b, i) in tersaring.slice(0, batas)" :key="i">
                <td class="nowrap"><time :datetime="new Date(b.t * 1000).toISOString()">{{ tanggalWaktu(b.t) }}</time></td>
                <td class="tag">
                  <button v-for="t in b.tag" :key="t" type="button" class="lencana" :class="kelasTag(t)" :title="`Saring: ${t}`" @click="tagAktif.includes(t) || alihTag(t)">{{ t }}</button>
                </td>
                <td class="nowrap"><button v-if="b.ip" type="button" class="ip" title="Cari IP ini" @click="cari = b.ip"><code>{{ b.ip }}</code></button></td>
                <td class="detail">
                  <template v-if="b.aturan"><b>{{ b.judul }}</b><span class="redup blok">{{ b.detail }}</span><span class="blok">{{ b.aturan }}<small v-if="b.id" class="redup"> · id {{ b.id }}</small></span></template>
                  <template v-else>{{ b.detail }}</template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <button v-if="tersaring.length > batas" type="button" class="tombol garis kecil lagi" @click="batas += 100">Tampilkan 100 lagi ({{ angka(tersaring.length - batas) }} tersisa)</button>
        <p class="redup catatan">Log WAF memuat 3.000 kejadian terbaru dan log firewall 1.500 kejadian terbaru. Login SSH dari IP kantor tidak ditampilkan. Klik tag atau IP di tabel untuk menyaring.</p>
      </template>
    </section>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.isi { display: grid; gap: 14px; }
.alat { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.rentang { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); }
.rentang button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.rentang button.aktif { background: var(--aksen); color: #fff; }
.kotak-cari { flex: 1 1 260px; min-width: 0; display: flex; align-items: center; gap: 8px; color: var(--teks-3); }
.kotak-cari input { flex: 1; min-width: 0; }
.tag-filter { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.chip { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--garis); background: transparent; color: var(--teks-2); font: inherit; font-size: 12.5px; font-weight: 600; padding: 4px 10px; border-radius: 999px; cursor: pointer; }
.chip small { color: var(--teks-3); font-weight: 500; }
.chip:hover { color: var(--teks-kuat); border-color: var(--teks-3); }
.chip.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); color: var(--aksen-terang); }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); }
.titik.merah { background: var(--bahaya); }
.titik.kuning { background: var(--waspada); }
.titik.hijau { background: var(--baik); }
.titik.biru { background: var(--aksen-terang); }
.titik.ungu { background: var(--ungu); }
.titik.teal { background: var(--teal); }
.jumlah { margin: 0; font-size: 12.5px; }
.tabel-wadah { position: relative; overflow-x: auto; }
.tag { min-width: 170px; }
.tag .lencana { border: 0; font: inherit; font-size: 11px; font-weight: 700; margin: 0 4px 4px 0; cursor: pointer; }
.tag .lencana:hover { text-decoration: underline; }
.lencana.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 14%, transparent); }
.detail { font-size: 13px; overflow-wrap: anywhere; min-width: 260px; }
.blok { display: block; font-size: 12px; margin-top: 2px; }
.ip { border: 0; background: none; padding: 0; cursor: pointer; }
.ip:hover code { text-decoration: underline; }
.nowrap { white-space: nowrap; }
.lagi { justify-self: start; }
.catatan { margin: 0; font-size: 12.5px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
.sk { --sk-dasar: color-mix(in srgb, var(--kartu-2), var(--teks) 7%); --sk-kilap: color-mix(in srgb, var(--kartu-2), var(--teks) 15%);
  display: block; border-radius: 6px; background: linear-gradient(90deg, var(--sk-dasar) 25%, var(--sk-kilap) 50%, var(--sk-dasar) 75%); background-size: 200% 100%; animation: sk-kilau 1.4s ease-in-out infinite; }
.sk-baris { height: 14px; margin: 14px 0; }
@keyframes sk-kilau { from { background-position: 100% 0; } to { background-position: -100% 0; } }
@media (prefers-reduced-motion: reduce) { .sk { animation: none; } }
</style>
