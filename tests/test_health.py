"""
tests/test_health.py
=====================
Unit tests for the HealthServer (HTTP /health and /metrics endpoints).
Uses aiohttp.test_utils.TestClient to make real HTTP calls to the server.
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from src.interfaces.health import HealthServer


@pytest.fixture()
def health_server() -> HealthServer:
    return HealthServer(site_id="TEST-SITE", version="0.0.0-test", port=0)


@pytest_asyncio.fixture()
async def client(health_server: HealthServer) -> AsyncGenerator[TestClient, None]:
    """Start a test aiohttp client bound to the health app."""
    async with TestClient(TestServer(health_server._app)) as tc:
        yield tc


# ---------------------------------------------------------------------------
# /health endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_returns_200_when_ok(client: TestClient) -> None:
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "healthy"
    assert data["site_id"] == "TEST-SITE"
    assert data["version"] == "0.0.0-test"
    assert data["last_cycle"] == 0
    assert data["safety_status"] == "unknown"
    assert "uptime_s" in data


@pytest.mark.asyncio
async def test_health_returns_503_when_degraded(
    health_server: HealthServer, client: TestClient
) -> None:
    health_server.last_cycle_ok = False
    resp = await client.get("/health")
    assert resp.status == 503
    data = await resp.json()
    assert data["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_reflects_cycle_counter(
    health_server: HealthServer, client: TestClient
) -> None:
    health_server.last_cycle = 42
    health_server.last_cycle_ok = True
    health_server.safety_status = "ok"
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["last_cycle"] == 42
    assert data["safety_status"] == "ok"


@pytest.mark.asyncio
async def test_root_redirects_to_health(client: TestClient) -> None:
    resp = await client.get("/", allow_redirects=False)
    assert resp.status in (301, 302, 303, 307, 308)
    assert "/health" in resp.headers.get("Location", "")


# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metrics_returns_200(client: TestClient) -> None:
    resp = await client.get("/metrics")
    assert resp.status == 200


@pytest.mark.asyncio
async def test_metrics_content_type_is_prometheus(client: TestClient) -> None:
    resp = await client.get("/metrics")
    content_type = resp.headers.get("Content-Type", "")
    assert "text/plain" in content_type


@pytest.mark.asyncio
async def test_metrics_contains_expected_metric_names(client: TestClient) -> None:
    resp = await client.get("/metrics")
    text = await resp.text()
    assert "bess_cycles_total" in text
    assert "bess_safety_blocks_total" in text
    assert "bess_last_soc_percent" in text
    assert "bess_gateway_info" in text


# ---------------------------------------------------------------------------
# HealthServer lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_serve_forever_can_be_cancelled(health_server: HealthServer) -> None:
    """serve_forever() must exit cleanly on task cancellation."""
    task = asyncio.create_task(health_server.serve_forever())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass  # expected


@pytest.mark.asyncio
async def test_run_context_manager_starts_and_stops(
    health_server: HealthServer,
) -> None:
    """run() context manager must return without error."""
    async with health_server.run():
        await asyncio.sleep(0.05)
    # if we get here the server started and stopped cleanly
