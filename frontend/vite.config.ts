import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Minimal typing to avoid adding @types/node for a single env override.
declare const process: { env: Record<string, string | undefined> }
const backendTarget = process.env.VITE_BACKEND_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173, proxy: { '/api': { target: backendTarget, changeOrigin: true } } },
  preview: { host: true, port: 4173 },
})
