"""Offline tests for P5: full_network grid clustering (0.111 floor), store_grid_mapping, and HOUR# limit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.stub import Stubber

from tests.weather.conftest import build_payload_for_params

SAMPLE_STORES = [
    {
        "store_id": 104,
        "store_code": "LC-HCM-01",
        "country_code": "VN",
        "latitude": 10.7769,
        "longitude": 106.7009,
        "timezone_name": "Asia/Ho_Chi_Minh",
        "store_status": "ACTIVE",
        "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
    },
    {
        "store_id": 516,
        "store_code": "LC-HCM-02",
        "country_code": "VN",
        "latitude": 10.7850,
        "longitude": 106.7100,
        "timezone_name": "Asia/Ho_Chi_Minh",
        "store_status": "ACTIVE",
        "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
    },
    {
        "store_id": 2137,
        "store_code": "LC-HN-01",
        "country_code": "VN",
        "latitude": 21.0285,
        "longitude": 105.8542,
        "timezone_name": "Asia/Ho_Chi_Minh",
        "store_status": "ACTIVE",
        "source": "LONGCHAU_PUBLIC_STORE_LOCATOR",
    },
    {
        "store_id": 5404,
        "store_code": "ONYX-DE-01",
        "country_code": "DE",
        "latitude": 52.52,
        "longitude": 13.405,
        "timezone_name": "Europe/Berlin",
        "store_status": "ACTIVE",
        "source": "ONYX_CHALLENGE_LOCATION_DIMENSION_UNVERIFIED",
    },
]


def test_resolve_cohort_full_network() -> None:
    from src.weather.config import resolve_cohort

    cohort = resolve_cohort("full_network")
    assert cohort["selection"] == "all_active"
    assert cohort["store_ids"] == []
    grid = cohort["grid_clustering"]
    assert grid["enabled"] is True
    assert grid["method"] == "floor"
    assert grid["step_deg"] == pytest.approx(0.111)
    assert grid["countries"] == ["VN"]
    assert grid["coordinate_mode"] == "centroid"


def test_cluster_locations_groups_same_vn_cell_and_keeps_intl() -> None:
    from src.weather.config import resolve_cohort
    from src.weather.grid import cluster_locations
    from src.weather.locations import evaluate_locations

    cohort = resolve_cohort("full_network")
    ev = evaluate_locations(SAMPLE_STORES, requested_store_ids=None, source_provenance_map=cohort["source_provenance_map"])
    assert len(ev["eligible_locations"]) == 4

    points, mapping = cluster_locations(ev["eligible_locations"], cohort["grid_clustering"])
    # 104 & 516 fall in floor(10.7769/0.111)=97, floor(106.7009/0.111)=961 -> 1 VN cell
    # 2137 falls in Hanoi -> 1 VN cell; 5404 (DE) stays direct -> 3 total points
    assert len(points) == 3
    assert len(mapping) == 4

    de_point = next(p for p in points if p["store_id"] == 5404)
    assert de_point["grid_id"] is None and de_point["member_store_ids"] == [5404]

    hcm_cell = next(p for p in points if 104 in p["member_store_ids"])
    assert hcm_cell["store_id"] is None
    assert hcm_cell["member_store_ids"] == [104, 516]
    assert hcm_cell["latitude"] == pytest.approx((10.7769 + 10.7850) / 2, abs=1e-6)
    assert hcm_cell["longitude"] == pytest.approx((106.7009 + 106.7100) / 2, abs=1e-6)


def test_full_network_plan_writes_mapping_and_executes_grid_metadata(tmp_path: Path) -> None:
    from src.weather.cli import run_cli
    from src.weather.storage import LocalSink

    now = datetime(2026, 11, 17, 23, 0, 0, tzinfo=timezone.utc)  # 06:00 VN

    def fake_fetcher(endpoint_key: str, params: dict[str, Any]) -> dict[str, Any]:
        raw = build_payload_for_params(params, now_utc=now)
        return {"http_status": 200, "headers": {"X-RateLimit-Cost": "5.6"},
                "rate_limit_headers": {"X-RateLimit-Cost": "5.6"}, "raw_bytes": raw}

    code, plan_out = run_cli(
        ["plan", "daily", "--cohort", "full_network", "--schedule-id", "daily-0600-vn", "--sink", "local"],
        store_rows_override=SAMPLE_STORES, runtime_dir=tmp_path, now_utc=now,
    )
    assert code == 0 and isinstance(plan_out, dict)
    assert plan_out["task_count"] == 3
    assert plan_out["estimated_cost_total"] == pytest.approx(16.8)
    mapping_key = plan_out["store_grid_mapping_s3_key"]

    sink = LocalSink(tmp_path)
    mapping_doc = sink.get_json(mapping_key)
    assert mapping_doc["store_count"] == 4 and mapping_doc["point_count"] == 3
    by_store = {r["store_id"]: r for r in mapping_doc["mappings"]}
    assert by_store[104]["task_id"] == by_store[516]["task_id"]
    assert by_store[104]["clustered"] is True and by_store[5404]["clustered"] is False

    code2, run_out = run_cli(
        ["run", "--plan", plan_out["plan_s3_key"], "--sink", "local"],
        store_rows_override=SAMPLE_STORES, runtime_dir=tmp_path, fetcher=fake_fetcher,
        sleep=lambda _: None, now_utc=now,
    )
    assert code2 == 0 and isinstance(run_out, dict)
    assert run_out["run_status"] == "SUCCEEDED"

    accepted_keys = sink.list_keys("raw/open_meteo/weather_forecast")
    grid_meta_keys = [k for k in accepted_keys if k.endswith("metadata.json") and by_store[104]["task_id"] in k]
    assert len(grid_meta_keys) == 1
    grid_meta = sink.get_json(grid_meta_keys[0])
    assert grid_meta["store_id"] is None
    assert grid_meta["grid_id"] == by_store[104]["grid_id"]
    assert grid_meta["member_store_ids"] == [104, 516]
    assert grid_meta["member_store_count"] == 2


def test_local_state_hourly_limit_defers_without_charging_daily(tmp_path: Path) -> None:
    from src.weather.state import LocalStateStore

    st = LocalStateStore(tmp_path / "state")
    ok = st.reserve_units(date_vn="2026-11-17", minute_key="202611172300", hour_key="2026111723",
                          mode="daily_forecast", units=4928.0, hourly_limit=4980.0)
    assert ok == {"allowed": True, "reason": "OK"}

    blocked = st.reserve_units(date_vn="2026-11-17", minute_key="202611172301", hour_key="2026111723",
                               mode="historical_backfill", units=60.0, hourly_limit=4980.0)
    assert blocked == {"allowed": False, "reason": "HOURLY_LIMIT"}
    assert st.get_budget("2026-11-17") == {"used_daily": 4928.0, "used_backfill": 0.0}
    assert st.get_hour_usage("2026111723") == pytest.approx(4928.0)


def test_dynamo_state_hourly_limit_and_seed_omits_none_store_id() -> None:
    from botocore.exceptions import ClientError
    from src.weather.handlers import _delay_for
    from src.weather.state import DynamoStateStore

    client = boto3.client("dynamodb", region_name="ap-southeast-1",
                          aws_access_key_id="test", aws_secret_access_key="test")
    _stub = Stubber(client)
    seen: list[Any] = []

    def fake_tx(**kw: Any) -> dict[str, Any]:
        seen.append(kw["TransactItems"])
        raise ClientError(
            {"Error": {"Code": "TransactionCanceledException", "Message": "limit"},
             "CancellationReasons": [{"Code": "None"}, {"Code": "None"}, {"Code": "ConditionalCheckFailed"}]},
            "TransactWriteItems",
        )

    client.transact_write_items = fake_tx  # type: ignore[method-assign]
    st = DynamoStateStore(table="t", client=client, now_epoch=lambda: 1700000000)
    res = st.reserve_units(date_vn="2026-11-17", minute_key="202611172305", hour_key="2026111723",
                           mode="daily_forecast", units=5.6)
    assert res == {"allowed": False, "reason": "HOURLY_LIMIT"}
    assert len(seen[0]) == 3 and seen[0][2]["Update"]["Key"]["pk"] == {"S": "HOUR#2026111723"}
    assert seen[0][2]["Update"]["ExpressionAttributeValues"][":maxhr"] == {"N": "4974.4"}

    captured: dict[str, Any] = {}
    client.update_item = lambda **kw: captured.update(kw) or {}  # type: ignore[method-assign]
    st.seed_task("r1", "t1", task_index=0, store_id=None, grid_id="grid:VN:floor:0.111:97:961", endpoint_key="forecast")
    names = set(captured["ExpressionAttributeNames"].values())
    assert "store_id" not in names and "grid_id" in names

    delay = _delay_for({"status": "DEFERRED", "reason": "HOURLY_LIMIT"},
                       datetime(2026, 11, 17, 23, 15, 0, tzinfo=timezone.utc))
    assert delay is not None and 2701 <= delay <= 2730
