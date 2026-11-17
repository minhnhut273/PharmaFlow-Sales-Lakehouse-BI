"""Shared Databricks workspace and dotenv helpers for local Volume sync CLIs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from dotenv import load_dotenv


def clean_databricks_host(raw_host: str) -> str:
    """Strip workspace query strings like ``/?o=...`` from Databricks Workspace URLs."""
    trimmed = raw_host.strip()
    parts = urlsplit(trimmed)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return trimmed.rstrip("/")


def default_dotenv_path() -> Path:
    """Resolve the repository-root ``.env`` path from ``src/pipeline/databricks/src/common/workspace.py``."""
    return Path(__file__).resolve().parents[5] / ".env"


def build_workspace_client_from_env(dotenv_path: Path | str | None = None) -> WorkspaceClient:
    """Load ``.env`` (without overriding shell vars) and return an authenticated ``WorkspaceClient``."""
    resolved = Path(dotenv_path) if dotenv_path else default_dotenv_path()
    load_dotenv(resolved, override=False)
    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")
    if not host or not token:
        raise ValueError("DATABRICKS_HOST and DATABRICKS_TOKEN must be set in environment or .env")
    return WorkspaceClient(host=clean_databricks_host(host), token=token)


def read_remote_json(workspace_client: WorkspaceClient, volume_path: str) -> dict[str, Any] | None:
    """Download and decode a JSON file from a Unity Catalog Volume, returning ``None`` if absent."""
    try:
        resp = workspace_client.files.download(volume_path)
        raw = resp.contents.read() if resp.contents is not None else b""
        if not raw.strip():
            return None
        parsed = json.loads(raw.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else None
    except NotFound:
        return None
