variable "project_id" {
  type        = string
  description = "Google Cloud project ID where all resources will be created."
}

variable "region" {
  type        = string
  description = "GCP region for regional resources (e.g. Pub/Sub, Artifact Registry)."
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, prod)."
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod"
  }
}

variable "pubsub_topic_name" {
  type        = string
  description = "Name of the GCP Pub/Sub topic for BESSAI telemetry."
  default     = "bess-telemetry"
}

variable "pubsub_message_retention_days" {
  type        = number
  description = "Number of days Pub/Sub retains undelivered messages."
  default     = 7
}

variable "service_account_name" {
  type        = string
  description = "Name for the BESSAI Edge Gateway service account."
  default     = "bessai-edge-sa"
}

variable "artifact_registry_repository" {
  type        = string
  description = "Name of the Artifact Registry Docker repository."
  default     = "bessai"
}
