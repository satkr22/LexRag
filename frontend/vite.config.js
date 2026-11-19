import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

/* global process */
const apiProxyTarget = process.env.API_PROXY_TARGET || 'http://localhost:9000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/agent': apiProxyTarget,
      '/sessions': apiProxyTarget,
      '/users': apiProxyTarget,
    },
  },
})
