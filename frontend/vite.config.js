import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // /api ile başlayan istekler FastAPI'ye gider; böylece CORS ayarı gerekmez
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
