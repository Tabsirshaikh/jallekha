"""Locate each mandal of the TGDPS weather data (D8b) on OpenStreetMap, via Nominatim.

The station files name a district and mandal but give no coordinates. Each (district, mandal)
is searched as "<mandal> mandal, <district>, Telangana" (the way scripts/data/fetch_d1.py found
the Hyderabad mandal relations); a result counts only if Nominatim places it in the same
district. Writes data/raw/d8_weather_stations/mandal_points.csv (one row per mandal: the OSM
object, its centre, and the match status) and appends to RETRIEVAL_LOG.md. One request per
second, as Nominatim's usage policy asks. OSM data (c) OpenStreetMap contributors, ODbL 1.0.

    python scripts/data/fetch_d8_mandal_points.py
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/forecast"))
import build_section_weather as sw  # noqa: E402

DIR = ROOT / "data/raw/d8_weather_stations"
STATIONS = DIR / "tgdps_daily_hmwssb_districts.csv.gz"
OUT = DIR / "mandal_points.csv"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "jallekha-d8b-mandals (HMWSSB tanker-planning research)"
# How OSM names the districts the station files call Rangareddy and Medchal-Malkajgiri.
OSM_DISTRICT = {
    "Hyderabad": ("Hyderabad",),
    "Medchal-Malkajgiri": ("Medchal–Malkajgiri", "Medchal-Malkajgiri", "Medchal Malkajgiri"),
    "Rangareddy": ("Ranga Reddy", "Rangareddy", "Rangareddi"),
    "Sangareddy": ("Sangareddy",),
}
FIELDS = ("district", "mandal", "query", "status", "osm_type", "osm_id", "osm_name", "lat", "lon")


def _search(query: str) -> list[dict]:
    params = {"q": query, "format": "jsonv2", "addressdetails": 1, "limit": 5, "countrycodes": "in"}
    url = f"{NOMINATIM}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except OSError:
            if attempt == 4:
                raise
            time.sleep(15 * (attempt + 1))
    raise AssertionError("unreachable")


def _in_district(result: dict, district: str) -> bool:
    address = result.get("address", {})
    found = address.get("state_district") or address.get("county") or ""
    return any(name.lower() in found.lower() for name in OSM_DISTRICT[district])


def locate(district: str, mandal: str) -> dict[str, str]:
    """The best Nominatim match in the same district: an administrative boundary first."""
    tried = []
    for query in (f"{mandal} mandal, {OSM_DISTRICT[district][0]}, Telangana",
                  f"{mandal}, {OSM_DISTRICT[district][0]}, Telangana"):  # fmt: skip
        tried.append(query)
        results = [r for r in _search(query) if _in_district(r, district)]
        time.sleep(1.1)
        if results:
            best = sorted(results, key=lambda r: (r.get("type") != "administrative",))[0]
            return {
                "district": district, "mandal": mandal, "query": query,
                "status": "BOUNDARY" if best.get("type") == "administrative" else "PLACE",
                "osm_type": best.get("osm_type", ""), "osm_id": str(best.get("osm_id", "")),
                "osm_name": best.get("display_name", ""),
                "lat": f"{float(best['lat']):.6f}", "lon": f"{float(best['lon']):.6f}",
            }  # fmt: skip
    return {"district": district, "mandal": mandal, "query": " | ".join(tried),
            "status": "NOT_FOUND", "osm_type": "", "osm_id": "", "osm_name": "",
            "lat": "", "lon": ""}  # fmt: skip


def main() -> None:
    with gzip.open(STATIONS, "rt", encoding="utf-8", newline="") as handle:
        found = {(r["district"], r["mandal"]) for r in csv.DictReader(handle)}
    # One name per mandal (spelling variants and number-only values: build_section_weather.py).
    mandals = sorted({(d, c) for d, m in found if (c := sw.canonical(d, m)) is not None})
    rows = [locate(d, m) for d, m in mandals]
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    counts = {s: sum(r["status"] == s for r in rows) for s in ("BOUNDARY", "PLACE", "NOT_FOUND")}
    with (DIR / "RETRIEVAL_LOG.md").open("a", encoding="utf-8") as handle:
        handle.write(
            f"""
## Mandal locations (`{OUT.name}`)

Nominatim search ({NOMINATIM}), "<mandal> mandal, <district>, Telangana", then "<mandal>,
<district>, Telangana"; only results Nominatim places in the same district. {len(rows)} mandals:
{counts["BOUNDARY"]} matched an administrative boundary, {counts["PLACE"]} a place of that name,
{counts["NOT_FOUND"]} not found. Retrieved {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")};
SHA-256 `{digest}`. OSM data (c) OpenStreetMap contributors, ODbL 1.0.
"""
        )
    print(f"Wrote {OUT}: {counts}")


if __name__ == "__main__":
    main()
