"""Planner: deterministic run/task IDs, endpoint routing, 14-day chunks, budget, frozen plans."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from src.weather.config import compute_config_hash, load_variable_contract
from src.weather.limiter import (
    BACKFILL_DAILY_ALLOWANCE,
    DEFAULT_DAILY_LIMIT,
    DEFAULT_DAILY_RESERVE,
    check_budget_admission,
    estimate_call_cost,
)

PLAN_SCHEMA_VERSION = "1"
MESSAGE_SCHEMA_VERSION = "1"
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
RAW_ROOT = "raw/open_meteo"

FORECAST_DAYS = 16
CHUNK_DAYS = 14
GFS_MIN_DATE = date(2022, 1, 1)
ERA5_MIN_DATE = date(1940, 1, 1)
ERA5_MAX_DATE = date(2021, 12, 31)
DAILY_DEADLINE_VN = time(9, 0)
MANUAL_DEADLINE_HOURS = 3
MANUAL_SCHEDULE_ID = "manual"

ENDPOINT_PREFIX = {
    "forecast": f"{RAW_ROOT}/weather_forecast",
    "historical_forecast": f"{RAW_ROOT}/historical_forecast",
    "historical_weather": f"{RAW_ROOT}/historical_weather",
}
SOURCE_TYPE = {
    "forecast": "FORECAST",
    "historical_forecast": "HISTORICAL_FORECAST_STITCHED",
    "historical_weather": "HISTORICAL_ERA5_REANALYSIS",
}

# Location fields copied into each task so the worker never needs the DB.
TASK_LOCATION_FIELDS = (
    "store_id",
    "store_code",
    "country_code",
    "latitude",
    "longitude",
    "timezone_name",
    "source",
    "coordinate_provenance",
    "coordinate_verification_status",
    "eligibility_reason",
)


# --------------------------------------------------------------------------- IDs


def _hash8(*parts: Any) -> str:
    joined = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8]


def _yyyymmdd(iso_date: str) -> str:
    return date.fromisoformat(iso_date).strftime("%Y%m%d")


def build_daily_run_id(
    *,
    schedule_date_vn: str,
    schedule_id: str,
    cohort_id: str,
    cohort_policy_version: str,
    contract_version: str,
    model: str,
    refresh_seq: int | None = None,
) -> str:
    parts = [schedule_date_vn, schedule_id, cohort_id, cohort_policy_version, contract_version, model]
    if refresh_seq is not None:
        parts.append(f"refresh_seq={int(refresh_seq)}")
    return f"daily-{_yyyymmdd(schedule_date_vn)}-{_hash8(*parts)}"


def build_backfill_run_id(
    *,
    ingest_date_vn: str,
    request_id: str,
    cohort_policy_version: str,
    contract_version: str,
) -> str:
    return f"backfill-{_yyyymmdd(ingest_date_vn)}-{_hash8(request_id, cohort_policy_version, contract_version)}"


def build_task_id(
    *,
    run_id: str,
    store_id: int | None = None,
    point_id: str | None = None,
    endpoint_key: str,
    start_date: str,
    end_date: str,
    contract_version: str,
    model: str | None,
) -> str:
    if store_id is not None:
        target = str(int(store_id))
    elif point_id:
        target = str(point_id)
    else:
        raise ValueError("build_task_id requires store_id or point_id")
    joined = "|".join([run_id, target, endpoint_key, start_date, end_date, contract_version, model or ""])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------- S3 keys


def run_prefix_for(s3_prefix: str, ingest_date: str, run_id: str) -> str:
    return f"{s3_prefix}/ingest_date={ingest_date}/run_id={run_id}"


def task_base_key(task: Mapping[str, Any]) -> str:
    """``<task.s3_prefix>/ingest_date=<d>/run_id=<r>/tasks/<task_id>`` (per-task prefix)."""
    return f"{run_prefix_for(task['s3_prefix'], task['ingest_date'], task['run_id'])}/tasks/{task['task_id']}"


def accepted_key_for(task: Mapping[str, Any]) -> str:
    return f"{task_base_key(task)}/accepted.json"


def _first_segment_endpoint(mode: str, start_date: str | None) -> str:
    if mode == "daily_forecast":
        return "forecast"
    if mode == "historical_backfill":
        if not start_date:
            raise ValueError("start_date is required to predict a backfill plan key")
        return "historical_weather" if date.fromisoformat(start_date) < GFS_MIN_DATE else "historical_forecast"
    raise ValueError(f"Unknown mode {mode!r}")


def predict_plan_key(mode: str, ingest_date: str, run_id: str, start_date: str | None = None) -> str:
    """Plan key known before reading the DB: run files live under the first segment's prefix."""
    prefix = ENDPOINT_PREFIX[_first_segment_endpoint(mode, start_date)]
    return f"{run_prefix_for(prefix, ingest_date, run_id)}/plan.json"


# ------------------------------------------------------------------- helpers


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_aware(dt: datetime, name: str) -> datetime:
    if dt.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware (UTC)")
    return dt.astimezone(timezone.utc)


def _loc(location: Any) -> dict[str, Any]:
    if isinstance(location, Mapping):
        return dict(location)
    return dict(vars(location))


def _contract_fingerprint(contract: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": contract["contract_version"],
        "model": contract["model"],
        "hourly_variables": list(contract["hourly_variables"]),
        "daily_variables": list(contract["daily_variables"]),
        "units": dict(contract["units"]),
        "timeformat": contract["timeformat"],
    }


def _plan_hash(definition: Mapping[str, Any], tasks: Sequence[Mapping[str, Any]]) -> str:
    task_defs = []
    for t in tasks:
        td = {k: t[k] for k in ("task_id", "store_id", "latitude", "longitude", "timezone_name", "endpoint_key",
                                "start_date", "end_date", "contract_version", "model")}
        if t.get("grid_id") is not None:
            td["grid_id"] = t["grid_id"]
            td["member_store_ids"] = list(t["member_store_ids"])
        task_defs.append(td)
    return compute_config_hash({**definition, "tasks": task_defs})


def _persist(
    plan: dict[str, Any],
    eligible: Sequence[Mapping[str, Any]],
    sink: Any,
    store_grid_mapping: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    """Write locations.json (and store_grid_mapping.json if clustered) then plan.json (create-only)."""
    locations_doc = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "run_id": plan["run_id"],
        "cohort_id": plan.get("cohort_id"),
        "cohort_policy_version": plan["cohort_policy_version"],
        "read_at_utc": plan["planned_at_utc"],
        "eligible_locations": list(eligible),
        "rejected_locations": list(plan["rejected_locations"]),
    }
    if not sink.exists(plan["locations_s3_key"]):
        sink.put_json_if_absent(plan["locations_s3_key"], locations_doc)
    mapping_key = plan.get("store_grid_mapping_s3_key")
    if store_grid_mapping is not None and mapping_key and not sink.exists(mapping_key):
        mapping_doc = {
            "schema_version": PLAN_SCHEMA_VERSION,
            "run_id": plan["run_id"],
            "cohort_id": plan.get("cohort_id"),
            "cohort_policy_version": plan["cohort_policy_version"],
            "grid_clustering": plan.get("grid_clustering"),
            "created_at_utc": plan["planned_at_utc"],
            "store_count": len(store_grid_mapping),
            "point_count": plan["task_count"],
            "mappings": list(store_grid_mapping),
        }
        sink.put_json_if_absent(mapping_key, mapping_doc)
    if not sink.put_json_if_absent(plan["plan_s3_key"], plan):
        existing = sink.get_json(plan["plan_s3_key"])
        if existing.get("config_hash") != plan["config_hash"]:
            raise ValueError(
                f"plan.json already exists for {plan['run_id']} with a different config_hash; "
                "refusing to replace a frozen plan"
            )


def _finalize(
    plan: dict[str, Any],
    eligible: Sequence[Mapping[str, Any]],
    sink: Any,
    dry_run: bool,
    store_grid_mapping: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    plan["dry_run"] = bool(dry_run)
    if sink is not None and not dry_run:
        _persist(plan, eligible, sink, store_grid_mapping=store_grid_mapping)
    return plan


# --------------------------------------------------------------- daily plan


def _daily_deadline(
    *, schedule_id: str, scheduled_at: datetime, planned_at: datetime, local_start: date, tz: ZoneInfo
) -> datetime:
    local_midnight = datetime.combine(local_start + timedelta(days=1), time(0, 0), tzinfo=tz).astimezone(timezone.utc)
    if schedule_id == MANUAL_SCHEDULE_ID:
        candidate = planned_at + timedelta(hours=MANUAL_DEADLINE_HOURS)
    else:
        vn_day = scheduled_at.astimezone(VN_TZ).date()
        candidate = datetime.combine(vn_day, DAILY_DEADLINE_VN, tzinfo=VN_TZ).astimezone(timezone.utc)
    return min(candidate, local_midnight)


def create_daily_plan(
    *,
    eligible_locations: Sequence[Any],
    rejected_locations: Sequence[Any],
    scheduled_at_utc: datetime,
    schedule_id: str,
    cohort_id: str,
    cohort_policy_version: str = "pilot_v1",
    contract_version: str = "weather_variables_v1",
    model: str = "gfs_global",
    sink: Any = None,
    dry_run: bool = False,
    planned_at_utc: datetime | None = None,
    refresh_seq: int | None = None,
    grid_clustering: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One forecast task per point (store or grid cell); 16-day window starts at local date."""
    scheduled_at = _require_aware(scheduled_at_utc, "scheduled_at_utc")
    planned_at = _require_aware(planned_at_utc, "planned_at_utc") if planned_at_utc else scheduled_at
    contract = load_variable_contract(contract_version)
    if contract["model"] != model or "forecast" not in contract["applies_to_endpoints"]:
        raise ValueError(f"Daily forecast must use {contract_version} with model {contract['model']!r}")

    eligible = sorted((_loc(e) for e in eligible_locations), key=lambda x: int(x["store_id"]))
    rejected = [_loc(r) for r in rejected_locations]
    if not eligible:
        raise ValueError("NO_ELIGIBLE_LOCATIONS: refusing to create an empty run")

    clustering_on = bool(grid_clustering and grid_clustering.get("enabled"))
    mapping_rows: list[dict[str, Any]] | None = None
    if clustering_on:
        from src.weather.grid import cluster_locations

        targets, mapping_rows = cluster_locations(eligible, grid_clustering)
    else:
        targets = eligible

    schedule_date_vn = scheduled_at.astimezone(VN_TZ).date().isoformat()
    run_id = build_daily_run_id(
        schedule_date_vn=schedule_date_vn,
        schedule_id=schedule_id,
        cohort_id=cohort_id,
        cohort_policy_version=cohort_policy_version,
        contract_version=contract_version,
        model=model,
        refresh_seq=refresh_seq,
    )
    s3_prefix = ENDPOINT_PREFIX["forecast"]
    cost = estimate_call_cost(contract["n_variables"], FORECAST_DAYS)

    tasks: list[dict[str, Any]] = []
    task_id_by_point: dict[str, str] = {}
    for loc in targets:
        tz = ZoneInfo(loc["timezone_name"])
        local_start = planned_at.astimezone(tz).date()
        start, end = local_start.isoformat(), (local_start + timedelta(days=FORECAST_DAYS - 1)).isoformat()
        point_id = loc.get("point_id")
        task_id = build_task_id(
            run_id=run_id, store_id=loc.get("store_id"), point_id=point_id, endpoint_key="forecast",
            start_date=start, end_date=end, contract_version=contract_version, model=model,
        )
        if point_id:
            task_id_by_point[str(point_id)] = task_id
        deadline = _daily_deadline(
            schedule_id=schedule_id, scheduled_at=scheduled_at, planned_at=planned_at, local_start=local_start, tz=tz
        )
        task_entry: dict[str, Any] = {
            "run_id": run_id,
            "task_id": task_id,
            "task_index": len(tasks),
            "ingest_date": schedule_date_vn,
            "mode": "daily_forecast",
            "endpoint_key": "forecast",
            "s3_prefix": s3_prefix,
            **{k: loc.get(k) for k in TASK_LOCATION_FIELDS},
            "start_date": start,
            "end_date": end,
            "expected_days": FORECAST_DAYS,
            "contract_version": contract_version,
            "model": model,
            "source_type": SOURCE_TYPE["forecast"],
            "estimated_cost": cost,
            "deadline_utc": _iso_utc(deadline),
            "scheduled_at_utc": _iso_utc(scheduled_at),
            "planned_at_utc": _iso_utc(planned_at),
        }
        if clustering_on:
            task_entry["point_id"] = point_id
            task_entry["grid_id"] = loc.get("grid_id")
            task_entry["member_store_ids"] = list(loc["member_store_ids"])
            task_entry["member_store_count"] = int(loc["member_store_count"])
        tasks.append(task_entry)

    if mapping_rows is not None:
        for row in mapping_rows:
            row["task_id"] = task_id_by_point[row["point_id"]]

    definition: dict[str, Any] = {
        "mode": "daily_forecast",
        "run_id": run_id,
        "schedule_date_vn": schedule_date_vn,
        "schedule_id": schedule_id,
        "cohort_id": cohort_id,
        "cohort_policy_version": cohort_policy_version,
        "contracts": [_contract_fingerprint(contract)],
        "rejected_store_ids": sorted(int(r["store_id"]) for r in rejected),
    }
    if clustering_on:
        definition["grid_clustering"] = dict(grid_clustering or {})
    config_hash = _plan_hash(definition, tasks)
    for t in tasks:
        t["config_hash"] = config_hash

    run_prefix = run_prefix_for(s3_prefix, schedule_date_vn, run_id)
    plan: dict[str, Any] = {
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "mode": "daily_forecast",
        "run_id": run_id,
        "ingest_date": schedule_date_vn,
        "scheduled_at_utc": _iso_utc(scheduled_at),
        "planned_at_utc": _iso_utc(planned_at),
        "schedule_id": schedule_id,
        "refresh_seq": refresh_seq,
        "cohort_id": cohort_id,
        "cohort_policy_version": cohort_policy_version,
        "contract_version": contract_version,
        "contract_versions": [contract_version],
        "model": model,
        "config_hash": config_hash,
        "run_prefix": run_prefix,
        "plan_s3_key": f"{run_prefix}/plan.json",
        "locations_s3_key": f"{run_prefix}/locations.json",
        "eligible_store_ids": [int(e["store_id"]) for e in eligible],
        "rejected_locations": rejected,
        "task_count": len(tasks),
        "estimated_cost_total": round(cost * len(tasks), 6),
        "tasks": tasks,
    }
    if clustering_on:
        plan["grid_clustering"] = dict(grid_clustering or {})
        plan["store_grid_mapping_s3_key"] = f"{run_prefix}/store_grid_mapping.json"
        plan["eligible_store_count"] = len(eligible)
        plan["point_count"] = len(tasks)
    return _finalize(plan, eligible, sink, dry_run, store_grid_mapping=mapping_rows)


# ------------------------------------------------------------ backfill plan


def _segments(start: date, end: date) -> list[tuple[str, date, date]]:
    segs: list[tuple[str, date, date]] = []
    if start <= ERA5_MAX_DATE:
        segs.append(("historical_weather", max(start, ERA5_MIN_DATE), min(end, ERA5_MAX_DATE)))
    if end >= GFS_MIN_DATE:
        segs.append(("historical_forecast", max(start, GFS_MIN_DATE), end))
    return segs


def _chunks(seg_start: date, seg_end: date) -> list[tuple[date, date]]:
    out = []
    d = seg_start
    while d <= seg_end:
        e = min(d + timedelta(days=CHUNK_DAYS - 1), seg_end)
        out.append((d, e))
        d = e + timedelta(days=1)
    return out


def create_backfill_plan(
    *,
    eligible_locations: Sequence[Any],
    rejected_locations: Sequence[Any],
    request_id: str,
    start_date: str,
    end_date: str,
    today_vn: str,
    cohort_policy_version: str = "pilot_v1",
    contract_version: str = "weather_variables_v1",
    sink: Any = None,
    dry_run: bool = False,
    reason: str | None = None,
    cohort_id: str | None = None,
    planned_at_utc: datetime | None = None,
    used_daily: float = 0.0,
    used_backfill: float = 0.0,
    daily_limit: float = DEFAULT_DAILY_LIMIT,
    daily_reserve: float = DEFAULT_DAILY_RESERVE,
) -> dict[str, Any]:
    """Historical backfill: split at 2022-01-01 (ERA5 | GFS), then 14-day chunks per store."""
    if not request_id or not str(request_id).strip():
        raise ValueError("request_id is required for backfill")
    start, end, today = date.fromisoformat(start_date), date.fromisoformat(end_date), date.fromisoformat(today_vn)
    if start > end:
        raise ValueError("start_date must be <= end_date")
    if end >= today:
        raise ValueError("end_date must be before today (VN); future/today windows are not backfill")
    if end < ERA5_MIN_DATE:
        raise ValueError("UNAVAILABLE_BEFORE_MODEL_COVERAGE: end_date is before 1940-01-01")

    eligible = [_loc(e) for e in eligible_locations]
    rejected = [_loc(r) for r in rejected_locations]
    if not eligible:
        raise ValueError("NO_ELIGIBLE_LOCATIONS: refusing to create an empty run")

    gfs = load_variable_contract(contract_version)
    era5 = load_variable_contract("weather_era5_v1")
    by_endpoint = {"historical_weather": era5, "historical_forecast": gfs}

    run_id = build_backfill_run_id(
        ingest_date_vn=today_vn, request_id=request_id,
        cohort_policy_version=cohort_policy_version, contract_version=contract_version,
    )
    planned_at = _require_aware(planned_at_utc, "planned_at_utc") if planned_at_utc else datetime.now(timezone.utc)

    tasks: list[dict[str, Any]] = []
    segments = _segments(start, end)
    for endpoint_key, seg_start, seg_end in segments:
        contract = by_endpoint[endpoint_key]
        for c_start, c_end in _chunks(seg_start, seg_end):
            n_days = (c_end - c_start).days + 1
            cost = estimate_call_cost(contract["n_variables"], n_days)
            for loc in sorted(eligible, key=lambda x: int(x["store_id"])):
                s, e = c_start.isoformat(), c_end.isoformat()
                tasks.append(
                    {
                        "run_id": run_id,
                        "task_id": build_task_id(
                            run_id=run_id, store_id=loc["store_id"], endpoint_key=endpoint_key, start_date=s,
                            end_date=e, contract_version=contract["contract_version"], model=contract["model"],
                        ),
                        "task_index": len(tasks),
                        "ingest_date": today_vn,
                        "mode": "historical_backfill",
                        "endpoint_key": endpoint_key,
                        "s3_prefix": ENDPOINT_PREFIX[endpoint_key],
                        **{k: loc.get(k) for k in TASK_LOCATION_FIELDS},
                        "start_date": s,
                        "end_date": e,
                        "expected_days": n_days,
                        "contract_version": contract["contract_version"],
                        "model": contract["model"],
                        "source_type": SOURCE_TYPE[endpoint_key],
                        "estimated_cost": cost,
                        "planned_at_utc": _iso_utc(planned_at),
                    }
                )

    total = round(sum(t["estimated_cost"] for t in tasks), 6)
    admission = check_budget_admission(
        mode="historical_backfill", required_units=total, daily_limit=daily_limit,
        daily_reserve=daily_reserve, used_daily=used_daily, used_backfill=used_backfill,
    )
    if not admission["allowed"] or total > BACKFILL_DAILY_ALLOWANCE:
        raise ValueError(
            f"BUDGET_EXCEEDED_FOR_RUN: requires {total} units, backfill allowance today is "
            f"{admission['available_units']} (daily reserve {daily_reserve} protected)"
        )

    definition = {
        "mode": "historical_backfill",
        "run_id": run_id,
        "request_id": request_id,
        "start_date": start_date,
        "end_date": end_date,
        "cohort_policy_version": cohort_policy_version,
        "contracts": [_contract_fingerprint(by_endpoint[s[0]]) for s in segments],
        "rejected_store_ids": sorted(int(r["store_id"]) for r in rejected),
    }
    config_hash = _plan_hash(definition, tasks)
    for t in tasks:
        t["config_hash"] = config_hash

    first_prefix = ENDPOINT_PREFIX[segments[0][0]]
    run_prefix = run_prefix_for(first_prefix, today_vn, run_id)
    plan = {
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "mode": "historical_backfill",
        "run_id": run_id,
        "ingest_date": today_vn,
        "planned_at_utc": _iso_utc(planned_at),
        "request_id": request_id,
        "reason": reason,
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "segments": [
            {"endpoint_key": k, "start_date": s.isoformat(), "end_date": e.isoformat(),
             "s3_prefix": ENDPOINT_PREFIX[k], "contract_version": by_endpoint[k]["contract_version"]}
            for k, s, e in segments
        ],
        "cohort_id": cohort_id,
        "cohort_policy_version": cohort_policy_version,
        "contract_version": contract_version,
        "contract_versions": [by_endpoint[s[0]]["contract_version"] for s in segments],
        "model": gfs["model"],
        "config_hash": config_hash,
        "run_prefix": run_prefix,
        "plan_s3_key": f"{run_prefix}/plan.json",
        "locations_s3_key": f"{run_prefix}/locations.json",
        "eligible_store_ids": sorted({t["store_id"] for t in tasks}),
        "rejected_locations": rejected,
        "task_count": len(tasks),
        "estimated_cost_total": total,
        "budget_admission": admission,
        "tasks": tasks,
    }
    return _finalize(plan, eligible, sink, dry_run)


# ------------------------------------------------------------ queue / replay


def build_task_queue_message(
    *, run_id: str, task_id: str, task_index: int, plan_s3_key: str, config_hash: str
) -> dict[str, Any]:
    """Lightweight queue reference: no DSN, secrets, coordinates or payload."""
    return {
        "message_schema_version": MESSAGE_SCHEMA_VERSION,
        "run_id": run_id,
        "task_id": task_id,
        "task_index": int(task_index),
        "plan_s3_key": plan_s3_key,
        "config_hash": config_hash,
    }


def pending_tasks(plan: Mapping[str, Any], sink: Any) -> list[dict[str, Any]]:
    return [dict(t) for t in plan.get("tasks", []) if not sink.exists(accepted_key_for(t))]


def load_or_create_plan(
    *,
    sink: Any,
    plan_s3_key: str,
    expected_config_hash: str | None,
    db_reader: Callable[[], Any],
    plan_builder: Callable[[Any], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Replay a frozen plan.json (no DB read) or build+persist a new one via plan_builder(db_reader())."""
    if sink.exists(plan_s3_key):
        plan = sink.get_json(plan_s3_key)
        if expected_config_hash is not None and plan.get("config_hash") != expected_config_hash:
            raise ValueError(
                f"config_hash mismatch for frozen plan {plan_s3_key}: "
                f"expected {expected_config_hash}, found {plan.get('config_hash')}"
            )
        result = dict(plan)
        result["replayed"] = True
        result["pending_tasks"] = pending_tasks(plan, sink)
        return result

    if plan_builder is None:
        raise ValueError(f"No frozen plan at {plan_s3_key} and no plan_builder supplied")
    plan = dict(plan_builder(db_reader()))
    if plan.get("plan_s3_key") != plan_s3_key:
        raise ValueError(f"Built plan key {plan.get('plan_s3_key')} != expected {plan_s3_key}")
    if not sink.exists(plan_s3_key):
        raise ValueError("plan_builder must persist the plan (sink provided, dry_run=False)")
    result = dict(plan)
    result["replayed"] = False
    result["pending_tasks"] = pending_tasks(plan, sink)
    return result
