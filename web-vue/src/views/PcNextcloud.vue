<script setup>
// Nextcloud di PC Backup (cloud.velocity.ai.id): versi, layanan, kuota dataset ZFS, pengguna, cron, backup DB, setupchecks.
// API: GET /api/fm/pc-backup/nextcloud[?segar=1] (services/pc_nextcloud.py, cache 5 mnt, disegarkan di latar).
import { ref, computed } from 'vue'
import Ikon from '../components/Ikon.vue'
import { pakaiPolling, minta, ukuranBerkas, tanggalWaktu, waktuLalu } from '../api.js'

const st = pakaiPolling('/api/fm/pc-backup/nextcloud', 60000)
const d = computed(() => st.data.value)
const nc = computed(() => d.value?.nc)
const ds = computed(() => nc.value?.dataset)
const persen = computed(() => (ds.value?.kuota ? Math.round((ds.value.terpakai / ds.value.kuota) * 100) : 0))

const menyegarkan = ref(false)
async function segarkan() {
  menyegarkan.value = true
  try { st.data.value = await minta('/api/fm/pc-backup/nextcloud?segar=1') } catch (e) { st.galat.value = e } finally { menyegarkan.value = false }
}

const LAYANAN = { nginx: 'nginx', 'php8.3-fpm': 'PHP-FPM', 'redis-server': 'Redis', mariadb: 'MariaDB', cloudflared: 'Tunnel', 'nextcloud-cron.timer': 'Cron' }
const layananMati = computed(() => Object.entries(nc.value?.layanan || {}).filter(([, v]) => v !== 'active').map(([k]) => LAYANAN[k] || k))
// Cron tiap 5 mnt; > 15 mnt tanpa jalan = timer bermasalah
const cronTelat = computed(() => nc.value?.cron_terakhir && nc.value.waktu - nc.value.cron_terakhir > 900)
const statusNc = computed(() => {
  const s = nc.value?.status
  if (!s?.installed) return ['bahaya', 'Tidak terpasang']
  if (s.maintenance) return ['waspada', 'Maintenance']
  if (s.needsDbUpgrade) return ['waspada', 'Perlu upgrade DB']
  return ['baik', 'Berjalan']
})
const TINGKAT = { error: ['bahaya', 'Error'], warning: ['waspada', 'Peringatan'], info: ['', 'Info'] }
const cek = computed(() => [...(nc.value?.cek || [])].sort((a, b) => ['error', 'warning', 'info'].indexOf(a.tingkat) - ['error', 'warning', 'info'].indexOf(b.tingkat)))
const bersih = (t) => (t || '').replace(/\s*\{link\}/g, '')
const terbaru = (t) => /up.to.date|no updates/i.test(t || '')
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Nextcloud</h1>
        <p class="redup">Cloud storage tim di PC Backup, data di dataset ZFS <code>Backup/nextcloud</code>, diakses lewat Cloudflare Tunnel.</p>
      </div>
      <div class="aksi">
        <a :href="d?.url || 'https://cloud.velocity.ai.id'" target="_blank" rel="noopener" class="tombol garis kecil"><Ikon nama="luar" :ukuran="15" /> Buka Nextcloud</a>
        <button type="button" class="tombol garis kecil" :disabled="menyegarkan || d?.menyegarkan" @click="segarkan"><Ikon nama="ulang" :ukuran="15" /> {{ menyegarkan || d?.menyegarkan ? 'Menyegarkan…' : 'Segarkan' }}</button>
      </div>
    </header>

    <p v-if="st.memuat.value && !d" class="redup">Memuat status Nextcloud (±30 detik)…</p>
    <p v-else-if="st.galat.value && !d" class="peringatan" role="alert">Gagal memuat status: {{ st.galat.value.message }}</p>

    <template v-if="d">
      <p v-if="d.galat" class="peringatan" role="alert">
        PC Backup tidak menjawab lewat SSH: {{ d.galat }}.
        <template v-if="nc">Data di bawah dari pengecekan terakhir yang berhasil ({{ waktuLalu(nc.waktu) }}).</template>
      </p>
      <p v-if="layananMati.length" class="peringatan" role="alert">Layanan tidak berjalan: {{ layananMati.join(', ') }}.</p>
      <p v-if="cronTelat" class="peringatan" role="alert">Cron Nextcloud terakhir jalan {{ waktuLalu(nc.cron_terakhir) }}. Periksa nextcloud-cron.timer.</p>

      <section v-if="nc" class="ringkas" aria-label="Ringkasan">
        <div class="kartu stat">
          <span class="redup">Status <span class="pil" :class="statusNc[0]">{{ statusNc[1] }}</span></span>
          <strong>{{ nc.status?.versionstring || '-' }}</strong>
          <span class="redup"><a :href="d.url" target="_blank" rel="noopener">{{ d.url.replace('https://', '') }}</a></span>
          <span class="redup">{{ nc.aplikasi?.aktif ?? '-' }} aplikasi aktif</span>
        </div>
        <div class="kartu stat">
          <span class="redup">Penyimpanan</span>
          <strong>{{ ds ? `${persen}%` : '-' }}</strong>
          <div class="meter" :class="{ waspada: persen >= 75, bahaya: persen >= 90 }" role="meter" :aria-valuenow="persen" aria-valuemin="0" aria-valuemax="100" aria-label="Pemakaian kuota Nextcloud"><i :style="{ width: persen + '%' }" /></div>
          <span class="redup" v-if="ds">Terpakai {{ ukuranBerkas(ds.terpakai) }} dari kuota {{ ukuranBerkas(ds.kuota) }}</span>
        </div>
        <div class="kartu stat">
          <span class="redup">Pengguna</span>
          <strong>{{ nc.pengguna?.length ?? '-' }}</strong>
          <span class="redup">Cron {{ nc.cron_terakhir ? waktuLalu(nc.cron_terakhir) : 'belum jalan' }}</span>
        </div>
        <div class="kartu stat">
          <span class="redup">Layanan</span>
          <ul class="layanan">
            <li v-for="(v, k) in nc.layanan || {}" :key="k"><span class="titik" :class="v === 'active' ? 'baik' : 'bahaya'" aria-hidden="true" /> {{ LAYANAN[k] || k }} <span v-if="v !== 'active'" class="redup">{{ v }}</span></li>
          </ul>
        </div>
      </section>

      <section v-if="nc" class="kartu" aria-labelledby="judul-pengguna">
        <div class="kartu-judul"><h2 id="judul-pengguna">Pengguna</h2><span class="redup">Kelola akun di Nextcloud ▸ Akun</span></div>
        <div class="tabel-gulir">
          <table class="tabel">
            <thead><tr><th>Akun</th><th>Grup</th><th>Terpakai</th><th>Kuota</th><th>Terakhir masuk</th></tr></thead>
            <tbody>
              <tr v-for="u in nc.pengguna" :key="u.id">
                <td><b>{{ u.nama || u.id }}</b> <span v-if="!u.aktif" class="pil bahaya">Nonaktif</span><br><span class="redup kecil">{{ u.id }}<template v-if="u.email"> · {{ u.email }}</template></span></td>
                <td>{{ u.grup.join(', ') || '-' }}</td>
                <td>{{ u.terpakai != null ? ukuranBerkas(u.terpakai) : '-' }}</td>
                <td>{{ u.kuota === 'none' ? 'Tanpa batas' : u.kuota || '-' }}</td>
                <td>{{ u.terakhir ? tanggalWaktu(Date.parse(u.terakhir) / 1000) : 'Belum pernah' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="nc" class="kartu">
        <div class="blok-server">
          <div>
            <h3>Backup</h3>
            <ul class="daftar">
              <li><span>Snapshot ZFS</span><span class="redup">{{ nc.snapshot?.jumlah ?? '-' }} · tiap hari 23:00, simpan 7</span></li>
              <li><span>Snapshot terbaru</span><span class="redup">{{ nc.snapshot?.terbaru ? tanggalWaktu(nc.snapshot.terbaru) : '-' }}</span></li>
              <li><span>Dump database</span><span :class="nc.dump ? 'redup' : 'galat'">{{ nc.dump ? `${tanggalWaktu(nc.dump.waktu)} · ${ukuranBerkas(nc.dump.ukuran)}` : 'Belum ada' }}</span></li>
              <li><span>Ruang snapshot</span><span class="redup">{{ ds ? ukuranBerkas(ds.snapshot) : '-' }}</span></li>
            </ul>
          </div>
          <div>
            <h3>Pembaruan</h3>
            <ul class="daftar">
              <li><span>Inti</span><span :class="terbaru(nc.pembaruan?.inti) ? 'redup' : 'galat'">{{ terbaru(nc.pembaruan?.inti) ? 'Terbaru' : nc.pembaruan?.inti || '-' }}</span></li>
              <li><span>Aplikasi</span><span :class="terbaru(nc.pembaruan?.aplikasi) ? 'redup' : 'galat'">{{ terbaru(nc.pembaruan?.aplikasi) ? 'Terbaru' : nc.pembaruan?.aplikasi || '-' }}</span></li>
            </ul>
          </div>
          <div>
            <h3>Sistem</h3>
            <ul class="daftar">
              <li><span>Lokasi data</span><span class="redup">/srv/backup/nextcloud/data</span></li>
              <li><span>Web</span><span class="redup">nginx 127.0.0.1:8250</span></li>
              <li><span>Batas unggah</span><span class="redup">chunk 50 MB (Cloudflare)</span></li>
            </ul>
          </div>
        </div>
      </section>

      <section v-if="cek.length" class="kartu" aria-labelledby="judul-cek">
        <div class="kartu-judul"><h2 id="judul-cek">Pemeriksaan sistem</h2><span class="redup">occ setupchecks · yang lolos tidak ditampilkan</span></div>
        <ul class="daftar-cek">
          <li v-for="(c, i) in cek" :key="i">
            <span class="pil" :class="TINGKAT[c.tingkat]?.[0]">{{ TINGKAT[c.tingkat]?.[1] || c.tingkat }}</span>
            <div><b>{{ c.nama }}</b><p class="redup kecil">{{ bersih(c.keterangan) }}</p></div>
          </li>
        </ul>
      </section>
      <p class="redup diperbarui">Diperbarui {{ waktuLalu(d.diperbarui) }}<template v-if="d.menyegarkan"> · menyegarkan…</template></p>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; min-width: 0; }
.aksi { display: flex; gap: 8px; flex-wrap: wrap; }
.aksi .tombol { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; }
.ringkas { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(190px, 100%), 1fr)); gap: 14px; }
.kartu { min-width: 0; }
.stat { display: grid; gap: 6px; align-content: start; }
.stat strong { font-size: 24px; }
.stat a, .kartu-judul a { color: var(--aksen-terang); }
.meter.waspada i { background: var(--waspada); }
.meter.bahaya i { background: var(--bahaya); }
.galat { color: var(--bahaya); overflow-wrap: anywhere; }
.layanan { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; font-size: 14px; }
.layanan li { display: flex; align-items: center; gap: 8px; }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); }
.titik.baik { background: var(--baik); }
.titik.bahaya { background: var(--bahaya); }
.blok-server { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr)); gap: 18px 28px; }
.blok-server > div { min-width: 0; }
.blok-server h3 { margin: 0 0 8px; font-size: 12px; font-weight: 600; color: var(--teks-3); text-transform: uppercase; letter-spacing: .04em; }
.daftar { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; font-size: 14px; }
.daftar li { display: flex; justify-content: space-between; gap: 12px; padding-bottom: 6px; border-bottom: 1px solid var(--garis); }
.daftar li:last-child { border-bottom: 0; padding-bottom: 0; }
.daftar li > :last-child { text-align: right; overflow-wrap: anywhere; }
.kecil { font-size: 12px; }
.diperbarui { margin: -6px 0 0; text-align: right; }
.tabel-gulir { overflow-x: auto; }
.tabel { width: 100%; border-collapse: collapse; font-size: 14px; }
.tabel th { text-align: left; font-size: 12px; font-weight: 600; color: var(--teks-3); padding: 0 12px 8px 0; white-space: nowrap; }
.tabel td { padding: 8px 12px 8px 0; border-top: 1px solid var(--garis); vertical-align: top; }
.daftar-cek { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; font-size: 14px; }
.daftar-cek li { display: grid; grid-template-columns: 96px minmax(0, 1fr); align-items: start; gap: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--garis); }
.daftar-cek li:last-child { border-bottom: 0; padding-bottom: 0; }
.daftar-cek .pil { justify-self: start; }
.daftar-cek div { min-width: 0; overflow-wrap: anywhere; }
.daftar-cek p { margin: 2px 0 0; white-space: pre-line; }
.peringatan { margin: 0; padding: 12px 14px; border-radius: var(--radius-kecil); border: 1px solid var(--waspada); background: rgba(232, 181, 74, .1); color: var(--teks); font-size: 14px; }
</style>
