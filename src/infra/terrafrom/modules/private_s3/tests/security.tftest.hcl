mock_provider "aws" {}

run "private_versioned_encrypted_bucket" {
  command = plan
  variables {
    bucket_name = "pharmaflow-dev-security-test"
    tags        = { Environment = "dev" }
  }

  assert {
    condition     = !aws_s3_bucket.this.force_destroy
    error_message = "Bucket must not purge stored objects on destroy."
  }
  assert {
    condition = (
      aws_s3_bucket_public_access_block.this.block_public_acls &&
      aws_s3_bucket_public_access_block.this.block_public_policy &&
      aws_s3_bucket_public_access_block.this.ignore_public_acls &&
      aws_s3_bucket_public_access_block.this.restrict_public_buckets
    )
    error_message = "All four public access blocks must be enabled."
  }
  assert {
    condition     = one(aws_s3_bucket_versioning.this.versioning_configuration).status == "Enabled"
    error_message = "Versioning must be enabled."
  }
  assert {
    condition     = one(aws_s3_bucket_ownership_controls.this.rule).object_ownership == "BucketOwnerEnforced"
    error_message = "ACLs must be disabled through bucket owner enforced ownership."
  }
  assert {
    condition     = one(one(aws_s3_bucket_server_side_encryption_configuration.this.rule).apply_server_side_encryption_by_default).sse_algorithm == "AES256"
    error_message = "Default encryption must use SSE-S3."
  }
  assert {
    condition     = jsondecode(aws_s3_bucket_policy.this.policy).Statement[0].Condition.Bool["aws:SecureTransport"] == "false"
    error_message = "Bucket policy must deny non-TLS access."
  }
}
