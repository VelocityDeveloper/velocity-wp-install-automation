<script setup>
// Kesiapan copot cPGuard (sub-menu Server): per server hosting, fungsi cPGuard mana yang sudah punya pengganti Velocity
// dan apa langkah berikutnya. HANYA MEMBACA endpoint modul lain (tanpa SSH baru, tanpa tombol aksi):
// /api/servers/waf, /api/servers/bfm, /api/servers/monitor (cache SSH modul masing-masing),
// /api/servers/antivirus/scan & /api/servers/cms (berkas hasil di disk dashboard).
// Mencopot cPGuard tetap manual per server atas izin (keputusan 12 Okt: paralel dulu 1–2 minggu).
import { computed } from 'vue'
import Ikon from '../components/Ikon.vue'
import Info from '../components/Info.vue'
import { pakaiPolling, waktuLalu, tanggalWaktu, angka } from '../api.js'
import { tabUrl } from '../laravel.js'

// Ambang kesiapan
const HARI_PARALEL = 7 // WAF Velocity berdampingan dengan cPGuard minimal sekian hari sebelum cPGuard dicopot
const HARI_SCAN_CMS = 7
const HARI_SCAN_AV = 7

const waf = pakaiPolling('/api/servers/waf', 300000)
const bfm = pakaiPolling('/api/servers/bfm', 300000)
const mon = pakaiPolling('/api/servers/monitor', 300000)
const av = pakaiPolling('/api/servers/antivirus/scan', 300000)
const cms = pakaiPolling('/api/servers/cms', 300000)
const sumber = [waf, bfm, mon, av, cms]
const memuat = computed(() => sumber.some((x) => x.memuat.value && !x.data.value))
const gagal = computed(() => sumber.filter((x) => x.galat.value).map((x) => x.galat.value.message))
const muatUlang = () => sumber.forEach((x) => x.muatUlang())

const sekarang = () => Date.now() / 1000
const hari = (t) => (t ? (sekarang() - t) / 86400 : Infinity)
const perHost = (d) => Object.fromEntries((d?.servers || []).map((s) => [s.host, s]))

const servers = computed(() => (waf.data.value?.servers || cms.data.value?.servers || []).map((s) => ({ host: s.host, name: s.name })))

// Status: siap | sebagian | belum | info. Setiap fungsi: label cPGuard, pengganti, cek(server) → {status, teks, langkah}
const FUNGSI = [
  {
    k: 'waf', label: 'WAF (ModSecurity ruleset)', pengganti: 'Velocity WAF', ke: '/server/waf', wajib: true,
    ket: 'Aturan WAF sekarang berasal dari /etc/cpguard/cpguard_modsec*.conf — ikut hilang saat cPGuard dicopot.',
    cek: ({ w }) => {
      const st = w?.status
      if (!w) return { status: 'belum', teks: 'Data WAF belum terbaca' }
      if (!w.ok) return { status: 'belum', teks: `Tidak terbaca: ${w.error || 'gagal'}` }
      if (!st?.terpasang) return { status: 'belum', teks: 'Belum terpasang', langkah: 'Pasang Velocity WAF mode deteksi' }
      const basi = st.sidik && waf.data.value?.lokal?.sidik && st.sidik !== waf.data.value.lokal.sidik
      if (st.mode !== 'blokir') return { status: 'sebagian', teks: `Terpasang mode deteksi${basi ? ' · perlu diperbarui' : ''}`, langkah: 'Pantau log, lalu ubah ke mode blokir' }
      return basi ? { status: 'sebagian', teks: 'Mode blokir · ruleset perlu diperbarui', langkah: 'Pasang ulang dengan setelan terbaru' } : { status: 'siap', teks: 'Mode blokir, ruleset terbaru' }
    },
  },
  {
    k: 'paralel', label: 'Masa uji berdampingan', pengganti: `≥ ${HARI_PARALEL} hari bersama cPGuard`, ke: '/server/waf?tab=log', wajib: true,
    ket: 'Velocity WAF dijalankan berdampingan dengan cPGuard agar positif palsu & selisih deteksi terlihat sebelum cPGuard dicopot.',
    cek: ({ w }) => {
      const st = w?.status
      if (!st?.terpasang || !st.diubah) return { status: 'belum', teks: 'Belum mulai (WAF belum terpasang)' }
      const h = hari(st.diubah)
      if (h >= HARI_PARALEL) return { status: 'siap', teks: `${Math.floor(h)} hari sejak ${tanggalWaktu(st.diubah)}` }
      return { status: 'sebagian', teks: `Hari ke-${Math.floor(h) + 1} dari ${HARI_PARALEL}`, langkah: `Tunggu ±${Math.ceil(HARI_PARALEL - h)} hari lagi` }
    },
  },
  {
    k: 'bfm', label: 'Brute Force Monitor (BFM)', pengganti: 'Velocity BFM + LFD', ke: '/server/bruteforce', wajib: true,
    ket: 'BFM cPGuard memblokir IP dari hit WAF ke csf.deny ("BFM:"). Pengganti membaca log WAF Velocity lewat aturan LFD.',
    cek: ({ b }) => {
      if (!b) return { status: 'belum', teks: 'Data brute force belum terbaca' }
      if (!b.ok) return { status: 'belum', teks: `Tidak terbaca: ${b.error || 'gagal'}` }
      if (!b.blok?.terpasang) return { status: 'belum', teks: 'Aturan Velocity BFM belum terpasang', langkah: 'Pasang dari halaman Brute Force' }
      if (!b.blok.slot_ok) return { status: 'sebagian', teks: 'Terpasang, slot log LFD bermasalah', langkah: 'Periksa CUSTOMn_LOG di csf.conf' }
      if (!b.lfd_aktif) return { status: 'belum', teks: 'LFD tidak aktif' }
      if (b.velocity_waf !== 'blokir') return { status: 'sebagian', teks: 'Terpasang, belum memblokir (WAF masih deteksi)', langkah: 'Aktif sendiri saat WAF mode blokir' }
      return { status: 'siap', teks: 'Terpasang & memblokir' }
    },
  },
  {
    k: 'firewall', label: 'Firewall CSF / LFD', pengganti: 'CSF + halaman Proteksi', ke: '/server/proteksi', wajib: true,
    ket: 'CSF/LFD tetap jalan tanpa cPGuard. Blokir "BFM:" milik cPGuard di csf.deny tidak diperbarui lagi sesudah dicopot.',
    cek: ({ b, m }) => {
      if (!b?.ok) return { status: 'belum', teks: 'Data CSF belum terbaca' }
      if (!b.lfd_aktif) return { status: 'belum', teks: 'LFD tidak aktif', langkah: 'Hidupkan LFD' }
      if (b.csf?.TESTING === '1') return { status: 'belum', teks: 'CSF masih mode TESTING' }
      const d = b.deny || {}
      const limit = Number(b.csf?.DENY_IP_LIMIT) || 0
      const porsi = d.total ? Math.round((d.sumber?.cpguard || 0) * 100 / d.total) : 0
      if (limit && d.total >= limit * 0.95) return { status: 'sebagian', teks: `csf.deny hampir penuh (${angka(d.total)}/${angka(limit)})`, langkah: 'Naikkan DENY_IP_LIMIT atau bersihkan' }
      return { status: 'siap', teks: `LFD aktif · csf.deny ${angka(d.total)}/${angka(limit)} (${porsi}% dari cPGuard)` }
    },
  },
  {
    k: 'cms', label: 'CMS Threat (kerentanan WordPress)', pengganti: 'Kerentanan CMS', ke: '/server/cms', wajib: true,
    ket: 'cPGuard memperbarui cms.db tiap malam. Pengganti: scan dari halaman Kerentanan CMS (belum terjadwal otomatis).',
    cek: ({ c }) => {
      if (!c?.diambil) return { status: 'belum', teks: 'Belum pernah di-scan', langkah: 'Scan dari halaman Kerentanan CMS' }
      const h = hari(c.diambil)
      if (h > HARI_SCAN_CMS) return { status: 'sebagian', teks: `Scan terakhir ${waktuLalu(c.diambil)}`, langkah: 'Scan ulang / buat jadwal malam' }
      return { status: 'sebagian', teks: `Scan ${waktuLalu(c.diambil)} · ${angka(c.ringkas?.situs)} situs, belum terjadwal`, langkah: 'Buat jadwal scan malam + notifikasi' }
    },
  },
  {
    k: 'malware', label: 'Pemindai malware', pengganti: 'Antivirus Velocity (VD.*)', ke: '/server/antivirus', wajib: true,
    ket: 'cPGuard memindai real-time (setiap berkas berubah) dengan libclamav + tanda tangan Malware.Expert. Pengganti saat ini scan manual tanda tangan VD.*; ClamAV ditunda menunggu keputusan.',
    cek: ({ a }) => {
      const selesai = a.filter((j) => j.status === 'selesai')
      const semua = selesai.find((j) => j.akun === 'semua')
      if (!selesai.length) return { status: 'belum', teks: 'Belum pernah di-scan dari dashboard; tanpa real-time', langkah: 'Putuskan ClamAV + jadwal scan' }
      if (!semua || hari(semua.mulai) > HARI_SCAN_AV) return { status: 'belum', teks: `Scan manual terakhir ${waktuLalu(selesai[0].mulai)}; tanpa real-time`, langkah: 'Putuskan ClamAV + jadwal scan' }
      return { status: 'sebagian', teks: `Scan semua akun ${waktuLalu(semua.mulai)}; tanpa real-time & tanpa jadwal`, langkah: 'Putuskan ClamAV + jadwal scan' }
    },
  },
  {
    k: 'pantau', label: 'Pemantauan & insiden (cpgosm)', pengganti: 'Monitoring Server', ke: '/server/monitoring', wajib: false,
    ket: 'Modul OS monitor/insiden cPGuard. Monitoring Velocity membaca resource, layanan, CSF, ModSecurity, dan CPU per akun — tanpa deteksi proses jahat otomatis.',
    cek: ({ m }) => {
      if (!m) return { status: 'info', teks: 'Data monitoring belum terbaca' }
      if (!m.ok) return { status: 'info', teks: `Tidak terbaca: ${m.error || 'gagal'}` }
      return { status: 'info', teks: `Monitoring jalan${m.cpguard ? ` · cPGuard 24 jam: ${angka(m.cpguard.insiden)} insiden` : ''}` }
    },
  },
]

const STATUS = {
  siap: { label: 'Siap', kelas: 'hijau', ikon: 'centang' },
  sebagian: { label: 'Sebagian', kelas: 'kuning', ikon: 'peringatan' },
  belum: { label: 'Belum', kelas: 'merah', ikon: 'peringatan' },
  info: { label: 'Info', kelas: 'abu', ikon: 'pantau' },
}

const matriks = computed(() => {
  const W = perHost(waf.data.value), B = perHost(bfm.data.value), M = perHost(mon.data.value), C = perHost(cms.data.value)
  const scan = av.data.value?.scan || []
  return servers.value.map((s) => {
    const ctx = { w: W[s.host], b: B[s.host], m: M[s.host], c: C[s.host], a: scan.filter((j) => j.host === s.host) }
    const hasil = Object.fromEntries(FUNGSI.map((f) => [f.k, f.cek(ctx)]))
    const wajib = FUNGSI.filter((f) => f.wajib)
    const siap = wajib.filter((f) => hasil[f.k].status === 'siap').length
    const sebagian = wajib.filter((f) => hasil[f.k].status === 'sebagian').length
    const cpgJalan = ctx.m?.cpguard ? Object.values(ctx.m.cpguard.proses || {}).some(Boolean) : null
    return { ...s, hasil, siap, sebagian, skor: siap + sebagian / 2, total: wajib.length, cpgJalan, cpgVersi: ctx.m?.cpguard?.versi,
      langkah: wajib.map((f) => ({ f, ...hasil[f.k] })).filter((x) => x.status !== 'siap' && x.langkah) }
  })
})
const pilih = tabUrl('s', '')
const terpilih = computed(() => matriks.value.find((s) => s.name === pilih.value) || null)
const persen = (s) => Math.max(4, Math.round((s.skor / s.total) * 100))
const kesimpulan = (s) => (s.siap === s.total ? ['hijau', 'Siap dicopot'] : s.siap >= s.total - 2 ? ['kuning', 'Hampir siap'] : ['merah', 'Belum siap'])
const totalSiap = computed(() => matriks.value.filter((s) => s.siap === s.total).length)
const terdekat = computed(() => [...matriks.value].sort((a, b) => b.skor - a.skor)[0])
// Pemblokir yang sama di semua server (bukan per server)
const pemblokirUmum = computed(() => FUNGSI.filter((f) => f.wajib && matriks.value.length && matriks.value.every((s) => s.hasil[f.k].status !== 'siap')))
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Kesiapan Copot cPGuard</h1>
        <p class="redup">Fungsi cPGuard mana yang sudah punya pengganti Velocity di tiap server. Halaman ini hanya membaca; mencopot cPGuard tetap manual per server atas izin.</p>
      </div>
      <button type="button" class="tombol kecil" :disabled="memuat" @click="muatUlang"><Ikon nama="ulang" :ukuran="16" /> Muat ulang</button>
    </header>

    <p v-if="memuat" class="redup" role="status">Membaca status WAF, brute force, monitoring, antivirus, dan CMS (±5–20 detik bila cache kosong)…</p>
    <template v-else>
      <p v-if="gagal.length" class="pesan-status bahaya">Sebagian data gagal dimuat: {{ gagal.join(' · ') }}</p>

      <div class="ringkas">
        <div class="kartu tile">
          <span class="tile-ikon hijau"><Ikon nama="centang" :ukuran="20" /></span>
          <div><span class="redup">Server siap dicopot</span><b>{{ totalSiap }} / {{ matriks.length }}</b><small class="redup">semua fungsi wajib terganti</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon biru"><Ikon nama="server" :ukuran="20" /></span>
          <div><span class="redup">Paling dekat</span><b>{{ terdekat?.name || '-' }}</b><small class="redup">{{ terdekat ? `${terdekat.siap}/${terdekat.total} siap · ${terdekat.sebagian} sebagian` : '' }}</small></div>
        </div>
        <div class="kartu tile">
          <span class="tile-ikon merah"><Ikon nama="peringatan" :ukuran="20" /></span>
          <div><span class="redup">Belum ada pengganti di semua server</span><b>{{ pemblokirUmum.length }}</b><small class="redup">{{ pemblokirUmum.map((f) => f.pengganti).join(', ') || 'tidak ada' }}</small></div>
        </div>
      </div>

      <!-- Kartu per server -->
      <div class="grid-server">
        <button v-for="s in matriks" :key="s.host" type="button" class="kartu server-kartu" :class="{ aktif: terpilih === s }" :aria-pressed="terpilih === s" @click="pilih = terpilih === s ? '' : s.name">
          <div class="server-kepala">
            <b>{{ s.name }}</b>
            <span class="lencana" :class="kesimpulan(s)[0]">{{ kesimpulan(s)[1] }}</span>
          </div>
          <div class="meter" role="img" :aria-label="`${s.siap} dari ${s.total} fungsi siap`"><span :class="kesimpulan(s)[0]" :style="{ width: `${persen(s)}%` }" /></div>
          <small class="redup">{{ s.siap }}/{{ s.total }} siap<template v-if="s.sebagian"> · {{ s.sebagian }} sebagian</template> · cPGuard {{ s.cpgJalan === null ? '?' : s.cpgJalan ? `jalan${s.cpgVersi ? ' ' + s.cpgVersi : ''}` : 'TIDAK jalan' }}</small>
          <small v-if="s.langkah[0]" class="redup langkah-utama">Berikutnya: {{ s.langkah[0].langkah }}</small>
        </button>
      </div>

      <!-- Matriks fungsi × server -->
      <section class="kartu" aria-labelledby="judul-matriks">
        <div class="kartu-judul"><h2 id="judul-matriks"><Ikon nama="daftar" :ukuran="16" /> Fungsi cPGuard &amp; penggantinya</h2></div>
        <div class="tabel-wadah">
          <table class="tabel matriks">
            <thead>
              <tr>
                <th scope="col">Fungsi cPGuard → pengganti</th>
                <th v-for="s in matriks" :key="s.host" scope="col" :class="{ sorot: terpilih === s }">{{ s.name }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="f in FUNGSI" :key="f.k">
                <th scope="row" class="fungsi">
                  <span class="fungsi-nama">{{ f.label }} <Info :label="`Tentang ${f.label}`"><p>{{ f.ket }}</p></Info></span>
                  <router-link :to="f.ke" class="redup pengganti">→ {{ f.pengganti }}</router-link>
                  <small v-if="!f.wajib" class="redup blok">tidak menghalangi copot</small>
                </th>
                <td v-for="s in matriks" :key="s.host" :class="{ sorot: terpilih === s }">
                  <span class="status" :class="STATUS[s.hasil[f.k].status].kelas"><Ikon :nama="STATUS[s.hasil[f.k].status].ikon" :ukuran="14" /> {{ STATUS[s.hasil[f.k].status].label }}</span>
                  <small class="redup blok">{{ s.hasil[f.k].teks }}</small>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Langkah per server -->
      <section class="kartu" aria-labelledby="judul-langkah">
        <div class="kartu-judul"><h2 id="judul-langkah"><Ikon nama="centang" :ukuran="16" /> Langkah berikutnya{{ terpilih ? ` · ${terpilih.name}` : '' }}</h2></div>
        <template v-for="s in (terpilih ? [terpilih] : matriks)" :key="s.host">
          <h3 v-if="!terpilih" class="sub-judul">{{ s.name }} <span class="redup">{{ s.siap }}/{{ s.total }}</span></h3>
          <ol v-if="s.langkah.length" class="langkah">
            <li v-for="x in s.langkah" :key="x.f.k">
              <router-link :to="x.f.ke + (x.f.ke.includes('?') ? '&' : '?') + `s=${encodeURIComponent(s.name)}`">{{ x.langkah }}</router-link>
              <span class="redup"> — {{ x.f.label }}: {{ x.teks }}</span>
            </li>
          </ol>
          <p v-else-if="s.siap === s.total" class="bersih"><Ikon nama="centang" :ukuran="18" /> Semua fungsi wajib sudah terganti. Copot cPGuard bisa dijadwalkan (minta izin dulu).</p>
          <p v-else class="redup">Menunggu waktu (lihat matriks).</p>
        </template>
      </section>

      <section class="kartu catatan" aria-labelledby="judul-copot">
        <div class="kartu-judul"><h2 id="judul-copot"><Ikon nama="peringatan" :ukuran="16" /> Urutan copot yang disarankan (manual)</h2></div>
        <ol class="langkah">
          <li>Semua baris wajib <b>Siap</b>, WAF mode blokir ≥ {{ HARI_PARALEL }} hari tanpa keluhan positif palsu.</li>
          <li>Cadangkan konfigurasi: <code>/etc/cpguard/</code>, <code>/opt/cpguard/app/data/*.db</code>, <code>csf.conf</code>, <code>csf.deny</code>.</li>
          <li>Hentikan layanan cPGuard dulu (jangan langsung uninstall), pantau 48 jam: WAF, LFD, situs klien, beban server.</li>
          <li>Bila aman: uninstall cPGuard, pastikan include <code>cpguard_modsec*.conf</code> hilang dan LiteSpeed restart bersih.</li>
          <li>Blokir "BFM:" lama di csf.deny dibiarkan kedaluwarsa tergusur blokir baru.</li>
        </ol>
        <p class="redup kecil-teks">Ambang: masa uji {{ HARI_PARALEL }} hari, scan CMS & antivirus ≤ {{ HARI_SCAN_CMS }} hari. Scan manual dihitung "Sebagian" sampai ada jadwal otomatis.</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; max-width: 1100px; }
.halaman > * { min-width: 0; }
.ringkas { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.tile { display: flex; gap: 14px; align-items: center; }
.tile > div { display: grid; gap: 3px; min-width: 0; }
.tile b { font-size: 24px; color: var(--teks-kuat); }
.tile small { font-size: 12px; }
.tile-ikon { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; }
.tile-ikon.merah { color: var(--bahaya); background: color-mix(in srgb, var(--bahaya) 15%, transparent); }
.tile-ikon.hijau { color: var(--baik); background: color-mix(in srgb, var(--baik) 15%, transparent); }
.tile-ikon.biru { color: var(--aksen-terang); background: var(--aksen-lembut); }
.grid-server { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(200px, 100%), 1fr)); gap: 12px; }
.server-kartu { display: grid; gap: 8px; text-align: left; font: inherit; color: var(--teks); cursor: pointer; padding: 14px 16px; }
.server-kartu:hover { border-color: var(--aksen-terang); }
.server-kartu.aktif { border-color: var(--aksen-terang); box-shadow: 0 0 0 1px var(--aksen-terang); }
.server-kepala { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.server-kepala b { font-size: 15px; color: var(--teks-kuat); }
.server-kartu small { font-size: 12px; }
.langkah-utama { overflow-wrap: anywhere; }
.meter { height: 6px; border-radius: 3px; background: var(--garis); overflow: hidden; }
.meter span { display: block; height: 100%; border-radius: 3px; }
.meter .hijau { background: var(--baik); }
.meter .kuning { background: var(--waspada); }
.meter .merah { background: var(--bahaya); }
.matriks th, .matriks td { vertical-align: top; }
.matriks td { min-width: 112px; font-size: 12.5px; }
.matriks th, .matriks td { padding-left: 8px; padding-right: 8px; }
.matriks .sorot { background: var(--aksen-lembut); }
.fungsi { min-width: 190px; text-align: left; font-weight: 400; }
.fungsi-nama { display: inline-flex; align-items: center; gap: 4px; font-weight: 600; color: var(--teks-kuat); font-size: 13.5px; }
.pengganti { display: block; font-size: 12.5px; text-decoration: none; margin-top: 2px; }
.pengganti:hover { text-decoration: underline; }
.status { display: inline-flex; align-items: center; gap: 5px; font-weight: 600; font-size: 13px; }
.status.hijau { color: var(--baik); }
.status.kuning { color: var(--waspada); }
.status.merah { color: var(--bahaya); }
.status.abu { color: var(--teks-2); }
.blok { display: block; margin-top: 2px; overflow-wrap: anywhere; }
.sub-judul { font-size: 14px; margin: 14px 0 6px; }
.sub-judul:first-of-type { margin-top: 0; }
.langkah { margin: 0; padding-left: 20px; display: grid; gap: 7px; font-size: 13.5px; }
.langkah a { color: var(--aksen-terang); font-weight: 600; }
.bersih { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--baik); font-weight: 600; }
.kecil-teks { font-size: 12.5px; margin: 12px 0 0; }
.tabel-wadah { position: relative; overflow-x: auto; }
code { font: 12.5px ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--teks); }
@media (max-width: 900px) { .ringkas { grid-template-columns: 1fr; } }
</style>
