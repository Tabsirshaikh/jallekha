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
    assert all(w["bookings_per_1000"] == "" for w in wards)
