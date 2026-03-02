# Runbook — BESSAI Edge Gateway Operations

> **Audience:** Operations team and on-call engineers  
> **Version:** v2.14.0 · **Updated:** 2026-03-02

---

## Health Checks

### Gateway is Down (`BESSGatewayDown` alert)

```bash
# 1. Check container status
docker ps --filter name=bessai-gateway

# 2. Check recent logs (last 100 lines)
docker logs bessai-gateway --tail=100

# 3. Restart if container exited
docker compose restart bessai-gateway

# 4. Verify health
curl http://localhost:8000/health
```

**Common causes:**
- `INVERTER_IP` not reachable (check inverter network)
- `GCP_PROJECT_ID` misconfigured (check `config/.env`)
- Port 502 blocked (check firewall)

---

## Safety Alerts

### Low SOC (`BESSLowSOC` < 10%)

```bash
# Check current SOC
curl http://localhost:8000/api/v1/status

# Check safety constraint active
curl http://localhost:8000/health
```

**Action:** Immediately stop all discharge commands. Allow charge from grid.  
If SOC ≤ 5%, `SafetyGuard` automatically blocks all discharge — **no action needed**.

### High Temperature (`BESSHighTemperature` > 45°C)

**Action:** Reduce charge rate by 50%. Alert site engineer. If > 55°C, emergency stop.

---

## AI-IDS Alerts

### Anomaly Detected (`BESSAnomalyDetected` score > 0.8)

**Investigation steps:**
1. Check for unusual power readings in Grafana
2. Verify inverter firmware has not been updated unexpectedly
3. Check for physical access to the hardware (security camera review)
4. If persistent: escalate per `SECURITY.md`

---

## Cloud Connectivity

### High Publish Errors (`BESSPublishErrorsHigh`)

```bash
# Check GCP connectivity
docker exec bessai-gateway python -c "from google.cloud import pubsub_v1; print('OK')"
```

**Note:** The gateway continues operating normally without cloud connectivity.  
Safety and local Prometheus metrics are unaffected.

---

## Docker Compose Commands

```bash
# Start full stack (gateway + monitoring)
docker compose --profile monitoring up -d

# Stop all
docker compose down

# Restart gateway only
docker compose restart bessai-gateway

# View live logs
docker compose logs -f bessai-gateway
```

---

## Emergency Procedures

### 1. Emergency Shutdown
```bash
docker compose stop bessai-gateway
# Inverter enters safe state after watchdog timeout
```

### 2. Manual Override (Inverter Panel)
- Huawei SUN2000: Physical ESC button on inverter LCD → Emergency Stop

### 3. Escalation Matrix
| Severity | Response Time | Escalation |
|---|---|---|
| 🔴 Critical (safety breach) | < 15 min | Site engineer + CTO |
| 🟠 High (gateway down) | < 1 hour | On-call engineer |
| 🟡 Medium (cloud disconnected) | < 4 hours | On-call engineer |

See [SECURITY.md](../SECURITY.md) for security incident handling.

---

## Recursos para adopters

| Recurso | Enlace |
|---------|--------|
| Hub de adopción | [ADOPTER_HUB.md](ADOPTER_HUB.md) |
| Onboarding día 0 → 7 | [ONBOARDING_7DAYS.md](ONBOARDING_7DAYS.md) |
| FAQ técnica | [FAQ.md](FAQ.md) |
| Soporte (issue) | [GitHub Issues](https://github.com/bess-solutions/open-bess-edge/issues/new?template=adopter_support.yml) |
