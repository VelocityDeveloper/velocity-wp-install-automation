<script setup>
// Brute Force (sub-menu Server): pengganti BFM cPGuard. BFM cPGuard ±99% berisi hit WAF (bot, crawler, probe) yang
// diubah jadi blokir CSF; penggantinya = blok aturan LFD (regex.custom.pm) yang memblokir IP berulang kali DITOLAK
// Velocity WAF. Data: GET /api/servers/bfm (installer_status.py → scripts/server_bfm_agent.py, termasuk simulasi
// 24 jam dari log WAF). Pasang/copot: POST /api/servers/bfm/aksi → job latar (csf -r + restart lfd, rollback otomatis).
// Ambang & durasi bersama semua server: POST /api/servers/bfm/setelan.
import PilihServer from '../components/PilihServer.vue'
import { pilihServer } from '../jenisServer.js'
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import Ikon from '../components/Ikon.vue'
import PelakuAkun from '../components/PelakuAkun.vue'
import { namaAkun } from '../akun.js'
import Info from '../components/Info.vue'
import { konfirmasi } from '../konfirmasi.js'
import { minta, kirim, pakaiPolling, tanggalWaktu, waktuLalu, angka } from '../api.js'
import { tabUrl } from '../laravel.js'

const bfm = pakaiPolling('/api/servers/bfm', 300000)
const riwayat = pakaiPolling('/api/servers/bfm/riwayat', 0)
const segarkan = ref(false)
async function muatSegar() {
  segarkan.value = true
  try { bfm.data.value = await minta('/api/servers/bfm?segar=1'); bfm.galat.value = null }
  catch (e) { bfm.galat.value = e }
  finally { segarkan.value = false }
  riwayat.muatUlang()
}
const servers = computed(() => bfm.data.value?.servers || [])
const lokal = computed(() => bfm.data.value?.lokal || null)
const pilih = pilihServer()
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || servers.value[0] || null)
const TAB = ['status', 'setelan', 'riwayat']
const tab = tabUrl('tab', 'status', { boleh: TAB })

// Pelaku di riwayat = akun yang masuk ke dash.velocity.ai.id (backend menggantinya dari cookie sesi)
const oleh = namaAkun

const PESAN = {
  invalid_oleh: 'Masuk dulu lewat tombol "Masuk dengan VD.net" di kanan atas — setiap perubahan dicatat atas nama akun Anda.',
  login_diperlukan: 'Sesi login habis atau belum masuk. Klik "Masuk dengan VD.net" di kanan atas.',
  server_tidak_dikenal: 'Server tidak dikenal; muat ulang halaman.',
  aksi_sedang_jalan: 'Masih ada perubahan berjalan di server ini. Tunggu selesai dulu.',
  csf_tidak_ada: 'CSF tidak ditemukan di server ini.',
  regex_custom_tidak_dikenal: '/etc/csf/regex.custom.pm bentuknya tidak dikenal — tidak diubah.',
  slot_custom_log_penuh: 'Semua CUSTOM1–9_LOG di csf.conf sudah terpakai.',
  dikembalikan: 'lfd gagal jalan dengan aturan baru — csf.conf & regex.custom.pm dikembalikan.',
  setelan_tidak_sah: 'Ada nilai setelan di luar batas.',
  job_tidak_ada: 'Status perubahan hilang (layanan dashboard di-restart). Cek ulang status server.',
  forbidden: 'Ditolak: hanya bisa dijalankan dari halaman dashboard ini.',
  timeout: 'Server tidak menjawab (timeout).',
}
const pesanGalat = (e) => PESAN[e] || e || 'gagal'
const pesan = reactive({ teks: '', galat: false })
const proses = ref(false)
function perluNama() {
  if (oleh.value.trim()) return false
  Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true })
  document.getElementById('nama-bfm')?.focus()
  return true
}

// ---- Ringkasan ----
const limit = (s) => Number(s?.csf?.DENY_IP_LIMIT || 0)
const terpasang = (s) => !!s?.blok?.terpasang
const perluUpdate = (s) => terpasang(s) && lokal.value && s.blok.sidik !== lokal.value.sidik
const simBlokir = (s) => Object.values(s?.simulasi?.aturan || {}).reduce((a, x) => a + (x.blokir || 0), 0)
// Kartu ringkasan untuk server terpilih saja
const total = computed(() => {
  const s = terpilih.value
  const deny = s.deny.total
  const cpg = s.deny.sumber.cpguard
  return {
    deny, cpg, persenCpg: deny ? Math.round((cpg / deny) * 100) : 0,
    penuh: !!(limit(s) && deny >= limit(s)),
    sim: simBlokir(s),
    cpg24: s.cpguard?.ip || 0,
  }
})
const jumlahTerpasang = computed(() => servers.value.filter((s) => s.ok && terpasang(s)).length)
function titik(s) {
  if (!s.ok || !s.lfd_aktif) return 'bahaya'
  if (terpasang(s)) return perluUpdate(s) ? 'waspada' : 'baik'
  return limit(s) && s.deny.total >= limit(s) ? 'waspada' : 'abu'
}

const SUMBER = [
  { k: 'cpguard', label: 'cPGuard BFM', warna: '#cc7a33' },
  { k: 'lfd', label: 'LFD (login gagal)', warna: '#5b8cff' },
  { k: 'velocity', label: 'Velocity BFM', warna: '#26a88e' },
  { k: 'dashboard', label: 'Dashboard', warna: '#a679e6' },
  { k: 'lain', label: 'Lainnya', warna: '#8a8f98' },
]
const LOGIN_LFD = [
  { k: 'LF_SSHD', label: 'SSH' }, { k: 'LF_DIRECTADMIN', label: 'DirectAdmin' }, { k: 'LF_FTPD', label: 'FTP' },
  { k: 'LF_SMTPAUTH', label: 'SMTP' }, { k: 'LF_POP3D', label: 'POP3' }, { k: 'LF_IMAPD', label: 'IMAP' },
]
const durasiLabel = (d) => (d === 1 ? 'permanen' : d >= 86400 ? `${d / 86400} hari` : d >= 3600 ? `${d / 3600} jam` : `${d / 60} menit`)
const ATURAN_KET = {
  berat: 'Akses .env/.git, wp-config, dump database/cadangan/alat debug, PHP tersembunyi, null byte, path traversal, bot AI palsu — tidak pernah dilakukan pengunjung asli',
  eksploit: 'Probe lain: PHP di uploads/cache, enumerasi user (?author=), PHP tanpa User-Agent',
  bot: 'sqlmap, nikto, masscan, zgrab, dan scanner lain (bot-jahat.txt)',
  crawler: 'Ahrefs, Semrush, PetalBot, Baiduspider… (bot-seo.txt) — sudah ditolak 429 oleh WAF; blokir firewall hanya menghemat beban',
  ai: 'Bot pengumpul data untuk melatih model AI (GPTBot, ClaudeBot, CCBot, Bytespider… — bot-ai.txt). Tidak mendatangkan pengunjung ke situs klien; sudah ditolak 429 oleh WAF, blokir firewall hanya menghemat beban',
  pencarian: 'Bot AI yang mengambil halaman saat pengguna bertanya ke ChatGPT/Perplexity (ChatGPT-User, OAI-SearchBot, PerplexityBot dari IP resmi). Bisa membuat situs klien dikutip & mendatangkan pengunjung; WAF hanya mencatatnya, jadi aturan ini tidak memblokir apa pun selama itu. UA serupa dari IP palsu masuk Eksploit',
  login: 'IP yang terus mencoba sesudah kena rate limit wp-login.php / xmlrpc.php',
}

// ---- Job pasang/copot ----
const jobs = ref({})
let timerJob = null
watch(() => bfm.data.value?.job, (daftar) => {
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
        const baru = await minta(`/api/servers/bfm/job?id=${j.id}`)
        jobs.value = { ...jobs.value, [j.host]: baru }
        if (baru.status !== 'berjalan') {
          Object.assign(pesan, baru.status === 'selesai'
            ? { teks: `${baru.server}: Velocity BFM ${baru.aksi === 'copot' ? 'dicopot' : 'terpasang'}.`, galat: false }
            : { teks: `${baru.server}: ${pesanGalat(baru.hasil?.error)}`, galat: true })
          muatSegar()
        }
      } catch (e) {
        jobs.value = { ...jobs.value, [j.host]: { ...j, status: 'gagal', hasil: { error: e.message } } }
      }
    }
  }, 3000)
}
onBeforeUnmount(() => clearInterval(timerJob))

async function jalankan(aksi) {
  if (perluNama()) return
  const s = terpilih.value
  const ya = await konfirmasi(aksi === 'copot'
    ? { judul: `Copot Velocity BFM dari ${s.name}?`, tombol: 'Copot', kelas: 'bahaya',
      teks: 'Blok aturan dihapus dari /etc/csf/regex.custom.pm, CUSTOM log dikembalikan, lalu csf -r + restart lfd. Blokir yang sudah ada tetap.' }
    : { judul: `${terpasang(s) ? 'Perbarui' : 'Pasang'} Velocity BFM di ${s.name}?`, tombol: terpasang(s) ? 'Perbarui' : 'Pasang',
      teks: `Menambah blok aturan di /etc/csf/regex.custom.pm dan mengarahkan satu CUSTOM log ke error log LiteSpeed, lalu csf -r + restart lfd (salinan cadangan dibuat; bila lfd gagal semua dikembalikan). ${s.velocity_waf === 'blokir' ? 'Velocity WAF mode blokir → IP mulai diblokir sesuai ambang.' : 'Velocity WAF belum mode blokir → belum ada IP yang diblokir sampai WAF dialihkan ke blokir.'}` })
  if (!ya) return
  proses.value = true
  try {
    const j = await kirim('/api/servers/bfm/aksi', { aksi, server: s.host, oleh: oleh.value.trim() })
    jobs.value = { ...jobs.value, [s.host]: j }
    Object.assign(pesan, { teks: `${s.name}: perubahan berjalan…`, galat: false })
    pantauJob()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}
const durasiJob = (j) => `${Math.max(1, (j.selesai || Math.floor(Date.now() / 1000)) - j.mulai)} dtk`

// ---- Setelan ----
const form = reactive({})
function isiForm() {
  const a = lokal.value?.aturan
  if (!a) return
  for (const k of Object.keys(a)) form[k] = { ...a[k] }
}
watch(lokal, (b, l) => { if (!l) isiForm() }, { immediate: true })
const berubah = computed(() => lokal.value && JSON.stringify(form) !== JSON.stringify(lokal.value.aturan))
async function simpan() {
  if (perluNama()) return
  proses.value = true
  try {
    const r = await kirim('/api/servers/bfm/setelan', { aturan: form, oleh: oleh.value.trim() })
    bfm.data.value = { ...bfm.data.value, lokal: r }
    isiForm()
    Object.assign(pesan, { teks: `Setelan disimpan. ${jumlahTerpasang.value ? 'Tekan "Perbarui" di server yang sudah terpasang.' : ''} Simulasi dihitung ulang…`, galat: false })
    riwayat.muatUlang()
    muatSegar()
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
  } finally {
    proses.value = false
  }
}

const riwayatServer = computed(() => (riwayat.data.value?.riwayat || []).filter((r) => r.aksi === 'setelan' || !terpilih.value || r.host === terpilih.value.host))
const AKSI_LABEL = { pasang: ['biru', 'Pasang'], copot: ['merah', 'Copot'], setelan: ['ungu', 'Ubah setelan'] }
const ringkasSetelan = (s) => Object.entries(s || {}).map(([k, v]) => `${lokal.value?.label[k] || k}: ${v.aktif ? `${v.ambang}× → ${durasiLabel(v.durasi)}` : 'mati'}`).join(' · ') || 'tanpa perubahan'
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Brute Force</h1>
        <p class="redup">Pengganti BFM cPGuard: IP yang berulang kali ditolak Velocity WAF diblokir di firewall (CSF/LFD), plus deteksi login gagal SSH, DirectAdmin, FTP, dan email.</p>
      </div>
      <div class="kepala-aksi">
        <div class="nama-saya"><span class="redup">Dicatat sebagai</span><PelakuAkun id="nama-bfm" /></div>
        <button type="button" class="tombol kecil" :disabled="segarkan || (bfm.memuat.value && !bfm.data.value)" @click="muatSegar"><Ikon nama="ulang" :ukuran="16" /> {{ segarkan ? 'Membaca…' : 'Muat ulang' }}</button>
      </div>
    </header>

    <div v-if="bfm.memuat.value && !bfm.data.value" class="skeleton" aria-busy="true">
      <p class="redup status-muat" role="status">Membaca CSF, LFD, dan log WAF semua server lewat SSH…</p>
      <div class="ringkas">
        <div v-for="i in 4" :key="i" class="kartu tile"><span class="sk sk-ikon" /><div><span class="sk sk-teks" /><span class="sk sk-angka" /><span class="sk sk-teks pendek" /></div></div>
      </div>
      <section class="kartu"><span class="sk sk-judul" /><div v-for="i in 4" :key="i" class="sk-baris"><span v-for="j in 3" :key="j" class="sk" /></div></section>
    </div>

    <p v-else-if="bfm.galat.value && !bfm.data.value" class="pesan-status bahaya">Gagal memuat: {{ bfm.galat.value.message }}</p>
    <p v-else-if="bfm.data.value?.error" class="pesan-status bahaya">Gagal memuat: {{ pesanGalat(bfm.data.value.error) }}</p>

    <template v-else-if="bfm.data.value">
      <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>

      <PilihServer v-if="terpilih" :servers="servers" :model-value="terpilih?.name" :titik="titik(terpilih)" :teks="(s) => s.name + (berjalan(s.host) ? ' · perubahan berjalan' : '')" @update:model-value="pilih = $event" />

      <!-- Ringkasan server terpilih -->
      <div v-if="terpilih?.ok" class="ringkas">
        <div class="kartu tile">
          <span class="tile-ikon kuning"><Ikon nama="perisai" :ukuran="20" /></span>
          <div><span class="redup">Blokir permanen dari cPGuard</span><b>{{ total.persenCpg }}%</b><small class="redup">{{ angka(total.cpg) }} dari {{ angka(total.deny) }} IP di csf.deny</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon" :class="total.penuh ? 'merah' : 'hijau'"><Ikon :nama="total.penuh ? 'peringatan' : 'centang'" :ukuran="20" /></span>
          <div><span class="redup">csf.deny</span><b>{{ total.penuh ? 'Penuh' : 'Ada ruang' }}</b><small class="redup">{{ angka(total.deny) }}{{ limit(terpilih) ? ` / ${angka(limit(terpilih))}` : '' }} IP{{ total.penuh ? ' — blokir lama tergusur' : '' }}</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon" :class="!terpasang(terpilih) ? 'merah' : perluUpdate(terpilih) ? 'kuning' : 'biru'"><Ikon nama="kunci" :ukuran="20" /></span>
          <div><span class="redup">Velocity BFM</span><b>{{ !terpasang(terpilih) ? 'Belum' : perluUpdate(terpilih) ? 'Perlu diperbarui' : 'Terpasang' }}</b><small class="redup">aktif memblokir bila WAF mode blokir</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon ungu"><Ikon nama="pantau" :ukuran="20" /></span>
          <div><span class="redup">Simulasi 24 jam</span><b>{{ angka(total.sim) }} IP</b><small class="redup">akan diblokir Velocity · cPGuard {{ angka(total.cpg24) }} IP</small></div>
        </div>
      </div>

      <section v-if="terpilih" class="kartu" aria-labelledby="judul-detail">
        <div class="kartu-judul">
          <h2 id="judul-detail"><Ikon nama="kunci" :ukuran="16" /> {{ terpilih.name }}
            <span v-if="terpilih.ok" class="lencana" :class="terpasang(terpilih) ? 'hijau' : 'abu'">{{ terpasang(terpilih) ? 'Velocity BFM terpasang' : 'Velocity BFM belum terpasang' }}</span>
            <span v-if="perluUpdate(terpilih)" class="lencana kuning">PERLU DIPERBARUI</span>
          </h2>
          <div class="tab" role="tablist" aria-label="Bagian brute force">
            <button v-for="t in [{ k: 'status', label: 'Status' }, { k: 'setelan', label: 'Setelan' }, { k: 'riwayat', label: 'Riwayat', n: riwayatServer.length }]"
              :key="t.k" type="button" role="tab" :aria-selected="tab === t.k" :class="{ aktif: tab === t.k }" @click="tab = t.k">
              {{ t.label }} <span v-if="t.n" class="hitung">{{ t.n }}</span>
            </button>
          </div>
        </div>

        <!-- ================= Status ================= -->
        <template v-if="tab === 'status'">
          <p v-if="!terpilih.ok" class="pesan-status bahaya">Tidak bisa dibaca: {{ pesanGalat(terpilih.error) }} {{ terpilih.pesan || '' }}</p>
          <template v-else>
            <!-- Kapasitas & sumber blokir -->
            <div class="blok">
              <div class="blok-kepala">
                <b>Daftar blokir permanen (csf.deny)</b>
                <span class="redup">{{ angka(terpilih.deny.total) }} / {{ angka(limit(terpilih)) }} IP · {{ terpilih.deny.tempban }} blokir sementara · ipset {{ terpilih.csf.LF_IPSET === '1' ? 'aktif' : 'mati' }}</span>
              </div>
              <div class="batang" role="img" :aria-label="`csf.deny terisi ${terpilih.deny.total} dari ${limit(terpilih)}`">
                <span v-for="x in SUMBER" :key="x.k" :style="{ width: `${limit(terpilih) ? (terpilih.deny.sumber[x.k] / Math.max(limit(terpilih), terpilih.deny.total)) * 100 : 0}%`, background: x.warna }" :title="`${x.label}: ${terpilih.deny.sumber[x.k]}`" />
              </div>
              <ul class="legenda">
                <li v-for="x in SUMBER.filter((x) => terpilih.deny.sumber[x.k])" :key="x.k"><span class="kotak" :style="{ background: x.warna }" aria-hidden="true" /> {{ x.label }} <b>{{ angka(terpilih.deny.sumber[x.k]) }}</b></li>
              </ul>
              <p v-if="limit(terpilih) && terpilih.deny.total >= limit(terpilih)" class="pesan-status waspada kecil-p">Penuh: setiap blokir baru menggusur blokir terlama. Naikkan DENY_IP_LIMIT di Proteksi → Setelan (ipset aktif, ribuan IP tetap ringan).</p>
            </div>

            <!-- Velocity BFM -->
            <div class="blok">
              <div class="blok-kepala">
                <b>Velocity BFM — blokir dari hit WAF</b>
                <span class="redup">Velocity WAF: {{ terpilih.velocity_waf ? `mode ${terpilih.velocity_waf}` : 'belum terpasang' }} · lfd {{ terpilih.lfd_aktif ? 'aktif' : 'MATI' }}<template v-if="terpasang(terpilih)"> · {{ terpilih.blok.slot }}{{ terpilih.blok.slot_ok === false ? ' (TIDAK menunjuk log LiteSpeed)' : '' }}</template></span>
              </div>
              <p v-if="!terpilih.velocity_waf" class="pesan-status waspada kecil-p">Velocity WAF belum terpasang di server ini — Velocity BFM tidak punya sumber data. Pasang WAF dulu di menu Server → WAF.</p>
              <p v-else-if="terpilih.velocity_waf !== 'blokir'" class="redup kecil-p">WAF masih mode deteksi: angka di bawah adalah <b>simulasi</b> (IP yang akan diblokir bila WAF mode blokir). Velocity BFM boleh dipasang sekarang — belum memblokir apa pun sampai WAF dialihkan ke blokir.</p>

              <div class="tabel-wadah">
                <table class="tabel">
                  <thead><tr><th scope="col">Aturan</th><th scope="col">Ambang → blokir</th><th scope="col" class="kanan">Hit 24 jam</th><th scope="col" class="kanan">IP</th><th scope="col" class="kanan">Akan diblokir</th></tr></thead>
                  <tbody>
                    <tr v-for="(a, k) in lokal.aturan" :key="k">
                      <td class="ket"><b>{{ lokal.label[k] }}</b><small class="redup blok-t">{{ ATURAN_KET[k] }}</small></td>
                      <td class="nowrap"><template v-if="a.aktif">{{ a.ambang }}× / {{ durasiLabel(Number(terpilih.csf.LF_INTERVAL || 3600)) }} → {{ durasiLabel(a.durasi) }}</template><span v-else class="lencana abu">Mati</span></td>
                      <td class="kanan">{{ angka(terpilih.simulasi?.aturan[k]?.hit) }}</td>
                      <td class="kanan">{{ angka(terpilih.simulasi?.aturan[k]?.ip) }}</td>
                      <td class="kanan">
                        <b>{{ angka(terpilih.simulasi?.aturan[k]?.blokir) }}</b>
                        <Info v-if="terpilih.simulasi?.aturan[k]?.contoh?.length" :label="`IP ${lokal.label[k]}`" rata="kanan"><ul class="daftar-ip"><li v-for="[ip, n] in terpilih.simulasi.aturan[k].contoh" :key="ip"><code>{{ ip }}</code> {{ n }}×</li></ul></Info>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div v-if="jobServer" class="job" :class="jobServer.status">
                <template v-if="jobServer.status === 'berjalan'">
                  <span class="putar besar" aria-hidden="true" />
                  <div role="status"><b>{{ jobServer.aksi === 'copot' ? 'Mencopot' : 'Memasang' }}…</b> <span class="redup">menulis aturan, csf -r, restart lfd · {{ durasiJob(jobServer) }}</span></div>
                </template>
                <template v-else>
                  <Ikon :nama="jobServer.status === 'selesai' ? 'centang' : 'peringatan'" :ukuran="20" />
                  <div>
                    <b>{{ jobServer.status === 'selesai' ? 'Berhasil' : 'Gagal' }}</b> · {{ jobServer.aksi }} · {{ durasiJob(jobServer) }}
                    <span v-if="jobServer.status !== 'selesai'" class="blok-t">{{ pesanGalat(jobServer.hasil?.error) }}</span>
                    <small v-for="g in jobServer.hasil?.hasil?.galat || []" :key="g" class="merah-teks blok-t"><code>{{ g }}</code></small>
                    <small v-if="jobServer.hasil?.cadangan" class="redup blok-t">Cadangan: {{ jobServer.hasil.cadangan.join(', ') }}</small>
                  </div>
                </template>
              </div>

              <div class="aksi">
                <button v-if="!terpasang(terpilih) || perluUpdate(terpilih)" type="button" class="tombol" :disabled="proses || berjalan(terpilih.host) || !terpilih.lfd_aktif" @click="jalankan('pasang')">
                  <Ikon nama="kunci" :ukuran="16" /> {{ terpasang(terpilih) ? 'Perbarui' : 'Pasang Velocity BFM' }}</button>
                <button v-if="terpasang(terpilih)" type="button" class="tombol bahaya garis" :disabled="proses || berjalan(terpilih.host)" @click="jalankan('copot')">Copot</button>
              </div>
            </div>

            <!-- Pembanding cPGuard -->
            <div v-if="terpilih.cpguard && !terpilih.cpguard.error" class="blok">
              <div class="blok-kepala">
                <b>BFM cPGuard 24 jam (pembanding)</b>
                <span class="redup">{{ angka(terpilih.cpguard.hit) }} kejadian · {{ angka(terpilih.cpguard.ip) }} IP</span>
              </div>
              <ul class="alasan">
                <li v-for="[r, n] in terpilih.cpguard.alasan" :key="r"><span>{{ r }}</span><b>{{ angka(n) }}</b></li>
              </ul>
            </div>

            <!-- Login gagal (LFD) -->
            <div class="blok">
              <div class="blok-kepala">
                <b>Login gagal (LFD)</b>
                <span class="redup">gagal sekian kali dalam {{ durasiLabel(Number(terpilih.csf.LF_INTERVAL || 3600)) }} → diblokir · <router-link :to="`/server/proteksi?s=${terpilih.name}&tab=setelan`">ubah di Proteksi → Setelan</router-link></span>
              </div>
              <div class="chip-baris">
                <span v-for="x in LOGIN_LFD" :key="x.k" class="chip" :class="{ mati: terpilih.csf[x.k] === '0' }">{{ x.label }} <b>{{ terpilih.csf[x.k] === '0' ? 'mati' : `${terpilih.csf[x.k]}×` }}</b></span>
              </div>
              <p class="redup kecil-p">Blokir ulang jadi permanen: {{ terpilih.csf.LF_PERMBLOCK === '1' ? `ya, sesudah ${terpilih.csf.LF_PERMBLOCK_COUNT}× dalam ${durasiLabel(Number(terpilih.csf.LF_PERMBLOCK_INTERVAL || 86400))}` : 'tidak' }}.</p>
            </div>
          </template>
        </template>

        <!-- ================= Setelan ================= -->
        <form v-else-if="tab === 'setelan'" class="setelan" @submit.prevent="simpan">
          <p class="redup kecil-p">Berlaku untuk <b>semua server</b>. Hit dihitung per IP dalam jendela LF_INTERVAL (bawaan 1 jam). Sesudah disimpan, server yang sudah terpasang perlu <b>Perbarui</b>.
            <Info label="Tentang ambang"><p>Velocity WAF sudah menolak setiap request jahat (403/429/406). Velocity BFM menambah blokir di firewall untuk IP yang terus mengulang, agar tidak membebani server sama sekali. Blokir sementara yang berulang otomatis jadi permanen bila LF_PERMBLOCK aktif.</p></Info>
          </p>
          <fieldset v-for="(a, k) in form" :key="k" class="aturan-set">
            <legend><label class="cek"><input v-model="a.aktif" type="checkbox"> {{ lokal.label[k] }}</label></legend>
            <small class="redup">{{ ATURAN_KET[k] }}</small>
            <div class="dua">
              <label class="isian"><span>Ambang (hit per jendela)</span><input v-model.number="a.ambang" type="number" min="2" max="500" :disabled="!a.aktif" required></label>
              <label class="isian"><span>Lama blokir</span>
                <select v-model.number="a.durasi" :disabled="!a.aktif"><option v-for="d in lokal.durasi_boleh" :key="d" :value="d">{{ durasiLabel(d) }}</option></select>
              </label>
            </div>
          </fieldset>
          <div class="aksi">
            <button type="submit" class="tombol" :disabled="proses || !berubah">Simpan setelan</button>
            <button v-if="berubah" type="button" class="tombol garis" @click="isiForm">Batalkan perubahan</button>
          </div>
        </form>

        <!-- ================= Riwayat ================= -->
        <template v-else-if="tab === 'riwayat'">
          <p v-if="!riwayatServer.length" class="redup">Belum ada perubahan dari dashboard.</p>
          <ul v-else class="kejadian">
            <li v-for="(r, i) in riwayatServer" :key="i">
              <span class="titik" :class="r.ok ? AKSI_LABEL[r.aksi]?.[0] : 'abu'" aria-hidden="true" />
              <div>
                <b>{{ AKSI_LABEL[r.aksi]?.[1] || r.aksi }}</b><template v-if="r.server"> · {{ r.server }}</template>
                <template v-if="r.aksi === 'setelan'"> <span class="redup">semua server · {{ ringkasSetelan(r.setelan) }}</span></template>
                <span v-if="!r.ok" class="lencana merah">GAGAL · {{ pesanGalat(r.error) }}</span>
                <small class="redup blok-t">{{ r.oleh }}</small>
              </div>
              <time class="redup">{{ tanggalWaktu(r.t) }}</time>
            </li>
          </ul>
        </template>
      </section>
      <p class="redup kaki">Dibaca {{ waktuLalu(bfm.data.value.diambil) }}.</p>
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
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
.blok { display: grid; gap: 10px; padding: 16px 0; border-top: 1px solid var(--garis); }
.blok:first-of-type { border-top: 0; padding-top: 0; }
.blok-kepala { display: flex; justify-content: space-between; align-items: baseline; gap: 6px 14px; flex-wrap: wrap; font-size: 13.5px; }
.blok-kepala .redup { font-size: 12.5px; }
.batang { display: flex; height: 12px; border-radius: 6px; overflow: hidden; background: var(--kartu-2); gap: 2px; }
.batang span { display: block; height: 100%; }
.legenda { list-style: none; margin: 0; padding: 0; display: flex; gap: 14px; flex-wrap: wrap; font-size: 12.5px; color: var(--teks-2); }
.legenda li { display: inline-flex; align-items: center; gap: 6px; }
.kotak { width: 10px; height: 10px; border-radius: 3px; }
.kecil-p { margin: 0; font-size: 13px; line-height: 1.55; }
.pesan-status.waspada { color: var(--waspada); }
.alasan { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px 20px; font-size: 13px; }
.alasan li { display: flex; justify-content: space-between; gap: 10px; padding: 4px 0; border-bottom: 1px solid var(--garis); }
.alasan span { color: var(--teks-2); overflow-wrap: anywhere; }
.chip-baris { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { border: 1px solid var(--garis); color: var(--teks-2); font-size: 12.5px; padding: 4px 10px; border-radius: 999px; }
.chip.mati { opacity: .6; }
.daftar-ip { list-style: none; margin: 0; padding: 0; display: grid; gap: 3px; font-size: 12.5px; }
.job { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 12px; align-items: center; padding: 12px 14px; border-radius: 12px;
  background: var(--kartu-2); border: 1px solid var(--garis); font-size: 13.5px; }
.job.selesai > svg { color: var(--baik); }
.job.gagal { border-color: color-mix(in srgb, var(--bahaya) 50%, transparent); }
.job.gagal > svg { color: var(--bahaya); }
.aksi { display: flex; gap: 10px; flex-wrap: wrap; }
.setelan { display: grid; gap: 14px; }
.aturan-set { margin: 0; padding: 12px 14px; border: 1px solid var(--garis); border-radius: 12px; display: grid; gap: 10px; min-width: 0; }
.aturan-set legend { padding: 0 6px; font-weight: 600; font-size: 13.5px; }
.aturan-set small { font-size: 12.5px; }
.cek { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; }
.dua { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.isian { display: grid; gap: 6px; font-size: 12.5px; color: var(--teks-2); min-width: 0; }
.isian input, .isian select { width: 100%; }
.kejadian { list-style: none; margin: 0; padding: 0; display: grid; }
.kejadian li { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 2px; border-bottom: 1px solid var(--garis); font-size: 13.5px; }
.kejadian li:last-child { border-bottom: 0; }
.kejadian li > div { overflow-wrap: anywhere; }
.kejadian time { font-size: 12.5px; white-space: nowrap; }
.ket { font-size: 13px; overflow-wrap: anywhere; min-width: 220px; }
.blok-t { display: block; }
.nowrap { white-space: nowrap; }
.kanan { text-align: right; white-space: nowrap; }
.merah-teks { color: var(--bahaya); }
.tabel-wadah { position: relative; overflow-x: auto; }
.kaki { margin: -8px 0 0; font-size: 12.5px; }
.putar { display: inline-block; width: 12px; height: 12px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: putar .8s linear infinite; vertical-align: -1px; }
.putar.besar { width: 22px; height: 22px; color: var(--aksen-terang); }
@keyframes putar { to { transform: rotate(360deg); } }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
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
.sk-judul { height: 14px; width: 200px; max-width: 60%; margin-bottom: 18px; }
.sk-baris { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 16px; padding: 14px 0; border-top: 1px solid var(--garis); }
.sk-baris .sk { height: 12px; }
@keyframes sk-kilau { from { background-position: 100% 0; } to { background-position: -100% 0; } }
@media (prefers-reduced-motion: reduce) { .sk, .putar { animation: none; } }
@media (max-width: 900px) { .ringkas { grid-template-columns: 1fr 1fr; } }
@media (max-width: 560px) {
  .ringkas, .dua, .alasan { grid-template-columns: 1fr; }
  .nama-saya { width: 100%; }
  .kepala-aksi { width: 100%; }
  .ket { min-width: 180px; }
  .kejadian li { grid-template-columns: 8px minmax(0, 1fr); }
  .kejadian time { grid-column: 2; }
}
</style>
