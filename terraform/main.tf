# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "pubsub.googleapis.com"
  ])
  
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Local variables
locals {
  common_labels = {
    environment = var.environment
    project     = var.project_id
    managed_by  = "terraform"
  }
}

# Module: BigQuery
module "bigquery" {
  source      = "./modules/bigquery"
  project_id  = var.project_id
  environment = var.environment
  location    = var.bigquery_location
  labels      = local.common_labels
  
  depends_on = [google_project_service.required_apis]
}

# Module: Storage (GCS)
module "storage" {
  source          = "./modules/storage"
  project_id      = var.project_id
  region          = var.region
  raw_bucket_name = var.raw_bucket_name
  environment     = var.environment
  labels          = local.common_labels
  
  depends_on = [google_project_service.required_apis]
}

# Module: IAM (doit être créé AVANT Pub/Sub)
module "iam" {
  source          = "./modules/iam"
  project_id      = var.project_id
  environment     = var.environment
  raw_bucket_name = var.raw_bucket_name
  
  depends_on = [
    module.storage,
    module.bigquery
  ]
}

# Module: Pub/Sub (APRÈS IAM)
module "pubsub" {
  source              = "./modules/pubsub"
  project_id          = var.project_id
  environment         = var.environment
  bigquery_project_id = var.project_id
  bigquery_dataset_id = module.bigquery.bronze_dataset_id
  bigquery_table_id   = "carts_raw_stream"
  labels              = local.common_labels
  
  # Attendre que TOUTES les permissions soient créées
  iam_dependencies = [
    module.bigquery.pubsub_table_permission_id,
    module.bigquery.pubsub_dataset_permission_id,
    module.bigquery.pubsub_project_permission_id
  ]
  
  depends_on = [
    module.bigquery,
    module.iam
  ]
}