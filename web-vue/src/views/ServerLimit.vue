<script setup>
// Limit Resource (VelocityGuard): pengganti LVE CloudLinux untuk server DirectAdmin non-CloudLinux (sanke).
// Limit = DA User Cgroups (systemd user-UID.slice), nilai default dari preset Kecil/Sedang/Tinggi di
// /etc/velocity-cg/preset yang diterapkan velocity-cg-default ke semua user DA (kecuali admin; nilai kustom dipertahankan).
// Data: GET /api/servers/limit (installer_status.py → scripts/server_limit_agent.py). Ganti preset: POST /api/servers/limit/aksi
// → job latar (cadangan → terapkan → verifikasi slice → kembalikan bila gagal). Override per akun: POST yang sama
// {user, nilai} → /etc/velocity-cg/user/USER (menang atas preset; nilai null = kembali ke preset).
import Dialog from '../components/Dialog.vue'
import PilihServer from '../components/PilihServer.vue'
import { pilihServer } from '../jenisServer.js'
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import Ikon from '../components/Ikon.vue'
import PelakuAkun from '../components/PelakuAkun.vue'
import { namaAkun } from '../akun.js'
import { konfirmasi } from '../konfirmasi.js'
import { minta, kirim, pakaiPolling } from '../api.js'

const lim = pakaiPolling('/api/servers/limit', 300000)
const segarkan = ref(false)
async function muatSegar() {
  segarkan.value = true
  try { lim.data.value = await minta('/api/servers/limit?segar=1'); lim.galat.value = null }
  catch (e) { lim.galat.value = e }
  finally { segarkan.value = false }
}
// Hanya server DA non-CloudLinux (CloudLinux memakai LVE sendiri)
const servers = computed(() => (lim.data.value?.servers || []).filter((s) => !s.ok || s.didukung))
const pilih = pilihServer()
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || servers.value[0] || null)
const oleh = namaAkun

const PRESET = [
  { k: 'kecil', label: 'Kecil', ket: 'Situs company profile / blog ringan' },
  { k: 'sedang', label: 'Sedang', ket: 'Toko online / berita dengan trafik sedang' },
  { k: 'tinggi', label: 'Tinggi', ket: 'Situs ramai, banyak plugin / cron berat' },
]
const BARIS = [
  { k: 'CPUQuota', label: 'CPU', f: (v) => `${v} (${Number.parseInt(v) / 100} core)` },
  { k: 'MemoryMax', label: 'RAM maksimal', f: (v) => `${v}B` },
  { k: 'IOReadBandwidthMax', label: 'IO baca', f: (v) => `${v}B/dtk` },
  { k: 'IOWriteBandwidthMax', label: 'IO tulis', f: (v) => `${v}B/dtk` },
  { k: 'IOReadIOPSMax', label: 'IOPS baca', f: (v) => v },
  { k: 'IOWriteIOPSMax', label: 'IOPS tulis', f: (v) => v },
  { k: 'TasksMax', label: 'Proses / thread', f: (v) => v },
  { k: 'EP', label: 'PHP serentak (EP)', f: (v) => `${v} request` },
  { k: 'MySQLConn', label: 'Koneksi MySQL', f: (v) => `${v} per user database` },
  { k: 'MySQLTime', label: 'Lama query MySQL', f: (v) => `maks ${v} dtk` },
]
// ringkas batas MySQL semua akun database user: "15 kon · 30 dtk" (nilai berbeda digabung "15/7")
const sqlRingkas = (akun) => {
  if (!akun?.length) return '—'
  const u = (k) => [...new Set(akun.map((x) => (x[k] === '0' ? '∞' : x[k])))].join('/')
  return `${u('koneksi')} kon · ${u('query')} dtk`
}
const PESAN = {
  invalid_oleh: 'Masuk dulu lewat tombol "Masuk dengan VD.net" di kanan atas — setiap perubahan dicatat atas nama akun Anda.',
  login_diperlukan: 'Sesi login habis atau belum masuk. Klik "Masuk dengan VD.net" di kanan atas.',
  server_tidak_dikenal: 'Server tidak dikenal; muat ulang halaman.',
  aksi_sedang_jalan: 'Masih ada perubahan berjalan di server ini. Tunggu selesai dulu.',
  preset_tidak_dikenal: 'Preset tidak dikenal.',
  velocity_cg_belum_terpasang: 'Mekanisme limit belum terpasang di server ini (build/sanke/cgroup/pasang.sh).',
  kunci_sibuk: 'Timer/hook limit di server masih berjalan lebih dari 10 menit — tidak ada yang diubah. Coba lagi nanti.',
  verifikasi_gagal: 'Nilai limit (slice, EP, atau MySQL) tidak sesuai sesudah diterapkan — semua dikembalikan ke preset lama.',
  galat: 'Agen berhenti karena galat — keadaan bisa setengah jadi. Muat ulang dan periksa kolom Status akun; cadangan ada di /root/velocity-cadangan/limit-resource-*.',
  bukan_directadmin: 'Bukan server DirectAdmin.',
  cloudlinux_pakai_lve: 'Server CloudLinux — limit memakai LVE.',
  job_tidak_ada: 'Status perubahan hilang (layanan dashboard di-restart). Muat ulang.',
  forbidden: 'Ditolak: hanya bisa dijalankan dari halaman dashboard ini.',
  user_tidak_ada: 'User DA tidak ada di server ini.',
  user_dikecualikan: 'Akun ini dikecualikan (tanpa batas) — tidak bisa diatur per akun.',
  nilai_tidak_sah: 'Ada nilai yang tidak sah (harus angka bulat positif; MySQL boleh 0 = tanpa batas).',
  timeout: 'Server tidak menjawab (timeout) — keadaan bisa setengah jadi. Muat ulang dan periksa kolom Status akun.',
}
const pesanGalat = (e) => PESAN[e] || e || 'gagal'
const pesan = reactive({ teks: '', galat: false })
const dipilih = ref('')
watch(() => [terpilih.value?.host, terpilih.value?.preset], ([, p]) => { dipilih.value = p || '' }, { immediate: true })

const ringkas = (n) => (n == null ? 'tanpa batas' : n)
const mem = (b) => (b == null ? 'tanpa batas' : `${Math.round(b / 1048576)} MB`)

// Pengingat (permintaan pemilik 25 Okt): salinan uji limit per akun di Sanke menunggu dihapus mulai 26 Okt.
// Hilang sendiri begitu akunnya dihapus di DirectAdmin; zona showa/tancho ikut terhapus (zona-sinkron), override oleh timer.
const UJI_HAPUS = { host: '157.66.55.81', mulai: '2026-10-26', users: ['ongkir', 'pengaca6'] }
const ujiSisa = computed(() => {
  const s = terpilih.value
  if (s?.host !== UJI_HAPUS.host || new Date().toISOString().slice(0, 10) < UJI_HAPUS.mulai) return []
  return UJI_HAPUS.users.filter((u) => s.users?.some((x) => x.user === u))
})

// ---- Form limit per akun (satuan form → nilai user.conf/override) ----
// Default LVE server Cahyadi (lvectl list, 25 Okt 2026): SPEED 100, PMEM 1024M, EP 20, NPROC 100, IO 1024 KB/s, IOPS 1024; tanpa MySQL Governor
const LVE_CAHYADI = { cpu: 100, ram: 1024, ioBaca: 1024, ioTulis: 1024, iopsBaca: 1024, iopsTulis: 1024, proses: 100, ep: 20, sqlKon: 0, sqlDtk: 0 }
const ISIAN = [
  { k: 'cpu', label: 'CPU (%)', ket: '100 = 1 core', min: 1 },
  { k: 'ram', label: 'RAM maksimal (MB)', min: 1 },
  { k: 'ioBaca', label: 'IO baca (KB/dtk)', min: 1 },
  { k: 'ioTulis', label: 'IO tulis (KB/dtk)', min: 1 },
  { k: 'iopsBaca', label: 'IOPS baca', min: 1 },
  { k: 'iopsTulis', label: 'IOPS tulis', min: 1 },
  { k: 'proses', label: 'Proses / thread', min: 1 },
  { k: 'ep', label: 'PHP serentak (EP)', min: 1 },
  { k: 'sqlKon', label: 'Koneksi MySQL', ket: '0 = tanpa batas', min: 0 },
  { k: 'sqlDtk', label: 'Lama query MySQL (dtk)', ket: '0 = tanpa batas', min: 0 },
]
const KB = (v) => { const m = /^(\d+)([KMG]?)$/.exec(v || ''); return m ? Number(m[1]) * { '': 0.001, K: 1, M: 1000, G: 1e6 }[m[2]] : null }
const MB = (v) => { const m = /^(\d+)([MG])$/.exec(v || ''); return m ? Number(m[1]) * (m[2] === 'G' ? 1024 : 1) : null }
function keForm(u, preset) {
  const n = { ...preset, ...u.nilai, ...u.override }
  const sql = u.mysql?.[0]
  return {
    cpu: Number.parseInt(n.CPUQuota), ram: MB(n.MemoryMax), ioBaca: KB(n.IOReadBandwidthMax), ioTulis: KB(n.IOWriteBandwidthMax),
    iopsBaca: Number(n.IOReadIOPSMax), iopsTulis: Number(n.IOWriteIOPSMax), proses: Number(n.TasksMax),
    ep: Number(u.override?.EP || u.ep?.[0] || preset.EP),
    sqlKon: Number(u.override?.MySQLConn ?? sql?.koneksi ?? preset.MySQLConn), sqlDtk: Number(u.override?.MySQLTime ?? sql?.query ?? preset.MySQLTime),
  }
}
const dariForm = (f) => ({
  CPUQuota: `${f.cpu}%`, MemoryMax: f.ram % 1024 ? `${f.ram}M` : `${f.ram / 1024}G`, IOReadBandwidthMax: `${f.ioBaca}K`,
  IOWriteBandwidthMax: `${f.ioTulis}K`, IOReadIOPSMax: String(f.iopsBaca), IOWriteIOPSMax: String(f.iopsTulis),
  TasksMax: String(f.proses), EP: String(f.ep), MySQLConn: String(f.sqlKon), MySQLTime: String(f.sqlDtk),
})
const form = reactive({ buka: false, user: null, data: {} })
function bukaForm(u) {
  Object.assign(form, { buka: true, user: u, data: keForm(u, terpilih.value.daftar[terpilih.value.preset]) })
}

async function kirimUser(user, nilai, teksJalan) {
  if (!oleh.value.trim()) { Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true }); return }
  const s = terpilih.value
  try {
    const j = await kirim('/api/servers/limit/aksi', { server: s.host, user, nilai, oleh: oleh.value.trim() })
    jobs.value = { ...jobs.value, [s.host]: j }
    Object.assign(pesan, { teks: `${s.name}: ${teksJalan}…`, galat: false })
    form.buka = false
    pantau()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  }
}
function simpanUser() {
  const f = form.data
  if (ISIAN.some((i) => !Number.isInteger(f[i.k]) || f[i.k] < i.min)) { Object.assign(pesan, { teks: PESAN.nilai_tidak_sah, galat: true }); return }
  kirimUser(form.user.user, dariForm(f), `mengatur limit ${form.user.user}`)
}
async function kembaliPreset(u) {
  const ya = await konfirmasi({
    judul: `Kembalikan ${u.user} ke preset ${terpilih.value.preset}?`, tombol: 'Kembalikan',
    teks: 'Limit khusus akun ini dihapus; CPU, RAM, IO, proses, EP, dan batas MySQL kembali mengikuti preset server. Cadangan dibuat.',
  })
  if (ya) kirimUser(u.user, null, `mengembalikan ${u.user} ke preset`)
}

// ---- Job terapkan (per host; gagal ambil status sekali = coba lagi, bukan dianggap gagal) ----
const jobs = ref({})
let timer = null
const job = computed(() => jobs.value[terpilih.value?.host] || null)
watch(() => lim.data.value?.job, (d) => { for (const j of d || []) jobs.value = { ...jobs.value, [j.host]: j }; pantau() })
const berjalan = computed(() => job.value?.status === 'berjalan')
let galatBeruntun = 0
function pantau() {
  const aktif = () => Object.values(jobs.value).find((j) => j.status === 'berjalan')
  if (timer || !aktif()) return
  timer = setInterval(async () => {
    const j = aktif()
    if (!j) { clearInterval(timer); timer = null; return }
    let baru
    try {
      baru = await minta(`/api/servers/limit/job?id=${j.id}`); galatBeruntun = 0
    } catch (e) {
      if (++galatBeruntun < 5) return
      baru = { ...j, status: 'gagal', hasil: { error: e.message } }
    }
    jobs.value = { ...jobs.value, [j.host]: baru }
    if (baru.status !== 'berjalan') {
      clearInterval(timer); timer = null
      Object.assign(pesan, baru.status === 'selesai'
        ? { teks: baru.user ? `${baru.server}: limit ${baru.user} diterapkan.` : `${baru.server}: preset ${baru.preset} diterapkan.`, galat: false }
        : { teks: `${baru.server}: ${pesanGalat(baru.hasil?.error)}`, galat: true })
      muatSegar()
      pantau() // job server lain masih berjalan
    }
  }, 3000)
}
onBeforeUnmount(() => clearInterval(timer))

async function terapkan() {
  if (!oleh.value.trim()) { Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true }); return }
  const s = terpilih.value
  const p = s.daftar[dipilih.value]
  const ya = await konfirmasi({
    judul: `Terapkan preset ${dipilih.value} di ${s.name}?`, tombol: 'Terapkan',
    teks: `Semua user DA (kecuali admin dan nilai kustom) dibatasi CPU ${p.CPUQuota}, RAM ${p.MemoryMax}, IO ${p.IOReadBandwidthMax}B/dtk, ${p.TasksMax} proses, ${p.EP} request PHP serentak, ${p.MySQLConn} koneksi MySQL & query maks ${p.MySQLTime} dtk. Berlaku langsung tanpa restart; user baru & hasil restore ikut. Cadangan dibuat, bila verifikasi gagal dikembalikan otomatis.`,
  })
  if (!ya) return
  try {
    const j = await kirim('/api/servers/limit/aksi', { server: s.host, preset: dipilih.value, oleh: oleh.value.trim() })
    jobs.value = { ...jobs.value, [s.host]: j }
    Object.assign(pesan, { teks: `${s.name}: menerapkan preset ${dipilih.value}…`, galat: false })
    pantau()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  }
}
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Limit Resource <span class="merek-guard">VelocityGuard</span></h1>
        <p class="redup">Pengganti LVE CloudLinux untuk server DirectAdmin biasa: batas CPU, RAM, IO, dan proses per akun lewat cgroup DirectAdmin.</p>
      </div>
      <div class="kepala-aksi">
        <div class="nama-saya"><span class="redup">Dicatat sebagai</span><PelakuAkun id="nama-limit" /></div>
        <button type="button" class="tombol kecil" :disabled="segarkan || (lim.memuat.value && !lim.data.value)" @click="muatSegar"><Ikon nama="ulang" :ukuran="16" /> {{ segarkan ? 'Membaca…' : 'Muat ulang' }}</button>
      </div>
    </header>

    <p v-if="lim.memuat.value && !lim.data.value" class="redup" role="status">Membaca limit semua server lewat SSH…</p>
    <p v-else-if="lim.galat.value && !lim.data.value" class="pesan-status bahaya">Gagal memuat: {{ lim.galat.value.message }}</p>
    <p v-else-if="lim.data.value?.error" class="pesan-status bahaya">Gagal memuat: {{ pesanGalat(lim.data.value.error) }}</p>
    <p v-else-if="lim.data.value && !servers.length" class="redup">Tidak ada server DirectAdmin non-CloudLinux.</p>

    <template v-else-if="terpilih">
      <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>
      <PilihServer :servers="servers" :model-value="terpilih.name" :titik="terpilih.terpasang ? 'baik' : 'abu'" @update:model-value="pilih = $event" />

      <section class="kartu" aria-labelledby="judul-limit">
        <div class="kartu-judul">
          <h2 id="judul-limit"><Ikon nama="server" :ukuran="16" /> {{ terpilih.name }}
            <span v-if="terpilih.terpasang" class="lencana hijau">Preset aktif: {{ terpilih.preset }}</span>
          </h2>
        </div>
        <p v-if="!terpilih.ok" class="pesan-status bahaya">Tidak bisa dibaca: {{ pesanGalat(terpilih.error) }} {{ terpilih.pesan || '' }}</p>
        <p v-else-if="!terpilih.terpasang" class="pesan-status waspada">{{ PESAN.velocity_cg_belum_terpasang }}</p>
        <template v-else>
          <p v-if="ujiSisa.length" class="pesan-status waspada" role="status">
            <b>Pengingat:</b> akun uji {{ ujiSisa.join(', ') }} (salinan dari Cahyadi/Kiya, 25 Okt) masih ada di {{ terpilih.name }} dan menunggu dihapus.
            Hapus lewat DirectAdmin {{ terpilih.name }} → List Users. Akun asli di server asal tidak ikut terhapus.
          </p>
          <div class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">Per akun</th><th v-for="p in PRESET" :key="p.k" scope="col" :class="{ aktif: p.k === terpilih.preset }">
                <label class="pilih"><input v-model="dipilih" type="radio" name="preset" :value="p.k" :disabled="berjalan"> {{ p.label }}</label>
                <small class="redup blok-t">{{ p.ket }}</small></th></tr></thead>
              <tbody>
                <tr v-for="b in BARIS" :key="b.k"><th scope="row">{{ b.label }}</th>
                  <td v-for="p in PRESET" :key="p.k" :class="{ aktif: p.k === terpilih.preset }">{{ b.f(terpilih.daftar[p.k][b.k]) }}</td></tr>
              </tbody>
            </table>
          </div>
          <p class="redup kecil-p">Akun <code>admin</code> tidak dibatasi. Nilai yang diubah manual per user/paket di DirectAdmin (selain nilai preset) dipertahankan. Swap per akun 0. EP = <code>pm.max_children</code> PHP-FPM per versi PHP (request lebih antre, bukan error 508). Batas MySQL berlaku per user database (akun DB sistem tidak dibatasi); query yang melewati batas waktu dihentikan.</p>

          <div v-if="job" class="job" :class="job.status" role="status">
            <span v-if="berjalan" class="putar besar" aria-hidden="true" />
            <Ikon v-else :nama="job.status === 'selesai' ? 'centang' : 'peringatan'" :ukuran="20" />
            <div>
              <b>{{ berjalan ? 'Menerapkan…' : job.status === 'selesai' ? 'Berhasil' : 'Gagal' }}</b> · {{ job.user ? `akun ${job.user}` : `preset ${job.preset}` }}
              <span v-if="job.status === 'gagal'" class="blok-t">{{ pesanGalat(job.hasil?.error) }}</span>
              <small v-if="job.hasil?.hasil?.cadangan" class="redup blok-t">Cadangan: {{ job.hasil.hasil.cadangan }}</small>
            </div>
          </div>
          <div class="aksi">
            <button type="button" class="tombol" :disabled="berjalan || !dipilih || dipilih === terpilih.preset" @click="terapkan">Terapkan preset {{ dipilih }}</button>
          </div>

          <h3 class="sub">Akun ({{ terpilih.users.length }})</h3>
          <div class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">User</th><th scope="col">CPU</th><th scope="col">RAM</th><th scope="col">Proses</th><th scope="col">EP</th><th scope="col">MySQL</th><th scope="col">Status</th><th scope="col">Atur</th></tr></thead>
              <tbody>
                <tr v-for="u in terpilih.users" :key="u.user">
                  <td><b>{{ u.user }}</b> <span v-if="u.kecuali" class="lencana abu">dikecualikan</span><span v-if="Object.keys(u.override || {}).length" class="lencana ungu" title="Limit khusus akun ini (bukan preset)">per akun</span><span v-else-if="u.kustom.length" class="lencana ungu" :title="u.kustom.join(', ')">kustom</span></td>
                  <td>{{ u.nyata.cpu == null ? 'tanpa batas' : `${u.nyata.cpu}%` }}</td>
                  <td>{{ mem(u.nyata.mem) }}</td>
                  <td>{{ ringkas(u.nyata.tasks) }}</td>
                  <td>{{ u.ep?.length ? u.ep.join('/') : '—' }}</td>
                  <td :title="(u.mysql || []).map((x) => `${x.akun}: ${x.koneksi} koneksi, ${x.query} dtk`).join('\n')">{{ sqlRingkas(u.mysql) }}</td>
                  <td><span class="lencana" :class="u.sesuai ? 'hijau' : 'kuning'">{{ u.sesuai ? 'sesuai' : 'belum diterapkan' }}</span></td>
                  <td class="aksi-u">
                    <template v-if="!u.kecuali">
                      <button type="button" class="tombol garis kecil" :disabled="berjalan" @click="bukaForm(u)">Atur</button>
                      <button v-if="Object.keys(u.override || {}).length" type="button" class="tombol garis kecil" :disabled="berjalan" @click="kembaliPreset(u)">Ke preset</button>
                    </template>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </section>
    </template>

    <Dialog :buka="form.buka" :judul="`Limit akun ${form.user?.user || ''}`" lebar="640px" @tutup="form.buka = false">
      <form class="form-limit" @submit.prevent="simpanUser">
        <p class="redup kecil-p">Berlaku hanya untuk akun ini dan tetap dipakai walau preset server diganti. Diisi dari nilai sekarang.</p>
        <div class="dua">
          <label v-for="i in ISIAN" :key="i.k" class="isian"><span>{{ i.label }}</span>
            <input v-model.number="form.data[i.k]" type="number" :min="i.min" step="1" required>
            <small v-if="i.ket">{{ i.ket }}</small></label>
        </div>
        <div class="aksi">
          <button type="button" class="tombol garis kecil" @click="form.data = { ...LVE_CAHYADI }">Isi seperti LVE Cahyadi</button>
          <span class="isi" />
          <button type="button" class="tombol garis kecil" @click="form.buka = false">Batal</button>
          <button type="submit" class="tombol kecil" :disabled="berjalan">Simpan</button>
        </div>
      </form>
    </Dialog>
  </div>
</template>

<style scoped>
.kecil-p { margin: 0; font-size: 13px; line-height: 1.55; }
.blok-t { display: block; }
th.aktif, td.aktif { background: var(--aksen-lembut); }
.pilih { display: inline-flex; gap: 6px; align-items: center; cursor: pointer; font-weight: 700; }
.sub { margin: 18px 0 8px; font-size: 15px; }
.job { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 12px; align-items: center; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--garis); margin: 12px 0; }
.job.selesai > svg { color: var(--baik); }
.job.gagal { border-color: color-mix(in srgb, var(--bahaya) 50%, transparent); }
.job.gagal > svg { color: var(--bahaya); }
.putar { width: 18px; height: 18px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: putar .8s linear infinite; }
@keyframes putar { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .putar { animation: none; } }
.aksi-u { white-space: nowrap; }
.aksi-u .tombol + .tombol { margin-left: 6px; }
.form-limit { display: grid; gap: 12px; }
.form-limit .dua { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.form-limit .isi { flex: 1; }
@media (max-width: 560px) { .form-limit .dua { grid-template-columns: minmax(0, 1fr); } }
.aksi { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
</style>
