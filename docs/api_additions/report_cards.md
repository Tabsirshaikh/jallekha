# API additions: ward report cards with deliveries, water debt and schedule (F20, item 11)

`docs/openapi.json` is regenerated (`python scripts/api/export_openapi.py`). Examples:
`docs/api_examples/ward_report_card.get.json`, `ward_sms_summary.get.json`,
`debt_day_close.post.json`, `debt_accounts.get.json`, `debt_days.get.json` (all SYNTHETIC, from
one real run of the loop below).

## The loop

```
officer registers a stop ──► the stop gets a ward (named, or found on the 2016 ward map)
officer supplies a day's bookings ──► plan: each scheduled ward's water split across its stops
officer approves the plan ──► drivers deliver; residents confirm or dispute (F12)
the day is over ──► officer closes it: per ward, planned litres minus Confirmed loads = debt (A6)
next supplied plan ──► uses the saved debts: a ward still owed water gets more turns (A7)
report card ──► deliveries, debt and schedule for each ward, with their basis
```

This follows how tanker programmes check service (per trip and per drop point: Delhi Jal Board
pays tankers from the GPS trip record, UNHCR keeps a delivery logbook per site): the plan says
what each stop is owed, the delivery proof says what arrived.

## Stops: the ward a stop serves

`POST /stops` takes an optional `ward_id` (an id of the ward table, e.g. `relation/7848824`).
Without it the stop's position is placed on the 2016 ward polygons
(`data/raw/geography/datameet/ghmc-wards.geojson`). The stop view gains:

| Field | Meaning |
|---|---|
| `ward_id` | the ward, or null when the position is outside every ward |
| `ward_name` | from the ward table |
| `ward_basis` | `OFFICER` (named), `DERIVED` (ward map) or `UNPLACED` |

An unknown `ward_id` is 422. New columns `delivery_stop.ward_id`, `delivery_stop.ward_basis`:
an existing database needs them added by hand (no migrations, LIMITATIONS 1.11).

## Plans from supplied bookings

`POST /plans` with `bookings` now also uses every registered stop that has a ward and every
saved debt account. Both go into the plan's recipe (it still rebuilds exactly) and into the plan
id hash when there are any (a plan without them keeps its old id). Replay plans are unchanged.

- Scheduled supply (A4): each scheduled ward's litres are split evenly across its stops in whole
  5,000 l loads. No fleet is given, so they are listed per stop as not routed.
- Debt (A7): a ward's group turns are raised by `entitlement x (1 + debt / cap)`. Only
  accounts that still owe water enter the plan (an account at 0 changes nothing).
- The plan view gains `stops` ([{`stop_id`, `ward_id`, `ward_name`, `litres`}]) and
  `debts_used`, and `basis.stops` / `basis.debts` when used. The `plan_created` ledger entry
  gains `stops` and `debts` counts.

## Closing a day (officer)

`POST /debt/days/{day}/close` with `{plan_id, officer_id, reason}`; `plan_id` may be left out
for a day that had no supplied plan (nothing is owed that day; Confirmed deliveries still pay
debt back).

For each ward, the litres the approved plan gave its stops (the stops the plan was built with)
are owed; each Confirmed delivery started that day (Hyderabad time) at a stop now registered in
the ward pays back one load. A6's `settle_day` is used
unchanged (cap 7 days of entitlement, alert after 3 days, debt never below 0). A ward that already
has an account is settled even when the plan gives it nothing. Ledger: one `water_debt_changed`
per changed account and one `debt_day_closed` (plan id and digest, totals, reason SHA-256 only).

| Refused (409) when | Message says |
|---|---|
| the day is today or later | not over yet |
| the day is already closed | already closed |
| a later day is already closed | days are closed in order |
| the day after the last closed day is not closed yet | close that day first (days close one after another, without gaps; the first close may be any past day) |
| the plan is a replay plan | SIMULATION, only supplied plans create debt |
| the plan is not approved, or is for another day | approved / is for |
| a delivery of the day is still open | the delivery ids |
| an empty reason | 422 |

Unknown plan 404; roles other than officer 403. Nothing is written when refused. The saved day
is refused (409) inside the database transaction too if it is not the next day, so two processes
cannot close days out of order.

`GET /debt/accounts` (officer, paged): `account_id` (`ward:<ward id>`), `ward_id`, `ward_name`,
`debt_litres`, `daily_entitlement_litres`, `cap_litres`, `in_debt_since`, `alert_raised`,
`settled_through`.

`GET /debt/days` (officer, paged): `day`, `plan_id`, `plan_digest`, `closed_by`, `reason`,
`closed_at`, `wards` ({ward id: {`planned_litres`, `credited_litres`, `deliveries`,
`debt_before`, `debt_after`, `capped`, `alert`, `days_in_debt`}}).

Tables: `water_debt_account` (one row per account), `debt_day` (one row per closed day, unique).

## Report card and SMS summary

`GET /wards/{ward_id}/report-card` (officer, resident, councillor): `deliveries`, `debt` and
`schedule` are now live. Each is `{value, basis, reason}`: a value with its basis, or value null,
basis `UNAVAILABLE` and the reason.

| Block | Value | Basis |
|---|---|---|
| `deliveries` | last 30 days at the ward's stops: `started`, `by_outcome` (Confirmed, Disputed, Unconfirmed, Failed, open), `confirmed_litres`, `stops` | REAL, SYNTHETIC or MIXED, as the stops are registered |
| `debt` | `debt_litres`, `debt_loads` (rounded up), `cap_litres`, `in_debt_since`, `days_in_debt`, `alert_raised`, `settled_through`, `last_day` (the ward's line of the last closed day) | DERIVED |
| `schedule` | one stored plan: supplied before replay, then the latest day, approved before draft. `plan_id`, `day`, `status`, `source`, `booked` (served / waiting for `ward:<id>`), `scheduled` (A4 share), `stops` (litres, loads, arrival times when routed) | the plan's own basis |

`GET /wards/{ward_id}/sms-summary` adds `window_days`, `deliveries`, `debt` and `schedule`
phrases to `params` ("not available" when a block has no value). Wording is still PROPOSED and
English only.
