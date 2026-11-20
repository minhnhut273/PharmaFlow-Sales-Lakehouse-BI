"""Shared UI theme injection, KPI cards, scope strips, insights, and Plotly helpers."""

from __future__ import annotations

import html
from typing import Any, Sequence

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (
    DEFAULT_PALETTE_KEY,
    PALETTES,
    TRACK_META,
    ThemePalette,
    country_label,
    provenance_label,
    temp_label,
    track_label,
)


def get_active_palette() -> ThemePalette:
    key = st.session_state.get("palette_key", DEFAULT_PALETTE_KEY)
    return PALETTES.get(key, PALETTES[DEFAULT_PALETTE_KEY])


def inject_theme_css(palette: ThemePalette) -> None:
    """Inject responsive PharmaFlow BI card and typography styles bound to selected palette."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

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
        }}

        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
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
            padding: 16px 20px;
            margin-bottom: 10px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
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

        .pf-insight-box {{
            background: {palette.card_bg};
            border: 1px solid {palette.border};
            border-left: 4px solid {palette.accent};
            border-radius: 10px;
            padding: 10px 16px;
            margin-bottom: 12px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        }}

        .pf-insight-title {{
            font-size: 0.85rem;
            font-weight: 750;
            color: {palette.ink};
            margin-bottom: 4px;
        }}

        .pf-insight-list {{
            margin: 0;
            padding-left: 18px;
            font-size: 0.82rem;
            color: {palette.ink};
            line-height: 1.5;
        }}

        .pf-insight-note {{
            margin-top: 5px;
            font-size: 0.74rem;
            color: {palette.muted};
        }}

        .pf-scope-strip {{
            font-size: 0.75rem;
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

        .pf-kpi-card {{
            background: {palette.card_bg};
            border: 1px solid #e4e9ef;
            border-top: 3px solid {palette.primary};
            border-radius: 12px;
            padding: 13px 15px 12px 15px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
            height: 100%;
            margin-bottom: 10px;
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
            font-size: 0.69rem;
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
        }}

        .pf-kpi-value {{
            font-size: 1.65rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            color: {palette.ink};
            line-height: 1.18;
            margin: 3px 0 4px 0;
        }}

        .pf-kpi-compare-box {{
            margin-top: 8px;
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
        }}

        .pf-kpi-delta {{
            display: inline-block;
            align-self: flex-start;
            font-size: 0.73rem;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 6px;
            margin-bottom: 2px;
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

        /* Tabs styling */
        button[data-baseweb="tab"] {{
            font-weight: 600;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: {palette.primary} !important;
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
    """Render top sheet header with provenance & currency badges."""
    pills_html: list[str] = []
    if dataset_track and dataset_track in TRACK_META:
        meta = TRACK_META[dataset_track]
        prov_cls = "pf-pill-observed" if meta.provenance_class == "OBSERVED" else "pf-pill-synthetic"
        pills_html.append(f'<span class="pf-pill {prov_cls}">{html.escape(provenance_label(meta.provenance_class))}</span>')
        ccy = meta.currency_code or "Không tiền tệ"
        pills_html.append(f'<span class="pf-pill">Tiền tệ: {html.escape(ccy)}</span>')
        pills_html.append(f'<span class="pf-pill">{html.escape(meta.short_vi)}</span>')

    for text, kind in extra_pills:
        cls = {
            "observed": "pf-pill pf-pill-observed",
            "synthetic": "pf-pill pf-pill-synthetic",
            "warn": "pf-pill pf-pill-warn",
        }.get(kind, "pf-pill")
        pills_html.append(f'<span class="{cls}">{html.escape(text)}</span>')

    st.markdown(
        f"""
        <div class="pf-page-header">
          <div class="pf-page-title-row">
            <h1 class="pf-page-title">{html.escape(title)}</h1>
            <div class="pf-badge-row">{''.join(pills_html)}</div>
          </div>
          <p class="pf-page-sub">{html.escape(subtitle)}</p>
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
    """Render concise active global & page-local filters bar for immediate scope transparency."""
    chips: list[str] = []
    chips.append(f"Nguồn: {track_label(filters.dataset_track)}")
    if filters.date_start and filters.date_end:
        chips.append(f"Ngày: {filters.date_start:%d/%m/%Y}–{filters.date_end:%d/%m/%Y}")
    if filters.countries:
        ctry_txt = ", ".join(country_label(c) for c in filters.countries[:3])
        if len(filters.countries) > 3:
            ctry_txt += f" (+{len(filters.countries) - 3})"
        chips.append(f"Quốc gia: {ctry_txt}")
    if filters.stores:
        st_txt = ", ".join(filters.stores[:2])
        if len(filters.stores) > 2:
            st_txt += f" (+{len(filters.stores) - 2})"
        chips.append(f"Cửa hàng: {st_txt}")
    if filters.clean_uoms:
        chips.append(f"ĐVT: {', '.join(filters.clean_uoms[:3])}{'...' if len(filters.clean_uoms) > 3 else ''}")
    else:
        chips.append("ĐVT: Tất cả")
    if filters.temp_bands:
        chips.append(f"Nhiệt độ: {', '.join(temp_label(t) for t in filters.temp_bands[:2])}{'...' if len(filters.temp_bands) > 2 else ''}")
    if compare_window is not None and getattr(compare_window, "valid", False):
        chips.append(f"So sánh: {compare_window.cur_label} vs {compare_window.prev_label}")

    global_html = "".join(f'<span class="pf-filter-chip">{html.escape(c)}</span>' for c in chips)
    local_html = "".join(
        f'<span class="pf-filter-chip pf-filter-chip-local">{html.escape(c)}</span>'
        for c in local_tags
        if c
    )
    st.markdown(
        f"""
        <div class="pf-filter-bar">
          <span><b>Phạm vi đang lọc:</b></span>
          {global_html}
          {local_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_scope_strip(text: str, *, kind: str = "default") -> None:
    cls = "pf-scope-strip pf-scope-strip-warn" if kind == "warn" else "pf-scope-strip"
    st.markdown(f'<div class="{cls}">{html.escape(text)}</div>', unsafe_allow_html=True)


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
    if not bullets and not note:
        return
    items = "".join(f"<li>{_md_bold_to_html(b)}</li>" for b in bullets if b)
    note_html = f'<div class="pf-insight-note">{html.escape(note)}</div>' if note else ""
    st.markdown(
        f"""
        <div class="pf-insight-box">
          <div class="pf-insight-title">{html.escape(title)}</div>
          <ul class="pf-insight-list">{items}</ul>
          {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(
    title: str,
    value: str,
    subtitle: str,
    *,
    tag: str | None = None,
    accent: str | None = None,
    delta_text: str | None = None,
    delta_tone: str = "neutral",
    period_label: str | None = None,
    compare_label: str | None = None,
) -> None:
    palette = get_active_palette()
    border_color = accent or palette.primary
    tag_html = f'<span class="pf-kpi-tag">{html.escape(tag)}</span>' if tag else ""
    period_html = f'<div class="pf-kpi-period">{html.escape(period_label)}</div>' if period_label else ""
    delta_cls = {
        "pos": "pf-kpi-delta pf-delta-pos",
        "neg": "pf-kpi-delta pf-delta-neg",
        "warn": "pf-kpi-delta pf-delta-warn",
    }.get(delta_tone, "pf-kpi-delta pf-delta-neutral")
    delta_html = f'<div class="{delta_cls}">{html.escape(delta_text)}</div>' if delta_text else ""

    if compare_label or period_label:
        cmp_val_html = f'<div class="pf-kpi-compare-val">{html.escape(compare_label)}</div>' if compare_label else ""
        compare_section = f'<div class="pf-kpi-compare-box">{cmp_val_html}{delta_html}</div>' if (compare_label or delta_html) else ""
        body_html = (
            f"{period_html}"
            f'<div class="pf-kpi-value">{html.escape(value)}</div>'
            f'<div class="pf-kpi-sub">{html.escape(subtitle)}</div>'
            f"{compare_section}"
        )
    else:
        body_html = (
            f'<div class="pf-kpi-value">{html.escape(value)}</div>'
            f"{delta_html}"
            f'<div class="pf-kpi-sub">{html.escape(subtitle)}</div>'
        )

    st.markdown(
        f"""
        <div class="pf-kpi-card" style="border-top-color: {html.escape(border_color)};">
          <div class="pf-kpi-top">
            <span class="pf-kpi-title">{html.escape(title)}</span>
            {tag_html}
          </div>
          {body_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chart_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="pf-card-head">
          <div class="pf-card-title">{html.escape(title)}</div>
          <div class="pf-card-sub">{html.escape(subtitle)}</div>
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
        font=dict(family="Inter, Segoe UI, sans-serif", size=12, color=palette.ink),
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
            font=dict(family="Inter, Segoe UI, sans-serif", size=12, color=palette.ink),
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
