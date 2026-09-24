<script setup>
import Dialog from './Dialog.vue'
import { keadaanKonfirmasi as k } from '../konfirmasi.js'
const jawab = (ya) => { k.buka = false; k.selesai?.(ya); k.selesai = null }
</script>

<template>
  <Dialog :buka="k.buka" :judul="k.judul" :kelas="k.kelas" @tutup="jawab(false)">
    <p class="teks">{{ k.teks }}</p>
    <div class="aksi-dialog">
      <button type="button" class="tombol garis" autofocus @click="jawab(false)">Batal</button>
      <button type="button" class="tombol" :class="k.kelas" @click="jawab(true)">{{ k.tombol }}</button>
    </div>
  </Dialog>
</template>

<style scoped>
.teks { margin: 0; color: var(--teks-2); white-space: pre-line; }
</style>
