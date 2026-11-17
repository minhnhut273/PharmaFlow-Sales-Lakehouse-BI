"""Local operations CLI for P1/P2.

    python -B -m src.weather.cli preflight
    python -B -m src.weather.cli locations --cohort pilot
    python -B -m src.weather.cli plan daily --cohort pilot [--location-ids 516,5404] [--dry-run]
    python -B -m src.weather.cli plan backfill --start-date 2021-12-25 --end-date 2022-01-05 \
        --location-ids 516 --request-id pilot-cross-2022 [--dry-run]
    python -B -m src.weather.cli run --plan <plan key> --sink local
    python -B -m src.weather.cli status --run-id <run_id>
    python -B -m src.weather.cli resume --run-id <run_id>

The Neon DSN is read from WEATHER_NEON_DSN and is never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.weather import __version__
from src.weather.aws_session import S3Config, S3ConfigError, assume_writer_session, load_s3_config
from src.weather.config import load_cohorts_config, load_variable_contract, resolve_cohort
from src.weather.locations import evaluate_locations, fetch_db_identity, read_all_active_store_rows, read_store_rows
from src.weather.planner import (
    MANUAL_SCHEDULE_ID,
    VN_TZ,
    accepted_key_for,
    build_backfill_run_id,
    build_daily_run_id,
    build_task_queue_message,
    create_backfill_plan,
    create_daily_plan,
    predict_plan_key,
)
from src.weather.reconcile import summarize_run_outcomes, write_summary
from src.weather.state import LocalStateStore
from src.weather.storage import WEATHER_PREFIXES, LocalSink, S3Sink

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = REPO_ROOT / ".runtime" / "weather"
DSN_ENV = "WEATHER_NEON_DSN"
EXPECTED_DATABASE = "pharmaflow_source_postgre_v2"
MAX_RETRYABLE_ATTEMPTS = 3  # first try + 2 retries
LEASE_SECONDS = 300

_DSN_PATTERN = re.compile(r"postgres(?:ql)?://\S+", re.IGNORECASE)


class CliError(Exception):
    """User-facing error with an exit code."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _redact(text: str) -> str:
    text = _DSN_PATTERN.sub("<redacted-dsn>", text)
    return re.sub(r"(password\s*=\s*)\S+", r"\1<redacted>", text, flags=re.IGNORECASE)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ids(raw: str | None) -> list[int] | None:
    if raw is None:
        return None
    try:
        ids = sorted({int(x) for x in raw.split(",") if x.strip()})
    except ValueError:
        raise CliError(f"--location-ids must be comma-separated integers, got {raw!r}", 2) from None
    if not ids:
        raise CliError("--location-ids is empty", 2)
    return ids


def _parse_utc(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise CliError("--scheduled-at must include a timezone (e.g. 2026-11-11T23:00:00Z)", 2)
    return dt.astimezone(timezone.utc)


# ------------------------------------------------------------------ context


def _default_s3_factory(config: S3Config) -> tuple[Any, dict[str, str]]:
    """Assume the writer role and return (S3 client, identity info). No secrets are returned."""
    from botocore.config import Config

    session, info = assume_writer_session(config)
    client = session.client("s3", region_name=config.region,
                            config=Config(retries={"mode": "standard", "total_max_attempts": 5},
                                          connect_timeout=10, read_timeout=60))
    return client, info


class Context:
    def __init__(
        self,
        *,
        runtime_dir: Path,
        store_rows_override: Sequence[Mapping[str, Any]] | None,
        fetcher: Callable[[str, Mapping[str, Any]], Mapping[str, Any]] | None,
        sleep: Callable[[float], None],
        now_utc: datetime | None,
        dsn: str | None,
        s3_factory: Callable[[S3Config], tuple[Any, dict[str, str]]] | None = None,
        s3_env: Mapping[str, str] | None = None,
        dsn_provider: Callable[[], str] | None = None,
    ) -> None:
        self.runtime_dir = runtime_dir
        self.sink: Any = LocalSink(runtime_dir)
        self.state = LocalStateStore(runtime_dir / "state")
        self.sink_kind = "local"
        self.s3_identity: dict[str, str] | None = None
        self.s3_config: S3Config | None = None
        self._s3_factory = s3_factory or _default_s3_factory
        self._s3_env = s3_env
        self.store_rows_override = store_rows_override
        self.fetcher = fetcher
        self.sleep = sleep
        self._now = now_utc
        self._dsn = dsn
        self._dsn_provider = dsn_provider

    def attach(self, *, sink: Any, state: Any, kind: str) -> None:
        """Use an externally built sink/state (Lambda: S3Sink + DynamoStateStore with the execution role)."""
        self.sink, self.state, self.sink_kind = sink, state, kind

    def select_sink(self, kind: str) -> None:
        """local: .runtime/weather + state/. s3: bucket via assumed writer role + state/s3/<bucket>/."""
        if kind == "local":
            return
        if kind != "s3":
            raise CliError(f"unknown sink {kind!r}", 2)
        try:
            cfg = load_s3_config(self._s3_env)
            client, identity = self._s3_factory(cfg)
        except S3ConfigError as exc:
            raise CliError(str(exc), 1) from None
        except Exception as exc:  # noqa: BLE001 - surface AWS auth problems without stack traces
            raise CliError(f"AWS session failed ({type(exc).__name__}): {_redact(str(exc))[:300]}", 1) from None
        self.s3_config = cfg
        self.s3_identity = identity
        self.sink = S3Sink(bucket=cfg.bucket, client=client, region=cfg.region)
        self.state = LocalStateStore(self.runtime_dir / "state" / "s3" / cfg.bucket)
        self.sink_kind = "s3"

    def now(self) -> datetime:
        return self._now or datetime.now(timezone.utc)

    def today_vn(self) -> str:
        return self.now().astimezone(VN_TZ).date().isoformat()

    def dsn(self) -> str:
        if not self._dsn and self._dsn_provider is not None:
            self._dsn = self._dsn_provider()
        value = self._dsn or os.environ.get(DSN_ENV)
        if not value:
            raise CliError(f"{DSN_ENV} is not set (put it in .env); cannot read org.store", 1)
        return value

    def read_rows(self, store_ids: Sequence[int]) -> list[dict[str, Any]]:
        if self.store_rows_override is not None:
            wanted = set(store_ids)
            return [dict(r) for r in self.store_rows_override if int(r["store_id"]) in wanted]
        try:
            return read_store_rows(self.dsn(), store_ids)
        except CliError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak DSN in messages
            raise CliError(f"Neon read failed ({type(exc).__name__}): {_redact(str(exc))[:300]}", 1) from None

    def read_all_active_rows(self) -> list[dict[str, Any]]:
        if self.store_rows_override is not None:
            return [dict(r) for r in self.store_rows_override]
        try:
            return read_all_active_store_rows(self.dsn())
        except CliError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak DSN in messages
            raise CliError(f"Neon read failed ({type(exc).__name__}): {_redact(str(exc))[:300]}", 1) from None


def _resolve_selection(args: argparse.Namespace) -> tuple[dict[str, Any], list[int] | None, str]:
    cohort = resolve_cohort(args.cohort)
    ids = _parse_ids(getattr(args, "location_ids", None))
    if ids is None:
        if cohort.get("selection") == "all_active":
            return cohort, None, args.cohort
        return cohort, cohort["store_ids"], args.cohort
    return cohort, ids, f"{args.cohort}:ids={','.join(str(i) for i in ids)}"


def _evaluate(ctx: Context, cohort: Mapping[str, Any], ids: Sequence[int] | None) -> dict[str, Any]:
    rows = ctx.read_all_active_rows() if ids is None else ctx.read_rows(ids)
    return evaluate_locations(
        rows=rows,
        requested_store_ids=ids,
        allow_unknown_status=cohort["allow_unknown_status"],
        override_reason=cohort["override_reason"],
        source_provenance_map=cohort["source_provenance_map"],
    )


def _plan_view(plan: Mapping[str, Any], *, replayed: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "run_id": plan["run_id"],
        "mode": plan["mode"],
        "replayed_frozen_plan": replayed,
        "dry_run": plan.get("dry_run", False),
        "plan_s3_key": plan["plan_s3_key"],
        "config_hash": plan["config_hash"],
        "task_count": plan["task_count"],
        "estimated_cost_total": plan["estimated_cost_total"],
        "rejected_locations": plan.get("rejected_locations", []),
        "tasks": [
            {
                "task_index": t["task_index"],
                "task_id": t["task_id"],
                "store_id": t.get("store_id"),
                **({"grid_id": t["grid_id"]} if t.get("grid_id") is not None else {}),
                "endpoint_key": t["endpoint_key"],
                "s3_prefix": t["s3_prefix"],
                "start_date": t["start_date"],
                "end_date": t["end_date"],
                "contract_version": t["contract_version"],
                "estimated_cost": t["estimated_cost"],
            }
            for t in plan["tasks"]
        ],
        "queue_messages_preview": [
            build_task_queue_message(run_id=plan["run_id"], task_id=t["task_id"], task_index=t["task_index"],
                                     plan_s3_key=plan["plan_s3_key"], config_hash=plan["config_hash"])
            for t in plan["tasks"][:2]
        ],
    }
    if plan.get("store_grid_mapping_s3_key"):
        out["store_grid_mapping_s3_key"] = plan["store_grid_mapping_s3_key"]
    return out


# ----------------------------------------------------------------- commands


def _s3_preflight(ctx: Context) -> dict[str, Any]:
    """Read-only S3 checks with the assumed writer role (writes nothing)."""
    cfg, sink = ctx.s3_config, ctx.sink
    out: dict[str, Any] = {"bucket": cfg.bucket, "region": cfg.region, "role_arn": cfg.role_arn,
                           "assumed_arn": (ctx.s3_identity or {}).get("assumed_arn"),
                           "session_expires_at_utc": (ctx.s3_identity or {}).get("expires_at_utc")}
    try:
        loc = sink.client.get_bucket_location(Bucket=cfg.bucket).get("LocationConstraint") or "us-east-1"
        out["bucket_region"] = loc
        listed = {}
        for prefix in WEATHER_PREFIXES:
            resp = sink.client.list_objects_v2(Bucket=cfg.bucket, Prefix=prefix, MaxKeys=1)
            listed[prefix] = resp.get("KeyCount", 0)
        out["list_prefixes"] = listed
        out["ok"] = loc == cfg.region
    except Exception as exc:  # noqa: BLE001
        out.update({"ok": False, "error": f"{type(exc).__name__}: {_redact(str(exc))[:300]}"})
    return out


def cmd_preflight(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    ok = True
    try:
        gfs = load_variable_contract("weather_variables_v1")
        era5 = load_variable_contract("weather_era5_v1")
        cohorts = load_cohorts_config()
        checks["config"] = {
            "ok": True,
            "weather_variables_v1": f"{len(gfs['hourly_variables'])} hourly + {len(gfs['daily_variables'])} daily",
            "weather_era5_v1": f"{len(era5['hourly_variables'])} hourly + {len(era5['daily_variables'])} daily",
            "cohort_policy_version": cohorts["cohort_policy_version"],
            "cohorts": {
                k: (len(v["store_ids"]) if v.get("store_ids") is not None else v.get("selection", "dynamic"))
                for k, v in cohorts["cohorts"].items()
            },
        }
    except Exception as exc:  # noqa: BLE001
        ok = False
        checks["config"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    if ctx.store_rows_override is not None:
        checks["neon"] = {"ok": True, "skipped": "store_rows_override supplied"}
    else:
        try:
            ident = fetch_db_identity(ctx.dsn())
            least_priv = ident["store_select_required_columns"] and not (
                ident["store_insert"] or ident["store_update"] or ident["store_delete"] or ident["store_truncate"]
            )
            db_ok = ident["current_database"] == EXPECTED_DATABASE
            checks["neon"] = {"ok": bool(least_priv and db_ok and ident["session_read_only"]),
                              "expected_database": EXPECTED_DATABASE, **ident}
        except CliError as exc:
            checks["neon"] = {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            checks["neon"] = {"ok": False, "error": f"{type(exc).__name__}: {_redact(str(exc))[:300]}"}
        ok = ok and checks["neon"]["ok"]

    try:
        ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
        probe = ctx.runtime_dir / f".preflight-{uuid.uuid4().hex[:8]}"
        probe.write_bytes(b"ok")
        probe.unlink()
        checks["runtime_dir"] = {"ok": True, "path": str(ctx.runtime_dir)}
    except OSError as exc:
        ok = False
        checks["runtime_dir"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    if ctx.sink_kind == "s3":
        checks["s3"] = _s3_preflight(ctx)
        ok = ok and checks["s3"]["ok"]

    checks["open_meteo"] = {"ok": True, "skipped": "preflight never calls Open-Meteo"}
    return {"command": "preflight", "ok": ok, "code_version": __version__, "checks": checks}


def cmd_locations(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    cohort, ids, cohort_label = _resolve_selection(args)
    res = _evaluate(ctx, cohort, ids)
    requested_count = len(ids) if ids is not None else len(res["eligible_locations"]) + len(res["rejected_locations"])
    out: dict[str, Any] = {
        "command": "locations",
        "cohort": cohort_label,
        "cohort_policy_version": cohort["cohort_policy_version"],
        "requested": requested_count,
        "eligible_count": len(res["eligible_locations"]),
        "rejected_count": len(res["rejected_locations"]),
        "eligible_locations": [
            {k: loc[k] for k in ("store_id", "store_code", "country_code", "timezone_name", "source",
                                 "coordinate_provenance", "coordinate_verification_status")}
            for loc in res["eligible_locations"]
        ],
        "rejected_locations": res["rejected_locations"],
    }
    if ids is None and cohort.get("grid_clustering", {}).get("enabled"):
        from src.weather.grid import cluster_locations

        points, _ = cluster_locations(res["eligible_locations"], cohort["grid_clustering"])
        out["grid_clustering"] = cohort["grid_clustering"]
        out["point_count"] = len(points)
    return out


def cmd_plan_daily(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    cohort, ids, cohort_label = _resolve_selection(args)
    scheduled_at = _parse_utc(args.scheduled_at) if (args.scheduled_at and not str(args.scheduled_at).startswith("<")) else ctx.now()
    schedule_id = args.schedule_id
    date_vn = scheduled_at.astimezone(VN_TZ).date().isoformat()
    run_id = build_daily_run_id(
        schedule_date_vn=date_vn, schedule_id=schedule_id, cohort_id=cohort_label,
        cohort_policy_version=cohort["cohort_policy_version"], contract_version="weather_variables_v1",
        model="gfs_global", refresh_seq=args.refresh_seq,
    )
    plan_key = predict_plan_key("daily_forecast", date_vn, run_id)
    if ctx.sink.exists(plan_key):
        plan = ctx.sink.get_json(plan_key)
        return {"command": "plan daily", **_plan_view(plan, replayed=True)}

    res = _evaluate(ctx, cohort, ids)
    grid_cfg = cohort.get("grid_clustering") if getattr(args, "location_ids", None) is None else None
    try:
        plan = create_daily_plan(
            eligible_locations=res["eligible_locations"], rejected_locations=res["rejected_locations"],
            scheduled_at_utc=scheduled_at, schedule_id=schedule_id, cohort_id=cohort_label,
            cohort_policy_version=cohort["cohort_policy_version"], sink=ctx.sink, dry_run=args.dry_run,
            planned_at_utc=ctx.now() if not args.scheduled_at else scheduled_at, refresh_seq=args.refresh_seq,
            grid_clustering=grid_cfg,
        )
    except ValueError as exc:
        raise CliError(str(exc), 1) from None
    if plan["plan_s3_key"] != plan_key:
        raise CliError(f"Internal error: predicted plan key {plan_key} != {plan['plan_s3_key']}")
    if not args.dry_run:
        ctx.state.register_run(plan["run_id"], plan["plan_s3_key"], plan["mode"], **_sink_info(ctx))
    return {"command": "plan daily", **_plan_view(plan)}


def cmd_plan_backfill(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    cohort, ids, cohort_label = _resolve_selection(args)
    today_vn = ctx.today_vn()
    run_id = build_backfill_run_id(
        ingest_date_vn=today_vn, request_id=args.request_id,
        cohort_policy_version=cohort["cohort_policy_version"], contract_version="weather_variables_v1",
    )
    plan_key = predict_plan_key("historical_backfill", today_vn, run_id, start_date=args.start_date)
    if ctx.sink.exists(plan_key):
        plan = ctx.sink.get_json(plan_key)
        if (plan.get("requested_start_date"), plan.get("requested_end_date")) != (args.start_date, args.end_date):
            raise CliError(
                f"request_id {args.request_id!r} already planned today for "
                f"{plan.get('requested_start_date')}..{plan.get('requested_end_date')}; use a new --request-id"
            )
        return {"command": "plan backfill", **_plan_view(plan, replayed=True)}

    res = _evaluate(ctx, cohort, ids)
    budget = ctx.state.get_budget(today_vn)
    try:
        plan = create_backfill_plan(
            eligible_locations=res["eligible_locations"], rejected_locations=res["rejected_locations"],
            request_id=args.request_id, start_date=args.start_date, end_date=args.end_date, today_vn=today_vn,
            cohort_policy_version=cohort["cohort_policy_version"], sink=ctx.sink, dry_run=args.dry_run,
            reason=args.reason, cohort_id=cohort_label, planned_at_utc=ctx.now(),
            used_daily=budget["used_daily"], used_backfill=budget["used_backfill"],
        )
    except ValueError as exc:
        raise CliError(str(exc), 1) from None
    if plan["plan_s3_key"] != plan_key:
        raise CliError(f"Internal error: predicted plan key {plan_key} != {plan['plan_s3_key']}")
    if not args.dry_run:
        ctx.state.register_run(plan["run_id"], plan["plan_s3_key"], plan["mode"], **_sink_info(ctx))
    return {"command": "plan backfill", **_plan_view(plan)}


def _final_statuses(ctx: Context, plan: Mapping[str, Any]) -> dict[str, str]:
    recorded = ctx.state.get_task_statuses(plan["run_id"])
    out: dict[str, str] = {}
    for task in plan["tasks"]:
        tid = task["task_id"]
        rec_status = recorded.get(tid)
        if rec_status in ("SUCCEEDED", "ACCEPTED_WITH_WARNINGS", "FAILED_VALIDATION", "FAILED", "EXPIRED", "DLQ"):
            out[tid] = rec_status
        else:
            key = accepted_key_for(task)
            if ctx.sink.exists(key):
                out[tid] = ctx.sink.get_json(key).get("status", "SUCCEEDED")
            else:
                out[tid] = rec_status or "PENDING"
    return out


def _summary(ctx: Context, plan: Mapping[str, Any], *, write: bool) -> tuple[dict[str, Any], str | None]:
    summary = summarize_run_outcomes(
        run_id=plan["run_id"], expected_task_ids=[t["task_id"] for t in plan["tasks"]],
        task_statuses=_final_statuses(ctx, plan), rejected_locations=plan.get("rejected_locations", []),
    )
    key = write_summary(ctx.sink, plan, summary) if write else None
    return summary, key


def _sink_info(ctx: Context) -> dict[str, Any]:
    info: dict[str, Any] = {"sink": ctx.sink_kind}
    if ctx.sink_kind == "s3":
        info.update({"bucket": getattr(ctx.sink, "bucket", None), "region": getattr(ctx.sink, "region", None)})
    return info


def _execute_plan(ctx: Context, plan: Mapping[str, Any], *, max_tasks: int | None) -> dict[str, Any]:
    from src.weather.runner import Pacer, process_task

    run_id = plan["run_id"]
    ctx.state.register_run(run_id, plan["plan_s3_key"], plan["mode"], **_sink_info(ctx))
    worker_id = f"cli-{os.getpid()}-{uuid.uuid4().hex[:6]}"
    session_fetcher = ctx.fetcher
    if session_fetcher is None:
        from src.weather.open_meteo import _default_session, fetch_open_meteo

        session = _default_session()

        def session_fetcher(endpoint_key: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
            return fetch_open_meteo(endpoint_key=endpoint_key, params=params, session=session)

    http_calls = 0
    units_charged = 0.0
    results: list[dict[str, Any]] = []
    stopped_reason: str | None = None
    pacer = Pacer(ctx.sleep)
    processed = 0

    for task in plan["tasks"]:
        if max_tasks is not None and processed >= max_tasks:
            stopped_reason = f"max_tasks={max_tasks} reached"
            break
        row = process_task(task, sink=ctx.sink, state=ctx.state, fetcher=session_fetcher, worker_id=worker_id,
                           now_fn=ctx.now, sleep=ctx.sleep, max_attempts=MAX_RETRYABLE_ATTEMPTS,
                           lease_seconds=LEASE_SECONDS, pacer=pacer)
        if not str(row.get("status", "")).startswith("SKIPPED_ALREADY") and not str(
                row.get("status", "")).startswith("SKIPPED_TERMINAL"):
            processed += 1
        http_calls += row.pop("http_calls", 0)
        units_charged = round(units_charged + row.pop("units", 0.0), 6)
        results.append(row)
        if row.get("status") == "DEFERRED" and row.get("reason"):
            stopped_reason = "local daily budget exhausted"
            break
        if row.get("http_category") == "DEFERRED_RATE_LIMIT":
            stopped_reason = f"HTTP 429 (Retry-After={row.get('retry_after_seconds')}); run 'resume' later"
            break

    summary, summary_key = _summary(ctx, plan, write=True)
    return {
        "run_id": run_id,
        "sink": ctx.sink_kind,
        "plan_uri": ctx.sink.uri(plan["plan_s3_key"]),
        "plan_s3_key": plan["plan_s3_key"],
        "http_calls": http_calls,
        "units_charged": units_charged,
        "stopped_reason": stopped_reason,
        "tasks": results,
        "run_status": summary["run_status"],
        "status_counts": summary["status_counts"],
        "summary_key": summary_key,
    }


def cmd_run(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    if not ctx.sink.exists(args.plan):
        raise CliError(f"plan not found in {ctx.sink_kind} sink: {args.plan}", 1)
    plan = ctx.sink.get_json(args.plan)
    return {"command": "run", **_execute_plan(ctx, plan, max_tasks=args.max_tasks)}


def _plan_for_run(ctx: Context, run_id: str) -> dict[str, Any]:
    run = ctx.state.get_run(run_id)
    if not run:
        raise CliError(f"run_id {run_id!r} is not registered for --sink {ctx.sink_kind} ({ctx.state.root_dir})", 1)
    if run.get("sink", "local") != ctx.sink_kind:
        raise CliError(f"run_id {run_id!r} was registered with sink {run.get('sink')!r}, not {ctx.sink_kind!r}", 2)
    if ctx.sink_kind == "s3" and run.get("bucket") != getattr(ctx.sink, "bucket", None):
        raise CliError(f"run_id {run_id!r} belongs to bucket {run.get('bucket')!r}", 2)
    if not ctx.sink.exists(run["plan_key"]):
        raise CliError(f"plan.json missing for {run_id}: {run['plan_key']}", 1)
    return ctx.sink.get_json(run["plan_key"])


def cmd_resume(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    plan = _plan_for_run(ctx, args.run_id)
    return {"command": "resume", **_execute_plan(ctx, plan, max_tasks=args.max_tasks)}


def cmd_status(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    plan = _plan_for_run(ctx, args.run_id)
    summary, _ = _summary(ctx, plan, write=False)
    summaries = ctx.sink.list_keys(f"{plan['run_prefix']}/summary")
    tasks = []
    for t in plan["tasks"]:
        rec = ctx.state.get_task(plan["run_id"], t["task_id"]) or {}
        key = accepted_key_for(t)
        tasks.append({
            "task_id": t["task_id"], "store_id": t.get("store_id"),
            **({"grid_id": t["grid_id"]} if t.get("grid_id") is not None else {}),
            "endpoint_key": t["endpoint_key"],
            "window": f"{t['start_date']}..{t['end_date']}", "status": summary["task_statuses"][t["task_id"]],
            "attempt_count": rec.get("attempt_count", 0),
            "accepted_key": key if ctx.sink.exists(key) else None,
        })
    return {
        "command": "status", "run_id": plan["run_id"], "mode": plan["mode"], "sink": ctx.sink_kind,
        "plan_uri": ctx.sink.uri(plan["plan_s3_key"]), "plan_s3_key": plan["plan_s3_key"],
        "run_status": summary["run_status"], "is_terminal": summary["is_terminal"],
        "status_counts": summary["status_counts"], "summary_keys": summaries, "tasks": tasks,
    }


# --------------------------------------------------------------------- argv


def _add_sink(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sink", choices=("local", "s3"), default="local",
                        help="local: .runtime/weather (P1); s3: dev bucket via the assumed writer role (P2)")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.weather.cli", description="PharmaFlow weather ingestion (local CLI)")
    sub = p.add_subparsers(dest="command", required=True)

    pre = sub.add_parser("preflight", help="check config, Neon read-only access, runtime dir (and S3 with --sink s3)")
    _add_sink(pre)

    loc = sub.add_parser("locations", help="evaluate cohort locations from org.store")
    loc.add_argument("--cohort", default="pilot")
    loc.add_argument("--location-ids")

    plan = sub.add_parser("plan", help="create (or replay) a frozen plan")
    plan_sub = plan.add_subparsers(dest="plan_mode", required=True)
    daily = plan_sub.add_parser("daily")
    daily.add_argument("--cohort", default="pilot")
    daily.add_argument("--location-ids")
    daily.add_argument("--schedule-id", default=MANUAL_SCHEDULE_ID)
    daily.add_argument("--scheduled-at", help="ISO UTC instant; default now")
    daily.add_argument("--refresh-seq", type=int)
    daily.add_argument("--dry-run", action="store_true")
    _add_sink(daily)
    back = plan_sub.add_parser("backfill")
    back.add_argument("--start-date", required=True)
    back.add_argument("--end-date", required=True)
    back.add_argument("--request-id", required=True)
    back.add_argument("--cohort", default="pilot")
    back.add_argument("--location-ids")
    back.add_argument("--reason")
    back.add_argument("--dry-run", action="store_true")
    _add_sink(back)

    run = sub.add_parser("run", help="execute pending tasks of a plan")
    run.add_argument("--plan", required=True, help="plan key, e.g. raw/open_meteo/.../plan.json")
    _add_sink(run)
    run.add_argument("--max-tasks", type=int)

    st = sub.add_parser("status", help="show run status (read-only)")
    st.add_argument("--run-id", required=True)
    _add_sink(st)

    rs = sub.add_parser("resume", help="re-run unfinished tasks of a registered run")
    rs.add_argument("--run-id", required=True)
    rs.add_argument("--max-tasks", type=int)
    _add_sink(rs)
    return p


COMMANDS: dict[str, Callable[[Context, argparse.Namespace], dict[str, Any]]] = {
    "preflight": cmd_preflight,
    "locations": cmd_locations,
    "run": cmd_run,
    "status": cmd_status,
    "resume": cmd_resume,
}


def run_cli(
    argv: Sequence[str],
    *,
    store_rows_override: Sequence[Mapping[str, Any]] | None = None,
    runtime_dir: Path | None = None,
    fetcher: Callable[[str, Mapping[str, Any]], Mapping[str, Any]] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now_utc: datetime | None = None,
    dsn: str | None = None,
    s3_factory: Callable[[S3Config], tuple[Any, dict[str, str]]] | None = None,
    s3_env: Mapping[str, str] | None = None,
) -> tuple[int, dict[str, Any] | str]:
    parser = _build_parser()
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return (int(exc.code or 0), "usage error (see --help)") if exc.code else (0, "help")

    ctx = Context(runtime_dir=Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR,
                  store_rows_override=store_rows_override, fetcher=fetcher, sleep=sleep, now_utc=now_utc, dsn=dsn,
                  s3_factory=s3_factory, s3_env=s3_env)
    try:
        ctx.select_sink(getattr(args, "sink", "local"))
        if args.command == "plan":
            handler = cmd_plan_daily if args.plan_mode == "daily" else cmd_plan_backfill
        else:
            handler = COMMANDS[args.command]
        output = handler(ctx, args)
    except CliError as exc:
        return exc.exit_code, {"command": args.command, "ok": False, "error": _redact(str(exc))}
    if args.command == "preflight" and not output.get("ok"):
        return 1, output
    return 0, output


def main(argv: Sequence[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env", override=False)
    except ImportError:
        pass
    code, output = run_cli(sys.argv[1:] if argv is None else argv)
    text = json.dumps(output, ensure_ascii=False, indent=2) if isinstance(output, dict) else str(output)
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
