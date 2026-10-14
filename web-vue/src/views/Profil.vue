<script setup>
// Profil akun yang sedang masuk ke dash.velocity.ai.id (data dari /__me di gerbang dash-login).
import { computed, onMounted } from 'vue'
import Ikon from '../components/Ikon.vue'
import { tanggalWaktu } from '../api.js'
import { akun, akunDimuat, muatAkun, inisial, URL_KELUAR } from '../akun.js'

onMounted(muatAkun)

const a = computed(() => akun.value)
const sisaHari = computed(() => (a.value ? Math.max(0, Math.ceil((a.value.sampai - Date.now() / 1000) / 86400)) : 0))
const peramban = (ua) => {
  if (!ua) return '-'
  const os = /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Windows/.test(ua) ? 'Windows' : /Mac OS/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : ''
  const br = /Edg\//.test(ua) ? 'Edge' : /OPR\//.test(ua) ? 'Opera' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : ua.split(/[ /]/)[0]
  return [br, os].filter(Boolean).join(' · ')
}
</script>

<template>
  <div class="halaman">
    <header class="kepala-halaman">
      <div>
        <h1>Profil</h1>
        <p class="redup">Akun yang sedang masuk ke dashboard ini.</p>
      </div>
      <a v-if="a" :href="URL_KELUAR" class="tombol bahaya kecil"><Ikon nama="keluar" :ukuran="16" /> Keluar</a>
    </header>

    <section v-if="!akunDimuat" class="kartu"><p class="redup">Memuat…</p></section>

    <section v-else-if="!a" class="kartu kosong">
      <Ikon nama="pengguna" :ukuran="28" />
      <p>Profil hanya tersedia saat membuka dashboard lewat <b>dash.velocity.ai.id</b>.</p>
      <p class="redup">Dari jaringan kantor / Tailscale dashboard terbuka tanpa login, jadi tidak ada akun yang masuk.</p>
    </section>

    <template v-else>
      <section class="kartu identitas">
        <span class="avatar besar" aria-hidden="true">{{ inisial(a.nama) }}</span>
        <div class="id-teks">
          <h2>{{ a.nama }}</h2>
          <p class="redup">@{{ a.username }}</p>
          <p class="lencana-baris">
            <span class="lencana" :class="a.sumber === 'vdnet' ? 'biru' : 'abu'">{{ a.sumber === 'vdnet' ? 'Masuk dengan VD.net' : 'Akun dashboard' }}</span>
            <span v-for="p in a.peran" :key="p" class="lencana teal">{{ p }}</span>
          </p>
        </div>
      </section>

      <div class="grid">
        <section class="kartu">
          <div class="kartu-judul"><h2>Sesi ini</h2><span class="pil baik">Aktif</span></div>
          <dl class="rincian">
            <dt>Masuk</dt><dd>{{ tanggalWaktu(a.sejak) }}</dd>
            <dt>Berakhir</dt><dd>{{ tanggalWaktu(a.sampai) }} <span class="redup">({{ sisaHari }} hari lagi)</span></dd>
            <dt>IP sekarang</dt><dd><code>{{ a.ip }}</code><span v-if="a.negara" class="redup"> · {{ a.negara }}</span></dd>
          </dl>
          <div class="aksi">
            <a :href="URL_KELUAR" class="tombol bahaya kecil"><Ikon nama="keluar" :ukuran="16" /> Keluar dari dashboard</a>
            <a v-if="a.sumber === 'vdnet'" href="https://new.velocitydeveloper.net/" target="_blank" rel="noopener" class="tombol garis kecil"><Ikon nama="luar" :ukuran="16" /> Buka VD.net</a>
          </div>
          <p v-if="a.sumber === 'vdnet'" class="redup catatan">Keluar di sini hanya menutup sesi dashboard; akun VD.net Anda tetap masuk.</p>
        </section>

        <section class="kartu">
          <div class="kartu-judul"><h2>Riwayat masuk</h2><span class="redup">{{ a.riwayat.length }} terakhir</span></div>
          <p v-if="!a.riwayat.length" class="redup">Belum ada catatan.</p>
          <div v-else class="tabel-wadah">
            <table class="tabel">
              <thead><tr><th>Waktu</th><th>IP</th><th class="sembunyi-hp">Peramban</th></tr></thead>
              <tbody>
                <tr v-for="(r, i) in a.riwayat" :key="i">
                  <td>{{ tanggalWaktu(r.waktu) }}</td>
                  <td><code>{{ r.ip }}</code><span v-if="r.negara" class="kecil">{{ r.negara }}</span></td>
                  <td class="sembunyi-hp">{{ peramban(r.ua) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.halaman { display: grid; gap: 20px; }
.kosong { display: grid; justify-items: center; gap: 6px; text-align: center; padding: 36px 20px; color: var(--teks-2); }
.kosong p { margin: 0; }
.identitas { display: flex; align-items: center; gap: 18px; }
.id-teks h2 { font-size: 20px; }
.id-teks p { margin: 2px 0 0; }
.lencana-baris { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px !important; }
.avatar.besar { width: 64px; height: 64px; font-size: 22px; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr); gap: 20px; align-items: start; }
.rincian { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 10px 16px; margin: 0; font-size: 14px; }
.rincian dt { color: var(--teks-3); }
.rincian dd { margin: 0; color: var(--teks-kuat); overflow-wrap: anywhere; }
.aksi { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
.catatan { margin: 10px 0 0; }
code { font-size: 12.5px; }
@media (max-width: 900px) { .grid { grid-template-columns: minmax(0, 1fr); } }
</style>
