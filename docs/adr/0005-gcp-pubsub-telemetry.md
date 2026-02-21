# ADR-0005: Use GCP Pub/Sub for Telemetry Ingestion

## Status
✅ Accepted — 2026-02-19

## Context

The BESSAI Edge Gateway produces real-time telemetry (SOC, power, temperature, AI scores) that must be reliably delivered to a cloud-based data pipeline for storage, analytics, and fleet management.

Requirements:
- **At-least-once delivery**: no telemetry data should be silently lost
- **Decoupled producers and consumers**: the edge device should not depend on backend availability
- **Multi-consumer**: the same telemetry should feed multiple downstream systems (BigQuery, alerting, dashboards)
- **Managed service**: minimal operational overhead for a small engineering team
- **GCP ecosystem**: the team is already using GCP (Cloud Run, Artifact Registry, Cloud Trace via OpenTelemetry)

Alternatives considered:
- **MQTT (self-hosted Mosquitto/HiveMQ)**: low latency but requires managing broker HA, no native fan-out
- **Apache Kafka (self-hosted)**: excellent for high throughput but operationally complex for a small team
- **Confluent Cloud (managed Kafka)**: better UX but expensive at scale; requires separate auth model
- **AWS IoT Core**: best-in-class for IoT but locks into AWS ecosystem, contradicts current GCP choice
- **HTTP POST to Cloud Run**: simple but synchronous — gateway blocks until backend responds; no buffering

## Decision

Use **GCP Pub/Sub** as the primary telemetry message bus.

Key implementation details in `src/interfaces/pubsub_publisher.py`:
- Async context manager wrapping `google.cloud.pubsub_v1.PublisherClient`
- Message envelope format: `{ "schema_version": "1.0", "site_id": "...", "timestamp": "...", "payload": {...} }`
- **Non-blocking**: publish is fire-and-forget; errors are logged and counted in Prometheus (`bess_publish_errors_total`)
- **Graceful degradation**: if Pub/Sub is unavailable or unconfigured, the gateway continues operating; telemetry is not buffered locally (acceptable for v1 — local queue planned for v2)
- Authentication: Workload Identity Federation (WIF) via GitHub Actions; Service Account JSON in production

**Infrastructure** (Terraform-managed):
- Topic: `bess-telemetry-dev`
- Subscription: `bess-telemetry-dev-pull` (for BigQuery DataLake consumer)
- IAM: `bessai-edge-sa-dev` with `roles/pubsub.publisher` only (least privilege)

## Consequences

### Positive
- **Managed HA**: Google guarantees 11 nines of durability; no broker maintenance
- **Fan-out**: multiple subscribers can consume the same topic independently (BigQuery, alerting, real-time dashboard)
- **Decoupled**: edge device is not aware of backend consumers
- **GCP ecosystem**: integrates natively with Cloud Logging, Cloud Monitoring, BigQuery Data Transfer
- **Workload Identity Federation**: no long-lived service account keys in edge devices

### Negative
- **GCP vendor lock-in**: switching to AWS or Azure requires replacing publisher + Terraform + IAM
- **Cost at scale**: Pub/Sub charges per message; at 1 message/5s × 1000 sites = ~500K msg/day → ~$1.50/day (acceptable)
- **No local buffering v1**: if Pub/Sub is unavailable during network outage, telemetry data is lost for that period

### Neutral
- The `GCP_PROJECT_ID` and `GCP_PUBSUB_TOPIC` env vars are optional in development — the gateway runs without GCP connectivity in simulator mode
- Future: a local ring-buffer (SQLite or RocksDB) could provide store-and-forward for offline tolerance
