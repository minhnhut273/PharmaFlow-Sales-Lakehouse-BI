"""Page 2: Multi-Factor Weather & Location Deep-Dive (Thời Tiết & Địa Điểm)."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.filters import get_current_filters
from config import (
    DOW_VI_BY_NUM,
    HUMIDITY_BAND_ORDER,
    RAIN_REGIME_ORDER,
    TEMP_BAND_ORDER,
    TRACK_META,
    fmt_compact,
    fmt_int,
    humidity_label,
    rain_label,
    safe_round,
    temp_label,
    track_label,
    weekend_label,
)
from db import get_active_schema, run_query_df
from queries import (
    FilterState,
    sql_daily_temp_scatter,
    sql_daily_weather_table,
    sql_humidity_weekend,
    sql_monthly_track_trend,
    sql_temp_rain_heatmap,
    sql_top_products_by_rain,
    sql_weather_kpis,
    sql_weekday_by_rain,
)
from ui import (
    get_active_palette,
    plotly_config,
    polish_horizontal_bar,
    polish_vertical_bar_headroom,
    render_chart_header,
    render_csv_download,
    render_empty_state,
    render_kpi_card,
    render_page_header,
    style_plotly,
)


def _set_heatmap_cell(temp_band: str | None, rain_regime: str | None) -> None:
    st.session_state["p2_cell_temp"] = temp_band
    st.session_state["p2_cell_rain"] = rain_regime


def _clear_heatmap_cell() -> None:
    st.session_state["p2_cell_temp"] = None
    st.session_state["p2_cell_rain"] = None


def render_page(global_filters: FilterState) -> None:
    schema = get_active_schema()
    palette = get_active_palette()
    meta = TRACK_META.get(global_filters.dataset_track or "")
    ccy = meta.currency_code if meta else None

    st.session_state.setdefault("p2_cell_temp", None)
    st.session_state.setdefault("p2_cell_rain", None)

    render_page_header(
        "Thời Tiết & Địa Điểm (Đa Yếu Tố)",
        "Phân tích tác động đồng thời của nhiệt độ, lượng mưa, độ ẩm và ngày cuối tuần đến sản lượng tiêu thụ thuốc tại từng nhà thuốc.",
        dataset_track=global_filters.dataset_track,
        extra_pills=[
            ("Lọc chéo ô Nhiệt độ × Mức mưa", "default"),
            (
                f"Địa điểm: {', '.join(global_filters.stores[:2])}{'...' if len(global_filters.stores) > 2 else ''}"
                if global_filters.stores
                else "Tất cả địa điểm",
                "default",
            ),
        ],
    )

    # Fetch heatmap grid early (ignoring active cell) to populate quick-pick cell buttons deterministically
    pre_rain = tuple(st.session_state.get("p2_rain_regimes", ()))
    pre_hum = tuple(st.session_state.get("p2_humidity_bands", ()))
    base_hm_filters = replace(global_filters, rain_regimes=pre_rain, humidity_bands=pre_hum)
    hm_sql, hm_params = sql_temp_rain_heatmap(schema, base_hm_filters)
    hm_df = run_query_df(hm_sql, hm_params)

    # Sheet-level weather controls + deterministic Weather Cell Selector
    with st.container(border=True):
        wc1, wc2 = st.columns([6, 6])
        with wc1:
            rain_sel = st.multiselect(
                "Mức mưa (trang này)",
                options=[r for r in RAIN_REGIME_ORDER if r != "Unknown"],
                format_func=rain_label,
                placeholder="Tất cả mức mưa",
                key="p2_rain_regimes",
            )
        with wc2:
            hum_sel = st.multiselect(
                "Mức độ ẩm (trang này)",
                options=[h for h in HUMIDITY_BAND_ORDER if h != "Unknown"],
                format_func=humidity_label,
                placeholder="Tất cả mức độ ẩm",
                key="p2_humidity_bands",
            )

        st.markdown(
            "<div style='font-size:0.84rem;font-weight:700;margin:4px 0 6px 0;'>Chọn nhanh ô thời tiết (Nhiệt độ × Mức mưa) để lọc đồng loạt KPI, Top thuốc & Bảng ngày</div>",
            unsafe_allow_html=True,
        )
        cs1, cs2, cs3 = st.columns([3.5, 3.5, 5])
        temp_opts = [None] + [t for t in TEMP_BAND_ORDER if t != "Unknown"]
        rain_opts = [None] + [r for r in RAIN_REGIME_ORDER if r != "Unknown"]
        with cs1:
            cell_temp = st.selectbox(
                "Ô Nhiệt độ",
                options=temp_opts,
                format_func=lambda x: "Tất cả mức nhiệt độ" if x is None else temp_label(x),
                key="p2_cell_temp",
            )
        with cs2:
            cell_rain = st.selectbox(
                "Ô Mức mưa",
                options=rain_opts,
                format_func=lambda x: "Tất cả mức mưa" if x is None else rain_label(x),
                key="p2_cell_rain",
            )
        with cs3:
            st.markdown("<div style='font-size:0.82rem;color:#546477;margin-bottom:6px;'>Trạng thái lọc ô</div>", unsafe_allow_html=True)
            if cell_temp or cell_rain:
                bcol1, bcol2 = st.columns([3, 1.5])
                with bcol1:
                    t_txt = temp_label(cell_temp) if cell_temp else "Mọi nhiệt độ"
                    r_txt = rain_label(cell_rain) if cell_rain else "Mọi mức mưa"
                    st.success(f"{t_txt} × {r_txt}")
                with bcol2:
                    st.button("Xóa lọc ô", width="stretch", on_click=_clear_heatmap_cell, key="p2_clear_hm")
            else:
                st.caption("Hoặc bấm 1 nút gợi ý phổ biến ngay bên dưới:")

        if not (cell_temp or cell_rain) and not hm_df.empty:
            top_cells = hm_df.sort_values("sold_qty", ascending=False).head(4)
            qcols = st.columns(len(top_cells))
            for idx, (_, crow) in enumerate(top_cells.iterrows()):
                t_raw = str(crow["temp_band"])
                r_raw = str(crow["rain_regime"])
                t_short = temp_label(t_raw).split("(")[0].strip()
                r_short = rain_label(r_raw).split("(")[0].strip()
                label_short = f"{t_short} × {r_short} ({fmt_compact(crow['sold_qty'], decimals=1)})"
                with qcols[idx]:
                    st.button(
                        label_short,
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

    # Row 1: 4 Weather & Location KPIs
    wk_sql, wk_params = sql_weather_kpis(schema, filters)
    wk_df = run_query_df(wk_sql, wk_params)
    wrow = wk_df.iloc[0] if not wk_df.empty else {}

    active_stores = int(wrow.get("active_stores") or 0)
    avg_qty_store = wrow.get("avg_qty_per_store")
    avg_temp = wrow.get("avg_temp_mean")
    avg_precip = wrow.get("avg_precip_sum")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card(
            "Số Cửa Hàng Hoạt Động",
            fmt_int(active_stores) if active_stores > 0 else "0",
            "Số địa điểm nhà thuốc phát sinh bán hàng",
            tag="Địa điểm",
            accent=palette.primary,
        )
    with k2:
        render_kpi_card(
            "Sản Lượng TB / Cửa Hàng",
            fmt_compact(avg_qty_store) if active_stores > 0 else "—",
            "Tổng sản lượng chia cho số cửa hàng hoạt động",
            tag="TB / CH",
            accent=palette.accent,
        )
    with k3:
        render_kpi_card(
            "Nhiệt Độ Trung Bình Quan Sát",
            f"{float(avg_temp):.2f} °C" if avg_temp is not None else "—",
            "Nhiệt độ trung bình ngày từ Open-Meteo",
            tag="°C",
            accent=palette.discrete[2],
        )
    with k4:
        render_kpi_card(
            "Lượng Mưa Trung Bình",
            f"{float(avg_precip):.2f} mm" if avg_precip is not None else "—",
            "Lượng mưa trung bình ngày tại địa điểm",
            tag="mm",
            accent=palette.discrete[3],
        )

    # Row 2: Full-width Interactive Weather Heatmap (Nhiệt độ × Mức mưa)
    with st.container(border=True):
        render_chart_header(
            "Sản Lượng Bán Theo Nhiệt Độ × Mức Mưa",
            "Bản đồ nhiệt giao cắt dải nhiệt độ và chế độ mưa (khung đen = ô đang chọn ở thanh trên)",
        )
        if hm_df.empty:
            render_empty_state()
        else:
            temp_order_raw = [b for b in TEMP_BAND_ORDER if b in set(hm_df["temp_band"])]
            rain_order_raw = [r for r in RAIN_REGIME_ORDER if r in set(hm_df["rain_regime"])]
            piv = (
                hm_df.pivot(index="rain_regime", columns="temp_band", values="sold_qty")
                .reindex(index=rain_order_raw, columns=temp_order_raw)
            )
            x_labels = [temp_label(c) for c in piv.columns]
            y_labels = [rain_label(idx) for idx in piv.index]
            z_vals = piv.values
            text_vals = [
                [fmt_compact(val, decimals=1) if pd.notna(val) else "" for val in row_vals]
                for row_vals in z_vals
            ]

            fig_hm = go.Figure(
                data=go.Heatmap(
                    z=z_vals,
                    x=x_labels,
                    y=y_labels,
                    text=text_vals,
                    texttemplate="%{text}",
                    textfont=dict(size=12),
                    colorscale=list(palette.continuous_scale),
                    colorbar=dict(title="Sản lượng", thickness=14),
                    hoverongaps=False,
                    hovertemplate="Nhiệt độ: %{x}<br>Mức mưa: %{y}<br>Sản lượng: %{z:,.0f}<extra></extra>",
                )
            )
            if cell_temp in piv.columns and cell_rain in piv.index:
                xi = list(piv.columns).index(cell_temp)
                yi = list(piv.index).index(cell_rain)
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
                height=340,
                show_legend=False,
                xaxis_title="Mức nhiệt độ",
                yaxis_title="Mức mưa",
            )
            fig_hm.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_hm, width="stretch", theme=None, config=plotly_config())

    # Row 3: Humidity x Weekend Bar (6) + Temp vs Qty Scatter (6)
    col_hum, col_scat = st.columns([6, 6], gap="medium")

    with col_hum:
        with st.container(border=True):
            render_chart_header(
                "Sản Lượng Bán Theo Độ Ẩm & Cuối Tuần",
                "So sánh sản lượng bán giữa ngày thường và cuối tuần theo dải độ ẩm",
            )
            hum_sql, hum_params = sql_humidity_weekend(schema, filters)
            hum_df = run_query_df(hum_sql, hum_params)
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
                    y="sold_qty",
                    color="weekend_vi",
                    barmode="group",
                    text_auto=".3s",
                    category_orders={"hum_vi": hum_order_vi, "weekend_vi": ["Ngày thường", "Cuối tuần"]},
                    color_discrete_sequence=[palette.primary, palette.accent],
                )
                fig_hum.update_traces(
                    textposition="outside",
                    hovertemplate="Độ ẩm: %{x}<br>Loại ngày: %{fullData.name}<br>Sản lượng: %{y:,.0f}<extra></extra>",
                )
                style_plotly(
                    fig_hum,
                    palette,
                    height=370,
                    xaxis_title="Mức độ ẩm",
                    yaxis_title="Sản lượng",
                )
                polish_vertical_bar_headroom(fig_hum, float(hum_df["sold_qty"].max()))
                fig_hum.update_layout(legend_title_text="Ngày trong tuần")
                st.plotly_chart(fig_hum, width="stretch", theme=None, config=plotly_config())

    with col_scat:
        with st.container(border=True):
            render_chart_header(
                "Nhiệt Độ Trung Bình vs Sản Lượng Bán",
                "Tương quan nhiệt độ trung bình ngày (°C) với tổng sản lượng bán theo mức mưa",
            )
            sc_sql, sc_params = sql_daily_temp_scatter(schema, filters)
            sc_df = run_query_df(sc_sql, sc_params)
            if sc_df.empty:
                render_empty_state()
            else:
                sc_df = sc_df.copy()
                sc_df["rain_vi"] = sc_df["rain_regime"].map(rain_label)
                rain_order_vi = [rain_label(r) for r in RAIN_REGIME_ORDER if r in set(sc_df["rain_regime"])]
                fig_sc = px.scatter(
                    sc_df,
                    x="temp_mean",
                    y="sold_qty",
                    color="rain_vi",
                    category_orders={"rain_vi": rain_order_vi},
                    hover_data={"local_date": True, "order_count": ":,"},
                    color_discrete_sequence=list(palette.discrete),
                    opacity=0.78,
                )
                fig_sc.update_traces(
                    marker=dict(size=8),
                    hovertemplate="Ngày: %{customdata[0]}<br>Nhiệt độ TB: %{x:.1f} °C<br>Sản lượng: %{y:,.0f}<br>Số đơn: %{customdata[1]}<extra></extra>",
                )
                style_plotly(
                    fig_sc,
                    palette,
                    height=370,
                    xaxis_title="Nhiệt độ trung bình (°C)",
                    yaxis_title="Sản lượng",
                )
                fig_sc.update_layout(legend_title_text="Mức mưa")
                st.plotly_chart(fig_sc, width="stretch", theme=None, config=plotly_config())

    # Row 4: Full-width Monthly Trend by Dataset Track
    with st.container(border=True):
        render_chart_header(
            "Tổng Sản Lượng Hàng Tháng Theo Nhóm Dữ Liệu",
            "Xu hướng sản lượng bán theo tháng trong bộ lọc thời tiết đang chọn",
        )
        ml_sql, ml_params = sql_monthly_track_trend(schema, filters)
        ml_df = run_query_df(ml_sql, ml_params)
        if ml_df.empty:
            render_empty_state()
        else:
            ml_df = ml_df.copy()
            ml_df["track_vi"] = ml_df["dataset_track"].map(track_label)
            fig_ml = px.line(
                ml_df,
                x="year_month",
                y="sold_qty",
                color="track_vi",
                markers=True,
                color_discrete_sequence=[palette.primary, palette.accent],
            )
            fig_ml.update_traces(
                line=dict(width=2.6),
                hovertemplate="Tháng %{x|%m/%Y}<br>Sản lượng: %{y:,.0f}<extra></extra>",
            )
            style_plotly(
                fig_ml,
                palette,
                height=310,
                xaxis_title="Tháng",
                yaxis_title="Sản lượng",
            )
            fig_ml.update_layout(legend_title_text="Nhóm dữ liệu")
            st.plotly_chart(fig_ml, width="stretch", theme=None, config=plotly_config())

    # Row 4: Enriched Daily Weather & Sales Table
    with st.container(border=True):
        render_chart_header(
            "Sản Lượng Bán & Thời Tiết Theo Ngày",
            "Bảng theo dõi sản lượng, số đơn hàng, nhiệt độ, lượng mưa, độ ẩm và doanh thu theo từng ngày",
        )
        by_store_uom = st.toggle(
            "Mở rộng chi tiết theo từng Cửa hàng & Đơn vị tính",
            value=False,
            key="p2_daily_store_uom",
        )
        dt_sql, dt_params = sql_daily_weather_table(schema, filters, by_store_uom=by_store_uom, limit=500)
        dt_df = run_query_df(dt_sql, dt_params)
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
                        "Sản lượng": safe_round(dt_df["sold_qty"], 0),
                        "Số đơn hàng": dt_df["order_count"],
                        "Nhiệt độ TB (°C)": safe_round(dt_df["temp_mean"], 2),
                        "Lượng mưa TB (mm)": safe_round(dt_df["precip_sum"], 2),
                        "Độ ẩm TB (%)": safe_round(dt_df["humidity_mean"], 1),
                        rev_col_name: safe_round(dt_df["line_amount"], 2),
                    }
                )
            else:
                show_df = pd.DataFrame(
                    {
                        "Ngày bán": dt_df["local_date"],
                        "Sản lượng": safe_round(dt_df["sold_qty"], 0),
                        "Số đơn hàng": dt_df["order_count"],
                        "Nhiệt độ TB (°C)": safe_round(dt_df["temp_mean"], 2),
                        "Lượng mưa TB (mm)": safe_round(dt_df["precip_sum"], 2),
                        "Độ ẩm TB (%)": safe_round(dt_df["humidity_mean"], 1),
                        rev_col_name: safe_round(dt_df["line_amount"], 2),
                    }
                )
            st.dataframe(
                show_df,
                width="stretch",
                hide_index=True,
                height=310,
                column_config={
                    "Ngày bán": st.column_config.DateColumn(format="YYYY-MM-DD"),
                    "Sản lượng": st.column_config.NumberColumn(format="%,.0f"),
                    "Số đơn hàng": st.column_config.NumberColumn(format="%,d"),
                    "Nhiệt độ TB (°C)": st.column_config.NumberColumn(format="%.2f"),
                    "Lượng mưa TB (mm)": st.column_config.NumberColumn(format="%.2f"),
                    "Độ ẩm TB (%)": st.column_config.NumberColumn(format="%.1f"),
                    rev_col_name: st.column_config.NumberColumn(format="%,.2f"),
                },
            )
            render_csv_download(show_df, "thoi_tiet_ban_hang_theo_ngay.csv", key="p2_csv_daily")

    # Row 5: Top 15 Drugs by Weather (6) + Weekday x Rain (6)
    col_top15, col_dow = st.columns([6, 6], gap="medium")

    with col_top15:
        with st.container(border=True):
            render_chart_header(
                "Top 15 Thuốc Bán Chạy Theo Điều Kiện Thời Tiết",
                "15 sản phẩm có tổng sản lượng cao nhất (xếp giảm dần từ trên xuống) phân tách theo chế độ mưa",
            )
            tp_sql, tp_params = sql_top_products_by_rain(schema, filters, limit=15)
            tp_df = run_query_df(tp_sql, tp_params)
            if tp_df.empty:
                render_empty_state()
            else:
                tp_df = tp_df.copy()
                tp_df["rain_vi"] = tp_df["rain_regime"].map(rain_label)
                prod_order_desc = (
                    tp_df.groupby("product_name", as_index=False)["total_qty"]
                    .max()
                    .sort_values("total_qty", ascending=False)["product_name"]
                    .tolist()
                )
                rain_order_vi = [rain_label(r) for r in RAIN_REGIME_ORDER if r in set(tp_df["rain_regime"])]
                fig_tp = px.bar(
                    tp_df,
                    x="sold_qty",
                    y="product_name",
                    color="rain_vi",
                    orientation="h",
                    category_orders={"rain_vi": rain_order_vi},
                    color_discrete_sequence=list(palette.discrete),
                )
                fig_tp.update_traces(
                    hovertemplate="Sản phẩm: %{y}<br>Mức mưa: %{fullData.name}<br>Sản lượng: %{x:,.0f}<extra></extra>"
                )
                style_plotly(
                    fig_tp,
                    palette,
                    height=440,
                    xaxis_title="Sản lượng",
                    yaxis_title="Sản phẩm",
                )
                max_total_qty = float(tp_df["total_qty"].max())
                polish_horizontal_bar(fig_tp, prod_order_desc, max_total_qty, right_margin=24)
                fig_tp.update_layout(legend_title_text="Mức mưa")
                st.plotly_chart(fig_tp, width="stretch", theme=None, config=plotly_config())

    with col_dow:
        with st.container(border=True):
            render_chart_header(
                "Sản Lượng Theo Thứ Trong Tuần & Mức Mưa",
                "Biến động sản lượng bán từ Thứ 2 đến Chủ nhật theo từng điều kiện mưa",
            )
            dow_sql, dow_params = sql_weekday_by_rain(schema, filters)
            dow_df = run_query_df(dow_sql, dow_params)
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
                    y="sold_qty",
                    color="rain_vi",
                    barmode="group",
                    category_orders={"dow_vi": dow_order, "rain_vi": rain_order_vi},
                    color_discrete_sequence=list(palette.discrete),
                )
                fig_dow.update_traces(
                    hovertemplate="Ngày: %{x}<br>Mức mưa: %{fullData.name}<br>Sản lượng: %{y:,.0f}<extra></extra>"
                )
                style_plotly(
                    fig_dow,
                    palette,
                    height=440,
                    xaxis_title="Thứ trong tuần",
                    yaxis_title="Sản lượng",
                )
                fig_dow.update_layout(legend_title_text="Mức mưa")
                st.plotly_chart(fig_dow, width="stretch", theme=None, config=plotly_config())


render_page(get_current_filters())
