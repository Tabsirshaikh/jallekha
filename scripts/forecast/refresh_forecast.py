"""One-command F5/F6 monthly refresh (fetch latest portal, train, rewrite all artifacts).

Usage: python scripts/forecast/refresh_forecast.py [--offline]
Offline repeats a build from committed raw files without network access.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import math
import os
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("OMP_NUM_THREADS", "1")

from app.config.forecast import FORECAST_CONFIG as CFG  # noqa: E402
from app.services import forecast as fc  # noqa: E402
from app.services import forecast_refresh as refresh  # noqa: E402
from app.services import hmwssb, shortage  # noqa: E402


def write(name, rows):
    path = ROOT / "data/derived" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(dict.fromkeys(k for r in rows for k in r)), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def source_signals():
    gw = fc.section_groundwater()
    by_month = defaultdict(list)
    for series in gw.values():
        for month, value in series.items():
            by_month[month].append(value)
    signals = {"ridge_groundwater": {m: statistics.median(v) for m, v in by_month.items()}}
    storage = defaultdict(list)
    targets = ("NAGARJUNA", "SINGUR", "YELLAMPALLY", "AKKAMPALL", "SRISAILAM")
    reservoir_rows = []
    for path in sorted((ROOT / "data/raw/reservoirs").glob("*.csv")):
        for row in csv.DictReader(path.open(encoding="utf-8-sig", newline="")):
            name = row.get("reservior_name", "")
            if not any(t in name.upper() for t in targets):
                continue
            try:
                capacity, gross = float(row["capacity"]), float(row["gross_storage"])
                if capacity <= 0 or gross < 0:
                    continue
                month = tuple(map(int, row["time"][:7].split("-")))
                storage[(month, name)].append((gross, capacity))
            except (ValueError, KeyError):
                continue
    monthly = defaultdict(list)
    for (month, name), values in sorted(storage.items()):
        gross = statistics.mean(v[0] for v in values)
        capacity = statistics.mean(v[1] for v in values)
        monthly[month].append(gross / capacity)
        reservoir_rows.append(
            {
                "month": f"{month[0]}-{month[1]:02d}",
                "reservoir": name,
                "gross_storage_tmc": gross,
                "capacity_tmc": capacity,
                "storage_share": gross / capacity,
                "days_observed": len(values),
                "basis": (
                    "DERIVED: monthly mean of REAL daily Telangana I&CAD storage; "
                    "context, not allocation or risk rule"
                ),
            }
        )
    signals["ridge_reservoir"] = {m: statistics.mean(v) for m, v in monthly.items()}
    if reservoir_rows:
        write("reservoir_monthly.csv", reservoir_rows)
    return signals, reservoir_rows


def build_shortage(table, matches, reservoirs):
    origin = table[0]["updated_through"]
    lookup = {r["section"]: r for r in matches}
    caps = shortage.load_capacity(ROOT)
    transferred_caps = {
        r["section"]: shortage.SectionCapacity(
            r["section"],
            caps[r["old_section"]].trips_per_day,
            caps[r["old_section"]].basis + "; conservative recut name transfer",
        )
        for r in matches
        if r["old_section"] in caps
    }
    groundwater = shortage.load_groundwater(
        ROOT / "data/derived/groundwater/section_anomaly.csv", origin
    )
    groundwater = {
        r["section"]: groundwater[r["old_section"]]
        for r in matches
        if r["old_section"] in groundwater
    }
    risk_rows = shortage.risk_list(
        [
            {k: str(v) if v is not None else "" for k, v in r.items()}
            for r in table
            if r["point"] is not None
        ],
        transferred_caps,
        origin,
        groundwater=groundwater or None,
    )
    risk_output = []
    latest_res = max((r["month"] for r in reservoirs), default="")
    reservoir_context = "; reservoir context unavailable"
    if latest_res:
        shown = [r for r in reservoirs if r["month"] == latest_res]
        reservoir_context = (
            f"; reservoir storage ({latest_res}): "
            + ", ".join(f"{r['reservoir']} {r['storage_share']:.0%} full" for r in shown)
            + " (context only)"
        )
    for r in risk_rows:
        risk_output.append(
            {
                "section": r.section,
                "section_basis": "current section; " + lookup[r.section]["basis"],
                "month": r.month,
                "months_ahead": r.months_ahead,
                "forecast_bookings": round(r.forecast_bookings, 1),
                "forecast_bookings_basis": r.forecast_basis,
                "upper_80": round(r.upper_80, 1) if r.upper_80 is not None else None,
                "upper_80_basis": r.upper_80_basis,
                "capacity_trips": round(r.capacity_trips, 1)
                if r.capacity_trips is not None
                else None,
                "capacity_trips_basis": r.capacity_basis,
                "capacity_ratio": r.capacity_ratio,
                "capacity_ratio_basis": "DERIVED: forecast/capacity"
                if r.capacity_ratio
                else "UNAVAILABLE",
                "risk": r.risk,
                "risk_basis": "DERIVED: unchanged configured capacity rule",
                "reason": r.reason + reservoir_context,
                "reason_basis": (
                    "DERIVED: row values; contextual groundwater and reservoir do not change risk"
                ),
                "groundwater_status": r.groundwater_status,
                "groundwater_status_basis": "DERIVED: transferred historical point context"
                if r.groundwater_m is not None
                else "UNAVAILABLE",
                "groundwater_m": r.groundwater_m,
                "groundwater_m_basis": "DERIVED: nearby well anomaly"
                if r.groundwater_m is not None
                else "UNAVAILABLE",
                "reservoir_status": "DERIVED" if latest_res else "UNAVAILABLE",
                "reservoir_status_basis": "DERIVED: REAL reservoir observations; context only"
                if latest_res
                else "UNAVAILABLE",
                "label": "DERIVED forecast vs ASSUMED capacity",
            }
        )
    for row in table:
        if (
            row["level"] == "section"
            and row["point"] is None
            and row["month"] in {shortage._add_months(origin, k) for k in (1, 2, 3)}
        ):
            empty = {k: None for k in risk_output[0]} if risk_output else {}
            empty.update(
                {
                    "section": row["section"],
                    "section_basis": "current section; UNAVAILABLE: no unique match",
                    "month": row["month"],
                    "months_ahead": next(
                        k for k in (1, 2, 3) if shortage._add_months(origin, k) == row["month"]
                    ),
                    "forecast_bookings": None,
                    "forecast_bookings_basis": row["point_basis"],
                    "upper_80_basis": "UNAVAILABLE",
                    "capacity_trips_basis": "UNAVAILABLE: no unique history match",
                    "capacity_ratio_basis": "UNAVAILABLE",
                    "risk": "unknown",
                    "risk_basis": "UNAVAILABLE: forecast history unmatched",
                    "reason": (
                        "Booking forecast unavailable: no unique historical section match; "
                        "capacity unknown; groundwater unavailable"
                    )
                    + reservoir_context,
                    "reason_basis": "UNAVAILABLE: uncertain section match; reservoir context only",
                    "groundwater_status": "UNAVAILABLE",
                    "groundwater_status_basis": "UNAVAILABLE",
                    "groundwater_m_basis": "UNAVAILABLE",
                    "reservoir_status": "DERIVED" if latest_res else "UNAVAILABLE",
                    "reservoir_status_basis": "DERIVED: observed storage, context only"
                    if latest_res
                    else "UNAVAILABLE",
                    "label": "DERIVED forecast vs ASSUMED capacity",
                }
            )
            risk_output.append(empty)
    risk_output.sort(key=lambda r: (r["section"], r["month"]))
    return risk_output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    if not args.offline:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/data/fetch_hmwssb_portal.py"), "--new-only"],
            check=True,
        )
        subprocess.run([sys.executable, str(ROOT / "scripts/data/fetch_reservoirs.py")], check=True)
    raw = fc.load_panel(ROOT / "data/raw/hmwssb_tankers_portal")
    last = raw.months[-1]
    updated = f"{last[0]}-{last[1]:02d}"
    records = hmwssb.read_rows(ROOT / "data/raw/hmwssb_tankers_portal")
    old, current = {}, {}
    for row in records:
        month = row["year"], row["month"]
        if month <= (2026, 1):
            old[row["section"]] = str(row["division"])
        if month == last:
            current[row["section"]] = str(row["division"])
    matches = refresh.match_sections(old, current)
    lookup = {r["section"]: r for r in matches}
    points = {
        r["section"]: r
        for r in csv.DictReader(
            (ROOT / "data/derived/crosswalk/section_to_ward_2016.csv").open(encoding="utf-8")
        )
    }
    for row in matches:
        point = points.get(row["old_section"], {})
        row.update(
            {
                "lat": point.get("lat", ""),
                "lng": point.get("lng", ""),
                "point_basis": (
                    "DERIVED_APPROXIMATE: old section geocoded point; current extent unverified"
                )
                if point.get("lat")
                else "UNAVAILABLE: no historical section point",
            }
        )
    write("forecast_section_crosswalk.csv", matches)
    matched = refresh.matched_panel(raw, matches)
    signals, reservoirs = source_signals()
    names = tuple(fc.MODELS) + refresh.NEW_MODELS
    backtest, predicted = [], {}

    def predict(train, target, name):
        city_train = (
            raw.until(fc.shift(train.months[-1], 1)) if train.months else fc.Panel(raw.column, {})
        )
        base = fc.seasonal_naive(train, target)
        city_base = refresh.city_predict(city_train, target, "seasonal_naive")
        if name in fc.MODELS:
            section = fc.MODELS[name](train, target)
            if section is None or base is None or city_base is None:
                return None
            ratio = sum(section.values()) / sum(base.values()) if sum(base.values()) else 1
            return city_base * ratio, section
        city = refresh.city_predict(city_train, target, name, signals)
        if city is None or base is None:
            return None
        ratio = city / city_base if city_base else 1
        return city, {s: v * ratio for s, v in base.items()}

    for name in names:
        for origin in raw.months:
            result = predict(matched.until(origin), origin, name)
            if result is None:
                continue
            city, section = result
            actual_city = sum(raw.values[origin].values())
            known = set(matched.values[origin]) & set(section)
            score = fc.score(
                {s: matched.values[origin][s] for s in known}, {s: section[s] for s in known}
            )
            if actual_city == 0:
                continue
            backtest.append(
                fc.BacktestRow(
                    name,
                    origin,
                    actual_city,
                    city,
                    abs(actual_city - city) / actual_city * 100,
                    score.abs_error,
                    score.actual_sum,
                    score.section_months,
                )
            )
            predicted[name, origin] = section
        print(f"Scored {name}", flush=True)
    # Extend complexity only for this explicit fixed-candidate refresh run.
    original = fc.COMPLEXITY
    fc.COMPLEXITY = ("seasonal_naive", "naive_x_growth", *refresh.NEW_MODELS, *original[2:])
    selection = fc.select(
        backtest, fc.yoy_months(raw), {m: fc.yoy_months(raw.until(m)) for m in raw.months}
    )
    fc.COMPLEXITY = original
    selected = selection.model
    rows = []
    for r in backtest:
        rows.append(
            {
                "run": "refresh",
                "row_type": "origin",
                "model": r.model,
                "origin": f"{r.origin[0]}-{r.origin[1]:02d}",
                "months": 1,
                "section_months": r.section_months,
                "city_mape": r.city_ape,
                "city_mape_basis": "DERIVED: exact city totals; ex-ante rolling origin",
                "section_wape": r.abs_error / r.actual_sum * 100 if r.actual_sum else None,
                "section_wape_basis": "DERIVED_APPROXIMATE: matched histories; unmatched excluded",
            }
        )
    for t in selection.tests:
        rows.append(
            {
                "run": "refresh",
                "row_type": "selection_test",
                "model": t.model,
                "months": selection.origins,
                "city_mape": t.city_mape,
                "section_wape": t.section_wape,
                "city_mape_basis": "DERIVED: shared origins >=12 prior year-on-year months",
                "section_wape_basis": "DERIVED_APPROXIMATE: same matched section cohort",
                "note": (
                    f"naive {t.baseline_city_mape:.4f}/{t.baseline_section_wape:.4f}; "
                    f"HLN DM one-sided p {t.p_value:.6f}; "
                    f"{'passes' if t.passed else 'fails'}"
                ),
            }
        )
    _, city_coverage = refresh.city_intervals(backtest, selected)
    rows.extend(city_coverage)
    rows.append(
        {
            "run": "refresh",
            "row_type": "selected",
            "model": selected,
            "months": selection.origins,
            "note": selection.reason,
        }
    )
    s2 = fc.baseline(fc.load_panel(ROOT / "data/raw/hmwssb_tankers"))
    rows.append(
        {
            "run": "s2_2022-01_2024-02",
            "row_type": "summary_all_origins",
            "model": "seasonal_naive",
            "months": len(s2.scored_months),
            "city_mape": s2.city_mape,
            "section_wape": s2.section_wape,
            "city_mape_basis": "DERIVED: unchanged confirmed S2 reproduction",
            "section_wape_basis": "DERIVED: unchanged confirmed S2 reproduction",
        }
    )
    write("forecast_backtest.csv", rows)
    # Section residual widths are calibrated on the same selected model's past predictions.
    errors = defaultdict(list)
    for (name, origin), forecast in predicted.items():
        if name == selected:
            for section, value in forecast.items():
                if section not in matched.values[origin]:
                    continue
                errors[section].append(abs(matched.values[origin].get(section, 0) - value))
    caps = shortage.load_capacity(ROOT)
    transferred_caps = {
        r["section"]: shortage.SectionCapacity(
            r["section"],
            caps[r["old_section"]].trips_per_day,
            caps[r["old_section"]].basis + "; conservative recut name transfer",
        )
        for r in matches
        if r["old_section"] in caps
    }
    table = []
    city_widths, _ = refresh.city_intervals(backtest, selected)
    for h in range(1, CFG.horizon_months + 1):
        month = fc.shift(last, h)
        label = f"{month[0]}-{month[1]:02d}"
        result = predict(matched, month, selected)
        city, sections = result if result else (None, {})
        city_row = {
            "level": "city",
            "section": "",
            "month": label,
            "model": selected,
            "point": city,
            "point_basis": (
                "DERIVED: exact city totals with selected ex-ante candidate; "
                "independent of recut placement"
            ),
            "updated_through": updated,
            "match_status": "exact",
            "capacity_trips": CFG.fleet_tankers_2026
            * CFG.trips_per_tanker_per_day
            * calendar.monthrange(*month)[1],
            "capacity_trips_basis": "DERIVED: configured fleet x daily trips x days",
        }
        for level, width in city_widths.items():
            pct = int(level * 100)
            known = city is not None and math.isfinite(width)
            city_row.update(
                {
                    f"lower_{pct}": max(0, city - width) if known else None,
                    f"upper_{pct}": city + width if known else None,
                    f"lower_{pct}_basis": (
                        "DERIVED: city residual conformal width; one-step coverage not "
                        "a 12-month guarantee"
                    )
                    if known
                    else "UNAVAILABLE",
                    f"upper_{pct}_basis": (
                        "DERIVED: city residual conformal width; one-step coverage not "
                        "a 12-month guarantee"
                    )
                    if known
                    else "UNAVAILABLE",
                }
            )
        table.append(city_row)
        for section, match in lookup.items():
            point = sections.get(section)
            cap = transferred_caps.get(section)
            row = {
                "level": "section",
                "section": section,
                "month": label,
                "model": selected,
                "point": point,
                "point_basis": (
                    "DERIVED_APPROXIMATE: one-to-one name-matched historical "
                    "section; boundary equivalence unverified"
                )
                if point is not None
                else "UNAVAILABLE: no unique historical match or seasonal lag",
                "updated_through": updated,
                "match_status": match["match_status"],
                "capacity_trips": cap.trips_per_day * calendar.monthrange(*month)[1]
                if cap
                else None,
                "capacity_trips_basis": cap.basis
                if cap
                else "UNAVAILABLE: no uniquely matched capacity",
            }
            for level in CFG.interval_levels:
                pct = int(level * 100)
                width = fc.conformal_quantile(errors[section], level)
                known = point is not None and math.isfinite(width)
                row.update(
                    {
                        f"lower_{pct}": max(0, point - width) if known else None,
                        f"upper_{pct}": point + width if known else None,
                        f"lower_{pct}_basis": "DERIVED_APPROXIMATE: section conformal residuals"
                        if known
                        else "UNAVAILABLE: insufficient residuals or history",
                        f"upper_{pct}_basis": "DERIVED_APPROXIMATE: section conformal residuals"
                        if known
                        else "UNAVAILABLE: insufficient residuals or history",
                    }
                )
            table.append(row)
    write("forecast_table.csv", table)
    write(
        "forecast_capacity.csv",
        [
            {
                "month": r["month"],
                "trips_needed": r["point"],
                "trips_needed_basis": r["point_basis"],
                "capacity_trips": r["capacity_trips"],
                "capacity_basis": r["capacity_trips_basis"],
                "shortfall_trips": max(0, r["point"] - r["capacity_trips"])
                if r["point"] is not None
                else None,
                "fleet_basis": "ASSUMED: configured 1123 tanker fleet",
            }
            for r in table
            if r["level"] == "city"
        ],
    )
    history, accuracy = [], []
    for month in raw.months[-12:]:
        label = f"{month[0]}-{month[1]:02d}"
        history.append(
            {
                "month": label,
                "level": "city",
                "section": "",
                "actual": sum(raw.values[month].values()),
                "actual_basis": "REAL: sum of all portal section bookings",
            }
        )
        for section, value in matched.values[month].items():
            history.append(
                {
                    "month": label,
                    "level": "section",
                    "section": section,
                    "actual": value,
                    "actual_basis": (
                        "DERIVED_APPROXIMATE: historical correspondence; current "
                        "published counts REAL"
                    ),
                }
            )
    for r in backtest:
        if r.model != selected or r.origin < fc.shift(last, -11):
            continue
        label = f"{r.origin[0]}-{r.origin[1]:02d}"
        capacity = (
            CFG.fleet_tankers_2026
            * CFG.trips_per_tanker_per_day
            * calendar.monthrange(*r.origin)[1]
        )
        accuracy.append(
            {
                "month": label,
                "level": "city",
                "section": "",
                "point": r.city_forecast,
                "actual": r.city_actual,
                "error_pct": (r.city_forecast - r.city_actual) / r.city_actual * 100,
                "capacity_trips": capacity,
                "point_basis": (
                    "DERIVED: retrospective rolling-origin estimate; not a "
                    "previously issued forecast"
                ),
                "actual_basis": "REAL: portal city total",
                "error_pct_basis": "DERIVED: signed forecast error / actual",
                "capacity_trips_basis": "DERIVED: current fleet assumption applied to month",
            }
        )
        for section, point in predicted[selected, r.origin].items():
            if section not in matched.values[r.origin]:
                continue
            actual = matched.values[r.origin].get(section, 0)
            accuracy.append(
                {
                    "month": label,
                    "level": "section",
                    "section": section,
                    "point": point,
                    "actual": actual,
                    "error_pct": (point - actual) / actual * 100 if actual else None,
                    "capacity_trips": None,
                    "point_basis": (
                        "DERIVED_APPROXIMATE: retrospective matched-history rolling estimate"
                    ),
                    "actual_basis": "DERIVED_APPROXIMATE: name correspondence",
                    "error_pct_basis": "DERIVED: signed relative error"
                    if actual
                    else "UNAVAILABLE: zero actual",
                    "capacity_trips_basis": "UNAVAILABLE",
                }
            )
    write("forecast_history.csv", history)
    write("forecast_accuracy.csv", accuracy)
    write("shortage_risk.csv", build_shortage(table, matches, reservoirs))
    report = {
        "updated_through": updated,
        "selected_model": selected,
        "selection_origins": selection.origins,
        "section_matches": dict(
            (s, sum(r["match_status"] == s for r in matches))
            for s in ("exact", "approximate", "unmatched")
        ),
        "selection_tests": [
            {
                "model": t.model,
                "city_mape": t.city_mape,
                "section_wape": t.section_wape,
                "baseline_city_mape": t.baseline_city_mape,
                "baseline_section_wape": t.baseline_section_wape,
                "p_value": t.p_value,
                "passed": t.passed,
            }
            for t in selection.tests
        ],
        "city_coverage": city_coverage,
        "basis": (
            "DERIVED: refreshed rolling-origin evaluation; matched section "
            "boundary equivalence unverified"
        ),
    }
    holdout_path = ROOT / "data/derived/forecast_2026_holdout.csv"
    if holdout_path.exists():
        holdout = list(csv.DictReader(holdout_path.open(encoding="utf-8", newline="")))
        report["frozen_2026_holdout"] = {
            "months": len(holdout),
            "previous_model_city_mape": statistics.mean(float(r["previous_ape"]) for r in holdout),
            "seasonal_naive_city_mape": statistics.mean(float(r["naive_ape"]) for r in holdout),
            "basis": "DERIVED: archived forecast through Jan 2026 versus exact Feb-Aug city totals",
        }
    (ROOT / "data/verification/forecast_refresh.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
