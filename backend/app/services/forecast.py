"""Monthly booking forecast and backtest (F5, T2). Pure functions; no LLM, no new libraries.

Data: HMWSSB monthly bookings per section (S2 `data/raw/hmwssb_tankers`, read with P2's
`hmwssb.read_rows`). A month whose file has no rows (Dec 2022) is **missing**, never zero.

Baseline protocol (recovered by reproduction on 2026-10-03; `config/forecast.py`): seasonal
naive (same month one year earlier) on `noofbookings`; a month is scored only if the month
12 earlier is present; all sections present in either month, a missing section value = 0;
city MAPE = mean of monthly absolute percentage errors of city totals; section WAPE = sum of
absolute errors / sum of actuals, pooled over all section-months.

Models: (a) seasonal naive; (b) seasonal naive x year-on-year growth; (c) one global
gradient-boosting model pooled over all sections (scikit-learn, `models` extra) that learns a
correction to seasonal naive from the month, last year's and the year before's values, recent
section and city growth, and weather (D8: last year's month against normal, and recent rain and
heat before the forecast origin). Every feature is at least as old as the forecast origin, so
the same model serves all 12 months of the horizon. Groundwater (D7) is not in the repo.

Every model receives only training data strictly before its target month (it refuses
otherwise), so the rolling-origin backtest cannot leak.
"""

from __future__ import annotations

import calendar
import csv
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.config.env import REPO_ROOT
from app.config.forecast import FORECAST_CONFIG, ForecastConfig
from app.services import hmwssb

Month = tuple[int, int]
SectionValues = dict[str, float]

NOT_RUN: dict[str, str] = {
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


# --- global gradient-boosting candidate ---------------------------------------------------


@dataclass(frozen=True)
class MonthWeather:
    tmax_mean: float  # mean daily maximum temperature, deg C
    precip_total: float  # total precipitation, mm


@lru_cache(maxsize=1)
def monthly_weather(path: str = FORECAST_CONFIG.weather_file) -> dict[Month, MonthWeather]:
    """D8 daily weather summed up per month (empty if the file is absent)."""
    file = REPO_ROOT / path
    if not file.exists():
        return {}
    tmax: dict[Month, list[float]] = {}
    rain: dict[Month, float] = {}
    with file.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            month = (int(row["date"][:4]), int(row["date"][5:7]))
            if row["tmax_c"]:
                tmax.setdefault(month, []).append(float(row["tmax_c"]))
            rain[month] = rain.get(month, 0.0) + float(row["precip_mm"] or 0.0)
    return {m: MonthWeather(sum(v) / len(v), rain.get(m, 0.0)) for m, v in tmax.items()}


@lru_cache(maxsize=1)
def _weather_normal() -> dict[int, MonthWeather]:
    first, last = FORECAST_CONFIG.weather_normal_years
    weather = monthly_weather()
    normal: dict[int, MonthWeather] = {}
    for m in range(1, 13):
        months = [weather[(y, m)] for y in range(first, last + 1) if (y, m) in weather]
        if months:
            normal[m] = MonthWeather(
                sum(w.tmax_mean for w in months) / len(months),
                sum(w.precip_total for w in months) / len(months),
            )
    return normal


@lru_cache(maxsize=1)
def section_monthly_weather() -> dict[str, dict[Month, MonthWeather]]:
    """D8b: each section's monthly weather (TGDPS stations of its nearest mandal, else its
    district, else the city; data/derived/weather/section_monthly.csv). Empty if absent."""
    file = REPO_ROOT / FORECAST_CONFIG.section_weather_file
    if not file.exists():
        return {}
    out: dict[str, dict[Month, MonthWeather]] = {}
    with file.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            month = (int(row["month"][:4]), int(row["month"][5:7]))
            out.setdefault(row["section"], {})[month] = MonthWeather(
                float(row["tmax_mean_c"]), float(row["rain_total_mm"])
            )
    return out


@lru_cache(maxsize=1)
def section_groundwater() -> dict[str, dict[Month, float]]:
    """D7: each section's groundwater anomaly per month (metres deeper than usual; median of
    nearby TGGWD wells; data/derived/groundwater/section_anomaly.csv). Empty if absent."""
    file = REPO_ROOT / FORECAST_CONFIG.groundwater_file
    if not file.exists():
        return {}
    out: dict[str, dict[Month, float]] = {}
    with file.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["anomaly_m"]:
                month = (int(row["month"][:4]), int(row["month"][5:7]))
                out.setdefault(row["section"], {})[month] = float(row["anomaly_m"])
    return out


@lru_cache(maxsize=1)
def _section_normals() -> dict[str, dict[int, MonthWeather]]:
    """Each section's normal per calendar month over `weather_normal_years`."""
    first, last = FORECAST_CONFIG.weather_normal_years
    out: dict[str, dict[int, MonthWeather]] = {}
    for section, series in section_monthly_weather().items():
        for m in range(1, 13):
            months = [series[(y, m)] for y in range(first, last + 1) if (y, m) in series]
            if months:
                out.setdefault(section, {})[m] = MonthWeather(
                    sum(w.tmax_mean for w in months) / len(months),
                    sum(w.precip_total for w in months) / len(months),
                )
    return out


def _weather_anomaly(
    month: Month,
    series: Mapping[Month, MonthWeather] | None = None,
    normals: Mapping[int, MonthWeather] | None = None,
) -> tuple[float, float]:
    """(heat: deg C above normal, rain: log ratio to normal) for one month; NaN if unknown.
    Default: the city series (D8); a section's own series when given."""
    series = monthly_weather() if series is None else series
    normals = _weather_normal() if normals is None else normals
    weather, normal = series.get(month), normals.get(month[1])
    if weather is None or normal is None:
        return math.nan, math.nan
    return (
        weather.tmax_mean - normal.tmax_mean,
        math.log1p(weather.precip_total) - math.log1p(normal.precip_total),
    )


def _recent_weather(
    cutoff: Month,
    series: Mapping[Month, MonthWeather] | None = None,
    normals: Mapping[int, MonthWeather] | None = None,
) -> tuple[float, float]:
    """Rain (log ratio to normal, `recent_rain_months`) and heat (deg C above normal,
    `recent_heat_months`) over the months just before `cutoff`; NaN when not all are known.
    Default: the city series (D8); a section's own series when given."""
    weather = monthly_weather() if series is None else series
    normal = _weather_normal() if normals is None else normals
    rain_months = [shift(cutoff, -k) for k in range(1, FORECAST_CONFIG.recent_rain_months + 1)]
    heat_months = [shift(cutoff, -k) for k in range(1, FORECAST_CONFIG.recent_heat_months + 1)]
    if not all(m in weather and m[1] in normal for m in rain_months + heat_months):
        return math.nan, math.nan
    rain = math.log1p(sum(weather[m].precip_total for m in rain_months)) - math.log1p(
        sum(normal[m[1]].precip_total for m in rain_months)
    )
    heat = sum(weather[m].tmax_mean - normal[m[1]].tmax_mean for m in heat_months) / len(
        heat_months
    )
    return rain, heat


def _recent_growth(train: Panel, cutoff: Month, window: int) -> tuple[float, dict[str, float]]:
    """Log year-on-year growth of the city and of each section over the most recent `window`
    training months before `cutoff` that have a value a year earlier (NaN when there are
    fewer)."""
    period = FORECAST_CONFIG.seasonal_period_months
    months = [m for m in sorted(train.values, reverse=True) if m < cutoff]
    months = [m for m in months if shift(m, -period) in train.values][:window]
    if len(months) < window:
        return math.nan, {}
    now: dict[str, float] = {}
    before: dict[str, float] = {}
    for m in months:
        for s, v in train.values[m].items():
            now[s] = now.get(s, 0.0) + v
        for s, v in train.values[shift(m, -period)].items():
            before[s] = before.get(s, 0.0) + v
    city = math.log1p(sum(now.values())) - math.log1p(sum(before.values()))
    sections = {s: math.log1p(now.get(s, 0.0)) - math.log1p(b) for s, b in before.items() if b > 0}
    return city, sections


def _gbm_rows(
    train: Panel, target: Month, cutoff: Month, local: bool = False, groundwater: bool = False
) -> tuple[list[str], list[list[float]]] | None:
    """Feature rows for every section of the month a year before `target`, using only data
    before `cutoff` (and before the training end). `local`: each section's own weather (D8b)
    where it has a series, the city series otherwise. `groundwater`: the section's groundwater
    anomaly in the month before `cutoff` (D7); otherwise that column is blank (NaN), and a model
    leaves out a column that is blank throughout, so the other models are unchanged."""
    period = FORECAST_CONFIG.seasonal_period_months
    lag_month = shift(target, -period)
    if lag_month not in train.values or lag_month >= cutoff:
        return None
    lag24 = train.values.get(shift(target, -2 * period), {})
    city_growth, section_growth = _recent_growth(
        train, cutoff, FORECAST_CONFIG.growth_window_months
    )
    city_weather = (*_weather_anomaly(lag_month), *_recent_weather(cutoff))
    series, normals = (section_monthly_weather(), _section_normals()) if local else ({}, {})

    def weather(section: str) -> tuple[float, float, float, float]:
        if section not in series or section not in normals:
            return city_weather
        own, normal = series[section], normals[section]
        return (*_weather_anomaly(lag_month, own, normal), *_recent_weather(cutoff, own, normal))

    wells = section_groundwater() if groundwater else {}
    before = shift(cutoff, -1)
    sections = sorted(train.values[lag_month])
    rows = []
    for s in sections:
        lag_heat, lag_rain, recent_rain, recent_heat = weather(s)
        rows.append(
            [
                math.log1p(train.values[lag_month][s]),
                math.log1p(lag24[s]) if s in lag24 else math.nan,
                float(target[1]),
                section_growth.get(s, math.nan),
                city_growth,
                lag_heat,
                lag_rain,
                recent_rain,
                recent_heat,
                wells.get(s, {}).get(before, math.nan),
            ]
        )
    return sections, rows


GBM_FEATURES = (
    "log_lag12", "log_lag24", "month", "section_growth", "city_growth",
    "lag12_heat_anomaly", "lag12_rain_anomaly", "recent_rain_anomaly", "recent_heat_anomaly",
    "groundwater_anomaly",
)  # fmt: skip


def global_gbm(train: Panel, target: Month) -> SectionValues | None:
    """One gradient-boosting model over all sections, trained on every training month that has
    a value a year earlier, predicting log(value + 1) - log(last year + 1). Forecasts the
    sections of the month a year before `target` (like seasonal naive); None without that month
    or with too little training data. Weather: the city series (D8)."""
    return _gbm(train, target, local=False)


def global_gbm_local_weather(train: Panel, target: Month) -> SectionValues | None:
    """The same model with each section's own weather (D8b TGDPS stations of its nearest
    mandal; research follow-up B). Sections without a series use the city weather."""
    return _gbm(train, target, local=True)


def global_gbm_groundwater(train: Panel, target: Month) -> SectionValues | None:
    """The city-weather model plus each section's groundwater anomaly (D7, item 17)."""
    return _gbm(train, target, local=False, groundwater=True)


def _gbm(
    train: Panel, target: Month, local: bool, groundwater: bool = False
) -> SectionValues | None:
    _check(train, target)
    cfg = FORECAST_CONFIG
    origin = shift(max(train.values), 1) if train.values else target
    query = _gbm_rows(train, target, min(target, origin), local, groundwater)
    if query is None:
        return None
    features: list[list[float]] = []
    targets: list[float] = []
    months = 0
    for month in sorted(train.values):
        rows = _gbm_rows(train, month, month, local, groundwater)
        if rows is None:
            continue
        months += 1
        actual = train.values[month]
        for section, row in zip(*rows, strict=True):
            features.append(row)
            targets.append(math.log1p(actual.get(section, 0.0)) - row[0])
    if months < cfg.gbm_min_training_months or len(targets) < cfg.gbm_min_training_rows:
        return None
    from sklearn.ensemble import HistGradientBoostingRegressor  # `models` extra

    model = HistGradientBoostingRegressor(
        loss="absolute_error",
        learning_rate=cfg.gbm_learning_rate,
        max_iter=cfg.gbm_max_iter,
        max_leaf_nodes=cfg.gbm_max_leaf_nodes,
        min_samples_leaf=cfg.gbm_min_samples_leaf,
        l2_regularization=cfg.gbm_l2_regularization,
        early_stopping=False,
        random_state=cfg.gbm_random_state,
    )
    # A feature with no value in the training data (e.g. no year-before-last yet) is left out.
    used = [i for i in range(len(GBM_FEATURES)) if any(not math.isnan(r[i]) for r in features)]
    model.fit([[r[i] for i in used] for r in features], targets)
    sections, rows = query
    predicted = model.predict([[r[i] for i in used] for r in rows])
    return {
        s: max(0.0, math.expm1(row[0] + float(p)))
        for s, row, p in zip(sections, rows, predicted, strict=True)
    }


def combo_naive_gbm(train: Panel, target: Month) -> SectionValues | None:
    """Equal average of seasonal naive and the gradient-boosting model per section: forecast
    combinations are hard to beat and rarely worse than the models they average (Wang et al.,
    "Forecast combinations: an over 50-year review"). None when either model has no forecast."""
    naive = seasonal_naive(train, target)
    gbm = global_gbm(train, target)
    if naive is None or gbm is None:
        return None
    return {s: (naive.get(s, 0.0) + gbm.get(s, 0.0)) / 2 for s in sorted(set(naive) | set(gbm))}


Model = Callable[[Panel, Month], SectionValues | None]
MODELS: dict[str, Model] = {
    "seasonal_naive": seasonal_naive,
    "naive_x_growth": naive_x_growth,
    "global_gbm": global_gbm,
    "global_gbm_local_weather": global_gbm_local_weather,
    "global_gbm_groundwater": global_gbm_groundwater,
    "combo_naive_gbm": combo_naive_gbm,
}
# Simplest first: on a statistical tie the simpler model is used.
COMPLEXITY: tuple[str, ...] = (
    "seasonal_naive",
    "naive_x_growth",
    "global_gbm",
    "global_gbm_local_weather",
    "global_gbm_groundwater",
    "combo_naive_gbm",
)


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


def yoy_months(panel: Panel) -> int:
    """Training months that have a value a year earlier (what a year-on-year model learns from).
    A missing month (Dec 2022) breaks the pair, so the month a year after it does not count."""
    return sum(1 for m in panel.values if shift(m, -12) in panel.values)


@dataclass(frozen=True)
class DMTest:
    statistic: float
    p_value: float  # one-sided: the candidate's losses are lower
    n: int


def diebold_mariano(baseline_losses: Sequence[float], candidate_losses: Sequence[float]) -> DMTest:
    """Diebold-Mariano test of equal accuracy, one-sided (candidate better), with the
    Harvey-Leybourne-Newbold small-sample correction for one-step forecasts (h = 1): the
    statistic is scaled by sqrt((n - 1) / n) and compared with Student's t on n - 1 degrees of
    freedom. Losses are paired per origin. Needs scipy (`models` extra)."""
    d = [b - c for b, c in zip(baseline_losses, candidate_losses, strict=True)]
    n = len(d)
    if n < 2:
        return DMTest(0.0, 1.0, n)
    mean = sum(d) / n
    variance = sum((x - mean) ** 2 for x in d) / n
    if variance == 0:
        if mean == 0:
            return DMTest(0.0, 1.0, n)
        return DMTest(math.copysign(math.inf, mean), 0.0 if mean > 0 else 1.0, n)
    statistic = mean / math.sqrt(variance / n) * math.sqrt((n - 1) / n)
    from scipy.stats import t  # `models` extra (installed with scikit-learn)

    return DMTest(statistic, float(t.sf(statistic, n - 1)), n)


@dataclass(frozen=True)
class CandidateTest:
    model: str
    city_mape: float
    section_wape: float
    baseline_city_mape: float
    baseline_section_wape: float
    dm: DMTest
    passed: bool

    @property
    def p_value(self) -> float:
        return self.dm.p_value


@dataclass(frozen=True)
class Selection:
    model: str
    origins: int  # scored origins (shared by every model, with enough history)
    tests: tuple[CandidateTest, ...]
    reason: str


def select(
    rows: Sequence[BacktestRow],
    production_yoy_months: int,
    origin_yoy_months: Mapping[Month, int] | None = None,
    config: ForecastConfig = FORECAST_CONFIG,
) -> Selection:
    """Selection rule (config `model_selection_rule`), applied to one backtest run (the longest).
    Scored on the origins every model shares where the training data had at least
    `selection_min_yoy_months` year-on-year months. A candidate passes when it beats seasonal
    naive on city MAPE and section WAPE and the HLN Diebold-Mariano test on the monthly section
    absolute errors rejects equal accuracy at `selection_alpha` (one-sided). The published
    forecast must also have that much history. Of the passing models the simplest is used,
    unless a more complex one is significantly better than it."""
    base = "seasonal_naive"
    minimum = config.selection_min_yoy_months
    origins = common_origins(rows)
    if origin_yoy_months is not None:
        origins = {o for o in origins if origin_yoy_months.get(o, 0) >= minimum}
    ordered = sorted(origins)
    loss: dict[str, dict[Month, float]] = {}
    for r in rows:
        if r.origin in origins:
            loss.setdefault(r.model, {})[r.origin] = r.abs_error
    summaries = summarise(rows, origins)

    def losses(model: str) -> list[float]:
        return [loss[model][o] for o in ordered]

    tests = []
    for name in COMPLEXITY[1:]:
        if name not in summaries or base not in summaries:
            continue
        s, b = summaries[name], summaries[base]
        dm = diebold_mariano(losses(base), losses(name))
        better = s.city_mape < b.city_mape and s.section_wape < b.section_wape
        passed = better and dm.p_value < config.selection_alpha
        tests.append(
            CandidateTest(
                name, s.city_mape, s.section_wape, b.city_mape, b.section_wape, dm, passed
            )
        )
    if production_yoy_months < minimum:
        reason = f"published forecast has {production_yoy_months} year-on-year months (< {minimum})"
        return Selection(base, len(ordered), tuple(tests), reason)
    passing = [t.model for t in tests if t.passed]
    if not passing:
        reason = "no candidate is better on both measures with a significant DM test"
        return Selection(base, len(ordered), tuple(tests), reason)
    chosen = passing[0]
    for name in passing[1:]:
        if diebold_mariano(losses(chosen), losses(name)).p_value < config.selection_alpha:
            chosen = name
    reason = f"better than seasonal naive on both measures, DM p < {config.selection_alpha}"
    if len(passing) > 1:
        reason += (
            f"; of {', '.join(passing)} the simplest unless a more complex one is "
            "significantly better"
        )
    return Selection(chosen, len(ordered), tuple(tests), reason)


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
    panel: Panel,
    model_name: str,
    horizon: int,
    config: ForecastConfig = FORECAST_CONFIG,
    basis_note: str = "",
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
    city_basis = "DERIVED: sum of section points"
    if basis_note:
        basis = f"{basis}; {basis_note}"
        city_basis = f"{city_basis}; {basis_note}"
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
            "point": reconcile(forecast),
            "point_basis": city_basis,
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
    Trips per day must be given (FORECAST_CONFIG.trips_per_tanker_per_day, DERIVED)."""
    if trips_per_tanker_per_day is None or trips_per_tanker_per_day <= 0:
        raise ValueError("trips per tanker per day is required (a positive number)")
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
                f"DERIVED: fleet x {trips_per_tanker_per_day} trips per day (news, 2026) x "
                f"{days} days",
            )
        )
    return rows
