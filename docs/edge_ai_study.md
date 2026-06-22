# Open BESS Edge: Estudio Técnico de Implementación de Inteligencia Artificial en el Borde
**Evolución e Integración de Modelos Locales, Control Autónomo y Ciberseguridad OT**

---

## 1. Arquitectura de Inteligencia Artificial en Open BESS Edge

Open BESS Edge se ha consolidado como un estándar de pasarela industrial para la gestión de sistemas de almacenamiento de energía en baterías (BESS). Para avanzar hacia la soberanía operativa completa, el sistema migra de un esquema dependiente de la nube a un **esquema de Inteligencia Artificial Híbrida en el Borde (Edge AI)**. 

Esta arquitectura consta de tres pilares fundamentales:
1. **Control de Despacho en Tiempo Real mediante Aprendizaje por Refuerzo Profundo (DRL)**: Modelos optimizados ejecutados en microsegundos vía ONNX Runtime.
2. **Razonamiento Cognitivo Local y Soporte de Operaciones**: Modelos de lenguaje compactos (LLMs locales) ejecutados directamente en la pasarela.
3. **Seguridad y Salud Físico-Digital**: Detección de intrusiones en la red OT (Modbus TCP) mediante algoritmos no supervisados (AI-IDS) y estimación del estado de salud de las celdas (SOH).

```
                            ┌────────────────────────────────────────┐
                            │        Open BESS Edge Gateway          │
                            │        (Nvidia Jetson Orin NX)         │
                            └───────────────────┬────────────────────┘
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
      [Inferencia de Control]        [Procesamiento de Lenguaje]       [Seguridad y Salud]
        • Algoritmo PPO (DRL)          • LLM Local (GLM-5.2 8B)          • AI-IDS (Isolation Forest)
        • Modelos en formato ONNX      • Optimización vía Unsloth        • Modelos Electro-Térmicos (SOH)
        • Latencia < 0.1 ms            • Operación 100% Offline          • Detección de Anomalías OT
```

---

## 2. Modelos de Lenguaje Locales (Local LLMs) en Subestaciones

### El Rol de GLM-5.2 y Unsloth
El despliegue de modelos de lenguaje en el borde de redes industriales presenta dos desafíos críticos: restricciones de memoria (VRAM) y latencia. 

* **GLM-5.2 (Quantized AWQ/GGUF 4-bit)**: Este modelo bilingüe e institucional se destaca en razonamiento lógico y parseo de manuales técnicos. Cuantizado a 4 bits, su tamaño en disco es de ~4.5 GB, requiriendo menos de 6 GB de VRAM para su ejecución, lo que lo hace ideal para hardware de borde.
* **Optimización con Unsloth**: El uso de Unsloth reduce drásticamente el costo computacional de fine-tuning. Permite adaptar el modelo localmente a las bitácoras operacionales históricas de la subestación y guías del CEN, acelerando el entrenamiento hasta en **2.2x** y disminuyendo el uso de memoria en un **70%**.

### Caso de Uso de Operación Autónoma Offline
* **Diagnóstico de Alarmas**: Ante un código de falla Modbus del inversor (ej. Huawei SUN2000), el modelo local traduce el código hexadecimal a instrucciones de reparación paso a paso para el operador en terreno, sin requerir internet.
* **Acciones Correctivas**: El LLM actúa como copiloto de toma de decisiones autónomas, sugiriendo cambios en las filosofías de frenado del modelo de degradación del BESS ante picos térmicos severos detectados en el Atacama.

---

## 3. Despacho Óptimo con Aprendizaje por Refuerzo Profundo (DRL) y ONNX

El núcleo del arbitraje de energía y la participación en servicios complementarios (SS.CC.) utiliza modelos de aprendizaje por refuerzo profundo (PPO) integrados en formato **ONNX**:

* **Entrenamiento Centralizado y Despliegue Distribuido**: Las políticas de control se entrenan con datasets masivos de precios marginales (CMg) reales del Coordinador Eléctrico Nacional (CEN), CAISO o ERCOT. Luego de la convergencia, el modelo de política de la red neuronal se exporta a un archivo `.onnx` ligero (2.1 KB).
* **Latencia Ultra-Baja**: Mediante ONNX Runtime en C++ o Python ligero (`bessai-edge`), la inferencia toma **menos de 0.1 milisegundos (p95)** en el hardware del borde. Esto permite al gateway recalcular el setpoint óptimo de potencia ante fluctuaciones bruscas de frecuencia de red (Primary Frequency Response) en tiempo real.
* **Clamping de Seguridad**: Las acciones sugeridas por la política DRL pasan por un módulo físico-matemático de seguridad en tiempo real (`safety.py`) que restringe instantáneamente setpoints que violen los límites operativos de SOC (Estado de Carga), límites de temperatura de celdas o rampas máximas del inversor.

---

## 4. Detección de Anomalías OT y Ciberseguridad (AI-IDS)

El entorno OT requiere estrictas medidas conforme a la normativa **IEC 62443 SL-2**:

* **AI-IDS basado en Isolation Forest**: La pasarela corre un modelo de aprendizaje no supervisado (`ai_ids.py`) que monitorea los frames Modbus TCP entrantes. El sistema mapea variables clave (ID de registro, valor de escritura, frecuencia de solicitud, IP de origen) para detectar anomalías.
* **Mitigación en Borde**: Si el score de anomalía supera el umbral de confianza (ej. intento de inyección de código o escritura de SOC máximo repetido maliciosamente), el gateway activa un safety block que desconecta el canal de control remoto y cambia el BESS a modo "Local Safe Standby", reportando la alerta vía logs estructurados con Loki y notificaciones SMTP cifradas.

---

## 5. Aprendizaje Federado (Federated Learning) para Estimación de SOH

El cálculo de la degradación química de celdas (modelos de envejecimiento por calendario y ciclado) se beneficia de la red de gateways mediante **Federated Learning**:

```
 ┌────────────────────────────────────────────────────────┐
 │                   Flower Server (Nube)                 │
 └───────────────────────────┬────────────────────────────┘
                             │  Agregación de Pesos (FedAvg)
            ┌────────────────┴────────────────┐
            ▼ (Pesos)                         ▼ (Pesos)
 ┌─────────────────────┐           ┌─────────────────────┐
 │  Gateway Sitio A    │           │  Gateway Sitio B    │
 │  (Datos Locales SOH)│           │  (Datos Locales SOH)│
 └─────────────────────┘           └─────────────────────┘
```

* **Flower Framework**: Open BESS Edge integra clientes Flower (`fl_client.py`) que entrenan modelos locales de predicción de SOH basados en la temperatura de operación y el perfil de descarga dinámico de cada sitio.
* **Privacidad de Datos**: Solo los pesos de las redes neuronales locales se envían al servidor de federación central (`fl_server.py`). Los datos crudos de telemetría operativa y ciclos de batería nunca abandonan la subestación física, garantizando la confidencialidad exigida por los inversionistas del proyecto.

---

## 6. Mapeo de Hardware Recomendado

Para soportar de manera concurrente estas capacidades de IA en Clínica BESS y proyectos de Open BESS Edge, se estructura el siguiente esquema de selección de hardware:

| Hardware | Inferencia DRL (ONNX) | LLM Local (GLM-5.2) | AI-IDS & Telemetría | Costo Est. | Recomendación |
|---|---|---|---|---|---|
| **Nvidia Jetson Orin Nano (8GB)** | Excelente (<0.1ms) | No recomendado (Falta VRAM) | Excelente | US$ 149 | Ideal para PLC Borde básico / Monitoreo |
| **Nvidia Jetson Orin NX (16GB)** | Excelente (<0.1ms) | Funcional (Cuantizado 4-bit) | Excelente | US$ 599 | **Recomendado** (Mejor relación costo-beneficio) |
| **Nvidia Jetson AGX Orin (64GB)**| Excelente (<0.05ms)| Excelente (Múltiples instancias / Fine-tuning) | Excelente | US$ 1,999 | Servidor Principal de Sitio / Hub de Planta |
