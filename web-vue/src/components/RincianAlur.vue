<script setup>
// Rincian satu poin alur di /token/proyek: komposisi token, run, dan bagian run yang paling makan token.
// Data: GET /api/ai/token-proyek/rincian (scripts/token_alur.py rincian_alur), dimuat saat panel dibuka.
// Bagian per alat hanya ada untuk run agen sejak 5 Nov 2026 (catat_claude.HitungUsage.rincian).
import { ref, computed, onMounted } from 'vue'
import { minta, angka, tanggalWaktu } from '../api.js'
import BilahTahap from './BilahTahap.vue'
import { persenTahap } from '../tahapToken.js'

const props = defineProps({
  proyek: { type: String, required: true },
  alur: { type: Object, required: true }, // baris alur dari /api/ai/token-proyek
})

const ringkasAngka = new Intl.NumberFormat('id-ID', { notation: 'compact', maximumFractionDigits: 1 })
const pendek = (n) => ringkasAngka.format(n || 0)
const usd = (n) => (n ? (n < 0.01 ? '<$0.01' : `$${n.toFixed(2)}`) : '–')

const data = ref(null)
const galat = ref('')
const muat = async () => {
  galat.value = ''
  try {
    data.value = await minta(`/api/ai/token-proyek/rincian?id=${encodeURIComponent(props.proyek)}&kunci=${encodeURIComponent(props.alur.kunci)}`)
  } catch (e) {
    galat.value = 'Rincian belum bisa dimuat.'
  }
}
onMounted(muat)

// Komposisi memakai angka riwayat penuh dari endpoint rincian (sama dengan baris alur bila tanpa saringan tanggal)
const sumber = computed(() => data.value?.total || props.alur)
const KOMPOSISI = [
  ['cache_baca', 'Cache baca', 'Konteks yang sama dibaca ulang di tiap giliran'],
  ['cache_tulis', 'Cache tulis', 'Konteks baru yang disimpan ke cache (hasil alat, berkas yang dibaca)'],
  ['input', 'Input', 'Input di luar cache'],
  ['output', 'Output', 'Yang ditulis model: jawaban, kode, perintah'],
]
const komposisi = computed(() => KOMPOSISI.map(([k, label, ket], i) => ({
  kunci: k, label, ket, total: sumber.value[k] || 0, warna: `var(--seri-${i + 1})`, alur: [],
})))
const totalKomposisi = computed(() => komposisi.value.reduce((n, t) => n + t.total, 0))
const porsiBaca = computed(() => (totalKomposisi.value ? sumber.value.cache_baca / totalKomposisi.value : 0))

const jumlahRun = computed(() => data.value?.jumlah_run || 0)
const giliran = computed(() => data.value?.total.giliran || 0)
const kesimpulan = computed(() => {
  const d = data.value
  if (!d || !jumlahRun.value) return ''
  const bagian = []
  if (porsiBaca.value >= 0.7) {
    bagian.push(`${persenTahap(sumber.value.cache_baca, totalKomposisi.value)} token adalah cache baca: konteks yang sama dibaca ulang di setiap giliran, jadi biayanya naik mengikuti jumlah giliran dan besarnya konteks.`)
  }
  if (jumlahRun.value > 1) {
    const besar = d.run_terbesar
    bagian.push(`Poin ini dijalankan ${angka(jumlahRun.value)} kali${sumber.value.gagal ? `, ${angka(sumber.value.gagal)} di antaranya gagal` : ''}; run terbesar ${pendek(besar.total)} (${persenTahap(besar.total, d.total.total)}).`)
  }
  const alat = Object.entries(d.alat)[0]
  if (alat && d.berinci.total) bagian.push(`Bagian terbesar di run yang terekam: ${alat[0]} (${persenTahap(alat[1].beban, d.berinci.total)}).`)
  return bagian.join(' ')
})

// Bagian run yang makan token (gabungan run berinci). Beban = tambahan konteks × giliran sesudahnya yang ikut membacanya.
const NAMA_ALAT = {
  'Konteks awal': 'Instruksi, system prompt & daftar alat yang dibaca di setiap giliran',
  'Teks agen': 'Teks penjelasan agen di antara langkah',
  Subagen: 'Token yang dipakai subagen (Agent)',
  Read: 'Hasil membaca berkas atau gambar',
}
const ketAlat = (n) => NAMA_ALAT[n] || (n.startsWith('Bash: ') ? 'Keluaran perintah ini' : 'Hasil alat ini')
const alat = computed(() => {
  const d = data.value
  if (!d?.berinci.run) return []
  const daftar = Object.entries(d.alat).map(([nama, a]) => ({ nama, ...a }))
  const atas = daftar.slice(0, 8)
  const sisa = daftar.slice(8)
  if (sisa.length) atas.push({ nama: `${sisa.length} bagian lain`, n: sisa.reduce((s, a) => s + a.n, 0), beban: sisa.reduce((s, a) => s + a.beban, 0), tambah: 0, lain: true })
  const maks = Math.max(1, ...atas.map((a) => a.beban))
  return atas.map((a) => ({ ...a, lebar: a.beban / maks * 100 }))
})
const outputBerinci = computed(() => data.value?.berinci.output || 0)

const runBuka = ref(new Set())
const alihRun = (ts) => {
  const s = new Set(runBuka.value)
  if (s.has(ts)) s.delete(ts)
  else s.add(ts)
  runBuka.value = s
}
const statusRun = (r) => (r.parsial ? 'terputus' : r.gagal ? 'gagal' : '')
</script>

<template>
  <div class="rincian-alur">
    <p v-if="galat" class="galat">{{ galat }} <button type="button" class="tombol garis kecil" @click="muat">Coba lagi</button></p>
    <p v-else-if="!data" class="redup">Memuat rincian…</p>
    <template v-else>
      <div class="kisi">
        <section aria-label="Komposisi token">
          <h4>Komposisi token</h4>
          <BilahTahap :tahap="komposisi" :format="pendek" :judul="`Komposisi token ${alur.label}`" />
          <dl class="angka-run">
            <div><dt>Run</dt><dd>{{ angka(jumlahRun) }}</dd></div>
            <div><dt>Giliran</dt><dd>{{ giliran ? angka(giliran) : '–' }}</dd></div>
            <div><dt>Rata-rata per run</dt><dd>{{ jumlahRun ? pendek(data.total.total / jumlahRun) : '–' }}</dd></div>
            <div><dt>Rata-rata per giliran</dt><dd>{{ giliran ? pendek(data.total.total / giliran) : '–' }}</dd></div>
          </dl>
          <p v-if="kesimpulan" class="kesimpulan">{{ kesimpulan }}</p>
        </section>

        <section aria-label="Bagian yang paling makan token">
          <h4>Bagian yang paling makan token</h4>
          <template v-if="alat.length">
            <ul class="daftar-alat">
              <li v-for="a in alat" :key="a.nama" :title="a.lain ? '' : `${ketAlat(a.nama)}. Menambah ±${angka(a.tambah)} token konteks, lalu dibaca ulang di giliran sesudahnya.`">
                <span class="nama">{{ a.nama }}<small v-if="a.n" class="redup"> · {{ angka(a.n) }}×</small></span>
                <span class="batang" aria-hidden="true"><i :style="{ width: `${a.lebar}%` }" /></span>
                <b>{{ persenTahap(a.beban, data.berinci.total) }}</b>
                <small class="redup">{{ pendek(a.beban) }}</small>
              </li>
              <li v-if="outputBerinci" title="Yang ditulis model: jawaban, kode, perintah">
                <span class="nama">Output model</span>
                <span class="batang" aria-hidden="true"><i :style="{ width: `${Math.min(100, outputBerinci / Math.max(1, alat[0].beban) * 100)}%` }" /></span>
                <b>{{ persenTahap(outputBerinci, data.berinci.total) }}</b>
                <small class="redup">{{ pendek(outputBerinci) }}</small>
              </li>
            </ul>
            <p class="ket redup">
              Dari {{ angka(data.berinci.run) }} run yang terekam rinciannya<template v-if="data.berinci.run < jumlahRun"> (dari {{ angka(jumlahRun) }} run)</template>.
              Hasil alat yang masuk ke konteks ikut dibaca ulang di setiap giliran sesudahnya, jadi angkanya = ukuran hasil × giliran yang membacanya. Alat yang dipanggil bersamaan dalam satu giliran berbagi angka sama rata, jadi porsinya perkiraan.
              Konteks awal {{ pendek(data.berinci.konteks_awal / data.berinci.run) }}, membesar sampai {{ pendek(data.berinci.konteks_akhir / data.berinci.run) }} per run (rata-rata).
            </p>
          </template>
          <p v-else class="ket redup">
            Rincian per alat (baca berkas, perintah, screenshot) mulai terekam untuk run agen sejak 5 Nov 2026.
            {{ jumlahRun ? 'Run di poin ini lebih lama dari itu, jadi baru angka totalnya yang tersedia.' : '' }}
            Alur non-agen (konten, baca form, dan sejenisnya) adalah panggilan tunggal tanpa alat, jadi rinciannya cukup komposisi di samping.
          </p>
        </section>
      </div>

      <section v-if="data.run.length" class="daftar-run" aria-label="Daftar run">
        <h4>Run <span class="redup">({{ jumlahRun > data.run.length ? `${angka(data.run.length)} terbaru dari ${angka(jumlahRun)}` : angka(jumlahRun) }})</span></h4>
        <table class="tabel-run">
          <thead><tr><th>Waktu</th><th class="kanan">Giliran</th><th class="kanan">Token</th><th class="kanan sembunyi-hp">Cache baca</th><th class="kanan">Biaya</th></tr></thead>
          <tbody>
            <template v-for="r in data.run" :key="r.ts">
              <tr :class="{ terbesar: data.run_terbesar && r.ts === data.run_terbesar.ts && jumlahRun > 1 }">
                <td>
                  <button v-if="r.rincian" type="button" class="buka-run" :aria-expanded="runBuka.has(r.ts)" @click="alihRun(r.ts)">
                    <span aria-hidden="true">{{ runBuka.has(r.ts) ? '▾' : '▸' }}</span> {{ tanggalWaktu(r.ts) }}
                  </button>
                  <span v-else>{{ tanggalWaktu(r.ts) }}</span>
                  <span v-if="statusRun(r)" class="lencana" :class="r.parsial ? 'kuning' : 'merah'">{{ statusRun(r) }}</span>
                </td>
                <td class="kanan">{{ r.giliran || '–' }}</td>
                <td class="kanan" :title="angka(r.total)"><b>{{ pendek(r.total) }}</b></td>
                <td class="kanan sembunyi-hp">{{ persenTahap(r.cache_baca, r.total) }}</td>
                <td class="kanan">{{ usd(r.biaya_usd) }}</td>
              </tr>
              <tr v-if="r.rincian && runBuka.has(r.ts)" class="baris-giliran">
                <td colspan="5">
                  <p class="redup">Giliran yang paling membebani run ini (konteks awal {{ pendek(r.rincian.konteks_awal) }} → akhir {{ pendek(r.rincian.konteks_akhir) }}):</p>
                  <ol>
                    <li v-for="g in r.rincian.teratas" :key="g.giliran">
                      Giliran {{ g.giliran }}: <b>{{ g.alat }}</b><template v-if="g.isi">{{ " " }}<code>{{ g.isi }}</code></template>
                      <span class="redup"> · +{{ pendek(g.tambah) }} konteks · {{ pendek(g.beban) }} ({{ persenTahap(g.beban, r.total) }})</span>
                    </li>
                  </ol>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>

<style scoped>
.rincian-alur { container-type: inline-size; display: grid; gap: 14px; padding: 12px 14px 14px; border: 1px solid var(--garis); border-radius: 12px; background: var(--kartu); }
h4 { margin: 0 0 8px; font-size: 13px; font-weight: 600; color: var(--teks); }
.kisi { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; }
@container (max-width: 699px) { .kisi { grid-template-columns: minmax(0, 1fr); } }
.angka-run { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin: 12px 0 0; }
.angka-run div { min-width: 0; }
.angka-run dt { font-size: 11.5px; color: var(--teks-2); }
.angka-run dd { margin: 0; font-size: 15px; font-weight: 700; color: var(--teks); font-variant-numeric: tabular-nums; }
@container (max-width: 459px) { .angka-run { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.kesimpulan { margin: 10px 0 0; font-size: 12.5px; color: var(--teks-2); line-height: 1.5; }
.daftar-alat { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.daftar-alat li { display: grid; grid-template-columns: minmax(0, 11em) minmax(40px, 1fr) 3.6em 3.4em; align-items: center; gap: 8px; font-size: 12.5px; color: var(--teks-2); }
.daftar-alat .nama { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--teks); }
.daftar-alat b { text-align: right; color: var(--teks); font-variant-numeric: tabular-nums; }
.daftar-alat small { text-align: right; font-variant-numeric: tabular-nums; }
.batang { height: 8px; }
.batang i { display: block; height: 100%; min-width: 2px; border-radius: 0 4px 4px 0; background: var(--seri-1); }
.ket { margin: 10px 0 0; font-size: 12px; line-height: 1.5; }
.galat { margin: 0; color: var(--bahaya); font-size: 13px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.tabel-run { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tabel-run th { text-align: left; font-weight: 600; color: var(--teks-2); padding: 4px 6px; border-bottom: 1px solid var(--garis); }
.tabel-run td { padding: 5px 6px; border-bottom: 1px solid var(--garis); vertical-align: top; }
.tabel-run .kanan { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.tabel-run tr.terbesar td { background: var(--kartu-2); }
.buka-run { all: unset; cursor: pointer; }
.buka-run:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 2px; border-radius: 4px; }
.lencana { margin-left: 6px; }
.baris-giliran td { background: var(--kartu-2); }
.baris-giliran p { margin: 0 0 4px; font-size: 12px; }
.baris-giliran ol { margin: 0; padding-left: 18px; display: grid; gap: 3px; }
.baris-giliran code { font-size: 11.5px; overflow-wrap: anywhere; }
@container (max-width: 459px) { .sembunyi-hp { display: none; } }
</style>
