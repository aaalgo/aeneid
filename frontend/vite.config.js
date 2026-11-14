import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  base: '/static/',
  build: { outDir: '../static', emptyOutDir: true },
  server: { proxy: { '/api': 'http://127.0.0.1:5000' } },
});
