# Phân công Tái cấu trúc Báo cáo (5 Chương) & Thuyết trình Slide — CO4033 (PharmaFlow BI)

> **Cập nhật v2 (27/11/2026):** Tài liệu phân công công việc tái cấu trúc Báo cáo (5 chương chuẩn HCMUT) & Thuyết trình Slide cho **3 thành viên (`Võ Công Đăng Khôi`, `Đoàn Mạnh Tất`, `Nguyễn Thị Cẩm Vân`)** dựa trên hiện trạng hệ thống kỹ thuật, khung LaTeX mẫu và 15 Slide HTML đã dựng sẵn; cập nhật tiến độ thực tế trên **Prism LaTeX (`report_BigData`)**:
> - **Võ Công Đăng Khôi (`2311708` — `TV A`):** Đã xong Chương 1, 2, 6 bản cũ trên Prism *(chưa chèn ảnh)*.
> - **Đoàn Mạnh Tất (`2313074` — `TV B`):** Đã cập nhật xong `ch04` trên Prism (gồm cấu hình máy, Benchmark Data Engineering & Scale-up `3×/5×/10×` kèm `Images/scaleup_time_memory.png`).
> - **Nguyễn Thị Cẩm Vân (`2313870` — `TV C`):** Đã cập nhật xong `ch05` trên Prism (gồm ảnh 5 trang Dashboard `Images/page1..5.png`, `page5-1.png`, nhận xét định lượng & bảng `tab:decisions`).
> - **Mốc thời gian:** Báo cáo LaTeX nộp linh hoạt theo hướng dẫn; **thuyết trình dự kiến vào tuần sau** (Khôi xác nhận lại lịch cụ thể với giảng viên).

- 🌐 **Live Dashboard (Streamlit Community Cloud):** https://pharmaflow-sales-lakehouse-bi-ut7zhiigkcrzqwvz93krzy.streamlit.app/
- 📄 **Thư mục Báo cáo LaTeX gốc tham chiếu:** [`report/`](report/README.md) (`17` tệp · đã có sẵn bản biên dịch [`main.pdf`](report/main.pdf) làm mẫu kiểm tra)
- 🖥️ **Bộ Slide thuyết trình (15 slides + Speaker Notes):** [`slides/index.html`](slides/index.html)
- 📋 **Rubric & Danh sách điểm cần vá:** [`reviews/yêu cầu bigdata.docx`](<reviews/yêu cầu bigdata.docx>)

> ⚠️ **Cảnh báo quan trọng khi tham khảo [`reviews/bao_cao_structure_co4033.md`](reviews/bao_cao_structure_co4033.md):**
> Chỉ tham khảo bố cục khung. **Tuyệt đối không copy** số liệu benchmark minh họa ở Mục 4.2 (`145.2s vs 38.6s`, `8.45s vs 0.42s`, v.v.) hay 3 insight giả định ở Mục 5.3 (*"miền Trung mưa >50mm"*, *"miền Bắc đợt lạnh"* — dữ liệu POS thực tế chỉ gồm `ONYX` EU `SYNTHETIC`, `IRPD` Indonesia `OBSERVED`, và `PHARMA_SALES_DAILY_ATC` Serbia `store_id = 5631 · OBSERVED`). Toàn bộ số liệu thật đã nằm sẵn trong [`report/`](report/README.md), `artifacts/forecasting/` và bảng $R^2$ ở **Mục 2** bên dưới.

---

## 1. Cấu trúc Báo cáo Mới (5 Chương — Ánh xạ từ 6 Chương cũ, Không làm lại từ đầu)

Bố cục mới khớp **100%** mẫu Mục lục báo cáo Bách Khoa (5 chương + Tài liệu tham khảo & Phụ lục) và góp ý cụ thể của Giảng viên/Vân cho Chương 3 & Chương 4, đồng thời giữ nguyên ánh xạ 1:1 vào **6 tiêu chí Rubric 100 điểm CO4033**:

| Bố cục Mới (5 Chương chuẩn HCMUT) | Nguồn chuyển từ bản 6 Chương cũ | Nội dung & Tiểu mục bắt buộc | Tiêu chí Rubric CO4033 |
| :--- | :--- | :--- | :---: |
| **Frontmatter** | `main.tex`, `camdoan.tex`, `phancong.tex`, `tomtat.tex`, `danhmuctuviettat.tex` | Bìa đủ **4 SV + MSSV + GVHD**; Lời cam đoan & Tuyên bố AI; Bảng phân công **4 dòng (`Tổng = 100%`)**; Tóm tắt cập nhật theo 5 chương; Mục lục, Danh mục hình/bảng. | Tiêu chí 6 (`15đ`) |
| **Chương 1: Mở đầu** (`ch01_modau.tex`) | Chuyển từ `ch01_baitoan_kpi.tex` | **1.1 Đặt vấn đề:** Bối cảnh phân mảnh đa nguồn, đa ĐVT, `OBSERVED` vs `SYNTHETIC`.<br>**1.2 Tổng quan tài liệu (*Literature Review*):** Tổng hợp 7 bài báo 2022–2026 (`Burinskiene 2022`, `Fourkiotis & Tsadiras 2024`, `E et al. 2024`, `Abacı 2026`, `Ramadhan et al. 2026`, `Sbrana & Babai 2026`, `Khan et al. 2026`).<br>**1.3 Mục đích, mục tiêu và Câu hỏi nghiên cứu:** 3 nhóm người dùng cuối + `BQ1`, `BQ2`, `BQ3`.<br>**1.4 Đối tượng, phạm vi nghiên cứu và Khung KPI:** Chuỗi `DATA -> FORECAST -> RISK -> DECISION -> OPERATIONAL OUTCOME`, phạm vi Module 01 ở 2 tầng đầu, tách *Prediction Quality* vs *Decision Quality*, Bảng định nghĩa KPI bắt buộc. | Tiêu chí 1 (`15đ`) |
| **Chương 2: Cơ sở lý thuyết** (`ch02_cosolythuyet.tex`) | **CHƯƠNG MỚI** *(cô đọng 2–3 trang)* | **2.1 Kiến trúc Xử lý Dữ liệu Lớn & Data Lakehouse:** Tiến hóa từ mô hình **MapReduce** truyền thống sang xử lý phân tán in-memory **Apache Spark** và kiến trúc **Medallion Lakehouse (`Bronze → Silver → Gold`)** trên Delta Lake *(đáp ứng ý thầy nhắc MapReduce một cách trung thực — KHÔNG bịa rằng hệ thống chạy Hadoop MapReduce)*.<br>**2.2 Cơ sở Mô hình Dự báo Chuỗi thời gian:** Nhóm Thống kê (`Seasonal Naïve`, `Harmonic ARIMA`, `Croston-SBA`), nhóm ML/GBDT (`Ridge`, `LightGBM Regression/Tweedie/AnchorRes`), `Hybrid` & `AutoRouted_Champion`. Nêu rõ lý do khoa học **không chọn Deep Learning / LSTM** cho chuỗi cỡ vừa `302` tuần (nguy cơ overfitting cao, khó giải thích hơn GBDT + `TreeSHAP` và thống kê theo `Fourkiotis 2024`, `Abacı 2026`).<br>**2.3 Hiệu chuẩn Khoảng tin cậy (`Split CQR`) và AI Giải thích (`TreeSHAP`).**<br>**2.4 Các Độ đo Đánh giá và Kiểm định Thống kê:** Công thức & ý nghĩa **MSE, RMSE, MAE, WAPE, MASE, $R^2$, Độ phủ Split CQR ($P_{10}$–$P_{90}$), Kiểm định Harvey--Diebold--Mariano (`DM'`)**. *(Lưu ý bắt buộc: bài toán là hồi quy chuỗi thời gian liên tục, **tuyệt đối không dùng Accuracy / F1-Score** của bài toán phân loại).* | Nền tảng lý thuyết (Tiêu chí 1, 3, 4) |
| **Chương 3: Phương pháp nghiên cứu** (`ch03_phuongphap.tex`) | Gộp `ch02_dulieu_quanly.tex` + `ch03_kientruc_pipeline.tex` + bảng kết quả lõi | **3.1 Nguồn gốc dữ liệu, Lưu trữ và Kiểm soát chất lượng** *(từ `ch02` cũ)*: Bảng 3 nguồn dữ liệu (`PostgreSQL` `714,959` POS + `78,884` obs, `MongoDB` `2,481` JSON, `Open-Meteo S3` `19,902` JSON + `75` ngày lễ Serbia), Provenance `OBSERVED/SYNTHETIC`, mô hình lưu trữ đa tầng + bảo mật, Bảng kiểm toán DQ trước--sau (`uv_index_max`, `26` ngày lễ `.ffill()`, tuần `W302` chuẩn hóa `qty_rate`), chẩn đoán thống kê 8 nhóm ATC (`Syntetos--Boylan` & `CCF` thời tiết ERA5).<br>**3.2 Phương pháp triển khai Hệ thống và Mô hình dự báo** *(từ `ch03` cũ)*: Sơ đồ kiến trúc 5 phân vùng, AWS Serverless + Terraform IaC, Databricks Medallion (`Bronze → Silver DLT → Gold` + cổng `ops.product_release`), BI Serving Bridge (`Neon #2 449 MB` + SQL Pushdown), Luồng ML 5 Notebooks (`NB01–NB05`), 3 tầng đặc trưng (`F1/F2/F3`), kiểm toán chống rò rỉ (`Perturbation Test = 0.0`) và Bảng kiểm thử tự động (`212+` tests).<br>**3.3 Thiết lập thực nghiệm và Kết quả theo các độ đo:** Cấu hình phần cứng/môi trường đo + Bảng kết quả mô hình chính `AutoRouted_Champion` trên 8 nhóm ATC (`holdout_52w`) với đủ các độ đo **MSE, RMSE, MAE, WAPE, MASE, $R^2$, CQR 80%**. | Tiêu chí 2 (`15đ`) + Tiêu chí 3 (`20đ`) |
| **Chương 4: Kết quả và thảo luận** (`ch04_ketqua_thaoluan.tex`) | Gộp `ch04_phantich_sosanh.tex` + `ch05_bi_quyetdinh.tex` | **4.1 So sánh với các phương pháp / giải thuật khác theo các độ đo:**<br>• *(a)* So sánh nội bộ 12 mô hình (`Seasonal Naïve`, `SNaïve Weighted`, `Croston-SBA`, `Harmonic ARIMA`, `Ridge`, `LightGBM F1/F1F2/F1F2F3/AnchorRes`, `Hybrid`, `AutoRouted_Champion`) trên **MSE, RMSE, MAE, WAPE, MASE, $R^2$** và kiểm định `Harvey--DM'` (`8/8` ATC thắng `SNaïve` với `p < 0.05`).<br>• *(b)* Đối chuẩn 1:1 với **Paper Fourkiotis & Tsadiras (2024)** (`6/8` vượt MSE XGBoost, nhanh gấp `1,166.9×`: `166.6s` vs `54 giờ`).<br>• *(c)* So sánh Engineering **Baseline (Pandas/PostgreSQL raw) vs Gold Mart SQL Pushdown** và **Scale-up Stress Test (`3×/5×/10×`)** (phần Mạnh Tất đã thực đo & update trên Prism).<br>**4.2 Phân tích đóng góp đặc trưng (`Ablation ERA5`), Giải thích `TreeSHAP` và Bất định `Split CQR`:** Hình `eval_ablation_wape.png`, `eval_treeshap_summary.png`, `eval_fanchart_52w.png` (ERA5 đóng góp `11.3%–25.9%` `TreeSHAP`; `Split CQR` nâng độ phủ `71.7% → 78.8%`).<br>**4.3 Kết quả Trực quan hóa Dashboard BI (5 trang Streamlit & QuickSight) và Nhận xét định lượng** *(từ `ch05` cũ)*: Chèn 5–6 ảnh chụp thật từ Streamlit Cloud + 4 nhận xét định lượng từ số liệu thật.<br>**4.4 Thảo luận, Đề xuất quyết định và Giới hạn trung thực:** Bảng đề xuất hành động `Human-in-the-loop` (Chi phí, Rủi ro, Điều kiện áp dụng) + giải thích trung thực 2 nhóm `M01AE/R03`, giải thích vì sao `R² < 0` ở nhóm bán thưa `N05C` (`67.9%` ngày = 0), và giới hạn quy mô `~715K` dòng. | Tiêu chí 4 (`20đ`) + Tiêu chí 5 (`15đ`) |
| **Chương 5: Kết luận và hướng phát triển đề tài** (`ch05_ketluan.tex`) | Chuyển từ `ch06_tongket_tailap.tex` | **5.1 Kết luận và Đối chiếu Mục tiêu đề tài:** Bảng/đoạn liên kết trực tiếp từng mục tiêu và `BQ1–BQ3` ở Chương 1 với kết quả đạt được.<br>**5.2 Khả năng tái lập hệ thống (*Reproducibility*):** Lệnh clone, `pytest`, 5 notebooks + **ảnh chụp terminal pass `212+` tests**.<br>**5.3 Hướng phát triển đề tài:** Bổ sung tồn kho thực FEFO/Safety Stock/ROP nối sang `RISK → DECISION`, tự động hóa batch weekly, quy đổi `base_qty`. | Tiêu chí 6 (`15đ`) |
| **Tài liệu tham khảo & Phụ lục** | `references.bib`, `appendices/appendix01_rubric_mapping.tex` | `references.bib` (10 nguồn chuẩn `IEEEtran`) + `appendix01_rubric_mapping.tex` (cập nhật lại cột vị trí chương theo **5 chương mới**). | Tiêu chí 6 (`15đ`) |

---

## 2. Bảng Số liệu $R^2$ Thực chứng Đã tính sẵn (Chèn thẳng vào Mục `3.3` & `4.1` — Không cần tính lại)

Toàn bộ giá trị $R^2 = 1 - \dfrac{\sum (y_t - \hat{y}_t)^2}{\sum (y_t - \bar{y})^2}$ dưới đây đã được tính trực tiếp từ file kết quả thực nghiệm thật `artifacts/forecasting/predictions_holdout_52w.parquet` (tập kiểm chứng 52 tuần cuối `W251–W302`):

| ATC | `AutoRouted` ($R^2$) | `SNaïve` ($R^2$) | `SNaïve_W` ($R^2$) | `Ridge_F1F2F3` ($R^2$) | `AnchorRes_F3` ($R^2$) | `Harmonic_ARIMA` ($R^2$) | `Croston_SBA` ($R^2$) | Ghi chú diễn giải nhanh |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **M01AB** | `0.1428` | `-0.5761` | `-0.0670` | **`0.2246`** | `0.0933` | `0.1412` | `0.1428` | Vượt hẳn `SNaïve` (từ âm lên dương) |
| **M01AE** | `0.2320` | `-0.1194` | `0.0804` | `0.2320` | **`0.2857`** | `0.2656` | `0.0904` | Vượt `SNaïve` & `SNaïve_W` |
| **N02BA** | `0.0795` | `-0.6494` | `-1.3939` | `-0.0247` | `0.0745` | `0.0795` | **`0.0848`** | Chuỗi ít mùa vụ, vẫn dương so với `SNaïve` âm sâu |
| **N02BE** | `0.6975` | `0.4662` | `0.6440` | `0.7455` | **`0.7938`** | `0.7272` | `0.4055` | Nhóm chủ lực mượt, mùa vụ mạnh (`R²` cao nhất `0.79`) |
| **N05B** | `0.0480` | `-2.0727` | `-0.6320` | **`0.1912`** | `0.0480` | `-0.0400` | `0.1394` | Phục hồi mạnh từ `SNaïve` (`-2.07`) |
| **N05C** | `-0.2044` | `-2.0241` | `-0.5227` | `-0.2249` | `-0.1111` | `-0.1685` | **`-0.0786`** | Bán thưa (`67.9%` ngày=0) → giải thích vì sao cần `WAPE/MASE/CQR` thay vì chỉ nhìn `R²` |
| **R03** | `0.2687` | `-0.2131` | `-0.1544` | `0.1845` | `0.2687` | **`0.2969`** | `0.2343` | Nhóm biến động (`CV²=0.82`), vẫn vượt xa `SNaïve` |
| **R06** | **`0.6544`** | `0.1655` | `0.4759` | `0.6278` | **`0.6544`** | `0.6112` | `0.4205` | Nhóm dị ứng nhạy thời tiết ERA5 (`R²` tăng `+0.49` vs `SNaïve`) |

> **Lưu ý khi viết nhận xét cho $R^2$:**
> 1. `AutoRouted_Champion` vượt `Seasonal_Naive` về $R^2$ trên cả **8/8 nhóm ATC** (`+0.23` đến `+2.12` điểm $R^2$).
> 2. **Tuyệt đối không** gom gộp tính $R^2$ chung cho cả 8 nhóm ATC trong một bảng vì thang đo sản lượng khác nhau xa (`4.14` đv/tuần ở `N05C` vs `208.63` đv/tuần ở `N02BE`) sẽ gây ảo giác $R^2$ cao giả tạo do chênh lệch phương sai giữa các nhóm.

---

## 3. Bảng Phân công Cụ thể Theo Tên 3 Thành viên (Prism LaTeX + Slide)

| Thành viên & Vai trò | Phần đã làm trên Prism (Giữ nguyên / Tái sử dụng) | Task cụ thể cần sửa trên Prism LaTeX (`report_BigData`) | Phần Slide & Bảo vệ tuần sau (`~15 phút` tổng) |
| :--- | :--- | :--- | :--- |
| **Võ Công Đăng Khôi (`2311708`)**<br/>*(TV A — Mở đầu, Dữ liệu & Tái lập)* | • Đã hoàn thành Chương 1, 2, 6 bản cũ trên Prism *(chưa chèn ảnh)*.<br>• Đã điền đủ tên & MSSV cả 4 thành viên ở `main.tex`. | - [ ] Trong `frontmatter/phancong.tex`, điền bổ sung 2 MSSV còn thiếu (`2312550` và `2313074`) cho đủ bảng phân công nhóm trong báo cáo (`Tổng = 100%`), cập nhật `camdoan.tex` & `tomtat.tex` theo bố cục **5 chương**.<br>- [ ] Chia lại **Chương 1 (`Mở đầu`)** thành 4 tiểu mục `1.1–1.4` theo mẫu Bách Khoa.<br>- [ ] Di chuyển toàn bộ nội dung **Chương 2 cũ** sang làm **Mục `3.1`** trong Chương 3 mới *(không xóa bỏ)*.<br>- [ ] Đổi **Chương 6 cũ** thành **Chương 5 mới (`Kết luận và hướng phát triển đề tài`)**, bổ sung bảng/đoạn đối chiếu trực tiếp với Mục tiêu & `BQ1–BQ3` ở Chương 1.<br>- [ ] Chạy `pytest` trên máy sạch, chụp ảnh màn hình terminal pass `212+` tests và **chèn ảnh** vào Mục `3.2` / `5.2`. | • Sửa nhẹ **Slide `01`** (thêm tên/MSSV 4 thành viên).<br>• Thuyết trình **Slides `01–05` (`4.2 phút`)**: Mở đầu → 3 Câu hỏi nghiệp vụ → 4 Hàng rào KPI → Quy mô 3 nguồn → Medallion & Atomic Gate.<br>• Hỏi lại giảng viên lịch thuyết trình cụ thể tuần sau. |
| **Đoàn Mạnh Tất (`2313074`)**<br/>*(TV B — Lý thuyết, Phương pháp & Thực nghiệm)* | • Đã hoàn thiện `ch04` trên Prism (`i5-12450HX`, `27.7 GB` RAM, `sec:bench_engineering`, `sec:scaleup` `3×/5×/10×`, `Images/scaleup_time_memory.png`). | - [ ] Viết mới **Chương 2 (`Cơ sở lý thuyết`)** gồm 4 tiểu mục ngắn gọn (`2.1` MapReduce → Spark/Lakehouse Medallion; `2.2` Mô hình chuỗi thời gian & lý do không dùng LSTM; `2.3` Split CQR & TreeSHAP; `2.4` Các độ đo hồi quy MSE/RMSE/MAE/WAPE/MASE/$R^2$/DM' và lưu ý không dùng Accuracy/F1-Score).<br>- [ ] Đặt nội dung Chương 3 cũ vào **Mục `3.2`** và viết **Mục `3.3` (`Thiết lập thực nghiệm & Kết quả theo các độ đo`)** dùng bảng độ đo có thêm cột **$R^2$ thật** ở **Mục 2**.<br>- [ ] Chuyển toàn bộ phần đối sánh + Benchmark/Scale-up vừa cập nhật sang **Mục `4.1`** của Chương 4 mới *(giữ nguyên toàn bộ số thực đo đã viết)* và bổ sung cột **$R^2$ so sánh giữa các giải thuật** *(lấy số từ bảng Mục 2)*.<br>- [ ] Tạo/bổ sung lại file `appendices/appendix01_rubric_mapping.tex` ánh xạ lại theo **5 chương mới** *(thư mục `appendices/` trên Prism hiện đang trống)*. | • Cập nhật **Slide `12`** (`baseline-vs-proposed`): đưa số thực đo & Scale-up `3×–10×` lên slide.<br>• Thuyết trình **Slides `06–10` (`4.6 phút`)**: Kiến trúc 5 phân vùng → EDA 8 ATC → Luồng 5 NB → Benchmark `8/8` thắng SNaïve → Ablation ERA5 & `TreeSHAP`. |
| **Nguyễn Thị Cẩm Vân (`2313870`)**<br/>*(TV C — BI, Thảo luận & Xuất PDF)* | • Đã hoàn thiện `ch05` trên Prism (đủ ảnh `Images/page1..5.png`, `page5-1.png`, nhận xét định lượng & `tab:decisions`). | - [ ] Chuyển nguyên nội dung **Chương 5 cũ** vào **Mục `4.2`, `4.3`, `4.4`** của Chương 4 mới (`Kết quả và thảo luận`), khớp mượt với Mục `4.1` của Mạnh Tất *(giữ nguyên các ảnh Dashboard đã chèn, tuyệt đối không dùng số liệu/insight giả)*.<br>- [ ] Ghép phần thảo luận 2 nhóm `M01AE/R03`, giải thích `R² < 0` ở `N05C` và giới hạn `~715K` dòng vào Mục `4.4`.<br>- [ ] Rà soát `main.tex` trên Prism: đổi lệnh `\input{chapters/...}` sang **5 chương mới**, kiểm tra Mục lục / Danh mục hình / Bảng / Tài liệu tham khảo không bị `?` hay lỗi biên dịch, xuất bản **`main.pdf`** sạch. | • Kiểm duyệt tổng thể 15 slides + Live Demo (có thể gắn ảnh chụp live vào **Slide `13`**).<br>• Thuyết trình **Slides `11–15` + Live Demo Web (`4.4 phút`)**: Fan Chart & Paper 2024 → Đối sánh Baseline → bấm Live Demo Streamlit 45s → 4 Quyết định & Giới hạn → Chốt hạ & mời Q&A. |

---

## 4. Hướng dẫn Thao tác Tái cấu trúc trên Prism LaTeX (`report_BigData`) + Prompt mẫu

Trên dự án Prism `report_BigData`, nhóm thực hiện nhanh theo 3 bước sau:

1. **Tạo / đổi tên đúng 5 tệp trong thư mục `chapters/`:**
   - `chapters/ch01_modau.tex`
   - `chapters/ch02_cosolythuyet.tex`
   - `chapters/ch03_phuongphap.tex`
   - `chapters/ch04_ketqua_thaoluan.tex`
   - `chapters/ch05_ketluan.tex`
2. **Cập nhật block `\input{chapters/...}` trong `main.tex` đúng 5 dòng trên:**
   ```latex
   \input{chapters/ch01_modau}
   \input{chapters/ch02_cosolythuyet}
   \input{chapters/ch03_phuongphap}
   \input{chapters/ch04_ketqua_thaoluan}
   \input{chapters/ch05_ketluan}
   ```
3. **Copy Prompt mẫu dưới đây dán trực tiếp vào trợ lý AI của Prism** (nếu muốn AI của Prism tự sắp xếp khung giúp trước khi từng người rà lại phần mình):

```text
Hãy tái cấu trúc dự án LaTeX này từ 6 chương hiện tại sang bố cục 5 chương chuẩn HCMUT theo đúng cấu trúc sau, giữ nguyên toàn bộ nội dung và số liệu thật hiện có của các thành viên (không tự bịa số liệu mới, không dùng dữ liệu giả):

1. Đổi tên/gộp thành 5 file trong chapters/ và cập nhật \input trong main.tex:
   - chapters/ch01_modau.tex (Chương 1: Mở đầu): Giữ toàn bộ ch01 cũ, sắp xếp theo 4 tiểu mục: 1.1 Đặt vấn đề; 1.2 Tổng quan tài liệu; 1.3 Mục đích, mục tiêu và Câu hỏi nghiên cứu; 1.4 Đối tượng, phạm vi nghiên cứu và Khung KPI.
   - chapters/ch02_cosolythuyet.tex (Chương 2: Cơ sở lý thuyết): Viết mới cô đọng 2-3 trang gồm 4 tiểu mục:
     * 2.1 Kiến trúc xử lý dữ liệu lớn & Data Lakehouse (nêu ngắn gọn tiến hóa từ MapReduce sang xử lý phân tán in-memory Apache Spark và Medallion Bronze-Silver-Gold; ghi rõ hệ thống dùng Spark/Delta Lake, không bịa rằng chạy Hadoop MapReduce).
     * 2.2 Cơ sở mô hình dự báo chuỗi thời gian (Seasonal Naive, Harmonic ARIMA, Croston-SBA, Ridge, LightGBM Regression/Tweedie/AnchorRes, Hybrid, AutoRouted_Champion; nêu lý do khoa học không dùng LSTM cho chuỗi cỡ vừa 302 tuần để tránh overfitting và giữ khả năng giải thích).
     * 2.3 Hiệu chuẩn khoảng tin cậy Split CQR và AI giải thích TreeSHAP.
     * 2.4 Các độ đo đánh giá (MSE, RMSE, MAE, WAPE, MASE, R^2, Split CQR coverage, kiểm định Harvey-DM'). Tuyệt đối KHÔNG dùng Accuracy hay F1-Score vì đây là bài toán hồi quy chuỗi thời gian, không phải phân loại.
   - chapters/ch03_phuongphap.tex (Chương 3: Phương pháp nghiên cứu):
     * 3.1 Nguồn gốc dữ liệu, Lưu trữ và Kiểm soát chất lượng (chuyển toàn bộ ch02 cũ + phần EDA Syntetos-Boylan/CCF).
     * 3.2 Phương pháp triển khai Hệ thống và Mô hình dự báo (chuyển toàn bộ ch03 cũ: kiến trúc 5 phân vùng, AWS/Terraform, Databricks Medallion, BI Bridge, ML 5 Notebooks, kiểm thử 212+ tests).
     * 3.3 Thiết lập thực nghiệm và Kết quả theo các độ đo (cấu hình phần cứng/môi trường đo + bảng kết quả AutoRouted_Champion trên 8 ATC gồm MSE, RMSE, MAE, WAPE, MASE, R^2, CQR 80%).
   - chapters/ch04_ketqua_thaoluan.tex (Chương 4: Kết quả và thảo luận):
     * 4.1 So sánh với các phương pháp / giải thuật khác theo các độ đo (giữ nguyên bảng đối sánh 8 ATC, Paper 2024, Benchmark Baseline vs Gold Pushdown và Scale-up 3x/5x/10x vừa được cập nhật; bổ sung cột R^2 so sánh các mô hình).
     * 4.2 Phân tích Ablation ERA5, TreeSHAP và Split CQR.
     * 4.3 Kết quả Trực quan hóa Dashboard BI 5 trang và Nhận xét định lượng (từ ch05 cũ).
     * 4.4 Thảo luận, Đề xuất quyết định và Giới hạn trung thực.
   - chapters/ch05_ketluan.tex (Chương 5: Kết luận và hướng phát triển đề tài): Chuyển từ ch06 cũ, bổ sung phần đối chiếu trực tiếp kết quả với mục tiêu ở Chương 1.

2. Cập nhật lại appendices/appendix01_rubric_mapping.tex cho khớp số chương 1..5 mới và đảm bảo biên dịch pdfLaTeX không lỗi, không vỡ bảng hoặc thiếu reference.
```

---

## 5. Phân công Chi tiết Từng Slide (`01–15`, tổng thời lượng `13.2 phút` / quỹ `15 phút` — Tuần sau)

Trong [`slides/index.html`](slides/index.html), toàn bộ **Speaker Notes** (`SPEAKER_NOTES`) đã được gắn sẵn nhãn `[TV A]`, `[TV B]`, `[TV C]` và thời lượng từng trang để khi nhấn phím **`P`** (**Speaker View**), người nói xem thẳng gợi ý từng ý và đồng hồ đếm ngược.

| Slide | `data-slide-id` | Nội dung chính | Người thuyết trình | Thời lượng | Việc cần chỉnh / Ghi chú thực chiến |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **01** | `cover` | Trang bìa · PharmaFlow Lakehouse & Demand Forecasting | **Khôi (`TV A`)** | `0.5'` | Thêm tên/MSSV 4 SV; kiểm tra đồng bộ màn hình chiếu khi bắt đầu. |
| **02** | `business-context` | Bối cảnh ngành dược & 3 Câu hỏi nghiệp vụ kiểm chứng | **Khôi (`TV A`)** | `0.9'` | Nêu rõ 3 nguồn (`ONYX`, `IRPD`, `Serbia 5631`) và phạm vi `DATA -> FORECAST`. |
| **03** | `kpi-governance` | Khung KPI & 4 Hàng rào Toàn vẹn (`OBSERVED/SYNTHETIC`, `UOM`, `line_count`, `WAPE/CQR`) | **Khôi (`TV A`)** | `0.9'` | Nhấn mạnh tư duy tránh sai số cộng dồn & bóp méo KPI. |
| **04** | `data-sources` | Quy mô 3 nguồn dữ liệu đã kiểm chứng (`714.9K` POS · `19,902` JSON · `474.6K` Gold) | **Khôi (`TV A`)** | `0.9'` | Đọc nhanh 4 tháp số liệu đối soát thực tế, không trộn nguồn. |
| **05** | `medallion-stack` | 3 tầng Medallion (`Bronze → Silver DLT → Gold`) & `ops.product_release` | **Khôi (`TV A`)** | `1.0'` | Chốt lại Atomic Swap sang Neon #2 (`449 MB`) rồi chuyển mic sang **Mạnh Tất**. |
| **06** | `architecture-overview` | Sơ đồ kiến trúc 5 phân vùng (`~$0/tháng`, `100%` thời tiết, `0.08–0.48s` pushdown) | **Mạnh Tất (`TV B`)** | `1.0'` | Diễn giải ngắn gọn luồng AWS Terraform IaC → Databricks → BI → ML. |
| **07** | `eda-diagnostics` | Chẩn đoán 8 nhóm ATC (`Syntetos-Boylan`) & Tương quan trễ ERA5 (`CCF`) | **Mạnh Tất (`TV B`)** | `0.9'` | Chỉ rõ nhóm mượt (`N02BE/R06`), biến động (`R03`) và bán thưa `N05C` (`67.9%` ngày = `0`). |
| **08** | `ml-pipeline-flow` | Luồng 5 Notebooks thống nhất (`166.6s`, `Leakage = 0.0`, `qty_rate`) | **Mạnh Tất (`TV B`)** | `0.8'` | Giải thích xử lý `W302` thiếu `2/7` ngày & Perturbation Leakage test. |
| **09** | `benchmark-atc` | `AutoRouted Champion` vs `Seasonal Naïve` (giảm `31.4%–69.0%` MSE, `DM' p < 0.05` trên `8/8`) | **Mạnh Tất (`TV B`)** | `1.0'` | Nhấn mạnh khóa chọn mô hình theo Val MAE, không nhìn tập Test; có thể nhắc thêm `R²` vượt `8/8` ATC. |
| **10** | `ablation-xai` | Thực chứng Ablation `F1→F2→F3` & `TreeSHAP` (`11.3%–25.9%` từ ERA5) | **Mạnh Tất (`TV B`)** | `0.9'` | Lấy ví dụ `R06` (`25.9%` từ ERA5) và `N02BE`, rồi chuyển mic sang **Vân**. |
| **11** | `fanchart-cqr` | Fan Chart `52W`, Split CQR `P10–P90` (`78.8%`) & Đối chuẩn Paper `2024` (`6/8` vượt MSE, `1,166.9×`) | **Vân (`TV C`)** | `0.9'` | Báo cáo trung thực cả 2 nhóm chưa vượt Paper (`M01AE`, `R03`). |
| **12** | `baseline-vs-proposed` | Đối sánh toàn diện Baseline vs Giải pháp đề xuất (Engineering + ML) | **Vân (`TV C`)** *(Tất điền số)* | `0.9'` | **Mạnh Tất** cập nhật số thực đo & Scale-up `3×–10×` lên Slide `12`; **Vân** thuyết trình. |
| **13** | `bi-dashboard-live` | Dashboard Streamlit 5 trang tiếng Việt + **Bấm Live Demo Cloud** | **Vân (`TV C`)** | `1.3'` | Alt-Tab mở link Streamlit Cloud demo ~45s (Trang 1 → Trang 2/3 → Trang 5); dự phòng bằng ảnh nếu rớt mạng. |
| **14** | `actionable-decisions` | 4 Đề xuất quyết định vận hành & Giới hạn trung thực (`Human-in-the-loop`, chưa gồm ROP/tồn kho) | **Vân (`TV C`)** | `0.8'` | Gắn rõ từng khuyến nghị với điều kiện áp dụng & giới hạn dữ liệu `~715K` dòng. |
| **15** | `closing` | Tổng kết `212+` Unit Tests, khả năng tái lập & Mời Q&A | **Vân (`TV C`)** | `0.5'` | Giữ màn hình slide cuối hoặc tab Live Streamlit sẵn cho phần hỏi đáp hội đồng. |

---

## 6. Quy trình Phối hợp Nhanh Tới Ngày Thuyết trình Tuần sau

1. **Bước 1 — Đổi khung 5 chương trên Prism (`report_BigData`):**
   - Tạo/đổi tên 5 file chương theo **Mục 4** (hoặc dán Prompt mẫu vào Prism AI để dựng khung), bảo toàn nguyên phần **Khôi** (`ch01/02/06` cũ), **Mạnh Tất** (`ch04` Benchmark/Scale-up) và **Vân** (`ch05` ảnh Dashboard & insights).
2. **Bước 2 — Hoàn thiện nội dung, ảnh & số $R^2$:**
   - **Khôi:** Bổ sung 2 MSSV còn thiếu (`2312550`, `2313074`) trong `phancong.tex`, chỉnh Chương 1, Mục `3.1`, Chương 5, chụp & chèn ảnh `pytest` pass `212+` tests.
   - **Mạnh Tất:** Hoàn thiện Chương 2 (MapReduce → Spark/Lakehouse, lý do không dùng LSTM, hệ độ đo hồi quy), Mục `3.2`–`3.3`, Mục `4.1` (ghép cột $R^2$ thật từ **Mục 2** + giữ nguyên số Benchmark/Scale-up), bổ sung `appendices/appendix01_rubric_mapping.tex` và cập nhật **Slide `12`**.
   - **Vân:** Chuyển `ch05` sang Mục `4.2`–`4.4` (giữ nguyên các ảnh Streamlit Cloud đã chèn), kiểm tra liên kết `main.tex` và biên dịch **`main.pdf`** sạch.
3. **Bước 3 — Tổng duyệt & Chốt Slide 15 phút (`Tuần sau`):**
   - Cả 3 bạn rà chéo lần cuối bản `main.pdf` (`0` số giả, `0` nhầm `Accuracy/F1-Score`, khớp số 100% giữa Report & Slide `01–15`).
   - Mở [`slides/index.html`](slides/index.html) trên Chrome/Edge, bấm **`P`** (Speaker View) chạy thử khớp ~`13.2 phút` (dư `~1.8 phút` dự phòng chuyển tab demo và chuyển người).
   - Nếu giảng viên yêu cầu nộp Slide PDF: nhấn **`B`** (tắt hiệu ứng động) → **`Ctrl + P`** → **Landscape** + bật **Background graphics** → Save as PDF.
