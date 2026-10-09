<script setup>
// Contoh tampilan untuk klien (permintaan user 2026-09-30): Claude membuat mockup HTML dari catatan, dokumen klien, dan
// DESIGN/PRD bila sudah ada — platform WordPress: beranda saja; Laravel: landing + dashboard bergaya aplikasi Velocity
// (SIA VD, templates/laravel/gaya-dashboard-vd.md) → pratinjau di sini, lalu diterbitkan ke
// server preview nglorok.com (VPS Sumopod) supaya PM bisa mengirim tautannya ke klien.
// API: aksi `contoh` {arahan}, aksi `terbitkan_contoh`, GET /api/laravel/p/<id>/contoh/<berkas>.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import LogLive from './LogLive.vue'
import Ikon from '../Ikon.vue'
import { aksi, pesanGalat, namaSaya, tabUrl } from '../../laravel.js'
import { waktuLalu } from '../../api.js'
import VersiBrief from './VersiBrief.vue'
import { konfirmasi } from '../../konfirmasi.js'

const props = defineProps({
  d: { type: Object, required: true },
  catatanBerubah: { type: Boolean, default: false },
  simpanCatatan: { type: Function, required: true },
})
const emit = defineEmits(['ubah'])

const c = computed(() => props.d.contoh)
const wp = computed(() => props.d.contoh_platform === 'wordpress')
// Platform dipilih ulang sesudah contoh dibuat → contoh lama tidak sesuai lagi
const bedaPlatform = computed(() => c.value && c.value.platform !== props.d.contoh_platform)
const jalan = computed(() => props.d.job?.jenis === 'contoh')
const adaBahan = computed(() => !!props.d.catatan.trim() || props.catatanBerubah || !!props.d.dokumen?.length)
const bisa = computed(() => adaBahan.value && !props.d.job && !!namaSaya.value.trim())
const halaman = tabUrl('contoh', 'index.html', { boleh: ['index.html', 'dashboard.html'] })
const perangkat = tabUrl('perangkat', 'pc', { boleh: ['pc', 'hp'] })
const arahan = ref(props.d.contoh?.arahan || '')
const bukaArahan = ref(false)
const status = ref({ kelas: '', teks: '' })
const menerbitkan = ref(false)
const tersalin = ref(false)
const src = computed(() => `/api/laravel/p/${props.d.slug}/contoh/${halaman.value}?v=${c.value?.waktu || 0}`)
const terbit = computed(() => c.value?.terbit)
const urlKlien = computed(() => (terbit.value?.ok ? terbit.value.url : ''))
watch(() => c.value?.arahan, (v) => { if (!bukaArahan.value) arahan.value = v || '' })

// Tampilan PC dirender selebar 1280px lalu diperkecil mengikuti lebar kartu
const LEBAR_PC = 1280
const TINGGI_PC = 800
const bingkai = ref(null)
const skala = ref(1)
let ro = null
watch(bingkai, (el) => {
  ro?.disconnect()
  if (!el) return
  ro = new ResizeObserver(() => { skala.value = Math.min(1, el.clientWidth / LEBAR_PC) })
  ro.observe(el)
})
onBeforeUnmount(() => ro?.disconnect())

async function buat() {
  status.value = { kelas: '', teks: '' }
  if (c.value && !(await konfirmasi({ judul: 'Buat ulang contoh tampilan?', tombol: 'Buat ulang', kelas: 'waspada',
    teks: 'Claude membuat 2 halaman baru dari bahan terbaru (dan arahan Anda bila diisi). Tautan klien tetap sama dan ikut diperbarui; versi lama disimpan sebagai cadangan di server.' }))) return
  try {
    if (props.catatanBerubah) await props.simpanCatatan()
    await aksi(props.d.slug, 'contoh', { arahan: arahan.value })
    bukaArahan.value = false
    emit('ubah')
  } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
async function terbitkan() {
  status.value = { kelas: '', teks: '' }
  menerbitkan.value = true
  try {
    const r = await aksi(props.d.slug, 'terbitkan_contoh')
    status.value = r.ok ? { kelas: 'baik', teks: 'Terbit. Tautan siap dikirim ke klien.' } : { kelas: 'bahaya', teks: r.galat }
    emit('ubah')
  } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } } finally { menerbitkan.value = false }
}
async function salin() {
  try { await navigator.clipboard.writeText(urlKlien.value) } catch { return }
  tersalin.value = true
  setTimeout(() => { tersalin.value = false }, 1800)
}
</script>

<template>
  <section id="contoh-tampilan" class="kartu" aria-labelledby="h-contoh">
    <div class="kartu-judul">
      <h2 id="h-contoh">Contoh tampilan untuk klien</h2>
      <span v-if="jalan" class="pil waspada">sedang dibuat</span>
      <span v-else-if="urlKlien" class="pil baik">terbit</span>
    </div>
    <p v-if="wp" class="redup bantu">Platform <b>WordPress</b>: Claude membuat 1 halaman HTML, yaitu beranda situs, berisi data contoh dari catatan dan dokumen klien. Tautannya bisa dikirim ke klien sebagai gambaran hasil akhir.</p>
    <p v-else class="redup bantu">Platform <b>Laravel</b>: Claude membuat 2 halaman HTML, yaitu landing page dan dashboard bergaya aplikasi Velocity (seperti SIA VD), berisi data contoh dari catatan, dokumen klien, dan DESIGN.md/PRD bila sudah ada. Tautannya bisa dikirim ke klien sebagai gambaran hasil akhir.</p>
    <p v-if="bedaPlatform && !jalan" class="pesan-status waspada">Contoh ini dibuat untuk platform {{ c.platform === 'wordpress' ? 'WordPress' : 'Laravel' }}, padahal platform sekarang {{ wp ? 'WordPress' : 'Laravel' }}. Buat ulang agar sesuai.</p>

    <div v-if="jalan" class="panel" role="status">
      <p class="redup">Claude sedang mendesain {{ wp ? 'beranda situs' : 'landing page + dashboard' }} (3–10 menit), lalu menerbitkannya ke nglorok.com.</p>
      <LogLive :id="d.slug" jenis="contoh" hidup tinggi="24vh" />
    </div>

    <template v-else-if="c">
      <div class="tautan">
        <template v-if="urlKlien">
          <Ikon nama="tautan" :ukuran="18" class="ikon" />
          <a :href="urlKlien" target="_blank" rel="noopener" class="url">{{ urlKlien }}</a>
          <button type="button" class="tombol kecil" @click="salin"><Ikon nama="salin" :ukuran="16" /> {{ tersalin ? 'Tersalin' : 'Salin tautan' }}</button>
          <a class="tombol garis kecil" :href="urlKlien" target="_blank" rel="noopener"><Ikon nama="luar" :ukuran="16" /> Buka</a>
        </template>
        <span v-else-if="!c.bisa_terbit" class="redup">Server preview nglorok.com belum diatur; contoh baru bisa dilihat di sini.</span>
        <span v-else class="bahaya-teks">Belum terbit{{ terbit?.galat ? `: ${terbit.galat}` : '' }}</span>
        <button v-if="c.bisa_terbit" type="button" class="tombol garis kecil" :disabled="menerbitkan || !!d.job || !namaSaya.trim()" @click="terbitkan">
          {{ menerbitkan ? 'Menerbitkan…' : urlKlien ? 'Terbitkan ulang' : 'Terbitkan ke nglorok.com' }}
        </button>
      </div>

      <div class="alat">
        <div class="tab" role="tablist" aria-label="Halaman">
          <button v-for="h in c.halaman" :key="h.nama" type="button" role="tab" :aria-selected="halaman === h.nama" :class="{ aktif: halaman === h.nama }" @click="halaman = h.nama">{{ h.label }}</button>
        </div>
        <div class="tab" role="tablist" aria-label="Perangkat">
          <button type="button" role="tab" :aria-selected="perangkat === 'pc'" :class="{ aktif: perangkat === 'pc' }" @click="perangkat = 'pc'">PC</button>
          <button type="button" role="tab" :aria-selected="perangkat === 'hp'" :class="{ aktif: perangkat === 'hp' }" @click="perangkat = 'hp'">HP</button>
        </div>
        <span class="redup kecil">{{ c.nama_aplikasi }} · dibuat {{ waktuLalu(c.waktu) }}</span>
        <VersiBrief :d="d" jenis="contoh" />
      </div>

      <div v-if="perangkat === 'pc'" ref="bingkai" class="bingkai-pc" :style="{ height: `${TINGGI_PC * skala}px` }">
        <iframe :src="src" :title="`Pratinjau ${halaman}`" sandbox="allow-scripts" loading="lazy"
          :style="{ width: `${LEBAR_PC}px`, height: `${TINGGI_PC}px`, transform: `scale(${skala})` }" />
      </div>
      <div v-else class="bingkai-hp">
        <iframe :src="src" :title="`Pratinjau ${halaman} versi HP`" sandbox="allow-scripts" loading="lazy" />
      </div>

      <div v-if="c.catatan?.length" class="hasil-claude">
        <b>Catatan Claude untuk PM</b>
        <ul><li v-for="(x, i) in c.catatan" :key="i">{{ x }}</li></ul>
      </div>
    </template>

    <details v-if="!jalan" class="arahan" :open="bukaArahan" @toggle="bukaArahan = $event.target.open">
      <summary>Arahan untuk Claude <span class="redup">(opsional{{ c?.arahan ? ', terakhir dipakai' : '' }})</span></summary>
      <textarea v-model="arahan" rows="3" maxlength="2000" :placeholder="wp ? 'Contoh: nuansa hangat, tonjolkan paket layanan & testimoni, tombol WhatsApp besar…' : 'Contoh: tonjolkan KPI per proyek di dashboard, landing lebih banyak ilustrasi lapangan…'" />
    </details>
    <div v-if="!jalan" class="aksi">
      <button type="button" :class="c ? 'tombol garis' : 'tombol'" :disabled="!bisa" @click="buat">
        <Ikon nama="claude" :ukuran="18" /> {{ c ? 'Buat ulang contoh tampilan' : 'Buat contoh tampilan' }}
      </button>
      <span v-if="!adaBahan" class="redup kecil">Isi catatan atau unggah dokumen klien dulu.</span>
    </div>
    <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
  </section>
</template>

<style scoped>
.bantu { margin: -6px 0 12px; }
.kecil { font-size: 12px; }
.panel { display: grid; gap: 12px; padding: 14px; border-radius: 12px; background: var(--kartu-2); }
.panel > p { margin: 0; }
.tautan { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 10px 12px; border-radius: 12px; background: var(--kartu-2); margin-bottom: 12px; }
.tautan .ikon { flex: none; color: var(--aksen); }
.url { flex: 1 1 220px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; font-size: 13.5px; }
.tautan .tombol { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; }
.bahaya-teks { color: var(--bahaya); font-size: 13px; flex: 1 1 220px; }
.alat { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 5px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.bingkai-pc { position: relative; overflow: hidden; border-radius: 10px; border: 1px solid var(--garis); background: #fff; }
.bingkai-pc iframe { position: absolute; top: 0; left: 0; border: 0; transform-origin: 0 0; }
.bingkai-hp { display: flex; justify-content: center; padding: 14px 0; border-radius: 12px; background: var(--kartu-2); }
.bingkai-hp iframe { width: 390px; max-width: 100%; height: 720px; border: 8px solid #111; border-radius: 28px; background: #fff; }
.hasil-claude { margin-top: 14px; padding: 12px 14px; border-radius: 12px; background: var(--kartu-2); }
.hasil-claude ul { margin: 8px 0 0; padding-left: 18px; display: grid; gap: 4px; color: var(--teks-2); }
.arahan { margin-top: 14px; }
.arahan summary { cursor: pointer; font-size: 13.5px; }
.arahan textarea { margin-top: 8px; width: 100%; font: inherit; font-size: 13.5px; }
.aksi { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.aksi .tombol { display: inline-flex; align-items: center; gap: 8px; }
.pesan-status { margin: 10px 0 0; }
.pesan-status.waspada { color: var(--waspada); margin: 0 0 12px; }
</style>
