<script setup>
// Package Manager: tema & plugin dari API Velocity (api.velocitydeveloper.co), zip tersinkron ke installer.
import { ref, computed, onMounted } from 'vue'
import Ikon from '../components/Ikon.vue'
import { ukuranBerkas, tanggalWaktu } from '../api.js'

const PAKAI = ['velocity', 'velocity-addons'] // dipasang installer di setiap situs
const data = ref(null)
const galat = ref('')
const menyinkron = ref(false)
const cari = ref('')

async function muat(sinkron) {
  galat.value = ''
  menyinkron.value = !!sinkron
  try {
    // Kolom `error` di sini = sebagian sinkron gagal; datanya tetap valid, jadi ditampilkan sebagai peringatan
    const r = await fetch(sinkron ? '/api/packages/sync' : '/api/packages', { method: sinkron ? 'POST' : 'GET', cache: 'no-store' })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    data.value = await r.json()
  } catch (e) {
    galat.value = `API tidak tersedia: ${e.message}`
  } finally {
    menyinkron.value = false
  }
}
onMounted(() => muat(false))

const sumberZip = (p) => !p.ada ? ['Belum ada', 'merah'] : p.source === 'api' ? ['Dari API', 'hijau'] : p.source === 'github' ? ['Dari GitHub', 'biru'] : ['Unggahan lama', 'kuning']
const jenisTema = (t) => t === 'wp_theme' ? 'Tema induk' : t === 'wp_theme_child' ? 'Child theme' : t || '-'
const tautanSumber = (x) => (x.github_url || x.package_file_url || x.package_external_url || '').replace(/\.git$/, '')
const labelSumber = (url) => { const l = url.replace(/^https:\/\/(www\.)?/, ''); return l.length > 44 ? `${l.slice(0, 41)}…` : l }

const saring = (daftar) => {
  const k = cari.value.trim().toLowerCase()
  return k ? daftar.filter((x) => [x.name, x.slug, x.paket].some((v) => String(v || '').toLowerCase().includes(k))) : daftar
}
const tema = computed(() => saring(data.value?.themes || []))
const plugin = computed(() => saring(data.value?.plugins || []))
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Paket</h1>
        <p class="redup">Tema &amp; plugin dikelola di API Velocity (api.velocitydeveloper.co). Versi baru otomatis dipakai installer, dicek tiap 10 menit.</p>
      </div>
      <button type="button" class="tombol" :disabled="menyinkron" @click="muat(true)"><Ikon nama="ulang" :ukuran="18" />{{ menyinkron ? 'Menyinkronkan…' : 'Sinkron sekarang' }}</button>
    </header>

    <p v-if="galat" class="pesan-status bahaya" role="alert">{{ galat }}</p>
    <p v-else-if="data" class="pesan-status" :class="{ bahaya: data.error }">
      <template v-if="data.error">Sebagian sinkron gagal (zip terakhir tetap dipakai): {{ data.error }} · </template>
      Cek API terakhir: {{ tanggalWaktu(data.synced_at) }}
    </p>

    <section class="kartu" aria-labelledby="judul-installer">
      <div class="kartu-judul"><h2 id="judul-installer">Dipakai installer</h2><span class="redup">tembolok zip: /var/lib/velocity/packages/</span></div>
      <p v-if="!data && !galat" class="redup">Memuat…</p>
      <div v-else-if="data" class="tabel-wadah">
        <table class="tabel">
          <thead><tr><th>Slug</th><th>Versi</th><th>Status zip</th><th class="sembunyi-hp">Ukuran</th><th class="sembunyi-hp">Tersinkron</th></tr></thead>
          <tbody>
            <tr v-for="p in data.installer" :key="p.slug">
              <td><b>{{ p.slug }}</b> <span class="lencana abu">{{ p.type }}</span></td>
              <td>{{ p.version || '-' }}</td>
              <td><span class="lencana" :class="sumberZip(p)[1]">{{ sumberZip(p)[0] }}</span></td>
              <td class="sembunyi-hp">{{ p.size ? ukuranBerkas(p.size) : '-' }}</td>
              <td class="sembunyi-hp">{{ tanggalWaktu(p.added_at) }}</td>
            </tr>
            <tr v-if="!data.installer?.length"><td colspan="5" class="redup">Belum ada paket.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <div class="cari">
      <input v-model="cari" type="search" placeholder="Cari tema atau plugin (nama, slug, paket)…" aria-label="Cari tema atau plugin">
    </div>

    <section class="kartu" aria-labelledby="judul-tema">
      <div class="kartu-judul"><h2 id="judul-tema">Tema di API</h2><span class="redup">{{ tema.length }} tema</span></div>
      <p v-if="!data && !galat" class="redup">Memuat…</p>
      <div v-else-if="data" class="tabel-wadah">
        <table class="tabel">
          <thead><tr><th>Nama</th><th>Versi</th><th class="sembunyi-hp">Jenis</th><th class="sembunyi-hp">Paket</th><th class="sembunyi-hp">Sumber</th></tr></thead>
          <tbody>
            <tr v-for="t in tema" :key="t.id || t.slug">
              <td><b>{{ t.name || t.slug }}</b> <span v-if="PAKAI.includes(t.slug)" class="lencana biru" title="Dipasang oleh installer">INSTALLER</span><span class="kecil">{{ t.slug }}</span></td>
              <td>{{ t.version || '-' }}</td>
              <td class="sembunyi-hp">{{ jenisTema(t.type) }}</td>
              <td class="sembunyi-hp">{{ t.paket || '-' }}</td>
              <td class="sembunyi-hp"><a v-if="tautanSumber(t)" :href="tautanSumber(t)" target="_blank" rel="noopener noreferrer">{{ labelSumber(tautanSumber(t)) }}</a><span v-else class="redup">-</span></td>
            </tr>
            <tr v-if="!tema.length"><td colspan="5" class="redup">{{ cari ? 'Tidak ada tema yang cocok.' : 'API tema tidak terjangkau.' }}</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="kartu" aria-labelledby="judul-plugin">
      <div class="kartu-judul"><h2 id="judul-plugin">Plugin di API</h2><span class="redup">{{ plugin.length }} plugin</span></div>
      <p v-if="!data && !galat" class="redup">Memuat…</p>
      <div v-else-if="data" class="tabel-wadah">
        <table class="tabel">
          <thead><tr><th>Nama</th><th>Versi</th><th class="sembunyi-hp">Butuh</th><th class="sembunyi-hp">Sumber</th></tr></thead>
          <tbody>
            <tr v-for="p in plugin" :key="p.id || p.slug">
              <td><b>{{ p.name || p.slug }}</b> <span v-if="PAKAI.includes(p.slug)" class="lencana biru" title="Dipasang oleh installer">INSTALLER</span><span class="kecil">{{ p.slug }}</span></td>
              <td>{{ p.version || '-' }}</td>
              <td class="sembunyi-hp">{{ p.requires_php ? `PHP ${p.requires_php}` : '-' }}{{ p.requires ? ` · WP ${p.requires}` : '' }}</td>
              <td class="sembunyi-hp"><a v-if="tautanSumber(p)" :href="tautanSumber(p)" target="_blank" rel="noopener noreferrer">{{ labelSumber(tautanSumber(p)) }}</a><span v-else class="redup">-</span></td>
            </tr>
            <tr v-if="!plugin.length"><td colspan="4" class="redup">{{ cari ? 'Tidak ada plugin yang cocok.' : 'API plugin tidak terjangkau.' }}</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; }
.cari input { max-width: 420px; }
</style>
