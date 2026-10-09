<script setup>
// Markdown ringan untuk teks keluaran Claude: baris "- " jadi daftar berpoin, `kode` jadi <code>, baris lain paragraf.
// Dirender lewat template (tanpa v-html) supaya isi laporan tidak bisa menyisipkan HTML.
import { computed } from 'vue'

const props = defineProps({ teks: { type: String, default: '' } })

const potongKode = (s) => s.split(/(`[^`\n]+`)/).filter(Boolean)
  .map((x) => (x.length > 2 && x.startsWith('`') && x.endsWith('`') ? { kode: true, t: x.slice(1, -1) } : { kode: false, t: x }))

const blok = computed(() => {
  const hasil = []
  for (const baris of (props.teks || '').split('\n')) {
    const poin = baris.match(/^\s*[-•*]\s+(.*)$/)
    if (poin) {
      const akhir = hasil[hasil.length - 1]
      if (akhir?.jenis === 'daftar') akhir.isi.push(potongKode(poin[1]))
      else hasil.push({ jenis: 'daftar', isi: [potongKode(poin[1])] })
    } else if (baris.trim()) {
      hasil.push({ jenis: 'paragraf', isi: potongKode(baris.trim()) })
    }
  }
  return hasil
})
</script>

<template>
  <div class="teks-ringan">
  <template v-for="(b, i) in blok" :key="i">
    <ul v-if="b.jenis === 'daftar'" class="teks-poin">
      <li v-for="(p, j) in b.isi" :key="j"><template v-for="(x, k) in p" :key="k"><code v-if="x.kode">{{ x.t }}</code><template v-else>{{ x.t }}</template></template></li>
    </ul>
    <p v-else><template v-for="(x, k) in b.isi" :key="k"><code v-if="x.kode">{{ x.t }}</code><template v-else>{{ x.t }}</template></template></p>
  </template>
  </div>
</template>

<style scoped>
.teks-ringan { margin-top: 4px; color: var(--teks-2); font-size: 13.5px; }
.teks-ringan > p { margin: 4px 0 0; }
.teks-ringan > p:first-child { margin-top: 0; }
.teks-poin { margin: 4px 0 0; padding-left: 18px; display: grid; gap: 2px; }
.teks-poin li::marker { color: var(--teks-3); }
code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .92em; padding: 1px 5px; border-radius: 5px; background: var(--kartu-2); color: var(--teks); overflow-wrap: anywhere; }
</style>
