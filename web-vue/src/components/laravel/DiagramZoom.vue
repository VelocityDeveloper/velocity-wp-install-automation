<script setup>
// Penampil satu diagram SVG (Mermaid) dengan zoom & geser: tombol −/+/Pas/100%, Ctrl+gulir (atau pinch
// di touchpad) zoom ke titik kursor, seret untuk menggeser. Zoom = mengubah ukuran SVG (bukan transform),
// jadi gulir bawaan browser tetap berfungsi sebagai navigasi.
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({ svg: { type: String, required: true }, tinggi: { type: String, default: '70vh' }, dalamDialog: Boolean })
const emit = defineEmits(['layarPenuh'])
const wadah = ref(null)
const isi = ref(null)
const skala = ref(1)
let asli = { w: 0, h: 0 }
const MIN = 0.1, MAKS = 4

function elSvg() { return isi.value?.querySelector('svg') }
function terapkan() {
  const s = elSvg()
  if (!s || !asli.w) return
  s.style.maxWidth = 'none'
  s.style.width = `${asli.w * skala.value}px`
  s.style.height = `${asli.h * skala.value}px`
}
// Zoom dengan menjaga titik (x, y) di wadah tetap di bawah kursor
function zoomKe(baru, x, y) {
  const w = wadah.value
  baru = Math.min(MAKS, Math.max(MIN, baru))
  if (!w || baru === skala.value) return
  const px = x ?? w.clientWidth / 2, py = y ?? w.clientHeight / 2
  const rasio = baru / skala.value
  const kiri = (w.scrollLeft + px) * rasio - px, atas = (w.scrollTop + py) * rasio - py
  skala.value = baru
  terapkan()
  w.scrollLeft = kiri
  w.scrollTop = atas
}
const perbesar = () => zoomKe(skala.value * 1.25)
const perkecil = () => zoomKe(skala.value / 1.25)
function pas() {
  const w = wadah.value
  if (!w || !asli.w) return
  skala.value = Math.min(1, (w.clientWidth - 24) / asli.w)
  terapkan()
  w.scrollLeft = 0
  w.scrollTop = 0
}
function asal() { zoomKe(1) }

function gulir(e) {
  if (!e.ctrlKey && !e.metaKey) return   // gulir biasa = geser seperti biasa
  e.preventDefault()
  const r = wadah.value.getBoundingClientRect()
  zoomKe(skala.value * Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top)
}
// Seret untuk menggeser (mouse/pen; sentuh memakai gulir bawaan)
let seret = null
const menyeret = ref(false)
function mulaiSeret(e) {
  if (e.pointerType === 'touch' || e.button !== 0) return
  seret = { x: e.clientX, y: e.clientY, kiri: wadah.value.scrollLeft, atas: wadah.value.scrollTop }
  wadah.value.setPointerCapture(e.pointerId)
  menyeret.value = true
}
function geser(e) {
  if (!seret) return
  wadah.value.scrollLeft = seret.kiri - (e.clientX - seret.x)
  wadah.value.scrollTop = seret.atas - (e.clientY - seret.y)
}
function selesaiSeret() { seret = null; menyeret.value = false }
function tombol(e) {
  if (e.key === '+' || e.key === '=') { e.preventDefault(); perbesar() }
  else if (e.key === '-') { e.preventDefault(); perkecil() }
  else if (e.key === '0') { e.preventDefault(); pas() }
}

// Diagram dirender dulu di wadah tersembunyi lalu dipindah ke dokumen (DokDiagram.pasang), jadi ukuran
// awal baru bisa dihitung saat wadah sudah punya lebar: ditunggu lewat ResizeObserver.
let pengamat = null
function awal() {
  const s = elSvg()
  if (!s || !wadah.value?.clientWidth) return false
  const vb = s.viewBox?.baseVal
  asli = vb && vb.width ? { w: vb.width, h: vb.height } : { w: s.getBBox().width, h: s.getBBox().height }
  if (!asli.w) return false
  // Pas lebar bila diagram lebih lebar dari wadah, selain itu ukuran asli
  if (asli.w > wadah.value.clientWidth - 24) pas()
  else { skala.value = 1; terapkan() }
  return true
}
onMounted(async () => {
  await nextTick()
  wadah.value.addEventListener('wheel', gulir, { passive: false })
  if (awal()) return
  pengamat = new ResizeObserver(() => { if (awal()) { pengamat.disconnect(); pengamat = null } })
  pengamat.observe(wadah.value)
})
onBeforeUnmount(() => { wadah.value?.removeEventListener('wheel', gulir); pengamat?.disconnect() })
</script>

<template>
  <div class="penampil">
    <div class="alat" role="toolbar" aria-label="Zoom diagram">
      <button type="button" class="tombol garis kecil" aria-label="Perkecil" title="Perkecil (−)" @click="perkecil">−</button>
      <output class="persen" aria-live="polite">{{ Math.round(skala * 100) }}%</output>
      <button type="button" class="tombol garis kecil" aria-label="Perbesar" title="Perbesar (+)" @click="perbesar">+</button>
      <button type="button" class="tombol garis kecil" title="Pas selebar kotak (0)" @click="pas">Pas</button>
      <button type="button" class="tombol garis kecil" title="Ukuran asli" @click="asal">100%</button>
      <button v-if="!dalamDialog" type="button" class="tombol garis kecil" @click="emit('layarPenuh')">Layar penuh</button>
    </div>
    <div ref="wadah" class="wadah" :class="{ menyeret }" :style="{ maxHeight: tinggi }" tabindex="0"
      aria-label="Diagram. Ctrl + gulir untuk zoom, seret untuk menggeser, tombol + − 0."
      @pointerdown="mulaiSeret" @pointermove="geser" @pointerup="selesaiSeret" @pointercancel="selesaiSeret" @keydown="tombol">
      <div ref="isi" class="isi" v-html="svg" />
    </div>
    <p class="petunjuk redup">Ctrl + gulir untuk zoom · seret untuk menggeser</p>
  </div>
</template>

<style scoped>
.penampil { display: grid; gap: 8px; }
.alat { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.alat .tombol { min-width: 34px; }
.persen { min-width: 48px; text-align: center; font-size: 12.5px; font-variant-numeric: tabular-nums; color: var(--teks-2); }
/* Latar bertitik ala kanvas; background-attachment local supaya titik ikut bergeser bersama diagram */
.wadah {
  overflow: auto; cursor: grab; border-radius: 10px; overscroll-behavior: contain;
  border: 1px solid var(--garis);
  background-color: var(--kanvas);
  background-image: radial-gradient(var(--kanvas-titik) 1.2px, transparent 1.4px);
  background-size: 18px 18px; background-position: 9px 9px; background-attachment: local;
}
.wadah.menyeret { cursor: grabbing; user-select: none; }
.isi { width: max-content; min-width: 100%; padding: 12px; }
.isi :deep(svg) { display: block; margin: 0 auto; }
.petunjuk { margin: 0; font-size: 11.5px; text-align: right; }
@media (hover: none) { .petunjuk { display: none; } }
</style>
