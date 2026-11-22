"""Shared UI theme injection, KPI cards, scope strips, insights, and Plotly helpers."""

from __future__ import annotations

import html
import re
from typing import Any, Sequence

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    import pydeck as pdk
except ImportError:  # pragma: no cover - optional fallback to MapLibre
    pdk = None

from config import (
    DEFAULT_PALETTE_KEY,
    PALETTES,
    TRACK_META,
    ThemePalette,
    country_label,
    currency_display_unit,
    currency_multiplier,
    fmt_compact,
    fmt_currency,
    fmt_int,
    provenance_label,
    temp_label,
    time_grain_label,
    track_label,
    vnd_rate_note,
)


def get_active_palette() -> ThemePalette:
    key = st.session_state.get("palette_key", DEFAULT_PALETTE_KEY)
    return PALETTES.get(key, PALETTES[DEFAULT_PALETTE_KEY])


def inject_theme_css(palette: ThemePalette) -> None:
    """Inject responsive PharmaFlow BI card and typography styles bound to selected palette."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

        :root {{
            --pf-primary: {palette.primary};
            --pf-primary-dark: {palette.primary_dark};
            --pf-soft: {palette.soft_bg};
            --pf-border: {palette.border};
            --pf-accent: {palette.accent};
            --pf-page: {palette.page_bg};
            --pf-card: {palette.card_bg};
            --pf-ink: {palette.ink};
            --pf-muted: {palette.muted};
            --pf-font: {palette.font_family};
            --pf-mono: {palette.mono_family};
        }}

        html, body, [class*="css"] {{
            font-family: {palette.font_family};
            -webkit-font-smoothing: antialiased;
        }}

        .stApp {{
            background-color: {palette.page_bg};
            color: {palette.ink};
        }}

        section[data-testid="stSidebar"] {{
            background-color: #ffffff;
            border-right: 1px solid #e4e9ef;
        }}

        div[data-testid="stMainBlockContainer"] {{
            padding-top: 1.4rem;
            padding-bottom: 2.5rem;
            max-width: 1620px;
        }}

        /* Styled chart & section containers */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {palette.card_bg};
            border: 1px solid #e4e9ef !important;
            border-radius: 12px !important;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
            padding: 0.25rem 0.45rem;
        }}

        .pf-page-header {{
            background: {palette.card_bg};
            border: 1px solid #e4e9ef;
            border-left: 5px solid {palette.primary};
            border-radius: 12px;
            padding: 10px 16px;
            margin-bottom: 8px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        }}

        .pf-sr-only {{
            display: none !important;
        }}

        .pf-page-title-wrap {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}

        .pf-page-title-row {{
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
        }}

        .pf-page-title {{
            margin: 0;
            font-size: 1.55rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            color: {palette.ink};
            line-height: 1.2;
        }}

        .pf-page-sub {{
            margin: 6px 0 0 0;
            color: {palette.muted};
            font-size: 0.9rem;
            line-height: 1.45;
        }}

        .pf-badge-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            align-items: center;
        }}

        .pf-pill {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 650;
            border: 1px solid {palette.border};
            background: {palette.soft_bg};
            color: {palette.primary_dark};
        }}

        .pf-pill-observed {{
            background: #e7f5f2;
            border-color: #99e2d2;
            color: #065f56;
        }}

        .pf-pill-synthetic {{
            background: #eef2ff;
            border-color: #c7d2fe;
            color: #3730a3;
        }}

        .pf-pill-warn {{
            background: #fffbeb;
            border-color: #fde68a;
            color: #92400e;
        }}

        .pf-filter-bar {{
            background: {palette.card_bg};
            border: 1px solid #e4e9ef;
            border-radius: 10px;
            padding: 8px 14px;
            margin-bottom: 10px;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 6px;
            font-size: 0.78rem;
            color: {palette.muted};
        }}

        .pf-filter-chip {{
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            border-radius: 6px;
            background: #f1f5f9;
            border: 1px solid #e2e8f0;
            color: {palette.ink};
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .pf-filter-chip-local {{
            background: {palette.soft_bg};
            border-color: {palette.border};
            color: {palette.primary_dark};
        }}

        .pf-compact-insight {{
            background: {palette.card_bg};
            border: 1px solid #e4e9ef;
            border-radius: 8px;
            padding: 5px 12px;
            margin: 2px 0 8px 0;
            font-size: 0.78rem;
            color: {palette.muted};
        }}

        .pf-compact-insight > summary {{
            cursor: pointer;
            font-weight: 600;
            color: {palette.primary_dark};
            list-style: none;
            user-select: none;
        }}

        .pf-compact-insight > summary::-webkit-details-marker {{
            display: none;
        }}

        .pf-compact-insight[open] {{
            border-left: 3px solid {palette.accent};
            padding: 8px 12px;
        }}

        .pf-insight-list {{
            margin: 6px 0 0 0;
            padding-left: 18px;
            font-size: 0.8rem;
            color: {palette.ink};
            line-height: 1.48;
        }}

        .pf-insight-note {{
            margin-top: 4px;
            font-size: 0.73rem;
            color: {palette.muted};
        }}

        .pf-scope-strip {{
            font-size: 0.74rem;
            color: {palette.muted};
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 4px 9px;
            margin: 2px 0 8px 0;
            line-height: 1.4;
        }}

        .pf-scope-strip-warn {{
            background: #fffbeb;
            border-color: #fde68a;
            color: #92400e;
        }}

        .pf-kpi-right {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            flex-shrink: 0;
        }}

        .pf-info-badge {{
            position: relative;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 19px;
            height: 19px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            font-style: normal;
            background: {palette.soft_bg};
            color: {palette.primary_dark};
            border: 1px solid {palette.border};
            cursor: help;
            flex-shrink: 0;
            transition: background-color 0.12s ease, color 0.12s ease;
        }}

        .pf-info-badge:hover {{
            background: {palette.primary};
            color: #ffffff;
            border-color: {palette.primary};
        }}

        .pf-info-badge[data-tooltip]:hover::after {{
            content: attr(data-tooltip);
            position: absolute;
            top: 132%;
            right: 0;
            z-index: 9999;
            width: max-content;
            max-width: 290px;
            white-space: normal;
            padding: 8px 10px;
            border-radius: 8px;
            background: #0f172a;
            color: #f8fafc;
            font-family: var(--pf-font);
            font-size: 0.74rem;
            font-weight: 500;
            line-height: 1.42;
            text-align: left;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.25);
            pointer-events: none;
        }}

        .pf-drawer-panel {{
            background: {palette.card_bg};
            border: 1px solid {palette.border};
            border-top: 4px solid {palette.accent};
            border-radius: 12px;
            padding: 14px 16px;
            box-shadow: 0 6px 20px rgba(15, 23, 42, 0.08);
        }}

        .pf-drawer-heading {{
            font-size: 0.96rem;
            font-weight: 800;
            color: {palette.ink};
            margin-bottom: 6px;
        }}

        .pf-card-head-row {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 8px;
        }}

        .pf-kpi-card {{
            background: {palette.card_bg};
            border: 1px solid #e4e9ef;
            border-top: 3px solid {palette.primary};
            border-radius: 12px;
            padding: 11px 14px 10px 14px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
            height: 100%;
            min-height: 92px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            margin-bottom: 10px;
            transition: transform 0.14s ease, box-shadow 0.14s ease, border-color 0.14s ease;
        }}

        .pf-kpi-card:hover {{
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.07);
            border-color: {palette.border};
        }}

        .pf-kpi-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            margin-bottom: 5px;
        }}

        .pf-kpi-title {{
            font-size: 0.82rem;
            font-weight: 700;
            color: {palette.ink};
            line-height: 1.25;
        }}

        .pf-kpi-tag {{
            font-family: var(--pf-mono);
            font-size: 0.68rem;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 6px;
            background: {palette.soft_bg};
            color: {palette.primary_dark};
            white-space: nowrap;
        }}

        .pf-kpi-period {{
            font-size: 0.72rem;
            font-weight: 600;
            color: {palette.primary_dark};
            margin-bottom: 2px;
            font-variant-numeric: tabular-nums;
        }}

        .pf-kpi-value {{
            font-size: 1.65rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            color: {palette.ink};
            line-height: 1.18;
            margin: 3px 0 4px 0;
            font-variant-numeric: tabular-nums;
        }}

        .pf-kpi-compare-box {{
            margin-top: auto;
            padding-top: 7px;
            border-top: 1px dashed #dce4ec;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .pf-kpi-compare-val {{
            font-size: 0.76rem;
            font-weight: 700;
            color: {palette.ink};
            line-height: 1.3;
            font-variant-numeric: tabular-nums;
        }}

        .pf-kpi-delta {{
            display: inline-block;
            align-self: flex-start;
            font-size: 0.73rem;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 6px;
            margin-bottom: 2px;
            font-variant-numeric: tabular-nums;
        }}

        .pf-delta-pos {{
            background: #ecfdf5;
            color: #047857;
            border: 1px solid #a7f3d0;
        }}

        .pf-delta-neg {{
            background: #fef2f2;
            color: #b91c1c;
            border: 1px solid #fecaca;
        }}

        .pf-delta-warn {{
            background: #fffbeb;
            color: #92400e;
            border: 1px solid #fde68a;
        }}

        .pf-delta-neutral {{
            background: #f1f5f9;
            color: #475569;
            border: 1px solid #e2e8f0;
        }}

        .pf-kpi-sub {{
            font-size: 0.76rem;
            color: {palette.muted};
            line-height: 1.38;
        }}

        .pf-card-head {{
            margin: 2px 0 6px 0;
        }}

        .pf-card-title {{
            font-size: 1.02rem;
            font-weight: 750;
            color: {palette.ink};
            margin: 0;
            line-height: 1.3;
        }}

        .pf-card-sub {{
            font-size: 0.8rem;
            color: {palette.muted};
            margin: 3px 0 0 0;
            line-height: 1.35;
        }}

        .pf-sidebar-brand {{
            padding: 6px 2px 10px 2px;
            border-bottom: 1px solid #e4e9ef;
            margin-bottom: 10px;
        }}

        .pf-sidebar-title {{
            font-size: 1.1rem;
            font-weight: 800;
            color: {palette.primary_dark};
            margin: 0;
            letter-spacing: -0.02em;
        }}

        .pf-sidebar-meta {{
            font-size: 0.75rem;
            color: {palette.muted};
            margin-top: 3px;
        }}

        /* Tabs, buttons & WCAG 2.2 AA focus styling */
        button[data-baseweb="tab"] {{
            font-weight: 600;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: {palette.primary} !important;
        }}
        div.stButton > button {{
            border-radius: 8px;
            border: 1px solid #dce4ec;
            font-size: 0.8rem;
            font-weight: 600;
            padding: 0.32rem 0.62rem;
            transition: background-color 0.12s ease, border-color 0.12s ease, color 0.12s ease;
        }}
        div.stButton > button:hover {{
            background-color: {palette.soft_bg};
            border-color: {palette.primary};
            color: {palette.primary_dark};
        }}
        button:focus-visible, input:focus-visible, [tabindex]:focus-visible {{
            outline: 2px solid {palette.primary} !important;
            outline-offset: 2px !important;
        }}
        [data-testid="stDataFrame"] {{
            font-variant-numeric: tabular-nums;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(
    title: str,
    subtitle: str,
    *,
    dataset_track: str | None = None,
    extra_pills: Sequence[tuple[str, str]] = (),
) -> None:
    """Render minimal 1-line sheet header with title + ⓘ tooltip icon, keeping dataset pills in .pf-sr-only."""
    st.session_state["_page_scope_notes"] = []
    hidden_pills: list[str] = []
    if dataset_track and dataset_track in TRACK_META:
        meta = TRACK_META[dataset_track]
        prov_txt = provenance_label(meta.provenance_class)
        ccy = meta.currency_code or "Không tiền tệ"
        hidden_pills.extend([prov_txt, meta.short_vi, f"Tiền tệ: {ccy}"])

    for text, _kind in extra_pills:
        hidden_pills.append(str(text))

    info_badge = (
        f'<span class="pf-info-badge" data-tooltip="{html.escape(subtitle)}" title="{html.escape(subtitle)}">ⓘ</span>'
        if subtitle
        else ""
    )
    sr_parts = [subtitle] if subtitle else []
    sr_parts.extend(hidden_pills)
    sr_html = f'<div class="pf-sr-only">{" | ".join(html.escape(p) for p in sr_parts)}</div>' if sr_parts else ""

    st.markdown(
        f"""
        <div class="pf-page-header">
          <div class="pf-page-title-row">
            <div class="pf-page-title-wrap">
              <h1 class="pf-page-title">{html.escape(title)}</h1>
              {info_badge}
            </div>
          </div>
          {sr_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_active_filter_bar(
    filters: Any,
    *,
    compare_window: Any = None,
    local_tags: Sequence[str] = (),
) -> None:
    """Render ultra-short active filter chips visually, keeping full scope metadata screen-reader-only."""
    visible_chips: list[str] = []
    hidden_chips: list[str] = [f"Nguồn: {track_label(filters.dataset_track)}"]

    if filters.date_start and filters.date_end:
        visible_chips.append(f"{filters.date_start:%d/%m/%y}–{filters.date_end:%d/%m/%y}")
        hidden_chips.append(f"Ngày: {filters.date_start:%d/%m/%Y}–{filters.date_end:%d/%m/%Y}")
    if getattr(filters, "time_grain", None):
        hidden_chips.append(f"Độ mịn: {time_grain_label(filters.time_grain)}")
    if filters.countries:
        ctry_txt = ", ".join(country_label(c) for c in filters.countries[:2])
        if len(filters.countries) > 2:
            ctry_txt += f" (+{len(filters.countries) - 2})"
        visible_chips.append(ctry_txt)
        hidden_chips.append(f"Quốc gia: {ctry_txt}")
    if getattr(filters, "city_clusters", None):
        cl_txt = ", ".join(filters.city_clusters[:2])
        if len(filters.city_clusters) > 2:
            cl_txt += f" (+{len(filters.city_clusters) - 2})"
        visible_chips.append(f"Cụm: {cl_txt}")
    if filters.stores:
        st_txt = ", ".join(filters.stores[:2])
        if len(filters.stores) > 2:
            st_txt += f" (+{len(filters.stores) - 2})"
        visible_chips.append(st_txt)
    if filters.clean_uoms:
        uom_txt = f"ĐVT: {', '.join(filters.clean_uoms[:2])}{'...' if len(filters.clean_uoms) > 2 else ''}"
        visible_chips.append(uom_txt)
    else:
        hidden_chips.append("ĐVT: Tất cả")
    if filters.temp_bands:
        t_txt = ", ".join(temp_label(t) for t in filters.temp_bands[:2])
        visible_chips.append(t_txt)
    meta = TRACK_META.get(filters.dataset_track or "")
    if getattr(filters, "display_vnd", False) and meta and meta.currency_code:
        visible_chips.append("VNĐ (₫)")
        hidden_chips.append(f"Tiền tệ: VNĐ (₫ · {vnd_rate_note(meta.currency_code, True)})")
    if compare_window is not None and getattr(compare_window, "valid", False):
        visible_chips.append(f"{compare_window.cur_label} vs {compare_window.prev_label}")

    global_html = "".join(f'<span class="pf-filter-chip">{html.escape(c)}</span>' for c in visible_chips)
    local_html = "".join(
        f'<span class="pf-filter-chip pf-filter-chip-local">{html.escape(c)}</span>'
        for c in local_tags
        if c
    )
    sr_html = f'<span class="pf-sr-only">{" · ".join(html.escape(c) for c in hidden_chips)}</span>'
    st.markdown(
        f"""
        <div class="pf-filter-bar">
          {global_html}
          {local_html}
          {sr_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def toggle_info_drawer() -> None:
    st.session_state["ui_info_drawer_open"] = not bool(st.session_state.get("ui_info_drawer_open", False))


def navigate_to_compare_page(default_mode: str | None = None) -> None:
    if default_mode:
        st.session_state["f_compare_mode"] = default_mode
    st.session_state["p4_from_jump"] = True
    try:
        st.switch_page("pages/04_san_pham_atc.py")
    except Exception:
        pass


def render_top_action_bar(
    filters: Any,
    *,
    page_key: str,
    compare_window: Any = None,
    local_tags: Sequence[str] = (),
    show_compare_jump: bool = True,
) -> None:
    """Render concise active filter strip alongside Compare Jump & Right-Side Explanation Drawer controls."""
    col_bar, col_cmp, col_info = st.columns(
        [7.8, 2.2, 2.0] if show_compare_jump else [9.8, 0.2, 2.0],
        gap="small",
    )
    with col_bar:
        render_active_filter_bar(filters, compare_window=compare_window, local_tags=local_tags)
    if show_compare_jump:
        with col_cmp:
            if st.button(
                "⚡ So sánh kỳ",
                key=f"{page_key}_jump_compare",
                width="stretch",
                help="Mở trang So sánh Kỳ (Tuần vs Tuần, Tháng vs Tháng hoặc 2 khoảng ngày tự chọn)",
            ):
                navigate_to_compare_page()
    with col_info:
        is_open = bool(st.session_state.get("ui_info_drawer_open", False))
        st.button(
            "✕ Đóng" if is_open else "ⓘ Giải thích",
            key=f"{page_key}_toggle_drawer",
            width="stretch",
            on_click=toggle_info_drawer,
            help="Mở bảng giải thích công thức, tỷ giá quy đổi và ý nghĩa số liệu bên phải màn hình",
        )


def open_page_layout_columns() -> tuple[Any, Any | None]:
    """Return (main_col, right_drawer_col_or_none) based on the user's Info Drawer toggle."""
    if st.session_state.get("ui_info_drawer_open", False):
        main_col, drawer_col = st.columns([8.5, 3.5], gap="medium")
        return main_col, drawer_col
    return st.container(), None


def render_right_explanation_panel(
    drawer_col: Any,
    *,
    page_key: str,
    page_title: str,
    glossary_items: Sequence[tuple[str, str]] = (),
    extra_notes: Sequence[str] = (),
) -> None:
    """Render collapsible right-side drawer containing metric formulas and optional insights."""
    if drawer_col is None:
        return
    saved_insights = st.session_state.get("_page_info_panel") or {}
    scope_notes = st.session_state.get("_page_scope_notes") or []
    with drawer_col:
        with st.container(border=True):
            h_col, c_col = st.columns([4, 1.3])
            with h_col:
                st.markdown(f"<div class='pf-drawer-heading'>ⓘ Giải thích · {html.escape(page_title)}</div>", unsafe_allow_html=True)
            with c_col:
                st.button("✕", key=f"{page_key}_close_drawer", on_click=toggle_info_drawer, width="stretch")

            if glossary_items:
                for term, desc in glossary_items:
                    st.markdown(f"**{term}**  \n<span style='font-size:0.8rem;color:#475569'>{desc}</span>", unsafe_allow_html=True)

            bullets = saved_insights.get("bullets") or []
            if bullets:
                st.divider()
                st.markdown(f"**{saved_insights.get('title', 'Điểm dữ liệu tự động')}**")
                for b in bullets:
                    st.markdown(f"- {b}")

            combined_notes = [*extra_notes, *[n for n in scope_notes if n not in extra_notes]]
            if combined_notes:
                st.divider()
                for n in combined_notes:
                    st.caption(n)


def render_scope_strip(text: str, *, kind: str = "default") -> None:
    """Store scope provenance text for the Right Explanation Drawer without cluttering visual cards."""
    notes = st.session_state.setdefault("_page_scope_notes", [])
    if text and text not in notes:
        notes.append(text)
    st.markdown(f'<div class="pf-sr-only">{html.escape(text)}</div>', unsafe_allow_html=True)


def _md_bold_to_html(text: str) -> str:
    """Convert **bold** and `code` markers safely inside escaped HTML."""
    escaped = html.escape(text)
    parts = escaped.split("**")
    out: list[str] = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1 and idx < len(parts) - 1:
            out.append(f"<strong>{part}</strong>")
        else:
            out.append(part)
    joined = "".join(out)
    code_parts = joined.split("`")
    final_parts: list[str] = []
    for idx, part in enumerate(code_parts):
        if idx % 2 == 1 and idx < len(code_parts) - 1:
            final_parts.append(f"<code style='font-size:0.9em;background:#f1f5f9;padding:1px 5px;border-radius:4px;'>{part}</code>")
        else:
            final_parts.append(part)
    return "".join(final_parts)


def render_insight_box(title: str, bullets: Sequence[str], *, note: str | None = None) -> None:
    """Keep visual canvas completely clean by routing insights to the Right Panel while retaining DOM text for accessibility/tests."""
    if not bullets and not note:
        return
    st.session_state["_page_info_panel"] = {
        "title": title,
        "bullets": list(bullets),
        "note": note,
    }
    items = "".join(f"<li>{_md_bold_to_html(b)}</li>" for b in bullets if b)
    note_html = f'<div class="pf-insight-note">{html.escape(note)}</div>' if note else ""
    st.markdown(
        f"""
        <div class="pf-sr-only">
          <div>{html.escape(title)}</div>
          <ul class="pf-insight-list">{items}</ul>
          {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(
    title: str,
    value: str,
    subtitle: str = "",
    *,
    tag: str | None = None,
    accent: str | None = None,
    delta_text: str | None = None,
    delta_tone: str = "neutral",
    period_label: str | None = None,
    compare_label: str | None = None,
    info_tooltip: str | None = None,
) -> None:
    palette = get_active_palette()
    border_color = accent or palette.primary

    tooltip_parts = [
        p
        for p in (info_tooltip, period_label, compare_label, delta_text, subtitle)
        if p and str(p).strip()
    ]
    full_tooltip = " · ".join(str(p).strip() for p in tooltip_parts)
    info_html = (
        f'<span class="pf-info-badge" data-tooltip="{html.escape(full_tooltip)}" title="{html.escape(full_tooltip)}">ⓘ</span>'
        if full_tooltip
        else ""
    )

    delta_cls = {
        "pos": "pf-kpi-delta pf-delta-pos",
        "neg": "pf-kpi-delta pf-delta-neg",
        "warn": "pf-kpi-delta pf-delta-warn",
    }.get(delta_tone, "pf-kpi-delta pf-delta-neutral")

    if delta_text:
        short_delta = re.sub(r"^So với [^:]+:\s*", "", delta_text).strip()
        bottom_html = f'<div class="{delta_cls}">{html.escape(short_delta)}</div>'
    elif subtitle:
        bottom_html = f'<div class="pf-kpi-sub">{html.escape(subtitle)}</div>'
    else:
        bottom_html = ""

    sr_parts = [p for p in (period_label, compare_label, delta_text, subtitle, tag) if p]
    sr_html = f'<div class="pf-sr-only">{" | ".join(html.escape(str(p)) for p in sr_parts)}</div>' if sr_parts else ""

    st.markdown(
        f"""
        <div class="pf-kpi-card" style="border-top-color: {html.escape(border_color)};">
          <div class="pf-kpi-top">
            <span class="pf-kpi-title">{html.escape(title)}</span>
            {info_html}
          </div>
          <div class="pf-kpi-value">{html.escape(value)}</div>
          {bottom_html}
          {sr_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chart_header(
    title: str,
    subtitle: str = "",
    *,
    info_tooltip: str | None = None,
) -> None:
    merged_tooltip = " · ".join(str(x).strip() for x in (info_tooltip, subtitle) if x and str(x).strip())
    info_html = (
        f'<span class="pf-info-badge" data-tooltip="{html.escape(merged_tooltip)}" title="{html.escape(merged_tooltip)}">ⓘ</span>'
        if merged_tooltip
        else ""
    )
    sr_html = f'<span class="pf-sr-only">{html.escape(subtitle)}</span>' if subtitle else ""
    st.markdown(
        f"""
        <div class="pf-card-head">
          <div class="pf-card-head-row">
            <div class="pf-card-title">{html.escape(title)}</div>
            {info_html}
          </div>
          {sr_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_plotly(
    fig: go.Figure,
    palette: ThemePalette,
    *,
    height: int = 360,
    show_legend: bool = True,
    margin: dict[str, int] | None = None,
    xaxis_title: str | None = None,
    yaxis_title: str | None = None,
) -> go.Figure:
    """Apply consistent PharmaFlow BI typography, colors, and hover polish."""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=palette.font_family, size=12, color=palette.ink),
        margin=margin or dict(l=14, r=14, t=18, b=16),
        showlegend=show_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=11, color=palette.muted),
        ),
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor=palette.border,
            font=dict(family=palette.font_family, size=12, color=palette.ink),
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor="#dce3eb",
        tickfont=dict(size=11, color=palette.muted),
        title_font=dict(size=12, color=palette.ink),
        automargin=True,
    )
    fig.update_yaxes(
        gridcolor="#eef2f6",
        zerolinecolor="#dce3eb",
        tickfont=dict(size=11, color=palette.muted),
        title_font=dict(size=12, color=palette.ink),
        automargin=True,
    )
    if xaxis_title is not None:
        fig.update_xaxes(title_text=xaxis_title)
    if yaxis_title is not None:
        fig.update_yaxes(title_text=yaxis_title)
    return fig


def render_csv_download(df: pd.DataFrame, filename: str, *, key: str, label: str = "Tải CSV") -> None:
    if df.empty:
        return
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=label,
        data=csv_bytes,
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def render_empty_state(message: str = "Không có dữ liệu phù hợp với bộ lọc hiện tại.") -> None:
    st.info(message)


def plotly_config(*, display_mode_bar: bool = False) -> dict[str, Any]:
    return {"displayModeBar": display_mode_bar, "responsive": True}


def polish_horizontal_bar(
    fig: go.Figure,
    categories_desc: Sequence[str],
    max_x: float | None,
    *,
    right_margin: int = 44,
) -> go.Figure:
    """Place highest-ranked category at the top of Y-axis and prevent right-edge text clipping."""
    asc = list(reversed(list(categories_desc)))
    fig.update_yaxes(categoryorder="array", categoryarray=asc)
    if max_x is not None and float(max_x) > 0:
        fig.update_xaxes(range=[0, float(max_x) * 1.22])
    fig.update_traces(cliponaxis=False)
    cur_margin = fig.layout.margin.to_plotly_json() if fig.layout.margin else {}
    cur_margin["r"] = max(int(cur_margin.get("r") or 14), right_margin)
    fig.update_layout(margin=cur_margin)
    return fig


def polish_vertical_bar_headroom(fig: go.Figure, max_y: float | None) -> go.Figure:
    """Add Y-axis headroom so outside data labels on vertical bars never clip."""
    if max_y is not None and float(max_y) > 0:
        fig.update_yaxes(range=[0, float(max_y) * 1.18])
    fig.update_traces(cliponaxis=False)
    return fig


def polish_diverging_bar(
    fig: go.Figure,
    max_abs: float | None,
    *,
    min_bound: float = 1.0,
    pad_factor: float = 1.38,
    right_margin: int = 34,
) -> go.Figure:
    """Keep diverging horizontal bar labels inside long bars / padded outside short bars cleanly."""
    bound = max(float(max_abs or 0.0), float(min_bound)) * pad_factor
    fig.update_xaxes(range=[-bound, bound], zeroline=True, zerolinewidth=1.4)
    fig.update_yaxes(automargin=True)
    fig.update_traces(textposition="auto", cliponaxis=False)
    cur_margin = fig.layout.margin.to_plotly_json() if fig.layout.margin else {}
    cur_margin["r"] = max(int(cur_margin.get("r") or 14), right_margin)
    fig.update_layout(margin=cur_margin)
    return fig


def render_street_map(
    df: pd.DataFrame,
    *,
    mode: str = "store",
    map_engine: str = "maplibre",
    size_col: str = "line_amount",
    color_col: str = "weighted_margin_pct",
    tile_style: str = "carto-voyager",
    palette: ThemePalette,
    ccy_label: str | None = "EUR",
    to_vnd: bool = False,
    height: int = 440,
) -> None:
    """Render an interactive street-tile map (MapLibre / Google-style 2D or PyDeck 3D) over stores or city clusters."""
    if df is None or df.empty:
        render_empty_state("Không có tọa độ cửa hàng để hiển thị trên bản đồ.")
        return

    work = df.copy()
    work["map_lat"] = pd.to_numeric(work["map_lat"], errors="coerce")
    work["map_lon"] = pd.to_numeric(work["map_lon"], errors="coerce")
    work = work.dropna(subset=["map_lat", "map_lon"])
    if work.empty:
        render_empty_state("Không có tọa độ GPS hợp lệ.")
        return

    mult = currency_multiplier(ccy_label, to_vnd=to_vnd)
    disp_ccy = currency_display_unit(ccy_label, to_vnd=to_vnd) or ""

    if mode == "cluster":
        grp_cols = [c for c in ("city_cluster", "country_code") if c in work.columns]
        if not grp_cols:
            grp_cols = ["store_name"]
        agg_rows: list[dict[str, Any]] = []
        for keys, g in work.groupby(grp_cols, dropna=False):
            key_tuple = keys if isinstance(keys, tuple) else (keys,)
            cl_name = str(key_tuple[0] or "Chưa rõ")
            ctry = str(key_tuple[1]) if len(key_tuple) > 1 else ""
            rev_sum = float(pd.to_numeric(g.get("line_amount"), errors="coerce").fillna(0.0).sum()) if "line_amount" in g else 0.0
            mrg_sum = float(pd.to_numeric(g.get("margin_amount"), errors="coerce").fillna(0.0).sum()) if "margin_amount" in g else 0.0
            qty_sum = float(pd.to_numeric(g.get("sold_qty"), errors="coerce").fillna(0.0).sum()) if "sold_qty" in g else 0.0
            line_sum = int(pd.to_numeric(g.get("line_count"), errors="coerce").fillna(0).sum()) if "line_count" in g else 0
            sd_sum = int(pd.to_numeric(g.get("active_store_days"), errors="coerce").fillna(0).sum()) if "active_store_days" in g else 0
            wmrg = (mrg_sum / rev_sum * 100.0) if (rev_sum > 0 and "margin_amount" in g and pd.to_numeric(g["margin_amount"], errors="coerce").notna().any()) else None
            agg_rows.append(
                {
                    "display_name": f"{cl_name} ({len(g)} CH)",
                    "city_cluster": cl_name,
                    "country_code": ctry,
                    "store_count": len(g),
                    "map_lat": float(g["map_lat"].mean()),
                    "map_lon": float(g["map_lon"].mean()),
                    "sold_qty": qty_sum,
                    "line_amount": rev_sum * mult if ("line_amount" in g and pd.to_numeric(g["line_amount"], errors="coerce").notna().any()) else None,
                    "margin_amount": mrg_sum * mult if ("margin_amount" in g and pd.to_numeric(g["margin_amount"], errors="coerce").notna().any()) else None,
                    "weighted_margin_pct": wmrg,
                    "line_count": line_sum,
                    "active_store_days": sd_sum,
                    "avg_temp_mean": float(pd.to_numeric(g["avg_temp_mean"], errors="coerce").mean()) if "avg_temp_mean" in g else None,
                    "avg_precip_sum": float(pd.to_numeric(g["avg_precip_sum"], errors="coerce").mean()) if "avg_precip_sum" in g else None,
                }
            )
        plot_df = pd.DataFrame(agg_rows)
    else:
        plot_df = work.copy()
        plot_df["display_name"] = plot_df["store_name"].astype(str)
        plot_df["store_count"] = 1
        if "line_amount" in plot_df.columns:
            plot_df["line_amount"] = pd.to_numeric(plot_df["line_amount"], errors="coerce") * mult
        if "margin_amount" in plot_df.columns:
            plot_df["margin_amount"] = pd.to_numeric(plot_df["margin_amount"], errors="coerce") * mult

    size_series = pd.to_numeric(plot_df.get(size_col), errors="coerce").fillna(0.0).clip(lower=0.0)
    if float(size_series.max()) <= 0:
        size_series = pd.to_numeric(plot_df.get("sold_qty"), errors="coerce").fillna(1.0).clip(lower=1.0)
    plot_df["_size_val"] = size_series

    if color_col in plot_df.columns and pd.to_numeric(plot_df[color_col], errors="coerce").notna().any():
        plot_df["_color_val"] = pd.to_numeric(plot_df[color_col], errors="coerce")
        actual_color_col = "_color_val"
    else:
        plot_df["_color_val"] = plot_df["_size_val"]
        actual_color_col = "_color_val"

    lat_span = float(plot_df["map_lat"].max() - plot_df["map_lat"].min())
    lon_span = float(plot_df["map_lon"].max() - plot_df["map_lon"].min())
    max_span = max(lat_span, lon_span)
    if len(plot_df) == 1 or max_span < 0.08:
        zoom = 11.2
    elif max_span < 0.45:
        zoom = 8.8
    elif max_span < 3.0:
        zoom = 6.2
    elif max_span < 10.0:
        zoom = 4.6
    else:
        zoom = 3.8
    center_lat = float(plot_df["map_lat"].mean())
    center_lon = float(plot_df["map_lon"].mean())

    plot_df["rev_fmt"] = [
        f"{fmt_compact(v)} {disp_ccy}".strip() if pd.notna(v) else "—"
        for v in plot_df.get("line_amount", pd.Series([None] * len(plot_df)))
    ]
    plot_df["qty_fmt"] = [fmt_compact(v, decimals=0) if pd.notna(v) else "—" for v in plot_df.get("sold_qty", pd.Series([None] * len(plot_df)))]
    plot_df["mrg_fmt"] = [f"{float(v):.2f}%" if pd.notna(v) else "—" for v in plot_df.get("weighted_margin_pct", pd.Series([None] * len(plot_df)))]
    plot_df["temp_fmt"] = [f"{float(v):.1f} °C" if pd.notna(v) else "—" for v in plot_df.get("avg_temp_mean", pd.Series([None] * len(plot_df)))]
    plot_df["rain_fmt"] = [f"{float(v):.2f} mm" if pd.notna(v) else "—" for v in plot_df.get("avg_precip_sum", pd.Series([None] * len(plot_df)))]
    plot_df["country_vi"] = plot_df["country_code"].map(country_label) if "country_code" in plot_df.columns else ""

    if map_engine == "pydeck" and pdk is not None:
        max_s = max(float(plot_df["_size_val"].max()), 1.0)
        plot_df["_elev"] = (plot_df["_size_val"] / max_s) * (120_000.0 if zoom < 7 else 8_000.0)
        plot_df["_radius"] = 22_000 if zoom < 5.5 else (6_000 if zoom < 8.5 else 700)

        min_c = float(plot_df["_color_val"].min()) if plot_df["_color_val"].notna().any() else 0.0
        max_c = float(plot_df["_color_val"].max()) if plot_df["_color_val"].notna().any() else 1.0
        span_c = max(max_c - min_c, 1e-6)
        r_vals, g_vals, b_vals = [], [], []
        for cv in plot_df["_color_val"].fillna(min_c):
            t = max(0.0, min(1.0, (float(cv) - min_c) / span_c))
            # Smooth emerald-to-blue gradient
            r_vals.append(int(217 * (1.0 - t) + 8 * t))
            g_vals.append(int(119 * (1.0 - t) + 123 * t))
            b_vals.append(int(6 * (1.0 - t) + 113 * t))
        plot_df["_r"] = r_vals
        plot_df["_g"] = g_vals
        plot_df["_b"] = b_vals

        pdk_cols = [
            "display_name",
            "country_vi",
            "map_lat",
            "map_lon",
            "_elev",
            "_radius",
            "_r",
            "_g",
            "_b",
            "rev_fmt",
            "qty_fmt",
            "mrg_fmt",
            "temp_fmt",
            "rain_fmt",
        ]
        pdk_data = plot_df[pdk_cols].to_dict(orient="records")
        col_radius = max(180, int(plot_df["_radius"].iloc[0] * 0.5))

        deck = pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
            initial_view_state=pdk.ViewState(
                latitude=center_lat,
                longitude=center_lon,
                zoom=zoom,
                pitch=38,
                bearing=8,
            ),
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    data=pdk_data,
                    get_position=["map_lon", "map_lat"],
                    get_radius="_radius",
                    get_fill_color=["_r", "_g", "_b", 135],
                    pickable=True,
                ),
                pdk.Layer(
                    "ColumnLayer",
                    data=pdk_data,
                    get_position=["map_lon", "map_lat"],
                    get_elevation="_elev",
                    elevation_scale=1,
                    radius=col_radius,
                    get_fill_color=["_r", "_g", "_b", 220],
                    pickable=True,
                    auto_highlight=True,
                ),
            ],
            tooltip={
                "html": (
                    "<b>{display_name}</b> ({country_vi})<br/>"
                    "Doanh thu: {rev_fmt}<br/>"
                    "Sản lượng: {qty_fmt}<br/>"
                    "Tỷ suất LN: {mrg_fmt}<br/>"
                    "Nhiệt độ TB: {temp_fmt} · Mưa TB: {rain_fmt}"
                ),
                "style": {
                    "backgroundColor": "#0f172a",
                    "color": "#f8fafc",
                    "fontSize": "12px",
                    "padding": "8px 10px",
                    "borderRadius": "8px",
                },
            },
        )
        st.pydeck_chart(deck, width="stretch", height=height)
        return

    color_title_map = {
        "weighted_margin_pct": "Tỷ suất LN (%)",
        "avg_temp_mean": "Nhiệt độ TB (°C)",
        "avg_precip_sum": "Lượng mưa TB (mm)",
        "line_amount": f"Doanh thu ({disp_ccy})" if disp_ccy else "Doanh thu",
        "sold_qty": "Sản lượng",
    }
    fig_map = px.scatter_map(
        plot_df,
        lat="map_lat",
        lon="map_lon",
        size="_size_val",
        color=actual_color_col,
        hover_name="display_name",
        custom_data=["country_vi", "rev_fmt", "qty_fmt", "mrg_fmt", "temp_fmt", "rain_fmt", "store_count"],
        color_continuous_scale=list(palette.continuous_scale),
        size_max=28 if mode == "cluster" else 20,
        zoom=zoom,
        center=dict(lat=center_lat, lon=center_lon),
        map_style=tile_style,
    )
    fig_map.update_traces(
        hovertemplate=(
            "<b>%{hovertext}</b> (%{customdata[0]})<br>"
            "Số cửa hàng: %{customdata[6]}<br>"
            "Doanh thu: %{customdata[1]}<br>"
            "Sản lượng: %{customdata[2]}<br>"
            "Tỷ suất LN: %{customdata[3]}<br>"
            "Nhiệt độ TB: %{customdata[4]} · Mưa TB: %{customdata[5]}<extra></extra>"
        )
    )
    fig_map.update_coloraxes(colorbar_title_text=color_title_map.get(color_col, "Giá trị"))
    fig_map.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=palette.font_family, size=12, color=palette.ink),
    )
    st.plotly_chart(fig_map, width="stretch", theme=None, config={"displayModeBar": True, "scrollZoom": True, "responsive": True})
