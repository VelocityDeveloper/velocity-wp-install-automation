<script setup>
// Satu tempat untuk semua pertanyaan ke klien (7 Okt): "Pertanyaan terbuka" di PRD.md, "belum jelas" di Rangkuman,
// dan "Tanyakan ke klien" di Saran platform. Isinya banyak yang mirip antar sumber, jadi sumber pertama yang ada
// (PRD → Rangkuman → Saran) jadi daftar utama; sumber lain dilipat. PM mencentang yang sudah dijawab (aksi `tanya`,
// tersimpan di server per teks pertanyaan) dan menyalin daftar utama yang belum dijawab untuk dikirim lewat WA.
import { ref, computed, watch } from 'vue'
import { aksi, pesanGalat, namaSaya } from '../../laravel.js'

const props = defineProps({ d: { type: Object, required: true } })

const rapikan = (t) => String(t || '').split(/\s+/).join(' ').trim()
const kunciDari = (t) => rapikan(t).slice(0, 300)

// Butir di bawah "## Pertanyaan terbuka" PRD.md sampai judul berikutnya
function dariPrd(md) {
  const m = /^##\s*Pertanyaan terbuka[^\n]*\n([\s\S]*?)(?=^#{1,2}\s|(?![\s\S]))/im.exec(md || '')
  if (!m) return []
  return m[1].split('\n').map((x) => x.match(/^\s*(?:[-*]|\d+[.)])\s+(.*)/)?.[1]).filter(Boolean).map(rapikan)
}

const SUMBER = computed(() => [
  { kunci: 'prd', label: 'PRD.md', isi: dariPrd(props.d.prd) },
  { kunci: 'rangkuman', label: 'Rangkuman', isi: (props.d.rangkuman?.belum_jelas || []).map(rapikan) },
  { kunci: 'saran', label: 'Saran platform', isi: (props.d.saran?.pertanyaan_klien || []).map(rapikan) },
].filter((s) => s.isi.length))

// Teks sama persis dari sumber berbeda cukup tampil sekali (di sumber pertama)
const kelompok = computed(() => {
  const ada = new Set()
  return SUMBER.value.map((s) => ({ ...s, isi: s.isi.filter((q) => !ada.has(kunciDari(q)) && ada.add(kunciDari(q))) }))
    .filter((s) => s.isi.length)
})

const dijawab = ref(new Set(props.d.pertanyaan_dijawab || []))
watch(() => props.d.pertanyaan_dijawab, (v) => { dijawab.value = new Set(v || []) })
const semua = computed(() => kelompok.value.flatMap((s) => s.isi))
const utama = computed(() => kelompok.value[0])
const belumDari = (isi) => isi.filter((q) => !dijawab.value.has(kunciDari(q)))
const belum = computed(() => belumDari(utama.value?.isi || []))
const sembunyikan = ref(false)
const status = ref({ kelas: '', teks: '' })
const bisaUbah = computed(() => !!namaSaya.value.trim() && (props.d.status_proyek || 'aktif') === 'aktif')

async function tandai(q, nilai) {
  const k = kunciDari(q)
  const lama = new Set(dijawab.value)
  const baru = new Set(lama)
  nilai ? baru.add(k) : baru.delete(k)
  dijawab.value = baru
  status.value = { kelas: '', teks: '' }
  try { await aksi(props.d.slug, 'tanya', { kunci: k, dijawab: nilai }) } catch (e) {
    dijawab.value = lama
    status.value = { kelas: 'bahaya', teks: pesanGalat(e) }
  }
}

// navigator.clipboard hanya ada di konteks aman (https/localhost); dashboard dibuka lewat http LAN → cadangan execCommand
async function salinTeks(teks) {
  try { await navigator.clipboard.writeText(teks); return true } catch {}
  const t = Object.assign(document.createElement('textarea'), { value: teks })
  t.style.cssText = 'position:fixed;opacity:0'
  document.body.appendChild(t)
  t.select()
  const ok = document.execCommand('copy')
  t.remove()
  return ok
}
const tersalin = ref(false)
async function salin() {
  const teks = `Beberapa hal yang perlu kami konfirmasi untuk ${props.d.judul}:\n\n`
    + belum.value.map((q, i) => `${i + 1}. ${q}`).join('\n')
  if (!(await salinTeks(teks))) { status.value = { kelas: 'bahaya', teks: 'Gagal menyalin. Pilih teks secara manual.' }; return }
  tersalin.value = true
  setTimeout(() => { tersalin.value = false }, 1800)
}
</script>

<template>
  <section v-if="semua.length" id="pertanyaan-klien" class="kartu" aria-labelledby="h-tanya">
    <div class="kartu-judul">
      <h2 id="h-tanya">Pertanyaan untuk klien</h2>
      <span class="pil" :class="belum.length ? 'waspada' : 'baik'">{{ belum.length ? `${belum.length} belum dijawab` : 'daftar utama sudah dijawab' }}</span>
      <div class="kanan">
        <label v-if="dijawab.size" class="redup sembunyi"><input v-model="sembunyikan" type="checkbox"> Sembunyikan yang sudah dijawab</label>
        <button type="button" class="tombol kecil" :disabled="!belum.length" @click="salin">{{ tersalin ? 'Tersalin ✓' : `Salin untuk WA (${belum.length})` }}</button>
      </div>
    </div>
    <p class="redup bantu">Centang setelah klien menjawab, lalu tambahkan jawabannya ke Catatan diskusi dan susun ulang dokumen yang terkait. "Salin untuk WA" menyalin daftar utama yang belum dijawab.</p>
    <component :is="i ? 'details' : 'div'" v-for="(s, i) in kelompok" :key="s.kunci" class="sumber">
      <component :is="i ? 'summary' : 'p'" class="label-sumber">Dari {{ s.label }}<span v-if="i" class="ket-sumber"> · {{ belumDari(s.isi).length }}/{{ s.isi.length }} belum dijawab, sebagian mirip daftar utama</span></component>
      <ul>
        <template v-for="q in s.isi" :key="q">
          <li v-if="!(sembunyikan && dijawab.has(kunciDari(q)))" :class="{ selesai: dijawab.has(kunciDari(q)) }">
            <label>
              <input type="checkbox" :checked="dijawab.has(kunciDari(q))" :disabled="!bisaUbah" @change="tandai(q, $event.target.checked)">
              <span>{{ q }}</span>
            </label>
          </li>
        </template>
      </ul>
    </component>
    <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
  </section>
</template>

<style scoped>
.bantu { margin: -6px 0 12px; font-size: 13px; }
.kanan { margin-left: auto; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.sembunyi { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; cursor: pointer; }
.sumber + .sumber { margin-top: 12px; }
details.sumber .ket-sumber { text-transform: none; letter-spacing: 0; font-weight: 500; }
details.sumber { padding: 8px 10px; border-radius: 10px; background: var(--kartu-2); }
details.sumber .label-sumber { margin: 0; cursor: pointer; }
details.sumber[open] .label-sumber { margin-bottom: 6px; }
.label-sumber { margin: 0 0 6px; cursor: default; font-size: 11.5px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: var(--teks-3); }
ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 2px; }
li label { display: flex; gap: 10px; align-items: flex-start; padding: 6px 8px; border-radius: 8px; cursor: pointer; font-size: 13.5px; color: var(--teks-2); }
li label:hover { background: var(--kartu-2); }
li input { margin-top: 3px; flex: none; accent-color: var(--aksen); }
li.selesai span { text-decoration: line-through; color: var(--teks-3); }
.pesan-status { margin: 10px 0 0; }
</style>
