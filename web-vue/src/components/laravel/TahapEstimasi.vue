<script setup>
// Tahap 2 Estimasi: Claude memecah PRD jadi fitur (+ kriteria terima + jam agen/webmaster, internal) → PM menyunting & mengunci.
import { ref, computed, watch } from 'vue'
import LogLive from './LogLive.vue'
import Ikon from '../Ikon.vue'
import { aksi, pesanGalat, namaSaya, jam, hariJam, JAM_SEHARI, jadwal, jalurLaravel as cekJalur } from '../../laravel.js'
import { konfirmasi } from '../../konfirmasi.js'
import { tanggalWaktu } from '../../api.js'
import VersiBrief from './VersiBrief.vue'

const props = defineProps({ d: { type: Object, required: true } })
const emit = defineEmits(['ubah'])

// Editor: kriteria disunting sebagai teks satu baris per kriteria
// Halaman (sel Matriks peran × halaman PRD) disunting sebagai "Halaman: Peran, Peran" satu baris per halaman
const keEditor = (fs) => fs.map((f) => ({ judul: f.judul, deskripsi: f.deskripsi || '', kriteria: f.kriteria.map((k) => k.teks).join('\n'), jam_agen: f.jam_agen, jam_webmaster: f.jam_webmaster,
  halaman: (f.halaman || []).map((h) => `${h.halaman}: ${h.peran.join(', ')}`).join('\n') }))
const dariTeksHalaman = (t) => t.split('\n').map((b) => {
  const i = b.lastIndexOf(':')
  return i < 0 ? null : { halaman: b.slice(0, i).trim(), peran: b.slice(i + 1).split(',').map((x) => x.trim()).filter(Boolean) }
}).filter((h) => h && h.halaman && h.peran.length)
const fitur = ref(keEditor(props.d.fitur))
const asal = ref(JSON.stringify(keEditor(props.d.fitur)))
watch(() => props.d.fitur, (fs) => {
  const baru = JSON.stringify(keEditor(fs))
  if (JSON.stringify(fitur.value) === asal.value) fitur.value = keEditor(fs)
  asal.value = baru
})
// Pekerjaan di luar fitur (deploy, impor data, UAT & revisi klien, serah terima) — dikerjakan sesudah fitur
const keTambahan = (ts) => ts.map((t) => ({ judul: t.judul, jam_agen: t.jam_agen, jam_webmaster: t.jam_webmaster }))
const tambahan = ref(keTambahan(props.d.tambahan))
const asalTambahan = ref(JSON.stringify(keTambahan(props.d.tambahan)))
watch(() => props.d.tambahan, (ts) => {
  if (JSON.stringify(tambahan.value) === asalTambahan.value) tambahan.value = keTambahan(ts)
  asalTambahan.value = JSON.stringify(keTambahan(ts))
})
const berubahTambahan = computed(() => JSON.stringify(tambahan.value) !== asalTambahan.value || (props.d.tambahan_bawaan && fitur.value.length > 0))
const berubah = computed(() => JSON.stringify(fitur.value) !== asal.value)
const dikunci = computed(() => !!props.d.estimasi_kunci)
// Selama Claude memecah ulang PRD, daftar lama disembunyikan (akan diganti; suntingan saat itu akan tertimpa)
const memecah = computed(() => props.d.job?.jenis === 'estimasi')
// Estimasi untuk semua platform; bukan Laravel + Vue = dikerjakan webmaster (jam agen 0), tanpa install & agen otomatis
const jalurLaravel = computed(() => cekJalur(props.d))
const terinstall = computed(() => ['jalan', 'ok'].includes(props.d.install?.status))
const rencana = computed(() => jadwal(fitur.value, props.d.jadwal, tambahan.value))
const jumlah = (xs, k) => xs.reduce((n, x) => n + Number(x[k] || 0), 0)
const total = computed(() => ({
  agen: jumlah(fitur.value, 'jam_agen') + jumlah(tambahan.value, 'jam_agen'),
  wm: jumlah(fitur.value, 'jam_webmaster') + jumlah(tambahan.value, 'jam_webmaster'),
}))
const terbuka = ref(new Set())
const alih = (i) => { const s = new Set(terbuka.value); s.has(i) ? s.delete(i) : s.add(i); terbuka.value = s }
function tambah() { fitur.value.push({ judul: '', deskripsi: '', kriteria: '', jam_agen: 0.15, jam_webmaster: 0.5, halaman: '' }); alih(fitur.value.length - 1) }

// Kalibrasi: estimasi jam agen dibanding lama kerja agen yang nyata (semua project, L.kalibrasi_agen)
const kal = computed(() => props.d.kalibrasi)
const rataEstMenit = computed(() => (fitur.value.length ? jumlah(fitur.value, 'jam_agen') * 60 / fitur.value.length : 0))
const terlaluBesar = computed(() => kal.value && rataEstMenit.value > kal.value.menit_median * 3)
function sesuaikan() {
  const r = kal.value?.rasio
  if (!r) return
  const skala = (x) => Math.max(0.05, Math.round(Number(x || 0) * r * 100) / 100)
  for (const f of fitur.value) f.jam_agen = skala(f.jam_agen)
  // Revisi UAT bawaan = ±25% jam fitur, ikut diskalakan; pekerjaan lain dibiarkan untuk dicek PM
  for (const t of tambahan.value) if (/revisi/i.test(t.judul) && t.jam_agen) t.jam_agen = skala(t.jam_agen)
  status.value = { kelas: 'baik', teks: 'Jam agen disesuaikan dengan data nyata — periksa lalu Simpan.' }
}
const cak = computed(() => props.d.cakupan)
function hapus(i) { fitur.value.splice(i, 1); terbuka.value = new Set() }
function geser(i, arah) { const j = i + arah; if (j < 0 || j >= fitur.value.length) return; const f = fitur.value; [f[i], f[j]] = [f[j], f[i]]; terbuka.value = new Set() }

const status = ref({ kelas: '', teks: '' })
async function lakukan(fn, ok) {
  status.value = { kelas: '', teks: '' }
  try { await fn(); status.value = { kelas: 'baik', teks: ok }; emit('ubah') } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
const kirimFitur = async () => {
  const body = {}
  if (berubah.value) body.fitur = fitur.value.map((f) => ({ ...f, kriteria: f.kriteria.split('\n').map((x) => x.trim()).filter(Boolean), halaman: dariTeksHalaman(f.halaman || '') }))
  if (berubahTambahan.value) body.tambahan = tambahan.value
  if (Object.keys(body).length) await aksi(props.d.slug, 'simpan', body)
}
const simpan = () => lakukan(kirimFitur, 'Estimasi disimpan.')
const tambahBaris = () => tambahan.value.push({ judul: '', jam_agen: 0, jam_webmaster: 1 })
async function pecah() {
  if (props.d.fitur.length && !(await konfirmasi({ judul: 'Pecah ulang dari PRD?', kelas: 'waspada', tombol: 'Pecah ulang', teks: 'Daftar fitur sekarang diganti hasil baru dari Claude (versi lama disimpan sebagai cadangan .bak di server).' }))) return
  lakukan(() => aksi(props.d.slug, 'estimasi'), 'Claude mulai memecah PRD (2–5 menit).')
}
async function kunci() {
  if (!(await konfirmasi({ judul: 'Kunci estimasi?', tombol: 'Kunci', teks: `${fitur.value.length} fitur + ${tambahan.value.length} pekerjaan lain · ${jalurLaravel.value ? `agen ${jam(total.value.agen)} mesin · ` : ''}webmaster ${hariJam(total.value.wm)} · fitur selesai hari ke-${rencana.value.hariFitur}, serah terima hari kerja ke-${rencana.value.hariSelesai}. Sesudah dikunci, DESIGN.md, PRD, dan fitur tidak bisa diubah kecuali kunci dibuka lagi (sebelum install).` }))) return
  lakukan(async () => { await kirimFitur(); await aksi(props.d.slug, 'kunci') }, jalurLaravel.value ? 'Estimasi dikunci. Lanjut ke tab Install.' : 'Estimasi dikunci.')
}
const buka = () => lakukan(() => aksi(props.d.slug, 'kunci', { buka: true }), 'Kunci dibuka.')
</script>

<template>
  <section class="kartu" aria-labelledby="h-est">
    <div class="kartu-judul">
      <h2 id="h-est">Fitur & estimasi <span class="redup">(internal)</span></h2>
      <span v-if="memecah" class="pil waspada">sedang disusun</span>
      <div v-else class="ringkas">
        <VersiBrief :d="d" jenis="estimasi" />
        <span><b>{{ fitur.length }}</b> fitur</span>
        <span v-if="jalurLaravel" title="Jam kerja agen di mesin (07.00–22.00), bukan jam orang">agen <b>{{ jam(total.agen) }}</b> mesin</span>
        <span :title="`1 hari = ${JAM_SEHARI} jam kerja webmaster`">webmaster <b>{{ hariJam(total.wm) }}</b></span>
      </div>
    </div>
    <div v-if="fitur.length && !memecah" class="jadwal">
      <div class="utama"><span class="redup">Perkiraan serah terima</span><b>hari kerja ke-{{ rencana.hariSelesai }}</b><small class="redup">± pukul {{ rencana.selesaiJam }} · termasuk pekerjaan di luar fitur</small></div>
      <div v-if="jalurLaravel"><span class="redup">Semua fitur direview</span><b>hari ke-{{ rencana.hariFitur }}</b><small class="redup">agen selesai hari ke-{{ rencana.hariAgen }} ± {{ rencana.agenSelesai }} · jatah ±{{ jam(rencana.porsi) }}/hari</small></div>
      <div v-else><span class="redup">Semua fitur selesai</span><b>hari ke-{{ rencana.hariFitur }}</b><small class="redup">± pukul {{ rencana.fiturJam }} · dikerjakan webmaster</small></div>
      <div><span class="redup">Webmaster</span><b>{{ hariJam(total.wm) }}</b><small class="redup">{{ JAM_SEHARI }} jam/hari{{ jalurLaravel ? ', review paralel dengan agen' : ', tanpa agen otomatis' }}</small></div>
      <p v-if="jalurLaravel" class="redup">Mesin nyala 07.00–22.00, tapi kuota Claude dipakai bersama webmaster &amp; agen lain, jadi agen dijatah
        maksimal {{ jam(rencana.perProject) }} per project per hari<template v-if="rencana.lain">; karena ada {{ rencana.lain }} project lain di tahap Agen,
        {{ jam(rencana.efektif) }} kapasitas harian dibagi → ±{{ jam(rencana.porsi) }} untuk project ini</template>.
        Tiap fitur yang selesai langsung bisa direview webmaster; pekerjaan di luar fitur (bawah) dikerjakan sesudahnya.</p>
    </div>
    <p v-if="memecah" class="redup bantu">Claude sedang memecah PRD jadi fitur, kriteria terima, jam, dan pekerjaan di luar fitur.
      Daftar tampil lagi otomatis setelah selesai (2–5 menit); versi sebelumnya tersimpan sebagai cadangan di server.</p>
    <p v-else-if="dikunci" class="pesan-status baik">Dikunci oleh {{ d.estimasi_kunci.oleh }} · {{ tanggalWaktu(d.estimasi_kunci.waktu) }}</p>
    <p v-else-if="!jalurLaravel" class="redup bantu">Platform {{ d.saran.pilihan.jalur === 'wordpress' ? 'WordPress' : 'pilihan PM' }}: semua fitur dikerjakan webmaster, jadi jam agen 0 dan jam webmaster = waktu mengerjakan sampai jadi. Install otomatis &amp; agen Claude hanya untuk Laravel + Vue. Kriteria terima = checklist yang dicentang webmaster, satu baris per kriteria.</p>
    <p v-else class="redup bantu">Satu fitur = satu sesi agen. Kriteria terima = checklist yang nanti diuji agen dan dicentang webmaster — satu baris per kriteria, harus bisa diuji.</p>

    <div v-if="fitur.length && !memecah && kal && jalurLaravel" class="kal" :class="{ waspada: terlaluBesar }">
      <span>Data nyata agen: median <b>{{ kal.menit_median }} menit</b> per fitur, 90% ≤ {{ kal.menit_p90 }} menit ({{ kal.fitur }} fitur selesai, termasuk perbaikan &amp; revisi).
        Estimasi ini rata-rata <b>{{ Math.round(rataEstMenit) }} menit</b> per fitur<template v-if="terlaluBesar"> — ±{{ Math.round(rataEstMenit / kal.menit_median) }}× lebih lama dari kenyataan, jadwal serah terima ikut molor</template>.</span>
      <button v-if="terlaluBesar && !dikunci && kal.rasio" type="button" class="tombol waspada kecil" @click="sesuaikan">Sesuaikan jam agen dengan data nyata</button>
    </div>
    <div v-if="fitur.length && !memecah && cak?.kurang?.length" class="cakupan" role="alert">
      <b>{{ cak.kurang.length }} dari {{ cak.sel }} akses di Matriks peran × halaman (PRD) belum masuk fitur mana pun</b>
      <p class="redup">Celah seperti ini yang dulu berakhir jadi revisi "halaman … belum ada". Tambahkan ke kolom Halaman fitur yang cocok (atau buat fitur baru), lalu Simpan. Dihitung dari fitur yang sudah disimpan.</p>
      <ul><li v-for="x in cak.kurang" :key="x">{{ x }}</li></ul>
    </div>
    <p v-else-if="fitur.length && !memecah && cak" class="pesan-status baik kecil">Cakupan matriks: semua {{ cak.sel }} akses peran × halaman masuk fitur.</p>
    <p v-else-if="fitur.length && !memecah && !dikunci && d.prd.trim()" class="redup kecil">PRD belum punya bagian "Matriks peran × halaman", jadi cakupan halaman per peran tidak bisa dicek otomatis — susun ulang PRD di tab Brief untuk menambahkannya.</p>

    <div v-if="!memecah" class="aksi">
      <button v-if="!dikunci" type="button" class="tombol garis" :disabled="!d.prd.trim() || !!d.job || !namaSaya.trim()" @click="pecah">
        <Ikon nama="claude" :ukuran="18" /> {{ d.fitur.length ? 'Pecah ulang dari PRD' : 'Pecah PRD jadi fitur dengan Claude' }}
      </button>
      <span v-if="!d.prd.trim()" class="redup">PRD masih kosong — isi di tab Brief.</span>
    </div>
    <LogLive v-if="d.job?.jenis === 'estimasi'" :id="d.slug" jenis="estimasi" hidup tinggi="30vh" class="log-est" />

    <ol v-if="fitur.length && !memecah" class="fitur">
      <li v-for="(f, i) in fitur" :key="i" class="f">
        <div class="f-baris">
          <span class="fid">F{{ String(i + 1).padStart(2, '0') }}</span>
          <input v-model="f.judul" class="f-judul" :readonly="dikunci" maxlength="120" placeholder="Judul fitur" :aria-label="`Judul fitur ${i + 1}`">
          <label class="f-jam"><span>agen</span><input v-model.number="f.jam_agen" type="number" min="0" max="200" step="0.05" :readonly="dikunci"></label>
          <label class="f-jam"><span>webmaster</span><input v-model.number="f.jam_webmaster" type="number" min="0" max="200" step="0.5" :readonly="dikunci"></label>
          <button type="button" class="tombol garis kecil" :aria-expanded="terbuka.has(i)" @click="alih(i)">{{ terbuka.has(i) ? 'Tutup' : `Rincian · ${f.kriteria.split('\n').filter((x) => x.trim()).length} kriteria` }}</button>
        </div>
        <div v-if="terbuka.has(i)" class="f-rinci">
          <label class="isian"><span>Deskripsi untuk agen</span><textarea v-model="f.deskripsi" :readonly="dikunci" rows="4" /></label>
          <label class="isian"><span>Kriteria terima (satu per baris)</span><textarea v-model="f.kriteria" :readonly="dikunci" rows="6" /></label>
          <label class="isian"><span>Halaman &amp; peran (satu per baris: <code>Halaman: Peran, Peran</code> — nama persis dari Matriks peran × halaman PRD)</span><textarea v-model="f.halaman" :readonly="dikunci" rows="3" placeholder="Materi: Admin, Guru" /></label>
          <div v-if="!dikunci" class="aksi">
            <button type="button" class="tombol garis kecil" :disabled="i === 0" @click="geser(i, -1)">↑ Naik</button>
            <button type="button" class="tombol garis kecil" :disabled="i === fitur.length - 1" @click="geser(i, 1)">↓ Turun</button>
            <button type="button" class="tombol bahaya kecil" @click="hapus(i)">Hapus fitur</button>
          </div>
        </div>
      </li>
    </ol>
    <p v-else-if="!d.job" class="redup kosong">Belum ada fitur.</p>

    <div v-if="(fitur.length || tambahan.length) && !memecah" class="lain">
      <h3>Pekerjaan di luar fitur <span class="redup">sesudah semua fitur direview</span></h3>
      <p v-if="d.tambahan_bawaan && !dikunci" class="redup kecil">Isian bawaan (revisi klien ±25% jam fitur). Sesuaikan dengan project ini lalu Simpan.</p>
      <div class="tb-kepala" aria-hidden="true"><span>Pekerjaan</span><span>agen (jam)</span><span>webmaster (jam)</span><span /></div>
      <div v-for="(t, i) in tambahan" :key="i" class="tb-baris">
        <input v-model="t.judul" :readonly="dikunci" maxlength="160" placeholder="mis. Deploy produksi" :aria-label="`Pekerjaan ${i + 1}`">
        <label><span class="hp">agen</span><input v-model.number="t.jam_agen" type="number" min="0" max="200" step="0.5" :readonly="dikunci" :aria-label="`Jam agen pekerjaan ${i + 1}`"></label>
        <label><span class="hp">webmaster</span><input v-model.number="t.jam_webmaster" type="number" min="0" max="200" step="0.5" :readonly="dikunci" :aria-label="`Jam webmaster pekerjaan ${i + 1}`"></label>
        <button v-if="!dikunci" type="button" class="tombol bahaya kecil" :aria-label="`Hapus pekerjaan ${i + 1}`" @click="tambahan.splice(i, 1)">Hapus</button>
      </div>
      <button v-if="!dikunci" type="button" class="tombol garis kecil" @click="tambahBaris"><Ikon nama="tambah" :ukuran="14" /> Tambah pekerjaan</button>
    </div>

    <div v-if="!memecah" class="aksi bawah">
      <template v-if="!dikunci">
        <button type="button" class="tombol garis" @click="tambah"><Ikon nama="tambah" :ukuran="16" /> Tambah fitur</button>
        <button type="button" class="tombol garis" :disabled="!(berubah || berubahTambahan) || !namaSaya.trim()" @click="simpan">Simpan</button>
        <button type="button" class="tombol" :disabled="!fitur.length || !!d.job || !namaSaya.trim()" @click="kunci"><Ikon nama="kunci" :ukuran="16" /> Kunci estimasi</button>
      </template>
      <button v-else-if="!terinstall" type="button" class="tombol garis" :disabled="!namaSaya.trim()" @click="buka">Buka kunci</button>
      <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
    </div>
  </section>
</template>

<style scoped>
.jadwal { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 0 0 14px; }
.jadwal .utama { border: 1px solid var(--aksen-terang); }
.jadwal > div { display: grid; gap: 2px; padding: 10px 12px; border-radius: 12px; background: var(--kartu-2); }
.jadwal span { font-size: 12px; }
.jadwal b { font-size: 16px; }
.jadwal small { font-size: 12px; }
.jadwal p { grid-column: 1 / -1; margin: 0; font-size: 12.5px; }
@media (max-width: 700px) { .jadwal { grid-template-columns: minmax(0, 1fr); } }
.lain { margin-top: 18px; display: grid; gap: 8px; }
.lain h3 { font-size: 14px; }
.lain h3 .redup { font-weight: 500; font-size: 12px; margin-left: 6px; }
.kecil { font-size: 12.5px; margin: 0; }
.tb-kepala, .tb-baris { display: grid; grid-template-columns: minmax(0, 1fr) 100px 120px 72px; gap: 8px; align-items: center; }
.tb-kepala span { font-size: 11.5px; color: var(--teks-3); }
.tb-baris input { min-height: 36px; padding: 6px 10px; }
.tb-baris .hp { display: none; }
.lain > .tombol { width: fit-content; }
@media (max-width: 760px) {
  .tb-kepala { display: none; }
  .tb-baris { grid-template-columns: repeat(2, minmax(0, 1fr)); padding: 10px; border-radius: 12px; background: var(--kartu-2); }
  .tb-baris > input, .tb-baris > .tombol { grid-column: 1 / -1; }
  .tb-baris label { display: grid; gap: 2px; }
  .tb-baris .hp { display: block; font-size: 11px; color: var(--teks-3); }
}
.bantu { margin: -6px 0 12px; }
.kal { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 0 0 12px; padding: 10px 12px; border-radius: 12px; background: var(--kartu-2); font-size: 13px; color: var(--teks-2); }
.kal span { flex: 1 1 360px; }
.kal b { color: var(--teks); }
.kal.waspada { border: 1px solid rgba(232, 181, 74, .5); }
.cakupan { margin: 0 0 12px; padding: 10px 12px; border-radius: 12px; border: 1px solid rgba(255, 107, 107, .5); background: rgba(255, 107, 107, .06); font-size: 13px; }
.cakupan b { color: var(--bahaya); }
.cakupan p { margin: 4px 0 0; }
.cakupan ul { margin: 6px 0 0; padding-left: 18px; columns: 2 240px; color: var(--teks-2); }
.ringkas { display: flex; gap: 14px; flex-wrap: wrap; font-size: 13px; color: var(--teks-2); }
.ringkas b { color: var(--teks); }
.aksi { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.aksi p { margin: 0; }
.bawah { margin-top: 14px; }
.log-est { margin-top: 12px; }
.fitur { list-style: none; margin: 14px 0 0; padding: 0; display: grid; gap: 8px; }
.f { padding: 10px 12px; border-radius: 12px; background: var(--kartu-2); }
.f-baris { display: grid; grid-template-columns: auto minmax(0, 1fr) 96px 110px auto; gap: 8px; align-items: center; }
.fid { font: 700 12px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--aksen-terang); }
.f-jam { display: grid; gap: 2px; }
.f-jam span { font-size: 11px; color: var(--teks-3); }
.f-jam input, .f-judul { min-height: 36px; padding: 6px 10px; }
.f-rinci { display: grid; gap: 10px; margin-top: 10px; }
.kosong { margin: 12px 0 0; }
@media (max-width: 760px) {
  .f-baris { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .fid, .f-judul, .f-baris .tombol { grid-column: 1 / -1; }
}
</style>
