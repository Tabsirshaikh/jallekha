"""F5 refresh: exact city totals, conservative section identity and ex-ante candidates.

Name correspondence does not establish boundary equivalence: changed divisions and OLD/new
aliases are approximate. One historical section can feed at most one current section.
"""

from __future__ import annotations

import calendar
import math
import re
from collections.abc import Mapping, Sequence

from app.config.forecast import FORECAST_CONFIG
from app.services import forecast as fc

NEW_MODELS = (
    "seasonal_level12",
    "seasonal_level6",
    "recent_seasonal_ridge",
    "ridge_summer",
    "ridge_groundwater",
    "ridge_reservoir",
    "ridge_groundwater_reservoir",
)


def normal_name(name: str) -> str:
    return re.sub(
        r"\s+", " ", re.sub(r"\s*\((?:OLD|NEW|DIV\s*\d+|PD\s*\d+)\)\s*", "", name.upper())
    ).strip()


def matched_panel(panel: fc.Panel, matches: Sequence[Mapping[str, str]]) -> fc.Panel:
    """Current active identity, including transient NEW suffixes; absent identities stay absent."""
    months = {}
    for month, values in panel.values.items():
        observed = {}
        for match in matches:
            if not match["old_section"]:
                continue
            name = match["section"]
            aliases = [
                s
                for s in values
                if normal_name(s) == normal_name(name) and (month <= (2026, 1) or "(OLD)" not in s)
            ]
            if name in aliases:
                observed[name] = values[name]
            elif len(aliases) == 1:
                observed[name] = values[aliases[0]]
        months[month] = observed
    return fc.Panel(panel.column, months)


def match_sections(old: Mapping[str, str], new: Mapping[str, str]) -> list[dict[str, str]]:
    rows = []
    used: set[str] = set()
    # Prefer the active name to residual OLD rows; never reuse the same history.
    for section in sorted(new, key=lambda s: ("(OLD)" in s, s)):
        candidates = [s for s in old if normal_name(s) == normal_name(section) and s not in used]
        source = candidates[0] if len(candidates) == 1 else ""
        if source:
            used.add(source)
        exact = source == section and old.get(source) == new[section]
        residual = any(normal_name(s) == normal_name(section) and s != section for s in new)
        status = (
            "exact"
            if source and exact and not residual
            else "approximate"
            if source
            else "unmatched"
        )
        rows.append(
            {
                "section": section,
                "division": new[section],
                "old_section": source,
                "old_division": old.get(source, ""),
                "match_status": status,
                "basis": "DERIVED: conservative one-to-one name/division correspondence; "
                "boundary equivalence unverified"
                if source
                else "UNAVAILABLE: no unique unused historical name; no invented history",
            }
        )
    return rows


def city_panel(panel: fc.Panel) -> fc.Panel:
    return fc.Panel(panel.column, {m: {"city": sum(v.values())} for m, v in panel.values.items()})


def city_predict(
    train: fc.Panel,
    target: fc.Month,
    name: str,
    signals: Mapping[str, Mapping[fc.Month, float]] | None = None,
) -> float | None:
    fc._check(train, target)
    city = city_panel(train)
    base = fc.seasonal_naive(city, target)
    if base is None:
        return None
    if name == "seasonal_naive":
        return base["city"]
    if name == "naive_x_growth":
        prediction = fc.naive_x_growth(city, target)
        return prediction["city"] if prediction else None
    if name.startswith("seasonal_level"):
        window = int(name.removeprefix("seasonal_level"))
        paired = [m for m in city.months if fc.shift(m, -12) in city.values][-window:]
        if not paired:
            return None
        ratios = [
            city.values[m]["city"] / max(1, city.values[fc.shift(m, -12)]["city"]) for m in paired
        ]
        # Fixed robust level correction: median of available past year-on-year ratios.
        return base["city"] * sorted(ratios)[len(ratios) // 2]
    if name not in NEW_MODELS:
        return None
    from sklearn.linear_model import Ridge

    signals = signals or {}
    origin = fc.shift(city.months[-1], 1)

    def features(month: fc.Month, cutoff: fc.Month) -> list[float]:
        before = fc.shift(month, -12)
        lag = city.values[before]["city"]
        growth = fc._growth(city.until(cutoff), month, FORECAST_CONFIG.growth_window_months)
        row = [
            math.log1p(lag),
            math.log(max(growth or 1.0, 0.001)),
            *[float(month[1] == m) for m in range(1, 13)],
        ]
        if name == "ridge_summer":
            row.append(float(month[1] in (3, 4, 5, 6)) * row[1])
        contexts = (
            ("ridge_groundwater", "ridge_reservoir")
            if name == "ridge_groundwater_reservoir"
            else (name,)
            if name in ("ridge_groundwater", "ridge_reservoir")
            else ()
        )
        for context in contexts:
            series = signals.get(context, {})
            available = [m for m in series if m < cutoff]
            row.append(series[max(available)] if available else 0.0)
            row.append(float(bool(available)))
        return row

    months = [m for m in city.months if fc.shift(m, -12) in city.values]
    if len(months) < FORECAST_CONFIG.gbm_min_training_months:
        return None
    x = [features(m, m) for m in months]
    y = [math.log1p(city.values[m]["city"]) for m in months]
    # Fixed recency weighting, ASSUMED; no backtest-tuned hyperparameter search.
    weights = [0.5 ** ((origin[0] * 12 + origin[1] - m[0] * 12 - m[1]) / 12) for m in months]
    model = Ridge(alpha=FORECAST_CONFIG.refresh_ridge_alpha).fit(x, y, sample_weight=weights)
    return max(0.0, math.expm1(float(model.predict([features(target, origin)])[0])))


def city_intervals(
    rows: Sequence[fc.BacktestRow], model: str
) -> tuple[dict[float, float], list[dict[str, object]]]:
    points = sorted((r for r in rows if r.model == model), key=lambda r: r.origin)
    split = len(points) // 2
    test = points[split:]
    window = FORECAST_CONFIG.city_interval_window_months
    errors = [abs(r.city_actual - r.city_forecast) for r in points]
    widths = {
        level: fc.conformal_quantile(errors[-window:], level)
        for level in FORECAST_CONFIG.interval_levels
    }
    measured = []
    for level in widths:
        past_widths = [
            fc.conformal_quantile(errors[max(0, i - window) : i], level)
            for i in range(split, len(points))
        ]
        enough = (
            min(split, window) >= FORECAST_CONFIG.min_calibration_months
            and len(test) >= FORECAST_CONFIG.min_test_months
            and all(math.isfinite(q) for q in past_widths)
        )
        measured.append(
            {
                "run": "refresh",
                "row_type": "city_coverage",
                "model": model,
                "interval": level,
                "months": len(test),
                "section_months": len(test),
                "coverage": sum(e <= q for e, q in zip(errors[split:], past_widths, strict=True))
                / len(test)
                if enough
                else None,
                "coverage_basis": (
                    "DERIVED: preceding rolling city residuals only; later months measured"
                )
                if enough
                else "UNAVAILABLE: too few finite calibration/test months",
                "note": (
                    f"Previous {window} residuals; exploratory window choice; "
                    "one-step coverage, not a 12-step guarantee"
                ),
            }
        )
    return widths, measured


def city_forecast_rows(
    panel: fc.Panel, model: str, horizon: int, backtest: Sequence[fc.BacktestRow] = (), signals=None
) -> list[dict[str, object]]:
    last = panel.months[-1]
    widths, _ = city_intervals(backtest, model)
    rows = []
    for h in range(1, horizon + 1):
        month = fc.shift(last, h)
        point = city_predict(panel, month, model, signals)
        row = {
            "level": "city",
            "section": "",
            "month": f"{month[0]}-{month[1]:02d}",
            "model": model,
            "point": point,
            "point_basis": (
                "DERIVED: direct forecast of exact portal city totals; no section placement"
            ),
            "updated_through": f"{last[0]}-{last[1]:02d}",
            "match_status": "exact",
            "capacity_trips": FORECAST_CONFIG.fleet_tankers_2026
            * FORECAST_CONFIG.trips_per_tanker_per_day
            * calendar.monthrange(*month)[1],
            "capacity_trips_basis": "DERIVED: configured fleet x trips per day x calendar days",
        }
        for level, width in widths.items():
            pct = int(level * 100)
            known = point is not None and math.isfinite(width)
            row[f"lower_{pct}"] = max(0.0, point - width) if known else None
            row[f"upper_{pct}"] = point + width if known else None
            basis = (
                (
                    "DERIVED: city absolute-residual conformal calibration; "
                    "one-step residuals applied across horizon, coverage not guaranteed"
                )
                if known
                else "UNAVAILABLE: no finite city calibration"
            )
            row[f"lower_{pct}_basis"] = basis
            row[f"upper_{pct}_basis"] = basis
        rows.append(row)
    return rows
