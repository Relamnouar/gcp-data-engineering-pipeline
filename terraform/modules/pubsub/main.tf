
# Schema Pub/Sub
resource "google_pubsub_schema" "cart_event_schema" {
  project = var.project_id
  name    = "cart-event-schema"
  type    = "AVRO"

  definition = file("${path.module}/schemas/cart_event_schema.json")
}

# Topic principal
resource "google_pubsub_topic" "carts_events" {
  name    = "carts-events"
  project = var.project_id
  schema_settings {
  schema   = google_pubsub_schema.cart_event_schema.id
  encoding = "JSON"
  }
  labels = var.labels
  depends_on = [google_pubsub_schema.cart_event_schema]
}

# Subscription avec BigQuery
resource "google_pubsub_subscription" "carts_to_bigquery" {
  name    = "carts-events-to-bigquery"
  topic   = google_pubsub_topic.carts_events.name
  project = var.project_id
  
  labels = var.labels
  
  ack_deadline_seconds       = 600
  message_retention_duration = "86400s"
  enable_message_ordering    = true
  
  bigquery_config {
    table            = "${var.bigquery_project_id}.${var.bigquery_dataset_id}.${var.bigquery_table_id}"
    write_metadata   = false
    use_topic_schema = true
    drop_unknown_fields = true
  }
  
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
  
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }
  
  # AJOUT : Attendre que les permissions IAM soient créées
  depends_on = [var.iam_dependencies]
}

# Dead letter topic
resource "google_pubsub_topic" "dead_letter" {
  name    = "carts-events-dead-letter"
  project = var.project_id
  
  labels = merge(var.labels, {
    type = "dead-letter"
  })
}

# Dead letter subscription
resource "google_pubsub_subscription" "dead_letter_sub" {
  name                       = "carts-events-dead-letter-sub"
  topic                      = google_pubsub_topic.dead_letter.name
  project                    = var.project_id
  ack_deadline_seconds       = 600
  message_retention_duration = "604800s"
  labels = var.labels
  depends_on = [
    var.iam_dependencies,
    google_pubsub_topic_iam_member.dead_letter_publisher
  ]
}

data "google_project" "pubsub_project" {
  project_id = var.project_id
}

resource "google_pubsub_topic_iam_member" "dead_letter_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.dead_letter.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.pubsub_project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}