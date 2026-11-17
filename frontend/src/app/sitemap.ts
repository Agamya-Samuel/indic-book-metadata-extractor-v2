import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  return [
    {
      url: new URL("/", SITE_URL).toString(),
      lastModified,
      changeFrequency: "monthly",
      priority: 1,
    },
    {
      url: new URL("/login", SITE_URL).toString(),
      lastModified,
      changeFrequency: "yearly",
      priority: 0.5,
    },
    {
      url: new URL("/register", SITE_URL).toString(),
      lastModified,
      changeFrequency: "yearly",
      priority: 0.5,
    },
  ];
}
