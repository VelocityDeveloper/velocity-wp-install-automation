<script setup>
// Grafik garis persen (0–100) untuk riwayat CPU/RAM. Satu sumbu, garis 2px, isi gradasi tipis +
// pendar lembut (gaya referensi), crosshair + tooltip saat kursor/tombol panah, label langsung di ujung garis.
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  titik: { type: Array, required: true }, // [{ t, cpu, mem, ... }]
  seri: { type: Array, required: true }, // [{ kunci, label, warna }]
  formatWaktu: { type: Function, required: true },
})

const wadah = ref(null)
const lebar = ref(800)
const TINGGI = 260
const PAD = { kiri: 40, kanan: 64, atas: 16, bawah: 28 }
let ro = null
onMounted(() => {
  ro = new ResizeObserver(([e]) => { lebar.value = Math.max(300, Math.round(e.contentRect.width)) })
  ro.observe(wadah.value)
})
onBeforeUnmount(() => ro?.disconnect())

const n = computed(() => props.titik.length)
const x = (i) => PAD.kiri + (lebar.value - PAD.kiri - PAD.kanan) * (n.value < 2 ? 0.5 : i / (n.value - 1))
const y = (v) => PAD.atas + (TINGGI - PAD.atas - PAD.bawah) * (1 - Math.max(0, Math.min(100, Number(v) || 0)) / 100)

// Kurva halus (monotone-ish) agar mirip referensi, tanpa melewati batas 0–100
const jalur = (kunci) => {
  const p = props.titik.map((q, i) => [x(i), y(q[kunci])])
  if (!p.length) return ''
  let d = `M${p[0][0].toFixed(1)} ${p[0][1].toFixed(1)}`
  for (let i = 1; i < p.length; i++) {
    const [x0, y0] = p[i - 1], [x1, y1] = p[i], cx = (x0 + x1) / 2
    d += ` C${cx.toFixed(1)} ${y0.toFixed(1)} ${cx.toFixed(1)} ${y1.toFixed(1)} ${x1.toFixed(1)} ${y1.toFixed(1)}`
  }
  return d
}
const area = (kunci) => n.value ? `${jalur(kunci)} L${x(n.value - 1).toFixed(1)} ${y(0)} L${x(0).toFixed(1)} ${y(0)} Z` : ''

const kisi = [0, 25, 50, 75, 100]
const labelSumbu = computed(() => {
  if (!n.value) return []
  const idx = [...new Set([0, Math.floor((n.value - 1) / 2), n.value - 1])]
  return idx.map((i) => ({ x: x(i), teks: props.formatWaktu(props.titik[i].t), anchor: i === 0 ? 'start' : i === n.value - 1 ? 'end' : 'middle' }))
})

// Label langsung di ujung kanan; digeser bila dua label bertumpuk
const labelUjung = computed(() => {
  if (!n.value) return []
  const akhir = props.titik[n.value - 1]
  const l = props.seri.map((s) => ({ ...s, y: y(akhir[s.kunci]), nilai: Math.round(akhir[s.kunci]) }))
  l.sort((a, b) => a.y - b.y)
  for (let i = 1; i < l.length; i++) if (l[i].y - l[i - 1].y < 16) l[i].y = l[i - 1].y + 16
  return l
})

// Crosshair
const aktif = ref(null)
function gerak(e) {
  const r = wadah.value.getBoundingClientRect()
  const px = ((e.clientX - r.left) / r.width) * lebar.value
  const i = Math.round(((px - PAD.kiri) / (lebar.value - PAD.kiri - PAD.kanan)) * (n.value - 1))
  aktif.value = Math.max(0, Math.min(n.value - 1, i))
}
function tombol(e) {
  if (!n.value) return
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    e.preventDefault()
    const i = aktif.value ?? n.value - 1
    aktif.value = Math.max(0, Math.min(n.value - 1, i + (e.key === 'ArrowLeft' ? -1 : 1)))
  } else if (e.key === 'Escape') aktif.value = null
}
const tip = computed(() => {
  if (aktif.value == null || !n.value) return null
  const q = props.titik[aktif.value]
  const kiri = (x(aktif.value) / lebar.value) * 100
  return { q, x: x(aktif.value), kiri, kanan: kiri > 60 }
})
const ringkas = computed(() => {
  if (!n.value) return 'Belum ada data'
  const akhir = props.titik[n.value - 1]
  return props.seri.map((s) => `${s.label} terakhir ${Math.round(akhir[s.kunci])}%`).join(', ')
})
const id = `g${Math.random().toString(36).slice(2, 8)}`
</script>

<template>
  <div ref="wadah" class="grafik">
    <svg
      :viewBox="`0 0 ${lebar} ${TINGGI}`" :height="TINGGI" role="img" tabindex="0"
      :aria-label="`Grafik pemakaian. ${ringkas}. Gunakan panah kiri/kanan untuk melihat nilai per waktu.`"
      @mousemove="gerak" @mouseleave="aktif = null" @keydown="tombol" @blur="aktif = null"
    >
      <defs>
        <linearGradient v-for="s in seri" :id="`${id}-${s.kunci}`" :key="s.kunci" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="s.warna" stop-opacity=".32" />
          <stop offset="100%" :stop-color="s.warna" stop-opacity="0" />
        </linearGradient>
        <filter :id="`${id}-pendar`" x="-5%" y="-20%" width="110%" height="140%"><feGaussianBlur stdDeviation="5" /></filter>
      </defs>
      <g class="kisi">
        <template v-for="v in kisi" :key="v">
          <line :x1="PAD.kiri" :x2="lebar - PAD.kanan" :y1="y(v)" :y2="y(v)" />
          <text :x="PAD.kiri - 8" :y="y(v) + 4" text-anchor="end">{{ v }}%</text>
        </template>
        <text v-for="(l, i) in labelSumbu" :key="i" :x="l.x" :y="TINGGI - 8" :text-anchor="l.anchor">{{ l.teks }}</text>
      </g>
      <g v-for="s in seri" :key="s.kunci">
        <path :d="area(s.kunci)" :fill="`url(#${id}-${s.kunci})`" />
        <path :d="jalur(s.kunci)" fill="none" :stroke="s.warna" stroke-width="5" opacity=".45" :filter="`url(#${id}-pendar)`" />
        <path :d="jalur(s.kunci)" fill="none" :stroke="s.warna" stroke-width="2" stroke-linecap="round" />
        <circle v-if="n === 1" :cx="x(0)" :cy="y(titik[0][s.kunci])" r="4" :fill="s.warna" />
      </g>
      <g class="ujung">
        <text v-for="l in labelUjung" :key="l.kunci" :x="lebar - PAD.kanan + 8" :y="l.y + 4">{{ l.label }} {{ l.nilai }}%</text>
      </g>
      <g v-if="tip">
        <line class="silang" :x1="tip.x" :x2="tip.x" :y1="PAD.atas" :y2="TINGGI - PAD.bawah" />
        <circle v-for="s in seri" :key="s.kunci" :cx="tip.x" :cy="y(tip.q[s.kunci])" r="5" :fill="s.warna" stroke="#151a33" stroke-width="2" />
      </g>
    </svg>
    <div v-if="tip" class="tip" :style="tip.kanan ? { right: `${100 - tip.kiri + 1.5}%` } : { left: `${tip.kiri + 1.5}%` }" aria-hidden="true">
      <b>{{ formatWaktu(tip.q.t, true) }}</b>
      <span v-for="s in seri" :key="s.kunci"><i :style="{ background: s.warna }" />{{ s.label }} <strong>{{ Math.round(tip.q[s.kunci]) }}%</strong></span>
    </div>
  </div>
</template>

<style scoped>
.grafik { position: relative; }
svg { display: block; width: 100%; cursor: crosshair; }
svg:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 4px; border-radius: 8px; }
.kisi line { stroke: #202746; stroke-width: 1; }
.kisi text, .ujung text { fill: var(--teks-3); font-size: 11px; }
.ujung text { fill: var(--teks-2); font-weight: 600; }
.silang { stroke: #5b6391; stroke-width: 1; stroke-dasharray: 3 3; }
.tip {
  position: absolute; top: 8px; pointer-events: none; display: grid; gap: 3px; min-width: 150px;
  padding: 10px 12px; border-radius: 10px; background: #0b0e20; border: 1px solid var(--garis);
  box-shadow: 0 12px 30px rgba(0, 0, 0, .45); font-size: 12.5px; color: var(--teks-2);
}
.tip b { color: var(--teks); font-weight: 600; }
.tip span { display: flex; align-items: center; gap: 7px; }
.tip i { width: 9px; height: 9px; border-radius: 3px; flex: none; }
.tip strong { margin-left: auto; color: var(--teks); }
</style>
