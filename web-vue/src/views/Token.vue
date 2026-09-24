<script setup>
// Token Usage: pemakaian token Claude Code per orang (Telegram, desktop, terminal SSH, otomasi).
// Data dari timer claude-pakai (scripts/claude-pakai) tiap menit → /brain/token.json (hanya LAN/Tailscale).
import { ref, computed } from 'vue'
import { pakaiPolling, angka, tanggalWaktu, waktuLalu } from '../api.js'

const { data, galat } = pakaiPolling('/brain/token.json', 60000)

const RENTANG = [['1', 'Hari ini'], ['7', '7 hari'], ['30', '30 hari'], ['semua', 'Semua']]
const JALUR = { telegram: 'Telegram', desktop: 'Desktop', terminal: 'Terminal SSH', otomasi: 'Otomasi' }
const rentang = ref('7')
const jalur = ref('')
const buka = ref(null)

const ringkas = new Intl.NumberFormat('id-ID', { notation: 'compact', maximumFractionDigits: 1 })
const pendek = (n) => ringkas.format(n || 0)

// Tanggal WIB (YYYY-MM-DD) paling awal yang masuk rentang
const batas = computed(() => {
  if (rentang.value === 'semua') return ''
  const wib = new Date(Date.now() + 7 * 3600e3)
  wib.setUTCDate(wib.getUTCDate() - (Number(rentang.value) - 1))
  return wib.toISOString().slice(0, 10)
})

const nol = () => ({ input: 0, tulis: 0, baca: 0, output: 0, panggilan: 0 })
function tambah(t, v) { t.input += v[0]; t.tulis += v[1]; t.baca += v[2]; t.output += v[3]; t.panggilan += v[4] }
const total = (t) => t.input + t.tulis + t.baca + t.output

// Per orang: jumlah dalam rentang + rincian per jalur, per model, per sesi
const orang = computed(() => {
  const hasil = []
  for (const o of data.value?.pengguna || []) {
    const t = nol(), perJalur = {}, perModel = {}, sesi = []
    for (const s of o.sesi) {
      if (jalur.value && s.jalur !== jalur.value) continue
      const ts = nol()
      for (const [tgl, pm] of Object.entries(s.hari)) {
        if (tgl < batas.value) continue
        for (const [model, v] of Object.entries(pm)) {
          tambah(ts, v)
          tambah(perModel[model] ||= nol(), v)
        }
      }
      if (!ts.panggilan) continue
      for (const k of Object.keys(t)) { t[k] += ts[k]; (perJalur[s.jalur] ||= nol())[k] += ts[k] }
      sesi.push({ ...s, t: ts })
    }
    if (!t.panggilan) continue
    sesi.sort((a, b) => (b.akhir || 0) - (a.akhir || 0))
    hasil.push({ nama: o.nama, t, sesi, perJalur, perModel, teridentifikasi: !/^(Belum teridentifikasi|Otomasi|SSH password)/.test(o.nama) })
  }
  return hasil.sort((a, b) => total(b.t) - total(a.t))
})

const semua = computed(() => orang.value.reduce((a, o) => { for (const k of Object.keys(a)) a[k] += o.t[k]; return a }, nol()))
const terbesar = computed(() => Math.max(1, ...orang.value.map((o) => total(o.t))))
const stat = computed(() => [
  ['Total token', data.value ? pendek(total(semua.value)) : null, angka(total(semua.value))],
  ['Output', data.value ? pendek(semua.value.output) : null, angka(semua.value.output)],
  ['Panggilan model', data.value ? angka(semua.value.panggilan) : null, ''],
  ['Orang / sumber', data.value ? angka(orang.value.length) : null, ''],
])
const namaModel = (m) => m.replace(/^claude-/, '').replace(/-\d{8}$/, '')
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Token Usage</h1>
        <p class="redup">Pemakaian token Claude Code per orang, dari transkrip sesi di Local PC. Diperbarui tiap menit.</p>
      </div>
      <span v-if="data" class="redup">Data {{ waktuLalu(data.dibuat) }}</span>
    </header>

    <p v-if="galat" class="pesan-status bahaya" role="alert">
      Data token tidak terbaca{{ String(galat.message).startsWith('403') ? ': hanya bisa dibuka dari jaringan kantor atau Tailscale.' : '.' }}
    </p>

    <div class="saring" role="group" aria-label="Saring">
      <div class="segmen" role="radiogroup" aria-label="Rentang waktu">
        <button v-for="[k, l] in RENTANG" :key="k" type="button" role="radio" :aria-checked="rentang === k" :class="{ aktif: rentang === k }" @click="rentang = k">{{ l }}</button>
      </div>
      <select v-model="jalur" aria-label="Saring jalur">
        <option value="">Semua jalur</option>
        <option v-for="(l, k) in JALUR" :key="k" :value="k">{{ l }}</option>
      </select>
    </div>

    <section class="ringkas" aria-label="Ringkasan">
      <div v-for="[l, n, penuh] in stat" :key="l" class="kartu angka" :title="penuh || null"><span class="redup">{{ l }}</span><b>{{ n == null ? '–' : n }}</b></div>
    </section>

    <section class="kartu">
      <div class="kartu-judul"><h2>Per orang</h2><span class="redup">klik baris untuk rincian</span></div>
      <div class="tabel-wadah">
        <table class="tabel">
          <thead>
            <tr>
              <th>Orang</th><th class="kanan">Total</th><th class="sembunyi-hp kanan">Input + cache tulis</th>
              <th class="sembunyi-hp kanan">Cache baca</th><th class="kanan">Output</th><th class="sembunyi-hp kanan">Sesi</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!data && !galat"><td colspan="6" class="redup">Memuat…</td></tr>
            <tr v-else-if="data && !orang.length"><td colspan="6" class="redup">Tidak ada pemakaian di rentang ini.</td></tr>
            <template v-for="o in orang" :key="o.nama">
              <tr class="baris" :class="{ terbuka: buka === o.nama }" tabindex="0" :aria-expanded="buka === o.nama"
                  @click="buka = buka === o.nama ? null : o.nama" @keydown.enter.prevent="buka = buka === o.nama ? null : o.nama">
                <td>
                  <b :class="{ redup: !o.teridentifikasi }">{{ o.nama }}</b>
                  <span class="kecil">{{ Object.keys(o.perJalur).map((j) => JALUR[j]).join(' · ') }}</span>
                  <div class="meter" :title="`${Math.round(total(o.t) / total(semua) * 100)}% dari total`"><i :style="{ width: `${total(o.t) / terbesar * 100}%` }" /></div>
                </td>
                <td class="kanan" :title="angka(total(o.t))"><b>{{ pendek(total(o.t)) }}</b></td>
                <td class="sembunyi-hp kanan" :title="angka(o.t.input + o.t.tulis)">{{ pendek(o.t.input + o.t.tulis) }}</td>
                <td class="sembunyi-hp kanan" :title="angka(o.t.baca)">{{ pendek(o.t.baca) }}</td>
                <td class="kanan" :title="angka(o.t.output)">{{ pendek(o.t.output) }}</td>
                <td class="sembunyi-hp kanan">{{ o.sesi.length }}</td>
              </tr>
              <tr v-if="buka === o.nama" class="rinci">
                <td colspan="6">
                  <div class="rinci-isi">
                    <div>
                      <h3>Per jalur</h3>
                      <ul class="daftar">
                        <li v-for="(t, j) in o.perJalur" :key="j"><span>{{ JALUR[j] }}</span><b :title="angka(total(t))">{{ pendek(total(t)) }}</b></li>
                      </ul>
                      <h3>Per model</h3>
                      <ul class="daftar">
                        <li v-for="(t, m) in o.perModel" :key="m"><span>{{ namaModel(m) }}</span><b :title="angka(total(t))">{{ pendek(total(t)) }}</b></li>
                      </ul>
                    </div>
                    <div>
                      <h3>Sesi ({{ o.sesi.length }})</h3>
                      <ul class="sesi">
                        <li v-for="s in o.sesi.slice(0, 30)" :key="s.sid">
                          <div><span class="judul-sesi">{{ s.judul || '(tanpa judul)' }}</span>
                            <span class="kecil">{{ JALUR[s.jalur] }} · {{ s.asal }} · {{ tanggalWaktu(s.akhir) }} · <code>{{ s.sid.slice(0, 8) }}</code></span></div>
                          <b :title="angka(total(s.t))">{{ pendek(total(s.t)) }}</b>
                        </li>
                      </ul>
                      <p v-if="o.sesi.length > 30" class="redup">+{{ o.sesi.length - 30 }} sesi lain</p>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <section class="kartu catatan">
      <h2>Cara membaca</h2>
      <ul>
        <li><b>Cache baca</b> paling besar tapi paling murah: konteks yang dipakai ulang tiap panggilan. <b>Input + cache tulis</b> dan <b>output</b> yang paling berat untuk kuota.</li>
        <li><b>Telegram</b> dikenali dari ID chat. <b>Desktop dan terminal</b> dikenali dari kunci SSH yang dipakai login<template v-if="data?.pencatat_sejak">, dicatat sejak {{ tanggalWaktu(data.pencatat_sejak) }}</template>. Sesi sebelumnya masuk "Belum teridentifikasi".</li>
        <li>Login SSH pakai <b>password</b> hanya bisa dikenali lewat IP. Nama untuk IP atau ID Telegram bisa ditambahkan di <code>/var/lib/velocity/claude-pakai/pengguna.json</code>.</li>
        <li>Semua orang memakai satu akun Claude, jadi angka ini dihitung dari transkrip lokal, bukan dari tagihan Anthropic.</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; min-width: 0; }
.ringkas { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.angka { display: grid; gap: 2px; padding: 14px 18px; }
.angka b { font-size: 26px; font-weight: 700; }
.saring { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.saring select { width: auto; min-width: 170px; }
.segmen { display: inline-flex; padding: 3px; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--panel); }
.segmen button { border: 0; background: transparent; color: var(--teks-2); padding: 7px 14px; border-radius: 8px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.segmen button.aktif { background: var(--aksen); color: #fff; }
.segmen button:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
.kanan { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.baris { cursor: pointer; }
.baris:hover td, .baris.terbuka td { background: var(--kartu-2); }
.baris:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: -2px; }
.baris .meter { margin-top: 8px; max-width: 260px; }
.rinci td { background: var(--panel); }
.rinci-isi { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: 24px; padding: 6px 4px; }
.rinci h3 { font-size: 12.5px; color: var(--teks-3); font-weight: 600; margin: 0 0 8px; }
.rinci h3:not(:first-child) { margin-top: 16px; }
.daftar, .sesi { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.daftar li, .sesi li { display: flex; justify-content: space-between; gap: 12px; }
.sesi li { padding-bottom: 6px; border-bottom: 1px solid var(--garis); }
.sesi li:last-child { border-bottom: 0; }
.sesi b, .daftar b { font-variant-numeric: tabular-nums; white-space: nowrap; }
.judul-sesi { overflow-wrap: anywhere; }
.catatan h2 { font-size: 15px; margin-bottom: 8px; }
.catatan ul { margin: 0; padding-left: 18px; display: grid; gap: 6px; color: var(--teks-2); font-size: 13.5px; }
@media (max-width: 900px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
  .rinci-isi { grid-template-columns: minmax(0, 1fr); }
}
</style>
