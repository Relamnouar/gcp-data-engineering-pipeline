output "bronze_dataset_id" {
  description = "Bronze dataset ID"
  value       = google_bigquery_dataset.bronze.dataset_id
}

output "silver_dataset_id" {
  description = "Silver dataset ID"
  value       = google_bigquery_dataset.silver.dataset_id
}

output "gold_dataset_id" {
  description = "Gold dataset ID"
  value       = google_bigquery_dataset.gold.dataset_id
}

output "products_raw_table_id" {
  description = "Products raw table ID"
  value       = google_bigquery_table.products_raw.table_id
}

output "users_raw_table_id" {
  description = "Users raw table ID"
  value       = google_bigquery_table.users_raw.table_id
}

output "carts_raw_stream_table_id" {
  description = "Carts raw stream table ID"
  value       = google_bigquery_table.carts_raw_stream.table_id
}
output "pubsub_table_permission_id" {
  description = "ID of Pub/Sub to carts table IAM permission"
  value       = google_bigquery_table_iam_member.pubsub_carts_table_editor.id
}
output "pubsub_dataset_permission_id" {
  description = "ID of Pub/Sub to dataset IAM permission"
  value       = google_bigquery_dataset_iam_member.pubsub_bronze_metadata.id
}
output "pubsub_project_permission_id" {
  description = "ID of Pub/Sub to project IAM permission"
  value       = google_project_iam_member.pubsub_bigquery_editor.id
}