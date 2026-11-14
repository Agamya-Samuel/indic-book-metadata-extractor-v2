#!/usr/bin/env node
/**
 * Contrast check for the design tokens in app/globals.css.
 *
 * The palette is authored in OKLCH, so the DOM can't be measured directly
 * (getComputedStyle returns lab()/oklch() and canvas fillStyle refuses them).
 * This resolves the tokens offline with a real OKLCH -> sRGB conversion and
 * checks the semantic pairs the components actually use, in both themes.
 *
 *   node scripts/check-contrast.mjs      (or: npm run lint:contrast)
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const CSS = readFileSync(join(here, "..", "src", "app", "globals.css"), "utf8")
  // Strip comments first: a comment mentioning --token: value would otherwise
  // be tokenised as a declaration.
  .replace(/\/\*[\s\S]*?\*\//g, "");

// --- token extraction -------------------------------------------------------

function block(selector) {
  const start = CSS.indexOf(`${selector} {`);
  if (start === -1) throw new Error(`selector not found: ${selector}`);
  const end = CSS.indexOf("}", start);
  return CSS.slice(start, end);
}

function tokens(source) {
  const out = {};
  for (const [, name, value] of source.matchAll(/--([\w-]+):\s*([^;]+);/g)) {
    out[name] = value.trim();
  }
  return out;
}

const root = tokens(block(":root"));
const dark = { ...root, ...tokens(block(".dark")) };

/** Resolve var() chains; returns a colour string like oklch(...) or #fff. */
function resolve(theme, name, seen = new Set()) {
  if (seen.has(name)) throw new Error(`circular token: ${name}`);
  seen.add(name);
  const raw = theme[name];
  if (raw === undefined) throw new Error(`unknown token: --${name}`);
  const ref = raw.match(/^var\(--([\w-]+)\)$/);
  return ref ? resolve(theme, ref[1], seen) : raw;
}

// --- colour maths -----------------------------------------------------------

const srgb = (x) => (x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055);
const clamp01 = (x) => Math.min(1, Math.max(0, x));

function parseColour(value) {
  const hex = value.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const h = hex[1].length === 3 ? hex[1].replace(/./g, (c) => c + c) : hex[1];
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  }
  const oklch = value.match(/oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)/i);
  if (oklch) {
    const [L, C, h] = oklch.slice(1, 4).map(Number);
    const rad = (h * Math.PI) / 180;
    return oklabToSrgb(L, C * Math.cos(rad), C * Math.sin(rad));
  }
  throw new Error(`unsupported colour: ${value}`);
}

function oklabToSrgb(L, a, b) {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [
    srgb(clamp01(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s)),
    srgb(clamp01(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s)),
    srgb(clamp01(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s)),
  ];
}

const luminance = ([r, g, b]) =>
  0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);

const ratio = (fg, bg) => {
  const [a, b] = [luminance(fg), luminance(bg)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
};

/** Composite a colour at `alpha` over a backdrop (what `/20` classes do). */
const over = (fg, bg, alpha) => fg.map((c, i) => c * alpha + bg[i] * (1 - alpha));

// --- the pairs components actually render ----------------------------------

/** fg, backdrop, optional backdrop alpha (composited over `base`), min ratio. */
const SEMANTIC = [
  ["body text", "text", "background", 1, 4.5],
  ["card text", "text", "surface", 1, 4.5],
  ["muted text on card", "text-muted", "surface", 1, 4.5],
  ["muted text on page", "text-muted", "background", 1, 4.5],
  ["subtle text on card", "text-subtle", "surface", 1, 4.5],
  ["muted text on sunken", "text-muted", "surface-sunken", 1, 4.5],
  ["text on sunken", "text", "surface-sunken", 1, 4.5],
  ["active nav / rail", "accent-soft-text", "accent-soft", 1, 4.5],
  ["link on card", "accent-text", "surface", 1, 4.5],
  ["link on page", "accent-text", "background", 1, 4.5],
  ["link on sunken", "accent-text", "surface-sunken", 1, 4.5],
  ["spinner/graphic on card", "accent-text", "surface", 1, 3],
  ["selection border vs card", "accent-ring", "surface", 1, 3],
  ["selection border vs page", "accent-ring", "background", 1, 3],
  ["selection border vs sunken", "accent-ring", "surface-sunken", 1, 3],
  ["primary button label", "btn-text-inverse", "accent", 1, 4.5],
  ["danger button label", "btn-text-inverse", "danger-600", 1, 4.5],
  ["secondary button label", "btn-text", "surface-raised", 1, 4.5],
  ["focus ring vs page", "focus-ring", "background", 1, 3],
];

const BANNERS = [
  ["danger banner", "danger-700", "danger-100", "danger-50", "danger-900"],
  ["success banner", "success-700", "success-100", "success-50", "success-900"],
  ["warning banner", "warning-700", "warning-100", "warning-50", "warning-900"],
  ["info banner", "info-700", "info-100", "info-50", "info-900"],
];

function checkTheme(theme, isDark) {
  const rows = [];
  const get = (name) => parseColour(resolve(theme, name));

  for (const [label, fg, bg, alpha, min] of SEMANTIC) {
    const backdrop = get(bg);
    const colour = alpha === 1 ? backdrop : over(get(bg), get("surface"), alpha);
    rows.push({ label, value: ratio(get(fg), colour), min });
  }

  // Banners: light uses the 50-tone background, dark the 900-tone at 20%.
  for (const [label, fgLight, fgDark, bgLight, bgDark] of BANNERS) {
    const surface = get("surface");
    if (isDark) {
      const colour = over(get(bgDark), surface, 0.2);
      rows.push({ label, value: ratio(get(fgDark), colour), min: 4.5 });
      rows.push({
        label: `${label} (chip on card)`,
        value: ratio(get(fgDark), surface),
        min: 4.5,
      });
    } else {
      rows.push({ label, value: ratio(get(fgLight), get(bgLight)), min: 4.5 });
    }
  }

  return rows.map((r) => ({ ...r, pass: r.value >= r.min }));
}

function report(themeName, rows) {
  console.log(`\n${themeName}`);
  let failed = 0;
  for (const r of rows) {
    if (!r.pass) failed += 1;
    const mark = r.pass ? "ok  " : "FAIL";
    console.log(
      `  ${mark} ${r.value.toFixed(2).padStart(5)} (min ${r.min})  ${r.label}`,
    );
  }
  return failed;
}

const lightRows = checkTheme(root, false);
const darkRows = checkTheme(dark, true);
let failed = report("light", lightRows);
failed += report("dark", darkRows);

console.log(
  failed === 0
    ? "\nAll semantic pairs meet their contrast target."
    : `\n${failed} pair(s) below target.`,
);
process.exit(failed === 0 ? 0 : 1);
