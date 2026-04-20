import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: process.env.PORTAL_UI_BASE || '/portal/',
  build: {
    outDir: '../frontend/portal',
    emptyOutDir: true
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  plugins: [vue()],
  test: {
    include: ['tests/unit/**/*.spec.ts'],
    globals: true,
    environment: 'jsdom'
  }
})
