"""Stand-in filling stations and section-to-station road km for the A8 sandbox (F19).

HMWSSB has 90 tanker filling stations (Telangana Today, 2025-12-21) but publishes no list
with coordinates (the tracking page only names the station of one booking; OSM has no
filling-station tags). So the sandbox uses 90 ASSUMED stand-ins: booking-weighted k-means
of the section points (Mar-Jul 2025 bookings), i.e. sites where bookings cluster.

Section points: the geocoded point (data/derived/crosswalk/section_to_ward_2016.csv) when
the section was located (MAPPED or UNMAPPED_NO_WARD); otherwise the booking-weighted centre of
the located sections in its HMWSSB division (APPROXIMATE). A division with no located section
gives no point; its bookings are left out of the sandbox and counted.

Road km (item 20): OSRM road km on OpenStreetMap, station to section and back
(data/derived/routing/, built by scripts/routing/build_osrm_legs.py; DERIVED), plus
2 x section_access_km x road_factor (ALLOCATION_CONFIG, 1.35) for driving inside the section to
the household. Station to station: OSRM road km both ways (for trip sharing, JL_POOL). A pair
OSRM found no route for falls back to straight line x road_factor (labelled ASSUMED). Each
section keeps its nearest b4_candidate_stations stations by road; the first is its home
station (HMWSSB: "token will be assigned to nearest Tanker Filling Station").
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.allocation import ALLOCATION_CONFIG  # noqa: E402
from app.config.sandbox import SANDBOX_CONFIG  # noqa: E402
from app.services import hmwssb  # noqa: E402
from app.services.geo import haversine_km  # noqa: E402

SECTION_WARDS = "data/derived/crosswalk/section_to_ward_2016.csv"
TANKERS = "data/raw/hmwssb_tankers_portal"
STATIONS = "data/derived/sandbox/stations.csv"
SECTIONS = "data/derived/sandbox/section_points.csv"
NETWORK = "data/derived/sandbox/section_station_km.csv"
STATION_PAIRS = "data/derived/sandbox/station_station_km.csv"
CHECKS = "data/verification/sandbox_stations_checks.json"
OSRM_SECTION_STATION = "data/derived/routing/osrm_section_station.csv"
OSRM_STATION_STATION = "data/derived/routing/osrm_station_station.csv"
OSRM_POINTS = "data/derived/routing/osrm_points.csv"
OSRM_BASIS = "DERIVED: OSRM car route on OSM roads (no traffic), both ways"
ESTIMATE_BASIS = "ASSUMED: straight line x road_factor (no OSRM route)"
WEIGHT_MONTHS = tuple((2025, m) for m in range(3, 8))  # the main replay window
LOCATED = ("MAPPED", "UNMAPPED_NO_WARD")
KMEANS_SEED = 0
KMEANS_ITERATIONS = 200


def section_points(root: Path) -> tuple[list[dict], dict[str, int]]:
    rows = hmwssb.read_rows(root / TANKERS)
    weight: dict[str, int] = defaultdict(int)
    for r in rows:
        if (r["year"], r["month"]) in WEIGHT_MONTHS:
            weight[r["section"]] += r["bookings"]
    with (root / SECTION_WARDS).open(encoding="utf-8", newline="") as handle:
        links = list(csv.DictReader(handle))
    located = [r for r in links if r["status"] in LOCATED and r["lat"]]
    centres: dict[str, tuple[float, float]] = {}
    by_division: dict[str, list[dict]] = defaultdict(list)
    for r in located:
        by_division[r["division"]].append(r)
    for division, members in by_division.items():
        w = [max(1, weight.get(r["section"], 0)) for r in members]
        lat = sum(float(r["lat"]) * x for r, x in zip(members, w, strict=True)) / sum(w)
        lng = sum(float(r["lng"]) * x for r, x in zip(members, w, strict=True)) / sum(w)
        centres[division] = (lat, lng)
    points = []
    for r in sorted(links, key=lambda r: r["section"]):
        if r in located:
            lat, lng, basis = float(r["lat"]), float(r["lng"]), "GEOCODED"
        elif r["division"] in centres:
            lat, lng = centres[r["division"]]
            basis = "DIVISION_CENTRE_APPROXIMATE"
        else:
            lat = lng = None
            basis = "NO_POINT"
        points.append(
            {
                "section": r["section"],
                "division": r["division"],
                "lat": lat,
                "lng": lng,
                "point_basis": basis,
                "bookings_2025_mar_jul": weight.get(r["section"], 0),
            }
        )
    return points, dict(weight)


def kmeans(xy: np.ndarray, weights: np.ndarray, k: int) -> np.ndarray:
    """Weighted k-means (Lloyd) with k-means++ seeding; deterministic for a fixed seed."""
    rng = np.random.default_rng(KMEANS_SEED)
    centres = [xy[rng.choice(len(xy), p=weights / weights.sum())]]
    for _ in range(1, k):
        d2 = np.min(((xy[:, None, :] - np.array(centres)[None]) ** 2).sum(-1), axis=1)
        p = weights * d2
        centres.append(xy[rng.choice(len(xy), p=p / p.sum())])
    centres = np.array(centres)
    for _ in range(KMEANS_ITERATIONS):
        label = ((xy[:, None, :] - centres[None]) ** 2).sum(-1).argmin(1)
        new = centres.copy()
        for j in range(k):
            members = label == j
            if weights[members].sum() > 0:
                new[j] = (xy[members] * weights[members, None]).sum(0) / weights[members].sum()
        if np.allclose(new, centres):
            break
        centres = new
    return centres


def osrm_legs(root: Path, stations: list[dict], points: list[dict]) -> tuple[dict, dict]:
    """Committed OSRM legs: {(section, station): (out_km, back_km)}, {(a, b): (ab_km, ba_km)}.
    Refuses legs built for other points (re-run scripts/routing/build_osrm_legs.py)."""
    with (root / OSRM_POINTS).open(encoding="utf-8", newline="") as handle:
        legged = {
            (r["kind"], r["id"]): (float(r["lat"]), float(r["lng"])) for r in csv.DictReader(handle)
        }
    expected = {("station", s["station_id"]): (s["lat"], s["lng"]) for s in stations} | {
        ("section", p["section"]): (p["lat"], p["lng"]) for p in points if p["lat"] is not None
    }
    for key, (lat, lng) in expected.items():
        got = legged.get(key)
        if got is None or abs(got[0] - lat) > 1e-6 or abs(got[1] - lng) > 1e-6:
            raise ValueError(f"OSRM legs are for other points ({key}); re-run build_osrm_legs.py")

    def km(value: str) -> float | None:
        return float(value) if value else None

    with (root / OSRM_SECTION_STATION).open(encoding="utf-8", newline="") as handle:
        section_station = {
            (r["section"], r["station_id"]): (km(r["out_km"]), km(r["back_km"]))
            for r in csv.DictReader(handle)
        }
    with (root / OSRM_STATION_STATION).open(encoding="utf-8", newline="") as handle:
        station_station = {
            (r["station_a"], r["station_b"]): (km(r["ab_km"]), km(r["ba_km"]))
            for r in csv.DictReader(handle)
        }
    return section_station, station_station


def _csv(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def build(root: Path = ROOT) -> dict[str, bytes]:
    cfg = SANDBOX_CONFIG
    points, _weight = section_points(root)
    usable = [p for p in points if p["lat"] is not None]
    lat0 = sum(p["lat"] for p in usable) / len(usable)
    scale = (111.32 * math.cos(math.radians(lat0)), 110.57)  # km per degree lng, lat
    xy = np.array([(p["lng"] * scale[0], p["lat"] * scale[1]) for p in usable])
    # sections with no 2025 bookings still get a station, but do not pull the sites
    weights = np.array([p["bookings_2025_mar_jul"] for p in usable], dtype=float)
    weighted = weights > 0
    centres = kmeans(xy[weighted], weights[weighted], cfg.station_count)
    station_ids = [f"ST{i + 1:02d}" for i in range(len(centres))]
    stations = [
        {
            "station_id": sid,
            "lat": round(c[1] / scale[1], 6),
            "lng": round(c[0] / scale[0], 6),
        }
        for sid, c in zip(station_ids, centres, strict=True)
    ]

    road_section, road_station = osrm_legs(root, stations, points)
    factor = ALLOCATION_CONFIG.road_factor
    access = 2 * cfg.section_access_km * factor

    def section_km(p: dict, s: dict) -> tuple[float, str]:
        out, back = road_section.get((p["section"], s["station_id"]), (None, None))
        if out is None or back is None:
            straight = haversine_km(p["lat"], p["lng"], s["lat"], s["lng"])
            return 2 * straight * factor + access, ESTIMATE_BASIS
        return out + back + access, OSRM_BASIS

    network, section_rows = [], []
    served_bookings: dict[str, int] = defaultdict(int)
    served_sections: dict[str, int] = defaultdict(int)
    for p in points:
        row = dict(p) | {"home_station": "", "home_round_trip_km": ""}
        if p["lat"] is not None:
            km = sorted(
                (*section_km(p, s), s["station_id"]) for s in stations
            )  # (km, basis, station): ties go to the lower id, as before
            km = sorted(km, key=lambda t: (t[0], t[2]))[: cfg.b4_candidate_stations]
            km = [(distance, sid, basis) for distance, basis, sid in km]
            for rank, (distance, sid, basis) in enumerate(km, start=1):
                network.append(
                    {
                        "section": p["section"],
                        "station_id": sid,
                        "rank": rank,
                        "round_trip_km": round(distance, 3),
                        "km_basis": basis,
                    }
                )
            row["home_station"], row["home_round_trip_km"] = (
                km[0][1],
                round(km[0][0], 3),
            )
            served_bookings[km[0][1]] += p["bookings_2025_mar_jul"]
            served_sections[km[0][1]] += 1
        section_rows.append(row)
    for s in stations:
        s["home_sections"] = served_sections[s["station_id"]]
        s["bookings_2025_mar_jul"] = served_bookings[s["station_id"]]
        s["basis"] = "ASSUMED_STAND_IN"

    def pair(a: dict, b: dict) -> dict:
        straight = haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])
        ab, ba = road_station.get((a["station_id"], b["station_id"]), (None, None))
        if ab is None or ba is None:
            km, basis = 2 * straight * factor, ESTIMATE_BASIS
        else:
            km, basis = ab + ba, OSRM_BASIS
        return {
            "station_a": a["station_id"],
            "station_b": b["station_id"],
            "straight_km": round(straight, 3),
            "round_trip_km": round(km, 3),
            "km_basis": basis,
        }

    pairs = [pair(a, b) for i, a in enumerate(stations) for b in stations[i + 1 :]]
    total = sum(p["bookings_2025_mar_jul"] for p in points)
    by_basis: dict[str, int] = defaultdict(int)
    for p in points:
        by_basis[p["point_basis"]] += p["bookings_2025_mar_jul"]
    summary = {
        "stations": len(stations),
        "station_basis": "ASSUMED_STAND_IN (booking-weighted k-means; HMWSSB publishes no list)",
        "station_count_source": "Telangana Today, 2025-12-21: 90 tanker filling stations",
        "bookings_2025_mar_jul": total,
        "booking_share_by_point_basis": {
            k: round(v / total, 6) for k, v in sorted(by_basis.items())
        },
        "road_factor": ALLOCATION_CONFIG.road_factor,
        "road_km_basis": {
            "section_station": dict(sorted(Counter(r["km_basis"] for r in network).items())),
            "station_station": dict(sorted(Counter(r["km_basis"] for r in pairs).items())),
        },
        "median_home_round_trip_km": round(
            float(np.median([r["home_round_trip_km"] for r in section_rows if r["home_station"]])),
            3,
        ),
    }
    artifacts = {
        STATIONS: _csv(stations),
        SECTIONS: _csv(section_rows),
        NETWORK: _csv(network),
        STATION_PAIRS: _csv(pairs),
    }
    checks = {
        "summary": summary,
        "inputs_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in (SECTION_WARDS, OSRM_POINTS, OSRM_SECTION_STATION, OSRM_STATION_STATION)
        },
        "outputs_sha256": {p: hashlib.sha256(c).hexdigest() for p, c in artifacts.items()},
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


if __name__ == "__main__":
    for name, content in build().items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("Sandbox stand-in stations built.")
