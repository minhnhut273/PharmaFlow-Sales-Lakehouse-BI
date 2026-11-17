# PharmaFlow — Sales & Demand: Software Specification

Tài liệu tổng hợp sáu đặc tả hiện hành của W19.10. Nội dung nguồn được giữ nguyên; chỉ cấp tiêu đề Markdown được dịch một bậc để tạo cấu trúc mục lục thống nhất. PDF chèn Org chart ngay sau User Stories, ảnh từng bộ diagram sau đặc tả tương ứng và Đấu thầu ở phụ lục cuối.

## Mục lục

- [1. Requirements](#spec-requirements)
- [2. User Stories](#spec-user_stories)
- [3. Use Case Specification](#spec-use_case)
- [4. Sequence Specification](#spec-sequence)
- [5. Activity Specification](#spec-activity)
- [6. State Specification](#spec-state)
- [Phụ lục A — Danh mục trang diagram](#appendix-diagrams)
- [Phụ lục B — Diagram tham chiếu](#appendix-references)

---

<a id="spec-requirements"></a>

## Requirements PharmaFlow — Sales & Demand (Landscape V1)

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | `PF-REQ-SALES-DEMAND-LANDSCAPE-V1` |
| Trạng thái | Bản nháp đề xuất; chưa được stakeholder xác nhận |
| Nguồn nhu cầu | [User Stories Sales & Demand Landscape V1](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md) |
| Phạm vi | Business Monitoring, Sales & Demand Insight, forecast Sales Quantity và Prediction Quality |
| Ngày lập | 2026-11-05 |
| Phân công actor đã xác nhận | Tab 2 cấp quyền đọc MD-01 cho US-01/02/03/04/06/07/11/12/14/15 theo scope assignment; US-03 là Supply Chain Planner và có thêm quyền điều chỉnh forecast. Data admin kiểm định forecast; IT admin vận hành hệ thống. Chi tiết nghiệp vụ vẫn là bản nháp. |

### 1. Mục đích và phạm vi

Đặc tả UR, FR, business/data rules và NFR phát sinh từ user needs được suy ra trực tiếp từ [Landscape](../../docs/Landscape/PharmaFlow_Data_Business_Analytics_Landscape_KPI_Fixed.pdf). Đây là yêu cầu cho nguyên mẫu PharmaFlow DSS; không mô tả POS, ERP, WMS hay hệ thống vận hành nhà thuốc.

Trong phạm vi: xem sales KPI theo chiều có bằng chứng; so sánh và phân tích lịch sử; xem số forecast Sales Quantity theo location/kỳ; đánh giá Prediction Quality nội bộ; hiển thị nhãn và trạng thái nghiệp vụ rõ ràng. Lineage, provenance và metadata run được lưu để truy vết nội bộ, không phải thông tin bắt buộc người dùng màn hình nghiệp vụ phải đọc.

Ngoài phạm vi: ghi hóa đơn; ghi nhận stock movement; cập nhật inventory balance; đổi trả/quality-control; nhận hàng/ASN; tính replenishment order; quyết định tender/bid; tự động transfer, procurement hoặc execution. Các miền này chỉ là nguồn/đích dữ liệu tương lai khi contract được xác định.

### 2. Quy ước và trạng thái evidence

| Nhãn | Ý nghĩa |
|---|---|
| **Landscape scope** | Nhu cầu/KPI được nêu trong Landscape |
| **Project constraint** | Ràng buộc đã có trong project invariant hoặc data contract |
| **Design proposal** | Yêu cầu chi tiết để hiện thực nguyên mẫu, cần stakeholder chấp nhận |
| **Data gate** | Chỉ áp dụng khi có source, grain, unit, provenance và coverage phù hợp |
| **Implementation evidence** | Phân biệt `Landscape scope`, `Modeled locally`, `Implemented locally`, `Verified deployed` |

`Landscape scope` không chứng minh có schema, code hoặc deployment. `SYNTHETIC` không được gọi là dữ liệu observed. `sim.*` là dữ liệu mô phỏng.

Mức ưu tiên trong tài liệu là đề xuất cho thảo luận: **Core** cho Monitoring/Insight, **Supporting** cho lineage/data quality, **Evaluation** cho kiểm định model. Chưa có MoSCoW được stakeholder phê duyệt.

### 3. Actors và user requirements

Tab chung “2. Người dùng & phân quyền” cấp quyền đọc MD-01 cho US-01, US-02, US-03, US-04, US-06, US-07, US-11, US-12, US-14 và US-15 trong scope assignment. Các luồng đọc dùng actor “Người dùng được quyền xem Sales/Forecast”; card Supply Chain trên org chart là đại diện nghiệp vụ, không giới hạn quyền đọc vào riêng chức danh này. US-03 là Supply Chain Planner, kế thừa quyền đọc và là role duy nhất có forecast:adjust. Data admin dùng quyền kỹ thuật để quản trị dữ liệu/kiểm định forecast; IT admin dùng quyền kỹ thuật để vận hành service/job/log. Hai quyền quản trị không tự cấp quyền nghiệp vụ MD-01. KPI Owner vẫn là accountability riêng: Store Manager là ứng viên cho Sales KPI cấp cửa hàng; Regional Manager cho Sales KPI nhiều cửa hàng; team Supply Chain Planning / Demand Management cho Demand/forecast KPI. Mapping owner từng KPI còn cần xác nhận. Xem căn cứ tại [User Stories §3](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md).

Mỗi UR theo khung actor → use case/user goal → nhu cầu người dùng → giá trị cho người dùng, có truy vết về user story và căn cứ. Tên bảng, thuật toán và cách kiểm thử được mô tả trong FR, business/data rules hoặc test scenarios.

#### UR-SD-08 — Điều chỉnh một giá trị forecast

**Actor:** Supply Chain Planner (US-03). **User goal:** điều chỉnh một giá trị Forecast Sales Quantity trong scope assignment, ghi lý do và lưu thành version riêng. **Giá trị:** có phương án nghiệp vụ truy vết được, phân biệt với model output mà không ghi đè forecast gốc hay score evaluation. **Truy vết:** US-SD-LS-08 → FR-SD-10.

### 4. Functional Requirements

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

#### FR-SD-01 — Theo dõi Sales Quantity

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

#### FR-SD-02 — So sánh Sales Quantity

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

#### FR-SD-03 — Xem xu hướng và biểu hiện mùa vụ

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

#### FR-SD-04 — Xem Forecast Sales Quantity

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

#### FR-SD-05 — Data admin đối soát dữ liệu và kiểm định forecast

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

#### FR-SD-06 — Hiển thị ngữ cảnh nghiệp vụ Sales/Forecast

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

#### FR-SD-09 — IT admin theo dõi vận hành hệ thống

- **Actor và mục đích:** IT admin theo dõi dịch vụ/job và xử lý sự cố vận hành trong phạm vi Sales & Demand.
- **Đầu vào:** trạng thái dịch vụ/job, lịch chạy, job/run ID, thời điểm bắt đầu/kết thúc và log theo contract hiện có.
- **Đầu ra:** thông tin vận hành theo job/run, trạng thái thành công/lỗi/chưa biết và chi tiết lỗi phù hợp quyền; credentials và sensitive values không xuất hiện trong log.
- **Luồng chính:** IT admin chọn dịch vụ/job hoặc run → xem trạng thái/lịch/log → ghi nhận vấn đề và hướng xử lý; chuyển vấn đề dữ liệu hoặc chất lượng forecast cho Data admin.
- **Quyền và ngoại lệ:** phân công vận hành đã xác nhận; quyền retry/restart/thay lịch và quy trình thực thi cần chốt riêng. Thiếu telemetry phải thể hiện chưa biết, không tự coi job thành công. Không mặc định IT admin được sửa dữ liệu hoặc kết luận kiểm định forecast.
- **Acceptance criteria:** `AC-SD-09-01` trạng thái và log truy được theo job/run ID khi contract cung cấp; `AC-SD-09-02` quyền truy cập được kiểm soát và log không lộ thông tin nhạy cảm; `AC-SD-09-03` lỗi vận hành và vấn đề dữ liệu/model có đầu mối xử lý rõ; `AC-SD-09-04` không thực hiện retry/restart/thay lịch khi chưa có quyền/quy trình được xác nhận.
- **Liên kết:** UR-SD-07; US-SD-LS-07; NFR-SD-07/09; TC-SD-14/16.

#### 4.1. Ánh xạ mã FR cũ

| Mã cũ | Xử lý khi viết lại | Truy vết mới |
|---|---|---|
| `FR-SD-01`–`FR-SD-06` | Giữ mã và đặc tả chi tiết theo cùng capability. | Các FR-SD-01–06 ở trên. |
| `FR-SD-07` | Không giữ như một capability độc lập; các quy tắc được đặt ở BR-SD-01–06, BR-SD-09 và acceptance criteria liên quan. | BR-SD-01–06/09; FR-SD-01–06. |
| `FR-SD-08` | Không giữ như một capability độc lập; các lỗi/điều kiện thiếu được đặt trong alternative/error flows của FR tương ứng. | FR-SD-01–05; TC-SD-02/03/07/09/13. |

Các mã FR-SD-07/08 đã phát hành không được tái sử dụng.

#### 4.2. Protocol đánh giá forecast được FR-SD-05 sử dụng

- Dùng rolling-origin/temporal backtesting; tại mỗi forecast origin, tập huấn luyện và feature chỉ chứa thông tin có trước origin đó.
- Model và baseline dùng cùng origins, target, series/grain, unit, horizon, actuals và evaluation period. Nếu một yếu tố khác nhau, kết quả không được trình bày như phép so sánh ngang hàng.
- Baseline đơn giản được báo cáo cạnh model. MAE, RMSE, WAPE và Bias là các metric ứng viên; stakeholder/model protocol phải chốt metric, định nghĩa, đơn vị và xử lý mẫu số trước khi dùng nghiệm thu.
- Lưu cutoff, origins, horizon, actuals reference, baseline/model version, protocol và metric definitions để tái lập evaluation.
- Prediction Quality được trình bày riêng với stockout/service/fill, average inventory, overstock, expiry/wastage và simulated total cost. Không kết luận chất lượng quyết định chỉ từ forecast error.
- Thiếu actuals, coverage, protocol hoặc baseline tương thích thì trạng thái là `not evaluable`/`invalid`, không sinh score thay thế.

### 5. Business và data rules

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

### 6. Non-functional Requirements

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

#### 6.1. Quyết định chất lượng còn chờ xác nhận

| Quyết định | Thông tin cần chốt | Trạng thái |
|---|---|---|
| Tải và hiệu năng | Dataset/series size, concurrency, thao tác đo, p95/throughput mục tiêu, thiết bị và môi trường. | TBD |
| Availability và reliability | Giờ vận hành, SLA/SLO và cách tính downtime/error rate. | TBD |
| Recovery/backup | Dữ liệu cần backup, retention, RPO/RTO và chủ thể chịu trách nhiệm. | TBD |
| Access/security | Cơ chế xác thực/credential/MFA/session, thực thi scope ở DB/RLS, retention và chi tiết triển khai audit. Role MD-01, scope assignment, SoD và audit fields đã có policy tại tab 2. | Policy đã xác định; chi tiết triển khai TBD |
| Usability/accessibility | Nhóm người dùng, thiết bị, tác vụ ưu tiên và mức WCAG nghiệm thu. | TBD |

### 7. Kịch bản nghiệm thu đề xuất

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

### 8. Ma trận truy vết

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

### 9. Hiện trạng và khoảng trống

| Evidence level | Trạng thái tại repo đã kiểm tra |
|---|---|
| Landscape scope | Sales KPI, Sales & Demand Insight, Forecast Sales Quantity, KPI lineage, semantics và cross-domain optimization được nêu trong Landscape |
| Modeled locally | Source PostgreSQL v2 có `pos.sales_observation` (source facts đã aggregate) cùng order/line contract; observations không phải POS orders. Package docs/schema phân biệt facts nguồn với record POS synthetic |
| Implemented locally | Package có code chuẩn bị, nạp và đối soát các source dataset. Đây là source-data pipeline evidence; không phải DSS forecast, analytics, inventory decision hay UI evidence |
| Verified deployed | Package README ghi source database v2 đã được nạp/đối soát cho các dataset được liệt kê. Không xác nhận deployment của chức năng Sales & Demand DSS hoặc forecast model/evaluation service |

#### 9.1. Data readiness và phân loại khả thi

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

### 10. Nguồn

#### Project sources

1. [Landscape PDF](../../docs/Landscape/PharmaFlow_Data_Business_Analytics_Landscape_KPI_Fixed.pdf), đặc biệt trang 5, 10–15.
2. [Landscape transcript](../../docs/Landscape/PharmaFlow_Landscape_Transcript_Revised.html).
3. [Domain/module map](../../docs/architecture/pharmaflow-domain-module-map.md).
4. [Source PostgreSQL v2 README](../../src/synthetic_data_source/pharmaflow_source_postgre/README.md) và `schema_full.sql` — dữ liệu source contract, không phải DSS feature evidence.
5. [Data-model / workflow contract](../../docs/data-model/Relations-DataSource/README.md) — một số nội dung đang có thay đổi chưa commit; cần re-review trước khi dùng thành quyết định schema.
6. [Chương 4 report skeleton](../../docs/reports/chapters/chapter04_tongquan_hethong.tex) — vị trí dự kiến tích hợp sau, không sửa trong đợt tạo requirements này.

#### Industry role analogies

Các mô tả công việc công khai của Boehringer Ingelheim và Takeda được dùng để kiểm tra khả năng gộp/tách planning, commercial analytics và forecast review. Đây là benchmark về cách tổ chức, không phải bằng chứng chức danh hoặc trách nhiệm đã được PharmaFlow phê duyệt.

1. [Boehringer Ingelheim — AD, Demand Planning](https://jobs.boehringer-ingelheim.com/job/Johns-Creek%2C-GA-AD%2C-Demand-Planner-Unit/1448131133/).
2. [Takeda — Insights & Analytics Manager](https://jobs.takeda.com/job/toronto/insights-and-analytics-manager/1113/102539792240).
3. [Takeda — Senior Analyst, Commercial Analytics](https://jobs.takeda.com/job/bengaluru/senior-analyst-commercial-analytics/1113/102808132064).
4. [Takeda — Manager, Forecasting](https://jobs.takeda.com/job/bengaluru/manager-forecasting/1113/96526052064).

#### Standards and methods

1. [ISO/IEC/IEEE 29148:2018](https://www.iso.org/standard/72089.html), bản International Standard đã công bố; ISO ghi nhận được xác nhận năm 2024 và bắt đầu quy trình sửa đổi năm 2026, bản DIS mới còn đang phát triển. Dùng ấn bản 2018 làm guidance cho requirements lifecycle/truy vết, không tuyên bố tuân thủ đầy đủ tiêu chuẩn.
2. [ISO/IEC 25010:2023](https://www.iso.org/standard/78176.html). Dùng để rà taxonomy chất lượng; không lấy thay cho workload/SLA của PharmaFlow.
3. [Forecasting: Principles and Practice, 3rd ed., §5.10](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation). Hỗ trợ rolling-origin đánh giá theo thời gian, không dùng residual/training fit thay forecast ngoài mẫu.
4. [OWASP ASVS 5.0.0](https://asvs.owasp.org/). Khung kiểm thử security khi auth boundary được xác định; control set cụ thể chưa được chốt.
5. [W3C WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/). Nguồn lựa chọn accessibility success criteria nếu có UI; mức nghiệm thu cần stakeholder xác nhận.
6. Các mẫu trong `docs/references/Report_Reference/` chỉ hỗ trợ tham khảo hình thức trình bày; nội dung nghiệp vụ, actor và ngưỡng từ đề tài mẫu không được chuyển thành yêu cầu PharmaFlow.

Ngày tra cứu nguồn Internet: 2026-11-05.

### Addendum — quyền MD-01 và điều chỉnh forecast (2026-11-07)

#### Quyền người dùng

Tab chung “2. Người dùng & phân quyền” là nguồn chính sách. Quyền đọc MD-01 được cấp cho US-01, US-02, US-03 (Supply Chain Planner), US-04, US-06, US-07, US-11, US-12, US-14 và US-15 theo phạm vi role assignment. `sales:read` áp dụng UC-SD-01/02/03/06; `forecast:read` áp dụng UC-SD-04/06. Quyền đọc MD-01 không cấp quyền nghiệp vụ MD-02–05.

Planner (US-03) có thêm `forecast:adjust`; quyền này chỉ cho phép tạo một bản điều chỉnh của một giá trị forecast trong phạm vi được gán. Data Admin có quyền kỹ thuật `forecast_evaluation:read` và `forecast_evaluation:record`; IT Admin có `job:read` và `job_log:read`. Hai quyền quản trị kỹ thuật không cấp quyền xem màn hình nghiệp vụ hoặc `forecast:adjust`. Quyền admin cần được khai báo trong role policy của MD-01; đây không phải quyết định thay đổi tab chung.

Mọi request đọc/ghi phải qua `permission` → `data scope` → SoD liên quan → điều kiện trạng thái nếu có. Backend áp dụng scope lên danh sách, bộ lọc, truy vấn chi tiết, kết quả tổng hợp và technical reference trước khi trả kết quả. Location của dataset chỉ được nối với REGION/STORE/WAREHOUSE khi có mapping được xác nhận; không có mapping thì chỉ trả phần scope có thể chứng minh hoặc từ chối theo policy. Quyền được kiểm tra lại khi ghi. Audit lưu actor, permission, resource, kết quả và thời điểm; thay đổi dữ liệu có before/after. Các quy định này mô tả yêu cầu, không xác nhận implementation hay deployment.

#### FR-SD-10 — Điều chỉnh một giá trị forecast

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
<a id="figures-requirements"></a>

---

<a id="spec-user_stories"></a>

## User Stories PharmaFlow — Sales & Demand (Landscape V1)

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | `PF-US-SALES-DEMAND-LANDSCAPE-V1` |
| Trạng thái | Bản nháp đặc tả từ Landscape; chưa được stakeholder xác nhận |
| Phạm vi | Sales & Demand trong PharmaFlow DSS; các giao điểm dữ liệu cần cho insight và forecast |
| Nguồn nghiệp vụ chính | PharmaFlow Data & Business Analytics Landscape KPI Fixed; Landscape Transcript Revised |
| Ngày lập | 2026-11-05 |

### 1. Mục đích và cách đọc

Tài liệu này chuyển nhu cầu Sales & Demand được thể hiện trong Landscape thành các mục tiêu người dùng có thể thảo luận, đặc tả và nghiệm thu. Số lượng story được xác định từ các mục tiêu, không dựa trên số story của tài liệu khác.

Mỗi story mang mã mới `US-SD-LS-*`. Các dấu căn cứ có nghĩa như sau:

- **Landscape scope** — mục tiêu hoặc KPI được nêu trực tiếp trong Landscape.
- **Project constraint** — ranh giới ngữ nghĩa hoặc đánh giá được quy định trong dự án.
- **Design proposal** — cách cung cấp khả năng cho nguyên mẫu; cần stakeholder xác nhận.
- **Data gate** — chỉ nghiệm thu khi dữ liệu nguồn có đủ grain, thời gian, đơn vị và provenance.

Trạng thái phạm vi nghiệp vụ không đồng nghĩa với trạng thái code. Hiện trạng schema, dữ liệu, mã và triển khai được đối chiếu riêng trong [Requirements Sales & Demand](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md).

### 2. Phạm vi Sales trong Landscape

Sales là lượng bán thực tế. Demand là nhu cầu cần đáp ứng và có thể không được quan sát đầy đủ. Landscape đặt monitoring KPI và sales quantity riêng với forecast, risk, opportunity và optimization.

| Business taxonomy | Category / SubCategory | Business Monitoring / Insight |
|---|---|---|
| Sales | Product Category → Product Group | Sales Quantity; Sales by Product |
| Sales | Sales Channel → Retail Store, Website, Mobile App | Sales by Location; Sales by Channel / Time |
| Sales & Demand Insight | Forecast Sales Quantity | High/low-performing product; seasonal pattern; trend theo product/location/channel khi dữ liệu hỗ trợ |

Các KPI dự báo ở cấp business không tự định nghĩa cách forecast, horizon, thuật toán hoặc metric nghiệm thu. Những lựa chọn đó được mô tả trong requirements với căn cứ hoặc trạng thái cần quyết định.

#### 2.1. Bảng phân tích nhu cầu nghiệp vụ

| Nhu cầu / căn cứ Landscape | Câu hỏi người dùng | Thông tin cần xem | Mục đích sử dụng | Giới hạn và cách xử lý trong bộ US |
|---|---|---|---|---|
| Theo dõi bán hàng — Sales KPI, tr.5, 11 | Đã bán bao nhiêu, trong kỳ nào, theo sản phẩm/nhóm, địa điểm và kênh nào? | Sales Quantity theo kỳ và các chiều thật sự có trong source | Nắm trạng thái bán hàng trong tập dữ liệu | US-SD-LS-01; giữ nguyên grain, unit và provenance nguồn; không tạo dimension thiếu |
| So sánh — Sales KPI và high/low-performing product, tr.5, 10 | Nhóm nào bán cao/thấp; sales thay đổi giữa kỳ hoặc nhóm ra sao? | Giá trị, chênh lệch/thứ hạng và tập đối tượng được so sánh | Nhận diện khác biệt cần phân tích | US-SD-LS-02; chỉ so sánh grain, UOM và coverage tương thích; thứ hạng không tự mang nghĩa tốt/xấu |
| Xu hướng/mùa vụ — Sales & Demand Insight, tr.5, 10 | Có trend hay seasonal pattern nào được dữ liệu hỗ trợ? | Chuỗi lịch sử và phạm vi thời gian/đối tượng | Hiểu pattern lịch sử để xem xét trong planning | US-SD-LS-03; không kết luận mùa vụ nếu thiếu coverage/chu kỳ; sales không đồng nghĩa demand |
| Dự báo — Forecast Sales Quantity, tr.5, 10, 12 | Forecast Sales Quantity là bao nhiêu theo từng location và kỳ, cho một hay nhiều cửa hàng/node? | Số forecast theo location và kỳ; tên location và đơn vị nếu có căn cứ | Tham khảo lượng bán dự kiến theo location trong planning | US-SD-LS-04; chỉ hiển thị location/kỳ được source và forecast hỗ trợ; không gộp location ngầm định; không mặc định forecast là latent demand |
| Kiểm định Prediction Quality — KPI/model quality, tr.11–12 | Forecast có được đánh giá nội bộ với actuals ngoài mẫu và baseline tương thích không? | Bằng chứng temporal backtest và metric được lưu trong hồ sơ kiểm định nội bộ | Đảm bảo chất lượng forecast được đánh giá tách khỏi chất lượng quyết định | US-SD-LS-05; đây là kiểm định nội bộ, không yêu cầu Supply Chain xem protocol hay metric kỹ thuật |
| Đọc đúng số liệu — KPI semantics, tr.11, 14 | Con số là Sales history hay Forecast Sales Quantity, thuộc location và kỳ nào? | Nhãn nghiệp vụ, location, kỳ forecast/lịch sử, đơn vị đã xác nhận và trạng thái dễ hiểu nếu chưa có số | Diễn giải đúng con số đang xem mà không cần đọc metadata kỹ thuật | US-SD-LS-06; lineage/provenance chi tiết vẫn được lưu nội bộ; không biến unknown thành zero hoặc tự suy diễn |
| Kết nối quyết định — Insight/Optimization và Inventory Insight, tr.10, 12 | Sales/forecast có thể cung cấp evidence gì để miền Inventory đánh giá stockout, excess hoặc replenishment? | Candidate handoff là Sales evidence/forecast reference có ngữ nghĩa và thời điểm rõ | Hỗ trợ trao đổi liên miền trước khi xây decision capability | **Hoãn khỏi US được nghiệm thu**: Landscape thể hiện capability liên miền nhưng chưa xác định consumer/decision contract, input Inventory đáng tin cậy hay acceptance outcome; nêu lại ở §5 và Requirements §9.1 |

### 3. Actor và đối chiếu org chart

Landscape yêu cầu mỗi KPI có owner ở cấp Department / Team / Role khi cơ cấu tổ chức được xác nhận, nhưng chưa chốt tên chức danh hay phân quyền người dùng. Đã đối chiếu với [pharmaflow_org_chart.drawio trên Drive](https://drive.google.com/file/d/1maGLTtuud9k01u6lnOm_EDjLhO4jWCSm/view?usp=sharing) và ảnh org chart toàn cảnh người dùng cung cấp. Trang `Trang-1` là sơ đồ tổ chức; `Page-2` mô tả workflow Tender nên không dùng làm bằng chứng cho actor Sales & Demand. Trong khối Vận hành thương mại & Kho vận, phòng `Supply Chain Planning / Demand Management` ghi nhiệm vụ `Ra quyết định thương mại` và có card `Supply Chain`; các nhánh Store Manager và Warehouse Manager lần lượt ghi `Kiểm tra thực tế` và `Thực thi & Kiểm soát vận hành`.

| Actor trong user stories | Bằng chứng trong org chart | Đối chiếu nghiệp vụ/ngành | Mức độ khớp và cách dùng |
|---|---|---|---|
| Người dùng được quyền xem Sales/Forecast | Card `Supply Chain` nằm dưới phòng `Supply Chain Planning / Demand Management`, có nhiệm vụ `Ra quyết định thương mại`. | MD-01 cấp R cho US-01, 02, 03, 04, 06, 07, 11, 12, 14, 15; Store Manager và Pharmacist được bao gồm cho thao tác đọc trong scope assignment. | **Dùng actor khái quát cho các story đọc.** Supply Chain là business representative; không giới hạn permission đọc vào riêng chức danh Supply Chain. Không yêu cầu người đọc xem model/protocol/run/lineage metadata. |
| `Store Manager` / `Pharmacist` | Org chart ghi `Kiểm tra thực tế` cho Store Manager; tab 2 ghi quyền R MD-01 cho US-06/US-07. | Tab 2 xác định quyền tính năng; assignment xác định data scope. | **Có thể dùng các chức năng đọc chung** với permission và scope tương ứng; không phát sinh thao tác kiểm tra, nhập hoặc xác nhận dữ liệu tại cửa hàng từ các story hiện tại. |
| `Warehouse Manager` | Org chart ghi `Thực thi & Kiểm soát vận hành`. | Vai trò này gắn với thực thi/kiểm soát nghiệp vụ kho. | **Chưa đưa vào actor hiện tại:** các story Sales & Demand không yêu cầu thao tác kho; handoff sang Inventory cũng đang deferred. Chỉ thêm khi phạm vi có use case kho hoặc handoff được định nghĩa. |
| Sales & Demand KPI Owner (trách nhiệm quản trị) | Landscape yêu cầu mỗi KPI có owner. Org chart có `Regional Manager`, `Store Manager`, và team Supply Chain Planning / Demand Management, nhưng chưa nối từng KPI với một owner cụ thể. | Ownership phụ thuộc domain và KPI scope/grain; không suy ra chỉ từ tên chức danh quản lý. | **Gán theo phạm vi KPI, không tạo actor/card mới:** `Store Manager` là ứng viên cho Sales KPI cấp cửa hàng; `Regional Manager` là ứng viên cho Sales KPI tổng hợp nhiều cửa hàng; team Supply Chain Planning / Demand Management là owner phù hợp để stakeholder xác nhận cho Demand/forecast KPIs. Chỉ đưa manager thành actor user story nếu họ trực tiếp dùng chức năng. |
| `Data admin` | Card có sẵn trong Khối Quản trị hệ thống; người dùng xác nhận kiêm kiểm định forecast ngày 2026-11-05. | Quản trị dữ liệu đầu vào, lineage/provenance và kiểm định Prediction Quality bằng actuals, baseline, temporal backtest. | **Phụ trách chất lượng dữ liệu và kiểm định forecast.** Đọc source/snapshot, đơn vị, location mapping, cutoff, model/protocol version và metric khi đối soát/kiểm định; lưu kết luận cùng bằng chứng. |
| `IT admin` | Card có sẵn trong Khối Quản trị hệ thống; người dùng xác nhận phụ trách vận hành ngày 2026-11-05. | Theo dõi dịch vụ, job, lịch chạy, trạng thái run, log lỗi và truy cập hệ thống. | **Phụ trách vận hành hệ thống.** Dùng run/job ID và log để xử lý sự cố; chuyển vấn đề chất lượng dữ liệu/model cho Data admin. Không mặc định chịu trách nhiệm kết luận chất lượng forecast. |

#### Bằng chứng ngành dùng làm đối chiếu

Các trang dưới đây là mô tả công việc của hãng dược, dùng để kiểm tra tên và phạm vi vai trò phổ biến; chúng không chứng minh các chức danh này đã tồn tại trong org chart của PharmaFlow.

- Boehringer Ingelheim `AD, Demand Planning`: một vai trò Demand Planning dẫn S&OP, analytics/reporting, review hiệu suất forecast và phối hợp Supply Chain, Marketing, Finance.
- Takeda `Insights & Analytics Manager`: một vai trò gộp commercial decision support, KPI/scorecard, sales performance analytics và demand forecasting.
- Takeda `Senior Analyst - Commercial Analytics`: một mô hình chuyên viên riêng về sales/channel data, brand KPIs, dashboards và insight.
- Takeda `Manager, Forecasting`: một mô hình chuyên trách chất lượng forecast, review model/assumptions/output và forecast accuracy.

**Phân công đã được người dùng xác nhận ngày 2026-11-05:** `Supply Chain` xem số forecast theo location/kỳ; `Data admin` quản trị dữ liệu và kiêm kiểm định forecast; `IT admin` vận hành hệ thống. Cả ba card đã có trong org chart. Các trách nhiệm này là quyết định phân công cho prototype, không phải bằng chứng chức năng đã triển khai. KPI Owner vẫn là accountability riêng: `Store Manager` là ứng viên cho Sales KPI cấp cửa hàng; `Regional Manager` cho Sales KPI nhiều cửa hàng; team Supply Chain Planning / Demand Management cho Demand/forecast KPI. Mapping owner theo từng KPI còn cần xác nhận. `Warehouse Manager` chưa được gán owner Sales & Demand; manager chỉ thành actor khi có thao tác sử dụng cụ thể.

Thẻ nhân sự trong sơ đồ có thông tin mẫu/không nhất quán (ví dụ email `me@example.com`, thẻ `Supply Chain` mang position `Brand Manager`), nên phép đối chiếu này chỉ dựa vào tên team, nhãn actor và nhiệm vụ hiển thị, không dựa vào tên cá nhân hoặc position trên các thẻ đó.

Không mặc định khách hàng, dược sĩ quầy, thủ kho hoặc người duyệt recommendation là người sử dụng trực tiếp module này.

### 4. User Stories

#### US-SD-LS-01 — Theo dõi Sales Quantity

**Căn cứ:** Landscape scope, trang 5 và 11.

**Là** Người dùng được quyền xem Sales/Forecast, **tôi muốn** theo dõi Sales Quantity trong một khoảng thời gian, **để** hiểu lượng bán theo product/group và các chiều location, channel, time có trong dữ liệu.

**Acceptance criteria**

- Người dùng có thể xem kỳ dữ liệu và đơn vị của Sales Quantity.
- Phân rã theo product/group, location, channel và time chỉ xuất hiện khi nguồn có chiều đó với ngữ nghĩa đã xác định.
- Location hiển thị theo nghĩa địa điểm bán/nhu cầu mà source xác nhận; nếu contract tách demand location và fulfillment location thì không dùng hai chiều thay thế nhau.
- Nguồn aggregate vẫn được trình bày ở grain aggregate; không được biến thành giao dịch từng hóa đơn hoặc số lượng từng SKU khi nguồn không cung cấp grain đó.
- Khi dimension, đơn vị hoặc coverage không có trong nguồn, giao diện ghi rõ chưa có/không xác định; không tạo category hay lượng zero để lấp chỗ trống.
- Sales Quantity được gắn nhãn theo evidence nguồn (publisher-reported, dataset observation, derived hoặc synthetic); provenance chưa xác nhận không được nâng thành actual sales đã kiểm chứng.

#### US-SD-LS-02 — So sánh Sales theo sản phẩm, địa điểm, kênh hoặc kỳ

**Căn cứ:** Landscape scope, trang 5, 11; thứ hạng high/low là nhu cầu Insight trên trang 10.

**Là** Người dùng được quyền xem Sales/Forecast, **tôi muốn** so sánh Sales Quantity giữa các product/group, location, channel hoặc kỳ, **để** nhận biết nhóm bán cao/thấp trong tập dữ liệu đang xem.

**Acceptance criteria**

- Kết quả nêu rõ kỳ, tập đối tượng, đơn vị và grain dùng để so sánh.
- Chỉ so sánh trực tiếp các chuỗi có measure và đơn vị tương thích; các grain không tương thích phải được giữ riêng hoặc có phép tổng hợp được định nghĩa.
- Thứ hạng mô tả kết quả trong tập được chọn; không tự gắn nhãn thành tốt/xấu về kinh doanh nếu chưa có ngưỡng hoặc mục tiêu được xác nhận.
- Khi coverage hoặc dữ liệu thiếu làm so sánh không công bằng, người dùng thấy cảnh báo và lý do.

#### US-SD-LS-03 — Xem xu hướng và biểu hiện mùa vụ

**Căn cứ:** Landscape scope, trang 5 và 10.

**Là** Người dùng được quyền xem Sales/Forecast, **tôi muốn** xem biến động Sales Quantity theo thời gian và các biểu hiện mùa vụ, **để** hiểu pattern lịch sử khi dữ liệu cho phép.

**Acceptance criteria**

- Mỗi biểu đồ hoặc nhận định cho biết measure, grain, kỳ dữ liệu và đối tượng được phân tích.
- Hệ thống phân biệt mô tả pattern lịch sử với kết luận mùa vụ đã được kiểm chứng.
- Nếu coverage thời gian, số chu kỳ hoặc chất lượng dữ liệu chưa đủ để đánh giá, kết quả ghi “chưa đủ dữ liệu” thay vì khẳng định có mùa vụ.
- Sales history không tự trở thành demand history; ảnh hưởng của stockout chỉ được diễn giải khi có evidence phù hợp.

#### US-SD-LS-04 — Xem Forecast Sales Quantity

**Căn cứ:** Landscape scope, trang 5, 10 và 12.

**Là** Người dùng được quyền xem Sales/Forecast, **tôi muốn** xem con số forecast Sales Quantity theo kỳ cho một hoặc nhiều location (cửa hàng hoặc node) được hỗ trợ, **để** tham khảo lượng bán dự kiến tại các location đó trong hoạt động lập kế hoạch.

**Acceptance criteria**

- Màn hình hiển thị số Forecast Sales Quantity theo từng location và kỳ forecast; người dùng có thể chọn một hoặc nhiều location được hỗ trợ.
- Khi chọn nhiều location, mỗi location có kết quả riêng; hệ thống không tự cộng các location thành một tổng.
- Location hiển thị theo tên/loại business mà source contract xác nhận, như cửa hàng hoặc node; không tự đổi demand location thành fulfillment location.
- Kết quả có nhãn nghiệp vụ `Forecast Sales Quantity`, kỳ forecast và đơn vị nếu đơn vị đã được xác nhận; không gọi forecast là latent demand.
- Sales history và forecast có nhãn riêng. Nếu kết quả demo/simulation dùng dữ liệu synthetic, giao diện dùng nhãn dễ hiểu như “dữ liệu mô phỏng”, không yêu cầu Người dùng được quyền xem Sales/Forecast đọc mã provenance.
- Model/version, protocol, cutoff nội bộ, run ID, grain kỹ thuật và lineage chi tiết được giữ trong metadata/hồ sơ nội bộ; không phải thông tin Người dùng được quyền xem Sales/Forecast cần xem để đọc con số forecast.
- Nếu location/kỳ được chọn không có forecast hợp lệ, giao diện nêu ngắn gọn “chưa có forecast cho location/kỳ này”, không tạo giá trị thay thế hoặc đưa lỗi kỹ thuật lên màn hình nghiệp vụ.

#### US-SD-LS-05 — Data admin kiểm định forecast

**Căn cứ:** Landscape scope, trang 5 và 11–12; project constraint về temporal backtesting và baseline.

**Là** Data admin, **tôi muốn** kiểm tra dữ liệu đầu vào và so sánh forecast với actuals ngoài mẫu cùng baseline, **để** kết luận Prediction Quality trên phạm vi đánh giá xác định và truy vết được kết quả.

**Phân công:** Data admin đọc hồ sơ dữ liệu/model/evaluation; Supply Chain nhận số forecast theo location/kỳ; IT admin xử lý trạng thái dịch vụ/job và sự cố vận hành.

**Điều kiện kiểm định nội bộ**

- Data admin kiểm tra nguồn/snapshot, đơn vị, location mapping, missing/duplicate và provenance; vấn đề dữ liệu được ghi nhận trước khi kết luận evaluation hợp lệ.
- Data admin xem cutoff, model/baseline/protocol version, actuals reference và metric definitions; kết luận kiểm định được lưu cùng run và bằng chứng, không sửa đè source facts hoặc score.
- Quy trình kiểm định nội bộ dùng rolling-origin/temporal backtesting; tại mỗi origin chỉ dùng thông tin có trước origin đó.
- Model và baseline được đánh giá trên actuals, target, grain, horizon và protocol tương thích; metric được ghi trong hồ sơ kỹ thuật nội bộ.
- MAE, RMSE, WAPE, Bias là metric ứng viên theo Landscape/project invariant; lựa chọn cuối cùng cần được xác định theo bài toán.
- Technical metric, protocol và cấu hình model không xuất hiện trong màn hình Supply Chain; user story này không yêu cầu Supply Chain tự so sánh model với baseline.
- Prediction Quality được lưu riêng với Decision Quality; forecast error không được xem là bằng chứng duy nhất về kết quả vận hành.
- Nếu actuals, coverage hoặc protocol chưa đủ, hồ sơ nội bộ đánh dấu chưa đánh giá được; không tự tạo score hay nhãn chất lượng cho Supply Chain.

#### US-SD-LS-06 — Đọc đúng ngữ cảnh của số liệu Sales/Forecast

**Căn cứ:** Landscape KPI lineage, trang 11; data semantics, trang 14; project constraints về observed/synthetic và sales/demand.

**Là** Người dùng được quyền xem Sales/Forecast, **tôi muốn** nhận biết con số đang xem là Sales history hay Forecast Sales Quantity, thuộc location và kỳ nào, **để** diễn giải đúng giá trị nghiệp vụ.

**Acceptance criteria**

- Màn hình nêu rõ loại số liệu bằng nhãn business dễ hiểu, ví dụ `Sales Quantity` hoặc `Forecast Sales Quantity`, cùng location, kỳ và đơn vị đã xác nhận.
- Location được trình bày theo nghĩa được source xác nhận; không trộn demand location với fulfillment location.
- Sales history, forecast và dữ liệu mô phỏng được phân biệt; không đổi sales thành demand hay làm dữ liệu thiếu thành zero.
- Khi không có giá trị cho location/kỳ, giao diện nêu trạng thái bằng ngôn ngữ nghiệp vụ, không yêu cầu Người dùng được quyền xem Sales/Forecast tự đọc source ID, grain kỹ thuật, provenance code hoặc run metadata.
- Lineage, source/run ID, provenance chi tiết và metadata kỹ thuật vẫn được lưu để truy vết nội bộ; chúng không phải trường bắt buộc trên màn hình Người dùng được quyền xem Sales/Forecast.

#### US-SD-LS-07 — IT admin theo dõi vận hành hệ thống

**Căn cứ:** Phân công người dùng ngày 2026-11-05; actor IT admin đã có trong Khối Quản trị hệ thống.

**Là** IT admin, **tôi muốn** theo dõi trạng thái dịch vụ và job, lịch chạy và log lỗi, **để** phát hiện sự cố và xác định bước xử lý vận hành.

**Acceptance criteria**

- Xem được trạng thái job/run, thời điểm bắt đầu/kết thúc và lỗi vận hành khi thông tin đó tồn tại trong contract; trạng thái chưa biết không được trình bày là thành công.
- Tra cứu log theo job/run ID theo quyền truy cập; log không chứa credentials hoặc sensitive values.
- Sự cố dữ liệu hoặc kết quả forecast bất thường được chuyển cho Data admin; IT admin không tự thay kết quả kiểm định model.
- Retry/restart hoặc thay lịch chỉ được thực hiện theo quyền và quy trình đã xác nhận; story này không mặc định cấp quyền thay đổi hay tự động chạy lại.

#### 4.1. Phạm vi dữ liệu, capability và điều kiện của từng story

| Story | Capability | Phạm vi dữ liệu và điều kiện sử dụng | Ngoại lệ / phụ thuộc | Trạng thái nhu cầu / hiện thực |
|---|---|---|---|---|
| US-SD-LS-01 | Business Monitoring | Sales observation theo source grain, kỳ, unit và dimension có contract | Nguồn không có location/channel/product detail thì không dựng chiều hoặc transaction giả; provenance chưa xác nhận phải hiện rõ | Đề xuất từ Landscape; khả năng từng dimension phụ thuộc dataset; không khẳng định có UI DSS |
| US-SD-LS-02 | Business Monitoring + Insight | So sánh product/group, location, channel hoặc time khi measure, UOM, grain và coverage tương thích | Không tương thích thì giữ riêng hoặc báo không so sánh được; cần định nghĩa aggregation nếu muốn tổng hợp | Đề xuất từ Landscape; cần source coverage và rule so sánh được xác nhận |
| US-SD-LS-03 | Business Insight | Chuỗi sales history đủ coverage theo đối tượng và thời gian | Thiếu chu kỳ/coverage thì không kết luận seasonal pattern; không suy lost demand khi thiếu stockout evidence | Đề xuất từ Landscape; điều kiện dữ liệu là gate |
| US-SD-LS-04 | Business Insight | Forecast Sales Quantity theo từng location và kỳ; người dùng chọn một hoặc nhiều cửa hàng/node được source/run hỗ trợ | Hiển thị từng location riêng, không tự cộng; không có kết quả thì báo ngắn gọn; model/run metadata giữ nội bộ | Nhu cầu có trong Landscape; DSS forecast hiện chưa được xác nhận là implemented/deployed |
| US-SD-LS-05 | Data admin: quản trị dữ liệu và kiểm định forecast | Source/snapshot, đơn vị, location mapping, provenance; actuals/baseline và temporal backtest tương thích | Data admin đọc metadata/metric và lưu kết luận; Supply Chain không phải đọc hồ sơ kỹ thuật | Phân công actor đã xác nhận; capability và protocol nghiệm thu còn Proposed, chưa xác nhận implemented/deployed |
| US-SD-LS-06 | Cross-cutting: Monitoring + Insight | Nhãn business, loại số liệu, location, kỳ, đơn vị đã xác nhận và trạng thái dễ hiểu | Lineage/provenance/source/run metadata giữ nội bộ; phân biệt Sales, forecast, synthetic và missing/zero | Đề xuất từ Landscape/project constraints; metadata nội bộ chỉ ghi khi contract có bằng chứng |
| US-SD-LS-07 | IT admin: vận hành hệ thống | Trạng thái dịch vụ/job, lịch chạy, run ID và log theo quyền | Thiếu telemetry phải ghi chưa biết; quyền retry/restart và quy trình xử lý cần chốt | Phân công actor đã xác nhận; chức năng vận hành chưa có evidence triển khai trong bộ tài liệu |

Không tạo story riêng cho thao tác hóa đơn, cập nhật kho hay recommendation execution. Nhu cầu handoff sang Inventory được ghi nhận ở bảng §2.1 nhưng hoãn khỏi scope nghiệm thu cho tới khi xác định consumer, data contract, decision purpose và outcome criteria.

### 5. Giao điểm và ranh giới module

Sales/forecast là input có thể được sử dụng ở Business Insight và các capability xuyên miền. Bản đặc tả Sales & Demand kết thúc ở việc cung cấp/giải thích sales evidence và forecast reference.

Landscape gợi ý Inventory Insight cho projected stockout/overstock và replenishment, nhưng bộ nguồn hiện chưa xác định phép chuyển Sales/forecast thành các kết luận đó, consumer cụ thể, contract với inventory state hay điều kiện nghiệm thu. Vì vậy, handoff này được ghi là **deferred need**, không bị bỏ quên và không biến thành story vận hành trong Sales.

- Inventory & Expiry sở hữu stock state, batch/expiry, stockout/excess risk và FEFO.
- Procurement & Supply sở hữu inbound PO, Goods Receipt, supplier và delivery performance.
- Distribution & Store Network sở hữu transfer, in-transit và network imbalance.
- Tender & Contract Fulfillment là outbound commitment path; Landscape scenario không phải observed tender data.
- Business Optimization tạo candidate action/scenario; Human Approval là review gate; approval không đồng nghĩa execution.

Các interface/API và business rules của các miền trên chưa được xác định bởi bộ US này.

### 6. Nguồn Landscape

1. [PharmaFlow Data & Business Analytics Landscape KPI Fixed](../../docs/Landscape/PharmaFlow_Data_Business_Analytics_Landscape_KPI_Fixed.pdf), trang 3–5, 10–15.
2. [PharmaFlow Landscape Transcript Revised](../../docs/Landscape/PharmaFlow_Landscape_Transcript_Revised.html).
3. [PharmaFlow Domain & Module Map](../../docs/architecture/pharmaflow-domain-module-map.md), dùng để diễn giải module boundary; không phải bằng chứng deployment.

#### Nguồn ngoài về vai trò ngành (analogy, không phải org evidence)

1. [Boehringer Ingelheim — AD, Demand Planning](https://jobs.boehringer-ingelheim.com/job/Johns-Creek%2C-GA-AD%2C-Demand-Planner-Unit/1448131133/).
2. [Takeda — Insights & Analytics Manager](https://jobs.takeda.com/job/toronto/insights-and-analytics-manager/1113/102539792240).
3. [Takeda — Senior Analyst, Commercial Analytics](https://jobs.takeda.com/job/bengaluru/senior-analyst-commercial-analytics/1113/102808132064).
4. [Takeda — Manager, Forecasting](https://jobs.takeda.com/job/bengaluru/manager-forecasting/1113/96526052064).

### 7. Trạng thái xác nhận

Các mục tiêu và KPI trong Landscape là căn cứ phạm vi. Người dùng đã xác nhận ngày 2026-11-05: Data admin quản trị dữ liệu và kiêm kiểm định forecast; IT admin vận hành hệ thống; Supply Chain đại diện nghiệp vụ xem kết quả. Tab 2 xác định mười role được cấp R tại MD-01, scope assignment, SoD và audit policy; chỉ US-03 có quyền điều chỉnh forecast. Story/capability vẫn là design proposal, chưa phải bằng chứng code hoặc deployment.

### Addendum — mapping quyền MD-01 (2026-11-07)

Quyền xem Sales/Forecast theo tab chung được áp dụng trong phạm vi role assignment cho US-01, US-02, US-03 Supply Chain Planner, US-04, US-06, US-07, US-11, US-12, US-14 và US-15. Đây là danh sách role được cấp R tại MD-01; mapping này không xác định KPI Owner. `Supply Chain` trong các story xem hiện tại là actor nghiệp vụ khái quát “Người dùng được quyền xem Sales/Forecast”, được cấp cụ thể cho các role trên. Planner có thêm `forecast:adjust`; Data Admin/IT Admin chỉ có quyền kỹ thuật theo nhiệm vụ đã xác nhận và không có quyền nghiệp vụ MD-01 mặc định.

#### US-SD-LS-08 — Điều chỉnh một giá trị forecast

**Là** Supply Chain Planner, **tôi muốn** điều chỉnh một giá trị forecast trong phạm vi được cấp và ghi lý do, **để** lưu một phương án nghiệp vụ có thể phân biệt và truy vết với output do model sinh.

**Acceptance criteria**

- Chỉ Planner có `forecast:adjust`; thao tác yêu cầu quyền xem, scope hợp lệ, forecast reference, location/kỳ, grain và đơn vị được xác nhận.
- Mỗi lần lưu một giá trị tạo version điều chỉnh riêng; lưu giá trị gốc, giá trị mới, lý do, actor, thời điểm và reference. Forecast gốc/source facts/score không bị ghi đè.
- Giá trị mới phải hữu hạn, không âm và theo precision trong unit contract. Thiếu căn cứ hoặc lý do thì không lưu.
- Forecast gốc là lựa chọn mặc định; người dùng chọn bản điều chỉnh tường minh. Nhãn model forecast và adjusted forecast khác nhau.
- Điều chỉnh không đồng nghĩa với approval, publish, execution hay thay đổi forecast run. Prediction Quality của model vẫn trỏ tới output gốc cho tới khi protocol riêng được xác định.
- Thu hồi quyền hoặc persistence failure không tạo version; nội dung nhập vẫn hiển thị để xử lý. Không tạo version nếu giá trị không đổi.
<a id="figures-user_stories"></a>

---

<a id="spec-use_case"></a>

## Đặc tả Use Case PharmaFlow — Sales & Demand (Landscape V1)

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | `PF-UC-SALES-DEMAND-LANDSCAPE-V1` |
| Trạng thái | Đặc tả đề xuất từ Landscape; cần stakeholder xác nhận trước khi khóa baseline |
| Phạm vi | Sales & Demand DSS: theo dõi Sales Quantity, xem forecast theo location/kỳ, kiểm định forecast nội bộ và theo dõi vận hành hệ thống |
| Ngày tạo | 2026-11-05 |
| Cập nhật lần cuối | 2026-11-07 |
| Người tạo / cập nhật | Chưa xác nhận |
| Sơ đồ đi kèm | [pharmaflow_sales_and_demand_usecase.drawio](pharmaflow_sales_and_demand_usecase.drawio) |
| Nguồn yêu cầu | [User Stories](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md); [Requirements](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md) |

### 1. Mục đích và quy ước

Tài liệu mô tả hành vi người dùng theo cấu trúc use case của tài liệu tham khảo: **Use-case name, Created by, Last updated by, Date created, Last updated date, Actor, Description, Pre-conditions, Post-conditions, Normal Flow, Alternative Flow**. Mỗi use case có thêm mã ổn định và truy vết về user story, user requirement, functional requirement.

- Luồng chính được đánh số liên tục. Luồng thay thế dùng hậu tố `a` và chỉ rõ bước phát sinh, ví dụ `3a`.
- “Sales Quantity” là lượng bán quan sát được; không tự đồng nhất với nhu cầu tiềm ẩn, tồn kho hay lượng mua.
- Forecast hiển thị riêng theo từng location và kỳ. Chọn nhiều location không đồng nghĩa với cộng thành tổng.
- Người dùng được quyền xem Sales/Forecast nhận nhãn nghiệp vụ, location, kỳ và đơn vị đã xác nhận. Metadata model, protocol, cutoff, run ID, grain kỹ thuật và lineage dành cho hồ sơ nội bộ, không phải thông tin cần đọc trên màn hình nghiệp vụ.
- Data admin đối soát dữ liệu và kiểm định **Prediction Quality**. **Decision Quality** và kết quả vận hành là lớp đánh giá riêng, không suy ra từ forecast error.
- IT admin theo dõi vận hành. Retry, restart và thay đổi lịch chỉ thực hiện khi quyền và quy trình được xác nhận.
- Các use case phản ánh đặc tả đề xuất; không phải bằng chứng chức năng đã được triển khai hay deploy.

#### Nguyên tắc thiết kế use case đã áp dụng

| Nguyên tắc | Cách áp dụng trong Sales & Demand |
|---|---|
| Bắt đầu từ mục tiêu của actor | Mỗi use case mô tả kết quả actor cần đạt; không biến màn hình, thuật toán, API hay từng bước nội bộ thành use case độc lập. |
| Đặt actor theo trách nhiệm nghiệp vụ | Supply Chain đọc kết quả nghiệp vụ; Data admin kiểm định dữ liệu và Prediction Quality; IT admin theo dõi dịch vụ/job/log. Metadata kỹ thuật không đưa vào trải nghiệm Supply Chain. |
| Giữ đúng ranh giới và ngữ nghĩa | Phân biệt Sales Quantity với nhu cầu, forecast với quyết định tồn kho, Prediction Quality với Decision Quality, và dữ liệu quan sát với dữ liệu mô phỏng. |
| Dùng `include` cho phần bắt buộc | Use case cơ sở gọi hành vi con mỗi lần hoàn tất mục tiêu; mũi tên đi từ use case cơ sở đến hành vi được bao gồm. |
| Dùng `extend` cho phần tùy chọn/có điều kiện | Use case mở rộng chỉ chạy tại extension point nêu rõ điều kiện; mũi tên đi từ use case mở rộng về use case cơ sở. |
| Chỉ tách use case con khi có hành vi đáng kiểm soát | Tách phần kiểm tra hoặc ghi nhận có kết quả riêng, tái sử dụng hoặc điều kiện rõ; không tách từng bước tuần tự thành một oval. |
| Giữ hai mức đọc của sơ đồ | 12 trang chi tiết tập trung vào từng UC chính và ngữ cảnh quan hệ cần thiết; trang 13 tổng hợp đủ 22 UC để xem actor và quan hệ ở mức toàn cảnh. |
| Duy trì truy vết | Mỗi UC được nối về User Story, User Requirement và Functional Requirement; UC phân rã kế thừa nguồn truy vết của hành vi cha. |

### 2. Actor

| Actor | Trách nhiệm trong phạm vi này | Quyền/ranh giới |
|---|---|---|
| `Người dùng được quyền xem Sales/Forecast` | Theo dõi/so sánh Sales Quantity; xem xu hướng, forecast theo location/kỳ và ngữ cảnh nghiệp vụ. | US-01, US-02, US-03 (Supply Chain Planner), US-04, US-06, US-07, US-11, US-12, US-14, US-15; chỉ trong scope assignment. Chỉ cần thông tin nghiệp vụ, không xem metadata kỹ thuật, phê duyệt hay thực thi hành động tồn kho. |
| `Supply Chain Planner (US-03)` | Dùng các UC đọc chung và điều chỉnh một giá trị forecast qua UC-SD-13. | Có `forecast:read` và `forecast:adjust` trong scope; không phê duyệt, publish hay thay đổi model output. |
| `Data admin` | Đối soát dữ liệu đầu vào; kiểm tra tính hợp lệ của evaluation; so sánh forecast với baseline khi đủ điều kiện; lưu kết luận và bằng chứng. | Đọc metadata kỹ thuật và hồ sơ dữ liệu/evaluation theo quyền được cấp. Không sửa đè source facts hoặc score gốc. |
| `IT admin` | Theo dõi trạng thái dịch vụ/job, lịch chạy và log; xác định sự cố vận hành, chuyển vấn đề dữ liệu/forecast cho Data admin. | Quyền retry/restart/thay đổi lịch và quyền truy cập chi tiết còn cần role matrix/quy trình xác nhận. Không kết luận chất lượng model thay Data admin. |

### 3. Danh mục và truy vết

| Mã use case | Use-case name | Actor chính | Truy vết |
|---|---|---|---|
| `UC-SD-01` | Theo dõi Sales Quantity | Người dùng được quyền xem Sales/Forecast | `US-SD-LS-01` / `UR-SD-01` / `FR-SD-01` |
| `UC-SD-02` | So sánh Sales Quantity | Người dùng được quyền xem Sales/Forecast | `US-SD-LS-02` / `UR-SD-02` / `FR-SD-02` |
| `UC-SD-03` | Xem xu hướng và biểu hiện mùa vụ | Người dùng được quyền xem Sales/Forecast | `US-SD-LS-03` / `UR-SD-03` / `FR-SD-03` |
| `UC-SD-04` | Xem forecast theo location và kỳ | Người dùng được quyền xem Sales/Forecast | `US-SD-LS-04` / `UR-SD-04` / `FR-SD-04` |
| `UC-SD-05` | Đối soát dữ liệu và kiểm định forecast | Data admin | `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-06` | Đọc ngữ cảnh nghiệp vụ Sales/Forecast | Người dùng được quyền xem Sales/Forecast | `US-SD-LS-06` / `UR-SD-06` / `FR-SD-06` |
| `UC-SD-07` | Theo dõi vận hành hệ thống | IT admin | `US-SD-LS-07` / `UR-SD-07` / `FR-SD-09` |
| `UC-SD-08` | Đối soát dữ liệu đầu vào | Data admin | Phân rã `UC-SD-05` / `FR-SD-05` |
| `UC-SD-09` | So sánh forecast với baseline | Data admin | Phân rã `UC-SD-05` / `FR-SD-05` |
| `UC-SD-10` | Ghi nhận kết luận kiểm định | Data admin | Phân rã `UC-SD-05` / `FR-SD-05` |
| `UC-SD-11` | Xem trạng thái dịch vụ/job và lịch chạy | IT admin | Phân rã `UC-SD-07` / `FR-SD-09` |
| `UC-SD-12` | Tra cứu log theo job/run | IT admin | Mở rộng có điều kiện `UC-SD-07` / `FR-SD-09` |
| `UC-SD-13` | Điều chỉnh một giá trị forecast | Supply Chain Planner (US-03) | `US-SD-LS-08` / `UR-SD-08` / `FR-SD-10` |
| `UC-SD-02.1` | Đối chiếu tính tương thích các chuỗi Sales | Người dùng được quyền xem Sales/Forecast (qua UC-SD-02) | Phân rã `US-SD-LS-02` / `UR-SD-02` / `FR-SD-02` |
| `UC-SD-03.1` | Xem biểu hiện mùa vụ | Người dùng được quyền xem Sales/Forecast (qua UC-SD-03) | Phân rã có điều kiện `US-SD-LS-03` / `UR-SD-03` / `FR-SD-03` |
| `UC-SD-08.1` | Đối chiếu nguồn và snapshot | Data admin (qua UC-SD-08) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-08.2` | Đối chiếu đơn vị và location mapping | Data admin (qua UC-SD-08) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-08.3` | Rà soát độ phủ, thiếu và trùng dữ liệu | Data admin (qua UC-SD-08) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-09.1` | Kiểm tra tính hợp lệ theo thời gian | Data admin (qua UC-SD-09) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-09.2` | Đối chiếu protocol forecast và baseline | Data admin (qua UC-SD-09) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-10.1` | Ghi căn cứ và tham chiếu kiểm định | Data admin (qua UC-SD-10) | Phân rã `US-SD-LS-05` / `UR-SD-05` / `FR-SD-05` |
| `UC-SD-11.1` | Xem trạng thái dịch vụ/job | IT admin (qua UC-SD-11) | Phân rã `US-SD-LS-07` / `UR-SD-07` / `FR-SD-09` |
| `UC-SD-11.2` | Xem lịch chạy và độ mới trạng thái | IT admin (qua UC-SD-11) | Phân rã `US-SD-LS-07` / `UR-SD-07` / `FR-SD-09` |

### 4. Đặc tả chi tiết

#### UC-SD-01 — Theo dõi Sales Quantity

| Trường | Nội dung |
|---|---|
| Use-case name | Theo dõi Sales Quantity |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast |
| Truy vết | `US-SD-LS-01`; `UR-SD-01`; `FR-SD-01` |

**Description:** Người dùng được quyền xem Sales/Forecast xem Sales Quantity theo kỳ và các chiều mà dữ liệu nguồn hỗ trợ để nắm trạng thái bán hàng trong phạm vi dữ liệu có căn cứ.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast được cấp quyền xem dữ liệu trong phạm vi được phê duyệt.
2. Có dữ liệu Sales cùng kỳ và trạng thái nguồn/provenance để trình bày.
3. Các chiều product/group, location, channel chỉ được chọn nếu source contract có hỗ trợ.

**Post-conditions**

- Kết quả được hiển thị theo grain, đơn vị, kỳ và provenance mà nguồn cung cấp.
- Không có source fact nào bị thay đổi bởi thao tác xem.

**Normal Flow**

1. Người dùng được quyền xem Sales/Forecast mở chức năng theo dõi Sales Quantity.
2. Người dùng được quyền xem Sales/Forecast chọn khoảng thời gian và các chiều khả dụng.
3. Hệ thống kiểm tra coverage, grain, đơn vị và trạng thái dữ liệu của phạm vi chọn.
4. Hệ thống hiển thị Sales Quantity cùng kỳ, đơn vị và các nhãn nghiệp vụ liên quan.
5. Người dùng được quyền xem Sales/Forecast xem kết quả theo phạm vi đã chọn.

**Alternative Flow**

- `2a`. Một chiều được chọn không có trong nguồn → hệ thống thông báo chiều đó không khả dụng và không dựng dữ liệu thay thế.
- `3a`. Không có bản ghi trong kỳ → hệ thống hiển thị trạng thái không có bản ghi, phân biệt với quantity bằng zero.
- `3b`. Provenance hoặc đơn vị chưa xác định → hệ thống đánh dấu chưa xác định/không khả dụng; không nâng dữ liệu thành actual đã kiểm chứng.
- `4a`. Lỗi tải dữ liệu → thông báo không thể tải kết quả; không hiển thị trạng thái lỗi như số liệu hợp lệ.

#### UC-SD-02 — So sánh Sales Quantity

| Trường | Nội dung |
|---|---|
| Use-case name | So sánh Sales Quantity |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast |
| Truy vết | `US-SD-LS-02`; `UR-SD-02`; `FR-SD-02` |

**Description:** Người dùng được quyền xem Sales/Forecast so sánh Sales Quantity giữa các đối tượng hoặc kỳ tương thích để nhận biết chênh lệch trong tập đang xem.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast có quyền xem các series được chọn.
2. Có ít nhất hai đối tượng hoặc kỳ để so sánh.
3. Measure và metadata cần thiết để đối chiếu đơn vị, grain và coverage có sẵn.

**Post-conditions**

- Kết quả nêu rõ tập so sánh, kỳ, đơn vị và grain.
- Không tạo thứ hạng cho những series không tương thích.

**Normal Flow**

1. Người dùng được quyền xem Sales/Forecast mở chức năng so sánh Sales Quantity.
2. Người dùng được quyền xem Sales/Forecast chọn các đối tượng và/hoặc kỳ cần so sánh.
3. Hệ thống kiểm tra measure, đơn vị, grain và coverage của từng series.
4. Hệ thống tính và hiển thị giá trị cùng chênh lệch hoặc thứ hạng trong tập đã chọn.
5. Người dùng được quyền xem Sales/Forecast xem kết quả và phạm vi so sánh.

**Alternative Flow**

- `2a`. Chỉ chọn một đối tượng/kỳ → hệ thống yêu cầu chọn thêm đối tượng/kỳ hoặc quay lại màn hình theo dõi.
- `3a`. Đơn vị, grain hoặc measure không tương thích → hệ thống nêu lý do; không so sánh trực tiếp hay xếp hạng các series đó.
- `3b`. Coverage thiếu hoặc khác nhau đáng kể → hệ thống cảnh báo giới hạn so sánh và không kết luận nhóm tốt/xấu.
- `4a`. Cần tổng hợp giữa grain nhưng chưa có rule được xác nhận → hệ thống giữ series riêng và không tự cộng.

#### UC-SD-03 — Xem xu hướng và biểu hiện mùa vụ

| Trường | Nội dung |
|---|---|
| Use-case name | Xem xu hướng và biểu hiện mùa vụ |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast |
| Truy vết | `US-SD-LS-03`; `UR-SD-03`; `FR-SD-03` |

**Description:** Người dùng được quyền xem Sales/Forecast xem lịch sử Sales Quantity và các biểu hiện xu hướng/mùa vụ có đủ coverage để hỗ trợ việc xem xét trong planning.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast được quyền xem series Sales đã chọn.
2. Có dữ liệu theo thời gian và thông tin về khoảng thời gian/coverage.

**Post-conditions**

- Chuỗi lịch sử và trạng thái đủ/thiếu bằng chứng được trình bày cùng phạm vi.
- Sales history không bị đổi nhãn thành demand history.

**Normal Flow**

1. Người dùng được quyền xem Sales/Forecast mở chức năng xu hướng và mùa vụ.
2. Người dùng được quyền xem Sales/Forecast chọn series, measure và khoảng thời gian.
3. Hệ thống kiểm tra tính liên tục của kỳ, coverage và số chu kỳ có thể quan sát.
4. Hệ thống hiển thị chuỗi Sales Quantity và xu hướng lịch sử.
5. Nếu điều kiện đánh giá mùa vụ phù hợp, hệ thống hiển thị biểu hiện mùa vụ cùng phạm vi bằng chứng.

**Alternative Flow**

- `3a`. Chuỗi quá ngắn, thiếu kỳ hoặc thiếu chu kỳ → hệ thống ghi “chưa đủ dữ liệu” và nêu phần coverage còn thiếu.
- `3b`. Provenance không rõ → hệ thống giữ cảnh báo nguồn; không trình bày nhận định như sự thật đã kiểm chứng.
- `5a`. Không có phương pháp/điều kiện đủ để kết luận mùa vụ → chỉ hiển thị lịch sử/mẫu hình quan sát được, không khẳng định có mùa vụ.

#### UC-SD-04 — Xem forecast theo location và kỳ

| Trường | Nội dung |
|---|---|
| Use-case name | Xem forecast theo location và kỳ |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast |
| Truy vết | `US-SD-LS-04`; `UR-SD-04`; `FR-SD-04` |

**Description:** Người dùng được quyền xem Sales/Forecast xem số Forecast Sales Quantity theo từng location và kỳ để tham khảo trong planning. Có thể chọn một hoặc nhiều location (ví dụ cửa hàng hoặc node) khi nguồn và forecast hỗ trợ.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast được quyền xem forecast trong phạm vi location được phê duyệt.
2. Có output forecast cho một phần hoặc toàn bộ location/kỳ được chọn.
3. Location, kỳ forecast và đơn vị được trình bày theo nghĩa mà source/run contract xác nhận.

**Post-conditions**

- Forecast được hiển thị riêng cho từng location và kỳ; nhiều location không bị cộng ngầm định.
- Màn hình chỉ có thông tin nghiệp vụ cần thiết; metadata kỹ thuật được giữ trong hồ sơ nội bộ.
- Không có model, dữ liệu nguồn hay quyết định vận hành nào bị thay đổi.

**Normal Flow**

1. Người dùng được quyền xem Sales/Forecast mở chức năng forecast Sales Quantity.
2. Người dùng được quyền xem Sales/Forecast chọn một hoặc nhiều location được hỗ trợ và kỳ forecast.
3. Hệ thống tìm output hợp lệ tương ứng với từng cặp location/kỳ.
4. Hệ thống hiển thị Forecast Sales Quantity riêng theo location và kỳ, kèm đơn vị đã xác nhận.
5. Người dùng được quyền xem Sales/Forecast đọc kết quả để tham khảo trong planning.

**Alternative Flow**

- `2a`. Location không được nguồn/run hỗ trợ → hệ thống nêu location không khả dụng; không đổi thành demand location hoặc fulfillment location khác.
- `3a`. Chưa có forecast hợp lệ cho một hay nhiều cặp location/kỳ → hiển thị “chưa có forecast cho location/kỳ này” cho đúng phần thiếu; không tạo zero hay giá trị thay thế.
- `3b`. Run nội bộ chưa hợp lệ/hoàn tất → không công bố forecast đó; chi tiết kỹ thuật ở hồ sơ nội bộ, thông báo trên màn hình vẫn dùng ngôn ngữ nghiệp vụ.
- `4a`. Đơn vị chưa được xác nhận → hiển thị rõ đơn vị chưa xác định hoặc ẩn đơn vị; không tự suy ra.
- `4b`. Kết quả là dữ liệu mô phỏng → gắn nhãn dễ hiểu “dữ liệu mô phỏng”; không yêu cầu Người dùng được quyền xem Sales/Forecast đọc mã provenance.

#### UC-SD-05 — Đối soát dữ liệu và kiểm định forecast

| Trường | Nội dung |
|---|---|
| Use-case name | Đối soát dữ liệu và kiểm định forecast |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin |
| Truy vết | `US-SD-LS-05`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin đối soát dữ liệu nguồn và hồ sơ evaluation, kiểm định Prediction Quality bằng temporal backtesting và baseline tương thích, rồi lưu kết luận có thể truy vết. Đây là công việc nội bộ; Supply Chain chỉ xem kết quả nghiệp vụ.

**Pre-conditions**

1. Data admin có quyền truy cập snapshot/dataset và hồ sơ evaluation tương ứng.
2. Có quy ước dữ liệu, metric và protocol cần thiết để kiểm tra; phần nào chưa được xác nhận phải được đánh dấu.
3. Forecast, actuals, baseline và protocol có thể được xác định theo target, grain, horizon và evaluation origins.

**Post-conditions**

- Kết quả kiểm tra dữ liệu và trạng thái evaluation được ghi nhận.
- Kết luận được gắn actor, thời điểm và tham chiếu bằng chứng/run; source facts và score gốc không bị ghi đè.
- Prediction Quality được lưu tách với Decision Quality; không suy chất lượng quyết định hay outcome từ forecast error.

**Normal Flow**

1. Data admin mở hồ sơ dữ liệu/evaluation cần kiểm định.
2. Hệ thống hiển thị snapshot, provenance, location mapping, đơn vị và các trường kỹ thuật có trong contract.
3. Data admin thực hiện đối soát dữ liệu đầu vào theo `UC-SD-08`.
4. Nếu dữ liệu và protocol đủ điều kiện, Data admin kiểm tra temporal validity và so sánh forecast với baseline theo `UC-SD-09`.
5. Hệ thống hiển thị metric, phạm vi đánh giá và khác biệt cần lưu ý theo protocol.
6. Data admin ghi kết luận kiểm định cùng bằng chứng theo `UC-SD-10`.
7. Hệ thống lưu bản ghi kết luận, actor, thời điểm và tham chiếu hồ sơ liên quan.

**Alternative Flow**

- `2a`. Một trường metadata không có trong contract → hệ thống đánh dấu chưa có/chưa xác định; không tự điền giá trị.
- `3a`. Phát hiện lỗi dữ liệu ảnh hưởng evaluation → Data admin ghi nhận lỗi; evaluation chuyển sang không hợp lệ hoặc chưa đánh giá được theo bằng chứng, không tiếp tục diễn giải score như hợp lệ.
- `4a`. Actuals, baseline, origins, horizon, target hoặc protocol không tương thích → kết quả được đánh dấu không so sánh được/chưa đánh giá được.
- `4b`. Có dấu hiệu temporal leakage hoặc run chưa hoàn tất → không kết luận Prediction Quality; lưu trạng thái và bằng chứng kiểm tra.
- `5a`. Chưa đủ coverage để tính metric → không tạo score thay thế và không gán nhãn tốt/xấu.
- `7a`. Không lưu được kết luận → thông báo chưa lưu; giữ nguyên source facts và kết quả evaluation gốc.
- `7b`. Sự cố dịch vụ/job cản trở việc truy cập → ghi nhận mã hồ sơ có sẵn và chuyển IT admin xử lý vận hành; Data admin không tự thực hiện quyền IT chưa được xác nhận.

#### UC-SD-06 — Đọc ngữ cảnh nghiệp vụ Sales/Forecast

| Trường | Nội dung |
|---|---|
| Use-case name | Đọc ngữ cảnh nghiệp vụ Sales/Forecast |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast |
| Truy vết | `US-SD-LS-06`; `UR-SD-06`; `FR-SD-06` |

**Description:** Khi xem kết quả Sales hoặc forecast, Người dùng được quyền xem Sales/Forecast nhận biết loại số liệu, location, kỳ và đơn vị đã xác nhận qua nhãn nghiệp vụ, không cần đọc lineage hay metadata kỹ thuật.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast đang xem kết quả Sales hoặc forecast.
2. Ngữ cảnh nghiệp vụ nào được source/run contract xác nhận thì có thể trình bày.

**Post-conditions**

- Kết quả mang nhãn Sales history hoặc Forecast Sales Quantity và ngữ cảnh khả dụng.
- Thiếu giá trị, quantity bằng zero và dữ liệu mô phỏng được phân biệt.

**Normal Flow**

1. Người dùng được quyền xem Sales/Forecast mở một kết quả Sales hoặc forecast.
2. Hệ thống xác định nhãn loại số liệu, location, kỳ, đơn vị và trạng thái có căn cứ.
3. Hệ thống hiển thị giá trị với các nhãn nghiệp vụ phù hợp.
4. Người dùng được quyền xem Sales/Forecast diễn giải kết quả trong đúng phạm vi được trình bày.

**Alternative Flow**

- `2a`. Thiếu location, kỳ hoặc đơn vị → hệ thống chỉ hiển thị phần đã xác nhận và diễn đạt phần thiếu là chưa có/chưa xác định.
- `2b`. Không có giá trị → hệ thống thông báo không có dữ liệu/forecast; không trình bày thành zero.
- `3a`. Output synthetic → gắn nhãn dữ liệu mô phỏng.
- `3b`. Lineage hoặc technical metadata không đầy đủ → giữ trạng thái thiếu trong hồ sơ nội bộ; không yêu cầu Người dùng được quyền xem Sales/Forecast tra cứu mã kỹ thuật.

#### UC-SD-07 — Theo dõi vận hành hệ thống

| Trường | Nội dung |
|---|---|
| Use-case name | Theo dõi vận hành hệ thống |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | IT admin |
| Truy vết | `US-SD-LS-07`; `UR-SD-07`; `FR-SD-09` |

**Description:** IT admin theo dõi trạng thái dịch vụ/job và lịch chạy để phát hiện, phân loại sự cố vận hành. Khi cần, IT admin tra cứu log theo `UC-SD-12` và chuyển vấn đề dữ liệu/forecast cho Data admin.

**Pre-conditions**

1. IT admin được cấp quyền xem thông tin vận hành theo role matrix áp dụng.
2. Trạng thái dịch vụ/job, lịch chạy và telemetry có sẵn theo contract của hệ thống.

**Post-conditions**

- Tình trạng quan sát được được ghi nhận với trạng thái thành công/lỗi/chưa biết phù hợp evidence.
- Vấn đề dữ liệu/model được chuyển cho Data admin; quyền retry/restart/thay lịch không được mặc định cấp.

**Normal Flow**

1. IT admin mở chức năng theo dõi vận hành Sales & Demand.
2. IT admin chọn dịch vụ, job hoặc khoảng lịch cần kiểm tra.
3. Hệ thống hiển thị trạng thái vận hành, lịch và thời điểm liên quan theo quyền.
4. IT admin đánh giá trạng thái và ghi nhận vấn đề vận hành nếu có.
5. Nếu cần xem log chi tiết của job/run, IT admin kích hoạt phần mở rộng `UC-SD-12`.
6. IT admin chuyển vấn đề dữ liệu hoặc bất thường chất lượng forecast cho Data admin.

**Alternative Flow**

- `2a`. Không có job trong phạm vi/kỳ chọn → hệ thống thông báo không tìm thấy job phù hợp.
- `3a`. Telemetry thiếu hoặc không mới → trạng thái được hiển thị là chưa biết/không cập nhật; không suy thành thành công.
- `4a`. Sự cố là lỗi dữ liệu hoặc kết quả forecast bất thường → IT admin chuyển Data admin kiểm tra; không tự sửa source facts hay kết luận model.
- `4b`. Cần retry/restart/thay lịch nhưng quyền/quy trình chưa xác nhận → chỉ ghi nhận nhu cầu; không thực thi thao tác.

#### UC-SD-08 — Đối soát dữ liệu đầu vào

| Trường | Nội dung |
|---|---|
| Use-case name | Đối soát dữ liệu đầu vào |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia như một phần bắt buộc của `UC-SD-05`) |
| Truy vết | Phân rã `US-SD-LS-05`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin kiểm tra dữ liệu và metadata liên quan trước khi đánh giá forecast, gồm source/snapshot, provenance, đơn vị, location mapping, missing/duplicate và tính đầy đủ theo contract.

**Pre-conditions**

1. Data admin được phép đọc snapshot và contract tương ứng.
2. Có thể nhận diện dataset/run cần đối soát.

**Post-conditions**

- Các kiểm tra, sai lệch và trường chưa xác định được ghi nhận để làm đầu vào cho `UC-SD-05`.
- Source fact không bị sửa đè trong use case này.

**Normal Flow**

1. Data admin chọn snapshot/dataset gắn với lần kiểm định.
2. Hệ thống hiển thị thông tin nguồn và metadata có trong contract.
3. Data admin kiểm tra đơn vị, location mapping, khoảng thời gian, missing/duplicate và provenance.
4. Hệ thống tổng hợp kết quả đối soát theo từng hạng mục.
5. Data admin xác nhận kết quả đối soát để quyết định điều kiện tiếp tục evaluation.

**Alternative Flow**

- `2a`. Snapshot/contract không tìm thấy → ghi nhận thiếu nguồn/contract; dừng đánh giá phụ thuộc thông tin đó.
- `3a`. Có mapping hoặc đơn vị không xác định → đánh dấu chưa xác định; không tự quy đổi hoặc ghép location.
- `3b`. Phát hiện duplicate/missing hoặc coverage sai lệch → ghi rõ phạm vi và mức ảnh hưởng; chưa kết luận evaluation hợp lệ.
- `5a`. Dữ liệu không đạt điều kiện → kết quả `invalid` hoặc `not assessable` được chuyển về `UC-SD-05` để ghi kết luận; không tự loại bỏ hay sửa bản ghi nguồn.

#### UC-SD-09 — So sánh forecast với baseline

| Trường | Nội dung |
|---|---|
| Use-case name | So sánh forecast với baseline |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia như một phần của `UC-SD-05`) |
| Truy vết | Phân rã `US-SD-LS-05`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin kiểm tra và đọc kết quả temporal backtest của forecast so với baseline tương thích trên cùng phạm vi evaluation để đánh giá Prediction Quality.

**Pre-conditions**

1. Đối soát dữ liệu tại `UC-SD-08` không chặn evaluation.
2. Forecast, baseline, actuals, target, grain, horizon, origins và protocol có đủ tham chiếu để kiểm tra tính tương thích.
3. Quy tắc metric áp dụng có định nghĩa; metric chưa được stakeholder chốt phải được ghi là lựa chọn/chờ xác nhận.

**Post-conditions**

- Metric và phạm vi so sánh được gắn với evaluation protocol tương ứng.
- Prediction Quality được lưu riêng; không suy ra Decision Quality hay operational outcome.

**Normal Flow**

1. Data admin mở kết quả evaluation đã qua kiểm tra dữ liệu.
2. Hệ thống hiển thị cutoff/origins, horizon, target, actuals reference, model/baseline/protocol version và metric definitions theo contract.
3. Data admin kiểm tra temporal validity, bảo đảm mỗi origin chỉ dùng thông tin có trước origin đó.
4. Hệ thống kiểm tra model và baseline dùng cùng actuals, target, grain, horizon, origins và protocol.
5. Hệ thống trình bày metric forecast cùng phạm vi và trạng thái so sánh.
6. Data admin xem xét kết quả Prediction Quality để ghi nhận trong `UC-SD-10`.

**Alternative Flow**

- `2a`. Metadata/version cần thiết thiếu → đánh dấu evaluation chưa đủ căn cứ; không suy diễn cấu hình.
- `3a`. Phát hiện temporal leakage → đánh dấu run không hợp lệ cho kết luận chất lượng.
- `4a`. Baseline không cùng phạm vi/actuals/protocol → không so sánh trực tiếp; ghi rõ nguyên nhân.
- `4b`. Run chưa hoàn tất hoặc actuals chưa đủ coverage → trạng thái chưa đánh giá được; không tự tạo score.
- `5a`. Metric chưa được chốt hoặc không xác định được do dữ liệu → trình bày trạng thái/căn cứ, không xếp hạng model tốt/xấu.

#### UC-SD-10 — Ghi nhận kết luận kiểm định

| Trường | Nội dung |
|---|---|
| Use-case name | Ghi nhận kết luận kiểm định |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia như một phần của `UC-SD-05`) |
| Truy vết | Phân rã `US-SD-LS-05`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin lưu kết quả đối soát và kết luận kiểm định forecast cùng người thực hiện, thời điểm, phạm vi và bằng chứng có thể truy vết.

**Pre-conditions**

1. Data admin đã thực hiện hoặc ghi rõ trạng thái các kiểm tra liên quan tại `UC-SD-08` và `UC-SD-09`.
2. Có thể nhận diện hồ sơ/run và bằng chứng tương ứng; kết luận có thể là hợp lệ, không hợp lệ hoặc chưa đánh giá được theo bằng chứng.

**Post-conditions**

- Một bản ghi kết luận gắn với actor, thời điểm, phạm vi, trạng thái và tham chiếu evidence được lưu nếu thao tác thành công.
- Source facts, actuals và score gốc không bị sửa.

**Normal Flow**

1. Data admin mở biểu mẫu kết luận cho evaluation.
2. Hệ thống hiển thị kết quả đối soát, metric, phạm vi protocol và các bằng chứng liên quan.
3. Data admin chọn trạng thái kết luận và nhập nhận xét/căn cứ.
4. Data admin gắn tham chiếu snapshot, run và bằng chứng hiện có.
5. Hệ thống kiểm tra các trường cần thiết, gắn actor và thời điểm lưu.
6. Hệ thống lưu kết luận và xác nhận hoàn tất.

**Alternative Flow**

- `2a`. Evaluation không đủ điều kiện → Data admin chọn `chưa đánh giá được` hoặc `không hợp lệ` và nêu lý do thay vì ghi score thay thế.
- `4a`. Thiếu evidence reference → hệ thống nhắc ghi rõ bằng chứng còn thiếu; kết luận không được thể hiện như đã truy vết đầy đủ.
- `5a`. Thiếu trạng thái hoặc căn cứ bắt buộc → hệ thống yêu cầu bổ sung và không lưu bản ghi hoàn chỉnh.
- `6a`. Lưu thất bại → giữ dữ liệu nguồn và score nguyên vẹn, báo chưa lưu để Data admin xử lý lại theo quyền/quy trình.

#### UC-SD-11 — Xem trạng thái dịch vụ/job và lịch chạy

| Trường | Nội dung |
|---|---|
| Use-case name | Xem trạng thái dịch vụ/job và lịch chạy |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | IT admin (tham gia như một phần bắt buộc của `UC-SD-07`) |
| Truy vết | Phân rã `US-SD-LS-07`; `UR-SD-07`; `FR-SD-09` |

**Description:** IT admin xem tình trạng dịch vụ/job và lịch chạy trong phạm vi được cấp quyền để xác định job thành công, lỗi, đang chạy hay chưa xác định.

**Pre-conditions**

1. IT admin có quyền xem thông tin vận hành liên quan.
2. Hệ thống có telemetry/lịch chạy hoặc xác định rõ dữ liệu đó chưa được cung cấp.

**Post-conditions**

- Trạng thái và thời điểm được trình bày theo telemetry hiện có.
- Không có job nào bị khởi động lại hoặc thay đổi lịch chỉ bởi thao tác xem.

**Normal Flow**

1. IT admin mở màn hình vận hành.
2. IT admin chọn dịch vụ/job hoặc khoảng lịch cần xem.
3. Hệ thống tra cứu trạng thái, thời điểm bắt đầu/kết thúc và lịch chạy hiện có.
4. Hệ thống hiển thị trạng thái cùng dấu thời gian/độ mới nếu có.
5. IT admin xác định job cần theo dõi sâu hơn hoặc ghi nhận tình trạng hiện tại.

**Alternative Flow**

- `2a`. Không có job phù hợp → hệ thống báo không tìm thấy job trong phạm vi đã chọn.
- `3a`. Không có telemetry → hiển thị chưa biết/chưa có telemetry, không coi là thành công.
- `4a`. Trạng thái quá cũ hoặc lịch không cập nhật → hiển thị thời điểm cập nhật cuối và cảnh báo dữ liệu cũ.
- `5a`. IT admin cần log chi tiết → tiếp tục bằng `UC-SD-12` khi có job/run để tra cứu.

#### UC-SD-12 — Tra cứu log theo job/run

| Trường | Nội dung |
|---|---|
| Use-case name | Tra cứu log theo job/run |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | IT admin; mở rộng có điều kiện từ `UC-SD-07` |
| Truy vết | Phân rã `US-SD-LS-07`; `UR-SD-07`; `FR-SD-09` |

**Description:** Khi cần chẩn đoán một dịch vụ/job/run cụ thể, IT admin tra cứu log được phép xem để nhận diện sự cố vận hành và chuyển vấn đề đúng đầu mối.

**Pre-conditions**

1. IT admin đang theo dõi vận hành tại `UC-SD-07` và có job/run cần tra cứu.
2. IT admin có quyền đọc log tương ứng; log đã được lưu và lập chỉ mục theo contract.

**Post-conditions**

- Log phù hợp được hiển thị hoặc hệ thống nêu rõ không có log/không đủ quyền.
- Credentials và sensitive values không được lộ; log không thay đổi trạng thái job.

**Normal Flow**

1. Tại điểm mở rộng “Xem chi tiết job/run” của `UC-SD-07`, IT admin yêu cầu tra cứu log.
2. IT admin chọn hoặc xác nhận job/run ID cần xem.
3. Hệ thống kiểm tra quyền và tra cứu log liên quan theo thời gian/phạm vi có sẵn.
4. Hệ thống che thông tin nhạy cảm theo chính sách rồi hiển thị kết quả.
5. IT admin phân loại vấn đề vận hành; nếu có dấu hiệu lỗi dữ liệu/model thì chuyển Data admin.

**Alternative Flow**

- `2a`. Thiếu hoặc sai job/run ID → yêu cầu chọn lại từ danh sách job/run khả dụng.
- `3a`. Không có log hoặc telemetry tương ứng → báo không có dữ liệu log; không tự kết luận job thành công.
- `3b`. Không đủ quyền → từ chối truy cập và ghi nhận kết quả kiểm tra quyền theo chính sách.
- `4a`. Phát hiện credentials/sensitive values trong nguồn log → không hiển thị giá trị nhạy cảm; ghi nhận sự cố theo quy trình bảo mật.
- `5a`. Log gợi ý lỗi dữ liệu hoặc chất lượng forecast → chuyển Data admin; IT admin không tự sửa dữ liệu/kết luận evaluation.

#### UC-SD-02.1 — Đối chiếu tính tương thích các chuỗi Sales

| Trường | Nội dung |
|---|---|
| Use-case name | Đối chiếu tính tương thích các chuỗi Sales |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast (tham gia thông qua `UC-SD-02`) |
| Truy vết | Phân rã bước 3–4 của `UC-SD-02`; `UR-SD-02`; `FR-SD-02` |

**Description:** Hệ thống xác định các chuỗi Sales được chọn có measure, đơn vị, grain và coverage đủ tương thích để so sánh hay không.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast đã chọn các chuỗi/kỳ trong `UC-SD-02`.
2. Metadata cần thiết có trong contract hoặc được đánh dấu chưa xác định.

**Post-conditions**

- Trạng thái tương thích và lý do được trả về `UC-SD-02`.
- Chuỗi không tương thích không bị xếp hạng hoặc gộp ngầm định.

**Normal Flow**

1. Hệ thống nhận tập chuỗi, measure và kỳ từ `UC-SD-02`.
2. Hệ thống kiểm tra measure, đơn vị, grain và coverage theo contract.
3. Hệ thống xác định tập có thể so sánh trực tiếp và điểm không tương thích.
4. Hệ thống trả kết quả cùng phạm vi/lý do về `UC-SD-02`.

**Alternative Flow**

- `2a`. Thiếu metadata → đánh dấu chưa xác định; không tự quy đổi đơn vị hoặc grain.
- `3a`. Có chuỗi không tương thích → loại khỏi so sánh trực tiếp và nêu lý do.

#### UC-SD-03.1 — Xem biểu hiện mùa vụ

| Trường | Nội dung |
|---|---|
| Use-case name | Xem biểu hiện mùa vụ |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Người dùng được quyền xem Sales/Forecast (tham gia thông qua `UC-SD-03`) |
| Truy vết | Mở rộng có điều kiện tại `UC-SD-03`; `UR-SD-03`; `FR-SD-03` |

**Description:** Hệ thống bổ sung nhận định mùa vụ khi coverage, số chu kỳ và phương pháp được xác nhận đủ căn cứ.

**Pre-conditions**

1. Người dùng được quyền xem Sales/Forecast đang xem xu hướng trong `UC-SD-03`.
2. Dữ liệu đáp ứng điều kiện coverage và chu kỳ theo phương pháp đã xác nhận.

**Post-conditions**

- Biểu hiện mùa vụ được trình bày kèm phạm vi thời gian và căn cứ.
- Nếu không đủ điều kiện, `UC-SD-03` vẫn hiển thị chuỗi/xu hướng lịch sử mà không kết luận mùa vụ.

**Normal Flow**

1. Hệ thống nhận series, measure và khoảng thời gian từ `UC-SD-03`.
2. Hệ thống kiểm tra điều kiện coverage và phương pháp.
3. Hệ thống hiển thị biểu hiện mùa vụ cùng chu kỳ làm căn cứ.
4. Hệ thống trả nội dung bổ sung về `UC-SD-03`.

**Alternative Flow**

- `2a`. Thiếu chu kỳ, missing period hoặc provenance chưa rõ → không kết luận mùa vụ và nêu phạm vi thiếu.
- `2b`. Phương pháp chưa được xác nhận → chỉ hiển thị lịch sử.

#### UC-SD-08.1 — Đối chiếu nguồn và snapshot

| Trường | Nội dung |
|---|---|
| Use-case name | Đối chiếu nguồn và snapshot |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-08` và `UC-SD-05`) |
| Truy vết | Phân rã bước 1–2 của `UC-SD-08`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin xác định snapshot/dataset có nguồn và contract phù hợp để diễn giải evaluation hay không.

**Pre-conditions**

1. Data admin đã mở hồ sơ cần kiểm định.
2. Có tham chiếu snapshot/dataset cần đối chiếu.

**Post-conditions**

- Nguồn, snapshot và contract được liên kết hoặc trạng thái thiếu được ghi nhận.
- Evaluation phụ thuộc nguồn thiếu không được đánh dấu hợp lệ.

**Normal Flow**

1. Hệ thống nhận tham chiếu snapshot/dataset từ `UC-SD-08`.
2. Data admin kiểm tra nguồn và contract gắn với snapshot.
3. Hệ thống ghi nhận phiên bản snapshot và trạng thái tham chiếu.
4. Hệ thống trả kết quả cho `UC-SD-08`.

**Alternative Flow**

- `2a`. Không tìm thấy snapshot/contract → ghi nhận thiếu căn cứ và dừng phần đánh giá phụ thuộc.
- `3a`. Không xác định được phiên bản → đánh dấu chưa truy vết đầy đủ; không suy đoán nguồn.

#### UC-SD-08.2 — Đối chiếu đơn vị và location mapping

| Trường | Nội dung |
|---|---|
| Use-case name | Đối chiếu đơn vị và location mapping |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-08` và `UC-SD-05`) |
| Truy vết | Phân rã bước 3 của `UC-SD-08`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin đối chiếu đơn vị và mapping location với contract, giữ nguyên khác biệt chưa được xác nhận.

**Pre-conditions**

1. Nguồn/snapshot đã được nhận diện hoặc trạng thái thiếu đã ghi nhận.
2. Contract có định nghĩa đơn vị/location mapping tương ứng, nếu định nghĩa tồn tại.

**Post-conditions**

- Đơn vị và mapping được đánh dấu phù hợp, không phù hợp hoặc chưa xác định.
- Không có phép đổi đơn vị hay ghép location tự suy diễn.

**Normal Flow**

1. Hệ thống hiển thị đơn vị/location trong snapshot cùng contract liên quan.
2. Data admin đối chiếu với định nghĩa có căn cứ.
3. Hệ thống ghi kết quả theo từng đơn vị/location.
4. Hệ thống trả kết quả cho `UC-SD-08`.

**Alternative Flow**

- `1a`. Thiếu định nghĩa trong contract → đánh dấu chưa xác định.
- `2a`. Mapping/đơn vị không khớp → ghi chênh lệch; không tự sửa source fact.

#### UC-SD-08.3 — Rà soát độ phủ, thiếu và trùng dữ liệu

| Trường | Nội dung |
|---|---|
| Use-case name | Rà soát độ phủ, thiếu và trùng dữ liệu |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-08` và `UC-SD-05`) |
| Truy vết | Phân rã bước 3–4 của `UC-SD-08`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin kiểm tra độ phủ theo contract và ghi nhận bản ghi thiếu/trùng hoặc kỳ/location chưa được đại diện.

**Pre-conditions**

1. Phạm vi snapshot/dataset được nhận diện.
2. Contract định nghĩa grain/phạm vi mong đợi để đánh giá coverage.

**Post-conditions**

- Coverage và sai lệch missing/duplicate được ghi cùng phạm vi ảnh hưởng.
- Trạng thái không đạt/chưa đánh giá được được trả về `UC-SD-08`.

**Normal Flow**

1. Hệ thống nhận grain, kỳ và phạm vi mong đợi theo contract.
2. Hệ thống đối chiếu dữ liệu với phạm vi đó.
3. Hệ thống tổng hợp coverage, missing và duplicate theo hạng mục.
4. Data admin xác nhận và trả kết quả cho `UC-SD-08`.

**Alternative Flow**

- `1a`. Contract không xác định phạm vi mong đợi → đánh dấu chưa đánh giá được.
- `2a`. Phát hiện sai lệch → ghi phạm vi và mức ảnh hưởng; không tự loại/sửa bản ghi nguồn.

#### UC-SD-09.1 — Kiểm tra tính hợp lệ theo thời gian

| Trường | Nội dung |
|---|---|
| Use-case name | Kiểm tra tính hợp lệ theo thời gian |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-09` và `UC-SD-05`) |
| Truy vết | Phân rã bước 2–3 của `UC-SD-09`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin kiểm tra cutoff, origins, horizon và actuals reference để xác định thông tin tương lai có lọt vào evaluation hay không.

**Pre-conditions**

1. Dữ liệu/protocol đủ điều kiện mở rộng `UC-SD-05`.
2. Metadata thời gian cần thiết có trong evaluation contract.

**Post-conditions**

- Temporal validity và căn cứ được trả về `UC-SD-09`.
- Run có temporal leakage không được dùng để kết luận Prediction Quality hợp lệ.

**Normal Flow**

1. Hệ thống hiển thị cutoff/origins, horizon và actuals reference.
2. Data admin kiểm tra mỗi origin chỉ dùng thông tin có trước origin đó.
3. Hệ thống ghi nhận trạng thái và vấn đề cần xem xét.
4. Hệ thống trả kết quả cho `UC-SD-09`.

**Alternative Flow**

- `1a`. Thiếu metadata cần thiết → đánh dấu chưa đủ căn cứ.
- `2a`. Phát hiện temporal leakage → đánh dấu run không hợp lệ cho kết luận chất lượng.

#### UC-SD-09.2 — Đối chiếu protocol forecast và baseline

| Trường | Nội dung |
|---|---|
| Use-case name | Đối chiếu protocol forecast và baseline |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-09` và `UC-SD-05`) |
| Truy vết | Phân rã bước 2 và 4 của `UC-SD-09`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin xác nhận forecast và baseline có cùng actuals, target, grain, horizon, origins và protocol trước khi đọc so sánh metric.

**Pre-conditions**

1. Dữ liệu/protocol đủ điều kiện vào `UC-SD-09`.
2. Có tham chiếu forecast, baseline và actuals cần đối chiếu.

**Post-conditions**

- Trạng thái tương thích hoặc lý do không tương thích được trả về `UC-SD-09`.
- Metric khác phạm vi không bị trình bày như so sánh trực tiếp.

**Normal Flow**

1. Hệ thống hiển thị target, grain, horizon, origins, actuals và protocol của forecast/baseline.
2. Data admin đối chiếu các trường cần tương thích.
3. Hệ thống trả phạm vi so sánh và định nghĩa metric cho `UC-SD-09`.

**Alternative Flow**

- `1a`. Thiếu metadata/version → đánh dấu chưa đủ căn cứ; không suy diễn cấu hình.
- `2a`. Trường so sánh không khớp → không so sánh trực tiếp và ghi nguyên nhân.

#### UC-SD-10.1 — Ghi căn cứ và tham chiếu kiểm định

| Trường | Nội dung |
|---|---|
| Use-case name | Ghi căn cứ và tham chiếu kiểm định |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | Data admin (tham gia thông qua `UC-SD-10` và `UC-SD-05`) |
| Truy vết | Phân rã bước 2–4 của `UC-SD-10`; `UR-SD-05`; `FR-SD-05` |

**Description:** Data admin gắn căn cứ/reference snapshot, run và evidence cho kết luận; bằng chứng còn thiếu được ghi rõ.

**Pre-conditions**

1. Data admin đã mở kết luận cần ghi trong `UC-SD-10`.
2. Kết quả đối soát/evaluation và evidence reference hiện có được cung cấp.

**Post-conditions**

- Kết luận lưu tham chiếu đang có và trạng thái bằng chứng còn thiếu.
- Hệ thống không tạo evidence reference hoặc sửa dữ liệu nguồn/score.

**Normal Flow**

1. Hệ thống hiển thị kết quả và reference hiện có.
2. Data admin gắn snapshot, run và bằng chứng liên quan.
3. Hệ thống ghi trạng thái đầy đủ/chưa đầy đủ của evidence.
4. Hệ thống trả kết quả cho `UC-SD-10` để lưu kết luận.

**Alternative Flow**

- `1a`. Không có evidence reference → ghi rõ bằng chứng thiếu và trạng thái phù hợp.
- `2a`. Reference không hợp lệ → yêu cầu xác nhận lại; không biểu thị đã truy vết đầy đủ.

#### UC-SD-11.1 — Xem trạng thái dịch vụ/job

| Trường | Nội dung |
|---|---|
| Use-case name | Xem trạng thái dịch vụ/job |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | IT admin (tham gia thông qua `UC-SD-11` và `UC-SD-07`) |
| Truy vết | Phân rã bước 2–4 của `UC-SD-11`; `UR-SD-07`; `FR-SD-09` |

**Description:** IT admin xem trạng thái dịch vụ/job và timestamp telemetry để nhận biết đang chạy, hoàn tất, lỗi hay chưa có căn cứ.

**Pre-conditions**

1. IT admin có quyền xem phạm vi vận hành tương ứng.
2. Dịch vụ/job được nhận diện hoặc truy vấn xác định không có dữ liệu.

**Post-conditions**

- Trạng thái và thời điểm cập nhật cuối được trả về `UC-SD-11`.
- Thao tác xem không khởi động lại job hoặc thay đổi trạng thái nguồn.

**Normal Flow**

1. Hệ thống nhận dịch vụ/job cần kiểm tra từ `UC-SD-11`.
2. Hệ thống đọc telemetry trạng thái và timestamp có sẵn.
3. Hệ thống trình bày trạng thái cùng thời điểm cập nhật.
4. Hệ thống trả kết quả để IT admin theo dõi vận hành.

**Alternative Flow**

- `2a`. Không có telemetry → hiển thị chưa biết/chưa có telemetry, không coi là thành công.
- `3a`. Trạng thái cũ → hiển thị độ cũ và cảnh báo bằng ngôn ngữ vận hành.

#### UC-SD-11.2 — Xem lịch chạy và độ mới trạng thái

| Trường | Nội dung |
|---|---|
| Use-case name | Xem lịch chạy và độ mới trạng thái |
| Created by | Chưa xác nhận |
| Last updated by | Chưa xác nhận |
| Date created | 2026-11-05 |
| Last updated date | 2026-11-05 |
| Actor | IT admin (tham gia thông qua `UC-SD-11` và `UC-SD-07`) |
| Truy vết | Phân rã bước 2–4 của `UC-SD-11`; `UR-SD-07`; `FR-SD-09` |

**Description:** IT admin xem lịch chạy và thời điểm cập nhật telemetry để xác định lịch/trạng thái có cũ so với thông tin hiện có hay không.

**Pre-conditions**

1. IT admin có quyền xem lịch vận hành tương ứng.
2. Có lịch/telemetry hoặc hệ thống có thể xác định dữ liệu chưa được cung cấp.

**Post-conditions**

- Lịch chạy và độ mới được trình bày theo nguồn hiện có.
- Thao tác xem không thay đổi lịch chạy hay quyền vận hành.

**Normal Flow**

1. Hệ thống nhận dịch vụ/job hoặc khoảng lịch từ `UC-SD-11`.
2. Hệ thống tra cứu lịch và timestamp liên quan.
3. Hệ thống hiển thị lịch cùng trạng thái mới/cũ theo timestamp.
4. Hệ thống trả kết quả để IT admin đánh giá vận hành.

**Alternative Flow**

- `2a`. Không có lịch/telemetry → nêu rõ dữ liệu vận hành chưa được cung cấp.
- `3a`. Lịch/trạng thái quá cũ → hiển thị timestamp cuối và cảnh báo; không tự thay lịch.

### 5. Quan hệ giữa các use case trên sơ đồ

| Quan hệ | Hướng trên sơ đồ | Căn cứ và điều kiện |
|---|---|---|
| Association | `Người dùng được quyền xem Sales/Forecast` — `UC-SD-01` đến `UC-SD-04` | Các role được cấp MD-01 xem Sales, so sánh, trend và forecast. `UC-SD-06` là hành vi ngữ cảnh được bao gồm, không phải mục tiêu actor khởi chạy độc lập. |
| Association | `Data admin` — `UC-SD-05` | Data admin khởi tạo mục tiêu tổng thể đối soát và kiểm định forecast. UC-08/10 là phần bắt buộc; UC-09 chỉ mở rộng khi dữ liệu và protocol đủ điều kiện. |
| Association | `IT admin` — `UC-SD-07` | IT admin khởi tạo mục tiêu theo dõi vận hành hệ thống. UC-11/12 biểu diễn hành vi thành phần của mục tiêu này. |
| `<<include>>` | `UC-SD-01`, `UC-SD-02`, `UC-SD-03`, `UC-SD-04` → `UC-SD-06` | Mỗi kết quả nghiệp vụ cần ngữ cảnh phù hợp (loại số liệu, location/kỳ, đơn vị/trạng thái có căn cứ) để người dùng diễn giải đúng. Mũi tên đi từ use case cơ sở tới UC được bao gồm. |
| `<<include>>` | `UC-SD-02` → `UC-SD-02.1` | So sánh cần xác định measure, đơn vị, grain và coverage tương thích trước khi trình bày chênh lệch/thứ hạng. |
| `<<extend>>` | `UC-SD-03.1` → `UC-SD-03` | Chỉ bổ sung nhận định mùa vụ khi coverage/phương pháp đủ căn cứ; extension point “Bổ sung thông tin mùa vụ”. |
| `<<include>>` | `UC-SD-05` → `UC-SD-08`, `UC-SD-10` | Kiểm định luôn ghi nhận kết quả đối soát và kết luận; kết luận có thể là invalid/not assessable khi điều kiện không đạt. |
| `<<include>>` | `UC-SD-08` → `UC-SD-08.1`, `UC-SD-08.2`, `UC-SD-08.3` | Đối soát có căn cứ cần nhận diện nguồn/snapshot, đơn vị/mapping và coverage/missing/duplicate theo contract. |
| `<<extend>>` | `UC-SD-09` → `UC-SD-05` | Chỉ đánh giá Prediction Quality khi dữ liệu/protocol đủ điều kiện, tại extension point “Đánh giá Prediction Quality”; UC-SD-05 vẫn hoàn chỉnh khi không so sánh được. |
| `<<include>>` | `UC-SD-09` → `UC-SD-09.1`, `UC-SD-09.2` | Đánh giá yêu cầu kiểm tra temporal validity và tính tương thích forecast/baseline trước khi đọc metric. |
| `<<include>>` | `UC-SD-10` → `UC-SD-10.1` | Kết luận cần ghi căn cứ/reference và thể hiện rõ evidence còn thiếu. |
| `<<include>>` | `UC-SD-07` → `UC-SD-11`; `UC-SD-11` → `UC-SD-11.1`, `UC-SD-11.2` | Theo dõi vận hành cần xem trạng thái dịch vụ/job, lịch chạy và độ mới telemetry trong phạm vi được cấp quyền. |
| `<<extend>>` | `UC-SD-12` → `UC-SD-07` | Tra cứu log chỉ xảy ra khi IT admin yêu cầu xem chi tiết job/run tại extension point cùng tên; mục tiêu theo dõi vận hành vẫn hoàn chỉnh khi không mở log. |

Association là đường liền không mũi tên. `<<include>>` là đường nét đứt có mũi tên từ use case cơ sở đến use case được bao gồm. `<<extend>>` là đường nét đứt từ use case mở rộng đến use case cơ sở. Chỉ dùng các quan hệ liệt kê trong bảng; không suy thêm actor, đăng nhập, retry hoặc thao tác quản trị ngoài phạm vi.

### 6. Ma trận truy vết UC → US/UR/FR

| Use case | User story | User requirement | Functional requirement |
|---|---|---|---|
| `UC-SD-01` | `US-SD-LS-01` | `UR-SD-01` | `FR-SD-01` |
| `UC-SD-02` | `US-SD-LS-02` | `UR-SD-02` | `FR-SD-02` |
| `UC-SD-03` | `US-SD-LS-03` | `UR-SD-03` | `FR-SD-03` |
| `UC-SD-04` | `US-SD-LS-04` | `UR-SD-04` | `FR-SD-04` |
| `UC-SD-05` | `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-06` | `US-SD-LS-06` | `UR-SD-06` | `FR-SD-06` |
| `UC-SD-07` | `US-SD-LS-07` | `UR-SD-07` | `FR-SD-09` |
| `UC-SD-08` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-09` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-10` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-11` | Phân rã `US-SD-LS-07` | `UR-SD-07` | `FR-SD-09` |
| `UC-SD-12` | Phân rã `US-SD-LS-07` | `UR-SD-07` | `FR-SD-09` |
| `UC-SD-13` | `US-SD-LS-08` | `UR-SD-08` | `FR-SD-10` |
| `UC-SD-02.1` | Phân rã `US-SD-LS-02` | `UR-SD-02` | `FR-SD-02` |
| `UC-SD-03.1` | Phân rã `US-SD-LS-03` | `UR-SD-03` | `FR-SD-03` |
| `UC-SD-08.1` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-08.2` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-08.3` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-09.1` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-09.2` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-10.1` | Phân rã `US-SD-LS-05` | `UR-SD-05` | `FR-SD-05` |
| `UC-SD-11.1` | Phân rã `US-SD-LS-07` | `UR-SD-07` | `FR-SD-09` |
| `UC-SD-11.2` | Phân rã `US-SD-LS-07` | `UR-SD-07` | `FR-SD-09` |

`FR-SD-07` và `FR-SD-08` đã được retire trong Requirements; không tái sử dụng. `UC-SD-07` là mã Use Case độc lập và ánh xạ tới `FR-SD-09`.

### 7. Nguồn và giới hạn evidence

1. `OneNigth_report03.pdf`, mục 4 “Đặc tả Use case”, mẫu metadata và Actor/Description, trang in 22–25; mẫu luồng chính/thay thế, trang in 30–31. Tham khảo cấu trúc trình bày; không sao chép nghiệp vụ SSO/Tutor.
2. [User Stories Sales & Demand Landscape V1](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md), đặc biệt US-SD-LS-01–07 và phân công actor.
3. [Requirements Sales & Demand Landscape V1](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md), đặc biệt UR-SD-01–07, FR-SD-01–06/09, protocol evaluation và các giới hạn dữ liệu.
4. PharmaFlow project invariants trong `AGENTS.md`: `DATA → FORECAST → RISK → DECISION → OPERATIONAL OUTCOME`; phân biệt Prediction Quality và Decision Quality; observed và synthetic; yêu cầu human-in-the-loop cho recommendation vận hành.

**Trạng thái evidence:** Phân công `Supply Chain` / `Data admin` / `IT admin` được người dùng xác nhận ngày 2026-11-05. Actor đọc khái quát và role mapping MD-01, scope, SoD và audit policy lấy từ tab 2 đã được xác định. Capability/flow/interface vẫn là design proposal; tài liệu này không khẳng định implementation hay deployment.

### Addendum — quyền MD-01 và UC-SD-13 (2026-11-07)

#### Actor và quyền xem chung

Actor đọc dùng chung trong UC-SD-01/02/03/04/06 là “Người dùng được quyền xem Sales/Forecast”. Danh sách role cấp quyền tại MD-01: US-01, US-02, US-03 (Supply Chain Planner), US-04, US-06, US-07, US-11, US-12, US-14, US-15; tất cả chịu scope assignment. Planner có thêm `forecast:adjust`. Data Admin có quyền kỹ thuật đọc evaluation/lưu kết luận; IT Admin có quyền kỹ thuật đọc job/log. Không được suy rộng từ quyền kỹ thuật sang quyền nghiệp vụ.

Trước mọi thao tác, kiểm tra permission, data scope và SoD liên quan; với ghi version, kiểm tra lại quyền hiện hành cùng reference và điều kiện trạng thái. Query không được trả location, aggregate hoặc metadata reference ngoài scope. Nếu không ánh xạ được dimension location vào cây tổ chức thì không tự coi đó là location nội bộ. Audit ghi actor, permission, resource, kết quả, thời điểm; ghi before/after cho thao tác tạo version. Quy tắc mô tả thiết kế, không tuyên bố đã triển khai.

#### UC-SD-13 — Điều chỉnh một giá trị forecast

| Trường | Nội dung |
|---|---|
| Use-case name | Điều chỉnh một giá trị forecast |
| Actor | Supply Chain Planner (US-03) |
| Permission | `forecast:read` + `forecast:adjust` trong scope được gán |
| Truy vết | `US-SD-LS-08`; `UR-SD-08`; `FR-SD-10` |

**Description:** Planner tạo một version điều chỉnh riêng cho một giá trị forecast đã có, ghi lý do và giữ nguyên model output gốc. Lưu điều chỉnh không phê duyệt, phát hành hoặc thực thi hành động tồn kho.

**Pre-conditions**

1. Planner có quyền đọc và điều chỉnh cho resource cùng scope đó.
2. Forecast reference, location/kỳ, grain và unit nhận diện được theo contract.

**Post-conditions**

- Khi lưu thành công, có version điều chỉnh kèm giá trị gốc, giá trị mới, lý do, actor, thời điểm và reference.
- Forecast gốc, source facts và score evaluation không đổi.

**Normal Flow**

1. Planner mở forecast gốc trong scope được cấp.
2. Planner chọn một coordinate location/kỳ và product/grain được output hỗ trợ.
3. Planner nhập một giá trị hữu hạn không âm theo precision của unit contract và cung cấp lý do.
4. Hệ thống kiểm tra permission, scope, SoD áp dụng, reference, unit và giá trị; kiểm quyền lại ngay trước persistence.
5. Hệ thống trình giá trị gốc/mới, chênh lệch, unit và lý do.
6. Planner xác nhận lưu; hệ thống tạo version riêng cùng actor/thời điểm/reference và ghi audit.
7. Hệ thống báo lưu thành công; forecast gốc vẫn là lựa chọn mặc định.

**Alternative Flow**

- `1a`. Không đủ permission/scope → từ chối, không trả dữ liệu ngoài scope.
- `2a`. Forecast reference/coordinate/unit không xác định hoặc mapping location không được xác nhận → không cho chỉnh; nêu phần thiếu.
- `3a`. Thiếu lý do, giá trị âm/vô hạn hoặc precision sai → giữ form, không lưu.
- `4a`. Quyền bị thu hồi hoặc reference không còn hợp lệ trước khi lưu → từ chối, không tạo version.
- `6a`. Giá trị không đổi → báo không có thay đổi, không tạo version.
- `6b`. Persistence lỗi → báo chưa lưu, giữ dữ liệu nhập; không thay đổi forecast gốc.

Lưu version không áp dụng SoD duyệt phiếu nếu không có policy phê duyệt forecast riêng. Không tạo trạng thái approved/published.
<a id="figures-use_case"></a>

---

<a id="spec-sequence"></a>

## Đặc tả Sequence PharmaFlow — Sales & Demand (Landscape V1)

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | `PF-SEQ-SALES-DEMAND-LANDSCAPE-V1` |
| Ngày lập | 2026-11-06 |
| Trạng thái | Proposed — đặc tả tương tác để review trước khi dựng hình |
| Phạm vi | 6 sequence tổng quan và 4 sequence chi tiết cho Sales & Demand DSS |
| Nguồn hành vi | [Use Case Specification](USE_CASE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md), [Requirements](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md), [User Stories](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md) |
| Sơ đồ phạm vi đối chiếu | [Draw.io Sales & Demand](pharmaflow_sales_and_demand_usecase.drawio), 13 trang, tổng quan 22 UC |
| Evidence | Phân công 3 actor đã xác nhận trong bộ nguồn; chi tiết hành vi và thiết kế nội bộ còn Proposed. Không xác nhận code, API, schema DSS hoặc deployment. |

### 1. Phạm vi và nguyên tắc đặc tả

Tài liệu chuyển Normal Flow, Alternative Flow, điều kiện và hậu điều kiện của UC thành các trao đổi có bên gửi, bên nhận và kết quả. Đây là đầu vào để dựng sequence diagram; chưa chứa hình hoặc mã Mermaid/PlantUML.

Nguồn chuẩn cho hành vi là ba tài liệu Markdown trên. File `sales_demand_usecase_diagram.puml` và HTML cũ bên cạnh chứa các luồng POS/kho khác phạm vi; không dùng các luồng đó để bổ sung yêu cầu vào bản này. [Domain/module map](../../docs/architecture/pharmaflow-domain-module-map.md) được dùng để giữ ranh giới Sales với các miền khác, không dùng làm bằng chứng triển khai.

Các ràng buộc xuyên suốt:

1. PharmaFlow là DSS; chuỗi toàn dự án là `DATA → FORECAST → RISK → DECISION → OPERATIONAL OUTCOME`. Bộ sequence này bao phủ Monitoring, Insight và kiểm định nội bộ; không tự mở rộng sang risk, replenishment, mua hàng, transfer hay execution.
2. Sales history, Forecast Sales Quantity và dữ liệu mô phỏng phải phân biệt. Sales không tự trở thành latent demand; forecast trừ sales không chứng minh unmet demand.
3. Giữ grain, đơn vị, coverage và provenance nguồn; không tạo SKU/transaction từ observation aggregate, không cộng observation gốc với POS synthetic như hai nguồn observed độc lập.
4. `demand_location_id` và `fulfillment_location_id` không thay thế nhau. Location hiển thị theo source/run contract.
5. Missing, zero, dữ liệu không hợp lệ và lỗi tải là các trạng thái khác nhau. Thành công một phần không được che phần thiếu/lỗi.
6. Người dùng được quyền xem Sales/Forecast đọc thông tin nghiệp vụ; metadata kỹ thuật được giữ nội bộ. Data admin đọc hồ sơ dữ liệu/evaluation và kết luận kiểm định; IT admin đọc trạng thái/lịch/log theo quyền.
7. Xem forecast không chạy model; xem evaluation không mặc định chạy lại backtest. Ghi kết luận kiểm định không mặc định phê duyệt phát hành forecast hay thực thi quyết định tồn kho.
8. Prediction Quality tách khỏi Decision Quality. Không thêm tự động hóa recommendation vận hành; human review của recommendation thuộc đặc tả tương lai khi scope được xác nhận.

### 2. Mức thiết kế, participant và quy ước

#### 2.1. Mức mô tả

Các sequence dùng participant logic để làm rõ trách nhiệm, chưa gán vào framework, endpoint, bảng SQL hoặc dịch vụ triển khai. Mỗi participant nội bộ dưới đây là **Design proposal**. Có thể hiện thực nhiều trách nhiệm trong cùng ứng dụng; không suy ra kiến trúc microservice.

| Ký hiệu | Participant | Trách nhiệm |
|---|---|---|
| SC | Người dùng được quyền xem Sales/Forecast | Chọn phạm vi và đọc kết quả nghiệp vụ trong role scope; mapping US-01, 02, 03, 04, 06, 07, 11, 12, 14, 15 |
| DA | Data admin | Đối soát dữ liệu, xem xét temporal validity/protocol, ghi kết luận |
| IT | IT admin | Theo dõi vận hành và đọc log theo quyền |
| UI-S | Giao diện Sales & Forecast | Nhận lựa chọn, hiển thị kết quả và trạng thái business |
| UI-D | Giao diện kiểm định | Trình bày hồ sơ kỹ thuật, nhận xác nhận và kết luận của DA |
| UI-O | Giao diện vận hành | Trình bày trạng thái/lịch/log phù hợp quyền |
| C-S | Xử lý Sales/Forecast | Điều phối truy vấn, kiểm tra ngữ nghĩa và chuẩn bị kết quả business |
| C-D | Xử lý kiểm định | Điều phối đối soát, kiểm tra điều kiện evaluation, tiếp nhận kết luận |
| C-O | Xử lý vận hành | Điều phối đọc trạng thái/lịch/log và kiểm tra quyền áp dụng |
| R-S | Nguồn đọc Sales và contract | Cung cấp observation, metadata, dimension và coverage theo nguồn |
| R-F | Nguồn kết quả forecast | Cung cấp output có sẵn và metadata run liên quan |
| R-E | Hồ sơ dữ liệu/evaluation | Cung cấp snapshot/contract, actuals reference, protocol, metric và evidence hiện có |
| R-K | Nơi lưu kết luận kiểm định | Lưu kết luận cùng actor, thời điểm, phạm vi và evidence reference |
| R-O | Nguồn thông tin vận hành | Cung cấp telemetry, lịch và log có sẵn theo contract |

R-E là vai trò truy cập hồ sơ logic, không khẳng định mọi dữ liệu nằm trong cùng database. R-O cũng không khẳng định một sản phẩm observability đã được chọn. Tên participant không phải tên API/class được chốt.

#### 2.2. Quy ước message và điều kiện

- Mã bước `M01…` có phạm vi trong từng sequence; nhánh `A01…` ghi điểm phát sinh và nguồn UC cụ thể.
- Dòng có cùng bên gửi/nhận biểu diễn xử lý nội bộ có thể vẽ thành self-message hoặc note. Hoạt động suy xét của actor không được biến thành kết luận tự động của hệ thống.
- `alt` biểu diễn kết quả loại trừ nhau tại một điểm; `opt` biểu diễn tương tác tùy điều kiện. Đối với mùa vụ hoặc evaluation, cần diễn đạt được cả lý do bỏ qua khi không đủ điều kiện.
- Duyệt logic theo từng location/kỳ không bắt buộc gửi một query cho mỗi cặp; chưa quyết định batching hoặc song song hóa.
- Khi dựng hình, dùng bảng bước làm nguồn nội dung; chia hình chính/ngoại lệ nếu quá dày. Không ép toàn bộ nhánh thành một khung lồng nhau.
- Liên kết tổng quan/chi tiết là tham chiếu đặc tả, không phải participant mang tên UC. `include` không tự định nghĩa thứ tự message và không buộc các bước sau lỗi phải tiếp tục như thành công.
- Mọi sequence bắt buộc áp dụng permission → data scope → SoD liên quan → điều kiện trạng thái trước khi trả/ghi dữ liệu; backend không dựa vào việc ẩn nút ở UI. Khi ghi, kiểm tra lại quyền và reference; từ chối không trả payload ngoài scope; audit actor/permission/resource/outcome/time và before/after khi có thay đổi. Không đặc tả login/token/session vì đây là trách nhiệm dịch vụ xác thực. Căn cứ: tab 2, NFR-SD-07, TC-SD-14.

#### 2.3. Ngữ cảnh business dùng chung — UC-SD-06

SEQ-SD-01–04 đều thực hiện các trách nhiệm sau trước khi hiển thị kết quả:

| Nội dung | Quy tắc |
|---|---|
| Loại số liệu | Nhãn Sales Quantity/Sales history và Forecast Sales Quantity tách biệt |
| Location và kỳ | Chỉ dùng nghĩa được contract xác nhận; thiếu thì báo chưa xác định |
| Đơn vị | Chỉ hiện đơn vị đã xác nhận; chưa rõ thì ghi trạng thái hoặc ẩn đơn vị theo flow |
| Provenance | Kết quả mô phỏng có nhãn dễ hiểu; không nâng provenance chưa rõ thành actual đã kiểm chứng |
| Giá trị thiếu | Thông báo đúng phần thiếu; không thay bằng zero |
| Metadata kỹ thuật | Giữ lineage, source/run ID, cutoff, model/protocol version và technical grain trong hồ sơ nội bộ |

UC-SD-06/2a–2b, 3a–3b được áp dụng ở cả bốn sequence, không cần một sequence actor khởi chạy riêng. FR-SD-01–03 còn yêu cầu kiểm soát grain/coverage; phạm vi grain phục vụ diễn giải phân tích có thể mô tả bằng ngôn ngữ business, không đưa mã lineage kỹ thuật lên màn hình. Chi tiết trình bày cần review UI, không xóa metadata khỏi hồ sơ nội bộ.

### 3. Danh mục sequence

| ID | Tên | Loại | UC chính/thành phần |
|---|---|---|---|
| SEQ-SD-01 | Theo dõi Sales Quantity | Tổng quan | UC-SD-01, UC-SD-06 |
| SEQ-SD-02 | So sánh Sales Quantity | Tổng quan | UC-SD-02, UC-SD-02.1, UC-SD-06 |
| SEQ-SD-03 | Xem xu hướng và biểu hiện mùa vụ | Tổng quan | UC-SD-03, UC-SD-03.1, UC-SD-06 |
| SEQ-SD-04 | Xem forecast theo location/kỳ | Tổng quan | UC-SD-04, UC-SD-06 |
| SEQ-SD-05 | Đối soát và kiểm định forecast | Tổng quan | UC-SD-05, UC-SD-08, UC-SD-09, UC-SD-10 |
| SEQ-SD-06 | Theo dõi vận hành | Tổng quan | UC-SD-07, UC-SD-11, UC-SD-12 |
| SEQ-SD-07 | Đối soát dữ liệu đầu vào | Chi tiết của 05 | UC-SD-08, UC-SD-08.1, UC-SD-08.2, UC-SD-08.3 |
| SEQ-SD-08 | Kiểm tra và so sánh evaluation | Chi tiết của 05 | UC-SD-09, UC-SD-09.1, UC-SD-09.2 |
| SEQ-SD-09 | Lưu kết luận và evidence reference | Chi tiết của 05 | UC-SD-10, UC-SD-10.1 |
| SEQ-SD-10 | Tra cứu log theo job/run | Chi tiết của 06 | UC-SD-12 |

Mã SEQ độc lập mã UC/FR; ví dụ SEQ-SD-07 không ánh xạ FR-SD-07. FR-SD-07/08 đã retire; UC-SD-07 ánh xạ FR-SD-09.

### 4. SEQ-SD-01 — Theo dõi Sales Quantity

**Mục tiêu:** SC đọc lượng bán theo kỳ và những chiều nguồn hỗ trợ, giữ ngữ nghĩa dữ liệu.

**Truy vết:** US-SD-LS-01/06; UR-SD-01/06; FR-SD-01/06; BR-SD-01–06/09; NFR-SD-01/02/09; TC-SD-01/02/04/05/12/13/15.

**Participant:** SC, UI-S, C-S, R-S. **Trigger:** SC mở theo dõi Sales Quantity.

**Điều kiện trước:** quyền đọc phù hợp; dữ liệu và contract có thể được nhận diện, phần thiếu có trạng thái riêng. Dimension chỉ được cung cấp khi có căn cứ nguồn. **Đầu vào:** kỳ và product/group/location/channel khả dụng. **Đầu ra:** giá trị hoặc trạng thái, phạm vi, đơn vị và nhãn business.

#### 4.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | SC → UI-S | Mở chức năng, yêu cầu xem phạm vi thời gian |
| M02 | UI-S → C-S | Yêu cầu phạm vi/chiều khả dụng theo contract |
| M03 | C-S → R-S | Đọc định nghĩa chiều và metadata nguồn hiện có |
| M04 | R-S → C-S → UI-S | Trả chiều hỗ trợ và trạng thái chưa xác định để SC chọn |
| M05 | SC → UI-S → C-S | Gửi kỳ và bộ lọc đã chọn |
| M06 | C-S → R-S | Đọc observation cùng metadata trong phạm vi; không yêu cầu grain chi tiết hơn nguồn |
| M07 | R-S → C-S | Trả dữ liệu, đơn vị, grain, coverage, provenance và phần thiếu có căn cứ |
| M08 | C-S → C-S | Kiểm tra phạm vi; chỉ tổng hợp khi UOM/grain tương thích và có rule |
| M09 | C-S → UI-S → SC | Trả và trình bày Sales Quantity cùng ngữ cảnh UC-SD-06 |

#### 4.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M05: chiều không được nguồn hỗ trợ | Báo không khả dụng; không dựng chiều thay thế; cần lựa chọn hợp lệ để tiếp tục | UC-SD-01/2a |
| A02 | M07: không có bản ghi | Trả trạng thái không có bản ghi cho phạm vi đó; zero chỉ hiển thị khi có giá trị zero được ghi nhận | UC-SD-01/3a |
| A03 | M07–08: đơn vị/provenance chưa xác định | Giữ trạng thái chưa rõ; không tổng hợp thiếu căn cứ hoặc nâng thành actual đã kiểm chứng | UC-SD-01/3b; BR-SD-05/06 |
| A04 | M03/M06–09: lỗi tải | Hiển thị không thể tải; tách phần lỗi nếu chỉ tải được một phần; không giả kết quả hợp lệ | UC-SD-01/4a; TC-SD-13 |

**Hậu điều kiện:** kết quả hoặc trạng thái tương ứng được trình bày; source facts không đổi. **Review trước dựng hình:** kiểm tra cả no record và zero; grain aggregate không bị chuyển thành transaction; áp dụng đầy đủ §2.3.

### 5. SEQ-SD-02 — So sánh Sales Quantity

**Mục tiêu:** SC so sánh tập series/kỳ tương thích, không nhận chênh lệch/thứ hạng sai nghĩa.

**Truy vết:** US-SD-LS-02/06; UR-SD-02/06; FR-SD-02/06; BR-SD-03/04/05/06/09; NFR-SD-02/06/08/09; TC-SD-03/12/13/15.

**Participant:** SC, UI-S, C-S, R-S. **Trigger:** SC chọn chức năng so sánh. **Điều kiện trước:** quyền đọc và có các series/metadata để kiểm tra; đường chính cần ít nhất hai đối tượng/kỳ. **Đầu vào:** tập đối tượng/kỳ, measure và metadata liên quan. **Đầu ra:** tập so sánh hợp lệ, giá trị, chênh lệch/thứ hạng cùng giới hạn.

#### 5.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | SC → UI-S → C-S | Chọn tập series và/hoặc kỳ cần so sánh |
| M02 | C-S → C-S | Kiểm tra có ít nhất hai đối tượng/kỳ |
| M03 | C-S → R-S | Đọc dữ liệu và measure/UOM/grain/coverage theo contract |
| M04 | R-S → C-S | Trả các chuỗi cùng metadata và trạng thái thiếu |
| M05 | C-S → C-S | Thực hiện UC-SD-02.1: xác định tập so sánh trực tiếp được và lý do không tương thích |
| M06 | C-S → C-S | Với tập đủ điều kiện, tính chênh lệch/thứ hạng theo rule; không tự đổi UOM/grain |
| M07 | C-S → UI-S → SC | Hiển thị giá trị, tập so sánh, kỳ, đơn vị, mức chi tiết business và giới hạn; áp dụng UC-SD-06 |

#### 5.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M02: chỉ một đối tượng/kỳ | Yêu cầu chọn thêm hoặc quay lại theo dõi; chưa tính so sánh | UC-SD-02/2a |
| A02 | M05: measure/UOM/grain không tương thích | Không tính chênh lệch/xếp hạng trực tiếp các chuỗi đó; ghi lý do. Chỉ tiếp tục với tập còn đủ điều kiện | UC-SD-02/3a; UC-SD-02.1/3a |
| A03 | M04–05: metadata thiếu | Đánh dấu chưa xác định; không tự quy đổi đơn vị/grain | UC-SD-02.1/2a |
| A04 | M05: coverage thiếu/khác đáng kể | Nêu giới hạn; không coi missing là zero hoặc kết luận nhóm tốt/xấu; nếu không đủ căn cứ thì không so sánh trực tiếp | UC-SD-02/3b; FR-SD-02 |
| A05 | M06: cần aggregation chưa có rule | Giữ riêng các series; không tự cộng | UC-SD-02/4a |
| A06 | M03–07: lỗi tải | Báo phần lỗi, không dùng phần thiếu làm cơ sở xếp hạng | FR-SD-02; TC-SD-13 |

**Hậu điều kiện:** không tạo thứ hạng cho series không tương thích; thứ hạng trong tập chọn không tự nghĩa là tốt/xấu kinh doanh; dữ liệu nguồn không đổi. **Review:** kiểm tra tương thích phải đứng trước tính toán; tập bị loại và phạm vi so sánh phải rõ.

### 6. SEQ-SD-03 — Xem xu hướng và biểu hiện mùa vụ

**Mục tiêu:** SC xem lịch sử và pattern có căn cứ; chỉ bổ sung mùa vụ khi đủ điều kiện.

**Truy vết:** US-SD-LS-03/06; UR-SD-03/06; FR-SD-03/06; BR-SD-01/04/05; NFR-SD-01/02/08/09; TC-SD-04/05/11/12/13. TC-SD-11 của bảng nghiệm thu Requirements là case thiếu chu kỳ.

**Participant:** SC, UI-S, C-S, R-S. **Trigger:** chọn series, measure, khoảng thời gian. **Điều kiện trước:** quyền xem và có lịch sử/coverage để kiểm tra. **Đầu ra:** lịch sử, xu hướng và thông tin mùa vụ nếu đủ bằng chứng; trạng thái thiếu được giữ riêng.

#### 6.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | SC → UI-S → C-S | Yêu cầu xem series/measure trong khoảng thời gian |
| M02 | C-S → R-S | Đọc chuỗi lịch sử, metadata thời gian, provenance và contract |
| M03 | R-S → C-S | Trả dữ liệu cùng coverage, missing period và thông tin có sẵn |
| M04 | C-S → C-S | Kiểm tra tính liên tục, coverage, số chu kỳ theo phương pháp được xác nhận |
| M05 | C-S → UI-S → SC | Trình bày lịch sử/xu hướng trong phạm vi có căn cứ, áp dụng UC-SD-06 |
| M06 | C-S → C-S | Khi đủ coverage/chu kỳ và phương pháp đã xác nhận: thực hiện phần bổ sung UC-SD-03.1 |
| M07 | C-S → UI-S → SC | Bổ sung biểu hiện mùa vụ cùng chu kỳ, phạm vi và căn cứ |

#### 6.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M04: quá ngắn, thiếu kỳ/chu kỳ | Hiện lịch sử khả dụng với khoảng trống; ghi chưa đủ dữ liệu và phạm vi thiếu; bỏ phần kết luận mùa vụ | UC-SD-03/3a; UC-SD-03.1/2a |
| A02 | M03–04: provenance chưa rõ | Chỉ hiện cảnh báo provenance chưa rõ; không trình giá trị/lịch sử như dữ liệu đã kiểm chứng; không kết luận mùa vụ thiếu căn cứ | UC-SD-03/3b; UC-SD-03.1/2a; quyết định review W19.10 |
| A03 | M06: phương pháp/điều kiện chưa xác nhận | Chỉ trình bày lịch sử; không tự chọn thuật toán/ngưỡng chu kỳ | UC-SD-03/5a; UC-SD-03.1/2b |
| A04 | M02–07: lỗi tải | Hiển thị lỗi/phần thiếu riêng; không dựng pattern từ dữ liệu tải thất bại | NFR-SD-09; TC-SD-13 |

**Hậu điều kiện:** historical pattern không bị gọi là latent demand hoặc lost demand. Không đổi source facts. **Review:** nhánh không có mùa vụ vẫn hoàn thành mục tiêu xem lịch sử; ngưỡng coverage và thuật toán là TBD, không mặc định 12/24 tháng.

### 7. SEQ-SD-04 — Xem Forecast Sales Quantity theo location/kỳ

**Mục tiêu:** SC đọc forecast có sẵn cho một/nhiều location và kỳ, giữ riêng kết quả từng cặp.

**Truy vết:** US-SD-LS-04/06; UR-SD-04/06; FR-SD-04/06; BR-SD-01/05/07/09; NFR-SD-01/05/06/09; TC-SD-06/07/12/13/15.

**Participant:** SC, UI-S, C-S, R-F. **Trigger:** SC mở forecast và chọn location/kỳ. **Điều kiện trước:** phạm vi đọc phù hợp; source/run contract nhận diện location/kỳ và thông tin hiện có. Đường thành công có ít nhất một output hợp lệ; đường thiếu vẫn phải trả trạng thái. **Đầu vào:** location và kỳ forecast. **Đầu ra:** con số/trạng thái từng cặp và đơn vị đã xác nhận.

#### 7.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | SC → UI-S → C-S | Yêu cầu phạm vi location/kỳ khả dụng |
| M02 | C-S → R-F → C-S | Đọc phạm vi source/run hỗ trợ; không suy location mới |
| M03 | C-S → UI-S → SC | Cung cấp lựa chọn có căn cứ |
| M04 | SC → UI-S → C-S | Gửi một/nhiều location và kỳ forecast |
| M05 | C-S → R-F | Tìm output cùng metadata cần thiết cho phạm vi chọn |
| M06 | R-F → C-S | Trả output hiện có, run reference/trạng thái và metadata nội bộ |
| M07 | C-S → C-S | Kiểm tra target, location, kỳ và điều kiện hợp lệ theo contract; xác định trạng thái từng cặp |
| M08 | C-S → UI-S | Trả số forecast được phép hiển thị và trạng thái business; metadata kỹ thuật giữ nội bộ |
| M09 | UI-S → SC | Hiển thị Forecast Sales Quantity riêng từng location/kỳ, đơn vị đã xác nhận và nhãn mô phỏng khi áp dụng |

#### 7.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M04/M07: location không được hỗ trợ | Báo không khả dụng, không đổi demand location thành fulfillment location hoặc ngược lại | UC-SD-04/2a |
| A02 | M06–07: thiếu output hợp lệ cho một/nhiều cặp | Ghi “chưa có forecast cho location/kỳ này” đúng phần thiếu; giữ phần hợp lệ; không điền zero | UC-SD-04/3a |
| A03 | M07: run chưa hợp lệ/chưa hoàn tất hoặc thiếu metadata bắt buộc | Không công bố output đó; giữ lý do kỹ thuật trong hồ sơ nội bộ; UI dùng thông báo business | UC-SD-04/3b; TC-SD-07 |
| A04 | M08–09: đơn vị chưa xác nhận | Ghi chưa xác định hoặc ẩn đơn vị; không tự suy đoán | UC-SD-04/4a |
| A05 | M08–09: output synthetic | Gắn “dữ liệu mô phỏng”, không bắt SC đọc provenance code | UC-SD-04/4b |
| A06 | M02/M05–09: tải thất bại | Báo lỗi tải riêng với trạng thái chưa có forecast; giữ rõ phần thành công/phần lỗi | NFR-SD-09; TC-SD-13 |

**Hậu điều kiện:** không cộng ngầm định nhiều location; không cập nhật model, source facts hoặc quyết định vận hành. Không hiển thị model/version, protocol, cutoff kỹ thuật, run ID và lineage trên UI-S. **Review:** chưa có chính sách chọn run khi nhiều output trùng target/location/kỳ; không mặc định lấy run mới nhất hoặc tự gắn trạng thái approved.

### 8. SEQ-SD-05 — Đối soát dữ liệu và kiểm định forecast

**Mục tiêu:** DA kiểm tra dữ liệu/evaluation và lưu kết luận có evidence, kể cả kết luận chưa đánh giá được.

**Truy vết:** US-SD-LS-05; UR-SD-05; FR-SD-05; BR-SD-05/07; NFR-SD-01/05/07/09; TC-SD-08/09/10/17.

**Participant:** DA, UI-D, C-D, R-E, R-K. **Trigger:** DA mở hồ sơ snapshot/run cần kiểm định. **Điều kiện trước:** quyền truy cập phù hợp và nhận diện được hồ sơ; trường contract chưa có phải được đánh dấu, không tự điền. **Đầu vào:** tham chiếu snapshot/run/evaluation, thông tin hiện có theo contract. **Đầu ra:** kết quả đối soát, trạng thái evaluation và kết luận lưu thành công hoặc thông báo chưa lưu.

#### 8.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | DA → UI-D → C-D | Chọn hồ sơ dữ liệu/evaluation |
| M02 | C-D → R-E → C-D | Đọc snapshot, provenance, mapping, UOM và hồ sơ kỹ thuật hiện có |
| M03 | C-D → UI-D → DA | Trình bày dữ liệu và các trường thiếu để đối soát |
| M04 | DA ↔ UI-D ↔ C-D | Đối soát đầu vào theo SEQ-SD-07; ghi kết quả từng hạng mục |
| M05 | C-D → C-D | Xác định điều kiện mở phần evaluation từ đối soát và protocol; không tự kết luận chất lượng |
| M06 | DA ↔ UI-D ↔ C-D | Nếu đủ điều kiện, kiểm tra temporal validity và khả năng so sánh theo SEQ-SD-08 |
| M07 | C-D → UI-D → DA | Trình bày metric/phạm vi hợp lệ hoặc trạng thái không đánh giá được cùng lý do |
| M08 | DA ↔ UI-D ↔ C-D | Nhập kết luận, căn cứ và evidence theo SEQ-SD-09; bước này vẫn cần khi phần so sánh bị chặn |
| M09 | C-D → R-K → C-D | Lưu kết luận cùng actor/thời điểm/reference; nhận kết quả lưu |
| M10 | C-D → UI-D → DA | Chỉ xác nhận đã lưu sau khi nhận kết quả lưu thành công |

#### 8.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M02–03: metadata thiếu | Ghi chưa có/chưa xác định; không suy cấu hình | UC-SD-05/2a |
| A02 | M04: lỗi dữ liệu ảnh hưởng evaluation | Giữ sai lệch và căn cứ; chặn diễn giải score như hợp lệ; tiếp tục phần ghi kết luận phù hợp | UC-SD-05/3a |
| A03 | M05–06: actuals/baseline/origins/horizon/target/protocol không tương thích | Không so sánh hoặc ghi chưa đánh giá được, chuyển M08 | UC-SD-05/4a |
| A04 | M06: leakage hoặc run chưa hoàn tất | Không đưa kết luận Prediction Quality dựa trên run đó; ghi trạng thái, evidence và chuyển M08 | UC-SD-05/4b |
| A05 | M07: coverage chưa đủ tính metric | Không tạo score thay thế hoặc nhãn tốt/xấu; chuyển ghi kết luận | UC-SD-05/5a |
| A06 | M09: lưu thất bại | Báo chưa lưu; không sửa source facts/score; không hiển thị hoàn tất | UC-SD-05/7a |
| A07 | Truy cập hồ sơ bị sự cố dịch vụ/job | Giữ mã hồ sơ hiện có và chuyển IT xử lý theo quy trình; không tự restart. Nếu chưa thể lưu, không nhận là đã lưu kết luận | UC-SD-05/7b |

**Hậu điều kiện:** kết luận đã lưu phải truy vết được; kết luận không hợp lệ/chưa đánh giá được vẫn là kết quả nghiệp vụ hợp lệ của quy trình kiểm định. Prediction Quality và Decision Quality lưu/diễn giải riêng. **Review:** M04/M06/M08 là nhóm tương tác, không vẽ thành ba service mang tên use case; tham chiếu hình chi tiết bằng liên kết tài liệu.

### 9. SEQ-SD-06 — Theo dõi vận hành hệ thống

**Mục tiêu:** IT xem trạng thái, lịch, độ mới và mở log khi cần để phân loại vấn đề.

**Truy vết:** US-SD-LS-07; UR-SD-07; FR-SD-09; NFR-SD-07/09; TC-SD-14/16.

**Participant:** IT, UI-O, C-O, R-O. **Trigger:** IT mở theo dõi vận hành. **Điều kiện trước:** phạm vi được phép xem; telemetry/lịch được truy vấn hoặc xác định chưa có. **Đầu vào:** dịch vụ/job, khoảng lịch và job/run reference khi có. **Đầu ra:** trạng thái và timestamp, lịch, độ mới, log tùy yêu cầu.

#### 9.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | IT → UI-O → C-O | Chọn dịch vụ/job hoặc khoảng lịch |
| M02 | C-O → R-O | Tra cứu trạng thái, thời điểm bắt đầu/kết thúc, timestamp telemetry và lịch hiện có |
| M03 | R-O → C-O | Trả trạng thái/lịch cùng timestamp và phần chưa có |
| M04 | C-O → UI-O → IT | Hiển thị trạng thái và độ mới có căn cứ — UC-SD-11, UC-SD-11.1, UC-SD-11.2 |
| M05 | IT → IT | Đánh giá trạng thái và ghi nhận vấn đề vận hành nếu có |
| M06 | IT → UI-O → C-O | Tùy yêu cầu xem chi tiết job/run: tiếp SEQ-SD-10 |
| M07 | IT → IT | Phân loại vấn đề; nếu thuộc dữ liệu/model thì chuyển DA theo quy trình được xác nhận |

#### 9.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M03: không có job phù hợp | Báo không tìm thấy job trong phạm vi; không tạo job giả | UC-SD-07/2a; UC-SD-11/2a |
| A02 | M03: thiếu telemetry/lịch | Nêu dữ liệu chưa được cung cấp; trạng thái chưa biết, không coi thành công | UC-SD-07/3a; UC-SD-11/3a; UC-SD-11.1/2a; UC-SD-11.2/2a |
| A03 | M04: telemetry/lịch cũ | Hiển thị timestamp cuối và cảnh báo; không tự cập nhật lịch | UC-SD-07/3a; UC-SD-11/4a; UC-SD-11.1/3a; UC-SD-11.2/3a |
| A04 | M05/M07: vấn đề dữ liệu/forecast | IT chuyển DA, không sửa facts hoặc kết luận chất lượng model | UC-SD-07/4a |
| A05 | M05: cần retry/restart/thay lịch nhưng quyền/quy trình chưa chốt | Chỉ ghi nhận nhu cầu, không thực thi | UC-SD-07/4b |
| A06 | M02–04: lỗi truy cập nguồn vận hành | Thể hiện lỗi đọc tách khỏi chưa có telemetry; không suy trạng thái job từ lỗi đọc | NFR-SD-09 |

**Hậu điều kiện:** thao tác xem không đổi trạng thái job/lịch; không tự kết luận thành công khi telemetry thiếu. **Review:** M05/M07 không mặc định có ticket service hay gửi email tự động; cơ chế ghi nhận/chuyển đầu mối là TBD.

### 10. SEQ-SD-07 — Đối soát dữ liệu đầu vào

**Mục tiêu:** DA xác nhận nguồn, snapshot, đơn vị/mapping và coverage trước khi diễn giải evaluation.

**Truy vết:** UC-SD-08/08.1/08.2/08.3; US-SD-LS-05; UR-SD-05; FR-SD-05; BR-SD-03–07/09; NFR-SD-01/05; TC-SD-17. **Quan hệ:** chi tiết M04 của SEQ-SD-05.

**Participant:** DA, UI-D, C-D, R-E. **Trigger:** mở phần đối soát của hồ sơ kiểm định. **Điều kiện trước:** nhận diện được snapshot/dataset cần đối chiếu và quyền đọc. **Đầu vào:** snapshot reference, source contract và phạm vi mong đợi nếu đã định nghĩa. **Đầu ra:** kết quả từng kiểm tra, sai lệch, phần thiếu và trạng thái ảnh hưởng evaluation.

#### 10.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | DA → UI-D → C-D | Chọn snapshot/dataset gắn lần kiểm định |
| M02 | C-D → R-E → C-D | Đọc nguồn, snapshot/version, provenance và contract reference — UC-SD-08.1 |
| M03 | C-D → UI-D → DA | Trình bày nguồn/contract; DA kiểm tra tham chiếu và phiên bản |
| M04 | C-D → UI-D → DA | Hiển thị UOM/location thực tế cạnh định nghĩa contract — UC-SD-08.2 |
| M05 | DA → UI-D → C-D | Xác nhận phù hợp/không phù hợp/chưa xác định cho từng đơn vị/mapping; giữ căn cứ |
| M06 | C-D → R-E → C-D | Đọc grain, kỳ/phạm vi mong đợi và dữ liệu cần kiểm coverage — UC-SD-08.3 |
| M07 | C-D → C-D | Đối chiếu phạm vi; tổng hợp coverage, missing, duplicate theo định nghĩa contract |
| M08 | C-D → UI-D → DA | Trình bày kết quả từng hạng mục và phạm vi ảnh hưởng |
| M09 | DA → UI-D → C-D | Xác nhận kết quả đối soát, phần chưa đủ căn cứ và ảnh hưởng tới điều kiện evaluation |
| M10 | C-D → UI-D | Trả kết quả cho SEQ-SD-05; kết quả được đưa vào hồ sơ kết luận ở SEQ-SD-09 |

#### 10.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M02: không tìm snapshot/contract | Ghi thiếu nguồn/contract, dừng kiểm tra phụ thuộc; trả trạng thái để ghi kết luận | UC-SD-08/2a; UC-SD-08.1/2a |
| A02 | M03: version không xác định | Ghi chưa truy vết đầy đủ, không đoán nguồn/version | UC-SD-08.1/3a |
| A03 | M04–05: thiếu định nghĩa UOM/location | Ghi chưa xác định; không tự đổi đơn vị hay ghép location | UC-SD-08/3a; UC-SD-08.2/1a |
| A04 | M05: đơn vị/mapping không khớp | Ghi chênh lệch và căn cứ; không sửa source facts | UC-SD-08.2/2a |
| A05 | M06: contract thiếu grain/phạm vi mong đợi | Không nhận coverage đã đạt; đánh dấu chưa đánh giá được | UC-SD-08.3/1a |
| A06 | M07–08: missing/duplicate/coverage lệch | Ghi phạm vi/mức ảnh hưởng; không tự xóa duplicate hoặc lấp missing | UC-SD-08/3b; UC-SD-08.3/2a |
| A07 | M09: dữ liệu không đạt điều kiện | Trả invalid hoặc not assessable theo evidence; SEQ-SD-05 bỏ phần evaluation bị chặn nhưng vẫn ghi kết luận | UC-SD-08/5a |

**Hậu điều kiện:** không có thao tác làm sạch/sửa nguồn trong sequence; kết quả đối soát là đầu vào điều kiện evaluation. **Review:** thuật toán nhận diện duplicate, calendar mong đợi và mức ảnh hưởng chưa có contract thì phải giữ TBD, không tự đặt ngưỡng đạt.

### 11. SEQ-SD-08 — Kiểm tra và so sánh evaluation

**Mục tiêu:** DA đọc metric trên temporal backtest hợp lệ và protocol tương thích, tránh so sánh sai phạm vi.

**Truy vết:** UC-SD-09/09.1/09.2; US-SD-LS-05; UR-SD-05; FR-SD-05 và Requirements §4.2; BR-SD-07; NFR-SD-05; TC-SD-08/09/10/17. **Quan hệ:** chi tiết M06–07 của SEQ-SD-05.

**Participant:** DA, UI-D, C-D, R-E. **Trigger:** DA mở phần evaluation khi đối soát không chặn và đủ tham chiếu protocol. **Điều kiện trước:** nhận diện forecast/baseline/actuals/target/grain/horizon/origins; phần thiếu được xử lý bằng nhánh tương ứng. **Đầu ra:** phạm vi metric có thể đọc, trạng thái temporal validity/comparability và căn cứ cho kết luận.

#### 11.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | DA → UI-D → C-D | Mở evaluation reference đã qua kiểm tra dữ liệu |
| M02 | C-D → R-E → C-D | Đọc cutoff/origins, horizon, target/grain/UOM, actuals reference, model/baseline/protocol version, metric definitions và trạng thái run |
| M03 | C-D → UI-D → DA | Trình bày hồ sơ thời gian cùng evidence hiện có — UC-SD-09.1 |
| M04 | DA → UI-D → C-D | Kiểm tra mỗi origin chỉ dùng thông tin trước origin, ghi temporal validity và vấn đề phát hiện; hệ thống hỗ trợ kiểm tra theo contract, không thay suy xét của DA |
| M05 | C-D → C-D | Đối chiếu model/baseline về actuals, target, grain, unit, horizon, origins, evaluation period và protocol — UC-SD-09.2 |
| M06 | C-D → UI-D → DA | Trả các trường so khớp/sai khác để DA xem xét; chỉ trình so sánh trực tiếp khi đủ điều kiện |
| M07 | C-D → UI-D → DA | Hiển thị metric có sẵn, định nghĩa/đơn vị, phạm vi và trạng thái so sánh |
| M08 | DA → UI-D → C-D | Ghi nhận xem xét Prediction Quality để chuyển SEQ-SD-09; không tự chọn model thắng hoặc kết luận outcome |

#### 11.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M02–03: metadata/version thiếu | Ghi chưa đủ căn cứ, không suy cấu hình; không nhận temporal validity/comparability đã đạt | UC-SD-09/2a; UC-SD-09.1/1a; UC-SD-09.2/1a |
| A02 | M04: phát hiện leakage | Ghi run không hợp lệ cho kết luận chất lượng; chuyển lưu kết luận có căn cứ | UC-SD-09/3a; UC-SD-09.1/2a |
| A03 | M05–06: protocol/phạm vi không khớp | Không so sánh trực tiếp; ghi rõ trường lệch | UC-SD-09/4a; UC-SD-09.2/2a |
| A04 | M02/M07: run chưa hoàn tất hoặc actuals chưa đủ coverage | Ghi chưa đánh giá được; nếu có giá trị metric nguồn thì hiển thị nguyên số kèm nhãn “Chưa đánh giá được”; không tính score mới/thay thế hoặc xếp hạng; không có số thì chỉ hiển thị trạng thái | UC-SD-09/4b |
| A05 | M07: metric chưa chốt/không xác định được | Trình bày trạng thái và căn cứ; không xếp hạng model tốt/xấu hoặc tạo công thức thay thế | UC-SD-09/5a |

**Hậu điều kiện:** trạng thái kiểm tra và phạm vi được chuyển cho phần kết luận; score gốc không bị sửa. Với A04, giá trị metric nguồn có sẵn (nếu có) vẫn được trình bày kèm nhãn “Chưa đánh giá được”; không tính score mới/thay thế hoặc xếp hạng. MAE/RMSE/WAPE/Bias là ứng viên, chưa mặc định bộ nghiệm thu. **Review:** rolling-origin yêu cầu evidence theo từng origin; chỉ có một trường cutoff không chứng minh không leakage. Không thêm lệnh train/backtest vào đường xem hồ sơ này.

### 12. SEQ-SD-09 — Lưu kết luận và evidence reference

**Mục tiêu:** DA lưu nhận xét và trạng thái có thể truy vết mà không ghi đè source facts hoặc score.

**Truy vết:** UC-SD-10/10.1; US-SD-LS-05; UR-SD-05; FR-SD-05; NFR-SD-01/05/07/09; TC-SD-17. **Quan hệ:** chi tiết M08–10 của SEQ-SD-05.

**Participant:** DA, UI-D, C-D, R-E, R-K. **Trigger:** DA mở biểu mẫu kết luận. **Điều kiện trước:** đã kiểm tra hoặc ghi rõ trạng thái các phần đối soát/evaluation; nhận diện hồ sơ và bằng chứng đang có. **Đầu vào:** kết quả kiểm tra, trạng thái kết luận, nhận xét/căn cứ, snapshot/run/evidence references. **Đầu ra:** bản ghi kết luận hoặc xác nhận chưa lưu.

#### 12.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | DA → UI-D → C-D | Mở biểu mẫu cho hồ sơ evaluation |
| M02 | C-D → R-E → C-D | Đọc kết quả đối soát, metric có căn cứ, phạm vi protocol và references hiện có |
| M03 | C-D → UI-D → DA | Hiển thị kết quả và phần bằng chứng còn thiếu |
| M04 | DA → UI-D → C-D | Chọn trạng thái, nhập nhận xét/căn cứ và gắn snapshot/run/evidence — UC-SD-10.1 |
| M05 | C-D → C-D | Kiểm tra trạng thái/căn cứ bắt buộc theo contract và tính hợp lệ references; xác định mức đầy đủ evidence |
| M06 | C-D → C-D | Gắn actor/thời điểm và phạm vi hồ sơ theo quy tắc được xác nhận |
| M07 | C-D → R-K | Gửi bản ghi kết luận và references để lưu; không cập nhật facts/actuals/score gốc |
| M08 | R-K → C-D | Trả kết quả lưu |
| M09 | C-D → UI-D → DA | Hiển thị đã lưu cùng thông tin truy vết có sẵn chỉ khi M08 thành công |

#### 12.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M03–04: evaluation không đủ điều kiện | DA ghi không hợp lệ/chưa đánh giá được và lý do; không nhập score thay thế | UC-SD-10/2a |
| A02 | M04–05: thiếu evidence reference | Ghi rõ bằng chứng thiếu, không biểu thị truy vết đầy đủ; chưa có policy buộc đầy đủ mọi reference thì không tự cấm lưu kết luận chưa đánh giá được | UC-SD-10/4a; UC-SD-10.1/1a |
| A03 | M05: reference không hợp lệ | Yêu cầu xác nhận lại, không biểu thị reference hợp lệ hoặc evidence đầy đủ | UC-SD-10.1/2a |
| A04 | M05: thiếu trạng thái/căn cứ bắt buộc | Yêu cầu bổ sung, không lưu bản ghi hoàn chỉnh | UC-SD-10/5a |
| A05 | M07–08: lưu thất bại | Báo chưa lưu; giữ facts và score nguyên vẹn; xử lý lại theo quyền/quy trình đã chốt, không tự retry nền | UC-SD-10/6a |

**Hậu điều kiện:** chỉ bản ghi có phản hồi lưu thành công được nhận là đã lưu; trạng thái invalid/not assessable có thể là kết luận được lưu. Không phát sinh workflow publish/approval vận hành. **Review:** cơ chế sửa/version kết luận, lưu nháp, transaction, idempotency và retention là TBD; chưa thêm UPDATE/UPSERT hay append-only contract.

### 13. SEQ-SD-10 — Tra cứu log theo job/run

**Mục tiêu:** IT chẩn đoán một job/run trong phạm vi được phép, không lộ thông tin nhạy cảm.

**Truy vết:** UC-SD-12; US-SD-LS-07; UR-SD-07; FR-SD-09; NFR-SD-07/09; TC-SD-14/16. **Quan hệ:** mở rộng có điều kiện M06 của SEQ-SD-06, tại điểm “Xem chi tiết job/run”.

**Participant:** IT, UI-O, C-O, R-O. **Trigger:** IT chủ động yêu cầu log. **Điều kiện trước:** có job/run reference, quyền đọc log áp dụng và nguồn log theo contract; thiếu được trả thành trạng thái riêng. **Đầu vào:** job/run ID, thời gian/phạm vi hiện có. **Đầu ra:** log đã kiểm soát nội dung hoặc không có log/không đủ quyền/lỗi truy cập.

#### 13.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | IT → UI-O | Yêu cầu xem log từ job/run đang theo dõi |
| M02 | IT → UI-O → C-O | Chọn/xác nhận job/run ID và phạm vi có sẵn |
| M03 | C-O → C-O | Kiểm tra reference và quyền đọc log theo policy áp dụng trước khi trả nội dung |
| M04 | C-O → R-O | Tra cứu log theo job/run và phạm vi được phép |
| M05 | R-O → C-O | Trả log hiện có hoặc trạng thái không có log |
| M06 | C-O → C-O | Che/loại thông tin nhạy cảm theo chính sách trước khi hiển thị |
| M07 | C-O → UI-O → IT | Trả nội dung được phép hiển thị và phạm vi log |
| M08 | IT → IT | Phân loại sự cố; chuyển DA nếu có dấu hiệu dữ liệu/model theo quy trình, trở lại theo dõi |

#### 13.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M02–03: thiếu/sai ID | Yêu cầu chọn lại từ job/run khả dụng; chưa truy xuất log với reference sai | UC-SD-12/2a |
| A02 | M05: không có log/telemetry | Báo không có dữ liệu log, không suy job thành công | UC-SD-12/3a |
| A03 | M03: không đủ quyền | Từ chối, không trả nội dung; ghi nhận kết quả kiểm tra quyền theo chính sách đã chốt | UC-SD-12/3b |
| A04 | M06: log nguồn có credentials/sensitive values | Không hiển thị giá trị đó; ghi nhận sự cố theo quy trình bảo mật; không sao chép giá trị nhạy cảm vào thông báo | UC-SD-12/4a |
| A05 | M08: log gợi ý lỗi dữ liệu/forecast | IT chuyển DA; không tự sửa facts/kết luận evaluation | UC-SD-12/5a |
| A06 | M04–07: lỗi đọc log | Báo lỗi truy cập riêng với không có log; không dùng lỗi truy cập để suy trạng thái run | NFR-SD-09 |

**Hậu điều kiện:** log không làm đổi job state; không restart/thay lịch; không thay kết luận chất lượng. **Review:** auth mechanism, masking rules, log index, retention và kênh chuyển sự cố chưa chốt; không tự chọn sản phẩm hoặc triển khai endpoint.

### 14. Ma trận bao phủ và quyết định cần chốt

#### 14.1. Bao phủ 22 use case

| UC | Sequence thực hiện | Trách nhiệm được bao phủ |
|---|---|---|
| UC-SD-01 | SEQ-SD-01 | Đọc Sales Quantity và các trạng thái dữ liệu |
| UC-SD-02 | SEQ-SD-02 | So sánh sau kiểm tra tương thích |
| UC-SD-02.1 | SEQ-SD-02/M05 và A02–A05 | Measure/UOM/grain/coverage và tập so sánh |
| UC-SD-03 | SEQ-SD-03 | Lịch sử/xu hướng và coverage |
| UC-SD-03.1 | SEQ-SD-03/M06–M07, A01–A03 | Mùa vụ chỉ khi đủ căn cứ |
| UC-SD-04 | SEQ-SD-04 | Forecast có sẵn theo từng location/kỳ |
| UC-SD-05 | SEQ-SD-05 | Điều phối kiểm định và kết luận |
| UC-SD-06 | §2.3 và SEQ-SD-01–04 | Nhãn business, missing/zero, mô phỏng và metadata nội bộ |
| UC-SD-07 | SEQ-SD-06 | Theo dõi vận hành và phân loại vấn đề |
| UC-SD-08 | SEQ-SD-07; SEQ-SD-05/M04 | Đối soát đầu vào |
| UC-SD-08.1 | SEQ-SD-07/M02–M03, A01–A02 | Nguồn/snapshot/contract/version |
| UC-SD-08.2 | SEQ-SD-07/M04–M05, A03–A04 | UOM/location mapping |
| UC-SD-08.3 | SEQ-SD-07/M06–M09, A05–A07 | Coverage/missing/duplicate |
| UC-SD-09 | SEQ-SD-08; SEQ-SD-05/M06–M07 | Evaluation đủ điều kiện |
| UC-SD-09.1 | SEQ-SD-08/M03–M04, A01–A02 | Temporal validity |
| UC-SD-09.2 | SEQ-SD-08/M05–M06, A01/A03 | Tương thích forecast/baseline |
| UC-SD-10 | SEQ-SD-09; SEQ-SD-05/M08–M10 | Kết luận và kết quả lưu |
| UC-SD-10.1 | SEQ-SD-09/M03–M05, A02–A03 | Căn cứ/reference và evidence thiếu |
| UC-SD-11 | SEQ-SD-06/M02–M04 | Trạng thái và lịch |
| UC-SD-11.1 | SEQ-SD-06/M02–M04, A02–A03 | Trạng thái và timestamp telemetry |
| UC-SD-11.2 | SEQ-SD-06/M02–M04, A02–A03 | Lịch và độ mới |
| UC-SD-12 | SEQ-SD-10; SEQ-SD-06/M06 | Log tùy yêu cầu theo quyền |

#### 14.2. Các quyết định mở

| Mã | Nội dung chưa chốt | Ảnh hưởng |
|---|---|---|
| OQ-SEQ-01 | Dataset ưu tiên, grain, UOM, calendar/coverage và dimension contract | Kiểm tra, aggregation và output SEQ-SD-01–03/07 |
| OQ-SEQ-02 | Phương pháp/ngưỡng đủ coverage và chu kỳ để diễn giải mùa vụ | Guard M06 của SEQ-SD-03 |
| OQ-SEQ-03 | Forecast output/run contract và chính sách chọn output khi có nhiều run | Điều kiện khả dụng/hợp lệ của SEQ-SD-04; chưa mặc định latest/approved |
| OQ-SEQ-04 | Target/horizon/origins, baseline/model, metric definitions và mẫu số | Temporal/comparability và metric SEQ-SD-08; chưa đặt ngưỡng thắng |
| OQ-SEQ-05 | Bộ trạng thái chính thức của kiểm định, field bắt buộc, reference validation, chính sách sửa/lưu | SEQ-SD-05/07–09; các từ invalid/not assessable/not evaluable hiện mô tả nghĩa theo nguồn, chưa là enum schema |
| OQ-SEQ-06 | Cơ chế authentication, DB/RLS enforcement, audit retention/implementation và masking chi tiết | Policy role/scope/SoD/audit fields đã theo tab 2; các chi tiết triển khai ảnh hưởng enforcement và sequence vận hành |
| OQ-SEQ-07 | Telemetry/lịch/log contract, timezone/timestamp, quy tắc stale | SEQ-SD-06/10; chưa tự đặt timeout hoặc ngưỡng độ cũ |
| OQ-SEQ-08 | Ghi nhận/chuyển sự cố và quyền retry/restart/thay lịch | Chưa bổ sung ticket integration hoặc thao tác thực thi |
| OQ-SEQ-09 | Latency/workload, retry cho thao tác xem, error presentation và layout UI | NFR-SD-06/08/09; chưa tự đặt SLA/số lần retry |

Thiếu quyết định mở không phải lý do tự điền giả định vào sequence. Khi dựng hình có thể giữ participant logic và ghi guard phụ thuộc contract; khi hiện thực phải chốt owning contract tương ứng.

#### 14.3. Checklist review trước dựng hình

- [ ] Mỗi đường đi có trigger, dữ liệu vào, bên nhận và kết quả cuối rõ.
- [ ] Mỗi Alternative Flow trong UC được ánh xạ tới nhánh trong sequence hoặc trách nhiệm dùng chung §2.3.
- [ ] Điều kiện dữ liệu được kiểm tra trước phép tính/diễn giải phụ thuộc; lỗi không rơi tiếp vào thông báo thành công.
- [ ] Nhánh DA không đánh giá được vẫn đi tới ghi kết luận; lỗi lưu kết thúc bằng chưa lưu.
- [ ] Tách hành vi kiểm tra của hệ thống với xem xét/xác nhận của DA; phân loại/chuyển sự cố của IT chưa tự thành integration.
- [ ] Không thêm participant, endpoint, bảng DSS, thuật toán, threshold, auth flow hoặc permission chưa có căn cứ như quyết định đã chốt.
- [ ] Forecast view không train model; evaluation view không tự chạy backtest; kết luận không tự publish/execute.
- [ ] Forecast nhiều location giữ riêng; missing khác zero; simulated khác observed; technical metadata giữ nội bộ.
- [ ] Sau dựng hình, kiểm cả khả năng render và coverage nội dung; chia hình nếu quá nhiều message/nhánh.

### 15. Nguồn đối chiếu

1. [User Stories Sales & Demand Landscape V1](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md), §3–5: actors, acceptance criteria và ranh giới module.
2. [Requirements Sales & Demand Landscape V1](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md), §4–7: FR, protocol, business/data rules, NFR và acceptance scenarios; §9: giới hạn evidence và data readiness.
3. [Use Case Specification Sales & Demand Landscape V1](USE_CASE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md), §4–6: toàn bộ Normal/Alternative Flow, quan hệ và truy vết 22 UC.
4. [Draw.io Sales & Demand](pharmaflow_sales_and_demand_usecase.drawio), trang 13 tổng quan và 12 trang UC.
5. [Project invariants](../../AGENTS.md) và [Domain/module map](../../docs/architecture/pharmaflow-domain-module-map.md): DSS boundary, ngữ nghĩa và evidence levels.

Tài liệu này không thay thế ba tài liệu nghiệp vụ nguồn và không khóa baseline requirements. Khi review làm đổi hành vi, phải cập nhật nguồn UC/FR/US liên quan trước hoặc cùng thay đổi đặc tả sequence.

### Addendum — access control và SEQ-SD-11 (2026-11-07)

#### Quy tắc quyền áp dụng cho mọi sequence

Actor đọc Sales/Forecast là “Người dùng được quyền xem Sales/Forecast”, tương ứng US-01, 02, 03, 04, 06, 07, 11, 12, 14, 15 theo role assignment và data scope. Planner có thêm `forecast:adjust`. Data Admin thực hiện evaluation bằng quyền kỹ thuật `forecast_evaluation:read/record`; IT Admin xem job/log bằng `job:read`/`job_log:read`. Không suy ra quyền nghiệp vụ từ hai role kỹ thuật.

Trước khi đọc dữ liệu, controller kiểm permission → data scope → SoD áp dụng. SEQ-SD-01–09 mô hình hóa hai operand: quyền/scope/SoD đạt thì tiếp tục flow; nếu bị từ chối thì ghi audit actor, permission, resource, outcome, timestamp, trả refusal và không trả payload ngoài scope. Trước khi ghi kết luận/version, kiểm lại permission, scope, SoD liên quan và resource reference ngay trước persistence; write audit có before/after. Chỉ trả kết quả, location, aggregate và reference thuộc scope. Location không có mapping được xác nhận không được gán vào scope nội bộ. Đây là policy requirement, chưa mô tả endpoint, auth protocol hay deployment.

#### 15. SEQ-SD-11 — Điều chỉnh một giá trị forecast

**Actor:** Planner (US-03). **Participants:** Planner, UI-F, C-F, R-F (forecast reference/version store), R-A (audit record). R-F/R-A là participant logic để mô tả trách nhiệm, không khẳng định bảng hay service đã triển khai.

**Trigger:** Planner chọn “Điều chỉnh” trên một forecast được phép xem. **Điều kiện trước:** có `forecast:read` + `forecast:adjust`; resource thuộc scope; reference, coordinate và unit có căn cứ.

| Bước | Gửi → Nhận | Nội dung |
|---|---|---|
| M01 | Planner → UI-F | Chọn forecast reference và một location/kỳ/product-grain |
| M02 | UI-F → C-F | Gửi yêu cầu mở form và coordinate |
| M03 | C-F → C-F | Kiểm permission, scope, SoD liên quan |
| M04 | C-F → R-F → C-F | Đọc output gốc và metadata coordinate/unit trong scope |
| M05 | C-F → UI-F → Planner | Trả giá trị gốc, unit, status và form điều chỉnh |
| M06 | Planner → UI-F → C-F | Gửi giá trị mới và lý do |
| M07 | C-F → C-F | Kiểm giá trị hữu hạn/không âm/precision, lý do, reference và quyền hiện hành |
| M08 | C-F → UI-F → Planner | Trình gốc/mới/chênh lệch/unit/lý do để xác nhận |
| M09 | Planner → UI-F → C-F | Xác nhận lưu version riêng |
| M10 | C-F → R-F → C-F | Tạo version điều chỉnh, gắn actor/thời điểm/reference; không sửa output gốc |
| M11 | C-F → R-A → C-F | Ghi audit outcome và before/after |
| M12 | C-F → UI-F → Planner | Báo lưu thành công; default selection vẫn là forecast gốc |

**Nhánh thay thế:** `M03` không đủ quyền/scope → từ chối, không trả dữ liệu ngoài quyền. `M04` thiếu forecast/reference/unit/mapping → báo không đủ căn cứ, không mở thao tác ghi. `M07` input sai → giữ form, không lưu. Quyền bị thu hồi hoặc reference mất hiệu lực trước `M10` → từ chối, không tạo version. Giá trị không đổi → báo không có thay đổi, không tạo version. Persistence thất bại → báo chưa lưu, giữ input; output gốc không đổi.

**Hậu điều kiện:** version chỉ tồn tại khi lưu thành công; model forecast, source facts và metric gốc bất biến. Màn hình đọc mặc định model forecast; người xem chọn bản điều chỉnh tường minh. Không mô tả approval, publish, execution hoặc metric cho adjusted output.
<a id="figures-sequence"></a>

---

<a id="spec-activity"></a>

## Đặc tả Activity — PharmaFlow Sales & Demand Landscape V1

| Thuộc tính | Giá trị |
|---|---|
| Mã | PF-ACT-SALES-DEMAND-LANDSCAPE-V1 |
| Ngày | 2026-11-06 |
| Trạng thái | Proposed — đặc tả trước dựng hình, không phải evidence implementation/deployment |
| Phạm vi | 6 activity tổng quan, 4 activity chi tiết; bao phủ 22 UC qua các hành vi thành phần |
| Nguồn chuẩn | [Use Case Specification](USE_CASE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md), [Requirements](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md), [User Stories](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md) |
| Đối chiếu tương tác | [Sequence Specification](SEQUENCE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md) |

### 1. Ý tưởng và cách tham khảo báo cáo mẫu

Activity trả lời: ai thực hiện hoạt động nào, điều kiện nào quyết định đường đi, đường lỗi kết thúc hoặc quay lại ở đâu. Sequence mô tả trao đổi giữa participant; không chuyển từng message đọc repository thành một activity riêng nếu không có ý nghĩa nghiệp vụ.

Đã tham khảo [OneNigth_report03.pdf](D:/DOWNLOAD/HCMUT/HK251/CNPM/BTL/OneNigth_report03.pdf), chương 7, trang in 127–166 (trang PDF 131–170), phần mô tả tiếp ở trang PDF 171. Đã xem trực tiếp Hình 90 (trang in 127) và Hình 118 (trang in 159). Ý tưởng áp dụng: swimlane người dùng/hệ thống, chia hình theo chức năng/actor, dùng decision cho điều kiện và mô tả bằng lời dưới hình.

Không lấy SSO, cache, export, chia sẻ bộ lọc, thông báo hoặc ngưỡng hiệu năng từ báo cáo mẫu làm yêu cầu PharmaFlow. Một số caption và mô tả gần nhau trong mẫu không khớp chủ đề; căn cứ nội dung W19.10 được ưu tiên khi xây đặc tả.

### 2. Quy ước dựng activity

#### 2.1. Swimlane và các node

| Thành phần | Quy ước |
|---|---|
| Lane người dùng | Người dùng được quyền xem Sales/Forecast (10 role mapping ở Addendum) cho ACT-SD-01–04; Data admin cho ACT-SD-05/07–09; IT admin cho ACT-SD-06/10 |
| Lane hệ thống | PharmaFlow DSS; không bắt buộc tách UI/backend/database thành lane nghiệp vụ |
| Action | Động từ + đối tượng, ví dụ “Kiểm tra tính tương thích” |
| Decision | Câu hỏi cụ thể, nhánh có guard loại trừ nhau, bao gồm thiếu/chưa xác định khi có khả năng |
| Merge | Hợp các đường thay thế khi cần xử lý chung; không đồng nghĩa chờ song song |
| Fork/join | Chỉ dùng khi có căn cứ thực hiện đồng thời; bản này chưa quy định concurrency |
| Initial/final | Bắt đầu/kết thúc một lần thực hiện quy trình, không xóa đối tượng hoặc khóa toàn bộ hệ thống |
| Call activity | Hành vi chi tiết được tham chiếu từ activity tổng quan; không triển khai lại hai lần |

Mã Nxx/Gxx/Exx chỉ có phạm vi trong từng ACT. N là action, G là decision, E là kết quả kết thúc. Bảng đường đi dưới đây là đặc tả control flow; chưa phải mã hình.

#### 2.2. Ràng buộc dùng chung

1. Mọi flow kiểm permission → data scope → SoD liên quan → điều kiện trạng thái trước khi đọc/ghi; từ chối quyền kết thúc ở outcome từ chối và không đi tới thành công. Backend thực thi kiểm tra; không thêm flow login/token/session của dịch vụ xác thực. Khi ghi, kiểm lại quyền/reference và ghi audit theo tab 2. NFR-SD-07; TC-SD-14.
2. Đối với ACT-SD-01–04, hành vi UC-SD-06 luôn được áp dụng khi trình bày: nhãn Sales/Forecast, location/kỳ, đơn vị đã xác nhận, nhãn mô phỏng; missing khác zero. Giữ lineage, cutoff, source/run/model/protocol metadata trong hồ sơ nội bộ.
3. Source facts không thay đổi do thao tác xem/đối soát. Không cộng UOM/grain không tương thích; không biến aggregate thành giao dịch, synthetic thành observed, sales thành latent demand; không đổi demand location thành fulfillment location.
4. Lỗi đọc nguồn khác không có bản ghi. Nếu một phần trả được, thể hiện phần hợp lệ/phần thiếu/phần lỗi riêng; không giả dữ liệu thay thế. Retry thao tác xem chỉ theo flow/quyền đã chốt, không tự thêm retry nền.
5. Không tự train model, chạy backtest, phát hành forecast, lập lệnh mua/chuyển kho hoặc thực thi quyết định. Prediction Quality tách khỏi Decision Quality.
6. Chuỗi toàn dự án `DATA → FORECAST → RISK → DECISION → OPERATIONAL OUTCOME` được giữ; phạm vi này chưa đặc tả toàn bộ các lớp đó. Các recommendation vận hành tương lai vẫn cần human review.

#### 2.3. Thành phần và cách viết từng loại node

Phần này quy định nội dung thực sự được ghi trong hình. Mã N/G/E là mã tra cứu, không thay cho tên node. Đối chiếu ký pháp với [OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/PDF), chương 15 (Activities) và 16 (Actions); báo cáo mẫu là nguồn ý tưởng trình bày, không phải tiêu chuẩn ký pháp.

| Loại thành phần | Hình thức | Nội dung cần viết | Quy tắc vào/ra |
|---|---|---|---|
| Initial node | Chấm tròn đặc | Không ghi action trong chấm; trigger ghi trong mô tả activity | Trong mô hình tuần tự này, một cạnh đi tới bước đầu |
| Action node | Chữ nhật bo góc | Một hành động rõ bằng động từ + đối tượng; actor thể hiện qua lane | Hoàn tất action mới đi tiếp; không dùng hình thoi để mô tả một tác vụ |
| Decision node | Hình thoi | Câu hỏi ngắn hoặc điều kiện cần phân loại | Một dòng điều khiển vào, nhiều đường ra có guard; xét cả chưa biết khi cần |
| Merge node | Hình thoi | Thường không cần tên/hành động bên trong | Hợp nhiều đường thay thế thành một đường ra; không chờ đủ tất cả đường vào |
| Fork/join node | Thanh đậm | Không nhét câu hỏi vào thanh | Fork tách luồng đồng thời; join đồng bộ. Không dùng cho lựa chọn Có/Không; chưa có nhu cầu trong 10 activity này |
| CallBehaviorAction | Action có ký hiệu gọi hành vi con khi renderer hỗ trợ | Tên hành vi và mã ACT tham chiếu | Luồng quay lại activity cha khi hành vi con kết thúc; lane chi tiết nằm trong hình con |
| Activity final | Chấm đặc trong vòng tròn | Không nhét câu “Đã lưu thành công” vào ký hiệu final | Không có cạnh đi ra; kết thúc lần thực hiện activity |
| Flow final | Vòng tròn có dấu X | Chỉ dùng khi cần chấm dứt riêng một nhánh/token | Không tương đương activity final; hiện chưa cần trong bản tuần tự này |
| Object node/object flow | Ô đối tượng và cạnh dữ liệu nếu cần | Tên dữ liệu, ví dụ “Phạm vi location/kỳ”, “Kết luận kiểm định” | Phân biệt dòng dữ liệu với control flow; input/output trong prose không bắt buộc trở thành object node |
| Activity partition | Lane có tên vai trò | Người dùng được quyền xem Sales/Forecast, Data admin, IT admin hoặc PharmaFlow DSS theo hình | Tên lane xác định trách nhiệm, không phải một action hoặc deployment service |
| Note | Ghi chú nối với node/cạnh liên quan | Rule hoặc tham chiếu BR/UC cần giải thích | Không làm thay đổi control flow; không dùng note thay cho nhánh lỗi |

**Cách viết action:** ưu tiên “Chọn location và kỳ”, “Kiểm tra trạng thái run”, “Hiển thị forecast theo location/kỳ”. Không ghi một đoạn thuật toán dài trong một ô; nếu có nhiều quyết định bên trong thì tách action/decision hoặc gọi activity con. Không ghi `do/`, `entry/`, `exit/` vào action node của activity: đó là cách mô tả behavior trong state.

**Cách viết guard:** đặt trên cạnh đi ra decision, ví dụ `[được nguồn hỗ trợ]`, `[không được hỗ trợ]`, `[chưa xác định]`. Guard là điều kiện, không phải tác vụ; “Hiển thị lỗi” là action sau cạnh, không phải guard. Có thể dùng `[else]` cho phần còn lại khi các trường hợp trước đã rõ; không tự đồng nhất chưa xác định với đã xác nhận không hợp lệ. Bản hình W19.10 dùng guard loại trừ nhau để chọn một đường; không dựa vào thứ tự đánh giá guard.

**Cách viết điểm kết thúc:** E01/E02 trong bảng hiện là mã outcome, chưa phải node tròn có chứa chữ. Khi dựng hình, biểu diễn action cuối như “Thông báo không có bản ghi” rồi nối tới activity final; đặt mã outcome ở action/note nếu cần truy vết. Kết thúc call activity chỉ trả điều khiển về cha, không đặt activity final của sơ đồ cha ở giữa luồng.

#### 2.4. Hồ sơ node và quy tắc chuyển bảng thành hình

Mỗi action khi triển khai từ bảng cần có hồ sơ: `ID; loại node; nhãn hiển thị; lane; điều kiện vào; input; output; cạnh ra/đích; nguồn UC/FR/BR`. Decision bổ sung danh sách guard; call activity bổ sung mã hành vi con; final không có output/cạnh ra. Thông tin dài giữ trong Markdown, chỉ đưa nhãn ngắn lên hình.

| Thành phần áp dụng ACT-SD-04 | Nhãn/nội dung trong hình | Điều kiện/dữ liệu và đường đi |
|---|---|---|
| I01 — Initial | Chấm đặc, không chữ | Bắt đầu lần yêu cầu xem; nối N01 |
| N01 — Action, lane Supply Chain | Chọn location và kỳ forecast | Input: phạm vi khả dụng; output: lựa chọn; tới G01 |
| G01 — Decision, lane Hệ thống | Location được hỗ trợ? | Cạnh `[được hỗ trợ]` tới N02; `[không/chưa xác định]` tới action báo không khả dụng rồi final |
| N02 — Action, lane Hệ thống | Tìm output và metadata | Output hiện có tới N03; lỗi tải tới action báo lỗi hoặc xử lý phần lỗi theo NFR-SD-09 |
| G02 — Decision, lane Hệ thống | Output đủ điều kiện? | `[có output hợp lệ]` tới N04; `[thiếu/chưa hợp lệ/chưa hoàn tất]` tới N05 |
| N04 — Action, lane Hệ thống | Chuẩn bị giá trị, unit đã xác nhận, nhãn mô phỏng; thêm cặp hợp lệ vào tập kết quả | Không hiển thị metadata run; unit/synthetic theo contract |
| N05 — Action, lane Hệ thống | Ghi chưa có forecast cho cặp đó vào tập kết quả | Không điền zero; giữ lý do kỹ thuật nội bộ |
| M06 — Merge, lane Hệ thống | Không cần chữ bên trong | Hợp kết quả của cặp hiện tại từ N04/N05 trước G03; không dùng join |
| N06 — Action, lane Hệ thống | Hoàn tất và hiển thị tập kết quả | Giữ phần hợp lệ/thiếu/lỗi riêng; không cộng location ngầm định |
| N07 — Action, lane Supply Chain | Đọc kết quả theo location/kỳ | Kết thúc đọc nối final; không tạo quyết định tồn kho |
| F01 — Activity final | Chấm đặc trong vòng tròn | Kết thúc lần xem, không thay đổi model/output nguồn |

Vòng N03–G02–N04/N05–M06 được điều khiển bởi G03: kiểm tra còn cặp chưa xử lý, xét một cặp, thêm kết quả hợp lệ hoặc trạng thái thiếu vào tập, rồi quay lại N03 nếu còn cặp; chỉ khi hết tập mới tới N06 để trình bày toàn bộ. Đây là lặp logic, không quy định query per item hay concurrency.

**Các merge bắt buộc làm rõ khi vẽ:** ACT-SD-01 trước N06; ACT-SD-03 trước điểm kết thúc chung nếu hai nhánh cùng kết thúc; ACT-SD-04 trước G03; ACT-SD-05 trước N06; ACT-SD-06 trước N06; ACT-SD-07 trước N05/E01 khi các đường thay thế cùng hội tụ; ACT-SD-08 trước kết quả trả về E01. Các vòng nhập lại ACT-SD-02/N01, ACT-SD-09/N02 và ACT-SD-10/N01 cũng hợp đường vào bằng merge. Bảng hiện rút gọn các điểm hợp luồng này; không nối nhiều cạnh thay thế trực tiếp vào một action theo cách tạo ngữ nghĩa chờ đồng thời. Hai nhánh có final riêng không cần merge chỉ để trang trí.

Các dòng ghi `Data admin + Hệ thống` hoặc `IT admin + Hệ thống` là call activity tổng quan. Khi phân rã, không tạo lane gộp hai chủ thể; từng action trong hình con phải thuộc lane thực hiện nó. Tác vụ kiểm tra và decision kết quả là hai thành phần khác nhau nếu cần thể hiện đầy đủ: action “Kiểm tra quyền” rồi decision “Có quyền?”; không biến decision thành công việc tính quyền.

### 3. Nhóm người dùng được quyền xem Sales/Forecast

#### ACT-SD-01 — Theo dõi Sales Quantity

**Truy vết:** UC-SD-01/06; US-SD-LS-01/06; FR-SD-01/06; SEQ-SD-01; BR-SD-01–06/09; TC-SD-01/02/04/05/12/13/15.

**Trigger:** Người dùng được quyền xem Sales/Forecast mở theo dõi Sales. **Điều kiện trước:** có quyền theo phạm vi áp dụng, nhận diện được nguồn/contract; thiếu metadata được biểu diễn riêng. **Input:** kỳ, chiều/bộ lọc khả dụng. **Output:** Sales Quantity hoặc trạng thái theo phạm vi.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Người dùng được quyền xem Sales/Forecast | Mở chức năng và chọn kỳ/chiều | G01 |
| G01 | Hệ thống | Chiều có được nguồn hỗ trợ? | Có: N02; không/chưa rõ: E01 |
| N02 | Hệ thống | Đọc observation, UOM/grain/coverage/provenance | G02; lỗi tải: E02 |
| G02 | Hệ thống | Có bản ghi trong phạm vi? | Có: N03; không: E03 |
| N03 | Hệ thống | Kiểm tra điều kiện tổng hợp, metadata và nghĩa location | G03 |
| G03 | Hệ thống | Đủ điều kiện cho phép tính yêu cầu? | Có: N04; thiếu: N05 |
| N04 | Hệ thống | Tổng hợp theo rule/UOM/grain đã xác nhận | N06 |
| N05 | Hệ thống | Giữ phần có căn cứ, đánh dấu chưa xác định; không tính phần thiếu điều kiện | N06 |
| N06 | Hệ thống | Trình bày Sales và ngữ cảnh UC-SD-06 | N07 |
| N07 | Người dùng được quyền xem Sales/Forecast | Đọc kết quả và giới hạn | E04 |

**Kết thúc:** E01 chiều không khả dụng, không dựng chiều thay thế (UC-SD-01/2a); E02 không tải được (4a); E03 không có bản ghi, khác quantity zero (3a); E04 đã trình bày kết quả/phần chưa xác định (3b). Người dùng có thể gửi lựa chọn mới thành lần xem khác; không tự chạy vòng lặp vô hạn.

**Hậu điều kiện:** không đổi facts; không nhận provenance chưa rõ là actual đã kiểm chứng. **Đối chiếu hình:** nhánh zero phải đi qua dữ liệu có bản ghi; không đi từ no record đến giá trị 0.

#### ACT-SD-02 — So sánh Sales Quantity

**Truy vết:** UC-SD-02/02.1/06; US-SD-LS-02/06; FR-SD-02/06; SEQ-SD-02; BR-SD-03/04/06; TC-SD-03/13.

**Trigger:** chọn so sánh. **Input:** các đối tượng/kỳ và measure. **Điều kiện trước:** quyền đọc, có metadata để kiểm tra hoặc ghi thiếu. **Output:** tập so sánh hợp lệ, chênh lệch/thứ hạng và giới hạn.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Người dùng được quyền xem Sales/Forecast | Chọn các đối tượng/kỳ | G01 |
| G01 | Hệ thống | Ít nhất hai đối tượng/kỳ? | Có: N02; không: N05 |
| N02 | Hệ thống | Đọc chuỗi và metadata; đối chiếu measure/UOM/grain/coverage theo UC-SD-02.1 | G02; lỗi: E01 |
| G02 | Hệ thống | Có tập đủ điều kiện so sánh trực tiếp? | Có: N03; không: E02 |
| N03 | Hệ thống | Giữ riêng chuỗi không tương thích, ghi lý do/cảnh báo coverage; tính trên tập đủ điều kiện | N04 |
| N04 | Hệ thống | Hiển thị tập, kỳ, đơn vị, phạm vi và kết quả với UC-SD-06 | E03 |
| N05 | Hệ thống | Yêu cầu chọn thêm hoặc quay về theo dõi | G03 |
| G03 | Người dùng được quyền xem Sales/Forecast | Chọn thêm đối tượng/kỳ? | Có: N01; không: E04 |

**Ngoại lệ:** khác measure/UOM/grain hoặc thiếu metadata: không so sánh trực tiếp (UC-SD-02/3a; UC-SD-02.1/2a,3a). Coverage thiếu/khác đáng kể: nêu giới hạn, nếu chưa đủ căn cứ thì G02 trả không (UC-SD-02/3b). Cần aggregation nhưng chưa có rule: giữ riêng, không tự cộng (4a). Không có ngưỡng coverage cố định được ngầm áp dụng.

**Kết thúc:** E01 lỗi tải; E02 chưa so sánh được kèm lý do; E03 đã trình bày; E04 quay lại theo dõi. **Hậu điều kiện:** không xếp hạng chuỗi không tương thích, không gọi high/low là tốt/xấu kinh doanh khi chưa có mục tiêu.

#### ACT-SD-03 — Xu hướng và biểu hiện mùa vụ

**Truy vết:** UC-SD-03/03.1/06; US-SD-LS-03/06; FR-SD-03/06; SEQ-SD-03; TC-SD-11/12/13.

**Trigger:** yêu cầu xem lịch sử. **Input:** series/measure/khoảng thời gian. **Điều kiện trước:** quyền và nguồn lịch sử có thể kiểm tra. **Output:** lịch sử và phần mùa vụ đủ căn cứ.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Người dùng được quyền xem Sales/Forecast | Chọn series, measure và kỳ | N02 |
| N02 | Hệ thống | Đọc chuỗi và coverage/provenance | N03; lỗi: E01 |
| N03 | Hệ thống | Kiểm tính liên tục, missing period và số chu kỳ | N04 |
| N04 | Hệ thống | Hiển thị lịch sử có căn cứ và khoảng trống, áp dụng UC-SD-06 | G01 |
| G01 | Hệ thống | Coverage/chu kỳ/provenance và phương pháp đã xác nhận đủ cho mùa vụ? | Có: N05; không/chưa rõ: N06 |
| N05 | Hệ thống | Bổ sung biểu hiện mùa vụ kèm chu kỳ/phạm vi evidence theo UC-SD-03.1 | E02 |
| N06 | Hệ thống | Ghi chưa đủ căn cứ hoặc phương pháp chưa xác nhận; giữ lịch sử | E03 |

**Ngoại lệ:** UC-SD-03/3a,3b,5a và UC-SD-03.1/2a,2b cùng dẫn tới N06 khi ảnh hưởng căn cứ mùa vụ. Không tự đặt thuật toán/ngưỡng số tháng. E01 lỗi tải khác thiếu coverage; E02 có thông tin mùa vụ đủ căn cứ; E03 chỉ có lịch sử/cảnh báo. **Hậu điều kiện:** không đổi sales history thành demand history hoặc suy lost demand.

#### ACT-SD-04 — Xem forecast theo location/kỳ

**Truy vết:** UC-SD-04/06; US-SD-LS-04/06; FR-SD-04/06; SEQ-SD-04; TC-SD-06/07/12/13/15.

**Trigger:** yêu cầu xem forecast. **Input:** một/nhiều location và kỳ. **Điều kiện trước:** scope quyền phù hợp và source/run contract nhận diện output. **Output:** giá trị/trạng thái riêng từng cặp location/kỳ.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Người dùng được quyền xem Sales/Forecast | Chọn location/kỳ được hỗ trợ | G01 |
| G01 | Hệ thống | Location có trong phạm vi nguồn/run hỗ trợ? | Có: N02; không: E01 |
| N02 | Hệ thống | Tìm output và metadata nội bộ | N03; lỗi: E02 |
| N03 | Hệ thống | Xét điều kiện cho từng cặp location/kỳ trong phạm vi yêu cầu | G02 |
| G02 | Hệ thống | Có output và đủ điều kiện hợp lệ theo contract? | Có: N04; không/chưa hoàn tất: N05 |
| N04 | Hệ thống | Chuẩn bị giá trị, unit đã xác nhận, nhãn mô phỏng; thêm cặp hợp lệ vào tập kết quả | M06 |
| N05 | Hệ thống | Ghi chưa có forecast cho cặp đó vào tập kết quả; giữ lý do kỹ thuật nội bộ | M06 |
| M06 | Hệ thống | Merge kết quả của cặp hiện tại từ N04/N05 | G03 |
| G03 | Hệ thống | Còn location/kỳ chưa xử lý? | Còn: N03; hết tập: N06 |
| N06 | Hệ thống | Hoàn tất tập kết quả, giữ riêng phần hợp lệ/thiếu/lỗi; áp dụng UC-SD-06 | N07 |
| N07 | Người dùng được quyền xem Sales/Forecast | Đọc kết quả theo từng location/kỳ | E03 |

G03 điều khiển vòng lặp theo cặp location/kỳ: mỗi lượt xử lý một cặp logic và thêm kết quả/trạng thái vào tập; khi còn cặp quay lại N03, khi hết mới tới N06. Đây là điều khiển logic; không yêu cầu query riêng per item hoặc xử lý song song.

**Ngoại lệ:** location không hỗ trợ → E01 (UC-SD-04/2a); thiếu output → N05 (3a); run chưa hợp lệ/hoàn tất → N05 (3b); unit chưa rõ → N04 chỉ hiện phần biết được, ghi chưa xác định/ẩn unit (4a); synthetic → nhãn mô phỏng (4b). E02 lỗi tải; nếu chỉ lỗi một phần thì giữ phần còn lại theo NFR-SD-09. E03 đã trình bày. **Hậu điều kiện:** không cộng ngầm định location, không train/chạy lại model, không công bố output thiếu điều kiện.

### 4. Nhóm Data admin

#### ACT-SD-05 — Đối soát và kiểm định forecast tổng thể

**Truy vết:** UC-SD-05/08/09/10; US-SD-LS-05; FR-SD-05; SEQ-SD-05; TC-SD-08/09/10/17.

**Trigger:** mở hồ sơ kiểm định. **Input:** snapshot/run/evaluation reference. **Điều kiện trước:** quyền truy cập, nhận diện hồ sơ; metadata chưa có được ghi thiếu. **Output:** kết luận có evidence hoặc chưa lưu.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Data admin | Chọn hồ sơ cần kiểm định | N02 |
| N02 | Hệ thống | Nạp hồ sơ và trình phần có/thiếu | N03; lỗi dịch vụ cản trở: E01 |
| N03 | Data admin + Hệ thống | Thực hiện đối soát ACT-SD-07 | G01 |
| G01 | Hệ thống | Đối soát và protocol đủ điều kiện mở phần evaluation? | Có: N04; không/chưa rõ: N05 |
| N04 | Data admin + Hệ thống | Kiểm temporal validity và comparability theo ACT-SD-08 | N06 |
| N05 | Hệ thống | Giữ lý do invalid/chưa đánh giá được, không diễn giải score như hợp lệ | N06 |
| N06 | Data admin + Hệ thống | Hợp đường evaluation có/không đủ điều kiện; ghi kết luận theo ACT-SD-09 | G02 |
| G02 | Hệ thống | Lưu thành công? | Có: E02; không: E03 |

Các dòng “Data admin + Hệ thống” là call activity; khi dựng hình chi tiết phải tách action vào đúng lane. Không dùng join tại N06: chỉ một đường lựa chọn đi tới merge.

**Ngoại lệ:** metadata thiếu → đánh dấu và xét gate theo ảnh hưởng (UC-SD-05/2a); dữ liệu lỗi → N05 (3a); protocol/phạm vi không tương thích → N05 (4a); leakage/run chưa hoàn tất → N05 (4b); coverage metric thiếu → N06; nếu có giá trị metric nguồn, hiển thị nguyên số kèm nhãn “Chưa đánh giá được”; không tính score mới (5a). Lỗi lưu → E03 (7a). E01: chuyển IT với reference có sẵn, không tự restart, không khẳng định kết luận đã lưu (7b).

**Hậu điều kiện:** E02 có kết luận lưu thành công, có thể là invalid/chưa đánh giá được; E03 chưa lưu. Không suy Decision Quality từ forecast error; không tự phát hành forecast sau kiểm định.

#### ACT-SD-07 — Đối soát dữ liệu đầu vào

**Truy vết:** UC-SD-08/08.1/08.2/08.3; FR-SD-05; SEQ-SD-07; TC-SD-17. **Ngữ cảnh:** call từ ACT-SD-05/N03. **Input:** nguồn/snapshot/contract. **Output:** kết quả từng hạng mục và ảnh hưởng tới evaluation.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Hệ thống | Đọc nguồn/snapshot/version/contract | G01 |
| G01 | Hệ thống | Có nguồn và contract cần thiết? | Có: N02; không: N06 |
| N02 | Data admin | Đối chiếu nguồn và snapshot, ghi thiếu version nếu có | N03 |
| N03 | Data admin | Đối chiếu UOM/location với định nghĩa contract, ghi phù hợp/không khớp/chưa rõ | G02 |
| G02 | Hệ thống | Contract có grain/kỳ/phạm vi mong đợi để kiểm coverage? | Có: N04; không: N05 |
| N04 | Hệ thống | Tổng hợp coverage/missing/duplicate theo contract, không sửa nguồn | N05 |
| N05 | Data admin | Xác nhận kết quả, phần thiếu và mức ảnh hưởng | E01 |
| N06 | Hệ thống | Ghi thiếu nguồn/contract; dừng kiểm tra phụ thuộc | E01 |

**Nhánh:** thiếu snapshot/contract: UC-SD-08/2a, UC-SD-08.1/2a; thiếu version: UC-SD-08.1/3a; UOM/mapping không rõ hoặc lệch: UC-SD-08/3a, UC-SD-08.2/1a,2a; thiếu phạm vi mong đợi: UC-SD-08.3/1a; missing/duplicate/coverage lệch: UC-SD-08/3b, UC-SD-08.3/2a. Không đủ điều kiện: trả invalid/not assessable theo evidence, UC-SD-08/5a.

**Hậu điều kiện E01:** trả kết quả đối soát cho gate ACT-SD-05/G01; không tự loại bản ghi, impute zero, sửa UOM hoặc tạo mapping. Định nghĩa duplicate và ngưỡng đạt còn cần contract.

#### ACT-SD-08 — Kiểm tra và so sánh evaluation

**Truy vết:** UC-SD-09/09.1/09.2; FR-SD-05, Requirements §4.2; SEQ-SD-08; TC-SD-08/09/10/17. **Trigger:** ACT-SD-05/G01 cho phép tiếp tục. **Input:** forecast/baseline/actuals và protocol metadata. **Output:** trạng thái temporal/comparability, metric đọc được và căn cứ.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Hệ thống | Nạp metadata/evidence theo origin, trạng thái run và metric definition | G01 |
| G01 | Hệ thống | Đủ metadata cần kiểm và run/actuals sẵn sàng? | Có: N02; không/chưa rõ: N06 |
| N02 | Data admin | Kiểm mỗi origin chỉ dùng thông tin trước origin; ghi evidence | G02 |
| G02 | Data admin | Temporal validity có đủ căn cứ? | Có: N03; leakage: N05; chưa rõ: N06 |
| N03 | Hệ thống | Đối chiếu target/grain/UOM/horizon/origins/actuals/protocol/evaluation period | G03 |
| G03 | Hệ thống | Forecast và baseline tương thích, metric đủ định nghĩa/coverage? | Có: N04; không/chưa rõ: N06 |
| N04 | Data admin | Đọc metric/phạm vi và xem xét Prediction Quality | E01 |
| N05 | Hệ thống | Ghi run invalid cho kết luận chất lượng; không diễn giải score hợp lệ | E01 |
| N06 | Hệ thống | Nếu có giá trị metric nguồn, hiển thị nguyên số kèm nhãn “Chưa đánh giá được”; không tính số mới/xếp hạng. Nếu không có số, chỉ hiển thị trạng thái thiếu căn cứ/không so sánh được | E01 |

**Nguồn nhánh:** UC-SD-09/2a–5a; UC-SD-09.1/1a,2a; UC-SD-09.2/1a,2a. N05 khác N06: vi phạm đã có evidence khác thiếu bằng chứng để đánh giá. E01 trả ACT-SD-05/N06 để DA ghi kết luận. **Hậu điều kiện:** không sửa score hoặc chạy lại model; nếu N06 có giá trị metric nguồn thì vẫn hiển thị số kèm nhãn “Chưa đánh giá được”; không tính score mới/thay thế hoặc xếp hạng. MAE/RMSE/WAPE/Bias là ứng viên cần chốt, không tự gán metric thắng.

#### ACT-SD-09 — Ghi và lưu kết luận kiểm định

**Truy vết:** UC-SD-10/10.1; FR-SD-05; SEQ-SD-09; TC-SD-17. **Trigger:** ACT-SD-05/N06. **Input:** kết quả đối soát/evaluation, trạng thái/nhận xét/căn cứ, evidence references. **Output:** kết luận đã lưu hoặc chưa lưu.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Hệ thống | Trình bày kết quả và bằng chứng còn thiếu | N02 |
| N02 | Data admin | Chọn trạng thái phù hợp, nhập căn cứ và gắn reference hiện có | G01 |
| G01 | Hệ thống | Đủ trạng thái/căn cứ bắt buộc và reference được xác nhận theo policy? | Có: N04; không: N03 |
| N03 | Hệ thống | Nêu trường thiếu/reference cần xác nhận lại | N02 khi DA bổ sung |
| N04 | Hệ thống | Ghi rõ mức đầy đủ evidence, gắn actor/thời điểm và lưu kết luận | G02 |
| G02 | Hệ thống | Nhận kết quả lưu thành công? | Có: E01; không: E02 |

**Ngoại lệ:** evaluation không đủ điều kiện vẫn được chọn kết luận invalid/chưa đánh giá được, UC-SD-10/2a. Thiếu evidence khác reference không hợp lệ: ghi thiếu và không nhận truy vết đầy đủ (UC-SD-10/4a; UC-SD-10.1/1a), reference không hợp lệ cần xác nhận lại (UC-SD-10.1/2a); không tự đặt điều kiện mọi evidence đều đầy đủ mới được lưu. Trường bắt buộc thiếu: UC-SD-10/5a. Lỗi lưu: UC-SD-10/6a.

**Hậu điều kiện:** E01 chỉ sau xác nhận lưu; E02 báo chưa lưu và giữ nguyên facts/actuals/score. N03 là vòng bổ sung do người dùng thao tác, không tự sửa nội dung. Rời biểu mẫu/lưu nháp/hủy chưa có policy thì không tự thêm transition hoặc cam kết giữ nội dung.

### 5. Nhóm IT admin

#### ACT-SD-06 — Theo dõi vận hành

**Truy vết:** UC-SD-07/11/11.1/11.2/12; US-SD-LS-07; FR-SD-09; SEQ-SD-06; TC-SD-14/16. **Trigger:** IT chọn dịch vụ/job/khoảng lịch. **Điều kiện trước:** quyền xem áp dụng. **Input/output:** phạm vi vận hành → trạng thái, lịch, timestamp, phần thiếu/cũ và log tùy yêu cầu.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | IT admin | Chọn phạm vi | N02 |
| N02 | Hệ thống | Đọc job/status/lịch/timestamp | G01; lỗi đọc: E01 |
| G01 | Hệ thống | Có job phù hợp? | Có: N03; không: E02 |
| N03 | Hệ thống | Hiển thị từng trạng thái/độ mới, phần telemetry/lịch chưa có | N04 |
| N04 | IT admin | Xem và phân loại vấn đề vận hành | G02 |
| G02 | IT admin | Cần tra cứu log chi tiết? | Có: N05; không: N06 |
| N05 | IT admin + Hệ thống | Thực hiện ACT-SD-10 | N06 |
| N06 | IT admin | Ghi nhận vấn đề; nếu thuộc dữ liệu/model thì chuyển Data admin theo quy trình | E03 |

**Nhánh dữ liệu vận hành:** thiếu telemetry/lịch → ghi chưa biết/chưa cung cấp; cũ → timestamp cuối và cảnh báo, không tự nhận thành công (UC-SD-07/3a; UC-SD-11/3a,4a; UC-SD-11.1/2a,3a; UC-SD-11.2/2a,3a). Không có job → E02 (UC-SD-07/2a; UC-SD-11/2a). Cần quyền restart/thay lịch chưa chốt → chỉ ghi nhu cầu, không thực thi (UC-SD-07/4b). Vấn đề model → DA (4a).

**Hậu điều kiện:** E01 lỗi đọc riêng với chưa có telemetry; E02 không có job; E03 đã xem/ghi nhận theo scope. Không tự tạo ticket/email integration, đổi lịch, retry job hay kết luận model thay DA.

#### ACT-SD-10 — Tra cứu log theo job/run

**Truy vết:** UC-SD-12; FR-SD-09; SEQ-SD-10; TC-SD-14/16. **Trigger:** ACT-SD-06/G02 chọn có. **Input:** job/run ID và phạm vi được phép. **Output:** log được phép xem hoặc trạng thái từ chối/không có/lỗi đọc.

| Node | Lane | Hoạt động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | IT admin | Chọn/xác nhận job/run ID | G01 |
| G01 | Hệ thống | ID có hợp lệ trong phạm vi? | Có: G02; không: N02 |
| N02 | Hệ thống | Yêu cầu chọn lại từ danh sách khả dụng | N01 khi IT chọn lại |
| G02 | Hệ thống | Có quyền đọc log theo policy? | Có: N03; không: E01 |
| N03 | Hệ thống | Tra cứu log | G03; lỗi đọc: E02 |
| G03 | Hệ thống | Có dữ liệu log? | Có: N04; không: E03 |
| N04 | Hệ thống | Che/loại credentials và sensitive values theo policy trước hiển thị; ghi nhận sự cố bảo mật nếu có | N05 |
| N05 | IT admin | Đọc, phân loại; vấn đề dữ liệu/model chuyển DA theo quy trình | E04 |

**Nguồn nhánh:** UC-SD-12/2a,3a,3b,4a,5a. E01 từ chối và ghi nhận kiểm tra quyền theo policy; E02 lỗi truy cập; E03 không có log, không chứng minh run thành công; E04 đã xem. Các điểm kết thúc của activity con trả về ACT-SD-06/N06, không dừng toàn bộ quy trình cha. **Hậu điều kiện:** không đổi job state, source facts hoặc kết luận kiểm định.

### 6. Bao phủ, review và điều kiện dựng hình

| Nhóm UC | Activity | Sequence |
|---|---|---|
| UC-SD-01, UC-SD-06 | ACT-SD-01 và §2.2 | SEQ-SD-01 |
| UC-SD-02, UC-SD-02.1, UC-SD-06 | ACT-SD-02 và §2.2 | SEQ-SD-02 |
| UC-SD-03, UC-SD-03.1, UC-SD-06 | ACT-SD-03 và §2.2 | SEQ-SD-03 |
| UC-SD-04, UC-SD-06 | ACT-SD-04 và §2.2 | SEQ-SD-04 |
| UC-SD-05, UC-SD-08, UC-SD-09, UC-SD-10 | ACT-SD-05 | SEQ-SD-05 |
| UC-SD-07, UC-SD-11, UC-SD-11.1, UC-SD-11.2, UC-SD-12 | ACT-SD-06 | SEQ-SD-06 |
| UC-SD-08, UC-SD-08.1, UC-SD-08.2, UC-SD-08.3 | ACT-SD-07 | SEQ-SD-07 |
| UC-SD-09, UC-SD-09.1, UC-SD-09.2 | ACT-SD-08 | SEQ-SD-08 |
| UC-SD-10, UC-SD-10.1 | ACT-SD-09 | SEQ-SD-09 |
| UC-SD-12 | ACT-SD-10 | SEQ-SD-10 |

Checklist trước vẽ: mỗi action đúng lane; mọi decision có đường thiếu/chưa rõ khi cần; mọi nhánh có đích; lỗi không đi vào thông báo thành công; không dùng fork/join cho lựa chọn; kết thúc activity con trả đúng activity cha; không thêm hủy/retry/timeouts/quyền chưa xác nhận. Khi dựng hình, theo skill diagram-design của dự án, thống nhất style/layout trước render; tài liệu này chưa tạo hình.

Các quyết định còn mở dùng chung [Sequence Specification §14.2](SEQUENCE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md): contract dữ liệu, coverage/seasonality, output selection, evaluation protocol/metric, trạng thái kiểm định, enforcement triển khai, log/telemetry, persistence và retry. Policy role/scope/SoD/audit đã theo tab 2; không ngầm khóa baseline từ bản đặc tả này.

### Addendum — access control và ACT-SD-11 (2026-11-07)

#### Phân quyền activity chung

Các action đọc Sales/Forecast dùng actor “Người dùng được quyền xem Sales/Forecast” và kiểm `sales:read` hoặc `forecast:read` cùng scope assignment. Danh sách role MD-01: US-01, 02, 03, 04, 06, 07, 11, 12, 14, 15. Planner có thêm `forecast:adjust`; Data Admin chỉ đọc/ghi hồ sơ evaluation kỹ thuật; IT Admin chỉ đọc job/log trong quyền vận hành. Mọi flow đọc kiểm permission và scope trước khi tải/trình dữ liệu. Flow ghi kiểm thêm SoD liên quan và kiểm lại permission/reference ngay trước persistence. Từ chối quyền kết thúc ở outcome lỗi được phép hiển thị; không đi vào outcome thành công. Audit ghi actor, permission, resource, outcome và thời điểm; ghi before/after khi lưu. Location chưa có mapping nội bộ được xác nhận không được dùng để nới scope.

#### ACT-SD-11 — Điều chỉnh một giá trị forecast

**Lane:** Supply Chain Planner; Hệ thống. **Trigger:** Planner yêu cầu điều chỉnh một forecast đã có. **Điều kiện trước:** quyền đọc/điều chỉnh và scope phù hợp; output gốc, coordinate location/kỳ/product-grain và unit nhận diện được.

| Node | Lane | Hành động/điều kiện | Đi tiếp |
|---|---|---|---|
| N01 | Supply Chain Planner | Chọn forecast và một coordinate cần điều chỉnh | G01 |
| G01 | Hệ thống | Có `forecast:read`, `forecast:adjust` và đúng scope? | Có: N02; không: E01 |
| N02 | Hệ thống | Đọc model output/reference và unit trong scope | G02 |
| G02 | Hệ thống | Reference, coordinate, unit và mapping có căn cứ? | Có: N03; không: E02 |
| N03 | Supply Chain Planner | Nhập một giá trị mới và lý do | G03 |
| G03 | Hệ thống | Giá trị hữu hạn, không âm, precision hợp lệ, lý do đủ? | Có: N04; không: E03 |
| N04 | Hệ thống | Trình forecast gốc/mới/chênh lệch/unit/lý do | N05 |
| N05 | Supply Chain Planner | Xác nhận lưu version riêng | G04 |
| G04 | Hệ thống | Quyền còn hiệu lực, reference còn hợp lệ và có thay đổi? | Có thay đổi: N06; bị thu hồi/reference lỗi: E04; không đổi: E05 |
| N06 | Hệ thống | Lưu adjusted version, actor/thời điểm/reference và audit | G05 |
| G05 | Hệ thống | Persistence thành công? | Có: N07; không: E06 |
| N07 | Hệ thống | Báo lưu; giữ model forecast làm lựa chọn mặc định, adjusted version riêng sẵn để xem | N08 |
| E01–E04, E06 | Hệ thống | Từ chối quyền, thiếu căn cứ, input sai, mất quyền hoặc persistence failure; không tạo version | Kết thúc lỗi |
| E05 | Hệ thống | Giá trị không đổi; không tạo version, model output giữ nguyên | Kết thúc không đổi |
| N08 | Supply Chain Planner | Chọn model/adjusted version để xem nếu cần; không đổi mặc định sử dụng ở module khác | Kết thúc thành công |

**Hậu điều kiện:** không tạo version nếu nhánh lỗi hoặc giá trị không đổi; không sửa forecast gốc/source facts/score. Không có approval, publish hay execution.
<a id="figures-activity"></a>

---

<a id="spec-state"></a>

## Đặc tả State — PharmaFlow Sales & Demand Landscape V1

| Thuộc tính | Giá trị |
|---|---|
| Mã | PF-STATE-SALES-DEMAND-LANDSCAPE-V1 |
| Ngày | 2026-11-06 |
| Trạng thái | Proposed — mô hình trạng thái tương tác, chưa phải enum/schema/workflow đã triển khai |
| Nguồn nghiệp vụ | [Use Cases](USE_CASE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md), [Requirements](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md), [User Stories](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md) |
| Đối chiếu | [Sequence Specification](SEQUENCE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md), [Activity Specification](ACTIVITY_SPEC_SALES_DEMAND_LANDSCAPE_V1.md) |
| Phạm vi | 3 state machine ứng viên: yêu cầu xem kết quả, phiên kiểm định, lần gửi lưu kết luận; bảng điều kiện riêng cho chất lượng/khả dụng/telemetry |

### 1. Ý tưởng từ báo cáo mẫu và giới hạn áp dụng

Đã tham khảo [OneNigth_report03.pdf](D:/DOWNLOAD/HCMUT/HK251/CNPM/BTL/OneNigth_report03.pdf), chương 8, trang in 167–179 (trang PDF 171–183). Đã xem trực tiếp Hình 124–125 ở trang in 168 và Hình 134–135 ở trang in 172. Mẫu tổ chức state chart theo nhóm vai trò/chức năng; nhiều node mô tả trạng thái tương tác giao diện và có nhãn hành vi `do/`.

Áp dụng cách mô tả trạng thái tương tác khi chưa có lifecycle entity bền vững được xác nhận. Mỗi hình PharmaFlow phải nêu rõ chủ thể, phạm vi một lần thực hiện và ý nghĩa transition; không gọi mọi bước xử lý là trạng thái của forecast/model. Không chuyển lifecycle đăng ký Tutor, tài khoản, lịch hẹn, SSO hoặc quyền quản trị của mẫu thành yêu cầu PharmaFlow.
State trả lời “một chủ thể đang ở trạng thái nào, sự kiện và điều kiện nào cho phép đổi trạng thái”. Activity trả lời “bước tiếp theo của công việc là gì”. Không cần một state diagram cho mỗi oval UC hoặc một state cho mỗi message.

### 2. Chọn chủ thể và tách các trục trạng thái

| Chủ thể/khái niệm | Cách mô tả trong bản này | Lý do |
|---|---|---|
| Một yêu cầu xem kết quả | ST-SD-01, trạng thái tạm thời của yêu cầu | Có gửi yêu cầu, đọc, kiểm tra và trả kết quả/lỗi |
| Một phiên kiểm định | ST-SD-02, tiến trình tương tác của DA | Có đối soát, gate evaluation, ghi kết luận và kết quả lưu |
| Một lần gửi lưu kết luận | ST-SD-03, trạng thái tạm thời của lần gửi | Cần phân biệt không đạt validation, lưu thành công và thất bại |
| Chất lượng đầu vào/evaluation | Bảng điều kiện §6; giá trị gắn với scope/evidence | Invalid và not assessable khác nhau, không mặc định có quy tắc chuyển qua lại |
| Khả dụng forecast theo location/kỳ | Bảng điều kiện §6 | Có/thiếu/không hợp lệ là kết quả kiểm tra output, chưa có lifecycle tạo/phát hành |
| Job/run execution | Chỉ đọc telemetry theo UC-SD-07/11/12 | Chưa có scheduler contract để chốt queued/running/retry/cancel lifecycle |
| Kết luận đã lưu | Kết quả persistence; không tự có draft/approved/published/archived | Chưa chốt sửa/version/retention hoặc approval publication |

Các tên ST và state dưới đây là **Design proposal suy ra từ hành vi đã đặc tả**. Chưa tạo entity, DB status column, API hoặc tự động hóa. Không yêu cầu lưu từng trạng thái tạm thời vào database.

#### 2.1. Quy ước transition

Mỗi transition ghi `event [guard] / action`. Sự kiện là điều quan sát được; guard kiểm điều kiện; action là tác động khi chuyển. Không đủ evidence không đồng nghĩa phát hiện vi phạm. Initial/final chỉ giới hạn một lần tương tác, không có nghĩa đối tượng nguồn bị tạo/xóa.

Các transition không có trong bảng chưa được định nghĩa trong mô hình đề xuất, không đồng nghĩa tất cả đều bị business cấm. Bảng “không được suy diễn” bên dưới phân biệt invariant có căn cứ với policy còn TBD. Không thêm tự động retry, timeout, cancel, restart hoặc reopen.

#### 2.2. Thành phần bên trong state node và trên transition

Đối chiếu ký pháp với [OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/PDF), §14.2.3.4.3 và phần ký pháp StateMachines trong chương 14. Một state đơn có tên và có thể có ngăn behavior; không bắt buộc state nào cũng đủ entry/do/exit.

| Thành phần | Vị trí và cách viết | Ý nghĩa/cách áp dụng |
|---|---|---|
| State name | Ngăn tên phía trên, ví dụ `Đang đọc dữ liệu` | Mô tả tình trạng của đúng chủ thể; ID V2/K2/L2 dùng truy vết, không thay tên |
| `entry / behavior` | Ngăn behavior dưới tên | Hành vi khi vào state; chỉ ghi khi thực sự có hành vi riêng cần thể hiện |
| `do / behavior` | Cùng ngăn behavior | Hành vi diễn ra khi state đang active; có thể hoàn tất hoặc bị dừng khi rời state |
| `exit / behavior` | Cùng ngăn behavior | Hành vi khi rời state; không tự thêm xóa dữ liệu, cleanup, rollback hoặc ghi audit chưa có yêu cầu |
| Internal transition | Trong ngăn behavior, nếu cần | Phản ứng sự kiện không rời state; khác self-transition bên ngoài. Chưa có nhu cầu được đặc tả riêng trong bản này |
| Transition | Cạnh có hướng giữa state | Nhãn `trigger [guard] / effect`; bỏ phần không áp dụng, không điền cho đủ mẫu |
| Initial pseudostate | Chấm đặc | Mũi tên khởi tạo không có trigger/guard; điều kiện bắt đầu ghi ngoài hình hoặc trước khi khởi tạo machine |
| Final state | Chấm đặc trong vòng tròn | Kết thúc region/phạm vi machine; không chứa entry/do/exit, không có cạnh đi ra |

**Mẫu nội dung node, không phải mã diagram:**

```text
V2 — Đang đọc dữ liệu
-------------------
do / Đọc dữ liệu và metadata trong phạm vi yêu cầu
```

Trong ví dụ này không có entry/exit riêng nên bỏ hai dòng đó. Dấu gạch phân ngăn là ký hiệu minh họa văn bản, khi vẽ dùng compartment của state. Không đặt toàn bộ câu “do / đọc dữ liệu…” làm tên state như một action box.

**Mẫu nhãn cạnh:** `Nhận phản hồi nguồn [truy vấn hoàn tất] / Chuyển kết quả sang kiểm tra`. Phân biệt:

- Trigger: sự kiện xảy ra, ví dụ nhận phản hồi hoặc DA gửi kết luận.
- Guard: điều kiện Boolean tại thời điểm xét chuyển, đặt trong `[...]`; thiếu evidence phải có cách xử lý riêng.
- Effect: hành vi khi transition được thực hiện, đặt sau `/`; không gọi effect trên cạnh là doActivity của state.
- Completion transition: có thể không ghi trigger; ghi guard/effect nếu cần khi behavior của state hoàn tất. Không bịa sự kiện người dùng cho bước chuyển nội bộ.

**Nhận xét cụ thể từ PDF:** Hình 134–135 có nhiều ô chứa `do/`, cạnh chứa điều kiện trong ngoặc vuông và một số cạnh cũng ghi `do/`. Đây là cách trình bày quan sát được trong mẫu, không được sao chép đồng loạt: W19.10 dành `do /` cho behavior trong state, còn hành vi trên transition viết sau `/` trong nhãn trigger/guard/effect. Hình 122–123 có nhiều node đặt tên giống thao tác; bản PharmaFlow phải giữ tên trạng thái và chủ thể rõ để tránh trùng Activity. Không coi `entry`, `exit`, composite state, history hay parallel region là thành phần đã có trong các hình mẫu đã xem.

#### 2.3. Hồ sơ nội dung cho toàn bộ state node

Hồ sơ mỗi state gồm `ID; chủ thể; tên; ý nghĩa/invariant; entry; do; exit; transition vào/ra; nguồn UC/FR`. Ý nghĩa/invariant đã ghi ở các bảng §3–5; bảng sau xác định nội dung behavior dự kiến trong hình. Mọi entry/exit để trống trong mô hình tối thiểu vì chưa có hành vi riêng được chốt. Dấu `—` nghĩa là bỏ compartment/dòng khi vẽ, không phải yêu cầu bổ sung chức năng.

| Machine/state | Tên state | `do /` đề xuất | `entry /` và `exit /` |
|---|---|---|---|
| ST-SD-01/V1 | Đang kiểm tra yêu cầu | Kiểm tra phạm vi hỗ trợ và quyền áp dụng | — |
| ST-SD-01/V2 | Đang đọc dữ liệu | Đọc facts/output và metadata có sẵn | — |
| ST-SD-01/V3 | Đang kiểm tra kết quả | Kiểm tra ngữ nghĩa, điều kiện hiển thị và phần thiếu/lỗi | — |
| ST-SD-01/V4 | Đã trả phản hồi | —; phản hồi đã được trình bày là điều kiện của state | — |
| ST-SD-01/V5 | Lỗi tải kết thúc yêu cầu | —; thông báo lỗi thuộc effect chuyển vào | — |
| ST-SD-01/V6 | Yêu cầu bị từ chối | —; thông báo từ chối thuộc effect chuyển vào | — |
| ST-SD-02/K1 | Đang đối soát đầu vào | DA đối chiếu nguồn/contract/UOM/mapping/coverage với hỗ trợ của hệ thống | — |
| ST-SD-02/K2 | Đang xem xét evaluation | DA kiểm temporal validity và xem xét comparability/metric có căn cứ | — |
| ST-SD-02/K3 | Đang ghi kết luận | DA nhập nhận xét/căn cứ và gắn reference hiện có | — |
| ST-SD-02/K4 | Đang gửi lưu | Thực hiện lần gửi lưu theo ST-SD-03 | — |
| ST-SD-02/K5 | Hoàn tất có kết luận đã lưu | —; phản hồi lưu thành công là điều kiện của state | — |
| ST-SD-02/K6 | Kết thúc lần lưu không thành công | —; nguyên nhân chưa lưu được giữ theo kết quả lần gửi | — |
| ST-SD-02/K7 | Gián đoạn do sự cố truy cập | —; ghi nhận/chuyển đầu mối thuộc effect chuyển vào | — |
| ST-SD-03/L1 | Đang kiểm tra nội dung | Kiểm trạng thái/căn cứ bắt buộc, reference và quyền áp dụng | — |
| ST-SD-03/L2 | Đang lưu | Gửi nội dung lưu và chờ phản hồi của nơi lưu | — |
| ST-SD-03/L3 | Đã lưu | —; có phản hồi lưu thành công | — |
| ST-SD-03/L4 | Chưa lưu do nội dung chưa đạt | —; đã nhận lý do validation/quyền | — |
| ST-SD-03/L5 | Lưu thất bại | —; đã nhận phản hồi lỗi lưu | — |

Các state K1–K3 mô tả trạng thái phiên tương tác, không phải hệ thống tự thực hiện thay DA. Các state V4–V6/K5–K7/L3–L5 là state kết quả trước final, không phải ký hiệu final. Khi dựng hình, chỉ giữ state kết quả nếu cần đọc outcome; final không thay cho tên outcome.

#### 2.4. Quy tắc dùng bảng transition khi dựng hình

1. Dùng bảng §3.2/4.2/5.2 xác định đích, event và guard; dùng §2.3 xác định behavior trong state. Mỗi tác vụ chỉ đặt một lần: nếu behavior đã là `do /` của state đích thì effect trên cạnh chỉ chuyển/giao context, không khởi chạy cùng tác vụ lần nữa.
2. Với T01 ở mỗi machine, thao tác người dùng/điều kiện có quyền là trigger khởi tạo machine ở bên ngoài; cạnh từ Initial tới state đầu chỉ là default transition, không đặt trigger hoặc guard trên cạnh đó.
3. Từ state active, phân biệt “đã hoàn tất kiểm tra” (completion) với “DA xác nhận/gửi” (sự kiện tương tác). Không biến cả hai thành cùng một nút action của Activity.
4. Bảng này mô tả state đơn của chủ thể tương tác. Chưa có căn cứ thêm composite state, history, orthogonal region, timer hoặc event defer. ST-SD-03 là mô hình chi tiết được tham chiếu, chưa tự khai báo nó là submachine UML có entry/exit point đã chốt.
5. Không dùng màu sắc, bo góc hoặc nhãn `do/` để thay cho kiểm tra ngữ nghĩa state. Phải đọc được “chủ thể đang ở tình trạng gì” ngay từ tên state.

### 3. ST-SD-01 — Trạng thái một yêu cầu xem Sales/Forecast

**Chủ thể:** một yêu cầu xem trong phạm vi và loại chức năng cố định; thay bộ lọc/gửi lại là yêu cầu khác. **Actor:** Người dùng được quyền xem Sales/Forecast, thuộc một trong mười role MD-01 nêu tại UC-SD/US. **Truy vết:** UC-SD-01–04/06; FR-SD-01–04/06; SEQ-SD-01–04; ACT-SD-01–04; TC-SD-02/03/04/06/07/11/12/13/14/15.

**Biên:** bắt đầu khi người dùng gửi phạm vi, kết thúc khi phản hồi của lần đó được trình bày hoặc bị từ chối. Không mô tả lifecycle của model, bản ghi Sales hay forecast run.

#### 3.1. Danh sách trạng thái

| State | Ý nghĩa | Điều kiện/hoạt động trong trạng thái |
|---|---|---|
| V1 — Đang kiểm tra yêu cầu | Đã nhận phạm vi; kiểm `sales:read` hoặc `forecast:read` tương ứng, scope assignment, SoD áp dụng và phạm vi được hỗ trợ trước khi đọc | Không trả dữ liệu ngoài quyền; không tự sửa lựa chọn |
| V2 — Đang đọc dữ liệu | Yêu cầu hợp lệ để truy vấn | Đọc facts/output và metadata có sẵn |
| V3 — Đang kiểm tra kết quả | Đã có phản hồi nguồn để kiểm ngữ nghĩa/điều kiện | Phân biệt phần hợp lệ/thiếu/lỗi, UOM/grain/location/provenance |
| V4 — Đã trả phản hồi | Phản hồi business đã được trình bày | Phản hồi có thể đủ, một phần, không có dữ liệu hoặc chưa so sánh/kết luận được |
| V5 — Lỗi tải kết thúc yêu cầu | Không tạo được phản hồi dữ liệu tin cậy cho lần xem | Thông báo lỗi khác no record/zero; giữ nguồn nguyên vẹn |
| V6 — Yêu cầu bị từ chối | Không đủ quyền hoặc phạm vi không được hỗ trợ | Nêu lý do phù hợp quyền; không phát sinh dữ liệu thay thế |

V4 không có nghĩa forecast/evaluation hợp lệ. Một yêu cầu trả thành công thông báo “chưa có forecast” vẫn có outcome dữ liệu là thiếu. Lỗi một phần có thể được trình bày trong V4 với từng phần được phân biệt; V5 dành cho thất bại tải khiến lần yêu cầu không có phản hồi dữ liệu tin cậy.

#### 3.2. Bảng transition

| Mã | Từ → Đến | Event [guard] / action | Căn cứ |
|---|---|---|---|
| T01 | Initial → V1 | Default transition, không trigger/guard; machine bắt đầu sau khi tiếp nhận phạm vi | Normal Flow UC-SD-01–04 |
| T02 | V1 → V2 | Hoàn tất kiểm tra [`sales:read` hoặc `forecast:read` tương ứng; scope/SoD áp dụng đạt; phạm vi được hỗ trợ] / đọc nguồn | FR-SD-01–04; NFR-SD-07; TC-SD-14 |
| T03 | V1 → V6 | Xác định thiếu permission, scope ngoài phạm vi hoặc phạm vi không hỗ trợ / audit outcome, từ chối và không trả payload | TC-SD-14; UC-SD-01/2a; UC-SD-04/2a; NFR-SD-07 |
| T04 | V2 → V3 | Nguồn trả dữ liệu hoặc kết quả không có bản ghi / kiểm kết quả | UC-SD-01/3a; UC-SD-04/3a |
| T05 | V2 → V5 | Nhận lỗi tải không xử lý được trong phản hồi một phần / báo lỗi | NFR-SD-09; TC-SD-13 |
| T06 | V3 → V4 | Hoàn tất kiểm tra / hiển thị số liệu có căn cứ hoặc trạng thái tương ứng và UC-SD-06 | UC-SD-02/3a,3b,4a; UC-SD-03/3a,3b,5a; UC-SD-04/3a,3b,4a,4b |
| T07 | V3 → V5 | Xảy ra lỗi tải bổ sung khiến không hoàn tất phản hồi tin cậy / báo lỗi | NFR-SD-09 |
| T08 | V4 → Final | Hoàn tất trình bày / kết thúc lần xem | Post-conditions UC-SD-01–04 |
| T09 | V5 → Final | Đã báo lỗi / kết thúc lần yêu cầu lỗi | TC-SD-13 |
| T10 | V6 → Final | Đã trả từ chối / kết thúc lần yêu cầu | TC-SD-14; nhánh không hỗ trợ |

#### 3.3. Invariant và đường không được suy diễn

| Tình huống | Quy tắc |
|---|---|
| V2 gặp lỗi → trả số 0 như dữ liệu | Không được: lỗi tải khác zero, NFR-SD-09 |
| V3 thiếu output → tự train model | Không được trong phạm vi FR-SD-04 |
| V4 → “forecast approved/published” | Không có policy; trạng thái phản hồi không cấp quyền phát hành |
| V5 → V2 tự động retry | Chưa được định nghĩa; retry phải theo flow được chốt, không tự thêm |
| V6 → V4 trả dữ liệu ngoài quyền | Không được theo permission/scope policy tại tab 2 |

**Kiểm thử chấp nhận mô hình:** zero từ bản ghi vẫn tới V4; thiếu forecast tới V4 với outcome thiếu; lỗi tải tới V5; series không tương thích tới V4 với lý do không so sánh được; dữ liệu mô phỏng tới V4 phải có nhãn. Không so output success của yêu cầu với chất lượng prediction.

### 4. ST-SD-02 — Trạng thái phiên kiểm định forecast

**Chủ thể:** một phiên tương tác kiểm định với snapshot/run reference xác định. Đây không phải vòng đời bền vững của forecast run. **Actor:** Data admin. **Truy vết:** UC-SD-05/08/09/10 và các UC con; FR-SD-05; SEQ-SD-05/07/08/09; ACT-SD-05/07/08/09; TC-SD-08/09/10/17.

#### 4.1. Danh sách trạng thái

| State | Ý nghĩa | Bất biến |
|---|---|---|
| K1 — Đang kiểm tra quyền và đối soát đầu vào | DA kiểm `forecast_evaluation:read`, scope và SoD áp dụng trước khi đọc/đối chiếu nguồn, contract, UOM, mapping, coverage | Không trả payload ngoài quyền; không sửa source facts |
| K2 — Đang xem xét evaluation | Đủ điều kiện mở phần temporal validity/comparability | Được mở phần kiểm tra không có nghĩa evaluation đã hợp lệ |
| K3 — Đang ghi kết luận | Đã có kết quả kiểm tra hoặc lý do chưa đánh giá được | DA chịu trách nhiệm nhận xét, evidence thiếu phải ghi rõ |
| K4 — Đang gửi lưu | Đã gửi nội dung kết luận; đang thực hiện ST-SD-03 | Chưa báo đã lưu khi chưa có xác nhận |
| K5 — Hoàn tất có kết luận đã lưu | Nơi lưu đã phản hồi thành công | Có thể lưu kết luận invalid/not assessable; không tự publish forecast |
| K6 — Kết thúc lần lưu không thành công | Lần gửi bị từ chối validation hoặc lưu thất bại | Không xác nhận có kết luận mới đã lưu |
| K7 — Bị chặn hoặc gián đoạn do quyền/truy cập | Thiếu permission/scope/SoD áp dụng trước khi đọc hoặc có sự cố cản trở tương tác | Không trả payload ngoài quyền; audit outcome; sự cố dịch vụ/job chuyển IT, DA không tự restart |

K6 mô tả kết quả lần gửi trong phiên, không khẳng định UI bị đóng hoặc mất nội dung. Không thiết kế giữ nháp hoặc tự khôi phục. Chính sách tiếp tục sau thất bại phải được chốt trước khi thêm đường quay lại.

#### 4.2. Bảng transition

| Mã | Từ → Đến | Event [guard] / action | Căn cứ |
|---|---|---|---|
| T01 | Initial → K1 | Yêu cầu mở phiên; K1 kiểm permission, scope và SoD áp dụng trước khi đọc hồ sơ | UC-SD-05/1–3; NFR-SD-07 |
| T02 | K1 → K2 | DA xác nhận đối soát [forecast_evaluation:read, scope/SoD áp dụng đạt; dữ liệu/protocol đủ điều kiện] / mở phần evaluation | UC-SD-05/4; UC-SD-08/5; NFR-SD-07 |
| T03 | K1 → K3 | Hoàn tất ghi nhận đối soát [quyền/scope hợp lệ nhưng evidence hoặc protocol chưa đủ] / giữ lý do, bỏ so sánh phụ thuộc | UC-SD-05/3a; UC-SD-08/5a |
| T04 | K2 → K3 | Hoàn tất xem xét hoặc phát hiện điều kiện chặn / mang metric hợp lệ hoặc lý do invalid/chưa đánh giá được sang kết luận | UC-SD-05/4a,4b,5a; UC-SD-09/2a–5a |
| T05 | K3 → K4 | DA gửi kết luận [forecast_evaluation:record, scope và SoD áp dụng đạt] / thực hiện ST-SD-03, nơi lưu kiểm lại trước persistence | UC-SD-10/3–6; NFR-SD-07 |
| T06 | K4 → K5 | Nhận phản hồi lưu thành công / xác nhận đã lưu cùng reference có sẵn | UC-SD-10/6 |
| T07 | K4 → K6 | Validation bị từ chối hoặc lưu thất bại / báo chưa lưu và lý do phù hợp | UC-SD-10/5a,6a |
| T08 | K1 → K7 | Thiếu permission/scope/SoD áp dụng trước khi đọc hoặc sự cố truy cập / không trả payload; audit outcome khi bị từ chối, chuyển IT nếu là sự cố dịch vụ | NFR-SD-07; UC-SD-05/7b |
| T09 | K2 → K7 | Sự cố truy cập cản trở evaluation / chuyển IT theo quy trình | UC-SD-05/7b |
| T10 | K3 → K7 | Không truy cập được hồ sơ cần ghi căn cứ / ghi nhận reference đang có, báo chưa hoàn tất | UC-SD-05/7b |
| T11 | K5 → Final | Đã hiển thị xác nhận lưu / kết thúc phiên trong phạm vi mô hình | Post-conditions UC-SD-05 |
| T12 | K6 → Final | Đã báo chưa lưu / kết thúc phạm vi lần thực hiện đang mô tả | UC-SD-05/7a |
| T13 | K7 → Final | Đã báo gián đoạn/chuyển đầu mối / chưa có kết luận hoàn tất được khẳng định | UC-SD-05/7b |

K1 là bước kiểm policy trước khi đọc payload; từ chối quyền/scope không được coi là thiếu evidence và không đi vào K3. Nếu lỗi truy cập xảy ra trước khi mở được hồ sơ thì không tạo phiên kiểm định giả. Lỗi truy cập tại K4 được ST-SD-03 xử lý như lỗi lưu; không có hai transition cạnh tranh cho cùng sự kiện.

#### 4.3. Điều kiện không được suy diễn

| Đường/diễn giải | Ràng buộc |
|---|---|
| K1 → K5 bỏ qua ghi kết luận/lưu | Không đủ căn cứ xác nhận đã lưu |
| K2 phát hiện leakage → kết luận Prediction Quality hợp lệ | Không được theo BR-SD-07/TC-SD-08 |
| K5 → model đã được duyệt phát hành | Không có publication workflow trong UC-SD-05/10 |
| K6/K7 → tự restart job hoặc tự chạy backtest | Ngoài phạm vi, quyền/quy trình chưa xác nhận |
| K5 → sửa/xóa kết luận hoặc mở lại phiên | Policy version/reopen/retention còn TBD; không thiết lập transition |

**Kiểm thử chấp nhận mô hình:** K1 bị chặn vẫn đến K3 và có thể K5 với kết luận chưa đánh giá được; K2 phát hiện leakage vẫn có thể lưu kết luận invalid; K4 lỗi không đến K5. K5 không chứng minh prediction tốt hoặc quyết định tồn kho tốt.

### 5. ST-SD-03 — Trạng thái một lần gửi lưu kết luận

**Chủ thể:** một lần gửi nội dung kết luận, không phải toàn bộ vòng đời bản ghi kết luận. **Truy vết:** UC-SD-10/10.1; FR-SD-05; SEQ-SD-09; ACT-SD-09; TC-SD-17.

#### 5.1. Danh sách trạng thái

| State | Ý nghĩa |
|---|---|
| L1 — Đang kiểm tra nội dung | Đã nhận lần gửi; kiểm trạng thái/căn cứ bắt buộc, references và quyền áp dụng |
| L2 — Đang lưu | Nội dung đủ điều kiện gửi lưu theo policy; chưa xác nhận persistence |
| L3 — Đã lưu | Nhận phản hồi lưu thành công |
| L4 — Chưa lưu do nội dung chưa đạt | Thiếu trường bắt buộc/reference cần xác nhận hoặc không đủ quyền theo policy |
| L5 — Lưu thất bại | Đã gửi lưu nhưng nhận lỗi, chưa có xác nhận thành công |

#### 5.2. Bảng transition

| Mã | Từ → Đến | Event [guard] / action | Căn cứ |
|---|---|---|---|
| T01 | Initial → L1 | Default transition, không trigger/guard; machine được khởi tạo bởi lần gửi nội dung của DA | UC-SD-10/3–5 |
| T02 | L1 → L2 | Hoàn tất validation [đạt policy áp dụng] / gắn actor/thời điểm, gửi lưu | UC-SD-10/5–6 |
| T03 | L1 → L4 | Hoàn tất validation [thiếu bắt buộc/reference chưa hợp lệ hoặc bị từ chối quyền] / yêu cầu bổ sung hoặc báo từ chối | UC-SD-10/5a; UC-SD-10.1/2a; NFR-SD-07 |
| T04 | L2 → L3 | Nơi lưu phản hồi thành công / xác nhận đã lưu | UC-SD-10/6 |
| T05 | L2 → L5 | Nơi lưu phản hồi thất bại / báo chưa lưu | UC-SD-10/6a |
| T06 | L3 → Final | Đã trình bày kết quả / trả thành công cho K4 của ST-SD-02 | UC-SD-05/7 |
| T07 | L4 → Final | Đã trình bày lý do / trả chưa lưu cho phiên cha | UC-SD-10/5a |
| T08 | L5 → Final | Đã trình bày lỗi / trả chưa lưu cho phiên cha | UC-SD-10/6a |

Thiếu evidence reference phải được ghi rõ, nhưng không tự đồng nghĩa validation bị chặn: phụ thuộc field/policy bắt buộc được xác nhận. Kết luận “chưa đánh giá được” có thể đạt L2/L3 với bằng chứng còn thiếu được mô tả trung thực. Reference đã biết không hợp lệ không được nhận là hợp lệ hoặc truy vết đầy đủ.

Không tự định nghĩa timeout, xử lý mất phản hồi sau khi server có thể đã lưu, retry/idempotency, duplicate submissions hoặc rollback. Đây là khoảng trống cần chốt; không có phản hồi thành công thì UI không báo “đã lưu”, nhưng cũng không khẳng định database chắc chắn chưa ghi nếu contract không chứng minh điều đó.

#### 5.3. Đường không được suy diễn

| Đường/diễn giải | Ràng buộc |
|---|---|
| L1 → L3 không có xác nhận nơi lưu | Không đủ căn cứ báo đã lưu |
| L4/L5 → L3 chỉ vì UI đóng thông báo lỗi | Không được; cần một lần gửi và phản hồi lưu thành công |
| L5 → L2 tự retry | Chưa có policy; không tự thêm |
| L3 → “forecast chất lượng tốt” | Persistence thành công không đánh giá Prediction Quality |
| Gửi lại sau bổ sung | Là lần gửi mới theo quy trình được chốt, không làm lần gửi cũ tự thành công |

**Kiểm thử chấp nhận mô hình:** thiếu trạng thái bắt buộc dẫn L4; reference sai dẫn L4; invalid/not assessable với nội dung hợp lệ vẫn có thể L3; lỗi persistence dẫn L5; facts và score nguyên vẹn trong mọi đường.

### 6. Các trạng thái dữ liệu phải mô tả bằng điều kiện riêng

#### 6.1. Kết quả đối soát và evaluation

| Trục | Các ý nghĩa cần phân biệt | Evidence cần có | Không suy diễn |
|---|---|---|---|
| Đối soát đầu vào | Phù hợp; phát hiện sai lệch; chưa xác định | Snapshot, contract, UOM/mapping, phạm vi và kết quả kiểm tra | Không dùng thiếu contract làm bằng chứng dữ liệu đạt |
| Temporal validity | Có căn cứ hợp lệ; có leakage; chưa đủ căn cứ | Thời điểm dữ liệu/features theo từng origin | Không lấy một cutoff đơn lẻ thay chứng cứ đầy đủ |
| Comparability | Tương thích; không tương thích; chưa đủ metadata | Target/grain/unit/horizon/origins/actuals/protocol/evaluation period | Không xếp hạng trực tiếp các phạm vi khác nhau |
| Khả năng đọc metric | Đủ căn cứ; chưa xác định được; chưa chốt định nghĩa | Actuals/coverage và metric definition | Không tạo score thay thế hoặc tự chọn MAE/RMSE/WAPE/Bias làm bộ nghiệm thu |
| Kết luận DA | Hợp lệ; không hợp lệ; chưa đánh giá được theo scope | Actor/thời điểm, kết quả kiểm tra, lý do và references | Kết luận hợp lệ của kiểm định không mặc định model tốt hoặc model được phát hành |

Nguồn dùng các từ invalid/not assessable/not evaluable trong ngữ cảnh khác nhau; đây chưa là enum database chuẩn hóa. Không vẽ đường “invalid → valid” chỉ do chờ đủ thời gian. Cần evidence mới và policy tái kiểm định/versioning trước khi đặc tả transition bền vững.

#### 6.2. Khả dụng forecast theo một cặp location/kỳ

| Điều kiện kiểm tra | Cách trình bày | Căn cứ |
|---|---|---|
| Có output và đủ điều kiện hợp lệ | Hiển thị Forecast Sales Quantity cùng business context | UC-SD-04 Normal Flow |
| Không có output | Chưa có forecast đúng location/kỳ; không điền zero | UC-SD-04/3a |
| Output/run chưa hợp lệ hoặc chưa hoàn tất | Không công bố số đó, giữ lý do kỹ thuật nội bộ | UC-SD-04/3b |
| Đơn vị chưa xác nhận | Ghi chưa xác định hoặc ẩn đơn vị; không tự đoán | UC-SD-04/4a |
| Synthetic | Nhãn dữ liệu mô phỏng | UC-SD-04/4b |
| Lỗi đọc | Thông báo lỗi riêng với không có forecast | NFR-SD-09 |

Synthetic là provenance, unit chưa rõ là metadata, có output là availability: các trục có thể đồng thời tồn tại, không nối thành chuỗi “synthetic → valid → available”. Chưa có trạng thái publish/approve/reject lifecycle của forecast output trong contract.

#### 6.3. Job/run và độ mới telemetry

| Trục | Cách sử dụng | Căn cứ |
|---|---|---|
| Execution status | Hiển thị đang chạy/hoàn tất/lỗi khi nguồn contract cung cấp | UC-SD-11/11.1 |
| Evidence availability | Thiếu telemetry thì trạng thái quan sát là chưa biết; không chứng minh job chưa chạy | UC-SD-11.1/2a |
| Freshness | Hiển thị timestamp cuối và cảnh báo cũ theo rule đã chốt | UC-SD-11.1/3a; UC-SD-11.2/3a |
| Schedule availability | Có lịch hoặc chưa được cung cấp; thao tác xem không thay lịch | UC-SD-11.2 |

“Telemetry cũ” không phải execution state mới của job. Chưa vẽ lifecycle queued → running → success/failed hoặc failed → retry: thiếu scheduler/state contract, quyền retry/restart và policy stale. Mẫu state diagram quản trị tài khoản không cung cấp những quy tắc này cho PharmaFlow.

### 7. Ma trận liên kết và quyết định mở

| Nhóm hoạt động | State thích hợp | Phạm vi |
|---|---|---|
| UC-SD-01/02/03/04/06; ACT-SD-01–04 | ST-SD-01 và §6.2 | Trạng thái một yêu cầu xem, không phải vòng đời dữ liệu |
| UC-SD-05/08/09 và UC con; ACT-SD-05/07/08 | ST-SD-02 và §6.1 | Tiến trình tương tác kiểm định và outcome/evidence tách riêng |
| UC-SD-10/10.1; ACT-SD-09 | ST-SD-03, K3–K6 của ST-SD-02 | Một lần gửi lưu; chưa quy định lifecycle sửa/phát hành kết luận |
| UC-SD-07/11/11.1/11.2/12; ACT-SD-06/10 | §6.3; chưa chốt state machine execution | Chỉ quan sát telemetry và log; không quản lý scheduler |

| Quyết định cần chốt | Ảnh hưởng |
|---|---|
| Các chủ thể tương tác đề xuất có được chấp nhận làm phạm vi state diagram không? | Tên và biên ST-SD-01–03; chưa khẳng định entity thiết kế đã khóa |
| Bộ mã/ý nghĩa kết luận, gate kiểm định và evidence bắt buộc | Guards K1/K2/K3 và validation L1 |
| Lưu nháp, sửa/version kết luận, tiếp tục/reopen sau lỗi | Chưa có transition quay lại từ K5/K6/K7 |
| Timeout, unknown save outcome, idempotency và retry | Chưa có cơ chế tự phục hồi L5; không giả database chắc chắn chưa ghi |
| Output/run selection và điều kiện công bố forecast | Chưa có lifecycle publish hoặc chính sách latest run |
| Execution state contract, quyền restart/cancel và stale threshold | Chưa có state diagram quản lý job |
| Authentication mechanism, enforcement DB/RLS, audit retention/implementation và masking chi tiết | Role/scope/SoD/audit fields đã theo tab 2; chi tiết triển khai còn chốt |

Checklist trước dựng hình: mỗi state có chủ thể và ý nghĩa tồn tại trong thời gian; mỗi transition có event/guard/action; không nối các trục độc lập thành lifecycle; nhánh lỗi không tự đi thành công; final không xóa đối tượng; không biến Proposed thành deployed; Prediction Quality/Decision Quality và observed/synthetic luôn tách riêng. Khi dựng hình theo skill diagram-design, chốt style/layout và chia hình theo mức độ phức tạp; bản này chưa chứa hình.

### Addendum — permission guards và ST-SD-04 (2026-11-07)

#### Permission guard chung

Các state machine đọc Sales/Forecast chỉ đi vào trạng thái đọc dữ liệu sau khi permission tương ứng và data scope được chấp nhận. Mất quyền trước khi trả dữ liệu dẫn tới state từ chối hiện có V6; không trả payload ngoài quyền. Phiên kiểm định Data Admin và truy cập job/log IT Admin dùng quyền kỹ thuật riêng, không đồng nhất với quyền nghiệp vụ MD-01. Các điều kiện SoD chỉ áp dụng khi có thao tác thuộc policy SoD; không tự thêm quy trình duyệt forecast. Permission guard không tuyên bố auth implementation đã tồn tại.

#### ST-SD-04 — Trạng thái một lần gửi lưu forecast adjustment

**Chủ thể:** một lần gửi lưu bản điều chỉnh cho một forecast reference/coordinate; đây không phải lifecycle của model run, approval hay forecast publication. **Actor:** Supply Chain Planner. **Trigger:** Planner xác nhận lưu một giá trị điều chỉnh. **Truy vết:** UC-SD-13; FR-SD-10; SEQ-SD-11; ACT-SD-11.

| State | Ý nghĩa/bất biến |
|---|---|
| A1 — Đang kiểm tra yêu cầu | Đã nhận submission; chưa tạo version |
| A2 — Đang kiểm tra reference và quyền | Kiểm permission, scope, reference, coordinate, unit |
| A3 — Yêu cầu chưa hợp lệ | Thiếu quyền/reference/unit/lý do hoặc giá trị sai; không persistence |
| A4 — Đang chờ xác nhận | Đã trình model output, giá trị mới, chênh lệch, unit, lý do |
| A5 — Đang lưu version | Permission/reference được kiểm lại; ghi version riêng và audit |
| A6 — Đã lưu version | Version có actor/thời điểm/reference; model output và score gốc không đổi |
| A7 — Lưu thất bại | Không có version mới; output gốc không đổi; cho phép người dùng xử lý lại bằng submission mới |
| A8 — Không có thay đổi | Giá trị mới trùng model value; không tạo version |
| A9 — Bị từ chối | Permission bị thu hồi hoặc scope không hợp lệ; không tiết lộ resource ngoài scope |

| Transition | From → To | Trigger/guard/action |
|---|---|---|
| T01 | Initial → A1 | Default transition khi nhận submission |
| T02 | A1 → A2 | Có input để kiểm tra |
| T03 | A2 → A3 | Thiếu permission, scope, reference, coordinate, unit hoặc SoD áp dụng không đạt |
| T04 | A2 → A4 | Reference và quyền hợp lệ; giá trị/lý do đạt validation |
| T05 | A4 → A8 | Planner xác nhận nhưng giá trị không đổi |
| T06 | A4 → A9 | Quyền bị thu hồi/reference không còn trong scope khi xác nhận |
| T07 | A4 → A5 | Planner xác nhận; quyền/reference được kiểm tra lại thành công |
| T08 | A5 → A6 | Version riêng và audit được ghi thành công |
| T09 | A5 → A7 | Persistence thất bại; không tạo version quan sát được |
| T10 | A3/A7/A8/A9 → Final | Trả outcome tương ứng; mọi retry là submission mới |
| T11 | A6 → Final | Trả xác nhận version đã lưu; model output vẫn là lựa chọn mặc định |

Không có state approved/published/active-by-default. Model output là lựa chọn mặc định kể cả khi A6; adjusted version chỉ được chọn tường minh.
<a id="figures-state"></a>

---

<a id="appendix-diagrams"></a>

## Phụ lục A — Danh mục trang diagram

Danh mục dưới đây được tạo trực tiếp từ page ID/tên trang của bốn file Draw.io W19.10 và hai trang tham chiếu. PDF chèn ảnh các trang theo thứ tự dưới đây; Markdown giữ nguyên nội dung sáu đặc tả ở dạng văn bản có thể tìm kiếm.

| # | Nhóm | Page ID | Tên trang | Vertex | Edge |
|---:|---|---|---|---:|---:|
| 1 | Org chart reference | prtHgNgQTEPvFCAcTncT | org-chart | 15 | 14 |
| 2 | Use Case | pf-sales-demand-01 | 01 — UC-SD-01 — Theo dõi Sales Quantity | 5 | 2 |
| 3 | Use Case | pf-sales-demand-02 | 02 — UC-SD-02 — So sánh Sales Quantity | 6 | 3 |
| 4 | Use Case | pf-sales-demand-03 | 03 — UC-SD-03 — Xu hướng và mùa vụ | 6 | 3 |
| 5 | Use Case | pf-sales-demand-04 | 04 — UC-SD-04 — Forecast theo location và kỳ | 5 | 2 |
| 6 | Use Case | pf-sales-demand-05 | 05 — UC-SD-05 — Đối soát và kiểm định forecast | 7 | 4 |
| 7 | Use Case | pf-sales-demand-06 | 06 — UC-SD-06 — Ngữ cảnh nghiệp vụ Sales/Forecast | 8 | 8 |
| 8 | Use Case | pf-sales-demand-07 | 07 — UC-SD-07 — Theo dõi vận hành hệ thống | 6 | 3 |
| 9 | Use Case | pf-sales-demand-08 | 08 — UC-SD-08 — Đối soát dữ liệu đầu vào | 7 | 5 |
| 10 | Use Case | pf-sales-demand-09 | 09 — UC-SD-09 — So sánh forecast với baseline | 7 | 4 |
| 11 | Use Case | pf-sales-demand-10 | 10 — UC-SD-10 — Ghi nhận kết luận kiểm định | 5 | 3 |
| 12 | Use Case | pf-sales-demand-11 | 11 — UC-SD-11 — Trạng thái và lịch chạy | 6 | 4 |
| 13 | Use Case | pf-sales-demand-12 | 12 — UC-SD-12 — Tra cứu log theo job/run | 5 | 2 |
| 14 | Use Case | pf-sales-demand-usecase | 13 — Tổng quan Sales & Demand | 28 | 25 |
| 15 | Use Case | uc-sd-13 | UC-SD-13 Điều chỉnh một giá trị forecast | 7 | 3 |
| 16 | Sequence | seq-sd-01 | SEQ-SD-01 — Theo dõi Sales Quantity | 70 | 38 |
| 17 | Sequence | seq-sd-02 | SEQ-SD-02 — So sánh Sales Quantity | 70 | 34 |
| 18 | Sequence | seq-sd-03 | SEQ-SD-03 — Xem xu hướng và biểu hiện mùa vụ | 66 | 36 |
| 19 | Sequence | seq-sd-04 | SEQ-SD-04 — Xem Forecast Sales Quantity theo location/kỳ | 71 | 36 |
| 20 | Sequence | seq-sd-05 | SEQ-SD-05 — Đối soát dữ liệu và kiểm định forecast | 93 | 57 |
| 21 | Sequence | seq-sd-06 | SEQ-SD-06 — Theo dõi vận hành hệ thống | 71 | 37 |
| 22 | Sequence | seq-sd-07 | SEQ-SD-07 — Đối soát dữ liệu đầu vào | 96 | 49 |
| 23 | Sequence | seq-sd-08 | SEQ-SD-08 — Kiểm tra và so sánh evaluation | 71 | 43 |
| 24 | Sequence | seq-sd-09 | SEQ-SD-09 — Lưu kết luận và evidence reference | 73 | 38 |
| 25 | Sequence | seq-sd-10 | SEQ-SD-10 — Tra cứu log theo job/run | 56 | 35 |
| 26 | Sequence | seq-sd-11 | SEQ-SD-11 — Điều chỉnh một giá trị forecast | 104 | 56 |
| 27 | Activity | act-sd-01 | ACT-SD-01 Theo dõi Sales Quantity | 35 | 23 |
| 28 | Activity | act-sd-02 | ACT-SD-02 So sánh Sales Quantity | 32 | 20 |
| 29 | Activity | act-sd-03 | ACT-SD-03 Xu hướng và biểu hiện mùa vụ | 31 | 18 |
| 30 | Activity | act-sd-04 | ACT-SD-04 Xem forecast theo location/kỳ | 32 | 22 |
| 31 | Activity | act-sd-05 | ACT-SD-05 Đối soát và kiểm định forecast tổng thể | 31 | 20 |
| 32 | Activity | act-sd-06 | ACT-SD-06 Theo dõi vận hành | 30 | 19 |
| 33 | Activity | act-sd-07 | ACT-SD-07 Đối soát dữ liệu đầu vào | 26 | 18 |
| 34 | Activity | act-sd-08 | ACT-SD-08 Kiểm tra và so sánh evaluation | 29 | 19 |
| 35 | Activity | act-sd-09 | ACT-SD-09 Ghi và lưu kết luận kiểm định | 25 | 15 |
| 36 | Activity | act-sd-10 | ACT-SD-10 Tra cứu log theo job/run | 32 | 20 |
| 37 | Activity | act-sd-11 | ACT-SD-11 Điều chỉnh một giá trị forecast | 28 | 22 |
| 38 | State | st-sd-01 | ST-SD-01 Trạng thái một yêu cầu xem Sales/Forecast | 13 | 10 |
| 39 | State | st-sd-02 | ST-SD-02 Trạng thái phiên kiểm định forecast | 14 | 13 |
| 40 | State | st-sd-03 | ST-SD-03 Trạng thái một lần gửi lưu kết luận | 12 | 8 |
| 41 | State | st-sd-04 | ST-SD-04 Trạng thái một lần gửi lưu forecast adjustment | 22 | 14 |
| 42 | Tender appendix | eXepszNBUrKucnShTvs4 | Module 5 - Đấu thầu | 223 | 149 |

<a id="appendix-references"></a>

## Phụ lục B — Diagram tham chiếu

PDF chèn trang Đấu thầu tại phụ lục này. Org chart được chèn sau User Stories. Cả hai ảnh được đọc từ candidate/snapshot Draw.io và không làm thay đổi nội dung trên Drive.
