"""Offline unit tests for Postgres & MongoDB Bronze ingestion and Volume sync helpers."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from databricks.sdk.errors import NotFound

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from src.bronze.mongo_snapshots import (  # noqa: E402
    normalize_mongo_document,
    parse_and_validate_bundle_bytes,
    unwrap_extended_json,
)
from src.bronze.pg_snapshot import (  # noqa: E402
    POPULATED_SOURCE_TABLES,
    reconcile_row_counts,
    resolve_tables,
)
from src.bronze.sync_mongo_to_volume import (  # noqa: E402
    sync_mongo_bundle_to_volume,
    validate_local_mongo_bundle,
)
from src.bronze.sync_neon_to_volume import (  # noqa: E402
    export_table_rows_to_jsonl_gz,
    sync_neon_tables_to_volume,
)


class _FakeDownloadResponse:
    def __init__(self, content: bytes) -> None:
        self.contents = io.BytesIO(content)


class _FakeFilesAPI:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, bytes, bool]] = []
        self.storage: dict[str, bytes] = {}

    def upload(self, path: str, data: io.BytesIO, overwrite: bool = False) -> None:
        raw = data.read()
        self.uploaded.append((path, raw, overwrite))
        self.storage[path] = raw

    def download(self, path: str) -> _FakeDownloadResponse:
        if path not in self.storage:
            raise NotFound(path)
        return _FakeDownloadResponse(self.storage[path])


class _FakeWorkspaceClient:
    def __init__(self) -> None:
        self.files = _FakeFilesAPI()


def test_resolve_tables_and_reconcile_counts() -> None:
    all_specs = resolve_tables(None)
    assert len(all_specs) == 12
    assert all_specs == POPULATED_SOURCE_TABLES

    subset = resolve_tables("pos.sales_order, org.store")
    assert [s.fq_source for s in subset] == ["pos.sales_order", "org.store"]

    with pytest.raises(ValueError, match="Unsupported"):
        resolve_tables("pos.nonexistent")

    assert reconcile_row_counts({"pos.sales_order": 10}, {"pos.sales_order": 10}) == []
    mismatches = reconcile_row_counts(
        {"pos.sales_order": 10, "org.store": 5},
        {"pos.sales_order": 9},
    )
    assert mismatches == [
        {"table": "pos.sales_order", "expected": 10, "actual": 9},
        {"table": "org.store", "expected": 5, "actual": None},
    ]


def test_unwrap_extended_json_and_normalize_doc() -> None:
    raw_doc = {
        "schema_version": {"$numberInt": "1"},
        "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
        "source_product_key": "SKU:00000462",
        "source_sku": "00000462",
        "composition": {
            "basis_text": "1 goi",
            "details_markdown": "Acetylcysteine 200mg",
            "web_description_markdown": "Desc",
            "items": [
                {
                    "name": "Acetylcysteine",
                    "description_text": "200mg",
                    "source_ingredient_id": {"$numberInt": "7376"},
                    "source_is_primary": True,
                    "source_record_id": {"$numberInt": "41162"},
                    "source_slug": "thanh-phan/acetylcysteine",
                }
            ],
        },
        "storage": {"instructions_text": "Noi kho rao"},
        "provenance": {
            "captured_at": {"$date": {"$numberLong": "1791314263197"}},
            "content_hash": "a" * 64,
            "evidence_status": "observed",
            "raw_local_path": "dataset/longchau-knowledge/_raw/test.html",
            "source_url": "https://nhathuoclongchau.com.vn/thuoc/acemuc-200mg-4881.html",
        },
        "extraction": {
            "extracted_at": {"$date": {"$numberLong": "1793863098462"}},
            "status": "COMPLETE",
            "version": "longchau-product-knowledge-v1",
        },
    }
    unwrapped = unwrap_extended_json(raw_doc)
    assert unwrapped["schema_version"] == 1
    assert unwrapped["composition"]["items"][0]["source_ingredient_id"] == 7376
    assert unwrapped["provenance"]["captured_at"].endswith("Z")

    row = normalize_mongo_document(
        raw_doc,
        ingest_run_id="run-1",
        ingest_date=date(2026, 11, 17),
        source_run_id="lc-run-1",
        source_object="/Volumes/test/documents.ejsonl",
        ingested_at=datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc),
    )
    assert row["schema_version"] == 1
    assert row["composition_items_count"] == 1
    assert row["composition_items"][0]["source_is_primary"] is True
    assert row["provenance_captured_at_utc"].year == 2026
    assert len(row["_row_hash"]) == 64


def _build_mongo_bundle_dir(tmp_path: Path, docs: list[dict[str, Any]], *, stats_key: bool = True) -> Path:
    run_dir = tmp_path / "lc-test-01"
    run_dir.mkdir(parents=True, exist_ok=True)
    ejsonl_bytes = ("\n".join(json.dumps(d) for d in docs) + "\n").encode("utf-8")
    (run_dir / "documents.ejsonl").write_bytes(ejsonl_bytes)
    sha = hashlib.sha256(ejsonl_bytes).hexdigest()
    manifest: dict[str, Any] = {
        "run_id": "lc-test-01",
        "data_file": "documents.ejsonl",
        "data_sha256": sha,
    }
    if stats_key:
        manifest["stats"] = {"unique_snapshots": len(docs)}
    else:
        manifest["document_count"] = len(docs)
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir


def test_mongo_bundle_validation_upload_order_and_idempotency(tmp_path: Path) -> None:
    doc = {
        "schema_version": {"$numberInt": "1"},
        "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
        "source_product_key": "SKU:0001",
        "source_sku": "0001",
        "composition": {"basis_text": "", "items": [], "details_markdown": "", "web_description_markdown": ""},
        "storage": {"instructions_text": ""},
        "provenance": {"captured_at": {"$date": {"$numberLong": "1791314263197"}}, "content_hash": "b" * 64},
        "extraction": {"extracted_at": {"$date": {"$numberLong": "1793863098462"}}, "status": "COMPLETE"},
    }
    run_dir = _build_mongo_bundle_dir(tmp_path, [doc], stats_key=True)
    ws = _FakeWorkspaceClient()

    res1 = sync_mongo_bundle_to_volume(workspace_client=ws, run_dir=run_dir)
    assert res1["status"] == "UPLOADED"
    assert res1["document_count"] == 1
    uploaded_paths = [p for p, _, _ in ws.files.uploaded]
    assert uploaded_paths == [
        "/Volumes/pharmaflow_dev/bronze_mongo/mongo_raw/run_id=lc-test-01/documents.ejsonl",
        "/Volumes/pharmaflow_dev/bronze_mongo/mongo_raw/run_id=lc-test-01/manifest.json",
    ]

    # Repeat call without force skips already synced bundle
    res2 = sync_mongo_bundle_to_volume(workspace_client=ws, run_dir=run_dir)
    assert res2["status"] == "SKIPPED_ALREADY_SYNCED"

    # parse_and_validate_bundle_bytes succeeds on good bundle and rejects tampered bytes
    manifest_bytes = (run_dir / "manifest.json").read_bytes()
    data_bytes = (run_dir / "documents.ejsonl").read_bytes()
    manifest, parsed = parse_and_validate_bundle_bytes(
        manifest_bytes=manifest_bytes,
        data_bytes=data_bytes,
        ingest_run_id="ingest-1",
        ingest_date=date(2026, 11, 17),
        source_object="test",
        ingested_at=datetime(2026, 11, 17, tzinfo=timezone.utc),
    )
    assert manifest["run_id"] == "lc-test-01"
    assert len(parsed) == 1

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        parse_and_validate_bundle_bytes(
            manifest_bytes=manifest_bytes,
            data_bytes=data_bytes + b" ",
            ingest_run_id="ingest-1",
            ingest_date=date(2026, 11, 17),
            source_object="test",
            ingested_at=datetime(2026, 11, 17, tzinfo=timezone.utc),
        )

    # Tamper data file on disk -> local validator catches it before upload
    (run_dir / "documents.ejsonl").write_bytes(data_bytes + b" ")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        validate_local_mongo_bundle(run_dir)


class _FakePgCursor:
    def __init__(self, table_data: dict[str, tuple[list[str], list[tuple[Any, ...]]]]) -> None:
        self._table_data = table_data
        self.description: list[tuple[str]] = []
        self._rows: list[tuple[Any, ...]] = []

    def __enter__(self) -> _FakePgCursor:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def execute(self, sql: str) -> None:
        tbl = sql.split("FROM ", 1)[1].strip()
        cols, rows = self._table_data[tbl]
        self.description = [(c,) for c in cols]
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


class _FakeTx:
    def __enter__(self) -> _FakeTx:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class _FakePgConn:
    def __init__(self, table_data: dict[str, tuple[list[str], list[tuple[Any, ...]]]]) -> None:
        self._table_data = table_data
        self.executed_sql: list[str] = []

    def transaction(self) -> _FakeTx:
        return _FakeTx()

    def execute(self, sql: str) -> None:
        self.executed_sql.append(sql)

    def cursor(self) -> _FakePgCursor:
        return _FakePgCursor(self._table_data)


def test_export_and_sync_neon_to_volume_repeatable_read() -> None:
    gz_bytes, cnt, sha = export_table_rows_to_jsonl_gz(
        ["id", "qty", "ordered_at", "local_day"],
        [(1, Decimal("2.5000"), datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc), date(2025, 1, 1))],
    )
    assert cnt == 1
    assert len(sha) == 64
    decoded = json.loads(gzip.decompress(gz_bytes).decode("utf-8").strip())
    assert decoded == {
        "id": 1,
        "qty": "2.5000",
        "ordered_at": "2025-01-01T12:00:00Z",
        "local_day": "2025-01-01",
    }

    conn = _FakePgConn(
        {
            "org.store": (["store_id", "store_code"], [(5389, "SIM_IRPD")]),
            "org.warehouse": (["warehouse_id", "store_id"], [(1, 5389)]),
        }
    )
    ws = _FakeWorkspaceClient()
    specs = resolve_tables("org.store,org.warehouse")
    res = sync_neon_tables_to_volume(
        pg_conn=conn,
        workspace_client=ws,
        tables=specs,
        run_id="pgvol-test-1",
    )
    assert "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY" in conn.executed_sql
    assert res["status"] == "UPLOADED"
    uploaded_paths = [p for p, _, _ in ws.files.uploaded]
    assert uploaded_paths == [
        "/Volumes/pharmaflow_dev/bronze_pg/pg_raw/run_id=pgvol-test-1/org__store.jsonl.gz",
        "/Volumes/pharmaflow_dev/bronze_pg/pg_raw/run_id=pgvol-test-1/org__warehouse.jsonl.gz",
        "/Volumes/pharmaflow_dev/bronze_pg/pg_raw/run_id=pgvol-test-1/manifest.json",
    ]
    manifest = json.loads(ws.files.storage[uploaded_paths[-1]].decode("utf-8"))
    assert manifest["tables"]["org.store"]["row_count"] == 1
    assert manifest["tables"]["org.warehouse"]["row_count"] == 1
