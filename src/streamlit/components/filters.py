"""Shared sidebar filters, palette selector, and cascading session state."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

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
from db import MissingDatabaseConfigError, get_active_schema, run_query_df
from queries import FilterState, sql_available_tracks, sql_filter_options, sql_release_state
from ui import get_active_palette, inject_theme_css


def _ensure_defaults() -> None:
    st.session_state.setdefault("palette_key", DEFAULT_PALETTE_KEY)
    st.session_state.setdefault("f_track", DEFAULT_TRACK)
    st.session_state.setdefault("f_countries", [])
    st.session_state.setdefault("f_stores", [])
    st.session_state.setdefault("f_uoms", [])
    st.session_state.setdefault("f_temp_bands", [])
    st.session_state.setdefault("f_rain_regimes", [])
    st.session_state.setdefault("f_humidity_bands", [])
    st.session_state.setdefault("f_heatmap_cell", None)


def reset_all_filters() -> None:
    st.session_state["f_track"] = DEFAULT_TRACK
    st.session_state["f_countries"] = []
    st.session_state["f_stores"] = []
    st.session_state["f_uoms"] = []
    st.session_state["f_temp_bands"] = []
    st.session_state["f_rain_regimes"] = []
    st.session_state["f_humidity_bands"] = []
    st.session_state["f_heatmap_cell"] = None
    st.session_state.pop("f_date_range", None)
    st.session_state.pop("f_track_prev", None)


def _prune_selection(state_key: str, valid_options: list[str]) -> list[str]:
    valid_set = set(valid_options)
    current = list(st.session_state.get(state_key, []))
    pruned = [v for v in current if v in valid_set]
    if pruned != current:
        st.session_state[state_key] = pruned
    return pruned


def render_sidebar_and_get_filters() -> FilterState:
    """Render shared sidebar palette switcher + cascading filters, returning FilterState."""
    _ensure_defaults()

    try:
        schema = get_active_schema()
        release_sql, release_params = sql_release_state(schema)
        release_df = run_query_df(release_sql, release_params)
        tracks_sql, tracks_params = sql_available_tracks(schema)
        tracks_df = run_query_df(tracks_sql, tracks_params)
    except MissingDatabaseConfigError as exc:
        inject_theme_css(get_active_palette())
        st.error(str(exc))
        st.stop()
    except Exception as exc:
        inject_theme_css(get_active_palette())
        st.error(f"Không thể kết nối Neon BI Mirror ({type(exc).__name__}). Hãy kiểm tra cấu hình mạng và `QUICK_NEON_DATABASE_URL`.")
        st.stop()

    palette_keys = list(PALETTES.keys())
    with st.sidebar:
        palette = get_active_palette()
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
              <div class="pf-sidebar-meta">Bán lẻ Dược phẩm & Thời tiết · Gold MD-01</div>
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
            help="Luôn tách nhóm dữ liệu để tránh cộng gộp EUR với IDR và nhiều đơn vị tính.",
        )

        # Fetch cascading option lists scoped by selected track
        opts_sql, opts_params = sql_filter_options(schema, selected_track)
        opts_df = run_query_df(opts_sql, opts_params)

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

        # Reset track-scoped subfilters cleanly when user switches dataset track
        prev_track = st.session_state.get("f_track_prev")
        if prev_track is not None and prev_track != selected_track:
            st.session_state["f_countries"] = []
            st.session_state["f_stores"] = []
            st.session_state["f_uoms"] = []
            st.session_state["f_date_range"] = (min_date, max_date)
            st.session_state["f_heatmap_cell"] = None
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
            "Đơn vị tính",
            options=uoms_avail,
            placeholder="Tất cả đơn vị",
            key="f_uoms",
        )

        # Smart multi-UOM warning for IRPD Indonesia
        track_meta = TRACK_META.get(selected_track)
        if track_meta and track_meta.multi_uom and not selected_uoms:
            st.warning(
                f"Nguồn này có **{len(uoms_avail)} đơn vị tính** khác nhau (`tab`, `pcs`, `fls`...). "
                "Nên chọn 1 đơn vị tính để so sánh sản lượng chính xác.",
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

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Đặt lại bộ lọc", width="stretch", on_click=reset_all_filters):
                pass
        with col_btn2:
            if st.button("Làm mới cache", width="stretch"):
                run_query_df.clear()
                st.rerun()

    # Apply theme CSS after palette selection resolves
    inject_theme_css(palette)

    cell = st.session_state.get("f_heatmap_cell")
    cell_temp = cell.get("temp_band") if isinstance(cell, dict) else None
    cell_rain = cell.get("rain_regime") if isinstance(cell, dict) else None

    return FilterState(
        dataset_track=selected_track,
        countries=tuple(selected_countries),
        stores=tuple(selected_stores),
        clean_uoms=tuple(selected_uoms),
        date_start=date_start,
        date_end=date_end,
        temp_bands=tuple(selected_temps),
        rain_regimes=tuple(st.session_state.get("p2_rain_regimes", ())),
        humidity_bands=tuple(st.session_state.get("p2_humidity_bands", ())),
        heatmap_temp_band=cell_temp,
        heatmap_rain_regime=cell_rain,
    )


def get_current_filters() -> FilterState:
    """Reuse FilterState rendered in app.py shell, or render sidebar directly when page runs standalone."""
    active = st.session_state.get("_active_filters")
    if isinstance(active, FilterState):
        return active
    return render_sidebar_and_get_filters()
