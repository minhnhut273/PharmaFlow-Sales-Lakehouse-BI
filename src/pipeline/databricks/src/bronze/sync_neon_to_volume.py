"""Fallback REPEATABLE READ Neon PostgreSQL -> Databricks Managed Volume exporter.

Matches ``pg_snapshot.py --source-mode volume`` by writing per-table ``.jsonl.gz`` exports
first inside a single repeatable-read PostgreSQL transaction and uploading ``manifest.json`` last.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
import uuid
from collections.abc import Sequence
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_PKG_ROOT = Path(__file__).resolve().parents[2]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from src.bronze.pg_snapshot import SourceTableSpec, resolve_tables  # noqa: E402
from src.common.workspace import build_workspace_client_from_env, default_dotenv_path  # noqa: E402

DEFAULT_CATALOG = "pharmaflow_dev"
DEFAULT_SCHEMA = "bronze_pg"
DEFAULT_VOLUME = "pg_raw"


def json_default(value: Any) -> Any:
    """Serialize PostgreSQL Python driver types cleanly into JSON lines."""
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    return str(value)


def export_table_rows_to_jsonl_gz(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> tuple[bytes, int, str]:
    """Encode rows from one cursor result into gzipped JSON Lines and return ``(gz_bytes, row_count, sha256)``."""
    buf = io.BytesIO()
    row_count = 0
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        for row in rows:
            record = dict(zip(columns, row))
            line = (json.dumps(record, ensure_ascii=False, default=json_default) + "\n").encode("utf-8")
            gz.write(line)
            row_count += 1
    payload = buf.getvalue()
    return payload, row_count, hashlib.sha256(payload).hexdigest()


def sync_neon_tables_to_volume(
    *,
    pg_conn: Any,
    workspace_client: Any,
    tables: Sequence[SourceTableSpec],
    catalog: str = DEFAULT_CATALOG,
    schema: str = DEFAULT_SCHEMA,
    volume: str = DEFAULT_VOLUME,
    run_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Export ``tables`` under a single REPEATABLE READ snapshot and upload to Databricks Volume."""
    started_at = datetime.now(timezone.utc)
    effective_run_id = run_id or f"pgvol-{started_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    volume_run_dir = f"/Volumes/{catalog}/{schema}/{volume}/run_id={effective_run_id}"

    manifest_tables: dict[str, dict[str, Any]] = {}
    staged_payloads: list[tuple[str, bytes]] = []

    with pg_conn.transaction():
        pg_conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        for spec in tables:
            with pg_conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {spec.fq_source}")
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
            file_name = f"{spec.bronze_table}.jsonl.gz"
            gz_bytes, row_count, sha256 = export_table_rows_to_jsonl_gz(columns, rows)
            manifest_tables[spec.fq_source] = {
                "file_name": file_name,
                "row_count": row_count,
                "sha256": sha256,
                "bytes": len(gz_bytes),
            }
            staged_payloads.append((f"{volume_run_dir}/{file_name}", gz_bytes))

    manifest = {
        "run_id": effective_run_id,
        "generated_at_utc": started_at.isoformat().replace("+00:00", "Z"),
        "source_mode": "volume",
        "tables": manifest_tables,
    }

    if dry_run:
        return {
            "status": "DRY_RUN",
            "run_id": effective_run_id,
            "volume_run_dir": volume_run_dir,
            "tables": manifest_tables,
        }

    for remote_path, payload in staged_payloads:
        workspace_client.files.upload(remote_path, io.BytesIO(payload), overwrite=True)

    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    workspace_client.files.upload(f"{volume_run_dir}/manifest.json", io.BytesIO(manifest_bytes), overwrite=True)

    return {
        "status": "UPLOADED",
        "run_id": effective_run_id,
        "volume_run_dir": volume_run_dir,
        "table_count": len(manifest_tables),
        "tables": manifest_tables,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=DEFAULT_CATALOG)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--volume", default=DEFAULT_VOLUME)
    parser.add_argument("--tables", default="all")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dotenv", default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    import psycopg

    args = parse_args(argv)
    resolved_dotenv = Path(args.dotenv) if args.dotenv else default_dotenv_path()
    load_dotenv(resolved_dotenv, override=False)
    dsn = os.environ.get("DATABASE_URL_UNPOOLED")
    if not dsn:
        raise ValueError("DATABASE_URL_UNPOOLED must be set in environment or .env")

    workspace_client = build_workspace_client_from_env(resolved_dotenv)
    tables = resolve_tables(args.tables)
    with psycopg.connect(dsn) as pg_conn:
        result = sync_neon_tables_to_volume(
            pg_conn=pg_conn,
            workspace_client=workspace_client,
            tables=tables,
            catalog=args.catalog,
            schema=args.schema,
            volume=args.volume,
            run_id=args.run_id,
            dry_run=args.dry_run,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
