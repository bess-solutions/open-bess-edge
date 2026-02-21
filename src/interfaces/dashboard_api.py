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
  GET /api/v1/schedule     → Optimal 24h arbitrage schedule (CMg forecast)
  GET /api/v1/version      → Software version and build metadata

Auth: Bearer token via DASHBOARD_API_KEY env var (empty = no auth in dev mode)

Usage::

    api = DashboardAPI(port=8080)
    await api.start()
    # ... later:
    await api.stop()
"""

from __future__ import annotations

import mimetypes
import os
import time
from pathlib import Path
from typing import Any

import structlog

from src.interfaces.arbitrage_engine import ArbitrageEngine
from src.interfaces.cmg_predictor import CMgPredictor

# Optional: bessai_arbitrage data-flywheel pipeline (Parquet-backed, cached)
try:
    from bessai_arbitrage import ArbitragePipeline, BessConfig  # type: ignore[import]

    _FLYWHEEL_AVAILABLE = True
except ImportError:
    _FLYWHEEL_AVAILABLE = False
    ArbitragePipeline = None  # type: ignore[assignment,misc]
    BessConfig = None  # type: ignore[assignment,misc]

__all__ = ["DashboardAPI", "DashboardState"]

log = structlog.get_logger(__name__)

VERSION = "1.0.0"  # bumped: data-flywheel integration
BUILD_DATE = "2026-02-20"

try:
    from aiohttp import web
    from aiohttp.web_middlewares import middleware

    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False
    web = None  # type: ignore[assignment]
    middleware = None  # type: ignore[assignment]


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
        self.onnx_dispatch_kw: float | None = None
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

        # Arbitrage Schedule (updated every 15 min)
        self.schedule_node: str = site_id
        self.schedule_last_updated: float = 0.0
        self.schedule_net_clp: float = 0.0
        self.schedule_charge_hours: int = 0
        self.schedule_discharge_hours: int = 0
        self._schedule_dict: dict | None = None

        # Data-Flywheel pipeline (initialised lazily by DashboardAPI)
        self.arbitrage_pipeline: Any | None = None

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
        state: DashboardState | None = None,
        port: int = 8080,
        api_key: str = "",
    ) -> None:
        self.state = state or DashboardState()
        self.port = port
        self.api_key = api_key or os.getenv("DASHBOARD_API_KEY", "")
        self._app: Any | None = None
        self._runner: Any | None = None

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    async def _check_auth(self, request: Any) -> bool:
        """Return True if auth is satisfied (no-op in dev mode)."""
        if not self.api_key:
            return True
        auth = request.headers.get("Authorization", "")
        return bool(auth == f"Bearer {self.api_key}")

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
        return self._json_response(
            {
                "version": VERSION,
                "build_date": BUILD_DATE,
                "project": "BESSAI Edge Gateway",
            }
        )

    async def handle_health(self, request: Any) -> Any:
        return self._json_response(
            {
                "status": "ok" if self.state.is_safe else "degraded",
                "site_id": self.state.site_id,
            }
        )

    async def handle_dashboard(self, request: Any) -> Any:
        """Serve the static dashboard SPA (index.html)."""
        dashboard_dir = Path(__file__).resolve().parents[2] / "dashboard"
        file = dashboard_dir / "index.html"
        if not file.exists():
            return web.Response(text="Dashboard UI not found. Run from project root.", status=404)
        return web.FileResponse(file)

    async def handle_static(self, request: Any) -> Any:
        """Serve CSS/JS assets under /dashboard/static/."""
        filename = request.match_info.get("filename", "")
        dashboard_dir = Path(__file__).resolve().parents[2] / "dashboard"
        file = dashboard_dir / filename
        if not file.exists() or not file.is_file():
            return web.Response(text="Not found", status=404)
        mime, _ = mimetypes.guess_type(str(file))
        return web.FileResponse(file, headers={"Content-Type": mime or "application/octet-stream"})

    async def handle_schedule(self, request: Any) -> Any:
        """Compute and return optimal 24h arbitrage dispatch schedule.

        Primary path: ArbitragePipeline (Parquet-backed, 15-min cache).
        Fallback: ephemeral CMgPredictor (no history, exponential smoothing).
        """
        if not await self._check_auth(request):
            return self._unauthorized()

        import datetime

        current_hour = datetime.datetime.now().hour
        node = dict(request.rel_url.query).get("node", self.state.schedule_node)

        # ── Fast path: return cached result (within 15 min) ────────────────
        if (
            self.state._schedule_dict is not None
            and (time.time() - self.state.schedule_last_updated) < 900
        ):
            return self._json_response(self.state._schedule_dict)

        # ── Primary: data-flywheel ArbitragePipeline ───────────────────────
        if _FLYWHEEL_AVAILABLE and self.state.arbitrage_pipeline is not None:
            try:
                opps = self.state.arbitrage_pipeline.run(force_refresh=False)
                result = {
                    "source": "bessai_arbitrage",
                    "node": node,
                    "computed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "opportunities": [opp.to_dict() for opp in opps],
                    "n_opportunities": len(opps),
                    "best": opps[0].to_dict() if opps else None,
                }
                self.state._schedule_dict = result
                self.state.schedule_last_updated = time.time()
                if opps:
                    self.state.schedule_net_clp = opps[0].ganancia_neta
                    self.state.schedule_charge_hours = (
                        opps[0].ventana_carga.end_hour - opps[0].ventana_carga.start_hour + 1
                    )
                    self.state.schedule_discharge_hours = (
                        opps[0].ventana_descarga.end_hour - opps[0].ventana_descarga.start_hour + 1
                    )
                log.info(
                    "dashboard_api.schedule_flywheel",
                    node=node,
                    n_opportunities=len(opps),
                )
                return self._json_response(result)
            except Exception as exc:
                log.warning(
                    "dashboard_api.schedule_flywheel_error",
                    error=str(exc),
                    fallback="cmg_predictor",
                )

        # ── Fallback: ephemeral CMgPredictor + legacy ArbitrageEngine ──────
        predictor = CMgPredictor(node=node)
        predictor.load()
        forecasts = predictor.predict_next_24h(
            current_hour=current_hour,
            current_cmg=self.state.soc_pct if self.state.soc_pct > 0 else None,
        )

        engine = ArbitrageEngine(
            capacity_kwh=float(request.rel_url.query.get("capacity_kwh", 1000.0)),
            max_power_kw=float(request.rel_url.query.get("max_power_kw", 500.0)),
            node=node,
        )
        schedule = engine.compute(forecasts, current_soc_pct=self.state.soc_pct)

        result = schedule.to_api_dict()
        result["source"] = "cmg_predictor_fallback"
        result["computed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result["predictor_method"] = forecasts[0].method if forecasts else "unknown"

        self.state._schedule_dict = result
        self.state.schedule_last_updated = time.time()
        self.state.schedule_net_clp = schedule.projected_net_clp
        self.state.schedule_charge_hours = schedule.n_charge_hours
        self.state.schedule_discharge_hours = schedule.n_discharge_hours

        log.info(
            "dashboard_api.schedule_fallback",
            node=node,
            net_clp=schedule.projected_net_clp,
        )
        return self._json_response(result)

    async def handle_onnx(self, request: Any) -> Any:
        """ONNX dispatch status."""
        if not await self._check_auth(request):
            return self._unauthorized()
        return self._json_response(
            {
                "available": self.state.onnx_available,
                "dispatch_kw": self.state.onnx_dispatch_kw,
                "inference_ms": round(self.state.onnx_inference_ms, 2),
                "dispatch_count": self.state.onnx_dispatch_count,
            }
        )

    async def handle_ids(self, request: Any) -> Any:
        """AI-IDS status."""
        if not await self._check_auth(request):
            return self._unauthorized()
        return self._json_response(
            {
                "score": round(self.state.ids_score, 4),
                "alert_count": self.state.ids_alert_count,
                "trained": self.state.ids_trained,
                "status": "alarm" if self.state.ids_score > 0.7 else "nominal",
            }
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the aiohttp web server with CORS enabled."""
        if not _AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp not installed. Run: pip install aiohttp")

        @middleware
        async def cors_middleware(request: Any, handler: Any) -> Any:
            """Allow cross-origin requests from the React frontend."""
            if request.method == "OPTIONS":
                resp = web.Response()
            else:
                resp = await handler(request)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            return resp

        # Initialise the data-flywheel pipeline (if bessai_arbitrage is installed)
        if _FLYWHEEL_AVAILABLE and BessConfig is not None and ArbitragePipeline is not None:
            try:
                _data_dir = Path(os.getenv("BESSAI_DATA_DIR", "data/historical"))
                _model_path = Path(os.getenv("BESSAI_MODEL_PATH", "models/price_predictor.onnx"))
                _cfg = BessConfig(
                    capacity_mwh=float(os.getenv("BESS_CAPACITY_MWH", "20")),
                    power_mw=float(os.getenv("BESS_POWER_MW", "10")),
                    efficiency_pct=float(os.getenv("BESS_EFFICIENCY_PCT", "92")),
                    degradation_cost_usd=float(os.getenv("BESS_DEGRADATION_USD", "4.5")),
                )
                self.state.arbitrage_pipeline = ArbitragePipeline(
                    data_dir=_data_dir,
                    model_path=_model_path if _model_path.exists() else None,
                    config=_cfg,
                )
                log.info(
                    "dashboard_api.flywheel_ready",
                    data_dir=str(_data_dir),
                    model=str(_model_path),
                )
            except Exception as exc:
                log.warning("dashboard_api.flywheel_init_failed", error=str(exc))

        self._app = web.Application(middlewares=[cors_middleware])
        self._app.router.add_get("/", self.handle_dashboard)
        self._app.router.add_get("/dashboard", self.handle_dashboard)
        self._app.router.add_get("/{filename:.*\.(?:css|js|ico|png|svg)}", self.handle_static)
        self._app.router.add_get("/api/v1/status", self.handle_status)
        self._app.router.add_get("/api/v1/fleet", self.handle_fleet)
        self._app.router.add_get("/api/v1/carbon", self.handle_carbon)
        self._app.router.add_get("/api/v1/p2p", self.handle_p2p)
        self._app.router.add_get("/api/v1/schedule", self.handle_schedule)
        self._app.router.add_get("/api/v1/onnx", self.handle_onnx)
        self._app.router.add_get("/api/v1/ids", self.handle_ids)
        self._app.router.add_get("/api/v1/version", self.handle_version)
        self._app.router.add_get("/api/v1/health", self.handle_health)
        self._app.router.add_options("/{path_info:.*}", self._cors_preflight)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        log.info("dashboard_api.started", port=self.port, flywheel=_FLYWHEEL_AVAILABLE)

    async def _cors_preflight(self, request: Any) -> Any:
        return web.Response(
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
            }
        )

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    @property
    def is_available(self) -> bool:
        return _AIOHTTP_AVAILABLE
