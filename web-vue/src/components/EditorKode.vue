<script setup>
// Editor kode Monaco (mesin VS Code) untuk menyunting berkas teks. Monaco ±4 MB, jadi dimuat terpisah
// (import dinamis) hanya saat editor pertama kali dibuka; halaman lain tidak ikut berat.
// Bahasa ditebak dari nama berkas; tema mengikuti terang/gelap dashboard.
import { ref, watch, onMounted, onBeforeUnmount, shallowRef } from 'vue'
import { tema } from '../tema.js'

const props = defineProps({ modelValue: { type: String, default: '' }, nama: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue', 'simpan'])
const wadah = ref(null)
const galat = ref('')
const memuat = ref(true)
const ed = shallowRef(null)
let monaco = null

async function muatMonaco() {
  if (window.__monaco) return window.__monaco
  const [m, EditorWorker, JsonWorker, CssWorker, HtmlWorker, TsWorker] = await Promise.all([
    import('monaco-editor'),
    import('monaco-editor/editor/editor.worker?worker'),
    import('monaco-editor/language/json/json.worker?worker'),
    import('monaco-editor/language/css/css.worker?worker'),
    import('monaco-editor/language/html/html.worker?worker'),
    import('monaco-editor/language/typescript/ts.worker?worker'),
  ])
  self.MonacoEnvironment = {
    getWorker(_, label) {
      if (label === 'json') return new JsonWorker.default()
      if (['css', 'scss', 'less'].includes(label)) return new CssWorker.default()
      if (['html', 'handlebars', 'razor'].includes(label)) return new HtmlWorker.default()
      if (['typescript', 'javascript'].includes(label)) return new TsWorker.default()
      return new EditorWorker.default()
    },
  }
  window.__monaco = m
  return m
}

// Nama berkas tanpa ekstensi yang umum di server (Dockerfile, .env, nginx.conf sudah lewat ekstensi .conf → tidak dikenal)
const NAMA_KHUSUS = { dockerfile: 'dockerfile', makefile: 'plaintext', '.env': 'ini', '.htaccess': 'ini', 'nginx.conf': 'ini' }
const EKS_TAMBAHAN = { conf: 'ini', cnf: 'ini', service: 'ini', timer: 'ini', env: 'ini', vue: 'html', blade: 'php', log: 'plaintext' }
function bahasa(path) {
  const nama = path.split('/').pop().toLowerCase()
  if (NAMA_KHUSUS[nama]) return NAMA_KHUSUS[nama]
  for (const l of monaco.languages.getLanguages()) {
    if (l.filenames?.some((f) => f.toLowerCase() === nama)) return l.id
    if (l.extensions?.some((e) => nama.endsWith(e.toLowerCase()))) return l.id
  }
  const eks = nama.includes('.') ? nama.split('.').pop() : ''
  return EKS_TAMBAHAN[eks] || 'plaintext'
}
const temaMonaco = () => (tema.value === 'light' ? 'vs' : 'vs-dark')

onMounted(async () => {
  try {
    monaco = await muatMonaco()
  } catch (e) {
    galat.value = `Editor gagal dimuat: ${e.message}`
    memuat.value = false
    return
  }
  memuat.value = false
  if (!wadah.value) return // dialog sudah ditutup selagi memuat
  const e = monaco.editor.create(wadah.value, {
    value: props.modelValue,
    language: bahasa(props.nama),
    theme: temaMonaco(),
    automaticLayout: true,
    fontSize: 13,
    fontFamily: 'ui-monospace, SFMono-Regular, Consolas, monospace',
    minimap: { enabled: true },
    scrollBeyondLastLine: false,
    renderWhitespace: 'selection',
    tabSize: 4,
    detectIndentation: true,
    wordWrap: 'off',
    ariaLabel: `Isi ${props.nama}`,
  })
  e.onDidChangeModelContent(() => emit('update:modelValue', e.getValue()))
  e.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => emit('simpan'))
  ed.value = e
  e.focus()
})

// Isi diganti dari luar (mis. dibuka ulang) → setel ke model tanpa memicu putaran balik
watch(() => props.modelValue, (v) => { if (ed.value && v !== ed.value.getValue()) ed.value.setValue(v) })
watch(tema, () => monaco?.editor.setTheme(temaMonaco()))
onBeforeUnmount(() => {
  // editor dulu, baru modelnya; urutan terbalik memicu galat "Model is disposed"
  const model = ed.value?.getModel()
  ed.value?.dispose()
  model?.dispose()
})

// Tombol yang sudah dipakai Monaco (Esc tutup kotak cari/saran, Tab indentasi) jangan diteruskan ke dialog,
// supaya dialog tidak ikut tertutup / fokus tidak melompat. Esc biasa tetap menutup dialog.
function tombol(ev) {
  if (ev.defaultPrevented) ev.stopPropagation()
}
</script>

<template>
  <div class="editor-kode" @keydown="tombol">
    <p v-if="memuat" class="redup status">Memuat editor…</p>
    <p v-if="galat" class="pesan-status bahaya" role="alert">{{ galat }}</p>
    <div ref="wadah" class="wadah" />
  </div>
</template>

<style scoped>
.editor-kode { position: relative; height: 66vh; min-height: 320px; border: 1px solid var(--garis); border-radius: 10px; overflow: hidden; }
.wadah { position: absolute; inset: 0; }
.status { position: absolute; inset: 0; display: grid; place-items: center; margin: 0; z-index: 1; }
</style>
