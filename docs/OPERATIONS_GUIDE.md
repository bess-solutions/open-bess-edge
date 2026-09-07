# Guía de Operaciones Industriales — BESSAI Edge Gateway

Esta guía describe los procedimientos operativos para desplegar, supervisar y mantener el BESSAI Edge Gateway en hardware de borde (Industrial PC, Raspberry Pi 4/5, o servidores locales de subestación) en conexión directa con inversores y sistemas BESS.

---

## 1. Arquitectura de Despliegue de Borde

El Gateway opera localmente junto al controlador del inversor o BMS, interactuando directamente a través de **Modbus TCP / RTU** sobre redes OT aisladas:

* **Modo Servicio Systemd:** Despliegue nativo para hardware embebido (Linux Debian/Ubuntu/Raspberry Pi OS).
* **Modo Contenedor Docker:** Despliegue en contenedor con aislamiento de dependencias y reinicio automático.

---

## 2. Puesta en Marcha con Systemd

### Archivo de Unidad (`/etc/systemd/system/bessai-edge.service`)

```ini
[Unit]
Description=BESSAI Edge Gateway Industrial Service
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=bess
WorkingDirectory=/opt/bessai-edge
EnvironmentFile=/opt/bessai-edge/config/.env
ExecStart=/opt/bessai-edge/.venv/bin/python -m src.edge_node
Restart=always
RestartSec=5s
LimitNOFILE=65535

# Aislamiento de seguridad OT (IEC 62443 SL-2)
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/opt/bessai-edge/data
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

### Comandos de Control Operativo

```bash
# Iniciar servicio
sudo systemctl start bessai-edge

# Verificar estado operativo y watchdog
sudo systemctl status bessai-edge

# Monitorear telemetría en tiempo real
sudo journalctl -u bessai-edge -f -o cat
```

---

## 3. Puesta en Marcha con Docker Compose

```bash
# Iniciar gateway en segundo plano
docker compose up -d

# Ver logs de eventos y lazos de control
docker compose logs -f --tail=100 bessai-edge
```

---

## 4. Supervisión de Telemetría y Salud Nodal

El gateway expone internamente métricas de operación física:

| Métrica | Umbral Normal | Acción si Excede |
| :--- | :--- | :--- |
| **`modbus_poll_latency_ms`** | $< 100\text{ ms}$ | Revisar conmutador Ethernet OT, cableado apantallado o saturación del inversor. |
| **`grid_frequency_hz`** | $49.80 - 50.20\text{ Hz}$ | Operación nominal SEN Chile. Fuera de banda activa droop FFR. |
| **`battery_soc_pct`** | $10\% - 95\%$ | Límites operativos de protección contra degradación acelerada. |
| **`battery_cell_temp_max_c`** | $< 45^\circ\text{C}$ | Si $> 55^\circ\text{C}$, el evaluador de envolvente dispara trip preventivo. |

---

## 5. Protocolo de Respuesta a Disparos de Seguridad (Safety Envelope)

Cuando `src.safety.safety_envelope_evaluator` detecta una anomalía de red o de celda:

1. **Estado TRIP:** El Gateway inhibe inmediatamente las órdenes de carga/descarga y comanda potencia activa $P = 0\text{ kW}$.
2. **Registro de Causa Raíz:** Inspeccionar el log JSON en `data/bess_safety_baseline.json` o salida de consola.
3. **Restablecimiento:** Requiere que las variables eléctricas retornen a la banda segura durante al menos 60 segundos antes de reanudar el lazo de despacho.
