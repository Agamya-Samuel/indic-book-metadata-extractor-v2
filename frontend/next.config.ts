import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",

  // Ensure the New Relic agent files are included in standalone output traces.
  // The agent loads ~74 files via Node subpath-imports that @vercel/nft
  // cannot statically resolve, which causes "Cannot find module" in production.
  outputFileTracingIncludes: {
    "/*": [
      "./node_modules/newrelic/**/*",
      "./node_modules/meriyah/**/*",
    ],
  },
  // Treat newrelic and meriyah as external packages (not bundled by webpack/turbopack).
  serverExternalPackages: ["newrelic", "meriyah"],
};

export default nextConfig;
