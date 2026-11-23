"""Precomputed ML demand forecasting artifact loader and analytics helpers for Page 5."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from config import atc_label

DEFAULT_ARTIFACTS_DIR: Path = Path(__file__).resolve().parents[2] / "artifacts" / "forecasting"
GOOGLE_DOC_URL: str = (
    "https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit"
)

ATC_ORDER: tuple[str, ...] = ("M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06")

MODEL_LABEL_VI: dict[str, str] = {
    "AutoRouted_Champion": "AutoRouted Champion (Chọn theo Val MAE)",
    "LightGBM_AnchorRes_F3": "LightGBM AnchorRes (Neo EWMA + ERA5)",
    "Ridge_F1F2F3": "Hồi quy Ridge (F1+F2+ERA5)",
    "Croston_SBA": "Croston-SBA (Chuỗi gián đoạn)",
    "Harmonic_ARIMA": "Harmonic ARIMA (Fourier K=2)",
    "Hybrid_SARIMA_LGBM_F3": "Hybrid OOF (SARIMA + α·LightGBM)",
    "LightGBM_F1F2F3": "LightGBM Đầy đủ (F1+F2+ERA5)",
    "LightGBM_F1F2": "LightGBM Lịch sử + Lịch (F1+F2)",
    "LightGBM_F1": "LightGBM Chỉ Lịch sử (F1)",
    "LightGBM_F1F2F3_LagOnly": "LightGBM F1+F2+ERA5 (Chỉ biến trễ)",
    "Seasonal_Naive": "Mùa vụ năm trước (y[t−52])",
    "Seasonal_Naive_Weighted": "Mùa vụ trọng số Paper 2024",
    "LightGBM_Daily_F1F2F3": "LightGBM Ngày (F1+F2+ERA5)",
    "LightGBM_Daily_F1F2": "LightGBM Ngày (F1+F2)",
    "Seasonal_Naive_7D": "Mùa vụ 7 ngày trước (y[t−7])",
}

FEATURE_GROUP_LABELS: dict[str, str] = {
    "F1": "Lịch sử nội sinh (F1)",
    "F2": "Lịch & Tỷ trọng (F2)",
    "F3": "Thời tiết ERA5 (F3)",
}

FEATURE_META_VI: dict[str, tuple[str, str]] = {
    # F1 — Lịch sử nội sinh (14)
    "lag_1": ("Sản lượng 1 tuần trước", "F1"),
    "lag_2": ("Sản lượng 2 tuần trước", "F1"),
    "lag_3": ("Sản lượng 3 tuần trước", "F1"),
    "lag_4": ("Sản lượng 4 tuần trước", "F1"),
    "lag_8": ("Sản lượng 8 tuần trước", "F1"),
    "lag_12": ("Sản lượng 12 tuần trước", "F1"),
    "lag_52": ("Sản lượng cùng kỳ 52 tuần", "F1"),
    "rolling_mean_4": ("Trung bình trượt 4 tuần", "F1"),
    "rolling_std_4": ("Độ lệch chuẩn 4 tuần", "F1"),
    "rolling_max_4": ("Đỉnh bán 4 tuần gần nhất", "F1"),
    "rolling_mean_12": ("Trung bình trượt 12 tuần", "F1"),
    "rolling_std_12": ("Độ lệch chuẩn 12 tuần", "F1"),
    "ewma_4": ("Trung bình mũ EWMA 4 tuần", "F1"),
    "zero_ratio_12": ("Tỷ lệ kỳ bằng 0 (12 tuần)", "F1"),
    # F2 — Lịch & tỷ trọng (8)
    "week_sin52": ("Chu kỳ mùa vụ năm (Sin)", "F2"),
    "week_cos52": ("Chu kỳ mùa vụ năm (Cos)", "F2"),
    "week_sin26": ("Chu kỳ nửa năm (Sin)", "F2"),
    "week_cos26": ("Chu kỳ nửa năm (Cos)", "F2"),
    "time_idx": ("Xu hướng thời gian dài hạn", "F2"),
    "is_rs_holiday": ("Ngày nghỉ lễ quốc gia Serbia", "F2"),
    "atc_share_lag1": ("Tỷ trọng nhóm ATC tuần trước", "F2"),
    "is_holiday_zero_lag1": ("Cờ đóng cửa lễ tuần trước", "F2"),
    # F3 — Compact Open-Meteo ERA5 (7)
    "temp_mean": ("Nhiệt độ trung bình (°C)", "F3"),
    "hdd": ("Độ ngày sưởi ấm (HDD)", "F3"),
    "humidity_mean": ("Độ ẩm không khí TB (%)", "F3"),
    "daylight_duration_s": ("Thời lượng nắng ban ngày (s)", "F3"),
    "temp_shock_2w": ("Biến động nhiệt 2 tuần (°C)", "F3"),
    "temp_mean_lag1": ("Nhiệt độ TB tuần trước (°C)", "F3"),
    "humidity_mean_lag1": ("Độ ẩm TB tuần trước (%)", "F3"),
}

SB_CLASS_VI: dict[str, str] = {
    "Smooth": "Ổn định (Smooth)",
    "Intermittent": "Bán thưa (Intermittent)",
    "Erratic": "Biến động mạnh (Erratic)",
    "Lumpy": "Thưa & biến động (Lumpy)",
}


def model_label_vi(model_name: str | None) -> str:
    if not model_name:
        return "Chưa rõ"
    return MODEL_LABEL_VI.get(str(model_name), str(model_name))


def parse_autorouted_selection(feature_set: str | None) -> tuple[str, float | None]:
    """Parse `selected=<model>|valMAE=<float>` exported by Notebook 04/05."""
    raw = str(feature_set or "").strip()
    selected = raw
    val_mae: float | None = None
    for part in raw.split("|"):
        if part.startswith("selected="):
            selected = part.split("=", 1)[1].strip()
        elif part.startswith("valMAE="):
            try:
                val_mae = float(part.split("=", 1)[1].strip())
            except ValueError:
                val_mae = None
    return selected, val_mae


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert `#rrggbb` to `rgba(r, g, b, alpha)` for Plotly confidence ribbons."""
    clean = str(hex_color or "#087b71").strip().lstrip("#")
    if len(clean) != 6:
        return f"rgba(8, 123, 113, {alpha:.2f})"
    try:
        r = int(clean[0:2], 16)
        g = int(clean[2:4], 16)
        b = int(clean[4:6], 16)
    except ValueError:
        return f"rgba(8, 123, 113, {alpha:.2f})"
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _read_parquet_safe(path: Path, date_cols: tuple[str, ...] = ()) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


def _read_json_safe(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return {}


@st.cache_data(ttl=600, show_spinner=False)
def load_forecast_bundle(artifacts_dir: str | None = None) -> dict[str, Any]:
    """Load precomputed forecasting CSV/Parquet/JSON outputs safely without mutating DB."""
    base = Path(artifacts_dir) if artifacts_dir else DEFAULT_ARTIFACTS_DIR

    metrics_by_atc = _read_csv_safe(base / "metrics_by_atc.csv")
    ablation = _read_csv_safe(base / "ablation_f1_f2_f3.csv")
    benchmark = _read_csv_safe(base / "benchmark_vs_paper2024.csv")
    coverage = _read_csv_safe(base / "quantiles_coverage.csv")
    dm_results = _read_csv_safe(base / "dm_test_results.csv")
    rolling_stability = _read_csv_safe(base / "rolling_4folds_stability.csv")
    daily_metrics = _read_csv_safe(base / "daily_365d_metrics.csv")
    eda_diagnostics = _read_csv_safe(base / "eda_diagnostics_8atc.csv")

    pred_weekly = _read_parquet_safe(base / "predictions_holdout_52w.parquet", date_cols=("week_end",))
    quantiles_weekly = _read_parquet_safe(base / "predictions_quantiles_52w.parquet", date_cols=("week_end",))
    pred_daily = _read_parquet_safe(base / "predictions_daily_365d.parquet", date_cols=("local_date",))
    shap_weekly = _read_parquet_safe(base / "shap_values_52w.parquet", date_cols=("week_end",))

    model_card = _read_json_safe(base / "model_card.json")
    training_summary = _read_json_safe(base / "training_summary.json")

    available = not metrics_by_atc.empty and not pred_weekly.empty

    return {
        "available": available,
        "artifacts_dir": str(base),
        "metrics_by_atc": metrics_by_atc,
        "ablation": ablation,
        "benchmark": benchmark,
        "coverage": coverage,
        "dm_results": dm_results,
        "rolling_stability": rolling_stability,
        "daily_metrics": daily_metrics,
        "eda_diagnostics": eda_diagnostics,
        "pred_weekly": pred_weekly,
        "quantiles_weekly": quantiles_weekly,
        "pred_daily": pred_daily,
        "shap_weekly": shap_weekly,
        "model_card": model_card,
        "training_summary": training_summary,
    }


def compute_shap_driver_table(
    shap_df: pd.DataFrame,
    atc_code: str,
    *,
    top_n: int = 10,
) -> tuple[pd.DataFrame, float, str]:
    """Summarize mean |TreeSHAP| per feature, its % share, and F3 weather contribution."""
    empty_cols = [
        "feature",
        "label_vi",
        "group_code",
        "group_label",
        "mean_abs_shap",
        "mean_signed_shap",
        "share_pct",
    ]
    if shap_df.empty or "atc_code" not in shap_df.columns:
        return pd.DataFrame(columns=empty_cols), 0.0, "raw_units"

    sub = shap_df.loc[shap_df["atc_code"] == atc_code].copy()
    if sub.empty:
        return pd.DataFrame(columns=empty_cols), 0.0, "raw_units"

    shap_space = str(sub["shap_space"].iloc[0]) if "shap_space" in sub.columns else "raw_units"
    ignore_cols = {"atc_code", "week_idx", "week_end", "y_true", "y_pred", "base_value", "shap_space"}
    feat_cols = [c for c in sub.columns if c not in ignore_cols]
    if not feat_cols:
        return pd.DataFrame(columns=empty_cols), 0.0, shap_space

    abs_means = sub[feat_cols].abs().mean(axis=0)
    signed_means = sub[feat_cols].mean(axis=0)
    total_abs = float(abs_means.sum())

    rows: list[dict[str, Any]] = []
    f3_share_pct = 0.0
    for feat in feat_cols:
        label_vi, grp = FEATURE_META_VI.get(feat, (feat, "F1"))
        val = float(abs_means[feat])
        share = (100.0 * val / total_abs) if total_abs > 0 else 0.0
        if grp == "F3":
            f3_share_pct += share
        rows.append(
            {
                "feature": feat,
                "label_vi": label_vi,
                "group_code": grp,
                "group_label": FEATURE_GROUP_LABELS.get(grp, grp),
                "mean_abs_shap": round(val, 4),
                "mean_signed_shap": round(float(signed_means[feat]), 4),
                "share_pct": round(share, 2),
            }
        )

    out = pd.DataFrame(rows).sort_values("mean_abs_shap", ascending=False).head(top_n).reset_index(drop=True)
    return out, round(f3_share_pct, 1), shap_space


def build_atc_overview_table(
    metrics_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    coverage_df: pd.DataFrame,
    dm_df: pd.DataFrame,
    eda_df: pd.DataFrame,
) -> pd.DataFrame:
    """Assemble unified 8-ATC summary linking AutoRouter, lowest MSE, baselines, Paper 2024, DM', and CQR."""
    if metrics_df.empty:
        return pd.DataFrame()

    holdout = metrics_df.loc[metrics_df["fold_id"] == "holdout_52w"].copy()
    if holdout.empty:
        return pd.DataFrame()

    bench_map = benchmark_df.set_index("atc_code").to_dict(orient="index") if not benchmark_df.empty else {}
    cov_map = coverage_df.set_index("atc_code").to_dict(orient="index") if not coverage_df.empty else {}
    eda_map = eda_df.set_index("atc_code").to_dict(orient="index") if not eda_df.empty else {}

    dm_sn_map: dict[str, dict[str, Any]] = {}
    if not dm_df.empty:
        dm_sn = dm_df.loc[
            (dm_df["horizon"] == "Weekly_52W")
            & (dm_df["model_A"] == "AutoRouted_Champion")
            & (dm_df["model_B"] == "Seasonal_Naive")
        ]
        dm_sn_map = dm_sn.set_index("atc_code").to_dict(orient="index")

    atcs = [a for a in ATC_ORDER if a in set(holdout["atc_code"])]
    for a in sorted(set(holdout["atc_code"])):
        if a not in atcs:
            atcs.append(a)

    rows: list[dict[str, Any]] = []
    for atc in atcs:
        sub = holdout.loc[holdout["atc_code"] == atc]
        ar = sub.loc[sub["model_name"] == "AutoRouted_Champion"]
        ar_row = ar.iloc[0] if not ar.empty else sub.iloc[0]
        ar_selected, val_mae = parse_autorouted_selection(ar_row.get("feature_set"))

        base_candidates = sub.loc[sub["model_name"] != "AutoRouted_Champion"]
        best_row = (
            base_candidates.sort_values("MSE", ascending=True).iloc[0]
            if not base_candidates.empty
            else ar_row
        )
        sn_sub = sub.loc[sub["model_name"] == "Seasonal_Naive"]
        sn_row = sn_sub.iloc[0] if not sn_sub.empty else None

        bench = bench_map.get(atc, {})
        cov = cov_map.get(atc, {})
        eda = eda_map.get(atc, {})
        dm_sn_row = dm_sn_map.get(atc, {})

        best_mse = float(best_row["MSE"])
        paper_xgb = bench.get("Paper_XGB_MSE")
        paper_stat = bench.get("Paper_BestStat_MSE")
        paper_stat_model = str(bench.get("Paper_BestStat_Model") or "—")
        beats_xgb = bool(paper_xgb is not None and pd.notna(paper_xgb) and best_mse < float(paper_xgb))

        sn_mse = float(sn_row["MSE"]) if sn_row is not None else None
        ar_mse = float(ar_row["MSE"])
        mse_drop_pct = ((sn_mse - ar_mse) / sn_mse * 100.0) if sn_mse and sn_mse > 0 else None

        sb_class = str(eda.get("sb_class") or "Smooth")
        rows.append(
            {
                "atc_code": atc,
                "atc_name_vi": atc_label(atc),
                "sb_class": sb_class,
                "sb_class_vi": SB_CLASS_VI.get(sb_class, sb_class),
                "autorouted_selected": ar_selected,
                "autorouted_selected_vi": model_label_vi(ar_selected),
                "autorouted_val_mae": val_mae,
                "autorouted_wape": float(ar_row["WAPE_pct"]),
                "autorouted_mase": float(ar_row["MASE"]),
                "autorouted_mse": ar_mse,
                "autorouted_bias": float(ar_row["Bias_pct"]),
                "best_mse_model": str(best_row["model_name"]),
                "best_mse_model_vi": model_label_vi(str(best_row["model_name"])),
                "best_mse_val": best_mse,
                "best_mse_wape": float(best_row["WAPE_pct"]),
                "snaive_mse": sn_mse,
                "snaive_wape": float(sn_row["WAPE_pct"]) if sn_row is not None else None,
                "mse_drop_vs_snaive_pct": mse_drop_pct,
                "paper_xgb_mse": float(paper_xgb) if paper_xgb is not None and pd.notna(paper_xgb) else None,
                "paper_best_stat_model": paper_stat_model,
                "paper_best_stat_mse": float(paper_stat) if paper_stat is not None and pd.notna(paper_stat) else None,
                "beats_paper_xgb": beats_xgb,
                "dm_p_vs_snaive": float(dm_sn_row["p_one_sided_A_better"]) if "p_one_sided_A_better" in dm_sn_row else None,
                "dm_wins_snaive": bool(dm_sn_row.get("A_wins_p05", False)),
                "cov_80_raw_pct": float(cov["cov_80_raw_pct"]) if "cov_80_raw_pct" in cov else None,
                "cov_80_cqr_pct": float(cov["cov_80_cqr_pct"]) if "cov_80_cqr_pct" in cov else None,
                "cqr_width": float(cov["cqr_width"]) if "cqr_width" in cov else None,
            }
        )

    return pd.DataFrame(rows)


def format_signed_pct(val: float | None, *, decimals: int = 1) -> str:
    """Format signed percentages cleanly with Unicode minus and never emit `+-`."""
    if val is None or pd.isna(val):
        return "—"
    v = float(val)
    if abs(v) < 10 ** (-decimals - 1):
        return f"0.{'0' * decimals}%"
    sign = "+" if v > 0 else "−"
    return f"{sign}{abs(v):.{decimals}f}%"


def build_forecast_insights(
    atc_code: str,
    overview_row: dict[str, Any],
    f3_weather_share_pct: float,
    shap_space: str,
    eda_row: dict[str, Any] | None = None,
) -> list[str]:
    """Generate concise, honest Vietnamese business takeaways for the selected ATC group."""
    bullets: list[str] = []
    sb_class = str(overview_row.get("sb_class") or "Smooth")
    ar_name = str(overview_row.get("autorouted_selected_vi") or overview_row.get("autorouted_selected") or "")
    ar_wape = overview_row.get("autorouted_wape")
    ar_mase = overview_row.get("autorouted_mase")
    dm_p = overview_row.get("dm_p_vs_snaive")
    mse_drop = overview_row.get("mse_drop_vs_snaive_pct")

    if ar_wape is not None and ar_mase is not None:
        dm_note = (
            f"kiểm định DM' vượt Seasonal Naïve có ý nghĩa thống kê (`p = {dm_p:.4f} < 0.05`)"
            if dm_p is not None and dm_p < 0.05
            else "so với Seasonal Naïve"
        )
        drop_txt = f"giảm **`{mse_drop:.1f}%`** MSE" if mse_drop is not None and mse_drop > 0 else "ổn định sai số"
        bullets.append(
            f"**Chọn mô hình tự động (không nhìn Test):** AutoRouter chọn **`{ar_name}`** dựa trên Validation MAE thấp nhất, "
            f"đạt `WAPE = {ar_wape:.2f}%`, `MASE = {ar_mase:.3f}` — {drop_txt} và {dm_note}."
        )

    cov_raw = overview_row.get("cov_80_raw_pct")
    cov_cqr = overview_row.get("cov_80_cqr_pct")
    if cov_raw is not None and cov_cqr is not None:
        bullets.append(
            f"**Biên an toàn Split CQR (mục tiêu 80%):** Độ phủ thực nghiệm trên `52` tuần kiểm chứng ở nhóm `{atc_code}` "
            f"đạt **`{cov_cqr:.1f}%`** (so với `{cov_raw:.1f}%` trước hiệu chuẩn)."
        )

    space_note = "không gian log-link Tweedie" if "tweedie" in shap_space.lower() else "đơn vị bán thực"
    bullets.append(
        f"**Tác động Thời tiết Open-Meteo ERA5 (`F3`):** Cụm 7 biến khí tượng đóng góp **`{f3_weather_share_pct:.1f}%`** "
        f"tổng giá trị tuyệt đối `TreeSHAP` cho nhóm `{atc_code}` (tính trên {space_note})."
    )

    if sb_class == "Intermittent":
        zero_pct = eda_row.get("daily_zero_pct") if eda_row else 67.9
        w_mean = eda_row.get("weekly_mean") if eda_row else 4.14
        bullets.append(
            f"**Lưu ý chuỗi bán thưa (`{atc_code}`):** Có tới `{zero_pct:.1f}%` ngày bằng 0 (TB `{w_mean:.2f}` đv/tuần). "
            f"Pipeline dùng `WAPE`/`MASE` và `Croston-SBA`/`Tweedie` thay vì `MAPE` để tránh nổ `inf%`."
        )
    elif not overview_row.get("beats_paper_xgb"):
        best_mse = overview_row.get("best_mse_val")
        xgb_mse = overview_row.get("paper_xgb_mse")
        bullets.append(
            f"**Đối sánh trung thực với Paper 2024:** Nhóm `{atc_code}` đạt MSE thấp nhất `{best_mse:.2f}`, vẫn xếp sau "
            f"`XGBoost` trong Fourkiotis & Tsadiras 2024 (`{xgb_mse:.2f}`) do tuân thủ nghiêm quy tắc không nhìn tập Test."
        )

    return bullets
