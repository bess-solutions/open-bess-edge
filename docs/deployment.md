# Guía de Despliegue en Producción — Open BESS Edge

Esta guía técnica proporciona las recomendaciones y requisitos obligatorios para desplegar el gateway **Open BESS Edge** en entornos industriales de subestaciones y plantas de almacenamiento de energía a gran escala (BESS).

---

## 1. Hardware Recomendado

Para garantizar un rendimiento estable y rango de temperatura industrial compatible con salas de control y celdas de media tensión, se prescriben las siguientes plataformas:

| Plataforma | Especificaciones Técnicas Mínimas | Escenario de Uso |
|---|---|---|
| **Moxa UC Series** (ej. UC-8112-LX) | ARM Cortex-A8 1 GHz, 512 MB RAM, Rango Temp: -40°C a 75°C, Dual Ethernet. | Puerta de enlace OT compacta y robusta en terreno. |
| **Advantech UNO Series** (ej. UNO-2000) | Intel Atom/Core i3, 4 GB RAM, Fanless, Entrada de alimentación redundante DC. | Concentrador de datos y servidor MCP local con modelos ONNX múltiples. |
| **Raspberry Pi 4/5 Compute Module** | ARM Cortex-A72, 2GB+ RAM, disipador pasivo industrial de aluminio. | Prototipado avanzado, validaciones previas y pilotos de bajo costo. |

---

## 2. Topología de Red y Reglas de Ciberseguridad (FortiGate)

El gateway debe situarse en una **DMZ Industrial** y no tener acceso directo a internet abierta.

### Configuración del Conector Modbus/TCP en el Inversor/PCS:
* **Allowlist de Origen**: El firewall local del inversor o el router industrial de switch debe restringir las peticiones entrantes del puerto `502` únicamente a la dirección IP estática asignada al Gateway Open BESS Edge.
* **Cifrado OT (mTLS)**: Si los dispositivos BMS/PCS soportan encapsulamiento seguro, configurar túneles IPSec o mTLS locales utilizando el modulo de configuración de TLS de BESSAI.

---

## 3. Integración con UPS de Control y Apagado Seguro

El sistema de alimentación ininterrumpida (UPS) debe ser monitoreado de forma permanente a través de su tarjeta SNMP o Modbus TCP para evitar corrupción del sistema operativo y pérdida de telemetría durante apagones prolongados:

```
[Red AC Principal] ──> [UPS Doble Conversión] ──> [Switches, Firewall, Gateway]
                             │
                             └─(Alerta de Batería <15%)──> [Graceful Shutdown]
```

### Protocolo de Apagado (Graceful Shutdown)
1. **Detección**: El daemon de monitoreo de UPS del gateway lee el registro de capacidad remanente.
2. **Pre-alarma**: Si la batería cae por debajo del 20%, se envía un paquete Syslog/MQTT crítico indicando pérdida de suministro inminente.
3. **Guardado Seguro**: A menos del 15% de batería, el EMS local detiene el bucle de consultas Modbus, cierra los sockets de conexión de forma limpia, y escribe el estado de degradación y logs pendientes en la unidad flash no volátil.
4. **Shutdown**: El gateway ejecuta el comando de apagado seguro del sistema operativo:
   ```bash
   sudo shutdown -h now
   ```
5. **Autorestart**: Al retornar el suministro AC y cargarse la UPS por encima del 30%, el BIOS/firmware del gateway debe estar configurado para encender automáticamente (Restore AC Power Loss = Power On) y reactivar los daemons del gateway de forma Headless.
