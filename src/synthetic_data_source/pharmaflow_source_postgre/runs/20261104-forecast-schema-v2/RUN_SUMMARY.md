# Forecast source rebuild — run summary

Run ID: `20261104-forecast-schema-v2`

Completed: `2026-11-04`

Package: `src/synthetic_data_source/pharmaflow_source_postgre/`

## Later Neon cleanup — current state checked 2026-11-05

After the source load and 7/7 sample acceptance, the user requested one environment only. Neon now has one branch (`production`, `br-icy-lake-b3gg39qb`) and one database (`pharmaflow_source_postgre_v2`, ID `773750`). The previous `pharmaflow_source_postgre` database was deleted after its verified dump was retained; the test branch/database was deleted; `neondb` was deleted and Neon Auth is disabled. The old sample run outputs below are historical evidence, not active resources. The repository `.env` and package CLI now target only v2.

## Safety boundary

- Before any Neon database change, created branch snapshot `snap-tiny-glade-b3ttso51` (`before-pharmaflow-source-postgre-v2-20261104`). The snapshot metadata and the pre-run checksums are in `backup/` and `baseline/`.
- Created and loaded the new database `pharmaflow_source_postgre_v2` (Neon database ID `773750`) on branch `br-icy-lake-b3gg39qb`.
- At completion of this initial run, the prior database `pharmaflow_source_postgre` was unchanged. Its pre-change check reported 24 base tables and 0 estimated live rows. The later, separately requested cleanup is recorded above.
- Did not edit or move the source dataset files.

## Schema result

`schema_full.sql` bootstrapped successfully in the new empty database: 35 tables on PostgreSQL 18.6. It retains procurement, inventory, transfer, stock-take, request, return, recall, and quality-control tables. Forecast-source changes are limited to the compact catalog contract, store geography/timezone, POS transaction fields, and `pos.sales_observation`.

No order row created inventory movements, receipts, procurement records, or fulfillment links. Unreported sales channels and fulfillment locations remain null. Source versus simulation is recorded in `source` labels.

## Per-source preparation and load

| Source | Prepared and loaded full grain | Handling rules | Result |
|---|---:|---|---|
| Long Châu | 2,478 products; 297 taxonomy nodes; 7,394 assignments; 2,694 stores | Public catalog and locator only; duplicate page captures merged; fallback product keys are URL-based when a source SKU is absent | Sample and full reconciliation passed; 0 rejects |
| IRPD | 2,972 products; 349,196 invoice headers; 627,389 sales lines | One fictional Semarang store at deterministic coordinates; line unit preserved; `TotalPrice` is line sales amount; invoice amount is derived by summing line totals; timestamp conflicts use earliest line time; stock files excluded | Sample and full reconciliation passed; 0 rejected sales rows |
| Onyx | 120 stores; 220 products; 62,036 unique date/store/product facts | 103 duplicated source-grain rows rejected; source coordinates retained with perturbed/unverified provenance; a separate simulated POS order is built at 12:00 local time for each store-day with positive sales | Sample and full reconciliation passed |
| Pharma Sales Data | 16,848 daily date/ATC observations across 8 groups | The source has no documented quantity unit; ATC observations retain null UOM; deterministic ×10 scaling and even split create simulated POS only for reviewed candidate mappings; the simulated store is Neven Farma in Niš | Sample and full reconciliation passed |

### Pharma Sales candidate boundary

Ten candidate product-to-ATC assignments were retained for review. The generated product-level POS uses M01AE, N02BE, R03, and R06 candidates. M01AB, N02BA, N05B, and N05C remain observation-only because the available Long Châu evidence did not support a sufficiently suitable SKU. The specific candidates and ingredient evidence are in `04-pharma-sales/prepared/full/atc_candidate_mapping.csv`.

The assignments are `CANDIDATE`; no pharmacist review is claimed. Simulated rows do not assert that the source observed those products, units, prices, or transactions.

## Final Neon counts

All four sources have `verified-full.json` markers and passed source-to-Neon row-count reconciliation. The complete count report is `database/final-verification.json`.

| Table group | Final rows |
|---|---:|
| `catalog.product` | 5,670 |
| `catalog.product_category` | 320 |
| `catalog.product_category_assignment` | 9,263 |
| `org.store` | 2,816 |
| `pos.sales_observation` | 78,884 |
| `pos.sales_order` | 393,942 |
| `pos.sales_order_line` | 708,126 |
| All procurement/inventory/return/recall/quality/request tables | 0 |
| All base tables | 35 tables |

The zero-row count means these datasets were not used to invent operational records; the unrelated schema tables remain defined and available for future sources/modules.

## Reproduction and audit files

- `database/bootstrap.json`, `database/final-verification.json`, `database/report.json`
- Each source folder's `profile.json`, `manifest.sample.json`, `manifest.full.json`, load/verification markers, prepared CSV files, and `validation.json`
- `baseline/` contains the pre-v2 schema, README, EERD, Git status, and SHA-256 checksums
- `backup/neon-snapshot.json` records the Neon rollback point

The original dirty work-tree state was preserved. No tests were added; verification used prepared-data validation, sample/full ingestion, per-source reconciliation, and final database row counts.
