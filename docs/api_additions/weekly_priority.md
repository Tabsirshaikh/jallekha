# Weekly section service priority (F1/F4/F7/F9/F11)

ROUTE_ON_MAIN applies only after this branch is merged. Implemented locally on
`feat/weekly-water-priority`; all figures below are DERIVED_APPROXIMATE or ASSUMED.

- `GET /field-checks/weekly-priority?section_id=5:ADIKMET`: officer/field-worker response
  `{basis, as_of, items}`. Omit the filter for the section catalog. Each item includes
  population estimate, Census baseline, the seven completed Hyderabad calendar days,
  estimated tanker requirement, confirmed litres, shortfall/share, days below the daily
  minimum, allocation factor/current weight, status/reason and the latest supply review.
  Unknown amounts are null; unknown factor is 1 (existing policy preserved).
- `POST /field-checks/supply-reviews`: officer/field-worker body:
  `{id: UUID, section_id, checked_on: YYYY-MM-DD, supply, tanker_share, records_complete,
  booking_reason, note}`. `supply` is adequate/insufficient/unavailable/unknown; adequate
  requires share 0, unavailable 1, insufficient strictly between 0 and 1. The share is the
  fraction of the emergency minimum that must come from tankers after checking other supply.
  `booking_reason` is other_supply/access_difficulty/unclear. Note is required. A complete
  record assertion covers the seven days ending on checked_on. Today/future dates are rejected.
  A current calculation requires yesterday's completed window; older reviews are retained
  as history and never treated as complete for a later window. Append-only; retry the same id
  and identical body. A different body under the same id returns 422.
- Observations are REAL officer reports, not measurements of piped litres. Ledger event
  `section_supply_reviewed` stores assessment/note SHA-256 only. Pending audit rows cannot
  affect priority. Supply reviews do not enter booking-flag precision (the existing F4
  yes/no/unclear observation is still required for that measure).

Calculation: estimated population = domestic connections x Census-derived household size
(existing section planner estimate, not counted residents). Weekly emergency minimum =
population x 15 lpcd x 7 x verified tanker share. This is NOT full household water demand.
Only Confirmed outcomes at REAL registered stops in the window count; one load = 5,000 litres
(ASSUMED). Stop-to-section assignment is geographic and approximate; unplaced stops cannot be
credited. Unconfirmed, disputed or pending outcomes make the section's current result unknown.
Failed deliveries count as zero water. A no-delivery shortage requires explicitly complete
officer-verified records, never merely an empty database.

Let r = max(0, requirement - delivered) / requirement (0 for zero requirement), and d be
the number of days below the estimated daily minimum. Allocation multiplier =
`(0.25 + 3.75*r) * (1 + 0.5*(d/7)*r)` (ASSUMED; max 6, not empirically calibrated).
Current weight = Census weight x multiplier. The allocation entitlement retains section size.
Tier 0/1 protection and station capacities remain. This does not guarantee global ordering
between differently sized sections or across stations. Unknown groups keep their previous
entitlement/debt policy. Verified groups do not receive a second debt boost for the same gap.

`POST /plans` now accepts `{day, unit: "section", bookings: [...], ...}` for current dates:
the same supplied-booking columns and validation as before, but names must exist in the
section catalog. No synthetic monthly arrivals or automatic replay carry-over are added;
include still-waiting, unexpired bookings explicitly. Existing section identities/population
are based on the 2025 evidence; newly re-cut unmatched sections are refused, not invented.
Without bookings, historical 2025 section replay behaviour is unchanged. Known weekly
assessments, quantities and factors are frozen in the plan recipe and its id; subsequent
reviews/deliveries do not change a saved plan. Verified shortfalls enter scheduled reserve
even with no booking/F4 flag; covered groups leave that reserve. An explicit
`scheduled=none` disables the reserve, including verified deficits. Stops remain estimated
centres and the reserve is limited, so priority is not a guarantee of adequate delivery.
Plan JSON keys are unchanged; its basis map explains weekly priority. Closing a supplied
section day uses supplied fresh booking counts instead of historical portal totals.

`GET /atlas/live-sections` now prefers `section:<name>` debt, including zero, and reports
`owed_basis=SECTION_ACCOUNT`. A ward account is an explicit WARD_PROXY fallback; no account
is UNAVAILABLE, not a confirmed zero. The original four warning-sign rules remain separate.

Validation: `scripts/evidence/verify_weekly_priority.py` writes SIMULATION counterfactuals.
No actual seven-day field cohort exists and no real-world effectiveness claim is made.

Research basis: [P?rez-Rodr?guez and Holgu?n-Veras, inventory/allocation with deprivation costs](https://doi.org/10.1287/trsc.2014.0565),
[Maheshwari et al., tanker planning with demand and supply constraints](https://arxiv.org/abs/2408.01184).
These sources support considering unmet demand and delivery timing; they do not validate our
seven-day window, coefficients, population proxy or Hyderabad effectiveness.
