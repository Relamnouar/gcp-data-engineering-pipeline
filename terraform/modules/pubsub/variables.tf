variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "bigquery_project_id" {
  description = "BigQuery project ID"
  type        = string
}

variable "bigquery_dataset_id" {
  description = "BigQuery dataset ID"
  type        = string
}

variable "bigquery_table_id" {
  description = "BigQuery table ID"
  type        = string
}

variable "labels" {
  description = "Labels to apply to resources"
  type        = map(string)
  default     = {}
}

variable "iam_dependencies" {
  description = "IAM dependencies to wait for"
  type        = list(string)
  default     = []
}
variable "schema_file_path" {
  description = "Path to the AVRO schema file"
  type        = string
  default     = "./schemas/cart_event_schema.json"
}