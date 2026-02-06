variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "raw_bucket_name" {
  description = "Name of the raw data bucket (for IAM permissions)"
  type        = string
}
