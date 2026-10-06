/** Checks every translated string in the app (i18n.tsx and each screen's own dictionary).
 * These checks cannot judge wording: a native speaker must review the Telugu, Urdu and Hindi
 * (docs/translation_review/). They catch what a reviewer should never have to: missing strings,
 * broken placeholders, English left in place of a translation, the wrong script. */
import { describe, expect, it } from "vitest";
import { extractTranslations, placeholders, SCRIPTS, isProse, type Entry } from "../scripts/i18nExtract.mjs";

const raw = import.meta.glob("./*.tsx", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
const sources = Object.fromEntries(Object.entries(raw).map(([path, text]) => [path.replace("./", "src/"), text]));
const entries: Entry[] = extractTranslations(sources);
const OTHERS = ["te", "ur", "hi"] as const;

describe("translations", () => {
  it("are found in i18n.tsx and in every screen that has its own dictionary", () => {
    const files = new Set(entries.map((entry) => entry.file));
    expect([...files].sort()).toEqual([
      "src/DriverExperience.tsx",
      "src/EvidenceExperience.tsx",
      "src/ExplainExperience.tsx",
      "src/FieldWorkerExperience.tsx",
      "src/ForecastExperience.tsx",
      "src/ImpactExperience.tsx",
      "src/OfficerOverview.tsx",
      "src/PlanExperience.tsx",
      "src/ResidentExperience.tsx",
      "src/SectionOutcomeForm.tsx",
      "src/i18n.tsx",
    ]);
    expect(entries.length).toBeGreaterThan(400);
  });

  it("exist in all four languages for every key", () => {
    const missing = entries.flatMap((entry) =>
      (["en", ...OTHERS] as const).filter((locale) => !entry[locale]?.trim()).map((locale) => `${entry.file} ${entry.key} (${locale})`),
    );
    expect(missing).toEqual([]);
  });

  it("keep exactly the placeholders of the English text", () => {
    const broken = entries.flatMap((entry) => {
      const expected = placeholders(entry.en ?? "");
      return OTHERS.filter((locale) => placeholders(entry[locale] ?? "") !== expected).map(
        (locale) => `${entry.file} ${entry.key} (${locale}): ${placeholders(entry[locale] ?? "")} vs ${expected}`,
      );
    });
    expect(broken).toEqual([]);
  });

  it("are written in the language's own script and are not the English text again", () => {
    const wrong = entries.flatMap((entry) => {
      if (!isProse(entry.en ?? "")) return []; // codes, numbers and labels like "SIMULATION" stay as they are
      return OTHERS.filter((locale) => {
        const text = entry[locale] ?? "";
        return text === entry.en || !SCRIPTS[locale].test(text);
      }).map((locale) => `${entry.file} ${entry.key} (${locale}): ${entry[locale]}`);
    });
    expect(wrong).toEqual([]);
  });
});

describe("translations, English left behind", () => {
  // CSV column names must stay in English: the header of a bookings file has to match them. A
  // hyphenated term ("seasonal-naive", a method name) counts as one word.
  const COLUMN_NAMES = new Set(["booking_id", "section", "arrived_at", "consumer_id", "category", "tier"]);
  const englishWords = (text: string) => (text.replace(/\{[A-Za-z0-9_]+\}/g, "").match(/\b[a-z]{3,}(?:-[a-z]+)*\b/g) ?? []).filter((word) => !COLUMN_NAMES.has(word));

  it("have no run of English words in place of a translation", () => {
    const left = entries.flatMap((entry) =>
      OTHERS.filter((locale) => englishWords(entry[locale] ?? "").length >= 2).map((locale) => `${entry.file} ${entry.key} (${locale}): ${entry[locale]}`),
    );
    expect(left).toEqual([]);
  });
});

describe("the checks themselves", () => {
  const sample = (te: string) => ({
    "src/Sample.tsx": `const liveEn = { greet: "Hello {name}, welcome", code: "OTP" };
const copy = { en: liveEn, te: { greet: ${JSON.stringify(te)}, code: "OTP" }, ur: { greet: "سلام {name}", code: "OTP" }, hi: { greet: "नमस्ते {name}", code: "OTP" } };`,
  });

  it("read a locale given by name and keep codes that are not prose", () => {
    const found = extractTranslations(sample("నమస్కారం {name}"));
    expect(found).toEqual([
      { file: "src/Sample.tsx", block: 1, key: "greet", en: "Hello {name}, welcome", te: "నమస్కారం {name}", ur: "سلام {name}", hi: "नमस्ते {name}" },
      { file: "src/Sample.tsx", block: 1, key: "code", en: "OTP", te: "OTP", ur: "OTP", hi: "OTP" },
    ]);
    expect(isProse("OTP")).toBe(false);
    expect(isProse("Hello {name}")).toBe(true);
  });

  it("would catch a dropped placeholder, English left in place, and the wrong script", () => {
    const [dropped] = extractTranslations(sample("నమస్కారం"));
    expect(placeholders(dropped.te ?? "")).not.toBe(placeholders(dropped.en ?? ""));
    const [copied] = extractTranslations(sample("Hello {name}, welcome"));
    expect(copied.te === copied.en || !SCRIPTS.te.test(copied.te ?? "")).toBe(true);
    const [devanagari] = extractTranslations(sample("नमस्ते {name}"));
    expect(SCRIPTS.te.test(devanagari.te ?? "")).toBe(false);
  });

  it("cover all the app's strings", () => {
    console.info(`translation checks covered ${entries.length} strings in ${new Set(entries.map((e) => e.file)).size} files`);
    expect(entries.filter((entry) => isProse(entry.en ?? "")).length).toBeGreaterThan(400);
  });
});
