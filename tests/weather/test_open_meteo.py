"""Unit tests for src/weather/open_meteo.py (TC-OM-01 .. TC-OM-04)."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from tests.weather.conftest import get_field


def test_tc_om_01_endpoint_allowlist_blocks_unapproved_urls() -> None:
    """TC-OM-01: Only the 3 allowlisted Open-Meteo endpoints are accepted; arbitrary URLs raise ValueError."""
    from src.weather.open_meteo import resolve_endpoint_url

    assert resolve_endpoint_url("forecast") == "https://api.open-meteo.com/v1/forecast"
    assert resolve_endpoint_url("historical_forecast") == "https://historical-forecast-api.open-meteo.com/v1/forecast"
    assert resolve_endpoint_url("historical_weather") == "https://archive-api.open-meteo.com/v1/archive"

    with pytest.raises(ValueError):
        resolve_endpoint_url("https://evil.example.com/v1/forecast")

    with pytest.raises(ValueError):
        resolve_endpoint_url("commercial_api")


def test_tc_om_02_build_query_params_enforces_unixtime_and_model_rules() -> None:
    """TC-OM-02: Query params enforce timeformat=unixtime, standard units, and model=gfs_global only for GFS endpoints."""
    from src.weather.open_meteo import build_open_meteo_params

    gfs_params = build_open_meteo_params(
        endpoint_key="forecast",
        latitude=10.746925,
        longitude=106.672734,
        timezone_name="Asia/Ho_Chi_Minh",
        hourly_variables=["temperature_2m", "precipitation"],
        daily_variables=["weather_code"],
        forecast_days=16,
        model="gfs_global",
    )
    assert gfs_params["timeformat"] == "unixtime"
    assert gfs_params["models"] == "gfs_global"
    assert gfs_params["forecast_days"] == 16
    assert gfs_params["temperature_unit"] == "celsius"
    assert gfs_params["wind_speed_unit"] == "ms"
    assert gfs_params["precipitation_unit"] == "mm"

    era5_params = build_open_meteo_params(
        endpoint_key="historical_weather",
        latitude=10.746925,
        longitude=106.672734,
        timezone_name="Asia/Ho_Chi_Minh",
        hourly_variables=["temperature_2m"],
        daily_variables=["weather_code"],
        start_date="2019-01-01",
        end_date="2019-01-14",
        model=None,
    )
    assert era5_params["timeformat"] == "unixtime"
    assert era5_params["start_date"] == "2019-01-01"
    assert era5_params["end_date"] == "2019-01-14"
    assert "models" not in era5_params


def test_tc_om_03_fetch_preserves_exact_raw_bytes_and_extracts_rate_limit_headers(
    synthetic_forecast_16d_bytes: bytes,
) -> None:
    """TC-OM-03: Client preserves exact raw response bytes, computes SHA-256, and extracts X-RateLimit-* headers."""
    from src.weather.open_meteo import fetch_open_meteo

    class FakeResponse:
        status_code = 200
        content = synthetic_forecast_16d_bytes
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Encoding": "deflate",
            "X-RateLimit-Cost": "5.6",
            "X-RateLimit-Limit": "600.0",
            "X-RateLimit-Remaining": "594.4",
            "X-RateLimit-Reset": "1794330060",
            "X-RateLimit-Window": "60",
        }

    called_kwargs: dict[str, Any] = {}

    class FakeSession:
        def get(self, url: str, **kwargs: Any) -> FakeResponse:
            called_kwargs["url"] = url
            called_kwargs.update(kwargs)
            return FakeResponse()

    result = fetch_open_meteo(
        endpoint_key="forecast",
        params={"latitude": 10.75, "longitude": 106.66, "timeformat": "unixtime"},
        session=FakeSession(),
    )

    assert called_kwargs["allow_redirects"] is False
    assert get_field(result, "http_status") == 200
    assert get_field(result, "raw_bytes") == synthetic_forecast_16d_bytes
    assert get_field(result, "raw_byte_length") == len(synthetic_forecast_16d_bytes)
    assert get_field(result, "raw_sha256") == hashlib.sha256(synthetic_forecast_16d_bytes).hexdigest()

    rl = get_field(result, "rate_limit_headers")
    assert float(rl["X-RateLimit-Cost"]) == pytest.approx(5.6)
    assert float(rl["X-RateLimit-Remaining"]) == pytest.approx(594.4)


@pytest.mark.parametrize(
    ("http_status", "headers", "expected_category"),
    [
        (200, {}, "OK"),
        (429, {"Retry-After": "30"}, "DEFERRED_RATE_LIMIT"),
        (503, {}, "RETRYABLE_SERVER_ERROR"),
        (400, {}, "TERMINAL_CLIENT_ERROR"),
    ],
)
def test_tc_om_04_classify_http_status_and_retry_after(
    http_status: int,
    headers: dict[str, str],
    expected_category: str,
) -> None:
    """TC-OM-04: Classify HTTP status codes into OK, DEFERRED_RATE_LIMIT (429), RETRYABLE_SERVER_ERROR (5xx), or TERMINAL_CLIENT_ERROR (4xx)."""
    from src.weather.open_meteo import classify_http_response

    info = classify_http_response(http_status=http_status, headers=headers)
    assert get_field(info, "category") == expected_category
    if http_status == 429:
        assert get_field(info, "retry_after_seconds") == 30

