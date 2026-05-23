const LANGUAGE_NAMES: Record<string, string> = {
  tel: "Telugu",
  hin: "Hindi",
  eng: "English",
};

export function getLanguageName(code: string): string {
  return LANGUAGE_NAMES[code] ?? code;
}
