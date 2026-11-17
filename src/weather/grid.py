"""Spatial grid clustering for full-network daily forecast ingestion (P5)."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


def cell_indices(lat: float, lon: float, *, step_deg: float, method: str) -> tuple[int, int]:
    """Compute deterministic spatial cell indices (row, col) for a coordinate."""
    if step_deg <= 0:
        raise ValueError(f"step_deg must be positive, got {step_deg!r}")
    if method == "floor":
        return math.floor(lat / step_deg), math.floor(lon / step_deg)
    if method == "round":
        return round(lat / step_deg), round(lon / step_deg)
    raise ValueError(f"Unsupported grid clustering method: {method!r}")


def build_grid_id(
    *, country_code: str, method: str, step_deg: float, row_idx: int, col_idx: int
) -> str:
    """Deterministic grid point identifier."""
    return f"grid:{country_code}:{method}:{step_deg:g}:{row_idx}:{col_idx}"


def _uniform_or_mixed(values: Sequence[Any]) -> str:
    distinct = sorted({str(v) for v in values if v is not None and str(v) != ""})
    if not distinct:
        return "UNKNOWN"
    return distinct[0] if len(distinct) == 1 else "MIXED"


def cluster_locations(
    eligible_locations: Sequence[Mapping[str, Any]],
    grid_config: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Cluster eligible stores for configured countries into representative grid points.

    Returns ``(points, store_grid_mapping)`` where ``points`` is the target list for API calls
    and ``store_grid_mapping`` maps every eligible store to its ``point_id`` / ``grid_id``.
    """
    locs = sorted((dict(loc) for loc in eligible_locations), key=lambda x: int(x["store_id"]))
    if not grid_config or not grid_config.get("enabled"):
        points: list[dict[str, Any]] = []
        mapping: list[dict[str, Any]] = []
        for loc in locs:
            pid = f"store:{int(loc['store_id'])}"
            points.append({
                **loc,
                "point_id": pid,
                "grid_id": None,
                "member_store_ids": [int(loc["store_id"])],
                "member_store_count": 1,
            })
            mapping.append(_mapping_row(loc=loc, point_id=pid, grid_id=None, point_lat=loc["latitude"],
                                      point_lon=loc["longitude"], clustered=False))
        return points, mapping

    countries = {str(c).upper() for c in grid_config["countries"]}
    step_deg = float(grid_config["step_deg"])
    method = str(grid_config["method"])
    coord_mode = str(grid_config.get("coordinate_mode") or "centroid")

    direct_points: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, int, int], list[dict[str, Any]]] = defaultdict(list)
    mapping_by_store: dict[int, dict[str, Any]] = {}

    for loc in locs:
        cc = str(loc.get("country_code") or "").upper()
        if cc in countries:
            row_idx, col_idx = cell_indices(float(loc["latitude"]), float(loc["longitude"]),
                                            step_deg=step_deg, method=method)
            grouped[(cc, str(loc["timezone_name"]), row_idx, col_idx)].append(loc)
        else:
            sid = int(loc["store_id"])
            pid = f"store:{sid}"
            direct_points.append({
                **loc,
                "point_id": pid,
                "grid_id": None,
                "member_store_ids": [sid],
                "member_store_count": 1,
            })
            mapping_by_store[sid] = _mapping_row(
                loc=loc, point_id=pid, grid_id=None,
                point_lat=float(loc["latitude"]), point_lon=float(loc["longitude"]), clustered=False,
            )

    grid_points: list[dict[str, Any]] = []
    for (cc, tz_name, row_idx, col_idx), members in sorted(grouped.items()):
        member_ids = sorted(int(m["store_id"]) for m in members)
        grid_id = build_grid_id(
            country_code=cc, method=method, step_deg=step_deg, row_idx=row_idx, col_idx=col_idx
        )
        if coord_mode == "centroid":
            rep_lat = round(sum(float(m["latitude"]) for m in members) / len(members), 6)
            rep_lon = round(sum(float(m["longitude"]) for m in members) / len(members), 6)
        elif coord_mode == "cell_center":
            rep_lat = round((row_idx + 0.5) * step_deg, 6)
            rep_lon = round((col_idx + 0.5) * step_deg, 6)
        else:
            raise ValueError(f"Unsupported coordinate_mode: {coord_mode!r}")

        grid_points.append({
            "point_id": grid_id,
            "grid_id": grid_id,
            "store_id": None,
            "store_code": None,
            "country_code": cc,
            "latitude": rep_lat,
            "longitude": rep_lon,
            "timezone_name": tz_name,
            "store_status": "ACTIVE",
            "source": _uniform_or_mixed([m.get("source") for m in members]),
            "coordinate_provenance": _uniform_or_mixed([m.get("coordinate_provenance") for m in members]),
            "coordinate_verification_status": _uniform_or_mixed(
                [m.get("coordinate_verification_status") for m in members]
            ),
            "eligibility_reason": f"GRID_CLUSTER:{method}:{step_deg:g}deg:{len(member_ids)}stores",
            "member_store_ids": member_ids,
            "member_store_count": len(member_ids),
        })
        for m in members:
            sid = int(m["store_id"])
            mapping_by_store[sid] = _mapping_row(
                loc=m, point_id=grid_id, grid_id=grid_id,
                point_lat=rep_lat, point_lon=rep_lon, clustered=True,
            )

    points = sorted(direct_points, key=lambda p: int(p["store_id"])) + sorted(
        grid_points, key=lambda p: str(p["grid_id"])
    )
    mapping_rows = [mapping_by_store[int(loc["store_id"])] for loc in locs]
    return points, mapping_rows


def _mapping_row(
    *,
    loc: Mapping[str, Any],
    point_id: str,
    grid_id: str | None,
    point_lat: float,
    point_lon: float,
    clustered: bool,
) -> dict[str, Any]:
    return {
        "store_id": int(loc["store_id"]),
        "store_code": loc.get("store_code"),
        "country_code": loc.get("country_code"),
        "timezone_name": loc["timezone_name"],
        "point_id": point_id,
        "grid_id": grid_id,
        "clustered": clustered,
        "store_latitude": float(loc["latitude"]),
        "store_longitude": float(loc["longitude"]),
        "point_latitude": float(point_lat),
        "point_longitude": float(point_lon),
        "source": loc.get("source"),
        "coordinate_provenance": loc.get("coordinate_provenance"),
        "coordinate_verification_status": loc.get("coordinate_verification_status"),
    }
