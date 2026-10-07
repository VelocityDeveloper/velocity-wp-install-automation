<script setup>
// Installer Laravel = alur project: Brief (PM) → Estimasi → Install → Agen Claude → Review webmaster.
// Halaman ini: daftar project; Project baru (ID urut project-001, relasi On Progress opsional) & Alur di modal.
// Data & aksi: scripts/laravel_proyek.py lewat /api/laravel.
import { reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import PilihOnProgress from '../components/laravel/PilihOnProgress.vue'
import PilihNama from '../components/laravel/PilihNama.vue'
import UbahStatus from '../components/laravel/UbahStatus.vue'
import HapusProyek from '../components/laravel/HapusProyek.vue'
import ServerDev from '../components/laravel/ServerDev.vue'
import { pakaiPolling, kirim, waktuLalu } from '../api.js'
import { namaSaya, KONDISI_SERVER, STATUS_PROYEK, TAHAP, indeksTahap, pesanGalat, hariJam, tabUrl, reviewMendesak, angkaToken } from '../laravel.js'

const router = useRouter()
const { data, galat, memuat, muatUlang } = pakaiPolling('/api/laravel', 10000)
const proyek = computed(() => data.value?.proyek || [])
const prasyarat = computed(() => data.value?.prasyarat || {})
// Status server dev (panel Server dev + badge di kartu project yang sudah di-install, dicocokkan lewat nama app)
const srv = pakaiPolling('/api/laravel/server', 15000)
const serverApp = computed(() => Object.fromEntries((srv.data.value?.server || []).map((s) => [s.id, s])))

const STACK = ['Laravel 13', 'Inertia', 'Vue 3 + TypeScript', 'Tailwind 4', 'shadcn-vue / reka-ui', 'Fortify', 'Wayfinder', 'Pest', 'Boost', 'MariaDB']

const form = reactive({ judul: '', klien: '', onprogress: '' })
const status = ref({ kelas: '', teks: '' })
const mengirim = ref(false)
const baruBuka = ref(false)
const alurBuka = ref(false)
function bukaBaru() {
  status.value = { kelas: '', teks: '' }
  baruBuka.value = true
}
async function buat() {
  mengirim.value = true
  status.value = { kelas: '', teks: '' }
  try {
    const r = await kirim('/api/laravel/p', { ...form, oleh: namaSaya.value.trim() })
    router.push(`/installer/laravel/${r.slug}`)
  } catch (e) {
    status.value = { kelas: 'bahaya', teks: pesanGalat(e) }
  } finally {
    mengirim.value = false
  }
}

// Filter progress = tahap project saat ini; project selesai hanya tampil di "Aktif".
// Project Selesai/Batal/Ditunda hanya tampil di tab statusnya, tidak ikut tab tahap & peringatan review.
const SARING = [{ nilai: 'semua', label: 'Aktif' }, ...TAHAP.map((t) => ({ nilai: t.kunci, label: t.label })),
  { nilai: 'selesai', label: 'Selesai', status: true }, { nilai: 'ditunda', label: 'Ditunda', status: true }, { nilai: 'batal', label: 'Batal', status: true }]
const saring = tabUrl('tahap', 'semua', { boleh: SARING.map((s) => s.nilai) })
const aktif = (p) => (p.status_proyek || 'aktif') === 'aktif'
const cocok = (p, n) => (n in STATUS_PROYEK ? p.status_proyek === n : aktif(p) && (n === 'semua' || p.tahap === n))
const tersaring = computed(() => proyek.value.filter((p) => cocok(p, saring.value)))
// Paginasi 10 project per halaman; nomor halaman di URL (?hal=2) supaya tombol Kembali dari detail project
// pulang ke halaman yang sama. Ganti filter tahap → kembali ke halaman 1.
const PER_HALAMAN = 10
const halUrl = tabUrl('hal', '1')
const jmlHalaman = computed(() => Math.max(1, Math.ceil(tersaring.value.length / PER_HALAMAN)))
const halaman = computed({
  get: () => Math.min(Math.max(1, parseInt(halUrl.value, 10) || 1), jmlHalaman.value),
  set: (n) => { halUrl.value = String(n) },
})
const tampil = computed(() => tersaring.value.slice((halaman.value - 1) * PER_HALAMAN, halaman.value * PER_HALAMAN))
// Nomor halaman ringkas: 1 … 4 5 6 … 12
const nomorHalaman = computed(() => {
  const n = jmlHalaman.value, k = halaman.value
  const set = [...new Set([1, n, k - 1, k, k + 1].filter((x) => x >= 1 && x <= n))].sort((a, b) => a - b)
  return set.flatMap((x, i) => (i && x - set[i - 1] > 1 ? ['…', x] : [x]))
})
function pilihSaring(n) {
  saring.value = n
  halUrl.value = '1'
}
const jumlah = (n) => proyek.value.filter((p) => cocok(p, n)).length
// Ubah status langsung dari kartu daftar (tombol di kartu tidak membuka halaman project)
const ubahStatus = ref(null)
const hapusProyek = ref(null)
const selesaiFitur = (p) => (p.fitur_status?.ok || 0)
// Peringatan review lintas project: fitur yang sudah dikerjakan agen tapi belum dicek webmaster (terlama dulu)
const antreReview = computed(() => proyek.value.filter((p) => aktif(p) && p.review?.menunggu).sort((a, b) => (a.review.tertua || 0) - (b.review.tertua || 0)))
const totalReview = computed(() => antreReview.value.reduce((n, p) => n + p.review.menunggu, 0))
// Total token Claude project (brief + agen) dari usage.jsonl; rincian di tooltip
const judulToken = (t) => [
  `Total ${t.total.toLocaleString('id-ID')} token (${t.panggilan} permintaan Claude)`,
  `Brief & dokumen: ${t.brief.toLocaleString('id-ID')}`,
  `Agen fitur: ${t.agen.toLocaleString('id-ID')}`,
  t.biaya_usd ? `Setara ≈ $${t.biaya_usd.toLocaleString('id-ID')} harga API` : '',
].filter(Boolean).join('\n')
const JOB = { susun: 'Claude menyusun brief', diagram: 'Claude menyusun ERD & flowchart', estimasi: 'Claude menyusun estimasi', install: 'Install berjalan', agen: 'Agen Claude bekerja' }
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Aplikasi Custom</h1>
        <p class="redup">Dari diskusi klien sampai aplikasi jadi: PM menyusun brief, agen Claude mengerjakan, webmaster memeriksa.</p>
      </div>
      <div class="nama-saya">
        <label for="nama-saya" class="redup">Nama Anda</label>
        <PilihNama :tim="data?.tim" />
      </div>
    </header>

    <div v-if="data && (!prasyarat.db_root || !prasyarat.github)" class="kartu peringatan" role="alert">
      <b>Install belum bisa dijalankan</b>
      <p v-if="!prasyarat.db_root">Kredensial root MariaDB belum ada di <code>/etc/velocity/secrets/mariadb_root.cnf</code>.</p>
      <p v-if="!prasyarat.github">GitHub CLI di server belum login (<code>gh auth status</code> gagal).</p>
    </div>

    <div v-if="antreReview.length" class="kartu peringatan review" :class="{ mendesak: antreReview.some((p) => reviewMendesak(p.review)) }" role="alert">
      <b>{{ totalReview }} fitur menunggu review webmaster</b>
      <ul>
        <li v-for="p in antreReview" :key="p.slug">
          <RouterLink :to="`/installer/laravel/${p.slug}?tab=review`">{{ p.judul }}</RouterLink>
          <span class="redup"> — {{ p.review.menunggu }} fitur, terlama {{ waktuLalu(p.review.tertua) }}</span>
          <span v-if="p.review.tertahan" class="pil bahaya">agen berhenti menunggu review {{ p.review.gerbang.join(', ') }}</span>
          <span v-else-if="p.review.gerbang.length" class="pil waspada">fondasi {{ p.review.gerbang.join(', ') }} belum direview</span>
        </li>
      </ul>
    </div>

    <div class="aksi-atas">
      <button type="button" class="tombol" @click="bukaBaru"><Ikon nama="tambah" :ukuran="18" /> Project baru</button>
      <button type="button" class="tombol garis" @click="alurBuka = true">Alur</button>
    </div>

    <Dialog :buka="baruBuka" judul="Project baru" lebar="560px" @tutup="baruBuka = false">
      <p class="redup ket-id">ID berikutnya <code>{{ data?.id_berikut || '…' }}</code></p>
      <form class="formulir" @submit.prevent="buat">
        <label class="isian">
          <span>Judul aplikasi</span>
          <input v-model="form.judul" required maxlength="80" placeholder="mis. Sistem Kasir Toko Sinar" autocomplete="off" autofocus>
        </label>
        <label class="isian">
          <span>Klien <em>opsional</em></span>
          <input v-model="form.klien" maxlength="80" placeholder="nama klien / no. CRM" autocomplete="off">
        </label>
        <div class="isian">
          <label for="op-baru"><span class="label">Relasi On Progress <em>opsional</em></span></label>
          <PilihOnProgress id="op-baru" v-model="form.onprogress" />
          <small>Saat diskusi awal folder biasanya belum ada — bisa dihubungkan nanti sebelum install.</small>
        </div>
        <div v-if="!namaSaya.trim()" class="isian">
          <label for="nama-baru"><span class="label">Nama Anda</span></label>
          <PilihNama id="nama-baru" :tim="data?.tim" />
        </div>
        <div class="aksi">
          <button type="submit" class="tombol" :disabled="mengirim || !form.judul.trim() || !namaSaya.trim()">
            <Ikon nama="tambah" :ukuran="18" /> {{ mengirim ? 'Membuat…' : 'Buat project' }}
          </button>
          <button type="button" class="tombol garis" @click="baruBuka = false">Batal</button>
          <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
        </div>
      </form>
    </Dialog>

    <Dialog :buka="alurBuka" judul="Alur" lebar="640px" @tutup="alurBuka = false">
      <p class="redup ket-id"><code>laravel new --vue</code></p>
      <ol class="alur">
        <li><b>Brief</b> — PM menempel catatan/chat diskusi klien, Claude menyusun draf DESIGN.md + PRD, PM menyunting.</li>
        <li><b>Estimasi</b> — Claude memecah PRD jadi fitur + kriteria terima + jam (internal), PM menyesuaikan lalu mengunci. Berlaku untuk semua platform; bila platform bukan Laravel + Vue (mis. WordPress), fitur dikerjakan webmaster (jam agen 0) dan alur berhenti di sini — Install &amp; Agen hanya untuk Laravel.</li>
        <li><b>Install</b> — kerangka Laravel, database, layanan dev, repo GitHub privat; DESIGN.md &amp; PRD ikut repo.</li>
        <li><b>Agen</b> — Claude mengerjakan fitur satu per satu; tiap fitur dites &amp; di-commit sesudah lolos verifikasi. Sesudah fitur fondasi (3 pertama) agen <b>berhenti sampai webmaster mereviewnya</b>, lalu lanjut otomatis. Sesudah fitur terakhir, dev di-deploy (composer, npm ci, build, migrate, restart, cek HTTP).</li>
        <li><b>Review</b> — webmaster mencentang checklist kriteria per fitur begitu fitur siap dicek (tidak perlu menunggu semua fitur): OK atau Revisi (kembali ke agen). Fitur yang menunggu tampil sebagai peringatan di daftar &amp; halaman project — merah bila lebih dari sehari atau agen tertahan.</li>
      </ol>
      <ul class="chip"><li v-for="s in STACK" :key="s">{{ s }}</li></ul>
    </Dialog>

    <UbahStatus :p="ubahStatus" @tutup="ubahStatus = null" @ubah="muatUlang" />
    <HapusProyek :p="hapusProyek" @tutup="hapusProyek = null" @hapus="muatUlang" />

    <ServerDev :data="srv.data.value" :galat="srv.galat.value" @ubah="srv.muatUlang" />

    <section class="kartu" aria-labelledby="judul-daftar">
      <div class="kartu-judul">
        <h2 id="judul-daftar">Project</h2>
        <div class="tab" role="tablist" aria-label="Saring project">
          <button v-for="s in SARING" :key="s.nilai" type="button" role="tab" :aria-selected="saring === s.nilai" :class="{ aktif: saring === s.nilai, status: s.status }" @click="pilihSaring(s.nilai)">
            {{ s.label }} <span class="hitung">{{ jumlah(s.nilai) }}</span>
          </button>
        </div>
      </div>
      <p v-if="memuat" class="redup">Memuat…</p>
      <p v-else-if="galat && !data" class="pesan-status bahaya">Gagal memuat: {{ galat.message }}</p>
      <p v-else-if="!tampil.length" class="redup">Belum ada project di sini.</p>
      <div v-else class="daftar">
        <RouterLink v-for="p in tampil" :key="p.slug" :to="`/installer/laravel/${p.slug}`" class="proyek" :class="{ jalan: p.job, nonaktif: !aktif(p) }" :aria-busy="!!p.job">
          <div class="p-atas">
            <div class="nama">
              <code class="id">{{ p.slug }}</code>
              <b>{{ p.judul }}</b>
              <span v-if="p.job" class="pil waspada pil-jalan"><i class="putar" aria-hidden="true" />{{ JOB[p.job.jenis] || p.job.jenis }}</span>
              <span v-if="aktif(p) && !p.job && p.tahap === 'selesai'" class="pil baik">Selesai</span>
              <span v-if="serverApp[p.app]" class="pil server" :class="KONDISI_SERVER[serverApp[p.app].kondisi]?.kelas" :title="serverApp[p.app].alasan.join(' · ') || `Server dev :${serverApp[p.app].port}`">
                server {{ KONDISI_SERVER[serverApp[p.app].kondisi]?.label.toLowerCase() }}
              </span>
              <span v-if="aktif(p) && p.review?.menunggu" class="pil" :class="reviewMendesak(p.review) ? 'bahaya' : 'waspada'">{{ p.review.menunggu }} menunggu review</span>
            </div>
            <div class="p-kanan">
              <span class="redup">{{ p.pm ? `PM ${p.pm} · ` : '' }}{{ waktuLalu(p.dibuat) }}</span>
              <button type="button" class="tombol-status" :class="p.status_proyek || 'aktif'" :title="`Ubah status ${p.slug}`" @click.prevent.stop="ubahStatus = p">
                <i aria-hidden="true" />{{ STATUS_PROYEK[p.status_proyek || 'aktif']?.label }}<span aria-hidden="true" class="panah">▾</span>
              </button>
              <button v-if="!p.app && !p.install?.status" type="button" class="tombol-hapus" :title="`Hapus ${p.slug}`" :aria-label="`Hapus ${p.slug}`" @click.prevent.stop="hapusProyek = p">
                <Ikon nama="sampah" :ukuran="15" />
              </button>
            </div>
          </div>
          <p class="redup meta">
            <template v-if="p.klien">{{ p.klien }} · </template>
            <template v-if="p.onprogress">On Progress: {{ p.onprogress }}</template><template v-else>belum ada relasi On Progress</template>
            <template v-if="p.brief_versi"> · brief v{{ p.brief_versi }}</template>
            <template v-if="p.fitur_total"> · {{ p.fitur_total }} fitur, agen {{ hariJam(p.jam_agen) }}, webmaster {{ hariJam(p.jam_webmaster) }}, total {{ hariJam(p.jam_agen + p.jam_webmaster) }}</template>
            <template v-if="'token' in p"> · <span class="token" :title="p.token ? judulToken(p.token) : 'Belum ada pemakaian token Claude'">{{ angkaToken(p.token?.total || 0) }} token</span></template>
          </p>
          <p v-if="!aktif(p) && p.status_info" class="redup meta alasan">
            {{ STATUS_PROYEK[p.status_proyek]?.label }} oleh {{ p.status_info.oleh }} {{ waktuLalu(p.status_info.waktu) }}<template v-if="p.status_info.alasan"> — {{ p.status_info.alasan }}</template>
          </p>
          <ol class="stepper" :aria-label="`Tahap ${p.slug}`">
            <li v-for="(t, i) in TAHAP" :key="t.kunci" :class="{ lewat: i < indeksTahap(p.tahap), kini: i === indeksTahap(p.tahap) }">
              <i aria-hidden="true" />{{ t.label }}
              <small v-if="t.kunci === 'review' && p.fitur_total && i <= indeksTahap(p.tahap)">{{ selesaiFitur(p) }}/{{ p.fitur_total }}</small>
            </li>
          </ol>
        </RouterLink>
      </div>
      <nav v-if="jmlHalaman > 1" class="halaman-nav" aria-label="Halaman daftar project">
        <span class="redup">{{ (halaman - 1) * PER_HALAMAN + 1 }}–{{ Math.min(halaman * PER_HALAMAN, tersaring.length) }} dari {{ tersaring.length }} project</span>
        <div>
          <button type="button" class="tombol garis kecil" :disabled="halaman <= 1" @click="halaman--">‹ Sebelumnya</button>
          <template v-for="(x, i) in nomorHalaman" :key="i">
            <span v-if="x === '…'" class="redup elip">…</span>
            <button v-else type="button" class="tombol kecil" :class="{ garis: x !== halaman }" :aria-current="x === halaman ? 'page' : undefined" @click="halaman = x">{{ x }}</button>
          </template>
          <button type="button" class="tombol garis kecil" :disabled="halaman >= jmlHalaman" @click="halaman++">Berikutnya ›</button>
        </div>
      </nav>
    </section>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; max-width: 1100px; }
.nama-saya { display: grid; gap: 4px; min-width: 200px; }
.nama-saya > label { font-size: 12px; }
.aksi-atas { display: flex; gap: 10px; flex-wrap: wrap; }
.ket-id { margin: -4px 0 14px; }
.peringatan { border-color: rgba(232, 181, 74, .5); background: rgba(232, 181, 74, .07); }
.peringatan b { color: var(--waspada); }
.peringatan p { margin: 6px 0 0; color: var(--teks-2); }
.peringatan.review.mendesak { border-color: rgba(255, 107, 107, .55); background: rgba(255, 107, 107, .06); }
.peringatan.review.mendesak > b { color: var(--bahaya); }
.peringatan.review ul { margin: 8px 0 0; padding-left: 18px; display: grid; gap: 6px; font-size: 13.5px; }
.peringatan.review li .pil { margin-left: 6px; }
.formulir { display: grid; gap: 14px; }
.isian em { font-style: normal; font-weight: 500; color: var(--teks-3); font-size: 12px; margin-left: 4px; }
.isian .label { font-size: 13px; font-weight: 600; color: var(--teks-2); }
.aksi { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.aksi p { margin: 0; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
.alur { margin: 0 0 14px; padding-left: 20px; display: grid; gap: 6px; color: var(--teks-2); font-size: 13px; }
.alur b { color: var(--teks); }
.chip { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px; }
.chip li { padding: 3px 9px; border-radius: 999px; background: var(--aksen-lembut); color: var(--aksen-terang); font-size: 12px; font-weight: 600; }
.tab { display: flex; flex-wrap: wrap; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
.tab button.status:not(.aktif) { color: var(--teks-3); }
.proyek.nonaktif { opacity: .72; }
.proyek.nonaktif:hover { opacity: 1; }
.meta.alasan { font-style: italic; }
.daftar { display: grid; gap: 12px; }
.halaman-nav { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
.halaman-nav div { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.halaman-nav .elip { padding: 0 2px; }
.proyek { display: grid; gap: 10px; padding: 14px 16px; border-radius: 12px; background: var(--kartu-2); color: var(--teks); border: 1px solid transparent; }
.proyek:hover { border-color: var(--aksen-terang); color: var(--teks); }
.p-atas { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; align-items: baseline; }
.p-kanan { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.tombol-status { display: inline-flex; align-items: center; gap: 6px; padding: 3px 8px 3px 10px; border-radius: 999px; border: 1px solid var(--garis); background: var(--kartu); color: var(--teks-2); font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
.tombol-status:hover { border-color: var(--aksen-terang); color: var(--teks); }
.tombol-status i { width: 7px; height: 7px; border-radius: 50%; background: var(--baik); }
.tombol-status.selesai i { background: var(--aksen-terang); }
.tombol-status.ditunda i { background: var(--waspada); }
.tombol-status.batal i { background: var(--bahaya); }
.tombol-hapus { display: inline-grid; place-items: center; width: 26px; height: 26px; padding: 0; border-radius: 999px; border: 1px solid transparent; background: none; color: var(--teks-2); cursor: pointer; }
.tombol-hapus:hover, .tombol-hapus:focus-visible { color: var(--bahaya); border-color: rgba(255, 107, 107, .5); background: rgba(255, 107, 107, .1); }
.tombol-status .panah { font-size: 10px; opacity: .6; }
.nama { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 15px; }
.id { padding: 2px 7px; border-radius: 6px; background: var(--kartu); color: var(--teks-2); font-size: 12px; }
.meta { margin: 0; }
.pil.server.mati { color: var(--teks-3); background: var(--kartu); }
.meta .token { cursor: help; text-decoration: underline dotted; text-underline-offset: 3px; }
.stepper { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; }
.stepper li { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--teks-3); padding-top: 8px; border-top: 3px solid var(--garis); flex-wrap: wrap; }
.stepper li i { width: 8px; height: 8px; border-radius: 50%; background: var(--garis); flex: none; }
.stepper li.lewat { border-top-color: var(--baik); color: var(--teks-2); }
.stepper li.lewat i { background: var(--baik); }
.stepper li.kini { border-top-color: var(--aksen-terang); color: var(--teks); font-weight: 600; }
.stepper li.kini i { background: var(--aksen-terang); }
.stepper small { color: var(--teks-3); font-weight: 500; }
/* Project yang sedang diproses (ada job): kilau menyapu kartu, bar tahap aktif mengalir, titiknya berdenyut */
.proyek.jalan { position: relative; overflow: hidden; isolation: isolate; border-color: rgba(232, 181, 74, .35); }
.proyek.jalan::after { content: ''; position: absolute; inset: 0; z-index: -1; pointer-events: none;
  background: linear-gradient(100deg, transparent 30%, rgba(232, 181, 74, .10) 50%, transparent 70%) no-repeat;
  background-size: 250% 100%; animation: kilau 2.8s ease-in-out infinite; }
.pil-jalan { display: inline-flex; align-items: center; gap: 6px; }
.pil-jalan::before { display: none; }
.putar { width: 10px; height: 10px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: putar .8s linear infinite; flex: none; }
.proyek.jalan .stepper li.kini { position: relative; border-top-color: transparent; }
.proyek.jalan .stepper li.kini::before { content: ''; position: absolute; left: 0; right: 0; top: -3px; height: 3px; border-radius: 3px;
  background: linear-gradient(90deg, var(--aksen-lembut) 0%, var(--aksen-terang) 40%, var(--aksen-lembut) 80%) 0 0 / 200% 100%;
  animation: alir 1.4s linear infinite; }
.proyek.jalan .stepper li.kini i { animation: denyut 1.6s ease-out infinite; }
@keyframes kilau { from { background-position: 150% 0; } to { background-position: -150% 0; } }
@keyframes putar { to { transform: rotate(360deg); } }
@keyframes alir { from { background-position: 200% 0; } to { background-position: 0 0; } }
@keyframes denyut { 0% { box-shadow: 0 0 0 0 var(--aksen-terang); } 70%, 100% { box-shadow: 0 0 0 6px transparent; } }
@media (prefers-reduced-motion: reduce) {
  .proyek.jalan::after, .putar, .proyek.jalan .stepper li.kini::before, .proyek.jalan .stepper li.kini i { animation: none; }
}
@media (max-width: 560px) { .stepper { grid-template-columns: repeat(3, minmax(0, 1fr)); } .nama-saya { width: 100%; } }
</style>
