# BESSAI Edge Gateway — Pilot Deployment Guide
**v2.13.0** · NTSyCS Full Compliance · First Production Site

---

## Checklist antes del primer arranque

```bash
# 1. Clonar y configurar
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge
cp .env.example config/.env

# 2. Editar config/.env con los valores del sitio
#    SITE_ID, INVERTER_IP, BESSAI_P_NOM_KW, CSIRT_API_KEY ...

# 3. Generar certificados mTLS para CEN (GAP-003)
bash infrastructure/certs/gen_certs.sh SITE-CL-001

# 4. Validar la configuración completa
python scripts/pilot_setup.py --site-id SITE-CL-001 --inverter-ip 192.168.1.100

# 5. Si el score es 100/100 → arrancar
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d

# Con monitoreo Prometheus + Grafana:
docker compose -f docker-compose.yml -f docker-compose.production.yml --profile monitoring up -d
```

---

## Variables críticas para el piloto

| Variable | Valor ejemplo | Descripción |
|---|---|---|
| `SITE_ID` | `SITE-CL-001` | ID único del sitio |
| `INVERTER_IP` | `192.168.1.100` | IP del inversor BESS |
| `BESSAI_P_NOM_KW` | `1000.0` | Potencia nominal en kW |
| `CEN_TLS_CERT` | `infrastructure/certs/client.crt` | Cert mTLS CEN |
| `CEN_TLS_KEY` | `infrastructure/certs/client.key` | Key mTLS CEN |
| `CSIRT_API_KEY` | `sk-csirt-xxxxx` | API key CSIRT Nacional |
| `SC_PFR_PRICE_USD_MWH` | `1.5` | Precio SC PFR (CEN 2024) |

---

## Verificar estado en producción

```bash
# Health + compliance status
curl http://localhost:8000/health
curl http://localhost:8000/compliance/status

# Informe completo SEC/CEN
curl http://localhost:8000/compliance/report | python -m json.tool

# Métricas Prometheus
curl http://localhost:8000/metrics | grep bess
```

### Respuesta esperada `/compliance/status` (sitio ok)

```json
{
  "status": "compliant",
  "compliance_score": 100.0,
  "norm_ref": "NTSyCS CEN Chile — 11 GAPs v2.12.0",
  "site_id": "SITE-CL-001"
}
```

---

## Activar Servicios Complementarios (SC) en CEN

1. Completar registro en el Coordinador Eléctrico Nacional (CEN)
2. Que `ServiciosComplementarios.check_eligibility()` retorne `True`
   ```python
   python -c "
   from src.core.servicios_complementarios import ServiciosComplementarios
   sc = ServiciosComplementarios()
   print(sc.check_eligibility({'p_nom_kw': 1000, 'response_time_s': 1.5}))
   "
   ```
3. Configurar oferta automática en CEN (coordinar con el operador del sitio)

---

## Endpoints disponibles en producción

| Endpoint | Método | Auth | Descripción |
|---|---|---|---|
| `/health` | GET | — | Estado del gateway (200/503) |
| `/metrics` | GET | — | Métricas Prometheus |
| `/compliance/status` | GET | — | Estado compliance NTSyCS |
| `/compliance/report` | GET | — | Informe completo SEC/CEN (JSON) |
| `/api/der/*` | * | mTLS | IEEE 2030.5 / SEP 2.0 (si habilitado) |

---

## Logs esperados en el primer arranque

```
{"level":"info","event":"compliance_stack.enabled","modules":11,"cycle_ms":0.23,"norm_ref":"NTSyCS CEN Chile — 11 GAPs (v2.12.0)"}
{"level":"info","event":"gateway.started","site":"SITE-CL-001","poll_interval_s":5}
{"level":"info","event":"cycle","cycle":1,"compliance_ok":true,"safety_ok":true}
```

---

## Soporte

- Documentación: `docs/`
- Issues: github.com/bess-solutions/open-bess-edge/issues
- Email interno: ingenieria@bess-solutions.cl
