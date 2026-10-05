# API additions: D9 facility counts and candidate critical stops (F1, F8 tier 0, F10; item 15)

`docs/openapi.json` is regenerated (`python scripts/api/export_openapi.py`). Example:
`docs/api_examples/facility_candidates.get.json` (REAL OSM features, ward placement DERIVED).

## Where the data comes from

```
scripts/data/fetch_d9_facilities.py ──► data/raw/d9_facilities/osm_facilities.csv (+ RETRIEVAL_LOG.md)
scripts/evidence/build_facilities.py ──► ward_facilities.csv (counts per 2016 ward)
                                     └─► facility_points.csv (each feature with its ward)
scripts/evidence/build_evidence.py   ──► ward_evidence.csv critical_facilities (DERIVED)
```

Categories (a feature counts once, in this order): `uphcs` (a health feature named UPHC, PHC,
Urban/Primary Health Centre or Basti Dawakhana), `hospitals`, `clinics`, `schools`, `care_homes`.

## Atlas and explanations

`GET /atlas/wards`, `GET /atlas/wards/{ward_id}` and `GET /explain/wards/{ward_id}` now return
`critical_facilities` (the sum of the five counts) with `critical_facilities_basis: "DERIVED"` for
every ward, including wards without Census data. The quality flag `FACILITIES_UNAVAILABLE` is
replaced by `FACILITIES_OSM_INCOMPLETE`: zero mapped in OpenStreetMap is not zero present.

## `GET /facilities/candidates?ward_id={ward_id}&offset=&limit=` (officer)

Read-only. The OSM facilities placed in the ward, as candidate critical (tier-0) stops for F10.
Nothing becomes a stop until an officer registers one (`POST /stops`) at a candidate's position.

| Field | Meaning |
|---|---|
| `status` | always `CANDIDATE_OFFICER_CONFIRMATION_REQUIRED` |
| `counts` | per category; `counts_basis` REAL (as mapped in OSM), `placement_basis` DERIVED |
| `items[]` | `osm_ref` (`node/123`), `osm_type`, `osm_id`, `osm_url`, `category`, `name` (text or null), `lat`, `lon`, `basis` REAL, `ward_id`, `ward_basis` DERIVED |
| order | hospitals, UPHCs, clinics, care homes, then schools (likeliest tier-0 stops first) |
| errors | 404 for a ward not in the ward table; 403 for any role but officer |
