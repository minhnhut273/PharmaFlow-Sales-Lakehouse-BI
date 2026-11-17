"""Unit tests for src/weather/planner.py (TC-PLN-01 .. TC-PLN-08)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from tests.weather.conftest import get_field


def test_tc_pln_01_deterministic_run_id_and_task_id() -> None:
    """TC-PLN-01: Identical inputs generate the exact same run_id and task_id; refresh_seq creates new run_id."""
    from src.weather.planner import build_daily_run_id, build_backfill_run_id, build_task_id

    r1 = build_daily_run_id(
        schedule_date_vn="2026-11-11",
        schedule_id="daily-0600-vn",
        cohort_id="pilot",
        cohort_policy_version="pilot_v1",
        contract_version="weather_variables_v1",
        model="gfs_global",
    )
    r2 = build_daily_run_id(
        schedule_date_vn="2026-11-11",
        schedule_id="daily-0600-vn",
        cohort_id="pilot",
        cohort_policy_version="pilot_v1",
        contract_version="weather_variables_v1",
        model="gfs_global",
    )
    r_refresh = build_daily_run_id(
        schedule_date_vn="2026-11-11",
        schedule_id="daily-0600-vn",
        cohort_id="pilot",
        cohort_policy_version="pilot_v1",
        contract_version="weather_variables_v1",
        model="gfs_global",
        refresh_seq=1,
    )

    assert r1 == r2
    assert r1.startswith("daily-20261111-")
    assert r_refresh != r1

    b1 = build_backfill_run_id(
        ingest_date_vn="2026-11-11",
        request_id="pilot-cross-2022",
        cohort_policy_version="pilot_v1",
        contract_version="weather_variables_v1",
    )
    b2 = build_backfill_run_id(
        ingest_date_vn="2026-11-11",
        request_id="pilot-cross-2022",
        cohort_policy_version="pilot_v1",
        contract_version="weather_variables_v1",
    )
    assert b1 == b2
    assert b1.startswith("backfill-20261111-")

    t1 = build_task_id(
        run_id=r1,
        store_id=104,
        endpoint_key="forecast",
        start_date="2026-11-11",
        end_date="2026-11-26",
        contract_version="weather_variables_v1",
        model="gfs_global",
    )
    t2 = build_task_id(
        run_id=r1,
        store_id=104,
        endpoint_key="forecast",
        start_date="2026-11-11",
        end_date="2026-11-26",
        contract_version="weather_variables_v1",
        model="gfs_global",
    )
    assert t1 == t2
    assert len(t1) == 16


def test_tc_pln_02_daily_forecast_plan_per_store_timezone(pilot_store_rows: list[dict[str, Any]]) -> None:
    """TC-PLN-02: Daily plan computes 16-day window in each store's own timezone and routes to forecast."""
    from src.weather.locations import evaluate_locations
    from src.weather.planner import create_daily_plan

    # At 2026-11-10T22:30:00Z:
    # - In Vietnam (UTC+7, 05:30): local date is already 2026-11-11 (window 2026-11-11 .. 2026-11-26)
    # - In Berlin (UTC+1, 23:30): local date is still 2026-11-10 (window 2026-11-10 .. 2026-11-25)
    # (At 23:00Z Berlin is exactly 00:00 on 2026-11-11; see test_p1_extra.py deadline test.)
    planned_at = datetime(2026, 11, 10, 22, 30, 0, tzinfo=timezone.utc)
    loc_result = evaluate_locations(rows=pilot_store_rows, requested_store_ids=[104, 5404])

    plan = create_daily_plan(
        eligible_locations=get_field(loc_result, "eligible_locations"),
        rejected_locations=get_field(loc_result, "rejected_locations"),
        scheduled_at_utc=planned_at,
        schedule_id="daily-0600-vn",
        cohort_id="pilot",
    )

    tasks = {get_field(t, "store_id"): t for t in get_field(plan, "tasks")}
    assert len(tasks) == 2

    vn_task = tasks[104]
    assert get_field(vn_task, "endpoint_key") == "forecast"
    assert get_field(vn_task, "s3_prefix") == "raw/open_meteo/weather_forecast"
    assert get_field(vn_task, "contract_version") == "weather_variables_v1"
    assert get_field(vn_task, "model") == "gfs_global"
    assert get_field(vn_task, "start_date") == "2026-11-11"
    assert get_field(vn_task, "end_date") == "2026-11-26"
    assert get_field(vn_task, "estimated_cost") == pytest.approx(5.60)

    berlin_task = tasks[5404]
    assert get_field(berlin_task, "start_date") == "2026-11-10"
    assert get_field(berlin_task, "end_date") == "2026-11-25"
    assert get_field(berlin_task, "estimated_cost") == pytest.approx(5.60)


def test_tc_pln_03_backfill_boundary_split_at_2022_01_01(pilot_store_rows: list[dict[str, Any]]) -> None:
    """TC-PLN-03: Backfill crossing 2022-01-01 splits cleanly into ERA5 (<2022) and GFS (>=2022) tasks."""
    from src.weather.locations import evaluate_locations
    from src.weather.planner import create_backfill_plan

    loc_result = evaluate_locations(rows=pilot_store_rows, requested_store_ids=[104])
    plan = create_backfill_plan(
        eligible_locations=get_field(loc_result, "eligible_locations"),
        rejected_locations=get_field(loc_result, "rejected_locations"),
        request_id="pilot-cross-2022",
        start_date="2021-12-20",
        end_date="2022-01-10",
        today_vn="2026-11-11",
    )

    tasks = list(get_field(plan, "tasks"))
    assert len(tasks) == 2

    t_era5 = tasks[0]
    assert get_field(t_era5, "start_date") == "2021-12-20"
    assert get_field(t_era5, "end_date") == "2021-12-31"
    assert get_field(t_era5, "endpoint_key") == "historical_weather"
    assert get_field(t_era5, "s3_prefix") == "raw/open_meteo/historical_weather"
    assert get_field(t_era5, "contract_version") == "weather_era5_v1"
    assert get_field(t_era5, "source_type") == "HISTORICAL_ERA5_REANALYSIS"
    assert get_field(t_era5, "estimated_cost") == pytest.approx(4.00)

    t_gfs = tasks[1]
    assert get_field(t_gfs, "start_date") == "2022-01-01"
    assert get_field(t_gfs, "end_date") == "2022-01-10"
    assert get_field(t_gfs, "endpoint_key") == "historical_forecast"
    assert get_field(t_gfs, "s3_prefix") == "raw/open_meteo/historical_forecast"
    assert get_field(t_gfs, "contract_version") == "weather_variables_v1"
    assert get_field(t_gfs, "model") == "gfs_global"
    assert get_field(t_gfs, "source_type") == "HISTORICAL_FORECAST_STITCHED"
    assert get_field(t_gfs, "estimated_cost") == pytest.approx(4.90)


def test_tc_pln_04_backfill_14_day_contiguous_chunks(pilot_store_rows: list[dict[str, Any]]) -> None:
    """TC-PLN-04: A 35-day backfill range is split into 3 contiguous chunks of 14 + 14 + 7 days."""
    from src.weather.locations import evaluate_locations
    from src.weather.planner import create_backfill_plan

    loc_result = evaluate_locations(rows=pilot_store_rows, requested_store_ids=[104])
    plan = create_backfill_plan(
        eligible_locations=get_field(loc_result, "eligible_locations"),
        rejected_locations=get_field(loc_result, "rejected_locations"),
        request_id="chunk-test-35d",
        start_date="2025-01-01",
        end_date="2025-02-04",
        today_vn="2026-11-11",
    )

    tasks = list(get_field(plan, "tasks"))
    windows = [(get_field(t, "start_date"), get_field(t, "end_date")) for t in tasks]
    assert windows == [
        ("2025-01-01", "2025-01-14"),
        ("2025-01-15", "2025-01-28"),
        ("2025-01-29", "2025-02-04"),
    ]


@pytest.mark.parametrize(
    ("start_date", "end_date", "expected_match"),
    [
        ("2025-02-10", "2025-02-01", "start_date"),
        ("2026-11-01", "2026-11-11", "today"),
        ("1935-01-01", "1939-12-31", "UNAVAILABLE_BEFORE_MODEL_COVERAGE"),
    ],
)
def test_tc_pln_05_backfill_invalid_date_windows_rejected(
    pilot_store_rows: list[dict[str, Any]],
    start_date: str,
    end_date: str,
    expected_match: str,
) -> None:
    """TC-PLN-05: Backfill rejects inverted dates, future/today dates, or < 1940-01-01."""
    from src.weather.locations import evaluate_locations
    from src.weather.planner import create_backfill_plan

    loc_result = evaluate_locations(rows=pilot_store_rows, requested_store_ids=[104])
    with pytest.raises(ValueError, match=expected_match):
        create_backfill_plan(
            eligible_locations=get_field(loc_result, "eligible_locations"),
            rejected_locations=get_field(loc_result, "rejected_locations"),
            request_id="bad-window",
            start_date=start_date,
            end_date=end_date,
            today_vn="2026-11-11",
        )


def test_tc_pln_06_queue_message_contains_only_lightweight_references() -> None:
    """TC-PLN-06: Queue message payload includes only lightweight references and zero secrets/coordinates."""
    from src.weather.planner import build_task_queue_message

    msg = build_task_queue_message(
        run_id="daily-20261111-a1b2c3d4",
        task_id="9f8e7d6c5b4a3210",
        task_index=0,
        plan_s3_key="raw/open_meteo/weather_forecast/ingest_date=2026-11-11/run_id=daily-20261111-a1b2c3d4/plan.json",
        config_hash="sha256:123456",
    )

    assert set(msg.keys()) == {
        "message_schema_version",
        "run_id",
        "task_id",
        "task_index",
        "plan_s3_key",
        "config_hash",
    }
    assert msg["message_schema_version"] == "1"


def test_tc_pln_07_replay_uses_frozen_plan_without_requerying_db(
    tmp_path: Path,
    pilot_store_rows: list[dict[str, Any]],
) -> None:
    """TC-PLN-07: If plan.json already exists for run_id, replay loads frozen plan without calling DB reader and filters out accepted tasks."""
    from src.weather.locations import evaluate_locations
    from src.weather.planner import create_backfill_plan, load_or_create_plan
    from src.weather.storage import LocalSink

    sink = LocalSink(root_dir=tmp_path)
    loc_result = evaluate_locations(rows=pilot_store_rows, requested_store_ids=[104, 516])
    initial_plan = create_backfill_plan(
        eligible_locations=get_field(loc_result, "eligible_locations"),
        rejected_locations=get_field(loc_result, "rejected_locations"),
        request_id="replay-test-01",
        start_date="2025-01-01",
        end_date="2025-01-05",
        today_vn="2026-11-11",
    )

    run_id = get_field(initial_plan, "run_id")
    plan_key = get_field(initial_plan, "plan_s3_key")
    tasks = list(get_field(initial_plan, "tasks"))
    assert len(tasks) == 2

    # Persist frozen plan and mark the first task as already accepted
    sink.put_json(plan_key, initial_plan if isinstance(initial_plan, dict) else initial_plan.__dict__)
    t0_id = get_field(tasks[0], "task_id")
    accepted_key = (
        f"raw/open_meteo/historical_forecast/ingest_date=2026-11-11/"
        f"run_id={run_id}/tasks/{t0_id}/accepted.json"
    )
    sink.put_json_if_absent(accepted_key, {"attempt_id": "att01", "status": "SUCCEEDED"})

    db_called = False

    def forbidden_db_reader() -> list[dict[str, Any]]:
        nonlocal db_called
        db_called = True
        raise AssertionError("DB reader must NOT be called when frozen plan.json already exists!")

    replayed = load_or_create_plan(
        sink=sink,
        plan_s3_key=plan_key,
        expected_config_hash=get_field(initial_plan, "config_hash"),
        db_reader=forbidden_db_reader,
    )

    assert db_called is False
    pending = list(get_field(replayed, "pending_tasks"))
    assert len(pending) == 1
    assert get_field(pending[0], "task_id") == get_field(tasks[1], "task_id")


def test_tc_pln_08_dry_run_does_not_write_to_sink(
    tmp_path: Path,
    pilot_store_rows: list[dict[str, Any]],
) -> None:
    """TC-PLN-08: In dry_run=True mode, planner returns plan & cost estimate without writing files to sink."""
    from src.weather.locations import evaluate_locations
    from src.weather.planner import create_daily_plan
    from src.weather.storage import LocalSink

    sink = LocalSink(root_dir=tmp_path)
    loc_result = evaluate_locations(rows=pilot_store_rows, requested_store_ids=[104])
    plan = create_daily_plan(
        eligible_locations=get_field(loc_result, "eligible_locations"),
        rejected_locations=get_field(loc_result, "rejected_locations"),
        scheduled_at_utc=datetime(2026, 11, 10, 23, 0, 0, tzinfo=timezone.utc),
        schedule_id="daily-0600-vn",
        cohort_id="pilot",
        sink=sink,
        dry_run=True,
    )

    plan_key = get_field(plan, "plan_s3_key")
    assert not sink.exists(plan_key)
    assert list(tmp_path.rglob("*")) == []

