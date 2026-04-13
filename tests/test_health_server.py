# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_health_server.py
============================
Unit tests for ``src.interfaces.health.HealthServer``.

Strategy: call route handlers directly (no real TCP server needed).
Uses aiohttp's built-in ``make_mocked_request`` pattern for handler tests.

Covers:
  - HealthServer construction: attributes, default state
  - _handle_health: status=healthy / degraded, JSON payload keys
  - _build_app: route registration
  - last_cycle, safety_status, last_cycle_ok mutations
"""

from __future__ import annotations

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from src.interfaces.health import HealthServer

# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestHealthServerConstruction:
    def test_default_state(self):
        server = HealthServer(site_id="TEST-001")
        assert server.last_cycle == 0
        assert server.safety_status == "unknown"
        assert server.last_cycle_ok is True

    def test_site_id_stored(self):
        server = HealthServer(site_id="SITE-CL-999")
        assert server._site_id == "SITE-CL-999"

    def test_version_stored(self):
        server = HealthServer(site_id="T", version="9.9.9")
        assert server._version == "9.9.9"

    def test_port_stored(self):
        server = HealthServer(site_id="T", port=9000)
        assert server._port == 9000

    def test_app_built_on_init(self):
        server = HealthServer(site_id="T")
        assert server._app is not None


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

class TestRoutesRegistered:
    def test_health_route_registered(self):
        server = HealthServer(site_id="T")
        routes = [r.resource.canonical for r in server._app.router.routes()]
        assert "/health" in routes

    def test_metrics_route_registered(self):
        server = HealthServer(site_id="T")
        routes = [r.resource.canonical for r in server._app.router.routes()]
        assert "/metrics" in routes

    def test_root_route_registered(self):
        server = HealthServer(site_id="T")
        routes = [r.resource.canonical for r in server._app.router.routes()]
        assert "/" in routes


# ---------------------------------------------------------------------------
# Handler: /health
# ---------------------------------------------------------------------------

class TestHandleHealth:
    @pytest.fixture()
    def server(self):
        return HealthServer(site_id="SITE-CL-001", version="2.16.0")

    async def test_health_returns_200_when_ok(self, server: HealthServer):
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        assert resp.status == 200

    async def test_health_returns_503_when_degraded(self, server: HealthServer):
        server.last_cycle_ok = False
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        assert resp.status == 503

    async def test_health_payload_has_required_keys(self, server: HealthServer):
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        payload = json.loads(resp.text)
        for key in ["status", "site_id", "version", "uptime_s",
                    "last_cycle", "safety_status"]:
            assert key in payload, f"Missing key: {key}"

    async def test_health_status_healthy(self, server: HealthServer):
        server.last_cycle_ok = True
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        payload = json.loads(resp.text)
        assert payload["status"] == "healthy"

    async def test_health_status_degraded(self, server: HealthServer):
        server.last_cycle_ok = False
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        payload = json.loads(resp.text)
        assert payload["status"] == "degraded"

    async def test_health_site_id_in_payload(self, server: HealthServer):
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        payload = json.loads(resp.text)
        assert payload["site_id"] == "SITE-CL-001"

    async def test_health_version_in_payload(self, server: HealthServer):
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        payload = json.loads(resp.text)
        assert payload["version"] == "2.16.0"

    async def test_health_uptime_s_non_negative(self, server: HealthServer):
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        payload = json.loads(resp.text)
        assert payload["uptime_s"] >= 0.0

    async def test_health_last_cycle_updated(self, server: HealthServer):
        server.last_cycle = 42
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        payload = json.loads(resp.text)
        assert payload["last_cycle"] == 42

    async def test_health_safety_status_reflected(self, server: HealthServer):
        server.safety_status = "ok"
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        payload = json.loads(resp.text)
        assert payload["safety_status"] == "ok"

    async def test_health_content_type_json(self, server: HealthServer):
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        assert "application/json" in resp.content_type


# ---------------------------------------------------------------------------
# Handler: /metrics
# ---------------------------------------------------------------------------

class TestHandleMetrics:
    async def test_metrics_returns_200(self):
        server = HealthServer(site_id="T")
        req = make_mocked_request("GET", "/metrics")
        resp = await server._handle_metrics(req)
        assert resp.status == 200

    async def test_metrics_content_type_plain(self):
        server = HealthServer(site_id="T")
        req = make_mocked_request("GET", "/metrics")
        resp = await server._handle_metrics(req)
        assert "text/plain" in resp.content_type

    async def test_metrics_body_non_empty(self):
        server = HealthServer(site_id="T")
        req = make_mocked_request("GET", "/metrics")
        resp = await server._handle_metrics(req)
        assert resp.body is not None


# ---------------------------------------------------------------------------
# Handler: / (redirect)
# ---------------------------------------------------------------------------

class TestHandleRoot:
    async def test_root_raises_redirect(self):
        server = HealthServer(site_id="T")
        req = make_mocked_request("GET", "/")
        with pytest.raises(web.HTTPFound):
            await server._handle_root(req)


# ---------------------------------------------------------------------------
# Mutable state
# ---------------------------------------------------------------------------

class TestMutableState:
    async def test_toggle_last_cycle_ok_changes_status(self):
        server = HealthServer(site_id="T")
        req = make_mocked_request("GET", "/health")

        server.last_cycle_ok = True
        resp_ok = await server._handle_health(req)
        payload_ok = json.loads(resp_ok.text)

        server.last_cycle_ok = False
        resp_deg = await server._handle_health(req)
        payload_deg = json.loads(resp_deg.text)

        assert payload_ok["status"] == "healthy"
        assert payload_deg["status"] == "degraded"

    async def test_last_cycle_increments_reflected(self):
        server = HealthServer(site_id="T")
        req = make_mocked_request("GET", "/health")
        for cycle in [1, 50, 100]:
            server.last_cycle = cycle
            resp = await server._handle_health(req)
            assert json.loads(resp.text)["last_cycle"] == cycle
