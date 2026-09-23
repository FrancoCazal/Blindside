import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    // Puerto fijo y sin fallback: el allowlist de CORS de la API nombra este
    // origen, así que si Vite se moviera de puerto el navegador empezaría a
    // bloquear las respuestas y parecería una falla de la API.
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  preview: { host: "127.0.0.1", port: 4173, strictPort: true },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    setupFiles: ["src/test-setup.ts"],
  },
});
