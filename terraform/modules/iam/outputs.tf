output "batch_sa_email" {
  description = "Batch ingestion service account email"
  value       = google_service_account.batch_ingestion.email
}

output "batch_sa_id" {
  description = "Batch ingestion service account ID"
  value       = google_service_account.batch_ingestion.id
}

output "streaming_sa_email" {
  description = "Streaming ingestion service account email"
  value       = google_service_account.streaming_ingestion.email
}

output "streaming_sa_id" {
  description = "Streaming ingestion service account ID"
  value       = google_service_account.streaming_ingestion.id
}

output "dbt_sa_email" {
  description = "dbt runner service account email"
  value       = google_service_account.dbt_runner.email
}

output "dbt_sa_id" {
  description = "dbt runner service account ID"
  value       = google_service_account.dbt_runner.id
}