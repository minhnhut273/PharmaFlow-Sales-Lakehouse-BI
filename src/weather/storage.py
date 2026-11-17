"""Storage sinks. P1: LocalSink (local files). P2: S3Sink (same S3-style keys on a bucket)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

WEATHER_PREFIXES = (
    "raw/open_meteo/weather_forecast/",
    "raw/open_meteo/historical_forecast/",
    "raw/open_meteo/historical_weather/",
)


def _validate_key(key: str) -> PurePosixPath:
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Storage key must be a non-empty string")
    if "\\" in key or key.startswith("/") or ":" in key.split("/", 1)[0]:
        raise ValueError(f"Storage key must be a relative POSIX key: {key!r}")
    path = PurePosixPath(key)
    if any(part in ("", ".", "..") for part in path.parts) or key.endswith("/"):
        raise ValueError(f"Storage key contains an invalid segment: {key!r}")
    return path


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


class LocalSink:
    """Filesystem sink using S3-style keys (``raw/open_meteo/...``) relative to ``root_dir``."""

    kind = "local"

    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir)

    def _path(self, key: str) -> Path:
        return self.root_dir.joinpath(*_validate_key(key).parts)

    def uri(self, key: str) -> str:
        return str(self._path(key))

    def put_bytes(self, key: str, data: bytes) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def put_json(self, key: str, payload: Mapping[str, Any]) -> None:
        self.put_bytes(key, _json_bytes(payload))

    def get_json(self, key: str) -> dict[str, Any]:
        return json.loads(self.get_bytes(key).decode("utf-8"))

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def put_json_if_absent(self, key: str, payload: Mapping[str, Any]) -> bool:
        """Create-only write (S3 If-None-Match: * equivalent). Returns False if the key exists."""
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = _json_bytes(payload)
        try:
            with target.open("xb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
        except FileExistsError:
            return False
        return True

    def list_keys(self, prefix: str) -> list[str]:
        base = self._path(prefix.rstrip("/"))
        if not base.exists():
            return []
        if base.is_file():
            return [prefix.rstrip("/")]
        keys = []
        for path in base.rglob("*"):
            if path.is_file() and not path.name.startswith(".tmp-"):
                keys.append(path.relative_to(self.root_dir).as_posix())
        return sorted(keys)


class S3Sink:
    """S3 sink with the LocalSink interface. Writes only inside the three Weather prefixes.

    - put_json_if_absent uses PutObject If-None-Match: * (412 -> False).
    - exists() uses ListObjectsV2(Prefix=key): the writer policy scopes s3:ListBucket by s3:prefix,
      so HeadObject on a missing key would return 403 instead of 404.
    - Every write sends ChecksumSHA256 so S3 verifies integrity server-side.
    """

    kind = "s3"

    def __init__(self, *, bucket: str, client: Any, region: str | None = None) -> None:
        self.bucket = bucket
        self.client = client
        self.region = region

    @staticmethod
    def _key(key: str) -> str:
        path = _validate_key(key).as_posix()
        if not any(path.startswith(p) for p in WEATHER_PREFIXES):
            raise ValueError(f"S3 key outside the Weather prefixes: {key!r}")
        return path

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{self._key(key)}"

    @staticmethod
    def _error_code(exc: Exception) -> str:
        return str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))

    def _put(self, key: str, data: bytes, content_type: str, *, if_none_match: bool) -> None:
        kwargs: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": self._key(key),
            "Body": data,
            "ContentType": content_type,
            "ChecksumSHA256": base64.b64encode(hashlib.sha256(data).digest()).decode("ascii"),
        }
        if if_none_match:
            kwargs["IfNoneMatch"] = "*"
        self.client.put_object(**kwargs)

    def put_bytes(self, key: str, data: bytes) -> None:
        self._put(key, data, "application/json" if key.endswith(".json") else "application/octet-stream",
                  if_none_match=False)

    def get_bytes(self, key: str) -> bytes:
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        except Exception as exc:
            if self._error_code(exc) in ("NoSuchKey", "404"):
                raise FileNotFoundError(self.uri(key)) from None
            raise
        with resp["Body"] as body:
            return body.read()

    def put_json(self, key: str, payload: Mapping[str, Any]) -> None:
        self._put(key, _json_bytes(payload), "application/json", if_none_match=False)

    def get_json(self, key: str) -> dict[str, Any]:
        return json.loads(self.get_bytes(key).decode("utf-8"))

    def exists(self, key: str) -> bool:
        k = self._key(key)
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=k, MaxKeys=1)
        return any(obj.get("Key") == k for obj in resp.get("Contents", []))

    def put_json_if_absent(self, key: str, payload: Mapping[str, Any]) -> bool:
        data = _json_bytes(payload)
        for attempt in range(2):
            try:
                self._put(key, data, "application/json", if_none_match=True)
                return True
            except Exception as exc:
                code = self._error_code(exc)
                if code == "PreconditionFailed":
                    return False
                if code == "ConditionalRequestConflict" and attempt == 0:
                    continue  # concurrent conditional write in flight; retry once
                raise
        return False

    def list_keys(self, prefix: str) -> list[str]:
        p = self._key(prefix.rstrip("/")) + "/"
        paginator = self.client.get_paginator("list_objects_v2")
        return sorted(k for k in paginator.paginate(Bucket=self.bucket, Prefix=p).search("Contents[].Key") if k)
