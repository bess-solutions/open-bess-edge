# ADR-0008: Adopt the BESSAI Enhancement Proposal (BEP) Process for Specification Changes

## Status
✅ Accepted — 2026-02-22

## Context

BESSAI Edge Gateway has matured from a single-organization internal tool into a project with governance documentation, external contributors, and formal specifications (BESSAI-SPEC-001, -002, -003). We need a structured, transparent process for proposing and ratifying changes to:
- Interface specifications (BESSAI-SPEC-*)
- Core governance rules (GOVERNANCE.md)
- Architectural decisions that affect external compatibility

Without such a process:
- Changes can be made unilaterally without community visibility
- Breaking changes to driver interfaces or telemetry schemas could be introduced without warning
- External adopters have no mechanism to propose improvements through a predictable channel
- The project cannot credibly claim multi-stakeholder governance

Alternatives considered:

| Process | Pros | Cons |
|---|---|---|
| **GitHub Issues only** | Simple, already in use | No formal states, no voting, no archive of decisions |
| **GitHub Discussions** | Better for open-ended conversation | Still no structured proposal lifecycle |
| **Python-style PEPs** | Battle-tested, well-known format | Heavyweight for a project of this size |
| **Kubernetes KEPs** | Excellent for complex changes | Very heavyweight (design docs, graduation criteria, etc.) |
| **IETF RFC-style** | Gold standard for internet standards | Overkill; requires formal working group apparatus |
| **BEP (this decision)** | Right-sized; inspired by PEPs/KEPs but simplified | New format; requires bootstrapping |

## Decision

Adopt a lightweight **BESSAI Enhancement Proposal (BEP)** process, documented in `docs/bep/BEP-0001.md` (the meta-BEP).

Key design choices:
- BEPs are Markdown files in `docs/bep/` with a structured header (BEP number, title, author, status, type)
- A GitHub Discussion MUST be opened for each BEP before a PR is submitted (using the `.github/DISCUSSION_TEMPLATE/bep_discussion.yml` template)
- BEP types: `Standards Track` (changes to specs), `Governance` (changes to rules), `Informational` (architecturally significant observations)
- **Quorum**: Acceptance requires approval of 2 Technical Steering Committee (TSC) members, at least 1 of whom MUST be external to BESS Solutions
- **Comment period**: Minimum 14 days for Standards Track and Governance BEPs; 7 days for Informational
- BEP states: `Draft → Under Review → Accepted | Rejected | Withdrawn`

## Consequences

### Positive
- **Transparency**: Every significant change to specs or governance is publicly visible and archived in Git history
- **Inclusivity**: External contributors have a clear, predictable path to propose changes
- **Stability guarantee**: Adopters can rely on the fact that breaking changes require a formal BEP + 14-day notice
- **Auditability**: The BEP archive serves as an immutable rationale record, complementing the ADR archive
- **Standard-body readiness**: Having a BEP process is a prerequisite for organizations like LF Energy and IEEE to take a project's governance seriously

### Negative
- **Process overhead**: Small improvements to non-normative docs now require more consideration about whether a BEP is needed
- **Bootstrapping**: The first TSC must be constituted before any BEP can be formally accepted (chicken-and-egg)

### Resolution of bootstrapping issue
The founding BEPs (BEP-0001 itself) are accepted by BESS Solutions Engineering Team as the founding body, with an explicit commitment to constitute an external TSC within 90 days of the first external adopter reaching Contributor status.

### Neutral
- The BEP number namespace starts at 0001. Numbers 0001-0099 are reserved for meta and governance BEPs. 0100+ for Standards Track.
- ADRs (already in `docs/adr/`) continue to be used for implementation-level decisions that do not affect external interfaces. BEPs are for cross-cutting specification and governance changes.
