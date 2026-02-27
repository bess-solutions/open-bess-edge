# 🔍 Análisis de Brechas Normativas — SEC Chile × Open-BESS-Edge

> **Generado:** 2026-02-27 21:06 UTC  
> **Datos SEC:** 41 documentos scraped,
> 34 relevantes a BESS  
> **Repo analizado:** [bess-solutions/open-bess-edge](https://github.com/bess-solutions/open-bess-edge)  
> **Fuente:** [Superintendencia de Electricidad y Combustibles](https://www.sec.cl)  

---

## 📊 Resumen Ejecutivo

| Indicador | Valor |
|---|---|
| Total de brechas identificadas | **11** |
| 🔴 Críticas | **4** |
| 🟡 Medias | **6** |
| 🟢 Bajas | **1** |
| ❌ Sin implementar | 0 |
| 🔄 Planificadas | 7 |
| ⚠️ Parciales | 3 |
| ✅ Implementadas | 1 |

---

## ⚠️ Índice de Brechas por Prioridad

### 🔴 Critical

- [GAP-003] **NTSyCS Cap. 6.1 — Telemetría al Coordinador Eléctrico** — PARTIAL
- [GAP-001] **NTSyCS Cap. 4.2 — Control de Potencia** — PLANNED
- [GAP-002] **NTSyCS Cap. 4.3 — Respuesta de Frecuencia Primaria** — PLANNED
- [GAP-004] **NTSyCS Cap. 6.2 — Protocolos de Comunicación SCADA** — PLANNED

### 🟡 Medium

- [GAP-007] **Decreto N°88/2020 (mod. 2023) — Reglamento PMGD** — PLANNED
- [GAP-006] **Res. Exenta CNE — IEEE 2030.5 para DER conectados a distribución** — PARTIAL
- [GAP-010] **NTCSE — Norma Técnica de Calidad de Servicio Eléctrico** — IMPLEMENTED
- [GAP-011] **NTSyCS Cap. 4.4 — Control de Potencia Reactiva** — PARTIAL
- [GAP-005] **NTSyCS 2024 Anexo 8 — Ciberseguridad** — PLANNED
- [GAP-009] **Res. Exenta SEC 2024 — Ciberseguridad Infraestructura Crítica** — PLANNED

### 🟢 Low

- [GAP-008] **Ley N°21.185 — ERNC y Almacenamiento** — PLANNED

---

## 📋 Detalle de Brechas

### GAP-003 — NTSyCS Cap. 6.1 — Telemetría al Coordinador Eléctrico

**Prioridad:** 🔴 Crítico  
**Estado BESSAI:** ⚠️ Parcial  
**Esfuerzo estimado:** 10–15 días  

**📄 Origen normativo:** [Informe SEC](https://www.sec.cl/home-mundo-energetico/)

#### Descripción de la Brecha

La NTSyCS exige canal de telemetría en tiempo real al Coordinador Eléctrico Nacional (CEN). El pipeline GCP Pub/Sub → CEN está marcado como 🔄 In Progress en BESSAI; no hay canal directo certificado.

#### Estado Actual en open-bess-edge

> CEN telemetry pipeline GCP Pub/Sub → CEN: 🔄 In progress
>
> *Referencia de código:* `docs/compliance/ntscys_compliance.md`

#### Acción Técnica Recomendada

```
Completar CENPublisher en src/core/publishers/cen_publisher.py con endpoint TLS dedicado. Validar formato ICCP/IEC 60870-5-101 o ICCP TCP/IP si el CEN lo admite.
```

#### Fragmento Normativo Relevante

> …a realización de un nuevo proceso de enrolamiento y a mejoras implementadas en el Formulario Web de reporte, conforme al numeral 5.4 del pliego RPTD N°17.  El nuevo plazo de enrolamiento y del segundo envío será informado durante marzo de 2026
, debiendo efectuarse el reporte 
dentro del primer semestre del presente año
.  Informe SEC
Oficina de Partes Virtual
Clientes Sin Luz
Eficiencia Energétic…

---

### GAP-001 — NTSyCS Cap. 4.2 — Control de Potencia

**Prioridad:** 🔴 Crítico  
**Estado BESSAI:** 🔄 Planificado  
**Esfuerzo estimado:** 3–5 días  

**📄 Origen normativo:** [Empresas Autorizadas como Organismos y Laboratorios](https://www.sec.cl/empresas-autorizadas-como-organismos-y-laboratorios/)

#### Descripción de la Brecha

La NTSyCS exige límites de rampa de potencia (MW/min) para unidades BESS conectadas al SEN. BESSAI no aplica ramp rate limiting en el driver Modbus; el setpoint se escribe directo sin gradiente.

#### Estado Actual en open-bess-edge

> Ramp rate limiting: listed as Gap 🔴 High → planned v2.0
>
> *Referencia de código:* `docs/compliance/ntscys_compliance.md#gap-analysis`

#### Acción Técnica Recomendada

```
Implementar RampRateGuard en SafetyGuard que limite δP/δt según parámetro configurable (ej. 10%Pnom/min por defecto). Ver BEP-0202 pending.
```

#### Fragmento Normativo Relevante

> …de Gas. Protocolos PC  12-04-2022  https://www.sec.cl/sitio-web/wp-content/uploads/2024/07/OC-OI-PC-DTSC-PARA-WEB-12Oct2022.xlsx  PROTOCOLOS PC – DTSC  PC N°59  Estanques de almacenamiento para GLP.  PC N°60  Estanques de transporte para GLP.  PC N°73  Estanques de almacenamiento para GLP, usados, de procedencia extranjera.  PC N°74  Estanques de transporte para GLP, usados, de procedencia extranj…

---

### GAP-002 — NTSyCS Cap. 4.3 — Respuesta de Frecuencia Primaria

**Prioridad:** 🔴 Crítico  
**Estado BESSAI:** 🔄 Planificado  
**Esfuerzo estimado:** 5–8 días  

**📄 Origen normativo:** [Studies](https://www.cne.cl/estudios/electricidad/)

#### Descripción de la Brecha

BESSAI carece de implementación de curva droop para Respuesta en Frecuencia Primaria (PFR). La NTSyCS requiere que unidades ≥1MW participen en regulación de frecuencia con tiempo de respuesta <2s.

#### Estado Actual en open-bess-edge

> Primary Frequency Response droop curve: Gap 🟡 → planned v2.0
>
> *Referencia de código:* `docs/compliance/ntscys_compliance.md#gap-analysis`

#### Acción Técnica Recomendada

```
Implementar FrequencyResponseAgent que monitoree f_grid via Modbus FC03 y calcule setpoint de potencia según curva droop db±0.1Hz. Integrar con SafetyGuard para override de DRL agent en emergencia.
```

#### Fragmento Normativo Relevante

> …Descargar  Estudio de definición de exigencias regulatorias necesarias  para establecer niveles de inercia y potencia de cortocircuito  eficientes para el Sistema Eléctrico Nacional  Publicado el: 07/01/2025  Descargar  CNE-23-001_Rev.03_Informe Final Definitivo  Publicado el: 05/08/2024  Descargar  20230726 R1173-22_CNE_PNCP_Informe_Final  Publicado el: 24/06/2024  Descargar  InformeFinalDefinit…

---

### GAP-004 — NTSyCS Cap. 6.2 — Protocolos de Comunicación SCADA

**Prioridad:** 🔴 Crítico  
**Estado BESSAI:** 🔄 Planificado  
**Esfuerzo estimado:** 8–12 días  

**📄 Origen normativo:** [[Base de conocimiento normativo]](https://www.sec.cl)

#### Descripción de la Brecha

IEC 60870-5-104 es el protocolo SCADA estándar exigido por el CEN para supervisión de unidades de generación/almacenamiento. BESSAI soporta Modbus TCP e IEC 61850 parcial, pero NO IEC 60870-5-104.

#### Estado Actual en open-bess-edge

> IEC 60870-5-104 SCADA protocol: Gap 🟡 → planned v2.0
>
> *Referencia de código:* `docs/compliance/ntscys_compliance.md#gap-analysis`

#### Acción Técnica Recomendada

```
Implementar src/drivers/iec104_driver.py usando librería 'lib60870-python' o 'pyiec60870'. Registrar en HardwareRegistry. Añadir tests de integración con simulador SCADA.
```

---

### GAP-007 — Decreto N°88/2020 (mod. 2023) — Reglamento PMGD

**Prioridad:** 🟡 Medio  
**Estado BESSAI:** 🔄 Planificado  
**Esfuerzo estimado:** 4–6 días  

**📄 Origen normativo:** [Informe SEC](https://www.sec.cl/home-mundo-energetico/)

#### Descripción de la Brecha

El Decreto 88 actualizado 2023 establece requisitos técnicos específicos para PMGD con almacenamiento (BESS), incluyendo parámetros de conexión, calidad de energía y reporte mensual a la SEC. BESSAI no documenta cumplimiento específico con D88.

#### Estado Actual en open-bess-edge

> CEN formal certification submission: Gap 🟢 → post-v2.0
>
> *Referencia de código:* `docs/compliance/ntscys_compliance.md#gap-analysis`

#### Acción Técnica Recomendada

```
Crear docs/compliance/decreto88_pmgd_mapping.md con tabla de cumplimiento. Implementar reporte mensual automático en src/scripts/pmgd_monthly_report.py vía SEC e-Declarador API.
```

#### Fragmento Normativo Relevante

> …n Obligatoriedad de Certificación
Pizarra Electrónica SIAC  Charlas SEC
Plataforma de Controversias PMGD  PLIEGOS RIC: Nuevo Reglamento de Instalaciones de Consumo Eléctrico  Seminario Electromovilidad  / 2024  Seminario – Semana de las Energías Renovables / 2024  Jornadas de Capacitación TE-4 y TE-6 / 2025  Charla Reportabilidad de Indicadores SGIIE  Información para la Industria Energética
Anuar…

---

### GAP-006 — Res. Exenta CNE — IEEE 2030.5 para DER conectados a distribución

**Prioridad:** 🟡 Medio  
**Estado BESSAI:** ⚠️ Parcial  
**Esfuerzo estimado:** 6–10 días  

**📄 Origen normativo:** [Generación Distribuída para Autoconsumo](http://www.sec.cl/GDA)

#### Descripción de la Brecha

Para BESS conectados a redes de distribución (BTD o media tensión), la CNE recomienda IEEE 2030.5 como protocolo de comunicación con el operador de distribución. La implementación en BESSAI es parcial.

#### Estado Actual en open-bess-edge

> IEEE 2030.5: listed in supported protocol list but partial
>
> *Referencia de código:* `README.md`

#### Acción Técnica Recomendada

```
Completar src/drivers/ieee2030_5_driver.py. Implementar DERProgram, DERControl y MirrorUsagePoint endpoints. Certificar con OpenADR Alliance si aplica.
```

#### Fragmento Normativo Relevante

> …as normas IEC 63027 o UL 1699B.

Las autorizaciones de inversores que no incorporen sistema AFCI perderán vigencia y no podrán ser utilizadas en nuevas declaraciones.

En caso de utilizar un inversor sin AFCI integrado, recuerde que podrá optar por la modalidad de proyecto especial, siempre que se incorpore una protección AFCI externa autorizada, conforme a los criterios técnicos establecidos en l…

---

### GAP-010 — NTCSE — Norma Técnica de Calidad de Servicio Eléctrico

**Prioridad:** 🟡 Medio  
**Estado BESSAI:** ✅ Implementado  
**Esfuerzo estimado:** 3–5 días  

**📄 Origen normativo:** [Pequeños Medios de Generación Distribuida](http://www.sec.cl/pequenos-medios-de-generacion/)

#### Descripción de la Brecha

La NTCSE de la SEC/CNE establece límites de THD, flicker y desbalance de tensión para unidades conectadas. BESSAI monitorea tensión pero no valida explícitamente estos límites en tiempo real.

#### Estado Actual en open-bess-edge

> Power quality metrics via Prometheus/OTel
>
> *Referencia de código:* `src/core/telemetry.py`

#### Acción Técnica Recomendada

```
Añadir PowerQualityGuard en SafetyGuard con alertas si THD_V > 5% o flicker Pst > 1.0 según NTCSE. Registrar eventos en telemetría.
```

#### Fragmento Normativo Relevante

> …tribuida  ¿Qué es un PMGD?  Es aquel medio de generación que, estando conectado  a una red de media tensión de una empresa concesionaria o a alguna instalación de una empresa que posea líneas de distribución de energía eléctrica y que utilicen bienes nacionales de uso público, aporta excedentes de potencia menores o iguales a 9 MW.  Comienzan oficialmente el año 2005, luego de la  aprobación del r…

---

### GAP-011 — NTSyCS Cap. 4.4 — Control de Potencia Reactiva

**Prioridad:** 🟡 Medio  
**Estado BESSAI:** ⚠️ Parcial  
**Esfuerzo estimado:** 5–7 días  

**📄 Origen normativo:** [Registro Nacional de Instaladoras e Instaladores](https://www.sec.cl/home-area-instalaciones/)

#### Descripción de la Brecha

NTSyCS requiere control de potencia reactiva (Q) en generadores ≥1MW. BESSAI monitorea Q pero el control se delega al firmware del inversor sin integración directa con el agente de despacho.

#### Estado Actual en open-bess-edge

> Reactive power: monitoring only, control via inverter firmware
>
> *Referencia de código:* `docs/compliance/ntscys_compliance.md`

#### Acción Técnica Recomendada

```
Expandir DRL agent o implementar Volt-VAR controller separado que ajuste setpoint Q del inversor vía Modbus FC16 en función de la tensión de punto de acoplamiento común (PCC).
```

#### Fragmento Normativo Relevante

> …Consulta Pública de Protocolos de Productos  Instaladoras e Instaladores Autorizados
Obtener o Renovar Certificado de Instaladora o Instalador  Certificación de Competencias Laborales  Clases de Instaladores o Instaladoras  Certificación de Instalaciones Interiores de Gas  Preguntas Frecuentes  Sanciones
Ingreso Recurso Reposición  Declaración Electrónica de Instalaciones
Sistema e-Declarador : T…

---

### GAP-005 — NTSyCS 2024 Anexo 8 — Ciberseguridad

**Prioridad:** 🟡 Medio  
**Estado BESSAI:** 🔄 Planificado  
**Esfuerzo estimado:** 2–3 días  

**📄 Origen normativo:** [Normas de Uso](https://www.sec.cl/area-ciudadana/normas-de-uso/)

#### Descripción de la Brecha

La NTSyCS 2024 requiere canal TLS dedicado entre el gateway edge y el SCADA del CEN. BESSAI usa TLS en la API dashboard, pero el canal SCADA→CEN aún no implementa TLS mutuo (mTLS).

#### Estado Actual en open-bess-edge

> TLS SCADA channel to CEN: Gap 🟡 → planned v1.5
>
> *Referencia de código:* `docs/compliance/ntscys_compliance.md#gap-analysis`

#### Acción Técnica Recomendada

```
Configurar mTLS en CENPublisher. Gestionar certificados via Let's Encrypt o CA del CEN según contrato de conexión.
```

#### Fragmento Normativo Relevante

> …ormación transmitida a través de aplicaciones proporcionadas por SEC es cifrada mediante el Sistema SSL (Secure Socket Layer), lo que significa que toda información transmitida a través de las aplicaciones no podrá ser leída ni capturada por terceros mientras viaja por la Red.  Para cualquier consulta contactarse a:
 E-mail: contactodau@sec.cl  Descargo de responsabilidades, términos y condiciones…

---

### GAP-009 — Res. Exenta SEC 2024 — Ciberseguridad Infraestructura Crítica

**Prioridad:** 🟡 Medio  
**Estado BESSAI:** 🔄 Planificado  
**Esfuerzo estimado:** 15–25 días  

**📄 Origen normativo:** [[Base de conocimiento normativo]](https://www.sec.cl)

#### Descripción de la Brecha

La SEC emitió en 2024 requisitos de ciberseguridad para operadores de infraestructura eléctrica crítica alineados con IEC 62443 SL-2 (no SL-1). BESSAI implementa SL-1; la certificación SL-2 está en roadmap pero sin fecha comprometida.

#### Estado Actual en open-bess-edge

> IEC 62443 SL-2: certification path documented, not yet achieved
>
> *Referencia de código:* `docs/compliance/iec_62443_sl2_certification_path.md`

#### Acción Técnica Recomendada

```
Seguir docs/compliance/iec_62443_sl2_certification_path.md. Priorizar SR 1.1 (identity mgmt), SR 2.1 (authorization), SR 3.1 (communication integrity) para alcanzar SL-2.
```

---

### GAP-008 — Ley N°21.185 — ERNC y Almacenamiento

**Prioridad:** 🟢 Bajo  
**Estado BESSAI:** 🔄 Planificado  
**Esfuerzo estimado:** 1–2 días  

**📄 Origen normativo:** [Noticias](https://www.cne.cl/es/)

#### Descripción de la Brecha

La Ley 21.185 actualiza el marco regulatorio de ERNC e incorpora el almacenamiento como categoría explícita. Requiere registro en el sistema MFRE de la CNE para acceder a beneficios tarifararios.

#### Estado Actual en open-bess-edge

> CEN formal certification submission: Gap 🟢 → post-v2.0
>
> *Referencia de código:* `docs/compliance/ntscys_compliance.md#gap-analysis`

#### Acción Técnica Recomendada

```
Documentar proceso de registro MFRE en docs/compliance/. No requiere cambios de código, pero sí checklist operacional.
```

#### Fragmento Normativo Relevante

> …cuentas de electricidad, tras los ...  Revisa el Reporte Mensual de febrero 2026  Revisa el Reporte ERNC de febrero 2026  Anterior  Siguiente  Plataformas  Nuestro Quehacer  Mesa técnica de trabajo – PDL Mercado GLP en cilindros  Agenda Inicial para el Segundo Tiempo de la Transición Energética  Res. Reglamentarias de la Ley 21.721  Procedimientos Normativos  Licitaciones de Suministros  Resolució…

---

---

## 🗺️ Mapa de Acción Recomendada

| Gap ID | Brecha | Esfuerzo | Prioridad | Estado BESSAI |
|---|---|---|---|---|
| GAP-003 | NTSyCS Cap. 6.1 — Telemetría al Coordinador Eléctrico | 10–15 días | 🔴 Crítico | ⚠️ Parcial |
| GAP-001 | NTSyCS Cap. 4.2 — Control de Potencia | 3–5 días | 🔴 Crítico | 🔄 Planificado |
| GAP-002 | NTSyCS Cap. 4.3 — Respuesta de Frecuencia Primaria | 5–8 días | 🔴 Crítico | 🔄 Planificado |
| GAP-004 | NTSyCS Cap. 6.2 — Protocolos de Comunicación SCADA | 8–12 días | 🔴 Crítico | 🔄 Planificado |
| GAP-007 | Decreto N°88/2020 (mod. 2023) — Reglamento PMGD | 4–6 días | 🟡 Medio | 🔄 Planificado |
| GAP-006 | Res. Exenta CNE — IEEE 2030.5 para DER conectados a distribución | 6–10 días | 🟡 Medio | ⚠️ Parcial |
| GAP-010 | NTCSE — Norma Técnica de Calidad de Servicio Eléctrico | 3–5 días | 🟡 Medio | ✅ Implementado |
| GAP-011 | NTSyCS Cap. 4.4 — Control de Potencia Reactiva | 5–7 días | 🟡 Medio | ⚠️ Parcial |
| GAP-005 | NTSyCS 2024 Anexo 8 — Ciberseguridad | 2–3 días | 🟡 Medio | 🔄 Planificado |
| GAP-009 | Res. Exenta SEC 2024 — Ciberseguridad Infraestructura Crítica | 15–25 días | 🟡 Medio | 🔄 Planificado |
| GAP-008 | Ley N°21.185 — ERNC y Almacenamiento | 1–2 días | 🟢 Bajo | 🔄 Planificado |

---

## 📚 Marco Normativo de Referencia

| Norma | Organismo | Aplicabilidad BESS |
|---|---|---|
| NTSyCS 2022 | Coordinador Eléctrico Nacional (CEN) | ✅ Obligatoria para ≥1MW |
| Decreto N°88/2020 (mod. 2023) | MEN | ✅ PMGD con almacenamiento |
| Ley N°21.185 (2020) | MEN/CNE | ✅ ERNC y almacenamiento |
| IEC 62443 SL-1/SL-2 | IEC → SEC 2024 | ✅ Ciberseguridad OT |
| IEEE 2030.5 (SEP 2.0) | IEEE → CNE | ⚠️ Distribución DER |
| IEC 60870-5-104 | IEC → CEN | ✅ SCADA obligatorio |
| NTCSE | SEC/CNE | ✅ Calidad de energía |
| Decreto N°125/2017 | MEN | ✅ Sistema eléctrico |

---

## 🤖 Metodología

Este reporte fue generado por **sec-bess-ingestor**, un sistema automático que:

1. **Raspa** sistemáticamente el sitio de la SEC Chile (resoluciones, circulares, normativas)
2. **Analiza** el contenido contra la base de conocimiento normativa de open-bess-edge
3. **Cruza** con el estado de implementación documentado en los archivos de compliance del repo
4. **Publica** automáticamente este reporte como PR al repo cuando se solicita actualización

```bash
# Comandos disponibles
python cli.py scrape      # Raspa SEC Chile
python cli.py analyze     # Analiza brechas
python cli.py report      # Genera este reporte
python cli.py publish     # Publica al repo (requiere GITHUB_TOKEN)
python cli.py update      # Todo en uno
```

> *Generado automáticamente por [sec-bess-ingestor](https://github.com/bess-solutions/open-bess-edge/tree/main/sec-bess-ingestor) — 2026-02-27 21:06 UTC*