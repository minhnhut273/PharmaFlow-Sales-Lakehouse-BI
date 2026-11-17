# Databricks notebook source
"""Atomic release validation and publication for Gold MD-01 Sales & Demand data products.

Reconciles Silver ``fact_sales_line`` and ``fact_sales_observation`` totals against Gold
``mart_sales_daily``, ``mart_sales_observation_period``, and ``mart_sales_weather_daily``
grouped by UOM, currency, and provenance class before stamping ``<catalog>.ops.product_release``.
"""

from __future__ import annotations

import argparse
import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

MD01_DOMAIN = "MD01_SALES_AND_DEMAND"


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def reconcile_grouped_aggregates(
    silver_rows: Sequence[Mapping[str, Any]],
    gold_rows: Sequence[Mapping[str, Any]],
    *,
    key_fields: tuple[str, ...],
    qty_field: str = "total_qty",
    amount_field: str = "total_amount",
    count_field: str = "row_count",
    qty_tolerance: Decimal = Decimal("0.0001"),
    amount_tolerance: Decimal = Decimal("0.01"),
) -> list[dict[str, Any]]:
    """Compare grouped Silver vs Gold aggregates and return any discrepancies."""

    def _index(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[Any, ...], Mapping[str, Any]]:
        indexed: dict[tuple[Any, ...], Mapping[str, Any]] = {}
        for r in rows:
            key = tuple(r.get(k) for k in key_fields)
            indexed[key] = r
        return indexed

    s_map = _index(silver_rows)
    g_map = _index(gold_rows)
    mismatches: list[dict[str, Any]] = []

    for key in sorted(set(s_map) | set(g_map), key=lambda k: tuple("" if x is None else str(x) for x in k)):
        key_dict = dict(zip(key_fields, key))
        s_row = s_map.get(key)
        g_row = g_map.get(key)
        if s_row is None or g_row is None:
            mismatches.append(
                {
                    "reason": "missing_group",
                    "key": key_dict,
                    "silver_present": s_row is not None,
                    "gold_present": g_row is not None,
                }
            )
            continue

        s_cnt = int(s_row.get(count_field) or 0)
        g_cnt = int(g_row.get(count_field) or 0)
        s_qty = _to_decimal(s_row.get(qty_field))
        g_qty = _to_decimal(g_row.get(qty_field))
        s_amt = _to_decimal(s_row.get(amount_field))
        g_amt = _to_decimal(g_row.get(amount_field))

        if (
            s_cnt != g_cnt
            or abs(s_qty - g_qty) > qty_tolerance
            or abs(s_amt - g_amt) > amount_tolerance
        ):
            mismatches.append(
                {
                    "reason": "aggregate_mismatch",
                    "key": key_dict,
                    "silver_count": s_cnt,
                    "gold_count": g_cnt,
                    "silver_qty": str(s_qty),
                    "gold_qty": str(g_qty),
                    "silver_amount": str(s_amt),
                    "gold_amount": str(g_amt),
                }
            )
    return mismatches


def _ensure_release_table(spark: Any, catalog: str) -> None:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.ops")
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {catalog}.ops.product_release (
          release_id STRING NOT NULL,
          product_domain STRING NOT NULL,
          status STRING NOT NULL,
          published_at_utc TIMESTAMP NOT NULL,
          silver_sales_line_count BIGINT NOT NULL,
          gold_mart_sales_daily_count BIGINT NOT NULL,
          gold_mart_weather_daily_count BIGINT NOT NULL,
          silver_obs_count BIGINT NOT NULL,
          gold_obs_period_count BIGINT NOT NULL,
          reconciliation_json STRING NOT NULL,
          bronze_watermark_json STRING NOT NULL,
          notes STRING
        ) USING DELTA
        """
    )


def _write_release_row(spark: Any, catalog: str, row: dict[str, Any]) -> None:
    from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

    schema = StructType(
        [
            StructField("release_id", StringType(), False),
            StructField("product_domain", StringType(), False),
            StructField("status", StringType(), False),
            StructField("published_at_utc", TimestampType(), False),
            StructField("silver_sales_line_count", LongType(), False),
            StructField("gold_mart_sales_daily_count", LongType(), False),
            StructField("gold_mart_weather_daily_count", LongType(), False),
            StructField("silver_obs_count", LongType(), False),
            StructField("gold_obs_period_count", LongType(), False),
            StructField("reconciliation_json", StringType(), False),
            StructField("bronze_watermark_json", StringType(), False),
            StructField("notes", StringType(), True),
        ]
    )
    spark.createDataFrame([row], schema=schema).write.mode("append").saveAsTable(f"{catalog}.ops.product_release")


def publish_md01_release(
    *,
    spark: Any,
    catalog: str = "pharmaflow_dev",
    release_id: str | None = None,
) -> dict[str, Any]:
    """Validate Silver -> Gold MD-01 reconciliation and publish an ``ACTIVE`` release record."""
    _ensure_release_table(spark, catalog)
    now_utc = datetime.now(timezone.utc)
    effective_release_id = release_id or f"md01-{now_utc.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"

    silver_line_groups = [
        r.asDict(recursive=True)
        for r in spark.sql(
            f"""
            SELECT
              sales_uom_code,
              currency_code,
              provenance_class,
              COUNT(*) AS row_count,
              SUM(sold_qty) AS total_qty,
              SUM(COALESCE(line_amount, CAST(0 AS DECIMAL(18, 4)))) AS total_amount
            FROM {catalog}.silver_sales.fact_sales_line
            GROUP BY sales_uom_code, currency_code, provenance_class
            """
        ).collect()
    ]
    gold_line_groups = [
        r.asDict(recursive=True)
        for r in spark.sql(
            f"""
            SELECT
              sales_uom_code,
              currency_code,
              provenance_class,
              SUM(line_count) AS row_count,
              SUM(sold_qty) AS total_qty,
              SUM(COALESCE(line_amount, CAST(0 AS DECIMAL(18, 4)))) AS total_amount
            FROM {catalog}.gold_md01_sales.mart_sales_daily
            GROUP BY sales_uom_code, currency_code, provenance_class
            """
        ).collect()
    ]
    line_mismatches = reconcile_grouped_aggregates(
        silver_line_groups,
        gold_line_groups,
        key_fields=("sales_uom_code", "currency_code", "provenance_class"),
    )

    silver_obs_groups = [
        r.asDict(recursive=True)
        for r in spark.sql(
            f"""
            SELECT
              subject_kind,
              quantity_uom_code,
              currency_code,
              provenance_class,
              COUNT(*) AS row_count,
              SUM(observed_qty) AS total_qty,
              SUM(COALESCE(revenue_amount, CAST(0 AS DECIMAL(18, 4)))) AS total_amount
            FROM {catalog}.silver_sales.fact_sales_observation
            GROUP BY subject_kind, quantity_uom_code, currency_code, provenance_class
            """
        ).collect()
    ]
    gold_obs_groups = [
        r.asDict(recursive=True)
        for r in spark.sql(
            f"""
            SELECT
              subject_kind,
              quantity_uom_code,
              currency_code,
              provenance_class,
              SUM(observation_count) AS row_count,
              SUM(observed_qty) AS total_qty,
              SUM(COALESCE(revenue_amount, CAST(0 AS DECIMAL(18, 4)))) AS total_amount
            FROM {catalog}.gold_md01_sales.mart_sales_observation_period
            GROUP BY subject_kind, quantity_uom_code, currency_code, provenance_class
            """
        ).collect()
    ]
    obs_mismatches = reconcile_grouped_aggregates(
        silver_obs_groups,
        gold_obs_groups,
        key_fields=("subject_kind", "quantity_uom_code", "currency_code", "provenance_class"),
    )

    silver_line_cnt = int(spark.table(f"{catalog}.silver_sales.fact_sales_line").count())
    gold_daily_cnt = int(spark.table(f"{catalog}.gold_md01_sales.mart_sales_daily").count())
    gold_weather_daily_cnt = int(spark.table(f"{catalog}.gold_md01_sales.mart_sales_weather_daily").count())
    silver_obs_cnt = int(spark.table(f"{catalog}.silver_sales.fact_sales_observation").count())
    gold_obs_period_cnt = int(spark.table(f"{catalog}.gold_md01_sales.mart_sales_observation_period").count())

    weather_fanout_mismatch = gold_weather_daily_cnt != gold_daily_cnt
    empty_gold = gold_daily_cnt == 0 or gold_obs_period_cnt == 0

    bronze_watermarks: list[dict[str, Any]] = []
    if spark.catalog.tableExists(f"{catalog}.ops.ingest_log"):
        wm_rows = spark.sql(
            f"""
            SELECT source_system, MAX(run_id) AS latest_run_id, MAX(finished_at_utc) AS latest_finished_at_utc
            FROM {catalog}.ops.ingest_log
            WHERE status = 'SUCCEEDED'
            GROUP BY source_system
            ORDER BY source_system
            """
        ).collect()
        for r in wm_rows:
            bronze_watermarks.append(
                {
                    "source_system": r["source_system"],
                    "latest_run_id": r["latest_run_id"],
                    "latest_finished_at_utc": (
                        r["latest_finished_at_utc"].isoformat() if r["latest_finished_at_utc"] else None
                    ),
                }
            )

    reconciliation_report = {
        "line_mismatches": line_mismatches,
        "observation_mismatches": obs_mismatches,
        "weather_join_row_count_match": not weather_fanout_mismatch,
        "non_empty_gold_marts": not empty_gold,
        "silver_line_groups": [
            {k: (str(v) if isinstance(v, Decimal) else v) for k, v in g.items()} for g in silver_line_groups
        ],
    }
    report_json = json.dumps(reconciliation_report, ensure_ascii=False)
    watermark_json = json.dumps(bronze_watermarks, ensure_ascii=False)

    has_failure = bool(line_mismatches or obs_mismatches or weather_fanout_mismatch or empty_gold)
    if has_failure:
        _write_release_row(
            spark,
            catalog,
            {
                "release_id": effective_release_id,
                "product_domain": MD01_DOMAIN,
                "status": "FAILED",
                "published_at_utc": now_utc,
                "silver_sales_line_count": silver_line_cnt,
                "gold_mart_sales_daily_count": gold_daily_cnt,
                "gold_mart_weather_daily_count": gold_weather_daily_cnt,
                "silver_obs_count": silver_obs_cnt,
                "gold_obs_period_count": gold_obs_period_cnt,
                "reconciliation_json": report_json,
                "bronze_watermark_json": watermark_json,
                "notes": "Reconciliation check failed before publication.",
            },
        )
        raise RuntimeError(f"MD-01 release reconciliation failed ({effective_release_id}): {report_json}")

    spark.sql(
        f"""
        UPDATE {catalog}.ops.product_release
        SET status = 'SUPERSEDED'
        WHERE product_domain = '{MD01_DOMAIN}' AND status = 'ACTIVE'
        """
    )
    _write_release_row(
        spark,
        catalog,
        {
            "release_id": effective_release_id,
            "product_domain": MD01_DOMAIN,
            "status": "ACTIVE",
            "published_at_utc": now_utc,
            "silver_sales_line_count": silver_line_cnt,
            "gold_mart_sales_daily_count": gold_daily_cnt,
            "gold_mart_weather_daily_count": gold_weather_daily_cnt,
            "silver_obs_count": silver_obs_cnt,
            "gold_obs_period_count": gold_obs_period_cnt,
            "reconciliation_json": report_json,
            "bronze_watermark_json": watermark_json,
            "notes": "All Silver-to-Gold reconciliation checks passed.",
        },
    )

    return {
        "release_id": effective_release_id,
        "product_domain": MD01_DOMAIN,
        "status": "ACTIVE",
        "silver_sales_line_count": silver_line_cnt,
        "gold_mart_sales_daily_count": gold_daily_cnt,
        "gold_mart_weather_daily_count": gold_weather_daily_cnt,
        "silver_obs_count": silver_obs_cnt,
        "gold_obs_period_count": gold_obs_period_cnt,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default="pharmaflow_dev")
    parser.add_argument("--release-id", default=None)
    return parser.parse_args(argv)


def _read_runtime_params(argv: Sequence[str] | None = None) -> argparse.Namespace:
    dbutils_obj = globals().get("dbutils")
    if argv is None and dbutils_obj is not None and hasattr(dbutils_obj, "widgets"):
        defaults = {"catalog": "pharmaflow_dev", "release_id": ""}
        resolved: dict[str, Any] = {}
        for k, dflt in defaults.items():
            try:
                val = dbutils_obj.widgets.get(k)
                resolved[k] = val if val else dflt
            except Exception:  # noqa: BLE001
                resolved[k] = dflt
        resolved["release_id"] = resolved["release_id"] or None
        return argparse.Namespace(**resolved)
    return parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    from pyspark.sql import SparkSession

    args = _read_runtime_params(argv)
    spark = globals().get("spark") or SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    summary = publish_md01_release(spark=spark, catalog=args.catalog, release_id=args.release_id)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    main()
