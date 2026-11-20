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
                "và cột quy đổi base_qty hiện NULL trong Gold mirror. Không thể cộng gộp sản lượng hay tính đơn giá bình quân xuyên ĐVT — "
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
) -> pd.DataFrame:
    """Add period delta, %, additive contribution (percentage points), and mix shift (pp)."""
    if df is None or df.empty:
        out = df.copy() if df is not None else pd.DataFrame()
        for col in ("delta", "pct_change", "contrib_pp", "share_cur", "share_prev", "mix_shift_pp", "presence_status"):
            out[col] = pd.Series(dtype="float64" if col != "presence_status" else "object")
        return out

    out = df.copy()
    cur_s = pd.to_numeric(out[cur_col], errors="coerce").fillna(0.0)
    prev_s = pd.to_numeric(out[prev_col], errors="coerce").fillna(0.0)
    out[cur_col] = cur_s
    out[prev_col] = prev_s
    out["delta"] = cur_s - prev_s

    total_cur = float(cur_s.sum())
    total_prev = float(prev_s.sum())

    def _pct(c: float, p: float) -> float | None:
        if p > 0:
            return (c - p) / p
        return None

    def _presence(c: float, p: float) -> str:
        if c > 0 and p > 0:
            return "Cả 2 kỳ"
        if c > 0 and p <= 0:
            return "Mới phát sinh kỳ này"
        if c <= 0 and p > 0:
            return "Ngừng phát sinh kỳ này"
        return "Không phát sinh"

    out["pct_change"] = [_pct(c, p) for c, p in zip(cur_s, prev_s)]
    out["contrib_pp"] = [(d / total_prev) * 100.0 if total_prev > 0 else None for d in out["delta"]]
    out["share_cur"] = [c / total_cur if total_cur > 0 else None for c in cur_s]
    out["share_prev"] = [p / total_prev if total_prev > 0 else None for p in prev_s]
    out["mix_shift_pp"] = [
        (sc - sp) * 100.0 if (sc is not None and sp is not None) else None
        for sc, sp in zip(out["share_cur"], out["share_prev"])
    ]
    out["presence_status"] = [_presence(c, p) for c, p in zip(cur_s, prev_s)]
    return out


def flag_small_sample(store_days: int | float | None, *, threshold: int = SMALL_SAMPLE_STORE_DAYS) -> bool:
    if store_days is None or pd.isna(store_days):
        return True
    return int(store_days) < threshold


# ---------------------------------------------------------------------------
# Rule-Based Insights (Strict Distinction: Arithmetic Contribution != Cause)
# ---------------------------------------------------------------------------

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
    prov_tag = "Mô phỏng (SYNTHETIC)" if provenance_class == "SYNTHETIC" else "Quan sát thực tế (OBSERVED)"

    if window.valid and cur_total is not None and prev_total is not None and prev_total > 0:
        diff = cur_total - prev_total
        pct = diff / prev_total
        direction = "tăng" if diff > 0 else ("giảm" if diff < 0 else "đi ngang")
        fmt_cur = fmt_currency(cur_total, metric_unit) if metric_unit else fmt_compact(cur_total)
        fmt_prev = fmt_currency(prev_total, metric_unit) if metric_unit else fmt_compact(prev_total)
        fmt_diff = fmt_currency(abs(diff), metric_unit) if metric_unit else fmt_compact(abs(diff))
        sign = "+" if diff > 0 else ("−" if diff < 0 else "")
        bullets.append(
            f"**Biến động kỳ {window.cur_label} so với {window.prev_label} ({prov_tag}):** "
            f"{metric_label} {direction} **{sign}{fmt_diff}** ({pct * 100:+.2f}%), từ {fmt_prev} lên {fmt_cur}."
        )
    elif window.note:
        bullets.append(f"**Kỳ so sánh ({meta_label}):** {window.note}")

    if driver_df is not None and not driver_df.empty and "delta" in driver_df.columns:
        valid_drv = driver_df.dropna(subset=["delta"])
        if not valid_drv.empty:
            top_pos = valid_drv.sort_values("delta", ascending=False).iloc[0]
            top_neg = valid_drv.sort_values("delta", ascending=True).iloc[0]
            parts: list[str] = []
            if float(top_pos["delta"]) > 0:
                pp_txt = f" ({top_pos['contrib_pp']:+.2f} điểm %)" if pd.notna(top_pos.get("contrib_pp")) else ""
                val_txt = fmt_currency(top_pos["delta"], metric_unit) if metric_unit else fmt_compact(top_pos["delta"])
                parts.append(f"tăng mạnh nhất: **{top_pos[driver_name_col]}** (+{val_txt}{pp_txt})")
            if float(top_neg["delta"]) < 0:
                pp_txt = f" ({top_neg['contrib_pp']:+.2f} điểm %)" if pd.notna(top_neg.get("contrib_pp")) else ""
                val_txt = fmt_currency(top_neg["delta"], metric_unit) if metric_unit else fmt_compact(top_neg["delta"])
                parts.append(f"giảm mạnh nhất: **{top_neg[driver_name_col]}** ({val_txt}{pp_txt})")
            if parts:
                bullets.append(
                    f"**Đóng góp số học lớn nhất (không suy diễn nguyên nhân):** {'; '.join(parts)}."
                )

    if uom_guard.is_multi_uom_blocked:
        bullets.append(
            f"**Lưu ý đơn vị tính ({meta_label}):** Nguồn đang gồm **{uom_guard.uom_count} đơn vị tính** và thiếu hệ số quy đổi `base_qty`; dashboard tạm khóa cộng tổng sản lượng và so sánh qua doanh thu hoặc bảng tách từng ĐVT."
        )
    elif provenance_class == "SYNTHETIC":
        bullets.append(
            "**Giới hạn diễn giải:** Số liệu nguồn này là **mô phỏng POS (`SYNTHETIC`)**; kết quả đơn hàng cấp hóa đơn (distinct `sales_order_id`) chưa khả dụng ở Gold mirror do grain là `Sản phẩm × Cửa hàng × Ngày`."
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
        target_df = adequate if len(adequate) >= 2 else valid
        if len(target_df) >= 2:
            hi = target_df.sort_values(metric_col, ascending=False).iloc[0]
            lo = target_df.sort_values(metric_col, ascending=True).iloc[0]
            hi_txt = fmt_currency(hi[metric_col], metric_unit) if metric_unit else f"{float(hi[metric_col]):,.2f}"
            lo_txt = fmt_currency(lo[metric_col], metric_unit) if metric_unit else f"{float(lo[metric_col]):,.2f}"
            hi_lbl = f"{temp_label(str(hi['temp_band']))} × {rain_label(str(hi['rain_regime']))}"
            lo_lbl = f"{temp_label(str(lo['temp_band']))} × {rain_label(str(lo['rain_regime']))}"
            diff_pct_txt = ""
            if float(lo[metric_col]) > 0:
                diff_pct = (float(hi[metric_col]) - float(lo[metric_col])) / float(lo[metric_col]) * 100.0
                diff_pct_txt = f" (chênh +{diff_pct:.1f}% trên các nhóm đủ mẫu `n ≥ {SMALL_SAMPLE_STORE_DAYS}` CH-ngày)" if not adequate.empty else f" (chênh +{diff_pct:.1f}%)"
            bullets.append(
                f"**Mối liên hệ quan sát (đã chuẩn hóa theo CH-ngày có bán):** Nhóm `{hi_lbl}` đạt {metric_noun} **{hi_txt}** (n={int(hi['active_store_days']):,}), "
                f"cao hơn nhóm `{lo_lbl}` ở mức **{lo_txt}** (n={int(lo['active_store_days']):,}){diff_pct_txt}."
            )
        small_cnt = int((valid["active_store_days"].fillna(0) < SMALL_SAMPLE_STORE_DAYS).sum())
        if small_cnt > 0:
            bullets.append(
                f"**Cảnh báo cỡ mẫu nhỏ:** Có **{small_cnt}** ô Nhiệt độ × Mức mưa có ít hơn `{SMALL_SAMPLE_STORE_DAYS}` cửa hàng-ngày — không nên kết luận quy luật từ các ô này."
            )

    cov_pct = (active_store_days / possible_store_days * 100.0) if possible_store_days > 0 else None
    cov_txt = f" ({cov_pct:.1f}% của {possible_store_days:,} CH × ngày hoạt động trong phạm vi lọc)" if cov_pct is not None else ""
    prov_note = "Dữ liệu đang xem thuộc nhóm **mô phỏng (`SYNTHETIC`)**" if provenance_class == "SYNTHETIC" else "Dữ liệu đang xem là **quan sát thực tế (`OBSERVED`)**"
    bullets.append(
        f"**Độ phủ & giới hạn nhân quả:** Gold mart chỉ lưu ngày có phát sinh bán (`sold_qty > 0`, tổng **{active_store_days:,}** CH-ngày{cov_txt}); **không bao gồm ngày bán bằng 0**. {prov_note}, chỉ phản ánh tương quan quan sát chứ chưa kiểm định tác động nhân quả."
    )
    return bullets[:3]


def build_store_insights(
    *,
    var_df: pd.DataFrame,
    watchlist_df: pd.DataFrame,
    matrix_df: pd.DataFrame,
    window: ComparisonWindow,
    metric_label: str,
    metric_unit: str | None,
    provenance_class: str,
) -> list[str]:
    bullets: list[str] = []
    if var_df is not None and not var_df.empty and window.valid:
        both = var_df[var_df["presence_status"] == "Cả 2 kỳ"]
        if len(both) > 1:
            top_up = both.sort_values("delta", ascending=False).iloc[0]
            top_dn = both.sort_values("delta", ascending=True).iloc[0]
            up_val = fmt_currency(top_up["delta"], metric_unit) if metric_unit else fmt_compact(top_up["delta"])
            dn_val = fmt_currency(top_dn["delta"], metric_unit) if metric_unit else fmt_compact(top_dn["delta"])
            bullets.append(
                f"**Biến động cùng cửa hàng ({len(both)} CH phát sinh cả 2 kỳ {window.cur_label} vs {window.prev_label}):** "
                f"Tăng mạnh nhất **{top_up['store_name']}** (+{up_val}); giảm sâu nhất **{top_dn['store_name']}** ({dn_val})."
            )
        elif len(both) == 1:
            only = both.iloc[0]
            val_txt = fmt_currency(only["delta"], metric_unit) if metric_unit else fmt_compact(only["delta"])
            pct_txt = f" ({only['pct_change'] * 100:+.2f}%)" if pd.notna(only.get("pct_change")) else ""
            bullets.append(
                f"**Cửa hàng duy nhất trong nguồn ({only['store_name']}):** {metric_label} thay đổi **{val_txt}**{pct_txt} giữa {window.prev_label} và {window.cur_label}."
            )

    if watchlist_df is not None and not watchlist_df.empty:
        bullets.append(
            f"**Nhóm cần rà soát ({len(watchlist_df)} cửa hàng):** Lọc theo rule định lượng (doanh thu trên trung vị nhưng biên LN gia quyền dưới trung vị, hoặc suy giảm lớn kỳ so sánh) — cần đối chiếu thêm tồn kho/giá vốn trước khi ra quyết định vận hành."
        )

    if matrix_df is not None and not matrix_df.empty:
        med_rev = float(matrix_df["line_amount"].median())
        med_mrg = float(matrix_df["weighted_margin_pct"].median())
        low_mrg_hi_rev = matrix_df[(matrix_df["line_amount"] >= med_rev) & (matrix_df["weighted_margin_pct"] < med_mrg)]
        bullets.append(
            f"**Phân tầng ma trận ONYX EU (Mô phỏng — {len(matrix_df)} CH đang lọc):** Trung vị doanh thu **{med_rev:,.0f} EUR**, biên LN gia quyền **{med_mrg:.2f}%**; có **{len(low_mrg_hi_rev)} CH** doanh thu cao nhưng biên LN thấp hơn trung vị (lưu ý Sales BI chưa gồm KPI tồn kho/điều chuyển Distribution)."
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
    if var_df is not None and not var_df.empty and window.valid:
        top_up = var_df.sort_values("delta", ascending=False).iloc[0]
        top_dn = var_df.sort_values("delta", ascending=True).iloc[0]
        parts: list[str] = []
        if float(top_up["delta"]) > 0:
            v_txt = fmt_currency(top_up["delta"], metric_unit) if metric_unit else fmt_compact(top_up["delta"])
            pp_txt = f" ({top_up['contrib_pp']:+.2f} điểm %)" if pd.notna(top_up.get("contrib_pp")) else ""
            parts.append(f"tăng mạnh nhất **{top_up['label']}** (+{v_txt}{pp_txt})")
        if float(top_dn["delta"]) < 0:
            v_txt = fmt_currency(top_dn["delta"], metric_unit) if metric_unit else fmt_compact(top_dn["delta"])
            pp_txt = f" ({top_dn['contrib_pp']:+.2f} điểm %)" if pd.notna(top_dn.get("contrib_pp")) else ""
            parts.append(f"giảm sâu nhất **{top_dn['label']}** ({v_txt}{pp_txt})")
        if parts:
            bullets.append(
                f"**Đóng góp biến động sản phẩm ({metric_label} · {window.cur_label} vs {window.prev_label}):** {'; '.join(parts)}."
            )

        mix_df = var_df.dropna(subset=["mix_shift_pp"])
        if not mix_df.empty:
            up_mix = mix_df.sort_values("mix_shift_pp", ascending=False).iloc[0]
            dn_mix = mix_df.sort_values("mix_shift_pp", ascending=True).iloc[0]
            bullets.append(
                f"**Dịch chuyển cơ cấu danh mục:** Tăng tỷ trọng nhiều nhất là **{up_mix['label']}** ({up_mix['mix_shift_pp']:+.2f} điểm %); "
                f"thu hẹp tỷ trọng nhiều nhất là **{dn_mix['label']}** ({dn_mix['mix_shift_pp']:+.2f} điểm %)."
            )

    if uom_guard.is_multi_uom_blocked:
        bullets.append(
            f"**Guard đa ĐVT:** Nguồn đang chứa {uom_guard.uom_count} đơn vị tính nên xếp hạng sản phẩm & cơ cấu đang đo theo **Doanh thu ({metric_unit})**, không cộng gộp sản lượng hay đơn giá xuyên ĐVT."
        )
    elif provenance_class == "SYNTHETIC":
        bullets.append(
            "**Ngữ cảnh nguồn:** Danh mục sản phẩm trên track mô phỏng phản ánh dữ liệu tổng hợp (`SYNTHETIC`), tách riêng với luồng quan sát Nhà sản xuất IRPD (`OBSERVED`) và nhóm ATC 2014–2019 (`OBSERVED`)."
        )
    return bullets[:3]
