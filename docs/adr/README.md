# Architecture Decision Records (ADRs)

This directory documents the key architectural decisions made in the BESSAI Edge Gateway project.

ADRs follow the [Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions): Title · Context · Decision · Consequences.

---

## Index

| ID | Title | Status | Date |
|---|---|---|---|
| [ADR-0001](0001-pydantic-settings-config.md) | Use pydantic-settings for configuration | ✅ Accepted | 2026-02-19 |
| [ADR-0002](0002-struct-modbus-encoding.md) | Use Python struct for Modbus encoding | ✅ Accepted | 2026-02-19 |
| [ADR-0003](0003-isolation-forest-anomaly-detection.md) | Use IsolationForest + z-score ensemble for AI-IDS | ✅ Accepted | 2026-02-19 |
| [ADR-0004](0004-onnx-offline-inference.md) | Use ONNX Runtime for offline edge inference | ✅ Accepted | 2026-02-19 |
| [ADR-0005](0005-gcp-pubsub-telemetry.md) | Use GCP Pub/Sub for telemetry ingestion | ✅ Accepted | 2026-02-19 |

---

## How to Add a New ADR

1. Copy the template: `cp 0000-template.md 000N-short-title.md`
2. Fill in all sections
3. Add a row to the index table above
4. Submit as a PR with label `adr`

**Template structure:**
```markdown
# ADR-000N: Title

## Status
Proposed | Accepted | Deprecated | Superseded by [ADR-XXXX]

## Context
...

## Decision
...

## Consequences
### Positive
### Negative
### Neutral
```
