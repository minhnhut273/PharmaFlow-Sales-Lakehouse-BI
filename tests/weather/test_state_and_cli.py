"""Unit tests for src/weather/state.py, reconcile.py, and cli.py (TC-STA-01 .. TC-CLI-02)."""

from __future__ import annotations

from pathlib import Path

from tests.weather.conftest import get_field


def test_tc_sta_01_local_state_store_task_lease_prevents_concurrent_duplicate(tmp_path: Path) -> None:
    """TC-STA-01: LocalStateStore grants task lease to first worker and denies second worker while lease is active."""
    from src.weather.state import LocalStateStore

    store = LocalStateStore(root_dir=tmp_path)
    granted_1 = store.acquire_task_lease(
        run_id="daily-20261111-abcd1234",
        task_id="task0001",
        worker_id="worker-a",
        now_epoch=1794330000,
        lease_seconds=120,
    )
    assert granted_1 is True

    # Second worker trying to acquire before lease expires (now + 30s < +120s) must be denied
    granted_2 = store.acquire_task_lease(
        run_id="daily-20261111-abcd1234",
        task_id="task0001",
        worker_id="worker-b",
        now_epoch=1794330030,
        lease_seconds=120,
    )
    assert granted_2 is False

    # After lease expires (now + 130s > +120s), another worker can reclaim the expired lease
    granted_after_expiry = store.acquire_task_lease(
        run_id="daily-20261111-abcd1234",
        task_id="task0001",
        worker_id="worker-b",
        now_epoch=1794330130,
        lease_seconds=120,
    )
    assert granted_after_expiry is True


def test_tc_sta_02_reconcile_run_summary_status_succeeded_partial_failed(tmp_path: Path) -> None:
    """TC-STA-02: Reconciler computes SUCCEEDED when all tasks succeed, PARTIAL on mixed outcomes, FAILED when all fail."""
    from src.weather.reconcile import summarize_run_outcomes

    s_all_ok = summarize_run_outcomes(
        run_id="run-1",
        expected_task_ids=["t1", "t2"],
        task_statuses={"t1": "SUCCEEDED", "t2": "ACCEPTED_WITH_WARNINGS"},
        rejected_locations=[],
    )
    assert get_field(s_all_ok, "run_status") == "SUCCEEDED"

    s_partial = summarize_run_outcomes(
        run_id="run-2",
        expected_task_ids=["t1", "t2"],
        task_statuses={"t1": "SUCCEEDED", "t2": "FAILED_VALIDATION"},
        rejected_locations=[{"store_id": 999, "rejection_reason": "INACTIVE"}],
    )
    assert get_field(s_partial, "run_status") == "PARTIAL"

    s_failed = summarize_run_outcomes(
        run_id="run-3",
        expected_task_ids=["t1", "t2"],
        task_statuses={"t1": "FAILED_VALIDATION", "t2": "EXPIRED"},
        rejected_locations=[],
    )
    assert get_field(s_failed, "run_status") == "FAILED"


def test_tc_cli_01_cli_plan_daily_dry_run_outputs_summary_without_cloud_calls(
    tmp_path: Path,
    pilot_store_rows: list[dict],
) -> None:
    """TC-CLI-01: CLI 'plan daily --cohort pilot --dry-run' returns exit code 0 and does not write files."""
    from src.weather.cli import run_cli

    exit_code, output = run_cli(
        ["plan", "daily", "--cohort", "pilot", "--dry-run"],
        store_rows_override=pilot_store_rows,
        runtime_dir=tmp_path,
    )
    assert exit_code == 0
    assert "daily-" in str(output)
    assert list(tmp_path.rglob("*.json")) == []
