<script setup>
// WAF server hosting (sub-menu Server): Velocity WAF = ruleset ModSecurity pengganti aturan cPGuard/Malware.Expert.
// Status per server: GET /api/servers/waf (installer_status.py → scripts/velocity_waf.py lewat SSH, hanya baca).
// Pasang / ganti mode / perbarui / copot: POST /api/servers/waf/aksi → job latar (LiteSpeed direstart, rollback
// otomatis bila situs uji error), dipantau lewat GET /api/servers/waf/job?id=. Setelan rakit berlaku untuk semua
// server: POST /api/servers/waf/setelan. Log: komponen LogWaf (sama dengan Proteksi > WAF).
import PilihServer from '../components/PilihServer.vue'
import { pilihServer } from '../jenisServer.js'
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import Ikon from '../components/Ikon.vue'
import PelakuAkun from '../components/PelakuAkun.vue'
import { namaAkun } from '../akun.js'
import Info from '../components/Info.vue'
import LogWaf from '../components/LogWaf.vue'
import { konfirmasi } from '../konfirmasi.js'
import { minta, kirim, pakaiPolling, tanggalWaktu, waktuLalu, angka } from '../api.js'
import { tabUrl } from '../laravel.js'

const waf = pakaiPolling('/api/servers/waf', 300000)
const aturan = pakaiPolling('/api/servers/waf/aturan', 0)
const riwayat = pakaiPolling('/api/servers/waf/riwayat', 0)
const segarkan = ref(false)
async function muatSegar() {
  segarkan.value = true
  try { waf.data.value = await minta('/api/servers/waf?segar=1'); waf.galat.value = null }
  catch (e) { waf.galat.value = e }
  finally { segarkan.value = false }
  riwayat.muatUlang()
}
const servers = computed(() => waf.data.value?.servers || [])
const lokal = computed(() => waf.data.value?.lokal || null)
const pilih = pilihServer()
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || servers.value[0] || null)
const TAB = ['status', 'log', 'aturan', 'setelan', 'riwayat']
const tab = tabUrl('tab', 'status', { boleh: TAB })

// Nama pelaku dipakai bersama halaman Proteksi & Antivirus
// Pelaku di riwayat = akun yang masuk ke dash.velocity.ai.id (backend menggantinya dari cookie sesi)
const oleh = namaAkun

const PESAN = {
  invalid_oleh: 'Masuk dulu lewat tombol "Masuk dengan VD.net" di kanan atas — setiap perubahan WAF dicatat atas nama akun Anda.',
  login_diperlukan: 'Sesi login habis atau belum masuk. Klik "Masuk dengan VD.net" di kanan atas.',
  server_tidak_dikenal: 'Server tidak dikenal; muat ulang halaman.',
  mode_tidak_sah: 'Mode tidak dikenal.',
  aksi_sedang_jalan: 'Masih ada perubahan WAF berjalan di server ini. Tunggu selesai dulu.',
  bukan_litespeed_modsecurity: 'Server ini bukan LiteSpeed + ModSecurity (/etc/modsecurity.d tidak ada).',
  dikembalikan: 'Pemeriksaan sesudah restart gagal — berkas & include dikembalikan seperti semula.',
  setelan_tidak_sah: 'Ada nilai setelan di luar batas.',
  ip_tidak_sah: 'Ada alamat IP / CIDR yang tidak sah.',
  cidr_terlalu_lebar: 'Rentang terlalu lebar: paling lebar /16 (IPv4) atau /32 (IPv6).',
  job_tidak_ada: 'Status perubahan hilang (layanan dashboard di-restart). Cek ulang status server.',
  forbidden: 'Ditolak: hanya bisa dijalankan dari halaman dashboard ini.',
  timeout: 'Server tidak menjawab (timeout).',
}
const pesanGalat = (e) => PESAN[e] || PESAN[String(e).split(':')[0]] || e || 'gagal'
const pesan = reactive({ teks: '', galat: false })
const proses = ref(false)
function perluNama() {
  if (oleh.value.trim()) return false
  Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true })
  document.getElementById('nama-waf')?.focus()
  return true
}

// ---- Keadaan per server ----
const st = (s) => s?.status || {}
const terpasang = (s) => !!st(s).terpasang
const perluUpdate = (s) => terpasang(s) && lokal.value && st(s).sidik !== lokal.value.sidik
function keadaan(s) {
  if (!s?.ok) return { kelas: 'abu', titik: 'bahaya', label: 'Tak terbaca' }
  if (!st(s).lsws || !st(s).modsecurity_d) return { kelas: 'abu', titik: 'abu', label: 'Tidak didukung' }
  if (!terpasang(s)) return { kelas: 'abu', titik: st(s).cpguard ? 'waspada' : 'bahaya', label: 'Belum terpasang' }
  if (st(s).mode === 'blokir') return { kelas: 'hijau', titik: perluUpdate(s) ? 'waspada' : 'baik', label: 'Mode blokir' }
  return { kelas: 'biru', titik: perluUpdate(s) ? 'waspada' : 'biru', label: 'Mode deteksi' }
}
// Server tanpa WAF sama sekali: cPGuard WAF tidak ada dan Velocity WAF belum terpasang
const tanpaWaf = (s) => s.ok && st(s).lsws && !st(s).cpguard && !terpasang(s)
const jumlahTerpasang = computed(() => servers.value.filter((s) => s.ok && terpasang(s)).length)

// ---- Job pasang/copot ----
const jobs = ref({})  // host → job terakhir dari sesi ini
let timerJob = null
watch(() => waf.data.value?.job, (daftar) => {
  for (const j of daftar || []) if (!jobs.value[j.host] || jobs.value[j.host].id !== j.id) jobs.value = { ...jobs.value, [j.host]: j }
  pantauJob()
})
const jobServer = computed(() => jobs.value[terpilih.value?.host] || null)
const berjalan = (host) => jobs.value[host]?.status === 'berjalan'
function pantauJob() {
  if (timerJob || !Object.values(jobs.value).some((j) => j.status === 'berjalan')) return
  timerJob = setInterval(async () => {
    const jalan = Object.values(jobs.value).filter((j) => j.status === 'berjalan')
    if (!jalan.length) { clearInterval(timerJob); timerJob = null; return }
    for (const j of jalan) {
      try {
        const baru = await minta(`/api/servers/waf/job?id=${j.id}`)
        jobs.value = { ...jobs.value, [j.host]: baru }
        if (baru.status !== 'berjalan') {
          const nama = baru.server
          Object.assign(pesan, baru.status === 'selesai'
            ? { teks: `${nama}: ${baru.aksi === 'copot' ? 'Velocity WAF dicopot' : `Velocity WAF aktif mode ${baru.mode}`}.`, galat: false }
            : { teks: `${nama}: ${pesanGalat(baru.hasil?.error)} ${baru.hasil?.alasan || ''}`, galat: true })
          muatSegar()
        }
      } catch (e) {
        jobs.value = { ...jobs.value, [j.host]: { ...j, status: 'gagal', hasil: { error: e.message } } }
      }
    }
  }, 3000)
}
onBeforeUnmount(() => clearInterval(timerJob))

const KONFIRMASI = {
  'pasang-deteksi': (s) => ({ judul: `Pasang Velocity WAF mode deteksi di ${s.name}?`, tombol: 'Pasang mode deteksi',
    teks: 'Aturan hanya MENCATAT (tidak memblokir pengunjung) — aman dijalankan berdampingan dengan cPGuard. LiteSpeed di-restart (±10 detik); bila situs uji error sesudahnya, semua dikembalikan otomatis.' }),
  'pasang-blokir': (s) => ({ judul: `Aktifkan mode BLOKIR di ${s.name}?`, tombol: 'Aktifkan blokir', kelas: 'bahaya',
    teks: `Bot jahat, crawler SEO/AI, probe berkas sensitif, dan brute force xmlrpc/wp-login akan DITOLAK (429/403/406).${st(s).cpguard ? ' cPGuard WAF masih aktif di server ini — aturan keduanya berjalan bersamaan.' : ''} LiteSpeed di-restart; rollback otomatis bila situs uji error.` }),
  perbarui: (s) => ({ judul: `Perbarui Velocity WAF di ${s.name}?`, tombol: 'Perbarui',
    teks: `Ruleset & setelan terbaru dipasang dengan mode tetap ${st(s).mode}. Berkas lama disalin ke /etc/velocity-waf.bak-<waktu>. LiteSpeed di-restart.` }),
  copot: (s) => ({ judul: `Copot Velocity WAF dari ${s.name}?`, tombol: 'Copot', kelas: 'bahaya',
    teks: `Include di /etc/modsecurity.d dihapus (berkas /etc/velocity-waf tetap ada) dan LiteSpeed di-restart.${st(s).cpguard ? '' : ' cPGuard WAF tidak aktif di server ini → server jadi TANPA aturan WAF.'}` }),
}
async function jalankan(jenis) {
  if (perluNama()) return
  const s = terpilih.value
  const ya = await konfirmasi(KONFIRMASI[jenis](s))
  if (!ya) return
  const body = jenis === 'copot' ? { aksi: 'copot' }
    : { aksi: 'pasang', mode: jenis === 'perbarui' ? (st(s).mode || 'deteksi') : jenis.split('-')[1] }
  proses.value = true
  try {
    const j = await kirim('/api/servers/waf/aksi', { ...body, server: s.host, oleh: oleh.value.trim() })
    jobs.value = { ...jobs.value, [s.host]: j }
    Object.assign(pesan, { teks: `${s.name}: perubahan WAF berjalan…`, galat: false })
    pantauJob()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
const durasi = (j) => `${Math.max(1, (j.selesai || Math.floor(Date.now() / 1000)) - j.mulai)} dtk`

// ---- Log: status IP dari data firewall (dimuat saat tab log dibuka) ----
const fw = ref(null)
watch(tab, async (t) => {
  if (t === 'log' && !fw.value) {
    try { fw.value = await minta('/api/servers/firewall') } catch { fw.value = { servers: [] } }
  }
}, { immediate: true })
function statusIp(ip, host) {
  const s = fw.value?.servers?.find((x) => x.host === host)
  if (!s?.ok || !s.csf) return null
  if (s.deny.some((d) => d.ip === ip)) return 'deny'
  if (s.sementara.some((d) => d.ip === ip)) return 'sementara'
  if (s.allow.some((d) => d.ip === ip)) return 'allow'
  return null
}
const namaHost = (h) => servers.value.find((s) => s.host === h)?.name || h
async function aksiFirewall(aksi, ip, host) {
  if (perluNama()) return
  const ya = await konfirmasi(aksi === 'blokir'
    ? { judul: `Blokir ${ip} 24 jam?`, teks: `Diblokir di CSF ${namaHost(host)}. Durasi lain & semua server: halaman Proteksi.`, tombol: 'Blokir 24 jam', kelas: 'bahaya' }
    : { judul: `Lepas blokir ${ip}?`, teks: `Blokir permanen & sementara IP ini dihapus di ${namaHost(host)}.`, tombol: 'Lepas blokir' })
  if (!ya) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/firewall/aksi', { aksi, ip, server: host, ttl: 86400, ket: 'dari halaman WAF', oleh: oleh.value.trim() })
    const h = r.servers?.[0]
    if (!h?.ok) throw new Error(h?.error || 'gagal')
    Object.assign(pesan, { teks: aksi === 'blokir' ? `${ip} diblokir 24 jam di ${namaHost(host)}.` : `Blokir ${ip} dilepas di ${namaHost(host)}.`, galat: false })
    fw.value = await minta('/api/servers/firewall?segar=1')
  } catch (e) {
    Object.assign(pesan, { teks: `${ip}: ${e.message}`, galat: true })
  } finally {
    proses.value = false
  }
}
async function cekIp(ip) {
  try {
    const r = await minta(`/api/servers/firewall/cek?ip=${encodeURIComponent(ip)}`)
    const di = r.servers.filter((c) => c.deny?.length || c.sementara?.length).map((c) => c.name)
    Object.assign(pesan, { teks: di.length ? `${ip} terblokir di: ${di.join(', ')}.` : `${ip} tidak diblokir di server mana pun.`, galat: false })
  } catch (e) {
    Object.assign(pesan, { teks: `${ip}: ${e.message}`, galat: true })
  }
}

// ---- Aturan ----
const AKSI_ATURAN = {
  429: ['merah', '429 Bot'], 403: ['merah', '403 Ditolak'], 406: ['ungu', '406 Rate limit'], catat: ['abu', 'Hanya dicatat'],
  ai_pencarian: ['kuning', 'Ikut setelan'],
}
const aksiAturan = (a) => {
  const s = lokal.value?.setelan
  if (a.opsional && s && !s[a.opsional]) return ['abu', 'Dimatikan']
  if (a.aksi === 'ai_pencarian') return s?.ai_pencarian === 'blokir' ? AKSI_ATURAN[429] : AKSI_ATURAN.catat
  return AKSI_ATURAN[a.aksi] || AKSI_ATURAN.catat
}
const bagianAturan = computed(() => {
  const out = []
  for (const a of aturan.data.value?.aturan || []) {
    const nama = a.bagian.replace(/^\d+\.\s*/, '')
    const b = out.find((x) => x.nama === nama)
    if (b) b.isi.push(a); else out.push({ nama, isi: [a] })
  }
  return out
})
const NAMA_DATA = {
  'bot-jahat.txt': 'Scanner & bot jahat', 'bot-seo.txt': 'Crawler SEO', 'bot-ai.txt': 'Crawler AI',
  'bot-ai-pencarian.txt': 'Bot AI pencarian', 'klien-skrip.txt': 'Klien HTTP skrip', 'ip-putih.txt': 'IP putih bawaan',
}
const bukaData = ref('')

// ---- Setelan ----
const form = reactive({ seo: true, ai: true, ai_pencarian: 'catat', xmlrpc: 10, login: 10, ip_putih: [] })
const ipBaru = reactive({ ip: '', ket: '' })
function isiForm() {
  const s = lokal.value?.setelan
  if (s) Object.assign(form, { ...s, ip_putih: s.ip_putih.map((x) => ({ ...x })) })
}
watch(lokal, (b, l) => { if (!l) isiForm() }, { immediate: true })
const berubah = computed(() => lokal.value && JSON.stringify({ ...form }) !== JSON.stringify(lokal.value.setelan))
function tambahIp() {
  const ip = ipBaru.ip.trim()
  if (!ip) return
  if (!form.ip_putih.some((x) => x.ip === ip)) form.ip_putih.push({ ip, ket: ipBaru.ket.trim() })
  Object.assign(ipBaru, { ip: '', ket: '' })
}
async function simpanSetelan() {
  if (perluNama()) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/waf/setelan', { setelan: { ...form }, oleh: oleh.value.trim() })
    waf.data.value = { ...waf.data.value, lokal: r }
    isiForm()
    Object.assign(pesan, { teks: `Setelan disimpan. ${jumlahTerpasang.value ? `Tekan "Perbarui" di tiap server (${jumlahTerpasang.value} terpasang) agar berlaku.` : 'Berlaku saat WAF dipasang.'}`, galat: false })
    riwayat.muatUlang()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}

// ---- Riwayat ----
const riwayatServer = computed(() => (riwayat.data.value?.riwayat || []).filter((r) => r.aksi === 'setelan' || !terpilih.value || r.host === terpilih.value.host))
const AKSI_LABEL = { pasang: ['biru', 'Pasang'], copot: ['merah', 'Copot'], setelan: ['ungu', 'Ubah setelan'] }
const ringkasSetelan = (s) => Object.entries(s || {}).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join(' ') || '(kosong)' : v}`).join(', ') || 'tanpa perubahan'
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>WAF Server <span class="merek-guard">VelocityGuard</span></h1>
        <p class="redup">Velocity WAF — aturan ModSecurity pengganti cPGuard: blokir bot jahat, probe berkas sensitif, dan brute force WordPress di tiap server hosting.</p>
      </div>
      <div class="kepala-aksi">
        <div class="nama-saya"><span class="redup">Dicatat sebagai</span><PelakuAkun id="nama-waf" /></div>
        <button type="button" class="tombol kecil" :disabled="segarkan || (waf.memuat.value && !waf.data.value)" @click="muatSegar"><Ikon nama="ulang" :ukuran="16" /> {{ segarkan ? 'Membaca…' : 'Muat ulang' }}</button>
      </div>
    </header>

    <div v-if="waf.memuat.value && !waf.data.value" class="skeleton" aria-busy="true">
      <p class="redup status-muat" role="status">Membaca status WAF semua server lewat SSH (±5–10 detik)…</p>
      <div class="ringkas">
        <div v-for="i in 4" :key="i" class="kartu tile"><span class="sk sk-ikon" /><div><span class="sk sk-teks" /><span class="sk sk-angka" /><span class="sk sk-teks pendek" /></div></div>
      </div>
      <div class="sk-menu"><span v-for="i in 5" :key="i" class="sk sk-pil" /></div>
      <section class="kartu"><span class="sk sk-judul" /><div v-for="i in 4" :key="i" class="sk-baris"><span v-for="j in 3" :key="j" class="sk" /></div></section>
    </div>

    <p v-else-if="waf.galat.value && !waf.data.value" class="pesan-status bahaya">Gagal memuat: {{ waf.galat.value.message }}</p>
    <p v-else-if="waf.data.value?.error" class="pesan-status bahaya">Gagal memuat: {{ pesanGalat(waf.data.value.error) }}</p>

    <template v-else-if="waf.data.value">
      <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>

      <PilihServer v-if="terpilih" :servers="servers" :model-value="terpilih?.name" :titik="keadaan(terpilih).titik" :teks="(s) => s.name + (berjalan(s.host) ? ' · perubahan berjalan' : '')" @update:model-value="pilih = $event" />

      <!-- Ringkasan server terpilih -->
      <div v-if="terpilih?.ok" class="ringkas">
        <div class="kartu tile">
          <span class="tile-ikon" :class="!terpasang(terpilih) ? 'merah' : st(terpilih).mode === 'blokir' ? 'hijau' : 'kuning'"><Ikon nama="waf" :ukuran="20" /></span>
          <div><span class="redup">Velocity WAF</span><b>{{ !terpasang(terpilih) ? 'Belum' : st(terpilih).mode === 'blokir' ? 'Mode blokir' : 'Mode deteksi' }}</b><small class="redup">{{ terpasang(terpilih) ? `versi ${st(terpilih).versi}` : 'belum dipasang' }}</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon" :class="perluUpdate(terpilih) ? 'kuning' : 'biru'"><Ikon nama="ulang" :ukuran="20" /></span>
          <div><span class="redup">Ruleset</span><b>{{ !terpasang(terpilih) ? '–' : perluUpdate(terpilih) ? 'Perlu diperbarui' : 'Terbaru' }}</b><small class="redup">dashboard {{ lokal?.versi }} · sidik {{ lokal?.sidik }}</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon ungu"><Ikon nama="perisai" :ukuran="20" /></span>
          <div><span class="redup">cPGuard WAF</span><b>{{ st(terpilih).cpguard ? 'Aktif' : 'Tidak aktif' }}</b><small class="redup">dicopot = aturannya ikut hilang</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon" :class="tanpaWaf(terpilih) ? 'merah' : 'hijau'"><Ikon :nama="tanpaWaf(terpilih) ? 'peringatan' : 'centang'" :ukuran="20" /></span>
          <div><span class="redup">Perlindungan</span><b>{{ tanpaWaf(terpilih) ? 'Tanpa WAF' : 'Terlindungi' }}</b><small class="redup">dibaca {{ waktuLalu(waf.data.value.diambil) }}</small></div>
        </div>
      </div>

      <section v-if="terpilih" class="kartu" aria-labelledby="judul-detail">
        <div class="kartu-judul">
          <h2 id="judul-detail"><Ikon nama="waf" :ukuran="16" /> {{ terpilih.name }}
            <span class="lencana" :class="keadaan(terpilih).kelas">{{ keadaan(terpilih).label }}</span>
            <span v-if="perluUpdate(terpilih)" class="lencana kuning">PERLU DIPERBARUI</span>
          </h2>
          <div class="tab" role="tablist" aria-label="Bagian WAF">
            <button v-for="t in [
              { k: 'status', label: 'Status' }, { k: 'log', label: 'Log' },
              { k: 'aturan', label: 'Aturan', n: aturan.data.value?.aturan?.length },
              { k: 'setelan', label: 'Setelan' }, { k: 'riwayat', label: 'Riwayat', n: riwayatServer.length },
            ]" :key="t.k" type="button" role="tab" :aria-selected="tab === t.k" :class="{ aktif: tab === t.k }" @click="tab = t.k">
              {{ t.label }} <span v-if="t.n" class="hitung">{{ t.n }}</span>
            </button>
          </div>
        </div>

        <!-- ================= Status ================= -->
        <template v-if="tab === 'status'">
          <p v-if="!terpilih.ok" class="pesan-status bahaya">Tidak bisa dibaca: {{ pesanGalat(terpilih.error) }}</p>
          <template v-else>
            <dl class="fakta">
              <div><dt>Velocity WAF</dt><dd>
                <template v-if="terpasang(terpilih)"><b>Aktif</b> · mode {{ st(terpilih).mode }} · versi <code>{{ st(terpilih).versi }}</code><small class="redup blok">dipasang {{ tanggalWaktu(st(terpilih).diubah) }}</small></template>
                <template v-else-if="st(terpilih).berkas_ada">Tidak aktif <small class="redup blok">berkas /etc/velocity-waf masih ada (versi {{ st(terpilih).versi }})</small></template>
                <template v-else>Belum pernah dipasang</template>
              </dd></div>
              <div><dt>Ruleset & setelan</dt><dd>
                <template v-if="!terpasang(terpilih)">—</template>
                <template v-else-if="perluUpdate(terpilih)"><span class="kuning-teks"><b>Berbeda</b></span> dari dashboard <small class="redup blok">server <code>{{ st(terpilih).sidik || 'tanpa sidik' }}</code> · dashboard <code>{{ lokal.sidik }}</code></small></template>
                <template v-else><span class="hijau-teks"><b>Terbaru</b></span> <small class="redup blok">sidik <code>{{ lokal.sidik }}</code></small></template>
              </dd></div>
              <div><dt>cPGuard WAF</dt><dd>
                <template v-if="st(terpilih).cpguard"><b>Aktif</b> · {{ st(terpilih).cpguard_aturan }} berkas aturan <small class="redup blok">hilang saat cPGuard dicopot</small></template>
                <template v-else>Tidak aktif</template>
              </dd></div>
              <div><dt>Platform</dt><dd>
                LiteSpeed {{ st(terpilih).lsws ? '✓' : '✗' }} · ModSecurity {{ st(terpilih).modsecurity_d ? '✓' : '✗' }}
                <small class="redup blok">{{ st(terpilih).cadangan }} salinan cadangan /etc/velocity-waf.bak-*</small>
              </dd></div>
            </dl>

            <!-- Job berjalan / hasil terakhir -->
            <div v-if="jobServer" class="job" :class="jobServer.status">
              <template v-if="jobServer.status === 'berjalan'">
                <span class="putar besar" aria-hidden="true" />
                <div role="status"><b>{{ jobServer.aksi === 'copot' ? 'Mencopot' : `Memasang mode ${jobServer.mode}` }}…</b>
                  <span class="redup"> menulis berkas, restart LiteSpeed, uji situs · {{ durasi(jobServer) }}</span></div>
              </template>
              <template v-else>
                <Ikon :nama="jobServer.status === 'selesai' ? 'centang' : 'peringatan'" :ukuran="20" />
                <div>
                  <b>{{ jobServer.status === 'selesai' ? 'Berhasil' : 'Gagal' }}</b> · {{ jobServer.aksi === 'copot' ? 'copot' : `pasang mode ${jobServer.mode}` }} · {{ durasi(jobServer) }}
                  <span v-if="jobServer.status !== 'selesai'" class="blok">{{ pesanGalat(jobServer.hasil?.error) }} {{ jobServer.hasil?.alasan || '' }}</span>
                  <small v-if="jobServer.hasil?.domain" class="redup blok">Uji di {{ jobServer.hasil.domain }}: HTTP sebelum {{ jobServer.hasil.http_sebelum }} → sesudah {{ jobServer.hasil.http_sesudah }} · UA sqlmap {{ jobServer.hasil.http_uji_sqlmap }}{{ jobServer.hasil.tercatat ? ' (tercatat)' : '' }}</small>
                  <small v-if="jobServer.hasil?.peringatan" class="kuning-teks blok">{{ jobServer.hasil.peringatan }}</small>
                  <small v-for="g in jobServer.hasil?.galat || []" :key="g" class="merah-teks blok"><code>{{ g }}</code></small>
                </div>
              </template>
            </div>

            <div v-if="st(terpilih).lsws && st(terpilih).modsecurity_d" class="aksi-waf">
              <template v-if="!terpasang(terpilih)">
                <button type="button" class="tombol" :disabled="proses || berjalan(terpilih.host)" @click="jalankan('pasang-deteksi')"><Ikon nama="waf" :ukuran="16" /> Pasang mode deteksi</button>
                <button type="button" class="tombol garis" :disabled="proses || berjalan(terpilih.host)" @click="jalankan('pasang-blokir')">Pasang langsung mode blokir</button>
              </template>
              <template v-else>
                <button v-if="perluUpdate(terpilih)" type="button" class="tombol" :disabled="proses || berjalan(terpilih.host)" @click="jalankan('perbarui')"><Ikon nama="ulang" :ukuran="16" /> Perbarui</button>
                <button v-if="st(terpilih).mode !== 'blokir'" type="button" class="tombol" :class="{ garis: perluUpdate(terpilih) }" :disabled="proses || berjalan(terpilih.host)" @click="jalankan('pasang-blokir')">Ganti ke mode blokir</button>
                <button v-else type="button" class="tombol garis" :disabled="proses || berjalan(terpilih.host)" @click="jalankan('pasang-deteksi')">Ganti ke mode deteksi</button>
                <button type="button" class="tombol bahaya garis" :disabled="proses || berjalan(terpilih.host)" @click="jalankan('copot')">Copot</button>
              </template>
            </div>

            <ol class="tahap" aria-label="Urutan peralihan dari cPGuard">
              <li :class="{ selesai: terpasang(terpilih) }"><b>Pasang mode deteksi</b><span class="redup">Berdampingan dengan cPGuard; aturan hanya mencatat.</span></li>
              <li :class="{ selesai: terpasang(terpilih) && st(terpilih).mode === 'blokir' }"><b>Pantau tab Log 1–2 minggu</b><span class="redup">Pastikan tidak ada situs/pengunjung sah yang kena (positif palsu); tambahkan IP putih bila perlu.</span></li>
              <li :class="{ selesai: !st(terpilih).cpguard }"><b>Copot cPGuard</b><span class="redup">Atas izin, per server.</span></li>
              <li :class="{ selesai: terpasang(terpilih) && st(terpilih).mode === 'blokir' }"><b>Ganti ke mode blokir</b><span class="redup">Segera sesudah cPGuard dicopot supaya server tidak tanpa perlindungan.</span></li>
            </ol>
          </template>
        </template>

        <!-- ================= Log ================= -->
        <LogWaf v-else-if="tab === 'log'" :server="terpilih.host" :status="statusIp" :proses="proses"
          @blokir="(ip, host) => aksiFirewall('blokir', ip, host)" @lepas="(ip, host) => aksiFirewall('lepas', ip, host)" @cek="cekIp" />

        <!-- ================= Aturan ================= -->
        <template v-else-if="tab === 'aturan'">
          <p class="redup kaki-form">Aksi di bawah berlaku pada mode <b>blokir</b>; di mode deteksi semua aturan hanya mencatat. ID 7700000–7709999, sumber <code>waf/velocity-waf.conf.in</code>.
            <Info label="Tentang aturan" rata="kanan"><p>Injeksi SQL/XSS dan klien skrip (python-requests dll.) sengaja selalu hanya dicatat — bisa saja callback payment gateway atau integrasi sah. Rate limit xmlrpc.php / wp-login.php hanya menolak berkas itu, bukan seluruh situs, karena banyak pengunjung berbagi IP (CGNAT seluler).</p></Info>
          </p>
          <p v-if="aturan.memuat.value" class="redup">Memuat…</p>
          <div v-for="b in bagianAturan" :key="b.nama" class="kelompok">
            <h3>{{ b.nama }}</h3>
            <ul class="aturan">
              <li v-for="a in b.isi" :key="a.id">
                <code class="redup">{{ a.id }}</code>
                <span>{{ a.pesan }}<template v-if="a.id === '7700501'"> · maks {{ lokal?.setelan.xmlrpc }} POST/menit, blokir 10 mnt</template><template v-else-if="a.id === '7700511'"> · maks {{ lokal?.setelan.login }} POST/5 menit, blokir 15 mnt</template></span>
                <span class="lencana" :class="aksiAturan(a)[0]">{{ aksiAturan(a)[1] }}</span>
              </li>
            </ul>
          </div>
          <div v-if="aturan.data.value" class="kelompok">
            <h3>Daftar pola</h3>
            <div class="data-daftar">
              <button v-for="(d, nama) in aturan.data.value.data" :key="nama" type="button" class="chip" :class="{ aktif: bukaData === nama }" :aria-expanded="bukaData === nama" @click="bukaData = bukaData === nama ? '' : nama">
                {{ NAMA_DATA[nama] || nama }} <b>{{ d.isi.length }}</b>
              </button>
            </div>
            <div v-if="bukaData" class="isi-data">
              <p class="redup">{{ aturan.data.value.data[bukaData].ket }}</p>
              <p class="pola"><code v-for="x in aturan.data.value.data[bukaData].isi" :key="x">{{ x }}</code></p>
            </div>
          </div>
        </template>

        <!-- ================= Setelan ================= -->
        <form v-else-if="tab === 'setelan'" class="setelan" @submit.prevent="simpanSetelan">
          <p class="redup kaki-form">Berlaku untuk <b>semua server</b>. Sesudah disimpan, server yang sudah terpasang ditandai "Perlu diperbarui" — tekan <b>Perbarui</b> per server.</p>
          <fieldset>
            <legend>Crawler</legend>
            <label class="cek"><input v-model="form.seo" type="checkbox"> Blokir crawler SEO komersial <small class="redup">Ahrefs, Semrush, Majestic… matikan bila ada klien yang memakainya</small></label>
            <label class="cek"><input v-model="form.ai" type="checkbox"> Blokir crawler pelatihan AI <small class="redup">GPTBot, ClaudeBot, Meta-ExternalAgent, Bytespider…</small></label>
            <div class="baris-pil">
              <span>Bot AI pencarian <small class="redup">(ChatGPT-User, OAI-SearchBot, Perplexity — situs bisa dikutip AI)</small></span>
              <div class="pil-durasi" role="radiogroup" aria-label="Bot AI pencarian">
                <label :class="{ aktif: form.ai_pencarian === 'catat' }"><input v-model="form.ai_pencarian" type="radio" class="sr" value="catat"> Hanya catat</label>
                <label :class="{ aktif: form.ai_pencarian === 'blokir' }"><input v-model="form.ai_pencarian" type="radio" class="sr" value="blokir"> Blokir</label>
              </div>
            </div>
          </fieldset>
          <fieldset>
            <legend>Rate limit brute force (per IP)</legend>
            <div class="dua">
              <label class="isian"><span>xmlrpc.php — maks. POST per menit</span><input v-model.number="form.xmlrpc" type="number" min="3" max="200" required></label>
              <label class="isian"><span>wp-login.php — maks. POST per 5 menit</span><input v-model.number="form.login" type="number" min="3" max="200" required></label>
            </div>
          </fieldset>
          <fieldset>
            <legend>IP putih tambahan <Info label="Tentang IP putih"><p>IP/CIDR di sini melewati semua aturan Velocity WAF (mis. IP kantor cabang, monitoring uptime, server klien yang memanggil API). Ditambahkan ke daftar bawaan ({{ aturan.data.value?.data['ip-putih.txt']?.isi.length || 0 }} IP). Paling lebar /16.</p></Info></legend>
            <ul v-if="form.ip_putih.length" class="ip-putih">
              <li v-for="(x, i) in form.ip_putih" :key="x.ip"><code>{{ x.ip }}</code> <span class="redup">{{ x.ket }}</span>
                <button type="button" class="tombol garis kecil" :aria-label="`Hapus ${x.ip}`" @click="form.ip_putih.splice(i, 1)">Hapus</button></li>
            </ul>
            <div class="tambah-ip">
              <input v-model="ipBaru.ip" placeholder="IP atau CIDR" aria-label="IP atau CIDR" @keydown.enter.prevent="tambahIp">
              <input v-model="ipBaru.ket" placeholder="Keterangan" aria-label="Keterangan" maxlength="80" @keydown.enter.prevent="tambahIp">
              <button type="button" class="tombol garis kecil" :disabled="!ipBaru.ip.trim()" @click="tambahIp">Tambah</button>
            </div>
          </fieldset>
          <div class="kaki-setelan">
            <button type="submit" class="tombol" :disabled="proses || !berubah">Simpan setelan</button>
            <button v-if="berubah" type="button" class="tombol garis" @click="isiForm">Batalkan perubahan</button>
          </div>
        </form>

        <!-- ================= Riwayat ================= -->
        <template v-else-if="tab === 'riwayat'">
          <p v-if="!riwayatServer.length" class="redup">Belum ada perubahan WAF dari dashboard.</p>
          <ul v-else class="kejadian">
            <li v-for="(r, i) in riwayatServer" :key="i">
              <span class="titik" :class="r.ok ? AKSI_LABEL[r.aksi]?.[0] : 'abu'" aria-hidden="true" />
              <div>
                <b>{{ AKSI_LABEL[r.aksi]?.[1] || r.aksi }}</b><template v-if="r.mode"> mode {{ r.mode }}</template><template v-if="r.server"> · {{ r.server }}</template>
                <template v-if="r.aksi === 'setelan'"> <span class="redup">semua server · {{ ringkasSetelan(r.setelan) }}</span></template>
                <span v-if="!r.ok" class="lencana merah">GAGAL · {{ pesanGalat(r.error) }}</span>
                <small class="redup blok">{{ r.oleh }}<template v-if="r.domain"> · uji {{ r.domain }} HTTP {{ (r.http || []).join(' → ') }}</template><template v-if="r.alasan"> · {{ r.alasan }}</template><template v-if="r.peringatan"> · {{ r.peringatan }}</template></small>
              </div>
              <time class="redup">{{ tanggalWaktu(r.t) }}</time>
            </li>
          </ul>
        </template>
      </section>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.kepala-aksi { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.nama-saya { display: grid; gap: 4px; font-size: 12px; }

.ringkas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.kartu-judul { flex-wrap: wrap; gap: 10px; }
.kartu-judul h2 { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tile { display: flex; gap: 14px; align-items: center; }
.tile > div { display: grid; gap: 3px; min-width: 0; }
.tile b { font-size: 24px; color: var(--teks-kuat); }
.tile small { font-size: 12px; overflow-wrap: anywhere; }
.tile-ikon { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; }
.tile-ikon.merah { color: var(--bahaya); background: color-mix(in srgb, var(--bahaya) 15%, transparent); }
.tile-ikon.kuning { color: var(--waspada); background: color-mix(in srgb, var(--waspada) 15%, transparent); }
.tile-ikon.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 15%, transparent); }
.tile-ikon.hijau { color: var(--baik); background: color-mix(in srgb, var(--baik) 15%, transparent); }
.tile-ikon.biru { color: var(--aksen-terang); background: var(--aksen-lembut); }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); vertical-align: 1px; }
.titik.baik, .titik.hijau { background: var(--baik); }
.titik.waspada, .titik.kuning { background: var(--waspada); }
.titik.bahaya, .titik.merah { background: var(--bahaya); }
.titik.biru { background: var(--aksen-terang); }
.titik.ungu { background: var(--ungu); }
.lencana.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 14%, transparent); }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
/* Status */
.fakta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0 0 16px; }
.fakta > div { padding: 12px 14px; border-radius: 10px; background: var(--kartu-2); min-width: 0; }
.fakta dt { font-size: 12px; color: var(--teks-2); margin-bottom: 4px; }
.fakta dd { margin: 0; font-size: 13.5px; overflow-wrap: anywhere; }
.job { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 12px; align-items: center; padding: 12px 14px; border-radius: 12px; margin-bottom: 16px;
  background: var(--kartu-2); border: 1px solid var(--garis); font-size: 13.5px; }
.job.selesai { border-color: color-mix(in srgb, var(--baik) 50%, transparent); color: var(--teks); }
.job.selesai > svg { color: var(--baik); }
.job.gagal { border-color: color-mix(in srgb, var(--bahaya) 50%, transparent); }
.job.gagal > svg { color: var(--bahaya); }
.aksi-waf { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
.tahap { list-style: none; margin: 0; padding: 16px 0 0; border-top: 1px solid var(--garis); display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; counter-reset: tahap; }
.tahap li { display: grid; gap: 4px; align-content: start; font-size: 13px; padding-left: 34px; position: relative; counter-increment: tahap; }
.tahap li::before { content: counter(tahap); position: absolute; left: 0; top: -2px; width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center;
  font-size: 12px; font-weight: 700; background: var(--kartu-2); color: var(--teks-2); border: 1px solid var(--garis); }
.tahap li.selesai::before { content: '✓'; background: var(--baik); border-color: var(--baik); color: #fff; }
.tahap li span { font-size: 12.5px; }
/* Aturan */
.kelompok { margin-bottom: 18px; }
.kelompok h3 { font-size: 13.5px; margin: 0 0 8px; color: var(--teks-kuat); }
.aturan { list-style: none; margin: 0; padding: 0; display: grid; }
.aturan li { display: grid; grid-template-columns: 70px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 8px 2px; border-bottom: 1px solid var(--garis); font-size: 13.5px; }
.aturan li:last-child { border-bottom: 0; }
.data-daftar { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { border: 1px solid var(--garis); background: transparent; color: var(--teks-2); font: inherit; font-size: 12.5px; padding: 5px 11px; border-radius: 999px; cursor: pointer; }
.chip:hover, .chip.aktif { border-color: var(--aksen-terang); color: var(--teks-kuat); }
.isi-data { margin-top: 10px; padding: 12px; border-radius: 10px; background: var(--kartu-2); font-size: 13px; }
.isi-data p { margin: 0 0 8px; }
.pola { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 !important; }
.pola code { padding: 2px 7px; border-radius: 6px; background: var(--kartu); border: 1px solid var(--garis); }
/* Setelan */
.setelan { display: grid; gap: 16px; }
.setelan fieldset { margin: 0; padding: 14px; border: 1px solid var(--garis); border-radius: 12px; display: grid; gap: 12px; min-width: 0; }
.setelan legend { display: inline-flex; align-items: center; gap: 4px; padding: 0 6px; font-size: 13px; font-weight: 600; color: var(--teks-kuat); }
.cek { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; font-size: 13.5px; cursor: pointer; }
.cek small { font-size: 12px; }
.baris-pil { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 13.5px; }
.pil-durasi { display: flex; flex-wrap: wrap; gap: 6px; }
.pil-durasi label { border: 1px solid var(--garis); border-radius: 9px; padding: 8px 12px; font-size: 13px; cursor: pointer; color: var(--teks-2); }
.pil-durasi label.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); color: var(--aksen-terang); font-weight: 600; }
.pil-durasi label:focus-within { outline: 2px solid var(--aksen-terang); outline-offset: 2px; }
.dua { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; align-items: end; }
.isian { display: grid; gap: 6px; font-size: 12.5px; color: var(--teks-2); min-width: 0; }
.isian input { width: 100%; }
.ip-putih { list-style: none; margin: 0; padding: 0; display: grid; }
.ip-putih li { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 10px; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--garis); font-size: 13px; }
.tambah-ip { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) auto; gap: 8px; }
.tambah-ip input { min-width: 0; }
.kaki-setelan { display: flex; gap: 10px; flex-wrap: wrap; }
.kaki-form { margin: 0 0 16px; font-size: 13px; line-height: 1.55; }
/* Riwayat */
.kejadian { list-style: none; margin: 0; padding: 0; display: grid; }
.kejadian li { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 2px; border-bottom: 1px solid var(--garis); font-size: 13.5px; }
.kejadian li:last-child { border-bottom: 0; }
.kejadian li > div { overflow-wrap: anywhere; }
.kejadian time { font-size: 12.5px; white-space: nowrap; }
.merah-teks { color: var(--bahaya); }
.kuning-teks { color: var(--waspada); }
.hijau-teks { color: var(--baik); }
.blok { display: block; }
.putar { display: inline-block; width: 12px; height: 12px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: putar .8s linear infinite; vertical-align: -1px; }
.putar.besar { width: 22px; height: 22px; color: var(--aksen-terang); }
@keyframes putar { to { transform: rotate(360deg); } }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
/* Skeleton */
.skeleton { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; }
.status-muat { margin: 0; }
.skeleton .tile > div { flex: 1; }
.skeleton .tile { min-height: 112px; }
.sk { --sk-dasar: color-mix(in srgb, var(--kartu-2), var(--teks) 7%); --sk-kilap: color-mix(in srgb, var(--kartu-2), var(--teks) 15%);
  display: block; border-radius: 6px; background: linear-gradient(90deg, var(--sk-dasar) 25%, var(--sk-kilap) 50%, var(--sk-dasar) 75%); background-size: 200% 100%; animation: sk-kilau 1.4s ease-in-out infinite; }
.sk-ikon { flex: none; width: 44px; height: 44px; border-radius: 12px; }
.sk-teks { height: 11px; width: 60%; margin: 4px 0; }
.sk-teks.pendek { width: 40%; }
.sk-angka { height: 22px; width: 45%; margin: 4px 0; }
.sk-menu { display: flex; gap: 8px; padding: 8px; border-radius: 12px; background: var(--kartu); border: 1px solid var(--garis); overflow: hidden; }
.sk-pil { flex: none; height: 30px; width: 96px; border-radius: 9px; }
.sk-judul { height: 14px; width: 200px; max-width: 60%; margin-bottom: 18px; }
.sk-baris { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 16px; padding: 14px 0; border-top: 1px solid var(--garis); }
.sk-baris .sk { height: 12px; }
@keyframes sk-kilau { from { background-position: 100% 0; } to { background-position: -100% 0; } }
@media (prefers-reduced-motion: reduce) { .sk, .putar { animation: none; } }
@media (max-width: 900px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
  .tahap { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 560px) {
  .ringkas, .fakta, .tahap, .dua { grid-template-columns: 1fr; }
  .nama-saya { width: 100%; }
  .kepala-aksi { width: 100%; }
  .tambah-ip { grid-template-columns: 1fr; }
  .tambah-ip .tombol { justify-self: start; }
  .aturan li { grid-template-columns: minmax(0, 1fr) auto; }
  .aturan li code { grid-column: 1 / -1; }
  .kejadian li { grid-template-columns: 8px minmax(0, 1fr); }
  .kejadian time { grid-column: 2; }
}
</style>
