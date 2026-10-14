import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Forward the data API to `wrangler dev` (port 8787) so `npm run dev` needs no .env file.
    proxy: {
      '/activity.json': 'http://localhost:8787',
    },
  },
})
