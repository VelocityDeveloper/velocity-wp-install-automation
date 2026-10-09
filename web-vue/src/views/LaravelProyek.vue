<script setup>
// Satu project Laravel: kepala (identitas + relasi On Progress), stepper tahap, dan isi tahap yang dipilih.
// Data dipoll: 3 dtk selama ada proses latar (Claude/installer/agen), 15 dtk bila tidak.
import { ref, reactive, computed, watch, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import PilihOnProgress from '../components/laravel/PilihOnProgress.vue'
import PilihNama from '../components/laravel/PilihNama.vue'
import TahapBrief from '../components/laravel/TahapBrief.vue'
import TahapEstimasi from '../components/laravel/TahapEstimasi.vue'
import TahapInstall from '../components/laravel/TahapInstall.vue'
import TahapAgen from '../components/laravel/TahapAgen.vue'
import TahapReview from '../components/laravel/TahapReview.vue'
import PeringatanReview from '../components/laravel/PeringatanReview.vue'
import UbahStatus from '../components/laravel/UbahStatus.vue'
import HapusProyek from '../components/laravel/HapusProyek.vue'
import { minta, tanggalWaktu } from '../api.js'
import { namaSaya, STATUS_PROYEK, TAHAP, indeksTahap, aksi, pesanGalat, tabUrl, reviewMendesak, jalurLaravel } from '../laravel.js'

const route = useRoute()
const router = useRouter()
const id = computed(() => route.params.id)
const d = ref(null)
const pilihan = tabUrl('tab', '', { sendiri: true })  // tab yang dipilih manual (?tab=); kosong = tahap sekarang
const galat = ref('')
let timer = null
async function muat() {
  try {
    d.value = await minta(`/api/laravel/p/${id.value}`)
    galat.value = ''
  } catch (e) {
    galat.value = e.message === 'tidak_ada' ? 'Project tidak ditemukan.' : e.message
  }
  clearTimeout(timer)
  timer = setTimeout(muat, d.value?.job ? 3000 : 15000)
}
watch(id, () => { d.value = null; muat() }, { immediate: true })
onBeforeUnmount(() => clearTimeout(timer))

// Lama job berjalan (d.job.mulai = epoch detik), berdetak tiap detik
const kini = ref(Date.now())
const detak = setInterval(() => { kini.value = Date.now() }, 1000)
onBeforeUnmount(() => clearInterval(detak))
const lamaJob = computed(() => {
  const m = d.value?.job?.mulai
  if (!m) return ''
  const s = Math.max(0, Math.floor(kini.value / 1000 - m))
  return s < 60 ? `${s} dtk` : s < 3600 ? `${Math.floor(s / 60)} mnt ${s % 60} dtk` : `${Math.floor(s / 3600)} jam ${Math.floor((s % 3600) / 60)} mnt`
})

const tabAktif = computed(() => (KOMPONEN[pilihan.value] && pilihan.value) || (d.value?.tahap === 'selesai' ? 'review' : d.value?.tahap) || 'brief')
const JOB = { saran: 'Claude sedang membandingkan platform (WordPress / Laravel+Vue / lainnya)', susun: 'Claude sedang menyusun DESIGN.md + PRD, lalu relasi database & flowchart', diagram: 'Claude sedang menyusun relasi database & flowchart', estimasi: 'Claude sedang memecah fitur & estimasi', contoh: 'Claude sedang membuat contoh tampilan untuk klien', rangkuman: 'Claude sedang menyusun Rangkuman Website Konsep', install: 'Install berjalan', agen: 'Agen Claude sedang bekerja' }
// Platform bukan Laravel + Vue (7 Okt): Install/Agen/Review khusus Laravel → diganti satu langkah penutup yang mengarah
// ke tempat situs dibangun (WordPress → Installer WordPress; lainnya → dikerjakan di luar installer)
const LANGKAH_LUAR = {
  wordpress: { kunci: 'luar', label: 'Installer WordPress', ket: 'Situs dibangun di sana', ke: '/installer/wordpress' },
  lainnya: { kunci: 'luar', label: 'Di luar installer', ket: 'Dikerjakan manual' },
}
const langkah = computed(() => {
  if (!d.value || jalurLaravel(d.value)) return TAHAP
  return [...TAHAP.slice(0, 2), LANGKAH_LUAR[d.value.saran.pilihan.jalur] || LANGKAH_LUAR.lainnya]
})
function klikLangkah(t) {
  if (t.kunci !== 'luar') pilihan.value = t.kunci
  else if (t.ke) router.push(t.ke)
}
const KOMPONEN = { brief: TahapBrief, estimasi: TahapEstimasi, install: TahapInstall, agen: TahapAgen, review: TahapReview }

// Ubah identitas (sebelum install)
const dialogBuka = ref(false)
const ident = reactive({ judul: '', klien: '', onprogress: '', domain: '' })
const identStatus = ref('')
const terinstall = computed(() => ['jalan', 'ok'].includes(d.value?.install?.status))
// Kartu Contoh tampilan ada di tab Brief; tombol di kepala halaman membuka tab itu lalu menggulir ke kartunya
async function keContoh() {
  pilihan.value = 'brief'
  await nextTick()
  document.getElementById('contoh-tampilan')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function bukaIdentitas() {
  Object.assign(ident, { judul: d.value.judul, klien: d.value.klien || '', onprogress: d.value.onprogress || '', domain: d.value.domain || '' })
  identStatus.value = ''
  dialogBuka.value = true
}
// Status project: brief tidak deal → Batal/Ditunda (aksi lain dikunci server sampai diaktifkan lagi)
const statusBuka = ref(false)
const hapusBuka = ref(false)
const mengaktifkan = ref(false)
const nonaktif = computed(() => (d.value?.status_proyek || 'aktif') !== 'aktif')
async function aktifkan() {
  mengaktifkan.value = true
  try { await aksi(id.value, 'status', { nilai: 'aktif' }); muat() } catch (e) { galat.value = pesanGalat(e) } finally { mengaktifkan.value = false }
}
async function simpanIdentitas() {
  try {
    await aksi(id.value, 'identitas', { ...ident })
    dialogBuka.value = false
    muat()
  } catch (e) { identStatus.value = pesanGalat(e) }
}
</script>

<template>
  <div class="halaman">
    <RouterLink to="/installer/laravel" class="kembali redup">← Semua Aplikasi Custom</RouterLink>
    <p v-if="galat && !d" class="pesan-status bahaya">{{ galat }}</p>
    <p v-else-if="!d" class="redup">Memuat…</p>
    <template v-else>
      <header class="kepala-halaman">
        <div>
          <p class="id"><code>{{ d.slug }}</code><span v-if="d.app"> · aplikasi <code>{{ d.app }}</code></span> · brief <b>v{{ d.brief?.versi || 0 }}</b></p>
          <h1>{{ d.judul }}</h1>
          <p class="redup">
            <template v-if="d.klien">{{ d.klien }} · </template>
            <template v-if="d.onprogress">On Progress: <b>{{ d.onprogress }}</b></template><template v-else>belum ada relasi On Progress</template>
            <template v-if="d.domain"> · {{ d.domain }}</template>
            · PM {{ d.pm }} · dibuat {{ tanggalWaktu(d.dibuat) }}
          </p>
        </div>
        <div class="kanan">
          <div class="nama-saya"><label for="nama-saya" class="redup">Nama Anda</label><PilihNama :tim="d.tim" /></div>
          <a v-if="d.contoh?.terbit?.ok" class="tombol kecil" :href="d.contoh.terbit.url" target="_blank" rel="noopener"><Ikon nama="luar" :ukuran="16" /> Preview klien</a>
          <button v-else type="button" class="tombol garis kecil" @click="keContoh"><Ikon nama="claude" :ukuran="16" /> {{ d.contoh ? 'Contoh tampilan' : 'Buat contoh tampilan' }}</button>
          <button v-if="d.contoh" type="button" class="tombol garis kecil" @click="keContoh">Kelola contoh</button>
          <button type="button" class="tombol garis kecil" @click="statusBuka = true">Status: {{ STATUS_PROYEK[d.status_proyek || 'aktif']?.label }}</button>
          <button v-if="!terinstall" type="button" class="tombol garis kecil" @click="bukaIdentitas"><Ikon nama="sunting" :ukuran="16" /> Ubah identitas / relasi</button>
          <button v-if="!d.app && !d.install?.status" type="button" class="tombol bahaya kecil" @click="hapusBuka = true"><Ikon nama="sampah" :ukuran="16" /> Hapus</button>
        </div>
      </header>

      <div v-if="nonaktif" class="kartu status-nonaktif" :class="STATUS_PROYEK[d.status_proyek]?.kelas" role="status">
        <div>
          <b>Project {{ STATUS_PROYEK[d.status_proyek]?.label.toLowerCase() }}</b>
          <span class="redup" v-if="d.status_info"> — oleh {{ d.status_info.oleh }}, {{ tanggalWaktu(d.status_info.waktu) }}</span>
          <p v-if="d.status_info?.alasan">{{ d.status_info.alasan }}</p>
          <p class="redup">Semua aksi dikunci dan project tidak tampil di daftar aktif. Data tetap tersimpan.</p>
        </div>
        <button type="button" class="tombol kecil" :disabled="!namaSaya.trim() || mengaktifkan" @click="aktifkan">Aktifkan kembali</button>
      </div>

      <div v-if="!namaSaya.trim()" class="kartu minta-nama" role="status">
        <label for="nama-saya-cepat"><b>Siapa Anda?</b> Pilih nama Anda (daftar PM &amp; webmaster dari CRM). Nama dicatat di riwayat setiap aksi; cukup sekali — tersimpan di browser ini.</label>
        <PilihNama id="nama-saya-cepat" :tim="d.tim" class="cepat" />
      </div>

      <div v-if="d.job" class="kartu proses" role="status">
        <span class="putar" aria-hidden="true" />
        <span>{{ JOB[d.job.jenis] || d.job.jenis }}…</span>
        <span v-if="lamaJob" class="lama">berjalan {{ lamaJob }}</span>
        <i class="garis-jalan" aria-hidden="true" />
      </div>

      <nav class="stepper" :class="{ jalan: d.job }" :style="{ '--kolom': langkah.length }" aria-label="Tahap project">
        <button v-for="(t, i) in langkah" :key="t.kunci" type="button" :aria-current="tabAktif === t.kunci ? 'step' : undefined"
          :class="{ lewat: i < indeksTahap(d.tahap), kini: i === indeksTahap(d.tahap), aktif: tabAktif === t.kunci, luar: t.kunci === 'luar', mati: t.kunci === 'luar' && !t.ke }"
          :disabled="t.kunci === 'luar' && !t.ke" :title="t.kunci === 'luar' ? 'Install, Agen, dan Review hanya untuk platform Laravel + Vue' : undefined" @click="klikLangkah(t)">
          <span class="nomor">{{ t.kunci === 'luar' ? '→' : i < indeksTahap(d.tahap) ? '✓' : i + 1 }}</span>
          <span><b>{{ t.label }}</b><small>{{ t.ket }}</small></span>
          <span v-if="t.kunci === 'review' && d.review?.menunggu" class="tunggu" :class="{ mendesak: reviewMendesak(d.review) }" :title="`${d.review.menunggu} fitur menunggu review`">{{ d.review.menunggu }}</span>
        </button>
      </nav>

      <PeringatanReview v-if="d.review?.menunggu && (tabAktif !== 'review' || d.review.tertahan)" :r="d.review" @buka="pilihan = 'review'" />

      <component :is="KOMPONEN[tabAktif]" :d="d" @ubah="muat" />

      <details class="kartu riwayat">
        <summary>Riwayat ({{ d.riwayat.length }})</summary>
        <ul>
          <li v-for="(r, i) in d.riwayat" :key="i"><span class="redup">{{ tanggalWaktu(r.waktu) }}</span> <b>{{ r.oleh }}</b> {{ r.aksi }}</li>
        </ul>
      </details>
    </template>

    <UbahStatus :p="statusBuka ? d : null" @tutup="statusBuka = false" @ubah="muat" />
    <HapusProyek :p="hapusBuka ? d : null" @tutup="hapusBuka = false" @hapus="router.push('/installer/laravel')" />

    <Dialog :buka="dialogBuka" judul="Identitas project" lebar="560px" @tutup="dialogBuka = false">
      <form class="formulir" @submit.prevent="simpanIdentitas">
        <label class="isian"><span>Judul aplikasi</span><input v-model="ident.judul" required maxlength="80" autofocus></label>
        <label class="isian"><span>Klien</span><input v-model="ident.klien" maxlength="80"></label>
        <div class="isian">
          <label for="op-ubah"><span class="label">Relasi On Progress</span></label>
          <PilihOnProgress id="op-ubah" v-model="ident.onprogress" :kecuali="d?.slug" />
        </div>
        <label class="isian"><span>Domain produksi</span><input v-model="ident.domain" maxlength="80" placeholder="otomatis dari relasi bila berupa domain" spellcheck="false">
          <small>Dipakai deploy-prod.sh.</small></label>
        <p v-if="identStatus" class="pesan-status bahaya">{{ identStatus }}</p>
        <div class="aksi-dialog">
          <button type="button" class="tombol garis" @click="dialogBuka = false">Batal</button>
          <button type="submit" class="tombol" :disabled="!namaSaya.trim()">Simpan</button>
        </div>
      </form>
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; max-width: 1100px; }
.kembali { font-size: 13px; width: fit-content; }
.id { margin: 0 0 4px !important; color: var(--teks-3); font-size: 12.5px; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks-2); }
.kepala-halaman b { color: var(--teks); font-weight: 600; }
.kanan { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; }
.kanan a.tombol { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; }
.nama-saya { display: grid; gap: 4px; min-width: 180px; }
.nama-saya > label { font-size: 12px; }
.minta-nama { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; padding: 12px 16px; border-color: rgba(232, 181, 74, .55); background: rgba(232, 181, 74, .08); }
.minta-nama label { flex: 1 1 320px; color: var(--teks-2); font-size: 13.5px; }
.minta-nama b { color: var(--waspada); }
.minta-nama .cepat { flex: 0 1 260px; }
/* Banner proses: cincin berputar, kilau menyapu, garis tak tentu di bawah */
.proses { position: relative; overflow: hidden; isolation: isolate; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 12px 16px 14px; border-color: rgba(232, 181, 74, .45); color: var(--waspada); font-weight: 600; }
.proses::after { content: ''; position: absolute; inset: 0; z-index: -1; pointer-events: none;
  background: linear-gradient(100deg, transparent 30%, rgba(232, 181, 74, .12) 50%, transparent 70%) no-repeat;
  background-size: 250% 100%; animation: kilau 2.8s ease-in-out infinite; }
.proses .lama { margin-left: auto; font-weight: 500; font-size: 12.5px; color: var(--teks-3); font-variant-numeric: tabular-nums; }
.putar { width: 14px; height: 14px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: putar .8s linear infinite; flex: none; }
.garis-jalan { position: absolute; left: 0; right: 0; bottom: 0; height: 3px; background: rgba(232, 181, 74, .15); overflow: hidden; }
.garis-jalan::before { content: ''; position: absolute; top: 0; bottom: 0; width: 35%; border-radius: 3px; background: var(--waspada); animation: geser 1.6s ease-in-out infinite; }
/* Tahap yang sedang dikerjakan: nomor bercincin berputar + garis bawah mengalir */
.stepper.jalan .kini { position: relative; overflow: hidden; }
.stepper.jalan .kini .nomor { position: relative; }
.stepper.jalan .kini .nomor::after { content: ''; position: absolute; inset: -4px; border-radius: 50%; border: 2px solid var(--aksen-terang); border-right-color: transparent; border-bottom-color: transparent; animation: putar 1s linear infinite; }
.stepper.jalan .kini::after { content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 3px;
  background: linear-gradient(90deg, var(--aksen-lembut) 0%, var(--aksen-terang) 40%, var(--aksen-lembut) 80%) 0 0 / 200% 100%; animation: alir 1.4s linear infinite; }
@keyframes kilau { from { background-position: 150% 0; } to { background-position: -150% 0; } }
@keyframes putar { to { transform: rotate(360deg); } }
@keyframes geser { from { left: -35%; } to { left: 100%; } }
@keyframes alir { from { background-position: 200% 0; } to { background-position: 0 0; } }
@media (prefers-reduced-motion: reduce) {
  .proses::after, .putar, .garis-jalan::before, .stepper.jalan .kini .nomor::after, .stepper.jalan .kini::after { animation: none; }
}
.stepper { display: grid; grid-template-columns: repeat(var(--kolom, 5), minmax(0, 1fr)); gap: 8px; }
.stepper .luar { border-style: dashed; }
.stepper .luar .nomor { background: var(--aksen-lembut); color: var(--aksen-terang); }
.stepper .mati { cursor: default; opacity: .7; }
.stepper button { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 12px; border: 1px solid var(--garis); background: var(--kartu); cursor: pointer; text-align: left; color: var(--teks-3); min-width: 0; }
.stepper button b { display: block; font-size: 13.5px; color: inherit; }
.stepper button small { display: block; font-size: 11.5px; color: var(--teks-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stepper button > span:last-child { min-width: 0; }
.nomor { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; flex: none; font-size: 12px; font-weight: 700; background: var(--kartu-2); }
.stepper .lewat { color: var(--teks-2); }
.stepper .lewat .nomor { background: rgba(52, 199, 123, .16); color: var(--baik); }
.stepper .kini { color: var(--teks); }
.stepper .kini .nomor { background: var(--aksen); color: #fff; }
.stepper .aktif { border-color: var(--aksen-terang); background: var(--kartu-2); }
/* Jumlah fitur menunggu review di langkah Review */
.stepper button { position: relative; }
.tunggu { position: absolute; top: 6px; right: 6px; min-width: 20px; height: 20px; padding: 0 6px; border-radius: 999px; display: grid; place-items: center; font-size: 11.5px; font-weight: 700; background: var(--waspada); color: #1a1205; }
.tunggu.mendesak { background: var(--bahaya); color: #fff; }
.status-nonaktif { display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap; padding: 12px 16px; }
.status-nonaktif p { margin: 4px 0 0; font-size: 13.5px; }
.status-nonaktif.bahaya { border-color: rgba(255, 107, 107, .55); background: rgba(255, 107, 107, .06); }
.status-nonaktif.bahaya > div > b { color: var(--bahaya); }
.status-nonaktif.info { border-color: rgba(91, 140, 255, .55); background: var(--aksen-lembut); }
.status-nonaktif.info > div > b { color: var(--aksen-terang); }
.status-nonaktif.waspada { border-color: rgba(232, 181, 74, .55); background: rgba(232, 181, 74, .08); }
.status-nonaktif.waspada > div > b { color: var(--waspada); }
.riwayat summary { cursor: pointer; font-weight: 600; }
.riwayat ul { margin: 12px 0 0; padding: 0; list-style: none; display: grid; gap: 6px; font-size: 13px; max-height: 320px; overflow: auto; }
.formulir { display: grid; gap: 14px; }
.isian .label { font-size: 13px; font-weight: 600; color: var(--teks-2); }
@media (max-width: 760px) {
  .stepper { grid-template-columns: repeat(var(--kolom, 5), minmax(0, 1fr)); }
  .stepper button { flex-direction: column; gap: 4px; padding: 8px 4px; text-align: center; }
  .stepper button small { display: none; }
  .stepper button b { font-size: 12px; }
}
</style>
