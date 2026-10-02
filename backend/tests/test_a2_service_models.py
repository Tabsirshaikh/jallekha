"""A2: service models and need weights per ward (F7), from E2 Census evidence + officer input."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config.allocation import ALLOCATION_CONFIG
from app.services import ledger, service_models

ROOT = Path(__file__).resolve().parents[2]
CFG = ALLOCATION_CONFIG


def ward(ward_id: str = "W1", **changes: str) -> dict[str, str]:
    row = {
        "ward_id": ward_id,
        "ward_name": f"Ward {ward_id}",
        "households": "10000",
        "wad": "0.10",
        "non_tap_share": "0.05",
        "cad": "0.08",
        "hardship": "0.12",
        "allocation_eligible": "True",
        "review_required": "False",
    }
    row.update(changes)
    return row


def only(rows: list[dict[str, str]], overrides=()) -> service_models.WardNeed:
    return service_models.build_ward_needs(rows, overrides)[0]


def test_piped_by_default_because_census_does_not_measure_supply_hours() -> None:
    need = only([ward()])
    assert need.service_class == "piped_regularity_unknown"
    assert need.service_route == "booked"
    assert need.class_basis == "CENSUS_2011_RULE"


def test_majority_without_tap_is_no_connection_and_gets_scheduled_supply() -> None:
    need = only([ward(non_tap_share=str(CFG.no_connection_non_tap_share))])
    assert need.service_class == "no_connection"
    assert need.service_route == "scheduled"


def test_need_weight_and_entitlement_formula() -> None:
    need = only([ward(wad="0.10", cad="0.08", hardship="0.12", households="10000")])
    expected = 1 + CFG.need_weight_wad * 0.10 + CFG.need_weight_cad * 0.08
    expected += CFG.need_weight_hardship * 0.12
    assert need.need_weight == pytest.approx(expected)
    assert need.entitlement == pytest.approx(10000 * expected)
    assert need.need_basis == "DERIVED"


def test_more_need_means_more_entitlement_for_equal_households() -> None:
    low, high = service_models.build_ward_needs([ward("A", wad="0.05"), ward("B", wad="0.25")], ())
    assert high.entitlement > low.entitlement


def test_ineligible_ward_gets_no_entitlement_and_an_officer_check() -> None:
    need = only([ward(allocation_eligible="False", wad="", households="")])
    assert need.entitlement is None and need.need_weight is None
    assert need.needs_officer_check
    assert "CENSUS_UNAVAILABLE" in need.check_reasons


def test_review_and_high_off_premises_wards_need_a_check() -> None:
    needs = service_models.build_ward_needs(
        [
            ward("R", review_required="True"),
            ward("H", wad=str(CFG.scheduled_candidate_wad)),
            ward("OK"),
        ],
        (),
    )
    by_id = {n.ward_id: n for n in needs}
    assert by_id["R"].check_reasons == ("E2_REVIEW_REQUIRED",)
    assert by_id["H"].scheduled_supply_candidate
    assert by_id["H"].check_reasons == ("SCHEDULED_SUPPLY_CANDIDATE",)
    assert not by_id["OK"].needs_officer_check and by_id["OK"].check_reasons == ()


def test_officer_override_changes_class_with_a_reason() -> None:
    override = service_models.Override(
        ward_id="W1",
        service_class="no_connection",
        reason="Field visit: 40 households in a basti have no tap",
        officer="officer-7",
    )
    need = only([ward()], [override])
    assert need.service_class == "no_connection"
    assert need.service_route == "scheduled"
    assert need.class_basis == "OFFICER"
    assert need.override_reason == override.reason


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"service_class": "piped_sometimes"}, "class"),
        ({"reason": "   "}, "reason"),
        ({"ward_id": "NOPE"}, "ward"),
    ],
)
def test_bad_override_is_rejected(changes: dict[str, str], message: str) -> None:
    base = {
        "ward_id": "W1",
        "service_class": "piped_intermittent",
        "reason": "Supply 2 hours on alternate days (AE report)",
        "officer": "officer-7",
    }
    base.update(changes)
    with pytest.raises(ValueError, match=message):
        service_models.build_ward_needs([ward()], [service_models.Override(**base)])


def test_two_overrides_for_one_ward_are_rejected() -> None:
    override = service_models.Override("W1", "piped_normal", "24x7 zone (AE report)", "o-1")
    with pytest.raises(ValueError, match="one override"):
        service_models.build_ward_needs([ward()], [override, override])


def test_override_becomes_a_ledger_entry() -> None:
    override = service_models.Override("W1", "piped_intermittent", "Alternate-day supply", "o-1")
    event = service_models.override_event(override, previous_class="piped_regularity_unknown")
    entry = ledger.next_entry(None, **event, created_at_iso="2026-10-02T06:00:00+00:00", key="k")
    assert entry.event_type == "override" and entry.entity_type == "ward"
    assert entry.payload["from"] == "piped_regularity_unknown"
    assert entry.payload["to"] == "piped_intermittent"
    assert ledger.verify_entries([entry], "k")["valid"]


def test_real_e2_evidence() -> None:
    needs = service_models.build_ward_needs(service_models.load_evidence(ROOT), ())
    assert len(needs) == 145
    with_entitlement = [n for n in needs if n.entitlement is not None]
    assert len(with_entitlement) == 143
    # Ward-level Census 2011 never shows a majority without tap water in GHMC (max ~29%):
    # "no connection" comes from officer input, not from the Census rule.
    assert all(n.service_class == "piped_regularity_unknown" for n in needs)
    assert sum(n.scheduled_supply_candidate for n in needs) >= 1
    assert all(n.need_weight >= 1 for n in with_entitlement)
