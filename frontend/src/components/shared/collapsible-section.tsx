"use client";

import { useState } from "react";

interface CollapsibleSectionProps {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export default function CollapsibleSection({
  title,
  count,
  defaultOpen = true,
  children,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const panelId = `panel-${title.toLowerCase().replace(/\s+/g, "-")}`;

  return (
    <div className="border rounded-lg dark:border-gray-600">
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-controls={panelId}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span
            className={`transform transition-transform text-gray-400 dark:text-gray-500 ${isOpen ? "rotate-90" : ""}`}
            aria-hidden="true"
          >
            ▶
          </span>
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{title}</span>
          {count !== undefined && (
            <span className="text-xs text-gray-500 dark:text-gray-400">({count} fields)</span>
          )}
        </div>
      </button>
      {isOpen && (
        <div id={panelId} className="px-4 pb-3">
          {children}
        </div>
      )}
    </div>
  );
}
