<script setup>
// "Nama Anda" = orang dari CRM new.velocitydeveloper (PM / webmaster / revisi, aktif) — daftar dari /api/laravel (tim).
// Pilihan "Lainnya…" untuk nama di luar daftar (mis. CRM belum diperbarui). Nilai disimpan di browser (namaSaya).
import { ref, computed, watch } from 'vue'
import { namaSaya } from '../../laravel.js'

const props = defineProps({ tim: { type: Object, default: () => ({}) }, id: { type: String, default: 'nama-saya' } })
const GRUP = [['pm', 'Project Manager'], ['webmaster', 'Webmaster'], ['revisi', 'Revisi']]
const semua = computed(() => GRUP.flatMap(([k]) => props.tim?.[k] || []))
const LAIN = '__lain__'
const manual = ref(false)
const pilihan = computed({
  get: () => (manual.value || (namaSaya.value && !semua.value.includes(namaSaya.value)) ? LAIN : namaSaya.value),
  set: (v) => {
    if (v === LAIN) { manual.value = true; if (semua.value.includes(namaSaya.value)) namaSaya.value = '' }
    else { manual.value = false; namaSaya.value = v }
  },
})
watch(semua, () => { if (namaSaya.value && !semua.value.includes(namaSaya.value)) manual.value = true }, { immediate: true })
</script>

<template>
  <div class="pilih-nama">
    <select :id="id" v-model="pilihan" aria-label="Nama Anda">
      <option value="" disabled>Pilih nama Anda…</option>
      <optgroup v-for="[k, label] in GRUP.filter(([k]) => tim?.[k]?.length)" :key="k" :label="label">
        <option v-for="n in tim[k]" :key="n" :value="n">{{ n }}</option>
      </optgroup>
      <option :value="LAIN">Lainnya…</option>
    </select>
    <input v-if="pilihan === LAIN" v-model.lazy="namaSaya" maxlength="40" placeholder="Tulis nama" autocomplete="name" aria-label="Nama lain">
  </div>
</template>

<style scoped>
.pilih-nama { display: grid; gap: 6px; }
</style>
