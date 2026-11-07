import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // The backend's CORS setting expects this exact port, so fail rather than move.
  server: { port: 5173, strictPort: true },
});
