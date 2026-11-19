"""Shared UI theme injection, KPI cards, Plotly styling, and export helpers."""

from __future__ import annotations

import html
from typing import Any, Sequence

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import DEFAULT_PALETTE_KEY, PALETTES, TRACK_META, ThemePalette, provenance_label


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
            margin-bottom: 14px;
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

        .pf-kpi-card {{
            background: {palette.card_bg};
            border: 1px solid #e4e9ef;
            border-top: 3px solid {palette.primary};
            border-radius: 12px;
            padding: 14px 16px 13px 16px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
            height: 100%;
            margin-bottom: 10px;
        }}

        .pf-kpi-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
        }}

        .pf-kpi-title {{
            font-size: 0.84rem;
            font-weight: 700;
            color: {palette.ink};
            line-height: 1.25;
        }}

        .pf-kpi-tag {{
            font-size: 0.7rem;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 6px;
            background: {palette.soft_bg};
            color: {palette.primary_dark};
            white-space: nowrap;
        }}

        .pf-kpi-value {{
            font-size: 1.85rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: {palette.ink};
            line-height: 1.15;
            margin: 4px 0;
        }}

        .pf-kpi-sub {{
            font-size: 0.77rem;
            color: {palette.muted};
            line-height: 1.35;
        }}

        .pf-card-head {{
            margin: 2px 0 8px 0;
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


def render_kpi_card(
    title: str,
    value: str,
    subtitle: str,
    *,
    tag: str | None = None,
    accent: str | None = None,
) -> None:
    palette = get_active_palette()
    border_color = accent or palette.primary
    tag_html = f'<span class="pf-kpi-tag">{html.escape(tag)}</span>' if tag else ""
    st.markdown(
        f"""
        <div class="pf-kpi-card" style="border-top-color: {html.escape(border_color)};">
          <div class="pf-kpi-top">
            <span class="pf-kpi-title">{html.escape(title)}</span>
            {tag_html}
          </div>
          <div class="pf-kpi-value">{html.escape(value)}</div>
          <div class="pf-kpi-sub">{html.escape(subtitle)}</div>
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
