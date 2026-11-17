"""Unit tests for src/weather/storage.py, worker.py, and planner replay (TC-STO-01 .. TC-WRK-05)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from tests.weather.conftest import get_field


def test_tc_sto_01_local_sink_preserves_exact_bytes_and_layout(
    tmp_path: Path,
    synthetic_forecast_16d_bytes: bytes,
) -> None:
    """TC-STO-01: LocalSink writes raw bytes under canonical S3-like key and reads back identical bytes & SHA-256."""
    from src.weather.storage import LocalSink

    sink = LocalSink(root_dir=tmp_path)
    raw_key = (
        "raw/open_meteo/weather_forecast/ingest_date=2026-11-11/"
        "run_id=daily-20261111-abcd1234/tasks/task0001/attempts/att01/response.json"
    )
    sink.put_bytes(raw_key, synthetic_forecast_16d_bytes)

    readback = sink.get_bytes(raw_key)
    assert readback == synthetic_forecast_16d_bytes
    assert hashlib.sha256(readback).hexdigest() == hashlib.sha256(synthetic_forecast_16d_bytes).hexdigest()


def test_tc_sto_02_conditional_write_prevents_overwriting_accepted_marker(tmp_path: Path) -> None:
    """TC-STO-02: Conditional write (put_if_absent) succeeds on first write and refuses second overwrite."""
    from src.weather.storage import LocalSink

    sink = LocalSink(root_dir=tmp_path)
    accepted_key = (
        "raw/open_meteo/weather_forecast/ingest_date=2026-11-11/"
        "run_id=daily-20261111-abcd1234/tasks/task0001/accepted.json"
    )

    first = sink.put_json_if_absent(accepted_key, {"attempt_id": "att01", "status": "SUCCEEDED"})
    assert first is True

    # Second attempt to overwrite accepted.json must return False or raise FileExistsError
    try:
        second = sink.put_json_if_absent(accepted_key, {"attempt_id": "att02", "status": "SUCCEEDED"})
        assert second is False
    except FileExistsError:
        pass

    stored = sink.get_json(accepted_key)
    assert stored["attempt_id"] == "att01"


def test_tc_wrk_01_worker_happy_path_persists_raw_metadata_and_accepted(
    tmp_path: Path,
    synthetic_forecast_16d_bytes: bytes,
) -> None:
    """TC-WRK-01: Worker fetches Open-Meteo, saves response.json + metadata.json, validates, and writes accepted.json."""
    from src.weather.storage import LocalSink
    from src.weather.worker import execute_task

    sink = LocalSink(root_dir=tmp_path)
    task = {
        "run_id": "daily-20261111-abcd1234",
        "task_id": "task0001abcd1234",
        "ingest_date": "2026-11-11",
        "mode": "daily_forecast",
        "endpoint_key": "forecast",
        "s3_prefix": "raw/open_meteo/weather_forecast",
        "store_id": 516,
        "store_code": "LC:80439",
        "latitude": 10.746925,
        "longitude": 106.672734,
        "timezone_name": "Asia/Ho_Chi_Minh",
        "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        "coordinate_provenance": "PUBLIC_STORE_LOCATOR",
        "start_date": "2026-11-11",
        "end_date": "2026-11-26",
        "expected_days": 16,
        "contract_version": "weather_variables_v1",
        "model": "gfs_global",
        "estimated_cost": 5.60,
        "config_hash": "sha256:testconfig",
    }

    call_count = 0

    def fake_fetcher(endpoint_key: str, params: dict[str, Any]) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return {
            "http_status": 200,
            "raw_bytes": synthetic_forecast_16d_bytes,
            "raw_byte_length": len(synthetic_forecast_16d_bytes),
            "raw_sha256": hashlib.sha256(synthetic_forecast_16d_bytes).hexdigest(),
            "rate_limit_headers": {"X-RateLimit-Cost": "5.6", "X-RateLimit-Remaining": "594.4"},
        }

    outcome = execute_task(task=task, sink=sink, fetcher=fake_fetcher, attempt_id="att01", today_vn="2026-11-11")
    assert call_count == 1
    assert get_field(outcome, "status") == "SUCCEEDED"

    base = "raw/open_meteo/weather_forecast/ingest_date=2026-11-11/run_id=daily-20261111-abcd1234/tasks/task0001abcd1234"
    assert sink.exists(f"{base}/attempts/att01/response.json")
    assert sink.exists(f"{base}/attempts/att01/metadata.json")
    assert sink.exists(f"{base}/accepted.json")

    accepted = sink.get_json(f"{base}/accepted.json")
    assert accepted["attempt_id"] == "att01"
    assert accepted["raw_sha256"] == hashlib.sha256(synthetic_forecast_16d_bytes).hexdigest()


def test_tc_wrk_02_worker_idempotency_skips_if_accepted_already_exists(
    tmp_path: Path,
    synthetic_forecast_16d_bytes: bytes,
) -> None:
    """TC-WRK-02: Re-running a task that already has accepted.json makes 0 HTTP calls and preserves the original attempt."""
    from src.weather.storage import LocalSink
    from src.weather.worker import execute_task

    sink = LocalSink(root_dir=tmp_path)
    task = {
        "run_id": "daily-20261111-abcd1234",
        "task_id": "task0001abcd1234",
        "ingest_date": "2026-11-11",
        "mode": "daily_forecast",
        "endpoint_key": "forecast",
        "s3_prefix": "raw/open_meteo/weather_forecast",
        "store_id": 516,
        "store_code": "LC:80439",
        "latitude": 10.746925,
        "longitude": 106.672734,
        "timezone_name": "Asia/Ho_Chi_Minh",
        "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        "coordinate_provenance": "PUBLIC_STORE_LOCATOR",
        "start_date": "2026-11-11",
        "end_date": "2026-11-26",
        "expected_days": 16,
        "contract_version": "weather_variables_v1",
        "model": "gfs_global",
        "estimated_cost": 5.60,
        "config_hash": "sha256:testconfig",
    }

    call_count = 0

    def fake_fetcher(endpoint_key: str, params: dict[str, Any]) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return {
            "http_status": 200,
            "raw_bytes": synthetic_forecast_16d_bytes,
            "raw_byte_length": len(synthetic_forecast_16d_bytes),
            "raw_sha256": hashlib.sha256(synthetic_forecast_16d_bytes).hexdigest(),
            "rate_limit_headers": {"X-RateLimit-Cost": "5.6"},
        }

    # First run
    execute_task(task=task, sink=sink, fetcher=fake_fetcher, attempt_id="att01", today_vn="2026-11-11")
    assert call_count == 1

    # Duplicate delivery / replay -> must NOT call fetcher again!
    second = execute_task(task=task, sink=sink, fetcher=fake_fetcher, attempt_id="att02", today_vn="2026-11-11")
    assert call_count == 1
    assert get_field(second, "status") in ("SUCCEEDED", "SKIPPED_ALREADY_ACCEPTED")


def test_tc_wrk_03_worker_all_null_saves_evidence_without_accepted_marker(
    tmp_path: Path,
    synthetic_all_null_bytes: bytes,
) -> None:
    """TC-WRK-03: On HTTP 200 all-null for closed past, worker saves attempt response+metadata but NEVER writes accepted.json."""
    from src.weather.storage import LocalSink
    from src.weather.worker import execute_task

    sink = LocalSink(root_dir=tmp_path)
    task = {
        "run_id": "backfill-20261111-deadbeef",
        "task_id": "tasknull00000001",
        "ingest_date": "2026-11-11",
        "mode": "historical_backfill",
        "endpoint_key": "historical_forecast",
        "s3_prefix": "raw/open_meteo/historical_forecast",
        "store_id": 516,
        "store_code": "LC:80439",
        "latitude": 10.746925,
        "longitude": 106.672734,
        "timezone_name": "Asia/Ho_Chi_Minh",
        "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
        "coordinate_provenance": "PUBLIC_STORE_LOCATOR",
        "start_date": "2016-01-01",
        "end_date": "2016-01-02",
        "expected_days": 2,
        "contract_version": "weather_variables_v1",
        "model": "gfs_global",
        "estimated_cost": 4.90,
        "config_hash": "sha256:testconfig",
    }

    def fake_null_fetcher(endpoint_key: str, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "http_status": 200,
            "raw_bytes": synthetic_all_null_bytes,
            "raw_byte_length": len(synthetic_all_null_bytes),
            "raw_sha256": hashlib.sha256(synthetic_all_null_bytes).hexdigest(),
            "rate_limit_headers": {"X-RateLimit-Cost": "4.9"},
        }

    outcome = execute_task(task=task, sink=sink, fetcher=fake_null_fetcher, attempt_id="att01", today_vn="2026-11-11")
    assert get_field(outcome, "status") == "FAILED_VALIDATION"

    base = "raw/open_meteo/historical_forecast/ingest_date=2026-11-11/run_id=backfill-20261111-deadbeef/tasks/tasknull00000001"
    assert sink.exists(f"{base}/attempts/att01/response.json")
    assert sink.exists(f"{base}/attempts/att01/metadata.json")
    assert not sink.exists(f"{base}/accepted.json")
