# Optional: copy to backend.remote.tf AFTER the bucket has been created.
terraform {
  backend "s3" {}
}
