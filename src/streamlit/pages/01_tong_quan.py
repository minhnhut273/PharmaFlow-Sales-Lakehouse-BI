"""Page 1: Store Manager View — Store Product Mix, Profit & Per-Product Time Series."""

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
    TIME_GRAIN_ORDER,
    TRACK_META,
    country_label,
    currency_display_unit,
    currency_multiplier,
    fmt_compact,
    fmt_currency,
    fmt_delta,
    fmt_int,
    fmt_metric_state,
    fmt_pct,
    provenance_label,
    safe_round,
    time_grain_label,
    track_label,
    vnd_rate_note,
)
import db
from queries import (
    FilterState,
    sql_dimension_variance,
    sql_exec_kpis,
    sql_monthly_sales_trend,
    sql_sales_by_country,
    sql_series_avg_growth_reference,
    sql_store_product_mix,
    sql_time_series_by_grain,
    sql_top_brands,
    sql_track_currency_summary,
    sql_uom_breakdown,
)
from ui import (
    get_active_palette,
    navigate_to_compare_page,
    open_page_layout_columns,
    plotly_config,
    polish_diverging_bar,
    polish_horizontal_bar,
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


def _scalar_or_none(val: object) -> float | None:
    if val is None or pd.isna(val):
        return None
    return float(val)


def _format_money(
    value: float | None,
    ccy: str | None,
    *,
    to_vnd: bool,
    compact: bool = True,
) -> str:
    return fmt_currency(value, ccy, compact=compact, to_vnd=to_vnd)


def render_page(filters: FilterState) -> None:
    schema = db.get_active_schema()
    palette = get_active_palette()
    meta = TRACK_META.get(filters.dataset_track or "")
    ccy = meta.currency_code if meta else None
    has_rev = bool(meta.has_revenue) if meta else False
    has_margin = bool(meta.has_margin) if meta else False
    prov_class = meta.provenance_class if meta else "SYNTHETIC"

    to_vnd = bool(filters.display_vnd and ccy)
    disp_ccy = currency_display_unit(ccy, to_vnd=to_vnd)
    ccy_mult = currency_multiplier(ccy, to_vnd=to_vnd)

    bounds = get_track_bounds()
    track_min_date = bounds.get("min_date")
    track_max_date = bounds.get("max_date")
    uoms_avail = bounds.get("uoms_avail") or ()

    render_page_header(
        "Cửa Hàng & Mặt Hàng",
        "Tỷ trọng danh mục đang bán, lợi nhuận theo sản phẩm và biến động theo từng loại thuốc.",
        dataset_track=filters.dataset_track,
        extra_pills=[
            ("Góc nhìn Cửa hàng trưởng", "default"),
            ("Không gồm Tồn kho", "warn"),
        ],
    )

    # 1. Core KPI & Monthly Comparison Scope
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

    render_top_action_bar(filters, page_key="p1", compare_window=cmp_window, show_compare_jump=True)

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

    # Pre-fetch driver variance for optional right-panel insights + reuse on Driver tab
    countries_avail = bounds.get("countries_avail") or ()
    driver_options = (["country", "brand", "product"] if len(countries_avail) > 1 else ["product", "brand"])
    default_driver = driver_options[0]
    if st.session_state.get("p1_driver_dim") not in driver_options:
        st.session_state["p1_driver_dim"] = default_driver

    use_rev_driver = bool(has_rev and uom_guard.is_multi_uom_blocked)
    driver_summary_df = pd.DataFrame()
    default_dim_for_insight: str | None = None
    vd_raw = pd.DataFrame()
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
        driver_name_col="label",
        uom_guard=uom_guard,
    )

    main_col, drawer_col = open_page_layout_columns()

    with main_col:
        # Store insights silently for Right-Side Panel & compact expandable strip (zero wall-of-text clutter)
        render_insight_box("Xem nhanh biến động & điểm chính", insight_bullets, note=cmp_window.note or None)

        # 2. Row 1: 6 Minimalist KPI Cards with top-right ⓘ hover tooltips + clean Lũy kế / Kỳ so sánh split
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
            formatter=lambda v: _format_money(v, ccy, to_vnd=to_vnd),
        )
        if not has_rev:
            rev_cmp_lbl = "Kỳ so sánh: Nguồn không có tiền tệ"
            rev_delta_txt, rev_delta_tone = "Chỉ hiển thị sản lượng", "neutral"
        elif has_cmp_window and cur_rev is not None and prev_rev is not None:
            rev_cmp_lbl = f"Kỳ {cmp_window.cur_label}: {_format_money(cur_rev, ccy, to_vnd=to_vnd)}"
            raw_delta, rev_delta_tone = fmt_delta(
                (cur_rev - prev_rev) * ccy_mult,
                unit=disp_ccy,
                pct=((cur_rev - prev_rev) / prev_rev) if prev_rev > 0 else None,
            )
            rev_delta_txt = f"So với {cmp_window.prev_label}: {raw_delta}"
        else:
            rev_cmp_lbl = "Kỳ so sánh: Chưa đủ dữ liệu"
            rev_delta_txt, rev_delta_tone = "Chọn ≥ 2 kỳ để đối chiếu", "neutral"

        if uom_guard.is_multi_uom_blocked:
            qty_display = "Cần chọn 1 ĐVT"
            qty_cmp_lbl = f"Đang lẫn {uom_guard.uom_count} ĐVT"
            qty_delta_txt, qty_delta_tone = "Chọn 1 ĐVT ở thanh bên", "warn"
            qty_sub = "Không cộng gộp viên + hộp + vỉ"
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
                qty_delta_txt, qty_delta_tone = "Chọn ≥ 2 kỳ để đối chiếu", "neutral"
            qty_sub = f"ĐVT: {uom_note} · {fmt_int(total_lines)} lượt dòng"

        margin_display = fmt_metric_state(
            total_margin,
            supported=has_margin,
            has_rows=row_count > 0 and margin_rows > 0,
            formatter=lambda v: _format_money(v, ccy, to_vnd=to_vnd),
        )
        if not has_margin:
            mrg_cmp_lbl = "Kỳ so sánh: Chưa có giá gốc"
            mrg_delta_txt, mrg_delta_tone = "Chỉ có ở nguồn ONYX EU", "neutral"
            mrg_sub = "Nguồn hiện tại không có chi phí vốn"
        else:
            if has_cmp_window and cur_mrg is not None and prev_mrg is not None:
                mrg_cmp_lbl = f"Kỳ {cmp_window.cur_label}: {_format_money(cur_mrg, ccy, to_vnd=to_vnd)}"
                raw_delta, mrg_delta_tone = fmt_delta(
                    (cur_mrg - prev_mrg) * ccy_mult,
                    unit=disp_ccy,
                    pct=((cur_mrg - prev_mrg) / prev_mrg) if prev_mrg > 0 else None,
                )
                mrg_delta_txt = f"So với {cmp_window.prev_label}: {raw_delta}"
            else:
                mrg_cmp_lbl = "Kỳ so sánh: Chưa đủ dữ liệu"
                mrg_delta_txt, mrg_delta_tone = "Chọn ≥ 2 kỳ để đối chiếu", "neutral"
            mrg_sub = f"Phủ giá vốn: {margin_rows:,}/{row_count:,} dòng"

        margin_pct_display = fmt_metric_state(
            weighted_margin_pct,
            supported=has_margin,
            has_rows=row_count > 0 and margin_rows > 0,
            formatter=fmt_pct,
        )
        if not has_margin:
            mpct_cmp_lbl = "Kỳ so sánh: Chưa có giá gốc"
            mpct_delta_txt, mpct_delta_tone = "Chưa có dữ liệu lãi/vốn", "neutral"
            mpct_sub = ""
        else:
            if has_cmp_window and cur_wmrg is not None and prev_wmrg is not None:
                mpct_cmp_lbl = f"Kỳ {cmp_window.cur_label}: {fmt_pct(cur_wmrg)}"
                raw_delta, mpct_delta_tone = fmt_delta((cur_wmrg - prev_wmrg) * 100.0, is_pp=True)
                mpct_delta_txt = f"So với {cmp_window.prev_label}: {raw_delta}"
            else:
                mpct_cmp_lbl = "Kỳ so sánh: Chưa đủ dữ liệu"
                mpct_delta_txt, mpct_delta_tone = "Chọn ≥ 2 kỳ để đối chiếu", "neutral"
            mpct_sub = f"TB theo dòng: {fmt_pct(row_avg_margin_pct)}"

        if not has_rev:
            price_display = "Nguồn không hỗ trợ"
            price_cmp_lbl = "Không có tiền tệ"
            price_delta_txt, price_delta_tone = "Chỉ hiển thị sản lượng", "neutral"
            price_sub = ""
        elif uom_guard.is_multi_uom_blocked:
            price_display = "Cần chọn 1 ĐVT"
            price_cmp_lbl = f"Đang lẫn {uom_guard.uom_count} ĐVT"
            price_delta_txt, price_delta_tone = "Chọn 1 ĐVT để xem đơn giá", "warn"
            price_sub = ""
        else:
            price_display = fmt_metric_state(
                weighted_unit_price,
                supported=has_rev,
                has_rows=row_count > 0 and rev_rows > 0,
                formatter=lambda v: _format_money(v, ccy, to_vnd=to_vnd, compact=False),
            )
            if has_cmp_window and cur_wup is not None and prev_wup is not None:
                price_cmp_lbl = f"Kỳ {cmp_window.cur_label}: {_format_money(cur_wup, ccy, to_vnd=to_vnd, compact=False)}"
                raw_delta, price_delta_tone = fmt_delta(
                    (cur_wup - prev_wup) * ccy_mult,
                    unit=disp_ccy,
                    pct=((cur_wup - prev_wup) / prev_wup) if prev_wup > 0 else None,
                )
                price_delta_txt = f"So với {cmp_window.prev_label}: {raw_delta}"
            else:
                price_cmp_lbl = "Kỳ so sánh: Chưa đủ dữ liệu"
                price_delta_txt, price_delta_tone = "Chọn ≥ 2 kỳ để đối chiếu", "neutral"
            price_sub = f"Đơn vị: {disp_ccy}/{uom_note}" if disp_ccy else ""

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_kpi_card(
                "Doanh Thu",
                rev_display,
                vnd_rate_note(ccy, to_vnd) or (f"{ccy} · {rev_rows:,} dòng" if has_rev and ccy else ""),
                tag=disp_ccy or "N/A",
                accent=palette.primary,
                period_label=agg_period_label,
                compare_label=rev_cmp_lbl,
                delta_text=rev_delta_txt,
                delta_tone=rev_delta_tone,
                info_tooltip=f"Tổng doanh thu thực bán trong phạm vi lọc. Đơn giá BQ: {price_display}. Bật VNĐ (₫) ở thanh bên để quy đổi.",
            )
        with c2:
            render_kpi_card(
                "Sản Lượng",
                qty_display,
                qty_sub,
                tag=uom_guard.single_uom or "ĐVT",
                accent=palette.accent,
                period_label=agg_period_label,
                compare_label=qty_cmp_lbl,
                delta_text=qty_delta_txt,
                delta_tone=qty_delta_tone,
                info_tooltip=(
                    f"Tổng sản lượng bán ({uom_note}) · Số lượt dòng: {fmt_int(total_lines)} · CH-ngày: {fmt_int(active_sd)}. "
                    f"Đơn giá BQ: {price_display}. Số Đơn Hàng Duy Nhất: Chưa khả dụng ở grain SP×CH×Ngày."
                ),
            )
        with c3:
            render_kpi_card(
                "Lợi Nhuận Gộp",
                margin_display,
                mrg_sub,
                tag=disp_ccy or "N/A",
                accent=palette.primary_dark,
                period_label=agg_period_label,
                compare_label=mrg_cmp_lbl,
                delta_text=mrg_delta_txt,
                delta_tone=mrg_delta_tone,
                info_tooltip="Tiền lãi gộp = Doanh thu − Giá gốc hàng bán (chỉ hiển thị khi nguồn có dữ liệu giá vốn).",
            )
        with c4:
            render_kpi_card(
                "Tỷ Suất LN",
                margin_pct_display,
                mpct_sub,
                tag="Theo doanh thu",
                accent=palette.discrete[3],
                period_label=agg_period_label,
                compare_label=mpct_cmp_lbl,
                delta_text=mpct_delta_txt,
                delta_tone=mpct_delta_tone,
                info_tooltip="Biên lợi nhuận gia quyền = Tổng tiền lãi / Tổng doanh thu thực tế.",
            )

        st.markdown(
            f"<div class='pf-sr-only'>Số Đơn Hàng Duy Nhất: Chưa khả dụng | Số lượt bán theo dòng: {fmt_int(total_lines)} | "
            f"Cửa hàng-ngày có bán: {fmt_int(active_sd)} | Đơn Giá Bình Quân: {price_display} | "
            f"{price_cmp_lbl} | {price_delta_txt}</div>",
            unsafe_allow_html=True,
        )

        # 3. Row 2: Store Manager Product Share & Ranking (with Local Component Filters!)
        with st.container(border=True):
            render_chart_header(
                "Tỷ Trọng & Top Mặt Hàng",
                "",
                info_tooltip="Cho biết từng mặt hàng chiếm bao nhiêu % doanh thu/sản lượng trong cửa hàng hoặc cụm đang chọn, kèm số lượt dòng và biến động kỳ trước.",
            )
            fcol1, fcol2, fcol3, fcol4 = st.columns([3.2, 2.2, 3.8, 2.8])
            mix_metric_opts: list[str] = []
            if has_rev:
                mix_metric_opts.append("line_amount")
            if not uom_guard.is_multi_uom_blocked:
                mix_metric_opts.append("sold_qty")
            if has_margin:
                mix_metric_opts.append("margin_amount")
            if not mix_metric_opts:
                mix_metric_opts = ["line_amount" if has_rev else "sold_qty"]
            if st.session_state.get("p1_mix_metric") not in mix_metric_opts:
                st.session_state["p1_mix_metric"] = mix_metric_opts[0]

            with fcol1:
                mix_metric = st.selectbox(
                    "Thước đo",
                    options=mix_metric_opts,
                    format_func=lambda m: {
                        "line_amount": f"Doanh thu ({disp_ccy})" if disp_ccy else "Doanh thu",
                        "sold_qty": f"Sản lượng ({uom_note})",
                        "margin_amount": f"Lợi nhuận ({disp_ccy})" if disp_ccy else "Lợi nhuận",
                    }.get(m, m),
                    key="p1_mix_metric",
                )
            with fcol2:
                top_n = st.selectbox(
                    "Top N",
                    options=[10, 15, 25, 50],
                    index=0,
                    key="p1_mix_top_n",
                )
            with fcol3:
                mix_search = st.text_input(
                    "Tìm thuốc",
                    placeholder="Nhập tên thuốc...",
                    key="p1_mix_search",
                )
            with fcol4:
                st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
                if st.button("⚡ So sánh kỳ", key="p1_mix_jump_btn", width="stretch"):
                    navigate_to_compare_page()

            pm_sql, pm_params = sql_store_product_mix(
                schema,
                filters,
                cur_start=cmp_window.cur_start if cmp_window.valid else None,
                cur_end=cmp_window.cur_end if cmp_window.valid else None,
                prev_start=cmp_window.prev_start if cmp_window.valid else None,
                prev_end=cmp_window.prev_end if cmp_window.valid else None,
                search_text=mix_search,
            )
            pm_df = db.run_query_df(pm_sql, pm_params)

            if pm_df.empty:
                render_empty_state()
            else:
                pm_work = pm_df.copy()
                pm_work["prod_label"] = pm_work.apply(
                    lambda r: f"{r['product_name']} ({r['clean_uom']})" if r.get("clean_uom") else str(r["product_name"]),
                    axis=1,
                )
                is_money_mix = mix_metric in ("line_amount", "margin_amount")
                pm_work["_metric_val"] = pd.to_numeric(pm_work[mix_metric], errors="coerce").fillna(0.0)
                if is_money_mix:
                    pm_work["_metric_val"] = pm_work["_metric_val"] * ccy_mult
                pm_work = pm_work.sort_values("_metric_val", ascending=False)
                tot_mix = float(pm_work["_metric_val"].sum())
                pm_work["share_pct"] = (pm_work["_metric_val"] / tot_mix * 100.0) if tot_mix > 0 else 0.0

                # Calculate period % delta if comparison window is valid
                c_col_pm = "cur_rev" if (mix_metric != "sold_qty" and has_rev) else "cur_qty"
                p_col_pm = "prev_rev" if (mix_metric != "sold_qty" and has_rev) else "prev_qty"
                c_vals = pd.to_numeric(pm_work[c_col_pm], errors="coerce")
                p_vals = pd.to_numeric(pm_work[p_col_pm], errors="coerce")
                pm_work["cmp_pct"] = [
                    ((float(cv) - float(pv)) / float(pv) * 100.0) if (pd.notna(cv) and pd.notna(pv) and float(pv) > 0) else None
                    for cv, pv in zip(c_vals, p_vals)
                ]

                top_items = pm_work.head(int(top_n)).copy()
                rest_val = float(pm_work.iloc[int(top_n):]["_metric_val"].sum()) if len(pm_work) > int(top_n) else 0.0
                donut_rows = [
                    {"Nhóm": r["prod_label"], "Giá trị": float(r["_metric_val"]), "Tỷ trọng (%)": float(r["share_pct"])}
                    for _, r in top_items.iterrows()
                    if float(r["_metric_val"]) > 0
                ]
                if rest_val > 0:
                    donut_rows.append(
                        {
                            "Nhóm": f"Còn lại ({len(pm_work) - len(top_items)} SP)",
                            "Giá trị": rest_val,
                            "Tỷ trọng (%)": (rest_val / tot_mix * 100.0) if tot_mix > 0 else 0.0,
                        }
                    )
                donut_df = pd.DataFrame(donut_rows)

                col_donut, col_tbl = st.columns([4.8, 7.2], gap="medium")
                with col_donut:
                    if donut_df.empty:
                        render_empty_state()
                    else:
                        unit_lbl = disp_ccy if is_money_mix else (uom_guard.single_uom or "ĐVT")
                        fig_mix = px.pie(
                            donut_df,
                            names="Nhóm",
                            values="Giá trị",
                            hole=0.58,
                            color_discrete_sequence=list(palette.discrete),
                        )
                        fig_mix.update_traces(
                            textposition="inside",
                            textinfo="percent",
                            textfont_size=11,
                            hovertemplate=f"<b>%{{label}}</b><br>Giá trị: %{{value:,.0f}} {unit_lbl or ''}<br>Tỷ trọng: %{{percent}}<extra></extra>",
                        )
                        fig_mix.add_annotation(
                            text=f"<b>{fmt_compact(tot_mix)}</b><br><span style='font-size:11px;color:{palette.muted}'>{unit_lbl or 'Tổng'} · {len(pm_work):,} SP</span>",
                            x=0.5,
                            y=0.5,
                            showarrow=False,
                            font=dict(size=14, color=palette.ink),
                        )
                        style_plotly(fig_mix, palette, height=345, show_legend=False)
                        fig_mix.update_layout(margin=dict(l=8, r=8, t=10, b=10))
                        st.plotly_chart(fig_mix, width="stretch", theme=None, config=plotly_config())

                with col_tbl:
                    rev_col_lbl = f"Doanh thu ({disp_ccy})" if disp_ccy else "Doanh thu"
                    mrg_col_lbl = f"Lợi nhuận ({disp_ccy})" if disp_ccy else "Lợi nhuận"
                    rev_series = safe_round(pd.to_numeric(top_items["line_amount"], errors="coerce") * ccy_mult, 0 if to_vnd else 2)
                    mrg_series = safe_round(pd.to_numeric(top_items["margin_amount"], errors="coerce") * ccy_mult, 0 if to_vnd else 2)
                    tbl_data: dict[str, Any] = {
                        "Mặt hàng": top_items["prod_label"],
                        "Tỷ trọng (%)": safe_round(top_items["share_pct"], 2),
                        "Lượt bán (dòng)": top_items["line_count"],
                        "Sản lượng": safe_round(top_items["sold_qty"], 0),
                    }
                    if has_rev:
                        tbl_data[rev_col_lbl] = rev_series
                    if has_margin:
                        tbl_data[mrg_col_lbl] = mrg_series
                        tbl_data["Tỷ suất LN (%)"] = safe_round(top_items["weighted_margin_pct"], 2)
                    if cmp_window.valid:
                        tbl_data[f"So kỳ trước (%)"] = safe_round(top_items["cmp_pct"], 2)
                    top_disp_df = pd.DataFrame(tbl_data)
                    col_cfg: dict[str, Any] = {
                        "Tỷ trọng (%)": st.column_config.ProgressColumn(
                            format="%.2f%%",
                            min_value=0.0,
                            max_value=max(float(top_items["share_pct"].max() or 10.0), 1.0),
                        ),
                        "Lượt bán (dòng)": st.column_config.NumberColumn(format="%,d"),
                        "Sản lượng": st.column_config.NumberColumn(format="%,.0f"),
                    }
                    if has_rev:
                        col_cfg[rev_col_lbl] = st.column_config.NumberColumn(format="%,.0f" if to_vnd else "%,.2f")
                    if has_margin:
                        col_cfg[mrg_col_lbl] = st.column_config.NumberColumn(format="%,.0f" if to_vnd else "%,.2f")
                        col_cfg["Tỷ suất LN (%)"] = st.column_config.NumberColumn(format="%.2f%%")
                    if cmp_window.valid:
                        col_cfg["So kỳ trước (%)"] = st.column_config.NumberColumn(format="%+.2f%%")
                    st.dataframe(top_disp_df, width="stretch", hide_index=True, height=345, column_config=col_cfg)

        # 4. Row 3: Flexible Time-Grain Sales Trajectory (Whole Store OR Selected Individual Drugs!)
        with st.container(border=True):
            render_chart_header(
                "Xu Hướng Theo Thời Gian",
                "",
                info_tooltip="Chọn 1 hoặc nhiều mặt hàng thuốc để xem đường biến động bán ra theo Ngày / Tuần / Tháng / Quý. Bỏ trống = xem tổng cửa hàng kèm % tăng trưởng.",
            )
            avail_prod_names = pm_df["product_name"].dropna().drop_duplicates().tolist() if not pm_df.empty else []
            scol1, scol2, scol3 = st.columns([5.2, 3.8, 3.0])
            with scol1:
                sel_products = st.multiselect(
                    "Chọn thuốc (trống = tất cả)",
                    options=avail_prod_names,
                    placeholder="Chọn 1–5 loại thuốc...",
                    key="p1_selected_products",
                )
            with scol2:
                # Local grain defaults to global filter grain unless overridden
                if st.session_state.get("p1_series_grain") not in TIME_GRAIN_ORDER:
                    st.session_state["p1_series_grain"] = filters.time_grain if filters.time_grain in TIME_GRAIN_ORDER else "month"
                series_grain = st.segmented_control(
                    "Độ mịn",
                    options=list(TIME_GRAIN_ORDER),
                    format_func=lambda g: {"day": "Ngày", "week": "Tuần", "month": "Tháng", "quarter": "Quý"}[g],
                    key="p1_series_grain",
                ) or filters.time_grain or "month"
            with scol3:
                trend_metric_opts = ["line_amount"] if (has_rev and uom_guard.is_multi_uom_blocked and not sel_products) else (
                    (["sold_qty", "line_amount", "margin_amount"] if has_margin else ["sold_qty", "line_amount"]) if has_rev else ["sold_qty"]
                )
                if st.session_state.get("p1_trend_metric") not in trend_metric_opts:
                    st.session_state["p1_trend_metric"] = trend_metric_opts[0]
                selected_trend_metric = st.radio(
                    "Chỉ tiêu",
                    options=trend_metric_opts,
                    format_func=lambda m: {
                        "sold_qty": f"Sản lượng ({uom_guard.single_uom})" if uom_guard.single_uom else "Sản lượng",
                        "line_amount": f"Doanh thu ({disp_ccy})" if disp_ccy else "Doanh thu",
                        "margin_amount": f"Lợi nhuận ({disp_ccy})" if disp_ccy else "Lợi nhuận",
                    }.get(m, m),
                    horizontal=True,
                    key="p1_trend_metric",
                )

            if sel_products:
                ts_sql, ts_params = sql_time_series_by_grain(schema, filters, grain=series_grain, products=sel_products)
                ts_df = db.run_query_df(ts_sql, ts_params)
                if ts_df.empty:
                    render_empty_state()
                else:
                    ts_plot = ts_df.copy()
                    ts_plot["series_uom"] = ts_plot.apply(
                        lambda r: f"{r['series_name']} ({r['clean_uom']})" if r.get("clean_uom") else str(r["series_name"]),
                        axis=1,
                    )
                    if selected_trend_metric in ("line_amount", "margin_amount"):
                        ts_plot[selected_trend_metric] = pd.to_numeric(ts_plot[selected_trend_metric], errors="coerce") * ccy_mult
                        y_lbl = f"{'Doanh thu' if selected_trend_metric == 'line_amount' else 'Lợi nhuận'} ({disp_ccy or ''})".strip()
                    else:
                        y_lbl = "Sản lượng (theo ĐVT từng thuốc)"
                    fig_ts = px.line(
                        ts_plot,
                        x="period_date",
                        y=selected_trend_metric,
                        color="series_uom",
                        markers=series_grain != "day",
                        color_discrete_sequence=list(palette.discrete),
                    )
                    fig_ts.update_traces(
                        line=dict(width=2.4),
                        hovertemplate=f"<b>%{{fullData.name}}</b><br>Kỳ %{{x|%d/%m/%Y}}<br>{y_lbl}: %{{y:,.0f}}<extra></extra>",
                    )
                    style_plotly(
                        fig_ts,
                        palette,
                        height=345,
                        xaxis_title=time_grain_label(series_grain),
                        yaxis_title=y_lbl,
                    )
                    st.plotly_chart(fig_ts, width="stretch", theme=None, config=plotly_config())
            elif series_grain == "month":
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
                    is_money_tr = val_col in ("line_amount", "margin_amount")
                    plot_df = growth_df.copy()
                    if is_money_tr:
                        plot_df[val_col] = pd.to_numeric(plot_df[val_col], errors="coerce") * ccy_mult
                    y_bar_title = (
                        f"{'Doanh thu' if val_col == 'line_amount' else 'Lợi nhuận'} ({disp_ccy})"
                        if is_money_tr
                        else f"Sản lượng ({uom_note})"
                    )
                    plot_df["pct_plot"] = pd.to_numeric(plot_df[pct_col], errors="coerce") * 100.0
                    bar_colors = [
                        "#94a3b8" if not hd else ("#f59e0b" if part else palette.primary)
                        for hd, part in zip(plot_df["has_data"], plot_df["is_partial_month"])
                    ]
                    hover_txt = [
                        f"Kỳ {r['month_label']}<br>"
                        f"Giá trị: {fmt_compact(r[val_col]) if pd.notna(r[val_col]) else 'Không có dữ liệu'}<br>"
                        f"Số ngày bán: {int(r['active_days'])}/{int(r['calendar_days'])}<br>"
                        + (f"MoM tổng: {r['pct_plot']:+.2f}%" if pd.notna(r["pct_plot"]) else f"Trạng thái: {r[status_col]}")
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
                            name="Tăng trưởng MoM (%)",
                            mode="lines+markers",
                            connectgaps=False,
                            line=dict(color=palette.accent, width=2.4),
                            marker=dict(size=5.5),
                            hovertemplate="Kỳ %{x|%m/%Y}<br>Tăng trưởng MoM: %{y:+.2f}%<extra></extra>",
                        ),
                        secondary_y=True,
                    )
                    style_plotly(fig, palette, height=345, xaxis_title="Tháng")
                    fig.update_yaxes(title_text=y_bar_title, secondary_y=False)
                    fig.update_yaxes(title_text="Tăng trưởng MoM (%)", ticksuffix="%", secondary_y=True, showgrid=False)
                    st.plotly_chart(fig, width="stretch", theme=None, config=plotly_config())
            else:
                ts_sql, ts_params = sql_time_series_by_grain(schema, filters, grain=series_grain, products=())
                ts_df = db.run_query_df(ts_sql, ts_params)
                if ts_df.empty:
                    render_empty_state()
                else:
                    ts_plot = ts_df.copy()
                    is_money_tr = selected_trend_metric in ("line_amount", "margin_amount")
                    if is_money_tr:
                        ts_plot[selected_trend_metric] = pd.to_numeric(ts_plot[selected_trend_metric], errors="coerce") * ccy_mult
                        y_lbl = f"{'Doanh thu' if selected_trend_metric == 'line_amount' else 'Lợi nhuận'} ({disp_ccy})"
                    else:
                        y_lbl = f"Sản lượng ({uom_note})"
                    fig_grain = px.area(
                        ts_plot,
                        x="period_date",
                        y=selected_trend_metric,
                        color_discrete_sequence=[palette.primary],
                    )
                    fig_grain.update_traces(
                        line=dict(width=2.2),
                        hovertemplate=f"Kỳ %{{x|%d/%m/%Y}}<br>{y_lbl}: %{{y:,.0f}}<extra></extra>",
                    )
                    style_plotly(fig_grain, palette, height=345, show_legend=False, xaxis_title=time_grain_label(series_grain), yaxis_title=y_lbl)
                    st.plotly_chart(fig_grain, width="stretch", theme=None, config=plotly_config())

        # 5. Row 4: Clean Tabbed Breakdowns (Drivers, Country Mix, UOM/Brand, Multi-Source Audit)
        with st.container(border=True):
            render_chart_header(
                "Phân Rã Chi Tiết",
                "",
                info_tooltip="Tổng hợp phân rã tăng/giảm, cơ cấu quốc gia, bảng tách ĐVT/thương hiệu và đối chiếu 3 nguồn dữ liệu.",
            )
            t_drv, t_mix, t_uom_brand, t_sources = st.tabs(
                [
                    "Tăng / Giảm",
                    "Quốc gia",
                    "ĐVT & Thương hiệu" if uom_guard.is_multi_uom_blocked else "Thương hiệu",
                    "3 Nguồn",
                ]
            )

            with t_drv:
                if not cmp_window.valid or not cmp_window.cur_start or not cmp_window.prev_start:
                    render_empty_state(cmp_window.note or "Chưa đủ 2 kỳ để tính đóng góp biến động.")
                else:
                    dim_labels = {"country": "Quốc gia", "brand": "Thương hiệu", "product": "Sản phẩm"}
                    sel_dim = st.radio(
                        "Phân rã theo",
                        options=driver_options,
                        format_func=lambda k: dim_labels[k],
                        horizontal=True,
                        key="p1_driver_dim",
                    )
                    if sel_dim == default_dim_for_insight and not vd_raw.empty:
                        dv_raw = vd_raw.copy()
                    else:
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
                            combined = combined.sort_values("delta", ascending=True).copy()
                            d_mult = ccy_mult if use_rev_d else 1.0
                            combined["_delta_disp"] = combined["delta"] * d_mult
                            combined["_p_disp"] = combined[p_col] * d_mult
                            combined["_c_disp"] = combined[c_col] * d_mult
                            colors = [palette.primary if d >= 0 else "#dc2626" for d in combined["_delta_disp"]]
                            unit_lbl = (disp_ccy or ccy or "") if use_rev_d else (uom_guard.single_uom or "ĐVT")
                            fig_drv = go.Figure(
                                go.Bar(
                                    x=combined["_delta_disp"],
                                    y=combined["item"],
                                    orientation="h",
                                    marker_color=colors,
                                    text=[f"{d:+,.0f}" for d in combined["_delta_disp"]],
                                    textposition="outside",
                                    customdata=list(zip(combined["_p_disp"], combined["_c_disp"], combined["contrib_pp"].fillna(0.0))),
                                    hovertemplate=(
                                        "<b>%{y}</b><br>"
                                        f"Kỳ trước: %{{customdata[0]:,.0f}} {unit_lbl}<br>"
                                        f"Kỳ này: %{{customdata[1]:,.0f}} {unit_lbl}<br>"
                                        f"Chênh lệch: %{{x:+,.0f}} {unit_lbl}<br>"
                                        "Đóng góp: %{customdata[2]:+.2f} điểm %<extra></extra>"
                                    ),
                                )
                            )
                            style_plotly(fig_drv, palette, height=320, show_legend=False, xaxis_title=f"Chênh lệch ({unit_lbl})", yaxis_title="")
                            polish_diverging_bar(fig_drv, float(combined["_delta_disp"].abs().max()))
                            st.plotly_chart(fig_drv, width="stretch", theme=None, config=plotly_config())
                            tot_prev_cat = float(pd.to_numeric(dv[p_col], errors="coerce").fillna(0.0).sum()) * d_mult
                            tot_cur_cat = float(pd.to_numeric(dv[c_col], errors="coerce").fillna(0.0).sum()) * d_mult
                            pct_suffix = f", {((tot_cur_cat - tot_prev_cat) / tot_prev_cat * 100.0):+.2f}%" if tot_prev_cat > 0 else ""
                            st.markdown(
                                f"<div class='pf-sr-only'>Tính trên toàn bộ {len(dv):,} nhóm hợp lệ (kỳ trước {fmt_compact(tot_prev_cat)} → kỳ này {fmt_compact(tot_cur_cat)}{pct_suffix}).</div>",
                                unsafe_allow_html=True,
                            )

            with t_mix:
                ctry_sql, ctry_params = sql_sales_by_country(schema, filters)
                ctry_df = db.run_query_df(ctry_sql, ctry_params)
                if ctry_df.empty:
                    render_empty_state()
                else:
                    ctry_df = ctry_df.copy()
                    ctry_df["country_vi"] = ctry_df["country_code"].map(country_label)
                    pie_col = "line_amount" if (has_rev and uom_guard.is_multi_uom_blocked) else "sold_qty"
                    pie_vals = pd.to_numeric(ctry_df[pie_col], errors="coerce").fillna(0.0) * (ccy_mult if pie_col == "line_amount" else 1.0)
                    ctry_df["_pie_val"] = pie_vals
                    pie_title = f"Tổng DT ({disp_ccy})" if pie_col == "line_amount" else "Tổng SL"
                    total_sum = float(pie_vals.sum())
                    fig_donut = px.pie(
                        ctry_df,
                        names="country_vi",
                        values="_pie_val",
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
                    style_plotly(fig_donut, palette, height=330, show_legend=True)
                    fig_donut.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.04, xanchor="center", x=0.5))
                    st.plotly_chart(fig_donut, width="stretch", theme=None, config=plotly_config())

            with t_uom_brand:
                if uom_guard.is_multi_uom_blocked:
                    uom_sql, uom_params = sql_uom_breakdown(schema, filters)
                    uom_df = db.run_query_df(uom_sql, uom_params)
                    if uom_df.empty:
                        render_empty_state()
                    else:
                        top_uoms = uom_df["clean_uom"].dropna().head(4).tolist()
                        if top_uoms:
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
                        rev_h = f"Doanh thu ({disp_ccy})" if disp_ccy else "Doanh thu"
                        up_h = f"Đơn giá gia quyền ({disp_ccy})" if disp_ccy else "Đơn giá gia quyền"
                        uom_disp = pd.DataFrame(
                            {
                                "Đơn vị tính": uom_df["clean_uom"],
                                "Lượt bán (dòng)": uom_df["line_count"],
                                "CH-ngày": uom_df["active_store_days"],
                                "Sản lượng (riêng ĐVT)": safe_round(uom_df["sold_qty"], 0),
                                rev_h: safe_round(pd.to_numeric(uom_df["line_amount"], errors="coerce") * ccy_mult, 0 if to_vnd else 2),
                                up_h: safe_round(pd.to_numeric(uom_df["weighted_unit_price"], errors="coerce") * ccy_mult, 2),
                            }
                        )
                        st.dataframe(uom_disp, width="stretch", hide_index=True, height=280)
                else:
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
                        fig_bar.update_traces(textposition="outside", hovertemplate="Thương hiệu: %{y}<br>Sản lượng: %{x:,.0f}<extra></extra>")
                        style_plotly(fig_bar, palette, height=340, show_legend=False, xaxis_title=f"Sản lượng ({uom_note})", yaxis_title="")
                        polish_horizontal_bar(fig_bar, brand_df["brand_name"].tolist(), float(brand_df["sold_qty"].max()))
                        st.plotly_chart(fig_bar, width="stretch", theme=None, config=plotly_config())

            with t_sources:
                compare_all = st.toggle(
                    "Hiển thị toàn bộ 3 nguồn (bỏ qua lọc ngày/quốc gia của thanh bên)",
                    value=True,
                    key="p1_summary_all_tracks",
                )
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
                            "Lượt bán (dòng)": sum_df["line_count"],
                            "CH-ngày": sum_df["active_store_days"],
                            "Sản lượng (nếu 1 ĐVT)": [
                                None if int(r["distinct_uom_count"] or 0) > 1 or pd.isna(r["sold_qty"]) else round(float(r["sold_qty"]))
                                for _, r in sum_df.iterrows()
                            ],
                            "Doanh thu (tiền tệ gốc)": safe_round(sum_df["line_amount"], 2),
                            "Lợi nhuận (tiền tệ gốc)": safe_round(sum_df["margin_amount"], 2),
                        }
                    )
                    st.dataframe(display_df, width="stretch", hide_index=True, height=240)
                    render_csv_download(display_df, "doi_chieu_nguon_du_lieu.csv", key="p1_csv_summary")

    render_right_explanation_panel(
        drawer_col,
        page_key="p1",
        page_title="Cửa Hàng & Mặt Hàng",
        glossary_items=[
            ("Tỷ suất lợi nhuận (Biên LN gia quyền %)", "Tính bằng SUM(margin_amount) / SUM(line_amount) thực bán — món doanh thu lớn có trọng số cao hơn."),
            ("Số lượt bán vs Số đơn duy nhất", "Gold mirror ở grain SP × CH × Ngày nên chưa có mã hóa đơn duy nhất (`Chưa khả dụng`); một hóa đơn 3 món tính 3 lượt dòng."),
            ("Đơn giá bình quân & Đa ĐVT", "Đơn giá gia quyền = Tổng doanh thu / Tổng sản lượng. Nguồn IRPD có nhiều ĐVT chưa có `base_qty`, hãy chọn 1 ĐVT để so sản lượng/đơn giá."),
            ("Lũy kế lọc vs Kỳ so sánh", "Con số lớn trên thẻ áp dụng toàn khoảng ngày thanh bên; phần biến động đối chiếu 2 kỳ liền kề đủ ngày."),
            ("Quy đổi VNĐ (₫)", "Tính tham chiếu trên EUR / IDR theo tỷ giá quy ước; nguồn Serbia không có tiền tệ chỉ hiển thị sản lượng."),
        ],
    )


render_page(get_current_filters())
