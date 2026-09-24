<script setup>
// Token Usage: pemakaian token Claude Code per orang (Telegram, desktop, terminal SSH, otomasi).
// Data dari timer claude-pakai (scripts/claude-pakai) tiap menit → /brain/token.json (hanya LAN/Tailscale).
import { ref, computed } from 'vue'
import { pakaiPolling, angka, tanggalWaktu, waktuLalu } from '../api.js'
import GrafikBatangTumpuk from '../components/GrafikBatangTumpuk.vue'

const { data, galat } = pakaiPolling('/brain/token.json', 60000)

const RENTANG = [['1', 'Hari ini'], ['7', '7 hari'], ['30', '30 hari'], ['semua', 'Semua']]
const JALUR = { telegram: 'Telegram', desktop: 'Desktop', terminal: 'Terminal SSH', otomasi: 'Otomasi' }
const rentang = ref('7')
const jalur = ref('')
const model = ref('')
const cari = ref('')
const jenis = ref('')
const buka = ref(null)
// Urutan tabel: kolom + arah; klik judul kolom yang sama membalik arah
const urut = ref({ kolom: 'total', naik: false })

// Jenis penggunaan: label dari token.json, warna tetap per jenis (palet kategori, lolos cek
// buta warna di latar kartu #151a33); "Lainnya" abu netral. Warna ikut jenis, bukan peringkat.
const WARNA_JENIS = {
  installer: '#3987e5', buat_web: '#d95926', revisi_web: '#199e70', pengembangan: '#c98500',
  chat_cs: '#d55181', server: '#008300', tanya: '#9085e9', lainnya: '#6b7194',
}
const daftarJenis = computed(() => (data.value?.jenis || []).map(([kunci, label]) => ({ kunci, label, warna: WARNA_JENIS[kunci] || '#6b7194' })))
const labelJenis = (k) => daftarJenis.value.find((j) => j.kunci === k)?.label || k || 'Lainnya'
// Tanda sesi boros: konteks rata-rata per panggilan besar (sesi terlalu panjang, belum /clear
// atau sesi baru) dan sesi yang terus jalan lebih dari sehari.
const KONTEKS_BESAR = 300e3
const SESI_BESAR = 100e6

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

const KOLOM = {
  nama: (o) => o.nama.toLowerCase(),
  total: (o) => total(o.t),
  masuk: (o) => o.t.input + o.t.tulis,
  baca: (o) => o.t.baca,
  output: (o) => o.t.output,
  sesi: (o) => o.sesi.length,
}
function urutkan(kolom) {
  urut.value = urut.value.kolom === kolom ? { kolom, naik: !urut.value.naik } : { kolom, naik: kolom === 'nama' }
}
const ariaUrut = (kolom) => urut.value.kolom === kolom ? (urut.value.naik ? 'ascending' : 'descending') : 'none'

// Model yang pernah dipakai, untuk pilihan saring
const daftarModel = computed(() => {
  const m = new Set()
  for (const o of data.value?.pengguna || []) for (const s of o.sesi) for (const pm of Object.values(s.hari)) for (const k of Object.keys(pm)) m.add(k)
  return [...m].sort()
})

// Per orang: jumlah dalam rentang + rincian per jalur, per model, per sesi
const orang = computed(() => {
  const hasil = [], q = cari.value.trim().toLowerCase()
  for (const o of data.value?.pengguna || []) {
    if (q && !o.nama.toLowerCase().includes(q)) continue
    const t = nol(), perJalur = {}, perModel = {}, perJenis = {}, sesi = []
    for (const s of o.sesi) {
      if (jalur.value && s.jalur !== jalur.value) continue
      if (jenis.value && (s.jenis || 'lainnya') !== jenis.value) continue
      const ts = nol()
      for (const [tgl, pm] of Object.entries(s.hari)) {
        if (tgl < batas.value) continue
        for (const [m, v] of Object.entries(pm)) {
          if (model.value && m !== model.value) continue
          tambah(ts, v)
          tambah(perModel[m] ||= nol(), v)
        }
      }
      if (!ts.panggilan) continue
      for (const k of Object.keys(t)) { t[k] += ts[k]; (perJalur[s.jalur] ||= nol())[k] += ts[k]; (perJenis[s.jenis || 'lainnya'] ||= nol())[k] += ts[k] }
      sesi.push({ ...s, t: ts })
    }
    if (!t.panggilan) continue
    sesi.sort((a, b) => (b.akhir || 0) - (a.akhir || 0))
    hasil.push({ nama: o.nama, t, sesi, perJalur, perModel, perJenis, teridentifikasi: !/^(Belum teridentifikasi|Otomasi|SSH password)/.test(o.nama) })
  }
  const nilai = KOLOM[urut.value.kolom], arah = urut.value.naik ? 1 : -1
  return hasil.sort((a, b) => {
    const x = nilai(a), y = nilai(b)
    return (x < y ? -1 : x > y ? 1 : 0) * arah || total(b.t) - total(a.t)
  })
})

// Per jenis (dalam rentang & saringan): jumlah, persen, sesi
const perJenis = computed(() => {
  const m = {}
  for (const o of orang.value) for (const s of o.sesi) {
    const r = (m[s.jenis || 'lainnya'] ||= { t: nol(), sesi: 0 })
    tambah(r.t, [s.t.input, s.t.tulis, s.t.baca, s.t.output, s.t.panggilan]); r.sesi++
  }
  const semuaT = Math.max(1, total(semua.value))
  return daftarJenis.value.filter((j) => m[j.kunci]).map((j) => ({ ...j, ...m[j.kunci], persen: total(m[j.kunci].t) / semuaT * 100 }))
})

// Token per hari per jenis. "Hari ini" tetap memperlihatkan 14 hari supaya ada pembanding.
const hariGrafik = computed(() => {
  const per = {}
  for (const o of data.value?.pengguna || []) {
    if (cari.value.trim() && !o.nama.toLowerCase().includes(cari.value.trim().toLowerCase())) continue
    for (const s of o.sesi) {
      if (jalur.value && s.jalur !== jalur.value) continue
      if (jenis.value && (s.jenis || 'lainnya') !== jenis.value) continue
      for (const [tgl, pm] of Object.entries(s.hari)) for (const [m, v] of Object.entries(pm)) {
        if (model.value && m !== model.value) continue
        const h = (per[tgl] ||= {})
        h[s.jenis || 'lainnya'] = (h[s.jenis || 'lainnya'] || 0) + v[0] + v[1] + v[2] + v[3]
      }
    }
  }
  const tgl = Object.keys(per).sort()
  if (!tgl.length) return []
  const n = rentang.value === 'semua' ? null : Math.max(14, Number(rentang.value))
  const akhir = new Date(Date.now() + 7 * 3600e3)
  const mulai = n ? new Date(akhir.getTime() - (n - 1) * 86400e3) : new Date(tgl[0] + 'T00:00:00Z')
  const hasil = []
  for (let d = new Date(mulai.toISOString().slice(0, 10) + 'T00:00:00Z'); d.toISOString().slice(0, 10) <= akhir.toISOString().slice(0, 10); d.setUTCDate(d.getUTCDate() + 1)) {
    const k = d.toISOString().slice(0, 10)
    hasil.push({ tgl: k, nilai: per[k] || {} })
  }
  return hasil
})
const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
const HARI = ['Min', 'Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab']
const formatTanggal = (tgl, panjang) => {
  const d = new Date(tgl + 'T00:00:00Z')
  return `${panjang ? HARI[d.getUTCDay()] + ', ' : ''}${d.getUTCDate()} ${BULAN[d.getUTCMonth()]}`
}

// Sesi terboros dalam rentang + tanda kebocoran
const sesiBoros = computed(() => {
  const semuaSesi = []
  for (const o of orang.value) for (const s of o.sesi) {
    const konteks = s.t.panggilan ? (s.t.input + s.t.tulis + s.t.baca) / s.t.panggilan : 0
    const jam = s.mulai && s.akhir ? (s.akhir - s.mulai) / 3600 : 0
    const tanda = []
    if (konteks >= KONTEKS_BESAR) tanda.push(['Konteks besar', `rata-rata ${pendek(konteks)} token dibaca ulang tiap panggilan`])
    if (jam >= 24) tanda.push(['Lebih dari sehari', `sesi berjalan ${Math.round(jam)} jam`])
    if (total(s.t) >= SESI_BESAR) tanda.push(['> 100 jt token', 'satu sesi di atas 100 juta token'])
    semuaSesi.push({ ...s, nama: o.nama, konteks, jam, tanda })
  }
  return semuaSesi.sort((a, b) => total(b.t) - total(a.t)).slice(0, 10)
})

const semua = computed(() => orang.value.reduce((a, o) => { for (const k of Object.keys(a)) a[k] += o.t[k]; return a }, nol()))
const terbesar = computed(() => Math.max(1, ...orang.value.map((o) => total(o.t))))
const stat = computed(() => [
  ['Total token', data.value ? pendek(total(semua.value)) : null, angka(total(semua.value))],
  ['Output', data.value ? pendek(semua.value.output) : null, angka(semua.value.output)],
  ['Panggilan model', data.value ? angka(semua.value.panggilan) : null, ''],
  ['Orang / sumber', data.value ? angka(orang.value.length) : null, ''],
])
const KEPALA = [
  ['nama', 'Orang', ''], ['total', 'Total', 'kanan'], ['masuk', 'Input + cache tulis', 'sembunyi-hp kanan'],
  ['baca', 'Cache baca', 'sembunyi-hp kanan'], ['output', 'Output', 'kanan'], ['sesi', 'Sesi', 'sembunyi-hp kanan'],
]
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
      <select v-model="model" aria-label="Saring model">
        <option value="">Semua model</option>
        <option v-for="m in daftarModel" :key="m" :value="m">{{ namaModel(m) }}</option>
      </select>
      <input v-model="cari" type="search" placeholder="Cari orang…" aria-label="Cari orang" autocomplete="off">
      <select v-model="jenis" aria-label="Saring jenis penggunaan">
        <option value="">Semua jenis</option>
        <option v-for="j in daftarJenis" :key="j.kunci" :value="j.kunci">{{ j.label }}</option>
      </select>
      <button v-if="jalur || model || cari || jenis" type="button" class="reset" @click="jalur = ''; model = ''; cari = ''; jenis = ''">Reset saringan</button>
    </div>

    <section class="ringkas" aria-label="Ringkasan">
      <div v-for="[l, n, penuh] in stat" :key="l" class="kartu angka" :title="penuh || null"><span class="redup">{{ l }}</span><b>{{ n == null ? '–' : n }}</b></div>
    </section>

    <section class="kartu">
      <div class="kartu-judul">
        <h2>Jenis penggunaan</h2>
        <span class="redup">token per hari{{ rentang === '1' ? ' (14 hari terakhir)' : '' }}, klik jenis untuk menyaring</span>
      </div>
      <p v-if="data && !perJenis.length" class="redup">Tidak ada pemakaian yang cocok dengan saringan ini.</p>
      <template v-else-if="data">
        <ul class="legenda" aria-label="Legenda jenis penggunaan">
          <li v-for="j in perJenis" :key="j.kunci"><i :style="{ background: j.warna }" />{{ j.label }}</li>
        </ul>
        <GrafikBatangTumpuk :hari="hariGrafik" :seri="daftarJenis" :format="pendek" :format-tanggal="formatTanggal" />
        <div class="tabel-wadah">
          <table class="tabel jenis-tabel">
            <thead><tr><th>Jenis</th><th class="kanan">Total</th><th class="kanan">Porsi</th><th class="sembunyi-hp kanan">Output</th><th class="sembunyi-hp kanan">Sesi</th><th class="sembunyi-hp kanan">Rata-rata/sesi</th></tr></thead>
            <tbody>
              <tr v-for="j in perJenis" :key="j.kunci" class="baris" :class="{ terbuka: jenis === j.kunci }" tabindex="0" :aria-pressed="jenis === j.kunci"
                  @click="jenis = jenis === j.kunci ? '' : j.kunci" @keydown.enter.prevent="jenis = jenis === j.kunci ? '' : j.kunci">
                <td><span class="swatch" :style="{ background: j.warna }" aria-hidden="true" />{{ j.label }}
                  <div class="porsi"><i :style="{ width: `${j.persen}%`, background: j.warna }" /></div></td>
                <td class="kanan" :title="angka(total(j.t))"><b>{{ pendek(total(j.t)) }}</b></td>
                <td class="kanan">{{ j.persen < 1 ? '<1' : Math.round(j.persen) }}%</td>
                <td class="sembunyi-hp kanan" :title="angka(j.t.output)">{{ pendek(j.t.output) }}</td>
                <td class="sembunyi-hp kanan">{{ j.sesi }}</td>
                <td class="sembunyi-hp kanan">{{ pendek(total(j.t) / j.sesi) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <p v-else class="redup">Memuat…</p>
    </section>

    <section v-if="sesiBoros.length" class="kartu">
      <div class="kartu-judul"><h2>Sesi terboros</h2><span class="redup">10 teratas dalam rentang, dengan tanda kebocoran</span></div>
      <ul class="sesi boros">
        <li v-for="s in sesiBoros" :key="s.sid">
          <div>
            <span class="judul-sesi"><span class="swatch" :style="{ background: WARNA_JENIS[s.jenis] || WARNA_JENIS.lainnya }" aria-hidden="true" />{{ s.judul || '(tanpa judul)' }}</span>
            <span class="kecil">{{ labelJenis(s.jenis) }} · {{ s.nama }} · {{ JALUR[s.jalur] }} · {{ angka(s.t.panggilan) }} panggilan · konteks rata-rata {{ pendek(s.konteks) }} · {{ tanggalWaktu(s.akhir) }} · <code>{{ s.sid.slice(0, 8) }}</code></span>
            <span v-if="s.tanda.length" class="tanda"><span v-for="[l, ket] in s.tanda" :key="l" class="lencana kuning" :title="ket">⚠ {{ l }}</span></span>
          </div>
          <b :title="angka(total(s.t))">{{ pendek(total(s.t)) }}</b>
        </li>
      </ul>
    </section>

    <section class="kartu">
      <div class="kartu-judul"><h2>Per orang</h2><span class="redup">klik baris untuk rincian</span></div>
      <div class="tabel-wadah">
        <table class="tabel">
          <thead>
            <tr>
              <th v-for="[k, l, kelas] in KEPALA" :key="k" :class="kelas" :aria-sort="ariaUrut(k)">
                <button type="button" class="urut" :class="{ aktif: urut.kolom === k }" @click="urutkan(k)">
                  {{ l }}<span class="panah" aria-hidden="true">{{ urut.kolom === k ? (urut.naik ? '▲' : '▼') : '↕' }}</span>
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!data && !galat"><td colspan="6" class="redup">Memuat…</td></tr>
            <tr v-else-if="data && !orang.length"><td colspan="6" class="redup">Tidak ada pemakaian yang cocok dengan saringan ini.</td></tr>
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
                      <h3>Per jenis</h3>
                      <ul class="daftar">
                        <li v-for="(t, j) in o.perJenis" :key="j"><span><span class="swatch" :style="{ background: WARNA_JENIS[j] || WARNA_JENIS.lainnya }" aria-hidden="true" />{{ labelJenis(j) }}</span><b :title="angka(total(t))">{{ pendek(total(t)) }}</b></li>
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
                            <span class="kecil">{{ labelJenis(s.jenis) }} · {{ JALUR[s.jalur] }} · {{ s.asal }} · {{ tanggalWaktu(s.akhir) }} · <code>{{ s.sid.slice(0, 8) }}</code></span></div>
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
        <li><b>Jenis penggunaan</b> ditebak dari pesan pertama sesi (domain, kata seperti eksekusi/revisi/installer). <b>Installer otomatis</b> = agen desain installer yang jalan tanpa transkrip, diambil dari catatan pemakaian installer. Tebakan salah bisa dikoreksi per sesi di <code>/var/lib/velocity/claude-pakai/jenis.json</code> (<code>{"&lt;id sesi&gt;": "revisi_web"}</code>).</li>
        <li>Tanda <b>konteks besar</b>: tiap panggilan membaca ulang lebih dari 300 rb token. Biasanya karena sesi terlalu panjang; mulai sesi baru atau <code>/clear</code> untuk tugas berbeda supaya kuota lebih hemat.</li>
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
.saring input[type=search] { width: auto; flex: 1 1 180px; max-width: 280px; }
.reset { border: 0; background: transparent; color: var(--aksen-terang); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; padding: 6px 4px; }
.urut { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; }
.urut:hover, .urut.aktif { color: var(--teks); }
.urut:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 2px; border-radius: 4px; }
.urut .panah { font-size: 10px; opacity: .45; }
.urut.aktif .panah { opacity: 1; }
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
.legenda { list-style: none; margin: 0 0 10px; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12.5px; color: var(--teks-2); }
.legenda li { display: inline-flex; align-items: center; gap: 7px; }
.legenda i, .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 3px; flex: none; }
.swatch { margin-right: 8px; vertical-align: -1px; }
.jenis-tabel { margin-top: 14px; }
.porsi { margin-top: 7px; max-width: 260px; height: 5px; border-radius: 999px; background: var(--kartu-2); overflow: hidden; }
.porsi i { display: block; height: 100%; border-radius: 999px; }
.boros li { align-items: flex-start; }
.boros .judul-sesi { display: block; }
.boros .kecil { display: block; margin-top: 3px; color: var(--teks-3); font-size: 12px; }
.boros .tanda { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.catatan h2 { font-size: 15px; margin-bottom: 8px; }
.catatan ul { margin: 0; padding-left: 18px; display: grid; gap: 6px; color: var(--teks-2); font-size: 13.5px; }
@media (max-width: 900px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
  .rinci-isi { grid-template-columns: minmax(0, 1fr); }
  .saring input[type=search] { max-width: none; }
}
</style>
