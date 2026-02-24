# ♾️ Plan de Inmortalidad — BESSAI Edge Gateway

> **Objetivo:** Que el sistema sobreviva a cualquier persona, empresa, ciclo de mercado o tecnología.  
> **Definición de inmortal:** Un proyecto es inmortal cuando su comunidad lo mantiene vivo aunque sus creadores desaparezcan.

---

## Los 5 Ejes de Inmortalidad

```
1. TÉCNICO     → El código se defiende solo
2. GOBERNANZA  → No depende de Rodrigo
3. COMUNIDAD   → La comunidad lo alimenta
4. FINANCIERO  → Se sostiene sin VC
5. LEGAL       → Nadie lo puede matar con litigio
```

---

## Eje 1 — Técnico: El código se defiende solo

> "Un sistema inmortal detecta degradación antes de morir."

### Ya implementado ✅
- 541 tests + chaos engineering + CI/CD 10 jobs
- ONNX offline → funciona sin internet ni cloud
- Multi-arch (amd64/arm64) → corre en cualquier hardware
- Protocolos estándar abiertos → no vendor lock-in (Modbus/IEEE/IEC)

### Pendiente ⏳
| Acción | Por qué es inmortalidad | Target |
|---|---|---|
| 100% coverage módulos críticos (`safety.py`, `modbus_driver.py`) | Un bug en safety puede matar el proyecto de un día para otro | v2.10.0 |
| BEP-0201 Digital Twin PINN | El sistema predice cuándo va a fallar — no solo reacciona | v3.0.0 |
| Watchdog autónomo + self-healing loop | El gateway se reinicia solo ante fallos detectados | v2.10.0 |
| Test de regresión automático contra hardware simulado | Cada PR valida que no se rompió algo real | v2.9.0 |
| Soporte DNP3 + OPC-UA (BEP-0202) | Más protocolos = más dispositivos = más irreemplazable | v3.0.0 |

---

## Eje 2 — Gobernanza: No depende de Rodrigo

> "Un proyecto que depende de una persona tiene una fecha de muerte."

### Ya implementado ✅
- BESSAI Open Alliance (BOA) Charter con TSC 9 asientos
- Proceso BEP para evolución del estándar — decisiones por consenso
- `GOVERNANCE.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`
- ADRs documentados (razón de cada decisión técnica)

### Pendiente ⏳
| Acción | Por qué es inmortalidad | Target |
|---|---|---|
| **Reclutar 2 co-maintainers** con permisos de merge | Si Rodrigo desaparece, el repo sigue vivo | Marzo 2026 |
| **TSC primera reunión** — 5 miembros fundadores | Gobernanza formal activa, no solo documentada | Abril 2026 |
| CLA (Contributor License Agreement) | Protege la licencia Apache cuando crezcan los contributors | v2.10.0 |
| Automatizar release con GitHub Actions + cosign | Nadie necesita acceso manual para publicar una release | v2.9.0 |
| Documentar "Bus Factor > 3" explícitamente | Que 3+ personas puedan mantener cualquier módulo | Hackathon 2026 |

---

## Eje 3 — Comunidad: La comunidad lo alimenta

> "Un proyecto inmortal crece solo cuando duermes."

### Ya implementado ✅
- Discord BESSAI Community activo
- GitHub Discussions habilitado
- Templates: Issues + PRs + Bug reports
- Bounty program documentado

### Pendiente ⏳
| Acción | Por qué es inmortalidad | Target |
|---|---|---|
| **10 "good first issues" abiertos** en GitHub | La puerta de entrada para contribuidores | Esta semana |
| **Hackathon BESSAI 2026** (Mayo 15-17) | Genera contribuidores orgánicos + perfiles hardware | Mayo 2026 |
| Post LinkedIn + Reddit + LF Energy Discord | 1 post bien hecho puede traer 20 contributors | Esta semana |
| **LF Energy Landscape** PR | Visibilidad global permanente en el mapa OSS energía | Marzo 2026 |
| Mentoring program — Issues etiquetados por nivel | Retención de contributors nuevos | Abril 2026 |
| Vídeo 60 seg: RPi5 + DRL tomando decisiones reales | El demo que hace que la gente haga fork | Cuando BEP-0200 F3 esté listo |

---

## Eje 4 — Financiero: Se sostiene sin VC

> "Un proyecto open-source que necesita inversión para sobrevivir no es inmortal."

### Modelo de sostenibilidad

```
Capa 1 (GRATIS, siempre): Apache 2.0 core — NUNCA se cierra
Capa 2 (COMUNIDAD):        GitHub Sponsors / Open Collective
Capa 3 (SERVICIOS):        Certificación BESSAI hardware + soporte enterprise
Capa 4 (FONDOS OSS):       LF Energy incubation + NLnet + Prototype Fund
Capa 5 (CONTRATOS):        PoC pagados con utilities Chile/LatAm
```

### Pendiente ⏳
| Acción | Por qué es inmortalidad | Target |
|---|---|---|
| **GitHub Sponsors** configurado | Primeras donaciones = proyecto percibido como viable | Esta semana |
| **Open Collective** BESSAI | Transparencia financiera → confianza → más donantes | Marzo 2026 |
| Programa BESSAI-CERTIFIED (hardware) | Fabricantes pagan por certificación → revenue sin inversión | v3.0.0 |
| **LF Energy incubation** application | Funding + visibilidad + credibilidad institucional | Q3 2026 |
| **NLnet Foundation** grant (EU) | Financiamiento sin equity para OSS de infraestructura crítica | Q2 2026 |
| Postular a **CORFO/ANID** (Chile) | Funding local para desarrollo + certificación IEC | Q2 2026 |
| Primer contrato PoC con CEN/utility | El dinero real valida que el sistema funciona | Q2 2026 |

---

## Eje 5 — Legal: Nadie lo puede matar con litigio

> "Apache 2.0 + NOTICE + marca registrada = escudo legal."

### Ya implementado ✅
- Apache 2.0 — permite uso comercial, no obliga a abrir modificaciones
- `NOTICE` con atribuciones completas
- SPDX headers en todos los archivos `src/`
- Sin código propietario de terceros — solo documentación pública de hardware

### Pendiente ⏳
| Acción | Por qué es inmortalidad | Target |
|---|---|---|
| **Registrar marca "BESSAI"** en INAPI Chile | Evita que alguien clone y venda como "BESSAI" | Q2 2026 |
| **CLA Contributor Agreement** (CLA Assistant bot) | Protege de futuras reclamaciones de copyright de contributors | v2.10.0 |
| **Trademark policy** pública | Define quién puede usar el nombre BESSAI y bajo qué condiciones | Q2 2026 |
| Verificar compatibilidad EPL-2.0 (paho-mqtt) | Confirmar con abogado IP que el uso actual es OK | Q1 2026 |
| SBOM automatizado en cada release | Trazabilidad total de dependencias → cumplimiento EU Cyber Resilience Act | v2.9.0 ✅ |

---

## Hoja de ruta consolidada — 90 días para la inmortalidad

```
Semana 1-2 (Feb 24 - Mar 7):
  └─ Branch-Protection + cosign keypair  ← Rodrigo
  └─ 10 good first issues en GitHub      ← Rodrigo
  └─ GitHub Sponsors activo              ← Rodrigo
  └─ Fix C901 + SSL test + tests MILP    ← AI

Semana 3-4 (Mar 8-21):
  └─ LF Energy Landscape PR
  └─ Post LinkedIn/Reddit lanzamiento
  └─ Reclutar primer co-maintainer
  └─ BEP-0200 Fase 3 inicio (datos CEN)

Semana 5-8 (Mar 22 - Abr 18):
  └─ BEP-0201 Digital Twin diseño
  └─ NLnet / CORFO postulación
  └─ TSC primera reunión (5 miembros)
  └─ CLA bot configurado

Semana 9-12 (Abr 19 - May 17):
  └─ HACKATHON BESSAI 2026
  └─ Primer release firmado v2.9.0
  └─ BESSAI-CERTIFIED Tier 1 (2 fabricantes)
  └─ Scorecard objetivo: 9/10
```

---

## Indicadores de que es inmortal

| Indicador | Umbral | Hoy |
|---|---|---|
| Contributors externos con PR merged | ≥ 5 | 0 |
| GitHub Stars | ≥ 500 | 0 |
| Co-maintainers con permisos | ≥ 3 | 1 (Rodrigo) |
| Scorecard | ≥ 9/10 | ~4/10 |
| Hardware BESSAI-CERTIFIED | ≥ 5 fabricantes | 0 |
| Funding mensual sostenible | ≥ $2.000 USD/mes | $0 |
| Adopters productivos | ≥ 3 | 0 |
| LF Energy status | Incubation o Graduated | No aplicado |

**Cuando todos esos indicadores se cumplan: el proyecto sobrevivirá aunque BESS Solutions SpA desaparezca.**
