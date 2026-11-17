"""Unit tests for src/weather/config.py (TC-CFG-01 .. TC-CFG-05)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.weather.conftest import get_field


def test_tc_cfg_01_load_gfs_variable_contract_v1(config_dir: Path) -> None:
    """TC-CFG-01: weather_variables_v1 loads 44 hourly + 5 daily = 49 variables, gfs_global, unixtime."""
    from src.weather.config import load_variable_contract

    contract = load_variable_contract("weather_variables_v1", config_dir=config_dir)
    hourly = list(get_field(contract, "hourly_variables"))
    daily = list(get_field(contract, "daily_variables"))
    core = list(get_field(contract, "core_hourly_variables"))
    units = get_field(contract, "units")

    assert get_field(contract, "contract_version") == "weather_variables_v1"
    assert get_field(contract, "model") == "gfs_global"
    assert get_field(contract, "timeformat") == "unixtime"
    assert len(hourly) == 44
    assert len(daily) == 5
    assert len(hourly) + len(daily) == 49
    assert set(core) == {"temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m"}
    assert get_field(units, "temperature_unit") == "celsius"
    assert get_field(units, "wind_speed_unit") == "ms"
    assert get_field(units, "precipitation_unit") == "mm"

    # Must exclude the 11 all-null GFS soil / 180m variables
    for excluded in ("wind_speed_180m", "wind_direction_180m", "soil_temperature_0cm", "soil_moisture_0_to_1cm"):
        assert excluded not in hourly


def test_tc_cfg_02_load_era5_variable_contract_v1(config_dir: Path) -> None:
    """TC-CFG-02: weather_era5_v1 loads 35 hourly + 5 daily = 40 variables for < 2022-01-01."""
    from src.weather.config import load_variable_contract

    contract = load_variable_contract("weather_era5_v1", config_dir=config_dir)
    hourly = list(get_field(contract, "hourly_variables"))
    daily = list(get_field(contract, "daily_variables"))

    assert get_field(contract, "contract_version") == "weather_era5_v1"
    assert get_field(contract, "timeformat") == "unixtime"
    assert len(hourly) == 35
    assert len(daily) == 5
    assert len(hourly) + len(daily) == 40

    # Must exclude the 9 GFS-only variables that return 100% null on ERA5
    for gfs_only in ("precipitation_probability", "visibility", "evapotranspiration", "uv_index", "cape"):
        assert gfs_only not in hourly


def test_tc_cfg_03_load_cohorts_config_pilot(config_dir: Path) -> None:
    """TC-CFG-03: cohorts.yaml loads pilot_v1 with the 7 approved pilot store_ids and provenance map."""
    from src.weather.config import load_cohorts_config

    cfg = load_cohorts_config(config_dir=config_dir)
    cohorts = get_field(cfg, "cohorts")
    pilot = get_field(cohorts, "pilot")
    prov_map = get_field(cfg, "source_provenance_map")

    assert get_field(cfg, "cohort_policy_version") == "pilot_v1"
    assert list(get_field(pilot, "store_ids")) == [104, 516, 1234, 2137, 5389, 5404, 5631]
    assert get_field(pilot, "allow_unknown_status") is False
    assert "LONGCHAU_PUBLIC_STORE_LOCATOR" in prov_map
    assert "ONYX_CHALLENGE_LOCATION_DIMENSION_UNVERIFIED" in prov_map
    assert "IRPD_SIMULATED_LOCATION_CENTRAL_JAVA" in prov_map
    assert "PHARMA_SALES_SIMULATED_LOCATION_NIS" in prov_map


def test_tc_cfg_04_compute_config_hash_is_deterministic() -> None:
    """TC-CFG-04: compute_config_hash produces identical sha256:... regardless of dict key order."""
    from src.weather.config import compute_config_hash

    payload_a = {"b": [1, 2, 3], "a": {"y": "unixtime", "x": "gfs_global"}}
    payload_b = {"a": {"x": "gfs_global", "y": "unixtime"}, "b": [1, 2, 3]}
    payload_c = {"a": {"x": "best_match", "y": "unixtime"}, "b": [1, 2, 3]}

    hash_a = compute_config_hash(payload_a)
    hash_b = compute_config_hash(payload_b)
    hash_c = compute_config_hash(payload_c)

    assert hash_a.startswith("sha256:")
    assert hash_a == hash_b
    assert hash_a != hash_c


def test_tc_cfg_05_reject_invalid_timeformat_or_empty_variables(tmp_path: Path) -> None:
    """TC-CFG-05: load_variable_contract raises ValueError when timeformat != unixtime or variables missing."""
    from src.weather.config import load_variable_contract

    bad_yaml = tmp_path / "bad_contract.yaml"
    bad_yaml.write_text(
        "contract_version: bad_v1\ntimeformat: iso8601\nhourly_variables: [temperature_2m]\ndaily_variables: [weather_code]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unixtime"):
        load_variable_contract("bad_contract", config_dir=tmp_path)
