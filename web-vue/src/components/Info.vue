<script setup>
// Ikon ⓘ dengan tooltip (kursor / fokus keyboard / ketuk di HP). Isi lewat slot.
// rata="kanan" untuk ikon di dekat tepi kanan supaya tooltip tidak keluar layar.
import { ref, useId } from 'vue'

defineProps({ label: { type: String, default: 'Info' }, rata: { type: String, default: 'kiri' } })
const id = useId()
const buka = ref(false)
</script>

<template>
  <span class="info" @mouseenter="buka = true" @mouseleave="buka = false">
    <button type="button" class="info-tombol" :aria-label="label" :aria-describedby="buka ? id : undefined" :aria-expanded="buka"
            @focus="buka = true" @blur="buka = false" @click="buka = !buka" @keydown.esc="buka = false">
      <svg width="15" height="15" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="1.6" /><path d="M10 9v5M10 6.2v.1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
    </button>
    <span v-show="buka" :id="id" role="tooltip" class="info-isi" :class="rata"><slot /></span>
  </span>
</template>

<style scoped>
.info { position: relative; display: inline-flex; vertical-align: middle; }
.info-tombol { display: grid; place-items: center; width: 22px; height: 22px; padding: 0; border: 0; border-radius: 6px; background: transparent; color: var(--teks-3); cursor: help; }
.info-tombol:hover, .info-tombol[aria-expanded="true"] { color: var(--aksen-terang); }
.info-tombol:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
.info-isi { position: absolute; top: calc(100% + 6px); z-index: 20; width: max-content; max-width: min(300px, calc(100vw - 32px));
  padding: 9px 12px; border-radius: 10px; background: var(--tooltip); border: 1px solid var(--garis); box-shadow: 0 10px 30px rgba(0, 0, 0, .25);
  color: var(--teks-2); font-size: 12.5px; font-weight: 500; line-height: 1.5; text-align: left; white-space: normal; }
.info-isi.kiri { left: -6px; }
.info-isi.kanan { right: -6px; }
.info-isi :deep(p) { margin: 0; }
.info-isi :deep(p + p), .info-isi :deep(p + ul), .info-isi :deep(ul + p) { margin-top: 6px; }
.info-isi :deep(ul) { margin: 0; padding-left: 16px; }
</style>
