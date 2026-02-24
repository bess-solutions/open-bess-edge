# BESSAI Open Alliance — Consortium Charter

**Version:** 1.0  
**Date:** 2026-02-24  
**Status:** Draft — Open for Industry Endorsement

---

## 1. Purpose and Mission

The **BESSAI Open Alliance** (BOA) is a vendor-neutral, multi-stakeholder consortium created to accelerate the adoption of open interoperability standards for Battery Energy Storage Systems (BESS) at the grid edge.

> **Mission:** *Establish open-bess-edge as the global reference implementation for BESS edge software, enabling interoperability across hardware vendors, cloud platforms, and regulatory jurisdictions.*

---

## 2. Founding Principles

| Principle | Description |
|---|---|
| **Vendor Neutrality** | No single organization may hold majority governance control |
| **Open Standards** | All technical outputs published under Apache 2.0 or Creative Commons |
| **Meritocracy** | Technical decisions based on evidence, benchmarks, and consensus |
| **Inclusivity** | Participation open to manufacturers, utilities, regulators, and academia |
| **Transparency** | All decisions documented publicly via BEP process |

---

## 3. Membership Tiers

### Tier 1 — Steering Member (Founding)
- **Voting rights:** 2 votes on Technical Steering Committee (TSC)
- **Requirements:** Signed MOU, active deployment of BESSAI or hardware driver contribution
- **Annual commitment:** Technical staff time equivalent to ≥0.5 FTE on open-bess-edge
- **Benefits:** Co-branding rights, priority support, roadmap influence

### Tier 2 — Contributing Member
- **Voting rights:** 1 vote on TSC
- **Requirements:** Merged PR or certified device in `registry/`
- **Annual commitment:** Technical staff time equivalent to ≥0.25 FTE
- **Benefits:** BESSAI Certified badge, listed in `docs/adopters.md`

### Tier 3 — Associate Member
- **Voting rights:** Advisory (no binding vote)
- **Requirements:** Completed BESSAI deployment and public case study
- **Benefits:** Listed in `docs/adopters.md`, access to BOA working groups

### Academic / NGO Members
- **Voting rights:** 1 vote via Academic Representatives pool
- **Requirements:** Published research using BESSAI or open-bess-edge
- **Benefits:** Early access to benchmarks and simulation data

---

## 4. Technical Steering Committee (TSC)

### 4.1 Composition

The TSC is the primary decision-making body for technical direction.

| Role | Seats | Selection |
|---|---|---|
| Maintainer Seats | 2 | Elected by Contributors (most commits, last 12 months) |
| Steering Member Seats | Up to 4 | One per Steering Member organization |
| Community-at-Large | 2 | Elected by all Contributing + Associate members |
| Regulatory Observer | 1 | Nominated by a recognized standards body (IEC/IEEE/CEN) |

**Quorum:** Minimum 5 TSC members for binding votes.  
**Majority rule:** Simple majority for technical decisions; 2/3 supermajority for spec changes or TSC charter amendments.

### 4.2 Current TSC (Founding — BESS Solutions)

| Member | Organization | Role | Since |
|---|---|---|---|
| Rodrigo Anca (TBC) | BESS Solutions | Founding Maintainer | 2026 |
| *[Vacant — Community]* | Open | Community Seat | TBD |
| *[Vacant — Industry]* | Open | Steering Member Seat | TBD |
| *[Vacant — Regulatory Observer]* | IEC TC 120 / IEEE PES | Observer | TBD |

> ⚡ **Immediate action required:** Fill 3 vacant TSC seats by Q3 2026 to reduce vendor concentration risk (current: 100% BESS Solutions — target: <50% by governance threshold).

### 4.3 TSC Responsibilities

- Approve BESSAI Enhancement Proposals (BEPs) affecting BESSAI-SPEC-*
- Manage the BEP process (BEP-0001)
- Approve hardware driver registrations (BESSAI Certified)
- Maintain the project roadmap and release schedule
- Interface with external standards bodies (IEC TC 120, IEEE PES, LF Energy)

---

## 5. Working Groups

| WG | Chair | Scope |
|---|---|---|
| **WG-HAL** | Hardware Abstraction & Drivers | `registry/`, BESSAI-SPEC-001, `src/drivers/` |
| **WG-SECURITY** | Security & Compliance | IEC 62443, OpenSSF, `docs/compliance/` |
| **WG-AI** | ML & DRL Optimization | BEP-0200, BEP-0201, `src/agents/` |
| **WG-INTEROP** | Protocol Interoperability | IEEE 2030.5, IEC 61850, DNP3, OCPP |
| **WG-COMMUNITY** | Adoption & Outreach | Events, tutorials, translations |

---

## 6. Intellectual Property Policy

- All contributions to `open-bess-edge` must be made under the **Apache License 2.0**
- Contributors sign a **Developer Certificate of Origin (DCO)** via `git commit -s`
- No CLA required — DCO is sufficient per Linux Foundation best practices
- BESSAI-SPEC-* documents are published under **Creative Commons BY 4.0**

---

## 7. Conflict of Interest Policy

TSC members must disclose any financial interest in outcomes they vote on. Members with conflicts abstain from related votes. Conflicts are logged in the `governance/` directory.

---

## 8. Relationship with LF Energy

The BESSAI Open Alliance intends to submit `open-bess-edge` to [LF Energy](https://lfenergy.org/) as a **Sandbox project** (application in `docs/lf_energy_proposal.md`).

Upon LF Energy graduation:
- The BOA charter governance is transferred to LF Energy staff-managed neutral body
- TSC composition expands to align with LF Energy's graduated project requirements
- IP ownership transfers to Linux Foundation (Apache 2.0 license unchanged)

---

## 9. Amendment Process

This charter may be amended by a 2/3 supermajority TSC vote, with 30-day public comment period prior to vote.

---

## 10. Founding Members

*Founding membership is open until Q3 2026. Organizations that join as Steering Members before the first TSC election receive founding rights.*

| Organization | Country | Segment | Status |
|---|---|---|---|
| BESS Solutions SpA | Chile | Software/Integration | ✅ Founding |
| *[Open — seek OEM partner]* | Global | Hardware OEM | Recruiting |
| *[Open — seek utility]* | LATAM/EU | Electric Utility | Recruiting |
| *[Open — seek research]* | Global | University/Research | Recruiting |

---

## Contact

To express interest in membership: **ingenieria@bess-solutions.cl**  
Subject: `BOA Membership — [Organization] — [Tier]`

GitHub Discussions: [BESSAI Open Alliance](https://github.com/bess-solutions/open-bess-edge/discussions)
