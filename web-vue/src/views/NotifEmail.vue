<script setup>
// Notif email Gmail -> Telegram (/opt/pengawas-email, timer tiap menit). Email dibaca read-only,
// status baca di Gmail tidak berubah. Sandi & token disimpan di /etc/velocity/secrets, browser hanya melihat versi tersamar.
import { ref, reactive, computed, watch } from 'vue'
import Ikon from '../components/Ikon.vue'
import Dialog from '../components/Dialog.vue'
import { konfirmasi } from '../konfirmasi.js'
import { pakaiPolling, kirim, tanggalWaktu } from '../api.js'

const { data, galat, memuat, muatUlang } = pakaiPolling('/api/email-notif', 30000)

const form = reactive({ gmail_user: '', sandi: '', token: '', proses: false, pesan: '', galat: '' })
// Isi email sekali saat data pertama datang; jangan menimpa ketikan user saat polling
watch(data, (d) => { if (d && !form.gmail_user) form.gmail_user = d.gmail_user || '' }, { immediate: true })

const PESAN = {
  forbidden: 'Hanya bisa disimpan dari jaringan kantor atau Tailscale.',
  email_tidak_valid: 'Alamat Gmail tidak valid.',
  sandi_kosong: 'App Password belum diisi.',
  gmail_login_gagal: 'Login Gmail ditolak. Periksa alamat & App Password (bukan sandi akun biasa).',
  gmail_tak_terjangkau: 'Gmail tidak bisa dihubungi dari server. Coba lagi sebentar.',
  token_tidak_valid: 'Token bot Telegram tidak valid.',
  telegram_tak_terjangkau: 'Telegram tidak bisa dihubungi dari server. Coba lagi sebentar.',
  chat_id_tidak_valid: 'Chat ID harus angka, grup diawali minus (mis. -4989379823).',
  nama_rute_kosong: 'Nama rute wajib diisi.',
  rute_tanpa_kata_kunci: 'Isi minimal satu kata kunci subject atau pengirim.',
  aturan_tidak_valid: 'Format aturan tidak valid.',
}
async function simpan() {
  Object.assign(form, { proses: true, pesan: '', galat: '' })
  try {
    data.value = await kirim('/api/email-notif/login', { gmail_user: form.gmail_user, sandi: form.sandi, token: form.token })
    Object.assign(form, { sandi: '', token: '', pesan: 'Login berhasil diuji dan disimpan. Berlaku di pemeriksaan berikutnya (≤1 menit).' })
  } catch (e) {
    form.galat = PESAN[e.message] || `Gagal menyimpan: ${e.message}`
  } finally {
    form.proses = false
  }
}

const kondisi = computed(() => {
  const d = data.value
  if (!d) return null
  if (!d.timer_aktif) return { kelas: 'bahaya', teks: 'Timer mati' }
  if (d.galat_terakhir) return { kelas: 'bahaya', teks: 'Gagal cek email' }
  if (!d.jalan_terakhir || Date.now() - new Date(d.jalan_terakhir) > 5 * 60000) return { kelas: 'waspada', teks: 'Tidak jalan >5 menit' }
  return { kelas: 'baik', teks: 'Berjalan' }
})
// ---- Aturan (/opt/pengawas-email/aturan.json): tiap perubahan langsung disimpan utuh ----
const aturan = computed(() => data.value?.aturan || {})
const rute = computed(() => aturan.value.rute || [])
const TAB = computed(() => [
  { nilai: 'rute', label: 'Rute divisi', jumlah: rute.value.length + 1 },
  { nilai: 'kecualikan_subject', label: 'Kecualikan subject', jumlah: aturan.value.kecualikan_subject?.length || 0 },
  { nilai: 'kecualikan_pengirim', label: 'Kecualikan pengirim', jumlah: aturan.value.kecualikan_pengirim?.length || 0 },
])
const tab = ref('rute')
const galatAturan = ref('')
const kirim7 = (chat) => data.value?.per_chat_7hari?.[chat] || 0

async function simpanAturan(baru) {
  galatAturan.value = ''
  const r = await kirim('/api/email-notif/aturan', { ...aturan.value, ...baru })
  data.value = r
}
const pisah = (t) => t.split(/[\n,]/).map((x) => x.trim()).filter(Boolean)

const edit = reactive({ buka: false, indeks: -1, bawaan: false, nama: '', subject: '', pengirim: '', chat_id: '', catatan: '', galat: '', proses: false })
function bukaRute(i) {
  const r = i >= 0 ? rute.value[i] : { nama: '', subject_berisi: [], pengirim_berisi: [], chat_id: '', catatan: '' }
  Object.assign(edit, { buka: true, indeks: i, bawaan: false, nama: r.nama, subject: r.subject_berisi.join('\n'), pengirim: r.pengirim_berisi.join('\n'), chat_id: r.chat_id, catatan: r.catatan || '', galat: '', proses: false })
}
function bukaBawaan() {
  Object.assign(edit, { buka: true, indeks: -1, bawaan: true, nama: 'Semua email lainnya', subject: '', pengirim: '', chat_id: aturan.value.chat_default || '', catatan: aturan.value.catatan_default || '', galat: '', proses: false })
}
async function simpanRute() {
  edit.proses = true
  try {
    if (edit.bawaan) {
      await simpanAturan({ chat_default: edit.chat_id, catatan_default: edit.catatan })
    } else {
      const baris = { nama: edit.nama, subject_berisi: pisah(edit.subject), pengirim_berisi: pisah(edit.pengirim), chat_id: edit.chat_id, catatan: edit.catatan }
      const daftar = rute.value.map((r) => ({ ...r }))
      if (edit.indeks >= 0) daftar[edit.indeks] = baris
      else daftar.push(baris)
      await simpanAturan({ rute: daftar })
    }
    edit.buka = false
  } catch (e) {
    edit.galat = PESAN[e.message] || `Gagal menyimpan: ${e.message}`
  } finally {
    edit.proses = false
  }
}
async function hapusRute(i) {
  const ok = await konfirmasi({ judul: `Hapus rute "${rute.value[i].nama}"?`, teks: 'Email yang cocok akan masuk ke grup default.', tombol: 'Hapus', kelas: 'bahaya' })
  if (!ok) return
  try {
    await simpanAturan({ rute: rute.value.filter((_, j) => j !== i) })
  } catch (e) {
    galatAturan.value = PESAN[e.message] || `Gagal menghapus: ${e.message}`
  }
}
// Urutan rute menentukan prioritas (yang pertama cocok dipakai)
async function geserRute(i, arah) {
  const daftar = [...rute.value]
  ;[daftar[i], daftar[i + arah]] = [daftar[i + arah], daftar[i]]
  try { await simpanAturan({ rute: daftar }) } catch (e) { galatAturan.value = PESAN[e.message] || e.message }
}

const baru = reactive({ kecualikan_subject: '', kecualikan_pengirim: '' })
async function tambahKecuali(kunci) {
  const nilai = pisah(baru[kunci])
  if (!nilai.length) return
  try {
    await simpanAturan({ [kunci]: [...(aturan.value[kunci] || []), ...nilai] })
    baru[kunci] = ''
  } catch (e) {
    galatAturan.value = PESAN[e.message] || `Gagal menyimpan: ${e.message}`
  }
}
async function hapusKecuali(kunci, nilai) {
  try {
    await simpanAturan({ [kunci]: aturan.value[kunci].filter((x) => x !== nilai) })
  } catch (e) {
    galatAturan.value = PESAN[e.message] || `Gagal menghapus: ${e.message}`
  }
}

const STATUS = { terkirim: ['hijau', 'Terkirim'], gagal: ['merah', 'Gagal'], dikecualikan: ['abu', 'Dikecualikan'] }
const hitung = (s) => data.value?.hari_ini?.[s] || 0
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Notif Email</h1>
        <p class="redup">Email masuk Gmail diteruskan ke grup Telegram tiap menit, tanpa menandai email sebagai terbaca.</p>
      </div>
      <button type="button" class="tombol garis kecil" @click="muatUlang"><Ikon nama="ulang" :ukuran="16" /> Periksa ulang</button>
    </header>

    <p v-if="memuat" class="redup">Memuat…</p>
    <p v-else-if="galat && !data" class="pesan-status bahaya">Gagal memuat: {{ galat.message }}</p>

    <template v-else-if="data">
      <div class="ringkas">
        <div class="kartu angka"><span class="redup">Status</span><b class="kecil-b"><span class="pil" :class="kondisi.kelas">{{ kondisi.teks }}</span></b></div>
        <div class="kartu angka"><span class="redup">Terkirim hari ini</span><b>{{ hitung('terkirim') }}</b></div>
        <div class="kartu angka"><span class="redup">Dikecualikan / gagal</span><b>{{ hitung('dikecualikan') }} <small>/ {{ hitung('gagal') }}</small></b></div>
      </div>
      <p v-if="data.galat_terakhir" class="pesan-status bahaya" role="alert">Galat terakhir: {{ data.galat_terakhir }}</p>

      <section class="kartu" aria-labelledby="judul-login">
        <div class="kartu-judul">
          <h2 id="judul-login"><Ikon nama="kunci" :ukuran="16" /> Pengaturan login</h2>
          <span class="redup">Cek terakhir: {{ tanggalWaktu(data.jalan_terakhir) }}</span>
        </div>
        <form class="form" @submit.prevent="simpan">
          <label class="isian"><span>Akun Gmail yang dipantau</span>
            <input v-model.trim="form.gmail_user" type="email" required maxlength="200" autocomplete="off" placeholder="nama@gmail.com">
          </label>
          <label class="isian"><span>App Password Gmail</span>
            <input v-model="form.sandi" type="password" maxlength="64" autocomplete="new-password" :placeholder="data.sandi ? `Tersimpan (${data.sandi}) — kosongkan bila tidak diganti` : '16 huruf dari Google'">
            <small>Buat di <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener">myaccount.google.com/apppasswords</a> (Verifikasi 2 Langkah harus aktif). Spasi boleh ikut ditempel.</small>
          </label>
          <label class="isian"><span>Token bot Telegram</span>
            <input v-model.trim="form.token" type="password" maxlength="100" autocomplete="off" :placeholder="data.token ? `Tersimpan (${data.token}) — kosongkan bila tidak diganti` : '123456:ABC…'">
            <small>Dari @BotFather. Bot harus sudah menjadi anggota grup tujuan.</small>
          </label>
          <p class="redup">Saat disimpan, login Gmail dan token bot diuji dulu; kalau gagal, pengaturan lama tetap dipakai. Ganti akun Gmail = email lama akun itu tidak dikirim ulang.</p>
          <p v-if="form.galat" class="pesan-status bahaya" role="alert">{{ form.galat }}</p>
          <p v-if="form.pesan" class="pesan-status baik" role="status">{{ form.pesan }}</p>
          <div class="aksi"><button type="submit" class="tombol" :disabled="form.proses">{{ form.proses ? 'Menguji & menyimpan…' : 'Uji & simpan' }}</button></div>
        </form>
      </section>

      <section class="kartu" aria-labelledby="judul-aturan">
        <div class="kartu-judul">
          <h2 id="judul-aturan">Aturan</h2>
          <div class="tab" role="tablist" aria-label="Jenis aturan">
            <button v-for="t in TAB" :key="t.nilai" type="button" role="tab" :aria-selected="tab === t.nilai" :class="{ aktif: tab === t.nilai }" @click="tab = t.nilai">
              {{ t.label }} <span class="hitung">{{ t.jumlah }}</span>
            </button>
          </div>
        </div>
        <p v-if="aturan.galat" class="pesan-status bahaya">Gagal membaca aturan.json: {{ aturan.galat }}</p>
        <p v-if="galatAturan" class="pesan-status bahaya" role="alert">{{ galatAturan }}</p>

        <template v-if="tab === 'rute'">
          <p class="redup petunjuk">Diperiksa dari atas ke bawah; rute pertama yang cocok (subject atau pengirim mengandung kata kunci, huruf besar/kecil diabaikan) menentukan grup tujuan.</p>
          <div class="grid-rute">
            <article v-for="(r, i) in rute" :key="i" class="rute">
              <div class="rute-atas">
                <b>{{ r.nama }}</b>
                <span class="lencana biru">#{{ i + 1 }}</span>
              </div>
              <dl>
                <div v-if="r.subject_berisi.length"><dt>Subject berisi</dt><dd><span v-for="k in r.subject_berisi" :key="k" class="chip">{{ k }}</span></dd></div>
                <div v-if="r.pengirim_berisi.length"><dt>Pengirim berisi</dt><dd><span v-for="k in r.pengirim_berisi" :key="k" class="chip">{{ k }}</span></dd></div>
                <div><dt>Grup tujuan</dt><dd><code>{{ r.chat_id }}</code></dd></div>
                <div v-if="r.catatan"><dt>Catatan</dt><dd>{{ r.catatan }}</dd></div>
              </dl>
              <div class="rute-bawah">
                <span class="redup">{{ kirim7(r.chat_id) }} terkirim · 7 hari</span>
                <span class="aksi-rute">
                  <button type="button" class="tombol garis kecil" :disabled="i === 0" :aria-label="`Naikkan ${r.nama}`" @click="geserRute(i, -1)">↑</button>
                  <button type="button" class="tombol garis kecil" :disabled="i === rute.length - 1" :aria-label="`Turunkan ${r.nama}`" @click="geserRute(i, 1)">↓</button>
                  <button type="button" class="tombol garis kecil" @click="bukaRute(i)"><Ikon nama="sunting" :ukuran="14" /> Edit</button>
                  <button type="button" class="tombol bahaya kecil" :aria-label="`Hapus ${r.nama}`" @click="hapusRute(i)"><Ikon nama="tutup" :ukuran="14" /></button>
                </span>
              </div>
            </article>
            <article class="rute bawaan">
              <div class="rute-atas"><b>Semua email lainnya</b><span class="lencana abu">DEFAULT</span></div>
              <dl>
                <div><dt>Berlaku untuk</dt><dd>Email yang tidak dikecualikan dan tidak cocok rute mana pun</dd></div>
                <div><dt>Grup tujuan</dt><dd><code>{{ aturan.chat_default }}</code></dd></div>
                <div v-if="aturan.catatan_default"><dt>Catatan</dt><dd>{{ aturan.catatan_default }}</dd></div>
              </dl>
              <div class="rute-bawah">
                <span class="redup">{{ kirim7(aturan.chat_default) }} terkirim · 7 hari</span>
                <span class="aksi-rute"><button type="button" class="tombol garis kecil" @click="bukaBawaan"><Ikon nama="sunting" :ukuran="14" /> Edit</button></span>
              </div>
            </article>
            <button type="button" class="rute tambah-rute" @click="bukaRute(-1)"><Ikon nama="tambah" :ukuran="20" /> Tambah rute divisi</button>
          </div>
        </template>

        <template v-else>
          <p class="redup petunjuk">{{ tab === 'kecualikan_subject' ? 'Email yang subject-nya mengandung kata ini tidak dikirim ke Telegram (huruf besar/kecil diabaikan).' : 'Email dari alamat ini tidak dikirim ke Telegram (harus sama persis).' }}</p>
          <ul class="daftar-chip">
            <li v-for="k in aturan[tab]" :key="k" class="chip besar">
              {{ k }}
              <button type="button" :aria-label="`Hapus ${k}`" @click="hapusKecuali(tab, k)"><Ikon nama="tutup" :ukuran="12" /></button>
            </li>
            <li v-if="!aturan[tab]?.length" class="redup">Belum ada.</li>
          </ul>
          <form class="tambah-kecuali" @submit.prevent="tambahKecuali(tab)">
            <input v-model="baru[tab]" maxlength="400" :placeholder="tab === 'kecualikan_subject' ? 'Kata/kalimat subject, pisahkan dengan koma' : 'alamat@email.com, pisahkan dengan koma'" :aria-label="tab === 'kecualikan_subject' ? 'Tambah pengecualian subject' : 'Tambah pengecualian pengirim'">
            <button type="submit" class="tombol kecil" :disabled="!baru[tab].trim()">+ Tambah</button>
          </form>
        </template>
      </section>

      <section class="kartu" aria-labelledby="judul-riwayat">
        <div class="kartu-judul"><h2 id="judul-riwayat">Email terakhir diproses</h2></div>
        <p v-if="!data.terakhir?.length" class="redup">Belum ada email baru sejak pengawas aktif.</p>
        <div v-else class="gulir">
          <table class="riwayat">
            <thead><tr><th scope="col">Waktu</th><th scope="col">Status</th><th scope="col">Dari</th><th scope="col">Subject</th></tr></thead>
            <tbody>
              <tr v-for="(e, i) in data.terakhir" :key="i">
                <td class="nowrap">{{ tanggalWaktu(e.waktu) }}</td>
                <td><span class="lencana" :class="(STATUS[e.status] || ['abu'])[0]">{{ STATUS[e.status]?.[1] || e.status }}</span></td>
                <td>{{ e.dari }}</td>
                <td>{{ e.subject }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
    <Dialog :buka="edit.buka" :judul="edit.bawaan ? 'Rute default' : (edit.indeks >= 0 ? `Edit rute: ${edit.nama}` : 'Tambah rute divisi')" lebar="560px" @tutup="edit.buka = false">
      <form class="form" @submit.prevent="simpanRute">
        <label v-if="!edit.bawaan" class="isian"><span>Nama rute / divisi</span><input v-model="edit.nama" required maxlength="100" placeholder="Keuangan"></label>
        <label v-if="!edit.bawaan" class="isian"><span>Subject berisi</span><textarea v-model="edit.subject" rows="3" placeholder="Satu per baris, mis.&#10;Invoice&#10;Pembayaran" /><small>Cocok bila subject mengandung salah satu kata ini.</small></label>
        <label v-if="!edit.bawaan" class="isian"><span>Pengirim berisi</span><textarea v-model="edit.pengirim" rows="2" placeholder="Satu per baris, mis. @bank.co.id" /><small>Cocok bila nama/alamat pengirim mengandung teks ini.</small></label>
        <label class="isian"><span>Chat ID grup Telegram</span><input v-model.trim="edit.chat_id" required inputmode="numeric" maxlength="21" placeholder="-4989379823"><small>Bot harus sudah ada di grup itu.</small></label>
        <label class="isian"><span>Catatan di pesan</span><input v-model="edit.catatan" maxlength="300" placeholder="⚠️ Silahkan Keuangan Cek"></label>
        <p v-if="edit.galat" class="pesan-status bahaya" role="alert">{{ edit.galat }}</p>
        <div class="aksi-dialog">
          <button type="button" class="tombol garis" @click="edit.buka = false">Batal</button>
          <button type="submit" class="tombol" :disabled="edit.proses">{{ edit.proses ? 'Menyimpan…' : 'Simpan' }}</button>
        </div>
      </form>
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 18px; max-width: 1000px; }
.ringkas { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.angka { display: grid; gap: 6px; }
.angka b { font-size: 24px; }
.angka b small { font-size: 14px; color: var(--teks-3); font-weight: 600; }
.angka .kecil-b { font-size: 16px; }
.kartu-judul h2 { display: inline-flex; align-items: center; gap: 8px; }
.form { display: grid; gap: 14px; max-width: 560px; }
.form a { color: var(--aksen-terang); }
.form p { margin: 0; }
.aksi { display: flex; }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
.petunjuk { margin: 0 0 12px; }
.grid-rute { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.rute { padding: 14px; border-radius: 12px; background: var(--kartu-2); display: grid; gap: 10px; align-content: start; }
.rute.bawaan { border: 1px dashed var(--garis); }
.rute-atas { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 15px; }
.rute dl { margin: 0; display: grid; gap: 8px; font-size: 13px; }
.rute dt { color: var(--teks-3); font-size: 12px; margin-bottom: 3px; }
.rute dd { margin: 0; color: var(--teks-2); display: flex; flex-wrap: wrap; gap: 5px; overflow-wrap: anywhere; }
.rute-bawah { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; margin-top: auto; }
.aksi-rute { display: flex; gap: 6px; }
.aksi-rute .tombol { display: inline-flex; align-items: center; gap: 4px; }
.tambah-rute { border: 1px dashed var(--garis); background: transparent; color: var(--teks-2); font: inherit; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 120px; cursor: pointer; }
.tambah-rute:hover { border-color: var(--aksen-terang); color: var(--aksen-terang); }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 2px 9px; border-radius: 999px; background: var(--kartu); color: var(--teks); font-size: 12.5px; }
.daftar-chip { list-style: none; margin: 0 0 12px; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; }
.chip.besar { padding: 5px 6px 5px 12px; background: var(--kartu-2); font-size: 13px; }
.chip button { display: grid; place-items: center; width: 22px; height: 22px; border: 0; border-radius: 50%; background: transparent; color: var(--teks-3); cursor: pointer; }
.chip button:hover { background: rgba(255, 107, 107, .15); color: var(--bahaya); }
.tambah-kecuali { display: flex; gap: 8px; max-width: 560px; }
.tambah-kecuali input { flex: 1; min-width: 0; }
.gulir { overflow-x: auto; }
.riwayat { width: 100%; border-collapse: collapse; font-size: 13px; }
.riwayat th { text-align: left; font-size: 12px; font-weight: 600; color: var(--teks-3); padding: 6px 10px 6px 0; border-bottom: 1px solid var(--garis); }
.riwayat td { padding: 7px 10px 7px 0; border-bottom: 1px solid var(--garis); color: var(--teks-2); overflow-wrap: anywhere; vertical-align: top; }
.nowrap { white-space: nowrap; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
.kaki { margin: 14px 0 0; }
@media (max-width: 700px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
  .ringkas .angka:first-child { grid-column: 1 / -1; }
  .kartu-judul { flex-wrap: wrap; }
}
</style>
