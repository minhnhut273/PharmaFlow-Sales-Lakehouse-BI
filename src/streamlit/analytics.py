"""Deterministic business analytics, comparison periods, UOM guards, and rule-based insights."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Sequence

import pandas as pd

from config import TRACK_META, fmt_compact, fmt_currency, fmt_pct, rain_label, temp_label

SMALL_SAMPLE_STORE_DAYS = 30
COMPARE_MODE_ORDER: tuple[str, ...] = ("latest_full_month", "half_split", "yoy_latest")
COMPARE_MODE_LABELS: dict[str, str] = {
    "latest_full_month": "2 tháng đủ ngày gần nhất (MoM)",
    "half_split": "Nửa sau vs Nửa trước khoảng chọn",
    "yoy_latest": "12 tháng gần nhất vs 12 tháng trước (YoY)",
}


@dataclass(frozen=True)
class ComparisonWindow:
    valid: bool
    mode: str
    mode_label: str
    cur_start: date | None
    cur_end: date | None
    prev_start: date | None
    prev_end: date | None
    cur_label: str
    prev_label: str
    note: str = ""


@dataclass(frozen=True)
class UomGuard:
    is_multi_uom_blocked: bool
    uom_count: int
    uoms: tuple[str, ...]
    single_uom: str | None
    message: str


@dataclass(frozen=True)
class MatrixSourceMeta:
    track_id: str
    label_vi: str
    provenance_class: str
    provenance_vi: str
    currency_code: str
    matches_sidebar_track: bool
    scope_note: str


@dataclass(frozen=True)
class WatchlistResult:
    status: str  # "alerts" | "reference_low_margin" | "no_alerts" | "insufficient_data"
    df: pd.DataFrame
    total_matched: int
    displayed_count: int
    evaluated_count: int
    supports_margin: bool
    title: str
    subtitle: str
    empty_message: str = ""


def _month_bounds(ym: date) -> tuple[date, date]:
    last_day = calendar.monthrange(ym.year, ym.month)[1]
    return date(ym.year, ym.month, 1), date(ym.year, ym.month, last_day)


def _next_month(ym: date) -> date:
    if ym.month == 12:
        return date(ym.year + 1, 1, 1)
    return date(ym.year, ym.month + 1, 1)


def _prev_month(ym: date) -> date:
    if ym.month == 1:
        return date(ym.year - 1, 12, 1)
    return date(ym.year, ym.month - 1, 1)


def _month_partial_reason(
    ym: date,
    *,
    date_start: date | None,
    date_end: date | None,
    track_min_date: date | None,
    track_max_date: date | None,
) -> tuple[bool, str]:
    m_start, m_end = _month_bounds(ym)
    reasons: list[str] = []

    if date_start is not None:
        is_user_start_clip = (track_min_date is None) or (date_start > track_min_date)
        if is_user_start_clip and date_start > m_start:
            reasons.append(f"bộ lọc bắt đầu từ {date_start:%d/%m/%Y}")
    if date_end is not None:
        is_user_end_clip = (track_max_date is None) or (date_end < track_max_date)
        if is_user_end_clip and date_end < m_end:
            reasons.append(f"bộ lọc kết thúc tại {date_end:%d/%m/%Y}")

    if track_min_date is not None and m_start <= track_min_date <= m_end:
        if (track_min_date - m_start).days >= 3:
            reasons.append(f"dữ liệu nguồn bắt đầu từ {track_min_date:%d/%m/%Y}")
    if track_max_date is not None and m_start <= track_max_date <= m_end:
        if (m_end - track_max_date).days >= 3:
            reasons.append(f"dữ liệu nguồn kết thúc tại {track_max_date:%d/%m/%Y}")

    return bool(reasons), "; ".join(reasons)


def _coerce_month_list(available_months: Sequence[Any]) -> list[date]:
    months: list[date] = []
    seen: set[date] = set()
    for val in available_months:
        if val is None or pd.isna(val):
            continue
        if isinstance(val, pd.Timestamp):
            d = val.date()
        elif hasattr(val, "year") and hasattr(val, "month"):
            d = date(int(val.year), int(val.month), 1)
        else:
            d = pd.to_datetime(val).date().replace(day=1)
        if d not in seen:
            seen.add(d)
            months.append(d)
    months.sort()
    return months


def _calendar_months_between(start_d: date, end_d: date) -> list[date]:
    cur = date(start_d.year, start_d.month, 1)
    stop = date(end_d.year, end_d.month, 1)
    out: list[date] = []
    while cur <= stop:
        out.append(cur)
        cur = _next_month(cur)
    return out


def _half_split_window(eff_start: date, eff_end: date, note: str = "") -> ComparisonWindow:
    total_days = (eff_end - eff_start).days + 1
    if total_days < 2:
        return ComparisonWindow(
            valid=False,
            mode="half_split",
            mode_label=COMPARE_MODE_LABELS["half_split"],
            cur_start=None,
            cur_end=None,
            prev_start=None,
            prev_end=None,
            cur_label="—",
            prev_label="—",
            note="Cần tối thiểu 2 ngày trong khoảng lọc để chia 2 kỳ so sánh bằng nhau.",
        )
    half = total_days // 2
    cur_end = eff_end
    cur_start = cur_end - timedelta(days=half - 1)
    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=half - 1)
    base_note = f"Hai cửa sổ rời nhau cùng độ dài {half} ngày ({prev_start:%d/%m/%Y}–{prev_end:%d/%m/%Y} vs {cur_start:%d/%m/%Y}–{cur_end:%d/%m/%Y})."
    full_note = f"{note} {base_note}".strip()
    return ComparisonWindow(
        valid=True,
        mode="half_split",
        mode_label=COMPARE_MODE_LABELS["half_split"],
        cur_start=cur_start,
        cur_end=cur_end,
        prev_start=prev_start,
        prev_end=prev_end,
        cur_label=f"{cur_start:%d/%m/%y}–{cur_end:%d/%m/%y}",
        prev_label=f"{prev_start:%d/%m/%y}–{prev_end:%d/%m/%y}",
        note=full_note,
    )


def resolve_comparison_periods(
    date_start: date | None,
    date_end: date | None,
    *,
    mode: str = "latest_full_month",
    available_months: Sequence[Any] = (),
    track_min_date: date | None = None,
    track_max_date: date | None = None,
) -> ComparisonWindow:
    """Select compatible cur vs prev comparison windows, skipping partial boundary months."""
    avail_sorted = _coerce_month_list(available_months)
    eff_start = date_start or track_min_date or (avail_sorted[0] if avail_sorted else None)
    eff_end = date_end or track_max_date or (_month_bounds(avail_sorted[-1])[1] if avail_sorted else None)
    if eff_start is None or eff_end is None or eff_start > eff_end:
        return ComparisonWindow(
            valid=False,
            mode=mode,
            mode_label=COMPARE_MODE_LABELS.get(mode, mode),
            cur_start=None,
            cur_end=None,
            prev_start=None,
            prev_end=None,
            cur_label="—",
            prev_label="—",
            note="Chưa có khoảng ngày hợp lệ để xác định kỳ so sánh.",
        )

    if mode == "half_split":
        return _half_split_window(eff_start, eff_end)

    spine = _calendar_months_between(eff_start, eff_end)
    avail_set = set(avail_sorted) if avail_sorted else set(spine)

    full_months: list[date] = []
    skipped_notes: list[str] = []
    for ym in spine:
        if ym not in avail_set:
            continue
        is_part, reason = _month_partial_reason(
            ym,
            date_start=date_start,
            date_end=date_end,
            track_min_date=track_min_date,
            track_max_date=track_max_date,
        )
        if is_part:
            skipped_notes.append(f"Bỏ qua tháng thiếu ngày {ym:%m/%Y} ({reason}).")
        else:
            full_months.append(ym)

    full_set = set(full_months)

    if mode == "yoy_latest":
        best_end_ym: date | None = None
        for ym in reversed(full_months):
            ok = True
            cursor = ym
            for _ in range(24):
                if cursor not in full_set:
                    ok = False
                    break
                cursor = _prev_month(cursor)
            if ok:
                best_end_ym = ym
                break
        if best_end_ym is not None:
            cur_end_ym = best_end_ym
            cur_start_ym = cur_end_ym
            for _ in range(11):
                cur_start_ym = _prev_month(cur_start_ym)
            prev_end_ym = _prev_month(cur_start_ym)
            prev_start_ym = prev_end_ym
            for _ in range(11):
                prev_start_ym = _prev_month(prev_start_ym)
            _, cur_end = _month_bounds(cur_end_ym)
            cur_start, _ = _month_bounds(cur_start_ym)
            _, prev_end = _month_bounds(prev_end_ym)
            prev_start, _ = _month_bounds(prev_start_ym)
            return ComparisonWindow(
                valid=True,
                mode="yoy_latest",
                mode_label=COMPARE_MODE_LABELS["yoy_latest"],
                cur_start=cur_start,
                cur_end=cur_end,
                prev_start=prev_start,
                prev_end=prev_end,
                cur_label=f"{cur_start_ym:%m/%Y}–{cur_end_ym:%m/%Y}",
                prev_label=f"{prev_start_ym:%m/%Y}–{prev_end_ym:%m/%Y}",
                note=" ".join(skipped_notes),
            )
        fallback = resolve_comparison_periods(
            date_start,
            date_end,
            mode="latest_full_month",
            available_months=avail_sorted,
            track_min_date=track_min_date,
            track_max_date=track_max_date,
        )
        msg = "Chưa đủ 24 tháng đủ ngày liên tiếp để so sánh YoY 12×12 → chuyển sang 2 tháng đủ ngày gần nhất."
        return ComparisonWindow(
            valid=fallback.valid,
            mode=fallback.mode,
            mode_label=fallback.mode_label,
            cur_start=fallback.cur_start,
            cur_end=fallback.cur_end,
            prev_start=fallback.prev_start,
            prev_end=fallback.prev_end,
            cur_label=fallback.cur_label,
            prev_label=fallback.prev_label,
            note=f"{msg} {fallback.note}".strip(),
        )

    # Default: latest_full_month — two consecutive full months
    for ym in reversed(full_months):
        prev_ym = _prev_month(ym)
        if prev_ym in full_set:
            cur_start, cur_end = _month_bounds(ym)
            prev_start, prev_end = _month_bounds(prev_ym)
            return ComparisonWindow(
                valid=True,
                mode="latest_full_month",
                mode_label=COMPARE_MODE_LABELS["latest_full_month"],
                cur_start=cur_start,
                cur_end=cur_end,
                prev_start=prev_start,
                prev_end=prev_end,
                cur_label=f"T{ym.month:02d}/{ym.year}",
                prev_label=f"T{prev_ym.month:02d}/{prev_ym.year}",
                note=" ".join(skipped_notes),
            )

    return _half_split_window(
        eff_start,
        eff_end,
        note="Không đủ 2 tháng dương lịch trọn vẹn liên tiếp → tự động chuyển sang chia đôi khoảng ngày.",
    )


def compute_monthly_growth(
    df: pd.DataFrame,
    *,
    date_start: date | None = None,
    date_end: date | None = None,
    track_min_date: date | None = None,
    track_max_date: date | None = None,
) -> pd.DataFrame:
    """Compute true aggregate MoM % growth over a gap-aware monthly calendar spine."""
    columns = [
        "year_month",
        "month_label",
        "calendar_days",
        "active_days",
        "active_store_days",
        "line_count",
        "sold_qty",
        "line_amount",
        "margin_amount",
        "has_data",
        "is_partial_month",
        "partial_reason",
        "prev_sold_qty",
        "mom_qty_diff",
        "mom_qty_pct",
        "mom_status",
        "prev_line_amount",
        "mom_rev_diff",
        "mom_rev_pct",
        "mom_rev_status",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)

    work = df.copy()
    work["ym_date"] = pd.to_datetime(work["year_month"]).dt.date.map(lambda d: date(d.year, d.month, 1))
    spine_start = min(work["ym_date"])
    spine_end = max(work["ym_date"])
    spine = _calendar_months_between(spine_start, spine_end)

    by_ym = {}
    for _, r in work.iterrows():
        by_ym[r["ym_date"]] = r

    records: list[dict[str, Any]] = []
    for idx, ym in enumerate(spine):
        cal_days = calendar.monthrange(ym.year, ym.month)[1]
        is_part, reason = _month_partial_reason(
            ym,
            date_start=date_start,
            date_end=date_end,
            track_min_date=track_min_date,
            track_max_date=track_max_date,
        )
        row = by_ym.get(ym)
        if row is None:
            records.append(
                {
                    "year_month": ym,
                    "month_label": f"{ym:%m/%Y}",
                    "calendar_days": cal_days,
                    "active_days": 0,
                    "active_store_days": 0,
                    "line_count": 0,
                    "sold_qty": None,
                    "line_amount": None,
                    "margin_amount": None,
                    "has_data": False,
                    "is_partial_month": is_part,
                    "partial_reason": reason,
                    "prev_sold_qty": None,
                    "mom_qty_diff": None,
                    "mom_qty_pct": None,
                    "mom_status": "Không có dữ liệu",
                    "prev_line_amount": None,
                    "mom_rev_diff": None,
                    "mom_rev_pct": None,
                    "mom_rev_status": "Không có dữ liệu",
                }
            )
            continue

        sold_qty = None if pd.isna(row.get("sold_qty")) else float(row["sold_qty"])
        line_amount = None if pd.isna(row.get("line_amount")) else float(row["line_amount"])
        margin_amount = None if pd.isna(row.get("margin_amount")) else float(row["margin_amount"])
        line_count = int(row.get("line_count") or 0)
        active_days = int(row.get("active_days") or 0)
        active_store_days = int(row.get("active_store_days") or 0)
        has_data = line_count > 0 or (sold_qty is not None and sold_qty > 0)

        prev_rec = records[idx - 1] if idx > 0 else None
        prev_qty = prev_rec["sold_qty"] if prev_rec else None
        prev_rev = prev_rec["line_amount"] if prev_rec else None

        mom_qty_diff = None
        mom_qty_pct = None
        if not has_data:
            mom_status = "Không có dữ liệu"
        elif idx == 0:
            mom_status = "Kỳ đầu tiên"
        elif is_part:
            mom_status = "Tháng chưa đủ ngày (không tính % MoM)"
        elif not prev_rec or not prev_rec["has_data"]:
            mom_status = "Tháng trước thiếu dữ liệu"
        elif prev_rec["is_partial_month"]:
            mom_status = "Tháng trước chưa đủ ngày (không tính % MoM)"
        elif prev_qty is None or prev_qty <= 0:
            mom_status = "Mẫu số bằng 0"
        elif sold_qty is None:
            mom_status = "Không có dữ liệu"
        else:
            mom_qty_diff = sold_qty - prev_qty
            mom_qty_pct = mom_qty_diff / prev_qty
            mom_status = "Hợp lệ"

        mom_rev_diff = None
        mom_rev_pct = None
        if line_amount is None:
            mom_rev_status = "Nguồn không ghi nhận doanh thu"
        elif idx == 0:
            mom_rev_status = "Kỳ đầu tiên"
        elif is_part:
            mom_rev_status = "Tháng chưa đủ ngày (không tính % MoM)"
        elif not prev_rec or not prev_rec["has_data"] or prev_rev is None:
            mom_rev_status = "Tháng trước thiếu dữ liệu"
        elif prev_rec["is_partial_month"]:
            mom_rev_status = "Tháng trước chưa đủ ngày (không tính % MoM)"
        elif prev_rev <= 0:
            mom_rev_status = "Mẫu số bằng 0"
        else:
            mom_rev_diff = line_amount - prev_rev
            mom_rev_pct = mom_rev_diff / prev_rev
            mom_rev_status = "Hợp lệ"

        records.append(
            {
                "year_month": ym,
                "month_label": f"{ym:%m/%Y}",
                "calendar_days": cal_days,
                "active_days": active_days,
                "active_store_days": active_store_days,
                "line_count": line_count,
                "sold_qty": sold_qty,
                "line_amount": line_amount,
                "margin_amount": margin_amount,
                "has_data": has_data,
                "is_partial_month": is_part,
                "partial_reason": reason,
                "prev_sold_qty": prev_qty,
                "mom_qty_diff": mom_qty_diff,
                "mom_qty_pct": mom_qty_pct,
                "mom_status": mom_status,
                "prev_line_amount": prev_rev,
                "mom_rev_diff": mom_rev_diff,
                "mom_rev_pct": mom_rev_pct,
                "mom_rev_status": mom_rev_status,
            }
        )

    return pd.DataFrame(records, columns=columns)


def evaluate_uom_compatibility(
    track_id: str | None,
    selected_uoms: Sequence[str],
    available_uoms_in_scope: Sequence[str],
) -> UomGuard:
    """Enforce UOM compatibility when base_qty conversion contract is missing."""
    cleaned_avail = list(dict.fromkeys(str(u) for u in available_uoms_in_scope if u))
    cleaned_sel = list(dict.fromkeys(str(u) for u in selected_uoms if u))
    effective = cleaned_sel if cleaned_sel else cleaned_avail
    meta = TRACK_META.get(track_id or "")

    if len(effective) > 1 or (meta and meta.multi_uom and len(cleaned_sel) == 0 and len(cleaned_avail) != 1):
        uoms_tuple = tuple(effective)
        count = len(uoms_tuple) if uoms_tuple else 0
        return UomGuard(
            is_multi_uom_blocked=True,
            uom_count=count,
            uoms=uoms_tuple,
            single_uom=None,
            message=(
                f"Phạm vi đang lọc gồm {max(count, 2)} đơn vị tính khác nhau ({', '.join(uoms_tuple[:5])}{'...' if count > 5 else ''}) "
                "và chưa có hệ số quy đổi chung về cùng đơn vị chuẩn. Không thể cộng gộp sản lượng hay tính đơn giá bình quân xuyên ĐVT — "
                "hãy chọn 1 đơn vị tính hoặc xem bảng tách theo từng ĐVT bên dưới."
            ),
        )

    single = effective[0] if len(effective) == 1 else (cleaned_sel[0] if len(cleaned_sel) == 1 else None)
    return UomGuard(
        is_multi_uom_blocked=False,
        uom_count=1 if single else 0,
        uoms=(single,) if single else (),
        single_uom=single,
        message="",
    )


def compute_variance_and_contributions(
    df: pd.DataFrame,
    *,
    cur_col: str = "cur_val",
    prev_col: str = "prev_val",
    metric_supported: bool = True,
    total_cur_override: float | None = None,
    total_prev_override: float | None = None,
) -> pd.DataFrame:
    """Add period delta, %, additive contribution (percentage points), and mix shift (pp).

    When ``metric_supported`` is False, or when a row recorded sales lines in a period
    while the metric value itself is missing/null, the row is flagged rather than coerced
    to zero so zero sales, missing metric data, and unsupported metrics remain distinct.
    """
    if df is None or df.empty:
        out = df.copy() if df is not None else pd.DataFrame()
        for col in ("delta", "pct_change", "contrib_pp", "share_cur", "share_prev", "mix_shift_pp", "presence_status"):
            out[col] = pd.Series(dtype="float64" if col != "presence_status" else "object")
        return out

    out = df.copy()
    raw_cur = pd.to_numeric(out[cur_col], errors="coerce")
    raw_prev = pd.to_numeric(out[prev_col], errors="coerce")

    if not metric_supported:
        out[cur_col] = raw_cur
        out[prev_col] = raw_prev
        for col in ("delta", "pct_change", "contrib_pp", "share_cur", "share_prev", "mix_shift_pp"):
            out[col] = pd.Series([None] * len(out), index=out.index, dtype="float64")
        out["presence_status"] = "Nguồn không hỗ trợ chỉ số"
        return out

    has_line_cols = "cur_lines" in out.columns and "prev_lines" in out.columns and cur_col not in ("cur_lines", "prev_lines")
    if has_line_cols:
        cur_lines_s = pd.to_numeric(out["cur_lines"], errors="coerce").fillna(0.0)
        prev_lines_s = pd.to_numeric(out["prev_lines"], errors="coerce").fillna(0.0)
        missing_cur_mask = (cur_lines_s > 0) & raw_cur.isna()
        missing_prev_mask = (prev_lines_s > 0) & raw_prev.isna()
    else:
        missing_cur_mask = pd.Series(False, index=out.index)
        missing_prev_mask = pd.Series(False, index=out.index)

    cur_s = raw_cur.fillna(0.0)
    prev_s = raw_prev.fillna(0.0)
    out[cur_col] = cur_s.where(~missing_cur_mask, other=float("nan"))
    out[prev_col] = prev_s.where(~missing_prev_mask, other=float("nan"))

    total_cur = float(total_cur_override) if total_cur_override is not None else float(cur_s.where(~missing_cur_mask, 0.0).sum())
    total_prev = float(total_prev_override) if total_prev_override is not None else float(prev_s.where(~missing_prev_mask, 0.0).sum())

    deltas: list[float | None] = []
    pcts: list[float | None] = []
    contribs: list[float | None] = []
    shares_cur: list[float | None] = []
    shares_prev: list[float | None] = []
    mix_shifts: list[float | None] = []
    presences: list[str] = []

    for c_val, p_val, m_cur, m_prev in zip(cur_s, prev_s, missing_cur_mask, missing_prev_mask):
        if m_cur or m_prev:
            deltas.append(None)
            pcts.append(None)
            contribs.append(None)
            shares_cur.append(None)
            shares_prev.append(None)
            mix_shifts.append(None)
            presences.append("Thiếu dữ liệu chỉ số")
            continue

        c = float(c_val)
        p = float(p_val)
        d = c - p
        deltas.append(d)
        pcts.append((d / p) if p > 0 else None)
        contribs.append((d / total_prev) * 100.0 if total_prev > 0 else None)
        sc = (c / total_cur) if total_cur > 0 else None
        sp = (p / total_prev) if total_prev > 0 else None
        shares_cur.append(sc)
        shares_prev.append(sp)
        mix_shifts.append(((sc - sp) * 100.0) if (sc is not None and sp is not None) else None)

        if c > 0 and p > 0:
            presences.append("Cả 2 kỳ")
        elif c > 0 and p <= 0:
            presences.append("Mới phát sinh kỳ này")
        elif c <= 0 and p > 0:
            presences.append("Chỉ phát sinh kỳ trước")
        else:
            presences.append("Không phát sinh")

    out["delta"] = pd.Series(deltas, index=out.index, dtype="float64")
    out["pct_change"] = pd.Series(pcts, index=out.index, dtype="float64")
    out["contrib_pp"] = pd.Series(contribs, index=out.index, dtype="float64")
    out["share_cur"] = pd.Series(shares_cur, index=out.index, dtype="float64")
    out["share_prev"] = pd.Series(shares_prev, index=out.index, dtype="float64")
    out["mix_shift_pp"] = pd.Series(mix_shifts, index=out.index, dtype="float64")
    out["presence_status"] = presences
    return out


def flag_small_sample(store_days: int | float | None, *, threshold: int = SMALL_SAMPLE_STORE_DAYS) -> bool:
    if store_days is None or pd.isna(store_days):
        return True
    return int(store_days) < threshold


# ---------------------------------------------------------------------------
# Rule-Based Insights (Strict Distinction: Arithmetic Contribution != Cause)
# ---------------------------------------------------------------------------

def _fmt_signed(
    value: float | int,
    unit: str | None = None,
    *,
    is_pp: bool = False,
    decimals: int = 2,
) -> str:
    """Format a signed magnitude without ever emitting double-sign strings like '+-'."""
    v = float(value)
    sign = "+" if v > 0 else ("−" if v < 0 else "")
    if is_pp:
        return f"{sign}{abs(v):.{decimals}f} điểm %"
    mag = fmt_currency(abs(v), unit) if unit else fmt_compact(abs(v), decimals=decimals)
    return f"{sign}{mag}"


def build_overview_insights(
    *,
    meta_label: str,
    provenance_class: str,
    window: ComparisonWindow,
    metric_label: str,
    metric_unit: str | None,
    cur_total: float | None,
    prev_total: float | None,
    driver_df: pd.DataFrame,
    driver_name_col: str,
    uom_guard: UomGuard,
) -> list[str]:
    bullets: list[str] = []
    prov_tag = "Dữ liệu mô phỏng" if provenance_class == "SYNTHETIC" else "Quan sát thực tế"

    if window.valid and cur_total is not None and prev_total is not None and prev_total > 0:
        diff = cur_total - prev_total
        pct = diff / prev_total
        direction = "tăng" if diff > 0 else ("giảm" if diff < 0 else "đi ngang")
        fmt_cur = fmt_currency(cur_total, metric_unit) if metric_unit else fmt_compact(cur_total)
        fmt_prev = fmt_currency(prev_total, metric_unit) if metric_unit else fmt_compact(prev_total)
        bullets.append(
            f"**Biến động kỳ {window.cur_label} so với {window.prev_label} ({prov_tag}):** "
            f"{metric_label} {direction} **{_fmt_signed(diff, metric_unit)}** ({pct * 100:+.2f}%), từ {fmt_prev} lên {fmt_cur}."
        )
    elif window.note:
        bullets.append(f"**Kỳ so sánh ({meta_label}):** {window.note}")

    if driver_df is not None and not driver_df.empty and "delta" in driver_df.columns:
        valid_drv = driver_df.dropna(subset=["delta"])
        if not valid_drv.empty:
            pos_drv = valid_drv[valid_drv["delta"] > 0].sort_values("delta", ascending=False)
            neg_drv = valid_drv[valid_drv["delta"] < 0].sort_values("delta", ascending=True)
            parts: list[str] = []
            if not pos_drv.empty:
                top_pos = pos_drv.iloc[0]
                pp_txt = f" ({top_pos['contrib_pp']:+.2f} điểm %)" if pd.notna(top_pos.get("contrib_pp")) else ""
                parts.append(f"tăng mạnh nhất: **{top_pos[driver_name_col]}** ({_fmt_signed(top_pos['delta'], metric_unit)}{pp_txt})")
            if not neg_drv.empty:
                top_neg = neg_drv.iloc[0]
                pp_txt = f" ({top_neg['contrib_pp']:+.2f} điểm %)" if pd.notna(top_neg.get("contrib_pp")) else ""
                parts.append(f"giảm mạnh nhất: **{top_neg[driver_name_col]}** ({_fmt_signed(top_neg['delta'], metric_unit)}{pp_txt})")
            if parts:
                bullets.append(
                    f"**Đóng góp số học lớn nhất (không suy diễn nguyên nhân):** {'; '.join(parts)}."
                )
            else:
                bullets.append(
                    f"**Đóng góp biến động:** Toàn bộ nhóm trong phạm vi đang có chênh lệch bằng 0 giữa {window.prev_label} và {window.cur_label}."
                )

    if uom_guard.is_multi_uom_blocked:
        bullets.append(
            f"**Lưu ý đơn vị tính ({meta_label}):** Nguồn đang gồm **{uom_guard.uom_count} đơn vị tính** và chưa có hệ số quy đổi chung; dashboard tạm khóa cộng tổng sản lượng để tránh cộng gộp sai ĐVT."
        )
    elif provenance_class == "SYNTHETIC":
        bullets.append(
            "**Giới hạn dữ liệu nguồn:** Số liệu nguồn này là **dữ liệu mô phỏng**; chưa có dữ liệu đếm số đơn hàng duy nhất (mới có số dòng bán theo sản phẩm, cửa hàng và ngày)."
        )
    return bullets[:3]


def build_weather_insights(
    *,
    hm_df: pd.DataFrame,
    metric_col: str,
    metric_unit: str | None,
    metric_noun: str,
    provenance_class: str,
    active_store_days: int,
    possible_store_days: int,
) -> list[str]:
    bullets: list[str] = []
    if hm_df is not None and not hm_df.empty and metric_col in hm_df.columns:
        valid = hm_df.dropna(subset=[metric_col]).copy()
        adequate = valid[valid["active_store_days"].fillna(0) >= SMALL_SAMPLE_STORE_DAYS]
        if len(adequate) >= 2:
            hi = adequate.sort_values(metric_col, ascending=False).iloc[0]
            lo = adequate.sort_values(metric_col, ascending=True).iloc[0]
            hi_txt = fmt_currency(hi[metric_col], metric_unit) if metric_unit else f"{float(hi[metric_col]):,.2f}"
            lo_txt = fmt_currency(lo[metric_col], metric_unit) if metric_unit else f"{float(lo[metric_col]):,.2f}"
            hi_lbl = f"{temp_label(str(hi['temp_band']))} × {rain_label(str(hi['rain_regime']))}"
            lo_lbl = f"{temp_label(str(lo['temp_band']))} × {rain_label(str(lo['rain_regime']))}"
            if float(hi[metric_col]) == float(lo[metric_col]):
                bullets.append(
                    f"**Mối liên hệ quan sát (trên {len(adequate)} nhóm đạt ngưỡng sàng lọc cỡ mẫu n ≥ {SMALL_SAMPLE_STORE_DAYS} CH-ngày):** "
                    f"Các nhóm đủ mẫu đang có cùng mức {metric_noun} **{hi_txt}**."
                )
            else:
                diff_pct_txt = ""
                if float(lo[metric_col]) > 0:
                    diff_pct = (float(hi[metric_col]) - float(lo[metric_col])) / float(lo[metric_col]) * 100.0
                    diff_pct_txt = f" (chênh {diff_pct:+.1f}%)"
                bullets.append(
                    f"**Mối liên hệ quan sát (trên {len(adequate)} nhóm đạt ngưỡng sàng lọc cỡ mẫu n ≥ {SMALL_SAMPLE_STORE_DAYS} CH-ngày):** "
                    f"Nhóm `{hi_lbl}` đạt {metric_noun} **{hi_txt}** (n={int(hi['active_store_days']):,}), "
                    f"cao hơn nhóm `{lo_lbl}` ở mức **{lo_txt}** (n={int(lo['active_store_days']):,}){diff_pct_txt}."
                )
        else:
            bullets.append(
                f"**Chưa đủ 2 nhóm đạt ngưỡng sàng lọc cỡ mẫu (n ≥ {SMALL_SAMPLE_STORE_DAYS} CH-ngày) để so sánh:** "
                f"Hiện chỉ có **{len(adequate)}/{len(valid)}** ô Nhiệt độ × Mức mưa đạt mức tối thiểu này, nên hệ thống không xếp hạng chênh lệch."
            )
        small_cnt = int((valid["active_store_days"].fillna(0) < SMALL_SAMPLE_STORE_DAYS).sum())
        if small_cnt > 0:
            bullets.append(
                f"**Lưu ý sàng lọc cỡ mẫu:** Có **{small_cnt}** ô dưới ngưỡng {SMALL_SAMPLE_STORE_DAYS} cửa hàng-ngày "
                "(đây là quy tắc sàng lọc độ phủ quan sát, không phải bằng chứng ý nghĩa thống kê hay tác động nhân quả)."
            )

    cov_pct = (active_store_days / possible_store_days * 100.0) if possible_store_days > 0 else None
    cov_txt = f" ({cov_pct:.1f}% của {possible_store_days:,} CH × ngày trong phạm vi lọc)" if cov_pct is not None else ""
    prov_note = "Dữ liệu đang xem thuộc nhóm **mô phỏng**" if provenance_class == "SYNTHETIC" else "Dữ liệu đang xem là **quan sát thực tế**"
    bullets.append(
        f"**Phạm vi quan sát & độ phủ:** Chỉ tính ngày có phát sinh bán (tổng **{active_store_days:,}** cửa hàng-ngày{cov_txt}); **không bao gồm ngày bán bằng 0**. {prov_note}, chỉ phản ánh mối liên hệ quan sát chứ chưa kết luận quan hệ nhân quả."
    )
    return bullets[:3]


def resolve_matrix_source_meta(
    matrix_df: pd.DataFrame | None,
    *,
    active_track: str | None,
    default_track: str = "ONYX_EU_SYNTHETIC",
) -> MatrixSourceMeta:
    """Resolve provenance, currency, and filter scope for the store matrix from its own query."""
    def _first_nonempty(col: str) -> str | None:
        if matrix_df is None or matrix_df.empty or col not in matrix_df.columns:
            return None
        vals = matrix_df[col].dropna().astype(str).str.strip()
        vals = vals[vals != ""]
        return str(vals.iloc[0]) if not vals.empty else None

    resolved_track = _first_nonempty("dataset_track") or default_track
    fallback_meta = TRACK_META.get(resolved_track) or TRACK_META.get(default_track)

    prov = _first_nonempty("provenance_class") or (fallback_meta.provenance_class if fallback_meta else "SYNTHETIC")
    ccy = _first_nonempty("currency_code") or (fallback_meta.currency_code if fallback_meta and fallback_meta.currency_code else "EUR")
    prov_vi = "Mô phỏng" if prov == "SYNTHETIC" else "Thực tế"

    if resolved_track == "ONYX_EU_SYNTHETIC":
        label_vi = "ONYX Châu Âu — Mô phỏng"
    elif fallback_meta:
        label_vi = f"{fallback_meta.short_vi} — {prov_vi}"
    else:
        label_vi = f"{resolved_track} — {prov_vi}"

    matches = resolved_track == active_track
    if matches:
        scope_note = "Áp dụng đầy đủ bộ lọc ngày, quốc gia, cửa hàng, ĐVT và nhiệt độ của thanh bên."
    else:
        scope_note = (
            f"Phần tham chiếu riêng từ nguồn {label_vi} ({ccy}); "
            "không áp dụng bộ lọc ngày/quốc gia/cửa hàng/ĐVT/nhiệt độ của nguồn đang chọn ở thanh bên."
        )

    return MatrixSourceMeta(
        track_id=resolved_track,
        label_vi=label_vi,
        provenance_class=prov,
        provenance_vi=prov_vi,
        currency_code=ccy,
        matches_sidebar_track=matches,
        scope_note=scope_note,
    )


def build_store_watchlist(
    store_var_df: pd.DataFrame | None,
    matrix_df: pd.DataFrame | None,
    *,
    window: ComparisonWindow,
    supports_margin: bool,
    cur_col: str,
    prev_col: str,
    max_alert_rows: int = 20,
    max_reference_rows: int = 10,
    max_non_margin_rows: int = 15,
) -> WatchlistResult:
    """Classify store watchlist state explicitly: alerts vs low-margin reference vs no alerts vs insufficient data."""
    if supports_margin:
        if not window.valid or store_var_df is None or store_var_df.empty or matrix_df is None or matrix_df.empty:
            return WatchlistResult(
                status="insufficient_data",
                df=pd.DataFrame(),
                total_matched=0,
                displayed_count=0,
                evaluated_count=0,
                supports_margin=True,
                title="Cửa Hàng Cần Xem Xét (Chưa Đủ Dữ Liệu)",
                subtitle="Cần đủ dữ liệu 2 kỳ so sánh và biên lợi nhuận để đánh giá tiêu chí cảnh báo.",
                empty_message="Chưa đủ dữ liệu so sánh 2 kỳ hoặc dữ liệu biên lợi nhuận để đánh giá.",
            )

        left_cols = [c for c in ("store_code", "store_name", "country_code", "line_amount", "weighted_margin_pct", "line_count") if c in matrix_df.columns]
        right_cols = [c for c in ("store_code", "delta", "pct_change", "mrg_pp_delta", "presence_status", cur_col, prev_col) if c in store_var_df.columns]
        merged_w = matrix_df[left_cols].merge(store_var_df[right_cols], on="store_code", how="left")
        if merged_w.empty:
            return WatchlistResult(
                status="insufficient_data",
                df=pd.DataFrame(),
                total_matched=0,
                displayed_count=0,
                evaluated_count=0,
                supports_margin=True,
                title="Cửa Hàng Cần Xem Xét (Chưa Đủ Dữ Liệu)",
                subtitle="Không ghép được cửa hàng giữa kỳ so sánh và ma trận biên lợi nhuận.",
                empty_message="Chưa có cửa hàng đủ dữ liệu để đánh giá trong phạm vi lọc.",
            )

        med_rev = float(pd.to_numeric(matrix_df["line_amount"], errors="coerce").median())
        med_mrg = float(pd.to_numeric(matrix_df["weighted_margin_pct"], errors="coerce").median())
        reasons: list[str] = []
        for _, r in merged_w.iterrows():
            flags: list[str] = []
            rev_v = float(r.get("line_amount") or 0.0) if pd.notna(r.get("line_amount")) else 0.0
            mrg_v = float(r.get("weighted_margin_pct") or 0.0) if pd.notna(r.get("weighted_margin_pct")) else None
            if rev_v >= med_rev and mrg_v is not None and mrg_v < med_mrg:
                flags.append("DT ≥ trung vị · Biên LN < trung vị")
            if pd.notna(r.get("pct_change")) and r.get("presence_status") == "Cả 2 kỳ" and float(r["pct_change"]) <= -0.15:
                flags.append("Giảm ≥ 15% kỳ so sánh")
            if pd.notna(r.get("mrg_pp_delta")) and float(r["mrg_pp_delta"]) <= -1.5:
                flags.append("Biên LN giảm ≥ 1.5 điểm %")
            reasons.append("; ".join(flags))

        merged_w["Lý do cần xem xét"] = reasons
        flagged = merged_w[merged_w["Lý do cần xem xét"] != ""].copy()
        evaluated_count = len(merged_w)

        if not flagged.empty:
            total_matched = len(flagged)
            shown = (
                flagged.sort_values(["pct_change", "weighted_margin_pct"], ascending=[True, True], na_position="last")
                .head(max_alert_rows)
                .copy()
            )
            displayed_count = len(shown)
            if total_matched > displayed_count:
                subtitle = (
                    f"{total_matched} cửa hàng cần xem xét; hiển thị {displayed_count} cửa hàng ưu tiên theo mức suy giảm và biên LN thấp."
                )
            else:
                subtitle = (
                    f"Phát hiện {total_matched} cửa hàng vượt tiêu chí cảnh báo (DT ≥ trung vị nhưng biên LN thấp hơn trung vị, hoặc suy giảm lớn kỳ so sánh)."
                )
            return WatchlistResult(
                status="alerts",
                df=shown,
                total_matched=total_matched,
                displayed_count=displayed_count,
                evaluated_count=evaluated_count,
                supports_margin=True,
                title="Cửa Hàng Cần Xem Xét (Vượt Tiêu Chí Cảnh Báo)",
                subtitle=subtitle,
            )

        ref = (
            merged_w.sort_values(["weighted_margin_pct", "pct_change"], ascending=[True, True], na_position="last")
            .head(max_reference_rows)
            .copy()
        )
        displayed_count = len(ref)
        ref["Lý do cần xem xét"] = f"Tham khảo: Top {displayed_count} biên LN thấp nhất (chưa vượt tiêu chí cảnh báo)"
        return WatchlistResult(
            status="reference_low_margin",
            df=ref,
            total_matched=0,
            displayed_count=displayed_count,
            evaluated_count=evaluated_count,
            supports_margin=True,
            title="Danh Sách Tham Khảo (Chưa Có Cảnh Báo)",
            subtitle=(
                f"Không có cửa hàng vượt tiêu chí cảnh báo trên {evaluated_count} CH đánh giá; "
                f"hiển thị Top {displayed_count} biên lợi nhuận thấp nhất để tham khảo thêm."
            ),
        )

    # Non-margin sources (IRPD / Serbia): evaluate same-store period declines only
    if not window.valid or store_var_df is None or store_var_df.empty or "delta" not in store_var_df.columns:
        return WatchlistResult(
            status="insufficient_data",
            df=pd.DataFrame(),
            total_matched=0,
            displayed_count=0,
            evaluated_count=0,
            supports_margin=False,
            title="Cửa Hàng Cần Xem Xét (Chưa Đủ Dữ Liệu)",
            subtitle="Chưa đủ dữ liệu so sánh cùng cửa hàng để đánh giá (nguồn hiện tại không hỗ trợ biên lợi nhuận).",
            empty_message="Chưa đủ dữ liệu so sánh 2 kỳ để đánh giá suy giảm cửa hàng.",
        )

    both = store_var_df[(store_var_df["presence_status"] == "Cả 2 kỳ") & store_var_df["delta"].notna()].copy()
    if both.empty:
        return WatchlistResult(
            status="insufficient_data",
            df=pd.DataFrame(),
            total_matched=0,
            displayed_count=0,
            evaluated_count=0,
            supports_margin=False,
            title="Cửa Hàng Cần Xem Xét (Chưa Đủ Dữ Liệu)",
            subtitle="Chưa có cửa hàng phát sinh bán đủ cả 2 kỳ để đánh giá (nguồn không hỗ trợ biên lợi nhuận).",
            empty_message="Chưa có cửa hàng phát sinh bán đồng thời cả 2 kỳ trong phạm vi lọc.",
        )

    evaluated_count = len(both)
    declining = both[both["delta"] < 0].copy()
    if not declining.empty:
        total_matched = len(declining)
        declining["Lý do cần xem xét"] = "Suy giảm so với kỳ trước (nguồn không hỗ trợ biên LN)"
        shown = declining.sort_values("delta", ascending=True).head(max_non_margin_rows).copy()
        displayed_count = len(shown)
        if total_matched > displayed_count:
            subtitle = (
                f"{total_matched} cửa hàng cần xem xét; hiển thị {displayed_count} cửa hàng suy giảm sâu nhất "
                "(nguồn không hỗ trợ biên lợi nhuận)."
            )
        else:
            subtitle = (
                f"Phát hiện {total_matched} cửa hàng suy giảm giữa {window.prev_label} và {window.cur_label} "
                "(nguồn không hỗ trợ biên lợi nhuận)."
            )
        return WatchlistResult(
            status="alerts",
            df=shown,
            total_matched=total_matched,
            displayed_count=displayed_count,
            evaluated_count=evaluated_count,
            supports_margin=False,
            title="Cửa Hàng Suy Giảm Cần Xem Xét",
            subtitle=subtitle,
        )

    return WatchlistResult(
        status="no_alerts",
        df=pd.DataFrame(),
        total_matched=0,
        displayed_count=0,
        evaluated_count=evaluated_count,
        supports_margin=False,
        title="Cửa Hàng Cần Xem Xét (Không Có Cảnh Báo)",
        subtitle=f"Không có cửa hàng suy giảm trong {evaluated_count} CH phát sinh cả 2 kỳ (nguồn không hỗ trợ biên lợi nhuận).",
        empty_message=f"Không ghi nhận cửa hàng suy giảm trong {evaluated_count} CH phát sinh cả 2 kỳ {window.cur_label} vs {window.prev_label}.",
    )


def build_store_insights(
    *,
    var_df: pd.DataFrame,
    watchlist_df: pd.DataFrame | None = None,
    matrix_df: pd.DataFrame,
    window: ComparisonWindow,
    metric_label: str,
    metric_unit: str | None,
    provenance_class: str,
    watchlist_result: WatchlistResult | None = None,
    matrix_meta: MatrixSourceMeta | None = None,
) -> list[str]:
    del provenance_class  # Matrix source provenance is resolved strictly from matrix query metadata
    bullets: list[str] = []
    if window.valid:
        both = (
            var_df[var_df["presence_status"] == "Cả 2 kỳ"].dropna(subset=["delta"])
            if (var_df is not None and not var_df.empty and "delta" in var_df.columns)
            else pd.DataFrame()
        )
        if len(both) > 1:
            pos_both = both[both["delta"] > 0].sort_values("delta", ascending=False)
            neg_both = both[both["delta"] < 0].sort_values("delta", ascending=True)
            scope_hdr = f"**Biến động cùng cửa hàng ({len(both)} CH phát sinh cả 2 kỳ {window.cur_label} vs {window.prev_label}):** "
            if not pos_both.empty and not neg_both.empty:
                top_up = pos_both.iloc[0]
                top_dn = neg_both.iloc[0]
                bullets.append(
                    f"{scope_hdr}Tăng mạnh nhất **{top_up['store_name']}** ({_fmt_signed(top_up['delta'], metric_unit)}); "
                    f"giảm sâu nhất **{top_dn['store_name']}** ({_fmt_signed(top_dn['delta'], metric_unit)})."
                )
            elif not pos_both.empty:
                top_up = pos_both.iloc[0]
                bullets.append(
                    f"{scope_hdr}Không có cửa hàng giảm ({len(pos_both)}/{len(both)} CH tăng); "
                    f"tăng mạnh nhất **{top_up['store_name']}** ({_fmt_signed(top_up['delta'], metric_unit)})."
                )
            elif not neg_both.empty:
                top_dn = neg_both.iloc[0]
                bullets.append(
                    f"{scope_hdr}Không có cửa hàng tăng ({len(neg_both)}/{len(both)} CH giảm); "
                    f"giảm sâu nhất **{top_dn['store_name']}** ({_fmt_signed(top_dn['delta'], metric_unit)})."
                )
            else:
                bullets.append(
                    f"{scope_hdr}{metric_label} của tất cả {len(both)} cửa hàng không đổi (chênh lệch = 0)."
                )
        elif len(both) == 1:
            only = both.iloc[0]
            d = float(only["delta"])
            pct_txt = f" ({only['pct_change'] * 100:+.2f}%)" if pd.notna(only.get("pct_change")) else ""
            if d > 0:
                chg = f"tăng **{_fmt_signed(d, metric_unit)}**{pct_txt}"
            elif d < 0:
                chg = f"giảm **{_fmt_signed(d, metric_unit)}**{pct_txt}"
            else:
                chg = "đi ngang (**0**)"
            bullets.append(
                f"**Cửa hàng duy nhất phát sinh cả 2 kỳ ({only['store_name']}):** {metric_label} {chg} giữa {window.prev_label} và {window.cur_label}."
            )
        else:
            bullets.append(
                f"**Biến động cùng cửa hàng ({window.cur_label} vs {window.prev_label}):** Chưa có cửa hàng nào phát sinh đồng thời cả 2 kỳ trong phạm vi đang lọc."
            )
    elif window.note:
        bullets.append(f"**So sánh cửa hàng:** {window.note}")

    if watchlist_result is not None:
        if watchlist_result.status == "alerts":
            if watchlist_result.total_matched > watchlist_result.displayed_count:
                cnt_txt = f"{watchlist_result.total_matched} cửa hàng cần xem xét; hiển thị {watchlist_result.displayed_count}"
            else:
                cnt_txt = f"{watchlist_result.total_matched} cửa hàng"
            if watchlist_result.supports_margin:
                bullets.append(
                    f"**Nhóm vượt tiêu chí cảnh báo ({cnt_txt}):** Lọc theo tiêu chí định lượng (doanh thu từ trung vị trở lên nhưng biên lợi nhuận thấp hơn trung vị, hoặc sụt giảm lớn kỳ so sánh) — cần kiểm tra thêm tồn kho và giá vốn trước khi quyết định."
                )
            else:
                bullets.append(
                    f"**Nhóm suy giảm cần xem xét ({cnt_txt}):** Các cửa hàng phát sinh cả 2 kỳ có chênh lệch giảm (nguồn hiện tại không hỗ trợ dữ liệu giá vốn và biên lợi nhuận) — cần đối chiếu thêm tồn kho trước khi quyết định."
                )
        elif watchlist_result.status == "reference_low_margin":
            bullets.append(
                f"**Chưa có cửa hàng vượt tiêu chí cảnh báo (trên {watchlist_result.evaluated_count} CH đánh giá):** Bảng hiển thị Top **{watchlist_result.displayed_count}** cửa hàng có biên lợi nhuận thấp nhất để **tham khảo thêm**, không phải danh sách cảnh báo suy giảm."
            )
        elif watchlist_result.status == "no_alerts":
            bullets.append(
                f"**Không có cửa hàng cảnh báo ({watchlist_result.evaluated_count} CH đánh giá):** Không ghi nhận cửa hàng suy giảm trong nhóm phát sinh cả 2 kỳ (nguồn hiện tại không hỗ trợ đánh giá biên lợi nhuận)."
            )
        else:
            bullets.append(
                "**Nhóm cần xem xét (chưa đủ dữ liệu):** Chưa đủ dữ liệu so sánh 2 kỳ hợp lệ để đánh giá tiêu chí cảnh báo cửa hàng."
            )
    elif watchlist_df is not None and not watchlist_df.empty:
        bullets.append(
            f"**Nhóm cần rà soát ({len(watchlist_df)} cửa hàng):** Lọc theo tiêu chí định lượng — cần kiểm tra thêm tồn kho và giá vốn trước khi quyết định."
        )

    if matrix_df is not None and not matrix_df.empty:
        m_meta = matrix_meta or resolve_matrix_source_meta(matrix_df, active_track=None)
        med_rev = float(matrix_df["line_amount"].median())
        med_mrg = float(matrix_df["weighted_margin_pct"].median())
        low_mrg_hi_rev = matrix_df[(matrix_df["line_amount"] >= med_rev) & (matrix_df["weighted_margin_pct"] < med_mrg)]
        if m_meta.matches_sidebar_track:
            bullets.append(
                f"**Phân tầng hiệu suất ({m_meta.label_vi} · {len(matrix_df)} CH theo bộ lọc hiện tại):** Trung vị doanh thu **{med_rev:,.0f} {m_meta.currency_code}**, biên LN gia quyền **{med_mrg:.2f}%**; có **{len(low_mrg_hi_rev)} CH** doanh thu từ trung vị trở lên nhưng biên lợi nhuận thấp hơn trung vị (dữ liệu bán hàng chưa gồm tồn kho hoặc điều chuyển kho)."
            )
        else:
            bullets.append(
                f"**Tham chiếu riêng — Ma trận {m_meta.label_vi} ({len(matrix_df)} CH toàn nguồn · không áp dụng bộ lọc nguồn thanh bên):** Trung vị doanh thu **{med_rev:,.0f} {m_meta.currency_code}**, biên LN gia quyền **{med_mrg:.2f}%**; có **{len(low_mrg_hi_rev)} CH** doanh thu từ trung vị trở lên nhưng biên lợi nhuận thấp hơn trung vị (chỉ nguồn ONYX có dữ liệu giá vốn và biên lợi nhuận)."
            )
    return bullets[:3]


def build_product_insights(
    *,
    var_df: pd.DataFrame,
    window: ComparisonWindow,
    metric_label: str,
    metric_unit: str | None,
    uom_guard: UomGuard,
    provenance_class: str,
) -> list[str]:
    bullets: list[str] = []
    if var_df is not None and not var_df.empty and window.valid and "delta" in var_df.columns:
        valid_var = var_df.dropna(subset=["delta"])
        if not valid_var.empty:
            pos_d = valid_var[valid_var["delta"] > 0].sort_values("delta", ascending=False)
            neg_d = valid_var[valid_var["delta"] < 0].sort_values("delta", ascending=True)
            parts: list[str] = []
            if not pos_d.empty:
                top_up = pos_d.iloc[0]
                pp_txt = f" ({top_up['contrib_pp']:+.2f} điểm %)" if pd.notna(top_up.get("contrib_pp")) else ""
                parts.append(f"tăng mạnh nhất **{top_up['label']}** ({_fmt_signed(top_up['delta'], metric_unit)}{pp_txt})")
            if not neg_d.empty:
                top_dn = neg_d.iloc[0]
                pp_txt = f" ({top_dn['contrib_pp']:+.2f} điểm %)" if pd.notna(top_dn.get("contrib_pp")) else ""
                parts.append(f"giảm sâu nhất **{top_dn['label']}** ({_fmt_signed(top_dn['delta'], metric_unit)}{pp_txt})")
            if parts:
                bullets.append(
                    f"**Đóng góp biến động trên toàn danh mục ({len(valid_var):,} nhóm · {metric_label} · {window.cur_label} vs {window.prev_label}):** {'; '.join(parts)}."
                )
            else:
                bullets.append(
                    f"**Đóng góp biến động ({len(valid_var):,} nhóm · {window.cur_label} vs {window.prev_label}):** Chênh lệch tất cả sản phẩm bằng 0."
                )

        mix_df = var_df.dropna(subset=["mix_shift_pp"])
        if not mix_df.empty:
            pos_mix = mix_df[mix_df["mix_shift_pp"] > 0].sort_values("mix_shift_pp", ascending=False)
            neg_mix = mix_df[mix_df["mix_shift_pp"] < 0].sort_values("mix_shift_pp", ascending=True)
            mix_parts: list[str] = []
            if not pos_mix.empty:
                up_mix = pos_mix.iloc[0]
                mix_parts.append(f"tăng tỷ trọng mạnh nhất là **{up_mix['label']}** ({up_mix['mix_shift_pp']:+.2f} điểm %)")
            if not neg_mix.empty:
                dn_mix = neg_mix.iloc[0]
                mix_parts.append(f"thu hẹp tỷ trọng nhiều nhất là **{dn_mix['label']}** ({dn_mix['mix_shift_pp']:+.2f} điểm %)")
            if mix_parts:
                bullets.append(f"**Dịch chuyển cơ cấu danh mục:** {'; '.join(mix_parts)}.")
            else:
                bullets.append("**Dịch chuyển cơ cấu danh mục:** Tỷ trọng các sản phẩm giữ nguyên giữa hai kỳ.")

    if uom_guard.is_multi_uom_blocked:
        bullets.append(
            f"**Lưu ý nhiều đơn vị tính:** Nguồn đang chứa {uom_guard.uom_count} đơn vị tính nên bảng xếp hạng & cơ cấu được tính theo **Doanh thu ({metric_unit})**, không cộng gộp sản lượng hay đơn giá xuyên ĐVT."
        )
    elif provenance_class == "SYNTHETIC":
        bullets.append(
            "**Ngữ cảnh nguồn:** Danh mục sản phẩm đang xem là **dữ liệu mô phỏng**, tách biệt với dữ liệu bán hàng thực tế IRPD và chuỗi ATC 2014–2019."
        )
    return bullets[:3]
