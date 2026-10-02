"""Read HMWSSB monthly tanker files and recompute simple real-data figures. Ported from v1 (S3).

Columns: year, month, division, section, noofbookings, delivered. Works on the S2 OpenCity
files (data/raw/hmwssb_tankers) and the D1b portal files (data/raw/hmwssb_tankers_portal).
v1's spreading of months into synthetic days is not ported; the booking replay is A1.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def _int(value: str | None) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0


def read_rows(data_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(data_dir.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle):
                section = (raw.get("section") or "").strip().upper()
                if not section or not raw.get("year"):
                    continue
                rows.append(
                    {
                        "year": _int(raw["year"]),
                        "month": _int(raw["month"]),
                        "division": (raw.get("division") or "").strip(),
                        "section": section,
                        "bookings": _int(raw.get("noofbookings")),
                        "delivered": _int(raw.get("delivered")),
                    }
                )
    return rows


def monthly_totals(rows: list[dict[str, Any]]) -> dict[tuple[int, int], int]:
    totals: dict[tuple[int, int], int] = defaultdict(int)
    for row in rows:
        totals[(row["year"], row["month"])] += row["bookings"]
    return dict(sorted(totals.items()))


def concentration(rows: list[dict[str, Any]], year: int, month: int) -> dict[str, Any]:
    """Share of a month's bookings held by the top 10% and bottom 50% of sections."""
    bookings = sorted(
        (r["bookings"] for r in rows if r["year"] == year and r["month"] == month), reverse=True
    )
    if not bookings:
        return {"year": year, "month": month, "sections": 0}
    total = sum(bookings)
    n = len(bookings)
    top_n = math.ceil(n * 0.10)
    bottom_n = n // 2
    return {
        "year": year,
        "month": month,
        "sections": n,
        "total_bookings": total,
        "top10_share": round(sum(bookings[:top_n]) / total, 4),
        "bottom50_share": round(sum(bookings[n - bottom_n :]) / total, 4),
    }


def seasonality_index(rows: list[dict[str, Any]]) -> dict[int, float]:
    """Mean bookings per calendar month divided by the mean over all observed months."""
    totals = monthly_totals(rows)
    by_month: dict[int, list[int]] = defaultdict(list)
    for (_year, month), value in totals.items():
        if value:
            by_month[month].append(value)
    observed = [v for v in totals.values() if v]
    mean_all = sum(observed) / max(1, len(observed))
    return {m: round((sum(vs) / len(vs)) / mean_all, 4) for m, vs in sorted(by_month.items())}


def insights(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Figures recomputed from the raw rows, never typed in by hand."""
    totals = monthly_totals(rows)
    jan, may = totals.get((2022, 1), 0), totals.get((2022, 5), 0)
    return {
        "months_available": len([v for v in totals.values() if v]),
        "sections": len({r["section"] for r in rows}),
        "monthly_totals": [{"year": y, "month": m, "bookings": v} for (y, m), v in totals.items()],
        "concentration": [concentration(rows, 2022, m) for m in (1, 5, 8)],
        "jan_may_2022": {"jan": jan, "may": may, "surge": round(may / jan, 2) if jan else None},
        "seasonality_index": seasonality_index(rows),
    }
