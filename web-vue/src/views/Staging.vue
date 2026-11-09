<script setup>
// Panel staging lokal: pengganti DirectAdmin akun vdcenterbiz di PC ini.
// Aksi (login, log, cron, DB, cadangan) = services/staging_aksi.py; pekerjaan berat satu per satu di latar.
// API: GET /api/fm/staging[?segar=1] (services/staging_lokal.py; pindai + du di latar, cache 1 jam).
// Cek HTTP per situs atas klik (/api/fm/staging/http): cek massal memenuhi pool FPM (2 Nov).
import { ref, computed, reactive, watch, onMounted, onBeforeUnmount } from 'vue'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import { pakaiPolling, minta, kirim, ukuranBerkas, waktuLalu, tanggalWaktu } from '../api.js'

const st = pakaiPolling('/api/fm/staging', 60000)
const d = computed(() => st.data.value)
const situs = computed(() => d.value?.situs || [])

const httpBaik = (k) => k >= 200 && k < 400

const SARING = [
  { nilai: 'semua', label: 'Semua', cocok: () => true },
  { nilai: 'wordpress', label: 'WordPress', cocok: (s) => s.jenis === 'wordpress' },
  { nilai: 'laravel', label: 'Laravel', cocok: (s) => s.jenis === 'laravel' },
  { nilai: 'lain', label: 'Lainnya', cocok: (s) => s.jenis === 'lain' || s.jenis === 'kosong' },
]
const saring = ref('semua')
const cari = ref('')
const urut = ref('nama')
const jumlah = (f) => situs.value.filter(f.cocok).length
const tampil = computed(() => {
  const f = SARING.find((x) => x.nilai === saring.value)
  const q = cari.value.trim().toLowerCase()
  const hasil = situs.value.filter((s) => f.cocok(s) && (!q || s.nama.toLowerCase().includes(q) || (s.db || '').toLowerCase().includes(q)))
  if (urut.value === 'disk') return [...hasil].sort((a, b) => (b.disk || 0) - (a.disk || 0))
  if (urut.value === 'db') return [...hasil].sort((a, b) => (b.db_ukuran || 0) - (a.db_ukuran || 0))
  return hasil
})

const LABEL_JENIS = { wordpress: 'WordPress', laravel: 'Laravel', lain: 'Lainnya', kosong: 'Kosong' }
const KELAS_JENIS = { wordpress: 'biru', laravel: 'hijau', lain: 'abu', kosong: 'kuning' }
const ukuran = (n) => (n == null ? '-' : ukuranBerkas(n))
const tautanBerkas = (p) => ({ path: '/berkas', query: { path: p } })

const totalDb = computed(() => situs.value.reduce((n, s) => n + (s.db_ukuran || 0), 0) + (d.value?.db_yatim || []).reduce((n, x) => n + x.ukuran, 0))
const layananMati = computed(() => Object.entries(d.value?.layanan || {}).filter(([, aktif]) => !aktif).map(([n]) => n))
const persenPartisi = computed(() => {
  const p = d.value?.partisi
  return p ? Math.round((p.terpakai / p.total) * 100) : 0
})

// Hasil cek HTTP hanya di halaman ini, per nama situs
const hasilHttp = reactive({})
const mengecek = ref('')
async function cekHttp(s) {
  mengecek.value = s.nama
  try {
    hasilHttp[s.nama] = await minta(`/api/fm/staging/http?nama=${encodeURIComponent(s.nama)}`)
  } catch (e) { hasilHttp[s.nama] = { galat: e.message } } finally { mengecek.value = '' }
}
const PESAN_HTTP = { situs_tidak_dikenal: 'Pindai ulang dulu', sedang_mengecek: 'Sedang dipakai, coba lagi' }

// Pesan galat dari API; kode bisa berekor rincian ("dump_ditolak: USE x")
const PESAN = {
  forbidden: 'Hanya bisa dari jaringan kantor atau Tailscale.',
  situs_tidak_dikenal: 'Situs tidak ada di hasil pindai. Pindai ulang dulu.',
  folder_situs_tidak_valid: 'Folder situs tidak valid.',
  konfirmasi_salah: 'Nama situs yang diketik tidak cocok.',
  sedang_ada_pekerjaan: 'Masih ada pekerjaan berjalan, tunggu selesai dulu.',
  ruang_cadangan_kurang: 'Ruang disk untuk cadangan kurang.',
  situs_tanpa_database: 'Situs ini tidak punya database yang terbaca.',
  dump_ditolak: 'Dump ditolak karena memuat perintah yang bisa menyentuh database lain',
  user_db_dipakai_situs_lain: 'User database ini dipakai juga oleh situs lain',
  cron_sudah_berubah: 'Cron sudah diubah orang lain. Muat ulang halaman dulu.',
  cron_ditolak: 'Format cron ditolak',
  nama_situs_tidak_valid: 'Nama hanya boleh huruf kecil, angka, titik, dan tanda hubung.',
  situs_sudah_ada: 'Situs dengan nama ini sudah ada.',
  database_sudah_ada: 'Nama database bentrok, coba lagi.',
  memuat_situs_lain: 'Tidak bisa dihapus, folder ini memuat situs lain',
  database_dipakai_situs_lain: 'Tidak bisa dihapus, database dipakai juga oleh',
  masih_dipakai_cron: 'Tidak bisa dihapus, hapus dulu baris cron ini',
  sedang_dipakai_proses: 'Tidak bisa dihapus, sedang dipakai proses',
}
function pesanGalat(e) {
  const teks = e?.message || String(e)
  const [kode, ...sisa] = teks.split(': ')
  return PESAN[kode] ? [PESAN[kode], sisa.join(': ')].filter(Boolean).join(': ') : teks
}

const kerja = computed(() => d.value?.pekerjaan?.aktif)
const terakhir = computed(() => d.value?.pekerjaan?.terakhir)
const LABEL_KERJA = { cadangan: 'Cadangan', pulihkan: 'Pulihkan', impor: 'Impor DB', 'sandi-db': 'Ganti sandi DB', hapus: 'Hapus situs' }
let pantau = null
onMounted(() => { pantau = setInterval(() => { if (kerja.value) st.muatUlang() }, 4000) })
onBeforeUnmount(() => clearInterval(pantau))

const galatMasuk = ref('')
async function masukAdmin(s) {
  // Tab dibuka lebih dulu: sesudah await peramban akan memblokirnya sebagai popup
  const tab = window.open('about:blank', '_blank')
  galatMasuk.value = ''
  try {
    const r = await kirim('/api/fm/staging/masuk', { nama: s.nama })
    tab.opener = null
    tab.location = r.url
  } catch (e) {
    tab?.close()
    galatMasuk.value = `${s.nama}: ${pesanGalat(e)}`
  }
}

// Dialog Kelola per situs
const kelola = reactive({ buka: false, s: null, sumber: 'php', baris: null, cadangan: [], galat: '', proses: false })
function bukaKelola(s) {
  Object.assign(kelola, { buka: true, s, sumber: 'php', baris: null, cadangan: [], galat: '' })
  muatLog()
  muatCadangan()
}
async function aksiKelola(f) {
  kelola.galat = ''
  kelola.proses = true
  try { await f() } catch (e) { kelola.galat = pesanGalat(e) } finally { kelola.proses = false }
}
const namaUrl = () => encodeURIComponent(kelola.s.nama)
const muatLog = () => aksiKelola(async () => {
  kelola.baris = (await minta(`/api/fm/staging/log?nama=${namaUrl()}&sumber=${kelola.sumber}`)).baris
})
const muatCadangan = () => aksiKelola(async () => {
  kelola.cadangan = (await minta(`/api/fm/staging/cadangan?nama=${namaUrl()}`)).cadangan
})
const buatCadangan = () => aksiKelola(async () => {
  await kirim('/api/fm/staging/cadangan', { nama: kelola.s.nama })
  await st.muatUlang()
})
watch(() => terakhir.value?.selesai, () => { if (kelola.buka) muatCadangan() })

// Aksi berbahaya: nama situs wajib diketik, peladen memeriksa ulang
const konfirm = reactive({ buka: false, judul: '', teks: '', tombol: '', ketik: '', jalankan: null })
function minta_konfirmasi(judul, teks, tombol, jalankan) {
  Object.assign(konfirm, { buka: true, judul, teks, tombol, ketik: '', jalankan })
}
async function setujui() {
  const f = konfirm.jalankan
  const konfirmasi = konfirm.ketik
  konfirm.buka = false
  await aksiKelola(async () => { await f(konfirmasi); await st.muatUlang() })
}
function konfirmPulihkan(c) {
  minta_konfirmasi('Pulihkan cadangan', `Berkas${c.ada_db ? ' dan database' : ''} ${kelola.s.nama} akan diganti dengan cadangan ${tanggalWaktu(c.waktu)}. Perubahan sesudah itu hilang, tapi kondisi sekarang dicadangkan otomatis lebih dulu.`, 'Pulihkan',
    (konfirmasi) => kirim('/api/fm/staging/pulihkan', { nama: kelola.s.nama, id: c.id, konfirmasi }))
}
function konfirmSandi() {
  minta_konfirmasi('Ganti sandi database', `Sandi user database ${kelola.s.db} diganti dengan sandi acak, dan konfigurasi situs ikut diperbarui. Alat lain yang masih menyimpan sandi lama perlu diperbarui manual.`, 'Ganti sandi',
    (konfirmasi) => kirim('/api/fm/staging/db/sandi', { nama: kelola.s.nama, konfirmasi }))
}
function konfirmHapusSitus() {
  const s = kelola.s
  minta_konfirmasi('Hapus situs', `Folder ${s.nama}${s.db ? ` dan database ${s.db} beserta usernya` : ''} akan dihapus dari staging. Cadangan dibuat otomatis lebih dulu dan tetap tersimpan di PC lokal. Pastikan tiket CRM situs ini tidak lagi memakai staging.`, 'Hapus situs',
    async (konfirmasi) => {
      await kirim('/api/fm/staging/hapus', { nama: s.nama, konfirmasi })
      kelola.buka = false
    })
}
const hapusCadangan = (c) => aksiKelola(async () => {
  await kirim('/api/fm/staging/cadangan/hapus', { nama: kelola.s.nama, id: c.id })
  await muatCadangan()
})
const berkasImpor = ref(null)
function pilihImpor(e) {
  const f = e.target.files?.[0]
  e.target.value = ''
  if (!f) return
  berkasImpor.value = f
  minta_konfirmasi('Impor database', `${f.name} (${ukuranBerkas(f.size)}) akan diimpor ke ${kelola.s.db}. Tabel yang sama di dump akan tertimpa. Situs dan database dicadangkan otomatis lebih dulu.`, 'Impor',
    async (konfirmasi) => {
      const r = await fetch(`/api/fm/staging/db/impor?nama=${namaUrl()}&konfirmasi=${encodeURIComponent(konfirmasi)}`, { method: 'PUT', body: f })
      const j = await r.json().catch(() => ({}))
      if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`)
    })
}

// Situs baru: sandi hanya ditampilkan sekali, tidak disimpan di mana pun
const baru = reactive({ buka: false, nama: '', galat: '', proses: false, hasil: null, tersalin: false })
function bukaBaru() {
  Object.assign(baru, { buka: true, nama: '', galat: '', proses: false, hasil: null, tersalin: false })
}
async function buatSitus() {
  baru.proses = true
  baru.galat = ''
  try {
    baru.hasil = await kirim('/api/fm/staging/buat', { nama: baru.nama })
    await st.muatUlang()
  } catch (e) { baru.galat = pesanGalat(e) } finally { baru.proses = false }
}
async function salinHasil() {
  const h = baru.hasil
  const teks = `Folder: ${h.path}\nAlamat: ${h.url}\nDB: ${h.db}\nUser DB: ${h.user}\nSandi DB: ${h.sandi}`
  try {
    await navigator.clipboard.writeText(teks)
  } catch {
    // http LAN bukan secure context: clipboard API tak tersedia, pakai cara lama
    const t = document.createElement('textarea')
    t.value = teks
    t.style.position = 'fixed'
    t.style.opacity = '0'
    document.body.appendChild(t)
    t.select()
    document.execCommand('copy')
    t.remove()
  }
  baru.tersalin = true
}

// Cron
const cron = reactive({ sunting: false, teks: '', dasar: '', galat: '', proses: false })
function suntingCron() {
  Object.assign(cron, { sunting: true, teks: d.value.cron_teks, dasar: d.value.cron_teks, galat: '' })
}
async function simpanCron() {
  cron.proses = true
  cron.galat = ''
  try {
    await kirim('/api/fm/staging/cron', { teks: cron.teks, dasar: cron.dasar })
    cron.sunting = false
    await st.muatUlang()
  } catch (e) { cron.galat = pesanGalat(e) } finally { cron.proses = false }
}

const meminta = ref(false)
async function segarkan() {
  meminta.value = true
  try {
    await minta('/api/fm/staging?segar=1')
    await st.muatUlang()
  } catch (e) { st.galat.value = e } finally { meminta.value = false }
}
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Staging</h1>
        <p class="redup">Situs staging klien di PC lokal (<code>{{ d?.url?.replace('https://', '') || 'velocitydatacenter.biz' }}</code>, user <code>vdcenterbiz</code>). Pengganti panel DirectAdmin untuk akun ini.</p>
      </div>
      <div class="aksi">
        <button v-if="d" type="button" class="tombol kecil" :disabled="!!kerja" @click="bukaBaru"><Ikon nama="tambah" :ukuran="15" /> Situs baru</button>
        <RouterLink v-if="d" :to="tautanBerkas(d.akar)" class="tombol garis kecil"><Ikon nama="berkas" :ukuran="15" /> File Manager</RouterLink>
        <button type="button" class="tombol garis kecil" :disabled="meminta || d?.menyegarkan" @click="segarkan"><Ikon nama="ulang" :ukuran="15" /> {{ d?.menyegarkan ? 'Memindai…' : 'Pindai ulang' }}</button>
      </div>
    </header>

    <p v-if="st.memuat.value && !d" class="redup">Memuat data staging…</p>
    <p v-else-if="st.galat.value && !d" class="peringatan" role="alert">Gagal memuat: {{ st.galat.value.message }}</p>

    <template v-if="d">
      <p v-if="d.galat" class="peringatan" role="alert">Pemindaian terakhir gagal: {{ d.galat }}.<template v-if="d.waktu"> Data di bawah dari {{ waktuLalu(d.waktu) }}.</template></p>
      <p v-if="layananMati.length" class="peringatan bahaya" role="alert">Layanan tidak berjalan: {{ layananMati.join(', ') }}</p>

      <p v-if="kerja" class="peringatan" role="status">{{ LABEL_KERJA[kerja.jenis] }} {{ kerja.nama }}: {{ kerja.tahap }}…</p>
      <p v-else-if="terakhir?.galat" class="peringatan bahaya" role="alert">{{ LABEL_KERJA[terakhir.jenis] }} {{ terakhir.nama }} gagal: {{ pesanGalat(terakhir.galat) }}</p>
      <p v-else-if="terakhir" class="redup" role="status">{{ LABEL_KERJA[terakhir.jenis] }} {{ terakhir.nama }}: {{ terakhir.pesan }} ({{ waktuLalu(terakhir.selesai) }})</p>
      <p v-if="galatMasuk" class="peringatan bahaya" role="alert">Gagal masuk {{ galatMasuk }}</p>

      <section class="ringkas" aria-label="Ringkasan">
        <div class="kartu stat">
          <span class="redup">Situs</span>
          <strong>{{ situs.length || '-' }}</strong>
          <span class="redup">{{ jumlah(SARING[1]) }} WordPress · {{ jumlah(SARING[2]) }} Laravel</span>
        </div>
        <div class="kartu stat">
          <span class="redup">Disk staging</span>
          <strong>{{ ukuran(d.disk_total) }}</strong>
          <span class="redup">Database {{ ukuranBerkas(totalDb) }}</span>
        </div>
        <div class="kartu stat">
          <span class="redup">Partisi /home</span>
          <strong>{{ persenPartisi }}%</strong>
          <div class="meter" :class="{ waspada: persenPartisi >= 75, bahaya: persenPartisi >= 90 }" role="meter" :aria-valuenow="persenPartisi" aria-valuemin="0" aria-valuemax="100" aria-label="Pemakaian partisi /home"><i :style="{ width: `${persenPartisi}%` }"></i></div>
          <span class="redup">Sisa {{ ukuranBerkas(d.partisi.sisa) }} dari {{ ukuranBerkas(d.partisi.total) }}</span>
        </div>
        <div class="kartu stat">
          <span class="redup">PHP-FPM</span>
          <strong>{{ d.fpm.proses }} / {{ d.fpm.maks }}</strong>
          <span class="redup">Proses aktif · RAM {{ ukuranBerkas(d.fpm.memori) }}</span>
          <span class="redup">{{ d.cron.length }} cron</span>
        </div>
      </section>

      <section class="kartu daftar" aria-label="Daftar situs">
        <div class="alat">
          <div class="saring" role="group" aria-label="Saring jenis situs">
            <button v-for="f in SARING" :key="f.nilai" type="button" class="tombol kecil" :class="saring === f.nilai ? '' : 'garis'" :aria-pressed="saring === f.nilai" @click="saring = f.nilai">{{ f.label }} ({{ jumlah(f) }})</button>
          </div>
          <input v-model="cari" type="search" placeholder="Cari situs atau database" aria-label="Cari situs atau database">
          <select v-model="urut" aria-label="Urutkan">
            <option value="nama">Urut nama</option>
            <option value="disk">Disk terbesar</option>
            <option value="db">Database terbesar</option>
          </select>
        </div>

        <p v-if="!situs.length" class="redup">Pemindaian pertama sedang berjalan, tunggu beberapa menit…</p>
        <p v-else-if="!tampil.length" class="redup">Tidak ada situs yang cocok.</p>
        <div v-else class="tabel-wadah">
          <table class="tabel">
            <thead><tr><th scope="col">Situs</th><th scope="col">Jenis</th><th scope="col">HTTP</th><th scope="col" class="kanan">Disk</th><th scope="col">Database</th><th scope="col" class="kanan">Ukuran DB</th><th scope="col" aria-label="Aksi"></th></tr></thead>
            <tbody>
              <tr v-for="s in tampil" :key="s.path">
                <th scope="row" class="nama">{{ s.nama }}</th>
                <td><span class="lencana" :class="KELAS_JENIS[s.jenis]">{{ LABEL_JENIS[s.jenis] }}<template v-if="s.versi"> {{ s.versi }}</template></span></td>
                <td class="http">
                  <button v-if="s.url" type="button" class="tombol garis kecil" :disabled="!!mengecek" :aria-label="`Cek HTTP ${s.nama}`" @click="cekHttp(s)">{{ mengecek === s.nama ? 'Mengecek…' : 'Cek' }}</button>
                  <span v-else class="redup">-</span>
                  <template v-if="hasilHttp[s.nama]">
                    <span v-if="hasilHttp[s.nama].galat" class="redup">{{ PESAN_HTTP[hasilHttp[s.nama].galat] || hasilHttp[s.nama].galat }}</span>
                    <span v-else class="lencana" :class="httpBaik(hasilHttp[s.nama].kode) ? 'hijau' : 'merah'">{{ hasilHttp[s.nama].kode || 'Tak menjawab' }} · {{ hasilHttp[s.nama].detik }} dtk</span>
                  </template>
                </td>
                <td class="kanan">{{ ukuran(s.disk) }}</td>
                <td class="db">{{ s.db || '-' }}</td>
                <td class="kanan">{{ ukuran(s.db_ukuran) }}</td>
                <td>
                  <div class="tautan">
                    <a v-if="s.url" :href="`${s.url}/`" target="_blank" rel="noopener">Buka</a>
                    <button v-if="s.jenis === 'wordpress'" type="button" class="teks" @click="masukAdmin(s)">Masuk</button>
                    <RouterLink :to="tautanBerkas(s.path)">Berkas</RouterLink>
                    <button type="button" class="teks" @click="bukaKelola(s)">Kelola</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="d.waktu" class="redup kecil-p">Dipindai {{ waktuLalu(d.waktu) }}. Cek HTTP dilakukan satu per satu agar staging tidak terbebani. Kode 500 atau 503 bisa berarti situs sedang mode maintenance, buka situsnya untuk memastikan.</p>
      </section>

      <section v-if="d.db_yatim?.length" class="kartu">
        <h2>Database tanpa situs ({{ d.db_yatim.length }})</h2>
        <p class="redup kecil-p">Tidak dirujuk <code>wp-config.php</code> atau <code>.env</code> mana pun yang terbaca. Pastikan dulu sebelum menghapus.</p>
        <ul class="daftar-db">
          <li v-for="x in d.db_yatim" :key="x.nama"><code>{{ x.nama }}</code> <span class="redup">{{ ukuranBerkas(x.ukuran) }}</span></li>
        </ul>
      </section>

      <section class="kartu">
        <div class="judul-baris">
          <h2>Cron ({{ d.cron.length }})</h2>
          <button v-if="!cron.sunting" type="button" class="tombol garis kecil" @click="suntingCron"><Ikon nama="sunting" :ukuran="15" /> Sunting</button>
        </div>
        <template v-if="cron.sunting">
          <label class="redup kecil-p" for="teks-cron">Crontab user vdcenterbiz. Isi lama disimpan otomatis sebelum diganti.</label>
          <textarea id="teks-cron" v-model="cron.teks" rows="12" spellcheck="false" class="kode"></textarea>
          <p v-if="cron.galat" class="peringatan bahaya" role="alert">{{ cron.galat }}</p>
          <div class="aksi">
            <button type="button" class="tombol kecil" :disabled="cron.proses" @click="simpanCron">{{ cron.proses ? 'Menyimpan…' : 'Simpan' }}</button>
            <button type="button" class="tombol garis kecil" :disabled="cron.proses" @click="cron.sunting = false">Batal</button>
          </div>
        </template>
        <ul v-else class="daftar-cron">
          <li v-for="(c, i) in d.cron" :key="i"><code>{{ c }}</code></li>
        </ul>
      </section>
    </template>

    <Dialog :buka="kelola.buka" :judul="kelola.s ? `Kelola ${kelola.s.nama}` : ''" lebar="860px" @tutup="kelola.buka = false">
      <div v-if="kelola.s" class="isi-kelola">
        <p v-if="kerja" class="peringatan" role="status">{{ LABEL_KERJA[kerja.jenis] }} {{ kerja.nama }}: {{ kerja.tahap }}…</p>
        <p v-if="kelola.galat" class="peringatan bahaya" role="alert">{{ kelola.galat }}</p>

        <section>
          <div class="judul-baris">
            <h3>Cadangan</h3>
            <button type="button" class="tombol garis kecil" :disabled="!!kerja || kelola.proses" @click="buatCadangan"><Ikon nama="cadangan" :ukuran="15" /> Buat cadangan</button>
          </div>
          <p v-if="!kelola.cadangan.length" class="redup kecil-p">Belum ada cadangan dari panel ini.</p>
          <div v-else class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">Waktu</th><th scope="col">Jenis</th><th scope="col" class="kanan">Ukuran</th><th scope="col" aria-label="Aksi"></th></tr></thead>
              <tbody>
                <tr v-for="c in kelola.cadangan" :key="c.id">
                  <td>{{ tanggalWaktu(c.waktu) }}</td>
                  <td>{{ c.jenis }}<template v-if="!c.ada_db"> (tanpa DB)</template></td>
                  <td class="kanan">{{ ukuranBerkas(c.ukuran) }}</td>
                  <td><div class="tautan">
                    <button type="button" class="teks" :disabled="!!kerja" @click="konfirmPulihkan(c)">Pulihkan</button>
                    <button type="button" class="teks bahaya" :disabled="!!kerja" @click="hapusCadangan(c)">Hapus</button>
                  </div></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="kelola.s.db">
          <h3>Database</h3>
          <p class="kecil-p"><code>{{ kelola.s.db }}</code> <span class="redup">{{ ukuran(kelola.s.db_ukuran) }}</span></p>
          <div class="aksi">
            <a class="tombol garis kecil" :href="`/api/fm/staging/db/ekspor?nama=${namaUrl()}`"><Ikon nama="unduh" :ukuran="15" /> Ekspor</a>
            <label class="tombol garis kecil" :class="{ mati: !!kerja }"><Ikon nama="unggah" :ukuran="15" /> Impor .sql / .sql.gz
              <input type="file" accept=".sql,.gz" class="berkas-tersembunyi" :disabled="!!kerja" @change="pilihImpor">
            </label>
            <a class="tombol garis kecil" href="/phpmyadmin/" target="_blank" rel="noopener"><Ikon nama="database" :ukuran="15" /> phpMyAdmin</a>
            <button type="button" class="tombol garis kecil" :disabled="!!kerja" @click="konfirmSandi"><Ikon nama="kunci" :ukuran="15" /> Ganti sandi</button>
          </div>
        </section>

        <section>
          <div class="judul-baris">
            <h3>Log</h3>
            <div class="aksi">
              <select v-model="kelola.sumber" aria-label="Sumber log" @change="muatLog">
                <option value="php">PHP</option>
                <option value="galat">Apache error</option>
                <option value="akses">Apache akses</option>
              </select>
              <button type="button" class="tombol garis kecil" :disabled="kelola.proses" @click="muatLog"><Ikon nama="ulang" :ukuran="15" /> Muat ulang</button>
            </div>
          </div>
          <p v-if="kelola.baris && !kelola.baris.length" class="redup kecil-p">Tidak ada baris untuk situs ini di bagian akhir log.</p>
          <pre v-else-if="kelola.baris" class="log" tabindex="0">{{ kelola.baris.join('\n') }}</pre>
        </section>

        <section class="zona-bahaya">
          <div class="judul-baris">
            <h3>Hapus situs</h3>
            <button type="button" class="tombol garis kecil teks-bahaya" :disabled="!!kerja" @click="konfirmHapusSitus"><Ikon nama="sampah" :ukuran="15" /> Hapus situs</button>
          </div>
          <p class="redup kecil-p">Ditolak otomatis bila situs masih dipakai cron, proses installer, atau berbagi database dengan situs lain.</p>
        </section>
      </div>
    </Dialog>

    <Dialog :buka="baru.buka" judul="Situs baru" lebar="520px" @tutup="baru.buka = false">
      <form v-if="!baru.hasil" class="isi-kelola" @submit.prevent="buatSitus">
        <p class="redup kecil-p">Membuat folder kosong, database, dan user database. WordPress tidak dipasang; pemasangan tetap lewat installer.</p>
        <label for="nama-baru">Nama folder, biasanya domain klien</label>
        <input id="nama-baru" v-model="baru.nama" autocomplete="off" autofocus placeholder="contoh.co.id">
        <p v-if="baru.galat" class="peringatan bahaya" role="alert">{{ baru.galat }}</p>
        <div class="aksi">
          <button type="submit" class="tombol" :disabled="!baru.nama.trim() || baru.proses">{{ baru.proses ? 'Membuat…' : 'Buat situs' }}</button>
          <button type="button" class="tombol garis" @click="baru.buka = false">Batal</button>
        </div>
      </form>
      <div v-else class="isi-kelola">
        <p class="peringatan" role="status">Salin sandi sekarang. Sandi ini hanya tampil sekali dan tidak disimpan.</p>
        <dl class="kredensial">
          <dt>Folder</dt><dd><code>{{ baru.hasil.path }}</code></dd>
          <dt>Alamat</dt><dd><code>{{ baru.hasil.url }}</code></dd>
          <dt>Database</dt><dd><code>{{ baru.hasil.db }}</code></dd>
          <dt>User DB</dt><dd><code>{{ baru.hasil.user }}</code></dd>
          <dt>Sandi DB</dt><dd><code>{{ baru.hasil.sandi }}</code></dd>
        </dl>
        <div class="aksi">
          <button type="button" class="tombol" @click="salinHasil"><Ikon :nama="baru.tersalin ? 'centang' : 'salin'" :ukuran="15" /> {{ baru.tersalin ? 'Tersalin' : 'Salin semua' }}</button>
          <button type="button" class="tombol garis" @click="baru.buka = false">Tutup</button>
        </div>
      </div>
    </Dialog>

    <Dialog :buka="konfirm.buka" :judul="konfirm.judul" lebar="480px" atas @tutup="konfirm.buka = false">
      <form class="isi-kelola" @submit.prevent="setujui">
        <p>{{ konfirm.teks }}</p>
        <label for="ketik-konfirmasi">Ketik <code>{{ kelola.s?.nama }}</code> untuk melanjutkan</label>
        <input id="ketik-konfirmasi" v-model="konfirm.ketik" autocomplete="off" autofocus>
        <div class="aksi">
          <button type="submit" class="tombol" :disabled="konfirm.ketik !== kelola.s?.nama">{{ konfirm.tombol }}</button>
          <button type="button" class="tombol garis" @click="konfirm.buka = false">Batal</button>
        </div>
      </form>
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; min-width: 0; }
.aksi { display: flex; gap: 8px; flex-wrap: wrap; }
.aksi .tombol { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; }
.ringkas { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(190px, 100%), 1fr)); gap: 14px; }
.kartu { min-width: 0; }
.stat { display: grid; gap: 6px; align-content: start; }
.stat strong { font-size: 24px; }
.meter.waspada i { background: var(--waspada); }
.meter.bahaya i { background: var(--bahaya); }
.daftar { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; }
.tabel td, .tabel th { vertical-align: middle; }
.alat { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.saring { display: flex; flex-wrap: wrap; gap: 6px; flex: 1 1 auto; }
.alat input { flex: 1 1 200px; max-width: 280px; }
.alat select { flex: 0 0 auto; width: auto; }
.nama { font-weight: 600; overflow-wrap: anywhere; min-width: 180px; }
.db { font-size: 12.5px; overflow-wrap: anywhere; }
.kanan { text-align: right; white-space: nowrap; }
.http { white-space: nowrap; }
.http .lencana, .http > .redup { margin-left: 6px; }
.tautan { display: flex; gap: 10px; white-space: nowrap; }
.kecil-p { font-size: 13px; margin: 0; }
.teks { background: none; border: 0; padding: 0; color: var(--aksen-terang); font: inherit; cursor: pointer; }
.teks:hover { text-decoration: underline; }
.teks:disabled { opacity: .5; cursor: default; }
.teks.bahaya { color: var(--bahaya); }
.judul-baris { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; }
.judul-baris h2, .judul-baris h3 { margin: 0; }
.judul-baris select { width: auto; }
.zona-bahaya { border-top: 1px solid var(--garis, rgba(127, 127, 127, .25)); padding-top: 14px; }
.teks-bahaya { color: var(--bahaya); }
.kredensial { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 6px 14px; margin: 0; font-size: 13px; }
.kredensial dt { color: var(--teks-3); }
.kredensial dd { margin: 0; overflow-wrap: anywhere; }
.isi-kelola { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; }
h3 { font-size: 15px; margin: 0 0 8px; }
.kode { width: 100%; font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12.5px; margin: 8px 0; }
.log { max-height: 280px; overflow: auto; font-size: 12px; line-height: 1.5; margin: 0; padding: 10px; border-radius: 10px; background: var(--kartu-2); white-space: pre-wrap; overflow-wrap: anywhere; }
.berkas-tersembunyi { position: absolute; inline-size: 1px; block-size: 1px; opacity: 0; }
label.tombol { position: relative; cursor: pointer; }
label.tombol.mati { opacity: .5; cursor: default; }
label.tombol:focus-within { outline: 2px solid var(--aksen-terang); outline-offset: 2px; }
h2 { font-size: 16px; margin: 0 0 8px; }
.daftar-db { list-style: none; margin: 10px 0 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr)); gap: 6px; font-size: 13px; }
.daftar-cron { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; font-size: 12.5px; }
.daftar-cron code { overflow-wrap: anywhere; }
</style>
