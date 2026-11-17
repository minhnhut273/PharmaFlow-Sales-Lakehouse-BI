"""Process one frozen task: lease -> reserve units -> execute_task -> record status.

Shared by the local CLI (LocalStateStore, several attempts, pacing by sleep) and the Lambda worker
(DynamoStateStore, one attempt per SQS delivery, pacing by the DynamoDB minute window).
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from src.weather.limiter import min_interval_seconds
from src.weather.planner import VN_TZ, accepted_key_for
from src.weather.worker import execute_task

TERMINAL_FAILURES = ("FAILED_VALIDATION", "FAILED", "EXPIRED", "DLQ")
SUCCESS = ("SUCCEEDED", "ACCEPTED_WITH_WARNINGS")


class Pacer:
    """Spaces consecutive Open-Meteo calls so the weighted per-minute limit is respected (CLI)."""

    def __init__(self, sleep: Callable[[float], None]) -> None:
        self.sleep = sleep
        self.last_cost: float | None = None

    def wait(self) -> None:
        if self.last_cost is not None:
            self.sleep(min_interval_seconds(self.last_cost))

    def record(self, cost: float) -> None:
        self.last_cost = cost


class NoPacer(Pacer):
    def __init__(self) -> None:
        super().__init__(lambda s: None)

    def wait(self) -> None:
        return None


def charged_units(outcome: Mapping[str, Any], task: Mapping[str, Any]) -> float:
    raw = (outcome.get("rate_limit_headers") or {}).get("X-RateLimit-Cost")
    try:
        return float(raw) if raw is not None else float(task["estimated_cost"])
    except (TypeError, ValueError):
        return float(task["estimated_cost"])


def process_task(
    task: Mapping[str, Any],
    *,
    sink: Any,
    state: Any,
    fetcher: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
    worker_id: str,
    now_fn: Callable[[], datetime],
    sleep: Callable[[float], None],
    max_attempts: int,
    lease_seconds: int,
    pacer: Pacer | None = None,
) -> dict[str, Any]:
    run_id, tid = task["run_id"], task["task_id"]
    row: dict[str, Any] = {"task_id": tid, "store_id": task.get("store_id"), "endpoint_key": task["endpoint_key"],
                           "window": f"{task['start_date']}..{task['end_date']}", "http_calls": 0, "units": 0.0}
    if task.get("grid_id") is not None:
        row["grid_id"] = task["grid_id"]
    pacer = pacer or NoPacer()

    if sink.exists(accepted_key_for(task)):
        row["status"] = "SKIPPED_ALREADY_ACCEPTED"
        return row
    prior = state.get_task(run_id, tid) or {}
    if prior.get("status") in TERMINAL_FAILURES:
        row["status"] = f"SKIPPED_TERMINAL_{prior['status']}"
        return row

    if not state.acquire_task_lease(run_id=run_id, task_id=tid, worker_id=worker_id,
                                    now_epoch=int(now_fn().timestamp()), lease_seconds=lease_seconds):
        row["status"] = "SKIPPED_LEASED_BY_OTHER_WORKER"
        return row

    try:
        outcome: dict[str, Any] = {}
        for attempt_no in range(1, max_attempts + 1):
            now = now_fn()
            today_vn = now.astimezone(VN_TZ).date().isoformat()
            hour_key = now.strftime("%Y%m%d%H")
            estimate = float(task["estimated_cost"])
            reservation = state.reserve_units(date_vn=today_vn, minute_key=now.strftime("%Y%m%d%H%M"),
                                              hour_key=hour_key, mode=task["mode"], units=estimate)
            if not reservation["allowed"]:
                state.record_task_status(run_id, tid, "DEFERRED", last_error=reservation["reason"])
                row.update({"status": "DEFERRED", "reason": reservation["reason"]})
                return row

            pacer.wait()
            attempt_id = f"att-{now_fn().strftime('%Y%m%dT%H%M%SZ')}-{random.getrandbits(24):06x}"
            outcome = execute_task(task=task, sink=sink, fetcher=fetcher, attempt_id=attempt_id,
                                   today_vn=today_vn, now_utc=now_fn())
            if outcome.get("http_called"):
                cost = charged_units(outcome, task)
                row["http_calls"] += 1
                row["units"] = round(row["units"] + cost, 6)
                pacer.record(cost)
                state.adjust_usage(date_vn=today_vn, mode=task["mode"], delta=round(cost - estimate, 6),
                                   hour_key=hour_key)
            else:
                state.adjust_usage(date_vn=today_vn, mode=task["mode"], delta=-estimate, hour_key=hour_key)

            state.record_task_status(
                run_id, tid, outcome["status"], count_attempt=bool(outcome.get("http_called")),
                last_attempt_id=attempt_id, last_error=outcome.get("validation_reason"),
                http_status=outcome.get("http_status"),
                accepted_attempt_id=attempt_id if outcome["status"] in SUCCESS else prior.get("accepted_attempt_id"),
            )
            if outcome["status"] != "RETRYABLE" or attempt_no == max_attempts:
                break
            sleep(min(30.0, 2.0 ** attempt_no) + random.uniform(0.0, 1.0))

        row.update({k: outcome.get(k) for k in ("status", "attempt_id", "http_status", "validation_status",
                                                 "validation_reason", "raw_sha256", "http_category",
                                                 "retry_after_seconds")})
        row["x_ratelimit_cost"] = (outcome.get("rate_limit_headers") or {}).get("X-RateLimit-Cost")
        return row
    finally:
        state.release_task_lease(run_id=run_id, task_id=tid, worker_id=worker_id)
