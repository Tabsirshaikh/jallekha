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


def test_real_artifacts_and_failed_joins():
    first = evidence.build()
    assert first == evidence.build()
    for path, content in first.items():
        assert (ROOT / path).read_bytes() == content
    rows = list(csv.DictReader(io.StringIO(first[evidence.OUTPUT].decode())))
    assert len(rows) == len({r["ward_id"] for r in rows}) == 145
    ambiguous = [r for r in rows if r["join_status"] == "AMBIGUOUS_CROSSWALK"]
    assert len(ambiguous) == 5
    assert any(r["join_status"] == "NO_CROSSWALK" for r in rows)
    for row in rows:
        assert row["review_required"] == "True"
        assert row["allocation_eligible"] == "False"
        assert row["critical_facilities"] == ""
        for key in evidence.METRICS:
            if row["join_status"] != "PROVISIONAL_NUMBER_ONLY":
                assert row[key] == ""
            assert row[key + "_basis"] == ("DERIVED" if row[key] else "UNAVAILABLE")


@pytest.mark.parametrize("candidate_count,status", [(0, "HH14_MISSING"), (2, "HH14_AMBIGUOUS")])
def test_hh_join_failure_never_invents_values(monkeypatch, candidate_count, status):
    # Supply absent or duplicate HH-14 records for every ward while preserving the real crosswalk.
    source = {i: [tuple([None] * 139)] * candidate_count for i in range(1, 151)}
    monkeypatch.setattr(evidence, "load_hh", lambda *_: source)
    rows = list(csv.DictReader(io.StringIO(evidence.build()[evidence.OUTPUT].decode())))
    affected = [r for r in rows if r["join_status"] == status]
    assert len(affected) == 135
    assert all(r[k] == "" for r in affected for k in evidence.METRICS)
