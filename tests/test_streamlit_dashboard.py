"""Automated unit and Streamlit AppTest smoke checks for BTL_BI/src/streamlit."""

from __future__ import annotations

import datetime as dt
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

import config  # noqa: E402
import db  # noqa: E402
import queries  # noqa: E402
import ui  # noqa: E402


# ---------------------------------------------------------------------------
# 1. SQL Builder & PharmaFlow Invariants
# ---------------------------------------------------------------------------

def test_validate_schema_accepts_valid_and_rejects_injection() -> None:
    assert queries.validate_schema("quick_gold_md01") == "quick_gold_md01"
    for bad in ("", "quick; DROP TABLE x", "bad-schema", "1starts_digit", 'foo"bar'):
        with pytest.raises(ValueError):
            queries.validate_schema(bad)


def test_build_where_clause_parameterized_and_override_safe() -> None:
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
    where_sql, params = queries.build_where_clause(f)
    assert "dataset_track = %s" in where_sql
    assert "country_code = ANY(%s)" in where_sql
    assert "store_name = ANY(%s)" in where_sql
    assert "clean_uom = ANY(%s)" in where_sql
    assert "local_date >= %s" in where_sql
    assert "local_date <= %s" in where_sql
    assert params[0] == "ONYX_EU_SYNTHETIC"
    assert params[1] == ["DE", "FR"]

    # When overriding track (e.g. IRPD manufacturers), EU country/store filters must NOT leak in
    ov_sql, ov_params = queries.build_where_clause(f, override_track="IRPD_ID_OBSERVED")
    assert ov_params[0] == "IRPD_ID_OBSERVED"
    assert "country_code = ANY" not in ov_sql
    assert "store_name = ANY" not in ov_sql

    # Ignoring weather cell keeps base grid intact
    hm_sql, _ = queries.build_where_clause(f, ignore_weather_cell=True)
    assert hm_sql.count("temp_band") == 1


def test_monthly_trend_enforces_month_granularity_and_avg_pct() -> None:
    f = queries.FilterState(dataset_track="ONYX_EU_SYNTHETIC", countries=("DE",))
    sql, params = queries.sql_monthly_trend_kpi("quick_gold_md01", f, scope_to_track=True)
    assert "period_granularity = 'MONTH'" in sql
    assert "AVG(sold_qty_pct_change)" in sql
    assert "SUM(sold_qty_pct_change)" not in sql
    assert "SIMULATED_ONYX_DAILY_FACT_TO_POS" in params
    assert ["DE"] in params


def test_weather_kpis_computes_per_store_average() -> None:
    sql, _ = queries.sql_weather_kpis("quick_gold_md01", queries.FilterState())
    assert "COUNT(DISTINCT store_id)" in sql
    assert "SUM(sold_qty) / NULLIF(COUNT(DISTINCT store_id), 0)" in sql


def test_eu_locked_and_irpd_locked_queries_enforce_tracks() -> None:
    f = queries.FilterState(dataset_track="SERBIA_RS_SYNTHETIC", countries=("RS",))
    for builder in (
        queries.sql_eu_country_summary,
        queries.sql_eu_country_month_heatmap,
        queries.sql_eu_promo_gauge,
        queries.sql_eu_brand_margin_and_profit,
        queries.sql_eu_store_matrix,
    ):
        sql, params = builder("quick_gold_md01", f)
        assert "dataset_track = %s" in sql
        assert params[0] == "ONYX_EU_SYNTHETIC"

    mfg_sql, mfg_params = queries.sql_irpd_top_manufacturers("quick_gold_md01", f)
    assert "manufacturer_name IS NOT NULL" in mfg_sql
    assert mfg_params[0] == "IRPD_ID_OBSERVED"


def test_product_detail_groups_by_uom_and_track() -> None:
    sql, params = queries.sql_product_detail_table("quick_gold_md01", queries.FilterState(), search_text="PainLess")
    assert "GROUP BY product_name, clean_uom, dataset_track" in sql
    assert "COUNT(clean_uom)" not in sql
    assert "%PainLess%" in params


def test_unit_price_histogram_uses_safe_width_bucket() -> None:
    sql, params = queries.sql_unit_price_distribution("quick_gold_md01", queries.FilterState(), bins=24)
    assert "WIDTH_BUCKET" in sql
    assert "LEAST(" in sql
    assert "GREATEST(" in sql
    assert params[-4:] == (24, 24, 24, 24)


# ---------------------------------------------------------------------------
# 2. Config Palettes, Localization Maps & Formatters
# ---------------------------------------------------------------------------

def test_palettes_and_vietnamese_dictionaries_complete() -> None:
    assert {"pharmaflow", "aws_quick", "ocean", "warm"}.issubset(config.PALETTES.keys())
    for k, pal in config.PALETTES.items():
        assert pal.primary.startswith("#")
        assert len(pal.continuous_scale) >= 3
        assert len(pal.discrete) >= 6, k

    for key in config.TEMP_BAND_ORDER:
        assert key in config.TEMP_BAND_VI
    for key in config.RAIN_REGIME_ORDER:
        assert key in config.RAIN_REGIME_VI
    for key in config.HUMIDITY_BAND_ORDER:
        assert key in config.HUMIDITY_BAND_VI
    assert set(config.DOW_VI_BY_NUM.keys()) == {1, 2, 3, 4, 5, 6, 7}
    assert set(config.ISO2_TO_ISO3.keys()) == {"DE", "FR", "IT", "BE", "PL", "NL", "ES", "AT", "ID", "RS"}
    assert len(config.ATC_CODE_VI) == 8


def test_formatters_never_prepend_dollar_for_eur_or_idr() -> None:
    eur = config.fmt_currency(8_619_407.63, "EUR")
    assert "$" not in eur
    assert "8.62M EUR" == eur

    idr = config.fmt_currency(690_000_000, "IDR")
    assert "$" not in idr
    assert "690.00M IDR" == idr

    assert config.fmt_pct(0.287429) == "28.74%"
    assert config.fmt_pct(11.707, already_scaled=True) == "11.71%"


# ---------------------------------------------------------------------------
# 3. Mocked End-to-End Streamlit AppTest Smoke Rendering (All 4 Pages)
# ---------------------------------------------------------------------------

def _mock_query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
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
        return pd.DataFrame(
            [
                {"dataset_track": "IRPD_ID_OBSERVED", "currency_code": "IDR", "provenance_class": "OBSERVED", "row_count": 387021},
                {"dataset_track": "ONYX_EU_SYNTHETIC", "currency_code": "EUR", "provenance_class": "SYNTHETIC", "row_count": 62036},
                {"dataset_track": "SERBIA_RS_SYNTHETIC", "currency_code": None, "provenance_class": "SYNTHETIC", "row_count": 25534},
            ]
        )
    if "array_remove(array_agg(distinct country_code" in sql_low:
        return pd.DataFrame(
            [{
                "min_date": dt.date(2024, 1, 1),
                "max_date": dt.date(2025, 12, 31),
                "countries": ["DE", "FR", "IT"],
                "uoms": ["ONYX_UNIT"],
                "stores": ["Berlin HealthPoint #014", "Paris HealthPoint #013"],
            }]
        )
    if "weighted_margin_pct" in sql_low:
        return pd.DataFrame(
            [{
                "total_revenue": 8619407.63,
                "total_sold_qty": 445078.0,
                "total_orders": 62036,
                "total_margin": 2416838.58,
                "avg_margin_pct": 0.287429,
                "weighted_margin_pct": 0.280395,
                "avg_unit_price": 24.96,
                "currency_code": "EUR",
                "provenance_class": "SYNTHETIC",
                "margin_rows": 62036,
                "row_count": 62036,
            }]
        )
    if "kpi_sales_trend" in sql_low:
        return pd.DataFrame(
            [
                {"period_start": dt.date(2024, 1, 1), "sold_qty": 18000.0, "avg_pct_change": 0.05, "order_count": 2500},
                {"period_start": dt.date(2024, 2, 1), "sold_qty": 19500.0, "avg_pct_change": 0.08, "order_count": 2600},
            ]
        )
    if "group by country_code\n" in sql_low and "lat" not in sql_low:
        return pd.DataFrame(
            [
                {"country_code": "DE", "sold_qty": 75000.0, "line_amount": 1500000.0, "order_count": 10000},
                {"country_code": "FR", "sold_qty": 71000.0, "line_amount": 1400000.0, "order_count": 9500},
            ]
        )
    if "group by brand_name\n" in sql_low and "margin_amount" in sql_low and "avg_margin_pct" not in sql_low:
        return pd.DataFrame(
            [
                {"brand_name": "PainLess", "sold_qty": 34000.0, "line_amount": 700000.0, "margin_amount": 190000.0},
                {"brand_name": "Medica", "sold_qty": 33000.0, "line_amount": 680000.0, "margin_amount": 185000.0},
            ]
        )
    if "coalesce(currency_code, 'n/a')" in sql_low:
        return pd.DataFrame(
            [
                {"dataset_track": "ONYX_EU_SYNTHETIC", "currency_code": "EUR", "provenance_class": "SYNTHETIC", "sold_qty": 445078.0, "order_count": 62036, "line_amount": 8619407.63, "margin_amount": 2416838.58}
            ]
        )
    if "avg_qty_per_store" in sql_low:
        return pd.DataFrame(
            [{
                "active_stores": 120,
                "avg_qty_per_store": 3708.98,
                "avg_temp_mean": 13.47,
                "avg_precip_sum": 2.45,
                "total_sold_qty": 445078.0,
                "total_orders": 62036,
            }]
        )
    if "group by temp_band, rain_regime" in sql_low:
        return pd.DataFrame(
            [
                {"temp_band": "1. Cold (<10C)", "rain_regime": "1. Dry (0 mm)", "sold_qty": 73480.0, "order_count": 9500, "days_count": 90},
                {"temp_band": "2. Cool (10-20C)", "rain_regime": "2. Light (0-5 mm)", "sold_qty": 85882.0, "order_count": 11000, "days_count": 100},
            ]
        )
    if "group by humidity_band, is_weekend" in sql_low:
        return pd.DataFrame(
            [
                {"humidity_band": "2. Normal (60-80%)", "is_weekend": False, "sold_qty": 170970.0, "order_count": 20000},
                {"humidity_band": "2. Normal (60-80%)", "is_weekend": True, "sold_qty": 57060.0, "order_count": 7000},
            ]
        )
    if "group by local_date, rain_regime" in sql_low:
        return pd.DataFrame(
            [{"local_date": dt.date(2024, 5, 1), "rain_regime": "1. Dry (0 mm)", "temp_mean": 16.5, "sold_qty": 620.0, "order_count": 90}]
        )
    if "group by year_month, dataset_track" in sql_low:
        return pd.DataFrame(
            [{"year_month": dt.date(2024, 5, 1), "dataset_track": "ONYX_EU_SYNTHETIC", "sold_qty": 18500.0, "order_count": 2500}]
        )
    if "group by local_date\n" in sql_low or "group by local_date, store_name" in sql_low:
        return pd.DataFrame(
            [{
                "local_date": dt.date(2024, 12, 19),
                "store_name": "Berlin HealthPoint #014",
                "temp_band": "1. Cold (<10C)",
                "rain_regime": "2. Light (0-5 mm)",
                "humidity_band": "2. Normal (60-80%)",
                "is_weekend": False,
                "clean_uom": "ONYX_UNIT",
                "sold_qty": 783.0,
                "order_count": 92,
                "temp_mean": 9.16,
                "precip_sum": 6.43,
                "humidity_mean": 76.17,
                "line_amount": 12949.83,
            }]
        )
    if "with top_products as" in sql_low:
        return pd.DataFrame(
            [
                {"product_name": "PainLess Throat Spray", "rain_regime": "1. Dry (0 mm)", "sold_qty": 3200.0, "total_qty": 6800.0},
                {"product_name": "PainLess Throat Spray", "rain_regime": "2. Light (0-5 mm)", "sold_qty": 2600.0, "total_qty": 6800.0},
            ]
        )
    if "group by day_of_week_num, day_of_week, rain_regime" in sql_low:
        return pd.DataFrame(
            [
                {"day_of_week_num": 1, "day_of_week": "Mon", "rain_regime": "1. Dry (0 mm)", "sold_qty": 33000.0, "order_count": 4200},
                {"day_of_week_num": 7, "day_of_week": "Sun", "rain_regime": "1. Dry (0 mm)", "sold_qty": 25000.0, "order_count": 3200},
            ]
        )
    if "avg(latitude)" in sql_low:
        return pd.DataFrame(
            [
                {"country_code": "DE", "sold_qty": 75000.0, "line_amount": 1500000.0, "margin_amount": 420000.0, "store_count": 18, "lat": 51.1, "lon": 10.4},
                {"country_code": "FR", "sold_qty": 71000.0, "line_amount": 1400000.0, "margin_amount": 395000.0, "store_count": 16, "lat": 46.2, "lon": 2.2},
            ]
        )
    if "group by month_num, country_code" in sql_low:
        return pd.DataFrame(
            [{"month_num": 1, "country_code": "DE", "sold_qty": 6527.0}, {"month_num": 1, "country_code": "FR", "sold_qty": 6331.0}]
        )
    if "group by store_name, country_code, dataset_track" in sql_low:
        return pd.DataFrame(
            [{"store_name": "Madrid HealthPoint #018", "country_code": "ES", "dataset_track": "ONYX_EU_SYNTHETIC", "sold_qty": 7430.0, "line_amount": 145000.0, "order_count": 1050}]
        )
    if "weighted_promo_pct" in sql_low:
        return pd.DataFrame([{"avg_promo_pct": 11.96, "weighted_promo_pct": 11.71}])
    if "group by brand_name\n" in sql_low and "avg_margin_pct" in sql_low:
        return pd.DataFrame(
            [{"brand_name": "PainLess", "line_amount": 700000.0, "margin_amount": 200000.0, "avg_margin_pct": 28.9, "sold_qty": 34000.0}]
        )
    if "group by store_code, store_name, country_code, source" in sql_low:
        return pd.DataFrame(
            [{"store_code": "ONYX:PH0120", "store_name": "Naples HealthPoint #120", "country_code": "IT", "source": "SIMULATED_ONYX_DAILY_FACT_TO_POS", "sold_qty": 4592.0, "order_count": 659, "line_amount": 83794.15, "margin_amount": 23557.29, "avg_margin_pct": 28.11}]
        )
    if "group by store_code, store_name, country_code\n" in sql_low:
        return pd.DataFrame(
            [
                {"store_code": "ONYX:PH0120", "store_name": "Naples HealthPoint #120", "country_code": "IT", "line_amount": 83794.15, "avg_margin_pct": 28.11, "sold_qty": 4592.0, "order_count": 659},
                {"store_code": "ONYX:PH0014", "store_name": "Berlin HealthPoint #014", "country_code": "DE", "line_amount": 95100.00, "avg_margin_pct": 29.10, "sold_qty": 5100.0, "order_count": 720},
            ]
        )
    if "group by product_name, clean_uom, dataset_track" in sql_low:
        return pd.DataFrame(
            [{"product_name": "AntiBioX Antibiotic 10 mg", "clean_uom": "ONYX_UNIT", "dataset_track": "ONYX_EU_SYNTHETIC", "sold_qty": 1336.0, "line_amount": 65720.97, "avg_unit_price": 49.12, "avg_margin_pct": 23.33}]
        )
    if "group by brand_name, product_name" in sql_low:
        return pd.DataFrame(
            [{"brand_name": "PainLess", "product_name": "PainLess Throat Spray", "sold_qty": 6800.0, "line_amount": 120000.0}]
        )
    if "width_bucket" in sql_low:
        return pd.DataFrame(
            [{"dataset_track": "ONYX_EU_SYNTHETIC", "bucket_id": 1, "obs_count": 5635, "bin_start": 1.33, "bin_end": 6.27}]
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
            [{"manufacturer_name": "Zenith", "line_amount": 817422019.0, "sold_qty": 469644.0, "order_count": 46214}]
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
def test_pages_render_without_exception_under_mocked_db(page_rel: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()

    with patch("db.run_query_df", side_effect=_mock_query_df):
        at = AppTest.from_file(str(STREAMLIT_DIR / page_rel), default_timeout=20)
        at.run()
        assert not at.exception, f"Exception on {page_rel}: {[e.value for e in at.exception]}"
        assert not at.error, f"Error widget on {page_rel}: {[e.value for e in at.error]}"


def test_safe_round_handles_object_none_columns() -> None:
    all_none = pd.Series([None, None], dtype=object)
    rounded = config.safe_round(all_none, 2)
    assert rounded.isna().all()

    mixed = pd.Series([None, 12.3456], dtype=object)
    rounded_mixed = config.safe_round(mixed, 2)
    assert pd.isna(rounded_mixed.iloc[0])
    assert rounded_mixed.iloc[1] == pytest.approx(12.35)


def test_polish_horizontal_bar_orders_highest_at_top_and_pads_x() -> None:
    df = pd.DataFrame({"name": ["Top1", "Mid2", "Low3"], "val": [34000.0, 20000.0, 5000.0]})
    fig = px.bar(df, x="val", y="name", orientation="h")
    ui.polish_horizontal_bar(fig, ["Top1", "Mid2", "Low3"], 34000.0)
    yaxis = fig.to_dict()["layout"]["yaxis"]
    xaxis = fig.to_dict()["layout"]["xaxis"]
    assert yaxis["categoryorder"] == "array"
    # In Plotly unreversed horizontal bars, last element in categoryarray appears at the TOP
    assert yaxis["categoryarray"] == ["Low3", "Mid2", "Top1"]
    assert xaxis["range"][1] > 34000.0


def test_pharmaflow_first_four_discrete_colors_distinct() -> None:
    first_four = config.PALETTES["pharmaflow"].discrete[:4]
    assert len(set(first_four)) == 4


def _mock_query_df_null_financials(sql: str, params: tuple = ()) -> pd.DataFrame:
    df = _mock_query_df(sql, params)
    sql_low = sql.lower()
    if "coalesce(currency_code, 'n/a')" in sql_low:
        return pd.DataFrame(
            [{"dataset_track": "IRPD_ID_OBSERVED", "currency_code": "IDR", "provenance_class": "OBSERVED", "sold_qty": 3630000.0, "order_count": 274480, "line_amount": 3990000000.0, "margin_amount": None}]
        )
    if "group by product_name, clean_uom, dataset_track" in sql_low:
        return pd.DataFrame(
            [{"product_name": "Paracetamol 500mg", "clean_uom": "tab", "dataset_track": "SERBIA_RS_SYNTHETIC", "sold_qty": 5000.0, "line_amount": None, "avg_unit_price": None, "avg_margin_pct": None}]
        )
    if "group by store_code, store_name, country_code, source" in sql_low:
        return pd.DataFrame(
            [{"store_code": "SIM_RS_001", "store_name": "Neven Farma", "country_code": "RS", "source": "SIMULATED_PHARMA_SALES_ATC_SCALE10", "sold_qty": 1275900.0, "order_count": 25534, "line_amount": None, "margin_amount": None, "avg_margin_pct": None}]
        )
    if "group by local_date\n" in sql_low:
        return pd.DataFrame(
            [{"local_date": dt.date(2018, 1, 5), "sold_qty": 200.0, "order_count": 10, "temp_mean": None, "precip_sum": None, "humidity_mean": None, "line_amount": None}]
        )
    return df


@pytest.mark.parametrize(
    "page_rel",
    [
        "pages/01_tong_quan.py",
        "pages/02_thoi_tiet_dia_diem.py",
        "pages/03_cua_hang_loi_nhuan.py",
        "pages/04_san_pham_atc.py",
    ],
)
def test_pages_handle_all_none_financial_and_weather_columns(page_rel: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()

    with patch("db.run_query_df", side_effect=_mock_query_df_null_financials):
        at = AppTest.from_file(str(STREAMLIT_DIR / page_rel), default_timeout=20)
        at.run()
        assert not at.exception, f"NoneType crash on {page_rel}: {[e.value for e in at.exception]}"


def test_app_navigation_entrypoint_renders_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUICK_NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
    monkeypatch.setenv("QUICK_NEON_SCHEMA", "quick_gold_md01")
    db.get_db_settings.cache_clear()

    with patch("db.run_query_df", side_effect=_mock_query_df):
        at = AppTest.from_file(str(STREAMLIT_DIR / "app.py"), default_timeout=20)
        at.run()
        assert not at.exception, f"Exception on app.py: {[e.value for e in at.exception]}"
        assert not at.error
