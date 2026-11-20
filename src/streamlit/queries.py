"""Parameterized PostgreSQL pushdown query builders for PharmaFlow BI Streamlit."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Sequence

from config import DEFAULT_TRACK, TRACK_META

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEFAULT_SCHEMA = "quick_gold_md01"
EU_STORE_MATRIX_TRACK = "ONYX_EU_SYNTHETIC"


def validate_schema(name: str) -> str:
    """Reject unsafe SQL schema identifiers."""
    cleaned = (name or "").strip()
    if not _IDENT_RE.match(cleaned):
        raise ValueError(f"Unsafe SQL schema identifier: {name!r}")
    return cleaned


@dataclass(frozen=True)
class FilterState:
    """Shared cross-page filter state; page-2 weather controls stay isolated to Page 2."""

    dataset_track: str | None = DEFAULT_TRACK
    countries: tuple[str, ...] = field(default_factory=tuple)
    stores: tuple[str, ...] = field(default_factory=tuple)
    clean_uoms: tuple[str, ...] = field(default_factory=tuple)
    date_start: date | None = None
    date_end: date | None = None
    temp_bands: tuple[str, ...] = field(default_factory=tuple)
    compare_mode: str = "latest_full_month"
    # Optional page-2-only weather filters (only injected via dataclasses.replace on Page 2)
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
    ignore_dates: bool = False,
    keep_dates_on_override: bool = False,
    date_override: tuple[date, date] | None = None,
    alias: str = "",
    extra_conditions: Sequence[str] = (),
) -> tuple[str, tuple[Any, ...]]:
    """Build parameterized SQL WHERE clause against bi_sales_weather_enriched.

    When ``override_track`` equals ``filters.dataset_track``, active country, store,
    UOM, weather, and date filters are preserved. When overriding to a *different*
    track (or ignoring track altogether), incompatible track-specific filters are
    excluded cleanly so cross-track panels stay consistent and explicit.
    """
    prefix = f"{alias}." if alias else ""
    clauses: list[str] = []
    params: list[Any] = []

    effective_track = None if ignore_track else (override_track if override_track is not None else filters.dataset_track)
    if effective_track:
        clauses.append(f"{prefix}dataset_track = %s")
        params.append(effective_track)

    same_track_scope = (not ignore_track) and (
        override_track is None or override_track == filters.dataset_track
    )

    if same_track_scope:
        if filters.countries:
            clauses.append(f"{prefix}country_code = ANY(%s)")
            params.append(list(filters.countries))
        if filters.stores:
            clauses.append(f"{prefix}store_name = ANY(%s)")
            params.append(list(filters.stores))
        if filters.clean_uoms:
            clauses.append(f"{prefix}clean_uom = ANY(%s)")
            params.append(list(filters.clean_uoms))

    apply_dates = not ignore_dates and (same_track_scope or keep_dates_on_override)
    if apply_dates:
        d_start = date_override[0] if date_override is not None else filters.date_start
        d_end = date_override[1] if date_override is not None else filters.date_end
        if d_start is not None:
            clauses.append(f"{prefix}local_date >= %s")
            params.append(d_start)
        if d_end is not None:
            clauses.append(f"{prefix}local_date <= %s")
            params.append(d_end)

    if same_track_scope:
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


def sql_filter_options(
    schema: str,
    dataset_track: str | None,
    countries: Sequence[str] = (),
) -> tuple[str, tuple[Any, ...]]:
    """Return track bounds plus cascading country/UOM/store option lists."""
    s = validate_schema(schema)
    base_where = "WHERE dataset_track = %s" if dataset_track else ""
    base_params: list[Any] = [dataset_track] if dataset_track else []

    store_clauses: list[str] = []
    store_params: list[Any] = []
    if dataset_track:
        store_clauses.append("dataset_track = %s")
        store_params.append(dataset_track)
    if countries:
        store_clauses.append("country_code = ANY(%s)")
        store_params.append(list(countries))
    store_where = ("WHERE " + " AND ".join(store_clauses)) if store_clauses else ""

    sql = f"""
    WITH base AS (
      SELECT
        MIN(local_date) AS min_date,
        MAX(local_date) AS max_date,
        ARRAY_REMOVE(ARRAY_AGG(DISTINCT country_code ORDER BY country_code), NULL) AS countries,
        ARRAY_REMOVE(ARRAY_AGG(DISTINCT clean_uom ORDER BY clean_uom), NULL) AS uoms
      FROM "{s}"."bi_sales_weather_enriched"
      {base_where}
    ),
    store_list AS (
      SELECT ARRAY_REMOVE(ARRAY_AGG(DISTINCT store_name ORDER BY store_name), NULL) AS stores
      FROM "{s}"."bi_sales_weather_enriched"
      {store_where}
    )
    SELECT b.min_date, b.max_date, b.countries, b.uoms, sl.stores
    FROM base b
    CROSS JOIN store_list sl
    """.strip()
    return sql, tuple([*base_params, *store_params])


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
# Page 1: Executive Overview (Tổng Quan) & Comparison Queries
# ---------------------------------------------------------------------------

def sql_exec_kpis(
    schema: str,
    filters: FilterState,
    *,
    date_override: tuple[date, date] | None = None,
) -> tuple[str, tuple[Any, ...]]:
    """Headline KPIs with null-safe weighted margin & weighted unit price (no non-additive order_count)."""
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, date_override=date_override)
    sql = f"""
    SELECT
      SUM(line_amount)::double precision AS total_revenue,
      SUM(sold_qty)::double precision AS total_sold_qty,
      COALESCE(SUM(line_count), 0)::bigint AS total_line_count,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days,
      COUNT(DISTINCT store_id)::bigint AS active_stores,
      ARRAY_REMOVE(ARRAY_AGG(DISTINCT clean_uom ORDER BY clean_uom), NULL) AS distinct_uoms,
      SUM(margin_amount)::double precision AS total_margin,
      (
        SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN margin_amount END)
        / NULLIF(SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN line_amount END), 0)
      )::double precision AS weighted_margin_pct,
      AVG(margin_pct)::double precision AS row_avg_margin_pct,
      (
        SUM(CASE WHEN line_amount IS NOT NULL AND sold_qty > 0 THEN line_amount END)
        / NULLIF(SUM(CASE WHEN line_amount IS NOT NULL AND sold_qty > 0 THEN sold_qty END), 0)
      )::double precision AS weighted_unit_price,
      AVG(avg_unit_price)::double precision AS row_avg_unit_price,
      MIN(currency_code) AS currency_code,
      MIN(provenance_class) AS provenance_class,
      COUNT(line_amount) AS rev_rows,
      COUNT(margin_amount) AS margin_rows,
      COUNT(*) AS row_count
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    """.strip()
    return sql, params


def sql_uom_breakdown(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    SELECT
      COALESCE(clean_uom, 'Chưa rõ') AS clean_uom,
      COUNT(*)::bigint AS mart_rows,
      COALESCE(SUM(line_count), 0)::bigint AS line_count,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      (
        SUM(CASE WHEN line_amount IS NOT NULL AND sold_qty > 0 THEN line_amount END)
        / NULLIF(SUM(CASE WHEN line_amount IS NOT NULL AND sold_qty > 0 THEN sold_qty END), 0)
      )::double precision AS weighted_unit_price
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY COALESCE(clean_uom, 'Chưa rõ')
    ORDER BY COALESCE(SUM(line_amount), SUM(sold_qty)) DESC NULLS LAST
    """.strip()
    return sql, params


def sql_monthly_sales_trend(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    """Aggregate monthly sales strictly inside the exact same FilterState scope as KPIs."""
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    SELECT
      year_month,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      SUM(margin_amount)::double precision AS margin_amount,
      COALESCE(SUM(line_count), 0)::bigint AS line_count,
      COUNT(DISTINCT local_date)::int AS active_days,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days,
      MIN(local_date) AS first_date,
      MAX(local_date) AS last_date
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY year_month
    ORDER BY year_month
    """.strip()
    return sql, params


def sql_series_avg_growth_reference(
    schema: str,
    filters: FilterState,
) -> tuple[str, tuple[Any, ...]]:
    """Reference series-level AVG(sold_qty_pct_change) from kpi_sales_trend (never use as aggregate MoM)."""
    s = validate_schema(schema)
    clauses = ["period_granularity = 'MONTH'"]
    params: list[Any] = []
    if filters.dataset_track:
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
      AVG(sold_qty_pct_change)::double precision AS series_avg_pct_change,
      COUNT(sold_qty_pct_change)::bigint AS series_pct_rows,
      COALESCE(SUM(line_count), 0)::bigint AS line_count
    FROM "{s}"."kpi_sales_trend"
    {where_sql}
    GROUP BY period_start
    ORDER BY period_start
    """.strip()
    return sql, tuple(params)


def sql_dimension_variance(
    schema: str,
    filters: FilterState,
    *,
    dim_kind: str,
    cur_start: date,
    cur_end: date,
    prev_start: date,
    prev_end: date,
    search_text: str = "",
    limit: int | None = None,
) -> tuple[str, tuple[Any, ...]]:
    """Compute side-by-side cur vs prev totals for variance, contribution, and mix shift.

    Defaults to ``limit=None`` so contribution and mix-shift denominators cover the full
    filtered catalog across both periods (including prior-only items and unlabelled groups).
    """
    s = validate_schema(schema)
    span_start = min(cur_start, prev_start)
    span_end = max(cur_end, prev_end)

    extra: list[str] = []
    extra_params: list[Any] = []
    cleaned_search = (search_text or "").strip()

    if dim_kind == "country":
        select_dims = "COALESCE(NULLIF(TRIM(country_code), ''), 'Chưa xác định') AS country_code"
        group_dims = "COALESCE(NULLIF(TRIM(country_code), ''), 'Chưa xác định')"
        nonnull_expr = "COUNT(NULLIF(TRIM(country_code), ''))::bigint AS nonnull_label_rows"
    elif dim_kind == "brand":
        select_dims = "COALESCE(NULLIF(TRIM(brand_name), ''), 'Chưa xác định') AS brand_name"
        group_dims = "COALESCE(NULLIF(TRIM(brand_name), ''), 'Chưa xác định')"
        nonnull_expr = "COUNT(NULLIF(TRIM(brand_name), ''))::bigint AS nonnull_label_rows"
    elif dim_kind == "store":
        select_dims = (
            "COALESCE(NULLIF(TRIM(store_code), ''), 'Chưa xác định') AS store_code, "
            "COALESCE(NULLIF(TRIM(store_name), ''), 'Chưa xác định') AS store_name, "
            "COALESCE(NULLIF(TRIM(country_code), ''), 'Chưa xác định') AS country_code"
        )
        group_dims = (
            "COALESCE(NULLIF(TRIM(store_code), ''), 'Chưa xác định'), "
            "COALESCE(NULLIF(TRIM(store_name), ''), 'Chưa xác định'), "
            "COALESCE(NULLIF(TRIM(country_code), ''), 'Chưa xác định')"
        )
        nonnull_expr = "COUNT(NULLIF(TRIM(store_name), ''))::bigint AS nonnull_label_rows"
        if cleaned_search:
            extra.append("(store_code ILIKE %s OR store_name ILIKE %s OR country_code ILIKE %s)")
            like = f"%{cleaned_search}%"
            extra_params.extend([like, like, like])
    elif dim_kind == "product":
        select_dims = (
            "COALESCE(NULLIF(TRIM(product_name), ''), 'Chưa xác định') AS product_name, "
            "COALESCE(NULLIF(TRIM(clean_uom), ''), 'Chưa xác định') AS clean_uom"
        )
        group_dims = (
            "COALESCE(NULLIF(TRIM(product_name), ''), 'Chưa xác định'), "
            "COALESCE(NULLIF(TRIM(clean_uom), ''), 'Chưa xác định')"
        )
        nonnull_expr = "COUNT(NULLIF(TRIM(product_name), ''))::bigint AS nonnull_label_rows"
        if cleaned_search:
            extra.append("(product_name ILIKE %s OR brand_name ILIKE %s OR clean_uom ILIKE %s)")
            like = f"%{cleaned_search}%"
            extra_params.extend([like, like, like])
    else:
        raise ValueError(f"Unsupported dim_kind: {dim_kind!r}")

    where_sql, where_params = build_where_clause(
        filters,
        date_override=(span_start, span_end),
        extra_conditions=extra,
    )

    limit_sql = ""
    limit_params: list[Any] = []
    if limit is not None:
        limit_sql = "\n    LIMIT %s"
        limit_params.append(int(limit))

    sql = f"""
    SELECT
      {select_dims},
      {nonnull_expr},
      COALESCE(SUM(CASE WHEN local_date BETWEEN %s AND %s THEN sold_qty END), 0)::double precision AS cur_qty,
      COALESCE(SUM(CASE WHEN local_date BETWEEN %s AND %s THEN sold_qty END), 0)::double precision AS prev_qty,
      SUM(CASE WHEN local_date BETWEEN %s AND %s THEN line_amount END)::double precision AS cur_rev,
      SUM(CASE WHEN local_date BETWEEN %s AND %s THEN line_amount END)::double precision AS prev_rev,
      SUM(CASE WHEN local_date BETWEEN %s AND %s THEN margin_amount END)::double precision AS cur_mrg,
      SUM(CASE WHEN local_date BETWEEN %s AND %s THEN margin_amount END)::double precision AS prev_mrg,
      COALESCE(SUM(CASE WHEN local_date BETWEEN %s AND %s THEN line_count END), 0)::bigint AS cur_lines,
      COALESCE(SUM(CASE WHEN local_date BETWEEN %s AND %s THEN line_count END), 0)::bigint AS prev_lines,
      COUNT(DISTINCT CASE WHEN local_date BETWEEN %s AND %s THEN (store_id, local_date) END)::bigint AS cur_store_days,
      COUNT(DISTINCT CASE WHEN local_date BETWEEN %s AND %s THEN (store_id, local_date) END)::bigint AS prev_store_days,
      (
        SUM(CASE WHEN local_date BETWEEN %s AND %s AND margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN margin_amount END)
        / NULLIF(SUM(CASE WHEN local_date BETWEEN %s AND %s AND margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN line_amount END), 0)
        * 100.0
      )::double precision AS cur_weighted_margin_pct,
      (
        SUM(CASE WHEN local_date BETWEEN %s AND %s AND margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN margin_amount END)
        / NULLIF(SUM(CASE WHEN local_date BETWEEN %s AND %s AND margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN line_amount END), 0)
        * 100.0
      )::double precision AS prev_weighted_margin_pct
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY {group_dims}
    ORDER BY COALESCE(SUM(ABS(line_amount)), SUM(ABS(sold_qty))) DESC NULLS LAST,
    SUM(sold_qty) DESC{limit_sql}
    """.strip()

    win_params: list[Any] = [
        cur_start, cur_end, prev_start, prev_end,  # qty
        cur_start, cur_end, prev_start, prev_end,  # rev
        cur_start, cur_end, prev_start, prev_end,  # mrg
        cur_start, cur_end, prev_start, prev_end,  # lines
        cur_start, cur_end, prev_start, prev_end,  # store_days
        cur_start, cur_end, cur_start, cur_end,    # cur margin
        prev_start, prev_end, prev_start, prev_end,  # prev margin
    ]
    return sql, tuple([*win_params, *where_params, *extra_params, *limit_params])


def sql_sales_by_country(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    SELECT
      country_code,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      COALESCE(SUM(line_count), 0)::bigint AS line_count,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY country_code
    ORDER BY COALESCE(SUM(line_amount), SUM(sold_qty)) DESC NULLS LAST
    """.strip()
    return sql, params


def sql_top_brands(schema: str, filters: FilterState, *, limit: int = 15) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, extra_conditions=("brand_name IS NOT NULL",))
    sql = f"""
    SELECT
      brand_name,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      SUM(margin_amount)::double precision AS margin_amount,
      COALESCE(SUM(line_count), 0)::bigint AS line_count
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
    where_sql, params = build_where_clause(
        filters,
        ignore_track=show_all_tracks,
        ignore_dates=show_all_tracks,
    )
    sql = f"""
    SELECT
      dataset_track,
      COALESCE(currency_code, 'N/A') AS currency_code,
      provenance_class,
      COUNT(DISTINCT clean_uom)::int AS distinct_uom_count,
      MIN(local_date) AS min_date,
      MAX(local_date) AS max_date,
      SUM(sold_qty)::double precision AS sold_qty,
      COALESCE(SUM(line_count), 0)::bigint AS line_count,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days,
      SUM(line_amount)::double precision AS line_amount,
      SUM(margin_amount)::double precision AS margin_amount
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY dataset_track, COALESCE(currency_code, 'N/A'), provenance_class
    ORDER BY COUNT(*) DESC
    """.strip()
    return sql, params


# ---------------------------------------------------------------------------
# Page 2: Weather & Location (Thời Tiết & Địa Điểm)
# ---------------------------------------------------------------------------

def sql_weather_kpis(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    """Compute store-day normalized KPIs and store-day unweighted weather averages."""
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    WITH filtered AS (
      SELECT
        store_id,
        local_date,
        sold_qty,
        line_amount,
        line_count,
        temp_mean,
        apparent_temp_mean,
        precip_sum,
        humidity_mean
      FROM "{s}"."bi_sales_weather_enriched"
      {where_sql}
    ),
    sd AS (
      SELECT
        store_id,
        local_date,
        AVG(temp_mean) AS temp_mean,
        AVG(apparent_temp_mean) AS apparent_temp_mean,
        AVG(precip_sum) AS precip_sum,
        AVG(humidity_mean) AS humidity_mean
      FROM filtered
      GROUP BY store_id, local_date
    ),
    agg_sales AS (
      SELECT
        COUNT(DISTINCT store_id)::bigint AS active_stores,
        COUNT(DISTINCT local_date)::bigint AS active_dates,
        COALESCE((MAX(local_date) - MIN(local_date) + 1), 0)::bigint AS span_days,
        COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days,
        SUM(sold_qty)::double precision AS total_sold_qty,
        SUM(line_amount)::double precision AS total_revenue,
        COALESCE(SUM(line_count), 0)::bigint AS total_line_count,
        COUNT(*) FILTER (WHERE temp_mean IS NOT NULL)::bigint AS weather_covered_rows,
        COUNT(*)::bigint AS row_count
      FROM filtered
    ),
    agg_weather AS (
      SELECT
        AVG(temp_mean)::double precision AS avg_temp_mean,
        AVG(apparent_temp_mean)::double precision AS avg_apparent_temp_mean,
        AVG(precip_sum)::double precision AS avg_precip_sum,
        AVG(humidity_mean)::double precision AS avg_humidity_mean,
        COUNT(*) FILTER (WHERE precip_sum > 0)::bigint AS rainy_store_days
      FROM sd
    )
    SELECT
      a.active_stores,
      a.active_dates,
      a.span_days,
      (a.active_stores * a.span_days)::bigint AS possible_store_days,
      a.active_store_days,
      a.total_sold_qty,
      a.total_revenue,
      a.total_line_count,
      (a.total_sold_qty / NULLIF(a.active_store_days, 0))::double precision AS qty_per_store_day,
      (a.total_revenue / NULLIF(a.active_store_days, 0))::double precision AS rev_per_store_day,
      (a.total_sold_qty / NULLIF(a.active_stores, 0))::double precision AS avg_qty_per_store,
      w.avg_temp_mean,
      w.avg_apparent_temp_mean,
      w.avg_precip_sum,
      w.avg_humidity_mean,
      w.rainy_store_days,
      a.weather_covered_rows,
      a.row_count
    FROM agg_sales a
    CROSS JOIN agg_weather w
    """.strip()
    return sql, params


def sql_temp_rain_heatmap(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    """Aggregate by temp_band x rain_regime with normalized store-day rate & sample sizes."""
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, ignore_weather_cell=True)
    sql = f"""
    SELECT
      temp_band,
      rain_regime,
      COUNT(*)::bigint AS mart_rows,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days,
      COUNT(DISTINCT local_date)::bigint AS active_days,
      COUNT(DISTINCT store_id)::bigint AS distinct_stores,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      (SUM(sold_qty) / NULLIF(COUNT(DISTINCT (store_id, local_date)), 0))::double precision AS qty_per_store_day,
      (SUM(line_amount) / NULLIF(COUNT(DISTINCT (store_id, local_date)), 0))::double precision AS rev_per_store_day
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
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      (SUM(sold_qty) / NULLIF(COUNT(DISTINCT (store_id, local_date)), 0))::double precision AS qty_per_store_day,
      (SUM(line_amount) / NULLIF(COUNT(DISTINCT (store_id, local_date)), 0))::double precision AS rev_per_store_day
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY humidity_band, is_weekend
    ORDER BY humidity_band, is_weekend
    """.strip()
    return sql, params


def sql_daily_temp_scatter(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    """Daily store-day temp_mean vs normalized sales rate & raw sales colored by rain_regime."""
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, extra_conditions=("temp_mean IS NOT NULL",))
    sql = f"""
    WITH filtered AS (
      SELECT store_id, local_date, rain_regime, temp_mean, sold_qty, line_amount, line_count
      FROM "{s}"."bi_sales_weather_enriched"
      {where_sql}
    ),
    sd_weather AS (
      SELECT store_id, local_date, rain_regime, AVG(temp_mean) AS temp_mean
      FROM filtered
      GROUP BY store_id, local_date, rain_regime
    ),
    day_weather AS (
      SELECT local_date, rain_regime, AVG(temp_mean)::double precision AS temp_mean
      FROM sd_weather
      GROUP BY local_date, rain_regime
    )
    SELECT
      f.local_date,
      f.rain_regime,
      dw.temp_mean,
      COUNT(DISTINCT f.store_id)::bigint AS active_stores,
      SUM(f.sold_qty)::double precision AS sold_qty,
      SUM(f.line_amount)::double precision AS line_amount,
      (SUM(f.sold_qty) / NULLIF(COUNT(DISTINCT f.store_id), 0))::double precision AS qty_per_store_day,
      (SUM(f.line_amount) / NULLIF(COUNT(DISTINCT f.store_id), 0))::double precision AS rev_per_store_day,
      COALESCE(SUM(f.line_count), 0)::bigint AS line_count
    FROM filtered f
    INNER JOIN day_weather dw
      ON f.local_date = dw.local_date AND f.rain_regime = dw.rain_regime
    GROUP BY f.local_date, f.rain_regime, dw.temp_mean
    ORDER BY f.local_date
    """.strip()
    return sql, params


def sql_monthly_weather_seasonality(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    """Monthly store-day weather averages vs normalized sales rate per active store-day."""
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    WITH filtered AS (
      SELECT
        year_month, store_id, local_date,
        sold_qty, line_amount, line_count,
        temp_mean, apparent_temp_mean, precip_sum, humidity_mean
      FROM "{s}"."bi_sales_weather_enriched"
      {where_sql}
    ),
    sd AS (
      SELECT
        year_month, store_id, local_date,
        AVG(temp_mean) AS temp_mean,
        AVG(apparent_temp_mean) AS apparent_temp_mean,
        AVG(precip_sum) AS precip_sum,
        AVG(humidity_mean) AS humidity_mean
      FROM filtered
      GROUP BY year_month, store_id, local_date
    ),
    w_month AS (
      SELECT
        year_month,
        AVG(temp_mean)::double precision AS avg_temp_mean,
        AVG(apparent_temp_mean)::double precision AS avg_apparent_temp_mean,
        AVG(precip_sum)::double precision AS avg_precip_sum,
        AVG(humidity_mean)::double precision AS avg_humidity_mean
      FROM sd
      GROUP BY year_month
    )
    SELECT
      f.year_month,
      COUNT(DISTINCT (f.store_id, f.local_date))::bigint AS active_store_days,
      COUNT(DISTINCT f.local_date)::int AS active_days,
      SUM(f.sold_qty)::double precision AS sold_qty,
      SUM(f.line_amount)::double precision AS line_amount,
      (SUM(f.sold_qty) / NULLIF(COUNT(DISTINCT (f.store_id, f.local_date)), 0))::double precision AS qty_per_store_day,
      (SUM(f.line_amount) / NULLIF(COUNT(DISTINCT (f.store_id, f.local_date)), 0))::double precision AS rev_per_store_day,
      w.avg_temp_mean,
      w.avg_apparent_temp_mean,
      w.avg_precip_sum,
      w.avg_humidity_mean
    FROM filtered f
    LEFT JOIN w_month w ON f.year_month = w.year_month
    GROUP BY f.year_month, w.avg_temp_mean, w.avg_apparent_temp_mean, w.avg_precip_sum, w.avg_humidity_mean
    ORDER BY f.year_month
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
          COALESCE(SUM(line_count), 0)::bigint AS line_count,
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
        WITH filtered AS (
          SELECT
            local_date, store_id, sold_qty, line_count, line_amount,
            temp_mean, precip_sum, humidity_mean
          FROM "{s}"."bi_sales_weather_enriched"
          {where_sql}
        ),
        sd AS (
          SELECT local_date, store_id,
                 AVG(temp_mean) AS temp_mean,
                 AVG(precip_sum) AS precip_sum,
                 AVG(humidity_mean) AS humidity_mean
          FROM filtered
          GROUP BY local_date, store_id
        ),
        day_w AS (
          SELECT local_date,
                 AVG(temp_mean)::double precision AS temp_mean,
                 AVG(precip_sum)::double precision AS precip_sum,
                 AVG(humidity_mean)::double precision AS humidity_mean
          FROM sd
          GROUP BY local_date
        )
        SELECT
          f.local_date,
          COUNT(DISTINCT f.store_id)::bigint AS active_stores,
          SUM(f.sold_qty)::double precision AS sold_qty,
          (SUM(f.sold_qty) / NULLIF(COUNT(DISTINCT f.store_id), 0))::double precision AS qty_per_store_day,
          COALESCE(SUM(f.line_count), 0)::bigint AS line_count,
          dw.temp_mean,
          dw.precip_sum,
          dw.humidity_mean,
          SUM(f.line_amount)::double precision AS line_amount
        FROM filtered f
        LEFT JOIN day_w dw ON f.local_date = dw.local_date
        GROUP BY f.local_date, dw.temp_mean, dw.precip_sum, dw.humidity_mean
        ORDER BY f.local_date DESC
        LIMIT %s
        """.strip()
    return sql, (*params, int(limit))


def sql_top_products_by_rain(
    schema: str,
    filters: FilterState,
    *,
    limit: int = 15,
    rank_by_revenue: bool = False,
) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, extra_conditions=("product_name IS NOT NULL",))
    order_expr = "SUM(line_amount)" if rank_by_revenue else "SUM(sold_qty)"
    m_where_sql, m_params = build_where_clause(filters, alias="m", extra_conditions=("m.product_name IS NOT NULL",))
    sql = f"""
    WITH top_products AS (
      SELECT product_name, {order_expr}::double precision AS total_metric
      FROM "{s}"."bi_sales_weather_enriched"
      {where_sql}
      GROUP BY product_name
      ORDER BY {order_expr} DESC NULLS LAST
      LIMIT %s
    )
    SELECT
      m.product_name,
      m.rain_regime,
      COUNT(DISTINCT (m.store_id, m.local_date))::bigint AS active_store_days,
      SUM(m.sold_qty)::double precision AS sold_qty,
      SUM(m.line_amount)::double precision AS line_amount,
      tp.total_metric
    FROM "{s}"."bi_sales_weather_enriched" m
    INNER JOIN top_products tp ON m.product_name = tp.product_name
    {m_where_sql}
    GROUP BY m.product_name, m.rain_regime, tp.total_metric
    ORDER BY tp.total_metric DESC NULLS LAST, m.rain_regime
    """.strip()
    return sql, (*params, int(limit), *m_params)


def sql_weekday_by_rain(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters)
    sql = f"""
    SELECT
      day_of_week_num,
      day_of_week,
      rain_regime,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      (SUM(sold_qty) / NULLIF(COUNT(DISTINCT (store_id, local_date)), 0))::double precision AS qty_per_store_day,
      (SUM(line_amount) / NULLIF(COUNT(DISTINCT (store_id, local_date)), 0))::double precision AS rev_per_store_day
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY day_of_week_num, day_of_week, rain_regime
    ORDER BY day_of_week_num, rain_regime
    """.strip()
    return sql, params


# ---------------------------------------------------------------------------
# Page 3: Stores & Margin (Cửa Hàng & Biên Lợi Nhuận)
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
      (
        SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN margin_amount END)
        / NULLIF(SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN line_amount END), 0)
        * 100.0
      )::double precision AS weighted_margin_pct,
      COUNT(DISTINCT store_id)::bigint AS store_count,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days,
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


def sql_eu_promo_breakdown(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    """Return weighted promo volume share + observed split by has_promotion (non-causal)."""
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, override_track="ONYX_EU_SYNTHETIC")
    sql = f"""
    SELECT
      COALESCE(has_promotion, false) AS has_promotion,
      COUNT(*)::bigint AS mart_rows,
      COALESCE(SUM(line_count), 0)::bigint AS line_count,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(promo_sold_qty)::double precision AS promo_sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      SUM(margin_amount)::double precision AS margin_amount,
      (
        SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN margin_amount END)
        / NULLIF(SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN line_amount END), 0)
        * 100.0
      )::double precision AS weighted_margin_pct,
      (
        SUM(CASE WHEN line_amount IS NOT NULL AND sold_qty > 0 THEN line_amount END)
        / NULLIF(SUM(CASE WHEN line_amount IS NOT NULL AND sold_qty > 0 THEN sold_qty END), 0)
      )::double precision AS weighted_unit_price,
      AVG(promo_share_pct)::double precision AS avg_row_promo_share
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY COALESCE(has_promotion, false)
    ORDER BY COALESCE(has_promotion, false) DESC
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
      (
        SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN margin_amount END)
        / NULLIF(SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN line_amount END), 0)
        * 100.0
      )::double precision AS weighted_margin_pct,
      (AVG(margin_pct) * 100.0)::double precision AS row_avg_margin_pct,
      SUM(sold_qty)::double precision AS sold_qty
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY brand_name
    ORDER BY SUM(margin_amount) DESC NULLS LAST
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
      COALESCE(SUM(line_count), 0)::bigint AS line_count,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days,
      SUM(line_amount)::double precision AS line_amount,
      SUM(margin_amount)::double precision AS margin_amount,
      (
        SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN margin_amount END)
        / NULLIF(SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN line_amount END), 0)
        * 100.0
      )::double precision AS weighted_margin_pct,
      (AVG(margin_pct) * 100.0)::double precision AS row_avg_margin_pct
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY store_code, store_name, country_code, source
    ORDER BY COALESCE(SUM(line_amount), SUM(sold_qty)) DESC NULLS LAST
    """.strip()
    return sql, (*params, *extra_params)


def sql_eu_store_matrix(schema: str, filters: FilterState) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    where_sql, params = build_where_clause(filters, override_track=EU_STORE_MATRIX_TRACK)
    sql = f"""
    SELECT
      store_code,
      store_name,
      country_code,
      MAX(dataset_track) AS dataset_track,
      MAX(provenance_class) AS provenance_class,
      MAX(currency_code) AS currency_code,
      SUM(line_amount)::double precision AS line_amount,
      SUM(margin_amount)::double precision AS margin_amount,
      (
        SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN margin_amount END)
        / NULLIF(SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN line_amount END), 0)
        * 100.0
      )::double precision AS weighted_margin_pct,
      (AVG(margin_pct) * 100.0)::double precision AS row_avg_margin_pct,
      SUM(sold_qty)::double precision AS sold_qty,
      COALESCE(SUM(line_count), 0)::bigint AS line_count,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days
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
      COALESCE(SUM(line_count), 0)::bigint AS line_count,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount,
      (
        SUM(CASE WHEN line_amount IS NOT NULL AND sold_qty > 0 THEN line_amount END)
        / NULLIF(SUM(CASE WHEN line_amount IS NOT NULL AND sold_qty > 0 THEN sold_qty END), 0)
      )::double precision AS weighted_unit_price,
      (
        SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN margin_amount END)
        / NULLIF(SUM(CASE WHEN margin_amount IS NOT NULL AND line_amount IS NOT NULL THEN line_amount END), 0)
        * 100.0
      )::double precision AS weighted_margin_pct
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY product_name, clean_uom, dataset_track
    ORDER BY COALESCE(SUM(line_amount), SUM(sold_qty)) DESC NULLS LAST
    LIMIT %s
    """.strip()
    return sql, (*params, *extra_params, int(limit))


def sql_brand_product_treemap(
    schema: str,
    filters: FilterState,
    *,
    limit: int = 80,
    use_revenue: bool = False,
) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    extra = ["brand_name IS NOT NULL", "product_name IS NOT NULL"]
    if use_revenue:
        extra.append("line_amount IS NOT NULL")
    where_sql, params = build_where_clause(filters, extra_conditions=extra)
    order_col = "SUM(line_amount)" if use_revenue else "SUM(sold_qty)"
    sql = f"""
    SELECT
      brand_name,
      product_name,
      clean_uom,
      SUM(sold_qty)::double precision AS sold_qty,
      SUM(line_amount)::double precision AS line_amount
    FROM "{s}"."bi_sales_weather_enriched"
    {where_sql}
    GROUP BY brand_name, product_name, clean_uom
    ORDER BY {order_col} DESC NULLS LAST
    LIMIT %s
    """.strip()
    return sql, (*params, int(limit))


def sql_unit_price_distribution(
    schema: str,
    filters: FilterState,
    *,
    bins: int = 24,
) -> tuple[str, tuple[Any, ...]]:
    """Compute exact mart-row (product x store x day) unit-price histogram inside PostgreSQL via WIDTH_BUCKET."""
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


def sql_atc_summary_meta(schema: str) -> tuple[str, tuple[Any, ...]]:
    s = validate_schema(schema)
    sql = f"""
    SELECT
      MIN(year_month) AS min_ym,
      MAX(year_month) AS max_ym,
      STRING_AGG(DISTINCT country_code, ', ' ORDER BY country_code) AS countries,
      MIN(provenance_class) AS provenance_class,
      MIN(source) AS source,
      COUNT(*)::bigint AS month_cat_rows
    FROM "{s}"."bi_atc_category_monthly"
    """.strip()
    return sql, ()


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
    """Locked to IRPD_ID_OBSERVED (IDR); preserves user filters when IRPD is already selected."""
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
      COALESCE(SUM(line_count), 0)::bigint AS line_count,
      COUNT(DISTINCT (store_id, local_date))::bigint AS active_store_days
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
