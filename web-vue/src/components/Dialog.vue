<script setup>
// Dialog modal yang aksesibel: fokus masuk ke dialog, Tab berputar di dalamnya, Esc & klik latar menutup,
// fokus kembali ke pemicu saat ditutup.
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'

const props = defineProps({ buka: Boolean, judul: String, kelas: { type: String, default: '' }, lebar: { type: String, default: '480px' } })
const emit = defineEmits(['tutup'])
const kotak = ref(null)
let pemicu = null

const fokusan = () => [...kotak.value.querySelectorAll('button:not([disabled]), [href], input:not([disabled]):not([readonly]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
function tombol(e) {
  if (e.key === 'Escape') { e.stopPropagation(); emit('tutup'); return }
  if (e.key !== 'Tab') return
  const f = fokusan(); if (!f.length) return
  if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus() }
  else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus() }
}
watch(() => props.buka, async (b) => {
  if (b) {
    pemicu = document.activeElement
    await nextTick()
    const f = fokusan()
    ;(kotak.value.querySelector('[autofocus]') || f[0])?.focus()
  } else if (pemicu && document.body.contains(pemicu)) pemicu.focus()
})
onBeforeUnmount(() => { if (props.buka && pemicu) pemicu.focus() })
</script>

<template>
  <Teleport to="body">
    <div v-if="buka" class="latar-dialog" @click.self="emit('tutup')" @keydown="tombol">
      <div ref="kotak" class="dialog" :class="kelas" :style="{ width: `min(${lebar}, 100%)` }" role="dialog" aria-modal="true" :aria-label="judul">
        <div class="dialog-kepala">
          <h2>{{ judul }}</h2>
          <button type="button" class="dialog-x" aria-label="Tutup" @click="emit('tutup')">
            <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5 5 15" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
          </button>
        </div>
        <slot />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.latar-dialog { position: fixed; inset: 0; z-index: 60; display: grid; place-items: center; padding: 16px; background: rgba(4, 6, 16, .72); overflow-y: auto; }
.dialog { max-height: calc(100vh - 32px); overflow-y: auto; padding: 20px 22px 22px; border-radius: var(--radius); background: var(--kartu); border: 1px solid var(--garis); box-shadow: 0 24px 60px rgba(0, 0, 0, .5); }
.dialog.bahaya { border-color: rgba(255, 107, 107, .5); }
.dialog.waspada { border-color: rgba(232, 181, 74, .5); }
.dialog-kepala { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.dialog-kepala h2 { font-size: 17px; }
.dialog.bahaya h2 { color: var(--bahaya); }
.dialog.waspada h2 { color: var(--waspada); }
.dialog-x { display: grid; place-items: center; width: 36px; height: 36px; border: 0; border-radius: 9px; background: transparent; color: var(--teks-2); cursor: pointer; flex: none; }
.dialog-x:hover { background: var(--kartu-2); color: #fff; }
</style>
