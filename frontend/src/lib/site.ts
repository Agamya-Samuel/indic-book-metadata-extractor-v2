import type { Metadata } from "next";

export const SITE_NAME = "Indic Book Metadata Extractor";
export const SITE_TITLE =
  "Indic Book Metadata Extractor — OCR for Indic Scripts";
export const SITE_SHORT_NAME = "Indic Books";
export const SITE_DESCRIPTION =
  "Turn scanned Indic-script books into structured records with OCR and a local LLM. Review the extracted metadata, then export to Wikibase or OpenRefine.";
export const SITE_SOCIAL_DESCRIPTION =
  "OCR and local LLM metadata extraction for Indic-script books. Review and export to Wikibase or OpenRefine.";
export const SITE_LOCALE = "en_IN";
export const SITE_KEYWORDS = [
  "OCR",
  "Indic scripts",
  "Telugu",
  "Hindi",
  "Wikibase",
  "OpenRefine",
  "bibliographic metadata",
  "digital humanities",
  "library science",
];

const FALLBACK_SITE_URL = "http://localhost:3000";

function resolveSiteUrl(): URL {
  for (const candidate of [
    process.env.NEXT_PUBLIC_SITE_URL,
    process.env.FRONTEND_URL,
  ]) {
    if (!candidate) continue;
    try {
      return new URL(candidate);
    } catch {
      continue;
    }
  }
  return new URL(FALLBACK_SITE_URL);
}

export const SITE_URL = resolveSiteUrl();

type OpenGraph = NonNullable<Metadata["openGraph"]>;

export const SITE_OPEN_GRAPH: OpenGraph = {
  type: "website",
  locale: SITE_LOCALE,
  siteName: SITE_NAME,
  title: SITE_TITLE,
  description: SITE_SOCIAL_DESCRIPTION,
};
