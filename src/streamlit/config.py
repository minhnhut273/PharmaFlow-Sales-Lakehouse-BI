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


def fmt_currency(value: float | int | None, currency_code: str | None = None, *, compact: bool = True) -> str:
    if value is None:
        return "—"
    v = float(value)
    if v != v:
        return "—"
    num = fmt_compact(v, decimals=2) if compact else f"{v:,.2f}"
    if currency_code:
        return f"{num} {currency_code}"
    return num
