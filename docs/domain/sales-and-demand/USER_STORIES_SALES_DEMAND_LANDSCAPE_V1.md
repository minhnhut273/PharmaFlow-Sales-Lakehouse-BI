# User Stories PharmaFlow — Sales & Demand (Landscape V1)

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | `PF-US-SALES-DEMAND-LANDSCAPE-V1` |
| Trạng thái | Bản nháp đặc tả từ Landscape; chưa được stakeholder xác nhận |
| Phạm vi | Sales & Demand trong PharmaFlow DSS; các giao điểm dữ liệu cần cho insight và forecast |
| Nguồn nghiệp vụ chính | PharmaFlow Data & Business Analytics Landscape KPI Fixed; Landscape Transcript Revised |
| Ngày lập | 2026-11-05 |

## 1. Mục đích và cách đọc

Tài liệu này chuyển nhu cầu Sales & Demand được thể hiện trong Landscape thành các mục tiêu người dùng có thể thảo luận, đặc tả và nghiệm thu. Số lượng story được xác định từ các mục tiêu, không dựa trên số story của tài liệu khác.

Mỗi story mang mã mới `US-SD-LS-*`. Các dấu căn cứ có nghĩa như sau:

- **Landscape scope** — mục tiêu hoặc KPI được nêu trực tiếp trong Landscape.
- **Project constraint** — ranh giới ngữ nghĩa hoặc đánh giá được quy định trong dự án.
- **Design proposal** — cách cung cấp khả năng cho nguyên mẫu; cần stakeholder xác nhận.
- **Data gate** — chỉ nghiệm thu khi dữ liệu nguồn có đủ grain, thời gian, đơn vị và provenance.

Trạng thái phạm vi nghiệp vụ không đồng nghĩa với trạng thái code. Hiện trạng schema, dữ liệu, mã và triển khai được đối chiếu riêng trong [Requirements Sales & Demand](REQUIREMENTS_SALES_DEMAND_LANDSCAPE_V1.md).

## 2. Phạm vi Sales trong Landscape

Sales là lượng bán thực tế. Demand là nhu cầu cần đáp ứng và có thể không được quan sát đầy đủ. Landscape đặt monitoring KPI và sales quantity riêng với forecast, risk, opportunity và optimization.

| Business taxonomy | Category / SubCategory | Business Monitoring / Insight |
|---|---|---|
| Sales | Product Category → Product Group | Sales Quantity; Sales by Product |
| Sales | Sales Channel → Retail Store, Website, Mobile App | Sales by Location; Sales by Channel / Time |
| Sales & Demand Insight | Forecast Sales Quantity | High/low-performing product; seasonal pattern; trend theo product/location/channel khi dữ liệu hỗ trợ |

Các KPI dự báo ở cấp business không tự định nghĩa cách forecast, horizon, thuật toán hoặc metric nghiệm thu. Những lựa chọn đó được mô tả trong requirements với căn cứ hoặc trạng thái cần quyết định.

### 2.1. Bảng phân tích nhu cầu nghiệp vụ

| Nhu cầu / căn cứ Landscape | Câu hỏi người dùng | Thông tin cần xem | Mục đích sử dụng | Giới hạn và cách xử lý trong bộ US |
|---|---|---|---|---|
| Theo dõi bán hàng — Sales KPI, tr.5, 11 | Đã bán bao nhiêu, trong kỳ nào, theo sản phẩm/nhóm, địa điểm và kênh nào? | Sales Quantity theo kỳ và các chiều thật sự có trong source | Nắm trạng thái bán hàng trong tập dữ liệu | US-SD-LS-01; giữ nguyên grain, unit và provenance nguồn; không tạo dimension thiếu |
| So sánh — Sales KPI và high/low-performing product, tr.5, 10 | Nhóm nào bán cao/thấp; sales thay đổi giữa kỳ hoặc nhóm ra sao? | Giá trị, chênh lệch/thứ hạng và tập đối tượng được so sánh | Nhận diện khác biệt cần phân tích | US-SD-LS-02; chỉ so sánh grain, UOM và coverage tương thích; thứ hạng không tự mang nghĩa tốt/xấu |
| Xu hướng/mùa vụ — Sales & Demand Insight, tr.5, 10 | Có trend hay seasonal pattern nào được dữ liệu hỗ trợ? | Chuỗi lịch sử và phạm vi thời gian/đối tượng | Hiểu pattern lịch sử để xem xét trong planning | US-SD-LS-03; không kết luận mùa vụ nếu thiếu coverage/chu kỳ; sales không đồng nghĩa demand |
| Dự báo — Forecast Sales Quantity, tr.5, 10, 12 | Forecast Sales Quantity là bao nhiêu theo từng location và kỳ, cho một hay nhiều cửa hàng/node? | Số forecast theo location và kỳ; tên location và đơn vị nếu có căn cứ | Tham khảo lượng bán dự kiến theo location trong planning | US-SD-LS-04; chỉ hiển thị location/kỳ được source và forecast hỗ trợ; không gộp location ngầm định; không mặc định forecast là latent demand |
| Kiểm định Prediction Quality — KPI/model quality, tr.11–12 | Forecast có được đánh giá nội bộ với actuals ngoài mẫu và baseline tương thích không? | Bằng chứng temporal backtest và metric được lưu trong hồ sơ kiểm định nội bộ | Đảm bảo chất lượng forecast được đánh giá tách khỏi chất lượng quyết định | US-SD-LS-05; đây là kiểm định nội bộ, không yêu cầu Supply Chain xem protocol hay metric kỹ thuật |
| Đọc đúng số liệu — KPI semantics, tr.11, 14 | Con số là Sales history hay Forecast Sales Quantity, thuộc location và kỳ nào? | Nhãn nghiệp vụ, location, kỳ forecast/lịch sử, đơn vị đã xác nhận và trạng thái dễ hiểu nếu chưa có số | Diễn giải đúng con số đang xem mà không cần đọc metadata kỹ thuật | US-SD-LS-06; lineage/provenance chi tiết vẫn được lưu nội bộ; không biến unknown thành zero hoặc tự suy diễn |
| Kết nối quyết định — Insight/Optimization và Inventory Insight, tr.10, 12 | Sales/forecast có thể cung cấp evidence gì để miền Inventory đánh giá stockout, excess hoặc replenishment? | Candidate handoff là Sales evidence/forecast reference có ngữ nghĩa và thời điểm rõ | Hỗ trợ trao đổi liên miền trước khi xây decision capability | **Hoãn khỏi US được nghiệm thu**: Landscape thể hiện capability liên miền nhưng chưa xác định consumer/decision contract, input Inventory đáng tin cậy hay acceptance outcome; nêu lại ở §5 và Requirements §9.1 |

## 3. Actor và đối chiếu org chart

Landscape yêu cầu mỗi KPI có owner ở cấp Department / Team / Role khi cơ cấu tổ chức được xác nhận, nhưng chưa chốt tên chức danh hay phân quyền người dùng. Đã đối chiếu với [pharmaflow_org_chart.drawio trên Drive](https://drive.google.com/file/d/1maGLTtuud9k01u6lnOm_EDjLhO4jWCSm/view?usp=sharing) và ảnh org chart toàn cảnh người dùng cung cấp. Trang `Trang-1` là sơ đồ tổ chức; `Page-2` mô tả workflow Tender nên không dùng làm bằng chứng cho actor Sales & Demand. Trong khối Vận hành thương mại & Kho vận, phòng `Supply Chain Planning / Demand Management` ghi nhiệm vụ `Ra quyết định thương mại` và có card `Supply Chain`; các nhánh Store Manager và Warehouse Manager lần lượt ghi `Kiểm tra thực tế` và `Thực thi & Kiểm soát vận hành`.

| Actor trong user stories | Bằng chứng trong org chart | Đối chiếu nghiệp vụ/ngành | Mức độ khớp và cách dùng |
|---|---|---|---|
| Người dùng được quyền xem Sales/Forecast | Card `Supply Chain` nằm dưới phòng `Supply Chain Planning / Demand Management`, có nhiệm vụ `Ra quyết định thương mại`. | MD-01 cấp R cho US-01, 02, 03, 04, 06, 07, 11, 12, 14, 15; Store Manager và Pharmacist được bao gồm cho thao tác đọc trong scope assignment. | **Dùng actor khái quát cho các story đọc.** Supply Chain là business representative; không giới hạn permission đọc vào riêng chức danh Supply Chain. Không yêu cầu người đọc xem model/protocol/run/lineage metadata. |
| `Store Manager` / `Pharmacist` | Org chart ghi `Kiểm tra thực tế` cho Store Manager; tab 2 ghi quyền R MD-01 cho US-06/US-07. | Tab 2 xác định quyền tính năng; assignment xác định data scope. | **Có thể dùng các chức năng đọc chung** với permission và scope tương ứng; không phát sinh thao tác kiểm tra, nhập hoặc xác nhận dữ liệu tại cửa hàng từ các story hiện tại. |
| `Warehouse Manager` | Org chart ghi `Thực thi & Kiểm soát vận hành`. | Vai trò này gắn với thực thi/kiểm soát nghiệp vụ kho. | **Chưa đưa vào actor hiện tại:** các story Sales & Demand không yêu cầu thao tác kho; handoff sang Inventory cũng đang deferred. Chỉ thêm khi phạm vi có use case kho hoặc handoff được định nghĩa. |
| Sales & Demand KPI Owner (trách nhiệm quản trị) | Landscape yêu cầu mỗi KPI có owner. Org chart có `Regional Manager`, `Store Manager`, và team Supply Chain Planning / Demand Management, nhưng chưa nối từng KPI với một owner cụ thể. | Ownership phụ thuộc domain và KPI scope/grain; không suy ra chỉ từ tên chức danh quản lý. | **Gán theo phạm vi KPI, không tạo actor/card mới:** `Store Manager` là ứng viên cho Sales KPI cấp cửa hàng; `Regional Manager` là ứng viên cho Sales KPI tổng hợp nhiều cửa hàng; team Supply Chain Planning / Demand Management là owner phù hợp để stakeholder xác nhận cho Demand/forecast KPIs. Chỉ đưa manager thành actor user story nếu họ trực tiếp dùng chức năng. |
| `Data admin` | Card có sẵn trong Khối Quản trị hệ thống; người dùng xác nhận kiêm kiểm định forecast ngày 2026-11-05. | Quản trị dữ liệu đầu vào, lineage/provenance và kiểm định Prediction Quality bằng actuals, baseline, temporal backtest. | **Phụ trách chất lượng dữ liệu và kiểm định forecast.** Đọc source/snapshot, đơn vị, location mapping, cutoff, model/protocol version và metric khi đối soát/kiểm định; lưu kết luận cùng bằng chứng. |
| `IT admin` | Card có sẵn trong Khối Quản trị hệ thống; người dùng xác nhận phụ trách vận hành ngày 2026-11-05. | Theo dõi dịch vụ, job, lịch chạy, trạng thái run, log lỗi và truy cập hệ thống. | **Phụ trách vận hành hệ thống.** Dùng run/job ID và log để xử lý sự cố; chuyển vấn đề chất lượng dữ liệu/model cho Data admin. Không mặc định chịu trách nhiệm kết luận chất lượng forecast. |

### Bằng chứng ngành dùng làm đối chiếu

Các trang dưới đây là mô tả công việc của hãng dược, dùng để kiểm tra tên và phạm vi vai trò phổ biến; chúng không chứng minh các chức danh này đã tồn tại trong org chart của PharmaFlow.

- Boehringer Ingelheim `AD, Demand Planning`: một vai trò Demand Planning dẫn S&OP, analytics/reporting, review hiệu suất forecast và phối hợp Supply Chain, Marketing, Finance.
- Takeda `Insights & Analytics Manager`: một vai trò gộp commercial decision support, KPI/scorecard, sales performance analytics và demand forecasting.
- Takeda `Senior Analyst - Commercial Analytics`: một mô hình chuyên viên riêng về sales/channel data, brand KPIs, dashboards và insight.
- Takeda `Manager, Forecasting`: một mô hình chuyên trách chất lượng forecast, review model/assumptions/output và forecast accuracy.

**Phân công đã được người dùng xác nhận ngày 2026-11-05:** `Supply Chain` xem số forecast theo location/kỳ; `Data admin` quản trị dữ liệu và kiêm kiểm định forecast; `IT admin` vận hành hệ thống. Cả ba card đã có trong org chart. Các trách nhiệm này là quyết định phân công cho prototype, không phải bằng chứng chức năng đã triển khai. KPI Owner vẫn là accountability riêng: `Store Manager` là ứng viên cho Sales KPI cấp cửa hàng; `Regional Manager` cho Sales KPI nhiều cửa hàng; team Supply Chain Planning / Demand Management cho Demand/forecast KPI. Mapping owner theo từng KPI còn cần xác nhận. `Warehouse Manager` chưa được gán owner Sales & Demand; manager chỉ thành actor khi có thao tác sử dụng cụ thể.

Thẻ nhân sự trong sơ đồ có thông tin mẫu/không nhất quán (ví dụ email `me@example.com`, thẻ `Supply Chain` mang position `Brand Manager`), nên phép đối chiếu này chỉ dựa vào tên team, nhãn actor và nhiệm vụ hiển thị, không dựa vào tên cá nhân hoặc position trên các thẻ đó.

Không mặc định khách hàng, dược sĩ quầy, thủ kho hoặc người duyệt recommendation là người sử dụng trực tiếp module này.

## 4. User Stories

### US-SD-LS-01 — Theo dõi Sales Quantity

**Căn cứ:** Landscape scope, trang 5 và 11.

**Là** Người dùng được quyền xem Sales/Forecast, **tôi muốn** theo dõi Sales Quantity trong một khoảng thời gian, **để** hiểu lượng bán theo product/group và các chiều location, channel, time có trong dữ liệu.

**Acceptance criteria**

- Người dùng có thể xem kỳ dữ liệu và đơn vị của Sales Quantity.
- Phân rã theo product/group, location, channel và time chỉ xuất hiện khi nguồn có chiều đó với ngữ nghĩa đã xác định.
- Location hiển thị theo nghĩa địa điểm bán/nhu cầu mà source xác nhận; nếu contract tách demand location và fulfillment location thì không dùng hai chiều thay thế nhau.
- Nguồn aggregate vẫn được trình bày ở grain aggregate; không được biến thành giao dịch từng hóa đơn hoặc số lượng từng SKU khi nguồn không cung cấp grain đó.
- Khi dimension, đơn vị hoặc coverage không có trong nguồn, giao diện ghi rõ chưa có/không xác định; không tạo category hay lượng zero để lấp chỗ trống.
- Sales Quantity được gắn nhãn theo evidence nguồn (publisher-reported, dataset observation, derived hoặc synthetic); provenance chưa xác nhận không được nâng thành actual sales đã kiểm chứng.

### US-SD-LS-02 — So sánh Sales theo sản phẩm, địa điểm, kênh hoặc kỳ

**Căn cứ:** Landscape scope, trang 5, 11; thứ hạng high/low là nhu cầu Insight trên trang 10.

**Là** Người dùng được quyền xem Sales/Forecast, **tôi muốn** so sánh Sales Quantity giữa các product/group, location, channel hoặc kỳ, **để** nhận biết nhóm bán cao/thấp trong tập dữ liệu đang xem.

**Acceptance criteria**

- Kết quả nêu rõ kỳ, tập đối tượng, đơn vị và grain dùng để so sánh.
- Chỉ so sánh trực tiếp các chuỗi có measure và đơn vị tương thích; các grain không tương thích phải được giữ riêng hoặc có phép tổng hợp được định nghĩa.
- Thứ hạng mô tả kết quả trong tập được chọn; không tự gắn nhãn thành tốt/xấu về kinh doanh nếu chưa có ngưỡng hoặc mục tiêu được xác nhận.
- Khi coverage hoặc dữ liệu thiếu làm so sánh không công bằng, người dùng thấy cảnh báo và lý do.

### US-SD-LS-03 — Xem xu hướng và biểu hiện mùa vụ

**Căn cứ:** Landscape scope, trang 5 và 10.

**Là** Người dùng được quyền xem Sales/Forecast, **tôi muốn** xem biến động Sales Quantity theo thời gian và các biểu hiện mùa vụ, **để** hiểu pattern lịch sử khi dữ liệu cho phép.

**Acceptance criteria**

- Mỗi biểu đồ hoặc nhận định cho biết measure, grain, kỳ dữ liệu và đối tượng được phân tích.
- Hệ thống phân biệt mô tả pattern lịch sử với kết luận mùa vụ đã được kiểm chứng.
- Nếu coverage thời gian, số chu kỳ hoặc chất lượng dữ liệu chưa đủ để đánh giá, kết quả ghi “chưa đủ dữ liệu” thay vì khẳng định có mùa vụ.
- Sales history không tự trở thành demand history; ảnh hưởng của stockout chỉ được diễn giải khi có evidence phù hợp.

### US-SD-LS-04 — Xem Forecast Sales Quantity

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

### US-SD-LS-05 — Data admin kiểm định forecast

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

### US-SD-LS-06 — Đọc đúng ngữ cảnh của số liệu Sales/Forecast

**Căn cứ:** Landscape KPI lineage, trang 11; data semantics, trang 14; project constraints về observed/synthetic và sales/demand.

**Là** Người dùng được quyền xem Sales/Forecast, **tôi muốn** nhận biết con số đang xem là Sales history hay Forecast Sales Quantity, thuộc location và kỳ nào, **để** diễn giải đúng giá trị nghiệp vụ.

**Acceptance criteria**

- Màn hình nêu rõ loại số liệu bằng nhãn business dễ hiểu, ví dụ `Sales Quantity` hoặc `Forecast Sales Quantity`, cùng location, kỳ và đơn vị đã xác nhận.
- Location được trình bày theo nghĩa được source xác nhận; không trộn demand location với fulfillment location.
- Sales history, forecast và dữ liệu mô phỏng được phân biệt; không đổi sales thành demand hay làm dữ liệu thiếu thành zero.
- Khi không có giá trị cho location/kỳ, giao diện nêu trạng thái bằng ngôn ngữ nghiệp vụ, không yêu cầu Người dùng được quyền xem Sales/Forecast tự đọc source ID, grain kỹ thuật, provenance code hoặc run metadata.
- Lineage, source/run ID, provenance chi tiết và metadata kỹ thuật vẫn được lưu để truy vết nội bộ; chúng không phải trường bắt buộc trên màn hình Người dùng được quyền xem Sales/Forecast.

### US-SD-LS-07 — IT admin theo dõi vận hành hệ thống

**Căn cứ:** Phân công người dùng ngày 2026-11-05; actor IT admin đã có trong Khối Quản trị hệ thống.

**Là** IT admin, **tôi muốn** theo dõi trạng thái dịch vụ và job, lịch chạy và log lỗi, **để** phát hiện sự cố và xác định bước xử lý vận hành.

**Acceptance criteria**

- Xem được trạng thái job/run, thời điểm bắt đầu/kết thúc và lỗi vận hành khi thông tin đó tồn tại trong contract; trạng thái chưa biết không được trình bày là thành công.
- Tra cứu log theo job/run ID theo quyền truy cập; log không chứa credentials hoặc sensitive values.
- Sự cố dữ liệu hoặc kết quả forecast bất thường được chuyển cho Data admin; IT admin không tự thay kết quả kiểm định model.
- Retry/restart hoặc thay lịch chỉ được thực hiện theo quyền và quy trình đã xác nhận; story này không mặc định cấp quyền thay đổi hay tự động chạy lại.

### 4.1. Phạm vi dữ liệu, capability và điều kiện của từng story

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

## 5. Giao điểm và ranh giới module

Sales/forecast là input có thể được sử dụng ở Business Insight và các capability xuyên miền. Bản đặc tả Sales & Demand kết thúc ở việc cung cấp/giải thích sales evidence và forecast reference.

Landscape gợi ý Inventory Insight cho projected stockout/overstock và replenishment, nhưng bộ nguồn hiện chưa xác định phép chuyển Sales/forecast thành các kết luận đó, consumer cụ thể, contract với inventory state hay điều kiện nghiệm thu. Vì vậy, handoff này được ghi là **deferred need**, không bị bỏ quên và không biến thành story vận hành trong Sales.

- Inventory & Expiry sở hữu stock state, batch/expiry, stockout/excess risk và FEFO.
- Procurement & Supply sở hữu inbound PO, Goods Receipt, supplier và delivery performance.
- Distribution & Store Network sở hữu transfer, in-transit và network imbalance.
- Tender & Contract Fulfillment là outbound commitment path; Landscape scenario không phải observed tender data.
- Business Optimization tạo candidate action/scenario; Human Approval là review gate; approval không đồng nghĩa execution.

Các interface/API và business rules của các miền trên chưa được xác định bởi bộ US này.

## 6. Nguồn Landscape

1. [PharmaFlow Data & Business Analytics Landscape KPI Fixed](../../docs/Landscape/PharmaFlow_Data_Business_Analytics_Landscape_KPI_Fixed.pdf), trang 3–5, 10–15.
2. [PharmaFlow Landscape Transcript Revised](../../docs/Landscape/PharmaFlow_Landscape_Transcript_Revised.html).
3. [PharmaFlow Domain & Module Map](../../docs/architecture/pharmaflow-domain-module-map.md), dùng để diễn giải module boundary; không phải bằng chứng deployment.

### Nguồn ngoài về vai trò ngành (analogy, không phải org evidence)

1. [Boehringer Ingelheim — AD, Demand Planning](https://jobs.boehringer-ingelheim.com/job/Johns-Creek%2C-GA-AD%2C-Demand-Planner-Unit/1448131133/).
2. [Takeda — Insights & Analytics Manager](https://jobs.takeda.com/job/toronto/insights-and-analytics-manager/1113/102539792240).
3. [Takeda — Senior Analyst, Commercial Analytics](https://jobs.takeda.com/job/bengaluru/senior-analyst-commercial-analytics/1113/102808132064).
4. [Takeda — Manager, Forecasting](https://jobs.takeda.com/job/bengaluru/manager-forecasting/1113/96526052064).

## 7. Trạng thái xác nhận

Các mục tiêu và KPI trong Landscape là căn cứ phạm vi. Người dùng đã xác nhận ngày 2026-11-05: Data admin quản trị dữ liệu và kiêm kiểm định forecast; IT admin vận hành hệ thống; Supply Chain đại diện nghiệp vụ xem kết quả. Tab 2 xác định mười role được cấp R tại MD-01, scope assignment, SoD và audit policy; chỉ US-03 có quyền điều chỉnh forecast. Story/capability vẫn là design proposal, chưa phải bằng chứng code hoặc deployment.

## Addendum — mapping quyền MD-01 (2026-11-07)

Quyền xem Sales/Forecast theo tab chung được áp dụng trong phạm vi role assignment cho US-01, US-02, US-03 Supply Chain Planner, US-04, US-06, US-07, US-11, US-12, US-14 và US-15. Đây là danh sách role được cấp R tại MD-01; mapping này không xác định KPI Owner. `Supply Chain` trong các story xem hiện tại là actor nghiệp vụ khái quát “Người dùng được quyền xem Sales/Forecast”, được cấp cụ thể cho các role trên. Planner có thêm `forecast:adjust`; Data Admin/IT Admin chỉ có quyền kỹ thuật theo nhiệm vụ đã xác nhận và không có quyền nghiệp vụ MD-01 mặc định.

### US-SD-LS-08 — Điều chỉnh một giá trị forecast

**Là** Supply Chain Planner, **tôi muốn** điều chỉnh một giá trị forecast trong phạm vi được cấp và ghi lý do, **để** lưu một phương án nghiệp vụ có thể phân biệt và truy vết với output do model sinh.

**Acceptance criteria**

- Chỉ Planner có `forecast:adjust`; thao tác yêu cầu quyền xem, scope hợp lệ, forecast reference, location/kỳ, grain và đơn vị được xác nhận.
- Mỗi lần lưu một giá trị tạo version điều chỉnh riêng; lưu giá trị gốc, giá trị mới, lý do, actor, thời điểm và reference. Forecast gốc/source facts/score không bị ghi đè.
- Giá trị mới phải hữu hạn, không âm và theo precision trong unit contract. Thiếu căn cứ hoặc lý do thì không lưu.
- Forecast gốc là lựa chọn mặc định; người dùng chọn bản điều chỉnh tường minh. Nhãn model forecast và adjusted forecast khác nhau.
- Điều chỉnh không đồng nghĩa với approval, publish, execution hay thay đổi forecast run. Prediction Quality của model vẫn trỏ tới output gốc cho tới khi protocol riêng được xác định.
- Thu hồi quyền hoặc persistence failure không tạo version; nội dung nhập vẫn hiển thị để xử lý. Không tạo version nếu giá trị không đổi.
