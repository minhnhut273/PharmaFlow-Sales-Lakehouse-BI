# Databricks notebook source
"""Out-of-scope auxiliary bridge: sync Gold MD-01 marts to a dedicated Neon PostgreSQL BI mirror.

Supports two execution modes without modifying core PharmaFlow pipelines:
- ``local``: reads Databricks Unity Catalog via SQL Statement Execution API (CSV external links)
  and bulk-loads into Neon via ``psycopg`` ``COPY`` with atomic staging-table swap.
- ``databricks``: runs inside a standalone Databricks Serverless job, writes staging tables via
  Spark JDBC directly to Neon, and atomically swaps tables + recreates ``mart_sales_daily`` view.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import time
import urllib.parse
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MD01_DOMAIN = "MD01_SALES_AND_DEMAND"
DEFAULT_CATALOG = "pharmaflow_dev"
DEFAULT_SOURCE_SCHEMA = "gold_md01_sales"
DEFAULT_TARGET_SCHEMA = "quick_gold_md01"
DEFAULT_WAREHOUSE_ID = "8ba78bc4f35756d5"
DEFAULT_SECRET_SCOPE = "quick-sync-aux"
DEFAULT_SECRET_KEY = "neon_database_url"

# mart_sales_weather_daily already includes all 29 columns of mart_sales_daily (SELECT m.*).
# Exposing mart_sales_daily as a PostgreSQL VIEW saves ~474k rows of duplicate storage on Neon Free.
DEFAULT_PHYSICAL_TABLES: tuple[str, ...] = (
    "mart_sales_weather_daily",
    "kpi_sales_trend",
    "mart_sales_observation_period",
)
ALL_SUPPORTED_TABLES: tuple[str, ...] = (
    "mart_sales_weather_daily",
    "kpi_sales_trend",
    "mart_sales_observation_period",
    "mart_sales_daily",
)

MART_SALES_DAILY_COLUMNS: tuple[str, ...] = (
    "product_id",
    "product_code",
    "product_name",
    "brand_name",
    "manufacturer_id",
    "manufacturer_name",
    "demand_location_id",
    "store_id",
    "store_code",
    "store_name",
    "country_code",
    "timezone_name",
    "latitude",
    "longitude",
    "local_date",
    "sales_uom_code",
    "currency_code",
    "provenance_class",
    "source",
    "line_count",
    "order_count",
    "sold_qty",
    "base_qty",
    "line_amount",
    "cost_amount",
    "margin_amount",
    "promo_sold_qty",
    "promo_line_count",
    "has_promotion",
)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DECIMAL_RE = re.compile(r"^decimal\(\s*(\d+)\s*,\s*(\d+)\s*\)$", re.IGNORECASE)


@dataclass(frozen=True)
class PgTargetConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    sslmode: str
    psycopg_dsn: str
    jdbc_url: str


def validate_identifier(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name


def resolve_tables(tables_csv: str | None) -> tuple[str, ...]:
    if not tables_csv or tables_csv.strip().lower() in ("", "default"):
        return DEFAULT_PHYSICAL_TABLES
    if tables_csv.strip().lower() == "all":
        return ALL_SUPPORTED_TABLES
    resolved: list[str] = []
    for raw in tables_csv.split(","):
        item = raw.strip()
        if not item:
            continue
        if item not in ALL_SUPPORTED_TABLES:
            raise ValueError(f"Unsupported Gold MD-01 table {item!r}; valid={ALL_SUPPORTED_TABLES}")
        if item not in resolved:
            resolved.append(item)
    if not resolved:
        raise ValueError("No valid tables resolved from --tables")
    return tuple(resolved)


def parse_pg_dsn(raw_dsn: str) -> PgTargetConfig:
    cleaned = raw_dsn.strip().strip('"').strip("'")
    parsed = urllib.parse.urlsplit(cleaned)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ValueError(f"Expected postgres/postgresql URL scheme, got {parsed.scheme!r}")
    if not parsed.hostname or not parsed.path.strip("/"):
        raise ValueError("Neon connection URL must include hostname and database name")

    host = parsed.hostname
    port = parsed.port or 5432
    database = parsed.path.lstrip("/")
    user = urllib.parse.unquote(parsed.username or "")
    password = urllib.parse.unquote(parsed.password or "")
    if not user or not password:
        raise ValueError("Neon connection URL must include username and password")

    qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
    sslmode = (qs.get("sslmode") or ["require"])[0]
    if sslmode == "disable":
        sslmode = "require"

    safe_query = urllib.parse.urlencode({"sslmode": sslmode})
    psycopg_dsn = (
        f"postgresql://{urllib.parse.quote(user, safe='')}:{urllib.parse.quote(password, safe='')}"
        f"@{host}:{port}/{database}?{safe_query}"
    )
    jdbc_url = (
        f"jdbc:postgresql://{host}:{port}/{database}"
        f"?sslmode={sslmode}&reWriteBatchedInserts=true&prepareThreshold=0"
    )
    return PgTargetConfig(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        sslmode=sslmode,
        psycopg_dsn=psycopg_dsn,
        jdbc_url=jdbc_url,
    )


def redact_pg_target(cfg: PgTargetConfig) -> str:
    return f"postgresql://{cfg.user}:***@{cfg.host}:{cfg.port}/{cfg.database}?sslmode={cfg.sslmode}"


def databricks_type_to_pg(type_text: str) -> str:
    normalized = type_text.strip().lower()
    m = _DECIMAL_RE.match(normalized)
    if m:
        return f"NUMERIC({int(m.group(1))},{int(m.group(2))})"
    mapping = {
        "string": "TEXT",
        "varchar": "TEXT",
        "char": "TEXT",
        "bigint": "BIGINT",
        "long": "BIGINT",
        "int": "INTEGER",
        "integer": "INTEGER",
        "smallint": "SMALLINT",
        "short": "SMALLINT",
        "tinyint": "SMALLINT",
        "byte": "SMALLINT",
        "double": "DOUBLE PRECISION",
        "float": "REAL",
        "boolean": "BOOLEAN",
        "date": "DATE",
        "timestamp": "TIMESTAMPTZ",
        "timestamp_ntz": "TIMESTAMP",
    }
    return mapping.get(normalized, "TEXT")


def build_create_table_sql(schema: str, table: str, columns: Sequence[tuple[str, str]]) -> str:
    s = validate_identifier(schema)
    t = validate_identifier(table)
    col_defs = [f'"{validate_identifier(col)}" {databricks_type_to_pg(typ)}' for col, typ in columns]
    return f'CREATE TABLE "{s}"."{t}" (\n  ' + ",\n  ".join(col_defs) + "\n)"


def build_mart_sales_daily_view_sql(schema: str) -> str:
    s = validate_identifier(schema)
    cols = ",\n  ".join(f'"{c}"' for c in MART_SALES_DAILY_COLUMNS)
    return (
        f'CREATE OR REPLACE VIEW "{s}"."mart_sales_daily" AS\n'
        f"SELECT\n  {cols}\n"
        f'FROM "{s}"."mart_sales_weather_daily"'
    )


def build_bi_views_sql(schema: str, *, available_tables: Sequence[str]) -> list[tuple[str, str]]:
    """Build zero-storage BI helper views for AWS Quick over synced Gold MD-01 tables."""
    s = validate_identifier(schema)
    avail = set(available_tables)
    views: list[tuple[str, str]] = []

    if "mart_sales_weather_daily" in avail:
        views.append(
            (
                "bi_sales_weather_enriched",
                f"""
                CREATE OR REPLACE VIEW "{s}"."bi_sales_weather_enriched" AS
                SELECT
                  m.*,
                  CASE
                    WHEN m.source = 'IRPD_PUBLISHER_REPORTED_POS' THEN 'IRPD_ID_OBSERVED'
                    WHEN m.source = 'SIMULATED_ONYX_DAILY_FACT_TO_POS' THEN 'ONYX_EU_SYNTHETIC'
                    WHEN m.source = 'SIMULATED_PHARMA_SALES_ATC_SCALE10' THEN 'SERBIA_RS_SYNTHETIC'
                    ELSE m.source
                  END AS dataset_track,
                  CASE
                    WHEN m.sales_uom_code LIKE 'IRPD_UOM_%'
                      THEN SPLIT_PART(SUBSTRING(m.sales_uom_code FROM 10), '_', 1)
                    ELSE m.sales_uom_code
                  END AS clean_uom,
                  DATE_TRUNC('month', m.local_date)::date AS year_month,
                  EXTRACT(YEAR FROM m.local_date)::int AS year_num,
                  EXTRACT(MONTH FROM m.local_date)::int AS month_num,
                  EXTRACT(ISODOW FROM m.local_date)::int AS day_of_week_num,
                  TO_CHAR(m.local_date, 'Dy') AS day_of_week,
                  (EXTRACT(ISODOW FROM m.local_date) IN (6, 7)) AS is_weekend,
                  CASE
                    WHEN m.temp_mean IS NULL THEN 'Unknown'
                    WHEN m.temp_mean < 10 THEN '1. Cold (<10C)'
                    WHEN m.temp_mean < 20 THEN '2. Cool (10-20C)'
                    WHEN m.temp_mean < 27 THEN '3. Mild (20-27C)'
                    WHEN m.temp_mean < 30 THEN '4. Warm (27-30C)'
                    ELSE '5. Hot (>=30C)'
                  END AS temp_band,
                  CASE
                    WHEN m.precip_sum IS NULL THEN 'Unknown'
                    WHEN m.precip_sum = 0 THEN '1. Dry (0 mm)'
                    WHEN m.precip_sum <= 5 THEN '2. Light (0-5 mm)'
                    WHEN m.precip_sum <= 20 THEN '3. Moderate (5-20 mm)'
                    ELSE '4. Heavy (>20 mm)'
                  END AS rain_regime,
                  CASE
                    WHEN m.humidity_mean IS NULL THEN 'Unknown'
                    WHEN m.humidity_mean < 60 THEN '1. Low (<60%)'
                    WHEN m.humidity_mean <= 80 THEN '2. Normal (60-80%)'
                    ELSE '3. High (>80%)'
                  END AS humidity_band,
                  (m.line_amount / NULLIF(m.sold_qty, 0))::double precision AS avg_unit_price,
                  (m.margin_amount / NULLIF(m.line_amount, 0))::double precision AS margin_pct,
                  (m.promo_sold_qty / NULLIF(m.sold_qty, 0))::double precision AS promo_share_pct
                FROM "{s}"."mart_sales_weather_daily" m
                """.strip(),
            )
        )
        views.append(
            (
                "bi_weather_impact_summary",
                f"""
                CREATE OR REPLACE VIEW "{s}"."bi_weather_impact_summary" AS
                SELECT
                  dataset_track,
                  country_code,
                  currency_code,
                  clean_uom,
                  provenance_class,
                  rain_regime,
                  temp_band,
                  humidity_band,
                  is_weekend,
                  COUNT(*) AS row_count,
                  COUNT(DISTINCT local_date) AS active_days,
                  COUNT(DISTINCT store_id) AS distinct_stores,
                  COUNT(DISTINCT product_id) AS distinct_products,
                  SUM(sold_qty)::double precision AS total_sold_qty,
                  AVG(sold_qty)::double precision AS avg_daily_sku_qty,
                  SUM(line_amount)::double precision AS total_line_amount,
                  SUM(margin_amount)::double precision AS total_margin_amount,
                  AVG(temp_mean) AS avg_temp_mean,
                  AVG(precip_sum) AS avg_precip_sum,
                  AVG(humidity_mean) AS avg_humidity_mean
                FROM "{s}"."bi_sales_weather_enriched"
                GROUP BY
                  dataset_track,
                  country_code,
                  currency_code,
                  clean_uom,
                  provenance_class,
                  rain_regime,
                  temp_band,
                  humidity_band,
                  is_weekend
                """.strip(),
            )
        )

    if "mart_sales_observation_period" in avail:
        views.append(
            (
                "bi_atc_category_monthly",
                f"""
                CREATE OR REPLACE VIEW "{s}"."bi_atc_category_monthly" AS
                SELECT
                  DATE_TRUNC('month', period_start)::date AS year_month,
                  EXTRACT(YEAR FROM period_start)::int AS year_num,
                  EXTRACT(MONTH FROM period_start)::int AS month_num,
                  country_code,
                  category_code,
                  category_name,
                  provenance_class,
                  source,
                  SUM(observation_count) AS observation_count,
                  SUM(observed_qty)::double precision AS total_observed_qty,
                  AVG(observed_qty)::double precision AS avg_daily_qty
                FROM "{s}"."mart_sales_observation_period"
                WHERE subject_kind = 'CATEGORY'
                GROUP BY
                  DATE_TRUNC('month', period_start)::date,
                  EXTRACT(YEAR FROM period_start)::int,
                  EXTRACT(MONTH FROM period_start)::int,
                  country_code,
                  category_code,
                  category_name,
                  provenance_class,
                  source
                """.strip(),
            )
        )

    return views


def should_skip_sync(
    *,
    active_release_id: str | None,
    last_release_id: str | None,
    last_status: str | None,
    force: bool,
) -> bool:
    if force or not active_release_id or not last_release_id:
        return False
    return last_status == "SUCCEEDED" and active_release_id == last_release_id


def strip_csv_header_if_chunk_zero(raw_csv: str, chunk_index: int, expected_columns: Sequence[str]) -> str:
    if chunk_index > 0:
        return raw_csv
    newline_pos = raw_csv.find("\n")
    if newline_pos == -1:
        header_line = raw_csv.rstrip("\r")
        rest = ""
    else:
        header_line = raw_csv[:newline_pos].rstrip("\r")
        rest = raw_csv[newline_pos + 1 :]
    actual_cols = [c.strip().strip('"') for c in header_line.split(",")] if header_line else []
    if list(expected_columns) != actual_cols:
        raise RuntimeError(
            f"CSV header mismatch from Databricks: expected={list(expected_columns)!r}, actual={actual_cols!r}"
        )
    return rest


def _ensure_state_table(conn: Any, schema: str) -> None:
    s = validate_identifier(schema)
    with conn.cursor() as cur:
        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{s}"')
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{s}"."sync_release_state" (
              product_domain TEXT PRIMARY KEY,
              release_id TEXT NOT NULL,
              status TEXT NOT NULL,
              sync_mode TEXT NOT NULL,
              synced_at_utc TIMESTAMPTZ NOT NULL,
              table_counts_json TEXT NOT NULL
            )
            """
        )
    conn.commit()


def _get_last_sync_state(conn: Any, schema: str) -> tuple[str | None, str | None]:
    s = validate_identifier(schema)
    with conn.cursor() as cur:
        cur.execute(
            f'SELECT release_id, status FROM "{s}"."sync_release_state" WHERE product_domain = %s',
            (MD01_DOMAIN,),
        )
        row = cur.fetchone()
    if not row:
        return None, None
    return row[0], row[1]


def _atomic_swap_and_record(
    conn: Any,
    *,
    schema: str,
    tables: Sequence[str],
    release_id: str,
    sync_mode: str,
    table_counts: dict[str, int],
    create_daily_view: bool,
) -> None:
    s = validate_identifier(schema)
    now_utc = datetime.now(timezone.utc)
    counts_json = json.dumps(table_counts, ensure_ascii=False)
    with conn.transaction():
        with conn.cursor() as cur:
            # Drop the view first if we are swapping mart_sales_weather_daily (dependent) or creating mart_sales_daily physically.
            cur.execute(
                """
                SELECT table_type
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = 'mart_sales_daily'
                """,
                (s,),
            )
            row = cur.fetchone()
            if row and row[0] == "VIEW":
                cur.execute(f'DROP VIEW IF EXISTS "{s}"."mart_sales_daily"')

            for tbl in tables:
                t = validate_identifier(tbl)
                stg = validate_identifier(f"_stg_{tbl}")
                cur.execute(f'DROP TABLE IF EXISTS "{s}"."{t}" CASCADE')
                cur.execute(f'ALTER TABLE "{s}"."{stg}" RENAME TO "{t}"')

            if create_daily_view:
                cur.execute(build_mart_sales_daily_view_sql(s))

            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                """,
                (s,),
            )
            base_tables = [r[0] for r in cur.fetchall()]
            for _view_name, view_sql in build_bi_views_sql(s, available_tables=base_tables):
                cur.execute(view_sql)

            cur.execute(
                f"""
                INSERT INTO "{s}"."sync_release_state" (
                  product_domain, release_id, status, sync_mode, synced_at_utc, table_counts_json
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (product_domain) DO UPDATE SET
                  release_id = EXCLUDED.release_id,
                  status = EXCLUDED.status,
                  sync_mode = EXCLUDED.sync_mode,
                  synced_at_utc = EXCLUDED.synced_at_utc,
                  table_counts_json = EXCLUDED.table_counts_json
                """,
                (MD01_DOMAIN, release_id, "SUCCEEDED", sync_mode, now_utc, counts_json),
            )


def _execute_databricks_sql(
    w: Any,
    *,
    warehouse_id: str,
    statement: str,
    fmt: Any = None,
    disposition: Any = None,
    poll_timeout_s: int = 600,
) -> Any:
    kwargs: dict[str, Any] = {
        "warehouse_id": warehouse_id,
        "statement": statement,
        "wait_timeout": "50s",
    }
    if fmt is not None:
        kwargs["format"] = fmt
    if disposition is not None:
        kwargs["disposition"] = disposition

    res = w.statement_execution.execute_statement(**kwargs)
    deadline = time.monotonic() + poll_timeout_s
    while str(res.status.state).endswith(("PENDING", "RUNNING")):
        if time.monotonic() > deadline:
            raise TimeoutError(f"Databricks SQL statement timed out after {poll_timeout_s}s: {res.statement_id}")
        time.sleep(2.0)
        res = w.statement_execution.get_statement(res.statement_id)

    if not str(res.status.state).endswith("SUCCEEDED"):
        raise RuntimeError(f"Databricks SQL failed ({res.status.state}): {res.status.error}")
    return res


def sync_local(
    *,
    catalog: str,
    source_schema: str,
    target_schema: str,
    tables: Sequence[str],
    warehouse_id: str,
    neon_dsn: str,
    force: bool = False,
    dry_run: bool = False,
    stop_warehouse: bool = True,
) -> dict[str, Any]:
    import psycopg
    import requests
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import Disposition, Format

    host = os.environ["DATABRICKS_HOST"].strip()
    token = os.environ["DATABRICKS_TOKEN"].strip()
    pg_cfg = parse_pg_dsn(neon_dsn)
    w = WorkspaceClient(host=host, token=token)

    try:
        rel_sql = (
            f"SELECT release_id FROM {validate_identifier(catalog)}.ops.product_release "
            f"WHERE product_domain = '{MD01_DOMAIN}' AND status = 'ACTIVE' "
            f"ORDER BY published_at_utc DESC LIMIT 1"
        )
        rel_res = _execute_databricks_sql(w, warehouse_id=warehouse_id, statement=rel_sql)
        active_release_id = (
            str(rel_res.result.data_array[0][0])
            if rel_res.result and rel_res.result.data_array
            else f"unreleased-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        )

        with psycopg.connect(pg_cfg.psycopg_dsn, prepare_threshold=None) as conn:
            _ensure_state_table(conn, target_schema)
            last_rel, last_status = _get_last_sync_state(conn, target_schema)

            if should_skip_sync(
                active_release_id=active_release_id,
                last_release_id=last_rel,
                last_status=last_status,
                force=force,
            ):
                return {
                    "status": "SKIPPED_UP_TO_DATE",
                    "mode": "local",
                    "release_id": active_release_id,
                    "target": redact_pg_target(pg_cfg),
                    "target_schema": target_schema,
                }

            if dry_run:
                return {
                    "status": "DRY_RUN_WOULD_SYNC",
                    "mode": "local",
                    "active_release_id": active_release_id,
                    "last_synced_release_id": last_rel,
                    "tables": list(tables),
                    "target": redact_pg_target(pg_cfg),
                    "target_schema": target_schema,
                }

            table_counts: dict[str, int] = {}
            s_ident = validate_identifier(target_schema)

            for tbl in tables:
                t_ident = validate_identifier(tbl)
                fq_tbl = f"{validate_identifier(catalog)}.{validate_identifier(source_schema)}.{t_ident}"
                uc_tbl = w.tables.get(fq_tbl)
                columns = [(c.name, c.type_text or "string") for c in (uc_tbl.columns or [])]
                if not columns:
                    raise RuntimeError(f"No columns found in Unity Catalog for {fq_tbl}")

                stg_ident = validate_identifier(f"_stg_{tbl}")
                with conn.cursor() as cur:
                    cur.execute(f'DROP TABLE IF EXISTS "{s_ident}"."{stg_ident}"')
                    cur.execute(build_create_table_sql(s_ident, stg_ident, columns))
                conn.commit()

                col_names = [c[0] for c in columns]
                select_cols = ", ".join(f"`{c}`" for c in col_names)
                export_res = _execute_databricks_sql(
                    w,
                    warehouse_id=warehouse_id,
                    statement=f"SELECT {select_cols} FROM {fq_tbl}",
                    fmt=Format.CSV,
                    disposition=Disposition.EXTERNAL_LINKS,
                    poll_timeout_s=900,
                )
                expected_rows = int(export_res.manifest.total_row_count or 0)
                total_chunks = int(export_res.manifest.total_chunk_count or 0)
                cols_sql = ", ".join(f'"{validate_identifier(c)}"' for c in col_names)

                if expected_rows > 0 and total_chunks > 0:
                    copy_sql = (
                        f'COPY "{s_ident}"."{stg_ident}" ({cols_sql}) '
                        f"FROM STDIN WITH (FORMAT csv, HEADER false, NULL 'null')"
                    )
                    with conn.cursor() as cur:
                        with cur.copy(copy_sql) as copy:
                            for chunk_idx in range(total_chunks):
                                chunk_links = w.statement_execution.get_statement_result_chunk_n(
                                    export_res.statement_id, chunk_idx
                                )
                                for link_obj in chunk_links.external_links or []:
                                    resp = requests.get(link_obj.external_link, timeout=120)
                                    resp.raise_for_status()
                                    csv_text = resp.content.decode("utf-8")
                                    payload = strip_csv_header_if_chunk_zero(csv_text, chunk_idx, col_names)
                                    if payload:
                                        copy.write(payload.encode("utf-8"))
                    conn.commit()

                with conn.cursor() as cur:
                    cur.execute(f'SELECT COUNT(*) FROM "{s_ident}"."{stg_ident}"')
                    actual_rows = int(cur.fetchone()[0])
                if actual_rows != expected_rows:
                    raise RuntimeError(
                        f"Row count mismatch while staging {tbl}: expected={expected_rows}, actual={actual_rows}"
                    )
                table_counts[tbl] = actual_rows

            create_daily_view = "mart_sales_weather_daily" in tables and "mart_sales_daily" not in tables
            _atomic_swap_and_record(
                conn,
                schema=target_schema,
                tables=tables,
                release_id=active_release_id,
                sync_mode="local_copy",
                table_counts=table_counts,
                create_daily_view=create_daily_view,
            )

            return {
                "status": "SUCCEEDED",
                "mode": "local",
                "release_id": active_release_id,
                "target": redact_pg_target(pg_cfg),
                "target_schema": target_schema,
                "table_counts": table_counts,
                "mart_sales_daily_view": create_daily_view,
            }
    finally:
        if stop_warehouse and not dry_run:
            try:
                w.warehouses.stop(warehouse_id)
            except Exception:  # noqa: BLE001
                pass


def sync_databricks(
    *,
    spark: Any,
    dbutils_obj: Any,
    catalog: str,
    source_schema: str,
    target_schema: str,
    tables: Sequence[str],
    secret_scope: str = DEFAULT_SECRET_SCOPE,
    secret_key: str = DEFAULT_SECRET_KEY,
    force: bool = False,
    dry_run: bool = False,
    num_partitions: int = 4,
) -> dict[str, Any]:
    import psycopg

    if dbutils_obj is None:
        raise RuntimeError("dbutils is required in databricks mode")
    raw_dsn = dbutils_obj.secrets.get(secret_scope, secret_key)
    pg_cfg = parse_pg_dsn(raw_dsn)

    rel_rows = spark.sql(
        f"""
        SELECT release_id
        FROM {validate_identifier(catalog)}.ops.product_release
        WHERE product_domain = '{MD01_DOMAIN}' AND status = 'ACTIVE'
        ORDER BY published_at_utc DESC
        LIMIT 1
        """
    ).collect()
    active_release_id = (
        str(rel_rows[0]["release_id"])
        if rel_rows
        else f"unreleased-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )

    with psycopg.connect(pg_cfg.psycopg_dsn, prepare_threshold=None) as conn:
        _ensure_state_table(conn, target_schema)
        last_rel, last_status = _get_last_sync_state(conn, target_schema)

        if should_skip_sync(
            active_release_id=active_release_id,
            last_release_id=last_rel,
            last_status=last_status,
            force=force,
        ):
            return {
                "status": "SKIPPED_UP_TO_DATE",
                "mode": "databricks",
                "release_id": active_release_id,
                "target": redact_pg_target(pg_cfg),
                "target_schema": target_schema,
            }

        if dry_run:
            return {
                "status": "DRY_RUN_WOULD_SYNC",
                "mode": "databricks",
                "active_release_id": active_release_id,
                "last_synced_release_id": last_rel,
                "tables": list(tables),
                "target": redact_pg_target(pg_cfg),
                "target_schema": target_schema,
            }

        table_counts: dict[str, int] = {}
        s_ident = validate_identifier(target_schema)

        for tbl in tables:
            t_ident = validate_identifier(tbl)
            fq_tbl = f"{validate_identifier(catalog)}.{validate_identifier(source_schema)}.{t_ident}"
            df = spark.table(fq_tbl)
            expected_rows = int(df.count())

            columns = [(name, dtype) for name, dtype in df.dtypes]
            stg_ident = validate_identifier(f"_stg_{tbl}")
            with conn.cursor() as cur:
                cur.execute(f'DROP TABLE IF EXISTS "{s_ident}"."{stg_ident}"')
                cur.execute(build_create_table_sql(s_ident, stg_ident, columns))
            conn.commit()

            if expected_rows > 0:
                try:
                    (
                        df.coalesce(max(1, num_partitions))
                        .write.format("postgresql")
                        .option("host", pg_cfg.host)
                        .option("port", str(pg_cfg.port))
                        .option("database", pg_cfg.database)
                        .option("dbtable", f"{s_ident}.{stg_ident}")
                        .option("user", pg_cfg.user)
                        .option("password", pg_cfg.password)
                        .option("sslmode", pg_cfg.sslmode)
                        .option("prepareThreshold", "0")
                        .option("batchsize", "10000")
                        .option("isolationLevel", "READ_COMMITTED")
                        .mode("append")
                        .save()
                    )
                except Exception:
                    col_names = [name for name, _ in columns]
                    cols_sql = ", ".join(f'"{validate_identifier(c)}"' for c in col_names)
                    with conn.cursor() as cur:
                        cur.execute(f'TRUNCATE TABLE "{s_ident}"."{stg_ident}"')
                        with cur.copy(f'COPY "{s_ident}"."{stg_ident}" ({cols_sql}) FROM STDIN') as copy:
                            for row in df.toLocalIterator():
                                copy.write_row(tuple(row[c] for c in col_names))
                    conn.commit()

            with conn.cursor() as cur:
                cur.execute(f'SELECT COUNT(*) FROM "{s_ident}"."{stg_ident}"')
                actual_rows = int(cur.fetchone()[0])
            if actual_rows != expected_rows:
                raise RuntimeError(
                    f"Row count mismatch while staging {tbl}: expected={expected_rows}, actual={actual_rows}"
                )
            table_counts[tbl] = actual_rows

        create_daily_view = "mart_sales_weather_daily" in tables and "mart_sales_daily" not in tables
        _atomic_swap_and_record(
            conn,
            schema=target_schema,
            tables=tables,
            release_id=active_release_id,
            sync_mode="databricks_jdbc",
            table_counts=table_counts,
            create_daily_view=create_daily_view,
        )

        return {
            "status": "SUCCEEDED",
            "mode": "databricks",
            "release_id": active_release_id,
            "target": redact_pg_target(pg_cfg),
            "target_schema": target_schema,
            "table_counts": table_counts,
            "mart_sales_daily_view": create_daily_view,
        }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("auto", "local", "databricks"), default="auto")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG)
    parser.add_argument("--source-schema", default=DEFAULT_SOURCE_SCHEMA)
    parser.add_argument(
        "--target-schema",
        default=(os.environ.get("QUICK_NEON_SCHEMA") or "").strip() or DEFAULT_TARGET_SCHEMA,
    )
    parser.add_argument("--tables", default="default", help="default | all | comma-separated table names")
    parser.add_argument("--warehouse-id", default=DEFAULT_WAREHOUSE_ID)
    parser.add_argument("--secret-scope", default=DEFAULT_SECRET_SCOPE)
    parser.add_argument("--secret-key", default=DEFAULT_SECRET_KEY)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-warehouse-running", action="store_true")
    return parser.parse_args(argv)


def _read_runtime_params(argv: Sequence[str] | None = None) -> argparse.Namespace:
    dbutils_obj = globals().get("dbutils")
    if argv is None and dbutils_obj is not None and hasattr(dbutils_obj, "widgets"):
        defaults = {
            "mode": "databricks",
            "catalog": DEFAULT_CATALOG,
            "source_schema": DEFAULT_SOURCE_SCHEMA,
            "target_schema": DEFAULT_TARGET_SCHEMA,
            "tables": "default",
            "secret_scope": DEFAULT_SECRET_SCOPE,
            "secret_key": DEFAULT_SECRET_KEY,
            "force": "false",
            "dry_run": "false",
        }
        resolved: dict[str, Any] = {}
        for k, dflt in defaults.items():
            try:
                val = dbutils_obj.widgets.get(k)
                resolved[k] = val if val else dflt
            except Exception:  # noqa: BLE001
                resolved[k] = dflt
        return argparse.Namespace(
            mode=resolved["mode"],
            catalog=resolved["catalog"],
            source_schema=resolved["source_schema"],
            target_schema=resolved["target_schema"],
            tables=resolved["tables"],
            warehouse_id=DEFAULT_WAREHOUSE_ID,
            secret_scope=resolved["secret_scope"],
            secret_key=resolved["secret_key"],
            force=str(resolved["force"]).lower() == "true",
            dry_run=str(resolved["dry_run"]).lower() == "true",
            keep_warehouse_running=True,
        )
    return parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv

        repo_root = Path(__file__).resolve().parents[2]
        load_dotenv(repo_root / ".env")
    except Exception:  # noqa: BLE001
        pass

    args = _read_runtime_params(argv)
    tables = resolve_tables(args.tables)
    dbutils_obj = globals().get("dbutils")
    mode = args.mode
    if mode == "auto":
        mode = "databricks" if dbutils_obj is not None else "local"

    if mode == "databricks":
        from pyspark.sql import SparkSession

        spark = globals().get("spark") or SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        summary = sync_databricks(
            spark=spark,
            dbutils_obj=dbutils_obj,
            catalog=args.catalog,
            source_schema=args.source_schema,
            target_schema=args.target_schema,
            tables=tables,
            secret_scope=args.secret_scope,
            secret_key=args.secret_key,
            force=args.force,
            dry_run=args.dry_run,
        )
    else:
        neon_dsn = os.environ.get("QUICK_NEON_DATABASE_URL", "").strip()
        if not neon_dsn:
            raise RuntimeError(
                "Missing QUICK_NEON_DATABASE_URL in environment / .env. "
                "See src/sync_quick/README.md for setup instructions."
            )
        summary = sync_local(
            catalog=args.catalog,
            source_schema=args.source_schema,
            target_schema=args.target_schema,
            tables=tables,
            warehouse_id=args.warehouse_id,
            neon_dsn=neon_dsn,
            force=args.force,
            dry_run=args.dry_run,
            stop_warehouse=not args.keep_warehouse_running,
        )

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    _exit_code = main()
    if _exit_code != 0:
        raise SystemExit(_exit_code)
