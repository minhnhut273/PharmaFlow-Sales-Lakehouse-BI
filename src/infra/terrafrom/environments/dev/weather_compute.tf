# P3: Weather compute (Lambda planner/worker/reconciler, 5 SQS queues, DynamoDB control state,
# EventBridge Scheduler, CloudWatch alarms). Everything is gated by enable_weather_compute (default false).
# Code is deployed separately by scripts/weather/deploy_code.ps1; Terraform only creates the shells.

variable "enable_weather_compute" {
  description = "Create the P3 weather compute stack (Lambda, SQS, DynamoDB, Scheduler, alarms)."
  type        = bool
  default     = false
}

variable "weather_compute_schedules_enabled" {
  description = "ENABLE the 06:00 daily planner and 5-minute reconciler schedules (P4). P3 keeps them DISABLED."
  type        = bool
  default     = false
}

variable "weather_daily_cohort_id" {
  description = "Cohort ID scheduled daily at 06:00 VN (pilot in P4; full_network in P5)."
  type        = string
  default     = "full_network"
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]+$", var.weather_daily_cohort_id))
    error_message = "weather_daily_cohort_id must be an alphanumeric/underscore/dash cohort name."
  }
}

variable "weather_neon_dsn_param_name" {
  description = "SSM SecureString parameter holding the SELECT-only Neon DSN. Created outside Terraform (no secret in state)."
  type        = string
  default     = "/pharmaflow/dev/weather/neon_dsn"
  validation {
    condition     = can(regex("^/[A-Za-z0-9_./-]+$", var.weather_neon_dsn_param_name))
    error_message = "Use an absolute SSM parameter path."
  }
}

locals {
  wc         = var.enable_weather_compute ? 1 : 0
  wc_prefix  = "pharmaflow-dev-weather"
  account_id = var.expected_account_id
  region     = "ap-southeast-1"

  lambda_specs = {
    planner    = { memory = 256, timeout = 180, handler = "src.weather.handlers.planner_handler" }
    worker     = { memory = 256, timeout = 150, handler = "src.weather.handlers.worker_handler" }
    reconciler = { memory = 256, timeout = 60, handler = "src.weather.handlers.reconciler_handler" }
  }
  # AWS guidance: source queue visibility timeout >= 6x the consuming function timeout.
  queue_visibility_seconds = 6 * local.lambda_specs.worker.timeout
  max_receive_count        = 5

  main_queues = toset(["daily", "backfill"])
  dlq_names   = toset(["daily", "backfill", "scheduler"])

  neon_param_arn = "arn:aws:ssm:${local.region}:${local.account_id}:parameter${var.weather_neon_dsn_param_name}"
  schedule_state = var.weather_compute_schedules_enabled ? "ENABLED" : "DISABLED"
}

# ------------------------------------------------------------------ DynamoDB

resource "aws_dynamodb_table" "weather_control" {
  count                       = local.wc
  name                        = "${local.wc_prefix}-control"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "pk"
  range_key                   = "sk"
  deletion_protection_enabled = true

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "gsi1pk"
    type = "S"
  }

  # Sparse index: only non-terminal RUN#<id>/META items carry gsi1pk = "ACTIVE".
  global_secondary_index {
    name            = "active_runs"
    projection_type = "ALL"
    key_schema {
      attribute_name = "gsi1pk"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "pk"
      key_type       = "RANGE"
    }
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = false # false = AWS owned key (default encryption at rest); no KMS cost
  }
}

# ---------------------------------------------------------------------- SQS

resource "aws_sqs_queue" "weather_dlq" {
  for_each                  = var.enable_weather_compute ? local.dlq_names : toset([])
  name                      = "${local.wc_prefix}-${each.key}-dlq"
  message_retention_seconds = 1209600 # 14 days
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "weather_main" {
  for_each                   = var.enable_weather_compute ? local.main_queues : toset([])
  name                       = "${local.wc_prefix}-${each.key}"
  visibility_timeout_seconds = local.queue_visibility_seconds
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.weather_dlq[each.key].arn
    maxReceiveCount     = local.max_receive_count
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "weather_dlq" {
  for_each  = var.enable_weather_compute ? local.main_queues : toset([])
  queue_url = aws_sqs_queue.weather_dlq[each.key].id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.weather_main[each.key].arn]
  })
}

# ---------------------------------------------------------------------- IAM

locals {
  # Trust policies as plain JSON (keeps mock-provider tests meaningful).
  lambda_trust_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = local.account_id } }
    }]
  })
  scheduler_trust_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = local.account_id } }
    }]
  })
}

resource "aws_iam_role" "weather_lambda" {
  for_each             = var.enable_weather_compute ? local.lambda_specs : {}
  name                 = "${local.wc_prefix}-${each.key}-lambda"
  description          = "Execution role for the weather ${each.key} Lambda (P3)."
  assume_role_policy   = local.lambda_trust_policy
  max_session_duration = 3600
}

resource "aws_cloudwatch_log_group" "weather_lambda" {
  for_each          = var.enable_weather_compute ? local.lambda_specs : {}
  name              = "/aws/lambda/${local.wc_prefix}-${each.key}"
  retention_in_days = 30
}

# All three functions read/write raw weather objects through the existing writer policy (no DeleteObject).
resource "aws_iam_role_policy_attachment" "weather_lambda_s3" {
  for_each   = var.enable_weather_compute ? local.lambda_specs : {}
  role       = aws_iam_role.weather_lambda[each.key].name
  policy_arn = aws_iam_policy.weather_writer.arn
}

locals {
  table_arn = var.enable_weather_compute ? aws_dynamodb_table.weather_control[0].arn : ""

  lambda_statements = var.enable_weather_compute ? {
    planner = [
      { Sid = "ReadNeonDsnParameter", Effect = "Allow", Action = ["ssm:GetParameter"], Resource = [local.neon_param_arn] },
      { Sid = "ControlState", Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"], Resource = [local.table_arn] },
      { Sid = "DispatchTasks", Effect = "Allow", Action = ["sqs:SendMessage"], Resource = [for q in aws_sqs_queue.weather_main : q.arn] },
    ]
    worker = [
      { Sid = "ControlState", Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:ConditionCheckItem"], Resource = [local.table_arn] },
      { Sid = "ConsumeTasks", Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes"], Resource = [for q in aws_sqs_queue.weather_main : q.arn] },
    ]
    reconciler = [
      { Sid = "ControlState", Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Query"], Resource = [local.table_arn, "${local.table_arn}/index/active_runs"] },
      { Sid = "DrainDeadLetters", Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = [for q in aws_sqs_queue.weather_dlq : q.arn] },
    ]
  } : {}
}

resource "aws_iam_role_policy" "weather_lambda" {
  for_each = var.enable_weather_compute ? local.lambda_specs : {}
  name     = "${local.wc_prefix}-${each.key}-inline"
  role     = aws_iam_role.weather_lambda[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.lambda_statements[each.key], [{
      Sid      = "WriteOwnLogs"
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = ["${aws_cloudwatch_log_group.weather_lambda[each.key].arn}:*"]
    }])
  })
}

# ------------------------------------------------------------------- Lambda

# Placeholder code for the first create only; real code is pushed by deploy_code.ps1 and ignored afterwards.
data "archive_file" "weather_placeholder" {
  count       = local.wc
  type        = "zip"
  output_path = "${path.module}/.terraform/weather-placeholder.zip"
  source {
    filename = "src/weather/handlers.py"
    content  = <<-PY
      def _placeholder(event, context):
          raise RuntimeError("placeholder code: run scripts/weather/deploy_code.ps1")
      planner_handler = worker_handler = reconciler_handler = _placeholder
    PY
  }
}

resource "aws_lambda_function" "weather" {
  for_each         = var.enable_weather_compute ? local.lambda_specs : {}
  function_name    = "${local.wc_prefix}-${each.key}"
  description      = "PharmaFlow weather ${each.key} (P3)."
  role             = aws_iam_role.weather_lambda[each.key].arn
  runtime          = "python3.12"
  architectures    = ["x86_64"]
  handler          = each.value.handler
  memory_size      = each.value.memory
  timeout          = each.value.timeout
  filename         = data.archive_file.weather_placeholder[0].output_path
  source_code_hash = data.archive_file.weather_placeholder[0].output_base64sha256

  environment {
    variables = {
      WEATHER_RUNTIME            = "lambda"
      WEATHER_S3_BUCKET          = local.bucket_name
      WEATHER_TABLE              = aws_dynamodb_table.weather_control[0].name
      WEATHER_DAILY_QUEUE_URL    = aws_sqs_queue.weather_main["daily"].id
      WEATHER_BACKFILL_QUEUE_URL = aws_sqs_queue.weather_main["backfill"].id
      WEATHER_DAILY_DLQ_URL      = aws_sqs_queue.weather_dlq["daily"].id
      WEATHER_BACKFILL_DLQ_URL   = aws_sqs_queue.weather_dlq["backfill"].id
      WEATHER_SCHEDULER_DLQ_URL  = aws_sqs_queue.weather_dlq["scheduler"].id
      WEATHER_NEON_DSN_PARAM     = each.key == "planner" ? var.weather_neon_dsn_param_name : ""
    }
  }

  depends_on = [aws_cloudwatch_log_group.weather_lambda, aws_iam_role_policy.weather_lambda]

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

resource "aws_lambda_function_event_invoke_config" "weather" {
  for_each                     = var.enable_weather_compute ? toset(["planner", "reconciler"]) : toset([])
  function_name                = aws_lambda_function.weather[each.key].function_name
  maximum_retry_attempts       = each.key == "planner" ? 1 : 0
  maximum_event_age_in_seconds = 3600
}

resource "aws_lambda_event_source_mapping" "weather_worker" {
  for_each                = var.enable_weather_compute ? local.main_queues : toset([])
  event_source_arn        = aws_sqs_queue.weather_main[each.key].arn
  function_name           = aws_lambda_function.weather["worker"].arn
  batch_size              = 1
  function_response_types = ["ReportBatchItemFailures"]
  scaling_config {
    maximum_concurrency = 2
  }
}

# ---------------------------------------------------------------- Scheduler

resource "aws_iam_role" "weather_scheduler" {
  count              = local.wc
  name               = "${local.wc_prefix}-scheduler"
  description        = "EventBridge Scheduler role: invoke weather planner/reconciler only (P3)."
  assume_role_policy = local.scheduler_trust_policy
}

resource "aws_iam_role_policy" "weather_scheduler" {
  count = local.wc
  name  = "${local.wc_prefix}-scheduler-inline"
  role  = aws_iam_role.weather_scheduler[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Sid = "InvokeWeatherFunctions", Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = [aws_lambda_function.weather["planner"].arn, aws_lambda_function.weather["reconciler"].arn] },
      { Sid = "SchedulerDeadLetter", Effect = "Allow", Action = ["sqs:SendMessage"], Resource = [aws_sqs_queue.weather_dlq["scheduler"].arn] },
    ]
  })
}

resource "aws_scheduler_schedule" "weather" {
  for_each = var.enable_weather_compute ? {
    planner_daily = {
      expression = "cron(0 6 * * ? *)"
      function   = "planner"
      input = jsonencode({
        mode        = "daily_forecast"
        cohort_id   = var.weather_daily_cohort_id
        schedule_id = "daily-0600-vn"
      })
    }
    reconciler = {
      expression = "rate(5 minutes)"
      function   = "reconciler"
      input      = jsonencode({ source = "scheduler" })
    }
  } : {}
  name                         = "${local.wc_prefix}-${replace(each.key, "_", "-")}"
  group_name                   = "default"
  schedule_expression          = each.value.expression
  schedule_expression_timezone = "Asia/Ho_Chi_Minh"
  state                        = local.schedule_state

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.weather[each.value.function].arn
    role_arn = aws_iam_role.weather_scheduler[0].arn
    input    = each.value.input
    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
    dead_letter_config {
      arn = aws_sqs_queue.weather_dlq["scheduler"].arn
    }
  }
}

# ------------------------------------------------------------------- Alarms
# No alarm actions in P3 (visible in CloudWatch only). Notifications are a P4 decision.

resource "aws_cloudwatch_metric_alarm" "weather_dlq_not_empty" {
  for_each            = var.enable_weather_compute ? local.dlq_names : toset([])
  alarm_name          = "${local.wc_prefix}-${each.key}-dlq-not-empty"
  alarm_description   = "Messages are waiting in ${aws_sqs_queue.weather_dlq[each.key].name}."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.weather_dlq[each.key].name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "weather_lambda_errors" {
  for_each            = var.enable_weather_compute ? local.lambda_specs : {}
  alarm_name          = "${local.wc_prefix}-${each.key}-errors"
  alarm_description   = "The weather ${each.key} Lambda reported errors."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.weather[each.key].function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

# ------------------------------------------------------------------ Outputs

output "weather_compute" {
  value = var.enable_weather_compute ? {
    table           = aws_dynamodb_table.weather_control[0].name
    functions       = { for k, f in aws_lambda_function.weather : k => f.function_name }
    queues          = { for k, q in aws_sqs_queue.weather_main : k => q.id }
    dead_letters    = { for k, q in aws_sqs_queue.weather_dlq : k => q.id }
    neon_dsn_param  = var.weather_neon_dsn_param_name
    schedules_state = local.schedule_state
  } : null
}
