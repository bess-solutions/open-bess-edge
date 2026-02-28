#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
scripts/pilot_setup.py
=======================
BESSAI Pilot Site Setup — Interactive configuration wizard.

Validates environment variables, checks connectivity to BESS hardware,
and generates a readiness report before the first production deployment.

Usage:
    python scripts/pilot_setup.py --site-id SITE-CL-001 --inverter-ip 192.168.1.100

Or interactively:
    python scripts/pilot_setup.py
"""

import argparse
import os
import sys
import socket
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "config" / ".env"
ENV_EXAMPLE = ROOT / ".env.example"


def _check(label: str, ok: bool, detail: str = "") -> bool:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {label}" + (f" — {detail}" if detail else ""))
    return ok


def check_env_file() -> bool:
    if ENV_FILE.exists():
        return _check("config/.env exists", True)
    else:
        _check("config/.env exists", False, "Run: cp .env.example config/.env && edit values")
        return False


def check_required_vars(required: list[str]) -> bool:
    """Load .env and check required vars are set."""
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    # Merge OS env
    env.update(os.environ)

    all_ok = True
    for var in required:
        val = env.get(var, "")
        ok = bool(val and val not in ("", "None", "null"))
        if not _check(f"${var}", ok, val[:30] + "..." if len(val) > 30 else val):
            all_ok = False
    return all_ok


def check_inverter_connectivity(host: str, port: int = 502, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return _check(f"Inverter {host}:{port} reachable", True)
    except OSError as exc:
        return _check(f"Inverter {host}:{port} reachable", False, str(exc))


def check_certs() -> bool:
    cert = ROOT / "infrastructure" / "certs" / "client.crt"
    key  = ROOT / "infrastructure" / "certs" / "client.key"
    ca   = ROOT / "infrastructure" / "certs" / "ca.crt"

    ok_cert = _check("client.crt exists", cert.exists(),
                     "Run: bash infrastructure/certs/gen_certs.sh" if not cert.exists() else "")
    ok_key  = _check("client.key exists", key.exists())
    ok_ca   = _check("ca.crt exists", ca.exists())
    return ok_cert and ok_key and ok_ca


def check_python_deps() -> bool:
    required_pkgs = ["structlog", "pydantic_settings", "pymodbus"]
    all_ok = True
    for pkg in required_pkgs:
        try:
            __import__(pkg)
            _check(f"Python: {pkg}", True)
        except ImportError:
            _check(f"Python: {pkg}", False, f"pip install {pkg}")
            all_ok = False
    return all_ok


def generate_readiness_report(results: dict[str, bool], site_id: str) -> None:
    all_ok = all(results.values())
    score = int(sum(results.values()) / len(results) * 100)

    print()
    print("=" * 56)
    print(f"  BESSAI Pilot Readiness Report — {site_id}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Score: {score}/100 — {'✅ READY FOR PILOT' if all_ok else '⚠️  NOT READY'}")
    print("=" * 56)

    if not all_ok:
        print()
        print("  Blocking issues:")
        for check, ok in results.items():
            if not ok:
                print(f"    ❌ {check}")
        print()
        print("  Fix these issues before deploying to production.")
        sys.exit(1)
    else:
        print()
        print("  All checks passed. Start the gateway with:")
        print("    python -m src.core.main")
        print("  Or with Docker:")
        print("    docker compose up -d")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="BESSAI Pilot Site Setup Check")
    parser.add_argument("--site-id", default=os.getenv("SITE_ID", "SITE-CL-001"))
    parser.add_argument("--inverter-ip", default=os.getenv("INVERTER_IP", ""))
    parser.add_argument("--inverter-port", type=int, default=502)
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║     BESSAI Edge Gateway — Pilot Site Setup Check     ║")
    print(f"║     Site: {args.site_id:<43}║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    results: dict[str, bool] = {}

    print("─── Config ───────────────────────────────────────────")
    results["config/.env"] = check_env_file()

    print("\n─── Required Environment Variables ───────────────────")
    results["required_vars"] = check_required_vars([
        "SITE_ID", "INVERTER_IP", "BESSAI_P_NOM_KW"
    ])

    print("\n─── mTLS Certificates (CEN GAP-003) ─────────────────")
    results["certs"] = check_certs()

    print("\n─── Python Dependencies ──────────────────────────────")
    results["python_deps"] = check_python_deps()

    if args.inverter_ip:
        print("\n─── Hardware Connectivity ────────────────────────────")
        results["inverter_connectivity"] = check_inverter_connectivity(
            args.inverter_ip, args.inverter_port
        )

    generate_readiness_report(results, args.site_id)


if __name__ == "__main__":
    main()
