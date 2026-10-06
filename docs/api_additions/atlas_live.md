# GET /atlas/live (officer)

Census need per ward plus five live clues that say where need may be rising now, and booking
concentration from the bookings officers supply each day. Service: `services/live_need.py`;
thresholds: `config/live_need.py` (all ASSUMED). Used by the U5 need map and the officer overview.

Census 2011 need cannot be re-measured daily. The live part is built from data the system already
records: water still owed (F11 debt accounts), bookings in the last 30 days against the ward's
usual month (2022-24 history / 25 months), "no water" complaints in the last 7 days (F14,
`complaint.area_id`), supply notices overlapping the last 7 days (F15), and the median groundwater
anomaly of the ward's sections (D7, latest month). A clue with no data is `known: false` and never
bad (owed is unknown until an officer has closed a day; bookings until bookings are supplied).
Groundwater has `counts: false`: shown as background, never counted. A ward is `rising` when at
least `min_bad_clues` (2) counted clues are bad; `known_count` says how many counted clues have data.

Concentration uses the distinct bookings (by id) stored in supplied plans that arrived in the last
30 days; with none it uses the 2022-24 section totals (`source: "history"`).

```json
{
  "as_of": "2026-10-06T12:00:00+00:00",
  "window_days": 30,
  "min_bad_clues": 2,
  "wards": [
    {
      "ward_id": "relation/7848824",
      "name": "Ward 105 Gachibowli",
      "need": {"wad": 0.08, "cad": 0.05, "hardship": 0.09, "households": 31000},
      "bookings_window": 0,
      "usual_month_bookings": 2657.2,
      "clues": [
        {"code": "owed", "bad": false, "known": true, "value": 0.0, "reference": 0.0},
        {"code": "bookings", "bad": false, "known": true, "value": 0, "reference": 3985.9},
        {"code": "complaints", "bad": false, "known": true, "value": 0, "reference": 3},
        {"code": "cuts", "bad": false, "known": true, "value": 0, "reference": 1},
        {"code": "groundwater", "bad": false, "known": true, "value": 0.4, "reference": 1.0}
      ],
      "bad_count": 0,
      "rising": false
    }
  ],
  "concentration": {
    "source": "history", "live_bookings": 0, "unplaced_bookings": 0,
    "gini": 0.78, "top_share": 0.677, "top_sections": 21, "sections": 201, "bookings": 1316215,
    "top": [{"section": "MADHAPUR", "bookings": 135332, "share": 0.1028}]
  }
}
```

Values: `owed` in tanker loads (5,000 l), `bookings` a count (reference = usual month x 1.5),
`complaints` and `cuts` counts, `groundwater` metres deeper than the same month in earlier years.
