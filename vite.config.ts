import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig({
  server: {
    host: "::",
    port: 8080,
    proxy: {
      // Proxy all /api and /ws requests to the FastAPI backend
      // This lets both frontend + backend work through a single ngrok tunnel
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ready": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/docs": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  plugins: [
    react(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Split heavy third-party libs into their own chunks so the initial
        // load isn't one 2 MB blob. Route-level React.lazy (see App.tsx) then
        // pulls charts/map/3D only on the pages that use them.
        manualChunks: {
          "react-vendor": ["react", "react-dom", "react-router-dom"],
          charts: ["recharts"],
          three: ["three", "@react-three/fiber"],
          map: ["leaflet", "react-leaflet"],
          motion: ["framer-motion"],
        },
      },
    },
    chunkSizeWarningLimit: 900,
  },
});
