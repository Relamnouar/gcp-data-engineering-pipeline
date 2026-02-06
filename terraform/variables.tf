variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west9"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod"
  }
}

variable "raw_bucket_name" {
  description = "Name of the GCS bucket for raw data"
  type        = string
}

variable "bigquery_location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "europe-west9"
}

variable "poll_interval_seconds" {
  description = "Polling interval for near real-time ingestion"
  type        = number
  default     = 60
}

variable "batch_schedule" {
  description = "Cron schedule for batch ingestion"
  type        = string
  default     = "0 2 * * *"  # 2 AM daily
}
