<script setup>
// Kerentanan CMS / WordPress (sub-menu Server): versi inti, plugin, dan tema setiap instalasi WP di server hosting
// dicocokkan dengan basis data publik wpvulnerability.net. Data: GET /api/servers/cms (ringkas, tanpa SSH),
// GET /api/servers/cms?server=<host> (detail), POST /api/servers/cms/scan (SSH hanya baca + cocokkan; thread latar).
// cPGuard "CMS Threat" (cms.db) ditampilkan sebagai pembanding selama cPGuard masih jalan. Hanya melapor.
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import Ikon from '../components/Ikon.vue'
import PelakuAkun from '../components/PelakuAkun.vue'
import { namaAkun } from '../akun.js'
import Info from '../components/Info.vue'
import { konfirmasi } from '../konfirmasi.js'
import { minta, kirim, pakaiPolling, tanggalWaktu, waktuLalu, angka } from '../api.js'
import { tabUrl } from '../laravel.js'

const cms = pakaiPolling('/api/servers/cms', 0)
const riwayat = pakaiPolling('/api/servers/cms/riwayat', 0)
const servers = computed(() => cms.data.value?.servers || [])
const job = computed(() => cms.data.value?.job || null)
const berjalan = computed(() => job.value?.status === 'berjalan')
const pilih = tabUrl('s', '')
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || servers.value[0] || null)
const TAB = ['situs', 'komponen', 'cpguard', 'riwayat']
const tab = tabUrl('tab', 'situs', { boleh: TAB })

// Pelaku di riwayat = akun yang masuk ke dash.velocity.ai.id (backend menggantinya dari cookie sesi)
const oleh = namaAkun

const PESAN = {
  invalid_oleh: 'Masuk dulu lewat tombol "Masuk dengan VD.net" di kanan atas — setiap scan dicatat atas nama akun Anda.',
  login_diperlukan: 'Sesi login habis atau belum masuk. Klik "Masuk dengan VD.net" di kanan atas.',
  server_tidak_dikenal: 'Server tidak dikenal; muat ulang halaman.',
  scan_sedang_jalan: 'Masih ada scan CMS berjalan. Tunggu sampai selesai.',
  kunci_ssh_installer_tidak_ada: 'Kunci SSH installer tidak ditemukan di PC dashboard.',
  forbidden: 'Ditolak: hanya bisa dijalankan dari halaman dashboard ini.',
  timeout: 'Server tidak menjawab (timeout).',
}
const pesanGalat = (e) => PESAN[e] || e || 'gagal'
const pesan = reactive({ teks: '', galat: false })
const proses = ref(false)

// ---- Tingkat keparahan ----
const TINGKAT = {
  kritis: { label: 'Kritis', kelas: 'merah', urut: 0 },
  tinggi: { label: 'Tinggi', kelas: 'oranye', urut: 1 },
  sedang: { label: 'Sedang', kelas: 'kuning', urut: 2 },
  rendah: { label: 'Rendah', kelas: 'abu', urut: 3 },
  tidak_diketahui: { label: 'Belum dinilai', kelas: 'abu', urut: 4 },
}
const tk = (t) => TINGKAT[t] || TINGKAT.tidak_diketahui
const JENIS = { core: 'Inti WP', plugin: 'Plugin', theme: 'Tema' }

function tingkatServer(s) {
  const r = s.ringkas
  if (!r) return 'abu'
  if (r.kritis) return 'bahaya'
  if (r.tinggi || r.sedang) return 'waspada'
  return 'baik'
}
const total = computed(() => {
  const acc = { situs: 0, rentan: 0, kritis: 0, tinggi: 0, inti_usang: 0, cpg_rentan: 0, sudah: 0 }
  for (const s of servers.value) {
    if (!s.ringkas) continue
    acc.sudah++
    for (const k of Object.keys(acc)) if (k !== 'sudah') acc[k] += s.ringkas[k] || 0
  }
  return acc
})
const diambilTerlama = computed(() => Math.min(...servers.value.map((s) => s.diambil || Infinity)))

// ---- Scan ----
async function mulaiScan(server) {
  if (!oleh.value.trim()) {
    Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true })
    document.getElementById('nama-cms')?.focus()
    return
  }
  const semua = server === 'semua'
  const ya = await konfirmasi({
    judul: semua ? 'Scan CMS semua server?' : `Scan CMS ${terpilih.value.name}?`,
    teks: 'Server hanya dibaca (daftar instalasi WordPress, versi plugin & tema) dengan prioritas rendah, lalu dicocokkan dengan basis data kerentanan. Tidak ada berkas yang diubah. Biasanya 1–5 menit.',
    tombol: 'Mulai scan',
  })
  if (!ya) return
  proses.value = true
  try {
    await kirim('/api/servers/cms/scan', { server: semua ? 'semua' : terpilih.value.host, oleh: oleh.value.trim() })
    Object.assign(pesan, { teks: 'Scan dimulai.', galat: false })
    await cms.muatUlang()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
// Selama scan berjalan: muat ulang ringkas tiap 3 dtk; sesudah selesai muat detail & riwayat
const timer = setInterval(() => { if (berjalan.value) cms.muatUlang() }, 3000)
onBeforeUnmount(() => clearInterval(timer))
watch(berjalan, (now, dulu) => {
  if (dulu && !now) {
    muatDetail()
    riwayat.muatUlang()
    const j = job.value
    if (j?.status === 'gagal') Object.assign(pesan, { teks: `Scan gagal: ${j.error}`, galat: true })
    else if (j) Object.assign(pesan, { teks: `Scan selesai${j.galat_api ? ` (${j.galat_api} komponen gagal dicek ke basis data kerentanan — dicoba lagi di scan berikutnya)` : ''}.`, galat: !!j.galat_api })
  }
})
const labelKemajuan = computed(() => {
  const k = job.value?.kemajuan
  if (!k) return 'Menyiapkan…'
  return k.tahap === 'inventaris'
    ? `Membaca instalasi WordPress di server (${k.ke}/${k.dari} server selesai)…`
    : `Mencocokkan ${angka(k.dari)} komponen dengan basis data kerentanan (${angka(k.ke)}/${angka(k.dari)})…`
})
const persenKemajuan = computed(() => {
  const k = job.value?.kemajuan
  if (!k || !k.dari) return 3
  return k.tahap === 'inventaris' ? (k.ke / k.dari) * 40 + 3 : 43 + (k.ke / k.dari) * 57
})

// ---- Detail server terpilih ----
const detail = ref(null)
const memuatDetail = ref(false)
// Hasil scan per host disimpan selama tab terbuka (kunci = waktu scan): pindah server/tab/halaman tidak memuat ulang.
// Sesudah server terpilih tampil, hasil server lain diambil diam-diam satu per satu.
async function ambilHasil(s) {
  const c = cacheHasil.get(s.host)
  if (c && c.diambil === s.diambil) return c
  const d = await minta(`/api/servers/cms?server=${encodeURIComponent(s.host)}`)
  if (d.diambil) cacheHasil.set(s.host, d)
  return d
}
async function muatDetail() {
  const s = terpilih.value
  if (!s) return
  if (!s.diambil) { detail.value = { host: s.host, belum: true }; return }
  memuatDetail.value = true
  try {
    const d = await ambilHasil(s)
    if (d.host === terpilih.value?.host) detail.value = d
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    memuatDetail.value = false
  }
  for (const lain of servers.value) {
    if (lain.diambil && lain.host !== s.host) { try { await ambilHasil(lain) } catch { /* dicoba lagi saat dipilih */ } }
  }
}
watch(() => [terpilih.value?.host, terpilih.value?.diambil], () => {
  if (detail.value?.host !== terpilih.value?.host) detail.value = null
  muatDetail()
}, { immediate: true })
watch(pilih, () => { cari.value = ''; filter.value = 'rentan'; buka.value = new Set(); bukaKomp.value = '' })

const kamus = computed(() => detail.value?.kerentanan || {})
const terbaru = computed(() => detail.value?.wp_terbaru)
const lebihLama = (a, b) => {
  const pa = String(a || '').split('.').map(Number); const pb = String(b || '').split('.').map(Number)
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i] || 0; const y = pb[i] || 0
    if (x !== y) return x < y
  }
  return false
}
const intiUsang = (s) => terbaru.value && lebihLama(s.versi, terbaru.value)
const alamat = (s) => `${s.domain}${s.sub || ''}`

// Situs + ringkas keparahan
const situs = computed(() => (detail.value?.situs || []).map((s) => {
  const ids = s.temuan.flatMap((t) => t.id)
  const hitung = { kritis: 0, tinggi: 0, sedang: 0, rendah: 0, tidak_diketahui: 0 }
  for (const i of ids) hitung[kamus.value[i]?.tingkat || 'tidak_diketahui']++
  const terburuk = Object.keys(hitung).find((k) => hitung[k]) || null
  const skor = Math.max(0, ...ids.map((i) => kamus.value[i]?.skor || 0))
  return { ...s, ids, hitung, terburuk, skor, eksploit: ids.some((i) => kamus.value[i]?.dieksploitasi), ditutup: s.temuan.filter((t) => t.ditutup) }
}))
const cari = ref('')
const filter = ref('rentan')
const FILTER = computed(() => [
  { k: 'rentan', label: 'Rentan', n: situs.value.filter((s) => s.ids.length).length },
  { k: 'kritis', label: 'Kritis', n: situs.value.filter((s) => s.hitung.kritis).length },
  { k: 'tinggi', label: 'Tinggi', n: situs.value.filter((s) => s.hitung.tinggi).length },
  { k: 'usang', label: 'Inti WP usang', n: situs.value.filter(intiUsang).length },
  { k: 'ditutup', label: 'Plugin ditutup', n: situs.value.filter((s) => s.ditutup.length).length },
  { k: 'semua', label: 'Semua situs', n: situs.value.length },
])
const situsTersaring = computed(() => {
  const q = cari.value.trim().toLowerCase()
  const f = filter.value
  return situs.value
    .filter((s) => (f === 'semua' || (f === 'rentan' && s.ids.length) || (f === 'kritis' && s.hitung.kritis) || (f === 'tinggi' && s.hitung.tinggi)
      || (f === 'usang' && intiUsang(s)) || (f === 'ditutup' && s.ditutup.length)))
    .filter((s) => !q || alamat(s).toLowerCase().includes(q) || s.user.includes(q)
      || s.temuan.some((t) => t.slug.includes(q) || (t.nama || '').toLowerCase().includes(q)))
    .sort((a, b) => (TINGKAT[a.terburuk]?.urut ?? 9) - (TINGKAT[b.terburuk]?.urut ?? 9) || b.skor - a.skor || b.ids.length - a.ids.length || alamat(a).localeCompare(alamat(b)))
})
const tampil = ref(60)
watch([cari, filter], () => { tampil.value = 60 })
const buka = ref(new Set())
const semuaVuln = ref(new Set())
const urutVuln = (ids) => [...ids].sort((a, b) => tk(kamus.value[a]?.tingkat).urut - tk(kamus.value[b]?.tingkat).urut || (kamus.value[b]?.skor || 0) - (kamus.value[a]?.skor || 0))
const alihBuka = (p) => { const n = new Set(buka.value); n.has(p) ? n.delete(p) : n.add(p); buka.value = n }

// Komponen rentan digabung lintas situs (untuk update massal)
const komponen = computed(() => {
  const peta = new Map()
  for (const s of situs.value) {
    for (const t of s.temuan) {
      if (!t.id.length && !t.ditutup) continue
      const k = `${t.jenis}|${t.slug}|${t.versi}`
      if (!peta.has(k)) peta.set(k, { ...t, situs: [] })
      peta.get(k).situs.push(s)
    }
  }
  return [...peta.values()].map((k) => {
    const v = k.id.map((i) => kamus.value[i]).filter(Boolean)
    const terburuk = v.map((x) => x.tingkat).sort((a, b) => tk(a).urut - tk(b).urut)[0] || null
    return { ...k, v, terburuk, skor: Math.max(0, ...v.map((x) => x.skor || 0)), perbaiki: versiAman(v) }
  }).sort((a, b) => tk(a.terburuk).urut - tk(b.terburuk).urut || b.situs.length - a.situs.length)
})
const cariKomp = ref('')
const komponenTersaring = computed(() => {
  const q = cariKomp.value.trim().toLowerCase()
  return komponen.value.filter((k) => !q || k.slug.includes(q) || (k.nama || '').toLowerCase().includes(q))
})
const bukaKomp = ref('')
// Versi minimum yang menutup semua kerentanan yang diketahui (null bila ada yang belum diperbaiki/tak diketahui)
function versiAman(v) {
  if (!v.length || v.some((x) => x.belum_diperbaiki)) return null
  const angkaVersi = v.map((x) => x.perbaiki).filter((p) => p && !p.startsWith('>'))
  if (!angkaVersi.length) return null
  return angkaVersi.reduce((a, b) => (lebihLama(a, b) ? b : a))
}

// ---- cPGuard pembanding ----
const cpg = computed(() => detail.value?.cpguard)
const cpgSitus = computed(() => {
  const kita = new Map(situs.value.map((s) => [s.path, s]))
  return (cpg.value?.situs || [])
    .filter((c) => String(c.rating || 'safe').toLowerCase() !== 'safe')
    .map((c) => ({ ...c, kita: kita.get(c.path) }))
    .sort((a, b) => (parseFloat(b.skor) || 0) - (parseFloat(a.skor) || 0))
})
const cpgKelas = (r) => ({ critical: 'merah', high: 'oranye', medium: 'kuning', low: 'abu' }[String(r || '').toLowerCase()] || 'abu')
const relatif = (p) => (p || '').replace(/^\/home\/[^/]+\/domains\//, '').replace(/\/public_html/, '')

const riwayatServer = computed(() => (riwayat.data.value?.riwayat || []))
const durasi = (j) => {
  const d = (j.selesai || Math.floor(Date.now() / 1000)) - j.mulai
  return d >= 60 ? `${Math.floor(d / 60)} mnt ${d % 60} dtk` : `${d} dtk`
}
</script>

<script>
const cacheHasil = new Map()
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Kerentanan CMS</h1>
        <p class="redup">Versi WordPress, plugin, dan tema setiap situs klien dicocokkan dengan basis data kerentanan publik. Hanya melapor — pembaruan tetap dikerjakan tim.</p>
      </div>
      <div class="kepala-aksi">
        <div class="nama-saya"><span class="redup">Dicatat sebagai</span><PelakuAkun id="nama-cms" /></div>
        <button type="button" class="tombol kecil" :disabled="proses || berjalan || !servers.length" @click="mulaiScan('semua')"><Ikon nama="cari" :ukuran="16" /> Scan semua server</button>
      </div>
    </header>

    <p v-if="cms.memuat.value && !cms.data.value" class="redup" role="status">Memuat…</p>
    <p v-else-if="cms.galat.value && !cms.data.value" class="pesan-status bahaya">Gagal memuat: {{ cms.galat.value.message }}</p>

    <template v-else-if="cms.data.value">
      <div class="ringkas">
        <div class="kartu tile">
          <span class="tile-ikon biru"><Ikon nama="cms" :ukuran="20" /></span>
          <div><span class="redup">Situs WordPress</span><b>{{ angka(total.situs) }}</b><small class="redup">{{ total.sudah }} / {{ servers.length }} server sudah di-scan</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon merah"><Ikon nama="peringatan" :ukuran="20" /></span>
          <div><span class="redup">Situs rentan</span><b>{{ angka(total.rentan) }}</b><small class="redup">{{ angka(total.kritis) }} kritis · {{ angka(total.tinggi) }} tinggi</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon kuning"><Ikon nama="ulang" :ukuran="20" /></span>
          <div><span class="redup">Inti WP belum terbaru</span><b>{{ angka(total.inti_usang) }}</b><small class="redup">terbaru {{ servers.find((s) => s.wp_terbaru)?.wp_terbaru || '-' }}</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon ungu"><Ikon nama="perisai" :ukuran="20" /></span>
          <div><span class="redup">Rentan menurut cPGuard</span><b>{{ angka(total.cpg_rentan) }}</b><small class="redup">{{ total.sudah ? `scan ${waktuLalu(diambilTerlama)}` : 'pembanding' }}</small></div>
        </div>
      </div>

      <div v-if="berjalan" class="kemajuan kartu" role="status">
        <span class="putar besar" aria-hidden="true" />
        <div>
          <b>Scan CMS {{ job.target === 'semua' ? 'semua server' : job.server.join(', ') }}</b>
          <span class="redup"> · {{ job.oleh }} · {{ durasi(job) }}</span>
          <div class="redup kecil-teks">{{ labelKemajuan }}</div>
          <div class="garis-jalan"><span :style="{ width: `${persenKemajuan}%` }" /></div>
        </div>
      </div>

      <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>

      <nav class="sub-menu" aria-label="Pilih server">
        <button v-for="s in servers" :key="s.host" type="button" :class="{ aktif: terpilih === s }" :aria-current="terpilih === s ? 'page' : undefined" @click="pilih = s.name">
          <span class="titik" :class="tingkatServer(s)" aria-hidden="true" /> {{ s.name }}
          <span v-if="s.ringkas?.rentan" class="hitung-menu">{{ s.ringkas.rentan }}</span>
        </button>
      </nav>

      <section v-if="terpilih" class="kartu" aria-labelledby="judul-cms">
        <div class="kartu-judul">
          <h2 id="judul-cms"><Ikon nama="cms" :ukuran="16" /> {{ terpilih.name }}
            <small v-if="terpilih.diambil" class="redup">{{ angka(terpilih.ringkas?.situs) }} situs · scan {{ waktuLalu(terpilih.diambil) }} oleh {{ terpilih.oleh }}</small>
          </h2>
          <div class="judul-kanan">
            <div v-if="terpilih.diambil" class="tab" role="tablist" aria-label="Bagian CMS">
              <button v-for="t in [
                { k: 'situs', label: 'Situs', n: terpilih.ringkas?.rentan },
                { k: 'komponen', label: 'Komponen rentan', n: komponen.length },
                { k: 'cpguard', label: 'cPGuard', n: terpilih.ringkas?.cpg_rentan },
                { k: 'riwayat', label: 'Riwayat scan' },
              ]" :key="t.k" type="button" role="tab" :aria-selected="tab === t.k" :class="{ aktif: tab === t.k }" @click="tab = t.k">
                {{ t.label }} <span v-if="t.n !== undefined" class="hitung">{{ t.n }}</span>
              </button>
            </div>
            <button type="button" class="tombol garis kecil" :disabled="proses || berjalan" @click="mulaiScan(terpilih.host)"><Ikon nama="ulang" :ukuran="15" /> Scan server ini</button>
          </div>
        </div>

        <div v-if="!terpilih.diambil" class="kosong">
          <p><b>Server ini belum pernah di-scan.</b></p>
          <p class="redup">Tekan <b>Scan server ini</b> untuk membaca semua instalasi WordPress (hanya baca, prioritas rendah) lalu mencocokkannya dengan basis data kerentanan.</p>
        </div>
        <p v-else-if="!detail && memuatDetail" class="redup" role="status">Memuat hasil scan…</p>

        <template v-else-if="detail && !detail.belum">
          <p v-if="detail.terpotong" class="pesan-status bahaya">Daftar terpotong di 3.000 instalasi.</p>

          <!-- ================= Situs ================= -->
          <template v-if="tab === 'situs'">
            <div class="alat">
              <input v-model="cari" type="search" placeholder="Cari domain / akun / plugin" aria-label="Cari situs">
              <div class="chip-filter" role="group" aria-label="Saring situs">
                <button v-for="f in FILTER" :key="f.k" type="button" :class="{ aktif: filter === f.k }" @click="filter = f.k">{{ f.label }} {{ f.n }}</button>
              </div>
            </div>
            <p v-if="!situsTersaring.length" class="bersih"><Ikon nama="centang" :ukuran="18" /> {{ filter === 'semua' ? 'Tidak ada situs WordPress.' : 'Tidak ada situs di saringan ini.' }}</p>
            <div v-else class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">Situs</th><th scope="col">WordPress</th><th scope="col">Kerentanan</th><th scope="col">Komponen rentan</th><th scope="col"><span class="sr">Rincian</span></th></tr></thead>
                <tbody>
                  <template v-for="s in situsTersaring.slice(0, tampil)" :key="s.path">
                    <tr :class="{ dibuka: buka.has(s.path) }">
                      <td class="situs-sel">
                        <a :href="`https://${alamat(s)}`" target="_blank" rel="noopener noreferrer">{{ alamat(s) }}</a>
                        <small class="redup blok">{{ s.user }} · {{ s.plugin.length }} plugin · {{ s.tema.length }} tema</small>
                      </td>
                      <td class="nowrap">
                        {{ s.versi }}
                        <span v-if="intiUsang(s)" class="lencana kuning" :title="`Versi terbaru ${terbaru}`">USANG</span>
                      </td>
                      <td class="sel-lencana">
                        <template v-if="s.ids.length">
                          <span v-for="(n, t) in s.hitung" v-show="n" :key="t" class="lencana" :class="tk(t).kelas">{{ n }} {{ tk(t).label }}</span>
                          <span v-if="s.eksploit" class="lencana merah" title="Sudah dieksploitasi di dunia nyata (KEV / SSVC)">DIEKSPLOITASI</span>
                        </template>
                        <span v-else class="hijau-teks">Aman</span>
                      </td>
                      <td class="ket">
                        <span v-for="t in s.temuan.filter((x) => x.id.length || x.ditutup).slice(0, 4)" :key="t.jenis + t.slug" class="komp">{{ t.jenis === 'core' ? 'WordPress' : t.slug }} <span class="redup">{{ t.versi }}</span></span>
                        <span v-if="s.temuan.filter((x) => x.id.length || x.ditutup).length > 4" class="redup">+{{ s.temuan.filter((x) => x.id.length || x.ditutup).length - 4 }}</span>
                      </td>
                      <td class="kanan">
                        <button v-if="s.temuan.length" type="button" class="tombol garis kecil" :aria-expanded="buka.has(s.path)" @click="alihBuka(s.path)">{{ buka.has(s.path) ? 'Tutup' : 'Rincian' }}</button>
                      </td>
                    </tr>
                    <tr v-if="buka.has(s.path)" class="baris-rinci">
                      <td colspan="5">
                        <div class="rinci-isi">
                        <p class="redup kecil-teks"><code>{{ s.path }}</code><template v-if="s.mu_plugin.length"> · mu-plugins: {{ s.mu_plugin.join(', ') }}</template></p>
                        <div v-for="t in s.temuan" :key="t.jenis + t.slug" class="rinci-komp">
                          <div class="rinci-kepala">
                            <span class="lencana abu">{{ JENIS[t.jenis] }}</span>
                            <b>{{ t.nama || t.slug }}</b> <span class="redup">{{ t.slug }} · versi {{ t.versi || '?' }}</span>
                            <span v-if="t.ditutup" class="lencana merah" :title="t.alasan_tutup || ''">DITUTUP DI WORDPRESS.ORG{{ t.alasan_tutup ? ` · ${t.alasan_tutup}` : '' }}</span>
                            <span v-if="t.jenis !== 'core' && versiAman(t.id.map((i) => kamus[i]).filter(Boolean))" class="hijau-teks kecil-teks">perbarui ke ≥ {{ versiAman(t.id.map((i) => kamus[i]).filter(Boolean)) }}</span>
                            <span v-else-if="t.jenis === 'core' && terbaru" class="hijau-teks kecil-teks">perbarui ke {{ terbaru }}</span>
                          </div>
                          <ul class="daftar-vuln">
                            <li v-for="i in urutVuln(t.id).slice(0, semuaVuln.has(s.path + t.slug) ? undefined : 5)" :key="i">
                              <span class="lencana" :class="tk(kamus[i]?.tingkat).kelas">{{ kamus[i]?.skor ?? '–' }} {{ tk(kamus[i]?.tingkat).label }}</span>
                              <a v-if="kamus[i]?.link" :href="kamus[i].link" target="_blank" rel="noopener noreferrer">{{ kamus[i]?.judul }}</a><span v-else>{{ kamus[i]?.judul }}</span>
                              <small class="redup"> {{ kamus[i]?.cve.join(', ') }}<template v-if="kamus[i]?.perbaiki"> · diperbaiki {{ kamus[i].perbaiki }}</template><template v-if="kamus[i]?.belum_diperbaiki"> · <b class="merah-teks">belum ada perbaikan</b></template></small>
                            </li>
                          </ul>
                          <button v-if="t.id.length > 5 && !semuaVuln.has(s.path + t.slug)" type="button" class="tombol garis kecil lagi" @click="semuaVuln = new Set([...semuaVuln, s.path + t.slug])">Tampilkan semua {{ t.id.length }} kerentanan</button>
                        </div>
                        </div>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
            <button v-if="situsTersaring.length > tampil" type="button" class="tombol garis kecil lagi" @click="tampil += 200">Tampilkan lebih banyak ({{ situsTersaring.length - tampil }} lagi)</button>
          </template>

          <!-- ================= Komponen ================= -->
          <template v-else-if="tab === 'komponen'">
            <p class="redup kecil-teks">Plugin/tema/versi inti yang sama digabung — berguna untuk memperbarui satu plugin di banyak situs sekaligus.</p>
            <div class="alat"><input v-model="cariKomp" type="search" placeholder="Cari plugin / tema" aria-label="Cari komponen"></div>
            <p v-if="!komponenTersaring.length" class="bersih"><Ikon nama="centang" :ukuran="18" /> Tidak ada komponen rentan.</p>
            <div v-else class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">Komponen</th><th scope="col">Versi</th><th scope="col">Terburuk</th><th scope="col">Perbarui ke</th><th scope="col">Situs</th></tr></thead>
                <tbody>
                  <template v-for="k in komponenTersaring" :key="k.jenis + k.slug + k.versi">
                    <tr>
                      <td class="ket"><span class="lencana abu">{{ JENIS[k.jenis] }}</span> <b>{{ k.jenis === 'core' ? 'WordPress' : (k.nama || k.slug) }}</b>
                        <small class="redup blok">{{ k.slug }} · {{ k.v.length }} kerentanan<template v-if="k.ditutup"> · <b class="merah-teks">ditutup di wordpress.org</b></template></small></td>
                      <td class="nowrap">{{ k.versi || '?' }}</td>
                      <td class="nowrap"><span v-if="k.terburuk" class="lencana" :class="tk(k.terburuk).kelas">{{ k.skor || '–' }} {{ tk(k.terburuk).label }}</span></td>
                      <td class="nowrap">{{ k.jenis === 'core' ? terbaru : (k.perbaiki || (k.v.some((x) => x.belum_diperbaiki) ? 'belum ada' : '-')) }}</td>
                      <td class="nowrap"><button type="button" class="tombol garis kecil" :aria-expanded="bukaKomp === k.jenis + k.slug + k.versi" @click="bukaKomp = bukaKomp === k.jenis + k.slug + k.versi ? '' : k.jenis + k.slug + k.versi">{{ k.situs.length }} situs</button></td>
                    </tr>
                    <tr v-if="bukaKomp === k.jenis + k.slug + k.versi" class="baris-rinci">
                      <td colspan="5"><span v-for="s in k.situs" :key="s.path" class="komp">{{ alamat(s) }} <span class="redup">{{ s.user }}</span></span></td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </template>

          <!-- ================= cPGuard ================= -->
          <template v-else-if="tab === 'cpguard'">
            <p class="redup kecil-teks">"CMS Threat" cPGuard dari <code>cms.db</code> saat scan terakhir — pembanding selama cPGuard masih jalan ({{ detail.cpguard_jalan ? 'jalan' : 'TIDAK jalan' }}).
              <Info label="Tentang pembanding cPGuard" rata="kanan"><p>cPGuard memperbarui datanya tiap malam ±02:00 dan menyimpan isu komponen yang sudah tidak terpasang; yang ditampilkan hanya komponen yang masih terpasang. Selisih wajar terjadi karena basis data kerentanannya berbeda.</p></Info>
            </p>
            <p v-if="!cpg" class="redup">cPGuard tidak terpasang di server ini.</p>
            <p v-else-if="cpg.error" class="pesan-status bahaya">cms.db tidak terbaca: {{ cpg.error }}</p>
            <p v-else-if="!cpgSitus.length" class="bersih"><Ikon nama="centang" :ukuran="18" /> cPGuard tidak menandai situs mana pun.</p>
            <div v-else class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">Situs</th><th scope="col">cPGuard</th><th scope="col">Isu cPGuard</th><th scope="col">Scan Velocity</th></tr></thead>
                <tbody>
                  <tr v-for="c in cpgSitus" :key="c.path">
                    <td class="situs-sel"><code>{{ relatif(c.path) }}</code><small class="redup blok">WP {{ c.versi || '?' }} · {{ c.waktu }}<template v-if="c.galat"> · <span class="kuning-teks">ada galat refresh</span></template></small></td>
                    <td class="nowrap"><span class="lencana" :class="cpgKelas(c.rating)">{{ c.skor }} {{ c.rating }}</span></td>
                    <td class="ket">
                      <span v-for="(x, i) in c.isu.slice(0, 4)" :key="i" class="blok">{{ x.slug || 'inti' }} <span class="redup">{{ x.versi }}</span> — {{ x.judul }}<template v-if="x.patch"> <span class="hijau-teks">→ {{ x.patch }}</span></template></span>
                      <span v-if="c.isu.length > 4" class="redup">+{{ c.isu.length - 4 }} lainnya</span>
                    </td>
                    <td class="nowrap">
                      <span v-if="!c.kita" class="redup">tidak ditemukan</span>
                      <span v-else-if="c.kita.ids.length" class="lencana" :class="tk(c.kita.terburuk).kelas">{{ c.kita.ids.length }} temuan</span>
                      <span v-else class="hijau-teks">Aman</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>

          <!-- ================= Riwayat ================= -->
          <template v-else-if="tab === 'riwayat'">
            <p v-if="!riwayatServer.length" class="redup">Belum ada riwayat scan.</p>
            <ul v-else class="kejadian">
              <li v-for="r in riwayatServer" :key="r.id">
                <span class="titik" :class="r.status === 'selesai' ? 'baik' : 'bahaya'" aria-hidden="true" />
                <div>
                  <b>{{ r.target === 'semua' ? 'Semua server' : (r.hasil?.[0]?.server || r.target) }}</b>
                  <span v-if="r.status !== 'selesai'" class="lencana merah">GAGAL · {{ r.error }}</span>
                  <small class="redup blok">{{ r.oleh }} · {{ durasi(r) }}<template v-for="h in r.hasil || []" :key="h.host"> · {{ h.server }}: {{ h.ok ? `${h.rentan}/${h.situs} rentan` : `gagal (${pesanGalat(h.error)})` }}</template></small>
                </div>
                <time class="redup">{{ tanggalWaktu(r.mulai) }}</time>
              </li>
            </ul>
          </template>

          <p class="redup kaki">Sumber: <a :href="cms.data.value.sumber" target="_blank" rel="noopener noreferrer">wpvulnerability.net</a> (CVE, Wordfence, WPScan, Patchstack), cache 24 jam.
            Plugin/tema premium atau buatan sendiri yang tidak ada di wordpress.org bisa tidak terdeteksi.</p>
        </template>
      </section>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.kepala-aksi { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.nama-saya { display: grid; gap: 4px; font-size: 12px; }

.ringkas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.tile { display: flex; gap: 14px; align-items: center; }
.tile > div { display: grid; gap: 3px; min-width: 0; }
.tile b { font-size: 24px; color: var(--teks-kuat); }
.tile small { font-size: 12px; }
.tile-ikon { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; }
.tile-ikon.merah { color: var(--bahaya); background: color-mix(in srgb, var(--bahaya) 15%, transparent); }
.tile-ikon.kuning { color: var(--waspada); background: color-mix(in srgb, var(--waspada) 15%, transparent); }
.tile-ikon.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 15%, transparent); }
.tile-ikon.biru { color: var(--aksen-terang); background: var(--aksen-lembut); }
.kartu-judul { flex-wrap: wrap; gap: 10px; }
.kartu-judul h2 { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.kartu-judul h2 small { font-size: 12.5px; font-weight: 400; }
.judul-kanan { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.sub-menu { display: flex; gap: 4px; padding: 4px; border-radius: 12px; background: var(--kartu); border: 1px solid var(--garis); overflow-x: auto; }
.sub-menu button { display: inline-flex; align-items: center; gap: 7px; flex: none; border: 0; background: transparent; color: var(--teks-2);
  font: inherit; font-size: 13.5px; font-weight: 600; padding: 9px 14px; border-radius: 9px; cursor: pointer; }
.sub-menu button:hover { color: var(--teks-kuat); background: var(--sorot); }
.sub-menu button.aktif { background: var(--aksen); color: #fff; }
.hitung-menu { font-size: 11.5px; padding: 1px 7px; border-radius: 999px; background: color-mix(in srgb, var(--bahaya) 18%, transparent); color: var(--bahaya); }
.sub-menu button.aktif .hitung-menu { background: rgb(255 255 255 / .22); color: #fff; }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); vertical-align: 1px; }
.titik.baik { background: var(--baik); }
.titik.waspada { background: var(--waspada); }
.titik.bahaya { background: var(--bahaya); }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
.lencana.oranye { color: #e0782f; background: color-mix(in srgb, #e0782f 15%, transparent); }
.lencana + .lencana { margin-left: 4px; }
.sel-lencana { max-width: 250px; line-height: 1.9; }
.sel-lencana .lencana { white-space: nowrap; }
.kosong { padding: 18px 4px; }
.kosong p { margin: 0 0 6px; }
.kemajuan { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 14px; align-items: center; font-size: 13.5px; }
.garis-jalan { height: 6px; border-radius: 3px; background: var(--garis); overflow: hidden; margin-top: 8px; }
.garis-jalan span { display: block; height: 100%; background: var(--aksen); border-radius: 3px; transition: width .4s; }
.putar { display: inline-block; width: 12px; height: 12px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: putar .8s linear infinite; }
.putar.besar { width: 22px; height: 22px; color: var(--aksen-terang); }
@keyframes putar { to { transform: rotate(360deg); } }
.alat { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; font-size: 13px; }
.alat input[type="search"] { flex: 1 1 220px; min-width: 0; }
.chip-filter { display: flex; gap: 4px; flex-wrap: wrap; }
.chip-filter button { border: 1px solid var(--garis); background: transparent; color: var(--teks-2); font: inherit; font-size: 12.5px; font-weight: 600; padding: 5px 10px; border-radius: 999px; cursor: pointer; }
.chip-filter button.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); color: var(--aksen-terang); }
.bersih { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--baik); font-weight: 600; }
.situs-sel { min-width: 220px; overflow-wrap: anywhere; }
.situs-sel a { color: var(--teks-kuat); font-weight: 600; text-decoration: none; }
.situs-sel a:hover { text-decoration: underline; }
.ket { font-size: 13px; color: var(--teks-2); overflow-wrap: anywhere; min-width: 180px; }
.komp { display: inline-block; margin: 0 8px 3px 0; font-size: 12.5px; }
.blok { display: block; }
.nowrap { white-space: nowrap; }
.kanan { text-align: right; white-space: nowrap; }
tr.dibuka td { border-bottom-color: transparent; }
.baris-rinci td { background: var(--kartu-2); padding: 12px 14px; }
.rinci-komp { padding: 8px 0; border-top: 1px solid var(--garis); }
.rinci-komp:first-of-type { border-top: 0; }
.rinci-kepala { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 13.5px; }
.daftar-vuln { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 5px; font-size: 13px; }
.daftar-vuln li { overflow-wrap: anywhere; }
.daftar-vuln .lencana { margin-right: 6px; }
.daftar-vuln small { margin-left: 4px; }
.daftar-vuln a { color: var(--teks); }
.kecil-teks { font-size: 12.5px; }
.merah-teks { color: var(--bahaya); }
.kuning-teks { color: var(--waspada); }
.hijau-teks { color: var(--baik); }
.lagi { margin-top: 10px; }
.kaki { margin: 16px 0 0; font-size: 12.5px; }
.kaki a { color: inherit; }
.kejadian { list-style: none; margin: 0; padding: 0; display: grid; }
.kejadian li { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 2px; border-bottom: 1px solid var(--garis); font-size: 13.5px; }
.kejadian li:last-child { border-bottom: 0; }
.kejadian li > div { overflow-wrap: anywhere; }
.kejadian time { font-size: 12.5px; white-space: nowrap; }
.tabel-wadah { position: relative; overflow-x: auto; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); overflow-wrap: anywhere; }
@media (prefers-reduced-motion: reduce) { .putar { animation: none; } .garis-jalan span { transition: none; } }
@media (max-width: 900px) { .ringkas { grid-template-columns: 1fr 1fr; } }
@media (max-width: 560px) {
  .ringkas { grid-template-columns: 1fr; }
  .nama-saya { width: 100%; }
  .kepala-aksi { width: 100%; }
  .kejadian li { grid-template-columns: 8px minmax(0, 1fr); }
  .kejadian time { grid-column: 2; }
  .situs-sel, .ket { min-width: 0; }
  .tabel { min-width: 620px; }
  /* Rincian tetap selebar layar walau tabel digulir menyamping */
  .rinci-isi { position: sticky; left: 14px; width: calc(100vw - 92px); }
}
</style>
