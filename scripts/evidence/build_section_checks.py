"""Build exact calendar-year section checks without fitting the legacy ward models."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
from app.config.section_checks import SECTION_CHECK_CONFIG as CONFIG  # noqa: E402
from app.services.section_checks import AnnualSection, backtest, screen  # noqa: E402
from scripts.evidence.build_equity import (  # noqa: E402
    DOMESTIC_CATEGORIES,
    FLATS_CATEGORIES,
)

OUTPUT = Path("data/derived/underserved")


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def annual(root, year):
    bookings, domestic, flats = defaultdict(int), defaultdict(int), defaultdict(int)
    booking_months, billing_months = defaultdict(set), defaultdict(set)
    inputs = []
    for month in range(1, CONFIG.months_per_year + 1):
        stem = f"{year}-{month:02}"
        for folder, billing in (("hmwssb_tankers_portal", False), ("hmwssb_billing_portal", True)):
            path = root / "data/raw" / folder / f"{stem}.csv"
            if not path.exists():
                continue
            inputs.append(path)
            keys = set()
            for row in read(path):
                if int(row["year"]) != year or int(row["month"]) != month:
                    raise ValueError(f"Date differs from file {path}")
                section = row["section"].strip()
                # Portal has an unnamed administrative bucket. It has no section identity;
                # exclude it explicitly rather than attaching its connections to a locality.
                if not section:
                    continue
                category = row.get("category") if billing else None
                division = row["division"].strip()
                key = (division, section, category)
                if key in keys:
                    raise ValueError(f"Duplicate/empty section row {key!r} in {path}")
                keys.add(key)
                identity = (division, section)
                if billing:
                    if category not in DOMESTIC_CATEGORIES:
                        continue
                    count = float(row["noofcans"])
                    if count < 0 or not count.is_integer():
                        raise ValueError("Invalid domestic connection count")
                    domestic[identity] += int(count)
                    if category in FLATS_CATEGORIES:
                        flats[identity] += int(count)
                    billing_months[identity].add(month)
                else:
                    count = float(row["noofbookings"])
                    if count < 0 or not count.is_integer():
                        raise ValueError("Invalid booking count")
                    bookings[identity] += int(count)
                    booking_months[identity].add(month)
    rows = [
        AnnualSection(
            s[1],
            s[0],
            year,
            bookings[s],
            domestic[s] / len(billing_months[s]) if billing_months[s] else None,
            flats[s] / domestic[s] if domestic[s] else None,
            len(booking_months[s]),
            len(billing_months[s]),
        )
        for s in sorted(booking_months)
    ]
    return rows, inputs


def build(root=ROOT):
    training, inputs = annual(root, CONFIG.train_year)
    current, current_inputs = annual(root, CONFIG.period_year)
    points_path = root / "data/derived/crosswalk/section_to_ward_2016.csv"
    need_path = root / "data/derived/evidence/ward_evidence.csv"
    points = {r["section"]: r for r in read(points_path)}
    wards = {r["ward_id"]: r for r in read(need_path)}
    context = {}
    cohort_wards = set()
    for section in current:
        point = points.get(section.section, {})
        if point.get("division") != section.division:
            point = {}
        ward_id = point.get("ward_id")
        ward = wards.get(ward_id, {})
        if ward.get("wad") and section.status(CONFIG) == "COMPLETE":
            context[f"{section.division}:{section.section}"] = float(ward["wad"])
            cohort_wards.add(ward_id)
    if cohort_wards:
        context["NEED_MEDIAN"] = median(float(wards[w]["wad"]) for w in cohort_wards)
    rows = screen(current, training, context)
    for row in rows:
        point = points.get(row["section"], {})
        if point.get("division") != row["division"]:
            point = {}
        row.update(
            ward_id=point.get("ward_id") or None,
            ward_name=point.get("ward_name") or None,
            lat=float(point["lat"]) if point.get("lat") else None,
            lng=float(point["lng"]) if point.get("lng") else None,
            location_basis="DERIVED_APPROXIMATE" if point.get("lat") else "UNAVAILABLE",
        )
    validation = backtest(training, current)
    inputs += current_inputs + [points_path, need_path]
    summary = {
        "schema_version": "e5-section-checks-v1",
        "config": asdict(CONFIG),
        "section_count": len(rows),
        "flagged_count": sum(r["field_check_candidate"] for r in rows),
        "validation": validation,
        "basis": "DERIVED",
        "method": "Annual bookings per 1000 mean monthly domestic connections; leave-target-out "
        "median of nearest same-division peers by log connection count and flats share. "
        "2024 ratio threshold; 2025 peer rates describe current comparisons. Need context only.",
        "limitations": [
            "Partial booking or billing years excluded, never filled with zero.",
            "Unnamed portal section buckets excluded; divisions are part of section identity.",
            "Connections are accounts, not households; flats share is only a proxy.",
            "Same-division peers may have different supply and booking access.",
            "2024 to 2025 accuracy is prediction accuracy, not field-check precision.",
            "Geocoded point and Census-2011 ward need are approximate context only.",
            "No field outcomes yet; flags cannot change allocation or entitlement.",
        ],
        "input_sha256": {
            str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in inputs
        },
    }
    return rows, summary


def encode(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows([{**r, "peer_sections": json.dumps(r["peer_sections"])} for r in rows])
    return stream.getvalue()


def main():
    rows, summary = build()
    folder = ROOT / OUTPUT
    folder.mkdir(exist_ok=True)
    (folder / "section_checks.csv").write_text(encode(rows), encoding="utf-8")
    (folder / "section_checks_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    (ROOT / "frontend/src/data/u5SectionChecks.json").write_text(
        json.dumps({"items": rows, "total": len(rows)}, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    example = {
        "_example": {
            "endpoint": "GET /underserved/section-checks",
            "status": "PROPOSED (implemented locally, owner approval pending)",
            "basis": "REAL bookings; DERIVED rates; DERIVED_APPROXIMATE need; ASSUMED policy",
            "built_from": (
                "data/derived/underserved/section_checks.csv and section_checks_summary.json"
            ),
        },
        "request": {"offset": 0, "limit": 2},
        "response": {
            "schema_version": summary["schema_version"],
            "basis": summary["basis"],
            "limitations": summary["limitations"],
            "validation": {k: v for k, v in validation_without_predictions(summary).items()},
            "flagged_count": summary["flagged_count"],
            "total": len(rows),
            "offset": 0,
            "limit": 2,
            "items": rows[:2],
        },
    }
    (ROOT / "docs/api_examples/section_checks.get.json").write_text(
        json.dumps(example, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in summary.items() if k in ("section_count", "flagged_count")}))
    print(json.dumps({k: v for k, v in summary["validation"].items() if k != "predictions"}))


def validation_without_predictions(summary):
    return {k: v for k, v in summary["validation"].items() if k != "predictions"}


if __name__ == "__main__":
    main()
