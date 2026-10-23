<script setup>
// Limit Resource (VelocityGuard): pengganti LVE CloudLinux untuk server DirectAdmin non-CloudLinux (sanke).
// Limit = DA User Cgroups (systemd user-UID.slice), nilai default dari preset Kecil/Sedang/Tinggi di
// /etc/velocity-cg/preset yang diterapkan velocity-cg-default ke semua user DA (kecuali admin; nilai kustom dipertahankan).
// Data: GET /api/servers/limit (installer_status.py → scripts/server_limit_agent.py). Ganti preset: POST /api/servers/limit/aksi
// → job latar (cadangan → terapkan → verifikasi slice → kembalikan bila gagal).
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
]
const PESAN = {
  invalid_oleh: 'Masuk dulu lewat tombol "Masuk dengan VD.net" di kanan atas — setiap perubahan dicatat atas nama akun Anda.',
  login_diperlukan: 'Sesi login habis atau belum masuk. Klik "Masuk dengan VD.net" di kanan atas.',
  server_tidak_dikenal: 'Server tidak dikenal; muat ulang halaman.',
  aksi_sedang_jalan: 'Masih ada perubahan berjalan di server ini. Tunggu selesai dulu.',
  preset_tidak_dikenal: 'Preset tidak dikenal.',
  velocity_cg_belum_terpasang: 'Mekanisme limit belum terpasang di server ini (build/sanke/cgroup/pasang.sh).',
  kunci_sibuk: 'Timer/hook limit di server masih berjalan lebih dari 10 menit — tidak ada yang diubah. Coba lagi nanti.',
  verifikasi_gagal: 'Nilai slice tidak sesuai sesudah diterapkan — semua dikembalikan ke preset lama.',
  galat: 'Agen berhenti karena galat — keadaan bisa setengah jadi. Muat ulang dan periksa kolom Status akun; cadangan ada di /root/velocity-cadangan/limit-resource-*.',
  bukan_directadmin: 'Bukan server DirectAdmin.',
  cloudlinux_pakai_lve: 'Server CloudLinux — limit memakai LVE.',
  job_tidak_ada: 'Status perubahan hilang (layanan dashboard di-restart). Muat ulang.',
  forbidden: 'Ditolak: hanya bisa dijalankan dari halaman dashboard ini.',
  timeout: 'Server tidak menjawab (timeout) — keadaan bisa setengah jadi. Muat ulang dan periksa kolom Status akun.',
}
const pesanGalat = (e) => PESAN[e] || e || 'gagal'
const pesan = reactive({ teks: '', galat: false })
const dipilih = ref('')
watch(() => [terpilih.value?.host, terpilih.value?.preset], ([, p]) => { dipilih.value = p || '' }, { immediate: true })

const ringkas = (n) => (n == null ? 'tanpa batas' : n)
const mem = (b) => (b == null ? 'tanpa batas' : `${Math.round(b / 1048576)} MB`)

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
        ? { teks: `${baru.server}: preset ${baru.preset} diterapkan.`, galat: false }
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
    teks: `Semua user DA (kecuali admin dan nilai kustom) dibatasi CPU ${p.CPUQuota}, RAM ${p.MemoryMax}, IO ${p.IOReadBandwidthMax}B/dtk, ${p.TasksMax} proses. Berlaku langsung tanpa restart; user baru & hasil restore ikut. Cadangan dibuat, bila verifikasi gagal dikembalikan otomatis.`,
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
          <p class="redup kecil-p">Akun <code>admin</code> tidak dibatasi. Nilai yang diubah manual per user/paket di DirectAdmin (selain nilai preset) dipertahankan. Swap per akun 0; koneksi MySQL maks 25 per user database.</p>

          <div v-if="job" class="job" :class="job.status" role="status">
            <span v-if="berjalan" class="putar besar" aria-hidden="true" />
            <Ikon v-else :nama="job.status === 'selesai' ? 'centang' : 'peringatan'" :ukuran="20" />
            <div>
              <b>{{ berjalan ? 'Menerapkan…' : job.status === 'selesai' ? 'Berhasil' : 'Gagal' }}</b> · preset {{ job.preset }}
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
              <thead><tr><th scope="col">User</th><th scope="col">CPU</th><th scope="col">RAM</th><th scope="col">Proses</th><th scope="col">Status</th></tr></thead>
              <tbody>
                <tr v-for="u in terpilih.users" :key="u.user">
                  <td><b>{{ u.user }}</b> <span v-if="u.kecuali" class="lencana abu">dikecualikan</span><span v-if="u.kustom.length" class="lencana ungu" :title="u.kustom.join(', ')">kustom</span></td>
                  <td>{{ u.nyata.cpu == null ? 'tanpa batas' : `${u.nyata.cpu}%` }}</td>
                  <td>{{ mem(u.nyata.mem) }}</td>
                  <td>{{ ringkas(u.nyata.tasks) }}</td>
                  <td><span class="lencana" :class="u.sesuai ? 'hijau' : 'kuning'">{{ u.sesuai ? 'sesuai' : 'belum diterapkan' }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </section>
    </template>
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
.aksi { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
</style>
