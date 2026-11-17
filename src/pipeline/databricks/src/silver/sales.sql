-- Lakeflow Declarative Pipeline (Silver Sales Facts)
-- Target schema: ${catalog}.silver_sales

CREATE OR REFRESH MATERIALIZED VIEW fact_sales_line (
  CONSTRAINT pk_not_null EXPECT (sales_order_line_id IS NOT NULL AND sales_order_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT qty_positive EXPECT (sold_qty > 0) ON VIOLATION DROP ROW,
  CONSTRAINT valid_local_date EXPECT (local_date IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT has_provenance EXPECT (provenance_class IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT "Cleaned POS order-line facts preserving local store timezone, unit-of-measure, currency, and provenance. Never equated with latent demand."
AS
SELECT
  CAST(l.sales_order_line_id AS BIGINT) AS sales_order_line_id,
  CAST(l.sales_order_id AS BIGINT) AS sales_order_id,
  TRIM(o.order_number) AS order_number,
  CAST(l.line_number AS INT) AS line_number,
  CAST(o.demand_location_id AS BIGINT) AS demand_location_id,
  CAST(o.fulfillment_location_id AS BIGINT) AS fulfillment_location_id,
  loc.store_id,
  loc.store_code,
  loc.country_code,
  loc.timezone_name,
  CAST(l.product_id AS BIGINT) AS product_id,
  CAST(l.product_packaging_id AS BIGINT) AS product_packaging_id,
  o.ordered_at AS ordered_at_utc,
  DATE(from_utc_timestamp(o.ordered_at, loc.timezone_name)) AS local_date,
  CAST(l.sold_quantity AS DECIMAL(18, 6)) AS sold_qty,
  NULLIF(TRIM(l.sales_uom_code), '') AS sales_uom_code,
  pkg.quantity_in_base_uom,
  CASE
    WHEN pkg.quantity_in_base_uom IS NOT NULL
      THEN CAST(l.sold_quantity * pkg.quantity_in_base_uom AS DECIMAL(18, 6))
    ELSE NULL
  END AS base_qty,
  CAST(l.unit_price AS DECIMAL(18, 4)) AS unit_price,
  CAST(l.line_amount AS DECIMAL(18, 4)) AS line_amount,
  CAST(l.cost_amount AS DECIMAL(18, 4)) AS cost_amount,
  CAST(l.margin_amount AS DECIMAL(18, 4)) AS margin_amount,
  NULLIF(UPPER(TRIM(l.currency_code)), '') AS currency_code,
  COALESCE(l.is_promotional, false) AS is_promotional,
  UPPER(TRIM(o.order_status)) AS order_status,
  l.source,
  o.source AS order_source,
  CASE
    WHEN l.source = 'IRPD_PUBLISHER_REPORTED_POS' THEN 'OBSERVED'
    WHEN l.source LIKE 'SIMULATED_%' THEN 'SYNTHETIC'
    ELSE 'UNVERIFIED'
  END AS provenance_class,
  l._ingest_run_id,
  l._ingested_at_utc
FROM ${catalog}.bronze_pg.latest_pos__sales_order_line l
INNER JOIN ${catalog}.bronze_pg.latest_pos__sales_order o
  ON CAST(l.sales_order_id AS BIGINT) = CAST(o.sales_order_id AS BIGINT)
INNER JOIN ${catalog}.silver_core.dim_location loc
  ON CAST(o.demand_location_id AS BIGINT) = loc.location_id
LEFT JOIN ${catalog}.silver_core.dim_product_packaging pkg
  ON CAST(l.product_packaging_id AS BIGINT) = pkg.product_packaging_id
WHERE UPPER(TRIM(o.order_status)) <> 'CANCELLED';


CREATE OR REFRESH MATERIALIZED VIEW fact_sales_observation (
  CONSTRAINT obs_pk_not_null EXPECT (sales_observation_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT obs_qty_non_negative EXPECT (observed_qty >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT obs_period_valid EXPECT (period_start IS NOT NULL AND period_end IS NOT NULL AND period_start <= period_end) ON VIOLATION FAIL UPDATE
)
COMMENT "Separate aggregated sales observations (ATC daily / ONYX challenge daily). Never unioned with fact_sales_line."
AS
SELECT
  CAST(obs.sales_observation_id AS BIGINT) AS sales_observation_id,
  CAST(obs.store_id AS BIGINT) AS store_id,
  loc.store_code,
  loc.country_code,
  loc.timezone_name,
  UPPER(TRIM(obs.subject_kind)) AS subject_kind,
  CAST(obs.product_id AS BIGINT) AS product_id,
  CAST(obs.category_id AS BIGINT) AS category_id,
  obs.period_start,
  obs.period_end,
  DATEDIFF(obs.period_end, obs.period_start) + 1 AS period_days,
  CAST(obs.quantity AS DECIMAL(18, 6)) AS observed_qty,
  NULLIF(TRIM(obs.quantity_uom_code), '') AS quantity_uom_code,
  CAST(obs.revenue_amount AS DECIMAL(18, 4)) AS revenue_amount,
  CAST(obs.cost_amount AS DECIMAL(18, 4)) AS cost_amount,
  CAST(obs.margin_amount AS DECIMAL(18, 4)) AS margin_amount,
  NULLIF(UPPER(TRIM(obs.currency_code)), '') AS currency_code,
  obs.source,
  CASE
    WHEN obs.source = 'PHARMA_SALES_DAILY_ATC' THEN 'OBSERVED'
    WHEN obs.source LIKE '%_UNVERIFIED' THEN 'UNVERIFIED'
    WHEN obs.source LIKE 'SIMULATED_%' THEN 'SYNTHETIC'
    ELSE 'UNVERIFIED'
  END AS provenance_class,
  obs._ingest_run_id,
  obs._ingested_at_utc
FROM ${catalog}.bronze_pg.latest_pos__sales_observation obs
INNER JOIN ${catalog}.silver_core.dim_location loc
  ON CAST(obs.store_id AS BIGINT) = loc.location_id;
