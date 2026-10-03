"""Build a compact impact snapshot from the committed A8 simulation results."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "derived" / "sandbox" / "results.csv"
OUTPUT = ROOT / "frontend" / "src" / "data" / "u9Impact.json"
METRICS = (
    "served_share",
    "need_weighted_unmet_share",
    "mean_wait_days",
    "gini_fill_rate",
    "jain_fill_rate",
    "worst_group_fill_rate",
    "km_per_kl",
)


def main() -> None:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    with SOURCE.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row.get("label") != "SIMULATION":
                raise ValueError("A8 rows must be labelled SIMULATION")
            grouped[(row["replay"], row["scenario"], row["policy"])].append(row)

    rows = []
    for (replay, scenario, policy), samples in sorted(grouped.items()):
        metrics = {}
        for name in METRICS:
            values = [float(sample[name]) for sample in samples if sample.get(name)]
            metrics[name] = {
                "mean": round(sum(values) / len(values), 6) if values else None,
                "min": round(min(values), 6) if values else None,
                "max": round(max(values), 6) if values else None,
                "basis": "SIMULATION",
            }
        rows.append(
            {
                "replay": replay,
                "scenario": scenario,
                "policy": policy,
                "seed_count": len(samples),
                "label": "SIMULATION",
                "metrics": metrics,
            }
        )

    payload = {
        "source": "data/derived/sandbox/results.csv",
        "source_label": "SIMULATION",
        "summary_source": "data/derived/sandbox/summary.json",
        "real_baselines": json.loads(
            (ROOT / "data" / "derived" / "sandbox" / "summary.json").read_text(encoding="utf-8")
        )["real_baselines"],
        "rows": rows,
        "unavailable": {
            "duplicate_merge_rate": "NOT_AVAILABLE",
            "reason": (
                "The replay has no complaints and the local duplicate calibration is unavailable."
            ),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
