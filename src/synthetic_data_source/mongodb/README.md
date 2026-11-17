# Long Châu product knowledge in MongoDB

## Purpose and data ownership

This package prepares and loads source-backed product-page facts from the local Long Châu knowledge base into MongoDB. It is a product-knowledge snapshot store; it is not a source of sales, dispensing, inventory, procurement, or supply facts.

In the target system architecture, this MongoDB collection is a separate document-shaped input source alongside the PostgreSQL source store. It supports the project's choice to distribute data across relational and document stores and to demonstrate handling heterogeneous data; no performance benchmark, database replication, or cross-database transaction is implied. Databricks ingestion is planned, while the web application's backend/API and operational database will be built separately. See [system architecture](../../../docs/architecture/pharmaflow-system-architecture.md), [data products by domain](../../../docs/architecture/pharmaflow-data-products.md), and [overall diagram](../../../artifacts/diagrams/architecture/pharmaflow-system-overview.html).

- Mongo target: database `pharmaflow_product_knowledge`, collection `product_snapshots`.
- Input: the project Long Châu knowledge tree `Dataset/longchau-knowledge/`. In this Windows checkout the CLI's default path is `dataset/longchau-knowledge`; pass `--kb-root` to override it.
- HTML captures remain local under the knowledge tree's `_raw/`. MongoDB stores extracted text and a local raw-file path. HTML is not stored in MongoDB or S3.
- The importer does not connect to Neon or write to PostgreSQL. PostgreSQL and MongoDB can be associated later by the same source SKU string; there is no cross-database foreign key or automatic replication.
- Evidence is marked as observed public-page data. It must remain distinct from simulated and operational PharmaFlow data.

## Document contract

Each document is one capture version, keyed by `(source, source_product_key, provenance.captured_at, provenance.content_hash)`. Different capture times or hashes are retained as history; an exact existing snapshot is skipped on retry.

| MongoDB field | Source mapping and meaning |
|---|---|
| `source` | `LONGCHAU_PUBLIC_PRODUCT_PAGE` |
| `source_sku` | Long Châu SKU, kept as a string so leading zeroes survive |
| `source_product_key` | `SKU:<sku>`; when SKU is absent, `URL:<canonical_url>` |
| `composition.basis_text` | `product.ingredientFor`, the source's basis for the listed composition |
| `composition.items[]` | Ordered entries from `product.ingredient[]` |
| `composition.items[].name` | Source ingredient name |
| `composition.items[].description_text` | `ingredient[].shortDescription`, preserved as text |
| `composition.items[].source_*` | Source record/ingredient IDs, primary flag, and slug when present |
| `composition.details_markdown` | Readable Markdown converted from `content.ingredient` |
| `composition.web_description_markdown` | Readable Markdown converted from `product.webIngredient` |
| `storage.instructions_text` | Readable text converted from `content.preservation` |
| `provenance.*` | Evidence status, source URL, capture time, content hash, and local raw path |
| `extraction.*` | Extractor version, extraction time, and `COMPLETE`, `RAW_UNAVAILABLE`, or `PARSE_ERROR` status |

The collection has a strict JSON Schema validator (`validationLevel: strict`, `validationAction: error`) and these indexes:

- `uq_product_capture`: unique snapshot identity `(source, source_product_key, captured_at, content_hash)`.
- `ix_source_product_history`: product history ordered by capture time, with `_id` as a tie-breaker.

The matching PostgreSQL reference is stored as `catalog.product_source_reference.external_product_key`; consumers can derive `SKU:<sku>` from the shared SKU and query `source_product_key`. URL-fallback records have no SKU join. The data does not infer ingredient amounts, active-ingredient status, packaging units, or storage instructions. Empty source fields remain null or empty; missing raw and parse failures do not create inferred facts.

## Connection and permissions

The connection helper loads the repository-root `.env` automatically. It reads `MONGODB_CONNECTION_STRING` (or `MONGODB_URI` as a fallback). If separate credentials are used, set both `USERNAME_MONGODB` and `PASSWORD_MONGODB`; the pair takes precedence over credentials embedded in the URI. The importer targets the database and collection constants above; it does not take them from the environment. Do not put credential values in this README or run reports.

Check network access and authentication with the read-only ping command:

```powershell
.\.venv\Scripts\python.exe .\src\synthetic_data_source\mongodb\check_connection.py
```

A successful ping confirms connectivity and authentication, not write privileges. Loading requires permission to create the collection when it is absent, create indexes, read, and insert/update documents. If the collection already exists but is empty and lacks the expected validator, the loader applies it with `collMod`; that case also requires `collMod` permission. A populated collection with an incompatible validator is left unchanged and the loader stops for review. Once the validator and indexes are in place, routine retries need only the target database's read/write and index privileges.

## Prepare, load, and verify

Run commands from the repository root with the project `.venv`. Use a new run ID for each `prepare`; reuse that same ID for `load`, `verify`, and any safe load retry.

```powershell
$runId = "lc-longchau-full-20261106-01" # choose an unused ID

.\.venv\Scripts\python.exe .\src\synthetic_data_source\mongodb\product_knowledge_cli.py prepare `
  --run-id $runId `
  --kb-root .\Dataset\longchau-knowledge

.\.venv\Scripts\python.exe .\src\synthetic_data_source\mongodb\product_knowledge_cli.py load `
  --run-id $runId --apply

.\.venv\Scripts\python.exe .\src\synthetic_data_source\mongodb\product_knowledge_cli.py verify `
  --run-id $runId
```

`prepare --limit N` is for a development bundle only. `prepare` refuses to reuse a non-empty run directory. A prepared run contains `documents.ejsonl`, `manifest.json`, `rejected.jsonl`, and then `load-result.json` and `verify-result.json` as those steps finish. The manifest includes the SHA-256 of the staged JSONL; load refuses changed or incomplete input. Timestamps are normalized to BSON Date millisecond precision before snapshot deduplication.

`load --apply` is the database-write command. It validates the prepared documents and collection contract, then upserts in batches of 200. It first loads at most ten samples across the available categories and reads them back; only a passing sample proceeds to the rest of the bundle. Exact existing snapshots are counted as `already_present`; new captures are inserted; conflicting content is reported without overwriting. The run must have zero rejected notes, and schema/legacy/duplicate-key conflicts stop the load. The loader never drops the collection or deletes documents.

If a load is interrupted, rerun `load --apply` with the same run ID. Existing equivalent snapshots are skipped, so retries are idempotent. `verify` is read-only and checks every staged snapshot's content plus the latest capture for each product key. Review both result files under `src/synthetic_data_source/mongodb/runs/<run-id>/`.

## Verified run

Run `lc-longchau-full-20261105-02` was prepared from 2,481 product notes with 0 rejected notes and 0 duplicate notes collapsed. Its manifest reports 2,481 snapshots, 2,480 product keys, 2,452 SKUs, and 28 URL-fallback records. Field coverage is 1,013 snapshots with a composition basis, 2,470 with ingredient items, and 2,451 with preservation text.

The recorded idempotent replay found all 2,481 snapshots already present. Full verification reported 2,481/2,481 snapshots verified, 0 missing, 0 mismatched, and 0 latest-product mismatches across 2,480 product keys. The corresponding manifest and result files are kept beside the prepared data in `runs/lc-longchau-full-20261105-02/`.
