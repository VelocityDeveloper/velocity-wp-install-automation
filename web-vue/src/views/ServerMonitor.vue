<script setup>
// Monitoring sistem & keamanan server hosting (sub-menu Server). Data: GET /api/servers/monitor
// (installer_status.py → scripts/server_monitor_agent.py lewat SSH, hanya baca, cache 60 dtk).
// Dasar modul keamanan sendiri pengganti cPGuard; angka cPGuard ditampilkan sebagai pembanding.
import { ref, computed, watch } from 'vue'
import Ikon from '../components/Ikon.vue'
import Info from '../components/Info.vue'
import GrafikGaris from '../components/GrafikGaris.vue'
import { minta, pakaiPolling, ukuranBerkas, waktuLalu, angka } from '../api.js'
import { tabUrl } from '../laravel.js'
import { jenisServer, pcKantor } from '../jenisServer.js'

const monitor = pakaiPolling('/api/servers/monitor', 60000)
const segarkan = ref(false)
async function muatSegar() {
  segarkan.value = true
  try { monitor.data.value = await minta('/api/servers/monitor?segar=1'); monitor.galat.value = null }
  catch (e) { monitor.galat.value = e }
  finally { segarkan.value = false }
}
const servers = computed(() => monitor.data.value?.servers || [])
// Tanpa ?s= → server pertama (Farnaz) yang terbuka
const pilih = tabUrl('s', '')
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || servers.value[0] || null)

// Grafik usage: riwayat dicatat scripts/server-usage-catat tiap 5 mnt (GET /api/servers/riwayat)
const RENTANG = [{ k: '24j', label: '24 jam' }, { k: '7h', label: '7 hari' }, { k: '30h', label: '30 hari' }]
const rentang = tabUrl('r', '24j', { boleh: RENTANG.map((r) => r.k) })
// Hanya riwayat server yang dibuka; server= kosong → server pertama (sama dengan tab bawaan)
const riwayat = pakaiPolling(() => `/api/servers/riwayat?rentang=${rentang.value}&server=${encodeURIComponent(terpilih.value?.name || pilih.value)}`, 300000)
watch(rentang, () => riwayat.muatUlang())
watch(() => terpilih.value?.name, (nama) => {
  if (nama && riwayat.data.value && !(riwayat.data.value.servers || []).some((r) => r.name === nama)) riwayat.muatUlang()
})
// Warna CPU/RAM sama dengan Beranda; Disk/Swap lolos validator dataviz (latar gelap #151a33 & terang #fff)
// Grafik detail per server. Pasangan warna lolos validator dataviz (#151a33 & #fff):
// RAM/Swap = teal/oranye, Masuk/Keluar = biru/oranye; grafik satu seri memakai biru, Disk ungu.
const angkaPendek = (v) => (Math.abs(v) < 10 ? Math.round(v * 10) / 10 : Math.round(v)).toLocaleString('id-ID')
const persen = (v) => `${Math.round(v)}%`
const GRAFIK = [
  { id: 'cpu', judul: 'CPU', seri: [{ kunci: 'cpu', label: 'CPU', warna: '#5b8cff' }], format: persen, persen: true },
  { id: 'load', judul: 'Load average', ket: 'rata 1 menit · garis putus = jumlah core', seri: [{ kunci: 'load', label: 'Load', warna: '#5b8cff' }], format: angkaPendek, acuanCore: true },
  { id: 'mem', judul: 'Memori', seri: [{ kunci: 'ram', label: 'RAM', warna: '#26a88e' }, { kunci: 'swap', label: 'Swap', warna: '#cc7a33' }], format: persen, persen: true },
  { id: 'net', judul: 'Web traffic', ket: 'Mbps · kartu jaringan utama', sumbu: angkaPendek, seri: [{ kunci: 'net_in', label: 'Masuk', warna: '#5b8cff' }, { kunci: 'net_out', label: 'Keluar', warna: '#cc7a33' }], format: (v) => `${angkaPendek(v)} Mbps`, ruang: 108 },
  { id: 'req', judul: 'Request per detik', ket: 'LiteSpeed', sumbu: angkaPendek, seri: [{ kunci: 'req', label: 'Req', warna: '#5b8cff' }], format: (v) => `${angkaPendek(v)}/s`, ruang: 80 },
  { id: 'conn', judul: 'Koneksi live', ket: 'koneksi HTTP/HTTPS aktif', seri: [{ kunci: 'conn', label: 'Koneksi', warna: '#5b8cff' }], format: angkaPendek, ruang: 88 },
  { id: 'disk', judul: 'Disk', ket: 'partisi terpenuh', seri: [{ kunci: 'disk', label: 'Disk', warna: '#a679e6' }], format: persen, persen: true },
]
// Puncak sumbu "rapi" (1/2/4/6/8 × 10^n, terbagi 4 dengan angka bulat) di atas nilai tertinggi
function maksRapi(v) {
  if (!(v > 0)) return 1
  const p = 10 ** Math.floor(Math.log10(v))
  return [1, 2, 4, 6, 8, 10].map((k) => k * p).find((k) => k >= v * 1.05) || 10 * p
}
const nilaiAkhir = (titik, kunci) => { for (let i = titik.length - 1; i >= 0; i--) if (titik[i][kunci] != null) return titik[i][kunci]; return null }
// Request/detik hanya dari LiteSpeed (server hosting); PC Backup juga tanpa web server → koneksi web disembunyikan
const GRAFIK_DISEMBUNYIKAN = { lokal: ['req'], backup: ['req', 'conn'] }
function grafikServer(host, jenis) {
  const titik = titikServer(host)
  const core = (riwayat.data.value?.servers || []).find((r) => r.host === host)?.core
  return GRAFIK.filter((gr) => !(GRAFIK_DISEMBUNYIKAN[jenis] || []).includes(gr.id)).map((gr) => {
    // Seri tanpa data sama sekali (mis. Swap di server tanpa swap) tidak digambar
    const seri = gr.seri.filter((sr) => titik.some((q) => q[sr.kunci] != null))
    const tinggi = Math.max(0, ...seri.map((sr) => puncak(titik, sr.kunci)), gr.acuanCore && core ? core : 0)
    const satu = (sr) => `sekarang ${gr.format(nilaiAkhir(titik, sr.kunci) ?? 0)} · rata ${gr.format(rata(titik, sr.kunci))} · puncak ${gr.format(puncak(titik, sr.kunci))}`
    return { ...gr, seri, ada: seri.length > 0, maks: gr.persen ? 100 : maksRapi(tinggi), acuan: gr.acuanCore && core ? { nilai: core, label: `${core} core` } : null,
      ringkas: seri.length > 1 ? seri.map((sr) => `${sr.label}: ${satu(sr)}`) : seri.map(satu) }
  })
}
const riwayatPerHost = computed(() => Object.fromEntries((riwayat.data.value?.servers || []).map((r) => [r.host, r.titik])))
const titikServer = (host) => riwayatPerHost.value[host] || []
const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
const dua = (v) => String(v).padStart(2, '0')
function formatWaktu(t, lengkap) {
  const d = new Date(t * 1000)
  const jam = `${dua(d.getHours())}.${dua(d.getMinutes())}`
  const tgl = `${d.getDate()} ${BULAN[d.getMonth()]}`
  if (lengkap) return `${tgl}, ${jam}`
  if (rentang.value !== '24j') return tgl
  return d.toDateString() === new Date().toDateString() ? jam : `${tgl} ${jam}`
}
const puncak = (titik, kunci) => titik.reduce((a, q) => (q[kunci] != null && q[kunci] > a ? q[kunci] : a), 0)
const rata = (titik, kunci) => {
  const v = titik.filter((q) => q[kunci] != null).map((q) => q[kunci])
  return v.length ? Math.round((v.reduce((a, b) => a + b, 0) / v.length) * 10) / 10 : 0
}

// Kelompok layanan: satu kelompok dianggap jalan bila salah satu unitnya aktif (litespeed/lsws, mariadb/mysqld…)
const KELOMPOK = [
  { label: 'Panel DirectAdmin', unit: ['directadmin'], penting: true },
  { label: 'Web server', unit: ['litespeed', 'lsws', 'httpd', 'nginx'], penting: true },
  { label: 'Database', unit: ['mariadb', 'mysqld'], penting: true },
  { label: 'Email keluar (Exim)', unit: ['exim'], penting: true },
  { label: 'Email masuk (Dovecot)', unit: ['dovecot'], penting: true },
  { label: 'FTP', unit: ['pure-ftpd', 'proftpd', 'vsftpd'], penting: true },
  { label: 'DNS (named)', unit: ['named'], penting: true },
  { label: 'SSH', unit: ['sshd', 'ssh'], penting: true },
  { label: 'Cron', unit: ['crond', 'cron'], penting: true },
  { label: 'Tailscale', unit: ['tailscaled'], pentingPc: ['lokal', 'backup'] },
  { label: 'ZFS (zed)', unit: ['zfs-zed'], pentingPc: ['backup'] },
  { label: 'Cloudflare Tunnel', unit: ['cloudflared'], pentingPc: ['lokal'] },
  { label: 'Dashboard & installer', unit: ['installer-status'], pentingPc: ['lokal'] },
  { label: 'Login dashboard', unit: ['dash-login'], pentingPc: ['lokal'] },
  { label: 'PHP-FPM', unit: ['php-fpm'] },
  { label: 'LFD (deteksi brute force)', unit: ['lfd'], penting: true },
  { label: 'Anti-spam (rspamd)', unit: ['rspamd'] },
  { label: 'fail2ban', unit: ['fail2ban'] },
  { label: 'Imunify', unit: ['imunify360', 'imunify-antivirus'] },
  { label: 'ClamAV', unit: ['clamd'] },
  { label: 'Redis', unit: ['redis'] },
]
function kelompokLayanan(s) {
  const st = Object.fromEntries((s.layanan || []).map((l) => [l.nama, l.status]))
  return KELOMPOK.filter((k) => k.unit.some((u) => u in st)).map((k) => {
    const unit = k.unit.filter((u) => u in st)
    const aktif = unit.filter((u) => st[u] === 'active')
    return { ...k, penting: k.penting || !!k.pentingPc?.includes(s.jenis), unit, aktif: aktif.length > 0, nama_aktif: aktif[0] || unit[0], status: aktif.length ? 'active' : st[unit[0]] }
  })
}

// Aturan peringatan per server → { judul, teks, tingkat: bahaya|waspada|info }
function periksa(s) {
  if (!s.ok) return [{ judul: 'Tidak tersambung', teks: s.error || 'SSH gagal', tingkat: 'bahaya' }]
  const p = []
  const tambah = (tingkat, judul, teks) => p.push({ tingkat, judul, teks })
  const sis = s.sistem || {}
  for (const k of kelompokLayanan(s)) {
    if (!k.aktif && k.penting) tambah('bahaya', `${k.label} mati`, `${k.unit.join('/')}: ${k.status}`)
  }
  for (const d of sis.disks || []) {
    if (d.persen >= 90) tambah('bahaya', `Disk ${d.mount} ${d.persen}%`, `sisa ${ukuranBerkas(d.free)}`)
    else if (d.persen >= 80) tambah('waspada', `Disk ${d.mount} ${d.persen}%`, `sisa ${ukuranBerkas(d.free)}`)
    if (d.inode >= 85) tambah(d.inode >= 95 ? 'bahaya' : 'waspada', `Inode ${d.mount} ${d.inode}%`, 'jumlah berkas mendekati batas')
  }
  if (sis.load && sis.cpu_core) {
    const r = sis.load[1] / sis.cpu_core
    if (r >= 1.5) tambah('bahaya', 'Load sangat tinggi', `load 5 mnt ${sis.load[1]} untuk ${sis.cpu_core} core`)
    else if (r >= 1) tambah('waspada', 'Load tinggi', `load 5 mnt ${sis.load[1]} untuk ${sis.cpu_core} core`)
  }
  if (sis.ram?.persen >= 90) tambah('waspada', `RAM ${sis.ram.persen}%`, 'memori hampir habis')
  if (sis.swap?.persen >= 80) tambah('waspada', `Swap ${sis.swap.persen}%`, 'memori sering ditukar ke disk')
  if (sis.iowait >= 20) tambah('waspada', `I/O wait ${sis.iowait}%`, 'disk jadi penghambat')
  const fw = s.firewall
  const backup = s.jenis === 'backup'
  const pc = pcKantor(s)
  if (s.jenis === 'lokal') {
    // PC Lokal: dashboard kantor, firewall-nya firewalld (bukan CSF), tanpa DirectAdmin
    if (s.keamanan?.firewalld !== 'running') tambah('waspada', 'Firewall firewalld mati', 'semua port dashboard terbuka di LAN')
  } else if (backup) {
    // PC Backup: bukan server hosting, firewall-nya ufw dan isinya pool ZFS
    if (s.keamanan?.ufw !== 'active') tambah('waspada', 'Firewall ufw mati', 'FTP/SSH terbuka untuk semua jaringan')
    for (const pl of s.penyimpanan?.pool || []) {
      if (pl.health !== 'ONLINE') tambah('bahaya', `Pool ZFS ${pl.nama} ${pl.health}`, 'cek zpool status, disk bermasalah')
    }
    if (!s.penyimpanan) tambah('bahaya', 'Pool ZFS tidak terbaca', 'zpool list gagal atau pool belum diimpor')
  } else if (!fw) tambah('bahaya', 'Firewall CSF tidak ada', '/etc/csf/csf.conf tidak ditemukan')
  else {
    if (fw.TESTING === '1') tambah('bahaya', 'CSF mode TESTING', 'aturan firewall dihapus otomatis tiap 5 menit')
    if (fw.LF_DAEMON !== '1') tambah('bahaya', 'LFD nonaktif di csf.conf', 'LF_DAEMON bukan 1, brute force tidak diblokir')
    if (fw.DENY_IP_LIMIT && fw.deny_permanen >= Number(fw.DENY_IP_LIMIT)) tambah('info', 'Daftar blokir permanen penuh', `${fw.deny_permanen}/${fw.DENY_IP_LIMIT}, IP lama tergeser keluar`)
  }
  const k = s.keamanan || {}
  if (k.ssh_permitrootlogin === 'yes' && k.ssh_passwordauthentication === 'yes') tambah('waspada', 'Root SSH boleh pakai sandi', `port ${k.ssh_port}, sebaiknya kunci SSH saja`)
  if (pc) { /* bukan server hosting: tanpa ModSecurity */ } else if (k.modsecurity === 'yes' && (!k.modsecurity_ruleset || k.modsecurity_ruleset === 'no')) tambah('waspada', 'ModSecurity tanpa ruleset', 'WAF aktif tapi belum ada aturan (komodo/owasp)')
  else if (k.modsecurity !== 'yes') tambah('waspada', 'ModSecurity mati', 'tidak ada WAF di web server')
  if (k.perlu_reboot) tambah('waspada', 'Perlu reboot', 'kernel/library baru belum dipakai')
  const h = s.hosting || {}
  if (h.antrean_email >= 1000) tambah('bahaya', `Antrean email ${angka(h.antrean_email)}`, 'kemungkinan ada akun mengirim spam')
  else if (h.antrean_email >= 300) tambah('waspada', `Antrean email ${angka(h.antrean_email)}`, 'periksa pengirim terbanyak')
  if (s.cpguard && Object.values(s.cpguard.proses || {}).some((v) => !v)) tambah('waspada', 'Proses cPGuard berhenti', Object.entries(s.cpguard.proses).filter(([, v]) => !v).map(([n]) => n).join(', '))
  if (s.cpguard?.malware) tambah('bahaya', `cPGuard: ${s.cpguard.malware} malware 24 jam`, 'cek Malware Scanner cPGuard')
  for (const [bagian, g] of Object.entries(s.galat || {})) tambah('info', `Data ${bagian} gagal dibaca`, g)
  const urut = { bahaya: 0, waspada: 1, info: 2 }
  return p.sort((a, b) => urut[a.tingkat] - urut[b.tingkat])
}
const skor = (daftar) => Math.max(0, 100 - daftar.filter((x) => x.tingkat === 'bahaya').length * 20 - daftar.filter((x) => x.tingkat === 'waspada').length * 7)
const tingkatUmum = (daftar) => (daftar.some((x) => x.tingkat === 'bahaya') ? 'bahaya' : daftar.some((x) => x.tingkat === 'waspada') ? 'waspada' : 'baik')
const LABEL_TINGKAT = { baik: 'Sehat', waspada: 'Perlu dicek', bahaya: 'Bermasalah' }

const hasil = computed(() => servers.value.map((s) => {
  const p = periksa(s)
  return { s, periksa: p, skor: skor(p), tingkat: tingkatUmum(p) }
}))
const pilihan = computed(() => hasil.value.find((h) => h.s === terpilih.value) || null)

const ringkas = computed(() => {
  const ok = servers.value.filter((s) => s.ok)
  return {
    sehat: hasil.value.filter((h) => h.tingkat === 'baik').length,
    online: ok.length,
    layananMati: hasil.value.reduce((a, h) => a + h.periksa.filter((p) => p.judul.endsWith(' mati') && p.tingkat === 'bahaya').length, 0),
    blokir: ok.reduce((a, s) => a + (s.firewall?.blokir_24j || 0), 0),
    gagal: ok.reduce((a, s) => a + (s.firewall?.gagal_24j || 0), 0),
    akun: ok.reduce((a, s) => a + (s.hosting?.akun || 0), 0),
    cpgMalware: ok.reduce((a, s) => a + (s.cpguard?.malware || 0), 0),
    cpgWaf: ok.reduce((a, s) => a + (s.cpguard?.waf || 0), 0),
  }
})

const tingkatPersen = (p) => (p >= 90 ? 'bahaya' : p >= 75 ? 'waspada' : '')
const lamaNyala = (u) => (u >= 86400 ? `${Math.floor(u / 86400)} hari` : `${Math.floor(u / 3600)} jam`)
const PEMICU = {
  LF_SSHD: 'SSH', LF_FTPD: 'FTP', LF_SMTPAUTH: 'SMTP auth', LF_POP3D: 'POP3', LF_IMAPD: 'IMAP', LF_DIRECTADMIN: 'DirectAdmin',
  LF_MODSEC: 'ModSecurity', LF_CPANEL: 'Panel', LF_HTACCESS: 'htaccess', LF_DISTATTACK: 'Serangan terdistribusi', LF_DISTFTP: 'FTP terdistribusi',
  LF_DISTSMTP: 'SMTP terdistribusi', LF_CUSTOMTRIGGER: 'Custom', LF_PORTFLOOD: 'Port flood', LF_CT: 'Koneksi berlebih',
}
const pemicu = (k) => PEMICU[k] || k.replace(/^LF_/, '')

function modulKeamanan(s) {
  const k = s.keamanan || {}, fw = s.firewall, cpg = s.cpguard
  const m = []
  if (s.jenis === 'lokal') {
    const f2b = (s.layanan || []).find((l) => l.nama === 'fail2ban')
    m.push({ judul: 'Firewall firewalld', teks: k.firewalld || 'tidak terpasang', st: k.firewalld === 'running' ? 'baik' : 'waspada', ikon: 'perisai' })
    m.push({ judul: 'Blokir brute force (fail2ban)', teks: f2b ? f2b.status : 'tidak terpasang', st: f2b?.status === 'active' ? 'baik' : 'waspada', ikon: 'kunci' })
    m.push({ judul: 'SSH', teks: `port ${k.ssh_port || '?'} · root ${k.ssh_permitrootlogin || '?'} · sandi ${k.ssh_passwordauthentication || '?'}`, st: k.ssh_passwordauthentication === 'yes' ? 'waspada' : 'baik', ikon: 'server' })
    m.push({ judul: 'Kernel & paket', teks: k.perlu_reboot ? 'perlu reboot agar pembaruan dipakai' : k.perlu_reboot === false ? 'tidak perlu reboot' : 'status tidak diketahui', st: k.perlu_reboot ? 'waspada' : 'baik', ikon: 'ulang' })
    m.push({ judul: 'SELinux', teks: k.selinux || 'tidak diketahui', st: 'info', ikon: 'kunci' })
    return m
  }
  if (s.jenis === 'backup') {
    m.push({ judul: 'Firewall ufw', teks: k.ufw || 'tidak terpasang', st: k.ufw === 'active' ? 'baik' : 'waspada', ikon: 'perisai' })
    const sandiBackup = k.ssh_passwordauthentication === 'yes'
    m.push({ judul: 'SSH', teks: `port ${k.ssh_port || '?'} · root ${k.ssh_permitrootlogin || '?'} · sandi ${k.ssh_passwordauthentication || '?'}`, st: sandiBackup ? 'waspada' : 'baik', ikon: 'server' })
    m.push({ judul: 'Kernel & paket', teks: k.perlu_reboot ? 'perlu reboot agar pembaruan dipakai' : k.perlu_reboot === false ? 'tidak perlu reboot' : 'status tidak diketahui', st: k.perlu_reboot ? 'waspada' : 'baik', ikon: 'ulang' })
    return m
  }
  m.push(fw
    ? { judul: 'Firewall CSF', teks: `v${fw.versi || '?'} · ${fw.TESTING === '1' ? 'mode TESTING' : 'mode produksi'} · ${angka(fw.allow)} IP diizinkan`, st: fw.TESTING === '1' ? 'bahaya' : 'baik', ikon: 'perisai' }
    : { judul: 'Firewall CSF', teks: 'tidak terpasang', st: 'bahaya', ikon: 'perisai' })
  if (fw) {
    const batas = ['LF_SSHD', 'LF_SMTPAUTH', 'LF_IMAPD', 'LF_FTPD', 'LF_DIRECTADMIN'].filter((x) => fw[x]).map((x) => `${pemicu(x)} ${fw[x]}`).join(' · ')
    m.push({ judul: 'Blokir brute force (LFD)', teks: fw.LF_DAEMON === '1' ? `batas gagal: ${batas}` : 'LF_DAEMON mati', st: fw.LF_DAEMON === '1' ? 'baik' : 'bahaya', ikon: 'kunci' })
  }
  const sandi = k.ssh_permitrootlogin === 'yes' && k.ssh_passwordauthentication === 'yes'
  m.push({ judul: 'SSH', teks: `port ${k.ssh_port || '?'} · root ${k.ssh_permitrootlogin || '?'} · sandi ${k.ssh_passwordauthentication || '?'}`, st: sandi ? 'waspada' : 'baik', ikon: 'server' })
  const ruleset = k.modsecurity_ruleset && k.modsecurity_ruleset !== 'no'
  m.push({ judul: 'WAF ModSecurity', teks: k.modsecurity === 'yes' ? (ruleset ? `ruleset ${k.modsecurity_ruleset}` : 'aktif, ruleset belum dipasang') : 'mati', st: k.modsecurity === 'yes' && ruleset ? 'baik' : 'waspada', ikon: 'perisai' })
  m.push({ judul: 'Kernel & paket', teks: k.perlu_reboot ? 'perlu reboot agar pembaruan dipakai' : k.perlu_reboot === false ? 'tidak perlu reboot' : 'status tidak diketahui', st: k.perlu_reboot ? 'waspada' : 'baik', ikon: 'ulang' })
  m.push({ judul: 'SELinux', teks: k.selinux || 'tidak diketahui', st: 'info', ikon: 'kunci' })
  if (cpg) {
    const mati = Object.entries(cpg.proses || {}).filter(([, v]) => !v).map(([n]) => n)
    m.push({ judul: 'cPGuard (pembanding)', teks: `v${cpg.versi || '?'} · ${mati.length ? `berhenti: ${mati.join(', ')}` : 'proses berjalan'}`, st: mati.length ? 'waspada' : 'baik', ikon: 'pantau' })
  }
  return m
}
const LABEL_MODUL = { baik: 'AKTIF', waspada: 'CEK', bahaya: 'MATI', info: 'INFO' }
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Monitoring Server</h1>
        <p class="redup">Kesehatan sistem, layanan, firewall, dan keamanan tiap server hosting dan PC kantor (bertag). Dibaca langsung lewat SSH, tanpa cPGuard.</p>
      </div>
      <div class="kepala-aksi">
        <span v-if="monitor.data.value?.diambil" class="redup">Diperbarui {{ waktuLalu(monitor.data.value.diambil) }}</span>
        <button type="button" class="tombol kecil" :disabled="segarkan" @click="muatSegar"><Ikon nama="ulang" :ukuran="16" /> {{ segarkan ? 'Memeriksa…' : 'Periksa ulang' }}</button>
      </div>
    </header>

    <!-- Skeleton: bentuk halaman tampil selagi SSH ke semua server berjalan (muatan pertama ±10–40 dtk) -->
    <div v-if="monitor.memuat.value && !monitor.data.value" class="skeleton" aria-busy="true">
      <p class="redup status-muat" role="status">Memeriksa semua server lewat SSH (±10–40 detik)…</p>
      <div class="ringkas">
        <div v-for="i in 4" :key="i" class="kartu tile"><span class="sk sk-ikon" /><div><span class="sk sk-teks" /><span class="sk sk-angka" /><span class="sk sk-teks pendek" /></div></div>
      </div>
      <div class="sk-menu"><span v-for="i in 6" :key="i" class="sk sk-pil" /></div>
      <section class="kartu sk-banner"><span class="sk sk-ikon besar" /><div><span class="sk sk-teks" /><span class="sk sk-angka" /><span class="sk sk-teks panjang" /><span class="sk sk-teks panjang" /></div><span class="sk sk-cincin" /></section>
      <section class="kartu">
        <span class="sk sk-judul" />
        <div class="grafik-grid"><div v-for="i in 4" :key="i" class="grafik-item"><span class="sk sk-teks" /><span class="sk sk-grafik" /></div></div>
      </section>
    </div>
    <p v-else-if="monitor.galat.value && !monitor.data.value" class="pesan-status bahaya">Gagal memuat: {{ monitor.galat.value.message }}</p>
    <p v-else-if="monitor.data.value?.error" class="pesan-status bahaya">Gagal memuat: {{ monitor.data.value.error }}</p>

    <template v-else-if="monitor.data.value">
      <div class="ringkas">
        <div class="kartu tile">
          <span class="tile-ikon" :class="ringkas.sehat === servers.length ? 'hijau' : 'kuning'"><Ikon nama="server" :ukuran="20" /></span>
          <div><span class="redup">Server sehat</span><b>{{ ringkas.sehat }} / {{ servers.length }}</b><small class="redup">{{ ringkas.online }} tersambung · {{ angka(ringkas.akun) }} akun</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon" :class="ringkas.layananMati ? 'merah' : 'hijau'"><Ikon nama="daya" :ukuran="20" /></span>
          <div><span class="redup">Layanan penting mati</span><b>{{ ringkas.layananMati }}</b><small class="redup">web, database, email, DNS, SSH…</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon ungu"><Ikon nama="perisai" :ukuran="20" /></span>
          <div><span class="redup">IP diblokir LFD · 24 jam</span><b>{{ angka(ringkas.blokir) }}</b><small class="redup">{{ angka(ringkas.gagal) }} percobaan login gagal</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon" :class="ringkas.cpgMalware ? 'merah' : 'hijau'"><Ikon nama="pantau" :ukuran="20" /></span>
          <div><span class="redup">cPGuard · 24 jam <Info label="Tentang angka cPGuard" rata="kanan"><p>Angka dari database cPGuard sebagai pembanding selama modul keamanan sendiri dibangun (jalan paralel).</p></Info></span><b>{{ angka(ringkas.cpgMalware) }} malware</b><small class="redup">{{ angka(ringkas.cpgWaf) }} kejadian WAF</small></div>
        </div>
      </div>

      <nav class="sub-menu" aria-label="Pilih server">
        <button v-for="h in hasil" :key="h.s.host" type="button" :class="{ aktif: terpilih === h.s }" :aria-current="terpilih === h.s ? 'page' : undefined" @click="pilih = h.s.name">
          <span class="titik" :class="h.tingkat" aria-hidden="true" /> {{ h.s.name }}
          <span class="lencana" :class="jenisServer(h.s.jenis).kelas" :title="jenisServer(h.s.jenis).ket">{{ jenisServer(h.s.jenis).label }}</span>
          <span v-if="h.periksa.filter((p) => p.tingkat === 'bahaya').length" class="hitung">{{ h.periksa.filter((p) => p.tingkat === 'bahaya').length }}</span>
        </button>
      </nav>

      <!-- ================= Detail satu server ================= -->
      <template v-if="pilihan">
        <section class="kartu status-proteksi" :class="pilihan.tingkat" aria-labelledby="judul-status">
          <div class="perisai-besar" aria-hidden="true"><Ikon nama="server" :ukuran="40" /></div>
          <div class="status-teks">
            <span class="label-kecil">{{ terpilih.name }} · {{ terpilih.sistem?.hostname || terpilih.host }} <span class="lencana" :class="jenisServer(terpilih.jenis).kelas">{{ jenisServer(terpilih.jenis).label }}</span></span>
            <h2 id="judul-status">{{ LABEL_TINGKAT[pilihan.tingkat] }}</h2>
            <p class="redup">{{ terpilih.sistem?.os }} · kernel {{ terpilih.sistem?.kernel }} · nyala {{ lamaNyala(terpilih.sistem?.uptime || 0) }} · SSH {{ angka(terpilih.ms) }} ms</p>
            <ul v-if="pilihan.periksa.length" class="masalah">
              <li v-for="m in pilihan.periksa" :key="m.judul"><span class="titik" :class="m.tingkat === 'info' ? 'biru' : m.tingkat" /> <b>{{ m.judul }}:</b> {{ m.teks }}</li>
            </ul>
          </div>
          <div class="skor" role="img" :aria-label="`Skor kesehatan ${pilihan.skor} dari 100`">
            <svg viewBox="0 0 120 120" aria-hidden="true">
              <circle cx="60" cy="60" r="50" class="skor-jalur" />
              <circle cx="60" cy="60" r="50" class="skor-isi" :style="{ strokeDasharray: `${(pilihan.skor / 100) * 314.16} 314.16` }" />
            </svg>
            <div class="skor-angka"><b>{{ pilihan.skor }}</b><span>skor</span></div>
          </div>
        </section>

        <template v-if="terpilih.ok">
          <section class="kartu" aria-labelledby="judul-grafik">
            <div class="kartu-judul">
              <h2 id="judul-grafik"><Ikon nama="token" :ukuran="16" /> Grafik pemakaian</h2>
              <div class="tab" role="tablist" aria-label="Rentang grafik">
                <button v-for="r in RENTANG" :key="r.k" type="button" role="tab" :aria-selected="rentang === r.k" :class="{ aktif: rentang === r.k }" @click="rentang = r.k">{{ r.label }}</button>
              </div>
            </div>
            <div v-if="riwayat.memuat.value && !riwayat.data.value" class="grafik-grid" aria-busy="true">
              <div v-for="gr in GRAFIK" :key="gr.id" class="grafik-item"><div class="grafik-kepala"><b>{{ gr.judul }}</b></div><span class="sk sk-grafik" /></div>
            </div>
            <div v-else-if="titikServer(terpilih.host).length" class="grafik-grid">
              <div v-for="gr in grafikServer(terpilih.host, terpilih.jenis)" :key="gr.id" class="grafik-item">
                <div class="grafik-kepala"><b>{{ gr.judul }}</b><span v-if="gr.ket" class="redup">{{ gr.ket }}</span></div>
                <template v-if="gr.ada">
                  <ul v-if="gr.seri.length > 1" class="legenda"><li v-for="sr in gr.seri" :key="sr.kunci"><span class="kotak" :style="{ background: sr.warna }" /> {{ sr.label }}</li></ul>
                  <GrafikGaris :titik="titikServer(terpilih.host)" :seri="gr.seri" :format-waktu="formatWaktu" :tinggi="170" :maks="gr.maks" :format="gr.format" :acuan="gr.acuan" :ruang-label="gr.ruang || 64" :format-sumbu="gr.sumbu || null" />
                  <small v-for="r in gr.ringkas" :key="r" class="redup ringkas-grafik">{{ r }}</small>
                </template>
                <p v-else class="redup kosong">Belum ada data di rentang ini; mulai tercatat sejak 12 Okt.</p>
              </div>
            </div>
            <p v-else class="redup">Riwayat belum ada. Pencatatan berjalan tiap 5 menit.</p>
          </section>

          <section class="kartu" aria-labelledby="judul-resource">
            <div class="kartu-judul"><h2 id="judul-resource"><Ikon nama="dashboard" :ukuran="16" /> Resource sistem</h2></div>
            <div class="resource">
              <div class="res">
                <div class="res-kepala"><span>CPU</span><b>{{ terpilih.sistem.cpu }}%</b></div>
                <div class="meter" :class="tingkatPersen(terpilih.sistem.cpu)"><i :style="{ width: `${terpilih.sistem.cpu}%` }" /></div>
                <small class="redup">{{ terpilih.sistem.cpu_core }} core · I/O wait {{ terpilih.sistem.iowait }}%</small>
              </div>
              <div class="res">
                <div class="res-kepala"><span>Load (1 · 5 · 15 mnt)</span><b>{{ terpilih.sistem.load[1].toFixed(2) }}</b></div>
                <div class="meter" :class="tingkatPersen((terpilih.sistem.load[1] / terpilih.sistem.cpu_core) * 100)"><i :style="{ width: `${Math.min(100, (terpilih.sistem.load[1] / terpilih.sistem.cpu_core) * 100)}%` }" /></div>
                <small class="redup">{{ terpilih.sistem.load.map((v) => v.toFixed(2)).join(' · ') }}</small>
              </div>
              <div v-if="terpilih.sistem.ram" class="res">
                <div class="res-kepala"><span>RAM</span><b>{{ terpilih.sistem.ram.persen }}%</b></div>
                <div class="meter" :class="tingkatPersen(terpilih.sistem.ram.persen)"><i :style="{ width: `${terpilih.sistem.ram.persen}%` }" /></div>
                <small class="redup">{{ ukuranBerkas(terpilih.sistem.ram.used) }} dari {{ ukuranBerkas(terpilih.sistem.ram.total) }}</small>
              </div>
              <div v-if="terpilih.sistem.swap" class="res">
                <div class="res-kepala"><span>Swap</span><b>{{ terpilih.sistem.swap.persen }}%</b></div>
                <div class="meter" :class="tingkatPersen(terpilih.sistem.swap.persen)"><i :style="{ width: `${terpilih.sistem.swap.persen}%` }" /></div>
                <small class="redup">{{ ukuranBerkas(terpilih.sistem.swap.used) }} dari {{ ukuranBerkas(terpilih.sistem.swap.total) }}</small>
              </div>
              <div v-for="d in terpilih.sistem.disks" :key="d.mount" class="res">
                <div class="res-kepala"><span>Disk {{ d.mount }}</span><b>{{ d.persen }}%</b></div>
                <div class="meter" :class="tingkatPersen(d.persen)"><i :style="{ width: `${d.persen}%` }" /></div>
                <small class="redup">Sisa {{ ukuranBerkas(d.free) }} dari {{ ukuranBerkas(d.total) }}<template v-if="d.inode != null"> · inode {{ d.inode }}%</template></small>
              </div>
            </div>
          </section>

          <section class="kartu" aria-labelledby="judul-layanan">
            <div class="kartu-judul">
              <h2 id="judul-layanan"><Ikon nama="daya" :ukuran="16" /> Layanan</h2>
              <span class="redup">{{ kelompokLayanan(terpilih).filter((k) => k.aktif).length }} dari {{ kelompokLayanan(terpilih).length }} berjalan</span>
            </div>
            <ul class="modul">
              <li v-for="k in kelompokLayanan(terpilih)" :key="k.label" :class="k.aktif ? 'baik' : k.penting ? 'bahaya' : 'redam'">
                <span class="modul-ikon"><Ikon :nama="k.aktif ? 'centang' : 'tutup'" :ukuran="18" /></span>
                <div class="modul-teks"><b>{{ k.label }}</b><span class="redup">{{ k.nama_aktif }} · {{ k.status }}</span></div>
                <span class="status-modul">{{ k.aktif ? 'JALAN' : k.penting ? 'MATI' : 'NONAKTIF' }}</span>
              </li>
            </ul>
          </section>

          <section class="kartu" aria-labelledby="judul-keamanan">
            <div class="kartu-judul"><h2 id="judul-keamanan"><Ikon nama="perisai" :ukuran="16" /> Modul keamanan</h2></div>
            <ul class="modul">
              <li v-for="m in modulKeamanan(terpilih)" :key="m.judul" :class="m.st">
                <span class="modul-ikon"><Ikon :nama="m.ikon" :ukuran="18" /></span>
                <div class="modul-teks"><b>{{ m.judul }}</b><span class="redup">{{ m.teks }}</span></div>
                <span class="status-modul">{{ LABEL_MODUL[m.st] }}</span>
              </li>
            </ul>
          </section>

          <div v-if="terpilih.firewall" class="dua-kolom">
            <section class="kartu" aria-labelledby="judul-blokir">
              <div class="kartu-judul">
                <h2 id="judul-blokir"><Ikon nama="kunci" :ukuran="16" /> Blokir LFD terbaru</h2>
                <span class="redup">{{ angka(terpilih.firewall.blokir_24j) }} dalam 24 jam · permanen {{ angka(terpilih.firewall.deny_permanen) }} · sementara {{ angka(terpilih.firewall.deny_sementara) }}</span>
              </div>
              <p v-if="!terpilih.firewall.terbaru.length" class="redup">Tidak ada IP yang diblokir dalam 24 jam.</p>
              <div v-else class="tabel-wadah">
                <table class="tabel">
                  <thead><tr><th scope="col">IP</th><th scope="col">Lewat</th><th scope="col" class="kanan">Waktu</th></tr></thead>
                  <tbody>
                    <tr v-for="b in terpilih.firewall.terbaru" :key="b.waktu + b.ip">
                      <td><span class="kode-negara">{{ b.negara }}</span> <code>{{ b.ip }}</code></td>
                      <td><span class="lencana abu">{{ pemicu(b.pemicu) }}</span></td>
                      <td class="kanan redup">{{ b.waktu.slice(5, 16) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
            <section class="kartu" aria-labelledby="judul-asal">
              <div class="kartu-judul"><h2 id="judul-asal"><Ikon nama="luar" :ukuran="16" /> Asal & jenis serangan</h2><span class="redup">24 jam</span></div>
              <p v-if="!terpilih.firewall.per_pemicu.length" class="redup">Belum ada data.</p>
              <template v-else>
                <ul class="batang">
                  <li v-for="[k, n] in terpilih.firewall.per_pemicu" :key="k">
                    <span>{{ pemicu(k) }}</span>
                    <span class="batang-meter"><span :style="{ width: `${(n / terpilih.firewall.per_pemicu[0][1]) * 100}%` }" /></span>
                    <b>{{ n }}</b>
                  </li>
                </ul>
                <p class="label-negara redup">Negara asal</p>
                <ul class="daftar-chip">
                  <li v-for="[k, n] in terpilih.firewall.per_negara" :key="k" class="chip-negara"><span class="kode-negara">{{ k }}</span> {{ n }}</li>
                </ul>
              </template>
            </section>
          </div>

          <div class="dua-kolom">
            <section class="kartu" aria-labelledby="judul-akun">
              <div class="kartu-judul"><h2 id="judul-akun"><Ikon nama="crm" :ukuran="16" /> Akun paling berat saat ini</h2><span class="redup">cuplikan CPU 1 detik</span></div>
              <div class="tabel-wadah">
                <table class="tabel">
                  <thead><tr><th scope="col">User</th><th scope="col" class="kanan">CPU</th><th scope="col" class="kanan">RAM</th><th scope="col" class="kanan">Proses</th></tr></thead>
                  <tbody>
                    <tr v-for="u in terpilih.hosting?.akun_teratas || []" :key="u.user">
                      <td><code>{{ u.user }}</code></td>
                      <td class="kanan"><b :class="{ 'teks-bahaya': u.cpu >= 100 }">{{ u.cpu }}%</b></td>
                      <td class="kanan">{{ u.mem }}%</td>
                      <td class="kanan">{{ u.proses }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <small class="redup">100% = satu core penuh. Server ini punya {{ terpilih.sistem.cpu_core }} core.</small>
            </section>
            <section v-if="terpilih.jenis === 'backup'" class="kartu" aria-labelledby="judul-simpan">
              <div class="kartu-judul"><h2 id="judul-simpan"><Ikon nama="server" :ukuran="16" /> Penyimpanan backup</h2><span class="redup">ZFS</span></div>
              <p v-if="!terpilih.penyimpanan" class="redup">Pool ZFS tidak terbaca.</p>
              <template v-else>
                <div v-for="pl in terpilih.penyimpanan.pool" :key="pl.nama" class="res">
                  <div class="res-kepala"><span>Pool {{ pl.nama }} · {{ pl.health }}</span><b>{{ pl.persen }}%</b></div>
                  <div class="meter" :class="tingkatPersen(pl.persen)"><i :style="{ width: `${pl.persen}%` }" /></div>
                  <small class="redup">Terpakai {{ ukuranBerkas(pl.used) }} · sisa {{ ukuranBerkas(pl.free) }} dari {{ ukuranBerkas(pl.total) }}</small>
                </div>
                <dl class="angka-dl">
                  <div><dt>Snapshot</dt><dd>{{ angka(terpilih.penyimpanan.snapshot) }}</dd></div>
                  <div><dt>Snapshot terakhir</dt><dd>{{ terpilih.penyimpanan.snapshot_terakhir ? waktuLalu(terpilih.penyimpanan.snapshot_terakhir.waktu) : 'belum ada' }}</dd></div>
                </dl>
              </template>
            </section>
            <section v-else-if="terpilih.jenis === 'lokal'" class="kartu" aria-labelledby="judul-web-lokal">
              <div class="kartu-judul"><h2 id="judul-web-lokal"><Ikon nama="dashboard" :ukuran="16" /> Web lokal</h2><span class="redup">nginx · dashboard & server dev</span></div>
              <dl class="angka-dl">
                <div><dt>Koneksi web aktif</dt><dd>{{ angka(terpilih.hosting?.koneksi_web) }}</dd></div>
              </dl>
              <template v-if="terpilih.hosting?.koneksi_ip_teratas?.length">
                <p class="label-negara redup">IP dengan koneksi web terbanyak</p>
                <ul class="daftar-chip">
                  <li v-for="[ip, n] in terpilih.hosting.koneksi_ip_teratas" :key="ip" class="chip-negara"><code>{{ ip }}</code> {{ n }}</li>
                </ul>
              </template>
            </section>
            <section v-else class="kartu" aria-labelledby="judul-hosting">
              <div class="kartu-judul"><h2 id="judul-hosting"><Ikon nama="email" :ukuran="16" /> Hosting</h2></div>
              <dl class="angka-dl">
                <div><dt>Akun · domain</dt><dd>{{ angka(terpilih.hosting?.akun) }} · {{ angka(terpilih.hosting?.domain) }}</dd></div>
                <div><dt>Antrean email</dt><dd :class="{ 'teks-bahaya': terpilih.hosting?.antrean_email >= 300 }">{{ terpilih.hosting?.antrean_email ?? '–' }}</dd></div>
                <div><dt>MySQL thread · slow query</dt><dd>{{ terpilih.hosting?.mysql_threads ?? '–' }} · {{ angka(terpilih.hosting?.mysql_slow) }}</dd></div>
                <div><dt>Koneksi web aktif</dt><dd>{{ angka(terpilih.hosting?.koneksi_web) }}</dd></div>
                <div><dt>Web server · PHP</dt><dd>{{ terpilih.keamanan?.webserver }} · {{ [terpilih.keamanan?.php1_release, terpilih.keamanan?.php2_release].filter((v) => v && v !== 'no').join(', ') }}</dd></div>
                <div v-if="terpilih.cpguard"><dt>cPGuard 24 jam</dt><dd>malware {{ terpilih.cpguard.malware ?? '–' }} · WAF {{ angka(terpilih.cpguard.waf) }} · brute force {{ angka(terpilih.cpguard.bruteforce) }}</dd></div>
              </dl>
              <template v-if="terpilih.hosting?.koneksi_ip_teratas?.length">
                <p class="label-negara redup">IP dengan koneksi web terbanyak</p>
                <ul class="daftar-chip">
                  <li v-for="[ip, n] in terpilih.hosting.koneksi_ip_teratas" :key="ip" class="chip-negara"><code>{{ ip }}</code> {{ n }}</li>
                </ul>
              </template>
            </section>
          </div>
        </template>
      </template>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.kepala-aksi { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.ringkas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.kartu-judul h2 { display: inline-flex; align-items: center; gap: 8px; }
.tile { display: flex; gap: 14px; align-items: center; }
.tile > div { display: grid; gap: 3px; min-width: 0; }
.tile b { font-size: 22px; color: var(--teks-kuat); }
.tile small { font-size: 12px; }
.tile-ikon { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; }
.tile-ikon.merah { color: var(--bahaya); background: color-mix(in srgb, var(--bahaya) 15%, transparent); }
.tile-ikon.kuning { color: var(--waspada); background: color-mix(in srgb, var(--waspada) 15%, transparent); }
.tile-ikon.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 15%, transparent); }
.tile-ikon.hijau { color: var(--baik); background: color-mix(in srgb, var(--baik) 15%, transparent); }
.sub-menu { display: flex; flex-wrap: wrap; gap: 4px; padding: 4px; border-radius: 12px; background: var(--kartu); border: 1px solid var(--garis); }
.sub-menu button { display: inline-flex; align-items: center; gap: 7px; flex: none; border: 0; background: transparent; color: var(--teks-2);
  font: inherit; font-size: 13.5px; font-weight: 600; padding: 9px 14px; border-radius: 9px; cursor: pointer; }
.sub-menu button:hover { color: var(--teks-kuat); background: var(--sorot); }
.sub-menu button.aktif { background: var(--aksen); color: #fff; }
.sub-menu .lencana { font-size: 10px; padding: 0 6px; }
.sub-menu button.aktif .lencana { color: #fff; background: rgba(255, 255, 255, .2); }
.sub-menu .hitung { min-width: 20px; padding: 1px 6px; border-radius: 999px; font-size: 11.5px; background: var(--bahaya); color: #fff; text-align: center; }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); }
.titik.baik { background: var(--baik); }
.titik.waspada { background: var(--waspada); }
.titik.bahaya { background: var(--bahaya); }
.titik.biru { background: var(--aksen-terang); }
.sub-menu button.aktif .titik { box-shadow: 0 0 0 2px #fff; }
/* Tabel ringkasan */
.blok { display: block; font-size: 11.5px; }
.kanan { text-align: right; white-space: nowrap; }
.teks-bahaya { color: var(--bahaya); }
/* Status ala cPGuard */
.status-proteksi { --warna: var(--baik); display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 20px; align-items: center;
  background: linear-gradient(120deg, color-mix(in srgb, var(--warna) 14%, var(--kartu)) 0%, var(--kartu) 60%); border-left: 4px solid var(--warna); }
.status-proteksi.waspada { --warna: var(--waspada); }
.status-proteksi.bahaya { --warna: var(--bahaya); }
.perisai-besar { display: grid; place-items: center; width: 72px; height: 72px; border-radius: 20px; color: var(--warna);
  background: color-mix(in srgb, var(--warna) 16%, transparent); box-shadow: 0 0 0 6px color-mix(in srgb, var(--warna) 7%, transparent); }
.status-teks { display: grid; gap: 4px; min-width: 0; }
.status-teks h2 { font-size: 22px; margin: 0; color: var(--teks-kuat); }
.status-teks p { margin: 0; overflow-wrap: anywhere; }
.label-kecil { font-size: 11.5px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--warna); overflow-wrap: anywhere; }
.masalah { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 4px; font-size: 13px; color: var(--teks-2); }
.skor { position: relative; width: 104px; height: 104px; }
.skor svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.skor circle { fill: none; stroke-width: 10; }
.skor-jalur { stroke: var(--kartu-2); }
.skor-isi { stroke: var(--warna); stroke-linecap: round; transition: stroke-dasharray .6s ease; }
.skor-angka { position: absolute; inset: 0; display: grid; place-content: center; text-align: center; line-height: 1.1; }
.skor-angka b { font-size: 28px; color: var(--teks-kuat); }
.skor-angka span { font-size: 11px; color: var(--teks-3); text-transform: uppercase; letter-spacing: .08em; }
/* Resource */
.resource { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px 18px; }
.res { display: grid; gap: 5px; align-content: start; }
.res-kepala { display: flex; justify-content: space-between; gap: 8px; font-size: 13px; }
.res-kepala b { font-variant-numeric: tabular-nums; }
.res small { font-size: 12px; }
.meter.waspada i { background: var(--waspada); }
.meter.bahaya i { background: var(--bahaya); }
/* Modul */
.modul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr)); gap: 10px; }
.modul li { --warna: var(--baik); display: flex; gap: 12px; align-items: center; padding: 12px 14px; border-radius: 12px; background: var(--kartu-2); border: 1px solid transparent; }
.modul li.waspada { --warna: var(--waspada); border-color: color-mix(in srgb, var(--waspada) 35%, transparent); }
.modul li.bahaya { --warna: var(--bahaya); border-color: color-mix(in srgb, var(--bahaya) 40%, transparent); }
.modul li.info { --warna: var(--aksen-terang); }
.modul li.redam { --warna: var(--teks-3); }
.modul-ikon { flex: none; display: grid; place-items: center; width: 36px; height: 36px; border-radius: 10px; color: var(--warna); background: color-mix(in srgb, var(--warna) 14%, transparent); }
.modul-teks { display: grid; gap: 2px; min-width: 0; flex: 1; font-size: 13px; overflow-wrap: anywhere; }
.modul-teks b { font-size: 13.5px; }
.status-modul { flex: none; font-size: 11px; font-weight: 800; letter-spacing: .06em; padding: 4px 9px; border-radius: 6px; color: var(--warna); background: color-mix(in srgb, var(--warna) 14%, transparent); }
/* Firewall & hosting */
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.legenda { list-style: none; margin: 0 0 6px; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: var(--teks-2); }
.legenda li { display: inline-flex; align-items: center; gap: 7px; }
.kotak { width: 10px; height: 10px; border-radius: 3px; }
.skeleton { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; }
.status-muat { margin: 0; }
.skeleton .tile > div { flex: 1; }
.skeleton .tile { min-height: 112px; }
.sk { --sk-dasar: color-mix(in srgb, var(--kartu-2), var(--teks) 7%); --sk-kilap: color-mix(in srgb, var(--kartu-2), var(--teks) 15%);
  display: block; border-radius: 6px; background: linear-gradient(90deg, var(--sk-dasar) 25%, var(--sk-kilap) 50%, var(--sk-dasar) 75%); background-size: 200% 100%; animation: sk-kilau 1.4s ease-in-out infinite; }
.sk-ikon { flex: none; width: 44px; height: 44px; border-radius: 12px; }
.sk-ikon.besar { width: 72px; height: 72px; border-radius: 20px; }
.sk-teks { height: 11px; width: 60%; margin: 4px 0; }
.sk-teks.pendek { width: 40%; }
.sk-teks.panjang { width: 85%; }
.sk-angka { height: 22px; width: 45%; margin: 4px 0; }
.sk-menu { display: flex; gap: 8px; padding: 8px; border-radius: 12px; background: var(--kartu); border: 1px solid var(--garis); overflow: hidden; }
.sk-pil { flex: none; height: 30px; width: 96px; border-radius: 9px; }
.sk-judul { height: 14px; width: 200px; max-width: 60%; margin-bottom: 18px; }
.sk-banner { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 20px; align-items: center; }
.sk-cincin { width: 104px; height: 104px; border-radius: 50%; }
.sk-grafik { height: 170px; margin: 8px 0 12px; border-radius: 10px; }
@keyframes sk-kilau { from { background-position: 100% 0; } to { background-position: -100% 0; } }
@media (prefers-reduced-motion: reduce) { .sk { animation: none; } }
.grafik-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(440px, 100%), 1fr)); gap: 14px; }
.ringkas-grafik { display: block; margin: 2px 0 0; font-size: 12px; }
.ringkas-grafik:last-child { margin-bottom: 8px; }
.kosong { margin: 10px 0 14px; font-size: 13px; }
.grafik-item { min-width: 0; padding: 12px 14px 6px; border-radius: 12px; background: var(--kartu-2); }
.grafik-kepala { display: flex; justify-content: space-between; align-items: baseline; gap: 4px 12px; flex-wrap: wrap; margin-bottom: 6px; font-size: 13.5px; }
.grafik-kepala span { font-size: 12.5px; }
.grafik-kepala.jarak { margin-top: 18px; }
.dua-kolom { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); gap: 18px; }
.dua-kolom > * { min-width: 0; }
.kode-negara { display: inline-block; min-width: 26px; padding: 1px 5px; border-radius: 4px; font-size: 11px; font-weight: 700; text-align: center; color: var(--teks-2); background: var(--kartu-2); border: 1px solid var(--garis); }
.batang { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.batang li { display: grid; grid-template-columns: minmax(0, 8em) minmax(0, 1fr) auto; gap: 10px; align-items: center; font-size: 13.5px; }
.batang-meter { height: 8px; border-radius: 99px; background: var(--kartu-2); overflow: hidden; }
.batang-meter span { display: block; height: 100%; border-radius: 99px; background: var(--ungu); }
.label-negara { margin: 16px 0 8px; font-size: 12.5px; }
.daftar-chip { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; }
.chip-negara { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px 4px 5px; border-radius: 999px; background: var(--kartu-2); font-size: 13px; }
.angka-dl { margin: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.angka-dl dt { font-size: 12px; color: var(--teks-3); margin-bottom: 3px; }
.angka-dl dd { margin: 0; font-weight: 600; color: var(--teks-kuat); overflow-wrap: anywhere; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
@media (max-width: 900px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
  .dua-kolom { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 560px) {
  .ringkas { grid-template-columns: 1fr; }
  .sk-banner { grid-template-columns: auto minmax(0, 1fr); }
  .sk-cincin { display: none; }
  .status-proteksi { grid-template-columns: auto minmax(0, 1fr); }
  .skor { grid-column: 1 / -1; justify-self: center; }
  .perisai-besar { width: 56px; height: 56px; }
  .angka-dl { grid-template-columns: 1fr; }
}
</style>
