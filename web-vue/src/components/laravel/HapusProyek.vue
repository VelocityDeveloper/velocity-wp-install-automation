<script setup>
// Dialog hapus project (project ujicoba / brief yang tidak dipakai) — dipakai di daftar /installer/laravel & halaman project.
// Server (L.hapus_proyek) hanya menerima project yang belum di-install; folder data dipindah ke cadangan, bukan dibuang.
// `p` = ringkasan project dari API (slug, judul, app, install, job). Emit `hapus` sesudah terhapus.
import { reactive, computed, watch } from 'vue'
import Dialog from '../Dialog.vue'
import { namaSaya, aksi, pesanGalat } from '../../laravel.js'

const props = defineProps({ p: Object })
const emit = defineEmits(['tutup', 'hapus'])
const st = reactive({ ketik: '', galat: '', mengirim: false })
watch(() => props.p, () => Object.assign(st, { ketik: '', galat: '', mengirim: false }))
const terinstall = computed(() => !!(props.p?.app || props.p?.install?.status))

async function hapus() {
  st.mengirim = true
  try {
    await aksi(props.p.slug, 'hapus', { konfirmasi: st.ketik.trim() })
    emit('hapus', props.p.slug)
    emit('tutup')
  } catch (e) {
    st.galat = String(e?.message || e).startsWith('sudah_diinstall') ? 'Project sudah di-install; tidak bisa dihapus dari sini.' : pesanGalat(e)
  } finally { st.mengirim = false }
}
</script>

<template>
  <Dialog :buka="!!p" judul="Hapus project" lebar="440px" @tutup="emit('tutup')">
    <form v-if="p" class="form-hapus" @submit.prevent="hapus">
      <p class="untuk redup"><code>{{ p.slug }}</code> {{ p.judul }}</p>
      <template v-if="terinstall">
        <p class="pesan-status waspada">Project ini sudah di-install (aplikasi <code>{{ p.app || '-' }}</code>: folder, database, repo GitHub, layanan dev). Hapus dari sini hanya untuk project yang belum di-install — gunakan status <b>Batal</b> untuk menyembunyikannya.</p>
        <div class="aksi-dialog"><button type="button" class="tombol garis" @click="emit('tutup')">Tutup</button></div>
      </template>
      <template v-else>
        <p class="ket">Project hilang dari daftar beserta brief, dokumen klien, estimasi, dan contoh tampilannya (preview klien ikut dicabut). Data disimpan sebagai cadangan di server; nomor <code>{{ p.slug }}</code> tidak dipakai ulang.</p>
        <label class="ketik">Ketik <code>{{ p.slug }}</code> untuk konfirmasi
          <input v-model="st.ketik" type="text" autocomplete="off" spellcheck="false" :placeholder="p.slug">
        </label>
        <p v-if="p.job" class="pesan-status waspada">Masih ada proses berjalan; tunggu selesai dulu.</p>
        <p v-if="!namaSaya.trim()" class="pesan-status waspada">Masuk dulu lewat "Masuk dengan VD.net".</p>
        <p v-if="st.galat" class="pesan-status bahaya">{{ st.galat }}</p>
        <div class="aksi-dialog">
          <button type="button" class="tombol garis" @click="emit('tutup')">Batal</button>
          <button type="submit" class="tombol bahaya" :disabled="!namaSaya.trim() || st.mengirim || !!p.job || st.ketik.trim() !== p.slug">{{ st.mengirim ? 'Menghapus…' : 'Hapus project' }}</button>
        </div>
      </template>
    </form>
  </Dialog>
</template>

<style scoped>
.form-hapus { display: grid; gap: 12px; }
.form-hapus .aksi-dialog { margin-top: 4px; }
.untuk { margin: -6px 0 0; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
code { font: 12px ui-monospace, SFMono-Regular, Consolas, monospace; }
.untuk code { margin-right: 4px; }
.ket { margin: 0; font-size: 13.5px; color: var(--teks-2); }
.ketik { display: grid; gap: 6px; font-size: 13px; color: var(--teks-2); }
.ketik input { width: 100%; font: 13px ui-monospace, SFMono-Regular, Consolas, monospace; }
.pesan-status { margin: 0; }
</style>
