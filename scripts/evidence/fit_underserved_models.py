"""Fit the E5 count models (F4) out of fold: NB, BYM2 and BYM2_SHRINKAGE.

Usage:
    python scripts/evidence/fit_underserved_models.py [--variants NB BYM2 BYM2_SHRINKAGE]
    python scripts/evidence/fit_underserved_models.py --check

Runs services/underserved_models.fit_crossvalidated_count_model (PyMC, 5 folds, configured
chains, draws and diagnostics) on the same gated cohort that build_underserved.py screens. PyMC
needs a 64-bit C++ compiler for practical speed; the P1:E5 models workflow runs this on Linux
CI and uploads the result for commit. Sampling is seeded, but results can differ slightly by
platform and library version, so the environment is recorded and CI never re-samples: tests
check the committed results against the current cohort instead.

The BYM2 variants use data/derived/underserved/ward_adjacency.json restricted to the cohort,
and only after data/derived/underserved/ward_adjacency_review.json names a reviewer and
matches the graph file's SHA-256.

Output: data/derived/underserved/model_results.json (scores, fold diagnostics, the cohort
fingerprint, graph hash, config and environment). A model whose diagnostics fail in any fold
is kept with status DIAGNOSTICS_FAILED and no scores; the screen then cannot claim stability.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_underserved  # noqa: E402
from build_ward_adjacency import OUTPUT as ADJACENCY  # noqa: E402
from build_ward_adjacency import REVIEW  # noqa: E402

from app.config.underserved import UNDERSERVED_CONFIG  # noqa: E402

RESULTS = build_underserved.MODEL_RESULTS
VARIANTS = ("NB", "BYM2", "BYM2_SHRINKAGE")
FOLDS = 5


def graph_inputs(root: Path, ward_ids: list[str]) -> tuple[list[tuple[str, str]], dict]:
    """Cohort edges and the review record; refuses an unreviewed or changed graph."""
    graph_bytes = (root / ADJACENCY).read_bytes()
    review_path = root / REVIEW
    if not review_path.is_file():
        raise SystemExit(f"{REVIEW} is missing: the adjacency graph has not been reviewed")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if review.get("source_sha256") != hashlib.sha256(graph_bytes).hexdigest():
        raise SystemExit("The adjacency graph changed after its review; review it again")
    graph = json.loads(graph_bytes)
    keep = set(ward_ids)
    edges = [(e["a"], e["b"]) for e in graph["edges"] if e["a"] in keep and e["b"] in keep]
    return edges, review


def environment() -> dict[str, str]:
    versions = {
        name: importlib.metadata.version(name) for name in ("pymc", "pytensor", "arviz", "numpy")
    }
    return {"python": platform.python_version(), "platform": platform.platform(), **versions}


def fit(root: Path, variants: tuple[str, ...]) -> dict:
    from app.services.underserved_models import fit_crossvalidated_count_model

    cohort = build_underserved.screening_cohort(root)
    ids = [a.ward_id for a in cohort]
    edges, review = graph_inputs(root, ids) if set(variants) - {"NB"} else ([], None)
    results = {}
    for variant in variants:
        print(f"fitting {variant} on {len(cohort)} wards, {FOLDS} folds", flush=True)
        results[variant] = fit_crossvalidated_count_model(
            cohort,
            edges=edges if variant != "NB" else (),
            variant=variant,
            folds=FOLDS,
            graph_review=review if variant != "NB" else None,
        )
        print(f"  {variant}: {results[variant]['status']}", flush=True)
    return {
        "schema_version": "E5-MODELS-1",
        "label": "DERIVED (model reference; not a reporting probability or ground truth)",
        "cohort_fingerprint": build_underserved.cohort_fingerprint(cohort),
        "cohort_size": len(cohort),
        "adjacency_sha256": review["source_sha256"] if review else None,
        "cohort_edges": len(edges),
        "config": asdict(UNDERSERVED_CONFIG),
        "folds": FOLDS,
        "environment": environment(),
        "results": results,
    }


def check(root: Path) -> None:
    doc = json.loads((root / RESULTS).read_text(encoding="utf-8"))
    cohort = build_underserved.screening_cohort(root)
    if doc["cohort_fingerprint"] != build_underserved.cohort_fingerprint(cohort):
        raise SystemExit("Model results are stale: the screened cohort changed; refit")
    for variant, result in doc["results"].items():
        print(f"{variant}: {result['status']}")
    print(f"Model results match the current cohort ({doc['cohort_size']} wards)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=VARIANTS)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check(ROOT)
    else:
        document = fit(ROOT, tuple(args.variants))
        path = ROOT / RESULTS
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {RESULTS}")
