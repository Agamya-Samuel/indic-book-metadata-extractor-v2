"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import type { MetadataFieldDefinition } from "@/lib/api";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { Button } from "@/components/shared/button";
import { Field, Input, Textarea } from "@/components/shared/input";
import { Card, Stack } from "@/components/shared/card";
import { cn } from "@/lib/utils";

interface FieldConfidence {
  confidence: number | null;
  extraction_method: string;
  source_page_number: number | null;
  source_text_snippet: string | null;
}

interface MetadataFormProps {
  fieldDefinitions: MetadataFieldDefinition[];
  values: Record<string, string>;
  onSave: (fields: Record<string, string | Record<string, string>>) => void;
  /** Retained for callers; the page's save bar owns the saving state now. */
  isSaving?: boolean;
  confidenceByField?: Record<string, FieldConfidence>;
  /** Reports which field the reviewer is working on, for the evidence pane. */
  onFieldFocus?: (fieldName: string) => void;
  /** Reports the unsaved-change count so the page can own the save bar. */
  onDirtyCountChange?: (count: number) => void;
  /** Hands the save and discard actions up to the page's save bar. */
  onRegisterActions?: (actions: {
    save: () => void;
    discard: () => void;
  }) => void;
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

const LONG_TEXT_FIELDS = new Set([
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

function getFieldConfidence(
  value: string | undefined | null,
  realConfidence: number | null | undefined,
): "high" | "medium" | "empty" {
  if (!value || value.trim() === "") return "empty";
  if (typeof realConfidence === "number") {
    if (realConfidence >= 0.85) return "high";
    if (realConfidence >= 0.5) return "medium";
    return "medium";
  }
  const lower = value.toLowerCase();
  if (
    lower === "n/a" ||
    lower === "not found" ||
    lower === "null" ||
    lower === "none" ||
    lower === "unknown"
  )
    return "medium";
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

export default function MetadataForm({
  fieldDefinitions,
  values,
  onSave,
  confidenceByField,
  onFieldFocus,
  onDirtyCountChange,
  onRegisterActions,
}: MetadataFormProps) {
  const [editedValues, setEditedValues] = useState<Record<string, string>>({});
  const [customFieldName, setCustomFieldName] = useState("");
  const [customFields, setCustomFields] = useState<Record<string, string>>({});

  const currentValues = useMemo(() => {
    const merged: Record<string, string> = {};
    for (const key of Object.keys(values)) {
      if (key === "custom_fields") continue;
      merged[key] = values[key];
    }
    if (values.custom_fields && typeof values.custom_fields === "object") {
      for (const [k, v] of Object.entries(values.custom_fields as Record<string, string>)) {
        merged[`custom_${k}`] = v;
      }
    }
    Object.assign(merged, editedValues);
    Object.assign(merged, customFields);
    return merged;
  }, [values, editedValues, customFields]);

  const dirtyKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const k of Object.keys(editedValues)) {
      if (editedValues[k] !== (values[k] ?? "")) keys.add(k);
    }
    for (const k of Object.keys(customFields)) {
      keys.add(k);
    }
    return keys;
  }, [editedValues, values, customFields]);

  const handleChange = useCallback((fieldName: string, value: string) => {
    setEditedValues((prev) => ({ ...prev, [fieldName]: value }));
  }, []);

  const handleAddCustomField = useCallback(() => {
    const name = customFieldName.trim();
    if (!name) return;
    setCustomFields((prev) => ({ ...prev, [`custom_${name}`]: "" }));
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
  }, []);

  const handleSave = useCallback(() => {
    const toSave: Record<string, string | Record<string, string>> = {};
    for (const k of dirtyKeys) {
      if (k.startsWith("custom_")) continue;
      toSave[k] = currentValues[k] ?? "";
    }
    const customObj: Record<string, string> = {};
    for (const k of Object.keys(currentValues)) {
      if (k.startsWith("custom_") && k !== "custom_fields") {
        const realName = k.replace("custom_", "");
        customObj[realName] = currentValues[k] ?? "";
      }
    }
    if (Object.keys(customObj).length > 0) {
      toSave.custom_fields = customObj;
    }
    onSave(toSave);
  }, [dirtyKeys, currentValues, onSave]);

  const handleDiscard = useCallback(() => {
    setEditedValues({});
    setCustomFields({});
  }, []);

  useEffect(() => {
    onDirtyCountChange?.(dirtyKeys.size);
  }, [dirtyKeys.size, onDirtyCountChange]);

  useEffect(() => {
    onRegisterActions?.({ save: handleSave, discard: handleDiscard });
  }, [onRegisterActions, handleSave, handleDiscard]);

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

  return (
    <div>
      <Stack gap={3}>
        {Object.entries(fieldsByBatch).map(([batch, fields]) => (
          <CollapsibleSection
            key={batch}
            title={BATCH_DISPLAY_NAMES[batch] ?? batch}
            count={fields.length}
            defaultOpen={batch === "core_identity" || batch === "publication"}
          >
            <Stack gap={2}>
              {fields.map((field) => {
                const value = currentValues[field.field_name] ?? "";
                const realConf = confidenceByField?.[field.field_name]?.confidence;
                const confidence = getFieldConfidence(value, realConf);
                const style = CONFIDENCE_STYLES[confidence];
                const isLong = LONG_TEXT_FIELDS.has(field.field_name);
                const tooltip =
                  realConf != null
                    ? `${style.label} (confidence ${(realConf * 100).toFixed(0)}%, ${confidenceByField?.[field.field_name]?.extraction_method ?? "unknown"})`
                    : style.label;

                return (
                  <div
                    key={field.field_name}
                    className={cn(
                      "flex flex-col gap-2 rounded-[var(--radius)] border px-3 py-2.5 sm:flex-row sm:items-start sm:gap-3",
                      style.border,
                      style.bg,
                    )}
                  >
                    <div className="shrink-0 sm:w-44">
                      <div className="flex items-center gap-1.5">
                        <span
                          aria-hidden="true"
                          className={cn("inline-block size-2 rounded-full", style.dot)}
                        />
                        <label
                          htmlFor={`field-${field.field_name}`}
                          className="text-[var(--text-xs)] font-medium text-[var(--text)]"
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
                    </div>
                    <div className="flex-1 min-w-0">
                      {isLong ? (
                        <Textarea
                          id={`field-${field.field_name}`}
                          value={value}
                          onChange={(e) =>
                            handleChange(field.field_name, e.target.value)
                          }
                          onFocus={() => onFieldFocus?.(field.field_name)}
                          rows={3}
                          dir="auto"
                        />
                      ) : (
                        <Input
                          id={`field-${field.field_name}`}
                          type="text"
                          value={value}
                          onChange={(e) =>
                            handleChange(field.field_name, e.target.value)
                          }
                          onFocus={() => onFieldFocus?.(field.field_name)}
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
        ))}
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

          {Object.keys(customFields).length > 0 && (
            <Stack gap={2}>
              {Object.entries(customFields).map(([key, val]) => {
                const displayName = key.replace("custom_", "");
                return (
                  <div key={key} className="flex items-center gap-2">
                    <span className="w-32 shrink-0 truncate text-[var(--text-xs)] font-medium text-[var(--text-muted)]">
                      {displayName}
                    </span>
                    <Input
                      className="flex-1"
                      type="text"
                      value={editedValues[key] ?? val}
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
