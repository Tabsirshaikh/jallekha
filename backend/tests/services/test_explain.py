"""T7 explanations (F16): ward and booking explanations, counterfactual, templates, debt."""

from __future__ import annotations

import csv
import string
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from app.config.access import ACCESS_CONFIG
from app.config.explain import EXPLAIN_CONFIG, TEMPLATES
from app.services import booking_groups as bg
from app.services import explain as ex
from app.services import fair_queue as fq
from app.services import hmwssb, replay
from app.services import service_models as sm
from app.services.water_debt import DebtAccount

REPO = Path(__file__).resolve().parents[3]
T0 = datetime(2025, 5, 15, 0, 0, tzinfo=UTC)


# --- real inputs, read with plain csv where the test checks values ------------------------


@pytest.fixture(scope="module")
def evidence_rows() -> list[dict[str, str]]:
    with (REPO / "data/derived/evidence/ward_evidence.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def needs(evidence_rows: list[dict[str, str]]) -> dict[str, sm.WardNeed]:
    return {n.ward_id: n for n in sm.build_ward_needs(evidence_rows, [])}


@pytest.fixture(scope="module")
def real_day(needs: dict[str, sm.WardNeed]) -> ex.QueueDay:
    """A real replayed day: A1 replay of the REAL May 2025 section totals (daily split
    SYNTHETIC), division 9's bookings on 15 May as one station's queue (test setup), groups and
    entitlements from A2 / booking_groups on the real files. Capacity is a test setting."""
    rows = hmwssb.read_rows(REPO / "data/raw/hmwssb_tankers_portal")
    days = [d for d in replay.daily_counts(rows, ((2025, 5),), seed=7) if d.day.day == 15]
    mapping = bg.load_section_wards(REPO)
    entitlement, _ = bg.group_entitlements(list(needs.values()), mapping)
    pending = [
        fq.QueueBooking(
            b.booking_id,
            bg.group_for(b.section, mapping),
            b.arrived_at,
            2,
            b.booking_id,
            "domestic",
        )
        for b in replay.arrivals(days, seed=7)
        if b.division == "9"
    ]
    assert len(pending) > 100
    return ex.QueueDay(pending, len(pending) // 3, entitlement, fq.QueueState())


def _number(text: str) -> float | None:
    return float(text) if text not in ("", None) else None


# --- ward explanation --------------------------------------------------------------------


def test_ward_explanation_equals_e2_and_a2_values_on_the_real_table(
    evidence_rows: list[dict[str, str]], needs: dict[str, sm.WardNeed]
) -> None:
    checked = 0
    for row in evidence_rows:
        need = needs[row["ward_id"]]
        e = ex.explain_ward(row, need)
        assert (e.ward_id, e.ward_name) == (row["ward_id"], row["ward_name"])
        assert (e.join_status, e.allocation_eligible, e.review_required) == (
            row["join_status"],
            row["allocation_eligible"] == "True",
            row["review_required"] == "True",
        )
        assert e.check_reasons == need.check_reasons
        assert (e.service_class, e.class_basis) == (need.service_class, need.class_basis)
        if e.status == "census":
            checked += 1
            for name in ("wad", "cad", "hardship"):
                assert getattr(e, name) == _number(row[name]) == getattr(need, name)
                assert getattr(e, f"{name}_basis") == row[f"{name}_basis"]
            assert e.households == need.households == int(float(row["households"]))
            assert e.households_basis == row["households_basis"]
            assert (e.need_weight, e.entitlement, e.need_basis) == (
                need.need_weight,
                need.entitlement,
                need.need_basis,
            )
            assert e.census_label == "Census 2011 / historical 2016 geography"
    # Every eligible ward was checked; the count comes from the file, not a constant.
    assert checked == sum(r["allocation_eligible"] == "True" for r in evidence_rows) > 0


def test_ward_without_census_data_shows_no_numbers(
    evidence_rows: list[dict[str, str]], needs: dict[str, sm.WardNeed]
) -> None:
    partial = [
        r
        for r in evidence_rows
        if r["allocation_eligible"] != "True" or r["join_status"] == "PARTIAL_CENSUS_COVERAGE"
    ]
    assert partial  # read from the file
    for row in partial:
        e = ex.explain_ward(row, needs[row["ward_id"]])
        assert e.status == "no_census_data"
        for name in ("wad", "cad", "hardship", "households", "need_weight", "entitlement"):
            assert getattr(e, name) is None
        for language in ACCESS_CONFIG.supported_languages:
            text = ex.render_ward(e, language)
            assert row["ward_name"] in text
            assert not any(ch.isdigit() for ch in text.replace(row["ward_name"], ""))
        assert "no Census data" in ex.render_ward(e, "en")


def test_facilities_are_shown_as_unavailable_when_e2_has_none(
    evidence_rows: list[dict[str, str]], needs: dict[str, sm.WardNeed]
) -> None:
    row = next(r for r in evidence_rows if r["allocation_eligible"] == "True")
    e = ex.explain_ward(row, needs[row["ward_id"]])
    assert e.critical_facilities == _number(row["critical_facilities"])
    assert e.critical_facilities_basis == row["critical_facilities_basis"]


def test_ward_and_need_must_be_the_same_ward(
    evidence_rows: list[dict[str, str]], needs: dict[str, sm.WardNeed]
) -> None:
    a, b = evidence_rows[0], evidence_rows[1]
    with pytest.raises(ValueError, match="ward"):
        ex.explain_ward(a, needs[b["ward_id"]])


# --- debt --------------------------------------------------------------------------------


def test_debt_is_shown_only_with_a_debt_account(
    evidence_rows: list[dict[str, str]], needs: dict[str, sm.WardNeed]
) -> None:
    row = next(r for r in evidence_rows if r["allocation_eligible"] == "True")
    without = ex.explain_ward(row, needs[row["ward_id"]])
    assert (without.debt.available, without.debt.debt_litres) == (False, None)
    assert "not available yet" in ex.render_ward(without, "en")
    account = DebtAccount(
        f"ward:{row['ward_id']}", 3000.0, debt_litres=1250.0, in_debt_since=date(2025, 5, 10)
    )
    with_debt = ex.explain_ward(row, needs[row["ward_id"]], debt=account)
    assert (with_debt.debt.available, with_debt.debt.debt_litres) == (True, 1250.0)
    assert with_debt.debt.in_debt_since == date(2025, 5, 10)
    assert "1250" in ex.render_ward(with_debt, "en")


# --- booking explanation -----------------------------------------------------------------


def _booking(n: int, group: str, minutes: int, tier: int = 2) -> fq.QueueBooking:
    return fq.QueueBooking(
        f"b{n}", group, T0 + timedelta(minutes=minutes), tier, f"c{n}", "domestic"
    )


def _small_day() -> ex.QueueDay:
    pending = [
        _booking(1, "A", 0),
        _booking(2, "B", 1),
        _booking(3, "A", 2),
        _booking(4, "A", 3),
        _booking(5, "B", 4),
        _booking(6, "C", 5, tier=1),
    ]
    return ex.QueueDay(pending, 4, {"A": 2.0, "B": 1.0, "C": 1.0}, fq.QueueState())


def test_booking_explanation_equals_a3_decision_on_a_real_replayed_day(
    real_day: ex.QueueDay,
) -> None:
    result = fq.order_bookings(
        real_day.pending, real_day.capacity, real_day.entitlement, real_day.state
    )
    for decision in result.served[:: max(1, len(result.served) // 25)]:
        e = ex.explain_booking(real_day, decision.booking.booking_id)
        assert e.status == "served"
        assert (e.position, e.reason, e.arrival_rank) == (
            decision.position,
            decision.reason,
            decision.arrival_rank,
        )
        assert (e.entitlement, e.quantum, e.deficit_before) == (
            decision.entitlement,
            decision.quantum,
            decision.deficit_before,
        )
        assert (e.group, e.tier, e.place) == (
            decision.booking.group,
            decision.booking.tier,
            decision.position,
        )
    waiting = result.waiting[0]
    e = ex.explain_booking(real_day, waiting.booking_id)
    assert e.status == "waiting" and e.position is None and e.place > real_day.capacity


def test_booking_explanation_reports_caps_and_waiting_time() -> None:
    day = _small_day()
    rejected = fq.Rejection(_booking(9, "A", 30), "CAP_DAYS_BETWEEN")
    e = ex.explain_booking(day, "b9", rejections=[rejected])
    assert (e.status, e.cap_reason, e.place) == ("rejected", "CAP_DAYS_BETWEEN", None)
    served = ex.explain_booking(day, "b1", now=T0 + timedelta(hours=5))
    assert served.cap_reason is None and served.waiting_hours == 5.0
    with pytest.raises(ValueError, match="b404"):
        ex.explain_booking(day, "b404")


# --- counterfactual ----------------------------------------------------------------------


def test_debt_is_reported_as_not_part_of_todays_ordering() -> None:
    cf = ex.find_counterfactual(_small_day(), "b5")
    assert ("water_debt", "not part of today's ordering") in cf.not_inputs


def test_counterfactual_moves_the_place_by_exactly_the_claimed_amount() -> None:
    day = _small_day()
    cf = ex.find_counterfactual(day, "b5")
    assert cf.status == "found" and cf.changes
    for change in cf.changes:
        assert change.after_place <= cf.before_place - 1
        assert ex.reproduce(day, "b5", change) == change.after_place  # re-run, same result
        smaller = ex.step_back(change)  # one step less must not be enough (smallest)
        if smaller is not None:
            assert ex.reproduce(day, "b5", smaller) >= cf.before_place


def test_counterfactual_on_a_real_replayed_day(real_day: ex.QueueDay) -> None:
    result = fq.order_bookings(
        real_day.pending, real_day.capacity, real_day.entitlement, real_day.state
    )
    target = result.waiting[0].booking_id
    cf = ex.find_counterfactual(real_day, target)
    assert cf.before_place > real_day.capacity
    assert cf.status == "found" and cf.changes  # not vacuous
    for change in cf.changes:
        assert ex.reproduce(real_day, target, change) == change.after_place <= cf.before_place - 1


def test_varied_inputs_are_real_inputs_of_order_bookings() -> None:
    cf = ex.find_counterfactual(_small_day(), "b5")
    assert {c.input for c in cf.changes} <= {
        "tier",
        "arrival",
        "group_entitlement",
        "group_deficit",
    }


def test_no_change_within_limits_is_a_valid_result() -> None:
    day = _small_day()
    first = ex.find_counterfactual(day, "b6")  # tier 1 is served first: nothing to improve
    assert first.status == "already_first" and first.changes == ()
    tight = replace(
        EXPLAIN_CONFIG,
        arrival_max_minutes=0,
        entitlement_max_ratio=1.0,
        deficit_max=0.0,
        try_tier_change=False,
    )
    none = ex.find_counterfactual(day, "b5", config=tight)
    assert (none.status, none.changes) == ("no_change_within_limits", ())
    assert "No single change" in ex.render_counterfactual(none, "en")


def test_counterfactual_text_uses_the_real_numbers() -> None:
    day = _small_day()
    cf = ex.find_counterfactual(day, "b5")
    text = ex.render_counterfactual(cf, "en")
    for change in cf.changes:
        assert str(change.after_place) in text and str(cf.before_place) in text


# --- templates ---------------------------------------------------------------------------


def test_every_template_key_renders_in_all_four_languages() -> None:
    assert set(ACCESS_CONFIG.supported_languages) == {"te", "ur", "hi", "en"}
    for key, by_language in TEMPLATES.items():
        assert set(by_language) == {"te", "ur", "hi", "en"}, key
        fields = {
            name
            for text in by_language.values()
            for _, name, _, _ in string.Formatter().parse(text)
            if name
        }
        params = {name: "7" for name in fields}
        for language in by_language:
            rendered = ex.render(key, language, params)
            assert "{" not in rendered and "}" not in rendered, (key, language)
        # Every language uses the same parameters as English.
        en_fields = {n for _, n, _, _ in string.Formatter().parse(by_language["en"]) if n}
        for language, text in by_language.items():
            assert {n for _, n, _, _ in string.Formatter().parse(text) if n} == en_fields, (
                key,
                language,
            )


def test_wording_is_marked_open() -> None:
    assert "OPEN, owner to confirm" in EXPLAIN_CONFIG.wording_basis
