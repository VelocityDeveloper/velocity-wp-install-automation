<script setup>
// Proteksi server hosting (sub-menu Server): kelola firewall CSF/LFD tiap server — blokir/lepas/whitelist IP
// dan setelan deteksi brute force. Data: GET /api/servers/firewall (installer_status.py → scripts/server_firewall_agent.py
// lewat SSH, cache 60 dtk), cek IP: GET /api/servers/firewall/cek, aksi: POST /api/servers/firewall/aksi (dicatat di riwayat).
// IP kantor, IP server sendiri, LAN, dan IP whitelist ditolak agen saat diblokir.
import { ref, reactive, computed, watch } from 'vue'
import Ikon from '../components/Ikon.vue'
import Info from '../components/Info.vue'
import Dialog from '../components/Dialog.vue'
import LogFirewall from '../components/LogFirewall.vue'
import LogWaf from '../components/LogWaf.vue'
import { konfirmasi } from '../konfirmasi.js'
import { minta, kirim, pakaiPolling, tanggalWaktu, waktuLalu, angka } from '../api.js'
import { tabUrl } from '../laravel.js'

const fw = pakaiPolling('/api/servers/firewall', 120000)
const riwayat = pakaiPolling('/api/servers/firewall/riwayat', 120000)
const segarkan = ref(false)
async function muatSegar() {
  segarkan.value = true
  try { fw.data.value = await minta('/api/servers/firewall?segar=1'); fw.galat.value = null }
  catch (e) { fw.galat.value = e }
  finally { segarkan.value = false }
  riwayat.muatUlang()
}
const servers = computed(() => fw.data.value?.servers || [])
const pilih = tabUrl('s', '')
const terpilih = computed(() => servers.value.find((s) => s.name === pilih.value) || null)
const TAB = ['blokir', 'sementara', 'whitelist', 'log', 'waf', 'setelan', 'riwayat']
const tab = tabUrl('tab', 'blokir', { boleh: TAB })

// Nama pelaku dicatat di riwayat aksi (dashboard tanpa akun per orang)
const oleh = ref('')
try { oleh.value = localStorage.getItem('proteksi-oleh') || '' } catch { /* penyimpanan diblokir */ }
watch(oleh, (v) => { try { localStorage.setItem('proteksi-oleh', v) } catch { /* abaikan */ } })

const PESAN = {
  invalid_oleh: 'Isi "Nama Anda" di kanan atas dulu — setiap perubahan firewall dicatat atas nama Anda.',
  ip_tidak_sah: 'Alamat IP / CIDR tidak sah.',
  ip_kantor: 'Itu IP kantor (dashboard ini tersambung lewat IP tersebut) — tidak boleh diblokir.',
  ip_server: 'Itu IP milik server sendiri — tidak boleh diblokir.',
  ip_lokal: 'IP lokal/LAN tidak boleh diblokir.',
  ada_di_whitelist: 'IP ada di whitelist server ini. Hapus dari whitelist dulu bila memang mau diblokir.',
  cidr_terlalu_lebar: 'Rentang terlalu lebar: paling lebar /16 (IPv4) atau /48 (IPv6).',
  ttl_tidak_sah: 'Durasi tidak dikenal.',
  nilai_tidak_sah: 'Ada nilai setelan di luar batas yang diizinkan.',
  setelan_tidak_dikenal: 'Setelan itu tidak bisa diubah dari dashboard.',
  csf_restart_gagal: 'csf -r gagal — csf.conf dikembalikan ke salinan sebelumnya.',
  server_tidak_dikenal: 'Server tidak dikenal; muat ulang halaman.',
  forbidden: 'Ditolak: hanya bisa diubah dari halaman dashboard ini.',
  timeout: 'Server tidak menjawab (timeout).',
}
const pesanGalat = (e) => PESAN[e] || e || 'gagal'
const pesan = reactive({ teks: '', galat: false })
const proses = ref(false)

// Jalankan aksi di satu server (host) atau 'semua'; kembalikan hasil per server
async function aksi(body, berhasil) {
  if (!oleh.value.trim()) {
    Object.assign(pesan, { teks: PESAN.invalid_oleh, galat: true })
    document.getElementById('nama-proteksi')?.focus()
    return null
  }
  proses.value = true
  try {
    const r = await kirim('/api/servers/firewall/aksi', { ...body, oleh: oleh.value.trim() })
    const gagal = r.servers.filter((h) => !h.ok)
    if (gagal.length) Object.assign(pesan, { teks: gagal.map((h) => `${h.name}: ${pesanGalat(h.error) || 'gagal'}`).join(' · '), galat: true })
    else Object.assign(pesan, { teks: berhasil, galat: false })
    // Hasil cek terbaru per server langsung memperbarui panel Cek IP
    if (cekHasil.value && r.servers.some((h) => h.cek?.ip === cekHasil.value.ip)) {
      cekHasil.value = { ...cekHasil.value, servers: cekHasil.value.servers.map((s) => {
        const h = r.servers.find((x) => x.host === s.host)
        return h?.cek ? { ...s, ...h.cek, ok: true } : s
      }) }
    }
    muatSegar()
    return r
  } catch (e) {
    Object.assign(pesan, { teks: pesanGalat(e.message), galat: true })
    return null
  } finally {
    proses.value = false
  }
}

// ---- Ringkasan ----
const aktif = (s) => s.ok && s.csf && s.layanan?.csf === 'active' && s.layanan?.lfd === 'active' && s.setelan?.TESTING !== '1'
const batasDeny = (s) => Number(s.setelan?.DENY_IP_LIMIT || 0)
const penuh = (s) => batasDeny(s) && s.deny.length >= batasDeny(s)
const total = computed(() => {
  const ok = servers.value.filter((s) => s.ok && s.csf)
  return {
    deny: ok.reduce((a, s) => a + s.deny.length, 0),
    sementara: ok.reduce((a, s) => a + s.sementara.length, 0),
    allow: ok.reduce((a, s) => a + s.allow.filter((x) => !x.include && !x.aturan).length, 0),
    aktif: servers.value.filter(aktif).length,
    penuh: ok.filter(penuh).length,
    dashboard: ok.reduce((a, s) => a + s.deny.filter((d) => d.sumber === 'dashboard').length, 0),
  }
})
function peringatan(s) {
  const out = []
  if (!s.ok) return [{ tingkat: 'bahaya', teks: `Tidak bisa dibaca: ${pesanGalat(s.error)}` }]
  if (!s.csf) return [{ tingkat: 'bahaya', teks: 'CSF tidak terpasang' }]
  if (s.setelan?.TESTING === '1') out.push({ tingkat: 'bahaya', teks: 'CSF masih mode TESTING — aturan dibuang tiap 5 menit' })
  for (const u of ['csf', 'lfd']) if (s.layanan?.[u] !== 'active') out.push({ tingkat: 'bahaya', teks: `${u.toUpperCase()} ${s.layanan?.[u] || 'mati'}` })
  if (penuh(s)) out.push({ tingkat: 'waspada', teks: `Daftar blokir penuh (${s.deny.length}/${batasDeny(s)}): setiap blokir baru menghapus blokir terlama` })
  if (s.setelan?.CT_LIMIT === '0') out.push({ tingkat: 'info', teks: 'Batas koneksi per IP (CT_LIMIT) mati' })
  return out
}
const tingkat = (s) => { const p = peringatan(s); return p.some((x) => x.tingkat === 'bahaya') ? 'bahaya' : p.some((x) => x.tingkat === 'waspada') ? 'waspada' : 'baik' }

// ---- Cek & tindak IP di semua server ----
const cekIp = ref('')
const cekHasil = ref(null)
const mengecek = ref(false)
async function cek(ip = cekIp.value) {
  ip = (ip || '').trim()
  if (!ip) return
  cekIp.value = ip
  mengecek.value = true
  try { cekHasil.value = await minta(`/api/servers/firewall/cek?ip=${encodeURIComponent(ip)}`) }
  catch (e) { Object.assign(pesan, { teks: pesanGalat(e.message), galat: true }) }
  finally { mengecek.value = false }
}
function statusCek(c) {
  if (!c.ok) return { kelas: 'abu', label: 'Tak terbaca' }
  if (c.deny?.length) return { kelas: 'merah', label: 'Diblokir permanen' }
  if (c.sementara?.length) return { kelas: 'kuning', label: `Diblokir sementara · ${sisa(c.sementara[0].sisa)}` }
  if (c.allow?.length) return { kelas: 'hijau', label: 'Whitelist' }
  if (c.terblokir_aktif) return { kelas: 'merah', label: 'Terblokir (aturan lain)' }
  return { kelas: 'abu', label: 'Tidak diblokir' }
}
// Status IP di satu server dari data ringkas (untuk tombol Lepas/Blokir di log)
function statusIp(ip, host) {
  const s = servers.value.find((x) => x.host === host)
  if (!s?.ok || !s.csf) return null
  if (s.deny.some((d) => d.ip === ip)) return 'deny'
  if (s.sementara.some((d) => d.ip === ip)) return 'sementara'
  if (s.allow.some((d) => d.ip === ip)) return 'allow'
  return null
}
function cekDariLog(ip) {
  cek(ip)
  document.getElementById('judul-cek')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
const terblokirDiMana = computed(() => (cekHasil.value?.servers || []).filter((c) => c.deny?.length || c.sementara?.length))
const namaServer = (host) => servers.value.find((s) => s.host === host)?.name || host

async function lepas(ip, host) {
  const semua = host === 'semua'
  const ya = await konfirmasi({ judul: `Lepas blokir ${ip}?`, teks: semua ? 'Blokir permanen & sementara IP ini dihapus di semua server.' : `Blokir permanen & sementara IP ini dihapus di ${namaServer(host)}.`, tombol: 'Lepas blokir' })
  if (ya) await aksi({ aksi: 'lepas', ip, server: host }, `Blokir ${ip} dilepas${semua ? ' di semua server' : ` di ${namaServer(host)}`}.`)
}
async function hapusWhitelist(ip, host) {
  const ya = await konfirmasi({ judul: `Hapus ${ip} dari whitelist?`, teks: `IP ini kembali bisa diblokir otomatis oleh LFD/cPGuard di ${host === 'semua' ? 'semua server' : namaServer(host)}.`, tombol: 'Hapus', kelas: 'bahaya' })
  if (ya) await aksi({ aksi: 'cabut_izin', ip, server: host }, `${ip} dihapus dari whitelist.`)
}

// Dialog blokir / whitelist (satu server atau semua)
const DURASI = [
  { nilai: 3600, label: '1 jam' }, { nilai: 21600, label: '6 jam' }, { nilai: 86400, label: '24 jam' },
  { nilai: 604800, label: '7 hari' }, { nilai: 2592000, label: '30 hari' }, { nilai: 0, label: 'Permanen' },
]
const dialog = reactive({ buka: false, jenis: 'blokir', ip: '', host: '', ttl: 86400, ket: '' })
function bukaDialog(jenis, ip = '', host = '') {
  Object.assign(dialog, { buka: true, jenis, ip, host: host || terpilih.value?.host || 'semua', ttl: 86400, ket: '' })
}
const judulDialog = computed(() => `${dialog.jenis === 'blokir' ? 'Blokir' : 'Whitelist'} IP`)
async function kirimDialog() {
  const di = dialog.host === 'semua' ? 'semua server' : namaServer(dialog.host)
  const body = { aksi: dialog.jenis === 'blokir' ? 'blokir' : 'izinkan', ip: dialog.ip.trim(), server: dialog.host, ket: dialog.ket }
  if (dialog.jenis === 'blokir') body.ttl = dialog.ttl
  const r = await aksi(body, dialog.jenis === 'blokir'
    ? `${body.ip} diblokir ${DURASI.find((d) => d.nilai === dialog.ttl)?.label.toLowerCase()} di ${di}.`
    : `${body.ip} masuk whitelist di ${di}.`)
  if (r) dialog.buka = false
}

// ---- Detail server ----
const SUMBER = { cpguard: 'cPGuard', lfd: 'LFD', dashboard: 'Dashboard', manual: 'Manual' }
const KELAS_SUMBER = { cpguard: 'ungu', lfd: 'biru', dashboard: 'hijau', manual: 'abu' }
const negaraDari = (ket) => (ket || '').match(/\(([A-Z]{2})\/([^/)]*)/)
const alasanRingkas = (ket) => (ket || '').replace(/^(lfd: |BFM: |velocity: )/, '').replace(/\s*\([A-Z]{2}\/[^)]*\)/, '').trim() || '-'
const cariDeny = ref('')
const sumberDeny = ref('')
const tampilSemua = ref(false)
watch(pilih, () => { cariDeny.value = ''; sumberDeny.value = ''; tampilSemua.value = false })
const denyTersaring = computed(() => {
  const s = terpilih.value
  if (!s?.deny) return []
  const q = cariDeny.value.trim().toLowerCase()
  return [...s.deny].sort((a, b) => (b.waktu || 0) - (a.waktu || 0))
    .filter((d) => (!sumberDeny.value || d.sumber === sumberDeny.value) && (!q || d.ip.includes(q) || d.ket.toLowerCase().includes(q)))
})
const hitungSumber = computed(() => {
  const out = {}
  for (const d of terpilih.value?.deny || []) out[d.sumber] = (out[d.sumber] || 0) + 1
  return out
})
const whitelist = computed(() => (terpilih.value?.allow || []).filter((a) => !a.include && !a.aturan))
const aturanLain = computed(() => (terpilih.value?.allow || []).filter((a) => a.include || a.aturan))
const cariAllow = ref('')
const allowTersaring = computed(() => {
  const q = cariAllow.value.trim().toLowerCase()
  return whitelist.value.filter((a) => !q || a.ip.includes(q) || a.ket.toLowerCase().includes(q))
})
function sisa(dtk) {
  if (dtk >= 86400) return `${Math.floor(dtk / 86400)} hari ${Math.floor((dtk % 86400) / 3600)} jam`
  if (dtk >= 3600) return `${Math.floor(dtk / 3600)} jam ${Math.floor((dtk % 3600) / 60)} mnt`
  return `${Math.max(1, Math.floor(dtk / 60))} mnt`
}
const riwayatServer = computed(() => (riwayat.data.value?.riwayat || []).filter((r) => !terpilih.value || r.host === terpilih.value.host))
const AKSI_LABEL = { blokir: ['merah', 'Blokir'], lepas: ['hijau', 'Lepas blokir'], izinkan: ['biru', 'Whitelist'], cabut_izin: ['kuning', 'Hapus whitelist'], atur: ['ungu', 'Ubah setelan'] }
const ringkasRiwayat = (r) => (r.aksi === 'atur'
  ? Object.entries(r.setelan || {}).map(([k, v]) => `${k}=${v || '""'}`).join(', ')
  : [r.ip, r.ttl ? `${DURASI.find((d) => d.nilai === r.ttl)?.label || `${r.ttl} dtk`}` : r.aksi === 'blokir' ? 'permanen' : '', r.ket].filter(Boolean).join(' · '))

// ---- Setelan CSF/LFD ----
const KELOMPOK_SETELAN = [
  { judul: 'Daftar blokir', ket: 'Bila penuh, blokir permanen terlama dihapus otomatis untuk memberi tempat yang baru.', isi: [
    { k: 'DENY_IP_LIMIT', label: 'Maks. blokir permanen', satuan: 'IP', min: 50, maks: 5000 },
    { k: 'DENY_TEMP_IP_LIMIT', label: 'Maks. blokir sementara', satuan: 'IP', min: 50, maks: 2000 },
  ] },
  { judul: 'Deteksi login gagal (LFD)', ket: 'Jumlah gagal login sebelum IP diblokir, dihitung dalam jangka di bawah. 0 = deteksi mati.', isi: [
    { k: 'LF_SSHD', label: 'SSH', satuan: 'kali', min: 0, maks: 100 },
    { k: 'LF_DIRECTADMIN', label: 'Login DirectAdmin', satuan: 'kali', min: 0, maks: 100 },
    { k: 'LF_FTPD', label: 'FTP', satuan: 'kali', min: 0, maks: 100 },
    { k: 'LF_SMTPAUTH', label: 'SMTP (kirim email)', satuan: 'kali', min: 0, maks: 100 },
    { k: 'LF_POP3D', label: 'POP3', satuan: 'kali', min: 0, maks: 100 },
    { k: 'LF_IMAPD', label: 'IMAP', satuan: 'kali', min: 0, maks: 100 },
    { k: 'LF_HTACCESS', label: 'Password .htaccess', satuan: 'kali', min: 0, maks: 100 },
    { k: 'LF_MODSEC', label: 'Pelanggaran ModSecurity', satuan: 'kali', min: 0, maks: 100 },
    { k: 'LF_INTERVAL', label: 'Jangka hitung', satuan: 'detik', min: 300, maks: 86400 },
  ] },
  { judul: 'Blokir permanen', ket: 'IP yang berkali-kali kena blokir sementara dinaikkan jadi permanen.', isi: [
    { k: 'LF_PERMBLOCK', label: 'Naikkan ke permanen', pilihan: [['1', 'Aktif'], ['0', 'Mati']] },
    { k: 'LF_PERMBLOCK_COUNT', label: 'Setelah diblokir sementara', satuan: 'kali', min: 1, maks: 20 },
    { k: 'LF_SSHD_PERM', label: 'Blokir SSH', satuan: '0/1/detik', min: 0, maks: 604800, ket: '1 = permanen, angka lain = lama blokir (detik)' },
  ] },
  { judul: 'Batas koneksi per IP', ket: 'Blokir IP yang membuka terlalu banyak koneksi sekaligus (banjir koneksi). 0 = mati.', isi: [
    { k: 'CT_LIMIT', label: 'Maks. koneksi per IP', satuan: 'koneksi', min: 0, maks: 1000, ket: 'Sarankan ≥ 300 bila dinyalakan (situs ramai/NAT kantor)' },
    { k: 'CT_INTERVAL', label: 'Diperiksa tiap', satuan: 'detik', min: 10, maks: 300 },
    { k: 'CT_BLOCK_TIME', label: 'Lama blokir', satuan: 'detik', min: 300, maks: 86400 },
  ] },
  { judul: 'Blokir negara', ket: 'Semua akses dari negara ini ditolak (web, email, FTP). Kode 2 huruf dipisah koma; ID (Indonesia) ditolak.', isi: [
    { k: 'CC_DENY', label: 'Kode negara', teks: true, placeholder: 'mis. CN,RU (kosong = tidak ada)' },
  ] },
]
const form = reactive({})
const formHost = ref('')
function isiForm() {
  const s = terpilih.value
  if (!s?.setelan) return
  for (const g of KELOMPOK_SETELAN) for (const f of g.isi) form[f.k] = s.setelan[f.k] ?? ''
  formHost.value = s.host
}
// Isi ulang hanya saat ganti server / sesudah disimpan, bukan tiap polling (ketikan tidak tertimpa)
watch(terpilih, (s) => { if (s && s.host !== formHost.value) isiForm() }, { immediate: true })
const berubah = computed(() => {
  const s = terpilih.value
  if (!s?.setelan) return {}
  const out = {}
  for (const g of KELOMPOK_SETELAN) for (const f of g.isi) {
    const v = String(form[f.k] ?? '').trim()
    if (v !== String(s.setelan[f.k] ?? '')) out[f.k] = f.teks ? v.toUpperCase().replace(/\s/g, '') : v
  }
  return out
})
async function simpanSetelan() {
  const ubah = berubah.value
  const daftar = Object.entries(ubah).map(([k, v]) => `${k}: ${terpilih.value.setelan[k] || '""'} → ${v || '""'}`).join('\n')
  const ya = await konfirmasi({ judul: `Simpan setelan firewall ${terpilih.value.name}?`, teks: `${daftar}\n\ncsf.conf disalin dulu, lalu csf -r dan restart lfd (±10–30 detik). Bila csf -r gagal, setelan lama dikembalikan otomatis.`, tombol: 'Simpan & terapkan' })
  if (!ya) return
  const r = await aksi({ aksi: 'atur', server: terpilih.value.host, setelan: ubah }, `Setelan ${terpilih.value.name} disimpan & diterapkan.`)
  if (r?.servers?.[0]?.ok) formHost.value = ''  // isi ulang dari data segar berikutnya
}
watch(() => fw.data.value, () => { if (!formHost.value) isiForm() })

let namaNegara = null
try { namaNegara = new Intl.DisplayNames(['id'], { type: 'region' }) } catch { /* peramban lama */ }
const negara = (k) => { try { return (k && namaNegara?.of(k)) || k } catch { return k } }
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Proteksi Server</h1>
        <p class="redup">Firewall CSF & deteksi brute force (LFD) di semua server hosting: blokir, lepas, whitelist IP, dan atur ambang blokir.</p>
      </div>
      <div class="kepala-aksi">
        <label class="nama-saya"><span class="redup">Nama Anda</span><input id="nama-proteksi" v-model.lazy="oleh" maxlength="40" placeholder="untuk riwayat aksi" autocomplete="name"></label>
        <button type="button" class="tombol kecil" :disabled="segarkan || (fw.memuat.value && !fw.data.value)" @click="muatSegar"><Ikon nama="ulang" :ukuran="16" /> {{ segarkan ? 'Membaca…' : 'Muat ulang' }}</button>
      </div>
    </header>

    <!-- Skeleton saat data pertama belum datang -->
    <div v-if="fw.memuat.value && !fw.data.value" class="skeleton" aria-busy="true">
      <p class="redup status-muat" role="status">Membaca firewall semua server lewat SSH (±5–15 detik)…</p>
      <div class="ringkas">
        <div v-for="i in 4" :key="i" class="kartu tile"><span class="sk sk-ikon" /><div><span class="sk sk-teks" /><span class="sk sk-angka" /><span class="sk sk-teks pendek" /></div></div>
      </div>
      <section class="kartu"><span class="sk sk-judul" /><span class="sk sk-isian" /></section>
      <div class="sk-menu"><span v-for="i in 6" :key="i" class="sk sk-pil" /></div>
      <section class="kartu">
        <span class="sk sk-judul" />
        <div v-for="i in 5" :key="i" class="sk-baris"><span v-for="j in 6" :key="j" class="sk" /></div>
      </section>
    </div>

    <p v-else-if="fw.galat.value && !fw.data.value" class="pesan-status bahaya">Gagal memuat: {{ fw.galat.value.message }}</p>
    <p v-else-if="fw.data.value?.error" class="pesan-status bahaya">Gagal memuat: {{ pesanGalat(fw.data.value.error) }}</p>

    <template v-else-if="fw.data.value">
      <div class="ringkas">
        <div class="kartu tile">
          <span class="tile-ikon merah"><Ikon nama="perisai" :ukuran="20" /></span>
          <div><span class="redup">Blokir permanen</span><b>{{ angka(total.deny) }}</b><small class="redup">{{ total.penuh }} server daftar penuh</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon kuning"><Ikon nama="jam" :ukuran="20" /></span>
          <div><span class="redup">Blokir sementara</span><b>{{ angka(total.sementara) }}</b><small class="redup">lepas otomatis saat habis</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon hijau"><Ikon nama="centang" :ukuran="20" /></span>
          <div><span class="redup">Whitelist</span><b>{{ angka(total.allow) }}</b><small class="redup">IP tidak pernah diblokir</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon ungu"><Ikon nama="server" :ukuran="20" /></span>
          <div><span class="redup">Firewall aktif</span><b>{{ total.aktif }} / {{ servers.length }}</b><small class="redup">dibaca {{ waktuLalu(fw.data.value.diambil) }}</small></div>
        </div>
      </div>

      <!-- Cek & tindak satu IP di semua server -->
      <section class="kartu" aria-labelledby="judul-cek">
        <div class="kartu-judul">
          <h2 id="judul-cek"><Ikon nama="cari" :ukuran="16" /> Cek & tindak IP
            <Info label="Tentang cek IP"><p>Mencari IP/CIDR di csf.deny, blokir sementara, whitelist, dan csf.ignore tiap server. Pakai ini saat klien atau kantor tidak bisa membuka situs/email/FTP — biasanya IP-nya terblokir LFD atau cPGuard.</p></Info>
          </h2>
          <div class="aksi-kanan">
            <button type="button" class="tombol bahaya kecil" :disabled="proses" @click="bukaDialog('blokir', cekIp, 'semua')"><Ikon nama="perisai" :ukuran="15" /> Blokir IP</button>
            <button type="button" class="tombol garis kecil" :disabled="proses" @click="bukaDialog('izinkan', cekIp, 'semua')"><Ikon nama="centang" :ukuran="15" /> Whitelist IP</button>
          </div>
        </div>
        <form class="form-cek" @submit.prevent="cek()">
          <label class="isian"><span class="sr">IP atau CIDR</span><input v-model="cekIp" inputmode="text" placeholder="IP atau CIDR, mis. 36.65.12.4 atau 36.65.0.0/16" autocomplete="off" spellcheck="false"></label>
          <button type="submit" class="tombol" :disabled="mengecek || !cekIp.trim()"><Ikon nama="cari" :ukuran="16" /> {{ mengecek ? 'Mengecek…' : 'Cek di semua server' }}</button>
        </form>

        <div v-if="cekHasil" class="hasil-cek">
          <div class="hasil-kepala">
            <p><code>{{ cekHasil.ip }}</code> — <b v-if="terblokirDiMana.length">terblokir di {{ terblokirDiMana.map((c) => c.name).join(', ') }}</b><span v-else>tidak terblokir di server mana pun</span></p>
            <button v-if="terblokirDiMana.length > 1" type="button" class="tombol kecil" :disabled="proses" @click="lepas(cekHasil.ip, 'semua')">Lepas blokir di semua server</button>
          </div>
          <div class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">Server</th><th scope="col">Status</th><th scope="col">Keterangan</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
              <tbody>
                <tr v-for="c in cekHasil.servers" :key="c.host">
                  <td><b>{{ c.name }}</b></td>
                  <td class="nowrap">
                    <span class="lencana" :class="statusCek(c).kelas">{{ statusCek(c).label }}</span>
                    <span v-if="c.ip_kantor" class="lencana biru">KANTOR</span>
                    <span v-if="c.ignore" class="lencana abu" title="Ada di csf.ignore: tidak dipantau LFD">IGNORE</span>
                  </td>
                  <td class="ket">
                    <template v-if="!c.ok">{{ pesanGalat(c.error) }}</template>
                    <template v-else>
                      <span v-for="d in [...(c.deny || []), ...(c.sementara || []), ...(c.allow || [])]" :key="d.ip + d.ket" class="blok">
                        <code v-if="d.ip !== cekHasil.ip">{{ d.ip }}</code> {{ d.ket || '-' }} <span v-if="d.waktu" class="redup">· {{ tanggalWaktu(d.waktu) }}</span>
                      </span>
                      <span v-if="!c.deny?.length && !c.sementara?.length && !c.allow?.length" class="redup">-</span>
                    </template>
                  </td>
                  <td class="kanan">
                    <template v-if="c.ok">
                      <button v-if="c.deny?.length || c.sementara?.length" type="button" class="tombol kecil" :disabled="proses" @click="lepas(cekHasil.ip, c.host)">Lepas</button>
                      <button v-else-if="c.allow?.length" type="button" class="tombol garis kecil" :disabled="proses" @click="hapusWhitelist(cekHasil.ip, c.host)">Hapus whitelist</button>
                      <button v-else-if="!c.ip_kantor" type="button" class="tombol bahaya kecil" :disabled="proses" @click="bukaDialog('blokir', cekHasil.ip, c.host)">Blokir</button>
                    </template>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>

      <nav class="sub-menu" aria-label="Pilih server">
        <button type="button" :class="{ aktif: !terpilih }" :aria-current="!terpilih ? 'page' : undefined" @click="pilih = ''"><Ikon nama="dashboard" :ukuran="16" /> Semua server</button>
        <button v-for="s in servers" :key="s.host" type="button" :class="{ aktif: terpilih === s }" :aria-current="terpilih === s ? 'page' : undefined" @click="pilih = s.name">
          <span class="titik" :class="tingkat(s)" aria-hidden="true" /> {{ s.name }}
        </button>
      </nav>

      <!-- ================= Semua server ================= -->
      <template v-if="!terpilih">
        <section class="kartu" aria-labelledby="judul-semua">
          <div class="kartu-judul"><h2 id="judul-semua"><Ikon nama="perisai" :ukuran="16" /> Firewall per server</h2><span class="redup">CSF + LFD</span></div>
          <div class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th scope="col">Server</th><th scope="col">CSF / LFD</th><th scope="col">Blokir permanen</th><th scope="col" class="kanan">Sementara</th><th scope="col" class="kanan">Whitelist</th><th scope="col">Login gagal → blokir</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
              <tbody>
                <tr v-for="s in servers" :key="s.host">
                  <td>
                    <b>{{ s.name }}</b><small class="redup blok">{{ s.host }}</small>
                    <span v-for="p in peringatan(s).filter((x) => x.tingkat !== 'info')" :key="p.teks" class="blok peringatan" :class="p.tingkat">{{ p.teks }}</span>
                  </td>
                  <template v-if="s.ok && s.csf">
                    <td class="nowrap">
                      <span class="titik" :class="s.layanan.csf === 'active' ? 'baik' : 'bahaya'" /> csf {{ s.versi }}
                      <span class="blok"><span class="titik" :class="s.layanan.lfd === 'active' ? 'baik' : 'bahaya'" /> lfd {{ s.layanan.lfd }}</span>
                    </td>
                    <td class="kolom-meter">
                      <span class="meter-teks">{{ angka(s.deny.length) }} / {{ angka(batasDeny(s)) }}</span>
                      <span class="meter" :class="{ penuh: penuh(s) }"><span :style="{ width: `${Math.min(100, (s.deny.length / (batasDeny(s) || 1)) * 100)}%` }" /></span>
                    </td>
                    <td class="kanan">{{ angka(s.sementara.length) }}</td>
                    <td class="kanan">{{ angka(s.allow.filter((a) => !a.include && !a.aturan).length) }}</td>
                    <td class="kecil-teks">SSH {{ s.setelan.LF_SSHD }} · DA {{ s.setelan.LF_DIRECTADMIN }} · SMTP {{ s.setelan.LF_SMTPAUTH }} · FTP {{ s.setelan.LF_FTPD }}<span class="redup blok">dalam {{ Math.round(Number(s.setelan.LF_INTERVAL || 0) / 60) }} menit</span></td>
                  </template>
                  <td v-else colspan="5" class="redup">{{ peringatan(s)[0]?.teks }}</td>
                  <td class="kanan"><button type="button" class="tombol garis kecil" @click="pilih = s.name">Kelola</button></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="redup kaki">Saat ini cPGuard masih berjalan paralel dan membuat sebagian besar blokir (sumber "BFM"). Blokir dari halaman ini diberi keterangan <code>velocity:</code> + nama Anda.</p>
        </section>

        <section class="kartu" aria-labelledby="judul-log">
          <div class="kartu-judul"><h2 id="judul-log"><Ikon nama="dokumen" :ukuran="16" /> Log firewall
            <Info label="Tentang log firewall"><p>Kejadian dari lfd.log tiap server (blokir brute force, login SSH, beban tinggi, relay email berlebih, file mencurigakan) digabung dengan blokir cPGuard/dashboard dari csf.deny. Klik IP untuk mengeceknya di semua server.</p></Info>
          </h2><span class="redup">semua server</span></div>
          <LogFirewall server="semua" :status="statusIp" :proses="proses" @blokir="(ip, host) => bukaDialog('blokir', ip, host)" @lepas="lepas" @cek="cekDariLog" />
        </section>

        <section class="kartu" aria-labelledby="judul-waf">
          <div class="kartu-judul"><h2 id="judul-waf"><Ikon nama="perisai" :ukuran="16" /> Log WAF
            <Info label="Tentang log WAF"><p>Request web yang diblokir ModSecurity di LiteSpeed (aturan cPGuard & Malware.Expert): bot/crawler (HTTP 429), eksploit & probe (403), dan rate limit/DDoS (406, mis. brute force xmlrpc.php). Dibaca langsung dari log LiteSpeed, jadi tetap jalan walau cPGuard dicopot.</p></Info>
          </h2><span class="redup">semua server</span></div>
          <LogWaf server="semua" :status="statusIp" :proses="proses" @blokir="(ip, host) => bukaDialog('blokir', ip, host)" @lepas="lepas" @cek="cekDariLog" />
        </section>

        <section class="kartu" aria-labelledby="judul-riwayat">
          <div class="kartu-judul"><h2 id="judul-riwayat"><Ikon nama="jam" :ukuran="16" /> Riwayat aksi</h2><span class="redup">dari halaman ini</span></div>
          <p v-if="riwayat.memuat.value && !riwayat.data.value" class="redup">Memuat…</p>
          <p v-else-if="!riwayatServer.length" class="redup">Belum ada aksi firewall dari dashboard.</p>
          <ol v-else class="kejadian">
            <li v-for="(r, i) in riwayatServer.slice(0, 30)" :key="i">
              <span class="titik" :class="r.ok ? (AKSI_LABEL[r.aksi]?.[0] || 'abu') : 'bahaya'" aria-hidden="true" />
              <div><b>{{ AKSI_LABEL[r.aksi]?.[1] || r.aksi }}</b> · {{ r.server }} · {{ ringkasRiwayat(r) }} <span class="redup">oleh {{ r.oleh }}</span> <span v-if="!r.ok" class="lencana merah">GAGAL: {{ pesanGalat(r.error) }}</span></div>
              <time class="redup" :datetime="new Date(r.t * 1000).toISOString()">{{ tanggalWaktu(r.t) }}</time>
            </li>
          </ol>
        </section>
      </template>

      <!-- ================= Detail satu server ================= -->
      <template v-else>
        <section v-if="!terpilih.ok || !terpilih.csf" class="kartu">
          <p class="pesan-status bahaya">{{ peringatan(terpilih)[0]?.teks }}</p>
        </section>
        <template v-else>
          <ul v-if="peringatan(terpilih).length" class="daftar-peringatan">
            <li v-for="p in peringatan(terpilih)" :key="p.teks" :class="p.tingkat"><span class="titik" :class="p.tingkat" aria-hidden="true" /> {{ p.teks }}</li>
          </ul>

          <section class="kartu" aria-labelledby="judul-detail">
            <div class="kartu-judul">
              <h2 id="judul-detail"><Ikon nama="perisai" :ukuran="16" /> {{ terpilih.name }} <small class="redup">csf {{ terpilih.versi }} · IP kantor terdeteksi {{ terpilih.ip_kantor || '-' }}</small></h2>
              <div class="tab" role="tablist" aria-label="Bagian firewall">
                <button v-for="t in [
                  { k: 'blokir', label: 'Diblokir', n: terpilih.deny.length },
                  { k: 'sementara', label: 'Sementara', n: terpilih.sementara.length },
                  { k: 'whitelist', label: 'Whitelist', n: whitelist.length },
                  { k: 'log', label: 'Log' },
                  { k: 'waf', label: 'WAF' },
                  { k: 'setelan', label: 'Setelan' },
                  { k: 'riwayat', label: 'Riwayat', n: riwayatServer.length },
                ]" :key="t.k" type="button" role="tab" :aria-selected="tab === t.k" :class="{ aktif: tab === t.k }" @click="tab = t.k">
                  {{ t.label }} <span v-if="t.n !== undefined" class="hitung">{{ t.n }}</span>
                </button>
              </div>
            </div>

            <!-- Diblokir permanen -->
            <template v-if="tab === 'blokir'">
              <div class="alat">
                <input v-model="cariDeny" type="search" placeholder="Cari IP / alasan" aria-label="Cari blokir">
                <div class="chip-filter" role="group" aria-label="Sumber blokir">
                  <button type="button" :class="{ aktif: !sumberDeny }" @click="sumberDeny = ''">Semua {{ terpilih.deny.length }}</button>
                  <button v-for="(n, k) in hitungSumber" :key="k" type="button" :class="{ aktif: sumberDeny === k }" @click="sumberDeny = k">{{ SUMBER[k] || k }} {{ n }}</button>
                </div>
                <button type="button" class="tombol bahaya kecil" :disabled="proses" @click="bukaDialog('blokir', '', terpilih.host)"><Ikon nama="tambah" :ukuran="15" /> Blokir IP</button>
              </div>
              <p v-if="!denyTersaring.length" class="redup">Tidak ada blokir yang cocok.</p>
              <div v-else class="tabel-wadah">
                <table class="tabel">
                  <thead><tr><th scope="col">IP</th><th scope="col">Sumber</th><th scope="col">Alasan</th><th scope="col">Sejak</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                  <tbody>
                    <tr v-for="d in (tampilSemua ? denyTersaring : denyTersaring.slice(0, 50))" :key="d.ip">
                      <td class="nowrap"><span v-if="negaraDari(d.ket)" class="kode-negara" :title="negara(negaraDari(d.ket)[1])">{{ negaraDari(d.ket)[1] }}</span> <code>{{ d.ip }}</code></td>
                      <td><span class="lencana" :class="KELAS_SUMBER[d.sumber]">{{ SUMBER[d.sumber] || d.sumber }}</span></td>
                      <td class="ket">{{ alasanRingkas(d.ket) }}</td>
                      <td class="nowrap">{{ d.waktu ? tanggalWaktu(d.waktu) : '-' }}</td>
                      <td class="kanan"><button type="button" class="tombol garis kecil" :disabled="proses" @click="lepas(d.ip, terpilih.host)">Lepas</button></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <button v-if="!tampilSemua && denyTersaring.length > 50" type="button" class="tombol garis kecil lagi" @click="tampilSemua = true">Tampilkan semua {{ denyTersaring.length }}</button>
            </template>

            <!-- Blokir sementara -->
            <template v-else-if="tab === 'sementara'">
              <div class="alat"><span class="redup">Blokir sementara lepas sendiri saat waktunya habis.</span>
                <button type="button" class="tombol bahaya kecil" :disabled="proses" @click="bukaDialog('blokir', '', terpilih.host)"><Ikon nama="tambah" :ukuran="15" /> Blokir IP</button>
              </div>
              <p v-if="!terpilih.sementara.length" class="redup">Tidak ada blokir sementara.</p>
              <div v-else class="tabel-wadah">
                <table class="tabel">
                  <thead><tr><th scope="col">IP</th><th scope="col">Port / arah</th><th scope="col">Alasan</th><th scope="col">Sisa</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                  <tbody>
                    <tr v-for="d in terpilih.sementara" :key="d.ip + d.port">
                      <td class="nowrap"><code>{{ d.ip }}</code></td>
                      <td class="nowrap">{{ d.port }} · {{ d.arah }}</td>
                      <td class="ket">{{ alasanRingkas(d.ket) }}</td>
                      <td class="nowrap">{{ sisa(d.sisa) }}</td>
                      <td class="kanan"><button type="button" class="tombol garis kecil" :disabled="proses" @click="lepas(d.ip, terpilih.host)">Lepas</button></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>

            <!-- Whitelist -->
            <template v-else-if="tab === 'whitelist'">
              <div class="alat">
                <input v-model="cariAllow" type="search" placeholder="Cari IP / keterangan" aria-label="Cari whitelist">
                <button type="button" class="tombol kecil" :disabled="proses" @click="bukaDialog('izinkan', '', terpilih.host)"><Ikon nama="tambah" :ukuran="15" /> Tambah whitelist</button>
              </div>
              <p v-if="!allowTersaring.length" class="redup">Tidak ada whitelist yang cocok.</p>
              <div v-else class="tabel-wadah">
                <table class="tabel">
                  <thead><tr><th scope="col">IP</th><th scope="col">Keterangan</th><th scope="col">Ditambahkan</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
                  <tbody>
                    <tr v-for="a in allowTersaring" :key="a.ip">
                      <td class="nowrap"><code>{{ a.ip }}</code> <span v-if="a.ip === terpilih.ip_kantor" class="lencana biru">KANTOR</span></td>
                      <td class="ket">{{ a.ket.replace(/^#\s*/, '') || '-' }}</td>
                      <td class="nowrap">{{ a.waktu ? tanggalWaktu(a.waktu) : '-' }}</td>
                      <td class="kanan"><button v-if="a.ip !== terpilih.ip_kantor" type="button" class="tombol garis kecil" :disabled="proses" @click="hapusWhitelist(a.ip, terpilih.host)">Hapus</button></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-if="aturanLain.length" class="redup kaki">
                Juga di csf.allow (tidak diubah dari sini):
                <template v-for="(a, i) in aturanLain" :key="a.ip"><code>{{ a.ip }}</code><template v-if="a.include"> ({{ a.isi }} IP)</template><template v-if="i < aturanLain.length - 1">, </template></template>.
              </p>
            </template>

            <!-- Log firewall server ini -->
            <LogFirewall v-else-if="tab === 'log'" :server="terpilih.host" :status="statusIp" :proses="proses"
              @blokir="(ip, host) => bukaDialog('blokir', ip, host)" @lepas="lepas" @cek="cekDariLog" />

            <LogWaf v-else-if="tab === 'waf'" :server="terpilih.host" :status="statusIp" :proses="proses"
              @blokir="(ip, host) => bukaDialog('blokir', ip, host)" @lepas="lepas" @cek="cekDariLog" />

            <!-- Setelan -->
            <form v-else-if="tab === 'setelan'" class="setelan" @submit.prevent="simpanSetelan">
              <fieldset v-for="g in KELOMPOK_SETELAN" :key="g.judul">
                <legend>{{ g.judul }}</legend>
                <p class="redup">{{ g.ket }}</p>
                <div class="isian-grid">
                  <label v-for="f in g.isi" :key="f.k" class="isian" :class="{ diubah: f.k in berubah, lebar: f.teks }">
                    <span>{{ f.label }}</span>
                    <select v-if="f.pilihan" v-model="form[f.k]"><option v-for="[v, l] in f.pilihan" :key="v" :value="v">{{ l }}</option></select>
                    <input v-else-if="f.teks" v-model="form[f.k]" :placeholder="f.placeholder" pattern="^([A-Za-z]{2}(\s*,\s*[A-Za-z]{2})*)?$" autocomplete="off" spellcheck="false">
                    <input v-else v-model="form[f.k]" type="number" :min="f.min" :max="f.maks" step="1" required>
                    <small>{{ f.k }}<template v-if="f.satuan"> · {{ f.satuan }}</template><template v-if="f.min !== undefined"> ({{ f.min }}–{{ angka(f.maks) }})</template><template v-if="f.ket"> · {{ f.ket }}</template></small>
                  </label>
                </div>
              </fieldset>
              <div class="simpan-baris">
                <button type="submit" class="tombol" :disabled="proses || !Object.keys(berubah).length">{{ proses ? 'Menerapkan…' : `Simpan & terapkan${Object.keys(berubah).length ? ` (${Object.keys(berubah).length})` : ''}` }}</button>
                <button v-if="Object.keys(berubah).length" type="button" class="tombol garis" :disabled="proses" @click="isiForm">Batal</button>
                <span class="redup">Hanya untuk {{ terpilih.name }}. csf.conf disalin dulu (csf.conf.velocity-&lt;waktu&gt;).</span>
              </div>
            </form>

            <!-- Riwayat server ini -->
            <template v-else>
              <p v-if="!riwayatServer.length" class="redup">Belum ada aksi firewall dari dashboard untuk server ini.</p>
              <ol v-else class="kejadian">
                <li v-for="(r, i) in riwayatServer.slice(0, 50)" :key="i">
                  <span class="titik" :class="r.ok ? (AKSI_LABEL[r.aksi]?.[0] || 'abu') : 'bahaya'" aria-hidden="true" />
                  <div><b>{{ AKSI_LABEL[r.aksi]?.[1] || r.aksi }}</b> · {{ ringkasRiwayat(r) }} <span class="redup">oleh {{ r.oleh }}</span> <span v-if="!r.ok" class="lencana merah">GAGAL: {{ pesanGalat(r.error) }}</span></div>
                  <time class="redup" :datetime="new Date(r.t * 1000).toISOString()">{{ tanggalWaktu(r.t) }}</time>
                </li>
              </ol>
            </template>
          </section>
        </template>
      </template>
    </template>

    <Dialog :buka="dialog.buka" :judul="judulDialog" @tutup="dialog.buka = false">
      <form class="form-dialog" @submit.prevent="kirimDialog">
        <label class="isian"><span>IP atau CIDR</span><input v-model="dialog.ip" required autofocus placeholder="mis. 185.65.135.185" autocomplete="off" spellcheck="false"></label>
        <label class="isian"><span>Server</span>
          <select v-model="dialog.host">
            <option value="semua">Semua server ({{ servers.length }})</option>
            <option v-for="s in servers" :key="s.host" :value="s.host">{{ s.name }}</option>
          </select>
        </label>
        <div v-if="dialog.jenis === 'blokir'" class="isian">
          <span>Durasi</span>
          <div class="pil-durasi" role="radiogroup" aria-label="Durasi blokir">
            <label v-for="d in DURASI" :key="d.nilai" :class="{ aktif: dialog.ttl === d.nilai }"><input v-model="dialog.ttl" type="radio" :value="d.nilai" class="sr"> {{ d.label }}</label>
          </div>
          <small v-if="dialog.ttl === 0">Permanen masuk csf.deny (maks. {{ terpilih ? batasDeny(terpilih) : 200 }} IP; bila penuh, yang terlama terhapus). Untuk penyerang sesaat, blokir sementara lebih awet.</small>
        </div>
        <label class="isian"><span>{{ dialog.jenis === 'blokir' ? 'Alasan' : 'Keterangan' }}</span><input v-model="dialog.ket" maxlength="120" :placeholder="dialog.jenis === 'blokir' ? 'mis. brute force wp-login klien X' : 'mis. IP kantor klien X / server backup'"></label>
        <p v-if="dialog.jenis === 'izinkan'" class="redup">IP whitelist tidak pernah diblokir LFD maupun cPGuard di server itu — pakai hanya untuk IP tepercaya.</p>
        <p v-if="!oleh.trim()" class="pesan-status bahaya">Isi "Nama Anda" di kanan atas dulu.</p>
        <div class="dialog-aksi">
          <button type="button" class="tombol garis" @click="dialog.buka = false">Batal</button>
          <button type="submit" class="tombol" :class="{ bahaya: dialog.jenis === 'blokir' }" :disabled="proses || !dialog.ip.trim() || !oleh.trim()">{{ proses ? 'Menerapkan…' : dialog.jenis === 'blokir' ? 'Blokir' : 'Tambah ke whitelist' }}</button>
        </div>
      </form>
    </Dialog>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.kepala-aksi { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.nama-saya { display: grid; gap: 4px; font-size: 12px; }
.nama-saya input { min-width: 190px; }
.ringkas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.kartu-judul { flex-wrap: wrap; gap: 10px; }
.kartu-judul h2 { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.kartu-judul h2 small { font-size: 12.5px; font-weight: 400; }
.aksi-kanan { display: flex; gap: 8px; flex-wrap: wrap; }
.tile { display: flex; gap: 14px; align-items: center; }
.tile > div { display: grid; gap: 3px; min-width: 0; }
.tile b { font-size: 24px; color: var(--teks-kuat); }
.tile small { font-size: 12px; }
.tile-ikon { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; }
.tile-ikon.merah { color: var(--bahaya); background: color-mix(in srgb, var(--bahaya) 15%, transparent); }
.tile-ikon.kuning { color: var(--waspada); background: color-mix(in srgb, var(--waspada) 15%, transparent); }
.tile-ikon.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 15%, transparent); }
.tile-ikon.hijau { color: var(--baik); background: color-mix(in srgb, var(--baik) 15%, transparent); }
.form-cek { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; align-items: end; }
.form-cek .tombol { min-height: 42px; }
.hasil-cek { margin-top: 14px; display: grid; gap: 8px; }
.hasil-kepala { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.hasil-kepala p { margin: 0; font-size: 14px; }
.sub-menu { display: flex; gap: 4px; padding: 4px; border-radius: 12px; background: var(--kartu); border: 1px solid var(--garis); overflow-x: auto; }
.sub-menu button { display: inline-flex; align-items: center; gap: 7px; flex: none; border: 0; background: transparent; color: var(--teks-2);
  font: inherit; font-size: 13.5px; font-weight: 600; padding: 9px 14px; border-radius: 9px; cursor: pointer; }
.sub-menu button:hover { color: var(--teks-kuat); background: var(--sorot); }
.sub-menu button.aktif { background: var(--aksen); color: #fff; }
.titik { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--teks-3); vertical-align: 1px; }
.titik.baik, .titik.hijau { background: var(--baik); }
.titik.waspada, .titik.kuning { background: var(--waspada); }
.titik.bahaya, .titik.merah { background: var(--bahaya); }
.titik.biru { background: var(--aksen-terang); }
.titik.ungu { background: var(--ungu); }
.lencana.ungu { color: var(--ungu); background: color-mix(in srgb, var(--ungu) 14%, transparent); }
.lencana + .lencana { margin-left: 4px; }
.peringatan { font-size: 12px; margin-top: 3px; }
.peringatan.bahaya { color: var(--bahaya); }
.peringatan.waspada { color: var(--waspada); }
.kolom-meter { min-width: 130px; }
.meter-teks { display: block; font-size: 13px; margin-bottom: 5px; }
.meter { display: block; height: 6px; border-radius: 99px; background: var(--kartu-2); overflow: hidden; }
.meter span { display: block; height: 100%; border-radius: 99px; background: var(--aksen-terang); }
.meter.penuh span { background: var(--waspada); }
.kecil-teks { font-size: 13px; }
.daftar-peringatan { list-style: none; margin: 0; padding: 12px 16px; display: grid; gap: 6px; border-radius: 12px; background: var(--kartu); border: 1px solid var(--garis); font-size: 13.5px; }
.daftar-peringatan li { display: flex; gap: 10px; align-items: center; }
.daftar-peringatan li.bahaya { color: var(--bahaya); }
.tab { display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--kartu-2); flex-wrap: wrap; }
.tab button { border: 0; background: transparent; color: var(--teks-2); font: inherit; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab button.aktif { background: var(--aksen); color: #fff; }
.tab .hitung { opacity: .7; margin-left: 2px; }
.alat { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
.alat input[type="search"] { flex: 1 1 220px; min-width: 0; }
.alat .tombol { margin-left: auto; }
.chip-filter { display: flex; gap: 4px; flex-wrap: wrap; }
.chip-filter button { border: 1px solid var(--garis); background: transparent; color: var(--teks-2); font: inherit; font-size: 12.5px; font-weight: 600; padding: 5px 10px; border-radius: 999px; cursor: pointer; }
.chip-filter button.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); color: var(--aksen-terang); }
.ket { font-size: 13px; color: var(--teks-2); overflow-wrap: anywhere; min-width: 180px; }
.blok { display: block; }
.lagi { margin-top: 10px; }
.kode-negara { display: inline-block; min-width: 26px; padding: 1px 5px; border-radius: 4px; font-size: 11px; font-weight: 700; text-align: center; color: var(--teks-2); background: var(--kartu-2); border: 1px solid var(--garis); }
.kejadian { list-style: none; margin: 0; padding: 0; display: grid; }
.kejadian li { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 2px; border-bottom: 1px solid var(--garis); font-size: 13.5px; }
.kejadian li:last-child { border-bottom: 0; }
.kejadian li > div { overflow-wrap: anywhere; }
.kejadian time { font-size: 12.5px; white-space: nowrap; }
.setelan { display: grid; gap: 18px; }
.setelan fieldset { margin: 0; padding: 14px 16px 16px; border: 1px solid var(--garis); border-radius: 12px; min-width: 0; }
.setelan legend { padding: 0 6px; font-weight: 700; font-size: 14px; color: var(--teks-kuat); }
.setelan fieldset > p { margin: 0 0 12px; font-size: 13px; }
.isian-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(200px, 100%), 1fr)); gap: 12px 14px; align-items: start; }
.isian.lebar { grid-column: 1 / -1; max-width: 420px; }
.isian small { overflow-wrap: anywhere; }
.isian.diubah input, .isian.diubah select { border-color: var(--waspada); box-shadow: 0 0 0 1px var(--waspada); }
.simpan-baris { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; font-size: 13px; }
.form-dialog { display: grid; gap: 14px; }
.form-dialog p { margin: 0; font-size: 13px; }
.pil-durasi { display: flex; flex-wrap: wrap; gap: 6px; }
.pil-durasi label { border: 1px solid var(--garis); border-radius: 9px; padding: 7px 12px; font-size: 13px; cursor: pointer; color: var(--teks-2); }
.pil-durasi label.aktif { background: var(--aksen-lembut); border-color: var(--aksen-terang); color: var(--aksen-terang); font-weight: 600; }
.pil-durasi label:focus-within { outline: 2px solid var(--aksen-terang); outline-offset: 2px; }
.dialog-aksi { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.nowrap { white-space: nowrap; }
.kanan { text-align: right; white-space: nowrap; }
.kaki { margin: 12px 0 0; font-size: 13px; }
.tabel-wadah { position: relative; overflow-x: auto; }
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
.sk-isian { height: 42px; border-radius: 10px; }
.sk-menu { display: flex; gap: 8px; padding: 8px; border-radius: 12px; background: var(--kartu); border: 1px solid var(--garis); overflow: hidden; }
.sk-pil { flex: none; height: 30px; width: 96px; border-radius: 9px; }
.sk-judul { height: 14px; width: 200px; max-width: 60%; margin-bottom: 18px; }
.sk-baris { display: grid; grid-template-columns: 1.2fr 1fr 1.4fr .6fr .6fr 1.6fr; gap: 16px; padding: 14px 0; border-top: 1px solid var(--garis); }
.sk-baris .sk { height: 12px; }
@keyframes sk-kilau { from { background-position: 100% 0; } to { background-position: -100% 0; } }
@media (prefers-reduced-motion: reduce) { .sk { animation: none; } }
@media (max-width: 900px) {
  .ringkas { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 560px) {
  .ringkas { grid-template-columns: 1fr; }
  .form-cek { grid-template-columns: 1fr; }
  .nama-saya, .nama-saya input { width: 100%; }
  .kepala-aksi { width: 100%; }
  .sk-baris { grid-template-columns: 1fr 1fr 1fr; }
  .kejadian li { grid-template-columns: 8px minmax(0, 1fr); }
  .kejadian time { grid-column: 2; }
  .alat .tombol { margin-left: 0; }
}
</style>
