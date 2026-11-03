import js from "@eslint/js";
import tseslint from "typescript-eslint";

/** Shared flat ESLint config for all @hrcore/* packages and apps. */
export const baseConfig = tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
  {
    ignores: ["dist/**", ".next/**", "node_modules/**", ".expo/**"],
  },
);

export default baseConfig;
