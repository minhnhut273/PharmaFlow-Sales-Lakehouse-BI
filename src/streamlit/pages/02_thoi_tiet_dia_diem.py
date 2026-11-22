"""Page 2: Weather & Location Observational Analytics (Thời Tiết & Địa Điểm)."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from analytics import SMALL_SAMPLE_STORE_DAYS, build_weather_insights, evaluate_uom_compatibility
from components.filters import get_current_filters, get_track_bounds, set_global_uoms
from config import (
    DOW_VI_BY_NUM,
    HUMIDITY_BAND_ORDER,
    RAIN_REGIME_ORDER,
    TEMP_BAND_ORDER,
    TIME_GRAIN_ORDER,
    TRACK_META,
    currency_display_unit,
    currency_multiplier,
    fmt_compact,
    fmt_currency,
    fmt_int,
    humidity_label,
    rain_label,
    safe_round,
    temp_label,
    time_grain_label,
    vnd_rate_note,
    weekend_label,
)
import db
from queries import (
    FilterState,
    sql_daily_temp_scatter,
    sql_daily_weather_table,
    sql_humidity_weekend,
    sql_store_map_points,
    sql_store_product_mix,
    sql_temp_rain_heatmap,
    sql_time_series_by_grain,
    sql_top_products_by_rain,
    sql_uom_breakdown,
    sql_weather_kpis,
    sql_weekday_by_rain,
)
from ui import (
    get_active_palette,
    open_page_layout_columns,
    plotly_config,
    polish_horizontal_bar,
    polish_vertical_bar_headroom,
    render_chart_header,
    render_csv_download,
    render_empty_state,
    render_insight_box,
    render_kpi_card,
    render_page_header,
    render_right_explanation_panel,
    render_scope_strip,
    render_street_map,
    render_top_action_bar,
    style_plotly,
)


def _clear_page2_filters() -> None:
    st.session_state["p2_temp_bands"] = []
    st.session_state["p2_rain_regimes"] = []
    st.session_state["p2_humidity_bands"] = []


def render_page(global_filters: FilterState) -> None:
    schema = db.get_active_schema()
    palette = get_active_palette()
    meta = TRACK_META.get(global_filters.dataset_track or "")
    ccy = meta.currency_code if meta else None
    has_rev = bool(meta.has_revenue) if meta else False
    prov_class = meta.provenance_class if meta else "SYNTHETIC"
    to_vnd = bool(global_filters.display_vnd)
    mult = currency_multiplier(ccy, to_vnd)
    disp_ccy = currency_display_unit(ccy, to_vnd)

    bounds = get_track_bounds()
    uoms_avail = bounds.get("uoms_avail") or ()

    st.session_state.setdefault("p2_temp_bands", [])
    st.session_state.setdefault("p2_rain_regimes", [])
    st.session_state.setdefault("p2_humidity_bands", [])

    render_page_header(
        "Thời Tiết & Mùa Vụ",
        "Trực quan hóa bản đồ thời tiết địa phương, ma trận nhiệt độ × mưa và xu hướng từng mặt hàng.",
        dataset_track=global_filters.dataset_track,
        extra_pills=[
            ("Không bao gồm ngày bán bằng 0", "warn"),
            ("Không suy diễn nhân quả", "default"),
        ],
    )

    uom_guard = evaluate_uom_compatibility(global_filters.dataset_track, global_filters.clean_uoms, uoms_avail)
    use_rev_instead_of_qty = bool(uom_guard.is_multi_uom_blocked and has_rev)

    # Local Weather Filters (strictly isolated to Page 2 — non-overlapping Temp / Rain / Humidity / Metric)
    with st.container(border=True):
        wc1, wc2, wc3, wc4 = st.columns([3, 3, 3, 3])
        with wc1:
            temp_sel = st.multiselect(
                "Nhiệt độ",
                options=[t for t in TEMP_BAND_ORDER if t != "Unknown"],
                format_func=temp_label,
                placeholder="Tất cả mức nhiệt độ",
                key="p2_temp_bands",
            )
        with wc2:
            rain_sel = st.multiselect(
                "Mức mưa",
                options=[r for r in RAIN_REGIME_ORDER if r != "Unknown"],
                format_func=rain_label,
                placeholder="Tất cả mức mưa",
                key="p2_rain_regimes",
            )
        with wc3:
            hum_sel = st.multiselect(
                "Độ ẩm",
                options=[h for h in HUMIDITY_BAND_ORDER if h != "Unknown"],
                format_func=humidity_label,
                placeholder="Tất cả độ ẩm",
                key="p2_humidity_bands",
            )
        with wc4:
            metric_mode = st.radio(
                "Thước đo",
                options=["normalized", "total"],
                format_func=lambda m: (
                    f"TB / CH-ngày ({disp_ccy or 'ĐVT'})"
                    if m == "normalized"
                    else "Tổng cộng"
                ),
                key="p2_metric_mode",
            )

        if temp_sel or rain_sel or hum_sel:
            bcol1, bcol2 = st.columns([9, 3])
            with bcol2:
                st.button("Xóa lọc thời tiết", width="stretch", on_click=_clear_page2_filters, key="p2_clear_all")

    filters = replace(
        global_filters,
        temp_bands=tuple(temp_sel) if temp_sel else global_filters.temp_bands,
        rain_regimes=tuple(rain_sel),
        humidity_bands=tuple(hum_sel),
    )

    hm_sql, hm_params = sql_temp_rain_heatmap(schema, filters)
    hm_df = db.run_query_df(hm_sql, hm_params)

    local_tags: list[str] = []
    if temp_sel:
        local_tags.append(f"T°: {', '.join(temp_label(t) for t in temp_sel)}")
    if rain_sel:
        local_tags.append(f"Mưa: {', '.join(rain_label(r) for r in rain_sel)}")
    if hum_sel:
        local_tags.append(f"Độ ẩm: {', '.join(humidity_label(h) for h in hum_sel)}")

    render_top_action_bar(
        global_filters,
        page_key="p2",
        local_tags=local_tags,
        show_compare_jump=True,
    )

    main_col, drawer_col = open_page_layout_columns()

    with main_col:
        if uom_guard.is_multi_uom_blocked:
            st.warning(
                f"{uom_guard.message} "
                + (
                    f"Biểu đồ đang dùng **Doanh thu ({disp_ccy}) / CH-ngày** thay cho cộng gộp sản lượng khác ĐVT."
                    if has_rev
                    else ""
                ),
                icon="⚠️",
            )
            uom_sql, uom_params = sql_uom_breakdown(schema, global_filters)
            uom_df = db.run_query_df(uom_sql, uom_params)
            top_uoms = uom_df["clean_uom"].dropna().head(5).tolist() if not uom_df.empty else []
            if top_uoms:
                cols_u = st.columns([2] + [1.2] * len(top_uoms))
                with cols_u[0]:
                    st.caption("Chọn nhanh 1 ĐVT:")
                for idx, u in enumerate(top_uoms):
                    with cols_u[idx + 1]:
                        st.button(
                            f"ĐVT: {u}",
                            key=f"p2_pick_uom_{idx}",
                            width="stretch",
                            on_click=set_global_uoms,
                            args=([str(u)],),
                        )

        # Metric display configuration
        is_norm = metric_mode == "normalized"
        val_scale = mult if use_rev_instead_of_qty else 1.0
        if use_rev_instead_of_qty:
            metric_col = "rev_per_store_day" if is_norm else "line_amount"
            metric_unit = disp_ccy
            metric_title_short = f"Doanh thu / CH-ngày ({disp_ccy})" if is_norm else f"Tổng doanh thu ({disp_ccy})"
            metric_noun = "doanh thu / CH-ngày" if is_norm else "tổng doanh thu"
        else:
            metric_col = "qty_per_store_day" if is_norm else "sold_qty"
            metric_unit = uom_guard.single_uom
            unit_suffix = f" ({metric_unit})" if metric_unit else ""
            metric_title_short = f"Sản lượng / CH-ngày{unit_suffix}" if is_norm else f"Tổng sản lượng{unit_suffix}"
            metric_noun = f"sản lượng / CH-ngày{unit_suffix}" if is_norm else f"tổng sản lượng{unit_suffix}"

        # KPI query
        wk_sql, wk_params = sql_weather_kpis(schema, filters)
        wk_df = db.run_query_df(wk_sql, wk_params)
        wrow = wk_df.iloc[0] if not wk_df.empty else {}

        active_stores = int(wrow.get("active_stores") or 0)
        active_dates = int(wrow.get("active_dates") or 0)
        active_sd = int(wrow.get("active_store_days") or 0)
        possible_sd = int(wrow.get("possible_store_days") or 0)
        cov_pct = (active_sd / possible_sd * 100.0) if possible_sd > 0 else 0.0
        qty_per_sd = wrow.get("qty_per_store_day")
        rev_per_sd = wrow.get("rev_per_store_day")
        total_qty = wrow.get("total_sold_qty")
        total_rev = wrow.get("total_revenue")
        avg_temp = wrow.get("avg_temp_mean")
        avg_app_temp = wrow.get("avg_apparent_temp_mean")
        avg_precip = wrow.get("avg_precip_sum")
        rainy_sd = int(wrow.get("rainy_store_days") or 0)
        w_rows = int(wrow.get("weather_covered_rows") or 0)
        tot_rows = int(wrow.get("row_count") or 0)
        w_cov_pct = (w_rows / tot_rows * 100.0) if tot_rows > 0 else 0.0
        rainy_share = (rainy_sd / active_sd * 100.0) if active_sd > 0 else 0.0

        # Collapsed/drawer insights (zero text wall on canvas)
        hm_norm_col = "rev_per_store_day" if use_rev_instead_of_qty else "qty_per_store_day"
        insight_bullets = build_weather_insights(
            hm_df=hm_df,
            metric_col=hm_norm_col,
            metric_unit=ccy if use_rev_instead_of_qty else uom_guard.single_uom,
            metric_noun=f"doanh thu / CH-ngày ({ccy})" if use_rev_instead_of_qty else f"sản lượng / CH-ngày ({uom_guard.single_uom or 'ĐVT'})",
            provenance_class=prov_class,
            active_store_days=active_sd,
            possible_store_days=possible_sd,
        )
        render_insight_box("Nhận xét thời tiết từ dữ liệu chuẩn hóa", insight_bullets)

        # Row 1: 4 Visual-first KPI Cards with top-right ⓘ tooltips
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            render_kpi_card(
                "Cửa Hàng-Ngày",
                f"{fmt_int(active_sd)}",
                f"{active_stores} CH · {active_dates} ngày",
                tag="Mẫu số",
                accent=palette.primary,
                delta_text=f"Phủ {cov_pct:.1f}%",
                delta_tone="neutral",
                info_tooltip="Chỉ đếm cặp (Cửa hàng, Ngày) có sold_qty > 0. Không tính ngày bán bằng 0 hay đóng cửa.",
            )
        with k2:
            if use_rev_instead_of_qty:
                k2_title = f"Trung Bình / Ngày ({disp_ccy})" if disp_ccy else "Trung Bình / Ngày"
                k2_val = fmt_currency(rev_per_sd, ccy, to_vnd=to_vnd) if active_sd > 0 else "—"
                k2_delta = f"Tổng: {fmt_currency(total_rev, ccy, to_vnd=to_vnd)}"
                k2_tip = f"Tổng doanh thu chia cho {active_sd:,} CH-ngày có bán. Dùng tiền tệ thay sản lượng vì đang chọn nhiều ĐVT. {vnd_rate_note(ccy, to_vnd)}"
            else:
                k2_title = f"Trung Bình / Ngày ({uom_guard.single_uom or 'ĐVT'})"
                k2_val = f"{float(qty_per_sd):,.2f}" if (active_sd > 0 and pd.notna(qty_per_sd)) else "—"
                k2_delta = f"Tổng: {fmt_compact(total_qty)}"
                k2_tip = "Tổng sản lượng (1 ĐVT đồng nhất) chia cho số CH-ngày có giao dịch bán."
            render_kpi_card(
                k2_title,
                k2_val,
                "Chuẩn hóa theo ngày có bán",
                tag="Tốc độ",
                accent=palette.accent,
                delta_text=k2_delta,
                delta_tone="neutral",
                info_tooltip=k2_tip,
            )
        with k3:
            render_kpi_card(
                "Nhiệt Độ TB",
                f"{float(avg_temp):.1f} °C" if pd.notna(avg_temp) else "—",
                f"Cảm nhận: {float(avg_app_temp):.1f} °C" if pd.notna(avg_app_temp) else "Open-Meteo",
                tag="°C",
                accent=palette.discrete[2],
                delta_text=f"Phủ {w_cov_pct:.1f}%",
                delta_tone="neutral",
                info_tooltip="Trung bình không trọng số nhiệt độ 2m theo từng cặp (Cửa hàng, Ngày) phát sinh bán.",
            )
        with k4:
            render_kpi_card(
                "Lượng Mưa TB",
                f"{float(avg_precip):.2f} mm" if pd.notna(avg_precip) else "—",
                f"{rainy_sd:,} CH-ngày có mưa",
                tag="mm",
                accent=palette.discrete[3],
                delta_text=f"Ngày mưa: {rainy_share:.1f}%",
                delta_tone="neutral",
                info_tooltip="Trung bình lượng mưa cộng dồn ngày (mm) trên các CH-ngày có bán.",
            )

        # Row 2: Weather Street Map (5.2) + Temp x Rain Heatmap (6.8)
        col_map, col_hm = st.columns([5.2, 6.8], gap="medium")

        with col_map:
            with st.container(border=True):
                render_chart_header(
                    "Bản Đồ Thời Tiết",
                    "Vị trí địa lý gắn nhiệt độ / lượng mưa TB tại từng cụm hoặc cửa hàng",
                    info_tooltip="Màu thể hiện nhiệt độ (°C) hoặc lượng mưa (mm) trung bình tại điểm bán; kích thước thể hiện doanh thu/sản lượng.",
                )
                mc1, mc2 = st.columns(2)
                with mc1:
                    map_mode = st.radio(
                        "Cấp độ",
                        options=["cluster", "store"],
                        format_func=lambda x: "Cụm TP" if x == "cluster" else "Cửa hàng",
                        horizontal=True,
                        key="p2_map_mode",
                    )
                with mc2:
                    map_color = st.radio(
                        "Màu",
                        options=["avg_temp_mean", "avg_precip_sum"],
                        format_func=lambda x: "Nhiệt độ" if x == "avg_temp_mean" else "Lượng mưa",
                        horizontal=True,
                        key="p2_map_color",
                    )
                wmap_sql, wmap_params = sql_store_map_points(schema, filters)
                wmap_df = db.run_query_df(wmap_sql, wmap_params)
                render_street_map(
                    wmap_df,
                    mode=map_mode,
                    map_engine="maplibre",
                    size_col="line_amount" if has_rev else "sold_qty",
                    color_col=map_color,
                    palette=palette,
                    ccy_label=ccy,
                    to_vnd=to_vnd,
                    height=370,
                )

        with col_hm:
            with st.container(border=True):
                render_chart_header(
                    "Heatmap Nhiệt Độ × Mưa",
                    f"{metric_title_short} · ⚠ đánh dấu n < 30 CH-ngày",
                    info_tooltip="Mỗi ô lấy tổng chia cho số CH-ngày có bán trong chế độ nhiệt độ × mưa đó. Ô dưới 30 mẫu có ký hiệu cảnh báo.",
                )
                if hm_df.empty:
                    render_empty_state()
                else:
                    hm_plot = hm_df.copy()
                    hm_plot["plot_val"] = pd.to_numeric(hm_plot[metric_col], errors="coerce") * val_scale
                    hm_plot["raw_val"] = pd.to_numeric(
                        hm_plot["line_amount" if use_rev_instead_of_qty else "sold_qty"], errors="coerce"
                    ) * val_scale

                    temp_order_raw = [b for b in TEMP_BAND_ORDER if b in set(hm_plot["temp_band"])]
                    rain_order_raw = [r for r in RAIN_REGIME_ORDER if r in set(hm_plot["rain_regime"])]
                    piv_val = hm_plot.pivot(index="rain_regime", columns="temp_band", values="plot_val").reindex(
                        index=rain_order_raw, columns=temp_order_raw
                    )
                    piv_n = hm_plot.pivot(index="rain_regime", columns="temp_band", values="active_store_days").reindex(
                        index=rain_order_raw, columns=temp_order_raw
                    )
                    piv_raw = hm_plot.pivot(index="rain_regime", columns="temp_band", values="raw_val").reindex(
                        index=rain_order_raw, columns=temp_order_raw
                    )
                    x_labels = [temp_label(c) for c in piv_val.columns]
                    y_labels = [rain_label(idx) for idx in piv_val.index]

                    text_vals: list[list[str]] = []
                    custom_vals: list[list[list[str]]] = []
                    for r_i, _r_name in enumerate(piv_val.index):
                        t_row: list[str] = []
                        c_row: list[list[str]] = []
                        for c_i, _c_name in enumerate(piv_val.columns):
                            v = piv_val.iat[r_i, c_i]
                            n_sd = piv_n.iat[r_i, c_i]
                            raw_v = piv_raw.iat[r_i, c_i]
                            if pd.notna(v) and pd.notna(n_sd):
                                n_int = int(n_sd)
                                warn = " ⚠" if n_int < SMALL_SAMPLE_STORE_DAYS else ""
                                v_fmt = fmt_compact(v, decimals=1)
                                t_row.append(f"{v_fmt}<br><span style='font-size:10px'>n={n_int:,}{warn}</span>")
                                c_row.append(
                                    [
                                        f"{v:,.2f}",
                                        f"{n_int:,}",
                                        fmt_compact(raw_v),
                                        f"< {SMALL_SAMPLE_STORE_DAYS} CH-ngày (mẫu nhỏ)" if warn else "Đủ mẫu tham khảo",
                                    ]
                                )
                            else:
                                t_row.append("")
                                c_row.append(["—", "0", "0", "Không có dữ liệu"])
                        text_vals.append(t_row)
                        custom_vals.append(c_row)

                    fig_hm = go.Figure(
                        data=go.Heatmap(
                            z=piv_val.values,
                            x=x_labels,
                            y=y_labels,
                            text=text_vals,
                            customdata=custom_vals,
                            texttemplate="%{text}",
                            textfont=dict(size=11),
                            colorscale=list(palette.continuous_scale),
                            colorbar=dict(title=disp_ccy or (metric_unit or "SL"), thickness=12),
                            hoverongaps=False,
                            hovertemplate=(
                                "Nhiệt độ: %{x}<br>Mức mưa: %{y}<br>"
                                f"{metric_title_short}: %{{customdata[0]}}<br>"
                                "CH-ngày có bán (n): %{customdata[1]}<br>"
                                "Tổng cộng ô này: %{customdata[2]}<br>"
                                "Độ tin cậy: %{customdata[3]}<extra></extra>"
                            ),
                        )
                    )
                    style_plotly(
                        fig_hm,
                        palette,
                        height=425,
                        show_legend=False,
                        xaxis_title="Mức nhiệt độ",
                        yaxis_title="Mức mưa",
                    )
                    fig_hm.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig_hm, width="stretch", theme=None, config=plotly_config())

        # Row 3: Per-Product Weather × Time-Series by Granularity
        with st.container(border=True):
            render_chart_header(
                "Xu Hướng Thuốc × Thời Tiết",
                "Chọn 1–4 mặt hàng cụ thể và độ mịn Ngày / Tuần / Tháng / Quý để đối chiếu cùng biến thời tiết",
                info_tooltip="Cho phép xem biến động lượng bán/doanh thu của từng thuốc cụ thể song song nhiệt độ hoặc lượng mưa theo cùng chu kỳ thời gian.",
            )
            mix_sql, mix_params = sql_store_product_mix(schema, filters)
            mix_df = db.run_query_df(mix_sql, mix_params)
            prod_choices = mix_df["product_name"].dropna().astype(str).head(40).tolist() if not mix_df.empty else []

            sc1, sc2, sc3 = st.columns([5, 3.2, 3.8])
            with sc1:
                sel_prods = st.multiselect(
                    "Chọn thuốc",
                    options=prod_choices,
                    max_selections=4,
                    placeholder="Tất cả mặt hàng...",
                    key="p2_selected_products",
                )
            with sc2:
                default_grain = global_filters.time_grain if global_filters.time_grain in TIME_GRAIN_ORDER else "month"
                if st.session_state.get("p2_series_grain") not in TIME_GRAIN_ORDER:
                    st.session_state["p2_series_grain"] = default_grain
                sel_grain = st.radio(
                    "Độ mịn",
                    options=list(TIME_GRAIN_ORDER),
                    format_func=time_grain_label,
                    horizontal=True,
                    key="p2_series_grain",
                )
            w_line_opts = {
                "avg_apparent_temp_mean": "Nhiệt độ cảm nhận (°C)",
                "avg_temp_mean": "Nhiệt độ TB (°C)",
                "avg_precip_sum": "Lượng mưa TB (mm)",
                "avg_humidity_mean": "Độ ẩm TB (%)",
            }
            with sc3:
                if st.session_state.get("p2_weather_line") not in w_line_opts:
                    st.session_state["p2_weather_line"] = "avg_apparent_temp_mean"
                sel_w_col = st.selectbox(
                    "Đường thời tiết",
                    options=list(w_line_opts.keys()),
                    format_func=lambda k: w_line_opts[k],
                    key="p2_weather_line",
                )

            ts_sql, ts_params = sql_time_series_by_grain(
                schema,
                filters,
                grain=sel_grain,
                products=tuple(sel_prods),
            )
            ts_df = db.run_query_df(ts_sql, ts_params)
            if ts_df.empty:
                render_empty_state()
            else:
                ts_plot = ts_df.copy()
                # When specific product(s) are chosen, check if each product can show qty cleanly, or fallback to revenue
                ts_uoms = set(ts_plot["clean_uom"].dropna().astype(str))
                ts_use_rev = bool(has_rev and (use_rev_instead_of_qty or (not sel_prods and len(ts_uoms) > 1)))
                ts_scale = mult if ts_use_rev else 1.0
                if ts_use_rev:
                    ts_y_raw = pd.to_numeric(ts_plot["line_amount"], errors="coerce") * ts_scale
                    y_lbl_main = f"DT / CH-ngày ({disp_ccy})" if is_norm else f"Doanh thu ({disp_ccy})"
                else:
                    ts_y_raw = pd.to_numeric(ts_plot["sold_qty"], errors="coerce")
                    u_lbl = next(iter(ts_uoms)) if len(ts_uoms) == 1 else (uom_guard.single_uom or "ĐVT")
                    y_lbl_main = f"SL / CH-ngày ({u_lbl})" if is_norm else f"Sản lượng ({u_lbl})"

                sd_denom = pd.to_numeric(ts_plot["active_store_days"], errors="coerce").replace(0, pd.NA)
                ts_plot["metric_y"] = (ts_y_raw / sd_denom) if is_norm else ts_y_raw
                ts_plot["period_date"] = pd.to_datetime(ts_plot["period_date"])

                fig_ts = make_subplots(specs=[[{"secondary_y": True}]])
                series_names = ts_plot["series_name"].dropna().astype(str).unique().tolist()
                if not sel_prods and len(series_names) == 1:
                    s_df = ts_plot.sort_values("period_date")
                    fig_ts.add_trace(
                        go.Bar(
                            x=s_df["period_date"],
                            y=s_df["metric_y"],
                            name=y_lbl_main,
                            marker_color=palette.primary,
                            opacity=0.82,
                            customdata=s_df["active_store_days"],
                            hovertemplate=f"%{{x|%Y-%m-%d}}<br>{y_lbl_main}: %{{y:,.2f}}<br>CH-ngày (n): %{{customdata:,}}<extra></extra>",
                        ),
                        secondary_y=False,
                    )
                else:
                    for idx, sname in enumerate(series_names):
                        s_df = ts_plot[ts_plot["series_name"].astype(str) == sname].sort_values("period_date")
                        color = palette.discrete[idx % len(palette.discrete)]
                        fig_ts.add_trace(
                            go.Scatter(
                                x=s_df["period_date"],
                                y=s_df["metric_y"],
                                name=sname,
                                mode="lines+markers",
                                line=dict(color=color, width=2.2),
                                marker=dict(size=5),
                                customdata=s_df["active_store_days"],
                                hovertemplate=f"{sname}<br>%{{x|%Y-%m-%d}}<br>{y_lbl_main}: %{{y:,.2f}}<br>CH-ngày (n): %{{customdata:,}}<extra></extra>",
                            ),
                            secondary_y=False,
                        )

                # Weather overlay aggregated by period_date
                w_agg = (
                    ts_plot.groupby("period_date", as_index=False)[sel_w_col]
                    .mean()
                    .sort_values("period_date")
                )
                fig_ts.add_trace(
                    go.Scatter(
                        x=w_agg["period_date"],
                        y=w_agg[sel_w_col],
                        name=w_line_opts[sel_w_col],
                        mode="lines+markers",
                        line=dict(color=palette.accent, width=2.3, dash="dot"),
                        marker=dict(size=5),
                        hovertemplate=f"%{{x|%Y-%m-%d}}<br>{w_line_opts[sel_w_col]}: %{{y:.2f}}<extra></extra>",
                    ),
                    secondary_y=True,
                )
                style_plotly(fig_ts, palette, height=340, xaxis_title=f"Thời gian ({time_grain_label(sel_grain)})")
                fig_ts.update_yaxes(title_text=y_lbl_main, secondary_y=False)
                fig_ts.update_yaxes(title_text=w_line_opts[sel_w_col], secondary_y=True, showgrid=False)
                st.plotly_chart(fig_ts, width="stretch", theme=None, config=plotly_config())

        # Row 4: Compact Tabs (Humidity & Weekend | Daily Temp Scatter | Top 15 Rain | Weekday | Lookup Table)
        tab_hum, tab_scat, tab_top15, tab_dow, tab_tbl = st.tabs(
            [
                "Độ Ẩm & Cuối Tuần",
                "Nhiệt Độ Ngày",
                "Top 15 Thuốc Theo Mưa",
                "Thứ Trong Tuần",
                "Bảng Tra Cứu Ngày",
            ]
        )

        with tab_hum:
            with st.container(border=True):
                render_chart_header(
                    f"{metric_title_short} Theo Độ Ẩm & Cuối Tuần",
                    "So sánh ngày thường vs cuối tuần trên cùng thước đo đã chọn",
                    info_tooltip="Tách riêng ngày thường và cuối tuần theo từng mức độ ẩm để tránh nhiễu lịch nghỉ cuối tuần.",
                )
                hum_sql, hum_params = sql_humidity_weekend(schema, filters)
                hum_df = db.run_query_df(hum_sql, hum_params)
                if hum_df.empty:
                    render_empty_state()
                else:
                    hum_plot = hum_df.copy()
                    hum_plot["plot_val"] = pd.to_numeric(hum_plot[metric_col], errors="coerce") * val_scale
                    hum_plot["hum_vi"] = hum_plot["humidity_band"].map(humidity_label)
                    hum_plot["weekend_vi"] = hum_plot["is_weekend"].map(weekend_label)
                    hum_order_vi = [humidity_label(h) for h in HUMIDITY_BAND_ORDER if h in set(hum_plot["humidity_band"])]
                    fig_hum = px.bar(
                        hum_plot,
                        x="hum_vi",
                        y="plot_val",
                        color="weekend_vi",
                        barmode="group",
                        text_auto=".2s",
                        hover_data={"active_store_days": ":,", "sold_qty": ":,.0f"},
                        category_orders={"hum_vi": hum_order_vi, "weekend_vi": ["Ngày thường", "Cuối tuần"]},
                        color_discrete_sequence=[palette.primary, palette.accent],
                    )
                    fig_hum.update_traces(
                        textposition="outside",
                        hovertemplate=(
                            "Độ ẩm: %{x}<br>Loại ngày: %{fullData.name}<br>"
                            f"{metric_title_short}: %{{y:,.2f}}<br>"
                            "CH-ngày (n): %{customdata[0]}<extra></extra>"
                        ),
                    )
                    style_plotly(
                        fig_hum,
                        palette,
                        height=360,
                        xaxis_title="Mức độ ẩm",
                        yaxis_title=metric_title_short,
                    )
                    max_hum_val = float(pd.to_numeric(hum_plot["plot_val"], errors="coerce").max() or 0.0)
                    polish_vertical_bar_headroom(fig_hum, max_hum_val)
                    fig_hum.update_layout(legend_title_text="Ngày trong tuần")
                    st.plotly_chart(fig_hum, width="stretch", theme=None, config=plotly_config())

        with tab_scat:
            with st.container(border=True):
                render_chart_header(
                    f"Nhiệt Độ TB Ngày vs {metric_title_short}",
                    "Mỗi điểm là 1 ngày × mức mưa; nhiệt độ TB tính ở cấp CH-ngày",
                )
                sc_sql, sc_params = sql_daily_temp_scatter(schema, filters)
                sc_df = db.run_query_df(sc_sql, sc_params)
                if sc_df.empty:
                    render_empty_state()
                else:
                    sc_plot = sc_df.copy()
                    sc_plot["plot_val"] = pd.to_numeric(sc_plot[metric_col], errors="coerce") * val_scale
                    sc_plot["rain_vi"] = sc_plot["rain_regime"].map(rain_label)
                    rain_order_vi = [rain_label(r) for r in RAIN_REGIME_ORDER if r in set(sc_plot["rain_regime"])]
                    fig_sc = px.scatter(
                        sc_plot,
                        x="temp_mean",
                        y="plot_val",
                        color="rain_vi",
                        category_orders={"rain_vi": rain_order_vi},
                        hover_data={"local_date": True, "active_stores": ":,", "line_count": ":,"},
                        color_discrete_sequence=list(palette.discrete),
                        opacity=0.78,
                    )
                    fig_sc.update_traces(
                        marker=dict(size=8),
                        hovertemplate=(
                            "Ngày: %{customdata[0]}<br>Nhiệt độ TB: %{x:.1f} °C<br>"
                            f"{metric_title_short}: %{{y:,.2f}}<br>"
                            "CH hoạt động: %{customdata[1]} · Dòng POS: %{customdata[2]}<extra></extra>"
                        ),
                    )
                    style_plotly(
                        fig_sc,
                        palette,
                        height=360,
                        xaxis_title="Nhiệt độ trung bình (°C)",
                        yaxis_title=metric_title_short,
                    )
                    fig_sc.update_layout(legend_title_text="Mức mưa")
                    st.plotly_chart(fig_sc, width="stretch", theme=None, config=plotly_config())

        with tab_top15:
            with st.container(border=True):
                prod_rank_by_rev = use_rev_instead_of_qty
                prod_val_col = "line_amount" if prod_rank_by_rev else "sold_qty"
                prod_scale = mult if prod_rank_by_rev else 1.0
                prod_unit_lbl = disp_ccy if prod_rank_by_rev else (uom_guard.single_uom or "ĐVT")
                render_chart_header(
                    f"Top 15 Sản Phẩm Theo {'Doanh Thu' if prod_rank_by_rev else 'Sản Lượng'} & Mức Mưa",
                    f"Xếp hạng theo {prod_unit_lbl} trong phạm vi bộ lọc hiện tại",
                )
                tp_sql, tp_params = sql_top_products_by_rain(
                    schema,
                    filters,
                    limit=15,
                    rank_by_revenue=prod_rank_by_rev,
                )
                tp_df = db.run_query_df(tp_sql, tp_params)
                if tp_df.empty:
                    render_empty_state()
                else:
                    tp_plot = tp_df.copy()
                    tp_plot["plot_val"] = pd.to_numeric(tp_plot[prod_val_col], errors="coerce") * prod_scale
                    tp_plot["plot_total"] = pd.to_numeric(tp_plot["total_metric"], errors="coerce") * prod_scale
                    tp_plot["rain_vi"] = tp_plot["rain_regime"].map(rain_label)
                    prod_order_desc = (
                        tp_plot.groupby("product_name", as_index=False)["plot_total"]
                        .max()
                        .sort_values("plot_total", ascending=False)["product_name"]
                        .tolist()
                    )
                    rain_order_vi = [rain_label(r) for r in RAIN_REGIME_ORDER if r in set(tp_plot["rain_regime"])]
                    fig_tp = px.bar(
                        tp_plot,
                        x="plot_val",
                        y="product_name",
                        color="rain_vi",
                        orientation="h",
                        hover_data={"active_store_days": ":,"},
                        category_orders={"rain_vi": rain_order_vi},
                        color_discrete_sequence=list(palette.discrete),
                    )
                    fig_tp.update_traces(
                        hovertemplate=(
                            "Sản phẩm: %{y}<br>Mức mưa: %{fullData.name}<br>"
                            f"Giá trị: %{{x:,.0f}} {prod_unit_lbl}<br>"
                            "CH-ngày (n): %{customdata[0]}<extra></extra>"
                        )
                    )
                    style_plotly(
                        fig_tp,
                        palette,
                        height=420,
                        xaxis_title=f"Giá trị ({prod_unit_lbl})",
                        yaxis_title="Sản phẩm",
                    )
                    max_total = float(pd.to_numeric(tp_plot["plot_total"], errors="coerce").max() or 0.0)
                    polish_horizontal_bar(fig_tp, prod_order_desc, max_total, right_margin=24)
                    fig_tp.update_layout(legend_title_text="Mức mưa")
                    st.plotly_chart(fig_tp, width="stretch", theme=None, config=plotly_config())

        with tab_dow:
            with st.container(border=True):
                render_chart_header(
                    f"{metric_title_short} Theo Thứ Trong Tuần & Mức Mưa",
                    "So sánh theo ngày trong tuần đã chuẩn hóa theo CH-ngày",
                )
                dow_sql, dow_params = sql_weekday_by_rain(schema, filters)
                dow_df = db.run_query_df(dow_sql, dow_params)
                if dow_df.empty:
                    render_empty_state()
                else:
                    dow_plot = dow_df.copy()
                    dow_plot["plot_val"] = pd.to_numeric(dow_plot[metric_col], errors="coerce") * val_scale
                    dow_plot["dow_vi"] = dow_plot["day_of_week_num"].map(
                        lambda n: DOW_VI_BY_NUM.get(int(n), str(n)) if pd.notna(n) else "Chưa rõ"
                    )
                    dow_plot["rain_vi"] = dow_plot["rain_regime"].map(rain_label)
                    dow_order = [
                        DOW_VI_BY_NUM[i]
                        for i in range(1, 8)
                        if i in set(dow_plot["day_of_week_num"].dropna().astype(int))
                    ]
                    rain_order_vi = [rain_label(r) for r in RAIN_REGIME_ORDER if r in set(dow_plot["rain_regime"])]
                    fig_dow = px.bar(
                        dow_plot,
                        x="dow_vi",
                        y="plot_val",
                        color="rain_vi",
                        barmode="group",
                        hover_data={"active_store_days": ":,"},
                        category_orders={"dow_vi": dow_order, "rain_vi": rain_order_vi},
                        color_discrete_sequence=list(palette.discrete),
                    )
                    fig_dow.update_traces(
                        hovertemplate=(
                            "Thứ: %{x}<br>Mức mưa: %{fullData.name}<br>"
                            f"{metric_title_short}: %{{y:,.2f}}<br>"
                            "CH-ngày (n): %{customdata[0]}<extra></extra>"
                        )
                    )
                    style_plotly(
                        fig_dow,
                        palette,
                        height=380,
                        xaxis_title="Thứ trong tuần",
                        yaxis_title=metric_title_short,
                    )
                    fig_dow.update_layout(legend_title_text="Mức mưa")
                    st.plotly_chart(fig_dow, width="stretch", theme=None, config=plotly_config())

        with tab_tbl:
            with st.container(border=True):
                render_chart_header(
                    "Bảng Tra Cứu Thời Tiết & Bán Hàng Theo Ngày",
                    "Chi tiết tối đa 500 dòng gần nhất trong phạm vi lọc",
                )
                by_store_uom = st.toggle(
                    "Mở rộng chi tiết theo từng Cửa hàng & Đơn vị tính",
                    value=False,
                    key="p2_daily_store_uom",
                )
                dt_sql, dt_params = sql_daily_weather_table(schema, filters, by_store_uom=by_store_uom, limit=500)
                dt_df = db.run_query_df(dt_sql, dt_params)
                if dt_df.empty:
                    render_empty_state()
                else:
                    rev_col_name = f"Doanh thu ({disp_ccy})" if disp_ccy else "Doanh thu"
                    rev_series = pd.to_numeric(dt_df["line_amount"], errors="coerce") * mult
                    rev_fmt = "%,.0f" if to_vnd else "%,.2f"
                    if by_store_uom:
                        show_df = pd.DataFrame(
                            {
                                "Ngày bán": dt_df["local_date"],
                                "Cửa hàng": dt_df["store_name"],
                                "Đơn vị tính": dt_df["clean_uom"],
                                "Mức nhiệt độ": dt_df["temp_band"].map(temp_label),
                                "Mức mưa": dt_df["rain_regime"].map(rain_label),
                                "Mức độ ẩm": dt_df["humidity_band"].map(humidity_label),
                                "Loại ngày": dt_df["is_weekend"].map(weekend_label),
                                "Sản lượng (theo ĐVT)": safe_round(dt_df["sold_qty"], 0),
                                "Số dòng POS": dt_df["line_count"],
                                "Nhiệt độ TB (°C)": safe_round(dt_df["temp_mean"], 2),
                                "Lượng mưa TB (mm)": safe_round(dt_df["precip_sum"], 2),
                                "Độ ẩm TB (%)": safe_round(dt_df["humidity_mean"], 1),
                                rev_col_name: safe_round(rev_series, 0 if to_vnd else 2),
                            }
                        )
                        col_cfg = {
                            "Ngày bán": st.column_config.DateColumn(format="YYYY-MM-DD"),
                            "Sản lượng (theo ĐVT)": st.column_config.NumberColumn(format="%,.0f"),
                            "Số dòng POS": st.column_config.NumberColumn(format="%,d"),
                            "Nhiệt độ TB (°C)": st.column_config.NumberColumn(format="%.2f"),
                            "Lượng mưa TB (mm)": st.column_config.NumberColumn(format="%.2f"),
                            "Độ ẩm TB (%)": st.column_config.NumberColumn(format="%.1f"),
                            rev_col_name: st.column_config.NumberColumn(format=rev_fmt),
                        }
                    elif use_rev_instead_of_qty:
                        rev_sd_series = safe_round(
                            rev_series / pd.to_numeric(dt_df["active_stores"], errors="coerce").replace(0, pd.NA),
                            0 if to_vnd else 2,
                        )
                        rev_sd_name = f"TB DT / CH-ngày ({disp_ccy})" if disp_ccy else "TB DT / CH-ngày"
                        show_df = pd.DataFrame(
                            {
                                "Ngày bán": dt_df["local_date"],
                                "Số CH có bán": dt_df["active_stores"],
                                "Số dòng POS": dt_df["line_count"],
                                rev_sd_name: rev_sd_series,
                                rev_col_name: safe_round(rev_series, 0 if to_vnd else 2),
                                "Nhiệt độ TB (°C)": safe_round(dt_df["temp_mean"], 2),
                                "Lượng mưa TB (mm)": safe_round(dt_df["precip_sum"], 2),
                                "Độ ẩm TB (%)": safe_round(dt_df["humidity_mean"], 1),
                            }
                        )
                        col_cfg = {
                            "Ngày bán": st.column_config.DateColumn(format="YYYY-MM-DD"),
                            "Số CH có bán": st.column_config.NumberColumn(format="%,d"),
                            "Số dòng POS": st.column_config.NumberColumn(format="%,d"),
                            rev_sd_name: st.column_config.NumberColumn(format=rev_fmt),
                            rev_col_name: st.column_config.NumberColumn(format=rev_fmt),
                            "Nhiệt độ TB (°C)": st.column_config.NumberColumn(format="%.2f"),
                            "Lượng mưa TB (mm)": st.column_config.NumberColumn(format="%.2f"),
                            "Độ ẩm TB (%)": st.column_config.NumberColumn(format="%.1f"),
                        }
                    else:
                        show_df = pd.DataFrame(
                            {
                                "Ngày bán": dt_df["local_date"],
                                "Số CH có bán": dt_df["active_stores"],
                                "Số dòng POS": dt_df["line_count"],
                                "TB SL / CH-ngày": safe_round(dt_df["qty_per_store_day"], 2),
                                "Tổng sản lượng": safe_round(dt_df["sold_qty"], 0),
                                "Nhiệt độ TB (°C)": safe_round(dt_df["temp_mean"], 2),
                                "Lượng mưa TB (mm)": safe_round(dt_df["precip_sum"], 2),
                                "Độ ẩm TB (%)": safe_round(dt_df["humidity_mean"], 1),
                                rev_col_name: safe_round(rev_series, 0 if to_vnd else 2),
                            }
                        )
                        col_cfg = {
                            "Ngày bán": st.column_config.DateColumn(format="YYYY-MM-DD"),
                            "Số CH có bán": st.column_config.NumberColumn(format="%,d"),
                            "Số dòng POS": st.column_config.NumberColumn(format="%,d"),
                            "TB SL / CH-ngày": st.column_config.NumberColumn(format="%,.2f"),
                            "Tổng sản lượng": st.column_config.NumberColumn(format="%,.0f"),
                            "Nhiệt độ TB (°C)": st.column_config.NumberColumn(format="%.2f"),
                            "Lượng mưa TB (mm)": st.column_config.NumberColumn(format="%.2f"),
                            "Độ ẩm TB (%)": st.column_config.NumberColumn(format="%.1f"),
                            rev_col_name: st.column_config.NumberColumn(format=rev_fmt),
                        }
                    st.dataframe(
                        show_df,
                        width="stretch",
                        hide_index=True,
                        height=300,
                        column_config=col_cfg,
                    )
                    render_csv_download(show_df, "thoi_tiet_ban_hang_theo_ngay.csv", key="p2_csv_daily")

        render_scope_strip(
            "Lưu ý phương pháp: Dữ liệu chỉ phản ánh các ngày có phát sinh bán (sold_qty > 0). Mọi mối liên hệ thời tiết mang tính quan sát, không kết luận nhân quả."
        )

    if drawer_col is not None:
        render_right_explanation_panel(
            drawer_col,
            page_key="p2",
            page_title="Thời Tiết & Mùa Vụ",
            glossary_items=[
                ("CH-ngày (Store-Day)", "Một cặp (Cửa hàng, Ngày) có phát sinh giao dịch bán (`sold_qty > 0`). Chuẩn hóa theo CH-ngày giúp không bị lệch giữa tháng dài/ngắn hay cụm đông/ít cửa hàng."),
                ("Tỷ lệ độ phủ", "`active_store_days / (số cửa hàng hoạt động × số ngày trong phạm vi lọc)`."),
                ("Cỡ mẫu n ≥ 30", "Ô nhiệt độ × mưa có dưới 30 CH-ngày mang ký hiệu `⚠` — dễ biến động ngẫu nhiên do ít ngày quan sát."),
                ("Không có ngày bán = 0", "Gold mirror (`bi_sales_weather_enriched`) không ghi dòng nào cho ngày đóng cửa hoặc bán 0, nên trung bình phản ánh cường độ bán trên ngày có giao dịch."),
                ("Tiền Việt (VNĐ ₫)", vnd_rate_note(ccy, True)),
            ],
            extra_notes=list(insight_bullets),
        )


render_page(get_current_filters())
