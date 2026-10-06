"""Re-run the E5 ward accuracy diagnostic before/after the approximate transfer.

NB predictions stay the archived point-input fit (no spatial sampling on Windows). New peer
predictions are recomputed from the same five need-neighbours. This is an in-sample sensitivity
audit of approximate counts, not proof of geographic accuracy or an out-of-sample validation.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median, pstdev

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.config.underserved import UNDERSERVED_CONFIG  # noqa: E402
from app.services.booking_transfer import split  # noqa: E402
from app.services.section_checks import metrics  # noqa: E402


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build():
    old = json.loads((ROOT / "data/derived/underserved/field_checks.json").read_text())
    rows = [r for r in old["rows"] if r.get("model_scores", {}).get("NB")]
    weights = defaultdict(dict)
    for r in read(ROOT / "data/derived/crosswalk/section_ward_building_weights.csv"):
        weights[(r["division"], r["section"])][r["ward_id"]] = float(r["weight"])
    bookings = defaultdict(int)
    for path in sorted((ROOT / "data/raw/hmwssb_tankers_portal").glob("2025-*.csv")):
        for r in read(path):
            bookings[(r["division"], r["section"])] += int(r["noofbookings"])
    new, unplaced = split(bookings, weights)
    population = {
        r["ward_id"]: float(r["households_2025_central"])
        for r in read(ROOT / "data/derived/population/ward_population_2025.csv")
        if r["households_2025_central"]
    }
    need = {r["ward_id"]: r for r in read(ROOT / "data/derived/evidence/ward_evidence.csv")}
    paired = [r for r in rows if r["ward_id"] in new]
    output = {}
    for label, observations in (
        ("point", {r["ward_id"]: r["observed_bookings"] for r in rows}),
        ("building", new),
    ):
        ids = [r["ward_id"] for r in paired]
        vectors = {
            w: (math.log(population[w]), float(need[w]["wad"]), float(need[w]["non_tap_share"]))
            for w in ids
        }
        scales = [pstdev(v[k] for v in vectors.values()) or 1 for k in range(3)]
        peers = []
        for w in ids:
            neighbours = sorted(
                (p for p in ids if p != w),
                key=lambda p: (
                    sum(((vectors[w][k] - vectors[p][k]) / scales[k]) ** 2 for k in range(3)),
                    p,
                ),
            )[: UNDERSERVED_CONFIG.peer_count]
            peers.append(
                median(observations[p] / population[p] for p in neighbours) * population[w]
            )
        observed = [observations[w] for w in ids]
        city_rate = sum(observed) / sum(population[w] for w in ids)
        output[label] = {
            "NB_archived_predictions": metrics(
                [r["model_scores"]["NB"]["expected"] for r in paired], observed
            ),
            "peer_recomputed": metrics(peers, observed),
            "household_city_rate": metrics([population[w] * city_rate for w in ids], observed),
        }
    return {
        "basis": "DERIVED_APPROXIMATE",
        "period_year": 2025,
        "paired_wards": len(paired),
        "placed_bookings": sum(new.values()),
        "unplaced_bookings": sum(unplaced.values()),
        "city_bookings": sum(bookings.values()),
        "results": output,
        "interpretation": (
            "In-sample sensitivity diagnostic; no authoritative ward observations. "
            "NB is the archived point-input fit, not refitted on new counts. "
            "Improved agreement cannot validate the geography."
        ),
    }


if __name__ == "__main__":
    result = build()
    (ROOT / "data/derived/underserved/booking_transfer_audit.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))
