<script setup>
// Tahap 5 Review: webmaster memeriksa tiap fitur yang sudah dikerjakan & dites agen.
// Checklist = kriteria terima PRD; di sampingnya status & bukti dari agen. OK butuh semua tercentang; Revisi kembali ke agen.
import { ref, reactive, computed, watch } from 'vue'
import Ikon from '../Ikon.vue'
import { aksi, pesanGalat, namaSaya, keNama, STATUS_FITUR } from '../../laravel.js'
import { tanggalWaktu } from '../../api.js'

const props = defineProps({ d: { type: Object, required: true } })
const emit = defineEmits(['ubah'])
const bisaDicek = computed(() => props.d.fitur.filter((f) => ['dites', 'ok', 'revisi'].includes(f.status) && f.hasil))
const ok = computed(() => props.d.fitur.filter((f) => f.status === 'ok').length)
const alamat = computed(() => props.d.install?.port ? `http://${location.hostname}:${props.d.install.port}` : '')

// Centang & catatan per fitur (disimpan ke server saat tombol ditekan)
const draf = reactive({})
watch(() => props.d.fitur, (fs) => {
  for (const f of fs) {
    const tanda = JSON.stringify([f.status, f.review?.waktu, f.hasil?.waktu])
    if (draf[f.id]?.tanda !== tanda) draf[f.id] = { tanda, cek: f.kriteria.map((k) => !!k.cek), catatan: '' }
  }
}, { immediate: true })
const pilihan = ref('')
const aktif = computed(() => pilihan.value || bisaDicek.value.find((f) => f.status === 'dites')?.id || bisaDicek.value[0]?.id || '')
const f = computed(() => props.d.fitur.find((x) => x.id === aktif.value))
const semuaCek = computed(() => f.value && draf[f.value.id]?.cek.every(Boolean))
const status = ref({ kelas: '', teks: '' })
async function putus(keputusan) {
  status.value = { kelas: '', teks: '' }
  const x = draf[f.value.id]
  try {
    await aksi(props.d.slug, 'review', { fitur: f.value.id, keputusan, cek: x.cek, catatan: x.catatan })
    status.value = { kelas: 'baik', teks: keputusan === 'ok' ? `${f.value.id} OK.` : keputusan === 'revisi' ? `${f.value.id} dikembalikan ke agen. Tekan Lanjutkan agen di tab Agen.` : 'Centang disimpan.' }
    if (keputusan === 'ok') pilihan.value = ''
    emit('ubah')
  } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
const AGEN = { terpenuhi: ['hijau', 'terpenuhi'], sebagian: ['kuning', 'sebagian'], belum: ['merah', 'belum'] }
</script>

<template>
  <section class="kartu" aria-labelledby="h-rev">
    <div class="kartu-judul">
      <h2 id="h-rev">Review webmaster</h2>
      <div class="ringkas"><span><b>{{ ok }}</b>/{{ d.fitur.length }} fitur OK</span>
        <a v-if="alamat" class="tombol kecil" :href="alamat" target="_blank" rel="noopener">Buka aplikasi dev <Ikon nama="luar" :ukuran="14" /></a>
        <RouterLink to="/projects" class="tombol garis kecil">Akun uji</RouterLink>
      </div>
    </div>
    <p v-if="d.agen?.deploy?.ok" class="redup kecil">Dev dideploy {{ tanggalWaktu(d.agen.deploy.waktu) }} dari commit <a :href="`${d.install.repo}/commit/${d.agen.deploy.commit}`" target="_blank" rel="noopener"><code>{{ d.agen.deploy.commit }}</code></a> — yang dicek di aplikasi dev = hasil terakhir agen.</p>
    <p v-else-if="bisaDicek.some((x) => x.status === 'dites')" class="pesan-status waspada-teks">Dev belum dideploy untuk hasil terakhir agen — jalankan Deploy dev di tab Agen dulu supaya yang direview sesuai.</p>
    <p v-if="!bisaDicek.length" class="redup">Belum ada fitur yang selesai dikerjakan agen.</p>

    <div v-else class="dua">
      <ul class="daftar" aria-label="Fitur">
        <li v-for="x in bisaDicek" :key="x.id">
          <button type="button" :class="{ aktif: aktif === x.id }" :aria-current="aktif === x.id ? 'true' : undefined" @click="pilihan = x.id; status = { kelas: '', teks: '' }">
            <span class="fid">{{ x.id }}</span><span class="dj">{{ x.judul }}</span>
            <span class="lencana" :class="STATUS_FITUR[x.status]?.[0]">{{ STATUS_FITUR[x.status]?.[1] }}</span>
          </button>
        </li>
      </ul>

      <article v-if="f" class="rinci" :aria-label="`Review ${f.id}`">
        <h3>{{ f.id }} · {{ f.judul }}</h3>
        <p v-if="f.hasil.ringkasan">{{ f.hasil.ringkasan }}</p>
        <p class="redup kecil">Dikerjakan agen {{ tanggalWaktu(f.hasil.waktu) }} · {{ f.hasil.tes_lulus ?? '?' }} tes lolos
          <template v-if="f.hasil.commit"> · commit <a :href="`${d.install.repo}/commit/${f.hasil.commit}`" target="_blank" rel="noopener"><code>{{ f.hasil.commit }}</code></a></template>
          <template v-if="f.review"> · review terakhir {{ f.review.oleh }} {{ tanggalWaktu(f.review.waktu) }}</template>
        </p>

        <div v-if="f.hasil.cara_cek?.length" class="blok">
          <b>Cara cek di browser (dari agen)</b>
          <ol><li v-for="(c, i) in f.hasil.cara_cek" :key="i">{{ c }}</li></ol>
        </div>
        <div v-if="f.hasil.catatan_webmaster" class="blok waspada"><b>Catatan agen</b><p>{{ f.hasil.catatan_webmaster }}</p></div>

        <fieldset class="checklist">
          <legend>Checklist kriteria terima</legend>
          <label v-for="(k, i) in f.kriteria" :key="i" class="kr">
            <input v-model="draf[f.id].cek[i]" type="checkbox" :disabled="f.status === 'revisi'">
            <span>
              {{ k.teks }}
              <small v-if="k.agen" class="agen"><span class="lencana" :class="AGEN[k.agen.status]?.[0]">agen: {{ AGEN[k.agen.status]?.[1] || k.agen.status }}</span> {{ k.agen.bukti }}</small>
            </span>
          </label>
        </fieldset>

        <div v-if="f.revisi?.length" class="blok"><b>Riwayat revisi</b>
          <ul><li v-for="(r, i) in f.revisi" :key="i"><span class="redup">{{ tanggalWaktu(r.waktu) }} {{ r.oleh }}:</span> {{ r.catatan }}</li></ul>
        </div>

        <template v-if="f.status !== 'revisi'">
          <label class="isian"><span>Catatan revisi untuk agen <em>(wajib bila Revisi)</em></span>
            <textarea v-model="draf[f.id].catatan" rows="3" placeholder="Apa yang salah / kurang, di halaman mana, harusnya bagaimana." /></label>
          <div class="aksi">
            <button type="button" class="tombol" :disabled="!semuaCek || !namaSaya.trim()" @click="putus('ok')"><Ikon nama="centang" :ukuran="16" /> Fitur OK</button>
            <button type="button" class="tombol waspada" :disabled="!draf[f.id].catatan.trim() || !namaSaya.trim()" @click="putus('revisi')">Revisi ke agen</button>
            <button type="button" class="tombol garis" :disabled="!namaSaya.trim()" @click="putus('simpan')">Simpan centang</button>
          </div>
        </template>
        <p v-else class="pesan-status">Menunggu agen mengerjakan revisi (tab Agen).</p>
        <button v-if="!namaSaya.trim()" type="button" class="isi-nama" @click="keNama">Isi "Nama Anda" dulu →</button>
        <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.ringkas { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; font-size: 13px; color: var(--teks-2); }
.ringkas b { color: var(--teks); }
.dua { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 16px; align-items: start; }
.daftar { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
.daftar button { width: 100%; display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 2px 8px; text-align: left; padding: 8px 10px; border-radius: 10px; border: 1px solid transparent; background: transparent; cursor: pointer; }
.daftar button:hover { background: var(--kartu-2); }
.daftar button.aktif { background: var(--kartu-2); border-color: var(--aksen-terang); }
.daftar .lencana { grid-column: 2; width: fit-content; }
.dj { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; font-size: 13.5px; }
.fid { font: 700 12px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--aksen-terang); padding-top: 2px; }
.rinci { display: grid; gap: 12px; min-width: 0; }
.rinci h3 { font-size: 16px; }
.rinci p { margin: 0; }
.kecil { font-size: 12px; }
.waspada-teks { color: var(--waspada); }
code { font: 12px ui-monospace, SFMono-Regular, Consolas, monospace; }
.blok { padding: 10px 12px; border-radius: 10px; background: var(--kartu-2); font-size: 13.5px; }
.blok ol, .blok ul { margin: 6px 0 0; padding-left: 20px; display: grid; gap: 3px; color: var(--teks-2); }
.blok p { margin-top: 4px; color: var(--teks-2); }
.blok.waspada { border-left: 3px solid var(--waspada); }
.checklist { margin: 0; padding: 12px; border: 1px solid var(--garis); border-radius: 12px; display: grid; gap: 10px; }
.checklist legend { padding: 0 6px; font-weight: 600; font-size: 13px; color: var(--teks-2); }
.kr { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 10px; align-items: start; cursor: pointer; font-size: 14px; }
.kr input { margin-top: 2px; }
.agen { display: block; margin-top: 3px; color: var(--teks-3); font-size: 12px; overflow-wrap: anywhere; }
.agen .lencana { margin-right: 4px; }
.isian em { font-style: normal; color: var(--teks-3); font-weight: 500; font-size: 12px; }
.aksi { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
@media (max-width: 820px) { .dua { grid-template-columns: minmax(0, 1fr); } }
</style>
