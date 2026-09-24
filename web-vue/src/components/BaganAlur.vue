<script setup>
// Bagan alur installer: logikanya (SIMPUL, GARIS, konteksRun) ada di /alur.js (web/installer/alur.js, dipakai juga dashboard lama),
// dimuat saat runtime supaya perubahan alur installer cukup ditulis di satu berkas itu.
import { ref, watch, onMounted } from 'vue'

const props = defineProps({ row: Object, galat: String })
const wadah = ref(null)
const siap = ref(!!window.AlurInstaller)
const gagalMuat = ref('')

let pemuat = null
function muatSkrip() {
  if (window.AlurInstaller) return Promise.resolve()
  pemuat ||= new Promise((ok, tolak) => {
    const s = document.createElement('script')
    s.src = `/alur.js?v=${Date.now()}`
    s.onload = ok
    s.onerror = () => { pemuat = null; tolak(new Error('alur.js tidak termuat')) }
    document.head.appendChild(s)
  })
  return pemuat
}

function gambar() {
  if (siap.value && wadah.value && props.row) window.AlurInstaller.render(wadah.value, props.row, { galat: props.galat })
}
onMounted(async () => {
  try { await muatSkrip(); siap.value = true; gambar() } catch (e) { gagalMuat.value = e.message }
})
watch(() => [props.row, props.galat], gambar)
</script>

<template>
  <p v-if="gagalMuat" class="pesan-status bahaya">{{ gagalMuat }}</p>
  <p v-else-if="!row" class="redup">Memuat log run terakhir…</p>
  <div ref="wadah" class="bagan" />
</template>

<style scoped>
/* Isi bagan digambar alur.js lewat innerHTML, jadi gayanya lewat :deep */
.bagan :deep(.flow-meta) { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-bottom: 12px; font-size: 12.5px; color: var(--teks-3); }
.bagan :deep(.flow-meta strong) { color: var(--teks); font-size: 14px; }
.bagan :deep(.flow-meta .run) { color: var(--aksen-terang); }
.bagan :deep(.flow-meta .ok) { color: var(--baik); }
.bagan :deep(.flow-meta .err) { color: var(--bahaya); }
.bagan :deep(.flow-meta .chip) { padding: 1px 8px; border-radius: 6px; background: var(--kartu-2); color: var(--teks-2); }
.bagan :deep(.flow-log) { margin: -4px 0 10px; color: var(--aksen-terang); font-size: 12px; overflow-wrap: anywhere; }
.bagan :deep(.flow-catatan) { margin: 0 0 10px; color: var(--teks-3); font-size: 12.5px; }
.bagan :deep(.flow-legenda) { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 10px 0 0; color: var(--teks-3); font-size: 12px; }
.bagan :deep(.alur-kanvas) {
  overflow-x: auto; overflow-y: hidden; border: 1px solid var(--garis); border-radius: 12px; cursor: grab;
  background: var(--panel) radial-gradient(circle, #232a4a 1px, transparent 1.5px) 0 0 / 22px 22px;
  scrollbar-color: var(--garis) var(--panel);
}
.bagan :deep(.alur-kanvas.geser) { cursor: grabbing; user-select: none; }
.bagan :deep(.alur-isi) { position: relative; }
.bagan :deep(.alur-isi svg) { position: absolute; left: 0; top: 0; overflow: visible; pointer-events: none; }
.bagan :deep(.alur-simpul) { margin: 0; padding: 0; list-style: none; }
.bagan :deep(.node) {
  position: absolute; height: 74px; padding: 9px 10px 8px; border: 1px solid var(--garis); border-radius: 10px;
  background: var(--kartu); font-size: 12px; line-height: 1.3;
}
.bagan :deep(.node-cek) { position: absolute; display: flex; flex-direction: column; align-items: center; gap: 1px; text-align: center; font-size: 11px; line-height: 1.25; }
.bagan :deep(.ketupat) { display: grid; place-items: center; width: 38px; height: 38px; margin: 8px 0 12px; border: 1px solid var(--garis); border-radius: 6px; background: var(--kartu); transform: rotate(45deg); }
.bagan :deep(.ketupat .node-ikon) { border: 0; transform: rotate(-45deg); }
.bagan :deep(.cek-nama), .bagan :deep(.node-nama) { color: var(--teks); font-weight: 700; }
.bagan :deep(.cek-ket) { max-width: 100%; color: var(--teks-3); overflow-wrap: anywhere; }
.bagan :deep(.node-top) { display: flex; align-items: center; gap: 7px; }
.bagan :deep(.node-ikon) { display: grid; place-items: center; flex: none; width: 18px; height: 18px; border: 1px solid currentColor; border-radius: 50%; font-size: 10px; font-weight: 700; }
.bagan :deep(.node-nama) { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bagan :deep(.node-sub) { display: -webkit-box; margin-top: 5px; overflow: hidden; color: var(--teks-3); -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.bagan :deep(.node.selesai), .bagan :deep(.node-cek.selesai .ketupat) { border-color: rgba(52, 199, 123, .45); }
.bagan :deep(.node.selesai .node-ikon), .bagan :deep(.node-cek.selesai .node-ikon) { color: var(--baik); }
.bagan :deep(.node.berjalan) { border-color: var(--aksen-terang); box-shadow: 0 0 0 1px var(--aksen-terang), 0 0 18px rgba(91, 140, 255, .35); }
.bagan :deep(.node.berjalan .node-ikon) { color: var(--aksen-terang); animation: denyut 1.2s ease-in-out infinite; }
.bagan :deep(.node.gagal), .bagan :deep(.node-cek.gagal .ketupat) { border-color: var(--bahaya); }
.bagan :deep(.node.gagal .node-ikon), .bagan :deep(.node.gagal .node-sub) { color: var(--bahaya); }
.bagan :deep(.node.dilewati) { border-style: dashed; }
.bagan :deep(.node.cabang), .bagan :deep(.node-cek.cabang .ketupat) { border-style: dashed; background: transparent; }
.bagan :deep(.node.dilewati .node-ikon), .bagan :deep(.node.dilewati .node-nama), .bagan :deep(.node.menunggu .node-ikon),
.bagan :deep(.node.menunggu .node-nama), .bagan :deep(.node.cabang .node-ikon), .bagan :deep(.node.cabang .node-nama),
.bagan :deep(.node-cek.cabang .node-ikon), .bagan :deep(.node-cek.cabang .cek-nama),
.bagan :deep(.node-cek.menunggu .node-ikon), .bagan :deep(.node-cek.menunggu .cek-nama) { color: var(--teks-3); }
.bagan :deep(.edge) { fill: none; stroke: #2e3760; stroke-width: 2; }
.bagan :deep(.edge.selesai) { stroke: var(--baik); stroke-opacity: .7; }
.bagan :deep(.edge.gagal) { stroke: var(--bahaya); }
.bagan :deep(.edge.cabang) { stroke: var(--garis); stroke-dasharray: 3 5; }
.bagan :deep(.edge.berjalan) { stroke: var(--aksen-terang); stroke-dasharray: 6 6; animation: alir .8s linear infinite; }
.bagan :deep(.edge-label) { fill: var(--teks-3); font: 10.5px "Plus Jakarta Sans", sans-serif; }
.bagan :deep(.edge-label.aktif) { fill: var(--teks-2); }
@keyframes alir { to { stroke-dashoffset: -12; } }
@keyframes denyut { 50% { opacity: .5; } }
@media (prefers-reduced-motion: reduce) { .bagan :deep(.edge.berjalan), .bagan :deep(.node.berjalan .node-ikon) { animation: none; } }
</style>
