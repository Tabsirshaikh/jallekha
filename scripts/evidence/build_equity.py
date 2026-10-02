"""E4: exact section booking concentration; absent data never becomes measured zero."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.config.equity import EQUITY_CONFIG  # noqa: E402

OUT = "data/derived/equity/"


def gini(values):
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Gini requires finite nonnegative values")
    values = sorted(values)
    total, count = sum(values), len(values)
    if not count or not total:
        return None
    return (
        2 * sum((i + 1) * v for i, v in enumerate(values)) / (count * total) - (count + 1) / count
    )


def per_thousand(bookings, population):
    if bookings is None or population is None or population <= 0:
        return None
    if bookings < 0 or not math.isfinite(bookings) or not math.isfinite(population):
        raise ValueError("Invalid rate input")
    return 1000 * bookings / population


def transfer(section_totals, mappings):
    """Reviewed approximate crosswalk; preserve mass and never infer wards from numbers."""
    by_section = defaultdict(list)
    for row in mappings:
        if row["reviewer_status"] != "approved" or not row.get("source_url"):
            raise ValueError("Unreviewed section mapping")
        if row["section"] not in section_totals:
            raise ValueError("Unknown section")
        weight = float(row["weight"])
        if not math.isfinite(weight) or not 0 < weight <= 1 or not row["ward_id"]:
            raise ValueError("Invalid mapping weight/ward")
        by_section[row["section"]].append((row["ward_id"], weight))
    result = defaultdict(float)
    for section, rows in by_section.items():
        if len({ward for ward, _ in rows}) != len(rows) or not math.isclose(
            sum(weight for _, weight in rows), 1, abs_tol=1e-9
        ):
            raise ValueError("Duplicate mapping or weights do not sum to one")
        for ward, weight in rows:
            result[ward] += section_totals[section] * weight
    return dict(result), sorted(set(section_totals) - set(by_section))


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def build(root=ROOT):
    inputs = sorted((root / "data/raw/hmwssb_tankers").glob("*.csv"))
    totals, deliveries, divisions, months_seen = (
        defaultdict(int),
        defaultdict(int),
        {},
        defaultdict(set),
    )
    monthly = []
    for path in inputs:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            if rows and reader.fieldnames != [
                "year",
                "month",
                "division",
                "section",
                "noofbookings",
                "delivered",
            ]:
                raise ValueError("Tanker source schema changed")
            if not rows and reader.fieldnames not in (
                ["year", "month"],
                ["year", "month", "division", "section", "noofbookings", "delivered"],
            ):
                raise ValueError("Unrecognized empty tanker source schema")
        month = path.stem
        keys = set()
        for row in rows:
            if month != f"{int(row['year']):04d}-{int(row['month']):02d}":
                raise ValueError("Row date differs from source file")
            section = row["section"].strip()
            division = row["division"]
            if section in keys or not section:
                raise ValueError("Duplicate/empty section-month row")
            keys.add(section)
            if section in divisions and divisions[section] != division:
                raise ValueError("Section name collision across divisions; new identity required")
            divisions[section] = division
            for field in ("noofbookings", "delivered"):
                if not row[field].isdigit():
                    raise ValueError("Missing or invalid source count")
            totals[section] += int(row["noofbookings"])
            deliveries[section] += int(row["delivered"])
            months_seen[section].add(month)
        monthly.append(
            {
                "month": month,
                "bookings": sum(int(r["noofbookings"]) for r in rows) if rows else None,
                "delivered": sum(int(r["delivered"]) for r in rows) if rows else None,
                "reported_sections": len(rows),
                "status": "OBSERVED_SOURCE_ROWS" if rows else "NO_SOURCE_ROWS",
                "basis": "REAL" if rows else "UNAVAILABLE",
            }
        )
    ordered = sorted(totals, key=lambda s: (-totals[s], s))
    total, count = sum(totals.values()), len(totals)
    top_count = math.ceil(count * EQUITY_CONFIG.top_fraction)
    bottom_count = math.floor(count * EQUITY_CONFIG.bottom_fraction)
    section_rows = [
        {
            "section": s,
            "division": divisions[s],
            "bookings": totals[s],
            "delivered": deliveries[s],
            "rank": i + 1,
            "share": round(totals[s] / total, 9),
            "observed_months": len(months_seen[s]),
            "population": None,
            "bookings_per_1000": None,
            "denominator_status": "NO_VERIFIED_SECTION_POPULATION",
            "count_basis": "REAL",
            "metric_basis": "DERIVED",
        }
        for i, s in enumerate(ordered)
    ]
    lorenz = [{"section_fraction": 0.0, "booking_fraction": 0.0}]
    cumulative = 0
    for i, section in enumerate(reversed(ordered), 1):
        cumulative += totals[section]
        lorenz.append(
            {
                "section_fraction": round(i / count, 9),
                "booking_fraction": round(cumulative / total, 9),
            }
        )
    seasonal = []
    for month in range(1, 13):
        observed = [
            r for r in monthly if int(r["month"][5:]) == month and r["bookings"] is not None
        ]
        seasonal.append(
            {
                "calendar_month": month,
                "observed_years": len(observed),
                "mean_monthly_bookings": round(
                    sum(r["bookings"] for r in observed) / len(observed), 6
                )
                if observed
                else None,
                "status": "DESCRIPTIVE_UNBALANCED_YEAR_SAMPLE",
                "basis": "DERIVED" if observed else "UNAVAILABLE",
            }
        )
    with (root / "data/derived/evidence/ward_evidence.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        wards = list(csv.DictReader(handle))
    ward_rows = [
        {
            "ward_id": w["ward_id"],
            "ward_name": w["ward_name"],
            "bookings": None,
            "bookings_per_1000": None,
            "mapping_status": "NO_VERIFIED_SECTION_WARD_CROSSWALK",
            "census_join_status": w["join_status"],
            "basis": "UNAVAILABLE",
        }
        for w in wards
    ]
    summary = {
        "section_count": count,
        "source_row_count": sum(r["reported_sections"] for r in monthly),
        "bookings": total,
        "delivered": sum(deliveries.values()),
        "delivery_to_booking_ratio": round(sum(deliveries.values()) / total, 9),
        "gini": round(gini(list(totals.values())), 9),
        "gini_basis": "DERIVED",
        "top_fraction_requested": EQUITY_CONFIG.top_fraction,
        "top_section_count": top_count,
        "top_booking_share": round(sum(totals[s] for s in ordered[:top_count]) / total, 9),
        "bottom_section_count": bottom_count,
        "bottom_booking_share": round(sum(totals[s] for s in ordered[-bottom_count:]) / total, 9),
        "missing_source_months": [r["month"] for r in monthly if r["bookings"] is None],
        "ward_metrics_status": "BLOCKED_NO_VERIFIED_SECTION_WARD_CROSSWALK",
        "interpretation": "Concentration of observed bookings, not unequal need or proven neglect",
        "seasonality_caveat": "Unbalanced observed years; December 2022 has no records, not zero",
        "source_url": "https://data.opencity.in/dataset/hyderabad-water-supply-through-tankers-data",
    }
    artifacts = {
        OUT + "sections.csv": csv_bytes(section_rows),
        OUT + "monthly.csv": csv_bytes(monthly),
        OUT + "lorenz.csv": csv_bytes(lorenz),
        OUT + "seasonality.csv": csv_bytes(seasonal),
        OUT + "wards.csv": csv_bytes(ward_rows),
        OUT + "summary.json": (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode(),
    }
    checks = {
        "raw_inputs_sha256": {
            str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in inputs
        },
        "evidence_input_sha256_lf": hashlib.sha256(
            (root / "data/derived/evidence/ward_evidence.csv").read_text(encoding="utf-8").encode()
        ).hexdigest(),
        "outputs_sha256": {p: hashlib.sha256(b).hexdigest() for p, b in artifacts.items()},
    }
    artifacts["data/verification/equity_checks.json"] = (
        json.dumps(checks, indent=2, sort_keys=True) + "\n"
    ).encode()
    return artifacts


if __name__ == "__main__":
    for name, data in build().items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print("E4 exact section metrics built; unsupported ward metrics remain empty.")
