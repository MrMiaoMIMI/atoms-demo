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
    // Keep the original Host (127.0.0.1:5173) so backend-generated email
    // links point at the dev server, not at 127.0.0.1:8000.
    proxy: {
      "/api": { target: "http://127.0.0.1:8000" },
      "/apps": { target: "http://127.0.0.1:8000" },
      // Keep the trailing slash: "/s" would also match "/src/main.tsx" and
      // proxy the dev app's own modules to FastAPI.
      "/s/": { target: "http://127.0.0.1:8000" },
    },
  },
});
