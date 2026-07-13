import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

const certsDir = resolve(__dirname, '../backend/certs')
const keyPath = resolve(certsDir, 'key.pem')
const certPath = resolve(certsDir, 'cert.pem')
// dev server 才需要 HTTPS；证书不存在时（如 Docker 构建环境）跳过，不影响 vite build
const https =
  existsSync(keyPath) && existsSync(certPath)
    ? { key: readFileSync(keyPath), cert: readFileSync(certPath) }
    : undefined

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5174,
    ...(https ? { https } : {}),
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
