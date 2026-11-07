import path from "path";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react() as never],   // vitest ships its own copy of vite, so the plugin types differ
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  test: { environment: "jsdom" },
});
