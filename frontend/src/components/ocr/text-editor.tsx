"use client";

import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import type { OcrWord } from "@/lib/api";
import { Button } from "@/components/shared/button";
import { Textarea } from "@/components/shared/input";
import { cn } from "@/lib/utils";

interface OcrTextEditorProps {
  words: OcrWord[];
  rawText: string | null;
  correctedText: string | null;
  selectedIndex?: number;
  onWordClick?: (index: number) => void;
  onSave?: (correctedText: string) => void;
  isSaving?: boolean;
}

interface WordGroup {
  blockNum: number;
  lineNum: number;
  words: { index: number; word: OcrWord }[];
}

function groupWordsByLine(words: OcrWord[]): WordGroup[] {
  const groups: Map<string, WordGroup> = new Map();

  words.forEach((word, index) => {
    const key = `${word.block_num}-${word.line_num}`;
    if (!groups.has(key)) {
      groups.set(key, {
        blockNum: word.block_num,
        lineNum: word.line_num,
        words: [],
      });
    }
    groups.get(key)!.words.push({ index, word });
  });

  return Array.from(groups.values()).sort(
    (a, b) => a.blockNum - b.blockNum || a.lineNum - b.lineNum,
  );
}

export default function OcrTextEditor({
  words,
  rawText,
  correctedText,
  selectedIndex,
  onWordClick,
  onSave,
  isSaving = false,
}: OcrTextEditorProps) {
  const [editMode, setEditMode] = useState(false);
  const [editedText, setEditedText] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const wordRefs = useRef<Map<number, HTMLSpanElement>>(new Map());

  const displayText = correctedText ?? rawText ?? "";
  const hasCorrections = correctedText !== null && correctedText !== rawText;

  const effectiveEditedText = editedText || displayText;

  const grouped = useMemo(() => groupWordsByLine(words), [words]);

  useEffect(() => {
    wordRefs.current.clear();
  }, [words]);

  useEffect(() => {
    if (selectedIndex === undefined || !containerRef.current) return;
    const el = wordRefs.current.get(selectedIndex);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [selectedIndex]);

  const handleWordClick = useCallback(
    (index: number) => {
      if (onWordClick) onWordClick(index);
    },
    [onWordClick],
  );

  const handleSave = () => {
    if (onSave) onSave(editMode ? editedText : displayText);
  };

  const handleToggleEdit = () => {
    if (editMode) {
      setEditMode(false);
    } else {
      setEditedText(displayText);
      setEditMode(true);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <h3 className="text-[var(--text-sm)] font-semibold text-[var(--text)]">
            OCR text
          </h3>
          <span className="text-[var(--text-xs)] tabular-nums text-[var(--text-muted)]">
            {words.length} words
          </span>
          {hasCorrections && (
            <span className="inline-flex items-center gap-1 rounded-full bg-[var(--info-50)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-[var(--info-700)] ring-1 ring-inset ring-[var(--info-500)]/30 dark:bg-[var(--info-900)]/20 dark:text-[var(--info-100)]">
              Edited
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={editMode ? "secondary" : "outline"}
            onClick={handleToggleEdit}
          >
            {editMode ? "Cancel edit" : "Edit text"}
          </Button>
          {onSave && (
            <Button
              type="button"
              size="sm"
              onClick={handleSave}
              loading={isSaving}
            >
              {isSaving ? "Saving" : "Save corrections"}
            </Button>
          )}
        </div>
      </div>

      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto px-4 py-3 text-[var(--text-sm)] leading-relaxed text-[var(--text)]"
        role="region"
        aria-label="OCR text editor"
      >
        {editMode ? (
          <Textarea
            value={effectiveEditedText}
            onChange={(e) => setEditedText(e.target.value)}
            className="min-h-0 h-full font-mono text-[var(--text-sm)] resize-none"
            dir="auto"
            aria-label="Edit OCR text"
          />
        ) : (
          <div className="whitespace-pre-wrap" dir="auto">
            {grouped.map((group) => (
              <div
                key={`block-${group.blockNum}-line-${group.lineNum}`}
                className="mb-1"
              >
                {group.words.map(({ index, word }) => {
                  const isSelected = index === selectedIndex;
                  const isLowConf = word.confidence < 60;

                  return (
                    <button
                      key={`word-${index}`}
                      type="button"
                      ref={(el) => {
                        if (el) wordRefs.current.set(index, el);
                      }}
                      onClick={() => handleWordClick(index)}
                      aria-label={`${word.text}, confidence ${word.confidence} percent${isLowConf ? ", uncertain" : ""}`}
                      aria-current={isSelected ? "true" : undefined}
                      className={cn(
                        "cursor-pointer rounded-[var(--radius-xs)] px-0.5",
                        "min-h-0 leading-inherit",
                        "transition-colors duration-[var(--duration-fast)]",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--background)]",
                        isSelected
                          ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)] ring-1 ring-inset ring-[var(--accent-ring)]/40"
                          : isLowConf
                            ? "underline decoration-[var(--danger-500)] decoration-2 underline-offset-2 hover:bg-[var(--danger-50)] dark:hover:bg-[var(--danger-900)]/20"
                            : "hover:bg-[var(--surface-sunken)]",
                      )}
                    >
                      {word.text}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
