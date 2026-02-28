# BESSAI Edge Gateway — Pilot Deployment Guide
**v2.14.0** · NTSyCS 11 GAPs · BESSAIServer Unificado · CEN SC Bidder

---

## Checklist antes del primer arranque

```bash
# 1. Clonar y configurar
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge

# 2. Editar config/.env con los valores del sitio
cp .env.example config/.env
nano config/.env   # ver "Variables críticas" abajo

# 3. Generar certificados mTLS para CEN (GAP-003)
make cert SITE_ID=SITE-CL-001
# → infrastructure/certs/SITE-CL-001/{ca.crt, client.crt, client.key}

# 4. Validar la configuración completa (debe dar score 100/100)
make pilot SITE_ID=SITE-CL-001

# 5. Si score 100/100 → arrancar producción
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d

# Con monitoreo Prometheus + Grafana:
docker compose -f docker-compose.yml -f docker-compose.production.yml --profile monitoring up -d
```

---

## Variables críticas para el piloto

| Variable | Valor ejemplo | Obligatorio | Descripción |
|---|---|---|---|
| `BESSAI_SITE_ID` | `SITE-CL-001` | ✅ | ID único del sitio |
| `BESSAI_CAPACITY_KWH` | `1000.0` | ✅ | Capacidad BESS en kWh |
| `BESSAI_P_NOM_KW` | `500.0` | ✅ | Potencia nominal en kW |
| `MODBUS_HOST` | `192.168.1.100` | ✅ | IP inversor Modbus TCP |
| `IEC104_HOST` | `192.168.1.100` | ○ | IP inversor IEC 60870-5-104 |
| `CEN_ENDPOINT` | `https://api.coordinador.cl/v1/telemetry` | ✅ | Endpoint API CEN |
| `CEN_TLS_CERT` | `infrastructure/certs/SITE-CL-001/client.crt` | ✅ | Cert mTLS CEN |
| `CEN_TLS_KEY` | `infrastructure/certs/SITE-CL-001/client.key` | ✅ | Key mTLS CEN |
| `CEN_TLS_CA` | `infrastructure/certs/SITE-CL-001/ca.crt` | ✅ | CA mTLS CEN |
| `CSIRT_API_KEY` | `sk-csirt-xxxxx` | ✅ | API key CSIRT · Ley 21.663/2024 |
| `SC_PFR_PRICE_USD_MWH` | `1.5` | ✅ | Precio SC PFR (USD/MWh) |
| `SC_CREG_PRICE_USD_MWH` | `2.0` | ○ | Precio SC CREG |
| `SC_AGC_PRICE_USD_MWH` | `3.5` | ○ | Precio SC AGC |
| `BESSAI_DRL_ENABLED` | `false` | — | Activar PPO (requiere ONNX) |

> **Obtener CSIRT API key:** csirt.gob.cl/registro-operadores
> **Registrar BESS en CEN:** SIGC portal → cert.cen.cl → sección "Almacenamiento"

---

## Requerimientos de hardware

| Componente | Mínimo | Recomendado |
|---|---|---|
| CPU | Raspberry Pi 4 (arm64) | Intel NUC / mini-PC x86 |
| RAM | 2 GB | 4–8 GB |
| Almacenamiento | 16 GB SD | 64 GB SSD |
| Red LAN | 100 Mbps | Ethernet Gig + 4G failover |
| Internet | 5 Mbps para CEN/CSIRT | 20 Mbps + redundancia |
| NTP | `chronyc tracking` drift <1s | GPS-NTP (obligatorio telemetría CEN) |
| Protocolo inversor | Modbus TCP (puerto 502) | IEC 60870-5-104 (puerto 2404) |
| Docker | 24.x+ | 27.x+ |

---

## Verificar estado en producción

```bash
# Health + compliance (v2.14.0 — BESSAIServer unificado)
make health                   # curl /health → JSON
make compliance-report        # curl /compliance/report → JSON SEC/CEN
make fleet                    # curl /fleet/summary → VPP KPIs

# Métricas Prometheus
curl http://localhost:8000/metrics | grep bess_

# Telemetría última cycle
curl http://localhost:8000/api/v1/telemetry | python -m json.tool
```

### Respuesta esperada `/health` (gateway sano)

```json
{
  "status": "healthy",
  "site_id": "SITE-CL-001",
  "version": "2.14.0",
  "uptime_s": 3601.0,
  "last_cycle": 720,
  "compliance_ok": true,
  "compliance_score": 100.0
}
```

### Respuesta esperada `/compliance/status` (NTSyCS conforme)

```json
{
  "status": "compliant",
  "compliance_score": 100.0,
  "norm_ref": "NTSyCS CEN Chile — 11 GAPs v2.12.0",
  "site_id": "SITE-CL-001",
  "violations": [],
  "gaps_checked": 11
}
```

---

## Activar SC Bidder (Servicios Complementarios)

Una vez registrado en CEN y obtenido el endpoint real:

```bash
# En config/.env:
CEN_ENDPOINT=https://api.coordinador.cl/v1/sc  # endpoint real CEN
CEN_SC_DRY_RUN=false                             # desactivar dry-run

# Verificar elegibilidad
python -c "
from src.core.cen_sc_bidder import CENSCBidder, SCType
b = CENSCBidder(site_id='SITE-CL-001', p_nom_kw=500.0, dry_run=False)
ok, reason = b.check_eligibility(75.0, SCType.PFR)
print('Eligible:', ok, reason or 'OK')
"

# Ver stats de licitaciones
curl http://localhost:8000/api/v1/telemetry
```

---

## Entrenar PPO con datos reales CEN (BEP-0200 Phase 3)

```bash
# 1. Exportar datos CEN a CSV
make export-cmg   # → data/cen_telemetry.csv

# 2. Entrenar PPO (500k steps, ~10 min en NUC)
make train-ppo SITE_ID=SITE-CL-001

# 3. Exportar modelo ONNX
make export-onnx
# → models/dispatch_policy.onnx + models/dispatch_policy.json

# 4. Activar en producción
# En config/.env:
# BESSAI_DRL_ENABLED=true
# BESSAI_ONNX_MODEL_PATH=models/dispatch_policy.onnx
```

---

## Endpoints disponibles (BESSAIServer v2.14.0)

| Endpoint | Método | Descripción |
|---|---|---|
| `/health` | GET | Estado + compliance_score (200/503) |
| `/metrics` | GET | Prometheus text exposition |
| `/compliance/status` | GET | NTSyCS state (200/503) |
| `/compliance/report` | GET | Informe completo por GAP para SEC/CEN |
| `/fleet/summary` | GET | KPIs VPP multi-sitio |
| `/fleet/sites` | GET | Telemetría por sitio (array) |
| `/api/v1/telemetry` | GET | Snapshot último ciclo de adquisición |
| `/api/der/*` | * | IEEE 2030.5 / SEP 2.0 (si habilitado) |

---

## Logs esperados en el primer arranque

```
{"level":"info","event":"bessai_server.started","port":8000,"endpoints":["/health","/metrics","/compliance/status",...]}
{"level":"info","event":"compliance_stack.enabled","modules":11,"cycle_ms":0.23,"norm_ref":"NTSyCS CEN Chile — 11 GAPs v2.12.0"}
{"level":"info","event":"gateway.started","site":"SITE-CL-001","version":"2.14.0","poll_interval_s":5}
{"level":"info","event":"cycle","cycle":1,"compliance_ok":true,"safety_ok":true,"soc_pct":65.0}
{"level":"info","event":"cen_bidder.dry_run_bid","sc_type":"PFR","capacity_kw":100.0,"price":1.5}
```

---

## Cronograma realista de despliegue

```
Hoy          → cp .env.example config/.env  →  editar valores reales
Día 1-2      → Registro portal CEN (SIGC)   →  obtener CEN_ENDPOINT
Día 1-2      → csirt.gob.cl                 →  obtener CSIRT_API_KEY
Día 2-3      → make cert SITE_ID=...        →  enviar cert a CEN por email
Día 3        → make pilot  (score: 100/100) →  ✅ LISTO PARA ARRANCAR
Día 3        → docker compose up -d         →  Gateway en vivo
Semana 1+    → compliance_ok=true           →  telemetría fluyendo a CEN
Semana 2+    → dry_run=False                →  primeras licitaciones SC (PFR)
Semana 3+    → make train-ppo               →  ONNX trained con datos reales
```

---

## Soporte

- Documentación: `docs/`
- Issues: github.com/bess-solutions/open-bess-edge/issues
- Email: ingenieria@bess-solutions.cl
- Compliance: `make compliance-report` → compartir JSON con SEC/CEN
