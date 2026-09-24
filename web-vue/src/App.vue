<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import Ikon from './components/Ikon.vue'
import KonfirmasiHost from './components/KonfirmasiHost.vue'
import { pakaiPolling } from './api.js'

const route = useRoute()
const sekarang = ref(new Date())
let jam = null
onMounted(() => { jam = setInterval(() => { sekarang.value = new Date() }, 1000) })
onBeforeUnmount(() => clearInterval(jam))

const tanggal = computed(() => sekarang.value.toLocaleDateString('id-ID', { weekday: 'long', day: 'numeric', month: 'long' }))
const pukul = computed(() => sekarang.value.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
const sapaan = computed(() => {
  const h = sekarang.value.getHours()
  return h < 11 ? 'Selamat pagi' : h < 15 ? 'Selamat siang' : h < 18 ? 'Selamat sore' : 'Selamat malam'
})

// Status server untuk kartu sambutan: ONLINE selama /api/stats menjawab
const stats = pakaiPolling('/api/stats', 5000)
const online = computed(() => !!stats.data.value && !stats.galat.value)

const backup = pakaiPolling('/api/backup', 30000)
const backupBerikut = computed(() => {
  const d = backup.data.value
  if (!d) return 'Memuat…'
  if (d.state === 'running') return `Sedang berjalan · tahap ${d.phase || '-'}`
  return d.next_run ? `${new Date(d.next_run * 1000).toLocaleString('id-ID', { weekday: 'short', hour: '2-digit', minute: '2-digit' })} · Google Drive` : 'Jadwal belum diketahui'
})

const NAV = [
  { ke: '/', label: 'Dashboard', ikon: 'dashboard' },
  { ke: '/installer', label: 'Installer', ikon: 'installer' },
  { ke: '/ai', label: 'AI Model', ikon: 'ai' },
  { ke: '/token', label: 'Token Usage', ikon: 'token' },
  { ke: '/paket', label: 'Paket', ikon: 'paket' },
  { ke: '/server', label: 'Server', ikon: 'server' },
  { ke: '/brain', label: 'Claude Brain', ikon: 'brain' },
]
const LAYANAN = [
  { url: '/n8n/', label: 'n8n', ikon: 'n8n' },
  { url: '/hermes/', label: 'Hermes', ikon: 'hermes' },
  { url: '/files/', label: 'File Manager', ikon: 'berkas' },
  { url: '/newvdnet/', label: 'New VDNet', ikon: 'crm', dev: true },
]

// Laci menu di HP
const menuBuka = ref(false)
watch(() => route.fullPath, () => { menuBuka.value = false })
const tutupEsc = (e) => { if (e.key === 'Escape') menuBuka.value = false }
onMounted(() => document.addEventListener('keydown', tutupEsc))
onBeforeUnmount(() => document.removeEventListener('keydown', tutupEsc))
</script>

<template>
  <div class="kerangka">
    <header class="atas-hp">
      <button class="ikon-tombol" type="button" aria-label="Buka menu" :aria-expanded="menuBuka" aria-controls="sisi" @click="menuBuka = true"><Ikon nama="menu" /></button>
      <RouterLink to="/" class="merek"><img src="/ikon.png" alt="" width="28" height="28"><span>Local PC</span></RouterLink>
      <span class="pil" :class="online ? 'baik' : 'bahaya'">{{ online ? 'Online' : 'Offline' }}</span>
    </header>
    <div v-if="menuBuka" class="tirai" @click="menuBuka = false" />

    <aside id="sisi" class="sisi" :class="{ buka: menuBuka }" aria-label="Menu utama">
      <div class="sisi-atas">
        <RouterLink to="/" class="merek"><img src="/ikon.png" alt="" width="30" height="30"><span>Velocity <b>Local PC</b></span></RouterLink>
        <button class="ikon-tombol tutup" type="button" aria-label="Tutup menu" @click="menuBuka = false"><Ikon nama="tutup" /></button>
      </div>

      <section class="sambutan">
        <div class="sambutan-baris">
          <span class="tanggal">{{ tanggal }}</span>
          <span class="pil" :class="online ? 'baik' : 'bahaya'">{{ online ? 'Online' : 'Offline' }}</span>
        </div>
        <p class="sapaan">{{ sapaan }},<br>Tim Velocity!</p>
        <p class="pukul"><Ikon nama="jam" :ukuran="15" /> {{ pukul }}</p>
      </section>

      <nav class="nav-kartu" aria-label="Halaman">
        <RouterLink v-for="n in NAV" :key="n.ke" :to="n.ke" class="nav-item" :class="{ aktif: n.ke === '/' ? route.path === '/' : route.path.startsWith(n.ke) }">
          <Ikon :nama="n.ikon" :ukuran="18" /><span>{{ n.label }}</span>
        </RouterLink>
      </nav>

      <nav class="nav-kartu" aria-label="Layanan kantor">
        <p class="nav-judul">Layanan</p>
        <a v-for="l in LAYANAN" :key="l.url" :href="l.url" class="nav-item">
          <Ikon :nama="l.ikon" :ukuran="18" /><span>{{ l.label }}</span>
          <em v-if="l.dev" class="lencana">DEV</em>
        </a>
      </nav>

      <RouterLink to="/#backup" class="kartu-bawah">
        <span class="kb-ikon"><Ikon nama="cadangan" :ukuran="18" /></span>
        <span><b>{{ backup.data.value?.state === 'running' ? 'Backup Google Drive' : 'Backup berikutnya' }}</b><small>{{ backupBerikut }}</small></span>
      </RouterLink>
    </aside>

    <main class="utama">
      <RouterView />
    </main>
    <KonfirmasiHost />
  </div>
</template>

<style scoped>
.kerangka { display: grid; grid-template-columns: 272px minmax(0, 1fr); gap: 20px; padding: 20px; min-height: 100vh; }
.sisi { display: flex; flex-direction: column; gap: 14px; position: sticky; top: 20px; align-self: start; height: calc(100vh - 40px); overflow-y: auto; }
.sisi-atas { display: flex; align-items: center; justify-content: space-between; padding: 4px 6px 2px; }
.merek { display: inline-flex; align-items: center; gap: 10px; color: var(--teks); font-weight: 600; font-size: 15px; }
.merek b { font-weight: 700; color: var(--aksen-terang); }
.merek img { border-radius: 8px; }
.ikon-tombol { display: grid; place-items: center; width: 40px; height: 40px; border: 0; border-radius: 10px; background: transparent; color: var(--teks-2); cursor: pointer; }
.ikon-tombol:hover { background: var(--kartu-2); color: #fff; }
.tutup { display: none; }

.sambutan { padding: 16px 18px; border-radius: var(--radius); background: var(--kartu); border: 1px solid var(--garis); }
.sambutan-baris { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.tanggal { font-size: 11.5px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: var(--teks-3); }
.sapaan { margin: 10px 0 8px; font-size: 21px; font-weight: 700; line-height: 1.25; }
.pukul { display: flex; align-items: center; gap: 6px; margin: 0; color: var(--teks-2); font-variant-numeric: tabular-nums; }

.nav-kartu { display: flex; flex-direction: column; gap: 2px; padding: 8px; border-radius: var(--radius); background: var(--kartu); border: 1px solid var(--garis); }
.nav-judul { margin: 6px 10px 4px; font-size: 11.5px; font-weight: 600; color: var(--teks-3); text-transform: uppercase; letter-spacing: .04em; }
.nav-item { display: flex; align-items: center; gap: 12px; min-height: 42px; padding: 0 12px; border-radius: var(--radius-kecil); color: var(--teks-2); font-weight: 500; }
.nav-item:hover { background: var(--kartu-2); color: #fff; }
.nav-item.aktif { background: var(--kartu-2); color: #fff; box-shadow: inset 3px 0 0 var(--aksen-terang); }
.nav-item.aktif :deep(svg) { color: var(--aksen-terang); }
.lencana { margin-left: auto; padding: 1px 7px; border-radius: 6px; font-style: normal; font-size: 10.5px; font-weight: 700; color: var(--waspada); background: rgba(232, 181, 74, .12); }

.kartu-bawah {
  margin-top: auto; display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-radius: var(--radius);
  background: linear-gradient(135deg, #2346c9, #3d6bff 60%, #5b8cff); color: #fff;
}
.kartu-bawah:hover { color: #fff; filter: brightness(1.08); }
.kartu-bawah b { display: block; font-size: 13.5px; }
.kartu-bawah small { display: block; font-size: 12px; opacity: .85; }
.kb-ikon { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; background: rgba(255, 255, 255, .16); flex: none; }

.utama { min-width: 0; border-radius: 22px; background: rgba(15, 18, 36, .72); border: 1px solid var(--garis); padding: 26px 28px 32px; }
.atas-hp, .tirai { display: none; }

@media (max-width: 960px) {
  .kerangka { grid-template-columns: minmax(0, 1fr); padding: 0; gap: 0; }
  .atas-hp { display: flex; align-items: center; gap: 10px; position: sticky; top: 0; z-index: 20; padding: 10px 16px; background: rgba(8, 10, 23, .92); border-bottom: 1px solid var(--garis); backdrop-filter: blur(8px); }
  .atas-hp .pil { margin-left: auto; }
  .sisi { position: fixed; z-index: 40; inset: 0 auto 0 0; width: min(300px, 86vw); height: 100vh; top: 0; padding: 16px; background: var(--panel); transform: translateX(-105%); transition: transform .2s ease; visibility: hidden; }
  .sisi.buka { transform: none; visibility: visible; }
  .tutup { display: grid; }
  .tirai { display: block; position: fixed; inset: 0; z-index: 30; background: rgba(0, 0, 0, .55); }
  .utama { border-radius: 0; border: 0; padding: 20px 16px 32px; background: transparent; }
}
@media (prefers-reduced-motion: reduce) { .sisi { transition: none; } }
</style>
