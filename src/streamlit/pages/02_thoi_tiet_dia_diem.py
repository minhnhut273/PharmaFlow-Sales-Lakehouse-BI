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
    TRACK_META,
    fmt_compact,
    fmt_currency,
    fmt_int,
    humidity_label,
    rain_label,
    safe_round,
    temp_label,
    weekend_label,
)
import db
from queries import (
    FilterState,
    sql_daily_temp_scatter,
    sql_daily_weather_table,
    sql_humidity_weekend,
    sql_monthly_weather_seasonality,
    sql_temp_rain_heatmap,
    sql_top_products_by_rain,
    sql_uom_breakdown,
    sql_weather_kpis,
    sql_weekday_by_rain,
)
from ui import (
    get_active_palette,
    plotly_config,
    polish_horizontal_bar,
    polish_vertical_bar_headroom,
    render_active_filter_bar,
    render_chart_header,
    render_csv_download,
    render_empty_state,
    render_insight_box,
    render_kpi_card,
    render_page_header,
    render_scope_strip,
    style_plotly,
)


def _set_heatmap_cell(temp_band: str | None, rain_regime: str | None) -> None:
    st.session_state["p2_cell_temp"] = temp_band
    st.session_state["p2_cell_rain"] = rain_regime


def _clear_page2_filters() -> None:
    st.session_state["p2_rain_regimes"] = []
    st.session_state["p2_humidity_bands"] = []
    st.session_state["p2_cell_temp"] = None
    st.session_state["p2_cell_rain"] = None


def render_page(global_filters: FilterState) -> None:
    schema = db.get_active_schema()
    palette = get_active_palette()
    meta = TRACK_META.get(global_filters.dataset_track or "")
    ccy = meta.currency_code if meta else None
    has_rev = bool(meta.has_revenue) if meta else False
    prov_class = meta.provenance_class if meta else "SYNTHETIC"

    bounds = get_track_bounds()
    uoms_avail = bounds.get("uoms_avail") or ()

    st.session_state.setdefault("p2_cell_temp", None)
    st.session_state.setdefault("p2_cell_rain", None)
    st.session_state.setdefault("p2_rain_regimes", [])
    st.session_state.setdefault("p2_humidity_bands", [])

    render_page_header(
        "Thời Tiết & Địa Điểm (Mối Liên Hệ Quan Sát)",
        "Đối chiếu mối liên hệ quan sát giữa nhiệt độ, lượng mưa, độ ẩm với tốc độ bán chuẩn hóa theo Cửa hàng-Ngày có bán.",
        dataset_track=global_filters.dataset_track,
        extra_pills=[
            ("Không bao gồm ngày bán bằng 0", "warn"),
            ("Không suy diễn nhân quả", "default"),
        ],
    )

    uom_guard = evaluate_uom_compatibility(global_filters.dataset_track, global_filters.clean_uoms, uoms_avail)
    use_rev_instead_of_qty = bool(uom_guard.is_multi_uom_blocked and has_rev)

    if uom_guard.is_multi_uom_blocked:
        st.warning(
            f"{uom_guard.message} "
            + (f"Trên trang này, các biểu đồ so sánh sẽ dùng **Doanh thu ({ccy}) / CH-ngày** thay cho cộng gộp sản lượng." if has_rev else ""),
            icon="⚠️",
        )
        uom_sql, uom_params = sql_uom_breakdown(schema, global_filters)
        uom_df = db.run_query_df(uom_sql, uom_params)
        top_uoms = uom_df["clean_uom"].dropna().head(5).tolist() if not uom_df.empty else []
        if top_uoms:
            cols_u = st.columns([2] + [1.2] * len(top_uoms))
            with cols_u[0]:
                st.caption("Chọn nhanh 1 ĐVT để phân tích sản lượng chuẩn:")
            for idx, u in enumerate(top_uoms):
                with cols_u[idx + 1]:
                    st.button(
                        f"ĐVT: {u}",
                        key=f"p2_pick_uom_{idx}",
                        width="stretch",
                        on_click=set_global_uoms,
                        args=([str(u)],),
                    )

    # Pre-fetch heatmap grid using Trang 2's rain/humidity filters (ignoring cell selection itself)
    pre_rain = tuple(st.session_state.get("p2_rain_regimes", ()))
    pre_hum = tuple(st.session_state.get("p2_humidity_bands", ()))
    base_hm_filters = replace(global_filters, rain_regimes=pre_rain, humidity_bands=pre_hum)
    hm_sql, hm_params = sql_temp_rain_heatmap(schema, base_hm_filters)
    hm_df = db.run_query_df(hm_sql, hm_params)

    # Page-2-only controls
    with st.container(border=True):
        wc1, wc2, wc3 = st.columns([4, 4, 4])
        with wc1:
            rain_sel = st.multiselect(
                "Mức mưa (chỉ áp dụng Trang 2)",
                options=[r for r in RAIN_REGIME_ORDER if r != "Unknown"],
                format_func=rain_label,
                placeholder="Tất cả mức mưa",
                key="p2_rain_regimes",
            )
        with wc2:
            hum_sel = st.multiselect(
                "Mức độ ẩm (chỉ áp dụng Trang 2)",
                options=[h for h in HUMIDITY_BAND_ORDER if h != "Unknown"],
                format_func=humidity_label,
                placeholder="Tất cả mức độ ẩm",
                key="p2_humidity_bands",
            )
        with wc3:
            metric_mode = st.radio(
                "Thước đo biểu đồ thời tiết",
                options=["normalized", "total"],
                format_func=lambda m: (
                    f"Chuẩn hóa / CH-ngày ({ccy or 'ĐVT'}) — Khuyên dùng"
                    if m == "normalized"
                    else "Tổng tích lũy (dễ lệch do khác số ngày/CH)"
                ),
                key="p2_metric_mode",
            )

        cs1, cs2, cs3 = st.columns([3.5, 3.5, 5])
        temp_opts = [None] + [t for t in TEMP_BAND_ORDER if t != "Unknown"]
        rain_opts = [None] + [r for r in RAIN_REGIME_ORDER if r != "Unknown"]
        with cs1:
            cell_temp = st.selectbox(
                "Ô Nhiệt độ (chỉ Trang 2)",
                options=temp_opts,
                format_func=lambda x: "Tất cả mức nhiệt độ" if x is None else temp_label(x),
                key="p2_cell_temp",
            )
        with cs2:
            cell_rain = st.selectbox(
                "Ô Mức mưa (chỉ Trang 2)",
                options=rain_opts,
                format_func=lambda x: "Tất cả mức mưa" if x is None else rain_label(x),
                key="p2_cell_rain",
            )
        with cs3:
            st.markdown("<div style='font-size:0.8rem;color:#546477;margin-bottom:5px;'>Chọn nhanh ô thời tiết đủ mẫu (n ≥ 30 CH-ngày) hoặc xóa lọc Trang 2</div>", unsafe_allow_html=True)
            if cell_temp or cell_rain or rain_sel or hum_sel:
                bcol1, bcol2 = st.columns([3.2, 1.8])
                with bcol1:
                    t_txt = temp_label(cell_temp) if cell_temp else "Mọi nhiệt độ"
                    r_txt = rain_label(cell_rain) if cell_rain else "Mọi mức mưa"
                    st.info(f"Đang khoanh Trang 2: {t_txt} × {r_txt}")
                with bcol2:
                    st.button("Xóa lọc Trang 2", width="stretch", on_click=_clear_page2_filters, key="p2_clear_all")
            else:
                st.caption("Gợi ý ô phổ biến (xếp theo tốc độ chuẩn hóa / CH-ngày):")

        if not (cell_temp or cell_rain) and not hm_df.empty:
            rate_col_hm = "rev_per_store_day" if use_rev_instead_of_qty else "qty_per_store_day"
            eligible = hm_df[hm_df["active_store_days"].fillna(0) >= SMALL_SAMPLE_STORE_DAYS]
            top_cells = (eligible if not eligible.empty else hm_df).sort_values(rate_col_hm, ascending=False).head(4)
            qcols = st.columns(len(top_cells))
            for idx, (_, crow) in enumerate(top_cells.iterrows()):
                t_raw = str(crow["temp_band"])
                r_raw = str(crow["rain_regime"])
                t_short = temp_label(t_raw).split("(")[0].strip()
                r_short = rain_label(r_raw).split("(")[0].strip()
                rate_txt = fmt_compact(crow[rate_col_hm], decimals=1)
                n_sd = int(crow["active_store_days"] or 0)
                with qcols[idx]:
                    st.button(
                        f"{t_short} × {r_short} ({rate_txt} · n={n_sd:,})",
                        width="stretch",
                        key=f"p2_quick_cell_{idx}",
                        on_click=_set_heatmap_cell,
                        args=(t_raw, r_raw),
                    )

    filters = replace(
        global_filters,
        rain_regimes=tuple(rain_sel),
        humidity_bands=tuple(hum_sel),
        heatmap_temp_band=cell_temp,
        heatmap_rain_regime=cell_rain,
    )

    local_tags: list[str] = []
    if rain_sel:
        local_tags.append(f"Trang 2 Mưa: {', '.join(rain_label(r) for r in rain_sel)}")
    if hum_sel:
        local_tags.append(f"Trang 2 Độ ẩm: {', '.join(humidity_label(h) for h in hum_sel)}")
    if cell_temp or cell_rain:
        local_tags.append(
            f"Trang 2 Ô: {temp_label(cell_temp) if cell_temp else 'Mọi T°'} × {rain_label(cell_rain) if cell_rain else 'Mọi mưa'}"
        )
    render_active_filter_bar(global_filters, local_tags=local_tags)

    # Determine metric column & titles cleanly (normalized vs reference total, revenue fallback if multi-UOM)
    is_norm = metric_mode == "normalized"
    if use_rev_instead_of_qty:
        metric_col = "rev_per_store_day" if is_norm else "line_amount"
        metric_unit = ccy
        metric_title_short = f"Doanh thu / CH-ngày ({ccy})" if is_norm else f"Tổng doanh thu ({ccy})"
        metric_noun = "doanh thu / CH-ngày" if is_norm else "tổng doanh thu"
    else:
        metric_col = "qty_per_store_day" if is_norm else "sold_qty"
        metric_unit = uom_guard.single_uom
        unit_suffix = f" ({metric_unit})" if metric_unit else ""
        metric_title_short = f"Sản lượng / CH-ngày{unit_suffix}" if is_norm else f"Tổng sản lượng{unit_suffix}"
        metric_noun = f"sản lượng / CH-ngày{unit_suffix}" if is_norm else f"tổng sản lượng{unit_suffix}"

    # KPI query (store-day weather averages & coverage)
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

    # Insights box computed from normalized store-day rates across hm_df (sufficient sample size >= 30)
    hm_norm_col = "rev_per_store_day" if use_rev_instead_of_qty else "qty_per_store_day"
    insight_bullets = build_weather_insights(
        hm_df=hm_df,
        metric_col=hm_norm_col,
        metric_unit=metric_unit,
        metric_noun=f"doanh thu / CH-ngày ({ccy})" if use_rev_instead_of_qty else f"sản lượng / CH-ngày ({uom_guard.single_uom or 'ĐVT'})",
        provenance_class=prov_class,
        active_store_days=active_sd,
        possible_store_days=possible_sd,
    )
    render_insight_box("Nhận xét thời tiết từ dữ liệu chuẩn hóa", insight_bullets)

    # Row 1: 4 KPI cards
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card(
            "Quy Mô Quan Sát (Cửa Hàng-Ngày)",
            f"{fmt_int(active_sd)} CH-ngày",
            "Chỉ tính ngày có phát sinh bán (không gồm ngày bán bằng 0).",
            tag="Mẫu số",
            accent=palette.primary,
            delta_text=f"{active_stores} CH · {active_dates} ngày · Phủ {cov_pct:.1f}%",
            delta_tone="neutral",
        )
    with k2:
        if use_rev_instead_of_qty:
            k2_title = f"Doanh Thu TB / CH-Ngày ({ccy})"
            k2_val = fmt_currency(rev_per_sd, ccy) if active_sd > 0 else "Không có dữ liệu"
            k2_delta = f"Tổng doanh thu kỳ lọc: {fmt_currency(total_rev, ccy)}"
            k2_sub = "Dùng doanh thu chuẩn hóa vì nguồn đang chọn nhiều ĐVT."
        else:
            k2_title = f"Sản Lượng TB / CH-Ngày ({uom_guard.single_uom or 'ĐVT'})"
            k2_val = f"{float(qty_per_sd):,.2f}" if (active_sd > 0 and pd.notna(qty_per_sd)) else "Không có dữ liệu"
            k2_delta = f"Tổng sản lượng kỳ lọc: {fmt_compact(total_qty)}"
            k2_sub = "Tổng lượng bán chia số (cửa hàng × ngày) phát sinh giao dịch."
        render_kpi_card(
            k2_title,
            k2_val,
            k2_sub,
            tag="Chuẩn hóa",
            accent=palette.accent,
            delta_text=k2_delta,
            delta_tone="neutral",
        )
    with k3:
        render_kpi_card(
            "Nhiệt Độ TB (Cấp CH-Ngày)",
            f"{float(avg_temp):.2f} °C" if pd.notna(avg_temp) else "Không có dữ liệu",
            "Trung bình không trọng số theo từng (cửa hàng, ngày) từ Open-Meteo.",
            tag="°C",
            accent=palette.discrete[2],
            delta_text=f"Cảm nhận oi bức: {float(avg_app_temp):.2f} °C · Phủ TT {w_cov_pct:.1f}%" if pd.notna(avg_app_temp) else f"Phủ TT {w_cov_pct:.1f}%",
            delta_tone="neutral",
        )
    with k4:
        render_kpi_card(
            "Lượng Mưa TB (Cấp CH-Ngày)",
            f"{float(avg_precip):.2f} mm" if pd.notna(avg_precip) else "Không có dữ liệu",
            "Trung bình không trọng số theo từng (cửa hàng, ngày) phát sinh bán.",
            tag="mm",
            accent=palette.discrete[3],
            delta_text=f"Ngày có mưa (>0 mm): {rainy_sd:,}/{active_sd:,} ({rainy_share:.1f}%)",
            delta_tone="neutral",
        )

    # Row 2: Full-width Weather Heatmap (normalized + sample count)
    with st.container(border=True):
        render_chart_header(
            f"{metric_title_short} Theo Nhiệt Độ × Mức Mưa",
            "Hiển thị giá trị kèm cỡ mẫu n = số cửa hàng-ngày có bán (⚠ đánh dấu ô cỡ mẫu < 30 CH-ngày)",
        )
        render_scope_strip(
            "Phương pháp: Mỗi ô chia cho số (cửa hàng × ngày) có phát sinh bán thực tế trong ô đó; ô viền đen = ô đang khoanh lọc tại Trang 2."
        )
        if hm_df.empty:
            render_empty_state()
        else:
            temp_order_raw = [b for b in TEMP_BAND_ORDER if b in set(hm_df["temp_band"])]
            rain_order_raw = [r for r in RAIN_REGIME_ORDER if r in set(hm_df["rain_regime"])]
            piv_val = (
                hm_df.pivot(index="rain_regime", columns="temp_band", values=metric_col)
                .reindex(index=rain_order_raw, columns=temp_order_raw)
            )
            piv_n = (
                hm_df.pivot(index="rain_regime", columns="temp_band", values="active_store_days")
                .reindex(index=rain_order_raw, columns=temp_order_raw)
            )
            piv_raw = (
                hm_df.pivot(index="rain_regime", columns="temp_band", values="line_amount" if use_rev_instead_of_qty else "sold_qty")
                .reindex(index=rain_order_raw, columns=temp_order_raw)
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
                        v_fmt = fmt_compact(v, decimals=1 if is_norm else 1)
                        t_row.append(f"{v_fmt}<br><span style='font-size:10px'>n={n_int:,}{warn}</span>")
                        c_row.append([f"{v:,.2f}", f"{n_int:,}", fmt_compact(raw_v), f"< {SMALL_SAMPLE_STORE_DAYS} CH-ngày (mẫu nhỏ)" if warn else "Đủ mẫu tham khảo"])
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
                    textfont=dict(size=11.5),
                    colorscale=list(palette.continuous_scale),
                    colorbar=dict(title=metric_title_short, thickness=14),
                    hoverongaps=False,
                    hovertemplate=(
                        "Nhiệt độ: %{x}<br>Mức mưa: %{y}<br>"
                        f"{metric_title_short}: %{{customdata[0]}}<br>"
                        "Số CH-ngày có bán (n): %{customdata[1]}<br>"
                        "Tổng cộng ô này: %{customdata[2]}<br>"
                        "Độ tin cậy mẫu: %{customdata[3]}<extra></extra>"
                    ),
                )
            )
            if cell_temp in piv_val.columns and cell_rain in piv_val.index:
                xi = list(piv_val.columns).index(cell_temp)
                yi = list(piv_val.index).index(cell_rain)
                fig_hm.add_shape(
                    type="rect",
                    x0=xi - 0.5,
                    x1=xi + 0.5,
                    y0=yi - 0.5,
                    y1=yi + 0.5,
                    line=dict(color="#111827", width=3),
                )
            style_plotly(
                fig_hm,
                palette,
                height=355,
                show_legend=False,
                xaxis_title="Mức nhiệt độ",
                yaxis_title="Mức mưa",
            )
            fig_hm.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_hm, width="stretch", theme=None, config=plotly_config())

    # Row 3: Humidity x Weekend (6) + Daily Temp Scatter (6)
    col_hum, col_scat = st.columns([6, 6], gap="medium")

    with col_hum:
        with st.container(border=True):
            render_chart_header(
                f"{metric_title_short} Theo Độ Ẩm & Cuối Tuần",
                "So sánh ngày thường vs cuối tuần trên cùng thước đo đã chọn (kèm số CH-ngày ở hover)",
            )
            hum_sql, hum_params = sql_humidity_weekend(schema, filters)
            hum_df = db.run_query_df(hum_sql, hum_params)
            if hum_df.empty:
                render_empty_state()
            else:
                hum_df = hum_df.copy()
                hum_df["hum_vi"] = hum_df["humidity_band"].map(humidity_label)
                hum_df["weekend_vi"] = hum_df["is_weekend"].map(weekend_label)
                hum_order_vi = [humidity_label(h) for h in HUMIDITY_BAND_ORDER if h in set(hum_df["humidity_band"])]
                fig_hum = px.bar(
                    hum_df,
                    x="hum_vi",
                    y=metric_col,
                    color="weekend_vi",
                    barmode="group",
                    text_auto=".2s" if is_norm else ".3s",
                    hover_data={"active_store_days": ":,", "sold_qty": ":,.0f"},
                    category_orders={"hum_vi": hum_order_vi, "weekend_vi": ["Ngày thường", "Cuối tuần"]},
                    color_discrete_sequence=[palette.primary, palette.accent],
                )
                fig_hum.update_traces(
                    textposition="outside",
                    hovertemplate=(
                        "Độ ẩm: %{x}<br>Loại ngày: %{fullData.name}<br>"
                        f"{metric_title_short}: %{{y:,.2f}}<br>"
                        "Số CH-ngày có bán (n): %{customdata[0]}<extra></extra>"
                    ),
                )
                style_plotly(
                    fig_hum,
                    palette,
                    height=370,
                    xaxis_title="Mức độ ẩm",
                    yaxis_title=metric_title_short,
                )
                max_hum_val = float(pd.to_numeric(hum_df[metric_col], errors="coerce").max() or 0.0)
                polish_vertical_bar_headroom(fig_hum, max_hum_val)
                fig_hum.update_layout(legend_title_text="Ngày trong tuần")
                st.plotly_chart(fig_hum, width="stretch", theme=None, config=plotly_config())

    with col_scat:
        with st.container(border=True):
            render_chart_header(
                f"Nhiệt Độ TB Ngày vs {metric_title_short}",
                "Mỗi điểm là 1 ngày × chế độ mưa; nhiệt độ TB tính từ cấp cửa hàng-ngày",
            )
            sc_sql, sc_params = sql_daily_temp_scatter(schema, filters)
            sc_df = db.run_query_df(sc_sql, sc_params)
            if sc_df.empty:
                render_empty_state()
            else:
                sc_df = sc_df.copy()
                sc_df["rain_vi"] = sc_df["rain_regime"].map(rain_label)
                rain_order_vi = [rain_label(r) for r in RAIN_REGIME_ORDER if r in set(sc_df["rain_regime"])]
                fig_sc = px.scatter(
                    sc_df,
                    x="temp_mean",
                    y=metric_col,
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
                        "Số CH hoạt động: %{customdata[1]} · Số dòng POS: %{customdata[2]}<extra></extra>"
                    ),
                )
                style_plotly(
                    fig_sc,
                    palette,
                    height=370,
                    xaxis_title="Nhiệt độ trung bình (°C)",
                    yaxis_title=metric_title_short,
                )
                fig_sc.update_layout(legend_title_text="Mức mưa")
                st.plotly_chart(fig_sc, width="stretch", theme=None, config=plotly_config())

    # Row 4: Full-width Monthly Weather Seasonality vs Normalized Sales Rate (does not duplicate Page 1!)
    with st.container(border=True):
        render_chart_header(
            f"Mùa Vụ Thời Tiết Theo Tháng vs {metric_title_short}",
            "Đối chiếu tháng mưa nhiều/ít, nhiệt độ oi bức (apparent temp) và cường độ bán trung bình / cửa hàng-ngày",
        )
        ws_sql, ws_params = sql_monthly_weather_seasonality(schema, filters)
        ws_df = db.run_query_df(ws_sql, ws_params)
        if ws_df.empty:
            render_empty_state()
        else:
            w_line_opts = {
                "avg_apparent_temp_mean": "Nhiệt độ cảm nhận / Oi bức (°C)",
                "avg_temp_mean": "Nhiệt độ trung bình (°C)",
                "avg_precip_sum": "Lượng mưa trung bình ngày (mm)",
                "avg_humidity_mean": "Độ ẩm trung bình (%)",
            }
            if st.session_state.get("p2_weather_line") not in w_line_opts:
                st.session_state["p2_weather_line"] = "avg_apparent_temp_mean"
            sel_w_col = st.radio(
                "Biến thời tiết đối chiếu (đường)",
                options=list(w_line_opts.keys()),
                format_func=lambda k: w_line_opts[k],
                horizontal=True,
                key="p2_weather_line",
            )
            ws_norm_col = "rev_per_store_day" if use_rev_instead_of_qty else "qty_per_store_day"
            ws_bar_lbl = f"Doanh thu / CH-ngày ({ccy})" if use_rev_instead_of_qty else f"Sản lượng / CH-ngày ({uom_guard.single_uom or 'ĐVT'})"

            fig_ws = make_subplots(specs=[[{"secondary_y": True}]])
            fig_ws.add_trace(
                go.Bar(
                    x=ws_df["year_month"],
                    y=ws_df[ws_norm_col],
                    name=ws_bar_lbl,
                    marker_color=palette.primary,
                    opacity=0.82,
                    customdata=list(zip(ws_df["active_store_days"], ws_df["active_days"])),
                    hovertemplate=(
                        "Tháng %{x|%m/%Y}<br>"
                        f"{ws_bar_lbl}: %{{y:,.2f}}<br>"
                        "Cỡ mẫu: %{customdata[0]:,} CH-ngày (%{customdata[1]} ngày)<extra></extra>"
                    ),
                ),
                secondary_y=False,
            )
            fig_ws.add_trace(
                go.Scatter(
                    x=ws_df["year_month"],
                    y=ws_df[sel_w_col],
                    name=w_line_opts[sel_w_col],
                    mode="lines+markers",
                    line=dict(color=palette.accent, width=2.4),
                    marker=dict(size=5),
                    hovertemplate=f"Tháng %{{x|%m/%Y}}<br>{w_line_opts[sel_w_col]}: %{{y:.2f}}<extra></extra>",
                ),
                secondary_y=True,
            )
            style_plotly(fig_ws, palette, height=320, xaxis_title="Tháng")
            fig_ws.update_yaxes(title_text=ws_bar_lbl, secondary_y=False)
            fig_ws.update_yaxes(title_text=w_line_opts[sel_w_col], secondary_y=True, showgrid=False)
            st.plotly_chart(fig_ws, width="stretch", theme=None, config=plotly_config())

    # Row 5: Top 15 Products by Rain (6) + Weekday x Rain (6)
    col_top15, col_dow = st.columns([6, 6], gap="medium")

    with col_top15:
        with st.container(border=True):
            prod_rank_by_rev = use_rev_instead_of_qty
            prod_val_col = "line_amount" if prod_rank_by_rev else "sold_qty"
            prod_unit_lbl = ccy if prod_rank_by_rev else (uom_guard.single_uom or "ĐVT")
            render_chart_header(
                f"Top 15 Sản Phẩm Theo {'Doanh Thu' if prod_rank_by_rev else 'Sản Lượng'} & Mức Mưa",
                f"Xếp hạng theo {prod_unit_lbl} trong phạm vi bộ lọc hiện tại (không trộn ĐVT)",
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
                tp_df = tp_df.copy()
                tp_df["rain_vi"] = tp_df["rain_regime"].map(rain_label)
                prod_order_desc = (
                    tp_df.groupby("product_name", as_index=False)["total_metric"]
                    .max()
                    .sort_values("total_metric", ascending=False)["product_name"]
                    .tolist()
                )
                rain_order_vi = [rain_label(r) for r in RAIN_REGIME_ORDER if r in set(tp_df["rain_regime"])]
                fig_tp = px.bar(
                    tp_df,
                    x=prod_val_col,
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
                    height=440,
                    xaxis_title=f"Giá trị ({prod_unit_lbl})",
                    yaxis_title="Sản phẩm",
                )
                max_total = float(pd.to_numeric(tp_df["total_metric"], errors="coerce").max() or 0.0)
                polish_horizontal_bar(fig_tp, prod_order_desc, max_total, right_margin=24)
                fig_tp.update_layout(legend_title_text="Mức mưa")
                st.plotly_chart(fig_tp, width="stretch", theme=None, config=plotly_config())

    with col_dow:
        with st.container(border=True):
            render_chart_header(
                f"{metric_title_short} Theo Thứ Trong Tuần & Mức Mưa",
                "So sánh theo ngày trong tuần đã chuẩn hóa theo CH-ngày (kèm n CH-ngày ở hover)",
            )
            dow_sql, dow_params = sql_weekday_by_rain(schema, filters)
            dow_df = db.run_query_df(dow_sql, dow_params)
            if dow_df.empty:
                render_empty_state()
            else:
                dow_df = dow_df.copy()
                dow_df["dow_vi"] = dow_df["day_of_week_num"].map(
                    lambda n: DOW_VI_BY_NUM.get(int(n), str(n)) if pd.notna(n) else "Chưa rõ"
                )
                dow_df["rain_vi"] = dow_df["rain_regime"].map(rain_label)
                dow_order = [DOW_VI_BY_NUM[i] for i in range(1, 8) if i in set(dow_df["day_of_week_num"].dropna().astype(int))]
                rain_order_vi = [rain_label(r) for r in RAIN_REGIME_ORDER if r in set(dow_df["rain_regime"])]
                fig_dow = px.bar(
                    dow_df,
                    x="dow_vi",
                    y=metric_col,
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
                    height=440,
                    xaxis_title="Thứ trong tuần",
                    yaxis_title=metric_title_short,
                )
                fig_dow.update_layout(legend_title_text="Mức mưa")
                st.plotly_chart(fig_dow, width="stretch", theme=None, config=plotly_config())

    # Row 6 (Bottom): Detailed Lookup Table
    with st.container(border=True):
        render_chart_header(
            "Bảng Tra Cứu Thời Tiết & Bán Hàng Theo Ngày",
            "Bảng chi tiết đặt sau các phân tích chính (hiển thị Số dòng bán & CH có bán; chưa có dữ liệu đếm đơn duy nhất)",
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
            rev_col_name = f"Doanh thu ({ccy})" if ccy else "Doanh thu"
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
                        rev_col_name: safe_round(dt_df["line_amount"], 2),
                    }
                )
                col_cfg = {
                    "Ngày bán": st.column_config.DateColumn(format="YYYY-MM-DD"),
                    "Sản lượng (theo ĐVT)": st.column_config.NumberColumn(format="%,.0f"),
                    "Số dòng POS": st.column_config.NumberColumn(format="%,d"),
                    "Nhiệt độ TB (°C)": st.column_config.NumberColumn(format="%.2f"),
                    "Lượng mưa TB (mm)": st.column_config.NumberColumn(format="%.2f"),
                    "Độ ẩm TB (%)": st.column_config.NumberColumn(format="%.1f"),
                    rev_col_name: st.column_config.NumberColumn(format="%,.2f"),
                }
            elif use_rev_instead_of_qty:
                rev_sd_series = safe_round(
                    pd.to_numeric(dt_df["line_amount"], errors="coerce")
                    / pd.to_numeric(dt_df["active_stores"], errors="coerce").replace(0, pd.NA),
                    2,
                )
                rev_sd_name = f"TB DT / CH-ngày ({ccy})" if ccy else "TB DT / CH-ngày"
                show_df = pd.DataFrame(
                    {
                        "Ngày bán": dt_df["local_date"],
                        "Số CH có bán": dt_df["active_stores"],
                        "Số dòng POS": dt_df["line_count"],
                        rev_sd_name: rev_sd_series,
                        rev_col_name: safe_round(dt_df["line_amount"], 2),
                        "Nhiệt độ TB (°C)": safe_round(dt_df["temp_mean"], 2),
                        "Lượng mưa TB (mm)": safe_round(dt_df["precip_sum"], 2),
                        "Độ ẩm TB (%)": safe_round(dt_df["humidity_mean"], 1),
                    }
                )
                col_cfg = {
                    "Ngày bán": st.column_config.DateColumn(format="YYYY-MM-DD"),
                    "Số CH có bán": st.column_config.NumberColumn(format="%,d"),
                    "Số dòng POS": st.column_config.NumberColumn(format="%,d"),
                    rev_sd_name: st.column_config.NumberColumn(format="%,.2f"),
                    rev_col_name: st.column_config.NumberColumn(format="%,.2f"),
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
                        rev_col_name: safe_round(dt_df["line_amount"], 2),
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
                    rev_col_name: st.column_config.NumberColumn(format="%,.2f"),
                }
            st.dataframe(
                show_df,
                width="stretch",
                hide_index=True,
                height=300,
                column_config=col_cfg,
            )
            render_csv_download(show_df, "thoi_tiet_ban_hang_theo_ngay.csv", key="p2_csv_daily")

    with st.expander("Định nghĩa chỉ số & nguồn dữ liệu"):
        st.markdown(
            "- **Nguồn dữ liệu:** `bi_sales_weather_enriched` tại grain `Sản phẩm × Cửa hàng × Ngày`, kết hợp dữ liệu thời tiết ngày theo cửa hàng từ Open-Meteo.\n"
            "- **Phạm vi quan sát (`sold_qty > 0`):** Bảng chỉ lưu các ngày có phát sinh giao dịch bán (`active_store_days` = số cặp `(cửa hàng, ngày)` có bán), **không gồm các ngày đóng cửa hoặc ngày bán bằng 0**.\n"
            "- **Tỷ lệ độ phủ:** `active_store_days / (số cửa hàng hoạt động × số ngày trong phạm vi lọc)`.\n"
            "- **Sàng lọc cỡ mẫu (`n ≥ 30` cửa hàng-ngày):** Chỉ dùng để lọc các ô có quá ít lượt quan sát trước khi xếp hạng mô tả; không thay thế kiểm định ý nghĩa thống kê hay kết luận tác động nhân quả.\n"
            "- **Đơn hàng duy nhất (`Distinct Order`):** Chưa khả dụng tại Gold mirror do dữ liệu đã tổng hợp theo `SP × CH × Ngày`."
        )


render_page(get_current_filters())
