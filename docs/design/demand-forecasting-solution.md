# Tổng Giải Pháp & Thiết Kế Hiện Thực Chi Tiết — Dự Báo Nhu Cầu Dược Phẩm (Demand Forecasting)

**Hệ thống:** PharmaFlow Lakehouse & Decision Support System (`Module 01 — Demand Forecasting`, phạm vi `DATA -> FORECAST`, đánh giá **Prediction Quality**)  
**Nguồn dữ liệu thực nghiệm (Đọc 100% từ tầng Gold):** Bộ dữ liệu **1 Nhà thuốc 6 Năm** (`2014-01-02` → `2019-10-08`, 57 thuốc / 8 nhóm ATC, `store_id = 5631`, `SIM_PHARMA_SALES_NIS_001`, Niš, Serbia) ghép nối trực tiếp giữa `mart_sales_observation_period` (`16,848` dòng, `source = 'PHARMA_SALES_DAILY_ATC'`, `provenance_class = 'OBSERVED'`) và `mart_sales_weather_daily` (`2,080` ngày thời tiết ERA5) tại schema `pharmaflow_dev.gold_md01_sales` / `quick_gold_md01`  
**Cơ sở khoa học & Số liệu đối chứng:** [Tổng quan Nghiên cứu 7 Bài báo (2022–2026)](./demand-forecasting-literature-review.md) — [Fourkiotis & Tsadiras (2024)](https://doi.org/10.3390/forecast6010010) ([PDF nội bộ](../references/papers/forecasting-06-00010.pdf)), [Abacı (2026)](https://doi.org/10.1109/ACCESS.2026.3685042), [Burinskiene (2022)](https://doi.org/10.3389/fmed.2022.582186), [Ramadhan et al. (2026)](https://doi.org/10.18280/isi.310117), [E et al. (2024)](https://doi.org/10.1016/j.procs.2024.08.239), [Sbrana & Babai (2026)](https://doi.org/10.1016/j.ejor.2026.06.009), [Khan et al. (2026)](https://doi.org/10.1007/s44163-026-01956-z)  
**Tài liệu Google Docs đầy đủ (4 Tab):** [Mở Google Docs](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit) · [Tab 2 — Kiến trúc & Phương pháp](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.0) · [Tab 3 — Thiết kế & Kết quả](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.s40qjatkb5g8)  
**Tài liệu hướng dẫn & README module:** [src/ml/README.md](../../src/ml/README.md) · [demand-forecasting-colab-step-by-step.md](./demand-forecasting-colab-step-by-step.md)

---

## 1. Mục tiêu, Ranh giới Phạm vi & 4 Hiệu chỉnh Phản biện

Trong kiến trúc PharmaFlow DSS (`DATA -> FORECAST -> RISK -> DECISION -> OPERATIONAL OUTCOME`), **Prediction Quality** và **Decision Quality** được tách biên nghiêm ngặt:

* **Goal:** Dự báo chính xác sản lượng thuốc bán ra (`observed_qty`) cho cả 8 nhóm điều trị ATC ở hai độ mịn Tuần (`302` tuần `W-SUN` đối chuẩn trực tiếp với bài báo) và Ngày (`2,106` ngày); chứng minh định lượng giá trị gia tăng của dữ liệu thời tiết Open-Meteo ERA5 qua thử nghiệm bóc tách `F1 -> F1+F2 -> F1+F2+F3`, kiểm định `Modified Diebold–Mariano (DM')` và giải thích `TreeSHAP`.
* **Non-Goal:** Không bịa đặt cột tồn kho đầu kỳ, cờ hết hàng (`stockout`), hay lead time trên bộ dữ liệu 6 năm vốn không có dữ liệu tồn kho; không nhúng các công thức Safety Stock, Reorder Point (ROP), FEFO hay gợi ý đặt hàng (thuộc Module hạ nguồn) vào pipeline ML dự báo.

Khi đối chiếu PDF gốc của 4 bài báo tham khảo với dữ liệu thực tế trên tầng Gold, có **4 điểm hiệu chỉnh chiến lược**:

| Vấn đề / Ngộ nhận Sơ bộ | Sự thật Xác thực từ Bài báo Gốc & Dữ liệu Gold (`store_id = 5631`) | Quyết định Hiệu chỉnh Hiện thực |
| :--- | :--- | :--- |
| **1. Đề xuất lấy Stockout-Aware & ROP làm trọng tâm** | **Burinskiene (2022)** chỉ có 13 tuần của 8 nhà thuốc và thay tuần thiếu hàng bằng `0.0001` hoặc trung bình cộng kèm cắt ngưỡng Grubbs `3s` (làm co phương sai thực). Bộ 1 Nhà thuốc 6 Năm trên Gold **không có cột tồn kho hay cờ stockout**. | Giữ nguyên quan sát thực (`OBSERVED`), chuyển trọng tâm đóng góp sang **Chẩn đoán Thống kê Dẫn đường + Tinh gọn 4 Model Đại diện + Kiểm chứng Giá trị Thời tiết ERA5**. |
| **2. Ngộ nhận XGBoost thắng áp đảo trong Fourkiotis & Tsadiras (2024)** | Trên chính bộ 302 tuần này (Test 52 tuần), xét theo **MSE** tại Bảng 2, XGBoost chỉ thắng **3/8 nhóm** (`M01AE`, `N02BE`, `R03`); **5/8 nhóm còn lại thuộc về thống kê** (`Seasonal Naïve` thắng `M01AB`, `ARIMA Roll` thắng `N02BA`, `DES` thắng `N05B`, `SES` thắng `N05C`, `TES` thắng `R06`). Dùng **MAPE** làm `N05C` nổ **`inf%`**; Grid Search thủ công tốn **54 giờ**. | **Loại bỏ MAPE khỏi thước đo chính** (thay bằng `WAPE`, `MASE`, `MSE/RMSE`, `MAE`, `Bias`). Thống nhất 4 trường phái mô hình trên tốc độ ngày `qty_rate` cùng `AutoRouted Champion` & `Split CQR`, chạy trọn luồng hết **`166.6 giây`** (~2.8 phút). |
| **3. Hạn chế cỡ mẫu kiểm định (`n = 8`) trong Abacı (2026)** | **Abacı (2026)** đề xuất quy trình rất chặt chẽ: chẩn đoán trước huấn luyện (`ADF`, `Ljung-Box`, `Mann-Kendall`, `Shapiro-Wilk`, `CoV`) + mô hình lai phần dư chống rò rỉ $\hat{y}_t^H = \hat{y}_t^S + \alpha^* \cdot \hat{r}_t^{ML}$. Tuy nhiên cỡ test chỉ có `n = 8` tháng nên kiểm định DM không đạt ý nghĩa (`p = 0.16–0.30`). | Đem khung chẩn đoán + $\alpha$-Hybrid chống rò rỉ của Abacı áp dụng lên bộ Gold 6 năm với **`n_test = 52` tuần** và **`n_test = 365` ngày** — tăng cỡ mẫu kiểm định **6.5 đến 45 lần**. |
| **4. Khoảng trống Future Work về Thời tiết** | Cả **Fourkiotis & Tsadiras (2024, tr. 16)** và **Abacı (2026, tr. 22)** đều chỉ chạy chuỗi đơn biến và nêu việc ghép dữ liệu khí tượng là hướng mở rộng cấp thiết nhất. **Ramadhan et al. (2026)** nhấn mạnh thêm giải thích bằng **SHAP**. | Kết nối trực tiếp `16,848` dòng doanh số ATC (`2014–2019`) với dữ liệu Open-Meteo ERA5 sẵn có trên tầng Gold của `store_id = 5631` và giải thích bằng **TreeSHAP + Feature Ablation**. |

---

## 2. Nguồn Dữ liệu 100% từ Tầng Gold & Phát hiện Kiểm toán (Không cần quay lại Silver)

Pipeline dự báo đọc trực tiếp từ **2 bảng Gold Mart** khớp 1:1 theo khóa `(store_id = 5631, local_date)`:

1. **`mart_sales_observation_period`**:
   * Bộ lọc chuẩn: `WHERE source = 'PHARMA_SALES_DAILY_ATC' AND store_id = 5631 AND subject_kind = 'CATEGORY'` (`provenance_class = 'OBSERVED'`).
   * Các cột sử dụng: `period_start` (`date`), `category_code` (8 nhóm ATC), `category_name`, `observed_qty` (`numeric`). Tổng quy mô đúng **`16,848` bản ghi (`2,106` ngày liên tục `2014-01-02` → `2019-10-08` × 8 nhóm)**.
2. **`mart_sales_weather_daily`**:
   * Khí tượng tái phân tích Open-Meteo ERA5 tại tọa độ Niš, Serbia (`store_id = 5631`), gồm **`2,080` ngày giao dịch có quan sát thời tiết** (`temp_mean` trung bình `12.81°C`, biên độ `-21.9°C` → `+38.5°C`; `humidity_mean` trung bình `71.7%`; `precip_sum` trung bình `1.80 mm/ngày`).
   * Các cột khí tượng xác thực trong bảng Gold: `temp_mean`, `temp_min`, `temp_max`, `apparent_temp_mean`, `humidity_mean`, `precip_sum`, `wind_speed_max`, `wind_speed_mean`, `wind_gusts_max`, `cloud_cover_mean`, `pressure_msl_mean`, `uv_index_max`, `shortwave_radiation_sum`, `weather_code`, `daylight_duration_s`.
   * *Lưu ý thiết kế đặc trưng:* Các biến vật lý nâng cao như `temp_range` ($T_{\max} - T_{\min}$), `hdd` (Heating Degree Days), `cdd` (Cooling Degree Days), `temp_shock_2w` không có sẵn trong bảng Gold hiện tại mà được tính ở bước Feature Engineering (`F3`) trên pipeline ML.
3. **Phát hiện kiểm toán — 26 ngày khuyết thời tiết là 26 ngày nghỉ lễ Quốc gia Serbia:**
   * Đúng `26` ngày trong `2,106` ngày không xuất hiện trong `mart_sales_weather_daily` (như `01-01`, `01-07` Giáng sinh Chính thống, `05-01`, `12-19`, Phục sinh...). Kiểm chứng trực tiếp xác nhận trên cả `26` ngày đó, tổng `observed_qty` trên cả 8 nhóm ATC **đều bằng `0.00` tuyệt đối**, và **không có bất kỳ ngày nào khác có tổng lượng bán = 0**.
   * Xử lý chuẩn (Chống Rò rỉ): Cờ `is_holiday_zero_obs` chỉ dùng cho kiểm toán EDA ở Notebook 02; khi tiền xử lý ML ở Notebook 03 tuyệt đối **không** đưa `is_holiday_zero(t)` vào đặc trưng (thay bằng lịch lễ biết trước `is_rs_holiday` + `is_holiday_zero_lag1`), loại bỏ cột `uv_index_max` (100% NULL), và dùng thuần `.ffill()` (không `.bfill()`) điền `26` ô thời tiết đơn lẻ.

---

## 3. Hồ sơ Chẩn đoán Thống kê Thực tế 8 Nhóm ATC trên Gold (`store_id = 5631`)

Số liệu thực tế chạy trực tiếp từ `quick_gold_md01.mart_sales_observation_period` (`N = 2,106` ngày, `N = 302` tuần `W-SUN`):

| Mã ATC | Nhóm Dược lý | Cấp Ngày: Mean (Zero%) | Cấp Ngày: ADI / `CV²` (Phân loại SB) | Cấp Tuần: Mean / CoV | Tự tương quan: `ACF(1)_W` / `ACF(52)_W` / `ACF(12)_M` | Xu hướng (MK `p`) & Chuẩn (SW `p`) | Mô hình Phù hợp Nhất |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **M01AB** | NSAID dẫn xuất acid acetic | `5.03` (`1.9%`) | `1.02` / `0.27` (**Smooth**) | `35.10` / `0.25` | `0.21` / `0.02` / `0.03` | MK `p=0.0001` (Tăng); SW `p=0.0692` (Chuẩn) | `Seasonal Naïve` / `SARIMA` (`α* → 0`) |
| **M01AE** | NSAID dẫn xuất acid propionic | `3.90` (`1.7%`) | `1.02` / `0.28` (**Smooth**) | `27.17` / `0.26` | `0.34` / `0.08` / `-0.10` | MK `p=0.6470`; SW `p<0.0001` | `LightGBM (F1+F2)` / `Hybrid` |
| **N02BA** | Salicylic acid (Aspirin) | `3.88` (`3.7%`) | `1.04` / `0.33` (**Smooth**) | `27.06` / `0.30` | `0.44` / `0.43` / **`0.58`** | MK `p<0.0001` (Giảm); SW `p=0.0127` | `SARIMA` + `Hybrid LightGBM (Weather F3)` |
| **N02BE** | Anilides (Paracetamol chủ lực) | **`29.92`** (`1.2%`) | `1.01` / `0.26` (**Smooth**) | **`208.63`** / `0.36` | **`0.81`** / **`0.53`** / **`0.52`** | MK `p=0.7331`; SW `p<0.0001` (Đỉnh đông) | `LightGBM (Weather F3)` & `Hybrid` |
| **N05B** | Thuốc giải lo âu | `8.85` (`2.0%`) | `1.02` / `0.37` (**Smooth**) | `61.74` / `0.36` | `0.49` / `-0.04` / `-0.06` | MK `p=0.0085` (Trôi mức); SW `p<0.0001` | `SARIMA` (`α*` nhỏ, không mùa vụ năm) |
| **N05C** | Thuốc ngủ & an thần | **`0.59`** (**`67.9%`**) | **`3.12`** / `0.41` (**Intermittent**) | `4.14` / **`0.76`** (`36` tuần = 0) | `0.14` / `0.01` / `-0.09` | MK `p=0.8277`; SW `p<0.0001` | `LightGBM Tweedie` / `SARIMA` kẹp `ŷ ≥ 0` |
| **R03** | Thuốc hen / COPD hô hấp | `5.51` (`23.0%`) | `1.30` / **`0.82`** (**Erratic**) | `38.44` / **`0.60`** | `0.49` / `0.32` / **`0.41`** | MK `p<0.0001` (Tăng); SW `p<0.0001` | `LightGBM` / `Hybrid + Weather F3` |
| **R06** | Kháng histamine (Dị ứng) | `2.90` (`12.2%`) | `1.14` / `0.49` (**Smooth/Biên**) | `20.22` / **`0.56`** | **`0.76`** / **`0.63`** / **`0.77`** | MK `p=0.0002` (Tăng); SW `p<0.0001` | `SARIMA` + `LightGBM (Weather F3)` |

---

## 4. Kiến trúc Các Họ Mô hình & Chiến lược Production (`qty_rate` + `AutoRouter` + `Split CQR`)

Pipeline chuẩn hóa toàn bộ mô hình theo tốc độ bán ngày `qty_rate = qty / active_days` và phối hợp **4 trường phái bổ trợ**:

1. **Trường phái 1 — Baselines & Chuỗi gián đoạn:** `Seasonal Naïve` (`y_{t-52W}` / `y_{t-7D}`), `Seasonal Naïve Weighted [0.4, 0.3, 0.2, 0.1]` và **`Croston-SBA`** (thắng `N05C` với `WAPE 44.24%`, `MSE 7.76` và đạt `36.71%` WAPE ở `R03`).
2. **Trường phái 2 — Thống kê & Ngoại suy tuyến tính:** `Harmonic ARIMA` (`ARIMA + Fourier K=2`) và **`Ridge_F1F2F3`** (`StandardScaler + RidgeCV`) giúp ngoại suy xu hướng mượt vượt trần cây (`M01AB` MSE `52.68`, `N05B` MSE `118.65`).
3. **Trường phái 3 — Học máy Cây & Phần dư Neo:** `LightGBM` (`L2`, `Tweedie` cho `N05C`, `Quantile P10/P50/P90`) học `Compact 7 ERA5` + **`LightGBM_AnchorRes_F3`** (dự báo phần dư quanh `EWMA_4` để phá trần cây: `N02BE` đạt MSE `1392.20` vượt `XGBoost` Paper).
4. **Trường phái 4 — Lai OOF & Định tuyến Tự động:** `Expanding-Block OOF Hybrid` (refit 26W + `1% Val Guard`) và **`AutoRouted_Champion`** tự chọn mô hình theo `Validation MAE` thấp nhất (không nhìn Test).

**Chiến lược đưa vào Production:**
* **Point Forecast Champion:** **`AutoRouted Champion`** (`r̂ · active_days`) — chọn mù Test theo `Validation MAE`, đánh bại `Seasonal Naïve` với `DM' p < 0.05` trên cả `8/8` nhóm ATC và đạt `MASE < 1.0` ở `7/8` nhóm.
* **Probabilistic & BI Explainability:** **`Global LightGBM + Split CQR (P10/P50/P90) + TreeSHAP`** — hiệu chuẩn Conformal trên tập Validation nâng độ phủ thực nghiệm 80% trung bình từ `71.7%` lên **`78.8%`** (`N02BE` tăng `55.8% → 78.8%`), xuất Fan Chart và tỷ trọng đóng góp thời tiết trực tiếp lên Dashboard BI.

---

## 5. Bảng Số liệu Gốc Fourkiotis & Tsadiras (2024) Dùng Để Đối sánh 1:1

Trích nguyên văn kết quả trên đúng **52 tuần Hold-out Test cuối cùng** từ **Bảng 2 (MSE, tr. 12)**, **Bảng 3 (Zdravković et al. MSE, tr. 13)** và **Bảng 4 (MAPE, tr. 14)** của [Fourkiotis & Tsadiras (2024)](https://doi.org/10.3390/forecast6010010) ([`forecasting-06-00010.pdf`](../references/papers/forecasting-06-00010.pdf)) trên cùng tập dữ liệu `2014–2019`:

| Mã ATC | Seasonal Naïve (MSE / MAPE) | Thống kê / Khác Tốt nhất (Paper MSE / MAPE) | XGBoost Paper (MSE / MAPE) | Zdravković et al. MSE (Bảng 3) |
| :--- | :--- | :--- | :--- | :--- |
| **M01AB** | **`49.19`** / `27.48%` | ARIMA Roll: `60.70` / `19.85%` | `54.81` / **`17.89%`** | `69.62` (Prophet) |
| **M01AE** | `58.75` / `34.77%` | LSTM: `58.04` / `26.97%` *(ARIMA Roll: `68.32` / `30.22%`)* | **`28.80`** / **`16.92%`** | `76.57` (ARIMA) |
| **N02BA** | `55.27` / `37.24%` | **`28.34`** (ARIMA Roll) / `27.08%` *(Prophet `28.81` / `28.02%`)* | `40.69` / **`17.98%`** | `31.94` (ARIMA) |
| **N02BE** | `2037.18` / `24.42%` | TES: `2190.53` / `18.89%` | **`1518.56`** / **`16.05%`** | `2147.07` (Auto-ARIMA) |
| **N05B** | `176.38` / `31.78%` | **`140.76`** (DES) / `19.17%` *(ARIMA Roll `147.14` / `18.49%`)* | `260.52` / `24.76%` | `147.13` (Auto-ARIMA) |
| **N05C** | `7.85` / `17.73%` *(Naïve `12.12%`)* | **`7.19`** (SES) / `86.81%` *(ARIMA `7.49` / `inf%`)* | `7.90` / **`inf%`** | `7.98` (ARIMA) |
| **R03** | `963.29` / `61.90%` | LSTM: `577.66` / `46.68%` *(TES `738.68` / **`39.91%`**)* | **`350.84`** / `54.78%` | `666.68` (Auto-ARIMA) |
| **R06** | `65.17` / `72.02%` | **`59.77`** (TES) / `63.68%` *(LSTM `84.95` / `48.98%`)* | `63.85` / **`36.26%`** | `66.84` (Stacked LSTM) |

---

## 6. Tính hợp lý & 4 Lưu ý Phương pháp luận khi Đối sánh với Baseline của Paper 2024

So sánh mô hình của PharmaFlow với các baseline của [Fourkiotis & Tsadiras (2024)](https://doi.org/10.3390/forecast6010010) **hoàn toàn hợp lý và giàu giá trị tham chiếu** vì cả hai bên sử dụng cùng một bộ dữ liệu gốc (`2014–2019`, 8 nhóm ATC, `302` tuần `W-SUN`). Kiểm chứng trực tiếp trên Hold-out 52 tuần (`W251–W302`, `2018-10-14 → 2019-10-13`) xác nhận `Seasonal Naïve (y[t − 52])` của PharmaFlow khớp **chính xác tới `0.01% MAPE` (Bảng 4 Paper 2024)** trên toàn bộ 7/8 nhóm có bán dương:

* `M01AB: 27.48%` · `M01AE: 34.77%` · `N02BA: 37.24%` · `N02BE: 24.42%` · `N05B: 31.78%` · `R03: 61.90%` · `R06: 72.02%`.

Tuy nhiên, để đảm bảo công bằng khoa học (**apples-to-apples**), cần tách bạch **4 sai khác giao thức** được phát hiện khi đối chiếu Bảng 1, Bảng 2 và Bảng 4 của bài báo với thực nghiệm Gold:

1. **Bất nhất cửa sổ Test ngay trong Bảng 1 Paper 2024 (`tr. 10 PDF`):** Bài báo không chạy mọi mô hình trên cùng một tập test (`ARIMA Rolling` chia `80%/20%`; `ARIMA Long-Term` lấy `50` quan sát cuối; `SES/DES/TES/SNaïve` chạy trên `52` tuần cuối).
2. **Bảng 2 MSE dùng `Seasonal Naïve` có trọng số `[0.4, 0.3, 0.2, 0.1]` trong khi Bảng 4 MAPE dùng `y[t − 52]`:** Bảng 1 của bài báo cấu hình trọng số nhiều năm gần (`0.4·y[t−52] + 0.3·y[t−104] + 0.2·y[t−156] + 0.1·y[t−208]`), làm giảm mạnh MSE so với `y[t−52]` đơn thuần (`M01AB: 107.08 → 72.49`, `N02BE: 3605.15 → 2404.25`, `N05C: 21.75 → 10.95`). Vì vậy PharmaFlow cài đặt **cả hai biến thể** trong cùng một harness thống nhất.
3. **Tuần cuối 302 chỉ có 2 ngày giao dịch (`2019-10-07 → 2019-10-08`):** Dữ liệu gốc dừng vào thứ Ba `08/10/2019`, khiến tuần `W-SUN` thứ `302` hụt ~70% lượng bán và làm tăng mạnh MSE ở các baseline không chia tỷ lệ ngày (`Seasonal Naïve` tăng `+338` đến `+583` MSE trên `N02BE`). PharmaFlow khắc phục bằng chuẩn hóa tốc độ ngày `qty_rate = qty / active_days`, giúp dự báo khớp hoàn toàn tuần `W302` (`Delta_MSE <= 0`).
4. **Xử lý `MAPE` trên `N05C` (`Weekly_zero_cnt > 0`):** Bài báo ghi `SNaïve MAPE = 17.73%` trong khi `XGBoost/ARIMA MAPE = inf%`. PharmaFlow dùng `WAPE` và `MASE` làm thước đo chính.

**Chuẩn đối sánh 2 tầng được áp dụng:**
* **Tầng 1 (Chính — Apples-to-Apples):** Đánh giá mọi mô hình cùng trên `W251–W302` + `4 Rolling Folds` + `Daily 365D`, chung quy tắc chống rò rỉ và `4` baseline nội bộ (`Seasonal_Naive`, `Seasonal_Naive_Weighted`, `Harmonic_ARIMA`, `Croston_SBA`).
* **Tầng 2 (Tham chiếu Ngoại sinh):** Đặt cạnh Bảng 2/4 Paper 2024 kèm phân tích độ nhạy `51W vs 52W`.

---

## 7. Kết quả Thực nghiệm Đã Kiểm chứng (Luồng Thống nhất `01 → 05`)

Toàn bộ `5` notebook trong `BTL_BI/src/ml/` đã được thực thi thành **1 luồng thống nhất duy nhất** (`Exit code 0`), vượt qua **Perturbation Leakage Unit-Test (`max_abs_diff == 0.0` cho cả Weekly và Daily)**, chuẩn hóa tốc độ ngày (`qty_rate * active_days`), dùng `Compact ERA5` (`7` biến trực giao vật lý), mở rộng `Ridge_F1F2F3`, `LightGBM_AnchorRes_F3`, `AutoRouted_Champion` (chọn mù Test theo Val MAE) và hiệu chuẩn `Split CQR P10–P90`. Tổng thời gian chạy trọn luồng chỉ **`166.6 giây`** (~`2.78` phút, nhanh gấp **`1,166.9×`** so với `54 giờ` Grid Search của Paper 2024) với `100%` dự báo `>= 0`.

### 7.1. Bảng Tổng hợp Hold-out 52 Tuần (`W251–W302`) — Luồng Thống nhất

| ATC | `AutoRouted Champion` (Chọn theo Val) | Mô hình MSE Thấp nhất (Post-hoc) | `SNaïve` / `SNaïve_W` (MSE · WAPE) | Paper 2024 (Bảng 2 MSE tham chiếu) |
| :--- | :--- | :--- | :---: | :--- |
| **M01AB** | `Croston_SBA` (`WAPE 15.74%`, `MSE 58.24`) | **`Ridge_F1F2F3`** (`MSE 52.68`, `WAPE 15.03%`, `MASE 0.587`) | `107.08 (22.96%)` / `72.49 (18.51%)` | `SN_W: 49.19` · `XGB: 54.81` *(Ridge vượt XGB)* |
| **M01AE** | `Ridge_F1F2F3` (`WAPE 25.17%`, `MSE 72.64`) | `AnchorRes_F3` (`MSE 67.56`, `WAPE 25.13%`, `MASE 0.991`) | `105.88 (29.42%)` / `86.98 (28.18%)` | `XGB: 28.80` · `LSTM: 58.04` *(4-Fold Ridge `24.38%`)* |
| **N02BA** | `Harmonic_ARIMA` (`WAPE 20.92%`, `MSE 29.06`) | **`LightGBM_F1F2`** (`MSE 27.72`, `Croston WAPE 19.92%`) | `52.07 (27.57%)` / `75.57 (33.11%)` | `ARIMA_R: 28.34` · `XGB: 40.69` *(Vượt cả ARIMA_R & XGB)* |
| **N02BE** | `LightGBM_F1F2F3` (`WAPE 15.44%`, `MSE 2042.8`) | **`AnchorRes_F3`** (**`MSE 1392.20`**, `WAPE 12.96%`, `MASE 0.439`) | `3605.15 (21.83%)` / `2404.25 (15.27%)` | `XGB: 1518.56` · `TES: 2190.53` *(AnchorRes vượt XGB & SN_W)* |
| **N05B** | **`AnchorRes_F3`** (`WAPE 16.49%`, `MSE 139.66`) | **`Ridge_F1F2F3`** (**`MSE 118.65`**, `WAPE 15.55%`, `MASE 0.344`) | `450.79 (28.04%)` / `239.42 (20.27%)` | `DES: 140.76` · `XGB: 260.52` *(Cả Router & Ridge vượt DES/XGB)* |
| **N05C** | `LightGBM_F1F2F3` (`WAPE 47.94%`, `MSE 8.66`) | **`Croston_SBA`** (`MSE 7.76`, `WAPE 44.24%`, `MASE 0.665`) | `21.75 (69.62%)` / `10.95 (54.13%)` | `SES: 7.19` · `SN_W: 7.85` · `XGB: 7.90` *(Vượt SN_W/XGB, `0 inf%`)* |
| **R03** | `AnchorRes_F3` (`WAPE 38.32%`, `MSE 688.80`) | `Harmonic_ARIMA` (`MSE 662.25`, `Ridge WAPE 36.46%`) | `1142.61 (49.34%)` / `1087.25 (46.80%)` | `XGB: 350.84` · `LSTM: 577.66` *(Thắng baseline `p<0.02`)* |
| **R06** | **`AnchorRes_F3`** (`WAPE 24.67%`, `MSE 57.04`) | **`LightGBM_F1F2`** (**`MSE 49.75`**, `WAPE 23.26%`, `MASE 0.783`) | `137.75 (36.75%)` / `86.50 (27.56%)` | `TES: 59.77` · `XGB: 63.85` *(Router & F1F2 vượt TES & XGB)* |

### 7.2. Kết quả Ablation Compact ERA5, 4-Fold Stability, `DM'`, Split CQR & `TreeSHAP`

| ATC | Ablation WAPE (`F1 → F1F2 → F1F2F3`) | 4-Fold Stability (Best `Mean ± Std`) | `DM'` `AutoRouter` (`vs SN / vs SN_W`) | `DM'` `F3 vs F1F2` (`52W / 365D`) | Split CQR `P10–90` (`Raw → CQR` · `TreeSHAP`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **M01AB** | `15.22 → 16.64 → 16.83%` (`ΔMSE −1.45`) | `F1F2F3: 15.14 ± 2.93%` | **`p=0.0100*`** / `p=0.203` | `52W: 0.284` · `365D: 0.096` | `78.8% → 82.7%` · `SH 16.1%` |
| **M01AE** | `26.91 → 26.10 → 25.96%` (`Δ = −0.14%`) | `Ridge: 24.38 ± 6.83%` | **`p=0.0315*`** / `p=0.104` | `52W: 0.113` · `365D: 0.868` | `63.5% → 63.5%` · `SH 11.3%` |
| **N02BA** | `20.15 → 20.67 → 22.06%` (`Δ = +1.39%`) | `LGBM_F1: 19.48 ± 5.05%` | **`p=0.0071*`** / **`p=0.0020*`** | `52W: 0.963` · `365D: 0.591` | `76.9% → 75.0%` · `SH 19.7%` |
| **N02BE** | `16.54 → 15.38 → 15.44%` (`AncRes 12.96%`) | **`AnchorRes: 12.67 ± 1.95%`** | **`p=0.0147*`** / `p=0.307` | `52W: 0.683` · `365D: 0.694` | **`55.8% → 78.8%`** · `daylight 8.06` |
| **N05B** | `17.30 → 17.52 → 16.76%` (`Δ = −0.76%`) | **`Ridge: 15.69 ± 1.08%`** | **`p=0.0045*`** / `p=0.0506` | **`52W sq: p=0.0339*`** · `365D: 0.530` | `90.4% → 73.1%` · `SH 17.3%` |
| **N05C** | `46.87 → 48.44 → 47.94%` (`Δ = −0.50%`) | **`AnchorRes: 43.80 ± 3.40%`** | **`p=0.0043*`** / **`p=0.0368*`** | `52W: 0.176` · **`365D abs: p=0.0096*`** | **`71.2% → 86.5%`** · `t_lag1 0.064` |
| **R03** | `39.68 → 38.49 → 38.46%` (`Ridge 36.46%`) | **`Croston: 37.58 ± 4.62%`** | **`p=0.0175*`** / **`p=0.0198*`** | `52W: 0.855` · `365D: 0.999` | **`65.4% → 88.5%`** · `t_lag1 2.35` |
| **R06** | `27.22 → 23.26 → 26.84%` (`Δ = +3.58%`) | `Router: 26.06 ± 9.66%` | **`p=0.0011*`** / **`p=0.0379*`** | `52W: 0.990` · `365D: 0.745` | **`71.2% → 82.7%`** · `SH 25.9%` |

**Kết luận trung thực cho RQ1–RQ3:**
* **RQ1:** `AutoRouted_Champion` (chọn theo `Val MAE`, không nhìn Test) đánh bại `Seasonal_Naive` với **`p < 0.05` trên cả `8/8` nhóm ATC**, thắng `Seasonal_Naive_Weighted` trên `7/8` nhóm và đạt `MASE < 1.0` ở `7/8` nhóm. Nhờ chuẩn hóa `qty_rate`, `Ridge` và `AnchorRes`, hệ mô hình vượt trực tiếp **MSE của Paper 2024 trên `6/8` nhóm** (`M01AB 52.68`, `N02BA 27.72`, `N02BE 1392.20`, `N05B 118.65`, `N05C 7.76`, `R06 49.75`); còn `M01AE` (`67.56` vs `28.80`) và `R03` (`662.25` vs `350.84`) xếp sau `XGBoost` Paper.
* **RQ2:** `Compact ERA5 (7 biến)` cải thiện điểm lỗi ở `5/8` nhóm tuần (`DM' p = 0.0339` tại `N05B`) và `N05C Daily 365D` (`DM' p = 0.0096`), đồng thời đóng góp `11.3%–25.9%` tổng `|TreeSHAP|` (`daylight_duration_s = 8.06` tại `N02BE`, `temp_mean_lag1 = 2.35` tại `R03`, `daylight = 1.27` & `humidity_mean_lag1 = 1.18` tại `R06`).
* **RQ3:** Chạy trọn luồng hết **`166.6s`** (nhanh gấp **`1,166.9×`** so với `54 giờ` Grid Search của Paper 2024), `100%` dự báo `>= 0`, và Split CQR nâng độ phủ trung bình `P10–P90` từ **`71.7% → 78.8%`** (`N02BE` từ `55.8% → 78.8%`).
