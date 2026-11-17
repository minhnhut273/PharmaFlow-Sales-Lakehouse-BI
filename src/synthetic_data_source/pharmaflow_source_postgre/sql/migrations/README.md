# Bootstrap and migration policy

`schema_full.sql` is the canonical full bootstrap for a newly created, empty source database. The original bootstrap is kept at `runs/20261104-forecast-schema-v2/baseline/schema_full.pre-v2.sql` with a checksum in the run record.

The v2 database is created as `pharmaflow_source_postgre_v2`; the old `pharmaflow_source_postgre` database remains intact. Do not apply this bootstrap to the old database, and do not drop it as part of the source-loader workflow.

The v2 source contract changes are limited to catalog identity/classification/packaging, store geography/timezone, POS transaction provenance/economics, and a new aggregate `pos.sales_observation` fact. Existing procurement, inventory, request, return, quality, and recall definitions remain in the bootstrap.
