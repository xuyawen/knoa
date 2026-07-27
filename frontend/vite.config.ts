import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// frontend2.0 dev server.
// Port 5175 to avoid collisions (5173 blocked, 5174 used by legacy frontend).
// Proxy /api to the backend (plain HTTP, no TLS) and strip
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
        target: 'http://localhost:8000',
        changeOrigin: true,
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
  // NOTE: hashed stale artifacts accumulate in dist/ — deployment must copy from
  // a clean build dir or clear the target before copying (see deploy scripts).
  build: {
    emptyOutDir: false,
    rollupOptions: {
      output: {
        // 手动分包：框架运行时与图标库与业务代码分离，
        // 业务迭代不再打爆 vendor 缓存；配合路由懒加载按页出包。
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          icons: ['lucide-vue-next'],
        },
      },
    },
  },
})
