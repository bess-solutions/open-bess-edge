# BESSAI Edge Gateway — Project Governance

> **Status:** Active · **Last updated:** 2026-02-21 · **License:** Apache 2.0

---

## Vision

BESSAI Edge Gateway is an open-source industrial gateway for Battery Energy Storage Systems (BESS), designed to be a reference implementation for safe, AI-augmented energy storage management compliant with Chilean NTSyCS regulation and IEC standards. Our goal is to make enterprise-grade BESS intelligence accessible to the global energy community.

---

## Roles and Responsibilities

### 👑 Maintainers

Maintainers are responsible for the long-term health of the project. They have:
- **Merge authority** on all pull requests
- **Release authority** — can tag and publish new versions
- **Veto power** on architecture decisions
- Responsibility for security disclosures (see [`SECURITY.md`](SECURITY.md))

**Current Maintainers:**

| Name | GitHub | Area |
|---|---|---|
| BESS Solutions Engineering Team | `@bess-solutions` | Core · Infrastructure · AI |

To become a Maintainer, a Contributor must have at least 10 accepted PRs, demonstrate deep understanding of the codebase, and be nominated by an existing Maintainer.

---

### 🤝 Contributors

Anyone who has submitted at least one accepted Pull Request. Contributors may:
- Open Issues and Pull Requests
- Review Pull Requests (non-binding)
- Participate in architectural discussions
- Vote on feature proposals (advisory)

---

### 🌍 Community Members

Anyone who participates in GitHub Discussions, reports issues, or uses the project. Community members may:
- Open Issues
- Participate in Discussions
- Request features

---

## Decision-Making Process

### Routine Changes (1 Maintainer approval)
- Bug fixes
- Documentation improvements
- Dependency updates (non-breaking)
- Test additions

### Significant Changes (2 Maintainer approvals or 1 week comment period)
- New modules or interfaces
- Breaking API changes
- New external dependencies
- Changes to CI/CD pipeline

### Architecture Decisions (ADR required + 2 weeks comment period)
- Changes to core architecture
- New protocol support (e.g., IEC 61850, OCPP)
- Infrastructure changes (new cloud provider, new data store)
- License changes

All architecture decisions must be documented as an **Architecture Decision Record (ADR)** in [`docs/adr/`](docs/adr/).

---

## Release Process

We follow **Semantic Versioning** ([semver.org](https://semver.org/)):

```
MAJOR.MINOR.PATCH
  │      │     └── Bug fixes, security patches, formatting
  │      └──────── New features (backward compatible)
  └─────────────── Breaking changes
```

### Release Steps
1. All CI jobs pass on `main`
2. `CHANGELOG.md` updated with release notes
3. `PROJECT_STATUS.md` version bumped
4. Git tag: `git tag -s vX.Y.Z -m "Release vX.Y.Z"` (signed)
5. GitHub Actions `release.yml` triggers automatically:
   - Builds and pushes Docker image (multi-arch)
   - Generates SBOM (CycloneDX)
   - Creates GitHub Release with changelog excerpt

### Release Cadence
- **Patch releases:** As needed for security/bug fixes
- **Minor releases:** Approximately monthly
- **Major releases:** When breaking changes accumulate, with 60-day deprecation notice

---

## Conflict Resolution

1. **Discussion first** — open a GitHub Discussion or comment on the relevant Issue/PR
2. **Maintainer mediation** — if unresolved after 7 days, a Maintainer will make the final call
3. **Code of Conduct violations** — reported to `conduct@bess-solutions.cl` (see [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md))

---

## Changes to Governance

Changes to this document require:
- A PR with at least **2 Maintainer approvals**
- A **14-day public comment period**
- Announcement in GitHub Discussions
