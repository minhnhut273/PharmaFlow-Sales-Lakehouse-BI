terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }
  backend "s3" {}
}

variable "expected_account_id" {
  description = "Account verified through STS. Prevents deployment to another account."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must contain exactly 12 digits."
  }
}

variable "weather_writer_role_names" {
  description = "Explicit existing IAM role names to attach Weather read/write policy to. No grants by default."
  type        = set(string)
  default     = []
}

variable "weather_reader_role_names" {
  description = "Explicit existing IAM role names to attach Weather read-only policy to."
  type        = set(string)
  default     = []
}

variable "weather_local_writer_principal_arns" {
  description = "IAM principal ARNs allowed to assume the local Weather writer role (P2 local CLI). Empty = role not created."
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for arn in var.weather_local_writer_principal_arns : can(regex("^arn:aws:iam::[0-9]{12}:(user|role)/[A-Za-z0-9+=,.@_/-]+$", arn))])
    error_message = "Each principal must be an explicit IAM user or role ARN (no wildcards, no account root)."
  }
}

provider "aws" {
  region              = "ap-southeast-1"
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = {
      Project     = "PharmaFlow"
      Environment = "dev"
      ManagedBy   = "Terraform"
    }
  }
}

locals {
  bucket_name = "pharmaflow-dev-weather-raw-${var.expected_account_id}-ap-southeast-1"
  bucket_arn  = "arn:aws:s3:::${local.bucket_name}"
  weather_prefixes = [
    "raw/open_meteo/weather_forecast/",
    "raw/open_meteo/historical_forecast/",
    "raw/open_meteo/historical_weather/"
  ]
  weather_object_arns = [for prefix in local.weather_prefixes : "${local.bucket_arn}/${prefix}*"]
  bucket_access_statements = [
    {
      Sid      = "LocateBucket"
      Effect   = "Allow"
      Action   = ["s3:GetBucketLocation"]
      Resource = local.bucket_arn
    },
    {
      Sid      = "ListWeatherPrefixes"
      Effect   = "Allow"
      Action   = ["s3:ListBucket"]
      Resource = local.bucket_arn
      Condition = {
        StringLike = {
          "s3:prefix" = flatten([for prefix in local.weather_prefixes : [prefix, "${prefix}*"]])
        }
      }
    }
  ]
}

module "data_bucket" {
  source      = "../../modules/private_s3"
  bucket_name = local.bucket_name
  tags        = { Purpose = "PharmaFlowSourceObjects" }
}

resource "aws_iam_policy" "weather_writer" {
  name        = "pharmaflow-dev-weather-s3-writer"
  description = "Read/write Weather raw objects only; no object deletion or bucket administration."
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.bucket_access_statements, [{
      Sid      = "ReadWriteWeatherObjects"
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject"]
      Resource = local.weather_object_arns
    }])
  })
}

resource "aws_iam_policy" "weather_reader" {
  name        = "pharmaflow-dev-weather-s3-reader"
  description = "Read/list accepted Weather raw objects for future consumers."
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.bucket_access_statements, [{
      Sid      = "ReadWeatherObjects"
      Effect   = "Allow"
      Action   = ["s3:GetObject"]
      Resource = local.weather_object_arns
    }])
  })
}

resource "aws_iam_role_policy_attachment" "weather_writer" {
  for_each   = var.weather_writer_role_names
  role       = each.value
  policy_arn = aws_iam_policy.weather_writer.arn
}

resource "aws_iam_role_policy_attachment" "weather_reader" {
  for_each   = var.weather_reader_role_names
  role       = each.value
  policy_arn = aws_iam_policy.weather_reader.arn
}

# P2: role assumed by the local CLI (--sink s3). Only the explicitly listed principals may assume it,
# and its only permissions come from the writer policy above (no DeleteObject, three prefixes only).
resource "aws_iam_role" "weather_local_writer" {
  count                = length(var.weather_local_writer_principal_arns) > 0 ? 1 : 0
  name                 = "pharmaflow-dev-weather-local-writer"
  description          = "Assumed by the PharmaFlow weather CLI on a developer machine to write raw Weather objects (P2)."
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowExplicitPrincipals"
      Effect    = "Allow"
      Principal = { AWS = sort(tolist(var.weather_local_writer_principal_arns)) }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "weather_local_writer" {
  count      = length(aws_iam_role.weather_local_writer)
  role       = aws_iam_role.weather_local_writer[0].name
  policy_arn = aws_iam_policy.weather_writer.arn
}

output "data_bucket_name" {
  value = module.data_bucket.bucket_name
}

output "data_bucket_arn" {
  value = module.data_bucket.bucket_arn
}

output "region" {
  value = "ap-southeast-1"
}

output "weather_s3_uris" {
  value = [for prefix in local.weather_prefixes : "s3://${local.bucket_name}/${prefix}"]
}

output "weather_writer_policy_arn" {
  value = aws_iam_policy.weather_writer.arn
}

output "weather_reader_policy_arn" {
  value = aws_iam_policy.weather_reader.arn
}

output "weather_local_writer_role_arn" {
  value = one(aws_iam_role.weather_local_writer[*].arn)
}
