"""Page 4: Product Portfolio, Mix Shift, Manufacturers & ATC Observations (Sản Phẩm & ATC)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import (
    build_product_insights,
    compute_variance_and_contributions,
    evaluate_uom_compatibility,
    resolve_comparison_periods,
)
from components.filters import get_current_filters, get_track_bounds, set_global_uoms
from config import TRACK_META, atc_label, country_label, fmt_compact, safe_round, track_label
import db
from queries import (
    FilterState,
    sql_atc_category_ranking,
    sql_atc_month_heatmap,
    sql_atc_monthly_trend,
    sql_atc_summary_meta,
    sql_brand_product_treemap,
    sql_dimension_variance,
    sql_irpd_top_manufacturers,
    sql_monthly_sales_trend,
    sql_product_detail_table,
    sql_unit_price_distribution,
    sql_uom_breakdown,
)
from ui import (
    get_active_palette,
    plotly_config,
    polish_diverging_bar,
    polish_horizontal_bar,
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

    render_page_header(
        "Sản Phẩm, Cơ Cấu Bán & Nhóm Thuốc ATC",
        "Nhận diện sản phẩm tăng/giảm mạnh, dịch chuyển cơ cấu danh mục, nhà sản xuất IRPD (OBSERVED) và chuỗi quan sát 8 nhóm thuốc ATC.",
        dataset_track=filters.dataset_track,
        extra_pills=[
            ("Phân rã biến động & Mix Shift", "default"),
            ("NSX: IRPD (OBSERVED)", "observed"),
            ("ATC: Quan sát 2014–2019", "observed"),
        ],
    )

    uom_guard = evaluate_uom_compatibility(filters.dataset_track, filters.clean_uoms, uoms_avail)
    use_rev = bool(has_rev and uom_guard.is_multi_uom_blocked)
    metric_label = f"Doanh thu ({ccy})" if use_rev else f"Sản lượng ({uom_guard.single_uom or 'ĐVT'})"
    metric_unit = ccy if use_rev else uom_guard.single_uom

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

    # Product variance + Mix shift across comparison periods
    prod_var_df = pd.DataFrame()
    c_col = "cur_rev" if use_rev else "cur_qty"
    p_col = "prev_rev" if use_rev else "prev_qty"
    if cmp_window.valid and cmp_window.cur_start and cmp_window.prev_start:
        pv_sql, pv_params = sql_dimension_variance(
            schema,
            filters,
            dim_kind="product",
            cur_start=cmp_window.cur_start,
            cur_end=cmp_window.cur_end,
            prev_start=cmp_window.prev_start,
            prev_end=cmp_window.prev_end,
            limit=500,
        )
        pv_raw = db.run_query_df(pv_sql, pv_params)
        if not pv_raw.empty:
            prod_var_df = compute_variance_and_contributions(pv_raw, cur_col=c_col, prev_col=p_col)
            prod_var_df["label"] = prod_var_df.apply(
                lambda r: f"{r['product_name']} ({r['clean_uom']})" if r.get("clean_uom") else str(r["product_name"]),
                axis=1,
            )

    render_insight_box(
        "Nhận xét biến động & dịch chuyển cơ cấu sản phẩm",
        build_product_insights(
            var_df=prod_var_df,
            window=cmp_window,
            metric_label=metric_label,
            metric_unit=metric_unit,
            uom_guard=uom_guard,
            provenance_class=prov_class,
        ),
        note=cmp_window.note or None,
    )

    # Row 1: Full-width Tabbed Product Variance & Mix Shift (prevents label squeezing beside long product names)
    with st.container(border=True):
        render_chart_header(
            f"Biến Động & Dịch Chuyển Cơ Cấu Sản Phẩm ({cmp_window.cur_label} vs {cmp_window.prev_label})",
            f"Phân tích tại đúng grain Sản phẩm × ĐVT theo {metric_label} — xem top tăng/giảm tuyệt đối và dịch chuyển tỷ trọng (điểm %)",
        )
        t_prod_mov, t_prod_mix = st.tabs(["Sản phẩm tăng / giảm mạnh nhất", "Dịch chuyển cơ cấu (Mix Shift — điểm %)"])

        with t_prod_mov:
            if not cmp_window.valid or prod_var_df.empty:
                render_empty_state(cmp_window.note or "Chưa có dữ liệu so sánh sản phẩm trong khoảng lọc.")
            else:
                gain = prod_var_df[prod_var_df["delta"] > 0].sort_values("delta", ascending=False).head(8)
                drop = prod_var_df[prod_var_df["delta"] < 0].sort_values("delta", ascending=True).head(8)
                comb = pd.concat([gain, drop], ignore_index=True).drop_duplicates(subset=["label"])
                if comb.empty:
                    render_empty_state("Không có biến động chênh lệch giữa 2 kỳ so sánh.")
                else:
                    comb = comb.sort_values("delta", ascending=True)
                    colors = [palette.primary if d >= 0 else "#dc2626" for d in comb["delta"]]
                    fig_pm = go.Figure(
                        go.Bar(
                            x=comb["delta"],
                            y=comb["label"],
                            orientation="h",
                            marker_color=colors,
                            text=[f"{d:+,.0f}" for d in comb["delta"]],
                            customdata=list(
                                zip(
                                    comb[p_col],
                                    comb[c_col],
                                    comb["contrib_pp"].fillna(0.0),
                                    comb["presence_status"],
                                )
                            ),
                            hovertemplate=(
                                "<b>%{y}</b><br>"
                                "Trạng thái: %{customdata[3]}<br>"
                                "Kỳ trước: %{customdata[0]:,.0f}<br>"
                                "Kỳ này: %{customdata[1]:,.0f}<br>"
                                "Chênh lệch: %{x:+,.0f}<br>"
                                "Đóng góp số học: %{customdata[2]:+.2f} điểm %<extra></extra>"
                            ),
                        )
                    )
                    style_plotly(
                        fig_pm,
                        palette,
                        height=400,
                        show_legend=False,
                        xaxis_title=f"Chênh lệch {metric_label}",
                        yaxis_title="",
                    )
                    polish_diverging_bar(fig_pm, float(comb["delta"].abs().max()), pad_factor=1.35)
                    st.plotly_chart(fig_pm, width="stretch", theme=None, config=plotly_config())

        with t_prod_mix:
            mix_valid = prod_var_df.dropna(subset=["mix_shift_pp"]).copy() if not prod_var_df.empty else pd.DataFrame()
            if not cmp_window.valid or mix_valid.empty:
                render_empty_state(cmp_window.note or "Chưa đủ dữ liệu để tính dịch chuyển cơ cấu.")
            else:
                up_m = mix_valid[mix_valid["mix_shift_pp"] > 0].sort_values("mix_shift_pp", ascending=False).head(8)
                dn_m = mix_valid[mix_valid["mix_shift_pp"] < 0].sort_values("mix_shift_pp", ascending=True).head(8)
                mix_comb = pd.concat([up_m, dn_m], ignore_index=True).drop_duplicates(subset=["label"])
                if mix_comb.empty:
                    render_empty_state("Tỷ trọng sản phẩm hầu như không đổi giữa 2 kỳ.")
                else:
                    mix_comb = mix_comb.sort_values("mix_shift_pp", ascending=True)
                    colors_m = [palette.accent if v >= 0 else "#ea580c" for v in mix_comb["mix_shift_pp"]]
                    fig_mx = go.Figure(
                        go.Bar(
                            x=mix_comb["mix_shift_pp"],
                            y=mix_comb["label"],
                            orientation="h",
                            marker_color=colors_m,
                            text=[f"{v:+.2f} đ%" for v in mix_comb["mix_shift_pp"]],
                            customdata=list(
                                zip(
                                    (mix_comb["share_prev"].fillna(0.0) * 100.0),
                                    (mix_comb["share_cur"].fillna(0.0) * 100.0),
                                )
                            ),
                            hovertemplate=(
                                "<b>%{y}</b><br>"
                                "Tỷ trọng kỳ trước: %{customdata[0]:.2f}%<br>"
                                "Tỷ trọng kỳ này: %{customdata[1]:.2f}%<br>"
                                "Dịch chuyển: %{x:+.2f} điểm %<extra></extra>"
                            ),
                        )
                    )
                    style_plotly(
                        fig_mx,
                        palette,
                        height=400,
                        show_legend=False,
                        xaxis_title="Thay đổi tỷ trọng (điểm %)",
                        yaxis_title="",
                    )
                    polish_diverging_bar(fig_mx, float(mix_comb["mix_shift_pp"].abs().max()), min_bound=0.5, pad_factor=1.35)
                    st.plotly_chart(fig_mx, width="stretch", theme=None, config=plotly_config())

    # Row 2: Brand-Product Treemap (6) + Unit Price Histogram (6, multi-UOM guarded)
    col_tree, col_hist = st.columns([6, 6], gap="medium")

    with col_tree:
        with st.container(border=True):
            tree_col = "line_amount" if use_rev else "sold_qty"
            tree_lbl = f"Doanh thu ({ccy})" if use_rev else f"Sản lượng ({uom_guard.single_uom or 'ĐVT'})"
            render_chart_header(
                f"Cơ Cấu Thương Hiệu × Sản Phẩm (Top 80 · Theo {tree_lbl})",
                "Tách đúng đến ĐVT để không gộp nhầm quy cách đóng gói",
            )
            tr_sql, tr_params = sql_brand_product_treemap(schema, filters, limit=80, use_revenue=use_rev)
            tr_df = db.run_query_df(tr_sql, tr_params)
            if tr_df.empty:
                render_empty_state("Nguồn dữ liệu hoặc bộ lọc hiện tại không có cặp Thương hiệu × Sản phẩm.")
            else:
                tr_df = tr_df.copy()
                tr_df["prod_uom"] = tr_df.apply(
                    lambda r: f"{r['product_name']} ({r['clean_uom']})" if r.get("clean_uom") else str(r["product_name"]),
                    axis=1,
                )
                fig_tr = px.treemap(
                    tr_df,
                    path=[px.Constant("Tất cả thương hiệu"), "brand_name", "prod_uom"],
                    values=tree_col,
                    color=tree_col,
                    labels={tree_col: tree_lbl},
                    color_continuous_scale=list(palette.continuous_scale),
                )
                fig_tr.update_traces(hovertemplate=f"<b>%{{label}}</b><br>{tree_lbl}: %{{value:,.0f}}<extra></extra>")
                fig_tr.update_coloraxes(colorbar_title_text=tree_lbl)
                style_plotly(fig_tr, palette, height=370, show_legend=False)
                fig_tr.update_layout(margin=dict(l=6, r=6, t=12, b=6))
                st.plotly_chart(fig_tr, width="stretch", theme=None, config=plotly_config())

    with col_hist:
        with st.container(border=True):
            render_chart_header(
                "Phân Bố Đơn Giá Cấp Dòng Mart (SP × CH × Ngày)",
                "Mỗi đơn vị đếm là 1 dòng tổng hợp sản phẩm × cửa hàng × ngày (không trộn nhiều ĐVT)",
            )
            if not has_rev:
                render_empty_state("Nguồn dữ liệu hiện tại không ghi nhận doanh thu và đơn giá tiền tệ.")
            elif uom_guard.is_multi_uom_blocked:
                st.warning(
                    f"Đang gộp **{uom_guard.uom_count} đơn vị tính** khác nhau — histogram đơn giá ({ccy}/ĐVT) bị khóa để tránh lẫn giá theo viên, vỉ và hộp.",
                    icon="⚠️",
                )
                uom_sql, uom_params = sql_uom_breakdown(schema, filters)
                uom_df = db.run_query_df(uom_sql, uom_params)
                top_uoms = uom_df["clean_uom"].dropna().head(4).tolist() if not uom_df.empty else []
                if top_uoms:
                    ucols = st.columns(len(top_uoms))
                    for idx, u in enumerate(top_uoms):
                        with ucols[idx]:
                            st.button(
                                f"Chọn ĐVT: {u}",
                                key=f"p4_pick_uom_{idx}",
                                width="stretch",
                                on_click=set_global_uoms,
                                args=([str(u)],),
                            )
            else:
                hs_sql, hs_params = sql_unit_price_distribution(schema, filters, bins=24)
                hs_df = db.run_query_df(hs_sql, hs_params)
                if hs_df.empty:
                    render_empty_state("Không có dữ liệu đơn giá hợp lệ trong phạm vi lọc.")
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
                        hovertemplate="Khoảng đơn giá: %{x}<br>Số dòng mart (SP×CH×ngày): %{y:,.0f}<extra></extra>"
                    )
                    style_plotly(
                        fig_hs,
                        palette,
                        height=370,
                        xaxis_title=f"Khoảng đơn giá ({ccy}/{uom_guard.single_uom or 'ĐVT'})",
                        yaxis_title="Số dòng mart",
                    )
                    polish_vertical_bar_headroom(fig_hs, float(hs_df.groupby("bin_label")["obs_count"].sum().max()))
                    fig_hs.update_xaxes(tickangle=-35)
                    fig_hs.update_layout(legend_title_text="Nhóm dữ liệu")
                    st.plotly_chart(fig_hs, width="stretch", theme=None, config=plotly_config())

    # Row 3: Independent Observed Sources — IRPD Manufacturers + Serbia WHO ATC (Full Clarity Scope Strips)
    is_irpd_selected = filters.dataset_track == "IRPD_ID_OBSERVED"
    with st.container(border=True):
        render_chart_header(
            "Top 15 Nhà Sản Xuất Theo Doanh Thu (IRPD Indonesia — OBSERVED)",
            "Nguồn ONYX EU hiện để trống manufacturer_name; doanh thu IDR cộng hợp lệ xuyên ĐVT (đếm Số dòng POS & CH-ngày)",
        )
        if is_irpd_selected:
            render_scope_strip(
                "Nguồn: IRPD Indonesia — Thực tế (OBSERVED · IDR) · Đang áp dụng bộ lọc ngày/ĐVT/nhiệt độ của Sidebar."
            )
        else:
            render_scope_strip(
                "Nguồn độc lập: IRPD Indonesia (OBSERVED · IDR) · Không áp dụng bộ lọc ngày/ĐVT của nguồn khác đang chọn ở Sidebar.",
                kind="warn",
            )
        mf_sql, mf_params = sql_irpd_top_manufacturers(schema, filters, limit=15)
        mf_df = db.run_query_df(mf_sql, mf_params)
        if mf_df.empty:
            render_empty_state("Không có dữ liệu nhà sản xuất trong phạm vi đang chọn.")
        else:
            mfg_order = mf_df["manufacturer_name"].tolist()
            fig_mf = px.bar(
                mf_df,
                x="line_amount",
                y="manufacturer_name",
                orientation="h",
                text_auto=".3s",
                hover_data={"line_count": ":,", "active_store_days": ":,"},
                color_discrete_sequence=[palette.primary],
            )
            fig_mf.update_traces(
                textposition="outside",
                hovertemplate=(
                    "Nhà sản xuất: %{y}<br>"
                    "Doanh thu: %{x:,.0f} IDR<br>"
                    "Số dòng POS: %{customdata[0]} · CH-ngày: %{customdata[1]}<extra></extra>"
                ),
            )
            style_plotly(
                fig_mf,
                palette,
                height=390,
                show_legend=False,
                xaxis_title="Doanh thu (IDR)",
                yaxis_title="Nhà sản xuất",
            )
            polish_horizontal_bar(fig_mf, mfg_order, float(mf_df["line_amount"].max()))
            st.plotly_chart(fig_mf, width="stretch", theme=None, config=plotly_config())

    # Full-width ATC Category Observation Card (with metadata strip and tabbed views)
    with st.container(border=True):
        render_chart_header(
            "Chuỗi Quan Sát 8 Nhóm Thuốc Điều Trị ATC (Dữ Liệu Quan Sát Độc Lập)",
            "Sử dụng đúng thuật ngữ sản lượng quan sát ở cấp nhóm ATC (không suy ngược thành giao dịch từng SKU hay nhu cầu ẩn)",
        )
        atc_meta_sql, atc_meta_params = sql_atc_summary_meta(schema)
        atc_meta_df = db.run_query_df(atc_meta_sql, atc_meta_params)
        atc_span = "2014–2019"
        atc_ctry = "Serbia (RS)"
        atc_src = "PHARMA_SALES_DAILY_ATC"
        if not atc_meta_df.empty:
            mr = atc_meta_df.iloc[0]
            if pd.notna(mr.get("min_ym")) and pd.notna(mr.get("max_ym")):
                min_ym_d = pd.to_datetime(mr["min_ym"]).date()
                max_ym_d = pd.to_datetime(mr["max_ym"]).date()
                atc_span = f"{min_ym_d:%m/%Y}–{max_ym_d:%m/%Y}"
            if mr.get("countries"):
                atc_ctry = country_label(str(mr["countries"]))
            if mr.get("source"):
                atc_src = str(mr["source"])

        apply_date_to_atc = st.toggle(
            f"Áp dụng khoảng ngày Sidebar cho chuỗi ATC (tắt = hiển thị toàn kỳ {atc_span})",
            value=False,
            key="p4_atc_apply_date",
        )
        atc_filters = filters if apply_date_to_atc else FilterState()
        atc_filter_txt = (
            f"Đang lọc theo ngày Sidebar ({filters.date_start:%d/%m/%Y}–{filters.date_end:%d/%m/%Y}); không áp dụng Quốc gia/Cửa hàng/ĐVT của nguồn chính"
            if apply_date_to_atc and filters.date_start and filters.date_end
            else f"Hiển thị toàn kỳ quan sát {atc_span}; không áp dụng bộ lọc nguồn chính ở Sidebar"
        )
        render_scope_strip(
            f"Nguồn: {atc_src} · Loại: Thực tế (OBSERVED) · Khu vực: {atc_ctry} · Grain: Nhóm ATC × Kỳ · {atc_filter_txt}.",
            kind="default" if apply_date_to_atc else "warn",
        )

        al_sql, al_params = sql_atc_monthly_trend(schema, atc_filters)
        al_df = db.run_query_df(al_sql, al_params)
        ah_sql, ah_params = sql_atc_month_heatmap(schema, atc_filters)
        ah_df = db.run_query_df(ah_sql, ah_params)
        ar_sql, ar_params = sql_atc_category_ranking(schema, atc_filters)
        ar_df = db.run_query_df(ar_sql, ar_params)

        t_atc1, t_atc2, t_atc3 = st.tabs(["Xu hướng theo tháng", "Heatmap Nhóm ATC × Tháng", "Xếp hạng 8 nhóm ATC"])
        with t_atc1:
            if al_df.empty:
                render_empty_state("Không có dữ liệu ATC trong khoảng ngày đang chọn.")
            else:
                al_df = al_df.copy()
                al_df["atc_vi"] = al_df.apply(lambda r: atc_label(r["category_code"], r["category_name"]), axis=1)
                fig_al = px.line(
                    al_df,
                    x="year_month",
                    y="total_observed_qty",
                    color="atc_vi",
                    color_discrete_sequence=list(palette.discrete),
                )
                fig_al.update_traces(
                    line=dict(width=2.1),
                    hovertemplate="Tháng %{x|%m/%Y}<br>Nhóm: %{fullData.name}<br>Sản lượng quan sát: %{y:,.1f}<extra></extra>",
                )
                style_plotly(fig_al, palette, height=350, xaxis_title="Tháng", yaxis_title="Sản lượng quan sát")
                fig_al.update_layout(
                    legend_title_text="Nhóm thuốc ATC",
                    legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.02, font=dict(size=11)),
                    margin=dict(l=14, r=190, t=18, b=16),
                )
                st.plotly_chart(fig_al, width="stretch", theme=None, config=plotly_config())

        with t_atc2:
            if ah_df.empty:
                render_empty_state("Không có dữ liệu ATC trong khoảng ngày đang chọn.")
            else:
                ah_df = ah_df.copy()
                ah_df["atc_short"] = ah_df["category_code"]
                piv = ah_df.pivot(index="month_num", columns="atc_short", values="total_observed_qty")
                piv = piv.reindex(index=sorted(piv.index), columns=sorted(piv.columns))
                y_labels = [f"Tháng {int(m)}" for m in piv.index]
                x_labels = [atc_label(str(c)) for c in piv.columns]
                text_vals = [[f"{v:,.0f}" if pd.notna(v) else "" for v in row] for row in piv.values]
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
                        hovertemplate="Nhóm ATC: %{x}<br>%{y}<br>Sản lượng quan sát: %{z:,.1f}<extra></extra>",
                    )
                )
                style_plotly(
                    fig_ah,
                    palette,
                    height=370,
                    show_legend=False,
                    xaxis_title="Nhóm thuốc ATC",
                    yaxis_title="Tháng",
                )
                fig_ah.update_xaxes(tickangle=-15)
                fig_ah.update_yaxes(autorange="reversed")
                st.plotly_chart(fig_ah, width="stretch", theme=None, config=plotly_config())

        with t_atc3:
            if ar_df.empty:
                render_empty_state("Không có dữ liệu ATC trong khoảng ngày đang chọn.")
            else:
                ar_df = ar_df.copy()
                ar_df["atc_vi"] = ar_df.apply(lambda r: atc_label(r["category_code"], r["category_name"]), axis=1)
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
                    hovertemplate="Nhóm: %{y}<br>Tổng SL quan sát: %{x:,.1f}<br>SL quan sát TB/ngày: %{customdata[0]} · Số kỳ QS: %{customdata[1]}<extra></extra>",
                )
                style_plotly(
                    fig_ar,
                    palette,
                    height=350,
                    show_legend=False,
                    xaxis_title="Tổng sản lượng quan sát",
                    yaxis_title="Nhóm thuốc ATC",
                )
                polish_horizontal_bar(fig_ar, atc_order, float(ar_df["total_observed_qty"].max()))
                st.plotly_chart(fig_ar, width="stretch", theme=None, config=plotly_config())

    # Row 4 (Bottom): Searchable Detailed Product Lookup Table
    with st.container(border=True):
        render_chart_header(
            "Bảng Tra Cứu Chi Tiết Sản Phẩm (Sản Phẩm × ĐVT × Nguồn)",
            "Đặt bên dưới các phân tích chính; dùng Đơn giá & Biên LN gia quyền thay cho trung bình cộng dòng mart",
        )
        prod_search = st.text_input(
            "Tìm nhanh theo tên sản phẩm, thương hiệu hoặc đơn vị tính",
            placeholder="Ví dụ: AntiBioX, Paracetamol, tab...",
            key="p4_product_search",
        )
        pt_sql, pt_params = sql_product_detail_table(schema, filters, search_text=prod_search, limit=500)
        pt_df = db.run_query_df(pt_sql, pt_params)
        if pt_df.empty:
            render_empty_state()
        else:
            rev_col = f"Doanh thu ({ccy})" if ccy else "Doanh thu"
            price_col = f"Đơn giá gia quyền ({ccy})" if ccy else "Đơn giá gia quyền"
            disp_df = pd.DataFrame(
                {
                    "Tên sản phẩm": pt_df["product_name"],
                    "Đơn vị tính": pt_df["clean_uom"],
                    "Nhóm dữ liệu": pt_df["dataset_track"].map(track_label),
                    "Số dòng POS": pt_df["line_count"],
                    "CH-ngày": pt_df["active_store_days"],
                    "Sản lượng (theo ĐVT)": safe_round(pt_df["sold_qty"], 0),
                    rev_col: safe_round(pt_df["line_amount"], 2),
                    price_col: safe_round(pt_df["weighted_unit_price"], 2),
                    "Biên LN gia quyền (%)": safe_round(pt_df["weighted_margin_pct"], 2),
                }
            )
            st.dataframe(
                disp_df,
                width="stretch",
                hide_index=True,
                height=340,
                column_config={
                    "Số dòng POS": st.column_config.NumberColumn(format="%,d"),
                    "CH-ngày": st.column_config.NumberColumn(format="%,d"),
                    "Sản lượng (theo ĐVT)": st.column_config.NumberColumn(format="%,.0f"),
                    rev_col: st.column_config.NumberColumn(format="%,.2f"),
                    price_col: st.column_config.NumberColumn(format="%,.2f"),
                    "Biên LN gia quyền (%)": st.column_config.NumberColumn(format="%.2f%%"),
                },
            )
            render_csv_download(disp_df, "chi_tiet_san_pham.csv", key="p4_csv_products")


render_page(get_current_filters())
