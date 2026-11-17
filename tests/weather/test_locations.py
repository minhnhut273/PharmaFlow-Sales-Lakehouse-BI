"""Unit tests for src/weather/locations.py (TC-LOC-01 .. TC-LOC-07)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.weather.conftest import get_field


def test_tc_loc_01_accept_all_active_stores_across_all_sources(pilot_store_rows: list[dict[str, Any]]) -> None:
    """TC-LOC-01: All ACTIVE stores with valid coords & IANA timezone are accepted regardless of source."""
    from src.weather.locations import evaluate_locations

    requested_ids = [104, 516, 1234, 2137, 5389, 5404, 5631]
    result = evaluate_locations(
        rows=pilot_store_rows,
        requested_store_ids=requested_ids,
        allow_unknown_status=False,
    )

    eligible = list(get_field(result, "eligible_locations"))
    rejected = list(get_field(result, "rejected_locations"))

    assert len(eligible) == 7
    assert len(rejected) == 0
    assert [get_field(loc, "store_id") for loc in eligible] == sorted(requested_ids)


def test_tc_loc_02_preserve_source_and_attach_provenance_labels(pilot_store_rows: list[dict[str, Any]]) -> None:
    """TC-LOC-02: Eligible locations preserve source and attach provenance without equating simulated/unverified with verified."""
    from src.weather.locations import evaluate_locations

    result = evaluate_locations(
        rows=pilot_store_rows,
        requested_store_ids=[104, 5389, 5404, 5631],
    )
    eligible = {get_field(loc, "store_id"): loc for loc in get_field(result, "eligible_locations")}

    # Long Chau
    lc = eligible[104]
    assert get_field(lc, "source") == "LONGCHAU_PUBLIC_STORE_LOCATOR"
    assert get_field(lc, "coordinate_provenance")
    assert get_field(lc, "coordinate_verification_status")

    # Onyx (perturbed / unverified)
    onyx = eligible[5404]
    assert get_field(onyx, "source") == "ONYX_CHALLENGE_LOCATION_DIMENSION_UNVERIFIED"
    assert "UNVERIFIED" in str(get_field(onyx, "coordinate_verification_status")).upper()

    # IRPD (simulated regional proxy)
    irpd = eligible[5389]
    assert get_field(irpd, "source") == "IRPD_SIMULATED_LOCATION_CENTRAL_JAVA"
    assert "SIMULATED" in str(get_field(irpd, "coordinate_verification_status")).upper()


def test_tc_loc_03_reject_inactive_stores() -> None:
    """TC-LOC-03: INACTIVE stores are placed in rejected_locations."""
    from src.weather.locations import evaluate_locations

    rows = [
        {
            "store_id": 9001,
            "store_code": "LC:9001",
            "country_code": "VN",
            "latitude": 10.75,
            "longitude": 106.66,
            "timezone_name": "Asia/Ho_Chi_Minh",
            "store_status": "INACTIVE",
            "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        }
    ]
    result = evaluate_locations(rows=rows, requested_store_ids=[9001])
    assert len(get_field(result, "eligible_locations")) == 0
    rejected = list(get_field(result, "rejected_locations"))
    assert len(rejected) == 1
    assert get_field(rejected[0], "store_id") == 9001
    assert "INACTIVE" in str(get_field(rejected[0], "rejection_reason")).upper()


def test_tc_loc_04_unknown_status_default_rejected_and_override_accepted() -> None:
    """TC-LOC-04: UNKNOWN store_status is rejected by default, accepted only with explicit override & reason."""
    from src.weather.locations import evaluate_locations

    rows = [
        {
            "store_id": 9002,
            "store_code": "LC:9002",
            "country_code": "VN",
            "latitude": 10.75,
            "longitude": 106.66,
            "timezone_name": "Asia/Ho_Chi_Minh",
            "store_status": "UNKNOWN",
            "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        }
    ]
    # Default: rejected
    res_default = evaluate_locations(rows=rows, requested_store_ids=[9002], allow_unknown_status=False)
    assert len(get_field(res_default, "eligible_locations")) == 0
    assert len(get_field(res_default, "rejected_locations")) == 1

    # With explicit override + reason: accepted
    res_override = evaluate_locations(
        rows=rows,
        requested_store_ids=[9002],
        allow_unknown_status=True,
        override_reason="Approved pilot test for unknown status store",
    )
    assert len(get_field(res_override, "eligible_locations")) == 1
    assert len(get_field(res_override, "rejected_locations")) == 0


@pytest.mark.parametrize(
    ("lat", "lon"),
    [
        (None, 106.66),
        (10.75, None),
        (None, None),
        (-95.0, 106.66),
        (91.0, 106.66),
        (10.75, 185.0),
        (10.75, -181.0),
        (float("nan"), 106.66),
        (10.75, float("inf")),
    ],
)
def test_tc_loc_05_reject_null_or_out_of_range_coordinates(lat: Any, lon: Any) -> None:
    """TC-LOC-05: NULL, NaN/Inf, or out-of-bounds coordinates are rejected without coercing NULL to 0."""
    from src.weather.locations import evaluate_locations

    rows = [
        {
            "store_id": 9003,
            "store_code": "LC:9003",
            "country_code": "VN",
            "latitude": lat,
            "longitude": lon,
            "timezone_name": "Asia/Ho_Chi_Minh",
            "store_status": "ACTIVE",
            "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        }
    ]
    result = evaluate_locations(rows=rows, requested_store_ids=[9003])
    assert len(get_field(result, "eligible_locations")) == 0
    rejected = list(get_field(result, "rejected_locations"))
    assert len(rejected) == 1
    assert get_field(rejected[0], "store_id") == 9003


def test_tc_loc_06_reject_invalid_iana_timezone() -> None:
    """TC-LOC-06: Invalid IANA timezone_name is rejected."""
    from src.weather.locations import evaluate_locations

    rows = [
        {
            "store_id": 9004,
            "store_code": "LC:9004",
            "country_code": "VN",
            "latitude": 10.75,
            "longitude": 106.66,
            "timezone_name": "Invalid/Timezone_Name",
            "store_status": "ACTIVE",
            "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        }
    ]
    result = evaluate_locations(rows=rows, requested_store_ids=[9004])
    assert len(get_field(result, "eligible_locations")) == 0
    rejected = list(get_field(result, "rejected_locations"))
    assert len(rejected) == 1
    assert "TIMEZONE" in str(get_field(rejected[0], "rejection_reason")).upper()


def test_tc_loc_07_missing_requested_store_id_is_recorded_in_rejected(pilot_store_rows: list[dict[str, Any]]) -> None:
    """TC-LOC-07: A requested store_id not returned from DB is recorded in rejected_locations (not silently lost)."""
    from src.weather.locations import evaluate_locations

    result = evaluate_locations(rows=pilot_store_rows[:2], requested_store_ids=[104, 516, 999999])
    eligible = list(get_field(result, "eligible_locations"))
    rejected = list(get_field(result, "rejected_locations"))

    assert [get_field(e, "store_id") for e in eligible] == [104, 516]
    assert len(rejected) == 1
    assert get_field(rejected[0], "store_id") == 999999
