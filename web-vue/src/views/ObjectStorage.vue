<script setup>
// Object Storage media klien (Garage di PC Backup): status Garage, jumlah klien, hampir penuh/penuh, disk dataset, tabel per klien.
// API: GET /api/fm/pc-backup/storage[?segar=1] (services/pc_storage.py, cache 30 dtk). Pindahan panel storage.velocity.ai.id.
import { ref, computed } from 'vue'
import Ikon from '../components/Ikon.vue'
import { pakaiPolling, minta, ukuranBerkas, waktuLalu, angka } from '../api.js'

const st = pakaiPolling('/api/fm/pc-backup/storage', 60000)
const d = computed(() => st.data.value)
const p = computed(() => d.value?.pakai)
const bucket = computed(() => p.value?.bucket || [])
const hampir = computed(() => bucket.value.filter((b) => (b.persen || 0) >= 80 && b.persen < 100).length)
const penuh = computed(() => bucket.value.filter((b) => (b.persen || 0) >= 100).length)
const status = (x) => (x >= 100 ? ['bahaya', 'Penuh'] : x >= 80 ? ['waspada', 'Hampir penuh'] : ['baik', 'Aman'])

const cari = ref('')
const hanyaMasalah = ref(false)
const daftar = computed(() => {
  const q = cari.value.trim().toLowerCase()
  return bucket.value.filter((b) => (!q || b.domain.toLowerCase().includes(q) || b.nama.includes(q)) && (!hanyaMasalah.value || (b.persen || 0) >= 80))
})

const menyegarkan = ref(false)
async function segarkan() {
  menyegarkan.value = true
  try { st.data.value = await minta('/api/fm/pc-backup/storage?segar=1') } catch (e) { st.galat.value = e } finally { menyegarkan.value = false }
}
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Object Storage</h1>
        <p class="redup">Media WordPress klien di Garage (PC Backup), dataset ZFS <code>Backup/s3</code>, dibaca publik lewat <code>media.velocity.ai.id</code>.</p>
      </div>
      <div class="aksi">
        <button type="button" class="tombol garis kecil" :disabled="menyegarkan" @click="segarkan"><Ikon nama="ulang" :ukuran="15" /> {{ menyegarkan ? 'Menyegarkan…' : 'Segarkan' }}</button>
      </div>
    </header>

    <p v-if="st.memuat.value && !d" class="redup">Memuat status object storage…</p>
    <p v-else-if="st.galat.value && !d" class="peringatan" role="alert">Gagal memuat status: {{ st.galat.value.message }}</p>

    <template v-if="d">
      <p v-if="d.galat" class="peringatan" role="alert">PC Backup tidak menjawab lewat SSH: {{ d.galat }}.<template v-if="p"> Data di bawah dari pengecekan terakhir yang berhasil.</template></p>
      <p v-else-if="d.garage_hidup === false" class="peringatan" role="alert">Garage mati: upload media klien tertahan di hosting dan dikirim ulang otomatis saat Garage aktif lagi. Gambar yang belum ada di cache Cloudflare tidak tampil.</p>
      <p v-else-if="p?.galat" class="peringatan" role="alert">Pencatatan terakhir gagal membaca bucket: {{ p.galat }}</p>

      <section class="ringkas" aria-label="Ringkasan">
        <div class="kartu stat">
          <span class="redup">Garage</span>
          <strong :class="d.garage_hidup ? 'baik' : 'bahaya'">{{ d.garage_hidup == null ? '-' : d.garage_hidup ? 'Aktif' : 'Mati' }}</strong>
          <span class="redup">health dicek tiap 1 menit</span>
        </div>
        <div class="kartu stat">
          <span class="redup">Klien</span>
          <strong>{{ angka(bucket.length) }}</strong>
          <span class="redup" v-if="bucket[0]?.max_byte">jatah {{ ukuranBerkas(bucket[0].max_byte) }} / {{ angka(bucket[0].max_objek) }} objek per klien</span>
        </div>
        <div class="kartu stat">
          <span class="redup">Hampir penuh / penuh</span>
          <strong :class="penuh ? 'bahaya' : hampir ? 'waspada' : 'baik'">{{ hampir }} / {{ penuh }}</strong>
          <span class="redup">hampir = ≥80%</span>
        </div>
        <div class="kartu stat" v-if="p?.dataset">
          <span class="redup">Disk dataset</span>
          <strong>{{ (p.dataset.persen ?? 0).toLocaleString('id-ID') }}%</strong>
          <div class="meter" :class="{ waspada: p.dataset.persen >= 80 }" role="meter" :aria-valuenow="p.dataset.persen" aria-valuemin="0" aria-valuemax="100" aria-label="Pemakaian dataset object storage"><i :style="{ width: Math.min(p.dataset.persen, 100) + '%' }" /></div>
          <span class="redup">{{ ukuranBerkas(p.dataset.terpakai) }} dari {{ ukuranBerkas(p.dataset.quota) }}</span>
        </div>
      </section>

      <section class="kartu" aria-labelledby="judul-klien">
        <div class="kartu-judul">
          <h2 id="judul-klien">Pemakaian per klien</h2>
          <div class="saring">
            <input v-model="cari" type="search" placeholder="Cari domain / bucket" aria-label="Cari domain atau bucket" />
            <label><input v-model="hanyaMasalah" type="checkbox" /> Hanya ≥80%</label>
          </div>
        </div>
        <div class="tabel-gulir">
          <table class="tabel">
            <thead><tr><th>Klien</th><th>Status</th><th>Ukuran</th><th>Objek</th><th>Bandwidth hari ini</th></tr></thead>
            <tbody>
              <tr v-for="b in daftar" :key="b.nama">
                <td><b>{{ b.domain }}</b><br><span class="redup kecil">{{ b.nama }}</span></td>
                <td><span class="pil" :class="status(b.persen || 0)[0]">{{ status(b.persen || 0)[1] }}</span></td>
                <td>
                  {{ ukuranBerkas(b.byte) }} / {{ b.max_byte ? ukuranBerkas(b.max_byte) : '∞' }}
                  <div class="meter" :class="{ waspada: b.persen >= 80, bahaya: b.persen >= 100 }" role="meter" :aria-valuenow="b.persen || 0" aria-valuemin="0" aria-valuemax="100" :aria-label="`Pemakaian ${b.domain}`"><i :style="{ width: Math.min(b.persen || 0, 100) + '%' }" /></div>
                  <span class="redup kecil">{{ (b.persen || 0).toLocaleString('id-ID') }}%</span>
                </td>
                <td>{{ angka(b.objek) }} / {{ b.max_objek ? angka(b.max_objek) : '∞' }}</td>
                <td>{{ ukuranBerkas(b.bandwidth_hari_ini) }}</td>
              </tr>
              <tr v-if="!daftar.length"><td colspan="5" class="redup">{{ bucket.length ? 'Tidak ada klien yang cocok.' : 'Belum ada klien.' }}</td></tr>
            </tbody>
          </table>
        </div>
      </section>
      <p class="redup diperbarui">Data pemakaian {{ p?.waktu ? waktuLalu(p.waktu) : '-' }} (dicatat tiap jam) · status {{ waktuLalu(d.diperbarui) }}</p>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; min-width: 0; }
.aksi { display: flex; gap: 8px; flex-wrap: wrap; }
.aksi .tombol { display: inline-flex; align-items: center; gap: 6px; }
.ringkas { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(190px, 100%), 1fr)); gap: 14px; }
.kartu { min-width: 0; }
.stat { display: grid; gap: 6px; align-content: start; }
.stat strong { font-size: 24px; }
.stat strong.baik { color: var(--baik); }
.stat strong.waspada { color: var(--waspada); }
.stat strong.bahaya { color: var(--bahaya); }
.meter { margin-top: 4px; }
.meter.waspada i { background: var(--waspada); }
.meter.bahaya i { background: var(--bahaya); }
.saring { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; font-size: 14px; }
.saring input[type=search] { min-width: 0; width: min(240px, 100%); }
.saring label { display: inline-flex; gap: 6px; align-items: center; }
.kecil { font-size: 12px; }
.diperbarui { margin: -6px 0 0; text-align: right; }
.tabel-gulir { overflow-x: auto; }
.tabel { width: 100%; border-collapse: collapse; font-size: 14px; }
.tabel th { text-align: left; font-size: 12px; font-weight: 600; color: var(--teks-3); padding: 0 12px 8px 0; white-space: nowrap; }
.tabel td { padding: 8px 12px 8px 0; border-top: 1px solid var(--garis); vertical-align: top; }
.peringatan { margin: 0; padding: 12px 14px; border-radius: var(--radius-kecil); border: 1px solid var(--waspada); background: rgba(232, 181, 74, .1); color: var(--teks); font-size: 14px; }
</style>
