# BESSAI v2.0 — Technical Roadmap
### *Chief Global Architect & AI Research Lead — 2026-02-19*

> [!IMPORTANT]
> Este documento representa la evolución estratégica de BESSAI desde un sistema _single-site_ hacia una **plataforma de energía distribuida de escala planetaria**. Cada área está detallada con stack tecnológico, justificación de decisiones y un plan de implementación por fases.

---

## Resumen Ejecutivo

| Dimensión | v1.0 (hoy) | v2.0 (target) |
|---|---|---|
| **Escala** | 1 sitio, 1 inversor | Miles de sitios, VPP global |
| **IA** | MILP determinístico | DRL + Federated Learning |
| **Seguridad** | Watchdog reactivo | AI-IDS + Data Diodes |
| **Datos** | BigQuery + Pub/Sub | Data Lakehouse (Petabyte-scale) |
| **Impacto** | Eficiencia local | LCA + Huella de carbono evitada |
| **Conectividad** | Cloud-only | Edge-first, off-grid capable |

---

## Arquitectura Global v2.0

```mermaid
graph TB
    subgraph EDGE["🏭 Edge Layer (por Sitio)"]
        direction TB
        MODBUS["Modbus TCP\nInversor Huawei SUN2000"]
        GW["BESSAI Edge Gateway\n(open-bess-edge)"]
        ONNX["ONNX/TFLite\nInference Engine"]
        IDS["AI-IDS\nAnomaly Detector"]
        DD["Data Diode\n(Unidireccional)"]
        MODBUS --> GW
        GW --> ONNX
        GW --> IDS
        GW --> DD
    end

    subgraph REGION["🌐 Regional Orchestrator (por País/Zona)"]
        direction TB
        FED["Federated Orchestrator\n(Kubernetes + Ray)"]
        VPP["VPP Aggregator\nOpenADR 3.0"]
        P2P["P2P Energy Ledger\n(Hyperledger Fabric)"]
        FL["Federated Learning\nServer (Flower/PySyft)"]
        FED --> VPP
        FED --> P2P
        FED --> FL
    end

    subgraph GLOBAL["☁️ Global Platform (Multi-Cloud)"]
        direction TB
        LH["Data Lakehouse\nDelta Lake + Apache Iceberg"]
        DRL["DRL Training Cluster\n(Ray RLlib + PPO/SAC)"]
        EXT["Exogenous Data Feeds\nNASA/NOAA/CAISO/ENTSO-E"]
        LCA["LCA Engine\nOpenLCA + SimaPro API"]
        DASH["Global Dashboard\nGreenfield Grafana + Carbon Metrics"]
        LH --> DRL
        EXT --> LH
        LH --> LCA
        LCA --> DASH
        DRL --> FL
    end

    subgraph MARKET["💹 Market Layer"]
        HVDC["HVDC Virtual\nIntercontinental Balancing"]
        H2["Green Hydrogen\nDispatch Optimizer"]
        MISO["Market Interfaces\nCAISO · ERCOT · ENTSO-E · MISO"]
    end

    DD -->|"OTLP/gRPC (cifrado)"| REGION
    FL -->|"Solo pesos del modelo"| EDGE
    REGION --> GLOBAL
    VPP --> MARKET
    GLOBAL --> MARKET
```

---

## Área 1 — Federated Orchestration (VPP & Multi-Site)

### El problema que resuelve
Un BESSAI Edge aislado es un **tomador de precios**. Una VPP con 10.000 BESSAI agrupados es un **hacedor de mercado** que puede participar en mercados de capacidad, frecuencia y energía.

### Stack Tecnológico

| Componente | Tecnología | Justificación |
|---|---|---|
| Orquestación de flota | **Kubernetes Federation (KubeFed)** | Un control plane que gobierna clusters en múltiples nubes y geografías |
| VPP Aggregation | **OpenADR 3.0** | Estándar de respuesta a la demanda certificado por FERC/ENTSO-E |
| P2P Energy Trading | **Hyperledger Fabric** | Ledger privado/permisionado; throughput > 3.000 tx/seg; no requiere tokens volátiles |
| Intercontinental Dispatch | **HVDC Virtual Scheduling API** + **Green Hydrogen Dispatch** | Desacopla generación solar (Atacama, Sahara) de demanda nocturna europea |
| Comunicación Federada | **gRPC + mTLS** | Latencia < 10ms para señales de control regional |

### Arquitectura P2P Energy Trading

```mermaid
sequenceDiagram
    participant NodeA as BESSAI-CL-001<br/>(Atacama, excedente solar)
    participant Ledger as Hyperledger Fabric<br/>(Smart Contract)
    participant NodeB as BESSAI-ES-042<br/>(Madrid, demanda nocturna)

    NodeA->>Ledger: proposeTransaction(energyQty=500kWh, price=42€/MWh)
    Ledger->>NodeB: broadcastOffer(offer_id, qty, price, carbon_score)
    NodeB->>Ledger: acceptTransaction(offer_id)
    Ledger->>NodeA: executeSettlement() — HTLC atómico
    Ledger->>NodeB: scheduleDispatch(UTC+1 peak window)
    Note over Ledger: Sin operador central.<br/>Liquidación en < 2 seg.
```

### KPIs de Escala

- **Latencia de señal VPP → Edge:** < 500ms (P99)
- **Nodos soportados por cluster regional:** 10.000+
- **Throughput P2P Ledger:** > 3.000 tx/seg

---

## Área 2 — Edge AI & Deep Reinforcement Learning

### El problema que resuelve
MILP es óptimo en condiciones predecibles. Los mercados eléctricos son **no estacionarios** — el DRL aprende comportamientos que MILP nunca podría modelar (anticipación de cascada de precios, gaming de mercado con múltiples jugadores).

### Stack Tecnológico

| Componente | Tecnología | Justificación |
|---|---|---|
| Inferencia en Edge | **ONNX Runtime** + **TensorFlow Lite** | < 50MB, corre en ARM64/x86, sin GPU |
| Entrenamiento DRL | **Ray RLlib** con **PPO** y **SAC** | PPO: estable en prod; SAC: óptimo para espacio de acción continuo (potencia, SoC target) |
| Federated Learning | **Flower (flwr)** o **PySyft** | Solo gradientes/pesos salen del edge — datos jamás salen del sitio |
| Pruebas de simulación | **Gymnasium + pandapower** | Entorno de red eléctrica para pre-entrenar antes de desplegar |
| Model Registry | **MLflow** en GCP Artifact Registry | Versionado, A/B testing entre MILP y DRL, rollback automático |

### Ciclo de Vida del Modelo DRL

```mermaid
graph LR
    SIM["Gymnasium\nSimulator\n(pandapower)"] -->|"Entrenamiento\noffline"| TRAIN["Ray RLlib\nDRL Training\n(PPO/SAC)"]
    TRAIN --> REG["MLflow\nModel Registry"]
    REG -->|"Export ONNX"| EDGE["BESSAI Edge\nONNX Runtime\n(inferencia local)"]
    EDGE -->|"Métricas reales\n(solo agregadas)"| FL["Flower\nFederated Learning"]
    FL -->|"Pesos\nActualizados"| TRAIN
    EDGE -->|"Operación\nOff-Grid"| BESS["BESS\nInversor"]
```

### Modos de Operación del Edge AI

| Modo | Condición | Modelo Activo |
|---|---|---|
| **Cloud-Connected** | Internet disponible | DRL actualizado en tiempo real |
| **Off-Grid / Isla** | Sin internet | ONNX local (último modelo descargado) |
| **Degradado** | Fallo de sensor | Fallback a reglas de safety determinísticas |
| **Black Start** | Catástrofe total | Protocolo autónomo de reactivación secuencial |

---

## Área 3 — Resiliencia Cibernética y Física (Defense-in-Depth)

### Stack de Seguridad

```mermaid
graph TB
    subgraph OT["🔒 OT Network (Air-Gapped)"]
        INV["Inversor / BESS"]
        GW["Edge Gateway"]
        INV -->|"Modbus TCP"| GW
    end

    subgraph DMZ["DMZ"]
        DD["Data Diode\n(Fox DataDiode / Waterfall)"]
        IDS["AI-IDS\n(Isolation Forest\n+ LSTM Autoencoder)"]
        GW -->|"Solo lectura"| DD
        GW --> IDS
    end

    subgraph IT["☁️ IT Network"]
        PUB["GCP Pub/Sub\n(escritura)"]
        SIEM["SIEM\n(Chronicle / Splunk)"]
        DD -->|"Unidireccional físico"| PUB
        IDS -->|"Alertas"| SIEM
    end
```

### AI-IDS — Detection Engine

El detector de intrusiones analiza tráfico Modbus usando dos capas:

1. **Isolation Forest** (sklearn) — detección de outliers en distribución de registros leídos. Un ataque de _reconnaissance_ genera patrones de lectura anómalos.
2. **LSTM Autoencoder** (TFLite, edge-deployed) — modela la secuencia temporal normal de lecturas. Error de reconstrucción > umbral → alerta.

```python
# Pseudo-código del pipeline AI-IDS
class ModbusAnomalyDetector:
    def score(self, modbus_frame: ModbusFrame) -> float:
        features = self._extract(modbus_frame)          # FC, address, count, timing
        iso_score = self.isolation_forest.score(features)
        lstm_error = self.autoencoder.reconstruction_error(features)
        return 0.4 * iso_score + 0.6 * lstm_error       # ensemble

    def alert_if_anomalous(self, score: float) -> None:
        if score > THRESHOLD:
            self.publish_to_siem(severity="CRITICAL")
            self.trigger_network_isolation()             # corte físico del puerto
```

### Protocolo Black Start Autónomo

| Fase | Acción | Tiempo máximo |
|---|---|---|
| **T+0** | Detección de fallo de red / desconexión total | 0s |
| **T+30s** | Edge verifica SoC > 20% → activa modo isla | 30s |
| **T+2min** | Cargas críticas priorizadas por tabla local | 2min |
| **T+10min** | ONNX local asume control de despacho completo | 10min |
| **T+reconexión** | Sincronización de fase con red → re-conexión suave | Variable |

---

## Área 4 — Global Data Lakehouse

### Arquitectura de Datos a Escala Planetaria

```mermaid
graph LR
    subgraph INGEST["Ingestión (Petabyte-scale)"]
        IOT["10K+ BESSAI Edges\n(OTLP/gRPC)"]
        SAT["Fuentes Satelitales\nNASA GISTEMP · NOAA GOES-18"]
        MKT["APIs Mercados\nCAISO · ERCOT · ENTSO-E · MISO"]
    end

    subgraph LAKE["Data Lakehouse (GCS + Multi-Cloud)"]
        STREAM["Apache Kafka\n(Confluent Cloud)\nStreaming Layer"]
        BRONZE["Bronze Zone\nRaw Telemetry\n(Apache Iceberg)"]
        SILVER["Silver Zone\nCleaned + Enriched\n(Delta Lake)"]
        GOLD["Gold Zone\nML Features + KPIs\n(Delta Lake)"]
        STREAM --> BRONZE --> SILVER --> GOLD
    end

    subgraph SERVE["Serving Layer"]
        BQ["BigQuery\n(Analytics)"]
        FT["Feast\n(Feature Store\npara DRL/ML)"]
        DASH["Grafana / Looker\n(Dashboards)"]
    end

    IOT --> STREAM
    SAT --> STREAM
    MKT --> STREAM
    GOLD --> BQ
    GOLD --> FT
    BQ --> DASH
```

### Fuentes Exógenas Integradas

| Fuente | Datos | Frecuencia | Uso |
|---|---|---|---|
| **NASA GISTEMP / POWER** | Irradiancia, temperatura superficial | Horario | Forecast de generación solar |
| **NOAA GOES-18** | Imágenes satelitales de nubes | 15 min | Predicción de sombras en tiempo real |
| **CAISO OASIS** | Precios spot California | 5 min | Señal de despacho para BESS oeste-USA |
| **ERCOT API** | Precios tiempo real Texas | 15 min | Arbitraje de energía |
| **ENTSO-E Transparency** | Precios pan-europeos + mix de generación | 1 hora | Despacho intercontinental |
| **CoinMetrics** | Costos de transacción en Ledger P2P | Continuo | Optimización de fees P2P |

---

## Área 5 — Life Cycle Assessment (LCA) en Tiempo Real

### Módulo LCA Integrado

El Dashboard de BESSAI v2.0 debe hablar el idioma del **CFO y del CPO de Sostenibilidad**, no solo del ingeniero eléctrico.

```mermaid
graph LR
    OPS["Datos Operativos\n(ciclos, SoC, temp)"] --> DEGR["Modelo de\nDegradación\n(Rainflow + SEI)"]
    DEGR --> LCA_ENG["LCA Engine\n(OpenLCA API)"]
    GRID["Mix Energético\nde la Red\n(ENTSO-E/CAISO)"] --> LCA_ENG
    LCA_ENG --> METRICS["Métricas de Salida"]

    subgraph METRICS
        CO2["CO₂ Evitado\n(tCO₂eq/año)"]
        LIFE["Vida Útil\nExtendida\n(ciclos ganados)"]
        COST["Costo Total\nde Propiedad\nTCO Update"]
        CIRCU["Score de\nCircularidad\n(Reciclabilidad)"]
    end
```

### KPIs del Dashboard de Sostenibilidad

| Métrica | Fórmula | Objetivo |
|---|---|---|
| **CO₂ Evitado** | `kWh_BESS × (grid_intensity - BESS_intensity)` | > 500 tCO₂eq/año por sitio |
| **Vida Útil Extendida** | `Δciclos_ahorrados vs operación naive` | +15% ciclos de vida |
| **LCOE del BESS** | `CAPEX + OPEX / (MWh_throughput × lifetime)` | < 80 €/MWh |
| **Score Circularidad** | `% materiales reciclables × recovery_rate` | > 70% |
| **Intensidad de GHG Scope 1+2** | `Emisiones directas + electricidad consumida` | Net-Zero para 2030 |

---

## Fases de Implementación

```mermaid
gantt
    title BESSAI v2.0 — Roadmap de Implementación
    dateFormat  YYYY-QQ
    axisFormat  %Y Q%q

    section Fundamentos (ya completado)
    Edge Gateway Core         :done, 2026-Q1, 1M
    Suite de Tests 45/45      :done, 2026-Q1, 1M

    section Fase 1 — Infraestructura (Q2 2026)
    Terraform GCP             :active, 2026-Q2, 2M
    GitHub Actions CI/CD      :active, 2026-Q2, 1M
    Simulador Modbus          :2026-Q2, 1M

    section Fase 2 — Edge AI (Q3 2026)
    ONNX Inference Engine     :2026-Q3, 2M
    AI-IDS Prototipo          :2026-Q3, 2M
    DRL Training (Ray RLlib)  :2026-Q3, 3M

    section Fase 3 — Federación (Q4 2026)
    KubeFed Multi-Cluster     :2026-Q4, 3M
    VPP Aggregator OpenADR    :2026-Q4, 2M
    Federated Learning (Flower):2026-Q4, 2M

    section Fase 4 — Mercados & Data (Q1 2027)
    Data Lakehouse Global     :2027-Q1, 3M
    P2P Ledger Hyperledger    :2027-Q1, 3M
    Exogenous Data Feeds      :2027-Q1, 2M

    section Fase 5 — LCA & Sostenibilidad (Q2 2027)
    LCA Engine OpenLCA        :2027-Q2, 2M
    Carbon Dashboard          :2027-Q2, 2M
    Intercontinental Dispatch :2027-Q2, 3M
```

---

## Stack Tecnológico Completo v2.0

| Capa | v1.0 | v2.0 |
|---|---|---|
| **Edge Runtime** | Python + asyncio | Python + ONNX Runtime + TFLite |
| **Protocolo Industrial** | Modbus TCP | Modbus TCP + IEC 61850 + DNP3 |
| **Seguridad OT** | Watchdog | Data Diode + AI-IDS + mTLS E2E |
| **Mensajería** | GCP Pub/Sub | Pub/Sub + Apache Kafka (Confluent) |
| **Orquestación** | Docker Compose | Kubernetes + KubeFed + Helm |
| **ML/RL** | *(ninguno)* | Ray RLlib (PPO/SAC) + ONNX |
| **Federated Learning** | *(ninguno)* | Flower (flwr) / PySyft |
| **P2P Trading** | *(ninguno)* | Hyperledger Fabric |
| **VPP** | *(ninguno)* | OpenADR 3.0 + custom aggregator |
| **Data Lakehouse** | BigQuery | BigQuery + Delta Lake + Apache Iceberg |
| **Feature Store** | *(ninguno)* | Feast |
| **Streaming** | Pub/Sub | Pub/Sub + Apache Kafka |
| **IaC** | *(terraform vacío)* | Terraform + Pulumi |
| **Observabilidad** | OpenTelemetry → GCP | OTel + Grafana + Prometheus + Loki |
| **LCA** | *(ninguno)* | OpenLCA API + custom EcoInventory |

---

## Principios Arquitectónicos No Negociables

> [!NOTE]
> Estos principios guían cada decisión de diseño en BESSAI v2.0

1. **Edge-First:** La operación segura nunca debe depender de conectividad cloud.
2. **Privacy-by-Design:** Los datos de telemetría del cliente jamás salen del edge en formato raw — solo gradientes/pesos del modelo (Federated Learning).
3. **Standards over Proprietary:** OpenADR, IEC 61850, OTLP, ONNX — siempre estándares abiertos sobre SDKs propietarios.
4. **Defense-in-Depth:** Cada capa asume que la capa anterior fue comprometida.
5. **Carbon-Aware:** Toda decisión de despacho incluye una dimensión de huella de carbono, no solo económica.
6. **Graceful Degradation:** El sistema opera en modo degradado en cascada: DRL → ONNX offline → MILP → reglas determinísticas → Black Start.
