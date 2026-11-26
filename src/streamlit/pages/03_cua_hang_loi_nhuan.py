"""Page 2 (Supply Chain View): City Clusters, Interactive Street Map, Store Watchlist & Margin Matrix."""

from __future__ import annotations

from dataclasses import replace

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
from components.filters import get_current_filters, get_track_bounds, prune_selection
from config import (
    country_label,
    currency_display_unit,
    currency_multiplier,
    fmt_compact,
    resolve_scope_meta,
    safe_round,
    track_label,
)
import db
from queries import (
    EU_STORE_MATRIX_TRACK,
    FilterState,
    sql_dimension_variance,
    sql_eu_brand_margin_and_profit,
    sql_eu_country_summary,
    sql_eu_promo_breakdown,
    sql_eu_store_matrix,
    sql_monthly_sales_trend,
    sql_sales_by_country,
    sql_store_map_points,
    sql_store_performance_table,
)
from ui import (
    get_active_palette,
    open_page_layout_columns,
    plotly_config,
    polish_diverging_bar,
    polish_horizontal_bar,
    polish_vertical_bar_headroom,
    render_chart_header,
    render_csv_download,
    render_empty_state,
    render_insight_box,
    render_page_header,
    render_right_explanation_panel,
    render_scope_strip,
    render_street_map,
    render_top_action_bar,
    style_plotly,
)


def render_page(filters: FilterState) -> None:
    schema = db.get_active_schema()
    palette = get_active_palette()
    bounds = get_track_bounds()
    track_min_date = bounds.get("min_date")
    track_max_date = bounds.get("max_date")
    uoms_avail = bounds.get("uoms_avail") or ()

    scope = bounds.get("scope_meta")
    if scope is None:
        scope = resolve_scope_meta(
            bounds.get("active_tracks") or (),
            bounds.get("active_currencies") or (),
            bounds.get("active_provenances") or (),
            display_vnd=bool(filters.display_vnd),
            fallback_track=filters.dataset_track,
        )
    ccy = scope.currency_code
    has_rev = scope.has_revenue
    prov_class = scope.provenance_class
    to_vnd = scope.to_vnd
    disp_ccy = scope.disp_ccy
    ccy_mult = scope.ccy_mult

    is_unified = filters.dataset_track is None
    is_onyx_only = scope.single_track_id == EU_STORE_MATRIX_TRACK
    is_onyx_selected = is_onyx_only or (is_unified and scope.has_margin)
    eu_scope_text = (
        f"Nguồn: {track_label(EU_STORE_MATRIX_TRACK)} · Áp dụng đầy đủ bộ lọc khu vực/cụm/cửa hàng/ngày của thanh bên."
        if (is_onyx_only or is_unified)
        else "Phần tham chiếu riêng: ONYX Châu Âu — Mô phỏng (EUR) · Không áp dụng bộ lọc nguồn đang chọn ở thanh bên."
    )

    render_page_header(
        "Cụm Cửa Hàng & Bản Đồ",
        "Theo dõi theo cụm thành phố trên bản đồ đường phố, nhận diện cửa hàng sụt giảm và phân tầng hiệu quả biên.",
        dataset_track=filters.dataset_track,
        extra_pills=[
            ("Góc nhìn Chuỗi cung ứng", "default"),
            ("Ma trận LN & KM: ONYX EU — Mô phỏng", "synthetic"),
        ],
    )

    # Local Page 3 controls lifted above queries so cluster selection applies uniformly across all 7 panels
    show_eu_network = False
    if not is_unified and not is_onyx_only:
        with st.container(border=True):
            show_eu_network = st.toggle(
                "Mạng lưới 120 CH EU",
                value=False,
                key="p3_map_force_eu",
                help="Nguồn hiện tại chỉ có 1 cửa hàng; bật để xem toàn bộ 120 cửa hàng / 38 cụm tại châu Âu (mô phỏng).",
            )
    else:
        st.session_state["p3_map_force_eu"] = False

    map_sql, map_params = sql_store_map_points(schema, filters, force_onyx=show_eu_network)
    raw_map_df = db.run_query_df(map_sql, map_params)

    if not raw_map_df.empty and "city_cluster" in raw_map_df.columns:
        p3_clusters_avail = sorted(raw_map_df["city_cluster"].dropna().astype(str).unique().tolist())
    elif not show_eu_network:
        p3_clusters_avail = (
            list(filters.city_clusters)
            if filters.city_clusters
            else list(bounds.get("clusters_avail") or ())
        )
    else:
        p3_clusters_avail = []

    sel_map_clusters: list[str] = []
    if len(p3_clusters_avail) > 1:
        prune_selection("p3_map_clusters", p3_clusters_avail)
        with st.container(border=True):
            sel_map_clusters = st.multiselect(
                "Lọc Cụm TP",
                options=p3_clusters_avail,
                placeholder=f"Tất cả ({len(p3_clusters_avail)} cụm · {len(raw_map_df)} CH)",
                key="p3_map_clusters",
            )
    else:
        st.session_state["p3_map_clusters"] = []

    map_df = (
        raw_map_df[raw_map_df["city_cluster"].astype(str).isin(sel_map_clusters)].copy()
        if (sel_map_clusters and not raw_map_df.empty and "city_cluster" in raw_map_df.columns)
        else raw_map_df
    )
    page_filters = (
        replace(filters, city_clusters=tuple(sel_map_clusters))
        if (sel_map_clusters and not show_eu_network)
        else filters
    )

    m_sql, m_params = sql_monthly_sales_trend(schema, page_filters)
    m_df = db.run_query_df(m_sql, m_params)
    avail_months = m_df["year_month"].tolist() if not m_df.empty else []
    cmp_window = resolve_comparison_periods(
        page_filters.date_start,
        page_filters.date_end,
        mode=page_filters.compare_mode,
        available_months=avail_months,
        track_min_date=track_min_date,
        track_max_date=track_max_date,
    )

    local_tags: list[str] = []
    if sel_map_clusters:
        cl_short = ", ".join(sel_map_clusters[:2])
        if len(sel_map_clusters) > 2:
            cl_short += f" (+{len(sel_map_clusters) - 2})"
        local_tags.append(f"Cụm EU: {cl_short}" if show_eu_network else f"Cụm trang: {cl_short}")

    bar_filters = replace(filters, city_clusters=()) if (sel_map_clusters and not show_eu_network) else filters
    render_top_action_bar(
        bar_filters,
        page_key="p3",
        compare_window=cmp_window,
        local_tags=local_tags,
        show_compare_jump=True,
    )

    uom_guard = evaluate_uom_compatibility(page_filters.dataset_track, page_filters.clean_uoms, uoms_avail)
    use_rev_var = bool(has_rev)
    c_col = "cur_rev" if use_rev_var else "cur_qty"
    p_col = "prev_rev" if use_rev_var else "prev_qty"
    var_metric_label = f"Doanh thu ({disp_ccy})" if use_rev_var else f"Sản lượng ({uom_guard.single_uom or 'ĐVT'})"
    var_unit = disp_ccy if use_rev_var else uom_guard.single_uom

    store_var_df = pd.DataFrame()
    if cmp_window.valid and cmp_window.cur_start and cmp_window.prev_start:
        sv_sql, sv_params = sql_dimension_variance(
            schema,
            page_filters,
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

    mx_sql, mx_params = sql_eu_store_matrix(schema, page_filters)
    mx_df = db.run_query_df(mx_sql, mx_params)
    matrix_meta = resolve_matrix_source_meta(
        mx_df,
        active_track=page_filters.dataset_track,
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

    main_col, drawer_col = open_page_layout_columns()

    with main_col:
        render_insight_box(
            "Xem nhanh biến động & chất lượng cửa hàng",
            build_store_insights(
                var_df=store_var_df,
                watchlist_df=watchlist_df,
                matrix_df=mx_df,
                window=cmp_window,
                metric_label=var_metric_label,
                metric_unit=ccy if use_rev_var else uom_guard.single_uom,
                provenance_class=prov_class,
                watchlist_result=watchlist_res,
                matrix_meta=matrix_meta,
            ),
            note=cmp_window.note or None,
        )

        # Row 1: Hero Supply Chain Interactive Street Map (City Clusters & GPS Stores)
        with st.container(border=True):
            render_chart_header(
                "Bản Đồ Cụm & Cửa Hàng",
                "",
                info_tooltip="Bản đồ nền đường phố chi tiết (cuộn để zoom tới từng tuyến phố). Có thể gom theo Cụm thành phố hoặc soi từng nhà thuốc ở chế độ 2D Phố / 3D Cột.",
            )
            mc1, mc2, mc3, mc4 = st.columns([2.5, 2.5, 2.5, 2.5])
            with mc1:
                map_mode = st.selectbox(
                    "Cấp độ",
                    options=["store", "cluster"],
                    format_func=lambda k: "Cửa hàng" if k == "store" else "Cụm TP",
                    key="p3_map_mode",
                )
            with mc2:
                map_engine = st.selectbox(
                    "Chế độ",
                    options=["maplibre", "pydeck"],
                    format_func=lambda k: "2D Phố" if k == "maplibre" else "3D Cột",
                    key="p3_map_engine",
                )
            with mc3:
                size_opts = ["line_amount", "sold_qty", "line_count"] if has_rev else ["sold_qty", "line_count"]
                if st.session_state.get("p3_map_size") not in size_opts:
                    st.session_state["p3_map_size"] = size_opts[0]
                map_size = st.selectbox(
                    "Cỡ điểm",
                    options=size_opts,
                    format_func=lambda k: {"line_amount": "Doanh thu", "sold_qty": "Sản lượng", "line_count": "Lượt bán"}[k],
                    key="p3_map_size",
                )
            with mc4:
                if is_onyx_only:
                    color_opts = ["weighted_margin_pct", "avg_temp_mean", "avg_precip_sum", "line_amount"]
                elif is_onyx_selected:
                    color_opts = ["avg_temp_mean", "avg_precip_sum", "weighted_margin_pct", "line_amount"]
                elif has_rev:
                    color_opts = ["avg_temp_mean", "avg_precip_sum", "line_amount"]
                else:
                    color_opts = ["avg_temp_mean", "avg_precip_sum", "sold_qty"]
                if st.session_state.get("p3_map_color") not in color_opts:
                    st.session_state["p3_map_color"] = color_opts[0]
                map_color = st.selectbox(
                    "Màu",
                    options=color_opts,
                    format_func=lambda k: {
                        "weighted_margin_pct": "Tỷ suất LN (%)",
                        "avg_temp_mean": "Nhiệt độ TB (°C)",
                        "avg_precip_sum": "Lượng mưa TB (mm)",
                        "line_amount": "Doanh thu",
                        "sold_qty": "Sản lượng",
                    }.get(k, k),
                    key="p3_map_color",
                )

            eff_map_ccy = "EUR" if show_eu_network else ccy
            render_street_map(
                map_df,
                mode=map_mode,
                map_engine=map_engine,
                size_col=map_size,
                color_col=map_color,
                palette=palette,
                ccy_label=eff_map_ccy,
                to_vnd=bool(filters.display_vnd and eff_map_ccy),
                height=430,
            )

        # Row 2: Same-Store Variance (6) + Store Watchlist (6)
        col_var, col_watch = st.columns([6, 6], gap="medium")

        with col_var:
            with st.container(border=True):
                render_chart_header(
                    "Biến Động Cùng Cửa Hàng",
                    f"{cmp_window.cur_label} vs {cmp_window.prev_label}",
                    info_tooltip="Chỉ xếp hạng những cửa hàng có phát sinh bán đồng thời ở cả 2 kỳ so sánh (Top tăng & Top giảm).",
                )
                if not cmp_window.valid or store_var_df.empty:
                    render_empty_state(cmp_window.note or "Chưa có dữ liệu so sánh cửa hàng trong khoảng lọc.")
                else:
                    both = store_var_df[store_var_df["presence_status"] == "Cả 2 kỳ"].copy()
                    if len(both) == 0:
                        render_empty_state("Không có cửa hàng nào phát sinh bán đồng thời ở cả 2 kỳ so sánh.")
                    elif len(both) == 1:
                        row_single = both.iloc[0]
                        d_s = float(row_single["delta"]) * (ccy_mult if use_rev_var else 1.0)
                        d_sign = "+" if d_s > 0 else ("−" if d_s < 0 else "")
                        st.info(
                            f"Có **1 cửa hàng** phát sinh cả 2 kỳ trong nguồn `{track_label(filters.dataset_track)}` (`{row_single['store_name']}`). "
                            f"Kỳ trước: **{fmt_compact(float(row_single[p_col]) * (ccy_mult if use_rev_var else 1.0))}**, "
                            f"kỳ này: **{fmt_compact(float(row_single[c_col]) * (ccy_mult if use_rev_var else 1.0))}** "
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
                            comb = comb.sort_values("delta", ascending=True).copy()
                            v_mult = ccy_mult if use_rev_var else 1.0
                            comb["_delta_disp"] = comb["delta"] * v_mult
                            comb["_p_disp"] = comb[p_col] * v_mult
                            comb["_c_disp"] = comb[c_col] * v_mult
                            colors = [palette.primary if d >= 0 else "#dc2626" for d in comb["_delta_disp"]]
                            fig_sv = go.Figure(
                                go.Bar(
                                    x=comb["_delta_disp"],
                                    y=comb["store_name"],
                                    orientation="h",
                                    marker_color=colors,
                                    text=[f"{d:+,.0f}" for d in comb["_delta_disp"]],
                                    textposition="outside",
                                    customdata=list(
                                        zip(
                                            comb["_p_disp"],
                                            comb["_c_disp"],
                                            comb["contrib_pp"].fillna(0.0),
                                            (comb["pct_change"] * 100.0).fillna(0.0),
                                        )
                                    ),
                                    hovertemplate=(
                                        "<b>%{y}</b><br>"
                                        "Kỳ trước: %{customdata[0]:,.0f}<br>"
                                        "Kỳ này: %{customdata[1]:,.0f}<br>"
                                        "Chênh lệch: %{x:+,.0f} (%{customdata[3]:+.2f}%)<br>"
                                        "Đóng góp: %{customdata[2]:+.2f} điểm %<extra></extra>"
                                    ),
                                )
                            )
                            style_plotly(fig_sv, palette, height=350, show_legend=False, xaxis_title=f"Chênh lệch {var_metric_label}", yaxis_title="")
                            polish_diverging_bar(fig_sv, float(comb["_delta_disp"].abs().max()))
                            st.plotly_chart(fig_sv, width="stretch", theme=None, config=plotly_config())

        with col_watch:
            with st.container(border=True):
                render_chart_header(
                    "Cửa Hàng Cần Lưu Ý",
                    f"{watchlist_res.title} · {watchlist_res.subtitle}",
                    info_tooltip="Tiêu chí cảnh báo: Doanh thu ≥ trung vị nhưng Tỷ suất LN < trung vị, hoặc sụt giảm ≥ 15%, hoặc Tỷ suất LN giảm ≥ 1.5 điểm %.",
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
                        mx_w_ccy = currency_display_unit(matrix_meta.currency_code, to_vnd=filters.display_vnd) or matrix_meta.currency_code
                        mx_w_mult = currency_multiplier(matrix_meta.currency_code, to_vnd=filters.display_vnd)
                        rev_col_w = f"Doanh thu ({mx_w_ccy})" if mx_w_ccy else "Doanh thu (EUR)"
                        w_disp = pd.DataFrame(
                            {
                                "Cửa hàng": watchlist_df["store_name"],
                                "Quốc gia": watchlist_df["country_code"].map(country_label),
                                rev_col_w: safe_round(pd.to_numeric(watchlist_df["line_amount"], errors="coerce") * mx_w_mult, 0),
                                "Tỷ suất LN (%)": safe_round(watchlist_df["weighted_margin_pct"], 2),
                                "Biến động kỳ (%)": safe_round(pd.to_numeric(watchlist_df["pct_change"], errors="coerce") * 100.0, 2),
                                reason_col_lbl: watchlist_df["Lý do cần xem xét"],
                            }
                        )
                        w_cfg = {
                            rev_col_w: st.column_config.NumberColumn(format="%,.0f"),
                            "Tỷ suất LN (%)": st.column_config.NumberColumn(format="%.2f%%"),
                            "Biến động kỳ (%)": st.column_config.NumberColumn(format="%+.2f%%"),
                        }
                    else:
                        val_col_lbl = f"Kỳ này ({var_unit})" if var_unit else "Kỳ này"
                        v_mult = ccy_mult if use_rev_var else 1.0
                        w_disp = pd.DataFrame(
                            {
                                "Cửa hàng": watchlist_df["store_name"],
                                val_col_lbl: safe_round(pd.to_numeric(watchlist_df[c_col], errors="coerce") * v_mult, 0),
                                "Chênh lệch": safe_round(pd.to_numeric(watchlist_df["delta"], errors="coerce") * v_mult, 0),
                                "Biến động (%)": safe_round(pd.to_numeric(watchlist_df["pct_change"], errors="coerce") * 100.0, 2),
                                reason_col_lbl: watchlist_df["Lý do cần xem xét"],
                            }
                        )
                        w_cfg = {
                            val_col_lbl: st.column_config.NumberColumn(format="%,.0f"),
                            "Chênh lệch": st.column_config.NumberColumn(format="%+,.0f"),
                            "Biến động (%)": st.column_config.NumberColumn(format="%+.2f%%"),
                        }
                    st.dataframe(w_disp, width="stretch", hide_index=True, height=310, column_config=w_cfg)
                    render_csv_download(w_disp, "cua_hang_can_xem_xet.csv", key="p3_csv_watchlist")

        # Row 3: Store Margin Matrix (with strict independent MatrixSourceMeta labeling!)
        mx_disp_ccy = currency_display_unit(matrix_meta.currency_code, to_vnd=filters.display_vnd) or matrix_meta.currency_code
        mx_mult = currency_multiplier(matrix_meta.currency_code, to_vnd=filters.display_vnd)
        with st.container(border=True):
            n_mx = len(mx_df)
            render_chart_header(
                "Ma Trận Doanh Thu × Tỷ Suất LN",
                f"{n_mx} Cửa Hàng · {matrix_meta.label_vi} · {matrix_meta.currency_code}",
                info_tooltip="Đường nét đứt chia 4 góc phần tư theo trung vị Doanh thu & Tỷ suất LN. Góc dưới phải = Doanh thu cao nhưng Tỷ suất LN thấp.",
            )
            render_scope_strip(
                f"Nguồn: {matrix_meta.label_vi} ({matrix_meta.currency_code}) · {matrix_meta.scope_note}",
                kind="default" if matrix_meta.matches_sidebar_track else "warn",
            )
            if mx_df.empty:
                render_empty_state()
            else:
                mx_plot = mx_df.copy()
                mx_plot["country_vi"] = mx_plot["country_code"].map(country_label)
                mx_plot["rev_disp"] = pd.to_numeric(mx_plot["line_amount"], errors="coerce") * mx_mult
                med_rev = float(mx_plot["rev_disp"].median())
                med_mrg = float(mx_plot["weighted_margin_pct"].median())
                fig_mx = px.scatter(
                    mx_plot,
                    x="rev_disp",
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
                        f"Doanh thu: %{{x:,.0f}} {mx_disp_ccy}<br>"
                        "Tỷ suất LN: %{y:.2f}%<br>"
                        "Mã: %{customdata[0]} · Lượt dòng: %{customdata[1]}<extra></extra>"
                    )
                )
                style_plotly(fig_mx, palette, height=390, xaxis_title=f"Doanh thu ({mx_disp_ccy})", yaxis_title="Tỷ suất lợi nhuận (%)")
                fig_mx.update_yaxes(ticksuffix="%")
                fig_mx.update_layout(legend_title_text="Quốc gia")
                st.plotly_chart(fig_mx, width="stretch", theme=None, config=plotly_config())

        # Row 4: Clean Tabbed Supply Chain Details (City Clusters Ranking, Geography & Promo, Brands, Table)
        with st.container(border=True):
            render_chart_header(
                "Phân Tích Cụm & Tra Cứu",
                "",
                info_tooltip="Tổng hợp xếp hạng theo cụm thành phố, khuyến mãi/thương hiệu ONYX EU và bảng tra cứu từng cửa hàng.",
            )
            t_cl, t_geo_promo, t_brand, t_tbl = st.tabs(
                ["Xếp hạng Cụm", "Quốc gia & KM", "Thương hiệu", "Tra cứu CH"]
            )

            with t_cl:
                if map_df.empty or "city_cluster" not in map_df.columns:
                    render_empty_state()
                else:
                    cl_df = map_df.copy()
                    cl_agg = (
                        cl_df.groupby(["city_cluster", "country_code"], as_index=False)
                        .agg(
                            store_count=("store_code", "nunique"),
                            sold_qty=("sold_qty", "sum"),
                            line_amount=("line_amount", "sum"),
                            margin_amount=("margin_amount", "sum"),
                            line_count=("line_count", "sum"),
                        )
                    )
                    cl_val_col = "line_amount" if has_rev or show_eu_network else "sold_qty"
                    cl_agg["_metric"] = pd.to_numeric(cl_agg[cl_val_col], errors="coerce").fillna(0.0)
                    if cl_val_col == "line_amount":
                        cl_agg["_metric"] = cl_agg["_metric"] * (currency_multiplier(eff_map_ccy, filters.display_vnd) if eff_map_ccy else 1.0)
                    cl_agg["label"] = cl_agg.apply(lambda r: f"{r['city_cluster']} ({int(r['store_count'])} CH)", axis=1)
                    cl_agg = cl_agg.sort_values("_metric", ascending=False).head(20)
                    fig_cl = px.bar(
                        cl_agg,
                        x="_metric",
                        y="label",
                        orientation="h",
                        text_auto=".3s",
                        color_discrete_sequence=[palette.primary],
                    )
                    fig_cl.update_traces(textposition="outside")
                    style_plotly(
                        fig_cl,
                        palette,
                        height=370,
                        show_legend=False,
                        xaxis_title=f"Doanh thu ({currency_display_unit(eff_map_ccy, filters.display_vnd) or ''})" if cl_val_col == "line_amount" else "Sản lượng",
                        yaxis_title="",
                    )
                    polish_horizontal_bar(fig_cl, cl_agg["label"].tolist(), float(cl_agg["_metric"].max() or 0.0))
                    st.plotly_chart(fig_cl, width="stretch", theme=None, config=plotly_config())

            with t_geo_promo:
                render_scope_strip(eu_scope_text, kind="default" if is_onyx_selected else "warn")
                g_left, g_right = st.columns([6.0, 6.0], gap="medium")
                with g_left:
                    if is_unified:
                        c_sql, c_params = sql_sales_by_country(schema, page_filters)
                        c_df = db.run_query_df(c_sql, c_params)
                        use_rev_ctry = bool(has_rev and not c_df.empty and pd.to_numeric(c_df["line_amount"], errors="coerce").notna().any())
                        ctry_hdr = "Doanh Thu Theo Quốc Gia" if use_rev_ctry else "Sản Lượng Theo Quốc Gia"
                        ctry_y_lbl = f"Doanh thu ({disp_ccy})" if use_rev_ctry else "Sản lượng"
                        render_chart_header(
                            ctry_hdr,
                            info_tooltip="Tổng hợp toàn bộ quốc gia trong phạm vi đang lọc (quy đổi VNĐ khi gồm nhiều tiền tệ).",
                        )
                        if c_df.empty:
                            render_empty_state()
                        else:
                            c_df = c_df.copy()
                            c_df["country_vi"] = c_df["country_code"].map(country_label)
                            if use_rev_ctry:
                                c_df["metric_disp"] = pd.to_numeric(c_df["line_amount"], errors="coerce").fillna(0.0) * ccy_mult
                            else:
                                c_df["metric_disp"] = pd.to_numeric(c_df["sold_qty"], errors="coerce").fillna(0.0)
                            c_df = c_df.sort_values("metric_disp", ascending=False)
                            fig_cbar = px.bar(c_df, x="country_vi", y="metric_disp", text_auto=".3s", color_discrete_sequence=[palette.primary])
                            fig_cbar.update_traces(textposition="outside")
                            style_plotly(fig_cbar, palette, height=320, show_legend=False, xaxis_title="Quốc gia", yaxis_title=ctry_y_lbl)
                            polish_vertical_bar_headroom(fig_cbar, float(c_df["metric_disp"].max()))
                            st.plotly_chart(fig_cbar, width="stretch", theme=None, config=plotly_config())
                    else:
                        render_chart_header(
                            "Doanh Thu Theo Quốc Gia",
                            info_tooltip="Tổng doanh thu thực bán theo từng quốc gia trong mạng lưới.",
                        )
                        c_sql, c_params = sql_eu_country_summary(schema, page_filters)
                        c_df = db.run_query_df(c_sql, c_params)
                        if c_df.empty:
                            render_empty_state()
                        else:
                            c_df = c_df.copy()
                            c_df["country_vi"] = c_df["country_code"].map(country_label)
                            c_df["rev_disp"] = pd.to_numeric(c_df["line_amount"], errors="coerce") * mx_mult
                            c_df = c_df.sort_values("rev_disp", ascending=False)
                            fig_cbar = px.bar(c_df, x="country_vi", y="rev_disp", text_auto=".3s", color_discrete_sequence=[palette.primary])
                            fig_cbar.update_traces(textposition="outside")
                            style_plotly(fig_cbar, palette, height=320, show_legend=False, xaxis_title="Quốc gia", yaxis_title=f"Doanh thu ({mx_disp_ccy})")
                            polish_vertical_bar_headroom(fig_cbar, float(c_df["rev_disp"].max()))
                            st.plotly_chart(fig_cbar, width="stretch", theme=None, config=plotly_config())
                with g_right:
                    render_chart_header(
                        "Tác Động Khuyến Mãi vs Giá Thường",
                        info_tooltip="Đối chiếu tỷ trọng sản lượng, tỷ trọng doanh thu và biên lợi nhuận gộp giữa hàng bán có khuyến mãi và hàng bán đúng giá niêm yết.",
                    )
                    pr_sql, pr_params = sql_eu_promo_breakdown(schema, page_filters)
                    pr_df = db.run_query_df(pr_sql, pr_params)
                    if pr_df.empty:
                        render_empty_state()
                    else:
                        tot_qty = float(pd.to_numeric(pr_df["sold_qty"], errors="coerce").fillna(0).sum())
                        tot_rev = float(pd.to_numeric(pr_df["line_amount"], errors="coerce").fillna(0).sum())
                        promo_rows: list[dict[str, object]] = []
                        for _, pr in pr_df.iterrows():
                            nhom = "Có khuyến mãi" if bool(pr.get("has_promotion")) else "Giá thường"
                            sl_share = (float(pr.get("sold_qty") or 0) / tot_qty * 100.0) if tot_qty > 0 else 0.0
                            dt_share = (float(pr.get("line_amount") or 0) / tot_rev * 100.0) if tot_rev > 0 else 0.0
                            mrg_pct = float(pr.get("weighted_margin_pct") or 0.0)
                            promo_rows.extend(
                                [
                                    {"Chỉ số": "Tỷ trọng SL (%)", "Nhóm": nhom, "Giá trị (%)": sl_share},
                                    {"Chỉ số": "Tỷ trọng DT (%)", "Nhóm": nhom, "Giá trị (%)": dt_share},
                                    {"Chỉ số": "Tỷ suất LN (%)", "Nhóm": nhom, "Giá trị (%)": mrg_pct},
                                ]
                            )
                        promo_cmp_df = pd.DataFrame(promo_rows)
                        fig_pr = px.bar(
                            promo_cmp_df,
                            x="Chỉ số",
                            y="Giá trị (%)",
                            color="Nhóm",
                            barmode="group",
                            text_auto=".1f",
                            category_orders={
                                "Chỉ số": ["Tỷ trọng SL (%)", "Tỷ trọng DT (%)", "Tỷ suất LN (%)"],
                                "Nhóm": ["Có khuyến mãi", "Giá thường"],
                            },
                            color_discrete_sequence=[palette.accent, palette.primary],
                        )
                        fig_pr.update_traces(
                            texttemplate="%{y:.1f}%",
                            textposition="outside",
                            hovertemplate="%{x} · %{fullData.name}: %{y:.2f}%<extra></extra>",
                        )
                        style_plotly(fig_pr, palette, height=320, xaxis_title="", yaxis_title="%")
                        polish_vertical_bar_headroom(fig_pr, float(promo_cmp_df["Giá trị (%)"].max() or 100.0))
                        fig_pr.update_yaxes(ticksuffix="%")
                        st.plotly_chart(fig_pr, width="stretch", theme=None, config=plotly_config())

            with t_brand:
                render_scope_strip(eu_scope_text, kind="default" if is_onyx_selected else "warn")
                bm_sql, bm_params = sql_eu_brand_margin_and_profit(schema, page_filters)
                bm_df = db.run_query_df(bm_sql, bm_params)
                if bm_df.empty:
                    render_empty_state()
                else:
                    bm_plot = bm_df.copy()
                    bm_plot["mrg_disp"] = pd.to_numeric(bm_plot["margin_amount"], errors="coerce") * mx_mult
                    fig_bp = px.bar(bm_plot, x="brand_name", y="mrg_disp", text_auto=".3s", color_discrete_sequence=[palette.primary])
                    fig_bp.update_traces(textposition="outside")
                    style_plotly(fig_bp, palette, height=330, show_legend=False, xaxis_title="Thương hiệu", yaxis_title=f"Lợi nhuận ({mx_disp_ccy})")
                    polish_vertical_bar_headroom(fig_bp, float(bm_plot["mrg_disp"].max()))
                    fig_bp.update_xaxes(tickangle=-20)
                    st.plotly_chart(fig_bp, width="stretch", theme=None, config=plotly_config())

            with t_tbl:
                store_search = st.text_input("Tìm nhanh mã, tên cửa hàng hoặc quốc gia", placeholder="Ví dụ: Munich, Berlin, ONYX:PH0120...", key="p3_store_search")
                st_sql, st_params = sql_store_performance_table(schema, page_filters, search_text=store_search)
                st_df = db.run_query_df(st_sql, st_params)
                if st_df.empty:
                    render_empty_state()
                else:
                    rev_label = f"Doanh thu ({disp_ccy})" if disp_ccy else "Doanh thu"
                    mrg_label = f"Lợi nhuận ({disp_ccy})" if disp_ccy else "Lợi nhuận"
                    disp_df = pd.DataFrame(
                        {
                            "Mã cửa hàng": st_df["store_code"],
                            "Tên cửa hàng": st_df["store_name"],
                            "Quốc gia": st_df["country_code"].map(country_label),
                            "Lượt bán (dòng)": st_df["line_count"],
                            "CH-ngày": st_df["active_store_days"],
                            "Sản lượng (nếu 1 ĐVT)": pd.Series([None] * len(st_df)) if uom_guard.is_multi_uom_blocked else safe_round(st_df["sold_qty"], 0),
                            rev_label: safe_round(pd.to_numeric(st_df["line_amount"], errors="coerce") * ccy_mult, 0 if to_vnd else 2),
                            mrg_label: safe_round(pd.to_numeric(st_df["margin_amount"], errors="coerce") * ccy_mult, 0 if to_vnd else 2),
                            "Tỷ suất LN (%)": safe_round(st_df["weighted_margin_pct"], 2),
                        }
                    )
                    st.dataframe(disp_df, width="stretch", hide_index=True, height=300)
                    render_csv_download(disp_df, "hieu_suat_cua_hang.csv", key="p3_csv_stores")

    render_right_explanation_panel(
        drawer_col,
        page_key="p3",
        page_title="Cụm CH & Bản Đồ",
        glossary_items=[
            ("Cụm cửa hàng (City Cluster)", "Gom các nhà thuốc nằm trong cùng thành phố (ví dụ Munich gồm 7 nhà thuốc) để Supply Chain đánh giá quy mô theo vùng thay vì nhìn rời rạc."),
            ("Bản đồ đường phố (2D Phố / 3D Cột)", "Dùng tọa độ GPS từng cửa hàng trong `bi_sales_weather_enriched`; chế độ Cụm TP gom trung bình tọa độ và cộng dồn quy mô toàn cụm."),
            ("Biến động cùng cửa hàng", "Chỉ xếp hạng cửa hàng phát sinh bán đồng thời ở cả 2 kỳ (`Cả 2 kỳ`), tính trên toàn bộ cửa hàng hợp lệ trước khi cắt Top."),
            ("Cảnh báo vs Danh sách tham khảo", "Khi có cửa hàng vượt tiêu chí (DT ≥ trung vị & Tỷ suất LN < trung vị, hoặc giảm ≥ 15%), bảng hiển thị Cảnh báo kèm tổng số phát hiện. Khi bằng 0, chỉ hiển thị Top biên thấp để tham khảo."),
            ("Ma trận nguồn độc lập (ONYX EU)", "Nguồn mô phỏng châu Âu (EUR) có giá vốn, `margin_amount` và cờ khuyến mãi; không bị trộn với dữ liệu không có giá gốc."),
        ],
    )


render_page(get_current_filters())
