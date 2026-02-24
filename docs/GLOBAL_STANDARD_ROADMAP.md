# Open-BESS-Edge — Global Standard Roadmap

> **Versión:** 2.0 · **Fecha:** 2026-02-24 · **Autor:** BESSAI Engineering Team
>
> *Este documento define la hoja de ruta estratégica para evolucionar Open-BESS-Edge de un proyecto open-source funcional a un estándar de facto global en software para gestión de BESS (Battery Energy Storage Systems). Sigue el modelo de madurez de proyectos que se convirtieron en estándares industriales como Linux, Kubernetes, o Modbus.*

---

## Estado Actual vs Objetivo

```
HOY (v2.6.0)                           OBJETIVO (v5.0, 2028)
─────────────────────────────────       ─────────────────────────────────
✅ OSS Apache 2.0                       ✅ + Fundación Neutral (LF Energy)
✅ IEC 62443 SL-2 path                  ✅ + IEC 62933, UL 9540, IEEE 2686
✅ 490 tests, CI/CD robusto             ✅ Conformance test suite interop
✅ Modbus, MQTT, GCP Pub/Sub            ✅ CIM, IEC 61850, OCPP, DNP3
✅ IEEE 2030.5 / SEP 2.0 (BEP-0100)    ✅ IEC 61850, DNP3, ISO 15118
✅ DRL Agent PPO (BEP-0200 Fase 1)      ✅ Trained model +25-35% uplift
✅ BEP process, BESSAI-SPEC-001/004     ✅ Specs formales en ISO/IEC bodies
✅ BESSAI Open Alliance charter (BOA)   ✅ 50+ implementadores en 15+ países
✅ Docs en inglés                       ✅ Docs en EN/ES/ZH/DE
```

---

## Gap Analysis vs Estándares Globales Establecidos

### Dimensión 1 — Gobernanza y Neutralidad

| Gap | Impacto | Referencia |
|-----|---------|-----------|
| Proyecto controlado por un solo vendor (BESS Solutions) | 🔴 Crítico | Linux Foundation: neutidad como requisito para adopción enterprise |
| No hay TSC con representación externa verificada | 🔴 Crítico | Kubernetes SIG model |
| Sin métricas públicas de contribuciones externas | 🟡 Alto | CNCF Graduated criteria |
| Sin advisory board con representación de utilities/OEMs | 🟡 Alto | Eclipse Foundation governance |

**Objetivo:** Donar proyecto a LF Energy (propuesta en `docs/lf_energy_proposal.md`). El TSC debe tener mínimo 50% miembros de organizaciones distintas de BESS Solutions.

### Dimensión 2 — Certificaciones y Estándares Internacionales

| Estándar | Estado Actual | Gap | Prioridad |
|----------|--------------|-----|-----------|
| **IEC 62443 SL-2** | ~95% path | Falta certificación formal + auditor acreditado | 🔴 Q3 2026 |
| **IEC 62933-5-2** | ❌ No cubierto | Grid integration performance para BESS | 🔴 Q4 2026 |
| **IEEE 2030.5 / SEP 2.0** | BEP-0100 Draft | Adapter no implementado aún | 🔴 Q3 2026 |
| **UL 9540 / UL 9540A** | ❌ No cubierto | Safety para BESS en NA (EE.UU./Canadá) | 🟡 Q1 2027 |
| **NFPA 855** | ❌ Sin referencia | Fire code para instalaciones BESS indoor | 🟡 Q1 2027 |
| **IEC 61850** | ❌ Parcial | Comunicación con subestaciones (SAS) | 🟡 Q2 2027 |
| **IEEE 2686 (BMS)** | ❌ No cubierto | Battery Management System data model | 🟠 Q3 2027 |
| **CIM (IEC 61968/61970)** | ❌ Sin soporte | Common Information Model para GIS/grids | 🟠 Q4 2027 |
| **OCPP 2.0.1** | ❌ Sin soporte | Charging Protocol (relevante para V2G) | 🟠 2028 |
| **DNP3 / IEC 60870-5** | ❌ Sin soporte | SCADA utility communications | 🟠 2028 |

### Dimensión 3 — Adopción e Interoperabilidad de Hardware

| Gap | Estado | Acción |
|-----|--------|--------|
| Perfiles hardware limitados (Huawei, SMA, Victron) | 3 perfiles | Expandir a BYD, CATL, LG, Tesla Powerpack |
| Sin driver LUNA2000 Gen 2 | En roadmap | Contactar Huawei FusionSolar API team |
| Sin soporte para inversores de string rápidos (SunSpec) | ❌ | BEP-0101: SunSpec Alliance profile |
| Sin protocolo para V2G (Vehicle-to-Grid) | ❌ | ISO 15118 adapter en roadmap 2028 |

### Dimensión 4 — Comunidad y Ecosistema

| Métrica | Hoy | Target 2028 | Referencia |
|---------|-----|-------------|-----------|
| GitHub stars | ~5 (estimado) | 1,000+ | CNCF Sandbox criteria: 100+ |
| Forks activos | 0 | 25+ | |
| Contribuyentes externos | 0 | 20+ de 10+ org | |
| Issues cerrados por terceros | 0 | 50+/año | |
| PR externos aceptados | 0 | 30+/año | |
| Países con deployments | 1 (Chile) | 15+ | |
| Utilities/OEMs partners | 0 | 5+ | |

### Dimensión 5 — Documentación y Accesibilidad

| Gap | Prioridad |
|-----|-----------|
| Docs solo en inglés | 🟡 ES/ZH/DE en Q1 2027 |
| Sin tutorial para grids europeos (CE marking, ENTSO-E) | 🟡 Q3 2026 |
| Sin quickstart para AWS IoT / Azure IoT Hub | 🟠 Q2 2027 |
| Sin curso certificado / learning path | 🟠 2027 |

---

## Hoja de Ruta por Fases

### Fase 0 — Foundation (HOY → Q2 2026) · `v2.x`
> *Consolidar la base técnica y iniciar reconocimiento comunitario*

```
✅ Completado
├── IEC 62443 SL-2 Phase 1 (SSP, NAD, PMS, PSIRT)
├── OpenSSF Silver/Gold foundations
├── MQTT dual-channel (v2.5.0)
├── Rate Limiting SR 7.1 (v2.3.0)
├── BEP process y BESSAI-SPEC-001/002/003
├── ✅ IEEE 2030.5 adapter BEP-0100 (v2.6.0) → Active
├── ✅ DRL Arbitrage Agent BEP-0200 Fase 1 (v2.6.0): BESSArbitrageEnv + ArbitragePolicy + ONNXArbitrageAgent
├── ✅ BESSAI Open Alliance Charter (docs/governance/CONSORTIUM_CHARTER.md)
├── ✅ BESSAI-SPEC-004 (IEEE P2686 BMS data model, draft)
└── ✅ Hackathon 2026 + IEEE Paper Abstract preparados

📋 Pendiente en esta fase
├── [ ] Publicar en IEEE Energy Conference / RE+ LATAM
├── [ ] Obtener auditor acreditado para IEC 62443 SL-2 formal
├── [ ] Submit a LF Energy Sandbox (propuesta actualizada en docs/)
└── [ ] Primera implementación externa documentada (partner)
```

**KPIs de éxito Fase 0:**
- Auditoría IEC 62443 SL-2 contratada
- LF Energy Sandbox: application submitted
- 1 PR externo merged
- 100 GitHub stars

---

### Fase 1 — Community & Standards (Q3 2026 → Q4 2026) · `v3.x`
> *Construir ecosistema y alineación con estándares internacionales*

```
├── [ ] BEP-0100: IEEE 2030.5 SEP 2.0 adapter (src/interfaces/sep2_adapter.py)
├── [ ] BEP-0101: SunSpec Alliance profile (solar + storage)
├── [ ] IEC 62933-5-2: gap analysis y spec
├── [ ] Perfiles hardware: BYD + CATL + Tesla Powerpack
├── [ ] Primer pilot documentado fuera de Chile (Colombia / España / Alemania)
├── [ ] Hackathon BESSAI — convocatoria pública de contribuciones
├── [ ] Advisory Board: 3 miembros de utilities/OEMs externos
└── [ ] Docs traducidas al español (Latinoamérica) y alemán (DACH)
```

**KPIs de éxito Fase 1:**
- 5 perfiles hardware en `registry/`
- IEC 62933-5-2 gap analysis publicado
- IEE 2030.5 Cat B compliance
- LF Energy Sandbox status: **Active**
- 500 GitHub stars, 5+ forks activos
- 1 utility partner firmado (MOU o piloto)

---

### Fase 2 — Interoperability & Certification (Q1 2027 → Q4 2027) · `v4.x`
> *Certificaciones formales y adopción multi-región*

```
├── [ ] UL 9540 / UL 9540A: compliance checklist + adapter
├── [ ] IEC 61850 driver (subestaciones eléctricas)
├── [ ] IEEE 2686 BMS data model integration
├── [ ] FERC Order 2222 compliance guide (EE.UU.)
├── [ ] ENTSO-E grid codes compliance guide (Europa)
├── [ ] CIM Common Information Model export adapter
├── [ ] Programa BESSAI Certified: versión 2.0 con auditor tercero
├── [ ] Conformance Test Suite autónomo (sin hardware)
├── [ ] Curso online + certificación BESSAI Developer
└── [ ] Submit a ISO/IEC JTC 1/SC 39 (energy efficiency in IT)
```

**KPIs de éxito Fase 2:**
- IEC 62443 SL-2 certificado por auditor acreditado
- 3 implementaciones certificadas por terceros
- Presencia en mercados: Chile + Colombia + España + Alemania + Australia
- LF Energy Graduated (o equivalente)
- 1,000 GitHub stars, 20+ forks

---

### Fase 3 — Global Standard (2028+) · `v5.x`
> *De facto standard en software edge para BESS*

```
├── [ ] DNP3 / IEC 60870-5 adapter (utilities NA/EU)
├── [ ] ISO 15118 V2G protocol support
├── [ ] OCPP 2.0.1 integration (EV charging + BESS)
├── [ ] Multi-site orchestration (BEP-0200: VPP fleet protocol)
├── [ ] Certificación IEEE / IEC formal como referencia implementación
└── [ ] Endorsement de organismos: IEC TC 120, IEEE PES
```

**KPIs de éxito Fase 3:**
- 50+ implementadores en 15+ países documentados
- Referenciado en al menos 1 norma IEC/IEEE como implementación de referencia
- 5,000+ GitHub stars
- Ecosistema de plugins/drivers de terceros (como NPM ecosystem)

---

## Sponsors y Partners Estratégicos

### Tier 1 — Fundaciones (gobernanza neutral)

| Organización | Por qué | Cómo avanzar |
|---|---|---|
| **LF Energy** | Fundación neutral de Linux Foundation para energía limpia; varios proyectos BESS ya dentro | Propuesta ya en `docs/lf_energy_proposal.md` — completar y enviar PR |
| **Eclipse Foundation** | Alternativa a LF; fuerte en industria y IoT | Presentar como candidato Eclipse IoT Working Group |
| **OpenSSF** | Security; ya en camino con Gold badge | Completar Gold, activar SLSA L2, contribuir a OpenSSF |

### Tier 2 — Standards Bodies

| Organización | Oportunidad |
|---|---|
| **IEC TC 120** (Electrical Energy Storage) | Proponer BESSAI-SPEC-001 como Technical Report |
| **IEEE PES** (Power & Energy Society) | Papers en IEEE Transactions on Sustainable Energy |
| **SunSpec Alliance** | Certificación de perfil Modbus/SunSpec |
| **OpenADR Alliance** | Certificación OpenADR 3.0 |

### Tier 3 — Utilities, OEMs y Integradores Clave

| Actor | País | Oportunidad |
|---|---|---|
| Enel Green Power | Chile / Italia | Pilot MW-scale BESS deployment |
| Vattenfall | Alemania / Suecia | BESS grid services (FCR/aFRR) |
| Pacific Gas & Electric (PG&E) | EE.UU. | BESS + FERC 2222 DER aggregation |
| Hydro Québec | Canadá | Grid-scale storage + OpenADR |
| AEMO | Australia | AS/NZS 4777.2 + BESS integration |
| Siemens Energy | Global | Hardware integration OEM agreement |
| BYD / CATL | China | Driver profile + co-development |

---

## Acciones Inmediatas (próximas 90 días)

| Acción | Owner | Deadline | Resultado esperado |
|--------|-------|----------|-------------------|
| Implementar BEP-0100 (IEEE 2030.5 Cat B) | Engineering | Q2 2026 | FERC 2222 ready |
| Enviar propuesta LF Energy | Rodrigo | Mar 2026 | LF Energy Sandbox |
| Publicar en RE+ LATAM (abstract) | Rodrigo | Mar 2026 | Visibilidad regional |
| Contratar auditor IEC 62443 (presupuesto) | Rodrigo | Abr 2026 | SL-2 certificado |
| Crear página `adopters.md` actualizada con 3 casos | Engineering | Mar 2026 | Credibilidad OSS |
| Hackathon público BESSAI (GitHub Discussion) | Rodrigo | Abr 2026 | 5+ contribuyentes |
| Perfil BYD/CATL Modbus registry | Engineering | Q2 2026 | 5 perfiles hardware |
| Traducción README al español (Latinoamérica) | Community | Abr 2026 | Accesibilidad |

---

## Métricas de Éxito por Fase

```
         Fase 0      Fase 1      Fase 2      Fase 3
Stars    100         500         1,000       5,000+
Forks    1           5           20          50+
Países   1           3           8           15+
Partners 0 (MOU)    1           3           10+
Certs    SL-2 path  SL-2 cert   UL 9540     IEC ref impl
Specs    SPEC-001/3  + 62933     + 61850     + ISO submit
```

---

## Lectura Adicional

- [`docs/lf_energy_proposal.md`](lf_energy_proposal.md) — Propuesta LF Energy Sandbox (v1.1)
- [`docs/governance/CONSORTIUM_CHARTER.md`](governance/CONSORTIUM_CHARTER.md) — BESSAI Open Alliance (BOA)
- [`docs/certification/UL9540_certification_roadmap.md`](certification/UL9540_certification_roadmap.md) — Path UL 9540
- [`docs/outreach/IEEE_PAPER_ABSTRACT.md`](outreach/IEEE_PAPER_ABSTRACT.md) — Abstract IEEE PES 2026
- [`docs/outreach/HACKATHON_BESSAI_2026.md`](outreach/HACKATHON_BESSAI_2026.md) — Hackathon Mayo 2026
- [`docs/compliance/ieee_2030_5_compliance.md`](compliance/ieee_2030_5_compliance.md) — Gap IEEE 2030.5
- [`docs/compliance/iec_62443_sl2_certification_path.md`](compliance/iec_62443_sl2_certification_path.md) — Ruta SL-2
- [`docs/specs/BESSAI-SPEC-004.md`](specs/BESSAI-SPEC-004.md) — IEEE P2686 BMS Data Model
- [`docs/bep/BEP-0100.md`](bep/BEP-0100.md) — BEP IEEE 2030.5 Adapter (Active)
- [`docs/bep/BEP-0200.md`](bep/BEP-0200.md) — BEP DRL Arbitrage Agent
- [`docs/bep/BEP-0001.md`](bep/BEP-0001.md) — BEP Process
- [`docs/interoperability/BESSAI-CERTIFIED.md`](interoperability/BESSAI-CERTIFIED.md) — Programa de certificación
- [`GOVERNANCE.md`](../GOVERNANCE.md) — Gobernanza actual
- [`docs/partnership_program.md`](partnership_program.md) — Programa de partners

---

*Este documento es un artefacto vivo. Debe actualizarse con cada versión mayor del proyecto.*
