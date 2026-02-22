# BESSAI Edge Gateway — LF Energy Landscape Submission

**Version:** 1.0  
**Date:** 2026-02-22  
**Status:** Draft — Pending Submission

---

## About This Document

This document is a **draft submission package** for the [LF Energy Landscape](https://landscape.lfenergy.org/) — the Linux Foundation's curated directory of open-source energy projects. Inclusion in the LF Energy Landscape is a significant credibility signal for adoption by utilities, regulators, and enterprise customers.

---

## Project Information

| Field | Value |
|---|---|
| **Project name** | BESSAI Edge Gateway |
| **Repository** | https://github.com/bess-solutions/open-bess-edge |
| **License** | Apache 2.0 |
| **Language(s)** | Python 3.10+ |
| **Category** | Energy Storage / DERM & Optimization |
| **Logo** | `assets/logo.png` (SVG preferred for landscape) |
| **Twitter/X** | (to be created) |
| **LinkedIn** | https://www.linkedin.com/company/bess-solutions |
| **Website** | https://bess-solutions.github.io/open-bess-edge/ |
| **Crunchbase** | (to be created) |

---

## Project Description (150 words max)

> BESSAI Edge Gateway is an open-source industrial gateway for Battery Energy Storage Systems (BESS). It provides a unified driver interface (BESSAI-SPEC-001) compatible with Huawei, SMA, Victron, and Fronius hardware; real-time safety enforcement aligned with IEC 62619 and IEC 62443; ONNX-based offline AI inference for dispatch optimization; and canonical telemetry streaming to GCP Pub/Sub or MQTT brokers (BESSAI-SPEC-003). Designed for deployment on Raspberry Pi 4/5 and Kubernetes edge nodes, it bridges OT hardware and cloud analytics pipelines for microgrids, industrial facilities, and virtual power plants. BESSAI is governed by a multi-stakeholder Technical Steering Committee (TSC) following a transparent Enhancement Proposal (BEP) process, and targets IEC 62443 SL-2 certification in 2026.

---

## Landscape Category Justification

| LF Energy Category | Fit |
|---|---|
| **Energy Storage** | Primary category — BESS management is the core function |
| **DERMS & Optimization** | BESSAI manages dispatch optimization and VPP aggregation |
| **Standards & Interoperability** | BESSAI-SPEC-* documents enable third-party implementations |

**Recommended primary category:** Energy Storage  
**Recommended sub-category:** BESS Management / Edge Gateway

---

## Submission Prerequisites Checklist

| Requirement | Status |
|---|---|
| Open-source license (OSI-approved) | ✅ Apache 2.0 |
| Public repository | ✅ GitHub |
| CI/CD pipeline | ✅ GitHub Actions (378 tests) |
| Security policy | ✅ `SECURITY.md` |
| Governance document | ✅ `GOVERNANCE.md` (TSC + BEP process) |
| Contributing guide | ✅ `CONTRIBUTING.md` |
| Changelog | ✅ `CHANGELOG.md` |
| OpenSSF Passing badge | ✅ Achieved |
| Release published | ✅ v1.7.1 |
| Logo (SVG) | ⚠️ PNG exists — SVG version needed |
| Crunchbase profile | ❌ To be created |

---

## Landscape YAML Entry (Draft)

The LF Energy Landscape uses a YAML-based catalog. Here is the draft entry for `landscape.yml`:

```yaml
- item:
    name: BESSAI Edge Gateway
    homepage_url: https://bess-solutions.github.io/open-bess-edge/
    logo: bessai-edge-gateway.svg
    twitter: https://twitter.com/bess_solutions_cl
    repo_url: https://github.com/bess-solutions/open-bess-edge
    project_org: https://github.com/bess-solutions
    description: >
      Open-source industrial edge gateway for Battery Energy Storage Systems (BESS)
      with IEC 62443 security, AI-augmented dispatch, and formal driver specifications.
    license: Apache-2.0
    category: Energy Storage
    subcategory: BESS Management
    oss: true
    crunchbase: https://www.crunchbase.com/organization/bess-solutions
```

---

## Action Items Before Submission

1. **Create SVG logo** — the landscape requires SVG format
2. **Create Crunchbase profile** for BESS Solutions (free, required by landscape)
3. **Create Twitter/X account** @bess_solutions_cl (recommended)
4. **Fork `lfenergy/lfenergy-landscape`** and open a PR with the YAML entry
5. **Submit to LF Energy Slack** `#landscape` channel for pre-review

---

## LF Energy Membership (Optional Next Step)

LF Energy has no membership fee for open-source projects at the **Associate** level. Associate members receive:
- Listing in official LF Energy communications
- Access to LF Energy working groups (Grid Modernization, DER, Cybersecurity)
- Eligibility to present at Open Source Summit and LF Energy events

**Contact:** info@lfenergy.org  
**Submission form:** https://landscape.lfenergy.org/guide#submit  
**Landscape GitHub:** https://github.com/lfenergy/lfenergy-landscape
