<script setup>
// Kartu "Token per alur installer" (dipindah dari /token ke /token/proyek, permintaan pemilik 5 Nov 2026): total
// WordPress + Aplikasi Custom per alur, porsi per tahap, dan grafik token installer per hari. Data /api/ai/token-proyek
// dengan rentang sendiri (?alur=minggu|bulan), tidak ikut saringan tanggal tabel di bawahnya.
import { ref, computed, watch } from 'vue'
import { pakaiPolling, angka } from '../api.js'
import { tabUrl } from '../laravel.js'
import GrafikBatangTumpuk from './GrafikBatangTumpuk.vue'
import BilahTahap from './BilahTahap.vue'
import Info from './Info.vue'
import { rekapTahap } from '../tahapToken.js'

// akun = siklus mingguan yang dipakai (Claude 1 Selasa 10.00, Claude 2 Minggu 04.00 WIB)
const props = defineProps({ akun: { type: String, default: '1' } })

const ringkas = new Intl.NumberFormat('id-ID', { notation: 'compact', maximumFractionDigits: 1 })
const pendek = (n) => ringkas.format(n || 0)
const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const hariWIB = (geser = 0) => {
  const d = new Date(Date.now() + 7 * 3600e3)
  d.setUTCDate(d.getUTCDate() + geser)
  return d.toISOString().slice(0, 10)
}
// Sama dengan Token.vue: data token per hari penuh, jadi hari reset dihitung masuk siklus baru
const SIKLUS = { 1: { hari: 2, jam: 10 }, 2: { hari: 0, jam: 4 } }
const mulaiMinggu = (k) => { // epoch detik awal siklus k ke belakang
  const { hari, jam } = SIKLUS[props.akun] || SIKLUS[1], kini = Date.now() + 7 * 3600e3
  const d = new Date(kini)
  d.setUTCHours(jam, 0, 0, 0)
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() - hari + 7) % 7))
  if (d.getTime() > kini) d.setUTCDate(d.getUTCDate() - 7)
  d.setUTCDate(d.getUTCDate() - 7 * k)
  return (d.getTime() - 7 * 3600e3) / 1000
}
const tglWIB = (t) => new Date((t + 7 * 3600) * 1000).toISOString().slice(0, 10)
const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
const HARI = ['Min', 'Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab']
const formatTanggal = (tgl, panjang) => {
  const d = new Date(tgl + 'T00:00:00Z')
  return `${panjang ? HARI[d.getUTCDay()] + ', ' : ''}${d.getUTCDate()} ${BULAN[d.getUTCMonth()]}`
}
const RENTANG_HARIAN = [['14', '14 hari'], ['30', '30 hari'], ['semua', 'Semua']]

// Total token per alur installer (usage.jsonl lewat /api/ai/token-proyek). Rentangnya punya filter sendiri (?alur=):
// Mingguan = siklus berjalan akun terpilih, Bulanan = sejak tanggal 1 bulan ini; keduanya sampai hari ini (WIB).
const WAKTU_ALUR = [['minggu', 'Mingguan'], ['bulan', 'Bulanan']]
const waktuAlur = tabUrl('alur', 'minggu', { boleh: WAKTU_ALUR.map(([k]) => k) })
const batasAlur = computed(() => {
  const sampai = hariWIB()
  return { dari: waktuAlur.value === 'bulan' ? `${sampai.slice(0, 7)}-01` : tglWIB(mulaiMinggu(0)), sampai }
})
const urlAlur = computed(() => `/api/ai/token-proyek?dari=${batasAlur.value.dari}&sampai=${batasAlur.value.sampai}`)
const { data: dataAlur, galat: galatAlur, muatUlang: muatAlur } = pakaiPolling(() => urlAlur.value, 300000)
watch(urlAlur, muatAlur)
// Nama yang mudah dibaca untuk kartu ini saja. token_alur.py sengaja tidak diubah: label di sana baru berlaku sesudah
// installer-status direstart, dan /token/proyek masih memakainya.
const LABEL_ALUR = {
  fse: 'Terapkan desain tema', diagram: 'Diagram data & alur', susun: 'Susun dokumen rancangan',
  'desain_claude:halaman': 'Desain halaman', 'desain_claude:tema': 'Desain tema', desain_claude: 'Desain (catatan lama)',
  tema: 'Penyesuaian tema', permintaan_claude: 'Permintaan dari form', konten: 'Penulisan konten',
}
const SERI_INSTALLER = [
  { kunci: 'wordpress', label: 'WordPress', pendek: 'WordPress', warna: '#3987e5' },
  { kunci: 'laravel', label: 'Aplikasi Custom', pendek: 'Custom', warna: '#d95926' },
]
const alurInstaller = computed(() => SERI_INSTALLER.map(({ kunci, label, pendek: labelPendek, warna }) => {
  const per = {}
  for (const p of dataAlur.value?.proyek || []) {
    if (p.jenis !== kunci) continue
    for (const a of p.alur) {
      // Agen & revisi per fitur (F01, F02, ...) dan baca gambar per skrip digabung jadi satu alur
      const nama = a.kunci.startsWith('agen:') ? 'Pembuatan fitur' : a.kunci.startsWith('review:') ? 'Revisi fitur' : a.kelompok === 'Baca gambar' ? 'Baca gambar' : LABEL_ALUR[a.kunci] || a.label
      const t = per[nama] ||= { nama, total: 0, panggilan: 0, biaya: 0, tanpaBiaya: 0, proyek: new Set() }
      if (!a.biaya_usd || a.parsial) t.tanpaBiaya++
      t.total += a.total
      t.panggilan += a.panggilan
      t.biaya += a.biaya_usd
      t.proyek.add(p.id)
    }
  }
  const baris = Object.values(per).sort((a, b) => b.total - a.total)
  const total = baris.reduce((n, b) => n + b.total, 0)
  // Satu project bisa menentukan seluruh angka installer: disebut bila mengambil lebih dari separuh
  const proyek = (dataAlur.value?.proyek || []).filter((p) => p.jenis === kunci)
  const teratas = proyek.reduce((m, p) => (!m || p.total > m.total ? p : m), null)
  const dominan = teratas && teratas.total > total / 2 ? teratas : null
  return { kunci, label, labelPendek, warna, baris, total, jumlahProyek: proyek.length, dominan }
}))
// Porsi per tahap pengerjaan per installer (Brief → Review untuk Aplikasi Custom), rentang = filter kartu ini
const tahapInstaller = computed(() => ['laravel', 'wordpress'].map((k) => {
  const daftar = (dataAlur.value?.proyek || []).filter((p) => p.jenis === k)
  return { kunci: k, label: SERI_INSTALLER.find((s) => s.kunci === k).label, n: daftar.length, tahap: rekapTahap(k, daftar) }
}).filter((r) => r.n))
const alurKosong = computed(() => alurInstaller.value.every((i) => !i.baris.length))
// Grafik token installer per hari (WordPress + Aplikasi Custom bertumpuk). Rentangnya sendiri, tidak ikut Mingguan/Bulanan;
// API mengirim `harian` untuk semua tanggal. Mulai dari hari pertama ada data bila lebih pendek dari rentang.
const rentangAlurHarian = ref('30')
const SERI_ALUR_HARIAN = SERI_INSTALLER.map(({ kunci, label, warna }) => ({ kunci, label, warna }))
const alurHarian = computed(() => {
  const per = dataAlur.value?.harian || {}
  const ada = Object.keys(per).filter((t) => Object.values(per[t]).some(Boolean)).sort()
  if (!ada.length) return []
  const n = Number(rentangAlurHarian.value)
  const mulai = n && hariWIB(-(n - 1)) > ada[0] ? hariWIB(-(n - 1)) : ada[0]
  const hasil = []
  for (let d = new Date(mulai + 'T00:00:00Z'); d.toISOString().slice(0, 10) <= hariWIB(); d.setUTCDate(d.getUTCDate() + 1)) {
    const k = d.toISOString().slice(0, 10)
    hasil.push({ tgl: k, nilai: { ...(per[k] || {}) } })
  }
  return hasil
})
const jumlahAlurHari = (h) => SERI_INSTALLER.reduce((a, s) => a + (h.nilai[s.kunci] || 0), 0)
// Tiga hari tertinggi diberi angka; hari yang berdekatan (< 3 hari) dilewati supaya labelnya tidak bertumpuk
const alurHariTeratas = computed(() => {
  const dipilih = []
  const jarak = (a, b) => Math.abs(new Date(a) - new Date(b)) / 86400e3
  for (const h of alurHarian.value.filter(jumlahAlurHari).sort((a, b) => jumlahAlurHari(b) - jumlahAlurHari(a))) {
    if (dipilih.length === 3) break
    if (dipilih.every((t) => jarak(t, h.tgl) >= 3)) dipilih.push(h.tgl)
  }
  return dipilih
})
const rataAlurHarian = computed(() => {
  const lengkap = alurHarian.value.filter((h) => h.tgl !== hariWIB())
  return lengkap.length ? lengkap.reduce((a, h) => a + jumlahAlurHari(h), 0) / lengkap.length : 0
})
const totalAlur = computed(() => alurInstaller.value.reduce((n, i) => n + i.total, 0))
// Satu daftar untuk kedua installer. Alur bernama sama tetap berdampingan. Alur di bawah 1% total gabungan dilipat per
// installer; alur kecil yang hanya satu tetap tampil sendiri.
const AMBANG_ALUR = 0.01
const barisGabungan = computed(() => {
  const besar = [], grup = []
  for (const i of alurInstaller.value) {
    const kecil = i.baris.filter((b) => b.total < totalAlur.value * AMBANG_ALUR)
    const lipat = kecil.length > 1
    for (const b of i.baris) if (!lipat || !kecil.includes(b)) besar.push({ ...b, i })
    if (!lipat) continue
    const jumlah = (k) => kecil.reduce((n, b) => n + b[k], 0)
    grup.push({ i, grup: true, nama: `Alur kecil ${i.labelPendek} (${kecil.length})`, total: jumlah('total'), biaya: jumlah('biaya'), tanpaBiaya: jumlah('tanpaBiaya'), anak: kecil.map((b) => ({ ...b, i, induk: true })) })
  }
  const perNama = {}
  for (const b of besar) perNama[b.nama] = (perNama[b.nama] || 0) + b.total
  besar.sort((a, b) => perNama[b.nama] - perNama[a.nama] || a.nama.localeCompare(b.nama) || b.total - a.total)
  grup.sort((a, b) => b.total - a.total)
  return [...besar, ...grup]
})
const barisTampil = computed(() => barisGabungan.value.flatMap((b) => (b.grup && alurBuka.value.has(kunciBaris(b.i, b)) ? [b, ...b.anak] : [b])))
// Batang total dan batang alur memakai satu skala, jadi panjangnya bisa dibandingkan di seluruh kartu
const puncakAlur = computed(() => Math.max(1, ...alurInstaller.value.map((i) => i.total)))
// API mengembalikan rentang yang dipakai: bila beda dari pilihan sekarang, angka yang tampil masih milik rentang lama
const alurMemperbarui = computed(() => Boolean(dataAlur.value) && (dataAlur.value.dari !== batasAlur.value.dari || dataAlur.value.sampai !== batasAlur.value.sampai))
const mencobaAlur = ref(false)
async function cobaLagiAlur() {
  mencobaAlur.value = true
  await muatAlur()
  mencobaAlur.value = false
}
// Project dominan: saring tabel di halaman yang sama (?cari=)
const tautanDominan = (p) => ({ path: '/token/proyek', query: { cari: p.id } })
const FORMAT_TGL = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', timeZone: 'UTC' })
const tglPendek = (t) => FORMAT_TGL.format(new Date(`${t}T00:00:00Z`))
const rentangAlur = computed(() => {
  const { dari, sampai } = batasAlur.value, tahun = sampai.slice(0, 4)
  if (dari === sampai) return `${tglPendek(dari)} ${tahun}`
  if (dari.slice(0, 4) !== tahun) return `${tglPendek(dari)} ${dari.slice(0, 4)} – ${tglPendek(sampai)} ${tahun}`
  if (dari.slice(5, 7) === sampai.slice(5, 7)) return `${Number(dari.slice(8))}–${tglPendek(sampai)} ${tahun}`
  return `${tglPendek(dari)} – ${tglPendek(sampai)} ${tahun}`
})
const labelAkun = computed(() => `Claude ${props.akun}`)
const alurBuka = ref(new Set())
const kunciBaris = (i, b) => `${i.kunci}|${b.grup ? '__kecil' : b.nama}`
function alihAlur(i, b) {
  const k = kunciBaris(i, b)
  if (!alurBuka.value.delete(k)) alurBuka.value.add(k)
}
// tanpaBiaya = gabungan project + alur yang biayanya nol (model tanpa harga) atau terputus sebelum biaya tercatat
const biayaAlur = (b) => {
  if (!b.biaya) return 'biaya tidak tercatat'
  const n = b.biaya < 0.005 ? '<$0.01' : usd.format(b.biaya)
  return `setara ${n}${b.tanpaBiaya ? ' (sebagian)' : ''}`
}
// Satu satuan di seluruh kartu: "841,7 rb" di samping "62 jt" mudah terbaca lebih besar
const jtAlur = (n) => {
  const j = (n || 0) / 1e6
  if (!j) return '0 jt'
  if (j < 0.01) return '<0,01 jt'
  return `${j.toLocaleString('id-ID', { maximumFractionDigits: j < 10 ? 2 : 1 })} jt`
}
const persenAlur = (n, t) => {
  const p = t ? n / t * 100 : 0
  return p > 0 && p < 0.1 ? '<0,1%' : `${p.toLocaleString('id-ID', { maximumFractionDigits: 1 })}%`
}
</script>

<template>
<section class="kartu" aria-labelledby="judul-alur">
  <div class="kartu-judul">
    <h2 id="judul-alur" class="judul-info">Token per alur installer
      <Info label="Tentang token per alur installer"><p>Jumlah semua project dari catatan installer, per alur, gabungan semua akun Claude. WordPress dan Aplikasi Custom memakai skala batang yang sama, dan persen dihitung dari total keduanya. Alur di bawah 1% digabung per installer dan bisa dibuka.</p><p>Mingguan memakai siklus berjalan Claude 1. Bulanan dihitung sejak tanggal 1 bulan ini. Keduanya sampai hari ini.</p><p>Hanya pemakaian installer; sesi Claude manual (terminal, desktop, Telegram, bot) tidak termasuk, jadi angkanya tidak bisa dijumlahkan dengan halaman Token Usage. Biaya adalah setara harga API dan hanya tercatat untuk Claude.</p></Info>
    </h2>
    <div class="aksi-alur">
      <div class="segmen" role="group" aria-label="Rentang token per alur">
        <button v-for="[k, l] in WAKTU_ALUR" :key="k" type="button" :class="{ aktif: waktuAlur === k }" :aria-pressed="waktuAlur === k" @click="waktuAlur = k">{{ l }}</button>
      </div>
    </div>
  </div>
  <div class="ket-alur">
    <p class="ket-utama">
      <span>{{ rentangAlur }} · semua project, gabungan semua akun<template v-if="waktuAlur === 'minggu'"> · tanggal mengikuti siklus {{ labelAkun }}</template></span>
    </p>
    <p class="ket-lanjut">Rentangnya dipilih di kartu ini, tidak ikut saringan tabel di bawah.</p>
  </div>
  <div v-if="galatAlur" class="galat-alur" role="alert">
    <span class="pesan-status bahaya">Data alur tidak terbaca.</span>
    <button type="button" class="coba-alur" :disabled="mencobaAlur" @click="cobaLagiAlur">{{ mencobaAlur ? 'Memuat…' : 'Coba lagi' }}</button>
  </div>
  <p v-else-if="!dataAlur" class="redup">Memuat…</p>
  <template v-else>
    <p v-if="alurMemperbarui" class="redup memperbarui-alur" role="status">Memperbarui…</p>
    <p v-if="alurKosong" class="redup" :class="{ 'alur-memuat': alurMemperbarui }">Tidak ada pemakaian dalam rentang ini.</p>
    <div v-else class="alur-installer" :class="{ 'alur-memuat': alurMemperbarui }">
      <p class="dasar-alur">Total kedua installer <b :title="angka(totalAlur)">{{ jtAlur(totalAlur) }}</b> = 100%</p>
      <ul class="total-daftar" aria-label="Total per installer">
        <li v-for="i in alurInstaller" :key="i.kunci" class="total-alur">
          <span class="nama">{{ i.label }}</span>
          <span class="tag-alur">{{ angka(i.jumlahProyek) }} project</span>
          <span class="batang-alur"><span v-if="i.total" class="porsi" aria-hidden="true" :style="{ flexBasis: `${i.total / puncakAlur * 100}%` }"><i :style="{ background: i.warna }" /></span></span>
          <b :title="angka(i.total)">{{ jtAlur(i.total) }}</b>
          <span class="persen-alur">{{ persenAlur(i.total, totalAlur) }}</span>
          <span v-if="i.dominan" class="dominan-alur">{{ jtAlur(i.dominan.total) }} ({{ Math.round(i.dominan.total / i.total * 100) }}%) dari <router-link :to="tautanDominan(i.dominan)" :title="i.dominan.nama || undefined">{{ i.dominan.id }}</router-link></span>
        </li>
      </ul>
      <div class="tahap-alur" aria-label="Porsi token per tahap pengerjaan">
        <h3>Porsi per tahap pengerjaan
          <Info label="Tentang porsi per tahap"><p>Bagian token tiap tahap dari total installer itu, untuk semua project dalam rentang kartu ini. Arahkan kursor ke bilah untuk melihat alur terbesar di tahap itu; rincian per project ada di tabel di bawah.</p><p>Aplikasi Custom: Brief mencakup saran platform, contoh tampilan, PRD, dan ERD/flowchart. Install tidak ditampilkan karena tidak memakai AI. Review = run agen untuk revisi dari webmaster.</p></Info>
        </h3>
        <div v-for="r in tahapInstaller" :key="r.kunci" class="tahap-baris">
          <p><b>{{ r.label }}</b> <span class="redup">{{ angka(r.n) }} project</span></p>
          <BilahTahap :tahap="r.tahap" :format="pendek" :judul="`Porsi token per tahap ${r.label}`" />
        </div>
      </div>
      <ul class="daftar-alur" aria-label="Token per alur, WordPress dan Aplikasi Custom">
        <li v-for="b in barisTampil" :key="b.grup ? kunciBaris(b.i, b) : `${b.induk ? 'anak' : 'baris'}|${kunciBaris(b.i, b)}`">
          <button type="button" class="baris-alur" :class="{ 'baris-anak': b.induk }" :aria-expanded="alurBuka.has(kunciBaris(b.i, b))" @click="alihAlur(b.i, b)">
            <span class="nama">{{ b.nama }}</span>
            <span class="tag-alur">{{ b.i.labelPendek }}</span>
            <span class="batang-alur">
              <span v-if="b.total" class="porsi" aria-hidden="true" :style="{ flexBasis: `${b.total / puncakAlur * 100}%` }"><i :style="{ background: b.i.warna }" /></span>
              <small v-if="b.grup" class="biaya-grup">{{ biayaAlur(b) }}</small>
            </span>
            <b :title="angka(b.total)">{{ jtAlur(b.total) }}</b>
            <span class="persen-alur">{{ persenAlur(b.total, totalAlur) }}</span>
            <span class="panah-alur" aria-hidden="true">›</span>
          </button>
          <p v-if="!b.grup && alurBuka.has(kunciBaris(b.i, b))" class="rinci-alur">{{ b.i.label }} · {{ angka(b.total) }} token · {{ angka(b.panggilan) }} permintaan · {{ b.proyek.size }} project · {{ biayaAlur(b) }}</p>
        </li>
      </ul>
    </div>
  </template>
  <div v-if="dataAlur && !galatAlur && alurHarian.length" class="alur-harian">
    <div class="kartu-judul">
      <h3>Token installer per hari <span class="redup">· rata-rata harian {{ jtAlur(rataAlurHarian) }}</span></h3>
      <div class="segmen" role="group" aria-label="Rentang grafik installer per hari">
        <button v-for="[k, l] in RENTANG_HARIAN" :key="k" type="button" :class="{ aktif: rentangAlurHarian === k }" :aria-pressed="rentangAlurHarian === k" @click="rentangAlurHarian = k">{{ l }}</button>
      </div>
    </div>
    <ul class="legenda" aria-label="Legenda installer">
      <li v-for="s in SERI_ALUR_HARIAN" :key="s.kunci"><i :style="{ background: s.warna }" />{{ s.label }}</li>
    </ul>
    <GrafikBatangTumpuk judul="Token installer per hari, WordPress dan Aplikasi Custom" :hari="alurHarian" :seri="SERI_ALUR_HARIAN" :format="pendek" :format-tanggal="formatTanggal" :label-nilai="alurHariTeratas" />
    <p class="redup ket-alur-harian">Rentang grafik ini dipilih sendiri, tidak ikut Mingguan/Bulanan. Rata-rata tidak menghitung hari ini.</p>
  </div>
</section>
</template>

<style scoped>
.segmen { display: inline-flex; padding: 3px; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--panel); }
.segmen button { border: 0; background: transparent; color: var(--teks-2); padding: 7px 14px; border-radius: 8px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.segmen button.aktif { background: var(--aksen); color: #fff; }
.segmen button:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
.tahap-alur { display: grid; gap: 14px; margin: 16px 0; padding: 14px 0; border-top: 1px solid var(--garis); border-bottom: 1px solid var(--garis); }
.tahap-alur h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--teks); display: flex; align-items: center; gap: 6px; }
.tahap-baris p { margin: 0 0 6px; font-size: 13px; }
.alur-harian { margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--garis); }
.alur-harian h3 { font-size: 14px; font-weight: 600; margin: 0; color: var(--teks); }
.ket-alur-harian { margin: 8px 0 0; font-size: 12px; }
.legenda { list-style: none; margin: 0 0 10px; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12.5px; color: var(--teks-2); }
.legenda li { display: inline-flex; align-items: center; gap: 7px; }
.legenda i, .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 3px; flex: none; }
.aksi-alur { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; }
.ket-alur { display: grid; gap: 2px; margin: 0 0 14px; font-size: 12.5px; line-height: 1.5; }
.ket-alur p { margin: 0; }
.ket-utama { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 8px; color: var(--teks); font-weight: 600; }
.ket-lanjut { color: var(--teks-3); }
.lencana-alur { display: inline-block; padding: 1px 8px; border: 1px solid var(--garis); border-radius: 999px; font-size: 11.5px; font-weight: 600; color: var(--waspada); white-space: nowrap; }
.galat-alur { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.galat-alur .pesan-status { margin: 0; }
.coba-alur { padding: 6px 12px; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--panel); color: var(--teks); font-size: 13px; font-weight: 600; cursor: pointer; }
.coba-alur:disabled { opacity: .6; cursor: default; }
.coba-alur:focus-visible, .baris-alur:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
.memperbarui-alur { margin: 0 0 8px; font-size: 12.5px; }
.alur-memuat { opacity: .5; transition: opacity .15s; }
/* Jumlah kolom dan bentuk baris mengikuti lebar kartu, bukan layar: lebar kartu ikut berubah oleh sidebar */
.alur-installer { container-type: inline-size; }
.dasar-alur { margin: 0 0 6px; font-size: 12.5px; color: var(--teks-2); }
.dasar-alur b { color: var(--teks); font-variant-numeric: tabular-nums; }
.alur-installer ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 1px; }
.alur-installer .total-daftar { margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid var(--garis); }
.baris-alur, .total-alur { display: grid; grid-template-columns: minmax(0, 190px) 66px minmax(0, 1fr) 56px 48px 10px; align-items: center; gap: 10px; width: 100%; padding: 5px 4px; font-size: 13px; color: var(--teks-2); text-align: left; }
.baris-alur { border: 0; border-radius: 6px; background: transparent; cursor: pointer; }
.total-alur { row-gap: 2px; }
.total-alur .nama { color: var(--teks); font-weight: 600; }
.baris-alur:hover, .baris-alur[aria-expanded="true"] { background: var(--kartu-2); }
.baris-alur .nama, .total-alur .nama { overflow-wrap: anywhere; }
.baris-anak .nama { padding-left: 12px; }
.tag-alur { color: var(--teks-3); font-size: 12px; white-space: nowrap; }
.batang-alur { display: flex; align-items: center; gap: 8px; min-width: 0; }
.batang-alur .porsi { flex: 0 0 auto; display: block; margin: 0; min-width: 3px; max-width: none; height: 12px; border-radius: 0; background: transparent; }
.total-alur .porsi { height: 16px; }
.batang-alur .porsi i { width: 100%; border-radius: 0 4px 4px 0; }
.biaya-grup { min-width: 0; font-size: 12px; color: var(--teks-2); }
.baris-alur b, .total-alur b, .persen-alur { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.baris-alur b, .total-alur b { color: var(--teks); }
.persen-alur { color: var(--teks-3); }
.dominan-alur { grid-column: 3 / -1; font-size: 12.5px; overflow-wrap: anywhere; }
.dominan-alur a { color: var(--aksen-terang); font-weight: 600; }
.panah-alur { color: var(--teks-3); font-size: 15px; line-height: 1; transition: transform .12s; }
.baris-alur[aria-expanded="true"] .panah-alur { transform: rotate(90deg); }
.rinci-alur { margin: 2px 0 8px; padding: 0 4px; font-size: 12.5px; line-height: 1.5; color: var(--teks-2); overflow-wrap: anywhere; }
/* Di bawah 640 px kolom nama memakan batang (1024 dengan sidebar hanya tersisa 164 px): nama dan batang dua lapis */
@container (max-width: 639px) {
  .baris-alur, .total-alur { grid-template-columns: 62px minmax(0, 1fr) auto 48px 10px; grid-template-areas: "nama nama total persen panah" "tag batang batang batang batang"; gap: 5px 8px; padding: 7px 4px; }
  .baris-alur .tag-alur, .total-alur .tag-alur { grid-area: tag; }
  .baris-alur .nama, .total-alur .nama { grid-area: nama; }
  .baris-alur .batang-alur, .total-alur .batang-alur { grid-area: batang; }
  .baris-alur b, .total-alur b { grid-area: total; }
  .baris-alur .persen-alur, .total-alur .persen-alur { grid-area: persen; }
  .baris-alur .panah-alur { grid-area: panah; }
  .dominan-alur { grid-column: 1 / -1; }
}
/* Area ketuk di layar sentuh; tampilan dengan kursor tidak berubah */
@media (pointer: coarse) {
  .aksi-alur .segmen button, .coba-alur, .baris-alur { min-height: 44px; }
  .ke-proyek { display: inline-block; padding-block: 12px; }
  .dominan-alur a { display: inline-block; padding-block: 13px; margin-block: -11px; }
}
.porsi { margin-top: 7px; max-width: 260px; height: 5px; border-radius: 999px; background: var(--kartu-2); overflow: hidden; }
.porsi i { display: block; height: 100%; border-radius: 999px; }
.judul-info { display: inline-flex; align-items: center; gap: 4px; }
</style>
