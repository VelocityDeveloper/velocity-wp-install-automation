<script setup>
// Status PC Backup (Ubuntu + ZFS lewat Tailscale): server DirectAdmin MENGIRIM backup lewat FTPS (vsftpd,
// user da-<server>) ke /srv/backup/directadmin/<server>; snapshot ZFS harian menjaga versi lama.
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

// Jadwal kirim dibaca langsung dari backup_crons.list DirectAdmin tiap server (d.da, cache 5 mnt)
const da = (s) => d.value?.da?.[s.server]
const salahTujuan = computed(() => Object.entries(d.value?.da || {}).flatMap(([server, x]) =>
  (x.jadwal || []).filter((j) => !j.ke_pc).map((j) => ({ server, ...j }))))
// Backup yang sedang berjalan di server DA + berkas yang sedang diterima PC Backup (persen per berkas)
const berjalan = computed(() => Object.entries(d.value?.da || {}).filter(([, x]) => x.berjalan).map(([server, x]) => {
  const b = x.berjalan
  const s = pc.value?.server?.find((v) => v.server === server)
  const masuk = b.terkirim ?? (s?.sedang_masuk?.berkas?.endsWith(b.berkas) ? s.sedang_masuk.ukuran : null)
  return { server, ...b, terkirim: masuk, persenBerkas: masuk != null && b.ukuran ? Math.min(100, Math.round((masuk / b.ukuran) * 100)) : null,
    persenUser: b.user_ke ? Math.round(((b.user_ke - 1) / b.user_total) * 100) : null, selesai: s?.sesi_terakhir?.ok, gagal: x.gagal_unggah?.length || 0 }
}))
// Perkiraan selesai: jam (hari ini tanpa tanggal) + sisa waktu
const jamSelesai = (t) => {
  if (!t) return null
  const w = new Date(t * 1000)
  const jam = w.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
  return w.toDateString() === new Date().toDateString() ? jam : `${w.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })} ${jam}`
}
const sisaWaktu = (t) => (t ? durasi(Math.floor(Date.now() / 1000), t) : '')
const laju = (b) => (b ? `${ukuranBerkas(b)}/dtk` : '')
const tujuan = (j) => (j.tujuan === 'ftp' ? `${j.ftp_ip}${j.ftp_path || ''}` : `lokal ${j.ftp_path || ''}`)
// append_to_path=dayofweek: DA menambah nama hari (Inggris) di belakang ftp_path
const HARI_DA = { Sen: 'Monday', Sel: 'Tuesday', Rab: 'Wednesday', Kam: 'Thursday', Jum: 'Friday', Sab: 'Saturday', Min: 'Sunday' }
const folderJadwal = (j) => {
  const p = (j.ftp_path || '/').replace(/\/$/, '')
  return j.append === 'dayofweek' ? j.hari.map((h) => `${p}/${HARI_DA[h] || h}`).join(', ') : p || '/'
}
// Kesehatan HDD: bahaya = SMART gagal / sektor pending / uncorrectable / error ZFS; waspada = sektor realokasi / panas
function statusDisk(x) {
  if (x.sehat === false || x.pending > 0 || x.uncorrect > 0 || x.pool?.galat > 0 || (x.pool && x.pool.status !== 'ONLINE')) return ['bahaya', 'Bermasalah']
  if (x.realloc > 0 || x.suhu >= 50) return ['waspada', 'Waspada']
  if (x.sehat == null) return ['', 'Tak terbaca']
  return ['baik', 'Sehat']
}
const diskBermasalah = computed(() => (pc.value?.disk || []).filter((x) => statusDisk(x)[0] === 'bahaya'))
const LAYANAN = { smartmontools: 'SMART', vsftpd: 'FTPS', tailscaled: 'Tailscale', 'zfs-zed': 'ZFS', 'backup-snapshot.timer': 'Snapshot', ufw: 'Firewall' }
const layananMati = computed(() => Object.entries(pc.value?.layanan || {}).filter(([, v]) => v !== 'active').map(([k]) => LAYANAN[k] || k))

// Kiriman dianggap terlambat bila sesi terakhir > 26 jam lalu (jadwal harian + waktu kirim)
function statusKirim(s) {
  const t = s.sesi_terakhir
  if (!t) return ['', 'Belum pernah']
  // vsftpd hanya mencatat berkas yang sempat tersambung; DA juga mencatat berkas yang tak pernah sampai
  const gagal = Math.max(t.gagal, da(s)?.gagal_unggah?.length || 0)
  if (gagal && !t.ok) return ['bahaya', 'Gagal']
  if (gagal) return ['waspada', `${gagal} gagal`]
  if (Date.now() / 1000 - t.selesai > 26 * 3600) return ['waspada', 'Terlambat']
  return ['baik', 'Sukses']
}

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
        <p class="redup">Server DirectAdmin mengirim backup ke PC Backup lewat FTPS (Tailscale); snapshot ZFS harian menjaga versi lama 7 hari.</p>
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
      <p v-if="salahTujuan.length" class="peringatan" role="alert">
        Jadwal backup belum mengarah ke PC Backup ({{ d.ip_pc }}):
        <template v-for="(j, i) in salahTujuan" :key="j.server + j.id">{{ i ? '; ' : ' ' }}<span class="kapital">{{ j.server }}</span> #{{ j.id }} ({{ j.hari.join('/') }}) ke {{ tujuan(j) }}</template>.
        Ubah di DirectAdmin ▸ Admin Backup/Transfer.
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
          <p class="galat"><b>{{ pc.zfs_rusak.length }} berkas rusak permanen</b> (blok gagal dibaca/checksum, tak bisa diperbaiki karena pool tanpa mirror).</p>
          <ul class="kecil"><li v-for="f in pc.zfs_rusak" :key="f.berkas"><code>{{ f.berkas }}</code><span v-if="!f.aktif" class="redup"> · berkas sudah tak ada, tinggal di snapshot</span><span v-if="f.snapshot.length" class="redup"> · juga di snapshot {{ f.snapshot.join(', ') }}</span></li></ul>
        </div>
      </section>

      <section v-for="b in berjalan" :key="b.server" class="kartu berjalan" aria-live="polite">
        <div class="kartu-judul">
          <h2><span class="denyut" aria-hidden="true" />Backup berjalan · <span class="kapital">{{ b.server }}</span></h2>
          <span class="redup">Mulai {{ b.mulai ? tanggalWaktu(b.mulai) : '-' }}<template v-if="b.mulai"> · {{ durasi(b.mulai, Math.floor(Date.now() / 1000)) }}</template></span>
        </div>
        <p class="perkiraan">
          <span class="redup">Perkiraan selesai</span>
          <strong>{{ b.eta_total ? `±${jamSelesai(b.eta_total)}` : 'Menghitung…' }}</strong>
          <span v-if="b.eta_total" class="redup">{{ sisaWaktu(b.eta_total) }} lagi<template v-if="b.laju_efektif"> · rata-rata {{ laju(b.laju_efektif) }}</template></span>
        </p>
        <div class="kemajuan">
          <div>
            <span class="redup">User {{ b.user_ke ?? '-' }} dari {{ b.user_total }}<template v-if="b.user"> · {{ b.user }}</template></span>
            <div class="meter jalan" role="meter" :aria-valuenow="b.persenUser || 0" aria-valuemin="0" aria-valuemax="100" aria-label="Kemajuan per user"><i :style="{ width: (b.persenUser || 0) + '%' }" /></div>
            <span class="kecil">{{ b.selesai ?? 0 }} berkas terkirim ke PC Backup<template v-if="b.gagal"> · <span class="galat">{{ b.gagal }} gagal</span></template></span>
          </div>
          <div>
            <span class="redup">{{ b.tahap === 'mengunggah' ? 'Mengunggah' : 'Mengemas' }} {{ b.berkas || '-' }}</span>
            <div class="meter jalan" role="meter" :aria-valuenow="b.persenBerkas || 0" aria-valuemin="0" aria-valuemax="100" aria-label="Kemajuan berkas"><i :style="{ width: (b.persenBerkas || 0) + '%' }" /></div>
            <span class="kecil">
              <template v-if="b.terkirim != null">{{ ukuranBerkas(b.terkirim) }} dari {{ ukuranBerkas(b.ukuran) }} ({{ b.persenBerkas }}%)</template>
              <template v-else>{{ ukuranBerkas(b.ukuran) }}{{ b.tahap === 'mengemas' ? ' sejauh ini' : '' }}</template>
              <template v-if="b.tujuan"> · ke {{ b.tujuan === d.ip_pc ? 'PC Backup' : b.tujuan }}</template>
            </span>
            <span v-if="b.eta_berkas" class="kecil">Berkas ini selesai ±{{ jamSelesai(b.eta_berkas) }} ({{ sisaWaktu(b.eta_berkas) }} lagi) · {{ laju(b.laju) }}</span>
          </div>
        </div>
      </section>

      <section v-for="s in pc?.server || []" :key="s.server" class="kartu">
        <div class="kartu-judul">
          <h2><span class="kapital">{{ s.server }}</span> <span class="pil" :class="statusKirim(s)[0]">{{ statusKirim(s)[1] }}</span></h2>
          <span class="redup">
            FTP {{ s.user || 'belum ada user' }}<template v-if="s.dataset"> · {{ ukuranBerkas(s.dataset.terpakai) }}</template>
            · <RouterLink :to="{ path: '/pc-backup/berkas', query: { path: `${d.akar}/directadmin/${s.server}` } }">Buka folder</RouterLink>
          </span>
        </div>
        <div class="blok-server">
          <div>
            <h3>Jadwal</h3>
            <ul class="daftar">
              <li v-for="j in da(s)?.jadwal || []" :key="j.id">
                <span>{{ j.hari.join(', ') }} · {{ j.jam }}</span>
                <span :class="j.ke_pc ? 'redup' : 'galat'">{{ j.ke_pc ? folderJadwal(j) : `ke ${tujuan(j)}` }}</span>
              </li>
            </ul>
            <p v-if="da(s)?.galat" class="kecil galat">Jadwal DA tak terbaca: {{ da(s).galat }}</p>
          </div>
          <div>
            <h3>Kiriman terakhir</h3>
            <ul v-if="s.sesi_terakhir" class="daftar">
              <li><span>{{ tanggalWaktu(s.sesi_terakhir.mulai) }}</span><span class="redup">{{ durasi(s.sesi_terakhir.mulai, s.sesi_terakhir.selesai) }}</span></li>
              <li><span>{{ s.sesi_terakhir.ok }} berkas</span><span class="redup">{{ ukuranBerkas(s.sesi_terakhir.bytes) }}</span></li>
            </ul>
            <p v-else class="redup">Belum ada kiriman.</p>
            <p v-if="s.gagal_terbaru.length" class="kecil galat">Gagal terakhir {{ tanggalWaktu(s.gagal_terbaru.at(-1).t) }}: {{ s.gagal_terbaru.at(-1).berkas }}</p>
            <p v-if="da(s)?.gagal_unggah?.length" class="kecil galat">{{ da(s).gagal_unggah.length }} gagal unggah di backup DA terakhir</p>
          </div>
          <div>
            <h3>Set backup</h3>
            <ul class="daftar">
              <li v-for="x in s.set" :key="x.nama">
                <RouterLink :to="{ path: '/pc-backup/berkas', query: { path: `${d.akar}/directadmin/${s.server}/${x.nama}` } }">{{ x.nama }}</RouterLink>
                <span class="redup" :title="x.terbaru ? `Terbaru ${tanggalWaktu(x.terbaru)}` : ''">{{ x.berkas ? `${x.berkas} berkas · ${ukuranBerkas(x.ukuran)}` : 'kosong' }}</span>
              </li>
            </ul>
            <p v-if="!s.set.length" class="redup">Belum ada set.</p>
          </div>
        </div>
      </section>
      <p v-if="pc && !pc.server?.length" class="redup">Belum ada server yang dibackup.</p>

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
.kapital { text-transform: capitalize; }
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
.berjalan { border-color: var(--aksen); }
.kemajuan { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr)); gap: 18px; }
.meter.jalan { height: 8px; }
.meter.jalan i { min-width: 8px; background-image: repeating-linear-gradient(-45deg, rgba(255, 255, 255, .22) 0 8px, transparent 8px 16px), linear-gradient(90deg, var(--aksen), var(--aksen-terang)); background-size: 22.6px 22.6px, 100% 100%; animation: garis 1s linear infinite; }
.denyut { display: inline-block; width: 9px; height: 9px; margin-right: 8px; border-radius: 50%; background: var(--baik); vertical-align: middle; animation: denyut 1.6s ease-out infinite; }
@keyframes garis { to { background-position: 22.6px 0, 0 0; } }
@keyframes denyut { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--baik) 60%, transparent); } 100% { box-shadow: 0 0 0 9px transparent; } }
@media (prefers-reduced-motion: reduce) { .meter.jalan i, .denyut { animation: none; } }
.perkiraan { margin: 0 0 14px; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.perkiraan strong { font-size: 24px; }
.kemajuan > div { display: grid; gap: 6px; min-width: 0; overflow-wrap: anywhere; }
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
.peringatan.bahaya { border-color: var(--bahaya); background: color-mix(in srgb, var(--bahaya) 10%, transparent); }
.peringatan { margin: 0; padding: 12px 14px; border-radius: var(--radius-kecil); border: 1px solid var(--waspada); background: rgba(232, 181, 74, .1); color: var(--teks); font-size: 14px; }
</style>
