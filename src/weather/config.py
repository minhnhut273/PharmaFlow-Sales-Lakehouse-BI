"""Load and validate weather ingestion configuration (variable contracts, cohorts)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent / "config"
REQUIRED_TIMEFORMAT = "unixtime"
REQUIRED_UNIT_KEYS = ("temperature_unit", "wind_speed_unit", "precipitation_unit")
DEFAULT_UNITS = {"temperature_unit": "celsius", "wind_speed_unit": "ms", "precipitation_unit": "mm"}
DEFAULT_CORE_HOURLY = ("temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path.name} must contain a YAML mapping")
    return data


def _string_list(value: Any, field: str, name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name}: '{field}' must be a non-empty list")
    if not all(isinstance(v, str) and v for v in value):
        raise ValueError(f"{name}: '{field}' must contain only non-empty strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{name}: '{field}' contains duplicates")
    return list(value)


def load_variable_contract(contract_name: str, config_dir: Path | None = None) -> dict[str, Any]:
    """Load <config_dir>/<contract_name>.yaml and validate the request contract."""
    base = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR
    data = _read_yaml(base / f"{contract_name}.yaml")

    timeformat = data.get("timeformat")
    if timeformat != REQUIRED_TIMEFORMAT:
        raise ValueError(
            f"{contract_name}: timeformat must be 'unixtime' (got {timeformat!r}); "
            "iso8601 shifts local times across DST"
        )

    hourly = _string_list(data.get("hourly_variables"), "hourly_variables", contract_name)
    daily = _string_list(data.get("daily_variables"), "daily_variables", contract_name)
    core = list(data.get("core_hourly_variables") or DEFAULT_CORE_HOURLY)
    missing_core = [v for v in core if v not in hourly]
    if missing_core:
        raise ValueError(f"{contract_name}: core variables not in hourly_variables: {missing_core}")

    units = dict(DEFAULT_UNITS)
    units.update(data.get("units") or {})
    for key in REQUIRED_UNIT_KEYS:
        if units.get(key) != DEFAULT_UNITS[key]:
            raise ValueError(f"{contract_name}: units.{key} must be {DEFAULT_UNITS[key]!r}")

    return {
        "contract_version": data.get("contract_version") or contract_name,
        "applies_to_endpoints": list(data.get("applies_to_endpoints") or []),
        "min_supported_date": data.get("min_supported_date"),
        "max_supported_date": data.get("max_supported_date"),
        "model": data.get("model"),
        "timeformat": timeformat,
        "units": units,
        "core_hourly_variables": core,
        "hourly_variables": hourly,
        "daily_variables": daily,
        "n_variables": len(hourly) + len(daily),
    }


def _validate_grid_clustering(grid: Any, cohort_id: str) -> dict[str, Any]:
    if not grid:
        return {"enabled": False}
    if not isinstance(grid, dict):
        raise ValueError(f"cohorts.yaml: cohort '{cohort_id}' grid_clustering must be a mapping")
    enabled = bool(grid.get("enabled", False))
    if not enabled:
        return {"enabled": False}
    countries = _string_list(grid.get("countries"), "grid_clustering.countries", f"cohort '{cohort_id}'")
    method = str(grid.get("method") or "")
    if method not in ("floor", "round"):
        raise ValueError(f"cohorts.yaml: cohort '{cohort_id}' grid_clustering.method must be 'floor' or 'round'")
    step = grid.get("step_deg")
    if isinstance(step, bool) or not isinstance(step, (int, float)) or float(step) <= 0 or float(step) > 10.0:
        raise ValueError(f"cohorts.yaml: cohort '{cohort_id}' grid_clustering.step_deg must be in (0, 10]")
    coord_mode = str(grid.get("coordinate_mode") or "centroid")
    if coord_mode not in ("centroid", "cell_center"):
        raise ValueError(f"cohorts.yaml: cohort '{cohort_id}' coordinate_mode must be 'centroid' or 'cell_center'")
    return {
        "enabled": True,
        "countries": [c.upper() for c in countries],
        "method": method,
        "step_deg": float(step),
        "coordinate_mode": coord_mode,
    }


def load_cohorts_config(config_dir: Path | None = None) -> dict[str, Any]:
    """Load cohorts.yaml (cohort IDs, default policy, source -> provenance map)."""
    base = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR
    data = _read_yaml(base / "cohorts.yaml")

    cohorts = data.get("cohorts")
    if not isinstance(cohorts, dict) or not cohorts:
        raise ValueError("cohorts.yaml: 'cohorts' must be a non-empty mapping")
    for cohort_id, cohort in cohorts.items():
        if not isinstance(cohort, dict):
            raise ValueError(f"cohorts.yaml: cohort '{cohort_id}' must be a mapping")
        selection = str(cohort.get("selection") or "store_ids")
        if selection not in ("store_ids", "all_active"):
            raise ValueError(f"cohorts.yaml: cohort '{cohort_id}' unknown selection {selection!r}")
        ids = cohort.get("store_ids")
        if selection == "store_ids":
            if not isinstance(ids, list) or not ids or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
                raise ValueError(f"cohorts.yaml: cohort '{cohort_id}' needs a non-empty integer store_ids list")
        elif ids is not None and (not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids)):
            raise ValueError(f"cohorts.yaml: cohort '{cohort_id}' store_ids must be integers when supplied")
        _validate_grid_clustering(cohort.get("grid_clustering"), cohort_id)
        if cohort.get("allow_unknown_status") and not cohort.get("override_reason"):
            raise ValueError(f"cohorts.yaml: cohort '{cohort_id}' allows UNKNOWN status without override_reason")

    version = data.get("cohort_policy_version")
    if not version:
        raise ValueError("cohorts.yaml: 'cohort_policy_version' is required")

    return {
        "schema_version": data.get("schema_version"),
        "cohort_policy_version": version,
        "default_policy": dict(data.get("default_policy") or {}),
        "source_provenance_map": dict(data.get("source_provenance_map") or {}),
        "cohorts": cohorts,
    }


def resolve_cohort(cohort_id: str, config_dir: Path | None = None) -> dict[str, Any]:
    """Return the cohort definition merged with the default policy."""
    cfg = load_cohorts_config(config_dir=config_dir)
    cohort = cfg["cohorts"].get(cohort_id)
    if cohort is None:
        raise ValueError(f"Unknown cohort_id {cohort_id!r}; known: {sorted(cfg['cohorts'])}")
    policy = dict(cfg["default_policy"])
    policy.update({k: v for k, v in cohort.items() if k not in ("store_ids", "grid_clustering", "selection")})
    selection = str(cohort.get("selection") or "store_ids")
    grid_clustering = _validate_grid_clustering(cohort.get("grid_clustering"), cohort_id)
    return {
        "cohort_id": cohort_id,
        "cohort_policy_version": cfg["cohort_policy_version"],
        "selection": selection,
        "store_ids": sorted(int(i) for i in (cohort.get("store_ids") or [])),
        "grid_clustering": grid_clustering,
        "allow_unknown_status": bool(policy.get("allow_unknown_status", False)),
        "override_reason": policy.get("override_reason"),
        "source_provenance_map": cfg["source_provenance_map"],
    }


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_config_hash(payload: Mapping[str, Any]) -> str:
    """Deterministic 'sha256:<hex>' over canonical JSON (key-order independent)."""
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
