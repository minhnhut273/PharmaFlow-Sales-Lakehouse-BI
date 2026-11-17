"""Unit tests for src/weather/validation.py (TC-VAL-01 .. TC-VAL-06)."""

from __future__ import annotations

from tests.weather.conftest import build_synthetic_openmeteo_payload, get_field


def test_tc_val_01_valid_16d_forecast_passes_validation(synthetic_forecast_16d_bytes: bytes) -> None:
    """TC-VAL-01: Valid 16d forecast (384h, unixtime, 0 nulls on core variables) returns SUCCEEDED."""
    from src.weather.validation import validate_open_meteo_response

    report = validate_open_meteo_response(
        raw_bytes=synthetic_forecast_16d_bytes,
        expected_days=16,
        timezone_name="Asia/Ho_Chi_Minh",
        end_date="2026-11-26",
        today_vn="2026-11-11",
    )

    assert get_field(report, "status") == "SUCCEEDED"
    assert get_field(report, "is_accepted") is True
    assert get_field(report, "hourly_step_count") == 384
    assert get_field(report, "daily_step_count") == 16


def test_tc_val_02_http_200_all_null_in_closed_past_is_terminal_failure(synthetic_all_null_bytes: bytes) -> None:
    """TC-VAL-02: HTTP 200 with 100% null core vars in a closed past window (< today - 5 days) -> FAILED_VALIDATION."""
    from src.weather.validation import validate_open_meteo_response

    report = validate_open_meteo_response(
        raw_bytes=synthetic_all_null_bytes,
        expected_days=2,
        timezone_name="Asia/Ho_Chi_Minh",
        end_date="2016-01-02",
        today_vn="2026-11-11",
    )

    assert get_field(report, "status") == "FAILED_VALIDATION"
    assert get_field(report, "is_accepted") is False
    assert get_field(report, "is_terminal") is True
    assert "ALL_NULL" in str(get_field(report, "reason")).upper()


def test_tc_val_03_http_200_all_null_near_present_is_deferred(synthetic_all_null_bytes: bytes) -> None:
    """TC-VAL-03: HTTP 200 with 100% null core vars near present (>= today - 5 days) -> DEFERRED (transient lag)."""
    from src.weather.validation import validate_open_meteo_response

    report = validate_open_meteo_response(
        raw_bytes=synthetic_all_null_bytes,
        expected_days=2,
        timezone_name="Asia/Ho_Chi_Minh",
        end_date="2026-11-09",
        today_vn="2026-11-11",
    )

    assert get_field(report, "status") == "DEFERRED"
    assert get_field(report, "is_accepted") is False
    assert get_field(report, "is_terminal") is False


def test_tc_val_04_secondary_variable_null_with_valid_core_vars_is_accepted_with_warnings(
    synthetic_partial_secondary_null_bytes: bytes,
) -> None:
    """TC-VAL-04: When only secondary variables have nulls and all 4 core variables are valid -> ACCEPTED_WITH_WARNINGS."""
    from src.weather.validation import validate_open_meteo_response

    report = validate_open_meteo_response(
        raw_bytes=synthetic_partial_secondary_null_bytes,
        expected_days=2,
        timezone_name="Asia/Ho_Chi_Minh",
        end_date="2025-05-02",
        today_vn="2026-11-11",
    )

    assert get_field(report, "status") in ("ACCEPTED_WITH_WARNINGS", "accepted_with_warnings")
    assert get_field(report, "is_accepted") is True
    null_report = get_field(report, "null_report")
    assert null_report["uv_index"]["null_ratio"] == 1.0
    assert null_report["temperature_2m"]["null_ratio"] == 0.0


def test_tc_val_05_berlin_dst_transition_unixtime_correctly_counts_25h_day(
    synthetic_berlin_dst_unixtime_bytes: bytes,
) -> None:
    """TC-VAL-05: Berlin DST fallback (2026-10-25 = 25 local hours) is properly converted via ZoneInfo and accepted."""
    from src.weather.validation import validate_open_meteo_response

    report = validate_open_meteo_response(
        raw_bytes=synthetic_berlin_dst_unixtime_bytes,
        expected_days=5,
        timezone_name="Europe/Berlin",
        end_date="2026-10-27",
        today_vn="2026-11-11",
    )

    assert get_field(report, "is_accepted") is True
    assert get_field(report, "hourly_step_count") == 120
    non_24h = get_field(report, "non_24h_days")
    assert non_24h.get("2026-10-25") == 25


def test_tc_val_06_reject_non_unixtime_response() -> None:
    """TC-VAL-06: Response with timeformat=iso8601 instead of unixtime is rejected."""
    from src.weather.validation import validate_open_meteo_response

    bad_bytes = build_synthetic_openmeteo_payload(hours=48, days=2, timeformat="iso8601")
    report = validate_open_meteo_response(
        raw_bytes=bad_bytes,
        expected_days=2,
        timezone_name="Asia/Ho_Chi_Minh",
        end_date="2025-05-02",
        today_vn="2026-11-11",
    )

    assert get_field(report, "is_accepted") is False
    assert get_field(report, "status") == "FAILED_VALIDATION"
