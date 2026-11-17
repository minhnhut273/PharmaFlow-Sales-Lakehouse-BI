"""Offline tests for the Long Chau MongoDB contract and run bundle."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from bson import ObjectId
from pymongo.errors import CollectionInvalid

from product_knowledge import (
    COLLECTION_NAME, COLLECTION_VALIDATOR, DATABASE_NAME, INDEXES, SOURCE_NAME, build_snapshot,
    canonical_source_key, html_to_markdown, load_frontmatter, validate_local,
)


ROOT = Path(__file__).resolve().parents[3]
KB = ROOT / "dataset" / "longchau-knowledge"


class ProductKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metformin_note = (
            next(
                (
                    path for path in KB.rglob("*.md")
                    if path.parent.name == "products" and path.name.startswith("vien-nen-metformin-stella-")
                ),
                None,
            )
            if KB.exists()
            else None
        )

    def _require_metformin_note(self):
        if self.metformin_note is None:
            self.skipTest("Local dataset/longchau-knowledge HTML fixtures are excluded from standalone repository.")
        return self.metformin_note

    def test_contract_uses_shared_sku_and_snapshot_indexes(self):
        self.assertEqual(DATABASE_NAME, "pharmaflow_product_knowledge")
        self.assertEqual(COLLECTION_NAME, "product_snapshots")
        self.assertEqual(len(INDEXES), 2)
        self.assertTrue(INDEXES[0][1]["unique"])
        self.assertEqual(SOURCE_NAME, "LONGCHAU_PUBLIC_PRODUCT_PAGE")

    def test_existing_empty_collection_gets_validator_when_pymongo_raises_collection_invalid(self):
        from product_knowledge_cli import _check_existing_collection

        class FakeCollection:
            def __init__(self):
                self.created_indexes = []

            def count_documents(self, query, limit=0):
                return 0

            def find(self, query, projection=None):
                return []

            def aggregate(self, pipeline):
                return []

            def create_index(self, keys, **options):
                self.created_indexes.append((keys, options))

        class FakeDatabase:
            def __init__(self):
                self.collection = FakeCollection()
                self.options = {}
                self.commands = []

            def create_collection(self, name, **options):
                raise CollectionInvalid(f"collection {name} already exists")

            def __getitem__(self, name):
                return self.collection

            def command(self, command):
                self.commands.append(command)
                if "listCollections" in command:
                    return {"cursor": {"firstBatch": [{"name": COLLECTION_NAME, "options": self.options}]}}
                if "collMod" in command:
                    self.options = {
                        "validator": command["validator"],
                        "validationLevel": command["validationLevel"],
                        "validationAction": command["validationAction"],
                    }
                    return {"ok": 1}
                raise AssertionError(f"unexpected command: {command}")

        database = FakeDatabase()
        collection = _check_existing_collection(database, COLLECTION_NAME)

        self.assertIs(collection, database.collection)
        self.assertEqual(database.options["validator"], COLLECTION_VALIDATOR)
        self.assertEqual(database.options["validationLevel"], "strict")
        self.assertEqual(database.options["validationAction"], "error")
        self.assertEqual(len(collection.created_indexes), len(INDEXES))

    def test_snapshot_identity_normalizes_naive_bson_timestamp(self):
        from product_knowledge_cli import _snapshot_identity

        note = self._require_metformin_note()
        document = build_snapshot(load_frontmatter(note), note, KB)
        document["provenance"]["captured_at"] = datetime(2026, 10, 11, 12, 28, 32, 320999, tzinfo=timezone.utc)
        naive_document = deepcopy(document)
        naive_document["provenance"]["captured_at"] = naive_document["provenance"]["captured_at"].replace(tzinfo=None)

        self.assertEqual(_snapshot_identity(document), _snapshot_identity(naive_document))

    def test_load_report_combines_sample_and_remaining_counts(self):
        from product_knowledge_cli import _combine_load_stats

        self.assertEqual(
            _combine_load_stats({"inserted": 10}, {"inserted": 2471}),
            {"inserted": 2481},
        )
        self.assertEqual(
            _combine_load_stats({"already_present": 10}, {"already_present": 2471}),
            {"already_present": 2481},
        )

    def test_source_key_preserves_sku_zeroes_and_url_fallback(self):
        self.assertEqual(canonical_source_key("00004875", "https://example.test/p"), "SKU:00004875")
        self.assertEqual(canonical_source_key(None, "https://example.test/p"), "URL:https://example.test/p")
        with self.assertRaises(ValueError):
            canonical_source_key(None, "")

    def test_html_conversion_keeps_paragraphs_and_table_rows(self):
        result = html_to_markdown("<p>Store safely</p><table><tr><th>Name</th><th>Amount</th></tr><tr><td>Vitamin C</td><td>150mg</td></tr></table>")
        self.assertIn("Store safely", result)
        self.assertIn("| Vitamin C | 150mg |", result)

    def test_metformin_capture_maps_three_facts_and_provenance(self):
        note = self._require_metformin_note()
        doc = build_snapshot(load_frontmatter(note), note, KB)
        validate_local(doc)
        self.assertEqual(doc["source_sku"], "00004875")
        self.assertEqual(doc["source_product_key"], "SKU:00004875")
        self.assertNotIn("postgres_ref", doc)
        self.assertEqual(doc["composition"]["basis_text"], "1 viên")
        self.assertEqual(doc["composition"]["items"][0]["description_text"], "850mg")
        self.assertIn("dưới 30", doc["storage"]["instructions_text"])
        self.assertTrue(doc["provenance"]["raw_local_path"].endswith("1f9b966ae976de01283c18975342030df5421af80eec438ac189ae3fd2418dac.html"))
        self.assertNotIn("html", doc["provenance"])

    def test_missing_raw_leaves_source_facts_unknown(self):
        note = self._require_metformin_note()
        metadata = load_frontmatter(note)
        metadata["raw_snapshot"] = "_raw/" + "0" * 64 + ".html"
        doc = build_snapshot(metadata, note, KB)
        self.assertEqual(doc["extraction"]["status"], "RAW_UNAVAILABLE")
        self.assertIsNone(doc["composition"]["basis_text"])
        self.assertEqual(doc["composition"]["items"], [])
        self.assertIsNone(doc["storage"]["instructions_text"])

    def test_invalid_raw_payload_is_parse_error_and_has_no_inferred_facts(self):
        note = self._require_metformin_note()
        metadata = load_frontmatter(note)
        # Avoid writing to the KB: the parser failure branch is represented by a non-JSON payload via patching.
        from unittest.mock import patch
        import product_knowledge
        with patch.object(product_knowledge, "_read_local_text", return_value="<html>no next data</html>"):
            doc = build_snapshot(metadata, note, KB)
        self.assertEqual(doc["extraction"]["status"], "PARSE_ERROR")
        self.assertIsNone(doc["composition"]["basis_text"])
        self.assertEqual(doc["composition"]["items"], [])
        self.assertIsNone(doc["storage"]["instructions_text"])

    def test_validator_rejects_mismatched_sku_key_extra_postgres_and_bad_hash(self):
        note = self._require_metformin_note()
        doc = build_snapshot(load_frontmatter(note), note, KB)
        doc["source_product_key"] = "SKU:4875"
        with self.assertRaises(ValueError):
            validate_local(doc)
        doc = build_snapshot(load_frontmatter(note), note, KB)
        doc["postgres_ref"] = {}
        with self.assertRaises(ValueError):
            validate_local(doc)
        doc = build_snapshot(load_frontmatter(note), note, KB)
        doc["composition"]["items"] = []
        validate_local(doc)
        doc["provenance"]["content_hash"] = "bad"
        with self.assertRaises(ValueError):
            validate_local(doc)

    def test_load_is_idempotent_and_keeps_new_capture_history(self):
        from product_knowledge_cli import _load_documents, _verify_all

        class FakeCollection:
            def __init__(self):
                self.docs = []
                self.find_one_calls = 0
                self.aggregate_calls = 0

            @staticmethod
            def matches(document, query):
                if "$or" in query:
                    return any(FakeCollection.matches(document, item) for item in query["$or"])
                for key, expected in query.items():
                    value = document
                    for part in key.split("."):
                        value = value.get(part) if isinstance(value, dict) else None
                    if isinstance(expected, dict) and "$in" in expected:
                        if value not in expected["$in"]:
                            return False
                        continue
                    if value != expected:
                        return False
                return True

            def find(self, query):
                return [deepcopy(doc) for doc in self.docs if self.matches(doc, query)]

            def bulk_write(self, operations, ordered=False):
                inserted = 0
                for operation in operations:
                    if any(self.matches(doc, operation._filter) for doc in self.docs):
                        continue
                    doc = deepcopy(operation._doc["$setOnInsert"])
                    doc["_id"] = ObjectId()
                    self.docs.append(doc)
                    inserted += 1
                return SimpleNamespace(upserted_count=inserted)

            def find_one(self, query, sort=None):
                self.find_one_calls += 1
                found = self.find(query)
                if sort:
                    for key, direction in reversed(sort):
                        found.sort(key=lambda doc: _deep_value(doc, key), reverse=direction < 0)
                return found[0] if found else None

            def aggregate(self, pipeline):
                self.aggregate_calls += 1
                found = deepcopy(self.docs)
                for stage in pipeline:
                    if "$match" in stage:
                        found = [doc for doc in found if self.matches(doc, stage["$match"])]
                    elif "$sort" in stage:
                        for key, direction in reversed(list(stage["$sort"].items())):
                            found.sort(key=lambda doc: _deep_value(doc, key), reverse=direction < 0)
                    elif "$group" in stage:
                        grouped = {}
                        for doc in found:
                            key = (doc["source"], doc["source_product_key"])
                            grouped.setdefault(key, {"_id": key, "latest": doc})
                        found = list(grouped.values())
                    elif "$replaceRoot" in stage:
                        found = [item["latest"] for item in found]
                return found

        def _deep_value(document, key):
            value = document
            for part in key.split("."):
                value = value.get(part) if isinstance(value, dict) else None
            return value

        note = self._require_metformin_note()
        doc = build_snapshot(load_frontmatter(note), note, KB)
        collection = FakeCollection()
        self.assertEqual(_load_documents(collection, [doc]), {"inserted": 1})
        self.assertEqual(_load_documents(collection, [doc]), {"already_present": 1})
        newer = deepcopy(doc)
        newer["provenance"]["captured_at"] += timedelta(seconds=1)
        newer["provenance"]["content_hash"] = "f" + newer["provenance"]["content_hash"][1:]
        self.assertEqual(_load_documents(collection, [newer]), {"inserted": 1})
        self.assertEqual(len(collection.docs), 2)
        report = _verify_all(collection, [doc, newer])
        self.assertEqual(report["missing"], 0)
        self.assertEqual(report["mismatched"], 0)
        self.assertEqual(report["latest_product_mismatches"], 0)
        self.assertEqual(collection.find_one_calls, 0)
        self.assertEqual(collection.aggregate_calls, 1)


if __name__ == "__main__":
    unittest.main()
