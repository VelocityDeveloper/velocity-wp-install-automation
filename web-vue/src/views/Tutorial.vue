<script setup>
// Statistik tutorial.velocitydeveloper.com: tutorial mana yang paling banyak dibuka.
// Pencatat di server tutorial (api/catat.php → SQLite), diambil lewat server_stats.py GET /api/tutorial?p= (cache 60 dtk).
import { ref, computed, watch } from 'vue'
import GrafikBatangTumpuk from '../components/GrafikBatangTumpuk.vue'
import { pakaiPolling, waktuLalu } from '../api.js'

const SITUS = 'https://tutorial.velocitydeveloper.com'
const RENTANG = [['1', 'Hari ini'], ['7', '7 hari'], ['30', '30 hari'], ['0', 'Semua']]
const rentang = ref('30')
const { data, galat, memuat, muatUlang } = pakaiPolling(() => `/api/tutorial?p=${rentang.value}`, 60000)
watch(rentang, muatUlang)

const angka = (n) => new Intl.NumberFormat('id-ID').format(n || 0)
const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
const HARI = ['Min', 'Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab']
const formatTanggal = (tgl, panjang) => {
  const d = new Date(tgl + 'T00:00:00Z')
  return `${panjang ? HARI[d.getUTCDay()] + ', ' : ''}${d.getUTCDate()} ${BULAN[d.getUTCMonth()]}${panjang === 'tahun' ? ' ' + d.getUTCFullYear() : ''}`
}

const stat = computed(() => {
  const t = data.value?.total || {}
  return [['Tayangan', t.tayangan], ['Pengunjung', t.pengunjung], ['Unduhan Word', t.unduh]]
})
const tutorial = computed(() => data.value?.tutorial || [])
const puncak = computed(() => Math.max(1, ...tutorial.value.map((t) => t.tayangan)))
const totalTayang = computed(() => data.value?.total?.tayangan || 0)

// Grafik 30 hari terakhir, hari tanpa kunjungan tetap tampil sebagai 0
const SERI = [{ kunci: 'tayangan', label: 'Tayangan', warna: '#5b8cff' }]
const hariGrafik = computed(() => {
  const ada = Object.fromEntries((data.value?.harian || []).map((h) => [h.tanggal, h.tayangan]))
  const hasil = []
  const sekarang = new Date(Date.now() + 7 * 3600e3) // tanggal WIB, sama dengan pencatat
  for (let i = 29; i >= 0; i--) {
    const tgl = new Date(sekarang - i * 86400e3).toISOString().slice(0, 10)
    hasil.push({ tgl, nilai: { tayangan: ada[tgl] || 0 } })
  }
  return hasil
})
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Statistik Tutorial</h1>
        <p class="redup">Tutorial yang paling banyak dibuka di <a :href="SITUS" target="_blank" rel="noopener">tutorial.velocitydeveloper.com</a>. Tanpa cookie, bot tidak dihitung.</p>
      </div>
      <span v-if="data?.dibuat" class="redup">Data {{ waktuLalu(data.dibuat) }}<template v-if="data.pertama"> · tercatat sejak {{ formatTanggal(data.pertama, 'tahun') }}</template></span>
    </header>

    <p v-if="galat || data?.galat" class="pesan-status bahaya" role="alert">
      {{ String(galat?.message || '').startsWith('403') ? 'Hanya bisa dibuka dari jaringan kantor atau Tailscale.' : `Data dari server tutorial tidak terbaca${data?.tutorial ? ', angka di bawah data terakhir' : ''}.` }}
    </p>

    <div class="segmen" role="radiogroup" aria-label="Rentang waktu">
      <button v-for="[k, l] in RENTANG" :key="k" type="button" role="radio" :aria-checked="rentang === k" :class="{ aktif: rentang === k }" @click="rentang = k">{{ l }}</button>
    </div>

    <section class="ringkas" aria-label="Ringkasan">
      <div v-for="[l, n] in stat" :key="l" class="kartu angka"><span class="redup">{{ l }}</span><b>{{ data ? angka(n) : '–' }}</b></div>
    </section>

    <section class="kartu" aria-labelledby="judul-peringkat">
      <div class="kartu-judul">
        <h2 id="judul-peringkat">Tutorial paling banyak dibuka</h2>
        <span class="redup">1 tayangan = 1 kali membuka tutorial</span>
      </div>
      <p v-if="memuat && !data" class="redup">Memuat…</p>
      <div v-else class="tabel-wadah">
        <table class="tabel">
          <thead><tr><th class="no">#</th><th>Tutorial</th><th class="kanan">Tayangan</th><th class="kanan">Porsi</th><th class="kanan sembunyi-hp">Pengunjung</th><th class="kanan sembunyi-hp">Unduh Word</th></tr></thead>
          <tbody>
            <tr v-for="(t, i) in tutorial" :key="t.slug" :class="{ nol: !t.tayangan }">
              <td class="no">{{ i + 1 }}</td>
              <td class="nama">
                <a :href="`${SITUS}/${t.slug}`" target="_blank" rel="noopener">{{ t.menu }}</a>
                <span v-if="t.kelompok" class="kecil">{{ t.kelompok }}</span>
                <div class="meter" aria-hidden="true"><i :style="{ width: `${(t.tayangan / puncak) * 100}%` }" /></div>
              </td>
              <td class="kanan tebal">{{ angka(t.tayangan) }}</td>
              <td class="kanan">{{ totalTayang ? Math.round((t.tayangan / totalTayang) * 100) : 0 }}%</td>
              <td class="kanan sembunyi-hp">{{ angka(t.pengunjung) }}</td>
              <td class="kanan sembunyi-hp">{{ angka(t.unduh) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="kartu" aria-labelledby="judul-harian">
      <div class="kartu-judul"><h2 id="judul-harian">Tayangan per hari</h2><span class="redup">30 hari terakhir</span></div>
      <GrafikBatangTumpuk v-if="data" :hari="hariGrafik" :seri="SERI" :format="angka" :format-tanggal="formatTanggal" />
    </section>

    <div class="dua">
      <section class="kartu" aria-labelledby="judul-bagian">
        <div class="kartu-judul"><h2 id="judul-bagian">Bagian yang dibuka langsung</h2></div>
        <p v-if="!data?.bagian?.length" class="redup">Belum ada. Muncul saat orang membuka tautan bagian, misalnya /login-wp-admin/lupa-sandi dari pesan WA.</p>
        <ul v-else class="daftar">
          <li v-for="b in data.bagian" :key="b.slug + b.bagian"><a :href="`${SITUS}/${b.slug}/${b.bagian}`" target="_blank" rel="noopener">/{{ b.slug }}/{{ b.bagian }}</a><b>{{ angka(b.n) }}</b></li>
        </ul>
      </section>
      <section class="kartu" aria-labelledby="judul-asal">
        <div class="kartu-judul"><h2 id="judul-asal">Asal & perangkat</h2></div>
        <p v-if="!data?.rujukan?.length" class="redup">Belum ada data.</p>
        <ul v-else class="daftar">
          <li v-for="r in data.rujukan" :key="r.r"><span>{{ r.r }}</span><b>{{ angka(r.n) }}</b></li>
          <li v-for="p in data.perangkat" :key="p.perangkat" class="redup-baris"><span>Perangkat: {{ p.perangkat }}</span><b>{{ angka(p.n) }}</b></li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; min-width: 0; }
.kepala-halaman a { color: var(--aksen-terang); }
.segmen { justify-self: start; display: inline-flex; padding: 3px; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--panel); }
.segmen button { border: 0; background: transparent; color: var(--teks-2); padding: 7px 14px; border-radius: 8px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.segmen button.aktif { background: var(--aksen); color: #fff; }
.segmen button:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
.ringkas { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.angka { display: grid; gap: 2px; padding: 14px 18px; }
.angka b { font-size: 26px; font-weight: 700; font-variant-numeric: tabular-nums; }
.tabel td, .tabel th { font-variant-numeric: tabular-nums; }
.kanan { text-align: right !important; }
.tebal { font-weight: 700; }
.no { width: 32px; color: var(--teks-3); }
.nama { min-width: 200px; }
.nama a { color: var(--teks); font-weight: 600; text-decoration: none; }
.nama a:hover { color: var(--aksen-terang); }
.nama .meter { margin-top: 8px; max-width: 360px; }
tr.nol .nama a, tr.nol td { color: var(--teks-3); }
.dua { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.daftar { list-style: none; margin: 0; padding: 0; }
.daftar li { display: flex; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--garis); font-size: 13.5px; }
.daftar li:last-child { border-bottom: 0; }
.daftar a { color: var(--aksen-terang); text-decoration: none; word-break: break-all; }
.daftar b { font-variant-numeric: tabular-nums; }
.redup-baris span { color: var(--teks-2); }
@media (max-width: 900px) {
  .dua { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
  .ringkas .angka:last-child { grid-column: span 2; }
  .sembunyi-hp { display: none; }
  .nama { min-width: 0; }
  .nama .meter { max-width: none; }
  .no { width: 20px; }
}
</style>
