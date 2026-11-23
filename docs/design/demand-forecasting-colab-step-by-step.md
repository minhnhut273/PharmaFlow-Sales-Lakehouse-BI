# Hướng dẫn Hiện thực Step-by-Step ML Lifecycle — Luồng Thống nhất 5 Notebooks (Google Colab)

**Môi trường mục tiêu:** Google Colab Pro (VS Code Extension) hoặc `.venv` Local  
**Kiến trúc Code:** 1 Luồng thống nhất gồm `5` Notebooks nối tiếp tại `BTL_BI/src/ml/`  
**Trạng thái:** Đã chạy kiểm chứng 100% (`Exit 0`, tổng thời gian `166.6s`, Weekly & Daily Perturbation Leakage Diff = `0.0`)  
**Nguồn dữ liệu:** 100% từ tầng Gold (`quick_gold_md01` / `pharmaflow_dev.gold_md01_sales`, `store_id = 5631`) + Lịch nghỉ lễ chính thức Serbia (`holidays`)  
**Tài liệu Google Docs đầy đủ (4 Tab):** [Mở Google Docs](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit) · [Tab 4 — Hướng dẫn Hiện thực 5 Notebooks](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.3fqlb8ix6shl)  
**Tài liệu nền tảng trong Repo:** [src/ml/README.md](../../src/ml/README.md) · [demand-forecasting-literature-review.md](./demand-forecasting-literature-review.md) · [demand-forecasting-solution.md](./demand-forecasting-solution.md)

> **Lưu ý khi chạy Google Colab Pro trên VS Code & Quản lý Compute:**
> * **Chỉ Notebook 01** (và tùy chọn đẩy Neon BI ở **Notebook 05**) cần kết nối DB (`QUICK_NEON_DATABASE_URL` qua `.env` Local, Colab Secrets hoặc `getpass()`).
> * **Các Notebook 02 → 04** chạy hoàn toàn **offline** bằng snapshot `.parquet` và `.json` trong `BTL_BI/artifacts/forecasting/`.
> * Khi chạy xong nhớ bấm `Ctrl+Shift+P` → **`Colab: Remove Server`** để ngắt máy ảo, tránh tiêu tốn Compute Units ngoài ý muốn.

---

## Tổng quan Luồng Hiện thực Thống nhất — 5 Notebooks ML Lifecycle

Quy trình chạy xuyên suốt từ `01 → 05` theo đúng các mắt xích chuẩn của vòng đời ML:

| # | Notebook (`BTL_BI/src/ml/`) | Khâu ML Chuẩn | Hoạt động Cốt lõi | Artifact Bàn giao Chính |
| :-: | :--- | :--- | :--- | :--- |
| **1** | `01_data_and_feature_collection.ipynb` | **Data & Feature Collecting** | Kéo 2 bảng Gold + lịch lễ Serbia; kiểm tra trùng khóa, ngày thiếu, `provenance_class == 'OBSERVED'` & min date thời tiết. | `raw_sales_5631.parquet`, `raw_weather_5631.parquet`, `raw_holidays_rs.parquet`, `data_manifest.json` |
| **2** | `02_eda_and_statistical_diagnostics.ipynb` | **Deep EDA & Diagnostics** | Sinh bảng chẩn đoán 8 ATC (`ADI/CV²`, `ADF/KPSS/LB/MK/SW`, `STL`, `CCF` ERA5) & ánh xạ chọn mô hình cho từng nhóm. | `eda_diagnostics_8atc.csv` + **4 hình EDA 300 DPI** |
| **3** | `03_preprocessing_and_feature_engineering.ipynb` | **Preprocessing, Rate FE & Leakage Audit** | Chuẩn hóa `qty_rate = qty / active_days`; thuần `.ffill()` (bỏ `uv_index_max`); bỏ `is_holiday_zero(t)`; `Compact 7 ERA5`; perturbation unit-test `= 0.0`. | `feature_store_weekly.parquet`, `feature_store_daily.parquet`, `feature_catalog.json` |
| **4** | `04_modeling_tuning_and_ablation.ipynb` | **Backtest, Tuning, Router & CQR** | `5` fold tuần × `12` mô hình (`Ridge`, `AnchorRes`, Exp-Block OOF Hybrid, `AutoRouter`) + Split CQR `P10–P90` + Daily `365D` (`166.6s`). | `predictions_holdout_52w.parquet`, `rolling_4folds`, `quantiles_52w`, `daily_365d`, `shap_values_52w.parquet` |
| **5** | `05_evaluation_xai_and_serving.ipynb` | **Evaluation, XAI & Benchmark** | Ghép `y_true/y_pred`; bảng `52W/51W`, Ablation, 4-Fold Stability, `DM'`, `CQR Cov`, `TreeSHAP` & 2-Tier Paper 2024. | `metrics_by_atc.csv`, `ablation_f1_f2_f3.csv`, `dm_test_results.csv`, `model_card.json` |

---

## Notebook 01 — Data & Feature Collecting (`01_data_and_feature_collection.ipynb`)

1. **Nguồn gốc (`Provenance`):** Truy vấn `mart_sales_observation_period` (`source = 'PHARMA_SALES_DAILY_ATC'`, `store_id = 5631`, `subject_kind = 'CATEGORY'`) và khẳng định `100%` dòng mang nhãn `OBSERVED`.
2. **Kiểm tra Trùng khóa & Ngày thiếu:** Assert `0` bản ghi trùng `(atc_code, local_date)` và khớp đủ `2,106` ngày liên tục (`2014-01-02 → 2019-10-08`) cho cả 8 nhóm ATC (`8 × 2,106 = 16,848` dòng).
3. **Kiểm tra Mốc Thời tiết ERA5 & Thu thập Lịch lễ Serbia:** Xác nhận `mart_sales_weather_daily` bắt đầu đúng `2014-01-02` (`2,080` ngày quan sát) nên Notebook 03 chỉ cần `.ffill()` (không dùng `.bfill()`). Thu thập ngày lễ Serbia `2014–2019` qua `holidays.country_holidays('RS')`, lưu 3 file Parquet và `data_manifest.json` (SHA-256).

```python
assert len(df_sales) == 16848 and (df_sales['qty'] >= 0).all()
assert set(df_sales['provenance_class'].unique()) == {'OBSERVED'}
assert not df_sales.duplicated(['atc_code', 'local_date']).any()
exp_days = pd.date_range('2014-01-02', '2019-10-08', freq='D')
for atc, g in df_sales.groupby('atc_code'):
    missing = set(exp_days) - set(pd.to_datetime(g['local_date']))
    assert len(missing) == 0, f'{atc} missing {len(missing)} days'
assert pd.to_datetime(df_weather['local_date']).min() == exp_days[0]
rs_hol = holidays.country_holidays('RS', years=range(2014, 2020))
```

---

## Notebook 02 — Deep EDA & Statistical Diagnostics (`02_eda_and_statistical_diagnostics.ipynb`)

* Sinh bảng `eda_diagnostics_8atc.csv` (`ADI/CV²`, `ADF`, `KPSS`, `Ljung–Box`, `Mann–Kendall`, `Shapiro–Wilk`, `ACF(1)_W`, `ACF(52)_W`, `STL`) và kiểm chứng `26` ngày thiếu trong `raw_weather_5631` trùng khớp `26` ngày có tổng bán = `0.00`.
* **Ánh xạ kết quả chẩn đoán → lựa chọn mô hình:**

| Nhóm ATC Tiêu biểu | Phát hiện Chẩn đoán Chính trên Gold | Tác động Trực tiếp tới Lựa chọn Mô hình |
| :--- | :--- | :--- |
| **M01AB** *(NSAID acetic)* | Smooth (`ADI 1.02`, `CV² 0.27`), không chu kỳ năm (`ACF52 = 0.02`), gần chuẩn (`SW p=0.069`). | Giữ `Seasonal Naïve` làm mốc cứng; `Ridge` & `AnchorRes` ngoại suy mượt thắng `XGBoost` Paper. |
| **N02BA & N05B** *(Aspirin, An thần)* | `N02BA` giảm dài hạn (`MK p<0.0001`) + mùa đông; `N05B` trôi mức, 0% chu kỳ năm (`ACF52 = −0.04`). | Ưu tiên `Harmonic ARIMA`, `Ridge` & `AnchorRes` bắt xu hướng mượt; guard `1%` Val chặn Hybrid trượt trend. |
| **N05C** *(An thần / Ngủ)* | Intermittent nặng: `67.9%` ngày = 0, `36/302` tuần = 0 (`ADI 3.12`); Paper 2024 nổ `MAPE = inf%`. | Bổ sung baseline chuyên biệt **`Croston-SBA`** (kèm `LightGBM Tweedie` + `WAPE/MASE`). |
| **N02BE, R03, R06** *(Sốt, Hen, Dị ứng)* | `N02BE` (`ACF52=0.53`), `R03` Erratic (`CV²=0.82`), `R06` chu kỳ xuân–hè (`ACF12=0.77`). | Phù hợp `LightGBM` / `AnchorRes` + `Compact 7 ERA5` & Split CQR `P10–P90`. |

* Xuất 4 biểu đồ EDA 300 DPI (`eda_01_small_multiples_6y.png`, `eda_02_syntetos_boylan_quadrant.png`, `eda_03_stl_n02be_vs_n05b.png`, `eda_04_weather_ccf.png`).

---

## Notebook 03 — Preprocessing, Rate Normalization & Leakage Audit (`03_preprocessing_and_feature_engineering.ipynb`)

> **Chốt chặn Chống rò rỉ & Chuẩn hóa Tốc độ Ngày (`qty_rate`):**
> 1. **Loại bỏ `is_holiday_zero(t)` khỏi `F2`:** Chỉ dùng cho kiểm toán EDA ở Notebook 02; thay bằng lịch lễ biết trước **`is_rs_holiday`** và biến trễ quá khứ **`is_holiday_zero_lag1`**.
> 2. **Xóa `.bfill()` trên cột thời tiết:** Bỏ cột 100% NULL `uv_index_max`, chỉ dùng **`.ffill()`** theo chiều xuôi và assert `0` NaN.
> 3. **Calendar-Exposure Rate Normalization:** Chia `qty_rate = qty / active_days`, tính toàn bộ `F1` trên `qty_rate` (`.shift(1)`), và dùng `active_days` thuần làm hệ số nhân phục hồi (`ŷ = r̂ · active_days`) — loại bỏ triệt để đột biến MSE ở tuần cụt `W302` (`2` ngày).

| Tầng Đặc trưng | Biến Tạo theo Từng Mốc Dự báo (Không Rò rỉ) | Quy tắc Chống Rò rỉ & Chuẩn hóa |
| :--- | :--- | :--- |
| **F1 — Lịch sử nội sinh** *(trên `qty_rate`)* | `lag_1, lag_2, lag_3, lag_4, lag_8, lag_12, lag_52`; `rolling_mean_4/12`, `rolling_std_4/12`, `rolling_max_4`, `ewma_4`, `zero_ratio_12` | Chuẩn hóa tốc độ `qty_rate = qty / active_days` rồi `.shift(1)` trước `rolling/ewm`. |
| **F2 — Lịch & Tỷ trọng** *(Đã bỏ `is_holiday_zero`)* | `week_sin52, week_cos52, week_sin26, week_cos26`, `time_idx`, `is_rs_holiday`, `atc_share_lag1`, `is_holiday_zero_lag1` | Không đưa `active_days` vào biến cây; `is_rs_holiday` biết trước cho mọi kỳ. |
| **F3 — Thời tiết ERA5** *(Compact `7` biến tuần)* | `temp_mean, hdd, humidity_mean, daylight_duration_s, temp_shock_2w, temp_mean_lag1, humidity_mean_lag1` *(Daily: `13` biến)* | Thuần `.ffill()`; lưu thêm `f3_lagged_only_cols` (`8` biến) & `f3_all_cols` (`19` biến) trong `feature_catalog.json`. |

```python
df_daily[w_cols] = df_daily.groupby('atc_code')[w_cols].ffill()
assert df_daily[w_cols].isna().sum().sum() == 0  # Không dùng .bfill()

# Perturbation Leakage Unit-Test (sửa Test W251..302 -> W1..W251 bất biến)
df_mut = df_weekly.copy()
df_mut.loc[df_mut['week_idx'] >= 250, 'qty'] *= 99.0
df_feat_mut, *_ = build_weekly_features(df_mut)
m = df_feat['week_idx'] <= 250
assert (df_feat.loc[m, weekly_all_cols].fillna(-9999) - df_feat_mut.loc[m, weekly_all_cols].fillna(-9999)).abs().max().max() == 0.0
```

---

## Notebook 04 — Unified Backtest Harness, Modeling, OOF Hybrid & CQR (`04_modeling_tuning_and_ablation.ipynb`)

* **1 Luồng Backtest Thống nhất qua `5` Fold Tuần (`holdout_52w` + `roll_f1..roll_f4`) + `Daily 365D`:**
  1. **Baselines (`Tier 1 & Paper 2024`):** `Seasonal_Naive (y[t−52])`, `Seasonal_Naive_Weighted ([0.4, 0.3, 0.2, 0.1])`, `Harmonic_ARIMA` (trên `qty_rate`), `Croston_SBA` (trên `qty_rate`).
  2. **Ngoại suy & Ablation:** `Ridge_F1F2F3` (`StandardScaler + RidgeCV`), `LightGBM_AnchorRes_F3` (học phần dư quanh `EWMA_4` để phá trần cây), và `LightGBM_F1 / F1F2 / F1F2F3 (Compact ERA5) / LagOnly` kèm exact **TreeSHAP (`pred_contrib=True`)**.
  3. **Expanding-Block OOF Hybrid:** Refit mở rộng mỗi `26` tuần qua `[104..val_end)` để sinh phần dư ngoài mẫu đồng nhất phân phối + cơ chế **chặn 1% Validation Guard** (`α* = 0` nếu cải thiện trên Val `< 1%`).
  4. **`AutoRouted_Champion` & Split CQR Quantiles (`P10/P50/P90`):** Tự chọn mô hình thắng theo `Validation MAE` thấp nhất (không chạm Test) và hiệu chuẩn biên tin cậy Split Conformal (Romano et al., 2019).
* **Đầu ra đã kiểm chứng (`166.6s` toàn luồng):** `predictions_holdout_52w.parquet` (`4,992` dòng), `predictions_rolling_4folds.parquet` (`4,576` dòng), `predictions_quantiles_52w.parquet` (`416` dòng), `predictions_daily_365d.parquet` (`8,760` dòng) và `shap_values_52w.parquet`.

---

## Notebook 05 — Evaluation, Ablation, DM', CQR & Paper 2024 Benchmark (`05_evaluation_xai_and_serving.ipynb`)

* Ghép `y_true` và `y_pred` tính đầy đủ `MSE`, `RMSE`, `MAE`, `WAPE (%)`, `MASE`, `Bias (%)`, kiểm chứng `AutoRouted_Champion` thắng `Seasonal_Naive` ở **`8/8` nhóm (`DM' p < 0.05`)**, vượt **MSE của Paper 2024 tại `6/8` nhóm** (`M01AB 52.68`, `N02BA 27.72`, `N02BE 1392.20`, `N05B 118.65`, `N05C 7.76`, `R06 49.75`), Split CQR đạt độ phủ TB **`78.8%`** (`N02BE` nhảy từ `55.8% → 78.8%`).
* Xuất `metrics_by_atc.csv`, `sensitivity_51w_vs_52w.csv`, `ablation_f1_f2_f3.csv`, `rolling_4folds_stability.csv`, `dm_test_results.csv`, `quantiles_coverage.csv`, `benchmark_vs_paper2024.csv`, `3` hình 300 DPI (`eval_ablation_wape.png`, `eval_treeshap_summary.png`, `eval_fanchart_52w.png`) và `model_card.json`.
