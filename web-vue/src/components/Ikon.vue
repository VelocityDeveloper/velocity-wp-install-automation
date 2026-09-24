<script setup>
// Ikon garis 20px buatan sendiri (bukan pustaka), satu gaya: stroke 1.6, ujung bulat
defineProps({ nama: { type: String, required: true }, ukuran: { type: Number, default: 20 } })
const PATH = {
  dashboard: 'M3 3h6v8H3zM11 3h6v5h-6zM11 10h6v7h-6zM3 13h6v4H3z',
  installer: 'M10 3v9m0 0-3.5-3.5M10 12l3.5-3.5M4 13v2a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-2',
  ai: 'M7 3v2M13 3v2M7 15v2M13 15v2M3 7h2M3 13h2M15 7h2M15 13h2M6 5h8a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM8 8h4v4H8z',
  token: 'M3 17h14M5 17V11M9 17V6M13 17V9M17 17V4',
  paket: 'M3.5 6.5 10 3l6.5 3.5v7L10 17l-6.5-3.5zM3.5 6.5 10 10l6.5-3.5M10 10v7',
  server: 'M4 3h12a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM4 11h12a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1zM6 6h.01M6 14h.01',
  proyek: 'M3 5a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1zM3 8h14M8.5 10.5 6.5 12.5l2 2M11.5 10.5l2 2-2 2',
  kunci: 'M6 9V6.5a4 4 0 0 1 8 0V9M5 9h10a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1zM10 12v2',
  salin: 'M7 7V4a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1h-3M4 7h8a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z',
  centang: 'M4 10.5 8 14.5 16 5.5',
  brain: 'M7 4a3 3 0 0 0-3 3v1a3 3 0 0 0 0 4v1a3 3 0 0 0 3 3h1V4zM13 4a3 3 0 0 1 3 3v1a3 3 0 0 1 0 4v1a3 3 0 0 1-3 3h-1V4z',
  n8n: 'M5 10h4M11 10h4M5 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0zM13 10a2 2 0 1 0-4 0M19 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0z',
  hermes: 'M4 5h12a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H9l-4 3v-3H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z',
  berkas: 'M3 6a1 1 0 0 1 1-1h4l2 2h6a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z',
  crm: 'M7 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 17a5 5 0 0 1 10 0M14 5h4M14 9h4M14 13h4',
  cadangan: 'M5 14a4 4 0 0 1 .5-8A5 5 0 0 1 15 7a3.5 3.5 0 0 1 .5 7M10 10v7m0-7-2.5 2.5M10 10l2.5 2.5',
  jam: 'M10 17a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM10 6v4l3 2',
  daya: 'M10 3v7M6 5.5a6 6 0 1 0 8 0',
  ulang: 'M16 10a6 6 0 1 1-2-4.5M16 4v3h-3',
  luar: 'M8 4H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-3M11 3h6v6M17 3l-8 8',
  menu: 'M3 5h14M3 10h14M3 15h14',
  claude: 'M10 3v14M3.9 6.5l12.2 7M3.9 13.5l12.2-7',
  bawah: 'M6 8l4 4 4-4',
  tutup: 'M5 5l10 10M15 5 5 15',
}
</script>

<template>
  <svg :width="ukuran" :height="ukuran" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="PATH[nama]" /></svg>
</template>
