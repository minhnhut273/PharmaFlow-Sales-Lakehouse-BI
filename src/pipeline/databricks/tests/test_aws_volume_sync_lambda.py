"""Offline unit tests for AWS Lambda S3 -> Databricks Volume bridge."""

from __future__ import annotations

import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from src.bronze.aws_volume_sync_lambda import (  # noqa: E402
    _scan_search_prefixes,
    sync_recent_objects,
)


class _FakePaginator:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self._objects = objects

    def paginate(self, *, Bucket: str, Prefix: str):  # noqa: N803
        yield {
            "Contents": [
                {"Key": k, "ETag": f'"{hashlib.md5(v).hexdigest()}"', "Size": len(v)}
                for k, v in sorted(self._objects.items())
                if k.startswith(Prefix)
            ]
        }


class _FakeS3:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def get_paginator(self, name: str) -> _FakePaginator:
        assert name == "list_objects_v2"
        return _FakePaginator(self.objects)

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        return {"Body": io.BytesIO(self.objects[Key]), "ETag": f'"{hashlib.md5(self.objects[Key]).hexdigest()}"'}


class _FakeFilesHttp:
    def __init__(self) -> None:
        self.storage: dict[str, bytes] = {}
        self.uploads: list[str] = []

    def download(self, volume_path: str) -> bytes:
        if volume_path not in self.storage:
            raise FileNotFoundError(volume_path)
        return self.storage[volume_path]

    def upload(self, volume_path: str, data: bytes, *, overwrite: bool = True) -> None:
        self.storage[volume_path] = data
        self.uploads.append(volume_path)


def test_scan_search_prefixes_recent_days_vn() -> None:
    now_utc = datetime(2026, 11, 17, 23, 18, tzinfo=timezone.utc)  # 2026-11-18 06:18 VN
    prefixes = _scan_search_prefixes(mode="daily", recent_days=2, now_utc=now_utc)
    assert prefixes == [
        "raw/open_meteo/weather_forecast/ingest_date=2026-11-18/",
        "raw/open_meteo/weather_forecast/ingest_date=2026-11-17/",
    ]


def test_lambda_sync_recent_objects_two_phase_and_idempotent() -> None:
    run_prefix = "raw/open_meteo/weather_forecast/ingest_date=2026-11-18/run_id=daily-20261118-aa"
    resp_b = b'{"hourly":{"time":[1]}}'
    meta_b = b'{"run_id":"daily-20261118-aa"}'
    acc_b = json.dumps(
        {
            "raw_sha256": hashlib.sha256(resp_b).hexdigest(),
            "response_key": f"{run_prefix}/tasks/t1/attempts/a1/response.json",
            "metadata_key": f"{run_prefix}/tasks/t1/attempts/a1/metadata.json",
        }
    ).encode("utf-8")
    objs = {
        f"{run_prefix}/tasks/t1/accepted.json": acc_b,
        f"{run_prefix}/tasks/t1/attempts/a1/response.json": resp_b,
        f"{run_prefix}/tasks/t1/attempts/a1/metadata.json": meta_b,
        f"{run_prefix}/store_grid_mapping.json": b'{"mappings":[]}',
        f"{run_prefix}/tasks/t1/attempts/bad/response.json": b"{}",
    }
    s3 = _FakeS3(objs)
    files_http = _FakeFilesHttp()

    res1 = sync_recent_objects(
        s3_client=s3,
        files_client=files_http,
        bucket="b",
        volume_root="/Volumes/pharmaflow_dev/bronze_weather/weather_raw",
        mode="daily",
        recent_days=2,
        now_utc=datetime(2026, 11, 17, 23, 18, tzinfo=timezone.utc),
    )
    assert res1["uploaded_count"] == 4
    assert res1["error_count"] == 0
    assert files_http.uploads[-2].endswith("/accepted.json")

    res2 = sync_recent_objects(
        s3_client=s3,
        files_client=files_http,
        bucket="b",
        volume_root="/Volumes/pharmaflow_dev/bronze_weather/weather_raw",
        mode="daily",
        recent_days=2,
        now_utc=datetime(2026, 11, 17, 23, 18, tzinfo=timezone.utc),
    )
    assert res2["pending_count"] == 0
    assert res2["uploaded_count"] == 0
