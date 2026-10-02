"""T2 forecast and backtest (F5): baseline reproduction, models, no leakage, reconciliation,
conformal intervals, longer portal history, capacity planner."""

from __future__ import annotations

import csv
import glob
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from app.config.forecast import FORECAST_CONFIG
from app.services import forecast as fc

REPO = Path(__file__).resolve().parents[3]
S2_DIR = REPO / "data/raw/hmwssb_tankers"
PORTAL_DIR = REPO / "data/raw/hmwssb_tankers_portal"


def _csv_rows(directory: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(glob.glob(str(directory / "*.csv"))):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


@pytest.fixture(scope="module")
def s2() -> fc.Panel:
    return fc.load_panel(S2_DIR)


def _panel(values: dict[tuple[int, int], dict[str, float]]) -> fc.Panel:
    return fc.Panel("noofbookings", values)


# --- done-when: the confirmed baseline protocol ------------------------------------------


def test_seasonal_naive_reproduces_the_baseline_within_tolerance(s2: fc.Panel) -> None:
    result = fc.baseline(s2)
    cfg = FORECAST_CONFIG
    assert abs(result.city_mape - cfg.baseline_city_mape_pct) <= cfg.baseline_tolerance_pp
    assert abs(result.section_wape - cfg.baseline_section_wape_pct) <= cfg.baseline_tolerance_pp
    # Scored months come from the files: every month with a value 12 months earlier.
    months = sorted({(int(r["year"]), int(r["month"])) for r in _csv_rows(S2_DIR)})
    expected = [m for m in months if fc.shift(m, -12) in set(months)]
    assert list(result.scored_months) == expected
    assert result.scored_months[0] == (2023, 1) and result.scored_months[-1] == (2024, 2)


def test_panel_holds_every_row_of_the_files(s2: fc.Panel) -> None:
    rows = _csv_rows(S2_DIR)
    assert sum(len(v) for v in s2.values.values()) == len(rows)
    assert sum(sum(v.values()) for v in s2.values.values()) == sum(
        int(r["noofbookings"]) for r in rows
    )
    sections = {r["section"].strip().upper() for r in rows}
    assert s2.sections() == sections


def test_dec_2022_is_missing_never_zero(s2: fc.Panel) -> None:
    assert (2022, 12) not in s2.months
    assert fc.seasonal_naive(s2.until((2023, 12)), (2023, 12)) is None
    assert (2023, 12) not in fc.baseline(s2).scored_months
    # Treating it as zero would score Dec 2023 against a zero forecast; the protocol does not.
    with_zero = _panel({**s2.values, (2022, 12): {}})
    assert (2023, 12) in fc.baseline(with_zero).scored_months


def test_config_records_the_protocol() -> None:
    cfg = FORECAST_CONFIG
    assert cfg.baseline_column == "noofbookings"
    assert cfg.baseline_recovered_on == "2026-10-03"
    assert "V-VERIFY_REVIEW.md" in cfg.baseline_protocol


# --- models and no leakage ---------------------------------------------------------------


def test_models_refuse_training_data_at_or_after_the_target(s2: fc.Panel) -> None:
    for model in fc.MODELS.values():
        with pytest.raises(ValueError, match="leak"):
            model(s2, (2023, 6))


def test_no_leakage_future_values_do_not_change_a_forecast(s2: fc.Panel) -> None:
    origin = (2023, 9)
    poisoned = _panel(
        {
            m: ({s: v * 1000 for s, v in secs.items()} if m >= origin else secs)
            for m, secs in s2.values.items()
        }
    )
    for name, model in fc.MODELS.items():
        assert model(s2.until(origin), origin) == model(poisoned.until(origin), origin), name
    rows = {(r.model, r.origin): r for r in fc.backtest(s2)}
    rows_poisoned = {(r.model, r.origin): r for r in fc.backtest(poisoned)}
    for key, row in rows.items():
        if key[1] < origin:
            assert row == rows_poisoned[key]


def test_seasonal_naive_is_the_same_month_a_year_earlier() -> None:
    p = _panel({(2022, 3): {"A": 10, "B": 4}, (2023, 2): {"A": 99}})
    assert fc.seasonal_naive(p, (2023, 3)) == {"A": 10, "B": 4}


def test_naive_times_growth_on_a_hand_checkable_fixture() -> None:
    window = FORECAST_CONFIG.growth_window_months
    values: dict[tuple[int, int], dict[str, float]] = {}
    for k in range(window):
        values[fc.shift((2022, 6), -k)] = {"A": 10}
        values[fc.shift((2023, 6), -k)] = {"A": 15}  # +50 % year on year
    values[(2022, 7)] = {"A": 20, "B": 2}
    p = _panel(values)
    assert fc.naive_x_growth(p, (2023, 7)) == pytest.approx({"A": 30.0, "B": 3.0})


def test_backtest_naive_equals_the_baseline(s2: fc.Panel) -> None:
    summary = fc.summarise(fc.backtest(s2, models=("seasonal_naive",)))["seasonal_naive"]
    base = fc.baseline(s2)
    assert summary.city_mape == pytest.approx(base.city_mape)
    assert summary.section_wape == pytest.approx(base.section_wape)
    assert summary.origins == len(base.scored_months)


def test_gbm_is_reported_as_not_run_without_a_library() -> None:
    assert "global_gbm" not in fc.MODELS
    assert "global_gbm" in fc.NOT_RUN and "not installed" in fc.NOT_RUN["global_gbm"]


# --- sections that appear or disappear ---------------------------------------------------


def test_a_section_that_appears_or_disappears_counts_as_zero() -> None:
    p = _panel({(2022, 5): {"A": 10, "GONE": 6}, (2023, 5): {"A": 12, "NEW": 4}})
    result = fc.baseline(p)
    # A: |12-10| = 2; GONE: |0-6| = 6; NEW: |4-0| = 4; actual sum 16.
    assert result.section_wape == pytest.approx((2 + 6 + 4) / 16 * 100)
    assert result.section_months == 3
    assert result.city_mape == pytest.approx(abs(16 - 16) / 16 * 100)


def test_section_changes_between_years_are_reported_from_the_files() -> None:
    rows = _csv_rows(PORTAL_DIR)
    by_year: dict[int, set[str]] = {}
    for r in rows:
        if (int(r["year"]), int(r["month"])) <= (2026, 1):
            by_year.setdefault(int(r["year"]), set()).add(r["section"].strip().upper())
    panel = fc.load_panel(PORTAL_DIR, through=(2026, 1))
    changes = fc.section_changes(panel)
    for year in sorted(by_year)[1:]:
        assert changes[year]["appeared"] == len(by_year[year] - by_year[year - 1])
        assert changes[year]["disappeared"] == len(by_year[year - 1] - by_year[year])


# --- reconciliation ----------------------------------------------------------------------


def test_section_forecasts_sum_to_the_city_forecast(s2: fc.Panel) -> None:
    table = fc.forecast_table(s2, "seasonal_naive", horizon=FORECAST_CONFIG.horizon_months)
    sections = [r for r in table if r["level"] == "section"]
    city = {r["month"]: r for r in table if r["level"] == "city"}
    assert city
    for month, row in city.items():
        assert row["point"] == pytest.approx(
            sum(r["point"] for r in sections if r["month"] == month)
        )
    assert fc.reconcile({"A": 2.5, "B": 4.0}) == 6.5


# --- conformal intervals -----------------------------------------------------------------


def test_conformal_quantile_and_coverage_on_a_tiny_fixture() -> None:
    # n = 4 scores, level 0.8 -> k = ceil(5 x 0.8) = 4 -> the 4th smallest score.
    assert fc.conformal_quantile([3.0, 1.0, 4.0, 2.0], 0.8) == 4.0
    # level 0.9 -> k = ceil(4.5) = 5 > n -> no finite interval.
    assert fc.conformal_quantile([3.0, 1.0, 4.0, 2.0], 0.9) == float("inf")
    # Actuals 5, 9, 2 against intervals [4, 6], [4, 8], [2, 3]: two of three inside.
    assert fc.coverage([5, 9, 2], [4, 4, 2], [6, 8, 3]) == pytest.approx(2 / 3)


def test_conformal_backtest_reports_coverage_or_says_why_not(s2: fc.Panel) -> None:
    results = fc.conformal_backtest(s2, "seasonal_naive")
    assert [r.level for r in results] == list(FORECAST_CONFIG.interval_levels)
    for r in results:
        assert r.n_calibration_months + r.n_test_months == len(fc.baseline(s2).scored_months)
        if r.status == "ok":
            assert 0 <= r.coverage <= 1 and r.n_test_points > 0
        else:
            assert r.status == "insufficient" and r.coverage is None and r.reason
    tight = replace(FORECAST_CONFIG, min_calibration_months=50)
    assert all(
        r.status == "insufficient"
        for r in fc.conformal_backtest(s2, "seasonal_naive", config=tight)
    )


# --- model choice ------------------------------------------------------------------------


def test_only_a_model_that_beats_the_baseline_is_selected() -> None:
    def s(mape: float, wape: float) -> fc.Summary:
        return fc.Summary(mape, wape, 10, 100)

    naive = {"seasonal_naive": s(20, 30)}
    assert fc.select_model([{**naive, "naive_x_growth": s(25, 29)}]) == "seasonal_naive"
    assert fc.select_model([{**naive, "naive_x_growth": s(19, 29)}]) == "naive_x_growth"
    # Must beat it in every run given (S2 and portal).
    assert (
        fc.select_model(
            [{**naive, "naive_x_growth": s(19, 29)}, {**naive, "naive_x_growth": s(21, 29)}]
        )
        == "seasonal_naive"
    )


# --- capacity planner --------------------------------------------------------------------


def test_capacity_planner_refuses_to_run_without_trips_per_day() -> None:
    assert FORECAST_CONFIG.trips_per_tanker_per_day is None
    with pytest.raises(ValueError, match="trips per tanker per day"):
        fc.capacity_plan({(2026, 5): 100.0}, fleet=10, trips_per_tanker_per_day=None)
    plan = fc.capacity_plan({(2026, 5): 1000.0}, fleet=10, trips_per_tanker_per_day=2.0)
    assert plan[0].capacity_trips == 10 * 2.0 * 31
    assert plan[0].shortfall_trips == 1000.0 - 620.0
    assert plan[0].fleet_basis.startswith("ASSUMED")


# --- output script -----------------------------------------------------------------------


def test_run_backtest_writes_outputs_with_basis_columns(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "run_backtest", REPO / "scripts/forecast/run_backtest.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert module.main(["--out-dir", str(tmp_path)]) == 0
    for name in ("forecast_backtest.csv", "forecast_table.csv"):
        with (tmp_path / name).open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert rows
        derived = [c for c in rows[0] if c in fc.DERIVED_COLUMNS]
        assert derived and all(f"{c}_basis" in rows[0] for c in derived)
