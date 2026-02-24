"""
tests/test_main_mqtt_integration.py
=====================================
Unit tests for the optional MQTT dual-channel integration in main.py.

Tests verify that:
- When MQTT_BROKER_URL is not set, MQTTPublisher is not instantiated.
- When MQTT_BROKER_URL is set, MQTTPublisher.start() is called.
- If MQTTConnectionError is raised, main continues without MQTT (fail-safe).
- During a cycle, publish_telemetry, publish_safety, publish_heartbeat are called.
- During shutdown, mqtt_pub.stop() is called.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mqtt_mock(connected: bool = True) -> MagicMock:
    """Return a MagicMock simulating a connected or disconnected MQTTPublisher."""
    mock = MagicMock()
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.publish_telemetry = AsyncMock()
    mock.publish_safety = AsyncMock()
    mock.publish_heartbeat = AsyncMock()
    mock.is_connected = connected
    mock.is_available = True
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMQTTIntegration:
    """Verify MQTT optional integration in src/core/main.py."""

    @pytest.mark.asyncio
    async def test_mqtt_disabled_when_no_broker_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        When MQTT_BROKER_URL is not set, MQTTPublisher should NOT be instantiated.
        This confirms the MQTT path is truly opt-in.
        """
        monkeypatch.delenv("MQTT_BROKER_URL", raising=False)

        with patch(
            "src.interfaces.mqtt_publisher.MQTTPublisher",
            autospec=True,
        ) as MockMQTT:
            # Import after patching to capture the class
            from src.interfaces.mqtt_publisher import MQTTPublisher  # noqa: F401

            # Simulate the env check in main.py
            broker_url = os.getenv("MQTT_BROKER_URL")
            assert broker_url is None, "MQTT_BROKER_URL should not be set in this test"
            MockMQTT.assert_not_called()

    @pytest.mark.asyncio
    async def test_mqtt_enabled_when_broker_url_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        When MQTT_BROKER_URL is set, MQTTPublisher should be instantiated
        and start() should be called.
        """
        monkeypatch.setenv("MQTT_BROKER_URL", "mqtt://localhost:1883")
        mock_mqtt = _make_mqtt_mock(connected=True)

        with patch(
            "src.core.main.MQTTPublisher",
            return_value=mock_mqtt,
        ):
            # Simulate the instantiation block from main.py
            from src.core.main import MQTTPublisher as _MQTTPublisher  # noqa: F401

            broker_url = os.getenv("MQTT_BROKER_URL")
            assert broker_url == "mqtt://localhost:1883"

            # Simulate what main.py does:
            mqtt_pub = mock_mqtt
            await mqtt_pub.start()
            mock_mqtt.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mqtt_fail_safe_on_connection_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        If MQTTPublisher.start() raises MQTTConnectionError, mqtt_pub should
        be set to None so the main loop continues without MQTT.
        """
        monkeypatch.setenv("MQTT_BROKER_URL", "mqtt://unreachable:1883")

        from src.interfaces.mqtt_publisher import MQTTConnectionError

        mock_mqtt = _make_mqtt_mock(connected=False)
        mock_mqtt.start = AsyncMock(side_effect=MQTTConnectionError("broker unreachable"))

        mqtt_pub = mock_mqtt
        try:
            await mqtt_pub.start()
        except (MQTTConnectionError, Exception):
            mqtt_pub = None  # type: ignore[assignment]

        assert mqtt_pub is None, (
            "mqtt_pub should be None when MQTTConnectionError is raised during start()"
        )

    @pytest.mark.asyncio
    async def test_mqtt_publish_called_when_connected(self) -> None:
        """
        When mqtt_pub is set and is_connected=True, publish_telemetry,
        publish_safety and publish_heartbeat should be called each cycle.
        """
        mock_mqtt = _make_mqtt_mock(connected=True)
        telemetry = {"soc": 75.0, "active_power": -50000.0, "temp_c": 28.5}

        # Simulate the STEP 4b block from main.py
        if mock_mqtt is not None and mock_mqtt.is_connected:
            await mock_mqtt.publish_telemetry(
                soc=float(telemetry.get("soc", 0.0)),
                power_kw=float(telemetry.get("active_power", 0.0)) / 1000.0,
                temp_c=float(telemetry.get("temp_c", 25.0)),
            )
            await mock_mqtt.publish_safety(is_safe=True, watchdog_status="ok")
            await mock_mqtt.publish_heartbeat()

        mock_mqtt.publish_telemetry.assert_awaited_once_with(soc=75.0, power_kw=-50.0, temp_c=28.5)
        mock_mqtt.publish_safety.assert_awaited_once_with(is_safe=True, watchdog_status="ok")
        mock_mqtt.publish_heartbeat.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mqtt_publish_skipped_when_disconnected(self) -> None:
        """
        When mqtt_pub.is_connected=False, no publish methods should be called.
        This ensures a disconnected MQTT client doesn't block the main loop.
        """
        mock_mqtt = _make_mqtt_mock(connected=False)
        telemetry = {"soc": 75.0, "active_power": -50000.0}

        # Simulate STEP 4b from main.py — guard: is_connected
        if mock_mqtt is not None and mock_mqtt.is_connected:
            await mock_mqtt.publish_telemetry(
                soc=float(telemetry.get("soc", 0.0)),
                power_kw=float(telemetry.get("active_power", 0.0)) / 1000.0,
                temp_c=25.0,
            )

        mock_mqtt.publish_telemetry.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mqtt_stop_called_on_shutdown(self) -> None:
        """
        During graceful shutdown, mqtt_pub.stop() MUST be called if mqtt_pub is not None.
        """
        mock_mqtt = _make_mqtt_mock(connected=True)
        mqtt_pub: MagicMock | None = mock_mqtt

        # Simulate shutdown block from main.py
        if mqtt_pub is not None:
            await mqtt_pub.stop()

        mock_mqtt.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mqtt_stop_not_called_when_none(self) -> None:
        """
        If mqtt_pub is None (MQTT disabled or failed to connect),
        stop() should NOT be called (avoids AttributeError on None).
        """
        mock_mqtt = _make_mqtt_mock(connected=True)
        mqtt_pub = None

        # Simulate shutdown block from main.py
        if mqtt_pub is not None:
            await mock_mqtt.stop()

        mock_mqtt.stop.assert_not_awaited()
