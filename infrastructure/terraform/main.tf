# =============================================================================
# BESSAI Edge Gateway — Terraform (GCP)
# =============================================================================
# Resources provisioned:
#   - GCP Pub/Sub topic + pull subscription (telemetry ingestion)
#   - IAM Service Account with least-privilege roles
#   - Artifact Registry Docker repository (container images)
#   - Secret Manager secret (GCP key for edge gateway auth)
#
# Usage:
#   terraform init
#   terraform workspace new dev   # or staging / prod
#   terraform apply -var="project_id=YOUR_PROJECT" -var="environment=dev"
# =============================================================================

locals {
  common_labels = {
    project     = "bessai"
    environment = var.environment
    managed_by  = "terraform"
    component   = "edge-gateway"
  }
}

# ── Enable required APIs ──────────────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each = toset([
    "pubsub.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ── Pub/Sub — telemetry topic ─────────────────────────────────────────────────
resource "google_pubsub_topic" "telemetry" {
  name    = "${var.pubsub_topic_name}-${var.environment}"
  project = var.project_id
  labels  = local.common_labels

  message_retention_duration = "${var.pubsub_message_retention_days * 86400}s"

  depends_on = [google_project_service.apis]
}

# ── Pub/Sub — dead-letter topic ───────────────────────────────────────────────
resource "google_pubsub_topic" "telemetry_dlq" {
  name    = "${var.pubsub_topic_name}-${var.environment}-dlq"
  project = var.project_id
  labels  = local.common_labels

  depends_on = [google_project_service.apis]
}

# ── Pub/Sub — pull subscription (for BigQuery / analytics consumers) ──────────
resource "google_pubsub_subscription" "telemetry_pull" {
  name    = "${var.pubsub_topic_name}-${var.environment}-pull"
  topic   = google_pubsub_topic.telemetry.name
  project = var.project_id
  labels  = local.common_labels

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s" # 7 days
  retain_acked_messages      = false
  enable_message_ordering    = false

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.telemetry_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# ── IAM — Service Account for Edge Gateway ────────────────────────────────────
resource "google_service_account" "bessai_edge" {
  account_id   = "${var.service_account_name}-${var.environment}"
  display_name = "BESSAI Edge Gateway — ${var.environment}"
  description  = "Service account used by the BESSAI Edge Gateway to publish telemetry and export traces."
  project      = var.project_id
}

# Pub/Sub publisher
resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.bessai_edge.email}"
}

# Cloud Monitoring writer
resource "google_project_iam_member" "monitoring_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.bessai_edge.email}"
}

# Cloud Trace writer
resource "google_project_iam_member" "trace_writer" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.bessai_edge.email}"
}

# ── Artifact Registry — Docker repository ─────────────────────────────────────
resource "google_artifact_registry_repository" "bessai" {
  repository_id = var.artifact_registry_repository
  format        = "DOCKER"
  location      = var.region
  description   = "BESSAI Edge Gateway Docker images"
  project       = var.project_id
  labels        = local.common_labels

  depends_on = [google_project_service.apis]
}

# GitHub Actions SA can push images (Workload Identity Federation)
resource "google_artifact_registry_repository_iam_member" "ci_writer" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.bessai.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.bessai_edge.email}"
}

# ── Secret Manager — service account key ─────────────────────────────────────
resource "google_secret_manager_secret" "edge_sa_key" {
  secret_id = "bessai-edge-sa-key-${var.environment}"
  project   = var.project_id
  labels    = local.common_labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# NOTE: The actual key version (secret value) should be populated manually
# or via a separate rotation workflow. Never store key JSON in Terraform state.
# To create a key and store it:
#   gcloud iam service-accounts keys create key.json \
#     --iam-account=<SA_EMAIL>
#   gcloud secrets versions add bessai-edge-sa-key-dev --data-file=key.json
#   rm key.json

# ── Workload Identity Federation for GitHub Actions ───────────────────────────
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions CI/CD"
  project                   = var.project_id

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC Provider"
  project                            = var.project_id

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  # Restrict to the BESSAI repo only — GCP requires attribute_condition to
  # reference at least one of the mapped provider claims.
  attribute_condition = "assertion.repository == 'bess-solutions/open-bess-edge'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}
