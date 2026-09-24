<script setup>
// Model AI installer: pilihan model per fungsi, daftar model (endpoint kompatibel OpenAI), pemakaian token per domain.
// API key tidak pernah ditampilkan.
import { ref, reactive, computed, onMounted } from 'vue'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import { minta, kirim, angka, tanggalWaktu } from '../api.js'
import { konfirmasi } from '../konfirmasi.js'

const data = reactive({ models: [], pemakaian: {}, peran: [], peranTetap: [] })
const memuat = ref(true)
const galat = ref('')
const statusPeran = reactive({})
const statusModel = reactive({})

async function muat() {
  memuat.value = true
  muatToken()
  try {
    const j = await minta('/api/ai/models')
    Object.assign(data, { models: j.models || [], pemakaian: j.pemakaian || {}, peran: j.peran || [], peranTetap: j.peran_tetap || [] })
    galat.value = ''
  } catch (e) { galat.value = e.message }
  finally { memuat.value = false }
}
onMounted(muat)

const modelDefault = computed(() => data.models.find((m) => m.is_default) || data.models[0])
const dipakaiOleh = (m) => data.peran.filter((p) => {
  const pilih = data.pemakaian[p.kunci] || ''
  return data.models.some((x) => x.id === pilih) ? pilih === m.id : modelDefault.value?.id === m.id
}).map((p) => p.label)

async function gantiPeran(p, nilai) {
  statusPeran[p.kunci] = { teks: 'Menyimpan…', kelas: '' }
  try {
    const j = await kirim('/api/ai/models/pemakaian', { peran: p.kunci, model_id: nilai })
    data.pemakaian = j.pemakaian || { ...data.pemakaian, [p.kunci]: nilai }
    statusPeran[p.kunci] = { teks: `Tersimpan: ${nilai || 'ikut default'}.`, kelas: 'baik' }
  } catch (e) {
    statusPeran[p.kunci] = { teks: `Gagal menyimpan: ${e.message}`, kelas: 'bahaya' }
    data.pemakaian = { ...data.pemakaian } // paksa pilihan kembali ke nilai tersimpan
  }
}
const pilihanHilang = (p) => { const v = data.pemakaian[p.kunci]; return v && !data.models.some((m) => m.id === v) }

async function aksiModel(m, aksi) {
  if (aksi === 'hapus') {
    const dipakai = dipakaiOleh(m)
    if (!(await konfirmasi({ judul: `Hapus model ${m.id}?`, teks: dipakai.length ? `Sekarang dipakai: ${dipakai.join(', ')}. Fungsi itu akan ikut model default.` : 'Model ini tidak dipakai fungsi mana pun.', tombol: 'Ya, hapus', kelas: 'bahaya' }))) return
  }
  statusModel[m.id] = { teks: aksi === 'test' ? 'Mengirim pesan uji ke endpoint (bisa sampai 60 detik)…' : 'Menyimpan…', kelas: '', proses: true }
  try {
    if (aksi === 'test') {
      const j = await kirim('/api/ai/models/test', { model_id: m.id })
      statusModel[m.id] = { teks: `Model menjawab: ${String(j.response || '').slice(0, 200)}`, kelas: 'baik' }
    } else if (aksi === 'default') {
      await kirim('/api/ai/models/set-default', { model_id: m.id }); delete statusModel[m.id]; await muat()
    } else if (aksi === 'hapus') {
      await kirim(`/api/ai/models/${encodeURIComponent(m.id)}/delete`, {}); delete statusModel[m.id]; await muat()
    }
  } catch (e) {
    statusModel[m.id] = { teks: `${aksi === 'test' ? 'Test gagal' : 'Gagal'}: ${e.message}`, kelas: 'bahaya' }
  }
}

// Formulir tambah/edit
const form = reactive({ buka: false, edit: false, id: '', model: '', endpoint: '', api_key: '', is_default: false, galat: '', proses: false })
function bukaForm(m) {
  Object.assign(form, m
    ? { buka: true, edit: true, id: m.id, model: m.model !== m.id ? (m.model || '') : '', endpoint: m.endpoint || '', api_key: '', is_default: !!m.is_default, galat: '' }
    : { buka: true, edit: false, id: '', model: '', endpoint: '', api_key: '', is_default: !data.models.length, galat: '' })
}
function isi9router() {
  form.endpoint = 'https://9router.com/api/v1'
  if (!form.edit && !form.id) form.id = '9router'
}
async function simpanForm() {
  const muatan = { id: form.id.trim(), model: form.model.trim(), endpoint: form.endpoint.trim(), api_key: form.api_key.trim(), is_default: form.is_default }
  form.galat = (!/^[A-Za-z0-9._-]+(?:\/[A-Za-z0-9._-]+)*$/.test(muatan.id) || muatan.id.includes('..'))
    ? 'ID model boleh huruf, angka, titik, garis bawah, tanda hubung, dan garis miring (mis. meta-llama/llama-3-70b).'
    : !/^https?:\/\/\S+$/.test(muatan.endpoint) ? 'Endpoint harus URL http(s) lengkap.'
    : (!form.edit && !muatan.api_key) ? 'API key wajib untuk model baru.' : ''
  if (form.galat) return
  form.proses = true
  try { await kirim('/api/ai/models', muatan); form.buka = false; await muat() }
  catch (e) { form.galat = `Gagal menyimpan: ${e.message}` }
  finally { form.proses = false }
}

// Pemakaian token
const token = ref(null)
const galatToken = ref('')
const halaman = ref(1)
const PER_HALAMAN = 10
async function muatToken() {
  try { token.value = await minta('/api/ai/usage'); galatToken.value = '' }
  catch (e) { galatToken.value = e.message }
}
const domain = computed(() => token.value?.domains || [])
const jmlHalaman = computed(() => Math.max(1, Math.ceil(domain.value.length / PER_HALAMAN)))
const domainTampil = computed(() => domain.value.slice((halaman.value - 1) * PER_HALAMAN, halaman.value * PER_HALAMAN))
const total = computed(() => token.value?.total || {})
const labelPeran = (k) => data.peran.find((p) => p.kunci === k)?.label || k
const rincianPeran = (per) => Object.entries(per || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${labelPeran(k)} ${angka(v)}`).join(' · ')
const ringkasSumber = (ps) => ['endpoint', 'claude'].filter((k) => ps?.[k]?.panggilan)
  .map((k) => `${k === 'claude' ? 'Claude' : 'Endpoint'} ${angka(ps[k].panggilan)} req / ${angka(ps[k].total_tokens)} token${k === 'claude' && ps[k].biaya_usd ? ` (setara US$${Number(ps[k].biaya_usd).toFixed(2)})` : ''}`).join(' · ')
const rinci = ref(null)
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>AI Model</h1>
        <p class="redup">Model yang dipanggil installer WordPress: tulisan halaman &amp; artikel, isi contoh desain, pemilihan foto, dan FSE builder. Perubahan berlaku di run installer berikutnya.</p>
      </div>
      <button type="button" class="tombol garis" @click="muat"><Ikon nama="ulang" :ukuran="18" /> Muat ulang</button>
    </header>

    <p v-if="galat" class="pesan-status bahaya" role="alert">Gagal memuat dari API: {{ galat }}</p>

    <section class="kartu" aria-labelledby="judul-peran">
      <div class="kartu-judul"><h2 id="judul-peran">Pemakaian per fungsi</h2></div>
      <p class="redup">Pilihan tersimpan begitu diganti. Baris bertanda "agen" dikerjakan Claude Code, bukan model endpoint, sehingga tidak bisa diganti di sini (atur lewat DESAIN_CLAUDE di /etc/velocity/installer-autopilot.env).</p>
      <p v-if="memuat" class="redup">Memuat…</p>
      <p v-else-if="!data.models.length" class="redup">Belum ada model. Tambahkan model di bawah; tanpa model, langkah AI installer dilewati.</p>
      <div v-else class="peran">
        <div v-for="p in data.peran" :key="p.kunci" class="peran-baris">
          <div><b>{{ p.label }}</b><span class="skrip">{{ p.script }}</span></div>
          <select :value="pilihanHilang(p) ? '' : (data.pemakaian[p.kunci] || '')" :aria-label="`Model untuk ${p.label}`" @change="gantiPeran(p, $event.target.value)">
            <option value="">Ikut default ({{ modelDefault?.id || '-' }})</option>
            <option v-for="m in data.models" :key="m.id" :value="m.id">{{ m.id }}</option>
          </select>
          <span class="pesan-status" :class="pilihanHilang(p) ? 'bahaya' : statusPeran[p.kunci]?.kelas" aria-live="polite">
            {{ pilihanHilang(p) ? `Model "${data.pemakaian[p.kunci]}" sudah dihapus, memakai default.` : statusPeran[p.kunci]?.teks }}
          </span>
        </div>
        <div v-for="p in data.peranTetap" :key="p.kunci" class="peran-baris tetap">
          <div><b>{{ p.label }}</b><span class="skrip">{{ p.script }}</span></div>
          <span class="lencana abu">agen · {{ p.model }}</span>
          <span class="pesan-status">{{ p.aktif ? 'Aktif (DESAIN_CLAUDE=1), tidak memakai model endpoint.' : 'Mati (DESAIN_CLAUDE=0), desain memakai generator.' }}</span>
        </div>
      </div>
    </section>

    <section class="kartu" aria-labelledby="judul-model">
      <div class="kartu-judul">
        <h2 id="judul-model">Model terdaftar</h2>
        <button type="button" class="tombol kecil" @click="bukaForm(null)">+ Tambah model</button>
      </div>
      <p class="redup">Endpoint yang kompatibel dengan OpenAI chat completions. API key tidak pernah ditampilkan.</p>
      <div class="daftar-model">
        <article v-for="m in data.models" :key="m.id" class="model">
          <div class="nama"><b>{{ m.id }}</b><span v-if="m.is_default" class="lencana biru">DEFAULT</span><span v-if="!m.api_key_set" class="lencana kuning">API key kosong</span></div>
          <dl>
            <div><dt>Model API</dt><dd>{{ m.model || m.id }}</dd></div>
            <div><dt>Endpoint</dt><dd>{{ m.endpoint }}</dd></div>
            <div><dt>Dipakai</dt><dd>{{ dipakaiOleh(m).join(', ') || 'Tidak dipakai fungsi mana pun' }}</dd></div>
          </dl>
          <div class="aksi">
            <button type="button" class="tombol garis kecil" :disabled="statusModel[m.id]?.proses" @click="aksiModel(m, 'test')">Test</button>
            <button type="button" class="tombol garis kecil" :disabled="statusModel[m.id]?.proses" @click="bukaForm(m)">Edit</button>
            <button v-if="!m.is_default" type="button" class="tombol garis kecil" :disabled="statusModel[m.id]?.proses" @click="aksiModel(m, 'default')">Jadikan default</button>
            <button type="button" class="tombol bahaya kecil" :disabled="statusModel[m.id]?.proses" @click="aksiModel(m, 'hapus')">Hapus</button>
          </div>
          <p v-if="statusModel[m.id]" class="pesan-status" :class="statusModel[m.id].kelas" aria-live="polite">{{ statusModel[m.id].teks }}</p>
        </article>
      </div>
    </section>

    <section class="kartu" aria-labelledby="judul-token">
      <div class="kartu-judul"><h2 id="judul-token">Pemakaian token per domain</h2></div>
      <p class="redup">Dijumlah dari setiap panggilan AI installer (usage.jsonl): model endpoint dan agen desain Claude dipisah per run. Klik domain untuk rincian per run.</p>
      <p v-if="galatToken" class="pesan-status bahaya">Gagal memuat pemakaian token: {{ galatToken }}</p>
      <p v-else-if="!token" class="redup">Memuat…</p>
      <p v-else-if="!domain.length" class="redup">Belum ada catatan. Pemakaian token tercatat mulai run installer berikutnya.</p>
      <template v-else>
        <div class="ringkas">
          <div><span class="redup">Total token</span><strong>{{ angka(total.total_tokens) }}</strong></div>
          <div><span class="redup">Request</span><strong>{{ angka(total.panggilan) }}</strong><span v-if="total.gagal" class="merah">{{ angka(total.gagal) }} gagal</span></div>
          <div><span class="redup">Domain</span><strong>{{ domain.length }}</strong></div>
          <div v-if="total.per_sumber?.claude?.biaya_usd"><span class="redup">Agen Claude (setara API)</span><strong>US${{ Number(total.per_sumber.claude.biaya_usd).toFixed(2) }}</strong></div>
        </div>
        <p class="redup">{{ ringkasSumber(total.per_sumber) }}</p>
        <div class="daftar-domain">
          <button v-for="d in domainTampil" :key="d.domain" type="button" class="domain" @click="rinci = d">
            <span class="d-nama">{{ d.domain }}</span>
            <span class="d-angka">{{ angka(d.total_tokens) }} token</span>
            <span class="d-sub">{{ d.runs.length }} run · {{ angka(d.panggilan) }} request<template v-if="d.gagal"> · <span class="merah">{{ angka(d.gagal) }} gagal</span></template> · terakhir {{ tanggalWaktu(d.terakhir) }}</span>
          </button>
        </div>
        <div v-if="jmlHalaman > 1" class="halaman-nav">
          <span class="redup">{{ (halaman - 1) * PER_HALAMAN + 1 }}–{{ Math.min(halaman * PER_HALAMAN, domain.length) }} dari {{ domain.length }} domain</span>
          <div>
            <button type="button" class="tombol garis kecil" :disabled="halaman <= 1" @click="halaman--">Sebelumnya</button>
            <button type="button" class="tombol garis kecil" :disabled="halaman >= jmlHalaman" @click="halaman++">Berikutnya</button>
          </div>
        </div>
      </template>
    </section>

    <Dialog :buka="form.buka" :judul="form.edit ? `Edit model ${form.id}` : 'Tambah model'" lebar="560px" @tutup="form.buka = false">
      <form class="form-model" @submit.prevent="simpanForm">
        <label class="isian"><span>ID model</span><input v-model="form.id" :readonly="form.edit" :autofocus="!form.edit" required><small>Huruf, angka, titik, garis bawah, tanda hubung, garis miring (mis. meta-llama/llama-3-70b). Tidak bisa diubah setelah disimpan.</small></label>
        <label class="isian"><span>Nama model di API</span><input v-model="form.model" :autofocus="form.edit"><small>Dikirim sebagai "model" ke endpoint. Kosong berarti sama dengan ID.</small></label>
        <label class="isian"><span>Endpoint URL</span><input v-model="form.endpoint" type="url" required placeholder="https://…/v1"></label>
        <label class="isian"><span>API key</span><input v-model="form.api_key" type="password" autocomplete="off"><small>{{ form.edit ? 'Kosongkan untuk tetap memakai API key yang tersimpan.' : 'Wajib untuk model baru.' }}</small></label>
        <label class="centang"><input v-model="form.is_default" type="checkbox"> Jadikan model default</label>
        <button type="button" class="tombol garis kecil pas" @click="isi9router">Isi endpoint 9router</button>
        <p v-if="form.galat" class="pesan-status bahaya" role="alert">{{ form.galat }}</p>
        <div class="aksi-dialog">
          <button type="button" class="tombol garis" @click="form.buka = false">Batal</button>
          <button type="submit" class="tombol" :disabled="form.proses">{{ form.proses ? 'Menyimpan…' : 'Simpan' }}</button>
        </div>
      </form>
    </Dialog>

    <Dialog :buka="!!rinci" :judul="rinci?.domain || ''" lebar="1100px" @tutup="rinci = null">
      <template v-if="rinci">
        <p class="redup"><b>{{ angka(rinci.total_tokens) }}</b> token · {{ rinci.runs.length }} run · {{ angka(rinci.panggilan) }} request<template v-if="ringkasSumber(rinci.per_sumber)"><br>{{ ringkasSumber(rinci.per_sumber) }}</template></p>
        <div class="tabel-wadah">
          <table class="tabel">
            <thead><tr><th>Run</th><th>Mode</th><th>Endpoint</th><th>Agen Claude</th><th>Total token</th><th>Request</th><th>Per fungsi</th><th>Model</th></tr></thead>
            <tbody>
              <tr v-for="r in rinci.runs" :key="r.run || r.mulai">
                <td>{{ tanggalWaktu(r.mulai) }}</td>
                <td>{{ r.mode }}</td>
                <td>{{ r.per_sumber?.endpoint?.panggilan ? `${angka(r.per_sumber.endpoint.panggilan)} req · ${angka(r.per_sumber.endpoint.total_tokens)}` : '-' }}</td>
                <td>{{ r.per_sumber?.claude?.panggilan ? `${angka(r.per_sumber.claude.panggilan)} req · ${angka(r.per_sumber.claude.total_tokens)}` : '-' }}<span v-if="r.per_sumber?.claude?.biaya_usd" class="skrip">setara US${{ Number(r.per_sumber.claude.biaya_usd).toFixed(2) }}</span></td>
                <td><b>{{ angka(r.total_tokens) }}</b></td>
                <td>{{ angka(r.panggilan) }}<span v-if="r.gagal" class="merah"> ({{ r.gagal }} gagal)</span></td>
                <td class="kecil-sel">{{ rincianPeran(r.per_peran) }}</td>
                <td class="kecil-sel">{{ (r.model || []).join(', ') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; }
.skrip { display: block; color: var(--teks-3); font-size: 12px; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.merah { color: var(--bahaya); }
.peran { display: grid; gap: 10px; margin-top: 12px; }
.peran-baris { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(200px, 1fr) minmax(0, 1fr); gap: 12px; align-items: center; padding: 12px 14px; border-radius: 12px; background: var(--kartu-2); }
.peran-baris.tetap { border: 1px dashed var(--garis); background: transparent; }
.peran-baris .pesan-status { margin: 0; }
.daftar-model { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; margin-top: 12px; }
.model { padding: 14px 16px; border-radius: 12px; background: var(--kartu-2); display: grid; gap: 10px; align-content: start; }
.model .nama { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 15px; }
.model dl { margin: 0; display: grid; gap: 4px; font-size: 13px; }
.model dl div { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 8px; }
.model dt { color: var(--teks-3); }
.model dd { margin: 0; overflow-wrap: anywhere; }
.aksi { display: flex; gap: 8px; flex-wrap: wrap; }
.ringkas { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 12px 0 6px; }
.ringkas > div { display: grid; padding: 12px 14px; border-radius: 12px; background: var(--kartu-2); }
.ringkas strong { font-size: 20px; font-variant-numeric: tabular-nums; }
.daftar-domain { display: grid; gap: 8px; margin-top: 10px; }
.domain { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 12px; padding: 12px 14px; border-radius: 12px; border: 1px solid transparent; background: var(--kartu-2); text-align: left; cursor: pointer; }
.domain:hover { border-color: var(--aksen); }
.d-nama { font-weight: 600; overflow-wrap: anywhere; }
.d-angka { font-weight: 600; color: var(--aksen-terang); font-variant-numeric: tabular-nums; }
.d-sub { grid-column: 1 / -1; font-size: 12.5px; color: var(--teks-3); }
.halaman-nav { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.halaman-nav div { display: flex; gap: 8px; }
.form-model { display: grid; gap: 14px; }
.centang { display: flex; align-items: center; gap: 10px; font-weight: 500; }
.pas { justify-self: start; }
.kecil-sel { font-size: 12.5px; color: var(--teks-2); min-width: 180px; }
@media (max-width: 800px) { .peran-baris { grid-template-columns: minmax(0, 1fr); } }
</style>
