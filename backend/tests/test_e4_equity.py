import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("equity", ROOT / "scripts/evidence/build_equity.py")
equity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(equity)


def test_gini_edge_cases():
    assert equity.gini([10, 10, 10]) == pytest.approx(0)
    assert equity.gini([0, 0, 30]) == pytest.approx(2 / 3)
    assert equity.gini([]) is None
    assert equity.gini([0, 0]) is None
    with pytest.raises(ValueError):
        equity.gini([-1, 1])
    assert equity.per_thousand(None, 100) is None
    assert equity.per_thousand(10, 0) is None
    assert equity.per_thousand(10, 2000) == 5


def test_mapping_mass_and_review_gate():
    mappings = [
        {
            "section": "A",
            "ward_id": ward,
            "weight": weight,
            "reviewer_status": "approved",
            "source_url": "https://example.test/fixture",
        }
        for ward, weight in [("W1", 0.25), ("W2", 0.75)]
    ]
    counts, missing = equity.transfer({"A": 100, "B": 5}, mappings)
    assert counts == {"W1": 25, "W2": 75}
    assert missing == ["B"]
    with pytest.raises(ValueError):
        equity.transfer({"A": 100}, [{**mappings[0], "reviewer_status": "pending"}])
    with pytest.raises(ValueError):
        equity.transfer({"A": 100}, [mappings[0]])


def test_real_metrics_and_missing_data():
    artifacts = equity.build()
    assert artifacts == equity.build()
    assert all((ROOT / p).read_bytes() == b for p, b in artifacts.items())
    summary = json.loads(artifacts[equity.OUT + "summary.json"])
    assert summary["section_count"] == 201
    assert summary["source_row_count"] == 4398
    assert summary["bookings"] == 1316215
    assert summary["delivered"] == 1315622
    assert summary["gini"] == pytest.approx(0.780329296, abs=1e-9)
    assert summary["top_section_count"] == 21
    assert summary["top_booking_share"] == pytest.approx(0.676969188, abs=1e-9)
    assert summary["missing_source_months"] == ["2022-12"]
    lorenz = list(csv.DictReader(io.StringIO(artifacts[equity.OUT + "lorenz.csv"].decode())))
    assert len(lorenz) == 202
    assert float(lorenz[0]["booking_fraction"]) == 0
    assert float(lorenz[-1]["booking_fraction"]) == 1
    assert all(
        float(a["booking_fraction"]) <= float(b["booking_fraction"])
        for a, b in zip(lorenz, lorenz[1:], strict=False)
    )
    wards = list(csv.DictReader(io.StringIO(artifacts[equity.OUT + "wards.csv"].decode())))
    assert len(wards) == 145


def test_section_rate_uses_official_domestic_connections():
    """Bookings per 1,000 HMWSSB domestic connections per month: REAL counts over a REAL
    denominator, no geography needed. Per-1,000-people stays empty (no section population)."""
    artifacts = equity.build()
    sections = list(csv.DictReader(io.StringIO(artifacts[equity.OUT + "sections.csv"].decode())))
    with_rate = [r for r in sections if r["bookings_per_1000_connections"]]
    # 7 of 201 sections are facilities or not billed (control room, WTP, pipelines)
    assert len(with_rate) >= 190
    for row in with_rate:
        assert row["denominator_status"] == "HMWSSB_DOMESTIC_CONNECTIONS"
        expected = 1000 * int(row["bookings"]) / int(row["observed_months"])
        expected /= float(row["domestic_connections_mean"])
        assert float(row["bookings_per_1000_connections"]) == pytest.approx(
            expected, rel=1e-5, abs=1e-6
        )  # stored mean is rounded
        assert 0 <= float(row["flats_connection_share"]) <= 1
        assert row["population"] == "" and row["bookings_per_1000"] == ""
    summary = json.loads(artifacts[equity.OUT + "summary.json"])
    assert summary["section_rate_denominator"].startswith("HMWSSB billing")
    madhapur = next(r for r in sections if r["section"] == "MADHAPUR")
    median = sorted(float(r["bookings_per_1000_connections"]) for r in with_rate)[
        len(with_rate) // 2
    ]
    assert float(madhapur["bookings_per_1000_connections"]) > 10 * median


def test_ward_bookings_are_approximate_and_preserve_placed_bookings():
    artifacts = equity.build()
    wards = list(csv.DictReader(io.StringIO(artifacts[equity.OUT + "wards.csv"].decode())))
    sections = list(csv.DictReader(io.StringIO(artifacts[equity.OUT + "sections.csv"].decode())))
    links = {
        (r["division"], r["section"]): r["ward_id"]
        for r in csv.DictReader(
            (ROOT / "data/derived/crosswalk/section_ward_building_weights.csv").open(
                encoding="utf-8"
            )
        )
        if r["ward_id"]
    }
    placed = sum(int(r["bookings"]) for r in sections if (r["division"], r["section"]) in links)
    with_bookings = [w for w in wards if w["bookings"]]
    assert sum(float(w["bookings"]) for w in with_bookings) == pytest.approx(placed)
    for ward in wards:
        if ward["bookings"]:
            assert ward["mapping_status"].startswith("VORONOI_DIVISION_HULL_")
            assert ward["basis"] == "DERIVED_APPROXIMATE"
            assert ward["bookings_per_1000"] == ""
        else:
            assert ward["mapping_status"] == "NO_PLACED_SECTION"
            assert ward["bookings_per_1000"] == ""
    summary = json.loads(artifacts[equity.OUT + "summary.json"])
    assert summary["ward_booking_share_placed"] >= 0.75
    assert summary["ward_metrics_status"].startswith("VORONOI_DIVISION_HULL_")
