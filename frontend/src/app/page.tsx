import Image from "next/image";
import { LinkButton } from "@/components/shared/button";

export default function Home() {
  return (
    <div className="relative isolate flex min-h-[calc(100dvh-var(--nav-height))] items-center justify-center overflow-hidden px-4 py-8 sm:py-10">
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
            className="font-display text-[1.75rem] leading-none text-[var(--accent)]"
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
        <h1 className="text-balance font-display text-[var(--text-3xl)] font-semibold tracking-tight text-[var(--text)] sm:text-6xl leading-[1.05] animate-hero animate-hero-2">
          A working tool for
          <br className="hidden sm:block" />{" "}
          <em className="font-display italic font-medium text-[var(--accent)]">
            Indic book
          </em>{" "}
          digitization.
        </h1>

        <p className="mx-auto mt-7 max-w-xl text-pretty text-[var(--text-base)] sm:text-[var(--text-md)] text-[var(--text-muted)] animate-hero animate-hero-3">
          Upload scanned book pages, run OCR and a fine-tuned language model,
          review the extracted bibliographic metadata, then export to Wikibase
          or OpenRefine.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row animate-hero animate-hero-4">
          <LinkButton href="/upload" size="lg">Start an upload</LinkButton>
          <LinkButton href="/library" size="lg" variant="outline">
            Browse the library
          </LinkButton>
        </div>

        <dl className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-px overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--border)] sm:grid-cols-3 animate-hero animate-hero-5">
          {[
            { k: "OCR", v: "Tesseract 5 + Indic scripts" },
            { k: "LLM", v: "Airavata 7B" },
            { k: "Export", v: "Wikibase · OpenRefine" },
          ].map((item) => (
            <div
              key={item.k}
              className="flex flex-col gap-1 bg-[var(--surface)] px-5 py-4 text-left"
            >
              <dt className="text-[10px] uppercase tracking-[0.14em] text-[var(--text-muted)]">
                {item.k}
              </dt>
              <dd className="text-[var(--text-sm)] font-medium text-[var(--text)]">
                {item.v}
              </dd>
            </div>
          ))}
        </dl>

        {/* OKI attribution — placed below the stat strip as a quiet credit
            rather than a sponsor banner. The 9-unit margin matches the
            macro-breath rhythm used between hero sections. Logo width
            144px keeps the visual weight below the H1 (the H1 is the
            dominant element, the attribution is supporting evidence). */}
        <div className="mt-12 flex flex-col items-center gap-4 animate-fade-in">
          <p className="max-w-md text-[var(--text-sm)] leading-relaxed text-[var(--text-muted)]">
            Developed under the Guidance, Mentorship, and Support of{" "}
            <span className="font-medium text-[var(--text)]">
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
        </div>
      </div>
    </div>
  );
}
