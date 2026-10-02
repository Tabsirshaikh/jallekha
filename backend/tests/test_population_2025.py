"""2025 ward population estimate (removes the "Census 2011 is too old" block).

Three estimates per ward: Census 2011 x building trend (E3), GHS-POP 2025 level, Census 2011
x GHS-POP 2015->2025 growth. Central: the building growth pattern (the one that predicts
HMWSSB connection growth), scaled so the city grows at HMWSSB's real domestic-connection
rate. Each ward keeps a low-high range over all estimates.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "population", ROOT / "scripts/evidence/build_population.py"
)
population = importlib.util.module_from_spec(spec)
spec.loader.exec_module(population)


@pytest.fixture(scope="module")
def built() -> dict[str, bytes]:
    return population.build()


def table(built) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(built[population.OUTPUT].decode())))


def test_ghs_crops_match_their_manifest() -> None:
    manifest = json.loads((ROOT / "data/derived/population_inputs/manifest.json").read_text())
    assert [f["year"] for f in manifest["files"]] == [2015, 2025]
    for entry in manifest["files"]:
        assert entry["licence"].startswith("CC BY 4.0")
        crop = (ROOT / entry["crop_file"]).read_bytes()
        assert hashlib.sha256(crop).hexdigest() == entry["crop_sha256"]


def test_artifacts_are_reproducible_and_committed(built) -> None:
    assert built == population.build()
    for path, content in built.items():
        assert (ROOT / path).read_bytes() == content


def test_every_census_ward_gets_a_central_value_inside_its_range(built) -> None:
    rows = table(built)
    assert len(rows) == 145
    estimated = [r for r in rows if r["population_2025_central"]]
    assert len(estimated) == 143
    for row in estimated:
        low, high = float(row["population_2025_low"]), float(row["population_2025_high"])
        central = float(row["population_2025_central"])
        assert low <= central <= high
        assert float(row["households_2025_central"]) == pytest.approx(
            central / float(row["household_size_2011"]), rel=1e-6
        )
        assert row["basis"] == "MODELLED_ESTIMATE"


def test_city_growth_follows_hmwssb_connection_growth(built) -> None:
    summary = json.loads(built[population.SUMMARY])
    rate = summary["city"]["connection_growth_annual"]
    assert 0.015 < rate < 0.03  # 2.18%/yr, 2022 -> 2025
    census, central = summary["city"]["census_2011"], summary["city"]["central_2025"]
    assert central == pytest.approx(census * (1 + rate) ** population.YEARS_SINCE_CENSUS, rel=1e-3)
    # the building and GHS-POP estimates bracket the central city total
    assert summary["city"]["ghs_growth_2025"] < central < summary["city"]["buildings_2025"]


def test_central_uses_the_growth_pattern_that_predicts_connections(built) -> None:
    """Independent official signal: HMWSSB domestic connection growth by ward (2022-2025).
    The building pattern predicts it; GHS-POP's ward growth (national rate spread almost evenly)
    does not, so GHS-POP only enters the level and the range."""
    checks = json.loads(built[population.SUMMARY])["checks"]
    assert checks["buildings_vs_connections_spearman"] >= 0.4
    assert checks["ghs_growth_vs_connections_spearman"] < 0.2
    assert checks["central_pattern"] == "BUILDINGS"
    assert checks["central_vs_connection_growth"]["wards"] >= 80


def test_wide_ranges_are_flagged(built) -> None:
    for row in table(built):
        if row["population_2025_central"]:
            spread = float(row["range_spread"])
            assert (row["review_flag"] == "WIDE_RANGE") == (spread > population.WIDE_RANGE)
