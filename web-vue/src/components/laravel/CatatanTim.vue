<script setup>
// Dialog catatan tim per project di daftar /installer/laravel (5 Nov 2026). Disimpan di proyek.json `catatan_tim`,
// terpisah dari catatan brief, jadi tidak dibaca agen Claude. Kosongkan lalu Simpan = hapus catatan.
import { reactive, watch } from 'vue'
import Dialog from '../Dialog.vue'
import { namaSaya, aksi, pesanGalat } from '../../laravel.js'

const props = defineProps({ p: Object })
const emit = defineEmits(['tutup', 'ubah'])
const st = reactive({ teks: '', galat: '', mengirim: false })
watch(() => props.p, (p) => {
  if (p) Object.assign(st, { teks: p.catatan_tim?.teks || '', galat: '', mengirim: false })
}, { immediate: true })

async function simpan() {
  st.mengirim = true
  try {
    await aksi(props.p.slug, 'catatan_tim', { teks: st.teks.trim() })
    emit('ubah')
    emit('tutup')
  } catch (e) { st.galat = pesanGalat(e) } finally { st.mengirim = false }
}
</script>

<template>
  <Dialog :buka="!!p" judul="Catatan project" lebar="480px" @tutup="emit('tutup')">
    <form v-if="p" class="form-catatan" @submit.prevent="simpan">
      <p class="untuk redup"><code>{{ p.slug }}</code> {{ p.judul }}</p>
      <textarea v-model="st.teks" rows="5" maxlength="2000" aria-label="Catatan project" autofocus
        placeholder="Catatan internal tim, tidak dibaca agen Claude. Kosongkan untuk menghapus." />
      <p v-if="!namaSaya.trim()" class="pesan-status waspada">Masuk dulu lewat "Masuk dengan VD.net".</p>
      <p v-if="st.galat" class="pesan-status bahaya">{{ st.galat }}</p>
      <div class="aksi-dialog">
        <button type="button" class="tombol garis" @click="emit('tutup')">Tutup</button>
        <button type="submit" class="tombol" :disabled="!namaSaya.trim() || st.mengirim || st.teks.trim() === (p.catatan_tim?.teks || '')">{{ st.mengirim ? 'Menyimpan…' : 'Simpan' }}</button>
      </div>
    </form>
  </Dialog>
</template>

<style scoped>
.form-catatan { display: grid; gap: 12px; }
.untuk { margin: -6px 0 0; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.untuk code { font: 12px ui-monospace, SFMono-Regular, Consolas, monospace; margin-right: 4px; }
textarea { width: 100%; resize: vertical; font: inherit; font-size: 13.5px; }
.pesan-status { margin: 0; }
</style>
