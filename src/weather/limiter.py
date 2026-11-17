"""Open-Meteo call weight estimation, daily budget admission, and pacing."""

from __future__ import annotations

DEFAULT_DAILY_LIMIT = 10000.0
DEFAULT_DAILY_RESERVE = 2000.0
DEFAULT_PER_MINUTE_LIMIT = 600.0
DEFAULT_HOURLY_LIMIT = 5000.0
HOURLY_SAFE_LIMIT = 4980.0
BACKFILL_DAILY_ALLOWANCE = DEFAULT_DAILY_LIMIT - DEFAULT_DAILY_RESERVE


def estimate_call_cost(n_variables: int, n_days: int) -> float:
    """Open-Meteo weighted cost: max(1, n_vars/10 * max(1, n_days/14))."""
    if n_variables <= 0 or n_days <= 0:
        raise ValueError("n_variables and n_days must be positive")
    return round(max(1.0, (n_variables / 10.0) * max(1.0, n_days / 14.0)), 6)


def check_budget_admission(
    *,
    mode: str,
    required_units: float,
    daily_limit: float = DEFAULT_DAILY_LIMIT,
    daily_reserve: float = DEFAULT_DAILY_RESERVE,
    used_daily: float = 0.0,
    used_backfill: float = 0.0,
) -> dict[str, object]:
    """Admit or reject a unit request. Backfill may never consume the daily reserve."""
    total_remaining = daily_limit - used_daily - used_backfill
    if mode == "historical_backfill":
        available = min(total_remaining, daily_limit - daily_reserve - used_backfill)
    elif mode == "daily_forecast":
        available = total_remaining
    else:
        raise ValueError(f"Unknown mode {mode!r}")

    available = round(available, 6)
    if required_units <= available + 1e-9:
        return {"allowed": True, "reason": "OK", "available_units": available, "required_units": required_units}
    return {
        "allowed": False,
        "reason": "BUDGET_EXCEEDED_FOR_RUN",
        "available_units": max(0.0, available),
        "required_units": required_units,
    }


def min_interval_seconds(cost: float, per_minute_limit: float = DEFAULT_PER_MINUTE_LIMIT) -> float:
    """Minimum spacing between calls so the weighted per-minute limit is never exceeded."""
    if per_minute_limit <= 0:
        raise ValueError("per_minute_limit must be positive")
    return max(0.0, float(cost)) * 60.0 / per_minute_limit
