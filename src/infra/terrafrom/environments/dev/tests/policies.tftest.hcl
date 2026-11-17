mock_provider "aws" {}

# Pin optional inputs so local terraform.tfvars (auto-loaded by `terraform test`) cannot change results.
variables {
  weather_writer_role_names           = []
  weather_reader_role_names           = []
  weather_local_writer_principal_arns = []
}

run "weather_policy_boundaries" {
  command = plan
  variables {
    expected_account_id = "123456789012"
  }

  assert {
    condition     = length(aws_iam_role_policy_attachment.weather_writer) == 0 && length(aws_iam_role_policy_attachment.weather_reader) == 0
    error_message = "No IAM principal receives access implicitly."
  }
  assert {
    condition     = length(aws_iam_role.weather_local_writer) == 0 && length(aws_iam_role_policy_attachment.weather_local_writer) == 0
    error_message = "The local writer role must not exist unless principals are listed explicitly."
  }
  assert {
    condition     = toset(jsondecode(aws_iam_policy.weather_writer.policy).Statement[2].Action) == toset(["s3:GetObject", "s3:PutObject"])
    error_message = "Writer must have only GetObject/PutObject object permissions."
  }
  assert {
    condition     = jsondecode(aws_iam_policy.weather_reader.policy).Statement[2].Action == ["s3:GetObject"]
    error_message = "Reader must not write or delete objects."
  }
  assert {
    condition = toset(jsondecode(aws_iam_policy.weather_writer.policy).Statement[2].Resource) == toset([
      "arn:aws:s3:::pharmaflow-dev-weather-raw-123456789012-ap-southeast-1/raw/open_meteo/weather_forecast/*",
      "arn:aws:s3:::pharmaflow-dev-weather-raw-123456789012-ap-southeast-1/raw/open_meteo/historical_forecast/*",
      "arn:aws:s3:::pharmaflow-dev-weather-raw-123456789012-ap-southeast-1/raw/open_meteo/historical_weather/*"
    ])
    error_message = "Writer object access must stay inside the three Weather prefixes."
  }
  assert {
    condition = toset(jsondecode(aws_iam_policy.weather_writer.policy).Statement[1].Condition.StringLike["s3:prefix"]) == toset([
      "raw/open_meteo/weather_forecast/",
      "raw/open_meteo/weather_forecast/*",
      "raw/open_meteo/historical_forecast/",
      "raw/open_meteo/historical_forecast/*",
      "raw/open_meteo/historical_weather/",
      "raw/open_meteo/historical_weather/*"
    ])
    error_message = "ListBucket must stay scoped to the Weather prefixes."
  }
}

run "explicit_writer_attachment" {
  command = plan
  variables {
    expected_account_id       = "123456789012"
    weather_writer_role_names = ["pharmaflow-dev-weather-worker"]
  }
  assert {
    condition     = length(aws_iam_role_policy_attachment.weather_writer) == 1 && length(aws_iam_role_policy_attachment.weather_reader) == 0
    error_message = "An explicit writer role must receive exactly one writer attachment."
  }
  assert {
    condition     = aws_iam_role_policy_attachment.weather_writer["pharmaflow-dev-weather-worker"].role == "pharmaflow-dev-weather-worker"
    error_message = "Policy must attach to the explicitly named role."
  }
}

run "invalid_account_input" {
  command = plan
  variables {
    expected_account_id = "invalid"
  }
  expect_failures = [var.expected_account_id]
}

run "local_writer_role_trusts_only_listed_principal" {
  command = plan
  variables {
    expected_account_id                 = "123456789012"
    weather_local_writer_principal_arns = ["arn:aws:iam::123456789012:user/dev-user"]
  }
  assert {
    condition     = length(aws_iam_role.weather_local_writer) == 1 && aws_iam_role.weather_local_writer[0].max_session_duration == 3600
    error_message = "Exactly one local writer role with a 1h max session."
  }
  assert {
    condition = (
      jsondecode(aws_iam_role.weather_local_writer[0].assume_role_policy).Statement[0].Principal.AWS == ["arn:aws:iam::123456789012:user/dev-user"]
      && jsondecode(aws_iam_role.weather_local_writer[0].assume_role_policy).Statement[0].Action == "sts:AssumeRole"
      && length(jsondecode(aws_iam_role.weather_local_writer[0].assume_role_policy).Statement) == 1
    )
    error_message = "Trust policy must allow only sts:AssumeRole for the listed principal."
  }
  assert {
    condition     = length(aws_iam_role_policy_attachment.weather_local_writer) == 1 && length(aws_iam_role_policy_attachment.weather_writer) == 0 && length(aws_iam_role_policy_attachment.weather_reader) == 0
    error_message = "The local writer role receives exactly one attachment, and no other role gains access."
  }
}

run "local_writer_rejects_wildcard_principal" {
  command = plan
  variables {
    expected_account_id                 = "123456789012"
    weather_local_writer_principal_arns = ["*"]
  }
  expect_failures = [var.weather_local_writer_principal_arns]
}
