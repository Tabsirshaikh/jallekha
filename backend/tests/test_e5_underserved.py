import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from app.config.underserved import UnderservedConfig
from app.services import underserved_models
from app.services.underserved import (
    AreaEvidence,
    blockers,
    peer_median,
    screen,
)
from app.services.underserved_models import fit_count_model, scaled_icar_basis

ROOT = Path(__file__).resolve().parents[2]
TEST_CONFIG = UnderservedConfig(minimum_areas=8, peer_count=3)
spec = importlib.util.spec_from_file_location(
    "underserved_builder", ROOT / "scripts/evidence/build_underserved.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def cohort(count=12, basis="SIMULATED", config=None):
    config = config or TEST_CONFIG
    result = []
    for index in range(count):
        result.append(
            AreaEvidence(
                ward_id=f"W{index:02}",
                ward_name=f"Zone {index}",
                households=800 + index * 83,
                wad=0.95 if index == 0 else index / count,
                non_tap_share=((index * 7) % count) / count,
                cad=0.9 if index == 0 else index / count,
                hardship=0.85 if index == 0 else (count - index) / (count * 2),
                bookings=(5 if index == 0 else 16 + (index * 11) % 25),
                period_year=2023,
                period_months=12,
                household_reference_year=2022,
                need_reference_year=2022,
                census_location_validated=True,
                booking_transfer_validated=True,
                booking_period_complete=True,
                basis=basis,
                growth_ratio=1.3,
                growth_quality="REVIEW_HIGH_VARIABILITY",
            )
        )
    return result


def test_real_inputs_fail_closed_and_have_no_unsupported_flags():
    output = builder.build()
    result = json.loads(output[builder.ROWS])
    summary = json.loads(output[builder.SUMMARY])
    assert len(result["rows"]) == 145
    assert len(result["data_review_queue"]) == 145
    assert result["field_check_list"] == []
    assert summary["eligible_count"] == 0
    assert summary["field_check_count"] == 0
    assert summary["reporting_probability"] is None
    assert all(row["status"] == "DATA_REVIEW_REQUIRED" for row in result["rows"])
    assert all(row["field_check_candidate"] is None for row in result["rows"])
    assert all(row["growth_ratio_basis"] == "DERIVED" for row in result["rows"])
    assert all(row["growth_quality"] == "REVIEW_HIGH_VARIABILITY" for row in result["rows"])


def test_actual_source_rows_expose_the_specific_review_blockers():
    areas = builder.load_areas()
    assert len(areas) == 145
    codes = set(blockers(areas[0]))
    assert "UNVALIDATED_CENSUS_LOCATION" in codes
    assert "UNVALIDATED_BOOKING_TRANSFER" in codes
    assert "INCOMPLETE_BOOKING_PERIOD" in codes
    assert "WARD_BOOKINGS_UNAVAILABLE" in codes


def test_peer_median_is_leave_one_out_and_only_uses_need_side_matching():
    areas = cohort()
    values = peer_median(areas, TEST_CONFIG)
    assert set(values) == {area.ward_id for area in areas}
    assert all(area.ward_id not in values[area.ward_id]["peers"] for area in areas)
    assert all(len(value["peers"]) == 3 for value in values.values())
    assert values["W00"]["expected"] > 0
    assert values["W00"]["interval_kind"] == "UNAVAILABLE_PEER_MEDIAN_HAS_NO_POSTERIOR"


def test_incompatible_evidence_cohorts_and_bad_configuration_are_rejected():
    areas = cohort()
    with pytest.raises(ValueError, match="Do not mix"):
        peer_median([areas[0], replace(areas[1], period_year=2022), *areas[2:]])
    with pytest.raises(ValueError, match="quantiles"):
        screen(areas, config=UnderservedConfig(ratio_quantile=1.5))


def test_agreement_explanation_is_a_field_check_not_an_entitlement():
    areas = cohort()
    names = ("NB", "BYM2", "BYM2_SHRINKAGE")
    model_results = {}
    for name in names:
        scores = {}
        for area in areas:
            ratio = 0.1 if area.ward_id == "W00" else 0.9
            scores[area.ward_id] = {
                "expected": area.bookings / ratio,
                "ratio": ratio,
                "ratio_lower": ratio - 0.02,
                "ratio_upper": ratio + 0.02,
                "interval_kind": "TEST_ONLY",
            }
        model_results[name] = {
            "status": "COMPLETE",
            "prediction_scope": "OUT_OF_FOLD",
            "scores": scores,
        }
    result = screen(areas, model_results=model_results, config=TEST_CONFIG)
    first = next(row for row in result["rows"] if row["ward_id"] == "W00")
    assert first["status"] == "STABLE_FIELD_CHECK_CANDIDATE"
    assert first["field_check_candidate"] is True
    assert set(first["flagged_variants"]) == {"PEER_MEDIAN", *names}
    assert first["action"] == "Send someone to check; no allocation or entitlement change"
    assert first["growth_ratio_context_only"] == 1.3
    assert result["summary"]["real_world_accuracy"] is None
    assert result["summary"]["ground_truth_count"] == 0
    assert any(reason["code"] == "LOW_OBSERVED_REFERENCE_RATIO" for reason in first["reasons"])


def test_icar_basis_handles_components_and_rejects_bad_graphs():
    wards = ["A", "B", "C", "D"]
    basis = scaled_icar_basis(wards, [("A", "B"), ("B", "C")])
    assert basis.shape == (4, 3)
    assert np.all(np.isfinite(basis))
    assert np.linalg.matrix_rank(basis) == 3
    assert np.allclose(basis[:3].sum(axis=0), 0)
    with pytest.raises(ValueError, match="Duplicate edge"):
        scaled_icar_basis(wards, [("A", "B"), ("B", "A")])


@pytest.mark.parametrize("variant,edges", [("NB", ()), ("BYM2", (("W00", "W01"),))])
def test_bayesian_models_smoke_on_synthetic_data(variant, edges):
    config = UnderservedConfig(
        minimum_areas=8,
        peer_count=3,
        chains=2,
        draws=60,
        tune=60,
        max_rhat=20,
        minimum_bulk_ess=1,
        seed=412,
    )
    areas = cohort(config=config)
    import pytensor

    if __import__("os").name == "nt":
        pytensor.config.cxx = ""
    if variant == "BYM2":
        edges = tuple((f"W{i:02}", f"W{i + 1:02}") for i in range(len(areas) - 1))
    graph_review = None
    if variant == "BYM2":
        graph_review = {
            "status": "REVIEWED",
            "geography_version": config.geography_version,
            "reviewer": "synthetic-test-only",
            "source_sha256": "a" * 64,
        }
    result = fit_count_model(
        areas,
        edges=edges,
        variant=variant,
        config=config,
        holdout_ids=("W00",),
        graph_review=graph_review,
    )
    assert result["status"] in {"COMPLETE", "DIAGNOSTICS_FAILED"}
    assert result["holdout_ids"] == ["W00"]
    assert set(result["scores"]) == {"W00"}
    assert result["prediction_scope"] == "HELDOUT_ONLY"
    for score in result["scores"].values():
        assert 0 <= score["ratio_lower"] <= score["ratio"] <= score["ratio_upper"]
        assert score["interval_kind"] == "POSTERIOR_REFERENCE_MEAN_RATIO_NOT_REPORTING_PROBABILITY"


def test_generated_results_are_reproducible_and_checksums_match():
    outputs = builder.build()
    assert outputs == builder.build()
    for path, expected in outputs.items():
        if path != builder.CHECKS:
            assert (ROOT / path).read_bytes() == expected
    checks = json.loads((ROOT / builder.CHECKS).read_text(encoding="utf-8"))
    assert checks["outputs_sha256"] == {
        path: __import__("hashlib").sha256(value).hexdigest()
        for path, value in outputs.items()
        if path in (builder.ROWS, builder.SUMMARY)
    }


def test_cross_validation_merges_only_disjoint_out_of_fold_predictions(monkeypatch):
    areas = cohort()
    calls = []

    def fake_fit(areas, edges=(), variant="NB", config=None, holdout_ids=(), graph_review=None):
        calls.append(tuple(holdout_ids))
        return {
            "status": "COMPLETE",
            "variant": variant,
            "prediction_scope": "HELDOUT_ONLY",
            "scores": {
                ward: {"ratio": 0.8, "ratio_lower": 0.7, "ratio_upper": 0.9} for ward in holdout_ids
            },
        }

    monkeypatch.setattr(underserved_models, "fit_count_model", fake_fit)
    result = underserved_models.fit_crossvalidated_count_model(
        areas, variant="NB", config=TEST_CONFIG, folds=4
    )
    assert result["status"] == "COMPLETE"
    assert result["prediction_scope"] == "OUT_OF_FOLD"
    assert set(result["scores"]) == {area.ward_id for area in areas}
    assert len(calls) == 4
    assert len({ward for fold in calls for ward in fold}) == len(areas)


def test_in_sample_or_failed_model_results_never_drive_flags():
    areas = cohort()
    ids = {area.ward_id for area in areas}
    scores = {ward: {"ratio": 0.1, "ratio_upper": 0.2, "expected": 100} for ward in ids}
    result = screen(
        areas,
        model_results={
            "NB": {"status": "COMPLETE", "prediction_scope": "HELDOUT_ONLY", "scores": scores},
            "BYM2": {
                "status": "DIAGNOSTICS_FAILED",
                "prediction_scope": "OUT_OF_FOLD",
                "scores": scores,
            },
        },
        config=TEST_CONFIG,
    )
    assert "NB" not in result["thresholds"]
    assert "BYM2" not in result["thresholds"]
    assert result["summary"]["stability_evaluated"] is False


def test_model_fits_require_holdouts_and_reviewed_spatial_graphs():
    areas = cohort()
    with pytest.raises(ValueError, match="Held-out areas are required"):
        fit_count_model(areas, variant="NB", config=TEST_CONFIG)
    with pytest.raises(ValueError, match="review metadata"):
        fit_count_model(
            areas,
            edges=tuple((f"W{i:02}", f"W{i + 1:02}") for i in range(len(areas) - 1)),
            variant="BYM2",
            config=TEST_CONFIG,
            holdout_ids=("W00",),
        )
