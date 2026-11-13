const LANGUAGE_NAMES: Record<string, string> = {
  tel: "Telugu",
  hin: "Hindi",
  eng: "English",
};

export function getLanguageName(code: string): string {
  return LANGUAGE_NAMES[code] ?? code;
}

/** Tiny className joiner. Filters out falsy values, joins with spaces. */
export function cn(
  ...parts: Array<string | number | false | null | undefined>
): string {
  return parts.filter(Boolean).join(" ");
}

/** Human-readable elapsed time, e.g. "45s", "2m 30s", "1h 5m". */
export function formatElapsed(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return "0s";
  const totalSeconds = Math.floor(ms / 1000);
  const seconds = totalSeconds % 60;
  const minutes = Math.floor(totalSeconds / 60);
  if (minutes <= 0) return `${seconds}s`;
  const hours = Math.floor(minutes / 60);
  if (hours <= 0) return `${minutes}m ${seconds}s`;
  return `${hours}h ${minutes % 60}m`;
}

/** "Page 12 of 84" style counters. */
export function formatCounters(done: number, total: number): string {
  return `${done} of ${total}`;
}

/** Short age for a timestamp, e.g. "just now", "5m ago", "3d ago". */
export function formatRelativeTime(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "";
  const diffSeconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (diffSeconds < 60) return "just now";
  const minutes = Math.floor(diffSeconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(then).toLocaleDateString();
}
