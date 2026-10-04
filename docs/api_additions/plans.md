# Plan routes added in Wave 1 (agent A)

For the lead to merge into `docs/api_shapes.md` and `docs/openapi.json`
(`python scripts/api/export_openapi.py`; `tests/api/test_api_auth.py::test_openapi_export_is_current`
fails until it is re-exported: the only differences are `/plans` GET and POST and the `NewPlan`
schema).

Errors use the shared shape `{"error": {"code", "message", "details"}}`. Auth as for every
officer route: no or unknown bearer token 401 `unauthorized`, a valid token with another role
403 `forbidden`.

## What changed behind the existing routes

- Plans are stored in the database (table `plan_record`), so they survive a restart. A row holds
  a **recipe**, not the plan: the planner is deterministic, so the plan is rebuilt on read, its
  digest compared with the stored digest, and the stored checks and approval put back on it.
  No objects are pickled.
- Recipe (JSON): `{"source": "planner_replay", "replay": "main_2025", "scenario": "tight",
  "seed": 0, "day": "YYYY-MM-DD", "gate": "T9", "threshold": 0.5}`.
- Plans created through the API are gated by **T9** (`services/confidence.py` `T9Gate`, threshold
  0.50 PROVISIONAL). `flags[*].basis` is `"DERIVED; min of available signals; threshold 0.50"`
  and `flags[*].reason` is T9's (`"weakest census_join_quality=0.0000 (...); used: ...;
  unavailable: ..."`). The offline replay script (`scripts/sandbox/build_planner_replay.py`) and
  A7's `ProvisionalGate` are unchanged, so the committed replay outputs do not move; the API plan's
  digest differs from the replay CSV's digest for the same day because its flags differ.
- Every API plan is SIMULATION: it is built from P2's committed A8 replay (Mar-Jul 2025; monthly
  totals REAL, daily arrivals SYNTHETIC).
- `GET /plans/{plan_id}`, `/confidence`, `/groups/{group}/check`, `/approve` and
  `/explain/bookings/{id}`: response shapes unchanged. Check and approval are now saved. New error:
  **409 `conflict`** when a stored plan no longer rebuilds to its stored digest (its input files
  or the gate changed since it was stored); the message names both digests.

## POST /plans

Build and store the plan for one day of the replay.

- Roles: officer.
- Request body: `{"day": "YYYY-MM-DD"}`. The day must be in the replay window, 2025-03-01 to
  2025-07-31.
- Response **201**: the new plan, in exactly the shape of `GET /plans/{plan_id}`
  (`docs/api_examples/plan.get.json`): `plan_id` (`"replay-YYYY-MM-DD"`), `day`, `status`
  (`"DRAFT"`), `digest`, `stations`, `stations_total`, `transfers`, `transfers_total`,
  `scheduled`, `scheduled_total`, `outage`, `outage_trips`, `reserve_trips`,
  `effective_entitlement`, `flags`, `flags_total`, `checked`, `unrouted`, `unrouted_total`,
  `special_stops`, `special_tankers`, `routing`, `approved_by`, `approval_reason`, `basis`.
  `basis` here is
  `{"plan": "SIMULATION (A7 replay main_2025, tight, seed 0; daily arrivals SYNTHETIC, monthly
  totals REAL)", "effective_entitlement": "DERIVED (A2 Census 2011 need; A3 fallback median where
  flagged)", "flags": "DERIVED (T9 gate: min of available signals; threshold 0.50 PROVISIONAL)"}`.
- **Idempotent by day**: if the day's plan is already stored, the response is **200** with the
  stored plan as it is now (including its checks and approval); nothing is built and no ledger
  entry is written. (Chosen over 409 so a retried request is harmless.)
- Ledger: one `plan_created` entry (actor `system`) when the plan is first stored, never on a
  repeat or on a rebuild. Its `at` field is the plan's nominal planning time (05:00 IST on the
  replay day, as in the replay), not the request time; the entry's own timestamp is the request
  time.
- Errors: 422 `validation_error` (missing or malformed `day`); 404 `not_found` (day outside the
  replay window; the message gives the window); 409 `conflict` (the stored plan for that day no
  longer rebuilds to its digest).
- Time: the first plan built after a start loads the replay (about 12 s); a later day builds in
  about 0.2 s per replay day after the last one built, an earlier day replays from 2025-03-01.

## GET /plans

List the stored plans, by day.

- Roles: officer.
- Query: `offset` (integer >= 0, default 0), `limit` (1-200, default 50).
- Response 200: `{"total", "offset", "limit", "items": [...]}`, each item
  `{"plan_id", "day" (YYYY-MM-DD), "status" (DRAFT | APPROVED), "basis" (object, as on the plan),
  "flags_total" (integer), "checked_total" (integer), "created_at" (ISO 8601 UTC)}`.
  Read from the stored rows; no plan is rebuilt.
- Errors: 422 `validation_error` (offset or limit out of range).

Example item:

```json
{
  "plan_id": "replay-2025-03-01",
  "day": "2025-03-01",
  "status": "DRAFT",
  "basis": {"plan": "SIMULATION (...)", "effective_entitlement": "DERIVED (...)", "flags": "DERIVED (T9 gate: ...)"},
  "flags_total": 40,
  "checked_total": 0,
  "created_at": "2026-10-04T09:12:03.512345+00:00"
}
```

## Need weights, ward names and the comparison (added 2026-10-04)

### `POST /plans`: optional `weights`
`{"day": "2025-05-01", "weights": {"wad": 5, "cad": 0, "hardship": 0}}`. All three are required
when `weights` is given, each between 0 and 5 (`need_weight_max`), no other fields (for example no
debt weight: the replay has no debts). Weights equal to the configured defaults make the default
plan. Other weights make a separate plan with its own replay run, id
(`replay-<day>-w<wad>-<cad>-<hardship>`) and digest; the plan_created ledger entry carries the
weights. A repeat with the same weights returns the stored plan (200). Out-of-range or malformed
weights: 422, nothing stored.

### Plan view: `weights` and `group_names`
- `weights`: `{wad, cad, hardship, is_default}`, the weights this plan was built with.
- `group_names`: a readable name for every group in `effective_entitlement` (ward name from the
  Census evidence file, or the HMWSSB section name; `null` when unknown, never invented).
- `basis.weights`: how the weights are labelled (ASSUMED policy weights; "chosen by an officer"
  when not the defaults).

### `GET /plans/{plan_id}/compare` (officer)
Who gains and who loses booked trips under the plan's weights, against the default plan for the
same day: `{against, day, weights, default_weights, gainers, losers, all_changes, basis}`. Each
row is `{group, name, served_default, served_weighted, change}`. Same trips redistributed, so
the changes sum to zero. A plan with the default weights (or an unknown plan) answers 404.
The effect is usually small: daily capacity and the round-robin limit how far weights can move
trips (for example, 6 groups change, by at most 8 trips, for the strongest water-access setting
on 2025-05-01).


`GET /plans` rows also carry `weights`: `null` for a default plan, or `{wad, cad, hardship}` for a
weighted one, so a list can label weighted plans without opening each.
