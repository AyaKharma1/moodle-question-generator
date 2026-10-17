import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// The frontend talks to the backend via /api. In development, Vite proxies
// /api to the FastAPI server so there are no CORS surprises.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
