-- =============================================================================
-- PharmaFlow Silver Weather Pipeline (Lakeflow Declarative Pipelines SQL)
-- Reads verified Bronze snapshots, enforces SHA-256 & source_type DQ rules,
-- explodes P5 grid clusters (grid_id / member_store_ids) to 2,816 stores,
-- normalizes UTC timestamps & store-local dates, and flags day-16 tail nulls.
-- =============================================================================

CREATE OR REFRESH MATERIALIZED VIEW weather_snapshot (
  CONSTRAINT valid_sha256 EXPECT (sha2(raw_payload, 256) = raw_sha256) ON VIOLATION FAIL UPDATE,
  CONSTRAINT valid_source_type EXPECT (
    source_type IN ('FORECAST', 'HISTORICAL_FORECAST_STITCHED', 'HISTORICAL_ERA5_REANALYSIS')
  ) ON VIOLATION DROP ROW
)
COMMENT 'Validated Open-Meteo Bronze snapshots with verified SHA-256 and store/grid lineage.'
AS
SELECT
  snapshot_id,
  forecast_snapshot_id,
  run_id,
  task_id,
  attempt_id,
  mode,
  source_type,
  resolved_store_id AS store_id,
  grid_id,
  CASE WHEN grid_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_grid_clustered,
  country_code,
  timezone_requested,
  timezone_returned,
  utc_offset_seconds,
  elevation_m,
  requested_latitude,
  requested_longitude,
  returned_latitude,
  returned_longitude,
  CAST(window_start_date AS DATE) AS window_start_date,
  CAST(window_end_date AS DATE) AS window_end_date,
  endpoint_key,
  model,
  validation_status,
  source,
  coordinate_provenance,
  coordinate_verification_status,
  record_provenance,
  raw_sha256,
  raw_byte_length,
  scheduled_at_utc,
  planned_at_utc,
  retrieved_at_utc,
  persisted_at_utc,
  accepted_at_utc,
  ingested_at_utc,
  raw_payload
FROM ${catalog}.bronze_weather.raw_snapshots
LATERAL VIEW EXPLODE(
  COALESCE(
    IF(store_id IS NOT NULL, ARRAY(store_id), NULL),
    member_store_ids
  )
) exp AS resolved_store_id;


CREATE OR REFRESH MATERIALIZED VIEW weather_hourly (
  CONSTRAINT valid_store_id EXPECT (store_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_event_ts EXPECT (event_timestamp_utc IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_local_date EXPECT (local_date IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Store-level hourly weather observations & 16-day GFS forecasts (44 variables; 9 nullable for ERA5 < 2022-01-01).'
AS
WITH parsed AS (
  SELECT
    s.snapshot_id,
    s.forecast_snapshot_id,
    s.run_id,
    s.task_id,
    s.mode,
    s.source_type,
    s.store_id,
    s.grid_id,
    s.is_grid_clustered,
    s.country_code,
    s.timezone_requested,
    s.utc_offset_seconds,
    s.elevation_m,
    s.model,
    s.validation_status,
    s.source,
    s.coordinate_provenance,
    s.coordinate_verification_status,
    s.record_provenance,
    s.scheduled_at_utc,
    s.retrieved_at_utc,
    s.window_start_date,
    s.window_end_date,
    from_json(
      get_json_object(s.raw_payload, '$.hourly'),
      'STRUCT<
        time: ARRAY<BIGINT>,
        temperature_2m: ARRAY<DOUBLE>,
        relative_humidity_2m: ARRAY<DOUBLE>,
        dew_point_2m: ARRAY<DOUBLE>,
        apparent_temperature: ARRAY<DOUBLE>,
        wet_bulb_temperature_2m: ARRAY<DOUBLE>,
        vapour_pressure_deficit: ARRAY<DOUBLE>,
        precipitation_probability: ARRAY<DOUBLE>,
        precipitation: ARRAY<DOUBLE>,
        rain: ARRAY<DOUBLE>,
        showers: ARRAY<DOUBLE>,
        snowfall: ARRAY<DOUBLE>,
        snow_depth: ARRAY<DOUBLE>,
        weather_code: ARRAY<INT>,
        pressure_msl: ARRAY<DOUBLE>,
        surface_pressure: ARRAY<DOUBLE>,
        cloud_cover: ARRAY<DOUBLE>,
        cloud_cover_low: ARRAY<DOUBLE>,
        cloud_cover_mid: ARRAY<DOUBLE>,
        cloud_cover_high: ARRAY<DOUBLE>,
        visibility: ARRAY<DOUBLE>,
        wind_speed_10m: ARRAY<DOUBLE>,
        wind_speed_80m: ARRAY<DOUBLE>,
        wind_speed_120m: ARRAY<DOUBLE>,
        wind_direction_10m: ARRAY<DOUBLE>,
        wind_direction_80m: ARRAY<DOUBLE>,
        wind_direction_120m: ARRAY<DOUBLE>,
        wind_gusts_10m: ARRAY<DOUBLE>,
        uv_index: ARRAY<DOUBLE>,
        uv_index_clear_sky: ARRAY<DOUBLE>,
        is_day: ARRAY<INT>,
        sunshine_duration: ARRAY<DOUBLE>,
        shortwave_radiation: ARRAY<DOUBLE>,
        direct_radiation: ARRAY<DOUBLE>,
        diffuse_radiation: ARRAY<DOUBLE>,
        direct_normal_irradiance: ARRAY<DOUBLE>,
        terrestrial_radiation: ARRAY<DOUBLE>,
        evapotranspiration: ARRAY<DOUBLE>,
        et0_fao_evapotranspiration: ARRAY<DOUBLE>,
        cape: ARRAY<DOUBLE>,
        lifted_index: ARRAY<DOUBLE>,
        convective_inhibition: ARRAY<DOUBLE>,
        freezing_level_height: ARRAY<DOUBLE>,
        boundary_layer_height: ARRAY<DOUBLE>,
        total_column_integrated_water_vapour: ARRAY<DOUBLE>
      >'
    ) AS h
  FROM LIVE.weather_snapshot s
)
SELECT
  p.snapshot_id,
  p.forecast_snapshot_id,
  p.run_id,
  p.task_id,
  p.mode,
  p.source_type,
  p.store_id,
  p.grid_id,
  p.is_grid_clustered,
  p.country_code,
  p.timezone_requested,
  p.utc_offset_seconds,
  p.elevation_m,
  p.model,
  p.validation_status,
  p.source,
  p.coordinate_provenance,
  p.coordinate_verification_status,
  p.record_provenance,
  p.scheduled_at_utc,
  p.retrieved_at_utc,
  timestamp_seconds(epoch_sec) AS event_timestamp_utc,
  CAST(from_utc_timestamp(timestamp_seconds(epoch_sec), p.timezone_requested) AS DATE) AS local_date,
  HOUR(from_utc_timestamp(timestamp_seconds(epoch_sec), p.timezone_requested)) AS local_hour,
  CAST(
    CAST(from_utc_timestamp(timestamp_seconds(epoch_sec), p.timezone_requested) AS DATE) = p.window_end_date
    AND p.h.temperature_2m[idx] IS NULL
    AND p.h.precipitation[idx] IS NULL
    AND p.h.weather_code[idx] IS NULL
    AS BOOLEAN
  ) AS is_tail_partial,
  p.h.temperature_2m[idx] AS temperature_2m,
  p.h.relative_humidity_2m[idx] AS relative_humidity_2m,
  p.h.dew_point_2m[idx] AS dew_point_2m,
  p.h.apparent_temperature[idx] AS apparent_temperature,
  p.h.wet_bulb_temperature_2m[idx] AS wet_bulb_temperature_2m,
  p.h.vapour_pressure_deficit[idx] AS vapour_pressure_deficit,
  p.h.precipitation_probability[idx] AS precipitation_probability,
  p.h.precipitation[idx] AS precipitation,
  p.h.rain[idx] AS rain,
  p.h.showers[idx] AS showers,
  p.h.snowfall[idx] AS snowfall,
  p.h.snow_depth[idx] AS snow_depth,
  p.h.weather_code[idx] AS weather_code,
  p.h.pressure_msl[idx] AS pressure_msl,
  p.h.surface_pressure[idx] AS surface_pressure,
  p.h.cloud_cover[idx] AS cloud_cover,
  p.h.cloud_cover_low[idx] AS cloud_cover_low,
  p.h.cloud_cover_mid[idx] AS cloud_cover_mid,
  p.h.cloud_cover_high[idx] AS cloud_cover_high,
  p.h.visibility[idx] AS visibility,
  p.h.wind_speed_10m[idx] AS wind_speed_10m,
  p.h.wind_speed_80m[idx] AS wind_speed_80m,
  p.h.wind_speed_120m[idx] AS wind_speed_120m,
  p.h.wind_direction_10m[idx] AS wind_direction_10m,
  p.h.wind_direction_80m[idx] AS wind_direction_80m,
  p.h.wind_direction_120m[idx] AS wind_direction_120m,
  p.h.wind_gusts_10m[idx] AS wind_gusts_10m,
  p.h.uv_index[idx] AS uv_index,
  p.h.uv_index_clear_sky[idx] AS uv_index_clear_sky,
  p.h.is_day[idx] AS is_day,
  p.h.sunshine_duration[idx] AS sunshine_duration,
  p.h.shortwave_radiation[idx] AS shortwave_radiation,
  p.h.direct_radiation[idx] AS direct_radiation,
  p.h.diffuse_radiation[idx] AS diffuse_radiation,
  p.h.direct_normal_irradiance[idx] AS direct_normal_irradiance,
  p.h.terrestrial_radiation[idx] AS terrestrial_radiation,
  p.h.evapotranspiration[idx] AS evapotranspiration,
  p.h.et0_fao_evapotranspiration[idx] AS et0_fao_evapotranspiration,
  p.h.cape[idx] AS cape,
  p.h.lifted_index[idx] AS lifted_index,
  p.h.convective_inhibition[idx] AS convective_inhibition,
  p.h.freezing_level_height[idx] AS freezing_level_height,
  p.h.boundary_layer_height[idx] AS boundary_layer_height,
  p.h.total_column_integrated_water_vapour[idx] AS total_column_integrated_water_vapour
FROM parsed p
LATERAL VIEW POSEXPLODE(p.h.time) t AS idx, epoch_sec;


CREATE OR REFRESH MATERIALIZED VIEW weather_daily (
  CONSTRAINT valid_store_id EXPECT (store_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_local_date EXPECT (local_date IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Store-level daily weather metrics exploded from Bronze snapshots with store-local calendar date.'
AS
WITH parsed AS (
  SELECT
    s.snapshot_id,
    s.forecast_snapshot_id,
    s.run_id,
    s.task_id,
    s.mode,
    s.source_type,
    s.store_id,
    s.grid_id,
    s.is_grid_clustered,
    s.country_code,
    s.timezone_requested,
    s.model,
    s.validation_status,
    s.source,
    s.coordinate_provenance,
    s.coordinate_verification_status,
    s.record_provenance,
    s.scheduled_at_utc,
    s.retrieved_at_utc,
    from_json(
      get_json_object(s.raw_payload, '$.daily'),
      'STRUCT<
        time: ARRAY<BIGINT>,
        weather_code: ARRAY<INT>,
        sunrise: ARRAY<BIGINT>,
        sunset: ARRAY<BIGINT>,
        daylight_duration: ARRAY<DOUBLE>,
        wind_direction_10m_dominant: ARRAY<DOUBLE>
      >'
    ) AS d
  FROM LIVE.weather_snapshot s
)
SELECT
  p.snapshot_id,
  p.forecast_snapshot_id,
  p.run_id,
  p.task_id,
  p.mode,
  p.source_type,
  p.store_id,
  p.grid_id,
  p.is_grid_clustered,
  p.country_code,
  p.timezone_requested,
  p.model,
  p.validation_status,
  p.source,
  p.coordinate_provenance,
  p.coordinate_verification_status,
  p.record_provenance,
  p.scheduled_at_utc,
  p.retrieved_at_utc,
  CAST(from_utc_timestamp(timestamp_seconds(epoch_sec), p.timezone_requested) AS DATE) AS local_date,
  p.d.weather_code[idx] AS weather_code,
  timestamp_seconds(p.d.sunrise[idx]) AS sunrise_utc,
  timestamp_seconds(p.d.sunset[idx]) AS sunset_utc,
  p.d.daylight_duration[idx] AS daylight_duration_s,
  p.d.wind_direction_10m_dominant[idx] AS wind_direction_10m_dominant
FROM parsed p
LATERAL VIEW POSEXPLODE(p.d.time) t AS idx, epoch_sec;


CREATE OR REFRESH MATERIALIZED VIEW store_grid_mapping
COMMENT 'Run-level store-to-grid provenance mapping mirrored from P5 full_network store_grid_mapping.json.'
AS
SELECT
  run_id,
  store_id,
  cohort_id,
  point_id,
  grid_id,
  clustered,
  store_code,
  country_code,
  timezone_name,
  store_latitude,
  store_longitude,
  point_latitude,
  point_longitude,
  source,
  coordinate_provenance,
  coordinate_verification_status,
  created_at_utc,
  ingested_at_utc
FROM ${catalog}.bronze_weather.store_grid_mapping;


CREATE OR REFRESH MATERIALIZED VIEW weather_daily_metrics (
  CONSTRAINT valid_store_id EXPECT (store_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_local_date EXPECT (local_date IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT positive_hours EXPECT (hourly_point_count > 0) ON VIOLATION DROP ROW
)
COMMENT 'Daily aggregated weather metrics from hourly series (excluding day-16 partial nulls), enriched with provider daily fields and weather_asof_valid flag.'
AS
WITH hourly_agg AS (
  SELECT
    snapshot_id,
    forecast_snapshot_id,
    run_id,
    task_id,
    mode,
    source_type,
    (source_type = 'FORECAST') AS weather_asof_valid,
    store_id,
    grid_id,
    is_grid_clustered,
    country_code,
    timezone_requested,
    model,
    validation_status,
    source,
    coordinate_provenance,
    coordinate_verification_status,
    record_provenance,
    scheduled_at_utc,
    retrieved_at_utc,
    local_date,
    COUNT(*) AS hourly_point_count,
    COUNT(temperature_2m) AS valid_temp_count,
    AVG(temperature_2m) AS temp_mean,
    MIN(temperature_2m) AS temp_min,
    MAX(temperature_2m) AS temp_max,
    AVG(apparent_temperature) AS apparent_temp_mean,
    AVG(relative_humidity_2m) AS humidity_mean,
    CASE WHEN COUNT(precipitation) > 0 THEN SUM(precipitation) ELSE NULL END AS precip_sum,
    MAX(wind_speed_10m) AS wind_speed_max,
    AVG(wind_speed_10m) AS wind_speed_mean,
    MAX(wind_gusts_10m) AS wind_gusts_max,
    AVG(cloud_cover) AS cloud_cover_mean,
    AVG(pressure_msl) AS pressure_msl_mean,
    MAX(uv_index) AS uv_index_max,
    CASE WHEN COUNT(shortwave_radiation) > 0 THEN SUM(shortwave_radiation) ELSE NULL END AS shortwave_radiation_sum
  FROM LIVE.weather_hourly
  WHERE NOT is_tail_partial
  GROUP BY
    snapshot_id,
    forecast_snapshot_id,
    run_id,
    task_id,
    mode,
    source_type,
    store_id,
    grid_id,
    is_grid_clustered,
    country_code,
    timezone_requested,
    model,
    validation_status,
    source,
    coordinate_provenance,
    coordinate_verification_status,
    record_provenance,
    scheduled_at_utc,
    retrieved_at_utc,
    local_date
)
SELECT
  h.snapshot_id,
  h.forecast_snapshot_id,
  h.run_id,
  h.task_id,
  h.mode,
  h.source_type,
  h.weather_asof_valid,
  h.store_id,
  h.grid_id,
  h.is_grid_clustered,
  h.country_code,
  h.timezone_requested,
  h.model,
  h.validation_status,
  h.source,
  h.coordinate_provenance,
  h.coordinate_verification_status,
  h.record_provenance,
  h.scheduled_at_utc,
  h.retrieved_at_utc,
  h.local_date,
  h.hourly_point_count,
  h.valid_temp_count,
  h.temp_mean,
  h.temp_min,
  h.temp_max,
  h.apparent_temp_mean,
  h.humidity_mean,
  h.precip_sum,
  h.wind_speed_max,
  h.wind_speed_mean,
  h.wind_gusts_max,
  h.cloud_cover_mean,
  h.pressure_msl_mean,
  h.uv_index_max,
  h.shortwave_radiation_sum,
  d.weather_code,
  d.sunrise_utc,
  d.sunset_utc,
  d.daylight_duration_s,
  d.wind_direction_10m_dominant
FROM hourly_agg h
LEFT JOIN LIVE.weather_daily d
  ON h.snapshot_id = d.snapshot_id
  AND h.store_id = d.store_id
  AND h.local_date = d.local_date;
