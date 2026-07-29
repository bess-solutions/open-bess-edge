# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/interfaces/server.py
=========================
BESSAI Edge Gateway — Unified API Server v2.14.0

Single aiohttp app that unifies ALL HTTP endpoints on one port:

  GET  /               → redirect → /health
  GET  /health         → liveness + gateway state (200/503)
  GET  /metrics        → Prometheus text exposition
  GET  /compliance/status  → NTSyCS compliance state (200/503)
  GET  /compliance/report  → full JSON audit report for SEC/CEN
  GET  /fleet/summary  → multi-site fleet KPIs (VPP fleet view)
  GET  /fleet/sites    → per-site telemetry array
  GET  /api/v1/telemetry  → last telemetry cycle (JSON)
  POST /api/v1/setpoint   → manual setpoint override (TOTP gated)

Design principles:
  - Zero hard deps beyond aiohttp (already in pyproject.toml)
  - All state injected via setter methods — no globals
  - Graceful degradation: each route catches its own exceptions
  - Structured JSON everywhere; Prometheus text only on /metrics

Usage::

    server = BESSAIServer(site_id="SITE-CL-001", version="2.14.0")
    server.set_compliance_state(all_ok=True, score=100.0, violations=[])
    server.set_fleet_summary(summary)
    async with server.run():
        await acquisition_loop()
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from typing import Any

import structlog
from aiohttp import web

from src.interfaces.metrics import generate_metrics
from src.interfaces.totp_auth import TOTPAuth

__all__ = ["BESSAIServer"]

log = structlog.get_logger(__name__)
_VERSION = "2.14.0"

# Rate limiter storage: IP -> (window_start_time, count)
_RATE_LIMIT_STORE: dict[str, tuple[float, int]] = {}
_MAX_REQUESTS_PER_MIN = 300
# BESSAI Unified Server middleware


@web.middleware
async def _rate_limit_middleware(request: web.Request, handler: Any) -> web.StreamResponse:  # noqa: C901
    # Bypass rate limiting for health and metrics endpoints
    if request.path in ("/health", "/metrics"):
        return await handler(request)

    # Bypass rate limiting if disabled via env var (e.g. for Locust load testing)
    import os

    if os.environ.get("BESSAI_DISABLE_RATE_LIMIT") == "true":
        return await handler(request)

    ip = request.remote or "127.0.0.1"
    now = time.time()

    # Periodic memory cleanup if store grows
    if len(_RATE_LIMIT_STORE) > 1000:
        expired = [k for k, (v_time, _) in _RATE_LIMIT_STORE.items() if now - v_time > 120.0]
        for k in expired:
            _RATE_LIMIT_STORE.pop(k, None)

    window_start, count = _RATE_LIMIT_STORE.get(ip, (now, 0))

    if now - window_start > 60.0:
        _RATE_LIMIT_STORE[ip] = (now, 1)
        return await handler(request)

    if count >= _MAX_REQUESTS_PER_MIN:
        log.warning("server.rate_limit_exceeded", ip=ip)
        return web.Response(
            text=json.dumps(
                {"error": "too_many_requests", "detail": "Rate limit exceeded (300 req/min)"}
            ),
            content_type="application/json",
            status=429,
        )

    _RATE_LIMIT_STORE[ip] = (window_start, count + 1)
    return await handler(request)


@dataclass
class _ComplianceSnapshot:
    all_ok: bool = False
    score: float = 0.0
    violations: list[str] = None  # type: ignore[assignment]
    norm_ref: str = "NTSyCS CEN Chile — 11 GAPs v2.12.0"
    cycle_count: int = 0
    last_updated: float = 0.0

    def __post_init__(self) -> None:
        if self.violations is None:
            self.violations = []


@dataclass
class _FleetSnapshot:
    n_sites: int = 0
    total_capacity_kwh: float = 0.0
    fleet_soc_pct: float = 0.0
    total_available_kw: float = 0.0
    sites_in_alarm: int = 0
    last_updated: float = 0.0


@dataclass
class _TelemetrySnapshot:
    site_id: str = ""
    soc_pct: float = 0.0
    power_kw: float = 0.0
    temp_c: float = 0.0
    f_grid_hz: float = 50.0
    safety_ok: bool = True
    cycle: int = 0
    timestamp: float = 0.0


class BESSAIServer:
    """Unified HTTP server — health + metrics + compliance + fleet.

    Parameters
    ----------
    site_id:
        Unique site identifier (SITE-CL-001 format).
    version:
        Application version string.
    host:
        Bind address (default ``0.0.0.0``).
    port:
        TCP port (default ``8000``).
    """

    def __init__(
        self,
        site_id: str,
        version: str = _VERSION,
        host: str = "0.0.0.0",  # nosec B104
        port: int = 8000,
    ) -> None:
        self._site_id = site_id
        self._version = version
        self._host = host
        self._port = port
        self._start_time = time.monotonic()

        # Mutable state — updated by main loop each cycle
        self.last_cycle_ok: bool = True
        self._compliance = _ComplianceSnapshot()
        self._fleet = _FleetSnapshot()
        self._telemetry = _TelemetrySnapshot(site_id=site_id)
        self._last_cycle_ok: bool = True
        self._last_cycle: int = 0
        self._safety_status: str = "unknown"

        # Per-site telemetry cache (for /fleet/sites)
        self._site_telemetries: list[dict[str, Any]] = []

        # TOTP Authentication verifier
        self._totp_auth = TOTPAuth(site_id=site_id)

        self._app = self._build_app()

    # ------------------------------------------------------------------
    # State setters — called from main acquisition loop
    # ------------------------------------------------------------------

    def set_cycle(self, cycle: int, ok: bool, safety_status: str = "ok") -> None:
        """Update cycle counter and health status."""
        self._last_cycle = cycle
        self._last_cycle_ok = ok
        self._safety_status = safety_status

    def set_compliance_state(
        self,
        all_ok: bool,
        score: float,
        violations: list[str],
        cycle: int = 0,
    ) -> None:
        """Update compliance state (called after ComplianceStack.run_cycle())."""
        self._compliance = _ComplianceSnapshot(
            all_ok=all_ok,
            score=score,
            violations=violations,
            cycle_count=cycle,
            last_updated=time.time(),
        )

    def set_fleet_summary(self, summary: Any) -> None:
        """Update fleet KPIs from FleetOrchestrator.run_cycle()."""
        self._fleet = _FleetSnapshot(
            n_sites=getattr(summary, "n_sites", 0),
            total_capacity_kwh=getattr(summary, "total_capacity_kwh", 0.0),
            fleet_soc_pct=getattr(summary, "fleet_soc_pct", 0.0),
            total_available_kw=getattr(summary, "total_available_kw", 0.0),
            sites_in_alarm=getattr(summary, "sites_in_alarm", 0),
            last_updated=time.time(),
        )

    def set_telemetry(self, telemetry: dict[str, Any]) -> None:
        """Cache latest telemetry dict for /api/v1/telemetry."""
        self._telemetry = _TelemetrySnapshot(
            site_id=telemetry.get("site_id", self._site_id),
            soc_pct=telemetry.get("soc_pct", 0.0),
            power_kw=telemetry.get("p_kw", 0.0),
            temp_c=telemetry.get("temp_c", 0.0),
            f_grid_hz=telemetry.get("f_hz", 50.0),
            safety_ok=telemetry.get("safety_ok", True),
            cycle=self._last_cycle,
            timestamp=time.time(),
        )

    def set_site_telemetries(self, sites: list[dict[str, Any]]) -> None:
        """Cache per-site telemetry for /fleet/sites."""
        self._site_telemetries = sites

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    async def _handle_root(self, _: web.Request) -> web.Response:
        raise web.HTTPFound("/health")

    async def _handle_health(self, _: web.Request) -> web.Response:
        uptime = time.monotonic() - self._start_time
        status = "healthy" if self._last_cycle_ok else "degraded"
        payload = {
            "status": status,
            "site_id": self._site_id,
            "version": self._version,
            "uptime_s": round(uptime, 1),
            "last_cycle": self._last_cycle,
            "safety_status": self._safety_status,
            "compliance_ok": self._compliance.all_ok,
            "compliance_score": self._compliance.score,
        }
        return web.Response(
            text=json.dumps(payload, indent=2),
            content_type="application/json",
            status=200 if status == "healthy" else 503,
        )

    async def _handle_metrics(self, _: web.Request) -> web.Response:
        data = generate_metrics()
        return web.Response(body=data, content_type="text/plain")

    async def _handle_compliance_status(self, _: web.Request) -> web.Response:
        c = self._compliance
        status = "compliant" if c.all_ok else "non_compliant"
        payload = {
            "status": status,
            "compliance_score": c.score,
            "norm_ref": c.norm_ref,
            "site_id": self._site_id,
            "violations": c.violations,
            "cycle_count": c.cycle_count,
            "last_updated_utc": (
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(c.last_updated))
                if c.last_updated
                else None
            ),
        }
        return web.Response(
            text=json.dumps(payload, indent=2),
            content_type="application/json",
            status=200 if c.all_ok else 503,
        )

    async def _handle_compliance_report(self, _: web.Request) -> web.Response:
        c = self._compliance
        gaps = {
            f"GAP-{str(i).zfill(3)}": (
                {"status": "closed", "compliant": True, "score": 100}
                if not any(f"GAP-{str(i).zfill(3)}" in v for v in c.violations)
                else {"status": "open", "compliant": False, "score": 0}
            )
            for i in range(1, 12)
        }
        payload = {
            "report_type": "NTSyCS_COMPLIANCE_REPORT",
            "site_id": self._site_id,
            "version": self._version,
            "norm_ref": c.norm_ref,
            "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "overall_status": "COMPLIANT" if c.all_ok else "NON_COMPLIANT",
            "compliance_score": c.score,
            "gaps_checked": 11,
            "gaps": gaps,
            "violations": c.violations,
            "cycle_count": c.cycle_count,
        }
        return web.Response(
            text=json.dumps(payload, indent=2),
            content_type="application/json",
            status=200,
        )

    async def _handle_fleet_summary(self, _: web.Request) -> web.Response:
        f = self._fleet
        payload = {
            "site_id": self._site_id,
            "n_sites": f.n_sites,
            "total_capacity_kwh": f.total_capacity_kwh,
            "fleet_soc_pct": round(f.fleet_soc_pct, 1),
            "total_available_kw": round(f.total_available_kw, 1),
            "sites_in_alarm": f.sites_in_alarm,
            "last_updated_utc": (
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(f.last_updated))
                if f.last_updated
                else None
            ),
        }
        return web.Response(
            text=json.dumps(payload, indent=2),
            content_type="application/json",
            status=200,
        )

    async def _handle_fleet_sites(self, _: web.Request) -> web.Response:
        return web.Response(
            text=json.dumps(self._site_telemetries, indent=2),
            content_type="application/json",
            status=200,
        )

    async def _handle_telemetry(self, _: web.Request) -> web.Response:
        t = self._telemetry
        payload = asdict(t)
        payload["timestamp_utc"] = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t.timestamp)) if t.timestamp else None
        )
        return web.Response(
            text=json.dumps(payload, indent=2),
            content_type="application/json",
            status=200,
        )

    async def _handle_not_found(self, _: web.Request) -> web.Response:
        return web.Response(
            text=json.dumps({"error": "Not found", "docs": "/health"}),
            content_type="application/json",
            status=404,
        )

    async def _handle_setpoint(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}

        if self._totp_auth.is_enabled:
            header_token = request.headers.get("X-TOTP-Code") or request.headers.get(
                "X-TOTP-Token"
            )
            json_token = (
                data.get("totp_code") or data.get("totp_token") if isinstance(data, dict) else None
            )
            token = str(header_token or json_token or "")
            if not self._totp_auth.verify(token):
                log.warning("server.setpoint_unauthorized", reason="invalid_or_missing_totp")
                return web.Response(
                    text=json.dumps(
                        {
                            "error": "unauthorized",
                            "detail": "Invalid or missing TOTP/MFA token (IEC 62443-3-3 SR 1.3)",
                        }
                    ),
                    content_type="application/json",
                    status=401,
                )

        if not isinstance(data, dict):
            return web.Response(
                text=json.dumps({"error": "bad request", "detail": "Expected JSON object"}),
                content_type="application/json",
                status=400,
            )

        try:
            target_kw = float(data.get("target_kw", 0.0))
            strategy = str(data.get("strategy", ""))
            log.info("server.setpoint_received", target_kw=target_kw, strategy=strategy)
            return web.Response(
                text=json.dumps({"status": "accepted", "target_kw": target_kw}),
                content_type="application/json",
                status=202,
            )
        except Exception as exc:
            return web.Response(
                text=json.dumps({"error": "bad request", "detail": str(exc)}),
                content_type="application/json",
                status=400,
            )

    # ------------------------------------------------------------------
    # App construction
    # ------------------------------------------------------------------

    def _build_app(self) -> web.Application:
        app = web.Application(middlewares=[_rate_limit_middleware])
        app.router.add_get("/", self._handle_root)
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/metrics", self._handle_metrics)
        app.router.add_get("/compliance/status", self._handle_compliance_status)
        app.router.add_get("/compliance/report", self._handle_compliance_report)
        app.router.add_get("/fleet/summary", self._handle_fleet_summary)
        app.router.add_get("/fleet/sites", self._handle_fleet_sites)
        app.router.add_get("/api/v1/telemetry", self._handle_telemetry)
        app.router.add_post("/api/v1/setpoint", self._handle_setpoint)
        return app

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def serve_forever(self) -> None:
        """Run the HTTP server until cancelled."""
        runner = web.AppRunner(self._app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self._host, self._port)
        await site.start()
        log.info(
            "bessai_server.started",
            host=self._host,
            port=self._port,
            site_id=self._site_id,
            version=self._version,
            endpoints=[
                "/health",
                "/metrics",
                "/compliance/status",
                "/compliance/report",
                "/fleet/summary",
                "/api/v1/telemetry",
            ],
        )
        try:
            await asyncio.Event().wait()  # sleep forever
        finally:
            await runner.cleanup()

    @asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        """Async context manager — starts the server as a background task."""
        task = asyncio.create_task(self.serve_forever(), name="bessai-server")
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
