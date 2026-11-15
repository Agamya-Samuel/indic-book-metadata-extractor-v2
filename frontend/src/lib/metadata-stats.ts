import type { MetadataFieldDefinition } from "@/lib/api";

/** Single threshold used by the row indicator, the filter, and the confirm dialog. */
export const LOW_CONFIDENCE_THRESHOLD = 0.5;

/** Values that mean "the source did not answer the question". */
export const UNCERTAIN_VALUES = ["n/a", "not found", "none", "unknown"] as const;

export type FieldStatus = "empty" | "uncertain" | "ok";

export interface FieldCounts {
  missing: number;
  uncertain: number;
}

export interface ConfidenceLike {
  confidence: number | null;
}

/** Fields whose drafts should be appended with a line break rather than a space. */
export const LONG_TEXT_FIELDS = new Set([
  "description_work",
  "description_edition",
  "dedication",
  "dedication_verbatim",
  "forewords",
  "abbreviations",
  "authors_in_compilation",
  "opinions_messages",
  "context",
]);

export function classifyFieldValue(
  value: string | null | undefined,
  confidence: number | null | undefined,
): FieldStatus {
  const text = (value ?? "").trim();
  if (!text) return "empty";
  if (
    typeof confidence === "number" &&
    confidence < LOW_CONFIDENCE_THRESHOLD
  ) {
    return "uncertain";
  }
  const lower = text.toLowerCase();
  if (UNCERTAIN_VALUES.some((sentinel) => sentinel === lower)) {
    return "uncertain";
  }
  return "ok";
}

/** Counts missing and uncertain standard fields against the live draft values. */
export function computeFieldCounts(
  fieldDefinitions: MetadataFieldDefinition[],
  values: Record<string, string>,
  confidenceByField?: Record<string, ConfidenceLike | undefined>,
): FieldCounts {
  let missing = 0;
  let uncertain = 0;

  for (const field of fieldDefinitions) {
    const status = classifyFieldValue(
      values[field.field_name],
      confidenceByField?.[field.field_name]?.confidence,
    );
    if (status === "empty") missing += 1;
    else if (status === "uncertain") uncertain += 1;
  }

  return { missing, uncertain };
}

export type AppendSeparator = "\n" | " ";

export function appendSeparatorFor(isLongText: boolean): AppendSeparator {
  return isLongText ? "\n" : " ";
}

/**
 * Appends a trimmed passage without overwriting an existing value. Empty
 * drafts receive the passage alone; otherwise a separator joins the two.
 */
export function appendToValue(
  existing: string,
  addition: string,
  separator: AppendSeparator,
): string {
  const trimmed = addition.trim();
  if (!trimmed) return existing;
  if (!existing.trim()) return trimmed;
  return `${existing.replace(/\s+$/, "")}${separator}${trimmed}`;
}
