/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    serverComponentsExternalPackages: ["@aws-sdk/client-bedrock-agent-runtime"],
  },
  webpack: (config, { isServer }) => {
    if (isServer) {
      config.externals.push({
        "@aws-sdk/client-bedrock-agent-runtime":
          "commonjs @aws-sdk/client-bedrock-agent-runtime",
      });
    }
    return config;
  },
};

export default nextConfig;
