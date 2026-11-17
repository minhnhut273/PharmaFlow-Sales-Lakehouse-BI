"""Offline unit tests for Bronze Weather Auto Loader helpers (path mapping, SHA-256 guard, P5 grid parsing)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from src.bronze.weather_autoloader import (  # noqa: E402
    build_snapshot_record,
    parse_store_grid_mapping_rows,
    prefixes_for_mode,
    resolve_storage_path,
)


def test_prefixes_and_resolve_storage_path() -> None:
    assert prefixes_for_mode("daily") == ("weather_forecast/",)
    assert prefixes_for_mode("historical") == ("historical_forecast/", "historical_weather/")
    assert len(prefixes_for_mode("all")) == 3

    key = "raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=r1/tasks/t1/attempts/a1/response.json"
    assert (
        resolve_storage_path("/Volumes/pharmaflow_dev/bronze_weather/weather_raw/open_meteo", key)
        == "/Volumes/pharmaflow_dev/bronze_weather/weather_raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=r1/tasks/t1/attempts/a1/response.json"
    )
    assert (
        resolve_storage_path("s3://my-bucket/raw/open_meteo/", key)
        == "s3://my-bucket/raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=r1/tasks/t1/attempts/a1/response.json"
    )
    with pytest.raises(ValueError):
        resolve_storage_path("/Volumes/x", "other/path/file.json")


def test_build_snapshot_record_valid_p5_grid_point() -> None:
    root = "/Volumes/pharmaflow_dev/bronze_weather/weather_raw/open_meteo"
    resp_key = "raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=r1/tasks/t1/attempts/a1/response.json"
    meta_key = "raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=r1/tasks/t1/attempts/a1/metadata.json"
    resp_bytes = b'{"hourly":{"time":[1700000000]},"daily":{"time":[1700000000]}}'
    sha = hashlib.sha256(resp_bytes).hexdigest()

    meta_bytes = json.dumps(
        {
            "run_id": "r1",
            "task_id": "t1",
            "attempt_id": "a1",
            "snapshot_id": "r1:t1:a1",
            "forecast_snapshot_id": "r1:t1:a1",
            "mode": "daily_forecast",
            "source_type": "FORECAST",
            "store_id": None,
            "grid_id": "grid:VN:floor:0.111:96:961",
            "member_store_ids": [516, 517],
            "member_store_count": 2,
            "country_code": "VN",
            "timezone_requested": "Asia/Ho_Chi_Minh",
            "timezone_returned": "Asia/Ho_Chi_Minh",
            "utc_offset_seconds": 25200,
            "elevation_m": 8.0,
            "requested_coordinates": {"latitude": 10.74, "longitude": 106.67},
            "returned_coordinates": {"latitude": 10.72, "longitude": 106.64},
            "window": {"start_date": "2026-11-18", "end_date": "2026-12-03"},
            "endpoint_key": "forecast",
            "model": "gfs_global",
            "validation_status": "SUCCEEDED",
            "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
            "coordinate_provenance": "PUBLIC_STORE_LOCATOR",
            "coordinate_verification_status": "OBSERVED_PUBLIC_UNVERIFIED",
            "scheduled_at_utc": "2026-11-17T23:00:00Z",
            "retrieved_at_utc": "2026-11-17T23:01:10Z",
        }
    ).encode("utf-8")

    acc_bytes = json.dumps(
        {
            "run_id": "r1",
            "task_id": "t1",
            "attempt_id": "a1",
            "status": "SUCCEEDED",
            "raw_sha256": sha,
            "response_key": resp_key,
            "metadata_key": meta_key,
            "accepted_at_utc": "2026-11-17T23:01:11Z",
        }
    ).encode("utf-8")

    files = {
        resolve_storage_path(root, resp_key): resp_bytes,
        resolve_storage_path(root, meta_key): meta_bytes,
    }
    snap, err = build_snapshot_record(
        accepted_bytes=acc_bytes,
        accepted_source_path=f"{root}/weather_forecast/ingest_date=2026-11-18/run_id=r1/tasks/t1/accepted.json",
        weather_raw_root=root,
        read_bytes_fn=lambda p: files[p],
    )
    assert err is None
    assert snap is not None
    assert snap["store_id"] is None
    assert snap["grid_id"] == "grid:VN:floor:0.111:96:961"
    assert snap["member_store_ids"] == [516, 517]
    assert snap["member_store_count"] == 2
    assert snap["record_provenance"] == "OBSERVED"
    assert snap["raw_sha256"] == sha


def test_build_snapshot_record_flags_sha256_corruption() -> None:
    root = "/Volumes/pharmaflow_dev/bronze_weather/weather_raw/open_meteo"
    resp_key = "raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=r1/tasks/t1/attempts/a1/response.json"
    meta_key = "raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=r1/tasks/t1/attempts/a1/metadata.json"
    acc_bytes = json.dumps(
        {
            "run_id": "r1",
            "task_id": "t1",
            "attempt_id": "a1",
            "raw_sha256": "0" * 64,
            "response_key": resp_key,
            "metadata_key": meta_key,
        }
    ).encode("utf-8")

    snap, err = build_snapshot_record(
        accepted_bytes=acc_bytes,
        accepted_source_path=f"{root}/weather_forecast/tasks/t1/accepted.json",
        weather_raw_root=root,
        read_bytes_fn=lambda _: b'{"tampered":true}',
    )
    assert snap is None
    assert err is not None
    assert err["error_code"] == "CORRUPTED_SHA256_MISMATCH"


def test_parse_store_grid_mapping_rows() -> None:
    payload = json.dumps(
        {
            "run_id": "daily-20261118-test",
            "cohort_id": "full_network",
            "created_at_utc": "2026-11-17T23:00:05Z",
            "mappings": [
                {
                    "store_id": 516,
                    "store_code": "LC:80439",
                    "country_code": "VN",
                    "timezone_name": "Asia/Ho_Chi_Minh",
                    "point_id": "grid:VN:floor:0.111:96:961",
                    "grid_id": "grid:VN:floor:0.111:96:961",
                    "clustered": True,
                    "store_latitude": 10.7469,
                    "store_longitude": 106.6727,
                    "point_latitude": 10.72,
                    "point_longitude": 106.65,
                    "source": "LONGCHAU",
                    "coordinate_provenance": "PUBLIC_STORE_LOCATOR",
                    "coordinate_verification_status": "OBSERVED_PUBLIC_UNVERIFIED",
                }
            ],
        }
    ).encode("utf-8")

    rows = parse_store_grid_mapping_rows(payload, source_file="/Volumes/.../store_grid_mapping.json")
    assert len(rows) == 1
    assert rows[0]["store_id"] == 516
    assert rows[0]["clustered"] is True
    assert rows[0]["grid_id"] == "grid:VN:floor:0.111:96:961"
