import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['src/**/*.test.ts', 'src/**/*.spec.ts', 'src/**/__tests__/*', 'electron/**/*.test.ts'],
    alias: {
      '@': resolve(__dirname, './src'),
      '@main': resolve(__dirname, './electron/main')
    }
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
      '@main': resolve(__dirname, './electron/main')
    }
  }
})
