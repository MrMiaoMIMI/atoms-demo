import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    // Preview iframes have an opaque origin ("null"); the dev server must
    // answer CORS preflights for them too.
    cors: { origin: "*" },
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/apps": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
