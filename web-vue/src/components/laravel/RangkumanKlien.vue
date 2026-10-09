<script setup>
// Tombol "Rangkuman" di bawah Dokumen klien (permintaan user 2026-09-30): Claude merangkum kebutuhan klien dari catatan
// diskusi + dokumen unggahan → berkas Word "Rangkuman Website Konsep" bertemplate SIMONTAK RSUD Piru
// (templates/laravel/rangkuman-konsep.docx, dibangun scripts/rangkuman_docx.py). Klik pertama menyusun; bila sudah
// ada, klik menampilkan pratinjau + tombol unduh .docx. API: aksi `rangkuman`, GET /api/laravel/p/<id>/rangkuman.docx.
import { computed, ref, watch } from 'vue'
import LogLive from './LogLive.vue'
import Ikon from '../Ikon.vue'
import VersiBrief from './VersiBrief.vue'
import { aksi, pesanGalat, namaSaya } from '../../laravel.js'
import { ukuranBerkas, waktuLalu } from '../../api.js'
import { konfirmasi } from '../../konfirmasi.js'

const props = defineProps({
  d: { type: Object, required: true },
  catatanBerubah: { type: Boolean, default: false },
  simpanCatatan: { type: Function, required: true },
})
const emit = defineEmits(['ubah'])

const BAGIAN = [['peran', 'Peran User'], ['fungsi', 'Fungsi Website'], ['menu', 'Menu web dan isinya'],
  ['tambahan_fitur', 'Tambahan Fitur'], ['desain', 'Desain Website'], ['warna', 'Warna Website'], ['batasan', 'Batasan Sistem']]
const r = computed(() => props.d.rangkuman)
const jalan = computed(() => props.d.job?.jenis === 'rangkuman')
const buka = ref(false)
const status = ref({ kelas: '', teks: '' })
const adaBahan = computed(() => !!props.d.catatan.trim() || props.catatanBerubah || !!props.d.dokumen?.length)
const bisa = computed(() => adaBahan.value && !props.d.job && !!namaSaya.value.trim())
const urlUnduh = computed(() => `/api/laravel/p/${props.d.slug}/rangkuman.docx?v=${r.value?.waktu || 0}`)
// Dokumen yang diunggah sesudah rangkuman disusun belum ikut terangkum
const usang = computed(() => r.value && (props.catatanBerubah || (props.d.dokumen || []).some((x) => x.waktu > r.value.waktu)))
// Bagian 1–3 berupa kelompok {subjudul, poin}; bagian lain daftar poin; Desain {pembuka, poin}
const kelompok = (k) => {
  const v = r.value?.[k]
  if (k === 'desain') return [{ subjudul: v?.pembuka || '', poin: v?.poin || [] }]
  return (v || []).length && typeof v[0] === 'object' ? v : [{ subjudul: '', poin: v || [] }]
}
watch(jalan, (v, lama) => { if (lama && !v && r.value) buka.value = true })

async function susun() {
  status.value = { kelas: '', teks: '' }
  try {
    if (props.catatanBerubah) await props.simpanCatatan()
    await aksi(props.d.slug, 'rangkuman')
    buka.value = true
    emit('ubah')
  } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
function klik() {
  if (r.value || jalan.value) { buka.value = !buka.value; return }
  susun()
}
async function susunUlang() {
  if (!(await konfirmasi({ judul: 'Susun ulang rangkuman?', tombol: 'Susun ulang', kelas: 'waspada',
    teks: 'Claude membaca ulang catatan & semua dokumen klien lalu membuat berkas Word baru. Versi sekarang disimpan sebagai cadangan di server.' }))) return
  susun()
}
// Pertanyaan ke klien kini dikumpulkan di panel PertanyaanKlien (7 Okt)
const keTanya = () => document.getElementById('pertanyaan-klien')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
</script>

<template>
  <div class="rangkuman">
    <div class="baris">
      <button type="button" class="tombol garis" :aria-expanded="buka && (!!r || jalan)" :disabled="!r && !jalan && !bisa" @click="klik">
        <Ikon nama="dokumen" :ukuran="18" /> Rangkuman
      </button>
      <span class="redup kecil">
        <template v-if="jalan">Claude sedang merangkum kebutuhan klien…</template>
        <template v-else-if="r">Word terakhir {{ waktuLalu(r.waktu) }}<template v-if="usang"> · ada bahan baru, susun ulang agar ikut</template></template>
        <template v-else>Rangkum kebutuhan klien jadi file Word (template Rangkuman Website Konsep)</template>
      </span>
      <VersiBrief v-if="r && !jalan" :d="d" jenis="rangkuman" />
    </div>
    <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>

    <div v-if="buka && jalan" class="panel" role="status">
      <p class="redup">Claude membaca catatan &amp; dokumen klien lalu menyusun Rangkuman Website Konsep (1–3 menit). File Word tampil di sini setelah selesai.</p>
      <LogLive :id="d.slug" jenis="rangkuman" hidup tinggi="22vh" />
    </div>

    <div v-else-if="buka && r" class="panel">
      <div class="berkas">
        <Ikon nama="dokumen" :ukuran="22" class="ikon" />
        <div class="info">
          <b class="nama">{{ r.nama_berkas }}</b>
          <span class="redup kecil">Word · {{ ukuranBerkas(r.ukuran) }} · disusun {{ waktuLalu(r.waktu) }}</span>
        </div>
        <a class="tombol" :href="urlUnduh" :download="r.nama_berkas"><Ikon nama="unduh" :ukuran="18" /> Unduh Word</a>
        <button type="button" class="tombol garis kecil" :disabled="!bisa" @click="susunUlang"><Ikon nama="claude" :ukuran="16" /> Susun ulang</button>
      </div>
      <p v-if="r.belum_jelas?.length" class="tanya-ke"><a href="#pertanyaan-klien" @click.prevent="keTanya">{{ r.belum_jelas.length }} hal perlu ditanyakan ke klien</a> <span class="redup">(tidak masuk file Word; ada di panel Pertanyaan untuk klien)</span></p>
      <article class="pratinjau" aria-label="Pratinjau isi file Word">
        <p><b>{{ r.judul }}</b></p>
        <p>{{ r.pembuka }}</p>
        <section v-for="([k, label], no) in BAGIAN" :key="k">
          <p class="bagian">{{ no + 1 }}. {{ label }}</p>
          <div v-for="(g, i) in kelompok(k)" :key="i" class="kelompok">
            <p v-if="g.subjudul">{{ g.subjudul }}</p>
            <p v-for="(x, j) in g.poin" :key="j">- {{ x }}</p>
          </div>
        </section>
        <section v-if="r.catatan_teknis?.length">
          <p class="bagian">Catatan Teknis:</p>
          <p v-for="(x, j) in r.catatan_teknis" :key="j">- {{ x }}</p>
        </section>
      </article>
    </div>
  </div>
</template>

<style scoped>
.rangkuman { margin-top: 14px; display: grid; gap: 10px; }
.baris { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.baris .tombol { display: inline-flex; align-items: center; gap: 8px; }
.kecil { font-size: 12px; }
.pesan-status { margin: 0; }
.panel { display: grid; gap: 12px; padding: 14px; border-radius: 12px; background: var(--kartu-2); }
.panel > p { margin: 0; }
.berkas { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.berkas .ikon { flex: none; color: var(--aksen); }
.info { display: grid; min-width: 0; flex: 1 1 200px; }
.nama { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13.5px; }
.berkas .tombol { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; }
/* Pratinjau meniru halaman Word: latar terang, huruf serif-less, poin "- " seperti template */
.pratinjau { max-height: 60vh; overflow: auto; padding: 22px 26px; border-radius: 8px; background: #fff; color: #1b1b1b; font-size: 13.5px; line-height: 1.5; }
.pratinjau p { margin: 0; }
.pratinjau section, .pratinjau .kelompok + .kelompok { margin-top: 12px; }
.pratinjau > p + p { margin-top: 2px; }
@media (max-width: 560px) { .pratinjau { padding: 16px; } }
.tanya-ke { margin: 0 0 12px; font-size: 13px; }
</style>
