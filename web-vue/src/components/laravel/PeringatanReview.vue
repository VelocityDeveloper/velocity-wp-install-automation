<script setup>
// Peringatan di alur project: ada fitur yang sudah dikerjakan agen tapi belum direview webmaster.
// Audit 1 Okt: agen elearning selesai 23 fitur dalam 1,5 hari, sementara 15 fitur menunggu review > 2 hari.
// Fitur fondasi (gerbang) yang belum direview menahan agen (status menunggu_review) — merah.
import { computed } from 'vue'
import { waktuLalu } from '../../api.js'
import { reviewMendesak } from '../../laravel.js'

const props = defineProps({ r: { type: Object, required: true }, ringkas: { type: Boolean, default: false } })
defineEmits(['buka'])
const daftar = (ids) => (ids.length > 6 ? `${ids.slice(0, 6).join(', ')} +${ids.length - 6}` : ids.join(', '))
const berikut = computed(() => `F${String((props.r.gerbang_n || 0) + 1).padStart(2, '0')}`)
</script>

<template>
  <div class="kartu peringatan-review" :class="{ mendesak: reviewMendesak(r) }" role="alert">
    <div class="isi">
      <b>{{ r.menunggu }} fitur menunggu review webmaster</b>
      <span class="redup">terlama sejak {{ waktuLalu(r.tertua) }} · {{ daftar(r.ids) }}</span>
      <p v-if="r.tertahan">Agen <b>berhenti</b>: fitur fondasi {{ r.gerbang.join(', ') }} wajib direview dulu (OK atau Revisi). Agen lanjut otomatis sesudahnya.</p>
      <p v-else-if="r.gerbang.length">Fitur fondasi {{ r.gerbang.join(', ') }} belum direview — agen akan berhenti sebelum {{ berikut }} sampai semuanya direview.</p>
      <p v-else-if="!ringkas">Review lebih awal = revisi lebih murah: masukan masuk sebelum fitur lain dibangun di atasnya.</p>
    </div>
    <button type="button" class="tombol kecil" :class="reviewMendesak(r) ? 'bahaya' : 'waspada'" @click="$emit('buka')">Review sekarang</button>
  </div>
</template>

<style scoped>
.peringatan-review { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; padding: 12px 16px; border-color: rgba(232, 181, 74, .55); background: rgba(232, 181, 74, .08); }
.peringatan-review.mendesak { border-color: rgba(255, 107, 107, .55); background: rgba(255, 107, 107, .07); }
.isi { flex: 1 1 320px; display: grid; gap: 2px; font-size: 13.5px; }
.isi > b { color: var(--waspada); }
.mendesak .isi > b { color: var(--bahaya); }
.isi p { margin: 4px 0 0; color: var(--teks-2); }
.isi p b { color: var(--teks); }
.isi .redup { font-size: 12.5px; }
</style>
