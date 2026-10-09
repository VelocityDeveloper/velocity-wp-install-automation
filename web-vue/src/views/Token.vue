<script setup>
// Token Usage: pemakaian token Claude Code per orang (Telegram, desktop, terminal SSH, otomasi).
// Data dari timer claude-pakai (scripts/claude-pakai) tiap menit → /brain/token.json (hanya LAN/Tailscale).
import { ref, computed } from 'vue'
import { pakaiPolling, angka, tanggalWaktu, waktuLalu } from '../api.js'
import GrafikBatangTumpuk from '../components/GrafikBatangTumpuk.vue'
import GrafikGaris from '../components/GrafikGaris.vue'
import { tabUrl } from '../laravel.js'
import Info from '../components/Info.vue'

const { data, galat } = pakaiPolling('/brain/token.json', 60000)
// Batas akun dari Anthropic (sama dengan /usage), timer claude-limit tiap 5 menit → /brain/limit.json
// (akun 1) dan /brain/limit-2.json (akun 2)
const { data: limit1, galat: galatLimit1 } = pakaiPolling('/brain/limit.json', 60000)
const { data: limit2, galat: galatLimit2 } = pakaiPolling('/brain/limit-2.json', 60000)
// Akun yang terakhir dipilih pembungkus scripts/claude-akun untuk agen installer
const { data: akunInstaller } = pakaiPolling('/brain/claude-akun.json', 60000)
// Rincian installer per bagian (usage.jsonl installer, Claude & gateway) → /brain/token-installer.json
const { data: dataInstaller } = pakaiPolling('/brain/token-installer.json', 60000)

const RENTANG = [['1', 'Hari ini'], ['kemarin', 'Kemarin'], ['7', '7 hari'], ['30', '30 hari'], ['semua', 'Semua']]
const JALUR = { telegram: 'Telegram', desktop: 'Desktop', terminal: 'Terminal SSH', otomasi: 'Otomasi' }
const rentang = ref('7')
const jalur = ref('')
const model = ref('')
const cari = ref('')
const jenis = ref('')
const divisi = ref('')
const buka = ref(null)
// Per orang / Jenis penggunaan / Sesi terboros jadi tab; tab aktif di URL (?tab=) supaya tautan bisa dibagikan
const TAB = [
  { kunci: 'orang', label: 'Per orang', ket: 'klik baris untuk rincian' },
  { kunci: 'jenis', label: 'Jenis penggunaan', ket: 'token per hari, klik jenis untuk menyaring' },
  { kunci: 'boros', label: 'Sesi terboros', ket: '10 teratas dalam rentang, dengan tanda kebocoran' },
]
const tab = tabUrl('tab', 'orang', { boleh: TAB.map((t) => t.kunci) })
// Dua langganan Claude: semua angka di halaman ini ikut akun yang dipilih (?akun=2). Sesi lama tanpa
// penanda akun = akun 1 (akun 2 baru dipasang 5 Okt 2026).
const DAFTAR_AKUN = computed(() => data.value?.akun || [{ kunci: '1', label: 'Claude 1' }, { kunci: '2', label: 'Claude 2' }])
const akun = tabUrl('akun', '1', { boleh: ['1', '2'] })
const akunSesi = (s) => (s.akun || '1') === akun.value
const limit = computed(() => akun.value === '2' ? limit2.value : limit1.value)
const galatLimit = computed(() => akun.value === '2' ? galatLimit2.value : galatLimit1.value)
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

// Rentang tanggal WIB (YYYY-MM-DD) {dari, sampai}. "Kemarin" perlu batas ATAS juga,
// rentang lain berakhir hari ini.
const hariWIB = (geser = 0) => {
  const d = new Date(Date.now() + 7 * 3600e3)
  d.setUTCDate(d.getUTCDate() + geser)
  return d.toISOString().slice(0, 10)
}
const batas = computed(() => {
  if (rentang.value === 'semua') return { dari: '', sampai: '9999-12-31' }
  if (rentang.value === 'kemarin') return { dari: hariWIB(-1), sampai: hariWIB(-1) }
  return { dari: hariWIB(-(Number(rentang.value) - 1)), sampai: hariWIB() }
})
const dalamRentang = (tgl) => tgl >= batas.value.dari && tgl <= batas.value.sampai

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
  divisi: (o) => (o.divisi || 'zzz').toLowerCase(),
}
function urutkan(kolom) {
  urut.value = urut.value.kolom === kolom ? { kolom, naik: !urut.value.naik } : { kolom, naik: kolom === 'nama' }
}
const ariaUrut = (kolom) => urut.value.kolom === kolom ? (urut.value.naik ? 'ascending' : 'descending') : 'none'

// Divisi dari pengguna.json (sumber: id-telegram-tim.xlsx), untuk pilihan saring
const daftarDivisi = computed(() => data.value?.divisi || [])

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
    if (divisi.value && (o.divisi || '') !== divisi.value) continue
    const t = nol(), perJalur = {}, perModel = {}, perJenis = {}, sesi = []
    for (const s of o.sesi) {
      if (!akunSesi(s)) continue
      if (jalur.value && s.jalur !== jalur.value) continue
      if (jenis.value && (s.jenis || 'lainnya') !== jenis.value) continue
      const ts = nol()
      for (const [tgl, pm] of Object.entries(s.hari)) {
        if (!dalamRentang(tgl)) continue
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
    hasil.push({ nama: o.nama, divisi: o.divisi || '', t, sesi, perJalur, perModel, perJenis, teridentifikasi: !/^(Belum teridentifikasi|Otomasi|SSH password)/.test(o.nama) })
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

// Installer per bagian dalam rentang: urut biaya (Claude) lalu token. Gateway GPT/Mimo tidak tercatat biayanya.
const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const perBagian = computed(() => {
  const d = dataInstaller.value
  if (!d || akun.value !== '1') return null // agen installer hanya memakai akun 1
  const m = {}
  for (const [tgl, pb] of Object.entries(d.hari || {})) {
    if (!dalamRentang(tgl)) continue
    for (const [b, x] of Object.entries(pb)) {
      const r = (m[b] ||= { kunci: b, token: 0, output: 0, baca: 0, biaya: 0, panggilan: 0, gagal: 0, domain: new Set(), model: new Set() })
      r.token += x.v[0]; r.output += x.v[1]; r.baca += x.v[2]; r.biaya += x.v[3]; r.panggilan += x.v[4]; r.gagal += x.v[5]
      x.domain.forEach((v) => r.domain.add(v)); x.model.forEach((v) => r.model.add(v))
    }
  }
  const baris = Object.values(m)
  const tok = Math.max(1, baris.reduce((a, r) => a + r.token, 0))
  const biaya = baris.reduce((a, r) => a + r.biaya, 0)
  return {
    token: baris.reduce((a, r) => a + r.token, 0), biaya,
    baris: baris.map((r) => ({ ...r, label: d.bagian?.[r.kunci]?.[0] || r.kunci, kelompok: d.bagian?.[r.kunci]?.[1] || 'lain',
      persen: r.token / tok * 100, persenBiaya: biaya ? r.biaya / biaya * 100 : 0, nDomain: r.domain.size, model: [...r.model].join(', ') }))
      .sort((a, b) => b.biaya - a.biaya || b.token - a.token),
  }
})

// Token per tanggal per jenis, ikut saringan orang/divisi/jalur/jenis/model (tanpa rentang)
const perTanggal = computed(() => {
  const per = {}
  for (const o of data.value?.pengguna || []) {
    if (cari.value.trim() && !o.nama.toLowerCase().includes(cari.value.trim().toLowerCase())) continue
    if (divisi.value && (o.divisi || '') !== divisi.value) continue
    for (const s of o.sesi) {
      if (!akunSesi(s)) continue
      if (jalur.value && s.jalur !== jalur.value) continue
      if (jenis.value && (s.jenis || 'lainnya') !== jenis.value) continue
      for (const [tgl, pm] of Object.entries(s.hari)) for (const [m, v] of Object.entries(pm)) {
        if (model.value && m !== model.value) continue
        const h = (per[tgl] ||= {})
        h[s.jenis || 'lainnya'] = (h[s.jenis || 'lainnya'] || 0) + v[0] + v[1] + v[2] + v[3]
      }
    }
  }
  return per
})
// Token per hari per jenis. "Hari ini" tetap memperlihatkan 14 hari supaya ada pembanding.
const hariGrafik = computed(() => {
  const per = perTanggal.value
  const tgl = Object.keys(per).sort()
  if (!tgl.length) return []
  const n = rentang.value === 'semua' ? null : Math.max(14, Number(rentang.value) || 14)
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

// Penggunaan harian: total token per hari (rentang sendiri, mulai dari hari pertama ada data),
// hari tertinggi, dan rata-rata per hari dalam minggu. Hari ini belum lengkap → tidak ikut rata-rata.
const RENTANG_HARIAN = [['14', '14 hari'], ['30', '30 hari'], ['semua', 'Semua']]
const rentangHarian = ref('30')
const SERI_HARIAN = [{ kunci: 'total', label: 'Token', warna: 'var(--aksen-terang)' }]
const harian = computed(() => {
  const per = perTanggal.value
  const ada = Object.keys(per).filter((t) => Object.values(per[t]).some(Boolean)).sort()
  if (!ada.length) return []
  const akhir = hariWIB()
  const n = Number(rentangHarian.value)
  const mulai = n && hariWIB(-(n - 1)) > ada[0] ? hariWIB(-(n - 1)) : ada[0]
  const hasil = []
  for (let d = new Date(mulai + 'T00:00:00Z'); d.toISOString().slice(0, 10) <= akhir; d.setUTCDate(d.getUTCDate() + 1)) {
    const k = d.toISOString().slice(0, 10)
    hasil.push({ tgl: k, nilai: { total: Object.values(per[k] || {}).reduce((a, v) => a + v, 0) } })
  }
  return hasil
})
const hariTeratas = computed(() => harian.value.filter((h) => h.nilai.total).sort((a, b) => b.nilai.total - a.nilai.total).slice(0, 5))
const NAMA_HARI = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu']
const perHariMinggu = computed(() => {
  const r = Array.from({ length: 7 }, () => ({ jumlah: 0, n: 0 }))
  for (const h of harian.value) {
    if (h.tgl === hariWIB()) continue
    const x = r[new Date(h.tgl + 'T00:00:00Z').getUTCDay()]
    x.jumlah += h.nilai.total; x.n++
  }
  // Urutan Senin → Minggu
  const baris = [1, 2, 3, 4, 5, 6, 0].map((i) => ({ nama: NAMA_HARI[i], rata: r[i].n ? r[i].jumlah / r[i].n : 0, n: r[i].n }))
  const maks = Math.max(1, ...baris.map((b) => b.rata))
  return baris.map((b) => ({ ...b, persen: b.rata / maks * 100, puncak: b.rata === maks }))
})
const rataHarian = computed(() => {
  const lengkap = harian.value.filter((h) => h.tgl !== hariWIB())
  return lengkap.length ? lengkap.reduce((a, h) => a + h.nilai.total, 0) / lengkap.length : 0
})

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
  ['nama', 'Orang', ''], ['divisi', 'Divisi', 'sembunyi-hp'], ['total', 'Total', 'kanan'], ['masuk', 'Input + cache tulis', 'sembunyi-hp kanan'],
  ['baca', 'Cache baca', 'sembunyi-hp kanan'], ['output', 'Output', 'kanan'], ['sesi', 'Sesi', 'sembunyi-hp kanan'],
]
// Kartu batas: warna meter ikut tingkat (biru < 70%, kuning < 90%, merah ≥ 90%)
const tingkat = (p) => p >= 90 ? 'merah' : p >= 70 ? 'kuning' : 'biru'
const sisaWaktu = (reset) => {
  if (!reset) return ''
  const d = Math.max(0, reset - Date.now() / 1000), j = Math.floor(d / 3600), m = Math.floor(d % 3600 / 60)
  return j >= 24 ? `${Math.floor(j / 24)} hari ${j % 24} jam` : j ? `${j} jam ${m} mnt` : `${m} mnt`
}
const jamReset = (reset) => reset ? new Date(reset * 1000).toLocaleString('id-ID', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '-'
const BULAN_PANJANG = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
const namaBulan = (ym) => ym ? `${BULAN_PANJANG[Number(ym.slice(5)) - 1]} ${ym.slice(0, 4)}` : ''
// Token bulan berjalan (WIB) dari transkrip lokal, tanpa saringan halaman
const tokenBulanIni = computed(() => {
  const awal = new Date(Date.now() + 7 * 3600e3).toISOString().slice(0, 8)
  let n = 0
  for (const o of data.value?.pengguna || []) for (const s of o.sesi) if (akunSesi(s)) for (const [tgl, pm] of Object.entries(s.hari)) {
    if (tgl.startsWith(awal)) for (const v of Object.values(pm)) n += v[0] + v[1] + v[2] + v[3]
  }
  return n
})
const SERI_LIMIT = [{ kunci: 'lima', label: '5 jam', warna: '#5b8cff' }, { kunci: 'minggu', label: '7 hari', warna: '#26a88e' }]
const titikLimit = computed(() => (limit.value?.riwayat || []).map((r) => ({ t: r.t, lima: r.lima?.persen ?? 0, minggu: r.minggu?.persen ?? 0 })))
const formatWaktuLimit = (t, lengkap) => new Date(t * 1000).toLocaleString('id-ID', lengkap
  ? { weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }
  : { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
const mataUang = (n, kode) => n == null ? '-' : new Intl.NumberFormat('id-ID', { style: 'currency', currency: kode || 'USD' }).format(n)

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

    <div class="tab tab-akun" role="tablist" aria-label="Akun Claude">
      <button v-for="a in DAFTAR_AKUN" :id="`akun-${a.kunci}`" :key="a.kunci" type="button" role="tab" :aria-selected="akun === a.kunci" :class="{ aktif: akun === a.kunci }" @click="akun = a.kunci">
        {{ a.label }}<span v-if="a.email" class="email-akun">{{ a.email }}</span>
      </button>
    </div>
    <p v-if="akunInstaller" class="akun-installer">
      <span class="titik" :class="akunInstaller.akun === '1' ? 'biru' : 'kuning'" aria-hidden="true" />
      Installer memakai <b>Claude {{ akunInstaller.akun }}</b>
      <span class="redup">· {{ akunInstaller.alasan }} · {{ waktuLalu(akunInstaller.t) }}</span>
      <Info label="Tentang pindah akun otomatis" rata="kanan"><p>Agen installer memanggil Claude lewat <code>scripts/claude-akun</code>. Claude 1 didahulukan; kalau batas 5 jam atau mingguannya mencapai {{ akunInstaller.ambang || 95 }}% atau baru kena limit, panggilan berikutnya pindah ke Claude 2, dan kembali ke Claude 1 begitu kuotanya pulih.</p></Info>
    </p>

    <p v-if="galat" class="pesan-status bahaya" role="alert">
      Data token tidak terbaca{{ String(galat.message).startsWith('403') ? ': hanya bisa dibuka dari jaringan kantor atau Tailscale.' : '.' }}
    </p>

    <section class="kartu" aria-labelledby="judul-batas">
      <div class="kartu-judul">
        <h2 id="judul-batas" class="judul-info">Batas pemakaian akun
          <Info label="Tentang batas pemakaian">
            <p>Angka resmi dari Anthropic, sama dengan perintah <code>/usage</code>. Semua orang memakai satu akun Claude.</p>
            <p v-if="limit?.rincian_mingguan?.length">Porsi mingguan: {{ limit.rincian_mingguan.filter((r) => r.persen).map((r) => `${r.nama} ${r.persen}%`).join(' · ') }}</p>
          </Info>
        </h2>
        <span class="redup">
          <template v-if="limit">Claude {{ limit.paket === 'max' ? 'Max' : limit.paket }}{{ /max_20x/.test(limit.tier) ? ' 20x' : /max_5x/.test(limit.tier) ? ' 5x' : '' }} · {{ waktuLalu(limit.dibuat) }}</template>
          <template v-else-if="!galatLimit">Memuat…</template>
        </span>
      </div>
      <p v-if="galatLimit" class="pesan-status bahaya" role="alert">Data batas tidak terbaca.</p>
      <p v-else-if="limit?.galat" class="pesan-status bahaya" role="alert">Gagal memperbarui ({{ limit.galat }}), angka di bawah dari {{ tanggalWaktu(limit.dibuat) }}.</p>
      <div v-if="limit" class="batas">
        <div v-for="[judul, j, ket] in [['5 jam', limit.lima_jam, 'Jendela bergulir sejak pesan pertama.'], ['Mingguan', limit.mingguan, 'Semua model.']]" :key="judul" class="batas-item">
          <div class="batas-kepala">
            <h3>{{ judul }}
              <Info :label="`Tentang batas ${judul}`"><p>{{ ket }}</p><p v-if="j?.reset">Reset {{ jamReset(j.reset) }}.</p></Info>
            </h3>
            <span v-if="(judul === '5 jam' && limit.batas_aktif === 'session') || (judul === 'Mingguan' && limit.batas_aktif === 'weekly_all')" class="lencana kuning" title="Batas yang saat ini paling menentukan menurut Anthropic">penentu</span>
          </div>
          <div class="batas-angka">
            <b class="persen">{{ j ? Math.round(j.persen) : '–' }}<small>%</small></b>
            <span v-if="j?.reset" class="kecil">reset {{ sisaWaktu(j.reset) }} lagi</span>
          </div>
          <div class="meter tebal" :class="tingkat(j?.persen)" role="meter" :aria-valuenow="j?.persen" aria-valuemin="0" aria-valuemax="100" :aria-label="`Batas ${judul} terpakai`"><i :style="{ width: `${Math.min(100, j?.persen || 0)}%` }" /></div>
          <span v-if="judul === 'Mingguan' && limit.mingguan_model.length" class="kecil">{{ limit.mingguan_model.map((m) => `Khusus ${m.nama} ${m.persen}%`).join(' · ') }}</span>
        </div>
        <div class="batas-item">
          <div class="batas-kepala">
            <h3>Bulanan · {{ namaBulan(limit.bulanan.bulan) }}
              <Info label="Tentang angka bulanan" rata="kanan">
                <p>Dari transkrip lokal. Paket Max tidak punya kuota bulanan; yang dibatasi hanya 5 jam dan mingguan.</p>
                <ul v-if="limit.bulanan.mingguan.length"><li v-for="m in limit.bulanan.mingguan" :key="m.reset">Puncak minggu s.d. {{ jamReset(m.reset).replace(/,? \d{2}[.:]\d{2}$/, '') }}: {{ Math.round(m.puncak) }}%</li></ul>
                <p>Rekap batas dicatat sejak {{ tanggalWaktu(limit.bulanan.sejak) }}.</p>
              </Info>
            </h3>
          </div>
          <div class="batas-angka">
            <b class="persen" :title="angka(tokenBulanIni)">{{ data ? pendek(tokenBulanIni) : '–' }}<small> token</small></b>
          </div>
          <span class="kecil">
            5 jam penuh {{ limit.bulanan.penuh_5jam }}/{{ limit.bulanan.jendela_5jam }} · puncak {{ limit.bulanan.puncak_5jam == null ? '-' : Math.round(limit.bulanan.puncak_5jam) + '%' }}
            · extra {{ limit.extra.aktif ? `${mataUang(limit.extra.terpakai, limit.extra.mata_uang)} / ${mataUang(limit.extra.batas, limit.extra.mata_uang)}` : 'tidak aktif' }}
          </span>
        </div>
      </div>
      <template v-if="titikLimit.length > 1">
        <h3 class="sub">Riwayat 8 hari</h3>
        <GrafikGaris :titik="titikLimit" :seri="SERI_LIMIT" :format-waktu="formatWaktuLimit" :tinggi="170" />
      </template>
    </section>

    <div class="saring" role="group" aria-label="Saring">
      <div class="segmen" role="radiogroup" aria-label="Rentang waktu">
        <button v-for="[k, l] in RENTANG" :key="k" type="button" role="radio" :aria-checked="rentang === k" :class="{ aktif: rentang === k }" @click="rentang = k">{{ l }}</button>
      </div>
      <select v-model="divisi" aria-label="Saring divisi">
        <option value="">Semua divisi</option>
        <option v-for="d in daftarDivisi" :key="d" :value="d">{{ d }}</option>
      </select>
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
      <button v-if="jalur || model || cari || jenis || divisi" type="button" class="reset" @click="jalur = ''; model = ''; cari = ''; jenis = ''; divisi = ''">Reset saringan</button>
    </div>

    <section class="ringkas" aria-label="Ringkasan">
      <div v-for="[l, n, penuh] in stat" :key="l" class="kartu angka" :title="penuh || null"><span class="redup">{{ l }}</span><b>{{ n == null ? '–' : n }}</b></div>
    </section>

    <section class="kartu" aria-labelledby="judul-harian">
      <div class="kartu-judul">
        <h2 id="judul-harian" class="judul-info">Penggunaan harian
          <Info label="Tentang penggunaan harian"><p>Total token Claude Code per hari (WIB), ikut saringan orang, divisi, jalur, jenis, dan model di atas. Tiga hari tertinggi diberi angka di atas batangnya.</p><p>Rata-rata per hari dalam minggu tidak menghitung hari ini karena belum selesai.</p></Info>
        </h2>
        <div class="segmen" role="group" aria-label="Rentang grafik harian">
          <button v-for="[k, l] in RENTANG_HARIAN" :key="k" type="button" :class="{ aktif: rentangHarian === k }" :aria-pressed="rentangHarian === k" @click="rentangHarian = k">{{ l }}</button>
        </div>
      </div>
      <p v-if="data && !harian.length" class="redup">Tidak ada pemakaian yang cocok dengan saringan ini.</p>
      <template v-else-if="data">
        <GrafikBatangTumpuk judul="Total token per hari" :hari="harian" :seri="SERI_HARIAN" :format="pendek" :format-tanggal="formatTanggal" :label-nilai="hariTeratas.slice(0, 3).map((h) => h.tgl)" />
        <div class="harian-rinci">
          <div>
            <h3>Rata-rata per hari dalam minggu <span class="redup">· rata-rata harian {{ pendek(rataHarian) }}</span></h3>
            <ul class="hari-minggu">
              <li v-for="b in perHariMinggu" :key="b.nama" :class="{ puncak: b.puncak }" :title="`${b.nama}: rata-rata ${angka(Math.round(b.rata))} token dari ${b.n} hari`">
                <span>{{ b.nama }}</span>
                <div class="porsi"><i :style="{ width: `${b.persen}%`, background: 'var(--aksen-terang)' }" /></div>
                <b>{{ b.n ? pendek(b.rata) : '–' }}</b>
              </li>
            </ul>
          </div>
          <div>
            <h3>Hari tertinggi</h3>
            <ol class="hari-teratas">
              <li v-for="h in hariTeratas" :key="h.tgl"><span>{{ NAMA_HARI[new Date(h.tgl + 'T00:00:00Z').getUTCDay()] }}, {{ formatTanggal(h.tgl) }}</span><b :title="angka(h.nilai.total)">{{ pendek(h.nilai.total) }}</b></li>
            </ol>
          </div>
        </div>
      </template>
      <p v-else class="redup">Memuat…</p>
    </section>

    <section class="kartu">
      <div class="kartu-judul">
        <div class="tab" role="tablist" aria-label="Rincian pemakaian">
          <button v-for="t in TAB" :id="`tab-${t.kunci}`" :key="t.kunci" type="button" role="tab" :aria-selected="tab === t.kunci" :aria-controls="`panel-${t.kunci}`" :class="{ aktif: tab === t.kunci }" @click="tab = t.kunci">{{ t.label }}</button>
        </div>
        <span class="redup">{{ tab === 'jenis' && ['1', 'kemarin'].includes(rentang) ? 'token per hari (14 hari terakhir), klik jenis untuk menyaring' : TAB.find((t) => t.kunci === tab).ket }}</span>
      </div>
      <div v-if="tab === 'orang'" id="panel-orang" role="tabpanel" aria-labelledby="tab-orang">
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
            <tr v-if="!data && !galat"><td colspan="7" class="redup">Memuat…</td></tr>
            <tr v-else-if="data && !orang.length"><td colspan="7" class="redup">Tidak ada pemakaian yang cocok dengan saringan ini.</td></tr>
            <template v-for="o in orang" :key="o.nama">
              <tr class="baris" :class="{ terbuka: buka === o.nama }" tabindex="0" :aria-expanded="buka === o.nama"
                  @click="buka = buka === o.nama ? null : o.nama" @keydown.enter.prevent="buka = buka === o.nama ? null : o.nama">
                <td>
                  <b :class="{ redup: !o.teridentifikasi }">{{ o.nama }}</b>
                  <span class="kecil">{{ Object.keys(o.perJalur).map((j) => JALUR[j]).join(' · ') }}</span>
                  <div class="meter" :title="`${Math.round(total(o.t) / total(semua) * 100)}% dari total`"><i :style="{ width: `${total(o.t) / terbesar * 100}%` }" /></div>
                </td>
                <td class="sembunyi-hp">
                  <button v-if="o.divisi" type="button" class="tag-divisi" :class="{ aktif: divisi === o.divisi }"
                          :title="divisi === o.divisi ? 'Hapus saringan divisi' : `Saring divisi ${o.divisi}`"
                          @click.stop="divisi = divisi === o.divisi ? '' : o.divisi">{{ o.divisi }}</button>
                  <span v-else class="redup">–</span>
                </td>
                <td class="kanan" :title="angka(total(o.t))"><b>{{ pendek(total(o.t)) }}</b></td>
                <td class="sembunyi-hp kanan" :title="angka(o.t.input + o.t.tulis)">{{ pendek(o.t.input + o.t.tulis) }}</td>
                <td class="sembunyi-hp kanan" :title="angka(o.t.baca)">{{ pendek(o.t.baca) }}</td>
                <td class="kanan" :title="angka(o.t.output)">{{ pendek(o.t.output) }}</td>
                <td class="sembunyi-hp kanan">{{ o.sesi.length }}</td>
              </tr>
              <tr v-if="buka === o.nama" class="rinci">
                <td colspan="7">
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
                          <div><span v-if="s.mulai" class="lencana biru mulai-sesi" :title="'Sesi dimulai ' + tanggalWaktu(s.mulai)">Mulai {{ tanggalWaktu(s.mulai) }}</span>
                            <span class="judul-sesi">{{ s.judul || '(tanpa judul)' }}</span>
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
      </div>
      <div v-else-if="tab === 'jenis'" id="panel-jenis" role="tabpanel" aria-labelledby="tab-jenis">
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
        <div v-if="perBagian" class="installer-rinci">
          <h3>Installer per bagian <span class="redup">· {{ pendek(perBagian.token) }} token · {{ usd.format(perBagian.biaya) }}</span></h3>
          <p v-if="!perBagian.baris.length" class="redup">Installer tidak memanggil AI dalam rentang ini.</p>
          <div v-else class="tabel-wadah">
            <table class="tabel jenis-tabel">
              <thead><tr><th>Bagian</th><th class="kanan">Biaya</th><th class="kanan">Token</th><th class="sembunyi-hp kanan">Output</th><th class="sembunyi-hp kanan">Panggilan</th><th class="sembunyi-hp kanan">Domain</th><th class="sembunyi-hp kanan">Rata-rata/domain</th><th class="sembunyi-hp">Model</th></tr></thead>
              <tbody>
                <tr v-for="b in perBagian.baris" :key="b.kunci">
                  <td>{{ b.label }}<span class="kecil"> · {{ b.kelompok === 'wp' ? 'WordPress' : b.kelompok === 'laravel' ? 'Laravel' : b.kelompok === 'custom' ? 'Paket custom' : 'lain' }}</span>
                    <div class="porsi"><i :style="{ width: `${b.persenBiaya || b.persen}%`, background: 'var(--aksen)' }" /></div></td>
                  <td class="kanan"><b>{{ b.biaya ? usd.format(b.biaya) : '–' }}</b><span v-if="b.biaya" class="kecil"> {{ b.persenBiaya < 1 ? '<1' : Math.round(b.persenBiaya) }}%</span></td>
                  <td class="kanan" :title="angka(b.token)">{{ pendek(b.token) }}</td>
                  <td class="sembunyi-hp kanan" :title="angka(b.output)">{{ pendek(b.output) }}</td>
                  <td class="sembunyi-hp kanan">{{ angka(b.panggilan) }}<span v-if="b.gagal" class="kecil"> ({{ b.gagal }} gagal)</span></td>
                  <td class="sembunyi-hp kanan">{{ b.nDomain }}</td>
                  <td class="sembunyi-hp kanan">{{ pendek(b.token / Math.max(1, b.nDomain)) }}</td>
                  <td class="sembunyi-hp kecil">{{ b.model }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="redup kecil">Dari catatan pemakaian installer (<code>/var/lib/velocity/ai/usage.jsonl</code>), semua model. Biaya hanya tercatat untuk Claude (setara harga API); model gateway (GPT/Mimo) tampil "–". Bagian paling atas = paling boros.</p>
        </div>
      </template>
      <p v-else class="redup">Memuat…</p>
      </div>
      <div v-else id="panel-boros" role="tabpanel" aria-labelledby="tab-boros">
        <p v-if="data && !sesiBoros.length" class="redup">Tidak ada sesi dalam rentang ini.</p>
      <ul v-if="sesiBoros.length" class="sesi boros">
        <li v-for="s in sesiBoros" :key="s.sid">
          <div>
            <span v-if="s.mulai" class="lencana biru mulai-sesi" :title="'Sesi dimulai ' + tanggalWaktu(s.mulai)">Mulai {{ tanggalWaktu(s.mulai) }}</span>
            <span class="judul-sesi"><span class="swatch" :style="{ background: WARNA_JENIS[s.jenis] || WARNA_JENIS.lainnya }" aria-hidden="true" />{{ s.judul || '(tanpa judul)' }}</span>
            <span class="kecil">{{ labelJenis(s.jenis) }} · {{ s.nama }} · {{ JALUR[s.jalur] }} · {{ angka(s.t.panggilan) }} panggilan · konteks rata-rata {{ pendek(s.konteks) }} · {{ tanggalWaktu(s.akhir) }} · <code>{{ s.sid.slice(0, 8) }}</code></span>
            <span v-if="s.tanda.length" class="tanda"><span v-for="[l, ket] in s.tanda" :key="l" class="lencana kuning" :title="ket">⚠ {{ l }}</span></span>
          </div>
          <b :title="angka(total(s.t))">{{ pendek(total(s.t)) }}</b>
        </li>
      </ul>
      </div>
    </section>

    <section class="kartu catatan">
      <h2>Cara membaca</h2>
      <ul>
        <li><b>Cache baca</b> paling besar tapi paling murah: konteks yang dipakai ulang tiap panggilan. <b>Input + cache tulis</b> dan <b>output</b> yang paling berat untuk kuota.</li>
        <li><b>Telegram</b> dikenali dari ID chat. <b>Desktop dan terminal</b> dikenali dari kunci SSH yang dipakai login<template v-if="data?.pencatat_sejak">, dicatat sejak {{ tanggalWaktu(data.pencatat_sejak) }}</template>. Sesi sebelumnya masuk "Belum teridentifikasi".</li>
        <li>Login SSH pakai <b>password</b> hanya bisa dikenali lewat IP. Nama untuk IP atau ID Telegram bisa ditambahkan di <code>/var/lib/velocity/claude-pakai/pengguna.json</code>.</li>
        <li><b>Divisi</b> ikut daftar tim di <code>/etc/velocity/secrets/id-telegram-tim.xlsx</code>, dipetakan per orang di <code>pengguna.json</code>. Orang tanpa divisi (termasuk "Belum teridentifikasi" dan Otomasi) tampil sebagai <b>–</b> dan tidak ikut kalau divisi disaring.</li>
        <li><b>Jenis penggunaan</b> ditebak dari pesan pertama sesi (domain, kata seperti eksekusi/revisi/installer). <b>Installer otomatis</b> = agen desain installer yang jalan tanpa transkrip, diambil dari catatan pemakaian installer. Tebakan salah bisa dikoreksi per sesi di <code>/var/lib/velocity/claude-pakai/jenis.json</code> (<code>{"&lt;id sesi&gt;": "revisi_web"}</code>).</li>
        <li>Tanda <b>konteks besar</b>: tiap panggilan membaca ulang lebih dari 300 rb token. Biasanya karena sesi terlalu panjang; mulai sesi baru atau <code>/clear</code> untuk tugas berbeda supaya kuota lebih hemat.</li>
        <li>Ada dua langganan: <b>Claude 1</b> (<code>claude</code>, Telegram, installer) dan <b>Claude 2</b> (<code>claude2</code>, mulai 5 Okt 2026). Tab akun menyaring semua angka di halaman ini. Sesi sebelum 5 Okt otomatis masuk Claude 1.</li>
        <li>Token dihitung dari transkrip lokal, bukan dari tagihan Anthropic. Batas pemakaian diambil langsung dari Anthropic per akun.</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; min-width: 0; }
.ringkas { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.angka { display: grid; gap: 2px; padding: 14px 18px; }
.angka b { font-size: 26px; font-weight: 700; }
.tag-divisi { background: var(--tag); border: 1px solid var(--tag-garis); color: var(--tag-teks); border-radius: 999px;
  padding: 2px 10px; font-size: .78rem; cursor: pointer; }
.tag-divisi:hover { border-color: var(--aksen-terang); color: var(--teks-kuat); }
.tag-divisi.aktif { background: var(--tag-aktif); border-color: var(--aksen-terang); color: var(--teks-kuat); }
.saring { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.saring select { width: auto; min-width: 170px; }
.saring input[type=search] { width: auto; flex: 1 1 180px; max-width: 280px; }
.reset { border: 0; background: transparent; color: var(--aksen-terang); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; padding: 6px 4px; }
.urut { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; }
.urut:hover, .urut.aktif { color: var(--teks); }
.urut:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 2px; border-radius: 4px; }
.urut .panah { font-size: 10px; opacity: .45; }
.urut.aktif .panah { opacity: 1; }
.tab { display: flex; flex-wrap: wrap; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 7px 14px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab-akun { justify-self: start; }
.tab-akun button { display: grid; justify-items: start; gap: 1px; padding: 8px 18px; font-size: 14px; }
.akun-installer { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 0; font-size: 13px; color: var(--teks-2); }
.akun-installer b { color: var(--teks); }
.akun-installer .titik { width: 8px; height: 8px; border-radius: 50%; background: var(--aksen-terang); }
.akun-installer .titik.kuning { background: var(--waspada); }
.email-akun { font-size: 11.5px; font-weight: 500; opacity: .75; }
.tab button:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
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
.mulai-sesi { margin-right: 6px; white-space: nowrap; }
.legenda { list-style: none; margin: 0 0 10px; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12.5px; color: var(--teks-2); }
.legenda li { display: inline-flex; align-items: center; gap: 7px; }
.legenda i, .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 3px; flex: none; }
.swatch { margin-right: 8px; vertical-align: -1px; }
.jenis-tabel { margin-top: 14px; }
.installer-rinci { margin-top: 22px; }
.harian-rinci { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 28px; margin-top: 16px; }
.harian-rinci h3 { font-size: 13px; color: var(--teks-2); font-weight: 600; margin: 0 0 10px; }
.hari-minggu, .hari-teratas { list-style: none; margin: 0; padding: 0; display: grid; gap: 7px; }
.hari-minggu li { display: grid; grid-template-columns: 64px minmax(0, 1fr) 56px; align-items: center; gap: 10px; font-size: 13px; color: var(--teks-2); }
.hari-minggu li .porsi { margin: 0; max-width: none; height: 8px; }
.hari-minggu li.puncak { color: var(--teks); font-weight: 600; }
.hari-minggu b, .hari-teratas b { text-align: right; font-variant-numeric: tabular-nums; color: var(--teks); }
.hari-teratas { counter-reset: no; }
.hari-teratas li { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; color: var(--teks-2); counter-increment: no; }
.hari-teratas li::before { content: counter(no) '.'; color: var(--teks-3); width: 18px; flex: none; }
.hari-teratas li span { margin-right: auto; }
@media (max-width: 760px) { .harian-rinci { grid-template-columns: minmax(0, 1fr); gap: 18px; } }
.installer-rinci h3 { margin: 0 0 4px; font-size: 15px; }
.installer-rinci .kecil { color: var(--teks-3); font-size: 12px; }
.porsi { margin-top: 7px; max-width: 260px; height: 5px; border-radius: 999px; background: var(--kartu-2); overflow: hidden; }
.porsi i { display: block; height: 100%; border-radius: 999px; }
.boros li { align-items: flex-start; }
.boros .judul-sesi { display: block; }
.boros .kecil { display: block; margin-top: 3px; color: var(--teks-3); font-size: 12px; }
.boros .tanda { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.catatan h2 { font-size: 15px; margin-bottom: 8px; }
.catatan ul { margin: 0; padding-left: 18px; display: grid; gap: 6px; color: var(--teks-2); font-size: 13.5px; }
.batas { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.batas-item { display: grid; align-content: start; gap: 6px; padding: 10px 14px; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--panel); }
.batas-kepala { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.batas h3, .sub { font-size: 13px; color: var(--teks-2); font-weight: 600; margin: 0; }
.batas h3, .judul-info { display: inline-flex; align-items: center; gap: 4px; }
.batas-angka { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.sub { margin: 14px 0 4px; }
.persen { font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.1; }
.persen small { font-size: 14px; font-weight: 600; color: var(--teks-3); margin-left: 2px; }
.meter.tebal { height: 8px; }
.meter.kuning i { background: var(--waspada); }
.meter.merah i { background: var(--bahaya); }
.batas .kecil { color: var(--teks-3); font-size: 12px; }
.kecil-daftar { margin-top: 4px; font-size: 12.5px; color: var(--teks-2); gap: 4px; }
@media (max-width: 900px) {
  .batas { grid-template-columns: minmax(0, 1fr); }
  .ringkas { grid-template-columns: 1fr 1fr; }
  .rinci-isi { grid-template-columns: minmax(0, 1fr); }
  .saring input[type=search] { max-width: none; }
}
</style>
