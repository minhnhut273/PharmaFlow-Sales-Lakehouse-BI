"""Page 3: Store Network, Geography & Margin Analytics (Cửa Hàng & Lợi Nhuận)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.filters import get_current_filters
from config import (
    ISO2_TO_ISO3,
    TRACK_META,
    country_label,
    fmt_compact,
    fmt_pct,
    safe_round,
)
from db import get_active_schema, run_query_df
from queries import (
    FilterState,
    sql_eu_brand_margin_and_profit,
    sql_eu_country_month_heatmap,
    sql_eu_country_summary,
    sql_eu_promo_gauge,
    sql_eu_store_matrix,
    sql_store_performance_table,
    sql_top_stores,
)
from ui import (
    get_active_palette,
    plotly_config,
    polish_horizontal_bar,
    polish_vertical_bar_headroom,
    render_chart_header,
    render_csv_download,
    render_empty_state,
    render_page_header,
    style_plotly,
)


def render_page(filters: FilterState) -> None:
    schema = get_active_schema()
    palette = get_active_palette()
    meta = TRACK_META.get(filters.dataset_track or "")
    ccy = meta.currency_code if meta else None

    render_page_header(
        "Cửa Hàng, Địa Lý & Biên Lợi Nhuận",
        "Đánh giá mạng lưới cửa hàng, phân bổ địa lý tại Châu Âu, hiệu quả khuyến mãi và ma trận biên lợi nhuận theo từng cửa hàng.",
        dataset_track=filters.dataset_track,
        extra_pills=[
            ("Khóa ONYX EU cho phân tích Margin & Promo", "synthetic"),
        ],
    )

    # Row 1: Country Geo Map / Bar (7) + ONYX EU Promo Gauge (5)
    col_geo, col_gauge = st.columns([7, 5], gap="medium")

    with col_geo:
        with st.container(border=True):
            render_chart_header(
                "Tổng Sản Lượng Bán Theo Quốc Gia (ONYX EU)",
                "Khóa riêng luồng dữ liệu ONYX EU (EUR) để 8 quốc gia Châu Âu không bị chênh lệch thang đo",
            )
            c_sql, c_params = sql_eu_country_summary(schema, filters)
            c_df = run_query_df(c_sql, c_params)
            if c_df.empty:
                render_empty_state()
            else:
                c_df = c_df.copy()
                c_df["country_vi"] = c_df["country_code"].map(country_label)
                c_df["iso3"] = c_df["country_code"].map(ISO2_TO_ISO3)

                tab_map, tab_bar = st.tabs(["Bản đồ Châu Âu", "Biểu đồ cột"])
                with tab_map:
                    fig_map = px.choropleth(
                        c_df,
                        locations="iso3",
                        locationmode="ISO-3",
                        color="sold_qty",
                        hover_name="country_vi",
                        hover_data={
                            "iso3": False,
                            "sold_qty": ":,.0f",
                            "line_amount": ":,.2f",
                            "store_count": True,
                        },
                        color_continuous_scale=list(palette.continuous_scale),
                        labels={
                            "sold_qty": "Sản lượng",
                            "line_amount": "Doanh thu (EUR)",
                            "store_count": "Số cửa hàng",
                        },
                    )
                    fig_map.update_geos(
                        scope="europe",
                        fitbounds="locations",
                        visible=True,
                        bgcolor="rgba(0,0,0,0)",
                        landcolor="#f1f5f9",
                        showcountries=True,
                        countrycolor="#cbd5e1",
                        subunitcolor="#e2e8f0",
                    )
                    style_plotly(fig_map, palette, height=345, show_legend=False)
                    fig_map.update_layout(margin=dict(l=4, r=4, t=8, b=4))
                    st.plotly_chart(fig_map, width="stretch", theme=None, config=plotly_config())

                with tab_bar:
                    fig_cbar = px.bar(
                        c_df,
                        x="country_vi",
                        y="sold_qty",
                        text_auto=".3s",
                        color_discrete_sequence=[palette.primary],
                    )
                    fig_cbar.update_traces(
                        textposition="outside",
                        hovertemplate="Quốc gia: %{x}<br>Sản lượng: %{y:,.0f}<extra></extra>",
                    )
                    style_plotly(
                        fig_cbar,
                        palette,
                        height=345,
                        show_legend=False,
                        xaxis_title="Quốc gia",
                        yaxis_title="Sản lượng",
                    )
                    polish_vertical_bar_headroom(fig_cbar, float(c_df["sold_qty"].max()))
                    st.plotly_chart(fig_cbar, width="stretch", theme=None, config=plotly_config())

    with col_gauge:
        with st.container(border=True):
            render_chart_header(
                "Tỷ Lệ Khuyến Mãi % (ONYX EU)",
                "Tỷ trọng sản lượng có khuyến mãi trên tổng sản lượng (khóa ONYX EU — thang 0–100%)",
            )
            pg_sql, pg_params = sql_eu_promo_gauge(schema, filters)
            pg_df = run_query_df(pg_sql, pg_params)
            if pg_df.empty or pg_df.iloc[0].get("weighted_promo_pct") is None:
                render_empty_state()
            else:
                weighted_pct = float(pg_df.iloc[0]["weighted_promo_pct"])
                unweighted_pct = float(pg_df.iloc[0]["avg_promo_pct"] or 0.0)
                fig_g = go.Figure(
                    go.Indicator(
                        mode="gauge+number",
                        value=weighted_pct,
                        number={"suffix": "%", "valueformat": ".2f", "font": {"size": 40, "color": palette.ink}},
                        gauge={
                            "axis": {"range": [0, 100], "ticksuffix": "%", "tickwidth": 1},
                            "bar": {"color": palette.primary, "thickness": 0.72},
                            "bgcolor": "#eef2f6",
                            "borderwidth": 0,
                            "steps": [
                                {"range": [0, 25], "color": palette.soft_bg},
                                {"range": [25, 100], "color": "#f8fafc"},
                            ],
                        },
                    )
                )
                style_plotly(fig_g, palette, height=330, show_legend=False)
                st.plotly_chart(fig_g, width="stretch", theme=None, config=plotly_config())
                st.caption(
                    f"Tỷ lệ theo sản lượng: **{weighted_pct:.2f}%** · Trung bình theo dòng giao dịch: **{unweighted_pct:.2f}%**."
                )

    # Row 2: Full-width Country x Month Heatmap (zero horizontal overlap across 8 EU countries)
    with st.container(border=True):
        render_chart_header(
            "Sản Lượng Bán Theo Quốc Gia & Tháng (ONYX EU)",
            "Phân bố mùa vụ sản lượng bán theo tháng giữa 8 quốc gia Châu Âu (2.49K – 6.73K)",
        )
        cm_sql, cm_params = sql_eu_country_month_heatmap(schema, filters)
        cm_df = run_query_df(cm_sql, cm_params)
        if cm_df.empty:
            render_empty_state()
        else:
            piv = cm_df.pivot(index="month_num", columns="country_code", values="sold_qty")
            piv = piv.reindex(index=sorted(piv.index), columns=sorted(piv.columns))
            y_labels = [f"Tháng {int(m)}" for m in piv.index]
            x_labels = [country_label(str(c)) for c in piv.columns]
            text_vals = [
                [f"{round(v):,}" if pd.notna(v) else "" for v in row]
                for row in piv.values
            ]
            fig_cm = go.Figure(
                data=go.Heatmap(
                    z=piv.values,
                    x=x_labels,
                    y=y_labels,
                    text=text_vals,
                    texttemplate="%{text}",
                    textfont=dict(size=12),
                    colorscale=list(palette.continuous_scale),
                    colorbar=dict(title="Sản lượng", thickness=14),
                    hovertemplate="Quốc gia: %{x}<br>%{y}<br>Sản lượng: %{z:,.0f}<extra></extra>",
                )
            )
            style_plotly(
                fig_cm,
                palette,
                height=390,
                show_legend=False,
                xaxis_title="Quốc gia",
                yaxis_title="Tháng",
            )
            fig_cm.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_cm, width="stretch", theme=None, config=plotly_config())

    # Row 3: Top 20 Stores (6) + Brand Margin Scatter (6)
    col_stores, col_bm = st.columns([6, 6], gap="medium")

    with col_stores:
        with st.container(border=True):
            render_chart_header(
                "Tổng Sản Lượng Bán Theo Cửa Hàng (Top 20)",
                "Xếp hạng cửa hàng theo sản lượng trong nhóm dữ liệu đang chọn (hỗ trợ cả EU, Indonesia, Serbia)",
            )
            ts_sql, ts_params = sql_top_stores(schema, filters, limit=20)
            ts_df = run_query_df(ts_sql, ts_params)
            if ts_df.empty:
                render_empty_state()
            else:
                ts_df = ts_df.copy()
                ts_df["country_vi"] = ts_df["country_code"].map(country_label)
                store_order = ts_df["store_name"].tolist()
                fig_ts = px.bar(
                    ts_df,
                    x="sold_qty",
                    y="store_name",
                    color="country_vi",
                    orientation="h",
                    color_discrete_sequence=list(palette.discrete),
                )
                fig_ts.update_traces(
                    hovertemplate="Cửa hàng: %{y}<br>Sản lượng: %{x:,.0f}<extra></extra>"
                )
                style_plotly(
                    fig_ts,
                    palette,
                    height=420,
                    xaxis_title="Sản lượng",
                    yaxis_title="Cửa hàng",
                )
                polish_horizontal_bar(fig_ts, store_order, float(ts_df["sold_qty"].max()), right_margin=24)
                fig_ts.update_layout(legend_title_text="Quốc gia")
                st.plotly_chart(fig_ts, width="stretch", theme=None, config=plotly_config())

    bm_sql, bm_params = sql_eu_brand_margin_and_profit(schema, filters)
    bm_df = run_query_df(bm_sql, bm_params)

    with col_bm:
        with st.container(border=True):
            render_chart_header(
                "Doanh Thu & Biên LN Theo Thương Hiệu (ONYX EU)",
                "Tương quan tổng doanh thu (EUR) với biên lợi nhuận trung bình (%) theo từng thương hiệu",
            )
            if bm_df.empty:
                render_empty_state()
            else:
                fig_bm = px.scatter(
                    bm_df,
                    x="line_amount",
                    y="avg_margin_pct",
                    size="sold_qty",
                    color="brand_name",
                    hover_data={"margin_amount": ":,.2f", "sold_qty": ":,.0f"},
                    color_discrete_sequence=list(palette.discrete) * 3,
                )
                fig_bm.update_traces(
                    hovertemplate="Thương hiệu: %{fullData.name}<br>Doanh thu: %{x:,.2f} EUR<br>Biên LN TB: %{y:.2f}%<extra></extra>"
                )
                style_plotly(
                    fig_bm,
                    palette,
                    height=420,
                    xaxis_title="Doanh thu (EUR)",
                    yaxis_title="Biên lợi nhuận (%)",
                )
                fig_bm.update_yaxes(ticksuffix="%")
                fig_bm.update_layout(
                    legend_title_text="Thương hiệu",
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=1.0,
                        xanchor="left",
                        x=1.02,
                        font=dict(size=10),
                    ),
                    margin=dict(l=14, r=120, t=18, b=16),
                )
                st.plotly_chart(fig_bm, width="stretch", theme=None, config=plotly_config())

    # Row 4: Full-width Brand Profit Bar (clean unclipped value labels across all brands)
    with st.container(border=True):
        render_chart_header(
            "Tổng Lợi Nhuận Theo Thương Hiệu (ONYX EU)",
            "Xếp hạng toàn bộ thương hiệu theo tổng lợi nhuận EUR tích lũy",
        )
        if bm_df.empty:
            render_empty_state()
        else:
            fig_bp = px.bar(
                bm_df,
                x="brand_name",
                y="margin_amount",
                text_auto=".3s",
                color_discrete_sequence=[palette.primary],
            )
            fig_bp.update_traces(
                textposition="outside",
                textfont_size=11,
                hovertemplate="Thương hiệu: %{x}<br>Lợi nhuận: %{y:,.2f} EUR<extra></extra>",
            )
            style_plotly(
                fig_bp,
                palette,
                height=340,
                show_legend=False,
                xaxis_title="Thương hiệu",
                yaxis_title="Lợi nhuận (EUR)",
            )
            polish_vertical_bar_headroom(fig_bp, float(bm_df["margin_amount"].max()))
            fig_bp.update_xaxes(tickangle=-20)
            st.plotly_chart(fig_bp, width="stretch", theme=None, config=plotly_config())

    # Row 4: Searchable Store Performance Pivot Table
    with st.container(border=True):
        render_chart_header(
            "Bảng Tổng Hợp Hiệu Suất Từng Cửa Hàng",
            "Chi tiết sản lượng, số đơn hàng, doanh thu và lợi nhuận theo từng cửa hàng & nguồn dữ liệu",
        )
        store_search = st.text_input(
            "Tìm nhanh theo mã, tên cửa hàng hoặc quốc gia",
            placeholder="Ví dụ: ONYX:PH0120, Madrid, Berlin...",
            key="p3_store_search",
        )
        st_sql, st_params = sql_store_performance_table(schema, filters, search_text=store_search)
        st_df = run_query_df(st_sql, st_params)
        if st_df.empty:
            render_empty_state()
        else:
            rev_label = f"Doanh thu ({ccy})" if ccy else "Doanh thu"
            mrg_label = f"Lợi nhuận ({ccy})" if ccy else "Lợi nhuận"
            disp_df = pd.DataFrame(
                {
                    "Mã cửa hàng": st_df["store_code"],
                    "Tên cửa hàng": st_df["store_name"],
                    "Quốc gia": st_df["country_code"].map(country_label),
                    "Nguồn dữ liệu": st_df["source"],
                    "Sản lượng": safe_round(st_df["sold_qty"], 0),
                    "Số đơn hàng": st_df["order_count"],
                    rev_label: safe_round(st_df["line_amount"], 2),
                    mrg_label: safe_round(st_df["margin_amount"], 2),
                    "Biên LN (%)": safe_round(st_df["avg_margin_pct"], 2),
                }
            )
            st.dataframe(
                disp_df,
                width="stretch",
                hide_index=True,
                height=330,
                column_config={
                    "Sản lượng": st.column_config.NumberColumn(format="%,.0f"),
                    "Số đơn hàng": st.column_config.NumberColumn(format="%,d"),
                    rev_label: st.column_config.NumberColumn(format="%,.2f"),
                    mrg_label: st.column_config.NumberColumn(format="%,.2f"),
                    "Biên LN (%)": st.column_config.NumberColumn(format="%.2f%%"),
                },
            )
            render_csv_download(disp_df, "hieu_suat_cua_hang.csv", key="p3_csv_stores")

    # Row 5: 120-Store Efficiency Bubble Matrix (Locked ONYX EU)
    with st.container(border=True):
        render_chart_header(
            "Ma Trận Hiệu Quả Cửa Hàng (ONYX EU)",
            "Định vị 120 cửa hàng Châu Âu theo Doanh thu (EUR) × Biên lợi nhuận (%) × Quy mô sản lượng (đường nét đứt = trung vị)",
        )
        mx_sql, mx_params = sql_eu_store_matrix(schema, filters)
        mx_df = run_query_df(mx_sql, mx_params)
        if mx_df.empty:
            render_empty_state()
        else:
            mx_df = mx_df.copy()
            mx_df["country_vi"] = mx_df["country_code"].map(country_label)
            med_rev = float(mx_df["line_amount"].median())
            med_mrg = float(mx_df["avg_margin_pct"].median())
            fig_mx = px.scatter(
                mx_df,
                x="line_amount",
                y="avg_margin_pct",
                size="sold_qty",
                color="country_vi",
                hover_name="store_name",
                hover_data={"store_code": True, "order_count": ":,", "sold_qty": ":,.0f"},
                color_discrete_sequence=list(palette.discrete),
                opacity=0.84,
            )
            fig_mx.add_vline(x=med_rev, line_dash="dash", line_color="#94a3b8", line_width=1.2)
            fig_mx.add_hline(y=med_mrg, line_dash="dash", line_color="#94a3b8", line_width=1.2)
            fig_mx.update_traces(
                hovertemplate="<b>%{hovertext}</b><br>Doanh thu: %{x:,.2f} EUR<br>Biên LN TB: %{y:.2f}%<br>Mã: %{customdata[0]} · Đơn: %{customdata[1]}<extra></extra>"
            )
            style_plotly(
                fig_mx,
                palette,
                height=440,
                xaxis_title="Doanh thu (EUR)",
                yaxis_title="Biên lợi nhuận (%)",
            )
            fig_mx.update_yaxes(ticksuffix="%")
            fig_mx.update_layout(legend_title_text="Quốc gia")
            st.plotly_chart(fig_mx, width="stretch", theme=None, config=plotly_config())
            st.caption(
                f"Ngưỡng trung vị tham chiếu ({len(mx_df)} cửa hàng): Doanh thu = **{med_rev:,.0f} EUR**, Biên lợi nhuận = **{fmt_pct(med_mrg, already_scaled=True)}**."
            )


render_page(get_current_filters())
