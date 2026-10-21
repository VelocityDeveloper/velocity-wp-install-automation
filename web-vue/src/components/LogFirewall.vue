<script setup>
// Log firewall (Server > Proteksi): GET /api/servers/firewall/log?server=<host|semua>&hari=1|7.
// Sumber: lfd.log (+ arsip) digabung blokir csf.deny/tempban yang tidak lewat lfd (cPGuard BFM, dashboard, manual).
// Login SSH dari IP kantor (timer dashboard) hanya dihitung agen, tidak dikirim per baris.
import { ref, computed, watch } from 'vue'
import GrafikBatangTumpuk from './GrafikBatangTumpuk.vue'
import { pakaiPolling, tanggalWaktu, angka } from '../api.js'

const props = defineProps({
  server: { type: String, default: 'semua' },       // host atau 'semua'
  status: { type: Function, required: true },        // (ip, host) → 'deny' | 'sementara' | 'allow' | null
  proses: Boolean,
  pc: Boolean,                                        // PC kantor: log SSH journal + fail2ban, bukan lfd
})
const emit = defineEmits(['blokir', 'lepas', 'cek'])

const hari = ref(1)
const log = pakaiPolling(() => `/api/servers/firewall/log?server=${encodeURIComponent(props.server)}&hari=${hari.value}`, 120000)
watch(() => [props.server, hari.value], () => { log.data.value = null; log.memuat.value = true; log.muatUlang() })

const JENIS = [
  { k: 'blokir', label: 'Blokir', kelas: 'merah' },
  { k: 'login', label: 'Login SSH', kelas: 'biru' },
  { k: 'peringatan', label: 'Peringatan', kelas: 'kuning' },
  { k: 'galat', label: 'Galat', kelas: 'merah' },
  { k: 'lepas', label: 'Lepas', kelas: 'hijau' },
  { k: 'sistem', label: 'Sistem', kelas: 'abu' },
]
const infoJenis = (k) => JENIS.find((j) => j.k === k) || { label: k, kelas: 'abu' }
const PEMICU = {
  LF_SSHD: 'SSH', LF_FTPD: 'FTP', LF_SMTPAUTH: 'SMTP', LF_POP3D: 'POP3', LF_IMAPD: 'IMAP', LF_DIRECTADMIN: 'DirectAdmin',
  LF_MODSEC: 'ModSecurity', LF_HTACCESS: '.htaccess', LF_EXIMSYNTAX: 'Exim', LF_CPANEL: 'cPanel', CT_LIMIT: 'Koneksi',
  PS_LIMIT: 'Port scan', LF_DISTATTACK: 'Serangan terdistribusi', LF_DISTFTP: 'FTP terdistribusi', LF_WEBMIN: 'Webmin',
  wordpress: 'WordPress', mod_security: 'ModSecurity', exim: 'Exim', dovecot: 'Dovecot', pureftpd: 'FTP', sshd: 'SSH', directadmin: 'DirectAdmin',
}
const SUMBER = { lfd: 'LFD', directadmin: 'DirectAdmin BFM', cpguard: 'cPGuard', dashboard: 'Dashboard', manual: 'Manual', fail2ban: 'fail2ban', ssh: 'SSH' }

const acara = computed(() => (log.data.value?.servers || []).flatMap((s) => (s.acara || []).map((e) => ({ ...e, host: s.host, name: s.name })))
  .sort((a, b) => b.t - a.t))
const galatServer = computed(() => (log.data.value?.servers || []).filter((s) => !s.ok))
const hitung = computed(() => {
  const out = {}
  for (const s of log.data.value?.servers || []) for (const [k, v] of Object.entries(s.hitung || {})) out[k] = (out[k] || 0) + v
  return out
})
const jenis = ref('')
const cari = ref('')
const batas = ref(100)
watch([jenis, cari, () => props.server, hari], () => { batas.value = 100 })
const tersaring = computed(() => {
  const q = cari.value.trim().toLowerCase()
  return acara.value.filter((e) => (!jenis.value || e.jenis === jenis.value)
    && (!q || (e.ip || '').includes(q) || e.pesan.toLowerCase().includes(q) || (e.name || '').toLowerCase().includes(q)))
})

// Grafik blokir per jam (24 jam) / per hari (7 hari), ditumpuk menurut sumber. Warna lolos validator dataviz.
// PC kantor: seri pertama = fail2ban (pengganti LFD), tanpa cPGuard
const SERI = computed(() => (props.pc
  ? [{ kunci: 'lfd', label: 'fail2ban', warna: '#5b8cff' }, { kunci: 'lain', label: 'Dashboard & manual', warna: '#26a88e' }]
  : [{ kunci: 'lfd', label: 'LFD', warna: '#5b8cff' }, { kunci: 'directadmin', label: 'DirectAdmin BFM', warna: '#cc7a33' }, { kunci: 'lain', label: 'Dashboard & manual', warna: '#26a88e' }]))
const ember = computed(() => {
  const per = hari.value === 1 ? 3600 : 86400
  const now = Math.floor(Date.now() / 1000)
  const awal = (t) => (per === 3600 ? Math.floor(t / 3600) * 3600 : Math.floor(new Date(new Date(t * 1000).toDateString()).getTime() / 1000))
  const kunci = []
  for (let i = (hari.value === 1 ? 23 : 6); i >= 0; i--) kunci.push(awal(now - i * per))
  const peta = Object.fromEntries(kunci.map((k) => [k, { tgl: k, nilai: { lfd: 0, directadmin: 0, lain: 0 } }]))
  for (const e of acara.value) {
    if (e.jenis !== 'blokir') continue
    const b = peta[awal(e.t)]
    if (b) b.nilai[e.sumber === 'lfd' || e.sumber === 'fail2ban' ? 'lfd' : e.sumber === 'directadmin' ? 'directadmin' : 'lain'] += 1
  }
  return kunci.map((k) => peta[k])
})
const totalSeri = (k) => ember.value.reduce((a, b) => a + b.nilai[k], 0)
const formatEmber = (t, panjang) => {
  const d = new Date(t * 1000)
  if (hari.value === 1) return panjang ? d.toLocaleString('id-ID', { weekday: 'short', hour: '2-digit', minute: '2-digit' }) : d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString('id-ID', panjang ? { weekday: 'long', day: 'numeric', month: 'short' } : { day: 'numeric', month: 'short' })
}

let namaNegara = null
try { namaNegara = new Intl.DisplayNames(['id'], { type: 'region' }) } catch { /* peramban lama */ }
const negara = (k) => { try { return (k && namaNegara?.of(k)) || k } catch { return k } }
// IP lokal/loopback tidak bisa diblokir (agen menolak) → tanpa tombol
const ipLokal = (ip) => /^(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|::1$|fe80:|f[cd])/i.test(ip)
const pesanRingkas = (e) => e.pesan.replace(/^(lfd: |BFM: |velocity: )/, '').replace(/\s*\([A-Z]{2}\/[^)]*\)/, '').replace(/ - \*Blocked in csf\*.*$/, '')
</script>

<template>
  <div class="log-fw">
    <div class="alat">
      <div class="rentang" role="group" aria-label="Rentang log">
        <button type="button" :class="{ aktif: hari === 1 }" @click="hari = 1">24 jam</button>
        <button type="button" :class="{ aktif: hari === 7 }" @click="hari = 7">7 hari</button>
      </div>
      <input v-model="cari" type="search" placeholder="Cari IP / pesan / server" aria-label="Cari log">
    </div>

    <div v-if="log.memuat.value && !log.data.value" aria-busy="true">
      <p class="redup" role="status">Membaca lfd.log lewat SSH…</p>
      <span class="sk sk-grafik" /><span v-for="i in 6" :key="i" class="sk sk-baris" />
    </div>
    <p v-else-if="log.galat.value && !log.data.value" class="pesan-status bahaya">Gagal memuat log: {{ log.galat.value.message }}</p>
    <p v-else-if="log.data.value?.error" class="pesan-status bahaya">Gagal memuat log: {{ log.data.value.error }}</p>

    <template v-else-if="log.data.value">
      <p v-for="s in galatServer" :key="s.host" class="pesan-status bahaya">{{ s.name }}: log tidak terbaca ({{ s.error }})</p>

      <div class="grafik">
        <div class="grafik-kepala">
          <b>Blokir per {{ hari === 1 ? 'jam' : 'hari' }}</b>
          <ul class="legenda">
            <li v-for="s in SERI" :key="s.kunci"><span class="kotak" :style="{ background: s.warna }" /> {{ s.label }} <b>{{ angka(totalSeri(s.kunci)) }}</b></li>
          </ul>
        </div>
        <GrafikBatangTumpuk :judul="`Blokir firewall per ${hari === 1 ? 'jam' : 'hari'} menurut sumber`" :hari="ember" :seri="SERI" :format="angka"
          :format-tanggal="formatEmber" satuan="blokir" :satuan-batang="hari === 1 ? 'jam' : 'hari'" />
      </div>

      <div class="chip-filter" role="group" aria-label="Jenis kejadian">
        <button type="button" :class="{ aktif: !jenis }" @click="jenis = ''">Semua {{ angka(acara.length) }}</button>
        <button v-for="j in JENIS.filter((x) => hitung[x.k])" :key="j.k" type="button" :class="{ aktif: jenis === j.k }" @click="jenis = j.k">
          <span class="titik" :class="j.kelas" aria-hidden="true" /> {{ j.label }} {{ angka(hitung[j.k]) }}
        </button>
      </div>
      <p v-if="hitung.login_kantor" class="redup catatan">{{ angka(hitung.login_kantor) }} login SSH dari IP kantor (pemantauan dashboard) tidak ditampilkan.</p>

      <p v-if="!tersaring.length" class="redup">Tidak ada kejadian yang cocok.</p>
      <div v-else class="tabel-wadah">
        <table class="tabel">
          <thead><tr>
            <th scope="col">Waktu</th><th v-if="server === 'semua'" scope="col">Server</th><th scope="col">Jenis</th>
            <th scope="col">IP</th><th scope="col">Kejadian</th><th scope="col"><span class="sr">Aksi</span></th>
          </tr></thead>
          <tbody>
            <tr v-for="(e, i) in tersaring.slice(0, batas)" :key="i">
              <td class="nowrap"><time :datetime="new Date(e.t * 1000).toISOString()">{{ tanggalWaktu(e.t) }}</time></td>
              <td v-if="server === 'semua'" class="nowrap"><b>{{ e.name }}</b></td>
              <td class="nowrap">
                <span class="lencana" :class="infoJenis(e.jenis).kelas">{{ infoJenis(e.jenis).label }}</span>
                <small v-if="e.jenis === 'blokir'" class="redup blok">{{ SUMBER[e.sumber] || e.sumber }}{{ e.sementara ? ' · sementara' : '' }}</small>
              </td>
              <td class="nowrap">
                <template v-if="e.ip"><span v-if="e.cc" class="kode-negara" :title="negara(e.cc)">{{ e.cc }}</span> <button type="button" class="ip" title="Cek IP ini di semua server" @click="emit('cek', e.ip)"><code>{{ e.ip }}</code></button></template>
                <span v-else class="redup">-</span>
              </td>
              <td class="pesan"><b v-if="e.pemicu" class="pemicu">{{ PEMICU[e.pemicu] || e.pemicu }}</b> {{ pesanRingkas(e) }}</td>
              <td class="kanan">
                <template v-if="e.ip">
                  <span v-if="status(e.ip, e.host) === 'allow'" class="lencana hijau">WHITELIST</span>
                  <button v-else-if="status(e.ip, e.host)" type="button" class="tombol garis kecil" :disabled="proses" @click="emit('lepas', e.ip, e.host)">Lepas</button>
                  <button v-else-if="!e.kantor && !ipLokal(e.ip) && e.jenis !== 'lepas'" type="button" class="tombol bahaya kecil" :disabled="proses" @click="emit('blokir', e.ip, e.host)">Blokir</button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <button v-if="tersaring.length > batas" type="button" class="tombol garis kecil lagi" @click="batas += 100">Tampilkan 100 lagi ({{ angka(tersaring.length - batas) }} tersisa)</button>
      <p v-if="pc" class="redup catatan">Dari journal SSH + /var/log/fail2ban.log + blokir dari dashboard. Login SSH dari LAN/Tailscale hanya dihitung.</p>
      <p v-else class="redup catatan">Dari /var/log/lfd.log tiap server + blokir cPGuard/dashboard di csf.deny{{ server === 'semua' ? ' · maks. 400 kejadian terbaru per server' : '' }}.</p>
    </template>
  </div>
</template>

<style scoped>
.log-fw { display: grid; gap: 12px; min-width: 0; }
.alat { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.alat input { flex: 1 1 220px; min-width: 0; }
.rentang { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); }
.rentang button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.rentang button.aktif { background: var(--aksen); color: #fff; }
.grafik { display: grid; gap: 6px; }
.grafik-kepala { display: flex; justify-content: space-between; align-items: center; gap: 8px 16px; flex-wrap: wrap; font-size: 13.5px; }
.legenda { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--teks-2); }
.legenda li { display: inline-flex; align-items: center; gap: 7px; }
.legenda b { color: var(--teks); }
.kotak { width: 10px; height: 10px; border-radius: 3px; }
.chip-filter { display: flex; gap: 4px; flex-wrap: wrap; }
.chip-filter button { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--garis); background: transparent; color: var(--teks-2); font: inherit; font-size: 12.5px; font-weight: 600; padding: 5px 10px; border-radius: 999px; cursor: pointer; }
.chip-filter button.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); color: var(--aksen-terang); }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); }
.titik.hijau { background: var(--baik); } .titik.kuning { background: var(--waspada); } .titik.merah { background: var(--bahaya); } .titik.biru { background: var(--aksen-terang); }
.catatan { margin: 0; font-size: 12.5px; }
.pesan { font-size: 13px; color: var(--teks-2); overflow-wrap: anywhere; min-width: 220px; }
.pemicu { color: var(--teks); font-weight: 600; }
.blok { display: block; font-size: 11.5px; margin-top: 2px; }
.ip { border: 0; background: none; padding: 0; cursor: pointer; }
.ip:hover code { text-decoration: underline; }
.kode-negara { display: inline-block; min-width: 26px; padding: 1px 5px; border-radius: 4px; font-size: 11px; font-weight: 700; text-align: center; color: var(--teks-2); background: var(--kartu-2); border: 1px solid var(--garis); }
.tabel-wadah { position: relative; overflow-x: auto; }
.nowrap { white-space: nowrap; }
.kanan { text-align: right; white-space: nowrap; }
.lagi { justify-self: start; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
.sk { --sk-dasar: color-mix(in srgb, var(--kartu-2), var(--teks) 7%); --sk-kilap: color-mix(in srgb, var(--kartu-2), var(--teks) 15%);
  display: block; border-radius: 6px; background: linear-gradient(90deg, var(--sk-dasar) 25%, var(--sk-kilap) 50%, var(--sk-dasar) 75%); background-size: 200% 100%; animation: sk-kilau 1.4s ease-in-out infinite; }
.sk-grafik { height: 220px; margin: 8px 0 12px; border-radius: 10px; }
.sk-baris { height: 14px; margin: 14px 0; }
@keyframes sk-kilau { from { background-position: 100% 0; } to { background-position: -100% 0; } }
@media (prefers-reduced-motion: reduce) { .sk { animation: none; } }
</style>
