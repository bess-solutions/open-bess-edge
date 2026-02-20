"""
tests/test_dashboard_api_handlers.py
======================================
Tests for DashboardAPI HTTP handlers and lifecycle.

Uses lightweight request mocks — no real aiohttp server needed.
Covers: _check_auth, handle_status, handle_fleet, handle_carbon,
        handle_p2p, handle_version, handle_health, handle_schedule,
        start/stop lifecycle, is_available property.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from src.interfaces.dashboard_api import DashboardAPI, DashboardState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(auth_header: str = "", query: dict | None = None) -> MagicMock:
    """Minimal aiohttp Request mock."""
    req = MagicMock()
    req.headers = {"Authorization": auth_header} if auth_header else {}
    if query is not None:
        req.rel_url.query = query
    else:
        req.rel_url.query = {}
    return req


def _parse(response: MagicMock) -> dict:
    """Extract JSON payload from a web.Response mock text."""
    return json.loads(response.text)


# ---------------------------------------------------------------------------
# _check_auth
# ---------------------------------------------------------------------------


class TestCheckAuth:
    @pytest.mark.asyncio
    async def test_no_api_key_always_passes(self):
        api = DashboardAPI(api_key="")
        req = _make_request()
        assert await api._check_auth(req) is True

    @pytest.mark.asyncio
    async def test_correct_bearer_token_passes(self):
        api = DashboardAPI(api_key="secret123")
        req = _make_request(auth_header="Bearer secret123")
        assert await api._check_auth(req) is True

    @pytest.mark.asyncio
    async def test_wrong_token_fails(self):
        api = DashboardAPI(api_key="secret123")
        req = _make_request(auth_header="Bearer wrong")
        assert await api._check_auth(req) is False

    @pytest.mark.asyncio
    async def test_missing_header_fails(self):
        api = DashboardAPI(api_key="secret123")
        req = _make_request(auth_header="")
        assert await api._check_auth(req) is False


# ---------------------------------------------------------------------------
# handle_status
# ---------------------------------------------------------------------------


class TestHandleStatus:
    def _api(self) -> DashboardAPI:
        state = DashboardState(site_id="test-site")
        state.soc_pct = 75.0
        state.is_safe = True
        return DashboardAPI(state=state, api_key="")

    @pytest.mark.asyncio
    async def test_status_returns_json_with_site_id(self):
        api = self._api()
        req = _make_request()
        resp = await api.handle_status(req)
        data = _parse(resp)
        assert data["site_id"] == "test-site"

    @pytest.mark.asyncio
    async def test_status_unauthorized_with_key(self):
        api = DashboardAPI(api_key="tok")
        req = _make_request()
        resp = await api.handle_status(req)
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_status_authorized_with_correct_key(self):
        state = DashboardState(site_id="s1")
        api = DashboardAPI(state=state, api_key="tok")
        req = _make_request(auth_header="Bearer tok")
        resp = await api.handle_status(req)
        data = _parse(resp)
        assert "telemetry" in data


# ---------------------------------------------------------------------------
# handle_fleet
# ---------------------------------------------------------------------------


class TestHandleFleet:
    @pytest.mark.asyncio
    async def test_fleet_returns_n_sites(self):
        state = DashboardState()
        state.fleet_n_sites = 7
        api = DashboardAPI(state=state, api_key="")
        resp = await api.handle_fleet(_make_request())
        data = _parse(resp)
        assert data["n_sites"] == 7

    @pytest.mark.asyncio
    async def test_fleet_unauthorized_returns_401(self):
        api = DashboardAPI(api_key="secret")
        resp = await api.handle_fleet(_make_request())
        assert resp.status == 401


# ---------------------------------------------------------------------------
# handle_carbon
# ---------------------------------------------------------------------------


class TestHandleCarbon:
    @pytest.mark.asyncio
    async def test_carbon_contains_co2_key(self):
        state = DashboardState()
        state.co2_avoided_kg = 500.0
        api = DashboardAPI(state=state, api_key="")
        resp = await api.handle_carbon(_make_request())
        data = _parse(resp)
        assert data["co2_avoided_kg"] == pytest.approx(500.0)
        assert "methodology" in data

    @pytest.mark.asyncio
    async def test_carbon_unauthorized_returns_401(self):
        api = DashboardAPI(api_key="tok")
        resp = await api.handle_carbon(_make_request())
        assert resp.status == 401


# ---------------------------------------------------------------------------
# handle_p2p
# ---------------------------------------------------------------------------


class TestHandleP2P:
    @pytest.mark.asyncio
    async def test_p2p_credits_minted(self):
        state = DashboardState()
        state.p2p_credits_minted = 10
        state.p2p_credits_kwh = 50.0
        api = DashboardAPI(state=state, api_key="")
        resp = await api.handle_p2p(_make_request())
        data = _parse(resp)
        assert data["credits_minted"] == 10

    @pytest.mark.asyncio
    async def test_p2p_unauthorized_returns_401(self):
        api = DashboardAPI(api_key="tok")
        resp = await api.handle_p2p(_make_request())
        assert resp.status == 401


# ---------------------------------------------------------------------------
# handle_version  (no auth required)
# ---------------------------------------------------------------------------


class TestHandleVersion:
    @pytest.mark.asyncio
    async def test_version_has_required_fields(self):
        api = DashboardAPI(api_key="tok")  # no auth on this endpoint
        resp = await api.handle_version(_make_request())
        data = _parse(resp)
        assert "version" in data
        assert "build_date" in data
        assert "project" in data

    @pytest.mark.asyncio
    async def test_version_no_auth_needed(self):
        """Version endpoint does NOT require auth."""
        api = DashboardAPI(api_key="tok")
        resp = await api.handle_version(_make_request())
        # Should not return 401 — version is always public
        assert not hasattr(resp, "status") or resp.status != 401


# ---------------------------------------------------------------------------
# handle_health  (no auth required)
# ---------------------------------------------------------------------------


class TestHandleHealth:
    @pytest.mark.asyncio
    async def test_health_ok_when_safe(self):
        state = DashboardState(site_id="hsite")
        state.is_safe = True
        api = DashboardAPI(state=state, api_key="")
        resp = await api.handle_health(_make_request())
        data = _parse(resp)
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_degraded_when_unsafe(self):
        state = DashboardState(site_id="hsite")
        state.is_safe = False
        api = DashboardAPI(state=state, api_key="")
        resp = await api.handle_health(_make_request())
        data = _parse(resp)
        assert data["status"] == "degraded"


# ---------------------------------------------------------------------------
# handle_schedule
# ---------------------------------------------------------------------------


class TestHandleSchedule:
    @pytest.mark.asyncio
    async def test_schedule_returns_hourly_schedule(self):
        state = DashboardState(site_id="sched-site")
        state.soc_pct = 55.0
        api = DashboardAPI(state=state, api_key="")
        req = _make_request(query={"capacity_kwh": "500", "max_power_kw": "250"})
        resp = await api.handle_schedule(req)
        data = _parse(resp)
        assert "hourly_schedule" in data
        assert len(data["hourly_schedule"]) == 24

    @pytest.mark.asyncio
    async def test_schedule_unauthorized_returns_401(self):
        api = DashboardAPI(api_key="tok")
        req = _make_request(query={})
        resp = await api.handle_schedule(req)
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_schedule_uses_cache_when_fresh(self):
        import time

        state = DashboardState()
        state._schedule_dict = {"cached": True, "hourly_schedule": []}
        state.schedule_last_updated = time.time() - 10  # 10s ago → fresh
        api = DashboardAPI(state=state, api_key="")
        req = _make_request(query={})
        resp = await api.handle_schedule(req)
        data = _parse(resp)
        assert data.get("cached") is True

    @pytest.mark.asyncio
    async def test_schedule_recomputes_when_stale(self):
        import time

        state = DashboardState()
        state._schedule_dict = {"cached": True, "hourly_schedule": []}
        state.schedule_last_updated = time.time() - 1000  # stale
        state.soc_pct = 50.0
        api = DashboardAPI(state=state, api_key="")
        req = _make_request(query={"capacity_kwh": "1000"})
        resp = await api.handle_schedule(req)
        data = _parse(resp)
        # Fresh computation should return the proper structure
        assert "hourly_schedule" in data
        assert data.get("cached") is not True


# ---------------------------------------------------------------------------
# is_available property
# ---------------------------------------------------------------------------


class TestDashboardAPIAvailability:
    def test_is_available_returns_bool(self):
        api = DashboardAPI()
        assert isinstance(api.is_available, bool)

    def test_is_available_true_when_aiohttp_installed(self):
        """aiohttp is in requirements.txt — should be available in test env."""
        api = DashboardAPI()
        assert api.is_available is True


# ---------------------------------------------------------------------------
# Lifecycle: start / stop
# ---------------------------------------------------------------------------


class TestDashboardAPILifecycle:
    @pytest.mark.asyncio
    async def test_start_raises_if_no_aiohttp(self, monkeypatch):
        import src.interfaces.dashboard_api as mod

        monkeypatch.setattr(mod, "_AIOHTTP_AVAILABLE", False)
        api = DashboardAPI()
        with pytest.raises(RuntimeError, match="aiohttp"):
            await api.start()

    @pytest.mark.asyncio
    async def test_stop_when_runner_is_none_is_noop(self):
        api = DashboardAPI()
        api._runner = None
        await api.stop()  # should not raise
