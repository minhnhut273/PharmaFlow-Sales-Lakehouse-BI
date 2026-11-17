"""Offline end-to-end CLI flow: plan -> run -> resume (0 HTTP) -> status, with a fake Open-Meteo."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tests.weather.conftest import build_payload_for_params

NOW = datetime(2026, 11, 11, 3, 0, 0, tzinfo=timezone.utc)  # 10:00 VN


class FakeOpenMeteo:
    """Builds a synthetic response sized to the requested window (SYNTHETIC_TEST_FIXTURE)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, endpoint_key: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((endpoint_key, dict(params)))
        if "forecast_days" in params:
            days = int(params["forecast_days"])
        else:
            days = (datetime.fromisoformat(params["end_date"]) - datetime.fromisoformat(params["start_date"])).days + 1
        body = build_payload_for_params(params, now_utc=NOW)
        return {"http_status": 200, "raw_bytes": body, "raw_sha256": hashlib.sha256(body).hexdigest(),
                "rate_limit_headers": {"X-RateLimit-Cost": "4.9"}, "headers": {}}


def _cli(argv: list[str], tmp_path: Path, rows: list[dict[str, Any]], fake: FakeOpenMeteo) -> dict[str, Any]:
    from src.weather.cli import run_cli

    code, out = run_cli(argv, store_rows_override=rows, runtime_dir=tmp_path, fetcher=fake,
                        sleep=lambda s: None, now_utc=NOW)
    assert code == 0, out
    json.dumps(out)  # output must be JSON serializable
    return out


def test_cli_daily_plan_run_resume_status(tmp_path: Path, pilot_store_rows: list[dict[str, Any]]) -> None:
    fake = FakeOpenMeteo()
    plan = _cli(["plan", "daily", "--cohort", "pilot", "--location-ids", "516,5404"], tmp_path, pilot_store_rows, fake)
    assert plan["task_count"] == 2 and plan["plan_s3_key"].startswith("raw/open_meteo/weather_forecast/")

    again = _cli(["plan", "daily", "--cohort", "pilot", "--location-ids", "516,5404"], tmp_path, [], fake)
    assert again["replayed_frozen_plan"] is True and again["run_id"] == plan["run_id"]

    run = _cli(["run", "--plan", plan["plan_s3_key"], "--sink", "local"], tmp_path, pilot_store_rows, fake)
    assert run["http_calls"] == 2 and run["run_status"] == "SUCCEEDED" and run["summary_key"]
    assert {c[0] for c in fake.calls} == {"forecast"}

    resume = _cli(["resume", "--run-id", plan["run_id"]], tmp_path, pilot_store_rows, fake)
    assert resume["http_calls"] == 0 and len(fake.calls) == 2
    assert {t["status"] for t in resume["tasks"]} == {"SKIPPED_ALREADY_ACCEPTED"}

    status = _cli(["status", "--run-id", plan["run_id"]], tmp_path, pilot_store_rows, fake)
    assert status["run_status"] == "SUCCEEDED" and all(t["accepted_key"] for t in status["tasks"])
    assert len(status["summary_keys"]) == 1


def test_cli_backfill_cross_2022_prefix_layout(tmp_path: Path, pilot_store_rows: list[dict[str, Any]]) -> None:
    from src.weather.storage import LocalSink

    fake = FakeOpenMeteo()
    plan = _cli(["plan", "backfill", "--start-date", "2021-12-25", "--end-date", "2022-01-05",
                 "--location-ids", "516", "--request-id", "pilot-smoke-cross-2022"], tmp_path, pilot_store_rows, fake)
    run_id = plan["run_id"]
    run_prefix = f"raw/open_meteo/historical_weather/ingest_date=2026-11-11/run_id={run_id}"
    assert plan["plan_s3_key"] == f"{run_prefix}/plan.json"

    run = _cli(["run", "--plan", plan["plan_s3_key"]], tmp_path, pilot_store_rows, fake)
    assert run["http_calls"] == 2 and run["run_status"] == "SUCCEEDED"
    assert [c[0] for c in fake.calls] == ["historical_weather", "historical_forecast"]
    assert "models" not in fake.calls[0][1] and fake.calls[1][1]["models"] == "gfs_global"

    sink = LocalSink(tmp_path)
    assert sink.exists(f"{run_prefix}/locations.json")
    assert run["summary_key"].startswith(f"{run_prefix}/summary/")
    era5_task, gfs_task = sink.get_json(plan["plan_s3_key"])["tasks"]
    assert sink.exists(f"{run_prefix}/tasks/{era5_task['task_id']}/accepted.json")
    gfs_accepted = (f"raw/open_meteo/historical_forecast/ingest_date=2026-11-11/run_id={run_id}"
                    f"/tasks/{gfs_task['task_id']}/accepted.json")
    assert sink.exists(gfs_accepted)

    resume = _cli(["resume", "--run-id", run_id], tmp_path, pilot_store_rows, fake)
    assert resume["http_calls"] == 0


def test_cli_s3_sink_requires_config(tmp_path: Path) -> None:
    from src.weather.cli import run_cli

    code, out = run_cli(["run", "--plan", "raw/x/plan.json", "--sink", "s3"], runtime_dir=tmp_path, s3_env={})
    assert code == 1 and "WEATHER_S3_BUCKET" in out["error"]


def test_cli_error_output_redacts_dsn(tmp_path: Path, monkeypatch: Any) -> None:
    from src.weather import cli

    def boom(dsn: str, ids: Any) -> Any:
        raise RuntimeError(f"connection to {dsn} failed")

    monkeypatch.setattr(cli, "read_store_rows", boom)
    code, out = cli.run_cli(["locations", "--cohort", "pilot"], runtime_dir=tmp_path,
                            dsn="postgresql://user:SECRETPASS@host/db")
    assert code == 1 and "SECRETPASS" not in json.dumps(out)
