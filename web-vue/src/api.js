// Akses API dashboard (tidak diubah; sama dengan yang dipakai dashboard lama) + polling berkala
import { ref, onMounted, onBeforeUnmount } from 'vue'

export async function ambil(url, opsi = {}) {
  const r = await fetch(url, { cache: 'no-store', ...opsi })
  if (!r.ok) throw new Error(`${r.status} ${url}`)
  return r.json()
}

// Ambil data tiap `jeda` ms selama komponen tampil. Mengembalikan { data, galat, memuat, muatUlang }.
export function pakaiPolling(url, jeda) {
  const data = ref(null)
  const galat = ref(null)
  const memuat = ref(true)
  let timer = null
  const muatUlang = async () => {
    try {
      data.value = await ambil(typeof url === 'function' ? url() : url)
      galat.value = null
    } catch (e) {
      galat.value = e
    } finally {
      memuat.value = false
    }
  }
  onMounted(() => { muatUlang(); if (jeda) timer = setInterval(muatUlang, jeda) })
  onBeforeUnmount(() => clearInterval(timer))
  return { data, galat, memuat, muatUlang }
}

export const ukuranBerkas = (n) => {
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++ }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`
}

export const waktuLalu = (t) => {
  if (!t) return '-'
  const d = Math.floor(Date.now() / 1000) - t
  if (d < 60) return 'baru saja'
  if (d < 3600) return `${Math.floor(d / 60)} menit lalu`
  if (d < 86400) return `${Math.floor(d / 3600)} jam lalu`
  return `${Math.floor(d / 86400)} hari lalu`
}

// POST JSON; galat membawa kode `error` dari API (dipetakan ke pesan manusiawi di tiap halaman)
export async function kirim(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) })
  const teks = await r.text()
  let j
  try { j = JSON.parse(teks) } catch { j = { error: `respon bukan JSON (HTTP ${r.status})` } }
  if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`)
  return j
}

// GET JSON dengan pesan galat dari API
export async function minta(url) {
  const r = await fetch(url, { cache: 'no-store' })
  const j = await r.json().catch(() => ({}))
  if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`)
  return j
}

export const tanggalWaktu = (ts) => {
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts)
  return ts && !isNaN(d) ? d.toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' }) : '-'
}
export const angka = (n) => Number(n || 0).toLocaleString('id-ID')
