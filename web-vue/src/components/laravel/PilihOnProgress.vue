<script setup>
// Pilih folder /home/On Progress/<nama> untuk relasi project (boleh kosong: diskusi awal biasanya belum ada folder).
import { ref, watch } from 'vue'
import { minta } from '../../api.js'

const model = defineModel({ type: String, default: '' })
const props = defineProps({ id: { type: String, default: 'pilih-op' }, kecuali: { type: String, default: '' } })
const q = ref('')
const hasil = ref([])
const buka = ref(false)
let tunda = null
watch(q, (v) => {
  clearTimeout(tunda)
  if (v.trim().length < 2) { hasil.value = []; return }
  tunda = setTimeout(async () => {
    try { hasil.value = (await minta(`/api/laravel/onprogress?q=${encodeURIComponent(v.trim())}`)).hasil || [] } catch { hasil.value = [] }
    buka.value = true
  }, 250)
})
function pilih(h) { model.value = h.nama; q.value = ''; hasil.value = []; buka.value = false }
</script>

<template>
  <div class="op">
    <div v-if="model" class="terpilih">
      <code>{{ model }}</code>
      <button type="button" class="tombol garis kecil" @click="model = ''">Lepas</button>
    </div>
    <template v-else>
      <input :id="props.id" v-model="q" type="search" autocomplete="off" spellcheck="false" placeholder="Cari folder On Progress (min. 2 huruf)…"
        role="combobox" :aria-expanded="buka && hasil.length > 0" :aria-controls="`${props.id}-daftar`" @keydown.esc="buka = false">
      <ul v-if="buka && q.trim().length >= 2" :id="`${props.id}-daftar`" class="daftar" role="listbox">
        <li v-if="!hasil.length" class="redup kosong">Tidak ada folder yang cocok.</li>
        <li v-for="h in hasil" :key="h.nama" role="option" :aria-selected="false">
          <button type="button" :disabled="!!h.dipakai && h.dipakai !== props.kecuali" @click="pilih(h)">
            {{ h.nama }} <small v-if="h.dipakai && h.dipakai !== props.kecuali">dipakai {{ h.dipakai }}</small>
          </button>
        </li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
.op { position: relative; }
.terpilih { display: flex; align-items: center; gap: 10px; min-height: 42px; flex-wrap: wrap; }
.terpilih code { font: 13px ui-monospace, SFMono-Regular, Consolas, monospace; padding: 6px 10px; border-radius: 8px; background: var(--kartu-2); overflow-wrap: anywhere; }
.daftar { position: absolute; z-index: 10; left: 0; right: 0; top: calc(100% + 4px); margin: 0; padding: 4px; list-style: none; max-height: 260px; overflow: auto; border-radius: 10px; background: var(--panel); border: 1px solid var(--garis); box-shadow: 0 12px 32px rgba(0, 0, 0, .4); }
.daftar button { width: 100%; text-align: left; border: 0; background: transparent; padding: 8px 10px; border-radius: 8px; cursor: pointer; overflow-wrap: anywhere; }
.daftar button:hover:not(:disabled) { background: var(--kartu-2); }
.daftar button:disabled { opacity: .5; cursor: default; }
.daftar small { color: var(--waspada); margin-left: 6px; }
.kosong { padding: 8px 10px; }
</style>
