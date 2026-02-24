# BENCHMARK-005: Edge Device Performance — Raspberry Pi 4 / 5 / Intel NUC

> **Versión**: 1.0.0 · **Fecha**: 2026-02-24  
> **Componente**: `src/` completo · modo normal y `BESSAI_LIGHTWEIGHT=1`  
> **BEP**: —

---

## Objetivo

Validar que BESSAI Edge Gateway corre correctamente en hardware edge de bajo costo y documentar el consumo de recursos para que los integradores elijan el dispositivo adecuado para su instalación.

---

## Hardware evaluado

| Dispositivo | CPU | RAM | Sistema Operativo | Rol típico |
|---|---|---|---|---|
| **Raspberry Pi 4 (4 GB)** | ARM Cortex-A72 @ 1.8 GHz (4 cores) | 4 GB LPDDR4 | Raspberry Pi OS 64-bit (Bookworm) | Instalación residencial / C&I pequeño |
| **Raspberry Pi 5 (8 GB)** | ARM Cortex-A76 @ 2.4 GHz (4 cores) | 8 GB LPDDR4X | Raspberry Pi OS 64-bit (Bookworm) | C&I mediano / múltiples inversores |
| **Intel NUC 12 Pro (i5-1240P)** | Intel Core i5-1240P (12 cores, 16 threads) | 16 GB DDR4 | Ubuntu 22.04 LTS | Edge industrial / VPP node |

---

## Metodología

- **Herramientas**: `psutil` (Python), `htop`, `time` de sistema, ONNX Runtime built-in profiler
- **Escenario**: Gateway ejecutando `main.py` con 1 inversor Modbus simulado, CMg predictor activo, MQTT publisher, telemetría OpenTelemetry
- **Duración de medición**: 10 minutos de operación estable
- **Modo normal**: todos los componentes activos
- **Modo lightweight** (`BESSAI_LIGHTWEIGHT=1`): sin OpenTelemetry traces, AI-IDS solo alertas críticas, sin VPP publisher ni P2P trading

---

## Resultados

### 1. CPU (media durante 10 min de operación)

| Dispositivo | Modo normal (%) | Modo lightweight (%) | Reducción |
|---|---|---|---|
| **Raspberry Pi 4** | 18 % | 9 % | **−50 %** |
| **Raspberry Pi 5** | 11 % | 5 % | **−55 %** |
| **Intel NUC 12** | 4 % | 2 % | **−50 %** |

> Sin carga de inferencia DRL. Con `ONNXArbitrageAgent` activo se añaden picos de ~5 % (RPi 4) / ~3 % (RPi 5) durante inferencia.

### 2. RAM (baseline en reposo + carga operativa)

| Dispositivo | Baseline (MB) | Pico operativo (MB) | Modo lightweight (MB) |
|---|---|---|---|
| **Raspberry Pi 4** | 148 | 312 | 195 |
| **Raspberry Pi 5** | 148 | 310 | 193 |
| **Intel NUC 12** | 152 | 318 | 197 |

> BESSAI Edge Gateway completo cabe cómodamente en **< 350 MB RAM** en todos los dispositivos. El 85 % adicional de RAM libre en RPi 4 puede usarse para caché de datos y buffers MQTT.

### 3. Latencia del ciclo de control (end-to-end)

| Operación | RPi 4 (ms) | RPi 5 (ms) | NUC 12 (ms) |
|---|---|---|---|
| Lectura Modbus (1 registro) | 8.2 | 5.1 | 1.8 |
| Lectura Modbus (batch 20 regs) | 22.4 | 14.8 | 5.2 |
| Inferencia ONNX DRL (CPU) | 2.8 | 1.2 | 0.3 |
| Publicación MQTT (1 mensaje) | 3.1 | 2.0 | 0.8 |
| **Ciclo completo (control loop)** | **~35** | **~23** | **~8** |

> Target de ciclo de control ≤ 100 ms → **todos los dispositivos cumplen con margen**.

### 4. Throughput MQTT

| Dispositivo | Mensajes/s (QoS 0) | Mensajes/s (QoS 1) |
|---|---|---|
| **Raspberry Pi 4** | 1 850 | 820 |
| **Raspberry Pi 5** | 3 200 | 1 400 |
| **Intel NUC 12** | 9 500 | 4 200 |

> Para instalaciones con ≤ 5 inversores publicando cada 1 segundo → RPi 4 es suficiente (5 msg/s << 820 msg/s QoS 1).

### 5. Consumo eléctrico del dispositivo edge

| Dispositivo | Consumo medio (W) | Consumo anual (kWh) | Costo anual (USD @ 0.10/kWh) |
|---|---|---|---|
| **Raspberry Pi 4** | 4.5 W | 39.4 kWh | $ 3.94 |
| **Raspberry Pi 5** | 6.0 W | 52.6 kWh | $ 5.26 |
| **Intel NUC 12** | 18 W | 157.7 kWh | $15.77 |

---

## Recomendaciones por caso de uso

| Caso de uso | Dispositivo recomendado | Motivo |
|---|---|---|
| Sistema residencial (1 inversor, 1 BESS) | **Raspberry Pi 4 (4 GB)** | Bajo costo (~USD 60), bajo consumo (4.5 W), suficiente para ciclos de 1 minuto |
| C&I hasta 5 inversores | **Raspberry Pi 5 (8 GB)** | Mayor throughput, 55 % menos CPU en lightweight, USD 80 |
| VPP node / múltiples inversores / DRL activo | **Intel NUC o industrial PC** | CPU extra para DRL training, RAM para buffers históricos |
| Entorno industrial con DIN rail | **Siemens SIMATIC IPC427E** | Certificación IP65, rango temp -20 a +60 °C (próximo benchmark) |

---

## Cómo habilitar el modo lightweight

```bash
# En tu .env (o exportar como variable de entorno)
BESSAI_LIGHTWEIGHT=1
```

O al arrancar el gateway:

```bash
BESSAI_LIGHTWEIGHT=1 python main.py
```

Ver [`src/core/lightweight_mode.py`](../../src/core/lightweight_mode.py) para los componentes desactivados.

---

## Próximos benchmarks

- [ ] Siemens SIMATIC IPC427E (industrial, certificado IEC 61131)
- [ ] NVIDIA Jetson Nano (DRL con GPU aceleración)
- [ ] Benchmark con 10+ inversores en paralelo (escenario VPP)

---

*Mantenido por BESSAI Engineering Team. Reproducir con: `python scripts/benchmark_edge.py --duration=600`*
