<script setup>
// Batang bertumpuk per hari (token per jenis penggunaan). Satu sumbu, celah 2px antar-segmen,
// ujung atas membulat 4px, tooltip per batang saat kursor/tombol panah.
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  hari: { type: Array, required: true }, // [{ tgl: 'YYYY-MM-DD', nilai: { kunci: angka } }]
  seri: { type: Array, required: true }, // [{ kunci, label, warna }] — urutan tumpukan dari bawah
  format: { type: Function, required: true },
  formatTanggal: { type: Function, required: true },
})

const wadah = ref(null)
const lebar = ref(800)
const TINGGI = 260
const PAD = { kiri: 48, kanan: 8, atas: 14, bawah: 28 }
let ro = null
onMounted(() => {
  ro = new ResizeObserver(([e]) => { lebar.value = Math.max(300, Math.round(e.contentRect.width)) })
  ro.observe(wadah.value)
})
onBeforeUnmount(() => ro?.disconnect())

const n = computed(() => props.hari.length)
const jumlah = (h) => props.seri.reduce((a, s) => a + (h.nilai[s.kunci] || 0), 0)
// Batas atas sumbu: angka bulat 1/2/5 × 10^k di atas nilai tertinggi
const puncak = computed(() => {
  const m = Math.max(1, ...props.hari.map(jumlah))
  const p = 10 ** Math.floor(Math.log10(m))
  return [1, 2, 2.5, 5, 10].map((k) => k * p).find((v) => v >= m)
})
const kisi = computed(() => [0, 0.25, 0.5, 0.75, 1].map((f) => f * puncak.value))
const tinggiPlot = TINGGI - PAD.atas - PAD.bawah
const y = (v) => PAD.atas + tinggiPlot * (1 - v / puncak.value)
const slot = computed(() => (lebar.value - PAD.kiri - PAD.kanan) / Math.max(1, n.value))
const lebarBatang = computed(() => Math.max(3, Math.min(34, slot.value * 0.66)))
const xTengah = (i) => PAD.kiri + slot.value * (i + 0.5)

// Segmen tiap batang: dari bawah ke atas, celah 2px, hanya segmen teratas yang membulat
const batang = computed(() => props.hari.map((h, i) => {
  const seg = []
  let dasar = 0
  for (const s of props.seri) {
    const v = h.nilai[s.kunci] || 0
    if (!v) continue
    seg.push({ kunci: s.kunci, warna: s.warna, y0: y(dasar), y1: y(dasar + v) })
    dasar += v
  }
  seg.forEach((g, j) => {
    const atas = j === seg.length - 1
    const bawah = j === 0 ? g.y0 : g.y0 - 1
    const puncakY = atas ? g.y1 : g.y1 + 1
    g.tinggi = Math.max(0, bawah - puncakY)
    g.puncakY = puncakY
    g.atas = atas
  })
  return { i, x: xTengah(i), seg: seg.filter((g) => g.tinggi > 0.5) }
}))

// Kotak bermata bulat hanya di atas (4px) — ujung data menempel ke garis dasar
const jalurSeg = (x, w, top, h, bulat) => {
  const r = bulat ? Math.min(4, w / 2, h) : 0
  const l = x - w / 2, rr = x + w / 2, b = top + h
  return `M${l} ${b}V${top + r}${r ? `Q${l} ${top} ${l + r} ${top}` : ''}H${rr - r}${r ? `Q${rr} ${top} ${rr} ${top + r}` : ''}V${b}Z`
}

const labelSumbu = computed(() => {
  if (!n.value) return []
  const langkah = Math.max(1, Math.ceil(n.value / Math.max(2, Math.floor((lebar.value - PAD.kiri) / 70))))
  const idx = []
  for (let i = n.value - 1; i >= 0; i -= langkah) idx.push(i)
  return idx.map((i) => ({ x: xTengah(i), teks: props.formatTanggal(props.hari[i].tgl) }))
})

const aktif = ref(null)
function gerak(e) {
  const r = wadah.value.getBoundingClientRect()
  const px = ((e.clientX - r.left) / r.width) * lebar.value
  const i = Math.floor((px - PAD.kiri) / slot.value)
  aktif.value = i >= 0 && i < n.value ? i : null
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
  const h = props.hari[aktif.value]
  const kiri = (xTengah(aktif.value) / lebar.value) * 100
  const baris = props.seri.map((s) => ({ ...s, v: h.nilai[s.kunci] || 0 })).filter((s) => s.v).reverse()
  return { h, kiri, kanan: kiri > 60, baris, total: jumlah(h) }
})
const ringkas = computed(() => {
  if (!n.value) return 'Belum ada data'
  const tertinggi = props.hari.reduce((a, h) => (jumlah(h) > jumlah(a) ? h : a), props.hari[0])
  return `${n.value} hari, tertinggi ${props.formatTanggal(tertinggi.tgl)} ${props.format(jumlah(tertinggi))} token`
})
</script>

<template>
  <div ref="wadah" class="grafik">
    <svg
      :viewBox="`0 0 ${lebar} ${TINGGI}`" :height="TINGGI" role="img" tabindex="0"
      :aria-label="`Token per hari menurut jenis penggunaan. ${ringkas}. Gunakan panah kiri/kanan untuk melihat rincian per hari.`"
      @mousemove="gerak" @mouseleave="aktif = null" @keydown="tombol" @blur="aktif = null"
    >
      <g class="kisi">
        <template v-for="v in kisi" :key="v">
          <line :x1="PAD.kiri" :x2="lebar - PAD.kanan" :y1="y(v)" :y2="y(v)" />
          <text :x="PAD.kiri - 8" :y="y(v) + 4" text-anchor="end">{{ format(v) }}</text>
        </template>
        <text v-for="l in labelSumbu" :key="l.x" :x="l.x" :y="TINGGI - 8" text-anchor="middle">{{ l.teks }}</text>
      </g>
      <rect v-if="tip" class="sorot" :x="xTengah(aktif) - slot / 2" :y="PAD.atas" :width="slot" :height="tinggiPlot" rx="6" />
      <g v-for="b in batang" :key="b.i" :opacity="aktif == null || aktif === b.i ? 1 : 0.55">
        <path v-for="g in b.seg" :key="g.kunci" :d="jalurSeg(b.x, lebarBatang, g.puncakY, g.tinggi, g.atas)" :fill="g.warna" />
      </g>
    </svg>
    <div v-if="tip" class="tip" :style="tip.kanan ? { right: `${100 - tip.kiri + 2}%` } : { left: `${tip.kiri + 2}%` }" aria-hidden="true">
      <b>{{ formatTanggal(tip.h.tgl, true) }} · {{ format(tip.total) }}</b>
      <span v-for="s in tip.baris" :key="s.kunci"><i :style="{ background: s.warna }" />{{ s.label }} <strong>{{ format(s.v) }}</strong></span>
      <span v-if="!tip.baris.length" class="redup">Tidak ada pemakaian</span>
    </div>
  </div>
</template>

<style scoped>
.grafik { position: relative; }
svg { display: block; width: 100%; cursor: default; }
svg:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 4px; border-radius: 8px; }
.kisi line { stroke: #202746; stroke-width: 1; }
.kisi text { fill: var(--teks-3); font-size: 11px; font-variant-numeric: tabular-nums; }
.sorot { fill: rgba(255, 255, 255, .04); }
.tip {
  position: absolute; top: 8px; pointer-events: none; display: grid; gap: 3px; min-width: 190px;
  padding: 10px 12px; border-radius: 10px; background: #0b0e20; border: 1px solid var(--garis);
  box-shadow: 0 12px 30px rgba(0, 0, 0, .45); font-size: 12.5px; color: var(--teks-2); z-index: 2;
}
.tip b { color: var(--teks); font-weight: 600; }
.tip span { display: flex; align-items: center; gap: 7px; }
.tip i { width: 9px; height: 9px; border-radius: 3px; flex: none; }
.tip strong { margin-left: auto; padding-left: 12px; color: var(--teks); font-variant-numeric: tabular-nums; }
</style>
