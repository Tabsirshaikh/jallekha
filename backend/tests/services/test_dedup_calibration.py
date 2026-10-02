"""T1 calibration script. All rows below are small test fixtures, not Chicago data."""

import csv
import hashlib
import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "calibrate_dedup", ROOT / "scripts/trust/calibrate_dedup.py"
)
calibrate_dedup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = calibrate_dedup  # dataclasses need the module registered
SPEC.loader.exec_module(calibrate_dedup)

HEADER = [
    "SR_NUMBER",
    "SR_TYPE",
    "CREATED_DATE",
    "LATITUDE",
    "LONGITUDE",
    "DUPLICATE",
    "PARENT_SR_NUMBER",
]
# Fixture: origin and points ~50 m / ~500 m north (1e-5 degree latitude is about 1.11 m).
FIXTURE = [
    ["SR1", "No Water", "04/01/2023 09:00:00 AM", "41.8800", "-87.6300", "false", ""],
    ["SR2", "No Water", "04/01/2023 11:00:00 AM", "41.88045", "-87.6300", "true", "SR1"],
    ["SR3", "No Water", "04/03/2023 12:00:00 PM", "41.8800", "-87.6300", "true", "SR1"],
    ["SR4", "Leak", "04/01/2023 09:00:00 AM", "41.9000", "-87.6300", "false", ""],
    ["SR5", "Leak", "04/02/2023 09:00:00 AM", "41.9045", "-87.6300", "true", "SR4"],
    ["SR6", "Leak", "04/02/2023 10:00:00 AM", "", "", "false", ""],
]


def write_fixture(path: Path) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(FIXTURE)
    return path


def write_manifest(path: Path, root: Path, data: Path, sha256: str) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["dataset_id", "file_path", "retrieved_at_utc", "sha256"])
        writer.writerow(
            [
                "D13-CHICAGO-311-TEST",
                data.relative_to(root).as_posix(),
                "2026-10-02T00:00:00+00:00",
                sha256,
            ]
        )
    return path


def test_refuses_unregistered_input_and_writes_nothing(tmp_path: Path) -> None:
    data = write_fixture(tmp_path / "chicago.csv")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("dataset_id,file_path,retrieved_at_utc,sha256\n", encoding="utf-8")
    output = tmp_path / "out.csv"
    code = calibrate_dedup.main(
        [
            "--input",
            str(data),
            "--manifest",
            str(manifest),
            "--root",
            str(tmp_path),
            "--output",
            str(output),
        ]
    )
    assert code == 2
    assert not output.exists()


def test_refuses_checksum_mismatch(tmp_path: Path) -> None:
    data = write_fixture(tmp_path / "chicago.csv")
    manifest = write_manifest(tmp_path / "manifest.csv", tmp_path, data, "0" * 64)
    with pytest.raises(calibrate_dedup.CalibrationBlocked, match="Checksum"):
        calibrate_dedup.registered_entry(data, manifest, tmp_path)


def test_refuses_missing_input(tmp_path: Path) -> None:
    with pytest.raises(calibrate_dedup.CalibrationBlocked, match="not found"):
        calibrate_dedup.registered_entry(tmp_path / "absent.csv", tmp_path / "m.csv", tmp_path)


def test_parse_time_formats() -> None:
    assert calibrate_dedup.parse_time("04/01/2023 01:30:00 PM").hour == 13
    assert calibrate_dedup.parse_time("2023-04-01T13:30:00.000").minute == 30
    with pytest.raises(ValueError):
        calibrate_dedup.parse_time("yesterday")


def test_quantile_linear_interpolation() -> None:
    assert calibrate_dedup.quantile([0, 10], 0.5) == 5
    assert calibrate_dedup.quantile([1, 2, 3, 4, 5], 0.9) == pytest.approx(4.6)
    assert math.isnan(calibrate_dedup.quantile([], 0.5))


def test_registered_run_writes_derived_output(tmp_path: Path) -> None:
    data = write_fixture(tmp_path / "chicago.csv")
    digest = hashlib.sha256(data.read_bytes()).hexdigest()
    manifest = write_manifest(tmp_path / "manifest.csv", tmp_path, data, digest)
    output = tmp_path / "out.csv"
    code = calibrate_dedup.main(
        [
            "--input",
            str(data),
            "--manifest",
            str(manifest),
            "--root",
            str(tmp_path),
            "--output",
            str(output),
        ]
    )
    assert code == 0
    with output.open(encoding="utf-8", newline="") as handle:
        rows = {(row["metric"], row["group"]): row for row in csv.DictReader(handle)}
    assert all(row["basis"] == "DERIVED" for row in rows.values())
    assert digest in rows[("rows_total", "all")]["basis_detail"]
    assert rows[("rows_total", "all")]["value"] == "6"
    assert rows[("rows_without_coordinates", "all")]["value"] == "1"

    # Fixture duplicates: SR2 (50 m, 2 h after SR1), SR3 (0 m, 51 h after SR1 and 49 h after
    # SR2, so outside 48 h of both), SR5 (500 m, 24 h).
    assert float(rows[("child_parent_hours_p90", "No Water")]["value"]) == pytest.approx(46.1)
    # 100 m / 48 h links only SR2; 300 m / 168 h links SR2 and SR3; SR5 (500 m) never.
    assert float(rows[("linked_share", "radius=100m;window=48h")]["value"]) == pytest.approx(1 / 3)
    assert float(rows[("linked_share", "radius=300m;window=168h")]["value"]) == pytest.approx(2 / 3)
    assert rows[("linked_share", "radius=100m;window=48h")]["reference"] == "0.71"
