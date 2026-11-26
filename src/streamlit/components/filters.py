"""Shared sidebar filters, palette selector, comparison selector, and isolated page state."""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

import pandas as pd
import streamlit as st

from analytics import COMPARE_MODE_LABELS, COMPARE_MODE_ORDER, evaluate_uom_compatibility
from config import (
    DEFAULT_PALETTE_KEY,
    DEFAULT_TRACK,
    HUMIDITY_BAND_ORDER,
    PALETTES,
    RAIN_REGIME_ORDER,
    TEMP_BAND_ORDER,
    TIME_GRAIN_ORDER,
    TRACK_META,
    country_label,
    resolve_scope_meta,
    temp_label,
    time_grain_label,
    vnd_rate_note,
)
import db
from queries import FilterState, sql_filter_taxonomy, sql_release_state
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
    "p1_series_grain",
    "p1_series_metric",
    "p1_series_ma",
    "_p1_synced_grain",
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
    "p2_map_mode",
    "p2_map_color",
    "_p2_synced_grain",
    "p3_store_search",
    "p3_map_mode",
    "p3_map_engine",
    "p3_map_size",
    "p3_map_color",
    "p3_map_clusters",
    "p3_map_force_eu",
    "p4_product_search",
    "p4_atc_apply_date",
    "p4_from_jump",
    "p4_compare_mode",
    "p4_custom_a",
    "p4_custom_b",
    "_p4_synced_compare_mode",
    "p5_atc",
    "p5_horizon",
    "p5_show_cqr",
    "p5_compare_weekly",
    "p5_compare_daily",
    "ui_info_drawer_open",
    "_page_info_panel",
)


def _to_date(val: Any, fallback: date) -> date:
    if isinstance(val, date) and not hasattr(val, "hour"):
        return val
    if hasattr(val, "date"):
        try:
            return val.date()
        except Exception:
            pass
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return fallback


def _ordered_available(raw_vals: set[str], canonical_order: Sequence[str]) -> list[str]:
    return [item for item in canonical_order if item != "Unknown" and item in raw_vals]


def resolve_cascading_options(
    taxonomy_df: pd.DataFrame,
    *,
    countries: Sequence[str] = (),
    city_clusters: Sequence[str] = (),
    stores: Sequence[str] = (),
    uoms: Sequence[str] = (),
    temp_bands: Sequence[str] = (),
) -> dict[str, Any]:
    """Compute strict top-down cascading options and prune stale child selections."""
    fallback_min = date(2014, 1, 1)
    fallback_max = date(2025, 12, 31)
    fallback_temps = [b for b in TEMP_BAND_ORDER if b != "Unknown"]
    fallback_rains = [r for r in RAIN_REGIME_ORDER if r != "Unknown"]
    fallback_hums = [h for h in HUMIDITY_BAND_ORDER if h != "Unknown"]

    if taxonomy_df is None or taxonomy_df.empty:
        return {
            "track_min_date": fallback_min,
            "track_max_date": fallback_max,
            "min_date": fallback_min,
            "max_date": fallback_max,
            "countries_avail": [],
            "clusters_avail": [],
            "stores_avail": [],
            "uoms_avail": [],
            "temp_bands_avail": fallback_temps,
            "rain_regimes_avail": fallback_rains,
            "humidity_bands_avail": fallback_hums,
            "active_tracks": (),
            "active_currencies": (),
            "active_provenances": (),
            "pruned_countries": [],
            "pruned_clusters": [],
            "pruned_stores": [],
            "pruned_uoms": [],
            "pruned_temps": [],
        }

    df = taxonomy_df.copy()
    track_min_date = _to_date(df["min_date"].dropna().min(), fallback_min) if "min_date" in df else fallback_min
    track_max_date = _to_date(df["max_date"].dropna().max(), fallback_max) if "max_date" in df else fallback_max

    countries_avail = sorted(df["country_code"].dropna().astype(str).unique().tolist())
    valid_countries = set(countries_avail)
    pruned_countries = [str(c) for c in countries if str(c) in valid_countries]
    df_c = df[df["country_code"].astype(str).isin(pruned_countries)] if pruned_countries else df

    clusters_avail = sorted(df_c["city_cluster"].dropna().astype(str).unique().tolist())
    valid_clusters = set(clusters_avail)
    pruned_clusters = [str(c) for c in city_clusters if str(c) in valid_clusters]
    df_cl = df_c[df_c["city_cluster"].astype(str).isin(pruned_clusters)] if pruned_clusters else df_c

    stores_avail = sorted(df_cl["store_name"].dropna().astype(str).unique().tolist())
    valid_stores = set(stores_avail)
    pruned_stores = [str(s) for s in stores if str(s) in valid_stores]
    df_s = df_cl[df_cl["store_name"].astype(str).isin(pruned_stores)] if pruned_stores else df_cl

    uoms_avail = sorted(df_s["clean_uom"].dropna().astype(str).unique().tolist())
    valid_uoms = set(uoms_avail)
    pruned_uoms = [str(u) for u in uoms if str(u) in valid_uoms]
    df_u = df_s[df_s["clean_uom"].astype(str).isin(pruned_uoms)] if pruned_uoms else df_s
    if df_u.empty:
        df_u = df_s

    min_date = _to_date(df_u["min_date"].dropna().min(), track_min_date) if "min_date" in df_u else track_min_date
    max_date = _to_date(df_u["max_date"].dropna().max(), track_max_date) if "max_date" in df_u else track_max_date

    raw_temps = set(df_u["temp_band"].dropna().astype(str)) if "temp_band" in df_u else set()
    temp_bands_avail = _ordered_available(raw_temps, TEMP_BAND_ORDER) or fallback_temps
    valid_temps = set(temp_bands_avail)
    pruned_temps = [str(t) for t in temp_bands if str(t) in valid_temps]
    df_t = df_u[df_u["temp_band"].astype(str).isin(pruned_temps)] if pruned_temps else df_u
    if df_t.empty:
        df_t = df_u

    raw_rains = set(df_t["rain_regime"].dropna().astype(str)) if "rain_regime" in df_t else set()
    rain_regimes_avail = _ordered_available(raw_rains, RAIN_REGIME_ORDER) or fallback_rains
    raw_hums = set(df_t["humidity_band"].dropna().astype(str)) if "humidity_band" in df_t else set()
    humidity_bands_avail = _ordered_available(raw_hums, HUMIDITY_BAND_ORDER) or fallback_hums

    active_tracks = (
        tuple(sorted(df_u["dataset_track"].dropna().astype(str).unique().tolist()))
        if "dataset_track" in df_u
        else ()
    )
    active_currencies = (
        tuple(sorted(df_u["currency_code"].dropna().astype(str).unique().tolist()))
        if "currency_code" in df_u
        else ()
    )
    active_provenances = (
        tuple(sorted(df_u["provenance_class"].dropna().astype(str).unique().tolist()))
        if "provenance_class" in df_u
        else ()
    )

    return {
        "track_min_date": track_min_date,
        "track_max_date": track_max_date,
        "min_date": min_date,
        "max_date": max_date,
        "countries_avail": countries_avail,
        "clusters_avail": clusters_avail,
        "stores_avail": stores_avail,
        "uoms_avail": uoms_avail,
        "temp_bands_avail": temp_bands_avail,
        "rain_regimes_avail": rain_regimes_avail,
        "humidity_bands_avail": humidity_bands_avail,
        "active_tracks": active_tracks,
        "active_currencies": active_currencies,
        "active_provenances": active_provenances,
        "pruned_countries": pruned_countries,
        "pruned_clusters": pruned_clusters,
        "pruned_stores": pruned_stores,
        "pruned_uoms": pruned_uoms,
        "pruned_temps": pruned_temps,
    }


def sync_local_from_global(
    global_val: str,
    local_key: str,
    tracker_key: str,
    valid_options: Sequence[str],
) -> str:
    """Propagate global sidebar control changes to a page-local control cleanly."""
    fallback = global_val if global_val in valid_options else valid_options[0]
    prev_synced = st.session_state.get(tracker_key)
    cur_local = st.session_state.get(local_key)
    if prev_synced is not None and prev_synced != global_val:
        st.session_state[local_key] = fallback
    elif cur_local not in valid_options:
        st.session_state[local_key] = fallback
    st.session_state[tracker_key] = global_val
    return str(st.session_state[local_key])


def _ensure_defaults() -> None:
    st.session_state.setdefault("palette_key", DEFAULT_PALETTE_KEY)
    st.session_state.setdefault("f_track", None)
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
    st.session_state["f_track"] = None
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
    st.session_state.pop("_prev_scope_date_bounds", None)
    st.session_state.pop("_track_bounds", None)
    for key in _PAGE_LOCAL_KEYS:
        st.session_state.pop(key, None)


def set_global_uoms(uoms: list[str]) -> None:
    """Callback helper for 1-click single-UOM selection buttons across pages."""
    st.session_state["f_uoms"] = list(uoms)


def _prune_selection(state_key: str, valid_options: Sequence[str]) -> list[str]:
    valid_set = set(valid_options)
    current = list(st.session_state.get(state_key, []))
    pruned = [v for v in current if v in valid_set]
    if pruned != current:
        st.session_state[state_key] = pruned
    return pruned


prune_selection = _prune_selection


def get_track_bounds() -> dict[str, Any]:
    return dict(st.session_state.get("_track_bounds") or {})


def render_sidebar_and_get_filters() -> FilterState:
    """Render shared sidebar palette switcher + unified cascading global filters across all datasets."""
    _ensure_defaults()

    try:
        schema = db.get_active_schema()
        release_sql, release_params = sql_release_state(schema)
        release_df = db.run_query_df(release_sql, release_params)
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

        selected_track: str | None = st.session_state.get("f_track")
        if selected_track is not None and not str(selected_track).strip():
            selected_track = None

        prev_track = st.session_state.get("f_track_prev")
        track_switched = prev_track is not None and prev_track != selected_track
        if track_switched:
            st.session_state["f_countries"] = []
            st.session_state["f_city_clusters"] = []
            st.session_state["f_stores"] = []
            st.session_state["f_uoms"] = []
            st.session_state["f_temp_bands"] = []
            st.session_state.pop("f_date_range", None)
            st.session_state.pop("_prev_scope_date_bounds", None)
            for key in _PAGE_LOCAL_KEYS:
                st.session_state.pop(key, None)

        tax_sql, tax_params = sql_filter_taxonomy(schema, selected_track)
        taxonomy_df = db.run_query_df(tax_sql, tax_params)

        casc = resolve_cascading_options(
            taxonomy_df,
            countries=st.session_state.get("f_countries", ()),
            city_clusters=st.session_state.get("f_city_clusters", ()),
            stores=st.session_state.get("f_stores", ()),
            uoms=st.session_state.get("f_uoms", ()),
            temp_bands=st.session_state.get("f_temp_bands", ()),
        )

        countries_avail: list[str] = casc["countries_avail"]
        clusters_avail: list[str] = casc["clusters_avail"]
        stores_avail: list[str] = casc["stores_avail"]
        uoms_avail: list[str] = casc["uoms_avail"]
        temp_bands_avail: list[str] = casc["temp_bands_avail"]
        min_date: date = casc["min_date"]
        max_date: date = casc["max_date"]
        track_min_date: date = casc["track_min_date"]
        track_max_date: date = casc["track_max_date"]

        st.session_state["f_countries"] = casc["pruned_countries"]
        st.session_state["f_city_clusters"] = casc["pruned_clusters"]
        st.session_state["f_stores"] = casc["pruned_stores"]
        st.session_state["f_uoms"] = casc["pruned_uoms"]
        st.session_state["f_temp_bands"] = casc["pruned_temps"]

        prev_scope_bounds = st.session_state.get("_prev_scope_date_bounds")
        cur_date_range = st.session_state.get("f_date_range")
        if track_switched or cur_date_range is None:
            st.session_state["f_date_range"] = (min_date, max_date)
        elif (
            not isinstance(cur_date_range, (tuple, list))
            or len(cur_date_range) != 2
            or not isinstance(cur_date_range[0], date)
            or not isinstance(cur_date_range[1], date)
        ):
            st.session_state["f_date_range"] = (min_date, max_date)
        elif (
            prev_scope_bounds is not None
            and (cur_date_range[0], cur_date_range[1]) == tuple(prev_scope_bounds)
            and (min_date, max_date) != tuple(prev_scope_bounds)
        ):
            # User had the full previous scope range selected -> auto-follow new scope bounds (incl. expanding back!)
            st.session_state["f_date_range"] = (min_date, max_date)
        else:
            d0, d1 = cur_date_range[0], cur_date_range[1]
            if d0 < min_date or d1 > max_date or d0 > d1:
                clamped_0 = max(d0, min_date)
                clamped_1 = min(d1, max_date)
                st.session_state["f_date_range"] = (
                    (clamped_0, clamped_1) if clamped_0 <= clamped_1 else (min_date, max_date)
                )

        st.session_state["_prev_scope_date_bounds"] = (min_date, max_date)
        st.session_state["f_track_prev"] = selected_track

        selected_countries = st.multiselect(
            "Quốc gia",
            options=countries_avail,
            format_func=country_label,
            placeholder="Tất cả quốc gia" if len(countries_avail) != 1 else country_label(countries_avail[0]),
            key="f_countries",
        )
        selected_clusters = st.multiselect(
            "Cụm cửa hàng",
            options=clusters_avail,
            placeholder="Tất cả cụm cửa hàng" if len(clusters_avail) != 1 else clusters_avail[0],
            key="f_city_clusters",
        )
        selected_stores = st.multiselect(
            "Cửa hàng",
            options=stores_avail,
            placeholder="Tất cả cửa hàng" if len(stores_avail) != 1 else stores_avail[0],
            key="f_stores",
        )
        selected_uoms = st.multiselect(
            "Đơn vị tính",
            options=uoms_avail,
            placeholder="Tất cả đơn vị" if len(uoms_avail) != 1 else uoms_avail[0],
            key="f_uoms",
        )

        # Recompute effective scope metadata from current multiselect selections
        scope_casc = resolve_cascading_options(
            taxonomy_df,
            countries=selected_countries,
            city_clusters=selected_clusters,
            stores=selected_stores,
            uoms=selected_uoms,
            temp_bands=st.session_state.get("f_temp_bands", ()),
        )
        active_tracks = scope_casc["active_tracks"]
        active_currencies = scope_casc["active_currencies"]
        active_provenances = scope_casc["active_provenances"]

        uom_track_hint = active_tracks[0] if len(active_tracks) == 1 else selected_track
        uom_guard = evaluate_uom_compatibility(uom_track_hint, selected_uoms, uoms_avail)
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

        pre_scope = resolve_scope_meta(
            active_tracks,
            active_currencies,
            active_provenances,
            display_vnd=bool(st.session_state.get("f_display_vnd", False)),
            fallback_track=selected_track,
        )
        if pre_scope.is_multi_currency:
            st.caption(
                f"Đa tiền tệ ({' + '.join(active_currencies)}) → tự động quy đổi tham chiếu về **VNĐ (₫)**."
            )
            display_vnd = True
            normalize_vnd = True
        elif pre_scope.currency_code:
            display_vnd = st.toggle(
                f"Quy đổi VNĐ (₫ từ {pre_scope.currency_code})",
                key="f_display_vnd",
                help=vnd_rate_note(pre_scope.currency_code, True) or "Quy đổi tham chiếu sang Đồng Việt Nam.",
            )
            normalize_vnd = False
        else:
            st.session_state["f_display_vnd"] = False
            display_vnd = False
            normalize_vnd = False

        scope_meta = resolve_scope_meta(
            active_tracks,
            active_currencies,
            active_provenances,
            display_vnd=display_vnd,
            fallback_track=selected_track,
        )

        with st.expander("Tùy chọn thêm", expanded=False):
            selected_palette_key = st.selectbox(
                "Bảng màu giao diện",
                options=palette_keys,
                format_func=lambda k: PALETTES[k].label,
                key="palette_key",
            )
            selected_temps = st.multiselect(
                "Mức nhiệt độ",
                options=temp_bands_avail,
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
        "min_date": track_min_date,
        "max_date": track_max_date,
        "scope_min_date": min_date,
        "scope_max_date": max_date,
        "uoms_avail": tuple(uoms_avail),
        "countries_avail": tuple(countries_avail),
        "clusters_avail": tuple(clusters_avail),
        "stores_avail": tuple(stores_avail),
        "temp_bands_avail": tuple(temp_bands_avail),
        "rain_regimes_avail": tuple(casc["rain_regimes_avail"]),
        "humidity_bands_avail": tuple(casc["humidity_bands_avail"]),
        "active_tracks": active_tracks,
        "active_currencies": active_currencies,
        "active_provenances": active_provenances,
        "scope_meta": scope_meta,
        "taxonomy_df": taxonomy_df,
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
        normalize_currency_to_vnd=bool(normalize_vnd),
    )


def get_current_filters() -> FilterState:
    """Reuse FilterState rendered in app.py shell, or render sidebar directly when page runs standalone."""
    active = st.session_state.get("_active_filters")
    if isinstance(active, FilterState):
        return active
    return render_sidebar_and_get_filters()
