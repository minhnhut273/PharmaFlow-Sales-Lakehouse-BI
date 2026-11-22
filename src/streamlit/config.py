"""Configuration, color palettes, dataset track metadata, and Vietnamese display maps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ThemePalette:
    key: str
    label: str
    primary: str
    primary_dark: str
    soft_bg: str
    border: str
    accent: str
    page_bg: str
    card_bg: str
    ink: str
    muted: str
    continuous_scale: tuple[str, ...]
    discrete: tuple[str, ...]
    font_family: str = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    mono_family: str = "'JetBrains Mono', 'Fira Code', monospace"


PALETTES: dict[str, ThemePalette] = {
    "pharmaflow": ThemePalette(
        key="pharmaflow",
        label="PharmaFlow Xanh Ngọc",
        primary="#087b71",
        primary_dark="#00685f",
        soft_bg="#e7f5f2",
        border="#cfe4df",
        accent="#285cb4",
        page_bg="#f4f6f9",
        card_bg="#ffffff",
        ink="#17263a",
        muted="#546477",
        continuous_scale=("#e7f5f2", "#8fd3c8", "#22a79a", "#087b71", "#054741"),
        discrete=(
            "#087b71",
            "#2563eb",
            "#d97706",
            "#dc2626",
            "#7c3aed",
            "#059669",
            "#db2777",
            "#475569",
        ),
    ),
    "aws_quick": ThemePalette(
        key="aws_quick",
        label="AWS Quick Tím Chàm",
        primary="#5b46e8",
        primary_dark="#4338ca",
        soft_bg="#eef2ff",
        border="#ddd6fe",
        accent="#0284c7",
        page_bg="#f6f7fb",
        card_bg="#ffffff",
        ink="#16191f",
        muted="#545b64",
        continuous_scale=("#ede9fe", "#a78bfa", "#7c3aed", "#5b46e8", "#312e81"),
        discrete=(
            "#5b46e8",
            "#0284c7",
            "#0f766e",
            "#d97706",
            "#db2777",
            "#15803d",
            "#9333ea",
            "#334155",
        ),
    ),
    "ocean": ThemePalette(
        key="ocean",
        label="Đại Dương Hiện Đại",
        primary="#1d4ed8",
        primary_dark="#1e3a8a",
        soft_bg="#eff6ff",
        border="#bfdbfe",
        accent="#0f766e",
        page_bg="#f3f6fb",
        card_bg="#ffffff",
        ink="#0f172a",
        muted="#475569",
        continuous_scale=("#dbeafe", "#60a5fa", "#2563eb", "#1d4ed8", "#1e3a8a"),
        discrete=(
            "#1d4ed8",
            "#0891b2",
            "#0f766e",
            "#f59e0b",
            "#dc2626",
            "#7c3aed",
            "#0284c7",
            "#475569",
        ),
    ),
    "warm": ThemePalette(
        key="warm",
        label="Hổ Phách Ấm",
        primary="#b45309",
        primary_dark="#78350f",
        soft_bg="#fffbeb",
        border="#fde68a",
        accent="#0f766e",
        page_bg="#faf7f2",
        card_bg="#ffffff",
        ink="#1c1917",
        muted="#57534e",
        continuous_scale=("#fef3c7", "#fbbf24", "#d97706", "#b45309", "#78350f"),
        discrete=(
            "#b45309",
            "#0f766e",
            "#1d4ed8",
            "#be123c",
            "#ca8a04",
            "#6d28d9",
            "#059669",
            "#44403c",
        ),
    ),
    "ant": ThemePalette(
        key="ant",
        label="Ant Enterprise (Xanh Lam B2B)",
        primary="#1677ff",
        primary_dark="#0958d9",
        soft_bg="#eff6ff",
        border="#bfdbfe",
        accent="#7c3aed",
        page_bg="#f5f7fa",
        card_bg="#ffffff",
        ink="#111827",
        muted="#4b5563",
        continuous_scale=("#eff6ff", "#93c5fd", "#3b82f6", "#1677ff", "#1e3a8a"),
        discrete=(
            "#1677ff",
            "#7c3aed",
            "#0d9488",
            "#d97706",
            "#dc2626",
            "#16a34a",
            "#db2777",
            "#475569",
        ),
        font_family="'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif",
        mono_family="'JetBrains Mono', monospace",
    ),
    "shadcn": ThemePalette(
        key="shadcn",
        label="Shadcn Minimal (Đơn Sắc Tinh Gọn)",
        primary="#0f172a",
        primary_dark="#020617",
        soft_bg="#f1f5f9",
        border="#e2e8f0",
        accent="#2563eb",
        page_bg="#f8fafc",
        card_bg="#ffffff",
        ink="#0f172a",
        muted="#64748b",
        continuous_scale=("#f1f5f9", "#cbd5e1", "#64748b", "#334155", "#0f172a"),
        discrete=(
            "#0f172a",
            "#2563eb",
            "#0d9488",
            "#d97706",
            "#dc2626",
            "#7c3aed",
            "#16a34a",
            "#64748b",
        ),
        font_family="'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        mono_family="'JetBrains Mono', monospace",
    ),
    "clean": ThemePalette(
        key="clean",
        label="Clean Analytics (Sáng & Thoáng)",
        primary="#2563eb",
        primary_dark="#1d4ed8",
        soft_bg="#eff6ff",
        border="#dbeafe",
        accent="#0891b2",
        page_bg="#f8fafc",
        card_bg="#ffffff",
        ink="#111827",
        muted="#475569",
        continuous_scale=("#eff6ff", "#93c5fd", "#3b82f6", "#2563eb", "#1e40af"),
        discrete=(
            "#2563eb",
            "#0891b2",
            "#7c3aed",
            "#16a34a",
            "#d97706",
            "#dc2626",
            "#db2777",
            "#475569",
        ),
        font_family="'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif",
        mono_family="'JetBrains Mono', monospace",
    ),
}

DEFAULT_PALETTE_KEY = "pharmaflow"
DEFAULT_TRACK = "ONYX_EU_SYNTHETIC"


@dataclass(frozen=True)
class TrackMeta:
    track_id: str
    source_name: str
    label_vi: str
    short_vi: str
    currency_code: str | None
    provenance_class: str
    has_revenue: bool
    has_margin: bool
    has_promo: bool
    has_manufacturer: bool
    multi_uom: bool


TRACK_META: dict[str, TrackMeta] = {
    "ONYX_EU_SYNTHETIC": TrackMeta(
        track_id="ONYX_EU_SYNTHETIC",
        source_name="SIMULATED_ONYX_DAILY_FACT_TO_POS",
        label_vi="ONYX Châu Âu — Mô phỏng (EUR)",
        short_vi="ONYX EU (EUR)",
        currency_code="EUR",
        provenance_class="SYNTHETIC",
        has_revenue=True,
        has_margin=True,
        has_promo=True,
        has_manufacturer=False,
        multi_uom=False,
    ),
    "IRPD_ID_OBSERVED": TrackMeta(
        track_id="IRPD_ID_OBSERVED",
        source_name="IRPD_PUBLISHER_REPORTED_POS",
        label_vi="IRPD Indonesia — Thực tế (IDR)",
        short_vi="IRPD Indonesia (IDR)",
        currency_code="IDR",
        provenance_class="OBSERVED",
        has_revenue=True,
        has_margin=False,
        has_promo=False,
        has_manufacturer=True,
        multi_uom=True,
    ),
    "SERBIA_RS_SYNTHETIC": TrackMeta(
        track_id="SERBIA_RS_SYNTHETIC",
        source_name="SIMULATED_PHARMA_SALES_ATC_SCALE10",
        label_vi="Serbia RS — Mô phỏng (Không tiền tệ)",
        short_vi="Serbia RS",
        currency_code=None,
        provenance_class="SYNTHETIC",
        has_revenue=False,
        has_margin=False,
        has_promo=False,
        has_manufacturer=False,
        multi_uom=False,
    ),
}

TEMP_BAND_ORDER: tuple[str, ...] = (
    "1. Cold (<10C)",
    "2. Cool (10-20C)",
    "3. Mild (20-27C)",
    "4. Warm (27-30C)",
    "5. Hot (>=30C)",
    "Unknown",
)

TEMP_BAND_VI: dict[str, str] = {
    "1. Cold (<10C)": "1. Lạnh (<10°C)",
    "2. Cool (10-20C)": "2. Mát (10–20°C)",
    "3. Mild (20-27C)": "3. Ôn hòa (20–27°C)",
    "4. Warm (27-30C)": "4. Ấm (27–30°C)",
    "5. Hot (>=30C)": "5. Nóng (≥30°C)",
    "Unknown": "Chưa rõ",
}

RAIN_REGIME_ORDER: tuple[str, ...] = (
    "1. Dry (0 mm)",
    "2. Light (0-5 mm)",
    "3. Moderate (5-20 mm)",
    "4. Heavy (>20 mm)",
    "Unknown",
)

RAIN_REGIME_VI: dict[str, str] = {
    "1. Dry (0 mm)": "1. Khô ráo (0 mm)",
    "2. Light (0-5 mm)": "2. Mưa nhẹ (0–5 mm)",
    "3. Moderate (5-20 mm)": "3. Mưa vừa (5–20 mm)",
    "4. Heavy (>20 mm)": "4. Mưa to (>20 mm)",
    "Unknown": "Chưa rõ",
}

HUMIDITY_BAND_ORDER: tuple[str, ...] = (
    "1. Low (<60%)",
    "2. Normal (60-80%)",
    "3. High (>80%)",
    "Unknown",
)

HUMIDITY_BAND_VI: dict[str, str] = {
    "1. Low (<60%)": "1. Thấp (<60%)",
    "2. Normal (60-80%)": "2. Trung bình (60–80%)",
    "3. High (>80%)": "3. Cao (>80%)",
    "Unknown": "Chưa rõ",
}

DOW_VI_BY_NUM: dict[int, str] = {
    1: "Thứ 2",
    2: "Thứ 3",
    3: "Thứ 4",
    4: "Thứ 5",
    5: "Thứ 6",
    6: "Thứ 7",
    7: "Chủ nhật",
}

WEEKEND_VI: dict[Any, str] = {
    False: "Ngày thường",
    True: "Cuối tuần",
    0: "Ngày thường",
    1: "Cuối tuần",
    "false": "Ngày thường",
    "true": "Cuối tuần",
}

TIME_GRAIN_ORDER: tuple[str, ...] = ("day", "week", "month", "quarter")
TIME_GRAIN_VI: dict[str, str] = {
    "day": "Theo Ngày",
    "week": "Theo Tuần",
    "month": "Theo Tháng",
    "quarter": "Theo Quý",
}

VND_REFERENCE_RATES: dict[str, float] = {
    "EUR": 27_500.0,
    "IDR": 1.60,
}

PROVENANCE_VI: dict[str, str] = {
    "OBSERVED": "Thực tế (OBSERVED)",
    "SYNTHETIC": "Mô phỏng (SYNTHETIC)",
    "UNVERIFIED": "Chưa xác minh (UNVERIFIED)",
}

COUNTRY_VI: dict[str, str] = {
    "DE": "Đức (DE)",
    "FR": "Pháp (FR)",
    "IT": "Ý (IT)",
    "BE": "Bỉ (BE)",
    "PL": "Ba Lan (PL)",
    "NL": "Hà Lan (NL)",
    "ES": "Tây Ban Nha (ES)",
    "AT": "Áo (AT)",
    "ID": "Indonesia (ID)",
    "RS": "Serbia (RS)",
}

ISO2_TO_ISO3: dict[str, str] = {
    "DE": "DEU",
    "FR": "FRA",
    "IT": "ITA",
    "BE": "BEL",
    "PL": "POL",
    "NL": "NLD",
    "ES": "ESP",
    "AT": "AUT",
    "ID": "IDN",
    "RS": "SRB",
}

ATC_CODE_VI: dict[str, str] = {
    "M01AB": "M01AB · NSAID axetic",
    "M01AE": "M01AE · NSAID propionic",
    "N02BA": "N02BA · Salicylate",
    "N02BE": "N02BE · Giảm đau hạ sốt",
    "N05B": "N05B · Giải lo âu",
    "N05C": "N05C · An thần gây ngủ",
    "R03": "R03 · Hen & hô hấp",
    "R06": "R06 · Kháng histamin",
}

TEMP_BAND_VI_TO_RAW = {v: k for k, v in TEMP_BAND_VI.items()}
RAIN_REGIME_VI_TO_RAW = {v: k for k, v in RAIN_REGIME_VI.items()}


def track_label(track: str | None) -> str:
    if not track:
        return "Chưa xác định"
    meta = TRACK_META.get(track)
    return meta.label_vi if meta else str(track)


def country_label(code: str | None) -> str:
    if not code:
        return "Chưa rõ"
    return COUNTRY_VI.get(code, str(code))


def provenance_label(prov: str | None) -> str:
    if not prov:
        return "Chưa rõ"
    return PROVENANCE_VI.get(str(prov).upper(), str(prov))


def temp_label(band: str | None) -> str:
    if not band:
        return "Chưa rõ"
    return TEMP_BAND_VI.get(band, str(band))


def rain_label(regime: str | None) -> str:
    if not regime:
        return "Chưa rõ"
    return RAIN_REGIME_VI.get(regime, str(regime))


def humidity_label(band: str | None) -> str:
    if not band:
        return "Chưa rõ"
    return HUMIDITY_BAND_VI.get(band, str(band))


def weekend_label(val: Any) -> str:
    if val is None:
        return "Chưa rõ"
    return WEEKEND_VI.get(val, WEEKEND_VI.get(str(val).lower(), str(val)))


def atc_label(code: str | None, fallback_name: str | None = None) -> str:
    if code and code in ATC_CODE_VI:
        return ATC_CODE_VI[code]
    if fallback_name:
        return f"{fallback_name} ({code})" if code else str(fallback_name)
    return str(code or "Khác")


def time_grain_label(grain: str | None) -> str:
    if not grain:
        return TIME_GRAIN_VI["month"]
    return TIME_GRAIN_VI.get(str(grain), str(grain))


def extract_city_cluster(store_name: str | None) -> str:
    txt = str(store_name or "").strip()
    if not txt:
        return "Chưa rõ"
    if " HealthPoint" in txt:
        return txt.split(" HealthPoint", 1)[0].strip() or txt
    return txt


def currency_multiplier(currency_code: str | None, to_vnd: bool = False) -> float:
    if not to_vnd or not currency_code:
        return 1.0
    return float(VND_REFERENCE_RATES.get(str(currency_code).upper(), 1.0))


def currency_display_unit(currency_code: str | None, to_vnd: bool = False) -> str | None:
    if not currency_code:
        return None
    return "₫" if to_vnd else str(currency_code)


def vnd_rate_note(currency_code: str | None, to_vnd: bool = False) -> str:
    if not to_vnd or not currency_code:
        return ""
    code = str(currency_code).upper()
    rate = VND_REFERENCE_RATES.get(code)
    if rate is None:
        return ""
    rate_str = f"{rate:,.0f}" if rate >= 10 else f"{rate:,.2f}"
    return f"Quy đổi tham chiếu: 1 {code} ≈ {rate_str} ₫"


def fmt_compact(value: float | int | None, *, decimals: int = 2) -> str:
    if value is None:
        return "—"
    v = float(value)
    if v != v:  # NaN
        return "—"
    abs_v = abs(v)
    if abs_v >= 1_000_000_000:
        return f"{v / 1_000_000_000:,.{decimals}f}B"
    if abs_v >= 1_000_000:
        return f"{v / 1_000_000:,.{decimals}f}M"
    if abs_v >= 1_000:
        return f"{v / 1_000:,.{decimals}f}K"
    if float(v).is_integer():
        return f"{int(v):,}"
    return f"{v:,.{decimals}f}"


def safe_round(series: pd.Series, decimals: int = 2) -> pd.Series:
    """Safely convert object/None Postgres columns before rounding to prevent NoneType.__round__ errors."""
    return pd.to_numeric(series, errors="coerce").round(decimals)


def fmt_int(value: float | int | None) -> str:
    if value is None:
        return "—"
    v = float(value)
    if v != v:
        return "—"
    return f"{round(v):,}"


def fmt_pct(value: float | None, *, decimals: int = 2, already_scaled: bool = False) -> str:
    if value is None:
        return "—"
    v = float(value)
    if v != v:
        return "—"
    pct = v if already_scaled else v * 100.0
    return f"{pct:.{decimals}f}%"


def fmt_currency(
    value: float | int | None,
    currency_code: str | None = None,
    *,
    compact: bool = True,
    to_vnd: bool = False,
    vnd_rate: float | None = None,
) -> str:
    if value is None:
        return "—"
    v = float(value)
    if v != v:
        return "—"
    if to_vnd:
        if not currency_code:
            return "—"
        rate = vnd_rate if vnd_rate is not None else currency_multiplier(currency_code, to_vnd=True)
        v = v * rate
        ccy_out = "₫"
    else:
        ccy_out = currency_code
    num = fmt_compact(v, decimals=2) if compact else f"{v:,.2f}"
    if ccy_out:
        return f"{num} {ccy_out}"
    return num


def fmt_delta(
    delta: float | int | None,
    *,
    unit: str | None = None,
    pct: float | None = None,
    decimals: int = 2,
    is_pp: bool = False,
) -> tuple[str, str]:
    """Format signed period delta + optional % change and return (label, tone)."""
    if delta is None:
        return "Chưa đủ 2 kỳ để so sánh", "neutral"
    d = float(delta)
    if d != d:
        return "Chưa đủ 2 kỳ để so sánh", "neutral"

    if abs(d) < 1e-12:
        tone = "neutral"
        sign = ""
    elif d > 0:
        tone = "pos"
        sign = "+"
    else:
        tone = "neg"
        sign = "−"

    if is_pp:
        base = f"{sign}{abs(d):.{decimals}f} điểm %"
    elif unit:
        base = f"{sign}{fmt_compact(abs(d), decimals=decimals)} {unit}"
    else:
        base = f"{sign}{fmt_compact(abs(d), decimals=decimals)}"

    if pct is not None and pct == pct and not is_pp:
        pct_sign = "+" if pct > 0 else ("−" if pct < 0 else "")
        return f"{base} ({pct_sign}{abs(pct) * 100:.2f}%)", tone
    return base, tone


def fmt_metric_state(
    value: float | int | None,
    *,
    supported: bool = True,
    has_rows: bool = True,
    formatter: Any = None,
    unsupported_text: str = "Nguồn không hỗ trợ",
    empty_text: str = "Không có dữ liệu",
) -> str:
    """Distinguish numeric zero, empty filter matches, and source-unsupported metrics."""
    if not supported:
        return unsupported_text
    if not has_rows:
        return empty_text
    if value is None:
        return empty_text
    v = float(value)
    if v != v:
        return empty_text
    if formatter is not None:
        return str(formatter(v))
    return fmt_compact(v)
