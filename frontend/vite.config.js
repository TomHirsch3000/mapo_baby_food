import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  // Relative asset URLs, so the same build works at a domain root and under a
  // path like /mapo_baby_food/ on GitHub Pages. The app's own data fetches are
  // already relative ('./claims/...'), which resolve against the document URL
  // and land in the right place either way.
  base: './',
  plugins: [react()],
  server: {
    port: 3000,
  },
});
