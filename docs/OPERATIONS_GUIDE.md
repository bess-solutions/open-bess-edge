# Guía de Operaciones Tier-1 para BESSAI

Esta guía describe los procedimientos operativos para mantener y monitorear el BESSAI Edge Gateway en entornos de producción con alta carga y disponibilidad Tier-1.

## 1. Monitoreo en Grafana
- **Dashboard Principal:** Disponible en la ruta de provisionamiento de su clúster (`bessai_main.json`).
- **Métricas Clave:**
  - `bess_fleet_latency_ms`: Histograma que expone la latencia del `FleetCoordinator`. Un P99 > 100ms es indicador de saturación en el nodo edge.
  - `bess_carbon_viability_score`: Gauge en tiempo real detallando viabilidad de ingresos por compensación. Valores < 2 comprometen la rentabilidad esperada.
  - `bess_injection_kw_capacity`: Exposición contínua de la capacidad liberable instantánea en rampa hacia el VPP.

## 2. Respuesta a Alertas (Prometheus)

| Alerta | Nivel | Acción Recomendada |
| :--- | :--- | :--- |
| **`HighFleetLatency`** | Warning | Revisar conectividad hacia la base de datos de flotas u orquestación local. Si el problema persiste y HPA no logra autoescalar (maxReplicas=10), escalar manualmente los Nodos de Kubernetes. Ejecute `kubectl get hpa bessai-edge`. |
| **`LowCarbonViability`** | Info/Warning | Indicar al despachador financiero escalar compensación en otras plantas. Posible pico en uso de combustibles fósiles en el mix del distribuidor regional. Revisar configuración de `LCAEngine`. |
| **`BESSGatewayDown`** | Critical | Verifique Docker Logs / Pod status (`kubectl logs deployment/bessai-edge`). Reinicie pod de ser necesario. |

## 3. Escalado y Despliegue Manual
A pesar de la configuración nativa de *Horizontal Pod Autoscaler* referenciada en Helm, un operador puede sobre-escribir escalar forzosamente el front de métricas:

```bash
# Sobrescribir HPA ante picos programados 
kubectl scale deployment bessai-edge --replicas=15
```

## 4. Pruebas de Carga 
Para simular comportamientos límite previo a conectar un nuevo sitio:
```bash
locust -f tests/load/locustfile.py --headless -u 1000 -r 50 --run-time 2m --csv=results
python scripts/analyze_locust.py results_stats.csv
```
El script generará las alertas pertinentes si el P99 sobrepasa los 100ms.
