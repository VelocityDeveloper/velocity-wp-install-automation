<script setup>
// Tahap 4 Agen: Claude mengerjakan fitur satu per satu; runner memverifikasi (tes, build, dev hidup) lalu commit.
import { ref, computed, onBeforeUnmount } from 'vue'
import LogLive from './LogLive.vue'
import Ikon from '../Ikon.vue'
import { aksi, pesanGalat, namaSaya, STATUS_FITUR, jam } from '../../laravel.js'
import { tanggalWaktu } from '../../api.js'

const props = defineProps({ d: { type: Object, required: true } })
const emit = defineEmits(['ubah'])
const agenJalan = computed(() => props.d.job?.jenis === 'agen')
// Fitur yang sedang dikerjakan agen: baris beranimasi + lama berjalan (f.mulai = epoch detik)
const fiturJalan = (f) => agenJalan.value && props.d.agen?.fitur === f.id
const kini = ref(Date.now())
const detak = setInterval(() => { kini.value = Date.now() }, 1000)
onBeforeUnmount(() => clearInterval(detak))
const lamaFitur = (f) => {
  if (!f.mulai) return ''
  const s = Math.max(0, Math.floor(kini.value / 1000 - f.mulai))
  return s < 60 ? `${s} dtk` : s < 3600 ? `${Math.floor(s / 60)} mnt ${s % 60} dtk` : `${Math.floor(s / 3600)} jam ${Math.floor((s % 3600) / 60)} mnt`
}
const terinstall = computed(() => props.d.install?.status === 'ok')
const sisa = computed(() => props.d.fitur.filter((f) => ['antre', 'revisi', 'jalan'].includes(f.status)).length)
const adaGagal = computed(() => props.d.fitur.some((f) => f.status === 'gagal'))
const biaya = computed(() => props.d.fitur.reduce((n, f) => n + Number(f.hasil?.biaya_usd || 0), 0))
const menit = computed(() => props.d.fitur.reduce((n, f) => n + Number(f.hasil?.menit || 0), 0))
const minta = computed(() => props.d.agen?.minta_berhenti)
// Tertahan gerbang review tanpa revisi: menekan Lanjutkan hanya akan berhenti lagi — arahkan ke Review
const tertahan = computed(() => props.d.review?.gerbang?.length && !props.d.fitur.some((f) => f.status === 'revisi'))
// Deploy dev sesudah semua fitur selesai; Review baru terbuka bila deploy terakhir lolos
const dep = computed(() => props.d.agen?.deploy)
const siapDeploy = computed(() => terinstall.value && !sisa.value && !adaGagal.value && props.d.fitur.some((f) => f.status === 'dites'))
const status = ref({ kelas: '', teks: '' })
async function lakukan(nama, body, ok) {
  status.value = { kelas: '', teks: '' }
  try { await aksi(props.d.slug, nama, body); status.value = { kelas: 'baik', teks: ok }; emit('ubah') } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
const terbuka = ref('')
// Galat lama tersimpan dengan kode warna ANSI (keluaran Pest); potongan awal bisa berupa sisa escape seperti ";22m"
const bersih = (t) => String(t).replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '').replace(/^[0-9;]*m/, '')
const urlCommit = (h) => (props.d.install?.repo && h ? `${props.d.install.repo}/commit/${h}` : '')
</script>

<template>
  <section class="kartu" aria-labelledby="h-agen">
    <div class="kartu-judul">
      <h2 id="h-agen">Agen Claude</h2>
      <div class="ringkas">
        <span><b>{{ d.fitur.length - sisa }}</b>/{{ d.fitur.length }} dikerjakan</span>
        <span>{{ Math.round(menit) }} menit agen</span>
        <span>setara API <b>${{ biaya.toFixed(2) }}</b></span>
      </div>
    </div>
    <p v-if="!terinstall" class="pesan-status">Aplikasi belum terpasang (tab Install).</p>
    <p v-else-if="!agenJalan && d.agen?.status === 'menunggu_pagi'" class="pesan-status waspada-teks">Agen berhenti sementara karena waktu mesin hari ini tidak cukup untuk fitur berikutnya (mesin mati 22.00). Otomatis lanjut besok saat mesin nyala.</p>
    <p v-else-if="!agenJalan && d.agen?.status === 'jatah_habis'" class="pesan-status waspada-teks">Jatah agen hari ini untuk project ini sudah terpakai (maks. 6 jam per project per hari, lebih sedikit bila banyak project di tahap Agen). Otomatis lanjut besok pagi.</p>
    <p v-else-if="!agenJalan && d.agen?.status === 'menunggu_kuota'" class="pesan-status waspada-teks">Kuota langganan Claude sedang habis (dipakai bersama webmaster &amp; agen lain). Fitur yang sedang dikerjakan tidak dianggap gagal; dicoba lagi otomatis tiap jam pukul .05.</p>
    <p v-else-if="!agenJalan && d.agen?.status === 'menunggu_review'" class="pesan-status bahaya-teks">Agen berhenti menunggu review fitur fondasi {{ d.review?.gerbang?.join(', ') }} di tab Review. Begitu semuanya ditandai OK atau Revisi, agen lanjut otomatis (revisi dikerjakan lebih dulu).</p>
    <p v-else-if="!agenJalan && d.agen?.status === 'deploy_gagal'" class="pesan-status waspada-teks">Semua fitur selesai, tetapi deploy dev gagal — Review belum dibuka. Lihat galat di bawah, perbaiki, lalu tekan Deploy dev.</p>
    <p v-else-if="!agenJalan && ['terputus', 'jalan'].includes(d.agen?.status) && sisa" class="pesan-status waspada-teks">Agen terputus (mesin mati di tengah pekerjaan). Otomatis lanjut dari perubahan terakhir saat mesin nyala, paling lambat tiap jam pukul .05 — atau tekan Lanjutkan agen.</p>
    <p v-if="terinstall" class="redup bantu">Mesin nyala 07.00–22.00: fitur baru tidak dimulai bila perkiraan selesainya lewat 21.45. Agen mengerjakan fitur berurutan. Tiap fitur baru di-commit sesudah runner memastikan sendiri: semua tes lolos, build frontend berhasil, dan aplikasi dev hidup. Bila gagal, agen berhenti di fitur itu dan perubahannya dibiarkan belum di-commit. Sesudah {{ d.review?.gerbang_n || 3 }} fitur pertama (fondasi), agen menunggu webmaster mereviewnya sebelum lanjut. Sesudah fitur terakhir, runner men-deploy dev (deploy-dev.sh: composer, npm ci, build, migrate, restart).</p>

    <div v-if="terinstall" class="aksi">
      <button v-if="!agenJalan" type="button" class="tombol" :disabled="!sisa || adaGagal || tertahan || !!d.job || !namaSaya.trim()" :title="tertahan ? 'Review fitur fondasi dulu di tab Review' : undefined" @click="lakukan('agen', { aksi: 'mulai' }, 'Agen mulai.')">
        <Ikon nama="mainkan" :ukuran="16" /> {{ d.fitur.some((f) => f.hasil) ? 'Lanjutkan agen' : 'Mulai agen' }}
      </button>
      <button v-else type="button" class="tombol waspada" :disabled="minta || !namaSaya.trim()" @click="lakukan('agen', { aksi: 'berhenti' }, 'Agen berhenti sesudah fitur yang sedang dikerjakan.')">
        <Ikon nama="henti" :ukuran="16" /> {{ minta ? 'Berhenti sesudah fitur ini…' : 'Hentikan sesudah fitur ini' }}
      </button>
      <button v-if="siapDeploy && !agenJalan" type="button" class="tombol" :class="{ garis: dep?.ok }" :disabled="!!d.job || !namaSaya.trim()" @click="lakukan('agen', { aksi: 'deploy' }, 'Deploy dev berjalan — pantau di Log agen.')">
        <Ikon nama="ulang" :ukuran="16" /> {{ dep?.ok ? 'Deploy dev ulang' : 'Deploy dev' }}
      </button>
      <span v-if="!sisa && !agenJalan && dep?.ok" class="redup">Semua fitur sudah dikerjakan &amp; dev sudah dideploy — lanjut ke Review.</span>
      <span v-else-if="adaGagal && !agenJalan" class="redup">Ada fitur gagal: tekan Ulangi di fitur itu (atau perbaiki manual & commit) sebelum melanjutkan.</span>
      <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
    </div>

    <div v-if="dep || siapDeploy" class="deploy" :class="dep ? (dep.ok ? 'lolos' : 'gagal') : ''">
      <b>Deploy dev</b>
      <span v-if="!dep" class="redup">belum dijalankan untuk hasil terakhir</span>
      <span v-else>{{ dep.ok ? 'lolos' : 'gagal' }} · {{ tanggalWaktu(dep.waktu) }}<template v-if="dep.commit"> · commit <a :href="urlCommit(dep.commit)" target="_blank" rel="noopener"><code>{{ dep.commit }}</code></a></template><template v-if="dep.http"> · /login HTTP {{ dep.http }}</template></span>
      <pre v-if="dep?.galat" class="galat">{{ dep.galat }}</pre>
    </div>

    <ol class="fitur">
      <li v-for="f in d.fitur" :key="f.id" class="f" :class="{ kini: d.agen?.fitur === f.id, jalan: fiturJalan(f) }" :aria-busy="fiturJalan(f)">
        <div class="f-baris">
          <span class="fid">{{ f.id }}</span>
          <b class="f-judul">{{ f.judul }}</b>
          <span class="lencana" :class="STATUS_FITUR[f.status]?.[0]"><i v-if="fiturJalan(f)" class="putar" aria-hidden="true" />{{ STATUS_FITUR[f.status]?.[1] || f.status }}</span>
          <span v-if="fiturJalan(f) && f.mulai" class="lama">berjalan {{ lamaFitur(f) }}</span>
          <span class="redup kecil">
            <template v-if="f.hasil">{{ f.hasil.menit }} mnt · <template v-if="f.hasil.tes_lulus != null">{{ f.hasil.tes_lulus }} tes lolos<template v-if="f.hasil.tes_gagal">, {{ f.hasil.tes_gagal }} gagal</template> · </template></template>
            <template v-else>estimasi {{ jam(f.jam_agen) }}</template>
            <a v-if="f.hasil?.commit" :href="urlCommit(f.hasil.commit)" target="_blank" rel="noopener"><code>{{ f.hasil.commit }}</code></a>
          </span>
          <button v-if="f.hasil" type="button" class="tombol garis kecil" :aria-expanded="terbuka === f.id" @click="terbuka = terbuka === f.id ? '' : f.id">{{ terbuka === f.id ? 'Tutup' : 'Hasil' }}</button>
        </div>
        <i v-if="fiturJalan(f)" class="garis-jalan" aria-hidden="true" />
        <div v-if="terbuka === f.id && f.hasil" class="f-rinci">
          <p v-if="f.hasil.ringkasan">{{ f.hasil.ringkasan }}</p>
          <p v-if="f.revisi?.length" class="redup">Revisi terakhir ({{ f.revisi.at(-1).oleh }}): {{ f.revisi.at(-1).catatan }}</p>
          <pre v-if="f.hasil.galat" class="galat">{{ bersih(f.hasil.galat) }}</pre>
          <p class="redup kecil">{{ tanggalWaktu(f.hasil.waktu) }} · {{ f.hasil.giliran || '?' }} giliran · setara API ${{ Number(f.hasil.biaya_usd || 0).toFixed(2) }}</p>
          <button v-if="f.status === 'gagal'" type="button" class="tombol kecil" :disabled="!namaSaya.trim()" @click="lakukan('ulangi', { fitur: f.id }, `${f.id} diantrekan ulang. Tekan Lanjutkan agen.`)">Ulangi fitur ini</button>
        </div>
      </li>
    </ol>
  </section>

  <section v-if="terinstall" class="kartu" aria-labelledby="h-log-agen">
    <div class="kartu-judul"><h2 id="h-log-agen">Log agen</h2><span v-if="agenJalan" class="pil waspada">live</span></div>
    <LogLive :id="d.slug" jenis="agen" :hidup="agenJalan" tinggi="60vh" />
  </section>
</template>

<style scoped>
.bantu { margin: -6px 0 12px; }
.waspada-teks { color: var(--waspada); margin: -4px 0 12px; }
.bahaya-teks { color: var(--bahaya); margin: -4px 0 12px; }
.ringkas { display: flex; gap: 14px; flex-wrap: wrap; font-size: 13px; color: var(--teks-2); }
.ringkas b { color: var(--teks); }
.aksi { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.aksi p { margin: 0; }
.fitur { list-style: none; margin: 14px 0 0; padding: 0; display: grid; gap: 8px; }
.f { padding: 10px 12px; border-radius: 12px; background: var(--kartu-2); border: 1px solid transparent; }
.f.kini { border-color: var(--waspada); }
/* Fitur yang sedang dikerjakan: kilau menyapu, spinner di lencana, garis tak tentu di bawah */
.f.jalan { position: relative; overflow: hidden; isolation: isolate; }
.f.jalan::after { content: ''; position: absolute; inset: 0; z-index: -1; pointer-events: none;
  background: linear-gradient(100deg, transparent 30%, rgba(232, 181, 74, .13) 50%, transparent 70%) no-repeat;
  background-size: 250% 100%; animation: kilau 2.8s ease-in-out infinite; }
.f.jalan .lencana { display: inline-flex; align-items: center; gap: 5px; }
.putar { width: 9px; height: 9px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: putar .8s linear infinite; flex: none; }
.lama { font-size: 12px; font-weight: 600; color: var(--waspada); font-variant-numeric: tabular-nums; }
.garis-jalan { position: absolute; left: 0; right: 0; bottom: 0; height: 3px; background: rgba(232, 181, 74, .15); overflow: hidden; }
.garis-jalan::before { content: ''; position: absolute; top: 0; bottom: 0; width: 30%; border-radius: 3px; background: var(--waspada); animation: geser 1.6s ease-in-out infinite; }
@keyframes kilau { from { background-position: 150% 0; } to { background-position: -150% 0; } }
@keyframes putar { to { transform: rotate(360deg); } }
@keyframes geser { from { left: -30%; } to { left: 100%; } }
@media (prefers-reduced-motion: reduce) { .f.jalan::after, .putar, .garis-jalan::before { animation: none; } }
.f-baris { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.fid { font: 700 12px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--aksen-terang); }
.f-judul { font-weight: 600; flex: 1 1 200px; min-width: 0; }
.kecil { font-size: 12px; }
code { font: 12px ui-monospace, SFMono-Regular, Consolas, monospace; }
.f-rinci { display: grid; gap: 8px; margin-top: 10px; font-size: 13.5px; }
.f-rinci p { margin: 0; }
.f-rinci .tombol { width: fit-content; }
.deploy { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin-top: 14px; padding: 10px 12px; border-radius: 12px; background: var(--kartu-2); border: 1px solid var(--garis); font-size: 13.5px; }
.deploy.lolos { border-color: rgba(38, 168, 142, .5); }
.deploy.gagal { border-color: rgba(255, 107, 107, .5); }
.deploy .galat { flex-basis: 100%; }
.galat { margin: 0; padding: 10px 12px; border-radius: 10px; background: var(--latar); border: 1px solid rgba(255, 107, 107, .4); color: var(--teks-2); font: 12px/1.55 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; word-break: break-word; max-height: 300px; overflow: auto; }
</style>
