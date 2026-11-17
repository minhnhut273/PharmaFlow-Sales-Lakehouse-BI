# Databricks notebook source
"""Bronze snapshot ingestion for MongoDB Extended JSON product knowledge bundles.

Reads validated ``manifest.json`` + ``documents.ejsonl`` bundles staged under
``<volume_root>/run_id=<source_run_id>/``, verifies SHA-256 and document counts,
unwraps Mongo Extended JSON wrappers, appends into
``<catalog>.bronze_mongo.product_snapshots``, updates
``<catalog>.bronze_mongo.latest_product_snapshots``, and logs to ``<catalog>.ops.ingest_log``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


def unwrap_extended_json(value: Any) -> Any:
    """Recursively convert MongoDB Extended JSON v2 wrappers into plain Python/JSON primitives."""
    if isinstance(value, list):
        return [unwrap_extended_json(item) for item in value]
    if isinstance(value, dict):
        if len(value) == 1:
            if "$numberInt" in value:
                return int(value["$numberInt"])
            if "$numberLong" in value:
                return int(value["$numberLong"])
            if "$numberDouble" in value:
                return float(value["$numberDouble"])
            if "$numberDecimal" in value:
                return float(value["$numberDecimal"])
            if "$oid" in value:
                return str(value["$oid"])
            if "$date" in value:
                inner = value["$date"]
                if isinstance(inner, dict) and "$numberLong" in inner:
                    ms = int(inner["$numberLong"])
                    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")
                if isinstance(inner, (int, float)):
                    return (
                        datetime.fromtimestamp(float(inner) / 1000.0, tz=timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
                return str(inner)
        return {k: unwrap_extended_json(v) for k, v in value.items()}
    return value


def parse_iso_utc_timestamp(raw: Any) -> datetime | None:
    """Parse an unwrapped ISO-8601 UTC string into a timezone-aware ``datetime``."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def normalize_mongo_document(
    raw_doc: Mapping[str, Any],
    *,
    ingest_run_id: str,
    ingest_date: Any,
    source_run_id: str,
    source_object: str,
    ingested_at: datetime,
) -> dict[str, Any]:
    """Unwrap Extended JSON fields and shape one Bronze ``product_snapshots`` record."""
    doc = unwrap_extended_json(dict(raw_doc))
    composition = doc.get("composition") if isinstance(doc.get("composition"), dict) else {}
    storage = doc.get("storage") if isinstance(doc.get("storage"), dict) else {}
    provenance = doc.get("provenance") if isinstance(doc.get("provenance"), dict) else {}
    extraction = doc.get("extraction") if isinstance(doc.get("extraction"), dict) else {}
    items = composition.get("items") if isinstance(composition.get("items"), list) else []

    normalized_items = [
        {
            "name": str(item["name"]) if item.get("name") is not None else None,
            "description_text": str(item["description_text"]) if item.get("description_text") is not None else None,
            "source_ingredient_id": (
                int(item["source_ingredient_id"]) if item.get("source_ingredient_id") is not None else None
            ),
            "source_is_primary": (
                bool(item["source_is_primary"]) if item.get("source_is_primary") is not None else None
            ),
            "source_record_id": (
                int(item["source_record_id"]) if item.get("source_record_id") is not None else None
            ),
            "source_slug": str(item["source_slug"]) if item.get("source_slug") is not None else None,
        }
        for item in items
        if isinstance(item, dict)
    ]

    canonical_json = json.dumps(doc, ensure_ascii=False, sort_keys=True)
    row_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    raw_schema_ver = doc.get("schema_version")
    return {
        "source": str(doc["source"]) if doc.get("source") is not None else None,
        "source_product_key": str(doc["source_product_key"]) if doc.get("source_product_key") is not None else None,
        "source_sku": str(doc["source_sku"]) if doc.get("source_sku") is not None else None,
        "schema_version": int(raw_schema_ver) if raw_schema_ver is not None else None,
        "composition_basis_text": (
            str(composition["basis_text"]) if composition.get("basis_text") is not None else None
        ),
        "composition_details_markdown": (
            str(composition["details_markdown"]) if composition.get("details_markdown") is not None else None
        ),
        "composition_web_description_markdown": (
            str(composition["web_description_markdown"])
            if composition.get("web_description_markdown") is not None
            else None
        ),
        "composition_items": normalized_items,
        "composition_items_count": len(normalized_items),
        "storage_instructions_text": (
            str(storage["instructions_text"]) if storage.get("instructions_text") is not None else None
        ),
        "provenance_captured_at_utc": parse_iso_utc_timestamp(provenance.get("captured_at")),
        "provenance_content_hash": (
            str(provenance["content_hash"]) if provenance.get("content_hash") is not None else None
        ),
        "provenance_evidence_status": (
            str(provenance["evidence_status"]) if provenance.get("evidence_status") is not None else None
        ),
        "provenance_raw_local_path": (
            str(provenance["raw_local_path"]) if provenance.get("raw_local_path") is not None else None
        ),
        "provenance_source_url": str(provenance["source_url"]) if provenance.get("source_url") is not None else None,
        "extraction_extracted_at_utc": parse_iso_utc_timestamp(extraction.get("extracted_at")),
        "extraction_status": str(extraction["status"]) if extraction.get("status") is not None else None,
        "extraction_version": str(extraction["version"]) if extraction.get("version") is not None else None,
        "source_run_id": source_run_id,
        "raw_json": canonical_json,
        "_ingest_run_id": ingest_run_id,
        "_ingest_date": ingest_date,
        "_ingested_at_utc": ingested_at,
        "_source_object": source_object,
        "_row_hash": row_hash,
    }


def _manifest_document_count(manifest: Mapping[str, Any]) -> int:
    stats = manifest.get("stats") if isinstance(manifest.get("stats"), Mapping) else {}
    val = manifest.get("document_count")
    if val is None:
        val = stats.get("unique_snapshots")
    if val is None:
        raise KeyError("Mongo manifest missing both 'document_count' and 'stats.unique_snapshots'")
    return int(val)


def parse_and_validate_bundle_bytes(
    *,
    manifest_bytes: bytes,
    data_bytes: bytes,
    ingest_run_id: str,
    ingest_date: Any,
    source_object: str,
    ingested_at: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Validate SHA-256 + count for raw bundle bytes and return ``(manifest, normalized_rows)``."""
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    source_run_id = str(manifest["run_id"])
    expected_sha = str(manifest["data_sha256"])
    expected_count = _manifest_document_count(manifest)

    actual_sha = hashlib.sha256(data_bytes).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError(f"Mongo bundle SHA-256 mismatch: expected {expected_sha}, got {actual_sha}")

    rows: list[dict[str, Any]] = []
    for raw_line in data_bytes.decode("utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed = json.loads(line)
        rows.append(
            normalize_mongo_document(
                parsed,
                ingest_run_id=ingest_run_id,
                ingest_date=ingest_date,
                source_run_id=source_run_id,
                source_object=source_object,
                ingested_at=ingested_at,
            )
        )

    if len(rows) != expected_count:
        raise ValueError(f"Mongo bundle count mismatch: expected {expected_count}, got {len(rows)}")
    return manifest, rows


def _ensure_schemas_and_log_table(spark: Any, catalog: str) -> None:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.ops")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.bronze_mongo")
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


def _spark_product_snapshot_schema() -> Any:
    from pyspark.sql.types import (
        ArrayType,
        BooleanType,
        DateType,
        LongType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    item_struct = StructType(
        [
            StructField("name", StringType(), True),
            StructField("description_text", StringType(), True),
            StructField("source_ingredient_id", LongType(), True),
            StructField("source_is_primary", BooleanType(), True),
            StructField("source_record_id", LongType(), True),
            StructField("source_slug", StringType(), True),
        ]
    )
    return StructType(
        [
            StructField("source", StringType(), True),
            StructField("source_product_key", StringType(), True),
            StructField("source_sku", StringType(), True),
            StructField("schema_version", LongType(), True),
            StructField("composition_basis_text", StringType(), True),
            StructField("composition_details_markdown", StringType(), True),
            StructField("composition_web_description_markdown", StringType(), True),
            StructField("composition_items", ArrayType(item_struct), False),
            StructField("composition_items_count", LongType(), False),
            StructField("storage_instructions_text", StringType(), True),
            StructField("provenance_captured_at_utc", TimestampType(), True),
            StructField("provenance_content_hash", StringType(), True),
            StructField("provenance_evidence_status", StringType(), True),
            StructField("provenance_raw_local_path", StringType(), True),
            StructField("provenance_source_url", StringType(), True),
            StructField("extraction_extracted_at_utc", TimestampType(), True),
            StructField("extraction_status", StringType(), True),
            StructField("extraction_version", StringType(), True),
            StructField("source_run_id", StringType(), False),
            StructField("raw_json", StringType(), False),
            StructField("_ingest_run_id", StringType(), False),
            StructField("_ingest_date", DateType(), False),
            StructField("_ingested_at_utc", TimestampType(), False),
            StructField("_source_object", StringType(), False),
            StructField("_row_hash", StringType(), False),
        ]
    )


def _locate_staged_manifest(spark: Any, volume_root: str, source_run_id: str | None = None) -> tuple[str, bytes]:
    base = volume_root.rstrip("/")
    search_root = f"{base}/run_id={source_run_id}" if source_run_id else base
    df = (
        spark.read.format("binaryFile")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "manifest.json")
        .load(search_root)
        .select("path", "content", "modificationTime")
        .orderBy("modificationTime", ascending=False)
        .limit(1)
    )
    rows = df.collect()
    if not rows:
        raise FileNotFoundError(f"No staged Mongo manifest.json found under {search_root}")
    manifest_path = str(rows[0]["path"]).removeprefix("dbfs:")
    return manifest_path.rsplit("/", 1)[0], bytes(rows[0]["content"])


def run_mongo_snapshot(
    *,
    spark: Any,
    catalog: str,
    volume_root: str = "/Volumes/pharmaflow_dev/bronze_mongo/mongo_raw",
    run_id: str | None = None,
    source_run_id: str | None = None,
) -> dict[str, Any]:
    """Ingest staged MongoDB ``product_snapshots`` bundle from UC Volume into Bronze Delta + latest view."""
    from pyspark.sql import functions as F

    _ensure_schemas_and_log_table(spark, catalog)
    started_at = datetime.now(timezone.utc)
    ingest_date = started_at.date()
    effective_run_id = run_id or f"mongo-{started_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"

    try:
        run_dir, manifest_bytes = _locate_staged_manifest(spark, volume_root, source_run_id=source_run_id)
        manifest_meta = json.loads(manifest_bytes.decode("utf-8"))
        data_file = str(manifest_meta["data_file"])
        data_path = f"{run_dir}/{data_file}"

        binary_rows = spark.read.format("binaryFile").load(data_path).select("content").collect()
        if not binary_rows:
            raise FileNotFoundError(f"Missing staged Mongo data file at {data_path}")
        data_bytes = bytes(binary_rows[0]["content"])

        manifest, normalized_rows = parse_and_validate_bundle_bytes(
            manifest_bytes=manifest_bytes,
            data_bytes=data_bytes,
            ingest_run_id=effective_run_id,
            ingest_date=ingest_date,
            source_object=data_path,
            ingested_at=started_at,
        )
        expected_count = _manifest_document_count(manifest)

        target_table = f"{catalog}.bronze_mongo.product_snapshots"
        latest_view = f"{catalog}.bronze_mongo.latest_product_snapshots"
        table_exists = bool(spark.catalog.tableExists(target_table))
        existing_cnt = 0
        if table_exists:
            existing_cnt = int(
                spark.table(target_table).filter(F.col("_ingest_run_id") == effective_run_id).count()
            )

        if existing_cnt == expected_count and expected_count > 0:
            written_cnt = existing_cnt
        else:
            if existing_cnt > 0:
                spark.sql(f"DELETE FROM {target_table} WHERE _ingest_run_id = '{effective_run_id}'")
            df = spark.createDataFrame(normalized_rows, schema=_spark_product_snapshot_schema())
            (
                df.write.format("delta")
                .mode("append")
                .option("mergeSchema", "true")
                .partitionBy("_ingest_date")
                .saveAsTable(target_table)
            )
            written_cnt = int(
                spark.table(target_table).filter(F.col("_ingest_run_id") == effective_run_id).count()
            )

        if written_cnt != expected_count:
            raise RuntimeError(
                f"Mongo Bronze row count mismatch for {effective_run_id}: expected {expected_count}, got {written_cnt}"
            )

        spark.sql(
            f"""
            CREATE OR REPLACE VIEW {latest_view} AS
            SELECT * FROM {target_table}
            WHERE _ingest_run_id = '{effective_run_id}'
            """
        )

        finished_at = datetime.now(timezone.utc)
        _write_ingest_logs(
            spark,
            catalog,
            [
                {
                    "run_id": effective_run_id,
                    "source_system": "MONGODB",
                    "source_mode": "volume",
                    "table_name": "product_snapshots",
                    "source_row_count": expected_count,
                    "bronze_row_count": written_cnt,
                    "status": "SUCCEEDED",
                    "started_at_utc": started_at,
                    "finished_at_utc": finished_at,
                    "error_detail": None,
                }
            ],
        )
        return {
            "run_id": effective_run_id,
            "source_run_id": manifest["run_id"],
            "status": "SUCCEEDED",
            "document_count": written_cnt,
            "data_sha256": manifest["data_sha256"],
        }
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        _write_ingest_logs(
            spark,
            catalog,
            [
                {
                    "run_id": effective_run_id,
                    "source_system": "MONGODB",
                    "source_mode": "volume",
                    "table_name": "product_snapshots",
                    "source_row_count": None,
                    "bronze_row_count": None,
                    "status": "FAILED",
                    "started_at_utc": started_at,
                    "finished_at_utc": finished_at,
                    "error_detail": f"{type(exc).__name__}: {str(exc)[:1000]}",
                }
            ],
        )
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default="pharmaflow_dev")
    parser.add_argument("--volume-root", default="/Volumes/pharmaflow_dev/bronze_mongo/mongo_raw")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--source-run-id", default=None)
    return parser.parse_args(argv)


def _read_runtime_params(argv: Sequence[str] | None = None) -> argparse.Namespace:
    dbutils_obj = globals().get("dbutils")
    if argv is None and dbutils_obj is not None and hasattr(dbutils_obj, "widgets"):
        defaults = {
            "catalog": "pharmaflow_dev",
            "volume_root": "/Volumes/pharmaflow_dev/bronze_mongo/mongo_raw",
            "run_id": "",
            "source_run_id": "",
        }
        resolved: dict[str, Any] = {}
        for k, dflt in defaults.items():
            try:
                val = dbutils_obj.widgets.get(k)
                resolved[k] = val if val else dflt
            except Exception:  # noqa: BLE001
                resolved[k] = dflt
        resolved["run_id"] = resolved["run_id"] or None
        resolved["source_run_id"] = resolved["source_run_id"] or None
        return argparse.Namespace(**resolved)
    return parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    from pyspark.sql import SparkSession

    args = _read_runtime_params(argv)
    spark = globals().get("spark") or SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    summary = run_mongo_snapshot(
        spark=spark,
        catalog=args.catalog,
        volume_root=args.volume_root,
        run_id=args.run_id,
        source_run_id=args.source_run_id,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    main()
