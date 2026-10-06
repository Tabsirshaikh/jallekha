# OSRM road legs: build log

Built 2026-10-06 11:14 UTC by `scripts/routing/build_osrm_legs.py`.

| Item | Value |
|---|---|
| Map | [https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf](https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf), Last-Modified Mon, 05 Oct 2026 14:34:07 GMT |
| Map size, SHA-256 | 557,911,797 bytes, `c3cb96f5f83168210f992e78fdf7ea4bfa79009dfbf29db63937576404c390cb` |
| Licence | OpenStreetMap contributors, ODbL 1.0 |
| Crop | bbox (78.1, 17.15, 78.75, 17.7) (lng/lat): 224,724 highways, 222 turn restrictions |
| Router | OSRM v26.10.0 prebuilt binaries, `profiles/car.lua` of the same tag, MLD |
| Points | 218 section points, 90 stations (data/derived/sandbox/section_points.csv, data/derived/sandbox/stations.csv) |
| Input SHA-256 | `data/derived/sandbox/section_points.csv` `490701a97a443bde...`, `data/derived/sandbox/stations.csv` `6232197e8f8b6605...` |
| Pairs with no route | 0 |
| Snap to road (m) | median 10.7, 90th percentile 46.0, max 587.7 |

Basis: DERIVED (OSRM shortest-time car route on OSM roads as mapped). Free-flow car speeds:
no traffic and no tanker (truck) limits, so minutes are optimistic. Points are the sandbox's
section points and ASSUMED stand-in stations, so the legs are road distances between assumed
places, not HMWSSB's real station-to-household trips.
