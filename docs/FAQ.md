# BESSAI Edge Gateway — FAQ Técnica para Adopters

> Respuestas directas a las preguntas más comunes. Sin rodeos.

---

## Integración de hardware

### ¿Funciona con inversores distintos de Huawei SUN2000?

**Sí.** BESSAI usa un sistema de perfiles JSON para soportar cualquier inversor que hable Modbus TCP o IEC 60870-5-104. Los inversores certificados actualmente son:

| Fabricante | Protocolo | Perfil |
|------------|-----------|--------|
| Huawei SUN2000 | Modbus TCP | `registry/huawei_sun2000.json` |
| SolarEdge StorEdge | SunSpec Modbus | `registry/solaredge_storedge.json` |
| BYD Battery-Box | CAN bus | `registry/byd_battery_box.json` |
| Tesla Powerwall 3 | REST API | `registry/tesla_powerwall3.json` |

Para añadir el tuyo: [tutorials/hardware_profile_contribution.md](tutorials/hardware_profile_contribution.md)

---

### ¿Puedo usar MQTT en vez de Modbus TCP?

MQTT no es un protocolo estándar de adquisición de datos en BESSAI (que usa Modbus TCP / IEC 104 para leer el hardware), pero sí puedes **publicar telemetría vía MQTT** hacia Home Assistant u otros brokers:

→ [tutorials/integration_homeassistant.md](tutorials/integration_homeassistant.md)

Si tu inversor solo habla MQTT, necesitarás un adaptador MQTT→Modbus (ej: Node-RED). Abre un issue si quieres orientación.

---

### ¿Qué pasa si no tengo conectividad a internet?

BESSAI está diseñado para operar **100% offline** en modo edge:

- El gateway **no requiere internet** para adquirir telemetría y gestionar la batería
- Los modelos ONNX se ejecutan localmente (no hay llamadas a APIs externas de IA)
- GCP Pub/Sub, CSIRT y CEN son opcionales — si no están configurados, el sistema arranca sin ellos con mensajes de WARNING (no errores críticos)

Para modo offline completo: en `config/.env`, deja vacíos `GCP_PROJECT_ID`, `CEN_ENDPOINT` y `CSIRT_API_KEY`.

---

### ¿BESSAI funciona en Windows?

El gateway en sí corre en Docker, así que **sí funciona en Windows** (require Docker Desktop con WSL2). 

Sin embargo, el hardware industrial (Modbus TCP) suele requerir conectividad LAN directa al inversor. La red de Docker en Windows tiene algunas limitaciones con `host` networking — se recomienda Linux o Raspberry Pi para producción.

---

## Mercados fuera de Chile

### Mi mercado no es Chile. ¿Aun así sirve?

**Sí, con configuración manual.** Las partes específicas de Chile son:

| Módulo | Qué hace | Sin Chile |
|--------|----------|-----------|
| `CENSCBidder` | Licita servicios complementarios al CEN | Déjalo en `dry_run=True` o desactívalo |
| `ComplianceStack` | Valida NTSyCS (normativa chilena) | Siempre pasa si `CEN_ENDPOINT` está vacío |
| `CMgPredictor` | Predice precios del mercado SEN Chile | Puedes alimentarlo con datos de tu mercado |
| `ArbitrageEngine` | Optimiza despacho por precios spot | Compatible con cualquier señal de precio |

Para operar en otro mercado, en `config/.env`:
```bash
CEN_ENDPOINT=          # vacío → CEN desactivado
CSIRT_API_KEY=         # vacío → notificaciones CSIRT desactivadas
# Configura tus precios directamente:
SC_PFR_PRICE_USD_MWH=1.5   # precio de tu mercado local
```

---

### ¿Cómo adapto BESSAI a México (CENACE / GDMTH)?

El módulo `LoadProfiler` ya incluye soporte para tarifas GDMTH de CFE México:

```bash
# Ejecutar análisis de tarifa GDMTH
python -m src.analytics.tariffs.load_profiler --market mexico_gdmth
```

Para conectar con datos CENACE en tiempo real, sigue el mismo patrón que `scripts/bessai_data_scraper.py` pero apuntando al endpoint de CENACE. Abre un issue con la etiqueta `mexico` si quieres soporte.

---

### ¿Y España / REE?

No hay integración nativa con REE/OMIE aún. El motor de arbitraje (`ArbitrageEngine`) es agnóstico al mercado — puedes alimentarlo con precios de cualquier fuente. Abre un issue con la etiqueta `spain` si estás interesado en desarrollar el conector.

---

## Performance y escalabilidad

### ¿Cuántos sitios puedo manejar en paralelo?

El componente `FleetOrchestrator` soporta múltiples sitios en modo VPP. Límites orientativos:

| Hardware gateway | Sitios simultáneos | Ciclo de polling |
|------------------|--------------------|-----------------|
| Raspberry Pi 4 (4 GB) | 3–5 sitios | 5 s |
| Intel NUC i5 (8 GB) | 10–20 sitios | 5 s |
| Servidor Linux (16 GB) | 50+ sitios | 5 s |

El cuello de botella es la latencia Modbus TCP, no el CPU. Cada sitio necesita ~20 ms de latencia de red.

---

### ¿El modo AI-IDS consume demasiada CPU en Raspberry Pi?

En modo normal, el AI-IDS (`ModbusAnomalyDetector`) usa IsolationForest + z-score. En Raspberry Pi 4:
- **CPU en reposo:** ~3–5% adicional
- **Durante fit():** pico de ~20% durante ~2 s (solo al inicio)

Si el CPU es un problema, activa el modo liviano:
```bash
# En config/.env:
BESSAI_LIGHTWEIGHT=1   # desactiva AI-IDS full, VPP, P2P y FL
```
Esto reduce el consumo CPU en ~50% con impacto mínimo en funcionalidad core.

---

### ¿Qué tan grande es la imagen Docker?

| Imagen | Tamaño comprimido |
|--------|-------------------|
| `bessai-edge` (producción) | ~380 MB |
| Con perfil simulador | ~420 MB |
| Con Prometheus + Grafana | ~900 MB total (3 contenedores) |

---

## Licencia y datos

### ¿Puedo usarlo en proyectos comerciales?

**Sí, bajo Apache 2.0** (la licencia del repositorio `open-bess-edge`). Puedes:
- Desplegarlo en instalaciones comerciales de clientes
- Integrarlo en tu propio producto
- Modificar el código sin obligación de publicar los cambios

La única restricción es mantener los créditos de copyright originales.

> ⚠️ Los modelos ONNX entrenados (`bessai-models`) se distribuyen bajo licencia separada desde el índice privado de BESS Solutions. El código de entrenamiento es open source; los pesos entrenados en producción son propietarios.

---

### ¿BESSAI colecta mis datos operativos?

**No.** El gateway solo:
1. Lee datos de **tu** inversor vía Modbus/IEC 104
2. Publica a **tu** instancia de GCP (si la configuras)
3. Envía telemetría a **tu** endpoint CEN (si participas en el mercado chileno)

BESS Solutions no tiene acceso a ninguno de esos datos. No hay telemetría hacia servidores de BESS Solutions en el código open source.

---

### ¿Necesito firmar un NDA?

- **Para usar el software:** No.
- **Para acceso a datasets históricos CMg:** Sí, un NDA simple de 1 página (solo aplica para el programa Early Adopters).

---

## Troubleshooting

### El gateway no conecta al inversor por Modbus

```bash
# 1. Verificar conectividad TCP al inversor
nc -zv 192.168.1.100 502   # debe decir "succeeded"

# 2. Si está bloqueado: verificar firewall del inversor
# Huawei SUN2000: habilitar Modbus TCP en app SUN2000 o dongle 4G

# 3. Capturar logs detallados
docker logs bessai-gateway 2>&1 | grep -i "modbus\|connect\|error"
```

---

### El compliance_score no llega a 100

```bash
# Ver detalle de cada GAP
curl http://localhost:8000/compliance/report | python -m json.tool

# Los GAPs más comunes que fallan:
# GAP-003: certificados mTLS no generados → make cert SITE_ID=...
# GAP-006: NTP sin sincronizar → chronyc tracking
# GAP-009: CSIRT_API_KEY vacío → csirt.gob.cl/registro
```

---

### Los contenedores arrancan pero Grafana no muestra datos

```bash
# Verificar que Prometheus está scrapeando
curl http://localhost:9090/api/v1/query?query=up

# Verificar que el gateway exporta métricas
curl http://localhost:8000/metrics | grep bess_

# Si Prometheus tiene "No targets": esperar 30 s y refrescar
```

---

*¿Tu pregunta no está aquí? [Abre un issue](https://github.com/bess-solutions/open-bess-edge/issues/new?labels=question,adopter-support) con la etiqueta `adopter-support`.*
