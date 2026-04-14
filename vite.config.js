import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  base: command === 'serve' ? '/' : './',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    hmr: {
      overlay: false
    },
    fs: {
      // 限制 Vite 只允许访问项目根目录以内的文件
      strict: false
    }
  },
  // 排除非源码目录，防止 Vite 依赖扫描器扫描到无关的 HTML 文件
  // (如 resources/python/Lib/site-packages 中的 pygame、win32com 文档等)
  build: {
    rollupOptions: {
      external: []
    }
  },
  optimizeDeps: {
    // 排除会被扫描到的非源码目录中的内容
    entries: ['index.html', 'src/**/*.{vue,ts,js,tsx,jsx}'],
    force: true,
    include: [
      'vue',
      'vue-router',
      'echarts',
      'marked',
      'dompurify',
      'three',
      'three/addons/controls/OrbitControls.js',
      'axios',
      'dayjs',
      'highlight.js',
      'lucide-vue-next',
      'qrcode.vue'
    ]
  }
}))
