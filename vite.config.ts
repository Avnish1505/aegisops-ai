import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // MapLibre 6 loads its worker with new URL('./maplibre-gl-worker.mjs', import.meta.url);
  // pre-bundling moves the module and breaks that path.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['src/test/setup.ts'],
  },
})
