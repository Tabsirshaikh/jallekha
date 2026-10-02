"""Build the E6 three-layer coverage GeoJSON package from reviewed E2/E4/E5 outputs."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.coverage import LAYER_IDS, build_coverage_layers  # noqa: E402

INPUTS = (
    "data/raw/geography/datameet/ghmc-wards.geojson",
    "data/derived/evidence/ward_evidence.csv",
    "data/derived/equity/summary.json",
    "data/derived/underserved/field_checks.json",
    "data/derived/equity/wards.csv",
)
OUTPUT_DIR = "data/derived/coverage"
MANIFEST = f"{OUTPUT_DIR}/layers.json"
CHECKS = "data/verification/coverage_checks.json"


def build(root: Path = ROOT) -> dict[str, bytes]:
    ward_geojson = json.loads((root / INPUTS[0]).read_text(encoding="utf-8-sig"))
    with (root / INPUTS[1]).open(encoding="utf-8-sig", newline="") as handle:
        evidence_rows = list(csv.DictReader(handle))
    equity_summary = json.loads((root / INPUTS[2]).read_text(encoding="utf-8"))
    underserved = json.loads((root / INPUTS[3]).read_text(encoding="utf-8"))
    with (root / INPUTS[4]).open(encoding="utf-8-sig", newline="") as handle:
        equity_wards = list(csv.DictReader(handle))
    layers, manifest = build_coverage_layers(
        ward_geojson,
        evidence_rows,
        underserved["rows"],
        equity_summary,
        equity_wards=equity_wards,
    )
    artifacts = {
        f"{OUTPUT_DIR}/{layer_id}.geojson": (
            json.dumps(layers[layer_id], indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode()
        for layer_id in LAYER_IDS
    }
    artifacts[MANIFEST] = (
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
    checks = {
        "schema_version": "E6-1",
        "inputs_sha256": {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in INPUTS
        },
        "outputs_sha256": {
            path: hashlib.sha256(content).hexdigest() for path, content in artifacts.items()
        },
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


def main() -> None:
    artifacts = build()
    for relative, content in artifacts.items():
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("P1:E6 built three evidence-status GeoJSON layers; unavailable values remain null")


if __name__ == "__main__":
    main()
