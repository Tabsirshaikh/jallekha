# JalLekha 2.0: known limitations

Status on `main` as of 2026-10-04 (after PRs #52, #57, #59, #60, #61 and #62). One section per feature of
`docs/JALLEKHA_FINAL_SOLUTION.md`, then limits that cut across features, then what is not built yet.
Sources: `docs/BRANCH_WORKLOG.md` ("Known limitations" of each branch), the solution document's
Section 8, and the 2026-10-03 verification of the repo against the document.

Legend: **[OPEN]** needs an owner or outside decision. **[ASSUMED]** a policy setting, changeable in config.
**[NOT BUILT]** feature or part missing.

---

## 1. Cross-cutting limits (affect many features)

1. **Census is from 2011.** Ward need (WAD, CAD, hardship) cannot be refreshed. Only household counts are updated, with a modelled 2025 estimate.
2. **Old and approximate geography.** The demo uses the historical 150-ward 2016 layer (145 polygons; wards 3, 4, 11, 13, 31, 113 missing). The 2025-26 reorganisation into 300 wards and three corporations has no machine-readable boundaries or crosswalk, so any "current ward" claim stays blocked.
3. **Census-to-ward placement is approximate.** Census 2011 uses 2009 wards. The 2009 map was fitted from a PDF (median boundary error about 155 m) and split over 2016 wards by building share. No exact-geometry join exists (0 exact joins, 143 approximate).
4. **Bookings are published per section, not per ward.** Sections are placed on wards by one geocoded point each: about 88% of bookings are placed, 60 of 221 sections are not. A ward with an unplaced section can look under-served.
5. **Section re-cut in Feb/Mar 2026.** 2026 section names do not match earlier years, so 2026 cannot be compared section by section.
6. **Daily data is synthetic.** HMWSSB publishes monthly totals only. Daily arrivals, times of day, complaints, outages and delivery confirmations in the demo are SYNTHETIC (monthly totals stay exact).
7. **Filling stations are stand-ins.** The count (90) is REAL, the positions are ASSUMED (booking-weighted k-means). HMWSSB publishes no station list with coordinates.
8. **Fleet, trips and capacity are from news reports**, not official data [ASSUMED].
9. **Most officer and field screens now use the live API, with a labelled fallback.** T10 is merged (bearer-token roles officer, driver, resident, field worker and councillor; tokens, optionally bound to a user id, come from the environment only). The atlas, equity and field-check (U5), forecast and shortage (U6), impact (U9), plan (U7), explanation and contest (U8), driver (U4), field-worker (U3) and resident (U2) intake screens call it when someone is signed in with the right role and the API answers; otherwise they show the committed snapshot or sample data with a "Saved snapshot" chip and the reason. The ward report card and SMS summary (U10) are live for resident, councillor and officer tokens, with the sample cards as the fallback. Nobody signs in with a password: a token is pasted in the top bar. Screens were tested with mocked and real API calls, but have not been looked at in a browser by a person.
10. **Translations are drafts.** Telugu, Urdu and Hindi were written without a native-speaker review; the app says so in each of them until a reviewer signs it off. `docs/translation_review/` has every string (807) beside its English, columns for the reviewer and a glossary with five inconsistent terms to settle. Automated checks (every test run) find no missing language, broken placeholder, wrong script or English left in place, but cannot judge wording. Alert and explanation wording is [OPEN].
11. **No migrations.** New database columns need a fresh database or a manual column add.
12. **Third-party warnings.** OR-Tools prints SWIG deprecation warnings on import (upstream).

---

## 2. Layer A: Evidence

### F1 Water Access Atlas (E1, E2)
- Based on Census 2011 moved onto 2016 wards approximately (limits 1 to 3 above).
- **Critical facilities come from a fresh OpenStreetMap pull (D9, item 15)**, not the lost verified snapshot: 941 hospitals, 294 clinics, 174 UPHCs, 439 schools and 6 care homes placed in the 145 wards (the document says 885 / 310 / 350 / 399 / 59; `data/derived/evidence/facilities_summary.json`). Counts are REAL as mapped, placement DERIVED. OSM is incomplete and uneven (`FACILITIES_OSM_INCOMPLETE`): zero mapped is not zero present, 3 wards have none mapped, and care homes are barely mapped. UPHCs are found by name (UPHC, PHC, Basti Dawakhana), so others count as clinics or hospitals, which is why UPHCs are half the document's figure. Many OSM "hospitals" are small nursing homes. The tag choices are ours; the original query was never found.
- 2 wards have partial Census coverage; Census for 2009 wards 115 and 116 (in Medak district) is not loaded.
- Share of households away from water is a Census snapshot, not today's observation.
- The Atlas screen (U5) calls the API (`/atlas/wards`, `/equity/*`, `/underserved/field-checks`, `/coverage/layers/...`) when an officer is signed in and all five answers are complete, and otherwise shows the committed snapshot (`frontend/src/data/u5Evidence.json`, rebuilt by `scripts/frontend/build_u5_snapshot.py`). Building change per ward comes from the field-check rows, so it is available only where the screen has them.

### F2 Growth signal and 2025 population (E3, POP)
- Buildings are not households or people. Office and mall growth inflates building trends (buildings +3.2%/yr, GHS-POP +1.2%/yr, HMWSSB connections +2.18%/yr).
- Open Buildings is modelled: confidence is uncalibrated, with cloud, tile seams and missed small buildings. City-wide year-to-year jumps are removed before the trend is fitted, and it is measured at 32 m.
- The 2025 population is **modelled, not counted**. The city rate is assumed to hold since 2011. Household size is held at its 2011 value. One HMWSSB connection can serve many flats.
- The connection check compares 2022-2025 connections with the 2016-2023 building trend, with approximate section placement.
- WorldPop was not extracted (1.84 GB file, host refuses range reads). GHS-POP is used for the level and the range only.

### F3 Booking Equity and coverage map (E4, E6)
- Ward booking numbers are approximate (one point per section; about 12% of bookings unplaced).
- Bookings per 1,000 connections: one connection can serve many flats.
- The Gini of 0.78 is exact at section level but depends on section definitions that were re-cut in 2026.
- There is no "people within 500 m of a public tap" layer: public tap locations are not available.
- The map screens (U5) follow the same live-or-snapshot rule.

### F4 Under-served Field-Check Screen (E5)
- 107 wards screened, **6 candidates**, 38 wards left in data review (37 have no placed section).
- **Only two of the four methods count.** The peer median and the negative-binomial model (NB) both run and pass every check, so a candidate must be flagged by both (`AGREED_FIELD_CHECK_CANDIDATE`; they agree on 6 of 7 flagged wards, Jaccard 0.86). Mailardevpally, flagged by the peer screen alone, is `MODEL_SENSITIVE_REVIEW`.
  - **The two spatial models (BYM2, BYM2-shrinkage) did not converge**, so E5's done-when ("flags stable across model variants") is met only for peer + NB, and the output says `stability_evaluated: false`.
  - Five rounds of fixes, each recorded in the commit history and `model_results.json`: sampler settings; Poisson likelihood; restricted spatial regression; PC prior on rho; islands without a structured effect; ICAR structure only; inverse-sqrt prior on the NB dispersion; PC prior on the spatial spread. The final setting passes 8 of 10 spatial folds. Fold 1 fails for every seed: without its 22 wards, ward-level variation (NB alpha) and spatial variation (sigma) cannot be told apart.
  - The strict gate (R-hat at most 1.01, bulk ESS at least 100, no divergences in every fold) was kept, not relaxed.
  - NB's expected bookings are far above the peer figure for the old-city candidates (Barkas: about 21,600 vs 1,193 from peers) because heavily booking western wards also have high WAD, so the model extrapolates; the flag holds either way (upper interval far below 1), but use the peer figure when quoting an expected count.
- Models are fitted on Linux (WSL or CI) and committed; CI never re-samples. The GitHub Actions models job could not run in October 2026 because of an account billing block.
- Low bookings cannot prove hidden demand. A candidate only means "send someone to check". No field check outcomes recorded (0 ground truth).
- Thresholds are policy parameters.
- The U5 field-check cards show these candidates, live or from the snapshot, with each method's ratio listed separately.

### F5 Surge Forecast and Capacity Planner (T2)
- **Built (T2, PR #58): baseline, backtest, reconciliation, intervals and capacity check.** The seasonal-naive baseline is reproduced (21.89% city MAPE, 35.12% section WAPE on the 2022-24 files). The protocol was recovered by reproduction, not from the lost review file, so the owner should confirm it before the numbers go on slides.
- On the longer portal history (to Jan 2026) seasonal naive scores 26.28% / 47.67% and the 80% interval covers only 0.77. Naive x growth does not beat the baseline on both measures, so no candidate is selected: **nothing beats the baseline**.
- **Gradient-boosting candidate built (item 12):** one scikit-learn model pooled over all sections, learning a correction to seasonal naive from the month, the values a year and two years earlier, recent section and city growth, and weather (D8, Open-Meteo reanalysis: last year's month against the 2019-2021 normal, recent rain and heat). Settings were fixed before the backtest and never tuned on it. Result on the same rolling backtest: on the portal history (33 common months) it beats seasonal naive on both measures (city MAPE 23.21% vs 26.28%, section WAPE 37.04% vs 47.67%); on the short S2 files (2-12 training months) it is slightly worse (23.60% / 35.99% vs 21.89% / 35.12%), worse in its first months and better once it has a year of history. Groundwater (D7) is still missing.
- **The published forecast is now the gradient-boosting model (research follow-up A, applied at the owner's request on 2026-10-06).** The rule is judged on the portal run only, on the 24 origins every model shares with at least 12 year-on-year training months: a candidate must beat seasonal naive on both measures and pass a one-sided Diebold-Mariano test with the Harvey-Leybourne-Newbold correction at 5% on the monthly section absolute errors; on a tie the simpler model wins. Gradient boosting: city MAPE 23.01% vs 30.98%, section WAPE 37.39% vs 50.97%, p = 0.0006. The equal average of the two (`combo_naive_gbm`) also passes (25.55% / 41.16%, p = 0.0001) but is not significantly better than gradient boosting, so the simpler model is used. Naive x growth does not pass (p = 0.40). The S2 run now only checks that the documented 21.9% / 35.1% baseline reproduces (it does: 21.89% / 35.12%).
- **Out of sample it is no better yet.** Scored on the real Feb-Aug 2026 city totals, which neither forecast saw, gradient boosting and seasonal naive are nearly tied (city MAPE 31.1% vs 31.8%; better in Feb, Mar and May, worse in Apr, Jun, Jul and Aug). Both badly under-forecast the summer 2026 surge (Aug 2026: 164,367 bookings against about 54,000-57,000 forecast). Seven months is too few to judge, and the Feb/Mar 2026 section re-cut stops a section-level check.
- **Weather per section does not help (research follow-up B).** A second gradient-boosting candidate gives each section the weather of its nearest mandal from the Telangana automatic weather stations (TGDPS, D8b: 2018-2026, 86 mandals located, 172 of 221 sections placed, median 1.95 km to the mandal centre; the 49 sections without a point keep the city series). On the 24 scored months it is not significantly better than the city-weather model (city MAPE 22.37% vs 23.01%, section WAPE 37.66% vs 37.39%), so the rule keeps the simpler city-weather model and the published forecast is unchanged. Mandal weather is placed by name lookup (Nominatim), the station files spell 12 mandals two ways (joined by an alias table) and number two mandals only as `27` / `28` (dropped); 4 rural Sangareddy mandals could not be located.
- [OPEN] trips per tanker per day (the capacity planner refuses to run without it) and Chronos-2.
- Short series (13 scored months per section, too few for 95% intervals); section names are not mapped across years, and the Feb/Mar 2026 re-cut breaks section-by-section comparison.
- `GET /forecast` and `/forecast/backtest` serve the table, and the U6 screen shows them live (city forecast DERIVED with no city interval, section forecast with intervals, backtest accuracy per model) with the committed real history and SIMULATION fixtures as the fallback.

### F6 Shortage Early Warning (T8)
- **Built (T8, PR #61):** 551 rows (section x month, 1 to 3 months after the forecast origin), each with a risk (low, medium, high, unknown) and a reason from its own numbers. `GET /shortage` serves it.
- **Groundwater (D7) is not in the repo**, so every reason says "groundwater data unavailable" and the warning is a forecast-against-capacity warning only. Reservoir levels are off until Q2 is approved.
- Capacity is ASSUMED (A8 fleet scenario: 1,150 tankers x 9 trips a day, 90 stand-in stations). 3 sections have no station, so their risk is `unknown`. Risk ratios (1.0 and 0.85) and the 80% bound rule are [OPEN].
- Built on T2's forecast, now the gradient-boosting model (F5), trained on data from before the Feb/Mar 2026 re-cut, so it inherits those limits. With it the list has 86 high, 110 medium, 352 low and 3 unknown section-months (with seasonal naive: 46 / 130 / 372 / 3).

---

## 3. Layer B: Allocation

### F7 Service models (A2)
- Need weights (water access counts double) and thresholds are policy assumptions [ASSUMED]. Officers can try other need weights for one plan (0 to 5 each); a weighted plan is a separate plan with its own ledger entry. The effect is small: on 2025-05-01 the strongest water-access setting moves 6 groups by at most 8 trips, because daily capacity limits it. The debt weight has no slider (the replay has no debts).
- Wards are never classed `no_connection` by Census alone (maximum non-tap share about 29%); that class normally comes from officer input.
- Need comes from Census 2011 through the approximate crosswalk.

### F8 Fair Queue (A3)
- Booking categories (domestic, apartment, commercial) and tier-1 declarations are **not in the HMWSSB data**. The simulation draws them from Census shares (SYNTHETIC).
- About 20% of bookings use a flagged fallback entitlement (median ward) because their section has no ward or no Census need data.
- Whether a household **without a CAN** can book at all is unverified [OPEN]. The app and website need a CAN; the phone line (155313) is unconfirmed.

### F9 Scheduled Supply Planner (A4)
- The service point list **starts empty**: officers must register points, because public tap and point data do not exist.
- Stops are whole 5,000 litre loads (shares are rounded to loads). Targets use Census off-premises share times 2011 population.
- The timetable SMS and print wording belongs to P4/T5.

### F10 Outage Response (A5, T5)
- Tier-0 stops are still officer-entered: `GET /facilities/candidates` lists each ward's OSM hospitals, UPHCs, clinics, care homes and schools (D9) as candidates, but nothing turns one into a critical stop automatically and no route creates outage critical stops yet; OSM is incomplete (see F1).
- Detection threshold (5 reports in 6 hours) and the 24-hour deprivation constant are policy assumptions.
- Notices are entered by officers; HMWSSB publishes press releases only, so no parser was built (D14 not fetched). Exact-only area matching; no locality alias table; Census population overstates partial-ward notices; no resident registry for alerts [OPEN].

### F11 Water Debt (A6)
- Debt is now settled and saved when an officer closes a day (`POST /debt/days/{day}/close`) from an approved supplied plan and the day's delivery outcomes, and the next supplied plan uses it (A7 raises the ward's turns). In the replay no delivery outcomes are simulated, so debt is never settled there. See F20 for the limits.
- The 7-day cap, 3-day alert and the weight of debt in the queue are [ASSUMED].

### Daily planner (A7), station sharing, sandbox (A8)
- Plans built through the API (`POST /plans`) use T9's gate. The offline replay script and `build_plan`'s own default still use the stand-in `ProvisionalGate` (it flags only groups with no Census need data), so the committed A8 replay outputs are unchanged and an API plan's digest differs from the replay CSV's for the same day.
- Routing needs officer-registered service points and critical-stop locations. Without a fleet, needs are listed as `unrouted`. Booked trips are single loads, not routed.
- **Station trip sharing** (3 km) is a new operating idea. No source shows HMWSSB lending trips between stations [OPEN]. Radius 0 switches it off.
- The sandbox uses 90 stand-in stations; straight-line km times 1.35 plus an in-section allowance, not real roads.
- Replay bookings carry no tier, so tier 0 and 1 priority is not tested in the simulation.
- Scheduled supply in the sandbox treats every A2 candidate as officer-confirmed.
- **The duplicate-merge measure (PS11) is missing** from the Impact results: the sandbox does not simulate complaints. The calibration extract is now logged (F13), so the engine's merge rate on real duplicates is known (82% linked, 65% into the right incident), but not a JalLekha-vs-B1 comparison.
- JL (JalLekha) is worse than B1 on: booked service served (the 5% reserve), and km per litre (sharing). These are listed in `summary.json`.
- Simulation shows capacity is not binding on 2025 data (B1 served 98.7%). The tight scenario is calibrated to the 2026 delivered share, whose cause HMWSSB does not publish.

---

## 4. Layer C: Trust and access

### F12 Delivery proof (T3)
- The driver app (U4) runs the live flow (start, send code, verify with the device position, outcome) when signed in as a driver and stops are registered; otherwise it shows its fixture preview. Stops are registered by an officer (`POST /stops`); no stop exists until then. Geofence radius (150 m) and the majority margin are [OPEN].
- Silent residents count for nothing; unresolved deliveries never reduce debt (decided in A6).

### F13 Duplicate engine (T1)
- **Calibration reproduced on a logged pull (item 14).** The original 31,098-row extract was never found and Chicago's data changes daily, so the closest match was pulled and registered (`data/raw/d13_chicago_311/`, D13-CHICAGO-311: the four water-supply types, 2022-2023, 31,835 rows, 4,931 duplicates) and `scripts/trust/calibrate_dedup.py` writes `data/derived/dedup_calibration.csv`. Results:
  - 95% of duplicates within **104 m** of their parent (document: 106 m), and no-water duplicates 90% within **24 h** (document: 20 h): reproduced.
  - Leak duplicates 90% within **381 h, about 16 days** (document: about 9 days): not reproduced; the 7-day leak window misses more leak duplicates than the document implies.
  - The document's **71% / 88%** reproduce (72% / 85%) only when a duplicate counts as caught once it is linked to *any* earlier complaint. Linked into the right incident (its parent or another duplicate of it): **59% / 60%**; to the exact recorded parent: 53% / 56%. Up to 15% / 27% of non-duplicate complaints are merged too (an upper bound: Chicago does not flag every duplicate).
  - **The rule JalLekha uses** (100 m; 48 h no-water, 7 days leaks; Chicago types mapped, low pressure as no-water, ASSUMED): 82% linked, 65% into the right incident, up to 19% of non-duplicates merged.
- It is still another city's data. Text similarity (LaBSE) is untested on Indian examples: it needs the heavy `ml` extra (torch, about 2 GB with the model) and a labelled set of Indian complaint pairs.

### F14 Unified multilingual intake (T4)
- No Telugu or Urdu speech error rate is published; it must be measured on a small labelled set. Failed items are saved for a human.
- Items marked `ledger_missing` are not retried automatically.
- The resident app (U2) is merged but still in progress; field-worker mode (U3) is built with a SYNTHETIC demo identity pending authentication. Neither has a live API (T10).

### F15 Supply-notice feed (T5)
- See F10: officer entry only, exact area matching, alert wording [OPEN].

### F16 Explanations and contest (T7)
- Counterfactuals change one input at a time. Reason and outcome codes and template wording are [OPEN].
- Debt appears in explanations only when a `DebtAccount` is supplied.
- The explanation and contest screen (U8) is live for officer, resident and councillor tokens (ward and booking explanations with the counterfactual, filing, the own-contest list, the officer's reply with a required reason); otherwise it shows sample explanations and browser-only contests labelled "not sent to the server". A resident or councillor token with no bound user id can read explanations but cannot file or list contests.

### F17 Confidence and defer-to-officer (T9)
- **Built (T9, PR #59), threshold chosen on a degraded-signal replay (item 18).** Confidence is the minimum of the available signals (Census join quality and section location); low confidence keeps a group in the plan but flagged, and `approve_plan` refuses until an officer marks it checked.
- **Threshold 0.05, DERIVED** (`data/derived/confidence_calibration.csv`, SIMULATION). The earlier all-fallback replay could not tell thresholds apart, so the replay is now run against "true" data that differs from ours in known places: weakly placed sections really lie in a neighbouring ward (2% of INSIDE placements, 25% NEAREST_500M, 50% WARD_NAME / OSM_NEAR_DIVISION / 6 km outliers) and true need differs from the recorded need by a log-normal factor that widens as the Census join score falls. These error rates are **ASSUMED** (config), not measured.
- Across 5 error draws, with nothing flagged 88.97-91.22% of group-days keep the same decision; 0.05 is the lowest threshold that keeps at least 90% (lowest draw 90.86%) in every draw. It flags the 45 of 152 replay groups with confidence 0 (no usable Census join or no ward placement) and catches about 41% of the damaged groups. The old 0.50 flagged 60 groups and kept fewer decisions right (lowest draw 90.22%). Catching 90% of damaged groups would need 0.70 and send 117 of 152 groups to officers.
- **Partly circular:** errors are placed where the data's own quality metadata says it is weak, which is the premise of the gate; the result says what threshold the 90% rule needs *if* real errors follow that pattern, not that they do (no ground truth). Need errors change few decisions because capacity rarely binds in the replay, so the margin over 90% is thin. The rule (90% in every draw) is OPEN, owner to confirm; the catch-rate alternative is in the calibration file.
- Plans stored before this change were built with the 0.50 gate; rebuilding one gives a different digest (409 on load, as for any gate change).
- Three of the five planned signals are unavailable: data age, forecast interval width and evidence age.

### F18 Tamper-evident ledger (S3, T6)
- Removing the last entry cannot be detected without a published head hash.
- Needs `LEDGER_HMAC_KEY`; with no key the ledger refuses to write.

### F19 Policy sandbox and Impact page
- See sandbox limits in section 3. The impact page (U9) reads `GET /impact` when an officer is signed in (badges taken from the API: SIMULATION) and the committed A8 snapshot otherwise.

### F20 Open ward report cards
- **Live (item 11):** the card shows deliveries (last 30 days at the ward's registered stops, by outcome), water debt (from closed days) and the schedule (one stored plan: supplied before replay, latest day, approved before draft), each with its basis or the reason it has none. The U10 screen calls it for resident, councillor and officer tokens and falls back to the sample cards labelled SIMULATION.
- **Debt covers scheduled-supply wards only.** Booked household deliveries have no registered stop and no delivery proof, so they cannot pay debt back and none is charged for them. A ward's debt starts only once it has a registered stop and a supplied plan gives that stop water.
- **A stop's ward** is named by the officer or placed on the 2016 ward map (DERIVED; the map is old and approximate, limit 2). A stop outside every ward is UNPLACED and counts for no ward. A stop's ward cannot be changed (no update route).
- **Each Confirmed delivery counts as one full 5,000 l load**: deliveries record no litres. Scheduled litres are split evenly across a ward's stops in whole loads, so a ward's planned litres can differ from its A4 share by up to one load per stop. Without a fleet, stop loads are not routed and have no arrival times.
- **Closing a day is manual:** an officer closes each past day, one after another without gaps (a day with no supplied plan is closed without one); there is no automatic close at midnight. Closing waits until every delivery of the day has an outcome. Only plans built from supplied bookings create debt (replay plans are simulations). The officer chooses which approved plan of the day settles it (the ledger records it); what is owed comes from the stops that plan was built with, while every Confirmed delivery counts for the ward its stop serves now.
- The ledger entries of a close are written before the database save (as for plan approval); a failure between the two (for example a locked SQLite database, answered with a 500) leaves the entries without the saved day, and closing the day again writes them a second time.
- The officer id in the close request is taken from the body, not from the token (as for plan approval), so one officer token can close a day in another's name; the ledger records the token's role only.
- The U10 ward picker lists the 145 wards of the committed atlas snapshot. API reasons and the schedule basis are English in every language, and the Telugu, Urdu and Hindi card wording is a draft like the rest.
- SMS wording is English only; Telugu, Urdu and Hindi fall back to English until native speakers review them.

---

## 5. Not finished (2026-10-04)

The to-do list for these, with how to do each item and when it counts as done, is `docs/REMAINING_WORK.md`.

| Item | Owner | Why |
|---|---|---|
| X1 release tag | P4 | README, slide outline and demo script are written; the tag waits for green CI and version approval |
| Green CI | owner | GitHub Actions has not run since the account billing block (jobs fail in seconds with "recent account payments have failed"); everything merged was checked locally instead |
| A live booking feed | HMWSSB / owner | plans can be built from bookings an officer supplies (CSV or the API, any day), but nothing imports HMWSSB's bookings automatically; supplied bookings are not verified, capacity is the ASSUMED fleet scenario, and nothing carries over from the day before (no queue state or debt from earlier supplied days) |
| Spatial models for E5 | P1 | BYM2 did not converge (see F4); peer + NB are used |
| Filling-point and reservoir decisions (Q1, Q2) | owner | ON_HOLD |
| Telugu, Urdu and Hindi wording review | native speakers | review pack and glossary ready in `docs/translation_review/`; set each language to "reviewed" in `frontend/src/i18n.tsx` afterwards |
| Passwords or single sign-on | owner | sign-in is a pasted token from the environment; there is no user database |

### Limits of the live wiring
- **Concurrent writes** to one plan or delivery: inside one process a per-item lock makes each change, its ledger entry and its save one step, and a stored version refuses a write from a stale read (409, "reload and try again"); a duplicate delivery start is a 409, not a 500. With several server processes the version still prevents lost updates, but a refused change can leave its ledger entry without the saved change (the lock does not span processes).
- **Plans are stored as a rebuild recipe**, not a copy. The first build or rebuild after a restart takes about 12 s, and the explain-booking route can take up to about 30 s after a restart when many plans are stored. If the inputs or gate change after a plan is stored, loading it fails with 409 (digest mismatch) rather than showing a different plan.
- A plan view is about 1.1 MB (every station and booking). It is refetched after each check or approval.
- The ledger entry for a check or approval is written before the database save, and for a new plan after it; a failure between the two leaves one without the other.
- A representative id cannot be reused at another stop. `GET /deliveries` loads every matching delivery before paging.
- The live schedule has no time windows (the API has none). Wards and sections are shown by name (from the Census evidence file); a ward without a name shows its id.
- The shortage screen loads at most 600 rows; API reason texts and bases are English only in every language.

## 6. Solution document statements that are now out of date

- The E5 paragraph says zero candidates; it is now 6 (2025 inputs, peer and NB agreeing).
- F2 says the growth ratio must not scale households; a modelled 2025 estimate now does.
- F19 policy list lacks JL_F8 and JL_POOL.
- D12 says "159 of 201 sections" geocoded; it is now 161 of 221.
- D9 lists 885 / 310 / 350 / 399 / 59 from a snapshot that was never found; the re-pull gives 941 / 294 / 174 / 439 / 6 in the wards (the D9 row now says so).
- `docs/features.csv` now has `doc_promise_met` (yes / partly / no) and `gap` per row (item 22). A DONE status means the task's own done-when passed, not that the solution document's promise is met.
