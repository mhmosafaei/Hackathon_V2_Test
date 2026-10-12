import { defineConfig } from 'vite';
export default defineConfig({server: {proxy: {'/api': 'http://127.0.0.1:8530'}}, test: {environment: 'jsdom', setupFiles: './src/test-setup.js', pool: 'threads', maxWorkers: 1, minWorkers: 1, testTimeout: 10000}});
