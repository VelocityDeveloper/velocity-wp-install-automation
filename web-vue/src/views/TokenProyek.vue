<script setup>
// Token per project dengan rincian per alur (installer WordPress & Aplikasi Custom).
// Data: GET /api/ai/token-proyek (scripts/token_alur.py, dari /var/lib/velocity/ai/usage.jsonl).
import { ref, computed, watch } from 'vue'
import { pakaiPolling, angka, tanggalWaktu } from '../api.js'
import { tabUrl } from '../laravel.js'

const cari = tabUrl('cari', '')
const jenis = tabUrl('jenis', '', { boleh: ['wordpress', 'laravel'] })
const dari = tabUrl('dari', '')
const sampai = tabUrl('sampai', '')
const url = computed(() => `/api/ai/token-proyek?dari=${dari.value}&sampai=${sampai.value}`)
const { data, galat, muatUlang } = pakaiPolling(() => url.value, 60000)
watch(url, muatUlang)

const JENIS = { wordpress: 'WordPress', laravel: 'Aplikasi Custom' }
const dibuka = ref(new Set())
const usd = (n) => (n ? `$${Number(n).toLocaleString('id-ID', { maximumFractionDigits: 2 })}` : '–')

const proyek = computed(() => {
  const q = cari.value.trim().toLowerCase()
  return (data.value?.proyek || []).filter((p) => (!jenis.value || p.jenis === jenis.value)
    && (!q || p.id.toLowerCase().includes(q) || (p.nama || '').toLowerCase().includes(q)))
})
const jumlah = computed(() => proyek.value.reduce((t, p) => {
  for (const k of ['total', 'input', 'cache_tulis', 'cache_baca', 'output', 'panggilan', 'biaya_usd']) t[k] += p[k] || 0
  return t
}, { total: 0, input: 0, cache_tulis: 0, cache_baca: 0, output: 0, panggilan: 0, biaya_usd: 0 }))
// Pencarian yang menyisakan satu project (dari tautan installer) langsung membuka rinciannya
const terbuka = (p) => dibuka.value.has(p.id) || proyek.value.length === 1
const alih = (p) => {
  const s = new Set(dibuka.value)
  if (terbuka(p)) s.delete(p.id)
  else s.add(p.id)
  dibuka.value = s
}
// Alur dikelompokkan berurutan; baris kelompok muncul saat kelompoknya berganti
const barisAlur = (p) => {
  const hasil = []
  let kini = null
  for (const a of p.alur) {
    if (a.kelompok !== kini) {
      kini = a.kelompok
      hasil.push({ kelompok: kini, kunci: `k:${kini}`, total: p.alur.filter((x) => x.kelompok === kini).reduce((n, x) => n + x.total, 0) })
    }
    hasil.push(a)
  }
  return hasil
}
const persen = (n, p) => (p.total ? `${(n / p.total * 100).toLocaleString('id-ID', { maximumFractionDigits: 1 })}%` : '–')
</script>

<template>
  <div class="halaman">
    <section class="kartu">
      <div class="kartu-judul">
        <h2>Token per project</h2>
        <RouterLink to="/token" class="redup">← Token Usage</RouterLink>
      </div>
      <div class="saring">
        <input v-model="cari" type="search" placeholder="Cari domain, project-NNN, atau nama project" aria-label="Cari project">
        <select v-model="jenis" aria-label="Jenis project">
          <option value="">Semua installer</option>
          <option v-for="(l, k) in JENIS" :key="k" :value="k">{{ l }}</option>
        </select>
        <input v-model="dari" type="date" aria-label="Dari tanggal" :max="sampai || undefined">
        <input v-model="sampai" type="date" aria-label="Sampai tanggal" :min="dari || undefined">
      </div>
      <p v-if="galat" class="pesan-status bahaya">Gagal memuat: {{ galat }}</p>
      <p v-if="data" class="redup ringkas">
        <b>{{ angka(proyek.length) }}</b> project · <b>{{ angka(jumlah.total) }}</b> token ·
        <b>{{ angka(jumlah.panggilan) }}</b> permintaan · setara <b>{{ usd(jumlah.biaya_usd) }}</b> harga API
      </p>
      <div class="tabel-wadah">
        <table class="tabel">
          <thead>
            <tr>
              <th>Project / alur</th>
              <th class="kanan">Total</th>
              <th class="kanan sembunyi-hp" title="Bagian dari total yang tampil / total project">Porsi</th>
              <th class="kanan sembunyi-hp">Input</th>
              <th class="kanan sembunyi-hp">Cache tulis</th>
              <th class="kanan sembunyi-hp">Cache baca</th>
              <th class="kanan sembunyi-hp">Output</th>
              <th class="kanan sembunyi-hp">Permintaan</th>
              <th class="kanan">Biaya</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!data && !galat"><td colspan="9" class="redup">Memuat…</td></tr>
            <tr v-else-if="data && !proyek.length"><td colspan="9" class="redup">Tidak ada pemakaian yang cocok dengan saringan ini.</td></tr>
            <template v-for="p in proyek" :key="p.id">
              <tr class="baris-proyek" :class="{ terbuka: terbuka(p) }">
                <td>
                  <button type="button" class="buka" :aria-expanded="terbuka(p)" @click="alih(p)">
                    <span class="panah" aria-hidden="true">{{ terbuka(p) ? '▾' : '▸' }}</span>
                    <span>
                      <b>{{ p.id }}</b> <span class="lencana abu">{{ JENIS[p.jenis] }}</span>
                      <span v-if="p.nama" class="kecil">{{ p.nama }}</span>
                      <span class="kecil">{{ p.alur.length }} alur · terakhir {{ tanggalWaktu(p.terakhir) }}</span>
                    </span>
                  </button>
                </td>
                <td class="kanan"><b>{{ angka(p.total) }}</b></td>
                <td class="kanan redup sembunyi-hp">{{ jumlah.total ? persen(p.total, jumlah) : '–' }}</td>
                <td class="kanan sembunyi-hp">{{ angka(p.input) }}</td>
                <td class="kanan sembunyi-hp">{{ angka(p.cache_tulis) }}</td>
                <td class="kanan sembunyi-hp">{{ angka(p.cache_baca) }}</td>
                <td class="kanan sembunyi-hp">{{ angka(p.output) }}</td>
                <td class="kanan sembunyi-hp">{{ angka(p.panggilan) }}</td>
                <td class="kanan">{{ usd(p.biaya_usd) }}</td>
              </tr>
              <template v-if="terbuka(p)">
                <template v-for="a in barisAlur(p)" :key="p.id + a.kunci">
                  <tr v-if="a.kelompok && !a.label" class="baris-kelompok">
                    <td>{{ a.kelompok }}</td>
                    <td class="kanan">{{ angka(a.total) }}</td>
                    <td class="kanan sembunyi-hp">{{ persen(a.total, p) }}</td>
                    <td colspan="5" class="sembunyi-hp" /><td />
                  </tr>
                  <tr v-else class="baris-alur">
                    <td>
                      {{ a.label }}<template v-if="a.judul"> · <span class="redup">{{ a.judul }}</span></template>
                      <span v-if="a.gagal" class="lencana merah" :title="`${a.gagal} catatan gagal`">{{ a.gagal }} gagal</span>
                      <span v-if="a.parsial" class="lencana kuning" title="Proses terhenti sebelum selesai: token terhitung dari langkah yang sudah jalan, biaya tidak diketahui">{{ a.parsial }} parsial</span>
                      <span class="kecil">{{ a.model.join(', ') }} · terakhir {{ tanggalWaktu(a.terakhir) }}</span>
                    </td>
                    <td class="kanan">{{ angka(a.total) }}</td>
                    <td class="kanan redup sembunyi-hp">{{ persen(a.total, p) }}</td>
                    <td class="kanan sembunyi-hp">{{ angka(a.input) }}</td>
                    <td class="kanan sembunyi-hp">{{ angka(a.cache_tulis) }}</td>
                    <td class="kanan sembunyi-hp">{{ angka(a.cache_baca) }}</td>
                    <td class="kanan sembunyi-hp">{{ angka(a.output) }}</td>
                    <td class="kanan sembunyi-hp">{{ angka(a.panggilan) }}</td>
                    <td class="kanan">{{ usd(a.biaya_usd) }}</td>
                  </tr>
                </template>
              </template>
            </template>
          </tbody>
        </table>
      </div>
      <p class="redup catatan">
        Biaya hanya tercatat untuk Claude (setara harga API); model gateway tampil "–". Pemakaian di luar project
        (bot, agen internal, laporan) tidak dihitung di sini<template v-if="data"> ({{ angka(data.di_luar_project.total) }} token)</template>. Sesi Claude manual (terminal, bot) belum termasuk, jadi total project yang juga dikerjakan manual bisa lebih besar.
      </p>
    </section>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; min-width: 0; }
.saring { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr); gap: 10px; margin-bottom: 14px; }
.ringkas { margin: 0 0 10px; }
.ringkas b { color: var(--teks); }
.tabel th, .tabel td { padding-left: 5px; padding-right: 5px; font-size: 13px; }
.tabel th:first-child, .tabel td:first-child { width: 26%; min-width: 150px; }
.buka > span:last-child { min-width: 0; }
.kanan { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.buka { all: unset; display: flex; gap: 8px; cursor: pointer; }
.buka:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 2px; }
.panah { color: var(--teks-3); width: 12px; flex: none; }
.baris-proyek.terbuka td { background: var(--kartu-2); }
.baris-kelompok td { font-size: 12px; font-weight: 700; color: var(--teks-2); padding-top: 12px; padding-bottom: 4px; padding-left: 30px; }
.baris-kelompok td.kanan { padding-left: 10px; }
.baris-alur td:first-child { padding-left: 30px; }
.catatan { margin: 12px 0 0; }
@media (max-width: 760px) {
  .saring { grid-template-columns: minmax(0, 1fr); }
  .sembunyi-hp { display: none; }
}
</style>
