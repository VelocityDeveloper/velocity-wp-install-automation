<script setup>
// Menu aksi per baris: posisinya fixed dari tombol pemicu (dibalik ke atas kalau tidak muat),
// tombol panah berpindah item, Esc/klik luar/gulir halaman menutup.
import { ref, nextTick, onBeforeUnmount } from 'vue'

const buka = ref(false)
const aksi = ref([])
const posisi = ref({ top: 0, left: 0 })
const menu = ref(null)
let pemicu = null

async function tampilkan(el, daftar) {
  pemicu = el
  aksi.value = daftar
  buka.value = true
  await nextTick()
  const r = el.getBoundingClientRect(), m = menu.value
  let top = r.bottom + 6
  if (top + m.offsetHeight > window.innerHeight) top = Math.max(6, r.top - m.offsetHeight - 6)
  posisi.value = { top, left: Math.max(6, Math.min(r.right - m.offsetWidth, window.innerWidth - m.offsetWidth - 8)) }
  m.querySelector('button:not([disabled])')?.focus()
  document.addEventListener('pointerdown', luar, true)
  window.addEventListener('scroll', tutup, true)
  window.addEventListener('resize', tutup)
}
function tutup(kembali) {
  if (!buka.value) return
  buka.value = false
  document.removeEventListener('pointerdown', luar, true)
  window.removeEventListener('scroll', tutup, true)
  window.removeEventListener('resize', tutup)
  if (kembali === true && pemicu) pemicu.focus()
}
function luar(e) { if (!menu.value?.contains(e.target) && e.target !== pemicu && !pemicu?.contains(e.target)) tutup() }
function tombol(e) {
  const b = [...menu.value.querySelectorAll('button:not([disabled])')]
  const i = b.indexOf(document.activeElement)
  if (e.key === 'Escape' || e.key === 'Tab') { e.preventDefault(); tutup(true) }
  else if (e.key === 'ArrowDown') { e.preventDefault(); b[(i + 1) % b.length]?.focus() }
  else if (e.key === 'ArrowUp') { e.preventDefault(); b[(i - 1 + b.length) % b.length]?.focus() }
}
function pilih(a) { tutup(); a.run() }
onBeforeUnmount(() => tutup())
defineExpose({ tampilkan, tutup, buka })
</script>

<template>
  <Teleport to="body">
    <div v-if="buka" ref="menu" class="menu-aksi" role="menu" :style="{ top: `${posisi.top}px`, left: `${posisi.left}px` }" @keydown="tombol">
      <button v-for="a in aksi" :key="a.label" type="button" role="menuitem" :class="{ bahaya: a.danger }" :disabled="a.disabled" :title="a.title || null" @click="pilih(a)">
        {{ a.label }}<small v-if="a.disabled && a.title">{{ a.title }}</small>
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.menu-aksi { position: fixed; z-index: 55; min-width: 200px; padding: 6px; border-radius: 12px; background: var(--kartu-2); border: 1px solid var(--garis); box-shadow: 0 16px 40px rgba(0, 0, 0, .45); }
.menu-aksi button { display: block; width: 100%; padding: 9px 12px; border: 0; border-radius: 8px; background: transparent; text-align: left; font-size: 13.5px; cursor: pointer; }
.menu-aksi button:hover:not(:disabled), .menu-aksi button:focus-visible { background: var(--aksen-lembut); color: #fff; outline: none; }
.menu-aksi button.bahaya { color: var(--bahaya); }
.menu-aksi button:disabled { color: var(--teks-3); cursor: default; }
.menu-aksi small { display: block; font-size: 11.5px; }
</style>
