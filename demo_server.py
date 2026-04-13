"""
demo_server.py — BESSAIServer Demo Standalone
==============================================
Levanta el BESSAIServer en puerto 8000 con datos simulados actualizándose cada 5 segundos.
No requiere Docker, GCP, ni hardware real.

Uso:
    python demo_server.py

Endpoints disponibles:
    http://localhost:8000/health
    http://localhost:8000/metrics
    http://localhost:8000/compliance/status
    http://localhost:8000/compliance/report
    http://localhost:8000/fleet/summary
    http://localhost:8000/fleet/sites
    http://localhost:8000/api/v1/telemetry
"""
import asyncio
import math
import random
import time

from src.interfaces.metrics import CARBON_VIABILITY_SCORE, FLEET_LATENCY_MS
from src.interfaces.server import BESSAIServer


async def simulate_loop(server: BESSAIServer) -> None:
    """Simula el loop de 5 segundos del gateway con datos realistas."""
    cycle = 0
    start = time.monotonic()

    while True:
        cycle += 1
        elapsed = time.monotonic() - start
        hour = (elapsed / 3600) % 24  # hora simulada (avanza rápido)

        # SOC oscila entre 20% y 90% siguiendo una curva sinusoidal
        soc = 55.0 + 35.0 * math.sin(elapsed / 30.0)
        soc = max(20.0, min(90.0, soc))

        # Potencia: carga durante precio bajo, descarga durante peak
        power_kw = 45.0 * math.sin(elapsed / 20.0 + 1.0)

        # Temperatura ligeramente variable
        temp_c = 28.0 + 2.0 * math.sin(elapsed / 60.0)

        # Simular compliance: todo OK salvo que el SOC baje de 25%
        compliance_ok = soc > 25.0
        violations = [] if compliance_ok else ["GAP-004: SOC below minimum threshold"]
        score = 100.0 if compliance_ok else 63.6  # 7/11 GAPs OK

        # Actualizar el servidor
        server.set_cycle(cycle, ok=True, safety_status="ok")
        server.set_compliance_state(
            all_ok=compliance_ok,
            score=score,
            violations=violations,
            cycle=cycle,
        )
        server.set_telemetry({
            "site_id": "DEMO-CL-001",
            "soc_pct": round(soc, 1),
            "p_kw": round(power_kw, 2),
            "temp_c": round(temp_c, 1),
            "safety_ok": compliance_ok,
        })

        # Fleet simulado: 3 sitios
        class FakeFleet:
            n_sites = 3
            total_capacity_kwh = 600.0
            fleet_soc_pct = round(soc * 0.95, 1)
            total_available_kw = round(abs(power_kw) * 2.5, 1)
            sites_in_alarm = 0 if compliance_ok else 1

        server.set_fleet_summary(FakeFleet())
        server.set_site_telemetries([
            {"site_id": "DEMO-CL-001", "soc_pct": round(soc, 1), "p_kw": round(power_kw, 2)},
            {"site_id": "DEMO-CL-002", "soc_pct": round(soc * 0.92, 1), "p_kw": round(power_kw * 0.8, 2)},
            {"site_id": "DEMO-CL-003", "soc_pct": round(soc * 1.05, 1), "p_kw": round(power_kw * 1.1, 2)},
        ])

        # Export MOCK Tier-1 Metrics
        # Score entre 1.0 (mal mix) a 3.0 (gran mix)
        carbon_score = random.uniform(2.1, 2.9) if compliance_ok else random.uniform(0.5, 1.8)
        CARBON_VIABILITY_SCORE.labels(site_id="DEMO-CL-001", region="CL").set(carbon_score)

        # Latency
        # P99 base de ~20-30ms, si falla compliance inyectamos picos simulados de > 100ms
        latency = random.uniform(15.0, 35.0) if compliance_ok else random.uniform(90.0, 150.0)
        FLEET_LATENCY_MS.labels(site_id="DEMO-CL-001", operation="fleet_sync").observe(latency)

        # Log de ciclo
        direction = "(UP) cargando" if power_kw < 0 else "(DOWN) descargando"
        status = "[OK] COMPLIANT" if compliance_ok else "[!] VIOLATION"
        print(f"  Ciclo {cycle:04d} | SOC: {soc:.1f}% | P: {power_kw:+.1f} kW {direction} | {status}")

        await asyncio.sleep(5.0)


async def main() -> None:
    server = BESSAIServer(
        site_id="DEMO-CL-001",
        version="v2.17.1-demo",
        port=8000,
    )

    print("=" * 60)
    print("  BESSAI Edge Gateway — Demo Server v2.17.1 (Tier-1)")
    print("=" * 60)
    print()
    print("  Endpoints disponibles:")
    print("    http://localhost:8000/health")
    print("    http://localhost:8000/metrics")
    print("    http://localhost:8000/compliance/status")
    print("    http://localhost:8000/compliance/report")
    print("    http://localhost:8000/fleet/summary")
    print("    http://localhost:8000/fleet/sites")
    print("    http://localhost:8000/api/v1/telemetry")
    print()
    print("  Actualizando cada 5 segundos. Ctrl+C para salir.")
    print("-" * 60)

    async with server.run():
        await simulate_loop(server)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  Gateway detenido.")
