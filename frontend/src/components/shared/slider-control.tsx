"use client";

import { cn } from "@/lib/utils";

interface SliderControlProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  formatValue?: (v: number) => string;
  hint?: string;
  id?: string;
}

/**
 * Range slider with a labelled value chip.
 * The native thumb is the only accessible option; we tint the track and
 * the focus ring to match the accent so it reads as part of the system.
 */
export default function SliderControl({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  formatValue,
  hint,
  id,
}: SliderControlProps) {
  const displayValue = formatValue ? formatValue(value) : value;
  const fieldId = id ?? `slider-${label.toLowerCase().replace(/\s+/g, "-")}`;
  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <label
          htmlFor={fieldId}
          className="text-[var(--text-sm)] font-medium text-[var(--text)]"
        >
          {label}
        </label>
        <span
          className="text-[var(--text-xs)] font-mono tabular-nums px-1.5 py-0.5 rounded-[var(--radius-xs)] bg-[var(--surface-sunken)] text-[var(--text-muted)]"
          aria-live="polite"
        >
          {displayValue}
        </span>
      </div>
      <div className="relative">
        <div
          aria-hidden="true"
          className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-[var(--surface-sunken)] border border-[var(--border)]"
        />
        <div
          aria-hidden="true"
          className="absolute left-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-[var(--accent)]"
          style={{ width: `${pct}%` }}
        />
        <input
          id={fieldId}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          aria-label={`${label}: ${displayValue}`}
          className={cn(
            "relative w-full h-6 appearance-none bg-transparent cursor-pointer",
            "[&::-webkit-slider-thumb]:appearance-none",
            "[&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4",
            "[&::-webkit-slider-thumb]:rounded-full",
            "[&::-webkit-slider-thumb]:bg-[var(--surface-raised)]",
            "[&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-[var(--accent)]",
            "[&::-webkit-slider-thumb]:shadow-[var(--shadow-sm)]",
            "[&::-webkit-slider-thumb]:transition-transform",
            "[&::-webkit-slider-thumb]:duration-[var(--duration-fast)]",
            "[&::-webkit-slider-thumb]:ease-[var(--ease-out)]",
            "[&::-webkit-slider-thumb]:hover:scale-110",
            "[&::-webkit-slider-thumb]:active:scale-95",
            "[&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4",
            "[&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0",
            "[&::-moz-range-thumb]:bg-[var(--surface-raised)]",
            "[&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-[var(--accent)]",
            "focus-visible:outline-none",
          )}
        />
      </div>
      {hint && (
        <p className="text-[var(--text-xs)] text-[var(--text-muted)]">{hint}</p>
      )}
    </div>
  );
}
