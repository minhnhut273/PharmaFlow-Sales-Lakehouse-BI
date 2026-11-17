"""Worker: execute one frozen task (fetch -> persist raw + metadata -> validate -> accepted marker)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from src.weather import __version__
from src.weather.config import load_variable_contract
from src.weather.open_meteo import (
    build_open_meteo_params,
    classify_http_response,
    fetch_open_meteo,
    resolve_endpoint_url,
)
from src.weather.planner import accepted_key_for, task_base_key
from src.weather.validation import validate_open_meteo_response

METADATA_SCHEMA_VERSION = "1"
ACCEPTED_SCHEMA_VERSION = "1"
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"

HTTP_CATEGORY_STATUS = {
    "DEFERRED_RATE_LIMIT": "DEFERRED",
    "RETRYABLE_SERVER_ERROR": "RETRYABLE",
    "TERMINAL_CLIENT_ERROR": "FAILED",
}

Fetcher = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def default_fetcher(endpoint_key: str, params: Mapping[str, Any]) -> dict[str, Any]:
    return fetch_open_meteo(endpoint_key=endpoint_key, params=params)


def storage_info(sink: Any) -> dict[str, Any]:
    """Where the object lives (never credentials)."""
    return {"kind": getattr(sink, "kind", "unknown"), "bucket": getattr(sink, "bucket", None),
            "region": getattr(sink, "region", None)}


def build_task_params(task: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    common = {
        "endpoint_key": task["endpoint_key"],
        "latitude": task["latitude"],
        "longitude": task["longitude"],
        "timezone_name": task["timezone_name"],
        "hourly_variables": contract["hourly_variables"],
        "daily_variables": contract["daily_variables"],
        "model": task.get("model"),
    }
    if task["endpoint_key"] == "forecast":
        return build_open_meteo_params(**common, forecast_days=int(task["expected_days"]))
    return build_open_meteo_params(**common, start_date=task["start_date"], end_date=task["end_date"])


def _redact_params(params: Mapping[str, Any]) -> dict[str, Any]:
    # No secrets are ever sent to Open-Meteo; keep the variable lists short in metadata.
    out = dict(params)
    for key in ("hourly", "daily"):
        if key in out:
            out[key] = f"<{len(str(out[key]).split(','))} variables, see request_contract_version>"
    return out


def _record_transport_error(
    task: Mapping[str, Any], sink: Any, base: str, attempt_id: str, params: Mapping[str, Any],
    endpoint_url: str, exc: BaseException,
) -> dict[str, Any]:
    """Timeout / connection error: no response bytes exist; keep a metadata-only attempt record."""
    metadata_key = f"{base}/attempts/{attempt_id}/metadata.json"
    error = f"{type(exc).__name__}: {str(exc)[:300]}"
    sink.put_json(metadata_key, {
        "schema_version": METADATA_SCHEMA_VERSION,
        "request_contract_version": task["contract_version"],
        "config_hash": task.get("config_hash"),
        "code_version": __version__,
        "run_id": task["run_id"],
        "task_id": task["task_id"],
        "attempt_id": attempt_id,
        "store_id": task.get("store_id"),
        "endpoint_key": task["endpoint_key"],
        "endpoint": endpoint_url,
        "query_params_redacted": _redact_params(params),
        "http_status": None,
        "http_category": "TRANSPORT_ERROR",
        "transport_error": error,
        **({"grid_id": task["grid_id"], "member_store_ids": task.get("member_store_ids"),
            "member_store_count": task.get("member_store_count")} if task.get("grid_id") is not None else {}),
        "response_key": None,
        "validation_status": "NOT_VALIDATED",
        "estimated_quota_charge": task.get("estimated_cost"),
        "retrieved_at_utc": None,
        "persisted_at_utc": _iso(datetime.now(timezone.utc)),
    })
    return {
        "status": "RETRYABLE",
        "attempt_id": attempt_id,
        "validation_status": "NOT_VALIDATED",
        "validation_reason": error,
        "http_status": None,
        "http_category": "TRANSPORT_ERROR",
        "raw_sha256": None,
        "rate_limit_headers": {},
        "http_called": True,
        "keys": {"metadata": metadata_key},
    }


def execute_task(
    *,
    task: Mapping[str, Any],
    sink: Any,
    fetcher: Fetcher | None = None,
    attempt_id: str,
    today_vn: str,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    base = task_base_key(task)
    accepted_key = accepted_key_for(task)
    now = now_utc or datetime.now(timezone.utc)

    if sink.exists(accepted_key):
        prior = sink.get_json(accepted_key)
        return {
            "status": "SKIPPED_ALREADY_ACCEPTED",
            "attempt_id": attempt_id,
            "accepted_attempt_id": prior.get("attempt_id"),
            "validation_status": prior.get("status"),
            "http_called": False,
        }

    deadline = task.get("deadline_utc")
    if deadline and now >= _parse_iso(deadline):
        return {"status": "EXPIRED", "attempt_id": attempt_id, "reason": f"deadline {deadline} passed",
                "http_called": False}

    contract = load_variable_contract(task["contract_version"])
    params = build_task_params(task, contract)
    endpoint_url = resolve_endpoint_url(task["endpoint_key"])

    fetch = fetcher or default_fetcher
    try:
        result = dict(fetch(task["endpoint_key"], params))
    except OSError as exc:  # requests.RequestException (timeouts, connection errors) subclasses OSError
        return _record_transport_error(task, sink, base, attempt_id, params, endpoint_url, exc)
    retrieved_at = datetime.now(timezone.utc)
    raw: bytes = result.get("raw_bytes") or b""
    raw_sha256 = hashlib.sha256(raw).hexdigest()
    if result.get("raw_sha256") and result["raw_sha256"] != raw_sha256:
        raise RuntimeError("Fetcher-reported SHA-256 does not match raw bytes")
    http_status = int(result.get("http_status", 0))
    headers = dict(result.get("headers") or {})
    rate_limit = dict(result.get("rate_limit_headers") or {})
    http_info = classify_http_response(http_status=http_status, headers=headers)

    attempt_prefix = f"{base}/attempts/{attempt_id}"
    response_key = f"{attempt_prefix}/response.json"
    metadata_key = f"{attempt_prefix}/metadata.json"

    # 1) Raw bytes first, exactly as received (after transport decompression).
    sink.put_bytes(response_key, raw)

    # 2) Validate in memory (only for HTTP 200).
    if http_info["category"] == "OK":
        report = validate_open_meteo_response(
            raw_bytes=raw,
            expected_days=int(task["expected_days"]),
            timezone_name=task["timezone_name"],
            end_date=task["end_date"],
            start_date=task["start_date"],
            today_vn=today_vn,
            core_variables=contract["core_hourly_variables"],
            expected_hourly_variables=contract["hourly_variables"],
        )
        status = report["status"]
    else:
        report = {"status": "NOT_VALIDATED", "reason": f"HTTP {http_status}", "is_accepted": False,
                  "is_terminal": http_info["category"] == "TERMINAL_CLIENT_ERROR"}
        status = HTTP_CATEGORY_STATUS[http_info["category"]]

    is_forecast = task["mode"] == "daily_forecast"
    snapshot_id = f"{task['run_id']}:{task['task_id']}:{attempt_id}"
    metadata = {
        "schema_version": METADATA_SCHEMA_VERSION,
        "request_contract_version": task["contract_version"],
        "config_hash": task.get("config_hash"),
        "code_version": __version__,
        "run_id": task["run_id"],
        "task_id": task["task_id"],
        "task_index": task.get("task_index"),
        "attempt_id": attempt_id,
        "mode": task["mode"],
        "snapshot_id": snapshot_id,
        "forecast_snapshot_id": snapshot_id if is_forecast else None,
        "source_type": task.get("source_type"),
        "store_id": task.get("store_id"),
        "store_code": task.get("store_code"),
        "country_code": task.get("country_code"),
        "requested_coordinates": {"latitude": task["latitude"], "longitude": task["longitude"]},
        "returned_coordinates": report.get("returned_coordinates"),
        "elevation_m": report.get("elevation_m"),
        "timezone_requested": task["timezone_name"],
        "timezone_returned": report.get("timezone_returned"),
        "utc_offset_seconds": report.get("utc_offset_seconds"),
        "timeformat": params["timeformat"],
        "source": task.get("source"),
        "coordinate_provenance": task.get("coordinate_provenance"),
        "coordinate_verification_status": task.get("coordinate_verification_status"),
        "eligibility_reason": task.get("eligibility_reason"),
        "endpoint_key": task["endpoint_key"],
        "endpoint": endpoint_url,
        "model": task.get("model"),
        "window": {"start_date": task["start_date"], "end_date": task["end_date"],
                   "expected_days": task["expected_days"]},
        "query_params_redacted": _redact_params(params),
        "http_status": http_status,
        "http_category": http_info["category"],
        "retry_after_seconds": http_info.get("retry_after_seconds"),
        "response_headers": headers,
        "raw_byte_length": len(raw),
        "raw_sha256": raw_sha256,
        "response_key": response_key,
        "validation_status": report["status"],
        "validation_reason": report.get("reason"),
        "hourly_step_count": report.get("hourly_step_count"),
        "daily_step_count": report.get("daily_step_count"),
        "non_24h_days": report.get("non_24h_days"),
        "returned_window": report.get("returned_window"),
        "missing_variables": report.get("missing_variables"),
        "null_report": report.get("null_report"),
        "rate_limit_headers": rate_limit,
        "estimated_quota_charge": task.get("estimated_cost"),
        "scheduled_at_utc": task.get("scheduled_at_utc"),
        "planned_at_utc": task.get("planned_at_utc"),
        "retrieved_at_utc": _iso(retrieved_at),
        "persisted_at_utc": _iso(datetime.now(timezone.utc)),
        "attribution": ATTRIBUTION,
        "storage": storage_info(sink),
    }
    if task.get("grid_id") is not None:
        metadata["grid_id"] = task["grid_id"]
        metadata["member_store_ids"] = task.get("member_store_ids")
        metadata["member_store_count"] = task.get("member_store_count")
    # 3) Metadata sidecar (includes validation outcome).
    sink.put_json(metadata_key, metadata)

    outcome = {
        "status": status,
        "attempt_id": attempt_id,
        "validation_status": report["status"],
        "validation_reason": report.get("reason"),
        "http_status": http_status,
        "http_category": http_info["category"],
        "retry_after_seconds": http_info.get("retry_after_seconds"),
        "raw_sha256": raw_sha256,
        "rate_limit_headers": rate_limit,
        "http_called": True,
        "keys": {"response": response_key, "metadata": metadata_key},
    }

    # 4) Immutable accepted marker only for accepted validations.
    if report.get("is_accepted") is True:
        marker = {
            "schema_version": ACCEPTED_SCHEMA_VERSION,
            "run_id": task["run_id"],
            "task_id": task["task_id"],
            "attempt_id": attempt_id,
            "status": status,
            "raw_sha256": raw_sha256,
            "response_key": response_key,
            "metadata_key": metadata_key,
            "accepted_at_utc": _iso(datetime.now(timezone.utc)),
            "storage": storage_info(sink),
        }
        if sink.put_json_if_absent(accepted_key, marker):
            outcome["keys"]["accepted"] = accepted_key
        else:
            prior = sink.get_json(accepted_key)
            outcome.update({"status": "SKIPPED_ALREADY_ACCEPTED", "accepted_attempt_id": prior.get("attempt_id")})
    return outcome
