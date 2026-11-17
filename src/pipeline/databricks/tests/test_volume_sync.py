"""Offline unit tests for S3 -> Databricks Managed Volume delta sync."""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from databricks.sdk.errors import NotFound

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from src.bronze.sync_s3_to_volume import (  # noqa: E402
    clean_databricks_host,
    discover_sync_candidates,
    extract_accepted_keys,
    s3_key_to_volume_path,
    sync_s3_to_databricks_volume,
)


class _FakePaginator:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self._objects = objects

    def paginate(self, *, Bucket: str, Prefix: str):  # noqa: N803
        contents = [
            {
                "Key": k,
                "ETag": f'"{hashlib.md5(v).hexdigest()}"',
                "Size": len(v),
            }
            for k, v in sorted(self._objects.items())
            if k.startswith(Prefix)
        ]
        yield {"Contents": contents}


class _FakeS3Client:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = dict(objects)

    def get_paginator(self, name: str) -> _FakePaginator:
        assert name == "list_objects_v2"
        return _FakePaginator(self.objects)

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        return {
            "Body": io.BytesIO(self.objects[Key]),
            "ETag": f'"{hashlib.md5(self.objects[Key]).hexdigest()}"',
        }


class _FakeFilesAPI:
    def __init__(self) -> None:
        self.storage: dict[str, bytes] = {}
        self.upload_order: list[str] = []

    def download(self, file_path: str):
        if file_path not in self.storage:
            raise NotFound("NOT_FOUND")
        return type("Resp", (), {"contents": io.BytesIO(self.storage[file_path])})()

    def upload(self, file_path: str, contents: io.BytesIO, *, overwrite: bool = False) -> None:
        if not overwrite and file_path in self.storage:
            raise FileExistsError(file_path)
        self.storage[file_path] = contents.read()
        self.upload_order.append(file_path)


class _FakeWorkspaceClient:
    def __init__(self) -> None:
        self.files = _FakeFilesAPI()


def _make_run_objects() -> dict[str, bytes]:
    run_prefix = "raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=daily-20261118-abc12345"
    resp_bytes = b'{"hourly":{"time":[1700000000]}}'
    meta_bytes = b'{"run_id":"daily-20261118-abc12345","task_id":"t1"}'
    sha = hashlib.sha256(resp_bytes).hexdigest()
    resp_key = f"{run_prefix}/tasks/t1/attempts/att-1/response.json"
    meta_key = f"{run_prefix}/tasks/t1/attempts/att-1/metadata.json"
    acc_key = f"{run_prefix}/tasks/t1/accepted.json"
    acc_bytes = json.dumps(
        {
            "schema_version": "1",
            "run_id": "daily-20261118-abc12345",
            "task_id": "t1",
            "raw_sha256": sha,
            "response_key": resp_key,
            "metadata_key": meta_key,
        }
    ).encode("utf-8")

    return {
        acc_key: acc_bytes,
        resp_key: resp_bytes,
        meta_key: meta_bytes,
        f"{run_prefix}/tasks/t1/attempts/att-failed/response.json": b'{"error":true}',
        f"{run_prefix}/tasks/orphan_garbage.json": b"{}",
        f"{run_prefix}/store_grid_mapping.json": b'{"mappings":[]}',
        f"{run_prefix}/summary/abc12345.json": b'{"run_status":"SUCCEEDED"}',
    }


def test_clean_host_and_path_mapping() -> None:
    assert (
        clean_databricks_host("https://dbc-46e38b03-6d3f.cloud.databricks.com/?o=7474659777573848")
        == "https://dbc-46e38b03-6d3f.cloud.databricks.com"
    )
    assert (
        s3_key_to_volume_path(
            "raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=r1/tasks/t1/accepted.json",
            volume_root="/Volumes/pharmaflow_dev/bronze_weather/weather_raw",
        )
        == "/Volumes/pharmaflow_dev/bronze_weather/weather_raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=r1/tasks/t1/accepted.json"
    )
    with pytest.raises(ValueError):
        s3_key_to_volume_path("other/key.json", volume_root="/Volumes/c/s/v")


def test_extract_accepted_rejects_bad_manifest() -> None:
    with pytest.raises(ValueError):
        extract_accepted_keys(
            {"response_key": "bad/key", "metadata_key": "raw/open_meteo/m.json", "raw_sha256": "a" * 64},
            "k",
        )


def test_discover_ignores_failed_attempts_and_orphans() -> None:
    objs = _make_run_objects()
    s3 = _FakeS3Client(objs)
    candidates = discover_sync_candidates(
        s3,
        "bucket",
        ["raw/open_meteo/weather_forecast/"],
        volume_root="/Volumes/pharmaflow_dev/bronze_weather/weather_raw",
    )
    keys = [c.s3_key for c in candidates]
    assert all("att-failed" not in k and "orphan_garbage" not in k for k in keys)
    assert len(keys) == 5
    assert keys[-1].endswith("/accepted.json")


def test_sync_is_idempotent_with_volume_manifest() -> None:
    objs = _make_run_objects()
    s3 = _FakeS3Client(objs)
    w = _FakeWorkspaceClient()

    first = sync_s3_to_databricks_volume(s3_client=s3, workspace_client=w, bucket="bucket", mode="daily")
    assert first["uploaded_count"] == 5
    assert first["error_count"] == 0
    assert w.files.upload_order[-2].endswith("/accepted.json")

    second = sync_s3_to_databricks_volume(s3_client=s3, workspace_client=w, bucket="bucket", mode="daily")
    assert second["pending_count"] == 0
    assert second["uploaded_count"] == 0


def test_sync_periodic_checkpoint_flushes_state_before_completion() -> None:
    objs = _make_run_objects()
    s3 = _FakeS3Client(objs)
    w = _FakeWorkspaceClient()

    res = sync_s3_to_databricks_volume(
        s3_client=s3,
        workspace_client=w,
        bucket="bucket",
        mode="daily",
        max_workers=1,
        checkpoint_every=2,
    )
    assert res["uploaded_count"] == 5
    manifest_uploads = [p for p in w.files.upload_order if p.endswith("/_sync_state/manifest.json")]
    assert len(manifest_uploads) == 3
    acc_idx = w.files.upload_order.index(
        "/Volumes/pharmaflow_dev/bronze_weather/weather_raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=daily-20261118-abc12345/tasks/t1/accepted.json"
    )
    resp_idx = w.files.upload_order.index(
        "/Volumes/pharmaflow_dev/bronze_weather/weather_raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=daily-20261118-abc12345/tasks/t1/attempts/att-1/response.json"
    )
    assert resp_idx < acc_idx
