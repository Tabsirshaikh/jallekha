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
- **Handoff / next step:** After S4 review/merge, implement U1 translations and Urdu RTL visual review, then proceed to U2 resident app when P3 T4 is ready.
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
- **Pull request:** pending
