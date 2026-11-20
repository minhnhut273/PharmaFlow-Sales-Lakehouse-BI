"""Page 3: Store Network, Geography, Variance & Margin Analytics (Cửa Hàng & Biên Lợi Nhuận)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import (
    build_store_insights,
    build_store_watchlist,
    compute_variance_and_contributions,
    evaluate_uom_compatibility,
    resolve_comparison_periods,
    resolve_matrix_source_meta,
)
from components.filters import get_current_filters, get_track_bounds
from config import (
    ISO2_TO_ISO3,
    TRACK_META,
    country_label,
    fmt_compact,
    fmt_currency,
    fmt_pct,
    safe_round,
    track_label,
)
import db
from queries import (
    EU_STORE_MATRIX_TRACK,
    FilterState,
    sql_dimension_variance,
    sql_eu_brand_margin_and_profit,
    sql_eu_country_month_heatmap,
    sql_eu_country_summary,
    sql_eu_promo_breakdown,
    sql_eu_store_matrix,
    sql_monthly_sales_trend,
    sql_store_performance_table,
)
from ui import (
    get_active_palette,
    plotly_config,
    polish_diverging_bar,
    polish_vertical_bar_headroom,
    render_active_filter_bar,
    render_chart_header,
    render_csv_download,
    render_empty_state,
    render_insight_box,
    render_page_header,
    render_scope_strip,
    style_plotly,
)


def render_page(filters: FilterState) -> None:
    schema = db.get_active_schema()
    palette = get_active_palette()
    meta = TRACK_META.get(filters.dataset_track or "")
    ccy = meta.currency_code if meta else None
    has_rev = bool(meta.has_revenue) if meta else False
    prov_class = meta.provenance_class if meta else "SYNTHETIC"

    bounds = get_track_bounds()
    track_min_date = bounds.get("min_date")
    track_max_date = bounds.get("max_date")
    uoms_avail = bounds.get("uoms_avail") or ()

    is_onyx_selected = filters.dataset_track == EU_STORE_MATRIX_TRACK
    eu_scope_text = (
        f"Nguồn: {track_label(EU_STORE_MATRIX_TRACK)} · Áp dụng đầy đủ bộ lọc ngày/quốc gia/cửa hàng/ĐVT/nhiệt độ của thanh bên."
        if is_onyx_selected
        else "Phần tham chiếu riêng: ONYX Châu Âu — Mô phỏng (EUR) · Không áp dụng bộ lọc ngày/quốc gia/cửa hàng/ĐVT/nhiệt độ của nguồn đang chọn ở thanh bên."
    )

    render_page_header(
        "Cửa Hàng, Địa Lý & Biên Lợi Nhuận",
        "Đánh giá biến động cùng cửa hàng, định vị doanh thu × biên lợi nhuận gia quyền và nhận diện cửa hàng cần xem xét.",
        dataset_track=filters.dataset_track,
        extra_pills=[
            ("Chưa gồm tồn kho / điều chuyển", "warn"),
            ("Ma trận LN & KM: ONYX EU — Mô phỏng", "synthetic"),
        ],
    )

    m_sql, m_params = sql_monthly_sales_trend(schema, filters)
    m_df = db.run_query_df(m_sql, m_params)
    avail_months = m_df["year_month"].tolist() if not m_df.empty else []
    cmp_window = resolve_comparison_periods(
        filters.date_start,
        filters.date_end,
        mode=filters.compare_mode,
        available_months=avail_months,
        track_min_date=track_min_date,
        track_max_date=track_max_date,
    )
    render_active_filter_bar(filters, compare_window=cmp_window)

    uom_guard = evaluate_uom_compatibility(filters.dataset_track, filters.clean_uoms, uoms_avail)
    use_rev_var = bool(has_rev)
    c_col = "cur_rev" if use_rev_var else "cur_qty"
    p_col = "prev_rev" if use_rev_var else "prev_qty"
    var_metric_label = f"Doanh thu ({ccy})" if use_rev_var else f"Sản lượng ({uom_guard.single_uom or 'ĐVT'})"
    var_unit = ccy if use_rev_var else uom_guard.single_uom

    store_var_df = pd.DataFrame()
    if cmp_window.valid and cmp_window.cur_start and cmp_window.prev_start:
        sv_sql, sv_params = sql_dimension_variance(
            schema,
            filters,
            dim_kind="store",
            cur_start=cmp_window.cur_start,
            cur_end=cmp_window.cur_end,
            prev_start=cmp_window.prev_start,
            prev_end=cmp_window.prev_end,
            limit=None,
        )
        sv_raw = db.run_query_df(sv_sql, sv_params)
        if not sv_raw.empty:
            store_var_df = compute_variance_and_contributions(
                sv_raw,
                cur_col=c_col,
                prev_col=p_col,
                metric_supported=True,
            )
            store_var_df["mrg_pp_delta"] = (
                pd.to_numeric(store_var_df["cur_weighted_margin_pct"], errors="coerce")
                - pd.to_numeric(store_var_df["prev_weighted_margin_pct"], errors="coerce")
            )

    mx_sql, mx_params = sql_eu_store_matrix(schema, filters)
    mx_df = db.run_query_df(mx_sql, mx_params)
    matrix_meta = resolve_matrix_source_meta(
        mx_df,
        active_track=filters.dataset_track,
        default_track=EU_STORE_MATRIX_TRACK,
    )

    watchlist_res = build_store_watchlist(
        store_var_df,
        mx_df,
        window=cmp_window,
        supports_margin=is_onyx_selected,
        cur_col=c_col,
        prev_col=p_col,
    )
    watchlist_df = watchlist_res.df

    render_insight_box(
        "Nhận xét biến động & chất lượng biên lợi nhuận cửa hàng",
        build_store_insights(
            var_df=store_var_df,
            watchlist_df=watchlist_df,
            matrix_df=mx_df,
            window=cmp_window,
            metric_label=var_metric_label,
            metric_unit=var_unit,
            provenance_class=prov_class,
            watchlist_result=watchlist_res,
            matrix_meta=matrix_meta,
        ),
        note=cmp_window.note or None,
    )

    # Row 1: Same-Store Variance (6) + Store Watchlist (6)
    col_var, col_watch = st.columns([6, 6], gap="medium")

    with col_var:
        with st.container(border=True):
            render_chart_header(
                f"Biến Động Cùng Cửa Hàng ({cmp_window.cur_label} vs {cmp_window.prev_label})",
                f"Chỉ xếp hạng cửa hàng phát sinh bán ở cả 2 kỳ theo {var_metric_label} (Top tăng & Top giảm)",
            )
            if not cmp_window.valid or store_var_df.empty:
                render_empty_state(cmp_window.note or "Chưa có dữ liệu so sánh cửa hàng trong khoảng lọc.")
            else:
                both = store_var_df[store_var_df["presence_status"] == "Cả 2 kỳ"].copy()
                if len(both) == 0:
                    render_empty_state("Không có cửa hàng nào phát sinh bán đồng thời ở cả 2 kỳ so sánh.")
                elif len(both) == 1:
                    row_single = both.iloc[0]
                    d_s = float(row_single["delta"])
                    d_sign = "+" if d_s > 0 else ("−" if d_s < 0 else "")
                    st.info(
                        f"Có **1 cửa hàng** phát sinh cả 2 kỳ trong nguồn `{track_label(filters.dataset_track)}` (`{row_single['store_name']}`). "
                        f"Kỳ trước: **{fmt_compact(row_single[p_col])}**, kỳ này: **{fmt_compact(row_single[c_col])}** "
                        f"(chênh lệch: **{d_sign}{fmt_compact(abs(d_s))}**"
                        + (f", **{row_single['pct_change'] * 100:+.2f}%**" if pd.notna(row_single.get("pct_change")) else "")
                        + ")."
                    )
                else:
                    gain = both[both["delta"] > 0].sort_values("delta", ascending=False).head(7)
                    drop = both[both["delta"] < 0].sort_values("delta", ascending=True).head(7)
                    comb = pd.concat([gain, drop], ignore_index=True).drop_duplicates(subset=["store_code"])
                    if comb.empty:
                        render_empty_state("Không có chênh lệch giữa 2 kỳ so sánh.")
                    else:
                        comb = comb.sort_values("delta", ascending=True)
                        colors = [palette.primary if d >= 0 else "#dc2626" for d in comb["delta"]]
                        fig_sv = go.Figure(
                            go.Bar(
                                x=comb["delta"],
                                y=comb["store_name"],
                                orientation="h",
                                marker_color=colors,
                                text=[f"{d:+,.0f}" for d in comb["delta"]],
                                textposition="outside",
                                customdata=list(
                                    zip(
                                        comb[p_col],
                                        comb[c_col],
                                        comb["contrib_pp"].fillna(0.0),
                                        (comb["pct_change"] * 100.0).fillna(0.0),
                                    )
                                ),
                                hovertemplate=(
                                    "<b>%{y}</b><br>"
                                    "Kỳ trước: %{customdata[0]:,.0f}<br>"
                                    "Kỳ này: %{customdata[1]:,.0f}<br>"
                                    "Chênh lệch: %{x:+,.0f} (%{customdata[3]:+.2f}%)<br>"
                                    "Đóng góp số học: %{customdata[2]:+.2f} điểm %<extra></extra>"
                                ),
                            )
                        )
                        style_plotly(
                            fig_sv,
                            palette,
                            height=370,
                            show_legend=False,
                            xaxis_title=f"Chênh lệch {var_metric_label}",
                            yaxis_title="",
                        )
                        polish_diverging_bar(fig_sv, float(comb["delta"].abs().max()))
                        st.plotly_chart(fig_sv, width="stretch", theme=None, config=plotly_config())

    with col_watch:
        with st.container(border=True):
            render_chart_header(
                watchlist_res.title,
                watchlist_res.subtitle,
            )
            if watchlist_res.status == "reference_low_margin":
                render_scope_strip(
                    "Chưa có cửa hàng vượt tiêu chí cảnh báo — danh sách bên dưới chỉ mang tính tham khảo (Top biên lợi nhuận thấp nhất).",
                    kind="default",
                )
            if watchlist_df.empty:
                render_empty_state(
                    watchlist_res.empty_message
                    or "Không có cửa hàng vượt ngưỡng cảnh báo trong phạm vi lọc hiện tại."
                )
            else:
                reason_col_lbl = (
                    "Ghi chú tham khảo"
                    if watchlist_res.status == "reference_low_margin"
                    else "Lý do cần xem xét"
                )
                if is_onyx_selected and "weighted_margin_pct" in watchlist_df.columns:
                    w_disp = pd.DataFrame(
                        {
                            "Cửa hàng": watchlist_df["store_name"],
                            "Quốc gia": watchlist_df["country_code"].map(country_label),
                            f"Doanh thu ({matrix_meta.currency_code})": safe_round(watchlist_df["line_amount"], 0),
                            "Biên LN gia quyền (%)": safe_round(watchlist_df["weighted_margin_pct"], 2),
                            "Biến động kỳ (%)": safe_round(pd.to_numeric(watchlist_df["pct_change"], errors="coerce") * 100.0, 2),
                            reason_col_lbl: watchlist_df["Lý do cần xem xét"],
                        }
                    )
                    rev_col_w = f"Doanh thu ({matrix_meta.currency_code})"
                    w_cfg = {
                        rev_col_w: st.column_config.NumberColumn(format="%,.0f"),
                        "Biên LN gia quyền (%)": st.column_config.NumberColumn(format="%.2f%%"),
                        "Biến động kỳ (%)": st.column_config.NumberColumn(format="%+.2f%%"),
                    }
                else:
                    val_col_lbl = f"Giá trị kỳ này ({var_unit})" if var_unit else "Giá trị kỳ này"
                    w_disp = pd.DataFrame(
                        {
                            "Cửa hàng": watchlist_df["store_name"],
                            val_col_lbl: safe_round(watchlist_df[c_col], 0),
                            "Chênh lệch": safe_round(watchlist_df["delta"], 0),
                            "Biến động (%)": safe_round(pd.to_numeric(watchlist_df["pct_change"], errors="coerce") * 100.0, 2),
                            reason_col_lbl: watchlist_df["Lý do cần xem xét"],
                        }
                    )
                    w_cfg = {
                        val_col_lbl: st.column_config.NumberColumn(format="%,.0f"),
                        "Chênh lệch": st.column_config.NumberColumn(format="%+,.0f"),
                        "Biến động (%)": st.column_config.NumberColumn(format="%+.2f%%"),
                    }
                st.dataframe(w_disp, width="stretch", hide_index=True, height=320, column_config=w_cfg)
                render_csv_download(w_disp, "cua_hang_can_xem_xet.csv", key="p3_csv_watchlist")

    # Row 2: Full-width Store Efficiency Bubble Matrix (explicit independent source provenance & EUR)
    with st.container(border=True):
        n_mx = len(mx_df)
        render_chart_header(
            f"Ma Trận Doanh Thu × Biên Lợi Nhuận Gia Quyền ({n_mx} Cửa Hàng · {matrix_meta.label_vi} · {matrix_meta.currency_code})",
            "Đường nét đứt = trung vị theo tập cửa hàng đang hiển thị; kích thước bong bóng = sản lượng bán",
        )
        render_scope_strip(
            f"Nguồn: {matrix_meta.label_vi} ({matrix_meta.currency_code}) · {matrix_meta.scope_note}",
            kind="default" if matrix_meta.matches_sidebar_track else "warn",
        )
        if mx_df.empty:
            render_empty_state()
        else:
            mx_df = mx_df.copy()
            mx_df["country_vi"] = mx_df["country_code"].map(country_label)
            med_rev = float(mx_df["line_amount"].median())
            med_mrg = float(mx_df["weighted_margin_pct"].median())
            fig_mx = px.scatter(
                mx_df,
                x="line_amount",
                y="weighted_margin_pct",
                size="sold_qty",
                color="country_vi",
                hover_name="store_name",
                hover_data={"store_code": True, "line_count": ":,", "active_store_days": ":,"},
                color_discrete_sequence=list(palette.discrete),
                opacity=0.84,
            )
            fig_mx.add_vline(x=med_rev, line_dash="dash", line_color="#94a3b8", line_width=1.2)
            fig_mx.add_hline(y=med_mrg, line_dash="dash", line_color="#94a3b8", line_width=1.2)
            fig_mx.update_traces(
                hovertemplate=(
                    "<b>%{hovertext}</b><br>"
                    "Doanh thu: %{x:,.2f} EUR<br>"
                    "Biên LN gia quyền: %{y:.2f}%<br>"
                    "Mã: %{customdata[0]} · Dòng POS: %{customdata[1]} · CH-ngày: %{customdata[2]}<extra></extra>"
                )
            )
            style_plotly(
                fig_mx,
                palette,
                height=420,
                xaxis_title="Doanh thu (EUR)",
                yaxis_title="Biên LN gộp gia quyền (%)",
            )
            fig_mx.update_yaxes(ticksuffix="%")
            fig_mx.update_layout(legend_title_text="Quốc gia")
            st.plotly_chart(fig_mx, width="stretch", theme=None, config=plotly_config())
            st.caption(
                f"Ngưỡng trung vị tập đang hiển thị ({n_mx} cửa hàng): Doanh thu = **{med_rev:,.0f} EUR**, "
                f"Biên LN gia quyền = **{fmt_pct(med_mrg, already_scaled=True)}**."
            )

    # Row 3: EU Geography & Country Seasonality (7) + Promo Volume Share & Breakdown (5)
    col_geo, col_gauge = st.columns([7, 5], gap="medium")

    with col_geo:
        with st.container(border=True):
            render_chart_header(
                "Địa Lý & Mùa Vụ Theo Quốc Gia Châu Âu (ONYX EU)",
                "Gom bản đồ, xếp hạng quốc gia và mùa vụ 12 tháng vào một khung tránh lặp thông tin",
            )
            render_scope_strip(eu_scope_text, kind="default" if is_onyx_selected else "warn")
            c_sql, c_params = sql_eu_country_summary(schema, filters)
            c_df = db.run_query_df(c_sql, c_params)
            cm_sql, cm_params = sql_eu_country_month_heatmap(schema, filters)
            cm_df = db.run_query_df(cm_sql, cm_params)

            if c_df.empty:
                render_empty_state()
            else:
                c_df = c_df.copy()
                c_df["country_vi"] = c_df["country_code"].map(country_label)
                c_df["iso3"] = c_df["country_code"].map(ISO2_TO_ISO3)

                tab_map, tab_bar, tab_hm = st.tabs(["Bản đồ Châu Âu", "Cột Quốc gia", "Heatmap Quốc gia × Tháng"])
                with tab_map:
                    fig_map = px.choropleth(
                        c_df,
                        locations="iso3",
                        locationmode="ISO-3",
                        color="line_amount",
                        hover_name="country_vi",
                        hover_data={
                            "iso3": False,
                            "line_amount": ":,.2f",
                            "sold_qty": ":,.0f",
                            "weighted_margin_pct": ":.2f",
                            "store_count": True,
                        },
                        color_continuous_scale=list(palette.continuous_scale),
                        labels={
                            "line_amount": "Doanh thu (EUR)",
                            "sold_qty": "Sản lượng",
                            "weighted_margin_pct": "Biên LN gia quyền (%)",
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
                        y="line_amount",
                        text_auto=".3s",
                        hover_data={"weighted_margin_pct": ":.2f", "store_count": True},
                        color_discrete_sequence=[palette.primary],
                    )
                    fig_cbar.update_traces(
                        textposition="outside",
                        hovertemplate="Quốc gia: %{x}<br>Doanh thu: %{y:,.2f} EUR<br>Biên LN GQ: %{customdata[0]:.2f}% · Số CH: %{customdata[1]}<extra></extra>",
                    )
                    style_plotly(
                        fig_cbar,
                        palette,
                        height=345,
                        show_legend=False,
                        xaxis_title="Quốc gia",
                        yaxis_title="Doanh thu (EUR)",
                    )
                    polish_vertical_bar_headroom(fig_cbar, float(c_df["line_amount"].max()))
                    st.plotly_chart(fig_cbar, width="stretch", theme=None, config=plotly_config())

                with tab_hm:
                    if cm_df.empty:
                        render_empty_state()
                    else:
                        piv = cm_df.pivot(index="month_num", columns="country_code", values="sold_qty")
                        piv = piv.reindex(index=sorted(piv.index), columns=sorted(piv.columns))
                        y_labels = [f"Tháng {int(m)}" for m in piv.index]
                        x_labels = [country_label(str(c)) for c in piv.columns]
                        text_vals = [[f"{round(v):,}" if pd.notna(v) else "" for v in row] for row in piv.values]
                        fig_cm = go.Figure(
                            data=go.Heatmap(
                                z=piv.values,
                                x=x_labels,
                                y=y_labels,
                                text=text_vals,
                                texttemplate="%{text}",
                                textfont=dict(size=10.5),
                                colorscale=list(palette.continuous_scale),
                                colorbar=dict(title="Sản lượng", thickness=12),
                                hovertemplate="Quốc gia: %{x}<br>%{y}<br>Sản lượng: %{z:,.0f}<extra></extra>",
                            )
                        )
                        style_plotly(fig_cm, palette, height=345, show_legend=False, xaxis_title="Quốc gia", yaxis_title="Tháng")
                        fig_cm.update_yaxes(autorange="reversed")
                        st.plotly_chart(fig_cm, width="stretch", theme=None, config=plotly_config())

    with col_gauge:
        with st.container(border=True):
            render_chart_header(
                "Tỷ Trọng Sản Lượng Có Khuyến Mãi (ONYX EU)",
                "Đo tỷ trọng lượng bán có khuyến mãi trên tổng sản lượng (chỉ là thống kê mô tả, chưa kết luận hiệu quả nhân quả)",
            )
            render_scope_strip(eu_scope_text, kind="default" if is_onyx_selected else "warn")
            pr_sql, pr_params = sql_eu_promo_breakdown(schema, filters)
            pr_df = db.run_query_df(pr_sql, pr_params)
            if pr_df.empty:
                render_empty_state()
            else:
                tot_qty = float(pd.to_numeric(pr_df["sold_qty"], errors="coerce").fillna(0).sum())
                promo_qty = float(pd.to_numeric(pr_df["promo_sold_qty"], errors="coerce").fillna(0).sum())
                weighted_promo = (promo_qty / tot_qty * 100.0) if tot_qty > 0 else None
                if weighted_promo is None:
                    render_empty_state()
                else:
                    fig_g = go.Figure(
                        go.Indicator(
                            mode="gauge+number",
                            value=weighted_promo,
                            number={"suffix": "%", "valueformat": ".2f", "font": {"size": 36, "color": palette.ink}},
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
                    style_plotly(fig_g, palette, height=220, show_legend=False)
                    st.plotly_chart(fig_g, width="stretch", theme=None, config=plotly_config())

                    pr_disp = pd.DataFrame(
                        {
                            "Nhóm giao dịch": ["Có khuyến mãi" if bool(r["has_promotion"]) else "Không khuyến mãi" for _, r in pr_df.iterrows()],
                            "Số dòng dữ liệu": pr_df["mart_rows"],
                            "Sản lượng": safe_round(pr_df["sold_qty"], 0),
                            "Biên LN gia quyền (%)": safe_round(pr_df["weighted_margin_pct"], 2),
                            "Đơn giá GQ (EUR)": safe_round(pr_df["weighted_unit_price"], 2),
                        }
                    )
                    st.dataframe(pr_disp, width="stretch", hide_index=True, height=110)
                    st.caption(
                        "Không đủ baseline/đối chứng trước–trong–sau khuyến mãi nên chưa đánh giá uplift hay hiệu quả ROI."
                    )

    # Row 4: Full-width Tabbed Brand Margin & Profit (ONYX EU)
    with st.container(border=True):
        render_chart_header(
            "Biên Lợi Nhuận Gia Quyền & Tổng Lợi Nhuận Theo Thương Hiệu (ONYX EU)",
            "Dùng biên LN gia quyền SUM(margin) / SUM(revenue); bảng cột xếp hạng toàn bộ thương hiệu",
        )
        render_scope_strip(eu_scope_text, kind="default" if is_onyx_selected else "warn")
        bm_sql, bm_params = sql_eu_brand_margin_and_profit(schema, filters)
        bm_df = db.run_query_df(bm_sql, bm_params)
        if bm_df.empty:
            render_empty_state()
        else:
            t_b1, t_b2 = st.tabs(["Scatter Doanh thu × Biên LN gia quyền", "Xếp hạng Tổng Lợi Nhuận"])
            with t_b1:
                fig_bm = px.scatter(
                    bm_df,
                    x="line_amount",
                    y="weighted_margin_pct",
                    size="sold_qty",
                    color="brand_name",
                    hover_data={"margin_amount": ":,.2f", "sold_qty": ":,.0f", "row_avg_margin_pct": ":.2f"},
                    color_discrete_sequence=list(palette.discrete) * 3,
                )
                fig_bm.update_traces(
                    hovertemplate=(
                        "Thương hiệu: %{fullData.name}<br>"
                        "Doanh thu: %{x:,.2f} EUR<br>"
                        "Biên LN gia quyền: %{y:.2f}% (TB dòng: %{customdata[2]:.2f}%)<br>"
                        "Lợi nhuận: %{customdata[0]} EUR · SL: %{customdata[1]}<extra></extra>"
                    )
                )
                style_plotly(
                    fig_bm,
                    palette,
                    height=370,
                    xaxis_title="Doanh thu (EUR)",
                    yaxis_title="Biên LN gộp gia quyền (%)",
                )
                fig_bm.update_yaxes(ticksuffix="%")
                fig_bm.update_layout(
                    legend_title_text="Thương hiệu",
                    legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.02, font=dict(size=10)),
                    margin=dict(l=14, r=130, t=18, b=16),
                )
                st.plotly_chart(fig_bm, width="stretch", theme=None, config=plotly_config())

            with t_b2:
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
                    height=360,
                    show_legend=False,
                    xaxis_title="Thương hiệu",
                    yaxis_title="Tổng lợi nhuận (EUR)",
                )
                polish_vertical_bar_headroom(fig_bp, float(bm_df["margin_amount"].max()))
                fig_bp.update_xaxes(tickangle=-20)
                st.plotly_chart(fig_bp, width="stretch", theme=None, config=plotly_config())

    # Row 5 (Bottom): Searchable Store Lookup Table
    with st.container(border=True):
        render_chart_header(
            "Bảng Tra Cứu Chi Tiết Từng Cửa Hàng",
            "Hiển thị Số dòng bán, Cửa hàng-ngày có bán, Biên lợi nhuận gia quyền vs TB theo dòng (chưa có dữ liệu đếm đơn duy nhất)",
        )
        store_search = st.text_input(
            "Tìm nhanh theo mã, tên cửa hàng hoặc quốc gia",
            placeholder="Ví dụ: ONYX:PH0120, Madrid, Berlin...",
            key="p3_store_search",
        )
        st_sql, st_params = sql_store_performance_table(schema, filters, search_text=store_search)
        st_df = db.run_query_df(st_sql, st_params)
        if st_df.empty:
            render_empty_state()
        else:
            rev_label = f"Doanh thu ({ccy})" if ccy else "Doanh thu"
            mrg_label = f"Lợi nhuận ({ccy})" if ccy else "Lợi nhuận"
            qty_col_series = (
                pd.Series([None] * len(st_df))
                if uom_guard.is_multi_uom_blocked
                else safe_round(st_df["sold_qty"], 0)
            )
            disp_df = pd.DataFrame(
                {
                    "Mã cửa hàng": st_df["store_code"],
                    "Tên cửa hàng": st_df["store_name"],
                    "Quốc gia": st_df["country_code"].map(country_label),
                    "Số dòng POS": st_df["line_count"],
                    "CH-ngày có bán": st_df["active_store_days"],
                    "Sản lượng (nếu 1 ĐVT)": qty_col_series,
                    rev_label: safe_round(st_df["line_amount"], 2),
                    mrg_label: safe_round(st_df["margin_amount"], 2),
                    "Biên LN gia quyền (%)": safe_round(st_df["weighted_margin_pct"], 2),
                    "Biên LN TB theo dòng (%)": safe_round(st_df["row_avg_margin_pct"], 2),
                }
            )
            st.dataframe(
                disp_df,
                width="stretch",
                hide_index=True,
                height=320,
                column_config={
                    "Số dòng POS": st.column_config.NumberColumn(format="%,d"),
                    "CH-ngày có bán": st.column_config.NumberColumn(format="%,d"),
                    "Sản lượng (nếu 1 ĐVT)": st.column_config.NumberColumn(format="%,.0f"),
                    rev_label: st.column_config.NumberColumn(format="%,.2f"),
                    mrg_label: st.column_config.NumberColumn(format="%,.2f"),
                    "Biên LN gia quyền (%)": st.column_config.NumberColumn(format="%.2f%%"),
                    "Biên LN TB theo dòng (%)": st.column_config.NumberColumn(format="%.2f%%"),
                },
            )
            render_csv_download(disp_df, "hieu_suat_cua_hang.csv", key="p3_csv_stores")

    with st.expander("Định nghĩa chỉ số & nguồn dữ liệu"):
        st.markdown(
            "- **Biến động cùng cửa hàng:** Chỉ xếp hạng các cửa hàng có phát sinh bán ở cả 2 kỳ so sánh (`Cả 2 kỳ`), tính trên toàn bộ cửa hàng hợp lệ trước khi cắt Top tăng/giảm để hiển thị.\n"
            "- **Ma trận & Khuyến mãi ONYX EU (`SYNTHETIC`):** Chỉ nguồn ONYX Châu Âu ghi nhận giá vốn, lợi nhuận gộp (`margin_amount`) và cờ khuyến mãi (`has_promotion`). Tỷ trọng sản lượng có khuyến mãi là thống kê mô tả, không đo lường uplift hay hiệu quả ROI do thiếu nhóm đối chứng.\n"
            "- **Biên lợi nhuận gia quyền:** `SUM(margin_amount) / SUM(line_amount)`; khác với trung bình cộng theo từng dòng mart (`SP × CH × Ngày`).\n"
            "- **Giới hạn phạm vi Sales:** Dữ liệu tại đây không bao gồm tồn kho hiện hữu, hàng hết hạn hoặc điều chuyển giữa các cửa hàng."
        )


render_page(get_current_filters())
