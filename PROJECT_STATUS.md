# 📊 BESSAI Edge Gateway — Estado del Proyecto

> **Versión Canónica:** v2.0.0-industrial-cen-cfydr · **Licencia:** Apache 2.0  
> **Estándar:** NTSyCS (CEN Chile) / IEC 62443 SL-2 / IEEE 2030.5  
> **Estado CI/CD:** [![CI](https://github.com/bess-solutions/open-bess-edge/actions/workflows/ci.yml/badge.svg)](https://github.com/bess-solutions/open-bess-edge/actions/workflows/ci.yml)

---

## 🎯 Alcance del Proyecto

**BESSAI Edge Gateway** es una pasarela industrial de borde de código abierto diseñada para operar en hardware local (Industrial PC, Raspberry Pi 4/5, servidores de subestación) junto al inversor de sistemas de almacenamiento de energía en baterías (BESS).

Provee adquisición de telemetría de alta fidelidad vía **Modbus TCP**, evaluación continua de envolventes de seguridad física y ejecución de lazos de control dinámicos de red en estricto cumplimiento con la normativa técnica del Sistema Eléctrico Nacional (SEN) de Chile y estándares internacionales.

---

## 🏗️ Núcleo Operativo Implementado (`src/`)

| Subsistema | Módulo | Responsabilidad Técnica |
| :--- | :--- | :--- |
| **Control FFR (Inercia/Droop)** | `src.controllers.ffr_droop_controller` | Respuesta rápida de frecuencia sub-500ms con estatismo configurable ($s=3\%$) y banda muerta simétrica de $\pm 30\text{ mHz}$ calibrada según el Estudio CEN CFyDR 2026. |
| **Control Volt/VAR** | `src.controllers.volt_var_controller` | Inyección/absorción de potencia reactiva para soporte dinámico de tensión en barras de transmisión/distribución. |
| **Driver Modbus TCP** | `src.drivers.modbus_client` | Cliente Modbus industrial asíncrono con decodificación IEEE 754 float32/uint16, reconexión exponencial y polling determinístico. |
| **Envolvente de Seguridad** | `src.safety.safety_envelope_evaluator` | Verificación de límites seguros (sub/sobre-tensión, sobre-frecuencia, deriva térmica y límites de SoC/SoH) con disparo de protecciones preventivas. |
| **Nodo Orquestador** | `src.edge_node` | Lazo principal de control determinístico y despacho local. |

---

## 🧪 Matriz de Validación y Cobertura

* **Pruebas Unitarias y de Cumplimiento:** **18 / 18 aprobadas** (100% pass rate) en 0.81s.
* **Cobertura de Código (`pytest-cov`):** **82%** medido sobre `src/`.
* **Seguridad Estática (SAST - Bandit):** **0 vulnerabilidades**.
* **Auditoría de Dependencias (pip-audit):** **0 CVEs detectados**.
* **Estilo y Calidad de Código (Ruff):** **0 errores, 0 advertencias**.

---

## ⚙️ Workflows Canónicos de Integración Continua (`.github/workflows/`)

1. **`ci.yml`**: Matriz de pruebas automatizadas en Python 3.10, 3.11 y 3.12, linting con Ruff, escaneo de seguridad con Bandit y pip-audit, y validación de compilación de imagen Docker.
2. **`codeql.yml`**: Análisis estático de código oficial de GitHub (CodeQL) para Python.
3. **`docs.yml`**: Compilación estricta y despliegue automatizado de la documentación en GitHub Pages vía MkDocs Material.
4. **`docker-multiarch.yml`**: Compilación y publicación de imágenes OCI multi-arquitectura (`linux/amd64`, `linux/arm64`) en GitHub Container Registry (ghcr.io).
5. **`release.yml`**: Generación automática de releases oficiales con catálogo SBOM (SPDX/CycloneDX) ante nuevos tags de versión.

---

## 📋 Registro de Hardware Soportado (`registry/`)

Perfiles Modbus validados para inversores y controladores de almacenamiento:
* Huawei SUN2000 (`registry/huawei_sun2000.json`)
* SMA Sunny Tripower (`registry/sma_sunny_tripower.json`)
* Fronius Symo GEN24 + BYD (`registry/fronius_gen24_byd.json`)
* SolarEdge StorEdge (`registry/solaredge_storedge.json`)
* BYD Battery-Box (`registry/byd_battery_box.json`)
* Tesla Powerwall 3 (`registry/tesla_powerwall3.json`)
* Victron MultiPlus-II (`registry/victron_multiplus2.json`)
