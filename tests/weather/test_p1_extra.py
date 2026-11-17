"""Supplementary P1 tests (offline, deterministic). Do not replace the TC-* suites."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from tests.weather.conftest import build_payload_for_params, build_synthetic_openmeteo_payload


# ---------------------------------------------------------------- locations


class _FakeCursor:
    description = [(c,) for c in ("store_id", "store_code", "country_code", "latitude", "longitude",
                                  "timezone_name", "store_status", "source")]

    def __init__(self, log: dict[str, Any]) -> None:
        self.log = log

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        self.log["sql"] = sql
        self.log["params"] = params

    def fetchall(self) -> list[tuple]:
        return [(516, "LC:80439", "VN", 10.746925, 106.672734, "Asia/Ho_Chi_Minh", "ACTIVE",
                 "LONGCHAU_PUBLIC_STORE_LOCATOR")]


class _FakeConn:
    def __init__(self, log: dict[str, Any]) -> None:
        self.log = log
        self.read_only = False

    def cursor(self) -> _FakeCursor:
        self.log["read_only_at_query"] = self.read_only
        return _FakeCursor(self.log)

    def rollback(self) -> None:
        self.log["rolled_back"] = True

    def close(self) -> None:
        self.log["closed"] = True


def test_read_store_rows_is_parameterized_and_read_only() -> None:
    from src.weather.locations import read_store_rows

    log: dict[str, Any] = {}
    rows = read_store_rows("postgresql://fake", [516, 104, 516], connect=lambda dsn, **kw: _FakeConn(log))
    assert log["read_only_at_query"] is True
    assert "ANY(%s)" in log["sql"] and "516" not in log["sql"]
    assert log["params"] == ([104, 516],)
    assert log["closed"] is True
    assert rows[0]["store_id"] == 516 and isinstance(rows[0]["latitude"], float)


def test_unmapped_source_is_labeled_unverified(pilot_store_rows: list[dict[str, Any]]) -> None:
    from src.weather.locations import evaluate_locations

    row = dict(pilot_store_rows[0], source="SOME_NEW_SOURCE")
    res = evaluate_locations(rows=[row], requested_store_ids=[row["store_id"]])
    loc = res["eligible_locations"][0]
    assert "UNVERIFIED" in loc["coordinate_verification_status"]


# ------------------------------------------------------------------ limiter


def test_min_interval_seconds_respects_per_minute_limit() -> None:
    from src.weather.limiter import min_interval_seconds

    assert min_interval_seconds(5.6) == pytest.approx(0.56)
    assert min_interval_seconds(6.0, per_minute_limit=60.0) == pytest.approx(6.0)


# ------------------------------------------------------------------ storage


@pytest.mark.parametrize("key", ["../escape.json", "/abs/key.json", "a/../b.json", "a\\b.json", "", "C:/x.json"])
def test_local_sink_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    from src.weather.storage import LocalSink

    with pytest.raises(ValueError):
        LocalSink(tmp_path).put_bytes(key, b"x")


# ------------------------------------------------------------------ planner


def _plan_backfill(rows: list[dict[str, Any]], ids: list[int], start: str, end: str, **kw: Any) -> dict[str, Any]:
    from src.weather.locations import evaluate_locations
    from src.weather.planner import create_backfill_plan

    res = evaluate_locations(rows=rows, requested_store_ids=ids)
    return create_backfill_plan(eligible_locations=res["eligible_locations"],
                                rejected_locations=res["rejected_locations"], request_id=kw.pop("request_id", "r1"),
                                start_date=start, end_date=end, today_vn="2026-11-11", **kw)


def test_cross_2022_plan_files_live_under_first_segment_prefix(pilot_store_rows: list[dict[str, Any]]) -> None:
    from src.weather.planner import build_backfill_run_id, predict_plan_key, task_base_key

    plan = _plan_backfill(pilot_store_rows, [516], "2021-12-25", "2022-01-05", request_id="pilot-cross-2022")
    run_id = plan["run_id"]
    assert run_id == build_backfill_run_id(ingest_date_vn="2026-11-11", request_id="pilot-cross-2022",
                                           cohort_policy_version="pilot_v1", contract_version="weather_variables_v1")
    expected = f"raw/open_meteo/historical_weather/ingest_date=2026-11-11/run_id={run_id}"
    assert plan["plan_s3_key"] == f"{expected}/plan.json"
    assert plan["locations_s3_key"] == f"{expected}/locations.json"
    assert plan["plan_s3_key"] == predict_plan_key("historical_backfill", "2026-11-11", run_id, start_date="2021-12-25")
    assert [t["s3_prefix"] for t in plan["tasks"]] == ["raw/open_meteo/historical_weather",
                                                       "raw/open_meteo/historical_forecast"]
    assert task_base_key(plan["tasks"][1]).startswith("raw/open_meteo/historical_forecast/")
    assert [t["expected_days"] for t in plan["tasks"]] == [7, 5]
    assert plan["estimated_cost_total"] == pytest.approx(8.90)


def test_backfill_clips_start_to_1940(pilot_store_rows: list[dict[str, Any]]) -> None:
    plan = _plan_backfill(pilot_store_rows, [516], "1939-12-25", "1940-01-03")
    assert plan["tasks"][0]["start_date"] == "1940-01-01"


def test_backfill_budget_exceeded_is_rejected_at_plan_time(pilot_store_rows: list[dict[str, Any]]) -> None:
    with pytest.raises(ValueError, match="BUDGET_EXCEEDED_FOR_RUN"):
        _plan_backfill(pilot_store_rows, [516], "2024-01-01", "2024-01-14", used_backfill=7999.0)


def test_daily_subset_cohort_gets_distinct_run_id() -> None:
    from src.weather.planner import build_daily_run_id

    common = dict(schedule_date_vn="2026-11-11", schedule_id="manual", cohort_policy_version="pilot_v1",
                  contract_version="weather_variables_v1", model="gfs_global")
    assert build_daily_run_id(cohort_id="pilot", **common) != build_daily_run_id(cohort_id="pilot:ids=516", **common)


def test_daily_deadline_is_0900_vn_and_before_local_midnight(pilot_store_rows: list[dict[str, Any]]) -> None:
    from src.weather.locations import evaluate_locations
    from src.weather.planner import create_daily_plan

    res = evaluate_locations(rows=pilot_store_rows, requested_store_ids=[516, 5404])
    plan = create_daily_plan(eligible_locations=res["eligible_locations"], rejected_locations=[],
                             scheduled_at_utc=datetime(2026, 11, 10, 23, 0, tzinfo=timezone.utc),
                             schedule_id="daily-0600-vn", cohort_id="pilot")
    by_store = {t["store_id"]: t for t in plan["tasks"]}
    assert by_store[516]["deadline_utc"] == "2026-11-11T02:00:00Z"  # 09:00 VN
    assert by_store[5404]["start_date"] == "2026-11-11"  # Berlin local midnight already passed
    assert by_store[5404]["deadline_utc"] == "2026-11-11T02:00:00Z"


def test_replay_with_wrong_config_hash_raises(tmp_path: Path, pilot_store_rows: list[dict[str, Any]]) -> None:
    from src.weather.planner import load_or_create_plan
    from src.weather.storage import LocalSink

    sink = LocalSink(tmp_path)
    plan = _plan_backfill(pilot_store_rows, [516], "2025-01-01", "2025-01-05", sink=sink)
    assert sink.exists(plan["plan_s3_key"]) and sink.exists(plan["locations_s3_key"])
    with pytest.raises(ValueError, match="config_hash"):
        load_or_create_plan(sink=sink, plan_s3_key=plan["plan_s3_key"], expected_config_hash="sha256:other",
                            db_reader=lambda: [])


# ------------------------------------------------------------------- worker


def _task(**over: Any) -> dict[str, Any]:
    base = {
        "run_id": "backfill-20261111-deadbeef", "task_id": "taskextra0000001", "ingest_date": "2026-11-11",
        "mode": "historical_backfill", "endpoint_key": "historical_forecast",
        "s3_prefix": "raw/open_meteo/historical_forecast", "store_id": 5404, "store_code": "ONYX:PH0014",
        "latitude": 52.527791, "longitude": 13.420219, "timezone_name": "Europe/Berlin",
        "source": "ONYX_CHALLENGE_LOCATION_DIMENSION_UNVERIFIED",
        "coordinate_provenance": "CHALLENGE_DATASET_PERTURBED",
        "coordinate_verification_status": "UNVERIFIED_PERTURBED",
        "eligibility_reason": "ACTIVE_VALID_COORDINATES_AND_TIMEZONE",
        "start_date": "2025-05-01", "end_date": "2025-05-02", "expected_days": 2,
        "contract_version": "weather_variables_v1", "model": "gfs_global",
        "source_type": "HISTORICAL_FORECAST_STITCHED", "estimated_cost": 4.90, "config_hash": "sha256:x",
    }
    base.update(over)
    return base


def _fetch_result(status: int, body: bytes = b"{}", headers: dict[str, str] | None = None) -> Any:
    return lambda ek, params: {"http_status": status, "raw_bytes": body,
                               "raw_sha256": hashlib.sha256(body).hexdigest(),
                               "rate_limit_headers": {}, "headers": headers or {}}


@pytest.mark.parametrize(("status", "expected"), [(429, "DEFERRED"), (503, "RETRYABLE"), (400, "FAILED")])
def test_worker_http_errors_keep_evidence_without_accepted(tmp_path: Path, status: int, expected: str) -> None:
    from src.weather.planner import accepted_key_for, task_base_key
    from src.weather.storage import LocalSink
    from src.weather.worker import execute_task

    sink = LocalSink(tmp_path)
    task = _task()
    out = execute_task(task=task, sink=sink, fetcher=_fetch_result(status, b'{"error":true}', {"Retry-After": "7"}),
                       attempt_id="a1", today_vn="2026-11-11")
    assert out["status"] == expected
    assert sink.exists(f"{task_base_key(task)}/attempts/a1/response.json")
    assert sink.get_json(f"{task_base_key(task)}/attempts/a1/metadata.json")["http_status"] == status
    assert not sink.exists(accepted_key_for(task))
    if status == 429:
        assert out["retry_after_seconds"] == 7


def test_worker_expired_deadline_makes_no_call(tmp_path: Path) -> None:
    from src.weather.storage import LocalSink
    from src.weather.worker import execute_task

    def forbidden(ek: str, params: Any) -> Any:
        raise AssertionError("must not call Open-Meteo after deadline")

    out = execute_task(task=_task(deadline_utc="2026-11-11T02:00:00Z"), sink=LocalSink(tmp_path), fetcher=forbidden,
                       attempt_id="a1", today_vn="2026-11-11",
                       now_utc=datetime(2026, 11, 11, 2, 0, 1, tzinfo=timezone.utc))
    assert out["status"] == "EXPIRED"
    assert list(tmp_path.rglob("*")) == []


def test_worker_metadata_carries_provenance_and_params(tmp_path: Path) -> None:
    from src.weather.planner import task_base_key
    from src.weather.storage import LocalSink
    from src.weather.worker import execute_task

    captured: dict[str, Any] = {}

    def fetcher(ek: str, params: Any) -> Any:
        captured.update(params)
        body = build_payload_for_params(params, utc_offset_seconds=7200)
        captured["_body"] = body
        return _fetch_result(200, body)(ek, params)

    sink = LocalSink(tmp_path)
    task = _task()
    out = execute_task(task=task, sink=sink, fetcher=fetcher, attempt_id="a1", today_vn="2026-11-11")
    body = captured.pop("_body")
    assert out["status"] == "SUCCEEDED"
    assert captured["models"] == "gfs_global" and captured["timeformat"] == "unixtime"
    assert captured["start_date"] == "2025-05-01" and "forecast_days" not in captured
    assert len(captured["hourly"].split(",")) == 44 and len(captured["daily"].split(",")) == 5
    meta = sink.get_json(f"{task_base_key(task)}/attempts/a1/metadata.json")
    assert meta["coordinate_verification_status"] == "UNVERIFIED_PERTURBED"
    assert meta["source"] == "ONYX_CHALLENGE_LOCATION_DIMENSION_UNVERIFIED"
    assert meta["forecast_snapshot_id"] is None
    assert meta["raw_sha256"] == hashlib.sha256(body).hexdigest()
    assert sink.get_bytes(meta["response_key"]) == body


# -------------------------------------------------------------- state / recon


def test_state_store_persists_status_budget_and_runs(tmp_path: Path) -> None:
    from src.weather.state import LocalStateStore

    s1 = LocalStateStore(tmp_path)
    s1.record_task_status("run-x", "t1", "SUCCEEDED", count_attempt=True)
    s1.add_usage("2026-11-11", "daily_forecast", 5.6)
    s1.add_usage("2026-11-11", "historical_backfill", 4.0)
    s1.register_run("run-x", "raw/open_meteo/x/plan.json", "daily_forecast")
    s2 = LocalStateStore(tmp_path)
    assert s2.get_task_statuses("run-x") == {"t1": "SUCCEEDED"}
    assert s2.get_task("run-x", "t1")["attempt_count"] == 1
    assert s2.get_budget("2026-11-11") == {"used_daily": 5.6, "used_backfill": 4.0}
    assert s2.get_run("run-x")["plan_key"] == "raw/open_meteo/x/plan.json"


def test_summary_running_when_tasks_pending_and_written_once(tmp_path: Path) -> None:
    from src.weather.reconcile import summarize_run_outcomes, write_summary
    from src.weather.storage import LocalSink

    running = summarize_run_outcomes(run_id="r", expected_task_ids=["a", "b"], task_statuses={"a": "SUCCEEDED"},
                                     rejected_locations=[])
    assert running["run_status"] == "RUNNING" and running["is_terminal"] is False
    sink = LocalSink(tmp_path)
    plan = {"run_prefix": "raw/open_meteo/weather_forecast/ingest_date=2026-11-11/run_id=r",
            "plan_s3_key": "p", "config_hash": "h", "mode": "daily_forecast"}
    assert write_summary(sink, plan, running) is None
    done = summarize_run_outcomes(run_id="r", expected_task_ids=["a"], task_statuses={"a": "SUCCEEDED"},
                                  rejected_locations=[])
    k1, k2 = write_summary(sink, plan, done), write_summary(sink, plan, done)
    assert k1 == k2 and len(sink.list_keys(f"{plan['run_prefix']}/summary")) == 1


def test_worker_transport_timeout_is_retryable_without_accepted(tmp_path: Path) -> None:
    """Live smoke 2026-11-12 hit a ReadTimeout on archive-api: must be RETRYABLE, not a crash."""
    from src.weather.planner import accepted_key_for, task_base_key
    from src.weather.storage import LocalSink
    from src.weather.worker import execute_task

    def timeout_fetcher(ek: str, params: Any) -> Any:
        raise TimeoutError("The read operation timed out")

    sink = LocalSink(tmp_path)
    task = _task()
    out = execute_task(task=task, sink=sink, fetcher=timeout_fetcher, attempt_id="a1", today_vn="2026-11-11")
    assert out["status"] == "RETRYABLE" and out["http_category"] == "TRANSPORT_ERROR"
    meta = sink.get_json(f"{task_base_key(task)}/attempts/a1/metadata.json")
    assert meta["http_status"] is None and "TimeoutError" in meta["transport_error"]
    assert not sink.exists(f"{task_base_key(task)}/attempts/a1/response.json")
    assert not sink.exists(accepted_key_for(task))


def test_cli_retries_transport_error_then_succeeds(tmp_path: Path, pilot_store_rows: list[dict[str, Any]]) -> None:
    from src.weather.cli import run_cli

    calls = {"n": 0}

    def flaky(ek: str, params: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("read timed out")
        body = build_payload_for_params(params)
        return _fetch_result(200, body)(ek, params)

    now = datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc)
    kw = dict(store_rows_override=pilot_store_rows, runtime_dir=tmp_path, fetcher=flaky, sleep=lambda s: None,
              now_utc=now)
    code, plan = run_cli(["plan", "backfill", "--start-date", "2021-12-25", "--end-date", "2021-12-31",
                          "--location-ids", "516", "--request-id", "flaky"], **kw)
    assert code == 0
    code, run = run_cli(["run", "--plan", plan["plan_s3_key"]], **kw)
    assert code == 0 and run["run_status"] == "SUCCEEDED" and run["http_calls"] == 2
