"""
src/interfaces/mqtt_publisher.py
================================
BESSAI Edge Gateway — MQTT Publisher (universal IoT transport).

Publishes BESS telemetry to any MQTT broker: Mosquitto, AWS IoT Core,
Azure IoT Hub, HiveMQ, Home Assistant, or self-hosted.

Topics published (QoS 1):
  {site_id}/telemetry         → SOC, power, temp, cycle_count
  {site_id}/safety            → is_safe, watchdog_status
  {site_id}/ai/ids            → AI-IDS anomaly score + alert_count
  {site_id}/ai/dispatch       → ONNX dispatch kW + inference_ms
  {site_id}/system/heartbeat  → ms since epoch (liveness probe)

Auth:
  - Anonymous (plain TCP)
  - Username/password (MQTT_USERNAME + MQTT_PASSWORD)
  - TLS with CA cert (MQTT_TLS_CA_CERT_PATH)
  - AWS IoT Core (TLS mutual auth via cert + private key)

Usage::

    publisher = MQTTPublisher(
        broker_url="mqtt://localhost:1883",
        site_id="SITE-CL-001",
    )
    await publisher.start()
    await publisher.publish_telemetry(soc=72.3, power_kw=-100.0, temp_c=29.1)
    await publisher.stop()

Install dependency: pip install paho-mqtt>=2.0
"""

from __future__ import annotations

import asyncio
import json
import os
import ssl
import time
import urllib.parse
from typing import Any

import structlog

__all__ = ["MQTTPublisher", "MQTTConnectionError"]

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MQTTConnectionError(RuntimeError):
    """Raised when the MQTT broker is unreachable or TLS fails."""


# ---------------------------------------------------------------------------
# Optional paho-mqtt import
# ---------------------------------------------------------------------------
try:
    import paho.mqtt.client as mqtt  # type: ignore[import]

    _PAHO_AVAILABLE = True
except ImportError:
    _PAHO_AVAILABLE = False
    mqtt = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Topic templates
# ---------------------------------------------------------------------------
_TOPICS = {
    "telemetry": "{site_id}/telemetry",
    "safety": "{site_id}/safety",
    "ids": "{site_id}/ai/ids",
    "dispatch": "{site_id}/ai/dispatch",
    "heartbeat": "{site_id}/system/heartbeat",
}


class MQTTPublisher:
    """
    Async-compatible MQTT publisher for BESSAI Edge telemetry.

    Uses paho-mqtt's loop_start() in a background thread and publishes
    via thread-safe paho calls from the async event loop.

    Parameters
    ----------
    broker_url:
        Full broker URL, e.g. ``mqtt://localhost:1883`` or
        ``mqtts://iot.example.com:8883`` or
        ``mqtt://user:pass@broker.hivemq.com:1883``.
    site_id:
        Site identifier used as MQTT topic prefix.
    client_id:
        MQTT client ID (defaults to ``bessai-{site_id}``).
    qos:
        Quality of Service level (0, 1 or 2). Default: 1.
    retain:
        Whether to set the RETAIN flag on publish. Default: False.
    tls_ca_cert:
        Path to CA certificate file for TLS verification. Optional.
    tls_certfile:
        Path to client certificate (mutual TLS / AWS IoT). Optional.
    tls_keyfile:
        Path to client private key (mutual TLS / AWS IoT). Optional.
    """

    def __init__(
        self,
        broker_url: str | None = None,
        site_id: str = "edge-001",
        client_id: str | None = None,
        qos: int = 1,
        retain: bool = False,
        tls_ca_cert: str | None = None,
        tls_certfile: str | None = None,
        tls_keyfile: str | None = None,
    ) -> None:
        self._broker_url = broker_url or os.getenv("MQTT_BROKER_URL", "mqtt://localhost:1883")
        self._site_id = site_id
        self._client_id = client_id or f"bessai-{site_id}"
        self._qos = qos
        self._retain = retain
        self._tls_ca_cert = tls_ca_cert or os.getenv("MQTT_TLS_CA_CERT_PATH")
        self._tls_certfile = tls_certfile or os.getenv("MQTT_TLS_CERTFILE")
        self._tls_keyfile = tls_keyfile or os.getenv("MQTT_TLS_KEYFILE")

        # Parse URL
        parsed = urllib.parse.urlparse(self._broker_url)
        self._host = parsed.hostname or "localhost"
        self._port = parsed.port or (8883 if parsed.scheme == "mqtts" else 1883)
        self._use_tls = parsed.scheme == "mqtts" or bool(self._tls_ca_cert or self._tls_certfile)
        self._username = parsed.username or os.getenv("MQTT_USERNAME")
        self._password = parsed.password or os.getenv("MQTT_PASSWORD")

        self._client: Any = None
        self._connected = False
        self._publish_count = 0

    # -----------------------------------------------------------------------
    # Topic helpers
    # -----------------------------------------------------------------------

    def _topic(self, key: str) -> str:
        return _TOPICS[key].format(site_id=self._site_id)

    def _dump(self, payload: dict) -> str:
        return json.dumps(payload, separators=(",", ":"))

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def _build_tls_context(self) -> ssl.SSLContext:
        """Build and return an SSLContext for TLS-secured connections."""
        tls_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if self._tls_ca_cert:
            tls_ctx.load_verify_locations(self._tls_ca_cert)
        else:
            tls_ctx.load_default_certs()
        if self._tls_certfile and self._tls_keyfile:
            tls_ctx.load_cert_chain(self._tls_certfile, self._tls_keyfile)
        return tls_ctx

    def _setup_callbacks(self) -> None:
        """Register on_connect / on_disconnect callbacks on the MQTT client."""

        def _on_connect(
            client: Any, userdata: Any, flags: Any, rc: Any, props: Any = None
        ) -> None:
            if rc == 0:
                self._connected = True
                log.info("mqtt_publisher.connected", host=self._host, port=self._port)
            else:
                log.error("mqtt_publisher.connect_failed", rc=rc)

        def _on_disconnect(client: Any, userdata: Any, rc: Any, props: Any = None) -> None:
            self._connected = False
            log.warning("mqtt_publisher.disconnected", rc=rc)

        self._client.on_connect = _on_connect
        self._client.on_disconnect = _on_disconnect

    async def start(self) -> None:
        """Connect to the MQTT broker (non-blocking)."""
        if not _PAHO_AVAILABLE:
            raise RuntimeError("paho-mqtt not installed. Run: pip install paho-mqtt>=2.0")

        self._client = mqtt.Client(client_id=self._client_id, protocol=mqtt.MQTTv5)

        if self._username:
            self._client.username_pw_set(self._username, self._password)

        if self._use_tls:
            self._client.tls_set_context(self._build_tls_context())

        self._setup_callbacks()

        self._client.connect_async(self._host, self._port, keepalive=60)
        self._client.loop_start()

        # Wait up to 10 s for connection
        for _ in range(100):
            if self._connected:
                break
            await asyncio.sleep(0.1)
        else:
            self._client.loop_stop()
            raise MQTTConnectionError(
                f"Could not connect to MQTT broker at {str(self._host)}:{self._port} within 10 s"
            )

        log.info(
            "mqtt_publisher.ready",
            broker=self._broker_url,
            site_id=self._site_id,
            tls=self._use_tls,
        )

    async def stop(self) -> None:
        """Disconnect cleanly from the MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        self._connected = False
        log.info("mqtt_publisher.stopped", site_id=self._site_id)

    # -----------------------------------------------------------------------
    # Publish helpers
    # -----------------------------------------------------------------------

    def _publish(self, topic: str, payload: dict) -> None:
        """Thread-safe publish. Silently discards if disconnected."""
        if not self._connected or self._client is None:
            log.warning("mqtt_publisher.publish_skipped", topic=topic, reason="disconnected")
            return
        result = self._client.publish(
            topic, self._dump(payload), qos=self._qos, retain=self._retain
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            log.warning("mqtt_publisher.publish_error", topic=topic, rc=result.rc)
        else:
            self._publish_count += 1

    async def publish_telemetry(
        self,
        soc: float,
        power_kw: float,
        temp_c: float,
        cycle_count: int = 0,
    ) -> None:
        """Publish the core BESS telemetry frame."""
        self._publish(
            self._topic("telemetry"),
            {
                "ts": time.time(),
                "site_id": self._site_id,
                "soc_pct": round(soc, 2),
                "power_kw": round(power_kw, 3),
                "temp_c": round(temp_c, 1),
                "cycle_count": cycle_count,
            },
        )

    async def publish_safety(self, is_safe: bool, watchdog_status: str = "ok") -> None:
        """Publish safety guard status."""
        self._publish(
            self._topic("safety"),
            {
                "ts": time.time(),
                "site_id": self._site_id,
                "is_safe": is_safe,
                "watchdog": watchdog_status,
            },
        )

    async def publish_ids(self, score: float, alert_count: int, trained: bool) -> None:
        """Publish AI-IDS anomaly detection result."""
        self._publish(
            self._topic("ids"),
            {
                "ts": time.time(),
                "site_id": self._site_id,
                "score": round(score, 4),
                "alert_count": alert_count,
                "trained": trained,
                "status": "alarm" if score > 0.7 else "nominal",
            },
        )

    async def publish_dispatch(self, dispatch_kw: float | None, inference_ms: float) -> None:
        """Publish ONNX dispatch command."""
        self._publish(
            self._topic("dispatch"),
            {
                "ts": time.time(),
                "site_id": self._site_id,
                "dispatch_kw": dispatch_kw,
                "inference_ms": round(inference_ms, 2),
            },
        )

    async def publish_heartbeat(self) -> None:
        """Publish liveness heartbeat."""
        self._publish(
            self._topic("heartbeat"),
            {"ts": time.time(), "site_id": self._site_id},
        )

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def publish_count(self) -> int:
        return self._publish_count

    @property
    def is_available(self) -> bool:
        return _PAHO_AVAILABLE
