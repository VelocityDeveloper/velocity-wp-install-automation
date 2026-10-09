<script setup>
// Dokumen klien di tahap Brief (permintaan user 2026-09-29): PM mengunggah brief PDF/Word, daftar kebutuhan Excel,
// presentasi, atau foto/sketsa. Teksnya diekstrak server dan ikut dibaca Claude saat saran platform & susun PRD;
// gambar & PDF hasil scan dibaca Claude langsung. API: POST /api/laravel/p/<id>/unggah (badan = isi berkas).
import { computed, ref } from 'vue'
import Ikon from '../Ikon.vue'
import { aksi, pesanGalat, namaSaya } from '../../laravel.js'
import { ukuranBerkas, waktuLalu } from '../../api.js'
import { konfirmasi } from '../../konfirmasi.js'

const props = defineProps({ d: { type: Object, required: true } })
const emit = defineEmits(['ubah'])

const TERIMA = '.pdf,.doc,.docx,.odt,.txt,.md,.csv,.xlsx,.ppt,.pptx,.pps,.ppsx,.odp,.png,.jpg,.jpeg,.webp,.gif'
const MAKS = 25 * 1024 * 1024
const dokumen = computed(() => props.d.dokumen || [])
const dikunci = computed(() => !!props.d.estimasi_kunci)
const sibukClaude = computed(() => ['saran', 'susun', 'rangkuman'].includes(props.d.job?.jenis))
const bisa = computed(() => !dikunci.value && !sibukClaude.value && !!namaSaya.value.trim())
const unggah = ref('')   // teks kemajuan unggah
const status = ref({ kelas: '', teks: '' })
const seret = ref(false)
const input = ref(null)

const urlBerkas = (nama) => `/api/laravel/p/${props.d.slug}/dokumen?nama=${encodeURIComponent(nama)}`
const kata = (n) => Math.max(1, Math.round(n / 6)).toLocaleString('id-ID')
function keterangan(x) {
  if (x.jenis === 'teks') return ['baik', `±${kata(x.karakter)} kata terbaca`]
  if (x.jenis === 'visual') return ['baik', `${x.nama.endsWith('.pdf') ? 'PDF scan' : 'gambar'}, dibaca Claude langsung`]
  return ['waspada', 'teks tidak terbaca']
}

function kirimBerkas(berkas, persen) {
  return new Promise((selesai, gagal) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/laravel/p/${props.d.slug}/unggah?nama=${encodeURIComponent(berkas.name)}&oleh=${encodeURIComponent(namaSaya.value.trim())}`)
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) persen(Math.round((e.loaded / e.total) * 100)) }
    xhr.onload = () => {
      let obj = {}
      try { obj = JSON.parse(xhr.responseText) } catch { /* nginx 413 berupa HTML */ }
      if (xhr.status >= 200 && xhr.status < 300 && !obj.error) selesai(obj)
      else gagal(new Error(obj.error || (xhr.status === 413 ? 'payload_too_large' : `HTTP ${xhr.status}`)))
    }
    xhr.onerror = () => gagal(new Error('Koneksi terputus saat mengunggah.'))
    xhr.send(berkas)
  })
}

async function unggahSemua(daftar) {
  if (!daftar.length || !bisa.value || unggah.value) return
  status.value = { kelas: '', teks: '' }
  const galat = []
  let ok = 0
  for (const [i, f] of daftar.entries()) {
    if (f.size > MAKS) { galat.push(`${f.name}: lebih dari 25 MB`); continue }
    const awal = `Mengunggah ${f.name}${daftar.length > 1 ? ` (${i + 1}/${daftar.length})` : ''}`
    unggah.value = `${awal}…`
    try {
      await kirimBerkas(f, (p) => { unggah.value = p < 100 ? `${awal}… ${p}%` : `${awal}… membaca isi dokumen` })
      ok++
    } catch (e) { galat.push(`${f.name}: ${pesanGalat(e)}`) }
  }
  unggah.value = ''
  if (input.value) input.value.value = ''
  if (ok) emit('ubah')
  const lanjut = props.d.prd || props.d.saran ? ' Minta saran / susun ulang PRD supaya ikut dibaca Claude.' : ''
  status.value = galat.length
    ? { kelas: 'bahaya', teks: `${ok ? `${ok} dokumen terunggah. ` : ''}Gagal: ${galat.join('; ')}` }
    : { kelas: 'baik', teks: `${ok} dokumen terunggah.${lanjut}` }
}
const pilih = (e) => unggahSemua([...(e.target.files || [])])
function jatuh(e) {
  seret.value = false
  unggahSemua([...(e.dataTransfer?.files || [])])
}

async function hapus(x) {
  if (!(await konfirmasi({ judul: `Hapus ${x.nama}?`, teks: 'Berkas dihapus dari server dan tidak ikut dibaca Claude lagi.', tombol: 'Hapus', kelas: 'bahaya' }))) return
  status.value = { kelas: '', teks: '' }
  try { await aksi(props.d.slug, 'hapus_dokumen', { nama: x.nama }); emit('ubah') } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
</script>

<template>
  <div class="dok-klien">
    <div class="judul">
      <h3 id="h-dok-klien">Dokumen klien</h3>
      <span v-if="dokumen.length" class="redup">{{ dokumen.length }} berkas</span>
    </div>
    <ul v-if="dokumen.length" class="daftar" aria-labelledby="h-dok-klien">
      <li v-for="x in dokumen" :key="x.nama">
        <Ikon nama="dokumen" :ukuran="18" class="ikon" />
        <div class="info">
          <a :href="urlBerkas(x.nama)" target="_blank" rel="noopener" class="nama">{{ x.nama }}</a>
          <span class="redup kecil">{{ ukuranBerkas(x.ukuran) }} · {{ x.oleh }} · {{ waktuLalu(x.waktu) }}</span>
        </div>
        <span class="pil" :class="keterangan(x)[0]" :title="x.jenis === 'kosong' ? 'Isi tidak bisa diekstrak; simpan ulang sebagai PDF lalu unggah lagi.' : ''">{{ keterangan(x)[1] }}</span>
        <button v-if="!dikunci" type="button" class="hapus" :disabled="!bisa" :aria-label="`Hapus ${x.nama}`" title="Hapus" @click="hapus(x)">
          <Ikon nama="sampah" :ukuran="16" />
        </button>
      </li>
    </ul>
    <label v-if="!dikunci" class="zona" :class="{ seret, mati: !bisa || !!unggah }"
           @dragover.prevent="seret = bisa" @dragleave.prevent="seret = false" @drop.prevent="jatuh">
      <input ref="input" type="file" multiple :accept="TERIMA" :disabled="!bisa || !!unggah" class="sr" @change="pilih">
      <Ikon nama="unggah" :ukuran="20" />
      <span v-if="unggah" role="status">{{ unggah }}</span>
      <span v-else><b>Pilih berkas</b> atau seret ke sini</span>
      <span class="redup kecil">PDF, Word, Excel (.xlsx), PowerPoint, TXT/CSV, gambar · maks 25 MB per berkas</span>
    </label>
    <p v-if="sibukClaude" class="redup kecil">Claude sedang membaca bahan; unggah/hapus dokumen setelah selesai.</p>
    <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
  </div>
</template>

<style scoped>
.dok-klien { margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--garis); display: grid; gap: 10px; }
.judul { display: flex; align-items: baseline; gap: 10px; }
.judul h3 { margin: 0; font-size: 14px; }
.daftar { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.daftar li { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 10px; background: var(--kartu-2); min-width: 0; }
.ikon { flex: none; color: var(--teks-2); }
.info { display: grid; min-width: 0; flex: 1; }
.nama { color: var(--teks); font-weight: 600; font-size: 13.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nama:hover { color: var(--aksen); }
.kecil { font-size: 12px; }
.pil { flex: none; }
.hapus { flex: none; display: grid; place-items: center; width: 30px; height: 30px; border: 0; border-radius: 8px; background: transparent; color: var(--teks-2); cursor: pointer; }
.hapus:hover:not(:disabled) { color: var(--bahaya); background: rgba(255, 107, 107, .1); }
.hapus:disabled { opacity: .4; cursor: not-allowed; }
.zona { display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 6px 10px; padding: 16px; border: 1.5px dashed var(--garis); border-radius: 12px; color: var(--teks-2); text-align: center; cursor: pointer; transition: border-color .15s, background .15s; }
.zona b { color: var(--aksen); }
.zona:hover:not(.mati), .zona.seret { border-color: var(--aksen); background: rgba(61, 107, 255, .06); }
.zona:focus-within { outline: 2px solid var(--aksen); outline-offset: 2px; }
.zona.mati { cursor: not-allowed; opacity: .6; }
.zona .kecil { flex-basis: 100%; }
.pesan-status { margin: 0; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
@media (max-width: 560px) { .daftar li { flex-wrap: wrap; } .pil { order: 3; margin-left: 28px; } }
</style>
