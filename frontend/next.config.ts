import type { NextConfig } from "next";

// Keep frame-ancestors only: a full script-src policy needs testing against
// Next's inline bootstrap and would risk breaking the app untested.
const SECURITY_HEADERS = [
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,

  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },

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
