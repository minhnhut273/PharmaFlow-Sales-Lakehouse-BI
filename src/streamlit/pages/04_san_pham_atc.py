"""Page 4: Period Comparison Hub, Mix Shift, Manufacturers & ATC Observations (So Sánh Kỳ & Danh Mục)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import (
    COMPARE_MODE_LABELS,
    COMPARE_MODE_ORDER,
    ComparisonWindow,
    build_product_insights,
    compute_variance_and_contributions,
    evaluate_uom_compatibility,
    resolve_comparison_periods,
)
from components.filters import get_current_filters, get_track_bounds, set_global_uoms
from config import (
    TRACK_META,
    atc_label,
    country_label,
    currency_display_unit,
    currency_multiplier,
    fmt_compact,
    fmt_currency,
    safe_round,
    track_label,
    vnd_rate_note,
)
import db
from queries import (
    FilterState,
    sql_atc_category_ranking,
    sql_atc_month_heatmap,
    sql_atc_monthly_trend,
    sql_atc_summary_meta,
    sql_brand_product_treemap,
    sql_dimension_variance,
    sql_exec_kpis,
    sql_irpd_top_manufacturers,
    sql_monthly_sales_trend,
    sql_product_detail_table,
    sql_unit_price_distribution,
    sql_uom_breakdown,
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
    render_kpi_card,
    render_page_header,
    render_right_explanation_panel,
    render_scope_strip,
    render_top_action_bar,
    style_plotly,
)


def _clamp_date(d: date, min_d: date | None, max_d: date | None) -> date:
    if min_d is not None and d < min_d:
        return min_d
    if max_d is not None and d > max_d:
        return max_d
    return d


def _parse_date_range(val: object, fallback: tuple[date, date]) -> tuple[date, date]:
    if isinstance(val, (tuple, list)):
        if len(val) >= 2 and isinstance(val[0], date) and isinstance(val[1], date):
            return min(val[0], val[1]), max(val[0], val[1])
        if len(val) == 1 and isinstance(val[0], date):
            return val[0], val[0]
    if isinstance(val, date):
        return val, val
    return fallback


def _pct_delta(cur: object, prev: object) -> tuple[str | None, str]:
    c_val = float(cur) if cur is not None and pd.notna(cur) else None
    p_val = float(prev) if prev is not None and pd.notna(prev) else None
    if c_val is None or p_val is None or p_val == 0:
        return None, "neutral"
    pct = (c_val - p_val) / abs(p_val) * 100.0
    tone = "pos" if pct > 0 else ("neg" if pct < 0 else "neutral")
    return f"{pct:+.2f}%", tone


def render_page(filters: FilterState) -> None:
    schema = db.get_active_schema()
    palette = get_active_palette()
    meta = TRACK_META.get(filters.dataset_track or "")
    ccy = meta.currency_code if meta else None
    has_rev = bool(meta.has_revenue) if meta else False
    prov_class = meta.provenance_class if meta else "SYNTHETIC"
    to_vnd = bool(filters.display_vnd)
    mult = currency_multiplier(ccy, to_vnd)
    disp_ccy = currency_display_unit(ccy, to_vnd)

    bounds = get_track_bounds()
    track_min_date = bounds.get("min_date")
    track_max_date = bounds.get("max_date")
    uoms_avail = bounds.get("uoms_avail") or ()

    render_page_header(
        "So Sánh Kỳ & Danh Mục",
        "Đặt cạnh nhau 2 khung thời gian (MoM, YoY hoặc Kỳ A vs Kỳ B tự chọn), truy vết biến động toàn danh mục, nhà sản xuất IRPD và nhóm ATC.",
        dataset_track=filters.dataset_track,
        extra_pills=[
            ("So sánh 2 kỳ linh hoạt", "default"),
            ("NSX: IRPD (Thực tế)", "observed"),
            ("ATC: 2014–2019 (Thực tế)", "observed"),
        ],
    )

    uom_guard = evaluate_uom_compatibility(filters.dataset_track, filters.clean_uoms, uoms_avail)
    use_rev = bool(has_rev and uom_guard.is_multi_uom_blocked)
    metric_label = f"Doanh thu ({disp_ccy})" if use_rev else f"Sản lượng ({uom_guard.single_uom or 'ĐVT'})"
    metric_unit = disp_ccy if use_rev else uom_guard.single_uom

    m_sql, m_params = sql_monthly_sales_trend(schema, filters)
    m_df = db.run_query_df(m_sql, m_params)
    avail_months = m_df["year_month"].tolist() if not m_df.empty else []

    # Interactive Period Comparison Selector (supports MoM / Half-split / YoY / Custom Period A vs Period B)
    mode_options = list(COMPARE_MODE_ORDER) + ["custom"]
    mode_short_labels = {
        "latest_full_month": "MoM (2 tháng)",
        "half_split": "Nửa kỳ",
        "yoy_latest": "YoY (12 tháng)",
        "custom": "Tùy chọn Kỳ A / B",
    }
    mode_labels = {**COMPARE_MODE_LABELS, "custom": "Tùy chọn Kỳ A / B"}
    default_mode = filters.compare_mode if filters.compare_mode in COMPARE_MODE_ORDER else "latest_full_month"
    if st.session_state.get("p4_compare_mode") not in mode_options:
        st.session_state["p4_compare_mode"] = default_mode

    with st.container(border=True):
        sel_mode = st.radio(
            "Chế độ so sánh",
            options=mode_options,
            format_func=lambda m: mode_short_labels.get(m, m),
            horizontal=True,
            key="p4_compare_mode",
        )
        if sel_mode == "custom":
            anchor_end = filters.date_end or track_max_date or date(2025, 12, 31)
            anchor_start = filters.date_start or track_min_date or (anchor_end - timedelta(days=59))
            def_a_end = _clamp_date(anchor_end, track_min_date, track_max_date)
            def_a_start = _clamp_date(max(anchor_start, def_a_end - timedelta(days=29)), track_min_date, track_max_date)
            def_b_end = _clamp_date(max(anchor_start, def_a_start - timedelta(days=1)), track_min_date, track_max_date)
            def_b_start = _clamp_date(max(anchor_start, def_b_end - timedelta(days=29)), track_min_date, track_max_date)

            st.session_state.setdefault("p4_custom_a", (def_a_start, def_a_end))
            st.session_state.setdefault("p4_custom_b", (def_b_start, def_b_end))

            dc1, dc2 = st.columns(2)
            with dc1:
                raw_a = st.date_input(
                    "Kỳ hiện tại (Kỳ A)",
                    min_value=track_min_date,
                    max_value=track_max_date,
                    key="p4_custom_a",
                )
            with dc2:
                raw_b = st.date_input(
                    "Kỳ đối chiếu (Kỳ B)",
                    min_value=track_min_date,
                    max_value=track_max_date,
                    key="p4_custom_b",
                )

            a_start, a_end = _parse_date_range(raw_a, (def_a_start, def_a_end))
            b_start, b_end = _parse_date_range(raw_b, (def_b_start, def_b_end))
            overlap = not (a_end < b_start or b_end < a_start)
            cmp_window = ComparisonWindow(
                valid=True,
                mode="custom",
                mode_label=mode_labels["custom"],
                cur_start=a_start,
                cur_end=a_end,
                prev_start=b_start,
                prev_end=b_end,
                cur_label=f"{a_start:%d/%m/%Y}–{a_end:%d/%m/%Y}",
                prev_label=f"{b_start:%d/%m/%Y}–{b_end:%d/%m/%Y}",
                note="Lưu ý: Hai khoảng ngày đang chọn có phần chồng lấn." if overlap else "",
            )
        else:
            cmp_window = resolve_comparison_periods(
                filters.date_start,
                filters.date_end,
                mode=sel_mode,
                available_months=avail_months,
                track_min_date=track_min_date,
                track_max_date=track_max_date,
            )

    render_top_action_bar(
        filters,
        page_key="p4",
        compare_window=cmp_window,
        local_tags=[f"Chế độ: {cmp_window.mode_label}"],
        show_compare_jump=False,
    )

    main_col, drawer_col = open_page_layout_columns()

    with main_col:
        # 4 Direct Period-A vs Period-B Comparison KPI Cards
        cur_k: dict[str, object] = {}
        prev_k: dict[str, object] = {}
        if cmp_window.valid and cmp_window.cur_start and cmp_window.cur_end and cmp_window.prev_start and cmp_window.prev_end:
            ck_sql, ck_params = sql_exec_kpis(schema, filters, date_override=(cmp_window.cur_start, cmp_window.cur_end))
            pk_sql, pk_params = sql_exec_kpis(schema, filters, date_override=(cmp_window.prev_start, cmp_window.prev_end))
            ck_df = db.run_query_df(ck_sql, ck_params)
            pk_df = db.run_query_df(pk_sql, pk_params)
            if not ck_df.empty:
                cur_k = ck_df.iloc[0].to_dict()
            if not pk_df.empty:
                prev_k = pk_df.iloc[0].to_dict()

        cur_rev = cur_k.get("total_revenue")
        prev_rev = prev_k.get("total_revenue")
        cur_qty = cur_k.get("total_sold_qty")
        prev_qty = prev_k.get("total_sold_qty")
        cur_margin = cur_k.get("total_margin")
        prev_margin = prev_k.get("total_margin")
        cur_mpct = cur_k.get("weighted_margin_pct")
        prev_mpct = prev_k.get("weighted_margin_pct")
        has_margin_data = int(cur_k.get("margin_rows") or 0) > 0

        rev_delta_txt, rev_tone = _pct_delta(cur_rev, prev_rev)
        qty_delta_txt, qty_tone = _pct_delta(cur_qty, prev_qty)
        mar_delta_txt, mar_tone = _pct_delta(cur_margin, prev_margin)

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            render_kpi_card(
                "Doanh Thu Kỳ A",
                fmt_currency(cur_rev, ccy, to_vnd=to_vnd) if has_rev else "—",
                f"Kỳ B: {fmt_currency(prev_rev, ccy, to_vnd=to_vnd)}" if has_rev else "Nguồn không có tiền tệ",
                tag=disp_ccy or "Không có",
                accent=palette.primary,
                delta_text=f"{rev_delta_txt} so với Kỳ B" if rev_delta_txt else "Chưa đủ kỳ đối chiếu",
                delta_tone=rev_tone,
                period_label=cmp_window.cur_label if cmp_window.valid else None,
                compare_label=cmp_window.prev_label if cmp_window.valid else None,
                info_tooltip=f"So sánh tổng doanh thu Kỳ A và Kỳ B. {vnd_rate_note(ccy, to_vnd)}",
            )
        with k2:
            if uom_guard.is_multi_uom_blocked:
                q_val = "Cần chọn 1 ĐVT"
                q_sub = f"Đang gồm {uom_guard.uom_count} ĐVT"
                q_delta = "Chọn 1 ĐVT ở thanh bên để so SL"
                q_tone = "neutral"
            else:
                q_val = f"{fmt_compact(cur_qty)} {uom_guard.single_uom or ''}".strip()
                q_sub = f"Kỳ B: {fmt_compact(prev_qty)} {uom_guard.single_uom or ''}".strip()
                q_delta = f"{qty_delta_txt} so với Kỳ B" if qty_delta_txt else "Chưa đủ kỳ đối chiếu"
                q_tone = qty_tone
            render_kpi_card(
                "Sản Lượng Kỳ A",
                q_val,
                q_sub,
                tag=uom_guard.single_uom or "Nhiều ĐVT",
                accent=palette.accent,
                delta_text=q_delta,
                delta_tone=q_tone,
                period_label=cmp_window.cur_label if cmp_window.valid else None,
                info_tooltip="Chỉ cộng và so sánh sản lượng khi chọn 1 đơn vị tính (ĐVT) duy nhất.",
            )
        with k3:
            render_kpi_card(
                "Lợi Nhuận Kỳ A",
                fmt_currency(cur_margin, ccy, to_vnd=to_vnd) if (has_rev and has_margin_data) else "—",
                f"Kỳ B: {fmt_currency(prev_margin, ccy, to_vnd=to_vnd)}" if (has_rev and has_margin_data) else "Không có dữ liệu giá gốc",
                tag="Lợi nhuận",
                accent=palette.discrete[2],
                delta_text=f"{mar_delta_txt} so với Kỳ B" if (has_margin_data and mar_delta_txt) else "Nguồn không ghi giá vốn",
                delta_tone=mar_tone if has_margin_data else "neutral",
                info_tooltip="Tổng lợi nhuận gộp từ các nguồn có ghi giá gốc/margin (`margin_amount`). Nguồn không có giá gốc hiển thị —.",
            )
        with k4:
            if has_margin_data and cur_mpct is not None and pd.notna(cur_mpct):
                mpct_val = f"{float(cur_mpct) * 100.0:.2f}%"
                if prev_mpct is not None and pd.notna(prev_mpct):
                    diff_pp = (float(cur_mpct) - float(prev_mpct)) * 100.0
                    mpct_delta = f"{diff_pp:+.2f} đ% vs Kỳ B ({float(prev_mpct) * 100.0:.2f}%)"
                    mpct_tone = "pos" if diff_pp > 0 else ("neg" if diff_pp < 0 else "neutral")
                else:
                    mpct_delta = "Chưa có tỷ suất Kỳ B"
                    mpct_tone = "neutral"
                mpct_sub = "Tổng lợi nhuận / Tổng doanh thu"
            else:
                mpct_val = "—"
                mpct_sub = "Không có dữ liệu giá gốc"
                mpct_delta = "Nguồn không ghi margin"
                mpct_tone = "neutral"
            render_kpi_card(
                "Tỷ Suất LN",
                mpct_val,
                mpct_sub,
                tag="Margin %",
                accent=palette.discrete[3],
                delta_text=mpct_delta,
                delta_tone=mpct_tone,
                info_tooltip="Tỷ suất lợi nhuận gia quyền = Tổng margin_amount / Tổng doanh thu có giá vốn (không lấy trung bình cộng từng dòng).",
            )

        # Product variance + Mix shift across full filtered catalog
        prod_var_df = pd.DataFrame()
        c_col = "cur_rev" if use_rev else "cur_qty"
        p_col = "prev_rev" if use_rev else "prev_qty"
        val_scale = mult if use_rev else 1.0
        var_metric_supported = has_rev if use_rev else True
        if cmp_window.valid and cmp_window.cur_start and cmp_window.prev_start:
            pv_sql, pv_params = sql_dimension_variance(
                schema,
                filters,
                dim_kind="product",
                cur_start=cmp_window.cur_start,
                cur_end=cmp_window.cur_end,
                prev_start=cmp_window.prev_start,
                prev_end=cmp_window.prev_end,
                limit=None,
            )
            pv_raw = db.run_query_df(pv_sql, pv_params)
            if not pv_raw.empty:
                prod_var_df = compute_variance_and_contributions(
                    pv_raw,
                    cur_col=c_col,
                    prev_col=p_col,
                    metric_supported=var_metric_supported,
                )
                prod_var_df["label"] = prod_var_df.apply(
                    lambda r: f"{r['product_name']} ({r['clean_uom']})" if r.get("clean_uom") else str(r["product_name"]),
                    axis=1,
                )

        # Compact collapsed/drawer insights (keeps assertions cleanly accessible without heavy text wall)
        insight_bullets = build_product_insights(
            var_df=prod_var_df,
            window=cmp_window,
            metric_label=f"Doanh thu ({ccy})" if use_rev else f"Sản lượng ({uom_guard.single_uom or 'ĐVT'})",
            metric_unit=ccy if use_rev else uom_guard.single_uom,
            uom_guard=uom_guard,
            provenance_class=prov_class,
        )
        render_insight_box("Nhận xét biến động & dịch chuyển cơ cấu sản phẩm", insight_bullets, note=cmp_window.note or None)

        # Row 1: Full-width Product Variance & Mix Shift (Top Gain/Drop + Mix Shift pp)
        var_scope_summary = ""
        if cmp_window.valid and not prod_var_df.empty:
            tot_prev_cat = float(pd.to_numeric(prod_var_df[p_col], errors="coerce").fillna(0.0).sum()) * val_scale
            tot_cur_cat = float(pd.to_numeric(prod_var_df[c_col], errors="coerce").fillna(0.0).sum()) * val_scale
            pct_suffix = f", {((tot_cur_cat - tot_prev_cat) / tot_prev_cat * 100.0):+.2f}%" if tot_prev_cat > 0 else ""
            prev_only_cnt = int((prod_var_df["presence_status"] == "Chỉ phát sinh kỳ trước").sum())
            new_cur_cnt = int((prod_var_df["presence_status"] == "Mới phát sinh kỳ này").sum())
            var_scope_summary = (
                f"Tính trên toàn bộ {len(prod_var_df):,} sản phẩm × ĐVT hợp lệ (tổng kỳ trước {fmt_compact(tot_prev_cat)} → kỳ này {fmt_compact(tot_cur_cat)}{pct_suffix}; "
                f"gồm {prev_only_cnt:,} nhóm chỉ phát sinh kỳ trước và {new_cur_cnt:,} nhóm mới kỳ này); biểu đồ hiển thị tối đa Top 8 tăng và Top 8 giảm."
            )

        with st.container(border=True):
            render_chart_header(
                "Biến Động & Cơ Cấu Sản Phẩm",
                f"{cmp_window.cur_label} vs {cmp_window.prev_label} · {metric_label}",
                info_tooltip=var_scope_summary or "Top 8 mặt hàng tăng mạnh nhất và giảm mạnh nhất giữa Kỳ A và Kỳ B, tính trên toàn bộ danh mục trước khi lấy Top.",
            )
            t_prod_mov, t_prod_mix = st.tabs(["Tăng / giảm mạnh nhất", "Dịch chuyển tỷ trọng (điểm %)"])

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
                        comb = comb.sort_values("delta", ascending=True).copy()
                        comb["delta_disp"] = comb["delta"] * val_scale
                        comb["prev_disp"] = pd.to_numeric(comb[p_col], errors="coerce").fillna(0.0) * val_scale
                        comb["cur_disp"] = pd.to_numeric(comb[c_col], errors="coerce").fillna(0.0) * val_scale
                        colors = [palette.primary if d >= 0 else "#dc2626" for d in comb["delta_disp"]]
                        fig_pm = go.Figure(
                            go.Bar(
                                x=comb["delta_disp"],
                                y=comb["label"],
                                orientation="h",
                                marker_color=colors,
                                text=[f"{d:+,.0f}" for d in comb["delta_disp"]],
                                customdata=list(
                                    zip(
                                        comb["prev_disp"],
                                        comb["cur_disp"],
                                        comb["contrib_pp"].fillna(0.0),
                                        comb["presence_status"],
                                    )
                                ),
                                hovertemplate=(
                                    "<b>%{y}</b><br>"
                                    "Trạng thái: %{customdata[3]}<br>"
                                    "Kỳ B (trước): %{customdata[0]:,.0f}<br>"
                                    "Kỳ A (này): %{customdata[1]:,.0f}<br>"
                                    "Chênh lệch: %{x:+,.0f}<br>"
                                    "Đóng góp số học: %{customdata[2]:+.2f} điểm %<extra></extra>"
                                ),
                            )
                        )
                        style_plotly(
                            fig_pm,
                            palette,
                            height=390,
                            show_legend=False,
                            xaxis_title=f"Chênh lệch {metric_label}",
                            yaxis_title="",
                        )
                        polish_diverging_bar(fig_pm, float(comb["delta_disp"].abs().max()), pad_factor=1.35)
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
                                    "Tỷ trọng Kỳ B: %{customdata[0]:.2f}%<br>"
                                    "Tỷ trọng Kỳ A: %{customdata[1]:.2f}%<br>"
                                    "Dịch chuyển: %{x:+.2f} điểm %<extra></extra>"
                                ),
                            )
                        )
                        style_plotly(
                            fig_mx,
                            palette,
                            height=390,
                            show_legend=False,
                            xaxis_title="Thay đổi tỷ trọng (điểm %)",
                            yaxis_title="",
                        )
                        polish_diverging_bar(fig_mx, float(mix_comb["mix_shift_pp"].abs().max()), min_bound=0.5, pad_factor=1.35)
                        st.plotly_chart(fig_mx, width="stretch", theme=None, config=plotly_config())

            if var_scope_summary:
                st.markdown(f"<div class='pf-sr-only'>{var_scope_summary}</div>", unsafe_allow_html=True)

        # Row 2: Compact Exploration Tabs
        tab_mix, tab_mfg, tab_atc, tab_tbl = st.tabs(
            [
                "Thương Hiệu & Giá",
                "Nhà Sản Xuất",
                "Nhóm Thuốc ATC",
                "Tra Cứu SP",
            ]
        )

        with tab_mix:
            col_tree, col_hist = st.columns([6, 6], gap="medium")
            with col_tree:
                with st.container(border=True):
                    tree_col = "line_amount" if use_rev else "sold_qty"
                    tree_lbl = f"Doanh thu ({disp_ccy})" if use_rev else f"Sản lượng ({uom_guard.single_uom or 'ĐVT'})"
                    render_chart_header(
                        f"Cơ Cấu Thương Hiệu × Sản Phẩm (Top 80 · {tree_lbl})",
                        "Tách đúng đến ĐVT để không gộp nhầm quy cách đóng gói",
                    )
                    tr_sql, tr_params = sql_brand_product_treemap(schema, filters, limit=80, use_revenue=use_rev)
                    tr_df = db.run_query_df(tr_sql, tr_params)
                    if tr_df.empty:
                        render_empty_state("Nguồn dữ liệu hoặc bộ lọc hiện tại không có cặp Thương hiệu × Sản phẩm.")
                    else:
                        tr_plot = tr_df.copy()
                        tr_plot["plot_val"] = pd.to_numeric(tr_plot[tree_col], errors="coerce") * val_scale
                        tr_plot["prod_uom"] = tr_plot.apply(
                            lambda r: f"{r['product_name']} ({r['clean_uom']})" if r.get("clean_uom") else str(r["product_name"]),
                            axis=1,
                        )
                        fig_tr = px.treemap(
                            tr_plot,
                            path=[px.Constant("Tất cả thương hiệu"), "brand_name", "prod_uom"],
                            values="plot_val",
                            color="plot_val",
                            labels={"plot_val": tree_lbl},
                            color_continuous_scale=list(palette.continuous_scale),
                        )
                        fig_tr.update_traces(hovertemplate=f"<b>%{{label}}</b><br>{tree_lbl}: %{{value:,.0f}}<extra></extra>")
                        fig_tr.update_coloraxes(colorbar_title_text=tree_lbl)
                        style_plotly(fig_tr, palette, height=360, show_legend=False)
                        fig_tr.update_layout(margin=dict(l=6, r=6, t=12, b=6))
                        st.plotly_chart(fig_tr, width="stretch", theme=None, config=plotly_config())

            with col_hist:
                with st.container(border=True):
                    render_chart_header(
                        "Phân Bố Đơn Giá Theo Dòng Bán",
                        "Chỉ tính khi chọn đúng 1 ĐVT đồng nhất",
                        info_tooltip="Tránh trộn đơn giá viên, vỉ, hộp vào cùng histogram.",
                    )
                    if not has_rev:
                        render_empty_state("Nguồn dữ liệu hiện tại không ghi nhận doanh thu và đơn giá tiền tệ.")
                    elif uom_guard.is_multi_uom_blocked:
                        st.warning(
                            f"Đang gộp **{uom_guard.uom_count} đơn vị tính** khác nhau — histogram đơn giá ({disp_ccy}/ĐVT) bị khóa để tránh lẫn giá theo viên, vỉ và hộp.",
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
                                lambda r: f"{float(r['bin_start']) * mult:,.0f}–{float(r['bin_end']) * mult:,.0f}"
                                if to_vnd
                                else f"{float(r['bin_start']):,.1f}–{float(r['bin_end']):,.1f}",
                                axis=1,
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
                                hovertemplate="Khoảng đơn giá: %{x}<br>Số dòng dữ liệu: %{y:,.0f}<extra></extra>"
                            )
                            style_plotly(
                                fig_hs,
                                palette,
                                height=360,
                                xaxis_title=f"Khoảng đơn giá ({disp_ccy}/{uom_guard.single_uom or 'ĐVT'})",
                                yaxis_title="Số dòng dữ liệu",
                            )
                            polish_vertical_bar_headroom(fig_hs, float(hs_df.groupby("bin_label")["obs_count"].sum().max()))
                            fig_hs.update_xaxes(tickangle=-35)
                            fig_hs.update_layout(legend_title_text="Nhóm dữ liệu")
                            st.plotly_chart(fig_hs, width="stretch", theme=None, config=plotly_config())

        with tab_mfg:
            is_irpd_selected = filters.dataset_track == "IRPD_ID_OBSERVED"
            irpd_mult = currency_multiplier("IDR", to_vnd)
            irpd_ccy = currency_display_unit("IDR", to_vnd) or "IDR"
            with st.container(border=True):
                render_chart_header(
                    f"Top 15 Nhà Sản Xuất Theo Doanh Thu (IRPD Indonesia — {irpd_ccy})",
                    "Nguồn ONYX EU chưa ghi nhận nhà sản xuất; doanh thu IDR cộng hợp lệ xuyên ĐVT",
                )
                if is_irpd_selected:
                    render_scope_strip("Nguồn: IRPD Indonesia — Thực tế · Đang áp dụng bộ lọc ngày/ĐVT/nhiệt độ của thanh bên.")
                else:
                    render_scope_strip(
                        "Nguồn độc lập: IRPD Indonesia — Thực tế · Không áp dụng bộ lọc ngày/ĐVT của nguồn khác đang chọn ở thanh bên.",
                        kind="warn",
                    )
                mf_sql, mf_params = sql_irpd_top_manufacturers(schema, filters, limit=15)
                mf_df = db.run_query_df(mf_sql, mf_params)
                if mf_df.empty:
                    render_empty_state("Không có dữ liệu nhà sản xuất trong phạm vi đang chọn.")
                else:
                    mf_plot = mf_df.copy()
                    mf_plot["rev_disp"] = pd.to_numeric(mf_plot["line_amount"], errors="coerce") * irpd_mult
                    mfg_order = mf_plot["manufacturer_name"].tolist()
                    fig_mf = px.bar(
                        mf_plot,
                        x="rev_disp",
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
                            f"Doanh thu: %{{x:,.0f}} {irpd_ccy}<br>"
                            "Số dòng POS: %{customdata[0]} · CH-ngày: %{customdata[1]}<extra></extra>"
                        ),
                    )
                    style_plotly(
                        fig_mf,
                        palette,
                        height=400,
                        show_legend=False,
                        xaxis_title=f"Doanh thu ({irpd_ccy})",
                        yaxis_title="Nhà sản xuất",
                    )
                    polish_horizontal_bar(fig_mf, mfg_order, float(mf_plot["rev_disp"].max()))
                    st.plotly_chart(fig_mf, width="stretch", theme=None, config=plotly_config())

        with tab_atc:
            with st.container(border=True):
                render_chart_header(
                    "Chuỗi Quan Sát 8 Nhóm Thuốc Điều Trị ATC (Serbia — Thực Tế)",
                    "Sản lượng quan sát ở cấp nhóm ATC (nguồn không ghi nhận doanh thu tiền tệ)",
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
                    f"Áp dụng khoảng ngày Sidebar cho chuỗi ATC (tắt = toàn kỳ {atc_span})",
                    value=False,
                    key="p4_atc_apply_date",
                )
                atc_filters = filters if apply_date_to_atc else FilterState()
                atc_filter_txt = (
                    f"Đang lọc ngày ({filters.date_start:%d/%m/%Y}–{filters.date_end:%d/%m/%Y}); bỏ qua Quốc gia/Cửa hàng/ĐVT của nguồn chính"
                    if apply_date_to_atc and filters.date_start and filters.date_end
                    else f"Hiển thị toàn kỳ quan sát {atc_span}; không áp dụng bộ lọc nguồn chính ở Sidebar"
                )
                render_scope_strip(
                    f"Nguồn độc lập: Chuỗi quan sát 8 nhóm ATC ({atc_ctry}) · Dữ liệu thực tế · {atc_filter_txt}.",
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
                            hovertemplate="Tháng %{x|%m/%Y}<br>Nhóm: %{fullData.name}<br>SL quan sát: %{y:,.1f}<extra></extra>",
                        )
                        style_plotly(fig_al, palette, height=340, xaxis_title="Tháng", yaxis_title="Sản lượng quan sát")
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
                                hovertemplate="Nhóm ATC: %{x}<br>%{y}<br>SL quan sát: %{z:,.1f}<extra></extra>",
                            )
                        )
                        style_plotly(
                            fig_ah,
                            palette,
                            height=360,
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
                            hovertemplate="Nhóm: %{y}<br>Tổng SL quan sát: %{x:,.1f}<br>SL TB/ngày: %{customdata[0]} · Số kỳ QS: %{customdata[1]}<extra></extra>",
                        )
                        style_plotly(
                            fig_ar,
                            palette,
                            height=340,
                            show_legend=False,
                            xaxis_title="Tổng sản lượng quan sát",
                            yaxis_title="Nhóm thuốc ATC",
                        )
                        polish_horizontal_bar(fig_ar, atc_order, float(ar_df["total_observed_qty"].max()))
                        st.plotly_chart(fig_ar, width="stretch", theme=None, config=plotly_config())

        with tab_tbl:
            with st.container(border=True):
                render_chart_header(
                    "Bảng Tra Cứu Chi Tiết Sản Phẩm (Sản Phẩm × ĐVT × Nguồn)",
                    "Đơn giá & Biên lợi nhuận tính theo công thức gia quyền",
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
                    rev_col = f"Doanh thu ({disp_ccy})" if disp_ccy else "Doanh thu"
                    price_col = f"Đơn giá gia quyền ({disp_ccy})" if disp_ccy else "Đơn giá gia quyền"
                    rev_series = pd.to_numeric(pt_df["line_amount"], errors="coerce") * mult
                    price_series = pd.to_numeric(pt_df["weighted_unit_price"], errors="coerce") * mult
                    num_fmt = "%,.0f" if to_vnd else "%,.2f"
                    disp_df = pd.DataFrame(
                        {
                            "Tên sản phẩm": pt_df["product_name"],
                            "Đơn vị tính": pt_df["clean_uom"],
                            "Nhóm dữ liệu": pt_df["dataset_track"].map(track_label),
                            "Số dòng POS": pt_df["line_count"],
                            "CH-ngày": pt_df["active_store_days"],
                            "Sản lượng (theo ĐVT)": safe_round(pt_df["sold_qty"], 0),
                            rev_col: safe_round(rev_series, 0 if to_vnd else 2),
                            price_col: safe_round(price_series, 0 if to_vnd else 2),
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
                            rev_col: st.column_config.NumberColumn(format=num_fmt),
                            price_col: st.column_config.NumberColumn(format=num_fmt),
                            "Biên LN gia quyền (%)": st.column_config.NumberColumn(format="%.2f%%"),
                        },
                    )
                    render_csv_download(disp_df, "chi_tiet_san_pham.csv", key="p4_csv_products")

    if drawer_col is not None:
        render_right_explanation_panel(
            drawer_col,
            page_key="p4",
            page_title="So Sánh Kỳ & Danh Mục",
            glossary_items=[
                ("So sánh Kỳ A vs Kỳ B", "Chọn nhanh MoM, Nửa kỳ, YoY hoặc 2 khoảng ngày bất kỳ ở thanh trên cùng."),
                ("Phạm vi toàn danh mục", "Tổng hợp toàn bộ sản phẩm × ĐVT trong 2 kỳ từ `bi_sales_weather_enriched` trước khi lấy Top, gồm cả món mới phát sinh hoặc ngừng bán."),
                ("Biên LN gia quyền (%)", "Tổng lợi nhuận gộp / Tổng doanh thu có giá vốn trong toàn kỳ, tránh lệch do lấy trung bình cộng từng dòng giao dịch nhỏ."),
                ("Dịch chuyển cơ cấu (điểm %)", "Tỷ trọng (%) của sản phẩm trong Kỳ A trừ tỷ trọng (%) trong Kỳ B."),
                ("Đóng góp số học (điểm %)", "Chênh lệch của riêng mặt hàng đó chia cho tổng quy mô toàn danh mục ở Kỳ B."),
                ("Nhà sản xuất IRPD & Nhóm ATC", "Nhà sản xuất chỉ có ở nguồn IRPD Indonesia; chuỗi ATC đọc độc lập từ `PHARMA_SALES_DAILY_ATC` (2014–2019, không ghi tiền tệ)."),
                ("Tiền Việt (VNĐ ₫)", vnd_rate_note(ccy, True)),
            ],
            extra_notes=list(insight_bullets),
        )


render_page(get_current_filters())
