# =============================================================================
# infrastructure/terraform/backend.tf
# =============================================================================
# Configuración del backend remoto (GCS) para el state de Terraform.
#
# ⚠️  Descomenta el bloque `backend` cuando tengas un bucket GCS disponible.
#     Hasta entonces, Terraform usa el backend local (terraform.tfstate).
#
# Para crear el bucket GCS para el state:
#   gsutil mb -l US gs://<tu-proyecto-gcp>-terraform-state
#   gsutil versioning set on gs://<tu-proyecto-gcp>-terraform-state
#
# Luego descomenta y ajusta:
# =============================================================================

terraform {
  required_version = ">= 1.7.0"

  # ── Descomenta para usar state remoto en GCS ───────────────────────────────
  # backend "gcs" {
  #   bucket  = "mi-proyecto-gcp-123456-terraform-state"
  #   prefix  = "bessai/edge-gateway"
  # }

  # ── Backend local (default — no requiere configuración) ───────────────────
  # Terraform usa backend local por defecto cuando `backend` no está definido.
  # El state se guarda en terraform.tfstate (agregar a .gitignore).
}
