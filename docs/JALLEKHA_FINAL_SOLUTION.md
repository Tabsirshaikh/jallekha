# JalLekha 2.0: final solution (built from scratch)

**Fair, explainable sharing of tanker water in Hyderabad, built only on data that exists.**

Version 3, 30 September 2026. Replaces the 22 September version. This version assumes a **new codebase built from scratch**; a few proven modules from the v1 prototype are ported with their tests (Section 9), nothing else is inherited.

Every data item is tagged **REAL** (public, downloaded and checked), **DERIVED** (computed from REAL by stated code), **ASSUMED** (policy setting or news figure), **SYNTHETIC** (generated for the demo, always labelled on screen) or **TO FETCH** (public and confirmed to exist, not yet downloaded). Every research claim has a source in Section 11 and a verification status.

---

## 1. The problem, in one paragraph

HMWSSB delivers almost every tanker that is booked (1,316,215 bookings and 1,315,622 deliveries, Jan 2022-Feb 2024: **99.95%**, REAL). The unfairness is in **who can book**. Across 201 HMWSSB sections the booking Gini is **0.78**; the top 21 sections (10%) took **67.7%** of bookings and the bottom half **2.9%** (REAL). Booking needs a phone, money (Rs 500 domestic, caps of 1 per 2 days or 8 per month) and storage. Census 2011 shows households without drinking water on their premises reach **33.4%** in some GHMC wards (median 5.5% across 148 GHMC Census wards; 2009 ward numbering) and households with no phone reach **19.2%** (REAL; recomputed 2026-10-02 from the HH-14 tables, GHMC wards only. The earlier 68.4% was Secunderabad Cantonment Board ward 2, which is not GHMC). In the western wards (2009 wards 111-114, Gachibowli to Chanda Nagar; today's Madhapur-Kondapur area) off-premises water is 12-33%, so heavy booking there is partly real need too: **booking volume tracks who can book and where piped supply is weak, not need alone.** Demand also triples each summer (22,834 bookings in Jan 2022 to 89,284 in Jun 2022, REAL) and the queue is first-come-first-served.

> **JalLekha measures need independently of requests, compares it with who actually gets water, and allocates limited tankers by need, history and fairness over time, with every decision explained, contestable and logged.**

## 2. How each PS11 requirement is met

| PS11 asks for | JalLekha feature | Data basis |
|---|---|---|
| Collect requests, tap schedules, supply info, complaints in one place | F14 unified intake (app, IVR/missed call, SMS, voice, field worker, offline); F15 supply-notice feed; F7 published schedules | Channels real code; complaints SYNTHETIC; notices REAL (TO FETCH) |
| Analyse demand and vulnerability | F1 Atlas, F2 growth adjustment, F5 forecast, F6 shortage early warning | REAL |
| Map service coverage | F3 Booking Equity + coverage map | REAL |
| Recommend fair allocation | F8 fair queue, F9 scheduled supply, F10 outage response, F11 water debt | Rules REAL; daily stream SYNTHETIC calibrated to REAL totals |
| QE1 explain priority for household, locality, community | F16 explanation per ward **and per booking**, counterfactual "what would change it" | DERIVED |
| QE2 population, vulnerability, previous service, distance, unmet demand, not submission order | F1/F2 need, F11 debt (previous service, unmet demand), distance in two roles (Section 5.4), F8 replaces FCFS | REAL + DERIVED |
| QE3 demand trends, underserved locations, potential shortages | F5 forecast, F4 under-served detector, F6 shortage early warning | REAL |
| QE4 mobile, multilingual, voice, offline, field workers | F14: Telugu, Urdu, Hindi, English; IndicConformer ASR; offline queue; field-worker mode; SMS/IVR | Models REAL (open, MIT) |
| QE5 fewer unmet requests, shorter travel, fewer duplicates, balanced coverage | F19 policy sandbox + F13 duplicate engine, each against first-come-first-served | SIMULATION on REAL-calibrated demand; duplicate rule calibrated on REAL complaints |

## 3. What the research says (verified)

| Finding | Design consequence |
|---|---|
| Complaint volume is not need: reporting bias and delay are documented in other cities, and Bayesian spatial latent-variable research estimates unobserved reporting under method-specific assumptions (Kontokosta & Hong 2021; Liu, Bhandaram & Garg 2023; Agostini, Pierson & Garg 2024). Those results are not ground truth or validated for Hyderabad. | Never allocate by bookings or complaints. F4 screens validated, comparable observed bookings against need-side references for a human field check; it cannot infer hidden demand or reporting probability. Census variables require validated geography; E3 growth is context-only. Duplicates may also inform reporting analysis (F13), subject to separate validation. |
| Using a proxy (cost) as the target builds bias in (Obermeyer et al. 2019). | Need target is water access, not requests. |
| Fair allocation with routing under uncertainty, max-min objective (Gao, Iravani & Sinclair 2026, arXiv 2606.19278). Deficit round robin gives long-run fairness with O(1) work per decision (Shreedhar & Varghese 1996). | Fair queue = tiers + deficit round robin; scheduled supply = weighted max-min; we cite them and do not claim a new algorithm. |
| Tree models and simple baselines beat deep models on small tabular data (Grinsztajn et al. 2022). Hierarchical forecasts can be made coherent section-to-city (Wickramasuriya, Athanasopoulos & Hyndman 2019). | Monthly section forecast with seasonal-naive baseline, gradient boosting candidate, reconciliation, honest backtest. |
| Humanitarian logistics should minimise deprivation cost, which rises non-linearly with time without supply (Holguín-Veras et al. 2013). | Outage priority rises with hours cut off (F10). |
| Abstaining and deferring to a human with a documented threshold (Chow 1970; conformal risk control, Angelopoulos et al. 2022). | Low-confidence decisions cannot auto-commit (F17). |
| Counterfactual explanations: "what would have to change" (Wachter, Mittelstadt & Russell 2017). | Explanation shows the smallest change that moves the rank (F16). |
| OTP + GPS tanker delivery already runs in Bengaluru; Delhi runs GPS tankers and fixed-point schedules for unconnected localities. | OTP/geofence is standard practice, not our innovation. Scheduled supply to fixed points is a proven model. |
| Norms: Sphere 2018 at least 15 l/person/day, water point within 500 m, queue under 30 min (PDF verified); JMP basic service = collection within 30 min round trip; CPHEEO 1999: 135 lpcd cities with sewerage, 150 metropolitan, 40 through standposts (secondary copy). | 15 lpcd floor; 150 lpcd reporting norm for Hyderabad; all as config values with source. |

**What is ours:** not a new algorithm but (1) a working evidence layer on real Hyderabad data that exposes the booking/need mismatch, (2) a fair queue + scheduled supply evaluated against today's FCFS on a replay of the real Mar-Jul 2025 summer (2023 kept for continuity, F19), (3) a closed loop in which verified delivery outcomes change the next allocation.

## 4. Data sources

| # | Dataset | Status | Used by |
|---|---|---|---|
| D1 | HMWSSB tanker bookings/deliveries, 201 sections, monthly Jan 2022-Feb 2024 (Dec 2022 empty), OpenCity; the same table continues to **Aug 2026** on the Telangana Open Data Portal (dataset 7f408a3a-7cdb-4d33-bfa3-1869f88c0e25, OGL India; identical on all 26 overlapping months; sections re-cut Feb/Mar 2026), see `docs/research/P2.md` | **REAL**, verified (4,398 rows); portal extension **TO FETCH** (P1) | F3, F4, F5, F8, F19 |
| D2 | Historical GHMC ward polygons, 145 of the 2016 scheme's 150 (wards 3, 4, 11, 13, 31, 113 missing), DataMeet/OSM | **REAL**, partial historical geometry; not current boundaries | all spatial demo views |
| D3 | Census 2011 PCA + HH-14 by ward, Hyderabad district (108 wards, 3,943,323 people), OpenCity | **REAL**, verified | F1 |
| D4 | Census 2011 PCA + HH-14, GHMC wards in Rangareddy (NADA catalogs 6728, 9835) | **REAL** | F1 west/north |
| D5 | District/mandal boundaries plus official 2025-26 notices for 300 wards and the three-corporation reorganisation | **TO FETCH**; current machine-readable ward boundaries/crosswalk not verified | F1 geography versioning |
| D6 | **Google Open Buildings 2.5D Temporal** (2016-2023) plus WorldPop and GHS-POP 100 m population grids | **TO FETCH**, verified; modelled sources with documented uncertainty | F2 growth sensitivity |
| D7 | **Groundwater level, CGWB / Telangana GW Dept**: manual wells (four times a year) and telemetric stations, via India-WRIS time-series extraction (CSV mirror on India Data Portal); GHMC station coverage and licence to confirm | **TO FETCH**, verified to exist | F5 covariate, F6 |
| D8 | Daily weather 2022-2026, Open-Meteo | **REAL** | F5 |
| D9 | OSM hospitals, clinics, UPHCs, schools, care homes (885 / 310 / 350 / 399 / 59; that snapshot was never found. Re-pulled 2026-10-05 and placed in the 145 wards: 941 / 294 / 174 / 439 / 6, `data/derived/evidence/facilities_summary.json`) | **REAL** as mapped in OSM (incomplete); ward placement DERIVED | F1, F8 tier 0, F10 |
| D10 | OSM HMWSSB tanks, reservoirs, works (~38) as stand-in filling points | **TO FETCH**; use as filling stations is **ASSUMED** | routing |
| D11 | OSM road network + OSRM | **REAL** | routing |
| D12 | Section coordinates (Nominatim, 159 of 201) | **DERIVED**, not hand-checked | F3 |
| D13 | Chicago 311 water complaints 2022-23 with duplicate flag and parent id (31,098 rows, 4,994 duplicates; that extract was lost, re-pulled 2026-10-05: 31,835 rows, 4,931 duplicates, `data/raw/d13_chicago_311/`) | **REAL**, another city | F13 calibration |
| D14 | HMWSSB supply-interruption notices (published through press/website) | **TO FETCH**; parse only what is published | F15, F10 |
| D15 | Reservoir levels (CWC/India-WRIS bulletins for Nagarjuna Sagar, Yellampally; twin reservoirs in news) | **TO VERIFY**; build F6 without it if no machine-readable source | F6 |
| D16 | Booking caps and prices by category (domestic 1 per 2 days or 8/month Rs 500; apartments 5-24 flats 2/day or 30/month; 25-200 flats 3/day or 60/month; commercial 1/day or 30/month Rs 850), HMWSSB guidelines; channels 47% IVRS / 46% app / 7% web (Apr 2026, news) | **REAL** | F8 |
| D17 | Fleet and stations (577 tankers early 2024; 1,150 tankers, 90 filling stations, 150 filling points Dec 2025; 900 to 1,200 tankers Feb 2026; news) | **ASSUMED** | F5, F8, F19 |
| D18 | Daily booking stream, complaints, outages, delivery confirmations | **SYNTHETIC**, calibrated where a REAL total exists | demo |
| D19 | HMWSSB billing and collection, consumer accounts (`noofcans`) per section and connection category, monthly Jan 2022-Aug 2026, Telangana Open Data Portal (GODL); same section names as D1 | **REAL** | F3 (bookings per 1,000 domestic connections), F2 (connection growth) |
| D20 | GHS-POP R2023A population grid 2015 and 2025 (EU JRC, 3 arc-second, CC BY 4.0), cropped to GHMC; with Census 2011 (E2), Open Buildings trend (E3) and HMWSSB connection growth (D19) gives a 2025 ward population estimate with a low-high range | **REAL** grid (modelled); estimate **DERIVED** | F1, F2, F4 |
| — | Public-tap locations and timings | **NOT AVAILABLE**; officer-entered only, starts empty | F9 |

**Data rules:** raw files are never edited; every derived column carries a `_basis` column; hand-typed values from the v1 prototype (slum share, storage share, supply hours, fill stations, outage events, fleet table, 7.64% elderly default) are **not** imported.

**Census HH-14 trap:** column numbers used in code are 0-based pandas indices; the sheet's printed numbers are one higher. Code asserts header text (index 81 "Within premises", 82 "Near premises", 83 "Away").

## 5. Features

### Layer A: Evidence (real data)

**F1 Water Access Atlas.** Per area: population, households, **Water Access Deficit** (WAD = share without water on premises: near + away; plus smaller weight for non-tap source), **Channel Access Deficit** (CAD = share with no phone), **hardship** (one room or less, dilapidated, no assets), critical facilities. The demo is frozen to the historical `GHMC_2016_150` scheme and labels its 145 available polygons as incomplete. Census-to-polygon joins use ward number, name and location checks with exact mandal aggregates as fallback. Every area carries `geography_version`, effective dates, source and join quality. The current 300-ward/three-corporation view remains unavailable until official machine-readable boundaries and a crosswalk are verified. Label: "Census 2011 / historical 2016 geography".

**F2 Growth signal (revised after E3 data audit).** E3 extracts Google's fractional building-count band for 2016–2023 and derives a historical-polygon building-index ratio. Buildings are not households or people, and the Census-to-polygon joins are not location-validated. All 145 available polygons currently exceed the engineering annual-variability review threshold. Therefore the ratio is context-only: it must not scale Census households, rank areas, or be validated against HMWSSB sections without an authoritative section-to-ward transfer.

**F3 Booking Equity and coverage map.** Exact section-level booking concentration includes Gini, Lorenz curve, top-10% share, and seasonality. The map exposes three evidence-status layers: provisional historical water-access evidence, ward booking coverage, and field-check screening status. Ward booking counts and per-1,000 metrics remain null until an authoritative section-to-ward transfer and population denominator are verified; unavailable values are never shown as zero. The historical Census links remain review-only until location validation. There is no "people within 500 m of a public tap" layer because verified public-tap location and service data are unavailable.

**F4 Under-served Field-Check Screen.** When valid, comparable inputs exist, fit negative-binomial and BYM2/shrinkage-BYM2 count references using need-side covariates only (household exposure, WAD and non-tap share); compare observed/reference ratios with out-of-fold posterior intervals. A candidate requires agreement across model variants (or an explicitly labelled peer-median fallback), low relative bookings, high WAD, and CAD or hardship above the cohort median. Thresholds and the spatial graph require review and are policy parameters, not entitlements. Reasons show the actual values and thresholds. Output: a **field-check list**, never a claim of proven neglect. Low bookings cannot identify unreported demand or reporting probability. Officer field observations are the only ground truth; record them before claiming accuracy. No flag can change allocation or entitlement.

**F5 Surge Forecast and Capacity Planner.** Monthly bookings per section and city, 12 months ahead. Baseline seasonal naive (measured: 21.9% city MAPE, 35.1% section WAPE); candidates seasonal naive × YoY growth, one global gradient-boosting model pooled over all sections with month, lag-12, trend, weather (D8) and groundwater depth (D7); Chronos-2 as a backtest-only candidate (owner decision pending: allowed only if it clearly beats seasonal naive and the owner confirms it is consistent with the no-LLM rule); hierarchical reconciliation section→city; split-conformal intervals from residuals pooled across sections after scaling by each section's seasonal-naive error (80% and 90% only: 13 scorable months per section are too few for 95%), checked for coverage in a rolling-origin backtest. Only a model that beats the baseline is used; if none does, say so. Capacity: trips needed vs fleet × trips/day (ASSUMED, labelled).

**F6 Shortage Early Warning (new, QE3).** Per section, monthly: forecast demand (F5) vs assumed capacity, plus groundwater-level anomaly (D7) for the mandal (falling water tables drive borewell failure and tanker demand). Output: "shortage risk" list 1-3 months ahead with the reason. Reservoir levels added only if D15 is verified.

### Layer B: Allocation

**F7 Service models.** Each ward is classed from Census + officer input: piped normal, piped intermittent, no connection. Booked service → F8; no-connection areas → F9; sudden loss of piped supply → F10.

**F8 Fair Queue for booked tankers.** When bookings exceed capacity: tier 0 critical facilities; tier 1 households declaring no water on premises (spot-checked; SYNTHETIC in demo, drawn to Census ward shares) and assisted-channel bookings; then **deficit round robin** across wards by entitlement (households × need weight). HMWSSB caps kept (by consumer category). Today each booking token goes to the nearest filling station and waits by serial number (FCFS per station); the fair queue reorders bookings **within each station's daily capacity**. Output: daily ordered list per filling point → router.

**F9 Scheduled Supply Planner.** For wards F1/F4 flag: target litres = households without water on premises × household size × norm (15 lpcd floor, officer may raise). Fleet reserve allocated by **weighted max-min** with a minimum-share floor; stops are officer-registered fixed points (list **starts empty**); timetable published by SMS and printable notice.

**F10 Outage Response.** Outage from a complaint cluster (F13), a published notice (F15) or an officer. Tier 0 first, then everyone to 10-15 lpcd; priority rises with hours cut off (deprivation cost). No water debt here.

**F11 Water Debt in litres.** `D' = max(0, D + entitled − confirmed delivered)`, capped; only **Confirmed** deliveries (F12) count; long debt raises an alert; every change logged.

**Distance has two roles.** Household distance to water (Census near/away) is part of need. Tanker travel distance is a routing cost and trip budget only; it **never lowers a ward's priority**.

### Layer C: Trust and access

**F12 Delivery proof.** OTP to one of 2-3 registered representatives per stop, server-side geofence (150 m), then 3-5 random residents get "Did you get water? 1 yes / 2 no". Outcomes: OTP + mostly yes = Confirmed; OTP + mostly no = Disputed; no OTP + mostly yes = Unconfirmed; no OTP + mostly no = Failed; silence counts for nothing.

**F13 Duplicate engine (calibrated).** Location/time rule calibrated on real Chicago duplicates: 95% within 106 m; no-water duplicates 90% within 20 h; leaks 90% within about 9 days (re-pulled 2026-10-05: 104 m, 24 h, and about 16 days for leaks; `data/derived/dedup_calibration.csv`). Rule: 100 m radius, 48 h window for no-water / tanker-missed / dirty water, 7 days for leaks and other; same household id matches first. Text: multilingual sentence embeddings (e.g. LaBSE) as a secondary signal, marked untested on Indian data. Duplicate **rate per area** is kept as a reporting-activity signal (Liu et al. 2023).

**F14 Unified multilingual intake.** Resident PWA and field-worker mode (offline queue, sync later), SMS, missed-call/IVR, voice notes. Languages: **Telugu, Urdu, Hindi, English**. Speech-to-text with **AI4Bharat IndicConformer-600M multilingual** (open, MIT; covers Telugu, Hindi and Urdu; runs with `transformers` + ONNX Runtime, no NeMo) on the server; no Telugu/Urdu error rate is published, so we measure it on a small labelled set; fallback: voice note saved for a human. Text ≥ 16 px, touch targets ≥ 48 px.

**F15 Supply-notice feed (new).** Official HMWSSB interruption notices are entered (or parsed when machine-readable) as outage events with area and hours, shown to residents in their language and fed to F10.

**F16 Explanations and contest.** For every ward and **every booking**: tier, need components, debt, waiting time, and the smallest change that would move it (counterfactual). Residents or councillors can contest a ranking; the officer must reply with a reason; both go in the ledger.

**F17 Confidence and defer-to-officer.** Signals: Census join quality, data age, section-location uncertainty, forecast interval width, evidence age. Low confidence → the ward stays in the plan but needs an officer's "checked". Threshold chosen on the replay so a stated share of auto-committed decisions match the full-information plan.

**F18 Tamper-evident ledger.** SHA-256 hash chain with HMAC; every allocation-affecting change (plan, override, weights, delivery outcome, debt, contest) is an entry. Each entry carries a sequence number (gaps are detected) and a `key_id` (HMAC key rotation); the head hash is published daily (ward report card / SMS) so the key holder cannot silently rewrite history. "Tamper-evident, not blockchain."

**F19 Policy sandbox and Impact page.** Replay the real Mar-Jul **2025** section totals (main) and Mar-Jul 2023 (continuity) (daily arrivals SYNTHETIC, monthly totals exact) under capacity limits: fleet × trips/day (ASSUMED) and a capacity tightened to the REAL Jun-Aug 2026 delivered share (89-92%). All policies run on the same seeds. Policies: B1 FCFS per nearest filling station (today), B2 nearest filling point, B3 largest bookers first, B4 minimum cost, B5 need-weighted, JL (F8 + F9). 30+ seeds. Four PS11 measures vs B1: unmet need share and waiting days; tanker km and km per litre; duplicate merge share; Gini, Jain index and worst-ward fill rate. Real baselines (booking Gini 0.78 sections / 0.86 wards) shown separately. Every number on the Impact page has a badge REAL / DERIVED / SIMULATION; state where JL is worse (usually km).

**F20 Open ward report cards.** A public page per ward (and SMS summary) with its need, bookings, debt, deliveries and schedule, so communities can check the system.

## 6. Architecture

```
Evidence (batch):  D1-D9 ─► pipeline (join, growth, place, quality flags) ─► ward table ─► F1 F2 F3 F4 F5 F6
Allocation (daily): bookings ─► F8 fair queue ─┐
                    F4 flags ─► F9 scheduled ──┼─► OR-Tools + OSRM routes ─► F17 confidence gate ─► officer approval (F16)
                    F13/F15 ─► F10 outage ─────┘                                                        │
Trust:  driver PWA ─► F12 OTP + geofence + resident SMS ─► outcome ─► F11 debt ─► F18 ledger ─► next day
Access: F14 intake (app, SMS, IVR, voice, field worker, offline) ─► F13 duplicates ─► complaints / outages
```

**Stack (as built; decided by the owner 2026-10-06, item 20):** FastAPI + SQLAlchemy on SQLite (`create_all`, no migrations; PostgreSQL/PostGIS in Docker is deferred), React + TypeScript PWAs with our own `useApi` fetch hook (no TanStack Query), maps drawn as SVG by each screen (no Leaflet: clearer for a prototype and works offline), OR-Tools, OSRM with cached legs (road km and minutes computed once on OpenStreetMap by `scripts/routing/build_osrm_legs.py` and committed; straight line x 1.35 only where OSRM has no route or for points with no cached leg), pandas / scikit-learn / statsmodels, optional PyMC or CmdStan for evaluated spatial models, shapely, our own split-conformal intervals (MAPIE not used: same method, extra dependency), bottom-up reconciliation (the city forecast is the sum of section forecasts; Nixtla hierarchicalforecast not used: too little history per section for MinT), IndicConformer (`transformers` + ONNX Runtime). No LLM in any scoring, allocation or explanation step.

**Code rules:** business logic in pure, unit-tested services; thin routers; every weight and threshold in config with its source; every data column with a basis; external services (OSRM, ASR) have offline fallbacks; synthetic data labelled on screen.

## 7. Evaluation

| On real data | Metric | Baseline |
|---|---|---|
| Booking inequality | Gini, Lorenz, top-10% share, bookings per 1,000 | measured 0.78 sections / 0.86 wards |
| Growth adjustment | correlation of ward building growth with section booking growth | none |
| Under-served detection | number flagged, stability across model variants, agreement with peer-median | no ground truth (stated); field checks |
| Forecast | MAPE, WAPE, interval coverage, rolling origin | seasonal naive 21.9% / 35.1% |
| Duplicates | share of real duplicates linked to an earlier complaint / into the right incident | 100 m / 48 h = 72% / 59%; 300 m / 7 d = 85% / 60%; configured rule 82% / 65% (Chicago, re-pulled 2026-10-05; the earlier 71% / 88% matched "linked to any earlier complaint") |

On the calibrated simulation (always labelled): the four PS11 measures from F19, 30+ seeds, mean and range, against B1.

## 8. Risks and honest limits

1. Census is 2011; F2 measures sensitivity but does not update water-access observations. 2. The demo uses an incomplete historical 2016 ward layer; Hyderabad's 2025-26 reorganisation requires official current boundaries and a new crosswalk. 3. Section locations are automatic; ward-level numbers are approximate and no authoritative public section polygons were verified. 4. HMWSSB data now runs to Aug 2026 (Telangana portal), but sections were re-cut in Feb/Mar 2026, so 2026 is not comparable section by section with earlier years. 5. Daily arrivals, deliveries and complaints are synthetic. 6. Duplicate calibration is from Chicago; text similarity untested on Indian data. 7. Filling-point locations are assumed. 8. Under-served flags have no ground truth; they trigger checks, not conclusions. On slides use only numbers re-verified in `V-VERIFY_REVIEW.md`; never "rich areas take the tankers".

## 9. Starting from scratch: what is ported

New repository, new structure. These v1 modules are **copied with their tests** (reviewed and adapted, not imported): hash-chained ledger, OTP and geofence checks, OR-Tools allocation + OSRM routing with the road-leg cache, spam filter, intake pipeline, HMWSSB CSV importer. The verified `research-data/` files (D1-D4, D9, D12, D13 and the verification reports) are copied into `data/raw/` unchanged. Nothing else carries over.

## 10. Three-minute demo

1. Booking Equity: top 10% of sections take 68% (REAL). 2. Atlas + growth: who lacks water today (REAL/DERIVED). 3. Under-served flags with reasons (DERIVED). 4. Forecast + shortage warning for next summer, accuracy vs baseline (REAL backtest). 5. Mar-Jul 2025 replay (main run; 2023 kept for continuity): FCFS vs fair queue + scheduled supply, four PS11 measures (SIMULATION). 6. Officer: explanation for a booking, slider, approve with reason. 7. Telugu voice complaint → duplicate merged → outage. 8. Delivery: OTP, resident says "no" → Disputed, debt stays. 9. Next day the ward moves up; ledger shows why; tampering is caught.

## 11. Sources (verification status)

| Source | Status |
|---|---|
| Kontokosta & Hong (2021), *Sustainable Cities and Society*, "Bias in smart city governance" | Verified (NYU Scholars) |
| Liu, Bhandaram & Garg, "Quantifying spatial under-reporting disparities in resident crowdsourcing" (arXiv 2204.08620) | Method and Chicago Water Management data verified (R-P3); journal venue **not confirmed** |
| Agostini, Pierson & Garg (2024), AAAI 38(20):21888-21896, Bayesian spatial model for under-reporting; code github.com/gsagostini/networks_underreporting | Verified |
| Gao, Iravani & Sinclair (2026), "Sequential Fair Allocation and Routing in Nonprofit Operations", arXiv 2606.19278 | Verified |
| Obermeyer et al. (2019), *Science*; Shreedhar & Varghese (1996), deficit round robin; Grinsztajn et al. (2022), NeurIPS; Wickramasuriya et al. (2019), *JASA*; Holguín-Veras et al. (2013), *J. Operations Management*; Chow (1970); Angelopoulos et al. (2022), conformal risk control; Wachter et al. (2017); Riebler et al. (2016), BYM2; Jain, Chiu & Hawe (1984) | Standard references; titles and years checked in the 22 Sep audit (R-01 to R-10) or well established |
| Google Open Buildings 2.5D Temporal; WorldPop India 100 m; EC/JRC GHS-POP R2023A | Verified modelled spatial sources; use for sensitivity, not direct water-access measurement |
| Telangana GW Dept groundwater levels, National Water Data Portal (nwdp.nwic.gov.in) | Verified to exist (telemetry 2021-2025, quarterly manual) |
| AI4Bharat IndicConformer (github.com/AI4Bharat/IndicConformerASR; Hugging Face ai4bharat/indic-conformer-600m-multilingual), MIT, 22 languages incl. Telugu, Hindi, Urdu | Verified (R-P3) |
| Sphere 2018; JMP service ladder; CPHEEO 1999 Table 2.1 (secondary copy) | Verified / secondary |
| HMWSSB data (OpenCity), DataMeet wards, Census 2011 (OpenCity, NADA), Chicago 311 (v6vf-nfxy) | Verified and recomputed 2026-09-30 |
| GHMC/Telangana 2025-26 ward and corporation reorganisation notices | Verified; current machine-readable boundary/crosswalk still required |
| Reservoir levels (D15), HMWSSB notices (D14) | To verify during the build |


**E5 implementation/data status (2 October 2026).** Current E2 has zero location-validated Census-to-polygon joins, and no authoritative HMWSSB section-to-ward transfer was found. Tanker records are monthly section totals, not ward counts. The implemented E5 therefore fails closed: all 145 historical polygon rows are marked `DATA_REVIEW_REQUIRED`, with zero candidates and no model scores. Synthetic tests verify method behavior only; they are not Hyderabad findings.
