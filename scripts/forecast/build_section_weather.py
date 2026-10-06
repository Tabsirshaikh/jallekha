"""D8b: monthly weather per HMWSSB section from the TGDPS stations (research follow-up B).

Daily station rows (data/raw/d8_weather_stations, REAL) become one value per mandal and month:
stations of a mandal are averaged per day; a month needs `MIN_DAY_SHARE` of its days; mean
daily maximum temperature, and rain summed and scaled to the full month. Each section with a
geocoded point (data/derived/crosswalk/section_to_ward_2016.csv, D12) takes the nearest mandal
centre (mandal_points.csv). When that mandal has no value for a month the mean of its district's
mandals is used, and when none has one, the city series (D8, Open-Meteo); sections without a
point use the city series throughout. Every value says which (`source`).

Output: data/derived/weather/section_monthly.csv (DERIVED) and section_mandal.csv (which mandal
each section takes, how far away), checked by data/verification/section_weather_checks.json.

    python scripts/forecast/build_section_weather.py
"""

from __future__ import annotations

import calendar
import csv
import gzip
import hashlib
import io
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIONS = "data/raw/d8_weather_stations/tgdps_daily_hmwssb_districts.csv.gz"
POINTS = "data/raw/d8_weather_stations/mandal_points.csv"
SECTIONS = "data/derived/crosswalk/section_to_ward_2016.csv"
CITY = "data/raw/d8_weather/open_meteo_hyderabad_daily.csv"
INPUTS = (STATIONS, POINTS, SECTIONS, CITY)
OUT_MONTHLY = "data/derived/weather/section_monthly.csv"
OUT_MANDAL = "data/derived/weather/section_mandal.csv"
CHECKS = "data/verification/section_weather_checks.json"
# A mandal-month counts only with values on at least this share of its days. ASSUMED.
MIN_DAY_SHARE = 0.8
Month = tuple[int, int]
Key = tuple[str, str]  # (district, mandal)
# The station files spell some mandals two ways in different years (2018-2019 vs 2019-2026); each
# pair is one mandal, named as OpenStreetMap names it (also where OSM spells it differently).
# DERIVED from the files' own year spans.
MANDAL_ALIASES: dict[Key, str] = {
    ("Hyderabad", "Maredpally"): "Marredpally",
    ("Hyderabad", "Tirumalgiri"): "Tirumalagiri",
    ("Medchal-Malkajgiri", "Bachpalle"): "Bachupally",
    ("Medchal-Malkajgiri", "Dundigal_Gandimaisamma"): "Dundigal Gandimaisamma",
    ("Medchal-Malkajgiri", "Ghatkeshar"): "Ghatkesar",
    ("Medchal-Malkajgiri", "Medchel"): "Medchal",
    ("Medchal-Malkajgiri", "Qutballapur"): "Quthbullapur",
    ("Rangareddy", "Choudergudem"): "Chowdergudem",
    ("Rangareddy", "Keshampeta"): "Keshampet",
    ("Rangareddy", "Nandigam"): "Nandigama",
    ("Rangareddy", "Talakondapalle"): "Talakondapally",
    ("Rangareddy", "Thalakondapally"): "Talakondapally",
    ("Sangareddy", "Naykal"): "Nyalkal",
    ("Sangareddy", "Ramchandrapuram"): "Ramachandrapuram",
}


def canonical(district: str, mandal: str) -> str | None:
    """The one name of a mandal; None for a value that is not a mandal name (e.g. "28")."""
    if not mandal or mandal.strip().isdigit():
        return None
    return MANDAL_ALIASES.get((district, mandal), mandal)


@dataclass(frozen=True)
class MonthWeather:
    tmax_mean: float  # mean daily maximum temperature, deg C
    rain_total: float  # rain over the month, mm (scaled to the full month)
    days: int  # days with values


def _num(text: str) -> float | None:
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _aggregate(days: Mapping[str, tuple[list[float], list[float]]]) -> dict[Month, MonthWeather]:
    """Daily (tmax values, rain values) by ISO date -> month values with enough days."""
    by_month: dict[Month, list[tuple[float | None, float | None]]] = {}
    for day, (tmax, rain) in days.items():
        month = (int(day[:4]), int(day[5:7]))
        by_month.setdefault(month, []).append(
            (sum(tmax) / len(tmax) if tmax else None, sum(rain) / len(rain) if rain else None)
        )
    out = {}
    for month, values in by_month.items():
        length = calendar.monthrange(*month)[1]
        tmax = [t for t, _ in values if t is not None]
        rain = [r for _, r in values if r is not None]
        if min(len(tmax), len(rain)) < MIN_DAY_SHARE * length:
            continue
        out[month] = MonthWeather(
            sum(tmax) / len(tmax), sum(rain) * length / len(rain), min(len(tmax), len(rain))
        )
    return out


def mandal_monthly(rows: list[dict[str, str]]) -> dict[tuple[str, str, Month], MonthWeather]:
    """(district, mandal, month) -> MonthWeather from daily station rows."""
    days: dict[Key, dict[str, tuple[list[float], list[float]]]] = {}
    for r in rows:
        mandal = canonical(r["district"], r["mandal"])
        if not r.get("date") or mandal is None:
            continue
        day = days.setdefault((r["district"], mandal), {}).setdefault(r["date"], ([], []))
        tmax, rain = _num(r.get("tmax_c", "")), _num(r.get("rain_mm", ""))
        if tmax is not None:
            day[0].append(tmax)
        if rain is not None:
            day[1].append(rain)
    return {
        (district, mandal, month): weather
        for (district, mandal), by_day in days.items()
        for month, weather in _aggregate(by_day).items()
    }


def nearest(
    point: tuple[float, float], points: Mapping[Key, tuple[float, float]]
) -> tuple[Key, float]:
    """The closest mandal centre and its distance in km (equirectangular, fine at city scale)."""
    lat0 = math.radians(point[0])

    def km(other: tuple[float, float]) -> float:
        dx = math.radians(other[1] - point[1]) * math.cos(lat0)
        dy = math.radians(other[0] - point[0])
        return 6371.0 * math.hypot(dx, dy)

    key = min(sorted(points), key=lambda k: km(points[k]))
    return key, km(points[key])


def section_table(
    sections: Mapping[str, tuple[float, float] | None],
    points: Mapping[Key, tuple[float, float]],
    mandals: Mapping[tuple[str, str, Month], MonthWeather],
    city: Mapping[Month, MonthWeather],
) -> dict[str, dict[Month, tuple[MonthWeather, str]]]:
    """Each section's weather per month (every month the city series has) and its source:
    MANDAL (nearest mandal), DISTRICT (mean of the district's mandals that month) or CITY."""
    district_month: dict[tuple[str, Month], list[MonthWeather]] = {}
    for (district, _mandal, month), weather in mandals.items():
        district_month.setdefault((district, month), []).append(weather)
    out: dict[str, dict[Month, tuple[MonthWeather, str]]] = {}
    for section, point in sorted(sections.items()):
        key = nearest(point, points)[0] if point is not None and points else None
        table = {}
        for month, fallback in sorted(city.items()):
            own = mandals.get((key[0], key[1], month)) if key else None
            peers = district_month.get((key[0], month), []) if key else []
            if own is not None:
                table[month] = (own, "MANDAL")
            elif peers:
                table[month] = (
                    MonthWeather(
                        sum(w.tmax_mean for w in peers) / len(peers),
                        sum(w.rain_total for w in peers) / len(peers),
                        min(w.days for w in peers),
                    ),
                    "DISTRICT",
                )
            else:
                table[month] = (fallback, "CITY")
        out[section] = table
    return out


def _read(root: Path, path: str) -> list[dict[str, str]]:
    if path.endswith(".gz"):
        with gzip.open(root / path, "rt", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    with (root / path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _city(root: Path) -> dict[Month, MonthWeather]:
    days = {
        r["date"]: (
            [v] if (v := _num(r["tmax_c"])) is not None else [],
            [p] if (p := _num(r["precip_mm"])) is not None else [],
        )  # fmt: skip
        for r in _read(root, CITY)
    }
    return _aggregate(days)


def _csv(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def build(root: Path = ROOT) -> dict[str, bytes]:
    mandals = mandal_monthly(_read(root, STATIONS))
    points = {
        (r["district"], r["mandal"]): (float(r["lat"]), float(r["lon"]))
        for r in _read(root, POINTS)
        if r["lat"] and r["lon"]
    }
    sections: dict[str, tuple[float, float] | None] = {
        r["section"]: (float(r["lat"]), float(r["lng"])) if r["lat"] and r["lng"] else None
        for r in _read(root, SECTIONS)
    }
    table = section_table(sections, points, mandals, _city(root))
    monthly = [
        {
            "section": section,
            "month": f"{month[0]}-{month[1]:02d}",
            "tmax_mean_c": f"{w.tmax_mean:.3f}",
            "rain_total_mm": f"{w.rain_total:.2f}",
            "days": w.days,
            "source": source,
            "basis": "DERIVED: "
            + {
                "MANDAL": "TGDPS stations of the nearest mandal",
                "DISTRICT": "mean of the district's TGDPS mandals (nearest mandal missing)",
                "CITY": "Open-Meteo city centre (no section point or no station value)",
            }[source],
        }  # fmt: skip
        for section, months in table.items()
        for month, (w, source) in months.items()
    ]
    placed = []
    no_point = "UNAVAILABLE: no geocoded section point; city weather used"
    near = "DERIVED: nearest TGDPS mandal centre to the D12 section point"
    for section, point in sorted(sections.items()):
        if point is None or not points:
            row = {"district": "", "mandal": "", "distance_km": "", "basis": no_point}
        else:
            (district, mandal), km = nearest(point, points)
            row = {
                "district": district,
                "mandal": mandal,
                "distance_km": f"{km:.2f}",
                "basis": near,
            }
        placed.append({"section": section, **row})
    artifacts = {OUT_MONTHLY: _csv(monthly), OUT_MANDAL: _csv(placed)}
    sources: dict[str, int] = {}
    for row in monthly:
        sources[row["source"]] = sources.get(row["source"], 0) + 1
    checks = {
        "inputs_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in INPUTS},
        "outputs_sha256": {p: hashlib.sha256(b).hexdigest() for p, b in artifacts.items()},
        "min_day_share": MIN_DAY_SHARE,
        "mandal_months": len(mandals),
        "section_month_sources": dict(sorted(sources.items())),
        "sections_with_point": sum(p is not None for p in sections.values()),
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


if __name__ == "__main__":
    for name, content in build().items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("D8b section weather built; see data/verification/section_weather_checks.json")
