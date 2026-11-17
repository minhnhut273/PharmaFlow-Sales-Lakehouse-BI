# Databricks notebook source
"""Bronze snapshot ingestion for populated Neon PostgreSQL source tables.

Supports direct Spark JDBC ingestion (default when Databricks Serverless can reach Neon)
and Managed Volume JSONL.GZ fallback ingestion via ``--source-mode volume``.
Writes append-only snapshots into ``<catalog>.bronze_pg.<schema>__<table>``, logs per-table
reconciliation into ``<catalog>.ops.ingest_log``, and atomically updates
``<catalog>.bronze_pg.latest_<schema>__<table>`` views only after all tables pass count checks.
"""

from __future__ import annotations

import argparse
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SourceTableSpec:
    schema_name: str
    table_name: str
    partition_col: str | None = None
    num_partitions: int = 1

    @property
    def fq_source(self) -> str:
        return f"{self.schema_name}.{self.table_name}"

    @property
    def bronze_table(self) -> str:
        return f"{self.schema_name}__{self.table_name}"

    @property
    def latest_view(self) -> str:
        return f"latest_{self.bronze_table}"


POPULATED_SOURCE_TABLES: tuple[SourceTableSpec, ...] = (
    SourceTableSpec("catalog", "manufacturer"),
    SourceTableSpec("catalog", "unit_of_measure"),
    SourceTableSpec("catalog", "product_category"),
    SourceTableSpec("catalog", "product"),
    SourceTableSpec("catalog", "product_category_assignment"),
    SourceTableSpec("catalog", "product_source_reference"),
    SourceTableSpec("catalog", "product_packaging"),
    SourceTableSpec("org", "store"),
    SourceTableSpec("org", "warehouse"),
    SourceTableSpec("pos", "sales_order", partition_col="sales_order_id", num_partitions=8),
    SourceTableSpec("pos", "sales_order_line", partition_col="sales_order_line_id", num_partitions=12),
    SourceTableSpec("pos", "sales_observation", partition_col="sales_observation_id", num_partitions=4),
)


def resolve_tables(tables_csv: str | None) -> tuple[SourceTableSpec, ...]:
    if not tables_csv or tables_csv.strip().lower() in ("", "all"):
        return POPULATED_SOURCE_TABLES
    by_name = {t.fq_source: t for t in POPULATED_SOURCE_TABLES}
    selected: list[SourceTableSpec] = []
    for raw in tables_csv.split(","):
        name = raw.strip()
        if not name:
            continue
        if name not in by_name:
            raise ValueError(f"Unsupported or unpopulated source table {name!r}; valid={sorted(by_name)}")
        selected.append(by_name[name])
    if not selected:
        raise ValueError("No valid tables resolved from --tables")
    return tuple(selected)


def reconcile_row_counts(expected_counts: dict[str, int], actual_counts: dict[str, int]) -> list[dict[str, Any]]:
    """Return list of mismatches between expected source counts and ingested Bronze counts."""
    mismatches: list[dict[str, Any]] = []
    for tbl, exp in expected_counts.items():
        act = actual_counts.get(tbl)
        if act != exp:
            mismatches.append({"table": tbl, "expected": exp, "actual": act})
    return mismatches


def _ensure_ops_and_bronze_tables(spark: Any, catalog: str) -> None:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.ops")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.bronze_pg")
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {catalog}.ops.ingest_log (
          run_id STRING NOT NULL,
          source_system STRING NOT NULL,
          source_mode STRING NOT NULL,
          table_name STRING NOT NULL,
          source_row_count BIGINT,
          bronze_row_count BIGINT,
          status STRING NOT NULL,
          started_at_utc TIMESTAMP NOT NULL,
          finished_at_utc TIMESTAMP,
          error_detail STRING
        ) USING DELTA
        """
    )


def _append_audit_columns(df: Any, *, run_id: str, ingest_date: str, source_object: str, ingested_at: datetime) -> Any:
    from pyspark.sql import functions as F

    biz_cols = [c for c in df.columns if not c.startswith("_")]
    return (
        df.withColumn("_ingest_run_id", F.lit(run_id))
        .withColumn("_ingest_date", F.to_date(F.lit(ingest_date)))
        .withColumn("_ingested_at_utc", F.lit(ingested_at))
        .withColumn("_source_object", F.lit(source_object))
        .withColumn("_snapshot_mode", F.lit("FULL"))
        .withColumn("_row_hash", F.sha2(F.to_json(F.struct(*[F.col(c) for c in biz_cols])), 256))
    )


def _read_jdbc_table(
    spark: Any,
    *,
    spec: SourceTableSpec,
    jdbc_url: str,
    user: str,
    password: str,
) -> tuple[Any, int]:
    """Read source table via Spark JDBC, returning ``(dataframe, exact_source_count)``."""
    if spec.partition_col and spec.num_partitions > 1:
        bounds_sql = (
            f"(SELECT COUNT(*) AS cnt, MIN({spec.partition_col}) AS lo, "
            f"MAX({spec.partition_col}) AS hi FROM {spec.fq_source}) AS _bounds"
        )
    else:
        bounds_sql = f"(SELECT COUNT(*) AS cnt FROM {spec.fq_source}) AS _bounds"

    bounds_row = (
        spark.read.format("jdbc")
        .option("url", jdbc_url)
        .option("driver", "org.postgresql.Driver")
        .option("dbtable", bounds_sql)
        .option("user", user)
        .option("password", password)
        .option("isolationLevel", "REPEATABLE_READ")
        .load()
        .collect()[0]
    )
    src_count = int(bounds_row["cnt"])

    reader = (
        spark.read.format("jdbc")
        .option("url", jdbc_url)
        .option("driver", "org.postgresql.Driver")
        .option("dbtable", spec.fq_source)
        .option("user", user)
        .option("password", password)
        .option("fetchsize", "10000")
        .option("isolationLevel", "REPEATABLE_READ")
    )
    if spec.partition_col and spec.num_partitions > 1 and src_count > 0:
        lo = int(bounds_row["lo"])
        hi = int(bounds_row["hi"])
        if hi >= lo:
            reader = (
                reader.option("partitionColumn", spec.partition_col)
                .option("lowerBound", str(lo))
                .option("upperBound", str(hi))
                .option("numPartitions", str(spec.num_partitions))
            )
    return reader.load(), src_count


def _read_volume_manifest(spark: Any, volume_root: str) -> tuple[str, dict[str, Any]]:
    """Locate the newest staged manifest.json under ``volume_root``."""
    base = volume_root.rstrip("/")
    df = (
        spark.read.format("binaryFile")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "manifest.json")
        .load(base)
        .select("path", "content", "modificationTime")
        .orderBy("modificationTime", ascending=False)
        .limit(1)
    )
    rows = df.collect()
    if not rows:
        raise FileNotFoundError(f"No staged manifest.json found under {base}")
    manifest_path = str(rows[0]["path"]).removeprefix("dbfs:")
    manifest = json.loads(bytes(rows[0]["content"]).decode("utf-8"))
    run_dir = manifest_path.rsplit("/", 1)[0]
    return run_dir, manifest


def run_pg_snapshot(
    *,
    spark: Any,
    catalog: str,
    source_mode: str = "jdbc",
    run_id: str | None = None,
    tables_csv: str | None = None,
    secret_scope: str = "pharmaflow-dev",
    volume_root: str = "/Volumes/pharmaflow_dev/bronze_pg/pg_raw",
    dbutils_obj: Any = None,
) -> dict[str, Any]:
    """Ingest populated Neon source tables into Bronze and refresh ``latest_*`` views."""
    from pyspark.sql import functions as F
    from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

    _ensure_ops_and_bronze_tables(spark, catalog)
    specs = resolve_tables(tables_csv)
    started_at = datetime.now(timezone.utc)
    ingest_date = started_at.date().isoformat()
    effective_run_id = run_id or f"pg-{started_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"

    jdbc_url = user = password = None
    volume_run_dir = None
    volume_manifest: dict[str, Any] = {}

    if source_mode == "jdbc":
        if dbutils_obj is None:
            raise RuntimeError("dbutils is required in jdbc mode to read secrets")
        jdbc_url = dbutils_obj.secrets.get(secret_scope, "neon_jdbc_url")
        user = dbutils_obj.secrets.get(secret_scope, "neon_user")
        password = dbutils_obj.secrets.get(secret_scope, "neon_password")
    elif source_mode == "volume":
        volume_run_dir, volume_manifest = _read_volume_manifest(spark, volume_root)
    else:
        raise ValueError(f"Unsupported source_mode {source_mode!r}; expected 'jdbc' or 'volume'")

    expected_counts: dict[str, int] = {}
    actual_counts: dict[str, int] = {}
    log_rows: list[dict[str, Any]] = []

    try:
        for spec in specs:
            if source_mode == "jdbc":
                assert jdbc_url and user is not None and password is not None
                raw_df, exp_cnt = _read_jdbc_table(
                    spark, spec=spec, jdbc_url=jdbc_url, user=user, password=password
                )
            else:
                table_entry = (volume_manifest.get("tables") or {}).get(spec.fq_source)
                if not table_entry:
                    raise KeyError(f"Missing table {spec.fq_source} in staged manifest.json")
                exp_cnt = int(table_entry["row_count"])
                file_path = f"{volume_run_dir}/{table_entry['file_name']}"
                raw_df = spark.read.json(file_path)

            expected_counts[spec.fq_source] = exp_cnt
            enriched_df = _append_audit_columns(
                raw_df,
                run_id=effective_run_id,
                ingest_date=ingest_date,
                source_object=spec.fq_source,
                ingested_at=started_at,
            )

            target_table = f"{catalog}.bronze_pg.{spec.bronze_table}"
            table_exists = bool(spark.catalog.tableExists(target_table))
            existing_cnt = 0
            if table_exists:
                existing_cnt = int(
                    spark.table(target_table)
                    .filter(F.col("_ingest_run_id") == effective_run_id)
                    .count()
                )

            if existing_cnt == exp_cnt and exp_cnt > 0:
                written_cnt = existing_cnt
            else:
                if existing_cnt > 0:
                    spark.sql(f"DELETE FROM {target_table} WHERE _ingest_run_id = '{effective_run_id}'")
                (
                    enriched_df.write.format("delta")
                    .mode("append")
                    .option("mergeSchema", "true")
                    .partitionBy("_ingest_date")
                    .saveAsTable(target_table)
                )
                written_cnt = int(
                    spark.table(target_table)
                    .filter(F.col("_ingest_run_id") == effective_run_id)
                    .count()
                )
            actual_counts[spec.fq_source] = written_cnt

        mismatches = reconcile_row_counts(expected_counts, actual_counts)
        finished_at = datetime.now(timezone.utc)
        if mismatches:
            for spec in specs:
                log_rows.append(
                    {
                        "run_id": effective_run_id,
                        "source_system": "POSTGRES",
                        "source_mode": source_mode,
                        "table_name": spec.fq_source,
                        "source_row_count": expected_counts.get(spec.fq_source),
                        "bronze_row_count": actual_counts.get(spec.fq_source),
                        "status": "FAILED",
                        "started_at_utc": started_at,
                        "finished_at_utc": finished_at,
                        "error_detail": json.dumps(mismatches),
                    }
                )
            _write_ingest_logs(spark, catalog, log_rows)
            raise RuntimeError(f"Row count mismatch in PG snapshot {effective_run_id}: {mismatches}")

        # Atomic pointer publication: update latest_* views only after all tables match 100%.
        for spec in specs:
            target_table = f"{catalog}.bronze_pg.{spec.bronze_table}"
            latest_view = f"{catalog}.bronze_pg.{spec.latest_view}"
            spark.sql(
                f"""
                CREATE OR REPLACE VIEW {latest_view} AS
                SELECT * FROM {target_table}
                WHERE _ingest_run_id = '{effective_run_id}'
                """
            )
            log_rows.append(
                {
                    "run_id": effective_run_id,
                    "source_system": "POSTGRES",
                    "source_mode": source_mode,
                    "table_name": spec.fq_source,
                    "source_row_count": expected_counts[spec.fq_source],
                    "bronze_row_count": actual_counts[spec.fq_source],
                    "status": "SUCCEEDED",
                    "started_at_utc": started_at,
                    "finished_at_utc": finished_at,
                    "error_detail": None,
                }
            )
        _write_ingest_logs(spark, catalog, log_rows)

        return {
            "run_id": effective_run_id,
            "source_mode": source_mode,
            "status": "SUCCEEDED",
            "table_count": len(specs),
            "counts": actual_counts,
        }
    except Exception as exc:
        if not log_rows:
            finished_at = datetime.now(timezone.utc)
            log_rows.append(
                {
                    "run_id": effective_run_id,
                    "source_system": "POSTGRES",
                    "source_mode": source_mode,
                    "table_name": "__RUN__",
                    "source_row_count": None,
                    "bronze_row_count": None,
                    "status": "FAILED",
                    "started_at_utc": started_at,
                    "finished_at_utc": finished_at,
                    "error_detail": f"{type(exc).__name__}: {str(exc)[:1000]}",
                }
            )
            _write_ingest_logs(spark, catalog, log_rows)
        raise


def _write_ingest_logs(spark: Any, catalog: str, rows: list[dict[str, Any]]) -> None:
    from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

    schema = StructType(
        [
            StructField("run_id", StringType(), False),
            StructField("source_system", StringType(), False),
            StructField("source_mode", StringType(), False),
            StructField("table_name", StringType(), False),
            StructField("source_row_count", LongType(), True),
            StructField("bronze_row_count", LongType(), True),
            StructField("status", StringType(), False),
            StructField("started_at_utc", TimestampType(), False),
            StructField("finished_at_utc", TimestampType(), True),
            StructField("error_detail", StringType(), True),
        ]
    )
    spark.createDataFrame(rows, schema=schema).write.mode("append").saveAsTable(f"{catalog}.ops.ingest_log")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default="pharmaflow_dev")
    parser.add_argument("--source-mode", choices=("jdbc", "volume"), default="jdbc")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--tables", default="all")
    parser.add_argument("--secret-scope", default="pharmaflow-dev")
    parser.add_argument("--volume-root", default="/Volumes/pharmaflow_dev/bronze_pg/pg_raw")
    return parser.parse_args(argv)


def _read_runtime_params(argv: Sequence[str] | None = None) -> argparse.Namespace:
    dbutils_obj = globals().get("dbutils")
    if argv is None and dbutils_obj is not None and hasattr(dbutils_obj, "widgets"):
        defaults = {
            "catalog": "pharmaflow_dev",
            "source_mode": "jdbc",
            "run_id": "",
            "tables": "all",
            "secret_scope": "pharmaflow-dev",
            "volume_root": "/Volumes/pharmaflow_dev/bronze_pg/pg_raw",
        }
        resolved: dict[str, Any] = {}
        for k, dflt in defaults.items():
            try:
                val = dbutils_obj.widgets.get(k)
                resolved[k] = val if val else dflt
            except Exception:  # noqa: BLE001
                resolved[k] = dflt
        resolved["run_id"] = resolved["run_id"] or None
        resolved["tables_csv"] = resolved.pop("tables")
        return argparse.Namespace(**resolved)
    ns = parse_args(argv)
    return argparse.Namespace(
        catalog=ns.catalog,
        source_mode=ns.source_mode,
        run_id=ns.run_id,
        tables_csv=ns.tables,
        secret_scope=ns.secret_scope,
        volume_root=ns.volume_root,
    )


def main(argv: Sequence[str] | None = None) -> int:
    from pyspark.sql import SparkSession

    args = _read_runtime_params(argv)
    spark = globals().get("spark") or SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    dbutils_obj = globals().get("dbutils")
    summary = run_pg_snapshot(
        spark=spark,
        catalog=args.catalog,
        source_mode=args.source_mode,
        run_id=args.run_id,
        tables_csv=args.tables_csv,
        secret_scope=args.secret_scope,
        volume_root=args.volume_root,
        dbutils_obj=dbutils_obj,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    main()
