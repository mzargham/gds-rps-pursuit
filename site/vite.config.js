import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  base: './',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        formal: resolve(__dirname, 'formal.html'),
        stats: resolve(__dirname, 'stats.html'),
      },
    },
  },
});
