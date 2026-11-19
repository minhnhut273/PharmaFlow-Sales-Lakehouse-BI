"""Page 1: Executive Overview (Tổng Quan)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from components.filters import get_current_filters
from config import (
    TRACK_META,
    country_label,
    fmt_compact,
    fmt_currency,
    fmt_pct,
    provenance_label,
    safe_round,
    track_label,
)
from db import get_active_schema, run_query_df
from queries import (
    FilterState,
    sql_exec_kpis,
    sql_monthly_trend_kpi,
    sql_sales_by_country,
    sql_top_brands,
    sql_track_currency_summary,
)
from ui import (
    get_active_palette,
    plotly_config,
    polish_horizontal_bar,
    render_chart_header,
    render_csv_download,
    render_empty_state,
    render_kpi_card,
    render_page_header,
    style_plotly,
)


def render_page(filters: FilterState) -> None:
    schema = get_active_schema()
    palette = get_active_palette()
    meta = TRACK_META.get(filters.dataset_track or "")
    ccy = meta.currency_code if meta else None
    uom_note = ", ".join(filters.clean_uoms) if filters.clean_uoms else ("Tổng nhiều đơn vị" if meta and meta.multi_uom else "Tất cả đơn vị")

    render_page_header(
        "Tổng Quan Điều Hành",
        "Tổng quan hiệu suất bán lẻ dược phẩm — KPI trọng yếu, xu hướng tăng trưởng theo kỳ, cơ cấu thị trường và thương hiệu dẫn đầu.",
        dataset_track=filters.dataset_track,
        extra_pills=[("Gold MD-01 · Sales Monitoring", "default")],
    )

    # Row 1: 6 KPI cards (2 rows x 3 columns)
    kpi_sql, kpi_params = sql_exec_kpis(schema, filters)
    kpi_df = run_query_df(kpi_sql, kpi_params)
    row = kpi_df.iloc[0] if not kpi_df.empty else {}

    row_count = int(row.get("row_count") or 0)
    total_rev = row.get("total_revenue")
    total_qty = row.get("total_sold_qty")
    total_orders = row.get("total_orders")
    total_margin = row.get("total_margin")
    avg_margin_pct = row.get("avg_margin_pct")
    weighted_margin_pct = row.get("weighted_margin_pct")
    avg_price = row.get("avg_unit_price")
    margin_rows = int(row.get("margin_rows") or 0)

    has_rev = bool(meta.has_revenue) if meta else (total_rev is not None and float(total_rev or 0) > 0)
    rev_display = fmt_currency(total_rev, ccy) if (row_count > 0 and has_rev) else "Không ghi nhận"
    rev_sub = f"Cộng dồn theo tiền tệ {ccy}" if (ccy and has_rev) else "Nguồn dữ liệu này không ghi nhận doanh thu tiền tệ"

    margin_display = fmt_currency(total_margin, ccy) if (row_count > 0 and margin_rows > 0) else "Không ghi nhận"
    margin_sub = f"Lợi nhuận gộp trên {margin_rows:,} dòng giao dịch" if margin_rows > 0 else "Chỉ khả dụng ở nguồn ONYX Châu Âu (EUR)"

    margin_pct_display = fmt_pct(avg_margin_pct) if (row_count > 0 and margin_rows > 0) else "Không ghi nhận"
    margin_pct_sub = (
        f"Trung bình giao dịch · Có trọng số DT: {fmt_pct(weighted_margin_pct)}"
        if margin_rows > 0
        else "Chưa có dữ liệu giá vốn cho nguồn này"
    )

    price_display = fmt_currency(avg_price, ccy, compact=False) if (row_count > 0 and has_rev and avg_price is not None) else "Không ghi nhận"
    price_sub = f"Giá đơn vị trung bình ({uom_note})"

    c1, c2, c3 = st.columns(3)
    with c1:
        render_kpi_card(
            "Tổng Doanh Thu Theo Nhóm Dữ Liệu",
            rev_display,
            rev_sub,
            tag=ccy or "N/A",
            accent=palette.primary,
        )
    with c2:
        render_kpi_card(
            "Tổng Sản Lượng Bán",
            fmt_compact(total_qty) if row_count > 0 else "—",
            f"Tổng sản lượng bán ra ({uom_note})",
            tag="Sản lượng",
            accent=palette.accent,
        )
    with c3:
        render_kpi_card(
            "Tổng Số Đơn Hàng",
            fmt_compact(total_orders) if row_count > 0 else "—",
            f"Tổng số đơn hàng ghi nhận qua {row_count:,} dòng",
            tag="Đơn hàng",
            accent=palette.discrete[2],
        )

    c4, c5, c6 = st.columns(3)
    with c4:
        render_kpi_card(
            "Tổng Lợi Nhuận Theo Nhóm Dữ Liệu",
            margin_display,
            margin_sub,
            tag=ccy or "N/A",
            accent=palette.primary_dark,
        )
    with c5:
        render_kpi_card(
            "Biên Lợi Nhuận Trung Bình (%)",
            margin_pct_display,
            margin_pct_sub,
            tag="% Biên LN",
            accent=palette.discrete[3],
        )
    with c6:
        render_kpi_card(
            "Đơn Giá Trung Bình Theo Nguồn",
            price_display,
            price_sub,
            tag=ccy or "N/A",
            accent=palette.discrete[5],
        )

    # Row 2: Combo Trend (7) + Country Donut (5)
    col_trend, col_country = st.columns([7, 5], gap="medium")

    with col_trend:
        with st.container(border=True):
            render_chart_header(
                "Tăng Trưởng Sản Lượng Bán Hàng Theo Tháng",
                "Sản lượng hàng tháng (cột) và % thay đổi trung bình so với tháng trước (đường — kỳ MONTH từ kpi_sales_trend)",
            )
            scope_track = st.toggle(
                "Lọc biểu đồ theo nguồn dữ liệu đang chọn",
                value=True,
                key="p1_trend_scope_track",
                help="Tắt để xem toàn chuỗi 2014–2025 gộp qua Serbia, Indonesia và EU giống mặc định ban đầu của AWS Quick.",
            )
            t_sql, t_params = sql_monthly_trend_kpi(schema, filters, scope_to_track=scope_track)
            trend_df = run_query_df(t_sql, t_params)
            if trend_df.empty:
                render_empty_state()
            else:
                trend_df = trend_df.copy()
                trend_df["pct_change_display"] = trend_df["avg_pct_change"].astype(float) * 100.0
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(
                    go.Bar(
                        x=trend_df["period_start"],
                        y=trend_df["sold_qty"],
                        name="Sản lượng (Tháng)",
                        marker_color=palette.primary,
                        opacity=0.88,
                        hovertemplate="Kỳ %{x|%m/%Y}<br>Sản lượng: %{y:,.0f}<extra></extra>",
                    ),
                    secondary_y=False,
                )
                fig.add_trace(
                    go.Scatter(
                        x=trend_df["period_start"],
                        y=trend_df["pct_change_display"],
                        name="Tăng trưởng TB (%)",
                        mode="lines+markers",
                        line=dict(color=palette.accent, width=2.4),
                        marker=dict(size=5),
                        hovertemplate="Kỳ %{x|%m/%Y}<br>Tăng trưởng TB: %{y:+.2f}%<extra></extra>",
                    ),
                    secondary_y=True,
                )
                style_plotly(fig, palette, height=345, xaxis_title="Kỳ thời gian (Tháng)")
                fig.update_yaxes(title_text="Sản lượng", secondary_y=False)
                fig.update_yaxes(title_text="Tăng trưởng TB (%)", ticksuffix="%", secondary_y=True, showgrid=False)
                st.plotly_chart(fig, width="stretch", theme=None, config=plotly_config())

    with col_country:
        with st.container(border=True):
            render_chart_header(
                "Tỷ Trọng Sản Lượng Bán Theo Quốc Gia",
                "Phân bố sản lượng bán ra giữa các quốc gia trong nhóm dữ liệu đang chọn",
            )
            ctry_sql, ctry_params = sql_sales_by_country(schema, filters)
            ctry_df = run_query_df(ctry_sql, ctry_params)
            if ctry_df.empty:
                render_empty_state()
            else:
                ctry_df = ctry_df.copy()
                ctry_df["country_vi"] = ctry_df["country_code"].map(country_label)
                total_sum = float(ctry_df["sold_qty"].sum())
                fig_donut = px.pie(
                    ctry_df,
                    names="country_vi",
                    values="sold_qty",
                    hole=0.55,
                    color_discrete_sequence=list(palette.discrete),
                )
                fig_donut.update_traces(
                    textposition="inside",
                    textinfo="percent",
                    textfont_size=11,
                    hovertemplate="%{label}<br>Sản lượng: %{value:,.0f} (%{percent})<extra></extra>",
                )
                fig_donut.add_annotation(
                    text=f"<b>{fmt_compact(total_sum)}</b><br><span style='font-size:11px;color:{palette.muted}'>Tổng SL</span>",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=14, color=palette.ink),
                )
                style_plotly(fig_donut, palette, height=385, show_legend=True)
                fig_donut.update_layout(
                    legend=dict(
                        orientation="h",
                        yanchor="top",
                        y=-0.04,
                        xanchor="center",
                        x=0.5,
                        font=dict(size=10.5),
                    ),
                    margin=dict(l=12, r=12, t=12, b=64),
                )
                st.plotly_chart(fig_donut, width="stretch", theme=None, config=plotly_config())

    # Row 3: Top Brands (6) + Track & Currency Summary Table (6)
    col_brands, col_table = st.columns([6, 6], gap="medium")

    with col_brands:
        with st.container(border=True):
            render_chart_header(
                "Tổng Sản Lượng Bán Theo Thương Hiệu",
                "Xếp hạng Top 15 thương hiệu theo sản lượng bán tích lũy",
            )
            b_sql, b_params = sql_top_brands(schema, filters, limit=15)
            brand_df = run_query_df(b_sql, b_params)
            if brand_df.empty:
                render_empty_state("Nguồn dữ liệu hoặc bộ lọc hiện tại chưa có thông tin thương hiệu.")
            else:
                fig_bar = px.bar(
                    brand_df,
                    x="sold_qty",
                    y="brand_name",
                    orientation="h",
                    text_auto=".3s",
                    color_discrete_sequence=[palette.primary],
                )
                fig_bar.update_traces(
                    textposition="outside",
                    hovertemplate="Thương hiệu: %{y}<br>Sản lượng: %{x:,.0f}<extra></extra>",
                )
                style_plotly(
                    fig_bar,
                    palette,
                    height=390,
                    show_legend=False,
                    xaxis_title="Sản lượng",
                    yaxis_title="Thương hiệu",
                )
                polish_horizontal_bar(fig_bar, brand_df["brand_name"].tolist(), float(brand_df["sold_qty"].max()))
                st.plotly_chart(fig_bar, width="stretch", theme=None, config=plotly_config())

    with col_table:
        with st.container(border=True):
            render_chart_header(
                "Sản Lượng & Đơn Hàng Theo Nhóm Dữ Liệu & Tiền Tệ",
                "Phân tách rạch ròi nguồn thực tế (OBSERVED) vs mô phỏng (SYNTHETIC) và đơn vị tiền tệ",
            )
            compare_all = st.toggle(
                "Hiển thị cả 3 nhóm dữ liệu để đối chiếu",
                value=True,
                key="p1_summary_all_tracks",
            )
            s_sql, s_params = sql_track_currency_summary(schema, filters, show_all_tracks=compare_all)
            sum_df = run_query_df(s_sql, s_params)
            if sum_df.empty:
                render_empty_state()
            else:
                display_df = pd.DataFrame(
                    {
                        "Nhóm dữ liệu": sum_df["dataset_track"].map(track_label),
                        "Tiền tệ": sum_df["currency_code"],
                        "Loại nguồn": sum_df["provenance_class"].map(provenance_label),
                        "Sản lượng": safe_round(sum_df["sold_qty"], 0),
                        "Số đơn hàng": sum_df["order_count"],
                        "Doanh thu": safe_round(sum_df["line_amount"], 2),
                        "Lợi nhuận": safe_round(sum_df["margin_amount"], 2),
                    }
                )
                st.dataframe(
                    display_df,
                    width="stretch",
                    hide_index=True,
                    height=320,
                    column_config={
                        "Sản lượng": st.column_config.NumberColumn(format="%,.0f"),
                        "Số đơn hàng": st.column_config.NumberColumn(format="%,d"),
                        "Doanh thu": st.column_config.NumberColumn(format="%,.2f"),
                        "Lợi nhuận": st.column_config.NumberColumn(format="%,.2f"),
                    },
                )
                render_csv_download(display_df, "tong_quan_nhom_du_lieu.csv", key="p1_csv_summary")


render_page(get_current_filters())
