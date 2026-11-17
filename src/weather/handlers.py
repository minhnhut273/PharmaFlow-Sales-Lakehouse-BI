"""AWS Lambda entrypoints (P3): planner_handler, worker_handler, reconciler_handler.

All three use the function's execution role directly (no assume-role). Logs are single-line JSON with
run/task identifiers, statuses and costs only; the Neon DSN and credentials are never logged.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.weather import __version__

QUEUE_FOR_MODE = {"daily_forecast": "WEATHER_DAILY_QUEUE_URL", "historical_backfill": "WEATHER_BACKFILL_QUEUE_URL"}
DLQ_ENVS = ("WEATHER_DAILY_DLQ_URL", "WEATHER_BACKFILL_DLQ_URL", "WEATHER_SCHEDULER_DLQ_URL")
MESSAGE_KEYS = {"message_schema_version", "run_id", "task_id", "task_index", "plan_s3_key", "config_hash"}
WORKER_LEASE_SECONDS = 180
MAX_VISIBILITY_SECONDS = 43200
# Unexpected errors (malformed message, transient AWS error) retry after ~30s instead of the 900s queue
# visibility timeout, so a poison message reaches the DLQ after maxReceiveCount=5 in a few minutes.
ERROR_RETRY_MIN_SECONDS = 20
ERROR_RETRY_MAX_SECONDS = 40
DLQ_DRAIN_LIMIT = 50

_clients: dict[str, Any] = {}
_plan_cache: dict[str, dict[str, Any]] = {}
_http_session: Any = None


# --------------------------------------------------------------------- infra


def log(event: str, **fields: Any) -> None:
    print(json.dumps({"event": event, "code_version": __version__, **fields}, ensure_ascii=False, default=str))


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing environment variable {name}")
    return value


def client(name: str) -> Any:
    if name not in _clients:
        import boto3
        from botocore.config import Config

        _clients[name] = boto3.client(name, config=Config(retries={"mode": "standard", "total_max_attempts": 5},
                                                          connect_timeout=5, read_timeout=30))
    return _clients[name]


def _sink() -> Any:
    from src.weather.storage import S3Sink

    return S3Sink(bucket=_env("WEATHER_S3_BUCKET"), client=client("s3"), region=os.environ.get("AWS_REGION"))


def _state() -> Any:
    from src.weather.state import DynamoStateStore

    return DynamoStateStore(table=_env("WEATHER_TABLE"), client=client("dynamodb"))


def _fetcher() -> Callable[[str, Mapping[str, Any]], Mapping[str, Any]]:
    global _http_session
    from src.weather.open_meteo import _default_session, fetch_open_meteo

    if _http_session is None:
        _http_session = _default_session()
    return lambda ek, params: fetch_open_meteo(endpoint_key=ek, params=params, session=_http_session)


def _read_neon_dsn() -> str:
    resp = client("ssm").get_parameter(Name=_env("WEATHER_NEON_DSN_PARAM"), WithDecryption=True)
    return resp["Parameter"]["Value"]


def _context(sink: Any, state: Any, *, dsn_provider: Callable[[], str] | None = None) -> Any:
    from src.weather.cli import Context

    ctx = Context(runtime_dir=Path("/tmp/weather"), store_rows_override=None, fetcher=None, sleep=time.sleep,
                  now_utc=None, dsn=None, dsn_provider=dsn_provider)
    ctx.attach(sink=sink, state=state, kind="s3")
    return ctx


def _smoke(name: str) -> dict[str, Any]:
    """{"dry_run": true}: import + runtime checks only. No Neon, no Open-Meteo, no AWS calls, no writes."""
    import importlib
    from zoneinfo import ZoneInfo

    from src.weather.config import load_cohorts_config, load_variable_contract

    modules = ["aws_session", "cli", "config", "grid", "limiter", "locations", "open_meteo", "planner", "reconcile",
               "runner", "state", "storage", "validation", "worker"]
    for mod in modules:
        importlib.import_module(f"src.weather.{mod}")

    import boto3
    import botocore.session
    import psycopg
    import requests
    import yaml

    put_shape = botocore.session.get_session().get_service_model("s3").operation_model("PutObject").input_shape
    gfs, era5 = load_variable_contract("weather_variables_v1"), load_variable_contract("weather_era5_v1")
    timezones = ["Asia/Ho_Chi_Minh", "Asia/Jakarta", "Europe/Berlin", "Europe/Belgrade"]
    out = {"ok": True, "function": name, "code_version": __version__,
           "contracts": {"weather_variables_v1": gfs["n_variables"], "weather_era5_v1": era5["n_variables"]},
           "cohort_policy_version": load_cohorts_config()["cohort_policy_version"],
           "modules_imported": len(modules),
           "libs": {"boto3": boto3.__version__, "psycopg": psycopg.__version__, "psycopg_impl": psycopg.pq.__impl__,
                    "libpq": psycopg.pq.version(), "requests": requests.__version__, "pyyaml": yaml.__version__},
           "s3_put_if_none_match": "IfNoneMatch" in put_shape.members,
           "timezones_ok": [str(ZoneInfo(tz)) for tz in timezones]}
    out["ok"] = out["s3_put_if_none_match"] and out["libs"]["psycopg_impl"] == "binary"
    log("smoke", **out)
    return out


# ------------------------------------------------------------------- planner


def _planner_args(event: Mapping[str, Any]) -> tuple[str, argparse.Namespace]:
    mode = event.get("mode")
    ids = event.get("location_ids")
    location_ids = ",".join(str(int(i)) for i in ids) if ids else None
    if mode == "daily_forecast":
        scheduled_at = event.get("scheduled_at_utc")
        if isinstance(scheduled_at, str) and (scheduled_at.startswith("<") or not scheduled_at.strip()):
            scheduled_at = None
        return "daily", argparse.Namespace(
            cohort=event.get("cohort_id", "pilot"), location_ids=location_ids,
            schedule_id=event.get("schedule_id", "manual"), scheduled_at=scheduled_at,
            refresh_seq=event.get("refresh_seq"), dry_run=bool(event.get("plan_dry_run", False)))
    if mode == "historical_backfill":
        for key in ("request_id", "start_date", "end_date"):
            if not event.get(key):
                raise ValueError(f"historical_backfill event requires {key}")
        return "backfill", argparse.Namespace(
            cohort=event.get("cohort_id", "pilot"), location_ids=location_ids, request_id=event["request_id"],
            start_date=event["start_date"], end_date=event["end_date"], reason=event.get("reason"),
            dry_run=bool(event.get("plan_dry_run", False)))
    raise ValueError(f"unsupported planner mode {mode!r}")


def _send_tasks(queue_url: str, plan: Mapping[str, Any], tasks: list[Mapping[str, Any]]) -> int:
    from src.weather.planner import build_task_queue_message

    sqs = client("sqs")
    sent = 0
    for start in range(0, len(tasks), 10):
        entries = [{"Id": t["task_id"], "MessageBody": json.dumps(build_task_queue_message(
            run_id=plan["run_id"], task_id=t["task_id"], task_index=t["task_index"],
            plan_s3_key=plan["plan_s3_key"], config_hash=plan["config_hash"]))} for t in tasks[start:start + 10]]
        for attempt in range(3):
            resp = sqs.send_message_batch(QueueUrl=queue_url, Entries=entries)
            sent += len(resp.get("Successful", []))
            failed = {f["Id"] for f in resp.get("Failed", [])}
            entries = [e for e in entries if e["Id"] in failed]
            if not entries:
                break
            time.sleep(0.5 * (attempt + 1))
        if entries:
            raise RuntimeError(f"SendMessageBatch failed for {len(entries)} task(s) of {plan['run_id']}")
    return sent


def planner_handler(event: Mapping[str, Any], context: Any = None) -> dict[str, Any]:
    if event.get("dry_run"):
        return _smoke("planner")
    from src.weather.cli import CliError, cmd_plan_backfill, cmd_plan_daily
    from src.weather.planner import accepted_key_for

    kind, args = _planner_args(event)
    sink, state = _sink(), _state()
    ctx = _context(sink, state, dsn_provider=_read_neon_dsn)
    try:
        view = (cmd_plan_daily if kind == "daily" else cmd_plan_backfill)(ctx, args)
    except CliError as exc:
        log("planner_rejected", mode=event.get("mode"), error=str(exc))
        raise RuntimeError(f"planner rejected request: {exc}") from None
    if view.get("dry_run"):
        log("planner_dry_run", run_id=view["run_id"], task_count=view["task_count"])
        return {"run_id": view["run_id"], "dry_run": True, "task_count": view["task_count"],
                "estimated_cost_total": view["estimated_cost_total"]}

    plan = sink.get_json(view["plan_s3_key"])
    state.register_run(plan["run_id"], plan["plan_s3_key"], plan["mode"], sink="s3", bucket=sink.bucket,
                       expected_tasks=plan["task_count"], config_hash=plan["config_hash"])
    pending = [t for t in plan["tasks"] if not sink.exists(accepted_key_for(t))]
    for t in pending:
        state.seed_task(plan["run_id"], t["task_id"], task_index=t["task_index"], store_id=t.get("store_id"),
                        grid_id=t.get("grid_id"), endpoint_key=t["endpoint_key"])
    sent = _send_tasks(_env(QUEUE_FOR_MODE[plan["mode"]]), plan, pending) if pending else 0
    out = {"run_id": plan["run_id"], "mode": plan["mode"], "plan_s3_key": plan["plan_s3_key"],
           "replayed_frozen_plan": bool(view.get("replayed_frozen_plan")), "task_count": plan["task_count"],
           "dispatched": sent, "already_accepted": plan["task_count"] - len(pending),
           "estimated_cost_total": plan["estimated_cost_total"],
           "neon_read": ctx._dsn is not None}  # DSN is fetched lazily, only when org.store is queried
    log("planner_dispatched", **out)
    return out


# -------------------------------------------------------------------- worker


def _queue_url_for(source_arn: str) -> str:
    name = source_arn.rsplit(":", 1)[-1]
    for env in QUEUE_FOR_MODE.values():
        url = os.environ.get(env, "")
        if url.rstrip("/").endswith("/" + name):
            return url
    raise RuntimeError(f"no queue URL configured for {name}")


def _load_plan(sink: Any, key: str) -> dict[str, Any]:
    if key not in _plan_cache:
        _plan_cache[key] = sink.get_json(key)
    return _plan_cache[key]


def _parse_message(body: str) -> dict[str, Any]:
    msg = json.loads(body)
    if not isinstance(msg, dict) or set(msg) != MESSAGE_KEYS or msg.get("message_schema_version") != "1":
        raise ValueError("message does not match task message schema v1")
    return msg


def _delay_for(row: Mapping[str, Any], now: datetime) -> int | None:
    """Seconds to hide a message before its next delivery, or None to ACK it."""
    status = row.get("status")
    if status == "DEFERRED":
        reason = str(row.get("reason") or row.get("validation_reason") or "")
        if row.get("retry_after_seconds"):
            return int(row["retry_after_seconds"]) + random.randint(1, 5)
        if reason == "MINUTE_LIMIT":
            return 60 - now.second + random.randint(1, 10)
        if reason == "HOURLY_LIMIT":
            return 3600 - (now.minute * 60 + now.second) + random.randint(1, 30)
        if reason.startswith("BUDGET_EXCEEDED"):
            return 3600
        if reason.startswith("NEAR_PRESENT_ALL_NULL"):
            return 2 * 3600
        return 120
    if status == "RETRYABLE":
        return random.randint(30, 90)
    if status == "SKIPPED_LEASED_BY_OTHER_WORKER":
        return 60
    return None


def process_record(record: Mapping[str, Any], *, sink: Any, state: Any, fetcher: Any, worker_id: str,
                   now_fn: Callable[[], datetime] | None = None) -> dict[str, Any]:
    from src.weather.runner import process_task

    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    msg = _parse_message(record["body"])
    plan = _load_plan(sink, msg["plan_s3_key"])
    if plan.get("run_id") != msg["run_id"] or plan.get("config_hash") != msg["config_hash"]:
        raise ValueError("message run_id/config_hash does not match the frozen plan")
    idx = int(msg["task_index"])
    if not (0 <= idx < len(plan["tasks"])) or plan["tasks"][idx]["task_id"] != msg["task_id"]:
        raise ValueError("task_index/task_id not found in the frozen plan")
    row = process_task(plan["tasks"][idx], sink=sink, state=state, fetcher=fetcher, worker_id=worker_id,
                       now_fn=now_fn, sleep=time.sleep, max_attempts=1, lease_seconds=WORKER_LEASE_SECONDS)
    row["run_id"] = msg["run_id"]
    row["delay_seconds"] = _delay_for(row, now_fn())
    return row


def worker_handler(event: Mapping[str, Any], context: Any = None) -> dict[str, Any]:
    if event.get("dry_run"):
        return _smoke("worker")
    sink, state, fetcher = _sink(), _state(), _fetcher()
    worker_id = getattr(context, "aws_request_id", None) or f"worker-{os.getpid()}"
    failures = []
    for record in event.get("Records", []):
        mid = record.get("messageId")
        try:
            row = process_record(record, sink=sink, state=state, fetcher=fetcher, worker_id=worker_id)
        except Exception as exc:  # noqa: BLE001 - malformed/mismatched messages go to the DLQ via retries
            log("worker_record_error", message_id=mid, error=f"{type(exc).__name__}: {str(exc)[:300]}",
                receive_count=record.get("attributes", {}).get("ApproximateReceiveCount"))
            _set_visibility(record, random.randint(ERROR_RETRY_MIN_SECONDS, ERROR_RETRY_MAX_SECONDS))
            failures.append({"itemIdentifier": mid})
            continue
        delay = row.pop("delay_seconds", None)
        log("worker_task", message_id=mid, **{k: row.get(k) for k in (
            "run_id", "task_id", "store_id", "grid_id", "endpoint_key", "window", "status", "reason", "http_status",
            "http_calls", "units", "x_ratelimit_cost", "validation_reason")}, delay_seconds=delay)
        if delay is not None:
            _set_visibility(record, delay)
            failures.append({"itemIdentifier": mid})
    return {"batchItemFailures": failures}


def _set_visibility(record: Mapping[str, Any], seconds: int) -> None:
    try:
        client("sqs").change_message_visibility(
            QueueUrl=_queue_url_for(record["eventSourceARN"]), ReceiptHandle=record["receiptHandle"],
            VisibilityTimeout=max(0, min(int(seconds), MAX_VISIBILITY_SECONDS)))
    except Exception as exc:  # noqa: BLE001 - the message still returns after the queue timeout
        log("worker_visibility_error", message_id=record.get("messageId"),
            error=f"{type(exc).__name__}: {str(exc)[:200]}")


# ---------------------------------------------------------------- reconciler


def _drain_dlq(url: str, *, sink: Any, state: Any) -> dict[str, int]:
    from src.weather.planner import accepted_key_for

    sqs = client("sqs")
    counts = {"received": 0, "marked_dlq": 0, "ignored": 0}
    while counts["received"] < DLQ_DRAIN_LIMIT:
        resp = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, WaitTimeSeconds=1,
                                   AttributeNames=["ApproximateReceiveCount"])
        messages = resp.get("Messages", [])
        if not messages:
            break
        for m in messages:
            counts["received"] += 1
            verdict = "ignored"
            try:
                msg = _parse_message(m["Body"])
                plan = sink.get_json(msg["plan_s3_key"])
                task = next((t for t in plan["tasks"] if t["task_id"] == msg["task_id"]), None)
                if (task is not None and plan.get("config_hash") == msg["config_hash"]
                        and not sink.exists(accepted_key_for(task))):
                    state.record_task_status(msg["run_id"], msg["task_id"], "DLQ",
                                             last_error=f"moved to DLQ after maxReceiveCount ({url.rsplit('/', 1)[-1]})",
                                             dlq_message_id=m["MessageId"])
                    verdict = "marked_dlq"
            except Exception as exc:  # noqa: BLE001 - foreign/invalid messages are logged then removed
                verdict = "ignored"
                log("dlq_unparsed", queue=url.rsplit("/", 1)[-1], message_id=m.get("MessageId"),
                    error=f"{type(exc).__name__}: {str(exc)[:200]}", body_preview=str(m.get("Body"))[:300])
            counts[verdict] += 1
            log("dlq_message", queue=url.rsplit("/", 1)[-1], message_id=m.get("MessageId"), verdict=verdict)
            sqs.delete_message(QueueUrl=url, ReceiptHandle=m["ReceiptHandle"])
    return counts


def reconcile_runs(*, sink: Any, state: Any, now: datetime) -> list[dict[str, Any]]:
    from src.weather.cli import _summary
    from src.weather.planner import accepted_key_for

    ctx = _context(sink, state)
    out = []
    now_epoch = int(now.timestamp())
    for run in state.list_active_runs():
        plan = sink.get_json(run["plan_key"])
        tasks = {t["task_id"]: t for t in plan["tasks"]}
        for item in state.list_tasks(plan["run_id"]):
            tid = item.get("task_id")
            if item.get("lease_expires_at") is not None and int(item["lease_expires_at"]) <= now_epoch:
                state.clear_expired_lease(run_id=plan["run_id"], task_id=tid, now_epoch=now_epoch)
        statuses = state.get_task_statuses(plan["run_id"])
        expired = 0
        for tid, task in tasks.items():
            deadline = task.get("deadline_utc")
            if (deadline and statuses.get(tid) not in ("SUCCEEDED", "ACCEPTED_WITH_WARNINGS", "FAILED_VALIDATION",
                                                         "FAILED", "EXPIRED", "DLQ")
                    and now >= datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                    and not sink.exists(accepted_key_for(task))):
                state.record_task_status(plan["run_id"], tid, "EXPIRED", last_error=f"deadline {deadline} passed")
                expired += 1
        summary, key = _summary(ctx, plan, write=True)
        if summary["is_terminal"]:
            state.mark_run_terminal(plan["run_id"], run_status=summary["run_status"], summary_key=key)
        row = {"run_id": plan["run_id"], "run_status": summary["run_status"], "terminal": summary["is_terminal"],
               "expired_now": expired, "status_counts": summary["status_counts"], "summary_key": key}
        log("reconcile_run", **row)
        out.append(row)
    return out


def reconciler_handler(event: Mapping[str, Any], context: Any = None) -> dict[str, Any]:
    if event.get("dry_run"):
        return _smoke("reconciler")
    sink, state = _sink(), _state()
    dlq = {env: _drain_dlq(_env(env), sink=sink, state=state) for env in DLQ_ENVS}
    runs = reconcile_runs(sink=sink, state=state, now=datetime.now(timezone.utc))
    out = {"dlq": dlq, "runs": runs}
    log("reconcile_done", runs=len(runs), dlq=dlq)
    return out
