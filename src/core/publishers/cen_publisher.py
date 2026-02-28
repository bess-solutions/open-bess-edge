# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/publishers/cen_publisher.py
======================================
CEN Telemetry Publisher — NTSyCS Cap. 6.1 + 6.2 (GAP-003).

Publishes real-time BESS telemetry to the Coordinador Eléctrico Nacional
(CEN) endpoint via HTTPS with mutual TLS (mTLS), as required by:

* NTSyCS Cap. 6.1 — Telemetría en tiempo real al CEN.
* NTSyCS 2024 Anexo 8 — Canal TLS dedicado (mTLS) entre el gateway
  edge y el SCADA del CEN.

Configuration (environment variables)
--------------------------------------
* ``CEN_ENDPOINT_URL`` — HTTPS endpoint provided by CEN (required for live mode).
* ``CEN_SITE_ID``      — Site identifier string (required).
* ``CEN_CA_CERT``      — Path to CEN Certificate Authority PEM file.
* ``CEN_CLIENT_CERT``  — Path to client certificate PEM file.
* ``CEN_CLIENT_KEY``   — Path to client private key PEM file.
* ``CEN_INTERVAL_S``   — Publish interval in seconds (default: 60).

If ``CEN_ENDPOINT_URL`` is not set, the publisher operates in **dry-run**
mode: payloads are logged but no network calls are made.

Usage
-----
::

    publisher = CENPublisher.from_env()
    await publisher.publish(telemetry)
"""

from __future__ import annotations

import json
import os
import ssl
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)

# Max retries on transient network errors
_MAX_RETRIES: int = 3
_RETRY_BACKOFF_BASE_S: float = 1.0  # doubles each retry


# ---------------------------------------------------------------------------
# Telemetry payload schema
# ---------------------------------------------------------------------------


@dataclass
class CENTelemetryPayload:
    """Structured telemetry payload as expected by the CEN endpoint."""

    timestamp: str           # ISO-8601 UTC
    site_id: str             # Site identifier from CEN contract
    soc_pct: float           # State of Charge (%)
    p_kw: float              # Active power (kW, + = discharge)
    q_kvar: float            # Reactive power (kVAr)
    f_hz: float              # Grid frequency (Hz)
    status: str              # "ONLINE" | "STANDBY" | "FAULT"
    bess_temp_c: float = 0.0 # Optional battery temperature (°C)


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------


class CENPublisher:
    """
    Publish BESS telemetry to the CEN endpoint with mTLS.

    Parameters
    ----------
    endpoint_url:
        Full HTTPS URL of the CEN telemetry receiver.
        If ``None`` or empty, operates in dry-run mode.
    site_id:
        Site identifier string from the CEN connection contract.
    ssl_context:
        Pre-built ``ssl.SSLContext`` with mTLS configured.
        If ``None``, the connection uses system CA store (for testing).
    interval_s:
        Publish interval in seconds (default 60 s per NTSyCS).
    dry_run:
        Force dry-run mode regardless of endpoint configuration.
    """

    def __init__(
        self,
        endpoint_url: str | None = None,
        site_id: str = "SITE-UNKNOWN",
        ssl_context: ssl.SSLContext | None = None,
        interval_s: float = 60.0,
        dry_run: bool = False,
    ) -> None:
        self._endpoint = endpoint_url
        self._site_id = site_id
        self._ssl_context = ssl_context
        self._interval_s = interval_s
        self._dry_run = dry_run or not endpoint_url

        log.info(
            "cen_publisher.initialized",
            endpoint=self._endpoint,
            site_id=self._site_id,
            interval_s=self._interval_s,
            dry_run=self._dry_run,
            mtls=ssl_context is not None,
            norm_ref="NTSyCS Cap. 6.1 / Anexo 8",
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "CENPublisher":
        """Create a CENPublisher from environment variables."""
        endpoint = os.environ.get("CEN_ENDPOINT_URL", "")
        site_id = os.environ.get("CEN_SITE_ID", "SITE-UNKNOWN")
        interval_s = float(os.environ.get("CEN_INTERVAL_S", "60"))

        ssl_ctx: ssl.SSLContext | None = None
        ca_cert = os.environ.get("CEN_CA_CERT")
        client_cert = os.environ.get("CEN_CLIENT_CERT")
        client_key = os.environ.get("CEN_CLIENT_KEY")

        if ca_cert and client_cert and client_key:
            ssl_ctx = cls._build_mtls_context(
                Path(ca_cert), Path(client_cert), Path(client_key)
            )

        return cls(
            endpoint_url=endpoint or None,
            site_id=site_id,
            ssl_context=ssl_ctx,
            interval_s=interval_s,
        )

    @staticmethod
    def _build_mtls_context(
        ca_cert: Path,
        client_cert: Path,
        client_key: Path,
    ) -> ssl.SSLContext:
        """Build an mTLS SSLContext from cert files."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cafile=str(ca_cert))
        ctx.load_cert_chain(certfile=str(client_cert), keyfile=str(client_key))
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        log.info(
            "cen_publisher.mtls_context_built",
            ca_cert=str(ca_cert),
            client_cert=str(client_cert),
        )
        return ctx

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def publish(self, telemetry: dict) -> bool:
        """
        Publish a telemetry snapshot to the CEN endpoint.

        Parameters
        ----------
        telemetry:
            Dict with keys: ``soc_pct``, ``p_kw``, ``q_kvar``,
            ``f_hz``, ``status``. Optional: ``bess_temp_c``.

        Returns
        -------
        bool
            ``True`` if published (or dry-run logged) successfully.
            ``False`` if all retries failed.
        """
        payload = CENTelemetryPayload(
            timestamp=datetime.now(timezone.utc).isoformat(),
            site_id=self._site_id,
            soc_pct=float(telemetry.get("soc_pct", 0.0)),
            p_kw=float(telemetry.get("p_kw", 0.0)),
            q_kvar=float(telemetry.get("q_kvar", 0.0)),
            f_hz=float(telemetry.get("f_hz", 50.0)),
            status=str(telemetry.get("status", "ONLINE")),
            bess_temp_c=float(telemetry.get("bess_temp_c", 0.0)),
        )

        if self._dry_run:
            log.info(
                "cen_publisher.dry_run.payload",
                payload=asdict(payload),
            )
            return True

        return await self._send_with_retry(payload)

    async def _send_with_retry(self, payload: CENTelemetryPayload) -> bool:
        """Send payload with exponential backoff retry logic."""
        import asyncio

        body = json.dumps(asdict(payload), ensure_ascii=False).encode("utf-8")

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                await self._do_http_post(body)
                log.info(
                    "cen_publisher.published",
                    attempt=attempt,
                    site_id=self._site_id,
                    timestamp=payload.timestamp,
                )
                return True
            except Exception as exc:
                wait = _RETRY_BACKOFF_BASE_S * (2 ** (attempt - 1))
                log.warning(
                    "cen_publisher.retry",
                    attempt=attempt,
                    max_attempts=_MAX_RETRIES,
                    error=str(exc),
                    retry_in_s=wait,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(wait)

        log.error("cen_publisher.all_retries_failed", site_id=self._site_id)
        return False

    async def _do_http_post(self, body: bytes) -> None:
        """Execute the HTTPS POST to the CEN endpoint."""
        import asyncio
        import urllib.request

        # Use asyncio executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()

        def _blocking_post() -> None:
            req = urllib.request.Request(
                self._endpoint,  # type: ignore[arg-type]
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "BESSAI-CENPublisher/1.0",
                },
            )
            ctx = self._ssl_context or ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                status = resp.status
                if status not in (200, 201, 204):
                    raise OSError(f"CEN endpoint returned HTTP {status}")

        await loop.run_in_executor(None, _blocking_post)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def dry_run(self) -> bool:
        """True if operating in dry-run mode (no network calls)."""
        return self._dry_run

    @property
    def interval_s(self) -> float:
        """Publish interval in seconds."""
        return self._interval_s
