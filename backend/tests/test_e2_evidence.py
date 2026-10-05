"""Evidence formula, failure handling and actual artifact contract tests."""

import csv
import importlib.util
import io
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "evidence", ROOT / "scripts/evidence/build_evidence.py"
)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


@pytest.mark.parametrize("value", [None, "", "NA", -1, 101, float("nan"), True])
def test_invalid_percentage_is_unknown(value):
    assert evidence.percentage(value) is None


def test_formulas_and_missing_components():
    row = [None] * 139
    for index, value in {
        82: 20,
        83: 10,
        71: 60,
        72: 15,
        131: 10,
        132: 50,
        133: 20,
        48: 5,
        49: 25,
        13: 3,
        138: 12,
    }.items():
        row[index] = value
    actual = evidence.metrics(tuple(row))
    assert actual["wad"] == 0.3
    assert actual["non_tap_share"] == 0.25
    assert actual["cad"] == 0.2
    assert actual["hardship"] == 0.15
    row[49] = None
    assert evidence.metrics(tuple(row))["hardship"] is None
    assert evidence.share([100, 0.01], complement=True) == 0
    assert evidence.share([80, 30]) is None


STATUSES = {
    "AREAL_2009_CROSSWALK",
    "PARTIAL_CENSUS_COVERAGE",
    "NO_CENSUS_ROW",
    "HH14_MISSING",
    "HH14_AMBIGUOUS",
}


@pytest.fixture(scope="module")
def built():
    return evidence.build()


def _rows(artifacts):
    return list(csv.DictReader(io.StringIO(artifacts[evidence.OUTPUT].decode())))


def test_real_artifacts_are_reproducible(built):
    assert built == evidence.build()
    for path, content in built.items():
        assert (ROOT / path).read_bytes() == content


def test_every_2016_ward_has_a_row_and_a_known_status(built):
    rows = _rows(built)
    assert len(rows) == len({r["ward_id"] for r in rows}) == 145
    assert {r["join_status"] for r in rows} <= STATUSES
    assert all(r["crosswalk_method"] == "BUILDING_WEIGHTED_2009_MAP" for r in rows)


def test_eligible_wards_have_complete_derived_values(built):
    rows = _rows(built)
    eligible = [r for r in rows if r["allocation_eligible"] == "True"]
    assert len(eligible) >= 120
    for row in eligible:
        assert row["join_status"] == "AREAL_2009_CROSSWALK"
        assert float(row["census_coverage"]) >= evidence.MIN_CENSUS_COVERAGE
        for key in evidence.METRICS:
            assert row[key] != "" and row[key + "_basis"] == "DERIVED"
    for row in rows:
        if row["allocation_eligible"] != "True":
            assert row["review_required"] == "True"


def test_every_ward_gets_its_d9_facility_count(built):
    """Facility counts do not depend on the Census join, so every ward has one (item 15)."""
    with (ROOT / evidence.FACILITIES).open(encoding="utf-8", newline="") as handle:
        d9 = {r["ward_id"]: r["critical_facilities"] for r in csv.DictReader(handle)}
    rows = _rows(built)
    for row in rows:
        assert row["critical_facilities"] == d9[row["ward_id"]]
        assert row["critical_facilities_basis"] == "DERIVED"
        flags = row["quality_flags"].split(";")
        assert "FACILITIES_UNAVAILABLE" not in flags
        assert "FACILITIES_OSM_INCOMPLETE" in flags
    assert evidence.FACILITIES in evidence.INPUTS


def test_census_goes_to_the_right_place_not_the_same_number(built):
    """Census ward numbers follow the 2009 map; 2016 ward 91 is Khairatabad (2009 ward 96),
    2016 ward 105 is Gachibowli (2009 wards 111-112)."""
    by_name = {r["ward_name"]: r for r in _rows(built)}

    def sources(name: str) -> list[str]:
        return [part.split(":")[0] for part in by_name[name]["source_units"].split(";")]

    # The 2016 ward was drawn from parts of 2009 wards 96 (Khairtabad) and 97 (Punjagutta);
    # 2009 ward 91 (Musheerabad), which the old number join used, is not a source.
    assert "96" in sources("Ward 91 Khairatabad")[:2]
    assert "91" not in sources("Ward 91 Khairatabad")
    assert sources("Ward 105 Gachibowli")[0] == "111+112"
    assert "105" not in sources("Ward 105 Gachibowli")


def test_households_are_conserved(built):
    rows = _rows(built)
    estimated = sum(int(r["households"]) for r in rows if r["households"])
    census = evidence.census_unit_totals()["households"]
    # Some census households sit in the six 2016 wards missing from the DataMeet layer.
    assert 0.85 * census <= estimated <= census


@pytest.mark.parametrize("candidate_count,status", [(0, "HH14_MISSING"), (2, "HH14_AMBIGUOUS")])
def test_hh_join_failure_never_invents_values(monkeypatch, candidate_count, status):
    # Supply absent or duplicate HH-14 records for every census row.
    with (ROOT / evidence.INPUTS[0]).open(encoding="utf-8", newline="") as handle:
        crosswalk = list(csv.DictReader(handle))
    sources = {"536": {}, "537": {}}
    for record in crosswalk:
        row = [None] * 139
        row[4], row[6] = record["source_subdistt_code"], record["source_town_code"]
        sources[record["source_district_code"]].setdefault(
            int(record["source_ward_num"]), []
        ).extend([tuple(row)] * candidate_count)
    monkeypatch.setattr(evidence, "load_hh", lambda _path, district: sources[district])
    rows = _rows(evidence.build())
    assert {r["join_status"] for r in rows} <= {status, "NO_CENSUS_ROW"}
    assert sum(r["join_status"] == status for r in rows) >= 140
    census = [k for k in evidence.METRICS if k != "critical_facilities"]
    assert all(r[k] == "" for r in rows for k in census)
    # Facility counts come from D9 (OSM), not the Census, so a failed join keeps them.
    assert all(r["critical_facilities"] != "" for r in rows)
    assert all(r["allocation_eligible"] == "False" for r in rows)
