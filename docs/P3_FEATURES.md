# P3 features: forecast, access and trust backend

Owner: P3. One section per task, updated at the end of each task on that task's branch. Sources: `docs/JALLEKHA_FINAL_SOLUTION.md`, `docs/features.csv`, `docs/research/P3.md`.

| ID | Feature | Branch | Status |
|---|---|---|---|
| R-P3 | Research note | `research/p3` | Local draft, not pushed |
| T1 | F13 duplicate engine | `feat/t1-dedup` | Not started (needs S1, R-P3 merged) |
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

- **Implementation notes:** Research only, no feature code. Decisions per feature (keep / change / add) are in `docs/research/P3.md`. Main changes proposed: F14 adds Urdu ASR and drops NeMo (IndicConformer runs on `transformers` + ONNX); F5 pools scaled conformal residuals across sections (80/90% intervals), uses one global GBM, and benchmarks Chronos-2 if the team accepts it; D7 groundwater source is India-WRIS / CGWB; F18 adds a daily published head hash, `key_id` per entry and gap detection.
- **Files:** `docs/research/P3.md`, `docs/P3_FEATURES.md`.
- **Tests and results:** none (docs only). Every claim carries a link; [R]/[S] marks read vs search-summary sources.
- **How to run:** n/a.
- **Open questions:** Chronos-2 vs "no LLM in scoring" (team); Liu et al. venue (confirm); D13 Chicago fresh pull (P1/owner); 21.9%/35.1% protocol (P1/owner).
- **Status log:** 2026-10-01 draft; 2026-10-02 citation check, trimmed to 2 pages.

## T1: duplicate engine (F13)

- **Implementation notes:** _to fill_
- **Files:** _to fill_
- **Tests and results:** _to fill_
- **How to run:** _to fill_
- **Status log:** _to fill_

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
