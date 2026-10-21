<script setup>
// Backup: salinan rsync per akun di PC Backup (/srv/backup/rsync/<server>, SSHFS di /mnt/pc-backup/rsync).
// Lihat (File Manager), unduh (folder → .tar.gz, DB → .sql), restore berkas/DB ke server DA.
// API: GET /api/fm/restore?server=&versi=, POST /api/fm/restore, GET /api/fm/restore/tugas[?id=] (services/pc_restore.py).
import { ref, computed, reactive, watch, onBeforeUnmount } from 'vue'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import { pakaiPolling, kirim, minta, ukuranBerkas, tanggalWaktu, waktuLalu } from '../api.js'
import { konfirmasi } from '../konfirmasi.js'

const server = ref('')
const versi = ref('terbaru')
const st = pakaiPolling(() => `/api/fm/restore?server=${encodeURIComponent(server.value)}&versi=${encodeURIComponent(versi.value)}`, 15000)
const d = computed(() => st.data.value)

// Status run rsync (<server>/.status.json). Akun yang sedang disalin diperkirakan dari laju rata-rata sejak akun sebelumnya
// selesai (dibatasi kuota akun itu) supaya bar tetap bergerak saat menyalin akun besar.
const kini = ref(Math.floor(Date.now() / 1000))
const detak = setInterval(() => { kini.value = Math.floor(Date.now() / 1000) }, 5000)
onBeforeUnmount(() => clearInterval(detak))
const TAHAP = { berkas: ['', 'Menyalin berkas'], db: ['', 'Dump database'], selesai: ['baik', 'Selesai'], gagal: ['bahaya', 'Gagal'], terhenti: ['waspada', 'Terhenti'] }
const sr = computed(() => {
  const s = d.value?.status
  if (!s) return null
  const jalan = s.tahap === 'berkas' || s.tahap === 'db'
  const dari = s.terakhir?.[0]?.waktu || s.mulai
  const sebagian = s.tahap === 'berkas' && s.laju ? Math.min(s.kuota_sekarang || 0, (kini.value - dari) * s.laju) : 0
  const byte = Math.min(s.byte_total, s.byte_selesai + sebagian)
  const persen = s.tahap === 'selesai' ? 100 : s.tahap === 'db'
    ? 95 + Math.round((s.db_selesai / (s.db_total || 1)) * 5)
    : Math.min(95, Math.round((byte / (s.byte_total || 1)) * 95))
  const sisa = s.tahap === 'berkas' && s.laju ? (s.byte_total - byte) / s.laju : null
  return { ...s, jalan, byte, persen, eta: sisa != null ? kini.value + Math.round(sisa) : null, lama: (s.selesai || kini.value) - s.mulai }
})
const durasi = (s) => (s < 60 ? `${s} dtk` : s < 3600 ? `${Math.round(s / 60)} mnt` : `${Math.floor(s / 3600)} jam ${Math.round((s % 3600) / 60)} mnt`)
const jam = (t) => new Date(t * 1000).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
watch(d, (x) => { if (x?.server_aktif && !server.value) server.value = x.server_aktif })
watch([server, versi], () => st.muatUlang())
watch(server, () => { versi.value = 'terbaru' })

const cari = ref('')
const akun = computed(() => (d.value?.akun || []).filter((a) => a.user.includes(cari.value.trim().toLowerCase())))
// Puluhan akun per server -> tabel dipaginasi di sisi klien (pola sama dengan Paket.vue).
const UKURAN_HALAMAN = 20
const halaman = ref(1)
const jumlahHalaman = computed(() => Math.max(1, Math.ceil(akun.value.length / UKURAN_HALAMAN)))
const akunHalaman = computed(() => akun.value.slice((halaman.value - 1) * UKURAN_HALAMAN, halaman.value * UKURAN_HALAMAN))
const rentang = computed(() => `${(halaman.value - 1) * UKURAN_HALAMAN + 1}–${Math.min(halaman.value * UKURAN_HALAMAN, akun.value.length)} dari ${akun.value.length} akun`)
watch([cari, server, versi], () => { halaman.value = 1 })
watch(jumlahHalaman, (n) => { if (halaman.value > n) halaman.value = n })
const lamaBackup = (v) => (v.durasi != null ? ` · backup ${v.durasi < 60 ? `${v.durasi} dtk` : `${Math.round(v.durasi / 60)} mnt`}` : '')
const labelVersi = (v) => (v.id === 'terbaru' ? `Terbaru${v.waktu ? ` · ${tanggalWaktu(v.waktu)} · ${waktuLalu(v.waktu)}` : ''}${lamaBackup(v)}` : `Snapshot ${tanggalWaktu(v.waktu)} · ${waktuLalu(v.waktu)}${lamaBackup(v)}`)
const urlUnduh = (p) => `/api/fm/unduh?path=${encodeURIComponent(p)}`
const urlLihat = (p) => ({ path: '/pc-backup/berkas', query: { path: p } })

const PESAN = {
  backup_berjalan: 'Backup masih berjalan.', gagal_mulai: 'PC Backup tidak bisa menjalankan backup.',
  server_tidak_ada: 'Server tidak ditemukan di backup rsync.', versi_tidak_ada: 'Versi backup tidak ditemukan.',
  akun_tidak_ada: 'Akun tidak ada di versi backup ini.', db_tidak_ada: 'Database tidak ada di backup.',
  tidak_ditemukan: 'Path tidak ada di backup akun ini.', path_tidak_valid: 'Path tidak valid.',
  restore_akun_ini_masih_berjalan: 'Restore untuk akun ini masih berjalan.', forbidden: 'Ditolak: buka dari jaringan kantor/Tailscale.',
}
const pesan = (e) => PESAN[e.message] || e.message

// Dialog restore
const form = reactive({ buka: false, akun: null, jenis: 'berkas', path: '', tujuan: 'asli', hapus: false, db: '', galat: '', kirim: false })
function bukaRestore(a, jenis = 'berkas', db = '') {
  Object.assign(form, { buka: true, akun: a, jenis: a.db.length || jenis === 'berkas' ? jenis : 'berkas', path: '', tujuan: 'terpisah', hapus: false, db: db || a.db[0]?.nama || '', galat: '', kirim: false })
}
const ringkasan = computed(() => {
  const a = form.akun
  if (!a) return ''
  const dari = `backup ${versi.value === 'terbaru' ? 'terbaru' : labelVersi(d.value.versi.find((v) => v.id === versi.value) || { id: versi.value })}`
  if (form.jenis === 'db') return `Database ${form.db} di ${server.value} akan diganti isinya dengan ${dari}. Isi sekarang didump dulu ke /root/velocity-cadangan/restore/ di server.`
  const p = `/home/${a.user}${form.path ? '/' + form.path.replace(/^\/+/, '') : ''}`
  if (form.tujuan === 'terpisah') return `${p} dari ${dari} disalin ke folder baru /home/${a.user}/restore-<waktu>/ di ${server.value}. Berkas yang ada tidak diubah.`
  return `${p} di ${server.value} ditimpa dengan ${dari}.${form.hapus ? ' Berkas yang tidak ada di backup DIHAPUS.' : ''} Berkas yang tertimpa${form.hapus ? '/terhapus' : ''} dipindah ke /root/velocity-cadangan/restore/ di server.`
})
async function jalankan() {
  const timpa = form.jenis === 'db' || form.tujuan === 'asli'
  if (timpa && !(await konfirmasi({ judul: 'Jalankan restore?', teks: ringkasan.value, tombol: 'Ya, restore', kelas: 'bahaya' }))) return
  form.kirim = true
  form.galat = ''
  try {
    const r = await kirim('/api/fm/restore', { server: server.value, versi: versi.value, user: form.akun.user, jenis: form.jenis,
      path: form.path.trim(), tujuan: form.tujuan, hapus: form.hapus, db: form.db })
    form.buka = false
    pantau(r.id)
  } catch (e) { form.galat = pesan(e) } finally { form.kirim = false }
}

// Run rsync di luar jadwal (systemctl start backup-rsync-<server> di PC Backup)
const mulaiBackup = reactive({ kirim: false, galat: '' })
async function backupSekarang() {
  if (!(await konfirmasi({ judul: 'Backup sekarang?', teks: `Salin ulang semua akun + dump database ${server.value} ke PC Backup sekarang, di luar jadwal 04:00.`, tombol: 'Ya, backup' }))) return
  mulaiBackup.kirim = true
  mulaiBackup.galat = ''
  try {
    await kirim('/api/fm/restore/backup-sekarang', { server: server.value })
    setTimeout(() => st.muatUlang(), 3000)
  } catch (e) { mulaiBackup.galat = pesan(e) } finally { mulaiBackup.kirim = false }
}

// Tugas restore (berjalan di layanan file-manager; riwayat hilang saat layanan dimulai ulang)
const riwayat = pakaiPolling('/api/fm/restore/tugas', 30000)
const aktif = ref(null)
let timer = null
async function pantau(id) {
  clearTimeout(timer)
  try {
    aktif.value = await minta(`/api/fm/restore/tugas?id=${id}`)
    if (aktif.value.status === 'berjalan') timer = setTimeout(() => pantau(id), 2000)
    else riwayat.muatUlang()
  } catch (e) { aktif.value = { id, status: 'gagal', log: [pesan(e)] } }
}
onBeforeUnmount(() => clearTimeout(timer))
const STATUS = { berjalan: ['', 'Berjalan'], selesai: ['baik', 'Selesai'], gagal: ['bahaya', 'Gagal'] }
const target = (t) => (t.jenis === 'db' ? `DB ${t.db}` : `/home/${t.user}${t.path ? '/' + t.path : ''}${t.tujuan === 'terpisah' ? ' → folder terpisah' : ''}`)
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Backup</h1>
        <p class="redup">Salinan rsync per akun di PC Backup. Lihat isinya, unduh, atau kembalikan berkas &amp; database ke server.</p>
      </div>
      <div class="aksi">
        <RouterLink to="/pc-backup/status" class="tombol garis kecil"><Ikon nama="cadangan" :ukuran="15" /> Status Backup</RouterLink>
        <button type="button" class="tombol garis kecil" @click="st.muatUlang()"><Ikon nama="ulang" :ukuran="15" /> Segarkan</button>
      </div>
    </header>

    <p v-if="st.memuat.value && !d" class="redup">Memuat daftar backup…</p>
    <p v-else-if="st.galat.value && !d" class="peringatan" role="alert">Gagal memuat: {{ st.galat.value.message }}</p>

    <template v-if="d">
      <p v-if="!d.tersambung" class="peringatan" role="alert">PC Backup tidak tersambung (mount SSHFS putus). Daftar mungkin kosong atau usang.</p>
      <p v-else-if="!d.server.length" class="peringatan" role="alert">Belum ada backup rsync di PC Backup.</p>

      <section v-if="sr" class="kartu status-rsync" :class="{ jalan: sr.jalan }" aria-live="polite">
        <div class="kartu-judul">
          <h2><span v-if="sr.jalan" class="denyut" aria-hidden="true" />Status backup · <span class="kapital">{{ sr.server }}</span>
            <span class="pil" :class="TAHAP[sr.tahap]?.[0]">{{ TAHAP[sr.tahap]?.[1] || sr.tahap }}</span></h2>
          <span class="redup">Mulai {{ tanggalWaktu(sr.mulai) }} · {{ durasi(sr.lama) }}<template v-if="!sr.jalan && sr.selesai"> · selesai {{ jam(sr.selesai) }}</template></span>
          <button type="button" class="tombol garis kecil" :disabled="sr.jalan || mulaiBackup.kirim" @click="backupSekarang"><Ikon nama="cadangan" :ukuran="15" /> {{ mulaiBackup.kirim ? 'Memulai…' : 'Backup sekarang' }}</button>
          <p v-if="mulaiBackup.galat" class="galat kecil">{{ mulaiBackup.galat }}</p>
        </div>
        <div class="angka-status">
          <div><span class="redup">Kemajuan</span><strong>{{ sr.persen }}%</strong></div>
          <div><span class="redup">Akun</span><strong>{{ sr.akun_selesai }}/{{ sr.akun_total }}</strong></div>
          <div><span class="redup">Data disalin</span><strong>{{ ukuranBerkas(sr.byte) }}</strong><span class="redup">dari ±{{ ukuranBerkas(sr.byte_total) }}</span></div>
          <div v-if="sr.laju"><span class="redup">Laju rata-rata</span><strong>{{ ukuranBerkas(sr.laju) }}/dtk</strong></div>
          <div v-if="sr.jalan"><span class="redup">Perkiraan selesai</span><strong>{{ sr.eta ? `±${jam(sr.eta)}` : 'Menghitung…' }}</strong><span v-if="sr.eta" class="redup">{{ durasi(sr.eta - kini) }} lagi{{ sr.tahap === 'berkas' ? ', belum termasuk dump DB' : '' }}</span></div>
          <div><span class="redup">Database</span><strong>{{ sr.db_selesai }}/{{ sr.db_total }}</strong><span v-if="sr.db_gagal?.length" class="galat">{{ sr.db_gagal.length }} gagal</span></div>
        </div>
        <div class="meter tebal" :class="{ jalan: sr.jalan, bahaya: sr.tahap === 'gagal', waspada: sr.tahap === 'terhenti' }" role="progressbar" :aria-valuenow="sr.persen" aria-valuemin="0" aria-valuemax="100" aria-label="Kemajuan backup"><i :style="{ width: sr.persen + '%' }" /></div>
        <p class="redup tahap-kini">
          <template v-if="sr.tahap === 'berkas'">Menyalin <strong>{{ sr.akun_sekarang || '…' }}</strong><template v-if="sr.kuota_sekarang"> (±{{ ukuranBerkas(sr.kuota_sekarang) }})</template> · akun ke-{{ sr.akun_selesai + 1 }} dari {{ sr.akun_total }}</template>
          <template v-else-if="sr.tahap === 'db'">Semua berkas tersalin. Dump database {{ sr.db_selesai }} dari {{ sr.db_total }}…</template>
          <template v-else-if="sr.tahap === 'terhenti'">Status tidak diperbarui sejak {{ waktuLalu(sr.diperbarui) }}; proses backup kemungkinan berhenti.</template>
          <template v-else-if="sr.tahap === 'gagal' && sr.akun_selesai >= sr.akun_total">Backup selesai, tapi ada yang gagal<template v-if="sr.gagal?.length">: {{ sr.gagal.length }} akun</template><template v-if="sr.db_gagal?.length"><template v-if="sr.gagal?.length">,</template> {{ sr.db_gagal.length }} database</template>.</template>
          <template v-else-if="sr.tahap === 'gagal'">Proses backup berhenti sebelum selesai.</template>
          <template v-else>Semua akun dan database tersalin.</template>
        </p>
        <p v-if="sr.gagal?.length" class="galat kecil-teks">Akun gagal: {{ sr.gagal.join(', ') }}</p>
        <p v-if="sr.db_gagal?.length" class="galat kecil-teks">DB gagal: {{ sr.db_gagal.join(', ') }}</p>
        <details v-if="sr.terakhir?.length" class="terakhir">
          <summary>Akun terakhir selesai</summary>
          <ul class="riwayat">
            <li v-for="a in sr.terakhir" :key="a.user"><span>{{ a.user }} <span v-if="a.rc && a.rc !== 24" class="galat">rc {{ a.rc }}</span></span><span class="redup">{{ ukuranBerkas(a.byte) }} · {{ durasi(a.detik) }} · {{ jam(a.waktu) }}</span></li>
          </ul>
        </details>
      </section>

      <section v-if="aktif" class="kartu" aria-live="polite">
        <div class="kartu-judul">
          <h2>Restore {{ aktif.user }} <span class="pil" :class="STATUS[aktif.status]?.[0]">{{ STATUS[aktif.status]?.[1] || aktif.status }}</span></h2>
          <button type="button" class="tombol garis kecil" :disabled="aktif.status === 'berjalan'" @click="aktif = null">Tutup</button>
        </div>
        <p v-if="aktif.server" class="redup">{{ target(aktif) }} · {{ aktif.server }} · versi {{ aktif.versi }} · mulai {{ tanggalWaktu(aktif.mulai) }}</p>
        <p v-if="aktif.status === 'selesai' && aktif.cadangan && !(aktif.jenis === 'berkas' && aktif.tujuan === 'terpisah')" class="redup">
          Isi lama dicadangkan di server: <code>{{ aktif.cadangan }}{{ aktif.jenis === 'db' ? '.sql.gz' : '/' }}</code>
        </p>
        <p v-if="aktif.status === 'selesai' && aktif.tujuan === 'terpisah'" class="redup">Hasil di server: <code>{{ aktif.hasil }}</code></p>
        <pre class="log">{{ (aktif.log || []).join('\n') }}</pre>
      </section>

      <section v-if="d.server.length" class="kartu">
        <div class="saring">
          <label class="isian"><span>Server</span>
            <select v-model="server"><option v-for="s in d.server" :key="s" :value="s">{{ s }}</option></select>
          </label>
          <label class="isian"><span>Versi</span>
            <select v-model="versi"><option v-for="v in d.versi" :key="v.id" :value="v.id">{{ labelVersi(v) }}</option></select>
          </label>
          <label class="isian"><span>Cari akun</span><input v-model="cari" type="search" placeholder="nama user DA" spellcheck="false"></label>
        </div>
        <p v-if="d.versi.length < 2" class="redup catatan">Snapshot harian untuk backup rsync belum ada, jadi baru tersedia versi terbaru.</p>

        <div class="tabel-wadah">
          <table class="tabel">
            <thead><tr><th>Akun</th><th>Database</th><th class="sembunyi-hp">Backup</th><th><span class="sr">Aksi</span></th></tr></thead>
            <tbody>
              <tr v-for="a in akunHalaman" :key="a.user">
                <td><strong>{{ a.user }}</strong><span class="kecil">/home/{{ a.user }}</span></td>
                <td>
                  <ul class="db">
                    <li v-for="x in a.db" :key="x.nama">
                      <span>{{ x.nama }} <span class="redup">{{ ukuranBerkas(x.ukuran) }}</span></span>
                      <a :href="urlUnduh(x.path)" class="tautan" :aria-label="`Unduh database ${x.nama}`"><Ikon nama="unduh" :ukuran="14" /> .sql</a>
                      <button type="button" class="tautan" :aria-label="`Restore database ${x.nama}`" @click="bukaRestore(a, 'db', x.nama)"><Ikon nama="database" :ukuran="14" /> Restore</button>
                    </li>
                  </ul>
                  <span v-if="!a.db.length" class="redup">Tanpa database</span>
                </td>
                <td class="sembunyi-hp"><span :title="tanggalWaktu(a.waktu)">{{ waktuLalu(a.waktu) }}</span></td>
                <td>
                  <div class="aksi-baris">
                    <RouterLink :to="urlLihat(a.path)" class="tombol garis kecil"><Ikon nama="berkas" :ukuran="14" /> Lihat</RouterLink>
                    <a :href="urlUnduh(a.path)" class="tombol garis kecil" :aria-label="`Unduh folder ${a.user} (.tar.gz)`"><Ikon nama="unduh" :ukuran="14" /> Unduh</a>
                    <button type="button" class="tombol waspada kecil" @click="bukaRestore(a)"><Ikon nama="ulang" :ukuran="14" /> Restore</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="!akun.length" class="redup">Tidak ada akun{{ cari ? ' yang cocok' : '' }}.</p>
        </div>
        <div v-if="akun.length > UKURAN_HALAMAN" class="paginasi">
          <span class="redup">{{ rentang }}</span>
          <span>
            <button type="button" class="tombol garis kecil" :disabled="halaman <= 1" @click="halaman--">Sebelumnya</button>
            <button type="button" class="tombol garis kecil" :disabled="halaman >= jumlahHalaman" @click="halaman++">Berikutnya</button>
          </span>
        </div>
        <p class="redup catatan">Unduh folder dialirkan langsung sebagai .tar.gz, jadi akun besar butuh beberapa menit sebelum unduhan selesai. Untuk satu berkas atau subfolder, buka lewat Lihat.</p>
      </section>

      <section v-if="riwayat.data.value?.tugas?.length" class="kartu">
        <div class="kartu-judul"><h2>Riwayat restore</h2><span class="redup">sejak layanan dimulai</span></div>
        <ul class="riwayat">
          <li v-for="t in riwayat.data.value.tugas" :key="t.id">
            <span><span class="pil" :class="STATUS[t.status]?.[0]">{{ STATUS[t.status]?.[1] }}</span> {{ t.server }}/{{ t.user }} · {{ target(t) }}</span>
            <span class="redup">{{ tanggalWaktu(t.mulai) }} · <button type="button" class="tautan" @click="pantau(t.id)">Log</button></span>
          </li>
        </ul>
      </section>
    </template>

    <Dialog :buka="form.buka" :judul="`Restore ${form.akun?.user || ''}`" lebar="560px" @tutup="form.buka = false">
      <form v-if="form.akun" class="form-restore" @submit.prevent="jalankan">
        <fieldset class="pilihan">
          <legend>Yang dikembalikan</legend>
          <label class="centang"><input v-model="form.jenis" type="radio" value="berkas"> Berkas</label>
          <label class="centang"><input v-model="form.jenis" type="radio" value="db" :disabled="!form.akun.db.length"> Database</label>
        </fieldset>

        <template v-if="form.jenis === 'berkas'">
          <label class="isian"><span>Path di dalam /home/{{ form.akun.user }}</span>
            <input v-model="form.path" placeholder="kosong = seluruh akun, mis. public_html/wp-content/uploads" spellcheck="false">
            <small>Folder atau satu berkas. Cek path-nya lewat tombol Lihat.</small>
          </label>
          <fieldset class="pilihan kolom">
            <legend>Tujuan</legend>
            <label class="centang"><input v-model="form.tujuan" type="radio" value="terpisah"> Salin ke folder terpisah <span class="redup">/home/{{ form.akun.user }}/restore-&lt;waktu&gt;/, situs tidak berubah</span></label>
            <label class="centang"><input v-model="form.tujuan" type="radio" value="asli"> Timpa di lokasi asli <span class="redup">berkas yang tertimpa dicadangkan</span></label>
            <label v-if="form.tujuan === 'asli'" class="centang anak"><input v-model="form.hapus" type="checkbox"> Hapus berkas yang tidak ada di backup <span class="redup">(ikut dicadangkan)</span></label>
          </fieldset>
        </template>
        <label v-else class="isian"><span>Database</span>
          <select v-model="form.db"><option v-for="x in form.akun.db" :key="x.nama" :value="x.nama">{{ x.nama }} ({{ ukuranBerkas(x.ukuran) }})</option></select>
          <small>Dump sekarang disimpan dulu di server, baru isi backup diimpor.</small>
        </label>

        <p class="ringkasan">{{ ringkasan }}</p>
        <p v-if="form.galat" class="pesan-status bahaya" role="alert">{{ form.galat }}</p>
        <div class="aksi-dialog">
          <button type="button" class="tombol garis" @click="form.buka = false">Batal</button>
          <button type="submit" class="tombol" :class="{ bahaya: form.jenis === 'db' || form.tujuan === 'asli' }" :disabled="form.kirim">{{ form.kirim ? 'Memulai…' : 'Jalankan restore' }}</button>
        </div>
      </form>
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; min-width: 0; }
.paginasi { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.paginasi span:last-child { display: flex; gap: 8px; }
.aksi, .aksi-baris { display: flex; gap: 8px; flex-wrap: wrap; }
.aksi .tombol, .aksi-baris .tombol { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; }
.aksi-baris { justify-content: flex-end; }
.kartu { min-width: 0; }
.saring { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr)); gap: 12px; margin-bottom: 14px; }
.catatan { margin: 0 0 12px; }
.tabel-wadah + .catatan { margin: 12px 0 0; }
.db { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
.db li { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; }
.tautan { display: inline-flex; align-items: center; gap: 4px; border: 0; padding: 0; background: none; font: inherit; font-size: 13px; color: var(--aksen-terang); cursor: pointer; text-decoration: none; }
.tautan:hover { color: var(--teks-kuat); }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.log { margin: 10px 0 0; max-height: 320px; overflow: auto; padding: 12px; border-radius: var(--radius-kecil); background: var(--kartu-2); font-size: 12px; white-space: pre-wrap; overflow-wrap: anywhere; }
code { overflow-wrap: anywhere; }
.riwayat { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; font-size: 14px; }
.riwayat li { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 12px; padding-bottom: 8px; border-bottom: 1px solid var(--garis); }
.riwayat li:last-child { border-bottom: 0; padding-bottom: 0; }
.form-restore { display: grid; gap: 14px; }
.pilihan { border: 0; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px 18px; }
.pilihan.kolom { flex-direction: column; }
.pilihan legend { padding: 0; margin-bottom: 6px; font-size: 13px; font-weight: 600; color: var(--teks-2); }
.centang { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 8px; font-size: 14px; }
.centang input { align-self: center; width: auto; min-height: 0; }
.centang.anak { margin-left: 26px; }
.ringkasan { margin: 0; padding: 10px 12px; border-radius: var(--radius-kecil); background: var(--kartu-2); font-size: 13px; color: var(--teks-2); overflow-wrap: anywhere; }
.kapital { text-transform: capitalize; }
.galat { color: var(--bahaya); overflow-wrap: anywhere; }
.kecil-teks { margin: 6px 0 0; font-size: 13px; }
.status-rsync.jalan { border-color: var(--aksen); }
.status-rsync .kartu-judul h2 { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 10px; }
.angka-status { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(140px, 100%), 1fr)); gap: 12px 18px; margin-bottom: 14px; }
.angka-status > div { display: grid; gap: 2px; min-width: 0; }
.angka-status strong { font-size: 20px; }
.meter.tebal { height: 10px; }
.meter.jalan i { min-width: 10px; background-image: repeating-linear-gradient(-45deg, rgba(255, 255, 255, .22) 0 8px, transparent 8px 16px), linear-gradient(90deg, var(--aksen), var(--aksen-terang)); background-size: 22.6px 22.6px, 100% 100%; animation: garis 1s linear infinite; }
.meter.bahaya i { background: var(--bahaya); }
.meter.waspada i { background: var(--waspada); }
.tahap-kini { margin: 10px 0 0; font-size: 13.5px; }
.tahap-kini strong { color: var(--teks); }
.terakhir { margin-top: 12px; }
.terakhir summary { cursor: pointer; font-size: 13px; color: var(--teks-2); margin-bottom: 8px; }
.denyut { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: var(--baik); animation: denyut 1.6s ease-out infinite; }
@keyframes garis { to { background-position: 22.6px 0, 0 0; } }
@keyframes denyut { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--baik) 60%, transparent); } 100% { box-shadow: 0 0 0 9px transparent; } }
@media (prefers-reduced-motion: reduce) { .meter.jalan i, .denyut { animation: none; } }
@media (max-width: 700px) {
  .tabel thead { display: none; }
  .tabel tr { display: grid; gap: 10px; padding: 12px 0; border-bottom: 1px solid var(--garis); }
  .tabel tr:last-child { border-bottom: 0; }
  .tabel td { padding: 0; border: 0; }
  .aksi-baris { justify-content: flex-start; }
}
.peringatan { margin: 0; padding: 12px 14px; border-radius: var(--radius-kecil); border: 1px solid var(--waspada); background: rgba(232, 181, 74, .1); color: var(--teks); font-size: 14px; }
</style>
