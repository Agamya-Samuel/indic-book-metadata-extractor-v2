import type { Metadata } from "next";

export const SITE_NAME = "Open Book Map";
export const SITE_TITLE =
  "Open Book Map — OCR and metadata for Indic books";
export const SITE_SHORT_NAME = "OpenBookMap";
export const SITE_DESCRIPTION =
  "Open Book Map turns scanned Indic-script books into structured records with OCR and a local LLM. Review the metadata, then export to Wikibase or OpenRefine.";
export const SITE_SOCIAL_DESCRIPTION =
  "Open Book Map: OCR and local LLM metadata extraction for Indic books, with review and export to Wikibase or OpenRefine.";
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

function resolveSiteUrl(): URL {
  const configured =
    process.env.NEXT_PUBLIC_SITE_URL ?? process.env.FRONTEND_URL;
  if (!configured) {
    throw new Error(
      "NEXT_PUBLIC_SITE_URL (or FRONTEND_URL) must be set to the public app origin",
    );
  }
  try {
    return new URL(configured);
  } catch {
    throw new Error(`Invalid app origin in NEXT_PUBLIC_SITE_URL: ${configured}`);
  }
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
