import Image from "next/image";
import type { Metadata } from "next";
import { LinkButton } from "@/components/shared/button";
import { SITE_DESCRIPTION, SITE_NAME, SITE_OPEN_GRAPH, SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
  openGraph: { ...SITE_OPEN_GRAPH, url: "/" },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${SITE_URL.origin}/#organization`,
      name: "Open Knowledge Initiatives (OKI), IIIT Hyderabad",
    },
    {
      "@type": "WebSite",
      "@id": `${SITE_URL.origin}/#website`,
      url: SITE_URL.origin,
      name: SITE_NAME,
      description: SITE_DESCRIPTION,
      inLanguage: "en-IN",
      publisher: { "@id": `${SITE_URL.origin}/#organization` },
    },
    {
      "@type": "WebApplication",
      name: SITE_NAME,
      url: SITE_URL.origin,
      description: SITE_DESCRIPTION,
      applicationCategory: "ResearchApplication",
      operatingSystem: "Web",
      inLanguage: "en-IN",
      isAccessibleForFree: true,
      publisher: { "@id": `${SITE_URL.origin}/#organization` },
    },
  ],
};

export default function Home() {
  const services = [
    { href: process.env.NEXT_PUBLIC_WIKIBASE_URL, title: "Wikibase", desc: "Browse the published catalogue" },
    { href: process.env.NEXT_PUBLIC_OPENREFINE_URL, title: "OpenRefine", desc: "Clean and reconcile metadata" },
    { href: process.env.NEXT_PUBLIC_QUICKSTATEMENTS_URL, title: "QuickStatements", desc: "Batch-edit items" },
  ].filter((s): s is { href: string; title: string; desc: string } => Boolean(s.href));

  return (
    <div className="relative isolate flex min-h-[calc(100dvh-var(--nav-height))] items-center justify-center overflow-hidden px-4 py-8 sm:py-10">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c"),
        }}
      />
      <div
        aria-hidden="true"
        className="paper-grid absolute inset-0 -z-10 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]"
      />

      <div className="mx-auto w-full max-w-3xl text-center">
        {/* The eyebrow: a quiet stamp in the display face. The ಇ brand
            mark re-anchors the visual identity on the hero (it only appears
            in the nav below this). The label is the same proof the original
            carried — "Indic script OCR + LLM" — set in tracked caps. */}
        <div className="mb-8 inline-flex items-center gap-2.5 text-[var(--text-muted)] animate-hero animate-hero-1">
          <span
            aria-hidden="true"
            className="font-display text-[1.75rem] leading-none text-[var(--accent-text)]"
          >
            ಇ
          </span>
          <span
            aria-hidden="true"
            className="h-3 w-px bg-[var(--border)]"
          />
          <span className="text-[11px] uppercase tracking-[0.18em]">
            Indic script OCR + LLM
          </span>
        </div>

        {/* Display serif: the scholarly voice. Italic accent word reads as
            a typographic emphasis rather than a color-coded highlight. */}
        <h1 className="text-balance font-display text-[length:var(--text-3xl)] font-semibold tracking-tight text-[var(--text)] sm:text-6xl leading-[1.05] animate-hero animate-hero-2">
          A working tool for
          <br className="hidden sm:block" />{" "}
          <em className="font-display italic font-medium text-[var(--accent-text)]">
            Indic book
          </em>{" "}
          digitization.
        </h1>

        <p className="mx-auto mt-7 max-w-xl text-pretty text-[length:var(--text-base)] sm:text-[length:var(--text-md)] text-[var(--text-muted)] animate-hero animate-hero-3">
          Upload scanned book pages, run OCR and a fine-tuned language model,
          review the extracted bibliographic metadata, then export to Wikibase
          or OpenRefine.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row animate-hero animate-hero-4">
          <LinkButton href="/upload" size="lg">Start an upload</LinkButton>
          <LinkButton href="/login" size="lg" variant="outline">
            Log in
          </LinkButton>
        </div>

        <dl className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-px overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--border)] sm:grid-cols-3 animate-hero animate-hero-5">
          {[
            { k: "OCR", v: "Tesseract 5 + Indic scripts" },
            { k: "LLM", v: "Local LLM" },
            { k: "Export", v: "Wikibase · OpenRefine" },
          ].map((item) => (
            <div
              key={item.k}
              className="flex flex-col gap-1 bg-[var(--surface)] px-5 py-4 text-left"
            >
              <dt className="text-[10px] uppercase tracking-[0.14em] text-[var(--text-muted)]">
                {item.k}
              </dt>
              <dd className="text-[length:var(--text-sm)] font-medium text-[var(--text)]">
                {item.v}
              </dd>
            </div>
          ))}
        </dl>

        {services.length > 0 && (
          <section className="mt-14 animate-fade-in" aria-labelledby="services-heading">
            <h2
              id="services-heading"
              className="text-[11px] uppercase tracking-[0.18em] text-[var(--text-muted)]"
            >
              Open data services
            </h2>
            <ul className="mt-4 grid grid-cols-1 gap-3 text-left sm:grid-cols-3">
              {services.map((service) => (
                <li key={service.title}>
                  <a
                    href={service.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex h-full flex-col gap-1 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] px-5 py-4 transition-colors hover:border-[var(--accent-soft-text)]"
                  >
                    <span className="text-[length:var(--text-sm)] font-medium text-[var(--text)]">
                      {service.title}{" "}
                      <span aria-hidden="true" className="text-[var(--accent-text)]">↗</span>
                    </span>
                    <span className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
                      {service.desc}
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Honest expectations: Telugu is the accuracy ceiling today, and the
            review step is part of the product, not an optional extra. */}
        <p className="mx-auto mt-6 max-w-xl text-pretty text-[length:var(--text-sm)] leading-relaxed text-[var(--text-muted)] animate-fade-in">
          Telugu OCR is the accuracy ceiling — the Telugu line model measures
          ≈ 0.16 median character error (Tesseract ≈ 0.40), versus ≈ 0.07 for
          Hindi — so the OCR review step is part of the workflow. Hindi stays
          on Tesseract.
        </p>

        {/* OKI attribution — placed below the stat strip as a quiet credit
            rather than a sponsor banner. The 9-unit margin matches the
            macro-breath rhythm used between hero sections. Logo width
            144px keeps the visual weight below the H1 (the H1 is the
            dominant element, the attribution is supporting evidence). */}
        <div className="mt-12 flex flex-col items-center gap-4 animate-fade-in">
          <p className="max-w-md text-[length:var(--text-sm)] leading-relaxed text-[var(--text-muted)]">
            Developed under the Guidance, Mentorship, and Support of{" "}
            <span className="font-medium text-[var(--text)]">
              <br />
              Open Knowledge Initiatives (OKI)
            </span>
            , IIIT Hyderabad.
          </p>
          <Image
            src="/Open_Knowledge_Initiatives_logo.png"
            alt="Open Knowledge Initiatives (OKI), IIIT Hyderabad"
            width={144}
            height={78}
            className="h-auto w-[120px] sm:w-[144px] opacity-80"
            priority={false}
          />
          <a
            href="https://github.com/Agamya-Samuel/indic-book-metadata-extractor-v2"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[length:var(--text-sm)] font-medium text-[var(--accent-text)] hover:underline"
          >
            Source code on GitHub{" "}
            <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    </div>
  );
}
