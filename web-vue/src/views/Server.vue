<script setup>
// Server: daftar server tujuan installer (/api/servers, data /var/lib/velocity/servers.json)
// + PC kantor (PC Lokal, PC Backup; /var/lib/velocity/servers-monitor.json, hanya dipantau) bertag pembeda
// + kapasitas disk & resource tiap server (/api/servers/resource, SSH, cache 60 dtk)
// + kontrol daya Local PC (dipindah dari beranda agar tidak terpencet).
import { ref, reactive, computed, onMounted } from 'vue'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import { minta, kirim, pakaiPolling, ukuranBerkas, waktuLalu } from '../api.js'
import { konfirmasi } from '../konfirmasi.js'
import { jenisServer } from '../jenisServer.js'

const PESAN = {
  nama_wajib: 'Nama server wajib diisi.',
  host_tidak_valid: 'Host hanya boleh huruf, angka, titik, dan tanda hubung.',
  user_tidak_valid: 'Username SSH tidak valid.',
  port_tidak_valid: 'Port harus 1–65535.',
  host_sudah_terdaftar: 'Host ini sudah terdaftar di server lain.',
  server_tidak_ditemukan: 'Server tidak ditemukan (daftar berubah?). Muat ulang halaman.',
  server_terakhir: 'Server terakhir tidak bisa dihapus.',
  diatur_lewat_env_INSTALLER_SERVERS: 'Daftar server diatur lewat env INSTALLER_SERVERS, tidak bisa diubah dari sini.',
  unauthorized: 'Tidak berwenang (butuh token dari luar LAN).',
}
function pesan(kode) {
  const m = /^(host_dipakai|masih_dipakai)_(\d+)_manifest$/.exec(kode || '')
  if (m) return m[1] === 'masih_dipakai' ? `Masih dipakai ${m[2]} manifest situs, tidak bisa dihapus.` : `Host lama masih dipakai ${m[2]} manifest situs.`
  return PESAN[kode] || `Gagal: ${kode}`
}

const servers = ref([])
const pc = ref([])
const simpananPc = ref('')
// Satu daftar untuk ditampilkan: server hosting dulu (urutan = default installer), lalu PC kantor
const daftar = computed(() => [
  ...servers.value.map((s, i) => ({ ...s, jenis: 'hosting', i, kunci: i })),
  ...pc.value.map((s) => ({ ...s, kunci: `pc:${s.host}` })),
])
const hanyaBaca = ref(false)
const simpanan = ref('')
const memuat = ref(true)
const galatMuat = ref('')
const statusDaftar = reactive({ teks: '', kelas: '' })
const hasilTes = reactive({})

function terapkan(d) {
  servers.value = d.servers || []
  pc.value = d.pc || []
  hanyaBaca.value = !!d.readonly
  if (d.store) simpanan.value = d.store
  if (d.store_pc) simpananPc.value = d.store_pc
}
async function muat() {
  try { terapkan(await minta('/api/servers')); galatMuat.value = '' }
  catch (e) { galatMuat.value = pesan(e.message) }
  finally { memuat.value = false }
}
onMounted(muat)
const beriStatus = (teks, galat) => Object.assign(statusDaftar, { teks, kelas: galat ? 'bahaya' : 'baik' })
const bersihkanTes = () => Object.keys(hasilTes).forEach((k) => delete hasilTes[k])

async function tesSsh(s) {
  const k = s.kunci
  hasilTes[k] = 'jalan'
  try { hasilTes[k] = await kirim('/api/servers/test', s.jenis === 'hosting' ? { index: s.i } : { pc: true, host: s.host }) }
  catch (e) { hasilTes[k] = { ok: false, error: pesan(e.message) } }
}
async function jadikanDefault(i) {
  const s = servers.value[i]
  if (!(await konfirmasi({ judul: 'Jadikan server default?', teks: `"${s.name}" akan menjadi tujuan untuk manifest situs baru.`, tombol: 'Jadikan default' }))) return
  try { terapkan(await kirim('/api/servers/default', { index: i })); bersihkanTes(); beriStatus(`${s.name} sekarang jadi default.`) }
  catch (e) { beriStatus(pesan(e.message), true) }
}
async function hapus(i) {
  const s = servers.value[i]
  if (!(await konfirmasi({ judul: 'Hapus server?', teks: `Hapus "${s.name}" (${s.host}) dari daftar server installer?`, tombol: 'Ya, hapus', kelas: 'bahaya' }))) return
  try { terapkan(await kirim('/api/servers/delete', { index: i })); bersihkanTes(); beriStatus(`Server ${s.name} dihapus.`) }
  catch (e) { beriStatus(pesan(e.message), true) }
}

// Resource (disk, CPU, RAM, load) per host
const resource = pakaiPolling('/api/servers/resource', 60000)
const segarkan = ref(false)
async function muatSegar() {
  segarkan.value = true
  try { resource.data.value = await minta('/api/servers/resource?segar=1'); resource.galat.value = null }
  catch (e) { resource.galat.value = e }
  finally { segarkan.value = false }
}
const resPerHost = computed(() => Object.fromEntries((resource.data.value?.servers || []).map((r) => [r.host, r])))
const tingkat = (p) => (p >= 90 ? 'bahaya' : p >= 75 ? 'waspada' : '')
const lamaNyala = (u) => (u >= 86400 ? `${Math.floor(u / 86400)} hari` : `${Math.floor(u / 3600)} jam`)
// Ringkasan kapasitas = server hosting saja (disk 1 TB PC Backup tidak ikut menggelembungkan "sisa disk")
const resHosting = computed(() => (resource.data.value?.servers || []).filter((r) => !r.jenis || r.jenis === 'hosting'))
const ringkasan = computed(() => {
  const semua = resHosting.value.filter((r) => r.ok)
  const disk = semua.flatMap((r) => r.disks || [])
  const total = disk.reduce((a, d) => a + d.total, 0)
  const pakai = disk.reduce((a, d) => a + d.used, 0)
  const sisa = disk.reduce((a, d) => a + d.free, 0)
  return {
    online: semua.length, jumlah: resHosting.value.length,
    total, pakai, sisa, persen: pakai + sisa ? Math.round((pakai * 1000) / (pakai + sisa)) / 10 : 0,
    core: semua.reduce((a, r) => a + (r.cpu_core || 0), 0),
    ram: semua.reduce((a, r) => a + (r.ram?.total || 0), 0),
  }
})

// Tambah
const baru = reactive({ name: '', host: '', user: 'root', port: '', notes: '' })
const statusTambah = reactive({ teks: '', kelas: '' })
async function tambah() {
  try {
    terapkan(await kirim('/api/servers', { ...baru }))
    Object.assign(statusTambah, { teks: `Server ${baru.name} ditambahkan.`, kelas: 'baik' })
    Object.assign(baru, { name: '', host: '', user: 'root', port: '', notes: '' })
  } catch (e) { Object.assign(statusTambah, { teks: pesan(e.message), kelas: 'bahaya' }) }
}

// Edit
const edit = reactive({ buka: false, index: -1, name: '', host: '', user: '', port: '', notes: '', galat: '' })
function bukaEdit(i) {
  const s = servers.value[i]
  Object.assign(edit, { buka: true, index: i, name: s.name, host: s.host, user: s.user, port: s.port, notes: s.notes || '', galat: '' })
}
async function simpanEdit() {
  const lama = servers.value[edit.index]
  const data = { index: edit.index, name: edit.name, host: edit.host, user: edit.user, port: edit.port, notes: edit.notes }
  if (lama && lama.domains && lama.host !== String(edit.host).trim()) {
    if (!(await konfirmasi({ judul: 'Ganti host?', teks: `Host ${lama.host} dipakai ${lama.domains} manifest situs. Manifest itu tetap menunjuk host lama. Tetap ganti?`, tombol: 'Tetap ganti', kelas: 'waspada' }))) return
    data.pindah_host = true
  }
  try {
    terapkan(await kirim('/api/servers', data))
    delete hasilTes[edit.index]
    edit.buka = false
    beriStatus(`Server ${data.name} disimpan.`)
  } catch (e) { edit.galat = pesan(e.message) }
}

// Kontrol daya Local PC
const AKSI = {
  shutdown: {
    judul: 'Shutdown server?', teks: 'Semua layanan kantor akan berhenti. Server perlu dinyalakan kembali secara fisik.',
    tombol: 'Ya, shutdown', url: '/api/shutdown', header: { 'X-Shutdown-Confirm': 'shutdown' },
    kirim: 'Mengirim perintah shutdown…', sukses: 'Shutdown dijadwalkan. Koneksi akan terputus.', gagal: 'Shutdown gagal.', kelas: 'bahaya',
  },
  restart: {
    judul: 'Restart server?', teks: 'Semua layanan terputus sementara (±1–3 menit) lalu kembali online otomatis. Pastikan tidak ada install yang sedang berjalan.',
    tombol: 'Ya, restart', url: '/api/restart', header: { 'X-Restart-Confirm': 'restart' },
    kirim: 'Mengirim perintah restart…', sukses: 'Restart dijadwalkan. Server kembali online ±1–3 menit.', gagal: 'Restart gagal.', kelas: 'waspada',
  },
}
const daya = reactive({ jenis: null, status: '', proses: false })
const bukaDaya = (jenis) => Object.assign(daya, { jenis, status: '', proses: false })
const tutupDaya = () => { if (!daya.proses) daya.jenis = null }
async function jalankanDaya() {
  const a = AKSI[daya.jenis]
  daya.proses = true
  daya.status = a.kirim
  try {
    const r = await fetch(a.url, { method: 'POST', headers: a.header })
    if (!r.ok) throw new Error(r.status)
    daya.status = a.sukses
  } catch {
    daya.status = a.gagal
    daya.proses = false
  }
}
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Server</h1>
        <p class="redup">Server hosting tujuan installer dan PC kantor (PC Lokal, PC Backup): kapasitas disk, pemakaian resource, dan kontrol daya Local PC.</p>
      </div>
    </header>

    <section class="kartu" aria-labelledby="judul-ringkas">
      <div class="kartu-judul">
        <h2 id="judul-ringkas">Kapasitas server hosting</h2>
        <span class="redup">
          <template v-if="resource.data.value?.diambil">Diperbarui {{ waktuLalu(resource.data.value.diambil) }} · </template>
          <button type="button" class="tombol garis kecil" :disabled="segarkan" @click="muatSegar">{{ segarkan ? 'Mengambil…' : 'Segarkan' }}</button>
        </span>
      </div>
      <p v-if="resource.memuat.value" class="redup">Mengambil data dari server lewat SSH…</p>
      <p v-else-if="resource.galat.value" class="pesan-status bahaya">Gagal mengambil resource: {{ resource.galat.value.message }}</p>
      <div v-else class="ringkas">
        <div class="tile">
          <span class="redup">Disk terpakai</span>
          <strong>{{ ringkasan.persen }}%</strong>
          <div class="meter" :class="tingkat(ringkasan.persen)" role="meter" :aria-valuenow="ringkasan.persen" aria-valuemin="0" aria-valuemax="100" aria-label="Disk terpakai semua server"><i :style="{ width: `${ringkasan.persen}%` }" /></div>
          <small class="redup">{{ ukuranBerkas(ringkasan.pakai) }} dari {{ ukuranBerkas(ringkasan.total) }}</small>
        </div>
        <div class="tile"><span class="redup">Sisa disk</span><strong>{{ ukuranBerkas(ringkasan.sisa) }}</strong><small class="redup">gabungan server hosting</small></div>
        <div class="tile"><span class="redup">Total CPU · RAM</span><strong>{{ ringkasan.core }} core</strong><small class="redup">RAM {{ ukuranBerkas(ringkasan.ram) }}</small></div>
        <div class="tile"><span class="redup">Server tersambung</span><strong :class="{ 'teks-bahaya': ringkasan.online < ringkasan.jumlah }">{{ ringkasan.online }} / {{ ringkasan.jumlah }}</strong><small class="redup">cek SSH tiap 1 menit</small></div>
      </div>
    </section>

    <section class="kartu" aria-labelledby="judul-daftar">
      <div class="kartu-judul">
        <h2 id="judul-daftar">Server terdaftar</h2>
        <span class="redup">{{ simpanan }}</span>
      </div>
      <p class="redup">Server <b>default</b> (urutan pertama) jadi tujuan manifest baru. Jumlah situs dihitung dari target_host manifest; server yang masih dipakai tidak bisa dihapus.
        Mesin bertag <span class="lencana ungu">PC Lokal</span> / <span class="lencana teal">PC Backup</span> hanya dipantau (Monitoring & Proteksi), bukan tujuan installer; datanya di <code>{{ simpananPc || 'servers-monitor.json' }}</code>.</p>
      <p v-if="memuat" class="redup">Memuat server…</p>
      <p v-else-if="galatMuat" class="pesan-status bahaya">Gagal memuat server: {{ galatMuat }}</p>
      <p v-else-if="!daftar.length" class="redup">Belum ada server. Tambahkan lewat formulir di bawah.</p>
      <div v-else class="daftar-server">
        <article v-for="s in daftar" :key="s.kunci" class="server-item" :class="{ utama: s.default }">
          <div class="info">
            <div class="nama">
              <b>{{ s.name }}</b>
              <span class="lencana" :class="jenisServer(s.jenis).kelas" :title="jenisServer(s.jenis).ket">{{ jenisServer(s.jenis).label }}</span>
              <span v-if="s.default" class="lencana biru" title="Tujuan manifest baru">DEFAULT</span>
              <span v-if="s.domains" class="lencana abu" title="Manifest situs yang memakai server ini">{{ s.domains }} situs</span>
            </div>
            <code class="alamat">{{ s.jenis === 'lokal' ? 'mesin ini (tanpa SSH)' : `${s.user}@${s.host}:${s.port}` }}</code>
            <p v-if="s.notes" class="redup catatan">{{ s.notes }}</p>
            <template v-if="resPerHost[s.host]">
              <p v-if="!resPerHost[s.host].ok" class="pesan-status bahaya">✗ Resource tidak terbaca: {{ resPerHost[s.host].error }}</p>
              <div v-else class="resource">
                <div v-for="d in resPerHost[s.host].disks" :key="d.mount" class="res">
                  <div class="res-kepala"><span>Disk {{ d.mount }}</span><b>{{ d.persen }}%</b></div>
                  <div class="meter" :class="tingkat(d.persen)" role="meter" :aria-valuenow="d.persen" aria-valuemin="0" aria-valuemax="100" :aria-label="`Disk ${d.mount} ${s.name}`"><i :style="{ width: `${d.persen}%` }" /></div>
                  <small class="redup">Sisa {{ ukuranBerkas(d.free) }} dari {{ ukuranBerkas(d.total) }}</small>
                </div>
                <div class="res">
                  <div class="res-kepala"><span>CPU</span><b>{{ resPerHost[s.host].cpu }}%</b></div>
                  <div class="meter" :class="tingkat(resPerHost[s.host].cpu)" role="meter" :aria-valuenow="resPerHost[s.host].cpu" aria-valuemin="0" aria-valuemax="100" :aria-label="`CPU ${s.name}`"><i :style="{ width: `${resPerHost[s.host].cpu}%` }" /></div>
                  <small class="redup">{{ resPerHost[s.host].cpu_core }} core · load {{ resPerHost[s.host].load?.map((v) => v.toFixed(2)).join(' · ') }}</small>
                </div>
                <div v-if="resPerHost[s.host].ram" class="res">
                  <div class="res-kepala"><span>RAM</span><b>{{ resPerHost[s.host].ram.persen }}%</b></div>
                  <div class="meter" :class="tingkat(resPerHost[s.host].ram.persen)" role="meter" :aria-valuenow="resPerHost[s.host].ram.persen" aria-valuemin="0" aria-valuemax="100" :aria-label="`RAM ${s.name}`"><i :style="{ width: `${resPerHost[s.host].ram.persen}%` }" /></div>
                  <small class="redup">{{ ukuranBerkas(resPerHost[s.host].ram.used) }} dari {{ ukuranBerkas(resPerHost[s.host].ram.total) }}</small>
                </div>
                <div v-if="resPerHost[s.host].swap" class="res">
                  <div class="res-kepala"><span>Swap</span><b>{{ resPerHost[s.host].swap.persen }}%</b></div>
                  <div class="meter" :class="tingkat(resPerHost[s.host].swap.persen)" role="meter" :aria-valuenow="resPerHost[s.host].swap.persen" aria-valuemin="0" aria-valuemax="100" :aria-label="`Swap ${s.name}`"><i :style="{ width: `${resPerHost[s.host].swap.persen}%` }" /></div>
                  <small class="redup">{{ ukuranBerkas(resPerHost[s.host].swap.used) }} dari {{ ukuranBerkas(resPerHost[s.host].swap.total) }} · nyala {{ lamaNyala(resPerHost[s.host].uptime) }}</small>
                </div>
                <div v-else class="res">
                  <div class="res-kepala"><span>Uptime</span><b>{{ lamaNyala(resPerHost[s.host].uptime) }}</b></div>
                  <small class="redup">tanpa swap</small>
                </div>
              </div>
            </template>
            <p v-if="hasilTes[s.kunci] === 'jalan'" class="pesan-status">Tes {{ s.jenis === 'lokal' ? 'koneksi' : 'SSH' }} berjalan…</p>
            <p v-else-if="hasilTes[s.kunci]" class="pesan-status" :class="hasilTes[s.kunci].ok ? 'baik' : 'bahaya'">
              <template v-if="hasilTes[s.kunci].ok">✓ {{ s.jenis === 'lokal' ? 'Terbaca' : 'SSH tersambung' }} · {{ hasilTes[s.kunci].hostname }}<template v-if="s.jenis === 'hosting'"> · DirectAdmin {{ hasilTes[s.kunci].directadmin ? 'ada' : 'tidak ada' }}</template> · {{ hasilTes[s.kunci].ms }} ms</template>
              <template v-else>✗ SSH gagal: {{ hasilTes[s.kunci].error }}</template>
            </p>
          </div>
          <div class="aksi">
            <button type="button" class="tombol garis kecil" :disabled="hasilTes[s.kunci] === 'jalan'" @click="tesSsh(s)">{{ s.jenis === 'lokal' ? 'Tes' : 'Tes SSH' }}</button>
            <template v-if="!hanyaBaca && s.jenis === 'hosting'">
              <button type="button" class="tombol garis kecil" @click="bukaEdit(s.i)">Edit</button>
              <button v-if="!s.default" type="button" class="tombol garis kecil" @click="jadikanDefault(s.i)">Jadikan default</button>
              <button v-if="!s.domains && servers.length > 1" type="button" class="tombol bahaya kecil" @click="hapus(s.i)">Hapus</button>
            </template>
          </div>
        </article>
      </div>
      <p v-if="statusDaftar.teks" class="pesan-status" :class="statusDaftar.kelas" role="status">{{ statusDaftar.teks }}</p>
    </section>

    <section class="kartu" aria-labelledby="judul-tambah">
      <div class="kartu-judul"><h2 id="judul-tambah">Tambah server hosting</h2></div>
      <form class="formulir" @submit.prevent="tambah">
        <label class="isian"><span>Nama server</span><input v-model="baru.name" required maxlength="80" placeholder="mis. Farnaz" :disabled="hanyaBaca"></label>
        <label class="isian"><span>Host / IP</span><input v-model="baru.host" required maxlength="253" placeholder="103.x.x.x atau hostname" :disabled="hanyaBaca"></label>
        <label class="isian"><span>Username SSH</span><input v-model="baru.user" required maxlength="32" :disabled="hanyaBaca"></label>
        <label class="isian"><span>Port SSH</span><input v-model="baru.port" type="number" min="1" max="65535" required placeholder="mis. 53864" :disabled="hanyaBaca"></label>
        <label class="isian lebar"><span>Catatan</span><textarea v-model="baru.notes" maxlength="500" placeholder="Hostname panel, fungsi server, atau batasan akses" :disabled="hanyaBaca" /></label>
        <div class="lebar kanan">
          <button type="submit" class="tombol" :disabled="hanyaBaca">Tambah server</button>
        </div>
      </form>
      <p v-if="statusTambah.teks" class="pesan-status" :class="statusTambah.kelas" role="status">{{ statusTambah.teks }}</p>
    </section>

    <section class="kartu" aria-labelledby="judul-daya">
      <div class="kartu-judul"><h2 id="judul-daya">Kontrol daya Local PC</h2></div>
      <p class="redup">Dipakai hanya bila perlu. Setiap tombol meminta konfirmasi dulu.</p>
      <div class="aksi-daya">
        <button type="button" class="tombol waspada" @click="bukaDaya('restart')"><Ikon nama="ulang" :ukuran="18" /> Restart server</button>
        <button type="button" class="tombol bahaya" @click="bukaDaya('shutdown')"><Ikon nama="daya" :ukuran="18" /> Shutdown server</button>
      </div>
    </section>

    <Dialog :buka="edit.buka" :judul="`Edit server: ${servers[edit.index]?.name || ''}`" lebar="560px" @tutup="edit.buka = false">
      <form class="formulir" @submit.prevent="simpanEdit">
        <label class="isian"><span>Nama server</span><input v-model="edit.name" required maxlength="80" autofocus></label>
        <label class="isian"><span>Host / IP</span><input v-model="edit.host" required maxlength="253"></label>
        <label class="isian"><span>Username SSH</span><input v-model="edit.user" required maxlength="32"></label>
        <label class="isian"><span>Port SSH</span><input v-model="edit.port" type="number" min="1" max="65535" required></label>
        <label class="isian lebar"><span>Catatan</span><textarea v-model="edit.notes" maxlength="500" /></label>
        <p v-if="edit.galat" class="pesan-status bahaya lebar" role="alert">{{ edit.galat }}</p>
        <div class="aksi-dialog lebar">
          <button type="button" class="tombol garis" @click="edit.buka = false">Batal</button>
          <button type="submit" class="tombol">Simpan</button>
        </div>
      </form>
    </Dialog>

    <Dialog :buka="!!daya.jenis" :judul="daya.jenis ? AKSI[daya.jenis].judul : ''" :kelas="daya.jenis ? AKSI[daya.jenis].kelas : ''" @tutup="tutupDaya">
      <template v-if="daya.jenis">
        <p class="redup">{{ AKSI[daya.jenis].teks }}</p>
        <div class="aksi-dialog">
          <button type="button" class="tombol garis" autofocus :disabled="daya.proses" @click="tutupDaya">Batal</button>
          <button type="button" class="tombol" :class="AKSI[daya.jenis].kelas" :disabled="daya.proses" @click="jalankanDaya">{{ AKSI[daya.jenis].tombol }}</button>
        </div>
        <p class="pesan-status" aria-live="polite">{{ daya.status }}</p>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; max-width: 1000px; }
.daftar-server { display: grid; gap: 10px; margin-top: 12px; }
.server-item { display: flex; justify-content: space-between; gap: 14px; flex-wrap: wrap; padding: 14px 16px; border-radius: 12px; background: var(--kartu-2); border: 1px solid transparent; }
.server-item.utama { border-color: rgba(91, 140, 255, .45); }
.info { min-width: 0; flex: 1 1 280px; }
.nama { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 15px; }
.alamat { display: inline-block; margin-top: 4px; font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks-2); overflow-wrap: anywhere; }
.catatan { margin: 4px 0 0; }
.aksi { display: flex; align-items: flex-start; gap: 8px; flex-wrap: wrap; }
.formulir { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-content: start; }
.formulir .lebar { grid-column: 1 / -1; }
.kanan { display: flex; justify-content: flex-end; }
.ringkas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
.tile { display: grid; gap: 6px; align-content: start; padding: 14px 16px; border-radius: 12px; background: var(--kartu-2); }
.tile strong { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
.tile .meter, .resource .meter { background: var(--kartu); }
.teks-bahaya { color: var(--bahaya); }
.resource { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px 16px; margin-top: 12px; }
.res { display: grid; gap: 5px; align-content: start; }
.res-kepala { display: flex; justify-content: space-between; gap: 8px; font-size: 13px; }
.res-kepala b { font-variant-numeric: tabular-nums; }
.res small { font-size: 12px; }
.meter.waspada i { background: var(--waspada); }
.meter.bahaya i { background: var(--bahaya); }
.aksi-daya { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
@media (max-width: 800px) { .ringkas { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px) { .formulir { grid-template-columns: minmax(0, 1fr); } }
</style>
