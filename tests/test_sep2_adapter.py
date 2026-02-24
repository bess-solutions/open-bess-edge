"""
tests/test_sep2_adapter.py
============================
Unit tests for the IEEE 2030.5 (SEP 2.0) adapter (BEP-0100).

Tests use a mock DataProvider and the aiohttp test client to exercise
all endpoints without requiring a real TLS context or BESS hardware.

Coverage targets per BEP-0100 Test Plan:
- GET /tm                         — TimeResource
- GET /edev                       — EndDeviceList
- GET /edev/0                     — EndDevice
- GET /edev/0/der                 — DERList
- GET /edev/0/der/0/derStatus     — DERStatus (live read_tag mapping)
- GET /edev/0/der/0/derSettings   — DERSettings (capability)
- GET /edev/0/der/0/derCapability — DERCapability
- GET /edev/0/derp                — DERProgramList
- POST /edev/0/derp/0/derc        — DERControl → write_tag()
  ├── opModConnect: false → standby
  ├── setMaxW: N → P_setpoint_kW
  ├── opModEnergize: true (normal SOC)
  ├── opModEnergize: true (SOC ≥ 98% → rejected)
  └── driver not connected → 503
- POST /mup                       — MirrorUsagePoint registration
- build_adapter_from_env()        — factory (enabled / disabled)
- SEP2ConfigError                 — missing cert paths
- _derive_lfdi()                  — fallback LFDI derivation
"""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Try importing the adapter — skip entire module if aiohttp not installed
# ---------------------------------------------------------------------------

try:
    from aiohttp.test_utils import TestClient, TestServer

    from src.interfaces.sep2_adapter import (
        SEP2Adapter,
        SEP2ConfigError,
        SEP2Error,
        _derive_lfdi,
        _storage_mode_from_power,
        build_adapter_from_env,
    )

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _AVAILABLE, reason="aiohttp not installed — skipping SEP 2.0 tests"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_driver(
    soc: float = 75.0,
    power_kw: float = -25.0,
    op_mode: float = 1.0,
    connected: bool = True,
) -> MagicMock:
    """Create a minimal DataProvider mock."""
    driver = MagicMock()
    driver.is_connected = connected
    driver.source_description = "MockDriver"

    async def _read_tag(tag: str) -> float:
        mapping = {
            "soc_pct": soc,
            "active_power_kw": power_kw,
            "operating_mode": op_mode,
            "battery_voltage_v": 700.0,
            "temp_c": 28.5,
        }
        return mapping.get(tag, 0.0)

    driver.read_tag = _read_tag
    driver.write_tag = AsyncMock()
    return driver


async def _make_test_client(driver: MagicMock, **kwargs: Any) -> TestClient:
    """Create an aiohttp TestClient for the SEP2Adapter (no TLS in tests)."""
    adapter = SEP2Adapter(driver=driver, **kwargs)
    # Build app directly without SSL for testing
    from aiohttp import web

    app = web.Application()
    adapter._register_routes(app)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    return client


# ---------------------------------------------------------------------------
# Helper constants
# ---------------------------------------------------------------------------

_CT = "application/sep+json"


# ---------------------------------------------------------------------------
# Tests — GET endpoints
# ---------------------------------------------------------------------------


class TestTimeResource:
    """GET /tm — TimeResource (IEEE 2030.5 §8.3)."""

    @pytest.mark.asyncio
    async def test_returns_200_and_current_time(self) -> None:
        driver = _make_driver()
        client = await _make_test_client(driver)
        async with client:
            before = int(time.time())
            resp = await client.get("/tm")
            after = int(time.time())
            assert resp.status == 200
            body = await resp.json(content_type=None)
            assert body["type"] == "TimeResource"
            assert before <= body["currentTime"] <= after + 1

    @pytest.mark.asyncio
    async def test_content_type(self) -> None:
        driver = _make_driver()
        client = await _make_test_client(driver)
        async with client:
            resp = await client.get("/tm")
            assert _CT in resp.headers.get("Content-Type", "")


class TestEndDeviceList:
    """GET /edev — EndDeviceList (IEEE 2030.5 §8.4)."""

    @pytest.mark.asyncio
    async def test_returns_end_device_list(self) -> None:
        driver = _make_driver()
        client = await _make_test_client(driver)
        async with client:
            resp = await client.get("/edev")
            assert resp.status == 200
            body = await resp.json(content_type=None)
            assert body["type"] == "EndDeviceList"
            assert body["all"] == 1
            assert len(body["EndDevice"]) == 1

    @pytest.mark.asyncio
    async def test_end_device_has_lfdi(self) -> None:
        driver = _make_driver()
        client = await _make_test_client(driver)
        async with client:
            resp = await client.get("/edev")
            body = await resp.json(content_type=None)
            edev = body["EndDevice"][0]
            assert "lFDI" in edev
            assert len(edev["lFDI"]) == 40


class TestDERStatus:
    """GET /edev/0/der/0/derStatus — live telemetry mapping."""

    @pytest.mark.asyncio
    async def test_soc_mapped_to_fixed_point(self) -> None:
        """SOC=75.0% should map to stateOfChargeStatus.value=7500."""
        driver = _make_driver(soc=75.0)
        client = await _make_test_client(driver)
        async with client:
            resp = await client.get("/edev/0/der/0/derStatus")
            assert resp.status == 200
            body = await resp.json(content_type=None)
            assert body["stateOfChargeStatus"]["value"] == 7500

    @pytest.mark.asyncio
    async def test_charging_storage_mode(self) -> None:
        """active_power_kw < 0 → storageModeStatus=3 (Charging)."""
        driver = _make_driver(power_kw=-30.0)
        client = await _make_test_client(driver)
        async with client:
            resp = await client.get("/edev/0/der/0/derStatus")
            body = await resp.json(content_type=None)
            assert body["storageModeStatus"]["value"] == 3  # CHARGING

    @pytest.mark.asyncio
    async def test_discharging_storage_mode(self) -> None:
        """active_power_kw > 0 → storageModeStatus=4 (Discharging)."""
        driver = _make_driver(power_kw=50.0)
        client = await _make_test_client(driver)
        async with client:
            resp = await client.get("/edev/0/der/0/derStatus")
            body = await resp.json(content_type=None)
            assert body["storageModeStatus"]["value"] == 4  # DISCHARGING

    @pytest.mark.asyncio
    async def test_idle_storage_mode(self) -> None:
        """active_power_kw ≈ 0 → storageModeStatus=5 (Idle)."""
        driver = _make_driver(power_kw=0.05)
        client = await _make_test_client(driver)
        async with client:
            resp = await client.get("/edev/0/der/0/derStatus")
            body = await resp.json(content_type=None)
            assert body["storageModeStatus"]["value"] == 5  # IDLE


class TestDERSettings:
    """GET /edev/0/der/0/derSettings — capability declaration."""

    @pytest.mark.asyncio
    async def test_max_w_returned(self) -> None:
        driver = _make_driver()
        client = await _make_test_client(driver, max_w=50000)
        async with client:
            resp = await client.get("/edev/0/der/0/derSettings")
            assert resp.status == 200
            body = await resp.json(content_type=None)
            assert body["setMaxW"]["value"] == 50000

    @pytest.mark.asyncio
    async def test_max_wh_returned(self) -> None:
        driver = _make_driver()
        client = await _make_test_client(driver, max_wh=200000)
        async with client:
            resp = await client.get("/edev/0/der/0/derSettings")
            body = await resp.json(content_type=None)
            assert body["setMaxWh"]["value"] == 200000


class TestDERCapability:
    """GET /edev/0/der/0/derCapability."""

    @pytest.mark.asyncio
    async def test_returns_capability(self) -> None:
        driver = _make_driver()
        client = await _make_test_client(driver)
        async with client:
            resp = await client.get("/edev/0/der/0/derCapability")
            assert resp.status == 200
            body = await resp.json(content_type=None)
            assert body["type"] == "DERCapability"
            assert "rtgMaxW" in body


# ---------------------------------------------------------------------------
# Tests — DERControl (POST)
# ---------------------------------------------------------------------------


class TestDERControl:
    """POST /edev/0/derp/0/derc — DERControl handler (BEP-0100 §DERControl Mapping)."""

    @pytest.mark.asyncio
    async def test_op_mod_connect_false_writes_standby(self) -> None:
        """opModConnect=false → write_tag('operating_mode', 99.0)."""
        driver = _make_driver()
        client = await _make_test_client(driver)
        async with client:
            payload = {"DERControlBase": {"opModConnect": False}}
            resp = await client.post(
                "/edev/0/derp/0/derc",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 201
            driver.write_tag.assert_awaited_once_with("operating_mode", 99.0)

    @pytest.mark.asyncio
    async def test_set_max_w_writes_p_setpoint(self) -> None:
        """setMaxW=50000W → write_tag('P_setpoint_kW', 50.0)."""
        driver = _make_driver()
        client = await _make_test_client(driver, max_w=100000)
        async with client:
            payload = {"DERControlBase": {"setMaxW": {"value": 50000, "multiplier": 0}}}
            resp = await client.post(
                "/edev/0/derp/0/derc",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 201
            driver.write_tag.assert_awaited_once_with("P_setpoint_kW", 50.0)

    @pytest.mark.asyncio
    async def test_set_max_w_exceeds_limit_returns_400(self) -> None:
        """setMaxW > device max_w → 400 Bad Request."""
        driver = _make_driver()
        client = await _make_test_client(driver, max_w=50000)
        async with client:
            payload = {"DERControlBase": {"setMaxW": 999999}}
            resp = await client.post(
                "/edev/0/derp/0/derc",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 400
            body = await resp.json(content_type=None)
            assert "errors" in body

    @pytest.mark.asyncio
    async def test_op_mod_energize_normal_soc(self) -> None:
        """opModEnergize=true with SOC=75% → write_tag('operating_mode', 1.0)."""
        driver = _make_driver(soc=75.0)
        client = await _make_test_client(driver)
        async with client:
            payload = {"DERControlBase": {"opModEnergize": True}}
            resp = await client.post(
                "/edev/0/derp/0/derc",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 201
            driver.write_tag.assert_awaited_once_with("operating_mode", 1.0)

    @pytest.mark.asyncio
    async def test_op_mod_energize_rejected_when_full(self) -> None:
        """opModEnergize=true with SOC=99% → 400 (battery full guard)."""
        driver = _make_driver(soc=99.0)
        client = await _make_test_client(driver)
        async with client:
            payload = {"DERControlBase": {"opModEnergize": True}}
            resp = await client.post(
                "/edev/0/derp/0/derc",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 400
            body = await resp.json(content_type=None)
            assert any("SOC" in e for e in body["errors"])

    @pytest.mark.asyncio
    async def test_driver_not_connected_returns_503(self) -> None:
        """DERControl when driver disconnected → 503 Service Unavailable."""
        driver = _make_driver(connected=False)
        client = await _make_test_client(driver)
        async with client:
            payload = {"DERControlBase": {"opModConnect": False}}
            resp = await client.post(
                "/edev/0/derp/0/derc",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 503

    @pytest.mark.asyncio
    async def test_invalid_json_returns_400(self) -> None:
        """Malformed JSON body → 400 Bad Request."""
        driver = _make_driver()
        client = await _make_test_client(driver)
        async with client:
            resp = await client.post(
                "/edev/0/derp/0/derc",
                data="not-json",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 400


# ---------------------------------------------------------------------------
# Tests — MirrorUsagePoint
# ---------------------------------------------------------------------------


class TestMirrorUsagePoint:
    """POST /mup — receive MUP registration from DERMS."""

    @pytest.mark.asyncio
    async def test_returns_201(self) -> None:
        driver = _make_driver()
        client = await _make_test_client(driver)
        async with client:
            payload = {"type": "MirrorUsagePoint", "deviceLFDI": "ABCDEF"}
            resp = await client.post(
                "/mup",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 201


# ---------------------------------------------------------------------------
# Tests — Factory and Config
# ---------------------------------------------------------------------------


class TestBuildAdapterFromEnv:
    """build_adapter_from_env() factory function."""

    def test_returns_none_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SEP2_ENABLED", "false")
        driver = _make_driver()
        result = build_adapter_from_env(driver)
        assert result is None

    def test_returns_adapter_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SEP2_ENABLED", "true")
        driver = _make_driver()
        result = build_adapter_from_env(driver)
        assert isinstance(result, SEP2Adapter)

    def test_returns_none_when_aiohttp_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SEP2_ENABLED", "true")
        driver = _make_driver()
        with patch("src.interfaces.sep2_adapter._AIOHTTP_AVAILABLE", False):
            result = build_adapter_from_env(driver)
        assert result is None


class TestSEP2ConfigError:
    """SEP2Adapter raises SEP2ConfigError when misconfigured."""

    def test_raises_when_require_mtls_but_no_ca(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """require_mtls=True without SEP2_TLS_CA → SEP2ConfigError."""
        # Create dummy cert/key files
        cert = tmp_path / "server.crt"
        key = tmp_path / "server.key"
        cert.write_text("CERT")
        key.write_text("KEY")

        driver = _make_driver()
        adapter = SEP2Adapter(
            driver=driver,
            tls_cert=str(cert),
            tls_key=str(key),
            tls_ca=None,
            require_mtls=True,
        )
        with pytest.raises(SEP2ConfigError, match="SEP2_TLS_CA"):
            adapter._build_ssl_context()


class TestDeriveLfdi:
    """_derive_lfdi() produces valid LFDI strings."""

    def test_fallback_when_no_cert(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SITE_ID", "TEST-SITE")
        lfdi = _derive_lfdi(None)
        assert len(lfdi) == 40
        assert lfdi == lfdi.upper()

    def test_fallback_when_cert_not_found(self) -> None:
        lfdi = _derive_lfdi("/nonexistent/path/cert.pem")
        assert len(lfdi) == 40


class TestStorageModeMapping:
    """_storage_mode_from_power() helper matches BEP-0100 §DERStatus Mapping."""

    def test_charging(self) -> None:
        assert _storage_mode_from_power(-30.0) == 3  # CHARGING

    def test_discharging(self) -> None:
        assert _storage_mode_from_power(30.0) == 4  # DISCHARGING

    def test_idle_near_zero_positive(self) -> None:
        assert _storage_mode_from_power(0.05) == 5  # IDLE

    def test_idle_near_zero_negative(self) -> None:
        assert _storage_mode_from_power(-0.05) == 5  # IDLE
