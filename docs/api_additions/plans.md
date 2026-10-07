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

`GET /plans` also returns `default_weights` (`{wad, cad, hardship}`, the configured policy weights)
and `max_weight` (the largest weight a request may use), so a screen can start its sliders at the
defaults and stop them at the maximum without copying the configuration.

## Plans from supplied bookings (added 2026-10-04)

There is no live booking feed (HMWSSB publishes monthly totals only), so an officer, or a later
import job, supplies the day's bookings.

### `POST /plans` with `bookings`
`{"day": "2026-10-03", "bookings": [{"booking_id": "B-1", "section": "ADARSHNAGAR", "arrived_at":
"2026-10-03T05:30:00+05:30"}, ...], "weights": {...}}` (`weights` optional, as above). Each booking:
- `booking_id`: 1 to 80 letters, digits, spaces or `_ . : / ( ) # -`, unique in the request.
- `section`: an HMWSSB section with a filling station and need data (the sections of
  `data/derived/sandbox/section_station_km.csv`).
- `arrived_at`: ISO date and time **with a time zone**, on or before the plan day (India time).
- optional `consumer_id` (1 to 64 characters; default the booking id), `category` (`domestic`,
  `apartment_5_24`, `apartment_25_200` or `commercial`; default `domestic`) and `tier` (0 critical
  facility, 1 no water on premises, 2 other; default 2). Unknown fields are refused.

At least 1 and at most 10,000 bookings (`max_supplied_bookings`). The day may be any day (no replay
window). Capacity is the same ASSUMED fleet scenario as the replay (there is no live capacity feed),
need comes from Census 2011, and nothing carries over from an earlier day. The plan id is
`plan-<day>-<8 hex of the bookings>` (plus the weights suffix), so the same bookings in any order
are the same plan: a repeat returns the stored plan (200) and logs nothing. Unusable bookings: 422
with the problems listed (up to 10, by booking number), nothing stored. The plan_created ledger
entry carries `source` and the number of bookings. The bookings are kept in the plan's recipe, so
the plan rebuilds exactly after a restart. `POST /plans` without `bookings` still needs a day of
the replay (404 otherwise).

### Plan view and list: `source`, `bookings_supplied`
`source` is `planner_replay` or `supplied_bookings`; `bookings_supplied` is the number of supplied
bookings, or `null` for a replay plan. List rows also carry `source`. `basis.plan` says the
bookings are as supplied and not verified here.

### Plans by section: `unit`, `capacity`, `capacity_scenario`, `trips_total` (feat/section-queue)
`POST /plans` accepts `unit: "section"` (default `"ward"`) and `capacity: "fleet" | "tight"` (default
`"fleet"`). A plan by section is made for a day of 2025 from that month's real booking total of each
HMWSSB section divided by the days of the month (all tier 2, domestic); entitlement is the section's
domestic connections x its need weight; sections whose need or connections are estimates are flagged
and need an officer's check before approval. `bookings` must not be supplied (422); a day outside 2025
is 404. Plan id `section-<day>-<capacity>` (plus the weights when not the defaults). The view and the
list carry `source: "section_month"`, `unit: "section"`, `capacity_scenario` and `trips_total`; groups
are `section:<name>`. `GET /plans/{id}/confidence` answers with the section gate (confidence 0 for an
estimated section, 1 otherwise). Basis: bookings REAL monthly totals, daily split by division of the
month, capacity ASSUMED (fleet) or DERIVED (tight), need DERIVED_APPROXIMATE or ESTIMATED.

### Plans by section, more (feat/section-plan-completion)
`POST /plans` for `unit: "section"` also accepts `priority` (default `true`), `scheduled` (`"f4"`
or `"none"`, default `"f4"`) and `carry_over` (default `true`). A plan with other than the defaults,
or with outages or section debts, gets a short hash in its id (`section-<day>-<capacity>-<hash>`).
- **Priority classes (estimated):** HMWSSB publishes no booking types, so each mapped hospital or
  care home (OSM, D9) is taken as one of its section's bookers every day (tier 0) and the Census
  share of homes fetching water from outside (WAD, carried onto the section) as the share of the
  rest in tier 1. Basis ASSUMED / ESTIMATED. Bookings are labelled domestic or commercial by the
  section's commercial connections, calibrated to the real 2022 commercial trip share (RTI).
- **Carry-over:** the days before (back `expiry + 1` = 4 days, inside 2025) are planned first; the
  bookings still waiting (they expire after 3 days) and the fair queue's turn credits arrive with
  the plan.
- **Scheduled supply (F9):** the sections the field-check screen (F4) flags get a reserved share of
  the trips (weighted max-min, 15 litres per person a day over people off premises = connections x
  household size x WAD), with a stop at the estimated centre of the section, not routed yet.
- **Outages (F10):** the supply notices (F15) that overlap the day become outages by section (a
  section is cut when at least half its buildings are in the notice's wards); the mapped hospitals,
  care homes, UPHCs and clinics of cut sections are critical stops served first.
- **Water debt:** `POST /debt/days/{day}/close` takes the id of an approved plan by section. Owed =
  the section's bookings of the day x 5,000 l; paid = Confirmed deliveries at stops inside the
  section's area. Accounts are `section:<name>` (`unit: "section"` in the account view) and the next
  plan by section reads them (a section in debt gets more turns).

### Tanker routes of a plan by section: `GET /plans/{plan_id}/routes[?station=ST12][&compact=true]` (feat/route-planner)
Officer only; 409 for a plan that is not by section, 404 for an unknown station. A booking is one
tanker load, so a trip is station -> place -> station and a tanker's day is a list of timed round
trips. Answer: `summary` (tankers on the road of the fleet of 1,150, trips, special trips, km,
sections reached, latest finish, trips per tanker, loads that do not fit the day, legs that are
estimates), `stations` (tankers, trips, km, finish, unscheduled per station), `tankers` (only for
the requested `station`: id, trips with times leave/arrive/unloaded/back, kind booked | scheduled |
outage | critical, km, leg basis OSRM | ESTIMATE), `unscheduled` (loads that did not fit),
`basis`. Loads leave in priority order (critical facilities, cut sections, scheduled supply, then
the booked queue as the fair queue served it) on the station's tanker that is free first; a load
a neighbouring station lent its trip for is driven from the lender; scheduled-supply and outage
loads go to the nearest station with a spare special trip. Computed from the plan, never stored.
With `compact=true` the answer also has `paths` (null otherwise): every tanker's trips as
`[lat, lng, depart, arrive, unloaded, back, kind]` (minutes after midnight; kind 0 booked,
1 scheduled, 2 outage, 3 critical), for the city-wide animation (feat/plan-visuals). Trips to a
place with no location are left out.

### Turns follow recent service and trips follow waiting bookings: `responsive`, `rebalance` (feat/responsive-allocation)
`POST /plans` with `unit: "section"` takes `responsive` (A) and `rebalance` (B), both true by default; the
recipe and plan id carry them only when on, so plans stored before rebuild unchanged. `overview.facts`
gains `trips_moved` and each section row `turn_factor` (this plan's turns over the Census turns).
`/field-checks/weekly-priority` rows gain `source` (OFFICER_CHECK, BOOKINGS or NONE) and, from bookings,
`bookings_delivered`, `bookings_not_delivered`, `bookings_unknown`.

### Plan overview of a plan by section: `overview` in `GET /plans/{plan_id}` (feat/plan-visuals)
Null for other plans. `facts`: bookings of the day, carried over, commercial, priority classes
(`tiers` and `served_tiers`: hospitals and care homes, homes without water on premises, others),
served, waiting, trips, trips kept for scheduled supply (`reserve_trips`) and how many of them the
scheduled water needs (`reserve_used_trips`), outage trips, trips left for bookings. `sections`:
one row per section (all 197, also the ones with no booking that day) with its bookings and served
by priority class, its service type (`cut` water cut by a notice, `scheduled` water on a schedule
for a section the field-check screen flags, `heavy` 2025 bookings per 1,000 connections in the top
quarter, `normal`, `unknown` without a connection count), its scheduled-supply or outage water
(litres, people, loads), bookings per 1,000 connections and the peers' rate. `stations`: the
bookings of each section held at each filling station (the screen replays the station's queue
from `stations[*].served`). Basis: DERIVED from the plan; the service-type cut-off is ASSUMED.

