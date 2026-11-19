"""Parameterized PostgreSQL pushdown query builders for PharmaFlow BI Streamlit."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Sequence

from config import DEFAULT_TRACK, TRACK_META

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEFAULT_SCHEMA = "quick_gold_md01"


def validate_schema(name: str) -> str:
    """Reject unsafe SQL schema identifiers."""
    cleaned = (name or "").strip()
    if not _IDENT_RE.match(cleaned):
        raise ValueError(f"Unsafe SQL schema identifier: {name!r}")
    return cleaned


@dataclass(frozen=True)
class FilterState:
    """Shared cross-page filter state synchronized via st.session_state."""

    dataset_track: str | None = DEFAULT_TRACK
    countries: tuple[str, ...] = field(default_factory=tuple)
    stores: tuple[str, ...] = field(default_factory=tuple)
    clean_uoms: tuple[str, ...] = field(default_factory=tuple)
    date_start: date | None = None
    date_end: date | None = None
    temp_bands: tuple[str, ...] = field(default_factory=tuple)
    rain_regimes: tuple[str, ...] = field(default_factory=tuple)
    humidity_bands: tuple[str, ...] = field(default_factory=tuple)
    heatmap_temp_band: str | None = None
    heatmap_rain_regime: str | None = None


def build_where_clause(
    filters: FilterState,
    *,
    override_track: str | None = None,
    ignore_track: bool = False,
    ignore_weather_cell: bool = False,
    alias: str = "",
    extra_conditions: Sequence[str] = (),
) -> tuple[str, tuple[Any, ...]]:
    """Build parameterized SQL WHERE clause against bi_sales_weather_enriched."""
    prefix = f"{alias}." if alias else ""
    clauses: list[str] = []
    params: list[Any] = []

    effective_track = None if ignore_track else (override_track if override_track is not None else filters.dataset_track)
    if effective_track:
        clauses.append(f"{prefix}dataset_track = %s")
        params.append(effective_track)

    if filters.countries and override_track is None:
        clauses.append(f"{prefix}country_code = ANY(%s)")
        params.append(list(filters.countries))

    if filters.stores and override_track is None:
        clauses.append(f"{prefix}store_name = ANY(%s)")
        params.append(list(filters.stores))

    if filters.clean_uoms and override_track is None:
        clauses.append(f"{prefix}clean_uom = ANY(%s)")
        params.append(list(filters.clean_uoms))

    if filters.date_start is not None:
        clauses.append(f"{prefix}local_date >= %s")
        params.append(filters.date_start)

    if filters.date_end is not None:
        clauses.append(f"{prefix}local_date <= %s")
        params.append(filters.date_end)

    if filters.temp_bands:
        clauses.append(f"{prefix}temp_band = ANY(%s)")
        params.append(list(filters.temp_bands))

    if filters.rain_regimes:
        clauses.append(f"{prefix}rain_regime = ANY(%s)")
        params.append(list(filters.rain_regimes))

    if filters.humidity_bands:
        clauses.append(f"{prefix}humidity_band = ANY(%s)")
        params.append(list(filters.humidity_bands))

    if not ignore_weather_cell:
        if filters.heatmap_temp_band:
            clauses.append(f"{prefix}temp_band = %s")
            params.append(filters.heatmap_temp_band)
        if filters.heatmap_rain_regime:
            clauses.append(f"{prefix}rain_regime = %s")
            params.append(filters.heatmap_rain_regime)

    for cond in extra_conditions:
        if cond and cond.strip():
            clauses.append(cond.strip())

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, tuple(params)


# ---------------------------------------------------------------------------
# Filter metadata & release state
# ---------------------------------------------------------------------------

def sql_release_state(schema: str) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    sql = f"""
    SELECT product_domain, release_id, status, sync_mode, synced_at_utc, table_counts_json
    FROM "{s}"."sync_release_state"
    LIMIT 1
    """.strip()
    return sql, ()


def sql_filter_options(schema: str, dataset_track: str | None) -> tuple[str, tuple[Any, ...]]:
    """Return distinct option lists scoped by selected track cleanly without scanning full rows client-side."""
    s = validate_schema(schema)
    where = "WHERE dataset_track = %s" if dataset_track else ""
    params: tuple[Any, ...] = (dataset_track,) if dataset_track else ()
    sql = f"""
    SELECT
      MIN(local_date) AS min_date,
      MAX(local_date) AS max_date,
      ARRAY_REMOVE(ARRAY_AGG(DISTINCT country_code ORDER BY country_code), NULL) AS countries,
      ARRAY_REMOVE(ARRAY_AGG(DISTINCT clean_uom ORDER BY clean_uom), NULL) AS uoms,
      ARRAY_REMOVE(ARRAY_AGG(DISTINCT store_name ORDER BY store_name), NULL) AS stores
    FROM "{s}"."bi_sales_weather_enriched"
    {where}
    """.strip()
    return sql, params


def sql_available_tracks(schema: str) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    sql = f"""
    SELECT dataset_track, MIN(currency_code) AS currency_code, MIN(provenance_class) AS provenance_class, COUNT(*) AS row_count
    FROM "{s}"."bi_sales_weather_enriched"
    GROUP BY dataset_track
    ORDER BY COUNT(*) DESC
    """.strip()
    return sql, ()


# ---------------------------------------------------------------------------
# Page 1: Executive Overview (Tổng Quan)
# ---------------------------------------------------------------------------

def sql_exec_kpis(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    SELECT
      COALESCE(SUM(line_amount), 0)::double precision AS total_revenue,
      COALESCE(SUM(sold_qty), 0)::double precision AS total_sold_qty,
      COALESCE(SUM(order_count), 0)::bigint AS total_orders,
      SUM(margin_amount)::double precision AS total_margin,
      AVG(margin_pct)::double precision AS avg_margin_pct,
      (SUM(margin_amount) / NULLIF(SUM(line_amount), 0))::double precision AS weighted_margin_pct,
      AVG(avg_unit_price)::double precision AS avg_unit_price,
      MIN(currency_code) AS currency_code,
      MIN(provenance_class) AS provenance_class,
      COUNT(margin_amount) AS margin_rows,
      COUNT(*) AS row_count
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    """.strip()
    return sql, params


def sql_monthly_trend_kpi(
    schema: str,
    filters: FilterState,
    *,
    scope_to_track: bool = False,
) -> tuple[str, tuple[Any, ...]]:
    """Use kpi_sales_trend strictly at MONTH granularity with AVG(sold_qty_pct_change)."""
    s = validate_schema(schema)
    clauses = ["period_granularity = 'MONTH'"]
    params: list[Any] = []

    if scope_to_track and filters.dataset_track:
        meta = TRACK_META.get(filters.dataset_track)
        if meta:
            clauses.append("source = %s")
            params.append(meta.source_name)
    if filters.countries:
        clauses.append("country_code = ANY(%s)")
        params.append(list(filters.countries))
    if filters.date_start is not None:
        clauses.append("period_start >= DATE_TRUNC('month', %s::date)::date")
        params.append(filters.date_start)
    if filters.date_end is not None:
        clauses.append("period_start <= DATE_TRUNC('month', %s::date)::date")
        params.append(filters.date_end)

    where_sql = "WHERE " + " AND ".join(clauses)
    sql = f"""
    SELECT
      period_start,
      SUM(sold_qty)::double precision AS sold_qty,
      AVG(sold_qty_pct_change)::double precision AS avg_pct_change,
      SUM(order_count)::bigint AS order_count
    FROM "{s}"."kpi_sales_trend"
    {where_sql}
    GROUP BY period_start
    ORDER BY period_start
    """.strip()
    return sql, tuple(params)


def sql_sales_by_country(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    SELECT
      country_code,
      SUM(sold_qty)::double precision AS sold_qty,
      COALESCE(SUM(line_amount), 0)::double precision AS line_amount,
      SUM(order_count)::bigint AS order_count
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY country_code
    ORDER BY SUM(sold_qty) DESC
    """.strip()
    return sql, params


def sql_top_brands(schema: str, filters: FilterState, *, limit: int = 15) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, extra_conditions=("brand_name IS NOT NULL",))
    sql = f"""
    SELECT
      brand_name,
      SUM(sold_qty)::double precision AS sold_qty,
      COALESCE(SUM(line_amount), 0)::double precision AS line_amount,
      SUM(margin_amount)::double precision AS margin_amount
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY brand_name
    ORDER BY SUM(sold_qty) DESC
    LIMIT %s
    """.strip()
    return sql, (*params, int(limit))


def sql_track_currency_summary(
    schema: str,
    filters: FilterState,
    *,
    show_all_tracks: bool = False,
) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, ignore_track=show_all_tracks)
    sql = f"""
    SELECT
      dataset_track,
      COALESCE(currency_code, 'N/A') AS currency_code,
      provenance_class,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(order_count)::bigint AS order_count,
      SUM(line_amount)::double precision AS line_amount,
      SUM(margin_amount)::double precision AS margin_amount
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY dataset_track, COALESCE(currency_code, 'N/A'), provenance_class
    ORDER BY SUM(sold_qty) DESC
    """.strip()
    return sql, params


# ---------------------------------------------------------------------------
# Page 2: Weather & Location (Thời Tiết & Địa Điểm)
# ---------------------------------------------------------------------------

def sql_weather_kpis(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    SELECT
      COUNT(DISTINCT store_id)::bigint AS active_stores,
      (SUM(sold_qty) / NULLIF(COUNT(DISTINCT store_id), 0))::double precision AS avg_qty_per_store,
      AVG(temp_mean)::double precision AS avg_temp_mean,
      AVG(precip_sum)::double precision AS avg_precip_sum,
      SUM(sold_qty)::double precision AS total_sold_qty,
      SUM(order_count)::bigint AS total_orders
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    """.strip()
    return sql, params


def sql_temp_rain_heatmap(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    """Aggregate by temp_band x rain_regime (ignoring heatmap click filter itself so grid stays intact)."""
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, ignore_weather_cell=True)
    sql = f"""
    SELECT
      temp_band,
      rain_regime,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(order_count)::bigint AS order_count,
      COUNT(DISTINCT local_date)::bigint AS days_count
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY temp_band, rain_regime
    """.strip()
    return sql, params


def sql_humidity_weekend(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    SELECT
      humidity_band,
      is_weekend,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(order_count)::bigint AS order_count
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY humidity_band, is_weekend
    ORDER BY humidity_band, is_weekend
    """.strip()
    return sql, params


def sql_daily_temp_scatter(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    """Daily average temp_mean vs daily SUM(sold_qty) colored by rain_regime."""
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, extra_conditions=("temp_mean IS NOT NULL",))
    sql = f"""
    SELECT
      local_date,
      rain_regime,
      AVG(temp_mean)::double precision AS temp_mean,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(order_count)::bigint AS order_count
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY local_date, rain_regime
    ORDER BY local_date
    """.strip()
    return sql, params


def sql_monthly_track_trend(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    SELECT
      year_month,
      dataset_track,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(order_count)::bigint AS order_count
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY year_month, dataset_track
    ORDER BY year_month
    """.strip()
    return sql, params


def sql_daily_weather_table(
    schema: str,
    filters: FilterState,
    *,
    by_store_uom: bool = False,
    limit: int = 500,
) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    if by_store_uom:
        sql = f"""
        SELECT
          local_date,
          store_name,
          temp_band,
          rain_regime,
          humidity_band,
          is_weekend,
          clean_uom,
          SUM(sold_qty)::double precision AS sold_qty,
          SUM(order_count)::bigint AS order_count,
          AVG(temp_mean)::double precision AS temp_mean,
          AVG(precip_sum)::double precision AS precip_sum,
          AVG(humidity_mean)::double precision AS humidity_mean,
          SUM(line_amount)::double precision AS line_amount
        FROM "{s}"."bi_sales_weather_enriched"
        {where_sql}
        GROUP BY local_date, store_name, temp_band, rain_regime, humidity_band, is_weekend, clean_uom
        ORDER BY local_date DESC, SUM(sold_qty) DESC
        LIMIT %s
        """.strip()
    else:
        sql = f"""
        SELECT
          local_date,
          SUM(sold_qty)::double precision AS sold_qty,
          SUM(order_count)::bigint AS order_count,
          AVG(temp_mean)::double precision AS temp_mean,
          AVG(precip_sum)::double precision AS precip_sum,
          AVG(humidity_mean)::double precision AS humidity_mean,
          SUM(line_amount)::double precision AS line_amount
        FROM "{s}"."bi_sales_weather_enriched"
        {where_sql}
        GROUP BY local_date
        ORDER BY local_date DESC
        LIMIT %s
        """.strip()
    return sql, (*params, int(limit))


def sql_top_products_by_rain(schema: str, filters: FilterState, *, limit: int = 15) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, extra_conditions=("product_name IS NOT NULL",))
    sql = f"""
    WITH top_products AS (
      SELECT product_name, SUM(sold_qty)::double precision AS total_qty
      FROM "{s}"."bi_sales_weather_enriched"
      {where_sql}
      GROUP BY product_name
      ORDER BY SUM(sold_qty) DESC
      LIMIT %s
    )
    SELECT
      m.product_name,
      m.rain_regime,
      SUM(m.sold_qty)::double precision AS sold_qty,
      tp.total_qty
    FROM "{s}"."bi_sales_weather_enriched" m
    INNER JOIN top_products tp ON m.product_name = tp.product_name
    {build_where_clause(filters, alias='m', extra_conditions=('m.product_name IS NOT NULL',))[0]}
    GROUP BY m.product_name, m.rain_regime, tp.total_qty
    ORDER BY tp.total_qty DESC, m.rain_regime
    """.strip()
    return sql, (*params, int(limit), *params)


def sql_weekday_by_rain(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    SELECT
      day_of_week_num,
      day_of_week,
      rain_regime,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(order_count)::bigint AS order_count
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY day_of_week_num, day_of_week, rain_regime
    ORDER BY day_of_week_num, rain_regime
    """.strip()
    return sql, params


# ---------------------------------------------------------------------------
# Page 3: Stores & Margin (Cửa Hàng & Lợi Nhuận)
# ---------------------------------------------------------------------------

def sql_eu_country_summary(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, override_track="ONYX_EU_SYNTHETIC")
    sql = f"""
    SELECT
      country_code,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      SUM(margin_amount)::double precision AS margin_amount,
      COUNT(DISTINCT store_id)::bigint AS store_count,
      AVG(latitude)::double precision AS lat,
      AVG(longitude)::double precision AS lon
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY country_code
    ORDER BY SUM(sold_qty) DESC
    """.strip()
    return sql, params


def sql_eu_country_month_heatmap(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, override_track="ONYX_EU_SYNTHETIC")
    sql = f"""
    SELECT
      month_num,
      country_code,
      SUM(sold_qty)::double precision AS sold_qty
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY month_num, country_code
    ORDER BY month_num, country_code
    """.strip()
    return sql, params


def sql_top_stores(schema: str, filters: FilterState, *, limit: int = 20) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    SELECT
      store_name,
      country_code,
      dataset_track,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      SUM(order_count)::bigint AS order_count
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY store_name, country_code, dataset_track
    ORDER BY SUM(sold_qty) DESC
    LIMIT %s
    """.strip()
    return sql, (*params, int(limit))


def sql_eu_promo_gauge(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, override_track="ONYX_EU_SYNTHETIC")
    sql = f"""
    SELECT
      (AVG(promo_share_pct) * 100.0)::double precision AS avg_promo_pct,
      (SUM(promo_sold_qty) / NULLIF(SUM(sold_qty), 0) * 100.0)::double precision AS weighted_promo_pct
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    """.strip()
    return sql, params


def sql_eu_brand_margin_and_profit(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(
        filters,
        override_track="ONYX_EU_SYNTHETIC",
        extra_conditions=("brand_name IS NOT NULL",),
    )
    sql = f"""
    SELECT
      brand_name,
      SUM(line_amount)::double precision AS line_amount,
      SUM(margin_amount)::double precision AS margin_amount,
      (AVG(margin_pct) * 100.0)::double precision AS avg_margin_pct,
      SUM(sold_qty)::double precision AS sold_qty
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY brand_name
    ORDER BY SUM(margin_amount) DESC
    """.strip()
    return sql, params


def sql_store_performance_table(
    schema: str,
    filters: FilterState,
    *,
    search_text: str = "",
) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    extra: list[str] = []
    extra_params: list[Any] = []
    cleaned_search = (search_text or "").strip()
    if cleaned_search:
        extra.append("(store_code ILIKE %s OR store_name ILIKE %s OR country_code ILIKE %s)")
        like = f"%{cleaned_search}%"
        extra_params.extend([like, like, like])
    where_sql, params = build_where_clause(filters, extra_conditions=extra)
    sql = f"""
    SELECT
      store_code,
      store_name,
      country_code,
      source,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(order_count)::bigint AS order_count,
      SUM(line_amount)::double precision AS line_amount,
      SUM(margin_amount)::double precision AS margin_amount,
      (AVG(margin_pct) * 100.0)::double precision AS avg_margin_pct
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY store_code, store_name, country_code, source
    ORDER BY SUM(sold_qty) DESC
    """.strip()
    return sql, (*params, *extra_params)


def sql_eu_store_matrix(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, override_track="ONYX_EU_SYNTHETIC")
    sql = f"""
    SELECT
      store_code,
      store_name,
      country_code,
      SUM(line_amount)::double precision AS line_amount,
      (AVG(margin_pct) * 100.0)::double precision AS avg_margin_pct,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(order_count)::bigint AS order_count
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY store_code, store_name, country_code
    ORDER BY SUM(line_amount) DESC
    """.strip()
    return sql, params


# ---------------------------------------------------------------------------
# Page 4: Products & ATC (Sản Phẩm & ATC)
# ---------------------------------------------------------------------------

def sql_product_detail_table(
    schema: str,
    filters: FilterState,
    *,
    search_text: str = "",
    limit: int = 500,
) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    extra: list[str] = ["product_name IS NOT NULL"]
    extra_params: list[Any] = []
    cleaned_search = (search_text or "").strip()
    if cleaned_search:
        extra.append("(product_name ILIKE %s OR brand_name ILIKE %s OR clean_uom ILIKE %s)")
        like = f"%{cleaned_search}%"
        extra_params.extend([like, like, like])
    where_sql, params = build_where_clause(filters, extra_conditions=extra)
    sql = f"""
    SELECT
      product_name,
      clean_uom,
      dataset_track,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      AVG(avg_unit_price)::double precision AS avg_unit_price,
      (AVG(margin_pct) * 100.0)::double precision AS avg_margin_pct
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY product_name, clean_uom, dataset_track
    ORDER BY SUM(sold_qty) DESC
    LIMIT %s
    """.strip()
    return sql, (*params, *extra_params, int(limit))


def sql_brand_product_treemap(schema: str, filters: FilterState, *, limit: int = 80) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(
        filters,
        extra_conditions=("brand_name IS NOT NULL", "product_name IS NOT NULL"),
    )
    sql = f"""
    SELECT
      brand_name,
      product_name,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY brand_name, product_name
    ORDER BY SUM(sold_qty) DESC
    LIMIT %s
    """.strip()
    return sql, (*params, int(limit))


def sql_unit_price_distribution(
    schema: str,
    filters: FilterState,
    *,
    bins: int = 24,
) -> tuple[str, tuple[Any, ...]]:
    """Compute exact full-table unit-price histogram inside PostgreSQL via WIDTH_BUCKET."""
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, extra_conditions=("avg_unit_price IS NOT NULL",))
    n_bins = max(5, int(bins))
    sql = f"""
    WITH filtered AS (
      SELECT avg_unit_price, dataset_track
      FROM "{s}"."bi_sales_weather_enriched"
      {where_sql}
    ),
    bounds AS (
      SELECT
        MIN(avg_unit_price)::double precision AS min_p,
        GREATEST(MAX(avg_unit_price)::double precision + 1e-6, MIN(avg_unit_price)::double precision + 1.0) AS max_p
      FROM filtered
    ),
    bucketed AS (
      SELECT
        f.dataset_track,
        LEAST(WIDTH_BUCKET(f.avg_unit_price, b.min_p, b.max_p, %s), %s) AS bucket_id,
        b.min_p,
        b.max_p
      FROM filtered f
      CROSS JOIN bounds b
    )
    SELECT
      dataset_track,
      bucket_id,
      COUNT(*)::bigint AS obs_count,
      (min_p + (bucket_id - 1) * (max_p - min_p) / %s)::double precision AS bin_start,
      (min_p + bucket_id * (max_p - min_p) / %s)::double precision AS bin_end
    FROM bucketed
    GROUP BY dataset_track, bucket_id, min_p, max_p
    ORDER BY bucket_id
    """.strip()
    return sql, (*params, n_bins, n_bins, n_bins, n_bins)


def sql_atc_monthly_trend(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    clauses: list[str] = []
    params: list[Any] = []
    if filters.date_start is not None:
        clauses.append("year_month >= DATE_TRUNC('month', %s::date)::date")
        params.append(filters.date_start)
    if filters.date_end is not None:
        clauses.append("year_month <= DATE_TRUNC('month', %s::date)::date")
        params.append(filters.date_end)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
    SELECT
      year_month,
      category_code,
      category_name,
      SUM(total_observed_qty)::double precision AS total_observed_qty
    FROM "{s}"."bi_atc_category_monthly"
    {where_sql}
    GROUP BY year_month, category_code, category_name
    ORDER BY year_month, category_code
    """.strip()
    return sql, tuple(params)


def sql_atc_month_heatmap(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    clauses: list[str] = []
    params: list[Any] = []
    if filters.date_start is not None:
        clauses.append("year_month >= DATE_TRUNC('month', %s::date)::date")
        params.append(filters.date_start)
    if filters.date_end is not None:
        clauses.append("year_month <= DATE_TRUNC('month', %s::date)::date")
        params.append(filters.date_end)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
    SELECT
      month_num,
      category_code,
      category_name,
      SUM(total_observed_qty)::double precision AS total_observed_qty
    FROM "{s}"."bi_atc_category_monthly"
    {where_sql}
    GROUP BY month_num, category_code, category_name
    ORDER BY month_num, category_code
    """.strip()
    return sql, tuple(params)


def sql_irpd_top_manufacturers(schema: str, filters: FilterState, *, limit: int = 15) -> tuple[str, tuple[Any, ...]]:
    """Locked to IRPD_ID_OBSERVED (IDR) because ONYX_EU_SYNTHETIC has NULL manufacturer_name."""
    s = validate_schema(schema)
    where_sql, params = build_where_clause(
        filters,
        override_track="IRPD_ID_OBSERVED",
        extra_conditions=("manufacturer_name IS NOT NULL",),
    )
    sql = f"""
    SELECT
      manufacturer_name,
      SUM(line_amount)::double precision AS line_amount,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(order_count)::bigint AS order_count
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY manufacturer_name
    ORDER BY SUM(line_amount) DESC
    LIMIT %s
    """.strip()
    return sql, (*params, int(limit))


def sql_atc_category_ranking(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    clauses: list[str] = []
    params: list[Any] = []
    if filters.date_start is not None:
        clauses.append("year_month >= DATE_TRUNC('month', %s::date)::date")
        params.append(filters.date_start)
    if filters.date_end is not None:
        clauses.append("year_month <= DATE_TRUNC('month', %s::date)::date")
        params.append(filters.date_end)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
    SELECT
      category_code,
      category_name,
      SUM(total_observed_qty)::double precision AS total_observed_qty,
      AVG(avg_daily_qty)::double precision AS avg_daily_qty,
      SUM(observation_count)::bigint AS observation_count
    FROM "{s}"."bi_atc_category_monthly"
    {where_sql}
    GROUP BY category_code, category_name
    ORDER BY SUM(total_observed_qty) DESC
    """.strip()
    return sql, tuple(params)
