<script setup>
// Pengganti kolom "Nama Anda": aksi dicatat atas nama akun yang masuk ke dash.velocity.ai.id.
// Belum masuk → tombol "Masuk dengan VD.net" (dari LAN dibawa ke halaman yang sama di dash).
import { akun, akunDimuat, inisial, urlMasuk } from '../akun.js'

defineProps({ id: { type: String, default: 'nama-saya' } })
</script>

<template>
  <span v-if="!akunDimuat" class="pelaku redup">Memeriksa login…</span>
  <RouterLink v-else-if="akun" :id="id" to="/profil" class="pelaku" :title="`Aksi dicatat atas nama ${akun.nama}`">
    <span class="avatar kecil" aria-hidden="true">{{ inisial(akun.nama) }}</span>
    <span class="nama">{{ akun.nama }}</span>
  </RouterLink>
  <a v-else :id="id" :href="urlMasuk()" class="tombol kecil masuk">
    <img src="https://new.velocitydeveloper.net/vd.webp" alt="" width="16" height="16"> Masuk dengan VD.net
  </a>
</template>

<style scoped>
.pelaku { display: inline-flex; align-items: center; gap: 8px; min-height: 34px; padding: 3px 12px 3px 4px; border-radius: 999px; border: 1px solid var(--garis); background: var(--kartu); color: var(--teks-kuat); font-size: 13.5px; font-weight: 600; max-width: 100%; }
.pelaku.redup { padding: 3px 12px; font-weight: 400; }
a.pelaku:hover { border-color: var(--aksen-terang); }
.avatar.kecil { width: 26px; height: 26px; font-size: 11px; }
.nama { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.masuk img { border-radius: 4px; background: #fff; }
</style>
