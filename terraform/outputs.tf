# ============================================================================
# PROJECT INFORMATION
# ============================================================================

output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP Region"
  value       = var.region
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

# ============================================================================
# BIGQUERY OUTPUTS
# ============================================================================

output "bronze_dataset_id" {
  description = "Bronze dataset ID (raw data)"
  value       = module.bigquery.bronze_dataset_id
}

output "silver_dataset_id" {
  description = "Silver dataset ID (staging)"
  value       = module.bigquery.silver_dataset_id
}

output "gold_dataset_id" {
  description = "Gold dataset ID (analytics)"
  value       = module.bigquery.gold_dataset_id
}

output "products_raw_table" {
  description = "Products raw table ID"
  value       = "${module.bigquery.bronze_dataset_id}.${module.bigquery.products_raw_table_id}"
}

output "users_raw_table" {
  description = "Users raw table ID"
  value       = "${module.bigquery.bronze_dataset_id}.${module.bigquery.users_raw_table_id}"
}

output "carts_raw_stream_table" {
  description = "Carts raw stream table ID"
  value       = "${module.bigquery.bronze_dataset_id}.${module.bigquery.carts_raw_stream_table_id}"
}

# ============================================================================
# STORAGE OUTPUTS
# ============================================================================

output "raw_bucket_name" {
  description = "Raw data GCS bucket name"
  value       = module.storage.bucket_name
}

output "raw_bucket_url" {
  description = "Raw data GCS bucket URL"
  value       = module.storage.bucket_url
}

# ============================================================================
# PUB/SUB OUTPUTS
# ============================================================================

output "pubsub_topic_name" {
  description = "Pub/Sub topic name for cart events"
  value       = module.pubsub.topic_name
}

output "pubsub_topic_id" {
  description = "Pub/Sub topic ID"
  value       = module.pubsub.topic_id
}

output "pubsub_subscription_name" {
  description = "Pub/Sub subscription name"
  value       = module.pubsub.subscription_name
}

output "dead_letter_topic_name" {
  description = "Dead letter topic name"
  value       = module.pubsub.dead_letter_topic_name
}

# ============================================================================
# IAM OUTPUTS (Service Accounts)
# ============================================================================

output "batch_sa_email" {
  description = "Service Account email for batch ingestion"
  value       = module.iam.batch_sa_email
}

output "streaming_sa_email" {
  description = "Service Account email for streaming ingestion"
  value       = module.iam.streaming_sa_email
}

output "dbt_sa_email" {
  description = "Service Account email for dbt"
  value       = module.iam.dbt_sa_email
}

# ============================================================================
# COMMAND HELPERS
# ============================================================================

output "batch_ingestion_command" {
  description = "Command to run batch ingestion"
  value       = "python batch_ingestion.py --project-id=${var.project_id} --bucket-name=${module.storage.bucket_name} --dataset-id=${module.bigquery.bronze_dataset_id}"
}

output "streaming_ingestion_command" {
  description = "Command to run streaming ingestion"
  value       = "python near_realtime_ingestion_2.py --project-id=${var.project_id} --topic-name=${module.pubsub.topic_name}"
}

output "dbt_command" {
  description = "Command to run dbt"
  value       = "dbt run --profiles-dir=. --project-dir=dbt_project"
}

# ============================================================================
# SUMMARY
# ============================================================================

output "deployment_summary" {
  description = "Deployment summary"
  value = {
    project_id  = var.project_id
    environment = var.environment
    region      = var.region
    
    datasets = {
      bronze = module.bigquery.bronze_dataset_id
      silver = module.bigquery.silver_dataset_id
      gold   = module.bigquery.gold_dataset_id
    }
    
    storage = {
      bucket = module.storage.bucket_name
    }
    
    pubsub = {
      topic        = module.pubsub.topic_name
      subscription = module.pubsub.subscription_name
    }
    
    service_accounts = {
      batch     = module.iam.batch_sa_email
      streaming = module.iam.streaming_sa_email
      dbt       = module.iam.dbt_sa_email
    }
  }
}
