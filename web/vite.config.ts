import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Shore Memory 后端默认在 127.0.0.1:7811
const SHORE_API = process.env.SHORE_API || 'http://127.0.0.1:7811'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/health': SHORE_API,
      '/metrics': SHORE_API,
      '/v1': {
        target: SHORE_API,
        changeOrigin: true,
        ws: true
      }
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    target: 'es2022',
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        manualChunks: {
          graph: ['sigma', 'graphology', 'graphology-layout-forceatlas2', 'graphology-communities-louvain'],
          charts: ['uplot'],
          virtual: ['@tanstack/vue-virtual']
        }
      }
    }
  }
})
