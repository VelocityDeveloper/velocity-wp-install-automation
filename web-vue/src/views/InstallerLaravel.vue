<script setup>
// Installer Laravel = alur project: Brief (PM) → Estimasi → Install → Agen Claude → Review webmaster.
// Halaman ini: daftar project + membuat project baru (ID urut project-001, relasi On Progress opsional).
// Data & aksi: scripts/laravel_proyek.py lewat /api/laravel.
import { reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Ikon from '../components/Ikon.vue'
import PilihOnProgress from '../components/laravel/PilihOnProgress.vue'
import PilihNama from '../components/laravel/PilihNama.vue'
import { pakaiPolling, kirim, waktuLalu } from '../api.js'
import { namaSaya, keNama, TAHAP, indeksTahap, pesanGalat, hariJam } from '../laravel.js'

const router = useRouter()
const { data, galat, memuat, muatUlang } = pakaiPolling('/api/laravel', 10000)
const proyek = computed(() => data.value?.proyek || [])
const prasyarat = computed(() => data.value?.prasyarat || {})

const STACK = ['Laravel 13', 'Inertia', 'Vue 3 + TypeScript', 'Tailwind 4', 'shadcn-vue / reka-ui', 'Fortify', 'Wayfinder', 'Pest', 'Boost', 'MariaDB']

const form = reactive({ judul: '', klien: '', onprogress: '' })
const status = ref({ kelas: '', teks: '' })
const mengirim = ref(false)
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

// Filter progress = tahap project saat ini; project selesai hanya tampil di "Semua".
const SARING = [{ nilai: 'semua', label: 'Semua' }, ...TAHAP.map((t) => ({ nilai: t.kunci, label: t.label }))]
const saring = ref('semua')
const cocok = (p, n) => n === 'semua' || p.tahap === n
const tampil = computed(() => proyek.value.filter((p) => cocok(p, saring.value)))
const jumlah = (n) => proyek.value.filter((p) => cocok(p, n)).length
const selesaiFitur = (p) => (p.fitur_status?.ok || 0)
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

    <div class="dua-kolom">
      <section class="kartu" aria-labelledby="judul-baru">
        <div class="kartu-judul"><h2 id="judul-baru">Project baru</h2><span class="redup">ID berikutnya <code>{{ data?.id_berikut || '…' }}</code></span></div>
        <form class="formulir" @submit.prevent="buat">
          <label class="isian">
            <span>Judul aplikasi</span>
            <input v-model="form.judul" required maxlength="80" placeholder="mis. Sistem Kasir Toko Sinar" autocomplete="off">
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
          <div class="aksi">
            <button type="submit" class="tombol" :disabled="mengirim || !form.judul.trim() || !namaSaya.trim()">
              <Ikon nama="tambah" :ukuran="18" /> {{ mengirim ? 'Membuat…' : 'Buat project' }}
            </button>
            <button v-if="!namaSaya.trim()" type="button" class="isi-nama" @click="keNama">Isi "Nama Anda" dulu →</button>
            <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
          </div>
        </form>
      </section>

      <section class="kartu" aria-labelledby="judul-alur">
        <div class="kartu-judul"><h2 id="judul-alur">Alur</h2><span class="redup"><code>laravel new --vue</code></span></div>
        <ol class="alur">
          <li><b>Brief</b> — PM menempel catatan/chat diskusi klien, Claude menyusun draf DESIGN.md + PRD, PM menyunting.</li>
          <li><b>Estimasi</b> — Claude memecah PRD jadi fitur + kriteria terima + jam (internal), PM menyesuaikan lalu mengunci.</li>
          <li><b>Install</b> — kerangka Laravel, database, layanan dev, repo GitHub privat; DESIGN.md & PRD ikut repo.</li>
          <li><b>Agen</b> — Claude mengerjakan fitur satu per satu; tiap fitur dites &amp; di-commit sesudah lolos verifikasi. Sesudah fitur terakhir, dev di-deploy (composer, npm ci, build, migrate, restart, cek HTTP) — Review baru terbuka bila deploy lolos.</li>
          <li><b>Review</b> — webmaster mencentang checklist kriteria per fitur: OK atau Revisi (kembali ke agen).</li>
        </ol>
        <ul class="chip"><li v-for="s in STACK" :key="s">{{ s }}</li></ul>
      </section>
    </div>

    <section class="kartu" aria-labelledby="judul-daftar">
      <div class="kartu-judul">
        <h2 id="judul-daftar">Project</h2>
        <div class="tab" role="tablist" aria-label="Saring project">
          <button v-for="s in SARING" :key="s.nilai" type="button" role="tab" :aria-selected="saring === s.nilai" :class="{ aktif: saring === s.nilai }" @click="saring = s.nilai">
            {{ s.label }} <span class="hitung">{{ jumlah(s.nilai) }}</span>
          </button>
        </div>
      </div>
      <p v-if="memuat" class="redup">Memuat…</p>
      <p v-else-if="galat && !data" class="pesan-status bahaya">Gagal memuat: {{ galat.message }}</p>
      <p v-else-if="!tampil.length" class="redup">Belum ada project di sini.</p>
      <div v-else class="daftar">
        <RouterLink v-for="p in tampil" :key="p.slug" :to="`/installer/laravel/${p.slug}`" class="proyek" :class="{ jalan: p.job }" :aria-busy="!!p.job">
          <div class="p-atas">
            <div class="nama">
              <code class="id">{{ p.slug }}</code>
              <b>{{ p.judul }}</b>
              <span v-if="p.job" class="pil waspada pil-jalan"><i class="putar" aria-hidden="true" />{{ JOB[p.job.jenis] || p.job.jenis }}</span>
              <span v-else-if="p.tahap === 'selesai'" class="pil baik">Selesai</span>
            </div>
            <span class="redup">{{ p.pm ? `PM ${p.pm} · ` : '' }}{{ waktuLalu(p.dibuat) }}</span>
          </div>
          <p class="redup meta">
            <template v-if="p.klien">{{ p.klien }} · </template>
            <template v-if="p.onprogress">On Progress: {{ p.onprogress }}</template><template v-else>belum ada relasi On Progress</template>
            <template v-if="p.fitur_total"> · {{ p.fitur_total }} fitur, agen {{ hariJam(p.jam_agen) }}, webmaster {{ hariJam(p.jam_webmaster) }}, total {{ hariJam(p.jam_agen + p.jam_webmaster) }}</template>
          </p>
          <ol class="stepper" :aria-label="`Tahap ${p.slug}`">
            <li v-for="(t, i) in TAHAP" :key="t.kunci" :class="{ lewat: i < indeksTahap(p.tahap), kini: i === indeksTahap(p.tahap) }">
              <i aria-hidden="true" />{{ t.label }}
              <small v-if="t.kunci === 'review' && p.fitur_total && i <= indeksTahap(p.tahap)">{{ selesaiFitur(p) }}/{{ p.fitur_total }}</small>
            </li>
          </ol>
        </RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; max-width: 1100px; }
.nama-saya { display: grid; gap: 4px; min-width: 200px; }
.nama-saya > label { font-size: 12px; }
.dua-kolom { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; align-items: start; }
.peringatan { border-color: rgba(232, 181, 74, .5); background: rgba(232, 181, 74, .07); }
.peringatan b { color: var(--waspada); }
.peringatan p { margin: 6px 0 0; color: var(--teks-2); }
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
.daftar { display: grid; gap: 12px; }
.proyek { display: grid; gap: 10px; padding: 14px 16px; border-radius: 12px; background: var(--kartu-2); color: var(--teks); border: 1px solid transparent; }
.proyek:hover { border-color: var(--aksen-terang); color: var(--teks); }
.p-atas { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; align-items: baseline; }
.nama { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 15px; }
.id { padding: 2px 7px; border-radius: 6px; background: var(--kartu); color: var(--teks-2); font-size: 12px; }
.meta { margin: 0; }
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
@media (max-width: 960px) { .dua-kolom { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 560px) { .stepper { grid-template-columns: repeat(3, minmax(0, 1fr)); } .nama-saya { width: 100%; } }
</style>
