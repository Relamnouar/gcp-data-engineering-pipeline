# Dataset Bronze (raw data)
resource "google_bigquery_dataset" "bronze" {
  dataset_id  = "bronze_data"
  project     = var.project_id
  location    = var.location
  description = "Raw data layer"
  
  labels = var.labels
}

# Table: products_raw
resource "google_bigquery_table" "products_raw" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id   = "products_raw"
  project    = var.project_id
  
  deletion_protection = false
  
  schema = jsonencode([
    { name = "extracted_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "entity_type", type = "STRING", mode = "REQUIRED" },
    { name = "record_count", type = "INTEGER", mode = "REQUIRED" },
    { name = "data", type = "JSON", mode = "REQUIRED" }
  ])
  
  time_partitioning {
    type  = "DAY"
    field = "extracted_at"
  }
  
  clustering = ["entity_type", "run_id"]
  
  labels = var.labels
}

# Table: users_raw
resource "google_bigquery_table" "users_raw" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id   = "users_raw"
  project    = var.project_id
  
  deletion_protection = false
  
  schema = jsonencode([
    { name = "extracted_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "entity_type", type = "STRING", mode = "REQUIRED" },
    { name = "record_count", type = "INTEGER", mode = "REQUIRED" },
    { name = "data", type = "JSON", mode = "REQUIRED" }
  ])
  
  time_partitioning {
    type  = "DAY"
    field = "extracted_at"
  }
  
  clustering = ["entity_type", "run_id"]
  
  labels = var.labels
}

# Table: carts_raw_stream
resource "google_bigquery_table" "carts_raw_stream" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id   = "carts_raw_stream"
  project    = var.project_id
  
  deletion_protection = false
  
    schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "event_type", type = "STRING", mode = "REQUIRED" },
    { name = "event_schema_version", type = "STRING", mode = "REQUIRED" },
    { name = "source", type = "STRING", mode = "REQUIRED" },
    { name = "extracted_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "published_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "data", type = "JSON", mode = "REQUIRED" }
  ])
  
  time_partitioning {
    type  = "DAY"
    field = "published_at"
  }
  
  clustering = ["event_type", "event_id"]
  
  labels = var.labels
}

# Dataset Silver (staging)
resource "google_bigquery_dataset" "silver" {
  dataset_id  = "silver_data"
  project     = var.project_id
  location    = var.location
  description = "Staging layer (dbt views)"
  
  labels = var.labels
}

# Dataset Gold (marts)
resource "google_bigquery_dataset" "gold" {
  dataset_id  = "gold_data"
  project     = var.project_id
  location    = var.location
  description = "Analytics layer (star schema)"
  
  labels = var.labels
}


data "google_project" "project" {
  project_id = var.project_id
}


resource "google_bigquery_table_iam_member" "pubsub_carts_table_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id   = google_bigquery_table.carts_raw_stream.table_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_bigquery_dataset_iam_member" "pubsub_bronze_metadata" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  role       = "roles/bigquery.metadataViewer"
  member     = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "pubsub_bigquery_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}