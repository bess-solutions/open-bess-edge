#!/usr/bin/env python3
"""
open-bess-edge/src/services/metrics_prometheus.py
==============================================================================
Servicio de Métricas Prometheus para Open BESS Edge
==============================================================================
Expone métricas de:
  - Latencia de lazo de control
  - Disparos de seguridad
  - Tiempo de respuesta FFR
  - Errores de comunicación Modbus
  - Estado de batería (SOC, temperatura, imbalance)
  - Salud del sistema

Integración con Prometheus scraper en puerto 8001/metrics
==============================================================================
"""

from dataclasses import dataclass
from typing import Optional
import time


@dataclass
class EdgeNodeMetrics:
    """
    Colección de métricas Prometheus para Open BESS Edge.
    
    Nota: Implementación compatible con prometheus_client library.
    Si prometheus_client no está disponible, proporciona fallback dict-based.
    """
    
    def __init__(self):
        """Inicializar métricas (con graceful fallback si prometheus_client no disponible)."""
        try:
            import prometheus_client as prom
            self.prometheus_available = True
        except ImportError:
            self.prometheus_available = False
            print("⚠️  prometheus_client no disponible - usando fallback dict-based")
        
        if self.prometheus_available:
            self._init_prometheus_metrics()
        else:
            self._init_fallback_metrics()
    
    def _init_prometheus_metrics(self):
        """Inicializar métricas reales Prometheus."""
        import prometheus_client as prom
        
        # Histogramas
        self.cycle_latency_ms = prom.Histogram(
            "bess_edge_cycle_latency_ms",
            "Latencia de ciclo de control (ms)",
            buckets=[0.05, 0.1, 0.15, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        self.ffr_response_time_ms = prom.Histogram(
            "bess_edge_ffr_response_time_ms",
            "Tiempo de respuesta FFR ante contingencia (ms)",
            buckets=[10, 50, 100, 200, 300, 400, 500]
        )
        
        # Contadores
        self.safety_trip_count = prom.Counter(
            "bess_edge_safety_trip_count_total",
            "Contador de disparos de seguridad",
            labelnames=["fault_code"]
        )
        
        self.modbus_errors_count = prom.Counter(
            "bess_edge_modbus_errors_total",
            "Errores de comunicación Modbus",
            labelnames=["error_type", "device"]
        )
        
        # Gauges
        self.soc_pct = prom.Gauge(
            "bess_edge_soc_percent",
            "State of Charge de baterías (%)"
        )
        
        self.soh_pct = prom.Gauge(
            "bess_edge_soh_percent",
            "State of Health de baterías (%)"
        )
        
        self.p_setpoint_kw = prom.Gauge(
            "bess_edge_p_setpoint_kw",
            "Consigna de potencia activa (kW)"
        )
        
        self.q_setpoint_kvar = prom.Gauge(
            "bess_edge_q_setpoint_kvar",
            "Consigna de potencia reactiva (kVAR)"
        )
        
        self.f_measured_hz = prom.Gauge(
            "bess_edge_f_measured_hz",
            "Frecuencia de red medida (Hz)"
        )
        
        self.v_measured_v = prom.Gauge(
            "bess_edge_v_measured_v",
            "Tensión de red medida (V)"
        )
        
        self.cell_v_imbalance_mv = prom.Gauge(
            "bess_edge_cell_v_imbalance_mv",
            "Desbalance de voltaje entre celdas (mV)"
        )
        
        self.cell_temp_max_c = prom.Gauge(
            "bess_edge_cell_temp_max_c",
            "Temperatura máxima de celda (°C)"
        )
        
        self.dc_isolation_kohm = prom.Gauge(
            "bess_edge_dc_isolation_kohm",
            "Aislamiento DC (kΩ)"
        )
        
        self.modbus_connection_status = prom.Gauge(
            "bess_edge_modbus_connection_status",
            "Estado de conexión Modbus (1=conectado, 0=desconectado)"
        )
        
        self.control_loop_uptime_s = prom.Counter(
            "bess_edge_uptime_seconds_total",
            "Tiempo de operación acumulativo (segundos)"
        )
    
    def _init_fallback_metrics(self):
        """Fallback: almacenar métricas en dicts si prometheus_client no disponible."""
        self.metrics_dict = {
            "cycle_latencies": [],  # Lista de últimas latencias
            "safety_trips": {},  # Counter por fault_code
            "modbus_errors": {},  # Counter por error_type
            "gauges": {
                "soc_pct": 0.0,
                "soh_pct": 0.0,
                "p_setpoint_kw": 0.0,
                "q_setpoint_kvar": 0.0,
                "f_measured_hz": 50.0,
                "v_measured_v": 400.0,
                "cell_v_imbalance_mv": 0.0,
                "cell_temp_max_c": 25.0,
                "dc_isolation_kohm": 1000.0,
                "modbus_connection_status": 0,
            },
            "uptime_start_ts": time.time(),
        }
    
    def record_cycle_latency(self, latency_ms: float):
        """Registrar latencia de ciclo."""
        if self.prometheus_available:
            self.cycle_latency_ms.observe(latency_ms)
        else:
            self.metrics_dict["cycle_latencies"].append(latency_ms)
            # Mantener solo últimas 1000 muestras
            if len(self.metrics_dict["cycle_latencies"]) > 1000:
                self.metrics_dict["cycle_latencies"] = self.metrics_dict["cycle_latencies"][-1000:]
    
    def record_safety_trip(self, fault_code: str):
        """Registrar disparo de seguridad."""
        if self.prometheus_available:
            self.safety_trip_count.labels(fault_code=fault_code).inc()
        else:
            self.metrics_dict["safety_trips"][fault_code] = self.metrics_dict["safety_trips"].get(fault_code, 0) + 1
    
    def record_modbus_error(self, error_type: str, device: str = "pcs"):
        """Registrar error Modbus."""
        if self.prometheus_available:
            self.modbus_errors_count.labels(error_type=error_type, device=device).inc()
        else:
            key = f"{error_type}_{device}"
            self.metrics_dict["modbus_errors"][key] = self.metrics_dict["modbus_errors"].get(key, 0) + 1
    
    def set_soc(self, soc_pct: float):
        """Actualizar SOC."""
        if self.prometheus_available:
            self.soc_pct.set(soc_pct)
        else:
            self.metrics_dict["gauges"]["soc_pct"] = soc_pct
    
    def set_soh(self, soh_pct: float):
        """Actualizar SOH."""
        if self.prometheus_available:
            self.soh_pct.set(soh_pct)
        else:
            self.metrics_dict["gauges"]["soh_pct"] = soh_pct
    
    def set_p_setpoint(self, p_kw: float):
        """Actualizar consigna de potencia activa."""
        if self.prometheus_available:
            self.p_setpoint_kw.set(p_kw)
        else:
            self.metrics_dict["gauges"]["p_setpoint_kw"] = p_kw
    
    def set_q_setpoint(self, q_kvar: float):
        """Actualizar consigna de potencia reactiva."""
        if self.prometheus_available:
            self.q_setpoint_kvar.set(q_kvar)
        else:
            self.metrics_dict["gauges"]["q_setpoint_kvar"] = q_kvar
    
    def set_frequency(self, f_hz: float):
        """Actualizar frecuencia de red medida."""
        if self.prometheus_available:
            self.f_measured_hz.set(f_hz)
        else:
            self.metrics_dict["gauges"]["f_measured_hz"] = f_hz
    
    def set_voltage(self, v_v: float):
        """Actualizar tensión de red medida."""
        if self.prometheus_available:
            self.v_measured_v.set(v_v)
        else:
            self.metrics_dict["gauges"]["v_measured_v"] = v_v
    
    def set_cell_imbalance(self, dv_mv: float):
        """Actualizar desbalance de voltaje de celdas."""
        if self.prometheus_available:
            self.cell_v_imbalance_mv.set(dv_mv)
        else:
            self.metrics_dict["gauges"]["cell_v_imbalance_mv"] = dv_mv
    
    def set_cell_temp_max(self, t_c: float):
        """Actualizar temperatura máxima de celda."""
        if self.prometheus_available:
            self.cell_temp_max_c.set(t_c)
        else:
            self.metrics_dict["gauges"]["cell_temp_max_c"] = t_c
    
    def set_dc_isolation(self, r_kohm: float):
        """Actualizar aislamiento DC."""
        if self.prometheus_available:
            self.dc_isolation_kohm.set(r_kohm)
        else:
            self.metrics_dict["gauges"]["dc_isolation_kohm"] = r_kohm
    
    def set_modbus_connected(self, connected: bool):
        """Actualizar estado de conexión Modbus."""
        status = 1 if connected else 0
        if self.prometheus_available:
            self.modbus_connection_status.set(status)
        else:
            self.metrics_dict["gauges"]["modbus_connection_status"] = status
    
    def get_metrics_summary(self) -> dict:
        """Obtener resumen de métricas (para fallback o debugging)."""
        if self.prometheus_available:
            # En producción, Prometheus scrapeará directo
            return {"status": "prometheus_enabled"}
        else:
            return self.metrics_dict
    
    def get_latency_stats(self) -> Optional[dict]:
        """Obtener estadísticas de latencia (solo en fallback mode)."""
        if not self.prometheus_available and self.metrics_dict["cycle_latencies"]:
            latencies = self.metrics_dict["cycle_latencies"]
            return {
                "count": len(latencies),
                "min_ms": min(latencies),
                "max_ms": max(latencies),
                "avg_ms": sum(latencies) / len(latencies),
                "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)],
                "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)],
            }
        return None


class PrometheusHTTPServer:
    """
    Servidor HTTP simple para Prometheus scrape.
    Expone métricas en /metrics
    """
    
    def __init__(self, port: int = 8001):
        self.port = port
        self.app = None
    
    async def start(self):
        """Iniciar servidor HTTP de Prometheus."""
        try:
            from aiohttp import web
            import prometheus_client
            
            async def metrics_handler(request):
                """Handler para endpoint /metrics."""
                return web.Response(
                    text=prometheus_client.REGISTRY.generate_latest().decode(),
                    content_type="text/plain; charset=utf-8"
                )
            
            self.app = web.Application()
            self.app.router.add_get('/metrics', metrics_handler)
            runner = web.AppRunner(self.app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', self.port)
            await site.start()
            
            print(f"✅ Prometheus HTTP server started on port {self.port}/metrics")
            
        except ImportError as e:
            print(f"⚠️  Cannot start Prometheus HTTP server: {e}")


if __name__ == "__main__":
    # Demo
    metrics = EdgeNodeMetrics()
    
    # Simular registros
    for i in range(10):
        metrics.record_cycle_latency(0.05 + i * 0.01)
    
    metrics.set_soc(75.5)
    metrics.set_frequency(49.98)
    metrics.record_safety_trip("BESS-GUARD-003")
    
    print("📊 Métricas registradas:")
    summary = metrics.get_metrics_summary()
    print(summary)
    
    stats = metrics.get_latency_stats()
    if stats:
        print("\n⏱️  Estadísticas de Latencia:")
        for key, val in stats.items():
            print(f"  {key}: {val:.3f}")
