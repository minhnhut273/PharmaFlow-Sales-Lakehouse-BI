"""Automated unit, business-invariant, and Streamlit AppTest checks for BTL_BI/src/streamlit."""

from __future__ import annotations

import datetime as dt
import inspect
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import plotly.express as px
import pytest
from streamlit.testing.v1 import AppTest

STREAMLIT_DIR = Path(__file__).resolve().parents[1] / "src" / "streamlit"
if str(STREAMLIT_DIR) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_DIR))

import analytics  # noqa: E402
from components import filters as filter_comp  # noqa: E402
import config  # noqa: E402
import db  # noqa: E402
import queries  # noqa: E402
import ui  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Business Analytics Logic: Monthly Growth, Comparison, UOM Guard & Contributions
# ---------------------------------------------------------------------------

def test_compute_monthly_growth_total_aggregation_gap_zero_and_partial_months() -> None:
    df = pd.DataFrame(
        [
            {"year_month": dt.date(2024, 1, 1), "sold_qty": 18785.0, "line_amount": 360000.0, "margin_amount": 100000.0, "line_count": 2457, "active_days": 31, "active_store_days": 1700},
            {"year_month": dt.date(2024, 2, 1), "sold_qty": 17740.0, "line_amount": 342000.0, "margin_amount": 95000.0, "line_count": 2236, "active_days": 29, "active_store_days": 1580},
            # Gap: 2024-03 is intentionally missing
            {"year_month": dt.date(2024, 4, 1), "sold_qty": 0.0, "line_amount": 0.0, "margin_amount": 0.0, "line_count": 1, "active_days": 1, "active_store_days": 1},
            {"year_month": dt.date(2024, 5, 1), "sold_qty": 15000.0, "line_amount": 290000.0, "margin_amount": 80000.0, "line_count": 1900, "active_days": 31, "active_store_days": 1500},
            # Partial tail clipped on 2024-06-10
            {"year_month": dt.date(2024, 6, 1), "sold_qty": 5000.0, "line_amount": 95000.0, "margin_amount": 26000.0, "line_count": 650, "active_days": 10, "active_store_days": 520},
        ]
    )
    res = analytics.compute_monthly_growth(
        df,
        date_start=dt.date(2024, 1, 1),
        date_end=dt.date(2024, 6, 10),
        track_min_date=dt.date(2024, 1, 1),
        track_max_date=dt.date(2024, 12, 31),
    )
    assert list(res["month_label"]) == ["01/2024", "02/2024", "03/2024", "04/2024", "05/2024", "06/2024"]

    # Feb 2024 aggregate growth: (17740 - 18785) / 18785 = -5.5629%
    feb = res.loc[res["month_label"] == "02/2024"].iloc[0]
    assert feb["mom_status"] == "Hợp lệ"
    assert feb["mom_qty_diff"] == pytest.approx(-1045.0)
    assert feb["mom_qty_pct"] == pytest.approx((17740.0 - 18785.0) / 18785.0)

    # Gap month 03/2024 & post-gap 04/2024 must NOT bridge MoM across missing period
    mar = res.loc[res["month_label"] == "03/2024"].iloc[0]
    apr = res.loc[res["month_label"] == "04/2024"].iloc[0]
    assert mar["has_data"] is np.bool_(False) or (mar["has_data"] is False)
    assert pd.isna(mar["mom_qty_pct"])
    assert pd.isna(apr["mom_qty_pct"])
    assert apr["mom_status"] == "Tháng trước thiếu dữ liệu"

    # Zero prior denominator in Apr -> May must NOT divide by 0
    may = res.loc[res["month_label"] == "05/2024"].iloc[0]
    assert pd.isna(may["mom_qty_pct"])
    assert may["mom_status"] == "Mẫu số bằng 0"

    # User-clipped partial month 06/2024 must be flagged partial and excluded from MoM %
    jun = res.loc[res["month_label"] == "06/2024"].iloc[0]
    assert bool(jun["is_partial_month"]) is True
    assert pd.isna(jun["mom_qty_pct"])


def test_resolve_comparison_periods_skips_partial_and_handles_modes() -> None:
    # Serbia tail partial month (ends 2019-10-08): skip 10/2019 -> compare 09/2019 vs 08/2019
    months = [dt.date(2019, 7, 1), dt.date(2019, 8, 1), dt.date(2019, 9, 1), dt.date(2019, 10, 1)]
    win = analytics.resolve_comparison_periods(
        dt.date(2014, 1, 2),
        dt.date(2019, 10, 8),
        mode="latest_full_month",
        available_months=months,
        track_min_date=dt.date(2014, 1, 2),
        track_max_date=dt.date(2019, 10, 8),
    )
    assert win.valid is True
    assert win.mode == "latest_full_month"
    assert win.cur_start == dt.date(2019, 9, 1)
    assert win.cur_end == dt.date(2019, 9, 30)
    assert win.prev_start == dt.date(2019, 8, 1)
    assert win.prev_end == dt.date(2019, 8, 31)
    assert "10/2019" in win.note

    # Too short for 2 full months -> clean equal-length half split
    short_win = analytics.resolve_comparison_periods(
        dt.date(2024, 1, 10),
        dt.date(2024, 1, 29),
        mode="latest_full_month",
        available_months=[dt.date(2024, 1, 1)],
    )
    assert short_win.valid is True
    assert short_win.mode == "half_split"
    assert (short_win.cur_end - short_win.cur_start) == (short_win.prev_end - short_win.prev_start)

    # YoY fallback when < 24 full months exist
    yoy_fb = analytics.resolve_comparison_periods(
        dt.date(2024, 1, 1),
        dt.date(2024, 6, 30),
        mode="yoy_latest",
        available_months=[dt.date(2024, m, 1) for m in range(1, 7)],
    )
    assert yoy_fb.valid is True
    assert yoy_fb.mode == "latest_full_month"
    assert "24 tháng" in yoy_fb.note


def test_uom_guard_and_variance_contribution_math() -> None:
    blocked = analytics.evaluate_uom_compatibility("IRPD_ID_OBSERVED", (), ("tab", "pcs", "fls"))
    assert blocked.is_multi_uom_blocked is True
    assert blocked.uom_count == 3

    allowed = analytics.evaluate_uom_compatibility("IRPD_ID_OBSERVED", ("tab",), ("tab", "pcs", "fls"))
    assert allowed.is_multi_uom_blocked is False
    assert allowed.single_uom == "tab"

    raw = pd.DataFrame(
        [
            {"label": "A", "cur_val": 120.0, "prev_val": 100.0},
            {"label": "B", "cur_val": 70.0, "prev_val": 100.0},
            {"label": "C (new)", "cur_val": 30.0, "prev_val": 0.0},
        ]
    )
    var_df = analytics.compute_variance_and_contributions(raw)
    # Total prev = 200, total cur = 220 -> +10.00% overall growth -> sum(contrib_pp) MUST equal +10.0
    assert var_df["contrib_pp"].sum() == pytest.approx(10.0)
    # Mix shifts MUST sum to 0.0 percentage points
    assert var_df["mix_shift_pp"].sum() == pytest.approx(0.0)
    assert var_df.loc[var_df["label"] == "C (new)", "presence_status"].iloc[0] == "Mới phát sinh kỳ này"


# ---------------------------------------------------------------------------
# 2. SQL Builders, Order Count Ban, Filter Scope Preservation & Reset
# ---------------------------------------------------------------------------

def test_no_query_exposes_non_additive_order_count() -> None:
    f = queries.FilterState(dataset_track="ONYX_EU_SYNTHETIC")
    d0, d1 = dt.date(2024, 1, 1), dt.date(2024, 2, 29)
    built_sqls = [
        queries.build_where_clause(f)[0],
        queries.sql_release_state("quick_gold_md01")[0],
        queries.sql_filter_options("quick_gold_md01", "ONYX_EU_SYNTHETIC", ("DE",))[0],
        queries.sql_available_tracks("quick_gold_md01")[0],
        queries.sql_exec_kpis("quick_gold_md01", f)[0],
        queries.sql_uom_breakdown("quick_gold_md01", f)[0],
        queries.sql_monthly_sales_trend("quick_gold_md01", f)[0],
        queries.sql_series_avg_growth_reference("quick_gold_md01", f)[0],
        queries.sql_dimension_variance("quick_gold_md01", f, dim_kind="country", cur_start=d0, cur_end=d1, prev_start=d0, prev_end=d1)[0],
        queries.sql_sales_by_country("quick_gold_md01", f)[0],
        queries.sql_top_brands("quick_gold_md01", f)[0],
        queries.sql_track_currency_summary("quick_gold_md01", f)[0],
        queries.sql_weather_kpis("quick_gold_md01", f)[0],
        queries.sql_temp_rain_heatmap("quick_gold_md01", f)[0],
        queries.sql_humidity_weekend("quick_gold_md01", f)[0],
        queries.sql_daily_temp_scatter("quick_gold_md01", f)[0],
        queries.sql_monthly_weather_seasonality("quick_gold_md01", f)[0],
        queries.sql_daily_weather_table("quick_gold_md01", f)[0],
        queries.sql_daily_weather_table("quick_gold_md01", f, by_store_uom=True)[0],
        queries.sql_top_products_by_rain("quick_gold_md01", f)[0],
        queries.sql_weekday_by_rain("quick_gold_md01", f)[0],
        queries.sql_eu_country_summary("quick_gold_md01", f)[0],
        queries.sql_eu_country_month_heatmap("quick_gold_md01", f)[0],
        queries.sql_eu_promo_breakdown("quick_gold_md01", f)[0],
        queries.sql_eu_brand_margin_and_profit("quick_gold_md01", f)[0],
        queries.sql_store_performance_table("quick_gold_md01", f)[0],
        queries.sql_eu_store_matrix("quick_gold_md01", f)[0],
        queries.sql_product_detail_table("quick_gold_md01", f)[0],
        queries.sql_brand_product_treemap("quick_gold_md01", f)[0],
        queries.sql_unit_price_distribution("quick_gold_md01", f)[0],
        queries.sql_atc_summary_meta("quick_gold_md01")[0],
        queries.sql_atc_monthly_trend("quick_gold_md01", f)[0],
        queries.sql_atc_month_heatmap("quick_gold_md01", f)[0],
        queries.sql_irpd_top_manufacturers("quick_gold_md01", f)[0],
        queries.sql_atc_category_ranking("quick_gold_md01", f)[0],
        queries.sql_store_product_mix("quick_gold_md01", f, cur_start=d0, cur_end=d1, prev_start=d0, prev_end=d1)[0],
        queries.sql_time_series_by_grain("quick_gold_md01", f, grain="week")[0],
        queries.sql_time_series_by_grain("quick_gold_md01", f, grain="day", products=("PainLess Throat Spray",))[0],
        queries.sql_store_map_points("quick_gold_md01", f)[0],
    ]
    for sql in built_sqls:
        low = sql.lower()
        assert "order_count" not in low, f"Found order_count in SQL:\n{sql}"
        assert "total_orders" not in low, f"Found total_orders in SQL:\n{sql}"


def test_validate_schema_accepts_valid_and_rejects_injection() -> None:
    assert queries.validate_schema("quick_gold_md01") == "quick_gold_md01"
    for bad in ("", "quick; DROP TABLE x", "bad-schema", "1starts_digit", 'foo"bar'):
        with pytest.raises(ValueError):
            queries.validate_schema(bad)


def test_build_where_clause_preserves_same_track_override_and_drops_cross_track() -> None:
    f = queries.FilterState(
        dataset_track="ONYX_EU_SYNTHETIC",
        countries=("DE", "FR"),
        stores=("Berlin HealthPoint #014",),
        clean_uoms=("ONYX_UNIT",),
        date_start=dt.date(2024, 1, 1),
        date_end=dt.date(2025, 12, 31),
        temp_bands=("2. Cool (10-20C)",),
        rain_regimes=("1. Dry (0 mm)",),
        humidity_bands=("2. Normal (60-80%)",),
        heatmap_temp_band="1. Cold (<10C)",
        heatmap_rain_regime="2. Light (0-5 mm)",
    )
    # Same-track override (e.g. ONYX EU panels while user is already on ONYX EU) MUST preserve filters
    same_sql, same_params = queries.build_where_clause(f, override_track="ONYX_EU_SYNTHETIC")
    assert "country_code = ANY(%s)" in same_sql
    assert "store_name = ANY(%s)" in same_sql
    assert "clean_uom = ANY(%s)" in same_sql
    assert "local_date >= %s" in same_sql
    assert ["DE", "FR"] in same_params

    # Cross-track override (e.g. IRPD Manufacturers while user is on ONYX EU) MUST drop EU countries/stores/dates
    cross_sql, cross_params = queries.build_where_clause(f, override_track="IRPD_ID_OBSERVED")
    assert cross_params == ("IRPD_ID_OBSERVED",)
    assert "country_code = ANY" not in cross_sql
    assert "store_name = ANY" not in cross_sql
    assert "local_date >=" not in cross_sql

    # Ignoring weather cell keeps base grid intact
    hm_sql, _ = queries.build_where_clause(f, ignore_weather_cell=True)
    assert hm_sql.count("temp_band") == 1


def test_weather_and_margin_sql_formulas() -> None:
    f = queries.FilterState(dataset_track="ONYX_EU_SYNTHETIC")
    wk_sql, _ = queries.sql_weather_kpis("quick_gold_md01", f)
    assert "count(distinct (store_id, local_date))" in wk_sql.lower()
    assert "qty_per_store_day" in wk_sql.lower()

    kpi_sql, _ = queries.sql_exec_kpis("quick_gold_md01", f)
    assert "weighted_margin_pct" in kpi_sql.lower()
    assert "weighted_unit_price" in kpi_sql.lower()
    assert "total_line_count" in kpi_sql.lower()

    mfg_sql, mfg_params = queries.sql_irpd_top_manufacturers("quick_gold_md01", f)
    assert "manufacturer_name is not null" in mfg_sql.lower()
    assert mfg_params[0] == "IRPD_ID_OBSERVED"

    f_irpd = queries.FilterState(dataset_track="IRPD_ID_OBSERVED", clean_uoms=("tab",), date_start=dt.date(2024, 1, 1))
    mfg_same_sql, mfg_same_params = queries.sql_irpd_top_manufacturers("quick_gold_md01", f_irpd)
    assert "clean_uom = any(%s)" in mfg_same_sql.lower()
    assert ["tab"] in mfg_same_params

    # Unit price histogram stays bounded
    hs_sql, hs_params = queries.sql_unit_price_distribution("quick_gold_md01", f, bins=24)
    assert "WIDTH_BUCKET" in hs_sql
    assert hs_params[-4:] == (24, 24, 24, 24)


def test_reset_all_filters_clears_global_and_page_local_state(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_state = {
        "f_track": "IRPD_ID_OBSERVED",
        "f_countries": ["ID"],
        "f_city_clusters": ["K24 Jakarta"],
        "f_stores": ["Some Store"],
        "f_uoms": ["tab"],
        "f_temp_bands": ["5. Hot (>=30C)"],
        "f_time_grain": "week",
        "f_display_vnd": True,
        "f_compare_mode": "half_split",
        "f_date_range": (dt.date(2024, 1, 1), dt.date(2024, 6, 30)),
        "p1_selected_products": ["PainLess Throat Spray"],
        "p2_rain_regimes": ["4. Heavy (>20 mm)"],
        "p2_humidity_bands": ["3. High (>80%)"],
        "p2_cell_temp": "5. Hot (>=30C)",
        "p2_cell_rain": "4. Heavy (>20 mm)",
        "p3_store_search": "Berlin",
        "p3_map_mode": "cluster",
        "p4_product_search": "AntiBioX",
        "p4_atc_apply_date": True,
        "p4_compare_mode": "custom",
    }
    monkeypatch.setattr(filter_comp.st, "session_state", fake_state)
    filter_comp.reset_all_filters()

    assert fake_state["f_track"] == config.DEFAULT_TRACK
    assert fake_state["f_countries"] == []
    assert fake_state["f_city_clusters"] == []
    assert fake_state["f_stores"] == []
    assert fake_state["f_uoms"] == []
    assert fake_state["f_temp_bands"] == []
    assert fake_state["f_time_grain"] == "month"
    assert fake_state["f_display_vnd"] is False
    assert "p1_selected_products" not in fake_state
    assert "p2_rain_regimes" not in fake_state
    assert "p2_humidity_bands" not in fake_state
    assert "p2_cell_temp" not in fake_state
    assert "p3_store_search" not in fake_state
    assert "p4_product_search" not in fake_state
    assert "p4_atc_apply_date" not in fake_state


def test_page2_filters_do_not_leak_to_global_filter_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()

    seen_sqls: list[str] = []

    def _side(sql: str, params: tuple = ()) -> pd.DataFrame:
        seen_sqls.append(sql.lower())
        return _mock_query_df(sql, params, track_mode="onyx")

    with patch("db.run_query_df", side_effect=_side):
        at = AppTest.from_file(str(STREAMLIT_DIR / "app.py"), default_timeout=20)
        at.session_state["p2_rain_regimes"] = ["4. Heavy (>20 mm)"]
        at.session_state["p2_humidity_bands"] = ["3. High (>80%)"]
        at.session_state["p2_cell_temp"] = "5. Hot (>=30C)"
        at.session_state["p2_cell_rain"] = "4. Heavy (>20 mm)"
        at.run()
        assert not at.exception
        assert "_active_filters" in at.session_state
        active = at.session_state["_active_filters"]
        assert active.rain_regimes == ()
        assert active.humidity_bands == ()
        assert active.heatmap_temp_band is None
        assert active.heatmap_rain_regime is None
        assert not any("rain_regime = any" in s or "humidity_band = any" in s for s in seen_sqls)


def test_irpd_single_uom_unlocks_quantity_and_unit_price(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()

    def _side_single_tab(sql: str, params: tuple = ()) -> pd.DataFrame:
        df = _mock_query_df(sql, params, track_mode="irpd")
        if "weighted_margin_pct" in sql.lower() and "total_line_count" in sql.lower():
            df = df.copy()
            df["distinct_uoms"] = [["tab"]]
            df["total_sold_qty"] = 3631938.0
            df["weighted_unit_price"] = 1098.72
        return df

    with patch("db.run_query_df", side_effect=_side_single_tab):
        at = AppTest.from_file(str(STREAMLIT_DIR / "pages/01_tong_quan.py"), default_timeout=20)
        at.session_state["f_track"] = "IRPD_ID_OBSERVED"
        at.session_state["f_uoms"] = ["tab"]
        at.run()
        assert not at.exception
        md_all = "\n".join(m.value for m in at.markdown)
        assert "Cần chọn 1 ĐVT" not in md_all
        assert "1,098.72 IDR" in md_all


# ---------------------------------------------------------------------------
# 3. Config Palettes, Localization Maps & Three-State Formatters
# ---------------------------------------------------------------------------

def test_palettes_and_three_state_formatters() -> None:
    assert {"pharmaflow", "aws_quick", "ocean", "warm", "ant", "shadcn", "clean"}.issubset(config.PALETTES.keys())
    for k, pal in config.PALETTES.items():
        assert pal.primary.startswith("#")
        assert len(set(pal.discrete[:4])) == 4, k
        assert pal.font_family
        assert pal.mono_family

    assert "$" not in config.fmt_currency(8_619_407.63, "EUR")
    assert config.fmt_metric_state(0.0, supported=True, has_rows=True) == "0"
    assert config.fmt_metric_state(None, supported=True, has_rows=False) == "Không có dữ liệu"
    assert config.fmt_metric_state(None, supported=False, has_rows=True) == "Nguồn không hỗ trợ"


# ---------------------------------------------------------------------------
# 4. End-to-End Mocked AppTest Across Tracks, Multi-UOM & Empty Results
# ---------------------------------------------------------------------------

import re  # noqa: E402
import numpy as np  # noqa: E402

_EXPECTED_MOCK_COLUMNS: dict[str, tuple[str, ...]] = {
    "release_state": ("product_domain", "release_id", "status", "sync_mode", "synced_at_utc", "table_counts_json"),
    "available_tracks": ("dataset_track", "currency_code", "provenance_class", "row_count"),
    "filter_options": ("min_date", "max_date", "countries", "uoms", "clusters", "stores"),
    "exec_kpis": (
        "total_revenue", "total_sold_qty", "total_line_count", "active_store_days",
        "active_stores", "distinct_uoms", "total_margin", "weighted_margin_pct",
        "row_avg_margin_pct", "weighted_unit_price", "row_avg_unit_price",
        "currency_code", "provenance_class", "rev_rows", "margin_rows", "row_count",
    ),
    "uom_breakdown": ("clean_uom", "mart_rows", "line_count", "active_store_days", "sold_qty", "line_amount", "weighted_unit_price"),
    "monthly_sales_trend": ("year_month", "sold_qty", "line_amount", "margin_amount", "line_count", "active_days", "active_store_days", "first_date", "last_date"),
    "series_avg_growth_ref": ("period_start", "sold_qty", "series_avg_pct_change", "series_pct_rows", "line_count"),
    "dim_variance_country": ("country_code", "nonnull_label_rows", "cur_qty", "prev_qty", "cur_rev", "prev_rev", "cur_mrg", "prev_mrg", "cur_lines", "prev_lines", "cur_store_days", "prev_store_days", "cur_weighted_margin_pct", "prev_weighted_margin_pct"),
    "dim_variance_brand": ("brand_name", "nonnull_label_rows", "cur_qty", "prev_qty", "cur_rev", "prev_rev", "cur_mrg", "prev_mrg", "cur_lines", "prev_lines", "cur_store_days", "prev_store_days", "cur_weighted_margin_pct", "prev_weighted_margin_pct"),
    "dim_variance_store": ("store_code", "store_name", "country_code", "nonnull_label_rows", "cur_qty", "prev_qty", "cur_rev", "prev_rev", "cur_mrg", "prev_mrg", "cur_lines", "prev_lines", "cur_store_days", "prev_store_days", "cur_weighted_margin_pct", "prev_weighted_margin_pct"),
    "dim_variance_product": ("product_name", "clean_uom", "nonnull_label_rows", "cur_qty", "prev_qty", "cur_rev", "prev_rev", "cur_mrg", "prev_mrg", "cur_lines", "prev_lines", "cur_store_days", "prev_store_days", "cur_weighted_margin_pct", "prev_weighted_margin_pct"),
    "sales_by_country": ("country_code", "sold_qty", "line_amount", "line_count", "active_store_days"),
    "top_brands": ("brand_name", "sold_qty", "line_amount", "margin_amount", "line_count"),
    "track_currency_summary": ("dataset_track", "currency_code", "provenance_class", "distinct_uom_count", "min_date", "max_date", "sold_qty", "line_count", "active_store_days", "line_amount", "margin_amount"),
    "weather_kpis": ("active_stores", "active_dates", "span_days", "possible_store_days", "active_store_days", "total_sold_qty", "total_revenue", "total_line_count", "qty_per_store_day", "rev_per_store_day", "avg_qty_per_store", "avg_temp_mean", "avg_apparent_temp_mean", "avg_precip_sum", "avg_humidity_mean", "rainy_store_days", "weather_covered_rows", "row_count"),
    "temp_rain_heatmap": ("temp_band", "rain_regime", "mart_rows", "active_store_days", "active_days", "distinct_stores", "sold_qty", "line_amount", "qty_per_store_day", "rev_per_store_day"),
    "humidity_weekend": ("humidity_band", "is_weekend", "active_store_days", "sold_qty", "line_amount", "qty_per_store_day", "rev_per_store_day"),
    "daily_temp_scatter": ("local_date", "rain_regime", "temp_mean", "active_stores", "sold_qty", "line_amount", "qty_per_store_day", "rev_per_store_day", "line_count"),
    "monthly_weather_seasonality": ("year_month", "active_store_days", "active_days", "sold_qty", "line_amount", "qty_per_store_day", "rev_per_store_day", "avg_temp_mean", "avg_apparent_temp_mean", "avg_precip_sum", "avg_humidity_mean"),
    "daily_weather_table": ("local_date", "store_name", "temp_band", "rain_regime", "humidity_band", "is_weekend", "clean_uom", "active_stores", "sold_qty", "qty_per_store_day", "line_count", "temp_mean", "precip_sum", "humidity_mean", "line_amount"),
    "top_products_by_rain": ("product_name", "rain_regime", "active_store_days", "sold_qty", "line_amount", "total_metric"),
    "weekday_by_rain": ("day_of_week_num", "day_of_week", "rain_regime", "active_store_days", "sold_qty", "line_amount", "qty_per_store_day", "rev_per_store_day"),
    "eu_country_summary": ("country_code", "sold_qty", "line_amount", "margin_amount", "weighted_margin_pct", "store_count", "active_store_days", "lat", "lon"),
    "eu_country_month_heatmap": ("month_num", "country_code", "sold_qty"),
    "eu_promo_breakdown": ("has_promotion", "mart_rows", "line_count", "sold_qty", "promo_sold_qty", "line_amount", "margin_amount", "weighted_margin_pct", "weighted_unit_price", "avg_row_promo_share"),
    "eu_brand_margin": ("brand_name", "line_amount", "margin_amount", "weighted_margin_pct", "row_avg_margin_pct", "sold_qty"),
    "store_perf_table": ("store_code", "store_name", "country_code", "source", "sold_qty", "line_count", "active_store_days", "line_amount", "margin_amount", "weighted_margin_pct", "row_avg_margin_pct"),
    "eu_store_matrix": ("store_code", "store_name", "country_code", "dataset_track", "provenance_class", "currency_code", "line_amount", "margin_amount", "weighted_margin_pct", "row_avg_margin_pct", "sold_qty", "line_count", "active_store_days"),
    "product_detail_table": ("product_name", "clean_uom", "dataset_track", "line_count", "active_store_days", "sold_qty", "line_amount", "weighted_unit_price", "weighted_margin_pct"),
    "brand_product_treemap": ("brand_name", "product_name", "clean_uom", "sold_qty", "line_amount"),
    "unit_price_distribution": ("dataset_track", "bucket_id", "obs_count", "bin_start", "bin_end"),
    "atc_summary_meta": ("min_ym", "max_ym", "countries", "provenance_class", "source", "month_cat_rows"),
    "atc_monthly_trend": ("year_month", "category_code", "category_name", "total_observed_qty"),
    "atc_month_heatmap": ("month_num", "category_code", "category_name", "total_observed_qty"),
    "irpd_top_manufacturers": ("manufacturer_name", "line_amount", "sold_qty", "line_count", "active_store_days"),
    "atc_category_ranking": ("category_code", "category_name", "total_observed_qty", "avg_daily_qty", "observation_count"),
    "store_product_mix": ("product_name", "clean_uom", "brand_name", "sold_qty", "line_amount", "margin_amount", "line_count", "active_store_days", "weighted_margin_pct", "weighted_unit_price", "cur_qty", "prev_qty", "cur_rev", "prev_rev"),
    "time_series_by_grain": ("period_date", "series_name", "clean_uom", "sold_qty", "line_amount", "margin_amount", "line_count", "active_store_days", "avg_temp_mean", "avg_apparent_temp_mean", "avg_precip_sum", "avg_humidity_mean"),
    "store_map_points": ("store_code", "store_name", "city_cluster", "country_code", "dataset_track", "provenance_class", "currency_code", "map_lat", "map_lon", "sold_qty", "line_amount", "margin_amount", "weighted_margin_pct", "line_count", "active_store_days", "avg_temp_mean", "avg_precip_sum"),
}


def _classify_sql(sql: str) -> str:
    """Classify parameterized query SQL by normalized projection/table signatures (format-agnostic)."""
    norm = re.sub(r"\s+", " ", sql.lower()).strip()

    if "sync_release_state" in norm:
        return "release_state"
    if "as row_count" in norm and "group by dataset_track order by" in norm:
        return "available_tracks"
    if "cross join store_list" in norm:
        return "filter_options"
    if "as weighted_margin_pct" in norm and "as total_line_count" in norm:
        return "exec_kpis"
    if "as mart_rows" in norm and "as weighted_unit_price" in norm and "clean_uom" in norm:
        return "uom_breakdown"
    if "as first_date" in norm and "group by year_month" in norm:
        return "monthly_sales_trend"
    if "as series_avg_pct_change" in norm:
        return "series_avg_growth_ref"
    if "as cur_weighted_margin_pct" in norm:
        if "as store_code" in norm and "as store_name" in norm:
            return "dim_variance_store"
        if "as brand_name" in norm:
            return "dim_variance_brand"
        if "as country_code" in norm:
            return "dim_variance_country"
        if "as product_name" in norm and "as clean_uom" in norm:
            return "dim_variance_product"
    if "as weighted_unit_price" in norm and "as cur_qty" in norm and "as cur_weighted_margin_pct" not in norm:
        return "store_product_mix"
    if "as period_date" in norm and "as series_name" in norm:
        return "time_series_by_grain"
    if "as map_lat" in norm and "as city_cluster" in norm:
        return "store_map_points"
    if "as distinct_uom_count" in norm:
        return "track_currency_summary"
    if "as rainy_store_days" in norm:
        return "weather_kpis"
    if "group by temp_band, rain_regime" in norm:
        return "temp_rain_heatmap"
    if "group by humidity_band, is_weekend" in norm:
        return "humidity_weekend"
    if "as temp_mean" in norm and "group by f.local_date, f.rain_regime" in norm:
        return "daily_temp_scatter"
    if "as avg_apparent_temp_mean" in norm and "w_month" in norm:
        return "monthly_weather_seasonality"
    if "as precip_sum" in norm and ("day_w as" in norm or "group by local_date, store_name" in norm):
        return "daily_weather_table"
    if "with top_products as" in norm:
        return "top_products_by_rain"
    if "group by day_of_week_num, day_of_week, rain_regime" in norm:
        return "weekday_by_rain"
    if "avg(latitude)" in norm:
        return "eu_country_summary"
    if "group by month_num, country_code" in norm:
        return "eu_country_month_heatmap"
    if "as promo_sold_qty" in norm:
        return "eu_promo_breakdown"
    if "as row_avg_margin_pct" in norm and "as source" not in norm and "as dataset_track" in norm:
        return "eu_store_matrix"
    if "as row_avg_margin_pct" in norm and "group by store_code, store_name, country_code, source" in norm:
        return "store_perf_table"
    if "group by brand_name" in norm and "as row_avg_margin_pct" in norm:
        return "eu_brand_margin"
    if "group by brand_name" in norm and "as line_count" in norm and "product_name" not in norm:
        return "top_brands"
    if "group by country_code" in norm and "as active_store_days" in norm and "avg(latitude)" not in norm:
        return "sales_by_country"
    if "group by product_name, clean_uom, dataset_track" in norm:
        return "product_detail_table"
    if "group by brand_name, product_name, clean_uom" in norm:
        return "brand_product_treemap"
    if "width_bucket" in norm:
        return "unit_price_distribution"
    if "as month_cat_rows" in norm:
        return "atc_summary_meta"
    if "group by year_month, category_code, category_name" in norm:
        return "atc_monthly_trend"
    if "group by month_num, category_code, category_name" in norm:
        return "atc_month_heatmap"
    if "group by manufacturer_name" in norm:
        return "irpd_top_manufacturers"
    if "group by category_code, category_name" in norm:
        return "atc_category_ranking"
    raise AssertionError(f"Unclassified SQL pattern: {sql}")


def _mock_query_df(sql: str, params: tuple = (), *, track_mode: str = "onyx") -> pd.DataFrame:
    kind = _classify_sql(sql)

    def _finish(df: pd.DataFrame) -> pd.DataFrame:
        expected = _EXPECTED_MOCK_COLUMNS.get(kind)
        if expected and not df.empty:
            missing = set(expected) - set(df.columns)
            assert not missing, f"Mock schema mismatch for {kind}: missing {missing}"
        return df

    if kind == "release_state":
        return _finish(pd.DataFrame(
            [{
                "product_domain": "MD01_SALES_AND_DEMAND",
                "release_id": "md01-test-release",
                "status": "SUCCEEDED",
                "sync_mode": "databricks_jdbc",
                "synced_at_utc": dt.datetime(2026, 11, 17, 12, 33, tzinfo=dt.timezone.utc),
                "table_counts_json": "{}",
            }]
        ))
    if kind == "available_tracks":
        rows = [
            {"dataset_track": "ONYX_EU_SYNTHETIC", "currency_code": "EUR", "provenance_class": "SYNTHETIC", "row_count": 62036},
            {"dataset_track": "IRPD_ID_OBSERVED", "currency_code": "IDR", "provenance_class": "OBSERVED", "row_count": 387021},
            {"dataset_track": "SERBIA_RS_SYNTHETIC", "currency_code": None, "provenance_class": "SYNTHETIC", "row_count": 25534},
        ]
        if track_mode == "irpd":
            rows = [rows[1], rows[0], rows[2]]
        elif track_mode == "serbia":
            rows = [rows[2], rows[0], rows[1]]
        return _finish(pd.DataFrame(rows))
    if kind == "filter_options":
        if track_mode == "irpd":
            return _finish(pd.DataFrame(
                [{
                    "min_date": dt.date(2023, 1, 2),
                    "max_date": dt.date(2025, 12, 31),
                    "countries": ["ID"],
                    "uoms": ["tab", "pcs", "fls"],
                    "clusters": ["K24 Jakarta"],
                    "stores": ["K24 Jakarta"],
                }]
            ))
        if track_mode == "serbia":
            return _finish(pd.DataFrame(
                [{
                    "min_date": dt.date(2014, 1, 2),
                    "max_date": dt.date(2019, 10, 8),
                    "countries": ["RS"],
                    "uoms": ["ATC_DEFINED_DAILY_DOSE_X10"],
                    "clusters": ["Belgrade Central Pharmacy"],
                    "stores": ["Belgrade Central Pharmacy"],
                }]
            ))
        return _finish(pd.DataFrame(
            [{
                "min_date": dt.date(2024, 1, 1),
                "max_date": dt.date(2025, 12, 31),
                "countries": ["DE", "FR", "IT"],
                "uoms": ["ONYX_UNIT"],
                "clusters": ["Berlin", "Paris"],
                "stores": ["Berlin HealthPoint #014", "Paris HealthPoint #013"],
            }]
        ))
    if kind == "exec_kpis":
        if track_mode == "irpd":
            return _finish(pd.DataFrame(
                [{
                    "total_revenue": 12_599_183_524.0,
                    "total_sold_qty": 4_638_081.3,
                    "total_line_count": 627389,
                    "active_store_days": 1088,
                    "active_stores": 1,
                    "distinct_uoms": ["tab", "pcs", "fls"],
                    "total_margin": None,
                    "weighted_margin_pct": None,
                    "row_avg_margin_pct": None,
                    "weighted_unit_price": 2716.46,
                    "row_avg_unit_price": 14596.71,
                    "currency_code": "IDR",
                    "provenance_class": "OBSERVED",
                    "rev_rows": 387021,
                    "margin_rows": 0,
                    "row_count": 387021,
                }]
            ))
        if track_mode == "serbia":
            return _finish(pd.DataFrame(
                [{
                    "total_revenue": None,
                    "total_sold_qty": 1_275_900.0,
                    "total_line_count": 25534,
                    "active_store_days": 2080,
                    "active_stores": 1,
                    "distinct_uoms": ["ATC_DEFINED_DAILY_DOSE_X10"],
                    "total_margin": None,
                    "weighted_margin_pct": None,
                    "row_avg_margin_pct": None,
                    "weighted_unit_price": None,
                    "row_avg_unit_price": None,
                    "currency_code": None,
                    "provenance_class": "SYNTHETIC",
                    "rev_rows": 0,
                    "margin_rows": 0,
                    "row_count": 25534,
                }]
            ))
        return _finish(pd.DataFrame(
            [{
                "total_revenue": 8_619_407.63,
                "total_sold_qty": 445_078.0,
                "total_line_count": 62036,
                "active_store_days": 42666,
                "active_stores": 120,
                "distinct_uoms": ["ONYX_UNIT"],
                "total_margin": 2_416_838.58,
                "weighted_margin_pct": 0.280395,
                "row_avg_margin_pct": 0.287429,
                "weighted_unit_price": 19.37,
                "row_avg_unit_price": 24.96,
                "currency_code": "EUR",
                "provenance_class": "SYNTHETIC",
                "rev_rows": 62036,
                "margin_rows": 62036,
                "row_count": 62036,
            }]
        ))
    if kind == "uom_breakdown":
        return _finish(pd.DataFrame(
            [
                {"clean_uom": "tab", "mart_rows": 135127, "line_count": 220000, "active_store_days": 1088, "sold_qty": 3631938.0, "line_amount": 3990501292.0, "weighted_unit_price": 1098.72},
                {"clean_uom": "pcs", "mart_rows": 91627, "line_count": 150000, "active_store_days": 1088, "sold_qty": 400927.0, "line_amount": 3120294962.0, "weighted_unit_price": 7782.70},
            ]
        ))
    if kind == "monthly_sales_trend":
        if track_mode == "serbia":
            return _finish(pd.DataFrame(
                [
                    {"year_month": dt.date(2019, 8, 1), "sold_qty": 19000.0, "line_amount": None, "margin_amount": None, "line_count": 400, "active_days": 31, "active_store_days": 31, "first_date": dt.date(2019, 8, 1), "last_date": dt.date(2019, 8, 31)},
                    {"year_month": dt.date(2019, 9, 1), "sold_qty": 18200.0, "line_amount": None, "margin_amount": None, "line_count": 390, "active_days": 30, "active_store_days": 30, "first_date": dt.date(2019, 9, 1), "last_date": dt.date(2019, 9, 30)},
                    {"year_month": dt.date(2019, 10, 1), "sold_qty": 4800.0, "line_amount": None, "margin_amount": None, "line_count": 90, "active_days": 8, "active_store_days": 8, "first_date": dt.date(2019, 10, 1), "last_date": dt.date(2019, 10, 8)},
                ]
            ))
        return _finish(pd.DataFrame(
            [
                {"year_month": dt.date(2024, 1, 1), "sold_qty": 18785.0, "line_amount": 360000.0, "margin_amount": 100000.0 if track_mode == "onyx" else None, "line_count": 2457, "active_days": 31, "active_store_days": 1700, "first_date": dt.date(2024, 1, 1), "last_date": dt.date(2024, 1, 31)},
                {"year_month": dt.date(2024, 2, 1), "sold_qty": 17740.0, "line_amount": 342000.0, "margin_amount": 95000.0 if track_mode == "onyx" else None, "line_count": 2236, "active_days": 29, "active_store_days": 1580, "first_date": dt.date(2024, 2, 1), "last_date": dt.date(2024, 2, 29)},
            ]
        ))
    if kind == "series_avg_growth_ref":
        return _finish(pd.DataFrame(
            [
                {"period_start": dt.date(2024, 1, 1), "sold_qty": 18785.0, "series_avg_pct_change": None, "series_pct_rows": 0, "line_count": 2457},
                {"period_start": dt.date(2024, 2, 1), "sold_qty": 17740.0, "series_avg_pct_change": 0.6443, "series_pct_rows": 281, "line_count": 2236},
            ]
        ))
    m_val = 28.0 if track_mode == "onyx" else None
    r_cur = 100000.0 if track_mode != "serbia" else None
    r_prev = 95000.0 if track_mode != "serbia" else None
    if kind == "dim_variance_country":
        return _finish(pd.DataFrame(
            [
                {"country_code": "DE", "nonnull_label_rows": 950, "cur_qty": 5000.0, "prev_qty": 4500.0, "cur_rev": r_cur, "prev_rev": r_prev, "cur_mrg": 28000.0, "prev_mrg": 26000.0, "cur_lines": 500, "prev_lines": 450, "cur_store_days": 200, "prev_store_days": 190, "cur_weighted_margin_pct": m_val, "prev_weighted_margin_pct": m_val},
                {"country_code": "FR", "nonnull_label_rows": 830, "cur_qty": 4000.0, "prev_qty": 4300.0, "cur_rev": 80000.0 if track_mode != "serbia" else None, "prev_rev": 86000.0 if track_mode != "serbia" else None, "cur_mrg": 22000.0, "prev_mrg": 24000.0, "cur_lines": 400, "prev_lines": 430, "cur_store_days": 180, "prev_store_days": 185, "cur_weighted_margin_pct": m_val, "prev_weighted_margin_pct": m_val},
            ]
        ))
    if kind == "dim_variance_brand":
        nonnull = 0 if track_mode == "irpd" else 600
        return _finish(pd.DataFrame(
            [
                {"brand_name": "Chưa xác định" if track_mode == "irpd" else "PainLess", "nonnull_label_rows": nonnull, "cur_qty": 3000.0, "prev_qty": 2700.0, "cur_rev": r_cur, "prev_rev": r_prev, "cur_mrg": 18000.0, "prev_mrg": 16000.0, "cur_lines": 300, "prev_lines": 270, "cur_store_days": 120, "prev_store_days": 115, "cur_weighted_margin_pct": m_val, "prev_weighted_margin_pct": m_val},
            ]
        ))
    if kind == "dim_variance_store":
        return _finish(pd.DataFrame(
            [
                {"store_code": "ONYX:PH0014", "store_name": "Berlin HealthPoint #014", "country_code": "DE", "nonnull_label_rows": 170, "cur_qty": 450.0, "prev_qty": 400.0, "cur_rev": r_cur, "prev_rev": r_prev, "cur_mrg": 25000.0, "prev_mrg": 24000.0, "cur_lines": 90, "prev_lines": 80, "cur_store_days": 25, "prev_store_days": 24, "cur_weighted_margin_pct": m_val, "prev_weighted_margin_pct": 29.0 if track_mode == "onyx" else None},
                {"store_code": "ONYX:PH0120", "store_name": "Naples HealthPoint #120", "country_code": "IT", "nonnull_label_rows": 155, "cur_qty": 320.0, "prev_qty": 420.0, "cur_rev": 75000.0 if track_mode != "serbia" else None, "prev_rev": 95000.0 if track_mode != "serbia" else None, "cur_mrg": 20000.0, "prev_mrg": 25000.0, "cur_lines": 70, "prev_lines": 85, "cur_store_days": 22, "prev_store_days": 25, "cur_weighted_margin_pct": 25.0 if track_mode == "onyx" else None, "prev_weighted_margin_pct": 27.0 if track_mode == "onyx" else None},
            ]
        ))
    if kind == "dim_variance_product":
        return _finish(pd.DataFrame(
            [
                {"product_name": "PainLess Throat Spray", "clean_uom": "ONYX_UNIT", "nonnull_label_rows": 290, "cur_qty": 900.0, "prev_qty": 800.0, "cur_rev": r_cur, "prev_rev": r_prev, "cur_mrg": 25000.0, "prev_mrg": 22000.0, "cur_lines": 150, "prev_lines": 140, "cur_store_days": 80, "prev_store_days": 75, "cur_weighted_margin_pct": m_val, "prev_weighted_margin_pct": m_val},
                {"product_name": "AntiBioX 10 mg", "clean_uom": "ONYX_UNIT", "nonnull_label_rows": 235, "cur_qty": 650.0, "prev_qty": 750.0, "cur_rev": 65000.0 if track_mode != "serbia" else None, "prev_rev": 78000.0 if track_mode != "serbia" else None, "cur_mrg": 18000.0, "prev_mrg": 21000.0, "cur_lines": 110, "prev_lines": 125, "cur_store_days": 65, "prev_store_days": 70, "cur_weighted_margin_pct": m_val, "prev_weighted_margin_pct": m_val},
            ]
        ))
    if kind == "sales_by_country":
        return _finish(pd.DataFrame(
            [
                {"country_code": "DE", "sold_qty": 75000.0, "line_amount": 1500000.0 if track_mode != "serbia" else None, "line_count": 10000, "active_store_days": 6000},
                {"country_code": "FR", "sold_qty": 71000.0, "line_amount": 1400000.0 if track_mode != "serbia" else None, "line_count": 9500, "active_store_days": 5800},
            ]
        ))
    if kind == "top_brands":
        return _finish(pd.DataFrame(
            [
                {"brand_name": "PainLess", "sold_qty": 34000.0, "line_amount": 700000.0, "margin_amount": 190000.0, "line_count": 4800},
                {"brand_name": "Medica", "sold_qty": 33000.0, "line_amount": 680000.0, "margin_amount": 185000.0, "line_count": 4600},
            ]
        ))
    if kind == "track_currency_summary":
        return _finish(pd.DataFrame(
            [
                {"dataset_track": "ONYX_EU_SYNTHETIC", "currency_code": "EUR", "provenance_class": "SYNTHETIC", "distinct_uom_count": 1, "min_date": dt.date(2024, 1, 1), "max_date": dt.date(2025, 12, 31), "sold_qty": 445078.0, "line_count": 62036, "active_store_days": 42666, "line_amount": 8619407.63, "margin_amount": 2416838.58},
                {"dataset_track": "IRPD_ID_OBSERVED", "currency_code": "IDR", "provenance_class": "OBSERVED", "distinct_uom_count": 20, "min_date": dt.date(2023, 1, 2), "max_date": dt.date(2025, 12, 31), "sold_qty": 4638081.3, "line_count": 627389, "active_store_days": 1088, "line_amount": 12599183524.0, "margin_amount": None},
            ]
        ))
    if kind == "weather_kpis":
        return _finish(pd.DataFrame(
            [{
                "active_stores": 120 if track_mode == "onyx" else 1,
                "active_dates": 731,
                "span_days": 731,
                "possible_store_days": 87720 if track_mode == "onyx" else 731,
                "active_store_days": 42666 if track_mode == "onyx" else 731,
                "total_sold_qty": 445078.0,
                "total_revenue": 8619407.63 if track_mode != "serbia" else None,
                "total_line_count": 62036,
                "qty_per_store_day": 10.43,
                "rev_per_store_day": 202.02 if track_mode != "serbia" else None,
                "avg_qty_per_store": 3708.98,
                "avg_temp_mean": 13.47,
                "avg_apparent_temp_mean": 12.10,
                "avg_precip_sum": 2.45,
                "avg_humidity_mean": 73.2,
                "rainy_store_days": 19500 if track_mode == "onyx" else 310,
                "weather_covered_rows": 62036,
                "row_count": 62036,
            }]
        ))
    if kind == "temp_rain_heatmap":
        return _finish(pd.DataFrame(
            [
                {"temp_band": "1. Cold (<10C)", "rain_regime": "1. Dry (0 mm)", "mart_rows": 10195, "active_store_days": 6976, "active_days": 375, "distinct_stores": 119, "sold_qty": 73959.0, "line_amount": 1400000.0, "qty_per_store_day": 10.60, "rev_per_store_day": 200.69},
                {"temp_band": "2. Cool (10-20C)", "rain_regime": "2. Light (0-5 mm)", "mart_rows": 11999, "active_store_days": 8244, "active_days": 641, "distinct_stores": 119, "sold_qty": 85882.0, "line_amount": 1650000.0, "qty_per_store_day": 10.42, "rev_per_store_day": 200.15},
                {"temp_band": "4. Warm (27-30C)", "rain_regime": "4. Heavy (>20 mm)", "mart_rows": 6, "active_store_days": 2, "active_days": 1, "distinct_stores": 2, "sold_qty": 48.0, "line_amount": 900.0, "qty_per_store_day": 24.0, "rev_per_store_day": 450.0},
            ]
        ))
    if kind == "humidity_weekend":
        return _finish(pd.DataFrame(
            [
                {"humidity_band": "2. Normal (60-80%)", "is_weekend": False, "active_store_days": 16099, "sold_qty": 171235.0, "line_amount": 3200000.0, "qty_per_store_day": 10.64, "rev_per_store_day": 198.77},
                {"humidity_band": "2. Normal (60-80%)", "is_weekend": True, "active_store_days": 5733, "sold_qty": 57058.0, "line_amount": 1080000.0, "qty_per_store_day": 9.95, "rev_per_store_day": 188.38},
            ]
        ))
    if kind == "daily_temp_scatter":
        return _finish(pd.DataFrame(
            [{"local_date": dt.date(2024, 5, 1), "rain_regime": "1. Dry (0 mm)", "temp_mean": 16.5, "active_stores": 60, "sold_qty": 620.0, "line_amount": 12000.0, "qty_per_store_day": 10.33, "rev_per_store_day": 200.0, "line_count": 90}]
        ))
    if kind == "monthly_weather_seasonality":
        return _finish(pd.DataFrame(
            [{"year_month": dt.date(2024, 5, 1), "active_store_days": 1800, "active_days": 31, "sold_qty": 18500.0, "line_amount": 350000.0, "qty_per_store_day": 10.28, "rev_per_store_day": 194.44, "avg_temp_mean": 16.2, "avg_apparent_temp_mean": 15.8, "avg_precip_sum": 1.9, "avg_humidity_mean": 68.4}]
        ))
    if kind == "daily_weather_table":
        return _finish(pd.DataFrame(
            [{
                "local_date": dt.date(2024, 12, 19),
                "store_name": "Berlin HealthPoint #014",
                "temp_band": "1. Cold (<10C)",
                "rain_regime": "2. Light (0-5 mm)",
                "humidity_band": "2. Normal (60-80%)",
                "is_weekend": False,
                "clean_uom": "ONYX_UNIT",
                "active_stores": 65,
                "sold_qty": 783.0,
                "qty_per_store_day": 12.05,
                "line_count": 92,
                "temp_mean": 9.16,
                "precip_sum": 6.43,
                "humidity_mean": 76.17,
                "line_amount": 12949.83 if track_mode != "serbia" else None,
            }]
        ))
    if kind == "top_products_by_rain":
        return _finish(pd.DataFrame(
            [
                {"product_name": "PainLess Throat Spray", "rain_regime": "1. Dry (0 mm)", "active_store_days": 220, "sold_qty": 3200.0, "line_amount": 60000.0, "total_metric": 6800.0},
                {"product_name": "PainLess Throat Spray", "rain_regime": "2. Light (0-5 mm)", "active_store_days": 190, "sold_qty": 2600.0, "line_amount": 49000.0, "total_metric": 6800.0},
            ]
        ))
    if kind == "weekday_by_rain":
        return _finish(pd.DataFrame(
            [
                {"day_of_week_num": 1, "day_of_week": "Mon", "rain_regime": "1. Dry (0 mm)", "active_store_days": 3100, "sold_qty": 33000.0, "line_amount": 630000.0, "qty_per_store_day": 10.65, "rev_per_store_day": 203.2},
                {"day_of_week_num": 7, "day_of_week": "Sun", "rain_regime": "1. Dry (0 mm)", "active_store_days": 2500, "sold_qty": 25000.0, "line_amount": 480000.0, "qty_per_store_day": 10.0, "rev_per_store_day": 192.0},
            ]
        ))
    if kind == "eu_country_summary":
        return _finish(pd.DataFrame(
            [
                {"country_code": "DE", "sold_qty": 75000.0, "line_amount": 1500000.0, "margin_amount": 420000.0, "weighted_margin_pct": 28.0, "store_count": 18, "active_store_days": 6500, "lat": 51.1, "lon": 10.4},
                {"country_code": "FR", "sold_qty": 71000.0, "line_amount": 1400000.0, "margin_amount": 395000.0, "weighted_margin_pct": 28.21, "store_count": 16, "active_store_days": 6200, "lat": 46.2, "lon": 2.2},
            ]
        ))
    if kind == "eu_country_month_heatmap":
        return _finish(pd.DataFrame(
            [{"month_num": 1, "country_code": "DE", "sold_qty": 6527.0}, {"month_num": 1, "country_code": "FR", "sold_qty": 6331.0}]
        ))
    if kind == "eu_promo_breakdown":
        return _finish(pd.DataFrame(
            [
                {"has_promotion": True, "mart_rows": 7419, "line_count": 7419, "sold_qty": 52107.0, "promo_sold_qty": 52107.0, "line_amount": 909973.33, "margin_amount": 181275.75, "weighted_margin_pct": 19.92, "weighted_unit_price": 17.46, "avg_row_promo_share": 1.0},
                {"has_promotion": False, "mart_rows": 54617, "line_count": 54617, "sold_qty": 392971.0, "promo_sold_qty": 0.0, "line_amount": 7709434.30, "margin_amount": 2235562.83, "weighted_margin_pct": 29.00, "weighted_unit_price": 19.62, "avg_row_promo_share": 0.0},
            ]
        ))
    if kind == "eu_brand_margin":
        return _finish(pd.DataFrame(
            [{"brand_name": "PainLess", "line_amount": 700000.0, "margin_amount": 200000.0, "weighted_margin_pct": 28.57, "row_avg_margin_pct": 28.9, "sold_qty": 34000.0}]
        ))
    if kind == "store_perf_table":
        return _finish(pd.DataFrame(
            [{"store_code": "ONYX:PH0120", "store_name": "Naples HealthPoint #120", "country_code": "IT", "source": "SIMULATED_ONYX_DAILY_FACT_TO_POS", "sold_qty": 4592.0, "line_count": 659, "active_store_days": 659, "line_amount": 83794.15 if track_mode != "serbia" else None, "margin_amount": 23557.29 if track_mode == "onyx" else None, "weighted_margin_pct": 28.11 if track_mode == "onyx" else None, "row_avg_margin_pct": 28.11 if track_mode == "onyx" else None}]
        ))
    if kind == "eu_store_matrix":
        return _finish(pd.DataFrame(
            [
                {"store_code": "ONYX:PH0120", "store_name": "Naples HealthPoint #120", "country_code": "IT", "dataset_track": "ONYX_EU_SYNTHETIC", "provenance_class": "SYNTHETIC", "currency_code": "EUR", "line_amount": 83794.15, "margin_amount": 23557.29, "weighted_margin_pct": 28.11, "row_avg_margin_pct": 28.11, "sold_qty": 4592.0, "line_count": 659, "active_store_days": 659},
                {"store_code": "ONYX:PH0014", "store_name": "Berlin HealthPoint #014", "country_code": "DE", "dataset_track": "ONYX_EU_SYNTHETIC", "provenance_class": "SYNTHETIC", "currency_code": "EUR", "line_amount": 95100.00, "margin_amount": 27674.10, "weighted_margin_pct": 29.10, "row_avg_margin_pct": 29.10, "sold_qty": 5100.0, "line_count": 720, "active_store_days": 720},
            ]
        ))
    if kind == "product_detail_table":
        return _finish(pd.DataFrame(
            [{"product_name": "AntiBioX Antibiotic 10 mg", "clean_uom": "ONYX_UNIT", "dataset_track": "ONYX_EU_SYNTHETIC", "line_count": 300, "active_store_days": 280, "sold_qty": 1336.0, "line_amount": 65720.97 if track_mode != "serbia" else None, "weighted_unit_price": 49.19 if track_mode != "serbia" else None, "weighted_margin_pct": 23.33 if track_mode == "onyx" else None}]
        ))
    if kind == "brand_product_treemap":
        return _finish(pd.DataFrame(
            [{"brand_name": "PainLess", "product_name": "PainLess Throat Spray", "clean_uom": "ONYX_UNIT", "sold_qty": 6800.0, "line_amount": 120000.0}]
        ))
    if kind == "unit_price_distribution":
        return _finish(pd.DataFrame(
            [{"dataset_track": "ONYX_EU_SYNTHETIC", "bucket_id": 1, "obs_count": 5635, "bin_start": 1.33, "bin_end": 6.27}]
        ))
    if kind == "atc_summary_meta":
        return _finish(pd.DataFrame(
            [{"min_ym": dt.date(2014, 1, 1), "max_ym": dt.date(2019, 10, 1), "countries": "RS", "provenance_class": "OBSERVED", "source": "PHARMA_SALES_DAILY_ATC", "month_cat_rows": 560}]
        ))
    if kind == "atc_monthly_trend":
        return _finish(pd.DataFrame(
            [{"year_month": dt.date(2014, 1, 1), "category_code": "N02BE", "category_name": "Anilides", "total_observed_qty": 950.0}]
        ))
    if kind == "atc_month_heatmap":
        return _finish(pd.DataFrame(
            [{"month_num": 1, "category_code": "N02BE", "category_name": "Anilides", "total_observed_qty": 7632.89}]
        ))
    if kind == "irpd_top_manufacturers":
        return _finish(pd.DataFrame(
            [{"manufacturer_name": "Zenith", "line_amount": 817422019.0, "sold_qty": 469644.0, "line_count": 46214, "active_store_days": 1050}]
        ))
    if kind == "atc_category_ranking":
        return _finish(pd.DataFrame(
            [{"category_code": "N02BE", "category_name": "Anilides", "total_observed_qty": 63005.4, "avg_daily_qty": 30.01, "observation_count": 2106}]
        ))
    if kind == "store_product_mix":
        uom = "tab" if track_mode == "irpd" else ("ATC_DEFINED_DAILY_DOSE_X10" if track_mode == "serbia" else "ONYX_UNIT")
        has_rev = track_mode != "serbia"
        has_mrg = track_mode == "onyx"
        return _finish(pd.DataFrame(
            [
                {
                    "product_name": "PainLess Throat Spray",
                    "clean_uom": uom,
                    "brand_name": "PainLess" if track_mode == "onyx" else "Chưa xác định",
                    "sold_qty": 12000.0,
                    "line_amount": 240000.0 if has_rev else None,
                    "margin_amount": 69600.0 if has_mrg else None,
                    "line_count": 1500,
                    "active_store_days": 520,
                    "weighted_margin_pct": 29.0 if has_mrg else None,
                    "weighted_unit_price": 20.0 if has_rev else None,
                    "cur_qty": 1100.0,
                    "prev_qty": 1000.0,
                    "cur_rev": 22000.0 if has_rev else None,
                    "prev_rev": 20000.0 if has_rev else None,
                },
                {
                    "product_name": "AntiBioX 10 mg",
                    "clean_uom": uom,
                    "brand_name": "Medica" if track_mode == "onyx" else "Chưa xác định",
                    "sold_qty": 9500.0,
                    "line_amount": 180000.0 if has_rev else None,
                    "margin_amount": 48600.0 if has_mrg else None,
                    "line_count": 1200,
                    "active_store_days": 460,
                    "weighted_margin_pct": 27.0 if has_mrg else None,
                    "weighted_unit_price": 18.95 if has_rev else None,
                    "cur_qty": 820.0,
                    "prev_qty": 900.0,
                    "cur_rev": 15500.0 if has_rev else None,
                    "prev_rev": 17000.0 if has_rev else None,
                },
            ]
        ))
    if kind == "time_series_by_grain":
        uom = "tab" if track_mode == "irpd" else ("ATC_DEFINED_DAILY_DOSE_X10" if track_mode == "serbia" else "ONYX_UNIT")
        has_rev = track_mode != "serbia"
        has_mrg = track_mode == "onyx"
        is_multi_prod = "trim(product_name)" in sql.lower()
        rows = [
            {
                "period_date": dt.date(2024, 1, 1),
                "series_name": "PainLess Throat Spray" if is_multi_prod else "Toàn bộ danh mục",
                "clean_uom": uom,
                "sold_qty": 9000.0,
                "line_amount": 180000.0 if has_rev else None,
                "margin_amount": 50400.0 if has_mrg else None,
                "line_count": 1100,
                "active_store_days": 420,
                "avg_temp_mean": 8.5,
                "avg_apparent_temp_mean": 7.1,
                "avg_precip_sum": 2.4,
                "avg_humidity_mean": 76.0,
            },
            {
                "period_date": dt.date(2024, 2, 1),
                "series_name": "PainLess Throat Spray" if is_multi_prod else "Toàn bộ danh mục",
                "clean_uom": uom,
                "sold_qty": 9600.0,
                "line_amount": 192000.0 if has_rev else None,
                "margin_amount": 53760.0 if has_mrg else None,
                "line_count": 1150,
                "active_store_days": 435,
                "avg_temp_mean": 10.2,
                "avg_apparent_temp_mean": 9.0,
                "avg_precip_sum": 1.8,
                "avg_humidity_mean": 72.5,
            },
        ]
        if is_multi_prod:
            rows.append(
                {
                    "period_date": dt.date(2024, 1, 1),
                    "series_name": "AntiBioX 10 mg",
                    "clean_uom": uom,
                    "sold_qty": 5400.0,
                    "line_amount": 102000.0 if has_rev else None,
                    "margin_amount": 27540.0 if has_mrg else None,
                    "line_count": 680,
                    "active_store_days": 300,
                    "avg_temp_mean": 8.5,
                    "avg_apparent_temp_mean": 7.1,
                    "avg_precip_sum": 2.4,
                    "avg_humidity_mean": 76.0,
                }
            )
        return _finish(pd.DataFrame(rows))
    if kind == "store_map_points":
        if track_mode == "irpd":
            return _finish(pd.DataFrame(
                [{
                    "store_code": "IRPD:ID_JAVA",
                    "store_name": "Apotek Simulasi IRPD - Jawa Tengah",
                    "city_cluster": "Apotek Simulasi IRPD - Jawa Tengah",
                    "country_code": "ID",
                    "dataset_track": "IRPD_ID_OBSERVED",
                    "provenance_class": "OBSERVED",
                    "currency_code": "IDR",
                    "map_lat": -7.15,
                    "map_lon": 110.14,
                    "sold_qty": 4638081.0,
                    "line_amount": 12599183524.0,
                    "margin_amount": None,
                    "weighted_margin_pct": None,
                    "line_count": 627389,
                    "active_store_days": 1088,
                    "avg_temp_mean": 27.4,
                    "avg_precip_sum": 5.2,
                }]
            ))
        if track_mode == "serbia":
            return _finish(pd.DataFrame(
                [{
                    "store_code": "RS:01",
                    "store_name": "Belgrade Central Pharmacy",
                    "city_cluster": "Belgrade Central Pharmacy",
                    "country_code": "RS",
                    "dataset_track": "SERBIA_RS_SYNTHETIC",
                    "provenance_class": "SYNTHETIC",
                    "currency_code": None,
                    "map_lat": 44.82,
                    "map_lon": 20.46,
                    "sold_qty": 1275900.0,
                    "line_amount": None,
                    "margin_amount": None,
                    "weighted_margin_pct": None,
                    "line_count": 25534,
                    "active_store_days": 2080,
                    "avg_temp_mean": 13.1,
                    "avg_precip_sum": 1.9,
                }]
            ))
        return _finish(pd.DataFrame(
            [
                {
                    "store_code": "ONYX:PH0014",
                    "store_name": "Berlin HealthPoint #014",
                    "city_cluster": "Berlin",
                    "country_code": "DE",
                    "dataset_track": "ONYX_EU_SYNTHETIC",
                    "provenance_class": "SYNTHETIC",
                    "currency_code": "EUR",
                    "map_lat": 52.52,
                    "map_lon": 13.405,
                    "sold_qty": 5100.0,
                    "line_amount": 95100.0,
                    "margin_amount": 27674.1,
                    "weighted_margin_pct": 29.10,
                    "line_count": 720,
                    "active_store_days": 720,
                    "avg_temp_mean": 11.4,
                    "avg_precip_sum": 2.1,
                },
                {
                    "store_code": "ONYX:PH0120",
                    "store_name": "Naples HealthPoint #120",
                    "city_cluster": "Naples",
                    "country_code": "IT",
                    "dataset_track": "ONYX_EU_SYNTHETIC",
                    "provenance_class": "SYNTHETIC",
                    "currency_code": "EUR",
                    "map_lat": 40.85,
                    "map_lon": 14.27,
                    "sold_qty": 4592.0,
                    "line_amount": 83794.15,
                    "margin_amount": 23557.29,
                    "weighted_margin_pct": 28.11,
                    "line_count": 659,
                    "active_store_days": 659,
                    "avg_temp_mean": 17.8,
                    "avg_precip_sum": 1.7,
                },
            ]
        ))
    raise AssertionError(f"Unhandled classified query kind: {kind}")


@pytest.mark.parametrize(
    "page_rel",
    [
        "pages/01_tong_quan.py",
        "pages/02_thoi_tiet_dia_diem.py",
        "pages/03_cua_hang_loi_nhuan.py",
        "pages/04_san_pham_atc.py",
    ],
)
@pytest.mark.parametrize("track_mode", ["onyx", "irpd", "serbia"])
def test_pages_render_without_exception_across_all_tracks(
    page_rel: str, track_mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()

    def _side(sql: str, params: tuple = ()) -> pd.DataFrame:
        return _mock_query_df(sql, params, track_mode=track_mode)

    with patch("db.run_query_df", side_effect=_side):
        at = AppTest.from_file(str(STREAMLIT_DIR / page_rel), default_timeout=20)
        at.run()
        assert not at.exception, f"Exception on {page_rel} ({track_mode}): {[e.value for e in at.exception]}"
        assert not at.error, f"Error widget on {page_rel} ({track_mode}): {[e.value for e in at.error]}"


@pytest.mark.parametrize(
    "page_rel",
    [
        "pages/01_tong_quan.py",
        "pages/02_thoi_tiet_dia_diem.py",
        "pages/03_cua_hang_loi_nhuan.py",
        "pages/04_san_pham_atc.py",
    ],
)
def test_pages_handle_empty_query_results_gracefully(page_rel: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()

    def _empty_except_meta(sql: str, params: tuple = ()) -> pd.DataFrame:
        low = sql.lower()
        if any(k in low for k in ("sync_release_state", "group by dataset_track\n", "cross join store_list sl")):
            return _mock_query_df(sql, params, track_mode="onyx")
        return pd.DataFrame()

    with patch("db.run_query_df", side_effect=_empty_except_meta):
        at = AppTest.from_file(str(STREAMLIT_DIR / page_rel), default_timeout=20)
        at.run()
        assert not at.exception, f"Empty DB crash on {page_rel}: {[e.value for e in at.exception]}"


def test_app_navigation_entrypoint_renders_honest_order_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()

    with patch("db.run_query_df", side_effect=_mock_query_df):
        at = AppTest.from_file(str(STREAMLIT_DIR / "app.py"), default_timeout=20)
        at.run()
        assert not at.exception, f"Exception on app.py: {[e.value for e in at.exception]}"
        assert not at.error
        md_all = "\n".join(m.value for m in at.markdown)
        assert "Chưa khả dụng" in md_all
        assert "Tổng Số Đơn Hàng" not in md_all


def test_safe_round_and_polish_horizontal_bar() -> None:
    all_none = pd.Series([None, None], dtype=object)
    rounded = config.safe_round(all_none, 2)
    assert rounded.isna().all()

    df = pd.DataFrame({"name": ["Top1", "Mid2", "Low3"], "val": [34000.0, 20000.0, 5000.0]})
    fig = px.bar(df, x="val", y="name", orientation="h")
    ui.polish_horizontal_bar(fig, ["Top1", "Mid2", "Low3"], 34000.0)
    yaxis = fig.to_dict()["layout"]["yaxis"]
    xaxis = fig.to_dict()["layout"]["xaxis"]
    assert yaxis["categoryorder"] == "array"
    assert yaxis["categoryarray"] == ["Low3", "Mid2", "Top1"]
    assert xaxis["range"][1] > 34000.0

    import plotly.graph_objects as go
    fig_div = go.Figure(go.Bar(x=[-3000.0, 2900.0], y=["Store A", "Store B"], orientation="h", text=["-3,000", "+2,900"]))
    ui.polish_diverging_bar(fig_div, 3000.0)
    assert fig_div.to_dict()["layout"]["xaxis"]["range"] == pytest.approx([-4140.0, 4140.0])
    assert fig_div.to_dict()["data"][0]["textposition"] == "auto"


def test_streamlit_slim_requirements_contains_only_runtime_deps() -> None:
    req_path = STREAMLIT_DIR / "requirements.txt"
    assert req_path.is_file()
    text = req_path.read_text(encoding="utf-8")
    lines = [
        line.strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    for pkg in ("streamlit", "plotly", "pandas", "psycopg[binary]", "python-dotenv"):
        assert any(line.startswith(pkg) for line in lines), f"Missing {pkg} in src/streamlit/requirements.txt"
    for heavy in ("boto3", "databricks-sdk", "pymongo"):
        assert all(heavy not in line for line in lines), f"Unexpected ETL package {heavy} in slim requirements"


def test_db_find_env_files_and_get_settings_supports_streamlit_local_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_app_dir = tmp_path / "repo" / "src" / "streamlit"
    fake_app_dir.mkdir(parents=True)
    local_env = fake_app_dir / ".env"
    local_env.write_text(
        "QUICK_NEON_DATABASE_URL=postgresql://bi_reader:secret@ep-demo-pooler.neon.tech/neondb?sslmode=require\n"
        "QUICK_NEON_SCHEMA=quick_gold_md01\n",
        encoding="utf-8",
    )
    fake_db_file = fake_app_dir / "db.py"
    fake_db_file.write_text("# stub", encoding="utf-8")

    monkeypatch.delenv("QUICK_NEON_DATABASE_URL", raising=False)
    monkeypatch.delenv("QUICK_NEON_SCHEMA", raising=False)
    monkeypatch.setattr(db, "__file__", str(fake_db_file))
    monkeypatch.chdir(tmp_path)
    db.get_db_settings.cache_clear()

    try:
        found = db._find_env_files()
        assert found[0] == local_env.resolve()
        dsn, schema = db.get_db_settings()
        assert dsn.startswith("postgresql://bi_reader:")
        assert schema == "quick_gold_md01"
    finally:
        db.get_db_settings.cache_clear()


# ---------------------------------------------------------------------------
# 5. Regression Suite: Matrix Provenance, Watchlist States, Full Catalog & Safety
# ---------------------------------------------------------------------------

def test_mock_classifier_covers_all_sql_builders() -> None:
    f = queries.FilterState(dataset_track="ONYX_EU_SYNTHETIC")
    d0, d1 = dt.date(2024, 1, 1), dt.date(2024, 2, 29)
    samples = [
        ("release_state", queries.sql_release_state("quick_gold_md01")[0]),
        ("available_tracks", queries.sql_available_tracks("quick_gold_md01")[0]),
        ("filter_options", queries.sql_filter_options("quick_gold_md01", "ONYX_EU_SYNTHETIC", ())[0]),
        ("exec_kpis", queries.sql_exec_kpis("quick_gold_md01", f)[0]),
        ("uom_breakdown", queries.sql_uom_breakdown("quick_gold_md01", f)[0]),
        ("monthly_sales_trend", queries.sql_monthly_sales_trend("quick_gold_md01", f)[0]),
        ("series_avg_growth_ref", queries.sql_series_avg_growth_reference("quick_gold_md01", f)[0]),
        ("dim_variance_country", queries.sql_dimension_variance("quick_gold_md01", f, dim_kind="country", cur_start=d0, cur_end=d1, prev_start=d0, prev_end=d1)[0]),
        ("dim_variance_brand", queries.sql_dimension_variance("quick_gold_md01", f, dim_kind="brand", cur_start=d0, cur_end=d1, prev_start=d0, prev_end=d1)[0]),
        ("dim_variance_store", queries.sql_dimension_variance("quick_gold_md01", f, dim_kind="store", cur_start=d0, cur_end=d1, prev_start=d0, prev_end=d1)[0]),
        ("dim_variance_product", queries.sql_dimension_variance("quick_gold_md01", f, dim_kind="product", cur_start=d0, cur_end=d1, prev_start=d0, prev_end=d1)[0]),
        ("sales_by_country", queries.sql_sales_by_country("quick_gold_md01", f)[0]),
        ("top_brands", queries.sql_top_brands("quick_gold_md01", f)[0]),
        ("track_currency_summary", queries.sql_track_currency_summary("quick_gold_md01", f)[0]),
        ("weather_kpis", queries.sql_weather_kpis("quick_gold_md01", f)[0]),
        ("temp_rain_heatmap", queries.sql_temp_rain_heatmap("quick_gold_md01", f)[0]),
        ("humidity_weekend", queries.sql_humidity_weekend("quick_gold_md01", f)[0]),
        ("daily_temp_scatter", queries.sql_daily_temp_scatter("quick_gold_md01", f)[0]),
        ("monthly_weather_seasonality", queries.sql_monthly_weather_seasonality("quick_gold_md01", f)[0]),
        ("daily_weather_table", queries.sql_daily_weather_table("quick_gold_md01", f, by_store_uom=False)[0]),
        ("daily_weather_table", queries.sql_daily_weather_table("quick_gold_md01", f, by_store_uom=True)[0]),
        ("top_products_by_rain", queries.sql_top_products_by_rain("quick_gold_md01", f)[0]),
        ("weekday_by_rain", queries.sql_weekday_by_rain("quick_gold_md01", f)[0]),
        ("eu_country_summary", queries.sql_eu_country_summary("quick_gold_md01", f)[0]),
        ("eu_country_month_heatmap", queries.sql_eu_country_month_heatmap("quick_gold_md01", f)[0]),
        ("eu_promo_breakdown", queries.sql_eu_promo_breakdown("quick_gold_md01", f)[0]),
        ("eu_brand_margin", queries.sql_eu_brand_margin_and_profit("quick_gold_md01", f)[0]),
        ("store_perf_table", queries.sql_store_performance_table("quick_gold_md01", f)[0]),
        ("eu_store_matrix", queries.sql_eu_store_matrix("quick_gold_md01", f)[0]),
        ("product_detail_table", queries.sql_product_detail_table("quick_gold_md01", f)[0]),
        ("brand_product_treemap", queries.sql_brand_product_treemap("quick_gold_md01", f)[0]),
        ("unit_price_distribution", queries.sql_unit_price_distribution("quick_gold_md01", f)[0]),
        ("atc_summary_meta", queries.sql_atc_summary_meta("quick_gold_md01")[0]),
        ("atc_monthly_trend", queries.sql_atc_monthly_trend("quick_gold_md01", f)[0]),
        ("atc_month_heatmap", queries.sql_atc_month_heatmap("quick_gold_md01", f)[0]),
        ("irpd_top_manufacturers", queries.sql_irpd_top_manufacturers("quick_gold_md01", f)[0]),
        ("atc_category_ranking", queries.sql_atc_category_ranking("quick_gold_md01", f)[0]),
        ("store_product_mix", queries.sql_store_product_mix("quick_gold_md01", f, cur_start=d0, cur_end=d1, prev_start=d0, prev_end=d1)[0]),
        ("time_series_by_grain", queries.sql_time_series_by_grain("quick_gold_md01", f, grain="week")[0]),
        ("time_series_by_grain", queries.sql_time_series_by_grain("quick_gold_md01", f, grain="day", products=("PainLess Throat Spray",))[0]),
        ("store_map_points", queries.sql_store_map_points("quick_gold_md01", f)[0]),
    ]
    for expected_kind, sql in samples:
        assert _classify_sql(sql) == expected_kind
        df = _mock_query_df(sql)
        assert not df.empty


def test_matrix_provenance_remains_onyx_synthetic_when_irpd_or_serbia_active(monkeypatch: pytest.MonkeyPatch) -> None:
    irpd_filter = queries.FilterState(dataset_track="IRPD_ID_OBSERVED", countries=("ID",))
    mx_sql, mx_params = queries.sql_eu_store_matrix("quick_gold_md01", irpd_filter)
    assert mx_params == ("ONYX_EU_SYNTHETIC",)
    assert "as dataset_track" in mx_sql.lower()
    assert "as provenance_class" in mx_sql.lower()
    assert "as currency_code" in mx_sql.lower()

    mx_df = pd.DataFrame(
        [
            {"store_code": "S1", "store_name": "Berlin #1", "country_code": "DE", "dataset_track": "ONYX_EU_SYNTHETIC", "provenance_class": "SYNTHETIC", "currency_code": "EUR", "line_amount": 100000.0, "weighted_margin_pct": 25.0},
            {"store_code": "S2", "store_name": "Paris #2", "country_code": "FR", "dataset_track": "ONYX_EU_SYNTHETIC", "provenance_class": "SYNTHETIC", "currency_code": "EUR", "line_amount": 60000.0, "weighted_margin_pct": 30.0},
        ]
    )
    meta_irpd = analytics.resolve_matrix_source_meta(mx_df, active_track="IRPD_ID_OBSERVED")
    assert meta_irpd.track_id == "ONYX_EU_SYNTHETIC"
    assert meta_irpd.provenance_class == "SYNTHETIC"
    assert meta_irpd.currency_code == "EUR"
    assert meta_irpd.label_vi == "ONYX Châu Âu — Mô phỏng"
    assert meta_irpd.matches_sidebar_track is False
    assert "không áp dụng bộ lọc" in meta_irpd.scope_note.lower()

    meta_onyx = analytics.resolve_matrix_source_meta(mx_df, active_track="ONYX_EU_SYNTHETIC")
    assert meta_onyx.matches_sidebar_track is True

    win = analytics.ComparisonWindow(
        valid=True,
        mode="latest_full_month",
        mode_label="2 tháng",
        cur_start=dt.date(2025, 12, 1),
        cur_end=dt.date(2025, 12, 31),
        prev_start=dt.date(2025, 11, 1),
        prev_end=dt.date(2025, 11, 30),
        cur_label="T12/2025",
        prev_label="T11/2025",
    )
    var_df = pd.DataFrame([{"store_code": "K1", "store_name": "K24 Jakarta", "presence_status": "Cả 2 kỳ", "delta": -500.0, "pct_change": -0.05}])
    bullets = analytics.build_store_insights(
        var_df=var_df,
        watchlist_df=pd.DataFrame(),
        matrix_df=mx_df,
        window=win,
        metric_label="Doanh thu (IDR)",
        metric_unit="IDR",
        provenance_class="OBSERVED",
        matrix_meta=meta_irpd,
    )
    joined = "\n".join(bullets)
    assert "ONYX Châu Âu — Mô phỏng" in joined
    assert "EUR" in joined
    assert "Tham chiếu riêng" in joined
    assert "Phân tầng hiệu suất (Thực tế" not in joined

    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()
    for track_mode, track_id in (("onyx", "ONYX_EU_SYNTHETIC"), ("irpd", "IRPD_ID_OBSERVED"), ("serbia", "SERBIA_RS_SYNTHETIC")):
        with patch("db.run_query_df", side_effect=lambda sql, params=(), _tm=track_mode: _mock_query_df(sql, params, track_mode=_tm)):
            at = AppTest.from_file(str(STREAMLIT_DIR / "pages/03_cua_hang_loi_nhuan.py"), default_timeout=20)
            at.session_state["f_track"] = track_id
            at.run()
            assert not at.exception
            md_all = "\n".join(m.value for m in at.markdown)
            assert "ONYX Châu Âu — Mô phỏng" in md_all
            assert "EUR" in md_all
            if track_id != "ONYX_EU_SYNTHETIC":
                assert "Phân tầng hiệu suất (Thực tế" not in md_all
                assert "Tham chiếu riêng" in md_all


def test_watchlist_explicit_states_and_truncation_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    win = analytics.ComparisonWindow(
        valid=True,
        mode="latest_full_month",
        mode_label="2 tháng",
        cur_start=dt.date(2025, 12, 1),
        cur_end=dt.date(2025, 12, 31),
        prev_start=dt.date(2025, 11, 1),
        prev_end=dt.date(2025, 11, 30),
        cur_label="T12/2025",
        prev_label="T11/2025",
    )

    # 1. 35 ONYX stores match warning rules -> cut to 20, total_matched preserved = 35
    rows_mx_35 = []
    rows_var_35 = []
    for i in range(40):
        sc = f"S{i:02d}"
        rev = 2000.0 if i < 35 else 500.0
        mrg = 15.0 if i < 35 else 35.0
        rows_mx_35.append({"store_code": sc, "store_name": f"Store {i}", "country_code": "DE", "dataset_track": "ONYX_EU_SYNTHETIC", "provenance_class": "SYNTHETIC", "currency_code": "EUR", "line_amount": rev, "weighted_margin_pct": mrg, "line_count": 10})
        rows_var_35.append({"store_code": sc, "store_name": f"Store {i}", "delta": -100.0, "pct_change": -0.20 if i < 35 else 0.05, "mrg_pp_delta": -2.0 if i < 35 else 0.5, "presence_status": "Cả 2 kỳ", "cur_rev": rev, "prev_rev": rev + 100})
    mx_35 = pd.DataFrame(rows_mx_35)
    var_35 = pd.DataFrame(rows_var_35)

    res_alerts = analytics.build_store_watchlist(var_35, mx_35, window=win, supports_margin=True, cur_col="cur_rev", prev_col="prev_rev")
    assert res_alerts.status == "alerts"
    assert res_alerts.total_matched == 35
    assert res_alerts.displayed_count == 20
    assert len(res_alerts.df) == 20
    assert "35 cửa hàng cần xem xét; hiển thị 20" in res_alerts.subtitle

    ins_alerts = "\n".join(
        analytics.build_store_insights(
            var_df=var_35,
            watchlist_result=res_alerts,
            matrix_df=mx_35,
            window=win,
            metric_label="Doanh thu (EUR)",
            metric_unit="EUR",
            provenance_class="SYNTHETIC",
            matrix_meta=analytics.resolve_matrix_source_meta(mx_35, active_track="ONYX_EU_SYNTHETIC"),
        )
    )
    assert "35 cửa hàng cần xem xét; hiển thị 20" in ins_alerts

    # 2. Zero stores match alert rules -> Top 10 low-margin reference list (NOT labeled as alerts)
    rows_mx_ref = []
    rows_var_ref = []
    for i in range(24):
        sc = f"R{i:02d}"
        # First 12 have lower revenue (< median) AND low margin; upper 12 have higher revenue (>= median) AND high margin -> zero overlap with DT>=med & mrg<med
        rev = 1000.0 + i * 100.0
        mrg = 15.0 + i * 1.0
        rows_mx_ref.append({"store_code": sc, "store_name": f"RefStore {i}", "country_code": "FR", "dataset_track": "ONYX_EU_SYNTHETIC", "provenance_class": "SYNTHETIC", "currency_code": "EUR", "line_amount": rev, "weighted_margin_pct": mrg, "line_count": 10})
        rows_var_ref.append({"store_code": sc, "store_name": f"RefStore {i}", "delta": 50.0, "pct_change": 0.05, "mrg_pp_delta": 0.2, "presence_status": "Cả 2 kỳ", "cur_rev": rev, "prev_rev": rev - 50.0})
    mx_ref = pd.DataFrame(rows_mx_ref)
    var_ref = pd.DataFrame(rows_var_ref)
    res_ref = analytics.build_store_watchlist(var_ref, mx_ref, window=win, supports_margin=True, cur_col="cur_rev", prev_col="prev_rev")
    assert res_ref.status == "reference_low_margin"
    assert res_ref.total_matched == 0
    assert res_ref.displayed_count == 10
    assert "Tham Khảo" in res_ref.title
    assert "chưa vượt tiêu chí cảnh báo" in res_ref.df["Lý do cần xem xét"].iloc[0]

    ins_ref = "\n".join(
        analytics.build_store_insights(
            var_df=var_ref,
            watchlist_result=res_ref,
            matrix_df=mx_ref,
            window=win,
            metric_label="Doanh thu (EUR)",
            metric_unit="EUR",
            provenance_class="SYNTHETIC",
            matrix_meta=analytics.resolve_matrix_source_meta(mx_ref, active_track="ONYX_EU_SYNTHETIC"),
        )
    )
    assert "Chưa có cửa hàng vượt tiêu chí cảnh báo" in ins_ref
    assert "tham khảo" in ins_ref.lower()

    # 3. Insufficient data state
    invalid_win = analytics.ComparisonWindow(False, "latest_full_month", "2 tháng", None, None, None, None, "—", "—", "Thiếu kỳ")
    res_insuff = analytics.build_store_watchlist(var_ref, mx_ref, window=invalid_win, supports_margin=True, cur_col="cur_rev", prev_col="prev_rev")
    assert res_insuff.status == "insufficient_data"
    assert res_insuff.df.empty

    # 4. Non-margin source (IRPD/Serbia): declining > 15 truncation AND no_alerts (all positive)
    non_mrg_20 = pd.DataFrame(
        [{"store_code": f"D{i}", "store_name": f"Dec {i}", "presence_status": "Cả 2 kỳ", "delta": -10.0 * (i + 1), "pct_change": -0.1, "cur_rev": 100.0, "prev_rev": 200.0} for i in range(20)]
    )
    res_nm_alerts = analytics.build_store_watchlist(non_mrg_20, mx_ref, window=win, supports_margin=False, cur_col="cur_rev", prev_col="prev_rev")
    assert res_nm_alerts.status == "alerts"
    assert res_nm_alerts.total_matched == 20
    assert res_nm_alerts.displayed_count == 15
    assert "20 cửa hàng cần xem xét; hiển thị 15" in res_nm_alerts.subtitle

    non_mrg_up = pd.DataFrame(
        [{"store_code": f"U{i}", "store_name": f"Up {i}", "presence_status": "Cả 2 kỳ", "delta": 25.0, "pct_change": 0.1, "cur_rev": 125.0, "prev_rev": 100.0} for i in range(4)]
    )
    res_no_alerts = analytics.build_store_watchlist(non_mrg_up, mx_ref, window=win, supports_margin=False, cur_col="cur_rev", prev_col="prev_rev")
    assert res_no_alerts.status == "no_alerts"
    assert res_no_alerts.total_matched == 0
    assert res_no_alerts.df.empty

    # AppTest verification on Page 3 rendering reference_low_margin clearly
    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()

    def _side_ref_only(sql: str, params: tuple = ()) -> pd.DataFrame:
        kind = _classify_sql(sql)
        if kind == "dim_variance_store":
            return pd.DataFrame(
                [
                    {"store_code": "ONYX:PH0014", "store_name": "Berlin HealthPoint #014", "country_code": "DE", "nonnull_label_rows": 100, "cur_qty": 450.0, "prev_qty": 400.0, "cur_rev": 95100.0, "prev_rev": 90000.0, "cur_mrg": 27674.0, "prev_mrg": 26100.0, "cur_lines": 90, "prev_lines": 80, "cur_store_days": 25, "prev_store_days": 24, "cur_weighted_margin_pct": 29.10, "prev_weighted_margin_pct": 29.00},
                    {"store_code": "ONYX:PH0120", "store_name": "Naples HealthPoint #120", "country_code": "IT", "nonnull_label_rows": 100, "cur_qty": 420.0, "prev_qty": 400.0, "cur_rev": 83794.0, "prev_rev": 80000.0, "cur_mrg": 23557.0, "prev_mrg": 22400.0, "cur_lines": 70, "prev_lines": 68, "cur_store_days": 22, "prev_store_days": 21, "cur_weighted_margin_pct": 28.11, "prev_weighted_margin_pct": 28.00},
                ]
            )
        return _mock_query_df(sql, params, track_mode="onyx")

    with patch("db.run_query_df", side_effect=_side_ref_only):
        at = AppTest.from_file(str(STREAMLIT_DIR / "pages/03_cua_hang_loi_nhuan.py"), default_timeout=20)
        at.run()
        assert not at.exception
        md_all = "\n".join(m.value for m in at.markdown)
        assert "Danh Sách Tham Khảo (Chưa Có Cảnh Báo)" in md_all
        assert "Chưa có cửa hàng vượt tiêu chí cảnh báo" in md_all


def test_full_catalog_variance_and_mix_shift_over_500_products_and_prev_only() -> None:
    d0, d1 = dt.date(2025, 11, 1), dt.date(2025, 11, 30)
    d2, d3 = dt.date(2025, 12, 1), dt.date(2025, 12, 31)
    f = queries.FilterState(dataset_track="IRPD_ID_OBSERVED")
    sql, _ = queries.sql_dimension_variance("quick_gold_md01", f, dim_kind="product", cur_start=d2, cur_end=d3, prev_start=d0, prev_end=d1)
    assert "limit %s" not in sql.lower()
    assert "COALESCE(NULLIF(TRIM(product_name), ''), 'Chưa xác định')" in sql
    assert "nonnull_label_rows" in sql

    # Simulate 650 products: top 500 grew +10% (50,000 -> 55,000) while 150 prev-only dropped 12,000 -> 0 => full catalog -11.29%
    rows = [
        {"product_name": f"Top_{i}", "clean_uom": "tab", "cur_rev": 110.0, "prev_rev": 100.0, "cur_lines": 5, "prev_lines": 5}
        for i in range(500)
    ] + [
        {"product_name": f"PrevOnly_{j}", "clean_uom": "tab", "cur_rev": np.nan, "prev_rev": 80.0, "cur_lines": 0, "prev_lines": 4}
        for j in range(150)
    ]
    res = analytics.compute_variance_and_contributions(pd.DataFrame(rows), cur_col="cur_rev", prev_col="prev_rev", metric_supported=True)
    assert len(res) == 650
    assert res["contrib_pp"].sum() == pytest.approx((-7000.0 / 62000.0) * 100.0)
    assert res["mix_shift_pp"].sum() == pytest.approx(0.0)
    prev_only_rows = res[res["product_name"].str.startswith("PrevOnly_")]
    assert (prev_only_rows["presence_status"] == "Chỉ phát sinh kỳ trước").all()
    assert (prev_only_rows["cur_rev"] == 0.0).all()

    # Missing data (sales lines occurred in period, revenue missing) vs unsupported metric
    edge_df = pd.DataFrame([{"product_name": "MissingRev", "clean_uom": "tab", "cur_rev": np.nan, "prev_rev": 100.0, "cur_lines": 3, "prev_lines": 2}])
    miss_res = analytics.compute_variance_and_contributions(edge_df, cur_col="cur_rev", prev_col="prev_rev", metric_supported=True)
    assert miss_res["presence_status"].iloc[0] == "Thiếu dữ liệu chỉ số"
    assert pd.isna(miss_res["delta"].iloc[0])

    unsup_res = analytics.compute_variance_and_contributions(edge_df, cur_col="cur_rev", prev_col="prev_rev", metric_supported=False)
    assert unsup_res["presence_status"].iloc[0] == "Nguồn không hỗ trợ chỉ số"
    assert pd.isna(unsup_res["delta"].iloc[0])


def test_weather_insights_sample_size_guard_cases() -> None:
    # 0 adequate groups
    df0 = pd.DataFrame([
        {"temp_band": "1. Cold (<10C)", "rain_regime": "1. Dry (0 mm)", "active_store_days": 10, "qty_per_store_day": 5.0},
        {"temp_band": "4. Warm (27-30C)", "rain_regime": "4. Heavy (>20 mm)", "active_store_days": 1, "qty_per_store_day": 500.0},
    ])
    b0 = "\n".join(analytics.build_weather_insights(hm_df=df0, metric_col="qty_per_store_day", metric_unit="tab", metric_noun="SL/CH-ngày", provenance_class="OBSERVED", active_store_days=11, possible_store_days=100))
    assert "Chưa đủ 2 nhóm đạt ngưỡng sàng lọc cỡ mẫu" in b0
    assert "+9900" not in b0

    # Exactly 1 adequate group (n=100, rate=10) + 1 tiny group (n=1, rate=1000) -> MUST NOT report +9900% or compare n>=30
    df1 = pd.DataFrame([
        {"temp_band": "1. Cold (<10C)", "rain_regime": "1. Dry (0 mm)", "active_store_days": 100, "qty_per_store_day": 10.0},
        {"temp_band": "4. Warm (27-30C)", "rain_regime": "4. Heavy (>20 mm)", "active_store_days": 1, "qty_per_store_day": 1000.0},
    ])
    b1 = "\n".join(analytics.build_weather_insights(hm_df=df1, metric_col="qty_per_store_day", metric_unit="tab", metric_noun="SL/CH-ngày", provenance_class="OBSERVED", active_store_days=101, possible_store_days=200))
    assert "Chưa đủ 2 nhóm đạt ngưỡng sàng lọc cỡ mẫu" in b1
    assert "1/2" in b1
    assert "9,900" not in b1 and "9900" not in b1

    # >=2 adequate groups + tiny outlier -> compares strictly among adequate groups
    df2 = pd.DataFrame([
        {"temp_band": "1. Cold (<10C)", "rain_regime": "1. Dry (0 mm)", "active_store_days": 100, "qty_per_store_day": 12.0},
        {"temp_band": "2. Cool (10-20C)", "rain_regime": "2. Light (0-5 mm)", "active_store_days": 80, "qty_per_store_day": 10.0},
        {"temp_band": "4. Warm (27-30C)", "rain_regime": "4. Heavy (>20 mm)", "active_store_days": 2, "qty_per_store_day": 9999.0},
    ])
    b2 = "\n".join(analytics.build_weather_insights(hm_df=df2, metric_col="qty_per_store_day", metric_unit="tab", metric_noun="SL/CH-ngày", provenance_class="OBSERVED", active_store_days=182, possible_store_days=200))
    assert "chênh +20.0%" in b2
    assert "9,999" not in b2


def test_store_insights_all_direction_cases_without_double_signs() -> None:
    win = analytics.ComparisonWindow(True, "latest_full_month", "2 tháng", dt.date(2025, 12, 1), dt.date(2025, 12, 31), dt.date(2025, 11, 1), dt.date(2025, 11, 30), "T12/2025", "T11/2025")
    mx_empty = pd.DataFrame()

    # All increasing
    up_df = pd.DataFrame([
        {"store_name": "A", "presence_status": "Cả 2 kỳ", "delta": 20.0, "pct_change": 0.2},
        {"store_name": "B", "presence_status": "Cả 2 kỳ", "delta": 5.0, "pct_change": 0.05},
    ])
    t_up = "\n".join(analytics.build_store_insights(var_df=up_df, matrix_df=mx_empty, window=win, metric_label="Doanh thu", metric_unit="EUR", provenance_class="SYNTHETIC"))
    assert "Không có cửa hàng giảm" in t_up
    assert "giảm sâu nhất" not in t_up

    # All decreasing (must never emit '+-' or 'tăng mạnh nhất')
    dn_df = pd.DataFrame([
        {"store_name": "A", "presence_status": "Cả 2 kỳ", "delta": -5.0, "pct_change": -0.05},
        {"store_name": "B", "presence_status": "Cả 2 kỳ", "delta": -20.0, "pct_change": -0.20},
    ])
    t_dn = "\n".join(analytics.build_store_insights(var_df=dn_df, matrix_df=mx_empty, window=win, metric_label="Doanh thu", metric_unit="EUR", provenance_class="SYNTHETIC"))
    assert "+-" not in t_dn
    assert "tăng mạnh nhất" not in t_dn.lower()
    assert "Không có cửa hàng tăng" in t_dn

    # All unchanged
    flat_df = pd.DataFrame([
        {"store_name": "A", "presence_status": "Cả 2 kỳ", "delta": 0.0, "pct_change": 0.0},
        {"store_name": "B", "presence_status": "Cả 2 kỳ", "delta": 0.0, "pct_change": 0.0},
    ])
    t_flat = "\n".join(analytics.build_store_insights(var_df=flat_df, matrix_df=mx_empty, window=win, metric_label="Doanh thu", metric_unit="EUR", provenance_class="SYNTHETIC"))
    assert "không đổi (chênh lệch = 0)" in t_flat

    # Single same-store
    one_df = pd.DataFrame([{"store_name": "Solo", "presence_status": "Cả 2 kỳ", "delta": -15.0, "pct_change": -0.10}])
    t_one = "\n".join(analytics.build_store_insights(var_df=one_df, matrix_df=mx_empty, window=win, metric_label="Doanh thu", metric_unit="EUR", provenance_class="SYNTHETIC"))
    assert "Cửa hàng duy nhất phát sinh cả 2 kỳ (Solo)" in t_one
    assert "+-" not in t_one

    # Zero same-store
    zero_df = pd.DataFrame([{"store_name": "NewOnly", "presence_status": "Mới phát sinh kỳ này", "delta": 30.0, "pct_change": None}])
    t_zero = "\n".join(analytics.build_store_insights(var_df=zero_df, matrix_df=mx_empty, window=win, metric_label="Doanh thu", metric_unit="EUR", provenance_class="SYNTHETIC"))
    assert "Chưa có cửa hàng nào phát sinh đồng thời cả 2 kỳ" in t_zero


def test_kpi_period_separation_multi_year_single_and_partial_month(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()

    # 1. Multi-year (default ONYX 2024-01-01..2025-12-31)
    with patch("db.run_query_df", side_effect=lambda s, p=(): _mock_query_df(s, p, track_mode="onyx")):
        at = AppTest.from_file(str(STREAMLIT_DIR / "pages/01_tong_quan.py"), default_timeout=20)
        at.run()
        assert not at.exception
        md = "\n".join(m.value for m in at.markdown)
        assert "Lũy kế lọc: 01/01/2024–31/12/2025" in md
        assert "Kỳ T02/2024:" in md
        assert "So với T01/2024:" in md

    # 2. Single full month (2024-02-01..2024-02-29 -> half-split within month, clearly distinct from full-month headline)
    with patch("db.run_query_df", side_effect=lambda s, p=(): _mock_query_df(s, p, track_mode="onyx")):
        at_m = AppTest.from_file(str(STREAMLIT_DIR / "pages/01_tong_quan.py"), default_timeout=20)
        at_m.session_state["f_date_range"] = (dt.date(2024, 2, 1), dt.date(2024, 2, 29))
        at_m.run()
        assert not at_m.exception
        md_m = "\n".join(m.value for m in at_m.markdown)
        assert "Lũy kế lọc: 01/02/2024–29/02/2024" in md_m
        assert "Kỳ 16/02/24–29/02/24:" in md_m
        assert "So với 02/02/24–15/02/24:" in md_m

    # 3. Partial month (2024-02-05..2024-02-20 -> falls back cleanly to half-split)
    with patch("db.run_query_df", side_effect=lambda s, p=(): _mock_query_df(s, p, track_mode="onyx")):
        at_p = AppTest.from_file(str(STREAMLIT_DIR / "pages/01_tong_quan.py"), default_timeout=20)
        at_p.session_state["f_date_range"] = (dt.date(2024, 2, 5), dt.date(2024, 2, 20))
        at_p.run()
        assert not at_p.exception
        md_p = "\n".join(m.value for m in at_p.markdown)
        assert "Lũy kế lọc: 05/02/2024–20/02/2024" in md_p
        assert "Kỳ 13/02/24–20/02/24:" in md_p
        assert "So với 05/02/24–12/02/24:" in md_p


# ---------------------------------------------------------------------------
# 6. Visual-First Redesign Tests: Clusters, VND, Granularity, Maps & Drawer
# ---------------------------------------------------------------------------

def test_cluster_extraction_vnd_conversion_and_new_sql_builders() -> None:
    assert config.extract_city_cluster("Munich HealthPoint #003") == "Munich"
    assert config.extract_city_cluster("Apotek Simulasi IRPD - Jawa Tengah") == "Apotek Simulasi IRPD - Jawa Tengah"
    assert config.extract_city_cluster("") == "Chưa rõ"

    assert config.fmt_currency(100.0, "EUR", to_vnd=True) == "2.75M ₫"
    assert config.fmt_currency(10_000.0, "IDR", to_vnd=True) == "16.00K ₫"
    assert config.fmt_currency(100.0, None, to_vnd=True) == "—"
    assert "Quy đổi tham chiếu" in config.vnd_rate_note("EUR", True)
    assert config.vnd_rate_note(None, True) == ""

    f = queries.FilterState(
        dataset_track="ONYX_EU_SYNTHETIC",
        city_clusters=("Munich", "Frankfurt"),
        time_grain="week",
        display_vnd=True,
    )
    where_sql, params = queries.build_where_clause(f)
    assert "SPLIT_PART(store_name, ' HealthPoint', 1) = ANY(%s)" in where_sql
    assert ["Munich", "Frankfurt"] in params

    for g, trunc_kw in (("day", "'day'"), ("week", "'week'"), ("month", "'month'"), ("quarter", "'quarter'")):
        ts_sql, _ = queries.sql_time_series_by_grain("quick_gold_md01", f, grain=g, products=("PainLess Throat Spray",))
        assert f"DATE_TRUNC({trunc_kw}" in ts_sql
        assert "COALESCE(NULLIF(TRIM(product_name), ''), 'Chưa xác định') = ANY(%s)" in ts_sql

    mix_sql, _ = queries.sql_store_product_mix(
        "quick_gold_md01",
        f,
        cur_start=dt.date(2025, 12, 1),
        cur_end=dt.date(2025, 12, 31),
        prev_start=dt.date(2025, 11, 1),
        prev_end=dt.date(2025, 11, 30),
        search_text="Pain",
    )
    assert "LIMIT" not in mix_sql.upper()
    assert "weighted_unit_price" in mix_sql
    assert "ILIKE %s" in mix_sql

    map_sql, map_params = queries.sql_store_map_points("quick_gold_md01", f, force_onyx=True)
    assert "map_lat" in map_sql and "map_lon" in map_sql and "city_cluster" in map_sql
    assert map_params[0] == "ONYX_EU_SYNTHETIC"


def test_redesigned_pages_drawer_product_trend_map_and_custom_compare(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()

    # Page 1: right explanation drawer open + multi-product weekly series + VND display
    with patch("db.run_query_df", side_effect=lambda s, p=(): _mock_query_df(s, p, track_mode="onyx")):
        at1 = AppTest.from_file(str(STREAMLIT_DIR / "pages/01_tong_quan.py"), default_timeout=20)
        at1.session_state["ui_info_drawer_open"] = True
        at1.session_state["f_display_vnd"] = True
        at1.session_state["f_time_grain"] = "week"
        at1.session_state["p1_selected_products"] = ["PainLess Throat Spray", "AntiBioX 10 mg"]
        at1.run()
        assert not at1.exception
        md1 = "\n".join(m.value for m in at1.markdown)
        assert "ⓘ Giải thích ·" in md1
        assert "₫" in md1

    # Page 2: right drawer open without leaking weather filters
    with patch("db.run_query_df", side_effect=lambda s, p=(): _mock_query_df(s, p, track_mode="onyx")):
        at2 = AppTest.from_file(str(STREAMLIT_DIR / "pages/02_thoi_tiet_dia_diem.py"), default_timeout=20)
        at2.session_state["ui_info_drawer_open"] = True
        at2.session_state["p2_selected_products"] = ["PainLess Throat Spray"]
        at2.run()
        assert not at2.exception
        md2 = "\n".join(m.value for m in at2.markdown)
        assert "ⓘ Giải thích · Thời Tiết &amp; Mùa Vụ" in md2

    # Page 3: cluster street map + PyDeck 3D columns engine
    with patch("db.run_query_df", side_effect=lambda s, p=(): _mock_query_df(s, p, track_mode="onyx")):
        at3 = AppTest.from_file(str(STREAMLIT_DIR / "pages/03_cua_hang_loi_nhuan.py"), default_timeout=20)
        at3.session_state["p3_map_mode"] = "cluster"
        at3.session_state["p3_map_engine"] = "pydeck"
        at3.run()
        assert not at3.exception

    # Page 4: custom Period A vs Period B comparison
    with patch("db.run_query_df", side_effect=lambda s, p=(): _mock_query_df(s, p, track_mode="onyx")):
        at4 = AppTest.from_file(str(STREAMLIT_DIR / "pages/04_san_pham_atc.py"), default_timeout=20)
        at4.session_state["p4_compare_mode"] = "custom"
        at4.session_state["p4_custom_a"] = (dt.date(2025, 11, 1), dt.date(2025, 12, 31))
        at4.session_state["p4_custom_b"] = (dt.date(2025, 9, 1), dt.date(2025, 10, 31))
        at4.run()
        assert not at4.exception
        md4 = "\n".join(m.value for m in at4.markdown)
        assert "01/11/2025–31/12/2025" in md4
        assert "01/09/2025–31/10/2025" in md4


