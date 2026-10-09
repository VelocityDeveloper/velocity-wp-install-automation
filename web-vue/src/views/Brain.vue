<script setup>
// Claude Brain: graf skill & memory (web/brain, data diperbarui timer brain-data tiap 5 menit).
// Angka ringkas dibaca langsung dari data.json/aktivitas.json; grafnya memakai mode mini halaman /brain/.
import { ref, computed, watch } from 'vue'
import { pakaiPolling, angka } from '../api.js'

const { data: brain, galat } = pakaiPolling('/brain/data.json', 60000)
// aktivitas.json ditulis brain-aktivitas tiap 2 dtk; log realtime ikut membacanya tiap 3 dtk
const { data: akt, galat: galatAkt } = pakaiPolling('/brain/aktivitas.json', 3000)
const toolHariIni = computed(() => Object.values(akt.value?.tools || {}).reduce((a, v) => a + (v.hari || 0), 0))
const stat = computed(() => [
  ['Memory', brain.value?.counts?.memory],
  ['Skill', brain.value?.counts?.skill],
  ['Proyek klien', brain.value?.counts?.proyek],
  ['Tools hari ini', akt.value ? toolHariIni.value : null],
])

// ---- Log realtime: kejadian memory/skill/proyek + pemakaian tool, terbaru di atas ----
const AKSI = {
  baca: ['baca', 'biru'], tulis: ['tulis', 'kuning'], skill: ['skill', 'hijau'], proyek: ['proyek', 'ungu'], tool: ['tool', 'abu'],
}
const SARING = [['', 'Semua'], ['memori', 'Memory & skill'], ['proyek', 'Proyek'], ['tool', 'Tools']]
const saring = ref('')
const sesiDipilih = ref('')
const jeda = ref(false)
const beku = ref([])
const labelSesi = computed(() => Object.fromEntries((akt.value?.sesi || []).map((x) => [x.id, x.label])))
const namaSimpul = (e) => {
  if (e.skill) return e.skill
  if (e.domain) return e.domain
  if (e.id === 'hub:memory') return 'indeks memory'
  return String(e.id || '').replace(/^m:[^/]*\//, '')
}
const semuaLog = computed(() => {
  const a = akt.value
  if (!a) return []
  const ev = (a.events || []).map((e) => ({
    t: e.t, sesi: e.sesi, aksi: e.aksi, target: namaSimpul(e), kelompok: e.aksi === 'proyek' ? 'proyek' : 'memori',
    kunci: `e${e.t}${e.sesi}${e.id || e.skill || e.domain}${e.aksi}`,
  }))
  const al = (a.alat || []).map((e) => ({ t: e.t, sesi: e.sesi, aksi: 'tool', target: e.tool, ket: e.ket, kelompok: 'tool', kunci: `a${e.t}${e.sesi}${e.tool}` }))
  return [...ev, ...al].sort((x, y) => y.t - x.t)
})
// Saat dijeda, daftar dibekukan; data tetap diambil supaya lanjut tanpa lompatan
watch(jeda, (v) => { beku.value = v ? semuaLog.value : [] })
const log = computed(() => (jeda.value ? beku.value : semuaLog.value)
  .filter((e) => (!saring.value || e.kelompok === saring.value) && (!sesiDipilih.value || e.sesi === sesiDipilih.value))
  .slice(0, 150))
const tertunda = computed(() => (jeda.value && beku.value.length ? semuaLog.value.filter((e) => e.t > beku.value[0].t).length : 0))
// Baris yang muncul sesudah halaman dibuka diberi sorot sebentar
const dilihat = new Set()
let awal = true
const baru = ref(new Set())
watch(semuaLog, (l) => {
  const b = new Set()
  for (const e of l) { if (!dilihat.has(e.kunci)) { dilihat.add(e.kunci); if (!awal) b.add(e.kunci) } }
  awal = false
  baru.value = b
})
const jam = (t) => new Date(t * 1000).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const sesiAktif = computed(() => (akt.value?.sesi || []).filter((x) => x.jumlah))

// ---- Cari & fokus: kendalikan graf mini di iframe lewat postMessage (dipasang di web/brain) ----
const frame = ref(null)
const kirimKeGraf = (pesan) => frame.value?.contentWindow?.postMessage(pesan, location.origin)
const JENIS_SIMPUL = { memory: 'memory', skill: 'skill', proyek: 'proyek' }
const q = ref('')
const terpilih = ref(null)
const derajat = computed(() => {
  const d = {}
  for (const l of brain.value?.links || []) if (l.kind !== 'struktur') { d[l.source] = (d[l.source] || 0) + 1; d[l.target] = (d[l.target] || 0) + 1 }
  return d
})
const hasilCari = computed(() => {
  const k = q.value.trim().toLowerCase()
  if (!k || !brain.value) return []
  // Awalan jenis (project-/feedback-…) diabaikan saat menilai; seri diputus oleh jumlah koneksi
  const inti = (n) => n.label.toLowerCase().replace(/^(project|feedback|user|reference)[-_]/, '')
  const skor = (n) => { const l = inti(n); return l === k ? 4 : l.startsWith(k) ? 3 : l.includes(k) ? 2 : 0 }
  return brain.value.nodes
    .filter((n) => JENIS_SIMPUL[n.kind] && (n.label.toLowerCase().includes(k) || (n.desc || '').toLowerCase().includes(k)))
    .sort((a, b) => skor(b) - skor(a) || (derajat.value[b.id] || 0) - (derajat.value[a.id] || 0) || a.label.localeCompare(b.label))
    .slice(0, 8)
})
function fokus(n) {
  terpilih.value = n
  q.value = ''
  kirimKeGraf({ brain: 'fokus', id: n.id })
  frame.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
function lepas() { terpilih.value = null; kirimKeGraf({ brain: 'lepas' }) }
const tandaMasalah = ref(true)
watch(tandaMasalah, (v) => kirimKeGraf({ brain: 'masalah', on: v }))

// ---- Kesehatan memory: data.json (scripts/brain-data) + pemakaian dari aktivitas.json ----
const memori = computed(() => (brain.value?.nodes || []).filter((n) => n.kind === 'memory'))
const kb = (b) => `${(b / 1024).toFixed(b < 10240 ? 1 : 0)} KB`
const indeks = computed(() => {
  // Indeks milik proyek yang benar-benar punya memory (abaikan MEMORY.md kosong)
  const ada = new Set(memori.value.map((m) => m.project))
  return Object.entries(brain.value?.kesehatan?.indeks || {}).filter(([p]) => ada.has(p)).map(([p, v]) => {
    // Terisi = rasio terbesar dari batas baris dan batas byte (Claude Code memotong di mana pun yang lebih dulu)
    const isi = Math.max(v.baris / v.batas_baris, v.batas_byte ? v.byte / v.batas_byte : 0)
    return { proyek: p, ...v, isi, kelas: { kuning: isi >= 0.8, merah: isi >= 1 || !!v.potong_baris } }
  })
})
const kelompokMasalah = computed(() => {
  const k = brain.value?.kesehatan
  if (!k) return []
  const punya = (kode) => memori.value.filter((m) => (m.masalah || []).includes(kode))
  const pakai = akt.value?.pakai || {}
  return [
    { kode: 'tak_diindeks', judul: 'Tidak ada di MEMORY.md', ket: 'Claude tidak tahu memory ini ada. Tambahkan satu baris ke indeks.', item: punya('tak_diindeks'), nilai: () => '' },
    { kode: 'besar', judul: `Terlalu besar (> ${kb(k.batas.besar)})`, ket: 'Tiap dibaca memakan banyak konteks. Ringkas, atau pecah jadi beberapa memory.', item: punya('besar').sort((a, b) => b.size - a.size), nilai: (m) => `${kb(m.size)} · ±${Math.round(m.size / 4000)} rb token` },
    { kode: 'usang', judul: `Project tidak diperbarui > ${k.batas.usang_hari} hari`, ket: 'Cek apakah isinya masih berlaku; hapus atau perbarui.', item: punya('usang'), nilai: (m) => `${Math.floor((Date.now() / 1000 - m.updated) / 86400)} hari` },
    { kode: 'tak_tersentuh', judul: 'Tidak tersentuh belakangan', ket: 'Tidak dibaca atau ditulis sesi mana pun dalam catatan aktivitas (bobot memudar ±3 hari). Kandidat digabung atau dihapus.', item: akt.value ? memori.value.filter((m) => !pakai[m.id]) : [], nilai: (m) => new Date(m.updated * 1000).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' }) },
    { kode: 'nama_ganda', judul: 'Nama ganda', ket: 'Dua berkas dengan name yang sama; tautan [[...]] bisa salah sasaran.', item: punya('nama_ganda'), nilai: (m) => m.file },
    { kode: 'tanpa_deskripsi', judul: 'Tanpa deskripsi', ket: 'Deskripsi dipakai untuk memutuskan memory mana yang relevan.', item: punya('tanpa_deskripsi'), nilai: () => '' },
  ]
})
// Kesehatan memory & Log realtime berbagi satu kartu bertab; default Log realtime
const tabBawah = ref('log')
const jumlahMasalah = computed(() => kelompokMasalah.value.filter((g) => g.kode !== 'tak_tersentuh').reduce((a, g) => a + g.item.length, 0))
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Claude Brain</h1>
        <p class="redup">Graf skill &amp; memory Claude. Sel menyala mengikuti aktivitas sesi yang sedang berjalan.</p>
      </div>
      <a href="/brain/" target="_blank" rel="noopener" class="tombol garis">Buka versi lengkap</a>
    </header>
    <p v-if="galat" class="pesan-status bahaya" role="alert">Data brain tidak terbaca.</p>
    <section class="ringkas" aria-label="Ringkasan">
      <div v-for="[l, n] in stat" :key="l" class="kartu angka"><span class="redup">{{ l }}</span><b>{{ n == null ? '–' : angka(n) }}</b></div>
    </section>
    <section class="kartu graf">
      <div class="alat-graf">
        <div class="cari-wadah">
          <input v-model="q" type="search" placeholder="Cari memory, skill, atau proyek…" aria-label="Cari simpul di graf" autocomplete="off"
                 @keydown.enter.prevent="hasilCari[0] && fokus(hasilCari[0])" @keydown.esc="q = ''">
          <ul v-if="hasilCari.length" class="hasil" role="listbox" aria-label="Hasil pencarian">
            <li v-for="n in hasilCari" :key="n.id">
              <button type="button" @click="fokus(n)"><span class="lencana abu">{{ JENIS_SIMPUL[n.kind] }}</span>{{ n.label }}<span v-if="n.desc" class="d">{{ n.desc }}</span></button>
            </li>
          </ul>
        </div>
        <span v-if="terpilih" class="fokus">Fokus: <b>{{ terpilih.label }}</b> <button type="button" class="tombol garis kecil" @click="lepas">Lepas</button></span>
        <label class="centang"><input v-model="tandaMasalah" type="checkbox"> Tandai memory bermasalah</label>
      </div>
      <iframe ref="frame" src="/brain/?mini=1" title="Graf Claude Brain" loading="lazy" @load="kirimKeGraf({ brain: 'masalah', on: tandaMasalah })" />
      <p class="redup">Cari lalu Enter untuk memusatkan graf ke simpul dan tetangganya · cincin merah putus-putus = memory bermasalah · Ctrl + gulir untuk zoom.</p>
    </section>

    <section class="kartu bertab">
      <div class="kartu-judul">
        <div class="tab" role="tablist" aria-label="Log dan kesehatan memory">
          <button id="tab-log" type="button" role="tab" :aria-selected="tabBawah === 'log'" aria-controls="panel-log" :class="{ aktif: tabBawah === 'log' }" @click="tabBawah = 'log'">
            <span class="titik" :class="{ mati: jeda || galatAkt }" aria-hidden="true" />Log realtime
          </button>
          <button id="tab-sehat" type="button" role="tab" :aria-selected="tabBawah === 'sehat'" aria-controls="panel-sehat" :class="{ aktif: tabBawah === 'sehat' }" @click="tabBawah = 'sehat'">
            Kesehatan memory<span v-if="jumlahMasalah" class="hitung">{{ jumlahMasalah }}</span>
          </button>
        </div>
        <span v-if="tabBawah === 'log'" class="redup">{{ galatAkt ? 'data aktivitas tidak terbaca' : jeda ? 'dijeda' : 'diperbarui tiap 3 detik' }}</span>
        <span v-else-if="brain?.kesehatan" class="redup">{{ jumlahMasalah ? `${jumlahMasalah} perlu dirapikan` : 'semua rapi' }} · {{ memori.length }} memory, total {{ kb(brain.kesehatan.total_byte) }}</span>
      </div>
      <div v-show="tabBawah === 'sehat'" id="panel-sehat" class="sehat" role="tabpanel" aria-labelledby="tab-sehat">
      <p v-if="brain && !brain.kesehatan" class="redup">Data kesehatan belum ada (tunggu brain-data berikutnya).</p>
      <template v-else-if="brain">
        <div v-for="ix in indeks" :key="ix.proyek" class="indeks">
          <div class="baris-indeks">
            <span>Indeks <code>MEMORY.md</code><span v-if="indeks.length > 1" class="redup"> (sesi dari <code>{{ ix.proyek.replace(/-/g, '/') }}</code>)</span></span>
            <b :class="ix.kelas">{{ ix.baris }} / {{ ix.batas_baris }} baris · {{ kb(ix.byte) }}<template v-if="ix.batas_byte"> / {{ kb(ix.batas_byte) }}</template></b>
          </div>
          <div class="meter" :class="ix.kelas" role="meter" :aria-valuenow="Math.round(ix.isi * 100)" aria-valuemin="0" aria-valuemax="100" aria-label="Isi indeks memory terhadap batas muat"><i :style="{ width: `${Math.min(100, ix.isi * 100)}%` }" /></div>
          <p v-if="ix.potong_baris" class="kecil merah"><b>Terpotong mulai baris {{ ix.potong_baris }}</b> — memory di bawahnya tidak terlihat di awal sesi. Pendekkan baris atau pindahkan kelompok entri ke sub-indeks.</p>
          <p class="kecil">Claude Code hanya memuat ±{{ ix.batas_baris }} baris / ±{{ kb(ix.batas_byte || 25000) }} pertama indeks (mana yang lebih dulu); memory di bawahnya tidak terlihat. Satu baris per memory, ≤{{ ix.batas_panjang || 150 }} karakter.</p>
          <p v-if="ix.sub?.length" class="kecil redup">Sub-indeks (dibaca bila perlu): <template v-for="(x, i) in ix.sub" :key="x.berkas"><code>{{ x.berkas }}</code> {{ x.baris }} baris · {{ kb(x.byte) }}<template v-if="i < ix.sub.length - 1">, </template></template></p>
          <p v-if="ix.panjang?.length" class="kecil kuning">{{ ix.panjang.length }} baris lebih dari {{ ix.batas_panjang }} karakter (detail sebaiknya di berkas topik): {{ ix.panjang.slice(0, 8).join(' · ') }}<template v-if="ix.panjang.length > 8"> +{{ ix.panjang.length - 8 }}</template></p>
          <p v-if="ix.dobel?.length" class="kecil merah">{{ ix.dobel.length }} baris berisi lebih dari satu entri: {{ ix.dobel.join(' · ') }}</p>
          <p v-if="ix.mati.length" class="kecil merah">Tautan indeks ke berkas yang tidak ada: <code v-for="b in ix.mati" :key="b">{{ b }} </code></p>
        </div>
        <details v-for="g in kelompokMasalah" :key="g.kode" class="grup" :open="g.item.length > 0 && g.kode !== 'tak_tersentuh'">
          <summary><span>{{ g.judul }}</span><span class="lencana" :class="!g.item.length ? 'hijau' : g.kode === 'tak_tersentuh' ? 'abu' : 'kuning'">{{ g.item.length || 'aman' }}</span></summary>
          <p class="kecil">{{ g.ket }}</p>
          <ul v-if="g.item.length" class="daftar-masalah">
            <li v-for="m in g.item" :key="m.id">
              <button type="button" :title="m.desc || m.file" @click="fokus(m)">{{ m.label }}</button>
              <span class="d">{{ g.nilai(m) }}</span>
            </li>
          </ul>
        </details>
        <p v-if="brain.kesehatan.hantu.length" class="kecil">Tautan [[…]] ke memory yang belum ada: {{ brain.kesehatan.hantu.join(', ') }}</p>
      </template>
      <p v-else class="redup">Memuat…</p>
      </div>
      <div v-show="tabBawah === 'log'" id="panel-log" class="log" role="tabpanel" aria-labelledby="tab-log">
      <div class="saring" role="group" aria-label="Saring log">
        <div class="segmen" role="radiogroup" aria-label="Jenis kejadian">
          <button v-for="[k, l] in SARING" :key="k" type="button" role="radio" :aria-checked="saring === k" :class="{ aktif: saring === k }" @click="saring = k">{{ l }}</button>
        </div>
        <select v-model="sesiDipilih" aria-label="Saring sesi">
          <option value="">Semua sesi</option>
          <option v-for="x in sesiAktif" :key="x.id" :value="x.id">{{ x.label }}{{ x.hidup ? '' : ' (selesai)' }}</option>
        </select>
        <button type="button" class="tombol garis kecil" :aria-pressed="jeda" @click="jeda = !jeda">
          {{ jeda ? `Lanjutkan${tertunda ? ` (+${tertunda})` : ''}` : 'Jeda' }}
        </button>
      </div>
      <div class="gulir" role="log" aria-live="polite" aria-label="Log aktivitas Claude">
        <p v-if="!akt" class="redup">Memuat…</p>
        <p v-else-if="!log.length" class="redup">Belum ada aktivitas yang cocok.</p>
        <ol v-else>
          <li v-for="e in log" :key="e.kunci" :class="{ baru: baru.has(e.kunci) }">
            <time :datetime="new Date(e.t * 1000).toISOString()">{{ jam(e.t) }}</time>
            <span class="lencana" :class="(AKSI[e.aksi] || AKSI.baca)[1]">{{ (AKSI[e.aksi] || AKSI.baca)[0] }}</span>
            <span class="target" :title="e.ket || null"><code>{{ e.target }}</code><span v-if="e.ket" class="ket"> {{ e.ket }}</span></span>
            <span class="sesi">{{ labelSesi[e.sesi] || `sesi ${e.sesi}` }}</span>
          </li>
        </ol>
      </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; min-width: 0; }
.ringkas { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.angka { display: grid; gap: 2px; padding: 14px 18px; }
.angka b { font-size: 26px; font-weight: 700; }
.graf { padding: 10px; }
.graf iframe { display: block; width: 100%; height: calc(100vh - 330px); min-height: 420px; border: 0; border-radius: 12px; background: var(--panel); }
.graf p { margin: 8px 6px 2px; }
.alat-graf { display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; margin: 2px 2px 10px; }
.cari-wadah { position: relative; flex: 1 1 260px; max-width: 420px; }
.cari-wadah input { width: 100%; }
.hasil { position: absolute; z-index: 5; top: calc(100% + 4px); left: 0; right: 0; list-style: none; margin: 0; padding: 4px; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--kartu-2); box-shadow: 0 12px 30px rgba(0, 0, 0, .4); }
.hasil button { all: unset; box-sizing: border-box; display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 2px 8px; align-items: center; width: 100%; padding: 7px 9px; border-radius: 8px; cursor: pointer; font-size: 13px; }
.hasil button:hover, .hasil button:focus-visible { background: var(--aksen-lembut); }
.hasil .d { grid-column: 2; color: var(--teks-3); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fokus { font-size: 13px; color: var(--teks-2); display: inline-flex; align-items: center; gap: 8px; }
.centang { display: inline-flex; align-items: center; gap: 7px; font-size: 13px; color: var(--teks-2); cursor: pointer; }
.centang input { width: auto; accent-color: var(--aksen); }
.sehat .kecil { color: var(--teks-3); font-size: 12.5px; margin: 6px 0 0; }
.sehat .merah { color: var(--bahaya); }
.sehat .kuning { color: var(--waspada); }
.indeks { padding: 12px 14px; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--panel); margin-bottom: 10px; }
.baris-indeks { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; font-size: 13.5px; }
.baris-indeks b { font-variant-numeric: tabular-nums; }
.meter.kuning i { background: var(--waspada); }
.meter.merah i { background: var(--bahaya); }
.grup { border-bottom: 1px solid var(--garis); padding: 10px 2px; }
.grup:last-of-type { border-bottom: 0; }
.grup summary { display: flex; justify-content: space-between; align-items: center; gap: 10px; cursor: pointer; font-size: 14px; font-weight: 600; }
.grup summary:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 2px; border-radius: 4px; }
.daftar-masalah { list-style: none; margin: 8px 0 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 4px 18px; }
.daftar-masalah li { display: flex; justify-content: space-between; gap: 10px; font-size: 13px; padding: 3px 0; min-width: 0; }
.daftar-masalah button { all: unset; cursor: pointer; color: var(--aksen-terang); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.daftar-masalah button:hover { text-decoration: underline; }
.daftar-masalah button:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 2px; border-radius: 3px; }
.daftar-masalah .d { color: var(--teks-3); white-space: nowrap; font-variant-numeric: tabular-nums; }
.tab { display: flex; flex-wrap: wrap; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); }
.tab button { display: inline-flex; align-items: center; gap: 8px; border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 7px 14px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab button:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
.tab .hitung { min-width: 18px; padding: 0 5px; border-radius: 9px; background: var(--waspada); color: #1a1a1a; font-size: 11px; line-height: 18px; text-align: center; }
.titik { width: 8px; height: 8px; border-radius: 50%; background: var(--baik); box-shadow: 0 0 0 0 rgba(52, 199, 123, .6); animation: denyut 2s infinite; }
.titik.mati { background: var(--teks-3); animation: none; }
@keyframes denyut { 70% { box-shadow: 0 0 0 7px rgba(52, 199, 123, 0); } 100% { box-shadow: 0 0 0 0 rgba(52, 199, 123, 0); } }
.saring { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px; }
.saring select { width: auto; min-width: 190px; }
.segmen { display: inline-flex; padding: 3px; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--panel); }
.segmen button { border: 0; background: transparent; color: var(--teks-2); padding: 7px 12px; border-radius: 8px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.segmen button.aktif { background: var(--aksen); color: #fff; }
.segmen button:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: 1px; }
.gulir { max-height: 420px; overflow-y: auto; border: 1px solid var(--garis); border-radius: var(--radius-kecil); background: var(--panel); }
.gulir > p { margin: 0; padding: 14px; }
.gulir ol { list-style: none; margin: 0; padding: 4px 0; font-size: 13px; }
.gulir li { display: grid; grid-template-columns: 70px 64px minmax(0, 1fr) minmax(0, 220px); gap: 10px; align-items: center; padding: 6px 12px; border-bottom: 1px solid var(--garis-halus); }
.gulir li.baru { animation: sorot 2.4s ease-out; }
@keyframes sorot { from { background: var(--aksen-lembut); } to { background: transparent; } }
.gulir time { color: var(--teks-3); font-variant-numeric: tabular-nums; }
.gulir .lencana { text-align: center; }
.lencana.ungu { color: var(--ungu); background: rgba(144, 133, 233, .14); }
.target { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1.4; }
.target code { color: var(--teks); font-size: 12.5px; background: none; padding: 0; }
.target .ket { margin-left: 8px; color: var(--teks-2); }
.sesi { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--teks-2); text-align: right; }
@media (prefers-reduced-motion: reduce) { .titik, .gulir li.baru { animation: none; } }
@media (max-width: 900px) { .ringkas { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px) {
  .gulir li { grid-template-columns: 62px 58px minmax(0, 1fr); }
  .gulir .sesi { grid-column: 3; text-align: left; font-size: 12px; }
}
</style>
