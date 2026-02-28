# Security Policy — BESSAI Edge Gateway

## Supported Versions

| Version | Support Status |
|---|---|
| v2.12.x (main) | ✅ Active support |
| v2.11.x | ⚠️ Security fixes only |
| < v2.11 | ❌ No longer supported |

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Report security issues via:

- **Email:** security@bess-solutions.cl
- **Response SLA:** Within 48 hours for acknowledgment; 90 days to patch.
- **Encryption:** PGP key available on request.

### What to include in your report

1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact (exploitability, affected components)
4. Suggested mitigation (optional)

## Scope

This security policy covers **BESSAI Edge Gateway** (`open-bess-edge`):

- `src/core/` — compliance and control logic
- `src/drivers/` — hardware drivers (Modbus, IEC 60870-5-104)
- `src/interfaces/` — publishers, health server, metrics

## Out of Scope

- Third-party libraries (report to their respective projects)
- Issues in trained AI models (stored privately — not in this repo)
- Physical security of BESS hardware installations

## Cybersecurity Standards

BESSAI Edge Gateway implements:

| Standard | Implementation |
|---|---|
| IEC 62443 SL-2 | `SL2SecurityGate` — RBAC, HMAC-SHA256, rate limiting |
| Ley Marco Ciberseguridad 21.663/2024 | `SecurityNotifier` — CSIRT notification ≤3h |
| OWASP Top 10 | No hardcoded secrets, input validation, structured logging |
| Apache 2.0 License | Open source — contributions welcome |

## Responsible Disclosure

We follow a **90-day coordinated disclosure** policy. Reporters who responsibly
disclose vulnerabilities will be credited in our CHANGELOG (unless they prefer anonymity).

## Known Security Notes

- **mTLS for CEN telemetry (GAP-003):** Certificates are never stored in this repo.
  Generate them via `bash infrastructure/certs/gen_certs.sh`.
- **AI models:** Trained ONNX models are not included in this open-source repository.
  They are distributed via the private `bessai-models` package.
- **Environment variables:** All sensitive configuration (endpoints, keys) must be
  set via `.env` file — never committed. See `.env.example`.

---
*BESS Solutions SpA — security@bess-solutions.cl*
