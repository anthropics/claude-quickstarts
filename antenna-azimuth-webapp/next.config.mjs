import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: fileURLToPath(new URL(".", import.meta.url)),
  eslint: {
    dirs: ["app", "components", "lib"],
  },
};

export default nextConfig;
