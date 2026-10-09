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
// Langkah di bagan alur installer (web/installer/alur.js) yang kini memenuhi aturan tsb.
// Aturan baru di scripts/audit-susulan (ATURAN) → tambahkan juga di sini.
const LANGKAH = {
  referensi_form_terlewat: 'Baca referensi',
  kredit_footer_tidak_ada: 'Finishing',
  statistik_footer_tidak_ada: 'Tema FSE · Tampilan tema klasik',
  sosmed_footer_tidak_ada: 'Tema FSE · Tampilan tema klasik',
  seo_dasar_kosong: 'Finishing',
  artikel_tanpa_foto_utama: 'Foto utama artikel',
  foto_utama_tanpa_caption: 'Foto utama artikel',
  kontak_biodata_tampil: 'Konten AI · Finishing',
  teks_catatan_ai: 'Konten AI',
  judul_ganda: 'Halaman blok & menu · Tampilan tema klasik',
  favicon_belum_terpasang: 'Finishing',
  halaman_privasi_tidak_ada: 'Finishing',
  halaman_privasi_belum_terbit: 'Finishing',
  tema_bukan_fse: 'Tema FSE',
}
const langkah = (kode) => LANGKAH[kodeInti(kode)] || ''
const ringkas = computed(() => {
  const h = {}
  for (const s of data.value?.situs || []) for (const a of s.aturan_baru) {
    const k = kodeInti(a.kode)
    h[k] ||= { n: 0, arti: a.arti }
    h[k].n++
  }
  return Object.entries(h).sort((a, b) => b[1].n - a[1].n)
})
const lebar = (n) => `${Math.max(2, (n / (data.value?.jumlah || 1)) * 100)}%`
const baris = computed(() => (data.value?.situs || []).filter((s) => !saring.value || s.aturan_baru.some((a) => kodeInti(a.kode) === saring.value)))
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Susulan aturan</h1>
        <p class="redup">Situs jadi yang belum ikut aturan terbaru. Perbaikan diputuskan manusia, karena sebagian situs sedang dikerjakan webmaster.</p>
      </div>
      <RouterLink to="/installer/wordpress" class="tombol garis">Kembali ke Installer</RouterLink>
    </header>

    <p v-if="galat" class="pesan-status bahaya" role="alert">{{ galat }}</p>
    <p v-else-if="!data" class="redup">Memuat…</p>
    <template v-else>
      <p class="pesan-status">
        <template v-if="data.waktu"><b>{{ data.perlu_susulan }}</b> dari {{ data.jumlah }} situs perlu susulan · diperiksa {{ tanggalWaktu(data.waktu) }}</template>
        <template v-else>Belum ada laporan. Jalankan <code>scripts/audit-susulan</code>.</template>
      </p>
      <section v-if="ringkas.length" class="kartu">
        <div class="judul-batang">
          <h2>Situs yang belum ikut, per aturan</h2>
          <span class="redup">panjang batang = bagian dari {{ data.jumlah }} situs · klik untuk menyaring tabel</span>
        </div>
        <div class="batang-daftar" role="group" aria-label="Saring menurut aturan">
          <button v-for="[k, v] in ringkas" :key="k" type="button" class="batang" :aria-pressed="saring === k" @click="saring = saring === k ? '' : k">
            <span class="batang-label">{{ v.arti }}<small v-if="LANGKAH[k]">Langkah installer: {{ LANGKAH[k] }}</small></span>
            <span class="batang-jalur"><i :style="{ width: lebar(v.n) }"></i></span>
            <b class="batang-n">{{ v.n }}</b>
          </button>
        </div>
      </section>
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
                    <li v-for="a in s.aturan_baru" :key="a.kode" :title="a.kode">{{ a.arti }}<span v-if="a.kode.includes(':')" class="redup"> ({{ a.kode.split(':').slice(1).join(':') }})</span><span v-if="langkah(a.kode)" class="langkah">{{ langkah(a.kode) }}</span></li>
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
.judul-batang { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 4px 12px; margin-bottom: 10px; }
.judul-batang h2 { margin: 0; font-size: 15px; }
.batang-daftar { display: grid; gap: 2px; }
.batang { display: grid; grid-template-columns: minmax(0, 20rem) minmax(0, 1fr) 2.5rem; align-items: center; gap: 12px; width: 100%; padding: 7px 10px; border: 1px solid transparent; border-radius: 10px; background: none; color: var(--teks-2); font: inherit; font-size: 13px; text-align: left; cursor: pointer; }
.batang:hover { background: var(--kartu-2); }
.batang[aria-pressed="true"] { background: var(--aksen-lembut); border-color: var(--aksen); color: var(--teks); }
.batang-label small { display: block; color: var(--teks-3); font-size: 11.5px; }
.batang-jalur { height: 10px; }
.batang-jalur i { display: block; height: 100%; border-radius: 0 4px 4px 0; background: var(--aksen-terang); }
.batang-n { text-align: right; color: var(--teks); font-variant-numeric: tabular-nums; }
.langkah { display: inline-block; margin-left: 6px; padding: 0 6px; border-radius: 6px; background: var(--kartu-2); color: var(--teks-3); font-size: 11px; white-space: nowrap; }
@media (max-width: 640px) {
  .batang { grid-template-columns: minmax(0, 1fr) 2.5rem; gap: 4px 10px; }
  .batang-label { grid-column: 1 / -1; }
}
ul { margin: 0; padding-left: 18px; }
li { margin: 2px 0; }
.lain { max-width: 300px; color: var(--teks-3); font-size: 12.5px; overflow-wrap: anywhere; }
td a b { color: var(--teks); }
</style>
