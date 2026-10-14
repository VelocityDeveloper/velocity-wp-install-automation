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

// Jadwal kirim tiap server diatur di DirectAdmin server itu; yang diketahui dicatat di sini
const JADWAL = { wulan: 'Tiap hari 00:00 · Sen/Rab/Sab ke folder hari, lainnya ke Harian' }
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

      <section class="kartu">
        <div class="kartu-judul">
          <h2>Backup per server</h2>
          <span class="redup">Diperbarui {{ waktuLalu(d.diperbarui) }}</span>
        </div>
        <div class="tabel-wadah">
          <table class="tabel">
            <thead>
              <tr><th>Server</th><th>Kiriman terakhir</th><th>Set backup</th><th>Ukuran</th></tr>
            </thead>
            <tbody>
              <tr v-for="s in pc?.server || []" :key="s.server">
                <td>
                  <strong class="kapital">{{ s.server }}</strong>
                  <span class="kecil">FTP {{ s.user || 'belum ada user' }}</span>
                  <span v-if="JADWAL[s.server]" class="kecil">{{ JADWAL[s.server] }}</span>
                </td>
                <td>
                  <span class="pil" :class="statusKirim(s)[0]">{{ statusKirim(s)[1] }}</span>
                  <template v-if="s.sesi_terakhir">
                    <span class="kecil">{{ tanggalWaktu(s.sesi_terakhir.mulai) }} · {{ durasi(s.sesi_terakhir.mulai, s.sesi_terakhir.selesai) }}</span>
                    <span class="kecil">{{ s.sesi_terakhir.ok }} berkas · {{ ukuranBerkas(s.sesi_terakhir.bytes) }}</span>
                  </template>
                  <span v-for="g in s.gagal_terbaru.slice(-2)" :key="g.t + g.berkas" class="kecil galat">Gagal {{ tanggalWaktu(g.t) }}: {{ g.berkas }}</span>
                </td>
                <td>
                  <span v-if="!s.set.length" class="redup">-</span>
                  <span v-for="x in s.set" :key="x.nama" class="kecil set">
                    <RouterLink :to="{ path: '/pc-backup/berkas', query: { path: `${d.akar}/directadmin/${s.server}/${x.nama}` } }">{{ x.nama }}</RouterLink>
                    {{ x.berkas ? `${x.berkas} berkas · ${ukuranBerkas(x.ukuran)} · ${tanggalWaktu(x.terbaru)}` : 'kosong' }}
                  </span>
                </td>
                <td>
                  {{ s.dataset ? ukuranBerkas(s.dataset.terpakai) : '-' }}
                  <span v-if="s.dataset?.snapshot" class="kecil">termasuk snapshot {{ ukuranBerkas(s.dataset.snapshot) }}</span>
                  <RouterLink class="kecil" :to="{ path: '/pc-backup/berkas', query: { path: `${d.akar}/directadmin/${s.server}` } }">Buka folder</RouterLink>
                </td>
              </tr>
              <tr v-if="pc && !pc.server?.length"><td colspan="4" class="redup">Belum ada server yang dibackup.</td></tr>
            </tbody>
          </table>
        </div>
      </section>
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
.set { display: block; }
a.kecil, .set a { color: var(--aksen-terang); }
.peringatan { margin: 0; padding: 12px 14px; border-radius: var(--radius-kecil); border: 1px solid var(--waspada); background: rgba(232, 181, 74, .1); color: var(--teks); font-size: 14px; }
</style>
