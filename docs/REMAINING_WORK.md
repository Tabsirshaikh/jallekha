# JalLekha 2.0: remaining work (items 11 to 22)

Status on `main` as of 2026-10-05, after PR #66. Items 1 to 10 of the 22-item list are done
(PRs #64, #65) and so are the four follow-up fixes (PR #66). This file lists what is left: for
each item, what it is, where it stands in the code today, what blocks it, how to do it, and when
it counts as done. `docs/LIMITATIONS.md` has the full list of known limits; this file is the
to-do list.

| # | Item | Feature | Who can start it | Blocked by |
|---|---|---|---|---|
| 11 | Ward report cards with real deliveries, debt and schedule | F20 | **done** (`feat/f20-report-cards`) | — |
| 12 | Gradient-boosting forecast | F5 | **done** (`feat/f5-gbm-forecast`); adoption is the owner's rule | — |
| 13 | Voice error rate for Telugu and Urdu | F14 | us, after recordings | a small labelled voice set |
| 14 | Reproduce the duplicate calibration (71% / 88%) | F13 | **done** (`feat/f13-dedup-calibration`); text-similarity test skipped by owner decision | — |
| 15 | Hospital and school data (D9) in the ward table | F1, F8, F10 | **done** (`feat/d9-facilities`) | — |
| 16 | Weather data (D8) | F5 | **done** (with item 12) | — |
| 17 | Groundwater data (D7) | F5, F6 | us, after registering | NWDP account |
| 18 | Degraded-signal replay for the T9 threshold | F17 | **done** (`feat/t9-degraded-replay`); the 90% rule is the owner's | — |
| 19 | Seven owner decisions | several | owner | owner |
| 20 | Decide the stack (or edit the doc) | all | owner, then us | decision |
| 21 | Fix demo step 5 in the solution doc | docs | **done** (`docs/demo-step5-2025`) | — |
| 22 | "Done-when vs doc promise" column in `features.csv` | tracker | **done** (`docs/item-22-promise-column`) | — |

Order we will work in: 11, then 21 and 22 (quick), then 15, 16, 18, 14, then 12 once 16 is in,
then 17 and 13 when the data arrives. Item 19 runs alongside: each decision unblocks something.

---

## Finish features

### 11. Ward report cards with real deliveries, debt and schedule (F20, U10)

**Status: done** on `feat/f20-report-cards` (see `docs/api_additions/report_cards.md`). Built as researched: stops get a ward, supplied plans give scheduled water to the stops, an officer closes each day to settle water debt, the next plan uses the debt, and the card and U10 screen show all three live. The text below is the plan it followed.

**What it is.** One public page per ward (and a short SMS) that tells residents how much water
their ward needs, how many bookings it made, how many tanker visits were delivered and confirmed,
how much water the ward is still owed (water debt), and when the next tankers are planned.

**Why it matters.** It is the "open" part of the solution: residents can check the system
themselves. Today the card shows only need and bookings, so it cannot show whether service
actually arrived.

**Where it stands.**
- `GET /wards/{id}/report-card` and `/sms-summary` exist (`backend/app/routers/evidence.py`,
  `_report_card`). Need and bookings are real; `deliveries`, `debt` and `schedule` all return
  "unavailable" with old reasons ("no delivery store on main", "no plan store on main").
- Deliveries and plans are now stored in the database (PR #65), but:
  - a delivery belongs to a stop, and a stop has only a position (`delivery_stop`: lat, lon),
    no ward, so nothing says which ward a delivery served;
  - water debt (A6, `services/water_debt.py`) is a pure calculation: there is no stored debt
    account and nothing settles a day, so no ward has a debt to show;
  - a stored plan knows its groups (`ward:<id>` or `section:<name>`) and trips, but the card
    does not read it.
- The U10 screen (`frontend/src/ResidentExperience.tsx`, page "ward") shows sample cards marked
  SIMULATION and never calls the API.

**How to do it.**
1. **Deliveries per ward.** Give each stop a ward: the officer may name it when registering the
   stop; otherwise it is found by placing the stop's position on the 2016 ward polygons
   (`data/raw/geography/datameet/ghmc-wards.geojson`, shapely is already a dependency), marked
   DERIVED. Count the ward's deliveries by outcome (Confirmed, Disputed, Unconfirmed, Failed,
   still open) for the last 30 days.
2. **Schedule.** From the plan store, take the latest approved plan (else the latest draft,
   labelled DRAFT) and list the ward's trips: booked trips served and still waiting for the
   ward's group, scheduled-supply and outage trips with the ward's id, and the plan's day and
   basis (SIMULATION for replay plans, SUPPLIED for officer bookings).
3. **Water debt.** Store one debt account per ward and settle it per day from the approved plan
   (litres planned for the ward) against Confirmed deliveries at the ward's stops, using A6's
   `settle_day` unchanged (ledger entry per change, cap, alert). The card shows the balance, days
   in debt and whether the alert is raised. *Design decision to confirm before building: who
   triggers the daily settlement (an officer route or the plan approval) and whether planned
   litres are the right "entitled" amount.*
4. **Screen.** U10 calls the two routes when the API answers (residents can read it), shows each
   block with its badge (REAL / DERIVED / SIMULATION / unavailable with the reason), and falls
   back to the sample cards with the "Saved snapshot" chip, like the other screens.
5. Update `docs/LIMITATIONS.md` (F20), `docs/api_additions/`, `docs/openapi.json`.

**Done when.** For a ward with registered stops, closed deliveries and an approved plan, the card
shows the delivery counts by outcome, the debt balance and the planned trips, each with its basis,
and the U10 screen shows them live; a ward with none of these says "none yet" rather than a
sample number. Tests at service, API and screen level; `python tasks.py test` and `lint` pass.

### 12. Better F5 forecast: gradient boosting (F5, T2)

**Status: done** on `feat/f5-gbm-forecast`. Built with scikit-learn 1.9.1 (`models` extra) and the D8 weather data. It beats seasonal naive on both measures on the portal history (MAPE 23.21% vs 26.28%, WAPE 37.04% vs 47.67%) and is slightly worse on the short S2 files, so under the current OPEN rule the baseline stays published. See `docs/LIMITATIONS.md` F5. The text below is the plan it followed.

**What it is.** A second forecasting model: one gradient-boosting model pooled over all sections,
using month, last year's value (lag 12), trend, weather (D8) and groundwater depth (D7), as the
solution doc promises (Section 5, F5).

**Where it stands.** `backend/app/services/forecast.py` has seasonal naive and seasonal naive x
growth only. Neither beats the baseline on both measures, so the forecast is the baseline
(21.89% city MAPE, 35.12% section WAPE on 2022-24; 26.28% / 47.67% on the longer history).

**Blocked by.** Weather data (item 16); groundwater (item 17) is optional for a first version.
No ML dependency is agreed (scikit-learn's `HistGradientBoostingRegressor` is the smallest
choice; LightGBM is not needed). The model-selection rule is an owner decision (item 19).

**How to do it.** Add the dependency; build features per section-month; train on rolling origins
with exactly the backtest protocol T2 uses; compare against seasonal naive on city MAPE and
section WAPE; keep it in the forecast table only if it beats the baseline on both, otherwise
report that it lost (the doc requires the honest result).

**Done when.** The backtest table has a GBM row on the same folds, and the selection follows the
agreed rule, whatever the outcome.

### 13. Measure the F14 voice error rate (F14, T4)

**What it is.** How often the speech model (IndicConformer, `ai4bharat/indic-conformer-600m-
multilingual`, `backend/app/config/intake.py`) gets Telugu and Urdu complaints wrong.

**Where it stands.** Voice intake works and failed items go to a person, but no error rate was
ever measured, and none is published for this domain.

**Blocked by.** A small labelled set: about 50 to 100 short recordings per language of
complaint-like sentences, each with a correct transcript, recorded with consent by speakers we
know. No public set of water-complaint speech exists.

**How to do it.** Add a script that runs the model on the set and reports word error rate and
character error rate per language, plus the share where the complaint category is still right
(what actually matters for routing). Store only the scores, not the recordings, unless the
speakers agree.

**Done when.** A committed results file with WER, CER and category accuracy per language and the
set's size, and the number quoted in `LIMITATIONS.md` (F14).

### 14. Reproduce F13's duplicate calibration (F13, T1)

**Status: location/time part done** on `feat/f13-dedup-calibration`: logged D13 pull, all measures reproduced or corrected (see `docs/LIMITATIONS.md` F13). The doc's 71% / 88% hold only as "linked to any earlier complaint"; into the right incident it is 59% / 60%, and 82% / 65% for the configured rule. The text-similarity test on Indian examples was **skipped by owner decision** (2026-10-05).

**What it is.** The duplicate engine merges complaints within 100 m and a time window per
category. The doc quotes "100 m / 48 h finds 71% of real duplicates, 300 m / 7 days finds 88%"
from Chicago 311 data.

**Where it stands.** The frozen Chicago extract was never found, so those numbers cannot be
reproduced from the repo. Text similarity (the embedding check) is untested on Indian examples.
The duplicate-merge measure is missing from the Impact page for the same reason.

**How to do it.** Download the Chicago 311 open data again (same categories and period as the
note in `docs/research/P3.md`), freeze the extract with its checksum in `data/raw/`, add a
script that computes the share of known duplicates linked within each radius and window, and
commit its output. For text: build a small set of Indian complaint pairs (English, Telugu, Urdu,
Hindi; same issue and different issue), written by us and labelled, and measure how well the
similarity score separates them.

**Done when.** The script reproduces the 71% / 88% figures (or reports the numbers it gets and
the doc is corrected), and a results file gives the text-similarity separation on the Indian set.
The Impact page's duplicate measure can then be filled in.

---

## Needs data from outside

### 15. Hospital and school data (D9) in the ward table (F1, F8 tier 0, F10)

**Status: done** on `feat/d9-facilities`: logged OSM pull (2,242 features, `data/raw/d9_facilities/`), counts per ward in `ward_facilities.csv`, the E2 facilities column filled for all 145 wards (DERIVED), the U5 atlas shows the count, and `GET /facilities/candidates` lists each ward's facilities as candidate critical stops for an officer. Totals do not match the document's (941 / 294 / 174 / 439 / 6 against 885 / 310 / 350 / 399 / 59); `docs/LIMITATIONS.md` F1 explains why. The text below is the plan it followed.

**What it is.** Counts of hospitals, clinics, urban health centres, schools and care homes per
ward, from OpenStreetMap. The doc lists D9 as REAL and verified (885 / 310 / 350 / 399 / 59).

**Where it stands.** The file was never copied into the repo (S2 notes it as unavailable), so the
ward table's facilities column says `FACILITIES_UNAVAILABLE`, and tier-0 critical stops in F10
are officer-entered only.

**How to do it.** Fetch the OSM features for the Hyderabad district boundary (Overpass API; the
boundary is already in `data/raw/geography/osm/hyderabad_district.geojson`), save them with a
retrieval log and checksum, place them on the 2016 wards, and fill the facilities column with
basis REAL (counts) / DERIVED (ward placement). Offer them as candidate critical stops in F10;
an officer still confirms each.

**Done when.** The atlas shows facility counts per ward, the counts match the doc's totals (or
the difference is explained), and the verifier passes.

### 16. Weather data (D8) from Open-Meteo (F5)

**Status: done** with item 12: `scripts/data/fetch_d8_weather.py` wrote `data/raw/d8_weather/` (2019-01-01 to 2026-09-30, 2,830 days, no gaps, retrieval log with SHA-256).

**What it is.** Daily temperature and rainfall for Hyderabad, 2019 to 2026, from Open-Meteo's
free historical API. The doc lists it as REAL.

**Where it stands.** Not in the repo.

**How to do it.** A fetch script for one point (city centre) or a few points, saved to
`data/raw/d8_weather/` with a retrieval log and checksum; a monthly summary (mean maximum
temperature, total rainfall, hot days over 40 C) for the forecast features.

**Done when.** The monthly weather table exists for every month the forecast uses, with a test
that checks coverage. Unblocks item 12.

### 17. Groundwater data (D7) (F5, F6)

**What it is.** Groundwater levels for Hyderabad and Ranga Reddy wells, from CGWB / Telangana
Groundwater Department through the National Water Data Portal (NWDP).

**Where it stands.** `data/raw/d7_groundwater/RETRIEVAL_LOG.md` records that the data exists but
NWDP needs a registered account and has no documented bulk download. Every F6 shortage reason
says "groundwater data unavailable".

**How to do it.** Someone registers at https://nwdp.nwic.gov.in and downloads the quarterly
manual-well data (2019 to 2024) for both districts, following the steps in the retrieval log. We
then place wells on mandals, compute the level change against the same season in past years, and
add it to F6's reasons and as a candidate F5 feature.

**Done when.** Either the groundwater anomaly appears in F6's reasons with basis REAL, or, if the
data is unusable (too few wells, gaps), `LIMITATIONS.md` says so with the evidence.

### 18. Degraded-signal replay for the T9 threshold (F17)

**Status: done** on `feat/t9-degraded-replay`: the calibration replays against true data that differs from ours where our placement and Census joins are weak (ASSUMED error rates, 5 draws). The curve separates and the 90% rule chooses **0.05** (DERIVED): 45 of 152 groups flagged, about 41% of damaged groups caught, at least 90.86% of unflagged decisions right in every draw. Catching 90% of damaged groups would need 0.70 (117 groups flagged). See `docs/LIMITATIONS.md` F17 for why this is partly circular. The text below is the plan it followed.

**What it is.** The confidence gate flags groups for an officer's check when confidence is below
a threshold. The threshold should be chosen on a replay, but on the normal replay nothing goes
wrong, so every threshold looks the same (`not_separable`) and it stays at a provisional 0.50,
which flags 60 of 152 groups.

**Where it stands.** `data/derived/confidence_calibration.csv` and `backend/app/config/
confidence.py` (PROVISIONAL 0.50).

**How to do it.** A replay scenario in which the signals are deliberately degraded in known
places: some sections moved to the wrong ward, some Census joins replaced with the fallback.
Then measure, for each threshold, how many wrong placements the gate catches and how many groups
it sends to officers, and choose the lowest threshold that meets the 0.90 target.

**Done when.** The calibration file shows a separable curve on the degraded scenario and the
config uses the chosen threshold (basis DERIVED), or the result says why no threshold works.

---

## Needs a decision

### 19. Seven decisions from the owner

| Decision | Why it is needed | What it unblocks |
|---|---|---|
| Fix the GitHub billing | Actions has not run since early October 2026 ("recent account payments have failed"); everything was checked locally | green CI, release tag |
| Trips per tanker per day | the F5 capacity planner refuses to run without it; F6 uses an assumed 9 | F5 capacity check, F6 |
| Q1 filling points, Q2 reservoir data | both ON_HOLD | F9 positions, F6 reservoir signal |
| Confirm the forecast protocol behind 21.9% / 35.1% | it was rebuilt by reproduction, not from the lost review file | quoting the numbers on slides |
| Is Chronos-2 allowed under the no-LLM rule? | doc lists it as a backtest-only candidate | item 12 comparison |
| Native speakers for Telugu, Urdu and Hindi | translations are drafts; review pack in `docs/translation_review/` | removing the draft notice |
| Version for the release tag (X1) | waits on green CI | release |

### 20. Decide the stack

**What it is.** The solution doc (Section 7) promises PostgreSQL/PostGIS in Docker, TanStack
Query, Leaflet, OSRM, scikit-learn, MAPIE and Nixtla. What we actually run: SQLite only, no
Docker files, plain `fetch` with our own `useApi` hook, no map library (maps are drawn without
Leaflet; the atlas is an SVG drawn by the screen), OR-Tools with OSRM only when `OSRM_URL` is
set (no OSRM server is set up, so routes use straight-line distance times a road factor), our own
split-conformal intervals instead of MAPIE, and no Nixtla.

**Options.** (a) Edit the doc to describe what we use and why (recommended for the competition:
quick and honest); (b) build the missing pieces (a Docker compose with PostgreSQL, Leaflet maps,
OSRM): several days, and a database migration tool would be needed too (we have none).

**Done when.** The doc and the code say the same thing.

### 21. Fix demo step 5 in the solution doc

**Status: done** on `docs/demo-step5-2025`: lines 45 and 164 now name the Mar-Jul 2025 replay as the main run, with 2023 kept for continuity. `docs/P4_DEMO.md` names no replay year, so it needed no change. The text below is the plan it followed.

**What it is.** `docs/JALLEKHA_FINAL_SOLUTION.md` line 164 (demo script, step 5) says "2023
replay", and line 45 says "a replay of the real 2023 summer". The sandbox and Impact page now use
the Mar-Jul 2025 replay as the main run (2023 is kept for continuity, F19).

**How to do it.** Change both lines to the 2025 replay; check `docs/P4_DEMO.md` says the same.

**Done when.** No line of the doc presents 2023 as the main replay.

### 22. "Done-when vs doc promise" column in `features.csv`

**Status: done** on `docs/item-22-promise-column`: every row has `doc_promise_met` (21 yes, 24 partly, 2 no) and a `gap` note, checked by `backend/tests/test_features_tracker.py`. T7 was already DONE; the notes of A7 and U4-U8 that still said the API was missing (from before PR #65) are corrected. The text below is the plan it followed.

**What it is.** `docs/features.csv` marks a task DONE when its own done-when test passed, which is
often narrower than what the solution doc promises (T2 is DONE but the GBM model is not built; T9
is DONE with a provisional threshold; U10 is DONE with sample cards). Readers take DONE to mean
the doc's promise is met.

**How to do it.** Add a column `doc_promise_met` (yes / partly / no) and a short `gap` note per
row, filled from `LIMITATIONS.md`, and fix the stale rows listed in `LIMITATIONS.md` section 6
(for example T7 still IN_REVIEW).

**Done when.** Every row has the new column and a reader can see at a glance which promises are
only partly met.

---

## Research follow-ups (2026-10-05)

Research only: nothing below is built yet. Each part says what was found, what we recommend and
how to do it.

### A. Choosing between the simple forecast and the gradient-boosting model (F5, after item 12)

**Status: done** on `feat/f5-selection-rule` (applied at the owner's request, 2026-10-06): the recommended rule below is built (`forecast.select`, `diebold_mariano`, `yoy_months`, `combo_naive_gbm`). It selects **gradient boosting** (p = 0.0006 on 24 origins; the combination also passes but is not significantly better). On the real Feb-Aug 2026 city totals the two forecasts are nearly tied (31.1% vs 31.8% MAPE); see `docs/LIMITATIONS.md` F5. The text below is the research it followed.

**The problem.** Item 12's gradient-boosting model beats seasonal naive on the long portal
backtest (city MAPE 23.21% vs 26.28%, section WAPE 37.04% vs 47.67%, 33 months) but is slightly
worse on the short S2 run (23.60% / 35.99% vs 21.89% / 35.12%). The selection rule in
`config/forecast.py` (OPEN, never confirmed) asks for a win on both measures in both runs, so the
baseline stays published.

**What the research says.**
1. **Judge on the longest honest backtest.** Rolling-origin evaluation (forecast each month from
   data before it, then move on) is the standard way to compare forecasting models
   ([Hyndman & Athanasopoulos, *Forecasting: Principles and Practice*, time series
   cross-validation](https://otexts.com/fpp3/tscv.html)). Our two runs cover the **same months**
   (2022 to Feb 2024 lies inside the portal run), from two copies of HMWSSB's data; the S2 run only
   gives the model less history. Requiring a win in both counts those months twice and punishes a
   learning model for having had less data, which is not how it will be used: the published
   forecast is trained on the portal data through Jan 2026 (about 36 months).
2. **Ask for evidence, not only a lower average.** The standard test of "is forecast A really more
   accurate than B" is the Diebold-Mariano test with the Harvey-Leybourne-Newbold correction for
   small samples ([statsmodels `diebold_mariano_test`](https://www.statsmodels.org/dev/generated/statsmodels.tsa.stattools.diebold_mariano_test.html),
   [MetricGate summary](https://metricgate.com/docs/diebold-mariano-equal-accuracy/)). It can still
   be over-confident in short samples ([Nottingham eprint](https://eprints.nottingham.ac.uk/43017)),
   so it should be one condition among others, not the only one.
3. **Try the average of the two.** Across 50 years of studies and the M competitions, a simple
   average of forecasts is hard to beat and rarely worse than the models it averages, because their
   errors partly cancel ([Wang et al., *Forecast combinations: an over 50-year review*](https://arxiv.org/pdf/2205.04216);
   [M-competition lessons](https://r-statistics.co/M-Competition-Lessons-in-R.html)). An equal
   average of seasonal naive and the gradient-boosting model is a cheap third candidate.
4. **Guard against too little history.** The model lost mainly in the months where it had 2 to 11
   year-on-year months to learn from. A minimum-history condition removes that failure mode.

**Recommended rule (for the owner to confirm, item 19).** A candidate replaces seasonal naive when,
on the longest rolling-origin backtest (the portal run, months every model shares):
- it is better on both city MAPE and section WAPE;
- the Harvey-Leybourne-Newbold Diebold-Mariano test on the monthly section absolute errors rejects
  equal accuracy at 5% (one-sided);
- it had at least 12 year-on-year training months when the forecast is made.

The equal average of the candidate and seasonal naive is scored the same way; when two options are
statistically tied, the simpler one wins. The S2 run stays as the check that reproduces the
documented 21.9% / 35.1% baseline, not as a second vote.

**How to do it.** In `backend/app/services/forecast.py`: add a `combo_naive_gbm` model (the mean of
the two), a Diebold-Mariano function (statsmodels is not a dependency; the statistic is a few lines
with numpy and scipy, already installed), and the new rule in `select_model`; put the rule's wording
in `config/forecast.py`; re-run `scripts/forecast/run_backtest.py`; update `LIMITATIONS.md` F5.
Tests: the statistic on a hand-checkable fixture, the minimum-history guard, and the rule choosing
the simpler option on a tie. About 1 to 2 hours.

### B. Weather for the whole of Hyderabad, not one point (D8, after item 16)

**Status: done** on `feat/d8-city-weather`: TGDPS daily station data for the four HMWSSB districts, 2018-01 to 2026-09 (105 monthly files from Open Data Telangana's catalogue API, `data/raw/d8_weather_stations/`; 2,827 day/month-swapped dates corrected and flagged), mandals located with Nominatim, each section given its nearest mandal (`data/derived/weather/`), and a per-section-weather gradient-boosting candidate scored under the part A rule. **It does not win** (not significantly better than the city-weather model), so the forecast is unchanged; see `docs/LIMITATIONS.md` F5. The text below is the plan it followed.

**The problem.** The forecast uses one weather series at the city centre (Open-Meteo, 17.385 N,
78.4867 E). Heat is not even across the city: studies of Hyderabad find the inner city 3 to 4 deg C
hotter at the surface after its growth ([SIG research report](https://sig.ac.in/assets/pdf/research_student/mtech/21070146006.pdf)),
with the strongest heat islands in Patancheru, Gachibowli, Mailardevpally and Hayathnagar
([The South First, 2024](https://thesouthfirst.com/news/hyderabad-turns-into-a-cluster-of-urban-heat-islands-what-it-means)).
These are land-surface temperatures, not air temperatures, but they show the spread.

**Sources found.**

| Source | What it gives | Detail | Verdict |
|---|---|---|---|
| **TGDPS automatic weather stations** (Telangana State Development Planning Society), on [AIKosh](https://aikosh.indiaai.gov.in/home/datasets/details/telangana_weather_data_2023_2025.html) / Open Data Telangana | about 584 stations; daily rainfall, minimum and maximum temperature, humidity and wind, by district and mandal; yearly files from [2018](https://aikosh.indiaai.gov.in/home/datasets/details/telangana_daily_weather_data_2018.html) to 2025 | real station measurements, one or more per mandal; Open Government License (India) | **best**: real local data for every booking year. To check before use: Hyderabad, Medchal-Malkajgiri, Ranga Reddy and Sangareddy mandals present, gaps, file format, and whether download needs a login |
| [Open-Meteo historical API](https://open-meteo.com/en/docs/historical-weather-api), several points in one call (comma-separated coordinates) | the current source, at many points | "best match" blends ECMWF IFS (9 km, from 2017), ERA5-Land (about 11 km) and ERA5 (25 km) | **fallback**: free and complete, but at 9 to 11 km a city about 40 km across has only a handful of distinct cells, and reanalysis smooths heat islands |
| IMD gridded data | rainfall at 0.25 deg, temperature at 1 deg | coarser than both | not worth it |

**Recommended approach.**
1. Download the TGDPS station files for 2018 to 2025 for the mandals HMWSSB serves and log them
   in `data/raw/d8_weather_stations/` with a retrieval log and checksums (as for D8).
2. Give each HMWSSB section the station of its mandal, or the nearest station. Sections are
   already geocoded (D12) and mandal boundaries are in
   `data/raw/geography/osm/hyderabad_mandals.geojson`. Where a station has a gap, fill from the
   nearest station, else from the Open-Meteo point nearest the section, and label filled values.
3. Build the gradient-boosting model's weather features per section (last year's month against
   that station's own 2019-2021 normal, recent rain and heat) instead of one value for the city.
4. Score it on the same backtest and keep it only if it wins under the rule in part A.

**Effort and limits.** About half a day once the files download. Station networks have gaps and
moved stations, and the 2018 start leaves 2019-2021 for the normal (as now). If the Hyderabad
mandal files are missing or too patchy, use the Open-Meteo multi-point fallback: one point per GHMC
zone (6 zones), given to sections by nearest point.

