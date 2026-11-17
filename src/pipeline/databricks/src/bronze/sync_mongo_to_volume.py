"""Upload validated MongoDB snapshot bundles to Databricks Unity Catalog Managed Volume."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_PKG_ROOT = Path(__file__).resolve().parents[2]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from src.common.workspace import build_workspace_client_from_env, read_remote_json  # noqa: E402

DEFAULT_CATALOG = "pharmaflow_dev"
DEFAULT_SCHEMA = "bronze_mongo"
DEFAULT_VOLUME = "mongo_raw"
DEFAULT_RUNS_ROOT = Path(__file__).resolve().parents[5] / "src" / "synthetic_data_source" / "mongodb" / "runs"


def discover_latest_mongo_run_dir(runs_root: Path | str = DEFAULT_RUNS_ROOT) -> Path:
    """Return the latest valid Mongo snapshot run directory under ``runs_root``."""
    root = Path(runs_root)
    if not root.exists():
        raise FileNotFoundError(f"Mongo runs directory does not exist: {root}")
    candidates = sorted(
        (p for p in root.iterdir() if p.is_dir() and (p / "manifest.json").is_file()),
        key=lambda p: p.name,
    )
    if not candidates:
        raise FileNotFoundError(f"No Mongo snapshot run directories with manifest.json found under {root}")
    return candidates[-1]


def validate_local_mongo_bundle(run_dir: Path | str) -> tuple[dict[str, Any], Path, bytes, bytes]:
    """Validate local ``manifest.json`` against its ``data_file`` SHA-256 and document count."""
    base = Path(run_dir)
    manifest_path = base / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing manifest.json in {base}")

    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    run_id = manifest.get("run_id")
    data_file = manifest.get("data_file")
    expected_sha = manifest.get("data_sha256")
    raw_stats = manifest.get("stats") if isinstance(manifest.get("stats"), dict) else {}
    expected_count = manifest.get("document_count")
    if expected_count is None:
        expected_count = raw_stats.get("unique_snapshots")

    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError(f"Invalid manifest run_id in {manifest_path}")
    if not isinstance(data_file, str) or "/" in data_file or "\\" in data_file:
        raise ValueError(f"Invalid manifest data_file {data_file!r} in {manifest_path}")
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise ValueError(f"Invalid manifest data_sha256 in {manifest_path}")
    if not isinstance(expected_count, int) or expected_count <= 0:
        raise ValueError(f"Invalid manifest snapshot count {expected_count!r} in {manifest_path}")

    data_path = base / data_file
    if not data_path.is_file():
        raise FileNotFoundError(f"Missing data file {data_path}")

    data_bytes = data_path.read_bytes()
    actual_sha = hashlib.sha256(data_bytes).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError(f"SHA-256 mismatch for {data_path}: expected {expected_sha}, got {actual_sha}")

    actual_count = sum(1 for line in data_bytes.splitlines() if line.strip())
    if actual_count != expected_count:
        raise ValueError(f"Document count mismatch for {data_path}: expected {expected_count}, got {actual_count}")

    return manifest, data_path, data_bytes, manifest_bytes


def _manifest_doc_count(manifest: dict[str, Any]) -> int:
    stats = manifest.get("stats") if isinstance(manifest.get("stats"), dict) else {}
    val = manifest.get("document_count")
    if val is None:
        val = stats.get("unique_snapshots")
    return int(val)


def sync_mongo_bundle_to_volume(
    *,
    workspace_client: Any,
    run_dir: Path | str,
    catalog: str = DEFAULT_CATALOG,
    schema: str = DEFAULT_SCHEMA,
    volume: str = DEFAULT_VOLUME,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Validate and upload ``documents.ejsonl`` (first) and ``manifest.json`` (second) to UC Volume."""
    manifest, data_path, data_bytes, manifest_bytes = validate_local_mongo_bundle(run_dir)
    doc_count = _manifest_doc_count(manifest)
    source_run_id = manifest["run_id"]
    volume_run_dir = f"/Volumes/{catalog}/{schema}/{volume}/run_id={source_run_id}"
    remote_data_path = f"{volume_run_dir}/{data_path.name}"
    remote_manifest_path = f"{volume_run_dir}/manifest.json"

    if not force:
        existing_manifest = read_remote_json(workspace_client, remote_manifest_path)
        if existing_manifest and existing_manifest.get("data_sha256") == manifest["data_sha256"]:
            return {
                "status": "SKIPPED_ALREADY_SYNCED",
                "source_run_id": source_run_id,
                "volume_run_dir": volume_run_dir,
                "document_count": doc_count,
                "data_sha256": manifest["data_sha256"],
                "uploaded_files": [],
            }

    if dry_run:
        return {
            "status": "DRY_RUN",
            "source_run_id": source_run_id,
            "volume_run_dir": volume_run_dir,
            "document_count": doc_count,
            "data_sha256": manifest["data_sha256"],
            "planned_files": [remote_data_path, remote_manifest_path],
        }

    # Upload data payload before manifest so readers never see a dangling manifest.
    workspace_client.files.upload(remote_data_path, io.BytesIO(data_bytes), overwrite=True)
    workspace_client.files.upload(remote_manifest_path, io.BytesIO(manifest_bytes), overwrite=True)

    return {
        "status": "UPLOADED",
        "source_run_id": source_run_id,
        "volume_run_dir": volume_run_dir,
        "document_count": doc_count,
        "data_sha256": manifest["data_sha256"],
        "bytes_uploaded": len(data_bytes) + len(manifest_bytes),
        "uploaded_files": [remote_data_path, remote_manifest_path],
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    parser.add_argument("--run-id", default=None, help="Specific Mongo run_id under --runs-root; defaults to latest.")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--volume", default=DEFAULT_VOLUME)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dotenv", default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    runs_root = Path(args.runs_root)
    run_dir = (runs_root / args.run_id) if args.run_id else discover_latest_mongo_run_dir(runs_root)
    workspace_client = build_workspace_client_from_env(args.dotenv)
    result = sync_mongo_bundle_to_volume(
        workspace_client=workspace_client,
        run_dir=run_dir,
        catalog=args.catalog,
        schema=args.schema,
        volume=args.volume,
        force=args.force,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
