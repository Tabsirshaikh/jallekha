# S2 source register

**Retrieval basis:** Exact source bytes downloaded on 2026-10-01. The legacy `research-data/` archive and `V-VERIFY_REVIEW.md` named in the planning documents were not present in the local v1 checkout, the old public prototype, the new repository, or the wider project directory. These files are therefore described as **rehydrated from their documented public sources**, not “ported unchanged.”

`source_manifest.csv` is the authoritative file-level register. It records the source URL, retrieval timestamp, source modification time where available, licence/terms status, geography, granularity, basis, byte size, SHA-256 checksum and limitations. Run:

```bash
python scripts/data/verify_manifest.py
```

## Included

| IDs | Files | Source | Status |
|---|---:|---|---|
| D1 | 26 monthly CSVs, Jan 2022-Feb 2024 | [OpenCity HMWSSB tanker dataset](https://data.opencity.in/dataset/hyderabad-water-supply-through-tankers-data) | REAL source bytes; December 2022 retained |
| D2 | DataMeet README, ward and zone GeoJSON | [DataMeet Municipal Spatial Data](https://github.com/datameet/Municipal_Spatial_Data/tree/master/Hyderabad) | REAL historical community/OSM geometry; CC BY 4.0; 145 ward features; not current official boundaries |
| D3 | Hyderabad PCA CSV and HH-14 XLSX | [OpenCity Hyderabad Census 2011](https://data.opencity.in/dataset/hyderabad-census-2011-data) | REAL Census mirror; public-domain label on portal |
| D4 | Rangareddy PCA and HH-14 XLSX | [Census NADA PCA catalog 6728](https://censusindia.gov.in/nada/index.php/catalog/6728), [HH-14 catalog 9835](https://censusindia.gov.in/nada/index.php/catalog/9835) | REAL official catalog downloads; source attribution required |

## Not included and why

- **D9 OSM facilities:** the previously verified snapshot was not found. A fresh OSM query would be new D1 fetch work and would not be an unchanged S2 port.
- **D12 Nominatim section coordinates:** this was a derived file and the original queries/results were not found. It must be regenerated with per-match provenance and review during the spatial pipeline.
- **D13 Chicago 311 calibration extract:** the exact prior query and frozen extract were not found. The live source changes over time, so a new download cannot be represented as the previous verified 31,098-row snapshot.
- **`V-VERIFY_REVIEW.md`:** no source copy was found. Its reported checks are not reproduced or claimed here.

No hand-typed analytical values or v1 prototype tables are included. Derived tables must be written outside `data/raw/` and must carry basis and quality fields.

## Added after S2

| IDs | Files | Source | Status |
|---|---:|---|---|
| D1b | 56 monthly CSVs, Jan 2022-Aug 2026, plus portal metadata JSON, in `data/raw/hmwssb_tankers_portal/` | [Telangana Open Data Portal, HMWSSB water tankers data](https://data.telangana.gov.in/api/1/metastore/schemas/dataset/items/7f408a3a-7cdb-4d33-bfa3-1869f88c0e25) | REAL source bytes; Open Government License, India; same columns as D1 and identical on all 26 overlapping months; sections re-cut Feb/Mar 2026, so 2026 is a new section geography. Register: `hmwssb_portal_manifest.csv`; checked by `backend/tests/test_d1b_portal.py`; fetched by `scripts/data/fetch_hmwssb_portal.py` |
