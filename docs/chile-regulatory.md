# Matriz de Cumplimiento Regulatorio (Chile & Internacional)

Esta matriz establece el cruzamiento formal entre las normativas regulatorias nacionales del Sistema Eléctrico Nacional (SEN) de Chile, estándares internacionales de interconexión, y sus implementaciones concretas dentro del ecosistema de software y hardware **Open BESS Edge**.

---

## 1. NTSCS (Norma Técnica de Seguridad y Calidad de Servicio) — CNE Chile

| Cláusula NTSCS | Exigencia Regulatoria | Implementación en Open BESS Edge | Mecanismo de Verificación |
|:---|:---|:---|:---|
| **Anexo Técnico IBR-GFM** | Capacidad de formar red (Grid-Forming) con inyección de corriente reactiva rápida ante caídas de voltaje. | `src/core/controllers/gfm_control.py`: Algoritmo de inercia sintética y lazo de control de voltaje rápido. | Ensayo de inyección de corriente reactiva en simulador hardware-in-the-loop (HIL). |
| **Capítulo 3, Art. 3-8** | Parámetro de estatismo (droop) ajustable para regulación primaria de frecuencia (típicamente 5%). | `config/grid_params.json` (`gfm_droop_gain = 0.05`): Parámetro configurable dinámicamente vía Modbus. | Auditoría de registros Modbus y simulación en `pandapower`. |
| **Anexo Técnico RT** | Soporte de bajo/alto voltaje (LVRT / HVRT) sin desconexión según curvas de despeje de fallas chilenas. | `src/core/protection/ride_through.py`: Perfil de desconexión por tiempo inverso adaptado a las curvas de la NTSCS. | Inyección de tensión AC mediante simulador de red secundario. |
| **Art. 4-12** | Telecontrol y transmisión de telemetría en tiempo real hacia el Coordinador Eléctrico Nacional (CEN). | `mcp_server/server.py`: Herramienta `get_battery_health` que encapsula el Perfil Mínimo de Telemetría (SOC, SOH, P, Q). | Verificación de tramas IEC 60870-5-104 en Wireshark. |

---

## 2. Superintendencia de Electricidad y Combustibles (SEC) — RGR N°06 / 2024

| Cláusula RGR N°06 | Exigencia Regulatoria | Implementación en Open BESS Edge | Mecanismo de Verificación |
|:---|:---|:---|:---|
| **Art. 14.2 — Contención** | Distancia mínima y barreras físicas de contención para evitar la propagación térmica de incendios entre celdas/racks. | `docs/standards/open_bess_edge_standard_v1.md#2.2.1`: Especificación de diseño de separación física a 1.2 metros. | Planos de layout generados por el RAG de ingeniería de detalle. |
| **Art. 14.4 — Ventilación** | Sistema de ventilación y extracción forzada para mantener la concentración de hidrógeno gaseoso por debajo del 1% (LEL). | `src/core/safety/gas_monitoring.py`: Lectura Modbus de sensores de gas H₂ / CO en compartimento de baterías. | Simulación de disparo del extractor forzado ante lectura > 0.8% H₂. |
| **Art. 15.1 — Parada de Emergencia** | Dispositivo mecánico de parada de emergencia (EPO) que desconecte el interruptor principal AC y abra los contactores DC. | `src/core/safety/safety_loop.py`: Función `trigger_hard_emergency()` que manda señal de apertura vía contactos secos. | Prueba funcional física del circuito del lazo de seguridad (E-Stop). |
| **Art. 16.3 — Registro de Fallas** | Trazabilidad completa de alarmas de sobrevoltaje, subvoltaje, sobretemperatura, y desbalances de celdas. | `mcp_server/server.py`: Herramienta `diagnose_faults` que lee el registro histórico de fallas y bitmaps de alarmas. | Inspección de base de datos local de eventos SQLite. |

---

## 3. NCh Elec / RIC (Reglamento de Seguridad de Instalaciones de Consumo de Energía)

| Pliego / Artículo RIC | Exigencia Regulatoria | Implementación en Open BESS Edge | Mecanismo de Verificación |
|:---|:---|:---|:---|
| **RIC N° 04 — Conductores** | Selección de secciones y calibres de conductores según la corriente nominal y límites de caída de tensión (< 3%). | `docs/standards/open_bess_edge_standard_v1.md#3.3`: Mapeo de calibres basados en especificaciones LF Energy BDF. | Cálculo automatizado de caída de tensión en el script de detalle. |
| **RIC N° 05 — Protecciones** | Coordinación de protecciones contra sobrecargas y cortocircuitos mediante relés y fusibles de acción rápida. | `docs/standards/open_bess_edge_standard_v1.md#7.2`: Nodos lógicos de protección IEC 61850 (PTOC, PTOV, PFRC). | Simulación de curvas de corriente vs tiempo en relé virtual. |

---

## 4. IEEE 1547-2018 (Standard for Interconnection of Distributed Energy Resources)

| Sección IEEE 1547 | Exigencia Regulatoria | Implementación en Open BESS Edge | Mecanismo de Verificación |
|:---|:---|:---|:---|
| **Sección 5.4 — Active Power** | Modulación de potencia activa en función de la sobrefrecuencia y subfrecuencia (Droop de frecuencia/vatios). | `src/core/controllers/active_power_derating.py`: Limitación dinámica de potencia activa según frecuencia de red. | Pruebas de inyección de frecuencia externa simulada. |
| **Sección 8.2 — Anti-isla** | Detección de condición de isla no intencional y desconexión obligatoria en un lapso menor a 2.0 segundos. | `src/core/protection/anti_islanding.py`: Detección pasiva por ROCOF y activa por inyección de perturbación. | Ensayo de desconexión con carga acoplada en RTT. |
