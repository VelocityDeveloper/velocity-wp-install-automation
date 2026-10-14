<script setup>
// Dulu: pilih "Nama Anda" dari tim CRM. Sejak 14 Okt 2026 pengisi = akun yang masuk ke dash.velocity.ai.id
// (Masuk dengan VD.net), jadi komponen ini hanya menampilkan akun atau tombol masuk. Prop tim tak dipakai lagi.
import PelakuAkun from '../PelakuAkun.vue'

defineProps({ tim: { type: Object, default: () => ({}) }, id: { type: String, default: 'nama-saya' } })
</script>

<template>
  <PelakuAkun :id="id" />
</template>
