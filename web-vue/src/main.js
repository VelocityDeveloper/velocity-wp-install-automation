import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Beranda from './views/Beranda.vue'
import Server from './views/Server.vue'
import Installer from './views/Installer.vue'
import Susulan from './views/Susulan.vue'
import InstallerLaravel from './views/InstallerLaravel.vue'
import LaravelProyek from './views/LaravelProyek.vue'
import Brain from './views/Brain.vue'
import Paket from './views/Paket.vue'
import AiModel from './views/AiModel.vue'
import Token from './views/Token.vue'
import Projects from './views/Projects.vue'
import Tutorial from './views/Tutorial.vue'
import NotifEmail from './views/NotifEmail.vue'
import Report from './views/Report.vue'
import Berkas from './views/Berkas.vue'
import VelocityUpdate from './views/VelocityUpdate.vue'
import Security from './views/Security.vue'
import './style.css'

const routes = [
  { path: '/', name: 'beranda', component: Beranda, meta: { judul: 'Dashboard' } },
  { path: '/server', name: 'server', component: Server, meta: { judul: 'Server' } },
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
  { path: '/report', component: Report, meta: { judul: 'Report Harian' } },
  { path: '/notif-email', component: NotifEmail, meta: { judul: 'Notif Email' } },
  { path: '/brain', component: Brain, meta: { judul: 'Claude Brain' } },
  // Sengaja tidak ada di menu (NAV App.vue): dibuka lewat alamat langsung
  { path: '/velocity-update', component: VelocityUpdate, meta: { judul: 'Velocity Update' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

// Ganti tab/saringan (path sama, hanya ?query berubah) → posisi gulir tetap; Kembali/Maju → posisi lama; halaman lain → atas.
const gulir = (to, from, simpan) => simpan || (to.path === from.path ? false : { top: 0 })
const router = createRouter({ history: createWebHistory(import.meta.env.BASE_URL), routes, scrollBehavior: gulir })
router.afterEach((to) => { document.title = `${to.meta.judul || 'Dashboard'} | Local PC Velocity` })

createApp(App).use(router).mount('#app')
