"""AWS Lambda handler for delta syncing accepted S3 weather files into a Databricks Managed Volume.

Uses only Python stdlib (``urllib.request``) and AWS Lambda's built-in ``boto3`` runtime so it deploys
as a lightweight standalone Lambda without modifying ``src/weather/`` ingestion packages.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo

import boto3

RAW_PREFIX_ROOT = "raw/open_meteo/"
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

MODE_PREFIXES: dict[str, tuple[str, ...]] = {
    "daily": ("raw/open_meteo/weather_forecast/",),
    "historical": (
        "raw/open_meteo/historical_forecast/",
        "raw/open_meteo/historical_weather/",
    ),
    "all": (
        "raw/open_meteo/weather_forecast/",
        "raw/open_meteo/historical_forecast/",
        "raw/open_meteo/historical_weather/",
    ),
}

_SSM_CACHE: dict[str, str] = {}


def clean_databricks_host(raw_host: str) -> str:
    trimmed = raw_host.strip()
    parts = urllib.parse.urlsplit(trimmed)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return trimmed.rstrip("/")


def volume_root_path(catalog: str, schema: str, volume: str) -> str:
    return f"/Volumes/{catalog}/{schema}/{volume}"


def s3_key_to_volume_path(s3_key: str, *, volume_root: str) -> str:
    if not isinstance(s3_key, str) or not s3_key.startswith(RAW_PREFIX_ROOT):
        raise ValueError(f"Expected S3 key under {RAW_PREFIX_ROOT!r}, got {s3_key!r}")
    if "\\" in s3_key or ".." in PurePosixPath(s3_key).parts:
        raise ValueError(f"Unsafe S3 key: {s3_key!r}")
    return f"{volume_root.rstrip('/')}/{s3_key[len('raw/'):]}"


def _state_path(volume_root: str) -> str:
    return f"{volume_root.rstrip('/')}/_sync_state/manifest.json"


def _recent_vn_dates(recent_days: int, *, now_utc: datetime | None = None) -> list[str]:
    now_vn = (now_utc or datetime.now(timezone.utc)).astimezone(VN_TZ).date()
    return [(now_vn - timedelta(days=offset)).isoformat() for offset in range(max(1, recent_days))]


class DatabricksFilesHttpClient:
    """Minimal Databricks Files REST API client using Python stdlib ``urllib``."""

    def __init__(self, *, host: str, token: str, timeout_s: float = 30.0) -> None:
        self.host = clean_databricks_host(host)
        self._token = token
        self.timeout_s = timeout_s

    def _file_url(self, volume_path: str, *, query: str = "") -> str:
        encoded = urllib.parse.quote(volume_path, safe="/")
        base = f"{self.host}/api/2.0/fs/files{encoded}"
        return f"{base}?{query}" if query else base

    def download(self, volume_path: str) -> bytes:
        req = urllib.request.Request(
            self._file_url(volume_path),
            headers={"Authorization": f"Bearer {self._token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise FileNotFoundError(volume_path) from exc
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"Databricks download HTTP {exc.code}: {detail}") from exc

    def upload(self, volume_path: str, data: bytes, *, overwrite: bool = True, max_attempts: int = 3) -> None:
        query = "overwrite=true" if overwrite else "overwrite=false"
        url = self._file_url(volume_path, query=query)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/octet-stream",
        }
        for attempt in range(1, max_attempts + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s):
                    return
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
                if exc.code in (429, 500, 502, 503, 504) and attempt < max_attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise RuntimeError(f"Databricks upload HTTP {exc.code} for {volume_path}: {detail}") from exc
            except urllib.error.URLError:
                if attempt < max_attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise


def _read_ssm_secret(param_name: str, *, ssm_client: Any | None = None) -> str:
    if param_name in _SSM_CACHE:
        return _SSM_CACHE[param_name]
    client = ssm_client or boto3.client("ssm")
    resp = client.get_parameter(Name=param_name, WithDecryption=True)
    value = resp["Parameter"]["Value"]
    _SSM_CACHE[param_name] = value
    return value


def _scan_search_prefixes(
    *,
    mode: str,
    ingest_date: str | None = None,
    recent_days: int | None = None,
    run_id: str | None = None,
    now_utc: datetime | None = None,
) -> list[str]:
    if mode not in MODE_PREFIXES:
        raise ValueError(f"Unsupported mode {mode!r}; expected one of {tuple(MODE_PREFIXES)}")
    base_prefixes = MODE_PREFIXES[mode]
    if ingest_date:
        dates = [ingest_date]
    elif recent_days:
        dates = _recent_vn_dates(int(recent_days), now_utc=now_utc)
    else:
        return list(base_prefixes)

    out: list[str] = []
    for base in base_prefixes:
        for d in dates:
            prefix = f"{base}ingest_date={d}/"
            if run_id:
                prefix = f"{prefix}run_id={run_id}/"
            out.append(prefix)
    return out


def sync_recent_objects(
    *,
    s3_client: Any,
    files_client: DatabricksFilesHttpClient,
    bucket: str,
    volume_root: str,
    mode: str = "daily",
    ingest_date: str | None = None,
    recent_days: int | None = None,
    run_id: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    max_workers: int = 12,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    state_path = _state_path(volume_root)
    if force:
        state: dict[str, dict[str, Any]] = {}
    else:
        try:
            state_doc = json.loads(files_client.download(state_path).decode("utf-8"))
            raw_objects = state_doc.get("objects")
            state = dict(raw_objects) if isinstance(raw_objects, dict) else {}
        except FileNotFoundError:
            state = {}

    def _is_done(key: str, etag: str | None) -> bool:
        if force:
            return False
        rec = state.get(key)
        if not isinstance(rec, Mapping):
            return False
        if etag and rec.get("etag"):
            return rec.get("etag") == etag
        return True

    search_prefixes = _scan_search_prefixes(
        mode=mode,
        ingest_date=ingest_date,
        recent_days=recent_days,
        run_id=run_id,
        now_utc=now_utc,
    )
    paginator = s3_client.get_paginator("list_objects_v2")
    run_filter = f"/run_id={run_id}/" if run_id else None

    pending_accepted: list[dict[str, Any]] = []
    candidates: dict[str, tuple[str, str | None]] = {}

    for prefix in search_prefixes:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if run_filter and run_filter not in key:
                    continue
                if key.endswith("/accepted.json"):
                    if not _is_done(key, obj.get("ETag")):
                        pending_accepted.append(obj)
                elif key.endswith("/store_grid_mapping.json") or ("/summary/" in key and key.endswith(".json")):
                    if not _is_done(key, obj.get("ETag")):
                        candidates[key] = (s3_key_to_volume_path(key, volume_root=volume_root), obj.get("ETag"))

    def _read_accepted(obj: Mapping[str, Any]) -> tuple[str, str | None, dict[str, Any]]:
        body = s3_client.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
        return obj["Key"], obj.get("ETag"), json.loads(body.decode("utf-8"))

    if pending_accepted:
        workers = max(1, min(max_workers, len(pending_accepted)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fut in as_completed([pool.submit(_read_accepted, obj) for obj in pending_accepted]):
                acc_key, acc_etag, payload = fut.result()
                resp_key = payload.get("response_key")
                meta_key = payload.get("metadata_key")
                for k, etag in ((resp_key, None), (meta_key, None), (acc_key, acc_etag)):
                    if not isinstance(k, str) or not k.startswith(RAW_PREFIX_ROOT):
                        raise ValueError(f"{acc_key}: invalid target key {k!r}")
                    if not _is_done(k, etag):
                        candidates.setdefault(k, (s3_key_to_volume_path(k, volume_root=volume_root), etag))

    non_manifests = sorted((k, v) for k, v in candidates.items() if not k.endswith("/accepted.json"))
    manifests = sorted((k, v) for k, v in candidates.items() if k.endswith("/accepted.json"))
    total_pending = len(non_manifests) + len(manifests)

    if dry_run or total_pending == 0:
        return {
            "mode": mode,
            "search_prefixes": search_prefixes,
            "dry_run": dry_run,
            "pending_count": total_pending,
            "uploaded_count": 0,
            "error_count": 0,
            "state_tracked_count": len(state),
        }

    uploaded = 0
    errors: list[dict[str, str]] = []
    synced_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _transfer(s3_key: str, vol_path: str, etag: str | None) -> tuple[str, dict[str, Any]]:
        obj = s3_client.get_object(Bucket=bucket, Key=s3_key)
        raw = obj["Body"].read()
        files_client.upload(vol_path, raw, overwrite=True)
        return s3_key, {
            "etag": etag or obj.get("ETag"),
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "synced_at_utc": synced_ts,
        }

    for batch in (non_manifests, manifests):
        if not batch:
            continue
        workers = max(1, min(max_workers, len(batch)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(_transfer, k, vp, etag): k for k, (vp, etag) in batch}
            for fut in as_completed(futs):
                s3_key = futs[fut]
                try:
                    k, meta = fut.result()
                    state[k] = meta
                    uploaded += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append({"s3_key": s3_key, "error": f"{type(exc).__name__}: {exc}"})

    if uploaded > 0:
        manifest_bytes = json.dumps(
            {
                "schema_version": "1",
                "updated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "object_count": len(state),
                "objects": state,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        files_client.upload(state_path, manifest_bytes, overwrite=True)

    return {
        "mode": mode,
        "search_prefixes": search_prefixes,
        "dry_run": False,
        "pending_count": total_pending,
        "uploaded_count": uploaded,
        "error_count": len(errors),
        "errors": errors[:20],
        "state_tracked_count": len(state),
    }


def lambda_handler(event: Mapping[str, Any] | None, context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for EventBridge Scheduler and manual invocations."""
    ev = dict(event or {})
    if ev.get("dry_run") and ev.get("smoke"):
        return {
            "ok": True,
            "handler": "databricks_volume_sync",
            "bucket": os.environ["WEATHER_S3_BUCKET"],
            "volume_root": volume_root_path(
                os.environ.get("DATABRICKS_CATALOG", "pharmaflow_dev"),
                os.environ.get("DATABRICKS_SCHEMA", "bronze_weather"),
                os.environ.get("DATABRICKS_VOLUME", "weather_raw"),
            ),
        }

    bucket = os.environ["WEATHER_S3_BUCKET"]
    host = os.environ["DATABRICKS_HOST"]
    token_param = os.environ["DATABRICKS_TOKEN_PARAM"]
    token = _read_ssm_secret(token_param)
    vol_root = volume_root_path(
        os.environ.get("DATABRICKS_CATALOG", "pharmaflow_dev"),
        os.environ.get("DATABRICKS_SCHEMA", "bronze_weather"),
        os.environ.get("DATABRICKS_VOLUME", "weather_raw"),
    )

    result = sync_recent_objects(
        s3_client=boto3.client("s3"),
        files_client=DatabricksFilesHttpClient(host=host, token=token),
        bucket=bucket,
        volume_root=vol_root,
        mode=str(ev.get("mode", "daily")),
        ingest_date=ev.get("ingest_date"),
        recent_days=ev.get("recent_days"),
        run_id=ev.get("run_id"),
        dry_run=bool(ev.get("dry_run", False)),
        force=bool(ev.get("force", False)),
        max_workers=int(ev.get("max_workers", 12)),
    )
    print(json.dumps({"event": "databricks_volume_sync", **{k: v for k, v in result.items() if k != "errors"}}))
    if result["error_count"] > 0:
        raise RuntimeError(f"databricks_volume_sync failed for {result['error_count']} objects: {result['errors'][:3]}")
    return result
