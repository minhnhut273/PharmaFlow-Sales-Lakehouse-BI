# Offline mock tests for the S3 -> Databricks Managed Volume sync Lambda bridge.
mock_provider "aws" {
  mock_resource "aws_iam_policy" {
    defaults = { arn = "arn:aws:iam::123456789012:policy/mock-policy" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/mock-role" }
  }
  mock_resource "aws_lambda_function" {
    defaults = { arn = "arn:aws:lambda:ap-southeast-1:123456789012:function:mock-bridge-fn" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = {
      arn = "arn:aws:sqs:ap-southeast-1:123456789012:mock-queue"
      id  = "https://sqs.ap-southeast-1.amazonaws.com/123456789012/mock-queue"
      url = "https://sqs.ap-southeast-1.amazonaws.com/123456789012/mock-queue"
    }
  }
  mock_resource "aws_dynamodb_table" {
    defaults = { arn = "arn:aws:dynamodb:ap-southeast-1:123456789012:table/mock-table" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:ap-southeast-1:123456789012:log-group:/aws/lambda/mock" }
  }
}

variables {
  expected_account_id                        = "123456789012"
  weather_writer_role_names                  = []
  weather_reader_role_names                  = []
  weather_local_writer_principal_arns        = []
  enable_weather_compute                     = false
  weather_compute_schedules_enabled          = false
  enable_databricks_volume_bridge            = false
  databricks_volume_bridge_schedules_enabled = false
}

run "bridge_disabled_by_default" {
  command = plan
  assert {
    condition = (
      length(aws_lambda_function.databricks_weather_sync) == 0
      && length(aws_scheduler_schedule.databricks_weather_sync) == 0
    )
    error_message = "Databricks volume bridge must be disabled unless explicitly opted in."
  }
}

run "bridge_enabled_least_privilege" {
  command = apply
  variables {
    enable_weather_compute                     = true
    enable_databricks_volume_bridge            = true
    databricks_volume_bridge_schedules_enabled = true
  }

  assert {
    condition     = aws_lambda_function.databricks_weather_sync[0].timeout == 300 && aws_lambda_function.databricks_weather_sync[0].memory_size == 512
    error_message = "Bridge Lambda must use 512MB and 300s timeout."
  }
  assert {
    condition     = aws_iam_role_policy_attachment.databricks_weather_sync_s3[0].policy_arn == aws_iam_policy.weather_reader.arn
    error_message = "Bridge Lambda must use the read-only weather_reader S3 policy."
  }
  assert {
    condition = flatten([
      for s in jsondecode(aws_iam_role_policy.databricks_weather_sync_inline[0].policy).Statement :
      s.Resource if contains(s.Action, "ssm:GetParameter")
    ]) == ["arn:aws:ssm:ap-southeast-1:123456789012:parameter/pharmaflow/dev/databricks/weather_sync_pat"]
    error_message = "Bridge Lambda may read only the Databricks PAT SSM parameter, not Neon DSN."
  }
  assert {
    condition     = aws_scheduler_schedule.databricks_weather_sync[0].schedule_expression == "cron(18 6 * * ? *)" && aws_scheduler_schedule.databricks_weather_sync[0].schedule_expression_timezone == "Asia/Ho_Chi_Minh" && aws_scheduler_schedule.databricks_weather_sync[0].state == "ENABLED"
    error_message = "Bridge scheduler must run at 06:18 Asia/Ho_Chi_Minh when enabled."
  }
}
