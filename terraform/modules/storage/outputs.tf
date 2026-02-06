output "bucket_name" {
  description = "GCS bucket name"
  value       = google_storage_bucket.raw_data.name
}

output "bucket_url" {
  description = "GCS bucket URL"
  value       = google_storage_bucket.raw_data.url
}

output "bucket_self_link" {
  description = "GCS bucket self link"
  value       = google_storage_bucket.raw_data.self_link
}
