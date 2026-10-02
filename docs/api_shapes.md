# API shapes (T10 contract draft)

Owner: P3. Status: **draft for P4**, docs only (`docs/api-shapes`). Part 7 item 1 and T10 step 1 of `docs/P3_BUILD_PLAN.md`. Nothing here is a route yet unless marked **Route on main**.

Every shape below is built from a real service or file. The response-field tables are generated from the example files in [`docs/api_examples/`](api_examples/), and every example was produced by calling the real service, route or file (see `_example.built_from` in each file). `backend/tests/test_api_shapes.py` checks that the examples are valid JSON, carry no phone numbers, match what the merged routes (health, intake, notices, ledger) really return, and equal their source rows where they come from a file.

The T10 plan asks for JSON examples in the frontend fixtures folder; `frontend/` is P4's area, so they are in `docs/api_examples/` for P4 to copy if wanted.

## Status legend

| Status | Meaning |
|---|---|
| Route on main | The route exists on `main`; the table is what it returns today. |
| From main | The service function or data file is on `main`; the route is not built. The shape is that function's dataclass (as `asdict`) or the file's columns. |
| PROPOSED, service not merged | The service is on a local P3 branch (T2 `feat/t2-forecast`, T9 `feat/t9-confidence`); the shape is that branch's actual output. |
| NOT DESIGNED | No service or file builds it. Fields are left empty for P4 / P2 to propose. |

## Conventions (PROPOSED unless stated)

- **Names:** snake_case, the same names as the service dataclasses and data-file columns (the merged routes already do this). U5 / U6 snapshots use camelCase; see the open questions.
- **Types from data files:** values are typed when served: empty -> `null`, `True` / `False` -> boolean, integer text -> integer, decimal text -> number, anything else stays text (lists inside a cell, such as `quality_flags` `A;B`, stay text in file-based routes; T7 splits them into a list).
- **Basis:** every number has a basis from the project vocabulary REAL / DERIVED / ASSUMED / SYNTHETIC / SIMULATION, plus UNAVAILABLE for a value that does not exist (shown as `null`, never 0). Where the source has a `<field>_basis` column or field, that is the number's basis (the tables name it); otherwise the endpoint's **Basis** line applies to every number. A4 / A5 results already carry a `basis` object (`OutageResponse.basis`, `ScheduledPlan.basis`); T10 can use the same `basis` object where a field has no sibling `_basis`.
- **Errors (on main):** one shape for every endpoint, `{"error": {"code": str, "message": str, "details": any | null}}` (`app/errors.py`). `code` is the HTTP status phrase (`not_found`, `conflict`, `unauthorized`, `forbidden`), `validation_error` for 422, `internal_error` for 500. **Note:** the merged intake and notice routes, and the contest service, answer a bad item with HTTP 200 and `status: "invalid"` plus `error` in the body (so a batch can report each item); only a malformed request body gives 422.
- **Times:** ISO 8601 with offset. Services store UTC (ledger, outage, delivery); A8 replay bookings carry +05:30.
- **Roles:** T10 step 3 names officer, driver, resident with simple token auth and a local dev token. Nothing on main checks a token today. Field workers and SMS-gateway webhooks are not among the three roles (open question).
- **Paging:** the ledger uses `after_seq` + `limit` (on main). Lists from files are proposed as `offset` + `limit` with `total`.
- **Language:** `lang` = `te` | `ur` | `hi` | `en` (`ACCESS_CONFIG.supported_languages`); unsupported falls back to `en` (as SMS does). T7 renders text on the server from template keys (no LLM).

## What exists today

- **Routes on main:** `GET /health`, `POST /intake/batch`, `POST /intake/sms`, `POST /intake/missed-call`, `POST /notices`, `GET /ledger/entries`, `GET /ledger/verify`. No authentication, no CORS settings, no `docs/openapi.json` yet.
- **P4 screens:** U2 resident (`frontend/src/ResidentExperience.tsx`) and U3 field worker (`frontend/src/FieldWorkerExperience.tsx`) post to `/intake/batch` (or `VITE_INTAKE_URL`); U4 driver (`frontend/src/DriverExperience.tsx`) is a local preview (demo OTP `123456`, three demo stops); U5 (`frontend/src/EvidenceExperience.tsx`, `frontend/src/data/u5Evidence.json`, `u5Geometry.json`, built by `scripts/frontend/build_u5_snapshot.py` from E2 / growth / equity / E5 / coverage files) and U6 (`frontend/src/ForecastExperience.tsx`, `frontend/src/data/u6Forecast.json`, built by `scripts/frontend/build_u6_snapshot.py`) read committed snapshots, not an API.
- Mismatches are listed in **Open questions for P4** at the end.

## 1. System

#### `GET /health`

- **Status:** **Route on main.**
- **Built from:** app/routers/system.py health()
- **Roles (PROPOSED, T10 step 3):** anyone (no token)
- **Request:** none
- **Errors:** none expected
- **Basis:** no numbers
- **Example:** [`docs/api_examples/health.get.json`](api_examples/health.get.json) (REAL (live call))

| Field | Type | Basis of numbers |
|---|---|---|
| `status` | string |  |
| `service` | string |  |
| `version` | string |  |


## 2. Atlas

#### `GET /atlas/wards?offset=0&limit=2`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** data/derived/evidence/ward_evidence.csv (all columns, typed by the CSV rule in api_shapes.md)
- **Roles (PROPOSED, T10 step 3):** officer (resident read: open question)
- **Request:** `offset` (integer, default 0), `limit` (integer, PROPOSED max 200)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`
- **Basis:** REAL Census 2011 reweighted to 2016 wards: DERIVED, HISTORICAL; each value's `<field>_basis` column
- **Example:** [`docs/api_examples/atlas_wards.get.json`](api_examples/atlas_wards.get.json) (REAL Census 2011 values reweighted to 2016 wards (DERIVED, HISTORICAL); each value's basis is its *_basis column)

| Field | Type | Basis of numbers |
|---|---|---|
| `total` | integer | see **Basis** |
| `offset` | integer | see **Basis** |
| `limit` | integer | see **Basis** |
| `items` | array |  |
| `items[]` | object |  |
| `items[].ward_id` | string |  |
| `items[].ward_name` | string |  |
| `items[].geo_version` | string |  |
| `items[].census_year` | integer | see **Basis** |
| `items[].source_district` | string (nullable) |  |
| `items[].source_ward_code` | string (nullable) |  |
| `items[].source_url` | string (nullable) |  |
| `items[].hh14_source_url` | string (nullable) |  |
| `items[].join_status` | string |  |
| `items[].location_status` | string |  |
| `items[].review_required` | boolean |  |
| `items[].allocation_eligible` | boolean |  |
| `items[].quality_flags` | string |  |
| `items[].crosswalk_method` | string |  |
| `items[].census_coverage` | number | see **Basis** |
| `items[].dominant_source_share` | number (nullable) | see **Basis** |
| `items[].source_units` | string (nullable) |  |
| `items[].population` | integer (nullable) | `population_basis` |
| `items[].population_basis` | string |  |
| `items[].households` | integer (nullable) | `households_basis` |
| `items[].households_basis` | string |  |
| `items[].wad` | number (nullable) | `wad_basis` |
| `items[].wad_basis` | string |  |
| `items[].non_tap_share` | number (nullable) | `non_tap_share_basis` |
| `items[].non_tap_share_basis` | string |  |
| `items[].cad` | number (nullable) | `cad_basis` |
| `items[].cad_basis` | string |  |
| `items[].one_room_or_less_share` | number (nullable) | `one_room_or_less_share_basis` |
| `items[].one_room_or_less_share_basis` | string |  |
| `items[].dilapidated_share` | number (nullable) | `dilapidated_share_basis` |
| `items[].dilapidated_share_basis` | string |  |
| `items[].no_assets_share` | number (nullable) | `no_assets_share_basis` |
| `items[].no_assets_share_basis` | string |  |
| `items[].hardship` | number (nullable) | `hardship_basis` |
| `items[].hardship_basis` | string |  |
| `items[].critical_facilities` | null in the example (type: see the source dataclass) (nullable) | `critical_facilities_basis` |
| `items[].critical_facilities_basis` | string |  |


#### `GET /atlas/wards/{ward_id}`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** ward_evidence.csv row + data/derived/growth/growth.csv row for the same ward_id
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** `ward_id` (path, e.g. `relation/7848799`, URL-encoded)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`; 404 for an unknown ward
- **Basis:** `<field>_basis` columns of ward_evidence.csv and growth.csv (`basis`, `quality_flag`)
- **Example:** [`docs/api_examples/atlas_ward.get.json`](api_examples/atlas_ward.get.json) (REAL / DERIVED per *_basis column; growth row DERIVED (Open Buildings 2016-2023))

| Field | Type | Basis of numbers |
|---|---|---|
| `evidence` | object |  |
| `evidence.ward_id` | string |  |
| `evidence.ward_name` | string |  |
| `evidence.geo_version` | string |  |
| `evidence.census_year` | integer | see **Basis** |
| `evidence.source_district` | string |  |
| `evidence.source_ward_code` | string |  |
| `evidence.source_url` | string |  |
| `evidence.hh14_source_url` | string |  |
| `evidence.join_status` | string |  |
| `evidence.location_status` | string |  |
| `evidence.review_required` | boolean |  |
| `evidence.allocation_eligible` | boolean |  |
| `evidence.quality_flags` | string |  |
| `evidence.crosswalk_method` | string |  |
| `evidence.census_coverage` | number | see **Basis** |
| `evidence.dominant_source_share` | number | see **Basis** |
| `evidence.source_units` | string |  |
| `evidence.population` | integer | `population_basis` |
| `evidence.population_basis` | string |  |
| `evidence.households` | integer | `households_basis` |
| `evidence.households_basis` | string |  |
| `evidence.wad` | number | `wad_basis` |
| `evidence.wad_basis` | string |  |
| `evidence.non_tap_share` | number | `non_tap_share_basis` |
| `evidence.non_tap_share_basis` | string |  |
| `evidence.cad` | number | `cad_basis` |
| `evidence.cad_basis` | string |  |
| `evidence.one_room_or_less_share` | number | `one_room_or_less_share_basis` |
| `evidence.one_room_or_less_share_basis` | string |  |
| `evidence.dilapidated_share` | number | `dilapidated_share_basis` |
| `evidence.dilapidated_share_basis` | string |  |
| `evidence.no_assets_share` | number | `no_assets_share_basis` |
| `evidence.no_assets_share_basis` | string |  |
| `evidence.hardship` | number | `hardship_basis` |
| `evidence.hardship_basis` | string |  |
| `evidence.critical_facilities` | null in the example (type: see the source dataclass) (nullable) | `critical_facilities_basis` |
| `evidence.critical_facilities_basis` | string |  |
| `growth` | object |  |
| `growth.ward_id` | string |  |
| `growth.ward_name` | string |  |
| `growth.period_start` | integer | see **Basis** |
| `growth.period_end` | integer | see **Basis** |
| `growth.building_index_2016` | number | see **Basis** |
| `growth.building_index_2023` | number | see **Basis** |
| `growth.building_growth_ratio` | number | see **Basis** |
| `growth.annual_log_change_cv` | number | see **Basis** |
| `growth.adjusted_annual_growth` | number | see **Basis** |
| `growth.trend_t` | number | see **Basis** |
| `growth.growth_stability` | string |  |
| `growth.all_years_usable` | boolean |  |
| `growth.grid_metres` | integer | see **Basis** |
| `growth.census_location_status` | string |  |
| `growth.census_households_2011` | integer | see **Basis** |
| `growth.adjusted_current_households` | null in the example (type: see the source dataclass) (nullable) |  |
| `growth.connection_growth_2022_2025` | null in the example (type: see the source dataclass) (nullable) |  |
| `growth.booking_validation` | string |  |
| `growth.basis` | string |  |
| `growth.quality_flag` | string |  |


## 3. Equity

#### `GET /equity/summary`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** data/derived/equity/summary.json (whole file)
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** none
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`
- **Basis:** REAL HMWSSB section records; ratios DERIVED
- **Example:** [`docs/api_examples/equity_summary.get.json`](api_examples/equity_summary.get.json) (REAL HMWSSB section records; ratios DERIVED)

| Field | Type | Basis of numbers |
|---|---|---|
| `bookings` | integer | see **Basis** |
| `bottom_booking_share` | number | see **Basis** |
| `bottom_section_count` | integer | see **Basis** |
| `delivered` | integer | see **Basis** |
| `delivery_to_booking_ratio` | number | see **Basis** |
| `gini` | number | `gini_basis` |
| `gini_basis` | string |  |
| `interpretation` | string |  |
| `missing_source_months` | array |  |
| `missing_source_months[]` | string |  |
| `seasonality_caveat` | string |  |
| `section_count` | integer | see **Basis** |
| `section_rate_denominator` | string |  |
| `section_rate_source_url` | string |  |
| `source_row_count` | integer | see **Basis** |
| `source_url` | string |  |
| `top_booking_share` | number | see **Basis** |
| `top_fraction_requested` | number | see **Basis** |
| `top_section_count` | integer | see **Basis** |
| `ward_booking_share_placed` | number | see **Basis** |
| `ward_metrics_status` | string |  |
| `ward_rate_population` | string |  |


#### `GET /equity/sections?offset=0&limit=2`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** data/derived/equity/sections.csv
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** `offset`, `limit`
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`
- **Basis:** `count_basis` (counts) and `metric_basis` (ratios) columns
- **Example:** [`docs/api_examples/equity_sections.get.json`](api_examples/equity_sections.get.json) (count_basis / metric_basis columns)

| Field | Type | Basis of numbers |
|---|---|---|
| `total` | integer | see **Basis** |
| `offset` | integer | see **Basis** |
| `limit` | integer | see **Basis** |
| `items` | array |  |
| `items[]` | object |  |
| `items[].section` | string |  |
| `items[].division` | integer | see **Basis** |
| `items[].bookings` | integer | see **Basis** |
| `items[].delivered` | integer | see **Basis** |
| `items[].rank` | integer | see **Basis** |
| `items[].share` | number | see **Basis** |
| `items[].observed_months` | integer | see **Basis** |
| `items[].population` | null in the example (type: see the source dataclass) (nullable) |  |
| `items[].bookings_per_1000` | null in the example (type: see the source dataclass) (nullable) |  |
| `items[].domestic_connections_mean` | number | see **Basis** |
| `items[].flats_connection_share` | number | see **Basis** |
| `items[].bookings_per_1000_connections` | number | see **Basis** |
| `items[].denominator_status` | string |  |
| `items[].count_basis` | string |  |
| `items[].metric_basis` | string |  |


#### `GET /equity/wards?offset=0&limit=2`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** data/derived/equity/wards.csv
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** `offset`, `limit`
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`
- **Basis:** `basis` column (ward placement of sections is approximate)
- **Example:** [`docs/api_examples/equity_wards.get.json`](api_examples/equity_wards.get.json) (basis column)

| Field | Type | Basis of numbers |
|---|---|---|
| `total` | integer | see **Basis** |
| `offset` | integer | see **Basis** |
| `limit` | integer | see **Basis** |
| `items` | array |  |
| `items[]` | object |  |
| `items[].ward_id` | string |  |
| `items[].ward_name` | string |  |
| `items[].bookings` | integer (nullable) | see **Basis** |
| `items[].bookings_per_1000` | number (nullable) | see **Basis** |
| `items[].mapping_status` | string |  |
| `items[].census_join_status` | string |  |
| `items[].basis` | string |  |


## 4. Under-served and field-check list

#### `GET /underserved/field-checks`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** data/derived/underserved/field_checks.json: schema_version, summary, limitations, field_check_list, and rows (first row of the list shown)
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** none (PROPOSED filter: `field_check_candidate=true`)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`
- **Basis:** each value's `<field>_basis` field (REAL inputs, DERIVED flags, UNAVAILABLE where missing)
- **Example:** [`docs/api_examples/underserved_field_checks.get.json`](api_examples/underserved_field_checks.get.json) (each value's *_basis field (REAL inputs, DERIVED flags, UNAVAILABLE where missing))

| Field | Type | Basis of numbers |
|---|---|---|
| `schema_version` | string |  |
| `summary` | object |  |
| `summary.area_count` | integer | see **Basis** |
| `summary.data_review_count` | integer | see **Basis** |
| `summary.eligible_count` | integer | see **Basis** |
| `summary.field_check_count` | integer | see **Basis** |
| `summary.ground_truth_count` | integer | see **Basis** |
| `summary.real_world_accuracy` | null in the example (type: see the source dataclass) (nullable) |  |
| `summary.screened_count` | integer | see **Basis** |
| `summary.stability_evaluated` | boolean |  |
| `limitations` | array |  |
| `limitations[]` | string |  |
| `field_check_list` | array |  |
| `field_check_list[]` | object |  |
| `field_check_list[].action` | string |  |
| `field_check_list[].field_check_candidate` | boolean | `field_check_candidate_basis` |
| `field_check_list[].field_check_candidate_basis` | string |  |
| `field_check_list[].flagged_variants` | array |  |
| `field_check_list[].flagged_variants[]` | string |  |
| `field_check_list[].geography_version` | string |  |
| `field_check_list[].growth_quality` | string |  |
| `field_check_list[].growth_ratio_basis` | string |  |
| `field_check_list[].growth_ratio_context_only` | number | see **Basis** |
| `field_check_list[].input_basis` | string |  |
| `field_check_list[].input_notes` | array |  |
| `field_check_list[].input_notes[]` | string |  |
| `field_check_list[].model_scores` | object | `model_scores_basis` |
| `field_check_list[].model_scores.PEER_MEDIAN` | object |  |
| `field_check_list[].model_scores.PEER_MEDIAN.expected` | number | see **Basis** |
| `field_check_list[].model_scores.PEER_MEDIAN.interval_kind` | string |  |
| `field_check_list[].model_scores.PEER_MEDIAN.peers` | array |  |
| `field_check_list[].model_scores.PEER_MEDIAN.peers[]` | string |  |
| `field_check_list[].model_scores.PEER_MEDIAN.ratio` | number | see **Basis** |
| `field_check_list[].model_scores.PEER_MEDIAN.ratio_lower` | null in the example (type: see the source dataclass) (nullable) |  |
| `field_check_list[].model_scores.PEER_MEDIAN.ratio_upper` | null in the example (type: see the source dataclass) (nullable) |  |
| `field_check_list[].model_scores_basis` | string |  |
| `field_check_list[].observed_bookings` | integer | `observed_bookings_basis` |
| `field_check_list[].observed_bookings_basis` | string |  |
| `field_check_list[].reasons` | array |  |
| `field_check_list[].reasons[]` | object |  |
| `field_check_list[].reasons[].basis` | string |  |
| `field_check_list[].reasons[].code` | string |  |
| `field_check_list[].reasons[].model` | string |  |
| `field_check_list[].reasons[].threshold` | number | see **Basis** |
| `field_check_list[].reasons[].value` | number | see **Basis** |
| `field_check_list[].stability_evaluated` | boolean |  |
| `field_check_list[].status` | string |  |
| `field_check_list[].ward_id` | string |  |
| `field_check_list[].ward_name` | string |  |
| `rows` | array |  |
| `rows[]` | object |  |
| `rows[].action` | string |  |
| `rows[].field_check_candidate` | boolean | `field_check_candidate_basis` |
| `rows[].field_check_candidate_basis` | string |  |
| `rows[].flagged_variants` | array |  |
| `rows[].flagged_variants[]` | string |  |
| `rows[].geography_version` | string |  |
| `rows[].growth_quality` | string |  |
| `rows[].growth_ratio_basis` | string |  |
| `rows[].growth_ratio_context_only` | number | see **Basis** |
| `rows[].input_basis` | string |  |
| `rows[].input_notes` | array |  |
| `rows[].input_notes[]` | string |  |
| `rows[].model_scores` | object | `model_scores_basis` |
| `rows[].model_scores.PEER_MEDIAN` | object |  |
| `rows[].model_scores.PEER_MEDIAN.expected` | number | see **Basis** |
| `rows[].model_scores.PEER_MEDIAN.interval_kind` | string |  |
| `rows[].model_scores.PEER_MEDIAN.peers` | array |  |
| `rows[].model_scores.PEER_MEDIAN.peers[]` | string |  |
| `rows[].model_scores.PEER_MEDIAN.ratio` | number | see **Basis** |
| `rows[].model_scores.PEER_MEDIAN.ratio_lower` | null in the example (type: see the source dataclass) (nullable) |  |
| `rows[].model_scores.PEER_MEDIAN.ratio_upper` | null in the example (type: see the source dataclass) (nullable) |  |
| `rows[].model_scores_basis` | string |  |
| `rows[].observed_bookings` | integer | `observed_bookings_basis` |
| `rows[].observed_bookings_basis` | string |  |
| `rows[].reasons` | array |  |
| `rows[].reasons[]` | object |  |
| `rows[].reasons[].basis` | string |  |
| `rows[].reasons[].code` | string |  |
| `rows[].reasons[].model` | string |  |
| … | | 7 more fields: see the example file |


## 5. Coverage GeoJSON

#### `GET /coverage/layers`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** data/derived/coverage/layers.json (whole file)
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** none
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`
- **Basis:** as stated per layer in layers.json
- **Example:** [`docs/api_examples/coverage_layers.get.json`](api_examples/coverage_layers.get.json) (as stated per layer)

| Field | Type | Basis of numbers |
|---|---|---|
| `excluded_layers` | array |  |
| `excluded_layers[]` | object |  |
| `excluded_layers[].layer_id` | string |  |
| `excluded_layers[].reason` | string |  |
| `feature_count` | integer | see **Basis** |
| `geography_version` | string |  |
| `interpretation` | string |  |
| `layers` | array |  |
| `layers[]` | object |  |
| `layers[].feature_count` | integer | see **Basis** |
| `layers[].file` | string |  |
| `layers[].layer_id` | string |  |
| `layers[].non_null_value_count` | integer | see **Basis** |
| `layers[].operational_use` | boolean |  |
| `schema_version` | string |  |


#### `GET /coverage/layers/{layer_id} (GeoJSON)`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** data/derived/coverage/water_access_evidence.geojson; one feature shown (the file has all wards)
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** `layer_id` (path; one of the ids in layers.json)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`; 404 for an unknown layer
- **Basis:** `value_basis` property of each feature (for example DERIVED_HISTORICAL_APPROXIMATE)
- **Example:** [`docs/api_examples/coverage_layer.get.json`](api_examples/coverage_layer.get.json) (value_basis property per feature)

| Field | Type | Basis of numbers |
|---|---|---|
| `geography_version` | string |  |
| `layer_id` | string |  |
| `operational_use` | boolean |  |
| `schema_version` | string |  |
| `source_task` | string |  |
| `title` | string |  |
| `type` | string |  |
| `value_field` | string |  |
| `value_status` | string |  |
| `features` | array |  |
| `features[]` | object |  |
| `features[].geometry` | object |  |
| `features[].geometry.coordinates` | array |  |
| `features[].geometry.coordinates[]` | array |  |
| `features[].geometry.coordinates[][]` | array |  |
| `features[].geometry.coordinates[][][]` | number | see **Basis** |
| `features[].geometry.type` | string |  |
| `features[].properties` | object |  |
| `features[].properties.allocation_eligible` | boolean |  |
| `features[].properties.display_status` | string |  |
| `features[].properties.layer_id` | string |  |
| `features[].properties.location_status` | string |  |
| `features[].properties.reference_year` | integer | see **Basis** |
| `features[].properties.value_basis` | string |  |
| `features[].properties.ward_id` | string |  |
| `features[].properties.ward_name` | string |  |
| `features[].properties.water_access_deficit_share` | number | see **Basis** |
| `features[].type` | string |  |


## 6. Forecast

#### `GET /forecast?level=city|section&section=`

- **Status:** **PROPOSED, service not merged (T2 on feat/t2-forecast, local).**
- **Built from:** feat/t2-forecast: data/derived/forecast_table.csv (scripts/forecast/run_backtest.py, services/forecast.py)
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** `level` (`city` | `section`), `section` (optional), `month` (optional, `YYYY-MM`)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`
- **Basis:** `point_basis`, `lower_80_basis`, `upper_80_basis`, `lower_90_basis`, `upper_90_basis` columns (DERIVED; city intervals UNAVAILABLE)
- **Example:** [`docs/api_examples/forecast.get.json`](api_examples/forecast.get.json) (point_basis / lower_*_basis / upper_*_basis columns (DERIVED; city intervals UNAVAILABLE))
- **Notes:** Rows typed by the CSV rule (see api_shapes.md); first 3 city rows and 2 section rows.
- **Limits:** section names are from before the Feb/Mar 2026 re-cut; city rows have no interval (section intervals do not add up); trips per day for capacity is OPEN.

| Field | Type | Basis of numbers |
|---|---|---|
| `items` | array |  |
| `items[]` | object |  |
| `items[].level` | string |  |
| `items[].section` | string (nullable) |  |
| `items[].month` | string |  |
| `items[].model` | string |  |
| `items[].point` | number | `point_basis` |
| `items[].point_basis` | string |  |
| `items[].lower_80` | number (nullable) | `lower_80_basis` |
| `items[].upper_80` | number (nullable) | `upper_80_basis` |
| `items[].lower_80_basis` | string |  |
| `items[].upper_80_basis` | string |  |
| `items[].lower_90` | number (nullable) | `lower_90_basis` |
| `items[].upper_90` | number (nullable) | `upper_90_basis` |
| `items[].lower_90_basis` | string |  |
| `items[].upper_90_basis` | string |  |
| `total` | integer | see **Basis** |


#### `GET /forecast/backtest`

- **Status:** **PROPOSED, service not merged (T2 on feat/t2-forecast, local).**
- **Built from:** feat/t2-forecast: data/derived/forecast_backtest.csv (summary rows shown)
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** none
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`
- **Basis:** `city_mape_basis`, `section_wape_basis`, `coverage_basis` columns (DERIVED)
- **Example:** [`docs/api_examples/forecast_backtest.get.json`](api_examples/forecast_backtest.get.json) (*_basis columns (DERIVED))

| Field | Type | Basis of numbers |
|---|---|---|
| `items` | array |  |
| `items[]` | object |  |
| `items[].run` | string |  |
| `items[].row_type` | string |  |
| `items[].model` | string |  |
| `items[].origin` | string (nullable) |  |
| `items[].months` | integer | see **Basis** |
| `items[].section_months` | integer | see **Basis** |
| `items[].city_mape` | number | `city_mape_basis` |
| `items[].city_mape_basis` | string |  |
| `items[].section_wape` | number | `section_wape_basis` |
| `items[].section_wape_basis` | string |  |
| `items[].interval` | null in the example (type: see the source dataclass) (nullable) |  |
| `items[].coverage` | null in the example (type: see the source dataclass) (nullable) | `coverage_basis` |
| `items[].coverage_basis` | null in the example (type: see the source dataclass) (nullable) |  |
| `items[].note` | null in the example (type: see the source dataclass) (nullable) |  |
| `total` | integer | see **Basis** |


## 7. Shortage

#### `GET /shortage`

- **Status:** **NOT DESIGNED, P3 (T8, not started).**
- **Built from:** nothing yet
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** not designed
- **Errors:** not designed
- **Basis:** not designed
- **Example:** [`docs/api_examples/shortage.get.json`](api_examples/shortage.get.json) (placeholder)
- **Notes:** T8 is not started. T2's capacity_plan (local) refuses to run without a sourced trips-per-tanker-per-day value.

_No fields: not designed._


## 8. Plan (queue, schedule, outage)

A7's `build_plan` returns a `DailyPlan`. The queue is `stations[*].served` / `waiting` (A3 order), the schedule is `scheduled` (A4 `WardShare` per ward) with `special_stops` / `unrouted`, the outage response is `outage` (A5 `OutageResponse`). There is **no plan store on main**: plans live in memory, so T10 needs one (P2 / P3) before these routes can work across requests. How a plan is created (scheduled job at 05:00 or an officer request) is not decided.

#### `GET /plans/{plan_id}`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/planner.py build_plan -> DailyPlan (StationPlan, ServedBooking, Transfer, WardShare, OutageResponse, Assessment, Unrouted, SpecialStop); scripts/sandbox/build_planner_replay.py replay(max_days=1)
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** `plan_id` (path)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`; 404 for an unknown plan
- **Basis:** SIMULATION in the example (replay); in use: trips and counts REAL operations data, entitlement DERIVED, flags PROVISIONAL until T9; the `basis` object names each
- **Example:** [`docs/api_examples/plan.get.json`](api_examples/plan.get.json) (SIMULATION: A7 build_plan on the first day of P2's committed planner replay)
- **Notes:** Lists are cut to the first items; *_total fields give the full counts. queue_states is internal and not shown.

| Field | Type | Basis of numbers |
|---|---|---|
| `plan_id` | string |  |
| `day` | string |  |
| `status` | string |  |
| `digest` | string |  |
| `reserve_trips` | integer | see **Basis** |
| `outage_trips` | integer | see **Basis** |
| `special_tankers` | array |  |
| `approved_by` | null in the example (type: see the source dataclass) (nullable) |  |
| `approval_reason` | null in the example (type: see the source dataclass) (nullable) |  |
| `stations` | object |  |
| `stations.ST01` | object |  |
| `stations.ST01.station` | string |  |
| `stations.ST01.trips` | integer | see **Basis** |
| `stations.ST01.booked_trips` | integer | see **Basis** |
| `stations.ST01.lent` | integer | see **Basis** |
| `stations.ST01.borrowed` | integer | see **Basis** |
| `stations.ST01.served` | array |  |
| `stations.ST01.served[]` | object |  |
| `stations.ST01.served[].booking_id` | string |  |
| `stations.ST01.served[].group` | string |  |
| `stations.ST01.served[].position` | integer | see **Basis** |
| `stations.ST01.served[].reason` | string |  |
| `stations.ST01.served[].lender` | null in the example (type: see the source dataclass) (nullable) |  |
| `stations.ST01.waiting` | array |  |
| `stations.ST01.served_total` | integer | see **Basis** |
| `stations.ST01.waiting_total` | integer | see **Basis** |
| `stations.ST02` | object |  |
| `stations.ST02.station` | string |  |
| `stations.ST02.trips` | integer | see **Basis** |
| `stations.ST02.booked_trips` | integer | see **Basis** |
| `stations.ST02.lent` | integer | see **Basis** |
| `stations.ST02.borrowed` | integer | see **Basis** |
| `stations.ST02.served` | array |  |
| `stations.ST02.served[]` | object |  |
| `stations.ST02.served[].booking_id` | string |  |
| `stations.ST02.served[].group` | string |  |
| `stations.ST02.served[].position` | integer | see **Basis** |
| `stations.ST02.served[].reason` | string |  |
| `stations.ST02.served[].lender` | null in the example (type: see the source dataclass) (nullable) |  |
| `stations.ST02.waiting` | array |  |
| `stations.ST02.waiting[]` | string |  |
| `stations.ST02.served_total` | integer | see **Basis** |
| `stations.ST02.waiting_total` | integer | see **Basis** |
| `stations_total` | integer | see **Basis** |
| `transfers` | array |  |
| `transfers[]` | object |  |
| `transfers[].lender` | string |  |
| `transfers[].borrower` | string |  |
| `transfers[].trips` | integer | see **Basis** |
| `transfers[].round_trip_km` | number | see **Basis** |
| `transfers_total` | integer | see **Basis** |
| `scheduled` | object |  |
| `scheduled.relation/7848824` | object |  |
| `scheduled.relation/7848824.ward_id` | string |  |
| `scheduled.relation/7848824.litres` | number | see **Basis** |
| `scheduled.relation/7848824.floor` | number | see **Basis** |
| `scheduled.relation/7848824.target` | number | see **Basis** |
| `scheduled.relation/7848824.status` | string |  |
| `scheduled.relation/7848859` | object |  |
| `scheduled.relation/7848859.ward_id` | string |  |
| `scheduled.relation/7848859.litres` | number | see **Basis** |
| `scheduled.relation/7848859.floor` | number | see **Basis** |
| `scheduled.relation/7848859.target` | number | see **Basis** |
| `scheduled.relation/7848859.status` | string |  |
| `scheduled_total` | integer | see **Basis** |
| `outage` | object |  |
| `outage.critical` | array |  |
| `outage.allocations` | array |  |
| `outage.ended` | array |  |
| `outage.unused_litres` | integer | see **Basis** |
| `outage.counts_toward_water_debt` | boolean |  |
| `outage.basis` | object |  |
| `outage.basis.people` | string |  |
| `outage.basis.lpcd` | string |  |
| `outage.basis.priority` | string |  |
| `effective_entitlement` | object |  |
| `effective_entitlement.section:40 MLD STP ATTAPUR` | number | see **Basis** |
| `effective_entitlement.section:ADARSHNAGAR` | number | see **Basis** |
| `effective_entitlement.section:ADIBATLA (PD 1)` | number | see **Basis** |
| `flags` | object |  |
| … | | 30 more fields: see the example file |


#### `GET /plans/{plan_id}/confidence`

- **Status:** **PROPOSED, service not merged (T9 on feat/t9-confidence, local).**
- **Built from:** feat/t9-confidence: services/confidence.py T9Gate.explain -> Combined (SignalScore); data/derived/confidence_calibration.csv selection row
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** `plan_id` (path)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`
- **Basis:** confidence DERIVED from REAL P1 files; threshold PROVISIONAL; calibration SIMULATION
- **Example:** [`docs/api_examples/plan_confidence.get.json`](api_examples/plan_confidence.get.json) (DERIVED from REAL P1 files; threshold PROVISIONAL (calibration not_separable, SIMULATION))
- **Notes:** Three groups of replay day 1: an unplaced section, a mixed-source ward, a ward above the threshold.
- **Limits:** T9's threshold 0.50 is a placeholder (calibration `not_separable`); three of the five signals are unavailable and are listed, never scored 0.

| Field | Type | Basis of numbers |
|---|---|---|
| `threshold` | number | `threshold_basis` |
| `threshold_basis` | string |  |
| `calibration` | object |  |
| `calibration.row_type` | string |  |
| `calibration.threshold` | number | see **Basis** |
| `calibration.group_days` | integer | see **Basis** |
| `calibration.unflagged_group_days` | integer | see **Basis** |
| `calibration.matched_unflagged` | integer | see **Basis** |
| `calibration.match_share` | number | `match_share_basis` |
| `calibration.match_share_basis` | string |  |
| `calibration.groups` | integer | see **Basis** |
| `calibration.flagged_groups` | integer | see **Basis** |
| `calibration.flagged_share` | number | `flagged_share_basis` |
| `calibration.flagged_share_basis` | string |  |
| `calibration.status` | string |  |
| `calibration.label` | string |  |
| `groups` | array |  |
| `groups[]` | object |  |
| `groups[].group` | string |  |
| `groups[].confidence` | number | see **Basis** |
| `groups[].needs_check` | boolean |  |
| `groups[].reason` | string |  |
| `groups[].used` | array |  |
| `groups[].used[]` | string |  |
| `groups[].unavailable` | array |  |
| `groups[].unavailable[]` | string |  |
| `groups[].signals` | array |  |
| `groups[].signals[]` | object |  |
| `groups[].signals[].name` | string |  |
| `groups[].signals[].available` | boolean |  |
| `groups[].signals[].score` | number (nullable) | see **Basis** |
| `groups[].signals[].basis` | string |  |


## 9. Approve

#### `POST /plans/{plan_id}/groups/{group}/check`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/planner.py mark_checked -> DailyPlan.checked; ledger event ward_reviewed (reason stored as sha256 + length only)
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** `plan_id`, `group` (path); body `officer_id` (string), `reason` (string, required, not blank)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`; a blank reason or an unflagged group raises `ValueError` in `mark_checked` (PROPOSED: 422 `validation_error`)
- **Basis:** no numbers except `ledger_seq` (DERIVED)
- **Example:** [`docs/api_examples/plan_check.post.json`](api_examples/plan_check.post.json) (SIMULATION plan (replay day 1); SYNTHETIC officer reason)

| Field | Type | Basis of numbers |
|---|---|---|
| `plan_id` | string |  |
| `group` | string |  |
| `checked` | boolean |  |
| `unchecked_flags` | array |  |
| `unchecked_flags[]` | string |  |
| `ledger_seq` | integer | see **Basis** |
| `ledger_event` | string |  |


#### `POST /plans/{plan_id}/approve`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/planner.py approve_plan: raises PlanBlocked while flagged groups are unchecked; shown as HTTPException(409, detail=<message>) through the existing handler in app/errors.py; ValueError for a missing reason or an approved plan
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** `plan_id` (path); body `officer_id` (string), `reason` (string, required)
- **Errors:** 409 `conflict` while flagged groups are unchecked (`PlanBlocked`, shown) or when already approved; 422 for a blank reason
- **Basis:** no numbers in the error; a success returns the plan (section 8)
- **Example:** [`docs/api_examples/plan_approve.post.json`](api_examples/plan_approve.post.json) (SIMULATION plan (replay day 1))
- **Notes:** Response shows the blocked case: one group checked, the others not. A success returns the plan with status APPROVED, approved_by and approval_reason.

| Field | Type | Basis of numbers |
|---|---|---|
| `http_status` | integer | see **Basis** |
| `body` | object |  |
| `body.error` | object |  |
| `body.error.code` | string |  |
| `body.error.message` | string |  |
| `body.error.details` | null in the example (type: see the source dataclass) (nullable) |  |


## 10. Explain (ward and booking)

#### `GET /explain/wards/{ward_id}?lang=te`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/explain.py explain_ward -> WardExplanation; render_ward(e, lang) -> text
- **Roles (PROPOSED, T10 step 3):** officer, resident
- **Request:** `ward_id` (path), `lang` (query)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`; 404 for an unknown ward
- **Basis:** the explanation's `<field>_basis` fields; `entitlement` DERIVED (A2)
- **Example:** [`docs/api_examples/explain_ward.get.json`](api_examples/explain_ward.get.json) (REAL ward_evidence.csv row; need and entitlement DERIVED (A2); *_basis per value)

| Field | Type | Basis of numbers |
|---|---|---|
| `explanation` | object |  |
| `explanation.ward_id` | string |  |
| `explanation.ward_name` | string |  |
| `explanation.status` | string |  |
| `explanation.service_class` | string |  |
| `explanation.class_basis` | string |  |
| `explanation.join_status` | string |  |
| `explanation.allocation_eligible` | boolean |  |
| `explanation.review_required` | boolean |  |
| `explanation.quality_flags` | array |  |
| `explanation.quality_flags[]` | string |  |
| `explanation.check_reasons` | array |  |
| `explanation.check_reasons[]` | string |  |
| `explanation.census_label` | string |  |
| `explanation.need_weight` | number | see **Basis** |
| `explanation.need_basis` | string |  |
| `explanation.wad` | number | `wad_basis` |
| `explanation.wad_basis` | string |  |
| `explanation.cad` | number | `cad_basis` |
| `explanation.cad_basis` | string |  |
| `explanation.hardship` | number | `hardship_basis` |
| `explanation.hardship_basis` | string |  |
| `explanation.households` | integer | `households_basis` |
| `explanation.households_basis` | string |  |
| `explanation.entitlement` | number | see **Basis** |
| `explanation.critical_facilities` | null in the example (type: see the source dataclass) (nullable) | `critical_facilities_basis` |
| `explanation.critical_facilities_basis` | string |  |
| `explanation.debt` | object |  |
| `explanation.debt.available` | boolean |  |
| `explanation.debt.account_id` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.debt.debt_litres` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.debt.cap_litres` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.debt.in_debt_since` | null in the example (type: see the source dataclass) (nullable) |  |
| `text` | object |  |
| `text.lang` | string |  |
| `text.body` | string |  |


#### `GET /explain/wards/{ward_id}?lang=en (ward without Census data)`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** explain_ward -> WardExplanation(status=no_census_data)
- **Roles (PROPOSED, T10 step 3):** officer, resident
- **Request:** as above
- **Errors:** as above
- **Basis:** values UNAVAILABLE (`null`); `status` = `no_census_data`, so no number is shown
- **Example:** [`docs/api_examples/explain_ward_no_census.get.json`](api_examples/explain_ward_no_census.get.json) (REAL ward_evidence.csv row with empty Census values)

| Field | Type | Basis of numbers |
|---|---|---|
| `explanation` | object |  |
| `explanation.ward_id` | string |  |
| `explanation.ward_name` | string |  |
| `explanation.status` | string |  |
| `explanation.service_class` | string |  |
| `explanation.class_basis` | string |  |
| `explanation.join_status` | string |  |
| `explanation.allocation_eligible` | boolean |  |
| `explanation.review_required` | boolean |  |
| `explanation.quality_flags` | array |  |
| `explanation.quality_flags[]` | string |  |
| `explanation.check_reasons` | array |  |
| `explanation.check_reasons[]` | string |  |
| `explanation.census_label` | string |  |
| `explanation.need_weight` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.need_basis` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.wad` | null in the example (type: see the source dataclass) (nullable) | `wad_basis` |
| `explanation.wad_basis` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.cad` | null in the example (type: see the source dataclass) (nullable) | `cad_basis` |
| `explanation.cad_basis` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.hardship` | null in the example (type: see the source dataclass) (nullable) | `hardship_basis` |
| `explanation.hardship_basis` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.households` | null in the example (type: see the source dataclass) (nullable) | `households_basis` |
| `explanation.households_basis` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.entitlement` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.critical_facilities` | null in the example (type: see the source dataclass) (nullable) | `critical_facilities_basis` |
| `explanation.critical_facilities_basis` | string |  |
| `explanation.debt` | object |  |
| `explanation.debt.available` | boolean |  |
| `explanation.debt.account_id` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.debt.debt_litres` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.debt.cap_litres` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.debt.in_debt_since` | null in the example (type: see the source dataclass) (nullable) |  |
| `text` | object |  |
| `text.lang` | string |  |
| `text.body` | string |  |


#### `GET /explain/bookings/{booking_id}?lang=hi`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/explain.py explain_booking -> BookingExplanation; find_counterfactual -> Counterfactual (Change); render_booking / render_counterfactual
- **Roles (PROPOSED, T10 step 3):** officer, resident (own booking only)
- **Request:** `booking_id` (path), `lang` (query)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`; 404 for an unknown booking
- **Basis:** DERIVED from A3 on the plan's queue day; SIMULATION in the example
- **Example:** [`docs/api_examples/explain_booking.get.json`](api_examples/explain_booking.get.json) (SIMULATION booking (A8 replay day 1; SYNTHETIC arrival, REAL monthly total); explanation DERIVED from A3)
- **Notes:** Queue of filling station ST19 on 2025-03-01 with capacity = the plan's booked_trips (215, after the scheduled reserve; raw capacity 226), A3 state at its start; the served set equals the plan's. waiting_hours is negative because the replay's 05:00 plan already holds bookings that arrive later that day (finding for P2 / T7, not a display rule).
- **Note:** the queue day must use the plan's `booked_trips` (capacity after the scheduled reserve), not the raw station capacity, or the explanation disagrees with the plan; the example checks the served set equals the plan's.

| Field | Type | Basis of numbers |
|---|---|---|
| `explanation` | object |  |
| `explanation.booking_id` | string |  |
| `explanation.status` | string |  |
| `explanation.group` | string |  |
| `explanation.tier` | integer | see **Basis** |
| `explanation.arrived_at` | string |  |
| `explanation.place` | integer | see **Basis** |
| `explanation.position` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.reason` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.arrival_rank` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.entitlement` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.quantum` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.deficit_before` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.capacity` | integer | see **Basis** |
| `explanation.cap_reason` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.waiting_hours` | number | see **Basis** |
| `explanation.debt` | object |  |
| `explanation.debt.available` | boolean |  |
| `explanation.debt.account_id` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.debt.debt_litres` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.debt.cap_litres` | null in the example (type: see the source dataclass) (nullable) |  |
| `explanation.debt.in_debt_since` | null in the example (type: see the source dataclass) (nullable) |  |
| `counterfactual` | object |  |
| `counterfactual.booking_id` | string |  |
| `counterfactual.status` | string |  |
| `counterfactual.before_place` | integer | see **Basis** |
| `counterfactual.changes` | array |  |
| `counterfactual.changes[]` | object |  |
| `counterfactual.changes[].input` | string |  |
| `counterfactual.changes[].amount` | integer or number | see **Basis** |
| `counterfactual.changes[].step` | integer or number | see **Basis** |
| `counterfactual.changes[].from_value` | integer or number or string | see **Basis** |
| `counterfactual.changes[].to_value` | integer or number or string | see **Basis** |
| `counterfactual.changes[].after_place` | integer | see **Basis** |
| `counterfactual.not_inputs` | array |  |
| `counterfactual.not_inputs[]` | array |  |
| `counterfactual.not_inputs[][]` | string |  |
| `text` | object |  |
| `text.lang` | string |  |
| `text.body` | string |  |
| `text.counterfactual` | string |  |


## 11. Contest and reply

#### `POST /contests`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/contest.py ContestService.file -> ContestResult; ledger contest_filed (text as sha256 + length)
- **Roles (PROPOSED, T10 step 3):** resident (and councillor, not a T10 role)
- **Request:** body `filed_by` (string), `role` (`resident` | `councillor`), `target_type` (`ward` | `booking`), `target_id` (string), `reason_code` (`ranking_wrong` | `need_data_wrong` | `service_class_wrong` | `delivery_not_received` | `other`), `reason_text` (string, required)
- **Errors:** HTTP 200 with `status: invalid` and `error` (service behaviour); 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`
- **Basis:** `ledger_seq` DERIVED; the text is stored once, the ledger holds its sha256 and length
- **Example:** [`docs/api_examples/contests.post.json`](api_examples/contests.post.json) (SYNTHETIC request; response from the real ContestService on a temporary database)

| Field | Type | Basis of numbers |
|---|---|---|
| `status` | string |  |
| `contest_id` | string |  |
| `reply_id` | null in the example (type: see the source dataclass) (nullable) |  |
| `ledger_seq` | integer | see **Basis** |
| `error` | null in the example (type: see the source dataclass) (nullable) |  |


#### `POST /contests/{contest_id}/reply`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** ContestService.reply -> ContestResult; ledger contest_replied
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** `contest_id` (path); body `officer_id`, `outcome_code` (`ranking_stands` | `ranking_changed` | `data_corrected` | `referred`), `reason_text` (required)
- **Errors:** HTTP 200 with `status` `invalid`, `not_found` or `already_replied` (service behaviour)
- **Basis:** `ledger_seq` DERIVED
- **Example:** [`docs/api_examples/contest_reply.post.json`](api_examples/contest_reply.post.json) (SYNTHETIC request; real ContestService)

| Field | Type | Basis of numbers |
|---|---|---|
| `status` | string |  |
| `contest_id` | string |  |
| `reply_id` | string |  |
| `ledger_seq` | integer | see **Basis** |
| `error` | null in the example (type: see the source dataclass) (nullable) |  |


## 12. Ledger list and verify

#### `GET /ledger/entries?after_seq=0&limit=2`

- **Status:** **Route on main.**
- **Built from:** app/routers/ledger.py list_entries() -> StoredLedger.page -> LedgerEntry + key_id
- **Roles (PROPOSED, T10 step 3):** officer (verify could be public: open question)
- **Request:** `after_seq` (integer >= 0, default 0), `limit` (1 to `TRUST_CONFIG.ledger_list_max_limit`, default 100)
- **Errors:** 422 `validation_error` for a bad `after_seq` / `limit`
- **Basis:** `seq` DERIVED (chain order); payload numbers carry the basis of the event that wrote them
- **Example:** [`docs/api_examples/ledger_entries.get.json`](api_examples/ledger_entries.get.json) (Entries written by the notice example above (SYNTHETIC notice) to a temporary stored ledger)
- **Note:** `payload` keys depend on `event_type` (ids, codes and numbers only; no free text, no phone numbers).

| Field | Type | Basis of numbers |
|---|---|---|
| `entries` | array |  |
| `entries[]` | object |  |
| `entries[].seq` | integer | see **Basis** |
| `entries[].event_type` | string |  |
| `entries[].entity_type` | string |  |
| `entries[].entity_id` | string |  |
| `entries[].payload` | object |  |
| `entries[].prev_hash` | string |  |
| `entries[].hash` | string |  |
| `entries[].signature` | string |  |
| `entries[].created_at_iso` | string |  |
| `entries[].key_id` | string |  |


#### `GET /ledger/verify`

- **Status:** **Route on main.**
- **Built from:** app/routers/ledger.py verify() -> StoredLedger.verify -> ChainCheck
- **Roles (PROPOSED, T10 step 3):** officer (or public)
- **Request:** none
- **Errors:** none expected (a broken chain is `valid: false` with `reason` and `broken_at`)
- **Basis:** `checked`, `head_seq`, `broken_at` DERIVED
- **Example:** [`docs/api_examples/ledger_verify.get.json`](api_examples/ledger_verify.get.json) (Same temporary ledger)

| Field | Type | Basis of numbers |
|---|---|---|
| `valid` | boolean |  |
| `checked` | integer | see **Basis** |
| `broken_at` | null in the example (type: see the source dataclass) (nullable) |  |
| `reason` | null in the example (type: see the source dataclass) (nullable) |  |
| `head_seq` | integer | see **Basis** |
| `head_hash` | string |  |
| `detail` | null in the example (type: see the source dataclass) (nullable) |  |


## 13. Delivery (OTP, outcome)

T3's service holds an immutable `DeliveryState`; there is **no delivery store on main**. Responses are a projection of `DeliveryState`: representative and resident phone numbers, the OTP nonce and hash, and the code itself are never returned. Outcomes are capitalised: `Confirmed` | `Disputed` | `Unconfirmed` | `Failed`. Only `Confirmed` counts toward water debt (`counts_toward_debt`).

#### `POST /deliveries`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/delivery.py start_delivery -> DeliveryState (projection: representatives, phones, OTP nonce and hash are never returned)
- **Roles (PROPOSED, T10 step 3):** driver
- **Request:** body `delivery_id`, `stop_id`, `driver_id` (the stop's location and 2-3 registered representatives come from the stop record, server-side)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`; `start_delivery` raises `ValueError` without 2-3 representatives
- **Basis:** SYNTHETIC in the example; `geofence_radius_m` null = config 150 m (REAL rule, F12)
- **Example:** [`docs/api_examples/delivery_start.post.json`](api_examples/delivery_start.post.json) (SYNTHETIC stop and driver; real T3 service)

| Field | Type | Basis of numbers |
|---|---|---|
| `delivery_id` | string |  |
| `stop_id` | string |  |
| `driver_id` | string |  |
| `started_at` | string |  |
| `geofence_radius_m` | null in the example (type: see the source dataclass) (nullable) |  |
| `otp_issued` | boolean |  |
| `otp_expires_at` | null in the example (type: see the source dataclass) (nullable) |  |
| `otp_digits` | null in the example (type: see the source dataclass) (nullable) |  |
| `wrong_attempts` | integer | see **Basis** |
| `outside_tries` | integer | see **Basis** |
| `otp_verified` | boolean |  |
| `sampled_residents` | integer | see **Basis** |
| `replies` | integer | see **Basis** |
| `outcome` | null in the example (type: see the source dataclass) (nullable) |  |


#### `POST /deliveries/{delivery_id}/otp`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/delivery.py request_otp -> DeliveryState
- **Roles (PROPOSED, T10 step 3):** driver
- **Request:** `delivery_id` (path); body `representative_id`
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`
- **Basis:** `otp_digits` ASSUMED / OPEN (config)
- **Example:** [`docs/api_examples/delivery_otp_request.post.json`](api_examples/delivery_otp_request.post.json) (SYNTHETIC; real T3 service; the code goes to the representative by SMS (template delivery.otp), never in the response)

| Field | Type | Basis of numbers |
|---|---|---|
| `delivery_id` | string |  |
| `stop_id` | string |  |
| `driver_id` | string |  |
| `started_at` | string |  |
| `geofence_radius_m` | null in the example (type: see the source dataclass) (nullable) |  |
| `otp_issued` | boolean |  |
| `otp_expires_at` | string |  |
| `otp_digits` | integer | see **Basis** |
| `wrong_attempts` | integer | see **Basis** |
| `outside_tries` | integer | see **Basis** |
| `otp_verified` | boolean |  |
| `sampled_residents` | integer | see **Basis** |
| `replies` | integer | see **Basis** |
| `outcome` | null in the example (type: see the source dataclass) (nullable) |  |


#### `POST /deliveries/{delivery_id}/otp/verify`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/delivery.py verify_otp -> (DeliveryState, VerifyResult); locate -> LocationCheck
- **Roles (PROPOSED, T10 step 3):** driver
- **Request:** `delivery_id` (path); body `code` (string), `lat`, `lon` (numbers, the driver's position)
- **Errors:** HTTP 200 with `result` one of `verified`, `already_verified`, `wrong_code`, `expired`, `locked`, `outside_geofence`, `invalid_location`, `no_otp`
- **Basis:** `distance_m` DERIVED (haversine); `radius_m` config
- **Example:** [`docs/api_examples/delivery_otp_verify.post.json`](api_examples/delivery_otp_verify.post.json) (SYNTHETIC positions; real T3 geofence and OTP check)
- **Notes:** Two calls: first from about 1.1 km away (outside_geofence, counts as an outside try, not an attempt), then inside with the right code (verified). The code is never echoed.

_The example shows several calls; fields are those of one call._

| Field | Type | Basis of numbers |
|---|---|---|
| `result` | string |  |
| `location` | object |  |
| `location.status` | string |  |
| `location.inside` | boolean |  |
| `location.distance_m` | number | see **Basis** |
| `location.radius_m` | integer | see **Basis** |
| `location.reason` | null in the example (type: see the source dataclass) (nullable) |  |
| `delivery` | object |  |
| `delivery.delivery_id` | string |  |
| `delivery.stop_id` | string |  |
| `delivery.driver_id` | string |  |
| `delivery.started_at` | string |  |
| `delivery.geofence_radius_m` | null in the example (type: see the source dataclass) (nullable) |  |
| `delivery.otp_issued` | boolean |  |
| `delivery.otp_expires_at` | string |  |
| `delivery.otp_digits` | integer | see **Basis** |
| `delivery.wrong_attempts` | integer | see **Basis** |
| `delivery.outside_tries` | integer | see **Basis** |
| `delivery.otp_verified` | boolean |  |
| `delivery.sampled_residents` | integer | see **Basis** |
| `delivery.replies` | integer | see **Basis** |
| `delivery.outcome` | null in the example (type: see the source dataclass) (nullable) |  |


#### `POST /deliveries/{delivery_id}/replies (SMS reply webhook)`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/delivery.py send_resident_check, parse_reply, record_response -> (DeliveryState, counted)
- **Roles (PROPOSED, T10 step 3):** SMS gateway (not a T10 role)
- **Request:** SMS reply webhook: sender (mapped to a sampled resident server-side) and `text`: one digit, `1` = yes, `2` = no, in any script
- **Errors:** a reply that is not counted gives `counted: false` (wrong text, outside the window, not sampled, second reply)
- **Basis:** counts DERIVED
- **Example:** [`docs/api_examples/delivery_reply.post.json`](api_examples/delivery_reply.post.json) (SYNTHETIC residents and replies; real T3 sampling and reply parsing)
- **Notes:** Resident ids only; the webhook would map the sender's number to a resident id server-side. A reply is one digit: 1 = yes, 2 = no, in any script; here 1, Telugu 1 and 2.

| Field | Type | Basis of numbers |
|---|---|---|
| `replies` | array |  |
| `replies[]` | object |  |
| `replies[].resident_id` | string |  |
| `replies[].text` | string |  |
| `replies[].counted` | boolean |  |
| `delivery` | object |  |
| `delivery.delivery_id` | string |  |
| `delivery.stop_id` | string |  |
| `delivery.driver_id` | string |  |
| `delivery.started_at` | string |  |
| `delivery.geofence_radius_m` | null in the example (type: see the source dataclass) (nullable) |  |
| `delivery.otp_issued` | boolean |  |
| `delivery.otp_expires_at` | string |  |
| `delivery.otp_digits` | integer | see **Basis** |
| `delivery.wrong_attempts` | integer | see **Basis** |
| `delivery.outside_tries` | integer | see **Basis** |
| `delivery.otp_verified` | boolean |  |
| `delivery.sampled_residents` | integer | see **Basis** |
| `delivery.replies` | integer | see **Basis** |
| `delivery.outcome` | null in the example (type: see the source dataclass) (nullable) |  |


#### `GET /deliveries/{delivery_id}`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/delivery.py close_delivery / compute_outcome -> OutcomeDecision; counts_toward_debt(outcome)
- **Roles (PROPOSED, T10 step 3):** officer, driver
- **Request:** `delivery_id` (path)
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (wrong role), 404 `not_found`, 422 `validation_error`; codes come from the HTTP status phrase in `app/errors.py`; 404 unknown delivery
- **Basis:** `outcome.basis` (DERIVED: F12 table)
- **Example:** [`docs/api_examples/delivery_outcome.get.json`](api_examples/delivery_outcome.get.json) (SYNTHETIC; outcome DERIVED by the T3 table (OTP x resident majority))

| Field | Type | Basis of numbers |
|---|---|---|
| `delivery_id` | string |  |
| `stop_id` | string |  |
| `driver_id` | string |  |
| `started_at` | string |  |
| `geofence_radius_m` | null in the example (type: see the source dataclass) (nullable) |  |
| `otp_issued` | boolean |  |
| `otp_expires_at` | string |  |
| `otp_digits` | integer | see **Basis** |
| `wrong_attempts` | integer | see **Basis** |
| `outside_tries` | integer | see **Basis** |
| `otp_verified` | boolean |  |
| `sampled_residents` | integer | see **Basis** |
| `replies` | integer | see **Basis** |
| `outcome` | object |  |
| `outcome.outcome` | string |  |
| `outcome.rule` | string |  |
| `outcome.otp_verified` | boolean |  |
| `outcome.yes` | integer | see **Basis** |
| `outcome.no` | integer | see **Basis** |
| `outcome.silent` | integer | see **Basis** |
| `outcome.basis` | string |  |
| `counts_toward_debt` | boolean |  |


## 14. Intake (all channels, batch sync)

#### `POST /intake/batch`

- **Status:** **Route on main.**
- **Built from:** app/routers/intake.py batch() -> services/intake_pipeline.py IntakeService.receive_batch -> IntakeResult
- **Roles (PROPOSED, T10 step 3):** resident, field worker (not a T10 role)
- **Request:** body `items` (array, at most `INTAKE_CONFIG.max_batch_items`); each item: `channel` (`app` | `field_worker`; `voice` is multipart, `sms` / `missed_call` have their own routes), `client_id` (string, idempotency key), `category` (`no_water` | `tanker_missed` | `dirty_water` | `leak` | `other`, optional), `text` (optional), `lat` + `lon` (together, optional; `lng` also accepted), `language_hint` (optional, max 8 chars), `client_created_at` (ISO 8601, optional), `household_id`, `reporter_id`, `area_id` (optional; a field-worker item needs `reporter_id` and `household_id` or `lat` / `lon`), `is_synthetic` (boolean)
- **Errors:** per item: `status` `invalid` with `error`; 422 `validation_error` if the body is not `{items: [...]}` or too long
- **Basis:** `spam_score` DERIVED (A1 rules); `ledger_seq` DERIVED
- **Example:** [`docs/api_examples/intake_batch.post.json`](api_examples/intake_batch.post.json) (SYNTHETIC request; response from the real IntakeService on a temporary database)
- **Notes:** Item 4 resends item 1's client_id (status duplicate); item 5 has an unknown channel (status invalid).
- **Statuses:** `created` (new complaint), `merged` (linked to an earlier complaint: `parent_id`), `duplicate` (the same `client_id` was already received: nothing new stored), `spam`, `invalid`. `complaint_status`: `open` | `awaiting_location` | `needs_transcription`.

| Field | Type | Basis of numbers |
|---|---|---|
| `results` | array |  |
| `results[]` | object |  |
| `results[].status` | string |  |
| `results[].client_id` | string |  |
| `results[].intake_id` | string (nullable) |  |
| `results[].complaint_id` | string (nullable) |  |
| `results[].complaint_status` | string (nullable) |  |
| `results[].parent_id` | null in the example (type: see the source dataclass) (nullable) |  |
| `results[].category` | string (nullable) |  |
| `results[].language` | string (nullable) |  |
| `results[].spam_score` | number (nullable) | see **Basis** |
| `results[].error` | string (nullable) |  |
| `results[].ledger_seq` | integer (nullable) | see **Basis** |


#### `POST /intake/sms`

- **Status:** **Route on main.**
- **Built from:** app/routers/intake.py sms_webhook() -> IntakeService.receive_sms -> IntakeResult
- **Roles (PROPOSED, T10 step 3):** SMS gateway (shared secret: open question)
- **Request:** provider's own field names: sender `from` | `sender` | `msisdn` | `mobile` | `phone` | `source`; text `body` | `text` | `message` | `content` | `msg`; time `timestamp` | `received_at` | `time` | `date` (config/intake.py)
- **Errors:** HTTP 200 with `status: invalid` when sender or text is missing
- **Basis:** as batch
- **Example:** [`docs/api_examples/intake_sms.post.json`](api_examples/intake_sms.post.json) (SYNTHETIC request; response from the real IntakeService)
- **Notes:** Sender field names accepted: config/intake.py SMS_SENDER_FIELDS / SMS_TEXT_FIELDS / SMS_TIME_FIELDS. The example was generated with an all-zero placeholder number.

| Field | Type | Basis of numbers |
|---|---|---|
| `status` | string |  |
| `client_id` | null in the example (type: see the source dataclass) (nullable) |  |
| `intake_id` | string |  |
| `complaint_id` | string |  |
| `complaint_status` | string |  |
| `parent_id` | null in the example (type: see the source dataclass) (nullable) |  |
| `category` | string |  |
| `language` | string |  |
| `spam_score` | number | see **Basis** |
| `error` | null in the example (type: see the source dataclass) (nullable) |  |
| `ledger_seq` | integer | see **Basis** |


#### `POST /intake/missed-call`

- **Status:** **Route on main.**
- **Built from:** app/routers/intake.py missed_call() -> IntakeService.receive_missed_call -> IntakeResult
- **Roles (PROPOSED, T10 step 3):** telephony gateway
- **Request:** caller field `caller` | `from` | `msisdn` | `mobile` | `phone` | `cli`
- **Errors:** HTTP 200 with `status: invalid` without a caller number
- **Basis:** category ASSUMED `no_water`
- **Example:** [`docs/api_examples/intake_missed_call.post.json`](api_examples/intake_missed_call.post.json) (SYNTHETIC request; response from the real IntakeService)
- **Notes:** Caller field names: config/intake.py CALLER_FIELDS. Category is ASSUMED no_water; the service asks back for the location.

| Field | Type | Basis of numbers |
|---|---|---|
| `status` | string |  |
| `client_id` | null in the example (type: see the source dataclass) (nullable) |  |
| `intake_id` | string |  |
| `complaint_id` | string |  |
| `complaint_status` | string |  |
| `parent_id` | null in the example (type: see the source dataclass) (nullable) |  |
| `category` | string |  |
| `language` | null in the example (type: see the source dataclass) (nullable) |  |
| `spam_score` | number | see **Basis** |
| `error` | null in the example (type: see the source dataclass) (nullable) |  |
| `ledger_seq` | integer | see **Basis** |


#### `POST /intake/voice (multipart: audio file + fields)`

- **Status:** **From main**: the service or file is on `main`; the route is not built (T10).
- **Built from:** services/intake_pipeline.py IntakeService.receive_voice -> IntakeResult
- **Roles (PROPOSED, T10 step 3):** resident, field worker
- **Request:** multipart: audio file (`audio/webm` etc., size-limited) + `lat`, `lon`, `language_hint`, `category`, `client_id`, `client_created_at`, `household_id`, `reporter_id`, `is_synthetic`
- **Errors:** HTTP 200 with `status: invalid` (empty, too large, unsupported type)
- **Basis:** transcript confidence from the model, `null` when unavailable
- **Example:** [`docs/api_examples/intake_voice.post.json`](api_examples/intake_voice.post.json) (SYNTHETIC audio bytes; response from the real IntakeService.receive_voice with the fallback transcriber)

| Field | Type | Basis of numbers |
|---|---|---|
| `status` | string |  |
| `client_id` | string |  |
| `intake_id` | string |  |
| `complaint_id` | string |  |
| `complaint_status` | string |  |
| `parent_id` | null in the example (type: see the source dataclass) (nullable) |  |
| `category` | string |  |
| `language` | string |  |
| `spam_score` | number | see **Basis** |
| `error` | null in the example (type: see the source dataclass) (nullable) |  |
| `ledger_seq` | integer | see **Basis** |


## 15. Notices

#### `POST /notices`

- **Status:** **Route on main.**
- **Built from:** app/routers/notices.py enter_notice() -> services/notices.py NoticeService.enter -> NoticeResult (AreaMatch, OutageEvent)
- **Roles (PROPOSED, T10 step 3):** officer
- **Request:** body `source` (`hmwssb_press_release` | `hmwssb_website` | `hmwssb_sms` | `officer_report`), `raw_text` (required), `area_names` (non-empty array of text), `start`, `end` (ISO 8601 with a time zone; end after start), `entered_by` (officer id), `source_ref` (optional), `people_affected` (optional number), `is_synthetic`
- **Errors:** HTTP 200 with `status: invalid` and `error`; statuses `created` (outage made), `needs_review` (no ward matched), `duplicate`, `invalid`
- **Basis:** `people_affected_basis`; `matched[].confidence` DERIVED (1.0 exact, else difflib); `hours` DERIVED
- **Example:** [`docs/api_examples/notices.post.json`](api_examples/notices.post.json) (SYNTHETIC notice text; area matching against the REAL section_to_ward_2016.csv / ward geojson; people_affected from the REAL Census 2011 ward population (DERIVED))

| Field | Type | Basis of numbers |
|---|---|---|
| `status` | string |  |
| `notice_id` | string |  |
| `outage_id` | string |  |
| `ward_ids` | array |  |
| `ward_ids[]` | string |  |
| `matched` | array |  |
| `matched[]` | object |  |
| `matched[].name` | string |  |
| `matched[].status` | string |  |
| `matched[].ward_id` | string |  |
| `matched[].ward_name` | string |  |
| `matched[].confidence` | number | see **Basis** |
| `matched[].method` | string |  |
| `matched[].reason` | null in the example (type: see the source dataclass) (nullable) |  |
| `matched[].suggestion` | null in the example (type: see the source dataclass) (nullable) |  |
| `flagged` | array |  |
| `flagged[]` | object |  |
| `flagged[].name` | string |  |
| `flagged[].status` | string |  |
| `flagged[].ward_id` | null in the example (type: see the source dataclass) (nullable) |  |
| `flagged[].ward_name` | null in the example (type: see the source dataclass) (nullable) |  |
| `flagged[].confidence` | number | see **Basis** |
| `flagged[].method` | null in the example (type: see the source dataclass) (nullable) |  |
| `flagged[].reason` | string |  |
| `flagged[].suggestion` | string |  |
| `hours` | number | see **Basis** |
| `people_affected` | number | `people_affected_basis` |
| `people_affected_basis` | string |  |
| `needs_officer_review` | boolean |  |
| `outage` | object |  |
| `outage.outage_id` | string |  |
| `outage.ward_ids` | array |  |
| `outage.ward_ids[]` | string |  |
| `outage.start` | string |  |
| `outage.end` | string |  |
| `outage.source` | string |  |
| `outage.reason` | string |  |
| `outage.created_by` | string |  |
| `outage.people_affected` | number | see **Basis** |
| `outage.planned_hours` | number | see **Basis** |
| `ledger_seqs` | array |  |
| `ledger_seqs[]` | integer | see **Basis** |
| `error` | null in the example (type: see the source dataclass) (nullable) |  |


## 16. Ward report card and SMS summary

#### `GET /wards/{ward_id}/report-card`

- **Status:** **NOT DESIGNED, P4 / P2 to propose.**
- **Built from:** nothing yet
- **Roles (PROPOSED, T10 step 3):** resident / public (not designed)
- **Request:** not designed
- **Errors:** not designed
- **Basis:** not designed
- **Example:** [`docs/api_examples/ward_report_card.get.json`](api_examples/ward_report_card.get.json) (placeholder)
- **Notes:** F20: need, bookings, debt, deliveries, schedule; no service builds a report card.

_No fields: not designed._


#### `GET /wards/{ward_id}/sms-summary`

- **Status:** **NOT DESIGNED, P4 / P2 to propose.**
- **Built from:** nothing yet
- **Roles (PROPOSED, T10 step 3):** resident (not designed)
- **Request:** not designed
- **Errors:** not designed
- **Basis:** not designed
- **Example:** [`docs/api_examples/ward_sms_summary.get.json`](api_examples/ward_sms_summary.get.json) (placeholder)
- **Notes:** F20 SMS summary; no service or template exists.

_No fields: not designed._


## 17. Impact

#### `GET /impact`

- **Status:** **NOT DESIGNED, P4 / P2 to propose.**
- **Built from:** nothing yet
- **Roles (PROPOSED, T10 step 3):** officer / public (not designed)
- **Request:** not designed
- **Errors:** not designed
- **Basis:** not designed
- **Example:** [`docs/api_examples/impact.get.json`](api_examples/impact.get.json) (placeholder)
- **Notes:** F19 Impact page. A8's data/derived/sandbox/results.csv and summary.json (SIMULATION) exist on main and are the likely source; no shape agreed.

_No fields: not designed._


## Open questions for P4

Mismatches found on `main` (P4 files were not edited):

1. **Field-worker app reads `duplicate` as "merged"** (`frontend/src/FieldWorkerExperience.tsx`, sync result mapping). On the backend `duplicate` means "this `client_id` was already received; nothing new stored" (a resend), and `merged` means "linked to someone else's earlier complaint" (`parent_id`). Suggest showing `duplicate` as "already sent".
2. **Resident app shows `spam` as "Could not send"** (`frontend/src/ResidentExperience.tsx`). A spam-scored report is stored and logged (`complaint_marked_spam`), not rejected. Which wording?
3. **Delivery outcome codes:** U4 uses `confirmed` / `disputed` / `unconfirmed` / `failed`; T3 returns `Confirmed` / `Disputed` / `Unconfirmed` / `Failed`. U4 also takes resident feedback as a toggle on the driver's screen; in T3 residents answer by SMS (`1` / `2`) after sampling, and the outcome waits for the reply window. U4's OTP is 6 digits like T3 (`otp_digits` 6, OPEN).
4. **Field-worker `area_id` is free text** typed by the worker; the backend stores it as given. Should it be a ward id or HMWSSB section from P1's area tables?
5. **Names and types:** U5 / U6 snapshots use camelCase and renamed fields (`waterAccessDeficitShare`, `population2011`, `hardshipShare`) where E2 uses `wad`, `population`, `hardship` (and the coverage GeoJSON uses `water_access_deficit_share`). Proposal: the API keeps snake_case source names; P4 maps them, or we agree one list.
6. **U6 forecast fixture** (`scripts/frontend/build_u6_snapshot.py`) has hand-typed illustrative values labelled `SIMULATION`; SIMULATION is for replay output, so `SYNTHETIC` (or an agreed ILLUSTRATIVE label) fits better. U6 shows city 80% / 90% bands, while T2 has intervals per section only (city intervals UNAVAILABLE). U6 marks the 21.9% / 35.1% baseline `NOT_DOCUMENTED`; T2 recovered the protocol (21.89% / 35.12%, owner-confirmed) on its unmerged branch. T2's table covers Feb 2026 - Jan 2027 on pre-re-cut section names; U6 shows Oct - Dec 2026.
7. **Auth and roles:** simple bearer token per role (officer, driver, resident) plus a local dev token (T10 step 3)? Field workers, councillors (contests) and SMS / telephony gateways (webhooks, shared secret) are not among the three roles.
8. **Pagination:** cursor (`after_seq` + `limit`, as the ledger) or `offset` + `limit` + `total` for file-based lists?
9. **Language:** server-rendered text in `lang` (as T7 does), or template key + parameters for P4 to render (as notices and SMS do)? Fallback to `en` for an unsupported language.
10. **Flagged and unavailable values:** missing values are `null` with basis `UNAVAILABLE` (never 0); flagged plan groups carry `needs_check`, a reason and the signals used / unavailable. How should screens show them (badge, greyed value, reason on tap)?
11. **HTTP status for item errors:** keep HTTP 200 with `status: invalid` per item (needed for batches), or 4xx for single-item routes?
12. **Times:** UTC from services vs +05:30 in replay bookings: convert on the server or on the screen?

Not for P4 (noted for P2 / P3): no plan store and no delivery store on main; the explanation's queue day must use the plan's `booked_trips`; A8's replay day holds bookings that arrive after the 05:00 plan time, so T7's `waiting_hours` can be negative; A8's `data/derived/sandbox/results.csv` and `summary.json` (SIMULATION) exist and are the likely source for the Impact page.
