<script setup>
// Bilah 100% bertumpuk: porsi token per tahap pengerjaan (lihat tahapToken.js). Celah 2px antar-segmen, ujung bilah
// membulat. Tooltip per segmen (tahap, token, persen, alur terbesar). `ringkas` = bilah tipis tanpa legenda untuk baris tabel.
import { ref, computed } from 'vue'
import { persenTahap } from '../tahapToken.js'

const props = defineProps({
  tahap: { type: Array, required: true }, // dari rekapTahap()
  format: { type: Function, required: true },
  judul: { type: String, default: 'Porsi token per tahap' },
  ringkas: { type: Boolean, default: false },
})

const total = computed(() => props.tahap.reduce((n, t) => n + t.total, 0))
const isi = computed(() => props.tahap.filter((t) => t.total > 0))
const terbesar = computed(() => isi.value.reduce((m, t) => (!m || t.total > m.total ? t : m), null))
const aktif = ref(null)
// Tooltip menempel di atas segmen yang disorot (posisi tengah segmen, dijepit supaya tidak keluar wadah)
const tip = computed(() => {
  let dasar = 0
  for (const t of isi.value) {
    const tengah = (dasar + t.total / 2) / (total.value || 1) * 100
    if (t.kunci === aktif.value) return { ...t, kiri: Math.min(60, Math.max(0, tengah - 15)) }
    dasar += t.total
  }
  return null
})
const labelSeg = (t) => `${t.label} ${persenTahap(t.total, total.value)}, ${props.format(t.total)} token${t.alur[0] ? `, terbesar ${t.alur[0].label}` : ''}`
// Pindah fokus antar-segmen tidak mengosongkan sorotan dulu (mencegah kedip)
const lepas = (e) => { if (!e.relatedTarget?.classList?.contains('seg')) aktif.value = null }
const ringkasan = computed(() => `${props.judul}: ${isi.value.map((t) => `${t.label} ${persenTahap(t.total, total.value)}`).join(', ') || 'belum ada pemakaian'}`)
</script>

<template>
  <!-- Akar <span>: varian ringkas berada di dalam <button> baris project, jadi isinya harus elemen frasa -->
  <span class="bilah-tahap" :class="{ ringkas }" @mouseleave="aktif = null">
    <span v-if="ringkas" class="bilah" aria-hidden="true">
      <span v-for="t in isi" :key="t.kunci" class="seg" :class="{ redup: aktif && aktif !== t.kunci }" :style="{ flexGrow: t.total, background: t.warna }" @mouseenter="aktif = t.kunci" />
      <span v-if="!isi.length" class="seg kosong" />
    </span>
    <span v-else class="bilah" role="group" :aria-label="ringkasan">
      <span
        v-for="t in isi" :key="t.kunci" class="seg" :class="{ redup: aktif && aktif !== t.kunci }"
        :style="{ flexGrow: t.total, background: t.warna }" tabindex="0" role="img" :aria-label="labelSeg(t)"
        @mouseenter="aktif = t.kunci" @focus="aktif = t.kunci" @blur="lepas" @click="aktif = t.kunci"
      />
      <span v-if="!isi.length" class="seg kosong" role="img" aria-label="Belum ada pemakaian" />
    </span>
    <span v-if="tip" class="tip" aria-hidden="true" :style="{ left: ringkas ? 0 : `${tip.kiri}%` }">
      <b><i :style="{ background: tip.warna }" />{{ tip.label }} · {{ persenTahap(tip.total, total) }}</b>
      <span class="redup">{{ format(tip.total) }} token<template v-if="tip.biaya"> · ${{ tip.biaya.toFixed(2) }}</template></span>
      <span v-for="a in tip.alur.slice(0, 4)" :key="a.label" class="alur"><span>{{ a.label }}</span><strong>{{ persenTahap(a.total, total) }}</strong></span>
      <span v-if="tip.alur.length > 4" class="redup">+{{ tip.alur.length - 4 }} alur lain</span>
    </span>
    <ul v-if="!ringkas" class="legenda-tahap" :aria-label="`Legenda ${judul}`">
      <li v-for="t in tahap" :key="t.kunci" :class="{ nol: !t.total, sorot: aktif === t.kunci }" :title="t.ket"
          @mouseenter="t.total && (aktif = t.kunci)">
        <i :style="{ background: t.total ? t.warna : 'var(--garis)' }" />
        <span>{{ t.label }}</span>
        <b>{{ t.total ? persenTahap(t.total, total) : '–' }}</b>
        <small class="redup">{{ t.total ? format(t.total) : 'belum tercatat' }}</small>
      </li>
    </ul>
    <span v-else-if="terbesar" class="ket-ringkas redup">{{ terbesar.label }} {{ persenTahap(terbesar.total, total) }} <span class="sr">· {{ ringkasan }}</span></span>
  </span>
</template>

<style scoped>
.bilah-tahap { display: block; position: relative; min-width: 0; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.bilah { display: flex; gap: 2px; height: 14px; border-radius: 4px; overflow: hidden; }
.ringkas .bilah { height: 7px; border-radius: 3px; }
.seg { flex-basis: 0; min-width: 3px; transition: opacity .12s; outline: none; }
.seg.kosong { flex-grow: 1; background: var(--garis); }
.seg.redup { opacity: .45; }
.seg:focus-visible { box-shadow: inset 0 0 0 2px var(--teks-kuat); }
.tip {
  position: absolute; left: 0; top: calc(100% + 6px); z-index: 5; pointer-events: none; display: grid; gap: 3px; min-width: 210px; max-width: 300px;
  padding: 9px 11px; border-radius: 10px; background: var(--tooltip); border: 1px solid var(--garis);
  box-shadow: 0 12px 30px rgba(0, 0, 0, .35); font-size: 12.5px; color: var(--teks-2);
}
.tip b { display: flex; align-items: center; gap: 7px; color: var(--teks); font-weight: 600; }
.tip i { width: 9px; height: 9px; border-radius: 3px; flex: none; }
.tip .alur { display: flex; gap: 10px; }
.tip .alur strong { margin-left: auto; color: var(--teks); font-variant-numeric: tabular-nums; }
.legenda-tahap { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 12.5px; color: var(--teks-2); }
.legenda-tahap li { display: inline-flex; align-items: baseline; gap: 6px; cursor: default; }
.legenda-tahap li.nol { opacity: .7; }
.legenda-tahap li.sorot span { color: var(--teks-kuat); }
.legenda-tahap i { align-self: center; width: 10px; height: 10px; border-radius: 3px; flex: none; }
.legenda-tahap b { color: var(--teks); font-variant-numeric: tabular-nums; }
.legenda-tahap small { font-size: 11.5px; }
.ket-ringkas { display: block; margin: 3px 0 0; font-size: 11.5px; }
</style>
