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
        "f_stores": ["Some Store"],
        "f_uoms": ["tab"],
        "f_temp_bands": ["5. Hot (>=30C)"],
        "f_compare_mode": "half_split",
        "f_date_range": (dt.date(2024, 1, 1), dt.date(2024, 6, 30)),
        "p2_rain_regimes": ["4. Heavy (>20 mm)"],
        "p2_humidity_bands": ["3. High (>80%)"],
        "p2_cell_temp": "5. Hot (>=30C)",
        "p2_cell_rain": "4. Heavy (>20 mm)",
        "p3_store_search": "Berlin",
        "p4_product_search": "AntiBioX",
        "p4_atc_apply_date": True,
    }
    monkeypatch.setattr(filter_comp.st, "session_state", fake_state)
    filter_comp.reset_all_filters()

    assert fake_state["f_track"] == config.DEFAULT_TRACK
    assert fake_state["f_countries"] == []
    assert fake_state["f_stores"] == []
    assert fake_state["f_uoms"] == []
    assert fake_state["f_temp_bands"] == []
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
    assert {"pharmaflow", "aws_quick", "ocean", "warm"}.issubset(config.PALETTES.keys())
    for k, pal in config.PALETTES.items():
        assert pal.primary.startswith("#")
        assert len(set(pal.discrete[:4])) == 4, k

    assert "$" not in config.fmt_currency(8_619_407.63, "EUR")
    assert config.fmt_metric_state(0.0, supported=True, has_rows=True) == "0"
    assert config.fmt_metric_state(None, supported=True, has_rows=False) == "Không có dữ liệu"
    assert config.fmt_metric_state(None, supported=False, has_rows=True) == "Nguồn không hỗ trợ"


# ---------------------------------------------------------------------------
# 4. End-to-End Mocked AppTest Across Tracks, Multi-UOM & Empty Results
# ---------------------------------------------------------------------------

import numpy as np  # noqa: E402


def _mock_query_df(sql: str, params: tuple = (), *, track_mode: str = "onyx") -> pd.DataFrame:
    sql_low = sql.lower()
    if "sync_release_state" in sql_low:
        return pd.DataFrame(
            [{
                "product_domain": "MD01_SALES_AND_DEMAND",
                "release_id": "md01-test-release",
                "status": "SUCCEEDED",
                "sync_mode": "databricks_jdbc",
                "synced_at_utc": dt.datetime(2026, 11, 17, 12, 33, tzinfo=dt.timezone.utc),
                "table_counts_json": "{}",
            }]
        )
    if "group by dataset_track\n" in sql_low and "row_count" in sql_low:
        rows = [
            {"dataset_track": "ONYX_EU_SYNTHETIC", "currency_code": "EUR", "provenance_class": "SYNTHETIC", "row_count": 62036},
            {"dataset_track": "IRPD_ID_OBSERVED", "currency_code": "IDR", "provenance_class": "OBSERVED", "row_count": 387021},
            {"dataset_track": "SERBIA_RS_SYNTHETIC", "currency_code": None, "provenance_class": "SYNTHETIC", "row_count": 25534},
        ]
        if track_mode == "irpd":
            rows = [rows[1], rows[0], rows[2]]
        elif track_mode == "serbia":
            rows = [rows[2], rows[0], rows[1]]
        return pd.DataFrame(rows)
    if "cross join store_list sl" in sql_low:
        if track_mode == "irpd":
            return pd.DataFrame(
                [{
                    "min_date": dt.date(2023, 1, 2),
                    "max_date": dt.date(2025, 12, 31),
                    "countries": ["ID"],
                    "uoms": ["tab", "pcs", "fls"],
                    "stores": ["K24 Jakarta"],
                }]
            )
        if track_mode == "serbia":
            return pd.DataFrame(
                [{
                    "min_date": dt.date(2014, 1, 2),
                    "max_date": dt.date(2019, 10, 8),
                    "countries": ["RS"],
                    "uoms": ["ATC_DEFINED_DAILY_DOSE_X10"],
                    "stores": ["Belgrade Central Pharmacy"],
                }]
            )
        return pd.DataFrame(
            [{
                "min_date": dt.date(2024, 1, 1),
                "max_date": dt.date(2025, 12, 31),
                "countries": ["DE", "FR", "IT"],
                "uoms": ["ONYX_UNIT"],
                "stores": ["Berlin HealthPoint #014", "Paris HealthPoint #013"],
            }]
        )
    if "weighted_margin_pct" in sql_low and "total_line_count" in sql_low:
        if track_mode == "irpd":
            return pd.DataFrame(
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
            )
        if track_mode == "serbia":
            return pd.DataFrame(
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
            )
        return pd.DataFrame(
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
        )
    if "group by coalesce(clean_uom" in sql_low:
        return pd.DataFrame(
            [
                {"clean_uom": "tab", "mart_rows": 135127, "line_count": 220000, "active_store_days": 1088, "sold_qty": 3631938.0, "line_amount": 3990501292.0, "weighted_unit_price": 1098.72},
                {"clean_uom": "pcs", "mart_rows": 91627, "line_count": 150000, "active_store_days": 1088, "sold_qty": 400927.0, "line_amount": 3120294962.0, "weighted_unit_price": 7782.70},
            ]
        )
    if "as first_date" in sql_low and "group by year_month" in sql_low:
        if track_mode == "serbia":
            return pd.DataFrame(
                [
                    {"year_month": dt.date(2019, 8, 1), "sold_qty": 19000.0, "line_amount": None, "margin_amount": None, "line_count": 400, "active_days": 31, "active_store_days": 31, "first_date": dt.date(2019, 8, 1), "last_date": dt.date(2019, 8, 31)},
                    {"year_month": dt.date(2019, 9, 1), "sold_qty": 18200.0, "line_amount": None, "margin_amount": None, "line_count": 390, "active_days": 30, "active_store_days": 30, "first_date": dt.date(2019, 9, 1), "last_date": dt.date(2019, 9, 30)},
                    {"year_month": dt.date(2019, 10, 1), "sold_qty": 4800.0, "line_amount": None, "margin_amount": None, "line_count": 90, "active_days": 8, "active_store_days": 8, "first_date": dt.date(2019, 10, 1), "last_date": dt.date(2019, 10, 8)},
                ]
            )
        return pd.DataFrame(
            [
                {"year_month": dt.date(2024, 1, 1), "sold_qty": 18785.0, "line_amount": 360000.0, "margin_amount": 100000.0 if track_mode == "onyx" else None, "line_count": 2457, "active_days": 31, "active_store_days": 1700, "first_date": dt.date(2024, 1, 1), "last_date": dt.date(2024, 1, 31)},
                {"year_month": dt.date(2024, 2, 1), "sold_qty": 17740.0, "line_amount": 342000.0, "margin_amount": 95000.0 if track_mode == "onyx" else None, "line_count": 2236, "active_days": 29, "active_store_days": 1580, "first_date": dt.date(2024, 2, 1), "last_date": dt.date(2024, 2, 29)},
            ]
        )
    if "series_avg_pct_change" in sql_low:
        return pd.DataFrame(
            [
                {"period_start": dt.date(2024, 1, 1), "sold_qty": 18785.0, "series_avg_pct_change": None, "series_pct_rows": 0, "line_count": 2457},
                {"period_start": dt.date(2024, 2, 1), "sold_qty": 17740.0, "series_avg_pct_change": 0.6443, "series_pct_rows": 281, "line_count": 2236},
            ]
        )
    if "cur_weighted_margin_pct" in sql_low:
        m_val = 28.0 if track_mode == "onyx" else None
        r_cur = 100000.0 if track_mode != "serbia" else None
        r_prev = 95000.0 if track_mode != "serbia" else None
        if "group by country_code" in sql_low:
            return pd.DataFrame(
                [
                    {"country_code": "DE", "cur_qty": 5000.0, "prev_qty": 4500.0, "cur_rev": r_cur, "prev_rev": r_prev, "cur_mrg": 28000.0, "prev_mrg": 26000.0, "cur_lines": 500, "prev_lines": 450, "cur_store_days": 200, "prev_store_days": 190, "cur_weighted_margin_pct": m_val, "prev_weighted_margin_pct": m_val},
                    {"country_code": "FR", "cur_qty": 4000.0, "prev_qty": 4300.0, "cur_rev": 80000.0 if track_mode != "serbia" else None, "prev_rev": 86000.0 if track_mode != "serbia" else None, "cur_mrg": 22000.0, "prev_mrg": 24000.0, "cur_lines": 400, "prev_lines": 430, "cur_store_days": 180, "prev_store_days": 185, "cur_weighted_margin_pct": m_val, "prev_weighted_margin_pct": m_val},
                ]
            )
        if "group by store_code, store_name, country_code" in sql_low:
            return pd.DataFrame(
                [
                    {"store_code": "ONYX:PH0014", "store_name": "Berlin HealthPoint #014", "country_code": "DE", "cur_qty": 450.0, "prev_qty": 400.0, "cur_rev": r_cur, "prev_rev": r_prev, "cur_mrg": 25000.0, "prev_mrg": 24000.0, "cur_lines": 90, "prev_lines": 80, "cur_store_days": 25, "prev_store_days": 24, "cur_weighted_margin_pct": m_val, "prev_weighted_margin_pct": 29.0 if track_mode == "onyx" else None},
                    {"store_code": "ONYX:PH0120", "store_name": "Naples HealthPoint #120", "country_code": "IT", "cur_qty": 320.0, "prev_qty": 420.0, "cur_rev": 75000.0 if track_mode != "serbia" else None, "prev_rev": 95000.0 if track_mode != "serbia" else None, "cur_mrg": 20000.0, "prev_mrg": 25000.0, "cur_lines": 70, "prev_lines": 85, "cur_store_days": 22, "prev_store_days": 25, "cur_weighted_margin_pct": 25.0 if track_mode == "onyx" else None, "prev_weighted_margin_pct": 27.0 if track_mode == "onyx" else None},
                ]
            )
        return pd.DataFrame(
            [
                {"product_name": "PainLess Throat Spray", "clean_uom": "ONYX_UNIT", "cur_qty": 900.0, "prev_qty": 800.0, "cur_rev": r_cur, "prev_rev": r_prev, "cur_mrg": 25000.0, "prev_mrg": 22000.0, "cur_lines": 150, "prev_lines": 140, "cur_store_days": 80, "prev_store_days": 75, "cur_weighted_margin_pct": m_val, "prev_weighted_margin_pct": m_val},
                {"product_name": "AntiBioX 10 mg", "clean_uom": "ONYX_UNIT", "cur_qty": 650.0, "prev_qty": 750.0, "cur_rev": 65000.0 if track_mode != "serbia" else None, "prev_rev": 78000.0 if track_mode != "serbia" else None, "cur_mrg": 18000.0, "prev_mrg": 21000.0, "cur_lines": 110, "prev_lines": 125, "cur_store_days": 65, "prev_store_days": 70, "cur_weighted_margin_pct": m_val, "prev_weighted_margin_pct": m_val},
            ]
        )
    if "group by country_code\n" in sql_low and "lat" not in sql_low:
        return pd.DataFrame(
            [
                {"country_code": "DE", "sold_qty": 75000.0, "line_amount": 1500000.0 if track_mode != "serbia" else None, "line_count": 10000, "active_store_days": 6000},
                {"country_code": "FR", "sold_qty": 71000.0, "line_amount": 1400000.0 if track_mode != "serbia" else None, "line_count": 9500, "active_store_days": 5800},
            ]
        )
    if "group by brand_name\n" in sql_low and "weighted_margin_pct" not in sql_low:
        return pd.DataFrame(
            [
                {"brand_name": "PainLess", "sold_qty": 34000.0, "line_amount": 700000.0, "margin_amount": 190000.0, "line_count": 4800},
                {"brand_name": "Medica", "sold_qty": 33000.0, "line_amount": 680000.0, "margin_amount": 185000.0, "line_count": 4600},
            ]
        )
    if "coalesce(currency_code, 'n/a')" in sql_low:
        return pd.DataFrame(
            [
                {"dataset_track": "ONYX_EU_SYNTHETIC", "currency_code": "EUR", "provenance_class": "SYNTHETIC", "distinct_uom_count": 1, "min_date": dt.date(2024, 1, 1), "max_date": dt.date(2025, 12, 31), "sold_qty": 445078.0, "line_count": 62036, "active_store_days": 42666, "line_amount": 8619407.63, "margin_amount": 2416838.58},
                {"dataset_track": "IRPD_ID_OBSERVED", "currency_code": "IDR", "provenance_class": "OBSERVED", "distinct_uom_count": 20, "min_date": dt.date(2023, 1, 2), "max_date": dt.date(2025, 12, 31), "sold_qty": 4638081.3, "line_count": 627389, "active_store_days": 1088, "line_amount": 12599183524.0, "margin_amount": None},
            ]
        )
    if "rainy_store_days" in sql_low:
        return pd.DataFrame(
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
        )
    if "group by temp_band, rain_regime" in sql_low:
        return pd.DataFrame(
            [
                {"temp_band": "1. Cold (<10C)", "rain_regime": "1. Dry (0 mm)", "mart_rows": 10195, "active_store_days": 6976, "active_days": 375, "distinct_stores": 119, "sold_qty": 73959.0, "line_amount": 1400000.0, "qty_per_store_day": 10.60, "rev_per_store_day": 200.69},
                {"temp_band": "2. Cool (10-20C)", "rain_regime": "2. Light (0-5 mm)", "mart_rows": 11999, "active_store_days": 8244, "active_days": 641, "distinct_stores": 119, "sold_qty": 85882.0, "line_amount": 1650000.0, "qty_per_store_day": 10.42, "rev_per_store_day": 200.15},
                {"temp_band": "4. Warm (27-30C)", "rain_regime": "4. Heavy (>20 mm)", "mart_rows": 6, "active_store_days": 2, "active_days": 1, "distinct_stores": 2, "sold_qty": 48.0, "line_amount": 900.0, "qty_per_store_day": 24.0, "rev_per_store_day": 450.0},
            ]
        )
    if "group by humidity_band, is_weekend" in sql_low:
        return pd.DataFrame(
            [
                {"humidity_band": "2. Normal (60-80%)", "is_weekend": False, "active_store_days": 16099, "sold_qty": 171235.0, "line_amount": 3200000.0, "qty_per_store_day": 10.64, "rev_per_store_day": 198.77},
                {"humidity_band": "2. Normal (60-80%)", "is_weekend": True, "active_store_days": 5733, "sold_qty": 57058.0, "line_amount": 1080000.0, "qty_per_store_day": 9.95, "rev_per_store_day": 188.38},
            ]
        )
    if "group by f.local_date, f.rain_regime, dw.temp_mean" in sql_low:
        return pd.DataFrame(
            [{"local_date": dt.date(2024, 5, 1), "rain_regime": "1. Dry (0 mm)", "temp_mean": 16.5, "active_stores": 60, "sold_qty": 620.0, "line_amount": 12000.0, "qty_per_store_day": 10.33, "rev_per_store_day": 200.0, "line_count": 90}]
        )
    if "as avg_apparent_temp_mean" in sql_low and "w_month" in sql_low:
        return pd.DataFrame(
            [{"year_month": dt.date(2024, 5, 1), "active_store_days": 1800, "active_days": 31, "sold_qty": 18500.0, "line_amount": 350000.0, "qty_per_store_day": 10.28, "rev_per_store_day": 194.44, "avg_temp_mean": 16.2, "avg_apparent_temp_mean": 15.8, "avg_precip_sum": 1.9, "avg_humidity_mean": 68.4}]
        )
    if "group by local_date, store_name" in sql_low or "from filtered f\n        left join day_w" in sql_low:
        return pd.DataFrame(
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
        )
    if "with top_products as" in sql_low:
        return pd.DataFrame(
            [
                {"product_name": "PainLess Throat Spray", "rain_regime": "1. Dry (0 mm)", "active_store_days": 220, "sold_qty": 3200.0, "line_amount": 60000.0, "total_metric": 6800.0},
                {"product_name": "PainLess Throat Spray", "rain_regime": "2. Light (0-5 mm)", "active_store_days": 190, "sold_qty": 2600.0, "line_amount": 49000.0, "total_metric": 6800.0},
            ]
        )
    if "group by day_of_week_num, day_of_week, rain_regime" in sql_low:
        return pd.DataFrame(
            [
                {"day_of_week_num": 1, "day_of_week": "Mon", "rain_regime": "1. Dry (0 mm)", "active_store_days": 3100, "sold_qty": 33000.0, "line_amount": 630000.0, "qty_per_store_day": 10.65, "rev_per_store_day": 203.2},
                {"day_of_week_num": 7, "day_of_week": "Sun", "rain_regime": "1. Dry (0 mm)", "active_store_days": 2500, "sold_qty": 25000.0, "line_amount": 480000.0, "qty_per_store_day": 10.0, "rev_per_store_day": 192.0},
            ]
        )
    if "avg(latitude)" in sql_low:
        return pd.DataFrame(
            [
                {"country_code": "DE", "sold_qty": 75000.0, "line_amount": 1500000.0, "margin_amount": 420000.0, "weighted_margin_pct": 28.0, "store_count": 18, "active_store_days": 6500, "lat": 51.1, "lon": 10.4},
                {"country_code": "FR", "sold_qty": 71000.0, "line_amount": 1400000.0, "margin_amount": 395000.0, "weighted_margin_pct": 28.21, "store_count": 16, "active_store_days": 6200, "lat": 46.2, "lon": 2.2},
            ]
        )
    if "group by month_num, country_code" in sql_low:
        return pd.DataFrame(
            [{"month_num": 1, "country_code": "DE", "sold_qty": 6527.0}, {"month_num": 1, "country_code": "FR", "sold_qty": 6331.0}]
        )
    if "group by coalesce(has_promotion, false)" in sql_low:
        return pd.DataFrame(
            [
                {"has_promotion": True, "mart_rows": 7419, "line_count": 7419, "sold_qty": 52107.0, "promo_sold_qty": 52107.0, "line_amount": 909973.33, "margin_amount": 181275.75, "weighted_margin_pct": 19.92, "weighted_unit_price": 17.46, "avg_row_promo_share": 1.0},
                {"has_promotion": False, "mart_rows": 54617, "line_count": 54617, "sold_qty": 392971.0, "promo_sold_qty": 0.0, "line_amount": 7709434.30, "margin_amount": 2235562.83, "weighted_margin_pct": 29.00, "weighted_unit_price": 19.62, "avg_row_promo_share": 0.0},
            ]
        )
    if "group by brand_name\n" in sql_low and "weighted_margin_pct" in sql_low:
        return pd.DataFrame(
            [{"brand_name": "PainLess", "line_amount": 700000.0, "margin_amount": 200000.0, "weighted_margin_pct": 28.57, "row_avg_margin_pct": 28.9, "sold_qty": 34000.0}]
        )
    if "group by store_code, store_name, country_code, source" in sql_low:
        return pd.DataFrame(
            [{"store_code": "ONYX:PH0120", "store_name": "Naples HealthPoint #120", "country_code": "IT", "source": "SIMULATED_ONYX_DAILY_FACT_TO_POS", "sold_qty": 4592.0, "line_count": 659, "active_store_days": 659, "line_amount": 83794.15 if track_mode != "serbia" else None, "margin_amount": 23557.29 if track_mode == "onyx" else None, "weighted_margin_pct": 28.11 if track_mode == "onyx" else None, "row_avg_margin_pct": 28.11 if track_mode == "onyx" else None}]
        )
    if "group by store_code, store_name, country_code\n" in sql_low:
        return pd.DataFrame(
            [
                {"store_code": "ONYX:PH0120", "store_name": "Naples HealthPoint #120", "country_code": "IT", "line_amount": 83794.15, "margin_amount": 23557.29, "weighted_margin_pct": 28.11, "row_avg_margin_pct": 28.11, "sold_qty": 4592.0, "line_count": 659, "active_store_days": 659},
                {"store_code": "ONYX:PH0014", "store_name": "Berlin HealthPoint #014", "country_code": "DE", "line_amount": 95100.00, "margin_amount": 27674.10, "weighted_margin_pct": 29.10, "row_avg_margin_pct": 29.10, "sold_qty": 5100.0, "line_count": 720, "active_store_days": 720},
            ]
        )
    if "group by product_name, clean_uom, dataset_track" in sql_low:
        return pd.DataFrame(
            [{"product_name": "AntiBioX Antibiotic 10 mg", "clean_uom": "ONYX_UNIT", "dataset_track": "ONYX_EU_SYNTHETIC", "line_count": 300, "active_store_days": 280, "sold_qty": 1336.0, "line_amount": 65720.97 if track_mode != "serbia" else None, "weighted_unit_price": 49.19 if track_mode != "serbia" else None, "weighted_margin_pct": 23.33 if track_mode == "onyx" else None}]
        )
    if "group by brand_name, product_name, clean_uom" in sql_low:
        return pd.DataFrame(
            [{"brand_name": "PainLess", "product_name": "PainLess Throat Spray", "clean_uom": "ONYX_UNIT", "sold_qty": 6800.0, "line_amount": 120000.0}]
        )
    if "width_bucket" in sql_low:
        return pd.DataFrame(
            [{"dataset_track": "ONYX_EU_SYNTHETIC", "bucket_id": 1, "obs_count": 5635, "bin_start": 1.33, "bin_end": 6.27}]
        )
    if "as month_cat_rows" in sql_low:
        return pd.DataFrame(
            [{"min_ym": dt.date(2014, 1, 1), "max_ym": dt.date(2019, 10, 1), "countries": "RS", "provenance_class": "OBSERVED", "source": "PHARMA_SALES_DAILY_ATC", "month_cat_rows": 560}]
        )
    if "group by year_month, category_code, category_name" in sql_low:
        return pd.DataFrame(
            [{"year_month": dt.date(2014, 1, 1), "category_code": "N02BE", "category_name": "Anilides", "total_observed_qty": 950.0}]
        )
    if "group by month_num, category_code, category_name" in sql_low:
        return pd.DataFrame(
            [{"month_num": 1, "category_code": "N02BE", "category_name": "Anilides", "total_observed_qty": 7632.89}]
        )
    if "group by manufacturer_name" in sql_low:
        return pd.DataFrame(
            [{"manufacturer_name": "Zenith", "line_amount": 817422019.0, "sold_qty": 469644.0, "line_count": 46214, "active_store_days": 1050}]
        )
    if "group by category_code, category_name" in sql_low:
        return pd.DataFrame(
            [{"category_code": "N02BE", "category_name": "Anilides", "total_observed_qty": 63005.4, "avg_daily_qty": 30.01, "observation_count": 2106}]
        )
    raise AssertionError(f"Unmocked SQL pattern: {sql}")


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
