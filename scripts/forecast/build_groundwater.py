"""D7: groundwater-level anomaly per well and per HMWSSB section (item 17).

From the Telangana Ground Water Department's monthly well levels (data/raw/d7_groundwater, REAL):
- a well is its district, village and position rounded to 0.01 deg (about 1 km); positions
  written latitude-for-longitude are swapped back, positions outside the region dropped;
- a well's anomaly in a month is its depth to water minus its mean depth in the same calendar
  month of earlier years (at least MIN_PRIOR_YEARS of them). Positive = deeper = drier;
- a section's anomaly is the median over wells within RADIUS_KM of its geocoded point (D12),
  with at least MIN_WELLS wells; otherwise none, with the reason.

Output (DERIVED): data/derived/groundwater/section_anomaly.csv (every section and month) and
well_anomaly.csv, checked by data/verification/groundwater_checks.json.

    python scripts/forecast/build_groundwater.py
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import statistics
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEVELS = "data/raw/d7_groundwater/tggwd_levels_hmwssb_districts.csv.gz"
SECTIONS = "data/derived/crosswalk/section_to_ward_2016.csv"
INPUTS = (LEVELS, SECTIONS)
OUT_SECTIONS = "data/derived/groundwater/section_anomaly.csv"
OUT_WELLS = "data/derived/groundwater/well_anomaly.csv"
CHECKS = "data/verification/groundwater_checks.json"
# All ASSUMED (policy-free data choices), in one place.
MIN_PRIOR_YEARS = 2  # earlier years of the same calendar month behind a well's normal
RADIUS_KM = 5.0  # wells counted for a section
MIN_WELLS = 2  # wells needed for a section value
POSITION_DECIMALS = 2  # well identity: position rounded to 0.01 deg (about 1 km)
REGION = ((16.5, 18.6), (77.0, 79.5))  # (lat, lon) bounds of the four districts, generous
Month = tuple[int, int]


def _num(text: str) -> float | None:
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def position(row: Mapping[str, str]) -> tuple[float, float] | None:
    """(lat, lon) of a well row; latitude-for-longitude swaps fixed; None outside the region."""
    a, b = _num(row.get("lat", "")), _num(row.get("lon", ""))
    if a is None or b is None:
        return None
    lat, lon = (b, a) if a > b else (a, b)  # here latitude (16-19) < longitude (77-80)
    (lat_lo, lat_hi), (lon_lo, lon_hi) = REGION
    return (lat, lon) if lat_lo <= lat <= lat_hi and lon_lo <= lon <= lon_hi else None


def well_id(row: Mapping[str, str]) -> str | None:
    point = position(row)
    if point is None:
        return None
    lat, lon = (round(v, POSITION_DECIMALS) for v in point)
    return f"{row['district']}|{row['village'].strip().lower()}|{lat:.2f},{lon:.2f}"


def _month(row: Mapping[str, str]) -> Month:
    return int(row["source_month"][:4]), int(row["source_month"][5:7])


def well_anomalies(rows: list[dict[str, str]]) -> dict[tuple[str, Month], float]:
    """(well, month) -> depth minus the mean of the same calendar month in earlier years."""
    depth: dict[str, dict[Month, list[float]]] = {}
    for r in rows:
        well, value = well_id(r), _num(r.get("depth_m_bgl", ""))
        if well is None or value is None:
            continue
        depth.setdefault(well, {}).setdefault(_month(r), []).append(value)
    out = {}
    for well, months in depth.items():
        mean = {m: sum(v) / len(v) for m, v in months.items()}
        for (year, number), value in mean.items():
            earlier = [v for (y, n), v in mean.items() if n == number and y < year]
            if len(earlier) >= MIN_PRIOR_YEARS:
                out[(well, (year, number))] = value - sum(earlier) / len(earlier)
    return out


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = math.radians(b[1] - a[1]) * math.cos(math.radians(a[0]))
    return 6371.0 * math.hypot(dx, math.radians(b[0] - a[0]))


@dataclass(frozen=True)
class SectionAnomaly:
    value: float | None  # metres; positive = water deeper than usual
    wells: int
    reason: str


def section_anomaly(
    point: tuple[float, float] | None,
    month: Month,
    wells: Mapping[str, tuple[float, float]],
    anomalies: Mapping[tuple[str, Month], float],
) -> SectionAnomaly:
    if point is None:
        return SectionAnomaly(None, 0, "no geocoded section point")
    near = [
        anomalies[(w, month)]
        for w, at in sorted(wells.items())
        if (w, month) in anomalies and _km(point, at) <= RADIUS_KM
    ]
    if len(near) < MIN_WELLS:
        noun = "well" if len(near) == 1 else "wells"
        return SectionAnomaly(
            None,
            len(near),
            f"{len(near)} {noun} with {MIN_PRIOR_YEARS}+ earlier years within {RADIUS_KM:g} km",
        )
    return SectionAnomaly(statistics.median(near), len(near), "")


def _csv(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def build(root: Path = ROOT) -> dict[str, bytes]:
    with gzip.open(root / LEVELS, "rt", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    anomalies = well_anomalies(rows)
    wells: dict[str, tuple[float, float]] = {}
    for r in rows:
        well = well_id(r)
        if well is not None:
            lat, lon = (float(v) for v in well.rsplit("|", 1)[1].split(","))
            wells[well] = (lat, lon)
    with (root / SECTIONS).open(encoding="utf-8", newline="") as handle:
        points = {
            r["section"]: (float(r["lat"]), float(r["lng"])) if r["lat"] and r["lng"] else None
            for r in csv.DictReader(handle)
        }
    months = sorted({_month(r) for r in rows})
    section_rows = []
    for section, point in sorted(points.items()):
        # The wells within reach of this section, found once (same result, much faster).
        local = {w: at for w, at in wells.items() if point and _km(point, at) <= RADIUS_KM}
        for month in months:
            a = section_anomaly(point, month, local, anomalies)
            section_rows.append(
                {
                    "section": section,
                    "month": f"{month[0]}-{month[1]:02d}",
                    "anomaly_m": "" if a.value is None else f"{a.value:.3f}",
                    "wells": a.wells,
                    "basis": (
                        f"DERIVED: median anomaly of {a.wells} TGGWD wells within "
                        f"{RADIUS_KM:g} km (REAL levels)"
                        if a.value is not None
                        else f"UNAVAILABLE: {a.reason}"
                    ),
                }
            )
    well_rows = [
        {"well": w, "month": f"{m[0]}-{m[1]:02d}", "anomaly_m": f"{v:.3f}"}
        for (w, m), v in sorted(anomalies.items())
    ]
    artifacts = {OUT_SECTIONS: _csv(section_rows), OUT_WELLS: _csv(well_rows)}
    latest = f"{months[-1][0]}-{months[-1][1]:02d}"
    checks = {
        "inputs_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in INPUTS},
        "outputs_sha256": {p: hashlib.sha256(b).hexdigest() for p, b in artifacts.items()},
        "settings": {
            "min_prior_years": MIN_PRIOR_YEARS,
            "radius_km": RADIUS_KM,
            "min_wells": MIN_WELLS,
            "position_decimals": POSITION_DECIMALS,
        },
        "wells": len(wells),
        "well_months_with_anomaly": len(anomalies),
        "latest_month": latest,
        "sections_with_value_at_latest_month": sum(
            1 for r in section_rows if r["month"] == latest and r["anomaly_m"]
        ),
        "sections": len(points),
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


if __name__ == "__main__":
    for name, content in build().items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("D7 groundwater anomalies built; see data/verification/groundwater_checks.json")
