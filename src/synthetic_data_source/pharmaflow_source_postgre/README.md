# PharmaFlow source PostgreSQL v2

This package owns the empty-database bootstrap, source mappings, deterministic sample/full preparation, sequential loaders, and run evidence for Long Châu, IRPD Indonesia, Onyx Pharmacy Sales, and Pharma Sales Data.

## Role in the PharmaFlow architecture

This PostgreSQL database is an **upstream simulated business source** for the DSS. It currently carries the prepared Sales & Demand inputs; the presence of inventory, procurement, or other domain tables in the schema does not mean those domains have been populated or are operational. The target data path is PostgreSQL/MongoDB source stores → Databricks Bronze/Silver/Gold → published data products → a separately built web backend/API. Databricks serves data and analytics; the web application will own its operational API and application database. See [system architecture](../../../docs/architecture/pharmaflow-system-architecture.md), [data products by domain](../../../docs/architecture/pharmaflow-data-products.md), and [overall diagram](../../../artifacts/diagrams/architecture/pharmaflow-system-overview.html).

The scope is the **source layer for later forecasting, KPI, and monitoring work**. It does not implement forecasting, inventory optimization, logistics, procurement, replenishment, or operational decisions. Existing procurement, inventory, transfer, stock-take, return, recall, quality-control, and customer-request tables remain in the schema and were not populated from these sales datasets.

## Current state — 2026-11-05

- Canonical fresh-database DDL: [`schema_full.sql`](schema_full.sql), version `20261104_01_forecast_source_contract_v2`.
- Full source database: Neon project `round-brook-76208048`, production branch `br-icy-lake-b3gg39qb`, database `pharmaflow_source_postgre_v2`.
- **One active Neon environment only:** production branch `br-icy-lake-b3gg39qb`, database `pharmaflow_source_postgre_v2` (ID `773750`). The local `.env` direct connection now targets this database.
- The previous database `pharmaflow_source_postgre` was deleted after its verified logical dump was retained. `neondb` was deleted and Neon Auth was disabled. The bounded-validation branch/database was deleted after acceptance; its run evidence remains historical and is not an active environment.
- Production v2 currently has 35 tables, 78,884 source observations, 393,942 sales orders, 714,959 sales lines, and 122 synthetic store-warehouse location records for stores with transaction-shaped data. These warehouse rows are explicitly `SYNTHETIC`; they are not evidence of stock, receipts, or confirmed fulfillment. Exact live table counts are in `runs/20261104-forecast-schema-v2/database/final-verification.json`.
- Bounded sample validation passed 7/7 acceptance tests before the test branch was retired. Treat those results as historical acceptance evidence. Full-source reconciliation passed for all four sources; the packaging/product pair constraints are installed and verified in production v2.
- On 2026-11-05, four official Long Châu medicine-page candidates were added to cover the four previously unmapped Pharma Sales groups. The mapping now has 14 distinct candidate SKUs across all 8 ATC groups. Their assignments remain `CANDIDATE`; the 4 new products have brands, manufacturers, and box descriptions, while product base UOM and package-to-unit conversion remain null. No ATC candidate was promoted to pharmacist-verified.
- The package configuration uses the v2 database as target. Credentials remain in the process environment or repository `.env`; they are not written to package config or run artifacts.

## Schema contract

The bootstrap preserves the existing 34-table local baseline and adds `pos.sales_observation`, for 35 tables total. Only the forecast-source contract in `catalog`, `org.store`, and POS order/line/observation tables changes; procurement, inventory, transfer, request, return, recall, quality-control, and proposal definitions remain. The code also enforces the distinction between observed source facts and generated POS records through separate fact tables and an auditable `source` value.

Versioned SQL artifacts:

- `sql/migrations/20261104_01_forecast_source_contract_v2.sql` is a psql wrapper for a **fresh empty database only**; it includes the canonical `schema_full.sql`. The Python bootstrap applies the same canonical file after its empty-database guard.
- `sql/migrations/20261104_02_product_packaging_pair_fk.sql` is an additive migration for the v2 production DB. Applied and verified at `2026-11-04T17:09:28Z`; it ensures a sales line's package belongs to that same product. It did not change row counts.
- `runs/20261104-forecast-schema-v2/baseline/schema_full.pre-v2.sql` and the accompanying checksums preserve the pre-change local bootstrap and review evidence. Neither versioned migration is intended for the old 24-table database.

## Sources and semantics

| Source | Stored facts | Simulated records | Deliberately not inferred |
|---|---|---|---|
| Long Châu | Public product/catalog/category and store-location evidence | None | Store sales, dispensing, stock, procurement, or fulfillment |
| IRPD Indonesia | Publisher-reported invoice and line data, preserving source units and `Asia/Jakarta` timestamps | One fictional Central Java store and deterministic coordinates | Original pharmacy identity/location; inventory movement; unsupported currency or unit conversions |
| Onyx Pharmacy Sales | Daily store × product facts with the source's revenue/cost/margin, retained as observations | One daily POS-like order per store with positive sales, at 12:00 local | Whether the challenge data represents real operations; exact unperturbed coordinates; dispensing or procurement facts |
| Pharma Sales Data | Daily ATC-group facts, with unknown source quantity unit left null | SKU-level POS simulation at scale 10 using 14 Long Châu candidate products across all 8 ATC groups | A source SKU, physical store, actual unit, invoice, or price |

`pos.sales_order` means source invoice transactions for IRPD or clearly identified simulated orders for Onyx/Pharma Sales. For each store appearing in prepared orders, the loader creates one `org.warehouse` row with a `SIM_STORE_WH::` code and `data_origin='SYNTHETIC'`; this satisfies the store-level location contract without claiming observed warehouse or stock facts. `fulfillment_location_id` and sales channel remain null unless the source confirms them. `pos.sales_observation` retains facts already aggregated by source. Do not sum a source observation and its generated synthetic POS counterpart as though they were two observed sales streams. No sale generates inventory, receipt, or procurement events.

Source field mappings are under `config/mappings/`. ATC candidate rules are in `config/mappings/pharma_sales_atc_products.yaml`; the four curated official Long Châu page references, ingredient evidence, route/form notes, and package labels are in `config/mappings/pharma_sales_longchau_candidates.csv`. They are pipeline supplements, not raw captures added to `Dataset/longchau-knowledge/`; no Long Châu taxonomy edge is inferred for them. Source profiles are in `config/sources/`. Original datasets remain at their source paths and are not modified.

## Repeatable workflow

The active full-source run is `runs/20261104-forecast-schema-v2/`; the 2026-11-05 expansion regenerated and reconciled Long Châu and Pharma Sales within that run. The pre-expansion outputs for those two sources are preserved under `runs/20261105-pharma-sales-atc-expansion/baseline/`. Source execution order is Long Châu → IRPD → Onyx → Pharma Sales.

1. `source_cli.py prepare <source>` profiles and prepares all source rows; `prepare-sample <source>` writes a deterministic bounded sample and manifest beside that source's run output.
2. The prior bounded samples and 7/7 acceptance run are retained under `runs/20261104-forecast-schema-v2/test/`. `scripts/run_test_branch_samples.ps1` now stops before asking for a URL because the test branch was retired and the project is single-environment.
3. Full data is loaded only into `pharmaflow_source_postgre_v2`. Use `scripts/run_neon.ps1` with `load <source> full` and `verify <source> full` in source order; the current run's full loads have already been reconciled. The existing full-load acceptance markers preserve the earlier sample gate.
4. `source_cli.py report --database pharmaflow_source_postgre_v2` and `verify all` create final full-run evidence. The CLI accepts only the active target for database operations; sample loads are disabled in single-environment mode.

Example PowerShell commands from the repository root:

```powershell
& .\src\synthetic_data_source\pharmaflow_source_postgre\scripts\run_test_branch_samples.ps1
& .\.venv\Scripts\python.exe -B .\src\synthetic_data_source\pharmaflow_source_postgre\scripts\source_cli.py report --database pharmaflow_source_postgre_v2
& .\.venv\Scripts\python.exe -B .\src\synthetic_data_source\pharmaflow_source_postgre\scripts\source_cli.py verify all --database pharmaflow_source_postgre_v2
```

The previous database dump is `runs/20261104-forecast-schema-v2/backup/pharmaflow_source_postgre-pre-v2.dump` (SHA-256 `0913a148e72dda4634219043243bde0ba9cd3bc8cc2cddde4f7744c0cfafa0c5`); its manifest records 24 tables and 0 rows. The existing Neon snapshot `snap-tiny-glade-b3ttso51` remains; a new snapshot attempt was rejected by the snapshot quota. The old database and the bounded test branch were subsequently deleted by request after acceptance; the dump and test evidence remain local.

## Bounded samples and full-load summary

| Source | Test sample | Full v2 load | Synthetic store-warehouse rows | Validation boundary |
|---|---:|---:|---:|---|
| Long Châu | 50 products across five taxonomy roots; 20 stores; no sales | 2,482 products; 297 categories; 7,394 observed-taxonomy assignments; 2,694 stores | 0 | Public catalog/location only; 4 curated official product pages supplement the source mapping |
| IRPD Indonesia | First 7 sales dates; 2,508 complete invoices / 4,641 lines; 1 simulated store | 349,196 orders; 627,389 lines; 2,972 products; 1 simulated store | 1 | Total order value derives from line `TotalPrice`; stock files excluded |
| Onyx | Five pharmacies × 14 source fact dates; 100 observations; 70 simulated orders / 100 lines | 62,036 unique daily facts; 120 stores; 42,666 simulated orders / 62,036 lines | 120 | Duplicate source fact-grain rows rejected; provenance and coordinates unverified |
| Pharma Sales Data | 28 source days; 224 observations; 27 simulated orders / 236 lines | 16,848 observations; 2,080 simulated orders / 25,534 lines | 1 | Eight ATC groups; no source UOM/price; 14 SKU mappings remain candidates |

Full source counts and reconciliation evidence are recorded under each `runs/20261104-forecast-schema-v2/<source>/` folder; the all-table production count snapshot is `runs/20261104-forecast-schema-v2/database/final-verification.json`. The 2026-11-05 output comparison and write evidence are in [`runs/20261105-pharma-sales-atc-expansion/`](runs/20261105-pharma-sales-atc-expansion/README.md). Test-branch sample markers and JUnit results are recorded under `runs/20261104-forecast-schema-v2/test/forecast-validation-20261104/`. A source is marked verified only against the manifest hash that was loaded.

## Diagram and data dictionary

- Conceptual source overview: [`forecast_schema_overview.html`](forecast_schema_overview.html).
- Physical v2 schema with SQL types and key constraints: [`forecast_source_schema_v2.html`](forecast_source_schema_v2.html), generated by `scripts/render_forecast_source_schema.py`.
- Data dictionary: [`docs/data-model/Relations-DataSource/README.md`](../../../docs/data-model/Relations-DataSource/README.md), with the current v2 source section clearly separated from v1 history and downstream proposal material.
- Physical source DDL: [`schema_full.sql`](schema_full.sql).

The core concept remains `DATA → FORECAST → RISK → DECISION → OPERATIONAL OUTCOME`; this package supplies source data only. Forecast models, temporal backtesting, KPI monitoring, decision logic, and logistics optimization are outside this implementation.
