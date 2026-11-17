# PharmaFlow infrastructure

Bộ Terraform S3 dev nằm tại [terrafrom/](terrafrom/README.md), giữ tên thư mục đã có trên máy. Region `ap-southeast-1`; account `522346104596`, profile `my-aws` đã được kiểm tra read-only ngày 2026-11-07.

Mở README của bộ Terraform để học provider, variables, resource, module, IAM, backend/state và thứ tự init → validate → plan → apply. Bộ Terraform này đã được apply lên account dev (bucket state, bucket dữ liệu Weather, 2 IAM policy; cập nhật 2026-11-11, chi tiết trong README của bộ). Chưa gắn policy cho role nào.
