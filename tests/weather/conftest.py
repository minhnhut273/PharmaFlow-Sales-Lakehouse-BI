"""Shared pytest fixtures and helpers for tests/weather/."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WEATHER_CONFIG_DIR = REPO_ROOT / "src" / "weather" / "config"


def get_field(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field from either a dict/Mapping or a dataclass/object attribute."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


@pytest.fixture()
def config_dir() -> Path:
    return WEATHER_CONFIG_DIR


@pytest.fixture()
def pilot_store_rows() -> list[dict[str, Any]]:
    """The 7 pilot stores verified on Neon pharmaflow_source_postgre_v2 in P0b."""
    return [
        {
            "store_id": 104,
            "store_code": "LC:81457",
            "country_code": "VN",
            "latitude": 21.074221,
            "longitude": 105.777006,
            "timezone_name": "Asia/Ho_Chi_Minh",
            "store_status": "ACTIVE",
            "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        },
        {
            "store_id": 516,
            "store_code": "LC:80439",
            "country_code": "VN",
            "latitude": 10.746925,
            "longitude": 106.672734,
            "timezone_name": "Asia/Ho_Chi_Minh",
            "store_status": "ACTIVE",
            "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        },
        {
            "store_id": 1234,
            "store_code": "LC:81222",
            "country_code": "VN",
            "latitude": 8.622943,
            "longitude": 105.017990,
            "timezone_name": "Asia/Ho_Chi_Minh",
            "store_status": "ACTIVE",
            "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        },
        {
            "store_id": 2137,
            "store_code": "LC:81176",
            "country_code": "VN",
            "latitude": 23.277563,
            "longitude": 105.359911,
            "timezone_name": "Asia/Ho_Chi_Minh",
            "store_status": "ACTIVE",
            "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        },
        {
            "store_id": 5389,
            "store_code": "SIM_IRPD_CENTRAL_JAVA_001",
            "country_code": "ID",
            "latitude": -6.963490,
            "longitude": 110.413261,
            "timezone_name": "Asia/Jakarta",
            "store_status": "ACTIVE",
            "source": "IRPD_SIMULATED_LOCATION_CENTRAL_JAVA",
        },
        {
            "store_id": 5404,
            "store_code": "ONYX:PH0014",
            "country_code": "DE",
            "latitude": 52.527791,
            "longitude": 13.420219,
            "timezone_name": "Europe/Berlin",
            "store_status": "ACTIVE",
            "source": "ONYX_CHALLENGE_LOCATION_DIMENSION_UNVERIFIED",
        },
        {
            "store_id": 5631,
            "store_code": "SIM_PHARMA_SALES_NIS_001",
            "country_code": "RS",
            "latitude": 43.322359,
            "longitude": 21.899252,
            "timezone_name": "Europe/Belgrade",
            "store_status": "ACTIVE",
            "source": "PHARMA_SALES_SIMULATED_LOCATION_NIS",
        },
    ]


def build_synthetic_openmeteo_payload(
    *,
    start_epoch: int = 1794330000,
    hours: int = 384,
    days: int = 16,
    timezone_name: str = "Asia/Ho_Chi_Minh",
    utc_offset_seconds: int = 25200,
    timeformat: str = "unixtime",
    all_null_core: bool = False,
    secondary_null: bool = False,
) -> bytes:
    """Build deterministic SYNTHETIC Open-Meteo JSON bytes for offline unit tests."""
    hourly_times = [start_epoch + i * 3600 for i in range(hours)]
    daily_times = [start_epoch + d * 86400 for d in range(days)]

    core_val = (lambda i: None) if all_null_core else (lambda i: round(25.0 + (i % 10) * 0.2, 2))
    secondary_val = (lambda i: None) if (all_null_core or secondary_null) else (lambda i: round(1.5 + (i % 5) * 0.1, 2))

    payload = {
        "_fixture_origin": "SYNTHETIC_TEST_FIXTURE",
        "latitude": 10.75,
        "longitude": 106.625,
        "generationtime_ms": 0.42,
        "utc_offset_seconds": utc_offset_seconds,
        "timezone": timezone_name,
        "timezone_abbreviation": "GMT+7" if utc_offset_seconds == 25200 else "GMT+1",
        "elevation": 9.0,
        "hourly_units": {
            "time": timeformat,
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "precipitation": "mm",
            "wind_speed_10m": "m/s",
            "uv_index": "",
        },
        "hourly": {
            "time": hourly_times if timeformat == "unixtime" else [f"2026-11-11T{i % 24:02d}:00" for i in range(hours)],
            "temperature_2m": [core_val(i) for i in range(hours)],
            "relative_humidity_2m": [None if all_null_core else 75 for _ in range(hours)],
            "precipitation": [None if all_null_core else 0.0 for _ in range(hours)],
            "wind_speed_10m": [None if all_null_core else 3.2 for _ in range(hours)],
            "uv_index": [secondary_val(i) for i in range(hours)],
        },
        "daily_units": {
            "time": timeformat,
            "weather_code": "wmo code",
        },
        "daily": {
            "time": daily_times if timeformat == "unixtime" else [f"2026-11-{11 + d:02d}" for d in range(days)],
            "weather_code": [None if all_null_core else 3 for _ in range(days)],
        },
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@pytest.fixture()
def synthetic_forecast_16d_bytes() -> bytes:
    return build_synthetic_openmeteo_payload(hours=384, days=16)


@pytest.fixture()
def synthetic_all_null_bytes() -> bytes:
    return build_synthetic_openmeteo_payload(hours=48, days=2, all_null_core=True)


@pytest.fixture()
def synthetic_partial_secondary_null_bytes() -> bytes:
    return build_synthetic_openmeteo_payload(hours=48, days=2, all_null_core=False, secondary_null=True)


@pytest.fixture()
def synthetic_berlin_dst_unixtime_bytes() -> bytes:
    """5-day (120h) Europe/Berlin payload across 2026-10-25 DST fallback starting at 1792710000."""
    # 1792710000 = 2026-10-22 23:00:00 UTC (which Open-Meteo returns for 2026-10-23..2026-10-27 with GMT+1 offset)
    return build_synthetic_openmeteo_payload(
        start_epoch=1792710000,
        hours=120,
        days=5,
        timezone_name="Europe/Berlin",
        utc_offset_seconds=3600,
        timeformat="unixtime",
    )


def build_payload_for_params(params: Mapping[str, Any], *, now_utc: datetime | None = None, **kwargs: Any) -> bytes:
    """SYNTHETIC payload whose hourly series starts at local midnight of the requested window.

    Backfill params carry start_date/end_date; forecast params only carry forecast_days, so the window
    starts at the local date of now_utc (like /v1/forecast, which always starts "today").
    """
    from datetime import date as _date
    from datetime import time as _time

    tz = ZoneInfo(params["timezone"])
    if "forecast_days" in params:
        start = (now_utc or datetime.now(timezone.utc)).astimezone(tz).date()
        days = int(params["forecast_days"])
    else:
        start = _date.fromisoformat(params["start_date"])
        days = (_date.fromisoformat(params["end_date"]) - start).days + 1
    start_epoch = int(datetime.combine(start, _time(0, 0), tzinfo=tz).timestamp())
    return build_synthetic_openmeteo_payload(start_epoch=start_epoch, hours=days * 24, days=days,
                                             timezone_name=params["timezone"], **kwargs)
