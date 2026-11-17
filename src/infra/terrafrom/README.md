# PharmaFlow S3 — Terraform dev

Đường dẫn canonical là **`src/infra/terrafrom/`**, theo yêu cầu của người dùng (giữ nguyên spelling). Region cố định `ap-southeast-1`, environment `dev`.

## Trạng thái và phạm vi

Ngày 2026-11-07: Terraform 1.16.2 và AWS CLI 2.36.30 đã có trên máy. Sau khi người dùng đăng nhập lại, profile `my-aws` được STS xác nhận thuộc account `522346104596`, IAM user `admin-nhut` (`arn:aws:iam::522346104596:user/admin-nhut`). User gắn `AdministratorAccess` và `IAMUserChangePassword`, không có permissions boundary, inline user policy hoặc group. IAM simulation cho các action cấu hình S3 và tạo/attach policy đã trả allowed; đây là simulation, chưa chứng minh mọi SCP/session/resource policy hoặc write thực tế đều cho phép.

Trước khi chuyển thư mục: init backend disabled, validate bootstrap/dev/module, fmt check, 1 mock test module bucket và 3 mock tests dev đều PASS; provider lock 6.72.0. Di chuyển đã đối chiếu hash 15 source/config files khớp; hai provider processes bị bỏ lại từ lần out-of-memory đã được xác minh không còn parent và dừng trước khi chuyển. Bộ cũ `infra/teraform/` đã được bỏ. Theo chỉ dẫn lúc đó của người dùng, chưa chạy thêm lệnh Terraform ở đường dẫn mới và chưa chạy live plan/apply; HeadBucket cho hai tên bucket dự kiến trả 404 tại lần kiểm tra ngày 2026-11-07.

**Cập nhật 2026-11-11 (đã xác minh trên AWS):** tài nguyên đã được tạo. HeadBucket thành công cho cả hai bucket (`pharmaflow-dev-tfstate-...` và `pharmaflow-dev-weather-raw-...`, `ap-southeast-1`); bucket state có state object `pharmaflow/dev/bootstrap/terraform.tfstate` (sửa lần cuối 2026-11-09) và `pharmaflow/dev/storage/terraform.tfstate`; hai IAM policy `pharmaflow-dev-weather-s3-writer` và `-reader` tồn tại. Ngày 2026-11-11 đã `plan` rồi `apply` thêm prefix `historical_weather/` vào hai policy (0 add / 2 change / 0 destroy); plan chạy lại không còn khác biệt, policy writer đọc lại từ IAM có đủ 3 ARN prefix. Chưa gắn policy cho role nào và chưa có object Weather trong bucket dữ liệu. Ngày tạo ban đầu của các tài nguyên khác không được ghi lại trong tài liệu này.

**Cập nhật 2026-11-13 (P2, đã xác minh trên AWS):**
- Thêm biến `weather_local_writer_principal_arns` vào `environments/dev/main.tf`. Biến mặc định rỗng, nên không bật thì không tạo role. Biến chặn wildcard và ARN root.
- `terraform.tfvars` (đã gitignore) đặt biến thành `["arn:aws:iam::522346104596:user/admin-nhut"]`. Nhờ đó tạo được role `pharmaflow-dev-weather-local-writer`:
  - Trust policy chỉ cho principal đó gọi `sts:AssumeRole`.
  - `max_session_duration = 3600`.
  - Chỉ có 1 managed policy là `pharmaflow-dev-weather-s3-writer`. Không có inline policy, không có permissions boundary.
- Output mới là `weather_local_writer_role_arn`.
- `tests/policies.tftest.hcl`:
  - Thêm khối `variables {}` ở cấp file để ghim các biến tùy chọn về rỗng. Lý do: `terraform test` tự nạp `terraform.tfvars` ở máy, nên nếu không ghim, test mặc định sẽ bị fail.
  - Thêm 2 run: role chỉ tin principal được liệt kê, và wildcard bị chặn. Kết quả `terraform test` pass 5/5.
- Kết quả trên AWS:
  - `apply` với `AWS_PROFILE=my-aws` kết quả `2 added, 0 changed, 0 destroyed`.
  - Chạy lại `plan -detailed-exitcode` trả `0`.
  - Đọc lại role từ IAM thấy khớp cấu hình.
  - `aws iam simulate-principal-policy` cho 15/15 kết quả đúng kỳ vọng: Get/Put trong 3 prefix được phép; `DeleteObject`, `DeleteObjectVersion`, ghi ngoài prefix, `PutBucketPolicy` và `ListBucket` ngoài prefix bị từ chối.
- Smoke P2 bằng CLI `--sink s3` đã ghi 18 object Weather đầu tiên lên bucket dữ liệu (18 version, 0 delete marker). Policy reader vẫn chưa gắn cho role nào.

**Cập nhật 2026-11-13 (P3, đã xác minh trên AWS):**
- File mới `environments/dev/weather_compute.tf`, đặt sau cờ `enable_weather_compute` (mặc định `false`; `terraform.tfvars` local đặt `true`). Cờ lịch `weather_compute_schedules_enabled` mặc định `false`.
- Thêm provider `hashicorp/archive` (v2.8.1, đã ghi vào `.terraform.lock.hcl`) để tạo placeholder zip trong `.terraform/`.
- Resource P3:
  - Bảng DynamoDB `pharmaflow-dev-weather-control`.
  - 5 queue `pharmaflow-dev-weather-{daily,backfill}` cùng DLQ và `scheduler-dlq`.
  - 3 Lambda `pharmaflow-dev-weather-{planner,worker,reconciler}`, kèm 4 role IAM.
  - 2 schedule (`DISABLED`) và 6 alarm.
- DSN Neon nằm ở SSM `/pharmaflow/dev/weather/neon_dsn`. Terraform không quản lý parameter này, nên giá trị không vào state.
- `tests/compute.tftest.hcl`:
  - Dùng `mock_resource` để tạo ARN giả đúng định dạng.
  - 3 run: tắt cờ thì không tạo gì; bật cờ thì kiểm tra queue, mapping, lịch, IAM và alarm; cờ P4 bật được lịch.
  - Kết quả `terraform test` pass 8/8.
- Kết quả trên AWS:
  - Apply ra `37 added, 0 changed, 0 destroyed`; chạy lại `plan -detailed-exitcode` trả `0`.
  - Đọc lại: bảng `ACTIVE`, bật deletion protection, TTL `ENABLED`; 2 event source mapping `Enabled` (batch 1, max concurrency 2); 2 schedule `DISABLED`.
- Smoke live 5 kịch bản đạt; xem `src/weather/SDD.md` mục 7.3.
- Lưu ý khi chạy trên PowerShell: phải bọc `"-backend-config=dev.backend.hcl"` trong dấu nháy, vì PowerShell tách token này tại dấu chấm.

Các file local `bootstrap/terraform.tfvars`, `environments/dev/terraform.tfvars`, `bootstrap/bootstrap.backend.hcl`, `environments/dev/dev.backend.hcl` đã điền account ID được STS xác nhận; Git ignore chúng. Backend configs chọn profile `my-aws`; provider dùng credential chain của terminal (`AWS_PROFILE=my-aws`). Các `.example` tiếp tục giữ account mẫu để người khác tái sử dụng. Không có access key hoặc token trong code/config này.

## Học code theo thứ tự

1. **Provider** trong hai file `main.tf`: plugin AWS giúp Terraform gọi AWS API. Region là ap-southeast-1; `allowed_account_ids` chặn nhầm account. `AWS_PROFILE` chọn phiên đăng nhập, còn account ID chỉ là định danh kiểm tra, không phải credentials.
2. **Variables**: `expected_account_id` là dữ liệu đầu vào. File `.tfvars` truyền giá trị cho biến; không chứa lệnh tạo tài nguyên. File `.example` chỉ là mẫu, Terraform không tự đọc nó.
3. **Module** `modules/private_s3/`: công thức dùng lại cho một bucket an toàn. `bootstrap/main.tf` và `environments/dev/main.tf` mỗi nơi gọi công thức này một lần với tên bucket khác nhau.
4. **Resource** `aws_s3_bucket.this`: khai báo bucket muốn có. Tên resource `this` chỉ là tên trong code Terraform; `bucket_name` mới là tên thật trên AWS. Các resource tiếp theo quản lý public access, ownership, versioning, encryption và bucket policy của cùng bucket đó.
5. **Tham chiếu** `bucket = aws_s3_bucket.this.id`: Terraform biết cấu hình đó phụ thuộc bucket, nên sẽ sắp thứ tự tự động. Không cần tự viết script tạo rồi sleep chờ bucket trước từng thao tác.
6. **IAM policy** trong dev: writer được GetObject/PutObject và list theo ba prefix Weather; reader chỉ đọc. `for_each` của attachments tạo một attachment cho mỗi role name được truyền vào. Danh sách rỗng nghĩa là policy mới chỉ được định nghĩa, chưa cấp quyền cho role nào.
7. **Outputs**: trả tên bucket, URI và policy ARN sau apply. Outputs không tự đăng nhập AWS hoặc upload JSON.
8. **State/backend**: Terraform ghi mapping giữa resource trong code và tài nguyên thật vào state. Bucket dữ liệu giữ Weather JSON; bucket state giữ sổ quản lý hạ tầng. Hai thứ có trách nhiệm khác nhau và dùng hai state keys riêng cho bootstrap/dev.

Ví dụ đọc một resource:

```hcl
resource "aws_s3_bucket" "this" {
  bucket        = var.bucket_name
  force_destroy = false
  lifecycle {
    prevent_destroy = true
  }
}
```

Đọc thành: quản lý một S3 bucket có tên do input cung cấp; không tự purge objects khi destroy; ngăn Terraform lập kế hoạch phá hủy bucket khi resource protection này còn trong cấu hình. `versioning` giữ các phiên bản object khi ghi đè; nó không tự cấm PutObject cùng key. Ingestion sau này cần unique keys/conditional writes để bảo toàn snapshot.

Chu trình học: viết `.tf` → `init` tải provider/module và khởi tạo backend → `validate` kiểm tra cấu hình → `plan` tính diff → đọc plan → `apply` thực hiện diff. `plan` có đọc AWS, `apply` mới thay đổi tài nguyên; bộ này đã được `plan`/`apply` thật lên account dev (xem cập nhật 2026-11-11 ở đầu tài liệu). `boto3` ở giai đoạn ingestion sẽ upload/download object sau khi bucket và quyền đã được tạo; Terraform quản lý hạ tầng.

Hai root modules:

| Root | Tài nguyên dự kiến |
|---|---|
| `bootstrap/` | Một bucket riêng lưu Terraform state, private, versioning, SSE-S3, ownership và HTTPS policy |
| `environments/dev/` | Một bucket dữ liệu PharmaFlow với cùng cấu hình bảo vệ; hai IAM managed policies Weather reader/writer; optional attachment vào existing roles được chỉ định |

Mỗi bucket gồm 6 Terraform resources (bucket, public access block, ownership, versioning, encryption, policy). Với role sets mặc định rỗng, dev thêm 2 IAM policies và không tự cấp quyền cho principal nào. Chưa có Lambda, SQS, Neon secret, Databricks role hoặc Terraform DynamoDB locking table.

S3 prefixes cho hai Weather endpoints:

```text
s3://pharmaflow-dev-weather-raw-<account-id>-ap-southeast-1/
  raw/open_meteo/weather_forecast/
  raw/open_meteo/historical_forecast/
  raw/open_meteo/historical_weather/
```

Không tạo folder-marker objects; prefix tồn tại khi upload object đầu tiên. Không có expiration/lifecycle xóa snapshot, CORS hay website hosting. `force_destroy=false` và `prevent_destroy=true` trên buckets; SSE-S3 không cần KMS key riêng.

## Cấu trúc

```text
src/infra/terrafrom/
  bootstrap/                  # Tạo bucket state bằng local backend trước
  environments/dev/           # S3 remote backend + bucket dữ liệu/IAM
  modules/private_s3/         # Cấu hình bảo vệ dùng chung cho cả hai bucket
```

## 1. Đăng nhập và xác minh account

Profile là cấu hình AWS CLI trên máy. Terraform AWS provider và boto3 dùng credential chain tiêu chuẩn; không đọc credentials từ `.env` dự án và không ghi access key vào `.tf`/`.tfvars`.

Ví dụ khi đã chọn `my-aws`:

```powershell
aws login --profile my-aws
$env:AWS_PROFILE = "my-aws"
aws sts get-caller-identity --region ap-southeast-1 --no-cli-pager
```

`aws login` áp dụng cho các profile dùng CLI login; profile cấu hình IAM Identity Center/SSO dùng `aws sso login --profile <name>` tương ứng. Không thay auth mode của existing profile khi chưa kiểm tra cấu hình. Nếu terminal đã đặt các biến access key/session token, kiểm tra credential source để tránh dùng nhầm; không in giá trị secret.

Đối chiếu Account và ARN trong STS với account muốn dùng cho PharmaFlow, rồi đặt rõ account guard:

```powershell
$env:TF_VAR_expected_account_id = "<12-digit-account-id-verified>"
```

Provider của cả hai root có `allowed_account_ids`; S3 backend config cũng có account guard riêng. Không dùng account ví dụ `123456789012` để deploy. Không chạy plan/apply khi STS thất bại. STS thành công chứng minh authentication; permissions tạo S3/IAM còn phải kiểm chứng bằng plan/apply và readback.

## 2. Bootstrap bucket Terraform state

Các lệnh bên dưới là quy trình đã dùng để dựng hạ tầng này; tài nguyên bootstrap/dev hiện đã tồn tại trên AWS (xem cập nhật 2026-11-11 ở đầu tài liệu), nên chỉ chạy lại khi dựng môi trường mới. Trên máy hiện có local config điền account thật; bỏ qua các bước Copy-Item nếu file đã tồn tại để tránh chép account mẫu đè lên cấu hình đã chuẩn bị.

Từ repo root, khi chưa có `bootstrap/backend.remote.tf`:

```powershell
terraform -chdir=src/infra/terrafrom/bootstrap init
terraform -chdir=src/infra/terrafrom/bootstrap validate
terraform -chdir=src/infra/terrafrom/bootstrap plan "-out=bootstrap.tfplan"
terraform -chdir=src/infra/terrafrom/bootstrap show bootstrap.tfplan
terraform -chdir=src/infra/terrafrom/bootstrap apply bootstrap.tfplan
terraform -chdir=src/infra/terrafrom/bootstrap output
```

Review plan phải chỉ có resources thuộc bucket `pharmaflow-dev-tfstate-<account-id>-ap-southeast-1`; không có destroy/replace/import tài nguyên khác. Nếu bucket cùng tên đã tồn tại, kiểm tra ownership và Terraform state trước; không tự import hoặc xóa để giải quyết xung đột.

Lần đầu bootstrap dùng local state trong chính root này. State/backup/plan bị ignore bởi Git nhưng là dữ liệu quản lý cần bảo vệ, không phải scratch được phép xóa.

Sau khi bucket state tồn tại, nên chuyển state bootstrap lên chính bucket đó:

```powershell
Copy-Item src/infra/terrafrom/bootstrap/backend.remote.tf.example src/infra/terrafrom/bootstrap/backend.remote.tf
Copy-Item src/infra/terrafrom/bootstrap/bootstrap.backend.hcl.example src/infra/terrafrom/bootstrap/bootstrap.backend.hcl
# Sửa bucket và allowed_account_ids trong bootstrap.backend.hcl thành account thật.
terraform -chdir=src/infra/terrafrom/bootstrap init -migrate-state "-backend-config=bootstrap.backend.hcl"
terraform -chdir=src/infra/terrafrom/bootstrap state list
```

Đọc/xác nhận lời nhắc migration, giữ local backup đến khi xác minh remote object và state list. Không chạy một bootstrap root mới với state rỗng rồi tạo lại bucket đã được quản lý. S3 native state lock (`use_lockfile=true`) dùng object `.tflock`, không cần DynamoDB table.

## 3. Plan và tạo bucket dữ liệu dev

```powershell
Copy-Item src/infra/terrafrom/environments/dev/dev.backend.hcl.example src/infra/terrafrom/environments/dev/dev.backend.hcl
# Sửa bucket và allowed_account_ids theo output bootstrap/account thật.
terraform -chdir=src/infra/terrafrom/environments/dev init -reconfigure "-backend-config=dev.backend.hcl"
terraform -chdir=src/infra/terrafrom/environments/dev validate
terraform -chdir=src/infra/terrafrom/environments/dev plan "-out=storage.tfplan"
terraform -chdir=src/infra/terrafrom/environments/dev show storage.tfplan
terraform -chdir=src/infra/terrafrom/environments/dev apply storage.tfplan
terraform -chdir=src/infra/terrafrom/environments/dev output
```

Provider và backend đều dùng AWS profile của terminal. Backend credential configuration độc lập với provider; không chỉ đặt profile bên trong provider rồi coi backend tự kế thừa. HCL examples chứa account ID mẫu, không có secret. Nếu dùng tfvars local, copy file `.example` và sửa; Git ignore file `.tfvars` thực. Commit `.terraform.lock.hcl` để tái lập provider version, không commit `.terraform/`, tfstate, plan hoặc credentials.

## 4. Quyền thao tác S3

- Writer policy: `GetBucketLocation`, `ListBucket` giới hạn ba prefix, `GetObject` và `PutObject` trong đúng ba prefix Weather. Không có DeleteObject, ACL hay bucket administration. `HeadObject` được authorize bằng GetObject.
- Reader policy: GetBucketLocation, ListBucket theo prefix, GetObject. Chưa phải Unity Catalog trust role; Databricks integration cần trust/external ID và kiểm thử riêng sau này.
- Hai IAM policies được tạo nhưng **chưa attach mặc định** vì chưa chọn identity. Muốn cấp quyền, khai báo tên existing roles trong `weather_writer_role_names`/`weather_reader_role_names` rồi review plan attachment. Role phải tồn tại trong account; dùng role name, không dùng ARN hoặc session ARN.
- Local SSO/login principal có thể có quyền deploy rộng hơn policy writer. Test bằng admin chỉ chứng minh đường S3 hoạt động; xác minh least privilege phải dùng đúng writer/reader role. Không tạo IAM user/access key cho ingestion.
- IAM allow được đánh giá cùng permissions boundary, session policy, SCP và bucket policy; policy được tạo thành công không tự chứng minh principal có effective access.

Quyền deploy cần quản lý cấu hình của đúng hai bucket (CreateBucket, tagging, public access block, ownership, encryption, versioning, bucket policy và các Get tương ứng), cùng IAM CreatePolicy/GetPolicy/ListPolicyVersions/CreatePolicyVersion/SetDefaultPolicyVersion/DeletePolicyVersion và tags cho hai policy Weather. Nếu attach existing roles, cần GetRole/AttachRolePolicy/ListAttachedRolePolicies; thao tác tháo attachment cần DetachRolePolicy. Có thể giới hạn bucket/policy ARNs theo các tên trong code. `iam:PassRole` không cần chỉ để tạo bucket/policy và attach managed policy vào existing role.

Backend principal cần ListBucket phù hợp state prefix, GetObject/PutObject cho hai state keys `pharmaflow/dev/bootstrap/terraform.tfstate`, `pharmaflow/dev/storage/terraform.tfstate`, cùng GetObject/PutObject/DeleteObject cho các `.tflock` tương ứng. Backend thường không cần DeleteObject trên state file. Không cấp quyền Weather writer lên bucket state.

## 5. Kiểm tra offline và sau deploy

Windows PowerShell 5.1 có thể tách `-out=bootstrap.tfplan` không có dấu nháy thành hai arguments `-out=bootstrap` và `.tfplan`, dẫn tới `Too many command line arguments`. Đã tái hiện bằng native argv trên máy. Dùng `"-out=bootstrap.tfplan"` và quote tương tự với `"-backend-config=dev.backend.hcl"`. `show` báo file không tồn tại là lỗi tiếp theo khi plan chưa tạo được file, không phải bằng chứng state bị hỏng.

Các kiểm tra offline không cần AWS credentials:

```powershell
terraform fmt -check -recursive src/infra/terrafrom
terraform -chdir=src/infra/terrafrom/modules/private_s3 init -backend=false
terraform -chdir=src/infra/terrafrom/modules/private_s3 validate
terraform -chdir=src/infra/terrafrom/modules/private_s3 test
terraform -chdir=src/infra/terrafrom/bootstrap init -backend=false
terraform -chdir=src/infra/terrafrom/bootstrap validate
terraform -chdir=src/infra/terrafrom/environments/dev init -backend=false
terraform -chdir=src/infra/terrafrom/environments/dev validate
terraform -chdir=src/infra/terrafrom/environments/dev test
```

`terraform test` dùng mock provider, `command=plan`; không tạo tài nguyên AWS. Kiểm tra cấu hình private/versioning/encryption/ownership/HTTPS và policy scopes. Sau khi đã cấu hình remote backend, không thay init/backend hay xóa state chỉ để chạy offline tests.

Chạy các lệnh lần lượt. Lượt kiểm tra ban đầu chạy nhiều AWS provider processes song song đã gặp Windows out-of-memory; chạy lại tuần tự với `GOMEMLIMIT=768MiB` và `GOGC=50` trong terminal kiểm tra đã giải quyết được. Các biến này chỉ điều chỉnh bộ nhớ của Go process, không đổi cấu hình Windows hoặc AWS.

Sau apply cần read back:

```powershell
$bucket = terraform -chdir=src/infra/terrafrom/environments/dev output -raw data_bucket_name
aws s3api get-bucket-location --bucket $bucket
aws s3api get-public-access-block --bucket $bucket
aws s3api get-bucket-ownership-controls --bucket $bucket
aws s3api get-bucket-versioning --bucket $bucket
aws s3api get-bucket-encryption --bucket $bucket
aws s3api get-bucket-policy --bucket $bucket
```

Sau khi role được cấp quyền, upload payload nhỏ gắn `data_origin=SYNTHETIC` vào `raw/open_meteo/weather_forecast/_smoke/<unique-id>/`, GetObject lại, so SHA-256 và xác minh VersionId. Giữ smoke object có provenance; không tự cấp DeleteObject chỉ để dọn test. Test reader không ghi được, writer không ghi ngoài prefix; kiểm tra IAM effective permissions trong account được phép. Chạy plan lại để xác nhận no changes.

## Nguồn và liên kết

- [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3): bootstrap backend, account guard, state locking và permissions.
- [Terraform AWS S3 resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket).
- [Weather ingestion plan](../../../docs/architecture/pharmaflow-weather-ingestion-v1-implementation-plan.md).

Không chạy `destroy` để thử rollback. Tắt consumer/ingestion khi cần điều tra; giữ state và dữ liệu. Các protection trong Terraform không bảo vệ tài nguyên khi bị xóa trực tiếp ngoài Terraform hoặc khi cấu hình bị gỡ khỏi state; IAM/quy trình vận hành vẫn phải giữ giới hạn tương ứng.
