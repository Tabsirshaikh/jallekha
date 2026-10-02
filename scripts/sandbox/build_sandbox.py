"""A8 policy sandbox (F19): every policy on the same replayed bookings, capacities and seeds.

Usage:
    python scripts/sandbox/build_sandbox.py [--workers N]

Replays (A1): Mar-Jul 2025 (main) and Mar-Jul 2023 (continuity). Monthly section totals are
REAL; the daily split and arrival times are SYNTHETIC (one draw per seed, shared by all
policies). Stations are the A8 stand-ins (scripts/sandbox/build_stations.py, ASSUMED).

Capacity scenarios, trips per station per day, split by each station's bookings in the same
months of the year before (fleet deployed where demand was last year):
- fleet: fleet_tankers x trips_per_tanker_day for the whole city (news figures);
- tight: last year's mean daily bookings x a factor, the factor chosen (seed 0, B1) so that B1
  delivers tight_delivered_share of bookings, the REAL Jun-Aug 2026 HMWSSB level.
Every station with home sections gets at least one trip a day.

Outputs (all labelled SIMULATION): data/derived/sandbox/results.csv (one row per replay,
scenario, policy and seed) and data/derived/sandbox/summary.json (mean and range, paired
differences against B1, where JL is worse). REAL baselines are reported separately.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import io
import json
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.allocation import ALLOCATION_CONFIG  # noqa: E402
from app.config.sandbox import SANDBOX_CONFIG  # noqa: E402
from app.services import (  # noqa: E402
    booking_groups,
    hmwssb,
    replay,
    sandbox,
    scheduled_supply,
    service_models,
)

TANKERS = "data/raw/hmwssb_tankers_portal"
SECTIONS = "data/derived/sandbox/section_points.csv"
NETWORK = "data/derived/sandbox/section_station_km.csv"
EQUITY = "data/derived/equity/summary.json"
EVIDENCE = "data/derived/evidence/ward_evidence.csv"
SECTION_WARDS = booking_groups.SECTION_WARDS
RESULTS = "data/derived/sandbox/results.csv"
SUMMARY = "data/derived/sandbox/summary.json"
CHECKS = "data/verification/sandbox_checks.json"
INPUTS = (TANKERS, SECTIONS, NETWORK, EQUITY, EVIDENCE, SECTION_WARDS)

LABEL = "SIMULATION"
REPLAYS = {
    "main_2025": ALLOCATION_CONFIG.replay_months_main,
    "secondary_2023": ALLOCATION_CONFIG.replay_months_secondary,
}
SCENARIOS = ("fleet", "tight")
METRICS = (
    "served_share",
    "unmet_share",
    "need_weighted_unmet_share",
    "mean_wait_days",
    "p90_wait_days",
    "tanker_km",
    "km_per_kl",
    "unused_capacity_share",
    "gini_fill_rate",
    "jain_fill_rate",
    "worst_group_fill_rate",
    "gini_need_coverage",
    "jain_need_coverage",
    "zero_water_ward_share",
    "scheduled_litres_per_day",
)
# Direction of "better" for each measure, used to list where JL is worse than B1.
HIGHER_IS_BETTER = {
    "served_share",
    "jain_fill_rate",
    "worst_group_fill_rate",
    "jain_need_coverage",
}
NEUTRAL = {"tanker_km", "scheduled_litres_per_day"}  # km is reported per kilolitre
CALIBRATION_STEPS = 16
POLICY_NOTES = {
    "B1": "FCFS at the nearest filling station (HMWSSB today)",
    "B2": "Nearest bookings first at each station",
    "B3": "Section with most pending bookings first",
    "B4": "Minimum cost: stations pooled, cheapest trips first",
    "B5": "Highest ward need weight first",
    "JL_F8": "JalLekha fair queue only (A3)",
    "JL": "JalLekha fair queue (A3) + scheduled-supply reserve (A4)",
}


@dataclass(frozen=True)
class Context:
    rows: list[dict[str, Any]]
    network: sandbox.Network
    mapping: dict[str, booking_groups.SectionLink]
    entitlement: dict[str, float]
    need_weight: dict[str, float]
    scheduled: tuple[scheduled_supply.ScheduledWard, ...]


def load_context(root: Path = ROOT) -> Context:
    rows = hmwssb.read_rows(root / TANKERS)
    with (root / NETWORK).open(encoding="utf-8", newline="") as handle:
        km = {
            (r["section"], r["station_id"]): float(r["round_trip_km"])
            for r in csv.DictReader(handle)
        }
    with (root / SECTIONS).open(encoding="utf-8", newline="") as handle:
        home = {
            r["section"]: r["home_station"] for r in csv.DictReader(handle) if r["home_station"]
        }
    mapping = booking_groups.load_section_wards(root)
    evidence = service_models.load_evidence(root)
    needs = service_models.build_ward_needs(evidence, [])
    entitlement, _fallback = booking_groups.group_entitlements(needs, mapping)
    ward_weight = {n.ward_id: n.need_weight for n in needs if n.need_weight}
    median_weight = statistics.median(ward_weight.values())
    need_weight = {
        group: ward_weight.get(group.removeprefix("ward:"), median_weight) for group in entitlement
    }
    candidates = {n.ward_id for n in needs if n.scheduled_supply_candidate}
    # Simulation: every A2 candidate is treated as officer-confirmed for scheduled supply.
    scheduled = tuple(scheduled_supply.scheduled_wards(needs, evidence, candidates))
    return Context(rows, sandbox.Network(km, home), mapping, entitlement, need_weight, scheduled)


def _days_in(months: tuple[tuple[int, int], ...]) -> int:
    return sum(calendar.monthrange(y, m)[1] for y, m in months)


def bookings_for(ctx: Context, months, seed: int) -> tuple[list[sandbox.SimBooking], int]:
    """The seed's replayed bookings; sections without a station point are left out."""
    start = date(*months[0], 1)
    out, left_out = [], 0
    for b in replay.arrivals(replay.daily_counts(ctx.rows, months, seed), seed):
        if b.section not in ctx.network.home:
            left_out += 1
            continue
        out.append(
            sandbox.SimBooking(
                booking_id=b.booking_id,
                section=b.section,
                group=booking_groups.group_for(b.section, ctx.mapping),
                day=(b.arrived_at.date() - start).days,
                arrived_at=b.arrived_at,
            )
        )
    return out, left_out


def station_base(ctx: Context, months) -> dict[str, float]:
    """Mean daily bookings per station in the same months one year earlier."""
    prior = {(y - 1, m) for y, m in months}
    days = _days_in(tuple(sorted(prior)))
    base: dict[str, float] = defaultdict(float)
    for station in set(ctx.network.home.values()):
        base[station] = 0.0
    for r in ctx.rows:
        if (r["year"], r["month"]) in prior and r["section"] in ctx.network.home:
            base[ctx.network.home[r["section"]]] += r["bookings"] / days
    return dict(base)


def fleet_capacity(base: dict[str, float]) -> dict[str, int]:
    cfg = SANDBOX_CONFIG
    trips = cfg.fleet_tankers * cfg.trips_per_tanker_day
    total = sum(base.values())
    return {s: max(1, round(trips * b / total)) for s, b in sorted(base.items())}


def scaled_capacity(base: dict[str, float], factor: float) -> dict[str, int]:
    return {s: max(1, round(factor * b)) for s, b in sorted(base.items())}


def setting_for(ctx: Context, months, capacity: dict[str, int]) -> sandbox.Setting:
    return sandbox.Setting(
        days=_days_in(months),
        capacity=capacity,
        entitlement=ctx.entitlement,
        need_weight=ctx.need_weight,
        expiry_days=SANDBOX_CONFIG.booking_expiry_days,
        litres_per_trip=ALLOCATION_CONFIG.tanker_load_litres,
        scheduled=ctx.scheduled,
        reserve_share=SANDBOX_CONFIG.jl_scheduled_reserve_share,
    )


def calibrate_tight(ctx: Context, months, base: dict[str, float]) -> tuple[float, float]:
    """Bisect the capacity factor so B1 (seed 0) delivers tight_delivered_share."""
    bookings, _ = bookings_for(ctx, months, 0)
    target = SANDBOX_CONFIG.tight_delivered_share
    low, high, best = 0.2, 2.0, (float("inf"), 1.0, 1.0)
    for _ in range(CALIBRATION_STEPS):
        factor = (low + high) / 2
        result = sandbox.run(
            "B1",
            bookings,
            ctx.network,
            setting_for(ctx, months, scaled_capacity(base, factor)),
        )
        share = len(result.served) / len(bookings)
        best = min(best, (abs(share - target), factor, share))
        low, high = (factor, high) if share < target else (low, factor)
    return round(best[1], 6), best[2]


def run_seed(
    ctx: Context,
    replay_name: str,
    capacities: dict[str, dict[str, int]],
    seed: int,
    policies: tuple[str, ...] = sandbox.POLICIES,
) -> list[dict[str, Any]]:
    months = REPLAYS[replay_name]
    bookings, left_out = bookings_for(ctx, months, seed)
    rows = []
    for scenario, capacity in capacities.items():
        cfg = setting_for(ctx, months, capacity)
        for policy in policies:
            result = sandbox.run(policy, bookings, ctx.network, cfg)
            m = sandbox.measures(
                result,
                bookings,
                ctx.network,
                cfg,
                SANDBOX_CONFIG.fairness_min_group_bookings,
            )
            rows.append(
                {
                    "replay": replay_name,
                    "scenario": scenario,
                    "policy": policy,
                    "seed": seed,
                    **{k: round(v, 6) if isinstance(v, float) else v for k, v in m.items()},
                    "bookings_left_out": left_out,
                    "label": LABEL,
                }
            )
    return rows


_CTX: Context | None = None


def _worker_init() -> None:
    global _CTX
    _CTX = load_context()


def _worker(job: tuple[str, dict[str, dict[str, int]], int]) -> list[dict[str, Any]]:
    assert _CTX is not None
    return run_seed(_CTX, *job)


def _sha(path: Path) -> str:
    if path.is_dir():
        digest = hashlib.sha256()
        for child in sorted(path.glob("*.csv")):
            digest.update(child.name.encode() + child.read_bytes())
        return digest.hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def real_baselines(ctx: Context, root: Path) -> dict[str, Any]:
    equity = json.loads((root / EQUITY).read_text(encoding="utf-8"))
    delivered = {}
    for name, months in [
        *REPLAYS.items(),
        ("jun_aug_2026", ((2026, 6), (2026, 7), (2026, 8))),
    ]:
        rows = [r for r in ctx.rows if (r["year"], r["month"]) in set(months)]
        booked = sum(r["bookings"] for r in rows)
        delivered[name] = round(sum(r["delivered"] for r in rows) / booked, 6)
    return {
        "label": "REAL",
        "booking_gini_sections": equity["gini"],
        "booking_gini_basis": equity["gini_basis"],
        "delivered_share": delivered,
        "source": "HMWSSB tanker bookings, Telangana Open Data Portal (D1); E4 equity summary",
    }


def jl_worse(summary: dict[str, Any]) -> list[dict[str, Any]]:
    worse = []
    for replay_name, scenarios in summary.items():
        for scenario, block in scenarios.items():
            for metric in METRICS:
                if metric in NEUTRAL:
                    continue
                diff = block["policies"]["JL"][metric]["diff_vs_b1_mean"]
                bad = diff < -1e-9 if metric in HIGHER_IS_BETTER else diff > 1e-9
                if bad:
                    worse.append(
                        {
                            "replay": replay_name,
                            "scenario": scenario,
                            "metric": metric,
                            "diff_vs_b1_mean": round(diff, 6),
                        }
                    )
    return worse


def build(root: Path = ROOT, workers: int = 1, seeds: int | None = None) -> dict[str, bytes]:
    cfg = SANDBOX_CONFIG
    seeds = cfg.seeds if seeds is None else seeds
    ctx = load_context(root)
    capacities: dict[str, dict[str, dict[str, int]]] = {}
    scenario_info: dict[str, dict[str, Any]] = {}
    for replay_name, months in REPLAYS.items():
        base = station_base(ctx, months)
        factor, b1_share = calibrate_tight(ctx, months, base)
        capacities[replay_name] = {
            "fleet": fleet_capacity(base),
            "tight": scaled_capacity(base, factor),
        }
        scenario_info[replay_name] = {
            "fleet": {
                "trips_per_day": sum(capacities[replay_name]["fleet"].values()),
                "basis": "REAL fleet (news) x DERIVED trips per tanker; split ASSUMED",
            },
            "tight": {
                "trips_per_day": sum(capacities[replay_name]["tight"].values()),
                "factor_on_last_year_daily_bookings": factor,
                "calibration_b1_served_share_seed0": round(b1_share, 6),
                "target_served_share": cfg.tight_delivered_share,
                "basis": "Calibrated to the REAL Jun-Aug 2026 delivered share",
            },
        }
    jobs = [(name, capacities[name], seed) for name in REPLAYS for seed in range(seeds)]
    if workers > 1:
        with ProcessPoolExecutor(workers, initializer=_worker_init) as pool:
            chunks = list(pool.map(_worker, jobs))
    else:
        chunks = [run_seed(ctx, *job) for job in jobs]
    rows = sorted(
        (row for chunk in chunks for row in chunk),
        key=lambda r: (
            r["replay"],
            r["scenario"],
            sandbox.POLICIES.index(r["policy"]),
            r["seed"],
        ),
    )
    summary: dict[str, Any] = {}
    for replay_name in REPLAYS:
        summary[replay_name] = {}
        for scenario in SCENARIOS:
            subset = [r for r in rows if r["replay"] == replay_name and r["scenario"] == scenario]
            summary[replay_name][scenario] = {
                **scenario_info[replay_name][scenario],
                "policies": sandbox.compare(subset, list(METRICS)),
            }
    document = {
        "label": LABEL,
        "seeds": seeds,
        "policies": POLICY_NOTES,
        "results": summary,
        "jl_worse_than_b1": jl_worse(summary),
        "real_baselines": real_baselines(ctx, root),
        "duplicates": {
            "status": "NOT_AVAILABLE",
            "reason": (
                "The booking replay has no complaints, and T1's duplicate calibration has not "
                "been run (the D13 Chicago 311 extract is not logged in the source manifest)."
            ),
            "solution_document_value": "71% linked at 100 m / 48 h (not verified here)",
        },
        "settings": {
            "booking_expiry_days": cfg.booking_expiry_days,
            "stations": cfg.station_count,
            "station_basis": "ASSUMED_STAND_IN",
            "jl_scheduled_reserve_share": cfg.jl_scheduled_reserve_share,
            "scheduled_wards": len(ctx.scheduled),
            "fairness_min_group_bookings": cfg.fairness_min_group_bookings,
            "section_access_km": cfg.section_access_km,
        },
        "limitations": [
            "SIMULATION: daily arrivals are synthetic; only monthly section totals are REAL.",
            "Filling stations are 90 stand-ins placed where bookings cluster; HMWSSB publishes "
            "no station list.",
            "Replay bookings carry no tier, so tier 0/1 priority is not exercised.",
            "Scheduled supply treats every A2 candidate as officer-confirmed.",
            "Need weights use Census 2011 shares (E2); groups without a ward use the median.",
            "Km are straight-line x road factor plus an in-section access distance, not roads.",
        ],
    }
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    artifacts = {
        RESULTS: stream.getvalue().encode(),
        SUMMARY: (json.dumps(document, indent=2, sort_keys=True) + "\n").encode(),
    }
    checks = {
        "capacities": capacities,
        "inputs_sha256": {p: _sha(root / p) for p in INPUTS},
        "outputs_sha256": {p: hashlib.sha256(c).hexdigest() for p, c in artifacts.items()},
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seeds", type=int, default=None)
    args = parser.parse_args()
    for name, content in build(workers=args.workers, seeds=args.seeds).items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("A8 sandbox results built (SIMULATION).")
