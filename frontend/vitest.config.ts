import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  // React 19's production build does not export `act`, but
  // @testing-library/react@16 requires it via `React.act`. Force the
  // development build for tests regardless of the shell's NODE_ENV.
  define: {
    "process.env.NODE_ENV": JSON.stringify("test"),
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    css: false,
    env: {
      NODE_ENV: "test",
    },
    alias: [
      {
        find: /^react-konva$/,
        replacement: path.resolve(__dirname, "./tests/__mocks__/react-konva.tsx"),
      },
    ],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
