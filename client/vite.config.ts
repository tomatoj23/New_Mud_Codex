import { defineConfig } from "vite";
import uniPlugin from "@dcloudio/vite-plugin-uni";

const uni =
  (uniPlugin as unknown as { default?: typeof uniPlugin }).default ?? uniPlugin;

export default defineConfig({
  plugins: [uni()],
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  test: {
    include: ["tests/**/*.test.ts"],
  },
});
