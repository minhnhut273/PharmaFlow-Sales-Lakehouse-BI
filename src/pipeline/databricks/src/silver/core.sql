-- Lakeflow Declarative Pipeline (Silver Core Dimensions & Knowledge)
-- Target schema: ${catalog}.silver_core

CREATE OR REFRESH MATERIALIZED VIEW dim_manufacturer (
  CONSTRAINT manufacturer_id_not_null EXPECT (manufacturer_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT manufacturer_name_not_null EXPECT (manufacturer_name IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Cleaned pharmaceutical manufacturers with provenance metadata."
AS
SELECT
  CAST(manufacturer_id AS BIGINT) AS manufacturer_id,
  TRIM(manufacturer_code) AS manufacturer_code,
  TRIM(manufacturer_name) AS manufacturer_name,
  NULLIF(UPPER(TRIM(country_code)), '') AS country_code,
  source,
  CASE
    WHEN source IN ('IRPD_PUBLISHER_REPORTED_CATALOG', 'LONGCHAU_PUBLIC_PRODUCT_PAGE') THEN 'OBSERVED'
    WHEN source LIKE 'SIMULATED_%' THEN 'SYNTHETIC'
    ELSE 'UNVERIFIED'
  END AS provenance_class,
  created_at,
  updated_at,
  _ingest_run_id,
  _ingested_at_utc
FROM ${catalog}.bronze_pg.latest_catalog__manufacturer;


CREATE OR REFRESH MATERIALIZED VIEW dim_unit_of_measure (
  CONSTRAINT uom_code_not_null EXPECT (uom_code IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT "Unit of measure reference dimension preserving source-native UOM codes."
AS
SELECT
  TRIM(uom_code) AS uom_code,
  TRIM(uom_name) AS uom_name,
  TRIM(uom_kind) AS uom_kind,
  source,
  created_at,
  _ingest_run_id,
  _ingested_at_utc
FROM ${catalog}.bronze_pg.latest_catalog__unit_of_measure;


CREATE OR REFRESH MATERIALIZED VIEW dim_product_category (
  CONSTRAINT category_id_not_null EXPECT (category_id IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT "Multi-taxonomy product category hierarchy (Long Chau, WHO ATC, IRPD, ONYX)."
AS
SELECT
  CAST(category_id AS BIGINT) AS category_id,
  TRIM(taxonomy_scheme) AS taxonomy_scheme,
  TRIM(category_code) AS category_code,
  TRIM(category_name) AS category_name,
  CAST(parent_category_id AS BIGINT) AS parent_category_id,
  source_category_path,
  COALESCE(is_active, true) AS is_active,
  source,
  CASE
    WHEN source IN ('LONGCHAU_PUBLIC_TAXONOMY', 'WHO_ATC_CLASSIFICATION', 'IRPD_PUBLISHER_REPORTED_CLASSIFICATION') THEN 'OBSERVED'
    WHEN source LIKE 'SIMULATED_%' THEN 'SYNTHETIC'
    ELSE 'UNVERIFIED'
  END AS provenance_class,
  _ingest_run_id,
  _ingested_at_utc
FROM ${catalog}.bronze_pg.latest_catalog__product_category;


CREATE OR REFRESH MATERIALIZED VIEW bridge_product_category (
  CONSTRAINT bridge_keys_not_null EXPECT (product_id IS NOT NULL AND category_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Many-to-many product-to-category assignments preserving DIRECT vs CANDIDATE status."
AS
SELECT
  CAST(product_id AS BIGINT) AS product_id,
  CAST(category_id AS BIGINT) AS category_id,
  UPPER(TRIM(assignment_status)) AS assignment_status,
  TRIM(assignment_basis) AS assignment_basis,
  (UPPER(TRIM(assignment_status)) = 'DIRECT') AS is_direct_assignment,
  source,
  assigned_at,
  _ingest_run_id,
  _ingested_at_utc
FROM ${catalog}.bronze_pg.latest_catalog__product_category_assignment;


CREATE OR REFRESH MATERIALIZED VIEW dim_product (
  CONSTRAINT product_id_not_null EXPECT (product_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT product_name_not_null EXPECT (product_name IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Conformed pharmaceutical product dimension."
AS
SELECT
  CAST(p.product_id AS BIGINT) AS product_id,
  TRIM(p.product_code) AS product_code,
  TRIM(p.product_name) AS product_name,
  NULLIF(TRIM(p.brand_name), '') AS brand_name,
  CAST(p.manufacturer_id AS BIGINT) AS manufacturer_id,
  m.manufacturer_name,
  m.country_code AS manufacturer_country_code,
  NULLIF(TRIM(p.base_uom_code), '') AS base_uom_code,
  COALESCE(p.is_active, true) AS is_active,
  p.source,
  CASE
    WHEN p.source IN ('IRPD_PUBLISHER_REPORTED_CATALOG', 'LONGCHAU_PUBLIC_PRODUCT_PAGE') THEN 'OBSERVED'
    WHEN p.source LIKE 'SIMULATED_%' THEN 'SYNTHETIC'
    ELSE 'UNVERIFIED'
  END AS provenance_class,
  p.created_at,
  p.updated_at,
  p._ingest_run_id,
  p._ingested_at_utc
FROM ${catalog}.bronze_pg.latest_catalog__product p
LEFT JOIN LIVE.dim_manufacturer m
  ON CAST(p.manufacturer_id AS BIGINT) = m.manufacturer_id;


CREATE OR REFRESH MATERIALIZED VIEW dim_product_packaging (
  CONSTRAINT packaging_id_not_null EXPECT (product_packaging_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT packaging_product_not_null EXPECT (product_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Packaging conversion dimension; leaves quantity_in_base_uom NULL unless explicitly verified."
AS
SELECT
  CAST(product_packaging_id AS BIGINT) AS product_packaging_id,
  CAST(product_id AS BIGINT) AS product_id,
  TRIM(packaging_code) AS packaging_code,
  TRIM(display_name) AS display_name,
  NULLIF(TRIM(package_uom_code), '') AS package_uom_code,
  CAST(quantity_in_base_uom AS DECIMAL(18, 6)) AS quantity_in_base_uom,
  COALESCE(is_default_sales_unit, false) AS is_default_sales_unit,
  source,
  _ingest_run_id,
  _ingested_at_utc
FROM ${catalog}.bronze_pg.latest_catalog__product_packaging;


CREATE OR REFRESH MATERIALIZED VIEW xref_product_source (
  CONSTRAINT xref_pk_not_null EXPECT (product_source_reference_id IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT "Cross-reference mapping between external source product keys (SKU/URL/code) and canonical product_id."
AS
SELECT
  CAST(product_source_reference_id AS BIGINT) AS product_source_reference_id,
  CAST(product_id AS BIGINT) AS product_id,
  source,
  TRIM(external_product_key) AS external_product_key,
  UPPER(TRIM(match_status)) AS match_status,
  TRIM(match_basis) AS match_basis,
  observed_at,
  _ingest_run_id,
  _ingested_at_utc
FROM ${catalog}.bronze_pg.latest_catalog__product_source_reference;


CREATE OR REFRESH MATERIALIZED VIEW dim_product_knowledge (
  CONSTRAINT knowledge_key_not_null EXPECT (source IS NOT NULL AND source_product_key IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT knowledge_hash_present EXPECT (provenance_content_hash IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Deduplicated Long Chau observed product knowledge from MongoDB linked to canonical product_id."
AS
WITH ranked_snapshots AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY source, source_product_key
      ORDER BY provenance_captured_at_utc DESC NULLS LAST, provenance_content_hash DESC
    ) AS _rn
  FROM ${catalog}.bronze_mongo.latest_product_snapshots
),
dedup_xref AS (
  SELECT
    source,
    external_product_key,
    product_id,
    ROW_NUMBER() OVER (
      PARTITION BY source, external_product_key
      ORDER BY observed_at DESC NULLS LAST, product_source_reference_id ASC
    ) AS _rn
  FROM LIVE.xref_product_source
  WHERE product_id IS NOT NULL
)
SELECT
  COALESCE(x_sku.product_id, x_url.product_id) AS product_id,
  s.source,
  s.source_product_key,
  s.source_sku,
  s.schema_version,
  s.composition_basis_text,
  s.composition_details_markdown,
  s.composition_web_description_markdown,
  s.composition_items,
  s.composition_items_count,
  TRANSFORM(
    FILTER(s.composition_items, item -> COALESCE(item.source_is_primary, false)),
    item -> item.name
  ) AS primary_ingredient_names,
  s.storage_instructions_text,
  s.provenance_captured_at_utc,
  s.provenance_content_hash,
  s.provenance_evidence_status,
  s.provenance_raw_local_path,
  s.provenance_source_url,
  s.extraction_extracted_at_utc,
  s.extraction_status,
  s.extraction_version,
  s.source_run_id,
  s._ingest_run_id,
  s._ingested_at_utc
FROM ranked_snapshots s
LEFT JOIN dedup_xref x_sku
  ON x_sku._rn = 1
  AND x_sku.source = s.source
  AND x_sku.external_product_key = s.source_product_key
LEFT JOIN dedup_xref x_url
  ON x_url._rn = 1
  AND x_url.source = s.source
  AND s.provenance_source_url IS NOT NULL
  AND x_url.external_product_key = CONCAT('URL:', s.provenance_source_url)
WHERE s._rn = 1;


CREATE OR REFRESH MATERIALIZED VIEW dim_location (
  CONSTRAINT location_id_not_null EXPECT (location_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT valid_timezone EXPECT (timezone_name IS NOT NULL AND LENGTH(TRIM(timezone_name)) > 0) ON VIOLATION FAIL UPDATE
)
COMMENT "Conformed store/location dimension (store_id grain) enriched with linked warehouse node attributes."
AS
WITH dedup_wh AS (
  SELECT
    CAST(store_id AS BIGINT) AS store_id,
    CAST(warehouse_id AS BIGINT) AS warehouse_id,
    TRIM(warehouse_code) AS warehouse_code,
    TRIM(warehouse_name) AS warehouse_name,
    TRIM(warehouse_kind) AS warehouse_kind,
    COALESCE(is_active, true) AS warehouse_is_active,
    TRIM(data_origin) AS warehouse_data_origin,
    ROW_NUMBER() OVER (
      PARTITION BY store_id
      ORDER BY COALESCE(is_active, false) DESC, warehouse_id ASC
    ) AS _rn
  FROM ${catalog}.bronze_pg.latest_org__warehouse
  WHERE store_id IS NOT NULL
)
SELECT
  CAST(s.store_id AS BIGINT) AS location_id,
  CAST(s.store_id AS BIGINT) AS store_id,
  TRIM(s.store_code) AS store_code,
  TRIM(s.store_name) AS store_name,
  s.address,
  s.city_name,
  s.region_name,
  NULLIF(UPPER(TRIM(s.country_code)), '') AS country_code,
  CAST(s.latitude AS DOUBLE) AS latitude,
  CAST(s.longitude AS DOUBLE) AS longitude,
  TRIM(s.timezone_name) AS timezone_name,
  UPPER(TRIM(s.store_status)) AS store_status,
  s.source AS store_source,
  CASE
    WHEN s.source = 'LONGCHAU_PUBLIC_STORE_LOCATOR' THEN 'OBSERVED'
    WHEN s.source LIKE '%_UNVERIFIED%' THEN 'UNVERIFIED'
    WHEN s.source LIKE '%SIMULATED%' THEN 'SYNTHETIC'
    ELSE 'UNVERIFIED'
  END AS store_provenance_class,
  w.warehouse_id,
  w.warehouse_code,
  w.warehouse_name,
  w.warehouse_kind,
  w.warehouse_is_active,
  w.warehouse_data_origin,
  (w.warehouse_id IS NOT NULL) AS has_warehouse_node,
  s.created_at,
  s._ingest_run_id,
  s._ingested_at_utc
FROM ${catalog}.bronze_pg.latest_org__store s
LEFT JOIN dedup_wh w
  ON w._rn = 1
  AND CAST(s.store_id AS BIGINT) = w.store_id;
