# Security Policy — BESSAI Edge Gateway

## Supported Versions

| Version | Supported |
|---|---|
| 1.3.x (latest) | ✅ Active support |
| 1.2.x | ✅ Security patches only |
| < 1.2 | ❌ End of life |

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
