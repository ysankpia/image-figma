import { resolve } from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@image-figma/dsl-schema": resolve(__dirname, "../dsl-schema/src/index.ts")
    }
  }
});
