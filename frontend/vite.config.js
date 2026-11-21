import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The browser talks to /api on the same origin; Vite proxies it to the local
// FastAPI service so the app also works behind a preview tunnel without
// exposing port 8000.
//
// Extra hostnames (for example a cloud preview URL) come from the environment
// so no machine-specific hostname is committed to the repository.
const extraHosts = (process.env.BOTFORGE_ALLOWED_HOSTS || process.env.__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS || '')
  .split(',')
  .map((host) => host.trim())
  .filter(Boolean);

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    allowedHosts: extraHosts.length ? extraHosts : undefined,
    proxy: {
      '/api': {
        target: process.env.BOTFORGE_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
