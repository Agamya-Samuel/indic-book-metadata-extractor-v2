"use client";

import { useState, useCallback, useMemo } from "react";
import type { MetadataFieldDefinition } from "@/lib/api";
import CollapsibleSection from "@/components/shared/collapsible-section";

interface MetadataFormProps {
  fieldDefinitions: MetadataFieldDefinition[];
  values: Record<string, string>;
  onSave: (fields: Record<string, string | Record<string, string>>) => void;
  isSaving: boolean;
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
  value: string | undefined | null
): "high" | "medium" | "empty" {
  if (!value || value.trim() === "") return "empty";
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
    dot: "bg-green-500",
    border: "border-green-200 dark:border-green-800",
    bg: "",
  },
  medium: {
    dot: "bg-yellow-500",
    border: "border-yellow-200 dark:border-yellow-800",
    bg: "bg-yellow-25 dark:bg-yellow-900/10",
  },
  empty: {
    dot: "bg-red-400",
    border: "border-red-200 dark:border-red-800",
    bg: "",
  },
};

export default function MetadataForm({
  fieldDefinitions,
  values,
  onSave,
  isSaving,
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

  const handleChange = useCallback(
    (fieldName: string, value: string) => {
      setEditedValues((prev) => ({ ...prev, [fieldName]: value }));
    },
    []
  );

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
      <div className="space-y-3">
        {Object.entries(fieldsByBatch).map(([batch, fields]) => (
          <CollapsibleSection
            key={batch}
            title={BATCH_DISPLAY_NAMES[batch] ?? batch}
            count={fields.length}
            defaultOpen={batch === "core_identity" || batch === "publication"}
          >
            <div className="space-y-2">
              {fields.map((field) => {
                const value = currentValues[field.field_name] ?? "";
                const confidence = getFieldConfidence(value);
                const style = CONFIDENCE_STYLES[confidence];
                const isLong = LONG_TEXT_FIELDS.has(field.field_name);

                return (
                  <div
                    key={field.field_name}
                    className={`flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-3 px-3 py-2 rounded border ${style.border} ${style.bg}`}
                  >
                    <div className="sm:w-44 shrink-0 pt-1.5">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`inline-block w-2 h-2 rounded-full ${style.dot}`}
                          title={
                            confidence === "high"
                              ? "Extracted"
                              : confidence === "medium"
                                ? "Uncertain"
                                : "Missing"
                          }
                        />
                        <label
                          htmlFor={`field-${field.field_name}`}
                          className="text-xs font-medium text-gray-700 dark:text-gray-300"
                        >
                          {field.display_name}
                        </label>
                      </div>
                      {field.wikidata_property && (
                        <span className="text-[10px] px-1 py-0.5 bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400 rounded ml-3.5">
                          {field.wikidata_property}
                        </span>
                      )}
                    </div>
                    <div className="flex-1">
                      {isLong ? (
                        <textarea
                          id={`field-${field.field_name}`}
                          value={value}
                          onChange={(e) =>
                            handleChange(field.field_name, e.target.value)
                          }
                          rows={2}
                          className="w-full border rounded px-2 py-1 text-sm resize-y focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                          dir="auto"
                        />
                      ) : (
                        <input
                          id={`field-${field.field_name}`}
                          type="text"
                          value={value}
                          onChange={(e) =>
                            handleChange(field.field_name, e.target.value)
                          }
                          className="w-full border rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
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
            </div>
          </CollapsibleSection>
        ))}
      </div>

      <div className="mt-4 border rounded-lg p-4 dark:border-gray-600">
        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Custom Fields
        </h4>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={customFieldName}
            onChange={(e) => setCustomFieldName(e.target.value)}
            placeholder="Field name"
            aria-label="New custom field name"
            className="flex-1 border rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAddCustomField();
            }}
          />
          <button
            onClick={handleAddCustomField}
            disabled={!customFieldName.trim()}
            className="px-3 py-1 text-sm bg-gray-100 dark:bg-gray-700 border dark:border-gray-600 rounded hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Add
          </button>
        </div>
        {Object.keys(customFields).length > 0 && (
          <div className="space-y-2">
            {Object.entries(customFields).map(([key, val]) => {
              const displayName = key.replace("custom_", "");
              return (
                <div key={key} className="flex items-center gap-2">
                  <span className="text-xs font-medium text-gray-500 dark:text-gray-400 w-32 truncate">
                    {displayName}
                  </span>
                  <input
                    type="text"
                    value={editedValues[key] ?? val}
                    onChange={(e) => handleChange(key, e.target.value)}
                    className="flex-1 border rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    dir="auto"
                  />
                  <button
                    onClick={() => handleRemoveCustomField(key)}
                    className="px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                  >
                    Remove
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={isSaving || dirtyKeys.size === 0}
          className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {isSaving ? "Saving..." : "Save Metadata"}
        </button>
        {dirtyKeys.size > 0 && (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {dirtyKeys.size} unsaved change{dirtyKeys.size !== 1 ? "s" : ""}
          </span>
        )}
      </div>
    </div>
  );
}
