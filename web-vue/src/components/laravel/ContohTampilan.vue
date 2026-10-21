<script setup>
// Contoh tampilan untuk klien (permintaan user 2026-09-30): Claude membuat mockup HTML dari catatan, dokumen klien, dan
// DESIGN/PRD bila sudah ada — platform WordPress: beranda saja; Laravel: landing + dashboard bergaya aplikasi Velocity
// (SIA VD, templates/laravel/gaya-dashboard-vd.md) → pratinjau di sini, lalu diterbitkan ke
// server preview velocity.ai.id (PC kantor lewat Cloudflare Tunnel) supaya PM bisa mengirim tautannya ke klien.
// Revisi (10 Okt, hemat token): aksi `contoh` {mode: 'revisi', halaman, arahan} → Claude menyunting HTML yang ada saja.
// API: aksi `contoh` {arahan}, aksi `terbitkan_contoh`, GET /api/laravel/p/<id>/contoh/<berkas>.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import LogLive from './LogLive.vue'
import Ikon from '../Ikon.vue'
import { aksi, pesanGalat, namaSaya, tabUrl } from '../../laravel.js'
import { waktuLalu } from '../../api.js'
import VersiBrief from './VersiBrief.vue'
import { konfirmasi } from '../../konfirmasi.js'

const props = defineProps({
  d: { type: Object, required: true },
  catatanBerubah: { type: Boolean, default: false },
  simpanCatatan: { type: Function, required: true },
})
const emit = defineEmits(['ubah'])

const c = computed(() => props.d.contoh)
const wp = computed(() => props.d.contoh_platform === 'wordpress')
// Platform dipilih ulang sesudah contoh dibuat → contoh lama tidak sesuai lagi
const bedaPlatform = computed(() => c.value && c.value.platform !== props.d.contoh_platform)
const jalan = computed(() => props.d.job?.jenis === 'contoh')
const adaBahan = computed(() => !!props.d.catatan.trim() || props.catatanBerubah || !!props.d.dokumen?.length)
const bisa = computed(() => adaBahan.value && !props.d.job && !!namaSaya.value.trim())
const halaman = tabUrl('contoh', 'index.html', { boleh: ['index.html', 'dashboard.html'] })
const perangkat = tabUrl('perangkat', 'pc', { boleh: ['pc', 'hp'] })
// Sudah ada contoh → kotak arahan dipakai untuk revisi, jadi mulai kosong (arahan lama tidak diulang tanpa sengaja)
const arahan = ref(props.d.contoh ? '' : props.d.contoh?.arahan || '')
const bukaArahan = ref(false)
const bisaRevisi = computed(() => !!c.value && !bedaPlatform.value)
const targetRevisi = ref('ikut')   // 'ikut' = halaman yang sedang dilihat
const halamanRevisi = computed(() => (targetRevisi.value === 'ikut' ? halaman.value : targetRevisi.value))
const jumlahRevisi = computed(() => c.value?.revisi?.length || 0)
const status = ref({ kelas: '', teks: '' })
const menerbitkan = ref(false)
const tersalin = ref(false)
const src = computed(() => `/api/laravel/p/${props.d.slug}/contoh/${halaman.value}?v=${c.value?.waktu || 0}`)
const terbit = computed(() => c.value?.terbit)
const urlKlien = computed(() => (terbit.value?.ok ? terbit.value.url : ''))

// Tampilan PC dirender selebar 1280px lalu diperkecil mengikuti lebar kartu
const LEBAR_PC = 1280
const TINGGI_PC = 800
const bingkai = ref(null)
const skala = ref(1)
let ro = null
watch(bingkai, (el) => {
  ro?.disconnect()
  if (!el) return
  ro = new ResizeObserver(() => { skala.value = Math.min(1, el.clientWidth / LEBAR_PC) })
  ro.observe(el)
})
onBeforeUnmount(() => ro?.disconnect())

async function revisi() {
  status.value = { kelas: '', teks: '' }
  try {
    await aksi(props.d.slug, 'contoh', { mode: 'revisi', halaman: wp.value ? 'index.html' : halamanRevisi.value, arahan: arahan.value })
    arahan.value = ''
    emit('ubah')
  } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
async function buat() {
  status.value = { kelas: '', teks: '' }
  if (c.value && !(await konfirmasi({ judul: 'Buat ulang dari nol?', tombol: 'Buat ulang', kelas: 'waspada',
    teks: `Claude mendesain ${wp.value ? 'beranda' : 'landing page + dashboard'} baru dari bahan terbaru${arahan.value.trim() ? ' dan arahan Anda' : ''} — desain sekarang diganti seluruhnya. Pakai ini hanya bila brief berubah besar atau arah desain diganti; untuk perubahan bagian tertentu, "Revisi" jauh lebih hemat (±5–10× lebih murah). Tautan klien tetap sama; versi lama disimpan sebagai cadangan.` }))) return
  try {
    if (props.catatanBerubah) await props.simpanCatatan()
    await aksi(props.d.slug, 'contoh', { arahan: arahan.value })
    bukaArahan.value = false
    emit('ubah')
  } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } }
}
async function terbitkan() {
  status.value = { kelas: '', teks: '' }
  menerbitkan.value = true
  try {
    const r = await aksi(props.d.slug, 'terbitkan_contoh')
    status.value = r.ok ? { kelas: 'baik', teks: 'Terbit. Tautan siap dikirim ke klien.' } : { kelas: 'bahaya', teks: r.galat }
    emit('ubah')
  } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } } finally { menerbitkan.value = false }
}
// ACC desain (15 Okt): PM 1 klik (keterangan opsional) + klien menekan "Setujui desain ini" di halaman preview → Install
// terbuka. Kecocokan dengan referensi dinilai otomatis (contoh.kemiripan), PM tak perlu mencocokkan sendiri.
const acc = computed(() => c.value?.acc || {})
const terpasang = computed(() => ['jalan', 'ok'].includes(props.d.install?.status))
const sahPeran = (k) => !!acc.value[k] && !acc.value[k].gugur
const ketPm = ref('')
const peta = computed(() => c.value?.referensi?.peta || [])
const mirip = computed(() => c.value?.kemiripan)
const skorBlok = (x) => mirip.value?.blok?.find((b) => b.halaman === x.halaman && b.blok === x.blok && b.sumber === x.sumber)
const situsRef = computed(() => (props.d.referensi || []).map((r) => r.domain))
// Contoh lama (sebelum 15 Okt) tak punya catatan referensi; contoh baru: referensi disebut tapi tak satu pun dibuka
const refTerlewat = computed(() => situsRef.value.length && (c.value?.referensi ? !c.value.referensi.dibuka?.length : true))
const menyimpanAcc = ref(false)
async function simpanAcc(peran, setuju) {
  status.value = { kelas: '', teks: '' }
  if (!setuju && !(await konfirmasi({ judul: `Batalkan ACC ${peran === 'pm' ? 'PM' : 'klien'}?`, tombol: 'Batalkan', kelas: 'waspada',
    teks: peran === 'pm' ? 'Install terkunci lagi sampai PM ACC ulang.' : 'Install terkunci lagi sampai klien menekan Setujui lagi di halaman preview.' }))) return
  menyimpanAcc.value = true
  try {
    await aksi(props.d.slug, 'acc_desain', { peran, setuju, catatan: ketPm.value })
    ketPm.value = ''
    emit('ubah')
  } catch (e) { status.value = { kelas: 'bahaya', teks: pesanGalat(e) } } finally { menyimpanAcc.value = false }
}
async function salin() {
  try { await navigator.clipboard.writeText(urlKlien.value) } catch { return }
  tersalin.value = true
  setTimeout(() => { tersalin.value = false }, 1800)
}
</script>

<template>
  <section id="contoh-tampilan" class="kartu" aria-labelledby="h-contoh">
    <div class="kartu-judul">
      <h2 id="h-contoh">Contoh tampilan untuk klien</h2>
      <span v-if="jalan" class="pil waspada">sedang dibuat</span>
      <span v-else-if="urlKlien" class="pil baik">terbit</span>
    </div>
    <p v-if="wp" class="redup bantu">Platform <b>WordPress</b>: Claude membuat 1 halaman HTML, yaitu beranda situs, berisi data contoh dari catatan dan dokumen klien. Tautannya bisa dikirim ke klien sebagai gambaran hasil akhir.</p>
    <p v-else class="redup bantu">Platform <b>Laravel</b>: Claude membuat 2 halaman HTML, yaitu landing page dan dashboard bergaya aplikasi Velocity (seperti SIA VD), berisi data contoh dari catatan, dokumen klien, dan DESIGN.md/PRD bila sudah ada. Tautannya bisa dikirim ke klien sebagai gambaran hasil akhir.</p>
    <p v-if="bedaPlatform && !jalan" class="pesan-status waspada">Contoh ini dibuat untuk platform {{ c.platform === 'wordpress' ? 'WordPress' : 'Laravel' }}, padahal platform sekarang {{ wp ? 'WordPress' : 'Laravel' }}. Buat ulang agar sesuai.</p>

    <div v-if="jalan" class="panel" role="status">
      <p class="redup">{{ d.job?.revisi ? 'Claude sedang merevisi contoh tampilan (1–4 menit)' : `Claude sedang mendesain ${wp ? 'beranda situs' : 'landing page + dashboard'} (3–10 menit)` }}, lalu menerbitkannya ke velocity.ai.id.</p>
      <LogLive :id="d.slug" jenis="contoh" hidup tinggi="24vh" />
    </div>

    <template v-else-if="c">
      <div class="tautan">
        <template v-if="urlKlien">
          <Ikon nama="tautan" :ukuran="18" class="ikon" />
          <a :href="urlKlien" target="_blank" rel="noopener" class="url">{{ urlKlien }}</a>
          <button type="button" class="tombol kecil" @click="salin"><Ikon nama="salin" :ukuran="16" /> {{ tersalin ? 'Tersalin' : 'Salin tautan' }}</button>
          <a class="tombol garis kecil" :href="urlKlien" target="_blank" rel="noopener"><Ikon nama="luar" :ukuran="16" /> Buka</a>
        </template>
        <span v-else-if="!c.bisa_terbit" class="redup">Server preview velocity.ai.id belum diatur; contoh baru bisa dilihat di sini.</span>
        <span v-else class="bahaya-teks">Belum terbit{{ terbit?.galat ? `: ${terbit.galat}` : '' }}</span>
        <button v-if="c.bisa_terbit" type="button" class="tombol garis kecil" :disabled="menerbitkan || !!d.job || !namaSaya.trim()" @click="terbitkan">
          {{ menerbitkan ? 'Menerbitkan…' : urlKlien ? 'Terbitkan ulang' : 'Terbitkan ke velocity.ai.id' }}
        </button>
      </div>

      <div class="alat">
        <div class="tab" role="tablist" aria-label="Halaman">
          <button v-for="h in c.halaman" :key="h.nama" type="button" role="tab" :aria-selected="halaman === h.nama" :class="{ aktif: halaman === h.nama }" @click="halaman = h.nama">{{ h.label }}</button>
        </div>
        <div class="tab" role="tablist" aria-label="Perangkat">
          <button type="button" role="tab" :aria-selected="perangkat === 'pc'" :class="{ aktif: perangkat === 'pc' }" @click="perangkat = 'pc'">PC</button>
          <button type="button" role="tab" :aria-selected="perangkat === 'hp'" :class="{ aktif: perangkat === 'hp' }" @click="perangkat = 'hp'">HP</button>
        </div>
        <span class="redup kecil">{{ c.nama_aplikasi }} · dibuat {{ waktuLalu(c.waktu) }}</span>
        <VersiBrief :d="d" jenis="contoh" />
      </div>

      <div v-if="perangkat === 'pc'" ref="bingkai" class="bingkai-pc" :style="{ height: `${TINGGI_PC * skala}px` }">
        <iframe :src="src" :title="`Pratinjau ${halaman}`" sandbox="allow-scripts allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox" loading="lazy"
          :style="{ width: `${LEBAR_PC}px`, height: `${TINGGI_PC}px`, transform: `scale(${skala})` }" />
      </div>
      <div v-else class="bingkai-hp">
        <iframe :src="src" :title="`Pratinjau ${halaman} versi HP`" sandbox="allow-scripts allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox" loading="lazy" />
      </div>

      <div v-if="c.catatan?.length" class="hasil-claude">
        <b>Catatan Claude untuk PM</b>
        <ul><li v-for="(x, i) in c.catatan" :key="i">{{ x }}</li></ul>
      </div>

      <div v-if="!bedaPlatform" class="acc" role="group" aria-labelledby="h-acc">
        <div class="kartu-judul">
          <h3 id="h-acc">ACC desain</h3>
          <span class="pil" :class="acc.sah ? 'baik' : 'waspada'">{{ acc.sah ? 'disetujui PM & klien' : 'belum lengkap' }}</span>
        </div>
        <p class="redup kecil">Wajib sebelum Install: agen meniru referensi klien (bila ada) lalu contoh ini. Contoh dibuat ulang atau direvisi → ACC gugur dan harus diulang.</p>
        <p v-if="refTerlewat" class="pesan-status waspada">
          Bahan menyebut situs referensi <b>{{ situsRef.join(', ') }}</b>, tetapi {{ c.referensi ? 'Claude tidak membukanya' : 'contoh ini dibuat sebelum situs referensi diperiksa otomatis' }}.
          Buat ulang contoh supaya referensi dipetakan dan dinilai otomatis.
        </p>

        <div class="peta">
          <div class="kartu-judul">
            <b>Referensi desain</b>
            <span v-if="mirip" class="pil" :class="mirip.lolos ? 'baik' : 'waspada'">kemiripan {{ mirip.skor }}/100 · {{ mirip.lolos ? 'lolos' : `di bawah ${mirip.ambang}` }}</span>
          </div>
          <p v-if="!peta.length" class="redup kecil">Tidak ada referensi dari klien — contoh tampilan ini menjadi acuan desain.</p>
          <template v-else>
            <p class="redup kecil">Acuan utama agen saat Install. Kemiripan dinilai otomatis; yang belum mirip sudah diperbaiki Claude sampai 2 putaran.</p>
            <ul>
              <li v-for="(x, i) in peta" :key="i">
                <span class="skor" :class="!skorBlok(x) ? '' : skorBlok(x).skor >= mirip.ambang ? 'baik' : 'waspada'">{{ skorBlok(x)?.skor ?? '–' }}</span>
                <span><b>{{ x.blok }}</b> <span class="redup">· {{ x.halaman === 'index.html' ? 'Landing' : 'Dashboard' }}</span><br>
                  <span class="kecil">meniru <a v-if="/^https?:/.test(x.sumber)" :href="x.sumber" target="_blank" rel="noopener">{{ x.sumber.replace(/^https?:\/\//, '') }}</a><template v-else>{{ x.sumber }}</template> — {{ x.unsur }}</span>
                  <span v-if="skorBlok(x)?.beda?.length && skorBlok(x).skor < mirip.ambang" class="redup kecil"><br>Beda: {{ skorBlok(x).beda.join('; ') }}</span></span>
              </li>
            </ul>
            <p v-if="mirip?.ringkasan" class="kecil">{{ mirip.ringkasan }}</p>
          </template>
        </div>

        <div class="langkah-acc">
          <b>1. PM</b>
          <template v-if="sahPeran('pm')">
            <span>✓ {{ acc.pm.oleh }} · {{ waktuLalu(acc.pm.waktu) }}<span v-if="acc.pm.catatan" class="redup"><br>“{{ acc.pm.catatan }}”</span></span>
            <button v-if="!terpasang" type="button" class="tombol garis kecil" :disabled="menyimpanAcc || !namaSaya.trim()" @click="simpanAcc('pm', false)">Batalkan</button>
          </template>
          <template v-else>
            <span v-if="acc.pm?.gugur" class="redup kecil">ACC {{ acc.pm.oleh }} gugur karena contoh berubah.</span>
            <textarea v-model="ketPm" rows="2" maxlength="1000" aria-label="Keterangan PM (opsional)" :disabled="terpasang"
              placeholder="Keterangan untuk webmaster/agen (opsional), mis. warna hijau tua dipertahankan, menu Promo menyusul"></textarea>
            <button type="button" class="tombol kecil" :disabled="menyimpanAcc || terpasang || !namaSaya.trim()" @click="simpanAcc('pm', true)">ACC PM</button>
          </template>
        </div>

        <div class="langkah-acc">
          <b>2. Klien</b>
          <template v-if="sahPeran('klien')">
            <span>✓ {{ acc.klien.oleh }} menekan Setujui di halaman preview · {{ waktuLalu(acc.klien.waktu) }}</span>
            <button v-if="!terpasang" type="button" class="tombol garis kecil" :disabled="menyimpanAcc || !namaSaya.trim()" @click="simpanAcc('klien', false)">Batalkan</button>
          </template>
          <span v-else class="redup">
            <span v-if="acc.klien?.gugur">Persetujuan klien sebelumnya gugur karena contoh berubah. </span>
            {{ urlKlien ? 'Menunggu klien menekan tombol hijau “Setujui desain ini” di tautan preview yang dikirim.' : 'Terbitkan contoh dulu, lalu kirim tautannya ke klien; klien menekan “Setujui desain ini” di halaman itu.' }}
          </span>
        </div>
      </div>
    </template>

    <div v-if="!jalan && bisaRevisi" class="revisi">
      <label for="arahan-revisi"><b>Revisi contoh</b> <span class="redup">· hanya bagian yang Anda sebut yang diubah, desain lain tetap{{ jumlahRevisi ? ` · sudah direvisi ${jumlahRevisi}×` : '' }}</span></label>
      <textarea id="arahan-revisi" v-model="arahan" rows="3" maxlength="2000" :placeholder="wp ? 'Contoh: hero pakai foto produk, tombol WhatsApp lebih besar, tambah seksi testimoni setelah layanan…' : 'Contoh: kartu KPI tambah “Proyek terlambat”, grafik jadi per bulan, hero landing lebih ringkas…'" />
      <p v-if="c.arahan" class="redup kecil">Arahan terakhir: {{ c.arahan }}</p>
      <div class="aksi">
        <label v-if="!wp && c.halaman.length > 1" class="pilih-hal">
          <span class="redup kecil">Ubah</span>
          <select v-model="targetRevisi">
            <option value="ikut">Halaman yang dilihat ({{ halaman === 'dashboard.html' ? 'Dashboard' : 'Landing page' }})</option>
            <option v-for="h in c.halaman" :key="h.nama" :value="h.nama">{{ h.label }} saja</option>
            <option value="semua">Keduanya</option>
          </select>
        </label>
        <button type="button" class="tombol" :disabled="!bisa || !arahan.trim()" @click="revisi">
          <Ikon nama="claude" :ukuran="18" /> Revisi dengan arahan
        </button>
        <button type="button" class="tombol garis" :disabled="!bisa" @click="buat">Buat ulang dari nol</button>
      </div>
    </div>
    <template v-else-if="!jalan">
      <details class="arahan" :open="bukaArahan" @toggle="bukaArahan = $event.target.open">
        <summary>Arahan untuk Claude <span class="redup">(opsional)</span></summary>
        <textarea v-model="arahan" rows="3" maxlength="2000" :placeholder="wp ? 'Contoh: nuansa hangat, tonjolkan paket layanan & testimoni, tombol WhatsApp besar…' : 'Contoh: tonjolkan KPI per proyek di dashboard, landing lebih banyak ilustrasi lapangan…'" />
      </details>
      <div class="aksi">
        <button type="button" :class="c ? 'tombol garis' : 'tombol'" :disabled="!bisa" @click="buat">
          <Ikon nama="claude" :ukuran="18" /> {{ c ? 'Buat ulang contoh tampilan' : 'Buat contoh tampilan' }}
        </button>
        <span v-if="!adaBahan" class="redup kecil">Isi catatan atau unggah dokumen klien dulu.</span>
      </div>
    </template>
    <p v-if="status.teks" class="pesan-status" :class="status.kelas" role="status">{{ status.teks }}</p>
  </section>
</template>

<style scoped>
.bantu { margin: -6px 0 12px; }
.kecil { font-size: 12px; }
.panel { display: grid; gap: 12px; padding: 14px; border-radius: 12px; background: var(--kartu-2); }
.panel > p { margin: 0; }
.tautan { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 10px 12px; border-radius: 12px; background: var(--kartu-2); margin-bottom: 12px; }
.tautan .ikon { flex: none; color: var(--aksen); }
.url { flex: 1 1 220px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; font-size: 13.5px; }
.tautan .tombol { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; }
.bahaya-teks { color: var(--bahaya); font-size: 13px; flex: 1 1 220px; }
.alat { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 5px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.bingkai-pc { position: relative; overflow: hidden; border-radius: 10px; border: 1px solid var(--garis); background: #fff; }
.bingkai-pc iframe { position: absolute; top: 0; left: 0; border: 0; transform-origin: 0 0; }
.bingkai-hp { display: flex; justify-content: center; padding: 14px 0; border-radius: 12px; background: var(--kartu-2); }
.bingkai-hp iframe { width: 390px; max-width: 100%; height: 720px; border: 8px solid #111; border-radius: 28px; background: #fff; }
.hasil-claude { margin-top: 14px; padding: 12px 14px; border-radius: 12px; background: var(--kartu-2); }
.hasil-claude ul { margin: 8px 0 0; padding-left: 18px; display: grid; gap: 4px; color: var(--teks-2); }
.arahan { margin-top: 14px; }
.revisi { margin-top: 14px; display: grid; gap: 8px; }
.revisi > label { font-size: 13.5px; }
.revisi textarea { width: 100%; font: inherit; font-size: 13.5px; }
.revisi > p { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.revisi .aksi { margin-top: 4px; }
.pilih-hal { display: inline-flex; align-items: center; gap: 6px; min-width: 0; }
.pilih-hal select { min-width: 0; max-width: 260px; font: inherit; font-size: 13px; }
.arahan summary { cursor: pointer; font-size: 13.5px; }
.arahan textarea { margin-top: 8px; width: 100%; font: inherit; font-size: 13.5px; }
.aksi { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.aksi .tombol { display: inline-flex; align-items: center; gap: 8px; }
.acc { margin-top: 14px; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--garis); display: grid; gap: 10px; }
.acc h3 { margin: 0; font-size: 15px; }
.acc > p { margin: 0; }
.langkah-acc { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 13.5px; }
.langkah-acc > b { flex: none; width: 64px; }
.langkah-acc input:not([type]) { flex: 1 1 240px; min-width: 0; font: inherit; font-size: 13.5px; }
.langkah-acc textarea { flex: 1 1 280px; min-width: 0; font: inherit; font-size: 13.5px; resize: vertical; }
.peta { display: grid; gap: 6px; padding: 10px 12px; border-radius: 10px; background: var(--latar-2, rgba(127,127,127,.06)); }
.peta p { margin: 0; }
.peta ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; }
.peta li { display: flex; gap: 10px; align-items: flex-start; font-size: 13.5px; }
.peta .skor { flex: none; min-width: 34px; text-align: center; font-weight: 700; border-radius: 8px; padding: 3px 6px; background: rgba(127,127,127,.15); }
.peta .skor.baik { background: #dcfce7; color: #166534; }
.peta .skor.waspada { background: #fef3c7; color: #92400e; }
.pesan-status { margin: 10px 0 0; }
.pesan-status.waspada { color: var(--waspada); margin: 0 0 12px; }
</style>
