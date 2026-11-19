"""Database connectivity and cached SQL pushdown executor for Neon BI mirror."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
import streamlit as st
from dotenv import dotenv_values

from queries import DEFAULT_SCHEMA, validate_schema


class MissingDatabaseConfigError(RuntimeError):
    """Raised when QUICK_NEON_DATABASE_URL cannot be resolved."""


def _find_env_files() -> tuple[Path, ...]:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / ".env",  # BTL_BI/.env
        here.parents[3] / ".env",  # DACN/.env
        Path.cwd() / ".env",
    ]
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        if path not in seen and path.is_file():
            seen.add(path)
            unique.append(path)
    return tuple(unique)


@lru_cache(maxsize=1)
def get_db_settings() -> tuple[str, str]:
    """Resolve QUICK_NEON_DATABASE_URL and QUICK_NEON_SCHEMA without logging secrets."""
    dsn = os.getenv("QUICK_NEON_DATABASE_URL", "").strip()
    schema = os.getenv("QUICK_NEON_SCHEMA", "").strip()

    if not dsn or not schema:
        for env_path in _find_env_files():
            vals = dotenv_values(env_path)
            if not dsn:
                dsn = (vals.get("QUICK_NEON_DATABASE_URL") or "").strip()
            if not schema:
                schema = (vals.get("QUICK_NEON_SCHEMA") or "").strip()
            if dsn and schema:
                break

    if not dsn:
        try:
            dsn = str(st.secrets.get("QUICK_NEON_DATABASE_URL", "")).strip()
        except Exception:
            dsn = ""

    if not schema:
        try:
            schema = str(st.secrets.get("QUICK_NEON_SCHEMA", "")).strip()
        except Exception:
            schema = ""

    if not dsn:
        raise MissingDatabaseConfigError(
            "Chưa tìm thấy biến môi trường QUICK_NEON_DATABASE_URL. "
            "Hãy cấu hình trong BTL_BI/.env hoặc DACN/.env trước khi chạy dashboard."
        )

    return dsn, validate_schema(schema or DEFAULT_SCHEMA)


@st.cache_data(ttl=600, show_spinner=False)
def run_query_df(sql: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    """Execute a read-only parameterized SQL query against Neon (-pooler safe)."""
    dsn, _ = get_db_settings()
    with psycopg.connect(dsn, prepare_threshold=None, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [desc[0] for desc in (cur.description or ())]
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=cols)


def get_active_schema() -> str:
    _, schema = get_db_settings()
    return schema
