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
9. **Most officer and field screens now use the live API, with a labelled fallback.** T10 is merged (bearer-token roles officer, driver, resident, field worker and councillor; tokens, optionally bound to a user id, come from the environment only). The atlas, equity and field-check (U5), forecast and shortage (U6), impact (U9), plan (U7), explanation and contest (U8), driver (U4), field-worker (U3) and resident (U2) intake screens call it when someone is signed in with the right role and the API answers; otherwise they show the committed snapshot or sample data with a "Saved snapshot" chip and the reason. The ward report card and SMS summary (U10) still show sample cards. Nobody signs in with a password: a token is pasted in the top bar. Screens were tested with mocked and real API calls, but have not been looked at in a browser by a person.
10. **Translations are drafts.** Telugu, Urdu and Hindi wording needs native-speaker review. Alert and explanation wording is [OPEN].
11. **No migrations.** New database columns need a fresh database or a manual column add.
12. **Third-party warnings.** OR-Tools prints SWIG deprecation warnings on import (upstream).

---

## 2. Layer A: Evidence

### F1 Water Access Atlas (E1, E2)
- Based on Census 2011 moved onto 2016 wards approximately (limits 1 to 3 above).
- The **critical facilities column is empty** (`FACILITIES_UNAVAILABLE`): hospitals, clinics and schools (D9) were never loaded into the ward table.
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
- **[NOT BUILT]** The gradient-boosting model with weather and groundwater: no scikit-learn or LightGBM dependency is agreed, and weather (D8) and groundwater (D7) data are not in the repo.
- [OPEN] trips per tanker per day (the capacity planner refuses to run without it), the model-selection rule, and Chronos-2.
- Short series (13 scored months per section, too few for 95% intervals); section names are not mapped across years, and the Feb/Mar 2026 re-cut breaks section-by-section comparison.
- `GET /forecast` and `/forecast/backtest` serve the table, and the U6 screen shows them live (city forecast DERIVED with no city interval, section forecast with intervals, backtest accuracy per model) with the committed real history and SIMULATION fixtures as the fallback.

### F6 Shortage Early Warning (T8)
- **Built (T8, PR #61):** 551 rows (section x month, 1 to 3 months after the forecast origin), each with a risk (low, medium, high, unknown) and a reason from its own numbers. `GET /shortage` serves it.
- **Groundwater (D7) is not in the repo**, so every reason says "groundwater data unavailable" and the warning is a forecast-against-capacity warning only. Reservoir levels are off until Q2 is approved.
- Capacity is ASSUMED (A8 fleet scenario: 1,150 tankers x 9 trips a day, 90 stand-in stations). 3 sections have no station, so their risk is `unknown`. Risk ratios (1.0 and 0.85) and the 80% bound rule are [OPEN].
- Built on T2's forecast, which is a seasonal-naive baseline from before the Feb/Mar 2026 re-cut, so it inherits those limits.

---

## 3. Layer B: Allocation

### F7 Service models (A2)
- Need weights (water access counts double) and thresholds are policy assumptions for officer sliders [ASSUMED].
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
- No verified critical-facility source: tier-0 stops are officer-entered.
- Detection threshold (5 reports in 6 hours) and the 24-hour deprivation constant are policy assumptions.
- Notices are entered by officers; HMWSSB publishes press releases only, so no parser was built (D14 not fetched). Exact-only area matching; no locality alias table; Census population overstates partial-ward notices; no resident registry for alerts [OPEN].

### F11 Water Debt (A6)
- Settlement exists, but debt only changes queue order through the planner (A7). In the replay no delivery outcomes are simulated, so debt is never settled there.
- The 7-day cap, 3-day alert and the weight of debt in the queue are [ASSUMED].

### Daily planner (A7), station sharing, sandbox (A8)
- Plans built through the API (`POST /plans`) use T9's gate. The offline replay script and `build_plan`'s own default still use the stand-in `ProvisionalGate` (it flags only groups with no Census need data), so the committed A8 replay outputs are unchanged and an API plan's digest differs from the replay CSV's for the same day.
- Routing needs officer-registered service points and critical-stop locations. Without a fleet, needs are listed as `unrouted`. Booked trips are single loads, not routed.
- **Station trip sharing** (3 km) is a new operating idea. No source shows HMWSSB lending trips between stations [OPEN]. Radius 0 switches it off.
- The sandbox uses 90 stand-in stations; straight-line km times 1.35 plus an in-section allowance, not real roads.
- Replay bookings carry no tier, so tier 0 and 1 priority is not tested in the simulation.
- Scheduled supply in the sandbox treats every A2 candidate as officer-confirmed.
- **The duplicate-merge measure (PS11) is missing** from the Impact results: T1's calibration extract was never logged.
- JL (JalLekha) is worse than B1 on: booked service served (the 5% reserve), and km per litre (sharing). These are listed in `summary.json`.
- Simulation shows capacity is not binding on 2025 data (B1 served 98.7%). The tight scenario is calibrated to the 2026 delivered share, whose cause HMWSSB does not publish.

---

## 4. Layer C: Trust and access

### F12 Delivery proof (T3)
- The driver app (U4) runs the live flow (start, send code, verify with the device position, outcome) when signed in as a driver and stops are registered; otherwise it shows its fixture preview. Stops are registered by an officer (`POST /stops`); no stop exists until then. Geofence radius (150 m) and the majority margin are [OPEN].
- Silent residents count for nothing; unresolved deliveries never reduce debt (decided in A6).

### F13 Duplicate engine (T1)
- Calibrated on Chicago 311, another city. The frozen extract was not found, so the 71% and 88% figures cannot be reproduced from the repo. Text similarity is untested on Indian data.

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
- **Built (T9, PR #59), threshold not calibrated.** Confidence is the minimum of the available signals (Census join quality and section location); low confidence keeps a group in the plan but flagged, and `approve_plan` refuses until an officer marks it checked.
- The threshold is **PROVISIONAL 0.50**: on P2's replay the 0.90 target is met with nothing flagged and the match share does not rise with the threshold (`not_separable`), so no threshold can be chosen from that replay. P2 must supply a degraded-signal scenario.
- At 0.50 the gate flags 60 of 152 groups (39%), about 38 a day for officers to check.
- Three of the five planned signals are unavailable: data age, forecast interval width and evidence age.

### F18 Tamper-evident ledger (S3, T6)
- Removing the last entry cannot be detected without a published head hash.
- Needs `LEDGER_HMAC_KEY`; with no key the ledger refuses to write.

### F19 Policy sandbox and Impact page
- See sandbox limits in section 3. The impact page (U9) reads `GET /impact` when an officer is signed in (badges taken from the API: SIMULATION) and the committed A8 snapshot otherwise.

### F20 Open ward report cards
- The ward report card and SMS summary routes exist (`/wards/{id}/report-card`, `/sms-summary`); the U10 screen still shows sample cards labelled as simulated and does not call them. Deliveries, water debt and schedule are "not available yet" in the card, because deliveries are stored now but are not yet joined to wards and water debt. SMS wording is English only; Telugu, Urdu and Hindi fall back to English until native speakers review them.

---

## 5. Not finished (2026-10-04)

| Item | Owner | Why |
|---|---|---|
| X1 release tag | P4 | README, slide outline and demo script are written; the tag waits for green CI and version approval |
| Green CI | owner | GitHub Actions has not run since the account billing block (jobs fail in seconds with "recent account payments have failed"); everything merged was checked locally instead |
| Ward report cards (U10 screen) live, with deliveries, debt and schedule | P3/P4 | deliveries and plans are stored, but nothing yet joins a delivery's outcome to a ward and its water debt (A6), so the card cannot show them |
| Plans from today's bookings | P2/P3 | `POST /plans` builds plans from the committed Mar-Jul 2025 replay (SIMULATION) only; no job builds a plan from live bookings |
| Gradient-boosting forecast | P3 | no agreed dependency; weather (D8) and groundwater (D7) data missing |
| T9 threshold calibration | P2/P3 | needs a degraded-signal replay scenario from P2; the threshold is a provisional 0.50 |
| Spatial models for E5 | P1 | BYM2 did not converge (see F4); peer + NB are used |
| Hospital and school data (D9) in the ward table | P1 | critical-facility column is empty, so F1 tier 0 and F10 have no facility counts |
| Filling-point and reservoir decisions (Q1, Q2) | owner | ON_HOLD |
| Telugu, Urdu and Hindi wording review | native speakers | drafts only |
| Passwords or single sign-on | owner | sign-in is a pasted token from the environment; there is no user database |

### Limits of the live wiring
- **Concurrent writes** to one plan or delivery are last-writer-wins (two simultaneous wrong OTP tries or checks can lose one). A race between two starts of the same delivery can end in a 500 instead of a 409.
- **Plans are stored as a rebuild recipe**, not a copy. The first build or rebuild after a restart takes about 12 s, and the explain-booking route can take up to about 30 s after a restart when many plans are stored. If the inputs or gate change after a plan is stored, loading it fails with 409 (digest mismatch) rather than showing a different plan.
- A plan view is about 1.1 MB (every station and booking). It is refetched after each check or approval.
- The ledger entry for a check or approval is written before the database save, and for a new plan after it; a failure between the two leaves one without the other.
- A representative id cannot be reused at another stop. `GET /deliveries` loads every matching delivery before paging.
- The live schedule shows ward ids and litres, not ward names or time windows, because the API has none; the plan screen's priority-weight sliders exist only in the sample.
- The shortage screen loads at most 600 rows; API reason texts and bases are English only in every language.

## 6. Solution document statements that are now out of date

- The E5 paragraph says zero candidates; it is now 6 (2025 inputs, peer and NB agreeing).
- F2 says the growth ratio must not scale households; a modelled 2025 estimate now does.
- F19 policy list lacks JL_F8 and JL_POOL.
- D12 says "159 of 201 sections" geocoded; it is now 161 of 221.
- T7 is merged (PR #46) but the tracker still says IN_REVIEW.
