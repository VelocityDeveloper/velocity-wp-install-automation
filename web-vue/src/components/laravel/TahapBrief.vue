<script setup>
// Tahap 1 Brief: PM menempel catatan/chat diskusi klien → Claude menyusun draf DESIGN.md + PRD.md, lalu
// DATABASE.md (ERD Mermaid) + FLOWCHART.md (alur proses Mermaid) → PM menyunting.
import { ref, computed, watch } from 'vue'
import LogLive from './LogLive.vue'
import DokDiagram from './DokDiagram.vue'
import Ikon from '../Ikon.vue'
import { aksi, pesanGalat, namaSaya, keNama } from '../../laravel.js'
import { konfirmasi } from '../../konfirmasi.js'

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
const tab = ref('prd')
const tabDok = computed(() => DOK.find((x) => x.kunci === tab.value))
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
const jalanSusun = computed(() => props.d.job?.jenis === 'susun')
// Selama Claude menyusun ulang, dokumen lama disembunyikan (akan diganti); suntingan yang belum disimpan tetap di `dok`
const menyusunDok = computed(() => ['susun', 'diagram'].includes(props.d.job?.jenis))
const status = ref({ kelas: '', teks: '' })

async function lakukan(fn, pesanOk) {
  status.value = { kelas: '', teks: '' }
  try { await fn(); status.value = { kelas: 'baik', teks: pesanOk }; emit('ubah') } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
const simpanCatatan = () => lakukan(() => aksi(props.d.slug, 'simpan', { catatan: catatan.value }), 'Catatan disimpan.')
const simpanDok = () => lakukan(() => aksi(props.d.slug, 'simpan', Object.fromEntries(KUNCI_DOK.filter((k) => dok.value[k] !== asal.value[k]).map((k) => [k, dok.value[k]]))), 'Dokumen disimpan.')
async function susunDiagram() {
  if ((props.d.database || props.d.flowchart) && !(await konfirmasi({
    judul: 'Susun ulang relasi database & flowchart?', tombol: 'Susun ulang', kelas: 'waspada',
    teks: 'Versi sekarang disimpan sebagai cadangan (.bak). Claude diminta mempertahankan suntingan Anda dan hanya memperbarui yang berubah karena PRD.',
  }))) return
  await lakukan(async () => {
    if (berubahDok.value) await simpanDok()
    await aksi(props.d.slug, 'diagram')
  }, 'Claude mulai menyusun relasi database & flowchart (2–5 menit).')
}
async function susun() {
  if ((props.d.prd || props.d.design) && !(await konfirmasi({
    judul: 'Susun ulang dengan Claude?', tombol: 'Susun ulang', kelas: 'waspada',
    teks: 'Draf sekarang disimpan sebagai cadangan (.bak). Claude diminta mempertahankan suntingan Anda dan hanya memperbarui yang berubah karena catatan baru.',
  }))) return
  await lakukan(async () => {
    if (berubahCatatan.value) await aksi(props.d.slug, 'simpan', { catatan: catatan.value })
    await aksi(props.d.slug, 'susun')
  }, 'Claude mulai menyusun (2–6 menit).')
}
const hitungKata = (t) => (t.trim() ? t.trim().split(/\s+/).length : 0)
</script>

<template>
  <section class="kartu" aria-labelledby="h-catatan">
    <div class="kartu-judul">
      <h2 id="h-catatan">Catatan diskusi klien</h2>
      <span class="redup">{{ hitungKata(catatan).toLocaleString('id-ID') }} kata</span>
    </div>
    <p class="redup bantu">Tempel ringkasan meeting, chat WA, atau poin kebutuhan dari klien apa adanya. Makin lengkap (peran pengguna, alur kerja, contoh data, warna/logo), makin baik drafnya. Catatan boleh ditambah lalu disusun ulang.</p>
    <textarea v-model="catatan" class="catatan" :disabled="dikunci" rows="12" placeholder="Contoh: Klien toko bangunan, ingin aplikasi kasir + stok 2 cabang. Kasir input penjualan, admin gudang kelola stok & mutasi antar cabang, owner lihat laporan harian…" />
    <div class="aksi">
      <button type="button" class="tombol garis" :disabled="!berubahCatatan || dikunci || !namaSaya.trim()" @click="simpanCatatan">Simpan catatan</button>
      <button type="button" class="tombol" :disabled="!catatan.trim() || dikunci || !!d.job || !namaSaya.trim()" @click="susun">
        <Ikon nama="claude" :ukuran="18" /> {{ d.prd || d.design ? 'Susun ulang dengan Claude' : 'Susun DESIGN.md + PRD dengan Claude' }}
      </button>
      <button v-if="!namaSaya.trim()" type="button" class="isi-nama" @click="keNama">Isi "Nama Anda" dulu →</button>
      <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
    </div>
    <div v-if="jalanSusun || d.ringkasan_brief.length" class="hasil-claude">
      <LogLive v-if="jalanSusun" :id="d.slug" jenis="susun" hidup tinggi="30vh" />
      <template v-else>
        <b>Catatan Claude untuk PM</b>
        <ul><li v-for="(r, i) in d.ringkasan_brief" :key="i">{{ r }}</li></ul>
      </template>
    </div>
  </section>

  <section v-if="menyusunDok" class="kartu disusun" aria-labelledby="h-dok-tunggu" role="status">
    <div class="kartu-judul"><h2 id="h-dok-tunggu">Dokumen spesifikasi</h2><span class="pil waspada">sedang disusun</span></div>
    <p class="redup">{{ d.job.jenis === 'susun' ? 'Claude sedang menyusun ulang PRD.md dan DESIGN.md, lalu relasi database & flowchart' : 'Claude sedang menyusun ulang relasi database & flowchart' }}.
      Dokumen tampil lagi otomatis setelah selesai (2–10 menit). Versi sebelumnya tersimpan sebagai cadangan di server.</p>
    <LogLive v-if="d.job.jenis === 'diagram'" :id="d.slug" jenis="diagram" hidup tinggi="30vh" />
  </section>

  <section v-else class="kartu" aria-labelledby="h-dok">
    <div class="kartu-judul">
      <h2 id="h-dok">Dokumen spesifikasi</h2>
      <div class="tab" role="tablist" aria-label="Dokumen">
        <button v-for="x in DOK" :key="x.kunci" type="button" role="tab" :aria-selected="tab === x.kunci" :class="{ aktif: tab === x.kunci }" @click="tab = x.kunci">
          {{ x.label }}<i v-if="dok[x.kunci] !== asal[x.kunci]" class="ubah" aria-label="belum disimpan" />
        </button>
      </div>
    </div>
    <p v-if="dikunci" class="pesan-status">Estimasi sudah dikunci; dokumen hanya bisa dibaca. Buka kunci di tab Estimasi untuk mengubah.</p>
    <p v-else class="redup bantu" v-html="tabDok.ket" />

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
    <DokDiagram v-if="tabDok.diagram && mode === 'diagram'" :md="dok[tab]" />
    <template v-else>
      <label class="sr" :for="`dok-${tab}`">{{ tabDok.label }}</label>
      <textarea :id="`dok-${tab}`" v-model="dok[tab]" class="md" :readonly="dikunci" rows="26" spellcheck="false" :placeholder="`Belum ada ${tabDok.label}. Susun dengan Claude, atau tulis sendiri.`" />
    </template>
    <div class="aksi">
      <button type="button" class="tombol" :disabled="!berubahDok || dikunci || !namaSaya.trim()" @click="simpanDok">Simpan dokumen</button>
      <span v-if="berubahDok" class="redup">Ada perubahan belum disimpan.</span>
    </div>
  </section>
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
.hasil-claude + * { margin-top: 12px; }
.ubah { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--waspada); margin-left: 6px; vertical-align: 2px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>
