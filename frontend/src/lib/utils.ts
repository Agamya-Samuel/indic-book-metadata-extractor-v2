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
