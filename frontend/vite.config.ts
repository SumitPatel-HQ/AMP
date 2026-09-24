/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true,
  },
  preview: {
    port: 5173,
    host: true,
  },
  worker: {
    // MapLibre spawns its worker as an ES module.
    format: 'es',
  },
  build: {
    // The map engine (MapLibre + deck.gl) is its own lazily loaded chunk and
    // is expected to exceed Vite's default 500 kB warning on its own.
    chunkSizeWarningLimit: 2000,
  },
  test: {
    setupFiles: ['./src/test/setup.ts'],
  },
})
