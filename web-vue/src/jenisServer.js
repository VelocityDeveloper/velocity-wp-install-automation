import { computed, watch } from 'vue'
import { tabUrl } from './laravel.js'
// Tag pembeda mesin di menu Server: server hosting (servers.json, tujuan installer, CSF)
// vs PC kantor (servers-monitor.json: PC Lokal = dashboard ini, PC Backup; firewalld/ufw).
export const JENIS_SERVER = {
  hosting: { label: 'Hosting', kelas: 'biru', ket: 'Server hosting klien (DirectAdmin)' },
  lokal: { label: 'PC Lokal', kelas: 'ungu', ket: 'PC kantor: dashboard, installer, server dev' },
  backup: { label: 'PC Backup', kelas: 'teal', ket: 'PC kantor: tujuan backup DirectAdmin' },
}
export const jenisServer = (j) => JENIS_SERVER[j] || JENIS_SERVER.hosting
export const pcKantor = (s) => s?.jenis === 'lokal' || s?.jenis === 'backup'

// Server terpilih di sub menu Server: ?s= di URL menang (tautan dibagikan), kalau kosong pakai pilihan
// terakhir (localStorage) supaya server tetap sama saat pindah Monitoring → Proteksi → WAF dst.
const KUNCI_SERVER = 'server-terpilih'
const bacaServer = () => { try { return localStorage.getItem(KUNCI_SERVER) || '' } catch { return '' } }
const simpanServer = (v) => { try { if (v) localStorage.setItem(KUNCI_SERVER, v) } catch { /* mode privat */ } }
export function pilihServer() {
  const s = tabUrl('s', '')
  watch(s, simpanServer, { immediate: true })
  return computed({ get: () => s.value || bacaServer(), set: (v) => { simpanServer(v); s.value = v } })
}
