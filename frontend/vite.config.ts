import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Optional: TASLEEM_PROXY=https://<stack> npm run dev serves this checkout against a running stack's /api, so
// a change can be tried (and the e2e tests run) before it is deployed. Unset, nothing is proxied.
const target = process.env.TASLEEM_PROXY;
// TASLEEM_LOCAL=1: proxy to services started from this checkout (core :8000, agent :8020), for testing a change
// end to end before it is deployed. See .claude/launch.json.
const local = process.env.TASLEEM_LOCAL
  ? Object.fromEntries([["core", 8000], ["agent", 8020], ["notifier", 8010], ["connector", 8030]].map(([svc, port]) => [
    `/api/${svc}`, { target: `http://127.0.0.1:${port}`, rewrite: (p: string) => p.replace(`/api/${svc}`, "") },
  ]))
  : undefined;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: local ?? (target ? { "/api": { target, changeOrigin: true, secure: true } } : undefined),
  },
  // TSL-179: the chart library loads lazily (see Landing and the lazy Programme route), which keeps every chunk
  // under the budget. Hand-written manualChunks were tried and removed: they created a circular chunk import
  // that broke React at load in the production build (caught on 20 Nov; the dev server never shows it).
  build: { chunkSizeWarningLimit: 500 },
  preview: { port: 4173, proxy: local ?? (target ? { "/api": { target, changeOrigin: true, secure: true } } : undefined) },
  test: { environment: "jsdom", globals: false },
} as never);
