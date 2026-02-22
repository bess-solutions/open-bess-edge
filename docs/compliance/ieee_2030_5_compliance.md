# IEEE 2030.5 Compliance Analysis

**Version:** 1.0  
**Date:** 2026-02-22  
**Status:** Gap Analysis — Implementation Planned

---

## What is IEEE 2030.5?

IEEE 2030.5 (also known as SEP 2.0 — Smart Energy Profile) is the **North American and Australian standard** for DER (Distributed Energy Resource) communication with utilities. It defines the communication protocol between:

- **DER devices** (inverters, BESS, EV chargers) ← BESSAI sits here
- **DERMS / Utility head-end systems** ← utilities and aggregators

California's CPUC Rule 21 and Australia's AEMO AS/NZS 4777.2 both mandate IEEE 2030.5 for grid-connected DER above certain capacities.

---

## Why This Matters for BESSAI

BESSAI Edge Gateway currently communicates with GCP Pub/Sub using a proprietary JSON schema (BESSAI-SPEC-003). Adding an IEEE 2030.5 adapter would allow BESSAI sites to:

1. **Respond to utility dispatch commands** (DER control, demand response)
2. **Report DER status** to utility DERMS systems
3. **Enter Australian and North American markets** without custom integration
4. **Qualify for grid services revenue** (frequency regulation, demand response programs)

---

## IEEE 2030.5 Key Concepts vs BESSAI Mapping

| IEEE 2030.5 Concept | BESSAI Equivalent | Status |
|---|---|---|
| `DERSettings` (capacity, min/max power) | `BESSAI-SPEC-001` device profile | ✅ Exists (maps needed) |
| `DERStatus` (SOC, power, mode) | `BESSAI-SPEC-003` telemetry payload | ✅ Exists (maps needed) |
| `DERControl` (power setpoint, mode) | `write_tag("P_setpoint_kW")` | ✅ Exists (adapter needed) |
| `EndDevice` registration | Site registry (not yet formalized) | ⚠️ Partial |
| TLS 1.2 + client certs (mandatory) | TLS only (via Ingress) | ❌ No client certs yet |
| RESTful HTTP/2 server | Dashboard API (HTTP/1.1) | ❌ HTTP/2 not yet |
| `MirrorUsagePoint` (metering data) | Telemetry publish to GCP | ⚠️ Partial |

---

## Compliance Gap Summary

| Requirement | Gap | Priority |
|---|---|---|
| TLS 1.2 with mutual client certificates | Missing mTLS for DERMS communication | HIGH |
| IEEE 2030.5 REST endpoint on BESSAI | New module needed: `src/interfaces/sep2_adapter.py` | HIGH |
| `DERStatus` mapping from BESSAI telemetry | JSON transform needed | MEDIUM |
| `DERControl` command ingestion | Adapter maps IEEE 2030.5 control → `write_tag()` | MEDIUM |
| `EndDevice` XML registration flow | New init sequence needed | MEDIUM |
| HTTP/2 support | Dashboard API upgrade to HTTP/2 | LOW |

---

## Implementation Plan (SEP 2.0 Adapter)

### Module: `src/interfaces/sep2_adapter.py`

```python
"""
IEEE 2030.5 (SEP 2.0) Adapter for BESSAI Edge Gateway.

Exposes the DER as an IEEE 2030.5-compliant REST server and
translates utility commands to BESSDriver write_tag() calls.
"""
class SEP2Adapter:
    async def get_der_status(self, driver: DataProvider) -> dict: ...
    async def get_der_settings(self) -> dict: ...
    async def apply_der_control(self, control: dict, driver: DataProvider) -> None: ...
    async def mirror_usage_point(self, telemetry: dict) -> None: ...
```

### Estimated Effort

| Task | Effort |
|---|---|
| `SEP2Adapter` core implementation | 3–4 days |
| mTLS configuration (BESSAI ↔ DERMS) | 1 day |
| `DERStatus` / `DERControl` XML ↔ JSON mapping | 2 days |
| Integration tests | 2 days |
| Documentation | 1 day |
| **Total** | **~9–10 engineering days** |

---

## Relevant Standards References

- **IEEE 2030.5-2018** — Smart Energy Profile 2.0
- **CPUC Rule 21** — California interconnection requirements (DER >10 kW)
- **AEMO AS/NZS 4777.2** — Australian DER communication standard
- **SunSpec Alliance** — interoperability certification for SEP 2.0 implementations

---

## Next Steps

1. **Decide:** Implement native SEP 2.0 in BESSAI vs. use a commercial gateway adapter (e.g., SolarNetwork)
2. **Draft BEP-0100:** "Add SEP 2.0 Adapter Interface" — Standards Track BEP
3. **Contact SunSpec Alliance** for interop testing program
