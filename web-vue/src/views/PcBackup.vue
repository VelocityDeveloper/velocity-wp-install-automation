<script setup>
// Status PC Backup (Ubuntu + ZFS lewat Tailscale): mesin, pool, disk, snapshot + backup sistem PC kantor.
// Backup server DirectAdmin (rsync) ada di /pc-backup/backup; backup FTP bawaan DA tak dipakai lagi.
// API: GET /api/fm/pc-backup[?segar=1] (services/pc_backup.py, data di-cache 60 dtk).
import { ref, computed } from 'vue'
import Ikon from '../components/Ikon.vue'
import { pakaiPolling, minta, ukuranBerkas, tanggalWaktu, waktuLalu } from '../api.js'

const st = pakaiPolling('/api/fm/pc-backup', 60000)
const d = computed(() => st.data.value)
const pc = computed(() => d.value?.pc)
const pool = computed(() => pc.value?.pool?.find((p) => p.nama === 'Backup') || pc.value?.pool?.[0])
const persenPool = computed(() => (pool.value ? Math.round((pool.value.terpakai / pool.value.ukuran) * 100) : 0))

const menyegarkan = ref(false)
async function segarkan() {
  menyegarkan.value = true
  try { st.data.value = await minta('/api/fm/pc-backup?segar=1') } catch (e) { st.galat.value = e } finally { menyegarkan.value = false }
}

const uptime = (s) => {
  if (!s) return '-'
  const h = Math.floor(s / 86400); const j = Math.floor((s % 86400) / 3600); const m = Math.floor((s % 3600) / 60)
  return h ? `${h} hari ${j} jam` : j ? `${j} jam ${m} mnt` : `${m} mnt`
}
const durasi = (a, b) => {
  const s = Math.max(0, b - a)
  return s < 60 ? `${s} dtk` : s < 3600 ? `${Math.round(s / 60)} mnt` : `${(s / 3600).toFixed(1)} jam`
}

// Kesehatan HDD: bahaya = SMART gagal / sektor pending / uncorrectable / error ZFS; waspada = sektor realokasi / panas
function statusDisk(x) {
  if (x.sehat === false || x.pending > 0 || x.uncorrect > 0 || x.pool?.galat > 0 || (x.pool && x.pool.status !== 'ONLINE')) return ['bahaya', 'Bermasalah']
  if (x.realloc > 0 || x.suhu >= 50) return ['waspada', 'Waspada']
  if (x.sehat == null) return ['', 'Tak terbaca']
  return ['baik', 'Sehat']
}
const diskBermasalah = computed(() => (pc.value?.disk || []).filter((x) => statusDisk(x)[0] === 'bahaya'))
const LAYANAN = { smartmontools: 'SMART', tailscaled: 'Tailscale', 'zfs-zed': 'ZFS', 'backup-snapshot.timer': 'Snapshot', 'zfs-scrub-mingguan.timer': 'Scrub', 'zfs-pulihkan.timer': 'Pemulih', ufw: 'Firewall' }
const layananMati = computed(() => Object.entries(pc.value?.layanan || {}).filter(([, v]) => v !== 'active').map(([k]) => LAYANAN[k] || k))

// Backup server DA (rsync): run terakhir per server dari .status.json di PC Backup
function statusRsync(x) {
  if (x.berjalan) return ['waspada', 'Berjalan']
  if (x.tahap === 'selesai') return ['baik', 'Sukses']
  if (x.tahap === 'gagal') return x.akun_selesai === x.akun_total && x.akun_total ? ['waspada', 'Sebagian gagal'] : ['bahaya', 'Gagal']
  return ['bahaya', 'Terhenti']
}
// Sama dengan PcRestore.vue: berkas 0–95%, DB 95–100%
const persenRsync = (x) => x.tahap === 'db'
  ? 95 + Math.round((x.db_selesai / (x.db_total || 1)) * 5)
  : Math.min(95, Math.round((x.byte_selesai / (x.byte_total || 1)) * 95))
const jam = (t) => (t ? new Date(t * 1000).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) : '-')

// Backup sistem PC kantor (velocity-backup, harian 02:00) -> /srv/backup/pckantor; status dari server_stats.py
const sistem = pakaiPolling('/api/backup', 15000)
const bs = computed(() => sistem.data.value)
const statusSistem = computed(() => {
  const x = bs.value
  if (!x) return ['', '-']
  if (x.state === 'ok' && x.stale) return ['bahaya', 'Basi']
  return ({ ok: ['baik', 'Sukses'], running: ['waspada', 'Berjalan'], error: ['bahaya', 'Gagal'], belum_pernah: ['', 'Belum pernah'] })[x.state] || ['', x.state]
})
const FASE = { prasyarat: 'Cek prasyarat', 'dump-database': 'Dump database', 'daftar-paket': 'Daftar paket', arsip: 'Mengarsip + enkripsi', unggah: 'Mengunggah ke PC Backup', mingguan: 'Salinan mingguan', pangkas: 'Pangkas arsip lama' }
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Status Backup</h1>
        <p class="redup">Kondisi PC Backup dan backup sistem PC kantor; snapshot ZFS harian menjaga versi lama 7 hari. Backup server DirectAdmin (rsync) ada di menu <RouterLink to="/pc-backup/backup">Backup</RouterLink>.</p>
      </div>
      <div class="aksi">
        <RouterLink to="/pc-backup/berkas" class="tombol garis kecil"><Ikon nama="berkas" :ukuran="15" /> File Manager</RouterLink>
        <button type="button" class="tombol garis kecil" :disabled="menyegarkan" @click="segarkan"><Ikon nama="ulang" :ukuran="15" /> {{ menyegarkan ? 'Menyegarkan…' : 'Segarkan' }}</button>
      </div>
    </header>

    <p v-if="st.memuat.value && !d" class="redup">Memuat status PC Backup…</p>
    <p v-else-if="st.galat.value && !d" class="peringatan" role="alert">Gagal memuat status: {{ st.galat.value.message }}</p>

    <template v-if="d">
      <p v-if="d.galat" class="peringatan" role="alert">
        PC Backup tidak menjawab lewat SSH: {{ d.galat }}.
        <template v-if="pc">Data di bawah dari pengecekan terakhir yang berhasil ({{ waktuLalu(pc.waktu) }}).</template>
      </p>
      <p v-else-if="layananMati.length" class="peringatan" role="alert">Layanan tidak berjalan di PC Backup: {{ layananMati.join(', ') }}.</p>
      <p v-if="diskBermasalah.length" class="peringatan bahaya" role="alert">
        Disk bermasalah: <template v-for="(x, i) in diskBermasalah" :key="x.nama">{{ i ? '; ' : '' }}{{ x.model }} ({{ x.nama }})</template>.
        Pool stripe: satu disk rusak = seluruh backup hilang. Siapkan pengganti.
      </p>

      <section class="ringkas" aria-label="Ringkasan">
        <div class="kartu stat">
          <span class="redup">Sambungan</span>
          <strong><span class="pil" :class="d.tersambung ? 'baik' : 'bahaya'">{{ d.tersambung ? 'Tersambung' : 'Terputus' }}</span></strong>
          <span class="redup">{{ pc?.sistem?.host || 'pc-backup' }} · {{ pc?.sistem?.os || '-' }}</span>
          <span class="redup">Menyala {{ uptime(pc?.sistem?.uptime) }}</span>
        </div>
        <div class="kartu stat">
          <span class="redup">Pool {{ pool?.nama || '-' }} <span v-if="pool" class="pil" :class="pool.status === 'ONLINE' ? 'baik' : 'bahaya'">{{ pool.status }}</span></span>
          <strong>{{ pool ? `${persenPool}%` : '-' }}</strong>
          <div class="meter" :class="{ waspada: persenPool >= 75, bahaya: persenPool >= 90 }" role="meter" :aria-valuenow="persenPool" aria-valuemin="0" aria-valuemax="100" aria-label="Pemakaian pool"><i :style="{ width: persenPool + '%' }" /></div>
          <span class="redup" v-if="pool">Terpakai {{ ukuranBerkas(pool.terpakai) }} · sisa {{ ukuranBerkas(pool.sisa) }} dari {{ ukuranBerkas(pool.ukuran) }}</span>
        </div>
        <div class="kartu stat">
          <span class="redup">Snapshot</span>
          <strong>{{ pc?.snapshot?.jumlah ?? '-' }}</strong>
          <span class="redup">{{ pc?.snapshot?.terbaru ? `Terbaru ${tanggalWaktu(pc.snapshot.terbaru)}` : 'Belum ada snapshot' }}</span>
          <span class="redup" v-if="pc?.snapshot">Tiap hari {{ pc.snapshot.jam }}, simpan {{ pc.snapshot.simpan_hari }} hari</span>
        </div>
        <div class="kartu stat">
          <span class="redup">Layanan</span>
          <ul class="layanan">
            <li v-for="(v, k) in pc?.layanan || {}" :key="k"><span class="titik" :class="v === 'active' ? 'baik' : 'bahaya'" aria-hidden="true" /> {{ LAYANAN[k] || k }} <span v-if="v !== 'active'" class="redup">{{ v }}</span></li>
          </ul>
        </div>
      </section>

      <section v-if="pc?.disk?.length" class="kartu" aria-labelledby="judul-disk">
        <div class="kartu-judul"><h2 id="judul-disk">Kesehatan disk</h2><span class="redup">SMART + error ZFS · uji pendek harian, panjang bulanan</span></div>
        <div class="tabel-gulir">
          <table class="tabel-disk">
            <thead><tr><th>Disk</th><th>Status</th><th>Suhu</th><th>Menyala</th><th title="Reallocated / Pending / Uncorrectable">Sektor rusak</th><th>Error ZFS</th><th>Uji terakhir</th></tr></thead>
            <tbody>
              <tr v-for="x in pc.disk" :key="x.nama">
                <td><b>{{ x.model || x.nama }}</b><br><span class="redup kecil">{{ x.nama }} · {{ x.ukuran ? ukuranBerkas(x.ukuran) : '-' }} · {{ x.rpm ? `${x.rpm} rpm` : 'SSD' }}{{ x.pool ? ' · pool' : ' · sistem' }}</span></td>
                <td><span class="pil" :class="statusDisk(x)[0]">{{ statusDisk(x)[1] }}</span></td>
                <td :class="{ galat: x.suhu >= 50 }">{{ x.suhu != null ? `${x.suhu}°C` : '-' }}</td>
                <td>{{ x.jam != null ? `${x.jam.toLocaleString('id-ID')} jam` : '-' }}<template v-if="x.jam != null"><br><span class="redup kecil">±{{ Math.floor(x.jam / 24).toLocaleString('id-ID') }} hari</span></template></td>
                <td :class="{ galat: x.pending > 0 || x.uncorrect > 0 }">{{ x.realloc ?? '-' }} / {{ x.pending ?? '-' }} / {{ x.uncorrect ?? '-' }}<span v-if="x.crc" class="redup kecil"> · CRC {{ x.crc }}</span></td>
                <td :class="{ galat: x.pool?.galat > 0 }">{{ x.pool ? x.pool.galat : '-' }}<template v-if="x.pool?.galat"><br><span class="redup kecil">baca {{ x.pool.baca }} · tulis {{ x.pool.tulis }} · cksum {{ x.pool.cksum }}</span></template></td>
                <td class="kecil">{{ x.uji_terakhir ? `${x.uji_terakhir}: ${x.uji_hasil}` : 'Belum pernah' }}<span v-if="x.uji_jam != null && x.jam != null" class="redup"> · {{ x.jam - x.uji_jam }} jam lalu</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="pc.zfs_scan" class="redup kecil">Scrub terakhir: {{ pc.zfs_scan }}</p>
        <div v-if="pc.zfs_rusak?.length" class="berkas-rusak">
          <p class="galat"><b>{{ pc.zfs_rusak.length }} berkas rusak permanen</b> (blok gagal dibaca/checksum). Berkas rsync dihapus otomatis 00:45 lalu disalin ulang dari server malam itu; snapshot &amp; arsip PC kantor hanya dicatat.</p>
          <ul class="kecil"><li v-for="f in pc.zfs_rusak" :key="f.berkas"><code>{{ f.berkas }}</code><span v-if="!f.aktif" class="redup"> · berkas sudah tak ada, tinggal di snapshot</span><span v-if="f.snapshot.length" class="redup"> · juga di snapshot {{ f.snapshot.join(', ') }}</span></li></ul>
        </div>
        <div v-if="pc.pulih?.length" class="berkas-rusak">
          <p><b>Riwayat pemulihan</b> <span class="redup kecil">berkas rsync rusak yang dihapus agar disalin ulang</span></p>
          <ul class="kecil">
            <li v-for="r in pc.pulih" :key="r.waktu">
              {{ tanggalWaktu(r.waktu) }}: {{ r.dihapus.length }} dihapus<template v-if="r.gagal.length">, <span class="galat">{{ r.gagal.length }} gagal</span></template><template v-if="r.dicatat.length"> · {{ r.dicatat.length }} hanya dicatat</template>
              <span v-if="r.batal" class="galat"> · {{ r.batal }}</span>
              <details v-if="r.dihapus.length"><summary class="redup">Lihat berkas</summary><code v-for="f in r.dihapus" :key="f" class="baris-kode">{{ f }}</code></details>
            </li>
          </ul>
        </div>
      </section>

      <section v-if="pc?.rsync?.length" class="kartu" aria-labelledby="judul-rsync">
        <div class="kartu-judul">
          <h2 id="judul-rsync">Backup server terakhir</h2>
          <span class="redup">rsync tarik dari PC Backup · <RouterLink to="/pc-backup/backup">Lihat isi</RouterLink></span>
        </div>
        <div class="tabel-gulir">
          <table class="tabel-disk">
            <thead><tr><th>Server</th><th>Status</th><th>Mulai</th><th>Lama</th><th>Akun</th><th>DB</th><th title="Ukuran berkas akun di server (diperiksa rsync)">Data</th><th title="Dipakai dataset ZFS, termasuk snapshot">Tersimpan</th><th>Jadwal</th></tr></thead>
            <tbody>
              <tr v-for="x in pc.rsync" :key="x.server">
                <td><b>{{ x.server }}</b></td>
                <td><span class="pil" :class="statusRsync(x)[0]">{{ statusRsync(x)[1] }}</span>
                  <template v-if="x.berjalan"><div class="meter jalan meter-rsync" role="progressbar" :aria-valuenow="persenRsync(x)" aria-valuemin="0" aria-valuemax="100" :aria-label="`Kemajuan backup ${x.server}`"><i :style="{ width: `${persenRsync(x)}%` }" /></div><span class="redup kecil">{{ persenRsync(x) }}% · {{ x.tahap === 'db' ? `DB ${x.db_selesai}/${x.db_total}` : `akun ${x.akun_selesai}/${x.akun_total}` }}</span></template></td>
                <td>{{ tanggalWaktu(x.mulai) }}<br><span class="redup kecil">{{ waktuLalu(x.mulai) }}</span></td>
                <td>{{ durasi(x.mulai, x.berjalan ? Math.floor(Date.now() / 1000) : x.selesai || x.diperbarui) }}<br><span class="redup kecil">{{ x.berjalan ? 'masih jalan' : `selesai ${jam(x.selesai)}` }}</span></td>
                <td :class="{ galat: x.gagal.length }">{{ x.akun_selesai }}/{{ x.akun_total }}<template v-if="x.gagal.length"><br><span class="kecil">{{ x.gagal.length }} gagal</span></template></td>
                <td :class="{ galat: x.db_gagal.length }">{{ x.db_selesai - x.db_gagal.length }}/{{ x.db_total }}<template v-if="x.db_gagal.length"><br><span class="kecil">{{ x.db_gagal.length }} gagal</span></template></td>
                <td>{{ ukuranBerkas(x.byte_selesai) }}<br><span class="redup kecil">±{{ ukuranBerkas(x.laju) }}/dtk</span></td>
                <td>{{ x.byte_tersimpan ? ukuranBerkas(x.byte_tersimpan) : '-' }}</td>
                <td>{{ x.jadwal ? `Harian ${x.jadwal}` : '-' }}<br><span class="redup kecil">{{ x.berikutnya ? `berikutnya ${tanggalWaktu(x.berikutnya)}` : 'timer mati' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <details v-if="pc.rsync.some((x) => x.gagal.length || x.db_gagal.length)" class="kecil">
          <summary class="galat">Rincian yang gagal</summary>
          <ul><li v-for="x in pc.rsync.filter((x) => x.gagal.length || x.db_gagal.length)" :key="x.server"><b>{{ x.server }}</b>: <template v-if="x.gagal.length">akun {{ x.gagal.join(', ') }}</template><template v-if="x.gagal.length && x.db_gagal.length"> · </template><template v-if="x.db_gagal.length">DB {{ x.db_gagal.join(', ') }}</template></li></ul>
        </details>
        <p class="redup kecil">Metode: PC Backup menarik <code>rsync -aH --delete</code> lewat SSH (kunci khusus, server hanya izinkan baca /home/&lt;user&gt;/ + data user DA), lalu <code>mariadb-dump</code> per DB dialirkan langsung (tanpa berkas di server, ulang 3x bila putus). Inkremental: hanya berkas berubah yang dikirim. Versi lama dijaga snapshot ZFS 23:00 (7 hari). Data = ukuran berkas akun yang diperiksa; laju = data ÷ lama.</p>
      </section>

      <section v-if="bs" class="kartu" :class="{ berjalan: bs.state === 'running' }">
        <div class="kartu-judul">
          <h2><span v-if="bs.state === 'running'" class="denyut" aria-hidden="true" />PC Kantor <span class="pil" :class="statusSistem[0]">{{ statusSistem[1] }}</span></h2>
          <span class="redup">
            Backup sistem 192.168.88.211 · GPG AES256
            · <RouterLink :to="{ path: '/pc-backup/berkas', query: { path: bs.dest || '/srv/backup/pckantor' } }">Buka folder</RouterLink>
          </span>
        </div>
        <div v-if="bs.state === 'running' && bs.progress" class="progres-sistem">
          <p class="perkiraan">
            <strong>{{ bs.progress.perkiraan ? '±' : '' }}{{ bs.progress.persen }}%</strong>
            <span class="redup">{{ FASE[bs.phase] || bs.phase }} ·
              {{ bs.progress.teks || `${ukuranBerkas(bs.progress.done)} dari ±${ukuranBerkas(bs.progress.total)}` }}
              <template v-if="bs.progress.laju"> · {{ bs.progress.laju }}</template>
              <template v-if="bs.progress.eta"> · sisa {{ bs.progress.eta }}</template>
            </span>
          </p>
          <div class="meter jalan" role="progressbar" :aria-valuenow="bs.progress.persen" aria-valuemin="0" aria-valuemax="100"><i :style="{ width: `${bs.progress.persen}%` }" /></div>
          <p v-if="bs.progress.perkiraan" class="redup kecil">Perkiraan dibanding ukuran arsip sukses terakhir.</p>
        </div>
        <div class="blok-server">
          <div>
            <h3>Jadwal</h3>
            <ul class="daftar">
              <li><span>Harian · 02:00</span><span :class="bs.timer_active === false ? 'galat' : 'redup'">{{ bs.timer_active === false ? 'Timer mati' : 'harian/' }}</span></li>
              <li><span>Minggu</span><span class="redup">mingguan/ (hardlink)</span></li>
              <li><span>Berikutnya</span><span class="redup">{{ bs.next_run ? tanggalWaktu(bs.next_run) : '-' }}</span></li>
            </ul>
          </div>
          <div>
            <h3>{{ bs.state === 'running' ? 'Sedang berjalan' : 'Backup terakhir' }}</h3>
            <ul class="daftar">
              <template v-if="bs.state === 'running'">
                <li><span>Tahap</span><span class="redup">{{ FASE[bs.phase] || bs.phase }}</span></li>
                <li><span>Mulai</span><span class="redup">{{ tanggalWaktu(bs.started) }} · {{ durasi(bs.started, Math.floor(Date.now() / 1000)) }}</span></li>
              </template>
              <template v-else>
                <li><span>{{ bs.finished ? tanggalWaktu(bs.finished) : '-' }}</span><span class="redup">{{ bs.duration ? durasi(0, bs.duration) : '' }}</span></li>
                <li><span>Ukuran arsip</span><span class="redup">{{ bs.size ? ukuranBerkas(bs.size) : '-' }}</span></li>
              </template>
              <li><span>Terakhir sukses</span><span class="redup">{{ bs.last_ok ? waktuLalu(bs.last_ok) : '-' }}</span></li>
            </ul>
            <p v-if="bs.error" class="kecil galat">{{ bs.error }}</p>
            <p v-else-if="bs.stale" class="kecil galat">Sukses terakhir lewat 48 jam. Periksa velocity-backup.timer.</p>
          </div>
          <div>
            <h3>Arsip tersimpan</h3>
            <ul class="daftar">
              <li><span>Harian</span><span class="redup">{{ bs.kept?.harian ?? '-' }} (batas 3)</span></li>
              <li><span>Mingguan</span><span class="redup">{{ bs.kept?.mingguan ?? '-' }} (batas 1)</span></li>
              <li><span>Tujuan</span><span class="redup">{{ bs.remote }}:{{ bs.dest }}</span></li>
            </ul>
          </div>
        </div>
      </section>
      <p class="redup diperbarui">Diperbarui {{ waktuLalu(d.diperbarui) }}</p>
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
.meter.waspada i { background: var(--waspada); }
.meter.bahaya i { background: var(--bahaya); }
.galat { color: var(--bahaya); overflow-wrap: anywhere; }
.layanan { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; font-size: 14px; }
.layanan li { display: flex; align-items: center; gap: 8px; }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); }
.titik.baik { background: var(--baik); }
.titik.bahaya { background: var(--bahaya); }
.kartu-judul h2 { display: flex; align-items: center; gap: 10px; }
.kartu-judul a { color: var(--aksen-terang); }
.blok-server { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr)); gap: 18px 28px; }
.blok-server > div { min-width: 0; }
.blok-server h3 { margin: 0 0 8px; font-size: 12px; font-weight: 600; color: var(--teks-3); text-transform: uppercase; letter-spacing: .04em; }
.blok-server p { margin: 6px 0 0; }
.daftar { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; font-size: 14px; }
.daftar li { display: flex; justify-content: space-between; gap: 12px; padding-bottom: 6px; border-bottom: 1px solid var(--garis); }
.daftar li:last-child { border-bottom: 0; padding-bottom: 0; }
.daftar li > :last-child { text-align: right; overflow-wrap: anywhere; }
.daftar a { color: var(--aksen-terang); }
.kecil { font-size: 12px; }
.diperbarui { margin: -6px 0 0; text-align: right; }
.meter-rsync { margin: 6px 0 2px; min-width: 110px; }
.berjalan { border-color: var(--aksen); }
.meter.jalan { height: 8px; }
.meter.jalan i { min-width: 8px; background-image: repeating-linear-gradient(-45deg, rgba(255, 255, 255, .22) 0 8px, transparent 8px 16px), linear-gradient(90deg, var(--aksen), var(--aksen-terang)); background-size: 22.6px 22.6px, 100% 100%; animation: garis 1s linear infinite; }
.denyut { display: inline-block; width: 9px; height: 9px; margin-right: 8px; border-radius: 50%; background: var(--baik); vertical-align: middle; animation: denyut 1.6s ease-out infinite; }
@keyframes garis { to { background-position: 22.6px 0, 0 0; } }
@keyframes denyut { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--baik) 60%, transparent); } 100% { box-shadow: 0 0 0 9px transparent; } }
@media (prefers-reduced-motion: reduce) { .meter.jalan i, .denyut { animation: none; } }
.perkiraan { margin: 0 0 14px; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.perkiraan strong { font-size: 24px; }
.progres-sistem { display: grid; gap: 6px; margin-bottom: 18px; }
.progres-sistem .perkiraan { margin: 0; }
.progres-sistem p.kecil { margin: 0; }
.tabel-gulir { overflow-x: auto; }
.tabel-disk { width: 100%; border-collapse: collapse; font-size: 14px; }
.tabel-disk th { text-align: left; font-size: 12px; font-weight: 600; color: var(--teks-3); padding: 0 12px 8px 0; white-space: nowrap; }
.tabel-disk td { padding: 8px 12px 8px 0; border-top: 1px solid var(--garis); vertical-align: top; }
.berkas-rusak { margin-top: 12px; }
.berkas-rusak ul { margin: 6px 0 0; padding-left: 18px; }
.berkas-rusak code { word-break: break-all; }
.baris-kode { display: block; }
.peringatan.bahaya { border-color: var(--bahaya); background: color-mix(in srgb, var(--bahaya) 10%, transparent); }
.peringatan { margin: 0; padding: 12px 14px; border-radius: var(--radius-kecil); border: 1px solid var(--waspada); background: rgba(232, 181, 74, .1); color: var(--teks); font-size: 14px; }
</style>
