"""Unit tests for src/weather/limiter.py (TC-LIM-01 .. TC-LIM-05)."""

from __future__ import annotations

import pytest

from tests.weather.conftest import get_field


def test_tc_lim_01_cost_formula_daily_forecast_16d() -> None:
    """TC-LIM-01: 49 variables (44 hourly + 5 daily) over 16 days costs 5.60 units."""
    from src.weather.limiter import estimate_call_cost

    cost = estimate_call_cost(n_variables=49, n_days=16)
    assert cost == pytest.approx(5.60, abs=1e-6)


def test_tc_lim_02_cost_formula_gfs_backfill_chunk_up_to_14d() -> None:
    """TC-LIM-02: 49 variables over <= 14 days costs 4.90 units."""
    from src.weather.limiter import estimate_call_cost

    assert estimate_call_cost(n_variables=49, n_days=14) == pytest.approx(4.90, abs=1e-6)
    assert estimate_call_cost(n_variables=49, n_days=7) == pytest.approx(4.90, abs=1e-6)
    assert estimate_call_cost(n_variables=49, n_days=1) == pytest.approx(4.90, abs=1e-6)


def test_tc_lim_03_cost_formula_era5_backfill_chunk_up_to_14d() -> None:
    """TC-LIM-03: 40 variables (ERA5 contract) over <= 14 days costs 4.00 units."""
    from src.weather.limiter import estimate_call_cost

    assert estimate_call_cost(n_variables=40, n_days=14) == pytest.approx(4.00, abs=1e-6)
    assert estimate_call_cost(n_variables=40, n_days=12) == pytest.approx(4.00, abs=1e-6)


def test_tc_lim_04_cost_formula_minimum_floor_is_one() -> None:
    """TC-LIM-04: Small requests with < 10 variables and <= 14 days have a floor of 1.0 unit."""
    from src.weather.limiter import estimate_call_cost

    assert estimate_call_cost(n_variables=6, n_days=5) == pytest.approx(1.0, abs=1e-6)
    assert estimate_call_cost(n_variables=1, n_days=1) == pytest.approx(1.0, abs=1e-6)


def test_tc_lim_05_admission_control_protects_daily_reserve() -> None:
    """TC-LIM-05: Backfill admission cannot consume daily_reserve; Daily Forecast can use daily_reserve."""
    from src.weather.limiter import check_budget_admission

    # Daily limit = 10000, daily_reserve = 2000, used_daily = 0, used_backfill = 7500
    # Remaining backfill allowance = (10000 - 2000) - 7500 = 500 units
    allowed_small = check_budget_admission(
        mode="historical_backfill",
        required_units=400.0,
        daily_limit=10000.0,
        daily_reserve=2000.0,
        used_daily=0.0,
        used_backfill=7500.0,
    )
    assert get_field(allowed_small, "allowed") is True

    # Requesting 600 units of backfill would eat into the 2000 daily_reserve -> rejected!
    denied_large = check_budget_admission(
        mode="historical_backfill",
        required_units=600.0,
        daily_limit=10000.0,
        daily_reserve=2000.0,
        used_daily=0.0,
        used_backfill=7500.0,
    )
    assert get_field(denied_large, "allowed") is False
    assert "BUDGET_EXCEEDED" in str(get_field(denied_large, "reason")).upper()

    # Daily forecast requesting 39.2 units (7 stores * 5.6) is allowed using the reserve!
    allowed_daily = check_budget_admission(
        mode="daily_forecast",
        required_units=39.2,
        daily_limit=10000.0,
        daily_reserve=2000.0,
        used_daily=0.0,
        used_backfill=7900.0,
    )
    assert get_field(allowed_daily, "allowed") is True
