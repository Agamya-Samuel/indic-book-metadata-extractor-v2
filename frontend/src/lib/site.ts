export const SITE_NAME = "Indic Book Metadata Extractor";
export const SITE_SHORT_NAME = "Indic Books";
export const SITE_DESCRIPTION =
  "OCR, local LLM extraction, and metadata review for Indic-script books. Upload scanned pages, curate bibliographic fields, and export records to Wikibase or OpenRefine.";
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
