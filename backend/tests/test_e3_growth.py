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
    # Growth stays a covariate: no household projection (R-P1)
    assert all(r["adjusted_current_households"] == "" for r in rows)
    summary = json.loads(outputs[growth.OUT + "summary.json"])
    assert summary["multi_source_growth_range"] is None
    assert summary["usable_growth_ratios"] == sum(r["building_growth_ratio"] != "" for r in rows)
    assert all(r["basis"] in ("DERIVED", "UNAVAILABLE") for r in annual)
    assert all(
        r["growth_stability"] in ("INSUFFICIENT_HISTORY", "STABLE_TREND", "REVIEW_NOISY_TREND")
        for r in rows
    )


def test_census_comes_from_e2_placement_not_the_old_number_join():
    outputs = growth.aggregate()
    rows = list(csv.DictReader(io.StringIO(outputs[growth.OUT + "growth.csv"].decode())))
    e2 = {
        r["ward_id"]: r
        for r in csv.DictReader(
            (ROOT / "data/derived/evidence/ward_evidence.csv").open(encoding="utf-8")
        )
    }
    for row in rows:
        assert row["census_location_status"] == e2[row["ward_id"]]["location_status"]
        assert row["census_households_2011"] == e2[row["ward_id"]]["households"]
    summary = json.loads(outputs[growth.OUT + "summary.json"])
    assert summary["approximate_census_joins"] == 143
    assert summary["exact_geometry_census_joins"] == 0


def test_city_wide_year_shocks_are_removed_before_judging_stability():
    """Open Buildings counts jump city-wide from year to year (Google: cloud cover, image
    misalignment, fewer 2016-17 frames). Removing the shared shocks, not the city trend,
    leaves each ward's own trend to judge."""
    outputs = growth.aggregate()
    summary = json.loads(outputs[growth.OUT + "summary.json"])
    shocks = summary["stability"]["city_year_shocks_log"]
    assert len(shocks) == 8 and abs(sum(shocks)) < 1e-6
    assert summary["stability"]["city_trend_annual_growth"] > 0.02
    rows = list(csv.DictReader(io.StringIO(outputs[growth.OUT + "growth.csv"].decode())))
    stable = [r for r in rows if r["growth_stability"] == "STABLE_TREND"]
    assert len(stable) >= 140
    for row in stable:
        assert float(row["trend_t"]) >= growth.CONFIG.minimum_trend_t
        assert row["adjusted_annual_growth"] != ""


def test_building_trend_agrees_with_hmwssb_connection_growth():
    """Independent check (F2): wards whose buildings grew faster gained more water connections
    (HMWSSB billing 2022 -> 2025, sections placed on wards)."""
    outputs = growth.aggregate()
    check = json.loads(outputs[growth.OUT + "summary.json"])["independent_checks"]
    assert check["connection_growth"]["wards"] >= 80
    assert check["connection_growth"]["spearman"] >= 0.4
    rows = list(csv.DictReader(io.StringIO(outputs[growth.OUT + "growth.csv"].decode())))
    assert (
        sum(r["connection_growth_2022_2025"] != "" for r in rows)
        == check["connection_growth"]["wards"]
    )


def test_reproducible_and_hash_register():
    outputs = growth.aggregate()
    checks = json.loads((ROOT / "data/verification/growth_checks.json").read_text())
    assert checks["output_sha256"] == {
        path: __import__("hashlib").sha256(data).hexdigest()
        for path, data in outputs.items()
        if path.startswith(growth.OUT)
    }
