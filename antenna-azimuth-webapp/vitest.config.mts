import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
  test: {
    // These are pure-math modules; nothing here needs a DOM.
    environment: "node",
    include: ["lib/**/*.test.ts"],
  },
});
