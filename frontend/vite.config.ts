import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const certsDir = resolve(__dirname, '../backend/certs')

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5174,
    https: {
      key: readFileSync(resolve(certsDir, 'key.pem')),
      cert: readFileSync(resolve(certsDir, 'cert.pem')),
    },
    proxy: {
      '/api': {
        target: 'https://localhost:8000',
        changeOrigin: true,
        secure: false,  // accept self-signed cert for local dev
        // SSE streaming: disable compression so http-proxy forwards chunks immediately
        configure: (proxy: any) => {
          proxy.on('proxyRes', (proxyRes: any) => {
            // Remove compression — without it, the proxy buffers until decompression finishes
            delete proxyRes.headers['content-encoding']
          })
        },
      },
    },
  },
})
