import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy API + WS calls to the backend on :8765 so the token/localhost model is
// identical to production (where the backend serves the built assets itself).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8765", changeOrigin: true, ws: true },
      "/healthz": "http://127.0.0.1:8765",
    },
  },
  build: {
    outDir: "dist",
    // Bundle everything; no runtime CDN (REQUIREMENTS §2).
    rollupOptions: {},
  },
});
