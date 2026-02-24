# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/interfaces/sep2_adapter.py
================================
BESSAI Edge Gateway — IEEE 2030.5 (SEP 2.0) Adapter
BEP-0100 · Status: Draft → Active

Overview
--------
This module implements an IEEE 2030.5-compliant REST server that enables
BESSAI Edge Gateways to register as DER (Distributed Energy Resource)
devices with utility DERMS (Distributed Energy Resource Management Systems).

Compliance Targets
------------------
- California CPUC Rule 21 (DER interconnection above threshold capacity)
- AEMO AS/NZS 4777.2 (Australia grid-connected DER)
- FERC Order 2222 (aggregated DER market participation)
- IEEE 2030.5-2018 §§ 5, 8, 10 (EndDevice, DER, MirrorUsagePoint)

Architecture
------------
::

    DERMS head-end         BESSAI Edge Gateway
    (utility)              (this module)
    ─────────────          ─────────────────────────────────────────────
    GET /edev          ──► SEP2Adapter.handle_edev()
    GET /edev/0/der/0  ──► SEP2Adapter.handle_der_status()   → read_tag()
    POST /edev/0/derp  ──► SEP2Adapter.handle_der_control()  → write_tag()
    GET /tm            ──► SEP2Adapter.handle_time()
    POST /mup          ◄── SEP2Adapter.push_mirror_usage()   (periodic)

All communication MUST use TLS 1.2+ (mTLS for production deployments).

Configuration Environment Variables
------------------------------------
SEP2_ENABLED        = true | false   (default: false — opt-in)
SEP2_PORT           = 8443           (default: 8443)
SEP2_HOST           = 0.0.0.0        (default: 0.0.0.0)
SEP2_TLS_CERT       = /certs/server.crt
SEP2_TLS_KEY        = /certs/server.key
SEP2_TLS_CA         = /certs/ca.crt  (set for mTLS; unset for TLS-only)
SEP2_REQUIRE_MTLS   = true | false   (default: true — require client cert)
SEP2_LFDI           = <hex-string>   (LFDI of this device; auto-derived from cert)
SEP2_MAX_W          = 100000         (max power in W from device profile)
SEP2_MAX_WH         = 400000         (battery capacity in Wh from device profile)
SEP2_DERMS_MUP_URL  = https://...    (DERMS MirrorUsagePoint URL; optional)
SEP2_MUP_INTERVAL   = 300           (MirrorUsagePoint posting interval in s)

Usage
-----
::

    from src.interfaces.sep2_adapter import SEP2Adapter

    adapter = SEP2Adapter(driver=driver)
    await adapter.start()   # blocks until stop() is called
    await adapter.stop()

Or integrated in main.py via the SEP2_ENABLED env flag (fail-safe):

::

    if os.getenv("SEP2_ENABLED", "false").lower() == "true":
        adapter = SEP2Adapter(driver=driver)
        asyncio.create_task(adapter.start())
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import ssl
import time
from typing import Any

import structlog

try:
    import aiohttp as _aiohttp
    from aiohttp import web as _web

    _AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    _aiohttp = None  # type: ignore[assignment]
    _web = None  # type: ignore[assignment]
    _AIOHTTP_AVAILABLE = False

from src.drivers.base import DataProvider

__all__ = ["SEP2Adapter", "SEP2Error", "SEP2ConfigError"]

log = structlog.get_logger(__name__)


def _make_json_response(body: str, content_type: str, status: int) -> Any:
    """
    Create an aiohttp JSON Response.

    Centralises all access to ``aiohttp._web.Response`` in one place so that
    static analysers (Pyre2 / Pyright) only need to trust that this helper
    is correct, rather than reasoning about the ``try/except ImportError``
    guard that affects the module-level ``_web`` binding.
    """
    return _web.Response(text=body, content_type=content_type, status=status)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SEP2Error(RuntimeError):
    """Base exception for all SEP 2.0 adapter errors."""


class SEP2ConfigError(SEP2Error):
    """Raised when adapter is misconfigured (e.g. missing cert paths)."""


# ---------------------------------------------------------------------------
# DER Status / Control constants  (IEEE 2030.5-2018 Table A-12)
# ---------------------------------------------------------------------------

_STORAGE_MODE_CHARGING = 3
_STORAGE_MODE_DISCHARGING = 4
_STORAGE_MODE_IDLE = 5

_OP_MODE_NORMAL = 1
_OP_MODE_STANDBY = 99

# Scale factor: IEEE 2030.5 uses fixed-point ×100 for SoC (0-10000 = 0-100%)
_SOC_SCALE = 100


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _storage_mode_from_power(active_power_kw: float) -> int:
    """Derive IEEE 2030.5 storageModeStatus from active_power_kw."""
    if active_power_kw > 0.1:
        return _STORAGE_MODE_DISCHARGING
    if active_power_kw < -0.1:
        return _STORAGE_MODE_CHARGING
    return _STORAGE_MODE_IDLE


def _derive_lfdi(cert_path: str | None) -> str:
    """
    Derive the LFDI (Long Form Device Identifier) from the TLS certificate.

    IEEE 2030.5-2018 §8.2: LFDI = SHA-256 of DER-encoded certificate,
    truncated to left-most 20 octets, hex-encoded.

    Falls back to a deterministic hex derived from SITE_ID + hostname
    if no cert is available (dev/test mode).
    """
    if cert_path and os.path.exists(cert_path):
        try:
            with open(cert_path, "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()
            return digest[:40].upper()
        except OSError:
            pass

    # Fallback: deterministic from env
    site_id = os.getenv("SITE_ID", "BESSAI-EDGE")
    import socket

    hostname = socket.gethostname()
    fallback = hashlib.sha256(f"{site_id}:{hostname}".encode()).hexdigest()
    return fallback[:40].upper()


# ---------------------------------------------------------------------------
# SEP2Adapter
# ---------------------------------------------------------------------------


class SEP2Adapter:
    """
    IEEE 2030.5 (SEP 2.0) REST server adapter for BESSAI Edge Gateway.

    Exposes the minimum DER endpoint set required for:
    - CPUC Rule 21 Cat B compliance (California)
    - AEMO AS/NZS 4777.2 (Australia)
    - FERC Order 2222 aggregated DER participation

    All JSON responses use the ``application/sep+json`` content-type
    (non-normative JSON profile of IEEE 2030.5).  Full XML per the
    normative spec is planned in BEP-0101.

    Parameters
    ----------
    driver:
        A ``DataProvider`` instance providing ``read_tag()`` / ``write_tag()``.
    host:
        Bind address (default: ``0.0.0.0`` or ``SEP2_HOST`` env var).
    port:
        Listening port (default: ``8443`` or ``SEP2_PORT`` env var).
    tls_cert:
        Path to server TLS certificate PEM (or ``SEP2_TLS_CERT``).
    tls_key:
        Path to server TLS private key PEM (or ``SEP2_TLS_KEY``).
    tls_ca:
        Path to CA cert PEM for mTLS client auth (or ``SEP2_TLS_CA``).
    require_mtls:
        Whether to require client certificates (default: True).
    max_w:
        Device maximum power in Watts (from device profile / config).
    max_wh:
        Battery capacity in Watt-hours (from device profile / config).
    derms_mup_url:
        URL of the DERMS MirrorUsagePoint resource (optional).
    mup_interval_s:
        Interval in seconds to push MirrorUsagePoint data (default: 300).
    """

    _CONTENT_TYPE = "application/sep+json"

    def __init__(
        self,
        driver: DataProvider,
        host: str | None = None,
        port: int | None = None,
        tls_cert: str | None = None,
        tls_key: str | None = None,
        tls_ca: str | None = None,
        require_mtls: bool | None = None,
        max_w: int | None = None,
        max_wh: int | None = None,
        derms_mup_url: str | None = None,
        mup_interval_s: int | None = None,
    ) -> None:
        if not _AIOHTTP_AVAILABLE:
            raise SEP2ConfigError(
                "aiohttp is required for IEEE 2030.5 adapter. Run: pip install aiohttp>=3.9"
            )

        self._driver = driver
        self._host = host or os.getenv("SEP2_HOST", "0.0.0.0")
        self._port = port or int(os.getenv("SEP2_PORT", "8443"))
        self._tls_cert = tls_cert or os.getenv("SEP2_TLS_CERT")
        self._tls_key = tls_key or os.getenv("SEP2_TLS_KEY")
        self._tls_ca = tls_ca or os.getenv("SEP2_TLS_CA")

        _require_mtls_env = os.getenv("SEP2_REQUIRE_MTLS", "true").lower() == "true"
        self._require_mtls = require_mtls if require_mtls is not None else _require_mtls_env

        self._max_w = max_w or int(os.getenv("SEP2_MAX_W", "100000"))
        self._max_wh = max_wh or int(os.getenv("SEP2_MAX_WH", "400000"))
        self._derms_mup_url = derms_mup_url or os.getenv("SEP2_DERMS_MUP_URL")
        self._mup_interval_s = mup_interval_s or int(os.getenv("SEP2_MUP_INTERVAL", "300"))

        _lfdi_env = os.getenv("SEP2_LFDI")
        self._lfdi = _lfdi_env or _derive_lfdi(self._tls_cert)

        self._site_id = os.getenv("SITE_ID", "BESSAI-EDGE")
        self._runner: Any = None
        self._mup_task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """
        Start the IEEE 2030.5 REST server.

        Builds the TLS context, creates the aiohttp Application,
        registers routes, and starts the TCP server.  Also launches
        the optional MirrorUsagePoint push task.

        Raises
        ------
        SEP2ConfigError
            If TLS cert/key are not found or TLS context cannot be built.
        SEP2Error
            If the server fails to bind.
        """
        ssl_ctx = self._build_ssl_context()

        app = _web.Application()
        self._register_routes(app)

        self._runner = _web.AppRunner(app)
        await self._runner.setup()

        site = _web.TCPSite(
            self._runner,
            host=self._host,
            port=self._port,
            ssl_context=ssl_ctx,
        )
        await site.start()
        self._running = True

        log.info(
            "sep2_adapter.started",
            host=self._host,
            port=self._port,
            lfdi=self._lfdi,
            mtls=self._require_mtls,
            tls=ssl_ctx is not None,
        )

        if self._derms_mup_url:
            self._mup_task = asyncio.create_task(self._mup_push_loop(), name="sep2_mup_push")

    async def stop(self) -> None:
        """Gracefully stop the IEEE 2030.5 server and cancel the MUP push task."""
        self._running = False

        if self._mup_task is not None and not self._mup_task.done():
            self._mup_task.cancel()
            mup_task = self._mup_task  # narrow type for await
            try:
                await mup_task
            except asyncio.CancelledError:
                pass

        if self._runner:
            await self._runner.cleanup()

        log.info("sep2_adapter.stopped")

    # ------------------------------------------------------------------
    # TLS / SSL Context
    # ------------------------------------------------------------------

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        """
        Build the SSL context for the server.

        Returns None if neither cert nor key are configured (dev/test mode
        without TLS — NOT suitable for production).
        """
        if not self._tls_cert or not self._tls_key:
            log.warning(
                "sep2_adapter.tls_disabled",
                action="running_without_tls",
                note="NOT suitable for production deployment",
            )
            return None

        if not os.path.exists(self._tls_cert):
            raise SEP2ConfigError(f"TLS cert not found: {self._tls_cert}")
        if not os.path.exists(self._tls_key):
            raise SEP2ConfigError(f"TLS key not found: {self._tls_key}")

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(certfile=self._tls_cert, keyfile=self._tls_key)

        if self._require_mtls:
            if not self._tls_ca:
                raise SEP2ConfigError("SEP2_TLS_CA must be set when SEP2_REQUIRE_MTLS=true")
            if not os.path.exists(self._tls_ca):
                raise SEP2ConfigError(f"TLS CA not found: {self._tls_ca}")
            ctx.load_verify_locations(cafile=self._tls_ca)
            ctx.verify_mode = ssl.CERT_REQUIRED

        log.info(
            "sep2_adapter.tls_configured",
            cert=self._tls_cert,
            mtls=self._require_mtls,
            ca=self._tls_ca,
        )
        return ctx

    # ------------------------------------------------------------------
    # Route registration
    # ------------------------------------------------------------------

    def _register_routes(self, app: Any) -> None:
        """Register all IEEE 2030.5 REST endpoints."""
        router = app.router
        # Time resource (§8.3 — MUST be implemented)
        router.add_get("/tm", self.handle_time)
        # EndDevice list (§8.4)
        router.add_get("/edev", self.handle_edev_list)
        # EndDevice (§8.4.2)
        router.add_get("/edev/{edev_id}", self.handle_edev)
        # DER list (§10.3)
        router.add_get("/edev/{edev_id}/der", self.handle_der_list)
        # DER Status (§10.5)
        router.add_get("/edev/{edev_id}/der/{der_id}/derStatus", self.handle_der_status)
        # DER Settings (§10.6 — capability declaration)
        router.add_get("/edev/{edev_id}/der/{der_id}/derSettings", self.handle_der_settings)
        # DER Capability (§10.4)
        router.add_get("/edev/{edev_id}/der/{der_id}/derCapability", self.handle_der_capability)
        # DER Program list (§10.7 — accept DERControl from DERMS)
        router.add_get("/edev/{edev_id}/derp", self.handle_der_program_list)
        # DERControl (§10.9 — DERMS sends dispatch commands here)
        router.add_post("/edev/{edev_id}/derp/{program_id}/derc", self.handle_der_control)
        # MirrorUsagePoint (§11 — BESSAI pushes to DERMS)
        router.add_post("/mup", self.handle_mirror_usage_point)

    # ------------------------------------------------------------------
    # IEEE 2030.5 endpoint handlers
    # ------------------------------------------------------------------

    async def handle_time(self, request: Any) -> Any:
        """
        GET /tm — TimeResource (IEEE 2030.5 §8.3).

        MUST be implemented per spec. Returns current UTC epoch time.
        """
        now = int(time.time())
        body = {
            "type": "TimeResource",
            "currentTime": now,
            "dstEndTime": 0,
            "dstOffset": 0,
            "dstStartTime": 0,
            "localTime": now,
            "quality": 7,
            "tzOffset": 0,
        }
        return _web.Response(
            text=_json_dumps(body),
            content_type=self._CONTENT_TYPE,
            status=200,
        )

    async def handle_edev_list(self, request: Any) -> Any:
        """GET /edev — EndDeviceList (IEEE 2030.5 §8.4)."""
        body = {
            "type": "EndDeviceList",
            "all": 1,
            "results": 1,
            "EndDevice": [self._build_edev_resource()],
        }
        return _web.Response(
            text=_json_dumps(body),
            content_type=self._CONTENT_TYPE,
            status=200,
        )

    async def handle_edev(self, request: Any) -> Any:
        """GET /edev/{edev_id} — EndDevice resource (IEEE 2030.5 §8.4.2)."""
        return _web.Response(
            text=_json_dumps(self._build_edev_resource()),
            content_type=self._CONTENT_TYPE,
            status=200,
        )

    async def handle_der_list(self, request: Any) -> Any:
        """GET /edev/{edev_id}/der — DER list for this EndDevice (§10.3)."""
        body = {
            "type": "DERList",
            "all": 1,
            "results": 1,
            "DER": [{"href": "/edev/0/der/0"}],
        }
        return _web.Response(
            text=_json_dumps(body),
            content_type=self._CONTENT_TYPE,
            status=200,
        )

    async def handle_der_status(self, request: Any) -> Any:
        """
        GET /edev/{edev_id}/der/{der_id}/derStatus — current DER status.

        Reads live telemetry from the DataProvider and maps to
        IEEE 2030.5 DERStatus fields per BEP-0100 §DERStatus Mapping.
        """
        try:
            soc = await self._driver.read_tag("soc_pct")
        except Exception:
            soc = 0.0

        try:
            power_kw = await self._driver.read_tag("active_power_kw")
        except Exception:
            power_kw = 0.0

        try:
            op_mode_raw = await self._driver.read_tag("operating_mode")
        except Exception:
            op_mode_raw = float(_OP_MODE_NORMAL)

        soc_fixed = int(soc * _SOC_SCALE)  # ×100 per IEEE 2030.5 fixed-point
        storage_mode = _storage_mode_from_power(power_kw)
        op_mode = _OP_MODE_STANDBY if int(op_mode_raw) == _OP_MODE_STANDBY else _OP_MODE_NORMAL

        body = {
            "type": "DERStatus",
            "readingTime": int(time.time()),
            "operationalModeStatus": {"value": op_mode},
            "stateOfChargeStatus": {"value": soc_fixed},
            "storageModeStatus": {"value": storage_mode},
            "inverterStatus": {"value": 1 if self._driver.is_connected else 6},
        }
        return _web.Response(
            text=_json_dumps(body),
            content_type=self._CONTENT_TYPE,
            status=200,
        )

    async def handle_der_settings(self, request: Any) -> Any:
        """
        GET /edev/{edev_id}/der/{der_id}/derSettings — capability settings.

        Declares device limits that the DERMS uses for scheduling.
        """
        body = {
            "type": "DERSettings",
            "setMaxW": {"value": self._max_w, "multiplier": 0},
            "setMaxWh": {"value": self._max_wh, "multiplier": 0},
            "setMinW": {"value": 0, "multiplier": 0},
            "setGradW": 1638,  # default ramp rate 10%/min in IEEE 2030.5 units
            "setMaxChargeRateW": {"value": self._max_w, "multiplier": 0},
            "setMaxDischargeRateW": {"value": self._max_w, "multiplier": 0},
            "updatedTime": int(time.time()),
        }
        return _web.Response(
            text=_json_dumps(body),
            content_type=self._CONTENT_TYPE,
            status=200,
        )

    async def handle_der_capability(self, request: Any) -> Any:
        """GET /edev/{edev_id}/der/{der_id}/derCapability (§10.4)."""
        body = {
            "type": "DERCapability",
            "modesSupported": "fa",  # bitmap: opModConnect + setMaxW + opModEnergize
            "rtgMaxW": {"value": self._max_w, "multiplier": 0},
            "rtgMaxWh": {"value": self._max_wh, "multiplier": 0},
            "rtgMinPFNormalOperation": {"value": 95, "multiplier": -2},
            "type_": 80,  # DERType: other storage
        }
        return _web.Response(
            text=_json_dumps(body),
            content_type=self._CONTENT_TYPE,
            status=200,
        )

    async def handle_der_program_list(self, request: Any) -> Any:
        """GET /edev/{edev_id}/derp — DERProgram list (§10.7)."""
        body = {
            "type": "DERProgramList",
            "all": 1,
            "results": 1,
            "DERProgram": [
                {
                    "href": "/edev/0/derp/0",
                    "description": "BESSAI DR Program",
                    "primacy": 0,
                }
            ],
        }
        return _web.Response(
            text=_json_dumps(body),
            content_type=self._CONTENT_TYPE,
            status=200,
        )

    async def handle_der_control(self, request: Any) -> Any:
        """
        POST /edev/{edev_id}/derp/{program_id}/derc — DERControl from DERMS.

        Receives a DERControl command from the utility DERMS and maps it to
        the appropriate ``write_tag()`` call on the DataProvider.

        Supported controls (BEP-0100 §DERControl Mapping):
        - ``opModConnect: false``  → ``write_tag("operating_mode", <standby>)``
        - ``setMaxW: N``           → ``write_tag("P_setpoint_kW", N/1000)``
        - ``opModEnergize: true``  → ``write_tag("operating_mode", <charge>)``

        Returns 201 Created on success, 400 on validation error,
        503 if driver is not connected.
        """
        if not self._driver.is_connected:
            return _web.Response(
                text=_json_dumps({"error": "DER not connected"}),
                content_type=self._CONTENT_TYPE,
                status=503,
            )

        try:
            payload: dict = await request.json()
        except Exception:
            return _web.Response(
                text=_json_dumps({"error": "Invalid JSON payload"}),
                content_type=self._CONTENT_TYPE,
                status=400,
            )

        der_control_base: dict = payload.get("DERControlBase", {})
        errors: list[str] = []

        # --- opModConnect: false → standby ---
        if "opModConnect" in der_control_base:
            val = der_control_base["opModConnect"]
            if val is False:
                try:
                    await self._driver.write_tag("operating_mode", float(_OP_MODE_STANDBY))
                    log.info("sep2_adapter.control.standby", lfdi=self._lfdi)
                except Exception as exc:
                    errors.append(f"write_tag(operating_mode=standby) failed: {exc}")

        # --- setMaxW: N → P_setpoint_kW = N/1000 ---
        if "setMaxW" in der_control_base:
            raw_w = der_control_base["setMaxW"]
            if isinstance(raw_w, dict):
                value_w = raw_w.get("value", 0)
                mult = raw_w.get("multiplier", 0)
                target_w = float(value_w) * (10**mult)
            else:
                target_w = float(raw_w)

            if target_w > self._max_w:
                errors.append(f"setMaxW={target_w}W exceeds device limit={self._max_w}W")
            else:
                try:
                    await self._driver.write_tag("P_setpoint_kW", target_w / 1000.0)
                    log.info(
                        "sep2_adapter.control.set_max_w",
                        target_kw=target_w / 1000.0,
                        lfdi=self._lfdi,
                    )
                except Exception as exc:
                    errors.append(f"write_tag(P_setpoint_kW={target_w / 1000:.1f}) failed: {exc}")

        # --- opModEnergize: true → charge mode ---
        if "opModEnergize" in der_control_base:
            val = der_control_base["opModEnergize"]
            if val is True:
                try:
                    # Read current SOC before energizing (guard: SOC < 98%)
                    soc = await self._driver.read_tag("soc_pct")
                    if soc >= 98.0:
                        errors.append(
                            f"opModEnergize rejected: SOC={soc:.1f}% >= 98% (battery full)"
                        )
                    else:
                        await self._driver.write_tag("operating_mode", float(_OP_MODE_NORMAL))
                        log.info(
                            "sep2_adapter.control.energize",
                            soc=soc,
                            lfdi=self._lfdi,
                        )
                except Exception as exc:
                    errors.append(f"opModEnergize failed: {exc}")

        if errors:
            return _web.Response(
                text=_json_dumps({"errors": errors, "status": "partial_failure"}),
                content_type=self._CONTENT_TYPE,
                status=400,
            )

        return _web.Response(
            text=_json_dumps({"status": "accepted"}),
            content_type=self._CONTENT_TYPE,
            status=201,
        )

    async def handle_mirror_usage_point(self, request: Any) -> Any:
        """
        POST /mup — Receive MirrorUsagePoint registration from DERMS (§11).

        The DERMS may push a MUP resource to auto-register telemetry subscriptions.
        We acknowledge with 201.
        """
        try:
            payload = await request.json()
            log.info("sep2_adapter.mup.registered", payload=str(payload)[:200])
        except Exception:
            pass

        return _web.Response(
            text=_json_dumps({"status": "registered"}),
            content_type=self._CONTENT_TYPE,
            status=201,
        )

    # ------------------------------------------------------------------
    # MirrorUsagePoint push loop (BESSAI → DERMS)
    # ------------------------------------------------------------------

    async def _mup_push_loop(self) -> None:
        """
        Periodically push interval metering data to the DERMS as a
        MirrorUsagePoint reading (IEEE 2030.5 §11).

        Requires SEP2_DERMS_MUP_URL to be set.
        """
        if _aiohttp is None:  # pragma: no cover
            log.warning("sep2_adapter.mup.aiohttp_missing")
            return
        aiohttp = _aiohttp  # local alias with known type

        log.info(
            "sep2_adapter.mup.loop_started",
            url=self._derms_mup_url,
            interval_s=self._mup_interval_s,
        )

        ssl_ctx: ssl.SSLContext | None = None
        if self._tls_cert and self._tls_key:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_ctx.load_cert_chain(certfile=self._tls_cert, keyfile=self._tls_key)
            if self._tls_ca:
                ssl_ctx.load_verify_locations(cafile=self._tls_ca)
            else:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE

        while self._running:
            try:
                telemetry = await self._read_telemetry_snapshot()
                await self._post_mirror_usage_point(aiohttp, ssl_ctx, telemetry)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning(
                    "sep2_adapter.mup.push_failed",
                    error=str(exc),
                    action="will_retry_next_interval",
                )

            await asyncio.sleep(self._mup_interval_s)

    async def _read_telemetry_snapshot(self) -> dict:
        """Read current telemetry tags for MUP posting."""
        snapshot: dict = {}
        for tag in ("soc_pct", "active_power_kw", "battery_voltage_v", "temp_c"):
            try:
                snapshot[tag] = await self._driver.read_tag(tag)
            except Exception:
                snapshot[tag] = 0.0
        return snapshot

    async def _post_mirror_usage_point(
        self, aiohttp: Any, ssl_ctx: ssl.SSLContext | None, telemetry: dict
    ) -> None:
        """POST a MirrorMeterReading to the DERMS MirrorUsagePoint URL."""
        now = int(time.time())
        body = {
            "type": "MirrorUsagePoint",
            "deviceLFDI": self._lfdi,
            "MirrorMeterReading": [
                {
                    "lastUpdateTime": now,
                    "description": "BESSAI SOC",
                    "ReadingType": {"commodity": 4, "uom": 29},  # uom 29 = %SOC
                    "Reading": {"value": int(telemetry.get("soc_pct", 0.0) * 100)},
                },
                {
                    "lastUpdateTime": now,
                    "description": "BESSAI Active Power",
                    "ReadingType": {"commodity": 4, "uom": 38},  # uom 38 = W
                    "Reading": {"value": int(telemetry.get("active_power_kw", 0.0) * 1000)},
                },
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._derms_mup_url,
                data=_json_dumps(body),
                headers={"Content-Type": self._CONTENT_TYPE},
                ssl=ssl_ctx,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status not in (200, 201, 204):
                    log.warning(
                        "sep2_adapter.mup.unexpected_status",
                        status=resp.status,
                        url=self._derms_mup_url,
                    )
                else:
                    log.debug(
                        "sep2_adapter.mup.pushed",
                        soc=telemetry.get("soc_pct"),
                        power_kw=telemetry.get("active_power_kw"),
                    )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_edev_resource(self) -> dict:
        """Build the EndDevice resource object."""
        return {
            "type": "EndDevice",
            "href": "/edev/0",
            "sFDI": self._lfdi[-10:].upper(),  # Short-Form Device Identifier (40 bits)
            "lFDI": self._lfdi,
            "deviceCategory": "0000000000000000",  # hex bitmap: DER
            "enabled": True,
            "loadShedDeviceCategory": "0000000000000000",
            "subscribable": 0,
            "DERListLink": {"href": "/edev/0/der"},
            "DERProgramListLink": {"href": "/edev/0/derp"},
            "registrationLink": {"href": "/edev/0/reg"},
            "selfDeviceLink": {"href": "/edev/0"},
        }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _json_dumps(obj: Any) -> str:
    """Serialize to JSON without external dependency on orjson."""
    import json

    return json.dumps(obj, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Module-level factory (for integration with main.py)
# ---------------------------------------------------------------------------


def build_adapter_from_env(driver: DataProvider) -> SEP2Adapter | None:
    """
    Create a ``SEP2Adapter`` from environment variables.

    Returns ``None`` if ``SEP2_ENABLED`` is not ``"true"``.

    Designed to be called from ``main.py`` in a fail-safe block::

        adapter = build_adapter_from_env(driver)
        if adapter is not None:
            asyncio.create_task(adapter.start())
    """
    enabled = os.getenv("SEP2_ENABLED", "false").lower() == "true"
    if not enabled:
        return None

    if not _AIOHTTP_AVAILABLE:
        log.warning(
            "sep2_adapter.aiohttp_missing",
            action="sep2_disabled",
            tip="pip install aiohttp>=3.9",
        )
        return None

    return SEP2Adapter(driver=driver)
