# P3 weather compute: offline mock tests. `command = apply` only applies against the mock provider.
mock_provider "aws" {
  mock_resource "aws_iam_policy" {
    defaults = { arn = "arn:aws:iam::123456789012:policy/mock-policy" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/mock-role" }
  }
  mock_resource "aws_lambda_function" {
    defaults = { arn = "arn:aws:lambda:ap-southeast-1:123456789012:function:mock-fn" }
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
  expected_account_id                 = "123456789012"
  weather_writer_role_names           = []
  weather_reader_role_names           = []
  weather_local_writer_principal_arns = []
  enable_weather_compute              = false
  weather_compute_schedules_enabled   = false
}

run "compute_disabled_by_default" {
  command = plan
  assert {
    condition = (
      length(aws_lambda_function.weather) == 0 && length(aws_sqs_queue.weather_main) == 0
      && length(aws_sqs_queue.weather_dlq) == 0 && length(aws_dynamodb_table.weather_control) == 0
      && length(aws_scheduler_schedule.weather) == 0 && length(aws_iam_role.weather_lambda) == 0
    )
    error_message = "No compute resource may exist unless enable_weather_compute = true."
  }
}

run "compute_enabled_shapes" {
  command = apply
  variables {
    enable_weather_compute = true
  }

  assert {
    condition     = length(aws_lambda_function.weather) == 3 && length(aws_sqs_queue.weather_main) == 2 && length(aws_sqs_queue.weather_dlq) == 3
    error_message = "Expect 3 functions, 2 main queues and 3 dead-letter queues."
  }
  assert {
    condition     = aws_dynamodb_table.weather_control[0].billing_mode == "PAY_PER_REQUEST" && aws_dynamodb_table.weather_control[0].hash_key == "pk" && aws_dynamodb_table.weather_control[0].range_key == "sk"
    error_message = "Control table must be on-demand with pk/sk keys."
  }
  assert {
    condition     = alltrue([for q in aws_sqs_queue.weather_main : jsondecode(q.redrive_policy).maxReceiveCount == 5])
    error_message = "Main queues must redrive to their DLQ after 5 receives."
  }
  assert {
    condition     = alltrue([for q in aws_sqs_queue.weather_main : q.visibility_timeout_seconds >= 6 * aws_lambda_function.weather["worker"].timeout])
    error_message = "Visibility timeout must be at least 6x the worker timeout."
  }
  assert {
    condition = alltrue([for m in aws_lambda_event_source_mapping.weather_worker :
      m.batch_size == 1 && m.scaling_config[0].maximum_concurrency == 2 && contains(tolist(m.function_response_types), "ReportBatchItemFailures")
    ])
    error_message = "Worker mappings: batch 1, max concurrency 2, ReportBatchItemFailures."
  }
  assert {
    condition     = alltrue([for s in aws_scheduler_schedule.weather : s.state == "DISABLED"])
    error_message = "Schedules must stay DISABLED in P3."
  }
  assert {
    condition     = aws_scheduler_schedule.weather["planner_daily"].schedule_expression == "cron(0 6 * * ? *)" && aws_scheduler_schedule.weather["planner_daily"].schedule_expression_timezone == "Asia/Ho_Chi_Minh"
    error_message = "Daily planner runs at 06:00 Asia/Ho_Chi_Minh."
  }
  assert {
    condition     = jsondecode(aws_scheduler_schedule.weather["planner_daily"].target[0].input).cohort_id == "full_network" && aws_lambda_function.weather["planner"].timeout == 180
    error_message = "P5 default schedule uses full_network cohort and 180s planner timeout."
  }
  assert {
    condition = alltrue(flatten([for k in ["worker", "reconciler"] : [
      for s in jsondecode(aws_iam_role_policy.weather_lambda[k].policy).Statement : [for a in s.Action : !startswith(a, "ssm:")]
    ]]))
    error_message = "Worker and reconciler must not read SSM (Neon DSN)."
  }
  assert {
    condition = alltrue(flatten([for k, p in aws_iam_role_policy.weather_lambda : [
      for s in jsondecode(p.policy).Statement : [for a in s.Action : !startswith(a, "s3:") && a != "*" && !endswith(a, ":*")]
    ]]))
    error_message = "Inline policies must not grant S3 or wildcard actions (S3 comes only from the writer policy)."
  }
  assert {
    condition = toset(flatten([for s in jsondecode(aws_iam_role_policy.weather_lambda["planner"].policy).Statement : [
      for a in s.Action : a if startswith(a, "sqs:")
    ]])) == toset(["sqs:SendMessage"])
    error_message = "Planner may only send messages."
  }
  assert {
    condition = flatten([for s in jsondecode(aws_iam_role_policy.weather_lambda["planner"].policy).Statement :
    s.Resource if contains(s.Action, "ssm:GetParameter")]) == ["arn:aws:ssm:ap-southeast-1:123456789012:parameter/pharmaflow/dev/weather/neon_dsn"]
    error_message = "Planner reads exactly one SSM parameter."
  }
  assert {
    condition     = length(aws_iam_role_policy_attachment.weather_lambda_s3) == 3 && alltrue([for a in aws_iam_role_policy_attachment.weather_lambda_s3 : a.policy_arn == aws_iam_policy.weather_writer.arn])
    error_message = "Each function role gets the weather writer policy (no DeleteObject)."
  }
  assert {
    condition     = aws_lambda_function.weather["planner"].environment[0].variables["WEATHER_NEON_DSN_PARAM"] != "" && aws_lambda_function.weather["worker"].environment[0].variables["WEATHER_NEON_DSN_PARAM"] == ""
    error_message = "Only the planner knows the DSN parameter name."
  }
  assert {
    condition     = length(aws_cloudwatch_metric_alarm.weather_dlq_not_empty) == 3 && length(aws_cloudwatch_metric_alarm.weather_lambda_errors) == 3
    error_message = "Expect 3 DLQ alarms and 3 Lambda error alarms."
  }
}

run "schedules_flag_enables" {
  command = apply
  variables {
    enable_weather_compute            = true
    weather_compute_schedules_enabled = true
  }
  assert {
    condition     = alltrue([for s in aws_scheduler_schedule.weather : s.state == "ENABLED"])
    error_message = "The P4 flag must enable both schedules."
  }
}
