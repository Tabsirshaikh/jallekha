import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Every API route group, so the dev server forwards them to the FastAPI app (uvicorn on 8000).
    proxy: {
      "/auth": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/intake": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/atlas": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/equity": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/underserved": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/coverage": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/forecast": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/shortage": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/plans": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/explain": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/contests": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/deliveries": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/stops": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/wards": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/impact": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ledger": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/notices": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
