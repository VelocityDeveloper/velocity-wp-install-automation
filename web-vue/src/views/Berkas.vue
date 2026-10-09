<script setup>
// File Manager seluruh sistem (/) — pengganti File Browser (/files/). API: services/file_manager.py (/api/fm/*, port 9123).
// Tanpa login: nginx membatasi ke LAN/Tailscale; aksi ubah berkas hanya diterima dari halaman ini (Origin = Host).
// Folder aktif disimpan di ?path= supaya tombol Kembali browser & tautan langsung berfungsi.
import { ref, reactive, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import EditorKode from '../components/EditorKode.vue'
import { konfirmasi } from '../konfirmasi.js'
import { kirim, minta, ukuranBerkas, tanggalWaktu } from '../api.js'

const route = useRoute()
const router = useRouter()
const folder = computed(() => (typeof route.query.path === 'string' && route.query.path.startsWith('/') ? route.query.path : '/'))
const gabung = (a, b) => (a === '/' ? '' : a) + '/' + b
const induk = (p) => p.replace(/\/[^/]+$/, '') || '/'

const PESAN = {
  forbidden: 'Hanya bisa dari jaringan kantor/Tailscale lewat halaman dashboard.',
  tidak_ditemukan: 'Tidak ditemukan.',
  izin_ditolak: 'Izin ditolak oleh sistem.',
  bukan_folder: 'Bukan folder.',
  bukan_berkas: 'Bukan berkas biasa.',
  berkas_terlalu_besar: 'Berkas lebih dari 5 MB, tidak bisa dibuka di editor. Unduh saja.',
  berkas_biner: 'Berkas biner, tidak bisa dibuka sebagai teks.',
  berkas_berubah: 'Berkas sudah diubah pihak lain sejak dibuka.',
  sudah_ada: 'Nama itu sudah ada di tujuan.',
  dilindungi: 'Folder tingkat atas (mis. /etc, /usr, /home) tidak boleh dihapus, dipindah, atau diganti nama.',
  nama_tidak_valid: 'Nama tidak valid (tanpa "/", bukan "." atau "..").',
  path_tidak_valid: 'Path harus diawali "/".',
  tujuan_bukan_folder: 'Tujuan bukan folder yang ada.',
  tujuan_di_dalam_sumber: 'Tujuan tidak boleh di dalam folder sumber itu sendiri.',
  zip_tidak_aman: 'Zip berisi path keluar folder tujuan, ekstrak dibatalkan.',
  zip_rusak: 'Berkas zip rusak atau bukan zip.',
  mode_tidak_valid: 'Izin harus angka oktal, mis. 644 atau 755.',
  kata_kosong: 'Isi kata yang dicari.',
}
const pesan = (e) => PESAN[e.message] || e.message

// ---- daftar isi folder ----
const data = ref(null)
const galat = ref('')
const memuat = ref(false)
const tersembunyi = ref(true)
const cari = ref('')
const urut = reactive({ kunci: 'nama', naik: true })
const pilih = ref(new Set())
const alamat = ref('/')

async function muat() {
  memuat.value = true
  try {
    data.value = await minta(`/api/fm/daftar?path=${encodeURIComponent(folder.value)}`)
    galat.value = ''
  } catch (e) {
    galat.value = pesan(e)
    if (data.value?.path !== folder.value) data.value = null
  } finally {
    memuat.value = false
  }
}
const buka = (p) => router.push({ query: { path: p } })

const entri = computed(() => {
  let d = data.value?.entri || []
  if (!tersembunyi.value) d = d.filter((e) => !e.nama.startsWith('.'))
  const c = cari.value.trim().toLowerCase()
  if (c) d = d.filter((e) => e.nama.toLowerCase().includes(c))
  const k = urut.kunci
  const arah = urut.naik ? 1 : -1
  return [...d].sort((a, b) => {
    if ((a.jenis === 'folder') !== (b.jenis === 'folder')) return a.jenis === 'folder' ? -1 : 1
    const x = a[k] ?? -1
    const y = b[k] ?? -1
    return (typeof x === 'string' ? x.localeCompare(y, 'id', { sensitivity: 'base' }) : x - y) * arah
  })
})
function ubahUrut(k) {
  if (urut.kunci === k) urut.naik = !urut.naik
  else Object.assign(urut, { kunci: k, naik: k === 'nama' })
}
const ariaUrut = (k) => (urut.kunci === k ? (urut.naik ? 'ascending' : 'descending') : 'none')

const remah = computed(() => {
  const bagian = folder.value.split('/').filter(Boolean)
  return [{ nama: '/', path: '/' }, ...bagian.map((n, i) => ({ nama: n, path: '/' + bagian.slice(0, i + 1).join('/') }))]
})
function keAlamat() {
  const p = alamat.value.trim()
  if (p.startsWith('/')) buka(p.replace(/\/+$/, '') || '/')
}

// ---- cari di folder ini & seluruh subfolder (GET /api/fm/cari, maks 500 hasil / 15 detik) ----
const pencarian = reactive({ kata: '', jenis: 'semua', hasil: null, memuat: false, galat: '' })
let nomorCari = 0
async function jalankanCari() {
  const kata = pencarian.kata.trim()
  if (!kata) return
  const nomor = ++nomorCari
  Object.assign(pencarian, { memuat: true, galat: '' })
  try {
    const r = await minta(`/api/fm/cari?path=${encodeURIComponent(folder.value)}&q=${encodeURIComponent(kata)}&jenis=${pencarian.jenis}&tersembunyi=${tersembunyi.value ? 1 : 0}`)
    if (nomor === nomorCari) pencarian.hasil = r
  } catch (e) {
    if (nomor === nomorCari) pencarian.galat = pesan(e)
  } finally {
    if (nomor === nomorCari) pencarian.memuat = false
  }
}
function tutupCari() {
  nomorCari++
  Object.assign(pencarian, { hasil: null, memuat: false, galat: '' })
}
const modeCari = computed(() => !!(pencarian.hasil || pencarian.memuat || pencarian.galat))
watch(folder, () => { pilih.value = new Set(); cari.value = ''; alamat.value = folder.value; tutupCari(); muat() }, { immediate: true })
// path relatif terhadap folder tempat mencari, supaya kolom nama tidak penuh awalan yang sama
const relatif = (p) => (folder.value === '/' ? p.slice(1) : p.slice(folder.value.length + 1))
function klikHasil(h) {
  if (h.jenis === 'folder') return buka(h.path)
  klikEntri({ ...h, nama: relatif(h.path) })
}

// ---- pilihan ----
const terpilih = computed(() => entri.value.filter((e) => pilih.value.has(e.nama)))
const semuaTerpilih = computed(() => entri.value.length > 0 && terpilih.value.length === entri.value.length)
function togglePilih(nama) {
  const s = new Set(pilih.value)
  s.has(nama) ? s.delete(nama) : s.add(nama)
  pilih.value = s
}
function togglSemua() {
  pilih.value = semuaTerpilih.value ? new Set() : new Set(entri.value.map((e) => e.nama))
}
const pathTerpilih = () => terpilih.value.map((e) => gabung(folder.value, e.nama))
const satu = computed(() => (terpilih.value.length === 1 ? terpilih.value[0] : null))

// ---- membuka berkas ----
const EKS_LIHAT = /\.(png|jpe?g|gif|webp|avif|bmp|ico|pdf|mp4|webm|mp3|ogg|wav)$/i
const EKS_BINER = /\.(zip|gz|tgz|tar|bz2|xz|7z|rar|iso|img|bin|so|o|exe|dll|woff2?|ttf|otf|eot|sqlite|db|mo|jar|class|pyc)$/i
const urlUnduh = (p, lihat) => `/api/fm/unduh?path=${encodeURIComponent(p)}${lihat ? '&lihat=1' : ''}`
function unduh(p) {
  const a = document.createElement('a')
  a.href = urlUnduh(p)
  a.download = ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}
function klikEntri(e) {
  const p = gabung(folder.value, e.nama)
  if (e.jenis === 'folder') return buka(p)
  if (e.jenis !== 'berkas') return
  if (EKS_LIHAT.test(e.nama)) return window.open(urlUnduh(p, true), '_blank', 'noopener')
  if (EKS_BINER.test(e.nama)) return unduh(p)
  bukaEditor(p)
}

// ---- editor teks ----
const editor = reactive({ buka: false, path: '', isi: '', asli: '', waktu: null, memuat: false, proses: false, galat: '' })
const berubah = computed(() => editor.isi !== editor.asli)
async function bukaEditor(p) {
  Object.assign(editor, { buka: true, path: p, isi: '', asli: '', waktu: null, memuat: true, proses: false, galat: '' })
  try {
    const r = await minta(`/api/fm/baca?path=${encodeURIComponent(p)}`)
    Object.assign(editor, { isi: r.isi, asli: r.isi, waktu: r.waktu })
  } catch (e) {
    if (e.message === 'berkas_biner' || e.message === 'berkas_terlalu_besar') {
      editor.buka = false
      if (await konfirmasi({ judul: 'Tidak bisa dibuka sebagai teks', teks: `${pesan(e)} Unduh berkasnya?`, tombol: 'Unduh' })) unduh(p)
      return
    }
    editor.galat = pesan(e)
  } finally {
    editor.memuat = false
  }
}
async function simpanEditor(paksa = false) {
  if (editor.proses || editor.memuat) return
  editor.proses = true
  editor.galat = ''
  try {
    const r = await kirim('/api/fm/tulis', { path: editor.path, isi: editor.isi, waktu: paksa ? null : editor.waktu })
    Object.assign(editor, { asli: editor.isi, waktu: r.waktu })
    muat()
  } catch (e) {
    if (e.message === 'berkas_berubah' && !paksa) {
      editor.proses = false
      if (await konfirmasi({ judul: 'Berkas berubah di server', teks: 'Berkas sudah diubah pihak lain sejak dibuka. Timpa dengan isi editor ini?', tombol: 'Timpa', kelas: 'waspada' })) return simpanEditor(true)
      return
    }
    editor.galat = pesan(e)
  } finally {
    editor.proses = false
  }
}
async function tutupEditor() {
  if (berubah.value && !(await konfirmasi({ judul: 'Buang perubahan?', teks: 'Perubahan yang belum disimpan akan hilang.', tombol: 'Buang', kelas: 'bahaya' }))) return
  editor.buka = false
}

// ---- dialog isian umum (folder/berkas baru, ganti nama, zip, izin, salin/pindah, ekstrak) ----
const isian = reactive({ buka: false, judul: '', label: '', nilai: '', petunjuk: '', tombol: 'Simpan', timpa: null, jalankan: null, galat: '', proses: false })
function tanya(opsi) {
  Object.assign(isian, { buka: true, petunjuk: '', tombol: 'Simpan', timpa: null, galat: '', proses: false, ...opsi })
}
async function kirimIsian() {
  isian.proses = true
  isian.galat = ''
  try {
    await isian.jalankan(isian.nilai.trim(), isian.timpa)
    isian.buka = false
    pilih.value = new Set()
    muat()
  } catch (e) {
    isian.galat = pesan(e)
  } finally {
    isian.proses = false
  }
}
const folderBaru = () => tanya({ judul: 'Folder baru', label: 'Nama folder', nilai: '', tombol: 'Buat', jalankan: (n) => kirim('/api/fm/buat', { path: folder.value, nama: n, jenis: 'folder' }) })
const berkasBaru = () => tanya({
  judul: 'Berkas baru', label: 'Nama berkas', nilai: '', tombol: 'Buat & buka',
  jalankan: async (n) => { await kirim('/api/fm/buat', { path: folder.value, nama: n, jenis: 'berkas' }); bukaEditor(gabung(folder.value, n)) },
})
const gantiNama = () => tanya({ judul: `Ganti nama: ${satu.value.nama}`, label: 'Nama baru', nilai: satu.value.nama, tombol: 'Ganti nama', jalankan: (n) => kirim('/api/fm/ganti-nama', { path: gabung(folder.value, satu.value.nama), nama: n }) })
const ubahIzin = () => tanya({ judul: `Izin: ${satu.value.nama}`, label: 'Izin (oktal)', nilai: satu.value.oktal || '', petunjuk: `Sekarang ${satu.value.mode} · pemilik ${satu.value.pemilik}:${satu.value.grup}. Umum: 644 berkas, 755 folder.`, tombol: 'Terapkan', jalankan: (m) => kirim('/api/fm/chmod', { path: gabung(folder.value, satu.value.nama), mode: m }) })
function salinPindah(pindah) {
  const paths = pathTerpilih()
  tanya({
    judul: `${pindah ? 'Pindah' : 'Salin'} ${paths.length} item ke…`, label: 'Folder tujuan', nilai: folder.value, tombol: pindah ? 'Pindah' : 'Salin', timpa: false,
    petunjuk: 'Berkas salinan ikut pemilik folder tujuan.',
    jalankan: (t, timpa) => kirim(`/api/fm/${pindah ? 'pindah' : 'salin'}`, { paths, tujuan: t.replace(/\/+$/, '') || '/', timpa }),
  })
}
function buatZip() {
  const paths = pathTerpilih()
  tanya({ judul: `Zip ${paths.length} item`, label: 'Nama berkas zip', nilai: (paths.length === 1 ? terpilih.value[0].nama : 'arsip') + '.zip', tombol: 'Buat zip', petunjuk: 'Disimpan di folder ini.', jalankan: (n) => kirim('/api/fm/zip', { paths, nama: n }) })
}
function ekstrak() {
  const p = gabung(folder.value, satu.value.nama)
  tanya({ judul: `Ekstrak ${satu.value.nama}`, label: 'Ekstrak ke folder', nilai: folder.value, tombol: 'Ekstrak', timpa: false, petunjuk: 'Folder dibuat bila belum ada.', jalankan: (t, timpa) => kirim('/api/fm/unzip', { path: p, tujuan: t.replace(/\/+$/, '') || '/', timpa }) })
}
async function hapus() {
  const daftar = terpilih.value
  const ada = daftar.filter((e) => e.jenis === 'folder').length
  const ok = await konfirmasi({
    judul: `Hapus ${daftar.length} item?`,
    teks: `${daftar.slice(0, 5).map((e) => e.nama).join(', ')}${daftar.length > 5 ? `, dan ${daftar.length - 5} lainnya` : ''}${ada ? ' — folder dihapus beserta seluruh isinya' : ''}. Tidak bisa dibatalkan.`,
    tombol: 'Hapus', kelas: 'bahaya',
  })
  if (!ok) return
  try {
    await kirim('/api/fm/hapus', { paths: pathTerpilih() })
    pilih.value = new Set()
  } catch (e) {
    galat.value = pesan(e)
  }
  muat()
}

// ---- unggah (satu permintaan PUT per berkas, badan = isi mentah) ----
const antrean = ref([])
const inputBerkas = ref(null)
const inputFolder = ref(null)
const seret = ref(false)
function unggahSatu(tugas, timpa) {
  return new Promise((selesai) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', `/api/fm/unggah?path=${encodeURIComponent(tugas.folder)}&nama=${encodeURIComponent(tugas.nama)}${timpa ? '&timpa=1' : ''}`)
    xhr.upload.onprogress = (ev) => { if (ev.lengthComputable) tugas.persen = Math.round((ev.loaded / ev.total) * 100) }
    xhr.onload = () => {
      let j = {}
      try { j = JSON.parse(xhr.responseText) } catch { /* bukan JSON */ }
      if (xhr.status === 200) Object.assign(tugas, { status: 'selesai', persen: 100 })
      else Object.assign(tugas, { status: 'gagal', galat: PESAN[j.error] || j.error || `HTTP ${xhr.status}` })
      selesai()
    }
    xhr.onerror = () => { Object.assign(tugas, { status: 'gagal', galat: 'Koneksi terputus' }); selesai() }
    tugas.status = 'jalan'
    xhr.send(tugas.berkas)
  })
}
async function unggah(daftar) {
  if (!daftar.length) return
  const tujuan = folder.value
  const nama = new Set((data.value?.entri || []).map((e) => e.nama))
  const bentrok = daftar.filter((d) => nama.has(d.nama.split('/')[0]))
  let timpa = false
  if (bentrok.length) {
    timpa = await konfirmasi({ judul: `${bentrok.length} nama sudah ada`, teks: `${bentrok.slice(0, 5).map((d) => d.nama.split('/')[0]).filter((v, i, a) => a.indexOf(v) === i).join(', ')} sudah ada di folder ini. Timpa?`, tombol: 'Timpa', kelas: 'waspada' })
    if (!timpa) daftar = daftar.filter((d) => !bentrok.includes(d))
  }
  const tugas = daftar.map((d) => reactive({ folder: tujuan, nama: d.nama, berkas: d.berkas, ukuran: d.berkas.size, persen: 0, status: 'antre', galat: '' }))
  antrean.value = [...antrean.value.filter((t) => t.status !== 'selesai'), ...tugas]
  for (const t of tugas) await unggahSatu(t, timpa)
  if (folder.value === tujuan) muat()
}
function pilihBerkas(ev, folderMode) {
  const daftar = [...ev.target.files].map((f) => ({ nama: folderMode ? f.webkitRelativePath : f.name, berkas: f }))
  ev.target.value = ''
  unggah(daftar)
}
// Seret-lepas: telusuri folder lewat webkitGetAsEntry
async function kumpulkan(entry, awalan, hasil) {
  if (entry.isFile) {
    const f = await new Promise((ok, gagal) => entry.file(ok, gagal))
    hasil.push({ nama: awalan + f.name, berkas: f })
  } else if (entry.isDirectory) {
    const pembaca = entry.createReader()
    let potong
    do {
      potong = await new Promise((ok, gagal) => pembaca.readEntries(ok, gagal))
      for (const e of potong) await kumpulkan(e, `${awalan}${entry.name}/`, hasil)
    } while (potong.length)
  }
}
async function lepas(ev) {
  seret.value = false
  const hasil = []
  const entri = [...ev.dataTransfer.items].map((i) => i.webkitGetAsEntry?.()).filter(Boolean)
  if (entri.length) for (const e of entri) await kumpulkan(e, '', hasil)
  else for (const f of ev.dataTransfer.files) hasil.push({ nama: f.name, berkas: f })
  unggah(hasil)
}
const unggahJalan = computed(() => antrean.value.filter((t) => t.status === 'jalan' || t.status === 'antre').length)

const ikonEntri = (e) => (e.jenis === 'folder' ? 'berkas' : e.link ? 'tautan' : 'dokumen')
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>File Manager</h1>
        <p class="redup">Seluruh sistem berkas Local PC. Hanya dari jaringan kantor/Tailscale; berkas baru ikut pemilik folder induknya.</p>
      </div>
      <p v-if="data?.disk" class="redup disk">Sisa disk {{ ukuranBerkas(data.disk.sisa) }} dari {{ ukuranBerkas(data.disk.total) }}</p>
    </header>

    <section class="kartu" :class="{ seret }" aria-label="Isi folder" @dragover.prevent="seret = true" @dragleave.self="seret = false" @drop.prevent="lepas">
      <div class="bar-alamat">
        <button type="button" class="tombol garis kecil" :disabled="folder === '/'" aria-label="Naik satu folder" @click="buka(induk(folder))"><Ikon nama="naik" :ukuran="16" /></button>
        <nav class="remah" aria-label="Lokasi">
          <template v-for="(r, i) in remah" :key="r.path">
            <span v-if="i > 1" class="pemisah" aria-hidden="true">/</span>
            <button type="button" :aria-current="r.path === folder ? 'page' : undefined" @click="buka(r.path)">{{ r.nama }}</button>
          </template>
        </nav>
        <form class="form-alamat" @submit.prevent="keAlamat">
          <input v-model="alamat" aria-label="Path folder" spellcheck="false">
          <button type="submit" class="tombol garis kecil">Buka</button>
        </form>
      </div>

      <div class="bar-alat">
        <div class="kelompok">
          <button type="button" class="tombol kecil" @click="inputBerkas.click()"><Ikon nama="unggah" :ukuran="15" /> Unggah</button>
          <button type="button" class="tombol garis kecil" @click="inputFolder.click()">Unggah folder</button>
          <button type="button" class="tombol garis kecil" @click="folderBaru"><Ikon nama="tambah" :ukuran="15" /> Folder</button>
          <button type="button" class="tombol garis kecil" @click="berkasBaru"><Ikon nama="tambah" :ukuran="15" /> Berkas</button>
          <button type="button" class="tombol garis kecil" aria-label="Muat ulang" @click="muat"><Ikon nama="ulang" :ukuran="15" /></button>
        </div>
        <div class="kelompok">
          <label class="centang"><input v-model="tersembunyi" type="checkbox"> Tampilkan tersembunyi</label>
          <input v-model="cari" class="cari" type="search" placeholder="Saring folder ini…" aria-label="Saring nama di folder ini">
        </div>
        <input ref="inputBerkas" type="file" multiple hidden @change="pilihBerkas($event, false)">
        <input ref="inputFolder" type="file" webkitdirectory hidden @change="pilihBerkas($event, true)">
      </div>

      <form class="bar-cari" role="search" @submit.prevent="jalankanCari">
        <input v-model="pencarian.kata" class="cari-dalam" type="search" :placeholder="`Cari berkas/folder di ${folder === '/' ? 'seluruh sistem' : folder} & subfolder…`" aria-label="Cari berkas atau folder di folder ini dan subfoldernya" spellcheck="false" @search="!pencarian.kata && tutupCari()">
        <select v-model="pencarian.jenis" aria-label="Jenis yang dicari">
          <option value="semua">Berkas & folder</option>
          <option value="berkas">Berkas saja</option>
          <option value="folder">Folder saja</option>
        </select>
        <button type="submit" class="tombol kecil" :disabled="pencarian.memuat || !pencarian.kata.trim()"><Ikon nama="cari" :ukuran="15" /> {{ pencarian.memuat ? 'Mencari…' : 'Cari' }}</button>
        <button v-if="modeCari" type="button" class="tombol garis kecil" @click="tutupCari">Tutup hasil</button>
      </form>

      <div v-if="modeCari" class="hasil-cari" aria-live="polite">
        <p v-if="pencarian.galat" class="pesan-status bahaya" role="alert">{{ pencarian.galat }}</p>
        <p v-else-if="pencarian.memuat && !pencarian.hasil" class="redup">Menelusuri {{ folder }}… (pencarian dari / bisa makan beberapa detik)</p>
        <template v-if="pencarian.hasil">
          <p class="redup ringkas-cari">
            <b>{{ pencarian.hasil.hasil.length }}</b> hasil untuk “{{ pencarian.hasil.kata }}” di {{ pencarian.hasil.path }}
            · {{ pencarian.hasil.diperiksa.toLocaleString('id-ID') }} item diperiksa
            <span v-if="pencarian.hasil.terpotong"> · dibatasi 500 hasil pertama, persempit kata/folder</span>
            <span v-if="pencarian.hasil.habis_waktu"> · berhenti setelah 15 detik, sebagian folder belum ditelusuri</span>
          </p>
          <div class="gulir">
            <table class="tabel">
              <thead>
                <tr><th>Path</th><th class="kanan">Ukuran</th><th>Diubah</th><th class="sembunyi-hp">Pemilik</th><th><span class="sr-only">Aksi</span></th></tr>
              </thead>
              <tbody>
                <tr v-for="h in pencarian.hasil.hasil" :key="h.path">
                  <td>
                    <button type="button" class="nama-entri" :class="h.jenis" :title="h.path" @click="klikHasil(h)">
                      <Ikon :nama="ikonEntri(h)" :ukuran="17" /><span>{{ relatif(h.path) }}</span>
                      <small v-if="h.link" class="redup">→ {{ h.link }}</small>
                    </button>
                  </td>
                  <td class="kanan angka-kol">{{ h.ukuran == null ? '—' : ukuranBerkas(h.ukuran) }}</td>
                  <td class="angka-kol">{{ h.waktu ? tanggalWaktu(h.waktu) : '—' }}</td>
                  <td class="sembunyi-hp">{{ h.pemilik }}<span v-if="h.grup" class="redup">:{{ h.grup }}</span></td>
                  <td class="angka-kol"><button type="button" class="tombol garis kecil" @click="buka(induk(h.path))">Buka lokasi</button></td>
                </tr>
              </tbody>
            </table>
            <p v-if="!pencarian.hasil.hasil.length" class="redup kosong">Tidak ada yang cocok. Tip: pakai * dan ? sebagai wildcard, mis. <code>*.log</code> atau <code>wp-config.php</code>.</p>
          </div>
        </template>
      </div>

      <div v-if="terpilih.length && !modeCari" class="bar-pilih" role="toolbar" aria-label="Aksi item terpilih">
        <b>{{ terpilih.length }} dipilih</b>
        <button v-if="satu?.jenis === 'berkas'" type="button" class="tombol garis kecil" @click="unduh(gabung(folder, satu.nama))"><Ikon nama="unduh" :ukuran="15" /> Unduh</button>
        <button v-if="satu" type="button" class="tombol garis kecil" @click="gantiNama">Ganti nama</button>
        <button type="button" class="tombol garis kecil" @click="salinPindah(false)"><Ikon nama="salin" :ukuran="15" /> Salin ke…</button>
        <button type="button" class="tombol garis kecil" @click="salinPindah(true)">Pindah ke…</button>
        <button type="button" class="tombol garis kecil" @click="buatZip">Zip</button>
        <button v-if="satu && /\.zip$/i.test(satu.nama)" type="button" class="tombol garis kecil" @click="ekstrak">Ekstrak</button>
        <button v-if="satu" type="button" class="tombol garis kecil" @click="ubahIzin"><Ikon nama="kunci" :ukuran="15" /> Izin</button>
        <button type="button" class="tombol bahaya kecil" @click="hapus"><Ikon nama="sampah" :ukuran="15" /> Hapus</button>
        <button type="button" class="tombol garis kecil batal" @click="pilih = new Set()">Batal pilih</button>
      </div>

      <p v-if="galat" class="pesan-status bahaya" role="alert">{{ galat }}</p>

      <div v-if="antrean.length" class="antrean" aria-live="polite">
        <div class="antrean-kepala">
          <b>Unggahan</b><span class="redup">{{ unggahJalan ? `${unggahJalan} tersisa` : 'selesai' }}</span>
          <button v-if="!unggahJalan" type="button" class="tombol garis kecil" @click="antrean = []">Tutup</button>
        </div>
        <ul>
          <li v-for="(t, i) in antrean" :key="i" :class="t.status">
            <span class="antrean-nama" :title="t.nama">{{ t.nama }}</span>
            <span class="redup">{{ ukuranBerkas(t.ukuran) }}</span>
            <span v-if="t.status === 'gagal'" class="galat-kecil">{{ t.galat }}</span>
            <span v-else class="meter" role="progressbar" :aria-valuenow="t.persen" aria-valuemin="0" aria-valuemax="100" :aria-label="`Unggah ${t.nama}`"><i :style="{ width: `${t.persen}%` }" /></span>
          </li>
        </ul>
      </div>

      <div v-show="!modeCari" class="gulir">
        <table class="tabel">
          <thead>
            <tr>
              <th class="kol-pilih"><input type="checkbox" :checked="semuaTerpilih" :indeterminate="terpilih.length > 0 && !semuaTerpilih" aria-label="Pilih semua" @change="togglSemua"></th>
              <th :aria-sort="ariaUrut('nama')"><button type="button" class="kepala-urut" @click="ubahUrut('nama')">Nama</button></th>
              <th class="kanan" :aria-sort="ariaUrut('ukuran')"><button type="button" class="kepala-urut" @click="ubahUrut('ukuran')">Ukuran</button></th>
              <th :aria-sort="ariaUrut('waktu')"><button type="button" class="kepala-urut" @click="ubahUrut('waktu')">Diubah</button></th>
              <th class="sembunyi-hp">Izin</th>
              <th class="sembunyi-hp">Pemilik</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="folder !== '/'" class="baris-naik">
              <td />
              <td colspan="5"><button type="button" class="nama-entri" @click="buka(induk(folder))"><Ikon nama="naik" :ukuran="16" /> ..</button></td>
            </tr>
            <tr v-for="e in entri" :key="e.nama" :class="{ dipilih: pilih.has(e.nama) }">
              <td class="kol-pilih"><input type="checkbox" :checked="pilih.has(e.nama)" :aria-label="`Pilih ${e.nama}`" @change="togglePilih(e.nama)"></td>
              <td>
                <button type="button" class="nama-entri" :class="e.jenis" :title="e.link ? `→ ${e.link}` : e.nama" @click="klikEntri(e)">
                  <Ikon :nama="ikonEntri(e)" :ukuran="17" /><span>{{ e.nama }}</span>
                  <small v-if="e.link" class="redup">→ {{ e.link }}</small>
                </button>
              </td>
              <td class="kanan angka-kol">{{ e.ukuran == null ? '—' : ukuranBerkas(e.ukuran) }}</td>
              <td class="angka-kol">{{ e.waktu ? tanggalWaktu(e.waktu) : '—' }}</td>
              <td class="sembunyi-hp"><code :title="e.oktal">{{ e.mode }}</code></td>
              <td class="sembunyi-hp">{{ e.pemilik }}<span class="redup">:{{ e.grup }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-if="memuat && !data" class="redup">Memuat…</p>
        <p v-else-if="data && !entri.length" class="redup kosong">{{ cari ? 'Tidak ada nama yang cocok.' : 'Folder kosong.' }}</p>
        <p v-if="data?.terpotong" class="pesan-status">Hanya 20.000 item pertama yang ditampilkan.</p>
      </div>
      <p class="redup kaki">Tarik & lepas berkas atau folder ke sini untuk mengunggah. Klik berkas teks untuk menyunting (Ctrl+S simpan).</p>
    </section>

    <Dialog :buka="isian.buka" :judul="isian.judul" lebar="520px" @tutup="isian.buka = false">
      <form class="form" @submit.prevent="kirimIsian">
        <label class="isian"><span>{{ isian.label }}</span><input v-model="isian.nilai" required spellcheck="false" autocomplete="off"></label>
        <label v-if="isian.timpa !== null" class="centang"><input v-model="isian.timpa" type="checkbox"> Timpa bila nama sudah ada</label>
        <p v-if="isian.petunjuk" class="redup">{{ isian.petunjuk }}</p>
        <p v-if="isian.galat" class="pesan-status bahaya" role="alert">{{ isian.galat }}</p>
        <div class="aksi-dialog">
          <button type="button" class="tombol garis" @click="isian.buka = false">Batal</button>
          <button type="submit" class="tombol" :disabled="isian.proses">{{ isian.proses ? 'Memproses…' : isian.tombol }}</button>
        </div>
      </form>
    </Dialog>

    <Dialog :buka="editor.buka" :judul="`${berubah ? '● ' : ''}${editor.path}`" lebar="1200px" @tutup="tutupEditor">
      <div class="editor">
        <p v-if="editor.memuat" class="redup">Membuka…</p>
        <EditorKode v-else :key="editor.path" v-model="editor.isi" :nama="editor.path" @simpan="simpanEditor()" />
        <p v-if="editor.galat" class="pesan-status bahaya" role="alert">{{ editor.galat }}</p>
        <div class="aksi-dialog">
          <span class="redup info-editor">{{ editor.isi.split('\n').length }} baris · Ctrl+S simpan</span>
          <a class="tombol garis" :href="urlUnduh(editor.path)" download>Unduh</a>
          <button type="button" class="tombol garis" @click="tutupEditor">Tutup</button>
          <button type="button" class="tombol" :disabled="!berubah || editor.proses" @click="simpanEditor()">{{ editor.proses ? 'Menyimpan…' : berubah ? 'Simpan' : 'Tersimpan' }}</button>
        </div>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; min-width: 0; }
.disk { margin: 0; }
.kartu { min-width: 0; display: grid; gap: 12px; transition: box-shadow .15s; }
.kartu.seret { box-shadow: 0 0 0 2px var(--aksen-terang) inset; }
.bar-alamat { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.remah { display: flex; align-items: center; flex-wrap: wrap; gap: 2px; flex: 1 1 260px; min-width: 0; font-size: 14px; }
.remah button { border: 0; background: none; color: var(--aksen-terang); font: inherit; padding: 3px 5px; border-radius: 6px; cursor: pointer; overflow-wrap: anywhere; text-align: left; }
.remah button:hover { background: var(--kartu-2); }
.remah button[aria-current] { color: var(--teks); font-weight: 700; }
.pemisah { color: var(--teks-3); }
.form-alamat { display: flex; gap: 6px; flex: 1 1 280px; }
.form-alamat input { min-height: 34px; padding: 5px 10px; font: 13px ui-monospace, SFMono-Regular, Consolas, monospace; }
.bar-alat { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.kelompok { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.kelompok .tombol, .bar-pilih .tombol { display: inline-flex; align-items: center; gap: 5px; }
.cari { min-height: 34px; padding: 5px 10px; width: 200px; }
.centang { display: inline-flex; align-items: center; gap: 7px; font-size: 13px; color: var(--teks-2); cursor: pointer; }
.bar-cari { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.bar-cari .cari-dalam { flex: 1 1 280px; min-height: 34px; padding: 5px 10px; }
.bar-cari select { min-height: 34px; padding: 5px 8px; width: auto; }
.bar-cari .tombol { display: inline-flex; align-items: center; gap: 5px; }
.hasil-cari { display: grid; gap: 8px; min-width: 0; }
.hasil-cari > * { min-width: 0; }
.hasil-cari .gulir { position: relative; }
.ringkas-cari { margin: 0; font-size: 13px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.bar-pilih { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 10px; border-radius: 10px; background: var(--aksen-lembut); }
.bar-pilih b { font-size: 13px; margin-right: 4px; }
.bar-pilih .batal { margin-left: auto; }
.gulir { overflow-x: auto; }
.tabel { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.tabel th { text-align: left; font-size: 12px; font-weight: 600; color: var(--teks-3); padding: 6px 10px; border-bottom: 1px solid var(--garis); white-space: nowrap; }
.tabel td { padding: 4px 10px; border-bottom: 1px solid var(--garis); color: var(--teks-2); vertical-align: middle; }
.tabel tr:hover td { background: var(--kartu-2); }
.tabel tr.dipilih td { background: var(--aksen-lembut); }
.kol-pilih { width: 34px; padding-right: 0 !important; }
.kanan { text-align: right !important; }
.angka-kol { white-space: nowrap; font-variant-numeric: tabular-nums; }
.kepala-urut { border: 0; background: none; color: inherit; font: inherit; padding: 0; cursor: pointer; }
th[aria-sort="ascending"] .kepala-urut::after { content: " ↑"; }
th[aria-sort="descending"] .kepala-urut::after { content: " ↓"; }
.nama-entri { display: inline-flex; align-items: center; gap: 8px; border: 0; background: none; color: var(--teks); font: inherit; padding: 5px 0; cursor: pointer; text-align: left; max-width: 100%; }
.nama-entri span { overflow-wrap: anywhere; }
.nama-entri svg { flex: none; }
.nama-entri:hover span { color: var(--aksen-terang); text-decoration: underline; text-underline-offset: 3px; }
.nama-entri.folder svg { color: var(--waspada); }
.nama-entri.rusak, .nama-entri.khusus { color: var(--teks-3); cursor: default; }
.nama-entri small { white-space: nowrap; }
.baris-naik .nama-entri { color: var(--teks-2); }
code { font: 12px ui-monospace, SFMono-Regular, Consolas, monospace; }
.kosong { padding: 18px 0; text-align: center; }
.kaki { margin: 0; }
.antrean { border: 1px solid var(--garis); border-radius: 10px; padding: 10px 12px; display: grid; gap: 8px; max-height: 220px; overflow-y: auto; }
.antrean-kepala { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.antrean-kepala .tombol { margin-left: auto; }
.antrean ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 5px; }
.antrean li { display: grid; grid-template-columns: minmax(0, 1fr) auto 140px; gap: 10px; align-items: center; font-size: 12.5px; }
.antrean-nama { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meter { height: 6px; border-radius: 3px; background: var(--kartu-2); overflow: hidden; }
.meter i { display: block; height: 100%; background: var(--aksen); transition: width .2s; }
.antrean li.selesai .meter i { background: var(--baik); }
.galat-kecil { color: var(--bahaya); font-size: 12px; }
.form { display: grid; gap: 12px; }
.form p { margin: 0; }
.editor { display: grid; gap: 10px; }
.editor .aksi-dialog { margin-top: 4px; align-items: center; }
.editor .aksi-dialog a { display: inline-flex; align-items: center; text-decoration: none; }
.info-editor { margin-right: auto; }
@media (max-width: 700px) {
  .sembunyi-hp { display: none; }
  .cari { width: 100%; }
  .kelompok { width: 100%; }
  .antrean li { grid-template-columns: minmax(0, 1fr) 80px; }
  .antrean li > .redup { display: none; }
}
</style>
