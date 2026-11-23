# Tổng quan Nghiên cứu & Phân tích 7 Bài báo Nền tảng (2022–2026)

**Phạm vi:** Tổng hợp hướng nghiên cứu, dữ liệu, phương pháp tiếp cận–giải quyết, phát hiện chính và khoảng trống nghiên cứu (`Research Gaps`) của **7 bài báo** trong [`docs/references/papers/`](../references/papers/)  
**Mục tiêu:** Khóa chặt cơ sở khoa học cho **PharmaFlow Module 01 (`DATA -> FORECAST`)**  
**Tài liệu Google Docs đầy đủ (4 Tab):** [Mở Google Docs](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit) · [Tab 1 — Tổng quan 7 Bài báo](https://docs.google.com/document/d/1Qxpmm4v4zUI8wN-NiUiOeSF5nTUlwOTYJmPgSZRZLJo/edit?tab=t.str8dzlshch7)  
**Tài liệu liên quan trong Repo:** [src/ml/README.md](../../src/ml/README.md) · [demand-forecasting-solution.md](./demand-forecasting-solution.md) · [demand-forecasting-colab-step-by-step.md](./demand-forecasting-colab-step-by-step.md)

> **Kết luận chung từ tài liệu nghiên cứu (Literature Consensus):**  
> Tổng hợp 7 bài báo giai đoạn 2022–2026 khẳng định **không tồn tại một thuật toán đơn lẻ nào thắng tuyệt đối trên mọi nhóm thuốc và mọi cấu trúc chuỗi thời gian**:
> * Trong **Fourkiotis & Tsadiras (2024)**, XGBoost chỉ thắng **3/8 nhóm ATC** theo MSE, trong khi **5/8 nhóm** thuộc về các mô hình thống kê/cơ sở.
> * Trong **Abacı (2026)**, Hybrid `SARIMA + α*·ML` giảm `RelMAE` **21–36%**, nhưng kiểm định `DM'` chưa đạt ý nghĩa thống kê (`p = 0.1638–0.3014`) do tập test chỉ có `n = 8` tháng.
> * Trong **Khan et al. (2026)**, `LightGBM` thắng theo `RMSLE` nhưng `Rolling Mean 3 tháng` lại thắng theo `WAPE`.
>
> Vì vậy, PharmaFlow thiết kế **Luồng Thống nhất 4 Trường phái Mô hình** trên tốc độ ngày `qty_rate` (`Baseline / Croston-SBA`, `Harmonic ARIMA / Ridge`, `LightGBM & AnchorRes`, `Expanding-Block OOF Hybrid`) cùng **`AutoRouted Champion`** theo Validation MAE + **`Compact ERA5 (F3)`** + **`Split CQR P10–P90`** + **`TreeSHAP`**.

---

## 1. Bức tranh Tổng thể: Ma trận So sánh 7 Nghiên cứu Tham khảo

| Nghiên cứu (Năm) | Bối cảnh & Dữ liệu | Hướng Tiếp cận & Mô hình | Phát hiện Chính (Số liệu Gốc) | Đóng góp cho PharmaFlow |
| :--- | :--- | :--- | :--- | :--- |
| **Burinskiene (2022)**<br>*Frontiers in Medicine* 9:582186 *(Trụ cột 1)* | 8 nhà thuốc bán lẻ Litva; 13 tuần; 280 kịch bản thử nghiệm. | 4 cách gom dữ liệu/lọc nhiễu × 8 model làm trơn (`HW Multiplicative`, v.v.); bù thiếu `0.0001` hoặc trung bình + cắt ngoại lai Grubbs `3s`. | Không thiếu hàng: cách #3 gộp từng nhà thuốc (`HW Mult` `U2 = 0.55455`, MAPE `9.77%`). Có thiếu hàng: cách #4 bù TB (`U2 = 0.50728`, MAPE `6.01%`). | Cho thấy gộp thô giữa cửa hàng làm méo dự báo và bù trung bình + cắt `3s` làm co phương sai → giữ nguyên `observed_qty` trên Gold (`Non-Goal 1`). |
| **Fourkiotis & Tsadiras (2024)**<br>*Forecasting (MDPI)* 6:170–186 *(Trụ cột 2)* | **Chính bộ 1 nhà thuốc 2014–2019** (~600k bản ghi, 57 SKU / 8 ATC, 302 tuần, Test 52 tuần). | So sánh 10 thuật toán đơn biến (`Naïve`, `SNaïve`, `SES/DES/TES`, `ARIMA Roll/Long`, `Prophet`, `XGBoost`, `LSTM`); `54h` Grid Search (CPU 4 nhân i5). | XGBoost thắng MSE `3/8` nhóm (`M01AE 28.80`, `N02BE 1518.56`, `R03 350.84`); thống kê thắng `5/8`; `N05C` nổ MAPE = `inf%`. | Cột mốc đối sánh **1:1** trên cùng dữ liệu Gold; giải quyết Future Work thời tiết (tr. 16) & thay MAPE bằng `WAPE/MASE`. |
| **Abacı (2026)**<br>*IEEE Access* 14:61666–61688 *(Trụ cột 3)* | Nhà thuốc bán lẻ Istanbul; 39 tháng (`01/2021–03/2024`), `n = 8` tháng test, 4 nhóm thuốc. | Chẩn đoán `ADF`, `Ljung-Box`, `Mann-Kendall`, `Shapiro-Wilk`, `STL`, `CoV`; Hybrid chống rò rỉ `SARIMA + α*·ML` (`XGB/SVR/ElasticNet`); Ablation `S1..S5`; Harvey `DM'`. | `RelMAE` giảm `21–36%` (`5.84→4.21%`, `4.41→3.48%`, `12.45→8.03%`, `7.25→4.96%`); `α*=1.0` (3 nhóm XGB) & `0.25` (SVR); `DM'` `p=0.1638–0.3014 > 0.05` (`n=8`). | Kế thừa trọn bộ chẩn đoán + `SARIMA + α*·LightGBM`; nâng cỡ mẫu test lên `n = 52W / 365D` và bổ sung thời tiết ERA5 (Future Work tr. 22). |
| **Ramadhan et al. (2026)**<br>*ISI* 31(1):179–191 *(Trụ cột 4)* | Scopus bibliometric & systematic review (`705 → 150 → 30` bài, đỉnh `202` bài năm 2024). | Phân tích mạng cụm `VOSviewer`; rà soát 5 thuật toán ML (`LSTM`, `RF`, `ANN`, `XGBoost`, `Linear Regression`). | Xác định 3 nhu cầu cấp thiết: khung **Hybrid** thống kê–ML, dữ liệu đa nguồn thực tế và **Explainable ML / SHAP**. | Định hướng kiến trúc Hybrid + dữ liệu thực Gold/ERA5 + giải thích `TreeSHAP` cho DSS. |
| **E et al. (2024)**<br>*Procedia CS (ITQM)* 242:264–271 *(Bổ trợ 1)* | `14,253` chuỗi SKU theo ngày × `152` cửa hàng (`99.9%` Intermittent/Lumpy). | Đề xuất 3 bước `ES-C-T` (liên cửa hàng + theo tuần bằng ES), phân loại `Syntetos–Boylan` (`ADI/CV²`). | Vượt ES `9.77%` MAE, `5.44%` RMSE, `5.96%` WRMSSE (`h=7`); thứ hạng phụ thuộc metric (`Croston` kém MAE nhưng top `WRMSSE`). | Chuẩn hóa EDA `ADI/CV²` cho 8 ATC (`N05C` Intermittent, `R03` Erratic) & đánh giá đa metric `WAPE/MASE`. |
| **Sbrana & Babai (2026)**<br>*EJOR* *(Bổ trợ 2)* | `42,686` chuỗi Walmart M5 + `24,029` chuỗi mỹ phẩm quy mô lớn. | Đối chiếu `AutoARIMA` vs Non-Negative ARMA `NNARMA(1,1)` (`φ_i > 0`, `-φ_i < θ_i ≤ 0`) + khoảng tin cậy `NBD`. | `AutoARIMA` sinh bộ lọc âm trên `6,681/30,490` (`~22%`) chuỗi M5 & dự báo âm trên `501` chuỗi; `sMAPC` cải thiện `4.38` vs `11.51`. | Khóa ràng buộc hậu xử lý `ŷ ≥ 0`, dùng `LightGBM Tweedie Loss` cho `N05C` và xuất dải phân vị `P10–P50–P90`. |
| **Khan et al. (2026)**<br>*Discover AI* 6:838 *(Bổ trợ 3)* | `22.67M` bản ghi NHS SCMD (`72` tháng `04/2019–03/2025`, `522,813` dòng SKU-tháng); không có nhãn tồn kho/thiếu hàng. | `LightGBM` kiểm toán rò rỉ + lag lịch + `quantity_share_of_month` + bậc mạng `Trust` + `TreeSHAP`. | `LightGBM` đạt `RMSLE = 0.4832` (7-fold rolling `0.4910`), Rolling Mean 3M thắng `WAPE = 0.1082`; Wilcoxon `p < 1e-150` (`r_rb=0.098–0.121`); `TreeSHAP`: `log_quantity` (`39.8%`) + `share` (`37.7%`). | Giữ phạm vi `DATA -> FORECAST` khi thiếu nhãn tồn kho, thiết kế đặc trưng tỷ trọng `atc_share` (`F2`), kiểm toán rò rỉ & `TreeSHAP`. |

---

## 2. Mổ xẻ Chi tiết 4 Bài báo Trụ cột

### 2.1 Burinskiene (2022) — Cấp độ Tổng hợp & Dữ liệu Thiếu hàng (`fmed-09-582186.pdf`)
> **Bài báo gốc:** Burinskiene, A. (2022), *Frontiers in Medicine* 9:582186 · DOI: <https://doi.org/10.3389/fmed.2022.582186>

* **Dữ liệu & Thiết kế:** Theo dõi 8 nhà thuốc bán lẻ tại Litva trong `13` tuần với `280` kịch bản thử nghiệm.
* **Phương pháp tiếp cận:** So sánh `4` hướng chuẩn bị/xử lý chuỗi × `8` thuật toán làm trơn & cơ sở (gồm `Holt–Winters Multiplicative`). Các tuần thiếu hàng (`shortage`) được thử thay bằng `0.0001` hoặc trung bình cộng, còn ngoại lai bị cắt tại ngưỡng `3s` bằng kiểm định Grubbs.
* **Kết quả & Giới hạn:** Khi không có thiếu hàng, hướng **#3** (dự báo riêng từng nhà thuốc rồi cộng tổng) đạt tốt nhất với `HW Multiplicative` (`U2 = 0.55455`, MAPE `9.77%`). Khi có thiếu hàng, hướng **#4** (từng nhà thuốc + bù trung bình + cắt ngoại lai) đạt `U2 = 0.50728`, MAPE `6.01%`. Tuy nhiên cửa sổ `13` tuần quá ngắn và cách thay bằng `0.0001`/trung bình hoặc cắt `3s` làm biến dạng phương sai thực. Vì bảng Gold `store_id = 5631` không có dữ liệu tồn kho/stockout, PharmaFlow giữ nguyên quan sát thực (`OBSERVED`) thay vì suy diễn cờ thiếu hàng.

### 2.2 Fourkiotis & Tsadiras (2024) — Đối chuẩn Trực tiếp 1:1 (`forecasting-06-00010.pdf`)
> **Bài báo gốc:** Fourkiotis, K. P., & Tsadiras, A. (2024), *Forecasting* 6(1), 170–186 · DOI: <https://doi.org/10.3390/forecast6010010>

* **Dữ liệu & Thiết kế:** Sử dụng **chính xác bộ dữ liệu 2014–2019 của 1 nhà thuốc** (`~600k` giao dịch, `57` sản phẩm gom theo `8` nhóm ATC, `302` tuần, Hold-out Test `52` tuần cuối) — khớp 100% với bảng `mart_sales_observation_period` (`store_id = 5631`) trên Gold.
* **Phương pháp tiếp cận:** Đánh giá `10` mô hình đơn biến (`Naïve`, `Seasonal Naïve`, `SES`, `DES`, `TES`, `ARIMA Roll`, `ARIMA Long`, `Prophet`, `XGBoost`, `LSTM`) với thời gian Grid Search kéo dài **54 giờ** trên CPU Intel i5 4 nhân; đối chiếu thêm với kết quả MSE của Zdravković et al. (Bảng 3, tr. 13).
* **Kết quả thực nghiệm (Bảng 2 MSE & Bảng 4 MAPE):** XGBoost chỉ dẫn đầu MSE ở **3/8 nhóm ATC** (`M01AE = 28.80`, `N02BE = 1518.56`, `R03 = 350.84`), trong khi **5/8 nhóm** thuộc về mô hình cơ sở/thống kê (`M01AB`: Seasonal Naïve `49.19`; `N02BA`: ARIMA Roll `28.34`; `N05B`: DES `140.76`; `N05C`: SES `7.19`; `R06`: TES `59.77`). Với nhóm thưa `N05C`, chỉ số MAPE nổ **`inf%`** ở XGBoost, ARIMA, Prophet và LSTM.
* **Khoảng trống Future Work (tr. 16):** Tác giả nêu rõ bài toán mới dừng ở chuỗi đơn biến, cần tích hợp **dữ liệu khí hậu/thời tiết ngoại sinh** và nguồn dữ liệu lớn hơn cho mô hình sâu.

### 2.3 Abacı (2026) — Chẩn đoán Thống kê, Hybrid Chống Rò rỉ & Ablation (`IEEE Access`)
> **Bài báo gốc:** Abacı, H. (2026), *IEEE Access* 14, 61666–61688 · DOI: <https://doi.org/10.1109/ACCESS.2026.3685042>

* **Dữ liệu & Thiết kế:** Dữ liệu bán tháng của một nhà thuốc bán lẻ tại Istanbul trong `39` tháng (`01/2021–03/2024`), `n = 8` tháng test cuối cho `4` nhóm thuốc (Kháng sinh, Chống trầm cảm, Ung thư, Giảm đau).
* **Phương pháp tiếp cận:** Tiến hành bộ chẩn đoán trước mô hình (`ADF`, `Ljung-Box`, `Mann-Kendall`, `Shapiro-Wilk`, phân rã `STL`, `CoV`); xây dựng Hybrid chống rò rỉ `SARIMA + α*·ML` (`XGBoost`, `SVR`, `ElasticNet`) chỉ học phần dư từ tín hiệu nội sinh hợp lệ (`pt, lags, d1, ds, sin/cos, t`); kết hợp 5 giai đoạn Ablation (`S1..S5`) và kiểm định Harvey–Diebold–Mariano (`DM'`).
* **Kết quả & Giới hạn:** Mô hình Hybrid giảm `RelMAE` từ **21–36%** (`5.84%→4.21%`, `4.41%→3.48%`, `12.45%→8.03%`, `7.25%→4.96%`), với `α* = 1.0` (XGBoost cho 3 nhóm) và `α* = 0.25` (SVR cho nhóm Chống trầm cảm). Tuy nhiên do `n = 8` tháng test quá hẹp, kiểm định `DM'` so với SARIMA cho `p = 0.1638–0.3014 > 0.05`. Phần Future Work (tr. 22) khuyến nghị mở rộng cửa sổ kiểm định dài hơn và bổ sung **dữ liệu thời tiết / ngoại sinh**.

### 2.4 Ramadhan et al. (2026) — Tổng quan Hệ thống & Nhu cầu XAI (`isi_31.01_17.pdf`)
> **Bài báo gốc:** Ramadhan, W., Noersasongko, E., Syukur, A., & Soeleman, M. A. (2026), *ISI* 31(1), 179–191 · DOI: <https://doi.org/10.18280/isi.310117>

* **Quy mô & Công cụ:** Tổng quan hệ thống chuẩn Scopus (`705 → 150 → 30` bài báo cốt lõi, số công bố đạt đỉnh `202` bài năm 2024) phân tích bằng `VOSviewer`.
* **Phát hiện & Khoảng trống:** Thống kê 5 thuật toán ML phổ biến (`LSTM`, `RF`, `ANN`, `XGBoost`, `Linear Regression`), đồng thời khẳng định triển khai chuỗi cung ứng thực tế còn thiếu 3 trụ cột: (1) kiến trúc **Hybrid** kết hợp thống kê và ML, (2) dữ liệu thực đa nguồn, và (3) **Explainable ML / SHAP** để giúp người quản lý kho hiểu lý do dự báo.

---

## 3. Ba Nghiên cứu Chuyên sâu Bổ trợ Kỹ thuật Chuỗi Thời gian

1. **E et al. (2024) — *Procedia Computer Science (ITQM)* 242:264–271** (<https://doi.org/10.1016/j.procs.2024.08.239>): Phân tích `14,253` chuỗi SKU ngày × `152` cửa hàng (`99.9%` Intermittent/Lumpy theo Syntetos–Boylan `ADI/CV²`). Đề xuất tổng hợp 3 tầng `ES-C-T` giúp giảm `9.77%` MAE, `5.44%` RMSE, `5.96%` WRMSSE tại `h = 7`, đồng thời chứng minh **thứ hạng thuật toán phụ thuộc vào thước đo** (`Croston` thua MAE nhưng nằm nhóm đầu ở `WRMSSE`).
2. **Sbrana & Babai (2026) — *European Journal of Operational Research*** (<https://doi.org/10.1016/j.ejor.2026.06.009>): Trên `42,686` chuỗi Walmart M5 và `24,029` chuỗi mỹ phẩm, `AutoARIMA` cho hệ số lọc âm ở `6,681 / 30,490` (`~22%`) chuỗi M5 và sinh **dự báo âm trên `501` chuỗi**. Chứng minh điều kiện đủ không âm (`φ_i > 0`, `-φ_i < θ_i ≤ 0`) cho `NNARMA(1,1)` kết hợp khoảng tin cậy Negative Binomial (`NBD`), cải thiện độ ổn định `sMAPC` từ `11.51` xuống `4.38`.
3. **Khan et al. (2026) — *Discover Artificial Intelligence* 6:838** (<https://doi.org/10.1007/s44163-026-01956-z>): Trên `22.67M` bản ghi NHS SCMD (`72` tháng `04/2019–03/2025`, `522,813` dòng SKU-tháng, `488,924` dòng lượng xuất dương tháng kế tiếp) hoàn toàn không có nhãn tồn kho/thiếu hàng, nhóm tác giả định vị bài toán là **dự báo nhu cầu + giám sát chuỗi**, kiểm toán chống rò rỉ chặt chẽ trên `LightGBM` kết hợp đặc trưng `quantity_share_of_month` và bậc mạng lưới Trust. Kết quả `LightGBM` đạt holdout `RMSLE = 0.4832` (`7`-fold rolling `0.4910`) nhưng `Rolling Mean 3M` thắng `WAPE = 0.1082` (Wilcoxon `p < 1e-150`, `r_rb = 0.098–0.121`); `TreeSHAP` xác nhận `log_quantity` (`39.8%`) và `quantity_share_of_month` (`37.7%`) chi phối cao nhất.

---

## 4. Tổng hợp Khoảng trống Nghiên cứu (`Research Gaps`) → Thiết kế PharmaFlow

| Khoảng trống từ Tài liệu | Bằng chứng Gốc trong 7 Bài báo | Giải pháp Chứng minh trên Gold của PharmaFlow |
| :--- | :--- | :--- |
| **1. Thiếu biến ngoại sinh Thời tiết** | **Fourkiotis & Tsadiras (2024, tr. 16)** và **Abacı (2026, tr. 22)** đều đặt tích hợp thời tiết là Future Work. | Ghép thẳng bảng Gold `mart_sales_weather_daily` (Open-Meteo ERA5) ở tầng `F3` + kiểm chứng qua Ablation (`F1 → F1+F2 → F1+F2+F3`), `DM'` và `TreeSHAP`. |
| **2. Sai lệch từ MAPE & đơn thước đo** | `MAPE` nổ `inf%` ở `N05C` (2024); đảo thứ hạng theo metric ở **E et al. (2024)** và **Khan et al. (2026)**. | Giữ `MSE/MAPE` để đối chiếu 1:1 Bảng 2 & 4 của Paper 2024, đồng thời lấy `WAPE`, `MASE`, `Bias` và `Pinball Loss` làm thước đo chính. |
| **3. Cỡ mẫu kiểm định hẹp & rò rỉ** | **Abacı (2026)** có `n = 8` tháng nên `DM'` chưa đạt `p < 0.05`; **Khan et al. (2026)** nhấn mạnh rà soát rò rỉ dữ liệu. | Cắt chuỗi theo trục thời gian với `n_test = 52` tuần / `365` ngày (lớn gấp `6.5–45×`), khóa `.shift(1)` cho mọi biến trễ/trượt. |
| **4. Chuỗi ngắt quãng & dự báo âm** | `99.9%` chuỗi thưa ở **E et al. (2024)**; `AutoARIMA` sinh `~22%` lọc âm & `501` dự báo âm (**Sbrana & Babai, 2026**). | Chẩn đoán `ADI/CV²` theo Syntetos–Boylan, áp dụng `LightGBM Tweedie` cho `N05C`, kẹp `ŷ ≥ 0` và xuất dải phân vị `P10–P50–P90`. |
| **5. Tốn `54h` chạy & thiếu giải thích XAI** | `54h` Grid Search (**Fourkiotis & Tsadiras, 2024**); thiếu Hybrid thực chiến + XAI (**Ramadhan et al., 2026**). | Luồng thống nhất 4 trường phái mô hình trên tốc độ ngày `qty_rate` (`SNaïve/Croston-SBA`, `Harmonic ARIMA/Ridge`, `LightGBM/AnchorRes`, `OOF Hybrid`) + `AutoRouted Champion` & `Split CQR P10–P90`, chạy trọn `5` fold + `Daily 365D` trong **`166.6 giây`** (nhanh gấp **`1,166.9×`** Paper 2024), kèm `TreeSHAP` giải thích cho DSS. |


---

## 5. Danh mục Tài liệu Tham khảo (7 Bài báo Gốc — Link Trực tiếp)

1. **[1]** Burinskiene, A. (2022). *Forecasting Model: The Case of the Pharmaceutical Retail.* Frontiers in Medicine, 9:582186. <https://doi.org/10.3389/fmed.2022.582186>
2. **[2]** Fourkiotis, K. P., & Tsadiras, A. (2024). *Applying Machine Learning and Statistical Forecasting Methods for Enhancing Pharmaceutical Sales Predictions.* Forecasting, 6(1), 170–186. <https://doi.org/10.3390/forecast6010010>
3. **[3]** Abacı, H. (2026). *Statistical Diagnostics and Forecast Accuracy: Comparing Time-Series, Machine-Learning, and Hybrid Models for Drug Sales.* IEEE Access, 14, 61666–61688. <https://doi.org/10.1109/ACCESS.2026.3685042>
4. **[4]** Ramadhan, W., Noersasongko, E., Syukur, A., & Soeleman, M. A. (2026). *Machine Learning Approaches for Pharmaceutical Demand Forecasting: A Bibliometric and Systematic Review of Methods and Research Trends.* Ingénierie des Systèmes d'Information, 31(1), 179–191. <https://doi.org/10.18280/isi.310117>
5. **[5]** E, E., Tian, X., Tao, Y., & Sun, H. (2024). *An ES-based model with contemporaneous and temporal aggregation for forecasting intermittent and lumpy retail demand.* Procedia Computer Science (ITQM 2024), 242, 264–271. <https://doi.org/10.1016/j.procs.2024.08.239>
6. **[6]** Sbrana, G., & Babai, M. Z. (2026). *Non-negative autoregressive moving average models for intermittent demand: Forecast accuracy and inventory implications.* European Journal of Operational Research. <https://doi.org/10.1016/j.ejor.2026.06.009>
7. **[7]** Khan, M. R. I., Tahsin, M. S., & Al Mamun, A. (2026). *Hospital trust network features inform machine learning for medicines demand forecasting and resilient supply chain decisions.* Discover Artificial Intelligence, 6:838. <https://doi.org/10.1007/s44163-026-01956-z>
