<script setup>
// Referensi desain (15 Okt): link yang terdeteksi otomatis di catatan/dokumen klien + link tambahan PM (dengan keterangan,
// mis. "hanya header"), atau tanda desain diserahkan ke tim. Disimpan lewat aksi `simpan` {referensi}; dibaca agen contoh & Install.
import { ref, computed } from 'vue'
import { aksi, pesanGalat, namaSaya } from '../../laravel.js'

const props = defineProps({ d: { type: Object, required: true } })
const emit = defineEmits(['ubah'])

const r = computed(() => props.d.referensi_desain || { terdeteksi: [], tambahan: [], abaikan: [], diserahkan: false })
const url = ref('')
const ket = ref('')
const menyimpan = ref(false)
const status = ref({ kelas: '', teks: '' })
const bisa = computed(() => !menyimpan.value && !!namaSaya.value.trim())

async function simpan(ubah, pesanOk) {
  const data = { tambahan: r.value.tambahan.map(({ url, ket }) => ({ url, ket })), abaikan: [...r.value.abaikan], diserahkan: r.value.diserahkan, ...ubah }
  menyimpan.value = true
  status.value = { kelas: '', teks: '' }
  try {
    await aksi(props.d.slug, 'simpan', { referensi: data })
    status.value = { kelas: 'baik', teks: pesanOk + (props.d.contoh ? ' Buat ulang contoh tampilan agar ikut berubah.' : '') }
    emit('ubah')
    return true
  } catch (e) {
    status.value = { kelas: 'bahaya', teks: pesanGalat(e) }
    return false
  } finally {
    menyimpan.value = false
  }
}
async function tambah() {
  if (await simpan({ tambahan: [...r.value.tambahan.map(({ url, ket }) => ({ url, ket })), { url: url.value.trim(), ket: ket.value.trim() }] }, 'Referensi ditambahkan.')) {
    url.value = ''
    ket.value = ''
  }
}
const hapusTambahan = (i) => simpan({ tambahan: r.value.tambahan.filter((_, j) => j !== i).map(({ url, ket }) => ({ url, ket })) }, 'Referensi dihapus.')
const abaikan = (dom, ya) => simpan({ abaikan: ya ? [...r.value.abaikan, dom] : r.value.abaikan.filter((x) => x !== dom) }, ya ? 'Link tidak dipakai sebagai referensi.' : 'Link dipakai lagi.')
</script>

<template>
  <fieldset class="ref">
    <legend>Referensi desain <span class="redup">— situs/tampilan yang ingin ditiru klien</span></legend>
    <label class="serah">
      <input type="checkbox" :checked="r.diserahkan" :disabled="!bisa" @change="simpan({ diserahkan: $event.target.checked }, $event.target.checked ? 'Desain diserahkan ke tim.' : 'Referensi dipakai lagi.')">
      Klien menyerahkan desain ke tim (tanpa referensi)
    </label>
    <template v-if="!r.diserahkan">
      <ul v-if="r.tambahan.length || r.terdeteksi.length">
        <li v-for="(x, i) in r.tambahan" :key="'t' + i">
          <span><a :href="x.url" target="_blank" rel="noopener">{{ x.url.replace(/^https?:\/\//, '') }}</a>
            <span class="pil kecil">ditambah PM</span><span v-if="x.ket" class="redup"> — {{ x.ket }}</span></span>
          <button type="button" class="tombol garis kecil" :disabled="!bisa" @click="hapusTambahan(i)">Hapus</button>
        </li>
        <li v-for="x in r.terdeteksi" :key="x.domain" :class="{ coret: r.abaikan.includes(x.domain) }">
          <span><a :href="x.url" target="_blank" rel="noopener">{{ x.url.replace(/^https?:\/\//, '') }}</a>
            <span class="pil kecil">dari catatan/dokumen</span></span>
          <button v-if="r.abaikan.includes(x.domain)" type="button" class="tombol garis kecil" :disabled="!bisa" @click="abaikan(x.domain, false)">Pakai lagi</button>
          <button v-else type="button" class="tombol garis kecil" :disabled="!bisa" @click="abaikan(x.domain, true)" title="Bukan referensi tampilan (mis. situs pembayaran/ekspedisi)">Bukan referensi</button>
        </li>
      </ul>
      <p v-else class="redup">Belum ada link. Link yang ditulis di catatan atau dokumen klien muncul di sini otomatis.</p>
      <form class="tambah" @submit.prevent="tambah">
        <input v-model="url" type="text" inputmode="url" maxlength="300" placeholder="Link referensi, mis. alibaba.com" aria-label="Link referensi desain" :disabled="!bisa">
        <input v-model="ket" type="text" maxlength="200" placeholder="Bagian yang ditiru (opsional), mis. header & grid produk saja" aria-label="Bagian yang ditiru" :disabled="!bisa">
        <button type="submit" class="tombol garis kecil" :disabled="!bisa || !url.trim()">Tambah</button>
      </form>
      <p class="redup">Gambar di dalam Word/PDF klien (screenshot, sketsa) ikut dibaca otomatis sebagai referensi.</p>
    </template>
    <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
  </fieldset>
</template>

<style scoped>
.ref { margin: 16px 0 0; padding: 12px 14px; border: 1px solid var(--garis); border-radius: 12px; display: grid; gap: 10px; min-width: 0; }
.ref legend { padding: 0 6px; font-size: 13.5px; font-weight: 600; }
.ref legend .redup { font-weight: 400; }
.ref p { margin: 0; font-size: 13px; }
.serah { display: flex; gap: 8px; align-items: center; font-size: 13.5px; }
ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; }
li { display: flex; gap: 10px; align-items: center; justify-content: space-between; font-size: 13.5px; padding: 6px 10px; border-radius: 8px; background: var(--kartu-2); }
li > span { min-width: 0; overflow-wrap: anywhere; }
li.coret a { text-decoration: line-through; opacity: .6; }
li .pil { margin-left: 6px; }
.tambah { display: flex; gap: 8px; flex-wrap: wrap; }
.tambah input { flex: 1 1 220px; min-width: 0; font: inherit; font-size: 13.5px; }
.tambah input:nth-child(2) { flex-basis: 300px; }
</style>
