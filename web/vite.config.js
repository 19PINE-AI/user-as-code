import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Deployed under https://ring0.me/research/user-as-code/ — absolute base makes
// asset + data URLs robust regardless of trailing slash.
export default defineConfig({
  plugins: [react()],
  base: '/research/user-as-code/',
})
