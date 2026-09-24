<script setup>
// Claude Brain: graf skill & memory (web/brain, data diperbarui timer brain-data tiap 5 menit).
// Angka ringkas dibaca langsung dari data.json/aktivitas.json; grafnya memakai mode mini halaman /brain/.
import { ref, computed, watch } from 'vue'
import { pakaiPolling, angka } from '../api.js'

const { data: brain, galat } = pakaiPolling('/brain/data.json', 60000)
// aktivitas.json ditulis brain-aktivitas tiap 2 dtk; log realtime ikut membacanya tiap 3 dtk
const { data: akt, galat: galatAkt } = pakaiPolling('/brain/aktivitas.json', 3000)
const toolHariIni = computed(() => Object.values(akt.value?.tools || {}).reduce((a, v) => a + (v.hari || 0), 0))
const stat = computed(() => [
  ['Memory', brain.value?.counts?.memory],
  ['Skill', brain.value?.counts?.skill],
  ['Proyek klien', brain.value?.counts?.proyek],
  ['Tools hari ini', akt.value ? toolHariIni.value : null],
])

// ---- Log realtime: kejadian memory/skill/proyek + pemakaian tool, terbaru di atas ----
const AKSI = {
  baca: ['baca', 'biru'], tulis: ['tulis', 'kuning'], skill: ['skill', 'hijau'], proyek: ['proyek', 'ungu'], tool: ['tool', 'abu'],
}
const SARING = [['', 'Semua'], ['memori', 'Memory & skill'], ['proyek', 'Proyek'], ['tool', 'Tools']]
const saring = ref('')
const sesiDipilih = ref('')
const jeda = ref(false)
const beku = ref([])
const labelSesi = computed(() => Object.fromEntries((akt.value?.sesi || []).map((x) => [x.id, x.label])))
const namaSimpul = (e) => {
  if (e.skill) return e.skill
  if (e.domain) return e.domain
  if (e.id === 'hub:memory') return 'indeks memory'
  return String(e.id || '').replace(/^m:[^/]*\//, '')
}
const semuaLog = computed(() => {
  const a = akt.value
  if (!a) return []
  const ev = (a.events || []).map((e) => ({
    t: e.t, sesi: e.sesi, aksi: e.aksi, target: namaSimpul(e), kelompok: e.aksi === 'proyek' ? 'proyek' : 'memori',
    kunci: `e${e.t}${e.sesi}${e.id || e.skill || e.domain}${e.aksi}`,
  }))
  const al = (a.alat || []).map((e) => ({ t: e.t, sesi: e.sesi, aksi: 'tool', target: e.tool, ket: e.ket, kelompok: 'tool', kunci: `a${e.t}${e.sesi}${e.tool}` }))
  return [...ev, ...al].sort((x, y) => y.t - x.t)
})
// Saat dijeda, daftar dibekukan; data tetap diambil supaya lanjut tanpa lompatan
watch(jeda, (v) => { beku.value = v ? semuaLog.value : [] })
const log = computed(() => (jeda.value ? beku.value : semuaLog.value)
  .filter((e) => (!saring.value || e.kelompok === saring.value) && (!sesiDipilih.value || e.sesi === sesiDipilih.value))
  .slice(0, 150))
const tertunda = computed(() => (jeda.value && beku.value.length ? semuaLog.value.filter((e) => e.t > beku.value[0].t).length : 0))
// Baris yang muncul sesudah halaman dibuka diberi sorot sebentar
const dilihat = new Set()
let awal = true
const baru = ref(new Set())
watch(semuaLog, (l) => {
  const b = new Set()
  for (const e of l) { if (!dilihat.has(e.kunci)) { dilihat.add(e.kunci); if (!awal) b.add(e.kunci) } }
  awal = false
  baru.value = b
})
const jam = (t) => new Date(t * 1000).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const sesiAktif = computed(() => (akt.value?.sesi || []).filter((x) => x.jumlah))
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Claude Brain</h1>
        <p class="redup">Graf skill &amp; memory Claude. Sel menyala mengikuti aktivitas sesi yang sedang berjalan.</p>
      </div>
      <a href="/brain/" target="_blank" rel="noopener" class="tombol garis">Buka versi lengkap</a>
    </header>
    <p v-if="galat" class="pesan-status bahaya" role="alert">Data brain tidak terbaca.</p>
    <section class="ringkas" aria-label="Ringkasan">
      <div v-for="[l, n] in stat" :key="l" class="kartu angka"><span class="redup">{{ l }}</span><b>{{ n == null ? '–' : angka(n) }}</b></div>
    </section>
    <section class="kartu graf">
      <iframe src="/brain/?mini=1" title="Graf Claude Brain" loading="lazy" />
      <p class="redup">Klik titik untuk detail di versi lengkap · Ctrl + gulir untuk zoom.</p>
    </section>
    <section class="kartu log">
      <div class="kartu-judul">
        <h2><span class="titik" :class="{ mati: jeda || galatAkt }" aria-hidden="true" />Log realtime</h2>
        <span class="redup">{{ galatAkt ? 'data aktivitas tidak terbaca' : jeda ? 'dijeda' : 'diperbarui tiap 3 detik' }}</span>
      </div>
      <div class="saring" role="group" aria-label="Saring log">
        <div class="segmen" role="radiogroup" aria-label="Jenis kejadian">
          <button v-for="[k, l] in SARING" :key="k" type="button" role="radio" :aria-checked="saring === k" :class="{ aktif: saring === k }" @click="saring = k">{{ l }}</button>
        </div>
        <select v-model="sesiDipilih" aria-label="Saring sesi">
          <option value="">Semua sesi</option>
          <option v-for="x in sesiAktif" :key="x.id" :value="x.id">{{ x.label }}{{ x.hidup ? '' : ' (selesai)' }}</option>
        </select>
        <button type="button" class="tombol garis kecil" :aria-pressed="jeda" @click="jeda = !jeda">
          {{ jeda ? `Lanjutkan${tertunda ? ` (+${tertunda})` : ''}` : 'Jeda' }}
        </button>
      </div>
      <div class="gulir" role="log" aria-live="polite" aria-label="Log aktivitas Claude">
        <p v-if="!akt" class="redup">Memuat…</p>
        <p v-else-if="!log.length" class="redup">Belum ada aktivitas yang cocok.</p>
        <ol v-else>
          <li v-for="e in log" :key="e.kunci" :class="{ baru: baru.has(e.kunci) }">
            <time :datetime="new Date(e.t * 1000).toISOString()">{{ jam(e.t) }}</time>
            <span class="lencana" :class="(AKSI[e.aksi] || AKSI.baca)[1]">{{ (AKSI[e.aksi] || AKSI.baca)[0] }}</span>
            <span class="target" :title="e.ket || null"><code>{{ e.target }}</code><span v-if="e.ket" class="ket"> {{ e.ket }}</span></span>
            <span class="sesi">{{ labelSesi[e.sesi] || `sesi ${e.sesi}` }}</span>
          </li>
        </ol>
      </div>
    </section>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; min-width: 0; }
.ringkas { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.angka { display: grid; gap: 2px; padding: 14px 18px; }
.angka b { font-size: 26px; font-weight: 700; }
.graf { padding: 10px; }
.graf iframe { display: block; width: 100%; height: calc(100vh - 330px); min-height: 420px; border: 0; border-radius: 12px; background: var(--panel); }
.graf p { margin: 8px 6px 2px; }
.log .kartu-judul h2 { display: inline-flex; align-items: center; gap: 9px; }
.titik { width: 8px; height: 8px; border-radius: 50%; background: var(--baik); box-shadow: 0 0 0 0 rgba(52, 199, 123, .6); animation: denyut 2s infinite; }
.titik.mati { background: var(--teks-3); animation: none; }
@keyframes denyut { 70% { box-shadow: 0 0 0 7px rgba(52, 199, 123, 0); } 100% { box-shadow: 0 0 0 0 rgba(52, 199, 123, 0); } }
.saring { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px; }
.saring select { width: auto; min-width: 190px; }
.segmen { display: inline-flex; padding: 3px; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--panel); }
.segmen button { border: 0; background: transparent; color: var(--teks-2); padding: 7px 12px; border-radius: 8px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.segmen button.aktif { background: var(--aksen); color: #fff; }
.segmen button:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
.gulir { max-height: 420px; overflow-y: auto; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--panel); }
.gulir > p { margin: 0; padding: 14px; }
.gulir ol { list-style: none; margin: 0; padding: 4px 0; font-size: 13px; }
.gulir li { display: grid; grid-template-columns: 70px 64px minmax(0, 1fr) minmax(0, 220px); gap: 10px; align-items: center; padding: 6px 12px; border-bottom: 1px solid rgba(255, 255, 255, .03); }
.gulir li.baru { animation: sorot 2.4s ease-out; }
@keyframes sorot { from { background: var(--aksen-lembut); } to { background: transparent; } }
.gulir time { color: var(--teks-3); font-variant-numeric: tabular-nums; }
.gulir .lencana { text-align: center; }
.lencana.ungu { color: #b2a8ff; background: rgba(144, 133, 233, .14); }
.target { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1.4; }
.target code { color: var(--teks); font-size: 12.5px; background: none; padding: 0; }
.target .ket { margin-left: 8px; color: var(--teks-2); }
.sesi { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--teks-2); text-align: right; }
@media (prefers-reduced-motion: reduce) { .titik, .gulir li.baru { animation: none; } }
@media (max-width: 900px) { .ringkas { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px) {
  .gulir li { grid-template-columns: 62px 58px minmax(0, 1fr); }
  .gulir .sesi { grid-column: 3; text-align: left; font-size: 12px; }
}
</style>
