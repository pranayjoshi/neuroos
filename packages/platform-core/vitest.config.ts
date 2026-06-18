import { defineConfig } from "vitest/config";
import { resolve } from "node:path";

export default defineConfig({
  test: {
    globals: false,
    environment: "node",
    testTimeout: 20000,
    hookTimeout: 10000,
    alias: {
      "@neuroos/shared-contracts/schema": resolve(
        __dirname,
        "../../jobs/00_shared_contracts/schema/index.ts"
      ),
      "@neuroos/shared-contracts/constants": resolve(
        __dirname,
        "../../jobs/00_shared_contracts/constants/index.ts"
      ),
    },
  },
});
