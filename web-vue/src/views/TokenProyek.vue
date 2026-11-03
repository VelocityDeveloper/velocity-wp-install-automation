<script setup>
// Token per project dengan rincian per alur (installer WordPress & Aplikasi Custom).
// Data: GET /api/ai/token-proyek (scripts/token_alur.py, dari /var/lib/velocity/ai/usage.jsonl).
import { ref, computed, watch } from 'vue'
import { pakaiPolling, angka, tanggalWaktu, waktuLalu } from '../api.js'
import { tabUrl } from '../laravel.js'
import Info from '../components/Info.vue'

const cari = tabUrl('cari', '')
const jenis = tabUrl('jenis', '', { boleh: ['wordpress', 'laravel'] })
const dari = tabUrl('dari', '')
const sampai = tabUrl('sampai', '')
const url = computed(() => `/api/ai/token-proyek?dari=${dari.value}&sampai=${sampai.value}`)
const { data, galat, muatUlang } = pakaiPolling(() => url.value, 60000)

// Polling berkala tetap senyap; ganti tanggal dan "Coba lagi" menampilkan tanda memuat.
const memperbarui = ref(false)
let nomorMuat = 0
const perbarui = async () => {
  const nomor = ++nomorMuat
  memperbarui.value = true
  await muatUlang()
  if (nomor === nomorMuat) memperbarui.value = false
}
watch(url, perbarui)

const JENIS = { wordpress: 'WordPress', laravel: 'Aplikasi Custom' }
const ringkasAngka = new Intl.NumberFormat('id-ID', { notation: 'compact', maximumFractionDigits: 1 })
const pendek = (n) => ringkasAngka.format(n || 0)
const formatUsd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const usd = (n) => (n > 0 && n < 0.01 ? '<$0.01' : formatUsd.format(n))
// Baris terputus punya token tanpa biaya, jadi biayanya tidak boleh tampak lengkap atau sama dengan "–" model gateway.
const biaya = (x) => {
  if (x.parsial) return x.biaya_usd ? `${usd(x.biaya_usd)} +?` : 'belum diketahui'
  return x.biaya_usd ? usd(x.biaya_usd) : '–'
}
const namaModel = (m) => m.replace(/^claude-/, '').replace(/-\d{8}$/, '')

const KOLOM_RINCI = [['input', 'Input'], ['cache_tulis', 'Cache tulis'], ['cache_baca', 'Cache baca'], ['output', 'Output'], ['panggilan', 'Panggilan']]
const PILIHAN_URUT = [['total', 'Total token'], ['biaya_usd', 'Biaya'], ['cache_baca', 'Cache baca'], ['output', 'Output'], ['panggilan', 'Panggilan'], ['id', 'Nama project']]
const urut = ref({ kolom: 'total', naik: false })
const urutkan = (kolom) => {
  urut.value = urut.value.kolom === kolom ? { kolom, naik: !urut.value.naik } : { kolom, naik: kolom === 'id' }
}
const kolomUrut = computed({
  get: () => urut.value.kolom,
  set: (kolom) => { urut.value = { kolom, naik: kolom === 'id' } },
})
const ariaUrut = (kolom) => (urut.value.kolom === kolom ? (urut.value.naik ? 'ascending' : 'descending') : 'none')

const proyek = computed(() => {
  const q = cari.value.trim().toLowerCase()
  const { kolom, naik } = urut.value
  return (data.value?.proyek || [])
    .filter((p) => (!jenis.value || p.jenis === jenis.value)
      && (!q || p.id.toLowerCase().includes(q) || (p.nama || '').toLowerCase().includes(q)))
    .sort((a, b) => {
      const beda = kolom === 'id'
        ? a.id.localeCompare(b.id, 'id', { numeric: true })
        : (a[kolom] || 0) - (b[kolom] || 0)
      return naik ? beda : -beda
    })
})
const LANGKAH = 30
const batas = ref(LANGKAH)
const tampil = computed(() => proyek.value.slice(0, batas.value))
watch([cari, jenis, dari, sampai, urut], () => { batas.value = LANGKAH })

const jumlah = computed(() => proyek.value.reduce((t, p) => {
  for (const k of ['total', 'input', 'cache_tulis', 'cache_baca', 'output', 'panggilan', 'biaya_usd', 'parsial']) t[k] += p[k] || 0
  return t
}, { total: 0, input: 0, cache_tulis: 0, cache_baca: 0, output: 0, panggilan: 0, biaya_usd: 0, parsial: 0 }))

// Pencarian yang menyisakan satu project (dari tautan installer) langsung membuka rinciannya, kecuali sudah ditutup manual
const dibuka = ref(new Set())
const ditutup = ref(new Set())
const terbuka = (p) => !ditutup.value.has(p.id) && (dibuka.value.has(p.id) || proyek.value.length === 1)
const alih = (p) => {
  const buka = new Set(dibuka.value)
  const tutup = new Set(ditutup.value)
  if (terbuka(p)) {
    buka.delete(p.id)
    tutup.add(p.id)
  } else {
    buka.add(p.id)
    tutup.delete(p.id)
  }
  dibuka.value = buka
  ditutup.value = tutup
}
// Alur dikelompokkan berurutan; baris kelompok muncul saat kelompoknya berganti
const barisAlur = (p) => {
  const hasil = []
  let kini = null
  for (const a of p.alur) {
    if (a.kelompok !== kini) {
      kini = a.kelompok
      const anggota = p.alur.filter((x) => x.kelompok === kini)
      const tambah = (k) => anggota.reduce((n, x) => n + (x[k] || 0), 0)
      hasil.push({ kelompok: kini, kunci: `k:${kini}`, total: tambah('total'), biaya_usd: tambah('biaya_usd'), parsial: tambah('parsial') })
    }
    hasil.push(a)
  }
  return hasil
}
const persen = (n, p) => {
  if (!p.total) return '–'
  const nilai = n / p.total * 100
  if (nilai > 0 && nilai < 0.1) return '<0,1%'
  return `${nilai.toLocaleString('id-ID', { maximumFractionDigits: 1 })}%`
}
// Pengganti kolom yang disembunyikan saat area tabel sempit
const rincian = (x) => `Input ${pendek(x.input)} · Tulis ${pendek(x.cache_tulis)} · Baca ${pendek(x.cache_baca)} · Output ${pendek(x.output)} · ${angka(x.panggilan)} panggilan`

// Tanggal WIB (YYYY-MM-DD), sama dengan halaman Token Usage
const hariWIB = (geser = 0) => {
  const d = new Date(Date.now() + 7 * 3600e3)
  d.setUTCDate(d.getUTCDate() + geser)
  return d.toISOString().slice(0, 10)
}
const RENTANG = [['7', '7 hari'], ['30', '30 hari'], ['semua', 'Semua']]
const rentangCepat = computed(() => {
  if (sampai.value) return ''
  if (!dari.value) return 'semua'
  return RENTANG.find(([k]) => k !== 'semua' && dari.value === hariWIB(-(Number(k) - 1)))?.[0] || ''
})
const pilihRentang = (k) => {
  dari.value = k === 'semua' ? '' : hariWIB(-(Number(k) - 1))
  sampai.value = ''
}
const tanggalBuka = ref(Boolean(dari.value || sampai.value))
// Di area sempit catatan dilipat supaya tabel tidak terdorong jauh
const catatanBuka = ref(false)
const adaSaringan = computed(() => Boolean(cari.value || jenis.value || dari.value || sampai.value))
const resetSaringan = () => {
  cari.value = ''
  jenis.value = ''
  dari.value = ''
  sampai.value = ''
}

const pesanGalat = computed(() => (data.value
  ? 'Data terbaru gagal dimuat. Angka di bawah masih dari pemuatan terakhir.'
  : 'Data token belum bisa dimuat. Bila terus gagal, muat ulang halaman.'))
const terakhirDipakai = computed(() => (data.value?.proyek || []).reduce((m, p) => (p.terakhir > m ? p.terakhir : m), ''))
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Token per Project</h1>
        <p class="redup">Token dan perkiraan biaya installer, per project dan per alur.</p>
      </div>
      <div class="kepala-kanan">
        <RouterLink to="/token" class="redup">← Token Usage</RouterLink>
        <span v-if="terakhirDipakai" class="redup" :title="tanggalWaktu(terakhirDipakai)">Pemakaian terakhir {{ waktuLalu(Date.parse(terakhirDipakai) / 1000) }}</span>
      </div>
    </header>

    <section class="kartu">
      <div class="saring-wadah">
        <div class="saring" role="group" aria-label="Saring">
          <input v-model="cari" class="f-cari" type="search" placeholder="Cari domain atau project" aria-label="Cari domain atau project">
          <select v-model="jenis" class="f-jenis" aria-label="Jenis project">
            <option value="">Semua installer</option>
            <option v-for="(l, k) in JENIS" :key="k" :value="k">{{ l }}</option>
          </select>
          <div class="f-cepat">
            <div class="segmen" role="radiogroup" aria-label="Rentang waktu">
              <button v-for="[k, l] in RENTANG" :key="k" type="button" role="radio" :aria-checked="rentangCepat === k" :class="{ aktif: rentangCepat === k }" @click="pilihRentang(k)">{{ l }}</button>
            </div>
            <button type="button" class="tombol garis kecil alih-tanggal" :aria-expanded="tanggalBuka" aria-controls="saring-tanggal" @click="tanggalBuka = !tanggalBuka">Tanggal</button>
            <button v-if="adaSaringan" type="button" class="tombol garis kecil" @click="resetSaringan">Reset saringan</button>
          </div>
          <div id="saring-tanggal" class="f-tanggal" :class="{ buka: tanggalBuka }">
            <label>
              <span class="redup">Dari</span>
              <input v-model="dari" type="date" :max="sampai || undefined">
            </label>
            <label>
              <span class="redup">Sampai</span>
              <input v-model="sampai" type="date" :min="dari || undefined">
            </label>
          </div>
        </div>
        <p class="catatan">
          Angka ini hanya dari installer. Pekerjaan manual lewat terminal atau bot belum termasuk, jadi total sebenarnya bisa lebih besar.
          <span id="catatan-lanjut" class="catatan-lanjut" :class="{ buka: catatanBuka }">
            Biaya adalah perkiraan menurut harga API Claude; model lain tampil "–".
            "Terputus" berarti proses berhenti sebelum selesai: tokennya terhitung, biayanya belum diketahui.
            <template v-if="data">Pemakaian di luar project, seperti agen internal dan laporan ({{ pendek(data.di_luar_project.total) }} token), tidak dihitung.</template>
          </span>
          <button type="button" class="alih-catatan" :aria-expanded="catatanBuka" aria-controls="catatan-lanjut" @click="catatanBuka = !catatanBuka">{{ catatanBuka ? 'Ringkas' : 'Selengkapnya' }}</button>
        </p>
      </div>

      <div v-if="galat" class="kotak-galat" role="alert">
        <span>{{ pesanGalat }}</span>
        <button type="button" class="tombol garis kecil" :disabled="memperbarui" @click="perbarui">{{ memperbarui ? 'Memuat…' : 'Coba lagi' }}</button>
      </div>

      <p v-if="data && (proyek.length || memperbarui)" class="redup ringkas">
        <template v-if="proyek.length">
          <b>{{ angka(proyek.length) }}</b> project · <b :title="angka(jumlah.total)">{{ pendek(jumlah.total) }}</b> token ·
          <b>{{ angka(jumlah.panggilan) }}</b> panggilan model · perkiraan biaya <b>{{ biaya(jumlah) }}</b>
        </template>
        <span v-if="memperbarui" class="status-muat" role="status">Memperbarui…</span>
      </p>

      <div v-if="data || !galat || memperbarui" class="tabel-wadah">
        <label class="urut-hp">
          <span class="redup">Urutkan</span>
          <select v-model="kolomUrut">
            <option v-for="[k, l] in PILIHAN_URUT" :key="k" :value="k">{{ l }}</option>
          </select>
        </label>
        <table class="tabel" :class="{ redupkan: memperbarui && data }" :aria-busy="memperbarui">
          <thead>
            <tr>
              <th :aria-sort="ariaUrut('id')">
                <button type="button" class="urut" :class="{ aktif: urut.kolom === 'id' }" @click="urutkan('id')">
                  Project / alur<span class="urut-panah" aria-hidden="true">{{ urut.kolom === 'id' ? (urut.naik ? '▲' : '▼') : '↕' }}</span>
                </button>
              </th>
              <th class="kanan" :aria-sort="ariaUrut('total')">
                <button type="button" class="urut" :class="{ aktif: urut.kolom === 'total' }" @click="urutkan('total')">
                  Total<span class="urut-panah" aria-hidden="true">{{ urut.kolom === 'total' ? (urut.naik ? '▲' : '▼') : '↕' }}</span>
                </button>
                <div v-if="proyek.length" class="jumlah-kolom" :title="angka(jumlah.total)">{{ pendek(jumlah.total) }}</div>
              </th>
              <th class="kanan kolom-rinci">
                Porsi
                <Info label="Tentang kolom Porsi" rata="kanan">
                  <p>Baris project: bagian dari total semua project yang tampil.</p>
                  <p>Baris kelompok dan alur: bagian dari total project-nya.</p>
                </Info>
              </th>
              <th v-for="[k, l] in KOLOM_RINCI" :key="k" class="kanan kolom-rinci" :aria-sort="ariaUrut(k)">
                <button type="button" class="urut" :class="{ aktif: urut.kolom === k }" @click="urutkan(k)">
                  {{ l }}<span class="urut-panah" aria-hidden="true">{{ urut.kolom === k ? (urut.naik ? '▲' : '▼') : '↕' }}</span>
                </button>
                <div v-if="proyek.length" class="jumlah-kolom" :title="angka(jumlah[k])">{{ pendek(jumlah[k]) }}</div>
              </th>
              <th class="kanan" :aria-sort="ariaUrut('biaya_usd')">
                <button type="button" class="urut" :class="{ aktif: urut.kolom === 'biaya_usd' }" @click="urutkan('biaya_usd')">
                  Biaya<span class="urut-panah" aria-hidden="true">{{ urut.kolom === 'biaya_usd' ? (urut.naik ? '▲' : '▼') : '↕' }}</span>
                </button>
                <div v-if="proyek.length" class="jumlah-kolom">{{ biaya(jumlah) }}</div>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!data" class="baris-pesan"><td colspan="9" class="redup">Memuat…</td></tr>
            <tr v-else-if="!proyek.length" class="baris-pesan">
              <td colspan="9" class="redup">
                <template v-if="adaSaringan">
                  Tidak ada pemakaian yang cocok dengan saringan ini.
                  <button type="button" class="tombol garis kecil tombol-reset" @click="resetSaringan">Reset saringan</button>
                </template>
                <template v-else>Belum ada pemakaian token yang tercatat.</template>
              </td>
            </tr>
            <template v-for="p in tampil" :key="p.id">
              <tr class="baris-proyek" :class="{ terbuka: terbuka(p) }">
                <td>
                  <button type="button" class="buka" :aria-expanded="terbuka(p)" @click="alih(p)">
                    <span class="panah" aria-hidden="true">{{ terbuka(p) ? '▾' : '▸' }}</span>
                    <span class="isi-buka">
                      <b>{{ p.id }}</b> <span class="lencana abu">{{ JENIS[p.jenis] }}</span>
                      <span v-if="p.parsial" class="lencana kuning" title="Ada proses yang terputus, jadi biaya project ini lebih besar dari angka yang tampil">ada biaya belum lengkap</span>
                      <span v-if="p.nama" class="kecil">{{ p.nama }}</span>
                      <span class="kecil">{{ p.alur.length }} alur · terakhir {{ tanggalWaktu(p.terakhir) }}</span>
                      <span class="rincian-ringkas">{{ persen(p.total, jumlah) }} dari total tampil · {{ rincian(p) }}</span>
                      <span v-if="p.parsial && terbuka(p)" class="ket-terputus">Terputus: proses berhenti sebelum selesai. Tokennya terhitung, biayanya belum diketahui.</span>
                    </span>
                  </button>
                </td>
                <td class="kanan" data-label="Total" :title="angka(p.total)"><b>{{ pendek(p.total) }}</b></td>
                <td class="kanan redup kolom-rinci">{{ persen(p.total, jumlah) }}</td>
                <td v-for="[k] in KOLOM_RINCI" :key="k" class="kanan kolom-rinci" :title="angka(p[k])">{{ pendek(p[k]) }}</td>
                <td class="kanan" data-label="Biaya">{{ biaya(p) }}</td>
              </tr>
              <template v-if="terbuka(p)">
                <template v-for="a in barisAlur(p)" :key="p.id + a.kunci">
                  <tr v-if="a.kelompok && !a.label" class="baris-kelompok">
                    <td>{{ a.kelompok }}</td>
                    <td class="kanan" data-label="Total" :title="angka(a.total)">{{ pendek(a.total) }}</td>
                    <td class="kanan kolom-rinci">{{ persen(a.total, p) }}</td>
                    <td colspan="5" class="kolom-rinci" />
                    <td class="kanan" data-label="Biaya">{{ biaya(a) }}</td>
                  </tr>
                  <tr v-else class="baris-alur">
                    <td>
                      {{ a.label }}<template v-if="a.judul"> · <span class="redup">{{ a.judul }}</span></template>
                      <span v-if="a.gagal" class="lencana merah" :title="`${a.gagal} catatan gagal`">{{ a.gagal }} gagal</span>
                      <span v-if="a.parsial" class="lencana kuning" title="Proses berhenti sebelum selesai: token terhitung dari langkah yang sudah jalan, biaya belum diketahui">{{ a.parsial }} terputus</span>
                      <span class="kecil" :title="`Terakhir ${tanggalWaktu(a.terakhir)}`">{{ a.model.map(namaModel).join(', ') }}</span>
                      <span class="rincian-ringkas">{{ persen(a.total, p) }} dari project · {{ rincian(a) }}</span>
                    </td>
                    <td class="kanan" data-label="Total" :title="angka(a.total)">{{ pendek(a.total) }}</td>
                    <td class="kanan redup kolom-rinci">{{ persen(a.total, p) }}</td>
                    <td v-for="[k] in KOLOM_RINCI" :key="k" class="kanan kolom-rinci" :title="angka(a[k])">{{ pendek(a[k]) }}</td>
                    <td class="kanan" data-label="Biaya">{{ biaya(a) }}</td>
                  </tr>
                </template>
              </template>
            </template>
          </tbody>
        </table>
      </div>
      <div v-if="proyek.length > tampil.length" class="lebih">
        <button type="button" class="tombol garis kecil" @click="batas += LANGKAH">Tampilkan lebih banyak</button>
        <span class="redup">{{ angka(tampil.length) }} dari {{ angka(proyek.length) }} project</span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; min-width: 0; }
.kepala-kanan { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
@media (max-width: 700px) { .kepala-kanan { flex-direction: row; flex-wrap: wrap; gap: 2px 12px; } }

/* Saringan: tata letak mengikuti lebar kartu, bukan layar, karena sidebar ikut memakan tempat */
.saring-wadah { container-type: inline-size; margin-bottom: 12px; }
.saring { margin-bottom: 12px; }
.saring { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 2fr); gap: 10px; align-items: end; }
.f-cari { grid-column: 1; grid-row: 1; }
.f-jenis { grid-column: 2; grid-row: 1; }
.f-tanggal { grid-column: 3; grid-row: 1; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px; }
.f-tanggal label { display: grid; gap: 3px; min-width: 0; }
.f-cepat { grid-column: 1 / -1; grid-row: 2; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.alih-tanggal { display: none; }
.segmen { display: inline-flex; padding: 3px; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--panel); }
.segmen button { border: 0; background: transparent; color: var(--teks-2); padding: 6px 12px; border-radius: 8px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; }
.segmen button.aktif { background: var(--aksen); color: #fff; }
.segmen button:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
@container (max-width: 759px) {
  .saring { grid-template-columns: minmax(0, 1fr); }
  .f-cari, .f-jenis, .f-cepat, .f-tanggal { grid-column: 1; grid-row: auto; }
  .alih-tanggal { display: inline-flex; align-items: center; }
  .f-tanggal { display: none; }
  .f-tanggal.buka { display: grid; }
  .segmen button { padding: 6px 10px; }
  .catatan-lanjut:not(.buka) { display: none; }
}

.catatan { margin: 0; padding: 9px 12px; border-radius: 10px; background: var(--kartu-2); color: var(--teks-2); font-size: 12.5px; line-height: 1.5; }
.alih-catatan { display: none; padding: 0; border: 0; background: transparent; color: var(--aksen-terang); font: inherit; font-weight: 600; cursor: pointer; }
.alih-catatan:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 2px; border-radius: 4px; }
@container (max-width: 759px) { .alih-catatan { display: inline; } }
.kotak-galat { display: flex; align-items: center; justify-content: space-between; gap: 8px 12px; flex-wrap: wrap; margin-bottom: 12px; padding: 9px 12px; border: 1px solid rgba(255, 107, 107, .5); border-radius: 10px; color: var(--bahaya); font-size: 13px; }
.ringkas { margin: 0 0 10px; }
.ringkas b { color: var(--teks); }
.status-muat { margin-left: 6px; color: var(--aksen-terang); font-weight: 600; }

/* overflow terlihat supaya kepala tabel bisa menempel saat halaman digulir; lebar tabel diatur container query di bawah */
.tabel-wadah { container-type: inline-size; overflow: visible; }
.tabel { transition: opacity .15s; }
.tabel.redupkan { opacity: .55; }
.tabel th, .tabel td { padding-left: 5px; padding-right: 5px; font-size: 13px; }
.tabel th { position: sticky; top: 0; z-index: 2; background: var(--kartu); border-bottom: 0; box-shadow: inset 0 -1px 0 var(--garis); vertical-align: bottom; }
.tabel th:first-child, .tabel td:first-child { width: 34%; min-width: 150px; }
.kanan { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.urut { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
.urut:hover, .urut.aktif { color: var(--teks); }
.urut:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 2px; border-radius: 4px; }
.urut-panah { font-size: 10px; opacity: .45; }
.urut.aktif .urut-panah { opacity: 1; }
.jumlah-kolom { margin-top: 3px; font-size: 12px; font-weight: 600; color: var(--teks); }
.urut-hp { display: none; align-items: center; gap: 8px; margin-bottom: 8px; }
.urut-hp select { width: auto; flex: 1; min-width: 0; }

.buka { all: unset; display: flex; gap: 8px; cursor: pointer; }
.buka:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 2px; }
.isi-buka { min-width: 0; }
.buka b { overflow-wrap: anywhere; }
.panah { color: var(--teks-3); width: 12px; flex: none; }
.rincian-ringkas { display: none; margin-top: 2px; color: var(--teks-2); font-size: 12px; font-variant-numeric: tabular-nums; }
.ket-terputus { display: block; margin-top: 4px; color: var(--waspada); font-size: 12px; }
.baris-proyek.terbuka td { background: var(--kartu-2); }
.baris-kelompok td { font-size: 12px; font-weight: 700; color: var(--teks-2); padding-top: 12px; padding-bottom: 4px; }
.baris-kelompok td:first-child { padding-left: 30px; }
.baris-alur td:first-child { padding-left: 42px; }
.tombol-reset { margin-left: 8px; }
.lebih { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 12px; }

/* Kolom rincian disembunyikan menurut lebar area tabel; angkanya pindah ke .rincian-ringkas */
@container (max-width: 899px) {
  .kolom-rinci { display: none; }
  .rincian-ringkas { display: block; }
  .tabel th:first-child, .tabel td:first-child { width: 100%; min-width: 0; }
}
/* Area sempit: tiap baris jadi grid. Nama selebar penuh, Total dan Biaya di bawahnya */
@container (max-width: 559px) {
  .urut-hp { display: flex; }
  .tabel, .tabel tbody { display: block; }
  .tabel thead { display: none; }
  .tabel tr { display: grid; grid-template-columns: minmax(0, 1fr) auto; border-bottom: 1px solid var(--garis); }
  .tabel td { border-bottom: 0; }
  .tabel td:first-child { grid-column: 1 / -1; padding-bottom: 2px; }
  .tabel td.kanan { padding-top: 2px; padding-bottom: 10px; }
  .tabel td.kanan::before { content: attr(data-label) " "; color: var(--teks-3); font-size: 12px; font-weight: 400; }
  .baris-pesan td:first-child { padding-bottom: 11px; }
  .baris-kelompok td:first-child { padding-left: 20px; }
  .baris-alur td:first-child { padding-left: 30px; }
}
@media (max-width: 960px) {
  .tabel th { top: 61px; }
}
</style>
