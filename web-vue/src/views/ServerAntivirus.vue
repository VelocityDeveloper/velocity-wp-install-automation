<script setup>
// Antivirus server hosting (sub-menu Server): scan berkas akun dengan tanda tangan Velocity (VD.*), deteksi cPGuard
// 30 hari sebagai pembanding, dan karantina manual. Data: GET /api/servers/antivirus (installer_status.py →
// scripts/server_antivirus_agent.py lewat SSH), scan: GET/POST /api/servers/antivirus/scan, aksi karantina:
// POST /api/servers/antivirus/aksi (dicatat di riwayat). Tidak ada karantina otomatis — semua temuan hanya dilaporkan.
import PilihServer from '../components/PilihServer.vue'
import { pilihServer } from '../jenisServer.js'
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import Ikon from '../components/Ikon.vue'
import PelakuAkun from '../components/PelakuAkun.vue'
import { namaAkun } from '../akun.js'
import Info from '../components/Info.vue'
import GrafikBatangTumpuk from '../components/GrafikBatangTumpuk.vue'
import { konfirmasi } from '../konfirmasi.js'
import { minta, kirim, pakaiPolling, tanggalWaktu, waktuLalu, angka, ukuranBerkas } from '../api.js'
import { tabUrl } from '../laravel.js'

const av = pakaiPolling('/api/servers/antivirus', 300000)
const daftarScan = pakaiPolling('/api/servers/antivirus/scan', 0)
const riwayat = pakaiPolling('/api/servers/antivirus/riwayat', 0)
const segarkan = ref(false)
async function muatSegar() {
  segarkan.value = true
  try { av.data.value = await minta('/api/servers/antivirus?segar=1'); av.galat.value = null }
  catch (e) { av.galat.value = e }
  finally { segarkan.value = false }
  daftarScan.muatUlang()
  riwayat.muatUlang()
}
const servers = computed(() => av.data.value?.servers || [])
const pilih = pilihServer()
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || servers.value[0] || null)
const TAB = ['scan', 'cpguard', 'karantina', 'riwayat']
const tab = tabUrl('tab', 'scan', { boleh: TAB })

// Nama pelaku dipakai bersama halaman Proteksi
// Pelaku di riwayat = akun yang masuk ke dash.velocity.ai.id (backend menggantinya dari cookie sesi)
const oleh = namaAkun

const PESAN = {
  invalid_oleh: 'Masuk dulu lewat tombol "Masuk dengan VD.net" di kanan atas — setiap scan & karantina dicatat atas nama akun Anda.',
  login_diperlukan: 'Sesi login habis atau belum masuk. Klik "Masuk dengan VD.net" di kanan atas.',
  server_tidak_dikenal: 'Server tidak dikenal; muat ulang halaman.',
  akun_tidak_dikenal: 'Akun tidak ada di server ini.',
  hari_tidak_sah: 'Scan semua akun wajib dibatasi berkas yang berubah N hari terakhir.',
  semua_akun_perlu_batas_hari: 'Scan semua akun wajib dibatasi berkas yang berubah N hari terakhir.',
  scan_sedang_jalan: 'Masih ada scan berjalan di server ini. Tunggu selesai atau hentikan dulu.',
  scan_tidak_jalan: 'Scan sudah tidak berjalan.',
  path_tidak_sah: 'Hanya berkas di /home/<akun>/domains/ yang bisa dikarantina.',
  berkas_tidak_ada: 'Berkas sudah tidak ada (mungkin sudah dihapus/dikarantina).',
  lokasi_asal_terisi: 'Lokasi asal sudah berisi berkas lain — tidak ditimpa.',
  folder_asal_hilang: 'Folder asal sudah tidak ada.',
  karantina_tidak_ada: 'Entri karantina tidak ditemukan.',
  salin_gagal: 'Salinan karantina tidak cocok — berkas asli tidak disentuh.',
  terputus: 'Terputus (layanan dashboard di-restart saat scan berjalan).',
  dihentikan: 'Dihentikan.',
  waktu_habis: 'Berhenti karena batas waktu 58 menit — sebagian berkas belum dipindai.',
  maks_temuan: 'Berhenti di 3.000 temuan.',
  forbidden: 'Ditolak: hanya bisa dijalankan dari halaman dashboard ini.',
  timeout: 'Server tidak menjawab (timeout).',
}
const pesanGalat = (e) => PESAN[e] || e || 'gagal'
const pesan = reactive({ teks: '', galat: false })
const proses = ref(false)

function perluNama() {
  if (oleh.value.trim()) return false
  Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true })
  document.getElementById('nama-antivirus')?.focus()
  return true
}

// ---- Ringkasan semua server ----
const tglLokal = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const hariLalu = (n) => tglLokal(new Date(Date.now() - n * 86400000))
const cpgJumlah = (s, n) => Object.entries(s?.cpguard?.per_hari || {}).reduce((a, [t, v]) => a + (t >= hariLalu(n - 1) ? v : 0), 0)
const scanServer = (host) => (daftarScan.data.value?.scan || []).filter((j) => j.host === host)
const scanTerakhir = (host) => scanServer(host).find((j) => j.status === 'selesai')
// Ringkasan kartu untuk server terpilih saja
const total = computed(() => {
  const s = terpilih.value
  const scan = scanTerakhir(s.host)
  return {
    cpg24: cpgJumlah(s, 1),
    cpg30: cpgJumlah(s, 30),
    virus: scan?.jumlah_virus || 0,
    curiga: (scan?.jumlah_temuan || 0) - (scan?.jumlah_virus || 0),
    karantina: s.karantina?.length || 0,
  }
})
function tingkat(s) {
  if (!s.ok) return 'bahaya'
  if (scanTerakhir(s.host)?.jumlah_virus || cpgJumlah(s, 1)) return 'bahaya'
  if (scanTerakhir(s.host)?.jumlah_temuan || cpgJumlah(s, 7)) return 'waspada'
  return 'baik'
}

// ---- Scan ----
const RENTANG = [
  { nilai: 1, label: '24 jam' }, { nilai: 3, label: '3 hari' }, { nilai: 7, label: '7 hari' },
  { nilai: 30, label: '30 hari' }, { nilai: 0, label: 'Semua berkas' },
]
const form = reactive({ akun: 'semua', hari: 1 })
watch(() => form.akun, (a) => { if (a === 'semua' && form.hari === 0) form.hari = 1 })
watch(pilih, () => { form.akun = 'semua'; form.hari = 1; lihatId.value = ''; filterTingkat.value = ''; cariTemuan.value = '' })
const akunServer = computed(() => terpilih.value?.akun || [])
const jalanDiServer = computed(() => scanServer(terpilih.value?.host).find((j) => j.status === 'berjalan'))

async function mulaiScan() {
  if (perluNama()) return
  proses.value = true
  try {
    const j = await kirim('/api/servers/antivirus/scan', { server: terpilih.value.host, akun: form.akun, hari: form.hari, oleh: oleh.value.trim() })
    Object.assign(pesan, { teks: `Scan dimulai di ${terpilih.value.name}.`, galat: false })
    await daftarScan.muatUlang()
    lihatId.value = j.id
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
async function hentikan(j) {
  const ya = await konfirmasi({ judul: 'Hentikan scan?', teks: 'Berkas yang sudah dipindai tidak disimpan sebagai hasil.', tombol: 'Hentikan', kelas: 'bahaya' })
  if (!ya) return
  try { await kirim('/api/servers/antivirus/henti', { id: j.id }) } catch (e) { Object.assign(pesan, { teks: pesanGalat(e.message), galat: true }) }
  setTimeout(() => daftarScan.muatUlang(), 1500)
}

// Detail scan yang sedang dilihat; scan berjalan disegarkan tiap 3 dtk
const lihatId = ref('')
const detail = ref(null)
let timerScan = null
async function muatDetail() {
  if (!lihatId.value) { detail.value = null; return }
  try {
    const d = await minta(`/api/servers/antivirus/scan?id=${lihatId.value}`)
    if (d.id === lihatId.value) detail.value = d
    if (d.status !== 'berjalan') {
      clearInterval(timerScan); timerScan = null
      daftarScan.muatUlang()
    }
  } catch (e) { Object.assign(pesan, { teks: pesanGalat(e.message), galat: true }) }
}
watch(lihatId, () => {
  clearInterval(timerScan); timerScan = null
  detail.value = null
  muatDetail()
  timerScan = setInterval(muatDetail, 3000)
})
// Scan berjalan di server lain/terpilih dipantau dari daftar
const timerDaftar = setInterval(() => { if (scanServer(terpilih.value?.host).some((j) => j.status === 'berjalan')) daftarScan.muatUlang() }, 5000)
onBeforeUnmount(() => { clearInterval(timerScan); clearInterval(timerDaftar) })
// Buka hasil scan terakhir server ini bila belum memilih
watch([terpilih, () => daftarScan.data.value], () => {
  if (!lihatId.value && terpilih.value) {
    const j = scanServer(terpilih.value.host)[0]
    if (j) lihatId.value = j.id
  }
}, { immediate: true })

const filterTingkat = ref('')
const cariTemuan = ref('')
const tampilSemua = ref(false)
const karantinaPath = ref(new Set())
const relatif = (p) => (p || '').replace(/^\/home\/[^/]+\/domains\//, '')
const temuanTersaring = computed(() => {
  const q = cariTemuan.value.trim().toLowerCase()
  return (detail.value?.temuan || [])
    .filter((t) => (!filterTingkat.value || t.tingkat === filterTingkat.value)
      && (!q || t.path.toLowerCase().includes(q) || t.tanda.some((x) => x.id.toLowerCase().includes(q))))
    .sort((a, b) => (a.tingkat === b.tingkat ? b.mtime - a.mtime : a.tingkat === 'virus' ? -1 : 1))
})
const hitungTingkat = computed(() => {
  const out = { virus: 0, curiga: 0 }
  for (const t of detail.value?.temuan || []) out[t.tingkat]++
  return out
})
const labelRentang = (h) => (h ? `berubah ${RENTANG.find((r) => r.nilai === h)?.label || `${h} hari`}` : 'semua berkas')
const durasi = (j) => {
  const d = (j.selesai || Math.floor(Date.now() / 1000)) - j.mulai
  return d >= 60 ? `${Math.floor(d / 60)} mnt ${d % 60} dtk` : `${d} dtk`
}

async function karantina(path, alasan) {
  if (perluNama()) return
  const ya = await konfirmasi({
    judul: 'Karantina berkas ini?',
    teks: `${relatif(path)} dipindah ke /root/velocity-karantina di ${terpilih.value.name}. Bila berkas ini dipakai situs (mis. index.php, functions.php), halaman bisa error sampai dibersihkan atau dikembalikan.`,
    tombol: 'Karantina', kelas: 'bahaya',
  })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/antivirus/aksi', { aksi: 'karantina', server: terpilih.value.host, path, alasan, oleh: oleh.value.trim() })
    if (!r.ok) throw new Error(r.error)
    karantinaPath.value = new Set([...karantinaPath.value, path])
    Object.assign(pesan, { teks: `${relatif(path)} dikarantina.`, galat: false })
    av.muatUlang()
    riwayat.muatUlang()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}

// ---- Karantina ----
async function aksiKarantina(k, aksi) {
  if (perluNama()) return
  const ya = await konfirmasi(aksi === 'kembalikan'
    ? { judul: 'Kembalikan berkas?', teks: `${relatif(k.path)} dipulihkan ke lokasi asal dengan pemilik & izin semula.`, tombol: 'Kembalikan' }
    : { judul: 'Hapus permanen?', teks: `Salinan karantina ${relatif(k.path)} dihapus dan tidak bisa dikembalikan.`, tombol: 'Hapus permanen', kelas: 'bahaya' })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/antivirus/aksi', { aksi, server: terpilih.value.host, id: k.id, oleh: oleh.value.trim() })
    if (!r.ok) throw new Error(r.error)
    Object.assign(pesan, { teks: aksi === 'kembalikan' ? `${relatif(k.path)} dikembalikan.` : 'Salinan karantina dihapus.', galat: false })
    if (aksi === 'kembalikan') karantinaPath.value = new Set([...karantinaPath.value].filter((p) => p !== k.path))
    av.muatUlang()
    riwayat.muatUlang()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}

// ---- Deteksi cPGuard ----
// Arti cleanup_status ditebak dari pola data (bukan dokumentasi resmi) → label + kode asli di tooltip
const CLEANUP = { '-1': ['ungu', 'Ditindak'], '100': ['hijau', 'Dibersihkan'], '-100': ['merah', 'Dihapus'], '0': ['abu', 'Dilaporkan'] }
const labelCleanup = (c) => CLEANUP[String(c)] || ['abu', c == null ? '-' : `Kode ${c}`]
const cariCpg = ref('')
const tampilSemuaCpg = ref(false)
watch(pilih, () => { cariCpg.value = ''; tampilSemuaCpg.value = false })
const cpgTersaring = computed(() => {
  const q = cariCpg.value.trim().toLowerCase()
  return (terpilih.value?.cpguard?.deteksi || []).filter((d) => !q || d.path.toLowerCase().includes(q)
    || (d.definisi || '').toLowerCase().includes(q) || (d.user || '').includes(q))
})
const cpgAkun = computed(() => (terpilih.value?.cpguard?.per_akun || []).slice(0, 8))
const SERI_CPG = [{ kunci: 'n', label: 'Deteksi cPGuard', warna: '#cc7a33' }]
const cpgHari = computed(() => {
  const per = terpilih.value?.cpguard?.per_hari || {}
  return Array.from({ length: 30 }, (_, i) => { const t = hariLalu(29 - i); return { tgl: t, nilai: { n: per[t] || 0 } } })
})
const puncakCpg = computed(() => [...cpgHari.value].sort((a, b) => b.nilai.n - a.nilai.n).filter((h) => h.nilai.n).slice(0, 3).map((h) => h.tgl))
const formatTgl = (t) => new Date(`${t}T00:00`).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })
const ringkasDefinisi = (d) => (d || '').replace(/^\{(HEX|CPG)\}/, '').replace(/\.UNOFFICIAL$/, '').replace(/^Malware\.Expert\./, '')

const riwayatServer = computed(() => (riwayat.data.value?.riwayat || []).filter((r) => !terpilih.value || r.host === terpilih.value.host))
const AKSI_LABEL = { karantina: ['merah', 'Karantina'], kembalikan: ['hijau', 'Kembalikan'], hapus: ['abu', 'Hapus permanen'] }
const namaTanda = (id) => (terpilih.value?.tanda || []).find((t) => t.id === id)?.nama || id
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Antivirus Server</h1>
        <p class="redup">Pindai berkas situs klien dengan tanda tangan Velocity, bandingkan dengan deteksi cPGuard, dan karantina berkas jahat secara manual.</p>
      </div>
      <div class="kepala-aksi">
        <div class="nama-saya"><span class="redup">Dicatat sebagai</span><PelakuAkun id="nama-antivirus" /></div>
        <button type="button" class="tombol kecil" :disabled="segarkan || (av.memuat.value && !av.data.value)" @click="muatSegar"><Ikon nama="ulang" :ukuran="16" /> {{ segarkan ? 'Membaca…' : 'Muat ulang' }}</button>
      </div>
    </header>

    <div v-if="av.memuat.value && !av.data.value" class="skeleton" aria-busy="true">
      <p class="redup status-muat" role="status">Membaca data antivirus semua server lewat SSH (±5–20 detik)…</p>
      <div class="ringkas">
        <div v-for="i in 4" :key="i" class="kartu tile"><span class="sk sk-ikon" /><div><span class="sk sk-teks" /><span class="sk sk-angka" /><span class="sk sk-teks pendek" /></div></div>
      </div>
      <div class="sk-menu"><span v-for="i in 5" :key="i" class="sk sk-pil" /></div>
      <section class="kartu">
        <span class="sk sk-judul" />
        <div v-for="i in 5" :key="i" class="sk-baris"><span v-for="j in 5" :key="j" class="sk" /></div>
      </section>
    </div>

    <p v-else-if="av.galat.value && !av.data.value" class="pesan-status bahaya">Gagal memuat: {{ av.galat.value.message }}</p>
    <p v-else-if="av.data.value?.error" class="pesan-status bahaya">Gagal memuat: {{ pesanGalat(av.data.value.error) }}</p>

    <template v-else-if="av.data.value">
      <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>

      <PilihServer v-if="terpilih" :servers="servers" :model-value="terpilih?.name" :titik="tingkat(terpilih)" :teks="(s) => s.name + (scanServer(s.host).some((j) => j.status === 'berjalan') ? ' · scan berjalan' : '')" @update:model-value="pilih = $event" />

      <template v-if="terpilih">
        <section v-if="!terpilih.ok" class="kartu">
          <p class="pesan-status bahaya">Tidak bisa dibaca: {{ pesanGalat(terpilih.error) }}</p>
        </section>
        <div v-if="terpilih.ok" class="ringkas">
            <div class="kartu tile">
              <span class="tile-ikon merah"><Ikon nama="virus" :ukuran="20" /></span>
              <div><span class="redup">Virus (scan terakhir)</span><b>{{ angka(total.virus) }}</b><small class="redup">{{ angka(total.curiga) }} berkas mencurigakan</small></div>
            </div>
            <div class="kartu tile">
              <span class="tile-ikon kuning"><Ikon nama="perisai" :ukuran="20" /></span>
              <div><span class="redup">Deteksi cPGuard 24 jam</span><b>{{ angka(total.cpg24) }}</b><small class="redup">{{ angka(total.cpg30) }} dalam 30 hari</small></div>
            </div>
            <div class="kartu tile">
              <span class="tile-ikon ungu"><Ikon nama="kunci" :ukuran="20" /></span>
              <div><span class="redup">Dikarantina Velocity</span><b>{{ angka(total.karantina) }}</b><small class="redup">bisa dikembalikan</small></div>
            </div>
            <div class="kartu tile">
              <span class="tile-ikon hijau"><Ikon nama="server" :ukuran="20" /></span>
              <div><span class="redup">cPGuard</span><b>{{ terpilih.cpguard_jalan ? 'Jalan' : 'Mati' }}</b><small class="redup">dibaca {{ waktuLalu(av.data.value.diambil) }}</small></div>
            </div>
          </div>
        <section v-if="terpilih.ok" class="kartu" aria-labelledby="judul-detail">
          <div class="kartu-judul">
            <h2 id="judul-detail"><Ikon nama="virus" :ukuran="16" /> {{ terpilih.name }}
              <small class="redup">{{ terpilih.akun.length }} akun · cPGuard {{ terpilih.cpguard ? (terpilih.cpguard_jalan ? 'jalan' : 'TIDAK jalan') : 'tidak terpasang' }}</small>
            </h2>
            <div class="tab" role="tablist" aria-label="Bagian antivirus">
              <button v-for="t in [
                { k: 'scan', label: 'Scan' },
                { k: 'cpguard', label: 'Deteksi cPGuard', n: terpilih.cpguard?.deteksi?.length },
                { k: 'karantina', label: 'Karantina', n: terpilih.karantina.length },
                { k: 'riwayat', label: 'Riwayat', n: riwayatServer.length },
              ]" :key="t.k" type="button" role="tab" :aria-selected="tab === t.k" :class="{ aktif: tab === t.k }" @click="tab = t.k">
                {{ t.label }} <span v-if="t.n !== undefined" class="hitung">{{ t.n }}</span>
              </button>
            </div>
          </div>

          <!-- ================= Scan ================= -->
          <template v-if="tab === 'scan'">
            <form class="form-scan" @submit.prevent="mulaiScan">
              <label class="isian"><span>Akun</span>
                <select v-model="form.akun">
                  <option value="semua">Semua akun ({{ terpilih.akun.length }})</option>
                  <option v-for="a in akunServer" :key="a.user" :value="a.user">{{ a.user }} — {{ a.domain.filter((d) => !['default', 'sharedip', 'suspended'].includes(d)).join(', ') || '-' }}</option>
                </select>
              </label>
              <fieldset class="pil-durasi">
                <legend>Berkas yang dipindai
                  <Info label="Tentang rentang scan"><p>Berkas yang dibuat/diubah dalam rentang ini (mtime atau ctime). "Semua berkas" hanya untuk satu akun — semua akun sekaligus bisa berjam-jam. Scan berjalan dengan prioritas rendah (nice/ionice) dan berhenti sendiri setelah 58 menit.</p></Info>
                </legend>
                <label v-for="r in RENTANG" :key="r.nilai" :class="{ aktif: form.hari === r.nilai, mati: r.nilai === 0 && form.akun === 'semua' }">
                  <input v-model="form.hari" type="radio" class="sr" :value="r.nilai" :disabled="r.nilai === 0 && form.akun === 'semua'"> {{ r.label }}
                </label>
              </fieldset>
              <button type="submit" class="tombol" :disabled="proses || !!jalanDiServer"><Ikon nama="cari" :ukuran="16" /> {{ jalanDiServer ? 'Scan berjalan…' : 'Mulai scan' }}</button>
            </form>
            <p class="redup kaki-form">Hanya melapor — tidak ada berkas yang diubah sampai Anda menekan <b>Karantina</b>. {{ (terpilih.tanda || []).length }} tanda tangan
              <Info label="Daftar tanda tangan"><ul class="daftar-tanda"><li v-for="t in terpilih.tanda" :key="t.id"><span class="lencana" :class="t.tingkat === 'virus' ? 'merah' : 'kuning'">{{ t.tingkat === 'virus' ? 'VIRUS' : 'CURIGA' }}</span> {{ t.nama }}</li></ul></Info>
            </p>

            <!-- Daftar scan server ini -->
            <div v-if="scanServer(terpilih.host).length" class="daftar-scan" role="list" aria-label="Scan sebelumnya">
              <button v-for="j in scanServer(terpilih.host).slice(0, 8)" :key="j.id" type="button" role="listitem" class="scan-item" :class="{ aktif: lihatId === j.id }" @click="lihatId = j.id">
                <span class="titik" :class="j.status === 'berjalan' ? 'biru' : j.status === 'gagal' ? 'abu' : j.jumlah_virus ? 'bahaya' : j.jumlah_temuan ? 'waspada' : 'baik'" aria-hidden="true" />
                <span class="scan-teks">
                  <b>{{ j.akun === 'semua' ? 'Semua akun' : j.akun }}</b> <span class="redup">· {{ labelRentang(j.hari) }}</span>
                  <small class="redup">{{ tanggalWaktu(j.mulai) }} · {{ j.oleh }}</small>
                </span>
                <span class="scan-hasil">
                  <template v-if="j.status === 'berjalan'"><span class="putar" aria-hidden="true" /> berjalan</template>
                  <template v-else-if="j.status === 'gagal'"><span class="redup" :title="pesanGalat(j.error)">{{ { terputus: 'Terputus', dihentikan: 'Dihentikan' }[j.error] || 'Gagal' }}</span></template>
                  <template v-else><b v-if="j.jumlah_virus" class="merah-teks">{{ j.jumlah_virus }} virus</b><span v-if="j.jumlah_temuan - j.jumlah_virus" class="kuning-teks">{{ j.jumlah_temuan - j.jumlah_virus }} curiga</span><span v-if="!j.jumlah_temuan" class="hijau-teks">Bersih</span></template>
                </span>
              </button>
            </div>
            <p v-else class="redup">Belum pernah di-scan dari dashboard.</p>

            <!-- Detail scan -->
            <div v-if="detail" class="detail-scan">
              <template v-if="detail.status === 'berjalan'">
                <div class="kemajuan" role="status">
                  <span class="putar besar" aria-hidden="true" />
                  <div>
                    <b>Memindai {{ detail.kemajuan?.akun || '…' }}</b>
                    <span class="redup"> akun {{ detail.kemajuan?.ke || 0 }}/{{ detail.kemajuan?.dari || '?' }} · {{ angka(detail.kemajuan?.berkas) }} berkas dilihat · {{ angka(detail.kemajuan?.dibaca) }} dibaca · {{ angka(detail.kemajuan?.temuan) }} temuan · {{ durasi(detail) }}</span>
                    <div class="garis-jalan"><span :style="{ width: `${detail.kemajuan ? (detail.kemajuan.ke / detail.kemajuan.dari) * 100 : 3}%` }" /></div>
                  </div>
                  <button type="button" class="tombol bahaya kecil" @click="hentikan(detail)">Hentikan</button>
                </div>
              </template>
              <p v-else-if="detail.status === 'gagal'" class="pesan-status bahaya">Scan gagal: {{ pesanGalat(detail.error) }} {{ detail.pesan || '' }}</p>
              <template v-else>
                <p class="ringkas-scan">
                  <b>{{ detail.akun === 'semua' ? `${detail.hasil.jumlah_akun} akun` : detail.akun }}</b> · {{ labelRentang(detail.hari) }} ·
                  {{ angka(detail.hasil.dibaca) }} berkas dibaca dari {{ angka(detail.hasil.berkas) }} ({{ ukuranBerkas(detail.hasil.byte) }}) · {{ durasi(detail) }}
                  <span v-if="detail.hasil.terpotong" class="lencana kuning">{{ pesanGalat(detail.hasil.terpotong) }}</span>
                </p>
                <p v-if="!detail.temuan.length" class="bersih"><Ikon nama="centang" :ukuran="18" /> Tidak ada berkas jahat atau mencurigakan.</p>
                <template v-else>
                  <div class="alat">
                    <input v-model="cariTemuan" type="search" placeholder="Cari path / aturan" aria-label="Cari temuan">
                    <div class="chip-filter" role="group" aria-label="Tingkat">
                      <button type="button" :class="{ aktif: !filterTingkat }" @click="filterTingkat = ''">Semua {{ detail.temuan.length }}</button>
                      <button type="button" :class="{ aktif: filterTingkat === 'virus' }" @click="filterTingkat = 'virus'">Virus {{ hitungTingkat.virus }}</button>
                      <button type="button" :class="{ aktif: filterTingkat === 'curiga' }" @click="filterTingkat = 'curiga'">Curiga {{ hitungTingkat.curiga }}</button>
                    </div>
                  </div>
                  <div class="tabel-wadah">
                    <table class="tabel">
                      <thead><tr><th scope="col">Berkas</th><th scope="col">Aturan</th><th scope="col">Diubah</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                      <tbody>
                        <tr v-for="t in (tampilSemua ? temuanTersaring : temuanTersaring.slice(0, 100))" :key="t.path">
                          <td class="ket berkas">
                            <span class="lencana" :class="t.tingkat === 'virus' ? 'merah' : 'kuning'">{{ t.tingkat === 'virus' ? 'VIRUS' : 'CURIGA' }}</span>
                            <code>{{ relatif(t.path) }}</code>
                            <small class="redup blok">{{ t.user }} · {{ ukuranBerkas(t.ukuran) }} · izin {{ t.izin }}</small>
                          </td>
                          <td class="ket">
                            <span v-for="x in t.tanda" :key="x.id" class="blok"><b>{{ x.nama }}</b> <span class="redup">{{ x.id }}</span>
                              <code class="bukti">{{ x.bukti }}</code></span>
                          </td>
                          <td class="nowrap">{{ tanggalWaktu(t.mtime) }}<small v-if="Math.abs(t.ctime - t.mtime) > 86400" class="redup blok" title="ctime = saat berkas terakhir ditulis/diubah izinnya; mtime bisa dipalsukan">ctime {{ tanggalWaktu(t.ctime) }}</small></td>
                          <td class="kanan">
                            <span v-if="karantinaPath.has(t.path)" class="lencana ungu">DIKARANTINA</span>
                            <button v-else type="button" class="tombol bahaya kecil" :disabled="proses" @click="karantina(t.path, t.tanda.map((x) => x.id).join(', '))">Karantina</button>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <button v-if="!tampilSemua && temuanTersaring.length > 100" type="button" class="tombol garis kecil lagi" @click="tampilSemua = true">Tampilkan semua {{ temuanTersaring.length }}</button>
                </template>
              </template>
            </div>
          </template>

          <!-- ================= Deteksi cPGuard ================= -->
          <template v-else-if="tab === 'cpguard'">
            <p v-if="!terpilih.cpguard" class="redup">cPGuard tidak terpasang di server ini.</p>
            <p v-else-if="terpilih.cpguard.error" class="pesan-status bahaya">scanner.db tidak terbaca: {{ terpilih.cpguard.error }}</p>
            <template v-else>
              <div class="grafik">
                <div class="grafik-kepala">
                  <b>Deteksi malware cPGuard per hari</b>
                  <span class="redup">30 hari: <b>{{ angka(cpgJumlah(terpilih, 30)) }}</b> · seluruhnya {{ angka(terpilih.cpguard.total) }}</span>
                </div>
                <GrafikBatangTumpuk judul="Deteksi malware cPGuard per hari" :hari="cpgHari" :seri="SERI_CPG" :format="angka" :format-tanggal="formatTgl"
                  :label-nilai="puncakCpg" satuan="deteksi" />
              </div>
              <div v-if="cpgAkun.length" class="akun-teratas">
                <span class="redup">Akun terbanyak:</span>
                <button v-for="[u, n] in cpgAkun" :key="u" type="button" class="chip" @click="cariCpg = u">{{ u }} <b>{{ n }}</b></button>
              </div>
              <div class="alat">
                <input v-model="cariCpg" type="search" :placeholder="`Cari path / definisi / akun di ${angka(terpilih.cpguard.deteksi.length)} deteksi terbaru`" aria-label="Cari deteksi cPGuard">
                <span class="redup">
                  Status ditebak dari pola data cPGuard
                  <Info label="Tentang status cPGuard" rata="kanan"><p>Kolom cleanup_status scanner.db tidak terdokumentasi. Ditindak = −1 (berkas bisa masih ada — dibersihkan di tempat atau dipulihkan), Dibersihkan = 100, Dihapus = −100 (umumnya .zip), Dilaporkan = 0. "Masih ada" dicek langsung ke disk saat dibaca.</p></Info>
                </span>
              </div>
              <p v-if="!cpgTersaring.length" class="redup">Tidak ada deteksi dalam 30 hari terakhir.</p>
              <div v-else class="tabel-wadah">
                <table class="tabel">
                  <thead><tr><th scope="col">Berkas</th><th scope="col">Definisi</th><th scope="col">Status</th><th scope="col">Waktu</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                  <tbody>
                    <tr v-for="d in (tampilSemuaCpg ? cpgTersaring : cpgTersaring.slice(0, 100))" :key="d.id">
                      <td class="ket berkas"><code>{{ relatif(d.path) }}</code><small class="redup blok">{{ d.user || '-' }} · {{ d.alasan }}</small></td>
                      <td class="ket"><span :title="d.definisi">{{ ringkasDefinisi(d.definisi) }}</span></td>
                      <td class="nowrap">
                        <span class="lencana" :class="labelCleanup(d.cleanup)[0]" :title="`cleanup_status ${d.cleanup}, file_status ${d.file_status}`">{{ labelCleanup(d.cleanup)[1] }}</span>
                        <span v-if="d.ada" class="lencana merah" title="Berkas masih ada di lokasi asal">MASIH ADA</span>
                      </td>
                      <td class="nowrap">{{ tanggalWaktu(d.waktu.replace(' ', 'T')) }}</td>
                      <td class="kanan">
                        <span v-if="karantinaPath.has(d.path)" class="lencana ungu">DIKARANTINA</span>
                        <button v-else-if="d.ada" type="button" class="tombol bahaya kecil" :disabled="proses" @click="karantina(d.path, `cPGuard ${d.definisi}`)">Karantina</button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <button v-if="!tampilSemuaCpg && cpgTersaring.length > 100" type="button" class="tombol garis kecil lagi" @click="tampilSemuaCpg = true">Tampilkan semua {{ cpgTersaring.length }}</button>
            </template>
          </template>

          <!-- ================= Karantina ================= -->
          <template v-else-if="tab === 'karantina'">
            <p class="redup kaki-form">Berkas disimpan di <code>/root/velocity-karantina/</code> server ini (hanya root) beserta pemilik, izin, dan waktu aslinya.</p>
            <p v-if="!terpilih.karantina.length" class="redup">Karantina kosong.</p>
            <div v-else class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">Berkas asal</th><th scope="col">Alasan</th><th scope="col">Dikarantina</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                <tbody>
                  <tr v-for="k in terpilih.karantina" :key="k.id">
                    <td class="ket berkas"><code>{{ relatif(k.path) }}</code><small class="redup blok">{{ k.user }} · {{ ukuranBerkas(k.ukuran) }} · sha256 {{ k.sha256.slice(0, 12) }}…</small></td>
                    <td class="ket">{{ (k.alasan || '-').split(', ').map(namaTanda).join(', ') }}</td>
                    <td class="nowrap">{{ tanggalWaktu(k.waktu) }}<small class="redup blok">{{ k.oleh || '-' }}</small></td>
                    <td class="kanan">
                      <button type="button" class="tombol garis kecil" :disabled="proses || k.asal_terisi" :title="k.asal_terisi ? 'Lokasi asal sudah berisi berkas lain' : ''" @click="aksiKarantina(k, 'kembalikan')">Kembalikan</button>
                      <button type="button" class="tombol bahaya kecil" :disabled="proses" @click="aksiKarantina(k, 'hapus')">Hapus</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>

          <!-- ================= Riwayat ================= -->
          <template v-else-if="tab === 'riwayat'">
            <p v-if="!riwayatServer.length" class="redup">Belum ada aksi karantina dari dashboard.</p>
            <ul v-else class="kejadian">
              <li v-for="(r, i) in riwayatServer" :key="i">
                <span class="titik" :class="r.ok ? AKSI_LABEL[r.aksi]?.[0] : 'abu'" aria-hidden="true" />
                <div>
                  <b>{{ AKSI_LABEL[r.aksi]?.[1] || r.aksi }}</b> <code>{{ relatif(r.path) }}</code>
                  <span v-if="!r.ok" class="lencana merah">GAGAL · {{ pesanGalat(r.error) }}</span>
                  <small class="redup blok">{{ r.oleh }}<template v-if="r.alasan"> · {{ r.alasan }}</template></small>
                </div>
                <time class="redup">{{ tanggalWaktu(r.t) }}</time>
              </li>
            </ul>
          </template>
        </section>
      </template>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.kepala-aksi { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.nama-saya { display: grid; gap: 4px; font-size: 12px; }

.ringkas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.kartu-judul { flex-wrap: wrap; gap: 10px; }
.kartu-judul h2 { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.kartu-judul h2 small { font-size: 12.5px; font-weight: 400; }
.tile { display: flex; gap: 14px; align-items: center; }
.tile > div { display: grid; gap: 3px; min-width: 0; }
.tile b { font-size: 24px; color: var(--teks-kuat); }
.tile small { font-size: 12px; }
.tile-ikon { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; }
.tile-ikon.merah { color: var(--bahaya); background: color-mix(in srgb, var(--bahaya) 15%, transparent); }
.tile-ikon.kuning { color: var(--waspada); background: color-mix(in srgb, var(--waspada) 15%, transparent); }
.tile-ikon.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 15%, transparent); }
.tile-ikon.hijau { color: var(--baik); background: color-mix(in srgb, var(--baik) 15%, transparent); }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); vertical-align: 1px; }
.titik.baik, .titik.hijau { background: var(--baik); }
.titik.waspada, .titik.kuning { background: var(--waspada); }
.titik.bahaya, .titik.merah { background: var(--bahaya); }
.titik.biru { background: var(--aksen-terang); }
.titik.ungu { background: var(--ungu); }
.lencana.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 14%, transparent); }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
/* Form scan */
.form-scan { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 14px; align-items: end; }
.form-scan .isian { display: grid; gap: 6px; font-size: 12.5px; color: var(--teks-2); min-width: 0; }
.form-scan select { width: 100%; min-width: 0; }
.form-scan .tombol { min-height: 42px; }
.pil-durasi { display: flex; flex-wrap: wrap; gap: 6px; margin: 0; padding: 0; border: 0; min-width: 0; }
.pil-durasi legend { display: inline-flex; align-items: center; gap: 4px; padding: 0; margin-bottom: 6px; font-size: 12.5px; color: var(--teks-2); }
.pil-durasi label { border: 1px solid var(--garis); border-radius: 9px; padding: 9px 12px; font-size: 13px; cursor: pointer; color: var(--teks-2); }
.pil-durasi label.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); color: var(--aksen-terang); font-weight: 600; }
.pil-durasi label.mati { opacity: .45; cursor: not-allowed; }
.pil-durasi label:focus-within { outline: 2px solid var(--aksen-terang); outline-offset: 2px; }
.kaki-form { margin: 10px 0 16px; font-size: 13px; display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.daftar-tanda { list-style: none; margin: 0; padding: 0; display: grid; gap: 5px; font-size: 12.5px; }
/* Daftar scan */
.daftar-scan { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(250px, 100%), 1fr)); gap: 8px; margin-bottom: 16px; }
.scan-item { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; gap: 10px; align-items: center; text-align: left; font: inherit; color: var(--teks);
  background: var(--kartu-2); border: 1px solid var(--garis); border-radius: 10px; padding: 10px 12px; cursor: pointer; }
.scan-item:hover { border-color: var(--aksen-terang); }
.scan-item.aktif { border-color: var(--aksen-terang); box-shadow: 0 0 0 1px var(--aksen-terang); }
.scan-teks { display: grid; gap: 2px; min-width: 0; font-size: 13px; overflow-wrap: anywhere; }
.scan-teks small { font-size: 11.5px; }
.scan-hasil { display: grid; justify-items: end; gap: 2px; font-size: 12.5px; white-space: nowrap; max-width: 110px; }
.merah-teks { color: var(--bahaya); }
.kuning-teks { color: var(--waspada); }
.hijau-teks { color: var(--baik); }
/* Detail scan */
.detail-scan { display: grid; gap: 12px; border-top: 1px solid var(--garis); padding-top: 16px; }
.ringkas-scan { margin: 0; font-size: 13.5px; }
.bersih { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--baik); font-weight: 600; }
.kemajuan { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 14px; align-items: center; padding: 14px; border-radius: 12px; background: var(--kartu-2); font-size: 13.5px; }
.garis-jalan { height: 6px; border-radius: 3px; background: var(--garis); overflow: hidden; margin-top: 8px; }
.garis-jalan span { display: block; height: 100%; background: var(--aksen); border-radius: 3px; transition: width .4s; }
.putar { display: inline-block; width: 12px; height: 12px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: putar .8s linear infinite; vertical-align: -1px; }
.putar.besar { width: 22px; height: 22px; color: var(--aksen-terang); }
@keyframes putar { to { transform: rotate(360deg); } }
.berkas { min-width: 260px; }
.berkas code { overflow-wrap: anywhere; }
.bukti { display: block; margin-top: 3px; padding: 4px 6px; border-radius: 6px; background: var(--kartu-2); font-size: 11.5px; color: var(--teks-2); overflow-wrap: anywhere; white-space: pre-wrap; max-height: 4.5em; overflow: hidden; }
/* cPGuard */
.grafik { display: grid; gap: 8px; margin-bottom: 14px; }
.grafik-kepala { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; font-size: 13.5px; }
.akun-teratas { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; font-size: 13px; }
.chip { border: 1px solid var(--garis); background: transparent; color: var(--teks-2); font: inherit; font-size: 12.5px; padding: 4px 10px; border-radius: 999px; cursor: pointer; }
.chip:hover { border-color: var(--aksen-terang); color: var(--teks-kuat); }
.alat { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; font-size: 13px; }
.alat input[type="search"] { flex: 1 1 220px; min-width: 0; }
.chip-filter { display: flex; gap: 4px; flex-wrap: wrap; }
.chip-filter button { border: 1px solid var(--garis); background: transparent; color: var(--teks-2); font: inherit; font-size: 12.5px; font-weight: 600; padding: 5px 10px; border-radius: 999px; cursor: pointer; }
.chip-filter button.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); color: var(--aksen-terang); }
.ket { font-size: 13px; color: var(--teks-2); overflow-wrap: anywhere; min-width: 180px; }
.blok { display: block; }
.lagi { margin-top: 10px; }
.kejadian { list-style: none; margin: 0; padding: 0; display: grid; }
.kejadian li { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 2px; border-bottom: 1px solid var(--garis); font-size: 13.5px; }
.kejadian li:last-child { border-bottom: 0; }
.kejadian li > div { overflow-wrap: anywhere; }
.kejadian time { font-size: 12.5px; white-space: nowrap; }
.nowrap { white-space: nowrap; }
.kanan { text-align: right; white-space: nowrap; }
.kanan .tombol + .tombol { margin-left: 6px; }
.tabel-wadah { position: relative; overflow-x: auto; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
/* Skeleton */
.skeleton { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; }
.status-muat { margin: 0; }
.skeleton .tile > div { flex: 1; }
.skeleton .tile { min-height: 112px; }
.sk { --sk-dasar: color-mix(in srgb, var(--kartu-2), var(--teks) 7%); --sk-kilap: color-mix(in srgb, var(--kartu-2), var(--teks) 15%);
  display: block; border-radius: 6px; background: linear-gradient(90deg, var(--sk-dasar) 25%, var(--sk-kilap) 50%, var(--sk-dasar) 75%); background-size: 200% 100%; animation: sk-kilau 1.4s ease-in-out infinite; }
.sk-ikon { flex: none; width: 44px; height: 44px; border-radius: 12px; }
.sk-teks { height: 11px; width: 60%; margin: 4px 0; }
.sk-teks.pendek { width: 40%; }
.sk-angka { height: 22px; width: 45%; margin: 4px 0; }
.sk-menu { display: flex; gap: 8px; padding: 8px; border-radius: 12px; background: var(--kartu); border: 1px solid var(--garis); overflow: hidden; }
.sk-pil { flex: none; height: 30px; width: 96px; border-radius: 9px; }
.sk-judul { height: 14px; width: 200px; max-width: 60%; margin-bottom: 18px; }
.sk-baris { display: grid; grid-template-columns: 2fr 1.2fr .8fr .8fr .6fr; gap: 16px; padding: 14px 0; border-top: 1px solid var(--garis); }
.sk-baris .sk { height: 12px; }
@keyframes sk-kilau { from { background-position: 100% 0; } to { background-position: -100% 0; } }
@media (prefers-reduced-motion: reduce) { .sk, .putar { animation: none; } .garis-jalan span { transition: none; } }
@media (max-width: 900px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
  .form-scan { grid-template-columns: 1fr; }
  .form-scan .tombol { justify-self: start; }
}
@media (max-width: 560px) {
  .ringkas { grid-template-columns: 1fr; }
  .nama-saya { width: 100%; }
  .kepala-aksi { width: 100%; }
  .sk-baris { grid-template-columns: 1fr 1fr 1fr; }
  .kejadian li { grid-template-columns: 8px minmax(0, 1fr); }
  .kejadian time { grid-column: 2; }
  .kemajuan { grid-template-columns: auto minmax(0, 1fr); }
  .kemajuan .tombol { grid-column: 1 / -1; justify-self: start; }
  .berkas, .ket { min-width: 0; }
  .tabel { min-width: 560px; }
}
</style>
