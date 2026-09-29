<script setup>
// Satu project Laravel: kepala (identitas + relasi On Progress), stepper tahap, dan isi tahap yang dipilih.
// Data dipoll: 3 dtk selama ada proses latar (Claude/installer/agen), 15 dtk bila tidak.
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import PilihOnProgress from '../components/laravel/PilihOnProgress.vue'
import PilihNama from '../components/laravel/PilihNama.vue'
import TahapBrief from '../components/laravel/TahapBrief.vue'
import TahapEstimasi from '../components/laravel/TahapEstimasi.vue'
import TahapInstall from '../components/laravel/TahapInstall.vue'
import TahapAgen from '../components/laravel/TahapAgen.vue'
import TahapReview from '../components/laravel/TahapReview.vue'
import { minta, tanggalWaktu } from '../api.js'
import { namaSaya, TAHAP, indeksTahap, aksi, pesanGalat } from '../laravel.js'

const route = useRoute()
const id = computed(() => route.params.id)
const d = ref(null)
const pilihan = ref('')  // tab yang dipilih manual; kosong = tahap sekarang
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
watch(id, () => { d.value = null; pilihan.value = ''; muat() }, { immediate: true })
onBeforeUnmount(() => clearTimeout(timer))

const tabAktif = computed(() => pilihan.value || (d.value?.tahap === 'selesai' ? 'review' : d.value?.tahap) || 'brief')
const JOB = { susun: 'Claude sedang menyusun DESIGN.md + PRD, lalu relasi database & flowchart', diagram: 'Claude sedang menyusun relasi database & flowchart', estimasi: 'Claude sedang memecah fitur & estimasi', install: 'Install berjalan', agen: 'Agen Claude sedang bekerja' }
const KOMPONEN = { brief: TahapBrief, estimasi: TahapEstimasi, install: TahapInstall, agen: TahapAgen, review: TahapReview }

// Ubah identitas (sebelum install)
const dialogBuka = ref(false)
const ident = reactive({ judul: '', klien: '', onprogress: '', domain: '' })
const identStatus = ref('')
const terinstall = computed(() => ['jalan', 'ok'].includes(d.value?.install?.status))
function bukaIdentitas() {
  Object.assign(ident, { judul: d.value.judul, klien: d.value.klien || '', onprogress: d.value.onprogress || '', domain: d.value.domain || '' })
  identStatus.value = ''
  dialogBuka.value = true
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
          <p class="id"><code>{{ d.slug }}</code><span v-if="d.app"> · aplikasi <code>{{ d.app }}</code></span></p>
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
          <button v-if="!terinstall" type="button" class="tombol garis kecil" @click="bukaIdentitas"><Ikon nama="sunting" :ukuran="16" /> Ubah identitas / relasi</button>
        </div>
      </header>

      <div v-if="!namaSaya.trim()" class="kartu minta-nama" role="status">
        <label for="nama-saya-cepat"><b>Siapa Anda?</b> Pilih nama Anda (daftar PM &amp; webmaster dari CRM). Nama dicatat di riwayat setiap aksi; cukup sekali — tersimpan di browser ini.</label>
        <PilihNama id="nama-saya-cepat" :tim="d.tim" class="cepat" />
      </div>

      <div v-if="d.job" class="kartu proses" role="status"><span class="titik" aria-hidden="true" /> {{ JOB[d.job.jenis] || d.job.jenis }}…</div>

      <nav class="stepper" aria-label="Tahap project">
        <button v-for="(t, i) in TAHAP" :key="t.kunci" type="button" :aria-current="tabAktif === t.kunci ? 'step' : undefined"
          :class="{ lewat: i < indeksTahap(d.tahap), kini: i === indeksTahap(d.tahap), aktif: tabAktif === t.kunci }" @click="pilihan = t.kunci">
          <span class="nomor">{{ i < indeksTahap(d.tahap) ? '✓' : i + 1 }}</span>
          <span><b>{{ t.label }}</b><small>{{ t.ket }}</small></span>
        </button>
      </nav>

      <component :is="KOMPONEN[tabAktif]" :d="d" @ubah="muat" />

      <details class="kartu riwayat">
        <summary>Riwayat ({{ d.riwayat.length }})</summary>
        <ul>
          <li v-for="(r, i) in d.riwayat" :key="i"><span class="redup">{{ tanggalWaktu(r.waktu) }}</span> <b>{{ r.oleh }}</b> {{ r.aksi }}</li>
        </ul>
      </details>
    </template>

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
.halaman { display: grid; gap: 16px; max-width: 1100px; }
.kembali { font-size: 13px; width: fit-content; }
.id { margin: 0 0 4px !important; color: var(--teks-3); font-size: 12.5px; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks-2); }
.kepala-halaman b { color: var(--teks); font-weight: 600; }
.kanan { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; }
.nama-saya { display: grid; gap: 4px; min-width: 180px; }
.nama-saya > label { font-size: 12px; }
.minta-nama { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; padding: 12px 16px; border-color: rgba(232, 181, 74, .55); background: rgba(232, 181, 74, .08); }
.minta-nama label { flex: 1 1 320px; color: var(--teks-2); font-size: 13.5px; }
.minta-nama b { color: var(--waspada); }
.minta-nama .cepat { flex: 0 1 260px; }
.proses { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-color: rgba(232, 181, 74, .45); color: var(--waspada); font-weight: 600; }
.titik { width: 10px; height: 10px; border-radius: 50%; background: var(--waspada); animation: denyut 1.2s ease-in-out infinite; }
@keyframes denyut { 50% { opacity: .3; } }
@media (prefers-reduced-motion: reduce) { .titik { animation: none; } }
.stepper { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
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
.riwayat summary { cursor: pointer; font-weight: 600; }
.riwayat ul { margin: 12px 0 0; padding: 0; list-style: none; display: grid; gap: 6px; font-size: 13px; max-height: 320px; overflow: auto; }
.formulir { display: grid; gap: 14px; }
.isian .label { font-size: 13px; font-weight: 600; color: var(--teks-2); }
@media (max-width: 760px) {
  .stepper { grid-template-columns: repeat(5, minmax(56px, 1fr)); }
  .stepper button { flex-direction: column; gap: 4px; padding: 8px 4px; text-align: center; }
  .stepper button small { display: none; }
  .stepper button b { font-size: 12px; }
}
</style>
