<script setup>
// Claude Brain: graf skill & memory (web/brain, data diperbarui timer brain-data tiap 5 menit).
// Angka ringkas dibaca langsung dari data.json/aktivitas.json; grafnya memakai mode mini halaman /brain/.
import { computed } from 'vue'
import { pakaiPolling, angka } from '../api.js'

const { data: brain, galat } = pakaiPolling('/brain/data.json', 60000)
const { data: akt } = pakaiPolling('/brain/aktivitas.json', 15000)
const toolHariIni = computed(() => Object.values(akt.value?.tools || {}).reduce((a, v) => a + (v.hari || 0), 0))
const stat = computed(() => [
  ['Memory', brain.value?.counts?.memory],
  ['Skill', brain.value?.counts?.skill],
  ['Proyek klien', brain.value?.counts?.proyek],
  ['Tools hari ini', akt.value ? toolHariIni.value : null],
])
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
@media (max-width: 900px) { .ringkas { grid-template-columns: repeat(2, 1fr); } }
</style>
