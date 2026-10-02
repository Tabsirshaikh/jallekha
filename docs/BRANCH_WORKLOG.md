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
- **Pull request:** pending
