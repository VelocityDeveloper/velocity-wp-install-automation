<script setup>
// Dialog ubah status project (Aktif / Ditunda / Batal) — dipakai di daftar /installer/laravel & halaman project.
// `p` = ringkasan project dari API (slug, status_proyek, status_info, job). Emit `ubah` sesudah tersimpan.
import { reactive, watch } from 'vue'
import Dialog from '../Dialog.vue'
import { namaSaya, STATUS_PROYEK, aksi, pesanGalat } from '../../laravel.js'

const props = defineProps({ p: Object })
const emit = defineEmits(['tutup', 'ubah'])
const st = reactive({ nilai: 'aktif', alasan: '', galat: '', mengirim: false })
watch(() => props.p, (p) => {
  if (p) Object.assign(st, { nilai: p.status_proyek || 'aktif', alasan: p.status_info?.alasan || '', galat: '', mengirim: false })
}, { immediate: true })

async function simpan() {
  st.mengirim = true
  try {
    await aksi(props.p.slug, 'status', { nilai: st.nilai, alasan: st.alasan.trim() })
    emit('ubah')
    emit('tutup')
  } catch (e) { st.galat = pesanGalat(e) } finally { st.mengirim = false }
}
</script>

<template>
  <Dialog :buka="!!p" judul="Ubah status" lebar="420px" @tutup="emit('tutup')">
    <form v-if="p" class="form-status" @submit.prevent="simpan">
      <p class="untuk redup"><code>{{ p.slug }}</code> {{ p.judul }}</p>
      <div class="segmen" role="radiogroup" aria-label="Status project">
        <label v-for="(s, k) in STATUS_PROYEK" :key="k" :class="[k, { dipilih: st.nilai === k }]">
          <input v-model="st.nilai" type="radio" name="status-proyek" :value="k" class="sr">
          <i aria-hidden="true" />{{ s.label }}
        </label>
      </div>
      <p class="ket redup">{{ STATUS_PROYEK[st.nilai]?.ket }}</p>
      <textarea v-if="st.nilai !== 'aktif'" v-model="st.alasan" rows="2" maxlength="500" aria-label="Alasan (opsional)"
        :placeholder="st.nilai === 'selesai' ? 'Catatan (opsional) — mis. sudah serah terima ke klien' : 'Alasan (opsional) — mis. klien memilih vendor lain'" />
      <p v-if="p.job && st.nilai !== 'aktif'" class="pesan-status waspada">Masih ada proses berjalan; tunggu selesai dulu.</p>
      <p v-if="!namaSaya.trim()" class="pesan-status waspada">Isi "Nama Anda" dulu.</p>
      <p v-if="st.galat" class="pesan-status bahaya">{{ st.galat }}</p>
      <div class="aksi-dialog">
        <button type="button" class="tombol garis" @click="emit('tutup')">Tutup</button>
        <button type="submit" class="tombol" :disabled="!namaSaya.trim() || st.mengirim || st.nilai === (p.status_proyek || 'aktif')">{{ st.mengirim ? 'Menyimpan…' : 'Simpan' }}</button>
      </div>
    </form>
  </Dialog>
</template>

<style scoped>
.form-status { display: grid; gap: 12px; }
.form-status .aksi-dialog { margin-top: 4px; }
.untuk { margin: -6px 0 0; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.untuk code { font: 12px ui-monospace, SFMono-Regular, Consolas, monospace; margin-right: 4px; }
.segmen { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; padding: 4px; border-radius: 12px; background: var(--kartu-2); }
.segmen label { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 9px 8px; border-radius: 9px; font-size: 13.5px; font-weight: 600; color: var(--teks-2); cursor: pointer; transition: background .15s, color .15s; }
.segmen label:hover { color: var(--teks); }
.segmen label i { width: 8px; height: 8px; border-radius: 50%; background: var(--baik); flex: none; }
.segmen .selesai i { background: var(--aksen-terang); }
.segmen .ditunda i { background: var(--waspada); }
.segmen .batal i { background: var(--bahaya); }
.segmen label.dipilih { background: var(--kartu); color: var(--teks); box-shadow: 0 1px 3px rgba(0, 0, 0, .25), inset 0 0 0 1px var(--garis); }
.segmen label:has(input:focus-visible) { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
.sr { position: absolute; opacity: 0; width: 1px; height: 1px; pointer-events: none; }
.ket { margin: -2px 2px 0; font-size: 12.5px; min-height: 1.4em; }
textarea { width: 100%; resize: vertical; font: inherit; font-size: 13.5px; }
.pesan-status { margin: 0; }
</style>
