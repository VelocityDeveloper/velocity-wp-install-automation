<script setup>
// Velocity Update: jurnal perubahan perusahaan + kondisi terbarunya (halaman tersembunyi, tidak ada di menu).
// Data /var/lib/velocity/velocity-update/data.json lewat /api/velocity-update (server_stats.py → scripts/velocity_update.py).
// Metrik otomatis dihitung tiap pagi (velocity-update-pantau.timer), Claude menilai tiap Senin (velocity-update-nilai.timer).
import { ref, reactive, computed, watch } from 'vue'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import Info from '../components/Info.vue'
import { konfirmasi } from '../konfirmasi.js'
import { pakaiPolling, kirim, tanggalWaktu, angka } from '../api.js'
import { tabUrl } from '../laravel.js'
import { useRoute, useRouter } from 'vue-router'

const { data, galat, memuat, muatUlang } = pakaiPolling('/api/velocity-update', 60000)

// ---- sandi halaman: API menjawab 401 sampai cookie sesi (HttpOnly, 30 hari) terpasang ----
const keluarPaksa = ref(false)
const perluMasuk = computed(() => keluarPaksa.value || (!!galat.value && galat.value.message.startsWith('401')))
const fm = reactive({ sandi: '', proses: false, galat: '' })
async function masuk() {
  Object.assign(fm, { proses: true, galat: '' })
  try {
    await kirim('/api/velocity-update/masuk', { sandi: fm.sandi })
    fm.sandi = ''
    keluarPaksa.value = false
    await muatUlang()
  } catch (e) {
    fm.galat = PESAN[e.message] || `Gagal masuk: ${e.message}`
  } finally {
    fm.proses = false
  }
}
async function keluar() {
  try { await kirim('/api/velocity-update/keluar', {}) } catch { /* cookie tetap dibuang di bawah */ }
  data.value = null
  keluarPaksa.value = true
}

const STATUS = {
  berjalan: { label: 'Berjalan', kelas: 'biru' },
  bagus: { label: 'Bagus', kelas: 'hijau' },
  perlu_perhatian: { label: 'Perlu perhatian', kelas: 'kuning' },
  selesai: { label: 'Selesai', kelas: 'abu' },
  dihentikan: { label: 'Dihentikan', kelas: 'abu' },
}
const PESAN = {
  forbidden: 'Hanya bisa diubah dari jaringan kantor atau Tailscale.',
  judul_kosong: 'Judul wajib diisi.',
  tanggal_tidak_valid: 'Tanggal mulai belum diisi.',
  isi_kosong: 'Isi kondisi masih kosong.',
  sedang_jalan: 'Claude sedang menilai. Tunggu sampai selesai.',
  tidak_ada: 'Data tidak ditemukan (mungkin baru dihapus).',
  sandi_salah: 'Sandi salah.',
  terlalu_banyak_percobaan: 'Terlalu banyak sandi salah. Coba lagi 15 menit lagi.',
  perlu_masuk: 'Sesi berakhir. Masukkan sandi lagi.',
}
const pesanGalat = (e) => PESAN[e.message] || e.message

const HARI = 86400000
const hariSejak = (t) => Math.floor((Date.now() - new Date(t)) / HARI)
const tglPendek = (t) => new Date(t).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })
const tglPanjang = (t) => new Date(t).toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric' })
const BASI = 7  // hari tanpa catatan kondisi = perlu dikabari

const daftar = computed(() => data.value?.update || [])
const terakhir = (u) => u.kondisi[u.kondisi.length - 1] || null
const basi = (u) => !['selesai', 'dihentikan'].includes(u.status) && (!terakhir(u) || hariSejak(terakhir(u).waktu) >= BASI)

const TAB = ['semua', 'perlu_perhatian', 'berjalan', 'bagus', 'arsip']
const tab = tabUrl('tab', 'semua', { boleh: TAB })
const hitung = computed(() => {
  const h = { semua: 0, perlu_perhatian: 0, berjalan: 0, bagus: 0, arsip: 0, basi: 0 }
  for (const u of daftar.value) {
    const arsip = ['selesai', 'dihentikan'].includes(u.status)
    h[arsip ? 'arsip' : u.status]++
    if (!arsip) h.semua++
    if (basi(u)) h.basi++
  }
  return h
})
const LABEL_TAB = { semua: 'Aktif', perlu_perhatian: 'Perlu perhatian', berjalan: 'Berjalan', bagus: 'Bagus', arsip: 'Selesai / dihentikan' }
const URUT = { perlu_perhatian: 0, berjalan: 1, bagus: 2, selesai: 3, dihentikan: 4 }
const tampil = computed(() => daftar.value
  .filter((u) => tab.value === 'semua' ? !['selesai', 'dihentikan'].includes(u.status)
    : tab.value === 'arsip' ? ['selesai', 'dihentikan'].includes(u.status) : u.status === tab.value)
  .slice()
  .sort((a, b) => (URUT[a.status] - URUT[b.status]) || (b.mulai < a.mulai ? -1 : 1)))

// ---- metrik otomatis ----
const LABEL_SUMBER = computed(() => Object.fromEntries((data.value?.sumber_tersedia || []).map((s) => [s.kunci, s.label])))
const fmt = (v) => v === null || v === undefined ? '–' : typeof v === 'string' ? v : angka(v)
const jt = (v) => v ? (v / 1e6).toLocaleString('id-ID', { maximumFractionDigits: 1 }) : '–'
const jamPendek = (t) => t ? new Date(t).toLocaleString('id-ID', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '–'
const sisaLabel = (n) => n === null || n === undefined ? '' : n < 0 ? `lewat ${-n} hr` : n === 0 ? 'hari ini' : `${n} hr lagi`
// arah: 'naik' = makin besar makin baik, 'turun' = makin kecil makin baik
function tren(a) {
  if (a.sebelum === null || a.sebelum === undefined || a.sesudah === null || a.sesudah === undefined || a.sebelum === a.sesudah) return { kelas: 'datar', panah: '→' }
  const naik = a.sesudah > a.sebelum
  const kelas = !a.arah ? 'netral' : (naik === (a.arah === 'naik') ? 'baik' : 'buruk')
  return { kelas, panah: naik ? '↑' : '↓' }
}
const periode = (m) => !m.periode ? ''
  : !m.periode.sebelum ? `kondisi per ${jamPendek(m.waktu)}`
    : `${tglPendek(m.periode.sebelum[0])}–${tglPendek(m.periode.sebelum[1])} vs ${tglPendek(m.periode.sesudah[0])}–${tglPendek(m.periode.sesudah[1])}`

// ---- buka/tutup riwayat (per kartu) ----
const buka = reactive({})
const jurnalPenuh = reactive({})

// ---- nama pencatat (disimpan di browser) ----
const oleh = ref((() => { try { return localStorage.getItem('vu-oleh') || 'Muh' } catch { return 'Muh' } })())
watch(oleh, (v) => { try { localStorage.setItem('vu-oleh', v) } catch { /* mode privat */ } })

async function aksi(nama, body) {
  try {
    const r = await kirim(`/api/velocity-update/${nama}`, { ...body, oleh: oleh.value })
    data.value = r
    return r
  } catch (e) {
    if (e.message === 'perlu_masuk') { data.value = null; keluarPaksa.value = true; fu.buka = false; fk.buka = false }
    throw e
  }
}

// ---- dialog update ----
const KOSONG = { id: '', judul: '', mulai: new Date().toISOString().slice(0, 10), divisi: '', jurnal: '', pantau: '', status: 'berjalan', sumber: [] }
const fu = reactive({ buka: false, ...KOSONG, proses: false, galat: '' })
const pilihanSumber = computed(() => {
  const baku = data.value?.sumber_tersedia || []
  const ada = new Set(baku.map((s) => s.kunci))
  const u = daftar.value.find((x) => x.id === fu.id)
  const khusus = fu.sumber.filter((k) => !ada.has(k)).map((k) => ({ kunci: k, label: u?.metrik?.[k]?.judul || k }))
  return [...baku, ...khusus]
})
const DIVISI = computed(() => [...new Set(['Semua tim', 'CS', 'AM', 'Support', 'Revisi', 'Ads', 'Webmaster', 'Konseptor', 'Layanan baru', ...daftar.value.map((u) => u.divisi).filter(Boolean)])])
function bukaUpdate(u) {
  Object.assign(fu, KOSONG, u ? { id: u.id, judul: u.judul, mulai: u.mulai, divisi: u.divisi, jurnal: u.jurnal, pantau: u.pantau, status: u.status, sumber: [...u.sumber] } : {}, { buka: true, proses: false, galat: '' })
}
async function simpanUpdate() {
  fu.proses = true
  fu.galat = ''
  try {
    await aksi(fu.id ? 'ubah' : 'tambah', { id: fu.id, judul: fu.judul, mulai: fu.mulai, divisi: fu.divisi, jurnal: fu.jurnal, pantau: fu.pantau, status: fu.status, sumber: fu.sumber })
    fu.buka = false
  } catch (e) {
    fu.galat = pesanGalat(e)
  } finally {
    fu.proses = false
  }
}
async function hapusUpdate(u) {
  if (!await konfirmasi({ judul: `Hapus "${u.judul}"?`, teks: `Semua ${u.kondisi.length} catatan kondisinya ikut terhapus. Kalau perubahan ini sudah tidak dipakai, lebih baik ubah statusnya jadi Dihentikan.`, tombol: 'Hapus', kelas: 'bahaya' })) return
  try { await aksi('hapus', { id: u.id }) } catch (e) { galatAksi.value = pesanGalat(e) }
}

// ---- dialog kondisi ----
const fk = reactive({ buka: false, id: '', judul: '', isi: '', status: '', proses: false, galat: '' })
function bukaKondisi(u) {
  Object.assign(fk, { buka: true, id: u.id, judul: u.judul, isi: '', status: '', proses: false, galat: '' })
}
async function simpanKondisi() {
  fk.proses = true
  fk.galat = ''
  try {
    await aksi('kondisi', { id: fk.id, isi: fk.isi, status: fk.status })
    fk.buka = false
    buka[fk.id] = true
  } catch (e) {
    fk.galat = pesanGalat(e)
  } finally {
    fk.proses = false
  }
}
async function hapusKondisi(u, k) {
  if (!await konfirmasi({ judul: 'Hapus catatan kondisi ini?', teks: k.isi.slice(0, 160), tombol: 'Hapus', kelas: 'bahaya' })) return
  try { await aksi('hapus-kondisi', { id: u.id, kondisi: k.id }) } catch (e) { galatAksi.value = pesanGalat(e) }
}

// ---- penilaian Claude & hitung ulang metrik ----
const galatAksi = ref('')
const proses = reactive({ nilai: false, pantau: false })
const menilai = computed(() => proses.nilai || data.value?.menilai)
async function mintaNilai() {
  galatAksi.value = ''
  proses.nilai = true
  try { await aksi('nilai', {}) } catch (e) { galatAksi.value = pesanGalat(e) } finally { proses.nilai = false }
}
async function hitungUlang() {
  galatAksi.value = ''
  proses.pantau = true
  try { await aksi('pantau', {}) } catch (e) { galatAksi.value = pesanGalat(e) } finally { proses.pantau = false }
}
// Saat Claude menilai, periksa lebih sering supaya hasilnya cepat tampil
let cek = null
watch(menilai, (v) => {
  clearInterval(cek)
  if (v) cek = setInterval(async () => { try { const r = await fetch('/api/velocity-update', { cache: 'no-store' }); if (r.ok) data.value = await r.json() } catch { /* coba lagi */ } }, 8000)
})
const nilai = computed(() => data.value?.nilai || {})

// ---- kartu ringkas → detail (?u=u-013). Push, bukan replace, supaya tombol Kembali browser menutup detail ----
const route = useRoute()
const router = useRouter()
const pilih = computed(() => daftar.value.find((u) => u.id === route.query.u) || null)
function bukaDetail(u) {
  router.push({ query: { ...route.query, u: u.id } })
  window.scrollTo({ top: 0 })
}
function tutupDetail() {
  if (window.history.state?.back) router.back()
  else { const q = { ...route.query }; delete q.u; router.replace({ query: q }) }
}
// Tautan lama #u-013 tetap jalan: ubah jadi ?u=u-013
if (/^#u-\d+$/.test(location.hash)) router.replace({ query: { ...route.query, u: location.hash.slice(1) }, hash: '' })
// Angka sorotan metrik otomatis yang ditampilkan di kartu ringkas (maks 3)
const sorotKartu = (u) => Object.values(u.metrik || {}).flatMap((m) => m.sorot || []).slice(0, 3)
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Velocity Update</h1>
        <p class="redup">Jurnal perubahan di perusahaan dan kondisi terbarunya. Angka otomatis dihitung ulang tiap pagi, Claude menilai tiap Senin.</p>
      </div>
      <div v-if="data && !perluMasuk" class="tombol-kepala">
        <button type="button" class="tombol garis kecil" :disabled="menilai" @click="mintaNilai">
          <Ikon nama="claude" :ukuran="16" /> {{ menilai ? 'Claude sedang menilai…' : 'Minta Claude menilai' }}
        </button>
        <button type="button" class="tombol kecil" @click="bukaUpdate(null)"><Ikon nama="tambah" :ukuran="16" /> Catat update</button>
        <button type="button" class="ikon-tombol" aria-label="Keluar" title="Keluar (kunci halaman)" @click="keluar"><Ikon nama="kunci" :ukuran="16" /></button>
      </div>
    </header>

    <p v-if="memuat" class="redup">Memuat…</p>
    <section v-else-if="perluMasuk" class="kartu masuk" aria-labelledby="judul-masuk">
      <h2 id="judul-masuk"><Ikon nama="kunci" :ukuran="18" /> Halaman ini bersandi</h2>
      <p class="redup">Masukkan sandi Velocity Update. Browser ini akan diingat selama 30 hari.</p>
      <form class="form" @submit.prevent="masuk">
        <label class="isian"><span>Sandi</span>
          <input v-model="fm.sandi" type="password" required autocomplete="current-password" autofocus>
        </label>
        <p v-if="fm.galat" class="pesan-status bahaya" role="alert">{{ fm.galat }}</p>
        <button type="submit" class="tombol" :disabled="fm.proses || !fm.sandi">{{ fm.proses ? 'Memeriksa…' : 'Masuk' }}</button>
      </form>
    </section>
    <p v-else-if="galat && !data" class="pesan-status bahaya">Gagal memuat: {{ galat.message }}</p>

    <template v-else-if="data">
      <p v-if="galatAksi" class="pesan-status bahaya" role="alert">{{ galatAksi }}</p>

      <template v-if="!pilih">
      <section v-if="nilai.ringkasan || menilai" class="kartu claude" aria-labelledby="judul-claude">
        <div class="kartu-judul">
          <h2 id="judul-claude"><Ikon nama="claude" :ukuran="16" /> Penilaian Claude</h2>
          <span class="redup">
            <template v-if="menilai"><span class="putar" aria-hidden="true"></span> Sedang menilai semua update aktif (±1–3 menit)…</template>
            <template v-else>{{ tanggalWaktu(nilai.waktu) }}</template>
          </span>
        </div>
        <p v-if="nilai.ringkasan" class="claude-isi">{{ nilai.ringkasan }}</p>
        <p class="redup kecil-p">Kondisi per update dari Claude tercatat di riwayat masing-masing kartu. Status tidak diubah otomatis — saran Claude tampil sebagai label kecil.</p>
      </section>

      <div class="ringkas">
        <button v-for="k in ['perlu_perhatian', 'berjalan', 'bagus']" :key="k" type="button" class="kartu angka" :class="{ aktif: tab === k }" @click="tab = tab === k ? 'semua' : k">
          <span class="redup">{{ STATUS[k].label }}</span><b :class="`warna-${STATUS[k].kelas}`">{{ hitung[k] }}</b>
        </button>
        <div class="kartu angka">
          <span class="redup">Belum ada kabar ≥{{ BASI }} hari
            <Info label="Tentang kabar" rata="kanan"><p>Update aktif yang catatan kondisi terakhirnya sudah {{ BASI }} hari atau lebih, atau belum pernah dicatat sama sekali.</p></Info>
          </span>
          <b :class="hitung.basi ? 'warna-kuning' : ''">{{ hitung.basi }}</b>
        </div>
      </div>

      <div class="bilah">
        <div class="tab" role="tablist" aria-label="Saring status">
          <button v-for="t in TAB" :key="t" type="button" role="tab" :aria-selected="tab === t" :class="{ aktif: tab === t }" @click="tab = t">
            {{ LABEL_TAB[t] }} <span class="hitung">{{ hitung[t] }}</span>
          </button>
        </div>
        <span class="redup">
          Angka otomatis: {{ data.pantau_terakhir ? tanggalWaktu(data.pantau_terakhir) : 'belum pernah' }}
          <button type="button" class="tautan" :disabled="proses.pantau" @click="hitungUlang">{{ proses.pantau ? 'menghitung…' : 'hitung ulang' }}</button>
        </span>
      </div>

      <p v-if="!tampil.length" class="kartu redup kosong">Tidak ada update di kelompok ini.</p>

      <div class="grid-upd">
        <button v-for="u in tampil" :key="u.id" type="button" class="kartu kartu-upd" :class="`garis-${STATUS[u.status].kelas}`" @click="bukaDetail(u)">
          <span class="ku-label">
            <span class="lencana kode">{{ u.id }}</span>
            <span class="lencana" :class="STATUS[u.status].kelas">{{ STATUS[u.status].label }}</span>
            <span v-if="u.divisi" class="lencana abu">{{ u.divisi }}</span>
          </span>
          <span class="ku-judul">{{ u.judul }}</span>
          <span class="ku-tgl redup">Mulai {{ tglPendek(u.mulai) }} · hari ke-{{ Math.max(hariSejak(u.mulai) + 1, 1) }}</span>
          <span class="ku-kondisi" :class="{ redup: !terakhir(u) }">{{ terakhir(u)?.isi || 'Belum ada catatan kondisi.' }}</span>
          <span v-if="sorotKartu(u).length" class="ku-sorot">
            <span v-for="x in sorotKartu(u)" :key="x.label" class="ku-chip" :class="{ buruk: x.buruk }">{{ x.label }} <b>{{ fmt(x.nilai) }}</b></span>
          </span>
          <span class="ku-bawah">
            <span v-if="terakhir(u)" class="redup"><span class="oleh" :class="{ claude: terakhir(u).jenis === 'claude' }">{{ terakhir(u).oleh }}</span> · {{ tglPendek(terakhir(u).waktu) }}</span>
            <span v-if="basi(u)" class="ku-basi">belum ada kabar ≥{{ BASI }} hari</span>
            <span class="ku-buka">Detail →</span>
          </span>
        </button>
      </div>
      </template>

      <template v-else>
      <button type="button" class="tautan kembali" @click="tutupDetail">← Semua update</button>
      <article v-for="u in [pilih]" :id="u.id" :key="u.id" class="kartu upd" :class="`garis-${STATUS[u.status].kelas}`">
        <div class="upd-kepala">
          <div class="tanggal" :title="`Mulai ${tglPanjang(u.mulai)}`">
            <b>{{ tglPendek(u.mulai) }}</b>
            <span>hari ke-{{ Math.max(hariSejak(u.mulai) + 1, 1) }}</span>
          </div>
          <div class="upd-judul">
            <h2>{{ u.judul }}</h2>
            <div class="label">
              <span class="lencana kode" title="Nomor update — dipakai di laporan Claude (mis. u-013)">{{ u.id }}</span>
              <span class="lencana" :class="STATUS[u.status].kelas">{{ STATUS[u.status].label }}</span>
              <span v-if="u.divisi" class="lencana abu">{{ u.divisi }}</span>
              <span v-if="u.saran_status && u.saran_status !== u.status" class="saran" :title="'Saran status dari penilaian Claude terakhir'">
                Claude: {{ STATUS[u.saran_status].label.toLowerCase() }}
              </span>
            </div>
          </div>
          <div class="upd-aksi">
            <button type="button" class="tombol garis kecil" @click="bukaKondisi(u)"><Ikon nama="tambah" :ukuran="15" /> Kondisi</button>
            <button type="button" class="ikon-tombol" aria-label="Ubah update" title="Ubah" @click="bukaUpdate(u)"><Ikon nama="sunting" :ukuran="16" /></button>
            <button type="button" class="ikon-tombol bahaya" aria-label="Hapus update" title="Hapus" @click="hapusUpdate(u)"><Ikon nama="sampah" :ukuran="16" /></button>
          </div>
        </div>

        <p v-if="u.jurnal" class="jurnal" :class="{ penuh: jurnalPenuh[u.id] }" @click="jurnalPenuh[u.id] = !jurnalPenuh[u.id]">{{ u.jurnal }}</p>
        <p v-if="u.pantau" class="pantau"><span>Yang dipantau</span>{{ u.pantau }}</p>

        <div class="kondisi" :class="{ basi: basi(u) }">
          <div class="kondisi-kepala">
            <span class="kecil-judul">Kondisi terbaru</span>
            <span v-if="terakhir(u)" class="redup">
              <span class="oleh" :class="{ claude: terakhir(u).jenis === 'claude' }">{{ terakhir(u).oleh }}</span>
              · {{ tglPendek(terakhir(u).waktu) }}
              <template v-if="hariSejak(terakhir(u).waktu) >= 1"> ({{ hariSejak(terakhir(u).waktu) }} hari lalu)</template>
            </span>
          </div>
          <p v-if="terakhir(u)" class="kondisi-isi">{{ terakhir(u).isi }}</p>
          <p v-else class="kondisi-isi redup">Belum ada catatan kondisi. <button type="button" class="tautan" @click="bukaKondisi(u)">Catat sekarang</button></p>
          <p v-if="basi(u) && terakhir(u)" class="peringatan">Sudah {{ hariSejak(terakhir(u).waktu) }} hari tanpa kabar baru.</p>
        </div>

        <div v-for="(m, s) in u.metrik" :key="s" class="metrik">
          <div class="metrik-kepala">
            <span class="kecil-judul">{{ m.judul || LABEL_SUMBER[s] || s }}</span>
            <span class="redup">otomatis · {{ periode(m) }}
              <Info v-if="m.ket" :label="`Tentang ${m.judul || s}`" rata="kanan"><p>{{ m.ket }}</p></Info>
            </span>
          </div>
          <p v-if="m.galat" class="pesan-status bahaya">Gagal dihitung: {{ m.galat }}</p>
          <template v-else>
            <p class="metrik-ringkas">{{ m.ringkas }}</p>
            <ul v-if="m.angka?.length || m.sorot?.length" class="angka-daftar">
              <li v-for="a in m.angka" :key="a.label" :title="a.ket || ''">
                <span class="a-label">{{ a.label }}</span>
                <span class="a-nilai">
                  <template v-if="a.sebelum !== null && a.sebelum !== undefined"><s>{{ fmt(a.sebelum) }}</s> </template>
                  <b :class="`tren-${tren(a).kelas}`">{{ a.sebelum !== null && a.sebelum !== undefined ? tren(a).panah + ' ' : '' }}{{ fmt(a.sesudah) }}</b>
                  <small>{{ a.satuan }}</small>
                </span>
              </li>
              <li v-for="x in m.sorot" :key="x.label" class="sorot">
                <span class="a-label">{{ x.label }}</span>
                <span class="a-nilai"><b :class="{ 'tren-buruk': x.buruk }">{{ fmt(x.nilai) }}</b></span>
              </li>
            </ul>
            <div v-if="m.orang" class="tabel-wadah">
              <table class="tabel orang">
                <thead><tr><th>Nama</th><th v-if="s === 'ai:semua'">Divisi</th><th>Hari aktif (7)</th><th>Sesi</th><th>Panggilan</th><th class="sembunyi-hp">Per hari aktif</th></tr></thead>
                <tbody>
                  <tr v-for="o in m.orang" :key="o.nama" :class="{ minim: o.minim }">
                    <td>{{ o.nama }} <span v-if="o.minim" class="lencana kuning">minim</span></td>
                    <td v-if="s === 'ai:semua'">{{ o.divisi }}</td>
                    <td>{{ o.hari_aktif }}/7</td>
                    <td>{{ o.sesi }}</td>
                    <td>{{ angka(o.panggilan) }}</td>
                    <td class="sembunyi-hp">{{ angka(o.per_hari_aktif) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="m.seri?.length" class="seri" role="img" :aria-label="`Panggilan Claude per hari, ${m.seri.length} hari`">
              <div v-for="t in m.seri" :key="t.t" class="seri-batang" :class="{ sesudah: t.t >= m.seri_tanda, minggu: new Date(t.t).getDay() === 0 }"
                   :title="`${tglPendek(t.t)}: ${angka(t.v)} panggilan`">
                <span class="seri-nilai">{{ t.v }}</span>
                <i :style="{ height: `${Math.max(2, 100 * t.v / Math.max(...m.seri.map((x) => x.v), 1))}%` }"></i>
                <span class="seri-tgl">{{ new Date(t.t).getDate() }}</span>
              </div>
            </div>
            <div v-if="m.paket" class="tabel-wadah">
              <table class="tabel orang">
                <thead><tr><th>Kelompok</th><th>Run</th><th>Berhasil</th><th>Lama (median)</th><th class="sembunyi-hp">Dipegang webmaster</th></tr></thead>
                <tbody>
                  <tr v-for="r in m.paket" :key="r.kelompok">
                    <td>{{ r.kelompok }}</td>
                    <td><span class="redup">{{ r.sebelum.run }}</span> → {{ r.sesudah.run }}</td>
                    <td><span class="redup">{{ fmt(r.sebelum.ok) }}%</span> → <b :class="r.sesudah.ok !== null && r.sebelum.ok !== null && r.sesudah.ok < r.sebelum.ok ? 'tren-buruk' : ''">{{ fmt(r.sesudah.ok) }}%</b></td>
                    <td><span class="redup">{{ fmt(r.sebelum.lama) }}</span> → {{ fmt(r.sesudah.lama) }} mnt</td>
                    <td class="sembunyi-hp">{{ r.dikerjakan_webmaster }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="m.konsep?.length" class="tabel-wadah">
              <table class="tabel orang">
                <thead><tr><th>Masuk</th><th>Web / project</th><th class="sembunyi-hp">Konseptor</th><th>Installer</th><th>Webmaster</th><th>Status CRM</th><th class="sembunyi-hp">Mulai</th><th class="sembunyi-hp">Selesai WM</th><th>Deadline</th></tr></thead>
                <tbody>
                  <tr v-for="k in m.konsep" :key="k.id" :title="k.ket">
                    <td>{{ k.tgl ? tglPendek(k.tgl) : '–' }}</td>
                    <td>{{ k.nama }} <span v-if="k.sumber === 'keduanya'" class="lencana hijau" title="Tersambung: project installer + order CRM">tersambung</span></td>
                    <td class="sembunyi-hp">{{ k.pm || '–' }}</td>
                    <td><template v-if="k.tahap">{{ k.tahap }}<span v-if="k.fitur" class="redup"> · {{ k.fitur }}</span><span v-if="k.review" class="lencana kuning" :title="`${k.review} fitur menunggu review`">{{ k.review }} review</span></template><span v-else class="redup">–</span></td>
                    <td>{{ k.webmaster || '–' }}</td>
                    <td><span class="lencana" :class="{ Selesai: 'hijau', 'Belum dikerjakan': 'merah', 'Dalam pengerjaan': 'biru', 'Belum ada order CRM': 'abu' }[k.status] || 'kuning'">{{ k.status }}</span></td>
                    <td class="sembunyi-hp">{{ k.mulai ? tglPendek(k.mulai) : '–' }}</td>
                    <td class="sembunyi-hp">{{ k.selesai_wm ? tglPendek(k.selesai_wm) : '–' }}</td>
                    <td :class="{ 'tren-buruk': k.telat }">{{ k.deadline ? tglPendek(k.deadline) : '–' }}<template v-if="k.telat"> · telat</template></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="m.omzet?.length" class="tabel-wadah">
              <table class="tabel orang angka-kanan">
                <thead><tr><th>Bulan</th><th>Omzet kotor</th><th class="sembunyi-hp">Versi Ringkasan</th><th>Pembuatan</th><th class="sembunyi-hp">Laba buat</th><th>Perpanjangan</th><th class="sembunyi-hp">Tambah space</th><th class="sembunyi-hp">Iklan+deposit</th><th class="sembunyi-hp">Jasa update</th><th class="sembunyi-hp">Lain</th><th class="sembunyi-hp">Order buat</th></tr></thead>
                <tbody>
                  <tr v-for="b in m.omzet" :key="b.bulan" :class="{ berjalan: b.berjalan }" :title="b.berjalan ? 'Bulan berjalan, belum penuh' : ''">
                    <td>{{ b.label }}<span v-if="b.berjalan" class="redup"> (berjalan)</span></td>
                    <td><b>{{ jt(b.kotor) }}</b></td>
                    <td class="sembunyi-hp">{{ jt(b.bersih) }}</td>
                    <td>{{ jt(b.pembuatan) }}</td>
                    <td class="sembunyi-hp">{{ jt(b.laba_buat) }}</td>
                    <td>{{ jt(b.perpanjangan) }}</td>
                    <td class="sembunyi-hp">{{ jt(b.tambah_space) }}</td>
                    <td class="sembunyi-hp">{{ jt(b.iklan) }}</td>
                    <td class="sembunyi-hp">{{ jt(b.jasa_update_web) }}</td>
                    <td class="sembunyi-hp">{{ jt(b.lain_lain + b.lainnya) }}</td>
                    <td class="sembunyi-hp">{{ b.order_buat }}</td>
                  </tr>
                </tbody>
              </table>
              <p class="redup catatan-tabel">Dalam juta rupiah. Laba buat = pembuatan dikurangi domain dan biaya iklan.</p>
            </div>
            <div v-if="m.webmaster?.length" class="wm-grid">
              <div v-for="o in m.webmaster" :key="o.nama" class="wm-kartu" :class="{ ada_tanda: o.tanda.length }">
                <div class="wm-kepala">
                  <b>{{ o.nama }}</b>
                  <span class="redup">aktif {{ jamPendek(o.terakhir_aktif) }}</span>
                </div>
                <ul v-if="o.tanda.length" class="wm-tanda"><li v-for="t in o.tanda" :key="t">{{ t }}</li></ul>
                <div class="wm-blok">
                  <span class="wm-label">CRM</span>
                  <p v-if="!o.crm.length" class="redup">–</p>
                  <p v-for="x in o.crm" :key="x.nama_web + x.status">
                    <span class="lencana" :class="x.status === 'Dalam pengerjaan' ? 'biru' : 'kuning'">{{ x.status === 'Dalam pengerjaan' ? 'dikerjakan' : x.status.toLowerCase() }}</span>
                    {{ x.nama_web }} <span class="redup">· {{ x.paket || x.jenis }}</span>
                    <span v-if="x.deadline" :class="x.status === 'Dalam pengerjaan' && x.sisa_hari <= 1 ? 'tren-buruk' : 'redup'"> · dl {{ tglPendek(x.deadline) }} ({{ sisaLabel(x.sisa_hari) }})</span>
                  </p>
                </div>
                <div v-if="o.installer.length" class="wm-blok">
                  <span class="wm-label">Installer</span>
                  <p v-for="x in o.installer" :key="x.jenis + x.nama">
                    <span class="redup">{{ x.jenis }}</span> {{ x.nama }} <span class="redup">· {{ x.tahap }}<template v-if="x.fitur"> · {{ x.fitur }} fitur</template></span>
                    <span v-if="x.review" class="lencana kuning">{{ x.review }} review</span>
                  </p>
                </div>
                <div class="wm-blok">
                  <span class="wm-label">Claude (2 hari)</span>
                  <p v-if="!o.sesi.length" class="redup">tidak ada sesi</p>
                  <p v-for="x in o.sesi" :key="x.akhir + x.judul"><span class="redup">{{ jamPendek(x.akhir) }}</span> {{ x.judul }}</p>
                </div>
                <p v-if="o.domain_lain.length" class="wm-lain redup">Domain lain disentuh: {{ o.domain_lain.join(', ') }}</p>
              </div>
            </div>
            <details v-if="m.basi?.length" class="wm-basi">
              <summary>{{ m.basi.length }} project "Dalam pengerjaan" di CRM atas nama orang di luar daftar webmaster</summary>
              <ul class="daftar-kecil">
                <li v-for="x in m.basi" :key="x.nama_web + x.webmaster">{{ x.webmaster }} · {{ x.nama_web }} <span class="redup">· {{ x.jenis }} · mulai {{ x.mulai ? tglPendek(x.mulai) : '–' }}<template v-if="x.catatan"> · {{ x.catatan }}</template></span></li>
              </ul>
            </details>
            <ul v-if="m.daftar_teks?.length" class="daftar-kecil">
              <li v-for="x in m.daftar_teks" :key="x">{{ x }}</li>
            </ul>
            <div v-if="m.contoh?.length" class="contoh">
              <span class="kecil-judul">Masih kurang halus → saran</span>
              <div v-for="c in m.contoh" :key="c.asli" class="contoh-baris">
                <p class="asli">“{{ c.asli }}”</p>
                <p class="saran-kalimat">{{ c.saran }}</p>
              </div>
            </div>
            <div v-if="m.contoh_baik?.length" class="contoh">
              <span class="kecil-judul">Sudah bagus</span>
              <p v-for="c in m.contoh_baik" :key="c" class="baik-kalimat">“{{ c }}”</p>
            </div>
            <p v-if="m.catatan" class="redup">{{ m.catatan }}</p>
            <ul v-if="m.daftar?.length" class="daftar-kecil">
              <li v-for="x in m.daftar" :key="x.tgl + x.nama"><span class="redup">{{ tglPendek(x.tgl) }}</span> {{ x.nama }} <span class="redup">Rp{{ angka(x.nilai) }}</span></li>
            </ul>
          </template>
        </div>
        <p v-if="!u.sumber.length" class="redup tanpa-metrik">Belum ada angka otomatis untuk update ini — kondisinya dari catatan manual.</p>

        <div v-if="u.kondisi.length > 1" class="riwayat">
          <button type="button" class="tautan" :aria-expanded="!!buka[u.id]" @click="buka[u.id] = !buka[u.id]">
            {{ buka[u.id] ? 'Sembunyikan riwayat' : `Lihat riwayat kondisi (${u.kondisi.length})` }}
          </button>
          <ol v-if="buka[u.id]" class="garis-waktu">
            <li v-for="k in u.kondisi.slice().reverse()" :key="k.id">
              <div class="gw-kepala">
                <span class="oleh" :class="{ claude: k.jenis === 'claude' }">{{ k.oleh }}</span>
                <span class="redup">{{ tanggalWaktu(k.waktu) }}</span>
                <span v-if="k.status" class="redup">· status {{ STATUS[k.status.dari]?.label }} → <b>{{ STATUS[k.status.ke]?.label }}</b></span>
                <button type="button" class="ikon-tombol kecil bahaya" aria-label="Hapus catatan" title="Hapus catatan" @click="hapusKondisi(u, k)"><Ikon nama="sampah" :ukuran="14" /></button>
              </div>
              <p>{{ k.isi }}</p>
            </li>
          </ol>
        </div>
      </article>
      </template>
    </template>

    <Dialog :buka="fu.buka" :judul="fu.id ? 'Ubah update' : 'Catat update baru'" lebar="620px" @tutup="fu.buka = false">
      <form class="form" @submit.prevent="simpanUpdate">
        <label class="isian"><span>Judul singkat</span>
          <input v-model="fu.judul" required maxlength="140" autofocus placeholder="mis. Tim Support pakai Claude Code">
        </label>
        <div class="dua">
          <label class="isian"><span>Mulai berlaku</span><input v-model="fu.mulai" type="date" required></label>
          <label class="isian"><span>Divisi / tim</span>
            <input v-model="fu.divisi" list="vu-divisi" maxlength="60" placeholder="Pilih atau ketik">
            <datalist id="vu-divisi"><option v-for="d in DIVISI" :key="d" :value="d" /></datalist>
          </label>
        </div>
        <label class="isian"><span>Jurnal — apa yang berubah</span>
          <textarea v-model="fu.jurnal" maxlength="4000" rows="3" placeholder="Apa yang diubah, mulai kapan, siapa yang menjalankan"></textarea>
        </label>
        <label class="isian"><span>Yang mau dipantau</span>
          <textarea v-model="fu.pantau" maxlength="1000" rows="2" placeholder="Tanda keberhasilan yang ingin dilihat"></textarea>
        </label>
        <fieldset class="isian sumber">
          <legend>Angka otomatis <small>(opsional)</small></legend>
          <label v-for="s in pilihanSumber" :key="s.kunci" class="centang">
            <input v-model="fu.sumber" type="checkbox" :value="s.kunci"> {{ s.label }}
          </label>
          <small>Belum ada sumber yang cocok? Catat kondisinya manual dulu, atau minta Claude menambahkan sumber datanya.</small>
        </fieldset>
        <label v-if="fu.id" class="isian"><span>Status</span>
          <select v-model="fu.status"><option v-for="(v, k) in STATUS" :key="k" :value="k">{{ v.label }}</option></select>
        </label>
        <p v-if="fu.galat" class="pesan-status bahaya" role="alert">{{ fu.galat }}</p>
        <div class="aksi-dialog">
          <button type="button" class="tombol garis" @click="fu.buka = false">Batal</button>
          <button type="submit" class="tombol" :disabled="fu.proses">{{ fu.proses ? 'Menyimpan…' : 'Simpan' }}</button>
        </div>
      </form>
    </Dialog>

    <Dialog :buka="fk.buka" judul="Catat kondisi terbaru" lebar="560px" @tutup="fk.buka = false">
      <form class="form" @submit.prevent="simpanKondisi">
        <p class="redup">{{ fk.id }} · {{ fk.judul }}</p>
        <label class="isian"><span>Kondisi sekarang</span>
          <textarea v-model="fk.isi" required maxlength="4000" rows="5" autofocus placeholder="Apa yang terjadi, angka bila ada, kendala, keputusan berikutnya"></textarea>
        </label>
        <div class="dua">
          <label class="isian"><span>Ubah status</span>
            <select v-model="fk.status">
              <option value="">Tetap</option>
              <option v-for="(v, k) in STATUS" :key="k" :value="k">{{ v.label }}</option>
            </select>
          </label>
          <label class="isian"><span>Dicatat oleh</span><input v-model="oleh" maxlength="60" required></label>
        </div>
        <p v-if="fk.galat" class="pesan-status bahaya" role="alert">{{ fk.galat }}</p>
        <div class="aksi-dialog">
          <button type="button" class="tombol garis" @click="fk.buka = false">Batal</button>
          <button type="submit" class="tombol" :disabled="fk.proses">{{ fk.proses ? 'Menyimpan…' : 'Simpan' }}</button>
        </div>
      </form>
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; max-width: 1080px; }
.tombol-kepala { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.masuk { max-width: 420px; display: grid; gap: 10px; }
.masuk h2 { display: inline-flex; align-items: center; gap: 8px; font-size: 17px; }
.masuk p { margin: 0; }
.kartu-judul h2 { display: inline-flex; align-items: center; gap: 8px; }

.claude { border-color: var(--aksen-lembut); background: linear-gradient(180deg, var(--aksen-lembut), transparent 70%), var(--kartu); }
.claude .kartu-judul { margin-bottom: 8px; }
.claude-isi { margin: 0; font-size: 14.5px; line-height: 1.65; white-space: pre-line; }
.kecil-p { margin: 10px 0 0; }
.putar { display: inline-block; width: 11px; height: 11px; margin-right: 4px; border: 2px solid var(--aksen-terang); border-right-color: transparent; border-radius: 50%; vertical-align: -1px; animation: putar .8s linear infinite; }
@keyframes putar { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .putar { animation: none; } }

.ringkas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.angka { display: grid; gap: 4px; text-align: left; font: inherit; color: inherit; padding: 14px 16px; }
button.angka { cursor: pointer; }
button.angka:hover, button.angka.aktif { border-color: var(--aksen-terang); }
.angka b { font-size: 24px; }
.angka .redup { display: inline-flex; align-items: center; gap: 4px; }
.warna-hijau { color: var(--baik); }
.warna-kuning { color: var(--waspada); }
.warna-biru { color: var(--aksen-terang); }

.bilah { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
.tautan { border: 0; background: none; padding: 0; font: inherit; color: var(--aksen-terang); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
.tautan:hover { color: var(--teks-kuat); }
.tautan:disabled { color: var(--teks-3); cursor: default; text-decoration: none; }
.kosong { margin: 0; text-align: center; }

/* Kartu ringkas (grid) */
.grid-upd { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr)); gap: 14px; }
.kartu-upd { display: flex; flex-direction: column; gap: 8px; width: 100%; text-align: left; font: inherit; color: inherit; cursor: pointer; border-left-width: 4px; transition: border-color .15s, transform .15s; }
.kartu-upd:hover { transform: translateY(-1px); border-top-color: var(--garis-kuat); border-right-color: var(--garis-kuat); border-bottom-color: var(--garis-kuat); }
.kartu-upd:focus-visible { outline: 2px solid var(--aksen); outline-offset: 2px; }
.ku-label { display: flex; flex-wrap: wrap; gap: 6px; }
.ku-judul { font-size: 15.5px; font-weight: 700; line-height: 1.35; color: var(--teks-kuat); }
.ku-tgl { font-size: 12px; }
.ku-kondisi { font-size: 13.5px; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; white-space: pre-line; }
.ku-sorot { display: flex; flex-wrap: wrap; gap: 6px; }
.ku-chip { font-size: 11.5px; padding: 2px 8px; border-radius: 6px; background: var(--kartu-2); color: var(--teks-3); }
.ku-chip b { color: var(--teks-kuat); margin-left: 2px; }
.ku-chip.buruk b { color: var(--bahaya); }
.ku-bawah { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: auto; padding-top: 4px; font-size: 12px; }
.ku-basi { color: var(--waspada); font-weight: 600; }
.ku-buka { margin-left: auto; color: var(--aksen-terang); font-weight: 600; }
.kembali { justify-self: start; font-size: 14px; }

/* Kartu update */
.upd { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; border-left-width: 4px; }
.upd-judul { min-width: 0; }
.garis-biru { border-left-color: var(--aksen); }
.garis-hijau { border-left-color: var(--baik); }
.garis-kuning { border-left-color: var(--waspada); }
.garis-abu { border-left-color: var(--garis-kuat); }
.upd-kepala { display: grid; grid-template-columns: auto 1fr auto; gap: 14px; align-items: start; }
.tanggal { display: grid; justify-items: center; min-width: 64px; padding: 6px 8px; border-radius: 10px; background: var(--kartu-2); line-height: 1.25; }
.tanggal b { font-size: 15px; }
.tanggal span { font-size: 11px; color: var(--teks-3); white-space: nowrap; }
.upd-judul h2 { font-size: 16.5px; line-height: 1.35; }
.label { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; }
.lencana.kode { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-weight: 700; color: var(--teks-kuat); background: var(--kartu-2); border: 1px solid var(--garis-kuat); }
.saran { font-size: 11.5px; color: var(--teks-3); border: 1px dashed var(--garis-kuat); border-radius: 6px; padding: 0 7px; }
.upd-aksi { display: flex; align-items: center; gap: 4px; }
.ikon-tombol { display: grid; place-items: center; width: 34px; height: 34px; border: 0; border-radius: 9px; background: transparent; color: var(--teks-3); cursor: pointer; }
.ikon-tombol:hover { background: var(--kartu-2); color: var(--teks-kuat); }
.ikon-tombol.bahaya:hover { color: var(--bahaya); background: rgba(255, 107, 107, .12); }
.ikon-tombol.kecil { width: 26px; height: 26px; margin-left: auto; }

.jurnal { margin: 0; color: var(--teks-2); display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; cursor: pointer; white-space: pre-line; }
.jurnal.penuh { -webkit-line-clamp: unset; line-clamp: unset; display: block; }
.pantau { margin: 0; font-size: 13px; color: var(--teks-2); }
.pantau span, .kecil-judul { display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; color: var(--teks-3); margin-right: 8px; }

.kondisi { padding: 12px 14px; border-radius: 12px; background: var(--kartu-2); }
.kondisi.basi { box-shadow: inset 3px 0 0 var(--waspada); }
.kondisi-kepala, .metrik-kepala { display: flex; align-items: center; justify-content: space-between; gap: 6px 12px; flex-wrap: wrap; margin-bottom: 6px; }
.metrik-kepala .redup { display: inline-flex; align-items: center; gap: 4px; }
.kondisi-isi { margin: 0; font-size: 14px; line-height: 1.6; white-space: pre-line; }
.peringatan { margin: 8px 0 0; font-size: 12.5px; color: var(--waspada); }
.oleh { font-weight: 700; color: var(--teks-2); }
.oleh.claude { color: var(--aksen-terang); }

.metrik { padding: 12px 14px; border-radius: 12px; border: 1px solid var(--garis); }
.metrik-ringkas { margin: 0 0 10px; font-size: 13.5px; color: var(--teks-2); }
.angka-daftar { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 8px; }
.angka-daftar li { display: grid; gap: 2px; padding: 8px 10px; border-radius: 10px; background: var(--kartu-2); cursor: default; }
.a-label { font-size: 12px; color: var(--teks-3); }
.a-nilai { font-size: 13px; color: var(--teks-3); }
.a-nilai s { text-decoration: none; }
.a-nilai b { font-size: 17px; color: var(--teks); }
.a-nilai small { margin-left: 2px; }
.tren-baik { color: var(--baik) !important; }
.tren-buruk { color: var(--bahaya) !important; }
.tren-netral, .tren-datar { color: var(--teks) !important; }
.orang { margin-top: 10px; font-size: 13px; }
.orang td { padding: 7px 10px; }
.orang tr.minim td { color: var(--waspada); }
.daftar-kecil { margin: 10px 0 0; padding-left: 18px; font-size: 13px; color: var(--teks-2); display: grid; gap: 2px; }
.tanpa-metrik { margin: 0; }
.seri { display: flex; align-items: flex-end; gap: 4px; height: 110px; margin-top: 10px; padding-top: 4px; }
.seri-batang { flex: 1; min-width: 0; height: 100%; display: grid; grid-template-rows: auto 1fr auto; align-items: end; justify-items: center; gap: 2px; }
.seri-batang i { display: block; width: 100%; max-width: 34px; border-radius: 5px 5px 2px 2px; background: var(--garis-kuat); align-self: end; }
.seri-batang.sesudah i { background: var(--aksen-terang); }
.seri-batang.minggu i { opacity: .45; }
.seri-nilai { font-size: 11px; color: var(--teks-3); }
.seri-tgl { font-size: 11px; color: var(--teks-3); }
.seri-batang.sesudah .seri-tgl { color: var(--aksen-terang); font-weight: 700; }
.contoh { margin-top: 12px; display: grid; gap: 8px; }
.contoh-baris { display: grid; gap: 3px; padding: 8px 10px; border-radius: 10px; background: var(--kartu-2); }
.contoh p { margin: 0; font-size: 13px; }
.asli { color: var(--waspada); }
.saran-kalimat { color: var(--teks); }
.saran-kalimat::before { content: "→ "; color: var(--baik); font-weight: 700; }
.baik-kalimat { color: var(--teks-2); padding-left: 10px; border-left: 3px solid var(--baik); }

.riwayat { display: grid; gap: 10px; }
.riwayat > .tautan { justify-self: start; font-size: 13px; }
.garis-waktu { list-style: none; margin: 0; padding: 0 0 0 14px; border-left: 2px solid var(--garis); display: grid; gap: 14px; }
.garis-waktu li { position: relative; }
.garis-waktu li::before { content: ""; position: absolute; left: -20px; top: 6px; width: 10px; height: 10px; border-radius: 50%; background: var(--kartu); border: 2px solid var(--garis-kuat); }
.gw-kepala { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 12.5px; }
.garis-waktu p { margin: 4px 0 0; font-size: 13.5px; color: var(--teks-2); white-space: pre-line; line-height: 1.6; }

/* Formulir dialog */
.form { display: grid; gap: 14px; }
.form p { margin: 0; }
.dua { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; }
.sumber { border: 0; padding: 0; margin: 0; display: grid; gap: 6px; }
.sumber legend { font-size: 13px; font-weight: 600; color: var(--teks-2); padding: 0; margin-bottom: 4px; }
.sumber legend small { font-weight: 500; color: var(--teks-3); }
.centang { display: flex; align-items: center; gap: 8px; font-size: 13.5px; cursor: pointer; }

@media (max-width: 760px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
  .upd-kepala { grid-template-columns: auto 1fr; }
  .upd-aksi { grid-column: 1 / -1; justify-content: flex-end; }
  .dua { grid-template-columns: 1fr; }
}
.angka-kanan td:not(:first-child), .angka-kanan th:not(:first-child) { text-align: right; font-variant-numeric: tabular-nums; }
.orang tr.berjalan td { color: var(--teks-2); font-style: italic; }
.catatan-tabel { font-size: 12px; margin: 6px 0 0; }
.wm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr)); gap: 10px; margin-top: 10px; }
.wm-kartu { padding: 10px 12px; border-radius: 12px; background: var(--kartu-2); display: grid; gap: 8px; align-content: start; border: 1px solid transparent; }
.wm-kartu.ada_tanda { border-color: rgba(255, 107, 107, .35); }
.wm-kepala { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.wm-kepala .redup { font-size: 12px; }
.wm-tanda { margin: 0; padding-left: 16px; font-size: 12.5px; color: var(--bahaya); }
.wm-blok { display: grid; gap: 3px; font-size: 13px; }
.wm-blok p { margin: 0; overflow-wrap: anywhere; }
.wm-label { font-size: 11px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: var(--teks-2); }
.wm-lain { margin: 0; font-size: 12px; overflow-wrap: anywhere; }
.wm-basi { margin-top: 10px; font-size: 13px; }
.wm-basi summary { cursor: pointer; color: var(--waspada); }
</style>
