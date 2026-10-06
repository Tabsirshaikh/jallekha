"""T8 shortage early warning (F6): per section and month, 1-3 months ahead, T2's forecast
against capacity, with a risk level from config rules and a reason built from the numbers.

Pure apart from `load_capacity` and `load_groundwater`, which read committed files. No LLM.
Groundwater (D7, item 17): the reason gives the section's groundwater anomaly at the forecast
origin (median of nearby wells; scripts/forecast/build_groundwater.py) or why there is none; it
does not change the risk level. Without groundwater data the reason says it is unavailable.
Reservoir levels are behind a flag that is off (Q2 not approved) and have no data.
"""

from __future__ import annotations

import calendar
import csv
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from app.config.forecast import SHORTAGE_CONFIG, ShortageConfig

RISKS = ("low", "medium", "high", "unknown")


@dataclass(frozen=True)
class SectionCapacity:
    section: str
    trips_per_day: float
    basis: str


@dataclass(frozen=True)
class ShortageRow:
    section: str
    month: str
    months_ahead: int
    forecast_bookings: float
    forecast_basis: str
    upper_80: float | None
    upper_80_basis: str
    capacity_trips: float | None
    capacity_basis: str
    capacity_ratio: float | None
    risk: str
    reason: str
    groundwater_status: str
    reservoir_status: str
    groundwater_m: float | None = None  # positive = water deeper than usual


@dataclass(frozen=True)
class GroundwaterSignal:
    value: float | None  # metres; positive = water deeper than usual for the month
    wells: int
    month: str  # the groundwater month used (YYYY-MM)
    reason: str  # why there is no value


def load_groundwater(path: Path, origin: str) -> dict[str, GroundwaterSignal]:
    """Each section's groundwater anomaly in the latest month at or before `origin` (the
    forecast is made then, so later readings are not used). Empty if the file is absent."""
    if not path.exists():
        return {}
    latest: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["month"] <= origin and row["month"] > latest.get(row["section"], {}).get(
                "month", ""
            ):
                latest[row["section"]] = row
    return {
        section: GroundwaterSignal(
            float(r["anomaly_m"]) if r["anomaly_m"] else None,
            int(r["wells"] or 0),
            r["month"],
            "" if r["anomaly_m"] else r["basis"].removeprefix("UNAVAILABLE: "),
        )
        for section, r in latest.items()
    }


def load_capacity(
    root: Path, config: ShortageConfig = SHORTAGE_CONFIG
) -> dict[str, SectionCapacity]:
    """A8's fleet-scenario station trips per day, shared over each station's home sections in
    proportion to their Mar-Jul 2025 bookings. Sections without a home station are left out."""
    checks = json.loads((root / config.a8_checks_path).read_text(encoding="utf-8"))
    stations: Mapping[str, float] = checks["capacities"][config.a8_replay][config.a8_scenario]
    with (root / config.a8_sections_path).open(encoding="utf-8", newline="") as handle:
        points = [p for p in csv.DictReader(handle) if p["home_station"]]
    home: dict[str, list[dict[str, str]]] = defaultdict(list)
    for p in points:
        home[p["home_station"]].append(p)
    out: dict[str, SectionCapacity] = {}
    for station, sections in home.items():
        trips = float(stations[station])
        weights = [float(p["bookings_2025_mar_jul"] or 0) for p in sections]
        total = sum(weights)
        for p, w in zip(sections, weights, strict=True):
            share = w / total if total else 1 / len(sections)
            basis = (
                f"ASSUMED: A8 {config.a8_replay} {config.a8_scenario}"
                f" capacity of {station}"
                f" ({trips:g} trips/day; REAL fleet x DERIVED trips per tanker)"
                f" x the section's share of the station's"
                f" Mar-Jul 2025 bookings ({share:.4f})"
            )
            out[p["section"]] = SectionCapacity(p["section"], trips * share, basis)
    return out


def risk_level(
    point: float,
    upper_80: float | None,
    capacity: float | None,
    config: ShortageConfig = SHORTAGE_CONFIG,
) -> str:
    if capacity is None or capacity <= 0:
        return "unknown"
    if point >= config.risk_high_ratio * capacity:
        return "high"
    upper_breaches = upper_80 is not None and upper_80 >= capacity
    if point >= config.risk_medium_ratio * capacity or upper_breaches:
        return "medium"
    return "low"


def _add_months(month: str, k: int) -> str:
    y, m = (int(x) for x in month.split("-"))
    m += k
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def _days(month: str) -> int:
    y, m = (int(x) for x in month.split("-"))
    return calendar.monthrange(y, m)[1]


def _num(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def _groundwater_text(signal: GroundwaterSignal | None, known: bool, config: ShortageConfig) -> str:
    if not known:
        return config.groundwater_note
    if signal is None:
        return "groundwater: no value for this section"
    if signal.value is None:
        return f"groundwater: {signal.reason} ({signal.month})"
    size = abs(signal.value)
    if round(size, 1) == 0:
        level = "at its usual level"
    else:
        level = f"{size:.1f} m {'deeper' if signal.value > 0 else 'shallower'} than usual"
    return (
        f"groundwater {level} near this section (median of {signal.wells} wells within "
        f"{config.groundwater_radius_km:g} km, {signal.month})"
    )


def _reason(
    row: ShortageRow,
    config: ShortageConfig,
    signal: GroundwaterSignal | None = None,
    known: bool = False,
) -> str:
    upper = f" (80% bound up to {row.upper_80:,.0f})" if row.upper_80 is not None else ""
    if row.capacity_ratio is None:
        if row.capacity_trips is not None and row.capacity_trips == 0:
            note = (
                "capacity is zero (A8 fleet split produced 0 trips"
                " for this section), so the risk is unknown"
            )
        else:
            note = (
                "capacity unavailable (no A8 filling station"
                " for this section), so the risk is unknown"
            )
        # Rounded from the 1-decimal value the CSV stores, so the reason matches the column.
        shown = round(row.forecast_bookings, 1)
        core = f"Forecast {shown:,.0f} bookings{upper} in {row.month}; {note}"
    else:
        core = (
            f"Forecast {round(row.forecast_bookings, 1):,.0f} bookings{upper}"
            f" in {row.month} against capacity"
            f" {row.capacity_trips:,.0f} trips (A8 fleet split, ASSUMED):"
            f" {row.capacity_ratio:.0%} of capacity, risk {row.risk}"
        )
    return f"{core}; {_groundwater_text(signal, known, config)}."


def risk_list(
    forecast_rows: Iterable[Mapping[str, str]],
    capacity: Mapping[str, SectionCapacity],
    origin: str,
    config: ShortageConfig = SHORTAGE_CONFIG,
    reservoirs_enabled: bool | None = None,
    groundwater: Mapping[str, GroundwaterSignal] | None = None,
) -> list[ShortageRow]:
    """Risk per section for each month `months_ahead` after `origin` (YYYY-MM)."""
    use_reservoirs = (
        reservoirs_enabled if reservoirs_enabled is not None else config.reservoirs_enabled
    )
    if use_reservoirs:
        raise ValueError(
            "reservoir levels are not in the repo (Q2 not approved); keep the flag off"
        )
    wanted = {_add_months(origin, k): k for k in config.months_ahead}
    rows: list[ShortageRow] = []
    for f in forecast_rows:
        if f.get("level") != "section" or f["month"] not in wanted:
            continue
        cap = capacity.get(f["section"])
        point, upper = float(f["point"]), _num(f.get("upper_80"))
        trips = cap.trips_per_day * _days(f["month"]) if cap else None
        risk = risk_level(point, upper, trips, config)
        row = ShortageRow(
            section=f["section"],
            month=f["month"],
            months_ahead=wanted[f["month"]],
            forecast_bookings=point,
            forecast_basis=f.get("point_basis", ""),
            upper_80=upper,
            upper_80_basis=f.get("upper_80_basis", "") if upper is not None else "UNAVAILABLE",
            capacity_trips=trips,
            capacity_basis=(f"{cap.basis}; x {_days(f['month'])} days" if cap else "UNAVAILABLE"),
            capacity_ratio=point / trips if trips else None,
            risk=risk,
            reason="",
            groundwater_status="UNAVAILABLE",
            reservoir_status="NOT_USED",
        )
        signal = (groundwater or {}).get(f["section"])
        if signal is not None and signal.value is not None:
            row = replace(row, groundwater_status="DERIVED", groundwater_m=signal.value)
        rows.append(row)
    rows.sort(key=lambda r: (r.section, r.month))
    known = groundwater is not None
    return [
        replace(r, reason=_reason(r, config, (groundwater or {}).get(r.section), known))
        for r in rows
    ]
