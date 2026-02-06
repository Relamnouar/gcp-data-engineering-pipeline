output "topic_name" {
  description = "Pub/Sub topic name"
  value       = google_pubsub_topic.carts_events.name
}

output "topic_id" {
  description = "Pub/Sub topic ID"
  value       = google_pubsub_topic.carts_events.id
}

output "subscription_name" {
  description = "Pub/Sub subscription name"
  value       = google_pubsub_subscription.carts_to_bigquery.name
}

output "subscription_id" {
  description = "Pub/Sub subscription ID"
  value       = google_pubsub_subscription.carts_to_bigquery.id
}

output "dead_letter_topic_name" {
  description = "Dead letter topic name"
  value       = google_pubsub_topic.dead_letter.name
}
output "dead_letter_permission_id" {
  description = "ID of Pub/Sub dead letter IAM permission"
  value       = google_pubsub_topic_iam_member.dead_letter_publisher.id
}
output "schema_id" {
  description = "Full ID of the Pub/Sub schema"
  value       = google_pubsub_schema.cart_event_schema.id
}

output "schema_name" {
  description = "Name of the Pub/Sub schema"
  value       = google_pubsub_schema.cart_event_schema.name
}
output "pubsub_service_account" {
  description = "Service account used by Pub/Sub"
  value       = "service-${data.google_project.pubsub_project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}