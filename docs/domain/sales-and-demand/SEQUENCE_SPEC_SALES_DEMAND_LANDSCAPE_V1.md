# Đặc tả Sequence PharmaFlow — Sales & Demand (Landscape V1)

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | `PF-SEQ-SALES-DEMAND-LANDSCAPE-V1` |
| Ngày lập | 2026-11-06 |
| Trạng thái | Proposed — đặc tả tương tác để review trước khi dựng hình |
| Phạm vi | 6 sequence tổng quan và 4 sequence chi tiết cho Sales & Demand DSS |
| Nguồn hành vi | [Use Case Specification](USE_CASE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md), [Requirements](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md), [User Stories](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md) |
| Sơ đồ phạm vi đối chiếu | [Draw.io Sales & Demand](pharmaflow_sales_and_demand_usecase.drawio), 13 trang, tổng quan 22 UC |
| Evidence | Phân công 3 actor đã xác nhận trong bộ nguồn; chi tiết hành vi và thiết kế nội bộ còn Proposed. Không xác nhận code, API, schema DSS hoặc deployment. |

## 1. Phạm vi và nguyên tắc đặc tả

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

## 2. Mức thiết kế, participant và quy ước

### 2.1. Mức mô tả

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

### 2.2. Quy ước message và điều kiện

- Mã bước `M01…` có phạm vi trong từng sequence; nhánh `A01…` ghi điểm phát sinh và nguồn UC cụ thể.
- Dòng có cùng bên gửi/nhận biểu diễn xử lý nội bộ có thể vẽ thành self-message hoặc note. Hoạt động suy xét của actor không được biến thành kết luận tự động của hệ thống.
- `alt` biểu diễn kết quả loại trừ nhau tại một điểm; `opt` biểu diễn tương tác tùy điều kiện. Đối với mùa vụ hoặc evaluation, cần diễn đạt được cả lý do bỏ qua khi không đủ điều kiện.
- Duyệt logic theo từng location/kỳ không bắt buộc gửi một query cho mỗi cặp; chưa quyết định batching hoặc song song hóa.
- Khi dựng hình, dùng bảng bước làm nguồn nội dung; chia hình chính/ngoại lệ nếu quá dày. Không ép toàn bộ nhánh thành một khung lồng nhau.
- Liên kết tổng quan/chi tiết là tham chiếu đặc tả, không phải participant mang tên UC. `include` không tự định nghĩa thứ tự message và không buộc các bước sau lỗi phải tiếp tục như thành công.
- Mọi sequence bắt buộc áp dụng permission → data scope → SoD liên quan → điều kiện trạng thái trước khi trả/ghi dữ liệu; backend không dựa vào việc ẩn nút ở UI. Khi ghi, kiểm tra lại quyền và reference; từ chối không trả payload ngoài scope; audit actor/permission/resource/outcome/time và before/after khi có thay đổi. Không đặc tả login/token/session vì đây là trách nhiệm dịch vụ xác thực. Căn cứ: tab 2, NFR-SD-07, TC-SD-14.

### 2.3. Ngữ cảnh business dùng chung — UC-SD-06

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

## 3. Danh mục sequence

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

## 4. SEQ-SD-01 — Theo dõi Sales Quantity

**Mục tiêu:** SC đọc lượng bán theo kỳ và những chiều nguồn hỗ trợ, giữ ngữ nghĩa dữ liệu.

**Truy vết:** US-SD-LS-01/06; UR-SD-01/06; FR-SD-01/06; BR-SD-01–06/09; NFR-SD-01/02/09; TC-SD-01/02/04/05/12/13/15.

**Participant:** SC, UI-S, C-S, R-S. **Trigger:** SC mở theo dõi Sales Quantity.

**Điều kiện trước:** quyền đọc phù hợp; dữ liệu và contract có thể được nhận diện, phần thiếu có trạng thái riêng. Dimension chỉ được cung cấp khi có căn cứ nguồn. **Đầu vào:** kỳ và product/group/location/channel khả dụng. **Đầu ra:** giá trị hoặc trạng thái, phạm vi, đơn vị và nhãn business.

### 4.1. Luồng tương tác chính

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

### 4.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M05: chiều không được nguồn hỗ trợ | Báo không khả dụng; không dựng chiều thay thế; cần lựa chọn hợp lệ để tiếp tục | UC-SD-01/2a |
| A02 | M07: không có bản ghi | Trả trạng thái không có bản ghi cho phạm vi đó; zero chỉ hiển thị khi có giá trị zero được ghi nhận | UC-SD-01/3a |
| A03 | M07–08: đơn vị/provenance chưa xác định | Giữ trạng thái chưa rõ; không tổng hợp thiếu căn cứ hoặc nâng thành actual đã kiểm chứng | UC-SD-01/3b; BR-SD-05/06 |
| A04 | M03/M06–09: lỗi tải | Hiển thị không thể tải; tách phần lỗi nếu chỉ tải được một phần; không giả kết quả hợp lệ | UC-SD-01/4a; TC-SD-13 |

**Hậu điều kiện:** kết quả hoặc trạng thái tương ứng được trình bày; source facts không đổi. **Review trước dựng hình:** kiểm tra cả no record và zero; grain aggregate không bị chuyển thành transaction; áp dụng đầy đủ §2.3.

## 5. SEQ-SD-02 — So sánh Sales Quantity

**Mục tiêu:** SC so sánh tập series/kỳ tương thích, không nhận chênh lệch/thứ hạng sai nghĩa.

**Truy vết:** US-SD-LS-02/06; UR-SD-02/06; FR-SD-02/06; BR-SD-03/04/05/06/09; NFR-SD-02/06/08/09; TC-SD-03/12/13/15.

**Participant:** SC, UI-S, C-S, R-S. **Trigger:** SC chọn chức năng so sánh. **Điều kiện trước:** quyền đọc và có các series/metadata để kiểm tra; đường chính cần ít nhất hai đối tượng/kỳ. **Đầu vào:** tập đối tượng/kỳ, measure và metadata liên quan. **Đầu ra:** tập so sánh hợp lệ, giá trị, chênh lệch/thứ hạng cùng giới hạn.

### 5.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | SC → UI-S → C-S | Chọn tập series và/hoặc kỳ cần so sánh |
| M02 | C-S → C-S | Kiểm tra có ít nhất hai đối tượng/kỳ |
| M03 | C-S → R-S | Đọc dữ liệu và measure/UOM/grain/coverage theo contract |
| M04 | R-S → C-S | Trả các chuỗi cùng metadata và trạng thái thiếu |
| M05 | C-S → C-S | Thực hiện UC-SD-02.1: xác định tập so sánh trực tiếp được và lý do không tương thích |
| M06 | C-S → C-S | Với tập đủ điều kiện, tính chênh lệch/thứ hạng theo rule; không tự đổi UOM/grain |
| M07 | C-S → UI-S → SC | Hiển thị giá trị, tập so sánh, kỳ, đơn vị, mức chi tiết business và giới hạn; áp dụng UC-SD-06 |

### 5.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M02: chỉ một đối tượng/kỳ | Yêu cầu chọn thêm hoặc quay lại theo dõi; chưa tính so sánh | UC-SD-02/2a |
| A02 | M05: measure/UOM/grain không tương thích | Không tính chênh lệch/xếp hạng trực tiếp các chuỗi đó; ghi lý do. Chỉ tiếp tục với tập còn đủ điều kiện | UC-SD-02/3a; UC-SD-02.1/3a |
| A03 | M04–05: metadata thiếu | Đánh dấu chưa xác định; không tự quy đổi đơn vị/grain | UC-SD-02.1/2a |
| A04 | M05: coverage thiếu/khác đáng kể | Nêu giới hạn; không coi missing là zero hoặc kết luận nhóm tốt/xấu; nếu không đủ căn cứ thì không so sánh trực tiếp | UC-SD-02/3b; FR-SD-02 |
| A05 | M06: cần aggregation chưa có rule | Giữ riêng các series; không tự cộng | UC-SD-02/4a |
| A06 | M03–07: lỗi tải | Báo phần lỗi, không dùng phần thiếu làm cơ sở xếp hạng | FR-SD-02; TC-SD-13 |

**Hậu điều kiện:** không tạo thứ hạng cho series không tương thích; thứ hạng trong tập chọn không tự nghĩa là tốt/xấu kinh doanh; dữ liệu nguồn không đổi. **Review:** kiểm tra tương thích phải đứng trước tính toán; tập bị loại và phạm vi so sánh phải rõ.

## 6. SEQ-SD-03 — Xem xu hướng và biểu hiện mùa vụ

**Mục tiêu:** SC xem lịch sử và pattern có căn cứ; chỉ bổ sung mùa vụ khi đủ điều kiện.

**Truy vết:** US-SD-LS-03/06; UR-SD-03/06; FR-SD-03/06; BR-SD-01/04/05; NFR-SD-01/02/08/09; TC-SD-04/05/11/12/13. TC-SD-11 của bảng nghiệm thu Requirements là case thiếu chu kỳ.

**Participant:** SC, UI-S, C-S, R-S. **Trigger:** chọn series, measure, khoảng thời gian. **Điều kiện trước:** quyền xem và có lịch sử/coverage để kiểm tra. **Đầu ra:** lịch sử, xu hướng và thông tin mùa vụ nếu đủ bằng chứng; trạng thái thiếu được giữ riêng.

### 6.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | SC → UI-S → C-S | Yêu cầu xem series/measure trong khoảng thời gian |
| M02 | C-S → R-S | Đọc chuỗi lịch sử, metadata thời gian, provenance và contract |
| M03 | R-S → C-S | Trả dữ liệu cùng coverage, missing period và thông tin có sẵn |
| M04 | C-S → C-S | Kiểm tra tính liên tục, coverage, số chu kỳ theo phương pháp được xác nhận |
| M05 | C-S → UI-S → SC | Trình bày lịch sử/xu hướng trong phạm vi có căn cứ, áp dụng UC-SD-06 |
| M06 | C-S → C-S | Khi đủ coverage/chu kỳ và phương pháp đã xác nhận: thực hiện phần bổ sung UC-SD-03.1 |
| M07 | C-S → UI-S → SC | Bổ sung biểu hiện mùa vụ cùng chu kỳ, phạm vi và căn cứ |

### 6.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M04: quá ngắn, thiếu kỳ/chu kỳ | Hiện lịch sử khả dụng với khoảng trống; ghi chưa đủ dữ liệu và phạm vi thiếu; bỏ phần kết luận mùa vụ | UC-SD-03/3a; UC-SD-03.1/2a |
| A02 | M03–04: provenance chưa rõ | Chỉ hiện cảnh báo provenance chưa rõ; không trình giá trị/lịch sử như dữ liệu đã kiểm chứng; không kết luận mùa vụ thiếu căn cứ | UC-SD-03/3b; UC-SD-03.1/2a; quyết định review W19.10 |
| A03 | M06: phương pháp/điều kiện chưa xác nhận | Chỉ trình bày lịch sử; không tự chọn thuật toán/ngưỡng chu kỳ | UC-SD-03/5a; UC-SD-03.1/2b |
| A04 | M02–07: lỗi tải | Hiển thị lỗi/phần thiếu riêng; không dựng pattern từ dữ liệu tải thất bại | NFR-SD-09; TC-SD-13 |

**Hậu điều kiện:** historical pattern không bị gọi là latent demand hoặc lost demand. Không đổi source facts. **Review:** nhánh không có mùa vụ vẫn hoàn thành mục tiêu xem lịch sử; ngưỡng coverage và thuật toán là TBD, không mặc định 12/24 tháng.

## 7. SEQ-SD-04 — Xem Forecast Sales Quantity theo location/kỳ

**Mục tiêu:** SC đọc forecast có sẵn cho một/nhiều location và kỳ, giữ riêng kết quả từng cặp.

**Truy vết:** US-SD-LS-04/06; UR-SD-04/06; FR-SD-04/06; BR-SD-01/05/07/09; NFR-SD-01/05/06/09; TC-SD-06/07/12/13/15.

**Participant:** SC, UI-S, C-S, R-F. **Trigger:** SC mở forecast và chọn location/kỳ. **Điều kiện trước:** phạm vi đọc phù hợp; source/run contract nhận diện location/kỳ và thông tin hiện có. Đường thành công có ít nhất một output hợp lệ; đường thiếu vẫn phải trả trạng thái. **Đầu vào:** location và kỳ forecast. **Đầu ra:** con số/trạng thái từng cặp và đơn vị đã xác nhận.

### 7.1. Luồng tương tác chính

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

### 7.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M04/M07: location không được hỗ trợ | Báo không khả dụng, không đổi demand location thành fulfillment location hoặc ngược lại | UC-SD-04/2a |
| A02 | M06–07: thiếu output hợp lệ cho một/nhiều cặp | Ghi “chưa có forecast cho location/kỳ này” đúng phần thiếu; giữ phần hợp lệ; không điền zero | UC-SD-04/3a |
| A03 | M07: run chưa hợp lệ/chưa hoàn tất hoặc thiếu metadata bắt buộc | Không công bố output đó; giữ lý do kỹ thuật trong hồ sơ nội bộ; UI dùng thông báo business | UC-SD-04/3b; TC-SD-07 |
| A04 | M08–09: đơn vị chưa xác nhận | Ghi chưa xác định hoặc ẩn đơn vị; không tự suy đoán | UC-SD-04/4a |
| A05 | M08–09: output synthetic | Gắn “dữ liệu mô phỏng”, không bắt SC đọc provenance code | UC-SD-04/4b |
| A06 | M02/M05–09: tải thất bại | Báo lỗi tải riêng với trạng thái chưa có forecast; giữ rõ phần thành công/phần lỗi | NFR-SD-09; TC-SD-13 |

**Hậu điều kiện:** không cộng ngầm định nhiều location; không cập nhật model, source facts hoặc quyết định vận hành. Không hiển thị model/version, protocol, cutoff kỹ thuật, run ID và lineage trên UI-S. **Review:** chưa có chính sách chọn run khi nhiều output trùng target/location/kỳ; không mặc định lấy run mới nhất hoặc tự gắn trạng thái approved.

## 8. SEQ-SD-05 — Đối soát dữ liệu và kiểm định forecast

**Mục tiêu:** DA kiểm tra dữ liệu/evaluation và lưu kết luận có evidence, kể cả kết luận chưa đánh giá được.

**Truy vết:** US-SD-LS-05; UR-SD-05; FR-SD-05; BR-SD-05/07; NFR-SD-01/05/07/09; TC-SD-08/09/10/17.

**Participant:** DA, UI-D, C-D, R-E, R-K. **Trigger:** DA mở hồ sơ snapshot/run cần kiểm định. **Điều kiện trước:** quyền truy cập phù hợp và nhận diện được hồ sơ; trường contract chưa có phải được đánh dấu, không tự điền. **Đầu vào:** tham chiếu snapshot/run/evaluation, thông tin hiện có theo contract. **Đầu ra:** kết quả đối soát, trạng thái evaluation và kết luận lưu thành công hoặc thông báo chưa lưu.

### 8.1. Luồng tương tác chính

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

### 8.2. Luồng thay thế

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

## 9. SEQ-SD-06 — Theo dõi vận hành hệ thống

**Mục tiêu:** IT xem trạng thái, lịch, độ mới và mở log khi cần để phân loại vấn đề.

**Truy vết:** US-SD-LS-07; UR-SD-07; FR-SD-09; NFR-SD-07/09; TC-SD-14/16.

**Participant:** IT, UI-O, C-O, R-O. **Trigger:** IT mở theo dõi vận hành. **Điều kiện trước:** phạm vi được phép xem; telemetry/lịch được truy vấn hoặc xác định chưa có. **Đầu vào:** dịch vụ/job, khoảng lịch và job/run reference khi có. **Đầu ra:** trạng thái và timestamp, lịch, độ mới, log tùy yêu cầu.

### 9.1. Luồng tương tác chính

| Bước | Gửi → Nhận | Nội dung và kết quả |
|---|---|---|
| M01 | IT → UI-O → C-O | Chọn dịch vụ/job hoặc khoảng lịch |
| M02 | C-O → R-O | Tra cứu trạng thái, thời điểm bắt đầu/kết thúc, timestamp telemetry và lịch hiện có |
| M03 | R-O → C-O | Trả trạng thái/lịch cùng timestamp và phần chưa có |
| M04 | C-O → UI-O → IT | Hiển thị trạng thái và độ mới có căn cứ — UC-SD-11, UC-SD-11.1, UC-SD-11.2 |
| M05 | IT → IT | Đánh giá trạng thái và ghi nhận vấn đề vận hành nếu có |
| M06 | IT → UI-O → C-O | Tùy yêu cầu xem chi tiết job/run: tiếp SEQ-SD-10 |
| M07 | IT → IT | Phân loại vấn đề; nếu thuộc dữ liệu/model thì chuyển DA theo quy trình được xác nhận |

### 9.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M03: không có job phù hợp | Báo không tìm thấy job trong phạm vi; không tạo job giả | UC-SD-07/2a; UC-SD-11/2a |
| A02 | M03: thiếu telemetry/lịch | Nêu dữ liệu chưa được cung cấp; trạng thái chưa biết, không coi thành công | UC-SD-07/3a; UC-SD-11/3a; UC-SD-11.1/2a; UC-SD-11.2/2a |
| A03 | M04: telemetry/lịch cũ | Hiển thị timestamp cuối và cảnh báo; không tự cập nhật lịch | UC-SD-07/3a; UC-SD-11/4a; UC-SD-11.1/3a; UC-SD-11.2/3a |
| A04 | M05/M07: vấn đề dữ liệu/forecast | IT chuyển DA, không sửa facts hoặc kết luận chất lượng model | UC-SD-07/4a |
| A05 | M05: cần retry/restart/thay lịch nhưng quyền/quy trình chưa chốt | Chỉ ghi nhận nhu cầu, không thực thi | UC-SD-07/4b |
| A06 | M02–04: lỗi truy cập nguồn vận hành | Thể hiện lỗi đọc tách khỏi chưa có telemetry; không suy trạng thái job từ lỗi đọc | NFR-SD-09 |

**Hậu điều kiện:** thao tác xem không đổi trạng thái job/lịch; không tự kết luận thành công khi telemetry thiếu. **Review:** M05/M07 không mặc định có ticket service hay gửi email tự động; cơ chế ghi nhận/chuyển đầu mối là TBD.

## 10. SEQ-SD-07 — Đối soát dữ liệu đầu vào

**Mục tiêu:** DA xác nhận nguồn, snapshot, đơn vị/mapping và coverage trước khi diễn giải evaluation.

**Truy vết:** UC-SD-08/08.1/08.2/08.3; US-SD-LS-05; UR-SD-05; FR-SD-05; BR-SD-03–07/09; NFR-SD-01/05; TC-SD-17. **Quan hệ:** chi tiết M04 của SEQ-SD-05.

**Participant:** DA, UI-D, C-D, R-E. **Trigger:** mở phần đối soát của hồ sơ kiểm định. **Điều kiện trước:** nhận diện được snapshot/dataset cần đối chiếu và quyền đọc. **Đầu vào:** snapshot reference, source contract và phạm vi mong đợi nếu đã định nghĩa. **Đầu ra:** kết quả từng kiểm tra, sai lệch, phần thiếu và trạng thái ảnh hưởng evaluation.

### 10.1. Luồng tương tác chính

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

### 10.2. Luồng thay thế

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

## 11. SEQ-SD-08 — Kiểm tra và so sánh evaluation

**Mục tiêu:** DA đọc metric trên temporal backtest hợp lệ và protocol tương thích, tránh so sánh sai phạm vi.

**Truy vết:** UC-SD-09/09.1/09.2; US-SD-LS-05; UR-SD-05; FR-SD-05 và Requirements §4.2; BR-SD-07; NFR-SD-05; TC-SD-08/09/10/17. **Quan hệ:** chi tiết M06–07 của SEQ-SD-05.

**Participant:** DA, UI-D, C-D, R-E. **Trigger:** DA mở phần evaluation khi đối soát không chặn và đủ tham chiếu protocol. **Điều kiện trước:** nhận diện forecast/baseline/actuals/target/grain/horizon/origins; phần thiếu được xử lý bằng nhánh tương ứng. **Đầu ra:** phạm vi metric có thể đọc, trạng thái temporal validity/comparability và căn cứ cho kết luận.

### 11.1. Luồng tương tác chính

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

### 11.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M02–03: metadata/version thiếu | Ghi chưa đủ căn cứ, không suy cấu hình; không nhận temporal validity/comparability đã đạt | UC-SD-09/2a; UC-SD-09.1/1a; UC-SD-09.2/1a |
| A02 | M04: phát hiện leakage | Ghi run không hợp lệ cho kết luận chất lượng; chuyển lưu kết luận có căn cứ | UC-SD-09/3a; UC-SD-09.1/2a |
| A03 | M05–06: protocol/phạm vi không khớp | Không so sánh trực tiếp; ghi rõ trường lệch | UC-SD-09/4a; UC-SD-09.2/2a |
| A04 | M02/M07: run chưa hoàn tất hoặc actuals chưa đủ coverage | Ghi chưa đánh giá được; nếu có giá trị metric nguồn thì hiển thị nguyên số kèm nhãn “Chưa đánh giá được”; không tính score mới/thay thế hoặc xếp hạng; không có số thì chỉ hiển thị trạng thái | UC-SD-09/4b |
| A05 | M07: metric chưa chốt/không xác định được | Trình bày trạng thái và căn cứ; không xếp hạng model tốt/xấu hoặc tạo công thức thay thế | UC-SD-09/5a |

**Hậu điều kiện:** trạng thái kiểm tra và phạm vi được chuyển cho phần kết luận; score gốc không bị sửa. Với A04, giá trị metric nguồn có sẵn (nếu có) vẫn được trình bày kèm nhãn “Chưa đánh giá được”; không tính score mới/thay thế hoặc xếp hạng. MAE/RMSE/WAPE/Bias là ứng viên, chưa mặc định bộ nghiệm thu. **Review:** rolling-origin yêu cầu evidence theo từng origin; chỉ có một trường cutoff không chứng minh không leakage. Không thêm lệnh train/backtest vào đường xem hồ sơ này.

## 12. SEQ-SD-09 — Lưu kết luận và evidence reference

**Mục tiêu:** DA lưu nhận xét và trạng thái có thể truy vết mà không ghi đè source facts hoặc score.

**Truy vết:** UC-SD-10/10.1; US-SD-LS-05; UR-SD-05; FR-SD-05; NFR-SD-01/05/07/09; TC-SD-17. **Quan hệ:** chi tiết M08–10 của SEQ-SD-05.

**Participant:** DA, UI-D, C-D, R-E, R-K. **Trigger:** DA mở biểu mẫu kết luận. **Điều kiện trước:** đã kiểm tra hoặc ghi rõ trạng thái các phần đối soát/evaluation; nhận diện hồ sơ và bằng chứng đang có. **Đầu vào:** kết quả kiểm tra, trạng thái kết luận, nhận xét/căn cứ, snapshot/run/evidence references. **Đầu ra:** bản ghi kết luận hoặc xác nhận chưa lưu.

### 12.1. Luồng tương tác chính

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

### 12.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M03–04: evaluation không đủ điều kiện | DA ghi không hợp lệ/chưa đánh giá được và lý do; không nhập score thay thế | UC-SD-10/2a |
| A02 | M04–05: thiếu evidence reference | Ghi rõ bằng chứng thiếu, không biểu thị truy vết đầy đủ; chưa có policy buộc đầy đủ mọi reference thì không tự cấm lưu kết luận chưa đánh giá được | UC-SD-10/4a; UC-SD-10.1/1a |
| A03 | M05: reference không hợp lệ | Yêu cầu xác nhận lại, không biểu thị reference hợp lệ hoặc evidence đầy đủ | UC-SD-10.1/2a |
| A04 | M05: thiếu trạng thái/căn cứ bắt buộc | Yêu cầu bổ sung, không lưu bản ghi hoàn chỉnh | UC-SD-10/5a |
| A05 | M07–08: lưu thất bại | Báo chưa lưu; giữ facts và score nguyên vẹn; xử lý lại theo quyền/quy trình đã chốt, không tự retry nền | UC-SD-10/6a |

**Hậu điều kiện:** chỉ bản ghi có phản hồi lưu thành công được nhận là đã lưu; trạng thái invalid/not assessable có thể là kết luận được lưu. Không phát sinh workflow publish/approval vận hành. **Review:** cơ chế sửa/version kết luận, lưu nháp, transaction, idempotency và retention là TBD; chưa thêm UPDATE/UPSERT hay append-only contract.

## 13. SEQ-SD-10 — Tra cứu log theo job/run

**Mục tiêu:** IT chẩn đoán một job/run trong phạm vi được phép, không lộ thông tin nhạy cảm.

**Truy vết:** UC-SD-12; US-SD-LS-07; UR-SD-07; FR-SD-09; NFR-SD-07/09; TC-SD-14/16. **Quan hệ:** mở rộng có điều kiện M06 của SEQ-SD-06, tại điểm “Xem chi tiết job/run”.

**Participant:** IT, UI-O, C-O, R-O. **Trigger:** IT chủ động yêu cầu log. **Điều kiện trước:** có job/run reference, quyền đọc log áp dụng và nguồn log theo contract; thiếu được trả thành trạng thái riêng. **Đầu vào:** job/run ID, thời gian/phạm vi hiện có. **Đầu ra:** log đã kiểm soát nội dung hoặc không có log/không đủ quyền/lỗi truy cập.

### 13.1. Luồng tương tác chính

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

### 13.2. Luồng thay thế

| Mã | Điểm/điều kiện | Phản hồi và điểm kết thúc | Căn cứ |
|---|---|---|---|
| A01 | M02–03: thiếu/sai ID | Yêu cầu chọn lại từ job/run khả dụng; chưa truy xuất log với reference sai | UC-SD-12/2a |
| A02 | M05: không có log/telemetry | Báo không có dữ liệu log, không suy job thành công | UC-SD-12/3a |
| A03 | M03: không đủ quyền | Từ chối, không trả nội dung; ghi nhận kết quả kiểm tra quyền theo chính sách đã chốt | UC-SD-12/3b |
| A04 | M06: log nguồn có credentials/sensitive values | Không hiển thị giá trị đó; ghi nhận sự cố theo quy trình bảo mật; không sao chép giá trị nhạy cảm vào thông báo | UC-SD-12/4a |
| A05 | M08: log gợi ý lỗi dữ liệu/forecast | IT chuyển DA; không tự sửa facts/kết luận evaluation | UC-SD-12/5a |
| A06 | M04–07: lỗi đọc log | Báo lỗi truy cập riêng với không có log; không dùng lỗi truy cập để suy trạng thái run | NFR-SD-09 |

**Hậu điều kiện:** log không làm đổi job state; không restart/thay lịch; không thay kết luận chất lượng. **Review:** auth mechanism, masking rules, log index, retention và kênh chuyển sự cố chưa chốt; không tự chọn sản phẩm hoặc triển khai endpoint.

## 14. Ma trận bao phủ và quyết định cần chốt

### 14.1. Bao phủ 22 use case

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

### 14.2. Các quyết định mở

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

### 14.3. Checklist review trước dựng hình

- [ ] Mỗi đường đi có trigger, dữ liệu vào, bên nhận và kết quả cuối rõ.
- [ ] Mỗi Alternative Flow trong UC được ánh xạ tới nhánh trong sequence hoặc trách nhiệm dùng chung §2.3.
- [ ] Điều kiện dữ liệu được kiểm tra trước phép tính/diễn giải phụ thuộc; lỗi không rơi tiếp vào thông báo thành công.
- [ ] Nhánh DA không đánh giá được vẫn đi tới ghi kết luận; lỗi lưu kết thúc bằng chưa lưu.
- [ ] Tách hành vi kiểm tra của hệ thống với xem xét/xác nhận của DA; phân loại/chuyển sự cố của IT chưa tự thành integration.
- [ ] Không thêm participant, endpoint, bảng DSS, thuật toán, threshold, auth flow hoặc permission chưa có căn cứ như quyết định đã chốt.
- [ ] Forecast view không train model; evaluation view không tự chạy backtest; kết luận không tự publish/execute.
- [ ] Forecast nhiều location giữ riêng; missing khác zero; simulated khác observed; technical metadata giữ nội bộ.
- [ ] Sau dựng hình, kiểm cả khả năng render và coverage nội dung; chia hình nếu quá nhiều message/nhánh.

## 15. Nguồn đối chiếu

1. [User Stories Sales & Demand Landscape V1](USER_STORIES_SALES_DEMAND_LANDSCAPE_V1.md), §3–5: actors, acceptance criteria và ranh giới module.
2. [Requirements Sales & Demand Landscape V1](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md), §4–7: FR, protocol, business/data rules, NFR và acceptance scenarios; §9: giới hạn evidence và data readiness.
3. [Use Case Specification Sales & Demand Landscape V1](USE_CASE_SPEC_SALES_DEMAND_LANDSCAPE_V1.md), §4–6: toàn bộ Normal/Alternative Flow, quan hệ và truy vết 22 UC.
4. [Draw.io Sales & Demand](pharmaflow_sales_and_demand_usecase.drawio), trang 13 tổng quan và 12 trang UC.
5. [Project invariants](../../AGENTS.md) và [Domain/module map](../../docs/architecture/pharmaflow-domain-module-map.md): DSS boundary, ngữ nghĩa và evidence levels.

Tài liệu này không thay thế ba tài liệu nghiệp vụ nguồn và không khóa baseline requirements. Khi review làm đổi hành vi, phải cập nhật nguồn UC/FR/US liên quan trước hoặc cùng thay đổi đặc tả sequence.

## Addendum — access control và SEQ-SD-11 (2026-11-07)

### Quy tắc quyền áp dụng cho mọi sequence

Actor đọc Sales/Forecast là “Người dùng được quyền xem Sales/Forecast”, tương ứng US-01, 02, 03, 04, 06, 07, 11, 12, 14, 15 theo role assignment và data scope. Planner có thêm `forecast:adjust`. Data Admin thực hiện evaluation bằng quyền kỹ thuật `forecast_evaluation:read/record`; IT Admin xem job/log bằng `job:read`/`job_log:read`. Không suy ra quyền nghiệp vụ từ hai role kỹ thuật.

Trước khi đọc dữ liệu, controller kiểm permission → data scope → SoD áp dụng. SEQ-SD-01–09 mô hình hóa hai operand: quyền/scope/SoD đạt thì tiếp tục flow; nếu bị từ chối thì ghi audit actor, permission, resource, outcome, timestamp, trả refusal và không trả payload ngoài scope. Trước khi ghi kết luận/version, kiểm lại permission, scope, SoD liên quan và resource reference ngay trước persistence; write audit có before/after. Chỉ trả kết quả, location, aggregate và reference thuộc scope. Location không có mapping được xác nhận không được gán vào scope nội bộ. Đây là policy requirement, chưa mô tả endpoint, auth protocol hay deployment.

### 15. SEQ-SD-11 — Điều chỉnh một giá trị forecast

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
