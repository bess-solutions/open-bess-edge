# 🚀 BESSAI Edge Gateway
## Pitch Ejecutivo — Start-Up Chile / Inversores
> v1.7.1 · Febrero 2026 · BESS Solutions · ingenieria@bess-solutions.cl

---

## El Problema

**Chile tiene 2 GW de almacenamiento en baterías en construcción** (MINENERGIA 2026-2030), pero el 90% de los integradores opera con soluciones propietarias cerradas: costos de $50k-$200k USD por instalación, lock-in de proveedor, y cero visibilidad de datos en tiempo real.

Resultado: parques solares en el desierto de Atacama con baterías mal gestionadas pierden entre **8-15% de su ciclo útil** por estrategias de carga subóptimas. En un activo de $5M USD, eso equivale a **$400-750k perdidos en vida útil**.

---

## La Solución

**BESSAI Edge Gateway** — software open-source para gestión inteligente de BESS:

```
Adquiere datos Modbus TCP → Valida seguridad → IA en el edge → Publica a la nube
```

- **Multi-hardware:** Huawei SUN2000, SMA Sunny Tripower, Victron, Fronius
- **Edge AI:** AI-IDS (anomalías), ONNX dispatcher (despacho óptimo)
- **Cloud-native:** GCP Pub/Sub, MQTT, OpenTelemetry
- **Open-source:** Apache 2.0, 378 tests, CI verde, OpenSSF Passing

---

## Tracción Técnica

| Métrica | Valor |
|---|---|
| Commits | 49 (en 3 días) |
| Tests | 378/378 ✅ |
| CI jobs | 9 (ruff · mypy · pytest · bandit · terraform · helm · docker · trivy · push) |
| Hardware soportado | 4 fabricantes (25-28 registros Modbus cada uno) |
| Países target | Chile, Brasil, Australia, EU |
| Compliance | IEC 62443 SL-1 · NTSyCS CEN Chile · OpenSSF Passing |
| Deployment | Docker · K3s · Raspberry Pi 4/5 · Kubernetes |

---

## Modelo de Negocio

```
[OPEN CORE] Gratis, siempre
      │
      ├── [MANAGED SAAS]     $299/sitio/mes — dashboard GCP, updates automáticos
      ├── [SOPORTE ENTERPRISE] $2.5k/mes — SLA 24/7, onboarding dedicado
      ├── [CONSULTING]       $5-15k/proyecto — integración custom (minas, parques solares)
      └── [GRANTS]           CORFO Green Tech · EU Horizon · FONDECYT
```

**Break-even:** 12 clientes SaaS ó 3 proyectos consulting.

---

## Mercado Total Disponible

| Segmento | Tamaño Chile | Tamaño LatAm |
|---|---|---|
| BESS instalados o en construcción | 2 GW / ~400 proyectos | 15 GW / ~3.000 proyectos |
| Precio promedio integración | $8k USD | $8k USD |
| **TAM** | **$3.2M USD/año** | **$24M USD/año** |
| **SAM** (primeros 2 años) | $320k USD | — |
| **SOM** (año 1) | $80k USD | — |

---

## Equipo

| Nombre | Rol | Background |
|---|---|---|
| Rodrigo Briones | CEO / CTO | Ing. Civil · IIoT · Python · GCP |

**Buscamos:** Co-founder BD/ventas · Advisors del sector energético

---

## Hitos Completados (Feb 2026)

- ✅ MVP funcional con hardware real (Huawei SUN2000)
- ✅ CI/CD completo: 9 jobs, Docker multi-arch, Helm chart
- ✅ Cloud infrastructure (GCP Pub/Sub, Terraform)
- ✅ Gobernanza OSS (LICENSE, SECURITY, CONTRIBUTING, ADRs)
- ✅ IEC 62443 SL-1 mapeado
- ✅ Kubernetes manifests (K3s, GKE, EKS)

---

## Hitos Próximos (Q2 2026)

| Hito | ETA | $$ Requerido |
|---|---|---|
| Pilot con cliente real (solar Atacama) | Abr 2026 | 0 (OSS) |
| 1er cliente pagante SaaS | May 2026 | $0 |
| Certificación IEC 62443 SL-2 | Jun 2026 | $15k USD |
| 10 clientes enterprise | Dic 2026 | $200k (ops+ventas) |

---

## Funding Solicitado

**$150k USD seed** — Start-Up Chile SSAF (hasta $80k USD) + Angel/VC

| Destino | % | Monto |
|---|---|---|
| Certificación IEC 62443 SL-2 | 10% | $15k |
| Marketing y comunidad OSS | 15% | $22.5k |
| Co-founder / primer hire BD | 40% | $60k |
| Infraestructura GCP + ops | 20% | $30k |
| Legal (patentes, contratos SLA) | 15% | $22.5k |

---

## Por Qué Ahora

1. **La ventana es ahora:** Chile tiene el pipeline de inversión BESS más grande de LatAm activo en 2026.
2. **OSS como moat:** Comunidad open-source = distribución gratuita + credibilidad técnica frente a proveedores cerrados.
3. **AI Edge es escaso:** Solo BESSAI ofrece AI-IDS + ONNX + despacho óptimo en el edge para este hardware.
4. **Normativa hace obligatorio:** NTSyCS 2025 exige telemetría en tiempo real — somos el camino más rápido al compliance.

---

> **Contacto:** Rodrigo Briones · ingenieria@bess-solutions.cl · github.com/bess-solutions/open-bess-edge
