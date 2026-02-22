# Patch Management SLA — BESSAI Edge Gateway

**Document:** PMS-001  
**Version:** 1.0  
**Date:** 2026-02-22  
**IEC 62443 reference:** SR 2.2 — Patch Management  
**Status:** Active

---

## 1. Patch SLA by Severity

| Severity | CVSS v3.1 | Fix SLA | Deployment SLA |
|----------|-----------|---------|----------------|
| **Critical** | 9.0–10.0 | **≤ 7 cal. days** | ≤ 24h after fix |
| **High** | 7.0–8.9 | **≤ 30 cal. days** | ≤ 72h after fix |
| **Medium** | 4.0–6.9 | **≤ 90 cal. days** | Next scheduled release |
| **Low** | 0.1–3.9 | **≤ 180 cal. days** | Next scheduled release |

> [!IMPORTANT]
> Any CVE with potential for physical harm (battery thermal runaway, grid instability) is treated as **Critical regardless of CVSS score** — Zero-Day Emergency Protocol: 24h response, out-of-band patch.

---

## 2. Detection Sources

| Tool | Scope | Cadence |
|------|-------|---------|
| **Dependabot** | Python deps (`requirements.txt`) | Daily automated PRs |
| **Trivy** (CI) | Container image CVE scan | Every build + weekly scheduled |
| **OSSF Scorecard** | Supply chain security posture | Weekly (GitHub Actions) |
| **NVD / CISA ICS-CERT** | ICS-specific CVEs | Manual review weekly |

---

## 3. Patch Workflow

```
CVE Detected
  │
  ▼
Triage (Engineering Lead, ≤ 24h)
  │
  ├─ Critical/High ─► Emergency branch: security/CVE-YYYY-XXXXX
  │                    Fix → PR → CI → cosign sign → release
  │
  └─ Medium/Low ────► Sprint backlog → next planned release
```

**Emergency requirements (Critical/High):**
- Peer review by ≥ 1 engineer (async allowed for speed)
- Full `pytest tests/ -q` must pass
- Image signed with `cosign` before release
- GitHub Release + security@bess-solutions.cl notification within 2h

---

## 4. Version Support Policy

| Status | Support |
|--------|---------|
| Latest stable (`v2.x`) | All severity levels |
| Previous minor (`v1.7.x`) | Critical + High only |
| Older | No support — upgrade required |

---

## 5. Dependency Pinning

| Layer | Strategy |
|-------|---------|
| Python deps | `requirements.txt` with `>=X.Y.Z` + Dependabot |
| Container base | `python:3.12-slim` + Trivy on every build |
| Infrastructure | Docker digest pinning in production |

> **Planned v2.2.0:** `pip-compile --generate-hashes` for reproducible builds (OpenSSF Gold Badge).

---

*Satisfies IEC 62443-2-3 and IEC 62443-3-3 SR 2.2 for SL-2 pre-assessment.*
