# JalLekha 2.0 — project guide for agents

Read this first; it replaces reading the whole repo. Then read only the files your task touches.

## What this is

PS11 (Hyderabad water supply): fair tanker allocation and complaint intelligence for HMWSSB.
Three layers from `docs/JALLEKHA_FINAL_SOLUTION.md` (the design doc, features F1-F20):

- **Layer A Evidence** (F1-F6): ward need atlas from Census 2011, growth, booking equity,
  under-served field checks, monthly booking forecast, shortage warning.
- **Layer B Allocation** (F7-F11, F19): need weights, fair queue, scheduled supply, outage
  response, water debt, daily planner, policy sandbox / impact page.
- **Layer C Trust and access** (F12-F18, F20): delivery proof (OTP + resident replies), duplicate
  complaints, multilingual intake (Telugu, Urdu, Hindi, English), explanations and contests,
  confidence gate, tamper-evident ledger, public ward report cards.

No LLM in any scoring, allocation or explanation step.

## Status (2026-10-05)

- All features exist; `docs/LIMITATIONS.md` lists every known limit per feature (read the section
  for your feature before changing it).
- **To-do list: `docs/REMAINING_WORK.md`** (items 11-22, each with what, where it stands, how to do
  it, done-when; plus "Research follow-ups"). Done: 11 (#68), 12 + 16 (#69), 14 (#70), 21 (#74),
  22 (#75), 15 (#76), 18 (#77), research A (`feat/f5-selection-rule`). Left: 13, 17, 19, 20, and
  research follow-up B.
- Last full check on `main` (5c4d43c): lint clean; 908 backend + 184 frontend tests pass; all data
  verifiers pass.
- GitHub Actions cannot run (account billing block). Every change is verified locally before merge.

## Layout

| Path | What |
|---|---|
| `backend/app/config/` | every policy number, with its source and basis comment (ASSUMED / DERIVED / OPEN). Never hard-code a number elsewhere |
| `backend/app/services/` | pure logic, one feature per module (`planner.py` A7, `plan_builder.py` API plans, `fair_queue.py` A3, `water_debt.py` A6, `day_close.py` closing a day, `report_card.py` F20, `forecast.py` F5, `shortage.py` F6, `confidence.py` T9, `dedup.py` F13, `delivery.py` + `delivery_store.py` F12, `ledger*.py` F18, `explain.py` / `contest.py` F16, `intake*.py` F14) |
| `backend/app/routers/` | thin FastAPI routes; stores via dependencies in `stores.py` (`get_plan_store`, `get_delivery_store`, `get_debt_store`); clock via `common.get_now` |
| `backend/app/models/` | SQLAlchemy tables, one per file, registered in `models/__init__.py`. SQLite, `create_all`, **no migrations** |
| `backend/tests/` | pytest; `tests/api/conftest.py` gives a `client` with temp DB, test tokens and all stores overridden |
| `frontend/src/` | React 19 + TS + Vite. One screen per `*Experience.tsx`, API→view mapping in `*Adapter.ts`, `useApi` (live flag), `auth.tsx`, `DataSource.tsx` (live vs "Saved snapshot" chip), snapshots in `src/data/` |
| `scripts/` | data fetch (`scripts/data/`), evidence builds and verifiers (`scripts/evidence/`), forecast backtest, sandbox replay, calibration |
| `data/raw/` | logged source data (checksums in `data/verification/source_manifest.csv`); `data/derived/` built outputs |
| `docs/` | `JALLEKHA_FINAL_SOLUTION.md` (design), `LIMITATIONS.md`, `REMAINING_WORK.md`, `BRANCH_WORKLOG.md`, `features.csv` (tracker), `api_shapes.md` + `api_additions/` + `api_examples/` (API contract), `openapi.json`, `translation_review/` |

## Screens (frontend/src)

U2 resident intake + U10 ward card: `ResidentExperience.tsx` (+ `WardCardLive.tsx`, `wardCardAdapter.ts`);
U3 `FieldWorkerExperience.tsx`; U4 `DriverExperience.tsx`; U5 atlas/equity/field checks
`EvidenceExperience.tsx`; U6 `ForecastExperience.tsx`; U7 plan `PlanExperience.tsx`; U8 explain and
contest `ExplainExperience.tsx`; U9 impact `ImpactExperience.tsx`. Snapshot builders:
`scripts/frontend/build_u5|u6|u9_snapshot.py`.

## Data (data/raw)

D1 HMWSSB monthly tanker bookings per section (`hmwssb_tankers` 2022-Feb 2024, `hmwssb_tankers_portal`
to Aug 2026; sections re-cut Feb/Mar 2026); `census` (2011); `geography` (2016 GHMC wards
`datameet/ghmc-wards.geojson`, 145 wards, ids like `relation/7848824`; OSM district/mandals/HMWSSB
points); `d6_open_buildings` (growth); `d7_groundwater` (NOT fetched, needs NWDP login); `d8_weather`
(Open-Meteo daily, city centre); `d13_chicago_311` (F13 calibration); `d9_facilities` (OSM hospitals,
clinics, UPHCs, schools, care homes; counts per ward in `data/derived/evidence/ward_facilities.csv`).

## Remaining items: start here

| Item | Read first | Change |
|---|---|---|
| Research B city weather | same doc, part B; `scripts/data/fetch_d8_weather.py`, weather features in `forecast.py` | TGDPS station data per mandal |
| 13 voice error rate | `backend/app/config/intake.py` (`asr_model_id`), `services/intake_pipeline.py` | blocked: needs labelled Telugu/Urdu recordings |
| 17 groundwater | `data/raw/d7_groundwater/RETRIEVAL_LOG.md`, `services/shortage.py` | blocked: NWDP account |
| 19, 20 | `docs/REMAINING_WORK.md` | owner decisions; 20 = edit design doc section 7 "Stack" (line ~138) or build Docker/PostgreSQL/Leaflet |

## Commands (run from the repo root, Windows)

- `python tasks.py lint` — ruff check + format check (config `backend/pyproject.toml`, 100 cols), eslint, tsc.
- `python tasks.py test` — backend pytest, frontend vitest, `npm run i18n:check`, all data verifiers.
  Backend tests run in parallel (pytest-xdist, `-n auto`): about 7-9 minutes in all, bounded by one
  E5 PyMC test (~4.5 min). Must exit 0 before any merge.
- Use the venv Python: `.venv/Scripts/python.exe` (has scikit-learn, pymc; system Python does not).
  One test file: `.venv/Scripts/python.exe -m pytest -q -p no:warnings backend/tests/<file>`.
- Format a file: `.venv/Scripts/python.exe -m ruff format --config backend/pyproject.toml <file>`.
- After API changes: `python scripts/api/export_openapi.py`. After UI string changes:
  `npm run i18n:export` in `frontend/` (the test fails while the pack is stale).

## Rules

- **TDD**: write the test, watch it fail, implement, watch it pass.
- **Basis labels everywhere**: every number shown or stored says REAL / DERIVED / SIMULATION /
  SYNTHETIC / ASSUMED / UNAVAILABLE (with a reason). Never show a made-up number as real.
- **Honest results**: if a model does not beat the baseline or a figure does not reproduce, say so
  in `LIMITATIONS.md`; never tune tests or rules to match a target.
- **Every UI string in en, te, ur, hi** (screen dictionaries; shared ones in `i18n.tsx`).
- **No secrets**: tokens and keys only from the environment (`API_TOKENS`, `LEDGER_HMAC_KEY`,
  `OTP_HMAC_KEY`, `GATEWAY_TOKEN`); tests use fake ones. Never commit `.env` or `jallekha.db`.
- **Ledger**: new event types must be added to `EVENT_TYPES` in `services/ledger.py`; reasons go on
  the ledger only as SHA-256.
- **Each fix updates the docs**: `docs/LIMITATIONS.md` (the feature's section), `docs/REMAINING_WORK.md`
  (status), `docs/BRANCH_WORKLOG.md` (one entry per branch), `docs/features.csv` (notes), and API
  docs/examples if routes change.
- **Workflow**: branch from latest `main` (`feat/...`, `fix/...`, `docs/...`) → tests → `tasks.py
  lint` and `test` green → push → PR → squash-merge with branch delete → pull `main`.
  Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; PR body ends with
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## Traps (learned the hard way)

- **Parallel work**: never switch branches or edit files in a folder where `tasks.py test` is
  running (tests read the files). Two agents at once → separate git worktrees or clones.
- **Shared docs conflict**: almost every fix edits the four docs above; on a merge conflict keep
  both sides.
- **Checksums**: E2 and E5 record the checksum of `source_manifest.csv`. Adding a manifest row means
  rebuilding them (`scripts/evidence/build_evidence.py`, `build_underserved.py`; only that line
  changes). `verify_manifest.py` counts the 33 S2 rows apart from logged extra pulls (D13).
- **Git Bash**: long `python - <<'EOF'` heredocs fail to parse; write the script to a file and run
  it. `/tmp` paths are invisible to Windows Python. Set `MSYS_NO_PATHCONV=1` for WSL paths.
- **Example status labels** in `docs/api_examples/*.json` must start with ROUTE_ON_MAIN,
  FROM_MAIN, PROPOSED or NOT DESIGNED (`test_api_shapes.py`). Plan-view field changes need
  `docs/api_examples/plan.get.json` updated (contract tests compare key sets).
- **API tests** must override every store (plan, delivery, debt) so they never touch the real
  `jallekha.db`.
- **Plans** are stored as rebuild recipes and checked by digest; a supplied plan's id hashes its
  bookings, stops and non-zero debts. Replay plans are SIMULATION (Mar-Jul 2025) and never create debt.
- E5 spatial models (BYM2) did not converge and are fitted on Linux only; never re-sample on Windows.
