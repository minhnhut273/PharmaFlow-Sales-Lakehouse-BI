"""P3 offline tests for Lambda handlers (fake S3/SQS, in-memory state, fake Open-Meteo).

Covers the SDD P3 gate cases: duplicate SQS delivery, crash before accepted.json, HTTP 429, budget
exhausted, HTTP 200 all-null, malformed message -> DLQ, and reconciler DLQ handling.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from tests.weather.conftest import build_payload_for_params
from tests.weather.test_p2_s3 import BUCKET, FakeS3

QUEUE_DAILY = "https://sqs.ap-southeast-1.amazonaws.com/123456789012/pharmaflow-dev-weather-daily"
QUEUE_BACKFILL = "https://sqs.ap-southeast-1.amazonaws.com/123456789012/pharmaflow-dev-weather-backfill"
DLQ_DAILY = "https://sqs.ap-southeast-1.amazonaws.com/123456789012/pharmaflow-dev-weather-daily-dlq"
DLQ_BACKFILL = "https://sqs.ap-southeast-1.amazonaws.com/123456789012/pharmaflow-dev-weather-backfill-dlq"
DLQ_SCHED = "https://sqs.ap-southeast-1.amazonaws.com/123456789012/pharmaflow-dev-weather-scheduler-dlq"


class MemState:
    """In-memory stand-in for DynamoStateStore (same method names)."""

    def __init__(self, reserve_reason: str = "OK") -> None:
        self.tasks: dict[tuple[str, str], dict[str, Any]] = {}
        self.runs: dict[str, dict[str, Any]] = {}
        self.reserve_reason = reserve_reason
        self.usage = 0.0

    def acquire_task_lease(self, *, run_id: str, task_id: str, worker_id: str, now_epoch: int,
                           lease_seconds: int = 120) -> bool:
        rec = self.tasks.setdefault((run_id, task_id), {"task_id": task_id})
        if rec.get("lease_owner") not in (None, worker_id) and now_epoch < rec.get("lease_expires_at", 0):
            return False
        rec.update(lease_owner=worker_id, lease_expires_at=now_epoch + lease_seconds)
        return True

    def release_task_lease(self, *, run_id: str, task_id: str, worker_id: str) -> None:
        rec = self.tasks.get((run_id, task_id), {})
        if rec.get("lease_owner") == worker_id:
            rec.pop("lease_owner", None)
            rec.pop("lease_expires_at", None)

    def clear_expired_lease(self, *, run_id: str, task_id: str, now_epoch: int) -> bool:
        rec = self.tasks.get((run_id, task_id), {})
        rec.pop("lease_owner", None)
        rec.pop("lease_expires_at", None)
        return True

    def record_task_status(self, run_id: str, task_id: str, status: str, **details: Any) -> dict[str, Any]:
        rec = self.tasks.setdefault((run_id, task_id), {"task_id": task_id})
        if details.pop("count_attempt", False):
            rec["attempt_count"] = rec.get("attempt_count", 0) + 1
        rec.update({k: v for k, v in details.items() if v is not None}, status=status)
        return rec

    def seed_task(self, run_id: str, task_id: str, **fields: Any) -> None:
        rec = self.tasks.setdefault((run_id, task_id), {"task_id": task_id})
        rec.setdefault("status", "PLANNED")
        rec.update(fields)

    def get_task(self, run_id: str, task_id: str) -> dict[str, Any] | None:
        return self.tasks.get((run_id, task_id))

    def get_task_statuses(self, run_id: str) -> dict[str, str]:
        return {t: r["status"] for (r_id, t), r in self.tasks.items() if r_id == run_id and r.get("status")}

    def list_tasks(self, run_id: str) -> list[dict[str, Any]]:
        return [r for (r_id, _), r in self.tasks.items() if r_id == run_id]

    def get_budget(self, date_vn: str) -> dict[str, float]:
        return {"used_daily": 0.0, "used_backfill": 0.0}

    def reserve_units(
        self, *, date_vn: str, minute_key: str, mode: str, units: float, hour_key: str | None = None
    ) -> dict[str, Any]:
        if self.reserve_reason != "OK":
            return {"allowed": False, "reason": self.reserve_reason}
        self.usage += units
        return {"allowed": True, "reason": "OK"}

    def adjust_usage(self, *, date_vn: str, mode: str, delta: float, hour_key: str | None = None) -> None:
        self.usage += delta

    def register_run(self, run_id: str, plan_key: str, mode: str, **details: Any) -> dict[str, Any]:
        rec = self.runs.setdefault(run_id, {"run_id": run_id})
        rec.update(plan_key=plan_key, mode=mode, active=True, **details)
        return rec

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.runs.get(run_id)

    def list_active_runs(self) -> list[dict[str, Any]]:
        return [r for r in self.runs.values() if r.get("active")]

    def mark_run_terminal(self, run_id: str, *, run_status: str, summary_key: str | None) -> None:
        self.runs[run_id].update(active=False, run_status=run_status, terminal_summary_key=summary_key)


class FakeSQS:
    def __init__(self) -> None:
        self.sent: dict[str, list[dict[str, Any]]] = {}
        self.visibility: list[dict[str, Any]] = []
        self.queues: dict[str, list[dict[str, Any]]] = {}
        self.deleted: list[str] = []

    def send_message_batch(self, *, QueueUrl: str, Entries: list[dict[str, Any]]) -> dict[str, Any]:
        self.sent.setdefault(QueueUrl, []).extend(Entries)
        return {"Successful": [{"Id": e["Id"]} for e in Entries], "Failed": []}

    def change_message_visibility(self, **kw: Any) -> dict[str, Any]:
        self.visibility.append(kw)
        return {}

    def receive_message(self, *, QueueUrl: str, **kw: Any) -> dict[str, Any]:
        msgs, self.queues[QueueUrl] = self.queues.get(QueueUrl, []), []
        return {"Messages": msgs} if msgs else {}

    def delete_message(self, *, QueueUrl: str, ReceiptHandle: str) -> dict[str, Any]:
        self.deleted.append(ReceiptHandle)
        return {}


class FakeOM:
    def __init__(self, status: int = 200, all_null: bool = False, headers: dict[str, str] | None = None) -> None:
        self.calls = 0
        self.status, self.all_null, self.headers = status, all_null, headers or {}

    def __call__(self, endpoint_key: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        days = int(params["forecast_days"]) if "forecast_days" in params else (
            datetime.fromisoformat(params["end_date"]) - datetime.fromisoformat(params["start_date"])).days + 1
        body = (build_payload_for_params(params, all_null_core=self.all_null)
                if self.status == 200 else b'{"error":true,"reason":"Too many requests"}')
        return {"http_status": self.status, "raw_bytes": body, "raw_sha256": hashlib.sha256(body).hexdigest(),
                "rate_limit_headers": {"X-RateLimit-Cost": "5.6"}, "headers": self.headers}


@pytest.fixture()
def env(monkeypatch: Any, pilot_store_rows: list[dict]) -> dict[str, Any]:
    from src.weather import cli, handlers

    for k, v in {"WEATHER_S3_BUCKET": BUCKET, "WEATHER_TABLE": "t", "WEATHER_DAILY_QUEUE_URL": QUEUE_DAILY,
                 "WEATHER_BACKFILL_QUEUE_URL": QUEUE_BACKFILL, "WEATHER_DAILY_DLQ_URL": DLQ_DAILY,
                 "WEATHER_BACKFILL_DLQ_URL": DLQ_BACKFILL, "WEATHER_SCHEDULER_DLQ_URL": DLQ_SCHED,
                 "WEATHER_NEON_DSN_PARAM": "/p", "AWS_REGION": "ap-southeast-1"}.items():
        monkeypatch.setenv(k, v)
    s3, sqs, state, om = FakeS3(), FakeSQS(), MemState(), FakeOM()
    calls = {"neon": 0, "ssm": 0}

    def rows(dsn: str, ids: Any) -> list[dict]:
        calls["neon"] += 1
        return [r for r in pilot_store_rows if r["store_id"] in set(ids)]

    def dsn() -> str:
        calls["ssm"] += 1
        return "postgresql://fake"

    from src.weather.storage import S3Sink

    monkeypatch.setattr(cli, "read_store_rows", rows)
    monkeypatch.setattr(handlers, "_read_neon_dsn", dsn)
    monkeypatch.setattr(handlers, "_sink", lambda: S3Sink(bucket=BUCKET, client=s3, region="ap-southeast-1"))
    monkeypatch.setattr(handlers, "_state", lambda: state)
    monkeypatch.setattr(handlers, "_fetcher", lambda: om)
    monkeypatch.setattr(handlers, "client", lambda name: sqs)
    handlers._plan_cache.clear()
    return {"s3": s3, "sqs": sqs, "state": state, "om": om, "calls": calls, "handlers": handlers}


def _records(sqs: FakeSQS, queue: str) -> list[dict[str, Any]]:
    arn = "arn:aws:sqs:ap-southeast-1:123456789012:" + queue.rsplit("/", 1)[-1]
    return [{"messageId": e["Id"], "receiptHandle": f"rh-{e['Id']}", "body": e["MessageBody"],
             "eventSourceARN": arn, "attributes": {"ApproximateReceiveCount": "1"}} for e in sqs.sent[queue]]


class Ctx:
    aws_request_id = "req-1"


def test_smoke_dry_run_touches_nothing(env: dict[str, Any]) -> None:
    h = env["handlers"]
    for fn in (h.planner_handler, h.worker_handler, h.reconciler_handler):
        assert fn({"dry_run": True}, Ctx())["ok"] is True
    assert env["s3"].objects == {} and env["sqs"].sent == {} and env["calls"] == {"neon": 0, "ssm": 0}


def test_planner_dispatch_then_replay_without_neon(env: dict[str, Any]) -> None:
    h, sqs = env["handlers"], env["sqs"]
    event = {"mode": "daily_forecast", "cohort_id": "pilot", "location_ids": [516, 5404], "schedule_id": "manual"}
    out = h.planner_handler(event, Ctx())
    assert out["dispatched"] == 2 and out["replayed_frozen_plan"] is False and out["neon_read"] is True
    msgs = [json.loads(e["MessageBody"]) for e in sqs.sent[QUEUE_DAILY]]
    assert all(set(m) == h.MESSAGE_KEYS for m in msgs)
    assert "postgresql" not in json.dumps(sqs.sent) and "latitude" not in json.dumps(sqs.sent)
    assert {t["status"] for t in env["state"].tasks.values()} == {"PLANNED"}
    assert env["state"].runs[out["run_id"]]["expected_tasks"] == 2
    assert env["calls"] == {"neon": 1, "ssm": 1}

    again = h.planner_handler(event, Ctx())
    assert again["replayed_frozen_plan"] is True and again["run_id"] == out["run_id"] and again["neon_read"] is False
    assert env["calls"] == {"neon": 1, "ssm": 1}  # frozen plan: no SSM, no Neon


def test_planner_handles_scheduler_placeholder_gracefully(env: dict[str, Any]) -> None:
    """When EventBridge Scheduler passes literal '<aws.scheduler.scheduled-time>', planner must not crash."""
    h = env["handlers"]
    event = {
        "mode": "daily_forecast",
        "cohort_id": "pilot",
        "location_ids": [516],
        "schedule_id": "daily-0600-vn",
        "scheduled_at_utc": "<aws.scheduler.scheduled-time>",
    }
    out = h.planner_handler(event, Ctx())
    assert out["dispatched"] == 1
    assert out["run_id"].startswith("daily-")
    assert env["calls"] == {"neon": 1, "ssm": 1}


def _plan_daily(env: dict[str, Any]) -> list[dict[str, Any]]:
    env["handlers"].planner_handler({"mode": "daily_forecast", "location_ids": [516], "schedule_id": "manual"},
                                    Ctx())
    return _records(env["sqs"], QUEUE_DAILY)


def test_worker_success_then_duplicate_delivery_makes_no_http_call(env: dict[str, Any]) -> None:
    h, om = env["handlers"], env["om"]
    recs = _plan_daily(env)
    assert h.worker_handler({"Records": recs}, Ctx()) == {"batchItemFailures": []}
    assert om.calls == 1 and len([k for k in env["s3"].objects if k.endswith("accepted.json")]) == 1
    assert h.worker_handler({"Records": recs}, Ctx()) == {"batchItemFailures": []}
    assert om.calls == 1


def test_worker_crash_before_accepted_retries_into_single_marker(env: dict[str, Any]) -> None:
    h, s3 = env["handlers"], env["s3"]
    recs = _plan_daily(env)
    original = s3.put_object
    state = {"crashed": False}

    def crash_once(**kw: Any) -> Any:
        if kw["Key"].endswith("accepted.json") and not state["crashed"]:
            state["crashed"] = True
            raise RuntimeError("simulated crash before accepted.json")
        return original(**kw)

    s3.put_object = crash_once  # type: ignore[method-assign]
    first = h.worker_handler({"Records": recs}, Ctx())
    assert first["batchItemFailures"] == [{"itemIdentifier": recs[0]["messageId"]}]
    assert not [k for k in s3.objects if k.endswith("accepted.json")]
    assert h.worker_handler({"Records": recs}, Ctx()) == {"batchItemFailures": []}
    accepted = [k for k in s3.objects if k.endswith("accepted.json")]
    attempts = {k.split("/attempts/")[1].split("/")[0] for k in s3.objects if "/attempts/" in k}
    assert len(accepted) == 1 and len(attempts) == 2 and env["om"].calls == 2
    task = next(iter(env["state"].tasks.values()))
    assert "lease_owner" not in task  # lease released even after the crash


def test_worker_429_defers_with_retry_after(env: dict[str, Any]) -> None:
    h = env["handlers"]
    env["om"].status, env["om"].headers = 429, {"Retry-After": "30"}
    recs = _plan_daily(env)
    out = h.worker_handler({"Records": recs}, Ctx())
    assert out["batchItemFailures"] == [{"itemIdentifier": recs[0]["messageId"]}]
    vis = env["sqs"].visibility[0]
    assert vis["QueueUrl"] == QUEUE_DAILY and 31 <= vis["VisibilityTimeout"] <= 35
    assert not [k for k in env["s3"].objects if k.endswith("accepted.json")]


def test_worker_budget_exhausted_defers_without_http(env: dict[str, Any]) -> None:
    h = env["handlers"]
    env["state"].reserve_reason = "BUDGET_EXCEEDED_FOR_RUN"
    recs = _plan_daily(env)
    out = h.worker_handler({"Records": recs}, Ctx())
    assert out["batchItemFailures"] and env["om"].calls == 0
    assert env["sqs"].visibility[0]["VisibilityTimeout"] == 3600
    assert next(iter(env["state"].tasks.values()))["status"] == "DEFERRED"


def test_worker_minute_limit_defers_to_next_minute(env: dict[str, Any]) -> None:
    h = env["handlers"]
    env["state"].reserve_reason = "MINUTE_LIMIT"
    out = h.worker_handler({"Records": _plan_daily(env)}, Ctx())
    assert out["batchItemFailures"] and env["om"].calls == 0
    assert 1 <= env["sqs"].visibility[0]["VisibilityTimeout"] <= 70


def test_worker_all_null_closed_past_is_terminal_ack(env: dict[str, Any]) -> None:
    h = env["handlers"]
    env["om"].all_null = True
    h.planner_handler({"mode": "historical_backfill", "request_id": "nulltest", "start_date": "2024-01-01",
                       "end_date": "2024-01-02", "location_ids": [516]}, Ctx())
    recs = _records(env["sqs"], QUEUE_BACKFILL)
    assert h.worker_handler({"Records": recs}, Ctx()) == {"batchItemFailures": []}
    assert next(iter(env["state"].tasks.values()))["status"] == "FAILED_VALIDATION"
    assert not [k for k in env["s3"].objects if k.endswith("accepted.json")]
    assert [k for k in env["s3"].objects if k.endswith("response.json")]


@pytest.mark.parametrize("mutate", ["not-json", "bad_hash", "bad_index", "extra_key"])
def test_worker_malformed_message_is_reported_as_failure(env: dict[str, Any], mutate: str) -> None:
    h = env["handlers"]
    rec = _plan_daily(env)[0]
    body = json.loads(rec["body"])
    if mutate == "not-json":
        rec["body"] = "{oops"
    else:
        if mutate == "bad_hash":
            body["config_hash"] = "sha256:wrong"
        elif mutate == "bad_index":
            body["task_index"] = 99
        else:
            body["secret"] = "x"
        rec["body"] = json.dumps(body)
    assert h.worker_handler({"Records": [rec]}, Ctx()) == {"batchItemFailures": [{"itemIdentifier": rec["messageId"]}]}
    assert env["om"].calls == 0
    vis = env["sqs"].visibility[-1]
    assert vis["QueueUrl"] == QUEUE_DAILY and 20 <= vis["VisibilityTimeout"] <= 40  # fast path to the DLQ


def test_reconciler_marks_dlq_task_and_writes_terminal_summary(env: dict[str, Any]) -> None:
    h, sqs, state = env["handlers"], env["sqs"], env["state"]
    env["handlers"].planner_handler({"mode": "daily_forecast", "location_ids": [516, 5404], "schedule_id": "manual"},
                                    Ctx())
    recs = _records(sqs, QUEUE_DAILY)
    h.worker_handler({"Records": [recs[0]]}, Ctx())  # first task succeeds
    sqs.queues[DLQ_DAILY] = [{"MessageId": "m-dlq", "ReceiptHandle": "rh-dlq", "Body": recs[1]["body"]},
                             {"MessageId": "m-bad", "ReceiptHandle": "rh-bad", "Body": "not json"}]
    out = h.reconciler_handler({}, Ctx())
    assert out["dlq"]["WEATHER_DAILY_DLQ_URL"] == {"received": 2, "marked_dlq": 1, "ignored": 1}
    assert set(sqs.deleted) == {"rh-dlq", "rh-bad"}
    run = out["runs"][0]
    assert run["run_status"] == "PARTIAL" and run["terminal"] is True and run["summary_key"]
    assert state.list_active_runs() == []
    assert run["summary_key"] in env["s3"].objects


def test_reconciler_ignores_dlq_message_for_already_accepted_task(env: dict[str, Any]) -> None:
    h, sqs = env["handlers"], env["sqs"]
    recs = _plan_daily(env)
    h.worker_handler({"Records": recs}, Ctx())
    sqs.queues[DLQ_DAILY] = [{"MessageId": "dup", "ReceiptHandle": "rh-dup", "Body": recs[0]["body"]}]
    out = h.reconciler_handler({}, Ctx())
    assert out["dlq"]["WEATHER_DAILY_DLQ_URL"]["ignored"] == 1
    assert out["runs"][0]["run_status"] == "SUCCEEDED"


def test_reconciler_expires_daily_task_after_deadline(env: dict[str, Any], monkeypatch: Any) -> None:
    from src.weather import handlers

    h = env["handlers"]
    _plan_daily(env)
    real = handlers.datetime

    class Later(real):  # type: ignore[misc, valid-type]
        @classmethod
        def now(cls, tz: Any = None) -> Any:
            return real.now(timezone.utc).replace(year=real.now().year + 1)

    monkeypatch.setattr(handlers, "datetime", Later)
    out = h.reconciler_handler({}, Ctx())
    assert out["runs"][0]["expired_now"] == 1 and out["runs"][0]["run_status"] == "FAILED"
