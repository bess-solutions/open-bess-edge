output "pubsub_topic_id" {
  description = "Full resource ID of the BESSAI telemetry Pub/Sub topic."
  value       = google_pubsub_topic.telemetry.id
}

output "pubsub_subscription_id" {
  description = "Full resource ID of the default pull subscription."
  value       = google_pubsub_subscription.telemetry_pull.id
}

output "service_account_email" {
  description = "Email of the BESSAI Edge Gateway service account."
  value       = google_service_account.bessai_edge.email
}

output "artifact_registry_url" {
  description = "Docker registry URL for BESSAI images."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository}"
}

output "secret_name" {
  description = "Resource name of the GCP service account key secret."
  value       = google_secret_manager_secret.edge_sa_key.name
}
