# PharmaFlow: bản đồ nghiệp vụ và sản phẩm dữ liệu

## Mục đích và trạng thái

Tài liệu này nối năm miền trong [Landscape](../Landscape/) với nhu cầu dữ liệu của kiến trúc đích. Đây là bản đồ lập kế hoạch, không phải danh sách bảng đã triển khai. Tên data product dưới đây là mô tả năng lực, không phải tên schema/table/API vật lý đã chốt.

Nguồn xử lý trung tâm dự kiến là Databricks Bronze–Silver–Gold. Nguồn đầu vào của DSS trong mô hình đồ án là PostgreSQL và MongoDB trong `src/synthetic_data_source/`, cùng các nguồn ngoài như Weather API và hồ sơ tender khi được bổ sung. Dataset, crawler, mapping và generator hỗ trợ dựng các nguồn này.

## Cách đọc tầng dữ liệu

| Tầng | Vai trò trong data product |
|---|---|
| **Bronze** | Giữ dữ liệu nhận vào và metadata nguồn; hỗ trợ truy vết/tái xử lý. |
| **Silver** | Chuẩn hóa và kiểm tra chất lượng trong khi giữ grain, định danh, đơn vị, thời gian và provenance. |
| **Gold / Data Product** | Công bố tập dữ liệu theo nhu cầu module hoặc nhóm consumer, với grain và ý nghĩa nghiệp vụ được mô tả. |

Feature/trainset có thể được tạo từ Silver chi tiết nếu phù hợp với bài toán. Chọn Gold hay Silver phụ thuộc mục đích sử dụng và hợp đồng dữ liệu; không mặc định một tầng thay thế mọi tầng khác.

## Ma trận theo miền

| Miền | Nhu cầu monitoring, insight và quyết định | Dữ liệu đầu vào cần có | Nguồn hiện có hoặc còn thiếu | Chuẩn hóa Silver dự kiến | Data product phục vụ module | Trạng thái và giới hạn |
|---|---|---|---|---|---|---|
| **Sales** | Theo dõi lượng bán theo sản phẩm, location, channel và thời gian; phân tích xu hướng/seasonality; dự báo Sales & Demand | Catalog và taxonomy có căn cứ; POS/order line hoặc aggregate observation; location, channel, thời gian và UOM theo nguồn | PostgreSQL source đã chuẩn bị dữ liệu phục vụ nghiên cứu Sales & Demand từ Long Châu catalog/location, IRPD, Onyx và Pharma Sales theo các mapping/provenance đã ghi trong package README. Dataset nguồn khác grain và ý nghĩa. | Chuẩn hóa khóa sản phẩm/location, thời gian/timezone, đơn vị; giữ riêng transaction và aggregate observation; phân biệt observed và synthetic POS; không coi sales là unmet demand | **Dự kiến:** sales monitoring mart; feature/trainset dự báo theo grain mà nguồn hỗ trợ; forecast/evaluation product sau khi xây pipeline mô hình | Nguồn đã chuẩn bị, nhưng Databricks, forecast app và web module chưa được xác nhận triển khai. Chưa suy ra SKU-level demand cho aggregate ATC data. |
| **Inventory & Expiry** | On-hand/available, days of supply, stockout/excess, batch/expiry, near-expiry, FEFO và replenishment insight | Balance theo kho/lô; movement/receipt/issue; reservation/restriction nếu có; batch/expiry; đơn vị; product/location | Có các định nghĩa/schema nguồn PostgreSQL và prototype downstream lịch sử; dữ liệu giao dịch hiện tại chưa được xác nhận nạp từ các nguồn Sales. Cần sinh dữ liệu synthetic có provenance cho thử nghiệm. | Tách on-hand, reserved/unreserved, restricted và saleable eligibility; giữ lô, expiry, movement và trạng thái chất lượng riêng; không tự suy saleability | **Dự kiến:** inventory snapshot/movement product; near-expiry/stockout risk product; input product cho replenishment/FEFO scenario | Data product chưa triển khai. Bảng schema không chứng minh có balance/lot thực hoặc workflow tồn kho hoạt động. |
| **Procurement & Supply** | Theo dõi PO đang mở, quantity ordered/received, giá, lead time, độ trễ và supplier reliability; đánh giá incoming supply | Supplier; PO và line; goods receipt và line; thời điểm đặt/nhận; số lượng accepted/rejected; product/UOM | Schema source có mô hình procurement nhưng dữ liệu tương ứng không được các bộ Sales hiện tại cung cấp. Cần tạo nguồn synthetic theo contract nghiệp vụ đã kiểm tra. | Giữ ordered quantity tách received/accepted/rejected; giữ supplier tách manufacturer; chuẩn hóa lead time và đơn vị nhưng không suy luận trạng thái chưa có nguồn | **Dự kiến:** procurement performance mart; incoming-supply features; dữ liệu cung cấp cho risk/replenishment review | Chưa có data product hoặc module triển khai. Không trình bày PO/receipt mô phỏng như hoạt động nhà cung cấp thật. |
| **Distribution & Store Network** | Xem inventory theo location, in-transit quantity/lead time, mất cân bằng location và cơ hội transfer/rebalancing | Location; balance theo kho/lô; transfer header/line; shipped/received event khi có; transit và lead time | Schema có location/transfer concepts; chưa có dữ liệu mạng lưới đủ để xác minh flow transfer thực. Cần dữ liệu synthetic cho các kịch bản. | Giữ source/destination, sent/received quantity, in-transit và thời điểm riêng; không đếm transfer là receipt procurement; dùng chung inventory facts thay vì tạo balance thứ hai | **Dự kiến:** network inventory view; transfer monitoring; imbalance/scenario product | Chưa có mục tiêu, constraint, horizon hoặc solver logistics được chốt; không tuyên bố kế hoạch “optimal”. |
| **Tender & Contract Fulfillment** | Landscape bao quát cơ hội/deadline, điều kiện bid, kết quả lựa chọn, cam kết cung ứng và fulfillment. Module 05 hiện giới hạn ở hồ sơ dự thầu, phân tích phương án, ghi kết quả trúng chính thức theo mặt hàng/số lượng và theo dõi đợt giao theo lượng trúng đã xác nhận; không quản lý ký kết/điều khoản hợp đồng. | Hồ sơ gốc/version; dữ liệu mặt hàng và số lượng yêu cầu; kết quả chính thức theo mặt hàng; số lượng trúng; từng đợt giao và liên kết sản phẩm/location/thời gian khi có căn cứ | Landscape xác định miền nghiệp vụ; các sơ đồ Module 05 trong `jobs/module-05-tender/` mô tả tương tác dự kiến, không phải workflow đã triển khai. Repo chưa có contract/source facts đã xác minh về bid/award/fulfillment. Hồ sơ lưu trên object storage (S3) mới là hướng kiến trúc. | Giữ metadata, version và link hồ sơ; phân biệt trường AI/OCR đề xuất với dữ liệu xác nhận; phân biệt phương án đã chọn, hồ sơ đã nộp, kết quả trúng chính thức và lượng giao thực tế. Dùng lượng trúng đã xác nhận làm mốc theo dõi giao; không suy ra hợp đồng hoặc giao hàng chỉ từ PDF/kịch bản. | **Dự kiến:** tender document/extraction view; supply-scenario view; official award-quantity record; delivery-progress view nếu có nguồn giao phù hợp | Landscape không tự tạo schema/lifecycle tender. Không sáng tác trạng thái tender hoặc coi file PDF là bằng chứng award/fulfillment; chưa có product/workflow Module 05 được xác minh là triển khai. |

## Hợp đồng và ngữ nghĩa dùng chung

Khi thiết kế từng product, cần ghi rõ grain, key, owner, thời gian và timezone, UOM, provenance, chất lượng, độ mới, consumer và giới hạn sử dụng. Các trường chưa có nghĩa được xác nhận phải ghi chưa rõ; không đoán ý nghĩa từ tên cột.

Các nguyên tắc xuyên miền:

- Sales là quantity sold; demand có thể không quan sát được khi stockout. Không đồng nhất sales với latent/unmet demand.
- Ordered quantity khác received quantity; supplier khác manufacturer.
- On-hand hoặc unreserved stock không tự động là saleable stock.
- Transfer khác procurement receipt; planned transfer khác movement đã xảy ra.
- Forecast, risk, recommendation và operational outcome là các facts/lớp khác nhau.
- Public tender award hoặc ví dụ Landscape không phải transaction fulfillment đã quan sát.
- Provenance (observed, synthetic/simulated, hoặc chưa xác minh) phải còn truy được sau Bronze/Silver/Gold.

## Đánh giá chất lượng

Đánh giá forecast riêng bằng temporal backtesting, chống leakage và baseline đơn giản trước mô hình phức tạp. MAE, RMSE, WAPE và Bias là các metric dự báo; không dùng chúng thay cho đánh giá quyết định.

Đánh giá decision/scenario riêng bằng chỉ số phù hợp như stockout, service/fill level, average inventory, overstock, expiry/wastage và simulated total cost. Kết quả synthetic cần luôn được báo là mô phỏng; không diễn giải như kết quả vận hành quan sát.

## Tài liệu liên quan

- [Kiến trúc hệ thống](pharmaflow-system-architecture.md).
- [Domain & Module Map](pharmaflow-domain-module-map.md).
- [Landscape và transcript](../Landscape/).
- [Source contract và dictionary](../data-model/Relations-DataSource/README.md).
