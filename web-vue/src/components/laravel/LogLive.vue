<script setup>
// Log proses latar satu project (susun/estimasi/install/agen). Dipoll selama `hidup`, sekali saat tidak.
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { minta } from '../../api.js'

const props = defineProps({ id: { type: String, required: true }, jenis: { type: String, required: true }, hidup: Boolean, tinggi: { type: String, default: '52vh' } })
const baris = ref([])
const kotak = ref(null)
let timer = null
async function muat() {
  try {
    const k = kotak.value
    const bawah = !k || k.scrollHeight - k.scrollTop - k.clientHeight < 40
    baris.value = (await minta(`/api/laravel/p/${props.id}?log=${props.jenis}`)).log || []
    if (bawah) { await nextTick(); if (kotak.value) kotak.value.scrollTop = kotak.value.scrollHeight }
  } catch { /* coba lagi */ }
}
watch(() => [props.id, props.jenis, props.hidup], () => {
  clearInterval(timer)
  muat()
  if (props.hidup) timer = setInterval(muat, 2500)
}, { immediate: true })
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <pre ref="kotak" class="log" tabindex="0" :style="{ maxHeight: tinggi }">{{ baris.length ? baris.join('\n') : '(log kosong)' }}</pre>
</template>

<style scoped>
.log { margin: 0; padding: 14px; overflow: auto; border-radius: 12px; background: var(--latar); border: 1px solid var(--garis); color: var(--teks-2); font: 12px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: pre-wrap; word-break: break-word; }
</style>
