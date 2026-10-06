"""Seeded 2024-to-2025 prior-sensitive section experiment; no BYM2 sampling.

Exposure: Census-2011 households apportioned by 2023 building mass, WAD/non-tap. Access:
CAD/hardship and distance to a 2024-only stand-in station fit. The committed sandbox station
file uses 2025 booking weights, so refit its stand-in method on 2024 to avoid test-year leakage.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
from app.config.section_checks import SECTION_CHECK_CONFIG  # noqa: E402
from app.config.underreporting import UNDERREPORTING_CONFIG as CONFIG  # noqa: E402
from app.services.geo import haversine_km  # noqa: E402
from app.services.section_checks import metrics  # noqa: E402
from app.services.underreporting import fit, retention  # noqa: E402
from scripts.evidence.build_section_checks import annual, read  # noqa: E402


def inputs():
    training, paths = annual(ROOT, SECTION_CHECK_CONFIG.train_year)
    testing, test_paths = annual(ROOT, SECTION_CHECK_CONFIG.period_year)
    evidence_path = ROOT / "data/derived/evidence/ward_evidence.csv"
    weights_path = ROOT / "data/derived/crosswalk/section_ward_building_weights.csv"
    points_path = ROOT / "data/derived/crosswalk/section_to_ward_2016.csv"
    evidence = {r["ward_id"]: r for r in read(evidence_path)}
    weights = read(weights_path)
    ward_mass = defaultdict(float)
    for r in weights:
        ward_mass[r["ward_id"]] += float(r["building_count_index"])
    section_covariates = defaultdict(lambda: np.zeros(5))
    for r in weights:
        w = evidence[r["ward_id"]]
        if any(not w[k] for k in ("households", "wad", "non_tap_share", "cad", "hardship")):
            continue
        exposure = (
            float(w["households"]) * float(r["building_count_index"]) / ward_mass[r["ward_id"]]
        )
        covariates = section_covariates[f"{r['division']}:{r['section']}"]
        covariates += exposure * np.array(
            [1, float(w["wad"]), float(w["non_tap_share"]), float(w["cad"]), float(w["hardship"])]
        )
    points = {
        f"{r['division']}:{r['section']}": (float(r["lat"]), float(r["lng"]))
        for r in read(points_path)
        if r["lat"] and r["lng"]
    }
    complete = [
        s for s in training if s.status() == "COMPLETE" and f"{s.division}:{s.section}" in points
    ]
    ids = [f"{s.division}:{s.section}" for s in complete]
    coordinates = np.array([points[s] for s in ids])
    clusters = (
        KMeans(
            n_clusters=min(CONFIG.stand_in_stations, len(coordinates)),
            random_state=CONFIG.seed,
            n_init=10,
        )
        .fit(coordinates, sample_weight=[s.bookings for s in complete])
        .cluster_centers_
    )
    samples = []
    actual = {f"{s.division}:{s.section}": s for s in testing if s.status() == "COMPLETE"}
    for s in complete:
        identity = f"{s.division}:{s.section}"
        cov = section_covariates.get(identity)
        if cov is None or cov[0] <= 0:
            continue
        h, wad, non_tap, cad, hardship = cov[0], *(cov[1:] / cov[0])
        need = h * max(CONFIG.minimum_need_share, wad + CONFIG.non_tap_weight * non_tap)
        distance = min(haversine_km(*points[identity], *station) for station in clusters)
        samples.append(
            {
                "id": identity,
                "exposure": need,
                "access": [cad, hardship, np.log1p(distance)],
                "observed": s.bookings,
                "connections": s.connections,
                "actual": actual[identity].bookings if identity in actual else None,
            }
        )
    return samples, paths + test_paths + [evidence_path, weights_path, points_path]


def main():
    samples, paths = inputs()
    paired = [i for i, s in enumerate(samples) if s["actual"] is not None]
    actual = [samples[i]["actual"] for i in paired]
    city_rate = sum(s["observed"] for s in samples) / sum(s["connections"] for s in samples)
    baseline = metrics([city_rate * samples[i]["connections"] for i in paired], actual)
    persistence = metrics([samples[i]["observed"] for i in paired], actual)
    shrunk = []
    for i in paired:
        target = samples[i]
        division = target["id"].split(":", 1)[0]
        peers = [
            s for s in samples if s["id"] != target["id"] and s["id"].split(":", 1)[0] == division
        ]
        division_rate = (
            sum(s["observed"] for s in peers) / sum(s["connections"] for s in peers)
            if peers
            else city_rate
        )
        weight = target["connections"] / (
            target["connections"] + CONFIG.division_shrinkage_connections
        )
        shrunk.append(
            weight * target["observed"] + (1 - weight) * division_rate * target["connections"]
        )
    shrinkage = metrics(shrunk, actual)
    runs = []
    for prior in CONFIG.reporting_prior_means:
        print(f"Fitting new non-spatial experiment: prior reporting mean {prior}", flush=True)
        prediction, diagnostics = fit(
            [s["exposure"] for s in samples],
            [s["access"] for s in samples],
            [s["observed"] for s in samples],
            prior,
        )
        score = metrics([prediction[i] for i in paired], actual)
        runs.append(
            {
                "prior_mean": prior,
                "prior_basis": "ASSUMED",
                "diagnostics": diagnostics,
                "metrics": score,
                "retention": retention(score, baseline, diagnostics),
                "retention_vs_persistence": retention(score, persistence, diagnostics),
                "predictions": [
                    {
                        "section_id": samples[i]["id"],
                        "expected": float(prediction[i]),
                        "actual": samples[i]["actual"],
                        "basis": "DERIVED",
                    }
                    for i in paired
                ],
            }
        )
    result = {
        "basis": "DERIVED",
        "config": asdict(CONFIG),
        "train_year": 2024,
        "test_year": 2025,
        "training_sections": len(samples),
        "paired_sections": len(paired),
        "baseline": baseline,
        "persistence_baseline": persistence,
        "division_shrinkage_baseline": shrinkage,
        "runs": runs,
        "reporting_probability": None,
        "true_demand": None,
        "latent_basis": "UNAVAILABLE",
        "latent_reason": (
            "No identified reporting prior or field ground truth; "
            "decomposition is assumption-dependent."
        ),
        "status": "RETAIN_OBSERVED_BOOKING_PREDICTOR"
        if all(
            r["retention"] == "RETAIN_OBSERVED_BOOKING_PREDICTOR"
            and r["retention_vs_persistence"] == "RETAIN_OBSERVED_BOOKING_PREDICTOR"
            for r in runs
        )
        else "REJECT_RESEARCH_CANDIDATE",
        "station_method": (
            "ASSUMED stand-ins refitted by 2024-only booking-weighted k-means; "
            "existing 2025 stations not used for fitting"
        ),
        "exposure_method": (
            "Census-2011 households apportioned by 2023 building-count mass; "
            "approximate need/context"
        ),
        "inputs_sha256": {
            str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
        },
    }
    (ROOT / "data/derived/underserved/underreporting_experiment.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("runs", "inputs_sha256", "config")}
        )
    )
    for r in runs:
        print(json.dumps({k: v for k, v in r.items() if k != "predictions"}))


if __name__ == "__main__":
    main()
