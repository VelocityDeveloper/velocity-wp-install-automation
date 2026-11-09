<script setup>
// Ikon ⓘ dengan tooltip (kursor / fokus keyboard / ketuk di HP). Isi lewat slot.
// rata="kanan" untuk ikon di dekat tepi kanan supaya tooltip tidak keluar layar.
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

const props = defineProps({ label: { type: String, default: 'Info' }, rata: { type: String, default: 'kiri' } })
const id = useId()
const buka = ref(false)
const akar = ref(null)
const isi = ref(null)
const geser = ref(0)

// Hanya kursor sungguhan yang membuka lewat hover: ketukan juga memicu "enter", lalu klik akan menutupnya lagi
const hover = (e, nilai) => { if (e.pointerType === 'mouse') buka.value = nilai }
// Fokus ikut membuka di antara pointerdown dan click, jadi ketukan dinilai dari status sebelum ditekan
let saatTekan = null
function alih() {
  buka.value = !(saatTekan ?? buka.value)
  saatTekan = null
}
// Safari iOS tidak memfokuskan tombol saat diketuk, jadi blur tidak bisa diandalkan untuk menutup
const tekanLuar = (e) => { if (!akar.value?.contains(e.target)) buka.value = false }
watch(buka, async (terbuka) => {
  document[terbuka ? 'addEventListener' : 'removeEventListener']('pointerdown', tekanLuar)
  geser.value = 0
  if (!terbuka) return
  // Di HP ikon bisa jauh dari tepi kiri, dan tabel yang bisa digeser memotong isinya: geser tooltip supaya tetap tampak
  await nextTick()
  const r = isi.value?.getBoundingClientRect()
  if (!r) return
  let kiri = 8, kanan = document.documentElement.clientWidth - 8
  for (let e = akar.value.parentElement; e; e = e.parentElement) {
    if (getComputedStyle(e).overflowX === 'visible') continue
    const k = e.getBoundingClientRect()
    kiri = Math.max(kiri, k.left + 4)
    kanan = Math.min(kanan, k.right - 4)
  }
  if (r.right > kanan) geser.value = kanan - r.right
  if (r.left + geser.value < kiri) geser.value = kiri - r.left
})
// Memakai left/right, bukan transform: transform tetap melebarkan halaman di HP
const posisi = computed(() => geser.value ? (props.rata === 'kanan' ? { right: `${-6 - geser.value}px` } : { left: `${-6 + geser.value}px` }) : null)
onBeforeUnmount(() => document.removeEventListener('pointerdown', tekanLuar))
</script>

<template>
  <span ref="akar" class="info" @pointerenter="hover($event, true)" @pointerleave="hover($event, false)">
    <button type="button" class="info-tombol" :aria-label="label" :aria-describedby="buka ? id : undefined" :aria-expanded="buka"
            @pointerdown="saatTekan = buka" @focus="buka = true" @blur="buka = false; saatTekan = null" @click="alih" @keydown.esc="buka = false">
      <svg width="15" height="15" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="1.6" /><path d="M10 9v5M10 6.2v.1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
    </button>
    <span v-show="buka" :id="id" ref="isi" role="tooltip" class="info-isi" :class="rata" :style="posisi"><slot /></span>
  </span>
</template>

<style scoped>
.info { position: relative; display: inline-flex; vertical-align: middle; }
.info-tombol { display: grid; place-items: center; width: 22px; height: 22px; padding: 0; border: 0; border-radius: 6px; background: transparent; color: var(--teks-3); cursor: help; }
.info-tombol:hover, .info-tombol[aria-expanded="true"] { color: var(--aksen-terang); }
.info-tombol:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
/* Area ketuk minimal 44 px di layar sentuh tanpa mengubah tata letak */
@media (pointer: coarse) { .info-tombol { position: relative; } .info-tombol::after { content: ''; position: absolute; inset: -11px; } }
.info-isi { position: absolute; top: calc(100% + 6px); z-index: 20; width: max-content; max-width: min(300px, calc(100vw - 32px));
  padding: 9px 12px; border-radius: 10px; background: var(--tooltip); border: 1px solid var(--garis); box-shadow: 0 10px 30px rgba(0, 0, 0, .25);
  color: var(--teks-2); font-size: 12.5px; font-weight: 500; line-height: 1.5; text-align: left; white-space: normal; }
.info-isi.kiri { left: -6px; }
.info-isi.kanan { right: -6px; }
.info-isi :deep(p) { margin: 0; }
.info-isi :deep(p + p), .info-isi :deep(p + ul), .info-isi :deep(ul + p) { margin-top: 6px; }
.info-isi :deep(ul) { margin: 0; padding-left: 16px; }
</style>
