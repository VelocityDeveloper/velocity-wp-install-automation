<script setup>
// Log WAF (Server > Proteksi): GET /api/servers/firewall/waf?server=<host|semua>&hari=1|7.
// Sumber: baris "ModSecurity:" di error log LiteSpeed tiap server (aturan cPGuard/Malware.Expert yang dimuat ModSecurity),
// jadi tetap terbaca walau cPGuard nanti dicopot. Agen mengirim ringkasan (teratas, per jam) + kejadian terbaru saja.
import { ref, computed, watch } from 'vue'
import GrafikBatangTumpuk from './GrafikBatangTumpuk.vue'
import { pakaiPolling, tanggalWaktu, angka } from '../api.js'

const props = defineProps({
  server: { type: String, default: 'semua' },
  status: { type: Function, required: true },        // (ip, host) → 'deny' | 'sementara' | 'allow' | null
  proses: Boolean,
})
const emit = defineEmits(['blokir', 'lepas', 'cek'])

const hari = ref(1)
const waf = pakaiPolling(() => `/api/servers/firewall/waf?server=${encodeURIComponent(props.server)}&hari=${hari.value}`, 120000)
watch(() => [props.server, hari.value], () => { waf.data.value = null; waf.memuat.value = true; waf.muatUlang() })

// Urutan & warna lolos validator dataviz (gelap & terang; teal di latar terang dibantu legenda + tabel)
const KATEGORI = [
  { kunci: 'ddos', label: 'Rate limit / DDoS', warna: '#a679e6', kelas: 'ungu' },
  { kunci: 'eksploit', label: 'Eksploit & probe', warna: '#cc7a33', kelas: 'merah' },
  { kunci: 'bot', label: 'Bot & crawler', warna: '#5b8cff', kelas: 'biru' },
  { kunci: 'lain', label: 'Lainnya', warna: '#26a88e', kelas: 'abu' },
]
const infoKat = (k) => KATEGORI.find((x) => x.kunci === k) || KATEGORI[3]
const KODE = { 429: 'Terlalu banyak (bot)', 403: 'Ditolak', 406: 'Ditolak (rate limit)', deteksi: 'Hanya dicatat' }

const daftar = computed(() => waf.data.value?.servers || [])
const galatServer = computed(() => daftar.value.filter((s) => !s.ok))
const total = computed(() => daftar.value.reduce((a, s) => a + (s.total || 0), 0))
// Gabung "teratas" semua server (tiap server mengirim 20 teratas)
function gabung(k) {
  const peta = {}
  for (const s of daftar.value) for (const [n, v] of s.teratas?.[k] || []) {
    const kunci = k === 'ip' && props.server === 'semua' ? `${n}|${s.host}` : n
    peta[kunci] = (peta[kunci] || 0) + v
  }
  return Object.entries(peta).sort((a, b) => b[1] - a[1]).slice(0, 10)
}
const perKat = computed(() => Object.fromEntries(gabung('kategori')))
const aturanTeratas = computed(() => gabung('aturan'))
const domainTeratas = computed(() => gabung('domain'))
const ipTeratas = computed(() => {
  // Kunci ip|host: tombol Blokir/Lepas tahu servernya
  const peta = {}
  for (const s of daftar.value) for (const [ip, v] of s.teratas?.ip || []) {
    const k = `${ip}|${s.host}`
    peta[k] = (peta[k] || 0) + v
  }
  return Object.entries(peta).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, v]) => { const [ip, host] = k.split('|'); return { ip, host, v, name: namaHost(host) } })
})
const namaHost = (h) => daftar.value.find((s) => s.host === h)?.name || h
const puncakList = (arr) => Math.max(1, ...arr.map((x) => (Array.isArray(x) ? x[1] : x.v)))

// Grafik per jam (24 jam) / per hari (7 hari)
const ember = computed(() => {
  const per = hari.value === 1 ? 3600 : 86400
  const now = Math.floor(Date.now() / 1000)
  const awal = (t) => (per === 3600 ? Math.floor(t / 3600) * 3600 : Math.floor(new Date(new Date(t * 1000).toDateString()).getTime() / 1000))
  const kunci = []
  for (let i = (hari.value === 1 ? 23 : 6); i >= 0; i--) kunci.push(awal(now - i * per))
  const peta = Object.fromEntries(kunci.map((k) => [k, { tgl: k, nilai: { ddos: 0, eksploit: 0, bot: 0, lain: 0 } }]))
  for (const s of daftar.value) for (const [t, isi] of s.jam || []) {
    const b = peta[awal(Number(t))]
    if (b) for (const [k, v] of Object.entries(isi)) b.nilai[k] = (b.nilai[k] || 0) + v
  }
  return kunci.map((k) => peta[k])
})
const formatEmber = (t, panjang) => {
  const d = new Date(t * 1000)
  if (hari.value === 1) return panjang ? d.toLocaleString('id-ID', { weekday: 'short', hour: '2-digit', minute: '2-digit' }) : d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString('id-ID', panjang ? { weekday: 'long', day: 'numeric', month: 'short' } : { day: 'numeric', month: 'short' })
}
const angkaPendek = (v) => (v >= 10000 ? `${Math.round(v / 1000)} rb` : angka(v))

// Kejadian terbaru
const acara = computed(() => daftar.value.flatMap((s) => (s.acara || []).map((e) => ({ ...e, host: s.host, name: s.name }))).sort((a, b) => b.t - a.t))
const kat = ref('')
const cari = ref('')
const batas = ref(100)
watch([kat, cari, () => props.server, hari], () => { batas.value = 100 })
const tersaring = computed(() => {
  const q = cari.value.trim().toLowerCase()
  return acara.value.filter((e) => (!kat.value || e.kategori === kat.value)
    && (!q || e.ip.includes(q) || e.domain.includes(q) || e.uri.toLowerCase().includes(q) || e.msg.toLowerCase().includes(q)))
})
const saring = (teks) => { cari.value = teks; document.getElementById(`waf-tabel-${props.server}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }
const ringkasAturan = (m) => (m || '-').replace(/^(Malware\.Expert|cPGuard|Velocity WAF) - /, '')
const penyedia = (m) => (/^Malware\.Expert/.test(m) ? 'Malware.Expert' : /^cPGuard/.test(m) ? 'cPGuard' : /^Velocity WAF/.test(m) ? 'Velocity' : '')
const ipLokal = (ip) => /^(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|::1$|fe80:|f[cd])/i.test(ip)
const satu = computed(() => (props.server !== 'semua' ? daftar.value[0] : null))
</script>

<template>
  <div class="log-waf">
    <div class="alat">
      <div class="rentang" role="group" aria-label="Rentang log WAF">
        <button type="button" :class="{ aktif: hari === 1 }" @click="hari = 1">24 jam</button>
        <button type="button" :class="{ aktif: hari === 7 }" @click="hari = 7">7 hari</button>
      </div>
      <input v-model="cari" type="search" placeholder="Cari IP / domain / URL / aturan" aria-label="Cari log WAF">
    </div>

    <div v-if="waf.memuat.value && !waf.data.value" aria-busy="true">
      <p class="redup" role="status">Membaca log ModSecurity LiteSpeed lewat SSH (±10–40 detik)…</p>
      <div class="kotak-angka"><span v-for="i in 4" :key="i" class="sk sk-angka" /></div>
      <span class="sk sk-grafik" /><span v-for="i in 5" :key="i" class="sk sk-baris" />
    </div>
    <p v-else-if="waf.galat.value && !waf.data.value" class="pesan-status bahaya">Gagal memuat log WAF: {{ waf.galat.value.message }}</p>
    <p v-else-if="waf.data.value?.error" class="pesan-status bahaya">Gagal memuat log WAF: {{ waf.data.value.error }}</p>

    <template v-else-if="waf.data.value">
      <p v-for="s in galatServer" :key="s.host" class="pesan-status bahaya">{{ s.name }}: log WAF tidak terbaca ({{ s.error }})</p>
      <p v-if="satu?.ok" class="redup catatan">
        ModSecurity {{ satu.modsecurity === 'yes' ? 'aktif' : (satu.modsecurity || '?') }} ·
        aturan: {{ satu.cpguard_rules ? 'cPGuard + Malware.Expert' : 'tidak ada aturan cPGuard' }}{{ satu.ruleset && satu.ruleset !== 'no' ? ` + ${satu.ruleset}` : '' }} ·
        Velocity WAF: {{ satu.velocity_waf ? satu.velocity_waf : 'belum dipasang' }} ·
        {{ satu.berkas }} berkas log dibaca
      </p>

      <div class="kotak-angka">
        <div class="angka-waf"><span class="redup">Request diblokir</span><b>{{ angka(total) }}</b></div>
        <div v-for="k in KATEGORI.filter((x) => x.kunci !== 'lain')" :key="k.kunci" class="angka-waf">
          <span class="redup"><span class="kotak" :style="{ background: k.warna }" aria-hidden="true" /> {{ k.label }}</span><b>{{ angka(perKat[k.kunci] || 0) }}</b>
        </div>
      </div>

      <div class="grafik">
        <div class="grafik-kepala">
          <b>Diblokir WAF per {{ hari === 1 ? 'jam' : 'hari' }}</b>
          <ul class="legenda">
            <li v-for="k in KATEGORI" :key="k.kunci"><span class="kotak" :style="{ background: k.warna }" /> {{ k.label }} <b>{{ angka(perKat[k.kunci] || 0) }}</b></li>
          </ul>
        </div>
        <GrafikBatangTumpuk :judul="`Request diblokir WAF per ${hari === 1 ? 'jam' : 'hari'} menurut kategori`" :hari="ember" :seri="KATEGORI" :format="angkaPendek"
          :format-tanggal="formatEmber" satuan="request" :satuan-batang="hari === 1 ? 'jam' : 'hari'" />
      </div>

      <div class="tiga-kolom">
        <section>
          <h3>Aturan teratas</h3>
          <ul class="peringkat">
            <li v-for="[n, v] in aturanTeratas" :key="n">
              <button type="button" class="nama" :title="n" @click="saring(n)"><small v-if="penyedia(n)" class="redup">{{ penyedia(n) }}</small> {{ ringkasAturan(n) }}</button>
              <span class="meter"><span :style="{ width: `${(v / puncakList(aturanTeratas)) * 100}%` }" /></span><b>{{ angkaPendek(v) }}</b>
            </li>
          </ul>
        </section>
        <section>
          <h3>Domain paling diserang</h3>
          <ul class="peringkat">
            <li v-for="[n, v] in domainTeratas" :key="n">
              <button type="button" class="nama" @click="saring(n)">{{ n || '(tanpa domain)' }}</button>
              <span class="meter"><span :style="{ width: `${(v / puncakList(domainTeratas)) * 100}%` }" /></span><b>{{ angkaPendek(v) }}</b>
            </li>
          </ul>
        </section>
        <section>
          <h3>IP paling sering diblokir</h3>
          <ul class="peringkat ip">
            <li v-for="x in ipTeratas" :key="x.ip + x.host">
              <button type="button" class="nama" title="Cek IP ini di semua server" @click="emit('cek', x.ip)"><code>{{ x.ip }}</code> <small v-if="server === 'semua'" class="redup">{{ x.name }}</small></button>
              <b>{{ angkaPendek(x.v) }}</b>
              <span v-if="status(x.ip, x.host) === 'allow'" class="lencana hijau">WL</span>
              <button v-else-if="status(x.ip, x.host)" type="button" class="tombol garis kecil" :disabled="proses" @click="emit('lepas', x.ip, x.host)">Lepas</button>
              <button v-else-if="!ipLokal(x.ip)" type="button" class="tombol bahaya kecil" :disabled="proses" @click="emit('blokir', x.ip, x.host)">Blokir</button>
            </li>
          </ul>
        </section>
      </div>

      <div :id="`waf-tabel-${server}`" class="chip-filter" role="group" aria-label="Kategori WAF">
        <button type="button" :class="{ aktif: !kat }" @click="kat = ''">Semua</button>
        <button v-for="k in KATEGORI.filter((x) => perKat[x.kunci])" :key="k.kunci" type="button" :class="{ aktif: kat === k.kunci }" @click="kat = k.kunci">
          <span class="kotak" :style="{ background: k.warna }" aria-hidden="true" /> {{ k.label }}
        </button>
      </div>
      <p v-if="!tersaring.length" class="redup">Tidak ada kejadian yang cocok di {{ angka(acara.length) }} kejadian terbaru.</p>
      <div v-else class="tabel-wadah">
        <table class="tabel">
          <thead><tr>
            <th scope="col">Waktu</th><th v-if="server === 'semua'" scope="col">Server</th><th scope="col">Kategori</th>
            <th scope="col">IP</th><th scope="col">Domain & URL</th><th scope="col">Aturan</th><th scope="col"><span class="sr">Aksi</span></th>
          </tr></thead>
          <tbody>
            <tr v-for="(e, i) in tersaring.slice(0, batas)" :key="i">
              <td class="nowrap"><time :datetime="new Date(e.t * 1000).toISOString()">{{ tanggalWaktu(e.t) }}</time></td>
              <td v-if="server === 'semua'" class="nowrap"><b>{{ e.name }}</b></td>
              <td class="nowrap"><span class="lencana" :class="infoKat(e.kategori).kelas">{{ infoKat(e.kategori).label }}</span><small class="redup blok" :title="KODE[e.kode]">{{ e.kode === 'deteksi' ? 'dicatat' : e.kode === '-' ? 'ditolak' : `HTTP ${e.kode}` }}</small></td>
              <td class="nowrap"><button type="button" class="ip" title="Cek IP ini di semua server" @click="emit('cek', e.ip)"><code>{{ e.ip }}</code></button></td>
              <td class="url"><b>{{ e.domain || '-' }}</b><span class="redup blok">{{ e.uri }}</span></td>
              <td class="aturan">{{ ringkasAturan(e.msg) }}<small v-if="e.id" class="redup blok">id {{ e.id }}</small></td>
              <td class="kanan">
                <span v-if="status(e.ip, e.host) === 'allow'" class="lencana hijau">WHITELIST</span>
                <button v-else-if="status(e.ip, e.host)" type="button" class="tombol garis kecil" :disabled="proses" @click="emit('lepas', e.ip, e.host)">Lepas</button>
                <button v-else-if="!ipLokal(e.ip)" type="button" class="tombol bahaya kecil" :disabled="proses" @click="emit('blokir', e.ip, e.host)">Blokir</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <button v-if="tersaring.length > batas" type="button" class="tombol garis kecil lagi" @click="batas += 100">Tampilkan 100 lagi ({{ angka(tersaring.length - batas) }} tersisa)</button>
      <p class="redup catatan">Angka & peringkat dihitung dari seluruh log; tabel memuat {{ server === 'semua' ? '250' : '3.000' }} kejadian terbaru{{ server === 'semua' ? ' per server' : '' }}. Klik aturan/domain untuk menyaring, klik IP untuk mengeceknya.</p>
    </template>
  </div>
</template>

<style scoped>
.log-waf { display: grid; gap: 14px; min-width: 0; }
.alat { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.alat input { flex: 1 1 220px; min-width: 0; }
.rentang { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); }
.rentang button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.rentang button.aktif { background: var(--aksen); color: #fff; }
.kotak-angka { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.angka-waf { display: grid; gap: 4px; padding: 12px 14px; border-radius: 12px; background: var(--kartu-2); }
.angka-waf span { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; }
.angka-waf b { font-size: 22px; color: var(--teks-kuat); }
.grafik { display: grid; gap: 6px; }
.grafik-kepala { display: flex; justify-content: space-between; align-items: center; gap: 8px 16px; flex-wrap: wrap; font-size: 13.5px; }
.legenda { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--teks-2); }
.legenda li { display: inline-flex; align-items: center; gap: 7px; }
.legenda b { color: var(--teks); }
.kotak { display: inline-block; flex: none; width: 10px; height: 10px; border-radius: 3px; }
.tiga-kolom { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
.tiga-kolom > * { min-width: 0; }
.tiga-kolom h3 { margin: 0 0 10px; font-size: 13.5px; color: var(--teks-kuat); }
.peringkat { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.peringkat li { display: grid; grid-template-columns: minmax(0, 1fr) 70px auto; gap: 8px; align-items: center; font-size: 13px; }
.peringkat.ip li { grid-template-columns: minmax(0, 1fr) auto auto; }
.peringkat .nama { min-width: 0; border: 0; background: none; padding: 0; color: var(--teks-2); font: inherit; text-align: left; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.peringkat .nama:hover { color: var(--teks-kuat); text-decoration: underline; }
.peringkat .tombol.kecil { min-height: 28px; padding: 0 9px; font-size: 12px; }
.meter { height: 6px; border-radius: 99px; background: var(--kartu-2); overflow: hidden; }
.meter span { display: block; height: 100%; border-radius: 99px; background: var(--aksen-terang); }
.chip-filter { display: flex; gap: 4px; flex-wrap: wrap; scroll-margin-top: 80px; }
.chip-filter button { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--garis); background: transparent; color: var(--teks-2); font: inherit; font-size: 12.5px; font-weight: 600; padding: 5px 10px; border-radius: 999px; cursor: pointer; }
.chip-filter button.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); color: var(--aksen-terang); }
.lencana.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 14%, transparent); }
.catatan { margin: 0; font-size: 12.5px; }
.url { font-size: 13px; overflow-wrap: anywhere; min-width: 200px; max-width: 340px; }
.aturan { font-size: 13px; color: var(--teks-2); min-width: 180px; }
.blok { display: block; font-size: 11.5px; margin-top: 2px; }
.ip { border: 0; background: none; padding: 0; cursor: pointer; }
.ip:hover code { text-decoration: underline; }
.tabel-wadah { position: relative; overflow-x: auto; }
.nowrap { white-space: nowrap; }
.kanan { text-align: right; white-space: nowrap; }
.lagi { justify-self: start; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
.sk { --sk-dasar: color-mix(in srgb, var(--kartu-2), var(--teks) 7%); --sk-kilap: color-mix(in srgb, var(--kartu-2), var(--teks) 15%);
  display: block; border-radius: 6px; background: linear-gradient(90deg, var(--sk-dasar) 25%, var(--sk-kilap) 50%, var(--sk-dasar) 75%); background-size: 200% 100%; animation: sk-kilau 1.4s ease-in-out infinite; }
.sk-angka { height: 64px; border-radius: 12px; }
.sk-grafik { height: 220px; margin: 12px 0; border-radius: 10px; }
.sk-baris { height: 14px; margin: 14px 0; }
@keyframes sk-kilau { from { background-position: 100% 0; } to { background-position: -100% 0; } }
@media (prefers-reduced-motion: reduce) { .sk { animation: none; } }
@media (max-width: 900px) { .tiga-kolom { grid-template-columns: minmax(0, 1fr); } .kotak-angka { grid-template-columns: 1fr 1fr; } }
</style>
