"""
standalone_api.py
=================
Run the BESSAI DashboardAPI as a standalone REST server — no IoT loop required.

This lets the React frontend (bess-arbitrage-visualizer) talk to the backend
without having to spin up the full Edge Gateway.

Usage
-----
    python standalone_api.py

Environment variables (optional, see .env.example):
    BESSAI_DATA_DIR       Path to Parquet data directory (default: data/historical)
    BESSAI_MODEL_PATH     Path to ONNX model (default: models/price_predictor.onnx)
    BESS_CAPACITY_MWH     Battery capacity in MWh (default: 20)
    BESS_POWER_MW         Battery max power in MW (default: 10)
    BESS_EFFICIENCY_PCT   Round-trip efficiency % (default: 92)
    BESS_DEGRADATION_USD  Degradation cost per cycle in USD (default: 4.5)
    DASHBOARD_API_KEY     Bearer token for auth (empty = dev mode, no auth)
    DASHBOARD_PORT        Port to listen on (default: 8080)

Endpoints
---------
    GET /api/v1/schedule   Optimal 24h arbitrage opportunities
    GET /api/v1/status     Site telemetry snapshot
    GET /api/v1/health     Health check
    GET /api/v1/version    Version info
    GET /api/v1/carbon     LCA carbon metrics
    GET /api/v1/fleet      Fleet KPIs
    GET /api/v1/onnx       ONNX dispatch status
    GET /api/v1/ids        AI-IDS status

Press Ctrl+C to stop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Make sure the package root is on sys.path when running from the repo root
sys.path.insert(0, str(Path(__file__).parent))

import structlog

from src.interfaces.dashboard_api import DashboardAPI, DashboardState

logging.basicConfig(level=logging.INFO)
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="%H:%M:%S"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger("bessai.standalone")


async def main() -> None:
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    api_key = os.getenv("DASHBOARD_API_KEY", "")

    state = DashboardState(site_id=os.getenv("SITE_ID", "bessai-local"))
    api = DashboardAPI(state=state, port=port, api_key=api_key)

    await api.start()

    log.info(
        "bessai.standalone.ready",
        url=f"http://localhost:{port}/api/v1/schedule",
        auth="enabled" if api_key else "dev-mode (no auth)",
    )
    print(f"\n  [OK]  BESSAI API en  http://localhost:{port}")
    print(f"  [>>]  Schedule:      http://localhost:{port}/api/v1/schedule")
    print(f"  [+]   Health:        http://localhost:{port}/api/v1/health")
    print("\n  Presiona Ctrl+C para detener.\n")


    try:
        # Run until interrupted
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await api.stop()
        log.info("bessai.standalone.stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
