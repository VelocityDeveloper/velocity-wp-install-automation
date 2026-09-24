import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Beranda from './views/Beranda.vue'
import Server from './views/Server.vue'
import Installer from './views/Installer.vue'
import Susulan from './views/Susulan.vue'
import Brain from './views/Brain.vue'
import Paket from './views/Paket.vue'
import AiModel from './views/AiModel.vue'
import Token from './views/Token.vue'
import Projects from './views/Projects.vue'
import './style.css'

const routes = [
  { path: '/', name: 'beranda', component: Beranda, meta: { judul: 'Dashboard' } },
  { path: '/server', name: 'server', component: Server, meta: { judul: 'Server' } },
  { path: '/installer', name: 'installer', component: Installer, meta: { judul: 'Installer' } },
  { path: '/installer/susulan', component: Susulan, meta: { judul: 'Susulan aturan' } },
  { path: '/ai', component: AiModel, meta: { judul: 'AI Model' } },
  { path: '/token', component: Token, meta: { judul: 'Token Usage' } },
  { path: '/paket', component: Paket, meta: { judul: 'Paket' } },
  { path: '/projects', component: Projects, meta: { judul: 'Project Lokal' } },
  { path: '/brain', component: Brain, meta: { judul: 'Claude Brain' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(import.meta.env.BASE_URL), routes, scrollBehavior: () => ({ top: 0 }) })
router.afterEach((to) => { document.title = `${to.meta.judul || 'Dashboard'} | Local PC Velocity` })

createApp(App).use(router).mount('#app')
