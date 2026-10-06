# Hand-off prompt: fix the low-bookings check (F3 / F4, E5)

Paste everything below the line into a new agent session started in the repo root
(`C:\Users\524ta\OneDrive\Desktop\ps\jallekha-v2`).

---

You are working on JalLekha 2.0 (PS11, Hyderabad water tankers, HMWSSB). Read `CLAUDE.md` first,
then `docs/JALLEKHA_FINAL_SOLUTION.md` sections F1-F4 (lines ~79-88), `docs/LIMITATIONS.md`
sections F3 and F4, and `docs/api_additions/atlas_live.md`. Follow every rule in `CLAUDE.md`
(TDD, basis labels in data/API/docs, honest results, every UI string in en/te/ur/hi, docs updated
with each change). **Owner rule for this work: build and commit locally on a branch; do not push,
open a PR or merge until the owner says "approve". Do not run the full `tasks.py test` after every
change; run the affected test files, and the full lint + test once before asking for approval.**

## The problem (verified 2026-10-06)

The U5 "Low bookings" tab and the ward "Booking check" panel compare each ward's 2025 bookings
(`observed_bookings` in `data/derived/underserved/field_checks.json`, built by
`scripts/evidence/build_underserved.py`, `PERIOD_YEAR = 2025`) with two references: the peer median
(5 similar wards) and a negative-binomial model (NB). Checked against the actual 2025 bookings of
the 107 scored wards:

| Method | Spearman rank corr | median miss | within 2x |
|---|---|---|---|
| NB model | 0.30 | 5.2x | 22% |
| Peer median | 0.44 | 3.7x | 27% |
| Baseline: households_2025 x city bookings per household | 0.48 | 5.4x | 21% |

(Households: `data/derived/population/ward_population_2025.csv` `households_2025_central`.)
NB is no better than the trivial baseline. Root cause is the **observed side**: HMWSSB publishes
bookings per section, and `data/derived/crosswalk/section_to_ward_2016.csv` pins each section to
ONE ward by one geocoded point, so all its bookings land in that ward. 69 of the 107 wards have one
section pinned, 28 have two. **All 6 flagged wards have only 1-2 sections pinned** (Kanchanbagh
11, Shastripuram 11, Falaknuma 24, Barkas 31, IS Sadan 151, Chandrayangutta 405 bookings in 2025),
so the flags are most likely placement artefacts, not people failing to book. Kapra "booked 44"
only because two tiny sections (Dammaiguda, Sainikpuri) were pinned there. In the 10 wards with 3+
sections the ranking is much better (0.75-0.92) but still about 4x off. The design doc F3 already
says ward booking counts must stay null until an authoritative section-to-ward transfer exists;
the current ward booking map breaks that. There is no ground truth (0 field-check outcomes).

## What to build, in order (one branch each, commit locally)

### 1a. Section-level low-bookings check (`feat/e5-section-check`) — do this first
Section booking counts are exact (no placement). Build the check per HMWSSB section:
- Data: monthly bookings per section `data/raw/hmwssb_tankers_portal/*.csv` (to 2026-08; sections
  were re-cut in Feb/Mar 2026, so use calendar 2025, or 2024 + 2025 separately); connections per
  section from HMWSSB billing (`data/raw/hmwssb_billing_portal/*.csv`, column `noofcans` by
  `category`; domestic categories as in `data/derived/equity/summary.json`
  `section_rate_denominator`). `data/derived/equity/sections.csv` already has
  `bookings_per_1000_connections` for 2022-Feb 2024 — reuse its method.
- Rate = bookings per 1,000 domestic connections. Reference = median rate of comparable sections
  (same division / similar connection count / similar flats share `flats_connection_share`), with
  the target section excluded. Flag a section when its rate is far below the reference (threshold
  in a config file, ASSUMED, e.g. below the 20th percentile ratio as E5 uses) AND its area has high
  need (WAD of the ward its point falls in above the cohort median) — need is context only.
- Validate honestly: out-of-sample, use 2024 to set references and check 2025; report rank
  correlation and median miss against the baseline "section connections x city rate". Write the
  numbers to `docs/LIMITATIONS.md` F4 whatever they are.
- Output `data/derived/underserved/section_checks.csv` (+ verifier in `scripts/evidence/`), an API
  route (officer) `GET /underserved/section-checks`, `docs/api_additions/`, `docs/openapi.json`
  (`python scripts/api/export_openapi.py`).
- U5 (`frontend/src/EvidenceExperience.tsx`): the "Low bookings" tab lists flagged **sections**
  (name, bookings in 2025, rate per 1,000 connections, similar sections' rate) in plain words, no
  basis labels on screen (owner decision), plus a dot per flagged section on the map at its point
  (from the crosswalk lat/lng). Remove the ward "Booking check" panel numbers (or replace with the
  ward's flagged sections). All strings in en/te/ur/hi, then `npm run i18n:export` in `frontend/`.

### 1b. Split section bookings across wards by buildings (`feat/booking-dasymetric`)
Replace one-point pinning with dasymetric areal interpolation weighted by building footprints
(literature: building-footprint dasymetric beats areal weighting). No section boundaries are
public, so approximate each section's area as the Voronoi cell of its point (all section points),
clipped to its HMWSSB division's extent (convex hull of that division's section points + buffer)
and to the GHMC ward union; split each section's bookings over wards by the share of its buildings
(Open Buildings, `data/raw/d6_open_buildings/`, see `scripts/evidence/` E3 build) falling in each
ward. Label every ward count DERIVED_APPROXIMATE with the method. Rebuild `data/derived/equity/
wards.csv` (and anything that reads it: check with grep), re-run the E5 comparison table above and
report whether it improved. Note the checksum trap in `CLAUDE.md` if any manifest row changes.

### 2. Better model (`feat/e5-underreporting`) — only after 1a/1b
Under-reporting framework (Stoner et al. 2019, JASA, arXiv 1809.00544): observed bookings ~
Binomial(true demand, booking probability); true demand from need (households x WAD, non-tap
share); booking probability from access (CAD = share with no phone, hardship, distance to the
nearest stand-in station `data/derived/sandbox/stations.csv`). Fit at section level (or on the 1b
ward counts). Keep it only if it beats the baseline out of sample (2024 -> 2025); otherwise record
that it lost in `LIMITATIONS.md` F4. **Trap:** E5's BYM2 models are fitted on Linux only; never
re-sample them on Windows. Use PyMC from `.venv` only for new non-spatial models, seeded.

### 3. Ground truth loop
Field workers (U3 `FieldWorkerExperience.tsx`) or officers record a check outcome per flagged
section ("people could not book: yes / no / unclear", date, note). Store it (new SQLAlchemy model,
ledger event added to `EVENT_TYPES` in `services/ledger.py`, reasons as SHA-256 on the ledger),
show the running precision of the flags once there are 30+ outcomes. Until then the screen says
"not yet checked on the ground".

## Also send (owner action, not code)
An RTI to HMWSSB for O&M section boundary maps (GIS; HMWSSB already publishes layers via PM Gati
Shakti, e.g. sewer lines on data.opencity.in). With real boundaries, 1b becomes exact.

## Done when
Each step: tests written first and seen failing, then passing; docs updated (`LIMITATIONS.md` F3/F4,
`REMAINING_WORK.md`, `BRANCH_WORKLOG.md`, `features.csv`, API docs); the accuracy table re-run and
reported honestly; committed locally; summary sent to the owner for approval.

---

# Hand-off 2: demand forecast and shortage warning (F5, F6)

Paste everything below this line into a new agent session (same rules as above: read `CLAUDE.md`,
`docs/JALLEKHA_FINAL_SOLUTION.md` F5/F6, `docs/LIMITATIONS.md` F5/F6; TDD; honest results; every UI
string in en/te/ur/hi; no basis labels on screen (owner decision, keep them in data/API/docs);
**commit locally, do not push or merge until the owner says "approve"**).

## What F5/F6 must do (design doc)
Predict tanker bookings for the **next 12 months**, city and per HMWSSB section; compare with the
fleet's capacity (1,123 tankers x 9 trips a day, `config/forecast.py`, DERIVED); warn 1-3 months
ahead which sections may run short, with reasons (F6, `services/shortage.py`).

## What is wrong now (verified 2026-10-06)
- **Stale:** training stops at Jan 2026 (`config/forecast.py` `portal_through = (2026, 1)`) because
  HMWSSB re-cut its sections in Feb/Mar 2026 (old and new section names do not match). The
  "12-month outlook" is Feb 2026 - Jan 2027, so 8 of its months are already past.
- **Inaccurate:** the selected model (`global_gbm`, gradient boosting + Open-Meteo weather, chosen by
  the research-A rule in `services/forecast.py` `select`) ties seasonal naive on the real Feb-Aug
  2026 city totals (MAPE 31.1% vs 31.8%) and badly under-forecast the 2026 summer: May 2026 actual
  319,106 vs 228,302 forecast; Aug 2026 actual 164,367 vs about 54,000-57,000.
- **No city range:** city rows have no interval ("section intervals do not add up").
- **Confusing chart:** `frontend/src/ForecastExperience.tsx` `OutlookChart` draws history and a
  forecast whose months are mostly past on one line; the owner could not read it.
- Data on disk: monthly bookings per section `data/raw/hmwssb_tankers_portal/*.csv` to 2026-08;
  weather `data/raw/d8_weather/`, `data/derived/weather/`; groundwater `data/derived/groundwater/`;
  backtest script `scripts/forecast/run_backtest.py` (writes `data/derived/forecast_*.csv`);
  shortage `scripts/forecast/run_shortage.py`. Reservoir levels: a source exists (Open Data
  Telangana "Telangana Irrigation & CAD Department - Daily Reservoir Storage Levels", 67 monthly
  CSV files Jan 2021 - Jul 2026, catalogue API like `scripts/data/fetch_d7_groundwater.py`;
  Nagarjuna Sagar, Singur, Sri Pada Yellampally, Akkampalli, Srisailam) - owner accepted it (Q2).

## Steps (branch `feat/f5-forecast-refresh`)
1. **City forecast from the latest month.** City totals are not affected by the re-cut: train on
   all months through the latest available (2026-08), forecast 12 months ahead (Sep 2026 - Aug
   2027). Re-run the rolling-origin backtest including 2026 and keep the research-A selection rule
   (beat seasonal naive on both measures + HLN Diebold-Mariano). Try, as candidates scored the same
   way: last 12-month trend / level shift, groundwater anomaly, reservoir storage (Q2 data above),
   and summer-peak features. Report honestly what wins and by how much; if nothing beats naive,
   say so in `LIMITATIONS.md` F5.
2. **City range:** split-conformal interval on city totals from the backtest (same method as the
   section intervals), 80% and 90%, with measured coverage.
3. **Sections across the re-cut:** build an old-to-new section crosswalk (names, divisions,
   geocoded points in `data/derived/crosswalk/section_to_ward_2016.csv`, overlap of bookings);
   label matches exact / approximate / unmatched; forecast new sections from their matched history;
   unmatched sections say so.
4. **Monthly refresh:** one command (or a `tasks.py` entry) that pulls the new portal month,
   retrains, rewrites the forecast and shortage files; document it. The screen shows "updated
   <month>".
5. **F6 shortage** recomputed from the new forecast (risk 1-3 months ahead), reasons in plain words;
   add reservoir storage to the reasons like groundwater (context, not in the risk rule).
6. **Redraw the screen** (`ForecastExperience.tsx`, `.css`, tests), two clear views:
   - **"Next 12 months"**: title like "Tankers expected per month, Sep 2026 - Aug 2027"; last 12
     months of actual bookings (solid) then the forecast (dashed) with a shaded range and the fleet
     capacity line; hover shows month, expected, range, capacity, and "short by N" if any.
   - **"How good was our forecast?"**: for past months, forecast vs actual in plain sentences
     ("May 2026: we expected 228,302, actual 319,106 - 29% too low") and one overall accuracy line.
   No technical words (MAPE, WAPE, seasonal naive, DERIVED) on screen; keep them in docs.
   Section view: pick a section, same two views.

## Done when
Forecast starts at the month after the latest data; city range shown; backtest and the 2026
out-of-sample numbers reported in `LIMITATIONS.md` F5 whatever they are; shortage list rebuilt;
screen redrawn and understandable without explanation; tests first; docs updated
(`REMAINING_WORK.md`, `BRANCH_WORKLOG.md`, `features.csv`, API docs/examples if shapes change);
committed locally; summary to the owner for approval.
