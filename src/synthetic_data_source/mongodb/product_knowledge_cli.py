"""Prepare, load and verify Long Chau product knowledge snapshots."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from bson.json_util import CANONICAL_JSON_OPTIONS, dumps, loads
from pymongo import UpdateOne
from pymongo.errors import CollectionInvalid

from connection import connect_mongodb
from product_knowledge import (
    COLLECTION_NAME, COLLECTION_VALIDATOR, DATABASE_NAME, INDEXES,
    SOURCE_NAME, build_snapshot, canonical_source_key, load_frontmatter, product_notes,
    validate_local,
)


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
DEFAULT_KB_ROOT = PROJECT_ROOT / "dataset" / "longchau-knowledge"
RUNS_ROOT = HERE / "runs"
BATCH_SIZE = 200


def _run_dir(run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id):
        raise ValueError("run-id must use 1-80 letters, digits, dots, underscores or hyphens")
    return RUNS_ROOT / run_id


def _normalize_bson_date(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def _semantic_document(document: dict[str, Any]) -> str:
    comparable = deepcopy(document)
    comparable.pop("_id", None)
    comparable.get("extraction", {}).pop("extracted_at", None)
    return dumps(comparable, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True)


def _snapshot_identity(document: dict[str, Any]) -> tuple[Any, ...]:
    provenance = document["provenance"]
    return (
        document["source"],
        document["source_product_key"],
        _normalize_bson_date(provenance["captured_at"]),
        provenance["content_hash"],
    )


def prepare(run_id: str, kb_root: Path, limit: int = 0) -> dict[str, Any]:
    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    if any(run_dir.iterdir()):
        raise FileExistsError(f"Run directory already contains data: {run_dir}")
    now = _normalize_bson_date(datetime.now(timezone.utc))
    stats = Counter()
    docs: dict[tuple[Any, ...], dict[str, Any]] = {}
    doc_categories: dict[tuple[Any, ...], set[str]] = {}
    errors: list[dict[str, str]] = []
    notes = sorted(product_notes(kb_root), key=lambda p: p.as_posix())
    if limit:
        notes = notes[:limit]

    # Inventory YAML metadata first so duplicate category notes do not reread the same raw capture.
    candidates: dict[tuple[Any, ...], list[tuple[Path, dict[str, Any], str]]] = {}
    for note in notes:
        stats["notes_discovered"] += 1
        try:
            metadata = load_frontmatter(note)
            if metadata.get("page_type") != "product_detail":
                stats["non_product_notes"] += 1
                continue
            stats["product_notes"] += 1
            product = metadata.get("product") or {}
            attrs = product.get("other_public_attributes") or {}
            sku = attrs.get("sku")
            sku = sku.strip() if isinstance(sku, str) and sku.strip() else None
            url = metadata.get("canonical_url") or product.get("canonical_url") or metadata.get("source_url")
            if not isinstance(url, str) or not url.strip():
                raise ValueError("missing canonical/source URL")
            crawl = metadata.get("crawl") or {}
            captured = crawl.get("crawled_at") or crawl.get("captured_at")
            if isinstance(captured, str):
                captured = datetime.fromisoformat(captured.replace("Z", "+00:00"))
            if not isinstance(captured, datetime):
                raise ValueError("missing capture timestamp")
            content_hash = crawl.get("content_hash")
            if not isinstance(content_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", content_hash):
                raise ValueError("missing or invalid capture SHA-256")
            key = (SOURCE_NAME, canonical_source_key(sku, url), _normalize_bson_date(captured), content_hash)
            parts = note.relative_to(kb_root).parts
            category = parts[0] if parts else "unknown"
            candidates.setdefault(key, []).append((note, metadata, category))
        except Exception as exc:
            stats["rejected_notes"] += 1
            errors.append({"note": note.relative_to(kb_root).as_posix(), "error": f"{type(exc).__name__}: {exc}"})

    stats["duplicate_notes_collapsed"] = sum(max(0, len(group) - 1) for group in candidates.values())
    for key in sorted(candidates, key=lambda identity: (identity[1], identity[2], identity[3])):
        note, metadata, _ = candidates[key][0]
        doc_categories[key] = {category for _, _, category in candidates[key]}
        try:
            document = build_snapshot(metadata, note, kb_root, extracted_at=now)
            document["provenance"]["captured_at"] = _normalize_bson_date(document["provenance"]["captured_at"])
            validate_local(document)
            docs[key] = document
            stats["status_" + document["extraction"]["status"]] += 1
        except Exception as exc:
            stats["rejected_notes"] += 1
            errors.append({"note": note.relative_to(kb_root).as_posix(), "error": f"{type(exc).__name__}: {exc}"})

    documents = sorted(docs.values(), key=lambda doc: (_snapshot_identity(doc)[1], _snapshot_identity(doc)[2], _snapshot_identity(doc)[3]))
    unique_keys = sorted({doc["source_product_key"] for doc in documents})
    stats["unique_snapshots"] = len(documents)
    stats["unique_product_keys"] = len(unique_keys)
    stats["unique_skus"] = len({doc["source_sku"] for doc in documents if doc["source_sku"]})
    stats["snapshots_without_sku"] = sum(not doc["source_sku"] for doc in documents)
    for field, present in (
        ("basis_text", lambda d: bool(d["composition"]["basis_text"])),
        ("ingredient_items", lambda d: bool(d["composition"]["items"])),
        ("storage_text", lambda d: bool(d["storage"]["instructions_text"])),
    ):
        stats[field + "_present"] = sum(present(doc) for doc in documents)
        stats[field + "_empty"] = len(documents) - stats[field + "_present"]

    # Choose one capture from as many categories as possible for the live sample load.
    sample_keys: list[tuple[Any, ...]] = []
    covered: set[str] = set()
    for key in sorted(docs, key=lambda k: (sorted(doc_categories[k])[0], k[1], k[2], k[3])):
        new_categories = doc_categories[key] - covered
        if new_categories:
            sample_keys.append(key)
            covered.update(new_categories)
    if len(sample_keys) < min(10, len(documents)):
        for doc in documents:
            key = _snapshot_identity(doc)
            if key not in sample_keys:
                sample_keys.append(key)
            if len(sample_keys) == min(10, len(documents)):
                break
    sample_ids = [[key[0], key[1], key[2].isoformat(), key[3]] for key in sample_keys[:10]]

    data_path = run_dir / "documents.ejsonl"
    with data_path.open("w", encoding="utf-8", newline="\n") as handle:
        for document in documents:
            handle.write(dumps(document, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True) + "\n")
    reject_path = run_dir / "rejected.jsonl"
    with reject_path.open("w", encoding="utf-8", newline="\n") as handle:
        for error in errors:
            handle.write(json.dumps(error, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {
        "run_id": run_id,
        "created_at": now.isoformat(),
        "source": "LONGCHAU_PUBLIC_PRODUCT_PAGE",
        "database": DATABASE_NAME,
        "collection": COLLECTION_NAME,
        "schema_version": 1,
        "data_file": data_path.name,
        "data_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "rejected_file": reject_path.name,
        "stats": dict(sorted(stats.items())),
        "sample_snapshot_ids": sample_ids,
        "load_status": "PREPARED",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _load_run(run_id: str) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    run_dir = _run_dir(run_id)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    data_path = run_dir / manifest["data_file"]
    actual_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
    if actual_hash != manifest.get("data_sha256"):
        raise ValueError("staged data checksum differs from manifest")
    documents = [loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(documents) != manifest["stats"]["unique_snapshots"]:
        raise ValueError("staged document count differs from manifest")
    if manifest["stats"].get("rejected_notes", 0):
        raise ValueError("prepared run has rejected notes; resolve them before loading")
    for document in documents:
        validate_local(document)
    if not documents:
        raise ValueError("prepared run contains no valid snapshots")
    return run_dir, manifest, documents


def _check_existing_collection(database: Any, collection_name: str) -> Any:
    try:
        collection = database.create_collection(collection_name, validator=COLLECTION_VALIDATOR, validationLevel="strict", validationAction="error")
    except Exception as exc:
        if getattr(exc, "code", None) != 48 and not isinstance(exc, CollectionInvalid):
            raise
        collection = database[collection_name]
        listed = database.command({
            "listCollections": 1,
            "filter": {"name": collection_name},
            "nameOnly": False,
        }).get("cursor", {}).get("firstBatch", [])
        if not listed:
            raise RuntimeError("Target collection exists but its options could not be read")
        options = listed[0].get("options", {})
        if (
            options.get("validator") != COLLECTION_VALIDATOR
            or options.get("validationLevel") != "strict"
            or options.get("validationAction") != "error"
        ):
            if collection.count_documents({}) != 0:
                raise RuntimeError("Existing non-empty collection validator differs; dbAdmin migration is required before loading")
            database.command({
                "collMod": collection_name,
                "validator": COLLECTION_VALIDATOR,
                "validationLevel": "strict",
                "validationAction": "error",
            })
            listed = database.command({
                "listCollections": 1,
                "filter": {"name": collection_name},
                "nameOnly": False,
            }).get("cursor", {}).get("firstBatch", [])
            options = listed[0].get("options", {}) if listed else {}
            if (
                options.get("validator") != COLLECTION_VALIDATOR
                or options.get("validationLevel") != "strict"
                or options.get("validationAction") != "error"
            ):
                raise RuntimeError("Failed to apply the expected validator to the empty collection")
        legacy = collection.count_documents({"$or": [
            {"postgres_ref": {"$exists": True}},
            {"schema_version": {"$ne": 1}},
            {"source_product_key": {"$exists": False}},
            {"provenance.captured_at": {"$exists": False}},
        ]}, limit=1)
        if legacy:
            raise RuntimeError("Collection has documents outside the SKU-only contract; no database changes made")
        for existing in collection.find({}, {"_id": 0}):
            validate_local(existing)
        duplicate = list(collection.aggregate([
            {"$group": {"_id": {"source": "$source", "key": "$source_product_key", "captured_at": "$provenance.captured_at", "hash": "$provenance.content_hash"}, "n": {"$sum": 1}}},
            {"$match": {"n": {"$gt": 1}}}, {"$limit": 1},
        ]))
        if duplicate:
            raise RuntimeError("Collection contains duplicate snapshot keys; no database changes made")
    for keys, options in INDEXES:
        collection.create_index(keys, **options)
    return collection


def _doc_key_filter(document: dict[str, Any]) -> dict[str, Any]:
    return {"source": document["source"], "source_product_key": document["source_product_key"], "provenance.captured_at": document["provenance"]["captured_at"], "provenance.content_hash": document["provenance"]["content_hash"]}


def _load_documents(collection: Any, documents: list[dict[str, Any]]) -> dict[str, int]:
    stats = Counter()
    for offset in range(0, len(documents), BATCH_SIZE):
        batch = documents[offset:offset + BATCH_SIZE]
        filters = [_doc_key_filter(doc) for doc in batch]
        existing_by_id: dict[tuple[Any, ...], dict[str, Any]] = {}
        for existing in collection.find({"$or": filters}):
            existing_by_id[_snapshot_identity(existing)] = existing
        ops = []
        for document in batch:
            existing = existing_by_id.get(_snapshot_identity(document))
            if existing is not None:
                if _semantic_document(existing) != _semantic_document(document):
                    stats["conflicts"] += 1
                else:
                    stats["already_present"] += 1
                continue
            ops.append(UpdateOne(_doc_key_filter(document), {"$setOnInsert": document}, upsert=True))
        if ops:
            result = collection.bulk_write(ops, ordered=False)
            stats["inserted"] += result.upserted_count
    return dict(stats)


def _combine_load_stats(*results: dict[str, int]) -> dict[str, int]:
    combined = Counter()
    for result in results:
        combined.update(result)
    return dict(combined)


def _verify_sample(collection: Any, documents: list[dict[str, Any]], sample_ids: list[list[Any]]) -> int:
    by_identity = {_snapshot_identity(doc): doc for doc in documents}
    checked = 0
    for values in sample_ids:
        key = (values[0], values[1], _normalize_bson_date(datetime.fromisoformat(values[2])), values[3])
        expected = by_identity[key]
        actual = collection.find_one(_doc_key_filter(expected))
        if actual is None or _semantic_document(actual) != _semantic_document(expected):
            raise RuntimeError(f"sample read-back mismatch for {expected['source_product_key']}")
        checked += 1
    return checked


def _verify_all(collection: Any, documents: list[dict[str, Any]]) -> dict[str, Any]:
    expected_by_identity = {_snapshot_identity(document): document for document in documents}
    latest_expected: dict[tuple[str, str], dict[str, Any]] = {}
    keys_by_source: dict[str, set[str]] = {}
    for expected in documents:
        identity = _snapshot_identity(expected)
        product_key = (expected["source"], expected["source_product_key"])
        keys_by_source.setdefault(expected["source"], set()).add(expected["source_product_key"])
        latest = latest_expected.get(product_key)
        if latest is None or identity[2] > latest["captured_at"]:
            latest_expected[product_key] = {"captured_at": identity[2], "identities": {identity}}
        elif identity[2] == latest["captured_at"]:
            latest["identities"].add(identity)

    match = {"$or": [
        {"source": source, "source_product_key": {"$in": sorted(source_keys)}}
        for source, source_keys in sorted(keys_by_source.items())
    ]}
    actual_by_identity = {}
    latest_actual = {}
    pipeline = [
        {"$match": match},
        {"$sort": {"source": 1, "source_product_key": 1, "provenance.captured_at": -1, "_id": -1}},
    ]
    for actual in collection.aggregate(pipeline):
        identity = _snapshot_identity(actual)
        actual_by_identity[identity] = actual
        product_key = (actual["source"], actual["source_product_key"])
        latest_actual.setdefault(product_key, actual)

    missing = 0
    mismatched = 0
    for identity, expected in expected_by_identity.items():
        actual = actual_by_identity.get(identity)
        if actual is None:
            missing += 1
        elif _semantic_document(actual) != _semantic_document(expected):
            mismatched += 1
    latest_mismatched = sum(
        1
        for product_key, expected in latest_expected.items()
        if product_key not in latest_actual
        or _snapshot_identity(latest_actual[product_key]) not in expected["identities"]
    )
    return {
        "expected_snapshots": len(documents),
        "verified_snapshots": len(documents) - missing - mismatched,
        "missing": missing,
        "mismatched": mismatched,
        "expected_products": len(latest_expected),
        "latest_product_mismatches": latest_mismatched,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="Read the local KB and write a checksummed run bundle.")
    prep.add_argument("--run-id", required=True)
    prep.add_argument("--kb-root", type=Path, default=DEFAULT_KB_ROOT)
    prep.add_argument("--limit", type=int, default=0, help="Optional development limit; omit for all notes.")
    load = commands.add_parser("load", help="Load a prepared bundle into MongoDB.")
    load.add_argument("--run-id", required=True)
    load.add_argument("--apply", action="store_true", required=True, help="Confirm writes to the dedicated product knowledge database.")
    verify = commands.add_parser("verify", help="Read back all expected snapshots from MongoDB.")
    verify.add_argument("--run-id", required=True)
    args = parser.parse_args()

    load_stage = None
    try:
        if args.command == "prepare":
            if not args.kb_root.is_dir():
                raise ValueError(f"Knowledge base directory does not exist: {args.kb_root}")
            manifest = prepare(args.run_id, args.kb_root, args.limit)
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0 if manifest["stats"].get("rejected_notes", 0) == 0 else 2

        run_dir, manifest, documents = _load_run(args.run_id)
        if args.command == "load":
            load_stage = "connecting"
        client, database, _ = connect_mongodb(database_name=DATABASE_NAME, collection_name=COLLECTION_NAME)
        try:
            if args.command == "load":
                load_stage = "preflighting_collection"
                collection = _check_existing_collection(database, COLLECTION_NAME)
                load_stage = "loading_sample"
                sample_keys = {(key[0], key[1], _normalize_bson_date(datetime.fromisoformat(key[2])), key[3]) for key in manifest["sample_snapshot_ids"]}
                by_key = {_snapshot_identity(doc): doc for doc in documents}
                sample = [by_key[key] for key in sample_keys]
                sample_result = _load_documents(collection, sample)
                sample_verified = _verify_sample(collection, sample, manifest["sample_snapshot_ids"])
                if sample_result.get("conflicts"):
                    raise RuntimeError(f"sample load found {sample_result['conflicts']} conflicting snapshots")
                sample_set = set(sample_keys)
                remaining = [doc for doc in documents if _snapshot_identity(doc) not in sample_set]
                load_stage = "loading_full_run"
                result = _load_documents(collection, remaining)
                if result.get("conflicts"):
                    raise RuntimeError(f"full load found {result['conflicts']} conflicting snapshots")
                load_result = {
                    "sample_verified": sample_verified,
                    "sample_result": sample_result,
                    "remaining_result": result,
                    **_combine_load_stats(sample_result, result),
                    "loaded_at": datetime.now(timezone.utc).isoformat(),
                }
                load_result["status"] = "LOADED"
                (run_dir / "load-result.json").write_text(json.dumps(load_result, indent=2) + "\n", encoding="utf-8")
                load_stage = "loaded"
                print(json.dumps(load_result, indent=2))
                return 0
            report = _verify_all(database[COLLECTION_NAME], documents)
            (run_dir / "verify-result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 0 if not any(report[k] for k in ("missing", "mismatched", "latest_product_mismatches")) else 3
        finally:
            client.close()
    except Exception as exc:
        if args.command == "load":
            try:
                run_dir = _run_dir(args.run_id)
                load_result = {
                    "status": "FAILED_BEFORE_DATABASE_WRITE" if load_stage == "connecting" else "FAILED",
                    "stage": load_stage,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                }
                (run_dir / "load-result.json").write_text(json.dumps(load_result, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
