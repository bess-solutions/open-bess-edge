"""
src/interfaces/dashboard_api.py
================================
BESSAI Edge Gateway — REST API Dashboard (aiohttp).

Provides a read-only JSON API for real-time edge intelligence:

  GET /api/v1/status       → Full site status (SOC, power, temp, alarms)
  GET /api/v1/fleet        → Fleet KPIs (n_sites, avg_SOC, flex_kW)
  GET /api/v1/carbon       → LCA metrics (CO₂ avoided, EF, trees equivalent)
  GET /api/v1/onnx         → AI dispatch status (last command, conf, latency)
  GET /api/v1/ids          → AI-IDS status (score, alert count, trained)
  GET /api/v1/p2p          → P2P energy credits (count, kWh, pending)
  GET /api/v1/version      → Software version and build metadata

Auth: Bearer token via DASHBOARD_API_KEY env var (empty = no auth in dev mode)

Usage::

    api = DashboardAPI(port=8080)
    await api.start()
    # ... later:
    await api.stop()
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import structlog

__all__ = ["DashboardAPI", "DashboardState"]

log = structlog.get_logger(__name__)

VERSION = "0.9.0"
BUILD_DATE = "2026-02-19"

try:
    from aiohttp import web
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False
    web = None  # type: ignore[assignment]


class DashboardState:
    """Shared state object updated by the main orchestrator loop.

    All fields are safe to read from any async context (no locking needed
    since Python GIL protects simple attribute reads).
    """

    def __init__(self, site_id: str = "edge-001") -> None:
        self.site_id = site_id
        self.started_at: float = time.time()

        # Telemetry (updated every cycle)
        self.soc_pct: float = 0.0
        self.power_kw: float = 0.0
        self.temp_c: float = 25.0
        self.cycle_count: int = 0
        self.last_cycle_ts: float = 0.0
        self.is_safe: bool = True

        # AI-IDS
        self.ids_score: float = 0.0
        self.ids_alert_count: int = 0
        self.ids_trained: bool = False

        # ONNX Dispatcher
        self.onnx_dispatch_kw: Optional[float] = None
        self.onnx_inference_ms: float = 0.0
        self.onnx_dispatch_count: int = 0
        self.onnx_available: bool = False

        # LCA Carbon
        self.co2_avoided_kg: float = 0.0
        self.grid_ef_g_kwh: float = 345.0
        self.equivalent_trees: float = 0.0

        # Fleet
        self.fleet_n_sites: int = 0
        self.fleet_total_capacity_kwh: float = 0.0
        self.fleet_avg_soc_pct: float = 0.0
        self.fleet_available_kw: float = 0.0
        self.fleet_alarms: int = 0

        # P2P
        self.p2p_credits_minted: int = 0
        self.p2p_credits_kwh: float = 0.0
        self.p2p_pending: int = 0

    def to_status_dict(self) -> dict[str, Any]:
        """Full site status snapshot."""
        uptime_s = time.time() - self.started_at
        return {
            "site_id": self.site_id,
            "version": VERSION,
            "uptime_s": round(uptime_s, 1),
            "is_safe": self.is_safe,
            "cycle_count": self.cycle_count,
            "last_cycle_ts": self.last_cycle_ts,
            "telemetry": {
                "soc_pct": round(self.soc_pct, 2),
                "power_kw": round(self.power_kw, 2),
                "temp_c": round(self.temp_c, 1),
            },
            "ids": {
                "score": round(self.ids_score, 4),
                "alert_count": self.ids_alert_count,
                "trained": self.ids_trained,
                "status": "alarm" if self.ids_score > 0.7 else "nominal",
            },
            "onnx": {
                "available": self.onnx_available,
                "dispatch_kw": self.onnx_dispatch_kw,
                "inference_ms": round(self.onnx_inference_ms, 2),
                "dispatch_count": self.onnx_dispatch_count,
            },
        }

    def to_fleet_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "n_sites": self.fleet_n_sites,
            "total_capacity_kwh": round(self.fleet_total_capacity_kwh, 1),
            "avg_soc_pct": round(self.fleet_avg_soc_pct, 1),
            "available_kw": round(self.fleet_available_kw, 1),
            "sites_in_alarm": self.fleet_alarms,
        }

    def to_carbon_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "co2_avoided_kg": round(self.co2_avoided_kg, 3),
            "grid_ef_g_kwh": round(self.grid_ef_g_kwh, 1),
            "equivalent_trees_planted": round(self.equivalent_trees, 2),
            "methodology": "IEA WEO 2024 + IEEE 2030.6 LCA",
        }

    def to_p2p_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "credits_minted": self.p2p_credits_minted,
            "credits_kwh": round(self.p2p_credits_kwh, 3),
            "credits_pending": self.p2p_pending,
        }


class DashboardAPI:
    """Async REST API dashboard for BESSAI edge sites.

    Parameters:
        state:  DashboardState shared with the orchestrator.
        port:   TCP port to listen on (default: 8080).
        api_key: Bearer token for auth (empty = dev mode, no auth).
    """

    def __init__(
        self,
        state: Optional[DashboardState] = None,
        port: int = 8080,
        api_key: str = "",
    ) -> None:
        self.state = state or DashboardState()
        self.port = port
        self.api_key = api_key or os.getenv("DASHBOARD_API_KEY", "")
        self._app: Optional[Any] = None
        self._runner: Optional[Any] = None

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    async def _check_auth(self, request: Any) -> bool:
        """Return True if auth is satisfied (no-op in dev mode)."""
        if not self.api_key:
            return True
        auth = request.headers.get("Authorization", "")
        return auth == f"Bearer {self.api_key}"

    def _json_response(self, data: dict) -> Any:
        return web.Response(
            text=__import__("json").dumps(data, indent=2),
            content_type="application/json",
        )

    def _unauthorized(self) -> Any:
        return web.Response(
            text='{"error": "Unauthorized"}',
            status=401,
            content_type="application/json",
        )

    async def handle_status(self, request: Any) -> Any:
        if not await self._check_auth(request):
            return self._unauthorized()
        return self._json_response(self.state.to_status_dict())

    async def handle_fleet(self, request: Any) -> Any:
        if not await self._check_auth(request):
            return self._unauthorized()
        return self._json_response(self.state.to_fleet_dict())

    async def handle_carbon(self, request: Any) -> Any:
        if not await self._check_auth(request):
            return self._unauthorized()
        return self._json_response(self.state.to_carbon_dict())

    async def handle_p2p(self, request: Any) -> Any:
        if not await self._check_auth(request):
            return self._unauthorized()
        return self._json_response(self.state.to_p2p_dict())

    async def handle_version(self, request: Any) -> Any:
        return self._json_response({
            "version": VERSION,
            "build_date": BUILD_DATE,
            "project": "BESSAI Edge Gateway",
        })

    async def handle_health(self, request: Any) -> Any:
        return self._json_response({
            "status": "ok" if self.state.is_safe else "degraded",
            "site_id": self.state.site_id,
        })

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the aiohttp web server."""
        if not _AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp not installed. Run: pip install aiohttp")

        self._app = web.Application()
        self._app.router.add_get("/api/v1/status", self.handle_status)
        self._app.router.add_get("/api/v1/fleet", self.handle_fleet)
        self._app.router.add_get("/api/v1/carbon", self.handle_carbon)
        self._app.router.add_get("/api/v1/p2p", self.handle_p2p)
        self._app.router.add_get("/api/v1/version", self.handle_version)
        self._app.router.add_get("/api/v1/health", self.handle_health)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        log.info("dashboard_api.started", port=self.port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    @property
    def is_available(self) -> bool:
        return _AIOHTTP_AVAILABLE
