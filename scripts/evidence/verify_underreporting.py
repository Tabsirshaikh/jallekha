"""Verify saved experiment inputs, predictions, metrics and rejection; never refit models."""

import hashlib
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.config.underreporting import UNDERREPORTING_CONFIG  # noqa: E402
from app.services.section_checks import metrics  # noqa: E402
from app.services.underreporting import retention  # noqa: E402


def main():
    result = json.loads(
        (ROOT / "data/derived/underserved/underreporting_experiment.json").read_text()
    )
    assert result["config"] == json.loads(json.dumps(asdict(UNDERREPORTING_CONFIG)))
    assert result["train_year"] == 2024 and result["test_year"] == 2025
    assert result["reporting_probability"] is None and result["true_demand"] is None
    for path, digest in result["inputs_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    for run in result["runs"]:
        predictions = run["predictions"]
        assert len(predictions) == result["paired_sections"]
        assert len({p["section_id"] for p in predictions}) == len(predictions)
        computed = metrics([p["expected"] for p in predictions], [p["actual"] for p in predictions])
        for key, value in computed.items():
            if isinstance(value, float):
                assert math.isclose(run["metrics"][key], value, rel_tol=1e-12, abs_tol=1e-12), key
            else:
                assert run["metrics"][key] == value, key
        assert run["retention"] == retention(run["metrics"], result["baseline"], run["diagnostics"])
        assert run["retention_vs_persistence"] == retention(
            run["metrics"], result["persistence_baseline"], run["diagnostics"]
        )
        assert run["diagnostics"]["posterior_diagnostics"] is None
    retained = all(
        r["retention"] == r["retention_vs_persistence"] == "RETAIN_OBSERVED_BOOKING_PREDICTOR"
        for r in result["runs"]
    )
    assert (result["status"] == "RETAIN_OBSERVED_BOOKING_PREDICTOR") == retained
    print(f"Under-reporting saved results verified: {result['status']}; no model sampled")


if __name__ == "__main__":
    main()
