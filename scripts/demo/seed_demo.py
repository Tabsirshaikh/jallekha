"""Fill a LOCAL JalLekha with SYNTHETIC demo data, so the screens show warnings and the booking
flow working (for a demo or a judge). Every record it makes is labelled SYNTHETIC; never run it
against a real deployment.

It talks to a running API in local test mode (sign-in off, SMS_PROVIDER=outbox):

* 30 SYNTHETIC bookings through the booking API in 8 sections (homes with and without water, two
  hospitals and a school, verified by a demo officer), so "Bookings" counts and the officer's
  booking panel fill;
* SYNTHETIC "no water" complaints in three sections' wards, so the complaint sign turns red;
* one SYNTHETIC supply-cut notice (Gachibowli), so the cut sign and the water-cut card show;
* SYNTHETIC supply checks dated yesterday for three sections (no water / partly / enough), so
  "Current water priority" shows a requirement, a shortfall and a covered section.

Usage (API running on 8000):
    python scripts/demo/seed_demo.py [--api http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IST = timezone(timedelta(hours=5, minutes=30))

# (section, how many bookings, category mix) - busy western sections and a few others
BOOKINGS = [
    ("KONDAPUR (DIV 15)", 7, "home"),
    ("KUKATPALLY", 5, "home"),
    ("HAFEEZPET", 4, "home"),
    ("GACHIBOWLI (DIV 15)", 4, "home"),
    ("MANIKONDA (DIV 18)", 4, "home"),
    ("SOMAJIGUDA", 2, "hospital"),
    ("KPHB", 2, "home"),
    ("DILSHUKNAGAR", 2, "school"),
]
COMPLAINT_SECTIONS = ["KONDAPUR (DIV 15)", "MANIKONDA (DIV 18)", "HAFEEZPET", "GACHIBOWLI (DIV 15)"]
REVIEWS = [  # section, supply, tanker share, why bookings are low
    ("MANIKONDA (DIV 18)", "unavailable", 1.0, "access_difficulty"),
    ("KPHB", "insufficient", 0.4, "unclear"),
    ("SOMAJIGUDA", "adequate", 0.0, "other_supply"),
]


def call(api: str, method: str, path: str, body: object | None = None) -> object:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(api + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})  # fmt: skip
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        return {"error": exc.code, "detail": exc.read().decode()[:300]}


def rows(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    api = parser.parse_args().api.rstrip("/")
    if not call(api, "GET", "/sms/test-mode").get("test_mode"):  # type: ignore[union-attr]
        print("Refused: run the API in local test mode (AUTH_REQUIRED unset, SMS_PROVIDER=outbox)")
        return 1
    from shapely.geometry import shape

    cells = json.loads((ROOT / "data/derived/crosswalk/section_cells.geojson").read_text("utf-8"))
    points = {}
    for f in cells["features"]:  # a point inside each section's approximate area
        inside = shape(f["geometry"]).representative_point()
        points[f["properties"]["section"]] = {"lat": str(inside.y), "lng": str(inside.x)}
    need = {r["section"]: r for r in rows("data/derived/evidence/section_need.csv")}
    checks = {r["section"]: r for r in rows("data/derived/underserved/section_checks.csv")}
    made = 0
    for n_section, (section, count, kind) in enumerate(BOOKINGS):
        p = points.get(section)
        if not p or not p["lat"]:
            print(f"skip {section}: no point")
            continue
        for k in range(count):
            # spread the pins a little inside the section; the server decides the section
            lat = float(p["lat"]) + 0.0003 * ((k % 3) - 1)
            lon = float(p["lng"]) + 0.0003 * ((k // 3) - 1)
            category = kind if k == 0 else "home"
            body = {
                "lat": lat, "lon": lon, "category": category,
                "water_at_home": "no" if k % 2 == 0 else "yes",
                "phone": f"+9190000{n_section:02d}{k:03d}", "language": "te",
                "basis": "SYNTHETIC",
                "facility_name": f"Demo {category.replace('_', ' ')} {section}"
                if category != "home" else None,
            }  # fmt: skip
            out = call(api, "POST", "/bookings", body)
            if isinstance(out, dict) and "booking_id" in out:
                made += 1
                if category != "home":
                    call(api, "POST", f"/bookings/{out['booking_id']}/claim",
                         {"decision": "VERIFIED", "officer_id": "demo-officer",
                          "reason": "SYNTHETIC demo: facility on the mapped list"})  # fmt: skip
            else:
                print(f"booking in {section} not made: {out}")
    print(f"{made} SYNTHETIC bookings made (one open booking per phone: rerun adds none)")

    items = []
    for section in COMPLAINT_SECTIONS:
        ward = need.get(section, {}).get("main_ward_id")
        p = points.get(section)
        for k in range(4):
            items.append({"client_id": f"demo-{uuid.uuid4()}", "channel": "app",
                          "category": "no_water", "text": "No water for two days (demo)",
                          "language_hint": "en", "ward_id": ward,
                          "lat": float(p["lat"]) + 0.002 * k if p else None,  # apart: no merge
                          "lon": float(p["lng"]) if p else None, "is_synthetic": True})  # fmt: skip
    out = call(api, "POST", "/intake/batch", {"items": items})
    print("complaints:", [r.get("status") for r in out.get("results", [])])  # type: ignore[union-attr]

    now = datetime.now(IST)
    notice = {
        "source": "hmwssb_press_release",
        "raw_text": "SYNTHETIC DEMO: water supply interrupted in Gachibowli for pipeline works.",
        "area_names": ["Gachibowli"],
        "start": (now - timedelta(hours=6)).isoformat(),
        "end": (now + timedelta(hours=30)).isoformat(),
        "entered_by": "demo-officer",
        "is_synthetic": True,
    }
    out = call(api, "POST", "/notices", notice)
    print("supply-cut notice:", "ok" if "error" not in str(out)[:20] else out)

    yesterday = (now - timedelta(days=1)).date().isoformat()
    for section, supply, share, reason in REVIEWS:
        row = checks.get(section)
        if not row:
            print(f"skip review {section}: not in section checks")
            continue
        body = {"id": str(uuid.uuid4()), "section_id": row["section_id"], "checked_on": yesterday,
                "supply": supply, "tanker_share": share, "records_complete": True,
                "booking_reason": reason, "synthetic": True,
                "note": "SYNTHETIC demo supply check: not a real field visit"}  # fmt: skip
        out = call(api, "POST", "/field-checks/supply-reviews", body)
        print(f"supply check {section}: {'ok' if 'error' not in out else out}")  # type: ignore[operator]
    print(f"Done at {datetime.now(UTC).isoformat()}. Everything above is labelled SYNTHETIC.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
