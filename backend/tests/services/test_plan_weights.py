"""Priority weights for plans (F7 need weights) and ward names on plans.

An officer can try other need weights (water access, phone access, hardship) before approving.
A weighted plan is a separate plan: its own replay run (weights change who is served, so what
carries over to the next day), its own id, its own digest, rebuilt from its recipe like any other.
Replay data is SIMULATION. The debt weight is not offered: the replay has no debts.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from app.config.allocation import ALLOCATION_CONFIG
from app.services import plan_builder, service_models
from app.services.service_models import NeedWeights

DAY = date(2025, 5, 1)
BARKAS = "ward:relation/7867584"  # highest water-access deficit of the 145 wards


def test_default_need_weight_is_unchanged_without_weights() -> None:
    cfg = ALLOCATION_CONFIG
    expected = (
        1 + cfg.need_weight_wad * 0.2 + cfg.need_weight_cad * 0.1 + cfg.need_weight_hardship * 0.3
    )
    assert service_models.need_weight(0.2, 0.1, 0.3) == pytest.approx(expected)
    assert service_models.need_weight(0.2, 0.1, 0.3, None) == pytest.approx(expected)
    assert NeedWeights.default() == NeedWeights(
        cfg.need_weight_wad, cfg.need_weight_cad, cfg.need_weight_hardship
    )


def test_need_weight_uses_the_weights_it_is_given() -> None:
    weights = NeedWeights(wad=4.0, cad=0.0, hardship=1.0)
    assert service_models.need_weight(0.2, 0.1, 0.3, weights) == pytest.approx(1 + 0.8 + 0 + 0.3)


@pytest.mark.parametrize(
    "bad",
    [
        NeedWeights(-0.1, 1, 1),
        NeedWeights(1, 5.5, 1),
        NeedWeights(1, 1, math.nan),
        NeedWeights(math.inf, 1, 1),
    ],
)
def test_weights_must_be_between_zero_and_five(bad: NeedWeights) -> None:
    with pytest.raises(ValueError, match="between 0 and"):
        bad.validated()


def test_weights_equal_to_the_defaults_make_the_default_plan() -> None:
    default = plan_builder.build_replay_plan(DAY)
    same = plan_builder.build_replay_plan(DAY, weights=NeedWeights.default())
    assert same.plan.plan_id == default.plan.plan_id == f"replay-{DAY.isoformat()}"
    assert same.plan.digest == default.plan.digest
    assert "weights" not in same.recipe


def test_a_weighted_plan_has_its_own_id_recipe_and_entitlement() -> None:
    default = plan_builder.build_replay_plan(DAY)
    weights = NeedWeights(wad=5.0, cad=0.0, hardship=0.0)
    weighted = plan_builder.build_replay_plan(DAY, weights=weights)
    assert weighted.plan.plan_id == f"replay-{DAY.isoformat()}-w5-0-0"
    assert weighted.recipe["weights"] == {"wad": 5.0, "cad": 0.0, "hardship": 0.0}
    assert weighted.plan.digest != default.plan.digest
    # the water-access weight went up, so the ward with the worst access gains the most
    # relative to the ward with the best access
    ratio = {
        g: weighted.inputs.entitlement[g] / default.inputs.entitlement[g]
        for g in default.inputs.entitlement
        if g.startswith("ward:")
    }
    assert ratio[BARKAS] > min(ratio.values())
    assert ratio[BARKAS] == pytest.approx(max(ratio.values()), rel=0.2)
    assert "weights" in weighted.basis["effective_entitlement"].lower() or (
        "ASSUMED" in weighted.basis["weights"]
    )


def test_a_weighted_plan_rebuilds_to_the_same_digest() -> None:
    weighted = plan_builder.build_replay_plan(DAY, weights=NeedWeights(3.0, 2.0, 0.5))
    again = plan_builder.rebuild(weighted.recipe)
    assert again.plan.digest == weighted.plan.digest
    assert again.plan.plan_id == weighted.plan.plan_id


def test_the_default_and_a_weighted_plan_do_not_disturb_each_other() -> None:
    first = plan_builder.build_replay_plan(DAY)
    plan_builder.build_replay_plan(DAY, weights=NeedWeights(5.0, 0.0, 0.0))
    second = plan_builder.build_replay_plan(DAY)
    assert second.plan.digest == first.plan.digest


def test_compare_lists_who_gains_and_who_loses_with_names() -> None:
    weighted = plan_builder.build_replay_plan(DAY, weights=NeedWeights(5.0, 0.0, 0.0))
    result = plan_builder.compare_to_default(weighted)
    assert result["against"] == f"replay-{DAY.isoformat()}"
    assert result["weights"] == {"wad": 5.0, "cad": 0.0, "hardship": 0.0}
    assert result["default_weights"] == NeedWeights.default().as_dict()
    gainers, losers = result["gainers"], result["losers"]
    assert gainers and losers  # the weights do move trips (a few, capacity is the limit)
    for row in gainers + losers:
        assert set(row) == {"group", "name", "served_default", "served_weighted", "change"}
        assert row["change"] == row["served_weighted"] - row["served_default"]
    assert [r["change"] for r in gainers] == sorted((r["change"] for r in gainers), reverse=True)
    assert all(r["change"] > 0 for r in gainers) and all(r["change"] < 0 for r in losers)
    # same trips, redistributed: what one group gains another loses
    assert sum(r["change"] for r in result["all_changes"]) == 0


def test_comparing_a_default_plan_is_refused() -> None:
    default = plan_builder.build_replay_plan(DAY)
    with pytest.raises(ValueError, match="default weights"):
        plan_builder.compare_to_default(default)


def test_group_names_come_from_the_evidence_file() -> None:
    names = plan_builder.group_names([BARKAS, "section:ATTAPUR", "ward:relation/does-not-exist"])
    assert names[BARKAS] == "Ward 42 Barkas"
    assert names["section:ATTAPUR"] == "ATTAPUR"
    assert names["ward:relation/does-not-exist"] is None  # unknown stays unknown, never invented
