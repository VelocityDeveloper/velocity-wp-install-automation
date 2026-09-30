// Tema terang/gelap: nilai awal sudah dipasang skrip kecil di index.html (sebelum CSS dimuat, jadi tidak berkedip).
// Pilihan user disimpan di localStorage; tanpa pilihan, ikut tema sistem dan berubah saat sistem berubah.
import { ref } from 'vue'

const KUNCI = 'tema'
const media = window.matchMedia('(prefers-color-scheme: light)')
const baca = () => { try { return localStorage.getItem(KUNCI) } catch { return null } }

export const tema = ref(document.documentElement.dataset.theme || (media.matches ? 'light' : 'dark'))

function pasang(t) {
  tema.value = t
  document.documentElement.dataset.theme = t
}

export function gantiTema() {
  const t = tema.value === 'light' ? 'dark' : 'light'
  pasang(t)
  try { localStorage.setItem(KUNCI, t) } catch { /* mode privat: cukup berlaku di sesi ini */ }
}

media.addEventListener('change', (e) => { if (!baca()) pasang(e.matches ? 'light' : 'dark') })
