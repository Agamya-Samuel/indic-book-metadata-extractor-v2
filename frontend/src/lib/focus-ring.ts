/**
 * Focus ring token set.
 *
 * The standard focus ring appears on every interactive element — buttons,
 * links styled as buttons, nav links, dropzone, etc. Extracting it prevents
 * drift and keeps the focus style consistent across the product surface.
 *
 * All variants share the same core: 2px ring, `--focus-ring` color,
 * `--offset-*` to `--background`, `outline: none` (replaced by the ring).
 *
 * - `focusRing`        — the default offset-2 variant (most common)
 * - `focusRingInset`   — `ring-inset` variant for elements that need the ring
 *                       drawn inside the element box (collapsible headers, etc.)
 * - `focusRingOffset1` — offset-1 variant for small controls where offset-2
 *                       would create too large a gap (word buttons, etc.)
 */
export const focusRing =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]";

export const focusRingInset =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-inset";

export const focusRingOffset1 =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--background)]";
