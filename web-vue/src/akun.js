// Akun yang sedang masuk ke dash.velocity.ai.id. Datanya dari gerbang login (/opt/dash-login, GET /__me);
// lewat LAN/Tailscale tidak ada gerbang, /__me tidak ada → akun.value tetap null dan kartu akun disembunyikan.
import { ref, computed } from 'vue'

export const akun = ref(null)
export const akunDimuat = ref(false)

export async function muatAkun() {
  try {
    const r = await fetch('/__me', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    const d = r.ok && (r.headers.get('content-type') || '').includes('json') ? await r.json() : null
    akun.value = d?.masuk ? d : null
  } catch {
    akun.value = null
  } finally {
    akunDimuat.value = true
  }
}

export const inisial = (nama) => (nama || '?').split(/[\s._-]+/).filter(Boolean).slice(0, 2).map((k) => k[0].toUpperCase()).join('')
export const URL_KELUAR = '/__logout'

// Nama pelaku untuk riwayat aksi (field "oleh"). Backend tetap menggantinya dengan nama dari cookie sesi,
// jadi ini hanya untuk tampilan & mencegah kirim saat belum masuk.
export const namaAkun = computed(() => akun.value?.nama || '')

// Tombol "Masuk dengan VD.net". Dari LAN/Tailscale tidak ada gerbang login, jadi dibawa ke halaman yang sama di dash.
export const DASH = 'https://dash.velocity.ai.id'
export function urlMasuk(tujuan = location.pathname + location.search) {
  const jalur = `/__sso/mulai?next=${encodeURIComponent(tujuan)}`
  return location.hostname === 'dash.velocity.ai.id' ? jalur : DASH + jalur
}
