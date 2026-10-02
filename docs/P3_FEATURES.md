# P3 features: forecast, access and trust backend

Owner: P3. One section per task, updated at the end of each task on that task's branch. Sources: `docs/JALLEKHA_FINAL_SOLUTION.md`, `docs/features.csv`, `docs/research/P3.md`.

| ID | Feature | Branch | Status |
|---|---|---|---|
| R-P3 | Research note | `research/p3` | DONE ([PR #7](https://github.com/Tabsirshaikh/jallekha/pull/7) merged) |
| S1 fix | Skeleton gaps T1-T10 need | `fix/s1-review` | DONE ([PR #15](https://github.com/Tabsirshaikh/jallekha/pull/15) merged) |
| T1 | F13 duplicate engine | `feat/t1-dedup` | DONE ([PR #19](https://github.com/Tabsirshaikh/jallekha/pull/19) merged); calibration run waits for D13 |
| T2 | F5 forecast + backtest | `feat/t2-forecast` | Blocked: 21.9% / 35.1% protocol (`V-VERIFY_REVIEW.md`) missing |
| T3 | F12 delivery proof | `feat/t3-delivery` | Blocked: S3 not started |
| T4 | F14 intake + voice | `feat/t4-intake` | Blocked: S3, T1 |
| T5 | F15 notices | `feat/t5-notices` | Blocked: A5 |
| T6 | F18 ledger | `feat/t6-ledger` | Blocked: S3 |
| T7 | F16 explanations + contest | `feat/t7-explain` | Blocked: E2, A3 |
| T8 | F6 shortage warning | `feat/t8-shortage` | Blocked: T2, D1 |
| T9 | F17 confidence gate | `feat/t9-confidence` | Blocked: E2, A8 |
| T10 | API for all screens | `feat/t10-api` | Shapes to agree with P4 in week 1 |

---

## R-P3: research note

- **Implementation notes:** Research only, no feature code. Decisions per feature (keep / change / add) are in `docs/research/P3.md`. Main changes proposed: F14 adds Urdu ASR and drops NeMo (IndicConformer runs on `transformers` + ONNX); F5 pools scaled conformal residuals across sections (80/90% intervals) and uses one global GBM; Chronos-2 is a backtest-only candidate, owner decision pending (allowed only if it clearly beats seasonal naive and the owner confirms it fits the no-LLM rule); D7 groundwater source is India-WRIS / CGWB; F18 adds a daily published head hash, `key_id` per entry and gap detection. Liu et al.: method and Chicago Water Management data confirmed; venue not confirmed.
- **Files:** `docs/research/P3.md`, `docs/P3_FEATURES.md`, `docs/P3_BUILD_PLAN.md` (plan + process-safety rule), `docs/JALLEKHA_FINAL_SOLUTION.md` (proposed edits, separate commit), `docs/features.csv` (R-P3 row only).
- **Tests and results:** none (docs only; `main` has no `tasks.py` until S1 merges). Every claim carries a link; [R]/[S] marks read vs search-summary sources.
- **How to run:** n/a.
- **Open questions:** Chronos-2 vs no-LLM rule (owner); D13 Chicago fresh pull (P1/owner); 21.9%/35.1% method (P1/owner).
- **Status log:** 2026-10-01 draft; 2026-10-02 citation check, trimmed to 2 pages, Liu venue marked not confirmed, Chronos-2 marked owner decision pending, solution-doc edits split into their own commit, PR opened; PR #7 merged into `main`, status DONE.

## S1: skeleton review fixes

- **Implementation notes:** S1 (PR #3) met its done-when; the P3 review (`docs/reviews/S1-review.md`, local) listed what T1-T10 still need. Branch `fix/s1-review` from `main` after PR #3 merged, one `S1: <what>` commit per item. Nothing that other areas depend on was restructured; `/health` keeps its exact response.
  1. `.env.example`: `DATABASE_URL`, `LEDGER_HMAC_KEY`, `OSRM_URL` (listed for P2, not read yet), `ASR_MODE`, `SMS_PROVIDER`. No secrets.
  2. Settings from the environment (`config/env.py`): `DATABASE_URL` (default SQLite `jallekha.db` anchored to the repo root, no longer the working directory), `LEDGER_HMAC_KEY` (no default, hidden from `repr`), `ASR_MODE` (`fallback` / `indicconformer`), `SMS_PROVIDER` (`fake`); invalid values are rejected.
  3. `services/` package: already on `main` (added by P1 with E5/E6); nothing to do.
  4. `models/` package: `Base`, `IdTimestampMixin` (UUID4 string ids, timezone-aware UTC `created_at`), `new_id`, `utcnow`; `app/db.py` with `make_engine`, `make_session_factory`, `create_all` (no migrations yet). One table per model file.
  5. `routers/` package; `/health` moved to `routers/system.py`.
  6. `config/forecast.py`: horizon 12, seasonal period 12, baseline 21.9% / 35.1% with 0.1 pp tolerance, interval levels 80/90%, fleet 577 / 1,123 (ASSUMED). Trips per tanker per day left out: no source yet (T2 adds it).
  7. Optional `ml` extra in `backend/pyproject.toml` (sentence-transformers, lightgbm, hierarchicalforecast, transformers, onnxruntime, onnx, torch 2.11.0 + torchaudio 2.11.0). Not installed by `tasks.py setup` or CI.
  8. `data/synthetic/README.md` with the SYNTHETIC labelling rules (`data/derived/` already existed).
  9. `.gitignore`: model weights (`/models/`, `*.nemo`, `*.onnx`, `*.pt`, `*.pth`, `*.ckpt`, `*.safetensors`); `backend/app/models/` stays tracked.
  10. One error shape for every endpoint (`app/errors.py`): `{"error": {"code", "message", "details"}}` for HTTP errors, validation errors (422, `validation_error`) and unexpected errors (500, `internal_error`, no internals leaked).
- **Files:** `.env.example`, `.gitignore`, `backend/pyproject.toml`, `backend/app/{db.py, errors.py, main.py}`, `backend/app/config/{env.py, database.py, trust.py, access.py, forecast.py}`, `backend/app/models/{__init__.py, base.py}`, `backend/app/routers/{__init__.py, system.py}`, `backend/tests/{test_config_env.py, test_db.py, test_forecast_config.py, test_errors.py}`, `data/synthetic/README.md`, `docs/P3_FEATURES.md`.
- **Tests and results (2026-10-02, Windows 11, Python 3.11.9, Node 24.16):** `python tasks.py test` exit 0: 73 backend tests passed (54 existing + 19 new), 1 frontend test, all P1 data/evidence verifiers pass. `python tasks.py lint` exit 0 (ruff check, ruff format, eslint, tsc). `scripts/ci/verify_main_integration.py` and `scripts/ci/verify_p1_r_p1.py` pass. `ml` extra: `pip install --dry-run ".[ml]"` resolves (38 packages); not installed or run.
- **How to run:** `python tasks.py test` / `python tasks.py lint`. API: `.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --env-file .env` after copying `.env.example` to `.env`. Optional ML: `.venv\Scripts\python -m pip install -e "./backend[ml]"`.
- **Not done:** frontend API base URL and fixtures folder (P4's area); `tasks.py` messages when Python/Node are missing; `run-api` command; Windows CI job; database migrations.
- **Status log:** 2026-10-02 fixes committed locally on `fix/s1-review`; awaiting approval to push.

## T1: duplicate engine (F13)

- **Implementation notes:** Rule from `docs/JALLEKHA_FINAL_SOLUTION.md` F13, values in `config/trust.py` with sources.
  - `find_parent(new, existing)`: only earlier complaints of the **same category** within the category window (48 h no-water / tanker-missed / dirty water; 168 h leak / other; inclusive) qualify. **Same household id matches first**, at any distance. Otherwise the nearest complaint within **100 m** (inclusive), then the most recent; unknown categories and naive timestamps are rejected.
  - `link_duplicates(complaints)`: processes in time order with a grid index; chained reports are linked to the **cluster root** (union-find) and keep `matched_id` for audit; result does not depend on input order.
  - `duplicate_rate_by_area(complaints, links, area_key, period)`: duplicates / complaints per area and UTC month or week, with `duplicate_rate_basis` (DERIVED). A reporting-activity signal (Liu et al.), not a need measure; missing area is reported as `unassigned`.
  - Text similarity (LaBSE, `ml` extra) is off by default, only records `text_score`, never creates or blocks a merge, and falls back to none when the model is missing. Untested on Indian data.
  - Models: `complaint` and `duplicate_link` (one table each; one link per child; basis column).
  - Calibration: `scripts/trust/calibrate_dedup.py` runs only on a D13 file registered in `data/verification/source_manifest.csv` with a matching SHA-256. It reports p95 child-parent distance, p90 hours per Chicago SR type and the linked share for 100 m / 48 h and 300 m / 7 d, next to the solution document's 106 m, 71% and 88% for comparison only. **Not run: D13 is not registered yet.**
- **Files:** `backend/app/config/trust.py`, `backend/app/services/dedup.py`, `backend/app/models/{complaint.py, duplicate_link.py, __init__.py}`, `scripts/trust/calibrate_dedup.py`, `backend/tests/services/{test_dedup.py, test_dedup_calibration.py}`, `backend/tests/test_dedup_models.py`, `backend/tests/test_db.py` (S1 test updated now that tables exist), `docs/worklogs/T1.md`, `docs/features.csv` (T1 row), `docs/P3_FEATURES.md`.
- **Tests and results (2026-10-02, Windows):** done-when tests: leak 5 days apart merges, no-water 5 days apart does not, 150 m apart does not; plus household first, household outside window, exactly 100 m / 100.5 m, 48 h / 48 h + 1 s, 7-day `other`, different category, later complaint never a parent, nearest wins, unknown category, naive time, chain to root, order independence, grid vs brute force (300 points), haversine, text secondary + fallback, duplicate rate. `python tasks.py test` exit 0: 105 backend tests (32 new), 1 frontend test, all P1 verifiers. `python tasks.py lint` exit 0. Calibration script: refusal paths and a six-row test fixture only.
- **How to run:** `.venv\Scripts\python -m pytest backend/tests/services/test_dedup.py`. Calibration (after P1 registers D13): `.venv\Scripts\python scripts/trust/calibrate_dedup.py --input <D13 file>` → `data/derived/dedup_calibration.csv`.
- **Status log:** 2026-10-02 core engine, models and calibration script committed locally on `feat/t1-dedup`; calibration waits for P1's D13 pull. PR #19 merged into `main`, status DONE. Follow-up on `fix/t1-followup`: trust config windows stored as tuple pairs (copy/pickle/asdict work), dedup reuses `services/geo.py` `haversine_m`.

## T2: forecast + backtest (F5)

- **Implementation notes:** _to fill_
- **Files:** _to fill_
- **Tests and results:** _to fill_
- **How to run:** _to fill_
- **Status log:** _to fill_

## T3: delivery proof (F12)

- **Implementation notes:** _to fill_
- **Files:** _to fill_
- **Tests and results:** _to fill_
- **How to run:** _to fill_
- **Status log:** _to fill_

## T4: intake + voice (F14)

- **Implementation notes:** _to fill_
- **Files:** _to fill_
- **Tests and results:** _to fill_
- **How to run:** _to fill_
- **Status log:** _to fill_

## T5: supply-notice feed (F15)

- **Implementation notes:** _to fill_
- **Files:** _to fill_
- **Tests and results:** _to fill_
- **How to run:** _to fill_
- **Status log:** _to fill_

## T6: ledger (F18)

- **Implementation notes:** _to fill_
- **Files:** _to fill_
- **Tests and results:** _to fill_
- **How to run:** _to fill_
- **Status log:** _to fill_

## T7: explanations + contest (F16)

- **Implementation notes:** _to fill_
- **Files:** _to fill_
- **Tests and results:** _to fill_
- **How to run:** _to fill_
- **Status log:** _to fill_

## T8: shortage early warning (F6)

- **Implementation notes:** _to fill_
- **Files:** _to fill_
- **Tests and results:** _to fill_
- **How to run:** _to fill_
- **Status log:** _to fill_

## T9: confidence gate (F17)

- **Implementation notes:** _to fill_
- **Files:** _to fill_
- **Tests and results:** _to fill_
- **How to run:** _to fill_
- **Status log:** _to fill_

## T10: API for all screens

- **Implementation notes:** _to fill_
- **Files:** _to fill_
- **Tests and results:** _to fill_
- **How to run:** _to fill_
- **Status log:** _to fill_
