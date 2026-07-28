# Servidor MCP (Model Context Protocol) — Open BESS Edge

El servidor MCP de **Open BESS Edge** es una interfaz basada en stdio que expone herramientas de telemetría, diagnóstico e higiene cibernética del gateway industrial a asistentes de inteligencia artificial (como Claude Desktop, extensiones de editores o swarms autónomos).

---

## 🔒 Política Zero Mock Data y Fallo Rápido (Fail-Fast)

De acuerdo con el estándar industrial de Open BESS Edge, todas las herramientas MCP operan con datos y conexiones reales de la planta.
* **No hay simulación estática de fallback**: Si el inversor Modbus está desconectado, o los archivos del dataset de degradación no están presentes, la herramienta **fallará inmediatamente** arrojando un error claro al asistente. Esto evita falsos positivos de salud y garantiza la auditabilidad del sistema.

---

## 🛠️ Herramientas Expuestas

### 1. `get_battery_health`
Lee las variables del perfil de telemetría de red del BESS.

* **Parámetros**:
  * `unit_id` (int, opcional): ID del esclavo Modbus (default: `1`).
  * `host` (str, opcional): Hostname/IP del BESS (default: `"localhost"`).
  * `port` (int, opcional): Puerto Modbus TCP (default: `5020`).
  * `profile` (str, opcional): Nombre del perfil JSON en `registry/` (default: `"simulator.json"`).
* **Ejemplo de Retorno (JSON)**:
  ```json
  {
    "unit_id": 1,
    "connected": true,
    "telemetry": {
      "soc_pct": 85.5,
      "temp_c": 26.2,
      "active_power_w": 1200.0,
      "ac_voltage_v": 220.5,
      "frequency_hz": 50.02
    },
    "status": "Operational (SOH not exposed by simulator profile)"
  }
  ```

### 2. `diagnose_faults`
Decodifica registros de alarmas activas del BESS.

* **Parámetros**:
  * `unit_id` (int, opcional): ID del esclavo Modbus (default: `1`).
  * `host` (str, opcional): IP del BESS (default: `"localhost"`).
  * `port` (int, opcional): Puerto TCP (default: `5020`).
  * `profile` (str, opcional): Perfil JSON (default: `"simulator.json"`).
* **Ejemplo de Retorno (JSON)**:
  ```json
  {
    "unit_id": 1,
    "inverter_state_code": 256,
    "status": "Running",
    "active_faults": [],
    "diagnostics": "No active alarm bitmasks defined in simulator profile."
  }
  ```

### 3. `predict_rul`
Pronostica la degradación y vida útil remanente (Remaining Useful Life) calculando el desgaste térmico de Arrhenius sobre el dataset real.

* **Parámetros**:
  * `unit_id` (int, opcional): ID de unidad (default: `1`).
  * `dataset_path` (str, opcional): Ruta al archivo `.parquet` (default: `"data/training_dataset.parquet"`).
* **Ejemplo de Retorno (JSON)**:
  ```json
  {
    "unit_id": 1,
    "dataset_analyzed": "C:\\Users\\lenovo\\OneDrive\\Desktop\\02_Proyectos_Tech\\01_BESS_Tech\\open-bess-edge\\data\\training_dataset.parquet",
    "total_records_hours": 744,
    "mean_ambient_temp_c": 21.4,
    "max_ambient_temp_c": 38.6,
    "calculated_hourly_degradation_pct": 0.00000314,
    "estimated_current_soh_pct": 98.5,
    "projected_remaining_hours": 58917.2,
    "projected_remaining_days": 2454.8,
    "projected_remaining_cycles": 2454.8,
    "end_of_life_threshold_soh_pct": 80.0,
    "status": "Prediction successfully generated using Arrhenius thermal-stress kinetics."
  }
  ```

### 4. `cyber_hygiene_check`
Audita la postura de seguridad (SSH, TLS, Cortafuegos) en el gateway local.

* **Parámetros**:
  * `host_ip` (str, opcional): IP del gateway host (default: `"localhost"`).
* **Ejemplo de Retorno (JSON)**:
  ```json
  {
    "host": "localhost",
    "timestamp": "2026-06-16T04:40:15.123456",
    "ssh_compliance": {
      "compliant": true,
      "details": {
        "config_file": "/etc/ssh/sshd_config",
        "PasswordAuthentication_Disabled": true,
        "PermitRootLogin_Disabled": true,
        "PubkeyAuthentication_Enabled": true
      }
    },
    "tls_compliance": {
      "compliant": true,
      "details": {
        "config_file": "/etc/ssl/openssl.cnf",
        "MinProtocol_TLS1_3": true,
        "CustomCipherString": true
      }
    },
    "security_level_achieved": "SL-2 (Operational - Recommended)",
    "overall_status": "COMPLIANT"
  }
  ```
