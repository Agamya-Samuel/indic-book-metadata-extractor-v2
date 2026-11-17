import type { NextConfig } from "next";

// `npm run build` passes --webpack deliberately. Turbopack's next/font/google
// loader intermittently fails in CI with
//   "next/font/google queries have exactly one entry"
// while resolving Noto Serif (multiple weights plus italic). The webpack font
// pipeline handles the same configuration deterministically. `next dev` still
// uses Turbopack, so local DX is unchanged.

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

// Prerendered pages are otherwise served with `s-maxage=31536000`, which lets
// the CDN keep a stale HTML document (and its old hashed chunks) for a year
// after a deploy. Revalidate page documents; hashed assets stay immutable.
const PAGE_CACHE_HEADERS = [
  { key: "Cache-Control", value: "public, max-age=0, must-revalidate" },
];

const STATIC_ASSET_PATTERN =
  "_next/static|_next/image|favicon.ico|icon.svg|apple-icon.png|"
  + "opengraph-image|twitter-image|manifest.webmanifest|robots.txt|sitemap.xml";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,

  async headers() {
    return [
      { source: "/:path*", headers: SECURITY_HEADERS },
      {
        source: `/((?!${STATIC_ASSET_PATTERN}).*)`,
        headers: PAGE_CACHE_HEADERS,
      },
    ];
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
