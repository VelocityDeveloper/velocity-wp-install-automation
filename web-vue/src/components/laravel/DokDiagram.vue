<script setup>
// Pratinjau dokumen Markdown berisi blok ```mermaid (DATABASE.md = ERD, FLOWCHART.md = alur proses).
// Mermaid & marked dimuat saat dibutuhkan saja (chunk terpisah). Diagram yang galat sintaks ditampilkan
// pesannya supaya PM tahu harus menyunting atau menyusun ulang.
import { ref, watch, nextTick, onMounted } from 'vue'
import Dialog from '../Dialog.vue'
import DiagramZoom from './DiagramZoom.vue'

const props = defineProps({ md: { type: String, default: '' } })
const wadah = ref(null)
const html = ref('')
const diagram = ref([])   // [{ svg, galat, kode, judul }]
const besar = ref(null)

let mermaid = null
async function muatMermaid() {
  if (mermaid) return mermaid
  mermaid = (await import('mermaid')).default
  mermaid.initialize({
    startOnLoad: false, securityLevel: 'strict', theme: 'base',
    fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif',
    themeVariables: {
      darkMode: true, background: '#151a33', primaryColor: '#1b2140', primaryTextColor: '#e8eaf6',
      primaryBorderColor: '#5b8cff', secondaryColor: '#12162b', tertiaryColor: '#0f1224', lineColor: '#8a91b8',
      textColor: '#e8eaf6', mainBkg: '#1b2140', nodeBorder: '#5b8cff', clusterBkg: '#12162b', clusterBorder: '#3a4478',
      edgeLabelBackground: '#151a33', attributeBackgroundColorOdd: '#171c36', attributeBackgroundColorEven: '#1d2344',
      fontSize: '14px',
    },
    er: { useMaxWidth: false }, flowchart: { useMaxWidth: false, htmlLabels: true },
  })
  return mermaid
}

let putaran = 0
// Kunci figure ikut putaran: node lama sudah dipindah pasang() ke dalam v-html, jadi harus dibuat baru tiap render
const versi = ref(0)
async function render() {
  const ini = ++putaran
  const [{ marked }, { default: DOMPurify }] = await Promise.all([import('marked'), import('dompurify')])
  const blok = []
  // Blok mermaid diganti penanda; sisanya Markdown biasa (disaring DOMPurify)
  const teks = props.md.replace(/```mermaid\s*\n([\s\S]*?)```/g, (_, kode) => `\n\n<div data-diagram="${blok.push(kode.trim()) - 1}" class="menunggu">Merender diagram…</div>\n\n`)
  html.value = DOMPurify.sanitize(marked.parse(teks), { ADD_ATTR: ['data-diagram'] })
  diagram.value = blok.map((kode) => ({ kode, svg: '', galat: '' }))
  versi.value = ini
  if (!blok.length) return
  const m = await muatMermaid()
  for (let i = 0; i < blok.length; i++) {
    try {
      const { svg } = await m.render(`dg-${ini}-${i}-${Math.random().toString(36).slice(2, 7)}`, blok[i])
      if (ini !== putaran) return
      diagram.value[i].svg = svg
    } catch (e) {
      if (ini !== putaran) return
      diagram.value[i].galat = String(e?.message || e).split('\n').slice(0, 6).join('\n')
    }
    // Tampilkan tiap diagram begitu jadi, tidak menunggu semuanya
    await nextTick()
    pasang()
  }
}
// Pindahkan tiap diagram ke posisi penandanya di dokumen
function pasang() {
  if (!wadah.value) return
  wadah.value.querySelectorAll('[data-diagram]').forEach((el) => {
    const d = diagram.value[Number(el.dataset.diagram)]
    const sumber = document.getElementById(`sumber-dg-${el.dataset.diagram}`)
    if (d && sumber && (d.svg || d.galat)) { el.replaceChildren(sumber); el.classList.remove('menunggu') }
  })
}
watch(() => props.md, render)
onMounted(render)
const jumlahGalat = () => diagram.value.filter((d) => d.galat).length
</script>

<template>
  <div class="dok">
    <p v-if="!md.trim()" class="redup">Belum ada isi.</p>
    <p v-else-if="jumlahGalat()" class="pesan-status bahaya">{{ jumlahGalat() }} diagram gagal dirender — cek pesan di diagram tsb, sunting sintaksnya atau susun ulang dengan Claude.</p>
    <div ref="wadah" class="md-isi" v-html="html" />
    <!-- Sumber diagram (dipindah ke penanda oleh pasang()) -->
    <div hidden>
      <figure v-for="(d, i) in diagram" :id="`sumber-dg-${i}`" :key="`${versi}-${i}`" class="diagram">
        <DiagramZoom v-if="d.svg" :svg="d.svg" tinggi="70vh" @layar-penuh="besar = d" />
        <pre v-else-if="d.galat" class="galat">Galat Mermaid:
{{ d.galat }}</pre>
        <p v-else class="redup">Merender diagram…</p>
      </figure>
    </div>
    <Dialog :buka="!!besar" judul="Diagram" lebar="96vw" @tutup="besar = null">
      <DiagramZoom v-if="besar" :svg="besar.svg" tinggi="78vh" dalam-dialog />
    </Dialog>
  </div>
</template>

<style scoped>
.dok { display: grid; gap: 12px; }
.md-isi { font-size: 14px; line-height: 1.65; color: var(--teks-2); min-width: 0; }
.md-isi :deep(h1) { font-size: 20px; color: var(--teks); margin: 4px 0 10px; }
.md-isi :deep(h2) { font-size: 17px; color: var(--teks); margin: 22px 0 8px; padding-top: 12px; border-top: 1px solid var(--garis); }
.md-isi :deep(h3) { font-size: 15px; color: var(--teks); margin: 16px 0 6px; }
.md-isi :deep(p) { margin: 6px 0; }
.md-isi :deep(ul), .md-isi :deep(ol) { padding-left: 20px; margin: 6px 0; }
.md-isi :deep(code) { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); background: var(--kartu-2); padding: 1px 5px; border-radius: 5px; }
.md-isi :deep(table) { width: 100%; border-collapse: collapse; font-size: 13px; margin: 8px 0; display: block; overflow-x: auto; }
.md-isi :deep(th), .md-isi :deep(td) { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--garis); vertical-align: top; }
.md-isi :deep(th) { color: var(--teks-3); font-weight: 600; font-size: 12px; white-space: nowrap; }
.md-isi :deep(strong) { color: var(--teks); }
.diagram { position: relative; margin: 10px 0; padding: 14px; border-radius: 12px; background: var(--kartu-2); border: 1px solid var(--garis); }
.md-isi :deep(.menunggu) { padding: 18px; border-radius: 12px; background: var(--kartu-2); color: var(--teks-3); font-size: 13px; }
.galat { margin: 0; white-space: pre-wrap; color: var(--bahaya); font: 12px/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; }
</style>
