-- Lakeflow Declarative Pipeline (Gold MD-01 Sales & Demand + Weather Context)
-- Target schema: ${catalog}.gold_md01_sales

CREATE OR REFRESH MATERIALIZED VIEW mart_sales_daily (
  CONSTRAINT mart_daily_keys_not_null EXPECT (product_id IS NOT NULL AND demand_location_id IS NOT NULL AND local_date IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT mart_daily_qty_positive EXPECT (sold_qty > 0) ON VIOLATION FAIL UPDATE,
  CONSTRAINT mart_daily_has_provenance EXPECT (provenance_class IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT "Gold MD-01 daily POS sales mart at product x location x local_date x UOM x currency x provenance grain. Strictly built from fact_sales_line only."
AS
SELECT
  f.product_id,
  p.product_code,
  p.product_name,
  p.brand_name,
  p.manufacturer_id,
  p.manufacturer_name,
  f.demand_location_id,
  f.store_id,
  loc.store_code,
  loc.store_name,
  loc.country_code,
  loc.timezone_name,
  loc.latitude,
  loc.longitude,
  f.local_date,
  f.sales_uom_code,
  f.currency_code,
  f.provenance_class,
  f.source,
  COUNT(*) AS line_count,
  COUNT(DISTINCT f.sales_order_id) AS order_count,
  SUM(f.sold_qty) AS sold_qty,
  CASE
    WHEN COUNT(*) = COUNT(f.base_qty) THEN SUM(f.base_qty)
    ELSE NULL
  END AS base_qty,
  SUM(f.line_amount) AS line_amount,
  SUM(f.cost_amount) AS cost_amount,
  SUM(f.margin_amount) AS margin_amount,
  SUM(CASE WHEN f.is_promotional THEN f.sold_qty ELSE CAST(0 AS DECIMAL(18, 6)) END) AS promo_sold_qty,
  SUM(CASE WHEN f.is_promotional THEN 1 ELSE 0 END) AS promo_line_count,
  (SUM(CASE WHEN f.is_promotional THEN 1 ELSE 0 END) > 0) AS has_promotion
FROM ${catalog}.silver_sales.fact_sales_line f
LEFT JOIN ${catalog}.silver_core.dim_product p
  ON f.product_id = p.product_id
LEFT JOIN ${catalog}.silver_core.dim_location loc
  ON f.store_id = loc.location_id
GROUP BY
  f.product_id,
  p.product_code,
  p.product_name,
  p.brand_name,
  p.manufacturer_id,
  p.manufacturer_name,
  f.demand_location_id,
  f.store_id,
  loc.store_code,
  loc.store_name,
  loc.country_code,
  loc.timezone_name,
  loc.latitude,
  loc.longitude,
  f.local_date,
  f.sales_uom_code,
  f.currency_code,
  f.provenance_class,
  f.source;


CREATE OR REFRESH MATERIALIZED VIEW mart_sales_observation_period (
  CONSTRAINT obs_mart_period_valid EXPECT (period_start IS NOT NULL AND period_end IS NOT NULL AND period_start <= period_end) ON VIOLATION FAIL UPDATE
)
COMMENT "Separate Gold MD-01 period observation mart (WHO ATC & ONYX unverified series). Never unioned with mart_sales_daily."
AS
SELECT
  obs.store_id,
  loc.store_code,
  loc.store_name,
  loc.country_code,
  loc.timezone_name,
  obs.subject_kind,
  obs.product_id,
  p.product_code,
  p.product_name,
  obs.category_id,
  c.taxonomy_scheme,
  c.category_code,
  c.category_name,
  obs.period_start,
  obs.period_end,
  obs.period_days,
  obs.quantity_uom_code,
  obs.currency_code,
  obs.provenance_class,
  obs.source,
  COUNT(*) AS observation_count,
  SUM(obs.observed_qty) AS observed_qty,
  SUM(obs.revenue_amount) AS revenue_amount,
  SUM(obs.cost_amount) AS cost_amount,
  SUM(obs.margin_amount) AS margin_amount
FROM ${catalog}.silver_sales.fact_sales_observation obs
LEFT JOIN ${catalog}.silver_core.dim_location loc
  ON obs.store_id = loc.location_id
LEFT JOIN ${catalog}.silver_core.dim_product p
  ON obs.product_id = p.product_id
LEFT JOIN ${catalog}.silver_core.dim_product_category c
  ON obs.category_id = c.category_id
GROUP BY
  obs.store_id,
  loc.store_code,
  loc.store_name,
  loc.country_code,
  loc.timezone_name,
  obs.subject_kind,
  obs.product_id,
  p.product_code,
  p.product_name,
  obs.category_id,
  c.taxonomy_scheme,
  c.category_code,
  c.category_name,
  obs.period_start,
  obs.period_end,
  obs.period_days,
  obs.quantity_uom_code,
  obs.currency_code,
  obs.provenance_class,
  obs.source;


CREATE OR REFRESH MATERIALIZED VIEW kpi_sales_trend (
  CONSTRAINT kpi_period_start_not_null EXPECT (period_start IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT "Gold MD-01 weekly and monthly sales trend KPIs strictly partitioned by UOM, currency, and provenance."
AS
WITH base_periods AS (
  SELECT
    'WEEK' AS period_granularity,
    CAST(DATE_TRUNC('WEEK', local_date) AS DATE) AS period_start,
    product_id,
    product_code,
    product_name,
    store_id,
    store_code,
    country_code,
    sales_uom_code,
    currency_code,
    provenance_class,
    source,
    SUM(line_count) AS line_count,
    SUM(order_count) AS order_count,
    COUNT(DISTINCT local_date) AS active_selling_days,
    SUM(sold_qty) AS sold_qty,
    SUM(line_amount) AS line_amount,
    SUM(promo_sold_qty) AS promo_sold_qty
  FROM LIVE.mart_sales_daily
  GROUP BY
    CAST(DATE_TRUNC('WEEK', local_date) AS DATE),
    product_id,
    product_code,
    product_name,
    store_id,
    store_code,
    country_code,
    sales_uom_code,
    currency_code,
    provenance_class,
    source

  UNION ALL

  SELECT
    'MONTH' AS period_granularity,
    CAST(DATE_TRUNC('MONTH', local_date) AS DATE) AS period_start,
    product_id,
    product_code,
    product_name,
    store_id,
    store_code,
    country_code,
    sales_uom_code,
    currency_code,
    provenance_class,
    source,
    SUM(line_count) AS line_count,
    SUM(order_count) AS order_count,
    COUNT(DISTINCT local_date) AS active_selling_days,
    SUM(sold_qty) AS sold_qty,
    SUM(line_amount) AS line_amount,
    SUM(promo_sold_qty) AS promo_sold_qty
  FROM LIVE.mart_sales_daily
  GROUP BY
    CAST(DATE_TRUNC('MONTH', local_date) AS DATE),
    product_id,
    product_code,
    product_name,
    store_id,
    store_code,
    country_code,
    sales_uom_code,
    currency_code,
    provenance_class,
    source
),
with_lag AS (
  SELECT
    *,
    LAG(sold_qty) OVER (
      PARTITION BY
        period_granularity,
        store_id,
        product_id,
        sales_uom_code,
        currency_code,
        provenance_class,
        source
      ORDER BY period_start
    ) AS prev_period_sold_qty,
    LAG(line_amount) OVER (
      PARTITION BY
        period_granularity,
        store_id,
        product_id,
        sales_uom_code,
        currency_code,
        provenance_class,
        source
      ORDER BY period_start
    ) AS prev_period_line_amount
  FROM base_periods
)
SELECT
  *,
  CASE
    WHEN prev_period_sold_qty IS NOT NULL AND prev_period_sold_qty > 0
      THEN CAST((sold_qty - prev_period_sold_qty) / prev_period_sold_qty AS DECIMAL(18, 6))
    ELSE NULL
  END AS sold_qty_pct_change
FROM with_lag;


CREATE OR REFRESH MATERIALIZED VIEW mart_sales_weather_daily (
  CONSTRAINT weather_mart_keys_not_null EXPECT (product_id IS NOT NULL AND store_id IS NOT NULL AND local_date IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT "ML/EDA-ready Gold MD-01 store x product x day mart enriched 1:1 with deduplicated Silver daily weather metrics."
AS
WITH weather_dedup AS (
  SELECT
    CAST(store_id AS BIGINT) AS store_id,
    local_date,
    snapshot_id AS weather_snapshot_id,
    run_id AS weather_run_id,
    mode AS weather_mode,
    source_type AS weather_source_type,
    weather_asof_valid,
    grid_id AS weather_grid_id,
    is_grid_clustered,
    validation_status AS weather_validation_status,
    source AS weather_source,
    coordinate_verification_status,
    record_provenance AS weather_record_provenance,
    retrieved_at_utc AS weather_retrieved_at_utc,
    hourly_point_count,
    valid_temp_count,
    temp_mean,
    temp_min,
    temp_max,
    apparent_temp_mean,
    humidity_mean,
    precip_sum,
    wind_speed_max,
    wind_speed_mean,
    wind_gusts_max,
    cloud_cover_mean,
    pressure_msl_mean,
    uv_index_max,
    shortwave_radiation_sum,
    weather_code,
    sunrise_utc,
    sunset_utc,
    daylight_duration_s,
    wind_direction_10m_dominant,
    ROW_NUMBER() OVER (
      PARTITION BY CAST(store_id AS BIGINT), local_date
      ORDER BY
        CASE
          WHEN UPPER(source_type) LIKE 'HISTORICAL%' AND UPPER(source_type) NOT LIKE '%FORECAST%' THEN 3
          WHEN UPPER(source_type) LIKE 'HISTORICAL_FORECAST%' THEN 2
          ELSE 1
        END DESC,
        retrieved_at_utc DESC NULLS LAST,
        snapshot_id DESC
    ) AS _rn
  FROM ${catalog}.silver_weather.weather_daily_metrics
  WHERE store_id IS NOT NULL AND local_date IS NOT NULL
)
SELECT
  m.*,
  (w.weather_snapshot_id IS NOT NULL) AS has_weather_observation,
  w.weather_snapshot_id,
  w.weather_run_id,
  w.weather_mode,
  w.weather_source_type,
  w.weather_asof_valid,
  w.weather_grid_id,
  w.is_grid_clustered,
  w.weather_validation_status,
  w.weather_source,
  w.coordinate_verification_status,
  w.weather_record_provenance,
  w.weather_retrieved_at_utc,
  w.hourly_point_count,
  w.valid_temp_count,
  w.temp_mean,
  w.temp_min,
  w.temp_max,
  w.apparent_temp_mean,
  w.humidity_mean,
  w.precip_sum,
  w.wind_speed_max,
  w.wind_speed_mean,
  w.wind_gusts_max,
  w.cloud_cover_mean,
  w.pressure_msl_mean,
  w.uv_index_max,
  w.shortwave_radiation_sum,
  w.weather_code,
  w.sunrise_utc,
  w.sunset_utc,
  w.daylight_duration_s,
  w.wind_direction_10m_dominant
FROM LIVE.mart_sales_daily m
LEFT JOIN weather_dedup w
  ON w._rn = 1
  AND m.store_id = w.store_id
  AND m.local_date = w.local_date;
