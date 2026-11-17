"""Provision an isolated Databricks Serverless auxiliary sync job for AWS Quick.

Reads ``DATABRICKS_HOST``, ``DATABRICKS_TOKEN``, and ``QUICK_NEON_DATABASE_URL`` from ``.env``
without echoing any secret, stores the Neon BI URL inside a dedicated secret scope
(``quick-sync-aux``), uploads ``sync_gold_to_neon.py`` to the current Databricks user's
Workspace folder, and creates/updates the standalone job ``[aux] quick_gold_md01_sync``.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import compute, jobs, workspace

try:
    from src.sync_quick.sync_gold_to_neon import (
        DEFAULT_CATALOG,
        DEFAULT_SECRET_KEY,
        DEFAULT_SECRET_SCOPE,
        DEFAULT_SOURCE_SCHEMA,
        DEFAULT_TARGET_SCHEMA,
        parse_pg_dsn,
        redact_pg_target,
    )
except ModuleNotFoundError:  # Allow running directly as a script from any CWD
    from sync_gold_to_neon import (
        DEFAULT_CATALOG,
        DEFAULT_SECRET_KEY,
        DEFAULT_SECRET_SCOPE,
        DEFAULT_SOURCE_SCHEMA,
        DEFAULT_TARGET_SCHEMA,
        parse_pg_dsn,
        redact_pg_target,
    )

AUX_JOB_NAME = "[aux] quick_gold_md01_sync"


def _ensure_secret(w: WorkspaceClient, scope: str, key: str, value: str) -> None:
    existing = {s.name for s in w.secrets.list_scopes()}
    if scope not in existing:
        w.secrets.create_scope(scope=scope)
    w.secrets.put_secret(scope=scope, key=key, string_value=value)


def _resolve_workspace_user(w: WorkspaceClient, explicit_user: str | None) -> str:
    if explicit_user:
        return explicit_user.strip()
    try:
        me = w.current_user.me()
        if me.user_name:
            return me.user_name
    except Exception:  # noqa: BLE001
        pass
    entries = list(w.workspace.list("/Workspace/Users"))
    if len(entries) == 1 and entries[0].path:
        return entries[0].path.rstrip("/").rsplit("/", 1)[-1]
    raise RuntimeError("Could not resolve Databricks workspace user automatically; pass --workspace-user <email>")


def _build_job_settings(
    *,
    notebook_path: str,
    catalog: str,
    source_schema: str,
    target_schema: str,
    tables: str,
    secret_scope: str,
    secret_key: str,
    trigger_mode: str,
    cron_expr: str,
) -> jobs.JobSettings:
    env_spec = jobs.JobEnvironment(
        environment_key="quick_sync_serverless",
        spec=compute.Environment(
            client="2",
            dependencies=["psycopg[binary]>=3,<4"],
        ),
    )
    task = jobs.Task(
        task_key="sync_gold_md01_to_neon",
        environment_key="quick_sync_serverless",
        notebook_task=jobs.NotebookTask(
            notebook_path=notebook_path,
            base_parameters={
                "mode": "databricks",
                "catalog": catalog,
                "source_schema": source_schema,
                "target_schema": target_schema,
                "tables": tables,
                "secret_scope": secret_scope,
                "secret_key": secret_key,
            },
        ),
    )
    kwargs: dict[str, object] = {
        "name": AUX_JOB_NAME,
        "description": "Out-of-scope auxiliary bridge: sync Gold MD-01 marts to Neon #2 for AWS Quick.",
        "max_concurrent_runs": 1,
        "environments": [env_spec],
        "tasks": [task],
        "tags": {"scope": "out_of_scope_aux", "purpose": "aws_quick_bi_mirror"},
    }
    if trigger_mode == "table":
        kwargs["trigger"] = jobs.TriggerSettings(
            table_update=jobs.TableUpdateTriggerConfiguration(
                table_names=[f"{catalog}.ops.product_release"],
                min_time_between_triggers_seconds=300,
                wait_after_last_change_seconds=60,
            )
        )
    elif trigger_mode == "cron":
        kwargs["schedule"] = jobs.CronSchedule(
            quartz_cron_expression=cron_expr,
            timezone_id="Asia/Ho_Chi_Minh",
        )
    return jobs.JobSettings(**kwargs)


def setup_aux_job(
    *,
    trigger_mode: str = "table",
    cron_expr: str = "0 45 6 * * ?",
    tables: str = "default",
    target_schema: str = DEFAULT_TARGET_SCHEMA,
    workspace_user: str | None = None,
    run_now: bool = False,
) -> dict[str, object]:
    neon_dsn = os.environ.get("QUICK_NEON_DATABASE_URL", "").strip()
    if not neon_dsn:
        raise RuntimeError("Missing QUICK_NEON_DATABASE_URL in .env")
    pg_cfg = parse_pg_dsn(neon_dsn)

    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"].strip(),
        token=os.environ["DATABRICKS_TOKEN"].strip(),
    )
    _ensure_secret(w, DEFAULT_SECRET_SCOPE, DEFAULT_SECRET_KEY, pg_cfg.psycopg_dsn)

    user_name = _resolve_workspace_user(w, workspace_user)
    ws_dir = f"/Workspace/Users/{user_name}/aux_sync_quick"
    ws_script_path = f"{ws_dir}/sync_gold_to_neon.py"
    w.workspace.mkdirs(ws_dir)
    script_bytes = (Path(__file__).resolve().parent / "sync_gold_to_neon.py").read_bytes()
    w.workspace.import_(
        path=ws_script_path,
        content=base64.b64encode(script_bytes).decode("ascii"),
        format=workspace.ImportFormat.SOURCE,
        language=workspace.Language.PYTHON,
        overwrite=True,
    )

    existing_job = next((j for j in w.jobs.list(name=AUX_JOB_NAME) if j.settings and j.settings.name == AUX_JOB_NAME), None)
    effective_trigger = trigger_mode
    settings = _build_job_settings(
        notebook_path=ws_script_path,
        catalog=DEFAULT_CATALOG,
        source_schema=DEFAULT_SOURCE_SCHEMA,
        target_schema=target_schema,
        tables=tables,
        secret_scope=DEFAULT_SECRET_SCOPE,
        secret_key=DEFAULT_SECRET_KEY,
        trigger_mode=effective_trigger,
        cron_expr=cron_expr,
    )

    def _upsert(job_settings: jobs.JobSettings) -> int:
        if existing_job and existing_job.job_id is not None:
            w.jobs.reset(job_id=existing_job.job_id, new_settings=job_settings)
            return int(existing_job.job_id)
        created = w.jobs.create(**{k: v for k, v in job_settings.__dict__.items() if v is not None})
        return int(created.job_id)

    try:
        job_id = _upsert(settings)
    except Exception:
        if effective_trigger != "table":
            raise
        # Free Edition fallback if table_update triggers are disallowed.
        effective_trigger = "cron"
        fallback_settings = _build_job_settings(
            notebook_path=ws_script_path,
            catalog=DEFAULT_CATALOG,
            source_schema=DEFAULT_SOURCE_SCHEMA,
            target_schema=target_schema,
            tables=tables,
            secret_scope=DEFAULT_SECRET_SCOPE,
            secret_key=DEFAULT_SECRET_KEY,
            trigger_mode="cron",
            cron_expr=cron_expr,
        )
        job_id = _upsert(fallback_settings)

    run_id = None
    if run_now:
        waiter = w.jobs.run_now(job_id=job_id)
        run_id = getattr(waiter, "run_id", None)

    return {
        "job_id": job_id,
        "job_name": AUX_JOB_NAME,
        "workspace_script": ws_script_path,
        "secret_scope": DEFAULT_SECRET_SCOPE,
        "target": redact_pg_target(pg_cfg),
        "target_schema": target_schema,
        "trigger_mode": effective_trigger,
        "triggered_run_id": run_id,
    }


def main() -> int:
    from dotenv import load_dotenv

    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trigger", choices=("table", "cron", "manual"), default="table")
    parser.add_argument("--cron", default="0 45 6 * * ?")
    parser.add_argument("--tables", default="default")
    parser.add_argument(
        "--target-schema",
        default=(os.environ.get("QUICK_NEON_SCHEMA") or "").strip() or DEFAULT_TARGET_SCHEMA,
    )
    parser.add_argument("--workspace-user", default=None)
    parser.add_argument("--run-now", action="store_true")
    args = parser.parse_args()

    result = setup_aux_job(
        trigger_mode=args.trigger,
        cron_expr=args.cron,
        tables=args.tables,
        target_schema=args.target_schema,
        workspace_user=args.workspace_user,
        run_now=args.run_now,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
