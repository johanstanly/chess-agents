import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// `npm run build` writes the page into ../docs (the GitHub Pages site) as its front page:
// docs/index.html, its code in docs/landing/, and the files from public/ (video, icon).
// The rest of docs/ (results, replay, 3D pages, games) is left untouched.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: './',   // relative paths, so it works at johanstanly.github.io/chess-agents/
  build: {
    outDir: '../docs',
    emptyOutDir: false,
    assetsDir: 'landing',
  },
  server: { port: 5174, host: '127.0.0.1' },
})
