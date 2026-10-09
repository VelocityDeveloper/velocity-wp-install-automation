<script setup>
// Keamanan PC kantor (/api/security, scripts/keamanan_pc.py): login publik dash.velocity.ai.id (gerbang /opt/dash-login),
// fail2ban SSH, firewall & port. Blokir login dash berlaku di gerbang (lewat tunnel semua IP tampak 127.0.0.1 bagi firewall),
// blokir SSH lewat fail2ban. Firewall hanya ditampilkan; mengubahnya lewat /root/velocity-cadangan/firewall-lan-saja.sh.
import { ref, reactive, computed, watch } from 'vue'
import Ikon from '../components/Ikon.vue'
import Info from '../components/Info.vue'
import { konfirmasi } from '../konfirmasi.js'
import GrafikBatangTumpuk from '../components/GrafikBatangTumpuk.vue'
import { pakaiPolling, kirim, tanggalWaktu, waktuLalu, angka } from '../api.js'
import { tabUrl } from '../laravel.js'

const segarkan = ref(false)
const { data, galat, memuat, muatUlang } = pakaiPolling(() => (segarkan.value ? '/api/security?segar=1' : '/api/security'), 30000)
async function periksaUlang() {
  segarkan.value = true
  await muatUlang()
  segarkan.value = false
}

const PESAN = {
  forbidden: 'Ditolak: hanya bisa diubah dari halaman dashboard ini.',
  ip_tidak_valid: 'Alamat IP tidak valid.',
  ip_jaringan_kantor: 'IP jaringan kantor/Tailscale/lokal tidak boleh diblokir.',
  ip_sendiri: 'Itu IP Anda sendiri — memblokirnya akan mengunci Anda keluar.',
  ip_tidak_diblokir: 'IP itu sudah tidak diblokir.',
  durasi_tidak_valid: 'Durasi blokir tidak valid.',
  pengaturan_tidak_valid: 'Nilai pengaturan di luar batas yang diizinkan.',
}
const pesan = reactive({ teks: '', galat: false })
const proses = ref(false)
async function jalankan(body, berhasil) {
  proses.value = true
  try {
    data.value = await kirim('/api/security', body)
    Object.assign(pesan, { teks: berhasil, galat: false })
    return true
  } catch (e) {
    Object.assign(pesan, { teks: PESAN[e.message] || `Gagal: ${e.message}`, galat: true })
    return false
  } finally {
    proses.value = false
  }
}

const d = computed(() => data.value || {})
const dash = computed(() => d.value.dash || {})
const f2b = computed(() => d.value.fail2ban || {})
const fw = computed(() => d.value.firewall || {})

// ---- Ringkasan & pemeriksaan ----
const totalBlokir = computed(() => (dash.value.blokir?.length || 0) + (f2b.value.ip_diblokir?.length || 0))
const PERIKSA = computed(() => {
  const x = d.value
  if (!x.ssh) return []
  const terbuka = fw.value.terbuka_internet || []
  return [
    { judul: 'Akses publik lewat Cloudflare Tunnel', ok: x.tunnel?.aktif, teks: x.tunnel?.aktif ? `Aktif: ${x.tunnel.hostname.join(', ')}` : 'cloudflared mati — domain tidak bisa dibuka' },
    { judul: 'Halaman login dashboard', ok: x.tunnel?.login_aktif, teks: x.tunnel?.login_aktif ? 'Gerbang login aktif di depan dash.velocity.ai.id' : 'Layanan dash-login mati — dashboard publik tidak bisa dibuka' },
    { judul: 'Firewall', ok: fw.value.aktif && fw.value.hanya_lan, waspada: fw.value.aktif && !fw.value.hanya_lan,
      teks: !fw.value.aktif ? 'firewalld mati' : fw.value.hanya_lan ? 'Port aplikasi hanya untuk LAN & Tailscale' : `${terbuka.length} layanan/port diizinkan dari mana saja (zona ${fw.value.zona_internet})` },
    { judul: 'Login SSH', ok: x.ssh.passwordauthentication === 'no', teks: x.ssh.passwordauthentication === 'no' ? `Hanya kunci SSH · maks ${x.ssh.maxauthtries} percobaan per koneksi` : 'Login pakai password masih diizinkan' },
    { judul: 'fail2ban (SSH)', ok: f2b.value.aktif, teks: f2b.value.aktif ? `Blokir ${f2b.value.bantime_menit} menit setelah ${f2b.value.maxretry}x gagal dalam ${f2b.value.findtime_menit} menit` : 'fail2ban mati' },
    { judul: 'SELinux', ok: x.selinux === 'Enforcing', waspada: x.selinux === 'Permissive', teks: x.selinux },
  ]
})
// Skor proteksi: aman = 1, perlu dicek = ½
const skor = computed(() => {
  const p = PERIKSA.value
  return p.length ? Math.round((100 * p.reduce((a, x) => a + (x.ok ? 1 : x.waspada ? 0.5 : 0), 0)) / p.length) : 0
})
const statusUmum = computed(() => {
  const p = PERIKSA.value
  if (p.some((x) => !x.ok && !x.waspada)) return { kelas: 'bahaya', judul: 'Ada proteksi yang mati' }
  if (p.some((x) => x.waspada)) return { kelas: 'waspada', judul: 'Terlindungi, ada yang perlu dicek' }
  return { kelas: 'baik', judul: 'PC kantor terlindungi' }
})
const masalah = computed(() => PERIKSA.value.filter((p) => !p.ok))
const IKON_PERIKSA = ['luar', 'kunci', 'komputer', 'server', 'perisai', 'perisai']
const kelasPeriksa = (p) => (p.ok ? 'baik' : p.waspada ? 'waspada' : 'bahaya')
const labelPeriksa = (p) => (p.ok ? 'Aman' : p.waspada ? 'Perlu dicek' : 'Bermasalah')

// ---- Login dashboard ----
const TAB_DASH = computed(() => [
  { nilai: 'blokir', label: 'IP diblokir', jumlah: dash.value.blokir?.length || 0 },
  { nilai: 'riwayat', label: 'Riwayat login', jumlah: dash.value.log?.length || 0 },
  { nilai: 'aturan', label: 'Aturan blokir' },
])
const tabDash = ref('blokir')
const HASIL = { berhasil: ['hijau', 'Berhasil'], gagal: ['merah', 'Gagal'], diblokir: ['kuning', 'Ditolak (diblokir)'] }
const DURASI = [
  { nilai: 60, label: '1 jam' }, { nilai: 1440, label: '24 jam' }, { nilai: 10080, label: '7 hari' }, { nilai: 0, label: 'Permanen' },
]
const sampai = (e) => (e.sampai ? tanggalWaktu(e.sampai) : 'Permanen')
const terblokirDash = (ip) => dash.value.blokir?.some((b) => b.ip === ip)
const terblokirSsh = (ip) => f2b.value.ip_diblokir?.includes(ip)
const ringkasUa = (ua) => {
  if (!ua) return '-'
  const os = /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Windows/.test(ua) ? 'Windows' : /Mac OS/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : ''
  const br = /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : ua.split(/[ /]/)[0]
  return [br, os].filter(Boolean).join(' · ')
}

const blokirBaru = reactive({ ip: '', menit: 1440, alasan: '', target: 'dash' })
async function blokirManual() {
  const t = blokirBaru.target
  const ok = await jalankan(
    t === 'dash' ? { aksi: 'dash_blokir', ip: blokirBaru.ip, menit: blokirBaru.menit, alasan: blokirBaru.alasan } : { aksi: 'ssh_blokir', ip: blokirBaru.ip },
    `${blokirBaru.ip} diblokir dari ${t === 'dash' ? 'login dashboard' : 'SSH'}.`,
  )
  if (ok) Object.assign(blokirBaru, { ip: '', alasan: '' })
}
async function blokirCepat(ip, target) {
  const ya = await konfirmasi({
    judul: `Blokir ${ip}?`,
    teks: target === 'dash' ? 'IP ini tidak bisa membuka dash.velocity.ai.id selama 24 jam.' : `IP ini diblokir dari SSH selama ${f2b.value.bantime_menit} menit (fail2ban).`,
    tombol: 'Blokir', kelas: 'bahaya',
  })
  if (ya) await jalankan(target === 'dash' ? { aksi: 'dash_blokir', ip, menit: 1440, alasan: 'manual dari riwayat' } : { aksi: 'ssh_blokir', ip }, `${ip} diblokir.`)
}
async function bukaBlokir(ip, target) {
  const ya = await konfirmasi({ judul: `Buka blokir ${ip}?`, teks: target === 'dash' ? 'IP ini bisa mencoba login dashboard lagi.' : 'IP ini bisa mencoba SSH lagi.', tombol: 'Buka blokir' })
  if (ya) await jalankan({ aksi: target === 'dash' ? 'dash_buka' : 'ssh_buka', ip }, `Blokir ${ip} dibuka.`)
}

const aturanDash = reactive({ maks_gagal: 5, jendela_menit: 15, lama_blokir_menit: 60 })
const aturanSsh = reactive({ maxretry: 5, findtime_menit: 10, bantime_menit: 60 })
// Isi formulir dari server hanya saat data pertama datang / sesudah disimpan, jangan menimpa ketikan saat polling
let terisi = false
watch(data, (x) => {
  if (!x || terisi) return
  Object.assign(aturanDash, x.dash.pengaturan)
  if (x.fail2ban.aktif) Object.assign(aturanSsh, { maxretry: x.fail2ban.maxretry, findtime_menit: x.fail2ban.findtime_menit, bantime_menit: x.fail2ban.bantime_menit })
  terisi = true
}, { immediate: true })
const simpanDash = () => jalankan({ aksi: 'dash_pengaturan', ...aturanDash }, 'Aturan blokir login dashboard disimpan (langsung berlaku).')
const simpanSsh = () => jalankan({ aksi: 'ssh_pengaturan', ...aturanSsh }, 'Aturan fail2ban SSH disimpan & diterapkan.')

// ---- SSH ----
const TAB_SSH = computed(() => [
  { nilai: 'blokir', label: 'IP diblokir', jumlah: f2b.value.ip_diblokir?.length || 0 },
  { nilai: 'gagal', label: 'Gagal 24 jam', jumlah: d.value.ssh_gagal?.total || 0 },
  { nilai: 'riwayat', label: 'Riwayat blokir', jumlah: f2b.value.riwayat?.length || 0 },
  { nilai: 'aturan', label: 'Aturan' },
])
const tabSsh = ref('blokir')
const AKSI_F2B = { Ban: ['merah', 'Diblokir'], 'Restore Ban': ['kuning', 'Blokir dipulihkan'], Unban: ['hijau', 'Dibuka'] }

// ---- Menu sub-halaman (ala menu server cPGuard) ----
const MENU = computed(() => [
  { kunci: 'ringkasan', label: 'Ringkasan', ikon: 'dashboard' },
  { kunci: 'login', label: 'Login Protection', ikon: 'kunci', jumlah: dash.value.blokir?.length },
  { kunci: 'ssh', label: 'SSH · fail2ban', ikon: 'server', jumlah: f2b.value.ip_diblokir?.length },
  { kunci: 'ipdb', label: 'Blokir IP', ikon: 'perisai', jumlah: totalBlokir.value },
  { kunci: 'firewall', label: 'Firewall & Port', ikon: 'komputer' },
])
const menu = tabUrl('tab', 'ringkasan', { boleh: ['ringkasan', 'login', 'ssh', 'ipdb', 'firewall'] })

// ---- Ringkasan: grafik serangan, negara, penyerang, kejadian ----
const akt = computed(() => d.value.aktivitas || { hari: [], negara: [], penyerang: [] })
const SERI = [
  { kunci: 'login_gagal', label: 'Login dashboard gagal', warna: 'var(--bahaya)' },
  { kunci: 'login_ditolak', label: 'Ditolak (IP diblokir)', warna: 'var(--waspada)' },
  { kunci: 'ssh_gagal', label: 'SSH gagal', warna: 'var(--ungu)' },
]
const totalSerangan = computed(() => akt.value.hari.reduce((a, h) => a + SERI.reduce((b, s) => b + (h.nilai[s.kunci] || 0), 0), 0))
const totalSeri = (k) => akt.value.hari.reduce((a, h) => a + (h.nilai[k] || 0), 0)
const formatTanggal = (t) => new Date(`${t}T00:00`).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })
let namaNegara = null
try { namaNegara = new Intl.DisplayNames(['id'], { type: 'region' }) } catch { /* peramban lama */ }
// IP kantor/Tailscale/lokal ditolak backend, jadi tombol Blokir tidak ditampilkan
const ipKantor = (ip) => /^(127\.|192\.168\.|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.|::1$|fe80:|fd7a:115c:a1e0:)/i.test(ip || '')
const negara = (k) => { try { return (k && namaNegara?.of(k)) || k || '-' } catch { return k } }
const puncakNegara = computed(() => Math.max(1, ...akt.value.negara.map((n) => n.jumlah)))
const JENIS_SERANG = { dash: 'Login', ssh: 'SSH' }

// Kejadian terbaru: gabungan log gerbang login + riwayat fail2ban
const kejadian = computed(() => {
  const a = (dash.value.log || []).map((l) => ({
    waktu: l.waktu, ip: l.ip, negara: l.negara, sumber: 'Login dashboard',
    kelas: (HASIL[l.hasil] || ['abu'])[0], label: HASIL[l.hasil]?.[1] || l.hasil, ket: l.user ? `user ${l.user}` : '',
  }))
  const b = (f2b.value.riwayat || []).map((r) => ({
    waktu: Math.floor(new Date(r.waktu.replace(' ', 'T')).getTime() / 1000), ip: r.ip, negara: '', sumber: 'SSH · fail2ban',
    kelas: (AKSI_F2B[r.aksi] || ['abu'])[0], label: AKSI_F2B[r.aksi]?.[1] || r.aksi, ket: '',
  }))
  return [...a, ...b].sort((x, y) => y.waktu - x.waktu).slice(0, 8)
})

const portInternet = computed(() => (d.value.port || []).filter((p) => p.internet).length)
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Security</h1>
        <p class="redup">Pusat proteksi PC kantor: login dashboard publik, SSH, blokir IP, firewall & port.</p>
      </div>
      <div class="kepala-aksi">
        <span v-if="d.ip_anda" class="redup">IP Anda: <code>{{ d.ip_anda }}</code></span>
        <button type="button" class="tombol kecil" :disabled="segarkan" @click="periksaUlang"><Ikon nama="ulang" :ukuran="16" /> {{ segarkan ? 'Memindai…' : 'Pindai ulang' }}</button>
      </div>
    </header>

    <p v-if="memuat && !data" class="redup">Memuat…</p>
    <p v-else-if="galat && !data" class="pesan-status bahaya">Gagal memuat: {{ galat.message }}</p>

    <template v-else-if="data">
      <!-- Status proteksi + skor (bagian atas panel server cPGuard) -->
      <section class="kartu status-proteksi" :class="statusUmum.kelas" aria-labelledby="judul-status">
        <div class="perisai-besar" aria-hidden="true"><Ikon nama="perisai" :ukuran="40" /></div>
        <div class="status-teks">
          <span class="label-kecil">Status proteksi</span>
          <h2 id="judul-status">{{ statusUmum.judul }}</h2>
          <p class="redup">
            PC Kantor · {{ (data.tunnel.hostname || []).join(', ') || 'tanpa tunnel' }} · dipindai {{ waktuLalu(data.diperbarui) }}
          </p>
          <ul v-if="masalah.length" class="masalah">
            <li v-for="m in masalah" :key="m.judul"><span class="titik" :class="kelasPeriksa(m)" /> <b>{{ m.judul }}:</b> {{ m.teks }}</li>
          </ul>
        </div>
        <div class="skor" role="img" :aria-label="`Skor proteksi ${skor} dari 100`">
          <svg viewBox="0 0 120 120" aria-hidden="true">
            <circle cx="60" cy="60" r="50" class="skor-jalur" />
            <circle cx="60" cy="60" r="50" class="skor-isi" :style="{ strokeDasharray: `${(skor / 100) * 314.16} 314.16` }" />
          </svg>
          <div class="skor-angka"><b>{{ skor }}</b><span>skor</span></div>
        </div>
      </section>

      <div class="ringkas">
        <div class="kartu tile">
          <span class="tile-ikon merah"><Ikon nama="perisai" :ukuran="20" /></span>
          <div><span class="redup">IP diblokir</span><b>{{ angka(totalBlokir) }}</b><small class="redup">login {{ dash.blokir.length }} · SSH {{ f2b.ip_diblokir?.length || 0 }}</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon kuning"><Ikon nama="kunci" :ukuran="20" /></span>
          <div><span class="redup">Login gagal · 24 jam</span><b>{{ angka(dash.hari_ini.gagal) }}</b><small class="redup">{{ dash.hari_ini.ditolak }} ditolak karena diblokir</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon ungu"><Ikon nama="server" :ukuran="20" /></span>
          <div><span class="redup">SSH gagal · 24 jam</span><b>{{ angka(data.ssh_gagal.total) }}</b><small class="redup">total diblokir fail2ban {{ f2b.blokir_total ?? '-' }}</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon hijau"><Ikon nama="centang" :ukuran="20" /></span>
          <div><span class="redup">Login berhasil · 24 jam</span><b>{{ angka(dash.hari_ini.berhasil) }}</b><small class="redup">dari {{ dash.hari_ini.ip_unik }} IP</small></div>
        </div>
      </div>

      <nav class="sub-menu" aria-label="Menu Security">
        <button v-for="m in MENU" :key="m.kunci" type="button" :class="{ aktif: menu === m.kunci }" :aria-current="menu === m.kunci ? 'page' : undefined" @click="menu = m.kunci">
          <Ikon :nama="m.ikon" :ukuran="16" /> {{ m.label }} <span v-if="m.jumlah" class="hitung">{{ m.jumlah }}</span>
        </button>
      </nav>

      <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>

      <template v-if="menu === 'ringkasan'">
        <section class="kartu" aria-labelledby="judul-modul">
          <div class="kartu-judul">
            <h2 id="judul-modul"><Ikon nama="perisai" :ukuran="16" /> Modul proteksi</h2>
            <span class="redup">{{ PERIKSA.filter((p) => p.ok).length }} dari {{ PERIKSA.length }} aman</span>
          </div>
          <ul class="modul">
            <li v-for="(p, i) in PERIKSA" :key="p.judul" :class="kelasPeriksa(p)">
              <span class="modul-ikon"><Ikon :nama="IKON_PERIKSA[i] || 'perisai'" :ukuran="18" /></span>
              <div class="modul-teks"><b>{{ p.judul }}</b><span class="redup">{{ p.teks }}</span></div>
              <span class="status-modul" :class="kelasPeriksa(p)">{{ p.ok ? 'AKTIF' : p.waspada ? 'CEK' : 'MATI' }}</span>
            </li>
          </ul>
        </section>

        <section class="kartu" aria-labelledby="judul-grafik">
          <div class="kartu-judul">
            <h2 id="judul-grafik"><Ikon nama="token" :ukuran="16" /> Serangan 14 hari terakhir</h2>
            <span class="redup">{{ angka(totalSerangan) }} percobaan</span>
          </div>
          <ul class="legenda">
            <li v-for="s in SERI" :key="s.kunci"><span class="kotak" :style="{ background: s.warna }" /> {{ s.label }} <b>{{ angka(totalSeri(s.kunci)) }}</b></li>
          </ul>
          <GrafikBatangTumpuk judul="Percobaan serangan per hari" :hari="akt.hari" :seri="SERI" :format="angka" :format-tanggal="formatTanggal" />
        </section>

        <div class="dua-kolom">
          <section class="kartu" aria-labelledby="judul-penyerang">
            <div class="kartu-judul"><h2 id="judul-penyerang"><Ikon nama="pantau" :ukuran="16" /> IP penyerang teratas</h2><span class="redup">14 hari</span></div>
            <p v-if="!akt.penyerang.length" class="redup">Belum ada percobaan serangan.</p>
            <div v-else class="tabel-wadah">
              <table class="tabel">
                <thead><tr><th scope="col">IP</th><th scope="col">Lewat</th><th scope="col" class="kanan">Percobaan</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                <tbody>
                  <tr v-for="e in akt.penyerang" :key="e.ip">
                    <td><span v-if="e.negara" class="kode-negara" :title="negara(e.negara)">{{ e.negara }}</span> <code>{{ e.ip }}</code><small class="redup blok">{{ waktuLalu(e.terakhir) }}</small></td>
                    <td><span v-for="j in e.jenis" :key="j" class="lencana abu">{{ JENIS_SERANG[j] }}</span></td>
                    <td class="kanan">{{ angka(e.jumlah) }}</td>
                    <td class="kanan">
                      <span v-if="terblokirDash(e.ip) || terblokirSsh(e.ip)" class="lencana merah">DIBLOKIR</span>
                      <span v-else-if="ipKantor(e.ip)" class="lencana biru">KANTOR</span>
                      <button v-else-if="e.ip !== d.ip_anda" type="button" class="tombol bahaya kecil" :disabled="proses" @click="blokirCepat(e.ip, e.jenis.includes('dash') ? 'dash' : 'ssh')">Blokir</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="kartu" aria-labelledby="judul-negara">
            <div class="kartu-judul"><h2 id="judul-negara"><Ikon nama="luar" :ukuran="16" /> Asal akses login</h2><span class="redup">14 hari · Cloudflare</span></div>
            <p v-if="!akt.negara.length" class="redup">Belum ada data negara.</p>
            <ul v-else class="negara">
              <li v-for="n in akt.negara" :key="n.kode">
                <span class="kode-negara" aria-hidden="true">{{ n.kode }}</span>
                <span class="negara-nama">{{ negara(n.kode) }}</span>
                <span class="negara-meter"><span :style="{ width: `${(n.jumlah / puncakNegara) * 100}%` }" /></span>
                <b>{{ angka(n.jumlah) }}</b>
              </li>
            </ul>
          </section>
        </div>

        <section class="kartu" aria-labelledby="judul-kejadian">
          <div class="kartu-judul"><h2 id="judul-kejadian"><Ikon nama="jam" :ukuran="16" /> Kejadian terbaru</h2></div>
          <p v-if="!kejadian.length" class="redup">Belum ada kejadian.</p>
          <ol v-else class="kejadian">
            <li v-for="(k, i) in kejadian" :key="i">
              <span class="titik" :class="k.kelas" aria-hidden="true" />
              <div><b>{{ k.label }}</b> · {{ k.sumber }} <span v-if="k.negara" class="kode-negara" :title="negara(k.negara)">{{ k.negara }}</span> <code>{{ k.ip }}</code> <span v-if="k.ket" class="redup">{{ k.ket }}</span></div>
              <time class="redup" :datetime="new Date(k.waktu * 1000).toISOString()">{{ tanggalWaktu(k.waktu) }}</time>
            </li>
          </ol>
        </section>
      </template>

      <section v-if="menu === 'login'" class="kartu" aria-labelledby="judul-dash">
        <div class="kartu-judul">
          <h2 id="judul-dash"><Ikon nama="kunci" :ukuran="16" /> Login dash.velocity.ai.id
            <Info label="Tentang login dashboard"><p>Semua pengunjung dari internet melewati halaman login ini. IP yang terlalu sering salah password diblokir otomatis oleh gerbang login — bukan firewall, karena lewat tunnel semua koneksi tampak dari 127.0.0.1.</p></Info>
          </h2>
          <div class="tab" role="tablist" aria-label="Login dashboard">
            <button v-for="t in TAB_DASH" :key="t.nilai" type="button" role="tab" :aria-selected="tabDash === t.nilai" :class="{ aktif: tabDash === t.nilai }" @click="tabDash = t.nilai">
              {{ t.label }} <span v-if="t.jumlah !== undefined" class="hitung">{{ t.jumlah }}</span>
            </button>
          </div>
        </div>

        <template v-if="tabDash === 'blokir'">
          <p v-if="!dash.blokir.length" class="redup">Tidak ada IP yang sedang diblokir.</p>
          <div v-else class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">IP</th><th scope="col">Alasan</th><th scope="col">Sejak</th><th scope="col">Sampai</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
              <tbody>
                <tr v-for="b in dash.blokir" :key="b.ip">
                  <td><code>{{ b.ip }}</code></td>
                  <td>{{ b.alasan }}</td>
                  <td class="nowrap">{{ tanggalWaktu(b.sejak) }}</td>
                  <td class="nowrap">{{ sampai(b) }}</td>
                  <td class="kanan"><button type="button" class="tombol garis kecil" :disabled="proses" @click="bukaBlokir(b.ip, 'dash')">Buka blokir</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <template v-else-if="tabDash === 'riwayat'">
          <p v-if="!dash.log.length" class="redup">Belum ada percobaan login.</p>
          <div v-else class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">Waktu</th><th scope="col">Hasil</th><th scope="col">IP</th><th scope="col">Negara</th><th scope="col">Username</th><th scope="col">Perangkat</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
              <tbody>
                <tr v-for="(l, i) in dash.log" :key="i">
                  <td class="nowrap">{{ tanggalWaktu(l.waktu) }}</td>
                  <td><span class="lencana" :class="(HASIL[l.hasil] || ['abu'])[0]">{{ HASIL[l.hasil]?.[1] || l.hasil }}</span></td>
                  <td><code>{{ l.ip }}</code></td>
                  <td>{{ l.negara || '-' }}</td>
                  <td>{{ l.user || '-' }}</td>
                  <td :title="l.ua">{{ ringkasUa(l.ua) }}</td>
                  <td class="kanan">
                    <span v-if="terblokirDash(l.ip)" class="lencana merah">DIBLOKIR</span>
                    <button v-else-if="l.ip !== d.ip_anda" type="button" class="tombol bahaya kecil" :disabled="proses" @click="blokirCepat(l.ip, 'dash')">Blokir</button>
                    <span v-else class="lencana biru">ANDA</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="redup kaki">100 percobaan terakhir. Negara dari Cloudflare.</p>
        </template>

        <form v-else class="form" @submit.prevent="simpanDash">
          <div class="baris-3">
            <label class="isian"><span>Maks. gagal</span><input v-model.number="aturanDash.maks_gagal" type="number" min="2" max="50" required><small>kali (2–50)</small></label>
            <label class="isian"><span>Dalam jangka</span><input v-model.number="aturanDash.jendela_menit" type="number" min="1" max="1440" required><small>menit</small></label>
            <label class="isian"><span>Lama blokir</span><input v-model.number="aturanDash.lama_blokir_menit" type="number" min="1" max="525600" required><small>menit</small></label>
          </div>
          <p class="redup">IP diblokir otomatis bila salah login {{ aturanDash.maks_gagal }}x dalam {{ aturanDash.jendela_menit }} menit, selama {{ aturanDash.lama_blokir_menit }} menit. Setiap percobaan salah juga ditahan 1 detik, dan maksimal 10 percobaan/menit per IP.</p>
          <div><button type="submit" class="tombol" :disabled="proses">Simpan aturan</button></div>
        </form>
      </section>

      <section v-if="menu === 'ssh'" class="kartu" aria-labelledby="judul-ssh">
        <div class="kartu-judul">
          <h2 id="judul-ssh"><Ikon nama="server" :ukuran="16" /> SSH · fail2ban
            <Info label="Tentang fail2ban SSH"><p>Port {{ data.ssh.port }}. IP yang tidak pernah diblokir: {{ (f2b.abaikan || []).join(', ') || '-' }}.</p></Info>
          </h2>
          <div class="tab" role="tablist" aria-label="SSH">
            <button v-for="t in TAB_SSH" :key="t.nilai" type="button" role="tab" :aria-selected="tabSsh === t.nilai" :class="{ aktif: tabSsh === t.nilai }" @click="tabSsh = t.nilai">
              {{ t.label }} <span v-if="t.jumlah !== undefined" class="hitung">{{ t.jumlah }}</span>
            </button>
          </div>
        </div>
        <p v-if="!f2b.aktif" class="pesan-status bahaya">fail2ban tidak aktif.</p>

        <template v-else-if="tabSsh === 'blokir'">
          <p v-if="!f2b.ip_diblokir.length" class="redup">Tidak ada IP yang sedang diblokir dari SSH.</p>
          <ul v-else class="daftar-chip">
            <li v-for="ip in f2b.ip_diblokir" :key="ip" class="chip besar">
              <code>{{ ip }}</code>
              <button type="button" :aria-label="`Buka blokir ${ip}`" :disabled="proses" @click="bukaBlokir(ip, 'ssh')"><Ikon nama="tutup" :ukuran="12" /></button>
            </li>
          </ul>
        </template>

        <template v-else-if="tabSsh === 'gagal'">
          <p v-if="!data.ssh_gagal.per_ip.length" class="redup">Tidak ada percobaan login SSH gagal dalam 24 jam terakhir.</p>
          <div v-else class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">IP</th><th scope="col">Percobaan gagal</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
              <tbody>
                <tr v-for="g in data.ssh_gagal.per_ip" :key="g.ip">
                  <td><code>{{ g.ip }}</code></td>
                  <td>{{ angka(g.jumlah) }}</td>
                  <td class="kanan">
                    <span v-if="terblokirSsh(g.ip)" class="lencana merah">DIBLOKIR</span>
                    <button v-else type="button" class="tombol bahaya kecil" :disabled="proses" @click="blokirCepat(g.ip, 'ssh')">Blokir</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <template v-else-if="tabSsh === 'riwayat'">
          <p v-if="!f2b.riwayat.length" class="redup">Belum ada riwayat blokir.</p>
          <div v-else class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">Waktu</th><th scope="col">Aksi</th><th scope="col">IP</th></tr></thead>
              <tbody>
                <tr v-for="(r, i) in f2b.riwayat" :key="i">
                  <td class="nowrap">{{ tanggalWaktu(r.waktu.replace(' ', 'T')) }}</td>
                  <td><span class="lencana" :class="(AKSI_F2B[r.aksi] || ['abu'])[0]">{{ AKSI_F2B[r.aksi]?.[1] || r.aksi }}</span></td>
                  <td><code>{{ r.ip }}</code></td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <form v-else class="form" @submit.prevent="simpanSsh">
          <div class="baris-3">
            <label class="isian"><span>Maks. gagal</span><input v-model.number="aturanSsh.maxretry" type="number" min="2" max="50" required><small>kali (2–50)</small></label>
            <label class="isian"><span>Dalam jangka</span><input v-model.number="aturanSsh.findtime_menit" type="number" min="1" max="1440" required><small>menit</small></label>
            <label class="isian"><span>Lama blokir</span><input v-model.number="aturanSsh.bantime_menit" type="number" min="1" max="525600" required><small>menit</small></label>
          </div>
          <p class="redup">Disimpan ke /etc/fail2ban/jail.d/90-dashboard.local dan langsung diterapkan ke jail sshd.</p>
          <div><button type="submit" class="tombol" :disabled="proses">Simpan aturan</button></div>
        </form>
      </section>

      <section v-if="menu === 'ipdb'" class="kartu" aria-labelledby="judul-ipdb">
        <div class="kartu-judul">
          <h2 id="judul-ipdb"><Ikon nama="perisai" :ukuran="16" /> Daftar IP diblokir</h2>
          <span class="redup">{{ totalBlokir }} IP</span>
        </div>
        <p v-if="!totalBlokir" class="redup">Tidak ada IP yang sedang diblokir.</p>
        <div v-else class="tabel-wadah">
          <table class="tabel">
            <thead><tr><th scope="col">IP</th><th scope="col">Diblokir dari</th><th scope="col">Alasan</th><th scope="col">Sampai</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
            <tbody>
              <tr v-for="b in dash.blokir" :key="`d-${b.ip}`">
                <td><code>{{ b.ip }}</code></td>
                <td><span class="lencana kuning">Login dashboard</span></td>
                <td>{{ b.alasan }}</td>
                <td class="nowrap">{{ sampai(b) }}</td>
                <td class="kanan"><button type="button" class="tombol garis kecil" :disabled="proses" @click="bukaBlokir(b.ip, 'dash')">Buka blokir</button></td>
              </tr>
              <tr v-for="ip in f2b.ip_diblokir || []" :key="`s-${ip}`">
                <td><code>{{ ip }}</code></td>
                <td><span class="lencana ungu">SSH · fail2ban</span></td>
                <td>Gagal login SSH / manual</td>
                <td class="nowrap">{{ f2b.bantime_menit }} menit sejak blokir</td>
                <td class="kanan"><button type="button" class="tombol garis kecil" :disabled="proses" @click="bukaBlokir(ip, 'ssh')">Buka blokir</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="menu === 'ipdb'" class="kartu" aria-labelledby="judul-manual">
        <div class="kartu-judul"><h2 id="judul-manual"><Ikon nama="tambah" :ukuran="16" /> Blokir IP manual</h2></div>
        <form class="form-manual" @submit.prevent="blokirManual">
          <label class="isian"><span>Alamat IP</span><input v-model.trim="blokirBaru.ip" required maxlength="45" placeholder="203.0.113.10 atau 2001:db8::1" autocomplete="off"></label>
          <label class="isian"><span>Blokir dari</span>
            <select v-model="blokirBaru.target"><option value="dash">Login dashboard</option><option value="ssh">SSH (fail2ban)</option></select>
          </label>
          <label v-if="blokirBaru.target === 'dash'" class="isian"><span>Lama</span>
            <select v-model.number="blokirBaru.menit"><option v-for="o in DURASI" :key="o.nilai" :value="o.nilai">{{ o.label }}</option></select>
          </label>
          <label v-if="blokirBaru.target === 'dash'" class="isian"><span>Alasan</span><input v-model="blokirBaru.alasan" maxlength="120" placeholder="opsional"></label>
          <div class="kirim-manual"><button type="submit" class="tombol bahaya" :disabled="proses || !blokirBaru.ip">Blokir</button></div>
        </form>
        <p class="redup kaki">IP jaringan kantor (192.168.x), Tailscale, dan IP Anda sendiri tidak bisa diblokir. Blokir SSH berlaku {{ f2b.bantime_menit }} menit sesuai aturan fail2ban.</p>
      </section>

      <section v-if="menu === 'firewall'" class="kartu" aria-labelledby="judul-fw">
        <div class="kartu-judul">
          <h2 id="judul-fw"><Ikon nama="komputer" :ukuran="16" /> Firewall & port</h2>
          <span class="pil" :class="fw.hanya_lan ? 'baik' : 'waspada'">{{ fw.hanya_lan ? 'Hanya LAN & Tailscale' : `${portInternet} port diizinkan dari internet` }}</span>
        </div>
        <div class="zona">
          <article v-for="z in fw.zona" :key="z.nama" class="zona-item">
            <div class="zona-atas"><b>{{ z.nama }}</b><span class="lencana" :class="z.nama === fw.zona_internet ? 'kuning' : 'biru'">{{ z.nama === fw.zona_internet ? 'INTERNET' : 'TERBATAS' }}</span></div>
            <dl>
              <div v-if="z.interface.length"><dt>Interface</dt><dd>{{ z.interface.join(', ') }}</dd></div>
              <div v-if="z.sumber.length"><dt>Sumber</dt><dd>{{ z.sumber.join(', ') }}</dd></div>
              <div><dt>Layanan</dt><dd>{{ z.layanan.join(', ') || '-' }}</dd></div>
              <div><dt>Port</dt><dd>{{ z.port.join(', ') || '-' }}</dd></div>
            </dl>
          </article>
        </div>
        <div class="tabel-wadah">
          <table class="tabel">
            <thead><tr><th scope="col">Port</th><th scope="col">Proses</th><th scope="col">Mendengarkan di</th><th scope="col">Firewall</th></tr></thead>
            <tbody>
              <tr v-for="p in data.port" :key="p.port">
                <td><code>{{ p.port }}</code></td>
                <td>{{ p.proses }}</td>
                <td class="alamat">{{ p.alamat.join(', ') }}</td>
                <td><span class="lencana" :class="p.internet ? 'kuning' : 'hijau'">{{ p.internet ? 'Dibuka untuk semua' : 'Tertutup dari luar' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="redup kaki">
          Router kantor saat ini tidak meneruskan port ke PC ini, jadi "Dibuka untuk semua" baru berbahaya bila diakses langsung lewat IPv6 publik.
          Untuk membatasi ke LAN & Tailscale jalankan <code>bash /root/velocity-cadangan/firewall-lan-saja.sh terapkan</code> (otomatis batal 5 menit bila tidak di-<code>simpan</code>).
        </p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.kepala-aksi { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.ringkas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.angka { display: grid; gap: 6px; align-content: start; }
.angka b { font-size: 24px; }
.kartu-judul h2 { display: inline-flex; align-items: center; gap: 8px; }
/* ---- Status proteksi ala cPGuard ---- */
.status-proteksi { --warna: var(--baik); display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 20px; align-items: center;
  background: linear-gradient(120deg, color-mix(in srgb, var(--warna) 14%, var(--kartu)) 0%, var(--kartu) 60%); border-left: 4px solid var(--warna); }
.status-proteksi.waspada { --warna: var(--waspada); }
.status-proteksi.bahaya { --warna: var(--bahaya); }
.perisai-besar { display: grid; place-items: center; width: 72px; height: 72px; border-radius: 20px; color: var(--warna);
  background: color-mix(in srgb, var(--warna) 16%, transparent); box-shadow: 0 0 0 6px color-mix(in srgb, var(--warna) 7%, transparent); }
.status-teks { display: grid; gap: 4px; }
.status-teks h2 { font-size: 22px; margin: 0; color: var(--teks-kuat); }
.status-teks p { margin: 0; }
.label-kecil { font-size: 11.5px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--warna); }
.masalah { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 4px; font-size: 13px; color: var(--teks-2); }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); }
.titik.baik, .titik.hijau { background: var(--baik); }
.titik.waspada, .titik.kuning { background: var(--waspada); }
.titik.bahaya, .titik.merah { background: var(--bahaya); }
.titik.biru { background: var(--aksen-terang); }
.skor { position: relative; width: 104px; height: 104px; }
.skor svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.skor circle { fill: none; stroke-width: 10; }
.skor-jalur { stroke: var(--kartu-2); }
.skor-isi { stroke: var(--warna); stroke-linecap: round; transition: stroke-dasharray .6s ease; }
.skor-angka { position: absolute; inset: 0; display: grid; place-content: center; text-align: center; line-height: 1.1; }
.skor-angka b { font-size: 28px; color: var(--teks-kuat); }
.skor-angka span { font-size: 11px; color: var(--teks-3); text-transform: uppercase; letter-spacing: .08em; }
/* ---- Kartu angka berikon ---- */
.tile { display: flex; gap: 14px; align-items: center; }
.tile > div { display: grid; gap: 3px; min-width: 0; }
.tile b { font-size: 24px; color: var(--teks-kuat); }
.tile small { font-size: 12px; }
.tile-ikon { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; }
.tile-ikon.merah { color: var(--bahaya); background: color-mix(in srgb, var(--bahaya) 15%, transparent); }
.tile-ikon.kuning { color: var(--waspada); background: color-mix(in srgb, var(--waspada) 15%, transparent); }
.tile-ikon.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 15%, transparent); }
.tile-ikon.hijau { color: var(--baik); background: color-mix(in srgb, var(--baik) 15%, transparent); }
/* ---- Sub-menu ---- */
.sub-menu { display: flex; gap: 4px; padding: 4px; border-radius: 12px; background: var(--kartu); border: 1px solid var(--garis); overflow-x: auto; }
.sub-menu button { display: inline-flex; align-items: center; gap: 7px; flex: none; border: 0; background: transparent; color: var(--teks-2);
  font: inherit; font-size: 13.5px; font-weight: 600; padding: 9px 14px; border-radius: 9px; cursor: pointer; }
.sub-menu button:hover { color: var(--teks-kuat); background: var(--sorot); }
.sub-menu button.aktif { background: var(--aksen); color: #fff; }
.sub-menu .hitung { min-width: 20px; padding: 1px 6px; border-radius: 999px; font-size: 11.5px; background: var(--bahaya); color: #fff; text-align: center; }
/* ---- Modul proteksi ---- */
.modul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(320px, 100%), 1fr)); gap: 10px; }
.modul li { --warna: var(--baik); display: flex; gap: 12px; align-items: center; padding: 12px 14px; border-radius: 12px; background: var(--kartu-2); border: 1px solid transparent; }
.modul li.waspada { --warna: var(--waspada); border-color: color-mix(in srgb, var(--waspada) 35%, transparent); }
.modul li.bahaya { --warna: var(--bahaya); border-color: color-mix(in srgb, var(--bahaya) 40%, transparent); }
.modul-ikon { flex: none; display: grid; place-items: center; width: 36px; height: 36px; border-radius: 10px; color: var(--warna); background: color-mix(in srgb, var(--warna) 14%, transparent); }
.modul-teks { display: grid; gap: 2px; min-width: 0; flex: 1; font-size: 13px; }
.modul-teks b { font-size: 13.5px; }
.status-modul { flex: none; font-size: 11px; font-weight: 800; letter-spacing: .06em; padding: 4px 9px; border-radius: 6px; color: var(--warna); background: color-mix(in srgb, var(--warna) 14%, transparent); }
.status-modul.baik { color: var(--baik); } .status-modul.waspada { color: var(--waspada); } .status-modul.bahaya { color: var(--bahaya); }
/* ---- Grafik, negara, kejadian ---- */
.legenda { list-style: none; margin: 0 0 8px; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: var(--teks-2); }
.legenda li { display: inline-flex; align-items: center; gap: 7px; }
.legenda b { color: var(--teks); }
.kotak { width: 10px; height: 10px; border-radius: 3px; }
.dua-kolom { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 18px; }
.dua-kolom > * { min-width: 0; }
.lencana.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 14%, transparent); }
.blok { display: block; font-size: 11.5px; }
.lencana + .lencana { margin-left: 4px; }
.negara { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.negara li { display: grid; grid-template-columns: 30px minmax(0, 8em) minmax(0, 1fr) auto; gap: 10px; align-items: center; font-size: 13.5px; }
.kode-negara { display: inline-block; min-width: 26px; padding: 1px 5px; border-radius: 4px; font-size: 11px; font-weight: 700; text-align: center; color: var(--teks-2); background: var(--kartu-2); border: 1px solid var(--garis); }
.negara-nama { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.negara-meter { height: 8px; border-radius: 99px; background: var(--kartu-2); overflow: hidden; }
.negara-meter span { display: block; height: 100%; border-radius: 99px; background: var(--aksen-terang); }
.kejadian { list-style: none; margin: 0; padding: 0; display: grid; }
.kejadian li { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 2px; border-bottom: 1px solid var(--garis); font-size: 13.5px; }
.kejadian li:last-child { border-bottom: 0; }
.kejadian time { font-size: 12.5px; white-space: nowrap; }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
.form { display: grid; gap: 14px; max-width: 620px; }
.form p { margin: 0; }
.baris-3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: start; }
.form-manual { display: grid; grid-template-columns: 1.4fr 1fr 1fr 1.4fr auto; gap: 12px; align-items: end; }
.kirim-manual .tombol { min-height: 42px; }
.daftar-chip { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; }
.chip.besar { padding: 5px 6px 5px 12px; background: var(--kartu-2); font-size: 13px; }
.chip button { display: grid; place-items: center; width: 22px; height: 22px; border: 0; border-radius: 50%; background: transparent; color: var(--teks-3); cursor: pointer; }
.chip button:hover { background: rgba(255, 107, 107, .15); color: var(--bahaya); }
.zona { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr)); gap: 12px; margin-bottom: 14px; }
.zona-item { padding: 14px; border-radius: 12px; background: var(--kartu-2); display: grid; gap: 10px; }
.zona-atas { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.zona-item dl { margin: 0; display: grid; gap: 8px; font-size: 13px; }
.zona-item dt { color: var(--teks-3); font-size: 12px; margin-bottom: 2px; }
.zona-item dd { margin: 0; color: var(--teks-2); overflow-wrap: anywhere; }
.alamat { font-size: 12.5px; color: var(--teks-2); overflow-wrap: anywhere; }
.nowrap { white-space: nowrap; }
.kanan { text-align: right; white-space: nowrap; }
.kaki { margin: 12px 0 0; }
.tabel-wadah { position: relative; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
@media (max-width: 900px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
  .dua-kolom { grid-template-columns: minmax(0, 1fr); }
  .form-manual { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 560px) {
  .baris-3, .form-manual { grid-template-columns: 1fr; }
  .ringkas { grid-template-columns: 1fr; }
  .status-proteksi { grid-template-columns: auto minmax(0, 1fr); }
  .skor { grid-column: 1 / -1; justify-self: center; }
  .perisai-besar { width: 56px; height: 56px; }
  .kejadian li { grid-template-columns: 8px minmax(0, 1fr); }
  .kejadian time { grid-column: 2; }
}
</style>
