# JalLekha 2.0: known limitations

Status on `main` as of 2026-10-03 (after PR #50). One section per feature of
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
9. **No authentication or API yet.** Roles (officer, driver, resident) arrive with T10. There is no live end-to-end path from a screen to the planner.
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
- **[NOT BUILT]** The Atlas screen (U5). The data exists in `data/derived/evidence/`.

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
- **[NOT BUILT]** The map screens (U5).

### F4 Under-served Field-Check Screen (E5)
- 107 wards screened, **7 candidates**, 38 wards left in data review (37 have no placed section).
- Peer-median screen only. **E5's done-when ("flags stable across model variants") is not met**, although the tracker says DONE: the output says `stability_evaluated: false`.
  - The NB, BYM2 and BYM2-shrinkage models exist (`services/underserved_models.py`, PyMC, 5-fold out-of-fold) but `scripts/evidence/build_underserved.py` calls `screen(areas)` without model results. They were skipped when E5 was switched on (PR #43).
  - BYM2 also needs a ward-adjacency graph with a named reviewer (by design); neither exists yet.
  - Running the models may reduce the 7 candidates, since a candidate must agree across variants.
- Low bookings cannot prove hidden demand. A candidate only means "send someone to check". No field check outcomes recorded (0 ground truth).
- Thresholds are policy parameters.

### F5 Surge Forecast and Capacity Planner (T2)
- **[NOT BUILT]** Only `config/forecast.py` exists. Weather (D8) and groundwater (D7) data were never downloaded; the raw folders hold only retrieval logs.
- Planned limits: 13 scorable months per section is too few for 95% intervals; a model is used only if it beats seasonal naive.

### F6 Shortage Early Warning (T8)
- **[NOT BUILT]** Needs T2, groundwater data, and reservoir levels (D15, [OPEN]: only if a machine-readable source exists).

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
- The planner's **confidence gate is a stand-in** (`ProvisionalGate`): it flags only groups with no Census need data. The real gate is T9.
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
- The driver app (U4) is **[NOT BUILT]**. Geofence radius (150 m) and the majority margin are [OPEN].
- Silent residents count for nothing; unresolved deliveries never reduce debt (decided in A6).

### F13 Duplicate engine (T1)
- Calibrated on Chicago 311, another city. The frozen extract was not found, so the 71% and 88% figures cannot be reproduced from the repo. Text similarity is untested on Indian data.

### F14 Unified multilingual intake (T4)
- No Telugu or Urdu speech error rate is published; it must be measured on a small labelled set. Failed items are saved for a human.
- Items marked `ledger_missing` are not retried automatically.
- **[NOT BUILT]** Resident app with offline queue (U2, PR #41 has failing checks) and field-worker mode (U3).

### F15 Supply-notice feed (T5)
- See F10: officer entry only, exact area matching, alert wording [OPEN].

### F16 Explanations and contest (T7)
- Counterfactuals change one input at a time. Reason and outcome codes and template wording are [OPEN].
- Debt appears in explanations only when a `DebtAccount` is supplied.
- **[NOT BUILT]** Explanation and contest screens (U8). No API (T10).

### F17 Confidence and defer-to-officer (T9)
- **[NOT BUILT]** Only the stand-in gate exists. The target share (for example 90%) is [OPEN] with the owner.

### F18 Tamper-evident ledger (S3, T6)
- Removing the last entry cannot be detected without a published head hash.
- Needs `LEDGER_HMAC_KEY`; with no key the ledger refuses to write.

### F19 Policy sandbox and Impact page
- See sandbox limits in section 3. **[NOT BUILT]** Impact page (U9).

### F20 Open ward report cards
- **[NOT BUILT]** No backend and no screen. In the tracker only U10 covers it, and it depends on T10.

---

## 5. Not built yet (from the 2026-10-03 verification)

| Item | Owner | Blocks |
|---|---|---|
| T2 forecast, T8 shortage warning | P3 | U6 |
| T9 confidence gate | P3 | A7's real gate |
| T10 API for all screens | P3 | U5, U6, U7, U10 |
| U2 resident app (PR #41 failing), U3, U4 | P4 | demo steps 7 and 8 |
| U5, U6, U7, U8, U9, U10 screens | P4 | demo |
| X1 README, slides, demo script, release tag | P4 | submission |
| F20 report-card backend | unassigned | U10 |
| Hospital and school data (D9) in the ward table | P1 area | F1 tier 0 and F10 |
| Weather (D8) and groundwater (D7) data | P1/P3 | T2, T8 |

## 6. Solution document statements that are now out of date

- The E5 paragraph says zero candidates; it is now 7 (2025 inputs).
- F2 says the growth ratio must not scale households; a modelled 2025 estimate now does.
- F19 policy list lacks JL_F8 and JL_POOL.
- D12 says "159 of 201 sections" geocoded; it is now 161 of 221.
- T7 is merged (PR #46) but the tracker still says IN_REVIEW.
