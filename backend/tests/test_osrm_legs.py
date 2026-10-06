"""Item 20: OSRM table answers become the committed road legs (scripts/routing/build_osrm_legs.py).

The download, crop and OSRM steps need the map and the binaries, so they are run by hand; this
checks the part that turns a /table answer into the committed files, and the committed files."""

from __future__ import annotations

import csv
import importlib.util
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "build_osrm_legs", ROOT / "scripts/routing/build_osrm_legs.py"
)
legs_build = importlib.util.module_from_spec(spec)
sys.modules["build_osrm_legs"] = legs_build
spec.loader.exec_module(legs_build)


def _rows(content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content.decode())))


def test_table_rows_are_from_and_to_in_both_directions() -> None:
    sections = [{"section": "A", "lat": "17.4", "lng": "78.4"}]
    stations = [
        {"station_id": "ST01", "lat": "17.5", "lng": "78.5"},
        {"station_id": "ST02", "lat": "17.3", "lng": "78.3"},
    ]
    # points: A, ST01, ST02; distances in metres, durations in seconds, row = from
    data = {
        "distances": [[0, 1000, 2000], [1500, 0, None], [2500, 3000, 0]],
        "durations": [[0, 60, 120], [90, 0, None], [150, 180, 0]],
        "sources": [{"distance": 12.34}, {"distance": 0.5}, {"distance": 40.0}],
    }
    built = legs_build.legs(data, sections, stations)
    section_station = _rows(built[legs_build.SECTION_STATION])
    assert section_station[0] == {
        "section": "A", "station_id": "ST01",
        "out_km": "1.500", "out_min": "1.50",  # ST01 -> A
        "back_km": "1.000", "back_min": "1.00",  # A -> ST01
    }  # fmt: skip
    pairs = _rows(built[legs_build.STATION_STATION])
    assert pairs == [
        {"station_a": "ST01", "station_b": "ST02", "ab_km": "", "ab_min": "",
         "ba_km": "3.000", "ba_min": "3.00"}
    ]  # fmt: skip
    points = _rows(built[legs_build.POINTS])
    assert [(p["kind"], p["id"], p["snap_m"]) for p in points] == [
        ("section", "A", "12.3"), ("station", "ST01", "0.5"), ("station", "ST02", "40.0")
    ]  # fmt: skip


def test_committed_legs_cover_every_section_and_station_pair() -> None:
    sections, stations = legs_build.read_points(ROOT)
    with (ROOT / legs_build.SECTION_STATION).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(sections) * len(stations)
    assert all(r["out_km"] and r["back_km"] for r in rows)
    log = (ROOT / legs_build.LOG).read_text(encoding="utf-8")
    assert "SHA-256" in log and "ODbL" in log and "Basis: DERIVED" in log
