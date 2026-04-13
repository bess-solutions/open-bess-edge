# BESSAI Support Playbook (L2)

Este Runbook proporciona instrucciones de triaje rápido para el equipo de nivel 2 (L2 Support) en operaciones de despliegue y contención de incidentes del Gateway BESSAI-Edge.

## 🛠 Diagnóstico: Alta Latencia (bess_fleet_latency_ms > 100ms)

**Síntoma:** Grafana dispara la alerta `HighFleetLatency` para un `site_id` específico.
**Impacto:** Los setpoints del VPP están experimentando retrasos considerables, arriesgando multas del mercado si la latencia rebasa los tiempos de inercia inyectables.

### Pasos de Mitigación:
1. **Verificar métricas en Grafana**:
   - Acudir al Dashboard `BESSAI Fleet Overview`.
   - Filtrar por `site_id` para aislar el nodo problemático.
2. **Revisar logs de Pod**:
   ```bash
   kubectl logs deployment/bessai-edge --tail=100 | grep -i "latency\|error\|timeout"
   ```
3. **Comprobar cuellos de botella CPU / I/O**:
   ```bash
   kubectl top pods -n bessai-pilot
   ```
   Si la CPU está por encima del 85%, el HPA está asfixiado.
4. **Escalar manualmente (Mitigación Inmediata)**:
   Si HPA está atascado u oscilando:
   ```bash
   kubectl scale deployment bessai-edge --replicas=6 -n bessai-pilot
   ```

## 🔋 Diagnóstico: Aumento de Degradación (bess_battery_degradation)

**Síntoma:** El score de degradación en un sitio escala a >1% drásticamente en menos de 24 horas.
**Causa probable:** Curva de despacho extrema desde el optimizador (SocSwing extremo repetitivo).
### Acción L2:
- Contactar de inmediato con Operaciones (Mercado Técnico).
- Desactivar inyecciones en el bloque afectado mediante Dashboard para aislar celda.

---

## ✅ Checklist Pre-Despliegue

Antes de aplicar un nuevo `helm upgrade`, L2 o DevOps deben ratificar los siguientes checkpoints en `Staging`:

- [ ] Validar `bess_fleet_latency_ms` (p99) <100ms utilizando `analyze_locust.py`.
- [ ] Confirmar `bess_battery_degradation` <1% en la simulación de pre-producción.
- [ ] Revisar alertas preexistentes en Prometheus (`http://prometheus:9090/alerts`) que indiquen inestabilidad.
- [ ] Asegurarse de que el `readinessProbe` local devuelve HTTP 200 en `/metrics`.
