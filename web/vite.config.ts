import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  // the Harness panel talks to the local control server (scripts/start.sh) through this proxy, so the browser only ever sees one origin
  server: { proxy: { "/harness-api": { target: "http://127.0.0.1:8765", rewrite: (p) => p.replace(/^\/harness-api/, "/api") } } },
});
