# BESSAI Edge Gateway — Release Process

**Version:** 1.0  
**Date:** 2026-02-22  
**Owner:** Core Maintainer team  

---

## Overview

This document describes the end-to-end release process for `open-bess-edge`, from planning to published artifacts. All releases follow [Semantic Versioning 2.0](https://semver.org/) and [Conventional Commits](https://www.conventionalcommits.org/).

---

## Release Types

| Type | Version bump | When to use |
|---|---|---|
| **Patch** | `v1.8.0` → `v1.8.1` | Bug fixes, security patches, docs |
| **Minor** | `v1.8.0` → `v1.9.0` | New features, backwards-compatible |
| **Major** | `v1.8.0` → `v2.0.0` | Breaking API or protocol changes |
| **Pre-release** | `v2.0.0-rc.1` | Release candidates for testing |

---

## Release Cadence

- **Patch releases:** As needed (after security fixes or critical bugs)
- **Minor releases:** Every 4–6 weeks or after a meaningful feature milestone
- **Major releases:** Announced ≥ 30 days in advance via GitHub Discussions

---

## Step-by-Step Release Process

### Step 1 — Pre-Release Checklist

Run the full validation suite locally:

```bash
# From the repository root
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/ --ignore-missing-imports
pytest tests/ -v --cov=src --cov-fail-under=80
bandit -r src/ -ll
pip-audit -r requirements.txt
```

Verify on `main`:
- [ ] All CI checks green: `ruff` · `mypy` · `pytest` · `bandit` · `trivy` · `scorecard`
- [ ] No open CRITICAL or HIGH CVEs from `pip-audit`
- [ ] `CHANGELOG.md` has an entry for the new version under `[Unreleased]`

### Step 2 — Update Version Numbers

Update the version string in **all** of the following locations:

```bash
# 1. pyproject.toml
[project]
version = "1.9.0"   # ← update here

# 2. src/__init__.py (if exists)
__version__ = "1.9.0"

# 3. CHANGELOG.md — rename [Unreleased] to [1.9.0] with the date
## [1.9.0] — 2026-02-22
```

### Step 3 — Update CHANGELOG.md

Move items from `[Unreleased]` to `[X.Y.Z]` with today's date:

```markdown
## [1.9.0] — 2026-02-22

### Added
- docs: Security guide for maintainers (OpenSSF Gold)
- docs: Formal release process documentation
- ci: Atheris fuzzing workflow for Modbus parsers
- docs: IEC 62443 network architecture diagram
- docs: PSIRT process and Patch Management SLA

### Changed
- requirements.txt: hash pinning for reproducible builds

### Security
- chore: Updated openssf_gold_checklist.md with completed items

## [Unreleased]
```

### Step 4 — Commit & Tag

```bash
# Commit version bump
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): bump version to v1.9.0"

# Create an annotated tag (NOT lightweight)
git tag -a v1.9.0 -m "Release v1.9.0 — OpenSSF Gold + IEC 62443 remediations"

# Push tag — this triggers the release.yml workflow
git push origin main --follow-tags
```

> [!IMPORTANT]
> **Always use annotated tags** (`-a` flag). Lightweight tags do not trigger the `release.yml` workflow correctly and do not carry the signing metadata.

### Step 5 — Monitor CI/CD Release Pipeline

The `release.yml` workflow runs automatically on tag push and performs:

| Job | What it does | Expected duration |
|---|---|---|
| `release-docker` | Builds multi-arch image (amd64 + arm64), pushes to GCP Artifact Registry | ~8 min |
| `generate-sbom` | Generates CycloneDX SBOM (JSON + XML) | ~2 min |
| `sign-image` | Signs Docker image with cosign (Sigstore keyless) | ~1 min |
| `slsa-provenance` | Generates SLSA Level 2 build provenance | ~3 min |
| `create-release` | Creates GitHub Release with SBOM attachments + release notes | ~1 min |

Monitor at: `https://github.com/bess-solutions/open-bess-edge/actions`

### Step 6 — Post-Release Verification

After the pipeline completes:

```bash
# 1. Verify GitHub Release was created
open https://github.com/bess-solutions/open-bess-edge/releases/latest

# 2. Verify Docker image is available
docker pull ghcr.io/bess-solutions/open-bess-edge:v1.9.0

# 3. Verify cosign signature
cosign verify \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp "https://github.com/bess-solutions/open-bess-edge/.github/workflows/release.yml" \
  ghcr.io/bess-solutions/open-bess-edge:v1.9.0

# 4. Verify SBOM is attached to the GitHub Release
# → GitHub Release page → Assets → sbom-v1.9.0.cdx.json ✅

# 5. Verify PyPI package (if applicable)
pip install bessai-edge==1.9.0 --dry-run
```

### Step 7 — Announce the Release

- Post in [GitHub Discussions](https://github.com/bess-solutions/open-bess-edge/discussions) with the changelog summary
- The weekly Discord update (`weekly-update.yml`) will automatically mention the new release the following Monday

---

## Hotfix / Security Patch Process

For urgent security fixes (CVSS ≥ 9.0 — must patch within 14 days per Patch Management SLA):

```bash
# 1. Create hotfix branch from the affected release tag
git checkout -b hotfix/cve-2026-XXXX v1.8.0

# 2. Apply the security fix
# ... make changes ...

# 3. Merge to main via PR (with security maintainer approval)
# Use the label "security" on the PR

# 4. Backport to current stable if the fix is applicable
git cherry-pick <commit-hash>

# 5. Tag a patch release immediately
git tag -a v1.8.1 -m "security: patch CVE-2026-XXXX"
git push origin main --follow-tags

# 6. Publish GitHub Security Advisory
# GitHub → Security → Advisories → New draft advisory
```

---

## PyPI Release (when applicable)

The `pypi.yml` workflow handles PyPI publication:

```bash
# Triggered automatically when release.yml completes successfully for non-pre-release tags
# Manual trigger:
gh workflow run pypi.yml --field tag=v1.9.0
```

---

## Rollback Procedure

If a release is found to be broken after publication:

1. **Mark the GitHub Release as pre-release** (not "latest") immediately
2. **Do NOT delete tags** — this breaks provenance chains and SLSA attestations
3. **Push a patch fix** and release `v1.9.1` as soon as possible
4. **Notify adopters** via GitHub Discussions if the broken release was promoted (e.g., via `latest` Docker tag)

---

## References

- [Semantic Versioning 2.0](https://semver.org/)
- [CHANGELOG format](https://keepachangelog.com/en/1.1.0/)
- [SLSA Framework](https://slsa.dev/)
- [Sigstore cosign](https://docs.sigstore.dev/cosign/overview/)
- [Maintainer Security Guide](security_guide_maintainer.md)
- [Patch Management SLA](compliance/patch_management_sla.md)
