<script setup>
// Batang mendatar (satu sumbu, mulai dari 0) untuk perbandingan antarkategori: satu seri atau bertumpuk.
// Celah 2px antar-segmen, ujung kanan membulat 4px, garis acuan opsional (mis. rata-rata), tooltip per baris
// saat kursor/fokus keyboard. Label nilai di ujung batang memakai warna teks, bukan warna seri.
import { ref, computed } from 'vue'

const props = defineProps({
  baris: { type: Array, required: true }, // [{ kunci, label, nilai: { seri: angka }, lencana?: [kelas, teks], rincian?: [[label, teks]] }]
  seri: { type: Array, required: true }, // [{ kunci, label, warna }]
  format: { type: Function, default: (v) => String(v) },
  acuan: { type: Object, default: null }, // { nilai, label }
  judul: { type: String, required: true },
  bisaPilih: { type: Boolean, default: false }, // baris bisa diklik/Enter → emit('pilih', kunci)
  terpilih: { type: String, default: '' },
})
const emit = defineEmits(['pilih'])

const aktif = ref(null)
const total = (b) => props.seri.reduce((a, s) => a + (b.nilai[s.kunci] || 0), 0)
const puncak = computed(() => Math.max(1, props.acuan?.nilai || 0, ...props.baris.map(total)))
const persen = (v) => `${(v / puncak.value) * 100}%`
const isi = (b) => props.seri.map((s) => ({ ...s, v: b.nilai[s.kunci] || 0 })).filter((s) => s.v > 0)
const aria = (b) => `${b.label}: ${props.format(total(b))}` + (props.seri.length > 1 ? ` (${isi(b).map((s) => `${s.label} ${props.format(s.v)}`).join(', ')})` : '')
  + (b.rincian || []).map(([l, t]) => `, ${l} ${t}`).join('')
</script>

<template>
  <div class="batang-mendatar">
    <ul v-if="seri.length > 1" class="legenda" aria-hidden="true">
      <li v-for="s in seri" :key="s.kunci"><i :style="{ background: s.warna }" />{{ s.label }}</li>
    </ul>
    <ul class="baris-daftar" :aria-label="judul">
      <li
        v-for="b in baris" :key="b.kunci" class="baris" :class="{ klik: bisaPilih, terpilih: terpilih === b.kunci }" tabindex="0" :aria-label="aria(b)"
        :role="bisaPilih ? 'button' : undefined" :aria-pressed="bisaPilih ? terpilih === b.kunci : undefined"
        @click="bisaPilih && emit('pilih', b.kunci)" @keydown.enter.space.prevent="bisaPilih && emit('pilih', b.kunci)"
        @mouseenter="aktif = b.kunci" @mouseleave="aktif = null" @focus="aktif = b.kunci" @blur="aktif = null"
      >
        <span class="label">
          {{ b.label }}
          <span v-if="b.lencana" class="lencana" :class="b.lencana[0]">{{ b.lencana[1] }}</span>
        </span>
        <span class="jalur">
          <span class="trek">
            <span class="isi" :style="{ width: persen(total(b)) }">
              <span v-for="s in isi(b)" :key="s.kunci" class="seg" :style="{ flexGrow: s.v, background: s.warna }" />
            </span>
            <span v-if="acuan" class="acuan" :style="{ left: persen(acuan.nilai) }" aria-hidden="true" />
          </span>
          <b class="nilai">{{ format(total(b)) }}</b>
        </span>
        <span v-if="aktif === b.kunci" class="tip" aria-hidden="true">
          <b>{{ b.label }} · {{ format(total(b)) }}</b>
          <span v-for="s in seri.length > 1 ? isi(b) : []" :key="s.kunci"><i :style="{ background: s.warna }" />{{ s.label }} <strong>{{ format(s.v) }}</strong></span>
          <span v-for="r in b.rincian || []" :key="r[0]">{{ r[0] }} <strong>{{ r[1] }}</strong></span>
        </span>
      </li>
    </ul>
    <p v-if="acuan" class="acuan-ket" aria-hidden="true"><i /> {{ acuan.label }}: {{ format(acuan.nilai) }}</p>
  </div>
</template>

<style scoped>
.batang-mendatar { display: grid; gap: 10px; }
.legenda { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 14px; font-size: 12.5px; color: var(--teks-2); }
.legenda li { display: flex; align-items: center; gap: 6px; }
.legenda i, .tip i { width: 10px; height: 10px; border-radius: 3px; flex: none; }
.baris-daftar { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
.baris { position: relative; display: grid; grid-template-columns: minmax(96px, 30%) minmax(0, 1fr); gap: 12px; align-items: center; padding: 5px 6px; border-radius: 8px; outline: none; }
.baris:hover, .baris:focus-visible { background: var(--sorot); }
.baris.klik { cursor: pointer; }
.baris.terpilih { background: var(--aksen-lembut); }
.baris:focus-visible { box-shadow: 0 0 0 2px var(--aksen-terang); }
.label { font-size: 13px; color: var(--teks); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.label .lencana { margin-left: 4px; }
.jalur { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 10px; height: 22px; }
.trek { position: relative; height: 14px; }
.isi { display: flex; gap: 2px; height: 14px; }
.isi:empty { width: 0 !important; }
.seg { min-width: 3px; height: 100%; }
.seg:last-child { border-radius: 0 4px 4px 0; }
.nilai { min-width: 44px; text-align: right; font-size: 12.5px; font-weight: 600; color: var(--teks-2); font-variant-numeric: tabular-nums; white-space: nowrap; }
.acuan { position: absolute; top: -2px; bottom: -2px; width: 0; border-left: 1.5px dashed var(--silang); pointer-events: none; }
.acuan-ket { margin: 0; font-size: 12px; color: var(--teks-3); display: flex; align-items: center; gap: 6px; }
.acuan-ket i { width: 14px; border-top: 1.5px dashed var(--silang); }
.tip {
  position: absolute; z-index: 3; left: 30%; top: calc(100% + 2px); pointer-events: none; display: grid; gap: 3px; min-width: 200px;
  padding: 10px 12px; border-radius: 10px; background: var(--tooltip); border: 1px solid var(--garis);
  box-shadow: 0 12px 30px rgba(0, 0, 0, .35); font-size: 12.5px; color: var(--teks-2);
}
.tip b { color: var(--teks); font-weight: 600; }
.tip span { display: flex; align-items: center; gap: 7px; }
.tip strong { margin-left: auto; padding-left: 12px; color: var(--teks); font-variant-numeric: tabular-nums; }
</style>
