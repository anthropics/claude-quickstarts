import nextPlugin from "@next/eslint-plugin-next";
import { baseConfig } from "@hrcore/config";

export default [
  ...baseConfig,
  {
    plugins: { "@next/next": nextPlugin },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
    },
  },
  { ignores: [".next/**", "next-env.d.ts"] },
];
