import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Beranda from './views/Beranda.vue'
import './style.css'

// Halaman lain dimuat saat dibuka (Monaco/Mermaid dll. tidak ikut diunduh di setiap halaman)
const Server = () => import('./views/Server.vue')
const ServerMonitor = () => import('./views/ServerMonitor.vue')
const ServerProteksi = () => import('./views/ServerProteksi.vue')
const ServerAntivirus = () => import('./views/ServerAntivirus.vue')
const ServerWaf = () => import('./views/ServerWaf.vue')
const ServerBruteforce = () => import('./views/ServerBruteforce.vue')
const ServerCms = () => import('./views/ServerCms.vue')
const ServerCpguard = () => import('./views/ServerCpguard.vue')
const Installer = () => import('./views/Installer.vue')
const Susulan = () => import('./views/Susulan.vue')
const InstallerLaravel = () => import('./views/InstallerLaravel.vue')
const LaravelProyek = () => import('./views/LaravelProyek.vue')
const Brain = () => import('./views/Brain.vue')
const Paket = () => import('./views/Paket.vue')
const AiModel = () => import('./views/AiModel.vue')
const Token = () => import('./views/Token.vue')
const Projects = () => import('./views/Projects.vue')
const Tutorial = () => import('./views/Tutorial.vue')
const NotifEmail = () => import('./views/NotifEmail.vue')
const Report = () => import('./views/Report.vue')
const Berkas = () => import('./views/Berkas.vue')
const PcBackup = () => import('./views/PcBackup.vue')
const VelocityUpdate = () => import('./views/VelocityUpdate.vue')
const Profil = () => import('./views/Profil.vue')
const Security = () => import('./views/Security.vue')

const routes = [
  { path: '/', name: 'beranda', component: Beranda, meta: { judul: 'Dashboard' } },
  { path: '/server', name: 'server', component: Server, meta: { judul: 'Server' } },
  { path: '/server/monitoring', component: ServerMonitor, meta: { judul: 'Monitoring Server' } },
  { path: '/server/proteksi', component: ServerProteksi, meta: { judul: 'Proteksi Server' } },
  { path: '/server/antivirus', component: ServerAntivirus, meta: { judul: 'Antivirus Server' } },
  { path: '/server/waf', component: ServerWaf, meta: { judul: 'WAF Server' } },
  { path: '/server/bruteforce', component: ServerBruteforce, meta: { judul: 'Brute Force' } },
  { path: '/server/cms', component: ServerCms, meta: { judul: 'Kerentanan CMS' } },
  { path: '/server/cpguard', component: ServerCpguard, meta: { judul: 'Kesiapan Copot cPGuard' } },
  { path: '/security', component: Security, meta: { judul: 'Security' } },
  // Installer bersub-menu per jenis aplikasi; alamat lama /installer & /installer/susulan dialihkan
  { path: '/installer', redirect: '/installer/wordpress' },
  { path: '/installer/susulan', redirect: '/installer/wordpress/susulan' },
  { path: '/installer/wordpress', name: 'installer', component: Installer, meta: { judul: 'Installer WordPress' } },
  { path: '/installer/wordpress/susulan', component: Susulan, meta: { judul: 'Susulan aturan' } },
  { path: '/installer/laravel', component: InstallerLaravel, meta: { judul: 'Aplikasi Custom' } },
  { path: '/installer/laravel/:id(project-\\d+)', component: LaravelProyek, meta: { judul: 'Project Aplikasi Custom' } },
  { path: '/ai', component: AiModel, meta: { judul: 'AI Model' } },
  { path: '/token', component: Token, meta: { judul: 'Token Usage' } },
  { path: '/paket', component: Paket, meta: { judul: 'Paket' } },
  { path: '/projects', component: Projects, meta: { judul: 'Project Lokal' } },
  { path: '/tutorial', component: Tutorial, meta: { judul: 'Statistik Tutorial' } },
  { path: '/berkas', component: Berkas, meta: { judul: 'File Manager' } },
  { path: '/pc-backup', redirect: '/pc-backup/status' },
  { path: '/pc-backup/status', component: PcBackup, meta: { judul: 'Status Backup' } },
  { path: '/pc-backup/berkas', component: Berkas, meta: { judul: 'File Manager PC Backup' } },
  { path: '/report', component: Report, meta: { judul: 'Report Harian' } },
  { path: '/notif-email', component: NotifEmail, meta: { judul: 'Notif Email' } },
  { path: '/brain', component: Brain, meta: { judul: 'Claude Brain' } },
  // Sengaja tidak ada di menu (NAV App.vue): dibuka lewat alamat langsung
  { path: '/velocity-update', component: VelocityUpdate, meta: { judul: 'Velocity Update' } },
  { path: '/profil', component: Profil, meta: { judul: 'Profil' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

// Ganti tab/saringan (path sama, hanya ?query berubah) → posisi gulir tetap; Kembali/Maju → posisi lama; halaman lain → atas.
const gulir = (to, from, simpan) => simpan || (to.path === from.path ? false : { top: 0 })
const router = createRouter({ history: createWebHistory(import.meta.env.BASE_URL), routes, scrollBehavior: gulir })
// Sesudah deploy, potongan JS lama sudah terhapus → muat ulang sekali ke alamat tujuan
router.onError((e, to) => {
  if (/dynamically imported module|Importing a module script failed|Failed to fetch/i.test(e?.message || '')) window.location.assign(to.fullPath)
})
router.afterEach((to) => { document.title = `${to.meta.judul || 'Dashboard'} | Local PC Velocity` })

// Dibuka dari LAN/Tailscale → pindah ke halaman yang sama di dash.velocity.ai.id supaya login (Masuk dengan VD.net)
// dan nama pelaku berlaku. Bila dash tak terjangkau (internet/tunnel mati) tetap di LAN. ?lan=1 = tetap di LAN untuk tab ini
// (mis. unggah berkas >100 MB yang ditolak Cloudflare).
const DASH = 'dash.velocity.ai.id'
async function keDash() {
  if (location.hostname === DASH) return false
  try {
    if (new URLSearchParams(location.search).has('lan')) sessionStorage.setItem('tetap-lan', '1')
    if (sessionStorage.getItem('tetap-lan')) return false
  } catch { /* penyimpanan diblokir: tetap coba pindah */ }
  try {
    await fetch(`https://${DASH}/__login`, { mode: 'no-cors', cache: 'no-store', signal: AbortSignal.timeout(2500) })
  } catch {
    return false
  }
  location.replace(`https://${DASH}${location.pathname}${location.search}${location.hash}`)
  return true
}

keDash().then((pindah) => { if (!pindah) createApp(App).use(router).mount('#app') })
