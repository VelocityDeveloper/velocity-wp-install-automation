<script setup>
// Tahap 1 Brief, urut sesuai alur kerja (7 Okt): PM menempel catatan/chat diskusi klien + mengunggah dokumen klien
// (DokumenKlien) → semua pertanyaan ke klien di satu panel (PertanyaanKlien) → Claude menyarankan platform
// (SaranPlatform) → PM memilih → Claude menyusun draf DESIGN.md + PRD.md, lalu DATABASE.md (ERD Mermaid) +
// FLOWCHART.md (alur proses Mermaid) → PM menyunting → contoh tampilan untuk klien (ContohTampilan, memakai DESIGN.md).
import { ref, computed, watch } from 'vue'
import LogLive from './LogLive.vue'
import DokDiagram from './DokDiagram.vue'
import SaranPlatform from './SaranPlatform.vue'
import DokumenKlien from './DokumenKlien.vue'
import RangkumanKlien from './RangkumanKlien.vue'
import ContohTampilan from './ContohTampilan.vue'
import ReferensiDesain from './ReferensiDesain.vue'
import PertanyaanKlien from './PertanyaanKlien.vue'
import Ikon from '../Ikon.vue'
import { aksi, pesanGalat, namaSaya, keNama } from '../../laravel.js'
import { konfirmasi } from '../../konfirmasi.js'
import { tanggalWaktu } from '../../api.js'

const props = defineProps({ d: { type: Object, required: true } })
const emit = defineEmits(['ubah'])

const catatan = ref(props.d.catatan)
const DOK = [
  { kunci: 'prd', label: 'PRD.md', ket: 'PRD: peran pengguna, fitur beserta <b>kriteria terima</b> yang bisa diuji, data utama, di luar cakupan, dan pertanyaan terbuka untuk klien.' },
  { kunci: 'design', label: 'DESIGN.md', ket: 'DESIGN.md: token warna, tipografi, radius, jarak, dan komponen (format design.md, seperti SIA VD). Agen memakainya untuk tema aplikasi.' },
  { kunci: 'database', label: 'Relasi database', ket: 'DATABASE.md: diagram ERD (Mermaid) + rincian kolom, indeks, dan perilaku hapus tiap tabel. Agen membuat migrasi & model mengikuti dokumen ini.', diagram: true },
  { kunci: 'flowchart', label: 'Flowchart', ket: 'FLOWCHART.md: alur umum per peran dan alur tiap proses bisnis (Mermaid), termasuk jalur gagal/penolakan.', diagram: true },
]
const KUNCI_DOK = DOK.map((x) => x.kunci)
const ambilDok = () => Object.fromEntries(KUNCI_DOK.map((k) => [k, props.d[k] || '']))
const dok = ref(ambilDok())
// Tab dokumen & mode tampilan cukup state lokal (tidak ditulis ke URL)
const tab = ref('prd')
const pilihanPlatform = computed(() => props.d.saran?.pilihan || null)
const tabDok = computed(() => DOK.find((x) => x.kunci === tab.value) || DOK[0])
const mode = ref('diagram')   // untuk dokumen diagram: pratinjau atau sunting
// Isi server baru (mis. Claude selesai) masuk ke editor hanya bila editor belum disunting
const asal = ref({ catatan: props.d.catatan, ...ambilDok() })
watch(() => [props.d.catatan, ...KUNCI_DOK.map((k) => props.d[k])], () => {
  if (catatan.value === asal.value.catatan) catatan.value = props.d.catatan
  for (const k of KUNCI_DOK) if (dok.value[k] === asal.value[k]) dok.value[k] = props.d[k] || ''
  asal.value = { catatan: props.d.catatan, ...ambilDok() }
})
const berubahCatatan = computed(() => catatan.value !== asal.value.catatan)
const berubahDok = computed(() => KUNCI_DOK.some((k) => dok.value[k] !== asal.value[k]))
const dikunci = computed(() => !!props.d.estimasi_kunci)
// Selama Claude menyusun ulang, dokumen lama disembunyikan (akan diganti); suntingan yang belum disimpan tetap di `dok`
const menyusunDok = computed(() => ['susun', 'diagram'].includes(props.d.job?.jenis))
const status = ref({ kelas: '', teks: '' })
const statusDok = ref({ kelas: '', teks: '' })
const adaDok = computed(() => KUNCI_DOK.some((k) => (props.d[k] || '').trim()))


async function lakukan(fn, pesanOk, target = status) {
  target.value = { kelas: '', teks: '' }
  try { await fn(); target.value = { kelas: 'baik', teks: pesanOk }; emit('ubah') } catch (e) { target.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
const simpanCatatanSaja = () => aksi(props.d.slug, 'simpan', { catatan: catatan.value })
const simpanCatatan = () => lakukan(() => aksi(props.d.slug, 'simpan', { catatan: catatan.value }), 'Catatan disimpan.')
const simpanDok = () => lakukan(() => aksi(props.d.slug, 'simpan', Object.fromEntries(KUNCI_DOK.filter((k) => dok.value[k] !== asal.value[k]).map((k) => [k, dok.value[k]]))), 'Dokumen disimpan.', statusDok)
async function susunDiagram() {
  if ((props.d.database || props.d.flowchart) && !(await konfirmasi({
    judul: 'Susun ulang relasi database & flowchart?', tombol: 'Susun ulang', kelas: 'waspada',
    teks: 'Versi sekarang disimpan sebagai cadangan (.bak). Claude diminta mempertahankan suntingan Anda dan hanya memperbarui yang berubah karena PRD.',
  }))) return
  await lakukan(async () => {
    if (berubahDok.value) await simpanDok()
    await aksi(props.d.slug, 'diagram')
  }, 'Claude mulai menyusun relasi database & flowchart (2–5 menit).', statusDok)
}
async function susun() {
  if ((props.d.prd || props.d.design) && !(await konfirmasi({
    judul: 'Susun ulang dengan Claude?', tombol: 'Susun ulang', kelas: 'waspada',
    teks: 'Draf sekarang disimpan sebagai cadangan (.bak). Claude diminta mempertahankan suntingan Anda dan hanya memperbarui yang berubah karena catatan baru. Relasi database & flowchart hanya disusun ulang bila peran, data, atau alur proses ikut berubah.',
  }))) return
  await lakukan(async () => {
    if (berubahCatatan.value) await aksi(props.d.slug, 'simpan', { catatan: catatan.value })
    await aksi(props.d.slug, 'susun')
  }, 'Claude mulai menyusun (2–6 menit).', statusDok)
}
// Kebutuhan konten halaman publik: PM menandai, laravel-brief memasukkannya ke susun PRD, estimasi & rangkuman
const KONTEN = [
  { kunci: '', label: 'Belum ditandai', ket: 'Claude tidak menambah fitur pengelolaan konten; bila catatan mengisyaratkan klien ingin mengubah sendiri, ditulis di Pertanyaan terbuka.' },
  { kunci: 'statis', label: 'Statis', ket: 'Teks beranda, FAQ, cara order, dsb. ditulis di kode. Perubahan lewat developer.' },
  { kunci: 'bersekat', label: 'Konten bersekat', ket: 'Klien mengubah isi sendiri lewat form Admin per seksi (hero, keunggulan, FAQ, cara order, menu & footer, kontak). Tata letak tetap. ±1 fitur.' },
  { kunci: 'page_builder', label: 'Page builder', ket: 'Klien menyusun halaman sendiri (halaman baru, seret-lepas seksi) seperti expedisi-vd. Lebih mahal, perlu pelatihan klien.' },
]
const konten = computed(() => props.d.konten?.mode || '')
const statusKonten = ref({ kelas: '', teks: '' })
const pilihKonten = (k) => k !== konten.value && lakukan(() => aksi(props.d.slug, 'simpan', { konten: k || null }),
  `Kebutuhan konten: ${KONTEN.find((x) => x.kunci === k).label}.${props.d.prd ? ' Susun ulang PRD & estimasi agar ikut berubah.' : ''}`, statusKonten)
const versiTerakhir = computed(() => props.d.brief?.riwayat?.[0])
const hitungKata = (t) => (t.trim() ? t.trim().split(/\s+/).length : 0)
</script>

<template>
  <section class="kartu" aria-labelledby="h-catatan">
    <div class="kartu-judul">
      <h2 id="h-catatan">Catatan diskusi klien</h2>
      <span class="redup">{{ hitungKata(catatan).toLocaleString('id-ID') }} kata</span>
      <span class="pil versi" :title="versiTerakhir ? `Terakhir: ${versiTerakhir.oleh} mengubah ${versiTerakhir.bagian.join(', ')} · ${tanggalWaktu(versiTerakhir.waktu)}` : 'Brief belum berisi'">brief v{{ d.brief?.versi || 0 }}</span>
    </div>
    <p class="redup bantu">Tempel ringkasan meeting, chat WA, atau poin kebutuhan dari klien apa adanya. Makin lengkap (peran pengguna, alur kerja, contoh data, warna/logo), makin baik drafnya. Dokumen dari klien bisa diunggah di bawah. Catatan boleh ditambah lalu disusun ulang.</p>
    <textarea v-model="catatan" class="catatan" :disabled="dikunci" :rows="catatan.trim() ? 8 : 12" placeholder="Contoh: Klien toko bangunan, ingin aplikasi kasir + stok 2 cabang. Kasir input penjualan, admin gudang kelola stok & mutasi antar cabang, owner lihat laporan harian…" />
    <div class="aksi">
      <button type="button" class="tombol garis" :disabled="!berubahCatatan || dikunci || !namaSaya.trim()" @click="simpanCatatan">Simpan catatan</button>
      <button v-if="!namaSaya.trim()" type="button" class="isi-nama" @click="keNama">Masuk dulu →</button>
      <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
    </div>
    <fieldset class="konten">
      <legend>Kebutuhan konten halaman <span class="redup">— apakah klien akan mengubah isi halaman sendiri tanpa developer?</span></legend>
      <div class="tab" role="radiogroup" aria-label="Kebutuhan konten halaman">
        <button v-for="x in KONTEN" :key="x.kunci" type="button" role="radio" :aria-checked="konten === x.kunci"
          :class="{ aktif: konten === x.kunci }" :disabled="!namaSaya.trim()" @click="pilihKonten(x.kunci)">{{ x.label }}</button>
      </div>
      <p class="redup">{{ KONTEN.find((x) => x.kunci === konten).ket }}<template v-if="d.konten"> · ditandai {{ d.konten.oleh }}, {{ tanggalWaktu(d.konten.waktu) }}</template></p>
      <p v-if="statusKonten.teks" class="pesan-status" :class="statusKonten.kelas" role="status">{{ statusKonten.teks }}</p>
    </fieldset>
    <ReferensiDesain :d="d" @ubah="emit('ubah')" />
    <DokumenKlien :d="d" @ubah="emit('ubah')" />
    <RangkumanKlien :d="d" :catatan-berubah="berubahCatatan" :simpan-catatan="simpanCatatanSaja" @ubah="emit('ubah')" />
    <details v-if="d.brief?.riwayat?.length" class="riwayat-versi">
      <summary>Riwayat versi brief <span class="redup">(sekarang v{{ d.brief.versi }}; naik setiap catatan, dokumen klien, kebutuhan konten, referensi desain, PRD, DESIGN.md, relasi database, atau flowchart berubah)</span></summary>
      <ul>
        <li v-for="v in d.brief.riwayat" :key="v.versi">
          <b>v{{ v.versi }}</b> <span class="redup">{{ tanggalWaktu(v.waktu) }}</span> {{ v.oleh }}
          {{ v.awal ? 'versi awal (sebelum penomoran):' : 'mengubah' }} {{ v.bagian.join(', ') }}
        </li>
      </ul>
    </details>
  </section>

  <PertanyaanKlien :d="d" />

  <SaranPlatform :d="d" :catatan-berubah="berubahCatatan" :simpan-catatan="simpanCatatanSaja" @ubah="emit('ubah')" @susun="susun" />

  <section v-if="menyusunDok" class="kartu disusun" aria-labelledby="h-dok-tunggu" role="status">
    <div class="kartu-judul"><h2 id="h-dok-tunggu">Dokumen spesifikasi</h2><span class="pil waspada">sedang disusun</span></div>
    <p class="redup">{{ d.job.jenis === 'susun' ? 'Claude sedang menyusun ulang PRD.md dan DESIGN.md, lalu relasi database & flowchart' : 'Claude sedang menyusun ulang relasi database & flowchart' }}.
      Dokumen tampil lagi otomatis setelah selesai (2–10 menit). Versi sebelumnya tersimpan sebagai cadangan di server.</p>
    <LogLive :id="d.slug" :jenis="d.job.jenis" hidup tinggi="30vh" />
  </section>

  <section v-else class="kartu" aria-labelledby="h-dok">
    <div class="kartu-judul">
      <h2 id="h-dok">Dokumen spesifikasi</h2>
      <div class="tab" role="tablist" aria-label="Dokumen">
        <button v-for="x in DOK" :key="x.kunci" type="button" role="tab" :aria-selected="tabDok.kunci === x.kunci" :class="{ aktif: tabDok.kunci === x.kunci }" @click="tab = x.kunci">
          {{ x.label }}<i v-if="dok[x.kunci] !== asal[x.kunci]" class="ubah" aria-label="belum disimpan" />
        </button>
      </div>
    </div>
    <p v-if="dikunci" class="pesan-status">Estimasi sudah dikunci; dokumen hanya bisa dibaca. Buka kunci di tab Estimasi untuk mengubah.</p>
    <p v-else class="redup bantu" v-html="tabDok.ket" />
    <p v-if="!adaDok && !dikunci" class="pesan-status">Belum ada dokumen. {{ pilihanPlatform ? 'Klik "Lanjut: susun PRD" di Saran platform' : 'Pilih platform di Saran platform, lalu klik "Lanjut: susun PRD"' }} agar Claude menyusunnya, atau tulis sendiri di bawah.</p>
    <details v-if="!tabDok.diagram && d.ringkasan_brief.length" class="hasil-claude lipat">
      <summary><b>Catatan Claude untuk PM</b> <span class="redup">({{ d.ringkasan_brief.length }} poin: keputusan, asumsi, pertanyaan)</span></summary>
      <ul><li v-for="(r, i) in d.ringkasan_brief" :key="i">{{ r }}</li></ul>
    </details>

    <template v-if="tabDok.diagram">
      <div class="baris-diagram">
        <div class="tab kecil" role="tablist" aria-label="Tampilan">
          <button type="button" role="tab" :aria-selected="mode === 'diagram'" :class="{ aktif: mode === 'diagram' }" @click="mode = 'diagram'">Diagram</button>
          <button type="button" role="tab" :aria-selected="mode === 'sunting'" :class="{ aktif: mode === 'sunting' }" @click="mode = 'sunting'">Sunting</button>
        </div>
        <button v-if="!dikunci" type="button" class="tombol garis kecil" :disabled="!d.prd.trim() || !!d.job || !namaSaya.trim()" @click="susunDiagram">
          <Ikon nama="claude" :ukuran="16" /> {{ d.database || d.flowchart ? 'Susun ulang relasi & flowchart' : 'Susun relasi database & flowchart dengan Claude' }}
        </button>
      </div>
      <div v-if="d.catatan_diagram.length && !d.job" class="hasil-claude">
        <b>Catatan Claude untuk PM</b>
        <ul><li v-for="(r, i) in d.catatan_diagram" :key="i">{{ r }}</li></ul>
      </div>
    </template>
    <DokDiagram v-if="tabDok.diagram && mode === 'diagram'" :md="dok[tabDok.kunci]" />
    <template v-else>
      <label class="sr" :for="`dok-${tabDok.kunci}`">{{ tabDok.label }}</label>
      <textarea :id="`dok-${tabDok.kunci}`" v-model="dok[tabDok.kunci]" class="md" :readonly="dikunci" rows="26" spellcheck="false" :placeholder="`Belum ada ${tabDok.label}. Susun dengan Claude, atau tulis sendiri.`" />
    </template>
    <div class="aksi">
      <button type="button" class="tombol" :disabled="!berubahDok || dikunci || !namaSaya.trim()" @click="simpanDok">Simpan dokumen</button>
      <span v-if="berubahDok" class="redup">Ada perubahan belum disimpan.</span>
      <button v-if="!dikunci && (d.prd || d.design)" type="button" class="tombol garis kanan" :disabled="!catatan.trim() && !d.dokumen?.length || !!d.job || !namaSaya.trim()" @click="susun">
        <Ikon nama="claude" :ukuran="18" /> Susun ulang PRD &amp; DESIGN.md
      </button>
      <p v-if="statusDok.teks" class="pesan-status" :class="statusDok.kelas" role="status">{{ statusDok.teks }}</p>
    </div>
  </section>

  <ContohTampilan :d="d" :catatan-berubah="berubahCatatan" :simpan-catatan="simpanCatatanSaja" @ubah="emit('ubah')" />
</template>

<style scoped>
.bantu { margin: -6px 0 12px; }
textarea { font: 13px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.catatan { font-family: inherit; font-size: 14px; }
.md { min-height: 420px; }
.aksi { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.aksi p { margin: 0; }
.hasil-claude { margin-top: 14px; padding: 12px 14px; border-radius: 12px; background: var(--kartu-2); }
.hasil-claude ul { margin: 8px 0 0; padding-left: 18px; display: grid; gap: 4px; color: var(--teks-2); }
.tab { display: flex; flex-wrap: wrap; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.baris-diagram { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.tab.kecil button { padding: 4px 10px; font-size: 12.5px; }
.disusun p { margin: 0 0 12px; }
.lipat { margin: 0 0 12px; }
.lipat summary { cursor: pointer; }
.lipat[open] summary { margin-bottom: 4px; }
.aksi .kanan { margin-left: auto; }
.hasil-claude + * { margin-top: 12px; }
.ubah { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--waspada); margin-left: 6px; vertical-align: 2px; }
.versi { margin-left: auto; }
.versi::before { display: none; }
.riwayat-versi { margin-top: 14px; font-size: 13px; }
.riwayat-versi summary { cursor: pointer; }
.riwayat-versi ul { margin: 8px 0 0; padding-left: 18px; display: grid; gap: 3px; color: var(--teks-2); max-height: 220px; overflow: auto; }
.konten { margin: 16px 0 0; padding: 12px 14px; border: 1px solid var(--garis); border-radius: 12px; }
.konten legend { padding: 0 6px; font-size: 13.5px; font-weight: 600; }
.konten legend .redup { font-weight: 400; }
.konten .tab { width: fit-content; max-width: 100%; }
.konten p { margin: 8px 0 0; font-size: 13px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>
