# BESSAI — PSIRT Process (Product Security Incident Response Team)

**Version:** 1.0  
**Date:** 2026-02-22  
**Status:** Active  
**Owner:** BESSAI Core Team — ingenieria@bess-solutions.cl

---

## Overview

BESSAI Edge Gateway is deployed in critical energy infrastructure. This document defines the formal **Product Security Incident Response Team (PSIRT)** process for receiving, triaging, remediating, and disclosing vulnerabilities in the `open-bess-edge` software.

This process satisfies:
- IEC 62443-2-1 SR 2.12 (vulnerability management)
- OpenSSF Best Practices — Silver/Gold criteria (vulnerability disclosure process)
- ISO/IEC 29147 (coordinated vulnerability disclosure)

---

## PSIRT Contact

| Channel | Details |
|---|---|
| **Primary email** | ingenieria@bess-solutions.cl |
| **GitHub Security** | [Private Security Advisory](https://github.com/bess-solutions/open-bess-edge/security/advisories/new) |
| **PGP key fingerprint** | See `SECURITY.md` |
| **Response SLA** | Acknowledgment within **48 hours** |

> [!CAUTION]
> **Do NOT report vulnerabilities as public GitHub Issues.** This exposes unpatched systems to attackers before a fix is available. Always use the channels above.

---

## Severity Classification

BESSAI uses CVSS v3.1 for severity scoring:

| CVSS Score | Severity | Example |
|---|---|---|
| 9.0 – 10.0 | **Critical** | RCE via Modbus parsing, auth bypass |
| 7.0 – 8.9 | **High** | Privilege escalation, DoS of safety module |
| 4.0 – 6.9 | **Medium** | Information disclosure, log injection |
| 0.1 – 3.9 | **Low** | Minor info leak, non-exploitable bug |

---

## Vulnerability Lifecycle

```
Reporter → [Private Disclosure] → PSIRT Acknowledgment (48h)
                                        ↓
                              [Triage & Severity Assessment] (5 days)
                                        ↓
                              [Patch Development] (per SLA below)
                                        ↓
                              [Coordinated Disclosure] (with reporter)
                                        ↓
                              [Public Advisory + Release] 
```

---

## Patch Management SLA

See [`docs/compliance/patch_management_sla.md`](patch_management_sla.md) for the full SLA.

| Severity | Patch SLA | Disclosure SLA |
|---|---|---|
| **Critical** | 14 calendar days | 14 days after patch release |
| **High** | 30 calendar days | 30 days after patch release |
| **Medium** | 90 calendar days | 90 days after patch release |
| **Low** | Best effort (next minor release) | With release notes |

If the patch cannot be completed within the SLA, PSIRT will:
1. Notify the reporter with a justified extension request (max +30 days for Critical)
2. Publish a mitigation advisory if available (e.g., "disable feature X as workaround")

---

## PSIRT Process — Step by Step

### Phase 1: Receipt & Acknowledgment (0–48 hours)

1. Reporter submits via email or GitHub Security Advisory
2. PSIRT member assigns a **tracking ID**: `BESSAI-SEC-YYYY-NNN`
3. Send acknowledgment email to reporter:
   - Confirm receipt
   - Provide tracking ID
   - Confirm NDA/embargo terms if reporter requests

### Phase 2: Triage (48 hours – 5 days)

1. Reproduce the vulnerability in a test environment
2. Assign CVSS v3.1 score (use [CVSS calculator](https://www.first.org/cvss/calculator/3.1))
3. Determine affected versions (check git history)
4. Assess exploitability in real deployments
5. Notify reporter of confirmed severity and target patch date

### Phase 3: Patch Development (per SLA)

1. Create a **private fork** or **draft GitHub Security Advisory** for the fix
2. Develop and test the patch
3. Update `CHANGELOG.md` (without disclosing the CVE ID yet)
4. Run the full test suite (`pytest tests/ -v --tb=short`)
5. Request review from a second Core Maintainer (two-person integrity — no self-merge)

### Phase 4: Coordinated Disclosure

1. Share the patch/advisory draft with the reporter for review (at least 72 hours before release)
2. Agree on a disclosure date
3. Prepare the GitHub Security Advisory draft (published on disclosure date)
4. Reserve a CVE ID via GitHub Security Advisories (automatic) or MITRE if needed

### Phase 5: Release & Public Disclosure

1. Merge the patch to `main`
2. Tag a new release (patch or minor, per [release process](../release_process.md))
3. Publish the GitHub Security Advisory
4. Update `CHANGELOG.md` with the public CVE reference
5. Post in GitHub Discussions: "Security advisory published: BESSAI-SEC-YYYY-NNN"
6. Notify adopters listed in [`docs/adopters.md`](../adopters.md) via email if deploying in production

---

## CVE Numbering Authority (CNA)

BESSAI requests CVE IDs via **GitHub Security Advisories**, which is an accredited CNA.

For vulnerabilities affecting BESSAI alongside a third-party library (e.g., pymodbus), coordinate with that project's maintainers before disclosure.

---

## Known Vulnerability Tracking

All resolved vulnerabilities are tracked in GitHub Security Advisories:
`https://github.com/bess-solutions/open-bess-edge/security/advisories`

---

## PSIRT Team Members

| Role | Contact |
|---|---|
| **PSIRT Lead** | Rodrigo — ingenieria@bess-solutions.cl |
| **Engineering Contact** | BESSAI Core Team |

---

## References

- [SECURITY.md](../../SECURITY.md) — Public vulnerability disclosure policy
- [Patch Management SLA](patch_management_sla.md)
- [IEC 62443 SL-2 Certification Path](iec_62443_sl2_certification_path.md)
- [ISO/IEC 29147:2018](https://www.iso.org/standard/72311.html) — Coordinated vulnerability disclosure
- [FIRST CVSS v3.1](https://www.first.org/cvss/v3-1/)
