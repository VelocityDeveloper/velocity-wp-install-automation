<script setup>
// Report harian malam (scripts/laporan-harian, timer 23:00): dipelajari, diperbaiki, masih kurang, tindak lanjut
// poin kemarin, fokus besok. Data statis /brain/laporan-harian.json (LAN-only), laporan dipilih lewat ?tanggal=.
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Ikon from '../components/Ikon.vue'
import TeksRingan from '../components/TeksRingan.vue'
import BatangMendatar from '../components/BatangMendatar.vue'
import GrafikBatangTumpuk from '../components/GrafikBatangTumpuk.vue'
import { pakaiPolling, tanggalWaktu, angka } from '../api.js'

const { data, galat, memuat, muatUlang } = pakaiPolling('/brain/laporan-harian.json', 300000)
const route = useRoute()
const router = useRouter()

const daftar = computed(() => data.value?.laporan || [])
const indeks = computed(() => {
  const i = daftar.value.findIndex((l) => l.tanggal === route.query.tanggal)
  return i < 0 ? 0 : i
})
const lap = computed(() => daftar.value[indeks.value])
const pilih = (tgl) => router.replace({ query: { ...route.query, tanggal: tgl } })
const geser = (arah) => { const l = daftar.value[indeks.value + arah]; if (l) pilih(l.tanggal) }

const HARI = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu']
const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
const namaTanggal = (t) => {
  const d = new Date(`${t}T00:00:00`)
  return `${HARI[d.getDay()]}, ${d.getDate()} ${BULAN[d.getMonth()]} ${d.getFullYear()}`
}
const PRIORITAS = { tinggi: ['merah', 'Tinggi', 0], sedang: ['kuning', 'Sedang', 1], rendah: ['abu', 'Rendah', 2] }
const STATUS = { tuntas: ['hijau', 'Tuntas'], sebagian: ['kuning', 'Sebagian'], belum: ['merah', 'Belum'] }
const kurang = computed(() => [...(lap.value?.kurang || [])].sort((a, b) => (PRIORITAS[a.prioritas]?.[2] ?? 3) - (PRIORITAS[b.prioritas]?.[2] ?? 3)))
const hitungTL = computed(() => {
  const h = { tuntas: 0, sebagian: 0, belum: 0 }
  for (const t of lap.value?.tindak_lanjut || []) h[t.status] = (h[t.status] || 0) + 1
  return h
})
// PIC poin "kurang": string "Agus, Muh" dipecah jadi lencana; laporan lama tanpa pic tidak menampilkan apa-apa
const pic = (k) => (k.pic || '').split(/\s*[,/]\s*|\s+dan\s+/).map((x) => x.trim()).filter((x) => x && x !== '-')
// Per divisi: angka dari skrip (lap.divisi) digabung ringkasan Claude (lap.per_divisi, laporan sejak 8 Okt)
// Poin array kadang diawali "- " oleh Claude; dibuang supaya tidak jadi bullet ganda
const bersih = (x) => (x || '').replace(/^\s*[-•*]\s+/, '')
const NILAI = { baik: ['hijau', 'Baik'], cukup: ['kuning', 'Cukup'], perlu_perhatian: ['merah', 'Perlu perhatian'] }
const divisi = computed(() => {
  const teks = Object.fromEntries((lap.value?.per_divisi || []).map((x) => [x.divisi, x]))
  return (lap.value?.divisi || []).map((d) => ({ ...teks[d.divisi], ...d, poin: teks[d.divisi]?.poin || [] }))
})
// Per orang dalam divisi: angka dari skrip (d.orang) + ringkasan Claude (d.per_orang, laporan sejak 8 Okt), dicocokkan
// per nama persis — "Aditya K" ≠ "Adityathok"
const orangDivisi = (d) => {
  const teks = Object.fromEntries((d.per_orang || []).map((o) => [o.nama, o.ringkasan]))
  return d.orang.map((o) => ({ ...o, ringkasan: teks[o.nama] }))
}
const tokenPendek = (n) => (n >= 1e9 ? `${(n / 1e9).toFixed(1)} M` : n >= 1e6 ? `${Math.round(n / 1e6)} jt` : angka(n)).replace('.', ',')
const tokenPerMinta = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(2)} jt` : `${Math.round(n / 1e3)} rb`).replace('.', ',')

// Tab (?tab=), tanggal tetap terbawa saat pindah tab
const TAB = [
  { kunci: 'ikhtisar', label: 'Ikhtisar' },
  { kunci: 'divisi', label: 'Divisi' },
  { kunci: 'kurang', label: 'Masih kurang' },
  { kunci: 'diperbaiki', label: 'Diperbaiki' },
  { kunci: 'dipelajari', label: 'Dipelajari' },
]
const tab = computed(() => (TAB.some((t) => t.kunci === route.query.tab) ? route.query.tab : 'ikhtisar'))
const keTab = (k) => router.replace({ query: { ...route.query, tab: k } })
const hitungTab = computed(() => ({
  divisi: divisi.value.filter((d) => d.sesi).length, kurang: kurang.value.length,
  diperbaiki: lap.value?.diperbaiki?.length || 0, dipelajari: lap.value?.dipelajari?.length || 0,
}))
const tombolTab = (e) => {
  const i = TAB.findIndex((t) => t.kunci === tab.value)
  const j = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : null
  if (j == null) return
  const t = TAB[(j + TAB.length) % TAB.length]
  keTab(t.kunci)
  document.getElementById(`tab-${t.kunci}`)?.focus()
}

// Grafik ikhtisar
const SERI_AKSEN = [{ kunci: 'v', label: 'Nilai', warna: 'var(--aksen)' }]
const divisiAktif = computed(() => divisi.value.filter((d) => d.sesi))
const barisPermintaan = computed(() => divisiAktif.value.map((d) => ({
  kunci: d.divisi, label: d.divisi, nilai: { v: d.pesan },
  rincian: [['Sesi', angka(d.sesi)], ['Orang', angka(d.orang.length)], ['Token', tokenPendek(d.token)]].concat(
    NILAI[d.penilaian] ? [['Penilaian', NILAI[d.penilaian][1]]] : []),
})).sort((a, b) => b.nilai.v - a.nilai.v))
const barisEfisiensi = computed(() => divisiAktif.value.filter((d) => d.pesan)
  .map((d) => ({ kunci: d.divisi, label: d.divisi, nilai: { v: d.token / d.pesan },
    rincian: [['Permintaan', angka(d.pesan)], ['Token', tokenPendek(d.token)]] }))
  .sort((a, b) => b.nilai.v - a.nilai.v))
const rataEfisiensi = computed(() => {
  const t = divisiAktif.value.reduce((a, d) => a + d.token, 0)
  const p = divisiAktif.value.reduce((a, d) => a + d.pesan, 0)
  return p ? { nilai: t / p, label: 'Rata-rata semua divisi' } : null
})
const hitungKurang = computed(() => {
  const h = { tinggi: 0, sedang: 0, rendah: 0 }
  for (const k of kurang.value) h[k.prioritas] = (h[k.prioritas] || 0) + 1
  return h
})
const hitungNilai = computed(() => {
  const h = { baik: 0, cukup: 0, perlu_perhatian: 0 }
  for (const d of divisiAktif.value) if (d.penilaian in h) h[d.penilaian] += 1
  return h
})
// Tren: hanya muncul bila sudah ada ≥ 2 laporan (urut lama → baru, maks 30 hari)
const tren = computed(() => [...daftar.value].slice(0, 30).reverse()
  .map((l) => ({ tgl: l.tanggal, nilai: { v: l.angka?.pesan_user || 0 } })))
const SERI_TREN = [{ kunci: 'v', label: 'Permintaan user', warna: 'var(--aksen)' }]
const tglPendek = (t, panjang) => (panjang ? namaTanggal(t) : `${Number(t.slice(8))} ${BULAN[Number(t.slice(5, 7)) - 1]}`)

// Tab divisi: saring satu divisi
const pilihDivisi = computed(() => route.query.divisi || '')
const keDivisi = (d) => router.replace({ query: { ...route.query, divisi: d || undefined } })
const divisiTampil = computed(() => (pilihDivisi.value ? divisi.value.filter((d) => d.divisi === pilihDivisi.value) : divisi.value))

// Tab masih kurang: grafik poin per PIC (bertumpuk menurut prioritas) + saringan
const SERI_PRIORITAS = [
  { kunci: 'tinggi', label: 'Tinggi', warna: 'var(--bahaya)' },
  { kunci: 'sedang', label: 'Sedang', warna: 'var(--waspada)' },
  { kunci: 'rendah', label: 'Rendah', warna: 'var(--teks-3)' },
]
const barisPic = computed(() => {
  const peta = {}
  for (const k of kurang.value) {
    for (const o of pic(k).length ? pic(k) : ['Belum ada PIC']) {
      peta[o] ??= { kunci: o, label: o, nilai: { tinggi: 0, sedang: 0, rendah: 0 } }
      peta[o].nilai[k.prioritas] = (peta[o].nilai[k.prioritas] || 0) + 1
    }
  }
  const jml = (b) => b.nilai.tinggi * 100 + b.nilai.sedang * 10 + b.nilai.rendah
  return Object.values(peta).sort((a, b) => jml(b) - jml(a))
})
// Laporan sebelum 8 Okt belum punya pic → grafik PIC disembunyikan
const adaPic = computed(() => kurang.value.some((k) => pic(k).length))
const saringPrioritas = computed(() => route.query.prioritas || '')
const saringPic = computed(() => route.query.pic || '')
const saring = (k, v) => router.replace({ query: { ...route.query, [k]: v || undefined } })
const kurangTampil = computed(() => kurang.value.filter((k) => (!saringPrioritas.value || k.prioritas === saringPrioritas.value)
  && (!saringPic.value || (pic(k).length ? pic(k) : ['Belum ada PIC']).includes(saringPic.value))))
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Report Harian</h1>
        <p class="redup">Rangkuman tiap malam pukul 23.00: apa yang dipelajari, diperbaiki, dan masih kurang, serta tindak lanjut dari laporan sebelumnya.</p>
      </div>
      <button type="button" class="tombol garis kecil" @click="muatUlang"><Ikon nama="ulang" :ukuran="16" /> Muat ulang</button>
    </header>

    <p v-if="memuat" class="redup">Memuat…</p>
    <p v-else-if="galat && !data" class="pesan-status bahaya">Gagal memuat: {{ galat.message }}</p>
    <p v-else-if="!lap" class="redup">Belum ada laporan. Laporan pertama dibuat malam ini pukul 23.00.</p>

    <template v-else>
      <div class="pilih-hari">
        <button type="button" class="tombol garis kecil" :disabled="indeks >= daftar.length - 1" aria-label="Laporan sebelumnya" @click="geser(1)">‹</button>
        <select :value="lap.tanggal" aria-label="Pilih tanggal laporan" @change="pilih($event.target.value)">
          <option v-for="l in daftar" :key="l.tanggal" :value="l.tanggal">{{ namaTanggal(l.tanggal) }}</option>
        </select>
        <button type="button" class="tombol garis kecil" :disabled="indeks === 0" aria-label="Laporan sesudahnya" @click="geser(-1)">›</button>
        <span class="redup kecil">Dibuat {{ tanggalWaktu(lap.dibuat) }}</span>
      </div>

      <div class="tab" role="tablist" aria-label="Bagian laporan" @keydown="tombolTab">
        <button
          v-for="t in TAB" :id="`tab-${t.kunci}`" :key="t.kunci" type="button" role="tab"
          :aria-selected="tab === t.kunci" :aria-controls="`panel-${t.kunci}`" :tabindex="tab === t.kunci ? 0 : -1"
          :class="{ aktif: tab === t.kunci }" @click="keTab(t.kunci)"
        >{{ t.label }}<span v-if="hitungTab[t.kunci] != null" class="hitung">{{ hitungTab[t.kunci] }}</span></button>
      </div>

      <!-- IKHTISAR -->
      <div v-if="tab === 'ikhtisar'" id="panel-ikhtisar" role="tabpanel" aria-labelledby="tab-ikhtisar" class="panel">
        <div class="ringkas">
          <div class="kartu angka"><span class="redup">Sesi Claude</span><b>{{ angka(lap.angka.sesi) }} <small>· {{ lap.angka.orang }} orang</small></b></div>
          <div class="kartu angka"><span class="redup">Permintaan user</span><b>{{ angka(lap.angka.pesan_user) }}</b></div>
          <div class="kartu angka"><span class="redup">Token sesi</span><b>{{ tokenPendek(lap.angka.token_sesi) }}</b></div>
          <div class="kartu angka"><span class="redup">Commit · memory</span><b>{{ angka(lap.angka.commit) }} <small>· {{ angka(lap.angka.memori) }} memory</small></b></div>
        </div>

        <section class="kartu" aria-labelledby="judul-ringkasan">
          <div class="kartu-judul"><h2 id="judul-ringkasan">Ringkasan</h2></div>
          <p class="ringkasan">{{ lap.ringkasan }}</p>
        </section>

        <div class="dua">
          <section class="kartu status-kartu" aria-labelledby="judul-st-kurang">
            <div class="kartu-judul">
              <h2 id="judul-st-kurang">Masih kurang</h2>
              <button type="button" class="tautan kecil" @click="keTab('kurang')">Lihat {{ kurang.length }} poin →</button>
            </div>
            <div class="ubin-status">
              <button v-for="p in SERI_PRIORITAS" :key="p.kunci" type="button" class="ubin" :class="PRIORITAS[p.kunci][0]"
                @click="router.replace({ query: { ...route.query, tab: 'kurang', prioritas: p.kunci } })">
                <b>{{ hitungKurang[p.kunci] }}</b><span><i />{{ p.label }}</span>
              </button>
            </div>
            <p v-if="lap.tindak_lanjut.length" class="redup kecil tl-baris">
              Tindak lanjut laporan sebelumnya:
              <span v-for="(v, k) in STATUS" :key="k" class="lencana" :class="v[0]">{{ hitungTL[k] }} {{ v[1] }}</span>
            </p>
          </section>
          <section class="kartu status-kartu" aria-labelledby="judul-st-nilai">
            <div class="kartu-judul">
              <h2 id="judul-st-nilai">Penilaian divisi</h2>
              <button type="button" class="tautan kecil" @click="keTab('divisi')">Lihat evaluasi →</button>
            </div>
            <div class="ubin-status">
              <div v-for="(v, k) in NILAI" :key="k" class="ubin statis" :class="v[0]"><b>{{ hitungNilai[k] }}</b><span><i />{{ v[1] }}</span></div>
            </div>
            <p class="nilai-chip">
              <button v-for="d in divisiAktif" :key="d.divisi" type="button" class="chip-divisi" @click="router.replace({ query: { ...route.query, tab: 'divisi', divisi: d.divisi } })">
                {{ d.divisi }} <span v-if="NILAI[d.penilaian]" class="lencana" :class="NILAI[d.penilaian][0]">{{ NILAI[d.penilaian][1] }}</span>
              </button>
            </p>
          </section>
        </div>

        <div class="dua">
          <section v-if="barisPermintaan.length" class="kartu" aria-labelledby="judul-g-minta">
            <div class="kartu-judul"><h2 id="judul-g-minta">Permintaan per divisi</h2><span class="redup kecil">jumlah pesan user ke Claude</span></div>
            <BatangMendatar :baris="barisPermintaan" :seri="SERI_AKSEN" :format="angka" judul="Permintaan per divisi" />
          </section>
          <section v-if="barisEfisiensi.length" class="kartu" aria-labelledby="judul-g-efisien">
            <div class="kartu-judul"><h2 id="judul-g-efisien">Token per permintaan</h2><span class="redup kecil">makin pendek makin hemat</span></div>
            <BatangMendatar :baris="barisEfisiensi" :seri="SERI_AKSEN" :format="tokenPerMinta" :acuan="rataEfisiensi" judul="Token per permintaan per divisi" />
          </section>
        </div>

        <section v-if="tren.length >= 2" class="kartu" aria-labelledby="judul-tren">
          <div class="kartu-judul"><h2 id="judul-tren">Permintaan user per hari</h2><span class="redup kecil">{{ tren.length }} laporan terakhir</span></div>
          <GrafikBatangTumpuk :hari="tren" :seri="SERI_TREN" :format="angka" :format-tanggal="tglPendek" judul="Permintaan user per hari" />
        </section>

        <section class="kartu" aria-labelledby="judul-besok">
          <div class="kartu-judul"><h2 id="judul-besok">Fokus besok</h2></div>
          <ol class="besok">
            <li v-for="(f, i) in lap.fokus_besok" :key="i"><TeksRingan :teks="bersih(f)" /></li>
          </ol>
        </section>
      </div>

      <!-- DIVISI -->
      <div v-else-if="tab === 'divisi'" id="panel-divisi" role="tabpanel" aria-labelledby="tab-divisi" class="panel">
        <div class="saringan" role="group" aria-label="Saring divisi">
          <button type="button" class="chip-divisi" :class="{ aktif: !pilihDivisi }" @click="keDivisi('')">Semua</button>
          <button v-for="d in divisi" :key="d.divisi" type="button" class="chip-divisi" :class="{ aktif: pilihDivisi === d.divisi, redup: !d.sesi }" @click="keDivisi(d.divisi)">
            <i v-if="NILAI[d.penilaian]" class="titik" :class="NILAI[d.penilaian][0]" aria-hidden="true" />{{ d.divisi }}
          </button>
        </div>
        <p class="redup kecil catatan">Dinilai dari sesi Claude saja, belum termasuk chat WA &amp; CRM.</p>
        <div class="grid-divisi" :class="{ tunggal: pilihDivisi }">
          <article v-for="d in divisiTampil" :key="d.divisi" class="kartu divisi" :class="{ kosong: !d.sesi }">
            <header>
              <h3>{{ d.divisi }} <span v-if="NILAI[d.penilaian]" class="lencana" :class="NILAI[d.penilaian][0]">{{ NILAI[d.penilaian][1] }}</span></h3>
              <span v-if="d.sesi" class="redup kecil">{{ angka(d.sesi) }} sesi · {{ angka(d.pesan) }} permintaan · {{ tokenPendek(d.token) }} token</span>
              <span v-else class="redup kecil">Tidak ada sesi Claude</span>
            </header>
            <p v-if="d.orang.length && !orangDivisi(d).some((o) => o.ringkasan)" class="orang">
              <span v-for="o in d.orang" :key="o.nama" class="lencana abu" :title="`${o.sesi} sesi · ${o.pesan} permintaan · ${tokenPendek(o.token)} token`">{{ o.nama }} <small>{{ o.pesan }}</small></span>
            </p>
            <p v-if="d.alasan" class="alasan">{{ d.alasan }}</p>
            <ul v-if="orangDivisi(d).some((o) => o.ringkasan)" class="per-orang" aria-label="Per orang">
              <li v-for="o in orangDivisi(d)" :key="o.nama">
                <span class="po-nama">{{ o.nama }} <small class="redup">{{ o.sesi }} sesi · {{ o.pesan }} permintaan · {{ tokenPendek(o.token) }} token</small></span>
                <TeksRingan class="po-isi" :teks="o.ringkasan || '—'" />
              </li>
            </ul>
            <p v-if="d.ringkasan" class="divisi-ringkas">{{ d.ringkasan }}</p>
            <ul v-if="d.poin.length" class="divisi-poin">
              <li v-for="(x, i) in d.poin" :key="i"><TeksRingan :teks="bersih(x)" /></li>
            </ul>
            <div v-if="d.penilaian" class="evaluasi">
              <template v-for="b in [['berjalan_baik', 'Berjalan baik', 'hijau'], ['perlu_perbaikan', 'Perlu diperbaiki', 'merah'], ['saran', 'Saran', 'biru']]" :key="b[0]">
                <div v-if="d[b[0]]?.length" class="eval-blok" :class="b[2]">
                  <span class="eval-judul">{{ b[1] }}</span>
                  <ul><li v-for="(x, i) in d[b[0]]" :key="i"><TeksRingan :teks="bersih(x)" /></li></ul>
                </div>
              </template>
            </div>
          </article>
        </div>
      </div>

      <!-- MASIH KURANG -->
      <div v-else-if="tab === 'kurang'" id="panel-kurang" role="tabpanel" aria-labelledby="tab-kurang" class="panel">
        <section v-if="adaPic" class="kartu" aria-labelledby="judul-g-pic">
          <div class="kartu-judul"><h2 id="judul-g-pic">Poin per penanggung jawab</h2><span class="redup kecil">klik nama untuk menyaring</span></div>
          <BatangMendatar :baris="barisPic" :seri="SERI_PRIORITAS" judul="Poin masih kurang per penanggung jawab" bisa-pilih :terpilih="saringPic" @pilih="(n) => saring('pic', saringPic === n ? '' : n)" />
        </section>

        <section v-if="lap.tindak_lanjut.length" class="kartu" aria-labelledby="judul-tl">
          <div class="kartu-judul">
            <h2 id="judul-tl">Tindak lanjut laporan {{ lap.kemarin ? namaTanggal(lap.kemarin) : 'kemarin' }}</h2>
            <span class="tl-hitung">
              <span v-for="(v, k) in STATUS" :key="k" class="lencana" :class="v[0]">{{ hitungTL[k] }} {{ v[1] }}</span>
            </span>
          </div>
          <ul class="daftar">
            <li v-for="(t, i) in lap.tindak_lanjut" :key="i" class="baris">
              <span class="lencana" :class="STATUS[t.status]?.[0]">{{ STATUS[t.status]?.[1] || t.status }}</span>
              <div><b>{{ t.poin }}</b><TeksRingan :teks="t.catatan" /></div>
            </li>
          </ul>
        </section>

        <section class="kartu" aria-labelledby="judul-kurang">
          <div class="kartu-judul">
            <h2 id="judul-kurang">Masih kurang</h2>
            <span class="redup kecil">{{ kurangTampil.length }} dari {{ kurang.length }} poin</span>
          </div>
          <div class="saringan" role="group" aria-label="Saring prioritas">
            <button type="button" class="chip-divisi" :class="{ aktif: !saringPrioritas }" @click="saring('prioritas', '')">Semua</button>
            <button v-for="p in SERI_PRIORITAS" :key="p.kunci" type="button" class="chip-divisi" :class="{ aktif: saringPrioritas === p.kunci }" @click="saring('prioritas', p.kunci)">
              <i class="titik" :class="PRIORITAS[p.kunci][0]" aria-hidden="true" />{{ p.label }} <small>{{ hitungKurang[p.kunci] }}</small>
            </button>
            <button v-if="saringPic" type="button" class="chip-divisi aktif" @click="saring('pic', '')">PIC: {{ saringPic }} ✕</button>
          </div>
          <p v-if="!kurangTampil.length" class="redup">Tidak ada.</p>
          <ul class="daftar">
            <li v-for="(k, i) in kurangTampil" :key="i" class="baris">
              <span class="lencana" :class="PRIORITAS[k.prioritas]?.[0]">{{ PRIORITAS[k.prioritas]?.[1] || k.prioritas }}</span>
              <div>
                <b>{{ k.judul }}</b> <span v-for="o in pic(k)" :key="o" class="lencana biru pic" title="Penanggung jawab">{{ o }}</span>
                <TeksRingan :teks="k.isi" />
                <div class="saran"><span>Saran:</span><TeksRingan :teks="k.saran" /></div>
              </div>
            </li>
          </ul>
        </section>
      </div>

      <!-- DIPERBAIKI -->
      <div v-else-if="tab === 'diperbaiki'" id="panel-diperbaiki" role="tabpanel" aria-labelledby="tab-diperbaiki" class="panel">
        <section class="kartu">
          <p v-if="!lap.diperbaiki.length" class="redup">Tidak ada.</p>
          <ul class="daftar">
            <li v-for="(x, i) in lap.diperbaiki" :key="i">
              <b>{{ x.judul }}</b> <span v-if="x.area" class="lencana biru">{{ x.area }}</span>
              <TeksRingan :teks="x.isi" />
            </li>
          </ul>
        </section>
      </div>

      <!-- DIPELAJARI -->
      <div v-else id="panel-dipelajari" role="tabpanel" aria-labelledby="tab-dipelajari" class="panel">
        <section class="kartu">
          <p v-if="!lap.dipelajari.length" class="redup">Tidak ada.</p>
          <ul class="daftar">
            <li v-for="(x, i) in lap.dipelajari" :key="i">
              <b>{{ x.judul }}</b>
              <TeksRingan :teks="x.isi" />
              <p v-if="x.sumber" class="sumber">{{ x.sumber }}</p>
            </li>
          </ul>
        </section>
      </div>

      <p class="redup kecil kaki">Disusun Claude dari memory, transkrip sesi, commit git, laporan installer & token, dan Velocity Update · {{ lap.detik }} dtk · ${{ lap.biaya_usd }}</p>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; max-width: 1100px; }
.pilih-hari { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pilih-hari select { width: auto; flex: 0 1 240px; min-width: 0; padding: 7px 10px; border-radius: var(--radius-kecil); border: 1px solid var(--garis); background: var(--kartu); color: var(--teks); font: inherit; font-weight: 600; }
.pilih-hari .tombol { width: auto; flex: none; min-width: 36px; justify-content: center; font-size: 16px; }
.kecil { font-size: 12.5px; }
.ringkas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.angka { display: grid; gap: 6px; }
.angka b { font-size: 24px; }
.angka b small { font-size: 14px; color: var(--teks-3); font-weight: 600; }
.ringkasan { margin: 0; line-height: 1.65; color: var(--teks-2); }
.tl-hitung { display: flex; gap: 6px; flex-wrap: wrap; }
.daftar { list-style: none; margin: 0; padding: 0; display: grid; }
.daftar li { padding: 11px 0; border-bottom: 1px solid var(--garis); line-height: 1.55; overflow-wrap: anywhere; }
.daftar li:first-child { padding-top: 2px; }
.daftar li:last-child { border-bottom: 0; padding-bottom: 0; }
.daftar p { margin: 4px 0 0; color: var(--teks-2); font-size: 13.5px; }
.baris { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 10px; align-items: start; }
.baris .lencana { justify-self: start; margin-top: 2px; }
.saran { margin-top: 6px; padding: 7px 10px; border-radius: 8px; background: var(--kartu-2); font-size: 13.5px; }
.saran > span { color: var(--teks); font-weight: 600; }
.saran :deep(code) { background: var(--kartu); }
.pic { margin-left: 4px; }
.sumber { font-size: 12px !important; color: var(--teks-3) !important; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.dua { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; align-items: start; }
.besok { margin: 0; padding-left: 22px; display: grid; gap: 8px; line-height: 1.55; color: var(--teks-2); }
.besok :deep(.teks-ringan) { margin-top: 0; font-size: 14px; }
.besok li::marker { color: var(--aksen-terang); font-weight: 700; }
.kaki { margin: 0; }
.panel { display: grid; gap: 18px; }
.tab { display: flex; flex-wrap: wrap; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); justify-self: start; max-width: 100%; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13.5px; font-weight: 600; padding: 7px 14px; border-radius: 8px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab button:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
.tab .hitung { font-size: 11.5px; padding: 0 6px; border-radius: 6px; background: var(--sorot); opacity: .85; }
.tautan { border: 0; background: none; padding: 0; color: var(--aksen-terang); font: inherit; font-weight: 600; cursor: pointer; }
.tautan:hover { text-decoration: underline; }
.status-kartu { display: grid; gap: 12px; align-content: start; }
.ubin-status { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.ubin { display: grid; gap: 2px; justify-items: start; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--garis); background: var(--kartu-2); font: inherit; color: var(--teks-2); cursor: pointer; text-align: left; }
.ubin.statis { cursor: default; }
.ubin:not(.statis):hover { border-color: var(--garis-kuat); }
.ubin b { font-size: 24px; color: var(--teks); font-variant-numeric: tabular-nums; }
.ubin span { display: flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600; }
.ubin i, .titik { width: 8px; height: 8px; border-radius: 50%; flex: none; background: var(--teks-3); display: inline-block; }
.merah > span > i, .titik.merah { background: var(--bahaya); }
.kuning > span > i, .titik.kuning { background: var(--waspada); }
.hijau > span > i, .titik.hijau { background: var(--baik); }
.abu > span > i, .titik.abu { background: var(--teks-3); }
.tl-baris { margin: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.nilai-chip, .saringan { margin: 0; display: flex; flex-wrap: wrap; gap: 6px; }
.chip-divisi { display: inline-flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 999px; border: 1px solid var(--tag-garis); background: var(--tag); color: var(--tag-teks); font: inherit; font-size: 12.5px; font-weight: 600; cursor: pointer; }
.chip-divisi:hover { border-color: var(--garis-kuat); }
.chip-divisi.aktif { background: var(--tag-aktif); color: var(--teks); border-color: var(--aksen); }
.chip-divisi.redup { opacity: .6; }
.chip-divisi small { opacity: .7; }
.catatan { margin: -8px 0 0; }
.saringan + .daftar, .saringan + p { margin-top: 14px; }
.kartu-judul + .saringan { margin-top: 2px; }
.grid-divisi { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-items: start; }
.grid-divisi.tunggal { grid-template-columns: minmax(0, 760px); }
.divisi { display: grid; gap: 10px; align-content: start; }
.divisi.kosong { opacity: .6; }
.divisi header { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.divisi h3 { margin: 0; font-size: 15px; }
.orang { margin: 0; display: flex; flex-wrap: wrap; gap: 5px; }
.orang small { font-weight: 600; opacity: .7; margin-left: 2px; }
.per-orang { list-style: none; margin: 0; padding: 0; display: grid; border: 1px solid var(--garis); border-radius: 10px; overflow: hidden; }
.per-orang li { display: grid; gap: 2px; padding: 8px 12px; border-bottom: 1px solid var(--garis); font-size: 13.5px; line-height: 1.5; }
.per-orang li:last-child { border-bottom: 0; }
.po-nama { font-weight: 600; color: var(--teks); }
.po-nama small { font-weight: 400; margin-left: 4px; font-size: 12px; }
.per-orang :deep(.po-isi) { margin-top: 0; }
.divisi-ringkas { margin: 0; line-height: 1.55; color: var(--teks-2); font-size: 13.5px; }
.divisi-poin { margin: 0; padding-left: 18px; display: grid; gap: 4px; line-height: 1.5; }
.divisi-poin :deep(.teks-ringan), .eval-blok :deep(.teks-ringan) { margin-top: 0; }
.divisi h3 .lencana { margin-left: 6px; vertical-align: 2px; }
.evaluasi { display: grid; gap: 8px; }
.alasan { margin: 0; font-size: 13.5px; font-style: italic; color: var(--teks-2); }
.eval-blok { padding: 7px 10px 7px 12px; border-radius: 8px; background: var(--kartu-2); border-left: 3px solid var(--garis); }
.eval-blok.hijau { border-left-color: var(--baik); }
.eval-blok.merah { border-left-color: var(--bahaya); }
.eval-blok.biru { border-left-color: var(--aksen-terang); }
.eval-judul { display: block; font-size: 12px; font-weight: 700; color: var(--teks); margin-bottom: 2px; }
.eval-blok ul { margin: 0; padding-left: 16px; display: grid; gap: 3px; line-height: 1.5; }
.eval-blok :deep(code) { background: var(--kartu); }
@media (max-width: 860px) {
  .dua, .grid-divisi { grid-template-columns: 1fr; }
  .ringkas { grid-template-columns: 1fr 1fr; }
  .tab { justify-self: stretch; }
  .tab button { padding: 7px 10px; }
  .kartu-judul { flex-wrap: wrap; }
}
</style>
