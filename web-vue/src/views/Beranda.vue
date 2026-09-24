<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import Ikon from '../components/Ikon.vue'
import GrafikGaris from '../components/GrafikGaris.vue'
import { pakaiPolling, ambil, ukuranBerkas, waktuLalu } from '../api.js'

// Status server (3 detik, sama seperti dashboard lama)
const stats = pakaiPolling('/api/stats', 3000)
const s = computed(() => stats.data.value)
const uptime = computed(() => {
  const u = s.value?.uptime || 0
  if (u < 3600) return `${Math.max(1, Math.floor(u / 60))} menit`
  if (u < 86400) return `${Math.floor(u / 3600)} jam ${Math.floor((u % 3600) / 60)} menit`
  return `${Math.floor(u / 86400)} hari ${Math.floor((u % 86400) / 3600)} jam`
})
const kartuStat = computed(() => {
  const d = s.value
  if (!d) return []
  return [
    { label: 'CPU', nilai: `${d.cpu}%`, persen: d.cpu, ket: `${d.cores} core` },
    { label: 'Memori', nilai: `${d.memory.percent}%`, persen: d.memory.percent, ket: `${ukuranBerkas(d.memory.used)} / ${ukuranBerkas(d.memory.total)}` },
    {
      label: 'Disk',
      baris: [['/', d.disk], ['/home', d.disk_home]].filter(([, x]) => x).map(([titik, x]) => ({
        titik, persen: x.percent, ket: `Sisa ${ukuranBerkas(x.free ?? x.total - x.used)} dari ${ukuranBerkas(x.total)}`,
      })),
    },
    { label: 'Load', nilai: d.load.map((v) => Number(v).toFixed(2)).join(' · '), persen: null, ket: `Uptime ${uptime.value}` },
  ]
})

// Riwayat pemakaian (perekam server_stats.py, 1 contoh/menit)
const RENTANG = [['1h', '1 jam'], ['1d', '1 hari'], ['7d', '7 hari'], ['30d', '30 hari']]
const rentang = ref('1h')
const riwayat = pakaiPolling(() => `/api/stats/history?range=${rentang.value}`, 60000)
watch(rentang, () => riwayat.muatUlang())
const titik = computed(() => riwayat.data.value?.points || [])
const SERI = [
  { kunci: 'cpu', label: 'CPU', warna: '#5b8cff' },
  { kunci: 'mem', label: 'RAM', warna: '#26a88e' },
]
const formatWaktu = (t, lengkap) => {
  const d = new Date(t * 1000)
  if (lengkap) return d.toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
  return rentang.value === '1h' || rentang.value === '1d'
    ? d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('id-ID', { day: '2-digit', month: 'short' })
}
const puncakCpu = computed(() => titik.value.length ? Math.max(...titik.value.map((q) => q.cpu_max ?? q.cpu)) : 0)

// Backup Google Drive
const backup = pakaiPolling('/api/backup', 15000)
const b = computed(() => backup.data.value)
const statusBackup = computed(() => {
  const d = b.value
  if (!d) return { teks: '-', kelas: 'waspada' }
  if (d.state === 'ok' && d.stale) return { teks: 'Basi', kelas: 'bahaya' }
  return ({ ok: { teks: 'Aman', kelas: 'baik' }, running: { teks: 'Berjalan', kelas: 'waspada' }, error: { teks: 'Gagal', kelas: 'bahaya' }, belum_pernah: { teks: 'Belum jalan', kelas: 'waspada' } })[d.state] || { teks: String(d.state || '-'), kelas: 'waspada' }
})
const pesanBackup = computed(() => {
  const d = b.value
  if (!d) return 'Memuat status backup…'
  if (d.error) return `Error: ${d.error}`
  if (d.state === 'ok' && d.stale) return `Backup terakhir sukses ${waktuLalu(d.last_ok)}, sudah lewat 48 jam. Periksa timer.`
  if (d.state === 'belum_pernah') return 'Belum pernah jalan. Menunggu backup pertama.'
  return `Arsip terenkripsi AES256 · retensi 3 harian + 1 mingguan · ${d.dest || '-'}`
})

// Cronjob aktif (dari API installer)
const installer = pakaiPolling('/api/installer', 10000)
const cron = computed(() => {
  const c = installer.data.value?.cronjobs
  const daftar = Array.isArray(c) ? c : c?.preview || []
  return { daftar, total: c?.count || daftar.length }
})

const LAYANAN = [
  { ke: '/installer', label: 'Website Installer', ket: 'Install dan pantau website dari manifest.', ikon: 'installer' },
  { ke: '/server', label: 'Manage Server', ket: 'Kelola server internal, shutdown & restart.', ikon: 'server' },
  { ke: '/paket', label: 'Package Manager', ket: 'Tema & plugin dari API Velocity.', ikon: 'paket' },
  { ke: '/ai', label: 'Manage Model', ket: 'Model AI untuk generate konten.', ikon: 'ai' },
  { url: '/n8n/', label: 'n8n', ket: 'Otomasi workflow dan integrasi aplikasi.', ikon: 'n8n' },
  { url: '/hermes/', label: 'Hermes', ket: 'Asisten AI internal untuk tim.', ikon: 'hermes' },
  { url: '/files/', label: 'File Manager', ket: 'Penyimpanan dan berbagi file kantor.', ikon: 'berkas' },
  { url: '/newvdnet/', label: 'New VDNet', ket: 'CRM Velocity (dev :3005/:8005), belum untuk tim.', ikon: 'crm', dev: true },
]

// Kotak Claude Brain hanya bila /brain/ bisa diakses (khusus jaringan kantor)
const brainAda = ref(false)
onMounted(() => { fetch('/brain/data.json', { method: 'HEAD', cache: 'no-store' }).then((r) => { brainAda.value = r.ok }).catch(() => {}) })
</script>

<template>
  <div class="beranda">
    <header class="kepala">
      <div>
        <h1>Dashboard</h1>
        <p class="redup">Local PC Velocity Developer · layanan internal kantor</p>
      </div>
      <span class="pil" :class="stats.galat.value ? 'bahaya' : s ? 'baik' : 'waspada'">{{ stats.galat.value ? 'Server tidak menjawab' : s ? 'Semua data terhubung' : 'Memuat…' }}</span>
    </header>

    <section class="stat" aria-label="Status server">
      <template v-if="s">
        <article v-for="k in kartuStat" :key="k.label" class="kartu stat-kartu">
          <span class="redup">{{ k.label }}</span>
          <template v-if="k.baris">
            <div v-for="x in k.baris" :key="x.titik" class="disk-baris">
              <div class="disk-kepala"><span>{{ x.titik }}</span><strong>{{ x.persen }}%</strong></div>
              <div class="meter" role="meter" :aria-valuenow="x.persen" aria-valuemin="0" aria-valuemax="100" :aria-label="`Disk ${x.titik}`"><i :style="{ width: `${x.persen}%` }" /></div>
              <span class="redup">{{ x.ket }}</span>
            </div>
          </template>
          <template v-else>
            <strong class="angka">{{ k.nilai }}</strong>
            <div v-if="k.persen !== null" class="meter" role="meter" :aria-valuenow="k.persen" aria-valuemin="0" aria-valuemax="100" :aria-label="k.label"><i :style="{ width: `${k.persen}%` }" /></div>
            <span class="redup">{{ k.ket }}</span>
          </template>
        </article>
      </template>
      <article v-else v-for="i in 4" :key="i" class="kartu stat-kartu kerangka-muat"><span /><span /></article>
    </section>

    <div class="baris-2">
      <section class="kartu grafik-kartu" aria-labelledby="judul-grafik">
        <div class="kartu-judul">
          <div>
            <h2 id="judul-grafik">Pemakaian CPU &amp; RAM</h2>
            <p v-if="titik.length" class="redup">Puncak CPU {{ puncakCpu }}% · {{ riwayat.data.value.samples }} contoh</p>
          </div>
          <div class="rentang" role="tablist" aria-label="Rentang waktu">
            <button v-for="[k, l] in RENTANG" :key="k" type="button" role="tab" :aria-selected="rentang === k" :class="{ on: rentang === k }" @click="rentang = k">{{ l }}</button>
          </div>
        </div>
        <div class="legenda" aria-hidden="true">
          <span v-for="sr in SERI" :key="sr.kunci"><i :style="{ background: sr.warna }" />{{ sr.label }}</span>
        </div>
        <GrafikGaris v-if="titik.length" :titik="titik" :seri="SERI" :format-waktu="formatWaktu" />
        <p v-else class="kosong">
          <template v-if="riwayat.memuat.value">Memuat riwayat…</template>
          <template v-else-if="riwayat.galat.value">Gagal memuat riwayat pemakaian.</template>
          <template v-else>Belum ada data di rentang ini. Perekam menyimpan satu contoh per menit.</template>
        </p>
      </section>

      <section id="backup" class="kartu backup" aria-labelledby="judul-backup">
        <div class="kartu-judul">
          <h2 id="judul-backup">Backup Google Drive</h2>
          <span class="pil" :class="statusBackup.kelas">{{ statusBackup.teks }}</span>
        </div>
        <dl class="daftar-data">
          <div><dt>Terakhir sukses</dt><dd>{{ b ? waktuLalu(b.last_ok) : '-' }}</dd></div>
          <div><dt>Ukuran arsip</dt><dd>{{ b?.size ? ukuranBerkas(b.size) : '-' }}</dd></div>
          <div><dt>Arsip tersimpan</dt><dd>{{ b?.kept ? `${b.kept.harian} harian + ${b.kept.mingguan} mingguan` : '-' }}</dd></div>
          <div v-if="b?.state !== 'running'"><dt>Jadwal berikut</dt><dd>{{ b?.next_run ? new Date(b.next_run * 1000).toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '-' }}</dd></div>
          <div v-if="b?.state === 'running'"><dt>Tahap</dt><dd>{{ b.phase || '-' }}</dd></div>
          <div><dt>Timer</dt><dd :class="{ merah: b?.timer_active === false }">{{ b?.timer_active === false ? 'Mati' : 'Aktif · harian 02:00' }}</dd></div>
        </dl>
        <p class="redup pesan" :class="{ merah: b?.error || statusBackup.kelas === 'bahaya' }">{{ pesanBackup }}</p>
      </section>
    </div>

    <div class="baris-3">
      <section class="kartu" aria-labelledby="judul-layanan">
        <div class="kartu-judul"><h2 id="judul-layanan">Layanan kantor</h2></div>
        <div class="layanan">
          <component :is="l.ke ? 'RouterLink' : 'a'" v-for="l in LAYANAN" :key="l.label" :to="l.ke" :href="l.url" class="layanan-item">
            <span class="layanan-ikon"><Ikon :nama="l.ikon" /></span>
            <span class="layanan-teks"><b>{{ l.label }} <em v-if="l.dev">DEV</em></b><small>{{ l.ket }}</small></span>
          </component>
        </div>
      </section>

      <section class="kartu" aria-labelledby="judul-cron">
        <div class="kartu-judul"><h2 id="judul-cron">Cronjob aktif</h2><span class="redup">{{ cron.total }} jadwal</span></div>
        <p v-if="installer.memuat.value" class="redup">Memuat…</p>
        <p v-else-if="installer.galat.value" class="merah">Gagal memuat cronjob.</p>
        <p v-else-if="!cron.daftar.length" class="redup">Tidak ada cronjob aktif.</p>
        <ul v-else class="cron">
          <li v-for="(c, i) in cron.daftar" :key="i"><code>{{ c }}</code></li>
        </ul>
        <p v-if="cron.total > cron.daftar.length" class="redup">{{ cron.daftar.length }} dari {{ cron.total }} cronjob ditampilkan.</p>
      </section>
    </div>

    <section v-if="brainAda" class="kartu brain" aria-labelledby="judul-brain">
      <div class="kartu-judul">
        <h2 id="judul-brain">Claude Brain</h2>
        <RouterLink to="/brain" class="redup">Buka lengkap</RouterLink>
      </div>
      <iframe src="/brain/?mini=1" title="Graf memory dan skill Claude" loading="lazy" allow="fullscreen" />
    </section>
  </div>
</template>

<style scoped>
.beranda { display: grid; gap: 18px; }
.kepala { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.kepala h1 { font-size: 26px; }
.kepala p { margin: 4px 0 0; font-size: 13.5px; }

.stat { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.stat-kartu { display: grid; gap: 8px; align-content: start; }
.angka { font-size: 26px; font-weight: 700; letter-spacing: -.01em; font-variant-numeric: tabular-nums; }
.disk-baris { display: grid; gap: 6px; }
.disk-baris + .disk-baris { margin-top: 4px; }
.disk-kepala { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.disk-kepala strong { font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
.kerangka-muat { min-height: 118px; }
.kerangka-muat span { display: block; height: 12px; border-radius: 6px; background: var(--kartu-2); }
.kerangka-muat span + span { height: 26px; width: 50%; }

.baris-2 { display: grid; grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); gap: 18px; }
.baris-3 { display: grid; grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); gap: 18px; align-items: start; }
.kartu-judul p { margin: 2px 0 0; }
.rentang { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); }
.rentang button { min-height: 32px; padding: 0 12px; border: 0; border-radius: 8px; background: transparent; color: var(--teks-2); cursor: pointer; font-size: 12.5px; font-weight: 600; }
.rentang button:hover { color: #fff; }
.rentang button.on { background: var(--aksen); color: #fff; }
.legenda { display: flex; gap: 16px; margin: -4px 0 6px; font-size: 12.5px; color: var(--teks-2); }
.legenda span { display: inline-flex; align-items: center; gap: 6px; }
.legenda i { width: 10px; height: 10px; border-radius: 3px; }
.kosong { margin: 40px 0; text-align: center; color: var(--teks-3); }

.daftar-data { margin: 0; display: grid; gap: 2px; }
.daftar-data div { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--garis); }
.daftar-data dt { color: var(--teks-3); }
.daftar-data dd { margin: 0; font-weight: 600; text-align: right; }
.pesan { margin: 12px 0 0; }
.merah { color: var(--bahaya) !important; }

.layanan { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.layanan-item { display: flex; align-items: flex-start; gap: 12px; padding: 12px; border-radius: 12px; background: var(--kartu-2); border: 1px solid transparent; color: var(--teks); }
.layanan-item:hover { border-color: var(--aksen); color: var(--teks); }
.layanan-ikon { display: grid; place-items: center; flex: none; width: 36px; height: 36px; border-radius: 10px; background: var(--aksen-lembut); color: var(--aksen-terang); }
.layanan-teks b { display: block; font-weight: 600; }
.layanan-teks em { margin-left: 6px; padding: 1px 6px; border-radius: 5px; font-style: normal; font-size: 10.5px; color: var(--waspada); background: rgba(232, 181, 74, .12); }
.layanan-teks small { display: block; color: var(--teks-3); font-size: 12.5px; line-height: 1.45; }

.cron { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.cron code { display: block; padding: 8px 10px; border-radius: 8px; background: var(--kartu-2); color: var(--teks-2); font: 12px/1.45 ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }

.brain iframe { display: block; width: 100%; height: clamp(380px, 68vh, 760px); border: 0; border-radius: 12px; background: #0d1210; }

@media (max-width: 1200px) {
  .stat { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .baris-2, .baris-3 { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 560px) {
  .stat { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px; }
  .angka { font-size: 22px; }
  .layanan { grid-template-columns: minmax(0, 1fr); }
  .kartu-judul { flex-wrap: wrap; }
}
</style>
