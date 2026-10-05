# JalLekha 2.0: remaining work (items 11 to 22)

Status on `main` as of 2026-10-05, after PR #66. Items 1 to 10 of the 22-item list are done
(PRs #64, #65) and so are the four follow-up fixes (PR #66). This file lists what is left: for
each item, what it is, where it stands in the code today, what blocks it, how to do it, and when
it counts as done. `docs/LIMITATIONS.md` has the full list of known limits; this file is the
to-do list.

| # | Item | Feature | Who can start it | Blocked by |
|---|---|---|---|---|
| 11 | Ward report cards with real deliveries, debt and schedule | F20 | us, now | nothing |
| 12 | Gradient-boosting forecast | F5 | us, after 16 | weather data (16), dependency choice (19) |
| 13 | Voice error rate for Telugu and Urdu | F14 | us, after recordings | a small labelled voice set |
| 14 | Reproduce the duplicate calibration (71% / 88%) | F13 | us, now | a calibration extract we must rebuild |
| 15 | Hospital and school data (D9) in the ward table | F1, F8, F10 | us, now | nothing (OSM is open) |
| 16 | Weather data (D8) | F5 | us, now | nothing (Open-Meteo is open) |
| 17 | Groundwater data (D7) | F5, F6 | us, after registering | NWDP account |
| 18 | Degraded-signal replay for the T9 threshold | F17 | us, now | nothing |
| 19 | Seven owner decisions | several | owner | owner |
| 20 | Decide the stack (or edit the doc) | all | owner, then us | decision |
| 21 | Fix demo step 5 in the solution doc | docs | us, now | nothing |
| 22 | "Done-when vs doc promise" column in `features.csv` | tracker | us, now | nothing |

Order we will work in: 11, then 21 and 22 (quick), then 15, 16, 18, 14, then 12 once 16 is in,
then 17 and 13 when the data arrives. Item 19 runs alongside: each decision unblocks something.

---

## Finish features

### 11. Ward report cards with real deliveries, debt and schedule (F20, U10)

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

**What it is.** `docs/JALLEKHA_FINAL_SOLUTION.md` line 164 (demo script, step 5) says "2023
replay", and line 45 says "a replay of the real 2023 summer". The sandbox and Impact page now use
the Mar-Jul 2025 replay as the main run (2023 is kept for continuity, F19).

**How to do it.** Change both lines to the 2025 replay; check `docs/P4_DEMO.md` says the same.

**Done when.** No line of the doc presents 2023 as the main replay.

### 22. "Done-when vs doc promise" column in `features.csv`

**What it is.** `docs/features.csv` marks a task DONE when its own done-when test passed, which is
often narrower than what the solution doc promises (T2 is DONE but the GBM model is not built; T9
is DONE with a provisional threshold; U10 is DONE with sample cards). Readers take DONE to mean
the doc's promise is met.

**How to do it.** Add a column `doc_promise_met` (yes / partly / no) and a short `gap` note per
row, filled from `LIMITATIONS.md`, and fix the stale rows listed in `LIMITATIONS.md` section 6
(for example T7 still IN_REVIEW).

**Done when.** Every row has the new column and a reader can see at a glance which promises are
only partly met.
