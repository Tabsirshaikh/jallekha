import csv
import hashlib
from pathlib import Path


def test_accepted_reservoir_source_bytes_match_separate_manifest():
    root = Path(__file__).resolve().parents[2]
    rows = list(
        csv.DictReader((root / "data/verification/reservoir_manifest.csv").open(encoding="utf-8"))
    )
    assert rows
    for row in rows:
        file = root / row["file_path"]
        assert row["basis"] == "REAL"
        assert row["source_url"].startswith("https://data.telangana.gov.in/")
        assert hashlib.sha256(file.read_bytes()).hexdigest() == row["sha256"]
        assert file.stat().st_size == int(row["bytes"])
