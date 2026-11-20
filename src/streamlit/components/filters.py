"""Shared sidebar filters, palette selector, comparison selector, and isolated page state."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from analytics import COMPARE_MODE_LABELS, COMPARE_MODE_ORDER, evaluate_uom_compatibility
from config import (
    DEFAULT_PALETTE_KEY,
    DEFAULT_TRACK,
    PALETTES,
    TEMP_BAND_ORDER,
    TRACK_META,
    country_label,
    temp_label,
    track_label,
)
import db
from queries import FilterState, sql_available_tracks, sql_filter_options, sql_release_state
from ui import get_active_palette, inject_theme_css

_PAGE_LOCAL_KEYS: tuple[str, ...] = (
    "p2_rain_regimes",
    "p2_humidity_bands",
    "p2_cell_temp",
    "p2_cell_rain",
    "p2_metric_mode",
    "p2_weather_line",
    "p2_daily_store_uom",
    "p3_store_search",
    "p4_product_search",
    "p4_atc_apply_date",
    "p1_summary_all_tracks",
    "p1_trend_metric",
    "p1_driver_dim",
    "p1_show_series_ref",
)


def _ensure_defaults() -> None:
    st.session_state.setdefault("palette_key", DEFAULT_PALETTE_KEY)
    st.session_state.setdefault("f_track", DEFAULT_TRACK)
    st.session_state.setdefault("f_countries", [])
    st.session_state.setdefault("f_stores", [])
    st.session_state.setdefault("f_uoms", [])
    st.session_state.setdefault("f_temp_bands", [])
    st.session_state.setdefault("f_compare_mode", COMPARE_MODE_ORDER[0])


def reset_all_filters() -> None:
    """Clear every global and page-local filter key cleanly."""
    st.session_state["f_track"] = DEFAULT_TRACK
    st.session_state["f_countries"] = []
    st.session_state["f_stores"] = []
    st.session_state["f_uoms"] = []
    st.session_state["f_temp_bands"] = []
    st.session_state["f_compare_mode"] = COMPARE_MODE_ORDER[0]
    st.session_state.pop("f_date_range", None)
    st.session_state.pop("f_track_prev", None)
    st.session_state.pop("_track_bounds", None)
    for key in _PAGE_LOCAL_KEYS:
        st.session_state.pop(key, None)


def set_global_uoms(uoms: list[str]) -> None:
    """Callback helper for 1-click single-UOM selection buttons across pages."""
    st.session_state["f_uoms"] = list(uoms)


def _prune_selection(state_key: str, valid_options: list[str]) -> list[str]:
    valid_set = set(valid_options)
    current = list(st.session_state.get(state_key, []))
    pruned = [v for v in current if v in valid_set]
    if pruned != current:
        st.session_state[state_key] = pruned
    return pruned


def get_track_bounds() -> dict[str, Any]:
    return dict(st.session_state.get("_track_bounds") or {})


def render_sidebar_and_get_filters() -> FilterState:
    """Render shared sidebar palette switcher + cascading global filters."""
    _ensure_defaults()

    try:
        schema = db.get_active_schema()
        release_sql, release_params = sql_release_state(schema)
        release_df = db.run_query_df(release_sql, release_params)
        tracks_sql, tracks_params = sql_available_tracks(schema)
        tracks_df = db.run_query_df(tracks_sql, tracks_params)
    except db.MissingDatabaseConfigError as exc:
        inject_theme_css(get_active_palette())
        st.error(str(exc))
        st.stop()
    except Exception as exc:
        inject_theme_css(get_active_palette())
        st.error(
            f"Không thể kết nối Neon BI Mirror ({type(exc).__name__}). "
            "Hãy kiểm tra cấu hình mạng và `QUICK_NEON_DATABASE_URL`."
        )
        st.stop()

    palette_keys = list(PALETTES.keys())
    with st.sidebar:
        release_text = "Chưa có bản ghi release"
        if not release_df.empty:
            row = release_df.iloc[0]
            ts = row.get("synced_at_utc")
            ts_str = ts.strftime("%d/%m/%Y %H:%M UTC") if hasattr(ts, "strftime") else str(ts or "")
            release_text = f"Release: {row.get('release_id', '—')} · {ts_str}"

        st.markdown(
            f"""
            <div class="pf-sidebar-brand">
              <div class="pf-sidebar-title">💊 PharmaFlow BI</div>
              <div class="pf-sidebar-meta">Bán lẻ Dược phẩm & Thời tiết · Sales MD-01</div>
              <div class="pf-sidebar-meta">{release_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        selected_palette_key = st.selectbox(
            "Bảng màu giao diện",
            options=palette_keys,
            format_func=lambda k: PALETTES[k].label,
            key="palette_key",
        )
        palette = PALETTES[selected_palette_key]

        st.divider()
        st.markdown("#### Bộ lọc toàn cục")

        raw_tracks = (
            tracks_df["dataset_track"].dropna().tolist()
            if not tracks_df.empty
            else list(TRACK_META.keys())
        )
        preferred_order = list(TRACK_META.keys())
        track_options = [t for t in preferred_order if t in raw_tracks] + [
            t for t in raw_tracks if t not in preferred_order
        ]
        if st.session_state["f_track"] not in track_options and track_options:
            st.session_state["f_track"] = track_options[0]

        selected_track = st.selectbox(
            "Nhóm dữ liệu",
            options=track_options,
            format_func=track_label,
            key="f_track",
            help="Luôn tách nguồn dữ liệu để không cộng gộp EUR với IDR, hay OBSERVED với SYNTHETIC.",
        )

        prev_track = st.session_state.get("f_track_prev")
        track_switched = prev_track is not None and prev_track != selected_track
        if track_switched:
            st.session_state["f_countries"] = []
            st.session_state["f_stores"] = []
            st.session_state["f_uoms"] = []
            st.session_state["f_temp_bands"] = []
            for key in _PAGE_LOCAL_KEYS:
                st.session_state.pop(key, None)

        pre_countries = () if track_switched else tuple(st.session_state.get("f_countries", ()))
        opts_sql, opts_params = sql_filter_options(schema, selected_track, pre_countries)
        opts_df = db.run_query_df(opts_sql, opts_params)

        countries_avail: list[str] = []
        uoms_avail: list[str] = []
        stores_avail: list[str] = []
        min_date = date(2014, 1, 1)
        max_date = date(2025, 12, 31)

        if not opts_df.empty:
            opt_row = opts_df.iloc[0]
            if opt_row.get("min_date") is not None:
                min_date = opt_row["min_date"]
            if opt_row.get("max_date") is not None:
                max_date = opt_row["max_date"]
            countries_avail = list(opt_row.get("countries") or [])
            uoms_avail = list(opt_row.get("uoms") or [])
            stores_avail = list(opt_row.get("stores") or [])

        if track_switched:
            st.session_state["f_date_range"] = (min_date, max_date)
        st.session_state["f_track_prev"] = selected_track

        _prune_selection("f_countries", countries_avail)
        _prune_selection("f_uoms", uoms_avail)
        _prune_selection("f_stores", stores_avail)

        cur_date_range = st.session_state.get("f_date_range")
        if (
            not isinstance(cur_date_range, (tuple, list))
            or len(cur_date_range) != 2
            or cur_date_range[0] < min_date
            or cur_date_range[1] > max_date
        ):
            st.session_state["f_date_range"] = (min_date, max_date)

        selected_countries = st.multiselect(
            "Quốc gia",
            options=countries_avail,
            format_func=country_label,
            placeholder="Tất cả quốc gia",
            key="f_countries",
        )
        selected_stores = st.multiselect(
            "Cửa hàng",
            options=stores_avail,
            placeholder="Tất cả cửa hàng",
            key="f_stores",
        )
        selected_uoms = st.multiselect(
            "Đơn vị tính (ĐVT)",
            options=uoms_avail,
            placeholder="Tất cả đơn vị",
            key="f_uoms",
        )

        uom_guard = evaluate_uom_compatibility(selected_track, selected_uoms, uoms_avail)
        if uom_guard.is_multi_uom_blocked:
            st.warning(
                f"Nguồn đang có **{uom_guard.uom_count} ĐVT** và thiếu hệ số quy đổi `base_qty`. "
                "Chọn **1 ĐVT** (như `tab`, `pcs`, `fls`) để mở khóa so sánh sản lượng & đơn giá.",
                icon="⚠️",
            )

        date_val = st.date_input(
            "Khoảng ngày bán",
            min_value=min_date,
            max_value=max_date,
            format="YYYY/MM/DD",
            key="f_date_range",
        )
        if isinstance(date_val, (tuple, list)) and len(date_val) == 2:
            date_start, date_end = date_val[0], date_val[1]
        else:
            date_start, date_end = date_val, date_val

        selected_temps = st.multiselect(
            "Mức nhiệt độ",
            options=[b for b in TEMP_BAND_ORDER if b != "Unknown"],
            format_func=temp_label,
            placeholder="Tất cả mức nhiệt độ",
            key="f_temp_bands",
        )

        compare_mode = st.selectbox(
            "Kỳ so sánh biến động",
            options=list(COMPARE_MODE_ORDER),
            format_func=lambda k: COMPARE_MODE_LABELS.get(k, k),
            key="f_compare_mode",
            help="Tự động bỏ qua tháng chưa đủ ngày để tránh so sánh lệch kỳ.",
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            st.button("Đặt lại bộ lọc", width="stretch", on_click=reset_all_filters)
        with col_btn2:
            if st.button("Làm mới cache", width="stretch"):
                db.run_query_df.clear()
                st.rerun()

    st.session_state["_track_bounds"] = {
        "min_date": min_date,
        "max_date": max_date,
        "uoms_avail": tuple(uoms_avail),
        "countries_avail": tuple(countries_avail),
        "stores_avail": tuple(stores_avail),
    }

    inject_theme_css(palette)

    return FilterState(
        dataset_track=selected_track,
        countries=tuple(selected_countries),
        stores=tuple(selected_stores),
        clean_uoms=tuple(selected_uoms),
        date_start=date_start,
        date_end=date_end,
        temp_bands=tuple(selected_temps),
        compare_mode=str(compare_mode),
    )


def get_current_filters() -> FilterState:
    """Reuse FilterState rendered in app.py shell, or render sidebar directly when page runs standalone."""
    active = st.session_state.get("_active_filters")
    if isinstance(active, FilterState):
        return active
    return render_sidebar_and_get_filters()
