<script setup>
// Kesiapan & progres migrasi Farnaz LiteSpeed -> nginx_apache (Pemantauan › Migrasi Farnaz).
// HANYA MEMBACA /brain/migrasi.json (scripts/migrasi-farnaz, timer tiap 1 menit, satu SSH baca-saja ke Farnaz).
// Eksekusi cutover tetap manual di screen Farnaz; halaman ini tidak punya tombol aksi.
import { computed } from 'vue'
import Ikon from '../components/Ikon.vue'
import { pakaiPolling, waktuLalu, tanggalWaktu, angka } from '../api.js'

const { data, galat, memuat, muatUlang } = pakaiPolling('/brain/migrasi.json', 20000)

const JAM_BASELINE = 6
const STATUS = {
  siap: { kelas: 'hijau', ikon: 'centang', label: 'Siap' },
  waspada: { kelas: 'kuning', ikon: 'peringatan', label: 'Perhatikan' },
  belum: { kelas: 'merah', ikon: 'tutup', label: 'Pemblokir' },
  info: { kelas: 'abu', ikon: 'jam', label: 'Info' },
}
const umurJam = (t) => (t ? (Date.now() / 1000 - t) / 3600 : Infinity)
const sudahPindah = computed(() => data.value?.webserver === 'nginx_apache')

// Praperiksa = syarat yang sama dengan langkah 1 cutover.sh (gagal di sana = skrip berhenti sebelum mengubah apa pun)
const cek = computed(() => {
  const d = data.value
  if (!d) return []
  const skrip = Object.entries(d.skrip || {})
  const rusak = skrip.filter(([, s]) => !s.ada || !s.sintaks).map(([n]) => n)
  const h = d.handler_htaccess
  const b = d.baseline
  const load1 = Number(d.load?.[0] || 0)
  return [
    sudahPindah.value
      ? { k: 'Webserver', s: 'info', t: `Sudah nginx_apache · port 443 dipegang ${d.port443 || '?'}` }
      : d.layanan?.litespeed === 'active' && d.port443 === 'litespeed'
        ? { k: 'LiteSpeed melayani', s: 'siap', t: `webserver=${d.webserver}, php1_mode=${d.php1_mode}, port 443 = litespeed` }
        : { k: 'LiteSpeed melayani', s: 'belum', t: `litespeed ${d.layanan?.litespeed}, port 443 = ${d.port443 || 'kosong'}` },
    { k: 'httpd -t', s: d.httpd_t?.ok ? 'siap' : 'belum', t: d.httpd_t?.pesan || '-' },
    { k: 'liblsapi-devel 1.1-94', s: d.liblsapi ? 'siap' : 'belum', t: d.liblsapi ? 'Tersedia di repo CloudLinux (mod_lsapi dipin 1.1-94)' : 'Tidak ditemukan di cache dnf' },
    h == null
      ? { k: 'Handler PHP di .htaccess', s: 'info', t: 'Belum dipindai (cutover memindai sendiri)' }
      : h.lain.length
        ? { k: 'Handler PHP di .htaccess', s: 'belum', t: `${h.lain.length} berkas baru selain bloranews: ${h.lain.slice(0, 3).join(', ')}` }
        : { k: 'Handler PHP di .htaccess', s: 'siap', t: `Hanya bloranews (dikomentari cutover) · pindai ${waktuLalu(h.waktu)}` },
    { k: 'Velocity WAF untuk mod_security2', s: d.waf_mask32 ? 'waspada' : 'siap', t: d.waf_mask32 ? `${d.waf_mask32} IP ber-/32 (cutover menormalkan)` : 'Tanpa /32, Apache bisa start' },
    { k: 'cPGuard WAF', s: d.cpguard_waf_aktif ? 'waspada' : 'siap', t: d.cpguard_waf_aktif ? 'cpguard_waf.conf aktif lagi (cron cPGuard) → ikut termuat di Apache; gladi tetap lulus' : 'cpguard_waf.conf.off' },
    { k: 'Skrip migrasi', s: rusak.length ? 'belum' : 'siap', t: rusak.length ? `Hilang/sintaks rusak: ${rusak.join(', ')}` : `${skrip.length} skrip, sintaks OK` },
    { k: 'Cadangan konfigurasi', s: d.cadangan?.['konfig-web.tar.gz'] ? 'info' : 'waspada', t: d.cadangan?.['konfig-web.tar.gz'] ? `Terakhir ${tanggalWaktu(d.cadangan['konfig-web.tar.gz'])} · dibuat ulang saat cutover mulai` : 'Belum ada · dibuat saat cutover mulai' },
    !b
      ? { k: 'Baseline semua domain', s: 'info', t: 'Belum ada · dibuat saat cutover mulai' }
      : { k: 'Baseline semua domain', s: umurJam(b.waktu) > JAM_BASELINE ? 'info' : 'siap', t: `${angka(b.total)} domain, ${angka(b.kode?.['200'])}×200 · ${waktuLalu(b.waktu)}${umurJam(b.waktu) > JAM_BASELINE ? ' (cutover membuat ulang)' : ''}` },
    { k: 'Beban server', s: load1 > (d.cpu || 1) ? 'waspada' : 'siap', t: `load ${d.load?.join(' / ')} (${d.cpu} CPU) · RAM ${d.ram_persen}% · disk ${d.disk_persen}%` },
  ]
})
const pemblokir = computed(() => cek.value.filter((c) => c.s === 'belum'))

// Fase dari cutover.log (hanya run terakhir, mulai dari "== 1. praperiksa")
const FASE = [
  { k: '== 1.', label: 'Praperiksa & cadangan', ket: 'Tanpa downtime' },
  { k: '== 2.', label: 'Bangun mod_lsapi', ket: 'LSWS masih melayani; gagal = batal' },
  { k: '== 3.', label: 'Switch nginx_apache', ket: 'Downtime mulai saat LSWS dihentikan' },
  { k: '== 4.', label: 'Uji & cek semua domain', ket: 'Situs mati / PHP bocor → rollback otomatis' },
  { k: '== selesai', label: 'Selesai', ket: 'Lanjut pasang cache nginx' },
]
const log = computed(() => data.value?.log || [])
const gagalLog = computed(() => log.value.find((b) => /BATAL|rollback otomatis|-> rollback|rollback mulai/.test(b)))
const fase = computed(() => {
  const ke = FASE.map((f) => log.value.some((b) => b.includes(f.k)))
  const terakhir = ke.lastIndexOf(true)
  return FASE.map((f, i) => ({
    ...f,
    s: i < terakhir || (i === terakhir && i === FASE.length - 1) ? 'siap' : i === terakhir ? (gagalLog.value ? 'belum' : data.value?.berjalan ? 'jalan' : 'siap') : 'tunggu',
  }))
})
const kondisi = computed(() => {
  const d = data.value
  if (!d) return null
  if (d.berjalan) return { kelas: 'waspada', teks: 'Cutover sedang berjalan' }
  if (gagalLog.value) return { kelas: 'bahaya', teks: /BATAL/.test(gagalLog.value) ? 'Cutover batal (LSWS tetap)' : 'Rollback ke LiteSpeed' }
  if (sudahPindah.value) return { kelas: 'baik', teks: 'Sudah nginx_apache' }
  if (pemblokir.value.length) return { kelas: 'bahaya', teks: `${pemblokir.value.length} pemblokir` }
  return { kelas: 'baik', teks: 'Siap dijalankan' }
})
const basi = computed(() => data.value?.diambil && Date.now() / 1000 - data.value.diambil > 300)

// Perbandingan kode HTTP sebelum vs sesudah
const banding = computed(() => {
  const a = data.value?.baseline, b = data.value?.sesudah
  if (!a || !b) return []
  return [...new Set([...Object.keys(a.kode), ...Object.keys(b.kode)])].sort().map((k) => ({ k, a: a.kode[k] || 0, b: b.kode[k] || 0 }))
})
const MODUL = ['lsapi_module', 'security2_module', 'hostinglimits_module']
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Migrasi Farnaz</h1>
        <p class="redup">LiteSpeed → nginx_apache (mod_lsapi, PHP Selector per user tetap). Dibaca dari server tiap menit, tanpa mengubah apa pun.</p>
      </div>
      <button type="button" class="tombol garis kecil" @click="muatUlang"><Ikon nama="ulang" :ukuran="16" /> Muat ulang</button>
    </header>

    <p v-if="memuat" class="redup" role="status">Memuat…</p>
    <p v-else-if="galat && !data" class="pesan-status bahaya">Gagal memuat: {{ galat.message }}</p>

    <template v-else-if="data">
      <p v-if="data.galat" class="pesan-status bahaya" role="alert">Pengambilan terakhir gagal ({{ waktuLalu(data.galat_waktu) }}): {{ data.galat }} — data di bawah dari {{ tanggalWaktu(data.waktu) }}.</p>
      <p v-else-if="basi" class="pesan-status waspada">Data tidak diperbarui sejak {{ waktuLalu(data.diambil) }} — periksa timer migrasi-farnaz.timer.</p>

      <div class="ringkas">
        <div class="kartu angka"><span class="redup">Status</span><b class="kecil-b"><span class="pil" :class="kondisi.kelas">{{ kondisi.teks }}</span></b></div>
        <div class="kartu angka"><span class="redup">Webserver</span><b class="kecil-b">{{ data.webserver }}</b><small class="redup">443: {{ data.port443 || 'kosong' }} · litespeed {{ data.layanan?.litespeed }} · httpd {{ data.layanan?.httpd }} · nginx {{ data.layanan?.nginx }}</small></div>
        <div class="kartu angka"><span class="redup">Diperbarui</span><b class="kecil-b">{{ waktuLalu(data.waktu) }}</b><small class="redup">{{ tanggalWaktu(data.waktu) }}</small></div>
      </div>

      <section class="kartu" aria-labelledby="judul-cek">
        <div class="kartu-judul"><h2 id="judul-cek"><Ikon nama="daftar" :ukuran="16" /> Praperiksa</h2></div>
        <ul class="daftar-cek">
          <li v-for="c in cek" :key="c.k">
            <span class="status" :class="STATUS[c.s].kelas"><Ikon :nama="STATUS[c.s].ikon" :ukuran="14" /> {{ STATUS[c.s].label }}</span>
            <div><b>{{ c.k }}</b><small class="redup blok">{{ c.t }}</small></div>
          </li>
        </ul>
      </section>

      <section class="kartu" aria-labelledby="judul-fase">
        <div class="kartu-judul">
          <h2 id="judul-fase"><Ikon nama="mainkan" :ukuran="16" /> Progres cutover</h2>
          <span class="redup">{{ data.berjalan ? 'cutover.sh berjalan' : data.log ? 'tidak berjalan' : 'belum pernah dijalankan' }}</span>
        </div>
        <ol class="fase">
          <li v-for="(f, i) in fase" :key="f.k" :class="f.s">
            <span class="nomor">{{ f.s === 'siap' ? '✓' : f.s === 'belum' ? '!' : i + 1 }}</span>
            <div><b>{{ f.label }}</b><small class="redup blok">{{ f.ket }}</small></div>
          </li>
        </ol>
        <p v-if="gagalLog" class="pesan-status bahaya" role="alert">{{ gagalLog }}</p>
        <template v-if="sudahPindah || data.layanan?.httpd === 'active'">
          <h3 class="sub-judul">Modul Apache</h3>
          <p class="chip-baris"><span v-for="m in MODUL" :key="m" class="status" :class="data.modul.includes(m) ? 'hijau' : 'merah'"><Ikon :nama="data.modul.includes(m) ? 'centang' : 'tutup'" :ukuran="14" /> {{ m }}</span></p>
        </template>
        <template v-if="banding.length">
          <h3 class="sub-judul">Kode HTTP semua domain: sebelum → sesudah</h3>
          <div class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">Kode</th><th scope="col">Sebelum</th><th scope="col">Sesudah</th><th scope="col">Selisih</th></tr></thead>
              <tbody>
                <tr v-for="r in banding" :key="r.k"><td>{{ r.k }}</td><td>{{ angka(r.a) }}</td><td>{{ angka(r.b) }}</td><td :class="{ merah: r.k === '200' ? r.b < r.a : r.b > r.a }">{{ r.b - r.a > 0 ? '+' : '' }}{{ r.b - r.a }}</td></tr>
                <tr><td>PHP bocor</td><td>{{ data.baseline.bocor }}</td><td>{{ data.sesudah.bocor }}</td><td :class="{ merah: data.sesudah.bocor > data.baseline.bocor }">{{ data.sesudah.bocor - data.baseline.bocor }}</td></tr>
              </tbody>
            </table>
          </div>
          <p class="redup kecil-teks">Daftar domain yang berubah: <code>/root/migrasi-nginx/beda-sebelum-sesudah.tsv</code></p>
        </template>
        <p v-if="sudahPindah" class="redup kecil-teks">Cache nginx pengganti LSCache ({{ data.cache_domain }} domain): {{ data.cache_terpasang ? 'terpasang' : 'belum dipasang' }}. Cron lsws-traffic-alert: <code>{{ data.cron_lsws || '-' }}</code></p>
      </section>

      <section v-if="data.log" class="kartu" aria-labelledby="judul-log">
        <div class="kartu-judul"><h2 id="judul-log"><Ikon nama="dokumen" :ukuran="16" /> cutover.log (run terakhir)</h2></div>
        <pre class="log">{{ log.join('\n') }}</pre>
      </section>

      <section class="kartu catatan" aria-labelledby="judul-cara">
        <div class="kartu-judul"><h2 id="judul-cara"><Ikon nama="peringatan" :ukuran="16" /> Cara menjalankan (manual, di Farnaz)</h2></div>
        <ol class="langkah">
          <li>Masuk: <code>ssh -p 53864 root@103.103.175.182</code> (tmux tidak ada di Farnaz, pakai screen).</li>
          <li>Jalankan: <code>screen -S migrasi /root/migrasi-nginx/cutover.sh</code>. Putus koneksi: <code>screen -r migrasi</code>.</li>
          <li>Sesudah selesai: <code>/root/migrasi-nginx/cache/pasang-cache.sh</code> (lepas: <code>pasang-cache.sh lepas</code>).</li>
          <li>Gagal parah: <code>/root/migrasi-nginx/rollback-cepat.sh</code> lalu <code>cek.sh rollback</code>.</li>
        </ol>
      </section>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.ringkas { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.angka { display: grid; gap: 6px; align-content: start; }
.angka .kecil-b { font-size: 16px; color: var(--teks-kuat); }
.ringkas small { font-size: 12px; overflow-wrap: anywhere; }
.daftar-cek { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.daftar-cek li { display: grid; grid-template-columns: 116px minmax(0, 1fr); gap: 10px; align-items: start; }
.daftar-cek b { font-size: 13.5px; color: var(--teks-kuat); }
.status { display: inline-flex; align-items: center; gap: 5px; font-weight: 600; font-size: 13px; }
.status.hijau { color: var(--baik); }
.status.kuning { color: var(--waspada); }
.status.merah { color: var(--bahaya); }
.status.abu { color: var(--teks-2); }
.blok { display: block; margin-top: 2px; overflow-wrap: anywhere; font-size: 12.5px; }
.fase { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr)); gap: 10px; }
.fase li { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border: 1px solid var(--garis); border-radius: 12px; }
.fase b { font-size: 13.5px; }
.nomor { flex: none; display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; font-weight: 700; font-size: 13px; background: var(--garis); color: var(--teks-2); }
.fase .siap .nomor { background: color-mix(in srgb, var(--baik) 18%, transparent); color: var(--baik); }
.fase .jalan { border-color: var(--aksen-terang); }
.fase .jalan .nomor { background: var(--aksen-lembut); color: var(--aksen-terang); }
.fase .belum { border-color: var(--bahaya); }
.fase .belum .nomor { background: color-mix(in srgb, var(--bahaya) 18%, transparent); color: var(--bahaya); }
.fase .tunggu { opacity: 0.7; }
.sub-judul { font-size: 14px; margin: 16px 0 8px; }
.chip-baris { display: flex; flex-wrap: wrap; gap: 14px; margin: 0; }
.merah { color: var(--bahaya); font-weight: 600; }
.tabel-wadah { overflow-x: auto; }
.log { margin: 0; max-height: 420px; overflow: auto; padding: 12px; border-radius: 10px; background: var(--latar); border: 1px solid var(--garis); font: 12px/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
.langkah { margin: 0; padding-left: 20px; display: grid; gap: 7px; font-size: 13.5px; }
.kecil-teks { font-size: 12.5px; margin: 10px 0 0; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); overflow-wrap: anywhere; }
@media (max-width: 900px) { .ringkas { grid-template-columns: 1fr; } }
@media (max-width: 560px) { .daftar-cek li { grid-template-columns: 1fr; gap: 2px; } }
</style>
