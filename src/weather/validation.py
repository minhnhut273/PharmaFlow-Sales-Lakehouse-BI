"""Validate Open-Meteo raw responses: schema, unixtime, step counts, DST days, and 200 all-null traps."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_CORE_VARIABLES = ("temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m")
NEAR_PRESENT_DAYS = 5


def _result(status: str, reason: str, *, accepted: bool, terminal: bool, **extra: Any) -> dict[str, Any]:
    base = {
        "status": status,
        "reason": reason,
        "is_accepted": accepted,
        "is_terminal": terminal,
        "hourly_step_count": 0,
        "daily_step_count": 0,
        "null_report": {},
        "non_24h_days": {},
        "missing_variables": [],
        "returned_coordinates": None,
        "returned_window": None,
        "elevation_m": None,
        "timezone_returned": None,
        "utc_offset_seconds": None,
        "timeformat_returned": None,
    }
    base.update(extra)
    return base


def _fail(reason: str, **extra: Any) -> dict[str, Any]:
    return _result("FAILED_VALIDATION", reason, accepted=False, terminal=True, **extra)


def validate_open_meteo_response(
    *,
    raw_bytes: bytes,
    expected_days: int,
    timezone_name: str,
    end_date: str,
    today_vn: str,
    core_variables: Sequence[str] = DEFAULT_CORE_VARIABLES,
    expected_hourly_variables: Sequence[str] | None = None,
    start_date: str | None = None,
) -> dict[str, Any]:
    """Parse (read-only) and classify a response. raw_bytes are never modified.

    When start_date is given (the worker always passes it), the first and last local dates of the returned
    hourly series must equal the task window; otherwise the snapshot is rejected as WINDOW_MISMATCH.
    /v1/forecast only accepts forecast_days and always starts "today", so a plan labelled with another date
    must never be accepted as that date's snapshot.
    """
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _fail("INVALID_JSON")
    if not isinstance(payload, dict):
        return _fail("INVALID_JSON_ROOT")
    if payload.get("error"):
        return _fail(f"PROVIDER_ERROR: {str(payload.get('reason'))[:200]}")

    lat, lon = payload.get("latitude"), payload.get("longitude")
    context = {
        "returned_coordinates": {"latitude": lat, "longitude": lon} if lat is not None else None,
        "elevation_m": payload.get("elevation"),
        "timezone_returned": payload.get("timezone"),
        "utc_offset_seconds": payload.get("utc_offset_seconds"),
    }

    hourly = payload.get("hourly")
    hourly_units = payload.get("hourly_units") or {}
    if not isinstance(hourly, dict) or not isinstance(hourly.get("time"), list):
        return _fail("MISSING_HOURLY_BLOCK", **context)

    timeformat = hourly_units.get("time")
    context["timeformat_returned"] = timeformat
    if timeformat != "unixtime":
        return _fail(f"TIMEFORMAT_NOT_UNIXTIME: {timeformat!r}", **context)

    times = hourly["time"]
    expected_steps = int(expected_days) * 24
    daily = payload.get("daily") if isinstance(payload.get("daily"), dict) else {}
    daily_steps = len(daily.get("time") or [])
    context["hourly_step_count"] = len(times)
    context["daily_step_count"] = daily_steps

    if not all(isinstance(t, int) and not isinstance(t, bool) for t in times):
        return _fail("HOURLY_TIME_NOT_EPOCH_INTEGERS", **context)
    if len(times) != expected_steps:
        return _fail(f"HOURLY_STEP_COUNT_MISMATCH: expected {expected_steps}, got {len(times)}", **context)
    if any(b - a != 3600 for a, b in zip(times, times[1:])):
        return _fail("HOURLY_TIME_NOT_CONTIGUOUS_3600S", **context)
    if daily and daily_steps != int(expected_days):
        return _fail(f"DAILY_STEP_COUNT_MISMATCH: expected {expected_days}, got {daily_steps}", **context)

    tz = ZoneInfo(timezone_name)
    local_dates = [datetime.fromtimestamp(t, tz=timezone.utc).astimezone(tz).date().isoformat() for t in times]
    per_day = Counter(local_dates)
    context["non_24h_days"] = {d: n for d, n in sorted(per_day.items()) if n != 24}
    context["returned_window"] = {"start_date": local_dates[0], "end_date": local_dates[-1]} if local_dates else None

    # Check window alignment. Open-Meteo archive API returns data aligned to its fixed standard-time
    # utc_offset_seconds (no historical DST shifts). If ZoneInfo shows a boundary mismatch (e.g. summer CEST
    # spilling 1 hour into end_date+1), verify against the provider's returned utc_offset_seconds.
    if start_date is not None and local_dates and (local_dates[0] != start_date or local_dates[-1] != end_date):
        utc_offset = payload.get("utc_offset_seconds")
        if isinstance(utc_offset, (int, float)):
            tz_offset = timezone(timedelta(seconds=int(utc_offset)))
            offset_dates = [
                datetime.fromtimestamp(t, tz=timezone.utc).astimezone(tz_offset).date().isoformat()
                for t in times
            ]
            if offset_dates and offset_dates[0] == start_date and offset_dates[-1] == end_date:
                local_dates = offset_dates
                per_day = Counter(local_dates)
                context["non_24h_days"] = {d: n for d, n in sorted(per_day.items()) if n != 24}
                context["returned_window"] = {"start_date": local_dates[0], "end_date": local_dates[-1]}

    if start_date is not None and local_dates and (local_dates[0] != start_date or local_dates[-1] != end_date):
        return _fail(
            f"WINDOW_MISMATCH: expected {start_date}..{end_date}, returned {local_dates[0]}..{local_dates[-1]}",
            **context,
        )

    null_report: dict[str, dict[str, Any]] = {}
    for name, values in hourly.items():
        if name == "time" or not isinstance(values, list):
            continue
        nulls = sum(1 for v in values if v is None)
        total = len(values)
        null_report[name] = {"total": total, "nulls": nulls, "null_ratio": (nulls / total) if total else 1.0}
        if total != len(times):
            return _fail(f"VARIABLE_LENGTH_MISMATCH: {name}", null_report=null_report, **context)
    context["null_report"] = null_report

    expected_vars = list(expected_hourly_variables) if expected_hourly_variables else list(core_variables)
    missing = [v for v in expected_vars if v not in null_report]
    context["missing_variables"] = missing
    missing_core = [v for v in core_variables if v not in null_report]
    if missing_core:
        return _fail(f"MISSING_CORE_VARIABLES: {missing_core}", **context)

    all_null_core = [v for v in core_variables if null_report[v]["null_ratio"] >= 1.0]
    if all_null_core:
        near_present_cutoff = date.fromisoformat(today_vn) - timedelta(days=NEAR_PRESENT_DAYS)
        if date.fromisoformat(end_date) >= near_present_cutoff:
            return _result(
                "DEFERRED", f"NEAR_PRESENT_ALL_NULL_LAG: {all_null_core}", accepted=False, terminal=False, **context
            )
        return _fail(f"FAILED_ALL_NULL_COVERAGE: {all_null_core}", **context)

    if any(r["nulls"] > 0 for r in null_report.values()):
        warn = sorted(n for n, r in null_report.items() if r["nulls"] > 0)
        return _result("ACCEPTED_WITH_WARNINGS", f"NULLS_IN: {warn}", accepted=True, terminal=True, **context)
    return _result("SUCCEEDED", "OK", accepted=True, terminal=True, **context)
