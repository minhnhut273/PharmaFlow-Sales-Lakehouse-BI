"""Delta sync of accepted AWS S3 weather files to a Databricks Managed Volume."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import boto3
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from dotenv import load_dotenv

DEFAULT_CATALOG = "pharmaflow_dev"
DEFAULT_SCHEMA = "bronze_weather"
DEFAULT_VOLUME = "weather_raw"
RAW_PREFIX_ROOT = "raw/open_meteo/"

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


@dataclass(frozen=True)
class SyncCandidate:
    s3_key: str
    volume_path: str
    etag: str | None = None
    size: int | None = None


def clean_databricks_host(raw_host: str) -> str:
    """Strip workspace query strings like ``/?o=...`` from Workspace URLs."""
    trimmed = raw_host.strip()
    parts = urlsplit(trimmed)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return trimmed.rstrip("/")


def volume_root_path(
    catalog: str = DEFAULT_CATALOG,
    schema: str = DEFAULT_SCHEMA,
    volume: str = DEFAULT_VOLUME,
) -> str:
    return f"/Volumes/{catalog}/{schema}/{volume}"


def prefixes_for_sync_mode(mode: str) -> tuple[str, ...]:
    if mode not in MODE_PREFIXES:
        raise ValueError(f"Unsupported sync mode {mode!r}; expected one of {tuple(MODE_PREFIXES)}")
    return MODE_PREFIXES[mode]


def s3_key_to_volume_path(s3_key: str, *, volume_root: str) -> str:
    """Map canonical S3 key ``raw/open_meteo/...`` to ``<volume_root>/open_meteo/...``."""
    if not isinstance(s3_key, str) or not s3_key.startswith(RAW_PREFIX_ROOT):
        raise ValueError(f"Expected S3 key under {RAW_PREFIX_ROOT!r}, got {s3_key!r}")
    if "\\" in s3_key or ".." in PurePosixPath(s3_key).parts:
        raise ValueError(f"Unsafe S3 key: {s3_key!r}")
    rel_under_raw = s3_key[len("raw/") :]
    return f"{volume_root.rstrip('/')}/{rel_under_raw}"


def extract_accepted_keys(accepted_payload: Mapping[str, Any], accepted_key: str) -> tuple[str, str, str]:
    """Validate an ``accepted.json`` manifest and return ``(accepted_key, response_key, metadata_key)``."""
    response_key = accepted_payload.get("response_key")
    metadata_key = accepted_payload.get("metadata_key")
    raw_sha256 = accepted_payload.get("raw_sha256")
    if not isinstance(response_key, str) or not response_key.startswith(RAW_PREFIX_ROOT):
        raise ValueError(f"{accepted_key}: invalid response_key {response_key!r}")
    if not isinstance(metadata_key, str) or not metadata_key.startswith(RAW_PREFIX_ROOT):
        raise ValueError(f"{accepted_key}: invalid metadata_key {metadata_key!r}")
    if not isinstance(raw_sha256, str) or len(raw_sha256) != 64:
        raise ValueError(f"{accepted_key}: invalid raw_sha256 {raw_sha256!r}")
    return accepted_key, response_key, metadata_key


def _scan_prefixes(
    s3_client: Any,
    bucket: str,
    prefixes: Sequence[str],
    *,
    ingest_date: str | None = None,
    run_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """List accepted manifests plus run-level ``store_grid_mapping.json`` and ``summary/*.json``."""
    paginator = s3_client.get_paginator("list_objects_v2")
    accepted_objs: list[dict[str, Any]] = []
    run_artifact_objs: list[dict[str, Any]] = []

    run_filter = f"/run_id={run_id}/" if run_id else None
    for base_prefix in prefixes:
        search_prefix = f"{base_prefix}ingest_date={ingest_date}/" if ingest_date else base_prefix
        if ingest_date and run_id:
            search_prefix = f"{search_prefix}run_id={run_id}/"
        for page in paginator.paginate(Bucket=bucket, Prefix=search_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if run_filter and run_filter not in key:
                    continue
                if key.endswith("/accepted.json"):
                    accepted_objs.append(obj)
                elif key.endswith("/store_grid_mapping.json") or ("/summary/" in key and key.endswith(".json")):
                    run_artifact_objs.append(obj)
    return accepted_objs, run_artifact_objs


def discover_sync_candidates(
    s3_client: Any,
    bucket: str,
    prefixes: Sequence[str],
    *,
    volume_root: str,
    ingest_date: str | None = None,
    run_id: str | None = None,
    max_workers: int = 12,
    already_synced: Mapping[str, Any] | None = None,
    force: bool = False,
) -> list[SyncCandidate]:
    """Return deduplicated S3 keys (``accepted.json``, paired response/metadata, mapping, summary) to upload."""
    accepted_objs, run_artifact_objs = _scan_prefixes(
        s3_client, bucket, prefixes, ingest_date=ingest_date, run_id=run_id
    )
    synced_map = already_synced or {}

    def _is_done(key: str, etag: str | None) -> bool:
        if force:
            return False
        rec = synced_map.get(key)
        if not isinstance(rec, Mapping):
            return False
        if etag and rec.get("etag"):
            return rec.get("etag") == etag
        return True

    pending_accepted = [obj for obj in accepted_objs if not _is_done(obj["Key"], obj.get("ETag"))]
    candidates_by_key: dict[str, SyncCandidate] = {}
    for obj in run_artifact_objs:
        key = obj["Key"]
        etag = obj.get("ETag")
        if _is_done(key, etag):
            continue
        candidates_by_key[key] = SyncCandidate(
            s3_key=key,
            volume_path=s3_key_to_volume_path(key, volume_root=volume_root),
            etag=etag,
            size=obj.get("Size"),
        )

    def _fetch_accepted(obj: Mapping[str, Any]) -> tuple[dict[str, Any], Mapping[str, Any]]:
        body = s3_client.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
        return json.loads(body.decode("utf-8")), obj

    if pending_accepted:
        workers = max(1, min(max_workers, len(pending_accepted)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_fetch_accepted, obj) for obj in pending_accepted]
            for fut in as_completed(futures):
                payload, acc_obj = fut.result()
                acc_key, resp_key, meta_key = extract_accepted_keys(payload, acc_obj["Key"])
                for key, etag, size in (
                    (resp_key, None, None),
                    (meta_key, None, None),
                    (acc_key, acc_obj.get("ETag"), acc_obj.get("Size")),
                ):
                    if _is_done(key, etag):
                        continue
                    candidates_by_key.setdefault(
                        key,
                        SyncCandidate(
                            s3_key=key,
                            volume_path=s3_key_to_volume_path(key, volume_root=volume_root),
                            etag=etag,
                            size=size,
                        ),
                    )

    non_manifest = [c for k, c in sorted(candidates_by_key.items()) if not k.endswith("/accepted.json")]
    manifests = [c for k, c in sorted(candidates_by_key.items()) if k.endswith("/accepted.json")]
    return non_manifest + manifests


def _state_path(volume_root: str) -> str:
    return f"{volume_root.rstrip('/')}/_sync_state/manifest.json"


def load_volume_sync_state(w: Any, volume_root: str) -> dict[str, dict[str, Any]]:
    path = _state_path(volume_root)
    try:
        resp = w.files.download(path)
        raw = resp.contents.read()
        data = json.loads(raw.decode("utf-8"))
        entries = data.get("objects")
        return dict(entries) if isinstance(entries, dict) else {}
    except NotFound:
        return {}
    except Exception as exc:  # noqa: BLE001
        if "NOT_FOUND" in str(exc) or "404" in str(exc):
            return {}
        raise


def save_volume_sync_state(w: Any, volume_root: str, objects: Mapping[str, dict[str, Any]]) -> None:
    payload = json.dumps(
        {
            "schema_version": "1",
            "updated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "object_count": len(objects),
            "objects": dict(objects),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    w.files.upload(_state_path(volume_root), io.BytesIO(payload), overwrite=True)


def sync_s3_to_databricks_volume(
    *,
    s3_client: Any,
    workspace_client: Any,
    bucket: str,
    mode: str = "daily",
    catalog: str = DEFAULT_CATALOG,
    schema: str = DEFAULT_SCHEMA,
    volume: str = DEFAULT_VOLUME,
    ingest_date: str | None = None,
    run_id: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    max_workers: int = 12,
    verify_sha256: bool = True,
    checkpoint_every: int = 250,
) -> dict[str, Any]:
    """Mirror newly accepted S3 Weather objects into Databricks Unity Catalog Managed Volume."""
    vol_root = volume_root_path(catalog=catalog, schema=schema, volume=volume)
    prefixes = prefixes_for_sync_mode(mode)
    state = load_volume_sync_state(workspace_client, vol_root) if not force else {}

    candidates = discover_sync_candidates(
        s3_client,
        bucket,
        prefixes,
        volume_root=vol_root,
        ingest_date=ingest_date,
        run_id=run_id,
        max_workers=max_workers,
        already_synced=state,
        force=force,
    )

    if dry_run or not candidates:
        return {
            "mode": mode,
            "bucket": bucket,
            "volume_root": vol_root,
            "dry_run": dry_run,
            "pending_count": len(candidates),
            "uploaded_count": 0,
            "error_count": 0,
            "state_tracked_count": len(state),
            "sample_keys": [c.s3_key for c in candidates[:10]],
        }

    non_manifests = [c for c in candidates if not c.s3_key.endswith("/accepted.json")]
    manifests = [c for c in candidates if c.s3_key.endswith("/accepted.json")]

    uploaded = 0
    since_last_ckpt = 0
    errors: list[dict[str, str]] = []
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _transfer_one(cand: SyncCandidate) -> tuple[str, dict[str, Any]]:
        obj = s3_client.get_object(Bucket=bucket, Key=cand.s3_key)
        raw = obj["Body"].read()
        sha = hashlib.sha256(raw).hexdigest() if verify_sha256 else None
        workspace_client.files.upload(cand.volume_path, io.BytesIO(raw), overwrite=True)
        return cand.s3_key, {
            "etag": cand.etag or obj.get("ETag"),
            "size": len(raw),
            "sha256": sha,
            "synced_at_utc": now_utc,
        }

    for phase_batch in (non_manifests, manifests):
        if not phase_batch:
            continue
        workers = max(1, min(max_workers, len(phase_batch)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(_transfer_one, c): c for c in phase_batch}
            for fut in as_completed(futs):
                cand = futs[fut]
                try:
                    key, meta = fut.result()
                    state[key] = meta
                    uploaded += 1
                    since_last_ckpt += 1
                    if checkpoint_every > 0 and since_last_ckpt >= checkpoint_every:
                        save_volume_sync_state(workspace_client, vol_root, state)
                        since_last_ckpt = 0
                except Exception as exc:  # noqa: BLE001
                    errors.append({"s3_key": cand.s3_key, "error": f"{type(exc).__name__}: {exc}"})

    if since_last_ckpt > 0:
        save_volume_sync_state(workspace_client, vol_root, state)

    return {
        "mode": mode,
        "bucket": bucket,
        "volume_root": vol_root,
        "dry_run": False,
        "pending_count": len(candidates),
        "uploaded_count": uploaded,
        "error_count": len(errors),
        "errors": errors[:20],
        "state_tracked_count": len(state),
    }


def build_clients_from_env(dotenv_path: Path | str | None = None) -> tuple[Any, WorkspaceClient, str]:
    """Create authenticated S3 client, Databricks WorkspaceClient, and bucket name from ``.env``."""
    resolved_dotenv = dotenv_path or (Path(__file__).resolve().parents[5] / ".env")
    load_dotenv(resolved_dotenv, override=False)
    profile = os.environ.get("WEATHER_AWS_PROFILE") or None
    region = os.environ.get("WEATHER_S3_REGION", "ap-southeast-1")
    bucket = os.environ.get("WEATHER_S3_BUCKET")
    if not bucket:
        raise ValueError("WEATHER_S3_BUCKET must be set in environment or .env")

    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")
    if not host or not token:
        raise ValueError("DATABRICKS_HOST and DATABRICKS_TOKEN must be set in environment or .env")

    session = boto3.Session(profile_name=profile, region_name=region)
    s3_client = session.client("s3")
    w = WorkspaceClient(host=clean_databricks_host(host), token=token)
    return s3_client, w, bucket


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("daily", "historical", "all"), default="daily")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--volume", default=DEFAULT_VOLUME)
    parser.add_argument("--ingest-date", default=None, help="Optional YYYY-MM-DD partition filter.")
    parser.add_argument("--run-id", default=None, help="Optional run_id filter.")
    parser.add_argument("--max-workers", type=int, default=12)
    parser.add_argument("--checkpoint-every", type=int, default=250)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Ignore existing sync manifest and re-upload.")
    parser.add_argument("--dotenv", default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    s3_client, workspace_client, bucket = build_clients_from_env(args.dotenv)
    result = sync_s3_to_databricks_volume(
        s3_client=s3_client,
        workspace_client=workspace_client,
        bucket=bucket,
        mode=args.mode,
        catalog=args.catalog,
        schema=args.schema,
        volume=args.volume,
        ingest_date=args.ingest_date,
        run_id=args.run_id,
        dry_run=args.dry_run,
        force=args.force,
        max_workers=args.max_workers,
        checkpoint_every=args.checkpoint_every,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("error_count", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
