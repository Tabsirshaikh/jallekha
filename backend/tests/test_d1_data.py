from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "data" / "verification" / "d1_manifest.csv"


def test_d1_manifest_exists() -> None:
    assert MANIFEST_PATH.is_file(), f"Missing {MANIFEST_PATH}"


def test_d1_manifest_entries_and_hashes() -> None:
    with MANIFEST_PATH.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) >= 3
    dataset_ids = {r["dataset_id"] for r in rows}
    assert "D5a-OSM-Hyderabad-District" in dataset_ids
    assert "D5b-OSM-Hyderabad-Mandals" in dataset_ids
    assert "D10-OSM-HMWSSB-Points" in dataset_ids

    for r in rows:
        assert r["basis"] == "REAL"
        assert r["license"].startswith("ODbL")
        fpath = ROOT / r["file_path"]
        assert fpath.is_file(), f"File missing: {fpath}"
        payload = fpath.read_bytes()
        assert len(payload) == int(r["bytes"])
        assert hashlib.sha256(payload).hexdigest() == r["sha256"]


def test_d1_geojson_layers() -> None:
    with MANIFEST_PATH.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    for r in rows:
        fpath = ROOT / r["file_path"]
        if fpath.suffix == ".geojson":
            data = json.loads(fpath.read_bytes().decode("utf-8"))
            assert data.get("type") == "FeatureCollection"
            features = data.get("features", [])
            assert isinstance(features, list)
            assert len(features) > 0, f"Expected non-empty features in {r['file_path']}"
            for feat in features:
                assert feat.get("type") == "Feature"
                assert "geometry" in feat
                assert "properties" in feat


def test_d1_retrieval_logs() -> None:
    d6_log = ROOT / "data" / "raw" / "d6_open_buildings" / "RETRIEVAL_LOG.md"
    d7_log = ROOT / "data" / "raw" / "d7_groundwater" / "RETRIEVAL_LOG.md"
    assert d6_log.is_file(), f"Missing {d6_log}"
    assert d7_log.is_file(), f"Missing {d7_log}"
    assert len(d6_log.read_text(encoding="utf-8")) > 100
    assert len(d7_log.read_text(encoding="utf-8")) > 100
