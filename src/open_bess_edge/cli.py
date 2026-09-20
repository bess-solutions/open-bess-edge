"""Interfaz de línea de comandos: ``open-bess-edge``."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

from . import __version__
from .config import EdgeConfig, load_config, reference_config
from .errors import OpenBessEdgeError
from .modbus.profile import list_profiles, load_profile
from .runtime.audit import verify_chain
from .runtime.factory import build_node
from .runtime.health import HealthServer


def _setup_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def _run(cfg: EdgeConfig, base_dir: Path | None) -> int:
    node = build_node(cfg, base_dir=base_dir)
    ok = await node.start(timeout_s=max(5.0, cfg.modbus.timeout_s * 4))
    health = None
    if cfg.health.enabled:
        health = HealthServer(node, cfg.health.host, cfg.health.port, cfg.health.reset_token)
        await health.start()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, node.request_stop)
        except NotImplementedError:  # pragma: no cover (Windows)
            pass
    if not ok:
        logging.getLogger("open_bess_edge").error(
            "sin conexión al arranque: el nodo permanece en SAFE_STATE y reintentará en segundo plano")
    try:
        await node.run()
    finally:
        if health:
            await health.stop()
        await node.stop()
    return 0


async def _simulate(cfg: EdgeConfig, duration: float) -> int:
    from .sim.runner import SimEnvironment  # noqa: PLC0415

    env = SimEnvironment(cfg)
    env.plant.f_profile = lambda t: 50.0 if t < 3.0 else (49.65 if t < 8.0 else 50.0)
    port = await env.start()
    node = build_node(cfg, host="127.0.0.1", port=port)
    await node.start()
    print(f"Simulación: planta {cfg.plant.p_nominal_kw:.0f} kW / {cfg.plant.e_nominal_kwh:.0f} kWh, "
          f"Modbus TCP 127.0.0.1:{port}")
    print("  t<3 s: 50.00 Hz | 3-8 s: 49.65 Hz (contingencia) | >8 s: 50.00 Hz")
    task = asyncio.ensure_future(node.run())
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    while loop.time() - t0 < duration:
        await asyncio.sleep(1.0)
        r = node.last_result
        if r:
            print(f"t={loop.time()-t0:4.1f}s  estado={r.state:<10} f={r.f_hz}  P_cons={r.p_setpoint_kw:8.1f} kW  "
                  f"P_med={0 if r.p_measured_kw is None else r.p_measured_kw:8.1f} kW  ffr={r.ffr_status}  lat={r.latency_ms:.2f} ms")
    node.request_stop()
    await task
    await node.stop()
    await env.stop()
    m = node.metrics
    print(f"ciclos={m.cycles} overruns={m.overruns} p99_lat={m.percentile(0.99):.2f} ms max={m.latency_ms_max:.2f} ms")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="open-bess-edge", description="Open BESS Edge — gateway de borde para BESS")
    ap.add_argument("--log-level", default="INFO")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="ejecutar el nodo")
    r.add_argument("--config", "-c", type=Path, default=None)
    c = sub.add_parser("check-config", help="validar un archivo de configuración y su perfil")
    c.add_argument("config", type=Path)
    s = sub.add_parser("simulate", help="simulación completa (planta + Modbus TCP + nodo)")
    s.add_argument("--config", "-c", type=Path, default=None)
    s.add_argument("--duration", type=float, default=12.0)
    pi = sub.add_parser("profile-info", help="capacidades de un perfil de dispositivo")
    pi.add_argument("profile", nargs="?")
    v = sub.add_parser("verify-audit", help="verificar la cadena de hash de la auditoría")
    v.add_argument("files", nargs="+", type=Path)
    sub.add_parser("version")
    a = ap.parse_args(argv)
    _setup_logging(a.log_level)

    try:
        if a.cmd == "version":
            print(__version__)
            return 0
        if a.cmd == "verify-audit":
            ok, msg = verify_chain(a.files)
            print(("OK: " if ok else "FALLO: ") + msg)
            return 0 if ok else 2
        if a.cmd == "profile-info":
            if not a.profile:
                for n in list_profiles():
                    print(n)
                return 0
            p = load_profile(a.profile)
            print(json.dumps({
                "name": p.name, "manufacturer": p.manufacturer, "model": p.model,
                "verification": p.verification_level, "telemetry_signals": list(p.telemetry_signals),
                "can_control_p": p.can_control_p, "can_control_q": p.can_control_q, "heartbeat": p.has_heartbeat,
                "mode": "control" if p.can_control_p else "monitor-only"}, indent=2, ensure_ascii=False))
            return 0
        if a.cmd == "check-config":
            cfg = load_config(a.config)
            p = load_profile(cfg.modbus.profile, a.config.parent)
            print(f"Configuración válida. Perfil '{p.name}' ({p.verification_level}); "
                  f"control P={p.can_control_p} Q={p.can_control_q}")
            return 0
        if a.cmd == "simulate":
            cfg = load_config(a.config) if a.config else reference_config()
            return asyncio.run(_simulate(cfg, a.duration))
        if a.cmd == "run":
            cfg = load_config(a.config)
            return asyncio.run(_run(cfg, a.config.parent if a.config else None))
    except OpenBessEdgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
