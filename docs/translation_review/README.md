# Translation review: Telugu, Urdu, Hindi

The app's Telugu, Urdu and Hindi text was written without a native-speaker review. Until a
reviewer signs a language off, the app shows a "this translation is a draft" notice in that
language. This folder is everything a reviewer needs.

## What is here

| File | What it is |
|---|---|
| `translations.csv` | Every string in the app (807 rows): file, key, the English, and the Telugu, Urdu and Hindi drafts, plus empty columns `telugu_ok`, `urdu_ok`, `hindi_ok` and `reviewer_notes`. UTF-8 with a byte order mark, so Excel and LibreOffice show the scripts correctly. |
| `GLOSSARY.md` | The words used for the project's key terms in each language, how often, and where the drafts are inconsistent. Settle these first: they repeat across many strings. |

## How to review (one language at a time)

1. Settle the glossary terms for your language (`GLOSSARY.md`, "Choose one" rows).
2. Go through `translations.csv`. For each row, put `yes` in your language's `_ok` column if the
   draft is right, or write the corrected text in `reviewer_notes` (prefix it with your language,
   for example `te: ...`).
3. Keep every `{placeholder}` exactly as it is (the app fills them in), and keep the CSV column
   names (`booking_id`, `section`, `arrived_at`, `consumer_id`, `category`, `tier`) in English:
   the header of a bookings file has to match them. Words like SIMULATION, ASSUMED, DERIVED,
   REAL, OTP, SMS and API are labels and stay as they are.
4. Send the file back. Plain wording matters more than formal wording: the readers include
   residents with little schooling (see `docs/research/P4.md`).

## How a developer applies a review

1. Change the strings in the source file named in the `file` column (each screen keeps its own
   dictionary; shared strings are in `frontend/src/i18n.tsx`).
2. Run `npm run i18n:export` in `frontend/` and commit the updated `translations.csv`
   (`python tasks.py test` fails while the file is out of date).
3. When a whole language is reviewed, set it to `"reviewed"` in `translationStatus` in
   `frontend/src/i18n.tsx`; the draft notice then disappears for that language.

## What is checked automatically

`frontend/src/i18nQuality.test.ts` checks every string on every test run: all four languages
present, the same placeholders as the English, the language's own script, no English sentence
left in place of a translation. It cannot judge whether the wording is right; only a reviewer can.
