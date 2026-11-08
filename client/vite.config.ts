import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// The FastAPI backend (uvicorn backend.api.main:app --port 8000) is proxied in dev,
// so the browser calls same-origin /auth and /api routes.
const backend = process.env.WAYPOINT_API_URL ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/auth': backend,
      '/api': backend,
    },
  },
})
