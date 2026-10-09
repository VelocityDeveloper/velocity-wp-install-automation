<script setup>
// Saran platform (sebelum PRD): Claude membandingkan WordPress / Laravel + Vue / lainnya dari catatan diskusi,
// lengkap dengan kelebihan & kekurangan. PM memilih satu opsi; opsi Laravel + Vue membuka tombol lanjut susun PRD dll.
import { computed, ref } from 'vue'
import LogLive from './LogLive.vue'
import Ikon from '../Ikon.vue'
import { aksi, pesanGalat, namaSaya } from '../../laravel.js'
import { tanggalWaktu } from '../../api.js'
import VersiBrief from './VersiBrief.vue'
import { konfirmasi } from '../../konfirmasi.js'

const props = defineProps({
  d: { type: Object, required: true },
  catatanBerubah: { type: Boolean, default: false },
  simpanCatatan: { type: Function, required: true },
})
const emit = defineEmits(['ubah', 'susun'])

const JALUR = { wordpress: 'WordPress', laravel_vue: 'Laravel + Vue', lainnya: 'Lainnya' }
const HOSTING = {
  shared_hosting: ['baik', 'Bisa shared hosting (DirectAdmin)'],
  shared_lalu_vps: ['baik', 'Shared hosting dulu → VPS saat ramai'],
  vps: ['waspada', 'Wajib VPS'],
  cloud_khusus: ['bahaya', 'Butuh cloud khusus'],
}
const s = computed(() => props.d.saran)
const pilihan = computed(() => s.value?.pilihan || null)
const opsiPilihan = computed(() => s.value?.opsi.find((o) => o.kunci === pilihan.value?.kunci) || null)
const jalan = computed(() => props.d.job?.jenis === 'saran')
const dikunci = computed(() => !!props.d.estimasi_kunci)
const adaPrd = computed(() => !!(props.d.prd || '').trim())
const status = ref({ kelas: '', teks: '' })
// Sesudah ada pilihan, perbandingan lengkap dilipat jadi ringkasan satu baris per opsi
const buka = ref(false)
const lengkap = computed(() => !pilihan.value || buka.value)
const rek = computed(() => s.value?.opsi.find((o) => o.kunci === s.value.rekomendasi) || null)

async function lakukan(fn, pesanOk) {
  status.value = { kelas: '', teks: '' }
  try { await fn(); status.value = { kelas: 'baik', teks: pesanOk }; emit('ubah') } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
async function mintaSaran() {
  if (s.value && !(await konfirmasi({
    judul: 'Minta saran ulang?', tombol: 'Minta ulang', kelas: 'waspada',
    teks: 'Saran sekarang disimpan sebagai cadangan (.bak) dan pilihan platform dikosongkan. Pakai ini bila catatan diskusi bertambah.',
  }))) return
  await lakukan(async () => {
    if (props.catatanBerubah) await props.simpanCatatan()
    await aksi(props.d.slug, 'saran')
  }, 'Claude mulai membandingkan platform (1–3 menit).')
}
const pilih = (o) => lakukan(() => aksi(props.d.slug, 'pilih_platform', { kunci: o.kunci }), `Dipilih: ${o.nama}.`)
// Pertanyaan ke klien kini dikumpulkan di panel PertanyaanKlien (7 Okt)
const keTanya = () => document.getElementById('pertanyaan-klien')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
</script>

<template>
  <section class="kartu" aria-labelledby="h-saran">
    <div class="kartu-judul">
      <h2 id="h-saran">Saran platform</h2>
      <div class="kepala-aksi">
        <VersiBrief :d="d" jenis="saran" />
        <span v-if="s" class="redup">{{ tanggalWaktu(s.waktu) }}</span>
        <button v-if="s" type="button" class="tombol garis kecil" :disabled="dikunci || !!d.job || !namaSaya.trim()" @click="mintaSaran">
          <Ikon nama="claude" :ukuran="16" /> Minta saran ulang
        </button>
      </div>
    </div>

    <template v-if="!s">
      <p class="redup bantu">Sebelum PRD disusun, Claude membandingkan platform yang paling tepat untuk kebutuhan ini — WordPress, Laravel + Vue, atau lainnya — beserta kelebihan, kekurangan, dan kebutuhan hostingnya. PRD, DESIGN.md, relasi database, dan flowchart bisa disusun sesudah platform dipilih; estimasi fitur & install otomatis khusus Laravel + Vue.</p>
      <div v-if="!jalan" class="aksi">
        <button type="button" class="tombol" :disabled="!d.catatan.trim() && !catatanBerubah && !d.dokumen?.length || dikunci || !!d.job || !namaSaya.trim()" @click="mintaSaran">
          <Ikon nama="claude" :ukuran="18" /> Minta saran platform dengan Claude
        </button>
      </div>
    </template>
    <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>

    <LogLive v-if="jalan" :id="d.slug" jenis="saran" hidup tinggi="24vh" class="log" />

    <template v-else-if="s">
      <!-- Ringkas: sudah ada pilihan -->
      <ul v-if="!lengkap" class="ringkas">
        <li v-for="o in s.opsi" :key="o.kunci" :class="{ dipilih: pilihan?.kunci === o.kunci }">
          <span class="skor-kecil"><b>{{ o.skor }}</b>/10</span>
          <span class="nama-opsi"><small>{{ JALUR[o.jalur] }}</small>{{ o.nama }}</span>
          <span class="pills">
            <span v-if="o.kunci === s.rekomendasi" class="pil aksen">Direkomendasikan</span>
            <span v-if="HOSTING[o.hosting]" class="pil" :class="HOSTING[o.hosting][0]">{{ HOSTING[o.hosting][1] }}</span>
          </span>
          <span v-if="pilihan?.kunci === o.kunci" class="tanda">✓ Dipilih</span>
          <button v-else type="button" class="tombol garis kecil" :disabled="dikunci || !!d.job || !namaSaya.trim()" @click="pilih(o)">Pilih</button>
        </li>
      </ul>

      <!-- Lengkap: belum memilih, atau dibuka -->
      <template v-else>
        <div v-if="rek" class="rekomendasi">
          <b>Rekomendasi Claude: {{ rek.nama }}</b>
          <p>{{ s.alasan }}</p>
        </div>

        <div class="opsi-grid">
          <article v-for="o in s.opsi" :key="o.kunci" class="opsi" :class="{ rek: o.kunci === s.rekomendasi, dipilih: pilihan?.kunci === o.kunci }">
            <header>
              <div>
                <span class="jalur">{{ JALUR[o.jalur] }}</span>
                <h3>{{ o.nama }}</h3>
              </div>
              <div class="skor" :aria-label="`Skor kecocokan ${o.skor} dari 10`"><b>{{ o.skor }}</b>/10</div>
            </header>
            <ul class="pills" aria-label="Kebutuhan hosting">
              <li v-if="o.kunci === s.rekomendasi" class="pil aksen">Direkomendasikan</li>
              <li v-if="HOSTING[o.hosting]" class="pil" :class="HOSTING[o.hosting][0]">{{ HOSTING[o.hosting][1] }}</li>
              <li v-for="(t, i) in o.syarat_server || []" :key="i" class="pil netral">{{ t }}</li>
            </ul>
            <p v-if="o.cocok_bila" class="cocok"><b>Cocok bila:</b> {{ o.cocok_bila }}</p>
            <div class="plusmin">
              <h4 class="plus">Kelebihan</h4>
              <ul><li v-for="(k, i) in o.kelebihan" :key="i">{{ k }}</li></ul>
              <h4 class="minus">Kekurangan</h4>
              <ul><li v-for="(k, i) in o.kekurangan" :key="i">{{ k }}</li></ul>
            </div>
            <details class="rinci">
              <summary>Stack &amp; biaya</summary>
              <dl>
                <div><dt>Stack</dt><dd>{{ o.stack }}</dd></div>
                <div><dt>Biaya berjalan</dt><dd>{{ o.biaya_berjalan }}</dd></div>
              </dl>
            </details>
            <p class="waktu"><span class="redup">Waktu</span> {{ o.perkiraan_waktu }}</p>
            <button type="button" class="tombol kecil pilih" :class="{ garis: pilihan?.kunci !== o.kunci }" :disabled="dikunci || !!d.job || !namaSaya.trim() || pilihan?.kunci === o.kunci" @click="pilih(o)">
              {{ pilihan?.kunci === o.kunci ? '✓ Dipilih' : 'Pilih opsi ini' }}
            </button>
          </article>
        </div>
      </template>

      <button v-if="pilihan" type="button" class="lipat-tombol" :aria-expanded="lengkap" @click="buka = !buka">
        {{ lengkap ? 'Ringkas perbandingan ▴' : 'Lihat perbandingan lengkap (kelebihan, kekurangan, biaya) ▾' }}
      </button>

      <p v-if="s.pertanyaan_klien.length" class="tanya-ke"><a href="#pertanyaan-klien" @click.prevent="keTanya">{{ s.pertanyaan_klien.length }} pertanyaan ke klien</a> <span class="redup">bisa mengubah rekomendasi; ada di panel Pertanyaan untuk klien.</span></p>

      <div class="lanjut" :class="{ siap: !!pilihan }">
        <p v-if="!pilihan" class="redup">Pilih salah satu opsi di atas untuk melanjutkan.</p>
        <template v-else-if="pilihan.jalur === 'laravel_vue'">
          <p><b>{{ opsiPilihan?.nama }}</b> <span class="redup">dipilih {{ pilihan.oleh }} · {{ tanggalWaktu(pilihan.waktu) }}</span></p>
          <span v-if="adaPrd" class="pil baik">PRD sudah disusun — lihat di bawah</span>
          <button v-else type="button" class="tombol" :disabled="dikunci || !!d.job || !namaSaya.trim()" @click="emit('susun')">
            <Ikon nama="claude" :ukuran="18" /> Lanjut: susun PRD, DESIGN.md &amp; diagram
          </button>
        </template>
        <template v-else>
          <p v-if="pilihan.jalur === 'wordpress'"><b>{{ opsiPilihan?.nama }}</b> dipilih {{ pilihan.oleh }}. Situs WordPress dibangun lewat
            <RouterLink to="/installer/wordpress">Installer WordPress</RouterLink>, bukan alur Laravel ini. PRD, DESIGN.md, diagram &amp; estimasi fitur tetap bisa disusun sebagai pegangan webmaster.</p>
          <p v-else><b>{{ opsiPilihan?.nama }}</b> dipilih {{ pilihan.oleh }}. Installer ini hanya membangun Laravel + Vue; opsi ini dikerjakan di luar alur otomatis. PRD, DESIGN.md, diagram &amp; estimasi fitur tetap bisa disusun sebagai pegangan webmaster.</p>
          <span v-if="adaPrd" class="pil baik">PRD sudah disusun — lihat di bawah</span>
          <button v-else type="button" class="tombol" :disabled="dikunci || !!d.job || !namaSaya.trim()" @click="emit('susun')">
            <Ikon nama="claude" :ukuran="18" /> Lanjut: susun PRD, DESIGN.md &amp; diagram
          </button>
        </template>
      </div>
    </template>
  </section>
</template>

<style scoped>
.kepala-aksi { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.bantu { margin: -6px 0 12px; }
.aksi { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pesan-status { margin: 8px 0 0; }
.log { margin-top: 14px; }
.rekomendasi { margin-top: 4px; padding: 12px 14px; border-radius: 12px; background: rgba(52, 199, 123, .08); border: 1px solid rgba(52, 199, 123, .35); }
.rekomendasi b { color: var(--baik); }
.rekomendasi p { margin: 6px 0 0; color: var(--teks-2); line-height: 1.55; font-size: 13.5px; }

.ringkas { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.ringkas li { display: grid; grid-template-columns: 56px minmax(0, 1fr) auto auto; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 12px; border: 1px solid var(--garis); background: var(--kartu-2); }
.ringkas li.dipilih { border-color: var(--aksen-terang); }
.skor-kecil { font-size: 12px; color: var(--teks-3); }
.skor-kecil b { font-size: 18px; color: var(--teks); }
.nama-opsi { font-weight: 600; font-size: 14px; min-width: 0; }
.nama-opsi small { display: block; font-size: 11px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: var(--teks-3); }
.tanda { color: var(--aksen-terang); font-weight: 600; font-size: 13px; padding: 0 6px; }

.opsi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 12px; margin-top: 14px; align-items: start; }
.opsi { display: flex; flex-direction: column; gap: 10px; padding: 14px; border-radius: 14px; border: 1px solid var(--garis); background: var(--kartu-2); min-width: 0; }
.opsi.rek { border-color: rgba(52, 199, 123, .5); }
.opsi.dipilih { border-color: var(--aksen-terang); box-shadow: 0 0 0 1px var(--aksen-terang); }
.opsi header { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
.opsi h3 { margin: 2px 0 0; font-size: 15.5px; line-height: 1.35; }
.jalur { font-size: 11.5px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: var(--teks-3); }
.skor { flex: none; font-size: 12.5px; color: var(--teks-3); }
.skor b { font-size: 22px; color: var(--teks); }
.pills { display: flex; flex-wrap: wrap; gap: 6px; margin: 0; padding: 0; list-style: none; }
.opsi ul.pills { padding: 0; display: flex; }
.pil.aksen { color: var(--aksen-terang); background: rgba(91, 140, 255, .14); }
.pil.netral { color: var(--teks-2); background: var(--kartu); border: 1px solid var(--garis); }
.pil.netral::before { display: none; }
.cocok { margin: 0; padding: 8px 10px; border-radius: 10px; background: var(--kartu); font-size: 13px; color: var(--teks-2); line-height: 1.5; }
.cocok b { color: var(--teks); font-weight: 600; }
.plusmin h4 { margin: 10px 0 4px; font-size: 12.5px; }
.plusmin h4:first-child { margin-top: 0; }
h4.plus { color: var(--baik); }
h4.minus { color: var(--bahaya); }
.opsi .plusmin ul { margin: 0; padding-left: 18px; display: grid; gap: 3px; font-size: 13px; color: var(--teks-2); line-height: 1.5; }
.rinci summary { cursor: pointer; font-size: 13px; }
.rinci summary { color: var(--teks-2); font-weight: 600; }
.rinci dl { margin: 8px 0 0; display: grid; gap: 8px; font-size: 12.5px; }
dt { color: var(--teks-3); font-weight: 600; }
dd { margin: 0; color: var(--teks-2); line-height: 1.5; }
.waktu { margin: 0; font-size: 12.5px; color: var(--teks-2); }
.opsi .pilih { align-self: flex-start; }
.lipat-tombol { margin-top: 10px; border: 0; background: none; padding: 4px 0; color: var(--aksen-terang); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.lanjut { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-top: 12px; padding: 12px 14px; border-radius: 12px; border: 1px dashed var(--garis); }
.lanjut.siap { border-style: solid; border-color: var(--aksen-terang); }
.lanjut p { margin: 0; color: var(--teks-2); font-size: 13.5px; }
@media (max-width: 640px) {
  .ringkas li { grid-template-columns: 44px minmax(0, 1fr) auto; }
  .ringkas .pills { grid-column: 2 / -1; grid-row: 2; }
  .lanjut .tombol { width: 100%; justify-content: center; }
}
.tanya-ke { margin: 12px 0 0; font-size: 13px; }
</style>
