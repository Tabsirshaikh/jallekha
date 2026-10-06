# D7 Groundwater Levels — Retrieval Log

**Dataset:** Telangana Groundwater Department / National Water Data Portal (NWDP)  
**Status:** TO FETCH (NWDP API requires registration; data format verification needed)  
**Basis:** TO FETCH — verified to exist, not yet downloaded  
**Used by:** F5 Surge Forecast covariate; F6 Shortage Early Warning

---

## Source

| Field | Value |
|---|---|
| Dataset name | Groundwater Level Monitoring Data, Telangana |
| Publisher | Central Ground Water Board (CGWB) / National Water Data Portal |
| Portal URL | https://nwdp.nwic.gov.in |
| Coverage | Telangana state; telemetry (six-hourly) and manual quarterly wells |
| Temporal coverage | ~2021–2025 (telemetry); quarterly since ~2000 (manual) |
| Format | CSV download (per station or bulk) |
| Licence | Government of India Open Data Licence (GODL) v1.0 |
| Verified to exist | 2026-10-01 (NWDP portal pages confirmed via JALLEKHA_FINAL_SOLUTION.md research) |

---

## Why Not Yet Downloaded

1. **Registration required:** NWDP requires a user account (https://nwdp.nwic.gov.in/register).
2. **Station list:** Must first retrieve the list of monitoring wells in Hyderabad / Ranga Reddy district, then download individual station CSVs or use the bulk export.
3. **API not fully documented:** No publicly documented REST endpoint for bulk download without UI interaction.

---

## Retrieval Steps

1. Register at https://nwdp.nwic.gov.in/register (free, government portal).
2. Navigate to: **Data Access → Groundwater Level → Telangana → Hyderabad / Ranga Reddy District**.
3. Download the **quarterly manual well data** for all wells in Hyderabad district and Ranga Reddy district, years 2019–2024 (CSV export).
4. Optionally: download the **six-hourly telemetry data** for the same period if available for Hyderabad wells.
5. Save files as:
   ```
   data/raw/d7_groundwater/telangana_gw_quarterly_<district>.csv
   data/raw/d7_groundwater/telangana_gw_telemetry_<district>.csv  (if available)
   ```

After download, add each file to `data/verification/d1_manifest.csv` with:
- `dataset_id`: `D7-GW-Quarterly-Hyderabad`, `D7-GW-Quarterly-Rangareddy`, etc.
- `basis`: `REAL`
- `license`: `GODL v1.0`
- `source_url`: `https://nwdp.nwic.gov.in`
- `retrieved_at_utc`: (timestamp of download)
- `sha256`: computed after download

---

## Columns to Expect (from CGWB documentation)

| Column | Description |
|---|---|
| `station_id` | Well/borehole identifier |
| `district` | District name |
| `mandal` / `tehsil` | Sub-district admin unit |
| `latitude`, `longitude` | Well location |
| `date` | Measurement date |
| `depth_to_water_level_mbgl` | Depth to water table in metres below ground level |

---

## Acceptance Criteria (for T2 and T8 tasks)

- Monthly mean depth-to-water-table per mandal for Hyderabad / Ranga Reddy.
- Must cover at least Jan 2022 – Feb 2024 (overlap with D1 HMWSSB period).
- Anomaly = monthly z-score > 1.5 (configurable in `config/evidence.py`).
- All derived anomaly values carry `_basis = "DERIVED"`.

---

## Fallback (if NWDP data cannot be retrieved)

Per F6 design: if no machine-readable groundwater source is verified, the shortage early warning uses **forecast demand vs capacity only** (no groundwater covariate). This fallback is documented in `config/evidence.py` under `GROUNDWATER_AVAILABLE = False`.

---

## Known Limitations

- Manual quarterly wells are sparse; interpolation to mandal level introduces uncertainty (label DERIVED).
- Telemetry wells may not be in the most water-stressed areas.
- Reservoir levels (D15) are tracked separately (Q2 decision pending).
