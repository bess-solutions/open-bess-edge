# Estándar Open BESS Edge + Ciberseguridad
## Versión 1.0 — Borrador para Revisión
**Proyecto:** BESSAI Pilot — Sistema de Almacenamiento de Energía en Borde  
**Contexto:** Sistema Eléctrico Nacional (SEN) de Chile  
**Estado:** BORRADOR — Validado por entrevista técnica /grill-me (2026-06-16)  
**Clasificación:** Uso Interno BESSAI — Propietario

---

## 1. Alcance y Objetivo

Este documento establece los requisitos técnicos mínimos y aspiracionales para el diseño, implementación y operación segura de un sistema BESS (Battery Energy Storage System) orientado a aplicaciones de **borde (edge)** en el contexto chileno.

**Objetivo principal:** Proveer la base técnica y normativa para integrar sistemas BESS al SEN de Chile con capacidades de telemetría, control autónomo y ciberseguridad desde la fase de arquitectura, conformando al marco regulatorio nacional e internacional.

---

## 2. Arquitectura del Sistema BESS Edge

### 2.1 Componentes Físicos Obligatorios

| Subsistema | Componentes | Tensión / Nivel |
|---|---|---|
| **Almacenamiento** | Racks de baterías + BMS por módulo | Baja Tensión (BT) < 1.000 V AC / < 1.500 V DC |
| **Conversión** | Inversores bidireccionales PCS (Power Conversion System) | BT → MT (con/sin transformador integrado) |
| **Transformación** | Transformador de potencia elevador | BT/MT → MT (typ. 23 kV / 13,2 kV) |
| **Interfaz MT** | Celdas de Media Tensión (MT) | 1 kV – 36 kV (SEN Chile) |
| **Protecciones** | Relés de protección en TODAS las interfaces: BT, AC-link, MT, PCC | Según NCh e IEC |
| **SCADA Planta** | Sistema de control y supervisión local del BESS | Red OT aislada |
| **SCADA SE** | Integración con el sistema SCADA de la subestación | Red OT/IT (vía DMZ) |

### 2.2 Componentes de Infraestructura de Control y Ciberseguridad (Obligatorios)

| Componente | Función | Estándar de Referencia |
|---|---|---|
| **Gateway IoT / Edge Computing** | Preprocesa datos Modbus/IEC 61850 localmente, agrega telemetría, convierte a MQTT/TLS o API REST para nube/SCADA | IEC 62541 (OPC-UA), MQTT v5 |
| **Firewall Industrial + DMZ** | Separa red OT (control) de red IT (empresa/internet). Inspección profunda (DPI) de protocolos industriales | IEC 62443-3-3, NIST SP 800-82 |
| **EMS / DERMS Local** | Orquesta la operación del BESS: despacho, respuesta a consignas CEN, lógica de isla, fallback 24-48h sin conectividad | IEEE 1547.8, estándar propio BESSAI |
| **UPS de Control** | Alimentación ininterrumpida para sistemas de control, comunicaciones y ciberseguridad | IEC 62040, IEEE 446 |

#### 2.2.1 Firewall Industrial + DMZ de Referencia

La segmentación perimetral e interna debe basarse en un diseño stateful y de inspección profunda de paquetes (DPI) para protocolos industriales (Modbus, DNP3, IEC 61850).
* **Hardware de Referencia**: Fortinet FortiGate Rugged series (ej. FortiGate 60F-Rugged o Cisco IE 3400/4000).
* **Configuración de DMZ**: El gateway de edge y el servidor MCP residen en una DMZ dedicada. Las interfaces OT (inversores, BMS) y el SCADA local residen en la zona OT interna protegida.
* **Políticas de Tráfico**: Allowlist estricto donde solo el servidor MCP y el SCADA Planta tienen permiso de iniciar lecturas Modbus/TCP en el puerto 502 hacia el rango IP del BMS/PCS. Toda comunicación externa (hacia la nube o BESSAI Swarm) debe ir cifrada con TLS 1.3.

#### 2.2.2 Sistema de UPS de Control: Especificaciones Técnicas Mínimas

Para garantizar la autonomía de control, adquisición de datos y seguridad local durante pérdidas de suministro AC:
* **Autonomía Mínima**: 2 horas a plena carga de los sistemas de control (EMS, Gateway, Firewall, switches y relés de protección).
* **Tecnología**: On-line doble conversión (IEC 62040-3 Clase VFI).
* **Integración de Comunicaciones**: Tarjeta de red SNMP/Modbus TCP para reportar en tiempo real: estado de carga de batería, tensión de entrada/salida, temperatura de celdas de UPS, y alarmas de falla.
* **Acciones de Fallback**: Si el nivel de batería de la UPS disminuye por debajo del 15%, el EMS local debe iniciar un apagado seguro (graceful shutdown) del gateway e instrumentación OT, dejando registro persistente del estado del BESS en la flash.

### 2.3 Diagrama de Capas del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                    CAPA DE GRID / RED                       │
│   SEN Chile — Subestación MT (23 kV / 13,2 kV)             │
│   IEC 60870-5-104 / DNP3 / IEC 61850 ↔ SCADA SE           │
└──────────────────────────┬──────────────────────────────────┘
                           │  Celda MT + Protecciones
┌──────────────────────────▼──────────────────────────────────┐
│                    CAPA DE INTERFAZ MT                      │
│   Transformador Elevador + Celdas MT + Relés de Protección  │
│   [Zona de Seguridad 3 — Alta Criticidad]                   │
└──────────────────────────┬──────────────────────────────────┘
                           │  AC-link BT
┌──────────────────────────▼──────────────────────────────────┐
│                    CAPA DE CONVERSIÓN                       │
│   Inversores Bidireccionales (PCS)                          │
│   Control: Modbus TCP ↔ SCADA Planta                       │
│   [Zona de Seguridad 2 — Criticidad Media-Alta]             │
└──────────────────────────┬──────────────────────────────────┘
                           │  DC-link
┌──────────────────────────▼──────────────────────────────────┐
│                    CAPA DE ALMACENAMIENTO                   │
│   Racks de Baterías + BMS Modular                           │
│   Telemetría: CAN/RS485/Modbus → Gateway IoT               │
│   [Zona de Seguridad 1 — Alta Criticidad]                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              CAPA DE CONTROL Y CIBERSEGURIDAD               │
│   EMS Local ── Gateway IoT/Edge ── Firewall/DMZ ── UPS     │
│   [Zona de Seguridad 2-3]                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Protocolos de Comunicación

### 3.1 Stack de Protocolos Requeridos

| Protocolo | Capa | Uso Principal | Nivel de Soporte |
|---|---|---|---|
| **Modbus TCP/RTU** | OT — Field Level | Comunicación BMS ↔ PCS ↔ SCADA Planta | **OBLIGATORIO** |
| **IEC 61850 (GOOSE + MMS)** | OT — Station/Process Level | Protecciones digitales y comunicación entre IEDs en SE | **OBLIGATORIO** |
| **DNP3** | OT — SCADA Level | Requerido por algunas utilities chilenas y operadores del CEN | **OBLIGATORIO** |
| **IEC 60870-5-104** | OT/IT — Telecontrol | Telecontrol SCADA de Subestaciones (interfaz CNE/CDEC) | **OBLIGATORIO** |
| **MQTT v5 + TLS 1.3** | IT — Cloud/API Level | Telemetría hacia la nube, BESSAI Swarm, dashboards | **RECOMENDADO** |
| **OPC-UA** | IT/OT — Convergencia | Interoperabilidad multi-vendor, interfaz hacia ERP/GIS | **RECOMENDADO** |
| **IEC 61968/61970 (CIM)** | IT — Enterprise Level | Modelo de datos común para integración con DERMS/EMS de SE | **ASPIRACIONAL** |

### 3.2 Mapeo de Datos Criticos (Signal Mapping)

Los siguientes puntos de datos DEBEN estar mapeados en TODOS los protocolos soportados:

```
BESS_STATUS.SOC          # Estado de Carga (%)
BESS_STATUS.SOH          # Estado de Salud (%)
BESS_POWER.ACTIVE_W      # Potencia Activa (W)
BESS_POWER.REACTIVE_VAR  # Potencia Reactiva (VAR)
BESS_THERMAL.TEMP_MAX    # Temperatura Máxima Celda (°C)
BESS_THERMAL.TEMP_AVG    # Temperatura Promedio (°C)
BESS_ALARMS.ACTIVE       # Alarmas Activas (bitmap)
BESS_ALARMS.FAULT        # Fallas Activas (bitmap)
```

### 3.3 Modelo de Datos LF Energy BDF (Battery Data Format) y Mapeo Modbus

Para garantizar la interoperabilidad con plataformas abiertas de la Linux Foundation Energy (LFE), se adopta la especificación **LF Energy BDF v1.0** para el modelamiento de la batería. A continuación se define la equivalencia de mapeo hacia registros Modbus TCP (Holding Registers, 16 bits por registro, direccionamiento basado en 0):

| Entidad BDF | Variable BDF | Descripción | Registro Modbus | Tipo de Dato | Escala | Unidad |
|---|---|---|---|---|---|---|
| **BatterySystem** | `soc` | Estado de carga del sistema | 3000 | UINT16 | 0.01 | % |
| **BatterySystem** | `soh` | Estado de salud del sistema | 3002 | UINT16 | 0.01 | % |
| **BatterySystem** | `voltage` | Tensión total DC del sistema | 3004 | UINT32 (2 reg) | 0.1 | V |
| **BatterySystem** | `current` | Corriente DC del sistema | 3006 | INT32 (2 reg) | 0.1 | A |
| **BatterySystem** | `active_power` | Potencia activa instantánea | 3008 | INT32 (2 reg) | 1.0 | W |
| **BatterySystem** | `reactive_power` | Potencia reactiva instantánea | 3010 | INT32 (2 reg) | 1.0 | VAR |
| **BatterySystem** | `alarm_bitmap` | Mapa de bits de alarmas del sistema | 3012 | UINT32 (2 reg) | 1 | Bitmask |
| **BatteryModule** | `mod_temp_max` | Temperatura máxima de módulo | 3100 | INT16 | 0.1 | °C |
| **BatteryModule** | `mod_temp_min` | Temperatura mínima de módulo | 3101 | INT16 | 0.1 | °C |
| **BatteryCell** | `cell_volt_max` | Tensión máxima de celda | 3200 | UINT16 | 0.001 | V |
| **BatteryCell** | `cell_volt_min` | Tensión mínima de celda | 3201 | UINT16 | 0.001 | V |

---

## 4. Telemetría — Perfiles de Datos

| Potencia Activa (P) | kW | PCS/Medidor | SCADA Planta + SCADA SE + CEN |
| Potencia Reactiva (Q) | kVAR | PCS/Medidor | SCADA Planta + SCADA SE |
| Tensión por Rack (V) | V DC | BMS por rack | SCADA Planta |
| Corriente por Rack (I) | A | BMS por rack | SCADA Planta |
| Temperatura Máxima Celda | °C | BMS | SCADA Planta + Alarma |
| Estado BMS (modo op.) | enum | BMS | SCADA Planta |
| Eventos de Protección | evento | Relés IED | SCADA SE + Log Auditoria |
| Alarmas Activas | bitmap | BMS + PCS | SCADA Planta + SCADA SE |

### 4.2 Perfil Extendido (Recomendado — Para operación avanzada y degradación)

Frecuencia: **1 dato por ciclo completo** de carga/descarga; **1 vez por día** para resúmenes.

| Variable | Unidad | Fuente | Destino |
|---|---|---|---|
| Ciclos de carga acumulados | nº | BMS | Nube + BESSAI Analytics |
| C-Rate histórico | C | BMS | BESSAI Analytics |
| Capacidad nominal remanente | Ah | BMS | BESSAI Analytics + Informe |
| Histograma Temperatura | distribución | BMS | BESSAI Analytics |
| Eventos de carga/descarga | evento | PCS | Log Auditoria |
| Curva de degradación SOH | % vs ciclos | Analytics | Dashboard + Informe |

---

## 5. Marco Normativo y Regulatorio

### 5.1 Marco Regulatorio Nacional (OBLIGATORIO)

| Norma | Ámbito | Aplicación en BESS Edge |
|---|---|---|
| **NTSCS** (Norma Técnica de Seguridad y Calidad de Servicio) — CNE | Conexión y operación en el SEN | Requisitos funcionales para IBR-GFM, estudios de robustez, respuesta a falla |
| **NCh Elec 4/2003** | Instalaciones eléctricas en BT | Diseño del sistema de baterías e inversores en BT |
| **Reglamento de la LGSE** | Marco legal eléctrico | Autorización de operación, rol del BESS en el SEN |
| **Resoluciones CDEC/CEN** | Despacho y coordinación | Interfaz para servicios complementarios, respuesta en frecuencia |

### 5.2 Estándares Técnicos Internacionales (OBLIGATORIOS)

| Estándar | Organismo | Aplicación en BESS Edge |
|---|---|---|
| **IEEE 1547-2018** | IEEE | Interconexión y operación de Recursos Energéticos Distribuidos (DER/IBR). Grid Forming (GFM), anti-isla, respuesta en voltaje/frecuencia |
| **IEC 61850** | IEC | Comunicación entre equipos en subestaciones digitales. Nodos lógicos para BESS: ZBAT, MMXU, PTOC, PTOV, PFRC |
| **IEC 62933-5-2** | IEC | Seguridad de sistemas de almacenamiento de energía conectados a la red |
| **UL 9540 / UL 9540A** | UL | Pruebas de seguridad de sistemas BESS (propagación de incendio) |

---

## 6. Arquitectura de Ciberseguridad — IEC 62443

### 6.1 Modelo de Madurez Escalonado

```
┌─────────────────────────────────────┐
│    SL-3 — Aspiracional             │ ← Infraestructura crítica nacional
│    Resistencia a APT / atacante     │    BESSAI Fase 3 (2027+)
│    estado-nación                    │
├─────────────────────────────────────┤
│    SL-2 — Objetivo Operacional     │ ← BESS industrial en operación
│    Resistencia a atacante con       │    BESSAI Fase 2 (2026)
│    medios y motivación moderados    │
├─────────────────────────────────────┤
│    SL-1 — Mínimo en Comisionamiento│ ← Durante instalación y pruebas
│    Protección contra accidentes     │    BESSAI Fase 1 (actual)
│    y ataques casuales               │
└─────────────────────────────────────┘
```

### 6.2 Zonas de Seguridad y Conduits (IEC 62443-3-2)

| Zona | Descripción | Activos | SL Objetivo |
|---|---|---|---|
| **Zona 0 — Campo** | Dispositivos físicos de campo | Baterías, BMS, sensores | SL-1 |
| **Zona 1 — Control OT** | Sistema de control BESS | PCS, SCADA Planta, relés | SL-2 |
| **Zona 2 — DMZ Industrial** | Zona desmilitarizada OT/IT | Gateway IoT, Firewall | SL-2 |
| **Zona 3 — SCADA SE** | Control de subestación | RTU, IED de SE, SCADA SE | SL-2/SL-3 |
| **Zona 4 — Red IT/Nube** | Sistemas corporativos | Dashboard, APIs, BESSAI Swarm | SL-1 |

### 6.3 Controles de Ciberseguridad Mínimos por Nivel

#### SL-1 (Comisionamiento)
- [ ] Cambio de contraseñas por defecto en TODOS los dispositivos
- [ ] Segmentación física/lógica de red OT e IT
- [ ] Logs de acceso habilitados y respaldados
- [ ] Actualización de firmware antes de puesta en marcha

#### SL-2 (Operación)
- [ ] Autenticación multifactor (MFA) para acceso remoto
- [ ] Cifrado TLS 1.2+ para TODA comunicación fuera de la red OT
- [ ] Monitorización de integridad de archivos en sistemas críticos
- [ ] Proceso de gestión de parches (máx. 30 días para criticidad alta)
- [ ] Firewall industrial con reglas allowlist (no denylist)
- [ ] IDS/IPS industrial (ej. Claroty, Nozomi, Dragos)
- [ ] Backup y recuperación ante desastre probado (RPO < 4h, RTO < 8h)

#### SL-3 (Aspiracional)
- [ ] Segmentación micro por dispositivo (zero-trust OT)
- [ ] HSM (Hardware Security Module) para claves criptográficas
- [ ] SOC 24/7 con playbooks específicos para BESS
- [ ] Pruebas de penetración anuales por red team certificado
- [ ] Cumplimiento NERC CIP (si aplica por criticidad)

---

## 7. Interfaz Grid — Requisitos de Conexión

### 7.1 Funciones Obligatorias del BESS en el SEN Chile

Según NTSCS + IEEE 1547-2018 para sistemas IBR (Inverter-Based Resources):

| Función | Parámetro | Referencia |
|---|---|---|
| **Control de Voltaje** | Respuesta Q(V): ±10% Vn en < 2s | NTSCS + IEEE 1547 §6.4 |
| **Control de Frecuencia (GFM)** | Droop f: 5% en < 500ms | NTSCS Anexo AT-IBR |
| **Anti-isla** | Detección en < 2s, desconexión en < 2s | IEEE 1547 §8.7 |
| **LVRT / HVRT** | Ride-through según curva NTSCS | NTSCS + IEEE 1547 §6.5 |
| **Potencia de Corto Circuito** | Aporte a falla según Ik" del sistema | Estudio específico de red |
| **Interfaz de Telecontrol** | IEC 60870-5-104 o DNP3 hacia SCADA SE | CDEC/CEN Resolución |

### 7.2 Nodos Lógicos IEC 61850 para BESS

```
ZBAT  — Battery Supervision (SOC, SOH, temperatura, ciclos)
MMXU  — Measurement Unit (V, I, P, Q, f, THD)
PTOC  — Time Overcurrent Protection
PTOV  — Time Overvoltage Protection
PFRC  — Rate of Change of Frequency (ROCOF)
CSWI  — Circuit Switch Control (desconexión)
GAPC  — Generic Automatic Process Control (EMS local)
```

---

## 8. EMS Local — Lógica de Autonomía

El EMS local DEBE garantizar **autonomía de 24-48 horas** sin conectividad a sistemas externos, con las siguientes capacidades mínimas:

### 8.1 Modos de Operación

| Modo | Disparador | Comportamiento |
|---|---|---|
| **Normal (Grid-Connected)** | Conectividad con SCADA SE + CEN | Sigue consignas remotas de P y Q |
| **Autónomo (Grid-Connected)** | Pérdida de comm > 30s | Ejecuta algoritmo local de optimización (SOC target, arbitraje) |
| **Isla (Islanded)** | Pérdida de conexión al SEN | Grid-Forming: mantiene V y f para cargas locales críticas |
| **Emergencia** | SOC < 10% o Temperatura > umbral | Carga mínima, protección de celdas, alerta a todos los canales |
| **Mantenimiento** | Comando manual autorizado | Modo safe, todas las protecciones activas, sin despacho |

### 8.2 Lógica de Decisión (Pseudocódigo)

```python
def ems_decision_loop():
    while True:
        state = read_bess_state()  # SOC, SOH, T, alarms
        grid_status = check_grid_connectivity()
        
        if state.alarms.critical:
            execute_emergency_shutdown()
        elif not grid_status.scada_connected:
            run_autonomous_mode(state)
        elif not grid_status.sen_connected:
            run_island_mode(state)
        else:
            follow_remote_setpoints(state)
        
        log_decision(state, mode, setpoints)
        sleep(DECISION_CYCLE_MS)  # 100ms default
```

---

## 9. Roadmap de Implementación

### Fase 1 — Fundación (Actual: 2025-2026)
- [x] Definición de la arquitectura base (este documento)
- [x] Implementación Modbus TCP en Linares
- [ ] Creación del esquema de datos (schema IEC 61850 básico)
- [ ] Despliegue de Firewall/DMZ en entorno de desarrollo
- [ ] Cumplimiento SL-1 verificado

### Fase 2 — Integración (2026)
- [ ] Integración IEC 61850 con SCADA de SE piloto
- [ ] Implementación DNP3 + IEC 60870-5-104 para telecontrol
- [ ] EMS Local v1.0 con modos Normal y Autónomo
- [ ] Certificación SL-2 auditada externamente
- [ ] Primera prueba LVRT/HVRT según NTSCS

### Fase 3 — Escalamiento (2027+)
- [ ] Integración CIM (IEC 61968/61970) para multi-BESS
- [ ] SOC 24/7 + IDS/IPS industrial
- [ ] Certificación SL-3 para infraestructura crítica
- [ ] Expansión a 3+ subestaciones en el SEN

---

## 10. Glosario

| Término | Definición |
|---|---|
| **BESS** | Battery Energy Storage System — Sistema de Almacenamiento de Energía en Baterías |
| **BMS** | Battery Management System — Sistema de Gestión de Baterías |
| **PCS** | Power Conversion System — Sistema de Conversión de Potencia (inversores) |
| **EMS** | Energy Management System — Sistema de Gestión de Energía |
| **DERMS** | Distributed Energy Resource Management System |
| **IBR** | Inverter-Based Resource — Recurso basado en inversor |
| **GFM** | Grid-Forming — Modo de operación que forma la red (define V y f) |
| **GFL** | Grid-Following — Modo de operación que sigue la red |
| **SEN** | Sistema Eléctrico Nacional (Chile) |
| **NTSCS** | Norma Técnica de Seguridad y Calidad de Servicio (CNE Chile) |
| **IED** | Intelligent Electronic Device — Relé digital o equipo de protección inteligente |
| **RTU** | Remote Terminal Unit — Unidad Terminal Remota |
| **DMZ** | Demilitarized Zone — Zona desmilitarizada de red |
| **SL** | Security Level — Nivel de Seguridad (IEC 62443) |
| **SOC** | State of Charge — Estado de Carga |
| **SOH** | State of Health — Estado de Salud |
| **MT** | Media Tensión (1 kV – 36 kV) |
| **BT** | Baja Tensión (< 1.000 V AC) |

---

*Documento generado mediante entrevista técnica /grill-me con el equipo BESSAI.*  
*Próxima revisión: tras primera validación en campo en subestación piloto.*  
*Contacto técnico: Rodrigo — BESSAI Pilot Project*
