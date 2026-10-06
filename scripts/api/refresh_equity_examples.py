"""Refresh affected evidence examples from the current committed derived contracts."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.routers.common import csv_rows, typed  # noqa: E402


def main():
    folder = ROOT / "docs/api_examples"
    wards = {r["ward_id"]: typed(r) for r in csv_rows("data/derived/equity/wards.csv")}
    for name in ("equity_summary.get", "equity_wards.get", "ward_report_card.get"):
        path = folder / f"{name}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["_example"]["status"] = "PROPOSED (local dasymetric repair, approval pending)"
        if name == "equity_summary.get":
            document["response"] = json.loads(
                (ROOT / "data/derived/equity/summary.json").read_text()
            )
        elif name == "equity_wards.get":
            document["response"]["items"] = [
                wards[r["ward_id"]] for r in document["response"]["items"]
            ]
        else:
            ward = wards[document["response"]["ward_id"]]
            document["response"]["bookings"].update(
                {k: ward[k] for k in ("bookings", "bookings_per_1000", "basis", "mapping_status")}
            )
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
