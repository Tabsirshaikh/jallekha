# D8 Daily weather, Hyderabad — Retrieval Log

**Dataset:** Open-Meteo historical weather API (ERA5-based reanalysis)
**Basis:** REAL (reanalysis at one point; not a station record)
**Licence:** CC BY 4.0, https://open-meteo.com/en/licence (attribution: Open-Meteo.com)
**Used by:** F5 gradient-boosting candidate (`backend/app/services/forecast.py`)

| Field | Value |
|---|---|
| Request | `https://archive-api.open-meteo.com/v1/archive?latitude=17.385&longitude=78.4867&start_date=2019-01-01&end_date=2026-09-30&daily=temperature_2m_max,precipitation_sum&timezone=Asia%2FKolkata` |
| Point | 17.385, 78.4867 (Hyderabad city centre), grid cell elevation 505.0 m |
| Period | 2019-01-01 to 2026-09-30 (2830 days) |
| Variables | daily maximum 2 m temperature (deg C), daily precipitation sum (mm) |
| Missing values | 0 |
| Retrieved | 2026-10-05 15:28 UTC |
| File | `open_meteo_hyderabad_daily.csv` |
| SHA-256 | `c72e6cc821f5e2897415ff842f73021ac4870f205321a01536f07e3b8f5d2b68` |

Re-run `python scripts/data/fetch_d8_weather.py --end 2026-09-30` to reproduce; later reanalysis
updates can change recent days slightly, so compare the checksum before replacing the file.
