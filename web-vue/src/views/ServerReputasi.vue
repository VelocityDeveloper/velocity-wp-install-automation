<script setup>
// Reputasi IP (sub-menu VelocityGuard): isi ipset `velocityguard_rep` yang di-DROP iptables di tiap server.
// Diisi timer velocityguard-reputasi tiap 15 mnt dari hit WAF "eksploit" yang ditolak; blokir 7 hari, diperpanjang
// tiap kali IP terlihat lagi. Halaman ini hanya baca: /api/servers/reputasi (ringkasan) + /api/servers/reputasi/daftar.
import PilihServer from '../components/PilihServer.vue'
import { ref, computed, watch } from 'vue'
import Ikon from '../components/Ikon.vue'
import { pakaiPolling, tanggalWaktu, angka, waktuLalu } from '../api.js'
import { tabUrl } from '../laravel.js'
import { pilihServer } from '../jenisServer.js'

const ring = pakaiPolling('/api/servers/reputasi', 120000)
const servers = computed(() => ring.data.value?.servers || [])
const pilih = pilihServer()
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || servers.value.find((s) => s.ok) || servers.value[0] || null)

const cariUrl = tabUrl('q', '')
const cari = ref(cariUrl.value)
let tunda = null
watch(cari, (v) => { clearTimeout(tunda); tunda = setTimeout(() => { cariUrl.value = v.trim() }, 400) })
const urut = tabUrl('urut', 'terbaru')
const halaman = ref(1)
watch([cariUrl, urut, () => terpilih.value?.host], () => { halaman.value = 1 })

const urlDaftar = () => (terpilih.value
  ? `/api/servers/reputasi/daftar?server=${encodeURIComponent(terpilih.value.host)}&q=${encodeURIComponent(cariUrl.value)}&urut=${urut.value}&halaman=${halaman.value}`
  : null)
const dft = pakaiPolling(urlDaftar, 300000)
watch(urlDaftar, (u, lama) => {
  if (!u || u === lama) return
  const gantiServer = !lama || !lama.startsWith(`/api/servers/reputasi/daftar?server=${encodeURIComponent(terpilih.value.host)}&`)
  if (gantiServer) dft.data.value = null
  dft.galat.value = null
  dft.muatUlang()
})
const d = computed(() => dft.data.value)
const jumlahHalaman = computed(() => (d.value?.tersaring ? Math.ceil(d.value.tersaring / d.value.per_halaman) : 1))

const URUT = [['terbaru', 'Terakhir diperbarui'], ['hit', 'Hit terbanyak (24 jam)'], ['lama', 'Paling dekat kedaluwarsa'], ['ip', 'Alamat IP']]
const sisaTeks = (s) => (s >= 86400 ? `${Math.floor(s / 86400)} hr ${Math.floor((s % 86400) / 3600)} j` : s >= 3600 ? `${Math.floor(s / 3600)} j ${Math.floor((s % 3600) / 60)} mnt` : `${Math.max(1, Math.floor(s / 60))} mnt`)
const bita = (n) => (n >= 1e9 ? `${(n / 1e9).toLocaleString('id-ID', { maximumFractionDigits: 1 })} GB` : n >= 1e6 ? `${(n / 1e6).toLocaleString('id-ID', { maximumFractionDigits: 1 })} MB` : `${Math.round(n / 1e3).toLocaleString('id-ID')} KB`)
const waktuDetik = (w) => (w ? Math.floor(new Date(w.replace(' ', 'T') + '+07:00').getTime() / 1000) : 0)
const kirimGagal = computed(() => Object.entries(ring.data.value?.kirim || {}).filter(([, v]) => String(v).startsWith('gagal')))
const isiMaks = computed(() => Math.max(0, ...servers.value.filter((s) => s.ok).map((s) => s.isi)))
const sumber = computed(() => Object.fromEntries((ring.data.value?.sumber || []).map((x) => [x.host, x.ip])))
const tren = computed(() => {
  const r = ring.data.value?.riwayat || []
  if (r.length < 2) return null
  const n = r.map((x) => x.jumlah)
  const maks = Math.max(...n, 1)
  const titik = n.map((v, i) => `${((i / (n.length - 1)) * 100).toFixed(2)},${(28 - (v / maks) * 26).toFixed(2)}`).join(' ')
  return { titik, min: Math.min(...n), maks, awal: r[0].waktu }
})
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Reputasi IP <span class="merek-guard">VelocityGuard</span></h1>
        <p class="redup">IP yang diblokir di semua server lewat ipset <code>velocityguard_rep</code> + iptables DROP. Sumbernya serangan eksploit yang ditolak WAF; tiap IP diblokir {{ ring.data.value?.ttl_hari || 7 }} hari dan diperpanjang setiap kali menyerang lagi.</p>
      </div>
    </header>

    <p v-if="ring.galat.value && !ring.data.value" class="pesan-status bahaya">Gagal memuat ringkasan: {{ ring.galat.value.message }}</p>
    <div v-else-if="!ring.data.value" aria-busy="true"><p class="redup" role="status">Memeriksa ipset di tiap server lewat SSH…</p><span v-for="i in 4" :key="i" class="sk sk-baris" /></div>

    <template v-else>
      <section class="kartu ringkas">
        <div class="angka-kotak">
          <span class="redup">IP di daftar</span><b>{{ angka(isiMaks) }}</b>
          <small class="redup">akumulasi {{ ring.data.value.ttl_hari }} hari</small>
        </div>
        <div class="angka-kotak">
          <span class="redup">Aktif menyerang 24 jam</span><b>{{ angka(ring.data.value.jumlah) }}</b>
          <small class="redup">kiriman terakhir {{ ring.data.value.waktu ? waktuLalu(waktuDetik(ring.data.value.waktu)) : '-' }}</small>
        </div>
        <div class="angka-kotak">
          <span class="redup">Paket ditolak</span><b>{{ angka(servers.reduce((a, s) => a + (s.paket || 0), 0)) }}</b>
          <small class="redup">semua server, sejak firewall terakhir dimuat ulang</small>
        </div>
        <div v-if="tren" class="angka-kotak tren">
          <span class="redup">IP aktif per kiriman (24 jam terakhir)</span>
          <svg viewBox="0 0 100 30" preserveAspectRatio="none" role="img" :aria-label="`Tren jumlah IP aktif, terendah ${tren.min}, tertinggi ${tren.maks}`">
            <polyline :points="tren.titik" fill="none" stroke="currentColor" stroke-width="1.5" vector-effect="non-scaling-stroke" />
          </svg>
          <small class="redup">{{ angka(tren.min) }}–{{ angka(tren.maks) }} IP</small>
        </div>
      </section>

      <p v-for="[n, v] in kirimGagal" :key="n" class="pesan-status waspada">Kiriman terakhir ke {{ n }} gagal: {{ v.replace(/^gagal: /, '') }}</p>

      <section class="kartu">
        <h2>Per server</h2>
        <div class="tabel-wadah">
          <table class="tabel">
            <thead><tr><th scope="col">Server</th><th scope="col" class="kanan">Isi daftar</th><th scope="col">Aturan DROP</th><th scope="col" class="kanan">Paket ditolak</th><th scope="col" class="kanan">IP eksploit 24 jam (sumber)</th></tr></thead>
            <tbody>
              <tr v-for="s in servers" :key="s.host">
                <td><b>{{ s.name }}</b></td>
                <template v-if="s.ok">
                  <td class="kanan">{{ angka(s.isi) }}<small v-if="s.isi < isiMaks * 0.9" class="lencana kuning" title="Isi jauh lebih sedikit dari server lain">kurang</small></td>
                  <td><span class="lencana" :class="s.aturan && s.csfpre ? 'hijau' : 'merah'">{{ s.aturan ? (s.csfpre ? 'Aktif' : 'Aktif, csfpre hilang') : 'Tidak aktif' }}</span></td>
                  <td class="kanan">{{ angka(s.paket) }} <small class="redup">· {{ bita(s.bita) }}</small></td>
                  <td class="kanan">{{ sumber[s.host] != null ? angka(sumber[s.host]) : '-' }}</td>
                </template>
                <td v-else colspan="4" class="bahaya-teks">Tidak terjangkau: {{ s.error }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="kartu isi">
        <h2>Daftar IP</h2>
        <div class="alat">
          <PilihServer v-if="servers.length" :servers="servers.filter((s) => s.ok)" :model-value="terpilih?.name" @update:model-value="pilih = $event" />
          <label class="kotak-cari">
            <Ikon nama="cari" :ukuran="16" />
            <input v-model="cari" type="search" placeholder="Cari IP, awalan (45.138.) atau CIDR (45.138.0.0/16)" aria-label="Cari IP">
          </label>
          <label class="urut"><span class="redup">Urut</span>
            <select v-model="urut"><option v-for="[k, l] in URUT" :key="k" :value="k">{{ l }}</option></select>
          </label>
        </div>

        <div v-if="!d && !dft.galat.value" aria-busy="true">
          <p class="redup" role="status">Membaca isi ipset {{ terpilih?.name }} (±15 detik untuk 100 ribu IP)…</p>
          <span v-for="i in 8" :key="i" class="sk sk-baris" />
        </div>
        <p v-else-if="dft.galat.value" class="pesan-status bahaya">Gagal memuat daftar: {{ dft.galat.value.message }}</p>
        <p v-else-if="d.error" class="pesan-status bahaya">{{ d.name || 'Server' }}: {{ d.error }}</p>
        <template v-else>
          <p class="redup jumlah" role="status">
            {{ angka(d.tersaring) }} dari {{ angka(d.total) }} IP di {{ d.name }} · {{ angka(d.aktif_24j) }} aktif 24 jam · data ipset {{ waktuLalu(d.diambil) }}
          </p>
          <p v-if="!d.baris.length" class="redup">{{ cariUrl ? `IP ${cariUrl} tidak ada di daftar reputasi ${d.name}.` : 'Daftar kosong.' }}</p>
          <div v-else class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">IP</th><th scope="col">24 jam terakhir</th><th scope="col">Terakhir diperbarui</th><th scope="col">Lepas otomatis dalam</th></tr></thead>
              <tbody>
                <tr v-for="b in d.baris" :key="b.ip">
                  <td class="nowrap"><code>{{ b.ip }}</code></td>
                  <td>
                    <template v-if="b.aktif_24j"><span class="lencana merah">Aktif</span> <span class="redup">{{ angka(b.hit) }} hit · {{ b.domain }} domain · {{ b.server }} server</span></template>
                    <span v-else class="redup">Tidak terlihat</span>
                  </td>
                  <td class="nowrap"><time :datetime="new Date(b.terlihat * 1000).toISOString()" :title="tanggalWaktu(b.terlihat)">{{ waktuLalu(b.terlihat) }}</time></td>
                  <td class="nowrap">{{ sisaTeks(b.sisa) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <nav v-if="jumlahHalaman > 1" class="halaman-nav" aria-label="Halaman daftar">
            <button type="button" class="tombol garis kecil" :disabled="halaman <= 1" @click="halaman--">‹ Sebelumnya</button>
            <span class="redup">Halaman {{ angka(halaman) }} / {{ angka(jumlahHalaman) }}</span>
            <button type="button" class="tombol garis kecil" :disabled="halaman >= jumlahHalaman" @click="halaman++">Berikutnya ›</button>
          </nav>
          <p class="redup catatan">"Terakhir diperbarui" = saat masa blokir terakhir di-reset ke {{ ring.data.value.ttl_hari }} hari (IP masih tercatat menyerang dalam 24 jam). IP dari daftar putih, Cloudflare, mesin pencari, dan server sendiri tidak pernah masuk. Isi ipset di-cache 5 menit.</p>
        </template>
      </section>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.kartu h2 { margin: 0 0 10px; font-size: 15px; }
.isi { display: grid; gap: 14px; }
.isi h2 { margin: 0; }
.ringkas { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 16px; }
.angka-kotak { display: grid; gap: 2px; align-content: start; }
.angka-kotak > span { font-size: 12.5px; }
.angka-kotak b { font-size: 24px; color: var(--teks-kuat); font-variant-numeric: tabular-nums; }
.angka-kotak small { font-size: 12px; }
.tren svg { width: 100%; height: 34px; color: var(--aksen-terang); }
.alat { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.kotak-cari { flex: 1 1 260px; min-width: 0; display: flex; align-items: center; gap: 8px; color: var(--teks-3); }
.kotak-cari input { flex: 1; min-width: 0; }
.urut { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; }
.urut select { width: auto; }
.jumlah { margin: 0; font-size: 12.5px; }
.tabel-wadah { position: relative; overflow-x: auto; }
.kanan { text-align: right; font-variant-numeric: tabular-nums; }
.kanan .lencana { margin-left: 6px; }
.bahaya-teks { color: var(--bahaya); font-size: 13px; }
.pesan-status.waspada { color: var(--waspada); }
.nowrap { white-space: nowrap; }
.halaman-nav { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.catatan { margin: 0; font-size: 12.5px; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
.sk { --sk-dasar: color-mix(in srgb, var(--kartu-2), var(--teks) 7%); --sk-kilap: color-mix(in srgb, var(--kartu-2), var(--teks) 15%);
  display: block; border-radius: 6px; background: linear-gradient(90deg, var(--sk-dasar) 25%, var(--sk-kilap) 50%, var(--sk-dasar) 75%); background-size: 200% 100%; animation: sk-kilau 1.4s ease-in-out infinite; }
.sk-baris { height: 14px; margin: 14px 0; }
@keyframes sk-kilau { from { background-position: 100% 0; } to { background-position: -100% 0; } }
@media (prefers-reduced-motion: reduce) { .sk { animation: none; } }
</style>
