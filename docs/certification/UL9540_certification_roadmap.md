# BESSAI Edge Gateway — UL 9540 / UL 9540A Certification Roadmap

**Version:** 1.0  
**Date:** 2026-02-24  
**Status:** In Planning — Target Q1 2027  
**Relevant markets:** United States, Canada, Australia

---

## Overview

UL 9540 (*Standard for Energy Storage Systems and Equipment*) and UL 9540A (*Test Method for Evaluating Thermal Runaway Fire Propagation in Battery Energy Storage Systems*) are the primary safety certifications required for BESS installations in North America. BESSAI Edge Gateway's software plays a critical role in enabling UL 9540 compliance for integrated systems.

---

## certification scope

| Standard | Full name | Relevance to BESSAI |
|---|---|---|
| **UL 9540** | Energy Storage Systems and Equipment | Gateway safety interlocks, BMS communication, SOC monitoring |
| **UL 9540A** | Thermal Runaway Test Method | Gateway must respond correctly to thermal runaway events |
| **NFPA 855** | Standard for the Installation of Stationary Energy Storage Systems | Fire code — gateway must support emergency shutdown signals |
| **IEC 62619** | Safety requirements for secondary lithium cells and batteries | SOC/SOH validation — already partially addressed by SafetyGuard |

---

## Gap Analysis: BESSAI vs UL 9540 Requirements

### Section 4 — General Requirements

| Requirement | UL 9540 §4 | BESSAI Status |
|---|---|---|
| System Level Safety Assessment | §4.1 | ✅ `SafetyGuard` implements SOC/power limits |
| Emergency Shutdown (ESD) | §4.3 | ⚠️ ESD signal reception — needs `write_tag("emergency_stop")` |
| Battery Management System (BMS) interface | §4.5 | ✅ Modbus register mapping in `registry/*.json` |
| AC/DC disconnect | §4.6 | ⚠️ Requires hardware relay; BESSAI can command via Modbus |
| Cybersecurity | §4.10 | ✅ IEC 62443 SL-2 path, TLS 1.2+, rate limiting |

### Section 7 — Software & Control System Requirements

| Requirement | UL 9540 §7 | BESSAI Status | Gap |
|---|---|---|---|
| Software change control | §7.1.3 | ✅ GitHub + SemVer + CHANGELOG | None |
| Fault detection and response | §7.3 | ✅ SafetyGuard + watchdog_loop | None |
| Logging and audit trail | §7.4 | ✅ structlog JSON + OpenTelemetry | None |
| Self-test capability | §7.5 | ⚠️ No explicit self-test on startup | Implement `src/core/self_test.py` |
| Over-current / over-voltage protection | §7.6 | ✅ SafetyGuard with configurable limits | None |
| SOC limits enforcement | §7.7 | ✅ SafetyGuard SOC_MIN / SOC_MAX | None |

---

## Implementation Roadmap

### Phase 1 — Software Compliance Prep (Q3-Q4 2026)

| Task | Module | BEP/ADR |
|---|---|---|
| Implement `emergency_stop` write tag | `src/core/safety.py` | ADR-TBD |
| Add startup self-test routine | `src/core/self_test.py` | ADR-TBD |
| Add thermal runaway alarm handler | `src/core/main.py` | — |
| IEEE 2686 BMS data model partial | `src/agents/bess_rl_env.py` | BEP-0201 |
| Document ESD wiring guide | `docs/tutorials/emergency_shutdown.md` | — |

### Phase 2 — Third-Party Lab Engagement (Q1 2027)

| Step | Action | Partner |
|---|---|---|
| 1 | Obtain BESSAI software component safety assessment | TÜV SÜD / UL Solutions |
| 2 | Engage BESS OEM partner with UL 9540 hardware cert | Huawei / BYD |
| 3 | Integrate BESSAI as the software component in UL 9540 system test | Lab test |
| 4 | Receive UL 9540 software component recognition letter | UL Solutions |

### Phase 3 — Market Documentation (Q2 2027)

- Publish `docs/compliance/ul9540_compliance_guide.md`
- List on [UL Product iQ](https://iq.ulprospector.com) database
- Reference in `BESSAI-CERTIFIED.md` for hardware partners

---

## Estimated Cost

| Item | Estimated Cost |
|---|---|
| TÜV SÜD software safety assessment | ~$8,000-15,000 USD |
| UL Solutions lab fees (1 system test) | ~$20,000-35,000 USD |
| Engineering prep (self-test, ESD handler) | ~40h internal |
| **Total** | **~$30,000-50,000 USD** |

> 💡 Cost can be shared with a hardware OEM partner. Recommend co-funding with Huawei FusionSolar as part of their LUNA2000 BESSAI integration.

---

## Jurisdiction Coverage

| Standard | Country | Required For |
|---|---|---|
| UL 9540 | 🇺🇸 USA | All BESS installations (AHJ discretion) |
| UL 9540 | 🇨🇦 Canada | BESS >20 kWh |
| AS/NZS 4777.2 | 🇦🇺 Australia | Grid-connected BESS + inverter |
| IEC 62619 | 🌍 Global | Battery cell safety |

---

## References

- [UL 9540 Standard (UL Solutions)](https://www.shopulstandards.com/ProductDetail.aspx?productId=UL9540)
- [NFPA 855 (2023 Edition)](https://www.nfpa.org/codes-and-standards/8/5/5)
- [`docs/compliance/iec62443_mapping.md`](../compliance/iec62443_mapping.md)
- [`docs/compliance/ieee_2030_5_compliance.md`](../compliance/ieee_2030_5_compliance.md)
