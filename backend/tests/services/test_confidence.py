"""T9 confidence gate (F17): signals, gate on A7's planner, calibration on the replay."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from app.config.confidence import CONFIDENCE_CONFIG
from app.services import confidence as cf
from app.services import fair_queue, planner
from app.services.ledger_port import InMemoryLedger
from app.services.planner import PlanInputs, PlannerBooking

REPO = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 5, 10, 5, 0, tzinfo=UTC)
DAY = date(2026, 5, 10)


def _ward(ward_id: str, **overrides: str) -> dict[str, str]:
    row = {
        "ward_id": ward_id,
        "join_status": "AREAL_2009_CROSSWALK",
        "census_coverage": "1.0000",
        "dominant_source_share": "1.0000",
        "allocation_eligible": "True",
        "review_required": "False",
        "census_year": "2011",
    }
    row.update(overrides)
    return row


def _section(
    section: str, ward_id: str, method: str = "INSIDE", status: str = "MAPPED", km: str = "1.0"
) -> dict[str, str]:
    return {
        "section": section,
        "ward_id": ward_id,
        "ward_method": method,
        "status": status,
        "division_distance_km": km,
    }


TABLES = cf.SignalTables(
    evidence={
        "A": _ward("A"),
        "B": _ward("B", dominant_source_share="0.3000"),
        "R": _ward("R", review_required="True"),
        "P": _ward(
            "P",
            join_status="PARTIAL_CENSUS_COVERAGE",
            allocation_eligible="False",
            census_coverage="0.5917",
        ),
    },
    sections=[
        _section("SA", "A"),
        _section("SB", "B"),
        _section("SR1", "R"),
        _section("SR2", "R", method="NEAREST_500M"),
        _section("SP", "P", method="WARD_NAME"),
        _section("FAR", "A", km="9.0"),
        _section("LOST", "", method="", status="UNMAPPED_NO_RESULT"),
    ],
)


# --- signals -----------------------------------------------------------------------------


def test_census_join_quality_boundaries() -> None:
    assert cf.score_census("ward:A", TABLES).score == 1.0
    assert cf.score_census("ward:B", TABLES).score == 0.3  # dominant source share
    review_cap = CONFIDENCE_CONFIG.census_review_cap
    assert cf.score_census("ward:R", TABLES).score == review_cap
    partial = cf.score_census("ward:P", TABLES)
    assert partial.score == 0.0 and partial.available and "PARTIAL_CENSUS_COVERAGE" in partial.basis
    assert cf.score_census("ward:UNKNOWN", TABLES).score == 0.0
    section = cf.score_census("section:LOST", TABLES)
    assert section.score == 0.0 and "fallback" in section.basis.lower()


def test_section_location_boundaries() -> None:
    methods = dict(CONFIDENCE_CONFIG.location_method_scores)
    assert cf.score_location("ward:B", TABLES).score == methods["INSIDE"] == 1.0
    assert cf.score_location("ward:R", TABLES).score == methods["NEAREST_500M"]  # weakest section
    assert cf.score_location("ward:P", TABLES).score == methods["WARD_NAME"]
    # A section farther than P1's outlier distance (6 km) caps the ward's score.
    assert cf.score_location("ward:A", TABLES).score == CONFIDENCE_CONFIG.location_outlier_cap
    lost = cf.score_location("section:LOST", TABLES)
    assert lost.score == 0.0 and "UNMAPPED_NO_RESULT" in lost.basis


def test_data_age_is_implemented_but_cannot_separate_wards() -> None:
    age = cf.score_data_age("ward:A", TABLES, today=DAY)
    assert not age.available and age.score is None
    assert "2011" in age.basis and "does not separate wards" in age.basis and "OPEN" in age.basis


def test_interval_width_and_evidence_age_are_unavailable_on_main() -> None:
    width = cf.score_interval_width("ward:A", cf.UnavailableIntervalWidth())
    assert not width.available and "T2" in width.basis
    evidence = cf.score_evidence_age("ward:A")
    assert not evidence.available and "no dated evidence" in evidence.basis


def test_interval_width_scores_when_a_source_exists() -> None:
    class Source:
        def relative_width(self, group: str) -> float | None:
            return {"ward:A": 0.0, "ward:B": CONFIDENCE_CONFIG.interval_width_zero_at}.get(group)

    assert cf.score_interval_width("ward:A", Source()).score == 1.0
    assert cf.score_interval_width("ward:B", Source()).score == 0.0
    assert not cf.score_interval_width("ward:C", Source()).available


# --- combination -------------------------------------------------------------------------


def test_missing_signals_are_excluded_and_listed_and_the_reason_names_the_weakest() -> None:
    result = cf.T9Gate(TABLES).explain("ward:B")
    assert result.used == ("census_join_quality", "section_location")
    assert set(result.unavailable) == {"data_age", "forecast_interval_width", "evidence_age"}
    assert result.confidence == 0.3  # minimum of the available signals
    assert "census_join_quality=0.3000" in result.reason
    assert "unavailable: data_age, evidence_age, forecast_interval_width" in result.reason


def test_no_available_signal_means_a_check() -> None:
    gate = cf.T9Gate(TABLES)
    result = gate.combine([cf.SignalScore("data_age", False, None, "x")])
    assert result.confidence == 0.0 and "no signal available" in result.reason


def test_gate_returns_a7_assessments() -> None:
    gate = cf.T9Gate(TABLES, threshold=0.5)
    out = gate.assess(["ward:A", "ward:B", "section:LOST"])
    assert isinstance(out["ward:B"], planner.Assessment)
    assert (out["ward:B"].needs_check, out["section:LOST"].needs_check) == (True, True)
    assert out["ward:A"].needs_check is (out["ward:A"].confidence < 0.5)
    assert out["ward:B"].basis.startswith("DERIVED")


# --- done-when, with A7's own functions --------------------------------------------------


def _pending(station: str, group: str, n: int, start: int = 0) -> list[PlannerBooking]:
    first = NOW - timedelta(hours=10)
    return [
        PlannerBooking(
            fair_queue.QueueBooking(
                booking_id=f"{group}-{start + i:03d}",
                group=group,
                arrived_at=first + timedelta(minutes=start + i),
                tier=2,
                consumer_id=f"c-{group}-{start + i}",
                category="domestic",
            ),
            station,
        )
        for i in range(n)
    ]


def test_low_confidence_cannot_auto_commit() -> None:
    chain = InMemoryLedger(key="test-ledger-key", clock=lambda: NOW)
    gate = cf.T9Gate(
        cf.SignalTables(
            evidence={"A": _ward("A"), "B": _ward("B", dominant_source_share="0.3000")},
            sections=[_section("SA", "A"), _section("SB", "B")],
        ),
        threshold=0.5,
    )
    data = PlanInputs(
        plan_id="P-2026-05-10",
        day=DAY,
        capacity={"S1": 10},
        pending=_pending("S1", "ward:A", 8) + _pending("S1", "ward:B", 8, start=100),
        entitlement={"ward:A": 1.0, "ward:B": 1.0},
    )
    plan = planner.build_plan(data, gate, chain, NOW)
    assert set(plan.flags) == {"ward:B"}
    with pytest.raises(planner.PlanBlocked, match="ward:B"):
        planner.approve_plan(plan, "officer-1", "Looks right", chain, NOW)
    with pytest.raises(ValueError, match="reason"):
        planner.mark_checked(plan, "ward:B", "officer-1", "   ", chain, NOW)
    checked = planner.mark_checked(
        plan, "ward:B", "officer-1", "Census mix verified on site", chain, NOW
    )
    approved = planner.approve_plan(checked, "officer-1", "Checked group B", chain, NOW)
    assert approved.status == "APPROVED"
    events = [e.event_type for e in chain.entries if e.entity_id == plan.plan_id]
    assert events == ["plan_created", "ward_reviewed", "plan_approved"]
    assert chain.verify().valid


# --- real files --------------------------------------------------------------------------


def test_gate_on_the_real_files() -> None:
    tables = cf.SignalTables.from_files(REPO)
    with (REPO / "data/derived/planner_replay/groups.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups = sorted({r["group"] for r in rows})
    fallback = {r["group"] for r in rows if r["need_basis"] == "FALLBACK_MEDIAN"}
    out = cf.T9Gate(tables).assess(groups)
    assert set(out) == set(groups)
    # Every group the replay marks as fallback (no Census need) gets confidence 0 here too.
    assert fallback and all(out[g].confidence == 0.0 and out[g].needs_check for g in fallback)
    with (REPO / "data/derived/evidence/ward_evidence.csv").open(encoding="utf-8") as handle:
        evidence = {r["ward_id"]: r for r in csv.DictReader(handle)}
    for group in groups:
        if (
            group.startswith("ward:")
            and evidence.get(group[5:], {}).get("allocation_eligible") == "True"
        ):
            assert out[group].confidence > 0.0


# --- calibration -------------------------------------------------------------------------


def test_calibration_picks_the_lowest_threshold_meeting_the_target() -> None:
    # Confidences: a 0.2, b 0.6, c 0.9. Group-days: a never matches, b matches 1 of 2, c always.
    confidences = {"a": 0.2, "b": 0.6, "c": 0.9}
    days = [cf.GroupDay("a", 1, False), cf.GroupDay("a", 2, False),
            cf.GroupDay("b", 1, True), cf.GroupDay("b", 2, False),
            cf.GroupDay("c", 1, True), cf.GroupDay("c", 2, True)]  # fmt: skip
    result = cf.calibrate(days, confidences, thresholds=(0.0, 0.5, 0.8, 1.0), target=0.75)
    rows = {r.threshold: r for r in result.rows}
    assert rows[0.0].match_share == pytest.approx(3 / 6) and rows[0.0].flagged_share == 0.0
    assert rows[0.5].match_share == pytest.approx(3 / 4) and rows[
        0.5
    ].flagged_share == pytest.approx(2 / 6)
    assert rows[0.8].match_share == 1.0
    assert rows[1.0].match_share is None and rows[1.0].flagged_share == 1.0
    assert (result.status, result.chosen) == ("chosen", 0.5)


def test_calibration_says_when_it_cannot_choose() -> None:
    days = [cf.GroupDay("a", 1, False), cf.GroupDay("b", 1, False)]
    unreachable = cf.calibrate(days, {"a": 0.5, "b": 0.5}, thresholds=(0.0, 0.5, 1.0), target=0.9)
    assert (unreachable.status, unreachable.chosen) == ("unreachable", None)
    # Target met with nothing flagged: the thresholds cannot be told apart, so none is chosen.
    matching = [cf.GroupDay("a", 1, True), cf.GroupDay("b", 1, True)]
    flat = cf.calibrate(matching, {"a": 0.2, "b": 0.8}, thresholds=(0.0, 0.5, 1.0), target=0.9)
    assert (flat.status, flat.chosen) == ("not_separable", None)


def test_outlier_distance_is_p1s_value() -> None:
    summary = json.loads(
        (REPO / CONFIDENCE_CONFIG.section_summary_path).read_text(encoding="utf-8")
    )
    assert CONFIDENCE_CONFIG.location_outlier_km == summary["checks"]["outlier_km"]


def test_committed_selection_is_the_config_threshold() -> None:
    with (REPO / CONFIDENCE_CONFIG.calibration_path).open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    selection = [r for r in rows if r["row_type"] == "selection"]
    assert len(selection) == 1
    row = selection[0]
    assert row["scenario"] == "degraded_signals"
    seeds = {r["seed"] for r in rows if r["row_type"] == "threshold"}
    assert len(seeds) == CONFIDENCE_CONFIG.degraded_seeds
    if row["status"] == "chosen":
        if CONFIDENCE_CONFIG.threshold_basis == "OWNER_DECISION":
            # A recorded decision may differ from the rule; the rule's own pick must stay current.
            picked = CONFIDENCE_CONFIG.rule_threshold
        else:
            assert CONFIDENCE_CONFIG.threshold_basis == "DERIVED"
            picked = CONFIDENCE_CONFIG.threshold
        assert float(row["threshold"]) == pytest.approx(picked, abs=0.005)
        # Every draw meets the target at the chosen threshold.
        at = [
            r for r in rows if r["row_type"] == "threshold" and r["threshold"] == row["threshold"]
        ]
        assert all(float(r["match_share"]) >= CONFIDENCE_CONFIG.target_match_share for r in at)
    else:
        assert CONFIDENCE_CONFIG.threshold_basis == "PROVISIONAL"
        assert float(row["threshold"]) == pytest.approx(
            CONFIDENCE_CONFIG.provisional_threshold, abs=0.005
        )
        assert "PROVISIONAL" in row["match_share_basis"]


def _calibration_script():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "calibrate_confidence", REPO / "scripts/trust/calibrate_confidence.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_committed_calibration_reproduces_within_tolerance(tmp_path: Path) -> None:
    # One error draw (seed 0) keeps the test to two replays; it must equal the committed rows.
    script = _calibration_script()
    assert script.main(["--out", str(tmp_path / "calibration.csv"), "--seeds", "1"]) == 0
    with (tmp_path / "calibration.csv").open(encoding="utf-8") as handle:
        fresh = [r for r in csv.DictReader(handle) if r["row_type"] == "threshold"]
    with (REPO / "data/derived/confidence_calibration.csv").open(encoding="utf-8") as handle:
        committed = [r for r in csv.DictReader(handle) if r["seed"] == "0"]
    assert [r["threshold"] for r in fresh] == [r["threshold"] for r in committed]
    tol = CONFIDENCE_CONFIG.reproduce_tolerance
    for a, b in zip(fresh, committed, strict=True):
        assert a["row_type"] == b["row_type"] and a["status"] == b["status"]
        assert (a["damaged_groups"], a["caught_groups"]) == (
            b["damaged_groups"],
            b["caught_groups"],
        )
        for column in ("match_share", "flagged_share", "caught_share"):
            if a[column] or b[column]:
                assert abs(float(a[column]) - float(b[column])) <= tol, (a["threshold"], column)
        assert a["label"] == "SIMULATION" and a["match_share_basis"]


# --- degraded-signal scenario (item 18) --------------------------------------------------

NEIGHBOURS = {"A": ("B", "P"), "B": ("A",), "P": ("A",), "R": ("A",)}


def _degraded_config(**changes: object):  # type: ignore[no-untyped-def]
    import dataclasses

    base = dict(
        degraded_move_probability=(("INSIDE", 0.0), ("NEAREST_500M", 0.0), ("WARD_NAME", 1.0)),
        degraded_outlier_move_probability=1.0,
        degraded_need_error_sd=1.0,
        degraded_need_error_sd_floor=0.0,
    )
    base.update(changes)
    return dataclasses.replace(CONFIDENCE_CONFIG, **base)


def test_degrade_moves_weakly_placed_sections_to_a_neighbouring_ward() -> None:
    config = _degraded_config()
    groups = ["ward:A", "ward:B", "ward:P", "ward:R", "section:LOST"]
    d = cf.degrade(7, TABLES, groups, NEIGHBOURS, config)
    # WARD_NAME (SP) and the 9 km outlier (FAR) always move here; INSIDE and NEAREST_500M never;
    # an unplaced section has no ward to move from.
    assert set(d.moved) == {"SP", "FAR"}
    assert d.moved["SP"] in NEIGHBOURS["P"] and d.moved["FAR"] in NEIGHBOURS["A"]
    assert d == cf.degrade(7, TABLES, groups, NEIGHBOURS, config)  # seeded


def test_need_error_grows_as_census_join_quality_falls() -> None:
    config = _degraded_config()
    groups = ["ward:A", "ward:B", "section:LOST"]
    factors = [cf.degrade(s, TABLES, groups, NEIGHBOURS, config).need_factor for s in range(20)]
    # A's Census join scores 1: no error. B (0.3) and an unplaced section (0) get errors.
    assert all(f["ward:A"] == 1.0 for f in factors)
    assert any(abs(f["ward:B"] - 1) > 0.05 for f in factors)
    assert any(abs(f["section:LOST"] - 1) > 0.05 for f in factors)
    floor = _degraded_config(degraded_need_error_sd=0.0, degraded_need_error_sd_floor=0.0)
    assert set(cf.degrade(3, TABLES, groups, NEIGHBOURS, floor).need_factor.values()) == {1.0}


def test_error_groups_are_where_a_section_moved_or_need_is_far_off() -> None:
    config = _degraded_config(degraded_error_need_share=0.25)
    d = cf.Degradation(
        seed=0,
        moved={"SP": "A"},
        need_factor={"ward:A": 1.0, "ward:B": 1.3, "ward:R": 0.9, "ward:P": 1.0},
    )
    # SP was placed in P (its group is wrong); B's need is 30% off; R's 10% is within tolerance.
    assert cf.error_groups(d, TABLES, config) == frozenset({"ward:P", "ward:B"})


def _row(t: float, share: float | None, flagged: int = 0) -> cf.CalibrationRow:
    return cf.CalibrationRow(t, 10, 10, 9, share, 4, flagged, flagged / 4)


def _cal(*shares: float | None) -> cf.Calibration:
    rows = tuple(
        _row(t, s, i) for i, (t, s) in enumerate(zip((0.0, 0.5, 1.0), shares, strict=True))
    )
    return cf.Calibration(rows, 0.9, "n/a", None)


def test_threshold_must_meet_the_target_in_every_seed() -> None:
    # Seed 1 meets the target with nothing flagged, seed 0 needs 0.5: 0.5 is chosen.
    assert cf.choose_across_seeds([_cal(0.85, 0.92, None), _cal(0.91, 0.95, None)], 0.9) == (
        "chosen",
        0.5,
    )
    assert cf.choose_across_seeds([_cal(0.91, 0.92, None), _cal(0.95, 0.9, None)], 0.9) == (
        "not_separable",
        None,
    )
    assert cf.choose_across_seeds([_cal(0.8, 0.85, None), _cal(0.95, 0.99, None)], 0.9) == (
        "unreachable",
        None,
    )
