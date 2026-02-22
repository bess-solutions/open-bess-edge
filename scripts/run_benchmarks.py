"""
BESSAI Benchmark Runner
========================
Runs reproducible benchmarks for BESSAI Edge Gateway.

Usage:
    python scripts/run_benchmarks.py --benchmark 001 --cycles 100 --ci
    python scripts/run_benchmarks.py --benchmark 002 --max-sites 50 --ci
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure the repo root is on the path when run as a script
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Benchmark 001 — Gateway Cycle Latency
# ---------------------------------------------------------------------------


async def _run_bench_001_cycle(driver_kwargs: dict) -> dict[str, float]:
    """Run one gateway cycle and return sub-phase timings in milliseconds."""
    from src.drivers.simulator_driver import SimulatorDriver
    from src.core.safety import SafetyGuard
    from src.interfaces.onnx_dispatcher import OnnxDispatcher

    driver = SimulatorDriver()
    await driver.connect()

    timings: dict[str, float] = {}

    # Phase: read_tags
    t0 = time.perf_counter()
    soc = await driver.read_tag("SOC_%")
    power = await driver.read_tag("P_kW")
    temp = await driver.read_tag("T_battery_C")
    alarm = await driver.read_tag("alarm_code")
    timings["read_tags"] = (time.perf_counter() - t0) * 1000

    # Phase: safety_eval
    t0 = time.perf_counter()
    guard = SafetyGuard()
    _ = guard.check_safety({"soc": soc, "temp": temp})
    timings["safety_eval"] = (time.perf_counter() - t0) * 1000

    # Phase: onnx_inference
    t0 = time.perf_counter()
    try:
        dispatcher = OnnxDispatcher()
        model_path = Path("models/dispatch_policy.onnx")
        if model_path.exists():
            _ = dispatcher.run_inference(soc_pct=soc, power_kw=power)
        timings["onnx_inference"] = (time.perf_counter() - t0) * 1000
    except Exception:
        timings["onnx_inference"] = 0.0

    # Phase: publish (simulated serialization only)
    t0 = time.perf_counter()
    _ = json.dumps({
        "schema_version": "1.0",
        "message_type": "telemetry",
        "site_id": "SITE-CL-001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"soc_pct": soc, "power_kw": power, "temperature_c": temp},
    })
    timings["publish"] = (time.perf_counter() - t0) * 1000

    timings["cycle_total"] = sum(timings.values())

    await driver.disconnect()
    return timings


async def benchmark_001(cycles: int = 100, warmup: int = 10) -> dict:
    """Run Benchmark 001: Gateway Cycle Latency."""
    print(f"\n📊 Benchmark 001 — Gateway Cycle Latency ({cycles} cycles)")
    print(f"   Warmup: {warmup} cycles (excluded)")

    all_timings: list[dict[str, float]] = []

    for i in range(cycles + warmup):
        t = await _run_bench_001_cycle({})
        if i >= warmup:
            all_timings.append(t)
        if (i + 1) % 20 == 0:
            print(f"   {i + 1 - warmup}/{cycles} cycles completed...")

    results: dict = {"benchmark": "001", "version": "1.0.0", "cycles": cycles,
                     "timestamp": datetime.now(timezone.utc).isoformat()}

    for phase in ["read_tags", "safety_eval", "onnx_inference", "publish", "cycle_total"]:
        vals = [t[phase] for t in all_timings]
        results[f"{phase}_p50_ms"] = statistics.median(vals)
        results[f"{phase}_p95_ms"] = sorted(vals)[int(len(vals) * 0.95)]
        results[f"{phase}_p99_ms"] = sorted(vals)[int(len(vals) * 0.99)]
        results[f"{phase}_max_ms"] = max(vals)

    print("\n✅ Results:")
    print(f"   cycle_total P50: {results['cycle_total_p50_ms']:.2f}ms")
    print(f"   cycle_total P99: {results['cycle_total_p99_ms']:.2f}ms")
    print(f"   cycle_total MAX: {results['cycle_total_max_ms']:.2f}ms")
    return results


# ---------------------------------------------------------------------------
# Benchmark 002 — Fleet Scalability
# ---------------------------------------------------------------------------


async def benchmark_002(max_sites: int = 50, cycles_per_count: int = 20) -> dict:
    """Run Benchmark 002: Fleet Orchestrator Scalability."""
    print(f"\n📊 Benchmark 002 — Fleet Scalability (up to {max_sites} sites)")

    from src.drivers.simulator_driver import SimulatorDriver
    from src.core.fleet_orchestrator import FleetOrchestrator

    site_counts = [1, 5, 10, 25, 50]
    site_counts = [s for s in site_counts if s <= max_sites]

    results: dict = {"benchmark": "002", "version": "1.0.0",
                     "timestamp": datetime.now(timezone.utc).isoformat()}

    for n in site_counts:
        print(f"   Testing {n} sites...")
        drivers = [SimulatorDriver(site_id=f"SITE-CL-{i:03d}") for i in range(n)]
        for d in drivers:
            await d.connect()

        latencies = []
        for _ in range(cycles_per_count):
            t0 = time.perf_counter()
            await asyncio.gather(*[d.read_tag("SOC_%") for d in drivers])
            latencies.append((time.perf_counter() - t0) * 1000)

        for d in drivers:
            await d.disconnect()

        sorted_lat = sorted(latencies)
        results[f"sites_{n}_cycle_p50_ms"] = statistics.median(latencies)
        results[f"sites_{n}_cycle_p99_ms"] = sorted_lat[int(len(sorted_lat) * 0.99)]
        print(f"   → {n} sites: P50={results[f'sites_{n}_cycle_p50_ms']:.1f}ms "
              f"P99={results[f'sites_{n}_cycle_p99_ms']:.1f}ms")

    return results


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="BESSAI Benchmark Runner")
    parser.add_argument("--benchmark", choices=["001", "002"], required=True)
    parser.add_argument("--cycles", type=int, default=100,
                        help="Number of cycles for benchmark 001")
    parser.add_argument("--max-sites", dest="max_sites", type=int, default=50,
                        help="Max sites for benchmark 002")
    parser.add_argument("--ci", action="store_true",
                        help="CI mode: use fewer cycles for speed")
    parser.add_argument("--output", default=None,
                        help="Output JSON file path")
    args = parser.parse_args()

    if args.ci:
        args.cycles = min(args.cycles, 100)
        args.max_sites = min(args.max_sites, 25)

    if args.benchmark == "001":
        results = asyncio.run(benchmark_001(cycles=args.cycles))
    else:
        results = asyncio.run(benchmark_002(max_sites=args.max_sites))

    output_path = args.output or f"benchmark_{args.benchmark}_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n📁 Results saved to {output_path}")


if __name__ == "__main__":
    main()
