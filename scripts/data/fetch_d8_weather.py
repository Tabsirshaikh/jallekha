"""Fetch D8: daily weather for Hyderabad from the Open-Meteo historical weather API (REAL).

Writes data/raw/d8_weather/open_meteo_hyderabad_daily.csv (one row per day: date, maximum
temperature in deg C, precipitation in mm) and RETRIEVAL_LOG.md with the request and SHA-256.
Open-Meteo's archive is ERA5-based reanalysis (CC BY 4.0, https://open-meteo.com/en/licence);
one point at the city centre stands for the city. Used by the F5 gradient-boosting candidate.

    python scripts/data/fetch_d8_weather.py [--end YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data/raw/d8_weather"
OUT = OUT_DIR / "open_meteo_hyderabad_daily.csv"
API = "https://archive-api.open-meteo.com/v1/archive"
# Hyderabad city centre (Charminar area); the same point the solution doc uses for the city.
LAT, LON = 17.385, 78.4867
START = date(2019, 1, 1)  # three years before the first booking month (Jan 2022)
VARIABLES = ("temperature_2m_max", "precipitation_sum")


def fetch(start: date, end: date) -> tuple[str, dict]:
    url = (
        f"{API}?latitude={LAT}&longitude={LON}&start_date={start}&end_date={end}"
        f"&daily={','.join(VARIABLES)}&timezone=Asia%2FKolkata"
    )
    with urllib.request.urlopen(url, timeout=120) as response:
        return url, json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    # The archive lags a few days behind today; default to the end of last full month.
    first_of_month = date.today().replace(day=1)
    parser.add_argument("--end", type=date.fromisoformat, default=first_of_month - timedelta(1))
    args = parser.parse_args()
    url, data = fetch(START, args.end)
    daily = data["daily"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["date", "tmax_c", "precip_mm"])
        for day, tmax, rain in zip(
            daily["time"],
            daily["temperature_2m_max"],
            daily["precipitation_sum"],
            strict=True,
        ):
            writer.writerow([day, "" if tmax is None else tmax, "" if rain is None else rain])
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    rows = len(daily["time"])
    missing = sum(v is None for k in VARIABLES for v in daily[k])
    (OUT_DIR / "RETRIEVAL_LOG.md").write_text(
        f"""# D8 Daily weather, Hyderabad — Retrieval Log

**Dataset:** Open-Meteo historical weather API (ERA5-based reanalysis)
**Basis:** REAL (reanalysis at one point; not a station record)
**Licence:** CC BY 4.0, https://open-meteo.com/en/licence (attribution: Open-Meteo.com)
**Used by:** F5 gradient-boosting candidate (`backend/app/services/forecast.py`)

| Field | Value |
|---|---|
| Request | `{url}` |
| Point | {LAT}, {LON} (Hyderabad city centre), grid cell elevation {data.get("elevation")} m |
| Period | {START} to {args.end} ({rows} days) |
| Variables | daily maximum 2 m temperature (deg C), daily precipitation sum (mm) |
| Missing values | {missing} |
| Retrieved | {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")} |
| File | `open_meteo_hyderabad_daily.csv` |
| SHA-256 | `{digest}` |

Re-run `python scripts/data/fetch_d8_weather.py --end {args.end}` to reproduce; later reanalysis
updates can change recent days slightly, so compare the checksum before replacing the file.
""",
        encoding="utf-8",
    )
    print(f"Wrote {OUT} ({rows} days, {missing} missing values, sha256 {digest[:12]})")


if __name__ == "__main__":
    main()
