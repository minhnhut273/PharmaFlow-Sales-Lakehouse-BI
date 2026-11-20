"""Page 1: Executive Overview (Tổng Quan Điều Hành)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from analytics import (
    build_overview_insights,
    compute_monthly_growth,
    compute_variance_and_contributions,
    evaluate_uom_compatibility,
    resolve_comparison_periods,
)
from components.filters import get_current_filters, get_track_bounds, set_global_uoms
from config import (
    TRACK_META,
    country_label,
    fmt_compact,
    fmt_currency,
    fmt_delta,
    fmt_int,
    fmt_metric_state,
    fmt_pct,
    provenance_label,
    safe_round,
    track_label,
)
import db
from queries import (
    FilterState,
    sql_dimension_variance,
    sql_exec_kpis,
    sql_monthly_sales_trend,
    sql_sales_by_country,
    sql_series_avg_growth_reference,
    sql_top_brands,
    sql_track_currency_summary,
    sql_uom_breakdown,
)
from ui import (
    get_active_palette,
    plotly_config,
    polish_diverging_bar,
    polish_horizontal_bar,
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


def _scalar_or_none(val: object) -> float | None:
    if val is None or pd.isna(val):
        return None
    return float(val)


def render_page(filters: FilterState) -> None:
    schema = db.get_active_schema()
    palette = get_active_palette()
    meta = TRACK_META.get(filters.dataset_track or "")
    ccy = meta.currency_code if meta else None
    has_rev = bool(meta.has_revenue) if meta else False
    has_margin = bool(meta.has_margin) if meta else False
    prov_class = meta.provenance_class if meta else "SYNTHETIC"

    bounds = get_track_bounds()
    track_min_date = bounds.get("min_date")
    track_max_date = bounds.get("max_date")
    uoms_avail = bounds.get("uoms_avail") or ()

    render_page_header(
        "Tổng Quan Điều Hành Bán Hàng",
        "Theo dõi doanh thu, sản lượng, biên lợi nhuận, so sánh biến động theo kỳ tương thích và nhóm đóng góp lớn nhất.",
        dataset_track=filters.dataset_track,
        extra_pills=[
            ("Phân tích Bán hàng", "default"),
            ("Chưa gồm Tồn kho / Nhập hàng", "warn"),
        ],
    )

    # 1. Load KPIs + monthly series under the exact same FilterState scope
    kpi_sql, kpi_params = sql_exec_kpis(schema, filters)
    kpi_df = db.run_query_df(kpi_sql, kpi_params)
    row = kpi_df.iloc[0] if not kpi_df.empty else {}

    m_sql, m_params = sql_monthly_sales_trend(schema, filters)
    m_raw_df = db.run_query_df(m_sql, m_params)

    row_count = int(row.get("row_count") or 0)
    rev_rows = int(row.get("rev_rows") or 0)
    margin_rows = int(row.get("margin_rows") or 0)
    total_rev = _scalar_or_none(row.get("total_revenue"))
    total_qty = _scalar_or_none(row.get("total_sold_qty"))
    total_lines = int(row.get("total_line_count") or 0)
    active_sd = int(row.get("active_store_days") or 0)
    total_margin = _scalar_or_none(row.get("total_margin"))
    weighted_margin_pct = _scalar_or_none(row.get("weighted_margin_pct"))
    row_avg_margin_pct = _scalar_or_none(row.get("row_avg_margin_pct"))
    weighted_unit_price = _scalar_or_none(row.get("weighted_unit_price"))
    row_avg_unit_price = _scalar_or_none(row.get("row_avg_unit_price"))

    distinct_uoms = tuple(row.get("distinct_uoms") or uoms_avail or ())
    uom_guard = evaluate_uom_compatibility(filters.dataset_track, filters.clean_uoms, distinct_uoms)
    uom_note = uom_guard.single_uom or (f"Đa ĐVT ({uom_guard.uom_count} loại)" if uom_guard.is_multi_uom_blocked else "Chưa rõ")

    avail_months = m_raw_df["year_month"].tolist() if not m_raw_df.empty else []
    cmp_window = resolve_comparison_periods(
        filters.date_start,
        filters.date_end,
        mode=filters.compare_mode,
        available_months=avail_months,
        track_min_date=track_min_date,
        track_max_date=track_max_date,
    )

    render_active_filter_bar(filters, compare_window=cmp_window)

    # 2. Fetch comparison-period KPIs & main variance driver
    cur_row: dict[str, object] = {}
    prev_row: dict[str, object] = {}
    if cmp_window.valid and cmp_window.cur_start and cmp_window.cur_end and cmp_window.prev_start and cmp_window.prev_end:
        c_sql, c_params = sql_exec_kpis(schema, filters, date_override=(cmp_window.cur_start, cmp_window.cur_end))
        p_sql, p_params = sql_exec_kpis(schema, filters, date_override=(cmp_window.prev_start, cmp_window.prev_end))
        c_df = db.run_query_df(c_sql, c_params)
        p_df = db.run_query_df(p_sql, p_params)
        if not c_df.empty:
            cur_row = dict(c_df.iloc[0])
        if not p_df.empty:
            prev_row = dict(p_df.iloc[0])

    cur_rev = _scalar_or_none(cur_row.get("total_revenue"))
    prev_rev = _scalar_or_none(prev_row.get("total_revenue"))
    cur_qty = _scalar_or_none(cur_row.get("total_sold_qty"))
    prev_qty = _scalar_or_none(prev_row.get("total_sold_qty"))
    cur_mrg = _scalar_or_none(cur_row.get("total_margin"))
    prev_mrg = _scalar_or_none(prev_row.get("total_margin"))
    cur_wmrg = _scalar_or_none(cur_row.get("weighted_margin_pct"))
    prev_wmrg = _scalar_or_none(prev_row.get("weighted_margin_pct"))
    cur_wup = _scalar_or_none(cur_row.get("weighted_unit_price"))
    prev_wup = _scalar_or_none(prev_row.get("weighted_unit_price"))

    # Load variance driver (default country if multi-country, else product)
    countries_avail = bounds.get("countries_avail") or ()
    driver_options = (["country", "brand", "product"] if len(countries_avail) > 1 else ["product", "brand"])
    default_driver = driver_options[0]
    if st.session_state.get("p1_driver_dim") not in driver_options:
        st.session_state["p1_driver_dim"] = default_driver

    use_rev_driver = bool(has_rev and uom_guard.is_multi_uom_blocked)
    driver_metric_label = f"Doanh thu ({ccy})" if use_rev_driver else (f"Sản lượng ({uom_guard.single_uom})" if uom_guard.single_uom else "Sản lượng")
    driver_unit = ccy if use_rev_driver else None

    # Pre-fetch full-catalog product or country variance for insight summary
    driver_summary_df = pd.DataFrame()
    driver_name_col = "label"
    if cmp_window.valid and cmp_window.cur_start and cmp_window.prev_start:
        default_dim_for_insight = "country" if len(countries_avail) > 1 else "product"
        vd_sql, vd_params = sql_dimension_variance(
            schema,
            filters,
            dim_kind=default_dim_for_insight,
            cur_start=cmp_window.cur_start,
            cur_end=cmp_window.cur_end,
            prev_start=cmp_window.prev_start,
            prev_end=cmp_window.prev_end,
            limit=None,
        )
        vd_raw = db.run_query_df(vd_sql, vd_params)
        if not vd_raw.empty:
            val_cur_col = "cur_rev" if use_rev_driver else "cur_qty"
            val_prev_col = "prev_rev" if use_rev_driver else "prev_qty"
            drv_supported = has_rev if use_rev_driver else True
            driver_summary_df = compute_variance_and_contributions(
                vd_raw,
                cur_col=val_cur_col,
                prev_col=val_prev_col,
                metric_supported=drv_supported,
                total_cur_override=cur_rev if use_rev_driver else cur_qty,
                total_prev_override=prev_rev if use_rev_driver else prev_qty,
            )
            if default_dim_for_insight == "country":
                driver_summary_df["label"] = driver_summary_df["country_code"].map(country_label)
            else:
                driver_summary_df["label"] = driver_summary_df.apply(
                    lambda r: f"{r['product_name']} ({r['clean_uom']})" if r.get("clean_uom") else str(r["product_name"]),
                    axis=1,
                )

    insight_bullets = build_overview_insights(
        meta_label=meta.short_vi if meta else str(filters.dataset_track),
        provenance_class=prov_class,
        window=cmp_window,
        metric_label="Doanh thu" if use_rev_driver else "Tổng sản lượng",
        metric_unit=ccy if use_rev_driver else (uom_guard.single_uom if uom_guard.single_uom else None),
        cur_total=cur_rev if use_rev_driver else cur_qty,
        prev_total=prev_rev if use_rev_driver else prev_qty,
        driver_df=driver_summary_df,
        driver_name_col=driver_name_col,
        uom_guard=uom_guard,
    )
    render_insight_box(
        "Tóm tắt điều hành từ dữ liệu đang lọc",
        insight_bullets,
        note=cmp_window.note or None,
    )

    # 3. Row 1: 6 KPI Cards (headline period explicitly separated from comparison period)
    agg_period_label = (
        f"Lũy kế lọc: {filters.date_start:%d/%m/%Y}–{filters.date_end:%d/%m/%Y}"
        if filters.date_start and filters.date_end
        else "Lũy kế khoảng đang lọc"
    )
    has_cmp_window = bool(cmp_window.valid)

    rev_display = fmt_metric_state(
        total_rev,
        supported=has_rev,
        has_rows=row_count > 0 and rev_rows > 0,
        formatter=lambda v: fmt_currency(v, ccy),
    )
    if not has_rev:
        rev_cmp_lbl = "Kỳ so sánh: Nguồn không hỗ trợ"
        rev_delta_txt, rev_delta_tone = "Không ghi nhận doanh thu tiền tệ", "neutral"
    elif has_cmp_window and cur_rev is not None and prev_rev is not None:
        rev_cmp_lbl = f"Kỳ {cmp_window.cur_label}: {fmt_currency(cur_rev, ccy)}"
        raw_delta, rev_delta_tone = fmt_delta(
            cur_rev - prev_rev,
            unit=ccy,
            pct=((cur_rev - prev_rev) / prev_rev) if prev_rev > 0 else None,
        )
        rev_delta_txt = f"So với {cmp_window.prev_label}: {raw_delta}"
    else:
        rev_cmp_lbl = "Kỳ so sánh: Chưa đủ dữ liệu"
        rev_delta_txt, rev_delta_tone = "Cần ít nhất 2 kỳ hợp lệ để đối chiếu", "neutral"

    if uom_guard.is_multi_uom_blocked:
        qty_display = "Cần chọn 1 ĐVT"
        qty_cmp_lbl = f"Đang gồm {uom_guard.uom_count} ĐVT khác nhau"
        qty_delta_txt, qty_delta_tone = "Chọn 1 ĐVT ở thanh lọc để mở khóa", "warn"
        qty_sub = "Không cộng gộp sản lượng khi chưa có hệ số quy đổi chung giữa các ĐVT."
    else:
        qty_display = fmt_metric_state(total_qty, supported=True, has_rows=row_count > 0)
        if has_cmp_window and cur_qty is not None and prev_qty is not None:
            cur_q_txt = fmt_compact(cur_qty) + (f" {uom_guard.single_uom}" if uom_guard.single_uom else "")
            qty_cmp_lbl = f"Kỳ {cmp_window.cur_label}: {cur_q_txt}"
            raw_delta, qty_delta_tone = fmt_delta(
                cur_qty - prev_qty,
                unit=uom_guard.single_uom or "",
                pct=((cur_qty - prev_qty) / prev_qty) if prev_qty > 0 else None,
            )
            qty_delta_txt = f"So với {cmp_window.prev_label}: {raw_delta}"
        else:
            qty_cmp_lbl = "Kỳ so sánh: Chưa đủ dữ liệu"
            qty_delta_txt, qty_delta_tone = "Cần ít nhất 2 kỳ hợp lệ để đối chiếu", "neutral"
        qty_sub = f"Đơn vị tính: {uom_note}"

    margin_display = fmt_metric_state(
        total_margin,
        supported=has_margin,
        has_rows=row_count > 0 and margin_rows > 0,
        formatter=lambda v: fmt_currency(v, ccy),
    )
    if not has_margin:
        mrg_cmp_lbl = "Kỳ so sánh: Nguồn không hỗ trợ"
        mrg_delta_txt, mrg_delta_tone = "Chưa ghi nhận giá vốn trên nguồn này", "neutral"
        mrg_sub = "Chỉ có dữ liệu giá vốn & lợi nhuận ở nguồn ONYX Châu Âu (EUR)."
    else:
        if has_cmp_window and cur_mrg is not None and prev_mrg is not None:
            mrg_cmp_lbl = f"Kỳ {cmp_window.cur_label}: {fmt_currency(cur_mrg, ccy)}"
            raw_delta, mrg_delta_tone = fmt_delta(
                cur_mrg - prev_mrg,
                unit=ccy,
                pct=((cur_mrg - prev_mrg) / prev_mrg) if prev_mrg > 0 else None,
            )
            mrg_delta_txt = f"So với {cmp_window.prev_label}: {raw_delta}"
        else:
            mrg_cmp_lbl = "Kỳ so sánh: Chưa đủ dữ liệu"
            mrg_delta_txt, mrg_delta_tone = "Cần ít nhất 2 kỳ hợp lệ để đối chiếu", "neutral"
        mrg_sub = f"Phủ giá vốn: {margin_rows:,}/{row_count:,} dòng dữ liệu."

    margin_pct_display = fmt_metric_state(
        weighted_margin_pct,
        supported=has_margin,
        has_rows=row_count > 0 and margin_rows > 0,
        formatter=fmt_pct,
    )
    if not has_margin:
        mpct_cmp_lbl = "Kỳ so sánh: Nguồn không hỗ trợ"
        mpct_delta_txt, mpct_delta_tone = "Chưa có dữ liệu giá vốn", "neutral"
        mpct_sub = "Nguồn hiện tại chưa có trường chi phí và lợi nhuận."
    else:
        if has_cmp_window and cur_wmrg is not None and prev_wmrg is not None:
            mpct_cmp_lbl = f"Kỳ {cmp_window.cur_label}: {fmt_pct(cur_wmrg)}"
            raw_delta, mpct_delta_tone = fmt_delta((cur_wmrg - prev_wmrg) * 100.0, is_pp=True)
            mpct_delta_txt = f"So với {cmp_window.prev_label}: {raw_delta}"
        else:
            mpct_cmp_lbl = "Kỳ so sánh: Chưa đủ dữ liệu"
            mpct_delta_txt, mpct_delta_tone = "Cần ít nhất 2 kỳ hợp lệ để đối chiếu", "neutral"
        mpct_sub = f"Tính theo tổng lợi nhuận / doanh thu (TB theo dòng: {fmt_pct(row_avg_margin_pct)})."

    if not has_rev:
        price_display = "Nguồn không hỗ trợ"
        price_cmp_lbl = "Kỳ so sánh: Nguồn không hỗ trợ"
        price_delta_txt, price_delta_tone = "Không có doanh thu tiền tệ", "neutral"
        price_sub = "Nguồn này không ghi nhận doanh thu và đơn giá."
    elif uom_guard.is_multi_uom_blocked:
        price_display = "Cần chọn 1 ĐVT"
        price_cmp_lbl = f"Đang lẫn {uom_guard.uom_count} ĐVT"
        price_delta_txt, price_delta_tone = "Chọn 1 ĐVT để tính đơn giá", "warn"
        price_sub = "Không tính đơn giá bình quân khi trộn hộp, viên, lọ..."
    else:
        price_display = fmt_metric_state(
            weighted_unit_price,
            supported=has_rev,
            has_rows=row_count > 0 and rev_rows > 0,
            formatter=lambda v: fmt_currency(v, ccy, compact=False),
        )
        if has_cmp_window and cur_wup is not None and prev_wup is not None:
            price_cmp_lbl = f"Kỳ {cmp_window.cur_label}: {fmt_currency(cur_wup, ccy, compact=False)}"
            raw_delta, price_delta_tone = fmt_delta(
                cur_wup - prev_wup,
                unit=ccy,
                pct=((cur_wup - prev_wup) / prev_wup) if prev_wup > 0 else None,
            )
            price_delta_txt = f"So với {cmp_window.prev_label}: {raw_delta}"
        else:
            price_cmp_lbl = "Kỳ so sánh: Chưa đủ dữ liệu"
            price_delta_txt, price_delta_tone = "Cần ít nhất 2 kỳ hợp lệ để đối chiếu", "neutral"
        price_sub = (
            f"Gia quyền theo sản lượng ({uom_note}). "
            f"TB theo dòng: {fmt_currency(row_avg_unit_price, ccy, compact=False)}."
        )

    c1, c2, c3 = st.columns(3)
    with c1:
        render_kpi_card(
            "Tổng Doanh Thu",
            rev_display,
            f"Ghi nhận {rev_rows:,}/{row_count:,} dòng · Tiền tệ {ccy}" if has_rev and ccy else "Nguồn này không ghi nhận doanh thu tiền tệ",
            tag=ccy or "N/A",
            accent=palette.primary,
            period_label=agg_period_label,
            compare_label=rev_cmp_lbl,
            delta_text=rev_delta_txt,
            delta_tone=rev_delta_tone,
        )
    with c2:
        render_kpi_card(
            "Tổng Sản Lượng Bán",
            qty_display,
            qty_sub,
            tag=uom_guard.single_uom or "ĐVT",
            accent=palette.accent,
            period_label=agg_period_label,
            compare_label=qty_cmp_lbl,
            delta_text=qty_delta_txt,
            delta_tone=qty_delta_tone,
        )
    with c3:
        render_kpi_card(
            "Số Đơn Hàng Duy Nhất",
            "Chưa khả dụng",
            "Chưa có dữ liệu đếm đơn duy nhất trong nguồn hiện tại.",
            tag="Cần bổ sung",
            accent="#d97706",
            period_label=agg_period_label,
            compare_label=f"Số dòng bán kỳ lọc: {fmt_int(total_lines)}",
            delta_text=f"Cửa hàng-ngày có bán: {fmt_int(active_sd)}",
            delta_tone="neutral",
        )

    c4, c5, c6 = st.columns(3)
    with c4:
        render_kpi_card(
            "Tổng Lợi Nhuận Gộp",
            margin_display,
            mrg_sub,
            tag=ccy or "N/A",
            accent=palette.primary_dark,
            period_label=agg_period_label,
            compare_label=mrg_cmp_lbl,
            delta_text=mrg_delta_txt,
            delta_tone=mrg_delta_tone,
        )
    with c5:
        render_kpi_card(
            "Biên Lợi Nhuận Gia Quyền (%)",
            margin_pct_display,
            mpct_sub,
            tag="Theo doanh thu",
            accent=palette.discrete[3],
            period_label=agg_period_label,
            compare_label=mpct_cmp_lbl,
            delta_text=mpct_delta_txt,
            delta_tone=mpct_delta_tone,
        )
    with c6:
        render_kpi_card(
            "Đơn Giá Bình Quân Gia Quyền",
            price_display,
            price_sub,
            tag=ccy or "N/A",
            accent=palette.discrete[5],
            period_label=agg_period_label,
            compare_label=price_cmp_lbl,
            delta_text=price_delta_txt,
            delta_tone=price_delta_tone,
        )

    # 4. Row 2: Exact Aggregate Monthly Trend (7) + Variance Driver & Structure (5)
    col_trend, col_driver = st.columns([7, 5], gap="medium")

    with col_trend:
        with st.container(border=True):
            render_chart_header(
                "Xu Hướng & Tăng Trưởng Tổng Theo Tháng",
                "Cùng 100% phạm vi bộ lọc với KPI; % tăng trưởng tính từ tổng lượng/doanh thu 2 tháng đủ ngày liền kề",
            )
            render_scope_strip(
                f"Nguồn: {track_label(filters.dataset_track)} · Trục cột & đường cùng dùng phạm vi lọc · Tự động ngắt đường khi thiếu tháng hoặc tháng chưa đủ ngày"
            )
            trend_metric_opts = ["line_amount"] if (has_rev and uom_guard.is_multi_uom_blocked) else (
                ["sold_qty", "line_amount"] if has_rev else ["sold_qty"]
            )
            if st.session_state.get("p1_trend_metric") not in trend_metric_opts:
                st.session_state["p1_trend_metric"] = trend_metric_opts[0]

            selected_trend_metric = trend_metric_opts[0]
            if len(trend_metric_opts) > 1:
                selected_trend_metric = st.radio(
                    "Chỉ tiêu biểu đồ tháng",
                    options=trend_metric_opts,
                    format_func=lambda m: f"Sản lượng ({uom_guard.single_uom})" if (m == "sold_qty" and uom_guard.single_uom) else ("Sản lượng" if m == "sold_qty" else f"Doanh thu ({ccy})"),
                    horizontal=True,
                    key="p1_trend_metric",
                )

            growth_df = compute_monthly_growth(
                m_raw_df,
                date_start=filters.date_start,
                date_end=filters.date_end,
                track_min_date=track_min_date,
                track_max_date=track_max_date,
            )
            if growth_df.empty:
                render_empty_state()
            else:
                val_col = selected_trend_metric
                pct_col = "mom_rev_pct" if val_col == "line_amount" else "mom_qty_pct"
                status_col = "mom_rev_status" if val_col == "line_amount" else "mom_status"
                y_bar_title = f"Doanh thu ({ccy})" if val_col == "line_amount" else f"Sản lượng ({uom_note})"

                plot_df = growth_df.copy()
                plot_df["pct_plot"] = pd.to_numeric(plot_df[pct_col], errors="coerce") * 100.0
                bar_colors = [
                    "#94a3b8" if not hd else ("#f59e0b" if part else palette.primary)
                    for hd, part in zip(plot_df["has_data"], plot_df["is_partial_month"])
                ]
                hover_txt = [
                    f"Kỳ {r['month_label']}<br>"
                    f"Giá trị: {fmt_compact(r[val_col]) if pd.notna(r[val_col]) else 'Không có dữ liệu'}<br>"
                    f"Số ngày phát sinh: {int(r['active_days'])}/{int(r['calendar_days'])}<br>"
                    f"MoM tổng: {r['pct_plot']:+.2f}%<br>" if pd.notna(r["pct_plot"]) else
                    f"Kỳ {r['month_label']}<br>"
                    f"Giá trị: {fmt_compact(r[val_col]) if pd.notna(r[val_col]) else 'Không có dữ liệu'}<br>"
                    f"Số ngày phát sinh: {int(r['active_days'])}/{int(r['calendar_days'])}<br>"
                    f"Trạng thái MoM: {r[status_col]}<br>"
                    + (f"Ghi chú: {r['partial_reason']}" if r["partial_reason"] else "")
                    for _, r in plot_df.iterrows()
                ]

                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(
                    go.Bar(
                        x=plot_df["year_month"],
                        y=plot_df[val_col],
                        name="Tổng theo tháng",
                        marker_color=bar_colors,
                        opacity=0.88,
                        text=hover_txt,
                        hovertemplate="%{text}<extra></extra>",
                    ),
                    secondary_y=False,
                )
                fig.add_trace(
                    go.Scatter(
                        x=plot_df["year_month"],
                        y=plot_df["pct_plot"],
                        name="Tăng trưởng tổng MoM (%)",
                        mode="lines+markers",
                        connectgaps=False,
                        line=dict(color=palette.accent, width=2.5),
                        marker=dict(size=5.5),
                        hovertemplate="Kỳ %{x|%m/%Y}<br>Tăng trưởng tổng MoM: %{y:+.2f}%<extra></extra>",
                    ),
                    secondary_y=True,
                )
                style_plotly(fig, palette, height=345, xaxis_title="Kỳ (Tháng)")
                fig.update_yaxes(title_text=y_bar_title, secondary_y=False)
                fig.update_yaxes(title_text="Tăng trưởng tổng MoM (%)", ticksuffix="%", secondary_y=True, showgrid=False)
                st.plotly_chart(fig, width="stretch", theme=None, config=plotly_config())

                partial_cnt = int(plot_df["is_partial_month"].sum())
                missing_cnt = int((~plot_df["has_data"]).sum())
                if partial_cnt or missing_cnt:
                    st.caption(
                        f"Màu cam = tháng chưa đủ ngày ({partial_cnt} kỳ), cột trống = tháng không có dữ liệu ({missing_cnt} kỳ) — đều tự động ngắt % MoM."
                    )

                with st.expander("Tham chiếu mở rộng: Trung bình tăng trưởng cấp từng chuỗi"):
                    ref_sql, ref_params = sql_series_avg_growth_reference(schema, filters)
                    ref_df = db.run_query_df(ref_sql, ref_params)
                    st.caption(
                        "Số liệu từ bảng `kpi_sales_trend` (trung bình tăng trưởng từng chuỗi Sản phẩm × Cửa hàng) — không dùng thay tăng trưởng tổng điều hành "
                        "vì các chuỗi quy mô nhỏ tăng đột biến có thể kéo trung bình cộng lên cao ngay cả khi tổng sản lượng giảm."
                    )
                    if not ref_df.empty:
                        merged_ref = plot_df[["year_month", "month_label", "sold_qty", "mom_qty_pct", "mom_status"]].merge(
                            ref_df[["period_start", "series_avg_pct_change", "series_pct_rows"]],
                            left_on="year_month",
                            right_on="period_start",
                            how="left",
                        )
                        ref_disp = pd.DataFrame(
                            {
                                "Tháng": merged_ref["month_label"],
                                "Tổng SL": safe_round(merged_ref["sold_qty"], 0),
                                "MoM tổng (%)": safe_round(merged_ref["mom_qty_pct"] * 100.0, 2),
                                "TB từng chuỗi (%)": safe_round(merged_ref["series_avg_pct_change"] * 100.0, 2),
                                "Số chuỗi": merged_ref["series_pct_rows"],
                                "Trạng thái MoM": merged_ref["mom_status"],
                            }
                        )
                        st.dataframe(ref_disp.tail(12), width="stretch", hide_index=True, height=220)

    with col_driver:
        with st.container(border=True):
            render_chart_header(
                "Đóng Góp Biến Động & Cơ Cấu",
                f"Nhóm đóng góp tăng/giảm lớn nhất giữa {cmp_window.cur_label} và {cmp_window.prev_label}"
                if cmp_window.valid
                else "Cơ cấu thị trường trong phạm vi đang lọc",
            )
            tab_drv, tab_mix = st.tabs(["Đóng góp biến động", "Cơ cấu Quốc gia"])
            with tab_drv:
                if not cmp_window.valid or not cmp_window.cur_start or not cmp_window.prev_start:
                    render_empty_state(cmp_window.note or "Chưa đủ 2 kỳ để tính đóng góp biến động.")
                else:
                    dim_labels = {"country": "Quốc gia", "brand": "Thương hiệu", "product": "Sản phẩm"}
                    sel_dim = st.radio(
                        "Phân rã đóng góp theo",
                        options=driver_options,
                        format_func=lambda k: dim_labels[k],
                        horizontal=True,
                        key="p1_driver_dim",
                    )
                    dv_sql, dv_params = sql_dimension_variance(
                        schema,
                        filters,
                        dim_kind=sel_dim,
                        cur_start=cmp_window.cur_start,
                        cur_end=cmp_window.cur_end,
                        prev_start=cmp_window.prev_start,
                        prev_end=cmp_window.prev_end,
                        limit=None,
                    )
                    dv_raw = db.run_query_df(dv_sql, dv_params)
                    if dv_raw.empty:
                        render_empty_state("Chiều phân tích này không có dữ liệu trong nguồn đang chọn.")
                    elif (
                        sel_dim == "brand"
                        and "nonnull_label_rows" in dv_raw.columns
                        and int(dv_raw["nonnull_label_rows"].fillna(0).sum()) == 0
                    ):
                        render_empty_state("Nguồn dữ liệu này chưa có thông tin thương hiệu để phân rã.")
                    else:
                        use_rev_d = bool(has_rev and (uom_guard.is_multi_uom_blocked or selected_trend_metric == "line_amount"))
                        c_col = "cur_rev" if use_rev_d else "cur_qty"
                        p_col = "prev_rev" if use_rev_d else "prev_qty"
                        dv_sup = has_rev if use_rev_d else True
                        dv = compute_variance_and_contributions(dv_raw, cur_col=c_col, prev_col=p_col, metric_supported=dv_sup)
                        if sel_dim == "country":
                            dv["item"] = dv["country_code"].map(country_label)
                        elif sel_dim == "brand":
                            dv["item"] = dv["brand_name"].astype(str)
                        else:
                            dv["item"] = dv.apply(
                                lambda r: f"{r['product_name']} ({r['clean_uom']})" if r.get("clean_uom") else str(r["product_name"]),
                                axis=1,
                            )
                        top_gain = dv[dv["delta"] > 0].sort_values("delta", ascending=False).head(6)
                        top_drop = dv[dv["delta"] < 0].sort_values("delta", ascending=True).head(6)
                        combined = pd.concat([top_gain, top_drop], ignore_index=True).drop_duplicates(subset=["item"])
                        if combined.empty:
                            render_empty_state("Không có biến động chênh lệch giữa 2 kỳ so sánh.")
                        else:
                            combined = combined.sort_values("delta", ascending=True)
                            colors = [palette.primary if d >= 0 else "#dc2626" for d in combined["delta"]]
                            unit_lbl = ccy if use_rev_d else (uom_guard.single_uom or "ĐVT")
                            fig_drv = go.Figure(
                                go.Bar(
                                    x=combined["delta"],
                                    y=combined["item"],
                                    orientation="h",
                                    marker_color=colors,
                                    text=[f"{d:+,.0f}" for d in combined["delta"]],
                                    textposition="outside",
                                    customdata=list(
                                        zip(
                                            combined[p_col],
                                            combined[c_col],
                                            combined["contrib_pp"].fillna(0.0),
                                        )
                                    ),
                                    hovertemplate=(
                                        "<b>%{y}</b><br>"
                                        f"Kỳ trước: %{{customdata[0]:,.0f}} {unit_lbl}<br>"
                                        f"Kỳ này: %{{customdata[1]:,.0f}} {unit_lbl}<br>"
                                        f"Chênh lệch: %{{x:+,.0f}} {unit_lbl}<br>"
                                        "Đóng góp số học: %{customdata[2]:+.2f} điểm %<extra></extra>"
                                    ),
                                )
                            )
                            style_plotly(
                                fig_drv,
                                palette,
                                height=320,
                                show_legend=False,
                                xaxis_title=f"Chênh lệch tuyệt đối ({unit_lbl})",
                                yaxis_title="",
                            )
                            polish_diverging_bar(fig_drv, float(combined["delta"].abs().max()))
                            st.plotly_chart(fig_drv, width="stretch", theme=None, config=plotly_config())
                            tot_prev_cat = float(pd.to_numeric(dv[p_col], errors="coerce").fillna(0.0).sum())
                            tot_cur_cat = float(pd.to_numeric(dv[c_col], errors="coerce").fillna(0.0).sum())
                            pct_suffix = (
                                f", {((tot_cur_cat - tot_prev_cat) / tot_prev_cat * 100.0):+.2f}%"
                                if tot_prev_cat > 0
                                else ""
                            )
                            st.caption(
                                f"Tính trên toàn bộ {len(dv):,} nhóm hợp lệ (tổng kỳ trước {fmt_compact(tot_prev_cat)} → kỳ này {fmt_compact(tot_cur_cat)}{pct_suffix}); biểu đồ hiển thị tối đa Top 6 tăng và Top 6 giảm."
                            )

            with tab_mix:
                ctry_sql, ctry_params = sql_sales_by_country(schema, filters)
                ctry_df = db.run_query_df(ctry_sql, ctry_params)
                if ctry_df.empty:
                    render_empty_state()
                else:
                    ctry_df = ctry_df.copy()
                    ctry_df["country_vi"] = ctry_df["country_code"].map(country_label)
                    pie_col = "line_amount" if (has_rev and uom_guard.is_multi_uom_blocked) else "sold_qty"
                    pie_title = f"Tổng DT ({ccy})" if pie_col == "line_amount" else "Tổng SL"
                    total_sum = float(pd.to_numeric(ctry_df[pie_col], errors="coerce").fillna(0).sum())
                    fig_donut = px.pie(
                        ctry_df,
                        names="country_vi",
                        values=pie_col,
                        hole=0.55,
                        color_discrete_sequence=list(palette.discrete),
                    )
                    fig_donut.update_traces(
                        textposition="inside",
                        textinfo="percent",
                        textfont_size=11,
                        hovertemplate="%{label}<br>Giá trị: %{value:,.0f} (%{percent})<extra></extra>",
                    )
                    fig_donut.add_annotation(
                        text=f"<b>{fmt_compact(total_sum)}</b><br><span style='font-size:11px;color:{palette.muted}'>{pie_title}</span>",
                        x=0.5,
                        y=0.5,
                        showarrow=False,
                        font=dict(size=14, color=palette.ink),
                    )
                    style_plotly(fig_donut, palette, height=340, show_legend=True)
                    fig_donut.update_layout(
                        legend=dict(orientation="h", yanchor="top", y=-0.04, xanchor="center", x=0.5, font=dict(size=10.5)),
                        margin=dict(l=12, r=12, t=12, b=64),
                    )
                    st.plotly_chart(fig_donut, width="stretch", theme=None, config=plotly_config())

    # 5. Row 3: UOM Split / Top Brands (6) + OBSERVED vs SYNTHETIC Comparison Table (6)
    col_left, col_table = st.columns([6, 6], gap="medium")

    with col_left:
        with st.container(border=True):
            if uom_guard.is_multi_uom_blocked:
                render_chart_header(
                    "Phân Tách Theo Đơn Vị Tính (ĐVT)",
                    f"Nguồn {meta.short_vi if meta else ''} có {uom_guard.uom_count} ĐVT khác nhau — hiển thị tách riêng từng đơn vị tính & đơn giá gia quyền",
                )
                uom_sql, uom_params = sql_uom_breakdown(schema, filters)
                uom_df = db.run_query_df(uom_sql, uom_params)
                if uom_df.empty:
                    render_empty_state()
                else:
                    top_uoms = uom_df["clean_uom"].dropna().head(4).tolist()
                    if top_uoms:
                        st.caption("Chọn nhanh 1 ĐVT để mở khóa sản lượng & đơn giá toàn dashboard:")
                        ucols = st.columns(len(top_uoms))
                        for idx, u in enumerate(top_uoms):
                            with ucols[idx]:
                                st.button(
                                    f"Lọc ĐVT: {u}",
                                    key=f"p1_pick_uom_{idx}",
                                    width="stretch",
                                    on_click=set_global_uoms,
                                    args=([str(u)],),
                                )
                    rev_h = f"Doanh thu ({ccy})" if ccy else "Doanh thu"
                    up_h = f"Đơn giá gia quyền ({ccy})" if ccy else "Đơn giá gia quyền"
                    uom_disp = pd.DataFrame(
                        {
                            "Đơn vị tính": uom_df["clean_uom"],
                            "Số dòng POS": uom_df["line_count"],
                            "CH-ngày": uom_df["active_store_days"],
                            "Sản lượng (riêng ĐVT)": safe_round(uom_df["sold_qty"], 0),
                            rev_h: safe_round(uom_df["line_amount"], 0),
                            up_h: safe_round(uom_df["weighted_unit_price"], 2),
                        }
                    )
                    st.dataframe(uom_disp, width="stretch", hide_index=True, height=280)
            else:
                render_chart_header(
                    "Top 15 Thương Hiệu Theo Sản Lượng",
                    f"Xếp hạng theo phạm vi lọc hiện tại (ĐVT: {uom_note})",
                )
                b_sql, b_params = sql_top_brands(schema, filters, limit=15)
                brand_df = db.run_query_df(b_sql, b_params)
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
                        height=380,
                        show_legend=False,
                        xaxis_title=f"Sản lượng ({uom_note})",
                        yaxis_title="Thương hiệu",
                    )
                    polish_horizontal_bar(fig_bar, brand_df["brand_name"].tolist(), float(brand_df["sold_qty"].max()))
                    st.plotly_chart(fig_bar, width="stretch", theme=None, config=plotly_config())

    with col_table:
        with st.container(border=True):
            render_chart_header(
                "Đối Chiếu Nguồn Thực Tế vs Mô Phỏng",
                "Tách riêng tiền tệ, số ĐVT, số dòng bán và khoảng thời gian từng nguồn dữ liệu",
            )
            compare_all = st.toggle(
                "Hiển thị toàn bộ 3 nguồn (bỏ qua ngày/quốc gia riêng của nguồn đang chọn)",
                value=True,
                key="p1_summary_all_tracks",
            )
            if compare_all:
                render_scope_strip("Phạm vi bảng: Toàn bộ 3 nguồn dữ liệu (không áp dụng bộ lọc ngày/quốc gia/ĐVT ở thanh lọc).")
            else:
                render_scope_strip(f"Phạm vi bảng: Khớp 100% bộ lọc hiện tại ({track_label(filters.dataset_track)}).")

            s_sql, s_params = sql_track_currency_summary(schema, filters, show_all_tracks=compare_all)
            sum_df = db.run_query_df(s_sql, s_params)
            if sum_df.empty:
                render_empty_state()
            else:
                display_df = pd.DataFrame(
                    {
                        "Nhóm dữ liệu": sum_df["dataset_track"].map(track_label),
                        "Loại nguồn": sum_df["provenance_class"].map(provenance_label),
                        "Tiền tệ": sum_df["currency_code"],
                        "Số ĐVT": sum_df["distinct_uom_count"],
                        "Từ ngày": sum_df["min_date"],
                        "Đến ngày": sum_df["max_date"],
                        "Số dòng POS": sum_df["line_count"],
                        "CH-ngày": sum_df["active_store_days"],
                        "Sản lượng (nếu 1 ĐVT)": [
                            None if int(r["distinct_uom_count"] or 0) > 1 or pd.isna(r["sold_qty"]) else round(float(r["sold_qty"]))
                            for _, r in sum_df.iterrows()
                        ],
                        "Doanh thu": safe_round(sum_df["line_amount"], 2),
                        "Lợi nhuận": safe_round(sum_df["margin_amount"], 2),
                    }
                )
                st.dataframe(
                    display_df,
                    width="stretch",
                    hide_index=True,
                    height=280,
                    column_config={
                        "Số dòng POS": st.column_config.NumberColumn(format="%,d"),
                        "CH-ngày": st.column_config.NumberColumn(format="%,d"),
                        "Sản lượng (nếu 1 ĐVT)": st.column_config.NumberColumn(format="%,.0f"),
                        "Doanh thu": st.column_config.NumberColumn(format="%,.2f"),
                        "Lợi nhuận": st.column_config.NumberColumn(format="%,.2f"),
                    },
                )
                st.caption("Ô `Sản lượng` để trống với nguồn nhiều ĐVT do chưa có hệ số quy đổi chung; dữ liệu hiện có chưa đếm được số đơn hàng duy nhất.")
                render_csv_download(display_df, "doi_chieu_nguon_du_lieu.csv", key="p1_csv_summary")

    with st.expander("Định nghĩa chỉ số & nguồn dữ liệu"):
        st.markdown(
            "- **Nguồn dữ liệu chính:** Tổng hợp từ `bi_sales_weather_enriched` tại grain `Sản phẩm × Cửa hàng × Ngày`, phân tách rạch ròi giữa nguồn quan sát thực tế (`OBSERVED`) và nguồn mô phỏng (`SYNTHETIC`).\n"
            "- **Lũy kế lọc vs Biến động kỳ so sánh:** Số lớn trên mỗi thẻ KPI là lũy kế toàn bộ khoảng ngày đang lọc ở thanh bên; khung phía dưới tách riêng giá trị kỳ so sánh gần nhất và chênh lệch so với kỳ liền trước đủ ngày.\n"
            "- **Biên lợi nhuận & Đơn giá gia quyền:** Tính bằng `SUM(margin_amount) / SUM(line_amount)` và `SUM(line_amount) / SUM(sold_qty)` trong đúng phạm vi lọc (không dùng trung bình cộng đơn giản của từng dòng).\n"
            "- **Số đơn hàng duy nhất (`COUNT(DISTINCT sales_order_id)`):** Tạm ẩn vì Gold mirror hiện tổng hợp ở grain `SP × CH × Ngày` và chưa truyền mã hóa đơn duy nhất qua data contract (cần bổ sung order mart riêng trước khi mở chỉ số này).\n"
            "- **Đa đơn vị tính (IRPD):** Thiếu hệ số quy đổi `base_qty`, nên dashboard không cộng gộp sản lượng hoặc đơn giá khi chưa chọn đúng 1 ĐVT.\n"
            "- **Tăng trưởng tổng theo tháng:** Tổng lượng/doanh thu từng tháng từ toàn bộ dòng hợp lệ, tự động ngắt đường khi thiếu tháng hoặc tháng chưa đủ ngày (bảng chuỗi cấp SP × CH xem tại `kpi_sales_trend`)."
        )


render_page(get_current_filters())
