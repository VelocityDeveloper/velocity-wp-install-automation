<script setup>
// Pantauan Realtime (VelocityGuard): antrean email, spam, percobaan peretasan, DDoS, dan kesehatan sistem semua server
// dalam satu panel. Data: GET /api/servers/pantau (services/server_pantau.py; agen scripts/server_pantau_agent.py
// diperiksa tiap 30 dtk, jendela bergulir 5 menit). Tindakan terukur: POST /api/servers/pantau/aksi {server, id}
// — hanya usulan yang masih berlaku di snapshot terakhir; nilai metrik sebelum & sesudah dicatat di riwayat.
import { ref, computed, reactive } from 'vue'
import Ikon from '../components/Ikon.vue'
import PelakuAkun from '../components/PelakuAkun.vue'
import { namaAkun } from '../akun.js'
import { konfirmasi } from '../konfirmasi.js'
import { kirim, pakaiPolling, waktuLalu } from '../api.js'

const pan = pakaiPolling('/api/servers/pantau', 10000)
const d = computed(() => pan.data.value || {})
const servers = computed(() => d.value.server || [])
const KAT = [
  { k: 'email', label: 'Antrean Email', ikon: 'email' },
  { k: 'spam', label: 'Spam', ikon: 'peringatan' },
  { k: 'retas', label: 'Percobaan Peretasan', ikon: 'kunci' },
  { k: 'ddos', label: 'DDoS & Koneksi', ikon: 'waf' },
  { k: 'sistem', label: 'Sistem', ikon: 'server' },
]
const WARNA = { normal: 'hijau', waspada: 'kuning', bahaya: 'merah' }
const LABEL = { normal: 'Normal', waspada: 'Waspada', bahaya: 'Bahaya' }
const nilaiRapi = (v) => (typeof v === 'number' ? Number(v.toFixed(1)).toLocaleString('id-ID') : v)
const judulRapi = (t) => String(t).replace(/(\d+)\.0(?=%|\s|$)/g, '$1')
const AKSI = {
  blokir_ip: 'Blokir IP 1 jam', hapus_frozen: 'Hapus email frozen', tahan_pengirim: 'Bekukan antrean pengirim',
  lepas_pengirim: 'Lepas antrean pengirim', jalankan_antrean: 'Proses antrean',
}
const PESAN = {
  invalid_oleh: 'Masuk dulu lewat tombol "Masuk dengan VD.net" — setiap tindakan dicatat atas nama akun Anda.',
  login_diperlukan: 'Sesi login habis. Klik "Masuk dengan VD.net" di kanan atas.',
  usulan_kedaluwarsa: 'Kondisi sudah berubah — usulan ini tidak berlaku lagi di pemeriksaan terakhir.',
  ip_dilindungi: 'IP ini dilindungi (kantor, Cloudflare, atau crawler resmi).',
  ip_kantor: 'IP kantor tidak boleh diblokir.', ada_di_whitelist: 'IP ada di whitelist server.',
  salin_cadangan_gagal: 'Salinan cadangan gagal dibuat — tidak ada email yang dihapus.',
  forbidden: 'Ditolak: hanya bisa dijalankan dari halaman dashboard ini.', timeout: 'Server tidak menjawab (timeout).',
}
const pesan = reactive({ teks: '', galat: false })
const lapor = (teks, galat = false) => Object.assign(pesan, { teks, galat })
const angka = (n) => (n == null ? '—' : Number(n).toLocaleString('id-ID'))

const jumlah = (f) => servers.value.reduce((a, s) => a + (s.ok ? (f(s.data) || 0) : 0), 0)
const ubin = computed(() => ({
  email: { utama: jumlah((x) => x.email?.antrean?.total), sat: 'pesan di antrean', ket: `${angka(jumlah((x) => x.email?.antrean?.frozen))} frozen · ${angka(jumlah((x) => x.email?.log?.terkirim))} terkirim / 5 mnt` },
  spam: { utama: jumlah((x) => (x.email?.log?.spam_ditolak || 0) + (x.email?.log?.rbl_ditolak || 0)), sat: 'spam/RBL ditolak / 5 mnt', ket: `${angka(jumlah((x) => x.email?.log?.dilarang_kirim))} kiriman akun ditahan` },
  retas: { utama: jumlah((x) => x.retas?.lfd?.blokir), sat: 'IP diblokir LFD / 5 mnt', ket: `${angka(jumlah((x) => x.retas?.waf?.tolak))} ditolak WAF · ${angka(jumlah((x) => x.email?.log?.auth_gagal))} login email gagal` },
  ddos: { utama: jumlah((x) => x.ddos?.syn_recv), sat: 'koneksi SYN_RECV', ket: `${angka(jumlah((x) => x.ddos?.web))} koneksi web aktif` },
  sistem: { utama: servers.value.filter((s) => s.ok && s.status?.sistem !== 'normal').length, sat: 'server perlu perhatian', ket: `${servers.value.filter((s) => !s.ok).length} server tak terjangkau` },
}))
const statusKat = (k) => {
  const t = servers.value.map((s) => (s.ok ? s.status?.[k] : 'waspada'))
  return t.includes('bahaya') ? 'bahaya' : t.includes('waspada') ? 'waspada' : 'normal'
}
const usulan = computed(() => servers.value.flatMap((s) => (s.usulan || []).map((u) => ({ ...u, server: s.name, host: s.host })))
  .sort((a, b) => (b.tingkat === 'bahaya') - (a.tingkat === 'bahaya')))
const sinyal = computed(() => servers.value.flatMap((s) => (s.sinyal || []).map((x) => ({ ...x, server: s.name })))
  .sort((a, b) => (b.tingkat === 'bahaya') - (a.tingkat === 'bahaya')))

const pilih = ref('')
const srv = computed(() => servers.value.find((s) => s.host === pilih.value) || null)
const baru = computed(() => (d.value.t ? Math.max(...servers.value.map((s) => s.data?.t || 0)) : 0))
const sedang = reactive({})

async function jalankan(u) {
  const ok = await konfirmasi({
    judul: `${AKSI[u.aksi]} · ${u.server}`,
    teks: `${u.target !== 'semua' ? `Target: ${u.target}\n` : ''}Dampak: ${u.dampak}\nAlasan: ${u.alasan}\n\nNilai "${u.ukur.satuan}" dicatat sekarang dan diukur ulang otomatis sesudahnya.`,
    tombol: AKSI[u.aksi], kelas: u.tingkat === 'bahaya' ? 'bahaya' : '',
  })
  if (!ok) return
  sedang[u.host + u.id] = true
  try {
    await kirim('/api/servers/pantau/aksi', { server: u.host, id: u.id, oleh: namaAkun.value })
    lapor(`${AKSI[u.aksi]} di ${u.server} berhasil — efeknya muncul di Riwayat tindakan setelah pemeriksaan berikutnya.`)
    pan.muatUlang()
  } catch (e) { lapor(PESAN[e.message] || e.message, true) } finally { sedang[u.host + u.id] = false }
}
async function lepas(t) {
  if (!await konfirmasi({ judul: 'Lepas antrean pengirim?', teks: `${t.target} di ${t.server} — pesan yang dibekukan akan dikirim lagi.`, tombol: 'Lepas' })) return
  try { await kirim('/api/servers/pantau/lepas', { server: t.host, pengirim: t.target, oleh: namaAkun.value }); lapor('Antrean dilepas.'); pan.muatUlang() }
  catch (e) { lapor(PESAN[e.message] || e.message, true) }
}
async function periksaSekarang() {
  try { await kirim('/api/servers/pantau/aksi', { server: servers.value[0]?.host, aksi: 'periksa', oleh: namaAkun.value }); lapor('Pemeriksaan dimulai, data diperbarui dalam ±10 detik.') }
  catch (e) { lapor(PESAN[e.message] || e.message, true) }
}

// Garis tren 1 jam dari titik [t, antrean, frozen, auth_gagal, spam, lfd, waf, syn_recv, web, load]
function garis(titik, kol) {
  const i = (d.value.kolom_titik || []).indexOf(kol)
  const v = (titik || []).map((x) => x[i]).filter((x) => x != null)
  if (v.length < 2) return ''
  const maks = Math.max(...v, 1)
  return v.map((x, j) => `${((j / (v.length - 1)) * 100).toFixed(1)},${(28 - (x / maks) * 26).toFixed(1)}`).join(' ')
}
const TREN = [
  { kol: 'antrean', label: 'Antrean email' }, { kol: 'spam', label: 'Spam ditolak' }, { kol: 'auth_gagal', label: 'Login email gagal' },
  { kol: 'lfd', label: 'Blokir LFD' }, { kol: 'waf', label: 'Tolak WAF' }, { kol: 'syn_recv', label: 'SYN_RECV' },
  { kol: 'web', label: 'Koneksi web' }, { kol: 'load', label: 'Load' },
]
const akhir = (titik, kol) => { const i = (d.value.kolom_titik || []).indexOf(kol); return titik?.length ? titik[titik.length - 1][i] : null }
const selisih = (t) => (t.sebelum == null || t.sesudah == null ? null : t.sesudah - t.sebelum)
const jam = (t) => (t ? new Date(t * 1000).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) : '')
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Pantauan Realtime</h1>
        <p class="redup">Antrean email, spam, percobaan peretasan, DDoS, dan kesehatan sistem semua server dalam satu panel. Diperiksa tiap {{ d.interval || 30 }} dtk, angka = jendela {{ (d.jendela || 300) / 60 }} menit terakhir. Tindakan tidak otomatis: setiap tombol menyebut dampaknya dan efeknya diukur ulang.</p>
      </div>
      <div class="kepala-aksi">
        <span class="langsung" :class="{ basi: baru && Date.now() / 1000 - baru > 120 }"><i></i>{{ baru ? `diperbarui ${waktuLalu(baru)}` : 'menunggu data…' }}</span>
        <button type="button" class="tombol kecil garis" @click="periksaSekarang"><Ikon nama="ulang" :ukuran="16" /> Periksa sekarang</button>
        <div class="nama-saya"><span class="redup">Dicatat sebagai</span><PelakuAkun id="nama-pantau" /></div>
      </div>
    </header>
    <p v-if="pesan.teks" class="pesan-status" :class="pesan.galat ? 'bahaya' : 'baik'" role="status">{{ pesan.teks }}</p>
    <p v-if="pan.memuat.value && !servers.length" class="redup">Memuat…</p>
    <p v-else-if="!servers.length" class="redup">Belum ada data — pemeriksaan pertama berjalan sesudah layanan dashboard dimulai (±30 dtk).</p>

    <template v-else>
      <!-- Ubin ringkasan per kategori -->
      <div class="ubin-baris">
        <div v-for="k in KAT" :key="k.k" class="ubin" :class="statusKat(k.k)">
          <div class="ubin-kepala"><Ikon :nama="k.ikon" :ukuran="16" /> {{ k.label }} <span class="lencana" :class="WARNA[statusKat(k.k)]">{{ LABEL[statusKat(k.k)] }}</span></div>
          <b class="ubin-angka">{{ angka(ubin[k.k].utama) }}</b>
          <span class="redup">{{ ubin[k.k].sat }}</span>
          <small class="redup blok">{{ ubin[k.k].ket }}</small>
        </div>
      </div>

      <div class="dua-kolom">
        <!-- Tindakan terukur -->
        <section class="kartu" aria-labelledby="judul-usulan">
          <div class="kartu-judul"><h2 id="judul-usulan"><Ikon nama="perisai" :ukuran="16" /> Tindakan terukur <span v-if="usulan.length" class="hitung">{{ usulan.length }}</span></h2></div>
          <p v-if="!usulan.length" class="bersih"><Ikon nama="centang" :ukuran="16" /> Tidak ada tindakan yang perlu diambil sekarang.</p>
          <ul class="daftar">
            <li v-for="u in usulan" :key="u.host + u.id" class="usulan" :class="u.tingkat">
              <div class="usulan-isi">
                <div class="baris-atas">
                  <span class="lencana" :class="WARNA[u.tingkat]">{{ LABEL[u.tingkat] }}</span>
                  <b>{{ u.server }}</b>
                  <span class="redup">·</span>
                  <span>{{ AKSI[u.aksi] }}</span>
                  <code v-if="u.aksi !== 'hapus_frozen' && u.target !== 'semua'" class="putus target">{{ u.target }}</code>
                </div>
                <p class="redup kecil-teks">{{ u.alasan }}</p>
                <p class="dampak"><Ikon nama="peringatan" :ukuran="14" /> <span>{{ u.dampak }}</span></p>
              </div>
              <button type="button" class="tombol kecil" :class="u.tingkat === 'bahaya' ? 'bahaya' : 'waspada'" :disabled="sedang[u.host + u.id]" @click="jalankan(u)">
                {{ sedang[u.host + u.id] ? 'Menjalankan…' : 'Jalankan' }}</button>
            </li>
          </ul>
        </section>

        <!-- Sinyal -->
        <section class="kartu" aria-labelledby="judul-sinyal">
          <div class="kartu-judul"><h2 id="judul-sinyal"><Ikon nama="peringatan" :ukuran="16" /> Sinyal aktif <span v-if="sinyal.length" class="hitung">{{ sinyal.length }}</span></h2></div>
          <p v-if="!sinyal.length" class="bersih"><Ikon nama="centang" :ukuran="16" /> Semua metrik di bawah ambang.</p>
          <ul class="sinyal">
            <li v-for="(x, i) in sinyal" :key="i">
              <span class="lencana" :class="WARNA[x.tingkat]">{{ LABEL[x.tingkat] }}</span>
              <b>{{ x.server }}</b>
              <span class="sinyal-judul">{{ judulRapi(x.judul) }}<small v-if="Array.isArray(x.ambang)" class="redup"> · ambang {{ x.ambang.map(nilaiRapi).join(' / ') }}</small></span>
              <span class="kat redup"><Ikon :nama="KAT.find((k) => k.k === x.kat)?.ikon" :ukuran="13" /> {{ KAT.find((k) => k.k === x.kat)?.label }}</span>
            </li>
          </ul>
        </section>
      </div>

      <!-- Matriks server -->
      <section class="kartu" aria-labelledby="judul-matriks">
        <div class="kartu-judul"><h2 id="judul-matriks"><Ikon nama="server" :ukuran="16" /> Semua server</h2><span class="redup kecil-teks">Klik baris untuk rincian &amp; tren 1 jam</span></div>
        <div class="tabel-wadah">
          <table class="tabel matriks">
            <thead><tr><th scope="col">Server</th><th scope="col">Antrean</th><th scope="col">Spam</th><th scope="col">Peretasan</th><th scope="col">DDoS</th><th scope="col">Sistem</th></tr></thead>
            <tbody>
              <tr v-for="s in servers" :key="s.host" class="bisa-klik" :class="{ terpilih: pilih === s.host }" tabindex="0"
                  @click="pilih = pilih === s.host ? '' : s.host" @keydown.enter="pilih = pilih === s.host ? '' : s.host">
                <td><b>{{ s.name }}</b><span class="kecil">{{ s.ok ? waktuLalu(s.data.t) : `gagal: ${s.error}` }}</span></td>
                <template v-if="s.ok">
                  <td><span class="titik" :class="WARNA[s.status.email]"></span><template v-if="s.data.email?.antrean?.ada">{{ angka(s.data.email.antrean.total) }} pesan</template><span v-else class="redup">tanpa email</span><span class="kecil">{{ s.data.email?.antrean?.ada ? `${angka(s.data.email.antrean.frozen)} frozen` : '' }}</span></td>
                  <td><span class="titik" :class="WARNA[s.status.spam]"></span>{{ angka((s.data.email?.log?.spam_ditolak || 0) + (s.data.email?.log?.rbl_ditolak || 0)) }} ditolak<span class="kecil">{{ angka(s.data.email?.log?.dilarang_kirim || 0) }} kiriman ditahan</span></td>
                  <td><span class="titik" :class="WARNA[s.status.retas]"></span>{{ angka(s.data.retas.lfd.blokir) }} diblokir<span class="kecil">{{ angka(s.data.retas.waf.tolak) }} WAF{{ s.data.email?.log ? ` · ${angka(s.data.email.log.auth_gagal)} login gagal` : '' }}</span></td>
                  <td><span class="titik" :class="WARNA[s.status.ddos]"></span>{{ angka(s.data.ddos.syn_recv) }} SYN<span class="kecil">{{ angka(s.data.ddos.web) }} koneksi web{{ s.lonjakan?.length ? ` · ${s.lonjakan.length} lonjakan` : '' }}</span></td>
                  <td><span class="titik" :class="WARNA[s.status.sistem]"></span>load {{ nilaiRapi(s.data.sistem.load?.[0]) }} / {{ s.data.sistem.cpu }} CPU<span class="kecil">RAM {{ nilaiRapi(s.data.sistem.ram_persen) }}% · disk {{ nilaiRapi(Math.max(0, ...Object.values(s.data.sistem.disk || {}))) }}%</span></td>
                </template>
                <td v-else colspan="5" class="redup">Server tidak terjangkau</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Rincian satu server -->
      <section v-if="srv?.ok" class="kartu" aria-labelledby="judul-rinci">
        <div class="kartu-judul"><h2 id="judul-rinci"><Ikon nama="pantau" :ukuran="16" /> Rincian {{ srv.name }}</h2><button type="button" class="tombol kecil garis" @click="pilih = ''">Tutup</button></div>
        <div class="tren">
          <figure v-for="t in TREN" :key="t.kol">
            <figcaption>{{ t.label }} <b>{{ angka(akhir(srv.titik, t.kol)) }}</b></figcaption>
            <svg viewBox="0 0 100 30" preserveAspectRatio="none" role="img" :aria-label="`Tren ${t.label} 1 jam`"><polyline :points="garis(srv.titik, t.kol)" /></svg>
          </figure>
        </div>
        <div class="rinci-kisi">
          <div v-if="srv.data.email?.antrean?.ada">
            <h3>Email</h3>
            <dl>
              <dt>Antrean</dt><dd>{{ angka(srv.data.email.antrean.total) }} · tertua {{ srv.data.email.antrean.tertua_jam ?? '—' }} jam</dd>
              <dt>Frozen</dt><dd>{{ angka(srv.data.email.antrean.frozen) }} ({{ angka(srv.data.email.antrean.frozen_24j) }} ≥24 jam)</dd>
              <dt>5 menit</dt><dd>{{ angka(srv.data.email.log?.masuk) }} masuk · {{ angka(srv.data.email.log?.terkirim) }} terkirim · {{ angka(srv.data.email.log?.bounce) }} bounce · {{ angka(srv.data.email.log?.tunda) }} tunda</dd>
            </dl>
            <h4>Pengirim terbanyak di antrean</h4>
            <ul class="top"><li v-for="p in srv.data.email.antrean.pengirim" :key="p.k"><code class="putus">{{ p.k }}</code> <b>{{ p.n }}</b></li></ul>
            <h4>Akun pengirim / 5 mnt</h4>
            <ul class="top"><li v-for="p in srv.data.email.pengirim_akun" :key="p.k"><code class="putus">{{ p.k }}</code> <b>{{ p.n }}</b></li><li v-if="!srv.data.email.pengirim_akun?.length" class="redup">—</li></ul>
          </div>
          <div>
            <h3>Peretasan</h3>
            <dl>
              <dt>LFD</dt><dd>{{ angka(srv.data.retas.lfd.blokir) }} blokir</dd>
              <dt>WAF</dt><dd>{{ angka(srv.data.retas.waf.tolak) }} ditolak</dd>
              <dt>SSH</dt><dd>{{ angka(srv.data.retas.ssh.gagal) }} gagal</dd>
              <dt>Email</dt><dd>{{ angka(srv.data.email?.log?.auth_gagal) }} login gagal</dd>
            </dl>
            <h4>Pemicu LFD</h4>
            <ul class="top"><li v-for="p in srv.data.retas.lfd.pemicu" :key="p.k">{{ p.k }} <b>{{ p.n }}</b></li><li v-if="!srv.data.retas.lfd.pemicu.length" class="redup">—</li></ul>
            <h4>Aturan WAF teratas</h4>
            <ul class="top"><li v-for="p in srv.data.retas.waf.aturan" :key="p.k"><code>{{ p.k }}</code> <b>{{ p.n }}</b></li><li v-if="!srv.data.retas.waf.aturan.length" class="redup">—</li></ul>
            <h4>IP login email gagal</h4>
            <ul class="top"><li v-for="p in srv.data.email?.auth_ip || []" :key="p.k"><code>{{ p.k }}</code> <b>{{ p.n }}</b></li><li v-if="!srv.data.email?.auth_ip?.length" class="redup">—</li></ul>
          </div>
          <div>
            <h3>DDoS & koneksi</h3>
            <dl>
              <dt>SYN_RECV</dt><dd>{{ angka(srv.data.ddos.syn_recv) }}</dd>
              <dt>Aktif</dt><dd>{{ angka(srv.data.ddos.established) }} ({{ angka(srv.data.ddos.web) }} web, {{ angka(srv.data.ddos.ip_unik_web) }} IP)</dd>
              <dt>Conntrack</dt><dd>{{ angka(srv.data.ddos.conntrack) }} / {{ angka(srv.data.ddos.conntrack_maks) }}</dd>
            </dl>
            <h4>Koneksi web per IP</h4>
            <ul class="top"><li v-for="p in srv.data.ddos.ip_web" :key="p.k"><code>{{ p.k }}</code> <b>{{ p.n }}</b></li></ul>
            <h4>Lonjakan aktif</h4>
            <ul class="top"><li v-for="l in srv.lonjakan" :key="l.domain">{{ l.domain }} <b>{{ l.puncak }}/mnt</b></li><li v-if="!srv.lonjakan?.length" class="redup">—</li></ul>
          </div>
          <div>
            <h3>Sistem</h3>
            <dl>
              <dt>Load</dt><dd>{{ srv.data.sistem.load?.join(' · ') }} ({{ srv.data.sistem.cpu }} CPU)</dd>
              <dt>RAM</dt><dd>{{ srv.data.sistem.ram_persen }}% · swap {{ srv.data.sistem.swap_persen }}%</dd>
              <template v-for="(v, m) in srv.data.sistem.disk" :key="m"><dt>Disk {{ m }}</dt><dd>{{ v }}%</dd></template>
            </dl>
            <h4>Layanan</h4>
            <ul class="top"><li v-for="(st, nm) in srv.data.sistem.layanan" :key="nm">{{ nm }} <span class="lencana" :class="st === 'active' ? 'hijau' : 'merah'">{{ st }}</span></li></ul>
          </div>
        </div>
      </section>

      <!-- Riwayat tindakan + efek terukur -->
      <section class="kartu" aria-labelledby="judul-riwayat">
        <div class="kartu-judul"><h2 id="judul-riwayat"><Ikon nama="dokumen" :ukuran="16" /> Riwayat tindakan & efeknya</h2></div>
        <p v-if="!d.tindakan?.length" class="redup">Belum ada tindakan.</p>
        <div v-else class="tabel-wadah">
          <table class="tabel">
            <thead><tr><th scope="col">Waktu</th><th scope="col">Server</th><th scope="col">Tindakan</th><th scope="col">Sebelum → sesudah</th><th scope="col">Oleh</th><th scope="col"><span class="sr">Aksi</span></th></tr></thead>
            <tbody>
              <tr v-for="t in d.tindakan" :key="t.id">
                <td>{{ jam(t.t) }}<span class="kecil">{{ waktuLalu(t.t) }}</span></td>
                <td>{{ t.server }}</td>
                <td><b>{{ AKSI[t.aksi] || t.aksi }}</b> <code v-if="t.target && t.target !== 'semua'" class="putus">{{ t.target }}</code>
                  <span class="kecil">{{ t.ok ? (t.jumlah != null ? `${t.jumlah} pesan` : 'berhasil') : `gagal: ${t.error}` }}{{ t.cadangan ? ` · cadangan ${t.cadangan}` : '' }}</span></td>
                <td>
                  <template v-if="t.sebelum != null">{{ angka(t.sebelum) }} → {{ t.sesudah != null ? angka(t.sesudah) : 'mengukur…' }}
                    <span v-if="selisih(t) != null" class="lencana" :class="selisih(t) < 0 ? 'hijau' : selisih(t) > 0 ? 'merah' : 'abu'">{{ selisih(t) > 0 ? '+' : '' }}{{ angka(selisih(t)) }}</span>
                    <span class="kecil">{{ t.satuan }}</span></template>
                  <span v-else class="redup">—</span>
                </td>
                <td>{{ t.oleh }}</td>
                <td><button v-if="t.aksi === 'tahan_pengirim' && t.ok" type="button" class="tombol kecil garis" @click="lepas(t)">Lepas</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1400px; }
.halaman > * { min-width: 0; }
.kepala-aksi { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.kartu-judul h2 { display: flex; align-items: center; gap: 6px; margin: 0; }
.langsung { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--teks-2); }
.langsung i { width: 8px; height: 8px; border-radius: 50%; background: var(--baik); box-shadow: 0 0 0 3px rgba(52, 199, 123, .2); animation: denyut 2s infinite; }
.langsung.basi i { background: var(--waspada); animation: none; }
@keyframes denyut { 50% { opacity: .35; } }
@media (prefers-reduced-motion: reduce) { .langsung i { animation: none; } }
.ubin-baris { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.ubin { background: var(--kartu); border: 1px solid var(--garis); border-radius: var(--radius, 16px); padding: 14px 16px; display: flex; flex-direction: column; gap: 2px; }
.ubin.waspada { border-color: rgba(232, 181, 74, .45); }
.ubin.bahaya { border-color: rgba(255, 107, 107, .55); }
.ubin-kepala { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--teks-2); }
.ubin-kepala .lencana { margin-left: auto; }
.ubin-angka { font-size: 26px; font-variant-numeric: tabular-nums; color: var(--teks-kuat); margin-top: 6px; }
.blok { display: block; }
.dua-kolom { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 380px), 1fr)); gap: 18px; align-items: start; }
.daftar > li.usulan { grid-template-columns: minmax(0, 1fr) auto; align-items: center; justify-items: stretch; gap: 12px; border-left: 3px solid var(--waspada); }
.daftar > li.usulan.bahaya { border-left-color: var(--bahaya); }
.usulan-isi { display: grid; gap: 4px; min-width: 0; }
.usulan .tombol { white-space: nowrap; }
.target { font-size: 12px; }
.sinyal { list-style: none; margin: 0; padding: 0; display: grid; }
.sinyal li { display: grid; grid-template-columns: 74px 78px minmax(0, 1fr) auto; align-items: center; gap: 10px; padding: 9px 2px; border-bottom: 1px solid var(--garis); font-size: 13px; }
.sinyal li:last-child { border-bottom: 0; }
.sinyal .lencana { justify-self: start; }
.sinyal .kat { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; white-space: nowrap; }
@media (max-width: 640px) { .sinyal li { grid-template-columns: auto minmax(0, 1fr); } .sinyal .kat { grid-column: 2; } }
.matriks td { white-space: nowrap; font-variant-numeric: tabular-nums; }
.matriks td:first-child { width: 1%; padding-right: 28px; }
.matriks .kecil { padding-left: 14px; margin-top: 2px; }
.daftar { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.daftar > li { border: 1px solid var(--garis); border-radius: 12px; padding: 10px 12px; display: grid; gap: 6px; justify-items: start; }
.baris-atas { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.dampak { margin: 0; font-size: 13px; color: var(--waspada); display: flex; gap: 6px; align-items: flex-start; }
.kecil-teks { margin: 0; font-size: 12.5px; }
.bersih { color: var(--baik); display: flex; gap: 6px; align-items: center; margin: 0; }
.hitung { font-size: 12px; background: var(--aksen-lembut); color: var(--aksen-terang); border-radius: 99px; padding: 1px 8px; margin-left: 4px; }
.titik { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.titik.hijau { background: var(--baik); } .titik.kuning { background: var(--waspada); } .titik.merah { background: var(--bahaya); }
.bisa-klik { cursor: pointer; }
.bisa-klik:hover, .bisa-klik.terpilih { background: var(--sorot); }
.bisa-klik:focus-visible { outline: 2px solid var(--aksen-terang); outline-offset: -2px; }
.tren { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 16px; }
.tren figure { margin: 0; background: var(--kartu-2); border-radius: 10px; padding: 8px 10px; }
.tren figcaption { font-size: 12px; color: var(--teks-3); display: flex; justify-content: space-between; }
.tren figcaption b { color: var(--teks); font-variant-numeric: tabular-nums; }
.tren svg { width: 100%; height: 32px; display: block; margin-top: 4px; }
.tren polyline { fill: none; stroke: var(--seri-1); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.rinci-kisi { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; }
.rinci-kisi h3 { font-size: 14px; margin: 0 0 8px; }
.rinci-kisi h4 { font-size: 12px; color: var(--teks-3); margin: 12px 0 4px; font-weight: 600; }
.rinci-kisi dl { display: grid; grid-template-columns: auto 1fr; gap: 4px 10px; margin: 0; font-size: 13px; }
.rinci-kisi dt { color: var(--teks-3); }
.rinci-kisi dd { margin: 0; font-variant-numeric: tabular-nums; }
.top { list-style: none; margin: 0; padding: 0; font-size: 12.5px; display: grid; gap: 3px; }
.top li { display: flex; justify-content: space-between; gap: 8px; }
.putus { overflow-wrap: anywhere; }
.sinyal-judul { overflow-wrap: break-word; word-break: normal; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>
