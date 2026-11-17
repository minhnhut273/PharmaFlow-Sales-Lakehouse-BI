terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # First init uses the implicit local backend. See README before migrating.
}

variable "expected_account_id" {
  description = "Account verified with aws sts get-caller-identity; mandatory account guard."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must contain exactly 12 digits."
  }
}

provider "aws" {
  region              = "ap-southeast-1"
  allowed_account_ids = [var.expected_account_id]
}

module "state_bucket" {
  source      = "../modules/private_s3"
  bucket_name = "pharmaflow-dev-tfstate-${var.expected_account_id}-ap-southeast-1"
  tags = {
    Project     = "PharmaFlow"
    Environment = "dev"
    ManagedBy   = "Terraform"
    Purpose     = "TerraformState"
  }
}

output "state_bucket_name" {
  value = module.state_bucket.bucket_name
}

output "account_id" {
  value = var.expected_account_id
}

output "region" {
  value = "ap-southeast-1"
}
