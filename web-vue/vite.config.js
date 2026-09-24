import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Dashboard utama di / sejak 2026-09-24 (dashboard lama di /lama/). Aset di v2-assets/ karena
// /assets/ di nginx sudah milik Hermes & newvdnet.
export default defineConfig({
  base: '/',
  build: { assetsDir: 'v2-assets' },
  plugins: [vue()],
  server: {
    proxy: { '/api': 'http://127.0.0.1', '/brain': 'http://127.0.0.1' },
  },
})
