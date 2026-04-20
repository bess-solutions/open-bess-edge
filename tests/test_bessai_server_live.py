"""
tests/test_bessai_server_live.py
================================
Suite de pruebas en vivo del BESSAIServer.
Requiere que demo_server.py esté corriendo en http://localhost:8000

Ejecutar con:
    python tests/test_bessai_server_live.py
"""
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

# Forzar UTF-8 en stdout para Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000"
PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"


@dataclass
class Result:
    name: str
    ok: bool
    detail: str
    ms: float


results: list[Result] = []


def get(path: str) -> tuple[dict, float]:
    """GET JSON endpoint, retorna (data, elapsed_ms)."""
    t0 = time.monotonic()
    with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as r:
        data = json.loads(r.read())
    return data, (time.monotonic() - t0) * 1000


def check(name: str, passed: bool, detail: str = "", ms: float = 0.0) -> None:
    results.append(Result(name, passed, detail, ms))
    icon = PASS if passed else FAIL
    suffix = f"  ({ms:.0f}ms)" if ms > 0 else ""
    print(f"  {icon}  {name}{suffix}")
    if not passed and detail:
        print(f"         ↳ {detail}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: Estructura del /health
# ─────────────────────────────────────────────────────────────────────────────
def test_health_schema():
    print("\n── TEST 1: Estructura /health ─────────")
    data, ms = get("/health")
    required_keys = ["status", "site_id", "version", "uptime_s", "last_cycle",
                     "safety_status", "compliance_ok", "compliance_score"]
    missing = [k for k in required_keys if k not in data]
    check("Tiene todos los campos requeridos", not missing, f"Faltan: {missing}", ms)
    check("status ∈ {healthy, degraded}", data.get("status") in ("healthy", "degraded"))
    check("uptime_s > 0", data.get("uptime_s", 0) > 0)
    check("last_cycle > 0 (el loop está corriendo)", data.get("last_cycle", 0) > 0)
    check("compliance_score es float [0–100]",
         0.0 <= float(data.get("compliance_score", -1)) <= 100.0)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: Telemetría se actualiza (dinámica)
# ─────────────────────────────────────────────────────────────────────────────
def test_telemetry_is_live():
    print("\n── TEST 2: /api/v1/telemetry es dinámico ─")
    d1, ms1 = get("/api/v1/telemetry")
    print(f"   {INFO} Ciclo 1: SOC={d1.get('soc_pct')}%, P={d1.get('power_kw')}kW")
    time.sleep(6)  # esperar > 5s (un ciclo completo)
    d2, ms2 = get("/api/v1/telemetry")
    print(f"   {INFO} Ciclo 2: SOC={d2.get('soc_pct')}%, P={d2.get('power_kw')}kW")
    changed = d1.get("soc_pct") != d2.get("soc_pct") or d1.get("power_kw") != d2.get("power_kw")
    check("Los valores cambian entre ciclos (datos vivos)", changed,
         f"SOC: {d1.get('soc_pct')} → {d2.get('soc_pct')}")
    check("soc_pct está en rango [0, 100]",
         0.0 <= float(d2.get("soc_pct", -1)) <= 100.0)
    check("timestamp_utc presente en respuesta", "timestamp_utc" in d2)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: Compliance report tiene los 11 GAPs
# ─────────────────────────────────────────────────────────────────────────────
def test_compliance_report():
    print("\n── TEST 3: /compliance/report ──────────")
    data, ms = get("/compliance/report")
    check("Tiene 11 GAPs", data.get("gaps_checked") == 11, ms=ms)
    gaps = data.get("gaps", {})
    check("GAPs van de GAP-001 a GAP-011",
         all(f"GAP-{str(i).zfill(3)}" in gaps for i in range(1, 12)))
    check("norm_ref menciona NTSyCS", "NTSyCS" in data.get("norm_ref", ""))
    check("generated_at_utc presente", "generated_at_utc" in data)
    check("report_type = NTSyCS_COMPLIANCE_REPORT",
         data.get("report_type") == "NTSyCS_COMPLIANCE_REPORT")
    print(f"   {INFO} Estado: {data.get('overall_status')} — Score: {data.get('compliance_score')}")
    if data.get("violations"):
        print(f"   {INFO} Violaciones activas: {data['violations']}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: Fleet — 3 sitios presentes
# ─────────────────────────────────────────────────────────────────────────────
def test_fleet():
    print("\n── TEST 4: /fleet/* ─────────────────────")
    summary, ms = get("/fleet/summary")
    check("n_sites = 3", summary.get("n_sites") == 3, ms=ms)
    check("total_capacity_kwh = 600", summary.get("total_capacity_kwh") == 600.0)
    check("fleet_soc_pct en rango [0, 100]",
         0.0 <= float(summary.get("fleet_soc_pct", -1)) <= 100.0)
    print(f"   {INFO} Fleet SOC: {summary.get('fleet_soc_pct')}% | "
          f"Disponible: {summary.get('total_available_kw')} kW | "
          f"Alarmas: {summary.get('sites_in_alarm')}")

    sites, _ = get("/fleet/sites")
    check("Retorna lista de 3 sitios", len(sites) == 3)
    site_ids = [s.get("site_id") for s in sites]
    check("Sitios: DEMO-CL-001/002/003 presentes",
         "DEMO-CL-001" in site_ids and "DEMO-CL-003" in site_ids)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: 404 para rutas desconocidas
# ─────────────────────────────────────────────────────────────────────────────
def test_404():
    print("\n── TEST 5: Manejo de rutas desconocidas ──")
    try:
        urllib.request.urlopen(f"{BASE}/ruta/que/no/existe", timeout=5)
        check("Ruta desconocida retorna 404", False, "Debería haber fallado")
    except urllib.error.HTTPError as e:
        check("Ruta desconocida retorna 404", e.code == 404, f"Got {e.code}")
    except Exception as e:
        check("404 handler activo", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: Carga concurrente — 20 requests simultáneos
# ─────────────────────────────────────────────────────────────────────────────
def test_concurrent_load():
    print("\n── TEST 6: Carga concurrente (20 requests) ──")
    N = 20
    endpoint = "/health"
    responses = []
    errors = []
    timings = []

    def hit():
        try:
            d, ms = get(endpoint)
            responses.append(d)
            timings.append(ms)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=hit) for _ in range(N)]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total_ms = (time.monotonic() - t0) * 1000

    check(f"Todas las {N} requests completaron", len(responses) == N,
         f"{len(errors)} errores: {errors[:2]}")
    check("Cero errores bajo carga", len(errors) == 0, f"Errores: {errors}")
    avg_ms = sum(timings) / len(timings) if timings else 0
    p99_ms = sorted(timings)[-1] if timings else 0
    check(f"Latencia promedio < 200ms (got {avg_ms:.0f}ms)", avg_ms < 200)
    check(f"P99 < 500ms (got {p99_ms:.0f}ms)", p99_ms < 500)
    print(f"   {INFO} {N} requests en {total_ms:.0f}ms | avg={avg_ms:.0f}ms | p99={p99_ms:.0f}ms")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7: Compliance violation activa cuando SOC < 25%
# ─────────────────────────────────────────────────────────────────────────────
def test_compliance_violation_scenario():
    print("\n── TEST 7: Escenario de violación de compliance ──")
    # El sim va ligeramente bajo 25% ~cada 30 ciclos (cada 2.5 min)
    # Tomamos el estado actual y verificamos que el report es coherente
    health, _ = get("/health")
    status, _ = get("/compliance/status")

    # Los dos endpoints deben ser coherentes entre sí
    health_ok = health.get("compliance_ok")
    status_ok = status.get("status") == "compliant"
    check("compliance_ok en /health coincide con /compliance/status",
         health_ok == status_ok,
         f"/health: {health_ok}, /compliance/status: {status.get('status')}")

    report, _ = get("/compliance/report")
    check("overall_status en /compliance/report es coherente",
         (health_ok and report.get("overall_status") == "COMPLIANT") or
         (not health_ok and report.get("overall_status") == "NON_COMPLIANT"))

    if not health_ok:
        check("Hay violaciones listadas cuando score < 100",
             len(report.get("violations", [])) > 0)
        print(f"   {INFO} Violación activa: {report.get('violations', ['?'])[0]}")
    else:
        print(f"   {INFO} Sistema compliant en este momento (score: {health.get('compliance_score')})")
        check("violations = [] cuando compliant", report.get("violations") == [])


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8: /metrics tiene formato Prometheus
# ─────────────────────────────────────────────────────────────────────────────
def test_prometheus_metrics():
    print("\n── TEST 8: /metrics formato Prometheus ──")
    t0 = time.monotonic()
    with urllib.request.urlopen(f"{BASE}/metrics", timeout=5) as r:
        content_type = r.headers.get("Content-Type", "")
        text = r.read().decode()
    ms = (time.monotonic() - t0) * 1000

    check("Content-Type es text/plain", "text/plain" in content_type, ms=ms)
    check("Contiene bess_cycles_total", "bess_cycles_total" in text)
    check("Contiene bess_safety_blocks_total", "bess_safety_blocks_total" in text)
    check("Contiene bess_last_soc_percent", "bess_last_soc_percent" in text)
    check("Contiene bess_gateway_info", "bess_gateway_info" in text)
    lines_with_data = [l for l in text.split("\n") if l and not l.startswith("#")]
    print(f"   {INFO} {len(lines_with_data)} series de métricas activas")


# ─────────────────────────────────────────────────────────────────────────────
# RESUMEN
# ─────────────────────────────────────────────────────────────────────────────
def print_summary():
    print("\n" + "=" * 55)
    print("  RESUMEN")
    print("=" * 55)
    passed = sum(1 for r in results if r.ok)
    failed = [r for r in results if not r.ok]
    total = len(results)
    print(f"  Total: {total} | PASS: {passed} | FAIL: {len(failed)}")
    if failed:
        print("\n  Fallos:")
        for f in failed:
            print(f"    ✗ {f.name}: {f.detail}")
    rate = passed / total * 100 if total else 0
    print(f"\n  Tasa de éxito: {rate:.0f}%")
    print("=" * 55)


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  BESSAI Edge Gateway — Live Test Suite v2.15.0")
    print(f"  Servidor: {BASE}")
    print("=" * 55)

    try:
        test_health_schema()
        test_telemetry_is_live()
        test_compliance_report()
        test_fleet()
        test_404()
        test_concurrent_load()
        test_compliance_violation_scenario()
        test_prometheus_metrics()
    except Exception as e:
        print(f"\n{FAIL} Error fatal en test suite: {e}")
        import traceback
        traceback.print_exc()

    print_summary()
