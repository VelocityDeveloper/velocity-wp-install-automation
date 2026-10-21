<script setup>
// VelocityGuard (grup menu VelocityGuard): bagian "selalu membaik" sistem keamanan pengganti cPGuard.
// - Celah harian: GET /api/servers/guard/celah[?tanggal=] (laporan 07:00 WIB, agen hanya baca), POST .../celah/scan (buat sekarang).
// - Virtual patch: kerentanan CMS tanpa login yang bisa ditahan WAF (bagian `cve` laporan yang sama).
// - Insiden: GET/POST /api/servers/guard/insiden — tiap problem dicatat bersama penyebab, perbaikan, dan aturan terkait.
import { ref, reactive, computed, watch } from 'vue'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import PelakuAkun from '../components/PelakuAkun.vue'
import { namaAkun } from '../akun.js'
import { konfirmasi } from '../konfirmasi.js'
import { kirim, pakaiPolling, tanggalWaktu, angka } from '../api.js'
import { tabUrl } from '../laravel.js'

const TAB = ['celah', 'patch', 'insiden']
const tab = tabUrl('tab', 'celah', { boleh: TAB })
const tanggal = tabUrl('tanggal', '')
const celah = pakaiPolling(() => `/api/servers/guard/celah${tanggal.value ? `?tanggal=${tanggal.value}` : ''}`, 0)
const ins = pakaiPolling('/api/servers/guard/insiden', 0)
watch(tanggal, () => celah.muatUlang())
const lap = computed(() => celah.data.value?.laporan || null)
const berjalan = computed(() => (celah.data.value?.job || []).length > 0)

const PESAN = {
  invalid_oleh: 'Masuk dulu lewat tombol "Masuk dengan VD.net" di kanan atas — setiap aksi dicatat atas nama akun Anda.',
  laporan_sedang_jalan: 'Laporan sedang dibuat. Tunggu sampai selesai.',
  judul_dan_tanggal_wajib: 'Judul dan tanggal wajib diisi.',
  forbidden: 'Ditolak: hanya bisa dijalankan dari halaman dashboard ini.',
}
const pesan = reactive({ teks: '', galat: false })
const lapor = (teks, galat = false) => Object.assign(pesan, { teks: PESAN[teks] || teks, galat })

const TINGKAT = { tinggi: ['merah', 'Tinggi'], sedang: ['kuning', 'Sedang'], info: ['abu', 'Info'], kritis: ['merah', 'Kritis'] }
const JENIS = {
  probe_lolos: 'Probe lolos', post_php: 'POST ke PHP', pemindai: 'Pemindai', bot_baru: 'Bot baru', php_baru: 'PHP baru', uji: 'Uji tanpa cPGuard',
}

async function buatSekarang() {
  if (!await konfirmasi({ judul: 'Buat laporan celah sekarang?', teks: 'Membaca log 24 jam di server uji lewat SSH (hanya baca, ±1–3 menit per server).', tombol: 'Buat' })) return
  try {
    await kirim('/api/servers/guard/celah/scan', { oleh: namaAkun.value })
    lapor('Laporan sedang dibuat… halaman dimuat ulang otomatis.')
    const t = setInterval(async () => { await celah.muatUlang(); if (!berjalan.value) { clearInterval(t); lapor('Laporan selesai.') } }, 10000)
  } catch (e) { lapor(e.message, true) }
}

const buka = ref({})
const alih = (k) => { buka.value = { ...buka.value, [k]: !buka.value[k] } }
const ringkasDetail = (d) => d.uri || d.path || d.ua || d.baris || ''
const metaDetail = (d) => [d.t && tanggalWaktu(d.t), d.ip, d.kode && `HTTP ${d.kode}`, d.ukuran && `${d.ukuran} B`].filter(Boolean).join(' · ')

// ---- Virtual patch ----
const cve = computed(() => lap.value?.cve || [])

// ---- Insiden ----
const STATUS = { terbuka: ['merah', 'Terbuka'], dipantau: ['kuning', 'Dipantau'], selesai: ['hijau', 'Selesai'] }
const daftarInsiden = computed(() => ins.data.value?.insiden || [])
const cari = ref('')
const tersaring = computed(() => {
  const k = cari.value.toLowerCase().trim()
  return k ? daftarInsiden.value.filter((x) => JSON.stringify(x).toLowerCase().includes(k)) : daftarInsiden.value
})
const kosong = () => ({ id: '', tanggal: new Date().toLocaleDateString('sv-SE'), judul: '', server: '', status: 'terbuka', penyebab: '', perbaikan: '', aturan: '' })
const form = reactive({ buka: false, data: kosong(), proses: false })
const ubah = (x) => Object.assign(form, { buka: true, data: x ? { ...kosong(), ...x } : kosong() })
function dariTemuan(s, x) {
  ubah({ ...kosong(), judul: x.judul, server: s.server, penyebab: `Laporan celah ${lap.value.tanggal}: ${JENIS[x.jenis] || x.jenis}`, perbaikan: x.usulan })
  tab.value = 'insiden'
}
async function simpan() {
  form.proses = true
  try {
    await kirim('/api/servers/guard/insiden', { ...form.data, oleh: namaAkun.value })
    form.buka = false
    lapor('Insiden tersimpan.')
    ins.muatUlang()
  } catch (e) { lapor(e.message, true) } finally { form.proses = false }
}
async function hapus(x) {
  if (!await konfirmasi({ judul: 'Hapus catatan insiden?', teks: x.judul, tombol: 'Hapus', kelas: 'bahaya' })) return
  try { await kirim('/api/servers/guard/insiden', { id: x.id, hapus: true, oleh: namaAkun.value }); ins.muatUlang() } catch (e) { lapor(e.message, true) }
}
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>VelocityGuard</h1>
        <p class="redup">Sistem keamanan server pengganti cPGuard yang terus diperbaiki: celah yang lolos tiap hari, kandidat virtual patch WAF, dan catatan setiap insiden beserta perbaikannya.</p>
      </div>
      <div class="kepala-aksi">
        <div class="nama-saya"><span class="redup">Dicatat sebagai</span><PelakuAkun id="nama-guard" /></div>
      </div>
    </header>

    <div class="tab" role="tablist" aria-label="Bagian VelocityGuard">
      <button v-for="t in [
        { k: 'celah', label: 'Celah harian' },
        { k: 'patch', label: 'Virtual patch', n: cve.filter((c) => c.baru).length },
        { k: 'insiden', label: 'Insiden', n: daftarInsiden.filter((x) => x.status !== 'selesai').length },
      ]" :key="t.k" type="button" role="tab" :aria-selected="tab === t.k" :class="{ aktif: tab === t.k }" @click="tab = t.k">
        {{ t.label }}<span v-if="t.n" class="hitung"> {{ t.n }}</span>
      </button>
    </div>
    <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>

    <!-- Celah harian -->
    <section v-if="tab === 'celah'" class="kartu" aria-labelledby="judul-celah">
      <div class="kartu-judul">
        <h2 id="judul-celah"><Ikon nama="perisai" :ukuran="16" /> Celah yang lolos{{ lap ? ` · ${lap.tanggal}` : '' }}</h2>
        <div class="aksi-baris">
          <label v-if="celah.data.value?.tanggal?.length" class="pilih-tgl"><span class="sr">Tanggal laporan</span>
            <select :value="lap?.tanggal" @change="tanggal = $event.target.value">
              <option v-for="t in celah.data.value.tanggal" :key="t" :value="t">{{ t }}</option>
            </select>
          </label>
          <button type="button" class="tombol kecil" :disabled="berjalan" @click="buatSekarang"><Ikon nama="ulang" :ukuran="16" /> {{ berjalan ? 'Membuat…' : 'Buat sekarang' }}</button>
        </div>
      </div>
      <p v-if="celah.memuat.value && !celah.data.value" class="redup">Memuat…</p>
      <p v-else-if="!lap" class="redup">Belum ada laporan. Laporan otomatis dibuat tiap hari pukul 07:00 WIB, atau klik "Buat sekarang".</p>
      <template v-else>
        <p class="redup kecil-teks">Dibuat {{ tanggalWaktu(lap.dibuat) }} oleh {{ lap.oleh }}. Agen hanya membaca log akses 24 jam; usulan dikerjakan manual lalu dicatat di Insiden.</p>
        <div v-for="s in lap.server" :key="s.host" class="server-blok">
          <h3 class="sub-judul">{{ s.server }}
            <span class="redup">{{ s.ok ? `${angka(s.request)} request · ${s.temuan.length} temuan · ${s.detik} dtk` : `gagal: ${s.error}` }}</span>
            <span v-if="s.cpguard_waf_off" class="lencana teal">tanpa cPGuard</span>
          </h3>
          <p v-if="s.ok && !s.temuan.length" class="bersih"><Ikon nama="centang" :ukuran="16" /> Tidak ada celah yang lolos.</p>
          <ul class="temuan">
            <li v-for="(x, i) in s.temuan" :key="i">
              <div class="temuan-kepala">
                <span class="lencana" :class="TINGKAT[x.tingkat][0]">{{ TINGKAT[x.tingkat][1] }}</span>
                <span class="lencana abu">{{ JENIS[x.jenis] || x.jenis }}</span>
                <b class="putus">{{ x.judul }}</b>
              </div>
              <p class="usulan"><Ikon nama="peringatan" :ukuran="14" /> {{ x.usulan }}</p>
              <div class="temuan-aksi">
                <button type="button" class="tombol kecil garis" :aria-expanded="!!buka[`${s.host}${i}`]" @click="alih(`${s.host}${i}`)">{{ buka[`${s.host}${i}`] ? 'Tutup' : `Rincian (${x.detail.length})` }}</button>
                <button type="button" class="tombol kecil garis" @click="dariTemuan(s, x)">Catat sebagai insiden</button>
              </div>
              <ul v-if="buka[`${s.host}${i}`]" class="rincian">
                <li v-for="(d, j) in x.detail" :key="j"><code class="putus">{{ ringkasDetail(d) }}</code> <small class="redup">{{ metaDetail(d) }}</small><small v-if="d.ua && d.uri" class="redup blok putus">{{ d.ua }}</small></li>
              </ul>
            </li>
          </ul>
        </div>
      </template>
    </section>

    <!-- Virtual patch -->
    <section v-if="tab === 'patch'" class="kartu" aria-labelledby="judul-patch">
      <div class="kartu-judul"><h2 id="judul-patch"><Ikon nama="waf" :ukuran="16" /> Kandidat virtual patch WAF</h2></div>
      <p class="redup kecil-teks">Kerentanan kritis/tinggi yang bisa dieksploitasi <b>tanpa login</b> dan jenisnya bisa ditahan WAF (RCE, SQLi, upload, LFI, eskalasi hak…), dari scan CMS terakhir server uji. Pertama: perbarui plugin. Bila tak bisa massal, buat aturan WAF yang menutup endpoint/parameter rentan.</p>
      <p v-if="!cve.length" class="redup">Tidak ada kandidat (atau laporan belum dibuat).</p>
      <div v-else class="tabel-wadah">
        <table class="tabel">
          <thead><tr><th scope="col">Komponen</th><th scope="col">Kerentanan</th><th scope="col">Situs</th><th scope="col">Server</th><th scope="col">Perbaikan</th></tr></thead>
          <tbody>
            <tr v-for="c in cve" :key="c.kunci">
              <td><b>{{ c.slug }}</b> <span v-if="c.baru" class="lencana biru">Baru</span></td>
              <td><span class="lencana" :class="TINGKAT[c.tingkat]?.[0]">{{ TINGKAT[c.tingkat]?.[1] }}</span> <a v-if="c.link" :href="c.link" target="_blank" rel="noopener">{{ c.judul }}</a><template v-else>{{ c.judul }}</template></td>
              <td>{{ angka(c.situs) }}</td>
              <td>{{ c.server.join(', ') }}</td>
              <td>{{ c.perbaiki ? `versi ${c.perbaiki}` : 'belum ada' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Insiden -->
    <section v-if="tab === 'insiden'" class="kartu" aria-labelledby="judul-insiden">
      <div class="kartu-judul">
        <h2 id="judul-insiden"><Ikon nama="dokumen" :ukuran="16" /> Catatan insiden</h2>
        <div class="aksi-baris">
          <input v-model="cari" type="search" placeholder="Cari insiden / aturan" aria-label="Cari insiden">
          <button type="button" class="tombol kecil" @click="ubah()"><Ikon nama="tambah" :ukuran="16" /> Tambah</button>
        </div>
      </div>
      <p v-if="!tersaring.length" class="redup">Belum ada catatan.</p>
      <ul class="temuan">
        <li v-for="x in tersaring" :key="x.id">
          <div class="temuan-kepala">
            <span class="lencana" :class="STATUS[x.status]?.[0]">{{ STATUS[x.status]?.[1] }}</span>
            <span class="redup">{{ x.tanggal }}{{ x.server ? ` · ${x.server}` : '' }}</span>
            <b class="putus">{{ x.judul }}</b>
          </div>
          <dl class="isi-insiden">
            <template v-if="x.penyebab"><dt>Penyebab</dt><dd>{{ x.penyebab }}</dd></template>
            <template v-if="x.perbaikan"><dt>Perbaikan</dt><dd>{{ x.perbaikan }}</dd></template>
            <template v-if="x.aturan"><dt>Aturan</dt><dd><code class="putus">{{ x.aturan }}</code></dd></template>
          </dl>
          <div class="temuan-aksi">
            <small class="redup">{{ x.oleh }} · {{ tanggalWaktu(x.diubah) }}</small>
            <button type="button" class="tombol kecil garis" @click="ubah(x)">Ubah</button>
            <button type="button" class="tombol kecil bahaya" @click="hapus(x)">Hapus</button>
          </div>
        </li>
      </ul>
    </section>

    <Dialog :buka="form.buka" :judul="form.data.id ? 'Ubah insiden' : 'Catat insiden'" lebar="640px" @tutup="form.buka = false">
      <form class="form-insiden" @submit.prevent="simpan">
        <label class="isian"><span>Judul</span><input v-model="form.data.judul" required maxlength="200" autofocus></label>
        <div class="dua">
          <label class="isian"><span>Tanggal</span><input v-model="form.data.tanggal" type="date" required></label>
          <label class="isian"><span>Server</span><input v-model="form.data.server" maxlength="60" placeholder="Wulan, Farnaz, semua…"></label>
          <label class="isian"><span>Status</span>
            <select v-model="form.data.status"><option v-for="(v, k) in STATUS" :key="k" :value="k">{{ v[1] }}</option></select>
          </label>
        </div>
        <label class="isian"><span>Penyebab</span><textarea v-model="form.data.penyebab" rows="3" /></label>
        <label class="isian"><span>Perbaikan</span><textarea v-model="form.data.perbaikan" rows="3" /></label>
        <label class="isian"><span>Aturan VelocityGuard terkait</span><input v-model="form.data.aturan" placeholder="mis. WAF 7700213, BFM berat, VD.SEO.Cloaking"></label>
        <div class="temuan-aksi">
          <button type="button" class="tombol kecil garis" @click="form.buka = false">Batal</button>
          <button type="submit" class="tombol kecil" :disabled="form.proses">{{ form.proses ? 'Menyimpan…' : 'Simpan' }}</button>
        </div>
      </form>
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; justify-self: start; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
.aksi-baris { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.server-blok + .server-blok { margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--garis); }
.sub-judul { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; font-size: 14px; margin: 0 0 10px; }
.sub-judul .redup { font-weight: 400; font-size: 12px; }
.temuan { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.temuan > li { border: 1px solid var(--garis); border-radius: 10px; padding: 10px 12px; display: grid; gap: 6px; min-width: 0; }
.temuan-kepala { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.temuan-aksi { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.temuan-aksi small { margin-right: auto; }
.usulan { margin: 0; font-size: 13px; color: var(--teks-2); display: flex; gap: 6px; align-items: flex-start; }
.rincian { margin: 0; padding-left: 18px; display: grid; gap: 4px; font-size: 12px; }
.putus { overflow-wrap: anywhere; word-break: break-word; }
.blok { display: block; }
.bersih { color: var(--baik); display: flex; gap: 6px; align-items: center; margin: 0; }
.kecil-teks { font-size: 12px; }
.lencana.teal { color: var(--teal); background: color-mix(in srgb, var(--teal) 14%, transparent); }
.isi-insiden { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 12px; margin: 0; font-size: 13px; }
.isi-insiden dt { color: var(--teks-3); }
.isi-insiden dd { margin: 0; white-space: pre-line; overflow-wrap: anywhere; }
.form-insiden { display: grid; gap: 12px; }
.form-insiden .dua { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
@media (max-width: 640px) {
  .form-insiden .dua { grid-template-columns: minmax(0, 1fr); }
  .isi-insiden { grid-template-columns: minmax(0, 1fr); }
}
</style>
