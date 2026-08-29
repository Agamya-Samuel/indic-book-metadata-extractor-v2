"use client";

import * as React from "react";

type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

const ThemeContext = React.createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "indic-books-theme";

/**
 * Manages the `dark` class on <html> and persists the user's preference
 * to localStorage. On first paint the inline script in <head> sets the
 * class to avoid a flash of wrong theme.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Read the initial theme from the class set by the no-flash inline script
  // BEFORE React renders, so the toggle reflects the right state on first paint.
  // We use lazy initialization to avoid an effect-driven setState cascade.
  const [theme, setThemeState] = React.useState<Theme>(() => {
    if (typeof document === "undefined") return "light";
    return document.documentElement.classList.contains("dark")
      ? "dark"
      : "light";
  });

  const setTheme = React.useCallback((next: Theme) => {
    setThemeState(next);
    if (next === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* localStorage unavailable; keep memory state only */
    }
  }, []);

  const toggle = React.useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  const value = React.useMemo(
    () => ({ theme, setTheme, toggle }),
    [theme, setTheme, toggle],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = React.useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within <ThemeProvider>");
  }
  return ctx;
}

/** Inline script for <head>: sets the `dark` class before paint to avoid FOUC. */
export const themeInitScript = `
(function(){try{var s=localStorage.getItem('${STORAGE_KEY}');var m=window.matchMedia('(prefers-color-scheme: dark)').matches;var d=s?s==='dark':m;if(d){document.documentElement.classList.add('dark');}}catch(e){}})();
`.trim();
