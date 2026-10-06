# F5/F6 refresh contract (2026-10-06)

PROPOSED: implemented on local `feat/f5-forecast-refresh`; owner approval pending.

All routes require an officer token. Pagination uses `offset` and `limit` (maximum 200); clients
fetch successive pages until `total` is reached.

- `GET /forecast?level=city|section&section=<name>` keeps point and 80/90 bound fields and their
  basis columns. Adds `updated_through`, `match_status` and `capacity_trips` with its basis.
  City bounds calibrate city residuals directly, independently of section intervals. An
  unmatched section has null point, bounds and capacity with UNAVAILABLE reasons.
- `GET /forecast/history?level=city|section&section=<name>` serves `month`, `level`, `section`,
  `actual` and `actual_basis`. Last twelve available months. Exact city totals include all
  portal rows; historical section identity is approximate across the re-cut.
- `GET /forecast/accuracy?level=city|section&section=<name>` serves `month`, `level`, `section`,
  `point`, `actual`, signed `error_pct`, `capacity_trips`, and numeric basis fields. These are
  retrospective rolling-origin estimates using only earlier records, not previously issued
  forecasts. Missing identity is excluded rather than displayed as an invented zero.
- `GET /forecast/backtest` adds city coverage rows and the current fixed-candidate selection
  evaluation. Section evaluation only scores pairs whose identity exists in both periods.
- `GET /shortage` retains the existing shape. Includes unknown warnings for unmatched sections;
  reservoir status is DERIVED when the accepted source is present. Reservoir percentages are
  contextual monthly observations and never alter the capacity risk rule.

`python scripts/forecast/refresh_forecast.py` fetches only new portal months, checks the accepted
reservoir catalogue, trains through the latest published month, and rewrites forecast, capacity,
history, accuracy, crosswalk, evaluation and shortage outputs. Add `--offline` to reproduce from
committed raw bytes. The refresh also rebuilds the UI fallback automatically.

After changes to A8 station assignments or capacities, run
`python scripts/forecast/refresh_forecast.py --capacity-only`. It updates forecast capacities,
city capacity totals, shortage reasons/ratios and `u6Forecast.json` together from the existing
forecast and conservative crosswalk. It does not fetch data, retrain, change predicted bookings
or recalculate intervals. Section capacity remains the documented ASSUMED A8 split. Run the
shortage reproduction and current-input capacity tests after any A8 rebuild.
Raw reservoir provenance is in `data/verification/reservoir_manifest.csv`; the global manifest
is unchanged. Legacy `run_backtest.py --out-dir ...` remains a historical protocol comparator,
not the publishing command.

Section name/division matches are correspondence only: changed divisions and OLD/NEW aliases
are approximate, their historical points do not establish new boundaries, and ambiguous names
remain unmatched. Every old history is used at most once. Exact city totals are independent of
the incomplete section cohort, so matched section forecasts do not sum to the city forecast.

Conformal measured coverage is reported honestly in LIMITATIONS F5; one-step calibration is
applied across twelve forecast months, not a claim of calibrated multi-step coverage. Fleet
and capacity transfers retain their ASSUMED/DERIVED labels in data and API; screens use plain
words in English, Telugu, Urdu and Hindi.
