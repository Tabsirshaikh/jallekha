"""Monthly booking forecast and backtest (F5, T2). Pure functions; no LLM, no new libraries.

Data: HMWSSB monthly bookings per section (S2 `data/raw/hmwssb_tankers`, read with P2's
`hmwssb.read_rows`). A month whose file has no rows (Dec 2022) is **missing**, never zero.

Baseline protocol (recovered by reproduction on 2026-10-03; `config/forecast.py`): seasonal
naive (same month one year earlier) on `noofbookings`; a month is scored only if the month
12 earlier is present; all sections present in either month, a missing section value = 0;
city MAPE = mean of monthly absolute percentage errors of city totals; section WAPE = sum of
absolute errors / sum of actuals, pooled over all section-months.

Models: (a) seasonal naive; (b) seasonal naive x year-on-year growth. A global gradient-
boosting model needs scikit-learn or lightgbm, which `tasks.py setup` does not install, so it
is listed in NOT_RUN. Weather (D8) and groundwater (D7) are not in the repo; covariates can be
added later through `ForecastConfig.covariates` and a model that reads them.

Every model receives only training data strictly before its target month (it refuses
otherwise), so the rolling-origin backtest cannot leak.
"""

from __future__ import annotations

import calendar
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.config.forecast import FORECAST_CONFIG, ForecastConfig
from app.services import hmwssb

Month = tuple[int, int]
SectionValues = dict[str, float]

NOT_RUN: dict[str, str] = {
    "global_gbm": (
        "not run: needs scikit-learn or lightgbm, not installed by tasks.py setup "
        "(lightgbm is in the optional ml extra); decision pending"
    ),
    "chronos_2": "not run: owner decision pending (no-LLM rule)",
}
DERIVED_COLUMNS = frozenset(
    {
        "city_mape",
        "section_wape",
        "coverage",
        "point",
        "lower_80",
        "upper_80",
        "lower_90",
        "upper_90",
    }
)


def shift(month: Month, k: int) -> Month:
    index = month[0] * 12 + (month[1] - 1) + k
    return index // 12, index % 12 + 1


# --- data --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Panel:
    """Values per present month and section. Months without rows are absent (missing)."""

    column: str
    values: Mapping[Month, Mapping[str, float]]

    @property
    def months(self) -> tuple[Month, ...]:
        return tuple(sorted(self.values))

    def sections(self) -> set[str]:
        return {s for secs in self.values.values() for s in secs}

    def until(self, origin: Month) -> Panel:
        """Training data: months strictly before `origin`."""
        return Panel(self.column, {m: v for m, v in self.values.items() if m < origin})


def load_panel(data_dir: Path, column: str = "noofbookings", through: Month | None = None) -> Panel:
    key = {"noofbookings": "bookings", "delivered": "delivered"}[column]
    values: dict[Month, dict[str, float]] = {}
    for row in hmwssb.read_rows(Path(data_dir)):
        month = (row["year"], row["month"])
        if through is not None and month > through:
            continue
        values.setdefault(month, {})[row["section"]] = float(row[key])
    return Panel(column, values)


def section_changes(panel: Panel) -> dict[int, dict[str, int]]:
    """Sections appearing or disappearing from one calendar year to the next."""
    by_year: dict[int, set[str]] = {}
    for (year, _), secs in panel.values.items():
        by_year.setdefault(year, set()).update(secs)
    years = sorted(by_year)
    return {
        y: {
            "sections": len(by_year[y]),
            "appeared": len(by_year[y] - by_year[p]),
            "disappeared": len(by_year[p] - by_year[y]),
        }
        for p, y in zip(years, years[1:], strict=False)
    }


# --- scoring -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Score:
    city_actual: float
    city_forecast: float
    abs_error: float
    actual_sum: float
    section_months: int


def score(actual: Mapping[str, float], forecast: Mapping[str, float]) -> Score:
    """All sections present in either; a missing value counts as 0."""
    keys = set(actual) | set(forecast)
    city_a = sum(actual.get(s, 0.0) for s in keys)
    city_f = reconcile({s: forecast.get(s, 0.0) for s in keys})
    abs_error = sum(abs(actual.get(s, 0.0) - forecast.get(s, 0.0)) for s in keys)
    return Score(city_a, city_f, abs_error, city_a, len(keys))


@dataclass(frozen=True)
class BaselineResult:
    city_mape: float
    section_wape: float
    scored_months: tuple[Month, ...]
    section_months: int


def baseline(panel: Panel) -> BaselineResult:
    """The confirmed protocol, computed directly on the whole panel."""
    present = set(panel.months)
    apes: list[float] = []
    abs_error = actual = 0.0
    scored: list[Month] = []
    section_months = 0
    for month in panel.months:
        before = shift(month, -FORECAST_CONFIG.seasonal_period_months)
        if before not in present:
            continue
        s = score(panel.values[month], panel.values[before])
        if s.city_actual == 0:
            continue
        scored.append(month)
        apes.append(abs(s.city_actual - s.city_forecast) / s.city_actual * 100)
        abs_error += s.abs_error
        actual += s.actual_sum
        section_months += s.section_months
    return BaselineResult(
        sum(apes) / len(apes), abs_error / actual * 100, tuple(scored), section_months
    )


# --- models ------------------------------------------------------------------------------


def _check(train: Panel, target: Month) -> None:
    if any(m >= target for m in train.values):
        raise ValueError(f"Training data must end before the target {target} (no leak)")


def seasonal_naive(train: Panel, target: Month) -> SectionValues | None:
    """Same month one year earlier; None when that month is missing."""
    _check(train, target)
    before = shift(target, -FORECAST_CONFIG.seasonal_period_months)
    if before not in train.values:
        return None
    return dict(train.values[before])


def _growth(train: Panel, target: Month, window: int) -> float | None:
    period = FORECAST_CONFIG.seasonal_period_months
    months: list[Month] = []
    for month in sorted(train.values, reverse=True):
        if shift(month, -period) in train.values:
            months.append(month)
        if len(months) == window:
            break
    if len(months) < window:
        return None
    now = sum(sum(train.values[m].values()) for m in months)
    before = sum(sum(train.values[shift(m, -period)].values()) for m in months)
    return now / before if before > 0 else None


def naive_x_growth(train: Panel, target: Month) -> SectionValues | None:
    """Seasonal naive x the city's year-on-year growth over the most recent months."""
    base = seasonal_naive(train, target)
    if base is None:
        return None
    growth = _growth(train, target, FORECAST_CONFIG.growth_window_months)
    if growth is None:
        return None
    return {s: v * growth for s, v in base.items()}


Model = Callable[[Panel, Month], SectionValues | None]
MODELS: dict[str, Model] = {"seasonal_naive": seasonal_naive, "naive_x_growth": naive_x_growth}


def reconcile(section_forecasts: Mapping[str, float]) -> float:
    """Bottom-up: the city forecast is the sum of the section forecasts."""
    return float(sum(section_forecasts.values()))


# --- rolling-origin backtest -------------------------------------------------------------


@dataclass(frozen=True)
class BacktestRow:
    model: str
    origin: Month  # forecast month; training uses months strictly before it
    city_actual: float
    city_forecast: float
    city_ape: float
    abs_error: float
    actual_sum: float
    section_months: int


def backtest(panel: Panel, models: Iterable[str] = tuple(MODELS)) -> list[BacktestRow]:
    rows: list[BacktestRow] = []
    for name in models:
        model = MODELS[name]
        for origin in panel.months:
            forecast = model(panel.until(origin), origin)
            if forecast is None:
                continue
            s = score(panel.values[origin], forecast)
            if s.city_actual == 0:
                continue
            rows.append(
                BacktestRow(
                    name,
                    origin,
                    s.city_actual,
                    s.city_forecast,
                    abs(s.city_actual - s.city_forecast) / s.city_actual * 100,
                    s.abs_error,
                    s.actual_sum,
                    s.section_months,
                )
            )
    return rows


@dataclass(frozen=True)
class Summary:
    city_mape: float
    section_wape: float
    origins: int
    section_months: int


def summarise(rows: Iterable[BacktestRow], origins: set[Month] | None = None) -> dict[str, Summary]:
    grouped: dict[str, list[BacktestRow]] = {}
    for row in rows:
        if origins is None or row.origin in origins:
            grouped.setdefault(row.model, []).append(row)
    return {
        name: Summary(
            sum(r.city_ape for r in rs) / len(rs),
            sum(r.abs_error for r in rs) / sum(r.actual_sum for r in rs) * 100,
            len(rs),
            sum(r.section_months for r in rs),
        )
        for name, rs in grouped.items()
    }


def common_origins(rows: Sequence[BacktestRow]) -> set[Month]:
    by_model: dict[str, set[Month]] = {}
    for row in rows:
        by_model.setdefault(row.model, set()).add(row.origin)
    sets = list(by_model.values())
    return set.intersection(*sets) if sets else set()


def select_model(runs: Sequence[Mapping[str, Summary]]) -> str:
    """A model is used only if it beats seasonal naive on both city MAPE and section WAPE in
    every run given; otherwise the baseline."""
    names = set.intersection(*(set(run) for run in runs)) - {"seasonal_naive"}
    winners = [
        n
        for n in sorted(names)
        if all(
            run[n].city_mape < run["seasonal_naive"].city_mape
            and run[n].section_wape < run["seasonal_naive"].section_wape
            for run in runs
        )
    ]
    if not winners:
        return "seasonal_naive"
    return min(winners, key=lambda n: runs[0][n].section_wape)


# --- split-conformal intervals -----------------------------------------------------------


def conformal_quantile(scores: Sequence[float], level: float) -> float:
    """Finite-sample split-conformal quantile: the ceil((n+1) level)-th smallest score."""
    n = len(scores)
    k = math.ceil((n + 1) * level)
    if n == 0 or k > n:
        return math.inf
    return sorted(scores)[k - 1]


def coverage(actuals: Sequence[float], lowers: Sequence[float], uppers: Sequence[float]) -> float:
    inside = sum(lo <= a <= up for a, lo, up in zip(actuals, lowers, uppers, strict=True))
    return inside / len(actuals)


@dataclass(frozen=True)
class Point:
    origin: Month
    section: str
    actual: float
    forecast: float


def _points(panel: Panel, model_name: str) -> list[Point]:
    model = MODELS[model_name]
    points: list[Point] = []
    for origin in panel.months:
        forecast = model(panel.until(origin), origin)
        if forecast is None:
            continue
        actual = panel.values[origin]
        for s in set(actual) | set(forecast):
            points.append(Point(origin, s, actual.get(s, 0.0), forecast.get(s, 0.0)))
    return points


def _scales(points: Sequence[Point]) -> dict[str, float]:
    """Each section's mean absolute error; zero or unknown -> the median positive scale."""
    errors: dict[str, list[float]] = {}
    for p in points:
        errors.setdefault(p.section, []).append(abs(p.actual - p.forecast))
    scales = {s: sum(e) / len(e) for s, e in errors.items()}
    positive = sorted(v for v in scales.values() if v > 0)
    fallback = positive[len(positive) // 2] if positive else 1.0
    return {s: (v if v > 0 else fallback) for s, v in scales.items()} | {"__fallback__": fallback}


@dataclass(frozen=True)
class ConformalResult:
    level: float
    status: str  # ok | insufficient
    coverage: float | None
    quantile: float | None
    n_calibration_months: int
    n_test_months: int
    n_test_points: int
    reason: str | None = None


def conformal_backtest(
    panel: Panel, model_name: str, config: ForecastConfig = FORECAST_CONFIG
) -> list[ConformalResult]:
    """Calibrate on the first half of the scored months, measure coverage on the rest.
    Scores are absolute errors scaled by each section's calibration error, pooled."""
    points = _points(panel, model_name)
    months = sorted({p.origin for p in points})
    n_cal = len(months) // 2
    cal_months, test_months = set(months[:n_cal]), set(months[n_cal:])
    out: list[ConformalResult] = []
    if n_cal < config.min_calibration_months or len(test_months) < config.min_test_months:
        reason = (
            f"{len(months)} scored months give {n_cal} calibration and {len(test_months)} "
            f"test months; at least {config.min_calibration_months} and "
            f"{config.min_test_months} are needed"
        )
        return [
            ConformalResult(level, "insufficient", None, None, n_cal, len(test_months), 0, reason)
            for level in config.interval_levels
        ]
    cal = [p for p in points if p.origin in cal_months]
    test = [p for p in points if p.origin in test_months]
    scales = _scales(cal)
    scale = lambda s: scales.get(s, scales["__fallback__"])  # noqa: E731
    scores = [abs(p.actual - p.forecast) / scale(p.section) for p in cal]
    for level in config.interval_levels:
        q = conformal_quantile(scores, level)
        lowers = [max(0.0, p.forecast - q * scale(p.section)) for p in test]
        uppers = [p.forecast + q * scale(p.section) for p in test]
        out.append(
            ConformalResult(
                level,
                "ok",
                coverage([p.actual for p in test], lowers, uppers),
                q,
                n_cal,
                len(test_months),
                len(test),
            )
        )
    return out


# --- forecast table ----------------------------------------------------------------------


def forecast_table(
    panel: Panel, model_name: str, horizon: int, config: ForecastConfig = FORECAST_CONFIG
) -> list[dict[str, object]]:
    """Section and city rows for the `horizon` months after the panel's last month.

    Section intervals: split-conformal, calibrated on every scored backtest point. City rows
    are the sum of section points (bottom-up); section intervals do not add up to a city
    interval, so the city has none.
    """
    model = MODELS[model_name]
    points = _points(panel, model_name)
    scales = _scales(points)
    scores = [
        abs(p.actual - p.forecast) / scales.get(p.section, scales["__fallback__"]) for p in points
    ]
    quantiles = {level: conformal_quantile(scores, level) for level in config.interval_levels}
    last = panel.months[-1]
    basis = f"DERIVED: {model_name} on {panel.column} through {last[0]}-{last[1]:02d}"
    interval_basis = (
        f"DERIVED: split-conformal, section-scaled pooled residuals of the {model_name} backtest"
    )
    rows: list[dict[str, object]] = []
    for h in range(1, horizon + 1):
        month = shift(last, h)
        forecast = model(panel, month)
        label = f"{month[0]}-{month[1]:02d}"
        if forecast is None:
            rows.append(
                {"level": "city", "section": "", "month": label, "model": model_name,
                 "point": None, "point_basis": "UNAVAILABLE: no value a year earlier"}
            )  # fmt: skip
            continue
        for section in sorted(forecast):
            s = scales.get(section, scales["__fallback__"])
            row: dict[str, object] = {
                "level": "section", "section": section, "month": label, "model": model_name,
                "point": forecast[section], "point_basis": basis,
            }  # fmt: skip
            for level, q in quantiles.items():
                pct = int(round(level * 100))
                row[f"lower_{pct}"] = max(0.0, forecast[section] - q * s)
                row[f"upper_{pct}"] = forecast[section] + q * s
                row[f"lower_{pct}_basis"] = interval_basis
                row[f"upper_{pct}_basis"] = interval_basis
            rows.append(row)
        city: dict[str, object] = {
            "level": "city", "section": "", "month": label, "model": model_name,
            "point": reconcile(forecast), "point_basis": "DERIVED: sum of section points",
        }  # fmt: skip
        for level in quantiles:
            pct = int(round(level * 100))
            for side in ("lower", "upper"):
                city[f"{side}_{pct}"] = None
                city[f"{side}_{pct}_basis"] = "UNAVAILABLE: section intervals do not add up"
        rows.append(city)
    return rows


# --- capacity planner --------------------------------------------------------------------


@dataclass(frozen=True)
class CapacityRow:
    month: Month
    trips_needed: float
    capacity_trips: float
    shortfall_trips: float
    trips_needed_basis: str
    capacity_basis: str
    fleet_basis: str = field(default="ASSUMED: config/forecast.py fleet (D17, news)")


def capacity_plan(
    city_forecast: Mapping[Month, float],
    fleet: int,
    trips_per_tanker_per_day: float | None,
) -> list[CapacityRow]:
    """Trips needed (one booking = one trip) versus fleet x trips per tanker per day x days.
    Trips per day has no source: it must be given (OPEN), never defaulted."""
    if trips_per_tanker_per_day is None or trips_per_tanker_per_day <= 0:
        raise ValueError(
            "trips per tanker per day is required (OPEN, owner to confirm: no sourced value)"
        )
    rows = []
    for month in sorted(city_forecast):
        days = calendar.monthrange(*month)[1]
        capacity = fleet * trips_per_tanker_per_day * days
        needed = city_forecast[month]
        rows.append(
            CapacityRow(
                month,
                needed,
                capacity,
                max(0.0, needed - capacity),
                "DERIVED: forecast bookings, one trip per booking (ASSUMED)",
                f"DERIVED: fleet x {trips_per_tanker_per_day} trips per day (OPEN) x {days} days",
            )
        )
    return rows
