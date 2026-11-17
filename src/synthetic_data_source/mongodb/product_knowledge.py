"""MongoDB contract and local Long Chau snapshot builder.

Source HTML remains in Dataset/longchau-knowledge. Only parsed, source-backed
fields and a relative local reference are stored in MongoDB.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable

import yaml


DATABASE_NAME = "pharmaflow_product_knowledge"
COLLECTION_NAME = "product_snapshots"
SOURCE_NAME = "LONGCHAU_PUBLIC_PRODUCT_PAGE"
SCHEMA_VERSION = 1
EXTRACTION_VERSION = "longchau-product-knowledge-v1"


def _local_open_path(path: Path) -> str:
    """Return a path Windows can open even when a product slug exceeds MAX_PATH."""
    file_path = str(path)
    if os.name == "nt":
        absolute = os.path.abspath(file_path)
        if absolute.startswith("\\\\"):
            file_path = "\\\\?\\UNC\\" + absolute.lstrip("\\")
        else:
            file_path = "\\\\?\\" + absolute
    return file_path


def _read_local_text(path: Path, *, encoding: str, errors: str = "strict") -> str:
    """Read project files, including long Windows paths used by KB product slugs."""
    file_path = _local_open_path(path)
    with open(file_path, "r", encoding=encoding, errors=errors) as handle:
        return handle.read()


def _snapshot_json_schema() -> dict[str, Any]:
    date = {"bsonType": "date"}
    string_or_null = {"bsonType": ["string", "null"]}
    return {
        "bsonType": "object",
        "required": [
            "_id", "schema_version", "source", "source_product_key", "source_sku",
            "composition", "storage", "provenance", "extraction",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "schema_version": {"bsonType": "int", "enum": [SCHEMA_VERSION]},
            "source": {"enum": [SOURCE_NAME]},
            "source_product_key": {"bsonType": "string", "minLength": 1},
            "source_sku": string_or_null,
            "composition": {
                "bsonType": "object",
                "required": ["basis_text", "items", "details_markdown", "web_description_markdown"],
                "properties": {
                    "basis_text": string_or_null,
                    "items": {"bsonType": "array", "items": {
                        "bsonType": "object",
                        "required": ["name", "description_text", "source_record_id", "source_ingredient_id", "source_is_primary", "source_slug"],
                        "properties": {
                            "name": string_or_null,
                            "description_text": string_or_null,
                            "source_record_id": {"bsonType": ["long", "int", "null"]},
                            "source_ingredient_id": {"bsonType": ["long", "int", "null"]},
                            "source_is_primary": {"bsonType": ["bool", "null"]},
                            "source_slug": string_or_null,
                        },
                        "additionalProperties": False,
                    }},
                    "details_markdown": string_or_null,
                    "web_description_markdown": string_or_null,
                },
                "additionalProperties": False,
            },
            "storage": {"bsonType": "object", "required": ["instructions_text"], "properties": {"instructions_text": string_or_null}, "additionalProperties": False},
            "provenance": {
                "bsonType": "object",
                "required": ["evidence_status", "source_url", "captured_at", "content_hash", "raw_local_path"],
                "properties": {
                    "evidence_status": {"enum": ["observed"]},
                    "source_url": {"bsonType": "string", "minLength": 1},
                    "captured_at": date,
                    "content_hash": {"bsonType": "string", "pattern": "^[0-9a-f]{64}$"},
                    "raw_local_path": string_or_null,
                },
                "additionalProperties": False,
            },
            "extraction": {
                "bsonType": "object",
                "required": ["version", "status", "extracted_at"],
                "properties": {
                    "version": {"bsonType": "string", "minLength": 1},
                    "status": {"enum": ["COMPLETE", "RAW_UNAVAILABLE", "PARSE_ERROR"]},
                    "extracted_at": date,
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }


COLLECTION_VALIDATOR = {"$jsonSchema": _snapshot_json_schema()}
INDEXES = [
    ([ ("source", 1), ("source_product_key", 1), ("provenance.captured_at", 1), ("provenance.content_hash", 1) ], {"unique": True, "name": "uq_product_capture"}),
    ([ ("source", 1), ("source_product_key", 1), ("provenance.captured_at", -1), ("_id", -1) ], {"name": "ix_source_product_history"}),
]


class _TextMarkdown(HTMLParser):
    """Convert source HTML to readable text while preserving table rows."""
    BLOCKS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.rows: list[list[str]] = []
        self.cell_text: list[str] = []
        self.in_cell = False
        self.in_table = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.in_table = True
        elif tag == "tr":
            self.rows.append([])
        elif tag in {"td", "th"}:
            self.in_cell = True
            self.cell_text = []
        elif tag == "br":
            (self.cell_text if self.in_cell else self.parts).append("\n")
        elif tag in self.BLOCKS:
            if not self.in_table:
                self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"}:
            self.in_cell = False
            cell = re.sub(r"\s+", " ", "".join(self.cell_text)).strip()
            if self.rows:
                self.rows[-1].append(cell)
            self.cell_text = []
        elif tag == "tr":
            pass
        elif tag == "table":
            if self.rows:
                width = max(map(len, self.rows))
                for i, row in enumerate(self.rows):
                    row += [""] * (width-len(row))
                    self.parts.append("| " + " | ".join(row) + " |\n")
                    if i == 0:
                        self.parts.append("| " + " | ".join(["---"]*width) + " |\n")
            self.rows.clear()
            self.in_table = False
            self.parts.append("\n")
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        (self.cell_text if self.in_cell else self.parts).append(data)

    def result(self) -> str | None:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text or None


def html_to_markdown(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parser = _TextMarkdown()
    parser.feed(value)
    parser.close()
    return parser.result()


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _as_text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def canonical_source_key(sku: str | None, canonical_url: str) -> str:
    if sku and sku.strip():
        return "SKU:" + sku.strip()
    if canonical_url and canonical_url.strip():
        return "URL:" + canonical_url.strip()
    raise ValueError("Long Chau product needs a source SKU or canonical URL")


def _get_raw_path(metadata: dict[str, Any], knowledge_root: Path) -> Path | None:
    raw = metadata.get("raw_snapshot")
    if isinstance(raw, str) and raw.strip():
        candidate = (knowledge_root / raw).resolve()
    else:
        content_hash = ((metadata.get("crawl") or {}).get("content_hash"))
        if not isinstance(content_hash, str):
            return None
        candidate = knowledge_root / "_raw" / f"{content_hash}.html"
    root = knowledge_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("raw_snapshot path escapes the Long Chau knowledge base")
    return candidate


def _extract_next_data(html: str) -> dict[str, Any] | None:
    match = re.search(r'<script\b(?=[^>]*\bid=["\']__NEXT_DATA__["\'])[^>]*>(.*?)</script>', html, re.I | re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1)).get("props", {}).get("pageProps", {})
    except (json.JSONDecodeError, AttributeError):
        return None


def _build_items(raw_items: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    items = []
    for item in raw_items:
        if isinstance(item, str):
            items.append({"name": _as_text(item), "description_text": None, "source_record_id": None, "source_ingredient_id": None, "source_is_primary": None, "source_slug": None})
            continue
        if not isinstance(item, dict):
            continue
        items.append({
            "name": _as_text(item.get("name")),
            "description_text": _as_text(item.get("shortDescription")),
            "source_record_id": _as_int(item.get("id")),
            "source_ingredient_id": _as_int(item.get("ingredientId")),
            "source_is_primary": _as_bool(item.get("isPrimary")),
            "source_slug": _as_text(item.get("slug")),
        })
    return items


def build_snapshot(metadata: dict[str, Any], note_path: Path, knowledge_root: Path, *, extracted_at: datetime | None = None) -> dict[str, Any]:
    """Build one Mongo document from a KB note and its local raw HTML capture."""
    product = metadata.get("product") or {}
    attrs = product.get("other_public_attributes") or {}
    source_url = _as_text(metadata.get("canonical_url") or product.get("canonical_url") or metadata.get("source_url"))
    if not source_url:
        raise ValueError(f"Missing canonical/source URL: {note_path}")
    sku = _as_text(attrs.get("sku"))
    crawl = metadata.get("crawl") or {}
    captured = crawl.get("crawled_at") or crawl.get("captured_at")
    if isinstance(captured, str):
        captured = datetime.fromisoformat(captured.replace("Z", "+00:00"))
    if not isinstance(captured, datetime):
        raise ValueError(f"Missing capture timestamp: {note_path}")
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    captured = captured.astimezone(timezone.utc)

    raw_path = _get_raw_path(metadata, knowledge_root)
    raw_html = _read_local_text(raw_path, encoding="utf-8", errors="replace") if raw_path and raw_path.is_file() else None
    raw_data = _extract_next_data(raw_html) if raw_html else None
    content_hash = _as_text(crawl.get("content_hash"))
    if not content_hash and raw_html:
        content_hash = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()
    if not content_hash or not re.fullmatch(r"[0-9a-f]{64}", content_hash):
        raise ValueError(f"Missing/invalid content hash: {note_path}")

    raw_product = (raw_data or {}).get("product") or {}
    raw_content = (raw_data or {}).get("content") or {}
    local_ref = raw_path.relative_to(Path(__file__).resolve().parents[3]).as_posix() if raw_path and raw_path.is_file() else None
    now = extracted_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if raw_data is None:
        status = "RAW_UNAVAILABLE" if raw_html is None else "PARSE_ERROR"
    elif not isinstance(raw_data.get("product"), dict):
        status = "PARSE_ERROR"
        raw_data = None
    else:
        status = "COMPLETE"
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE_NAME,
        "source_product_key": canonical_source_key(sku, source_url),
        "source_sku": sku,
        "composition": {
            "basis_text": _as_text(raw_product.get("ingredientFor")) if raw_data is not None else None,
            "items": _build_items(raw_product.get("ingredient")) if raw_data is not None else [],
            "details_markdown": html_to_markdown(raw_content.get("ingredient")) if raw_data is not None else None,
            "web_description_markdown": html_to_markdown(raw_product.get("webIngredient")) if raw_data is not None else None,
        },
        "storage": {"instructions_text": html_to_markdown(raw_content.get("preservation")) if raw_data is not None else None},
        "provenance": {
            "evidence_status": "observed",
            "source_url": source_url,
            "captured_at": captured,
            "content_hash": content_hash,
            "raw_local_path": local_ref,
        },
        "extraction": {"version": EXTRACTION_VERSION, "status": status, "extracted_at": now.astimezone(timezone.utc)},
    }


def validate_local(document: dict[str, Any]) -> None:
    """Validate contract invariants before a MongoDB insert/upsert."""
    required = {"schema_version", "source", "source_product_key", "source_sku", "composition", "storage", "provenance", "extraction"}
    if not isinstance(document, dict) or set(document) != required:
        raise ValueError("Snapshot has missing or unexpected top-level fields")
    if document["schema_version"] != SCHEMA_VERSION or document["source"] != SOURCE_NAME:
        raise ValueError("Unsupported schema version or source")
    if document["source_sku"]:
        expected_key = "SKU:" + document["source_sku"]
        if document["source_product_key"] != expected_key:
            raise ValueError("source_product_key must preserve the source SKU exactly")
    elif not document["source_product_key"].startswith("URL:"):
        raise ValueError("Products without SKU must use a URL source key")
    composition = document["composition"]
    if set(composition) != {"basis_text", "items", "details_markdown", "web_description_markdown"}:
        raise ValueError("composition has missing or unexpected fields")
    if not isinstance(composition.get("items"), list):
        raise ValueError("composition.items must be an array")
    for item in composition["items"]:
        if not isinstance(item, dict) or set(item) != {"name", "description_text", "source_record_id", "source_ingredient_id", "source_is_primary", "source_slug"}:
            raise ValueError("Invalid composition item shape")
    if set(document["storage"]) != {"instructions_text"}:
        raise ValueError("storage has missing or unexpected fields")
    provenance = document["provenance"]
    if set(provenance) != {"evidence_status", "source_url", "captured_at", "content_hash", "raw_local_path"}:
        raise ValueError("provenance has missing or unexpected fields")
    if not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get("content_hash", ""))):
        raise ValueError("provenance.content_hash must be lowercase SHA-256")
    if not isinstance(provenance.get("captured_at"), datetime):
        raise ValueError("provenance.captured_at must be a datetime")
    extraction = document["extraction"]
    if set(extraction) != {"version", "status", "extracted_at"} or extraction.get("status") not in {"COMPLETE", "RAW_UNAVAILABLE", "PARSE_ERROR"}:
        raise ValueError("Invalid extraction metadata")
    if not isinstance(extraction.get("extracted_at"), datetime):
        raise ValueError("extraction.extracted_at must be a datetime")


def create_or_update_collection(database: Any) -> Any:
    """Ensure contract and indexes without dropping existing documents."""
    if COLLECTION_NAME not in database.list_collection_names():
        collection = database.create_collection(COLLECTION_NAME, validator=COLLECTION_VALIDATOR, validationLevel="strict", validationAction="error")
    else:
        collection = database[COLLECTION_NAME]
        database.command({"collMod": COLLECTION_NAME, "validator": COLLECTION_VALIDATOR, "validationLevel": "strict", "validationAction": "error"})
    for keys, options in INDEXES:
        collection.create_index(keys, **options)
    return collection


def load_frontmatter(note_path: Path) -> dict[str, Any]:
    with open(_local_open_path(note_path), "r", encoding="utf-8-sig") as handle:
        if handle.readline().strip() != "---":
            raise ValueError(f"Missing YAML frontmatter: {note_path}")
        lines: list[str] = []
        for line in handle:
            if line.strip() == "---":
                break
            lines.append(line)
        else:
            raise ValueError(f"Unterminated YAML frontmatter: {note_path}")
    if not lines:
        raise ValueError(f"Missing YAML frontmatter: {note_path}")
    value = yaml.safe_load("".join(lines)) or {}
    if not isinstance(value, dict):
        raise ValueError(f"Frontmatter must be a YAML object: {note_path}")
    return value


def product_notes(knowledge_root: Path) -> Iterable[Path]:
    for path in knowledge_root.rglob("*.md"):
        if "products" in path.relative_to(knowledge_root).parts:
            yield path
