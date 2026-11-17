"""Shared MongoDB connection helpers for the PharmaFlow source utilities."""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ServerSelectionTimeoutError


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)


class MongoConnectionError(RuntimeError):
    """A MongoDB configuration or connection error with secrets omitted."""


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise MongoConnectionError(f"Missing required environment variable: {name}")
    return value


def _remove_uri_credentials(uri: str) -> str:
    return re.sub(
        r"^(mongodb(?:\+srv)?://)[^/?#@]*@",
        r"\1",
        uri,
        count=1,
        flags=re.IGNORECASE,
    )


def connect_mongodb(
    *, database_name: str | None = None, collection_name: str | None = None
) -> tuple[MongoClient, Database, str]:
    """Connect to MongoDB, optionally selecting an explicit database/collection."""
    uri = os.getenv("MONGODB_CONNECTION_STRING", "").strip() or os.getenv(
        "MONGODB_URI", ""
    ).strip()
    if not uri:
        raise MongoConnectionError(
            "Set MONGODB_CONNECTION_STRING in .env (MONGODB_URI is also supported)."
        )
    if not re.match(r"^mongodb(?:\+srv)?://", uri, flags=re.IGNORECASE):
        raise MongoConnectionError(
            "MongoDB connection string must use mongodb:// or mongodb+srv://."
        )

    database_name = database_name or _required_env("MONGODB_DATABASE_NAME")
    collection_name = collection_name or _required_env("MONGODB_COLLECTION_NAME")
    username = os.getenv("USERNAME_MONGODB", "").strip()
    password = os.getenv("PASSWORD_MONGODB", "")

    options: dict[str, object] = {"serverSelectionTimeoutMS": 10_000}
    if username or password:
        if not username or not password:
            raise MongoConnectionError(
                "Set both USERNAME_MONGODB and PASSWORD_MONGODB, or omit both."
            )
        # Explicit env credentials take precedence over stale URI user-info.
        uri = _remove_uri_credentials(uri)
        options.update(username=username, password=password)

    client: MongoClient | None = None
    try:
        client = MongoClient(uri, **options)
        client.admin.command({"ping": 1})
        return client, client[database_name], collection_name
    except Exception as exc:
        if client is not None:
            client.close()
        if isinstance(exc, ServerSelectionTimeoutError):
            detail = str(exc).casefold()
            if "ssl handshake failed" in detail or "[ssl:" in detail:
                reason = "TLS handshake failed"
            elif "authentication failed" in detail or "bad auth" in detail:
                reason = "authentication was rejected"
            elif "name resolution" in detail or "dns" in detail:
                reason = "MongoDB host lookup failed"
            else:
                reason = "server selection timed out; check Atlas network access and cluster availability"
        else:
            reason = f"connection or authentication failed ({type(exc).__name__})"
        raise MongoConnectionError(
            f"MongoDB connection failed: {reason}."
        ) from None
