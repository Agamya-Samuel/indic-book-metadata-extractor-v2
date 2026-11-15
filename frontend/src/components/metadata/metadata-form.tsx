"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import type { MetadataFieldDefinition } from "@/lib/api";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { Button } from "@/components/shared/button";
import { Field, Input, Textarea } from "@/components/shared/input";
import { Card, Stack } from "@/components/shared/card";
import { cn } from "@/lib/utils";
import { focusRing } from "@/lib/focus-ring";
import {
  LONG_TEXT_FIELDS,
  appendSeparatorFor,
  appendToValue,
  classifyFieldValue,
  computeFieldCounts,
} from "@/lib/metadata-stats";

interface FieldConfidence {
  confidence: number | null;
  extraction_method: string;
  source_page_number: number | null;
  source_text_snippet: string | null;
}

export interface MetadataFormStats {
  dirty: number;
  missing: number;
  uncertain: number;
}

export interface MetadataFormActions {
  save: () => void;
  discard: () => void;
  appendToField: (fieldName: string, text: string) => void;
}

interface MetadataFormProps {
  fieldDefinitions: MetadataFieldDefinition[];
  values: Record<string, string | Record<string, string>>;
  onSave: (
    fields: Record<string, string | Record<string, string>>,
  ) => void | Promise<void>;
  /** Retained for callers; the page's save bar owns the saving state now. */
  isSaving?: boolean;
  confidenceByField?: Record<string, FieldConfidence>;
  /** Reports which field the reviewer is working on, for the reference pane. */
  onFieldFocus?: (fieldName: string) => void;
  /** Jumps the reference pane to a field with a recorded source page. */
  onShowSource?: (fieldName: string) => void;
  /** Reports dirty, missing and uncertain counts to the page. */
  onStatsChange?: (stats: MetadataFormStats) => void;
  /** Hands the save, discard, and append actions up to the page. */
  onRegisterActions?: (actions: MetadataFormActions) => void;
}

const BATCH_DISPLAY_NAMES: Record<string, string> = {
  core_identity: "Core Identity",
  contributors: "Contributors",
  publication: "Publication",
  content_classification: "Content Classification",
  edition_series: "Edition & Series",
  relationships: "Relationships",
  ancillary_content: "Ancillary Content",
  physical_extra: "Physical & Extra",
};

type FieldFilter = "all" | "missing" | "uncertain";

function getFieldConfidence(
  value: string | undefined | null,
  realConfidence: number | null | undefined,
): "high" | "medium" | "empty" {
  const status = classifyFieldValue(value, realConfidence);
  if (status === "empty") return "empty";
  if (status === "uncertain") return "medium";
  if (typeof realConfidence === "number") {
    return realConfidence >= 0.85 ? "high" : "medium";
  }
  return "high";
}

const CONFIDENCE_STYLES = {
  high: {
    dot: "bg-[var(--success-500)]",
    border: "border-[var(--border)]",
    bg: "",
    label: "High confidence",
  },
  medium: {
    dot: "bg-[var(--warning-500)]",
    border: "border-[var(--warning-500)]/30",
    bg: "bg-[var(--warning-50)] dark:bg-[var(--warning-900)]/10",
    label: "Uncertain",
  },
  empty: {
    dot: "bg-[var(--danger-500)]",
    border: "border-[var(--danger-500)]/20",
    bg: "bg-[var(--danger-50)]/40 dark:bg-[var(--danger-900)]/5",
    label: "Missing",
  },
};

const FILTER_DOTS: Record<FieldFilter, string> = {
  all: "bg-[var(--text-subtle)]",
  missing: "bg-[var(--danger-500)]",
  uncertain: "bg-[var(--warning-500)]",
};

function afterRender(callback: () => void): void {
  if (
    typeof window !== "undefined" &&
    typeof window.requestAnimationFrame === "function"
  ) {
    window.requestAnimationFrame(callback);
    return;
  }
  setTimeout(callback, 0);
}

function FilterChip({
  filter,
  active,
  count,
  onClick,
}: {
  filter: FieldFilter;
  active: boolean;
  count: number;
  onClick: () => void;
}) {
  const label = filter === "all" ? "All" : filter === "missing" ? "Missing" : "Uncertain";
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1",
        "text-[11px] font-medium tabular-nums",
        focusRing,
        active
          ? "border-[var(--accent)]/40 bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
          : "border-[var(--border)] text-[var(--text-muted)] hover:bg-[var(--surface-sunken)] hover:text-[var(--text)]",
      )}
    >
      <span
        aria-hidden="true"
        className={cn("size-1.5 shrink-0 rounded-full", FILTER_DOTS[filter])}
      />
      {label} ({count})
    </button>
  );
}

export default function MetadataForm({
  fieldDefinitions,
  values,
  onSave,
  confidenceByField,
  onFieldFocus,
  onShowSource,
  onStatsChange,
  onRegisterActions,
}: MetadataFormProps) {
  const [editedValues, setEditedValues] = useState<Record<string, string>>({});
  const [customFieldName, setCustomFieldName] = useState("");
  const [customFields, setCustomFields] = useState<Record<string, string>>({});
  const [removedCustomKeys, setRemovedCustomKeys] = useState<Set<string>>(
    new Set(),
  );
  const [filter, setFilter] = useState<FieldFilter>("all");
  const [activeField, setActiveField] = useState<string | undefined>(undefined);
  // Section that must be open for a programmatic focus (Next missing / append)
  // to land on a visible row. Cleared when the reviewer changes the filter.
  const [revealField, setRevealField] = useState<string | null>(null);
  const fieldRefs = useRef<
    Record<string, HTMLInputElement | HTMLTextAreaElement | null>
  >({});

  // ``custom_fields`` is the one nested value; normalise it once.
  const persistedCustomFields = useMemo<Record<string, string>>(() => {
    const raw = values.custom_fields;
    if (!raw || typeof raw !== "object") return {};
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
      out[k] = typeof v === "string" ? v : "";
    }
    return out;
  }, [values.custom_fields]);

  const currentValues = useMemo(() => {
    const merged: Record<string, string> = {};
    for (const key of Object.keys(values)) {
      if (key === "custom_fields") continue;
      const value = values[key];
      merged[key] = typeof value === "string" ? value : "";
    }
    for (const [k, v] of Object.entries(persistedCustomFields)) {
      merged[`custom_${k}`] = v;
    }
    for (const key of removedCustomKeys) delete merged[key];
    Object.assign(merged, editedValues);
    Object.assign(merged, customFields);
    return merged;
  }, [values, persistedCustomFields, editedValues, customFields, removedCustomKeys]);

  // Custom fields come from two places: the ones already saved on the book and
  // the ones added in this session. Removed ones are hidden but still tracked
  // as dirty so the removal is saved.
  const displayedCustomKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const k of Object.keys(persistedCustomFields)) {
      keys.add(`custom_${k}`);
    }
    for (const k of Object.keys(customFields)) keys.add(k);
    for (const k of removedCustomKeys) keys.delete(k);
    return Array.from(keys);
  }, [persistedCustomFields, customFields, removedCustomKeys]);

  const dirtyKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const k of Object.keys(editedValues)) {
      if (k.startsWith("custom_")) continue;
      if (editedValues[k] !== (values[k] ?? "")) keys.add(k);
    }
    for (const k of displayedCustomKeys) {
      const realName = k.replace("custom_", "");
      if ((currentValues[k] ?? "") !== (persistedCustomFields[realName] ?? "")) {
        keys.add(k);
      }
    }
    for (const k of removedCustomKeys) keys.add(k);
    return keys;
  }, [
    editedValues,
    values,
    displayedCustomKeys,
    removedCustomKeys,
    currentValues,
    persistedCustomFields,
  ]);

  const fieldCounts = useMemo(
    () => computeFieldCounts(fieldDefinitions, currentValues, confidenceByField),
    [fieldDefinitions, currentValues, confidenceByField],
  );

  const statusFor = useCallback(
    (fieldName: string) =>
      classifyFieldValue(
        currentValues[fieldName],
        confidenceByField?.[fieldName]?.confidence,
      ),
    [currentValues, confidenceByField],
  );

  const handleChange = useCallback((fieldName: string, value: string) => {
    setEditedValues((prev) => ({ ...prev, [fieldName]: value }));
  }, []);

  const focusField = useCallback(
    (fieldName: string) => {
      setActiveField(fieldName);
      // Next missing and append focus fields programmatically; the row may be
      // inside a collapsed section, so open that section first.
      setRevealField(fieldName);
      onFieldFocus?.(fieldName);
      afterRender(() => {
        const element = fieldRefs.current[fieldName];
        if (!element) return;
        element.focus({ preventScroll: true });
        if (typeof element.scrollIntoView === "function") {
          element.scrollIntoView({ block: "center", behavior: "auto" });
        }
        const end = element.value.length;
        element.setSelectionRange(end, end);
      });
    },
    [onFieldFocus],
  );

  const appendToField = useCallback(
    (fieldName: string, text: string) => {
      const next = appendToValue(
        currentValues[fieldName] ?? "",
        text,
        appendSeparatorFor(LONG_TEXT_FIELDS.has(fieldName)),
      );
      setEditedValues((prev) => ({ ...prev, [fieldName]: next }));
      focusField(fieldName);
    },
    [currentValues, focusField],
  );

  const handleAddCustomField = useCallback(() => {
    const name = customFieldName.trim();
    if (!name) return;
    const key = `custom_${name}`;
    setCustomFields((prev) => ({ ...prev, [key]: "" }));
    setRemovedCustomKeys((prev) => {
      if (!prev.has(key)) return prev;
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
    setCustomFieldName("");
  }, [customFieldName]);

  const handleRemoveCustomField = useCallback((key: string) => {
    setCustomFields((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setEditedValues((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setRemovedCustomKeys((prev) => new Set(prev).add(key));
  }, []);

  const handleSave = useCallback(async () => {
    const toSave: Record<string, string | Record<string, string>> = {};
    for (const k of dirtyKeys) {
      if (k.startsWith("custom_")) continue;
      toSave[k] = currentValues[k] ?? "";
    }
    const customObj: Record<string, string> = {};
    for (const k of Object.keys(currentValues)) {
      if (k.startsWith("custom_")) {
        customObj[k.replace("custom_", "")] = currentValues[k] ?? "";
      }
    }
    const persistedCustom = persistedCustomFields;
    // Always send custom_fields once the book has any, so removing the last one
    // is persisted instead of leaving the old value in place.
    if (
      Object.keys(persistedCustom).length > 0 ||
      Object.keys(customObj).length > 0 ||
      removedCustomKeys.size > 0
    ) {
      toSave.custom_fields = customObj;
    }
    try {
      await onSave(toSave);
    } catch {
      return; // the page reports the failure; keep the reviewer's draft
    }
    setEditedValues({});
    setCustomFields({});
    setRemovedCustomKeys(new Set());
  }, [
    dirtyKeys,
    currentValues,
    onSave,
    removedCustomKeys,
    persistedCustomFields,
  ]);

  const handleDiscard = useCallback(() => {
    setEditedValues({});
    setCustomFields({});
    setRemovedCustomKeys(new Set());
  }, []);

  useEffect(() => {
    onStatsChange?.({
      dirty: dirtyKeys.size,
      missing: fieldCounts.missing,
      uncertain: fieldCounts.uncertain,
    });
  }, [
    dirtyKeys.size,
    fieldCounts.missing,
    fieldCounts.uncertain,
    onStatsChange,
  ]);

  useEffect(() => {
    onRegisterActions?.({
      save: handleSave,
      discard: handleDiscard,
      appendToField,
    });
  }, [onRegisterActions, handleSave, handleDiscard, appendToField]);

  const matchesFilter = useCallback(
    (fieldName: string) => {
      if (filter === "all") return true;
      if (activeField === fieldName) return true;
      const status = statusFor(fieldName);
      return filter === "missing" ? status === "empty" : status === "uncertain";
    },
    [filter, activeField, statusFor],
  );

  const goToNextMissing = useCallback(() => {
    const missing = fieldDefinitions.filter(
      (field) => statusFor(field.field_name) === "empty",
    );
    if (missing.length === 0) return;
    const index = missing.findIndex(
      (field) => field.field_name === activeField,
    );
    const next = missing[(index + 1) % missing.length];
    if (filter === "uncertain") setFilter("all");
    focusField(next.field_name);
  }, [fieldDefinitions, statusFor, activeField, filter, focusField]);

  const fieldsByBatch = useMemo(() => {
    const grouped: Record<string, MetadataFieldDefinition[]> = {};
    for (const field of fieldDefinitions) {
      if (!grouped[field.batch_group]) {
        grouped[field.batch_group] = [];
      }
      grouped[field.batch_group].push(field);
    }
    return grouped;
  }, [fieldDefinitions]);

  const batchByField = useMemo(() => {
    const map = new Map<string, string>();
    for (const field of fieldDefinitions) {
      map.set(field.field_name, field.batch_group);
    }
    return map;
  }, [fieldDefinitions]);

  return (
    <div>
      <div
        role="group"
        aria-label="Filter metadata fields"
        className="mb-3 flex flex-wrap items-center gap-1.5"
      >
        <FilterChip
          filter="all"
          active={filter === "all"}
          count={fieldDefinitions.length}
          onClick={() => {
            setRevealField(null);
            setFilter("all");
          }}
        />
        <FilterChip
          filter="missing"
          active={filter === "missing"}
          count={fieldCounts.missing}
          onClick={() => {
            setRevealField(null);
            setFilter("missing");
          }}
        />
        <FilterChip
          filter="uncertain"
          active={filter === "uncertain"}
          count={fieldCounts.uncertain}
          onClick={() => {
            setRevealField(null);
            setFilter("uncertain");
          }}
        />
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto"
          onClick={goToNextMissing}
          disabled={fieldCounts.missing === 0}
        >
          Next missing
        </Button>
      </div>

      <Stack gap={3}>
        {Object.entries(fieldsByBatch).map(([batch, fields]) => {
          const visibleFields = fields.filter((field) =>
            matchesFilter(field.field_name),
          );
          if (visibleFields.length === 0) return null;

          return (
            <CollapsibleSection
              key={batch}
              title={BATCH_DISPLAY_NAMES[batch] ?? batch}
              count={visibleFields.length}
              defaultOpen={batch === "core_identity" || batch === "publication"}
              forceOpen={
                filter !== "all" ||
                (revealField !== null && batchByField.get(revealField) === batch)
              }
            >
              <Stack gap={2}>
                {visibleFields.map((field) => {
                  const value = currentValues[field.field_name] ?? "";
                  const fieldConfidence = confidenceByField?.[field.field_name];
                  const realConf = fieldConfidence?.confidence;
                  const confidence = getFieldConfidence(value, realConf);
                  const style = CONFIDENCE_STYLES[confidence];
                  const isLong = LONG_TEXT_FIELDS.has(field.field_name);
                  const sourcePage = fieldConfidence?.source_page_number;
                  const tooltip =
                    realConf != null
                      ? `${style.label} (confidence ${(realConf * 100).toFixed(0)}%, ${fieldConfidence?.extraction_method ?? "unknown"})`
                      : style.label;

                  return (
                    <div
                      key={field.field_name}
                      className={cn(
                        "flex flex-col gap-2 rounded-[var(--radius)] border px-3 py-2.5 xl:flex-row xl:items-start xl:gap-3",
                        style.border,
                        style.bg,
                      )}
                    >
                      <div className="shrink-0 xl:w-44">
                        <div className="flex items-center gap-1.5">
                          <span
                            aria-hidden="true"
                            className={cn(
                              "inline-block size-2 rounded-full",
                              style.dot,
                            )}
                          />
                          <label
                            htmlFor={`field-${field.field_name}`}
                            className="text-[length:var(--text-xs)] font-medium text-[var(--text)]"
                            title={tooltip}
                          >
                            {field.display_name}
                          </label>
                        </div>
                        {field.wikidata_property && (
                          <span className="mt-1 ml-3.5 inline-block rounded-[var(--radius-xs)] bg-[var(--neutral-100)] px-1 py-0.5 font-mono text-[10px] text-[var(--text-muted)] dark:bg-[var(--neutral-800)]">
                            {field.wikidata_property}
                          </span>
                        )}
                        {onShowSource && sourcePage != null && (
                          <button
                            type="button"
                            onClick={() => onShowSource(field.field_name)}
                            className={cn(
                              "mt-1 ml-3.5 block rounded-[var(--radius-xs)] px-1 py-0.5",
                              "text-[10px] font-medium text-[var(--accent-soft-text)]",
                              "hover:bg-[var(--accent-soft)]",
                              focusRing,
                            )}
                          >
                            Source p.{sourcePage}
                          </button>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        {isLong ? (
                          <Textarea
                            id={`field-${field.field_name}`}
                            ref={(element) => {
                              fieldRefs.current[field.field_name] = element;
                            }}
                            value={value}
                            onChange={(e) =>
                              handleChange(field.field_name, e.target.value)
                            }
                            onFocus={() => {
                              setActiveField(field.field_name);
                              onFieldFocus?.(field.field_name);
                            }}
                            rows={3}
                            dir="auto"
                          />
                        ) : (
                          <Input
                            id={`field-${field.field_name}`}
                            ref={(element) => {
                              fieldRefs.current[field.field_name] = element;
                            }}
                            type="text"
                            value={value}
                            onChange={(e) =>
                              handleChange(field.field_name, e.target.value)
                            }
                            onFocus={() => {
                              setActiveField(field.field_name);
                              onFieldFocus?.(field.field_name);
                            }}
                            dir="auto"
                            placeholder={
                              confidence === "empty" ? "Not extracted" : ""
                            }
                          />
                        )}
                      </div>
                    </div>
                  );
                })}
              </Stack>
            </CollapsibleSection>
          );
        })}
      </Stack>

      <Card className="mt-4" title="Custom fields" description="Add any field that's not in the standard list.">
        <Stack gap={3}>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Field label="New field" htmlFor="new-custom-field">
                <Input
                  id="new-custom-field"
                  type="text"
                  value={customFieldName}
                  onChange={(e) => setCustomFieldName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleAddCustomField();
                  }}
                  placeholder="e.g. printer"
                />
              </Field>
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={handleAddCustomField}
              disabled={!customFieldName.trim()}
            >
              Add
            </Button>
          </div>

          {displayedCustomKeys.length > 0 && (
            <Stack gap={2}>
              {displayedCustomKeys.map((key) => {
                const displayName = key.replace("custom_", "");
                return (
                  <div key={key} className="flex items-center gap-2">
                    <span className="w-32 shrink-0 truncate text-[length:var(--text-xs)] font-medium text-[var(--text-muted)]">
                      {displayName}
                    </span>
                    <Input
                      className="flex-1"
                      type="text"
                      value={currentValues[key] ?? ""}
                      onChange={(e) => handleChange(key, e.target.value)}
                      dir="auto"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveCustomField(key)}
                    >
                      Remove
                    </Button>
                  </div>
                );
              })}
            </Stack>
          )}
        </Stack>
      </Card>
    </div>
  );
}
