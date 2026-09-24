<script setup>
// Situs jadi yang belum ikut aturan terbaru. Data: scripts/audit-susulan (hanya membaca situs) → /api/installer/susulan.
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { tanggalWaktu } from '../api.js'

const data = ref(null)
const galat = ref('')
const saring = ref('')
onMounted(async () => {
  try {
    const r = await fetch('/api/installer/susulan', { cache: 'no-store' })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    data.value = await r.json()
  } catch (e) { galat.value = `Laporan tidak terbaca: ${e.message}` }
})
const kodeInti = (k) => k.split(':')[0]
const ringkas = computed(() => {
  const h = {}
  for (const s of data.value?.situs || []) for (const a of s.aturan_baru) {
    const k = kodeInti(a.kode)
    h[k] ||= { n: 0, arti: a.arti }
    h[k].n++
  }
  return Object.entries(h).sort((a, b) => b[1].n - a[1].n)
})
const baris = computed(() => (data.value?.situs || []).filter((s) => !saring.value || s.aturan_baru.some((a) => kodeInti(a.kode) === saring.value)))
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Susulan aturan</h1>
        <p class="redup">Situs jadi yang belum ikut aturan terbaru. Perbaikan diputuskan manusia, karena sebagian situs sedang dikerjakan webmaster.</p>
      </div>
      <RouterLink to="/installer" class="tombol garis">Kembali ke Installer</RouterLink>
    </header>

    <p v-if="galat" class="pesan-status bahaya" role="alert">{{ galat }}</p>
    <p v-else-if="!data" class="redup">Memuat…</p>
    <template v-else>
      <p class="pesan-status">
        <template v-if="data.waktu"><b>{{ data.perlu_susulan }}</b> dari {{ data.jumlah }} situs perlu susulan · diperiksa {{ tanggalWaktu(data.waktu) }}</template>
        <template v-else>Belum ada laporan. Jalankan <code>scripts/audit-susulan</code>.</template>
      </p>
      <div class="chip-wadah" role="group" aria-label="Saring menurut aturan">
        <button v-for="[k, v] in ringkas" :key="k" type="button" class="chip" :aria-pressed="saring === k" @click="saring = saring === k ? '' : k">{{ v.arti }} <b>{{ v.n }}</b></button>
      </div>
      <section class="kartu">
        <div class="tabel-wadah">
          <table class="tabel">
            <thead><tr><th>Situs</th><th class="sembunyi-hp">Paket / tema</th><th>Belum ikut aturan</th><th class="sembunyi-hp">Temuan lain</th></tr></thead>
            <tbody>
              <tr v-for="s in baris" :key="s.domain">
                <td><a :href="`https://${s.domain}`" target="_blank" rel="noopener noreferrer"><b>{{ s.domain }}</b></a><span class="kecil">{{ s.status_instalasi }}</span></td>
                <td class="sembunyi-hp">{{ s.paket }}<span class="kecil">{{ s.tema }}</span></td>
                <td>
                  <ul v-if="s.aturan_baru.length">
                    <li v-for="a in s.aturan_baru" :key="a.kode" :title="a.kode">{{ a.arti }}<span v-if="a.kode.includes(':')" class="redup"> ({{ a.kode.split(':').slice(1).join(':') }})</span></li>
                  </ul>
                  <span v-else class="lencana hijau">Sudah ikut semua</span>
                </td>
                <td class="sembunyi-hp lain">{{ s.temuan_lain.join(', ') || '-' }}</td>
              </tr>
              <tr v-if="!baris.length"><td colspan="4" class="redup">Tidak ada situs.</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; min-width: 0; }
.chip-wadah { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { max-width: 100%; text-align: left; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--garis); background: var(--kartu); font-size: 12.5px; color: var(--teks-2); cursor: pointer; }
.chip b { margin-left: 4px; color: var(--teks); }
.chip:hover { border-color: var(--aksen-terang); }
.chip[aria-pressed="true"] { background: var(--aksen); border-color: var(--aksen); color: #fff; }
.chip[aria-pressed="true"] b { color: #fff; }
ul { margin: 0; padding-left: 18px; }
li { margin: 2px 0; }
.lain { max-width: 300px; color: var(--teks-3); font-size: 12.5px; overflow-wrap: anywhere; }
td a b { color: var(--teks); }
</style>
