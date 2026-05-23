"use client";

import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import type { OcrWord } from "@/lib/api";

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
    (a, b) =>
      a.blockNum - b.blockNum || a.lineNum - b.lineNum
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
      if (onWordClick) {
        onWordClick(index);
      }
    },
    [onWordClick]
  );

  const handleSave = () => {
    if (onSave) {
      onSave(editMode ? editedText : displayText);
    }
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
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 border-b bg-gray-50 dark:bg-gray-800 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">OCR Text</h3>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            ({words.length} words)
          </span>
          {hasCorrections && (
            <span className="text-xs px-2 py-0.5 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded">
              Edited
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleToggleEdit}
            className={`px-3 py-1 text-xs rounded border transition-colors ${
              editMode
                ? "bg-blue-600 text-white border-blue-600"
                : "border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
            }`}
          >
            {editMode ? "Cancel Edit" : "Edit Text"}
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-3 py-1 text-xs rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSaving ? "Saving..." : "Save Corrections"}
          </button>
        </div>
      </div>

      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto p-4 text-sm leading-relaxed"
        role="region"
        aria-label="OCR text editor"
      >
        {editMode ? (
          <textarea
            value={effectiveEditedText}
            onChange={(e) => setEditedText(e.target.value)}
            className="w-full h-full min-h-[400px] p-2 border rounded font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
            dir="auto"
            aria-label="Edit OCR text"
          />
        ) : (
          <div className="whitespace-pre-wrap" dir="auto">
            {grouped.map((group) => (
              <div key={`block-${group.blockNum}-line-${group.lineNum}`} className="mb-1">
                {group.words.map(({ index, word }) => {
                  const isSelected = index === selectedIndex;
                  const isLowConf = word.confidence < 60;

                  return (
                    <span
                      key={`word-${index}`}
                      ref={(el) => {
                        if (el) wordRefs.current.set(index, el);
                      }}
                      onClick={() => handleWordClick(index)}
                      className={`cursor-pointer px-0.5 rounded-sm transition-colors ${
                        isSelected
                          ? "bg-blue-200 ring-1 ring-blue-400 dark:bg-blue-800 dark:ring-blue-500"
                          : isLowConf
                            ? "underline decoration-red-400 decoration-2 underline-offset-2 hover:bg-red-50 dark:hover:bg-red-900/30"
                            : "hover:bg-gray-200 dark:hover:bg-gray-600"
                      }`}
                      title={`Confidence: ${word.confidence}%`}
                    >
                      {word.text}
                    </span>
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
