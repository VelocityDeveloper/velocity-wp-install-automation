<script setup>
// Server dev Laravel di Local PC: nyala / mati / perlu restart, aktivitas terakhir, dan jadwal mati otomatis
// (diam 24 jam → server-dev-tidur.timer mematikannya supaya RAM PC tidak habis). API: scripts/server_dev.py.
import { computed, ref } from 'vue'
import { kirim, ukuranBerkas, waktuLalu } from '../../api.js'
import { konfirmasi } from '../../konfirmasi.js'
import { namaSaya, pesanGalat, KONDISI_SERVER as KONDISI } from '../../laravel.js'

const props = defineProps({ data: Object, galat: Object })
const emit = defineEmits(['ubah'])

const URUTAN = { perlu_restart: 0, nyala: 1, mati: 2, tidak_ada: 3 }
const server = computed(() => [...(props.data?.server || [])].sort((a, b) => URUTAN[a.kondisi] - URUTAN[b.kondisi]))
// Bawaan hanya yang butuh tindakan supaya daftar project tidak terdorong jauh; pilihan diingat per browser.
const semua = ref(false)
try { semua.value = localStorage.getItem('server-dev-semua') === '1' } catch { /* penyimpanan diblokir */ }
const ubahSemua = () => {
  semua.value = !semua.value
  try { localStorage.setItem('server-dev-semua', semua.value ? '1' : '0') } catch { /* abaikan */ }
}
const perluTindakan = (s) => s.kondisi === 'perlu_restart' || s.kondisi === 'tidak_ada'
const tampil = computed(() => (semua.value ? server.value : server.value.filter(perluTindakan)))
const hitung = (k) => server.value.filter((s) => s.kondisi === k).length
const totalMemori = computed(() => server.value.reduce((n, s) => n + (s.memori || 0), 0))

const nanti = (t) => {
  const d = t - Math.floor(Date.now() / 1000)
  if (d <= 0) return 'pengecekan berikutnya'
  if (d < 3600) return `${Math.max(1, Math.floor(d / 60))} menit lagi`
  return `${Math.floor(d / 3600)} jam lagi`
}
const alamat = (s) => `http://${location.hostname}:${s.port}/`

const sibuk = ref('')
const pesan = ref({ kelas: '', teks: '' })
const LABEL = { nyala: 'Nyalakan', mati: 'Matikan', restart: 'Restart' }
async function jalankan(s, aksi) {
  if (aksi === 'mati' && !(await konfirmasi({
    judul: `Matikan ${s.nama}?`,
    teks: `Semua layanan (${s.layanan.map((l) => l.nama).join(', ')}) dihentikan. Bisa dinyalakan lagi kapan saja dari sini.`,
    tombol: 'Matikan', kelas: 'bahaya',
  }))) return
  sibuk.value = `${s.id}:${aksi}`
  pesan.value = { kelas: '', teks: '' }
  try {
    await kirim(`/api/laravel/server/${s.id}/${aksi}`, { oleh: namaSaya.value.trim() })
    pesan.value = { kelas: 'baik', teks: `${s.nama}: ${LABEL[aksi].toLowerCase()} berhasil.` }
    emit('ubah')
  } catch (e) {
    pesan.value = { kelas: 'bahaya', teks: `${s.nama}: ${pesanGalat(e)}` }
  } finally {
    sibuk.value = ''
  }
}
</script>

<template>
  <section class="kartu" aria-labelledby="judul-server">
    <div class="kartu-judul">
      <h2 id="judul-server">Server dev</h2>
      <p v-if="server.length" class="redup ringkas">
        {{ hitung('nyala') }} nyala<template v-if="hitung('perlu_restart')"> · <b class="waspada">{{ hitung('perlu_restart') }} perlu restart</b></template>
        · {{ hitung('mati') }} mati · RAM {{ ukuranBerkas(totalMemori) }}
      </p>
    </div>
    <p class="redup ket">Server yang tidak dibuka dan kodenya tidak diubah selama 24 jam dimatikan otomatis supaya RAM PC tidak habis. Nyalakan lagi di sini kapan saja.</p>
    <p v-if="galat && !data" class="pesan-status bahaya">Gagal memuat status server: {{ galat.message }}</p>
    <p v-else-if="!data" class="redup">Memuat…</p>
    <ul v-else-if="tampil.length" class="daftar-server">
      <li v-for="s in tampil" :key="s.id" :class="KONDISI[s.kondisi]?.kelas">
        <div class="kiri">
          <div class="baris-nama">
            <span class="pil" :class="KONDISI[s.kondisi]?.kelas">{{ KONDISI[s.kondisi]?.label }}</span>
            <b>{{ s.nama }}</b>
            <a v-if="s.port && s.kondisi !== 'mati'" :href="alamat(s)" target="_blank" rel="noopener" class="port">:{{ s.port }}</a>
            <code v-else-if="s.port" class="port">:{{ s.port }}</code>
          </div>
          <p v-if="s.alasan.length" class="alasan">{{ s.alasan.join(' · ') }}</p>
          <p class="redup meta">
            <template v-if="s.kondisi !== 'mati'">{{ ukuranBerkas(s.memori) }} · </template>
            aktivitas {{ s.aktivitas ? waktuLalu(s.aktivitas) : 'belum tercatat' }}
            <template v-if="s.selalu_nyala"> · selalu nyala (tidak dimatikan otomatis)</template>
            <template v-else-if="s.mati_otomatis"> · mati otomatis {{ nanti(s.mati_otomatis) }}</template>
            <template v-else-if="s.kondisi === 'mati' && s.dimatikan"> · dimatikan {{ s.dimatikan.oleh }} {{ waktuLalu(s.dimatikan.waktu) }}</template>
          </p>
        </div>
        <div class="tombol-baris">
          <button v-if="s.kondisi === 'mati'" type="button" class="tombol kecil" :disabled="!!sibuk" @click="jalankan(s, 'nyala')">
            {{ sibuk === `${s.id}:nyala` ? 'Menyalakan…' : 'Nyalakan' }}
          </button>
          <template v-else-if="s.kondisi !== 'tidak_ada'">
            <button type="button" class="tombol kecil" :class="s.kondisi === 'perlu_restart' ? 'waspada' : 'garis'" :disabled="!!sibuk" @click="jalankan(s, 'restart')">
              {{ sibuk === `${s.id}:restart` ? 'Restart…' : 'Restart' }}
            </button>
            <button v-if="!s.selalu_nyala" type="button" class="tombol kecil garis" :disabled="!!sibuk" @click="jalankan(s, 'mati')">
              {{ sibuk === `${s.id}:mati` ? 'Mematikan…' : 'Matikan' }}
            </button>
          </template>
        </div>
      </li>
    </ul>
    <p v-else class="redup">Semua server dalam keadaan baik.</p>
    <button v-if="data && server.length" type="button" class="tombol garis kecil lihat" :aria-expanded="semua" @click="ubahSemua">
      {{ semua ? 'Tampilkan yang perlu tindakan saja' : `Lihat semua ${server.length} server` }}
    </button>
    <p v-if="pesan.teks" class="pesan-status" :class="pesan.kelas" role="status">{{ pesan.teks }}</p>
  </section>
</template>

<style scoped>
.ringkas { margin: 0; font-size: 13px; }
.ringkas .waspada { color: var(--waspada); }
.ket { margin: -6px 0 12px; font-size: 13px; }
.daftar-server { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.daftar-server li { display: flex; justify-content: space-between; align-items: center; gap: 10px 14px; flex-wrap: wrap;
  padding: 10px 14px; border-radius: 10px; background: var(--kartu-2); border: 1px solid transparent; }
.daftar-server li.waspada { border-color: rgba(232, 181, 74, .4); }
.daftar-server li.mati { opacity: .75; }
.daftar-server li.mati:hover { opacity: 1; }
.kiri { display: grid; gap: 3px; min-width: 0; }
.baris-nama { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 14px; }
.pil.mati { color: var(--teks-3); background: var(--kartu); }
.port { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; }
.alasan { margin: 0; font-size: 12.5px; color: var(--waspada); }
.meta { margin: 0; font-size: 12.5px; }
.tombol-baris { display: flex; gap: 6px; flex-wrap: wrap; }
.pesan-status { margin: 10px 0 0; }
.lihat { margin-top: 10px; }
</style>
