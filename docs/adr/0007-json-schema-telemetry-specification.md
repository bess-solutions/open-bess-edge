# ADR-0007: Adopt JSON Schema (Draft 2020-12) as the Normative Format for Telemetry Specifications

## Status
✅ Accepted — 2026-02-22

## Context

BESSAI-SPEC-003 defines the canonical message format for all telemetry published by BESSAI Edge Gateways. We needed a machine-readable, language-agnostic format for these schemas that:
- Is parseable by code (for validation in CI and at runtime)
- Is human-readable without tooling
- Is widely supported across programming languages and cloud services
- Supports versioning and schema evolution clearly
- Can be validated by existing tools without custom parsers

Alternatives considered:

| Format | Pros | Cons |
|---|---|---|
| **JSON Schema** | Language-agnostic, broad tooling (Python: `jsonschema`, GCP native), widely adopted in OpenAPI | Can be verbose for complex schemas |
| **Protocol Buffers (protobuf)** | Compact binary encoding, strong typing | Requires code generation; not human-readable; overkill for JSON REST/MQTT |
| **Apache Avro** | Excellent for Kafka/Confluent ecosystems, compact | Schema registry dependency; less familiar to OT engineers |
| **OpenAPI 3.1** | Industry standard for REST APIs | Focused on REST only; not well-suited for MQTT/Pub/Sub schemas |
| **YANG** | IEC and telecom standard for network device config | Very steep learning curve; tooling requires specialized expertise |

## Decision

Use **JSON Schema Draft 2020-12** as the normative format for all BESSAI telemetry schemas, as defined in BESSAI-SPEC-003.

Key details:
- Schemas are embedded inline in the spec documents (under `docs/specs/`) for readability
- A separate `docs/specs/schemas/` directory contains standalone `.json` schema files for CI validation
- The `$id` URI pattern `https://bessai.io/schemas/v1/<schema>.json` is used for canonical identification
- Python validation in CI uses the `jsonschema` library (already a transitive dependency via FastAPI)

## Consequences

### Positive
- **CI validation**: GitHub Actions can validate all telemetry messages in integration tests against the schema, catching breaking changes before merge
- **Multi-language compatibility**: Any team adding a consumer (Python, TypeScript, Go) can use native JSON Schema validators
- **GCP native**: GCP Pub/Sub Schema Registry supports Avro and JSON Schema natively — enables schema enforcement at the broker level
- **OpenAPI alignment**: JSON Schema 2020-12 is the same dialect used by OpenAPI 3.1, enabling future auto-generation of API docs from the telemetry schemas
- **Low barrier**: No code generation step; schemas are plain JSON files any developer can read and modify

### Negative
- **Verbosity**: JSON Schema is more verbose than Protobuf or Avro for complex nested types
- **No binary encoding**: JSON is ~3-5× larger than Protobuf binary for the same data (acceptable at our telemetry frequency)

### Neutral
- Schema IDs use the `https://bessai.io/schemas/` namespace; the domain must eventually host the actual schema files (or redirect to GitHub)
- Schema evolution follows BESSAI-SPEC-003 §6 versioning rules, not JSON Schema's own mechanisms
