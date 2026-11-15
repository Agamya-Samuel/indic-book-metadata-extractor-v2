import { describe, it, expect } from "vitest";
import {
  buildCorpus,
  clampPageNumber,
  findMatches,
  findValueHints,
  pageNumberFromParam,
  searchCorpus,
  segmentText,
  type OcrCorpusPage,
} from "@/lib/ocr-corpus";
import type { PageResponse } from "@/lib/api";

function page(
  pageNumber: number,
  ocrText: string | null,
  confidence: number | null = 90,
): PageResponse {
  return {
    id: `page-${pageNumber}`,
    page_number: pageNumber,
    image_path: null,
    preprocessing_config: null,
    image_url: `/api/pages/${pageNumber}/image`,
    ocr_text: ocrText,
    ocr_confidence: confidence,
  };
}

function corpusPage(pageNumber: number, text: string): OcrCorpusPage {
  return {
    id: `page-${pageNumber}`,
    pageNumber,
    text,
    confidence: 90,
    imageUrl: null,
  };
}

describe("buildCorpus", () => {
  it("maps and sorts pages by page number", () => {
    const corpus = buildCorpus([
      page(3, "third"),
      page(1, "first"),
      page(2, null, null),
    ]);

    expect(corpus.map((p) => p.pageNumber)).toEqual([1, 2, 3]);
    expect(corpus[2].text).toBe("third");
    expect(corpus[1].text).toBe("");
    expect(corpus[1].confidence).toBeNull();
    expect(corpus[0].imageUrl).toBe("/api/pages/1/image");
  });
});

describe("findMatches", () => {
  it("finds repeated Latin matches at exact offsets", () => {
    const matches = findMatches("The title and the title again", "title");
    expect(matches).toEqual([
      { start: 4, end: 9 },
      { start: 18, end: 23 },
    ]);
  });

  it("is case-insensitive", () => {
    expect(findMatches("TELUGU title", "telugu")).toEqual([
      { start: 0, end: 6 },
    ]);
  });

  it("finds Telugu text", () => {
    const text = "గ్రంథం పేరు: ఆంధ్ర మహాభారతం";
    const matches = findMatches(text, "మహాభారతం");
    expect(matches).toHaveLength(1);
    expect(text.slice(matches[0].start, matches[0].end)).toBe("మహాభారతం");
  });

  it("returns nothing for empty or absent queries", () => {
    expect(findMatches("some text", "")).toEqual([]);
    expect(findMatches("some text", "   ")).toEqual([]);
    expect(findMatches("some text", "missing")).toEqual([]);
  });
});

describe("searchCorpus", () => {
  it("groups matches by page and counts totals", () => {
    const search = searchCorpus(
      [
        corpusPage(1, "title one, title two"),
        corpusPage(2, "nothing here"),
        corpusPage(3, "Title three"),
      ],
      "title",
    );

    expect(search.results.map((r) => r.pageNumber)).toEqual([1, 3]);
    expect(search.results[0].matches).toHaveLength(2);
    expect(search.totalMatches).toBe(3);
    expect(search.totalPages).toBe(2);
    expect(search.truncated).toBe(false);
  });

  it("caps the page list while still counting every match", () => {
    const corpus = Array.from({ length: 60 }, (_, i) =>
      corpusPage(i + 1, "hit hit"),
    );
    const search = searchCorpus(corpus, "hit", 50);

    expect(search.results).toHaveLength(50);
    expect(search.totalPages).toBe(60);
    expect(search.totalMatches).toBe(120);
    expect(search.truncated).toBe(true);
  });

  it("returns an empty search for a blank query", () => {
    expect(searchCorpus([corpusPage(1, "text")], " ")).toEqual({
      results: [],
      totalPages: 0,
      totalMatches: 0,
      truncated: false,
    });
  });
});

describe("segmentText", () => {
  it("splits text into plain and matched segments", () => {
    const text = "before MATCH after";
    const segments = segmentText(text, findMatches(text, "match"));
    expect(segments).toEqual([
      { text: "before ", match: false },
      { text: "MATCH", match: true },
      { text: " after", match: false },
    ]);
  });

  it("handles adjacent matches without dropping text", () => {
    const text = "abab";
    const segments = segmentText(text, findMatches(text, "ab"));
    expect(segments.map((s) => s.text).join("")).toBe(text);
    expect(segments.filter((s) => s.match)).toHaveLength(2);
  });

  it("returns the whole text when there are no matches", () => {
    expect(segmentText("plain", [])).toEqual([
      { text: "plain", match: false },
    ]);
  });

  it("returns nothing for empty text", () => {
    expect(segmentText("", [])).toEqual([]);
  });
});

describe("findValueHints", () => {
  it("lists pages that contain the value, up to the limit", () => {
    const hints = findValueHints(
      [
        corpusPage(1, "no mention"),
        corpusPage(2, "Andhra Mahabharata"),
        corpusPage(3, "andhra mahabharata again"),
      ],
      "Andhra Mahabharata",
    );
    expect(hints).toEqual([2, 3]);
  });

  it("ignores values shorter than three characters", () => {
    expect(findValueHints([corpusPage(1, "ab")], "ab")).toEqual([]);
  });
});

describe("page number clamping", () => {
  it("clamps to the book length", () => {
    expect(clampPageNumber(0, 10)).toBe(1);
    expect(clampPageNumber(7, 10)).toBe(7);
    expect(clampPageNumber(12, 10)).toBe(10);
    expect(clampPageNumber(Number.NaN, 10)).toBe(1);
  });

  it("parses a query param and clamps it", () => {
    expect(pageNumberFromParam("12", 10)).toBe(10);
    expect(pageNumberFromParam("3", 10)).toBe(3);
    expect(pageNumberFromParam("abc", 10)).toBeNull();
    expect(pageNumberFromParam(null, 10)).toBeNull();
  });
});
