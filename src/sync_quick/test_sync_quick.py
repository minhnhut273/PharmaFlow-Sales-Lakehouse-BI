"""Offline unit tests for the out-of-scope src/sync_quick auxiliary bridge."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from sync_gold_to_neon import (  # noqa: E402
    DEFAULT_PHYSICAL_TABLES,
    DEFAULT_TARGET_SCHEMA,
    build_bi_views_sql,
    build_create_table_sql,
    build_mart_sales_daily_view_sql,
    databricks_type_to_pg,
    parse_args,
    parse_pg_dsn,
    redact_pg_target,
    resolve_tables,
    should_skip_sync,
    strip_csv_header_if_chunk_zero,
)


def test_parse_and_redact_pg_dsn() -> None:
    cfg = parse_pg_dsn('"postgresql://alice:s3cr3t%21@ep-demo.ap-southeast-1.aws.neon.tech/quick_bi?sslmode=require"')
    assert cfg.host == "ep-demo.ap-southeast-1.aws.neon.tech"
    assert cfg.port == 5432
    assert cfg.database == "quick_bi"
    assert cfg.user == "alice"
    assert cfg.password == "s3cr3t!"
    assert cfg.sslmode == "require"
    assert "reWriteBatchedInserts=true" in cfg.jdbc_url
    redacted = redact_pg_target(cfg)
    assert "s3cr3t" not in redacted
    assert "***" in redacted


def test_type_mapping_and_ddl_generation() -> None:
    assert databricks_type_to_pg("bigint") == "BIGINT"
    assert databricks_type_to_pg("decimal(28,6)") == "NUMERIC(28,6)"
    assert databricks_type_to_pg("timestamp") == "TIMESTAMPTZ"
    assert databricks_type_to_pg("double") == "DOUBLE PRECISION"

    ddl = build_create_table_sql(
        "quick_gold_md01",
        "_stg_kpi_sales_trend",
        [("store_id", "bigint"), ("sold_qty", "decimal(38,6)"), ("period_start", "date")],
    )
    assert 'CREATE TABLE "quick_gold_md01"."_stg_kpi_sales_trend"' in ddl
    assert '"sold_qty" NUMERIC(38,6)' in ddl

    view_sql = build_mart_sales_daily_view_sql("quick_gold_md01")
    assert 'CREATE OR REPLACE VIEW "quick_gold_md01"."mart_sales_daily"' in view_sql
    assert 'FROM "quick_gold_md01"."mart_sales_weather_daily"' in view_sql


def test_resolve_tables_and_skip_logic() -> None:
    assert resolve_tables("default") == DEFAULT_PHYSICAL_TABLES
    assert resolve_tables("kpi_sales_trend, mart_sales_observation_period") == (
        "kpi_sales_trend",
        "mart_sales_observation_period",
    )
    with pytest.raises(ValueError, match="Unsupported"):
        resolve_tables("nonexistent_table")

    assert should_skip_sync(active_release_id="r1", last_release_id="r1", last_status="SUCCEEDED", force=False)
    assert not should_skip_sync(active_release_id="r2", last_release_id="r1", last_status="SUCCEEDED", force=False)
    assert not should_skip_sync(active_release_id="r1", last_release_id="r1", last_status="SUCCEEDED", force=True)
    assert not should_skip_sync(active_release_id="r1", last_release_id="r1", last_status="FAILED", force=False)


def test_strip_csv_header_chunk_zero_and_later_chunks() -> None:
    cols = ["store_id", "product_id", "sold_qty"]
    chunk0 = "store_id,product_id,sold_qty\n5389,101,5.0\n5389,null,2.0\n"
    assert strip_csv_header_if_chunk_zero(chunk0, 0, cols) == "5389,101,5.0\n5389,null,2.0\n"

    chunk1 = "5389,102,3.0\n"
    assert strip_csv_header_if_chunk_zero(chunk1, 1, cols) == chunk1

    with pytest.raises(RuntimeError, match="CSV header mismatch"):
        strip_csv_header_if_chunk_zero("wrong_col\n1\n", 0, cols)


def test_empty_env_schema_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "")
    ns = parse_args([])
    assert ns.target_schema == DEFAULT_TARGET_SCHEMA
    assert "prepareThreshold=0" in parse_pg_dsn("postgresql://u:p@h.neon.tech/db").jdbc_url


def test_build_bi_views_sql() -> None:
    views = build_bi_views_sql(
        "quick_gold_md01",
        available_tables=["mart_sales_weather_daily", "mart_sales_observation_period"],
    )
    names = [name for name, _sql in views]
    assert names == [
        "bi_sales_weather_enriched",
        "bi_weather_impact_summary",
        "bi_atc_category_monthly",
    ]
    assert 'CREATE OR REPLACE VIEW "quick_gold_md01"."bi_sales_weather_enriched"' in views[0][1]

