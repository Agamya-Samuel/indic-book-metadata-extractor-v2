import { describe, it, expect } from "vitest";
import {
  appendSeparatorFor,
  appendToValue,
  classifyFieldValue,
  computeFieldCounts,
  LOW_CONFIDENCE_THRESHOLD,
} from "@/lib/metadata-stats";
import type { MetadataFieldDefinition } from "@/lib/api";

const fieldDefinitions: MetadataFieldDefinition[] = [
  {
    field_name: "title",
    display_name: "Title",
    wikidata_property: "P1476",
    batch_group: "core_identity",
  },
  {
    field_name: "publisher",
    display_name: "Publisher",
    wikidata_property: "P123",
    batch_group: "publication",
  },
  {
    field_name: "publication_date",
    display_name: "Publication Date",
    wikidata_property: "P577",
    batch_group: "publication",
  },
  {
    field_name: "author",
    display_name: "Author",
    wikidata_property: "P50",
    batch_group: "core_identity",
  },
];

describe("classifyFieldValue", () => {
  it("treats blank drafts as missing", () => {
    expect(classifyFieldValue("", null)).toBe("empty");
    expect(classifyFieldValue("   ", 0.9)).toBe("empty");
    expect(classifyFieldValue(undefined, null)).toBe("empty");
  });

  it("treats real low confidence as uncertain", () => {
    expect(
      classifyFieldValue("Some value", LOW_CONFIDENCE_THRESHOLD - 0.01),
    ).toBe("uncertain");
    expect(
      classifyFieldValue("Some value", LOW_CONFIDENCE_THRESHOLD),
    ).toBe("ok");
  });

  it("treats sentinel answers as uncertain regardless of confidence", () => {
    expect(classifyFieldValue("n/a", 0.99)).toBe("uncertain");
    expect(classifyFieldValue("Not Found", 0.99)).toBe("uncertain");
    expect(classifyFieldValue("none", null)).toBe("uncertain");
    expect(classifyFieldValue("UNKNOWN", null)).toBe("uncertain");
  });

  it("treats a normal answer as ok", () => {
    expect(classifyFieldValue("Andhra Mahabharata", 0.8)).toBe("ok");
  });
});

describe("computeFieldCounts", () => {
  it("counts missing and uncertain fields from live draft values", () => {
    const counts = computeFieldCounts(
      fieldDefinitions,
      {
        title: "Andhra Mahabharata",
        publisher: "",
        publication_date: "not found",
        author: "Somebody",
      },
      {
        title: { confidence: 0.9 },
        publisher: { confidence: null },
        publication_date: { confidence: 0.9 },
        author: { confidence: 0.2 },
      },
    );

    expect(counts).toEqual({ missing: 1, uncertain: 2 });
  });

  it("uses drafts, not persisted values", () => {
    const counts = computeFieldCounts(fieldDefinitions, {
      title: "Now filled",
      publisher: "",
      publication_date: "",
      author: "",
    });
    expect(counts.missing).toBe(3);
  });
});

describe("appendToValue", () => {
  it("fills an empty draft with the trimmed passage", () => {
    expect(appendToValue("", "  source text  ", " ")).toBe("source text");
    expect(appendToValue("   ", "source text", "\n")).toBe("source text");
  });

  it("appends after an existing value with a space", () => {
    expect(appendToValue("First part", "second part", " ")).toBe(
      "First part second part",
    );
  });

  it("appends after an existing value with a newline for long text", () => {
    expect(appendToValue("First paragraph", "second paragraph", "\n")).toBe(
      "First paragraph\nsecond paragraph",
    );
  });

  it("trims trailing whitespace before joining", () => {
    expect(appendToValue("Existing   ", "addition", " ")).toBe(
      "Existing addition",
    );
  });

  it("never overwrites an existing value with an empty passage", () => {
    expect(appendToValue("Existing value", "   ", " ")).toBe("Existing value");
  });
});

describe("appendSeparatorFor", () => {
  it("uses a newline for long text fields and a space otherwise", () => {
    expect(appendSeparatorFor(true)).toBe("\n");
    expect(appendSeparatorFor(false)).toBe(" ");
  });
});
