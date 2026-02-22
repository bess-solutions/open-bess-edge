# IEC 62443 SL-2 Certification Path

**Version:** 1.0  
**Date:** 2026-02-22  
**Status:** Active — roadmap document

---

## Objective

This document defines the **step-by-step path** for BESSAI Edge Gateway to obtain formal **IEC 62443-3-3 Security Level 2 (SL-2) certification** from an accredited third-party body (TÜV SÜD, DNV, or Bureau Veritas).

SL-2 certification is the industry threshold for industrial automation and control systems (IACS) connected to critical infrastructure. It is required by several national regulatory frameworks (Spain REE, Germany BNetzA) and is a strong differentiator for international sales.

---

## Current Baseline

Based on the existing `iec62443_sl2_gap.md` analysis:

| Domain | Current Status | Gap |
|---|---|---|
| Authentication (SR 1.1) | API key auth implemented | Needs MFA for management access |
| Audit logging (SR 2.8) | Structured logs via structlog | Log forwarding to SIEM needed |
| Software integrity (SR 3.2) | SLSA Level 2 + cosign | Not formally evaluated by auditor |
| Vulnerability disclosure (SR 2.12) | `SECURITY.md` exists | No formal PSIRT process |
| Patch management (SR 2.2) | Dependabot + CI | Formal patch SLA document needed |
| Communication integrity (SR 3.1) | TLS enforced (Ingress) | mTLS for OT segment not implemented |
| Network segmentation (SR 5.2) | Docker network isolation | Formal network diagram needed |

**Estimated SL-2 readiness:** ~65%

---

## Certification Path

### Phase 1 — Pre-Assessment (Q1 2026)

**Cost estimate:** ~USD 5,000–8,000 (pre-audit consulting)  
**Duration:** 4–6 weeks

- [ ] Engage a pre-assessment consultant (TÜV SÜD Digital Service or DNV Advisory)
- [ ] Produce formal **System Security Plan (SSP)** — maps BESSAI architecture to IEC 62443-3-3 Security Requirements (SR)
- [ ] Produce **Network Architecture Diagram** documenting OT/IT separation
- [ ] Implement formal **PSIRT (Product Security Incident Response Team)** process — publish `SECURITY.md` PSIRT section
- [ ] Produce formal **Patch Management SLA** document: Critical CVEs patched within 30 days, High within 90 days

### Phase 2 — Gap Remediation (Q1–Q2 2026)

**Duration:** 6–10 weeks (parallel to Phase 1 tail)

| Gap | Remediation | Owner |
|---|---|---|
| MFA for management | Implement TOTP for admin dashboard via `pyotp` | Engineering |
| SIEM log forwarding | Add Fluentd/Loki output target for audit logs | Engineering |
| mTLS for OT segment | Add mutual TLS config to Modbus TCP wrapper | Engineering |
| Formal network diagram | Create `docs/architecture/network_diagram.md` with OT zones | Engineering |

### Phase 3 — Formal Audit (Q2–Q3 2026)

**Cost estimate:** ~USD 25,000–45,000 (full SL-2 audit)  
**Duration:** 8–12 weeks

- [ ] Select accredited Certification Body (CB): **TÜV SÜD** or **DNV GL**
- [ ] Submit formal audit package (SSP + evidence + test reports)
- [ ] Participate in on-site audit (can be done remotely for software-only components)
- [ ] Address audit findings (finding period typically 30–60 days)
- [ ] Receive IEC 62443 SL-2 Certificate (valid 3 years, annual surveillance)

### Phase 4 — Maintain Certification (Ongoing)

- Annual surveillance audit (lower cost, ~USD 5,000)
- Notify CB within 30 days of any significant architecture change
- Update SSP after any MAJOR version release
- Track CVEs and apply patches per Patch Management SLA

---

## Budget Summary

| Phase | Cost (USD) | Timeline |
|---|---|---|
| Pre-assessment | 5,000–8,000 | Q1 2026 |
| Gap remediation (engineering) | Internal | Q1–Q2 2026 |
| Formal audit | 25,000–45,000 | Q2–Q3 2026 |
| Annual surveillance | 5,000/year | Ongoing |
| **Total (Year 1)** | **~35,000–55,000** | **Q1–Q3 2026** |

---

## Shortlisted Certification Bodies

| Body | Region | Contact | Notes |
|---|---|---|---|
| TÜV SÜD | Global (Germany HQ) | ics@tuev-sued.de | Most recognized in LATAM enterprise sales |
| DNV GL Cyber | Global (Norway HQ) | cybersecurity@dnv.com | Strong oil & gas and energy sector |
| Bureau Veritas | Global (France HQ) | — | Recognized by Chilean regulator CNE |

---

## Impact on Adoption

IEC 62443 SL-2 certification unlocks:
- **European market** — required for grid-connected BESS >100kW in Germany, UK, Spain
- **Enterprise customers** — CISOs require IEC 62443 for OT procurement
- **Insurance** — cyber insurance premiums reduced with SL-2 evidence
- **Government procurement** — Chilean ley de ciberseguridad (2024) expects IEC 62443 for critical infrastructure
