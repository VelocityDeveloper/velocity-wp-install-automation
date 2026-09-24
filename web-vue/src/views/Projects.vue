<script setup>
// Project yang berjalan di Local PC (klien & internal). Identitas dari config/local-projects.json,
// status layanan systemd / HTTP / git diperiksa server_stats.py (GET /api/projects, cache 10 dtk).
import { ref, computed, reactive } from 'vue'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import { pakaiPolling, ukuranBerkas, waktuLalu, tanggalWaktu, kirim } from '../api.js'

const { data, galat, memuat, muatUlang } = pakaiPolling('/api/projects', 15000)
const projects = computed(() => data.value?.projects || [])

const SARING = [
  { nilai: 'klien', label: 'Klien' },
  { nilai: 'internal', label: 'Internal' },
  { nilai: 'semua', label: 'Semua' },
]
const saring = ref('klien')
const tampil = computed(() => projects.value.filter((p) => saring.value === 'semua' || p.jenis === saring.value))
const jumlah = (jenis) => projects.value.filter((p) => jenis === 'semua' || p.jenis === jenis).length

const httpHidup = (h) => !!h && h.kode >= 200 && h.kode < 400
function kondisi(p) {
  const aktif = p.layanan.filter((l) => l.aktif).length
  if (!aktif && (!p.http || !httpHidup(p.http))) return { kelas: 'bahaya', teks: 'Mati' }
  if (aktif < p.layanan.length || (p.http && !httpHidup(p.http))) return { kelas: 'waspada', teks: 'Bermasalah' }
  return { kelas: 'baik', teks: 'Berjalan' }
}
const ringkas = computed(() => {
  const klien = projects.value.filter((p) => p.jenis === 'klien')
  return { klien: klien.length, klienJalan: klien.filter((p) => kondisi(p).kelas === 'baik').length, total: projects.value.length }
})

// Tautan ikut host yang sedang dibuka (LAN atau Tailscale); port dev hanya http.
const alamatBuka = (p) => p.url || `http://${location.hostname}:${p.port}/`
const labelBuka = (p) => p.url ? p.url : `${location.hostname}:${p.port}`
const totalMemori = (p) => p.layanan.reduce((n, l) => n + (l.memori || 0), 0)
const sejak = (p) => Math.min(...p.layanan.map((l) => l.sejak || Infinity))

// Akun uji: disimpan di /etc/velocity/secrets/local-projects-login.json (bukan repo), sunting lewat dialog.
const alamatLogin = (p) => {
  const dasar = alamatBuka(p)
  const path = p.login?.path || ''
  return path ? dasar.replace(/\/$/, '') + path : dasar
}
const tersalin = ref('')
async function salin(teks, kunci) {
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
  tersalin.value = kunci
  setTimeout(() => { if (tersalin.value === kunci) tersalin.value = '' }, 1500)
}

const PESAN = {
  forbidden: 'Hanya bisa disimpan dari jaringan kantor atau Tailscale.',
  project_tidak_dikenal: 'Project tidak ada di config/local-projects.json.',
  path_harus_diawali_garis_miring: 'Path login harus diawali "/", mis. /login.',
  akun_terlalu_banyak: 'Maksimal 20 akun per project.',
}
const edit = reactive({ buka: false, id: '', nama: '', path: '', akun: [], galat: '', proses: false })
function bukaEdit(p) {
  Object.assign(edit, {
    buka: true, id: p.id, nama: p.nama, path: p.login?.path || '', galat: '', proses: false,
    akun: (p.login?.akun?.length ? p.login.akun : [{ peran: 'Admin', user: '', sandi: '' }]).map((a) => ({ ...a })),
  })
}
async function simpanEdit() {
  edit.proses = true
  try {
    const r = await kirim('/api/projects/login', { id: edit.id, path: edit.path, akun: edit.akun })
    const p = projects.value.find((x) => x.id === edit.id)
    if (p) p.login = r.login
    edit.buka = false
  } catch (e) {
    edit.galat = PESAN[e.message] || `Gagal menyimpan: ${e.message}`
  } finally {
    edit.proses = false
  }
}
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Project Lokal</h1>
        <p class="redup">Aplikasi yang berjalan di Local PC. Status diperbarui tiap 15 detik.</p>
      </div>
      <button type="button" class="tombol garis kecil" @click="muatUlang"><Ikon nama="ulang" :ukuran="16" /> Periksa ulang</button>
    </header>

    <div class="ringkas">
      <div class="kartu angka"><span class="redup">Project klien berjalan</span><b>{{ ringkas.klienJalan }} <small>/ {{ ringkas.klien }}</small></b></div>
      <div class="kartu angka"><span class="redup">Total project</span><b>{{ ringkas.total }}</b></div>
      <div class="kartu angka"><span class="redup">Diperiksa</span><b class="kecil-b">{{ data?.diperiksa ? waktuLalu(data.diperiksa) : '-' }}</b></div>
    </div>

    <section class="kartu" aria-labelledby="judul-project">
      <div class="kartu-judul">
        <h2 id="judul-project">Daftar project</h2>
        <div class="tab" role="tablist" aria-label="Saring jenis project">
          <button v-for="s in SARING" :key="s.nilai" type="button" role="tab" :aria-selected="saring === s.nilai" :class="{ aktif: saring === s.nilai }" @click="saring = s.nilai">
            {{ s.label }} <span class="hitung">{{ jumlah(s.nilai) }}</span>
          </button>
        </div>
      </div>

      <p v-if="memuat" class="redup">Memeriksa project…</p>
      <p v-else-if="galat && !data" class="pesan-status bahaya">Gagal memuat: {{ galat.message }}</p>
      <p v-else-if="data?.error" class="pesan-status bahaya">{{ data.error }}</p>
      <p v-else-if="!tampil.length" class="redup">Tidak ada project di kategori ini.</p>

      <div v-else class="daftar">
        <article v-for="p in tampil" :key="p.id" class="project">
          <div class="baris-atas">
            <div class="nama">
              <b>{{ p.nama }}</b>
              <span class="lencana" :class="p.jenis === 'klien' ? 'biru' : 'abu'">{{ p.jenis === 'klien' ? 'KLIEN' : 'INTERNAL' }}</span>
              <span class="pil" :class="kondisi(p).kelas">{{ kondisi(p).teks }}</span>
            </div>
            <div class="tautan">
              <a class="tombol kecil" :href="alamatBuka(p)" target="_blank" rel="noopener">Buka <Ikon nama="luar" :ukuran="14" /></a>
              <a v-if="p.produksi" class="tombol garis kecil" :href="p.produksi" target="_blank" rel="noopener">Produksi <Ikon nama="luar" :ukuran="14" /></a>
            </div>
          </div>

          <dl class="rincian">
            <div><dt>Alamat</dt><dd><code>{{ labelBuka(p) }}</code>
              <span v-if="p.http" class="lencana" :class="httpHidup(p.http) ? 'hijau' : 'merah'" :title="`Cek http://127.0.0.1:${p.port}/`">HTTP {{ p.http.kode || 'gagal' }} · {{ p.http.ms }} ms</span></dd></div>
            <div><dt>Stack</dt><dd>{{ p.stack || '-' }}</dd></div>
            <div><dt>Folder</dt><dd><code>{{ p.folder }}</code></dd></div>
            <div><dt>Memori</dt><dd>{{ ukuranBerkas(totalMemori(p)) }} <span class="redup">· jalan sejak {{ isFinite(sejak(p)) ? tanggalWaktu(sejak(p)) : '-' }}</span></dd></div>
            <div v-if="p.git" class="lebar"><dt>Git</dt><dd>
              <span class="lencana abu">{{ p.git.cabang }}</span>
              <a v-if="p.git.remote?.startsWith('https://')" :href="`${p.git.remote}/commit/${p.git.commit}`" target="_blank" rel="noopener"><code>{{ p.git.commit }}</code></a>
              <code v-else>{{ p.git.commit }}</code>
              {{ p.git.pesan }} <span class="redup">· {{ waktuLalu(p.git.waktu) }}</span>
              <span v-if="p.git.berubah" class="lencana kuning" title="Berkas terlacak yang diubah tapi belum di-commit">{{ p.git.berubah }} berkas belum commit</span>
            </dd></div>
          </dl>

          <div class="login">
            <div class="login-kepala">
              <span class="login-judul"><Ikon nama="kunci" :ukuran="15" /> Login uji</span>
              <a v-if="p.login?.akun?.length" :href="alamatLogin(p)" target="_blank" rel="noopener" class="tautan-login">{{ alamatLogin(p).replace(/^https?:\/\//, '') }} <Ikon nama="luar" :ukuran="13" /></a>
              <button type="button" class="tombol garis kecil" @click="bukaEdit(p)">{{ p.login?.akun?.length ? 'Edit' : 'Isi login' }}</button>
            </div>
            <table v-if="p.login?.akun?.length" class="akun">
              <tbody>
                <tr v-for="(a, i) in p.login.akun" :key="i">
                  <th scope="row">{{ a.peran || '-' }}</th>
                  <td>
                    <button type="button" class="salin" :title="`Salin ${a.user}`" @click="salin(a.user, `${p.id}-${i}-u`)">
                      <code>{{ a.user }}</code><Ikon :nama="tersalin === `${p.id}-${i}-u` ? 'centang' : 'salin'" :ukuran="14" />
                    </button>
                  </td>
                  <td>
                    <button type="button" class="salin" title="Salin kata sandi" @click="salin(a.sandi, `${p.id}-${i}-s`)">
                      <code>{{ a.sandi }}</code><Ikon :nama="tersalin === `${p.id}-${i}-s` ? 'centang' : 'salin'" :ukuran="14" />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
            <p v-else class="redup kosong">Belum ada akun uji tersimpan.</p>
          </div>

          <ul class="layanan" aria-label="Layanan systemd">
            <li v-for="l in p.layanan" :key="l.nama" :class="l.aktif ? 'baik' : 'bahaya'" :title="l.status">
              <i aria-hidden="true" />{{ l.nama }}<span v-if="!l.aktif"> · {{ l.status }}</span>
            </li>
          </ul>
          <p v-if="p.catatan" class="redup catatan">{{ p.catatan }}</p>
        </article>
      </div>
      <p class="redup kaki">Tambah atau ubah daftar lewat <code>config/local-projects.json</code> di repo installer; tidak perlu restart.</p>
    </section>

    <Dialog :buka="edit.buka" :judul="`Login uji: ${edit.nama}`" lebar="640px" @tutup="edit.buka = false">
      <form class="form-login" @submit.prevent="simpanEdit">
        <label class="isian"><span>Path halaman login</span><input v-model="edit.path" maxlength="200" placeholder="/login"><small>Ditambahkan ke alamat project. Kosongkan bila login di halaman depan.</small></label>
        <div class="baris-akun kepala-akun" aria-hidden="true"><span>Peran</span><span>Username / email</span><span>Kata sandi</span><span /></div>
        <div v-for="(a, i) in edit.akun" :key="i" class="baris-akun">
          <input v-model="a.peran" maxlength="200" placeholder="Admin" :aria-label="`Peran akun ${i + 1}`">
          <input v-model="a.user" maxlength="200" placeholder="admin@contoh.test" :aria-label="`Username akun ${i + 1}`">
          <input v-model="a.sandi" maxlength="200" placeholder="kata sandi" :aria-label="`Kata sandi akun ${i + 1}`">
          <button type="button" class="tombol bahaya kecil" :aria-label="`Hapus akun ${i + 1}`" @click="edit.akun.splice(i, 1)"><Ikon nama="tutup" :ukuran="14" /></button>
        </div>
        <div><button type="button" class="tombol garis kecil" :disabled="edit.akun.length >= 20" @click="edit.akun.push({ peran: '', user: '', sandi: '' })">+ Tambah akun</button></div>
        <p class="redup">Disimpan di server (/etc/velocity/secrets), bukan di repo. Hanya untuk akun uji/dev, jangan akun produksi.</p>
        <p v-if="edit.galat" class="pesan-status bahaya" role="alert">{{ edit.galat }}</p>
        <div class="aksi-dialog">
          <button type="button" class="tombol garis" @click="edit.buka = false">Batal</button>
          <button type="submit" class="tombol" :disabled="edit.proses">{{ edit.proses ? 'Menyimpan…' : 'Simpan' }}</button>
        </div>
      </form>
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; max-width: 1000px; }
.ringkas { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.angka { display: grid; gap: 6px; }
.angka b { font-size: 24px; }
.angka b small { font-size: 14px; color: var(--teks-3); font-weight: 600; }
.angka .kecil-b { font-size: 16px; }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
.daftar { display: grid; gap: 12px; }
.project { padding: 16px; border-radius: 12px; background: var(--kartu-2); display: grid; gap: 12px; }
.baris-atas { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.nama { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 15.5px; }
.tautan { display: flex; gap: 8px; flex-wrap: wrap; }
.tautan .tombol { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; }
.rincian { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 18px; margin: 0; font-size: 13px; }
.rincian div { display: grid; grid-template-columns: 70px minmax(0, 1fr); gap: 8px; align-items: baseline; }
.rincian .lebar { grid-column: 1 / -1; }
.rincian dt { color: var(--teks-3); font-size: 12px; }
.rincian dd { margin: 0; color: var(--teks-2); overflow-wrap: anywhere; display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px; }
.rincian a { color: var(--aksen-terang); }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
.layanan { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px; }
.layanan li { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font: 12px ui-monospace, SFMono-Regular, Consolas, monospace; background: var(--kartu); color: var(--teks-2); }
.layanan i { width: 7px; height: 7px; border-radius: 50%; }
.layanan .baik i { background: var(--baik); }
.layanan .bahaya { color: var(--bahaya); }
.layanan .bahaya i { background: var(--bahaya); }
.catatan { margin: 0; }
.login { border: 1px solid var(--garis); border-radius: 10px; padding: 10px 12px; display: grid; gap: 8px; }
.login-kepala { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.login-judul { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600; color: var(--teks-2); }
.tautan-login { display: inline-flex; align-items: center; gap: 4px; font-size: 12.5px; color: var(--aksen-terang); margin-right: auto; overflow-wrap: anywhere; }
.login-kepala .tombol { margin-left: auto; }
.akun { justify-self: start; width: max-content; max-width: 100%; border-collapse: collapse; font-size: 13px; }
.akun th { text-align: left; font-weight: 600; color: var(--teks-3); font-size: 12px; padding: 3px 10px 3px 0; white-space: nowrap; width: 1%; }
.akun td { padding: 3px 8px 3px 0; }
.salin { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; border: 0; background: var(--kartu); color: var(--teks-3); padding: 4px 8px; border-radius: 7px; cursor: pointer; text-align: left; }
.salin code { overflow-wrap: anywhere; }
.salin:hover { color: var(--aksen-terang); }
.kosong { margin: 0; }
.form-login { display: grid; gap: 12px; }
.baris-akun { display: grid; grid-template-columns: minmax(0, .8fr) minmax(0, 1.4fr) minmax(0, 1fr) auto; gap: 8px; align-items: center; }
.kepala-akun { font-size: 12px; font-weight: 600; color: var(--teks-3); }
.kaki { margin: 14px 0 0; }
@media (max-width: 700px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
  .ringkas .angka:last-child { grid-column: 1 / -1; }
  .rincian { grid-template-columns: minmax(0, 1fr); }
  .kartu-judul { flex-wrap: wrap; }
  .akun, .akun tbody, .akun tr { display: grid; gap: 4px; }
  .akun tr { grid-template-columns: minmax(0, 1fr); padding: 4px 0; justify-items: start; }
  .akun { width: auto; }
  .akun th { grid-column: 1 / -1; width: auto; }
  .baris-akun { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .baris-akun input:first-child { grid-column: 1 / -1; }
  .kepala-akun { display: none; }
}
</style>
