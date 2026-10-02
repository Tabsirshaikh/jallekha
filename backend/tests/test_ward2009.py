"""2009 GHMC ward map rebuilt from the official vector PDF, and the 2009 -> 2016 crosswalk.

Census 2011 numbers wards by the 2009 delimitation; the DataMeet layer is 2016. The map is
checked against facts the fit never uses: the Census district of each ward and ward names.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ward2009", ROOT / "scripts/evidence/build_ward2009.py"
)
ward2009 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ward2009)


@pytest.fixture(scope="module")
def built() -> dict[str, bytes]:
    return ward2009.build()


def test_sources_match_manifest() -> None:
    with (ROOT / "data/verification/ward2009_manifest.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {r["dataset_id"] for r in rows} == {
        "W2009-GHMC-ward-map",
        "W2009-ward-names",
        "W2009-hyderabad-district",
    }
    for row in rows:
        payload = (ROOT / row["file_path"]).read_bytes()
        assert len(payload) == int(row["bytes"])
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]
        assert row["basis"] == "REAL" and row["license"]


def test_ward_names_parsed_from_pinned_revision() -> None:
    names = ward2009.ward_names()
    assert len(names) == 150
    assert names[1] == "Kapra"
    assert names[91] == "Musheerabad"
    assert names[105] == "Banjara Hills"


def test_every_2009_ward_number_has_a_polygon(built) -> None:
    features = json.loads(built[ward2009.WARDS])["features"]
    numbers = [n for f in features for n in f["properties"]["ward_numbers_2009"]]
    assert sorted(numbers) == list(range(1, 151))
    merged = [f for f in features if len(f["properties"]["ward_numbers_2009"]) > 1]
    assert [f["properties"]["ward_numbers_2009"] for f in merged] == [[111, 112]]
    for feature in features:
        props = feature["properties"]
        assert props["geo_version"] == "GHMC_2009_150" and props["basis"] == "DERIVED"
        lon, lat = feature["geometry"]["coordinates"][0][0][0]
        assert 78.1 < lon < 78.8 and 17.2 < lat < 17.7


def test_fit_and_independent_checks(built) -> None:
    summary = json.loads(built[ward2009.SUMMARY])
    assert summary["fit"]["outline_iou"] >= 0.85
    assert summary["fit"]["median_boundary_error_m"] <= 250
    # Census places wards 18-56, 61-100, 102-110, 140-150 in Hyderabad district.
    assert summary["checks"]["census_district_agreement"] >= 0.9
    assert summary["checks"]["census_district_false_inside"] == 0
    # Names are never used in the fit; a wrong map would score near 1%.
    assert summary["checks"]["same_name_largest_overlap_share"] >= 0.8


def test_crosswalk_weights_are_shares(built) -> None:
    rows = list(csv.DictReader(io.StringIO(built[ward2009.WEIGHTS].decode())))
    per_source: dict[str, float] = defaultdict(float)
    targets = set()
    for row in rows:
        weight = float(row["building_share"])
        assert 0 < weight <= 1
        assert row["weight_basis"] == "DERIVED"
        per_source[row["source_unit_2009"]] += weight
        targets.add(row["target_ward_id"])
    assert len(per_source) == 149
    # shares are written with 4 decimals, so a sum may exceed 1 by rounding only
    assert all(total <= 1.001 for total in per_source.values())
    # Six 2016 polygons are missing from the DataMeet layer, so a few sources lose some share.
    assert sum(total >= 0.9 for total in per_source.values()) >= 135
    assert len(targets) == 145


def test_committed_artifacts_match_a_fresh_build(built) -> None:
    for name, content in built.items():
        committed = (ROOT / name).read_bytes()
        if name == ward2009.WEIGHTS:
            assert ward2009.weights_close(committed, content)
        elif name == ward2009.WARDS:
            assert ward2009.geojson_close(committed, content)
        else:
            assert ward2009.summary_close(committed, content)
