/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Docker Desktop bind mounts on Windows/macOS don't deliver file-change
    // events into the container, so HMR needs polling there.
    watch: process.env.VITE_USE_POLLING === "true" ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      "/api": {
        target: process.env.API_PROXY_TARGET ?? "http://api:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    server: {
      deps: {
        // Ships ESM with extensionless internal imports, which Node's strict
        // resolver rejects; Vite's resolver (dev/build) handles them fine.
        inline: ["@material/material-color-utilities"],
      },
    },
  },
});
