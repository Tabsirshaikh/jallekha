# JalLekha 2.0: P3 (Padmaja) detailed build plan

Owner: Padmaja (P3: forecast, access and trust backend). Repository: https://github.com/Tabsirshaikh/jallekha (nothing is pushed until Padmaja approves).
Feature documentation (updated after every task): `docs/P3_FEATURES.md`.
Sources: `docs/JALLEKHA_FINAL_SOLUTION.md`, `docs/features.csv`, `docs/TEAM_PLAN.md`.

> Paths and commands were checked against the S1 skeleton (`feat/s1-skeleton` @ `ecccf67`, PR #3) on 2026-10-02; review in `docs/reviews/S1-review.md`. Items still marked **(added by fix/s1-review)** do not exist in S1 yet and are created by the S1 fix branch after PR #3 merges.

---

## Part 0. The whole project in short

**What it is:** a fair, explainable system for sharing Hyderabad tanker water. HMWSSB delivers 99.95% of booked tankers, but booking is very unequal (Gini 0.78; top 10% of sections take 67.7% of bookings). JalLekha measures need from Census and building-growth data (not from requests), compares it with who actually gets water, and allocates by need, history and fairness, with every decision explained, contestable and logged.

**Data labels:** REAL, DERIVED, ASSUMED, SYNTHETIC, TO FETCH. Every derived column has a `_basis` column. Synthetic data is labelled on screen. No LLM is used in any scoring, allocation or explanation step.

**Three layers**

| Layer | Features | Who |
|---|---|---|
| A Evidence | F1 Atlas, F2 growth adjustment, F3 booking equity, F4 under-served detector, F5 forecast, F6 shortage warning | P1 (F1-F4), P3 (F5-F6) |
| B Allocation | F7 service models, F8 fair queue, F9 scheduled supply, F10 outage, F11 water debt, F19 sandbox | P2 |
| C Trust and access | F12 delivery proof, F13 duplicates, F14 intake + voice, F15 notices, F16 explanations + contest, F17 confidence, F18 ledger | P3 |

**Team**

| Person | Area |
|---|---|
| P1 | Data and evidence (E1-E6, D1, S2) |
| P2 | Allocation and simulation (A1-A8, S3) |
| **P3 (you)** | Forecast, delivery proof, duplicates, intake, notices, ledger, explanations, confidence, API (T1-T10, S1, R-P3) |
| P4 | Frontend, i18n, demo (U1-U10, X1, S4) |

**Four-week shape:** Week 1 research + skeleton + data + E1/E2 + A1/T1/U1 + API shapes agreed. Week 2 T2-T4. Week 3 T5-T8, screens on the real API. Week 4 T9-T10, demo rehearsal, release tag.

---

## Part 1. Working rules for the agent and approval protocol

Read this plan, `docs/TEAM_PLAN.md`, `docs/JALLEKHA_FINAL_SOLUTION.md` and `docs/features.csv` first, then work through the tasks in Part 2 order.

### 1.1 Rules (always apply)

1. Work only on the task named; touch only the files that task lists.
2. Commit locally on the task's feature branch. **Never run `git push`, open a PR or merge** until Padmaja writes "APPROVED TO PUSH".
3. No hand-typed data. Every derived column has a `_basis` column. Synthetic data is labelled.
4. Business logic in pure, unit-tested services; routers stay thin; every weight and threshold in the area's config file with its source.
5. No LLM in any scoring, allocation, explanation or confidence step.
6. Never commit secrets, `.env`, databases, `node_modules/` or virtual environments.
7. If another person's branch is missing, code against an interface/stub and say so.
8. If a test cannot reproduce a number from the documents, stop and report; never adjust the test to pass.
9. **After finishing each task, update `docs/P3_FEATURES.md`** (the feature-information file): fill the task's "Implementation notes", "Files", "Tests and results", "How to run" and status log with what was actually built. Commit it on the same branch.
10. Never kill processes by name (no `taskkill /IM`, no `pkill`). Stop a process only by its exact PID, and only one you started.

### 1.2 Approval protocol for every task

1. Work on branch `feat/<task>`, small local commits (`T1: what changed`).
2. Print: tests, lint, `git diff --stat`, the updated `docs/P3_FEATURES.md` section, and the PR description draft (what built, how tested with command + result, data used and its basis, what is not done).
3. Padmaja reads it and replies **APPROVED TO PUSH** or requests changes.
4. Only then: `git push -u origin <branch>`, open the PR on GitHub, set the `features.csv` row to `IN_REVIEW` with the PR link, request one reviewer.
5. After merge: set the row `DONE`, then `git checkout main && git pull origin main && git branch -d <branch>`.

---

## Part 2. Your task list at a glance

| Order | ID | Task | Branch | Needs (others) | Week |
|---|---|---|---|---|---|
| 0 | R-P3 | Research note | `research/p3` | none | 1 (days 1-2) |
| 1 | S1 review | Review/fix skeleton | `fix/s1-review` | none | 1 (day 1) |
| 2 | Review dependants | S3, S2, then others as they arrive | review only | | 1 |
| 3 | T1 | Duplicate engine | `feat/t1-dedup` | S1, R-P3 | 1-2 |
| 4 | T2 | Forecast + backtest | `feat/t2-forecast` | S2, D1 | 2 |
| 5 | T3 | Delivery proof | `feat/t3-delivery` | S3 | 2 |
| 6 | T4 | Intake + voice | `feat/t4-intake` | S3, T1 | 2 |
| 7 | T5 | Notice feed | `feat/t5-notices` | A5 | 3 |
| 8 | T6 | Ledger wiring | `feat/t6-ledger` | S3 | 3 |
| 9 | T7 | Explanations + contest | `feat/t7-explain` | E2, A3 | 3 |
| 10 | T8 | Shortage warning | `feat/t8-shortage` | T2, D1 | 3 |
| 11 | T9 | Confidence gate | `feat/t9-confidence` | E2, A8 | 4 |
| 12 | T10 | API for all screens | `feat/t10-api` | E2, T2, A7, A8 | 3-4 (shapes in week 1) |

Notes on order:
- Feature tasks start only after `docs/research/P3.md` is merged.
- T6 (ledger) is used by T3, T5, T7. Build the thin ledger interface early (see T3 step 1) so T6 only wires and hardens it.
- T10 depends on late tasks, but the **JSON shapes must be agreed with P4 in week 1**. Do this as a docs-only PR (see Part 7) so P4 can build on fixtures.

---

## Part 3. First: review S1 (skeleton) and everything that depends on it

`features.csv` lists S1 as **your** task ("Everyone waits for this"). A teammate has already built it, so your job is to review it against S1's done-when and your T-tasks' needs, fix gaps, and take responsibility for its row.

### 3.1 Find and check out the S1 branch

```bash
git fetch origin
git branch -r | grep -i s1            # expect origin/feat/s1-skeleton
git log origin/main --oneline -n 10   # is S1 already merged?
```

- **If S1 is already merged into `main`:** read it from `main`, and put fixes on a new branch `fix/s1-review` from `main`.
- **If it is still an open branch/PR:** `git checkout -b review/s1 origin/feat/s1-skeleton`. Leave review comments on the PR on GitHub (after your approval), and ask the author to fix, or make small fixes yourself on a branch off his branch only if he agrees.

### 3.2 Run it exactly as TEAM_PLAN says

```bash
python tasks.py setup
python tasks.py test
python tasks.py lint
```

S1 done-when: CI green on an empty test; `tasks.py setup/test/lint` work **on Windows**. Test on a clean clone, not only in his folder.

### 3.3 S1 review checklist (tick each one; write findings in `docs/reviews/S1-review.md` locally first)

**Repo and process**
- [ ] `docs/` contains `JALLEKHA_FINAL_SOLUTION.md`, `features.csv`, `TEAM_PLAN.md`, and a place for `docs/research/` and `docs/reviews/`.
- [ ] `.gitignore` covers `.env`, `*.db`, `*.sqlite`, `node_modules/`, `.venv/`, `__pycache__/`, build output, model weights.
- [ ] `.env.example` exists (no secrets) with at least `DATABASE_URL`, `LEDGER_HMAC_KEY`, `OSRM_URL`, `ASR_MODE`, `SMS_PROVIDER`.
- [ ] Branch protection on `main` (no direct push, one approving review) and CI required.
- [ ] CI workflow runs tests and lint on push/PR, on Linux at least; Windows if feasible.

**Backend**
- [ ] FastAPI app starts; `/health` returns OK; routers folder exists and routers are empty/thin.
- [ ] Services folder separate from routers; pure functions importable without a database.
- [ ] SQLAlchemy set up with SQLite locally; **one table per model file**; migrations (Alembic) or a documented create-all approach.
- [ ] Test runner (pytest) configured, one empty test passes; lint (ruff or flake8) configured.
- [ ] **Config has one section per area**: `config/evidence.py`, `config/allocation.py`, and for you **`config/forecast.py`, `config/trust.py`** (dedup, delivery, confidence, ledger). Each value has a source comment. If your two files are missing, add them in the S1 fix.
- [ ] Settings read from environment, secrets never hard-coded.

**Frontend**
- [ ] React + TypeScript builds (`npm run build`), lint passes, a placeholder test passes.
- [ ] API client reads base URL from env; fixtures folder exists (for P4's fixtures-first approach).

**tasks.py**
- [ ] Commands: `setup`, `test`, `lint` work on Windows PowerShell and on Linux/macOS; error messages are clear when Python/Node is missing; it does not rely on `bash`-only syntax.
- [ ] Optional but helpful: `run-api`, `run-frontend`, `run-all`.

**Things your T-tasks need from S1**
- [ ] A place for data: `data/raw`, `data/verification`, `data/derived`, `data/synthetic` (synthetic kept separate).
- [ ] A way to optionally install heavy ML dependencies (`NeMo`/IndicConformer, `sentence-transformers`, `lightgbm`) as **extras** so `setup` stays quick: e.g. `requirements-ml.txt`. Core `setup` must not need a GPU.
- [ ] Time handling and IDs: UTC timestamps; UUID or ULID primary keys for offline-sync items.
- [ ] Logging and error-response shape defined once.

### 3.4 Fix what is wrong

For each failed item: smallest fix, own commit `S1: <what>`, on `fix/s1-review`. Do not restructure what others already depend on; if a rename would break P1/P2/P4 branches, ask first. Then follow the approval protocol (1.2) and PR it. Update the `features.csv` S1 row: status and notes ("reviewed by P3, fixes in PR #..").

### 3.5 Review dependants (in this order)

Everything of yours depends on these. Review each when its PR exists (`git fetch`, check out, run tests; review comments after your approval):

| Branch | Why you review it | What to check |
|---|---|---|
| `feat/s3-port` (P2) | **T3, T4, T6 depend on it** (ledger, OTP, geofence, spam, intake pipeline, CSV importer) | Ported tests pass; ledger is SHA-256 chain with HMAC; canonical serialisation; OTP expiry/attempt limits; geofence 150 m distance function is correct (haversine, metres); no import from the old repo; no hand-typed data |
| `feat/s2-data` (P1) | **T2 depends on it** (D1 bookings, verification files) | Checksums recorded; `SOURCES.md` present; raw files unedited; D1 has 4,398 rows, Dec 2022 empty |
| `feat/d1-fetch` (P1) | T2, T8 need groundwater (D7), weather, boundaries | Retrieval log (URL/date/licence); machine-readable; mandal identifiers present so sections can be mapped |
| `feat/e2-evidence` (P1) | T7, T9, T10 depend on it | `_basis` columns; Census empty when join fails; data-quality flag column is usable by T9 |
| `feat/a3-queue` (P2) | T7 explanations use `order_bookings` | Function signature stable and documented (inputs, tiers, DRR state) |
| `feat/a5-outage` (P2) | T5 depends on it | How an outage event is created (function + fields: area, start, end, source) |
| `feat/a7-planner`, `feat/a8-sandbox` (P2) | T9, T10 depend on them | Replay output format (per day: plan, inputs, quality signals) |
| `feat/u*` (P4) | Your API shapes must match | Fixtures match the agreed shapes |

Put your review result per branch in a comment (approve, or list of fixes). Do not approve what fails tests.

### 3.6 After the review

Update this file's paths and commands (marked "confirm after S1 review"), then start R-P3.

---

## Part 4. R-P3: research before building (2 days, `research/p3`)

Output: `docs/research/P3.md`, **max 2 pages**, for each feature (F5, F6, F12-F18): sources checked (link + date), what you found, decision **keep / change / add** with reason. Every claim has a link. "No better source found" with the list checked is valid. Open a PR; one teammate and the owner review; build only after merge.

What to check, per feature:

| Feature | Research questions | Where to look |
|---|---|---|
| F5 forecast | Which methods work on **very short monthly series** (about 25 usable months)? Is gradient boosting realistic or will seasonal naive win? Conformal intervals for time series (split conformal, EnbPI, adaptive conformal) | statsforecast, sktime, Darts, MAPIE docs; Hyndman FPP3 (hierarchical, MinT); Wickramasuriya et al. 2019; Grinsztajn et al. 2022; arXiv/Scholar |
| F5/F6 covariates | Groundwater levels: Telangana GW Dept via National Water Data Portal. Is a CSV downloadable by code? Station density for Hyderabad mandals, date range, licence. Weather: Open-Meteo history API | nwdp.nwic.gov.in, India-WRIS, data.gov.in, open-meteo.com |
| F6 / Q2 reservoir | Is any **machine-readable** reservoir level source verified (CWC, India-WRIS)? If not, state "build without" | CWC bulletins, India-WRIS |
| F13 duplicates | Multilingual sentence embeddings for Telugu/Urdu/Hindi/English (LaBSE, multilingual-e5, IndicSBERT); evidence on code-mixed text; check Liu et al. 2023 and Chicago 311 numbers (95% within 106 m etc.) | Hugging Face, arXiv 2204.08620, Chicago data portal v6vf-nfxy |
| F14 intake/voice | **AI4Bharat IndicConformer**: which languages exactly? Confirm **Telugu and Hindi**, and check **Urdu** coverage (the plan lists Urdu as a UI language). Model size, CPU speed, licence (MIT), NeMo installation difficulty on Windows | github.com/AI4Bharat/IndicConformerASR, Hugging Face |
| F12 delivery proof | OTP + GPS tanker delivery in Bengaluru (BWSSB), Delhi GPS tankers; how disputes are handled | news, BWSSB/DJB sites, RTI replies |
| F15 notices | Where HMWSSB publishes interruption notices; machine-readable? | hmwssb.telangana.gov.in, press releases, X/Twitter |
| F16 explanations | Counterfactual explanations (Wachter et al. 2017), contest/appeal practice in public algorithms | papers, existing government systems |
| F17 confidence | Defer-to-human thresholds, conformal risk control (Angelopoulos et al. 2022), Chow 1970 | arXiv |
| F18 ledger | Hash chain + HMAC design; failure modes (key rotation, gaps) | standard references |

Also **verify each cited paper says what the solution claims** (e.g., Gao et al. arXiv 2606.19278 and Liu et al. 2023) and record any mismatch.

Agent prompt: "Do R-P3 research for the features listed; fetch sources, summarise in docs/research/P3.md in under 2 pages with links and keep/change/add decisions. Do not write feature code."

---

## Part 5. Your tasks in detail (T1-T10)

Layout used below (checked against S1 on 2026-10-02). Services are pure and tested; routers are thin.

```
backend/app/config/trust.py                 # exists in S1 (dedup, delivery, confidence, ledger values go here)
backend/app/config/forecast.py              # (added by fix/s1-review)
backend/app/services/{dedup,forecast,delivery,intake,notices,ledger,explain,shortage,confidence}.py   # (added by fix/s1-review: services/ package)
backend/app/models/<one table per file>.py  # (added by fix/s1-review: models/ package + DB base)
backend/app/routers/<area>.py               # (added by fix/s1-review: routers/ package)
backend/tests/services/test_<name>.py       # backend/tests exists in S1
scripts/<area>/<script>.py                  # pattern set by S2 (scripts/data/); P3 uses scripts/trust/, scripts/forecast/
data/raw/ , data/verification/              # exist in S2
data/derived/ , data/synthetic/             # (added by fix/s1-review)
```

All commands run from the repo root. `python tasks.py setup` creates the virtual environment at **`.venv/` in the repo root** (not in `backend/`); run single tests with `.venv\Scripts\python -m pytest <path>` on Windows or `.venv/bin/python -m pytest <path>` on macOS/Linux.

Common rules for every task:
- Work on a branch named in `features.csv`; **only touch the task's files**.
- Write tests first for the done-when item; services have unit tests.
- Every number in config has a source comment; every derived output column has a `_basis` column.
- Finish: `python tasks.py test` and `python tasks.py lint` pass → approval protocol (1.2).

---

### T1: Duplicate engine (F13), `feat/t1-dedup`

**Needs:** S1, R-P3. **Done when:** tests prove a 5-day-apart leak merges, a 5-day-apart no-water does not, and a 150 m neighbour does not.

**Rules to implement (from the solution):**
- Same household id matches first.
- Radius 100 m. Window 48 h for `no_water`, `tanker_missed`, `dirty_water`; 7 days for `leak` and `other`.
- Text similarity (multilingual embeddings, e.g. LaBSE) is a **secondary** signal, optional, marked "untested on Indian data".
- Duplicate **rate per area** is stored as a reporting-activity signal (not only removal).

**Steps**
1. Config in `config/trust.py`: `DEDUP_RADIUS_M=100`, `WINDOW_HOURS={no_water:48, tanker_missed:48, dirty_water:48, leak:168, other:168}`, source comments (Chicago calibration).
2. Models: `complaint.py` (id, category, lat, lon, household_id, text, language, created_at, source channel, basis), `duplicate_link.py` (child id, parent id, rule that matched, score).
3. Service `dedup.py`: `haversine_m`, `find_parent(new, existing)` (household rule → location+time rule → optional text signal), cluster handling with union-find, efficient neighbour search (grid index or BallTree with haversine).
4. `duplicate_rate_by_area(complaints, area_key, period)` → table with `_basis`.
5. Calibration script `scripts/calibrate_dedup.py` on D13 (Chicago, 31,098 rows, 4,994 duplicates, parent ids): reproduce 95% within about 106 m, no-water 90% within about 20 h, leaks 90% within about 9 days; and linked share: 100 m/48 h about 71%, 300 m/7 d about 88%. Write results to `data/derived/dedup_calibration.csv` (basis DERIVED). If numbers differ, report, do not tune tests.
6. Optional embedding adapter behind an interface; default off; falls back cleanly when the model is missing.
7. Tests: the three done-when cases, household-first, boundary at exactly 100 m, window boundary, different category not merged, clustering chain, duplicate rate.

**Run:** `python tasks.py test` (or `.venv\Scripts\python -m pytest backend/tests/services/test_dedup.py`); calibration: `.venv\Scripts\python scripts/trust/calibrate_dedup.py`. **Note (S2 review):** D13 Chicago extract is not in the repo; calibration needs a fresh, logged download (decide with P1/owner).

---

### T2: Forecast + backtest (F5), `feat/t2-forecast`

**Needs:** S2, D1 (P1). **Done when:** seasonal naive reproduces **21.9% city MAPE / 35.1% section WAPE within 0.1 percentage point**.

**Steps**
1. Find the exact protocol that produced 21.9%/35.1% in `data/verification/` (V-VERIFY_REVIEW or notes): which months were held out, how Dec 2022 (empty) is handled (treat as **missing, not zero**), MAPE vs WAPE definitions. Write the test first. If you cannot reproduce it, stop and ask P1/owner.
2. Data loader from D1 (4,398 rows; 201 sections; Jan 2022-Feb 2024). Config in `config/forecast.py`: horizon 12, rolling-origin settings, trips/day and fleet (ASSUMED, labelled; 577 early 2024, 1,123 in 2026 from news).
3. Models: (a) seasonal naive, (b) seasonal naive × year-on-year growth, (c) gradient boosting (month, lag-12, trend, weather D8, groundwater D7). With about 25 usable months, expect the baseline to be hard to beat.
4. Hierarchical reconciliation section → city (bottom-up first; MinT if research supports it).
5. Split-conformal intervals from rolling-origin residuals; measure **empirical coverage**.
6. Rolling-origin backtest report: MAPE, WAPE, coverage per model → `data/derived/forecast_backtest.csv`. **Only a model that beats the baseline is used; if none does, say so** in the report and use the baseline.
7. Capacity planner: trips needed vs fleet × trips/day, labelled ASSUMED.
8. Output forecast table (section, month, point, lower, upper, model, `_basis`).
9. Tests: baseline numbers, no leakage (train data strictly before forecast origin), reconciliation sums to city, coverage computed correctly.

**Run:** `.venv\Scripts\python scripts/forecast/run_backtest.py` then open `data/derived/forecast_backtest.csv`. **Note (S2 review):** `V-VERIFY_REVIEW.md` is not in the repo, so the 21.9% / 35.1% protocol must come from P1/owner before the test is written (rule 8). D1 in S2: 26 monthly files in `data/raw/hmwssb_tankers/`, columns `year, month, division, section, noofbookings, delivered`; 4,398 rows; `2022-12.csv` header only.

---

### T3: Delivery proof (F12), `feat/t3-delivery`

**Needs:** S3 (ported OTP + geofence + ledger). **Done when:** outcome table exact; silence counts for nothing; ledger entries written.

**Rules:** OTP to one of 2-3 registered representatives per stop; server-side geofence 150 m; then 3-5 random residents get "Did you get water? 1 yes / 2 no".

| OTP | Residents | Outcome |
|---|---|---|
| verified | mostly yes | **Confirmed** |
| verified | mostly no | **Disputed** |
| not verified | mostly yes | **Unconfirmed** |
| not verified | mostly no | **Failed** |

**Steps**
1. Define a small `LedgerPort` interface (`append(entry_type, payload, actor)`), backed by the S3 ledger; this keeps T3 independent of T6.
2. Models: `delivery.py`, `representative.py`, `resident_response.py`, `delivery_outcome.py`.
3. Service `delivery.py`: `start_delivery`, `request_otp`, `verify_otp` (reuse S3, expiry and attempt limit), `check_geofence` (150 m from config), `sample_residents` (seeded random 3-5), `record_response`, `compute_outcome`.
4. **Decision to confirm with owner and write in config + test:** what "mostly" means (strictly more yes than no) and what happens with ties or **zero replies** (silence counts for nothing, so zero replies cannot decide; propose: outcome stays pending until the reply window closes, then OTP-only outcome is "Unconfirmed" if OTP verified with no replies, and "Failed" if neither). Do not guess silently.
5. SMS sender abstraction with a fake provider for tests/demo (messages in the resident's language via template keys).
6. Ledger entry for each state change and the final outcome; expose the outcome event for P2's water debt (A6: only **Confirmed** counts).
7. Tests: all four outcomes, ties, zero replies, geofence 149 m vs 151 m, expired OTP, wrong OTP attempts, silence ignored, ledger entry created.

---

### T4: Unified intake + voice (F14), `feat/t4-intake`

**Needs:** S3 (intake pipeline, spam filter), T1. **Done when:** a voice note works with the offline fallback; tests pass.

**Channels:** app (PWA), SMS, missed call/IVR, voice note, field worker (reporting for others), offline sync.

**Steps**
1. Common `IntakeMessage` → normalise → spam filter (S3) → classify category (keyword lists per language te/hi/ur/en in config; deterministic, no LLM) → create `Complaint` → T1 dedup → outcome (new/merged).
2. Adapters: SMS webhook (provider-agnostic payload parser), missed call (phone number + time; ask-back SMS), app JSON, field-worker JSON (`reported_for` household/location, `reporter_id`).
3. **Offline sync:** client-generated UUID per item (`client_id`) as idempotency key; batch endpoint accepts a list; duplicates by `client_id` ignored; returns per-item status; client timestamp kept alongside server timestamp.
4. **Voice:** ASR runs server-side. Interface `Transcriber`; implementation `IndicConformerTranscriber` (optional extra, `requirements-ml.txt`; Telugu and Hindi, Urdu per R-P3 findings); `FallbackTranscriber` that stores the audio and creates a "needs human transcription" complaint, so the report is never lost. `ASR_MODE=fallback|indicconformer` in env.
5. Language detection by script (Telugu/Devanagari/Arabic-script/Latin) as a cheap first step.
6. Store raw channel, language and transcript confidence.
7. Tests: each channel creates a complaint; spam rejected; same `client_id` twice = one item; voice with ASR unavailable → fallback record; Telugu/Hindi/Urdu keyword categorisation; field-worker report links to household.

---

### T5: Supply-notice feed (F15), `feat/t5-notices`

**Needs:** A5 (outage creation, P2). **Done when:** a notice creates an outage with area and hours.

**Steps**
1. Model `supply_notice.py` (source, raw text, area names, sections/wards mapped, start, end, hours, entered_by, basis REAL).
2. Entry paths: officer form/API (always works) and a parser for machine-readable text (only parse what is published; if D14 shows no machine-readable feed, manual entry is the result, and say so).
3. Area mapping from names to sections/wards using the area tables from P1 (fuzzy match with confidence; unmatched areas flagged for officer).
4. On save: call P2's outage-creation function (A5) with area + hours; if A5 is not merged, code against an interface and test with a fake.
5. Resident alerts: templated messages keyed per language (te/ur/hi/en); strings agreed with P4's i18n.
6. Ledger entry for notice and outage creation.
7. Tests: notice with area and hours → outage event; duplicate notice not duplicated; unmatched area flagged; alert text per language.

---

### T6: Ledger wiring (F18), `feat/t6-ledger`

**Needs:** S3. **Done when:** a tamper test catches an edited entry.

**Steps**
1. Review the ported ledger: SHA-256 hash chain; each entry hashes the previous hash + canonical JSON of the payload; HMAC with `LEDGER_HMAC_KEY` from env; sequence number; actor; timestamp.
2. Entry types enum: `plan`, `override`, `weights`, `delivery_outcome`, `debt`, `contest`, `contest_reply`, `notice`, `outage`, `field_check`.
3. Single service `ledger.record(entry_type, payload, actor)` used by every other module (T3, T5, T7, A-tasks); concurrency-safe (transaction + unique sequence).
4. `verify_chain()` returns first broken index and reason (hash mismatch, HMAC mismatch, gap).
5. Router: read-only list + verify endpoint; no update/delete endpoints.
6. Wire the allocation-affecting events from other areas through the same call (agree function names with P2 in the PR; do not edit their files; they call yours).
7. Tests: edit a payload in the DB → `verify_chain` fails at that entry; delete an entry → gap detected; wrong HMAC key → fail; reorder → fail; concurrent appends keep a valid chain.
8. Wording in docs: "tamper-evident, not blockchain".

---

### T7: Explanations + contest (F16), `feat/t7-explain`

**Needs:** E2 (P1 ward table), A3 (P2 `order_bookings`). **Done when:** a contest reply requires a reason; both go in the ledger.

**Steps**
1. Ward explanation: tier, need components (WAD, CAD, hardship, facilities, with `_basis` and "Census 2011" label), debt, waiting time, join-quality flag.
2. Booking explanation: tier, rank position, DRR entitlement, caps applied, waiting time, debt.
3. **Counterfactual:** the smallest change that moves the rank: re-run the A3 ordering with modified inputs (e.g., debt +X litres, tier changed, wait +N days) and search the smallest change that moves up by one place; output as plain text from templates. No LLM.
4. Templates per language keys (te/ur/hi/en); text built from real numbers only.
5. Contest model: who (resident or councillor), target (ward/booking), reason, status; officer reply **must contain a non-empty reason** (validation in service, not only UI); both entries go to the ledger.
6. Tests: explanation values equal source values; counterfactual changes rank by exactly the claimed amount; contest reply without a reason rejected; ledger has contest and reply; works when Census join failed (shows "no Census data", no invented numbers).

---

### T8: Shortage early warning (F6), `feat/t8-shortage`

**Needs:** T2, D1. **Done when:** a risk list 1-3 months ahead with reasons.

**Steps**
1. Per section and month: forecast demand (T2) vs assumed capacity (fleet × trips/day, ASSUMED).
2. Groundwater anomaly per mandal: current level vs the mandal's own seasonal baseline (z-score or percentile; thresholds in `config/forecast.py`); map section → mandal using the P1 table.
3. Risk level (low/medium/high) from stated rules; reasons as text from real numbers ("forecast 1.3× capacity; groundwater 1.8 SD below usual").
4. Reservoir levels behind a feature flag, **off** unless Q2 is approved and a machine-readable source is verified.
5. Output table with `_basis`; section locations with low accuracy flagged.
6. Tests: threshold boundaries; missing groundwater data → reason says so, no fake value; flag off → no reservoir input.

---

### T9: Confidence gate (F17), `feat/t9-confidence`

**Needs:** E2 (P1), A8 (P2 replay). **Done when:** low confidence cannot auto-commit.

**Signals:** Census join quality, data age, section-location uncertainty (only 159 of 201 geocoded; DERIVED), forecast interval width (T2), evidence age.

**Steps**
1. Score each signal 0-1 with documented rules; combine transparently (e.g., minimum or weighted mean, in config; the reason lists which signal is weakest).
2. Gate: `confidence < threshold` → ward stays in the plan but flagged **needs officer "checked"**.
3. `commit_plan` refuses to auto-commit flagged wards; officer "checked" clears it with a reason and a ledger entry.
4. **Threshold selection on the replay (A8):** for each replay day compare the plan under full information with the plan under degraded signals; choose the threshold so that at least a stated share (config, e.g. 90%, to be decided with owner) of auto-committed decisions match the full-information plan; write `data/derived/confidence_calibration.csv` (SIMULATION).
5. Until A8 exists, use a clearly labelled **provisional** threshold; replace it when A8 is merged.
6. Tests: each signal's boundary; low confidence cannot auto-commit; officer-checked path; calibration picks the threshold satisfying the target on a tiny fixture.

---

### T10: API for all screens, `feat/t10-api`

**Needs:** E2, T2, A7, A8. **Done when:** API tests pass and shapes match P4's fixtures.

**Steps**
1. Contract first (week 1): `docs/api_shapes.md` + JSON examples in the frontend fixtures folder, agreed with P4 (Part 7).
2. Endpoints (thin routers calling services): atlas, equity, under-served + field-check list, coverage GeoJSON, forecast, shortage, plan (queue/schedule/outage), approve (requires reason), explain (ward/booking), contest + reply, ledger list/verify, delivery (OTP, outcome), intake (all channels, sync batch), ward report card + SMS summary, impact (with REAL/DERIVED/SIMULATION badge per number).
3. Roles: officer, driver, resident (simple token auth; keep a local dev token).
4. Consistent error shape; pagination; CORS for the frontend; OpenAPI exported to `docs/openapi.json`.
5. Every response that carries a number includes its `basis`.
6. Contract tests: validate responses against the JSON schemas that match P4's fixtures.
7. Tests: each endpoint; auth failures; approval without reason rejected.

---

## Part 6. How to run everything manually (for all teammates)

Read this once. Commands were checked against S1 on 2026-10-02. `python tasks.py` with no argument prints what the skeleton offers: `setup|test|lint|check`.

### 6.1 Prerequisites (Windows, macOS or Linux)

| Tool | Version (from S1) | Check |
|---|---|---|
| Git | any recent | `git --version` |
| Python | 3.11 or newer (CI uses 3.12) | `python --version` |
| Node.js + npm | **22.12 or newer** (Vitest 5 needs it; CI uses 22) | `node --version` |
| (optional) Docker | for PostgreSQL/PostGIS and OSRM | `docker --version` |

### 6.2 Get the code and set it up

```bash
git clone https://github.com/Tabsirshaikh/jallekha.git
cd jallekha
python tasks.py setup      # backend virtual environment + frontend packages
python tasks.py test       # runs backend and frontend tests
python tasks.py lint       # runs linters
```

Copy `.env.example` to `.env` and fill the values (never commit `.env`). For local use, any random string works for `LEDGER_HMAC_KEY`. **(`.env.example` added by fix/s1-review; S1 has none yet.)**

### 6.3 Start the app by hand

S1's `tasks.py` has no `run` commands. From the repo root:

```bash
# Backend (terminal 1), from the repo root
.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --port 8000     # Windows
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --port 8000         # macOS/Linux
# open http://localhost:8000/docs   (interactive API) and /health   (checked: both return 200)

# Frontend (terminal 2), from the repo root
npm run dev --prefix frontend
# open the address printed (usually http://localhost:5173)
```

### 6.4 Run each P3 part by hand

From the repo root. `PY` below means `.venv\Scripts\python` on Windows and `.venv/bin/python` on macOS/Linux.

```bash
# T1 duplicate engine
PY -m pytest backend/tests/services/test_dedup.py
PY scripts/trust/calibrate_dedup.py          # writes data/derived/dedup_calibration.csv

# T2 forecast and backtest
PY -m pytest backend/tests/services/test_forecast.py
PY scripts/forecast/run_backtest.py          # writes data/derived/forecast_backtest.csv

# T3 delivery proof
PY -m pytest backend/tests/services/test_delivery.py

# T4 intake and voice (fallback mode needs no ML install)
PY -m pytest backend/tests/services/test_intake.py
# Optional real speech recognition (ML extra added by fix/s1-review):
PY -m pip install -e "./backend[ml]"
# Windows PowerShell:  $env:ASR_MODE="indicconformer"; PY -m uvicorn app.main:app --app-dir backend --port 8000
# macOS/Linux:         ASR_MODE=indicconformer PY -m uvicorn app.main:app --app-dir backend --port 8000

# T5 notices
PY -m pytest backend/tests/services/test_notices.py

# T6 ledger
PY -m pytest backend/tests/services/test_ledger.py
# After the API exists: open http://localhost:8000/docs and call the ledger verify endpoint

# T7 explanations + contest
PY -m pytest backend/tests/services/test_explain.py

# T8 shortage warning
PY -m pytest backend/tests/services/test_shortage.py

# T9 confidence gate
PY -m pytest backend/tests/services/test_confidence.py

# T10 API
PY -m pytest backend/tests/api
```

### 6.5 Review someone's branch on your machine

```bash
git fetch origin
git checkout feat/<their-branch>
python tasks.py setup
python tasks.py test
python tasks.py lint
git checkout main                                   # when finished
```

Reviewer checklist (from TEAM_PLAN): done-when in `features.csv` is met; tests exist and pass; no hand-typed data; only the task's files changed; synthetic data labelled.

### 6.6 Everyday git (everyone)

```bash
git checkout main && git pull origin main
git checkout -b feat/<task-id>-<short-name>
git add <only the files you changed>
git commit -m "<task-id>: what changed"
git push -u origin feat/<task-id>-<short-name>      # then open a PR into main
git fetch origin && git merge origin/main           # every morning
```

Never push to `main`, force-push a shared branch, merge your own PR without a review, or commit secrets, `.env`, databases, `node_modules/` or virtual environments.

### 6.7 Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found on Windows | Install Python from python.org with "Add to PATH", or try `py tasks.py setup` |
| PowerShell blocks the venv script | Not needed if you call `.venv\Scripts\python` directly; otherwise `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `vitest` fails on start | Node older than 22.12; upgrade Node |
| Port already in use | Start on another port: `--port 8001` and set the frontend API URL |
| IndicConformer install fails | Use `ASR_MODE=fallback`; voice notes are stored for a human |
| Tests fail only on your machine | Delete the venv, run `python tasks.py setup` again, run on a clean clone |

---

## Part 7. Week 1 coordination actions

1. **With P4:** a docs-only PR with API JSON shapes (`docs/api_shapes.md` + example JSON) for the screens: plan, explanation, contest, forecast, shortage, delivery outcomes, intake, ledger verify, impact badges. Ask the owner to add it as a row or note in `features.csv` (it is not listed today).
2. **With P2:** agree the function names for `ledger.record(...)`, the outage-creation call used by T5, and the `order_bookings` signature used by T7.
3. **With P1:** confirm the E2 column names for join quality and data age (T9), and the section → mandal mapping (T2, T8).
4. **With the owner:** confirm the rule for ties/zero replies in delivery proof (T3), the target match share for the confidence threshold (T9), and Q2 (reservoirs).

---

## Part 8. Definition of done for each task (checklist to paste in every PR)

- [ ] Done-when in `features.csv` is met (quote it)
- [ ] `python tasks.py test` and `python tasks.py lint` pass
- [ ] Unit tests for every service function; routers thin
- [ ] Config values have sources; derived columns have `_basis`
- [ ] No hand-typed data; synthetic data labelled
- [ ] Only the task's files changed
- [ ] `features.csv` row set to `IN_REVIEW` with PR link
- [ ] `docs/P3_FEATURES.md` section for this task updated
- [ ] Padmaja wrote "APPROVED TO PUSH" before the push
