"""Reconcile run outcomes and write an immutable terminal summary."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from src.weather.config import canonical_json
from src.weather.state import SUCCESS_TASK_STATUSES, TERMINAL_TASK_STATUSES


def summarize_run_outcomes(
    *,
    run_id: str,
    expected_task_ids: Sequence[str],
    task_statuses: Mapping[str, str],
    rejected_locations: Sequence[Any],
) -> dict[str, Any]:
    statuses = {tid: task_statuses.get(tid, "PENDING") for tid in expected_task_ids}
    counts = Counter(statuses.values())
    non_terminal = sorted(t for t, s in statuses.items() if s not in TERMINAL_TASK_STATUSES)
    succeeded = sum(1 for s in statuses.values() if s in SUCCESS_TASK_STATUSES)

    if not expected_task_ids:
        run_status, is_terminal = "FAILED", True
    elif non_terminal:
        run_status, is_terminal = "RUNNING", False
    elif succeeded == len(expected_task_ids):
        run_status, is_terminal = "SUCCEEDED", True
    elif succeeded > 0:
        run_status, is_terminal = "PARTIAL", True
    else:
        run_status, is_terminal = "FAILED", True

    return {
        "run_id": run_id,
        "run_status": run_status,
        "is_terminal": is_terminal,
        "expected_tasks": len(expected_task_ids),
        "succeeded_tasks": succeeded,
        "status_counts": dict(sorted(counts.items())),
        "non_terminal_task_ids": non_terminal,
        "task_statuses": dict(sorted(statuses.items())),
        "rejected_locations": [dict(r) if isinstance(r, Mapping) else r for r in rejected_locations],
    }


def write_summary(sink: Any, plan: Mapping[str, Any], summary: Mapping[str, Any]) -> str | None:
    """Write <run_prefix>/summary/<rev>.json once the run is terminal. Same outcome -> same file."""
    if not summary.get("is_terminal"):
        return None
    rev = hashlib.sha256(
        canonical_json({"run_status": summary["run_status"], "tasks": summary["task_statuses"]}).encode("utf-8")
    ).hexdigest()[:8]
    key = f"{plan['run_prefix']}/summary/{rev}.json"
    doc = {
        "schema_version": "1",
        "terminal_revision": rev,
        "plan_s3_key": plan["plan_s3_key"],
        "config_hash": plan.get("config_hash"),
        "mode": plan.get("mode"),
        "written_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **summary,
    }
    sink.put_json_if_absent(key, doc)
    return key
