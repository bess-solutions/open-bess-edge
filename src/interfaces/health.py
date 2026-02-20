"""
src/interfaces/health.py
=========================
BESSAI Edge Gateway — Async HTTP Health & Metrics Server.

Provides two endpoints on ``PORT`` (default 8000):

- ``GET /health``   → JSON with gateway liveness, uptime and last cycle info.
- ``GET /metrics``  → Prometheus text exposition (scraped by otel-collector
                       or a Prometheus instance).
- ``GET /``         → redirects to /health for convenience.

Usage
-----
Start inside the main async event loop::

    server = HealthServer(site_id="SITE-CL-001", version="0.4.1")
    async with server.run():
        ...   # your acquisition loop

Or with ``asyncio.create_task``::

    task = asyncio.create_task(server.serve_forever())
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiohttp import web

from src.interfaces.metrics import generate_metrics

__all__ = ["HealthServer"]

_VERSION = "0.4.1"


class HealthServer:
    """
    Lightweight aiohttp HTTP server running alongside the gateway loop.

    Parameters
    ----------
    site_id:
        Value of the ``SITE_ID`` setting — included in every /health response.
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
        host: str = "0.0.0.0",
        port: int = 8000,
    ) -> None:
        self._site_id = site_id
        self._version = version
        self._host = host
        self._port = port
        self._start_time = time.monotonic()

        # Mutable state updated by the main orchestrator each cycle
        self.last_cycle: int = 0
        self.safety_status: str = "unknown"
        self.last_cycle_ok: bool = True

        self._app = self._build_app()

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    async def _handle_health(self, request: web.Request) -> web.Response:
        uptime = time.monotonic() - self._start_time
        status = "healthy" if self.last_cycle_ok else "degraded"
        payload = {
            "status": status,
            "site_id": self._site_id,
            "version": self._version,
            "uptime_s": round(uptime, 1),
            "last_cycle": self.last_cycle,
            "safety_status": self.safety_status,
        }
        status_code = 200 if status == "healthy" else 503
        return web.Response(
            text=json.dumps(payload, indent=2),
            content_type="application/json",
            status=status_code,
        )

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        data = generate_metrics()
        # aiohttp sets Content-Type header from content_type automatically;
        # passing both content_type and headers["Content-Type"] raises ValueError.
        return web.Response(
            body=data,
            content_type="text/plain",
        )

    async def _handle_root(self, request: web.Request) -> web.Response:
        raise web.HTTPFound("/health")

    # ------------------------------------------------------------------
    # App construction
    # ------------------------------------------------------------------

    def _build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/", self._handle_root)
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/metrics", self._handle_metrics)
        return app

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    async def serve_forever(self) -> None:
        """Run the HTTP server until cancelled."""
        runner = web.AppRunner(self._app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self._host, self._port)
        await site.start()
        try:
            await asyncio.Event().wait()  # sleep forever
        finally:
            await runner.cleanup()

    @asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        """
        Async context manager — starts the server as a background task.

        Example::

            async with health_server.run():
                await acquisition_loop()
        """
        task = asyncio.create_task(self.serve_forever(), name="health-server")
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
