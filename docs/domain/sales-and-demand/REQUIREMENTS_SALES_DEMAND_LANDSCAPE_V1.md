# Requirements PharmaFlow — Sales & Demand (Landscape V1)

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | `PF-REQ-SALES-DEMAND-LANDSCAPE-V1` |
| Trạng thái | Bản nháp đề xuất; chưa được stakeholder xác nhận |
| Nguồn nhu cầu | [User Stories Sales & Demand Landscape V1](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md) |
| Phạm vi | Business Monitoring, Sales & Demand Insight, forecast Sales Quantity và Prediction Quality |
| Ngày lập | 2026-11-05 |
| Phân công actor đã xác nhận | Tab 2 cấp quyền đọc MD-01 cho US-01/02/03/04/06/07/11/12/14/15 theo scope assignment; US-03 là Supply Chain Planner và có thêm quyền điều chỉnh forecast. Data admin kiểm định forecast; IT admin vận hành hệ thống. Chi tiết nghiệp vụ vẫn là bản nháp. |

## 1. Mục đích và phạm vi

Đặc tả UR, FR, business/data rules và NFR phát sinh từ user needs được suy ra trực tiếp từ [Landscape](../../docs/Landscape/PharmaFlow_Data_Business_Analytics_Landscape_KPI_Fixed.pdf). Đây là yêu cầu cho nguyên mẫu PharmaFlow DSS; không mô tả POS, ERP, WMS hay hệ thống vận hành nhà thuốc.

Trong phạm vi: xem sales KPI theo chiều có bằng chứng; so sánh và phân tích lịch sử; xem số forecast Sales Quantity theo location/kỳ; đánh giá Prediction Quality nội bộ; hiển thị nhãn và trạng thái nghiệp vụ rõ ràng. Lineage, provenance và metadata run được lưu để truy vết nội bộ, không phải thông tin bắt buộc người dùng màn hình nghiệp vụ phải đọc.

Ngoài phạm vi: ghi hóa đơn; ghi nhận stock movement; cập nhật inventory balance; đổi trả/quality-control; nhận hàng/ASN; tính replenishment order; quyết định tender/bid; tự động transfer, procurement hoặc execution. Các miền này chỉ là nguồn/đích dữ liệu tương lai khi contract được xác định.

## 2. Quy ước và trạng thái evidence

| Nhãn | Ý nghĩa |
|---|---|
| **Landscape scope** | Nhu cầu/KPI được nêu trong Landscape |
| **Project constraint** | Ràng buộc đã có trong project invariant hoặc data contract |
| **Design proposal** | Yêu cầu chi tiết để hiện thực nguyên mẫu, cần stakeholder chấp nhận |
| **Data gate** | Chỉ áp dụng khi có source, grain, unit, provenance và coverage phù hợp |
| **Implementation evidence** | Phân biệt `Landscape scope`, `Modeled locally`, `Implemented locally`, `Verified deployed` |

`Landscape scope` không chứng minh có schema, code hoặc deployment. `SYNTHETIC` không được gọi là dữ liệu observed. `sim.*` là dữ liệu mô phỏng.

Mức ưu tiên trong tài liệu là đề xuất cho thảo luận: **Core** cho Monitoring/Insight, **Supporting** cho lineage/data quality, **Evaluation** cho kiểm định model. Chưa có MoSCoW được stakeholder phê duyệt.

## 3. Actors và user requirements

Tab chung “2. Người dùng & phân quyền” cấp quyền đọc MD-01 cho US-01, US-02, US-03, US-04, US-06, US-07, US-11, US-12, US-14 và US-15 trong scope assignment. Các luồng đọc dùng actor “Người dùng được quyền xem Sales/Forecast”; card Supply Chain trên org chart là đại diện nghiệp vụ, không giới hạn quyền đọc vào riêng chức danh này. US-03 là Supply Chain Planner, kế thừa quyền đọc và là role duy nhất có forecast:adjust. Data admin dùng quyền kỹ thuật để quản trị dữ liệu/kiểm định forecast; IT admin dùng quyền kỹ thuật để vận hành service/job/log. Hai quyền quản trị không tự cấp quyền nghiệp vụ MD-01. KPI Owner vẫn là accountability riêng: Store Manager là ứng viên cho Sales KPI cấp cửa hàng; Regional Manager cho Sales KPI nhiều cửa hàng; team Supply Chain Planning / Demand Management cho Demand/forecast KPI. Mapping owner từng KPI còn cần xác nhận. Xem căn cứ tại [User Stories §3](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md).

Mỗi UR theo khung actor → use case/user goal → nhu cầu người dùng → giá trị cho người dùng, có truy vết về user story và căn cứ. Tên bảng, thuật toán và cách kiểm thử được mô tả trong FR, business/data rules hoặc test scenarios.

### UR-SD-08 — Điều chỉnh một giá trị forecast

**Actor:** Supply Chain Planner (US-03). **User goal:** điều chỉnh một giá trị Forecast Sales Quantity trong scope assignment, ghi lý do và lưu thành version riêng. **Giá trị:** có phương án nghiệp vụ truy vết được, phân biệt với model output mà không ghi đè forecast gốc hay score evaluation. **Truy vết:** US-SD-LS-08 → FR-SD-10.

## 4. Functional Requirements

Mọi FR dưới đây có trạng thái **Proposed** đến khi stakeholder xác nhận. Bảng đầu tóm tắt phạm vi; các mục sau đặc tả hành vi mà người dùng quan sát được. Flow mô tả nghiệp vụ, không quy định API, schema, thư viện biểu đồ hay thuật toán chưa được chọn.

| ID | Tên chức năng | Actor | Mô tả ngắn | Truy vết | Trạng thái |
|---|---|---|---|---|---|
| `FR-SD-01` | Theo dõi Sales Quantity | Người dùng được quyền xem Sales/Forecast | Xem lượng bán theo kỳ và các chiều có contract hỗ trợ. | UR-SD-01; US-SD-LS-01 | Proposed |
| `FR-SD-02` | So sánh Sales Quantity | Người dùng được quyền xem Sales/Forecast | So sánh các đối tượng hoặc kỳ có dữ liệu tương thích. | UR-SD-02; US-SD-LS-02 | Proposed |
| `FR-SD-03` | Xem xu hướng và mùa vụ | Người dùng được quyền xem Sales/Forecast | Xem pattern lịch sử và mức đủ dữ liệu cho nhận định mùa vụ. | UR-SD-03; US-SD-LS-03 | Proposed |
| `FR-SD-04` | Xem Forecast Sales Quantity theo location/kỳ | Người dùng được quyền xem Sales/Forecast | Xem con số theo từng location và kỳ; hỗ trợ chọn một hoặc nhiều location khi có forecast. | UR-SD-04; US-SD-LS-04 | Proposed |
| `FR-SD-05` | Đối soát dữ liệu và kiểm định forecast | Data admin | Kiểm tra dữ liệu, đọc hồ sơ evaluation, so sánh baseline và lưu kết luận kiểm định. | UR-SD-05; US-SD-LS-05 | Proposed; actor đã xác nhận |
| `FR-SD-06` | Hiển thị ngữ cảnh nghiệp vụ Sales/Forecast | Người dùng được quyền xem Sales/Forecast | Hiển thị nhãn loại số liệu, location, kỳ và đơn vị đã xác nhận; lineage kỹ thuật được lưu nội bộ. | UR-SD-06; US-SD-LS-06 | Proposed |
| `FR-SD-09` | Theo dõi vận hành hệ thống | IT admin | Xem trạng thái dịch vụ/job, lịch chạy và log theo job/run ID theo quyền. | UR-SD-07; US-SD-LS-07 | Proposed; actor đã xác nhận |
| `FR-SD-10` | Điều chỉnh một giá trị forecast | Supply Chain Planner (US-03) | Tạo version điều chỉnh riêng có lý do trong scope; giữ nguyên model output và score gốc. | UR-SD-08; US-SD-LS-08 | Proposed; actor và quyền được xác định theo tab 2 |

### FR-SD-01 — Theo dõi Sales Quantity

- **Actor và mục đích:** Người dùng được quyền xem Sales/Forecast xem lượng bán quan sát được theo phạm vi đang lập kế hoạch.
- **Kích hoạt và điều kiện trước:** actor mở chức năng Sales và chọn kỳ; dữ liệu nguồn đã được nạp, có trạng thái provenance và dimension contract.
- **Đầu vào:** kỳ bắt đầu/kết thúc; product/group, location hoặc channel khi các chiều đó có trong source contract.
- **Đầu ra và giao diện:** số lượng, đơn vị, grain, kỳ và nguồn; bảng hoặc biểu đồ có nhãn rõ; chiều không tồn tại được ghi `unavailable`/`unknown`.
- **Xử lý:** tổng hợp không vượt grain nguồn; chỉ cộng quantity khi UOM/grain tương thích; giữ nhãn observed/derived/synthetic.
- **Phân quyền và hậu điều kiện:** actor có sales:read trong scope được gán; thao tác xem không làm thay đổi source facts.
- **Luồng chính:** chọn kỳ → chọn chiều khả dụng → hệ thống kiểm tra coverage và tính tương thích → hiển thị kết quả kèm metadata.
- **Ngoại lệ:** không có bản ghi; quantity bằng zero; thiếu dimension; nguồn không có provenance; lỗi tải dữ liệu. Mỗi trạng thái phải được biểu diễn riêng, không thay missing bằng zero.
- **Acceptance criteria:** `AC-SD-01-01` hiển thị đúng grain, đơn vị và kỳ; `AC-SD-01-02` không dựng dimension/source fact còn thiếu; `AC-SD-01-03` phân biệt zero, no record và nguồn synthetic.
- **Liên kết:** BR-SD-01–06, BR-SD-09; NFR-SD-01/02; TC-SD-01/02/04/05/11.

### FR-SD-02 — So sánh Sales Quantity

- **Actor và mục đích:** Người dùng được quyền xem Sales/Forecast so sánh nhóm hoặc kỳ để nhận diện chênh lệch cần phân tích.
- **Kích hoạt và điều kiện trước:** actor chọn hai hoặc nhiều đối tượng/kỳ; mỗi chuỗi có measure và metadata đủ để kiểm tra tính tương thích.
- **Đầu vào:** tập đối tượng, kỳ, measure, đơn vị và grain.
- **Đầu ra và giao diện:** giá trị và chênh lệch/thứ hạng trong tập chọn, cùng tập so sánh, kỳ, đơn vị và grain.
- **Xử lý:** kiểm tra measure, unit, grain và coverage trước khi tính; nếu cần tổng hợp giữa grain, chỉ làm theo rule đã xác nhận.
- **Permissions và hậu điều kiện:** chỉ actor được cấp quyền xem dữ liệu tương ứng; không cập nhật source facts.
- **Luồng chính:** chọn tập/kỳ → hệ thống kiểm tra khả năng so sánh → tính và hiển thị kết quả.
- **Ngoại lệ:** UOM/grain khác nhau; coverage thiếu; dimension không được hỗ trợ; thiếu kỳ; request tải lỗi. Hiển thị lý do và không xếp hạng các chuỗi không tương thích.
- **Acceptance criteria:** `AC-SD-02-01` kết quả luôn nêu tập và kỳ so sánh; `AC-SD-02-02` không so sánh trực tiếp chuỗi không tương thích; `AC-SD-02-03` thứ hạng không bị diễn giải thành tốt/xấu khi chưa có ngưỡng nghiệp vụ.
- **Liên kết:** BR-SD-03/04/06; NFR-SD-02/06/08/09; TC-SD-03/13.

### FR-SD-03 — Xem xu hướng và biểu hiện mùa vụ

- **Actor và mục đích:** Người dùng được quyền xem Sales/Forecast xem biến động lịch sử để xem xét trong lập kế hoạch.
- **Kích hoạt và điều kiện trước:** actor chọn measure, series và khoảng thời gian; dữ liệu có coverage thời gian có thể đánh giá.
- **Đầu vào:** Sales Quantity, series/grain, kỳ và metadata về coverage.
- **Đầu ra và giao diện:** chuỗi lịch sử và các pattern xu hướng; kết luận mùa vụ chỉ xuất hiện khi phương pháp/coverage phù hợp và được mô tả.
- **Xử lý:** mô tả lịch sử tách khỏi suy luận mùa vụ; không suy nhu cầu bị mất bằng cách so forecast với sales.
- **Permissions và hậu điều kiện:** chức năng chỉ đọc; trạng thái đủ/thiếu dữ liệu được giữ cùng kết quả.
- **Luồng chính:** chọn series/kỳ → hệ thống kiểm tra coverage → hiển thị lịch sử và mức bằng chứng của nhận định.
- **Ngoại lệ:** chuỗi quá ngắn, thiếu chu kỳ, missing period hoặc provenance không rõ; hiển thị “chưa đủ dữ liệu” và phạm vi thiếu.
- **Acceptance criteria:** `AC-SD-03-01` chart thể hiện measure, grain, kỳ; `AC-SD-03-02` không tuyên bố mùa vụ khi điều kiện chưa đủ; `AC-SD-03-03` sales không bị gắn nhãn thành demand history.
- **Liên kết:** BR-SD-01/04/05; NFR-SD-01/02/08/09; TC-SD-04/05/12.

### FR-SD-04 — Xem Forecast Sales Quantity

- **Actor và mục đích:** Người dùng được quyền xem Sales/Forecast xem số Forecast Sales Quantity theo location và kỳ để tham khảo khi lập kế hoạch.
- **Kích hoạt và điều kiện trước:** actor chọn một hoặc nhiều location và kỳ forecast; hệ thống có output forecast tương ứng. FR này không tạo hoặc khởi chạy model.
- **Đầu vào:** con số forecast theo location/kỳ và đơn vị nếu được xác nhận. Run metadata, provenance và metadata kỹ thuật được kiểm tra/lưu nội bộ.
- **Đầu ra và giao diện:** số forecast theo từng location và kỳ; location được đặt tên theo nghĩa business có trong contract (ví dụ cửa hàng hoặc node); Sales history có nhãn riêng nếu cùng màn hình.
- **Xử lý:** kiểm tra target, location, kỳ và metadata nội bộ trước khi công bố; không cộng gộp location ngầm định và không thay location bằng một loại khác.
- **Permissions và hậu điều kiện:** actor có forecast:read trong scope được gán; không cập nhật model hay dữ liệu nguồn.
- **Luồng chính:** chọn một/nhiều location và kỳ → hệ thống tìm output đủ điều kiện → hiển thị số riêng theo location/kỳ với nhãn business.
- **Ngoại lệ:** chưa có output cho location/kỳ hoặc run nội bộ chưa hợp lệ; giao diện báo ngắn gọn rằng chưa có forecast, còn chi tiết kỹ thuật được ghi trong log/hồ sơ nội bộ. Không tạo giá trị thay thế.
- **Acceptance criteria:** `AC-SD-04-01` target được gắn nhãn Forecast Sales Quantity; `AC-SD-04-02` mỗi location hiển thị riêng theo kỳ, không tự tổng hợp; `AC-SD-04-03` chỉ hiện unit đã xác nhận; `AC-SD-04-04` không hiển thị model/version, protocol, cutoff kỹ thuật, run ID hay lineage trong màn hình Supply Chain; `AC-SD-04-05` dữ liệu mô phỏng có nhãn business dễ hiểu và missing khác zero.
- **Liên kết:** BR-SD-01/05/07; NFR-SD-01/05/06/09; TC-SD-06/07/12/13.

### FR-SD-05 — Data admin đối soát dữ liệu và kiểm định forecast

- **Actor và mục đích:** Data admin quản trị chất lượng dữ liệu và kiểm định Prediction Quality theo phân công đã xác nhận.
- **Kích hoạt và điều kiện trước:** Data admin chọn dữ liệu/run cần kiểm tra; có source contract, evaluation protocol, actuals và baseline để xác định tính hợp lệ.
- **Đầu vào:** protocol, forecast, baseline, target, grain, unit, origins, horizons, actuals và metric definitions.
- **Đầu ra:** Data admin đọc được nguồn/snapshot, đơn vị, location mapping, missing/duplicate, provenance, metadata run và hồ sơ metric/evaluation; kết luận kiểm định lưu cùng bằng chứng. Supply Chain chỉ nhận kết quả nghiệp vụ.
- **Xử lý:** chỉ dùng thông tin có trước mỗi forecast origin; model và baseline dùng cùng origins/target/horizon/actuals; Prediction Quality được lưu tách khỏi Decision Quality.
- **Quyền và hậu điều kiện:** Data admin được phân công truy cập hồ sơ dữ liệu/evaluation; quyền chi tiết theo dataset/run và thao tác thực thi còn cần role matrix. Kết luận ghi actor/thời điểm và tham chiếu bằng chứng, không sửa đè source facts/score. IT admin không mặc định được quyền kết luận chất lượng model.
- **Luồng chính:** Data admin chọn snapshot/run → kiểm tra dữ liệu, temporal validity và tính tương thích → xem metric model/baseline → ghi kết luận cùng bằng chứng. Sự cố dịch vụ/job chuyển IT admin; lỗi dữ liệu/model do Data admin xem xét.
- **Ngoại lệ:** actuals, baseline, origins hoặc protocol thiếu/không tương thích; phát hiện leakage; run chưa hoàn tất. Đánh dấu invalid/không đánh giá được trong hồ sơ nội bộ.
- **Acceptance criteria:** `AC-SD-05-01` temporal validity được kiểm tra theo từng origin; `AC-SD-05-02` baseline/model dùng cùng phạm vi; `AC-SD-05-03` Prediction Quality tách khỏi Decision Quality; `AC-SD-05-04` Data admin đọc metric/protocol trong phạm vi quyền, các trường này không xuất hiện trên màn hình Supply Chain; `AC-SD-05-05` điều kiện thiếu được ghi là chưa đánh giá được, không tự tạo score; `AC-SD-05-06` lưu kết quả kiểm tra dữ liệu và kết luận kèm actor/thời điểm/bằng chứng.
- **Liên kết:** BR-SD-07; protocol tại §4.2; NFR-SD-05/07; TC-SD-08–10/17.

### FR-SD-06 — Hiển thị ngữ cảnh nghiệp vụ Sales/Forecast

- **Actor và mục đích:** Người dùng được quyền xem Sales/Forecast đọc nhãn và ngữ cảnh business cơ bản của số Sales/Forecast.
- **Kích hoạt và điều kiện trước:** actor xem sales value hoặc forecast theo location/kỳ; nhãn business và đơn vị được xác định nếu có căn cứ.
- **Đầu vào:** giá trị, loại số liệu (Sales history/Forecast Sales Quantity), location, kỳ, đơn vị đã xác nhận và trạng thái khả dụng.
- **Đầu ra và giao diện:** các trường business nêu trên; trạng thái thiếu được diễn đạt ngắn gọn, dễ hiểu. Không hiển thị source ID, technical grain, provenance code, cutoff, model/protocol version hay run ID.
- **Xử lý:** hệ thống giữ lineage/provenance ở hồ sơ nội bộ; chuyển trạng thái kỹ thuật ảnh hưởng kết quả thành thông báo business, không tự suy nghĩa cho field chưa có contract.
- **Permissions và hậu điều kiện:** Supply Chain chỉ đọc thông tin theo quyền đã xác nhận; truy vấn không đổi metadata nguồn.
- **Luồng chính:** mở kết quả → hệ thống lấy business label/location/kỳ/unit → hiển thị con số cùng trạng thái phù hợp.
- **Ngoại lệ:** thiếu location, kỳ, unit hoặc output; hiển thị phần business biết được và báo thiếu dữ liệu bằng ngôn ngữ đơn giản. Chi tiết lineage thiếu được giữ trong hồ sơ nội bộ.
- **Acceptance criteria:** `AC-SD-06-01` phân biệt Sales history với forecast và mô phỏng; `AC-SD-06-02` location/kỳ/unit chỉ hiện theo contract; `AC-SD-06-03` missing khác zero; `AC-SD-06-04` technical lineage/run metadata vẫn truy vết được nội bộ nhưng không bị yêu cầu trên màn hình Supply Chain.
- **Liên kết:** BR-SD-01/02/05; NFR-SD-01/02/05/08; TC-SD-12/14.

### FR-SD-09 — IT admin theo dõi vận hành hệ thống

- **Actor và mục đích:** IT admin theo dõi dịch vụ/job và xử lý sự cố vận hành trong phạm vi Sales & Demand.
- **Đầu vào:** trạng thái dịch vụ/job, lịch chạy, job/run ID, thời điểm bắt đầu/kết thúc và log theo contract hiện có.
- **Đầu ra:** thông tin vận hành theo job/run, trạng thái thành công/lỗi/chưa biết và chi tiết lỗi phù hợp quyền; credentials và sensitive values không xuất hiện trong log.
- **Luồng chính:** IT admin chọn dịch vụ/job hoặc run → xem trạng thái/lịch/log → ghi nhận vấn đề và hướng xử lý; chuyển vấn đề dữ liệu hoặc chất lượng forecast cho Data admin.
- **Quyền và ngoại lệ:** phân công vận hành đã xác nhận; quyền retry/restart/thay lịch và quy trình thực thi cần chốt riêng. Thiếu telemetry phải thể hiện chưa biết, không tự coi job thành công. Không mặc định IT admin được sửa dữ liệu hoặc kết luận kiểm định forecast.
- **Acceptance criteria:** `AC-SD-09-01` trạng thái và log truy được theo job/run ID khi contract cung cấp; `AC-SD-09-02` quyền truy cập được kiểm soát và log không lộ thông tin nhạy cảm; `AC-SD-09-03` lỗi vận hành và vấn đề dữ liệu/model có đầu mối xử lý rõ; `AC-SD-09-04` không thực hiện retry/restart/thay lịch khi chưa có quyền/quy trình được xác nhận.
- **Liên kết:** UR-SD-07; US-SD-LS-07; NFR-SD-07/09; TC-SD-14/16.

### 4.1. Ánh xạ mã FR cũ

| Mã cũ | Xử lý khi viết lại | Truy vết mới |
|---|---|---|
| `FR-SD-01`–`FR-SD-06` | Giữ mã và đặc tả chi tiết theo cùng capability. | Các FR-SD-01–06 ở trên. |
| `FR-SD-07` | Không giữ như một capability độc lập; các quy tắc được đặt ở BR-SD-01–06, BR-SD-09 và acceptance criteria liên quan. | BR-SD-01–06/09; FR-SD-01–06. |
| `FR-SD-08` | Không giữ như một capability độc lập; các lỗi/điều kiện thiếu được đặt trong alternative/error flows của FR tương ứng. | FR-SD-01–05; TC-SD-02/03/07/09/13. |

Các mã FR-SD-07/08 đã phát hành không được tái sử dụng.

### 4.2. Protocol đánh giá forecast được FR-SD-05 sử dụng

- Dùng rolling-origin/temporal backtesting; tại mỗi forecast origin, tập huấn luyện và feature chỉ chứa thông tin có trước origin đó.
- Model và baseline dùng cùng origins, target, series/grain, unit, horizon, actuals và evaluation period. Nếu một yếu tố khác nhau, kết quả không được trình bày như phép so sánh ngang hàng.
- Baseline đơn giản được báo cáo cạnh model. MAE, RMSE, WAPE và Bias là các metric ứng viên; stakeholder/model protocol phải chốt metric, định nghĩa, đơn vị và xử lý mẫu số trước khi dùng nghiệm thu.
- Lưu cutoff, origins, horizon, actuals reference, baseline/model version, protocol và metric definitions để tái lập evaluation.
- Prediction Quality được trình bày riêng với stockout/service/fill, average inventory, overstock, expiry/wastage và simulated total cost. Không kết luận chất lượng quyết định chỉ từ forecast error.
- Thiếu actuals, coverage, protocol hoặc baseline tương thích thì trạng thái là `not evaluable`/`invalid`, không sinh score thay thế.

## 5. Business và data rules

| ID | Rule | Căn cứ | Trạng thái |
|---|---|---|---|
| `BR-SD-01` | Về nghĩa nghiệp vụ, sales là lượng bán; nó có thể thấp hơn demand khi stockout. Một trường quantity trong dataset chưa tự chứng minh đó là actual sales đã kiểm chứng; giữ provenance và mức xác nhận nguồn. Không suy demand bằng cách lấy forecast trừ sales. | Landscape trang 5, 14; Project invariant; source profiles | Bắt buộc |
| `BR-SD-02` | Một KPI phải thuộc business taxonomy và có lineage về Category/SubCategory; forecasting/risk/opportunity là Insight, không phải Category/SubCategory. | Landscape trang 4, 11, 15 | Bắt buộc |
| `BR-SD-03` | Không mặc định observation aggregate là transaction/SKU fact; không làm tăng độ chi tiết vượt grain nguồn. | Source contract v2; Project invariant | Bắt buộc |
| `BR-SD-04` | Không coi bản ghi bị thiếu là quantity zero; phải giữ khoảng trống/coverage trong phép so sánh. | Project data semantics | Bắt buộc |
| `BR-SD-05` | Không trộn source facts với dữ liệu sinh tổng hợp; giữ provenance/mức xác nhận của source, và kết quả từ simulator mang nhãn `SYNTHETIC`. | Landscape trang 14; Project invariant | Bắt buộc |
| `BR-SD-06` | Quantity chỉ được tổng hợp khi UOM và grain tương thích; conversion cần mapping có căn cứ. | Source contract và data dictionary | Bắt buộc |
| `BR-SD-07` | Forecast evaluation dùng rolling-origin/temporal backtesting và baseline đơn giản; prediction metric và operational/decision metric tách biệt. | Project invariants; Landscape trang 11–12 | Bắt buộc |
| `BR-SD-08` | Approval là review gate, không tự chứng minh execution; module Sales không tạo lệnh kho/mua/transfer. | Landscape trang 10, 12; Project invariant | Bắt buộc |
| `BR-SD-09` | Khi source contract phân biệt `demand_location_id` với `fulfillment_location_id`, Sales by Location dùng đúng nghĩa location được xác nhận; không coi địa điểm fulfillment là nơi phát sinh sales/demand nếu chưa có mapping nghiệp vụ. | Source PostgreSQL v2 contract; Project invariant | Bắt buộc |

## 6. Non-functional Requirements

NFR mô tả mức chất lượng cần đạt và cách xác minh. Mục tiêu chưa có căn cứ được để `TBD`; con số ở báo cáo mẫu Tripjoy không được chuyển thành SLA PharmaFlow. Semantic rules, backtesting và so sánh evaluation được đặc tả ở BR/FR/protocol để tránh lặp lại cùng một nội dung ở NFR.

| ID | Nhóm chất lượng | Yêu cầu và cách đo | Mục tiêu/trạng thái | Căn cứ |
|---|---|---|---|---|
| `NFR-SD-01` | Traceability | Mỗi KPI/forecast được công bố có lineage và metadata do source/run contract cung cấp: grain, unit, period/cutoff, provenance; giá trị chưa có phải được ghi unknown/unavailable trong hồ sơ truy vết nội bộ. Đối chiếu output với source/run manifest; không yêu cầu Supply Chain đọc technical metadata trên màn hình nghiệp vụ. | Required metadata: theo contract; phạm vi metadata contract và mọi ngoại lệ cần xác nhận. Proposed. | Landscape KPI ownership/lineage; Project invariant |
| `NFR-SD-02` | Semantic display integrity | Nhãn, giá trị và metadata hiển thị phải phản ánh đúng loại evidence và trạng thái dữ liệu; kiểm bằng cases observed/derived/synthetic, missing/zero, không tương thích unit/grain và location semantics. | Không hiển thị nhầm nghĩa; chi tiết kiểm tra tại BR-SD-01–06/09 và FR acceptance criteria. Proposed. | Project invariants; Source contract |
| `NFR-SD-05` | Reproducibility | Với mỗi forecast/evaluation, hệ thống lưu nội bộ source snapshot, cutoff/origins, horizon, model/baseline/protocol version, metric definition và run identifier; lưu seed/config nếu phương pháp có yếu tố ngẫu nhiên. Các trường này phục vụ truy vết/tái lập, không phải thông tin UI cho Supply Chain. | Required fields theo model/run contract; contract chưa xác nhận. Proposed. | Design proposal; model/run contract cần chốt |
| `NFR-SD-06` | Performance | Đo thao tác xem/lọc/so sánh và thời gian hoàn tất evaluation job; lưu kích thước dataset, số series, concurrency, cấu hình môi trường và percentile trong hồ sơ kiểm thử nội bộ, không phải giao diện business. | p95/throughput và workload target: `TBD`, cần stakeholder xác nhận. | ISO/IEC 25010:2023 làm taxonomy; chưa có workload/SLA |
| `NFR-SD-07` | Security/access | Mọi request phải kiểm `permission → data scope → SoD` liên quan → điều kiện trạng thái trước khi trả dữ liệu hoặc ghi. Backend giới hạn danh sách, filter, detail, aggregate và reference theo assignment; kiểm tra lại quyền trước ghi; audit actor, permission, resource, outcome, thời điểm và before/after cho thay đổi. Credential/MFA/session không thuộc module. | Role MD-01 và phạm vi là policy đã xác định tại tab 2; cơ chế xác thực, thực thi DB/RLS, retention và cách triển khai audit còn `TBD`. Yêu cầu thiết kế; chưa phải implementation evidence. | Tab “2. Người dùng & phân quyền”; OWASP ASVS 5.0.0 |
| `NFR-SD-08` | Usability/accessibility | Nếu có UI, đánh giá task completion cho xem KPI, so sánh, xem forecast và diễn giải lineage/error state; kiểm keyboard/contrast/labels theo success criteria được chọn. | User group, success criteria và mức WCAG 2.2: `TBD`, không tuyên bố conform trước khi đo. | ISO/IEC 25010:2023; WCAG 2.2 |
| `NFR-SD-09` | Reliability | Với lỗi tải hoặc dữ liệu chỉ có một phần, UI phải thể hiện trạng thái thành công/lỗi/thiếu riêng; user có thể thử lại theo flow được chốt; không trình trạng thái lỗi thành số liệu hợp lệ. | Hành vi lỗi ở FR flows; availability/error-rate target: `TBD`. | Design proposal; chưa có vận hành/SLA |
| `NFR-SD-10` | Maintainability | Định nghĩa KPI, rule, metric, nguồn và trace giữa UR/FR/BR/TC có mã ổn định, tài liệu hóa và cập nhật cùng thay đổi requirements. | Quy trình review/versioning cần xác nhận trước baseline. Proposed. | ISO/IEC 25010:2023 taxonomy; project traceability needs |

`NFR-SD-03` (Temporal validity) và `NFR-SD-04` (Evaluation comparability) được chuyển thành protocol tại §4.2 và acceptance criteria FR-SD-05. Hai mã cũ đã retire, không tái sử dụng. Khả năng mở rộng, availability SLA, backup và recovery được ghi vào danh sách quyết định cần chốt; hiện chưa đủ thông tin triển khai để đặt metric/threshold hoặc tạo cam kết NFR.

### 6.1. Quyết định chất lượng còn chờ xác nhận

| Quyết định | Thông tin cần chốt | Trạng thái |
|---|---|---|
| Tải và hiệu năng | Dataset/series size, concurrency, thao tác đo, p95/throughput mục tiêu, thiết bị và môi trường. | TBD |
| Availability và reliability | Giờ vận hành, SLA/SLO và cách tính downtime/error rate. | TBD |
| Recovery/backup | Dữ liệu cần backup, retention, RPO/RTO và chủ thể chịu trách nhiệm. | TBD |
| Access/security | Cơ chế xác thực/credential/MFA/session, thực thi scope ở DB/RLS, retention và chi tiết triển khai audit. Role MD-01, scope assignment, SoD và audit fields đã có policy tại tab 2. | Policy đã xác định; chi tiết triển khai TBD |
| Usability/accessibility | Nhóm người dùng, thiết bị, tác vụ ưu tiên và mức WCAG nghiệm thu. | TBD |

## 7. Kịch bản nghiệm thu đề xuất

| ID | Tình huống | Kết quả mong đợi |
|---|---|---|
| `TC-SD-01` | Source có product/store/channel/time và coverage hợp lệ | Sales quantity hiển thị đúng grain, period và unit theo contract. |
| `TC-SD-02` | Source thiếu channel hoặc location | Dimension được ghi unknown/unavailable; không tạo fact/dimension thay thế. |
| `TC-SD-03` | So sánh hai series khác UOM/grain hoặc coverage | Không tính chênh lệch/xếp hạng trực tiếp; nêu nguyên nhân. |
| `TC-SD-04` | Kỳ không có record so với quantity zero đã ghi | UI phân biệt no record với zero. |
| `TC-SD-05` | Observation và POS-like synthetic cùng nguồn gốc | Không trình bày như hai nguồn Sales observed độc lập; provenance được phân biệt. |
| `TC-SD-06` | Forecast hợp lệ cho location/kỳ được chọn | Người dùng được quyền xem Sales/Forecast thấy con số Forecast Sales Quantity theo từng location và kỳ, cùng đơn vị đã xác nhận; technical metadata được lưu nội bộ, không hiện trên màn hình nghiệp vụ. |
| `TC-SD-07` | Forecast run thiếu metadata nội bộ, lỗi hoặc chưa hoàn tất | Không công bố con số không hợp lệ; Người dùng được quyền xem Sales/Forecast nhận thông báo nghiệp vụ ngắn gọn, chi tiết kỹ thuật nằm trong hồ sơ nội bộ. |
| `TC-SD-08` | Backtest feature/label chứa dữ liệu sau forecast origin | Evaluation bị đánh dấu invalid/không công bố như kết quả hợp lệ. |
| `TC-SD-09` | Model và baseline lệch evaluation origin/horizon/target | Không trình bày như so sánh ngang hàng. |
| `TC-SD-10` | Forecast error tốt hơn nhưng decision metrics xấu hơn | Prediction Quality và Decision Quality được trình bày tách biệt. |
| `TC-SD-11` | Series không đủ chu kỳ/coverage để nhận định mùa vụ | Trả trạng thái “chưa đủ dữ liệu”, không khẳng định có mùa vụ. |
| `TC-SD-12` | Thiếu lineage/provenance nội bộ hoặc KPI owner chưa xác nhận | Lưu trạng thái thiếu để truy vết; UI không tự điền và chỉ hiển thị thông tin business đã xác nhận, không yêu cầu Supply Chain đọc metadata kỹ thuật. |
| `TC-SD-13` | Widget/query lỗi hoặc một phần dữ liệu tải thất bại | Hiển thị lỗi/phần thiếu riêng với phần thành công; cung cấp retry nếu thao tác cho phép. |
| `TC-SD-14` | Role không có permission hoặc resource ngoài scope được gán | Từ chối; không trả dữ liệu/location/aggregate/reference ngoài quyền; ghi audit outcome theo policy. |
| `TC-SD-15` | Demand location khác fulfillment location theo contract | Sales breakdown dùng đúng nghĩa location; không thay bằng fulfillment location. |
| `TC-SD-16` | IT admin tra cứu một job/run lỗi hoặc thiếu telemetry | Xem trạng thái/lịch/log theo quyền; thiếu telemetry ghi chưa biết; vấn đề dữ liệu/model chuyển Data admin; không mặc định retry/restart hoặc thay lịch. |
| `TC-SD-17` | Data admin kiểm tra snapshot/run và ghi kết luận forecast | Xem dữ liệu/metadata/metric theo quyền; lưu kết luận cùng actor/thời điểm/bằng chứng; Supply Chain không nhận hồ sơ kỹ thuật; không sửa đè source facts/score. |

Đây là acceptance scenarios đề xuất, chưa phải bằng chứng test đã chạy. Policy quyền và scope của TC-SD-14 đã được xác định tại tab 2; dòng này không xác nhận auth hay enforcement đã được triển khai.

## 8. Ma trận truy vết

| Landscape need | Story | UR | FR | NFR / test |
|---|---|---|---|---|
| Sales quantity/product/channel/location/time (tr.5, 11) | US-SD-LS-01 | UR-SD-01 | FR-SD-01 | NFR-SD-01/02/06/09; TC-SD-01/02/04/05/15 |
| High/low product, trend, seasonal pattern (tr.5, 10) | US-SD-LS-02/03 | UR-SD-02/03 | FR-SD-02/03 | NFR-SD-02/06/08/09; TC-SD-03/04/11/13 |
| Forecast Sales Quantity by location/period (tr.5, 10, 12) | US-SD-LS-04 | UR-SD-04 | FR-SD-04 | NFR-SD-01/05/06/09; TC-SD-06/07/12/13 |
| Data admin kiểm định Prediction Quality; Prediction ≠ Decision Quality (tr.11–12; phân công 2026-11-05) | US-SD-LS-05 | UR-SD-05 | FR-SD-05; protocol §4.2 | NFR-SD-05/07; TC-SD-08–10/17; technical metrics are not a Supply Chain UI requirement |
| Business labels; observed sales, forecast and synthetic semantics (tr.11, 14) | US-SD-LS-06 | UR-SD-06 | FR-SD-06; BR-SD-01–06/09 | NFR-SD-01/02/05/08; TC-SD-02/05/12/15 |
| IT admin vận hành hệ thống (phân công người dùng 2026-11-05) | US-SD-LS-07 | UR-SD-07 | FR-SD-09 | NFR-SD-07/09; TC-SD-14/16 |
| Điều chỉnh một giá trị forecast theo quyền MD-01 | US-SD-LS-08 | UR-SD-08 | FR-SD-10 | NFR-SD-07; TC-SD-18–21; chỉ US-03 có `forecast:adjust` |
| Sales/forecast input to Inventory insight/decision (tr.10, 12) | **Deferred need; no US accepted** | — | — | Chưa có consumer, data/decision contract hay outcome criteria; see §9.1 |

## 9. Hiện trạng và khoảng trống

| Evidence level | Trạng thái tại repo đã kiểm tra |
|---|---|
| Landscape scope | Sales KPI, Sales & Demand Insight, Forecast Sales Quantity, KPI lineage, semantics và cross-domain optimization được nêu trong Landscape |
| Modeled locally | Source PostgreSQL v2 có `pos.sales_observation` (source facts đã aggregate) cùng order/line contract; observations không phải POS orders. Package docs/schema phân biệt facts nguồn với record POS synthetic |
| Implemented locally | Package có code chuẩn bị, nạp và đối soát các source dataset. Đây là source-data pipeline evidence; không phải DSS forecast, analytics, inventory decision hay UI evidence |
| Verified deployed | Package README ghi source database v2 đã được nạp/đối soát cho các dataset được liệt kê. Không xác nhận deployment của chức năng Sales & Demand DSS hoặc forecast model/evaluation service |

### 9.1. Data readiness và phân loại khả thi

Các trạng thái dưới đây đánh giá contract/data/code, không thay thế nhu cầu nghiệp vụ trong Landscape:

| Nhu cầu | Phân loại hiện tại | Bằng chứng và giới hạn | Bước cần có trước nghiệm thu DSS |
|---|---|---|---|
| Theo dõi Sales Quantity | **Có source contract/data hỗ trợ ở grain nguồn** | `pos.sales_observation` lưu fact aggregate; package README ghi các source dataset đã được nạp/đối soát. Nguồn khác nhau về grain/provenance; Long Châu không có sales; không phải mọi source có cùng product/location/channel/UOM | Chọn dataset/use case và xác nhận KPI, dimension, unit, coverage; giữ nguồn/derived/synthetic phân biệt |
| So sánh và trend | **Cần kiểm tra/bổ sung theo từng dataset** | Có thể dùng các chuỗi observation hiện hữu khi dimension, UOM và coverage tương thích; Onyx/Pharma Sales có grain riêng, location/SKU semantics bị giới hạn; missing period không chứng minh quantity zero | Chốt phép tổng hợp, calendar/coverage và điều kiện so sánh; không khái quát từ một dataset sang toàn bộ module |
| Forecast Sales Quantity | **Landscape scope; DSS capability chưa có evidence** | Source package chuẩn bị dữ liệu cho forecasting; README nói forecasting ngoài scope package; hiện không có forecast service/run contract được xác nhận trong phạm vi này | Chốt model/run contract, target/grain, cutoff/horizon, model version, actuals và nguồn output như điều kiện nội bộ; UI Supply Chain chỉ hiển thị số theo location/kỳ và đơn vị đã xác nhận |
| Prediction Quality | **Cần bổ sung model/evaluation contract; chưa là DSS capability** | Source pipeline không chứng minh temporal backtest, baseline, metric reporting hoặc UI đã chạy | Xác định protocol/horizon/baseline/metric và audit temporal leakage; chỉ nghiệm thu sau khi có run evidence |
| Lineage/provenance | **Có một phần trong source contract; UI chưa có evidence** | `pos.sales_observation.source`, dataset profile/manifest và tách fact aggregate khỏi synthetic POS hỗ trợ lineage nội bộ theo nguồn; không đồng nghĩa mọi metadata có sẵn ngay tại KPI output | Chốt metadata nội bộ để truy từ KPI/forecast về source/run; Người dùng được quyền xem Sales/Forecast nhận nhãn business và trạng thái dễ hiểu, không phải tự đọc metadata kỹ thuật |
| POS-like output từ dataset aggregate | **Chỉ dùng minh họa mô phỏng** | Package README ghi Onyx/Pharma Sales có POS-like/simulated orders; không được cộng cùng observation gốc như hai luồng observed sales | Gắn nhãn synthetic và dùng riêng cho demo/test; không dùng như chứng cứ bán hàng quan sát |
| Sales/forecast handoff sang Inventory decision | **Chưa đủ căn cứ đưa vào prototype scope; deferred** | Landscape nêu Inventory Insight/optimization nhưng chưa định nghĩa consumer, decision inputs, contract về inventory availability/expiry, hay outcome criteria cho handoff Sales | Xác nhận use case và owner liên miền; đối chiếu source inventory data; định nghĩa contract, decision-quality measures và human review boundary trước khi tạo story/FR |

Trước khi chốt requirements cần xác nhận: owner/team cho từng Sales KPI theo phạm vi cửa hàng/khu vực và từng Demand/forecast KPI; grain ưu tiên; KPI definition và UOM mapping; forecast horizon; actuals đủ coverage; protocol/baseline/model candidates; ngưỡng latency; cơ chế đăng nhập, enforcement scope ở DB/RLS, audit retention/implementation; mục tiêu accessibility; và contract nếu mở handoff sang Inventory. Danh sách role MD-01, permission, scope assignment và nguyên tắc audit đã theo tab 2. Protocol, model version, run ID và technical metric là quyết định cho kiểm định/truy vết nội bộ, không phải thông số Supply Chain phải xem. Requirement nào phụ thuộc quyết định chưa có được giữ trạng thái `TBD`, không biến thành giả định mặc định.

## 10. Nguồn

### Project sources

1. [Landscape PDF](../../docs/Landscape/PharmaFlow_Data_Business_Analytics_Landscape_KPI_Fixed.pdf), đặc biệt trang 5, 10–15.
2. [Landscape transcript](../../docs/Landscape/PharmaFlow_Landscape_Transcript_Revised.html).
3. [Domain/module map](../../docs/architecture/pharmaflow-domain-module-map.md).
4. [Source PostgreSQL v2 README](../../src/synthetic_data_source/pharmaflow_source_postgre/README.md) và `schema_full.sql` — dữ liệu source contract, không phải DSS feature evidence.
5. [Data-model / workflow contract](../../docs/data-model/Relations-DataSource/README.md) — một số nội dung đang có thay đổi chưa commit; cần re-review trước khi dùng thành quyết định schema.
6. [Chương 4 report skeleton](../../docs/reports/chapters/chapter04_tongquan_hethong.tex) — vị trí dự kiến tích hợp sau, không sửa trong đợt tạo requirements này.

### Industry role analogies

Các mô tả công việc công khai của Boehringer Ingelheim và Takeda được dùng để kiểm tra khả năng gộp/tách planning, commercial analytics và forecast review. Đây là benchmark về cách tổ chức, không phải bằng chứng chức danh hoặc trách nhiệm đã được PharmaFlow phê duyệt.

1. [Boehringer Ingelheim — AD, Demand Planning](https://jobs.boehringer-ingelheim.com/job/Johns-Creek%2C-GA-AD%2C-Demand-Planner-Unit/1448131133/).
2. [Takeda — Insights & Analytics Manager](https://jobs.takeda.com/job/toronto/insights-and-analytics-manager/1113/102539792240).
3. [Takeda — Senior Analyst, Commercial Analytics](https://jobs.takeda.com/job/bengaluru/senior-analyst-commercial-analytics/1113/102808132064).
4. [Takeda — Manager, Forecasting](https://jobs.takeda.com/job/bengaluru/manager-forecasting/1113/96526052064).

### Standards and methods

1. [ISO/IEC/IEEE 29148:2018](https://www.iso.org/standard/72089.html), bản International Standard đã công bố; ISO ghi nhận được xác nhận năm 2024 và bắt đầu quy trình sửa đổi năm 2026, bản DIS mới còn đang phát triển. Dùng ấn bản 2018 làm guidance cho requirements lifecycle/truy vết, không tuyên bố tuân thủ đầy đủ tiêu chuẩn.
2. [ISO/IEC 25010:2023](https://www.iso.org/standard/78176.html). Dùng để rà taxonomy chất lượng; không lấy thay cho workload/SLA của PharmaFlow.
3. [Forecasting: Principles and Practice, 3rd ed., §5.10](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation). Hỗ trợ rolling-origin đánh giá theo thời gian, không dùng residual/training fit thay forecast ngoài mẫu.
4. [OWASP ASVS 5.0.0](https://asvs.owasp.org/). Khung kiểm thử security khi auth boundary được xác định; control set cụ thể chưa được chốt.
5. [W3C WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/). Nguồn lựa chọn accessibility success criteria nếu có UI; mức nghiệm thu cần stakeholder xác nhận.
6. Các mẫu trong `docs/references/Report_Reference/` chỉ hỗ trợ tham khảo hình thức trình bày; nội dung nghiệp vụ, actor và ngưỡng từ đề tài mẫu không được chuyển thành yêu cầu PharmaFlow.

Ngày tra cứu nguồn Internet: 2026-11-05.

## Addendum — quyền MD-01 và điều chỉnh forecast (2026-11-07)

### Quyền người dùng

Tab chung “2. Người dùng & phân quyền” là nguồn chính sách. Quyền đọc MD-01 được cấp cho US-01, US-02, US-03 (Supply Chain Planner), US-04, US-06, US-07, US-11, US-12, US-14 và US-15 theo phạm vi role assignment. `sales:read` áp dụng UC-SD-01/02/03/06; `forecast:read` áp dụng UC-SD-04/06. Quyền đọc MD-01 không cấp quyền nghiệp vụ MD-02–05.

Planner (US-03) có thêm `forecast:adjust`; quyền này chỉ cho phép tạo một bản điều chỉnh của một giá trị forecast trong phạm vi được gán. Data Admin có quyền kỹ thuật `forecast_evaluation:read` và `forecast_evaluation:record`; IT Admin có `job:read` và `job_log:read`. Hai quyền quản trị kỹ thuật không cấp quyền xem màn hình nghiệp vụ hoặc `forecast:adjust`. Quyền admin cần được khai báo trong role policy của MD-01; đây không phải quyết định thay đổi tab chung.

Mọi request đọc/ghi phải qua `permission` → `data scope` → SoD liên quan → điều kiện trạng thái nếu có. Backend áp dụng scope lên danh sách, bộ lọc, truy vấn chi tiết, kết quả tổng hợp và technical reference trước khi trả kết quả. Location của dataset chỉ được nối với REGION/STORE/WAREHOUSE khi có mapping được xác nhận; không có mapping thì chỉ trả phần scope có thể chứng minh hoặc từ chối theo policy. Quyền được kiểm tra lại khi ghi. Audit lưu actor, permission, resource, kết quả và thời điểm; thay đổi dữ liệu có before/after. Các quy định này mô tả yêu cầu, không xác nhận implementation hay deployment.

### FR-SD-10 — Điều chỉnh một giá trị forecast

**Actor:** Supply Chain Planner. **Permission:** `forecast:adjust`; phải có `forecast:read` và scope phù hợp. **Input:** tham chiếu forecast gốc, location/kỳ và product/grain mà output hỗ trợ, giá trị mới, đơn vị cùng lý do.

Hệ thống kiểm tra reference và coordinate, quyền hiện hành, giá trị hữu hạn không âm, đơn vị và độ chính xác theo contract. Trước khi lưu, hiển thị forecast gốc, giá trị điều chỉnh, chênh lệch, đơn vị và lý do để Planner xác nhận. Khi lưu, tạo version riêng gắn actor/thời điểm/reference; không ghi đè forecast do model sinh, source facts hay score evaluation. Nếu reference, unit hoặc coordinate không đủ căn cứ, từ chối lưu và nêu trường thiếu. Nếu quyền bị thu hồi hoặc lưu thất bại, không tạo version; giữ nội dung nhập để người dùng xử lý lại. Nếu giá trị không đổi, không tạo version mới.

Mặc định màn hình tiếp tục chọn forecast gốc; người xem có quyền chọn rõ bản điều chỉnh để xem. Nhãn phải phân biệt “forecast do mô hình sinh” và “forecast đã điều chỉnh bởi người dùng”. Prediction Quality hiện tại chỉ đánh giá forecast gốc; đánh giá bản điều chỉnh cần protocol riêng. Không suy ra approval, publish hay execution từ thao tác lưu này.

| ID | Tiêu chí nghiệm thu bổ sung |
|---|---|
| `AC-SD-10-01` | Chỉ US-03 có `forecast:adjust`; mọi role khác bị từ chối ghi. |
| `AC-SD-10-02` | Scope được kiểm tra cho cả bản gốc và location/kỳ; không có mapping thì không mở rộng dữ liệu. |
| `AC-SD-10-03` | Mỗi lần lưu khác giá trị tạo version riêng với lý do, actor, thời điểm và reference; bản gốc không đổi. |
| `AC-SD-10-04` | Số âm, vô hạn, unit/precision không hợp lệ hoặc thiếu lý do/reference không được lưu. |
| `AC-SD-10-05` | UI phân biệt model forecast với adjusted forecast; mặc định vẫn là bản gốc. |
| `AC-SD-10-06` | Quyền bị thu hồi hoặc lỗi persistence không tạo version và không làm mất bản gốc. |
| `TC-SD-18` | Planner điều chỉnh một giá trị hợp lệ trong scope; đọc lại được version và audit. |
| `TC-SD-19` | Role chỉ đọc, out-of-scope, thiếu mapping hoặc reference lỗi; từ chối và không lộ dữ liệu. |
| `TC-SD-20` | Thử số âm/vô hạn/thiếu lý do/đơn vị sai/lưu lỗi; không tạo version. |
| `TC-SD-21` | Sau điều chỉnh, forecast gốc và score evaluation gốc không đổi; default hiển thị vẫn là forecast gốc. |

Auth mechanism, credential/MFA/session, audit retention/hash-chain implementation và kiểm soát cơ sở dữ liệu còn là quyết định triển khai; không được hiểu là đã có code.
