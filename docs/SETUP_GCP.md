# Configuración GCP para BESSAI Edge Gateway

> **Tiempo estimado:** 30 min · **Requiere:** cuenta GCP + permisos de propietario

---

## Por qué GCP

BESSAI publica telemetría (SOC, potencia, temperatura, métricas IA) a GCP Pub/Sub en cada ciclo de adquisición (cada ~30s). Sin GCP configurado, el sistema registra `bess_publish_errors_total++` en cada ciclo pero sigue operando. No es bloqueante para el piloto.

---

## Paso 1 — Crear proyecto GCP

```bash
# Requiere: gcloud CLI autenticado (gcloud auth login)
gcloud projects create bessai-production-001 --name="BESSAI Production"
gcloud config set project bessai-production-001
```

O hacerlo en la consola: https://console.cloud.google.com/projectcreate

---

## Paso 2 — Habilitar APIs

```bash
gcloud services enable pubsub.googleapis.com bigquery.googleapis.com cloudscheduler.googleapis.com
```

---

## Paso 3 — Crear Service Account

```bash
# Crear service account
gcloud iam service-accounts create bessai-edge \
  --display-name="BESSAI Edge Gateway"

# Asignar roles mínimos necesarios
gcloud projects add-iam-policy-binding bessai-production-001 \
  --member="serviceAccount:bessai-edge@bessai-production-001.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"

gcloud projects add-iam-policy-binding bessai-production-001 \
  --member="serviceAccount:bessai-edge@bessai-production-001.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

# Descargar key (guardar fuera del repo)
gcloud iam service-accounts keys create ~/bessai-gcp-key.json \
  --iam-account=bessai-edge@bessai-production-001.iam.gserviceaccount.com
```

---

## Paso 4 — Crear Topic Pub/Sub

```bash
gcloud pubsub topics create bess-telemetry
gcloud pubsub subscriptions create bess-telemetry-sub --topic=bess-telemetry
```

---

## Paso 5 — Configurar variables de entorno

Editar `config/.env` en el servidor/RaspberryPi donde corre BESSAI:

```bash
GCP_PROJECT_ID=bessai-production-001
GCP_PUBSUB_TOPIC=bess-telemetry
GOOGLE_APPLICATION_CREDENTIALS=/home/pi/bessai-gcp-key.json
```

> ⚠️ **Nunca commitear** `bessai-gcp-key.json`. Está incluido en `.gitignore`.

---

## Paso 6 — Verificar

```bash
# Iniciar el gateway y verificar que los errores de publish desaparecen:
curl http://localhost:8000/metrics | grep publish_errors
# Esperado: bess_publish_errors_total = 0
```

---

## BigQuery Dataset (opcional — para DataLake)

```bash
bq mk --dataset bessai-production-001:bessai_telemetry
```

Luego configurar en `.env`:
```bash
BIGQUERY_PROJECT_ID=bessai-production-001
BIGQUERY_DATASET=bessai_telemetry
```

---

## Terraform (automatizado)

Si prefieres reproducir toda la infraestructura con Terraform:

```bash
cd infrastructure/terraform
terraform init
terraform apply -var="project_id=bessai-production-001"
```

Los 18 recursos GCP se crean automáticamente.

---

*BESS Solutions SpA · Confidencial · 2026-03-02*
