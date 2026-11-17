# Databricks notebook source
"""Bronze Auto Loader ingestion for Open-Meteo Weather manifests (``accepted.json`` + ``store_grid_mapping.json``).

Works identically against either Databricks Free Edition Managed Volumes
(``/Volumes/<catalog>/bronze_weather/weather_raw/open_meteo``) or AWS S3
(``s3://<bucket>/raw/open_meteo``) via ``--weather-raw-root``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

MODE_RELATIVE_PREFIXES: dict[str, tuple[str, ...]] = {
    "daily": ("weather_forecast/",),
    "historical": ("historical_forecast/", "historical_weather/"),
    "all": ("weather_forecast/", "historical_forecast/", "historical_weather/"),
}


def prefixes_for_mode(mode: str) -> tuple[str, ...]:
    if mode not in MODE_RELATIVE_PREFIXES:
        raise ValueError(f"Unsupported mode {mode!r}; expected one of {tuple(MODE_RELATIVE_PREFIXES)}")
    return MODE_RELATIVE_PREFIXES[mode]


def resolve_storage_path(weather_raw_root: str, key: str) -> str:
    """Resolve an S3/manifest key (e.g. ``raw/open_meteo/weather_forecast/...``) under ``weather_raw_root``."""
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Storage key must be non-empty")
    if "\\" in key or ".." in PurePosixPath(key).parts:
        raise ValueError(f"Unsafe storage key: {key!r}")

    trimmed = key.lstrip("/")
    for strip_prefix in ("raw/open_meteo/", "open_meteo/"):
        if trimmed.startswith(strip_prefix):
            trimmed = trimmed[len(strip_prefix) :]
            break
    else:
        raise ValueError(
            f"Weather key {key!r} must start with 'raw/open_meteo/' or 'open_meteo/'"
        )
    return f"{weather_raw_root.rstrip('/')}/{trimmed}"


def _parse_iso_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    norm = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(norm).astimezone(timezone.utc)


def _as_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def build_snapshot_record(
    *,
    accepted_bytes: bytes,
    accepted_source_path: str,
    weather_raw_root: str,
    read_bytes_fn: Callable[[str], bytes],
    ingested_at_utc: datetime | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Validate an ``accepted.json`` manifest, verify ``raw_sha256``, and return ``(snapshot_row, error_row)``."""
    now = ingested_at_utc or datetime.now(timezone.utc)
    try:
        accepted = json.loads(accepted_bytes.decode("utf-8"))
        response_key = accepted["response_key"]
        metadata_key = accepted["metadata_key"]
        expected_sha256 = str(accepted["raw_sha256"]).lower()
    except Exception as exc:  # noqa: BLE001
        return None, {
            "accepted_path": accepted_source_path,
            "run_id": None,
            "task_id": None,
            "expected_sha256": None,
            "actual_sha256": None,
            "error_code": "INVALID_ACCEPTED_MANIFEST",
            "error_detail": f"{type(exc).__name__}: {exc}",
            "detected_at_utc": now,
        }

    run_id = accepted.get("run_id")
    task_id = accepted.get("task_id")
    try:
        response_path = resolve_storage_path(weather_raw_root, response_key)
        metadata_path = resolve_storage_path(weather_raw_root, metadata_key)
        response_bytes = read_bytes_fn(response_path)
        actual_sha256 = hashlib.sha256(response_bytes).hexdigest().lower()
    except Exception as exc:  # noqa: BLE001
        return None, {
            "accepted_path": accepted_source_path,
            "run_id": run_id,
            "task_id": task_id,
            "expected_sha256": expected_sha256,
            "actual_sha256": None,
            "error_code": "MISSING_TARGET_FILE",
            "error_detail": f"{type(exc).__name__}: {exc}",
            "detected_at_utc": now,
        }

    if actual_sha256 != expected_sha256:
        return None, {
            "accepted_path": accepted_source_path,
            "run_id": run_id,
            "task_id": task_id,
            "expected_sha256": expected_sha256,
            "actual_sha256": actual_sha256,
            "error_code": "CORRUPTED_SHA256_MISMATCH",
            "error_detail": f"Expected {expected_sha256}, computed {actual_sha256}",
            "detected_at_utc": now,
        }

    try:
        raw_payload = response_bytes.decode("utf-8")
        meta_bytes = read_bytes_fn(metadata_path)
        metadata_json = meta_bytes.decode("utf-8")
        meta = json.loads(metadata_json)
    except Exception as exc:  # noqa: BLE001
        return None, {
            "accepted_path": accepted_source_path,
            "run_id": run_id,
            "task_id": task_id,
            "expected_sha256": expected_sha256,
            "actual_sha256": actual_sha256,
            "error_code": "INVALID_PAYLOAD_OR_METADATA",
            "error_detail": f"{type(exc).__name__}: {exc}",
            "detected_at_utc": now,
        }

    req_coords = meta.get("requested_coordinates") or {}
    ret_coords = meta.get("returned_coordinates") or {}
    window = meta.get("window") or {}
    raw_members = meta.get("member_store_ids")
    member_store_ids = [int(x) for x in raw_members] if isinstance(raw_members, list) else None

    row = {
        "snapshot_id": meta.get("snapshot_id") or f"{run_id}:{task_id}:{accepted.get('attempt_id')}",
        "forecast_snapshot_id": meta.get("forecast_snapshot_id"),
        "run_id": str(meta.get("run_id") or run_id),
        "task_id": str(meta.get("task_id") or task_id),
        "attempt_id": str(meta.get("attempt_id") or accepted.get("attempt_id") or ""),
        "mode": meta.get("mode"),
        "source_type": meta.get("source_type"),
        "store_id": _as_int(meta.get("store_id")),
        "grid_id": meta.get("grid_id"),
        "member_store_ids": member_store_ids,
        "member_store_count": _as_int(meta.get("member_store_count")),
        "store_code": meta.get("store_code"),
        "country_code": meta.get("country_code"),
        "timezone_requested": meta.get("timezone_requested"),
        "timezone_returned": meta.get("timezone_returned"),
        "utc_offset_seconds": _as_int(meta.get("utc_offset_seconds")),
        "elevation_m": _as_float(meta.get("elevation_m")),
        "requested_latitude": _as_float(req_coords.get("latitude")),
        "requested_longitude": _as_float(req_coords.get("longitude")),
        "returned_latitude": _as_float(ret_coords.get("latitude")),
        "returned_longitude": _as_float(ret_coords.get("longitude")),
        "window_start_date": window.get("start_date"),
        "window_end_date": window.get("end_date"),
        "endpoint_key": meta.get("endpoint_key"),
        "model": meta.get("model"),
        "validation_status": meta.get("validation_status") or accepted.get("status"),
        "source": meta.get("source"),
        "coordinate_provenance": meta.get("coordinate_provenance"),
        "coordinate_verification_status": meta.get("coordinate_verification_status"),
        "record_provenance": "OBSERVED",
        "raw_sha256": expected_sha256,
        "raw_byte_length": len(response_bytes),
        "response_key": response_key,
        "metadata_key": metadata_key,
        "accepted_key": accepted_source_path,
        "scheduled_at_utc": _parse_iso_ts(meta.get("scheduled_at_utc")),
        "planned_at_utc": _parse_iso_ts(meta.get("planned_at_utc")),
        "retrieved_at_utc": _parse_iso_ts(meta.get("retrieved_at_utc")),
        "persisted_at_utc": _parse_iso_ts(meta.get("persisted_at_utc")),
        "accepted_at_utc": _parse_iso_ts(accepted.get("accepted_at_utc")),
        "ingested_at_utc": now,
        "raw_payload": raw_payload,
        "metadata_json": metadata_json,
    }
    return row, None


def parse_store_grid_mapping_rows(
    mapping_bytes: bytes,
    *,
    source_file: str,
    ingested_at_utc: datetime | None = None,
) -> list[dict[str, Any]]:
    """Flatten a run's ``store_grid_mapping.json`` into Delta table rows."""
    now = ingested_at_utc or datetime.now(timezone.utc)
    doc = json.loads(mapping_bytes.decode("utf-8"))
    run_id = str(doc["run_id"])
    cohort_id = doc.get("cohort_id")
    created_at = _parse_iso_ts(doc.get("created_at_utc"))
    rows: list[dict[str, Any]] = []
    for item in doc.get("mappings", []):
        rows.append(
            {
                "run_id": run_id,
                "store_id": int(item["store_id"]),
                "cohort_id": cohort_id,
                "point_id": str(item["point_id"]),
                "grid_id": item.get("grid_id"),
                "clustered": bool(item.get("clustered", False)),
                "store_code": item.get("store_code"),
                "country_code": item.get("country_code"),
                "timezone_name": item.get("timezone_name"),
                "store_latitude": _as_float(item.get("store_latitude")),
                "store_longitude": _as_float(item.get("store_longitude")),
                "point_latitude": _as_float(item.get("point_latitude")),
                "point_longitude": _as_float(item.get("point_longitude")),
                "source": item.get("source"),
                "coordinate_provenance": item.get("coordinate_provenance"),
                "coordinate_verification_status": item.get("coordinate_verification_status"),
                "created_at_utc": created_at,
                "source_file": source_file,
                "ingested_at_utc": now,
            }
        )
    return rows


def _ensure_tables(spark: Any, catalog: str) -> None:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.bronze_weather")
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {catalog}.bronze_weather.raw_snapshots (
          snapshot_id STRING,
          forecast_snapshot_id STRING,
          run_id STRING,
          task_id STRING,
          attempt_id STRING,
          mode STRING,
          source_type STRING,
          store_id INT,
          grid_id STRING,
          member_store_ids ARRAY<INT>,
          member_store_count INT,
          store_code STRING,
          country_code STRING,
          timezone_requested STRING,
          timezone_returned STRING,
          utc_offset_seconds INT,
          elevation_m DOUBLE,
          requested_latitude DOUBLE,
          requested_longitude DOUBLE,
          returned_latitude DOUBLE,
          returned_longitude DOUBLE,
          window_start_date STRING,
          window_end_date STRING,
          endpoint_key STRING,
          model STRING,
          validation_status STRING,
          source STRING,
          coordinate_provenance STRING,
          coordinate_verification_status STRING,
          record_provenance STRING,
          raw_sha256 STRING,
          raw_byte_length BIGINT,
          response_key STRING,
          metadata_key STRING,
          accepted_key STRING,
          scheduled_at_utc TIMESTAMP,
          planned_at_utc TIMESTAMP,
          retrieved_at_utc TIMESTAMP,
          persisted_at_utc TIMESTAMP,
          accepted_at_utc TIMESTAMP,
          ingested_at_utc TIMESTAMP,
          raw_payload STRING,
          metadata_json STRING
        ) USING DELTA
        """
    )
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {catalog}.bronze_weather.store_grid_mapping (
          run_id STRING,
          store_id INT,
          cohort_id STRING,
          point_id STRING,
          grid_id STRING,
          clustered BOOLEAN,
          store_code STRING,
          country_code STRING,
          timezone_name STRING,
          store_latitude DOUBLE,
          store_longitude DOUBLE,
          point_latitude DOUBLE,
          point_longitude DOUBLE,
          source STRING,
          coordinate_provenance STRING,
          coordinate_verification_status STRING,
          created_at_utc TIMESTAMP,
          source_file STRING,
          ingested_at_utc TIMESTAMP
        ) USING DELTA
        """
    )
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {catalog}.bronze_weather.ingest_errors (
          accepted_path STRING,
          run_id STRING,
          task_id STRING,
          expected_sha256 STRING,
          actual_sha256 STRING,
          error_code STRING,
          error_detail STRING,
          detected_at_utc TIMESTAMP
        ) USING DELTA
        """
    )


def _snapshot_spark_schema():
    from pyspark.sql.types import (
        ArrayType,
        DoubleType,
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    return StructType(
        [
            StructField("snapshot_id", StringType(), False),
            StructField("forecast_snapshot_id", StringType(), True),
            StructField("run_id", StringType(), False),
            StructField("task_id", StringType(), False),
            StructField("attempt_id", StringType(), False),
            StructField("mode", StringType(), True),
            StructField("source_type", StringType(), True),
            StructField("store_id", IntegerType(), True),
            StructField("grid_id", StringType(), True),
            StructField("member_store_ids", ArrayType(IntegerType()), True),
            StructField("member_store_count", IntegerType(), True),
            StructField("store_code", StringType(), True),
            StructField("country_code", StringType(), True),
            StructField("timezone_requested", StringType(), True),
            StructField("timezone_returned", StringType(), True),
            StructField("utc_offset_seconds", IntegerType(), True),
            StructField("elevation_m", DoubleType(), True),
            StructField("requested_latitude", DoubleType(), True),
            StructField("requested_longitude", DoubleType(), True),
            StructField("returned_latitude", DoubleType(), True),
            StructField("returned_longitude", DoubleType(), True),
            StructField("window_start_date", StringType(), True),
            StructField("window_end_date", StringType(), True),
            StructField("endpoint_key", StringType(), True),
            StructField("model", StringType(), True),
            StructField("validation_status", StringType(), True),
            StructField("source", StringType(), True),
            StructField("coordinate_provenance", StringType(), True),
            StructField("coordinate_verification_status", StringType(), True),
            StructField("record_provenance", StringType(), False),
            StructField("raw_sha256", StringType(), False),
            StructField("raw_byte_length", LongType(), False),
            StructField("response_key", StringType(), False),
            StructField("metadata_key", StringType(), False),
            StructField("accepted_key", StringType(), False),
            StructField("scheduled_at_utc", TimestampType(), True),
            StructField("planned_at_utc", TimestampType(), True),
            StructField("retrieved_at_utc", TimestampType(), True),
            StructField("persisted_at_utc", TimestampType(), True),
            StructField("accepted_at_utc", TimestampType(), True),
            StructField("ingested_at_utc", TimestampType(), False),
            StructField("raw_payload", StringType(), False),
            StructField("metadata_json", StringType(), False),
        ]
    )


def _mapping_spark_schema():
    from pyspark.sql.types import (
        BooleanType,
        DoubleType,
        IntegerType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    return StructType(
        [
            StructField("run_id", StringType(), False),
            StructField("store_id", IntegerType(), False),
            StructField("cohort_id", StringType(), True),
            StructField("point_id", StringType(), False),
            StructField("grid_id", StringType(), True),
            StructField("clustered", BooleanType(), False),
            StructField("store_code", StringType(), True),
            StructField("country_code", StringType(), True),
            StructField("timezone_name", StringType(), True),
            StructField("store_latitude", DoubleType(), True),
            StructField("store_longitude", DoubleType(), True),
            StructField("point_latitude", DoubleType(), True),
            StructField("point_longitude", DoubleType(), True),
            StructField("source", StringType(), True),
            StructField("coordinate_provenance", StringType(), True),
            StructField("coordinate_verification_status", StringType(), True),
            StructField("created_at_utc", TimestampType(), True),
            StructField("source_file", StringType(), False),
            StructField("ingested_at_utc", TimestampType(), False),
        ]
    )


def _error_spark_schema():
    from pyspark.sql.types import StringType, StructField, StructType, TimestampType

    return StructType(
        [
            StructField("accepted_path", StringType(), False),
            StructField("run_id", StringType(), True),
            StructField("task_id", StringType(), True),
            StructField("expected_sha256", StringType(), True),
            StructField("actual_sha256", StringType(), True),
            StructField("error_code", StringType(), False),
            StructField("error_detail", StringType(), False),
            StructField("detected_at_utc", TimestampType(), False),
        ]
    )


def _read_spark_binary_map(spark: Any, paths: Sequence[str]) -> dict[str, bytes]:
    if not paths:
        return {}
    df = spark.read.format("binaryFile").load(list(paths)).select("path", "content")
    out: dict[str, bytes] = {}
    for rec in df.toLocalIterator():
        norm = str(rec["path"]).removeprefix("dbfs:")
        out[norm] = bytes(rec["content"])
        out[str(rec["path"])] = bytes(rec["content"])
    return out


def _has_matching_files(spark: Any, source_dir: str, glob_name: str) -> bool:
    try:
        return (
            spark.read.format("binaryFile")
            .option("recursiveFileLookup", "true")
            .option("pathGlobFilter", glob_name)
            .load(source_dir)
            .limit(1)
            .count()
            > 0
        )
    except Exception:  # noqa: BLE001 - directory may not exist yet for a dataset prefix
        return False


def run_autoloader(
    *,
    spark: Any,
    mode: str,
    catalog: str,
    weather_raw_root: str,
    checkpoint_root: str,
) -> dict[str, int]:
    """Run Auto Loader (``availableNow=True``) for ``accepted.json`` and ``store_grid_mapping.json``."""
    _ensure_tables(spark, catalog)
    counters = {"accepted_rows": 0, "error_rows": 0, "mapping_rows": 0}

    for rel_prefix in prefixes_for_mode(mode):
        source_dir = f"{weather_raw_root.rstrip('/')}/{rel_prefix.rstrip('/')}"
        dataset_slug = rel_prefix.strip("/")
        if not _has_matching_files(spark, source_dir, "accepted.json"):
            continue

        def _process_accepted_batch(batch_df: Any, batch_id: int) -> None:  # noqa: ARG001
            manifest_rows = [(str(r["path"]), bytes(r["content"])) for r in batch_df.select("path", "content").collect()]
            if not manifest_rows:
                return

            target_paths: list[str] = []
            for _, raw_manifest in manifest_rows:
                try:
                    m = json.loads(raw_manifest.decode("utf-8"))
                    target_paths.append(resolve_storage_path(weather_raw_root, m["response_key"]))
                    target_paths.append(resolve_storage_path(weather_raw_root, m["metadata_key"]))
                except Exception:  # noqa: BLE001 - build_snapshot_record captures invalid manifests cleanly
                    continue

            blob_map = _read_spark_binary_map(spark, sorted(set(target_paths)))

            def _lookup_bytes(p: str) -> bytes:
                if p in blob_map:
                    return blob_map[p]
                dbfs_p = f"dbfs:{p}" if p.startswith("/") else p
                if dbfs_p in blob_map:
                    return blob_map[dbfs_p]
                raise FileNotFoundError(f"Missing target object at {p}")

            valid_rows: list[dict[str, Any]] = []
            error_rows: list[dict[str, Any]] = []
            for src_path, raw_manifest in manifest_rows:
                snap, err = build_snapshot_record(
                    accepted_bytes=raw_manifest,
                    accepted_source_path=str(src_path).removeprefix("dbfs:"),
                    weather_raw_root=weather_raw_root,
                    read_bytes_fn=_lookup_bytes,
                )
                if snap is not None:
                    valid_rows.append(snap)
                if err is not None:
                    error_rows.append(err)

            if error_rows:
                err_df = spark.createDataFrame(error_rows, schema=_error_spark_schema())
                err_df.write.mode("append").saveAsTable(f"{catalog}.bronze_weather.ingest_errors")
                counters["error_rows"] += len(error_rows)

            if valid_rows:
                snap_df = spark.createDataFrame(valid_rows, schema=_snapshot_spark_schema()).dropDuplicates(["snapshot_id"])
                snap_df.createOrReplaceTempView("_tmp_weather_snapshots_batch")
                spark.sql(
                    f"""
                    MERGE INTO {catalog}.bronze_weather.raw_snapshots AS tgt
                    USING _tmp_weather_snapshots_batch AS src
                    ON tgt.snapshot_id = src.snapshot_id
                    WHEN NOT MATCHED THEN INSERT *
                    """
                )
                counters["accepted_rows"] += len(valid_rows)

        acc_stream = (
            spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "binaryFile")
            .option("cloudFiles.includeExistingFiles", "true")
            .option("cloudFiles.maxFilesPerTrigger", "250")
            .option("recursiveFileLookup", "true")
            .option("pathGlobFilter", "accepted.json")
            .load(source_dir)
        )
        acc_query = (
            acc_stream.writeStream.foreachBatch(_process_accepted_batch)
            .option("checkpointLocation", f"{checkpoint_root.rstrip('/')}/weather_accepted/{dataset_slug}")
            .trigger(availableNow=True)
            .start()
        )
        acc_query.awaitTermination()

        if _has_matching_files(spark, source_dir, "store_grid_mapping.json"):

            def _process_mapping_batch(batch_df: Any, batch_id: int) -> None:  # noqa: ARG001
                collected = batch_df.select("path", "content").collect()
                all_rows: list[dict[str, Any]] = []
                for rec in collected:
                    all_rows.extend(
                        parse_store_grid_mapping_rows(
                            bytes(rec["content"]),
                            source_file=str(rec["path"]).removeprefix("dbfs:"),
                        )
                    )
                if not all_rows:
                    return
                map_df = spark.createDataFrame(all_rows, schema=_mapping_spark_schema()).dropDuplicates(
                    ["run_id", "store_id"]
                )
                map_df.createOrReplaceTempView("_tmp_weather_mapping_batch")
                spark.sql(
                    f"""
                    MERGE INTO {catalog}.bronze_weather.store_grid_mapping AS tgt
                    USING _tmp_weather_mapping_batch AS src
                    ON tgt.run_id = src.run_id AND tgt.store_id = src.store_id
                    WHEN NOT MATCHED THEN INSERT *
                    """
                )
                counters["mapping_rows"] += len(all_rows)

            map_stream = (
                spark.readStream.format("cloudFiles")
                .option("cloudFiles.format", "binaryFile")
                .option("cloudFiles.includeExistingFiles", "true")
                .option("cloudFiles.maxFilesPerTrigger", "50")
                .option("recursiveFileLookup", "true")
                .option("pathGlobFilter", "store_grid_mapping.json")
                .load(source_dir)
            )
            map_query = (
                map_stream.writeStream.foreachBatch(_process_mapping_batch)
                .option("checkpointLocation", f"{checkpoint_root.rstrip('/')}/weather_mapping/{dataset_slug}")
                .trigger(availableNow=True)
                .start()
            )
            map_query.awaitTermination()

    return counters


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("daily", "historical", "all"), default="daily")
    parser.add_argument("--catalog", default="pharmaflow_dev")
    parser.add_argument(
        "--weather-raw-root",
        default="/Volumes/pharmaflow_dev/bronze_weather/weather_raw/open_meteo",
    )
    parser.add_argument(
        "--checkpoint-root",
        default="/Volumes/pharmaflow_dev/bronze_weather/weather_raw/_checkpoints",
    )
    return parser.parse_args(argv)


def _read_runtime_params(argv: Sequence[str] | None = None) -> argparse.Namespace:
    dbutils_obj = globals().get("dbutils")
    if argv is None and dbutils_obj is not None and hasattr(dbutils_obj, "widgets"):
        defaults = {
            "mode": "daily",
            "catalog": "pharmaflow_dev",
            "weather_raw_root": "/Volumes/pharmaflow_dev/bronze_weather/weather_raw/open_meteo",
            "checkpoint_root": "/Volumes/pharmaflow_dev/bronze_weather/weather_raw/_checkpoints",
        }
        resolved: dict[str, str] = {}
        for k, default_val in defaults.items():
            try:
                val = dbutils_obj.widgets.get(k)
                resolved[k] = val if val else default_val
            except Exception:  # noqa: BLE001
                resolved[k] = default_val
        return argparse.Namespace(**resolved)
    return parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    from pyspark.sql import SparkSession

    args = _read_runtime_params(argv)
    spark = globals().get("spark") or SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    summary = run_autoloader(
        spark=spark,
        mode=args.mode,
        catalog=args.catalog,
        weather_raw_root=args.weather_raw_root,
        checkpoint_root=args.checkpoint_root,
    )
    print(json.dumps({"mode": args.mode, "catalog": args.catalog, **summary}))
    if summary["error_rows"] > 0:
        raise RuntimeError(f"Weather Auto Loader detected {summary['error_rows']} SHA-256/manifest errors")
    return 0


if __name__ == "__main__":
    main()
