# Security Policy — BESSAI Edge Gateway

## Supported Versions

| Version | Supported |
|---|---|
| 2.1.x (latest) | ✅ Active support — all CVEs |
| 2.0.x | ✅ Security patches — Critical + High |
| 1.7.x | ⚠️ Critical patches only |
| < 1.7 | ❌ End of life |

## Reporting a Vulnerability

**⚠️ Do NOT report security vulnerabilities via public GitHub Issues.**

### Preferred Channel — GitHub Security Advisories (Private)

Use GitHub's private, encrypted reporting channel:

1. Navigate to the [Security Advisories page](https://github.com/bess-solutions/open-bess-edge/security/advisories)
2. Click **"Report a vulnerability"**
3. Fill out the form with maximum detail

### Alternative Channel

Email: **security@bess-solutions.cl**
- Use PGP encryption if possible (key available on [keys.openpgp.org](https://keys.openpgp.org/))
- Subject: `[BESSAI SECURITY] <brief description>`

---

## What to Include in Your Report

Please include as much of the following as possible:

```
- Type of vulnerability (e.g., injection, auth bypass, DoS, info disclosure)
- Affected component (e.g., Dashboard API, Modbus driver, config parsing)
- Full path to the file(s) with the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if available)
- Impact assessment: what an attacker could achieve
- CVSS score suggestion (optional)
```

---

## Response Timeline

| Event | Target SLA |
|---|---|
| Acknowledgement of receipt | **≤ 48 hours** |
| Initial triage & severity assessment | **≤ 5 business days** |
| Status update to reporter | **≤ 14 days** |
| Patch release (Critical/High) | **≤ 30 days** |
| Patch release (Medium/Low) | **≤ 90 days** |
| Public disclosure (coordinated) | **After patch is released** |

---

## Severity Classification

We follow the [CVSS v3.1](https://www.first.org/cvss/v3.1/specification-document) scoring system:

| Severity | CVSS Score | Expected Response |
|---|---|---|
| Critical | 9.0–10.0 | Immediate — patch within 30 days |
| High | 7.0–8.9 | Patch within 30 days |
| Medium | 4.0–6.9 | Patch within 90 days |
| Low | 0.1–3.9 | Patch in next scheduled release |

---

## Industrial / ICS Specific Concerns

Given that BESSAI Edge Gateway operates in **industrial environments (ICS/OT)**, we treat the following with Critical priority:

- **Modbus protocol injection** — commands that could cause unsafe battery operation
- **Safety Guard bypass** — circumventing SOC/temperature safety limits
- **Authentication bypass** — in Dashboard API or ONNX inference endpoints
- **Denial of Service** — that could disrupt BESS operational cycles
- **Credential exposure** — GCP service account keys, API tokens

Any vulnerability with potential for **physical harm** (battery fire, grid instability) is treated under a **Zero-Day Emergency Protocol**: 24-hour response, out-of-band patch.

---

## Scope

### In Scope
- `src/` — all Python source modules
- `infrastructure/docker/` — Dockerfile and docker-compose configurations
- `infrastructure/terraform/` — GCP infrastructure-as-code
- `.github/workflows/` — CI/CD pipeline configurations
- `config/` — configuration handling and secrets management

### Out of Scope
- Third-party dependencies (report to the respective upstream project)
- GCP infrastructure managed by Google
- Social engineering attacks
- Physical security (data center access)

---

## Safe Harbor

BESS Solutions commits to:

- Not pursue legal action against security researchers acting in **good faith**
- Work collaboratively to understand and resolve reported issues
- Publicly credit researchers in our release notes (unless anonymity is preferred)
- Not share researcher identity without explicit permission

---

## Security Updates Notification

Subscribe to security notifications:
- **GitHub Watch** → "Security alerts" on [bess-solutions/open-bess-edge](https://github.com/bess-solutions/open-bess-edge)
- **GitHub Releases** → new releases always include a security changelog section

---

## Compliance Standards

This project targets compliance with:

- **IEC 62443** — Industrial Automation and Control Systems Security
- **NIST SP 800-82** — Guide to Industrial Control Systems Security
- **NTSyCS** — Norma Técnica de Seguridad y Calidad de Servicio (CEN Chile)

See [`docs/compliance/`](docs/compliance/) for detailed compliance mappings.

Key compliance documents:
- [System Security Plan (SSP-001)](docs/compliance/ssp_iec62443_sl2.md) — IEC 62443-3-3 SL-2 coverage
- [Patch Management SLA (PMS-001)](docs/compliance/patch_management_sla.md) — IEC 62443-2-3
- [Network Architecture (NAD-001)](docs/architecture/network_diagram.md) — IEC 62443-3-2
- [SL-2 Certification Path](docs/compliance/iec_62443_sl2_certification_path.md)

---

## PSIRT — Product Security Incident Response Team

**IEC 62443-3-3 SR 2.12 — Non-repudiation | Vulnerability disclosure**

### Contact

| Channel | Address | SLA |
|---------|---------|-----|
| GitHub Security Advisories (preferred) | [Report privately](https://github.com/bess-solutions/open-bess-edge/security/advisories/new) | 48h acknowledgement |
| Email | security@bess-solutions.cl | 48h acknowledgement |
| Emergency (physical safety risk) | security@bess-solutions.cl Subject: `[EMERGENCY]` | 4h response |

### PSIRT Process

1. **Receipt** — Researcher submits via GitHub Security Advisory or email
2. **Acknowledgement** — PSIRT acknowledges within 48h (4h for [EMERGENCY])
3. **Triage** — Engineering Lead assigns CVSS score and severity within 5 business days
4. **Remediation** — Fix timeline per [Patch Management SLA](docs/compliance/patch_management_sla.md)
5. **Coordination** — PSIRT works with researcher on disclosure timeline (default: 90 days)
6. **Disclosure** — CVE requested from MITRE; GitHub Advisory published; release notes updated
7. **Credit** — Researcher credited in release notes unless anonymity requested

### ICS-Specific Emergency Protocol

If the vulnerability has potential for **physical harm** (battery fire, grid instability, safety system bypass):

- Response SLA: **4 hours** (not 48)
- Out-of-band patch issued **within 24 hours** of confirmation
- Immediate notification to affected site operators via `SITE_ID`-tagged alert
- Coordinated disclosure with CISA ICS-CERT if CVSS ≥ 9.0

### PSIRT Team

| Role | Responsibility |
|------|---------------|
| PSIRT Lead | Triage, coordination, disclosure | 
| Engineering Lead | Fix implementation, patch review |
| Site Operations | Deployment coordination with field teams |
