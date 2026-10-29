import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/**
 * Component and unit tests.
 *
 * Deliberately not end-to-end: these run with no servers, no database and no
 * network, so they can run on every push without infrastructure. They cover
 * the pieces where a regression would be silent -- the provenance labelling,
 * the ARIA tab wiring, and the API client's request shape.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    // The production build is the type check; tests should not duplicate it.
    typecheck: { enabled: false },
  },
});
