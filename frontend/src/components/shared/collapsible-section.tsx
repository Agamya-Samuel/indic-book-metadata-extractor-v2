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

  return (
    <div className="border rounded-lg">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span
            className={`transform transition-transform text-gray-400 ${isOpen ? "rotate-90" : ""}`}
          >
            ▶
          </span>
          <span className="text-sm font-medium text-gray-900">{title}</span>
          {count !== undefined && (
            <span className="text-xs text-gray-500">({count} fields)</span>
          )}
        </div>
      </button>
      {isOpen && <div className="px-4 pb-3">{children}</div>}
    </div>
  );
}
