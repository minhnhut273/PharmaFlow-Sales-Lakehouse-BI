"""P3 offline tests for DynamoStateStore (botocore Stubber; no AWS calls)."""

from __future__ import annotations

from typing import Any

import boto3
import pytest
from botocore.stub import ANY, Stubber

TABLE = "pharmaflow-dev-weather-control"


@pytest.fixture()
def ddb() -> tuple[Any, Stubber]:
    client = boto3.client("dynamodb", region_name="ap-southeast-1", aws_access_key_id="x",
                          aws_secret_access_key="x")
    stub = Stubber(client)
    stub.activate()
    yield client, stub
    stub.deactivate()


def _store(client: Any) -> Any:
    from src.weather.state import DynamoStateStore

    return DynamoStateStore(table=TABLE, client=client, now_epoch=lambda: 1794330000)


def _update_params(key: dict[str, Any]) -> dict[str, Any]:
    return {"TableName": TABLE, "Key": key, "UpdateExpression": ANY, "ExpressionAttributeNames": ANY,
            "ExpressionAttributeValues": ANY, "ConditionExpression": ANY}


TASK_KEY = {"pk": {"S": "RUN#r1"}, "sk": {"S": "TASK#t1"}}


def test_lease_granted_then_denied_on_condition_failure(ddb: Any) -> None:
    client, stub = ddb
    stub.add_response("update_item", {}, _update_params(TASK_KEY))
    stub.add_client_error("update_item", service_error_code="ConditionalCheckFailedException",
                          expected_params=_update_params(TASK_KEY))
    store = _store(client)
    assert store.acquire_task_lease(run_id="r1", task_id="t1", worker_id="w1", now_epoch=100, lease_seconds=120)
    assert not store.acquire_task_lease(run_id="r1", task_id="t1", worker_id="w2", now_epoch=130, lease_seconds=120)
    stub.assert_no_pending_responses()


def test_lease_condition_allows_owner_or_expired_lease(ddb: Any) -> None:
    client, _ = ddb
    captured: dict[str, Any] = {}

    def capture(**kw: Any) -> dict[str, Any]:
        captured.update(kw)
        return {}

    client.update_item = capture  # type: ignore[method-assign]
    _store(client).acquire_task_lease(run_id="r1", task_id="t1", worker_id="w1", now_epoch=100, lease_seconds=120)
    assert captured["ConditionExpression"] == "attribute_not_exists(#lo) OR #lo = :w OR #le <= :now"
    names, values = captured["ExpressionAttributeNames"], captured["ExpressionAttributeValues"]
    assert names["#lo"] == "lease_owner" and names["#le"] == "lease_expires_at"
    assert values[":w"] == {"S": "w1"} and values[":now"] == {"N": "100"}
    assert {"N": "220"} in values.values()  # lease_expires_at = now + lease_seconds


def test_release_ignores_lease_owned_by_another_worker(ddb: Any) -> None:
    client, stub = ddb
    stub.add_client_error("update_item", service_error_code="ConditionalCheckFailedException",
                          expected_params=_update_params(TASK_KEY))
    _store(client).release_task_lease(run_id="r1", task_id="t1", worker_id="w2")
    stub.assert_no_pending_responses()


def _transact(client: Any, error: list[str] | None) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []

    def fake(**kw: Any) -> dict[str, Any]:
        seen.extend(kw["TransactItems"])
        if error:
            from botocore.exceptions import ClientError

            exc = ClientError({"Error": {"Code": "TransactionCanceledException", "Message": "x"},
                               "CancellationReasons": [{"Code": c} for c in error]}, "TransactWriteItems")
            raise exc
        return {}

    client.transact_write_items = fake  # type: ignore[method-assign]
    return seen


@pytest.mark.parametrize(("reasons", "expected"), [
    (None, "OK"),
    (["ConditionalCheckFailed", "None"], "BUDGET_EXCEEDED_FOR_RUN"),
    (["None", "ConditionalCheckFailed"], "MINUTE_LIMIT"),
])
def test_reserve_units_maps_transaction_outcome(ddb: Any, reasons: list[str] | None, expected: str) -> None:
    client, _ = ddb
    seen = _transact(client, reasons)
    out = _store(client).reserve_units(date_vn="2026-11-13", minute_key="202611130300", mode="historical_backfill",
                                       units=4.9)
    assert out["reason"] == expected and out["allowed"] is (expected == "OK")
    budget, rate = seen[0]["Update"], seen[1]["Update"]
    assert budget["Key"]["pk"] == {"S": "BUDGET#2026-11-13"} and rate["Key"]["pk"] == {"S": "RATE#202611130300"}
    # backfill: total <= 10000-4.9 and used_backfill <= 10000-2000-4.9
    assert budget["ExpressionAttributeValues"][":maxtot"] == {"N": "9995.1"}
    assert budget["ExpressionAttributeValues"][":maxbf"] == {"N": "7995.1"}
    assert "#bf" in budget["ConditionExpression"]
    assert rate["ExpressionAttributeValues"][":maxmin"] == {"N": "545.1"}


def test_reserve_units_daily_may_use_reserve(ddb: Any) -> None:
    client, _ = ddb
    seen = _transact(client, None)
    _store(client).reserve_units(date_vn="2026-11-13", minute_key="202611130300", mode="daily_forecast", units=5.6)
    budget = seen[0]["Update"]
    assert "#bf" not in budget["ConditionExpression"] and budget["ExpressionAttributeNames"]["#m"] == "used_daily"


def test_seed_task_does_not_overwrite_existing_status(ddb: Any) -> None:
    client, _ = ddb
    captured: dict[str, Any] = {}
    client.update_item = lambda **kw: captured.update(kw) or {}  # type: ignore[method-assign]
    _store(client).seed_task("r1", "t1", task_index=0)
    status_ph = next(k for k, v in captured["ExpressionAttributeNames"].items() if v == "status")
    assert f"{status_ph} = if_not_exists({status_ph}," in captured["UpdateExpression"]


def test_get_task_statuses_and_active_runs(ddb: Any) -> None:
    client, stub = ddb
    stub.add_response("query", {"Items": [
        {"pk": {"S": "RUN#r1"}, "sk": {"S": "TASK#t1"}, "status": {"S": "SUCCEEDED"}},
        {"pk": {"S": "RUN#r1"}, "sk": {"S": "TASK#t2"}, "status": {"S": "PLANNED"}, "attempt_count": {"N": "2"}},
    ]}, {"TableName": TABLE, "ConsistentRead": True, "KeyConditionExpression": ANY,
         "ExpressionAttributeValues": {":pk": {"S": "RUN#r1"}, ":t": {"S": "TASK#"}}})
    stub.add_response("query", {"Items": [{"pk": {"S": "RUN#r1"}, "sk": {"S": "META"}, "plan_key": {"S": "k"},
                                           "gsi1pk": {"S": "ACTIVE"}}]},
                      {"TableName": TABLE, "IndexName": "active_runs", "KeyConditionExpression": ANY,
                       "ExpressionAttributeValues": {":a": {"S": "ACTIVE"}}})
    store = _store(client)
    assert store.get_task_statuses("r1") == {"t1": "SUCCEEDED", "t2": "PLANNED"}
    assert store.list_active_runs()[0]["plan_key"] == "k"


def test_mark_run_terminal_removes_active_flag(ddb: Any) -> None:
    client, _ = ddb
    captured: dict[str, Any] = {}
    client.update_item = lambda **kw: captured.update(kw) or {}  # type: ignore[method-assign]
    _store(client).mark_run_terminal("r1", run_status="SUCCEEDED", summary_key="s.json")
    assert captured["Key"] == {"pk": {"S": "RUN#r1"}, "sk": {"S": "META"}}
    assert "REMOVE" in captured["UpdateExpression"] and "gsi1pk" in captured["ExpressionAttributeNames"].values()


def test_record_task_status_counts_attempts_and_skips_none(ddb: Any) -> None:
    client, _ = ddb
    captured: dict[str, Any] = {}
    client.update_item = lambda **kw: captured.update(kw) or {}  # type: ignore[method-assign]
    _store(client).record_task_status("r1", "t1", "SUCCEEDED", count_attempt=True, last_error=None, http_status=200)
    names = captured["ExpressionAttributeNames"].values()
    assert "attempt_count" in names and "last_error" not in names and "http_status" in names
    assert " ADD " in f" {captured['UpdateExpression']} "
