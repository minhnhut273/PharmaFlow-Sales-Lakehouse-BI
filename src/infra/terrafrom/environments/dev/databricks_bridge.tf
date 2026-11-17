# Option 2 bridge: AWS Lambda + EventBridge Scheduler syncing accepted Weather S3 files
# to Databricks Free Edition Managed Volume at 06:18 VN (before Databricks job at 06:25 VN).

variable "enable_databricks_volume_bridge" {
  description = "Create the standalone AWS Lambda + Scheduler that mirrors accepted Weather S3 objects into Databricks Managed Volume."
  type        = bool
  default     = false
}

variable "databricks_volume_bridge_schedules_enabled" {
  description = "ENABLE the 06:18 VN EventBridge schedule for Databricks volume sync."
  type        = bool
  default     = false
}

variable "databricks_host" {
  description = "Clean Databricks Workspace URL (no query parameters)."
  type        = string
  default     = "https://dbc-46e38b03-6d3f.cloud.databricks.com"
}

variable "databricks_token_param_name" {
  description = "SSM SecureString parameter holding the Databricks PAT (created outside Terraform)."
  type        = string
  default     = "/pharmaflow/dev/databricks/weather_sync_pat"
}

variable "databricks_catalog" {
  description = "Target Unity Catalog name in Databricks."
  type        = string
  default     = "pharmaflow_dev"
}

variable "databricks_schema" {
  description = "Target Unity Catalog schema hosting the raw weather volume."
  type        = string
  default     = "bronze_weather"
}

variable "databricks_volume" {
  description = "Target Unity Catalog Managed Volume name."
  type        = string
  default     = "weather_raw"
}

locals {
  dbx_bridge       = var.enable_databricks_volume_bridge ? 1 : 0
  dbx_bridge_name  = "pharmaflow-dev-databricks-weather-sync"
  dbx_param_arn    = "arn:aws:ssm:${local.region}:${local.account_id}:parameter${var.databricks_token_param_name}"
  dbx_sched_state  = var.databricks_volume_bridge_schedules_enabled ? "ENABLED" : "DISABLED"
  dbx_source_file  = "${path.module}/../../../../pipeline/databricks/src/bronze/aws_volume_sync_lambda.py"
}

data "archive_file" "databricks_weather_sync" {
  count       = local.dbx_bridge
  type        = "zip"
  output_path = "${path.module}/.terraform/databricks-weather-sync.zip"
  source {
    content  = file(local.dbx_source_file)
    filename = "lambda_handler.py"
  }
}

resource "aws_cloudwatch_log_group" "databricks_weather_sync" {
  count             = local.dbx_bridge
  name              = "/aws/lambda/${local.dbx_bridge_name}"
  retention_in_days = 30
}

resource "aws_iam_role" "databricks_weather_sync" {
  count                = local.dbx_bridge
  name                 = "${local.dbx_bridge_name}-lambda"
  description          = "Least-privilege role for S3 -> Databricks Managed Volume sync Lambda."
  assume_role_policy   = local.lambda_trust_policy
  max_session_duration = 3600
}

# Attach strictly read-only S3 policy (three Weather prefixes only; no PutObject/DeleteObject).
resource "aws_iam_role_policy_attachment" "databricks_weather_sync_s3" {
  count      = local.dbx_bridge
  role       = aws_iam_role.databricks_weather_sync[0].name
  policy_arn = aws_iam_policy.weather_reader.arn
}

resource "aws_iam_role_policy" "databricks_weather_sync_inline" {
  count = local.dbx_bridge
  name  = "${local.dbx_bridge_name}-inline"
  role  = aws_iam_role.databricks_weather_sync[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadDatabricksPatParameter"
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = [local.dbx_param_arn]
      },
      {
        Sid      = "WriteOwnLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["${aws_cloudwatch_log_group.databricks_weather_sync[0].arn}:*"]
      }
    ]
  })
}

resource "aws_lambda_function" "databricks_weather_sync" {
  count            = local.dbx_bridge
  function_name    = local.dbx_bridge_name
  description      = "Delta sync accepted Open-Meteo S3 objects into Databricks Free Edition Managed Volume."
  role             = aws_iam_role.databricks_weather_sync[0].arn
  runtime          = "python3.12"
  architectures    = ["x86_64"]
  handler          = "lambda_handler.lambda_handler"
  memory_size      = 512
  timeout          = 300
  filename         = data.archive_file.databricks_weather_sync[0].output_path
  source_code_hash = data.archive_file.databricks_weather_sync[0].output_base64sha256

  environment {
    variables = {
      WEATHER_S3_BUCKET     = local.bucket_name
      DATABRICKS_HOST       = var.databricks_host
      DATABRICKS_TOKEN_PARAM = var.databricks_token_param_name
      DATABRICKS_CATALOG    = var.databricks_catalog
      DATABRICKS_SCHEMA     = var.databricks_schema
      DATABRICKS_VOLUME     = var.databricks_volume
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.databricks_weather_sync,
    aws_iam_role_policy.databricks_weather_sync_inline,
    aws_iam_role_policy_attachment.databricks_weather_sync_s3,
  ]
}

resource "aws_iam_role" "databricks_bridge_scheduler" {
  count              = local.dbx_bridge
  name               = "${local.dbx_bridge_name}-scheduler"
  description        = "EventBridge Scheduler role: invoke Databricks volume sync Lambda only."
  assume_role_policy = local.scheduler_trust_policy
}

resource "aws_iam_role_policy" "databricks_bridge_scheduler" {
  count = local.dbx_bridge
  name  = "${local.dbx_bridge_name}-scheduler-inline"
  role  = aws_iam_role.databricks_bridge_scheduler[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [{
        Sid      = "InvokeBridgeLambda"
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = [aws_lambda_function.databricks_weather_sync[0].arn]
      }],
      var.enable_weather_compute ? [{
        Sid      = "SchedulerDeadLetter"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = [aws_sqs_queue.weather_dlq["scheduler"].arn]
      }] : []
    )
  })
}

resource "aws_scheduler_schedule" "databricks_weather_sync" {
  count                        = local.dbx_bridge
  name                         = local.dbx_bridge_name
  group_name                   = "default"
  schedule_expression          = "cron(18 6 * * ? *)"
  schedule_expression_timezone = "Asia/Ho_Chi_Minh"
  state                        = local.dbx_sched_state

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.databricks_weather_sync[0].arn
    role_arn = aws_iam_role.databricks_bridge_scheduler[0].arn
    input = jsonencode({
      mode        = "daily"
      recent_days = 2
      max_workers = 12
    })
    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 1
    }
    dynamic "dead_letter_config" {
      for_each = var.enable_weather_compute ? [1] : []
      content {
        arn = aws_sqs_queue.weather_dlq["scheduler"].arn
      }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "databricks_weather_sync_errors" {
  count               = local.dbx_bridge
  alarm_name          = "${local.dbx_bridge_name}-errors"
  alarm_description   = "The S3 -> Databricks Managed Volume sync Lambda reported errors."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.databricks_weather_sync[0].function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

output "databricks_weather_sync_function_name" {
  value = var.enable_databricks_volume_bridge ? aws_lambda_function.databricks_weather_sync[0].function_name : null
}
