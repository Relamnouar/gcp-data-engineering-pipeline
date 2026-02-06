# Service Account: Batch Ingestion
resource "google_service_account" "batch_ingestion" {
  account_id   = "batch-ingestion-sa-${var.environment}"
  display_name = "Batch Ingestion Service Account (${var.environment})"
  project      = var.project_id
}

resource "google_project_iam_member" "batch_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.batch_ingestion.email}"
}

resource "google_project_iam_member" "batch_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.batch_ingestion.email}"
}

resource "google_project_iam_member" "batch_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.batch_ingestion.email}"
}

# Service Account: Streaming Ingestion
resource "google_service_account" "streaming_ingestion" {
  account_id   = "streaming-ingestion-sa-${var.environment}"
  display_name = "Streaming Ingestion Service Account (${var.environment})"
  project      = var.project_id
}

resource "google_project_iam_member" "streaming_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.streaming_ingestion.email}"
}

# Service Account: dbt
resource "google_service_account" "dbt_runner" {
  account_id   = "dbt-runner-sa-${var.environment}"
  display_name = "dbt Runner Service Account (${var.environment})"
  project      = var.project_id
}

resource "google_project_iam_member" "dbt_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dbt_runner.email}"
}

resource "google_project_iam_member" "dbt_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dbt_runner.email}"
}
