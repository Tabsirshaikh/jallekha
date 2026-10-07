"""Make a LOCAL test day for the driver screen and the officer's route map: build the plan by
section for a day (tight capacity, so tankers make several round trips), check its flagged
sections, approve it as a demo officer, then print the tankers to try on the driver screen.

Run the API in local test mode first (sign-in off, SMS_PROVIDER=outbox); seed_demo.py before
this adds SYNTHETIC bookings so some trips carry a real delivery code. The plan itself is the
normal plan (SIMULATION: the day's demand comes from monthly totals); the three resident codes the
driver types at each stop are the fixed test code 000000.

Usage (API running on 8000):
    python scripts/demo/seed_driver_day.py [--day 2026-10-07] [--api http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
OFFICER = {"officer_id": "demo-officer", "reason": "SIMULATION test day for the driver screen"}


def call(api: str, method: str, path: str, body: object | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(api + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})  # fmt: skip
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        return {"error": exc.code, "detail": exc.read().decode()[:300]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--day", default=datetime.now(IST).date().isoformat())
    args = parser.parse_args()
    api, day = args.api.rstrip("/"), args.day
    if not call(api, "GET", "/sms/test-mode").get("test_mode"):
        print("Refused: run the API in local test mode (AUTH_REQUIRED unset, SMS_PROVIDER=outbox)")
        return 1
    plan = call(api, "POST", "/plans", {"day": day, "unit": "section", "capacity": "tight"})
    if "plan_id" not in plan:
        print(f"Plan not made: {plan}")
        return 1
    plan_id = plan["plan_id"]
    if plan["status"] != "APPROVED":
        for group in plan["flags"]:
            call(api, "POST", f"/plans/{plan_id}/groups/{urllib.parse.quote(group)}/check", OFFICER)
        done = call(api, "POST", f"/plans/{plan_id}/approve", OFFICER)
        if done.get("status") != "APPROVED":
            print(f"Plan {plan_id} not approved: {done}")
            return 1
    routes = call(api, "GET", f"/plans/{plan_id}/routes?compact=true")
    longest = sorted(routes["paths"], key=lambda p: (-len(p["trips"]), p["tanker_id"]))[:5]
    booked = call(api, "GET", f"/driver/tankers?day={day}").get("items", [])
    print(f"Approved plan {plan_id} for {day}.")
    print("On the driver screen pick Day", day, "and one of these tankers:")
    for p in longest:
        print(f"  {p['tanker_id']}  station {p['station_id']}  {len(p['trips'])} round trips")
    if booked:
        ids = ", ".join(t["tanker_id"] for t in booked[:5])
        print(f"Tankers carrying bookings made through JalLekha (real code flow): {ids}")
    print("At each stop: Delivered -> type 000000 for each of the 3 residents (test code).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
