"""Small deterministic counterfactuals; SIMULATION, not Hyderabad field validation."""

import json
import sys
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import fair_queue, weekly_priority  # noqa: E402


def main():
    day = date(2026, 10, 7)
    at = datetime(2026, 10, 7, tzinfo=UTC)
    bookings = [
        fair_queue.QueueBooking(f"{g}-{i}", g, at, 2, f"{g}-{i}", "domestic")
        for g in ("A", "B")
        for i in range(20)
    ]
    baseline = {"A": 200.0, "B": 120.0}
    review = {
        "checked_on": "2026-10-06",
        "supply": "unavailable",
        "tanker_share": 1,
        "records_complete": True,
        "ledger_missing": False,
    }
    covered = weekly_priority.calculate(100, 2, review, 10500, day)
    neglected = weekly_priority.calculate(100, 1.2, review, 0, day, days_below_minimum=7)
    factors = {"A": covered["allocation_factor"], "B": neglected["allocation_factor"]}
    rows = {}
    for policy, weights in {
        "baseline": baseline,
        "weekly": {g: v * factors[g] for g, v in baseline.items()},
        "unknown_records": {
            g: v * weekly_priority.calculate(100, v / 100, None, 0, day)["allocation_factor"]
            for g, v in baseline.items()
        },
    }.items():
        result = fair_queue.order_bookings(bookings, 20, weights, fair_queue.QueueState())
        rows[policy] = dict(Counter(d.booking.group for d in result.served))
    assert rows["weekly"]["B"] > rows["baseline"]["B"]
    assert rows["unknown_records"] == rows["baseline"]
    assert sum(rows["weekly"].values()) == sum(rows["baseline"].values()) == 20
    output = {
        "basis": "SIMULATION",
        "policy_coefficients": "ASSUMED",
        "scenario": "Equal populations; A weekly requirement covered, B no water; "
        "40 tier-2 bookings share 20 trips at one station",
        "served_by_area": rows,
        "limitation": "Illustrative mechanics only. No current requirements or complete "
        "real delivery cohorts exist; no real-world improvement claim.",
    }
    path = ROOT / "data/verification/weekly_priority_examples.json"
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
