// Writes the translation review pack, docs/translation_review/translations.csv: every string of
// the app with its Telugu, Urdu and Hindi translation and empty columns for the reviewer.
//   npm run i18n:export   rewrite the pack after changing any string
//   npm run i18n:check    fail if the committed pack no longer matches the source (tasks.py test)
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { extractTranslations, toCsv } from "./i18nExtract.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "src");
const out = join(here, "..", "..", "docs", "translation_review", "translations.csv");

const sources = Object.fromEntries(
  readdirSync(src)
    .filter((name) => /\.tsx?$/.test(name) && !/\.(test|d)\.tsx?$/.test(name))
    .map((name) => [`src/${name}`, readFileSync(join(src, name), "utf8")]),
);
const entries = extractTranslations(sources);
const csv = toCsv(entries);
const normalised = (text) => text.replace(/\r\n/g, "\n"); // git may store or check out other line ends

if (process.argv.includes("--check")) {
  if (!existsSync(out) || normalised(readFileSync(out, "utf8")) !== normalised(csv)) {
    console.error(`${out} is out of date: run npm run i18n:export and commit it`);
    process.exit(1);
  }
  console.log(`Translation review pack is current (${entries.length} strings)`);
} else {
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, csv, "utf8");
  console.log(`Wrote ${out} (${entries.length} strings)`);
}
