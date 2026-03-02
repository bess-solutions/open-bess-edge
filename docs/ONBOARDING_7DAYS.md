# BESSAI Edge Gateway — Onboarding en 7 Días

> De "cloné el repo" a "sistema en producción con datos reales". Día a día, sin saltarse pasos.

---

## Antes de empezar — Checklist de prerequisitos

Verifica esto antes del Día 0:

```bash
docker --version          # ≥ 24.x
docker compose version    # ≥ 2.x
git --version             # ≥ 2.40
python --version          # ≥ 3.11 (opcional para desarrollo)
```

**Hardware mínimo para producción:**
- CPU: Raspberry Pi 4 (4GB) o superior
- Red: acceso LAN directo al inversor (Modbus TCP puerto 502)
- Internet: para telemetría CEN y actualizaciones (puede ser 4G)

**Sin hardware todavía?** No hay problema — los Días 0-1 funcionan 100% con simulador.

---

## Día 0 — Primera demo local (30 min)

**Objetivo:** Ver BESSAI corriendo en tu máquina con datos simulados.

```bash
# 1. Clonar el repositorio
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge

# 2. Activar el hook de seguridad (protege archivos propietarios)
bash scripts/install_hooks.sh

# 3. Levantar stack completo con simulador
docker compose -f infrastructure/docker/docker-compose.yml \
  --profile simulator \
  --profile monitoring \
  up --build -d

# 4. Esperar ~60 segundos y verificar
curl http://localhost:8000/health
# Esperado: {"status": "ok", "site_id": "SITE-SIM-001", ...}
```

**Abre en el navegador:**
- `http://localhost:8000/health` → Estado del gateway
- `http://localhost:9090` → Prometheus (métricas raw)
- `http://localhost:3000` → Grafana (dashboard visual)

✅ **Día 0 completado** cuando ves el dashboard de Grafana con SOC y potencia moviéndose.

> 📖 Guía detallada: [tutorials/quickstart_5min.md](tutorials/quickstart_5min.md)

---

## Día 1 — Entender la arquitectura (1–2 h)

**Objetivo:** Saber qué hace cada pieza antes de tocarla.

### Lectura recomendada (en orden)

| Documento | Tiempo | Por qué |
|-----------|--------|---------|
| [architecture.md](architecture.md) | 20 min | Mapa mental del sistema completo |
| [API.md](API.md) | 15 min | Los 8 endpoints del gateway |
| [.env.example](../.env.example) | 10 min | Todas las variables disponibles |

### Mini-experimentos mientras lees

```bash
# Ver todas las métricas Prometheus disponibles
curl http://localhost:8000/metrics | grep "^bess_" | cut -d'{' -f1 | sort -u

# Ver telemetría del último ciclo
curl http://localhost:8000/api/v1/telemetry | python -m json.tool

# Ver estado de compliance (siempre 100% en simulador)
curl http://localhost:8000/compliance/status | python -m json.tool

# Ver logs en tiempo real
docker logs -f bessai-gateway-sim 2>&1 | head -30
```

✅ **Día 1 completado** cuando puedes explicar en 1 oración qué hace cada endpoint.

---

## Día 2 — Configurar para tu sitio real (2–3 h)

**Objetivo:** Crear el `config/.env` con los valores de tu instalación.

```bash
# Copiar el template
cp .env.example config/.env

# Editar con tus valores reales
nano config/.env   # o tu editor preferido
```

### Variables críticas a configurar

```bash
# ── Identidad del sitio ───────────────────────────────────────
BESSAI_SITE_ID=SITE-CL-001          # ID único (ej: nombre-ciudad-001)
BESSAI_CAPACITY_KWH=200.0           # Capacidad real de tu BESS en kWh
BESSAI_P_NOM_KW=100.0               # Potencia nominal en kW

# ── Hardware (un protocolo u otro) ────────────────────────────
MODBUS_HOST=192.168.1.100           # IP real de tu inversor
MODBUS_PORT=502                     # Puerto Modbus (casi siempre 502)
DRIVER_PROFILE_PATH=registry/huawei_sun2000.json  # perfil de tu inversor

# ── Grafana (seguridad) ───────────────────────────────────────
GF_SECURITY_ADMIN_PASSWORD=CambiarEstoAhora!   # contraseña fuerte
```

> Para inversores no-Huawei: ver [FAQ.md → Hardware alternativo](FAQ.md#funciona-con-inversores-distintos-de-huawei-sun2000)

### Validar la configuración

```bash
# Cargar el .env y verificar que el gateway arranca sin errores
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d bessai-edge
docker logs bessai-edge 2>&1 | tail -20
```

✅ **Día 2 completado** cuando ves `"event": "gateway.started"` en los logs sin errores.

---

## Día 3 — Conectar hardware real (3–4 h)

**Objetivo:** Leer datos reales del inversor/batería físicos.

### Verificar conectividad Modbus

```bash
# Desde el host (instalar modbus-cli si no está)
pip install modbus-cli
# Leer registro SOC del SUN2000 (registro 37760, unit_id=0)
modbus read -s 37760 -c 1 -d uint16 192.168.1.100

# Alternativa: verificar con nc
nc -zv 192.168.1.100 502 && echo "Puerto Modbus accesible"
```

### Arrancar con hardware real (sin simulador)

```bash
# Detener el stack de simulación
docker compose -f infrastructure/docker/docker-compose.yml \
  --profile simulator --profile monitoring down

# Arrancar solo con hardware real
docker compose -f docker-compose.yml -f docker-compose.production.yml \
  --profile monitoring up -d
```

### Validar que el SOC se lee correctamente

```bash
watch -n 5 'curl -s http://localhost:8000/api/v1/telemetry | python -m json.tool | grep -E "soc|power_kw"'
```

> 📖 Guía detallada: [tutorials/connecting_real_hardware.md](tutorials/connecting_real_hardware.md)

✅ **Día 3 completado** cuando el SOC del gateway coincide con el que muestra el panel del inversor.

---

## Día 4 — Certificados mTLS y registro CEN (Chile) (2 h)

> **Solo si operas en Chile y participas en el mercado SEN.**  
> Si estás en otro mercado, salta al Día 5.

```bash
# Generar certificados mTLS para tu sitio
make cert SITE_ID=SITE-CL-001
# → infrastructure/certs/SITE-CL-001/{ca.crt, client.crt, client.key}

# Estos certificados deben enviarse al CEN para registro:
# Portal: cert.cen.cl → sección "Almacenamiento"
# Email: Adjuntar client.crt + ca.crt

# Mientras tanto, activar en .env:
CEN_TLS_CERT=infrastructure/certs/SITE-CL-001/client.crt
CEN_TLS_KEY=infrastructure/certs/SITE-CL-001/client.key
CEN_TLS_CA=infrastructure/certs/SITE-CL-001/ca.crt
```

También obtener CSIRT API Key (requerida por Ley 21.663/2024):
→ csirt.gob.cl/registro-operadores

✅ **Día 4 completado** cuando tienes los certs generados y el registro CEN enviado.

---

## Día 5 — Validación pre-producción (1 h)

**Objetivo:** `make pilot` debe dar **100/100**.

```bash
# Validación completa del sitio
make pilot SITE_ID=SITE-CL-001

# Salida esperada:
# ✅ GAP-001 Telemetría tiempo real: OK
# ✅ GAP-003 mTLS CEN: OK
# ✅ GAP-006 Sincronización NTP: OK
# ...
# Score: 100/100 — LISTO PARA PRODUCCIÓN
```

**Si algún GAP falla:**
```bash
# Ver detalle completo
curl http://localhost:8000/compliance/report | python -m json.tool
```

> Los GAPs más comunes que fallan: ver [FAQ.md → compliance_score](FAQ.md#el-compliance_score-no-llega-a-100)

✅ **Día 5 completado** cuando `make pilot` devuelve `Score: 100/100`.

---

## Día 6 — Producción real (1 h)

**Objetivo:** Gateway en producción, telemetría fluyendo, monitoreo activo.

```bash
# Arranque definitivo
docker compose -f docker-compose.yml -f docker-compose.production.yml \
  --profile monitoring up -d

# Verificar estado
make health
make compliance-report

# Configurar alertas Prometheus (opcional pero recomendado)
# Las reglas están en infrastructure/prometheus/alert_rules.yml
```

### Primera semana post-arranque

- Monitorear `compliance_ok = true` en cada ciclo
- Verificar que los logs no tienen errores `CRITICAL`
- Revisar el dashboard Grafana con datos reales

✅ **Día 6 completado** cuando ves `"compliance_ok": true` en `/health` con datos reales.

---

## Día 7 — Optimización con IA (opcional, 2–3 h)

**Objetivo:** Activar el motor DRL (PPO) con datos reales de tu mercado.

```bash
# 1. Obtener datos históricos de precios CMg (Chile)
make scrape   # → data/historical/

# 2. Entrenar modelo PPO con datos reales (500k steps, ~10 min en NUC)
make train-ppo SITE_ID=SITE-CL-001

# 3. Activar el modelo en producción
# En config/.env:
BESSAI_DRL_ENABLED=true
BESSAI_ONNX_MODEL_PATH=models/dispatch_policy.onnx

# 4. Reiniciar el gateway
docker compose restart bessai-edge
```

> 📖 Guía completa de entrenamiento: [tutorials/training_custom_drl.md](tutorials/training_custom_drl.md)

---

## Semana 2+ — SC Bidder y VPP (solo Chile)

Una vez con `compliance_ok=true` sostenido por 7 días:

```bash
# Activar licitaciones reales de Servicios Complementarios
# En config/.env:
CEN_SC_DRY_RUN=false   # era true durante la semana 1

# Monitorear revenue
curl http://localhost:8000/api/v1/telemetry | python -m json.tool | grep revenue
```

---

## Resumen de todo el recorrido

```
Hoy (30 min)   → Demo local en simulador
Día 1 (2h)     → Entender arquitectura + APIs
Día 2 (2h)     → Config .env con valores reales
Día 3 (4h)     → Conectar hardware físico
Día 4 (2h)     → Certs mTLS + registro CEN [Chile]
Día 5 (1h)     → make pilot → 100/100 ✅
Día 6 (1h)     → Producción real en vivo
Día 7 (3h)     → Modelo IA DRL activo [opcional]
Semana 2+      → SC Bidder activo [Chile]
```

---

## ¿Necesitas ayuda en algún paso?

- **Bugs o errores:** [GitHub Issues](https://github.com/bess-solutions/open-bess-edge/issues/new?labels=adopter-support)
- **Preguntas generales:** [GitHub Discussions](https://github.com/bess-solutions/open-bess-edge/discussions)
- **Soporte directo (Early Adopters):** `ingenieria@bess-solutions.cl`
