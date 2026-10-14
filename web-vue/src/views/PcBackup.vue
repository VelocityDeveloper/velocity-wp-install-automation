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
const LAYANAN = { vsftpd: 'FTPS', tailscaled: 'Tailscale', 'zfs-zed': 'ZFS', 'backup-snapshot.timer': 'Snapshot', ufw: 'Firewall' }
const layananMati = computed(() => Object.entries(pc.value?.layanan || {}).filter(([, v]) => v !== 'active').map(([k]) => LAYANAN[k] || k))

// Kiriman dianggap terlambat bila sesi terakhir > 26 jam lalu (jadwal harian + waktu kirim)
function statusKirim(s) {
  const t = s.sesi_terakhir
  if (!t) return ['', 'Belum pernah']
  if (t.gagal && !t.ok) return ['bahaya', 'Gagal']
  if (t.gagal) return ['waspada', `${t.gagal} gagal`]
  if (Date.now() / 1000 - t.selesai > 26 * 3600) return ['waspada', 'Terlambat']
  return ['baik', 'Sukses']
}
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
.peringatan { margin: 0; padding: 12px 14px; border-radius: var(--radius-kecil); border: 1px solid var(--waspada); background: rgba(232, 181, 74, .1); color: var(--teks); font-size: 14px; }
</style>
