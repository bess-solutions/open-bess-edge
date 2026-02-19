terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Remote state in GCS — configure per-environment
  # Uncomment and fill in for production:
  # backend "gcs" {
  #   bucket  = "bessai-tf-state"
  #   prefix  = "open-bess-edge"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
