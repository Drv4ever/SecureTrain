import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    host: 'localhost',
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/employee': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
      '/healthz': 'http://localhost:8000',
    },
  },
})
