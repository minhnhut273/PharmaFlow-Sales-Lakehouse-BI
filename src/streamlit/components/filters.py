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
    TIME_GRAIN_ORDER,
    TRACK_META,
    country_label,
    temp_label,
    time_grain_label,
    track_label,
    vnd_rate_note,
)
import db
from queries import FilterState, sql_available_tracks, sql_filter_options, sql_release_state
from ui import get_active_palette, inject_theme_css

_PAGE_LOCAL_KEYS: tuple[str, ...] = (
    "p1_summary_all_tracks",
    "p1_trend_metric",
    "p1_driver_dim",
    "p1_show_series_ref",
    "p1_mix_metric",
    "p1_mix_top_n",
    "p1_mix_search",
    "p1_selected_products",
    "p1_series_metric",
    "p1_series_ma",
    "p2_temp_bands",
    "p2_rain_regimes",
    "p2_humidity_bands",
    "p2_cell_temp",
    "p2_cell_rain",
    "p2_metric_mode",
    "p2_weather_line",
    "p2_daily_store_uom",
    "p2_selected_products",
    "p2_series_grain",
    "p3_store_search",
    "p3_map_mode",
    "p3_map_engine",
    "p3_map_size",
    "p3_map_color",
    "p3_map_clusters",
    "p4_product_search",
    "p4_atc_apply_date",
    "p4_from_jump",
    "p5_atc",
    "p5_horizon",
    "p5_show_cqr",
    "p5_compare_weekly",
    "p5_compare_daily",
    "ui_info_drawer_open",
    "_page_info_panel",
)


def _ensure_defaults() -> None:
    st.session_state.setdefault("palette_key", DEFAULT_PALETTE_KEY)
    st.session_state.setdefault("f_track", DEFAULT_TRACK)
    st.session_state.setdefault("f_countries", [])
    st.session_state.setdefault("f_city_clusters", [])
    st.session_state.setdefault("f_stores", [])
    st.session_state.setdefault("f_uoms", [])
    st.session_state.setdefault("f_temp_bands", [])
    st.session_state.setdefault("f_compare_mode", COMPARE_MODE_ORDER[0])
    st.session_state.setdefault("f_time_grain", "month")
    st.session_state.setdefault("f_display_vnd", False)


def reset_all_filters() -> None:
    """Clear every global and page-local filter key cleanly."""
    st.session_state["f_track"] = DEFAULT_TRACK
    st.session_state["f_countries"] = []
    st.session_state["f_city_clusters"] = []
    st.session_state["f_stores"] = []
    st.session_state["f_uoms"] = []
    st.session_state["f_temp_bands"] = []
    st.session_state["f_compare_mode"] = COMPARE_MODE_ORDER[0]
    st.session_state["f_time_grain"] = "month"
    st.session_state["f_display_vnd"] = False
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
            f"Không thể kết nối cơ sở dữ liệu BI ({type(exc).__name__}). "
            "Hãy kiểm tra cấu hình mạng và `QUICK_NEON_DATABASE_URL`."
        )
        st.stop()

    palette_keys = list(PALETTES.keys())
    with st.sidebar:
        release_text = "Chưa ghi nhận bản cập nhật dữ liệu"
        if not release_df.empty:
            row = release_df.iloc[0]
            ts = row.get("synced_at_utc")
            ts_str = ts.strftime("%d/%m/%Y %H:%M UTC") if hasattr(ts, "strftime") else str(ts or "")
            release_text = f"Cập nhật: {row.get('release_id', '—')} · {ts_str}"

        st.markdown(
            f"""
            <div class="pf-sidebar-brand">
              <div class="pf-sidebar-title">💊 PharmaFlow BI</div>
              <div class="pf-sidebar-meta">{release_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        selected_palette_key = st.session_state.get("palette_key", DEFAULT_PALETTE_KEY)
        if selected_palette_key not in PALETTES:
            selected_palette_key = DEFAULT_PALETTE_KEY

        st.markdown("#### Bộ lọc")

        raw_tracks = (
            tracks_df["dataset_track"].dropna().tolist()
            if not tracks_df.empty
            else list(TRACK_META.keys())
        )
        preferred_order = list(TRACK_META.keys())
        track_options = [t for t in preferred_order if t in raw_tracks] + [
            t for t in raw_tracks if t not in preferred_order
        ]

        # Automatically resolve dataset track from active Country / Cluster / Store / UOM filters
        cur_countries = tuple(st.session_state.get("f_countries", ()))
        cur_clusters = tuple(st.session_state.get("f_city_clusters", ()))
        cur_stores = tuple(st.session_state.get("f_stores", ()))
        cur_uoms = tuple(st.session_state.get("f_uoms", ()))
        place_text = " ".join(str(x) for x in (*cur_clusters, *cur_stores)).lower()

        from_filter = True
        if (
            "ID" in cur_countries
            or any(kw in place_text for kw in ("irpd", "apotek", "k24"))
            or any(str(u) not in ("ONYX_UNIT", "ATC_DEFINED_DAILY_DOSE_X10") for u in cur_uoms)
        ):
            selected_track = "IRPD_ID_OBSERVED"
        elif (
            "RS" in cur_countries
            or "belgrade" in place_text
            or "ATC_DEFINED_DAILY_DOSE_X10" in cur_uoms
        ):
            selected_track = "SERBIA_RS_SYNTHETIC"
        elif cur_countries or "healthpoint" in place_text or "ONYX_UNIT" in cur_uoms or cur_clusters or cur_stores:
            selected_track = "ONYX_EU_SYNTHETIC"
        else:
            from_filter = False
            explicit_track = st.session_state.get("f_track")
            prev_track_val = st.session_state.get("f_track_prev")
            if (
                explicit_track in track_options
                and (prev_track_val is None or not st.session_state.get("_track_from_filter", False))
            ):
                selected_track = str(explicit_track)
            else:
                selected_track = track_options[0] if track_options else DEFAULT_TRACK

        if selected_track not in track_options and track_options:
            selected_track = track_options[0]
        st.session_state["f_track"] = selected_track
        st.session_state["_track_from_filter"] = from_filter

        prev_track = st.session_state.get("f_track_prev")
        track_switched = prev_track is not None and prev_track != selected_track
        if track_switched:
            for key in _PAGE_LOCAL_KEYS:
                st.session_state.pop(key, None)

        opts_sql, opts_params = sql_filter_options(schema, selected_track, cur_countries, cur_clusters)
        opts_df = db.run_query_df(opts_sql, opts_params)

        countries_avail: list[str] = []
        clusters_avail: list[str] = []
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
            clusters_avail = list(opt_row.get("clusters") or [])
            uoms_avail = list(opt_row.get("uoms") or [])
            stores_avail = list(opt_row.get("stores") or [])

        if track_switched:
            st.session_state["f_date_range"] = (min_date, max_date)
        st.session_state["f_track_prev"] = selected_track

        _prune_selection("f_countries", countries_avail)
        _prune_selection("f_city_clusters", clusters_avail)
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
        selected_clusters = st.multiselect(
            "Cụm cửa hàng",
            options=clusters_avail,
            placeholder="Tất cả cụm cửa hàng",
            key="f_city_clusters",
        )
        selected_stores = st.multiselect(
            "Cửa hàng",
            options=stores_avail,
            placeholder="Tất cả cửa hàng",
            key="f_stores",
        )
        selected_uoms = st.multiselect(
            "Đơn vị tính",
            options=uoms_avail,
            placeholder="Tất cả đơn vị",
            key="f_uoms",
        )

        uom_guard = evaluate_uom_compatibility(selected_track, selected_uoms, uoms_avail)
        if uom_guard.is_multi_uom_blocked:
            st.warning(
                f"Đang gồm **{uom_guard.uom_count} ĐVT** chưa có hệ số quy đổi chung — chọn **1 ĐVT** để so sản lượng.",
                icon="⚠️",
            )

        date_val = st.date_input(
            "Khoảng thời gian",
            min_value=min_date,
            max_value=max_date,
            format="YYYY/MM/DD",
            key="f_date_range",
        )
        if isinstance(date_val, (tuple, list)) and len(date_val) == 2:
            date_start, date_end = date_val[0], date_val[1]
        else:
            date_start, date_end = date_val, date_val

        selected_grain = st.selectbox(
            "Độ mịn thời gian",
            options=list(TIME_GRAIN_ORDER),
            format_func=time_grain_label,
            key="f_time_grain",
        )

        track_meta = TRACK_META.get(selected_track or "")
        track_ccy = track_meta.currency_code if track_meta else None
        if track_ccy:
            display_vnd = st.toggle(
                f"Quy đổi VNĐ (₫ từ {track_ccy})",
                key="f_display_vnd",
                help=vnd_rate_note(track_ccy, True) or "Quy đổi tham chiếu sang Đồng Việt Nam.",
            )
        else:
            st.session_state["f_display_vnd"] = False
            display_vnd = False

        with st.expander("Tùy chọn thêm", expanded=False):
            selected_palette_key = st.selectbox(
                "Bảng màu giao diện",
                options=palette_keys,
                format_func=lambda k: PALETTES[k].label,
                key="palette_key",
            )
            selected_temps = st.multiselect(
                "Mức nhiệt độ",
                options=[b for b in TEMP_BAND_ORDER if b != "Unknown"],
                format_func=temp_label,
                placeholder="Tất cả mức nhiệt độ",
                key="f_temp_bands",
            )
            compare_mode = st.selectbox(
                "Kỳ so sánh mặc định",
                options=list(COMPARE_MODE_ORDER),
                format_func=lambda k: COMPARE_MODE_LABELS.get(k, k),
                key="f_compare_mode",
                help="Tự động bỏ qua tháng chưa đủ ngày để tránh so sánh lệch kỳ.",
            )
        palette = PALETTES[selected_palette_key]

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            st.button("Đặt lại bộ lọc", width="stretch", on_click=reset_all_filters)
        with col_btn2:
            if st.button("Làm mới", width="stretch"):
                db.run_query_df.clear()
                st.rerun()

    st.session_state["_track_bounds"] = {
        "min_date": min_date,
        "max_date": max_date,
        "uoms_avail": tuple(uoms_avail),
        "countries_avail": tuple(countries_avail),
        "clusters_avail": tuple(clusters_avail),
        "stores_avail": tuple(stores_avail),
    }

    inject_theme_css(palette)

    return FilterState(
        dataset_track=selected_track,
        countries=tuple(selected_countries),
        city_clusters=tuple(selected_clusters),
        stores=tuple(selected_stores),
        clean_uoms=tuple(selected_uoms),
        date_start=date_start,
        date_end=date_end,
        temp_bands=tuple(selected_temps),
        compare_mode=str(compare_mode),
        time_grain=str(selected_grain),
        display_vnd=bool(display_vnd),
    )


def get_current_filters() -> FilterState:
    """Reuse FilterState rendered in app.py shell, or render sidebar directly when page runs standalone."""
    active = st.session_state.get("_active_filters")
    if isinstance(active, FilterState):
        return active
    return render_sidebar_and_get_filters()
