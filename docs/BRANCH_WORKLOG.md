# Branch worklog

## `feat/weekly-water-priority` - 2026-10-07

- Owner approved research-based weekly service feedback after reviewing the implementation plan.
  Read project guide, F1/F4/F7/F11 limits and research; isolated worktree, no other checkout edits.
- TDD: missing calculation/UI modules failed first; current supplied section plan initially
  rejected; day closure failed looking for unavailable 2026-10 portal totals. All fixed.
- Added append-only supply reviews, ledger digests, officer/field-worker form in four languages,
  population-based emergency requirement and complete-record/confirmed-delivery gates.
- Current priority map/selected-section panel keeps Census baseline separate. Section debt takes
  precedence over ward proxy, including a true zero. Historical recipes remain unchanged.
- Current supplied section plans freeze weekly evidence in their identity/recipe, adjust turns
  without double-counting debt, and reserve supply for verified shortages without bookings.
  Supplied records also feed live booking signs and close-day accounting.
- Simulation counterfactual: neglected area 7 -> 19 of 20 trips; covered area 13 -> 1; unknown
  records keep baseline. No real field validation and no globally optimal-policy claim.
- Validation: 81 affected backend tests pass; final weekly/reserve guard rerun 12 pass;
  all 205 frontend tests, full lint/type checks, translation check (934 strings) and production
  build pass. Browser verified live isolated API/UI, English and Hindi, unknown records and
  the new priority layer. No unrelated PyMC/model-training suite rerun.
- Translation export now includes shared .ts dictionaries (including five previously omitted
  live-reason strings). Fixed one inherited Ruff style violation in section-map serialization;
  no algorithm/output changes there. No push or merge authorized for this branch.


## `fix/forecast-capacity-sync` — warning quality follow-up, 2026-10-07

- Owner asked to address the remaining F5/F6 bugs and explain groundwater/reservoir use.
  Read F5/F6 limitations and P3 before work; no spatial sampling or edits to the other checkout.
- TDD failures observed for preserved known capacity, date window, API filtering, division
  annotation matches, rolling range leakage, joint water candidate and empty/missing GBM input.
  Fixes preserve explicit zeros, exclude absent training observations and avoid empty prediction crashes.
- Forecast matches 77 approximate/196 unmatched; local-weather GBM wins the unchanged 31-origin
  rule: city 27.72% vs31.16%, section37.76% vs48.35%, p=.0073. Joint water Ridge44.22%/52.89% loses.
  Previous-year rolling city errors: 80/90 nominal coverage76.19%/90.48% on21 months, exploratory;
  no independent future or multi-step calibration claim. Frozen2026 holdout remains unchanged.
- Added twelve-month shortage outlook, optional API month filters, Hyderabad-date next-three-month
  view and current lead times. Legacy first-three-month risk file retained for compatibility.
  Nov-Jan view819 rows:27high/30medium/154low/608unknown (588unmatched+20missing seasonal history).
- Known capacity/groundwater remain shown without a forecast. UI explains estimated trips,
  missing data, stale observations and measured city range reliability in four languages;
  localized warning summaries replace raw English text outside English. Source stock percentages
  remain context; reporting zeros are not verified empty reservoirs.
- Portal metadata still endsAug2026; no newer month invented. Actual capacity/section GIS absent.
  API examples/shapes unchanged; new query parameters documented and OpenAPI regenerated.
  Browser verified live API on5198 and UI5197; no browser errors, correct Nov-Jan dates.
- Validation:70 affected backend tests passed, including the existing forecast/backtest suite;
  frontend202 tests passed on the full run and its one outdated date-copy assertion was updated
  and passed on rerun. Lint/type checks, translation checks and production build pass. Verified
  live filter counts819/27high/30medium/608unknown/154low and Hindi dates in the real browser.
  No repeated full PyMC suite for this follow-up; the owner requested focused checks.

## `fix/forecast-capacity-sync` — synchronized capacities, 2026-10-07

- Isolated worktree `../jallekha-capacity-sync`, based on fetched main `6b6bff1`; no edits to
  the other session's checkout. TDD: current-source capacity assertion, new CLI test and existing
  shortage reproduction test failed first; all now pass.
- Routing had reassigned home stations without regenerating F5/F6 capacities. Added a capacity-only
  refresh and shared section-capacity transfer; full refresh also updates U6 snapshot automatically.
- Rebuilt 168 forecast section/month capacities, 42 shortage rows and saved screen data. Ahmed
  Nagar September capacity 112.1 -> 97.7 trips (ASSUMED split). Predictions and ranges preserved;
  all risk labels unchanged. Test checks no fetch/fitting, cross-output agreement and repeatability.
- Affected backend tests pass; full test command exited zero, including frontend, translations
  and all data verifiers. Fixed a CLI help line-length lint issue without changing its text;
  full lint passes. No API/UI string changes, source-manifest changes or new model fitting.
  Owner subsequently authorized committing and pushing this fix branch; no PR/merge.

## `feat/place-missing-sections` — location review, 2026-10-07

- Fetched current origin/main; isolated worktree `../jallekha-placement-review`. Brought
  latest main into the existing owner-assigned branch without rewriting shared history.
- Reviewed all eight ambiguous and three far-away candidates. Five named OSM places accepted;
  six unresolved review rows and twelve NOT_FOUND rows have blank coordinates. All 22 existing
  automatic candidates retain their weaker status, including documented landmark proxies.
- New CSV: 45 identities; ACCEPT_AUTO 22/66,374 bookings; ACCEPT_REVIEWED 5/24,543;
  UNPLACED 18/26,647. Accepted candidate coverage 90,917 (77.33% of missing-location cohort).
  Every point is copied from logged candidates; no existing data or section map changed.
- Four artifact tests failed before CSV creation, then passed. Evidence/reasons in
  `research/SECTION_PLACEMENT_REVIEW.md`. No UI/API changes; push only this branch, no PR/merge.
- Final checks: lint, 200 frontend tests, translations and all task data verifiers pass.
  Full backend: 1,025 pass, one inherited shortage-artifact reproducibility failure. A8 station
  changes make 42 saved capacity/reason rows stale; risk categories are unchanged. The current
  forecast table contains the same stale section-capacity inputs. Existing data was preserved;
  no full-green claim. Fix verification report: `research/E5_F5_FIX_VERIFICATION.md`.

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
- **What we changed:** Added English, Telugu, Urdu and Hindi resident flows for issue reports, request tracking and an area card. Reports persist in IndexedDB, can include device location only after the resident opts in, and sync idempotently through T4's `/intake/batch` contract when online; the dev server proxies `/intake` to the local API. Added a web manifest and service worker for cached app-shell use. U10 now supplies an explicitly synthetic sample ward card and SMS summary, and request tracking labels its demo delivery code as SIMULATION.
- **Validation:** Frontend lint, typecheck and production build pass. `git diff --check` passes. No tests were run.
- **Known limitations:** Live delivery-code assignment and verified ward service information need backend/API support. Intake submission also needs the API running and reachable at `/intake/batch`. All translations are drafts pending native-speaker review.
- **Handoff / next step:** Coordinate with P3 on resident-facing delivery-code and ward-information API shapes; then connect the card to verified data.
- **Pull request:** pending.

## `feat/u8-explain` — `U8`

- **Owner / date:** P4, 2026-10-03.
- **Purpose:** Show why a booking received its sample queue position and let residents file a contest for officer reply.
- **What we found:** T7 explanation and contest services are present on `main`; T10 has not added their HTTP routes. The service's contest reason and reply outcome codes are therefore used as UI choices, but no service call is made.
- **What we changed:** Added a four-language explanation and contest preview, with a synthetic booking rationale, a clearly illustrative counterfactual, contest form, and reason-required officer reply form. Preview contests persist in local browser storage only.
- **Validation:** `python tasks.py lint`, frontend production build and `git diff --check` pass. The task workflow `.github/workflows/p4-u8-u10.yml` repeats frontend lint and build. No tests were added or run.
- **Known limitations:** Queue values are synthetic and the counterfactual is explanatory copy, not calculated output. Contest filing/reply does not call T7 or update the ledger. Native-speaker review remains required.
- **Handoff / next step:** Connect this screen to T10 explanation and contest routes when available; replace fixtures with T7 output.
- **Pull request:** pending.

## `feat/u9-impact` — `U9`

- **Owner / date:** P4, 2026-10-03.
- **Purpose:** Compare policy-sandbox outcomes while showing the basis of every reported value.
- **What we changed:** Added `scripts/frontend/build_u9_snapshot.py` and `frontend/src/data/u9Impact.json`, a compact summary of A8 `results.csv` grouped by replay, scenario and policy across seeds. The UI compares selected metrics and ranges, marks every result SIMULATION, and keeps duplicate-complaint impact UNAVAILABLE.
- **Validation:** Snapshot generated from committed A8 results (32 replay/scenario/policy groups, 30 seeds each). `python tasks.py lint`, frontend production build and `git diff --check` pass. The task workflow `.github/workflows/p4-u8-u10.yml` repeats frontend lint and build. No tests were added or run.
- **Known limitations:** The sandbox output is simulated, not observed field impact. Duplicate-complaint reduction cannot be measured from this replay. This screen does not claim that JalLekha improves outcomes over B1.
- **Handoff / next step:** Refresh the snapshot when A8 results change; use validated field outcomes only after they are collected and reviewed.
- **Pull request:** pending.

## `feat/u10-cards` — `U10`

- **Owner / date:** P4, 2026-10-03.
- **Purpose:** Give residents a simple ward summary and an SMS-sized version of the same information.
- **What we changed:** Added two localized sample ward cards with need, monthly bookings, deliveries, waiting bookings, an example schedule and a copyable SMS summary. Every value and schedule carries a SIMULATION label. Added a clearly marked sample delivery code to U2 request tracking.
- **Validation:** `python tasks.py lint`, frontend production build and `git diff --check` pass. `.github/workflows/p4-u8-u10.yml` repeats frontend lint and build. No tests were added or run.
- **Known limitations:** T10 report-card route and verified ward schedule are unavailable. The displayed values are synthetic examples and must not be treated as local service information.
- **Handoff / next step:** Replace sample wards with the T10 report-card response and approved SMS templates when available.
- **Pull request:** pending.

## `feat/x1-docs` — `X1`

- **Owner / date:** P4, 2026-10-03.
- **Purpose:** Document the prototype, pitch/demo flow and release handoff.
- **What we changed:** Updated the README status and added `docs/P4_DEMO.md` with a slide outline, three-minute demo script and run steps.
- **Validation:** Documentation checked against current feature scope and explicit sample-data limits. Frontend build, `python tasks.py lint` and `git diff --check` pass. Release tag intentionally waits until the branch merges, required checks pass and the owner confirms a version.
- **Known limitations:** The repository contains no PowerPoint deck to edit. The notes provide content for the deck. No release tag is created from an unmerged feature branch.
- **Handoff / next step:** Apply the outline to the presentation, merge the branch, then create the owner-approved release tag from green `main`.
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

## `feat/u5-evidence` — `U5`

- **Owner / date:** P4, 2026-10-03.
- **Purpose:** Give officers an atlas for historical water-access and growth evidence, booking equity, and under-served field-check hypotheses.
- **What we found:** Merged E2–E6 outputs include ward evidence and historical polygons, but the Census join is approximate, the ward geography is incomplete and historical, section-to-ward booking placement is approximate, and field-check flags are hypotheses rather than ground truth. T10 is not needed to render this local snapshot.
- **What we changed:** Replaced the officer Water Access placeholder with a localized, lazy-loaded evidence experience. It includes a selectable 145-polygon historical ward map, ward search and evidence details, Census 2011 water-access context, Open Buildings 2016–2023 building-change signals, exact section-level booking concentration, approximate ward booking rates, and E5 field-check candidates with reason values and thresholds. `scripts/frontend/build_u5_snapshot.py` regenerates the local JSON snapshot from merged E2–E6 outputs.
- **Validation:** Frontend lint, production build, and `git diff --check` pass. The production build splits U5 into a separate evidence chunk. Added `.github/workflows/p4-u5.yml` to repeat lint and build in CI.
- **Known limitations:** The map is the incomplete `GHMC_2016_150` historical scheme, not current boundaries. Census values use an approximate 2009-to-2016 crosswalk and refer to 2011. Open Buildings indicates building change only, not population growth. Citywide section booking totals are exact; ward rates use approximate section placement. Field-check flags are screening hypotheses and do not establish unmet need, neglect, or entitlement. Snapshot data must be regenerated when source outputs change; no live T10 integration is included.
- **Handoff / next step:** Refresh the generated snapshot from reviewed E2–E6 outputs and connect T10 when its API contract is ready. Keep unavailable metrics null and preserve the historical/approximate labels.
- **Pull request:** pending.

## `feat/u6-forecast` — `U6`

- **Owner / date:** P4, 2026-10-03.
- **Purpose:** Show observed tanker demand, forecast ranges and shortage warning signals to officers.
- **What we found:** The Telangana Open Data Portal tanker files contain monthly city totals from January 2022 through August 2026, with December 2022 empty. T2 and T8 remain TODO; the repository records seasonal-naive backtest errors of 21.9% city MAPE and 35.1% section WAPE but does not document the exact protocol. GHMC groundwater station coverage and extraction/licence are unconfirmed; no verified reservoir series is available.
- **What we changed:** Added a localized officer screen with a real monthly demand chart, latest/peak actuals, the documented baseline benchmark and accuracy caveat, plus 80%/90% illustrative range fixtures and demo-capacity shortage scenarios. The UI labels history REAL, benchmark DERIVED, and projections/capacity SIMULATION. `scripts/frontend/build_u6_snapshot.py` regenerates the snapshot from the portal CSVs and records the missing month as null. Added `.github/workflows/p4-u6.yml`.
- **Validation:** Frontend lint, production build, and `git diff --check` pass. CI workflow repeats frontend lint and build. No tests were run.
- **Known limitations:** Demo forecast intervals are not calibrated outputs, the capacity threshold is illustrative, and shortage cards are not operational warnings. Accuracy benchmarks are historical and their protocol is undocumented. Groundwater and reservoir inputs are unavailable; T2/T8 APIs are not connected.
- **Handoff / next step:** Replace fixtures with T2 forecast and backtest results plus T8 risk output when those tasks land. Confirm groundwater coverage/licence and fleet trip capacity before showing operational risk.
- **Pull request:** pending.

## `feat/u7-plan` — `U7`

- **Owner / date:** P4, 2026-10-03.
- **Purpose:** Let an officer review the daily allocation queue, scheduled trips, priority weights, confidence flags, and a reason-gated approval.
- **What we changed:** Added a four-language officer plan screen with a synthetic queue and schedule, adjustable need/service-gap/debt weights, an explicit “who gains” comparison, a flagged group that requires a manual review tick, and an approval reason field. The approval confirmation is local to the preview; no API, dispatch, entitlement, or ledger is changed. Connected the view to officer navigation and added a dedicated CI workflow.
- **Validation:** Frontend lint and production build pass; `git diff --check` passes. No tests were run.
- **Known limitations:** T10 plan/approval API integration is not available. All groups, values, trips, schedule, scores and resulting approval are SIMULATION fixtures; weighting is not a validated policy. Translation strings need native-speaker review.
- **Handoff / next step:** Replace preview fixtures with A7/T10 responses when the API is available. Preserve server-side confidence/approval gates and ledger behavior.
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
  - `main` at `d12e4fd` is green on CI; locally (Windows) P2's two A8 tests fail (see Validation).
- **What we changed:**
  - `docs/features.csv` / `docs/P3_FEATURES.md` status rows: T7 DONE, T2 IN_PROGRESS (own commit).
  - `backend/app/config/forecast.py`: the recovered protocol with its date; T2 settings (growth window, coverage minimums, `forecast_table_note`, `model_selection_rule` OPEN); `trips_per_tanker_per_day` OPEN with no default.
  - `backend/app/services/forecast.py`: panel loader (P2's `hmwssb.read_rows`, unchanged), baseline protocol, seasonal naive, naive x growth, leak-proof rolling backtest, bottom-up reconciliation, split-conformal intervals, model selection, capacity planner, forecast table.
  - `scripts/forecast/run_backtest.py`; outputs `data/derived/forecast_backtest.csv` and `data/derived/forecast_table.csv` (every derived column has a `_basis`; the table is labelled as using section names from before the Feb/Mar 2026 re-cut, so Feb 2026 onwards cannot be compared section by section with current HMWSSB sections).
  - Tests `backend/tests/services/test_forecast.py`; workflow `.github/workflows/p3-t2.yml`; `docs/worklogs/T2.md`.
  - No P1, P2 or P4 file was edited.
- **Validation:**
  - 19 tests written first (`ImportError` before the code existed), including the done-when (21.9% / 35.1% within 0.1 pp on the S2 files, scored months read from the files), no leakage, reconciliation sums, coverage on a hand-checkable fixture, Dec 2022 never zero, sections appearing / disappearing, and the capacity planner refusing to run without trips per day.
  - After merging `main` (`d12e4fd`): `python tasks.py test`: 591 backend passed, 2 failed; frontend 1 passed. The 2 are inherited, none in T2 files: P2 `backend/tests/test_a8_build.py::test_stations_are_reproducible_committed_and_labelled` and `::test_one_seed_reproduces` fail on Windows only (last-digit float differences, e.g. BACHUPALLY (PD 7) lat 17.49872903654913 committed vs 17.498729036549125 rebuilt; B1 tanker_km 775397.417 vs 775397.417003; Windows 10.0.26200, Python 3.11.9, shapely 2.1.2 / GEOS 3.13.1) and pass on Linux CI; identical on a clean checkout of `main`; not edited, skipped or marked.
  - All P1 verifiers pass when run separately. `python tasks.py lint` exit 0. The `P3:T2` workflow commands pass locally (22 tests, baseline line, ruff).
- **Known limitations:**
  - OPEN, owner to confirm: trips per tanker per day; the model selection rule; the scikit-learn / lightgbm dependency (team); Chronos-2 (no-LLM rule); where the published forecast starts (pre-re-cut section names).
  - Short series (13 scored months on S2); coverage is pooled over months and sections that are not independent; portal coverage under target (0.77 / 0.87); no weather or groundwater covariates; section names not mapped across years.
- **Handoff / next step:**
  - Follow-up: a global gradient-boosting model once the team decides the dependency and D7 / D8 exist.
  - P2: check `test_a8_build.py` on Windows.
  - P1: weather (D8), groundwater (D7) and a trips-per-day source. Owner: confirm the recovered protocol before 21.9% / 35.1% go on slides.
  - T8 builds on the forecast table.
- **Pull request:** pending.

## `fix/e5-models` — E5: run the NB / BYM2 models so field-check flags are checked across methods

- **Owner / date:** P1 (work done by the repo owner), 2026-10-03.
- **Why:** E5 was marked DONE, but `build_underserved.py` called `screen(areas)` without model results, so the done-when ("flags stable across model variants") was never evaluated. BYM2 also needed a reviewed ward-adjacency graph, which did not exist.
- **What we changed:**
  - `scripts/evidence/build_ward_adjacency.py`: rook adjacency (at least 50 m shared border, 10 m snap, UTM 44N), 145 wards and 364 edges, plus a review record checked by SHA-256. Owner-reviewed on automated evidence: 360 of 364 edges stable across 9 settings; live OSM agrees on 356 of 356 comparable edges; Wikipedia spot-check.
  - `scripts/evidence/fit_underserved_models.py`: fits NB, BYM2 and BYM2_SHRINKAGE out of fold (5 folds) on the gated cohort and writes `data/derived/underserved/model_results.json` with a cohort fingerprint, graph hash, config and environment. Fitting runs on Linux (WSL or CI); tests never re-sample, and `build_underserved.py` refuses stale results.
  - `services/underserved_models.py` and `config/underserved.py`: options added during the BYM2 diagnosis (likelihood, rho prior, restricted regression, island handling, ICAR-only structure, inverse-sqrt NB dispersion prior, PC prior on the spatial spread), each with its source. Defaults are now the settings of the committed results.
  - `services/underserved.py`: when the spatial models fail their diagnostics, a candidate must still agree across every method that passed, which needs at least peer and NB (`AGREED_FIELD_CHECK_CANDIDATE`). Four-way stability is still only claimed when all four pass (`stability_evaluated`). The summary lists `agreement_methods` and `methods_failed_diagnostics`.
  - `.github/workflows/p1-e5-models.yml`: Linux job that fits the models and uploads the results for review.
  - Each candidate reason appears once; the WAD reason is no longer repeated per method, and ratio reasons name their method.
  - U5 (after merging `main`): snapshot rebuilt (6 candidates); the field-check cards say "PEER + NB", label the NB ratio reason separately, and key reasons by code and method (no duplicate React keys). `docs/LIMITATIONS.md` updated for T2, U2-U6.
- **Result:** NB passes every check in all folds. BYM2 and BYM2_SHRINKAGE pass 8 of 10 folds but fail fold 1 for every seed (NB alpha and spatial sigma cannot be separated without its 22 wards), so they are recorded as DIAGNOSTICS_FAILED; the strict gate was kept. Candidates: 7 peer-only → **6 agreed by peer and NB** (Jaccard 0.86); Mailardevpally becomes `MODEL_SENSITIVE_REVIEW`.
- **Validation:** new tests written first and failing first (graph reproducibility and review, stale results refused, dispersion and spread priors, agreement across passing methods, peer-only flag not a candidate). `verify_underserved.py` passes. Full suite and lint: see the PR.
- **Known limitations:**
  - Four-way stability is not met; the spatial models did not converge (see `docs/LIMITATIONS.md` F4).
  - GitHub Actions could not run the models job (account billing block, October 2026); the committed results come from WSL Ubuntu with the same pinned PyMC 5.25.1.
  - No field-check outcomes are recorded yet (0 ground truth).
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/52

- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/58

## `docs/api-shapes` — API shapes draft for T10 (Part 7 item 1)

- **Owner / date:** P3, 2026-10-03.
- **Purpose:** Docs-only contract draft for P4: `docs/api_shapes.md` and one example JSON per endpoint (`docs/api_examples/`), from `docs/P3_BUILD_PLAN.md` Part 7 item 1 and T10 step 1. **Not a row in `docs/features.csv`**: no row was added or changed (Part 7 asks the owner to decide whether it gets one).
- **What we found:**
  - Routes on `main`: `GET /health`, `POST /intake/batch`, `/intake/sms`, `/intake/missed-call`, `POST /notices`, `GET /ledger/entries`, `/ledger/verify`. No auth, CORS or OpenAPI export yet. Intake, notices and contests answer a bad item with HTTP 200 and `status: "invalid"`; only malformed bodies use the shared error shape (`app/errors.py`, `code` from the HTTP status phrase).
  - P4 mismatches: the U3 field-worker app reads `duplicate` (resent `client_id`) as `merged`; the U2 resident app shows `spam` as "Could not send"; U4 uses lowercase outcomes (`confirmed`) where T3 returns `Confirmed`, and takes resident feedback on the driver's screen where T3 uses SMS replies `1` / `2`; U3 sends `area_id` as free text; U5 / U6 snapshots use camelCase and renamed fields (`waterAccessDeficitShare` vs E2 `wad`); the U6 forecast fixture is hand-typed but labelled SIMULATION, shows city intervals T2 does not produce, and marks the 21.9% / 35.1% protocol `NOT_DOCUMENTED`.
  - For P2 / P3: no plan store and no delivery store on `main`; an explanation's queue day must use the plan's `booked_trips` (capacity after the scheduled reserve), or it disagrees with the plan (checked on replay day 1, station ST19: 215 matches, raw 226 does not); A8's replay day holds bookings that arrive after the 05:00 plan time, so T7's `waiting_hours` can be negative; A8's `results.csv` / `summary.json` exist for a future Impact page.
  - `main` moved to `26b47d9` (U6) before this branch was cut; U6 adds 9 E501 errors and a format failure in P4's `scripts/frontend/build_u6_snapshot.py`.
- **What we changed:**
  - `docs/api_shapes.md`: conventions, status legend, what exists today, 17 sections (36 endpoints) with method and path, request, response fields and types, basis, errors, roles, and open questions for P4. Status: 7 route on main, 22 from main (service or file on main, route not built), 3 PROPOSED (T2 forecast and backtest, T9 confidence, from the local branches' actual output), 4 NOT DESIGNED (shortage: T8 not started; report card, SMS summary, impact: P4 / P2 to propose).
  - `docs/api_examples/*.json` (36): each produced by calling the real route, service or file (temporary databases; SYNTHETIC requests; P2's replay day 1 for the plan and booking examples, SIMULATION; real ward rows from `ward_evidence.csv`); each records its endpoint, status, basis and source in `_example`. No phone numbers (a placeholder is shown; the services never echo numbers) and no personal free text. Response-field tables in the doc are generated from these files. The generator scripts were kept out of the repo (docs-only scope).
  - `backend/tests/test_api_shapes.py` (3 tests). No backend code, routes or frontend files changed.
  - P4 answers applied (2026-10-03): duplicate = "already sent", merged = linked to existing complaint; spam = received and flagged; four delivery outcomes, pending until reply window closes; stable ward_id + section_id; snake_case; null/UNAVAILABLE; SYNTHETIC demo forecasts; roles officer/driver/resident/field_worker + gateway; offset/limit/total + after_seq/limit; structured codes; needs_check; per-item batch status; ISO 8601 with offset; ward report card; impact section. Councillor role OPEN.
- **Validation:**
  - 3 tests: examples valid/labelled JSON without phone numbers; merged routes return documented fields; file-based examples match source rows.
  - After merging `main` (`570d4b8`, T2 #58): `python tasks.py test`: ~613 backend passed, 2 failed; frontend 1 passed. Inherited failures same as T2/T9.
  - `python tasks.py lint` exit 0.
- **Known limitations:** Roles, auth, pagination and language handling are proposals for T10 to implement. Councillor role OPEN.
- **Handoff / next step:** T10 builds the routes from the agreed shapes. P4: no further questions open.
- **Update after P4's review (2026-10-03):** P4's answers applied in `docs/api_shapes.md` (section **Agreed with P4**): intake wording (`duplicate` = already sent, `merged` = linked to an existing complaint, `spam` = flagged for review); the four delivery outcome codes with `outcome_status` `pending` until the reply window closes; `ward_id` + `section_id` instead of free-text `area_id`; snake_case; missing numbers `null` + `UNAVAILABLE`; demo forecasts SYNTHETIC; roles `officer`, `driver`, `resident`, `field_worker` plus a gateway credential; `offset` / `limit` / `total` (ledger `after_seq` / `limit`); codes and structured values for the UI, SMS built on the server with English fallback; `needs_check` with signals; per-item batch status and 4xx for malformed requests; ISO 8601, UTC. Ward report card, SMS summary and impact designed from files on `main` (deliveries, debt, schedule and duplicate-merge share UNAVAILABLE). The example test's phone pattern no longer matches digits inside decimals. The under-served example now shows both reason kinds (found by T10's contract test). Still OPEN: councillor role; SMS wording in te / ur / hi.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/57

- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/58

## `feat/t9-confidence` — `T9`

- **Owner / date:** P3, 2026-10-03.
- **Purpose:** Confidence gate (F17): score each planner group's data quality, flag low confidence so it cannot auto-commit (officer check through A7), and choose the threshold on P2's A7 replay.
- **What we found:**
  - A7's `ConfidenceGate` Protocol is sufficient: `build_plan` keeps flagged groups, `approve_plan` raises `PlanBlocked` until `mark_checked` (`ward_reviewed`). No planner change and no new ledger event needed.
  - Census 2011 is the year for every ward (data age cannot separate wards); no dated evidence exists (evidence age unavailable); T2 is not on `main` (forecast width unavailable).
  - Calibration on the replay (153 days, 152 groups, 17,363 group-days; full information vs every group on the A3 fallback entitlement): the 0.90 target is met with nothing flagged (0.9522 at threshold 0.00), and the match share does not rise with the threshold (0.73-0.96). Fallback and Census groups match at the same rate (0.950 / 0.953). The thresholds cannot be separated, so none is chosen.
  - `main` moved from `73efb55` to `28b2661` (`319efd9`) and then `d12e4fd`; both merged without conflicts. T2 merged as #58 (570d4b8).
- **What we changed:**
  - `docs/features.csv` / `docs/P3_FEATURES.md` status row: T9 IN_PROGRESS (own commit).
  - `backend/app/config/confidence.py`: per-signal rules, combination, target 0.90, PROVISIONAL threshold 0.50, candidates, rounding, tolerance; each with a source or ASSUMED / OPEN.
  - `backend/app/services/confidence.py`: Census join quality, section location, data age (excluded), forecast interval width (interface, unavailable), evidence age (unavailable); minimum of the available signals; `T9Gate` (A7 `ConfidenceGate`); `calibrate`.
  - `scripts/trust/calibrate_confidence.py`; output `data/derived/confidence_calibration.csv` (SIMULATION, `_basis` columns; status `not_separable`, PROVISIONAL 0.50 kept).
  - Tests `backend/tests/services/test_confidence.py`; workflow `.github/workflows/p3-t9.yml`; `docs/worklogs/T9.md`; T9 section of `docs/P3_FEATURES.md`.
  - No P1, P2 or P4 file was edited; no API route; no new ledger event type.
- **Validation:**
  - 15 tests written first (`ModuleNotFoundError` before the code existed), including the done-when with A7's functions (flagged group, `PlanBlocked`, blank reason refused, `mark_checked` then approval, `plan_created` / `ward_reviewed` / `plan_approved` in the ledger, chain verifies), signal boundaries, missing signals listed, the weakest signal in the reason, the gate on the real files (counts read from the files), calibration on a hand-checkable fixture, and the committed calibration reproduced within 1e-4.
  - After merging `main` (`570d4b8`, T2 #58): `python tasks.py test`: 610 backend passed, 2 failed; frontend 1 passed; all P1 verifiers pass. The 2 are inherited, none in T9 files: P2 `backend/tests/test_a8_build.py::test_stations_are_reproducible_committed_and_labelled` and `::test_one_seed_reproduces` (Windows float last digits; pass on Linux CI).
  - `python tasks.py lint` exit 0. The `P3:T9` workflow regenerates the calibration on Linux and compares rounded values.
- **Known limitations:**
  - The done-when is met and tested, but the threshold is **not calibrated**: 0.50 is a placeholder (`not_separable`), accepted by Padmaja until P2 provides a per-group degraded scenario.
  - At 0.50 the gate flags 60 of 152 groups (39%).
  - Three of the five planned signals are unavailable: data age (Census 2011 for every ward), forecast interval width (waits for T2), evidence age (no dated data).
  - OPEN, owner to confirm: the threshold, target 0.90, minimum combination, Census rule and review cap, location scores and outlier cap, per-group data age, interval-width rule.
- **Handoff / next step:**
  - P2 (request, see `docs/worklogs/T9.md`): degraded-scenario replay for threshold calibration.
  - T10: expose the reason and the officer check.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/59

## `feat/t8-shortage` — `T8`

- **Owner / date:** P3, 2026-10-03.
- **Purpose:** F6 shortage early warning: risk list per section 1-3 months ahead, T2 forecast vs capacity, reasons from the numbers.
- **What we found:** A8 on `main` has a usable capacity assumption (1,150 tankers x 9 trips per tanker per day, 90 stand-in stations); all 198 T2 sections match A8's sections, 195 have a station. T2 forecasts only sections with a value a year earlier (182 / 184 / 185). D7 groundwater and reservoir data are not in the repo.
- **What we changed:** `ShortageConfig` in `config/forecast.py`; `services/shortage.py`; `scripts/forecast/run_shortage.py`; `data/derived/shortage_risk.csv` (551 rows, `_basis` on every derived column); tests `backend/tests/services/test_shortage.py`; workflow `.github/workflows/p3-t8.yml`; `docs/worklogs/T8.md`; T8 section of `docs/P3_FEATURES.md`; status rows. Cut from `feat/t2-forecast`.
- **Validation:** 8 tests written first, including the done-when (risk list 1-3 months ahead with reasons) on the real files, with the expected rows read from the forecast table (every section-month T2 forecasts in the three months: 551 today), and the committed list reproducing. Some edits to `services/shortage.py`, the test and `scripts/forecast/run_shortage.py` were made by another P3 session; they were reviewed and kept. `python tasks.py test`: 599 backend passed, 2 failed (P2 `test_a8_build.py::test_stations_are_reproducible_committed_and_labelled` and `::test_one_seed_reproduces`, Windows only, pass on Linux CI, identical on `main`); frontend passed; lint exit 0. The `P3:T8` workflow commands pass locally.
- **Known limitations:** OPEN, owner to confirm: risk ratios 1.0 / 0.85 and the 80% bound rule; A8's 2025 split and fleet used for 2026; one booking = one trip; forecast start (pre-re-cut names). No groundwater or reservoir signal ("groundwater data unavailable" in every reason).
- **Handoff / next step:** Retarget to `main` after T2 merges. P1: D7. Owner: Q2 and OPEN values. T10: `GET /shortage`.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/61

## `feat/t10-api` — `T10`

- **Owner / date:** P3, 2026-10-03.
- **Purpose:** API for all screens (thin routers, shapes agreed with P4 in `docs/api_shapes.md`), token auth by role, one error shape, paging, CORS, OpenAPI export.
- **What we found:** no plan store or delivery store on `main` (in-memory holders, empty until filled; routes 404); `python-multipart` not installed (voice upload not built); the under-served example lacked the plain-reason row (fixed on `docs/api-shapes`).
- **What we changed:** `app/auth.py`, `config/api.py`, new routers (evidence, forecast, plans, contests, deliveries, common, stores), auth / 422 / ward and section ids on the merged intake, notices and ledger routers, CORS in `main.py`, `scripts/api/export_openapi.py`, `docs/openapi.json`, `.env.example` (empty token variables), tests `backend/tests/api/`, P3's own router tests updated for auth (an invalid notice is now 422), workflow `.github/workflows/p3-t10.yml`, docs. Branch = `main` + local merges of #59 and #57.
- **Validation:** 32 API tests (every route conforms to its example; auth 401 / 403, dev token, gateway; approval without a reason 422; paging; CORS; OpenAPI current). `python tasks.py test`: 641 backend passed, 2 failed (P2 `test_a8_build.py::test_stations_are_reproducible_committed_and_labelled` and `::test_one_seed_reproduces`, Windows only, pass on Linux CI); frontend passed; lint exit 0.
- **Known limitations:** OPEN: councillor role; voice upload (`python-multipart`); plan and delivery stores; SMS wording te / ur / hi; OTP key management. In-memory holders reset on restart.
- **Handoff / next step:** merge #59 and #57 first. P2: plan store and daily job. P4: wire screens to the routes.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/62

## `feat/live-backend` — live wiring: persistent plans and deliveries, identity, and the screens on the API

- **Owner / date:** P2 work done by the repo owner, 2026-10-04 (items 1 to 10 of the finish list).
- **Why:** T10 made the API exist, but plans and deliveries lived in memory (no route created a plan or a stop), contests could not be listed, there was no identity beyond a role, and most screens still read snapshots. A running app could not do the demo's loop.
- **What we changed (backend):**
  - **Plans** (`services/plan_builder.py`, `models/plan_record.py`, `routers/stores.py`, `routers/plans.py`): `POST /plans` builds a plan for a replay day (2025-03-01 to 2025-07-31, SIMULATION) with **T9's gate**; `GET /plans` lists. A plan is stored as a rebuild recipe plus the officer's checks and approval (no pickling); a read rebuilds it, refuses it on a digest mismatch (409) and puts the checks back without writing ledger entries again.
  - **Stops and deliveries** (`services/delivery_store.py`, `routers/stops.py`, `models/delivery_stop.py`, `resident.py`, `delivery_roster.py`): the existing `delivery`, `representative`, `resident_response` and `delivery_outcome` tables are used; `POST /stops` (officer, validated, never echoes phone numbers), `GET /stops`, `GET /deliveries`. A delivery reloads exactly equal through a new store instance.
  - **Identity and roles** (`config/api.py`, `auth.py`, `routers/auth_routes.py`): `API_TOKENS` accepts `role:token[:user_id]`; `GET /auth/me`; a **councillor** role (may file contests and read explanations and ward cards, nothing officer-only); a resident or councillor reads only their own contests.
  - **Contests** (`routers/contests.py`, `services/contest.py`): `GET /contests` (filters, paging) and `GET /contests/{id}`; booking ids with spaces and brackets are accepted (every contest about a real booking was refused before), and an id containing a phone-like digit run is refused even when spaces or dots split it.
- **What we changed (frontend):** a shared client (`api.ts`, `useApi.ts`, `auth.tsx`), a top-bar sign-in and a "Live data / Saved snapshot" chip; the atlas, equity and field-check (U5), forecast and shortage (U6), impact (U9), plan (U7), explanation and contest (U8), driver (U4), field-worker (U3) and resident (U2) intake screens use the live API when signed in with the right role, with an adapter and tests each, and fall back to their labelled snapshot or sample otherwise. Resident and field-worker intake now send the bearer token (it was always rejected before). The field worker's free-text area is no longer sent (the intake rejects `area_id`).
- **How it was built:** three backend agents and six frontend agents in separate worktrees, each test-first, merged here with the integration checks below. Each screen was also driven against a real running API (fake tokens, temporary database).
- **Validation:** see the pull request for the full-suite counts. New tests: plan builder, plan store and routes, delivery store and stop routes (the full driver flow with no phone number, OTP, nonce or hash in any response or database column), identity (38), contests, and 126 frontend tests across 19 files.
- **Known limitations:** see `docs/LIMITATIONS.md` section 5 ("Not finished" and "Limits of the live wiring"). Main ones: plans come only from the committed replay, U10 report cards are still sample, sign-in is a pasted token, concurrent writes are last-writer-wins, screens were not looked at in a browser by a person.
- **Pull request:** see the PR for `feat/live-backend`.

## `fix/four-gaps` — supplied-booking plans, concurrency, weights and names, translation review

- **Owner / date:** P2 work done by the repo owner, 2026-10-04 to 2026-10-05.
- **Why:** four gaps left after the live wiring: plans only from the 2025 replay; two simultaneous actions could lose a change or crash a duplicate start with a 500; the live plan screen had no priority weights and showed ward ids; the Telugu, Urdu and Hindi text is unreviewed.
- **What we changed:**
  - **Plans from supplied bookings:** `POST /plans` takes the day's bookings (any day; validated, listed problems by booking number; canonical order, so the same bookings are the same plan; id is a hash of the bookings; kept in the recipe so the plan rebuilds exactly). The plan screen takes them as CSV (paste or file) and checks the shape before sending. There is still no automatic feed: HMWSSB publishes monthly totals only.
  - **Concurrency:** optimistic versions (`plan_record.version`, new `delivery_version` table) refuse a write from a stale read (409), and a per-plan / per-delivery lock makes change, ledger entry and save one step in one process; a duplicate start is a 409.
  - **Weights and names:** `NeedWeights` (water access, phone access, hardship; 0 to 5). A weighted plan is its own replay run with its own id and ledger entry; `GET /plans/{id}/compare` lists who gains and loses trips; plan views carry `weights`, `group_names` and `source`; the list carries the default weights and the maximum. The screen has the three sliders, the who-gains panel and names everywhere.
  - **Translations:** `docs/translation_review/` (807 strings with reviewer columns, a glossary with counts and five inconsistencies), `npm run i18n:export` / `i18n:check` (in `tasks.py test`), quality checks on every test run, and a "draft translation" notice in Telugu, Urdu and Hindi until each is set to reviewed.
- **Validation:** tests written first and seen failing for each part (store-level conflict rules plus real concurrent HTTP calls; weights and supplied bookings at service and API level; adapter, CSV parser and screen tests; translation checks with tests proving they catch dropped placeholders, copied English and the wrong script). The real API was run once to confirm the shapes the screen expects. Full suite: see the PR.
- **Known limitations:** see `docs/LIMITATIONS.md` (live booking feed, weights' small effect, multi-process ledger gap, translations still need a native speaker).
- **Pull request:** see the PR for `fix/four-gaps`.

## `feat/f20-report-cards` — ward report cards with real deliveries, water debt and schedule (item 11)

- **Owner / date:** P2 work done by the repo owner, 2026-10-05.
- **Why:** the F20 card showed need and bookings only; deliveries, water debt and schedule were "not available" because nothing joined a delivery to a ward, nothing settled debt, and the card did not read the plans. The U10 screen showed sample cards.
- **What we changed (design from the item 11 research in `docs/REMAINING_WORK.md`):**
  - **Stops get a ward:** named by the officer or placed on the 2016 ward polygons (DERIVED); `delivery_stop.ward_id`, `ward_basis`.
  - **Plans give water to stops:** a supplied plan uses the registered stops as the scheduled-supply points (A4 splits each scheduled ward's litres across its stops) and the saved debt accounts (A7 raises the ward's turns); both are in the recipe and the plan id.
  - **Closing a day (A6):** `POST /debt/days/{day}/close` settles every ward's debt from the approved supplied plan and the day's delivery outcomes at its stops, with A6's `settle_day` unchanged; new `water_debt_account` and `debt_day` tables, `GET /debt/accounts`, `GET /debt/days`, ledger entry `debt_day_closed`.
  - **Card and SMS:** deliveries, debt and schedule are live `{value, basis, reason}` blocks; the SMS gains the three phrases. The U10 screen calls the card and SMS for resident, councillor and officer tokens and keeps the sample cards as the labelled fallback.
- **Validation:** tests written first and seen failing for each part (ward placement, store, plan builder, day close, report card service, API loop and refusals, screen and adapter). Full suites: see the PR.
- **Known limitations:** see `docs/LIMITATIONS.md` F11 and F20 (scheduled-supply wards only, one load per Confirmed delivery, manual close, old ward map).
- **Pull request:** see the PR for `feat/f20-report-cards`.

## `feat/f5-gbm-forecast` — gradient-boosting forecast candidate with weather (items 12 and 16)

- **Owner / date:** P2 work done by the repo owner, 2026-10-05.
- **Why:** F5 promises a global gradient-boosting model with weather; only seasonal naive and naive x growth existed, and D8 weather was not in the repo.
- **What we changed:**
  - **D8 weather:** `scripts/data/fetch_d8_weather.py` fetches Open-Meteo daily maximum temperature and rainfall for the city centre, 2019-2026, into `data/raw/d8_weather/` with a retrieval log and checksum.
  - **Model:** `forecast.global_gbm`, a scikit-learn `HistGradientBoostingRegressor` (absolute-error loss) pooled over all sections, predicting log(value + 1) minus log(last year + 1) from the month, the values a year and two years earlier, recent section and city growth, last year's month weather against the 2019-2021 normal, and recent rain and heat. Every feature is at least as old as the forecast origin, so one model serves the whole 12-month horizon, and the leak check refuses later training data. Settings are in `config/forecast.py`, fixed before the backtest.
  - **Results** (`data/derived/forecast_backtest.csv`): portal run, MAPE 23.21% / WAPE 37.04% against seasonal naive's 26.28% / 47.67%; S2 run, 23.60% / 35.99% against 21.89% / 35.12%. The OPEN selection rule (both measures, both runs) keeps seasonal naive, so the forecast table and the shortage warning are unchanged.
  - `scikit-learn==1.9.1` added to the `models` extra.
- **Validation:** tests written first and seen failing (learns growth seasonal naive misses, deterministic, needs last year's month and enough history, serves 12 months, monthly weather from the daily file); the existing leak tests now cover the new model.
- **Known limitations:** see `docs/LIMITATIONS.md` F5 (owner rule decides adoption; groundwater missing; one weather point for the city).
- **Pull request:** see the PR for `feat/f5-gbm-forecast`.

## `feat/f13-dedup-calibration` — reproduce the F13 duplicate calibration (item 14, location and time)

- **Owner / date:** P2 work done by the repo owner, 2026-10-05.
- **Why:** the 106 m / 20 h / 9 days / 71% / 88% figures came from a Chicago extract that was never found, so they could not be checked.
- **What we changed:**
  - `scripts/data/fetch_d13_chicago.py` pulls the closest match (the four water-supply types, 2022-2023: 31,835 rows, 4,931 duplicates) into `data/raw/d13_chicago_311/` and registers it as D13-CHICAGO-311 in the source manifest.
  - `scripts/trust/calibrate_dedup.py` now reports three ways of counting a caught duplicate (linked to anything, into the right incident, to the exact parent), the share of non-duplicates merged, and the configured JalLekha rule with Chicago types mapped. The document's 71% / 88% are compared with "linked to anything", the only definition that reproduces them.
  - Results in `data/derived/dedup_calibration.csv`; the solution document's D13 row, F13 text and section 7 table now carry the re-pulled numbers.
  - The new manifest row changes the manifest checksum that E2 and E5 record, so `evidence_checks.json` and `underserved_checks.json` were rebuilt (only that checksum line changed), and `verify_manifest.py` now counts the 33 S2 resources apart from logged D13 pulls.
- **Validation:** tests written first and seen failing (fixtures where the three definitions differ; merged non-duplicates; the configured rule).
- **Known limitations:** another city's data; leak duplicates spread over about 16 days, longer than the 7-day window; text similarity on Indian examples still untested (`docs/LIMITATIONS.md` F13).
- **Pull request:** see the PR for `feat/f13-dedup-calibration`.

## `docs/demo-step5-2025` — demo step 5 names the 2025 replay (item 21)

- **Owner / date:** docs work done by the repo owner, 2026-10-05.
- **Why:** the solution document still presented the 2023 summer as the main replay (line 45 and demo step 5), while the sandbox and Impact page use Mar-Jul 2025 as the main run and keep 2023 for continuity (F19).
- **What we changed:** `docs/JALLEKHA_FINAL_SOLUTION.md` line 45 and section 10 step 5 now name the Mar-Jul 2025 replay as the main run, with 2023 kept for continuity. `docs/P4_DEMO.md` names no replay year and is unchanged. Status updated in `docs/REMAINING_WORK.md`, `docs/features.csv` (X1 note) and `CLAUDE.md`.
- **Validation:** no line of the solution document presents 2023 as the main replay (checked with a search for "2023"); docs only, no code changed.
- **Known limitations:** none.
- **Pull request:** see the PR for `docs/demo-step5-2025`.

## `docs/item-22-promise-column` — tracker says whether each doc promise is met (item 22)

- **Owner / date:** docs work done by the repo owner, 2026-10-06.
- **Why:** `docs/features.csv` marks a task DONE when its own done-when passed, which is often narrower than the solution document's promise (T2 DONE without an adopted GBM, T9 DONE with a provisional threshold), so readers took DONE to mean the promise is met.
- **What we changed:**
  - Two new columns at the end of `docs/features.csv`: `doc_promise_met` (yes / partly / no) and `gap` (what is missing, from `docs/LIMITATIONS.md`). Result: 21 yes, 24 partly, 2 no (Q1, Q2 on hold).
  - Stale notes fixed: A7 (API plans use T9's gate) and U4-U8 (live since PR #65, not "pending" or "unavailable"). T7 was already DONE, so the `LIMITATIONS.md` section 6 line about it is replaced by a note on the new columns.
  - `backend/tests/test_features_tracker.py` keeps the columns honest: allowed values, a gap note for every partly / no row, T2 and T9 not marked met, and no stale notes on the live screens.
- **Validation:** tests written first and seen failing (5 of 5), then passing; `scripts/ci/verify_p1_r_p1.py` still passes (47 rows, columns read by name).
- **Known limitations:** the yes / partly / no values are a judgement against the solution document as written; update a row's value whenever its gap closes.
- **Pull request:** see the PR for `docs/item-22-promise-column`.

## `feat/d9-facilities` — hospitals, clinics, UPHCs, schools and care homes per ward (item 15)

- **Owner / date:** P1 work done by the repo owner, 2026-10-06.
- **Why:** the ward table's critical facilities column was empty (`FACILITIES_UNAVAILABLE`) because the verified D9 snapshot was never copied, so F1, F8 tier 0 and F10 had no facility data.
- **What we changed:**
  - `scripts/data/fetch_d9_facilities.py` pulls OSM features (Overpass, bounding box of the 2016 ward layer) into `data/raw/d9_facilities/` with a retrieval log and SHA-256; registered as D9-OSM-FACILITIES in the source manifest (`verify_manifest.py` counts it apart from the 33 S2 rows, like D13).
  - `scripts/evidence/build_facilities.py` puts each feature in one category (UPHC by name, hospital, clinic, school, care home) and places it on the 2016 wards: `ward_facilities.csv` (counts), `facility_points.csv` (each feature with its ward), `facilities_summary.json` (totals beside the document's), checked by `verify_facilities.py` (added to `tasks.py test`).
  - E2 fills `critical_facilities` for all 145 wards (DERIVED; flag `FACILITIES_OSM_INCOMPLETE`). The manifest and E2 checksums changed, so the E5, E6, population and A8 checks were rebuilt (only checksum lines changed; E5's model results are unaffected because their cohort fingerprint has no facility input).
  - `GET /facilities/candidates?ward_id=` (officer): the ward's facilities as candidate critical stops, read-only (`docs/api_additions/facilities.md`).
  - U5 atlas: the selected ward shows the OSM facility count with the "not everything is mapped" note, in all four languages; snapshot rebuilt.
- **Results:** in the wards 941 hospitals, 294 clinics, 174 UPHCs, 439 schools, 6 care homes (document: 885 / 310 / 350 / 399 / 59). Close for hospitals, clinics and schools; UPHCs are found by name only; care homes are barely mapped in OSM.
- **Validation:** tests written first and seen failing (classification, placement and shared edges, reproducible artifacts, E2 column, API route and roles, adapter and screen), then passing.
- **Known limitations:** OSM is incomplete (zero mapped is not zero present); tag choices are ours; old 2016 ward map; no route creates outage critical stops from a candidate yet (`docs/LIMITATIONS.md` F1, F10).
- **Pull request:** see the PR for `feat/d9-facilities`.

## `feat/t9-degraded-replay` — T9 threshold chosen on a degraded-signal replay (item 18)

- **Owner / date:** P3 work done by the repo owner, 2026-10-06.
- **Why:** on the all-fallback replay every threshold looked the same (`not_separable`), so the gate ran on a PROVISIONAL 0.50 that flagged 60 of 152 groups.
- **What we changed:**
  - `services/confidence.py`: `degrade` (one seeded draw of errors: weakly placed sections moved to a neighbouring ward, true need off by a factor that widens as the Census join score falls), `error_groups` (which groups those errors damage) and `choose_across_seeds` (the lowest threshold meeting the target in every draw). Error rates and draw count in `config/confidence.py`, all ASSUMED.
  - `scripts/trust/calibrate_confidence.py` now runs the A7 replay once on our data and once per draw on the "true" data, and writes per draw and threshold: match share of unflagged group-days, groups flagged, damaged groups caught; plus the selection row. `--seeds` lets the test re-run draw 0 only.
  - Config threshold 0.05, basis DERIVED. U7 says how a DERIVED threshold was chosen (all four languages) and keeps the PROVISIONAL wording for a provisional one. `plan_confidence.get.json` updated.
- **Results:** 0.05 keeps at least 90.86% of unflagged decisions right in all 5 draws (88.97% with nothing flagged), flags 45 of 152 groups, catches about 41% of damaged groups; 0.70 would catch about 92% but flag 117 groups.
- **Validation:** tests written first and seen failing (moves only weak placements and only to neighbours, need error grows as join quality falls, damaged groups, every-draw rule, committed selection equals config, draw 0 reproduces; U7 note), then passing.
- **Known limitations:** assumed error rates and partly circular by design; thin margin because capacity rarely binds; the 90% rule is OPEN (`docs/LIMITATIONS.md` F17).
- **Pull request:** see the PR for `feat/t9-degraded-replay`.

## `chore/parallel-tests` — backend tests run in parallel

- **Owner / date:** repo owner, 2026-10-06.
- **Why:** GitHub Actions cannot run (billing), so every merge runs `tasks.py test` locally; the serial backend suite took 14-16 minutes.
- **What we changed:** `pytest-xdist==3.8.0` in the `dev` extra; `tasks.py test` runs `pytest -n auto backend/tests`. The tests themselves are unchanged.
- **Validation:** the same 945 backend tests pass in 6 min 36 s (was 13-16 min serially). The slowest single test (E5 PyMC prior, ~4.5 min) now bounds the run.
- **Known limitations:** none; install the new dev dependency with `python tasks.py setup` (or `pip install pytest-xdist==3.8.0`).
- **Pull request:** see the PR for `chore/parallel-tests`.

## `feat/f5-selection-rule` — forecast model chosen by a tested rule (research follow-up A)

- **Owner / date:** P3 work done by the repo owner, 2026-10-06 (rule applied at the owner's request).
- **Why:** the OPEN rule (beat seasonal naive on both measures in both runs) counted the same months twice and penalised the gradient-boosting model for the short S2 history, so the baseline stayed published although the model won the long backtest.
- **What we changed:**
  - `services/forecast.py`: `combo_naive_gbm` (equal average, a fourth model), `yoy_months`, `diebold_mariano` (one-sided, HLN correction, h = 1; scipy from the `models` extra) and `select` (portal run, shared origins with >= 12 year-on-year training months, better on both measures and DM p < 0.05, published forecast needs the same history, simplest model on a tie). The old `select_model` is removed.
  - `config/forecast.py`: the rule, `selection_alpha` 0.05, `selection_min_yoy_months` 12.
  - `scripts/forecast/run_backtest.py` writes a `selection_test` row per candidate (both measures, DM statistic, p, n) and the `selected` row with the reason. Forecast table and shortage list rebuilt; API examples regenerated.
- **Results:** gradient boosting selected (23.01% / 37.39% vs 30.98% / 50.97%, p = 0.0006, 24 origins). Shortage list: 86 high / 110 medium / 352 low / 3 unknown (was 46 / 130 / 372 / 3). On the real Feb-Aug 2026 city totals the two forecasts are nearly tied (31.1% vs 31.8% MAPE) and both miss the summer 2026 surge.
- **Validation:** tests written first and seen failing (DM statistic and p on a hand-checked fixture, year-on-year months with the Dec 2022 gap, combination, significance and history conditions, tie goes to the simpler model, scoring only origins with enough history), then passing.
- **Known limitations:** 24 scored months; DM can be over-confident in short samples; out-of-sample evidence so far is a tie (`docs/LIMITATIONS.md` F5).
- **Pull request:** see the PR for `feat/f5-selection-rule`.

## `feat/d8-city-weather` — weather per section from the Telangana weather stations (research follow-up B)

- **Owner / date:** P3 work done by the repo owner, 2026-10-06.
- **Why:** the forecast used one Open-Meteo point for the whole city, while heat and rain vary across Hyderabad.
- **What we changed:**
  - `scripts/data/fetch_d8_stations.py`: the 105 monthly TGDPS files (2018-01 to 2026-09) from Open Data Telangana's catalogue API, four HMWSSB districts kept, both file layouts normalised, the 2023-2026 day/month swap corrected (2,827 dates, flagged, original text kept), gzip with a fixed timestamp (2.1 MB); every source file's SHA-256 in the retrieval log. A download cache outside the repo survives network drops.
  - `scripts/data/fetch_d8_mandal_points.py`: Nominatim lookup of each mandal in its district (74 boundaries, 8 places, 4 rural mandals not found).
  - `scripts/forecast/build_section_weather.py`: stations averaged per mandal and day, months with >= 80% of days, nearest mandal per geocoded section, district then city fallback (labelled); spelling-variant alias table; checked by a reproducibility test.
  - `services/forecast.py`: `global_gbm_local_weather` (the same model with each section's own weather), between `global_gbm` and the combination in the rule's complexity order.
- **Results:** not significantly better than the city-weather model (22.37% / 37.66% vs 23.01% / 37.39% on 24 origins), so `global_gbm` stays published and the forecast table is unchanged.
- **Validation:** tests written first and seen failing (station and day averaging, day coverage and rain scaling, blank values, nearest mandal and fallbacks, aliases, per-section feature rows, city fallback, candidate order), then passing.
- **Known limitations:** mandal points by name lookup; alias table by hand from the files' year spans; 49 sections have no point (`docs/LIMITATIONS.md` F5).
- **Pull request:** see the PR for `feat/d8-city-weather`.

## `feat/d7-groundwater` — groundwater levels in the shortage reasons and as a forecast candidate (item 17)

- **Owner / date:** P3 work done by the repo owner, 2026-10-06.
- **Why:** F6 said "groundwater data unavailable" on every row because the NWDP route needed an account.
- **What we changed:**
  - `scripts/data/fetch_d7_groundwater.py`: the Ground Water Department's 67 monthly well-level files (Jan 2021 - Jul 2026) from Open Data Telangana's catalogue API, four HMWSSB districts kept, gzip, every source SHA-256 logged; the old NWDP plan kept as `NWDP_NOTE.md`.
  - `scripts/forecast/build_groundwater.py`: well identity (village + position rounded to 0.01 deg, swapped coordinates fixed, out-of-region positions dropped), anomaly against the same month in at least 2 earlier years, section anomaly = median of wells within 5 km (at least 2), every section-month with its value or reason; reproducibility test.
  - `services/shortage.py`: `load_groundwater` (latest month at or before the forecast origin), `GroundwaterSignal`, reasons with the anomaly or why there is none, `groundwater_m` column; the risk rule is unchanged.
  - `services/forecast.py`: `groundwater_anomaly` feature (blank for other models, which drop blank columns, so they are unchanged) and the `global_gbm_groundwater` candidate.
  - U6: DERIVED groundwater note and card when the API has it (all four languages); the saved-sample card says the sample has none. Shortage API example regenerated.
- **Results:** 389 of 551 shortage rows carry a groundwater anomaly. The groundwater forecast candidate is better on both measures (22.63% / 36.80% vs 23.01% / 37.39%) but not significantly (p = 0.074), so the forecast is unchanged.
- **Validation:** tests written first and seen failing (coordinate swaps and region, well identity, anomaly needs two earlier years and ignores N/A, nearby-well median and reasons, latest month at or before the origin, reason text and unchanged risk, feature from the month before the cutoff, candidate order, U6 note), then passing.
- **Known limitations:** short history (2021 start); messy well positions; the anomaly is shown, not used for the risk (`docs/LIMITATIONS.md` F5, F6).
- **Pull request:** see the PR for `feat/d7-groundwater`.

## `feat/item19-trips-protocol` — owner decisions 2 and 4 (item 19)

- **Owner / date:** repo owner, 2026-10-06.
- **Why:** the F5 capacity check refused to run without trips per tanker per day, and the docs still asked for the forecast protocol to be confirmed although it was confirmed on 2026-10-03.
- **What we changed:**
  - `config/forecast.py`: `trips_per_tanker_per_day = 9.0` with `trips_per_tanker_per_day_basis` (DERIVED: 11,000 trips / 1,233 tankers, May 2026 news = 8.9; other Hyderabad, Chennai and Bengaluru figures in the comment); same value as the sandbox.
  - `services/forecast.py`: the capacity basis no longer says OPEN; `scripts/forecast/run_backtest.py` writes `data/derived/forecast_capacity.csv` by default.
  - Docs: protocol recorded as confirmed (`LIMITATIONS.md` F5); item 19 statuses (6, 7 and item 13 dropped by the owner); Q1 searched again (no list); Q2 source found (Open Data Telangana daily reservoir storage, 2021-2026); stale item 12 status line fixed.
- **Results:** 1,123 tankers x 9 trips covers every forecast month (May 2026 peak: 73% of capacity); a peak-season rate, and the forecast under-forecast the real 2026 surge.
- **Validation:** test written first and seen failing (config value, basis, same as sandbox, capacity basis), then passing; the script test checks the capacity file.
- **Pull request:** see the PR for `feat/item19-trips-protocol`.

## `feat/u5-live-atlas` — live need map and officer overview

- **Owner / date:** repo owner, 2026-10-06.
- **Why:** the owner found the atlas too complex (basis labels, geography jargon, small map) and not live: booking equity came from fixed 2022-24 files and need never changed.
- **What we changed:**
  - `GET /atlas/live` (`services/live_need.py`, `config/live_need.py`): Census need plus five live clues per ward (water owed, bookings jump, "no water" complaints, supply cuts, groundwater), flagged at 2 bad clues; booking concentration from bookings supplied in the last 30 days (history if none). `PlanStore.supplied_bookings()` reads stored bookings without rebuilding plans.
  - U5 rebuilt (`EvidenceExperience.tsx` + `.css`): near full-page map with a latitude-corrected projection, layers (need rising now, no water at home, limited access, building growth), bookings tab with concentration and busiest areas on the map, low-bookings tab explained as booked vs similar wards vs model, ward sheet at the bottom with all ward facts and the live signs in plain words, ward search. No basis labels or geography jargon on screen.
  - Officer overview (`OfficerOverview.tsx`): live cards (need rising, low bookings, concentration, latest plan) that open their screen, and a three-step "what to do today" list; the non-working buttons are gone.
  - Snapshot (`build_u5_snapshot.py`) carries CAD and the field-check observed / expected bookings.
- **Validation:** service and API tests written first and seen failing, then passing; screen tests rewritten for the new layout; headless screenshot checked.
- **Known limitations:** `docs/LIMITATIONS.md` "Live need on the U5 map".
- **Pull request:** see the PR for `feat/u5-live-atlas`.

## `fix/u5-map-signs` — owner review of the need map

- **Owner / date:** repo owner, 2026-10-06.
- **Why:** owner review: a focus box appeared on click, the map was too small, CAD was mislabelled ("limited water access"; it is the Channel Access Deficit, homes with no phone), "need rising" was driven by groundwater alone and showed missing data as green ticks, and the booking check said 2022-24 for 2025 figures.
- **What we changed:** groundwater is background (`counts: false`), owed and bookings are unknown until data is entered (`known_count`), unknown wards grey; WAD / CAD labels corrected in all four languages; booking check says 2025, names the peer and model figures and says when a ward booked more than expected; map fills the screen, zoom (wheel, buttons) and drag, no focus box.
- **Validation:** tests written first for the sign rules and seen failing; screen tests updated; headless screenshot checked.

## `fix/u5-zoom-buttons` — zoom by buttons only

- **Owner / date:** repo owner, 2026-10-06.
- **Why:** the owner wants the map box to stay fixed: no mouse-wheel zoom or drag.
- **What we changed:** wheel and drag removed; + zooms towards the selected ward (else the centre of the view), - zooms out, the fit button resets. Test: wheel leaves the view unchanged, the buttons change and reset it.

## `fix/u5-zoom-buttons` — zoom by buttons only

- **Owner / date:** repo owner, 2026-10-06.
- **Why:** the map box must stay fixed: no mouse-wheel zoom or drag.
- **What we changed:** wheel and drag removed; + zooms towards the selected ward (else the centre), - zooms out, the fit button resets.
## `feat/e5-section-check` — F3/F4 section repair, 2026-10-06

- Preserves the owner's local U5/navigation/forecast work by branching from `277118f`,
  which includes latest local main (`e75ed63`), rather than discarding those commits.
- TDD: service import and officer route failed before implementation; U5 test failed on
  the missing section tab before implementation. Affected tests now pass.
- Exact 2025 section/division counts and billing denominators; complete-year gates,
  leave-target-out comparable peers, 2024-trained threshold, contextual ward need only.
- 197 identities, 12 candidates. 121 temporal validation pairs: peer rho 0.3718,
  median miss 2.4824x, within-2x 38.02%; baseline 0.1504 / 3.3103x / 28.10%.
- Officer route, OpenAPI, reproducible verifier and snapshot. U5 hides old ward model
  numbers, lists sections and marks their approximate points; en/te/ur/hi strings exported.
- No ground outcomes or precision claim; point-based ward outputs are legacy research.
  No spatial sampling, source-manifest edits or external publication.
- Contract checks exposed a pre-existing duplicate `_need` helper that broke explanation
  and report-card routes; renamed the live-atlas helper to preserve the typed ward lookup.
## `feat/booking-dasymetric` — F3/F4 transfer repair, 2026-10-06

- TDD: geometry/mass tests failed on missing service; equity conservation test failed against
  old point totals. Geometry, split conservation and E4/E6 affected tests now pass.
- Global Voronoi from all points, clipped to division hull + 1km and historical ward union;
  2023 Open Buildings fractional-count shares from existing 32m E3 cache, not vector footprints.
- 171 weighted sections, 145 wards; 91.82% of 2025 bookings placed. Unplaced counts preserved.
  Ward counts approximate; F3 per-population metrics remain null. Rebuilt E4/E6/U5 and examples.
- Reproduced original 107-ward diagnostic; magnitude errors improve but rho falls for NB,
  peers and baseline. Full figures and caveats in F4. No claim of geographic improvement.
- Legacy E5 fits frozen on original observations. No spatial resampling or source-manifest edits.
  New section checks retain exact counts; approximate counts are research/context only.
- Actual vector building footprints and official section GIS are still absent. RTI is owner action.
## `feat/e5-underreporting` — F4 model experiment, 2026-10-06

- Read F4-F6/P3/worklog before parallel primary-source research; no repetition of BYM2 repairs.
- New non-spatial PyMC marginalized NB/Binomial model, seeded 2024-only data; 107 section pairs.
  Need exposure from historical Census/2023 buildings; 2024-only station stand-ins avoid leakage.
- Initial NUTS was interrupted without final metrics. Bounded MAP with three seeded starts and
  three assumed reporting priors completed; all optimizers succeeded, predictions agree within 0.8%.
  Posterior diagnostics and latent demand/probability unavailable; no posterior claims.
- Reject all new fits: median misses 3.79/3.93/4.53x vs city baseline 3.61x and own-section
  persistence 1.36x (rho 0.955, within2x 91.59%). Complete table in LIMITATIONS F4.
- Test-first gate for MAP optimizer success/stability failed before implementation and now passes.
  Saved-result verifier checks inputs, predictions, metrics and rejection without fitting.
- No operational scoring/allocation change, no Windows spatial sampling, no external publication.
  Work isolated after another session stashed this code and switched the shared checkout.
## `feat/e5-ground-truth` — F4 observation loop, 2026-10-06

- TDD: missing store/API/form tests failed first, then pass for persistence, replay/conflicts,
  actor authorization, note digests, pending-ledger retry and a 30-distinct-decisive sample gate.
- Append-only SQLAlchemy observations, new ledger event, digest-only notes, current flag digest,
  officer/field-worker API and shared U3/U5 form with four languages. Actual outcomes remain zero.
- Latest linked visit per section/year counts; repeated and unclear visits do not inflate precision.
  12 current flags cannot reach 30 distinct decisive outcomes; future independent cohorts needed.
- Live U5 cards reflect recorded outcomes; overview reports 12 section flags instead of six wards.
  Ward need scores unchanged. Browser preview uses an isolated temporary database, never main DB.
- Worktree `.claude/worktrees/e5-repairs`; original checkout restored to the other session's
  supply-timings work after preserving these files. No push, PR, merge or external messages.
- Selected section dots now show the section name, exact bookings, connection rate, peer rate
  and visit status beside the map. Browser verified using a temporary database; its synthetic
  unclear visit is not a ground observation and is not included in committed artifacts.
- Final validation: full lint, 1,001 backend tests, 196 frontend tests, translation checks,
  all data verifiers and production build pass. The first full run exposed stale sandbox
  provenance after the E4 rebuild; refreshed only the E4 summary checksum because its consumed
  Gini values are unchanged, then reran the full suite successfully.


## feat/f5-forecast-refresh ? 2026-10-06 (local, owner approval pending)

Refreshed exact city bookings through Aug2026 and Sep2026-Aug2027 horizon; tested fixed level,
recency Ridge, summer and lagged groundwater/reservoir candidates alongside existing models.
No candidate passes both metrics plus HLN DM: retain seasonal naive, disclose undercoverage.
Added direct city ranges, paged history/accuracy API, conservative one-to-one section matches
(63 approximate/210 unmatched), unknown warnings instead of invented counts/capacities, and
logged Q2 reservoir context. Corrected transient NEW aliases after browser review exposed a
missing May; unavailable section-month identities stay absent. Replaced illustrative U6 output
with actual published snapshots and separate observed/future/accuracy/section views in en/te/ur/hi.

TDD: new refresh tests failed on missing module; passed after implementation. Alias regression
failed on NEW suffix then passed. Frontend tests failed before redraw and passed after. Full lint
passed; full backend run 995 passed/2 failed in373s: outdated forecast example and inherited
sandbox input hash. Both fixed and 45 affected checks pass; all194 frontend tests, i18n and every data verifier pass.
No push, PR or merge. Evidence and reproducible commands in LIMITATIONS F5/F6 and API addition.

## `feat/d16-supply-timings` — Prompt A / D16 Water Supply Timings (2026-10-06)

- **Owner / date:** Codex / 2026-10-06.
- **Purpose:** Walk HMWSSB public Water Supply Timings system and web archives, fetch all available timing records, verify coverage against 2025 tanker bookings and wards, inspect outage/pressure dashboards, draft RTI application, and document honest limitations.
- **What we found:**
  - HMWSSB's live "Water Supply Timings" portal (`https://bms.hyderabadwater.gov.in/wstl/managerupload/DivisionMap.aspx`) links 11 division pages requiring browser User-Agent and `Referer: .../DivisionMap.aspx`. It defines 89 sections (93 JS function entries).
  - Every single live section query currently returns `<script language="javaScript">alert('No Data Found');</script>`: the live database is completely empty.
  - Wayback Machine CDX search revealed exactly one historical capture containing tabular data: S.R. NAGAR (Division 6, Section 0624) from 2024-05-14 21:57:12 UTC, containing 21 localities. Older `hyderabadwater.gov.in` and `.asp` variants have 0 timing tables. Archive.today has 0 captures.
  - Coverage: 1 of 89 sections (1.12%), 21 localities, representing 40,862 of 1,436,768 (2.84%) 2025 tanker bookings, mapped to Ward 98 Ameerpet (`relation/7857794`).
  - Outage Dashboard (`https://erp.hyderabadwater.gov.in/HmwssbOnlineNew/#/OutageDashboard`) requires internal ERP credentials (no public table/JSON feed). Water Pressure Dashboard (`https://mdm.hyderabadwater.gov.in/real-time-water-pressure`) server (65.2.47.226) is unresponsive (timed out).
- **What we changed:**
  - `scripts/data/fetch_supply_timings.py`: walks live system, queries CDX API, parses tables, calculates 24h start/end times and hours, and computes coverage against 2025 portal bookings.
  - `data/raw/d16_supply_timings/supply_timings.csv`: 21 localities for S.R. Nagar with columns `division_code,section,section_code,locality_code,locality,slum_status,from_time,to_time,hours,pattern,water_source,captured_at,capture_source,source_url`.
  - `data/raw/d16_supply_timings/RETRIEVAL_LOG.md`: provenance log with URLs, dates, counts, and SHA-256 hashes of all saved files.
  - `data/raw/d16_supply_timings/raw_pages/`: archived raw HTML and gzip pages.
  - `scripts/data/verify_supply_timings.py` & `data/verification/verify_supply_timings.py`: standalone verifier writing `data/verification/supply_timings_checks.json`.
  - `docs/handoff/RTI_SUPPLY_HOURS.md`: formal RTI draft requesting scheduled timings, SCADA daily hours/flow 2024–2026, and GIS boundary maps.
  - `docs/LIMITATIONS.md`: corrected section "Live need on the U5 map" with verified portal facts and 2.84% coverage.
  - `docs/REMAINING_WORK.md` & `docs/features.csv`: updated status and tracker.
- **Validation:**
  - TDD: `backend/tests/test_d16_supply_timings.py` written first and failed on missing script; now 7 tests pass (time conversion, duration math, empty page detection, S.R. Nagar HTML parser, coverage maths, verifier execution).
  - Verifier `scripts/data/verify_supply_timings.py` exits 0 with `PASS`.
- **Known limitations:**
  - 88 of 89 sections (98.88%) have no public timing data; live database is empty.
  - S.R. Nagar timings are from May 2024 (archived), not live telemetry.
  - Outage and pressure dashboards are not publicly available without credentials or server repairs.
- **Handoff / next step:**
  - Committed locally on `feat/d16-supply-timings`. Do not push or merge until owner says "approve".
- **Pull request:** pending owner approval.

## `feat/item20-osrm` — OSRM road routing with cached legs (item 20)

- **Owner / date:** repo owner, 2026-10-06.
- **Why:** item 20: the owner chose to build OSRM routing; SQLite, SVG maps, own intervals and bottom-up reconciliation stay (design doc stack line edited).
- **What we changed:** `scripts/routing/build_osrm_legs.py` (Geofabrik extract, pyosmium crop, OSRM v26.10.0 Windows binaries, car profile, /table both directions); committed legs and build log in `data/derived/routing/`; `scripts/sandbox/build_stations.py` uses road km (home station = nearest by road); sandbox, planner replay, T9 calibration, shortage and U9 snapshot rebuilt; T9 threshold kept at 0.05 as a delegated owner decision (`rule_threshold` 0.70 recorded and tested).
- **Results:** road/straight ratio 1.32 median; km per kl +12% for all policies; JL_POOL's served-share gain over B1 falls from 1.2 to 0.3 points.
- **Validation:** road-km test written first and seen failing; OSRM table parsing tests; affected tests pass.

## `feat/remove-sign-in` — no sign-in

- **Owner / date:** repo owner, 2026-10-06.
- **Why:** owner decision: nobody should have to sign in or paste a token to use the screens.
- **What we changed:** `config/api.py` (`auth_required`, from `AUTH_REQUIRED`; a config built directly still requires tokens), `auth.py` (open server: every caller is the `dev` principal), `routers/auth_routes.py` (`open` flag), `.env.example`; frontend `auth.tsx` asks `/auth/me` once, and on an open server is signed in and acts as the role of the workspace on show (`App.tsx`); `SignIn.tsx` renders nothing then; `docs/openapi.json`, `docs/api_additions/auth_contests.md`, `docs/LIMITATIONS.md`.
- **Known limitations:** with `AUTH_REQUIRED` unset anyone who can reach the API can use every officer route (approve plans, close days). Roles are a screen choice. Screen ids in open mode are fixed (`officer-01`, `driver-01`, `resident-01`, `field-worker-01`). Set `AUTH_REQUIRED=true` to restore tokens.
- **Validation:** backend `tests/api` (170) and the affected router tests pass; frontend lint, type check and all 200 tests pass; full `tasks.py test` (PyMC, data verifiers) not run in this session.

## `feat/section-placement-integrate` — reviewed section placements into the section map

- **Owner / date:** repo owner, 2026-10-06.
- **Why:** 45 of the 197 sections had no location, so no area or need on the section map. The reviewed placements (`section_placement_reviewed.csv`, branch `feat/place-missing-sections`) place 27 of them.
- **What we changed:** `scripts/evidence/build_booking_transfer.py` takes `--with-reviewed` and writes `section_ward_building_weights_reviewed.csv` and `..._summary_reviewed.json` beside the first build (the ward-level files stay on the first build); `scripts/evidence/build_section_map.py` uses the reviewed build when present and adds a `location_basis` column to `section_need.csv`; section snapshot and geometry rebuilt.
- **Results:** sections with area and need 150 -> 170; share of 2025 bookings in them 91.8% -> 97.0%. 21 of the 27 placed sections get weights. Six get none because their cell lies wholly outside the 2016 ward layer (Bachupally, Shamshabad, Thukkuguda, Nagaram, Pedda Amberpet, Pocharam): no ward to take need from, so they stay without area or need (no fallback). Bachupally alone is 16,766 bookings.
- **Known limitations:** adding points changes neighbours' cells (median weight shift 0, 90th percentile 0.10, largest 0.54), so need of nearby sections moved a little. The ward-level equity files were not rebuilt. `verify_booking_transfer.py` compares bytes and differs in the 16th digit of `geometry_coverage_fraction` on a newer shapely than the pinned one; the weights themselves are identical.
- **Validation:** baseline build reproduces the committed weights exactly (max difference 0.0); affected backend and all 200 frontend tests pass; lint and type check clean.

## `feat/section-queue` — daily plan by section (feat/section-queue, stacked on `feat/section-placement-integrate`)

- **Owner / date:** repo owner, 2026-10-06. Owner answers: stations = the 90 ASSUMED stand-ins; daily bookings = monthly totals divided by days; fleet 1,150 x 9; unit = section; sections without need get a labelled estimate; map by section and by ward.
- **What we changed:** `backend/app/services/section_plan.py` (section table with need, connections, station; daily bookings from a month's real totals by running remainder; station capacity from the fleet or the tight scenario, shared by the year's bookings; `SectionGate`; ward totals by building share), `plan_builder.py` (`section_month` plans, rebuilt from a recipe), `routers/plans.py` (`unit`, `capacity`, section confidence, `group_totals`, `ward_totals`), frontend `SectionPlanForm.tsx`, `PlanMap.tsx` (coverage map, Sections | Wards), `PlanExperience.tsx`, `planAdapter.ts`; `docs/api_additions/plans.md`, `docs/api_examples/plan.get.json`.
- **Results:** on 2025-05-15 (6,712 bookings): whole fleet (10,350 trips) serves all; tight (6,480 trips) serves 6,373 and leaves 339 waiting, mostly in a few sections of the west (Manikonda, Gachibowli). 27 of 197 sections have an estimated need (division or city median) and 5 an estimated connection count; they are flagged and need an officer's check. 8 sections get the nearest station, 3 the division's usual station.
- **Known limitations:** only days of 2025 (the section names of our tables); every booking is tier 2 and domestic (not published), so tiers 0 and 1, booking caps, scheduled supply, outages and carry-over between days are not in a plan by section; daily split is an even spread of the month, not a forecast; water debt is read from `section:` accounts, but closing a day does not yet write section accounts; no routes yet (next branch); ward figures are an estimate (building share); English only; no new frontend tests.
- **Validation:** backend `tests/api` pass, including 5 new tests; frontend lint, type check and 200 tests pass; checked in a browser against a local API.

## `feat/section-plan-completion` — priority classes, carry-over, section debt, scheduled supply and outages for plans by section

- **Owner / date:** repo owner, 2026-10-06 (limits 2 to 5 of the section plan; limits 1 and 6 left).
- **What we changed:** `backend/app/config/section_plan.py` (every setting with its basis); `section_plan.py` (estimated tiers 0/1 and commercial label, multi-day replay with carry-over and a step cache, F9 candidates and estimated stops, outages from notices, `section_of_point`, `fresh_bookings`); `plan_builder.py` (options in the recipe, plan id hash); `routers/plans.py` (options, outages from supply notices); `day_close.py` (`close_section_day`), `routers/debt.py` (section plans, account view); `scripts/evidence/build_section_map.py` (section facilities and section areas as data); frontend `SectionPlanForm.tsx`.
- **Research:** HMWSSB publishes no booking types. Real figures used: commercial trips were 190,145 of 589,189 (2022 RTI, News Minute), so bookings are labelled domestic or commercial in that proportion by commercial connections; hospitals first when supply fails is common water-agency practice.
- **Results (2025-05-15, tight):** 8,979 bookings with 2,267 carried over, 665 tier 0, 835 tier 1; 12 sections on scheduled supply; a supply notice for Gachibowli gave an outage response by section with critical facilities first; closing the day wrote section accounts that the next day's plan used (a section in debt gets about 14% more turns).
- **Known limitations:** tier 0 and tier 1 are estimates, not data; booking caps are not applied (they never bind at section level); scheduled stops are estimated centres and, like outage and critical stops, are not routed (no fleet given; the route planner is next); a section's water debt is bookings minus Confirmed deliveries, so with no delivery recorded every section accrues debt to its cap; days still only in 2025; the day split is still an even spread; ward and section debt use the same closed-day chain, so use one unit at a time; English only.
- **Validation:** backend `tests/api` (including 9 section tests) and the notice and ledger router tests pass; frontend lint, type check and 200 tests pass; checked in a browser.

## `feat/route-planner` — tanker routes of a plan by section

- **Owner / date:** repo owner, 2026-10-06. Stations stay the 90 ASSUMED stand-ins; fleet 1,150 (news); map by section and by ward.
- **What we changed:** `backend/app/services/route_schedule.py` (named tankers per station, loads to the tanker free first, special loads to the nearest station with a spare special trip, OSRM legs where cached plus the drive inside the section, a 06:00-22:00 day), `GET /plans/{id}/routes` in `routers/plans.py`, settings in `config/section_plan.py`; frontend `PlanRoutes.tsx` (stations table, tankers, trip table, station-to-section map), `mapGeo.ts`.
- **Results (2025-05-15):** tight scenario: 719 tankers (of 1,150) make 6,256 trips, 8.7 trips per tanker (HMWSSB's own figure is 8.9), about 2.8 km a round trip, last tanker back 19:10, nothing left over; whole fleet: 1,147 tankers, 6.0 trips each, back by 17:16. A scheduled-supply load for a flagged section is driven by a tanker of the nearest station that had a spare special trip.
- **Known limitations:** a trip serves one load (HMWSSB's booking unit), so there is no multi-stop chaining and no solver; a tanker is not sent past another place on the way; station positions are stand-ins placed on section centres, so most trips are short and the distances are between assumed places; OSRM is free-flow (no traffic, no truck limits) and was not built for sections placed after review or for facilities (straight line x 1.35, labelled ESTIMATE; 204 of 6,256 trips); lines on the map are straight, not road shapes; every tanker starts at 06:00 and filling points are not limited; no live GPS; English only; no new frontend tests.
- **Validation:** backend `tests/api` (including 2 route tests) pass; frontend lint, type check and 200 tests pass; checked in a browser.

