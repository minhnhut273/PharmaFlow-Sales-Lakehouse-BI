"""Page 4: Product Portfolio, Manufacturers & ATC Categories (Sản Phẩm & ATC)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.filters import get_current_filters
from config import TRACK_META, atc_label, safe_round, track_label
from db import get_active_schema, run_query_df
from queries import (
    FilterState,
    sql_atc_category_ranking,
    sql_atc_month_heatmap,
    sql_atc_monthly_trend,
    sql_brand_product_treemap,
    sql_irpd_top_manufacturers,
    sql_product_detail_table,
    sql_unit_price_distribution,
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
        "Sản Phẩm, Nhà Sản Xuất & Nhóm Thuốc ATC",
        "Phân tích danh mục sản phẩm, nhà sản xuất (dữ liệu quan sát IRPD Indonesia), phân phối đơn giá và xu hướng tiêu thụ 8 nhóm thuốc điều trị ATC.",
        dataset_track=filters.dataset_track,
        extra_pills=[
            ("8 Nhóm Thuốc ATC · Dữ liệu Quan sát", "default"),
            ("NSX: Khóa IRPD Indonesia (IDR)", "observed"),
        ],
    )

    # Row 1: Searchable Product Table (7 clean columns, fixed Group-By)
    with st.container(border=True):
        render_chart_header(
            "Sản Lượng, Doanh Thu & Đơn Giá Theo Sản Phẩm",
            "Bảng chi tiết phân nhóm đúng theo Sản phẩm × Đơn vị tính × Nhóm dữ liệu (tối đa 500 dòng theo sản lượng)",
        )
        prod_search = st.text_input(
            "Tìm nhanh theo tên sản phẩm, thương hiệu hoặc đơn vị tính",
            placeholder="Ví dụ: AntiBioX, Paracetamol, tab...",
            key="p4_product_search",
        )
        pt_sql, pt_params = sql_product_detail_table(schema, filters, search_text=prod_search, limit=500)
        pt_df = run_query_df(pt_sql, pt_params)
        if pt_df.empty:
            render_empty_state()
        else:
            rev_col = f"Doanh thu ({ccy})" if ccy else "Doanh thu"
            price_col = f"Đơn giá TB ({ccy})" if ccy else "Đơn giá TB"
            disp_df = pd.DataFrame(
                {
                    "Tên sản phẩm": pt_df["product_name"],
                    "Đơn vị tính": pt_df["clean_uom"],
                    "Nhóm dữ liệu": pt_df["dataset_track"].map(track_label),
                    "Sản lượng": safe_round(pt_df["sold_qty"], 0),
                    rev_col: safe_round(pt_df["line_amount"], 2),
                    price_col: safe_round(pt_df["avg_unit_price"], 2),
                    "Biên lợi nhuận (%)": safe_round(pt_df["avg_margin_pct"], 2),
                }
            )
            st.dataframe(
                disp_df,
                width="stretch",
                hide_index=True,
                height=340,
                column_config={
                    "Sản lượng": st.column_config.NumberColumn(format="%,.0f"),
                    rev_col: st.column_config.NumberColumn(format="%,.2f"),
                    price_col: st.column_config.NumberColumn(format="%,.2f"),
                    "Biên lợi nhuận (%)": st.column_config.NumberColumn(format="%.2f%%"),
                },
            )
            render_csv_download(disp_df, "chi_tiet_san_pham.csv", key="p4_csv_products")

    # Row 2: Brand-Product Treemap (6) + Unit Price Histogram (6)
    col_tree, col_hist = st.columns([6, 6], gap="medium")

    with col_tree:
        with st.container(border=True):
            render_chart_header(
                "Tổng Sản Lượng Bán Theo Thương Hiệu & Sản Phẩm",
                "Phân cấp tỷ trọng sản lượng bán theo thương hiệu và từng sản phẩm (Top 80 SKU)",
            )
            tr_sql, tr_params = sql_brand_product_treemap(schema, filters, limit=80)
            tr_df = run_query_df(tr_sql, tr_params)
            if tr_df.empty:
                render_empty_state("Nguồn dữ liệu hoặc bộ lọc hiện tại không có cặp Thương hiệu × Sản phẩm.")
            else:
                fig_tr = px.treemap(
                    tr_df,
                    path=[px.Constant("Tất cả thương hiệu"), "brand_name", "product_name"],
                    values="sold_qty",
                    color="sold_qty",
                    labels={"sold_qty": "Sản lượng"},
                    color_continuous_scale=list(palette.continuous_scale),
                )
                fig_tr.update_traces(
                    hovertemplate="<b>%{label}</b><br>Sản lượng: %{value:,.0f}<extra></extra>"
                )
                fig_tr.update_coloraxes(colorbar_title_text="Sản lượng")
                style_plotly(fig_tr, palette, height=380, show_legend=False)
                fig_tr.update_layout(margin=dict(l=6, r=6, t=12, b=6))
                st.plotly_chart(fig_tr, width="stretch", theme=None, config=plotly_config())

    with col_hist:
        with st.container(border=True):
            render_chart_header(
                "Phân Bố Đơn Giá Trung Bình",
                "Tần suất phân bố đơn giá bán trung bình theo từng khoảng giá (tính trực tiếp trên PostgreSQL)",
            )
            hs_sql, hs_params = sql_unit_price_distribution(schema, filters, bins=24)
            hs_df = run_query_df(hs_sql, hs_params)
            if hs_df.empty:
                render_empty_state("Nguồn dữ liệu hiện tại không ghi nhận đơn giá tiền tệ.")
            else:
                hs_df = hs_df.copy()
                hs_df["track_vi"] = hs_df["dataset_track"].map(track_label)
                hs_df["bin_label"] = hs_df.apply(
                    lambda r: f"{r['bin_start']:,.1f}–{r['bin_end']:,.1f}", axis=1
                )
                bin_order = hs_df.sort_values("bucket_id")["bin_label"].drop_duplicates().tolist()
                fig_hs = px.bar(
                    hs_df,
                    x="bin_label",
                    y="obs_count",
                    color="track_vi",
                    category_orders={"bin_label": bin_order},
                    color_discrete_sequence=[palette.primary, palette.accent],
                )
                fig_hs.update_traces(
                    hovertemplate="Khoảng giá: %{x}<br>Số bản ghi: %{y:,.0f}<extra></extra>"
                )
                style_plotly(
                    fig_hs,
                    palette,
                    height=380,
                    xaxis_title=f"Khoảng đơn giá ({ccy})" if ccy else "Khoảng đơn giá",
                    yaxis_title="Số bản ghi",
                )
                polish_vertical_bar_headroom(fig_hs, float(hs_df.groupby("bin_label")["obs_count"].sum().max()))
                fig_hs.update_xaxes(tickangle=-35)
                fig_hs.update_layout(legend_title_text="Nhóm dữ liệu")
                st.plotly_chart(fig_hs, width="stretch", theme=None, config=plotly_config())

    # ATC Scope Toggle (bi_atc_category_monthly spans 2014–2019 surveillance window)
    apply_date_to_atc = st.toggle(
        "Áp dụng khoảng ngày đang lọc ở Sidebar cho chuỗi quan sát ATC (mặc định hiển thị toàn kỳ ATC 2014–2019)",
        value=False,
        key="p4_atc_apply_date",
    )
    atc_filters = filters if apply_date_to_atc else FilterState()

    # Row 3: Full-width Monthly ATC Line (clean vertical legend on right, zero collision with X-axis)
    with st.container(border=True):
        render_chart_header(
            "Xu Hướng Tiêu Thụ Theo Nhóm Thuốc ATC Hàng Tháng",
            "Tổng sản lượng quan sát hàng tháng của 8 nhóm thuốc điều trị ATC (bi_atc_category_monthly · 2014–2019)",
        )
        al_sql, al_params = sql_atc_monthly_trend(schema, atc_filters)
        al_df = run_query_df(al_sql, al_params)
        if al_df.empty:
            render_empty_state("Không có dữ liệu ATC trong khoảng ngày đang chọn.")
        else:
            al_df = al_df.copy()
            al_df["atc_vi"] = al_df.apply(
                lambda r: atc_label(r["category_code"], r["category_name"]), axis=1
            )
            fig_al = px.line(
                al_df,
                x="year_month",
                y="total_observed_qty",
                color="atc_vi",
                color_discrete_sequence=list(palette.discrete),
            )
            fig_al.update_traces(
                line=dict(width=2.1),
                hovertemplate="Tháng %{x|%m/%Y}<br>Nhóm: %{fullData.name}<br>Sản lượng QS: %{y:,.1f}<extra></extra>",
            )
            style_plotly(
                fig_al,
                palette,
                height=360,
                xaxis_title="Tháng",
                yaxis_title="Sản lượng quan sát",
            )
            fig_al.update_layout(
                legend_title_text="Nhóm thuốc ATC",
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1.0,
                    xanchor="left",
                    x=1.02,
                    font=dict(size=11),
                ),
                margin=dict(l=14, r=190, t=18, b=16),
            )
            st.plotly_chart(fig_al, width="stretch", theme=None, config=plotly_config())

    # Row 4: Full-width ATC Heatmap (zero horizontal overlap across 8 ATC groups)
    with st.container(border=True):
        render_chart_header(
            "Sản Lượng Theo Nhóm Thuốc ATC & Tháng",
            "Phân bố mùa vụ hàng tháng theo 8 nhóm thuốc điều trị ATC (bi_atc_category_monthly)",
        )
        ah_sql, ah_params = sql_atc_month_heatmap(schema, atc_filters)
        ah_df = run_query_df(ah_sql, ah_params)
        if ah_df.empty:
            render_empty_state("Không có dữ liệu ATC trong khoảng ngày đang chọn.")
        else:
            ah_df = ah_df.copy()
            ah_df["atc_short"] = ah_df["category_code"]
            piv = ah_df.pivot(index="month_num", columns="atc_short", values="total_observed_qty")
            piv = piv.reindex(index=sorted(piv.index), columns=sorted(piv.columns))
            y_labels = [f"Tháng {int(m)}" for m in piv.index]
            x_labels = [atc_label(str(c)) for c in piv.columns]
            text_vals = [
                [f"{v:,.0f}" if pd.notna(v) else "" for v in row]
                for row in piv.values
            ]
            fig_ah = go.Figure(
                data=go.Heatmap(
                    z=piv.values,
                    x=x_labels,
                    y=y_labels,
                    text=text_vals,
                    texttemplate="%{text}",
                    textfont=dict(size=11.5),
                    colorscale=list(palette.continuous_scale),
                    colorbar=dict(title="SL quan sát", thickness=14),
                    hovertemplate="Nhóm ATC: %{x}<br>%{y}<br>Sản lượng QS: %{z:,.1f}<extra></extra>",
                )
            )
            style_plotly(
                fig_ah,
                palette,
                height=390,
                show_legend=False,
                xaxis_title="Nhóm thuốc ATC",
                yaxis_title="Tháng",
            )
            fig_ah.update_xaxes(tickangle=-15)
            fig_ah.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_ah, width="stretch", theme=None, config=plotly_config())

    # Row 4: Top 15 Manufacturers IRPD-IDR (6) + 8 ATC Group Totals (6)
    col_mfg, col_atc_rank = st.columns([6, 6], gap="medium")

    with col_mfg:
        with st.container(border=True):
            render_chart_header(
                "Top 15 Nhà Sản Xuất Theo Doanh Thu (IRPD — IDR)",
                "Khóa riêng luồng dữ liệu quan sát IRPD Indonesia (nguồn ONYX EU không ghi nhận tên nhà sản xuất)",
            )
            mf_sql, mf_params = sql_irpd_top_manufacturers(schema, filters, limit=15)
            mf_df = run_query_df(mf_sql, mf_params)
            if mf_df.empty:
                render_empty_state("Không có dữ liệu nhà sản xuất trong khoảng ngày đang chọn.")
            else:
                mfg_order = mf_df["manufacturer_name"].tolist()
                fig_mf = px.bar(
                    mf_df,
                    x="line_amount",
                    y="manufacturer_name",
                    orientation="h",
                    text_auto=".3s",
                    hover_data={"sold_qty": ":,.0f", "order_count": ":,"},
                    color_discrete_sequence=[palette.primary],
                )
                fig_mf.update_traces(
                    textposition="outside",
                    hovertemplate="Nhà sản xuất: %{y}<br>Doanh thu: %{x:,.0f} IDR<br>Sản lượng: %{customdata[0]} · Đơn: %{customdata[1]}<extra></extra>",
                )
                style_plotly(
                    fig_mf,
                    palette,
                    height=430,
                    show_legend=False,
                    xaxis_title="Doanh thu (IDR)",
                    yaxis_title="Nhà sản xuất",
                )
                polish_horizontal_bar(fig_mf, mfg_order, float(mf_df["line_amount"].max()))
                st.plotly_chart(fig_mf, width="stretch", theme=None, config=plotly_config())

    with col_atc_rank:
        with st.container(border=True):
            render_chart_header(
                "Tổng Sản Lượng Quan Sát Theo 8 Nhóm ATC",
                "Xếp hạng giảm dần 8 nhóm thuốc điều trị ATC kèm mức tiêu thụ trung bình/ngày",
            )
            ar_sql, ar_params = sql_atc_category_ranking(schema, atc_filters)
            ar_df = run_query_df(ar_sql, ar_params)
            if ar_df.empty:
                render_empty_state()
            else:
                ar_df = ar_df.copy()
                ar_df["atc_vi"] = ar_df.apply(
                    lambda r: atc_label(r["category_code"], r["category_name"]), axis=1
                )
                atc_order = ar_df["atc_vi"].tolist()
                fig_ar = px.bar(
                    ar_df,
                    x="total_observed_qty",
                    y="atc_vi",
                    orientation="h",
                    text_auto=".3s",
                    hover_data={"avg_daily_qty": ":.2f", "observation_count": ":,"},
                    color_discrete_sequence=[palette.accent],
                )
                fig_ar.update_traces(
                    textposition="outside",
                    hovertemplate="Nhóm: %{y}<br>Tổng SL quan sát: %{x:,.1f}<br>Sản lượng TB/ngày: %{customdata[0]} · Số kỳ QS: %{customdata[1]}<extra></extra>",
                )
                style_plotly(
                    fig_ar,
                    palette,
                    height=430,
                    show_legend=False,
                    xaxis_title="Tổng sản lượng quan sát",
                    yaxis_title="Nhóm thuốc ATC",
                )
                polish_horizontal_bar(fig_ar, atc_order, float(ar_df["total_observed_qty"].max()))
                st.plotly_chart(fig_ar, width="stretch", theme=None, config=plotly_config())


render_page(get_current_filters())
