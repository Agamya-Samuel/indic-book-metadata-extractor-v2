import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/admin",
          "/dashboard",
          "/books",
          "/upload",
          "/notifications",
          "/pending-approval",
          "/verify-email",
          "/forgot-password",
          "/reset-password",
          "/api",
        ],
      },
    ],
    sitemap: new URL("/sitemap.xml", SITE_URL).toString(),
    host: SITE_URL.origin,
  };
}
