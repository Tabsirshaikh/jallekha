import csv
import importlib.util
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("growth", ROOT / "scripts/evidence/build_growth.py")
growth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(growth)


def test_real_growth_outputs_are_deterministic_and_block_household_claims():
    outputs = growth.aggregate()
    assert outputs == growth.aggregate()
    for path, data in outputs.items():
        if path != "data/verification/growth_checks.json":
            assert (ROOT / path).read_bytes() == data
    rows = list(csv.DictReader(io.StringIO(outputs[growth.OUT + "growth.csv"].decode())))
    annual = list(csv.DictReader(io.StringIO(outputs[growth.OUT + "annual.csv"].decode())))
    assert len(rows) == 145
    assert len(annual) == 145 * 8
    assert all(r["adjusted_current_households"] == "" for r in rows)
    assert all(r["census_households_2011"] == "" for r in rows)
    assert all(r["booking_validation"].startswith("BLOCKED") for r in rows)
    summary = json.loads(outputs[growth.OUT + "summary.json"])
    assert summary["validated_census_joins"] == 0
    assert summary["multi_source_growth_range"] is None
    assert summary["usable_growth_ratios"] == sum(r["building_growth_ratio"] != "" for r in rows)
    assert all(r["basis"] in ("DERIVED", "UNAVAILABLE") for r in annual)
    assert all(
        r["growth_stability"]
        in (
            "INSUFFICIENT_HISTORY",
            "REVIEW_HIGH_VARIABILITY",
            "NO_HIGH_VARIABILITY_FLAG",
            "UNCLASSIFIED_NEAR_ZERO_MEAN",
        )
        for r in rows
    )
    checks = json.loads((ROOT / "data/verification/growth_checks.json").read_text())
    assert checks["output_sha256"] == {
        path: __import__("hashlib").sha256(data).hexdigest()
        for path, data in outputs.items()
        if path.startswith(growth.OUT)
    }
