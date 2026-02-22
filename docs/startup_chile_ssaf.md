# 📋 Postulación Start-Up Chile — SSAF S16
## BESSAI Edge Gateway — BESS Solutions

> **Programa:** Start-Up Chile SSAF (Semilla de Asignación Flexible)
> **Monto solicitado:** $80.000 USD (CLP equivalente)
> **Fecha límite:** Revisar en [startupchile.org](https://startupchile.org) — convocar S16 2026
> **Contacto:** Rodrigo Briones · ingenieria@bess-solutions.cl

---

## 1. Descripción del Proyecto (máx. 500 palabras)

**BESSAI Edge Gateway** es un sistema de software open-source para la gestión inteligente de sistemas de almacenamiento de energía en baterías (BESS). Conecta inversores industriales (Huawei, SMA, Victron, Fronius) vía protocolo Modbus TCP, aplica inteligencia artificial en el borde de la red para detectar anomalías y optimizar el despacho, y publica telemetría a la nube (GCP, MQTT).

**Problema que resuelve:** Chile tiene $2 GW de BESS en construcción para el período 2026-2030. Los integradores actuales usan soluciones propietarias con costos de $50.000-$200.000 USD por instalación y sin acceso a datos en tiempo real. Esto genera gestión subóptima que consume entre 8-15% del ciclo útil de las baterías.

**Propuesta de valor:** BESSAI reduce el costo de integración a < $5.000 USD (80-90% menos), cumple la Norma Técnica de Seguridad y Calidad de Servicio (NTSyCS) del CEN Chile, y aplica IA para maximizar la vida útil de los activos.

**Estado actual (Feb 2026):**
- Software funcional con hardware real (49 commits, 378 tests, CI verde)
- Soporte para 4 fabricantes de inversores
- Compliance IEC 62443 SL-1, OpenSSF Passing badge
- Infraestructura cloud provisionada (GCP Pub/Sub, Terraform)
- Kubernetes manifests para deployment en minas y parques solares
- Repositorio público: github.com/bess-solutions/open-bess-edge

---

## 2. Problema y Oportunidad de Mercado

### El problema específico
La NTSyCS 2025 del CEN Chile exige que todos los activos BESS mayores a 1 MW reporten telemetría en tiempo real. Los operadores tienen < 12 meses para cumplir o arriesgan multas y desconexión de la red.

### Mercado objetivo
- **Chile:** ~400 proyectos BESS en desarrollo, TAM $3.2M USD/año
- **LatAm:** ~3.000 proyectos, TAM $24M USD/año
- **Entrada:** 20 proyectos en Chile en 2026, revenue target $80k USD

### Solución técnica diferenciada
BESSAI es el único sistema en LatAm que combina:
1. Multi-hardware open-source (sin lock-in)
2. Edge AI (AI-IDS + ONNX) sin necesidad de conectividad constante
3. Compliance NTSyCS + IEC 62443 documentado

---

## 3. Modelo de Negocio

| Línea | Precio | Margen |
|---|---|---|
| SaaS Managed | $299/sitio/mes | ~85% |
| Enterprise Support | $2.500/mes | ~70% |
| Consulting / Integración | $5.000-$15.000/proyecto | ~60% |
| Training técnico | $500/persona | ~90% |

**Proyección año 1:** $80k USD (10 clientes SaaS + 3 proyectos consulting)
**Break-even:** Mes 8 con 3 empleados

---

## 4. Equipo Fundador

| Persona | Rol | Experiencia |
|---|---|---|
| Rodrigo Briones | CEO / CTO | Ingeniería Civil Eléctrica, 5 años en proyectos IIoT, Python, GCP, Modbus |

**Busca:** Co-fundador BD con red en el sector energético y minero

---

## 5. Plan de Uso de los Fondos ($80k USD)

| Categoría | USD | Plazo |
|---|---|---|
| Co-founder / primer hire comercial | $32.000 | Mes 1-6 |
| Certificación IEC 62443 SL-2 | $15.000 | Mes 3 |
| Marketing y comunidad OSS (eventos, Reddit, LinkedIn) | $12.000 | Mes 1-12 |
| Infraestructura GCP + servidores | $8.000 | Mes 1-12 |
| Legal (contratos SLA enterprise, registro SII) | $8.000 | Mes 1-3 |
| Viajes a clientes / demos presenciales | $5.000 | Mes 4-12 |

---

## 6. Métricas de Éxito (KPIs — 12 meses)

| KPI | Meta |
|---|---|
| Clientes SaaS activos | 10 |
| Revenue mensual recurrente (MRR) | $3k USD |
| Proyectos consulting cerrados | 3 |
| Stars GitHub | 500+ |
| Contribuidores externos | 10+ |
| Países con adopción | 3 (Chile, Brasil, Australia) |

---

## 7. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Competencia de Siemens / ABB | Baja | Open-source y precio inaccesible para ellos |
| Lentitud regulatoria CEN | Media | NTSyCS ya obliga, no hay opción |
| Capacidad técnica | Baja | 49 commits + CI verde + docs completos |
| Comercialización sin equipo BD | Alta | Usar fondos SSAF para primer hire comercial |

---

## 8. Tracción y Validación

- **MVP funcional verificado** con hardware real Huawei SUN2000
- **Open-source**: código público, auditado y con gobernanza OSS
- **Comunidad técnica:** repositorio indexado en GitHub con documentación completa
- **Compliance documentado:** NTSyCS y IEC 62443 mapeados (ventaja competitiva)

---

## 9. Próximos Pasos Inmediatos

1. ✅ Completar repositorio GitHub (hecho — v1.7.1)
2. 🔄 Contactar 3 operadores solares en Atacama para pilot (Abr 2026)
3. 🔄 Aplicar a SSAF S16 (este formulario)
4. ⬜ Certificación IEC 62443 SL-2 (Jun 2026 con fondos)
5. ⬜ Lanzar SaaS managed en GCP (Jul 2026)

---

> **Repositorio:** https://github.com/bess-solutions/open-bess-edge
> **Demo live:** `docker compose --profile simulator up` (sin hardware)
> **Contacto:** ingenieria@bess-solutions.cl
