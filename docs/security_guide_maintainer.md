# BESSAI Edge Gateway — Maintainer Security Guide

**Version:** 1.0  
**Date:** 2026-02-22  
**Audience:** Repository maintainers and core contributors  
**Status:** Active — required reading for all maintainers

---

## Overview

This guide defines the security responsibilities and mandatory practices for all maintainers of the `open-bess-edge` repository. Because BESSAI controls physical battery hardware and is deployed in critical energy infrastructure, supply chain integrity and access security are paramount.

> [!IMPORTANT]
> All maintainers **must complete** the checklist in the [Onboarding Checklist](#maintainer-onboarding-checklist) before merging their first PR.

---

## 1. Account Security

### 1.1 Two-Factor Authentication (2FA)

**Mandatory.** All accounts with write access to this repository must have 2FA enabled.

- **Required type:** TOTP app (Google Authenticator, Authy, 1Password) or hardware key (YubiKey)
- **SMS 2FA is NOT accepted** — it is vulnerable to SIM-swapping attacks
- **Verification:** GitHub enforces 2FA via organization settings. Accounts without 2FA lose access automatically.

```bash
# Verify your 2FA status:
# GitHub → Settings → Password and authentication → Two-factor authentication
```

### 1.2 SSH Key Management

- Use **Ed25519** SSH keys, never RSA-2048 or DSA
- Set a strong passphrase on your SSH private key
- Rotate SSH keys annually or immediately upon compromise

```bash
# Generate a new Ed25519 key:
ssh-keygen -t ed25519 -C "your-email@bess-solutions.cl" -f ~/.ssh/id_bessai_ed25519
```

### 1.3 GPG Commit Signing

All commits merged to `main` must be GPG-signed.

```bash
# Generate a GPG key (RSA 4096 or ed25519):
gpg --full-generate-key

# Get your key ID:
gpg --list-secret-keys --keyid-format=long

# Configure Git to sign commits:
git config --global user.signingkey YOUR_KEY_ID
git config --global commit.gpgsign true

# Add key to GitHub:
gpg --armor --export YOUR_KEY_ID
# Copy output → GitHub → Settings → SSH and GPG keys → New GPG key
```

---

## 2. Repository Access Control

### 2.1 Least Privilege

| Role | Permissions | Notes |
|---|---|---|
| **Core Maintainer** | Write + merge to `main` | Must have 2FA + GPG signing |
| **Module Maintainer** | Write to specific branches | Cannot merge to `main` |
| **Contributor** | Fork + PR only | No direct write access |
| **CI/CD Bot** | Scoped secrets via OIDC | No human credentials |

### 2.2 Branch Protection Rules

`main` branch has the following protections enforced:

- ✅ Require pull request before merging (minimum 1 approval)
- ✅ Require status checks (CI must pass: ruff, mypy, pytest, bandit, trivy)
- ✅ Require linear history (no merge commits)
- ✅ Restrict who can push (only Core Maintainers)
- ✅ Block force pushes — **never override this**
- ✅ Require signed commits

### 2.3 Two-Person Integrity Rule

> **No maintainer may merge a PR they authored.**

This is enforced by the branch protection setting "Restrict who can approve pull requests" which prevents self-approval. The rationale:
- Prevents single points of compromise in the supply chain
- Required for OpenSSF Silver/Gold badge criteria
- Aligns with IEC 62443 SR 2.12 (access control separation)

---

## 3. Secrets Management

### 3.1 GitHub Secrets

Current secrets used in CI/CD:

| Secret | Used by | Notes |
|---|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `release.yml`, `ci.yml` | Keyless auth via WIF — no expiry |
| `GCP_SERVICE_ACCOUNT` | `release.yml`, `ci.yml` | Scoped to Artifact Registry + Pub/Sub |
| `GCP_REGION` | `release.yml` | e.g., `us-central1` |
| `GCP_PROJECT_ID` | `release.yml` | GCP project ID |
| `DISCORD_WEBHOOK_URL` | `weekly-update.yml` | Community weekly update |

**Rules:**
1. **Never commit secrets to the repository** — even in comments or test files
2. **Never log secrets** — use `::add-mask::` in GitHub Actions if a secret appears in output
3. **Rotate secrets annually** or immediately upon suspected compromise
4. **Use OIDC/WIF** for GCP authentication — never store service account JSON keys as secrets

### 3.2 Dependency Secrets

- Dependabot PRs are reviewed before merge — they can introduce malicious dependencies via typosquatting
- Check the `pip-audit` report in CI for known CVEs before approving a dependency update PR

---

## 4. Code Review Security

### 4.1 Security-Sensitive Areas

Always request review from a Core Maintainer (in addition to normal review) when PRs touch:

| Area | Risk |
|---|---|
| `src/core/safety.py` | Safety-critical — controls physical hardware limits |
| `src/drivers/*.py` | Direct hardware interface — malicious code could damage batteries |
| `.github/workflows/*.yml` | CI/CD supply chain — could exfiltrate secrets or deploy malicious images |
| `infrastructure/docker/Dockerfile` | Container image integrity |
| `requirements.txt` or `pyproject.toml` | Supply chain — dependency confusion attacks |

### 4.2 What to Check in PRs

- [ ] No hardcoded credentials, API keys, or tokens
- [ ] No `eval()`, `exec()`, or `subprocess` calls with unsanitized input
- [ ] Exception handlers do not silently swallow errors in `core/` or `drivers/`
- [ ] New dependencies are legitimate (check PyPI, GitHub stars, maintainer activity)
- [ ] CI changes maintain all existing security gates (do not remove bandit, trivy, etc.)

---

## 5. Vulnerability Response (PSIRT)

### 5.1 Reporting a Vulnerability

See [`SECURITY.md`](../SECURITY.md) and [`docs/compliance/psirt_process.md`](compliance/psirt_process.md).

**PSIRT contact:** ingenieria@bess-solutions.cl  
**PGP key:** Published on `SECURITY.md`

### 5.2 Maintainer Obligations

When notified of a vulnerability:

1. **Acknowledge within 48 hours** — reply to the reporter with confirmation and a tracking number
2. **Assess severity within 5 days** — use CVSS v3.1 scoring
3. **Prepare patch and advisory draft** — do not disclose publicly yet
4. **Coordinate disclosure** — notify reporter of target disclosure date (max 90 days from report)
5. **Publish GitHub Security Advisory** — after patch is merged and released
6. **Patch SLA** (from `patch_management_sla.md`):
   - CVSS Critical (9.0–10.0): patch within **14 days**
   - CVSS High (7.0–8.9): patch within **30 days**
   - CVSS Medium (4.0–6.9): patch within **90 days**

---

## 6. Release Security

### 6.1 Release Process Summary

See the full release process at [`docs/release_process.md`](release_process.md).

### 6.2 Release Security Gates

Before creating a release tag, verify:

- [ ] All CI checks pass on `main` (ruff, mypy, pytest 378/378, bandit, trivy ✅)
- [ ] `CHANGELOG.md` updated with all changes
- [ ] No open CRITICAL or HIGH CVEs in `pip-audit` output
- [ ] `release.yml` workflow will run: SBOM generation, cosign signing, SLSA provenance

### 6.3 Artifact Verification

Users can verify release artifacts:

```bash
# Verify Docker image signature (cosign keyless)
cosign verify \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp "https://github.com/bess-solutions/open-bess-edge/.github/workflows/release.yml" \
  ghcr.io/bess-solutions/open-bess-edge:v1.8.0

# Verify SLSA provenance
slsa-verifier verify-image \
  --source-uri github.com/bess-solutions/open-bess-edge \
  ghcr.io/bess-solutions/open-bess-edge:v1.8.0
```

---

## 7. Incident Response

### 7.1 Suspected Supply Chain Compromise

**If you suspect the repository, CI/CD pipeline, or any released artifact has been compromised:**

1. **Immediately notify** the PSIRT team: ingenieria@bess-solutions.cl
2. **Do not push** any new commits until the investigation is complete
3. **Revoke all CI/CD secrets** via GitHub → Settings → Secrets (takes effect immediately)
4. **Rotate** all GCP service account keys and WIF configurations
5. **Contact GitHub Security** if you suspect a platform-level compromise
6. **Notify adopters** if a released artifact is affected — see `SECURITY.md` for disclosure process

### 7.2 Compromised Maintainer Account

1. Remove the account's write access immediately (GitHub → Settings → Collaborators)
2. Audit recent commits and PRs merged by that account
3. If suspicious commits were merged, follow supply chain compromise procedure above
4. Issue a security advisory if any released artifact was affected

---

## Maintainer Onboarding Checklist

Complete this checklist before your first merge:

- [ ] Enable 2FA on your GitHub account (TOTP, not SMS)
- [ ] Generate and configure GPG signing key for commits
- [ ] Add your GPG public key to GitHub
- [ ] Configure `git config --global commit.gpgsign true`
- [ ] Read this guide completely
- [ ] Read [`SECURITY.md`](../SECURITY.md) and [`CONTRIBUTING.md`](../CONTRIBUTING.md)
- [ ] Acknowledge the two-person integrity rule in writing (reply to your onboarding PR)

---

## References

- [OpenSSF Best Practices — Gold Badge](https://bestpractices.dev/en/criteria/2)
- [IEC 62443-3-3 Security Level 2](docs/compliance/iec_62443_sl2_certification_path.md)
- [PSIRT Process](docs/compliance/psirt_process.md)
- [OpenSSF Gold Checklist](openssf_gold_checklist.md)
- [SLSA Framework](https://slsa.dev/)
- [Sigstore / cosign](https://docs.sigstore.dev/)
