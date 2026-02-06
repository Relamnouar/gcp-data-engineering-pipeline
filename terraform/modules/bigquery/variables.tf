variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "europe-west9"
}

variable "labels" {
  description = "Labels to apply to resources"
  type        = map(string)
  default     = {}
}