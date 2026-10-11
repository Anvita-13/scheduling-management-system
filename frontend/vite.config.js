import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.VITE_BACKEND_URL || 'http://localhost:8000'
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      // The dev server forwards /api to FastAPI, so the browser sees a single origin (no CORS needed).
      proxy: { '/api': { target: backend, changeOrigin: true } },
    },
  }
})
