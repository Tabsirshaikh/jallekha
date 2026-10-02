# Branch worklog

This file records what each task branch discovered and changed. It lets a teammate understand, review, reproduce, or correct the work without relying on chat history.

## Required workflow

Every task branch must add or update its entry here before opening a pull request. Keep the entry concise and evidence based. Update it again if review changes the implementation.

Use this template:

```markdown
## `<branch>` — `<task-id>`

- **Owner / date:**
- **Purpose:**
- **What we found:** Facts, constraints, data gaps, failed assumptions, and important evidence links.
- **What we changed:** Files and behavior changed on this branch.
- **Validation:** Commands, tests, datasets, results, and the task-specific `<owner>:<task-id>` CI workflow. Distinguish simulated results from real observations.
- **Known limitations:** Remaining uncertainty, unavailable data, deferred scope, or operational risk.
- **Handoff / next step:** Dependencies created, who needs the output, and what must happen after merge.
- **Pull request:** URL or `pending`.
```

The pull-request description must summarize the same information and link to this file. A task cannot move from `IN_REVIEW` to `DONE` until its entry reflects the merged result.

## `feat/s4-shells` — `S4`

- **Owner / date:** P4, 2026-10-02.
- **Purpose:** Establish the shared design system, officer/resident/driver workspace shells, and localization foundation.
- **What we found:** The frontend was still the Vite starter page. The current repository includes S1 and P1 evidence work. P4 research recommends clear low-literacy actions, explicit simulation/data labels, large text and touch targets, offline-friendly assets, and a locale-aware RTL foundation.
- **What we changed:** Replaced the starter page with responsive officer, resident, and driver workspace previews; added role navigation for desktop and mobile, explicit demo/no-live-service states, REAL/DERIVED/SIMULATION tags, reusable visual tokens and components, and `frontend/src/i18n.tsx` with locale metadata and direction handling for English, Telugu, Urdu, and Hindi. Text is at least 16px and interactive controls are at least 48px. No external font or runtime service is required.
- **Validation:** `npm run lint`, `npm run build`, and `npm run test -- --run` pass locally. The frontend test wraps `App` in `LocaleProvider` and confirms all three workspaces render and switch. Opened the Vite app at `http://127.0.0.1:5173/` and confirmed the officer, resident, and driver workspaces render and switch. Added `.github/workflows/p4-s4.yml` to repeat lint and production build for the `P4:S4` task check.
- **Known limitations:** Translation catalogs are scaffolding only; actual translated UI strings belong to U1. Data screens and real API integrations belong to U5-U10. This is a shell preview with no live requests, route assignment, or allocation approval.
- **Handoff / next step:** Merged to main in PR #16. U1 is underway on `feat/u1-i18n`; resident/driver functionality follows after U1 and P3 T4.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/16

## `feat/u1-i18n` — `U1`

- **Owner / date:** P4, 2026-10-02.
- **Purpose:** Make the shared officer, resident, and driver shells available in English, Telugu, Urdu, and Hindi, with Urdu RTL behavior.
- **What we found:** S4 supplied locale context and direction handling but no language picker or translated catalog. R-P4 recommends short, clear language, logical layout properties, and native review of Urdu wording.
- **What we changed:** Added a locale selector and full shell message catalogs for en/te/ur/hi. Workspace labels, navigation, resident and driver content, and shared shell copy use translation keys; selecting Urdu applies RTL direction to the app and document. Added a locale-switching UI test.
- **Validation:** `npm run test -- --run` passes (1 test covering Telugu and Hindi strings, workspace switching, and Urdu RTL/lang attributes); `npm run lint` passes; `npm run build` passes. CI workflow `P4:U1` will run frontend tests, lint, and build.
- **Known limitations:** These are draft translations. Native speakers must review Telugu, Urdu, and Hindi wording and layout before release; no runtime translation is used.
- **Handoff / next step:** After U1 review/merge, start U2 once P3 T4 (intake) is ready. U3 follows U2; U4 also waits for P3 T3 delivery proof.
- **Pull request:** pending.

## `feat/u2-resident` — `U2`

- **Owner / date:** P4, 2026-10-02.
- **Purpose:** Build the resident-facing reporting and tracking experience with an offline-first queue.
- **What we found:** P3's T4 intake batch endpoint accepts app items with `client_id`, `channel`, `category`, `text`, `language_hint`, and `area_id`; it returns per-item outcomes. There is no resident-facing delivery-code or ward-information API in `main`. U1 is merged; T4's implementation is present via PR #37, though its tracker row remains `IN_REVIEW`.
- **What we changed:** Added English, Telugu, Urdu and Hindi resident flows for issue reports, request tracking and an area card. Reports persist in IndexedDB, can include device location only after the resident opts in, and sync idempotently through T4's `/intake/batch` contract when online; the dev server proxies `/intake` to the local API. Added a web manifest and service worker for cached app-shell use. The UI explicitly identifies local-only reports and unavailable live delivery/ward data.
- **Validation:** `git diff --check` passes. `.github/workflows/p4-u2.yml` runs frontend lint and production build. Local UI/test/build validation has not been run.
- **Known limitations:** Live delivery-code assignment and verified ward service information need backend/API support. Intake submission also needs the API running and reachable at `/intake/batch`. All translations are drafts pending native-speaker review.
- **Handoff / next step:** Coordinate with P3 on resident-facing delivery-code and ward-information API shapes; then connect the card to verified data.
- **Pull request:** pending.

## `feat/u3-field` — `U3`

- **Owner / date:** P4, 2026-10-03.
- **Purpose:** Give field workers a multilingual way to record water issues for households and sync them after offline visits.
- **What we changed:** Added a dedicated field-worker workspace with an issue form, household reference or explicitly shared location, report-language selection, sample report, and per-record IndexedDB sync queue. Online and manual retries post to T4's `/intake/batch` shape with stable client ids and original client timestamps. Until T10 authentication exists, the UI uses `DEMO-FW-01` and marks every submitted record `is_synthetic: true`.
- **Validation:** Frontend lint and production build pass. `git diff --check` passes. No live field-worker authentication was available, so the endpoint contract is exercised only by the UI implementation and CI build checks.
- **Known limitations:** Worker identity is a demo fixture; all submitted records are synthetic and must not be treated as operational reports. GPS is optional and requested only after the worker chooses it. Native-speaker review is still needed for translated wording.
- **Handoff / next step:** Replace the demo identity with T10's authenticated worker identity before operational use; preserve the offline client id and sync state.
- **Pull request:** pending.

## `feat/u4-driver` — `U4`

- **Owner / date:** P4, 2026-10-02.
- **Purpose:** Build the driver route, arrival and delivery-proof screens.
- **What we found:** T3's service exposes server-side geofence and OTP verification and four outcomes (`Confirmed`, `Disputed`, `Unconfirmed`, `Failed`), but main has no driver or delivery API router. R-P4 requires clear synthetic labels and no false claims about live service.
- **What we changed:** Added English, Telugu, Urdu and Hindi driver route and delivery-proof screens, with three visibly synthetic stops and a preview-only arrival action. A local fixture flow uses the displayed demo OTP (`123456`) and a selectable simulated resident response to demonstrate all four T3 outcomes; the code is cleared and nothing is sent or persisted.
- **Validation:** Frontend lint and production build pass. `.github/workflows/p4-u4.yml` repeats both checks. UI and test suite have not been run locally.
- **Known limitations:** This is a fixture-backed demonstration, not live route assignment, GPS geofence confirmation, OTP verification, resident messaging or ledger persistence. Live API integration remains a follow-up after P3 provides endpoints.
- **Handoff / next step:** U4 preview scope is complete. Integrate the real route / arrival / OTP endpoints when available, preserving server-side geofence and outcome decisions.
- **Pull request:** pending.

## `research/p1` — `R-P1`

- **Owner / date:** P1 (Yaseer), 2026-10-01.
- **Purpose:** Recheck the data and methods behind F1-F4 before implementation.
- **What we found:**
  - Census 2011 is still the only verified official ward-level source found for household water and phone access; no newer ward-level replacement was verified.
  - The available DataMeet/OSM file contains only 145 polygons from the historical 2016 150-ward scheme. Official sources describe a 300-ward arrangement in December 2025 and a three-corporation reorganisation in February 2026. A current machine-readable boundary/crosswalk was not verified.
  - Open Buildings Temporal is useful for detecting building change, but its documented jitter, temporal instability and uncalibrated confidence prevent treating its building ratio as an exact household-growth ratio.
  - No authoritative public HMWSSB section polygons or section-to-ward crosswalk were verified. Section totals are exact; ward attribution is approximate.
  - Agostini et al. supports modelling latent spatial under-reporting, but BYM2 is a separate spatial prior from Riebler et al. Low bookings alone cannot prove unmet need.
- **What we changed:** Added `docs/research/P1.md`; froze the demo to versioned historical geography `GHMC_2016_150`; required effective dates and source quality for geography; changed F2 to compare Open Buildings, WorldPop and GHS-POP sensitivity estimates; changed F4 to negative-binomial and peer-median baselines with optional evaluated BYM2; revised D1, E1, E3 and E5 acceptance criteria; added `docs/P1_TASKS.md`.
- **Validation:** `python scripts/ci/verify_p1_r_p1.py` parses all 46 tracker rows, checks every F1-F4 decision and evidence marker, confirms solution corrections and validates this worklog. GitHub Actions runs it as `P1:R-P1`; `git diff --check` also passes. This branch changes documentation and specifications, so no application test suite exists yet.
- **Known limitations:** The demo can make historically anchored comparisons but cannot claim current ward-level water need. Current official polygons, a current crosswalk, HMWSSB section boundaries and field truth for under-reporting remain unavailable.
- **Handoff / next step:** One teammate and the owner review PR #2. After merge, mark R-P1 `DONE`. P1 then waits for S1 and starts S2; D1/E1/E3/E5 must follow the revised acceptance criteria.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/2

## `research/p2` — `R-P2`

- **Owner / date:** P2, 2026-10-02.
- **Purpose:** Recheck the data and methods behind F7-F11, routing and F19 before implementation.
- **What we found:**
  - HMWSSB publishes the D1 table on the Telangana Open Data Portal (dataset `7f408a3a-7cdb-4d33-bfa3-1869f88c0e25`, OGL India) up to **Aug 2026**: 56 monthly CSVs, 5,356,766 bookings and 5,281,651 delivered. All 26 months overlapping D1 match `data/derived/equity/monthly.csv` exactly.
  - Capacity binds for the first time in Jun-Aug 2026: delivered share 92.1% / 89.2% / 92.4% (63,428 bookings not delivered). Before that it is at least 98% every month.
  - Sections were re-cut in Feb/Mar 2026 (no Feb or Mar 2026 name matches 2025); 2023 and 2025 share 168 of 178 sections.
  - Today's queue (HMWSSB tracking page): token → nearest filling station → FCFS serial number per station. Caps differ by consumer category.
  - 90 stations, 150 filling points, 1,150 tankers (Dec 2025); no public station coordinates. Whether a household without a CAN can book is not verified.
  - DRR, Gao et al., Holguín-Veras et al. and Jain et al. citations checked.
- **What we changed:** Added `docs/research/P2.md`. Proposed solution-doc edits in a separate commit: D1 coverage, D16 caps by category, D17 fleet, F8 baseline per filling station, F19 replay window and capacity scenarios, risk 4. R-P2 row in `docs/features.csv`.
- **Validation:** Documentation only. Portal figures were recomputed from all 56 downloaded CSVs and compared month by month with `data/derived/equity/monthly.csv` (26 of 26 identical). Every claim in the note carries a link marked [R] (read) or [S] (search summary only).
- **Known limitations:** The portal data is not yet in `data/raw` (P1 ingest). No filling-station coordinates. The CAN requirement for booking is unverified. Fleet and trip figures come from news reports (ASSUMED).
- **Handoff / next step:** One teammate and the owner review the PR. After merge: P1 ingests the portal files as raw data; P2 starts S3, then A1 (replay Mar-Jul 2025 and 2023) and A2.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/17

## `feat/d1b-portal-tankers` — `D1b` (data for A1/A8, found in R-P2)

- **Owner / date:** P2, 2026-10-02. P1 reviews (data area owner).
- **Purpose:** Add the newer official HMWSSB tanker table (Jan 2022-Aug 2026) found in R-P2 as raw data, without changing the verified S2 files.
- **What we found:** The Telangana Open Data Portal publishes the D1 table (dataset `7f408a3a-7cdb-4d33-bfa3-1869f88c0e25`, Open Government License, India) to Aug 2026. Dec 2022 is a header-only file. No blank counts and no row with delivered > bookings. Sections re-cut Feb/Mar 2026.
- **What we changed:** `scripts/data/fetch_hmwssb_portal.py` downloads exact bytes into `data/raw/hmwssb_tankers_portal/` (56 monthly CSVs + `metadata.json`) and writes `data/verification/hmwssb_portal_manifest.csv` (same columns as `source_manifest.csv`). `backend/tests/test_d1b_portal.py` checks hashes, the month range, totals, Dec 2022, delivered ≤ bookings, and that every overlapping month and section equals the S2 OpenCity files. `SOURCES.md` gets an "Added after S2" section. S2 files, `source_manifest.csv` and `verify_manifest.py` are untouched, so the 33-file / 4,398-row S2 checks still hold. No tracker row was added (P1's R-P1 check requires 47 rows); the A1 row notes point here.
- **Validation:** `python tasks.py test`: 61 pytest tests pass (7 new in `test_d1b_portal.py`), frontend test and all P1 verifiers pass. `python tasks.py lint` passes. `scripts/ci/verify_p1_r_p1.py` passes. The committed files are byte-identical to an independent download made earlier the same day. All data REAL; nothing derived or simulated.
- **Known limitations:** The 2026 section names cannot be joined to earlier years without a crosswalk. The portal gives no reason for the Jun-Aug 2026 non-delivery. The portal may refuse cloud runners, so CI checks committed files only.
- **Handoff / next step:** P2 uses Mar-Jul 2025 (and 2023) for the A1 replay; P3 may use 55 months for T2; P1 decides whether E4/E6 should add the newer months.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/18

## `feat/s3-port` — `S3`

- **Owner / date:** P2, 2026-10-02.
- **Purpose:** Copy the proven v1 modules (github.com/abhay-hanchate/jallekha) into the new backend with their tests, adapted, without v1's database coupling or hand-typed data.
- **What we found:** v1's modules depend on v1's database models, settings object and seed data. The ledger and intake database pipelines overlap P3's T6 and T4. v1's committed OSRM cache was built on v1's hand-typed filling stations. v1 planned 6,000 l stops; HMWSSB's domestic tanker is 5,000 l.
- **What we changed:**
  - Pure services in `backend/app/services/`: `ledger.py` (hash chain + HMAC, `next_entry`, `verify_entries`; refuses to sign without a key), `otp.py`, `geofence.py`, `geo.py`, `spam.py`, `intake.py` (channels, `IntakeMessage`, `validate`, `clean_text`, `preset_category` only), `routing.py` (OSRM via `OSRM_URL`, in-memory cache, offline estimate), `vrp.py` (OR-Tools CVRP with reloads, generic `Demand`/`Tanker`/`Station`), `hmwssb.py` (reader for S2 and D1b files).
  - Config: routing and solver values in `config/allocation.py`; new `config/spam.py`; three fields added to P3's `config/trust.py` (`geofence_max_radius_metres`, `otp_digits`, `otp_max_attempts`). Every value has a source comment.
  - `ortools==9.15.6755` added to the dependencies. The `.env.example` note on `OSRM_URL` was updated.
  - Not ported: v1 database models and pipelines, the OSRM cache file, v1 ward scoring, v1's synthetic daily spreading (A1 does that).
- **Validation:** 40 new tests in `backend/tests/test_s3_*.py` were written first and seen failing (ImportError), then pass. `python tasks.py test`: 120 pytest tests pass, plus all P1 verifiers. `python tasks.py lint` passes. `pip check` is clean. Route-planner tests use straight-line legs (no network). HMWSSB figures are recomputed from the REAL raw files.
- **Known limitations:** Planner values (trips, shift, refill and unloading minutes, speed, road factor) are ASSUMED from v1 and revisited in A4. Spam thresholds are ASSUMED from v1 and tuned in T4. OR-Tools prints SWIG deprecation warnings on import (upstream).
- **Handoff / next step:**
  - P3 T3 uses `otp`/`geofence`; T6 stores `LedgerEntry` rows and calls `next_entry`/`verify_entries` with `TRUST_CONFIG.ledger_hmac_key`; T4 builds the pipeline on `intake` + `spam`.
  - P2 A4 builds on `vrp.plan`; A1 reads files with `hmwssb.read_rows`.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/20

## `feat/a1-replay` — `A1`

- **Owner / date:** P2, 2026-10-02.
- **Purpose:** Daily tanker bookings for the F19 policy sandbox, rebuilt from real HMWSSB monthly totals.
- **What we found:** HMWSSB publishes bookings per section per month only. In the replay windows (Mar-Jul 2025 and 2023, portal data) every section appears once per month with no zero rows. No public daily or hourly booking pattern was found, so v1's hand-typed weekday profile is not used.
- **What we changed:**
  - `backend/app/services/replay.py`:
    - `daily_counts(rows, months, seed)` spreads each section-month total over its days (each day equally likely); the totals are preserved exactly.
    - `arrivals(days, seed)` gives each booking a random second of its day (IST) and returns bookings in arrival (FCFS) order with stable ids `YYYY-MM-DD:SECTION:NNNNN`.
    - Randomness is seeded per section-month, so adding months does not change the others.
    - Rows carry `basis="SYNTHETIC"` (split) and `total_basis="REAL"` (month total).
    - Months without data (e.g. Dec 2022) raise `ValueError`.
  - `config/allocation.py`: `replay_months_main` (Mar-Jul 2025) and `replay_months_secondary` (Mar-Jul 2023), with source.
- **Validation:** 8 tests in `backend/tests/test_a1_replay.py` were written first and seen failing (ImportError), then pass. They cover exact section-month totals for both windows, the 977,933 total for summer 2025, seeding, month bounds, labels, refusal of empty months, and arrivals (count, order, same day, ids, repeatable). `python tasks.py test`: 160 pytest tests pass, plus all P1 verifiers. `python tasks.py lint` passes.
- **Known limitations:** The day and time-of-day split is uniform (ASSUMED); a real daily pattern would need HMWSSB daily data (RTI). Categories (domestic, apartment, commercial) are not in the source and are not invented here.
- **Handoff / next step:**
  - A3 orders `arrivals(...)` per filling station.
  - A8 runs the policies on the same seeds (common random numbers).
  - P3's T9/T10 get the replay format: `DailyCount(day, division, section, bookings, basis, total_basis)` and `Booking(booking_id, section, division, arrived_at, basis)`.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/22

## `fix/e2-ward-crosswalk` — E2 fix (Census ward numbering), affects E4-E6

- **Owner / date:** P2, 2026-10-02, with the owner's approval to change P1's finished work. P1 should review.
- **Purpose:** E2 allowed 0 wards for allocation. Find out why and fix it at the source.
- **What we found:**
  - **Census 2011 numbers GHMC wards by the 2009 delimitation; the DataMeet layer is the 2016 delimitation.** Wards were renumbered and redrawn in 2015.
    - Only 15 of 144 numbers keep their name (2009 names: Wikipedia 2009 election results).
    - The Census district split proves it: under 2016 numbers, Census "Hyderabad district" wards 104-110 would be Kondapur, Gachibowli, Madhapur and others, all in Rangareddy.
    - So the E1/E2 number join put Census values on the wrong area for most wards; e.g. 2016 "Ward 91 Khairatabad" carried 2009 ward 91 (Musheerabad).
  - No machine-readable 2009 ward map exists online. IDFC, hyderabad-svi and bharatlas all reuse the 2016 OSM wards. The official GHMC 2009 ward PDF (GODL) is a vector ArcMap export with ward lines and red ward-number labels.
  - `data/raw/geography/osm/hyderabad_district.geojson` and `hyderabad_mandals.geojson` hold a single Point each, not boundaries (D1 issue for P1).
- **What we changed:**
  - New raw sources with manifest (`scripts/data/fetch_ward2009.py`, `data/verification/ward2009_manifest.csv`): GHMC 2009 ward PDF, pinned Wikipedia revision of the 2009 ward table, OSM Hyderabad district polygon (validation only).
  - `scripts/evidence/build_ward2009.py`:
    - Polygonizes the PDF ward lines (pdfplumber, MIT; 149 units, wards 111+112 merged because the PDF has no line between them).
    - Fits them to the DataMeet GHMC outline by affine iterative closest point (outline IoU 0.90, median boundary error 155 m).
    - Writes `data/derived/ward2009/` and `data/derived/crosswalk/ward2009_to_ghmc2016_weights.csv` (share of each 2009 ward's Open Buildings 2016 building count in each 2016 ward, from the E3 tiles).
  - **Independent checks (not used in the fit):** Census district agreement 96% with 0 wards wrongly inside Hyderabad district (the 2016 number join scores 84%); the 2009 ward with the same name is the largest overlap for 86% of 99 name pairs.
  - `build_evidence.py` (E2): Census wards (2009 numbering) are split over 2016 wards by building share.
    - New columns: `crosswalk_method`, `census_coverage`, `dominant_source_share`, `source_units`.
    - New statuses: `AREAL_2009_CROSSWALK` / `PARTIAL_CENSUS_COVERAGE` / `HH14_*` / `NO_CENSUS_ROW`.
    - Result: **143 of 145 wards allocation-eligible** (was 0). 2 are partial: they overlap 2009 wards 115-116, which were in Medak district and are not loaded. Wards that are mixtures (<50% from one 2009 ward) or incomplete are `review_required`.
    - HH-14 formulas, header checks and fail-closed handling are unchanged.
  - E4/E5/E6 artifacts rebuilt. E6 water layer now labels values `APPROXIMATE_2009_CROSSWALK` and passes E2 eligibility through (booking and field layers stay unavailable). E5 stays closed, because its exact-geometry rule and the missing section-to-ward booking transfer still block it; only its limitation text changed.
  - `pdfplumber==0.11.10` added to the `geo` extra.
- **Validation:**
  - Tests written first (`test_ward2009.py` new, E2 tests rewritten, including a regression test that 2016 Ward 91 Khairatabad takes nothing from 2009 ward 91), then made to pass.
  - `python tasks.py test`: 170 pass, plus all P1 verifiers. `python tasks.py lint` passes.
  - P1 CI steps run locally: E1 rebuild leaves `data/derived/crosswalk` unchanged; `verify_main_integration.py` and `verify_p1_r_p1.py` pass.
- **Known limitations:** Values are approximate (PDF fit; Census 2011 households spread by 2016 buildings). The 2016 layer still lacks 6 wards. Current 300-ward claim stays blocked. Medak-district Census (2009 wards 115-116) is not loaded.
- **Handoff / next step:**
  - P1 reviews the method and decides whether E5 should accept approximate locations.
  - P1 should fix the D1 district/mandal files (points, not polygons).
  - A2 uses the eligible wards with `review_required` as the officer-check flag.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/24

## `fix/s3-ledger-geofence` — S3 review fixes

- **Owner / date:** P2, 2026-10-02. Fixes P3's review of PR #20.
- **Purpose:** Fix the two defects that block T3/T6 (D1, D6) and the low-severity items (D3, D7, D8, D9, D11, D13, D14).
- **What we changed:**
  - **D1:** the ledger hash covers every stored field (`entry_hash`: canonical JSON of all `LedgerEntry` fields except `hash`/`signature`, so fields added later are covered automatically). `compute_hash` is replaced.
  - **D3:** NaN and Infinity are rejected (`allow_nan=False`).
  - **D6:** the geofence boundary uses a 1e-6 m tolerance.
  - **D7:** radius `None` = default; 0 or negative raises.
  - **D8:** missing location gives `distance_m=None`.
  - **D9:** non-finite or out-of-range coordinates raise.
  - **D11:** the OTP HMAC input includes the digit count; `derive_code(..., digits=)` re-derives an issued code exactly.
  - **D13:** digits and address punctuation (`config/spam.py address_punctuation`) are not counted as gibberish.
  - **D14:** "missed call = no water" is marked ASSUMED.
  - Not ours (per the review): D2 (head hash, T6), D10/D12 (OTP validity and attempts, T3/owner).
- **Validation:**
  - `backend/tests/test_s3_review_fixes.py` was written first; 15 tests failed, one per defect, then all pass. It covers: every `LedgerEntry` field edited after signing is detected; reorder and delete are detected; NaN/±inf rejected; points exactly 150 m away inside on all 360 bearings, +1 mm outside; radius 0/-10 rejected; missing location gives distance None; invalid coordinates for both the point and the stop; OTP digits; address text.
  - Two original S3 tests were updated to the new requirements (`entry_hash`; "111 222 ###" is not gibberish under D13).
  - `python tasks.py test`: 198 pass. `python tasks.py lint` passes.
- **Known limitations:** Removing the last entry is still undetectable without a published head hash (D2, T6).
- **Handoff / next step:** T3 and T6 can build on S3.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/25

## `fix/d1-boundaries` — P1 follow-ups (D1 boundaries, E5 location rule)

- **Owner / date:** P2, 2026-10-02, doing P1's follow-ups with the owner's approval. P1 should review.
- **Purpose:** Fix two P1 items found during the E2 crosswalk work (PR #24).
- **What we found:**
  - D1's `hyderabad_district.geojson` and `hyderabad_mandals.geojson` held one centre **point** each (Overpass `out center`), not boundaries. Nothing reads them yet.
  - Overpass was overloaded on 2026-10-02 (504s on three servers); Nominatim lookup returns the boundary polygons.
  - E5 accepted only exact-geometry Census locations, so E2's approximate placement could never pass.
- **What we changed:**
  - `scripts/data/fetch_d1.py`: D5a = Hyderabad district polygon (OSM relation 7255986); D5b = the 16 current Hyderabad district mandals as polygons. Both use Nominatim lookup by relation id; ids were found by name search and are listed in the script.
  - New `--only=D5a,D5b` option re-fetches only those layers and keeps the other files and manifest rows unchanged (D10 HMWSSB points are byte-identical).
  - Added the missing top-level `import urllib.request`.
  - The mandals are labelled as current OSM mandals, not the 2011 Census mandals; GHMC mandals in Rangareddy (reorganised in 2016) are not included.
  - E5 (`build_underserved.py`): a ward counts as Census-located if E2 placed it exactly **or** approximately on the rebuilt 2009 map and marked it eligible (field checks only). The limitation text says so. E5/E6 artifacts rebuilt.
- **Validation:**
  - New `test_d1_district_and_mandals_are_polygons` failed first, then passes. The 16 mandals tile the district exactly (overlap 1.0).
  - The E5 test was rewritten first: 143 located, 2 partial keep the blocker, all still blocked by the missing booking transfer.
  - `python tasks.py test`: 199 pass. `python tasks.py lint` passes. `verify_d1.py`, `verify_underserved.py` and `verify_coverage.py` pass.
- **Known limitations:**
  - E5 still produces 0 field checks until bookings can be placed on wards (no section-to-ward transfer).
  - `data/raw/geography/nominatim/hyderabad_district.geojson` (E2 validation) duplicates D5a; both are the same OSM relation.
- **Handoff / next step:**
  - P1 reviews.
  - The section-to-ward booking transfer is the remaining E4/E5 blocker.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/27

## `feat/a2-service` — `A2`

- **Owner / date:** P2, 2026-10-02.
- **Purpose:** Service class, route and need weight per ward (F7), as input to A3 (fair queue) and A4 (scheduled supply).
- **What we found:**
  - After E2's 2009-to-2016 crosswalk, no GHMC ward has a majority without tap water (non-tap share max 28.8%, median 1.7%). Unconnected pockets are smaller than a ward, so "no connection" must come from officer input.
  - Census 2011 records the water source, not supply hours, so "piped intermittent" cannot be derived either.
  - Off-premises water (WAD) separates wards: 1-28%; the western corridor and Barkas are highest.
  - The solution doc's "68.4%" off-premises figure is Secunderabad Cantonment Board ward 2, which is not in GHMC. The highest GHMC 2009 Census ward is 33.4% (ward 112). Correct it before slides.
- **What we changed:**
  - `backend/app/services/service_models.py`:
    - `build_ward_needs(evidence, overrides)` gives each ward a class (`piped_regularity_unknown` by default; `no_connection` if non-tap >= 50%, ASSUMED; officer may set any class), a route (`no_connection` -> scheduled F9, piped -> booked F8), need weight `1 + 2*WAD + 1*CAD + 1*hardship` (ASSUMED policy weights), and entitlement = households x need weight.
    - `scheduled_supply_candidate` when WAD >= 15% (ASSUMED).
    - `needs_officer_check` with reasons `CENSUS_UNAVAILABLE` / `E2_REVIEW_REQUIRED` / `SCHEDULED_SUPPLY_CANDIDATE`.
    - Overrides need a reason, a known ward and class, and at most one per ward. `override_event()` gives the ledger entry arguments.
    - Distance is not part of the need weight.
  - `config/allocation.py`: thresholds and weights, with sources.
- **Validation:**
  - 13 tests in `backend/tests/test_a2_service_models.py` were written first (ImportError), then pass. They cover rules, formula, monotone need, ineligible wards, check reasons, overrides (valid, invalid, duplicate), override to ledger entry (verified chain), and real E2 data (145 wards, 143 with entitlement, 0 Census no-connection).
  - Real data: need weight 1.15-1.79 (median 1.33), 20 scheduled-supply candidates, 43 wards flagged for an officer check.
  - `python tasks.py test`: 252 pass, 1 skipped (P3's D6 test, which passes once its skip is removed). `python tasks.py lint` passes.
- **Known limitations:** Weights and thresholds are policy assumptions for officer sliders (U7). Values come from Census 2011 via an approximate crosswalk.
- **Handoff / next step:**
  - A3 orders bookings with `entitlement`; A4 serves `scheduled` wards and candidates the officer confirms.
  - T6 stores override entries.
  - T7 explains `need_weight` components.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/28

## `fix/doc-census-figures` — solution doc census figures

- **Owner / date:** P2 (covering P1/owner), 2026-10-02.
- **Purpose:** Make the section 1 Census numbers verifiable before slides.
- **What we found:**
  - "Up to 68.4% without water on premises" is Secunderabad Cantonment Board ward 2, not GHMC.
  - Recomputed from HH-14, GHMC wards only (148 Census wards, 2009 numbering): max 33.4% (2009 ward 112, Serilingampally), median 5.5% (doc said 5.2%).
  - Still correct: no phone up to 19.2% (Dabeerpura); western wards 12-33% (2009 wards 111-114).
- **What we changed:** One sentence in `docs/JALLEKHA_FINAL_SOLUTION.md` section 1, with the recompute date and the reason for the change.
- **Validation:** Figures from `build_evidence.census_units()` (same HH-14 formulas as E2). `scripts/ci/verify_p1_r_p1.py` passes.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/30

## `feat/a3-queue` — `A3`

- **Owner / date:** P2, 2026-10-02.
- **Purpose:** Fair queue for booked tankers (F8), plus today's FCFS as baseline B1 for A8.
- **What we found:**
  - HMWSSB queues each booking at its nearest filling station by serial number (R-P2), so the queue works per station-day.
  - Bookings are published per HMWSSB section and need per ward, and there is no section-to-ward map yet. So the queue works on generic groups that carry an entitlement; the mapping can be added without changing A3.
- **What we changed:**
  - `backend/app/services/fair_queue.py`:
    - `order_bookings(pending, capacity, entitlement, state)` serves tier 0 (critical facilities) then tier 1 (no water on premises or assisted channel), both FCFS, then deficit round robin across groups. A group's quantum is its entitlement / largest entitlement.
    - Deficits and the round-robin cursor carry to the next day while a group waits. A turn interrupted by capacity resumes without re-adding its quantum. Empty groups do not bank turns.
    - Every `Decision` carries position, reason, arrival rank, entitlement, quantum and deficit (for T7).
    - `order_fcfs` is baseline B1.
    - `apply_caps` enforces the HMWSSB caps per consumer category (`config/allocation.py booking_caps`, REAL published rule) with `CAP_DAYS_BETWEEN` / `CAP_PER_DAY` / `CAP_PER_MONTH`.
    - Distance is never used.
- **Validation:**
  - 16 tests in `backend/tests/test_a3_fair_queue.py` were written first (ImportError), then pass. They cover tier order, a 2:1 entitlement split (20/10 of 30), FCFS within a group, capacity and waiting order, no starvation over days (entitlement 1 vs 10 served by day 4), no banking by empty groups, missing entitlement, explanation fields, the FCFS baseline, determinism, and all cap rules including history across days.
  - 20,000 bookings in one station-day are ordered in 0.04 s.
  - `python tasks.py test`: 287 pass. `python tasks.py lint` passes.
- **Known limitations:**
  - Tier-1 declarations and consumer categories are not in the HMWSSB data; A8 draws them (SYNTHETIC) from Census shares.
  - The section-to-ward entitlement mapping is still open (needs section locations; D12 not ported).
- **Handoff / next step:**
  - T7 uses `order_bookings` and `Decision` for explanations and counterfactuals.
  - A7 runs it per station-day; A8 compares it with `order_fcfs`.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/31

## `feat/a4-scheduled` — `A4`

- **Owner / date:** P2, 2026-10-02.
- **Purpose:** Scheduled tanker supply to fixed points for unconnected areas (F9).
- **What we found:**
  - The Census rule routes no ward to scheduled supply (A2), so scheduling starts only when an officer confirms A2 candidates or sets a ward to no_connection.
  - If all 20 candidates were confirmed: about 182,000 people off premises, 2.73 million litres/day at 15 lpcd = 546 tanker loads (about 5% of the reported ~11,000 daily trips).
- **What we changed:**
  - `backend/app/services/scheduled_supply.py`:
    - `scheduled_wards(needs, evidence, confirmed)`: A2 route "scheduled" plus officer-confirmed candidates; people off premises = population x WAD.
    - `target_litres` (15 lpcd floor; officers may raise the norm, never lower it).
    - `share_reserve`: floors first; equal fraction of floors when the reserve is short; extra by weighted max-min (progressive filling by need weight, capped at targets).
    - `ServicePointRegistry` starts **empty** (no seed list). `register()` needs a reason, valid coordinates and a known ward, rejects duplicates, and returns ledger entry args (new event type `service_point_registered`).
    - `plan_scheduled_supply` routes points with the S3 OR-Tools planner (floor stops mandatory) and returns a timetable (point, ward, tanker, trip, arrival HH:MM, litres). Wards without a point are `NEEDS_SERVICE_POINT`.
    - Distance never changes a ward's share.
- **Validation:**
  - 12 tests in `backend/tests/test_a4_scheduled_supply.py` were written first (ImportError), then pass. They cover:
    - registry starts empty;
    - registration rules and ledger entry;
    - floor and norm;
    - all targets met;
    - floors then 2:1 extra;
    - a capped ward releases its extra;
    - short reserve gives an equal fraction of floors;
    - share independent of location;
    - a ward without a point is reported;
    - plan to timetable, with timetable litres = routed litres;
    - a far point raises km but not the share;
    - real-data scheduled wards.
  - `python tasks.py test`: 299 pass. `python tasks.py lint` passes.
- **Known limitations:**
  - Filling stations for routing are still the OSM stand-ins (Q1, ASSUMED).
  - Stops are whole tanker loads (the share is rounded to loads per point).
  - SMS/print wording of the timetable is for P4 (U2) / T5.
- **Handoff / next step:**
  - A7 combines this with A3 and A5 into the daily plan.
  - T6 stores `service_point_registered` entries.
  - P4 shows the timetable and the officer point registration.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/32

## `fix/a3-section-wards` — section -> ward link for the A3 fair queue

- **Owner / date:** P2, 2026-10-02.
- **Purpose:** Close A3's open gap: bookings are published per HMWSSB section, need (A2 entitlement) is per 2016 ward.
- **What we found:**
  - No public section boundaries or locations exist (R-P1, R-P2), but sections are named after localities.
  - Of 221 sections (Jan 2022 - Jan 2026), Nominatim finds 161 names inside GHMC.
  - A fixed 6 km division-outlier limit wrongly dropped correct sections in wide edge-of-city divisions (e.g. Manikonda, Nallagandla), so the limit is relative.
- **What we changed:**
  - `scripts/data/fetch_section_geocodes.py`: cleans names ("KONDAPUR (DIV 15)" -> "Kondapur") and searches Nominatim in the GHMC box (1 request/s). Raw answers are kept in `data/raw/geography/nominatim/hmwssb_section_search.json`, with `data/verification/section_geocode_manifest.csv`.
  - `scripts/evidence/build_section_wards.py`:
    - Best answer inside GHMC: places/boundaries first, then OSM importance.
    - Point in a 2016 ward, or the nearest ward within 500 m.
    - Division check: unused if farther than both 6 km and 3x the division's median distance from its median location.
    - Independent name check.
    - Outputs: `data/derived/crosswalk/section_to_ward_2016.csv` + `section_to_ward_summary.json`.
    - No Voronoi service areas (per R-P1).
  - `backend/app/services/booking_groups.py`: `group_for(section)` gives "ward:<id>" or "section:<name>"; `group_entitlements` uses A2 entitlement per ward, and the median ward entitlement as a flagged fallback for unplaced sections and wards without entitlement, so no booking is dropped.
- **Result:**
  - 142 of 221 sections placed, covering **80.5% of bookings**, in 98 wards.
  - Same-name sections land in or next to that ward in 97% of 66 pairs.
  - 14 outliers are not used: mostly common names (Defence Colony, Housing Board, Srinivas Nagar) or the wrong same-name place (Meerpet, Pragathinagar).
  - 60 sections have no OSM match (e.g. "CONTROL ROOM", "M.R.G.FILTERS"); 5 fall outside the ward layer.
- **Validation:**
  - 7 tests in `backend/tests/test_section_wards.py` were written first (missing data), then pass. They cover reproducible artifacts, one row per section, the coverage gate, the name check, outlier rules (Meerpet dropped, Manikonda kept), groups and entitlements for every section, and a real replayed day (6 May 2025) through `order_bookings`.
  - `python tasks.py test`: 306 pass. `python tasks.py lint` passes.
- **Known limitations:**
  - One point per section, not a service area.
  - About 20% of bookings use the flagged fallback entitlement.
  - Sections after the Feb/Mar 2026 re-cut are not covered.
- **Handoff / next step:**
  - A8 replays with these groups.
  - The same link can give E4/E5 approximate ward bookings (their remaining blocker) in a later PR.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/33

## `feat/a5-outage` — `A5`

- **Owner / date:** P2, 2026-10-02.
- **Purpose:** Response to sudden loss of piped supply (F10), and the outage-creation call that T5 (supply notices) uses.
- **What we changed:**
  - `backend/app/services/outage.py`:
    - **`create_outage(outage_id, ward_ids, start, end, source, reason, created_by, known_wards, people_affected)`** is the single creation function. Sources are `complaints` / `notice` / `officer`. It validates wards, source, reason, end > start and people >= 0, and returns `OutageEvent` + ledger args (new event type `outage_created`).
    - `detect_from_complaints(complaints, now)`: wards with >= 5 distinct `no_water` reports in 6 h (T1 `link_duplicates` children removed; timezone-aware times as T1 requires) become candidates needing officer confirmation.
    - `deprivation_weight(h) = exp(h / 24)`: rises faster the longer water is cut off (Holguin-Veras 2013); ASSUMED tau.
    - `plan_response(outages, critical_stops, capacity_litres, now)`: tier-0 critical stops first, then each active outage's 10 lpcd floor in priority order (longest cut-off first), then top-ups to 15 lpcd. Ended outages are listed, not served. `counts_toward_water_debt = False`.
    - `people_in_wards` (population from E2).
  - `config/allocation.py`: floor/target lpcd, tau, detection threshold and window, with sources.
- **Validation:**
  - 17 tests in `backend/tests/test_a5_outage.py` were written first (ImportError), then pass. They cover creation and ledger entry, 6 rejection cases, detection (distinct reports, duplicates not double-counted, old and leak reports ignored), convex deprivation weight, longest outage first when short, critical facilities first, floor-then-top-up never above target, ended outages, no debt, and population.
  - `python tasks.py test`: 323 pass. `python tasks.py lint` passes.
- **Known limitations:**
  - There is no verified critical-facility source yet (E2 facilities UNAVAILABLE); tier-0 stops come from officers.
  - Detection threshold and tau are policy assumptions.
- **Handoff / next step:**
  - **T5:** call `create_outage(..., source="notice", ...)` with the notice's wards, start/end and reason, then store the returned ledger args (T6).
  - A7 routes the response with the S3 planner.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/34

## `feat/e4-section-rates` — D1c billing data, E4 rates, E6 booking layer (limitation F3)

- **Owner / date:** P2 (covering P1), 2026-10-02.
- **Purpose:** Remove F3's NULL bookings-per-1,000 limitation.
- **What we found:**
  - HMWSSB publishes **billing and collection data by section** (Telangana portal dataset `3485ce9d-…`, GODL, Jan 2022-Aug 2026, 56 monthly CSVs). `noofcans` = connections per section and category.
  - Section names match the tanker table (183/184 sections, 100% of bookings, May 2025).
  - The portal metadata gives the category legend (D Domestic, DS Domestic-Slums, M0 Domestic with Flats, MB Multi Stored Buildings, PS Public stand post, FS Filling station, …).
- **What we changed:**
  - `scripts/data/fetch_hmwssb_billing.py`: raw files go to `data/raw/hmwssb_billing_portal/`, with `data/verification/hmwssb_billing_manifest.csv` and `backend/tests/test_d1c_billing.py`.
  - **E4** (`build_equity.py`):
    - `sections.csv` gains `domestic_connections_mean`, `flats_connection_share` and **`bookings_per_1000_connections`** (per month, REAL/REAL, same months as the bookings); `denominator_status = HMWSSB_DOMESTIC_CONNECTIONS`.
    - Per-1,000-people stays empty (no section population).
    - `wards.csv`: **approximate** ward bookings via `section_to_ward_2016.csv` and bookings per 1,000 people (Census 2011 via E2); wards without a placed section stay empty (`NO_PLACED_SECTION`).
    - The headline Gini 0.78 and top-10% share 67.7% are unchanged.
  - **E6** (`coverage.py`): the booking layer shows E4's approximate ward bookings (labelled `DERIVED_APPROXIMATE`) when E4 reports `APPROXIMATE_SECTION_POINT_IN_WARD`, and stays empty when blocked. The builder reads `equity/wards.csv`; the verifier and test compare with E4's own counts.
  - Solution doc: data row D19.
- **Result:**
  - 194/201 sections have a rate (median 11 bookings per 1,000 domestic connections per month; Kondapur 697, Hafeezpet 506, Madhapur 503). The 7 without a rate are facilities (control room, WTP, pipelines) or not billed.
  - 79.3% of bookings are placed on 94 wards.
- **Validation:** Tests were written first: `test_d1c_billing.py` (hashes, months, columns, section-name match) and E4 tests for the rate formula, empty per-people values, the Madhapur rate > 10x the median, ward mass preservation and statuses. A real bug was caught on the way: the new loop variable shadowed `count`. `python tasks.py test`: 328 pass. `python tasks.py lint` passes. All P1 verifiers pass.
- **Known limitations:**
  - One connection can serve many flats (`flats_connection_share` is reported).
  - Ward values are approximate (one point per section, about 20% of bookings unplaced).
  - Post-Feb-2026 sections are re-cut.
- **Handoff / next step:**
  - E3: connection growth and stability (next PR).
  - PS/FS category counts may help F9 (public taps) and Q1 (filling stations).
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/36

## `fix/e3-growth-stability` — E3 stability, E2 census, connection check (limitation F2)

- **Owner / date:** P2 (covering P1), 2026-10-02.
- **Purpose:** Remove F2's "all 145 wards high variability / joins not location-validated / no HMWSSB validation" limitation.
- **What we found:**
  - The CV-of-annual-log-change flag fired on every ward because Open Buildings counts jump **city-wide** from year to year: median ward change +9.6%, -0.4%, -4.8%, +7.1%, +1.3%, +11.7%, +2.7%. Google documents this ("building count over an area could also be unstable ... cloud cover, misalignment between input images and fewer Sentinel-2 timeframes for years 2016-2017").
  - The CV also explodes when annual growth is small (~3%).
  - E3 still read the old E1 number join.
- **What we changed:**
  - `build_growth.py`:
    - City-wide year shocks (cumulative median ward log change minus its own linear trend) are removed, keeping the city trend.
    - Least-squares trend per ward; `STABLE_TREND` if t >= `minimum_trend_t` (2.0, `config/growth.py`), else `REVIEW_NOISY_TREND`.
    - New columns `adjusted_annual_growth`, `trend_t`, `connection_growth_2022_2025`. The raw CV column is kept for transparency.
    - Census status and households come from E2.
    - `booking_validation` per ward from the section links.
    - Independent check: Spearman of ward building trend vs HMWSSB domestic connection growth 2022 -> 2025 (billing, sections placed on wards).
    - No household projection (growth stays a covariate, R-P1).
  - E5: reads the renamed summary key and has updated limitation text; its booking gate is unchanged (approximate transfer is not verified).
- **Result:**
  - 145/145 wards `STABLE_TREND` (median t 7.4, min 2.45); was 145/145 high variability.
  - City trend +3.24%/yr.
  - Connection check: Spearman **0.52** over 92 wards (the raw 2016-2023 ratio gives 0.47).
  - 143 approximate census joins from E2, 0 exact.
- **Validation:** E3 tests were rewritten first (E2 census, shocks removed and summing to 0, >= 140 stable, connection check rho >= 0.4 over >= 80 wards), then pass. `python tasks.py test`: 332 pass. `python tasks.py lint` passes. All P1 verifiers pass.
- **Known limitations:**
  - The connection check uses 2022-2025 vs the 2016-2023 building trend, and approximate section placement.
  - WorldPop/GHS-POP are still not extracted.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/38

## `fix/section-placement-v2` — better section -> ward placement

- **Owner / date:** P2, 2026-10-02.
- **Purpose:** Raise the share of bookings placed on wards (was 80.5%).
- **What we found:**
  - Most unplaced bookings were spelling variants of 2016 ward names ("Mehidipatnam" for Mehdipatnam, "Vengalraonagar" for Vengal Rao Nagar, "Hubsiguda" for Habsiguda). Nominatim needs exact spelling.
  - Common names ("Srinivas Nagar", "Kakatiya Nagar", "Meerpet") have several OSM places, and the first answer was taken.
- **What we changed:** `build_section_wards.py` adds a second chance for unplaced sections, each within 6 km of the division's centre (strict limit):
  1. Another OSM answer for the same name, nearest the division (`OSM_NEAR_DIVISION`).
  2. A 2016 ward whose name is a spelling variant: similarity >= 0.85, 0.05 ahead of the next (`WARD_NAME`).
  - The independent name check uses only OSM-placed sections, so it stays non-circular.
- **Result:**
  - 161/221 sections, **88.5% of bookings**, in 108 wards. Methods: 132 inside, 10 nearest-500 m, 5 OSM-near-division, 14 ward-name.
  - Rejected by the division check: Shapoornagar -> Saroornagar (20 km), Kodandapur(WTP) -> Kondapur (24 km).
  - Meerpet now uses the Meerpet in its division (1.06 km) instead of the one 13.8 km away.
  - Downstream: E4 ward bookings 87.1% placed (was 79.3%); E3 connection check over 102 wards, rho 0.51.
- **Validation:** Section tests were updated first (coverage >= 0.85, spelling variants, common names, rejection of a far ward name, strict limit for second-pass placements), then pass. `python tasks.py test`: 418 pass. `python tasks.py lint` passes. All P1 verifiers pass.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/39

## `feat/population-2025` — 2025 ward population estimate (F2 "growth only as context")

- **Owner / date:** P2 (covering P1), 2026-10-02.
- **Purpose:** Give every ward a current (2025) population and household estimate with an honest range, so E5 and A2 need not rely only on Census 2011.
- **What we found:**
  - GHS-POP R2023A (EU JRC, CC BY 4.0) 3-arc-second tiles are downloadable (168 MB each; the server limits speed per connection, so parallel byte ranges are used).
  - City-wide: buildings +3.2%/yr, GHS-POP +1.2%/yr, **HMWSSB domestic connections +2.18%/yr (REAL, 2022 -> 2025)**.
  - Ward by ward, building growth predicts connection growth (Spearman 0.50); **GHS-POP's ward growth does not (0.04)**, because it gives almost every ward +11-15%.
- **What we changed:**
  - `scripts/data/fetch_ghs_pop.py`: GHMC crops of the 2015 and 2025 tiles in `data/derived/population_inputs/`, with the source URL, zip SHA-256 and size, and the crop window in `manifest.json` (tiles are too large for git).
  - `scripts/evidence/build_population.py`:
    - Estimates per ward: A = Census 2011 x building trend, B = GHS-POP 2025 level, C = Census 2011 x GHS growth.
    - **Central** = building growth pattern, shifted so the city grows at the HMWSSB connection rate.
    - Low-high range, `WIDE_RANGE` flag (> 0.6).
    - Households = central / 2011 household size.
    - Outputs: `data/derived/population/`.
  - Solution doc: data row D20.
- **Result:**
  - 143 wards. City: Census 2011 6.36M; central 2025 **8.60M** (1.95M households); range across methods 7.33M (GHS level) to 10.11M (buildings).
  - 42 wards flagged wide range.
  - Fastest growth: Gajularamaram, Macha Bolarum, Gachibowli.
- **Validation:** `backend/tests/test_population_2025.py` was written first: crop hashes, reproducibility, central inside range, households formula, city total = Census x connection rate^14, A/C bracket the central total, central pattern validated against connections. A planned "average both patterns" design was dropped after this check showed GHS-POP ward growth carries no signal. `python tasks.py test`: 424 pass. `python tasks.py lint` passes.
- **Known limitations:**
  - Modelled, not counted.
  - The connection rate is assumed constant since 2011.
  - Household size is held at 2011.
  - One connection can serve many flats.
- **Handoff / next step:** E5 uses `households_2025_central` (reference year 2025); A2 can switch entitlement to 2025 households.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/40

## `feat/t4-ledger-wiring` — `T4` follow-up (intake events in the ledger)

- **Owner / date:** P3, 2026-10-02.
- **Purpose:** Log intake events (F14) to T6's stored ledger now that T6 (#35) and T4 (#37) are merged.
- **What we found:**
  - No intake event type existed. Adding them breaks T4's test `test_no_ledger_entries_while_no_intake_event_type_exists`, whose premise is that they are absent.
  - The ledger write happens after the report is saved, so a failing ledger (for example no `LEDGER_HMAC_KEY`) must not lose the report.
- **What we changed:**
  - `backend/app/services/ledger.py` (P2's file, `EVENT_TYPES` only, own commit): `complaint_received`, `complaint_merged`, `complaint_marked_spam`.
  - `backend/tests/services/test_intake_pipeline.py` (own commit): the one test adapted; the types are removed for that test only, so its purpose (no type, nothing written) is kept.
  - `backend/app/services/intake_pipeline.py`: `default_service` writes through `ledger_store.get_ledger()`; results carry `ledger_seq`; a ledger failure is logged and the report kept.
  - `backend/app/models/intake_item.py`: `ledger_missing` marker (set when an entry is expected, cleared once written); `IntakeService.intake_ids_missing_ledger()` lists such items.
  - Tests `backend/tests/services/test_intake_ledger.py`; docs `docs/P3_FEATURES.md`, `docs/features.csv` (T4 and T6 DONE), `docs/worklogs/T4.md`; workflow `.github/workflows/p3-t4.yml`.
- **Validation:**
  - 8 tests written first (failed before the wiring): entries for created / merged / spam items with a verified chain; nothing for duplicates or invalid items; no phone number, name, text, audio or household id in any payload; ledger failure keeps the report; default service uses the stored ledger; missing entries marked and listed.
  - After merging `main` (E3-FIX #38): `python tasks.py test` exit 0 (425 backend passed, 1 frontend test, all P1 verifiers); `python tasks.py lint` exit 0.
  - Task workflow `P3:T4` (`.github/workflows/p3-t4.yml`): T4 intake, ledger-wiring, T1 dedup and S3 spam/intake tests, ruff check and format check on the T4 files.
  - All test data is synthetic.
- **Known limitations:**
  - No automatic retry for items marked `ledger_missing`.
  - The new column needs a fresh database or a manual column add (no migrations; `create_all` does not alter tables).
- **Handoff / next step:**
  - T5 / T7 log through `ledger_store.record` in the same way.
  - Merge note: `feat/t5-notices` edits the T5 row next to the T4 and T6 rows in `docs/P3_FEATURES.md` and `docs/features.csv`; the branch merged second needs a one-line fix in each.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/42

## `feat/e5-screen` — E5 under-served field checks switched on (F4)

- **Owner / date:** P2 (covering P1), 2026-10-02.
- **Purpose:** E5 produced no field checks: it requires current households (<= 2 years old) and a ward booking transfer, and neither existed.
- **What we found:**
  - The 2-year rule is right for household exposure, but need shares (WAD, CAD, hardship) only exist in Census 2011 and are structural.
  - The portal never publishes zero rows (smallest section-month value is 1), so a section missing from an existing month had no bookings. Whole missing months (Dec 2022) stay missing.
  - A latent bug: `screen()` crashed (KeyError) when eligible and blocked wards were mixed, because per-model scores exist only for eligible wards.
- **What we changed:**
  - `config/underserved.py`: `max_need_reference_age_years = 15` (ASSUMED) for need shares; households keep the 2-year rule. `underserved.py` applies each limit to its own field, and the per-model lookup bug is fixed (regression test added).
  - `build_underserved.py`:
    - Households = 2025 central estimate (#40), reference 2025.
    - Bookings = Jan-Dec 2025 HMWSSB portal summed over sections placed in the ward (#33/#39); period complete when all 12 city months exist.
    - Approximate transfer accepted.
    - Every row carries `input_notes` (`APPROXIMATE_BOOKING_TRANSFER`, `HISTORICAL_NEED_REFERENCE_2011`, `MODELLED_HOUSEHOLDS_2025`, and `ABSENT_SECTION_MONTH_COUNTED_AS_ZERO` where it applies).
    - Wards without a placed section stay in data review.
  - `verify_underserved.py` and E6 test/verifier check consistency instead of "all closed". E6's field layer mirrors E5.
- **Result:** **107 wards screened, 7 field-check candidates** (peer-median screen): Barkas (WAD 28%, bookings 0.03x peers), Kanchanbagh, Falaknuma, IS Sadan, Chandrayangutta, Shastripuram, Mailardevpally. All are old-city/south wards with high off-premises water, low booking use, and high phone deficit or hardship. 38 wards stay in data review (37 without a placed section, partial-census wards).
- **Validation:** E5 tests were rewritten and added first (separate age limits, real screen, blockers, mixed-cohort regression), then pass. `python tasks.py test`: 426 pass. `python tasks.py lint` passes. All P1 verifiers pass.
- **Known limitations:**
  - A ward with an unplaced section may be undercounted and look under-served (stated in limits).
  - Candidates only mean "send someone to check".
  - The Bayesian models (NB/BYM2) are not run in the build (peer-median only).
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/43

## `feat/a6-debt` — A6 water debt in litres (F11)

- **Owner / date:** P2, 2026-10-02.
- **Purpose:** keep track of entitled water that did not arrive, so the planner (A7) can serve long-missed groups first and officers see long shortfalls.
- **What we built:** `services/water_debt.py`.
  - `settle_day(account, day, entitled, deliveries, ledger, now)` applies `D' = min(cap, max(0, D + entitled - confirmed delivered))` once per account per day, in order.
  - Only deliveries T3 counts (`delivery.counts_toward_debt`: Confirmed) reduce debt. Disputed, Unconfirmed and Failed do not.
  - Outage relief (A5) never reduces debt.
  - Extra water does not bank credit.
  - `credit_from_delivery` turns a closed T3 delivery into a credit.
  - Cap = `water_debt_cap_days` (7, ASSUMED) x the account's daily entitlement. The cut is logged.
  - Debt outstanding `water_debt_alert_days` (3) days in a row raises one alert per debt run. DERIVED from HMWSSB's "1 tanker in two days" rule; the margin is ASSUMED.
  - Every change or alert is one `water_debt_changed` ledger entry with ids and numbers only (`entity_type = water_debt_account`). A day that changes nothing writes nothing.
- **Decided here:** `trust.unresolved_delivery_changes_shortfall` (left open by T3) means "an Unconfirmed delivery reduces debt". It stays False, per F11.
- **Validation:** 19 tests in `tests/test_a6_water_debt.py`, written first and failing first (module missing). A mutation check (counting outage water) makes the outage test fail. `python tasks.py test`: 453 pass. `python tasks.py lint` passes.
- **Known limitations:** an account is any unit carrying an entitlement (booking group or ward). A7 chooses the unit, feeds daily entitlements and closed deliveries, and stores accounts. Debt does not yet change queue order; that is A7.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/45

## `feat/t5-notices` — `T5`

- **Owner / date:** P3, 2026-10-02.
- **Purpose:** Supply-notice feed (F15): an officer enters an HMWSSB supply-interruption notice; its areas are matched to wards; it becomes an A5 outage; both are logged in the stored ledger; residents can be alerted in te / ur / hi / en.
- **What we found:**
  - `docs/research/P3.md` F15 decided "Keep officer entry": HMWSSB notices are press releases with area lists and hours, with no machine-readable feed; D14 has not been fetched. So no parser was built.
  - A5's `create_outage` returns `entity_type` / `entity_id` outside its payload and puts `reason` (free text) in it. T5 passes the code `hmwssb_supply_notice` and copies the entity fields into the payload for `ledger_store.record`.
  - A notice does not state people affected, which A5 needs.
  - P1's tables: 221 sections (161 placed on a 2016 ward after SEC-FIX #39; 142 before), 145 wards, no locality alias table. "Uppal" is both Ward 10's name and a section P1 placed in Ward 7, so name matching must flag ambiguity. A 0.9 similarity threshold would accept the typo "Nacharm" (0.93), so the proposal is exact matches only.
- **What we changed:**
  - `backend/app/config/notices.py`: sources, area table paths, alert wording (te / ur / hi / en), OPEN values.
  - `backend/app/models/supply_notice.py` (+ `models/__init__.py`): raw text, areas, matched and flagged areas, times, hours, people affected, bases, fingerprint, `ledger_missing`.
  - `backend/app/services/notices.py`: `AreaIndex` (exact match = confidence 1.0; ambiguous, unplaced and near-miss names flagged, never guessed), `NoticeService.enter` (checks, duplicate refusal, A5 outage, ledger), `send_alerts`, `render_alert`.
  - `backend/app/routers/notices.py` + `backend/app/main.py`: `POST /notices` (officer entry).
  - Tests `backend/tests/services/test_notices.py`; docs `docs/P3_FEATURES.md`, `docs/features.csv` (T5 IN_PROGRESS), `docs/worklogs/T5.md`; workflow `.github/workflows/p3-t5.yml`.
- **Validation:**
  - 26 tests written first (import failed before the code existed): outage creation; `outage_created` and `notice_published` in the stored ledger with a verified chain; no free text or phone in payloads; duplicates not entered twice; unmatched, near-miss, ambiguous and unplaced areas flagged; no matched area means no outage; P1's real tables load (counts read from the files and compared with `AreaIndex`: 221 / 161 / 145); six malformed or backwards time ranges rejected; people affected from the officer, else the labelled Census fallback; alert wording in four languages; endpoint; ledger failure marker.
  - `python tasks.py test` exit 0: 460 backend passed, 1 frontend test, all P1 verifiers (run 2026-10-02, after merging #39, #40, #42 and #43; 458 before #43, which adds 2 E5 tests); `python tasks.py lint` exit 0.
  - Placement counts come from P1's section_to_ward_2016.csv and change when P1 updates it (142 -> 161 placed after SEC-FIX #39); the test reads them from the file.
  - Task workflow `P3:T5` (`.github/workflows/p3-t5.yml`): T5 tests, A5 outage and T6 ledger-store tests, ruff check and format check on the T5 files.
  - Notices and phone numbers in tests are synthetic; area names and ward ids come from P1's tables.
- **Known limitations:**
  - OPEN, owner to confirm: people-affected rule, exact-only matching, alert wording (native speakers and P4).
  - 60 of 221 sections are unplaced (after SEC-FIX #39); the crosswalk does not cover section names after the Feb/Mar 2026 re-cut; no locality alias table; Census 2011 ward population overstates partial-ward notices; no resident registry for alerts; no authentication until T10.
- **Handoff / next step:**
  - P2 (A5): consider putting `entity_type` / `entity_id` inside `create_outage`'s payload.
  - P4: review the alert wording; show flagged areas to the officer.
  - P1: a locality alias table and post-2026 section names would raise the matched share.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/44

## `feat/t7-explain` — `T7`

- **Owner / date:** P3, 2026-10-03.
- **Purpose:** Explanations and contest (F16): an explanation for every ward and every booking, the smallest single change that would move a booking up (counterfactual), text in te / ur / hi / en, and contests whose officer reply must give a reason, with both in the ledger.
- **What we found:**
  - A3's `order_bookings` takes each booking's arrival time, tier and group, the capacity, group entitlements (A2) and the carried-over round-robin state. Waiting time is an input (arrival time); **water debt is not** (A6 does not feed A3), so the counterfactual reports it as "not part of today's ordering" instead of varying it.
  - `order_bookings` with capacity = all pending gives a full order whose first `capacity` places equal today's served positions (tested on a real day), so waiting bookings get a place too.
  - A6 stores no debt accounts: debt is explained only when the caller passes a `DebtAccount`.
  - E2 has no Census values for the two partial-coverage wards; critical facilities are UNAVAILABLE for every ward.
  - No booking-to-filling-station mapping exists; the real-day test uses one division's bookings as one station's queue.
  - Note for P2: A2's `override_event` puts the officer's free-text `reason` into its ledger payload (not changed here).
- **What we changed:**
  - `docs/features.csv` / `docs/P3_FEATURES.md` status rows: T4 and T5 DONE, T7 IN_PROGRESS (own commit).
  - `backend/app/config/explain.py`: contest roles and targets (F16), reason and outcome codes (OPEN), text limit, counterfactual limits (OPEN), 15 templates in te / ur / hi / en (wording OPEN).
  - `backend/app/models/contest.py`, `contest_reply.py` (+ `models/__init__.py`): one table each; one reply per contest; text, SHA-256 of the text, `ledger_missing`.
  - `backend/app/services/explain.py`: `explain_ward`, `explain_booking`, `QueueDay`, `find_counterfactual` (re-runs P2's `order_bookings`, one input at a time), `reproduce`, `step_back`, `render_*`.
  - `backend/app/services/contest.py`: `ContestService.file` / `.reply` (reply needs a non-empty reason, an officer id and an outcome code), `contest_filed` / `contest_replied` via `ledger_store.record` with ids, codes and the text hash, `verify_text`, phone numbers removed from stored text, `ids_missing_ledger`.
  - Tests `backend/tests/services/test_explain.py`, `backend/tests/services/test_contest.py`; workflow `.github/workflows/p3-t7.yml`; `docs/worklogs/T7.md`.
  - No P1, P2 or P4 file was edited.
- **Validation:**
  - 39 tests written first (import failed before the code existed): the done-when (reply without a reason rejected, nothing stored or logged; contest and reply in the stored ledger, chain verifies); ward values equal E2 / A2 for every eligible ward of the real `ward_evidence.csv`; booking values equal A3's `Decision` on a real replayed day (A1 replay of the REAL May 2025 totals, daily split SYNTHETIC); counterfactual reproduces exactly on re-run and one step less is not enough; no-change and already-first cases; no-Census wards without numbers; debt with and without an account; no free text or phone in ledger payloads; hash check detects edited text; all templates in four languages. Counts come from the files.
  - `python tasks.py test` exit 0 (518 backend passed, 1 frontend test, all P1 verifiers); `python tasks.py lint` exit 0.
  - Task workflow `P3:T7`: T7 tests with A3 and A2 tests, ruff check and format check on the T7 files (run locally: 68 passed, clean).
- **Known limitations:**
  - OPEN, owner to confirm: contest reason codes, reply outcome codes, counterfactual limits, template wording (native speakers and P4).
  - Debt only with a `DebtAccount` until A7; one input changed at a time; Census 2011 on a historical 2016 ward map; no retry for `ledger_missing`; no API until T10.
- **Handoff / next step:**
  - P2: consider a code plus a text hash in A2's `override_event` payload instead of free text; A7 to store `DebtAccount`s.
  - P4: review the wording; show `no_census_data` wards and counterfactuals as returned.
  - T10: routes for explanations and contests.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/46

## `feat/a8-sandbox` — A8 policy sandbox (F19)

- **Owner / date:** P2, 2026-10-03.
- **Purpose:** compare today's process (B1) with the baselines and JalLekha on the same replayed bookings, as F19 and PS11 QE5 ask. This unblocks P3's T9 (confidence threshold chosen on replay) and T10.
- **What we built:**
  - `services/sandbox.py`: daily station queues with a trip capacity. A booking unserved for `booking_expiry_days` (3, ASSUMED) is unmet. Seven policies:
    - B1 FCFS at the nearest station.
    - B2 nearest first.
    - B3 largest bookers first.
    - B4 minimum cost (stations pooled, cheapest trips first).
    - B5 need first.
    - JL_F8 (A3 fair queue).
    - JL (JL_F8 + A4 reserve of 5% of trips for scheduled supply, ASSUMED).
  - Measures:
    - Unmet and need-weighted unmet share, waiting days.
    - Tanker km and km per kilolitre, unused capacity.
    - Fill-rate Gini, Jain and worst ward (among bookers).
    - **Need coverage** (litres per day per unit of entitlement over every ward, scheduled supply included): Gini, Jain, share of wards with no water.
  - `compare` gives mean, range and same-seed differences against B1.
  - `config/sandbox.py`: every value has a source and basis.
  - `scripts/sandbox/build_stations.py`: **90 stand-in filling stations** (REAL count; positions ASSUMED, booking-weighted k-means). HMWSSB publishes no station list (checked: tracking site, news, OSM).
    - Section points are geocoded (89% of bookings) or the division centre (11%, APPROXIMATE).
    - Road km = 2 x (straight line + 0.732 km in-section access, DERIVED from ward areas) x 1.35.
  - `scripts/sandbox/build_sandbox.py`: Mar-Jul 2025 (main) and Mar-Jul 2023 replays, 30 seeds, two capacity scenarios. Each station's capacity follows its share of the previous year's bookings.
    - fleet: 1,150 tankers x 9 trips.
    - tight: calibrated so B1 delivers 90%, the REAL Jun-Aug 2026 share (91.1%).
    - Outputs `data/derived/sandbox/results.csv` and `summary.json` (SIMULATION), with REAL baselines kept apart (booking Gini 0.78; delivered 99.9% in 2025, 91.1% Jun-Aug 2026).
  - `booking_groups.ward_group` added (shared group naming).
- **Results (30 seeds, means; SIMULATION):**
  - **Fleet capacity:** all policies serve 98.7-100% (REAL 2025: 99.9%). Capacity is not the problem: 39% of trips go unused, but stations sized on last year's demand miss growth areas. Pooling stations (B4) serves 100%.
  - **Tight capacity (2025, B1 = 90.0%):**
    - JL_F8 serves the same as B1 (89.9%) with shorter waits (0.90 vs 1.01 days) and slightly more even fill rates (Gini 0.068 vs 0.069).
    - B2, B3 and B5 cut waits but leave some wards almost unserved (worst ward fill 0.3% vs 37.8%).
    - B4 serves the most (94.0%) at 14% more km per kilolitre.
  - **Need coverage:** under every booking-only policy water follows bookings (Gini about 0.75-0.76). JL lowers it to 0.72-0.73 (0.70 in 2023), and no ward is left without water.
  - **Where JL is worse (listed in `summary.json`):** the 5% scheduled reserve costs booked service, -2.7 points served and +0.06 days wait in the tight 2025 case. Its worst booking ward is also lower (36.0% vs 37.8%).
  - Duplicate merge share is NOT_AVAILABLE: the replay has no complaints, and T1's calibration has not run (D13 extract not logged).
- **Takeaways for A7:** pooling station capacity across neighbours (as B4 does) is the biggest lever for booked service. A7 may want to let a station's spare trips serve a neighbour's queue. That is a design choice for the owner, not made here.
- **Validation:**
  - `tests/test_a8_sandbox.py` (15): policy order, capacity, expiry, B4 pooling, JL_F8 = A3 `order_bookings`, JL reserve via A4, determinism, Gini/Jain, measures, need coverage, B1 comparison. The tests were run after the code; deliberate breaks of B2 order, expiry and capacity each made tests fail, and the need-coverage test was written first and failed first.
  - `tests/test_a8_build.py` (8): stations reproducible; outputs match checks; 30 seeds per cell; same bookings per seed; tight B1 = 90% ± 1 point; summary recomputed from the results; REAL kept apart; JL-worse list complete; one seed re-run reproduces the committed rows.
  - `python tasks.py test`: 476 pass. `python tasks.py lint` passes.
- **How to rebuild:** `python scripts/sandbox/build_stations.py`, then `python scripts/sandbox/build_sandbox.py --workers 4` (about 30 min on 4 workers; about 450 MB each).
- **Known limitations:**
  - Stations are stand-ins.
  - Daily arrivals are synthetic.
  - Replay bookings have no tier, so tier 0/1 are not exercised.
  - Every A2 scheduled candidate is treated as officer-confirmed.
  - Km are not road-routed.
  - Water debt (A6) does not yet change queue order (A7).
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/47

## `feat/a8-pooling` — A8 follow-up: station trip sharing (JL_POOL)

- **Owner / date:** P2, 2026-10-03.
- **Purpose:** A8 showed that pooling station capacity (B4) is the biggest lever for booked service. The owner asked to research it and implement the best form for JalLekha.
- **Research** (`docs/research/P2.md`, "Station trip sharing"):
  - REAL problem: in July 2026 only 8 of 95 HMWSSB stations had pending bookings (NewsMeter); in April 2025, 14-15 stations had backlogs. HMWSSB adds tankers and shifts; no source shows trips lent between stations.
  - Theory: limited flexibility gives most of the gain of full pooling (Jordan & Graves 1995; Bassamboo, Randhawa & Van Mieghem 2012).
- **What we built:**
  - `services/station_sharing.py`: a station lends only the trips left after its own queue, to stations within a radius. OR-Tools min-cost max-flow moves the most trips at the least extra km. A7 will reuse it.
  - `sandbox.py`: new policy **JL_POOL** (JL + sharing). The borrower keeps its A3 fair order. A lent trip uses the direct lender-section km when known, otherwise the detour estimate.
  - `build_stations.py`: station-to-station km.
  - `build_sandbox.py`: a radius sweep (0-12 km, 5 seeds, main replay, tight capacity). Kneedle (Satopää et al. 2011) picks the knee. The "where JalLekha is worse" list now covers JL and JL_POOL.
  - `config/allocation.py`: `station_sharing_radius_km = 3.0` (DERIVED from the sweep; a median of 4 neighbours per station).
- **Results (30 seeds, SIMULATION):** JL_POOL vs B1:
  - Tight 2025: served 91.2% vs 90.0%; wait 0.64 vs 1.01 days; worst ward 46.9% vs 37.8%; need-coverage Gini 0.726 vs 0.757; need-weighted unmet 9.0% vs 10.0%; km per kl +12% (the only measure where it is worse; listed).
  - Fleet 2025: served 99.97% vs 98.7%.
  - Tight 2023: served 91.4% vs 90.0%.
- **Validation:**
  - `test_station_sharing.py` (6), written first and failing first.
  - JL_POOL sandbox tests (3), written first. Deliberate breaks (ignoring the radius, lending trips a station still needs) each made a test fail.
  - `test_a8_build.py`: the knee rule, the radius in use equals the committed sweep's knee, served never falls as the radius grows.
  - `python tasks.py test`: 552 pass. `python tasks.py lint` passes.
- **Known limitations:**
  - Whether HMWSSB allows cross-station tokens is not verified. This is an operating change for the officer to approve (A7).
  - Stand-in stations and synthetic daily arrivals as in A8.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/48

## `feat/a7-planner` — A7 daily planner (F8-F11, F17 gate stand-in)

- **Owner / date:** P2, 2026-10-03.
- **Purpose:** one daily plan that combines outage response, scheduled supply, the fair queue, water debt and station sharing, held as a DRAFT until an officer approves it with a reason.
- **What we built:** `services/planner.py`.
  - `build_plan(inputs, gate, ledger, now)` plans the day's trips in this order:
    1. Outage response (A5, at most `outage_max_fleet_share` = 30% of trips, ASSUMED).
    2. The scheduled-supply reserve (A4, `scheduled_reserve_share` = 5%, ASSUMED; the sandbox now reads the same value).
    3. Each station's A3 fair queue with the trips left. Outage and reserve trips come from every station in proportion (largest remainder).
  - Water debt (A6) raises a group's turns: entitlement x (1 + `debt_priority_weight` x debt / cap), so a group at the cap gets double turns (weight 1.0, ASSUMED).
  - Spare trips go to neighbours within 3 km (`station_sharing`, #48).
  - The output is an ordered list per station (with the lender for shared trips), next-day queue states and a SHA-256 digest of the plan. It is logged as `plan_created`.
  - Confidence: a `ConfidenceGate` protocol. `ProvisionalGate` (labelled PROVISIONAL) flags groups whose need comes from the A3 fallback (no Census data) **until P3's T9 replaces it**.
  - `mark_checked` (reason required, `ward_reviewed`) and `approve_plan` (reason required; refused while a flagged group is unchecked; refused twice; `plan_approved` carries the digest of the exact plan). Reason text stays off the ledger (SHA-256 and length only, as T7 does).
- **Validation:**
  - `tests/test_a7_planner.py` (13): A3 equivalence, outage first, reserve, debt raises turns, sharing within/beyond the radius, trips never overspent, flags block approval, reasons required, end-to-end plan → check → approve with ledger entries and chain verify, determinism, bad input, inputs not mutated.
  - Deliberate breaks (no flag check, debt ignored, outage not deducted) each made tests fail.
  - `python tasks.py test`: 565 pass. `python tasks.py lint` passes.
- **Known limitations:**
  - The confidence gate is a stand-in; swap in T9's gate (same protocol) when it merges.
  - Routing of scheduled points is A4's `plan_scheduled_supply` (the registry starts empty). Booked trips are single loads (station → household → station).
  - Cross-station sharing needs HMWSSB's agreement (an officer decision).
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/49

## `feat/a7-routes` — A7 follow-up: routes and the planner replay for T9

- **Owner / date:** P2, 2026-10-03.
- **Why:** checking #49 against its own spec found two gaps. The plan had no **routes** (features.csv: "queue + schedule + outage → routes → ..."), and there was no **per-day replay output** that T9 needs (P3_BUILD_PLAN: "plan, inputs, quality signals").
- **What we changed:**
  - `planner.py`: tier-0 critical stops, outage points (registered points in the outage wards) and scheduled points are routed together by the S3 OR-Tools planner, using the tankers set aside for those trips (fleet sorted by id; enough for the outage + reserve trips at `max_trips_per_tanker`).
    - Priority: critical 100 (mandatory) > outage up to 90 (floor stops mandatory) > scheduled up to 80.
    - Output: `special_stops` (kind, place, ward, tanker, trip, sequence, arrival, litres), `special_tankers`, and `unrouted` (NEEDS_LOCATION / NEEDS_SERVICE_POINT / NO_FLEET_GIVEN / NOT_ROUTED), so no need is skipped silently.
    - Routes are part of the plan digest. `plan_created` logs the routing status, routed stops, km and unrouted count.
  - `scheduled_supply.py`: `scheduled_demands` extracted from `plan_scheduled_supply` (behaviour unchanged; A4 tests pass) so the planner reuses A4's demands.
  - `scripts/sandbox/build_planner_replay.py`: the real planner day by day on the A8 replay (Mar-Jul 2025, seed 0, tight capacity, 3 km sharing, scheduled reserve).
    - Outputs `data/derived/planner_replay/days.csv` (per-day trips, served, waiting, expired, trips lent, flags, digest) and `groups.csv` (per day and group: pending, served, served by a lent trip, entitlement and the quality signals need basis, location status and flag). Labelled SIMULATION.
    - `replay(setup, entitlement=..., fallback_groups=...)` lets T9 re-run the same days with a degraded signal and compare plans by digest.
    - Cross-check: the planner serves 91.1% of bookings, matching A8's JL_POOL (91.2%).
- **Validation:**
  - 4 routing tests and 5 replay tests. The routing tests were written first and failed first; one expectation was corrected because the router delivers whole 5,000 l loads.
  - `python tasks.py test`: 574 pass. `python tasks.py lint` passes.
- **Known limitations:**
  - The replay has no outages and does not settle debt (no delivery outcomes are simulated).
  - Routing needs registered service points (the registry starts empty) and officer-entered locations for critical stops.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/50

## `feat/t2-forecast` — `T2`

- **Owner / date:** P3, 2026-10-03.
- **Purpose:** Forecast and backtest (F5): monthly HMWSSB bookings per section and city, 12 months ahead, with a reproduced seasonal-naive baseline, a rolling-origin backtest, bottom-up reconciliation, split-conformal intervals and a capacity check.
- **What we found:**
  - `V-VERIFY_REVIEW.md`, which recorded how 21.9% / 35.1% were computed, was never found. The protocol was recovered by reproduction on 2026-10-03 and confirmed by Padmaja: `noofbookings`; seasonal naive (same month a year earlier); Dec 2022 missing, not zero, so Dec 2023 is not scored (13 months, Jan 2023 - Feb 2024); all sections, missing = 0; city MAPE = mean of monthly errors; section WAPE pooled. Result 21.89% / 35.12% on the S2 files. `delivered` and both-years sections also land within 0.1 pp; Dec 2022 as zero and per-month WAPE do not.
  - On the longer D1b portal history (to Jan 2026, before the Feb/Mar 2026 re-cut) seasonal naive scores 26.28% / 47.67%, well above the S2 window; the 80% interval covers only 0.77 there. Section names change every year (no mapping applied).
  - Naive x growth beats the baseline on portal city MAPE (19.77 vs 26.28) but not on section WAPE (48.90 vs 47.67), and is worse on both in S2, so it is not selected.
  - `tasks.py setup` installs no scikit-learn or lightgbm, and weather (D7) / groundwater (D8) data are not in the repo, so the global gradient-boosting model is not run.
  - `main` at `ef2e53c` (still at `73efb55`, U3) fails 3 tests outside T2 (see Validation).
- **What we changed:**
  - `docs/features.csv` / `docs/P3_FEATURES.md` status rows: T7 DONE, T2 IN_PROGRESS (own commit).
  - `backend/app/config/forecast.py`: the recovered protocol with its date; T2 settings (growth window, coverage minimums, `forecast_table_note`, `model_selection_rule` OPEN); `trips_per_tanker_per_day` OPEN with no default.
  - `backend/app/services/forecast.py`: panel loader (P2's `hmwssb.read_rows`, unchanged), baseline protocol, seasonal naive, naive x growth, leak-proof rolling backtest, bottom-up reconciliation, split-conformal intervals, model selection, capacity planner, forecast table.
  - `scripts/forecast/run_backtest.py`; outputs `data/derived/forecast_backtest.csv` and `data/derived/forecast_table.csv` (every derived column has a `_basis`; the table is labelled as using section names from before the Feb/Mar 2026 re-cut, so Feb 2026 onwards cannot be compared section by section with current HMWSSB sections).
  - Tests `backend/tests/services/test_forecast.py`; workflow `.github/workflows/p3-t2.yml`; `docs/worklogs/T2.md`.
  - No P1, P2 or P4 file was edited.
- **Validation:**
  - 19 tests written first (`ImportError` before the code existed), including the done-when (21.9% / 35.1% within 0.1 pp on the S2 files, scored months read from the files), no leakage, reconciliation sums, coverage on a hand-checkable fixture, Dec 2022 never zero, sections appearing / disappearing, and the capacity planner refusing to run without trips per day.
  - `python tasks.py test` exit 1: 591 backend passed, 2 failed; frontend 1 failed. **All 3 failures are inherited from `main` and none is in T2 files**; they fail identically on a clean checkout of `main`, and their files were not edited, skipped or marked:
    - P4 `frontend/src/App.test.tsx` > "translates resident and driver shells and applies Urdu right-to-left direction": `Unable to find an accessible element with the role "heading" and name "آج کا کام"`; also red on `main`'s CI at `ef2e53c`.
    - P2 `backend/tests/test_a8_build.py::test_stations_are_reproducible_committed_and_labelled` (`data/derived/sandbox/section_points.csv`: 26 coordinates differ in the last digits, e.g. BACHUPALLY (PD 7) lat 17.49872903654913 committed vs 17.498729036549125 rebuilt) and `::test_one_seed_reproduces` (B1 `tanker_km` 775397.417 vs 775397.417003). They pass on Linux CI and fail on Windows 10.0.26200, Python 3.11.9, shapely 2.1.2 / GEOS 3.13.1, numpy 2.2.6.
  - All P1 verifiers pass when run separately. `python tasks.py lint` exit 0. The `P3:T2` workflow commands pass locally (22 tests, baseline line, ruff).
- **Known limitations:**
  - OPEN, owner to confirm: trips per tanker per day; the model selection rule; the scikit-learn / lightgbm dependency (team); Chronos-2 (no-LLM rule); where the published forecast starts (pre-re-cut section names).
  - Short series (13 scored months on S2); coverage is pooled over months and sections that are not independent; portal coverage under target (0.77 / 0.87); no weather or groundwater covariates; section names not mapped across years.
- **Handoff / next step:**
  - Follow-up: a global gradient-boosting model once the team decides the dependency and D7 / D8 exist.
  - P4: fix `App.test.tsx` on `main`. P2: check `test_a8_build.py` on Windows. This branch is pushed only after `main` is green.
  - P1: weather (D8), groundwater (D7) and a trips-per-day source. Owner: confirm the recovered protocol before 21.9% / 35.1% go on slides.
  - T8 builds on the forecast table.
- **Pull request:** pending.
