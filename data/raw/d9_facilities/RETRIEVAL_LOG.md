# D9 Health facilities, schools and care homes (OpenStreetMap) — Retrieval Log

**Dataset:** OpenStreetMap features via the Overpass API
**Basis:** REAL as mapped in OSM (incomplete: a ward with none mapped may still have some)
**Licence:** ODbL 1.0, (c) OpenStreetMap contributors, https://www.openstreetmap.org/copyright
**Used by:** F1 critical facilities (E2), F8 tier 0 and F10 candidate critical stops

| Field | Value |
|---|---|
| Endpoint | `https://overpass-api.de/api/interpreter` |
| Area | 2016 ward layer bounding box + 0.005 deg: (17.2866, 78.2668, 17.5658, 78.6262) (south, west, north, east) |
| OSM data as of | 2026-10-05T18:46:51Z |
| Retrieved | 2026-10-05 18:49 UTC |
| Features | 2242 (nodes, and ways and relations at their centre) |
| File | `osm_facilities.csv` |
| SHA-256 | `ffe088e6aa205c13e0252e8d44ea4f22c2e0cb5228221538169aa156dab848bd` |

Query:

```
[out:json][timeout:300];(nwr["amenity"~"^(hospital|clinic|doctors|school|nursing_home|social_facility)$"](17.2866,78.2668,17.5658,78.6262);nwr["healthcare"~"^(hospital|clinic|doctor|centre)$"](17.2866,78.2668,17.5658,78.6262););out center tags;
```

The original D9 snapshot (885 / 310 / 350 / 399 / 59 in the solution document) and its query
were never found (`data/verification/SOURCES.md`), so this is a fresh pull with our own tag
choices; `scripts/evidence/build_facilities.py` documents them and compares the totals.
OSM changes daily: re-running gives a different file, so compare before replacing it.
