import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 900 },
  server: { proxy: { "/api": "http://localhost:8000", "/docs": "http://localhost:8000", "/openapi.json": "http://localhost:8000" } },
});
