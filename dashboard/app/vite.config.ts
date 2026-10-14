/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Relative asset URLs let the built site work from any host or sub-path (e.g. GitHub Pages).
  base: './',
  test: {
    include: ['src/**/*.test.ts', 'scripts/**/*.test.mjs'],
  },
});
