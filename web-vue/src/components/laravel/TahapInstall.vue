<script setup>
// Tahap 3 Install: nama aplikasi (folder/database/layanan/repo) ditentukan di sini, bawaan dari relasi On Progress.
import { ref, computed } from 'vue'
import LogLive from './LogLive.vue'
import Ikon from '../Ikon.vue'
import { aksi, pesanGalat, namaSaya, keNama } from '../../laravel.js'
import { konfirmasi } from '../../konfirmasi.js'
import { tanggalWaktu } from '../../api.js'

const props = defineProps({ d: { type: Object, required: true } })
const emit = defineEmits(['ubah'])
const LANGKAH = ['Periksa nama, port, alat', 'laravel new --vue', '.env (Asia/Jakarta, id)', 'Pengaturan aplikasi + footer', 'Database + migrasi', 'Seeder akun uji',
  'CLAUDE.md + DESIGN.md + PRD', 'User sistem, systemd, firewall', 'deploy-dev/prod.sh', 'Repo GitHub + commit', 'Daftar Project Lokal']

const app = ref(props.d.app || props.d.saran_app)
const lanjutAgen = ref(true)
const inst = computed(() => props.d.install || {})
const terinstall = computed(() => ['jalan', 'ok'].includes(inst.value.status))
const SLUG_RE = /^[a-z][a-z0-9-]{1,30}[a-z0-9]$/
const salahApp = computed(() => app.value && (!SLUG_RE.test(app.value) || app.value.includes('--')) ? 'Huruf kecil, angka, tanda hubung; 3–32 karakter, diawali huruf.' : '')
const pratinjau = computed(() => {
  const s = app.value || 'nama-app'
  return [['Folder', `/home/${s}`], ['Database', s.replace(/-/g, '_')], ['User & layanan', `${s.replace(/-/g, '')} · ${s}-dev, ${s}-queue`],
    ['Repo', `${props.d.github_org}/${s} (privat)`], ['Skrip deploy', `/root/${s}/deploy-dev.sh, deploy-prod.sh`]]
})
const persen = computed(() => Math.round(((inst.value.status === 'ok' ? inst.value.total : Math.max(0, (inst.value.langkah || 1) - 1)) / (inst.value.total || LANGKAH.length)) * 100))
const status = ref({ kelas: '', teks: '' })
async function install() {
  if (!(await konfirmasi({
    judul: `Install ${app.value}?`, tombol: 'Install',
    teks: `Membuat /home/${app.value}, database, user sistem, layanan dev, dan repo privat ${props.d.github_org}/${app.value} (3–5 menit).${lanjutAgen.value ? ' Sesudah selesai, agen Claude langsung mulai mengerjakan fitur.' : ''}`,
  }))) return
  status.value = { kelas: '', teks: '' }
  try {
    const r = await aksi(props.d.slug, 'install', { app: app.value, lanjut_agen: lanjutAgen.value })
    status.value = { kelas: 'baik', teks: `Install dimulai di port ${r.port}.` }
    emit('ubah')
  } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
const alamat = computed(() => inst.value.port ? `http://${location.hostname}:${inst.value.port}/` : '')
</script>

<template>
  <section class="kartu" aria-labelledby="h-inst">
    <div class="kartu-judul"><h2 id="h-inst">Install aplikasi</h2>
      <span v-if="inst.status" class="pil" :class="{ ok: 'baik', jalan: 'waspada', gagal: 'bahaya' }[inst.status]">{{ { ok: 'Terpasang', jalan: 'Berjalan', gagal: 'Gagal' }[inst.status] }}</span>
    </div>

    <p v-if="!d.estimasi_kunci" class="pesan-status">Kunci estimasi dulu di tab Estimasi.</p>

    <template v-if="!terinstall">
      <div class="form">
        <label class="isian">
          <span>Nama aplikasi</span>
          <input v-model="app" maxlength="32" spellcheck="false" :disabled="!d.estimasi_kunci">
          <small v-if="salahApp" class="salah">{{ salahApp }}</small>
          <small v-else>Bawaan dari {{ d.onprogress ? `relasi On Progress (${d.onprogress})` : 'judul — hubungkan relasi On Progress dulu bila sudah ada foldernya' }}.</small>
        </label>
        <dl class="pratinjau"><div v-for="[k, v] in pratinjau" :key="k"><dt>{{ k }}</dt><dd><code>{{ v }}</code></dd></div></dl>
        <label class="centang"><input v-model="lanjutAgen" type="checkbox"> Sesudah install, langsung serahkan ke agen Claude</label>
        <div class="aksi">
          <button type="button" class="tombol" :disabled="!d.estimasi_kunci || !app || !!salahApp || !!d.job || !namaSaya.trim()" @click="install"><Ikon nama="installer" :ukuran="18" /> Run Install</button>
          <button v-if="!namaSaya.trim()" type="button" class="isi-nama" @click="keNama">Isi "Nama Anda" dulu →</button>
          <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
        </div>
      </div>
    </template>

    <template v-if="inst.status">
      <div v-if="inst.status !== 'ok'" class="kemajuan">
        <div class="meter" role="progressbar" :aria-valuenow="persen" aria-valuemin="0" aria-valuemax="100" aria-label="Kemajuan install"><i :style="{ width: persen + '%' }" /></div>
        <span class="redup">Langkah {{ inst.langkah || 1 }}/{{ inst.total || LANGKAH.length }}: {{ LANGKAH[(inst.langkah || 1) - 1] }}</span>
      </div>
      <p v-if="inst.status === 'gagal'" class="pesan-status bahaya">{{ inst.galat }}. Bagian yang sudah dibuat (folder, database, repo) tidak dihapus otomatis — bereskan dulu sebelum install ulang dengan nama yang sama.</p>
      <dl v-if="inst.status === 'ok'" class="pratinjau hasil">
        <div><dt>Aplikasi dev</dt><dd><a :href="alamat" target="_blank" rel="noopener">{{ alamat }}</a></dd></div>
        <div><dt>Repo</dt><dd><a :href="inst.repo" target="_blank" rel="noopener">{{ inst.repo }}</a></dd></div>
        <div><dt>Akun uji</dt><dd><RouterLink to="/projects">kartu Project Lokal</RouterLink></dd></div>
        <div><dt>Selesai</dt><dd>{{ tanggalWaktu(inst.selesai) }}</dd></div>
      </dl>
      <LogLive :id="d.slug" jenis="install" :hidup="d.job?.jenis === 'install'" tinggi="46vh" class="log" />
    </template>
  </section>
</template>

<style scoped>
.form { display: grid; gap: 14px; max-width: 640px; }
.isian .salah { color: var(--bahaya); }
.pratinjau { display: grid; gap: 6px; margin: 0; padding: 12px 14px; border-radius: 12px; background: var(--kartu-2); font-size: 12.5px; }
.pratinjau div { display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 8px; align-items: baseline; }
.pratinjau dt { color: var(--teks-3); }
.pratinjau dd { margin: 0; overflow-wrap: anywhere; }
.hasil { margin-bottom: 12px; font-size: 13.5px; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
.centang { display: flex; align-items: center; gap: 8px; font-size: 13.5px; color: var(--teks-2); cursor: pointer; }
.aksi { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.aksi p { margin: 0; }
.kemajuan { display: grid; gap: 6px; margin: 14px 0 10px; }
.log { margin-top: 10px; }
@media (max-width: 560px) { .pratinjau div { grid-template-columns: minmax(0, 1fr); gap: 0; } }
</style>
