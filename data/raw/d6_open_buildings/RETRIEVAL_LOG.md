# D6 Open Buildings Temporal — Retrieval Log

**Dataset:** Google Open Buildings 2.5D Temporal  
**Status:** TO FETCH (requires Earth Engine or HDX account authentication)  
**Basis:** TO FETCH — verified to exist, not yet downloaded  
**Used by:** F2 Growth Adjustment (E3)

---

## Source

| Field | Value |
|---|---|
| Dataset name | Google Open Buildings 2.5D Temporal |
| Publisher | Google Research |
| Coverage | Global, including India, annual 2016–2023 |
| Resolution | ~4 m effective |
| Format | Cloud-optimised GeoTIFF (per-tile) via Earth Engine; CSV tiles via HDX |
| Earth Engine asset | `GOOGLE/Research/open-buildings-temporal/v1` |
| HDX page | https://data.humdata.org/dataset/open-buildings-temporal-india |
| Google product page | https://sites.research.google/gr/open-buildings/temporal |
| Licence | CC BY 4.0 |
| Verified to exist | 2026-10-01 (product page and EE catalogue confirmed) |

---

## Why Not Yet Downloaded

Access requires one of:
1. **Google Earth Engine** — authenticated GEE account with `earthengine-api` Python client; export a per-ward building-count raster for Hyderabad bbox (17.20,78.20,17.65,78.70), years 2016–2023.
2. **HDX / direct tiles** — CSV tile downloads at https://data.humdata.org/dataset/open-buildings-temporal-india require browsing and selecting the correct tile.

Neither path is scriptable without credentials. This file documents the retrieval steps so any team member with an EE account can complete the fetch.

---

## Retrieval Steps (Earth Engine)

```python
import ee
ee.Initialize()

collection = ee.ImageCollection("GOOGLE/Research/open-buildings-temporal/v1")
# Select building_presence band, filter years
for year in range(2016, 2024):
    img = collection.filter(ee.Filter.calendarRange(year, year, "year")).first()
    # Export to GCS then download, or use .getDownloadURL() for small tiles
```

Store the output GeoTIFF per year as:
```
data/raw/d6_open_buildings/ghmc_building_count_<YYYY>.tif
```

Then add each file to `data/verification/d1_manifest.csv` with:
- `dataset_id`: `D6-OpenBuildings-<YYYY>`
- `basis`: `REAL`
- `license`: `CC BY 4.0`
- `source_url`: `https://earthengine.google.com/`
- `retrieved_at_utc`: (timestamp of download)
- `sha256`: computed after download

---

## Acceptance Criteria (for E3 task)

- Building-count raster or CSV for Hyderabad bbox, each year 2016–2023.
- Growth ratio per ward = (count_2023 − count_2016) / count_2016.
- All derived ward-level ratios must carry `_basis = "DERIVED"`.
- Validation: ward growth ratio correlated with HMWSSB booking growth by section (E3 done-when).

---

## Known Limitations

- Open Buildings uses satellite imagery, not ground survey; building count is a proxy for household growth.
- Some wards may not align exactly to the 2016 GHMC ward polygons (DataMeet D2).
- Demolition/reconstruction is not separately distinguishable from new construction.
