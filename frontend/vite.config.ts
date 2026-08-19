import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Tailwind v4 se integra como plugin de Vite: ya no hay tailwind.config.js
// ni postcss.config.js. Los tokens viven en src/index.css.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // import.meta.dirname: __dirname no está soportado por el configLoader
      // nativo que Vite hará default en una versión mayor futura.
      '@': new URL('./src', import.meta.url).pathname,
    },
  },
  server: {
    port: 5173,
    // En producción el SPA y la API comparten origen (rewrite de Render).
    // Este proxy reproduce esa condición en local, así que el código del cliente
    // usa siempre rutas relativas y CORS nunca entra en juego.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8010', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8010', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
