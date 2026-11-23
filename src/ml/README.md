# 📈 PharmaFlow Module 01 — ML Dự báo Nhu cầu Dược phẩm (`DATA -> FORECAST`)

**Phạm vi:** Dự báo sản lượng bán ra (`observed_qty`) ở tầng **Prediction Quality** (`DATA -> FORECAST`) trên dữ liệu thực tế `provenance_class = 'OBSERVED'` của **1 nhà thuốc 6 năm** (`store_id = 5631`, `PHARMA_SALES_DAILY_ATC`, `2014-01-02 → 2019-10-08`, `16,848` dòng × `8` nhóm ATC) ghép với **thời tiết Open-Meteo ERA5** (`2,080` ngày) và **lịch nghỉ lễ Serbia** (`75` ngày). Không suy diễn hay bịa đặt cột tồn kho, cờ `stockout`, Safety Stock hay Reorder Point (ROP).

---

## 📚 Tài liệu Chi tiết & Google Docs Đầy đủ (4 Tab)

> **Xem bản Tài liệu Thiết kế, Phân tích 7 Bài báo & Kết quả Chi tiết nhất trên Google Docs:**
> * 📖 **[Tài liệu Google Docs Đầy đủ (4 Tab)](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit)**
>   * **Tab 1 — Tổng quan Nghiên cứu 7 Bài báo (2022–2026):** [Mở Tab 1](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.str8dzlshch7)
>   * **Tab 2 — Tổng quan Kiến trúc & Phương pháp Luồng Thống nhất:** [Mở Tab 2](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.0)
>   * **Tab 3 — Thiết kế Gold, Đối sánh Paper 2024 & Kết quả Thực nghiệm:** [Mở Tab 3](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.s40qjatkb5g8)
>   * **Tab 4 — Hướng dẫn Hiện thực 5 Notebooks (1 Luồng Thống nhất):** [Mở Tab 4](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.3fqlb8ix6shl)

**Bản Markdown đồng bộ trong repo:**
* [demand-forecasting-literature-review.md](../../docs/design/demand-forecasting-literature-review.md) — Cơ sở khoa học từ 7 bài báo (2022–2026)
* [demand-forecasting-solution.md](../../docs/design/demand-forecasting-solution.md) — Giải pháp, hồ sơ 8 nhóm ATC, thiết kế chuẩn & bảng đối chiếu kết quả
* [demand-forecasting-colab-step-by-step.md](../../docs/design/demand-forecasting-colab-step-by-step.md) — Hướng dẫn hiện thực từng bước trên `.venv` hoặc Google Colab

---

## 🔄 Luồng Thống nhất 5 Notebooks (`01 → 05`)

Pipeline được xây dựng thành **1 luồng thống nhất duy nhất** chạy tuần tự từ `01 → 05` (`Exit code 0`, tổng thời gian chạy trọn `5` fold tuần + `Daily 365D` là **`166.6s`**, nhanh gấp **`1,166.9×`** so với `54 giờ` Grid Search của Fourkiotis & Tsadiras, 2024):

| Bước | Notebook | Nhiệm vụ Cốt lõi | Kiểm soát Chất lượng & Chống Rò rỉ |
| :-: | :--- | :--- | :--- |
| **01** | [01_data_and_feature_collection.ipynb](./01_data_and_feature_collection.ipynb) | Trích 2 bảng Gold (`mart_sales_observation_period`, `mart_sales_weather_daily`) + lịch lễ Serbia `holidays.country_holidays('RS')`. | Assert `16,848` dòng `OBSERVED`, `0` trùng khóa, `0` ngày thiếu, ngày bắt đầu ERA5 = `2014-01-02`, lưu SHA-256 trong `data_manifest.json`. |
| **02** | [02_eda_and_statistical_diagnostics.ipynb](./02_eda_and_statistical_diagnostics.ipynb) | Chẩn đoán 8 nhóm ATC (`ADI/CV²`, `ADF`, `KPSS`, `Ljung-Box`, `Mann-Kendall`, `Shapiro-Wilk`, `STL`, `CCF` thời tiết). | Chứng minh `26` ngày khuyết ERA5 khớp 100% `26` ngày đóng cửa lễ có `total qty = 0.00`; xuất `eda_diagnostics_8atc.csv` + `4` hình 300 DPI. |
| **03** | [03_preprocessing_and_feature_engineering.ipynb](./03_preprocessing_and_feature_engineering.ipynb) | Tiền xử lý & tạo Feature Store Tuần (`302W`) và Ngày (`2,106D`) gồm `F1` nội sinh, `F2` lịch/tỷ trọng và **Compact 7-biến ERA5 (`F3`)**. | Chuẩn hóa tốc độ bán ngày `qty_rate = qty / active_days`; bỏ `uv_index_max` (100% NULL); thuần `.ffill()` (không `.bfill()`); loại `is_holiday_zero(t)`; **Perturbation Leakage Unit-Test `max_abs_diff == 0.0`** trên cả Weekly & Daily. |
| **04** | [04_modeling_tuning_and_ablation.ipynb](./04_modeling_tuning_and_ablation.ipynb) | Chạy `12` mô hình qua `5` fold tuần (`holdout_52w` + `roll_f1..roll_f4`) & `Daily 365D`: 4 Baselines/Stat (`SNaïve`, `SNaïve_W`, `Harmonic_ARIMA`, `Croston_SBA`), `Ridge_F1F2F3`, `LightGBM` (`F1/F1F2/F1F2F3/LagOnly`, `AnchorRes_F3`), `Expanding-Block OOF Hybrid` (`26W` + `1% Val Guard`), `AutoRouted_Champion`. | Chọn `AutoRouted_Champion` mù Test theo `Validation MAE` thấp nhất; hiệu chuẩn khoảng tin cậy **Split CQR `P10/P50/P90`**; tính **TreeSHAP** (`pred_contrib=True`); `100%` dự báo `>= 0`, `0` NaN. |
| **05** | [05_evaluation_xai_and_serving.ipynb](./05_evaluation_xai_and_serving.ipynb) | Ghép `y_true/y_pred`, đánh giá `MSE/RMSE/MAE/WAPE/MASE/Bias`, phân tích độ nhạy `51W vs 52W`, Ablation `F1 → F1F2 → F1F2F3`, ổn định `4-Fold`, kiểm định `Modified Diebold–Mariano (DM')`, độ phủ CQR & đối sánh 2 tầng Paper 2024. | Xuất toàn bộ bảng CSV đánh giá, `model_card.json`, `training_summary.json` và `3` biểu đồ 300 DPI phục vụ báo cáo & Dashboard BI. |

---

## 📊 Kết quả Thực nghiệm Đã Kiểm chứng (`holdout_52w: W251–W302`)

| Nhóm ATC | `AutoRouted_Champion` *(Chọn theo Val MAE)* | `MSE` thấp nhất *(Post-hoc)* | `SNaïve` / `SNaïve_W` *(MSE · WAPE)* | Paper 2024 *(Bảng 2 MSE)* | Split CQR `80%` *(Raw → CQR)* & `F3 SHAP` |
| :--- | :--- | :--- | :---: | :--- | :---: |
| **M01AB** | `Croston_SBA` (`WAPE 15.74%`, `MSE 58.24`, `MASE 0.614`) | **`Ridge_F1F2F3`** (`MSE 52.68`, `WAPE 15.03%`) | `107.08 (22.96%)` / `72.49 (18.51%)` | `SN_W: 49.19` · `XGB: 54.81` | `78.8% → 82.7%` · `16.1%` |
| **M01AE** | `Ridge_F1F2F3` (`WAPE 25.17%`, `MSE 72.64`, `MASE 0.993`) | `AnchorRes_F3` (`MSE 67.56`, `WAPE 25.13%`) | `105.88 (29.42%)` / `86.98 (28.18%)` | `XGB: 28.80` · `LSTM: 58.04` | `63.5% → 63.5%` · `11.3%` |
| **N02BA** | `Harmonic_ARIMA` (`WAPE 20.92%`, `MSE 29.06`, `MASE 0.623`) | **`LightGBM_F1F2`** (`MSE 27.72`, `WAPE 20.67%`) | `52.07 (27.57%)` / `75.57 (33.11%)` | `ARIMA_R: 28.34` · `XGB: 40.69` | `76.9% → 75.0%` · `19.7%` |
| **N02BE** | `LightGBM_F1F2F3` (`WAPE 15.44%`, `MSE 2042.84`, `MASE 0.523`) | **`AnchorRes_F3`** (`MSE 1392.20`, `WAPE 12.96%`) | `3605.15 (21.83%)` / `2404.25 (15.27%)` | `XGB: 1518.56` · `TES: 2190.53` | `55.8% → 78.8%` · `16.4%` |
| **N05B** | **`AnchorRes_F3`** (`WAPE 16.49%`, `MSE 139.66`, `MASE 0.365`) | **`Ridge_F1F2F3`** (`MSE 118.65`, `WAPE 15.55%`) | `450.79 (28.04%)` / `239.42 (20.27%)` | `DES: 140.76` · `XGB: 260.52` | `90.4% → 73.1%` · `17.3%` |
| **N05C** | `LightGBM_F1F2F3` (`WAPE 47.94%`, `MSE 8.66`, `MASE 0.720`) | **`Croston_SBA`** (`MSE 7.76`, `WAPE 44.24%`) | `21.75 (69.62%)` / `10.95 (54.13%)` | `SES: 7.19` · `SN_W: 7.85` · `XGB: 7.90` | `71.2% → 86.5%` · `50.5%` |
| **R03** | `AnchorRes_F3` (`WAPE 38.32%`, `MSE 688.80`, `MASE 1.182`) | `Harmonic_ARIMA` (`MSE 662.25`, `WAPE 37.56%`) | `1142.61 (49.34%)` / `1087.25 (46.80%)` | `XGB: 350.84` · `LSTM: 577.66` | `65.4% → 88.5%` · `18.9%` |
| **R06** | **`AnchorRes_F3`** (`WAPE 24.67%`, `MSE 57.04`, `MASE 0.830`) | **`LightGBM_F1F2`** (`MSE 49.75`, `WAPE 23.26%`) | `137.75 (36.75%)` / `86.50 (27.56%)` | `TES: 59.77` · `XGB: 63.85` | `71.2% → 82.7%` · `25.9%` |

**Điểm chốt ngắn gọn:**
* **Thắng Baseline nội bộ:** `AutoRouted_Champion` đánh bại `Seasonal_Naive` với `DM' p < 0.05` trên **`8/8` nhóm ATC**; giảm `MSE` so với `Seasonal_Naive_Weighted` trên **`8/8` nhóm**, giảm `WAPE` trên **`7/8` nhóm** (`4/8` đạt `DM' p < 0.05`, `N05B p = 0.0506`), và đạt `MASE < 1.0` ở **`7/8` nhóm**.
* **So với Fourkiotis & Tsadiras (2024):** Vượt MSE Bảng 2 của bài báo trên **`6/8` nhóm ATC** (`M01AB`, `N02BA`, `N02BE`, `N05B`, `N05C`, `R06`); còn `M01AE` (`67.56` vs `28.80`) và `R03` (`662.25` vs `350.84`) vẫn xếp sau `XGBoost` của bài báo.
* **Giá trị Thời tiết ERA5 (`F3`) & Độ bất định:** `Compact ERA5` cải thiện lỗi tại `5/8` nhóm tuần (`N05B DM' p = 0.0339`) và `N05C Daily 365D` (`DM' p = 0.0096`), đóng góp `11.3%–25.9%` tổng L2 `|TreeSHAP|` (`N05C` Tweedie `50.5%`); `Split CQR` nâng độ phủ trung bình `P10–P90` từ **`71.7% → 78.8%`**.

---

## 📦 Danh mục Artifacts Bàn giao (`artifacts/forecasting/`)

Thư mục [`../../artifacts/forecasting/`](../../artifacts/forecasting/) chứa đầy đủ đầu ra của lần chạy chuẩn hóa:
* **Dữ liệu nguồn & Feature Store:** `raw_sales_5631.parquet`, `raw_weather_5631.parquet`, `raw_holidays_rs.parquet`, `data_manifest.json`, `feature_store_weekly.parquet`, `feature_store_daily.parquet`, `feature_catalog.json`.
* **Dự báo & Giải thích (`.parquet`):** `predictions_holdout_52w.parquet`, `predictions_rolling_4folds.parquet`, `predictions_quantiles_52w.parquet`, `predictions_daily_365d.parquet`, `shap_values_52w.parquet`.
* **Bảng đánh giá & Siêu dữ liệu (`.csv`, `.json`):** `eda_diagnostics_8atc.csv`, `metrics_by_atc.csv`, `ablation_f1_f2_f3.csv`, `rolling_4folds_stability.csv`, `dm_test_results.csv`, `daily_365d_metrics.csv`, `quantiles_coverage.csv`, `sensitivity_51w_vs_52w.csv`, `benchmark_vs_paper2024.csv`, `model_card.json`, `training_summary.json`.
* **Biểu đồ 300 DPI (`.png`):** `eda_01_small_multiples_6y.png`, `eda_02_syntetos_boylan_quadrant.png`, `eda_03_stl_n02be_vs_n05b.png`, `eda_04_weather_ccf.png`, `eval_ablation_wape.png`, `eval_treeshap_summary.png`, `eval_fanchart_52w.png`.

---

## 🚀 Cách chạy lại Pipeline

* **Phân tách kết nối:** Chỉ **Notebook 01** (tùy chọn Neon BI ở Notebook 05) cần `.env` chứa `QUICK_NEON_DATABASE_URL` và `QUICK_NEON_SCHEMA=quick_gold_md01`. Các Notebook **02 → 05** chạy **100% offline** từ snapshot trong `artifacts/forecasting/`.
* **Thư viện ML bổ sung** (ngoài `requirements.txt` cơ bản): `lightgbm`, `statsmodels`, `scikit-learn`, `scipy`, `holidays`, `pyarrow`, `matplotlib`, `seaborn`, `psycopg[binary]`.
* **Chạy trên Local `.venv` (ví dụ thực thi tuần tự cả 5 notebooks bằng `nbclient`/`jupyter`):**
  ```powershell
  # Chạy trực tiếp trên VS Code / Jupyter hoặc tuần tự NB01 -> NB05 từ gốc BTL_BI/
  .\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace src\ml\01_data_and_feature_collection.ipynb
  .\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace src\ml\02_eda_and_statistical_diagnostics.ipynb
  .\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace src\ml\03_preprocessing_and_feature_engineering.ipynb
  .\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace src\ml\04_modeling_tuning_and_ablation.ipynb
  .\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace src\ml\05_evaluation_xai_and_serving.ipynb
  ```
* **Chạy trên Google Colab Pro:** Mở lần lượt `01 → 05` trong VS Code Colab Extension hoặc Colab Web và nhớ đóng runtime (`Colab: Remove Server`) sau khi xong — xem chi tiết tại [demand-forecasting-colab-step-by-step.md](../../docs/design/demand-forecasting-colab-step-by-step.md).

---

## 🔗 Kết nối đề xuất với Streamlit BI Dashboard

Trang 5 của Dashboard BI ([`src/streamlit/pages/05_du_bao_nhu_cau.py`](../streamlit/pages/05_du_bao_nhu_cau.py) · [src/streamlit/README.md](../streamlit/README.md)) đọc trực tiếp các artifact dự báo đã tính sẵn trong `artifacts/forecasting/` qua `@st.cache_data` (hiển thị Fan Chart `52W/365D`, Split CQR `P10–P90`, `TreeSHAP` tiếng Việt và bảng đối chuẩn Paper 2024) mà không huấn luyện mô hình trực tiếp trong ứng dụng web.
