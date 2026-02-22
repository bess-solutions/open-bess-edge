# BESSAI Benchmark 003 — Security Analysis

**Version:** 1.0.0  
**Date:** 2026-02-22  
**Status:** Active

---

## Overview

This benchmark documents the results of static security analysis, dependency audit, and conceptual attack surface review for BESSAI Edge Gateway v1.7.1. It is intended to provide transparent, reproducible evidence of the project's security posture.

---

## 1. Static Analysis (Bandit)

Bandit is a Python AST-based security linter that detects common security issues.

### How to Run

```bash
bandit -r src/ -ll --format json -o docs/benchmarks/bandit_results.json
bandit -r src/ -ll  # human-readable
```

### Results (v1.7.1)

| Severity | Count | Notes |
|---|---|---|
| **HIGH** | 0 | ✅ No high-severity issues |
| **MEDIUM** | 0 | ✅ No medium-severity issues |
| **LOW** | 2 | Subprocess usage (acceptable — in `ai_ids.py`, reviewed) |

**Enforced in CI:** Yes. The `bandit` step in `.github/workflows/ci.yml` runs on every PR with `-ll` (medium+) — any finding at medium or above blocks merge.

---

## 2. Dependency Vulnerability Audit (Trivy)

Trivy scans the Docker image for known CVEs in OS packages and Python dependencies.

### How to Run

```bash
# Scan the production Docker image
trivy image --severity HIGH,CRITICAL ghcr.io/bess-solutions/open-bess-edge:latest

# Scan local dependencies only
trivy fs --security-checks vuln requirements.txt
```

### Results (v1.7.1)

| Severity | Count | Notes |
|---|---|---|
| **CRITICAL** | 0 | ✅ |
| **HIGH** | 0 | ✅ |
| **MEDIUM** | 3 | Transitive deps — tracked, no known exploitable path |
| **LOW** | 11 | Informational |

**Enforced in CI:** Yes. The `trivy` step blocks on CRITICAL/HIGH findings.

---

## 3. Supply Chain Security (OpenSSF Scorecard)

The OpenSSF Scorecard evaluates the project's supply chain security practices automatically on every push to `main`.

### How to Run

```bash
# Requires GITHUB_TOKEN
scorecard --repo=github.com/bess-solutions/open-bess-edge --format json
```

### Results (v1.7.1)

| Check | Score | Notes |
|---|---|---|
| Branch Protection | 10/10 | Required reviews + signed commits enforced |
| Code Review | 10/10 | Two-person integrity rule |
| Dependency Update Tool | 9/10 | Dependabot enabled for all ecosystems |
| SAST | 8/10 | Bandit + ruff + mypy in CI |
| Token Permissions | 10/10 | Minimal permissions on all workflows |
| Vulnerabilities | 10/10 | No open CVEs above threshold |
| Signed Releases | 9/10 | SLSA Level 2 + cosign signing |
| **Overall** | **9.3/10** | ✅ |

---

## 4. Dashboard API Penetration Test (Conceptual)

The Dashboard REST API (`src/interfaces/dashboard_api.py`) exposes the following endpoints and has been reviewed against OWASP Top 10:

| OWASP Risk | Endpoint | Mitigation | Status |
|---|---|---|---|
| A01 Broken Access Control | All `/api/v1/*` | `X-API-Key` auth (configurable) | ✅ Mitigated |
| A02 Cryptographic Failure | All endpoints | HTTPS enforced in production (Ingress/nginx) | ✅ Mitigated (infra) |
| A03 Injection | Query params | Pydantic validation on all inputs | ✅ Mitigated |
| A05 Security Misconfiguration | Health endpoint | `/health` is unauthenticated (by design) | ⚠️ Acceptable |
| A06 Vulnerable Components | Dependencies | Trivy + Dependabot (see §2) | ✅ Mitigated |
| A07 Auth Failures | Auth header | Rate limiting RECOMMENDED for production | ⚠️ Recommended |

**Formal penetration test:** Not yet performed. Planned as a prerequisite for IEC 62443 SL-2 certification (see `docs/compliance/iec_62443_sl2_certification_path.md`).

---

## 5. Mutation Testing (mutmut)

Mutation testing verifies the quality of the test suite by introducing code mutations and checking if tests catch them.

### How to Run

```bash
mutmut run --paths-to-mutate=src/core/safety.py,src/core/config.py
mutmut results
```

### Results (v1.7.1, safety.py)

| Metric | Value |
|---|---|
| Mutants generated | 84 |
| Killed (caught by tests) | 79 |
| Survived | 5 |
| **Mutation score** | **94.0%** |

Surviving mutants are reviewed and documented. None affect safety-critical code paths.

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-02-22 | Initial security benchmark (v1.7.1) |
