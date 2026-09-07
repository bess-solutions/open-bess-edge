# Guía de Puesta en Servicio de Pilotos (Site Pilot Guide) — BESSAI Edge Gateway

Esta guía detalla los pasos de ingeniería de campo para comisionar el BESSAI Edge Gateway en una instalación BESS piloto, validando la comunicación Modbus TCP con el inversor y la respuesta dinámica conforme a las exigencias del Coordinador Eléctrico Nacional (CEN) y la NTSyCS de Chile.

---

## 1. Requisitos Previos en Terreno

* **Hardware:** Raspberry Pi 4/5, IPC industrial o servidor local con Linux.
* **Red OT:** Conexión Ethernet con visibilidad IP hacia el inversor o controlador de planta (ej. Huawei SmartLogger, SMA Data Manager).
* **Entorno:** Python 3.10+ o Docker con Docker Compose.

---

## 2. Configuración del Sitio

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/bess-solutions/open-bess-edge.git
   cd open-bess-edge
   ```

2. **Preparar entorno local:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # En Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configurar parámetros en `config/edge_config.yaml`:**
   ```yaml
   site:
     id: "PILOT-CL-LINARES-01"
     inverter_type: "huawei_sun2000"
     modbus_host: "192.168.1.50"
     modbus_port: 502
     unit_id: 1

   grid_standards:
     nominal_frequency_hz: 50.0
     deadband_hz: 0.030          # ±30 mHz según Estudio CEN CFyDR 2026
     droop_percentage: 3.0       # Estatismo s = 3%
     ffr_response_time_ms: 500   # Respuesta rápida FFR sub-500ms
   ```

---

## 3. Verificación Preflight de Controladores

Antes de energizar o habilitar el lazo de consignas al inversor, ejecutar la suite de pruebas de cumplimiento:

```bash
# Validar controladores FFR, Volt/VAR y envolvente de seguridad
pytest tests/ -v --tb=short
```

Debe confirmar **18/18 pruebas aprobadas** (100% pass rate).

---

## 4. Conexión y Arranque del Gateway

Ejecutar el nodo de borde en modo supervisión:

```bash
python -m src.edge_node --config config/edge_config.yaml
```

Verificar en la salida de consola:
1. Conexión exitosa al socket Modbus TCP del inversor.
2. Lectura de tensión, corriente, potencia activa/reactiva y SoC.
3. Evaluación de envolvente de seguridad en estado `NORMAL`.

---

## 5. Pruebas de Despacho y Estatismo en Sitio

Para simular o auditar el lazo FFR:
* Inyectar un escalón de frecuencia en el simulador o esperar oscilaciones naturales del SEN.
* Verificar que la consigna de potencia $\Delta P$ responda proporcionalmente al estatismo configurado ($s=3\%$) respetando la banda muerta de $\pm 30\text{ mHz}$.
