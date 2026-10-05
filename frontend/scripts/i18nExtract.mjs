// Reads every translation dictionary in the app's source: i18n.tsx (`english` plus `translated`)
// and the screens' own `{ en: {...}, te: {...}, ur: {...}, hi: {...} }` objects. Used by the
// quality tests (src/i18nQuality.test.ts) and by the review-pack export (exportTranslations.mjs).
import ts from "typescript";

export const LOCALES = ["en", "te", "ur", "hi"];

/** Each language's own script: Telugu, Arabic (Urdu), Devanagari (Hindi). */
export const SCRIPTS = {
  te: /[ఀ-౿]/,
  ur: /[؀-ۿ]/,
  hi: /[ऀ-ॿ]/,
};

const PLACEHOLDER = /\{[A-Za-z0-9_]+\}/g;

/** The placeholders of a string, sorted and de-duplicated, as one comparable string. */
export function placeholders(text) {
  return [...new Set(text.match(PLACEHOLDER) ?? [])].sort().join(" ");
}

/** True for running text (a word of three lowercase letters outside placeholders). Codes,
 * numbers and labels such as "SIMULATION" or "OTP" are not prose and may stay as they are. */
export function isProse(text) {
  return /[a-z]{3,}/.test(text.replace(PLACEHOLDER, ""));
}

function keyOf(name) {
  if (ts.isIdentifier(name) || ts.isStringLiteral(name)) return name.text;
  return null;
}

function strings(object) {
  const out = new Map();
  for (const property of object.properties) {
    if (!ts.isPropertyAssignment(property)) continue;
    const key = keyOf(property.name);
    const value = property.initializer;
    if (key && (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value))) out.set(key, value.text);
  }
  return out;
}

function unwrap(node) {
  // `{...} as const`, `{...} satisfies X`, `({...})`
  while (node && (ts.isAsExpression(node) || ts.isSatisfiesExpression?.(node) || ts.isParenthesizedExpression(node))) node = node.expression;
  return node;
}

/** One entry per key of each dictionary: { file, block, key, en, te, ur, hi } (null when absent). */
export function extractTranslations(sources) {
  const entries = [];
  for (const [file, text] of Object.entries(sources).sort(([a], [b]) => a.localeCompare(b))) {
    const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    // Named objects in this file, for a locale given by name (`en: liveEn`); i18n.tsx keeps its
    // English in `const english = {...}` and does not name it in `translated`.
    const named = new Map();
    const blocks = [];
    const collect = (node) => {
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
        const value = unwrap(node.initializer);
        if (value && ts.isObjectLiteralExpression(value)) named.set(node.name.text, strings(value));
      }
      ts.forEachChild(node, collect);
    };
    collect(source);
    const english = named.get("english") ?? null;
    const visit = (node) => {
      if (ts.isObjectLiteralExpression(node)) {
        const byLocale = {};
        for (const property of node.properties) {
          if (!ts.isPropertyAssignment(property)) continue;
          const key = keyOf(property.name);
          const value = unwrap(property.initializer);
          if (!LOCALES.includes(key) || !value) continue;
          if (ts.isObjectLiteralExpression(value)) byLocale[key] = strings(value);
          else if (ts.isIdentifier(value) && named.has(value.text)) byLocale[key] = named.get(value.text);
        }
        if (byLocale.te || byLocale.ur || byLocale.hi) blocks.push(byLocale);
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
    blocks.forEach((byLocale, index) => {
      if (!byLocale.en && english) byLocale.en = english;
      const keys = [];
      for (const locale of LOCALES) for (const key of byLocale[locale]?.keys() ?? []) if (!keys.includes(key)) keys.push(key);
      for (const key of keys) {
        const entry = { file, block: index + 1, key };
        for (const locale of LOCALES) entry[locale] = byLocale[locale]?.get(key) ?? null;
        entries.push(entry);
      }
    });
  }
  return entries;
}

function cell(value) {
  const text = value ?? "";
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

/** The review pack: one row per string, the three translations beside the English, and empty
 * columns for the reviewer. UTF-8 with a byte order mark so spreadsheet programs read the
 * Telugu, Urdu and Hindi correctly. */
export function toCsv(entries) {
  const header = ["file", "block", "key", "english", "telugu", "urdu", "hindi", "telugu_ok", "urdu_ok", "hindi_ok", "reviewer_notes"];
  const rows = entries.map((e) => [e.file, String(e.block), e.key, e.en, e.te, e.ur, e.hi, "", "", "", ""].map(cell).join(","));
  return "﻿" + [header.join(","), ...rows].join("\r\n") + "\r\n";
}
