import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// frontend2.0 dev server.
// Port 5175 to avoid collisions (5173 blocked, 5174 used by legacy frontend).
// Proxy /api to the backend (HTTPS self-signed -> secure:false) and strip
// content-encoding so SSE streams are not buffered (see project memory).
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5175,
    proxy: {
      '/api': {
        target: 'https://localhost:8000',
        changeOrigin: true,
        secure: false,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            delete (proxyRes.headers as Record<string, unknown>)['content-encoding']
          })
        },
      },
    },
  },
  // emptyOutDir disabled: the bundler's pre-delete uses trash which is blocked
  // by the workspace safe-delete layer on this volume; overwrite in place instead.
  build: {
    emptyOutDir: false,
  },
})
