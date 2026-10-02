# P3 features: forecast, access and trust backend

Owner: P3. One section per task, updated at the end of each task on that task's branch. Sources: `docs/JALLEKHA_FINAL_SOLUTION.md`, `docs/features.csv`, `docs/research/P3.md`.

| ID | Feature | Branch | Status |
|---|---|---|---|
| R-P3 | Research note | `research/p3` | DONE ([PR #7](https://github.com/Tabsirshaikh/jallekha/pull/7) merged) |
| S1 fix | Skeleton gaps T1-T10 need | `fix/s1-review` | DONE ([PR #15](https://github.com/Tabsirshaikh/jallekha/pull/15) merged) |
| T1 | F13 duplicate engine | `feat/t1-dedup` | DONE ([PR #19](https://github.com/Tabsirshaikh/jallekha/pull/19) merged); calibration run waits for D13 |
| T2 | F5 forecast + backtest | `feat/t2-forecast` | Blocked: 21.9% / 35.1% protocol (`V-VERIFY_REVIEW.md`) missing |
| T3 | F12 delivery proof | `feat/t3-delivery` | DONE ([PR #26](https://github.com/Tabsirshaikh/jallekha/pull/26) merged); decisions (a) and (b) OPEN |
| T4 | F14 intake + voice | `feat/t4-intake` | IN_PROGRESS (local, not pushed); keyword lists, offline report time, phone registry and ASR revision OPEN |
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

- **Implementation notes:** Rule from `docs/JALLEKHA_FINAL_SOLUTION.md` F12; values in `config/trust.py` with sources. Pure service `services/delivery.py` (immutable `DeliveryState`, no database); S3's `services/otp.py` and `services/geofence.py` are used unchanged.
  - **Outcome table:** OTP verified + mostly yes = **Confirmed**; verified + mostly no = **Disputed**; not verified + mostly yes = **Unconfirmed**; not verified + mostly no = **Failed**. **Silence counts for nothing:** only replies are counted. Only Confirmed counts toward water debt (`counts_toward_debt`, for P2's A6). Each outcome has an `outcome_basis` (DERIVED) naming the rule and counts.
  - `start_delivery` needs 2-3 registered representatives of that stop (F12). `request_otp` sends the OTP by SMS to one of them; the plain code is never stored (nonce + hash), and the digit count is stored with the OTP and passed as `digits=` whenever the code is re-derived (`issued_code`), so changing `otp_digits` later does not break an issued OTP (S3 review D11). `verify_otp` checks, in order: already verified, locked, no OTP, expired, **geofence** (driver position, server side, 150 m), then the code. Only a wrong code inside the geofence uses an attempt; the code is never checked from outside, so a right and a wrong code from outside get the same `outside_geofence` reply. **Outside tries** are counted per stop visit (`outside_tries`): tries 1 to `outside_tries_max` are logged, the next writes one `outside_tries_exceeded` entry, later ones write nothing (stops ledger flooding; the code still works once the driver is inside). **Wrong attempts are counted per stop visit and are not reset by a reissued OTP;** at the limit the stop is locked and the OTP counts as not verified.
  - **Location input (S3 review D7, D8, D9):** `locate` / `check_geofence` return a `LocationCheck` with `status` `inside`, `outside`, `no_location` or `invalid_location` (`reason` `invalid_coordinates`, `invalid_radius` or `invalid_distance`); NaN, infinite or out-of-range coordinates (driver or stop) and a radius that is 0, negative, NaN or infinite never raise. `verify_otp` returns `invalid_location` for these; it uses no attempt and counts as an outside try. `distance_m` is `None` without a usable position, and results and ledger payloads never contain inf or NaN. `start_delivery` takes an optional per-stop `radius_m` (default config, 150 m).
  - `sample_residents`: seeded random sample of 3-5 residents (F12), representatives excluded, independent of input order; everyone if fewer than 3. `send_resident_check` sends "Did you get water? 1 yes / 2 no" and starts the reply window. `parse_reply` accepts 1 / 2 in any script (Telugu, Devanagari, Arabic-Indic digits). `record_response` counts only a sampled resident's first valid reply inside the window.
  - `close_delivery` decides once every sampled resident has replied or the window has closed, and writes the outcome to the ledger once.
  - **SMS:** `services/sms.py`, provider-agnostic; messages are template keys (`delivery.otp`, `delivery.resident_check`) plus the recipient's language and parameters, no hand-typed text. Only the fake provider exists (`SMS_PROVIDER=fake`). The wording per language is for P4's localisation.
  - **Ledger:** `services/ledger_port.py`: `LedgerPort.append(entry_type, payload, actor)`, implemented by `InMemoryLedger` on the S3 hash chain (T6 adds storage). `entity_type` / `entity_id` also stay in the payload (every entry field is hashed since S3-FIX #25). Every state change is an entry: `delivery_started`, `otp_issued`, `geofence_checked`, `otp_attempted`, `residents_sampled`, `resident_replied`, `delivery_outcome`, `outside_tries_exceeded`. The seven new ones were added to `EVENT_TYPES` in `services/ledger.py` (P2's file) in two separate commits, as instructed (`otp_issued` already existed). Payloads hold ids and numbers only, never phone numbers or OTP codes.
  - Models (one table each): `representative`, `delivery`, `resident_response` (one row per delivery and resident), `delivery_outcome` (one per delivery).
  - **OPEN decision (a), owner to confirm. Not decided.** OTP length, validity and attempt limit. Implemented proposal: `otp_digits = 6`, `otp_valid_minutes = 10` (NIST SP 800-63B v4 section 3.1.3.2, reference only), `otp_max_attempts = 3` wrong tries per stop. `otp_digits` was 4 (ported from v1, ASSUMED).
  - **OPEN decision (b), owner to confirm. Not decided.** What "mostly" means with ties and zero replies. Implemented proposal (`docs/P3_BUILD_PLAN.md` T3 step 4): mostly = yes exceeds no by `delivery_majority_margin = 1`; a tie or zero replies is no majority, so the outcome waits until the reply window (`delivery_reply_window_minutes = 120`, also a proposal) closes, then falls back to the OTP alone: verified → Unconfirmed, not verified → Failed. Consequence to confirm: one yes and four silent residents gives Confirmed when the OTP was verified.
  - **OPEN value, owner to confirm. Not decided.** `outside_tries_max = 10` OTP tries from outside the geofence logged per stop visit (proposal).
  - **Known limit:** the geofence position comes from the driver's phone and can be faked, so it is one of two checks, together with the resident replies.
- **Files:** `backend/app/config/trust.py`, `backend/app/services/{delivery.py, ledger_port.py, sms.py}`, `backend/app/services/ledger.py` (`EVENT_TYPES` only), `backend/app/models/{representative.py, delivery.py, resident_response.py, delivery_outcome.py, __init__.py}`, `backend/tests/services/test_delivery.py`, `backend/tests/test_delivery_models.py`, `docs/worklogs/T3.md`, `docs/P3_FEATURES.md`.
- **Tests and results (2026-10-02, Windows):** written first (import failed before the service existed). All four outcomes (table and end to end), only Confirmed counts toward debt, ties and zero replies (pending, then OTP-only fallback), no residents to ask, silence ignored (1 yes + silent = Confirmed after the window), invalid / late / unsampled / repeated replies ignored, reply digits in four scripts, waiting for all replies or the window, seeded sample (size 3-5, excludes representatives, order independent), template keys and languages, geofence 149 m inside / 151 m outside on five bearings, OTP outside the geofence not counted, right and wrong code from outside get the same reply, geofence checked before the code, outside tries 1-10 logged and try 11 onwards add only one `outside_tries_exceeded` entry, OTP to a registered representative only, 2-3 representatives, expired OTP (valid at the expiry second, rejected 1 s later, not counted), wrong attempts lock the stop across a reissue, naive time rejected, every state change and the outcome in a valid signed chain, no code or phone in the ledger, outcome written once, unknown event / missing entity rejected; model tables and unique constraints. 59 new tests pass, including exactly 150 m inside on all 360 bearings (enabled after S3-FIX #25 fixed D6); OTP still valid after `otp_digits` changes (D11); `invalid_location` for NaN / infinite / out-of-range positions and bad radii (D7, D9); no inf or NaN in results or ledger, also if `geofence.check` returned them (D8); `seq` and `prev_hash` change `entry_hash`. `python tasks.py test` exit 0 after merging `main` (S3-FIX #25, E2-FIX #24): 257 backend passed, 0 skipped, 1 frontend test, all P1 verifiers. `python tasks.py lint` exit 0.
- **How to run:** `.venv\Scripts\python -m pytest backend/tests/services/test_delivery.py backend/tests/test_delivery_models.py -rs`.
- **Status log:** 2026-10-02 config, `EVENT_TYPES` (separate commit), service, ports, models and tests committed locally on `feat/t3-delivery`; not pushed. Then, after review: tests that outside tries reveal nothing and the geofence is checked first; `outside_tries_exceeded` event type (own commit); cap on logged outside tries (`outside_tries_max`, OPEN). PR #26 merged, status DONE. Follow-up on `feat/t3-delivery` after merging `main`: exact-150 m test enabled (D6 fixed by S3-FIX #25), D1 note removed from `ledger_port.py`; then S3 review fixes handled in T3, each in its own commit: D11 (digits stored and passed), D7/D9 (`invalid_location`), D8 (no inf / NaN), and a test that `seq` / `prev_hash` change the hash. No T3 code uses the removed `ledger.compute_hash`. Waiting for: owner decisions (a) and (b). Not built here: API routes (T10), database storage of the ledger (T6), a real SMS provider, the OTP key in config (passed in by the caller for now).

## T4: intake + voice (F14)

- **Implementation notes:** `services/intake_pipeline.py`, built on P2's `services/intake.py` (`IntakeMessage`, `validate`, `clean_text`, `preset_category`) and `services/spam.py`, both used unchanged.
  - **Pipeline:** item → validate → spam score (spam is kept as an `intake_item` marked `spam`, no complaint) → language → category → `Complaint` → T1 duplicate check (`dedup.find_parent`; a match adds a `duplicate_link` to the cluster root) → one `IntakeResult` per item: `created`, `merged`, `spam`, `duplicate` or `invalid`. Complaint status: `open`, `awaiting_location` or `needs_transcription`.
  - **Channels:** app and field worker (JSON), SMS webhook (sender / text / time taken from whichever field names the gateway uses), missed call (number only; category `no_water` with basis "ASSUMED ... S3 review D14"; an ask-back SMS `intake.ask_location` asks for the location), voice notes. A field-worker report needs `reporter_id` and either `household_id` (stored as the complaint's household) or a location. Any report with neither a location nor a household is `awaiting_location` and gets the ask-back SMS when a phone is known.
  - **Offline sync:** `client_id` is the idempotency key (unique in `intake_item`); the same id again returns `duplicate` with the first complaint. `receive_batch` handles each item on its own and returns a status per item, in order. `client_created_at` must carry a time zone and is stored next to the server's `created_at`; an SMS gateway's own timestamp is stored the same way. Which time a synced report counts from is OPEN (below).
  - **Language:** by script (Telugu, Devanagari → `hi`, Arabic script → `ur`, Latin → `en`), by majority of letters, with a `language_basis`; the client's hint only when the text has no letters. Speech recognition's language wins for voice.
  - **Category:** button choice first ("REPORTED"), then the missed-call rule ("ASSUMED"), then keyword lists for te / hi / ur / en in `config/intake.py` (deterministic, no LLM; order tanker_missed, dirty_water, leak, no_water, else other; whole words in Latin script; Arabic letter variants normalised to Urdu forms). Every complaint has a `category_basis`.
  - **Voice:** `Transcriber` interface; `FallbackTranscriber` (no ASR: the audio is stored, the complaint is `needs_transcription` with `needs_human_transcription`); `IndicConformerTranscriber` (`ai4bharat/indic-conformer-600m-multilingual`, `ml` extra, not installed: `transformers` + `torchaudio`; Telugu, Hindi, Urdu per `docs/research/P3.md` F14; needs a te / hi / ur hint, reports no confidence; untested here). `ASR_MODE` (settings) picks it, falling back when the extra is missing; a transcription error also falls back. The audio is always kept (`voice_note`, file named by SHA-256 in `INTAKE_AUDIO_DIR`, git-ignored `/uploads/`), so no report is lost. Transcript confidence is stored when the model gives one.
  - **Stored:** channel, language and basis, category and basis, transcript confidence, reporter, household, client and server times, spam score and reasons. Phone numbers only as HMAC-SHA256 with `PHONE_HASH_KEY` (for the spam burst count); a report with a phone is refused without the key. Responses never echo phone numbers.
  - **Ledger:** no event type for intake exists in `EVENT_TYPES` (`issue_status_changed` is for status changes). None was added. T4 calls a LedgerPort-style `append(entry_type, payload, actor)` only for the proposed `complaint_received`, `complaint_merged`, `complaint_marked_spam`, and only once they exist; payloads are limited to ids, codes and numbers (`LEDGER_PAYLOAD_KEYS`). After T6 (#35) lands, `main` is merged in and the stored ledger is passed in.
  - **Endpoints (thin):** `POST /intake/batch` (at most `max_batch_items`), `POST /intake/sms`, `POST /intake/missed-call`. No voice upload endpoint yet (needs `python-multipart`; T10) and no authentication until T10.
  - **OPEN, owner to confirm. Not decided.** Keyword lists (written for this project, ASSUMED; native speakers to review); `offline_report_time = "server"` (proposal; "client" would use the phone's time within `max_offline_age_hours = 72`); `phone_registry_available = False` (no resident phone registry, so app / SMS / voice phones count as unregistered in the spam score; field workers count as registered); `asr_model_revision = None` (the model loads remote code; a revision should be pinned). ASSUMED: missed call = no water (S3 review D14); Latin text = `en` (may be romanised Telugu / Hindi); `max_audio_bytes = 10 MB`, `max_batch_items = 200`.
  - **Limits:** reports without a location are not checked for duplicates (also household-only field-worker reports); no area boundaries at intake, so the spam rule's "km outside the area" is not used; the IndicConformer path is not run in tests.
- **Files:** `backend/app/config/intake.py`, `.env.example`, `.gitignore`, `backend/app/models/{complaint.py, intake_item.py, voice_note.py, __init__.py}`, `backend/app/services/intake_pipeline.py`, `backend/app/routers/intake.py`, `backend/app/main.py`, `backend/tests/services/test_intake_pipeline.py`, `backend/tests/test_intake_models_router.py`, `docs/worklogs/T4.md`, `docs/features.csv`, `docs/P3_FEATURES.md`.
- **Config keys:** environment `PHONE_HASH_KEY`, `INTAKE_AUDIO_DIR`, `ASR_MODE`, `SMS_PROVIDER`, `DATABASE_URL`; `INTAKE_CONFIG` (`config/intake.py`): `KEYWORDS`, `CATEGORY_ORDER`, SMS / caller field names, `missed_call_category_basis`, `latin_language`, `offline_report_time` (OPEN), `max_offline_age_hours` (OPEN), `phone_registry_available` (OPEN), `asr_model_id`, `asr_model_revision` (OPEN), `max_audio_bytes`, `max_batch_items`, `audio_types`.
- **Tests and results (2026-10-02, Windows):** written first (import failed before the code existed). Each channel creates a complaint (app, SMS with three providers' field names, missed call, field worker for a household and for a location, voice); spam rejected and kept (short gibberish SMS; a burst of 6 from one phone); Telugu, Hindi and Urdu text accepted and categorised, plus romanised Telugu; address-only text not rejected; language by script and hint; Arabic letter variants; button wins; unknown channel / category invalid; same `client_id` twice = one item; a batch with one bad item processes the others and reports each status; client and SMS gateway times kept next to the server time, zone required; voice with ASR unavailable → stored audio + `needs_transcription` complaint; voice with a transcript stores text, language and confidence; empty / oversized audio invalid; `ASR_MODE` selection and fallback; a duplicate report merged by T1 to the cluster root, a far one not; reports without location not deduplicated; raw phone numbers never stored; no phone key → refused; no ledger entries while no event type exists; once types exist, payloads hold ids and numbers only (no phone, name or text); P2's `IntakeMessage` used as is; tables, unique `client_id`, endpoints and batch limit. 48 new tests. `python tasks.py test` exit 0: 371 backend passed, 1 frontend test, all P1 verifiers. `python tasks.py lint` exit 0.
- **How to run:** `.venv\Scripts\python -m pytest backend/tests/services/test_intake_pipeline.py backend/tests/test_intake_models_router.py`. API: set `PHONE_HASH_KEY` (and `ASR_MODE=fallback`), run the app, then `POST /intake/batch`, `/intake/sms`, `/intake/missed-call` (see `/docs`). Optional speech recognition: `pip install -e "./backend[ml]"` and `ASR_MODE=indicconformer` (not tested here).
- **Status log:** 2026-10-02 config, models, pipeline and endpoints committed locally on `feat/t4-intake`; not pushed. Waiting for: T6 (#35) to merge, then merge `main` and pass the stored ledger; the team to decide intake event types; the owner on the OPEN values; T10 for voice upload and authentication.

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
