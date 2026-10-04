"""E5 model-variant stability (F4): reviewed ward graph, committed out-of-fold NB / BYM2 /
BYM2_SHRINKAGE results, and the screen that requires all four methods to agree.

The models are fitted on Linux CI (P1:E5-MODELS) and committed; these tests never re-sample.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {"PEER_MEDIAN", "NB", "BYM2", "BYM2_SHRINKAGE"}


def _load(name: str):
    path = ROOT / f"scripts/evidence/{name}.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


adjacency = _load("build_ward_adjacency")
builder = _load("build_underserved")
fitter = _load("fit_underserved_models")


@pytest.fixture(scope="module")
def graph() -> dict:
    return json.loads((ROOT / adjacency.OUTPUT).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def models() -> dict:
    return json.loads((ROOT / builder.MODEL_RESULTS).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def screen_output() -> tuple[dict, dict]:
    out = builder.build()
    return json.loads(out[builder.ROWS]), json.loads(out[builder.SUMMARY])


def test_graph_is_reproducible_and_well_formed(graph) -> None:
    assert adjacency.build() == graph
    pairs = [(e["a"], e["b"]) for e in graph["edges"]]
    assert len(pairs) == len({tuple(sorted(p)) for p in pairs}) == graph["edge_count"]
    assert all(a != b and a in graph["ward_names"] and b in graph["ward_names"] for a, b in pairs)
    assert all(e["shared_border_m"] >= adjacency.MIN_SHARED_M for e in graph["edges"])
    assert len(graph["components"]) == 1 and graph["wards_without_neighbours"] == []
    barkas = "relation/7867584"
    neighbours = {b if a == barkas else a for a, b in pairs if barkas in (a, b)}
    assert {graph["ward_names"][w] for w in neighbours} == {
        "Ward 41 Kanchanbagh",
        "Ward 43 Chandrayangutta",
    }


def test_graph_review_names_a_reviewer_and_matches_the_graph_file() -> None:
    review = json.loads((ROOT / adjacency.REVIEW).read_text(encoding="utf-8"))
    assert review["status"] == "REVIEWED" and review["reviewer"].strip()
    assert review["geography_version"] == "GHMC_2016_150"
    digest = hashlib.sha256((ROOT / adjacency.OUTPUT).read_bytes()).hexdigest()
    assert review["source_sha256"] == digest
    assert "Not a local-knowledge review" in review["method"]


def test_fitting_refuses_a_changed_or_unreviewed_graph(tmp_path) -> None:
    for relative in (adjacency.OUTPUT, adjacency.REVIEW):
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / relative, tmp_path / relative)
    ids = sorted(json.loads((tmp_path / adjacency.OUTPUT).read_text())["ward_names"])
    edges, review = fitter.graph_inputs(tmp_path, ids)
    assert len(edges) == 364 and review["status"] == "REVIEWED"
    (tmp_path / adjacency.OUTPUT).write_bytes((tmp_path / adjacency.OUTPUT).read_bytes() + b" ")
    with pytest.raises(SystemExit, match="changed after its review"):
        fitter.graph_inputs(tmp_path, ids)
    (tmp_path / adjacency.REVIEW).unlink()
    with pytest.raises(SystemExit, match="not been reviewed"):
        fitter.graph_inputs(tmp_path, ids)


def test_model_results_are_for_the_current_cohort(models) -> None:
    cohort = builder.screening_cohort()
    assert models["cohort_fingerprint"] == builder.cohort_fingerprint(cohort)
    assert models["cohort_size"] == len(cohort)
    assert set(models["results"]) == {"NB", "BYM2", "BYM2_SHRINKAGE"}
    review = json.loads((ROOT / adjacency.REVIEW).read_text(encoding="utf-8"))
    assert models["adjacency_sha256"] == review["source_sha256"]
    for variant, result in models["results"].items():
        assert result["prediction_scope"] == "OUT_OF_FOLD", variant
        assert len(result["fold_diagnostics"]) == models["folds"] == 5, variant
        if result["status"] == "COMPLETE":
            assert set(result["scores"]) == {a.ward_id for a in cohort}, variant
            for fold in result["fold_diagnostics"]:
                assert fold["divergences"] == 0 and fold["max_rhat"] <= 1.01, variant
        else:
            assert result["scores"] == {}, variant


def test_stale_model_results_are_refused(monkeypatch) -> None:
    monkeypatch.setattr(builder, "cohort_fingerprint", lambda cohort: "0" * 64)
    with pytest.raises(ValueError, match="stale"):
        builder.build()


def test_candidates_need_all_four_methods_when_models_complete(models, screen_output) -> None:
    result, summary = screen_output
    complete = all(r["status"] == "COMPLETE" for r in models["results"].values())
    assert summary["models"]["status"] == "MODEL_RESULTS_LOADED"
    assert summary["stability_evaluated"] is complete
    for row in result["rows"]:
        if row["field_check_candidate"]:
            if complete:
                assert set(row["flagged_variants"]) == REQUIRED
                assert row["status"] == "STABLE_FIELD_CHECK_CANDIDATE"
            elif models["results"]["NB"]["status"] == "COMPLETE":
                # Failed spatial models: peer and NB must still agree
                assert {"PEER_MEDIAN", "NB"} <= set(row["flagged_variants"])
                assert row["status"] == "AGREED_FIELD_CHECK_CANDIDATE"
            else:
                assert row["status"] == "PEER_ONLY_FIELD_CHECK"
    if complete:
        assert set(result["pairwise_flag_jaccard"]) == {
            f"{a}:{b}" for a in sorted(REQUIRED) for b in sorted(REQUIRED) if a < b
        }
