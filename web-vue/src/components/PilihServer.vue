<script setup>
// Pilihan server di sub menu Server (pengganti deret tab). v-model = nama server;
// titik = kelas status server terpilih, teks = isi opsi (nama + status singkat).
defineProps({
  servers: { type: Array, default: () => [] },
  modelValue: { type: String, default: '' },
  titik: { type: String, default: '' },
  teks: { type: Function, default: (s) => s.name },
})
defineEmits(['update:modelValue'])
</script>

<template>
  <label class="pilih-server">
    <span class="label">Server</span>
    <span v-if="titik" class="titik" :class="titik" aria-hidden="true" />
    <select :value="modelValue" @change="$emit('update:modelValue', $event.target.value)">
      <option v-for="s in servers" :key="s.host" :value="s.name">{{ teks(s) }}</option>
    </select>
  </label>
</template>

<style scoped>
.pilih-server { display: inline-flex; align-items: center; gap: 10px; max-width: 100%; justify-self: start; align-self: flex-start; }
.label { font-size: 13px; font-weight: 600; color: var(--teks-2); }
select { width: auto; min-width: 240px; max-width: 100%; font-weight: 600; }
.titik { display: inline-block; flex: none; width: 10px; height: 10px; border-radius: 50%; background: var(--teks-3); }
.titik.baik, .titik.hijau { background: var(--baik); }
.titik.waspada, .titik.kuning { background: var(--waspada); }
.titik.bahaya, .titik.merah { background: var(--bahaya); }
.titik.biru { background: var(--aksen-terang); }
.titik.ungu { background: var(--ungu); }
.titik.teal { background: var(--teal); }
</style>
