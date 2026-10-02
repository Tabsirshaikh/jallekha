"""Calibrate the F13 duplicate rule on the Chicago 311 extract (D13), task T1.

Runs only on P1's logged D13 pull: the input file must be listed in
data/verification/source_manifest.csv under a dataset id starting with "D13" and its
SHA-256 must match. Otherwise it stops with exit code 2 and writes nothing.

Usage:
    python scripts/trust/calibrate_dedup.py --input data/raw/<d13 file>.csv

Output: data/derived/dedup_calibration.csv (basis DERIVED). Each metric is printed next to the
value the solution document reports, for comparison only: if they differ, report the
difference; never tune the rule or the tests to match.

Chicago timestamps are local time without zone; they are compared as-is, so pairs that
straddle a daylight-saving change can be off by one hour.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.services.dedup import ComplaintRecord, DedupRule, haversine_m, link_duplicates

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "verification" / "source_manifest.csv"
OUTPUT = ROOT / "data" / "derived" / "dedup_calibration.csv"
SOURCE_DOC = "docs/JALLEKHA_FINAL_SOLUTION.md"

# (metric, group) -> (value reported in the solution document, where it says so)
REFERENCES = {
    ("child_parent_distance_m_p95", "all"): (106.0, f"{SOURCE_DOC} F13 '95% within 106 m'"),
    ("linked_share", "radius=100m;window=48h"): (0.71, f"{SOURCE_DOC} section 7 '100 m / 48 h'"),
    ("linked_share", "radius=300m;window=168h"): (0.88, f"{SOURCE_DOC} section 7 '300 m / 7 d'"),
}
# Uniform-window rules evaluated in section 7 of the solution document.
REPLAY_RULES = ((100.0, 48.0), (300.0, 168.0))
_TIME_FORMATS = ("%m/%d/%Y %I:%M:%S %p", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S")


class CalibrationBlocked(Exception):
    """The input is not P1's registered D13 pull."""


@dataclass(frozen=True)
class ChicagoRow:
    sr_number: str
    sr_type: str
    created_at: datetime
    lat: float | None
    lon: float | None
    duplicate: bool
    parent: str | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def registered_entry(path: Path, manifest: Path = MANIFEST, root: Path = ROOT) -> dict[str, str]:
    if not path.is_file():
        raise CalibrationBlocked(f"Input not found: {path}")
    if not manifest.is_file():
        raise CalibrationBlocked(f"Manifest not found: {manifest}")
    with manifest.open(encoding="utf-8", newline="") as handle:
        entries = [row for row in csv.DictReader(handle) if row["dataset_id"].startswith("D13")]
    resolved = path.resolve()
    for entry in entries:
        if (root / entry["file_path"]).resolve() == resolved:
            if entry["sha256"] != sha256_file(path):
                raise CalibrationBlocked(f"Checksum of {path} does not match the manifest")
            return entry
    raise CalibrationBlocked(
        f"{path} is not registered as D13 in {manifest}; wait for P1's logged D13 pull"
    )


def parse_time(value: str) -> datetime:
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised CREATED_DATE format: {value!r}")


def _float(value: str | None) -> float | None:
    try:
        number = float(value) if value not in (None, "") else None
    except ValueError:
        return None
    return number if number is not None and math.isfinite(number) else None


def parse_rows(path: Path) -> list[ChicagoRow]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for raw in reader:
            row = {key.strip().upper(): value for key, value in raw.items() if key}
            rows.append(
                ChicagoRow(
                    sr_number=row["SR_NUMBER"].strip(),
                    sr_type=row["SR_TYPE"].strip(),
                    created_at=parse_time(row["CREATED_DATE"]),
                    lat=_float(row.get("LATITUDE")),
                    lon=_float(row.get("LONGITUDE")),
                    duplicate=row.get("DUPLICATE", "").strip().lower() == "true",
                    parent=(row.get("PARENT_SR_NUMBER") or "").strip() or None,
                )
            )
    return rows


def quantile(values: list[float], q: float) -> float:
    """Linear interpolation between order statistics (same as numpy's default)."""
    if not values:
        return math.nan
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _true_root(sr: str, by_sr: dict[str, ChicagoRow]) -> str:
    seen = set()
    while by_sr[sr].parent in by_sr and sr not in seen:
        seen.add(sr)
        sr = by_sr[sr].parent  # type: ignore[assignment]
    return sr


def calibrate(rows: list[ChicagoRow]) -> list[dict[str, object]]:
    by_sr = {row.sr_number: row for row in rows}
    located = [row for row in rows if row.lat is not None and row.lon is not None]
    pairs = [
        (row, by_sr[row.parent])
        for row in located
        if row.duplicate and row.parent in by_sr and by_sr[row.parent].lat is not None
    ]
    results: list[dict[str, object]] = []

    def add(metric: str, group: str, value: float, n: int) -> None:
        reference, source = REFERENCES.get((metric, group), (None, ""))
        results.append(
            {
                "metric": metric,
                "group": group,
                "value": value,
                "n": n,
                "reference": reference,
                "reference_source": source,
            }
        )

    distances = [haversine_m(c.lat, c.lon, p.lat, p.lon) for c, p in pairs]  # type: ignore[arg-type]
    add("child_parent_distance_m_p95", "all", quantile(distances, 0.95), len(distances))
    by_type: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for (child, parent), distance in zip(pairs, distances, strict=True):
        hours = (child.created_at - parent.created_at).total_seconds() / 3600
        by_type[child.sr_type].append((distance, hours))
    for sr_type, values in sorted(by_type.items()):
        add(
            "child_parent_distance_m_p95",
            sr_type,
            quantile([d for d, _ in values], 0.95),
            len(values),
        )
        add("child_parent_hours_p90", sr_type, quantile([h for _, h in values], 0.90), len(values))

    records = [
        ComplaintRecord(
            id=r.sr_number,
            category=r.sr_type,
            lat=r.lat,
            lon=r.lon,  # type: ignore[arg-type]
            created_at=r.created_at,
        )
        for r in located
    ]
    for radius, window in REPLAY_RULES:
        rule = DedupRule(radius_m=radius, window_hours={}, default_window_hours=window)
        engine_root = {link.child_id: link.parent_id for link in link_duplicates(records, rule)}
        hits = sum(
            engine_root.get(child.sr_number) == _true_root(child.sr_number, by_sr)
            for child, _ in pairs
        )
        add(
            "linked_share",
            f"radius={radius:g}m;window={window:g}h",
            hits / len(pairs) if pairs else math.nan,
            len(pairs),
        )
    add("rows_total", "all", len(rows), len(rows))
    add("rows_without_coordinates", "all", len(rows) - len(located), len(rows))
    return results


def write_output(results: list[dict[str, object]], output: Path, basis_detail: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "metric",
        "group",
        "value",
        "n",
        "reference",
        "reference_source",
        "basis",
        "basis_detail",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in results:
            writer.writerow({**row, "basis": "DERIVED", "basis_detail": basis_detail})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        entry = registered_entry(args.input, args.manifest, args.root)
    except CalibrationBlocked as exc:
        print(f"calibrate_dedup: not run: {exc}", file=sys.stderr)
        return 2
    results = calibrate(parse_rows(args.input))
    basis_detail = (
        f"Chicago 311 {entry['dataset_id']} sha256={entry['sha256']} "
        f"retrieved {entry['retrieved_at_utc']}; F13 rule replay (T1 dedup engine); "
        "linked share = true duplicates whose engine cluster root equals the true root"
    )
    write_output(results, args.output, basis_detail)
    for row in results:
        print(
            f"{row['metric']:<30} {row['group']:<32} value={row['value']} n={row['n']} "
            f"reference={row['reference']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
