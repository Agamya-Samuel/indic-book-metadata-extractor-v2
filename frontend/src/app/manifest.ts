import type { MetadataRoute } from "next";
import {
  SITE_DESCRIPTION,
  SITE_NAME,
  SITE_SHORT_NAME,
} from "@/lib/site";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SITE_NAME,
    short_name: SITE_SHORT_NAME,
    description: SITE_DESCRIPTION,
    id: "/",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#204569",
    lang: "en-IN",
    dir: "ltr",
    categories: ["education", "productivity", "research"],
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
    ],
  };
}
