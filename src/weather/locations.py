"""Read-only store location reader (Neon org.store) and cohort eligibility policy."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

STORE_COLUMNS = (
    "store_id",
    "store_code",
    "country_code",
    "latitude",
    "longitude",
    "timezone_name",
    "store_status",
    "source",
)

STORE_QUERY = (
    "SELECT store_id, store_code, country_code, latitude, longitude, "
    "timezone_name, store_status, source "
    "FROM org.store "
    "WHERE store_id = ANY(%s) "
    "ORDER BY store_id"
)

ALL_ACTIVE_STORE_QUERY = (
    "SELECT store_id, store_code, country_code, latitude, longitude, "
    "timezone_name, store_status, source "
    "FROM org.store "
    "WHERE store_status = 'ACTIVE' "
    "ORDER BY store_id"
)

UNMAPPED_PROVENANCE = {
    "coordinate_provenance": "UNMAPPED_SOURCE",
    "coordinate_verification_status": "UNVERIFIED_UNMAPPED_SOURCE",
}


def _as_coordinate(value: Any) -> float | None:
    """Return a finite float, or None. NULL is never coerced to 0; bool is not a number."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _valid_timezone(name: Any) -> bool:
    if not isinstance(name, str) or not name.strip():
        return False
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def _default_provenance_map() -> Mapping[str, Any]:
    from src.weather.config import load_cohorts_config

    return load_cohorts_config()["source_provenance_map"]


def evaluate_locations(
    rows: Sequence[Mapping[str, Any]],
    requested_store_ids: Sequence[int] | None = None,
    allow_unknown_status: bool = False,
    override_reason: str | None = None,
    source_provenance_map: Mapping[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Split requested stores into eligible / rejected according to the v1 cohort policy."""
    prov_map = source_provenance_map if source_provenance_map is not None else _default_provenance_map()
    unknown_allowed = bool(allow_unknown_status) and bool(override_reason and str(override_reason).strip())

    by_id: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        by_id[int(row["store_id"])] = row

    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    target_ids = sorted({int(i) for i in requested_store_ids}) if requested_store_ids is not None else sorted(by_id)
    for store_id in target_ids:
        row = by_id.get(store_id)
        if row is None:
            rejected.append({"store_id": store_id, "rejection_reason": "STORE_NOT_FOUND"})
            continue

        base = {"store_id": store_id, "store_code": row.get("store_code"), "source": row.get("source")}
        lat = _as_coordinate(row.get("latitude"))
        lon = _as_coordinate(row.get("longitude"))
        if lat is None or lon is None or not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            rejected.append({**base, "rejection_reason": "INVALID_COORDINATES"})
            continue

        tz = row.get("timezone_name")
        if not _valid_timezone(tz):
            rejected.append({**base, "rejection_reason": "INVALID_TIMEZONE"})
            continue

        status = str(row.get("store_status") or "").upper()
        if status == "ACTIVE":
            reason = "ACTIVE_VALID_COORDINATES_AND_TIMEZONE"
        elif status == "UNKNOWN" and unknown_allowed:
            reason = f"UNKNOWN_STATUS_OVERRIDE: {str(override_reason).strip()}"
        elif status == "INACTIVE":
            rejected.append({**base, "rejection_reason": "INACTIVE"})
            continue
        elif status == "UNKNOWN":
            rejected.append({**base, "rejection_reason": "UNKNOWN_STATUS"})
            continue
        else:
            rejected.append({**base, "rejection_reason": f"UNSUPPORTED_STATUS:{status or 'NULL'}"})
            continue

        prov = prov_map.get(row.get("source")) or UNMAPPED_PROVENANCE
        eligible.append(
            {
                "store_id": store_id,
                "store_code": row.get("store_code"),
                "country_code": row.get("country_code"),
                "latitude": lat,
                "longitude": lon,
                "timezone_name": tz,
                "store_status": status,
                "source": row.get("source"),
                "coordinate_provenance": prov.get("coordinate_provenance", UNMAPPED_PROVENANCE["coordinate_provenance"]),
                "coordinate_verification_status": prov.get(
                    "coordinate_verification_status", UNMAPPED_PROVENANCE["coordinate_verification_status"]
                ),
                "eligibility_reason": reason,
            }
        )

    return {"eligible_locations": eligible, "rejected_locations": rejected}


def _default_connect(dsn: str, **kwargs: Any) -> Any:
    import psycopg

    return psycopg.connect(dsn, **kwargs)


def _rows_as_dicts(cursor: Any) -> list[dict[str, Any]]:
    names = [col[0] for col in cursor.description]
    return [dict(zip(names, rec)) for rec in cursor.fetchall()]


def _run_store_query(
    dsn: str,
    query: str,
    params: tuple[Any, ...] | None = None,
    *,
    connect: Callable[..., Any] = _default_connect,
    connect_timeout: int = 10,
) -> list[dict[str, Any]]:
    conn = connect(dsn, connect_timeout=connect_timeout)
    try:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = _rows_as_dicts(cur)
        conn.rollback()
    finally:
        conn.close()
    for row in rows:
        for key in ("latitude", "longitude"):
            if row.get(key) is not None and not isinstance(row[key], float):
                row[key] = float(row[key])
    return rows


def read_store_rows(
    dsn: str,
    store_ids: Sequence[int],
    *,
    connect: Callable[..., Any] = _default_connect,
    connect_timeout: int = 10,
) -> list[dict[str, Any]]:
    """SELECT-only read of org.store for the given IDs in a read-only session."""
    ids = sorted({int(i) for i in store_ids})
    if not ids:
        return []
    return _run_store_query(dsn, STORE_QUERY, (ids,), connect=connect, connect_timeout=connect_timeout)


def read_all_active_store_rows(
    dsn: str,
    *,
    connect: Callable[..., Any] = _default_connect,
    connect_timeout: int = 10,
) -> list[dict[str, Any]]:
    """SELECT-only read of all ACTIVE rows in org.store in a read-only session."""
    return _run_store_query(dsn, ALL_ACTIVE_STORE_QUERY, None, connect=connect, connect_timeout=connect_timeout)


def fetch_db_identity(
    dsn: str,
    *,
    connect: Callable[..., Any] = _default_connect,
    connect_timeout: int = 10,
) -> dict[str, Any]:
    """Preflight: database/user identity and privileges on org.store (no data rows)."""
    conn = connect(dsn, connect_timeout=connect_timeout)
    try:
        conn.read_only = True
        with conn.cursor() as cur:
            # weather_reader has column-level SELECT on the 8 columns, so table-level
            # has_table_privilege('SELECT') is false; check each required column instead.
            cur.execute(
                "SELECT current_database(), current_user, "
                "(SELECT bool_and(has_column_privilege(current_user, 'org.store', c, 'SELECT')) "
                "   FROM unnest(%s::text[]) AS c), "
                "has_any_column_privilege(current_user, 'org.store', 'INSERT'), "
                "has_any_column_privilege(current_user, 'org.store', 'UPDATE'), "
                "has_table_privilege(current_user, 'org.store', 'DELETE'), "
                "has_table_privilege(current_user, 'org.store', 'TRUNCATE'), "
                "current_setting('transaction_read_only')",
                (list(STORE_COLUMNS),),
            )
            db, user, can_select, can_insert, can_update, can_delete, can_truncate, ro = cur.fetchone()
        conn.rollback()
    finally:
        conn.close()
    return {
        "current_database": db,
        "current_user": user,
        "store_select_required_columns": bool(can_select),
        "store_insert": bool(can_insert),
        "store_update": bool(can_update),
        "store_delete": bool(can_delete),
        "store_truncate": bool(can_truncate),
        "session_read_only": ro == "on",
    }
