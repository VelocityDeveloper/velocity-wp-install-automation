<script setup>
// Penanda versi brief pada keluaran yang dibuat dari brief (saran, rangkuman, contoh, estimasi).
// Label selalu menyebut statusnya (7 Okt): "v3" hijau di samping "brief v5" dulu terbaca usang padahal bahannya belum berubah.
// Data dari API detail `brief.keluaran[jenis]` = { dari, usang: [nama bagian yang berubah sesudahnya] }.
import { computed } from 'vue'

const props = defineProps({ d: { type: Object, required: true }, jenis: { type: String, required: true } })
const k = computed(() => props.d.brief?.keluaran?.[props.jenis])
const judul = computed(() => k.value?.usang.length
  ? `Dibuat dari brief v${k.value.dari}. Sesudah itu berubah: ${k.value.usang.join(', ')}. Susun ulang agar ikut.`
  : `Dibuat dari brief v${k.value?.dari}, bahan yang dibaca belum berubah sejak itu.`)
</script>

<template>
  <span v-if="k" class="pil" :class="k.usang.length ? 'waspada' : 'baik'" :title="judul">
    dari brief v{{ k.dari }} · <template v-if="k.usang.length">usang ({{ k.usang.join(', ') }} berubah)</template><template v-else>masih sesuai</template>
  </span>
</template>
