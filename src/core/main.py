"""
src/core/main.py
=================
BESSAI Edge Gateway — Main Orchestrator.

Entry point for the async acquisition loop.  Brings together:

1. ``Settings``         — reads all configuration from environment.
2. ``configure_otel``   — bootstraps distributed tracing & metrics.
3. ``UniversalDriver``  — connects to the BESS device via Modbus TCP.
4. ``SafetyGuard``      — validates telemetry before forwarding.
5. ``PubSubPublisher``  — publishes safe telemetry to GCP Pub/Sub.
6. ``watchdog_loop``    — background heartbeat task (auto-restarted if it dies).
7. ``HealthServer``     — HTTP /health + /metrics endpoints on port 8000.

Lifecycle
---------
::

    startup → connect → while True { acquire → safety → watchdog → publish → sleep }
                                                                              ↓
    SIGINT/SIGTERM ──────────────────────────────────────────── graceful shutdown

Run
---
::

    python -m src.core.main
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from importlib.metadata import version as _pkg_version
from typing import Any

try:
    _GATEWAY_VERSION: str = _pkg_version("bessai-edge")
except Exception:
    _GATEWAY_VERSION = "dev"

import structlog

from src.core.config import get_settings
from src.core.safety import SafetyGuard
from src.drivers.base import DataProvider
from src.drivers.modbus_driver import UniversalDriver
from src.drivers.simulator_driver import SimMode, SimulatorDriver
from src.interfaces.health import HealthServer
from src.interfaces.metrics import (
    CYCLES_TOTAL,
    GATEWAY_INFO,
    LAST_CYCLE_DURATION_S,
    LAST_POWER_KW,
    LAST_SOC_PERCENT,
    PUBLISH_ERRORS_TOTAL,
    SAFETY_BLOCKS_TOTAL,
)
from src.interfaces.otel_setup import configure_otel, get_tracer, shutdown_otel
from src.interfaces.pubsub_publisher import PubSubPublisher

# Resolve settings once at module level (safe — uses _LazySettings proxy)
_cfg = get_settings()

# ---------------------------------------------------------------------------
# Step 1 — Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Tags read on every acquisition cycle
# ---------------------------------------------------------------------------
_ACQUISITION_TAGS: list[str] = ["active_power", "soc"]

# ---------------------------------------------------------------------------
# Graceful shutdown — shared event set by signal handlers
# ---------------------------------------------------------------------------
_shutdown_event: asyncio.Event


def _handle_signal(sig: signal.Signals) -> None:
    """Mark the shutdown event so the main loop exits cleanly."""
    log.warning("shutdown.signal_received", signal=sig.name)
    _shutdown_event.set()


# ---------------------------------------------------------------------------
# Helper — read all configured tags in one cycle
# ---------------------------------------------------------------------------


async def _acquire(driver: DataProvider) -> dict[str, Any]:
    """
    Read ``_ACQUISITION_TAGS`` from the device.  Tags that fail are logged
    and skipped so a single bad register does not block valid readings.
    """
    telemetry: dict[str, Any] = {}
    for tag in _ACQUISITION_TAGS:
        try:
            telemetry[tag] = await driver.read_tag(tag)
        except Exception as exc:
            log.warning("acquire.tag.skip", tag=tag, error=str(exc))
    return telemetry


# ---------------------------------------------------------------------------
# Helper — ensure the watchdog task is alive; (re)start if needed
# ---------------------------------------------------------------------------


def _ensure_watchdog(
    guard: SafetyGuard,
    driver: DataProvider,
    watchdog_ref: list[asyncio.Task[None]],
) -> None:
    """
    Start the watchdog background task if it is not currently running.

    *watchdog_ref* is a one-element list used as a mutable reference so
    callers can inspect the current task object.
    """
    task: asyncio.Task[None] | None = watchdog_ref[0] if watchdog_ref else None

    if task is None or task.done():
        if task is not None and not task.cancelled():
            exc = task.exception()
            if exc:
                log.critical(
                    "watchdog.died",
                    error=str(exc),
                    action="restarting",
                )

        new_task: asyncio.Task[None] = asyncio.create_task(
            guard.watchdog_loop(driver), name="watchdog"
        )
        if watchdog_ref:
            watchdog_ref[0] = new_task
        else:
            watchdog_ref.append(new_task)

        log.info("watchdog.started_or_restarted")


# ---------------------------------------------------------------------------
# Main coroutine
# ---------------------------------------------------------------------------


async def main() -> None:  # noqa: C901
    """
    Bootstrap and run the BESSAI Edge Gateway until a shutdown signal.
    """
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    # ── Register OS signal handlers ───────────────────────────────────────
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal, sig)

    # ── Step 2 — OpenTelemetry ────────────────────────────────────────────
    configure_otel()
    tracer = get_tracer()

    # ── Step 3 — Driver instantiation (factory: sim ↔ real) ─────────────
    # Decision logic:
    #   BESSAI_MODE=demo        → always SimulatorDriver
    #   BESSAI_MODE=production  → always UniversalDriver (fails if IP missing)
    #   BESSAI_MODE=auto (def.) → SimulatorDriver if INVERTER_IP not set, else UniversalDriver
    _bessai_mode = os.getenv("BESSAI_MODE", "auto").lower()
    _inverter_ip = getattr(_cfg, "inverter_ip_str", None) or os.getenv("INVERTER_IP", "")

    _use_sim = _bessai_mode == "demo" or (_bessai_mode == "auto" and not _inverter_ip)

    driver: DataProvider
    if _use_sim:
        _sim_mode = os.getenv("BESSAI_SIM_MODE", SimMode.NORMAL)
        _profile = getattr(_cfg, "DEVICE_PROFILE", "huawei_sun2000")
        driver = SimulatorDriver(
            profile=_profile,
            mode=_sim_mode,
        )
        log.info(
            "startup.driver.sim",
            profile=_profile,
            sim_mode=_sim_mode,
            tip="Set INVERTER_IP in .env to switch to real hardware",
        )
    else:
        driver = UniversalDriver(
            host=_cfg.inverter_ip_str,
            port=_cfg.INVERTER_PORT,
            profile_path=_cfg.driver_profile_abs,
        )
        log.info(
            "startup.driver.real",
            host=_cfg.inverter_ip_str,
            port=_cfg.INVERTER_PORT,
        )

    # ── Step 4 — Connect (fail fast if unreachable) ───────────────────────
    try:
        await driver.connect()
    except Exception as exc:
        log.critical(
            "startup.driver_connect_failed",
            error=str(exc),
            action="exiting",
        )
        return

    # ── Step 5b — Health & Metrics server ────────────────────────────────
    health_server = HealthServer(
        site_id=_cfg.SITE_ID,
        version=_GATEWAY_VERSION,
        port=_cfg.HEALTH_PORT,
    )
    # Register static info gauge
    GATEWAY_INFO.labels(site_id=_cfg.SITE_ID, version=_GATEWAY_VERSION).set(1)

    # ── Step 5 — Safety guard, publisher, watchdog reference ─────────────
    guard = SafetyGuard(watchdog_interval_s=1.0)
    watchdog_ref: list[asyncio.Task[None]] = []  # mutable single-element ref

    if not _cfg.GCP_PROJECT_ID:
        raise ValueError(
            "GCP_PROJECT_ID is required. Set it in config/.env or as an environment variable."
        )
    if not _cfg.GCP_PUBSUB_TOPIC:
        raise ValueError(
            "GCP_PUBSUB_TOPIC is required. Set it in config/.env or as an environment variable."
        )
    async with (
        PubSubPublisher(
            project_id=_cfg.GCP_PROJECT_ID,
            topic_name=_cfg.GCP_PUBSUB_TOPIC,
        ) as publisher,
        health_server.run(),
    ):
        log.info(
            "gateway.started",
            site=_cfg.SITE_ID,
            inverter=_cfg.inverter_ip_str,
            poll_interval_s=_cfg.WATCHDOG_TIMEOUT,
            health_port=_cfg.HEALTH_PORT,
        )

        cycle: int = 0

        # ── Infinite acquisition loop ─────────────────────────────────────
        while not _shutdown_event.is_set():
            cycle += 1
            cycle_start = time.monotonic()

            with tracer.start_as_current_span("bess.cycle") as span:
                span.set_attribute("cycle", cycle)
                span.set_attribute("site_id", _cfg.SITE_ID)

                # ── STEP 1: Adquisición ───────────────────────────────────
                telemetry = await _acquire(driver)

                if not telemetry:
                    log.warning("cycle.empty_telemetry", cycle=cycle)
                    health_server.last_cycle_ok = False
                    await asyncio.sleep(_cfg.WATCHDOG_TIMEOUT)
                    continue

                span.set_attribute("tags_acquired", list(telemetry.keys()))

                # Update telemetry gauges
                if "soc" in telemetry:
                    LAST_SOC_PERCENT.labels(site_id=_cfg.SITE_ID).set(float(telemetry["soc"]))
                if "active_power" in telemetry:
                    LAST_POWER_KW.labels(site_id=_cfg.SITE_ID).set(
                        float(telemetry["active_power"]) / 1000.0
                    )

                # ── STEP 2: Seguridad ─────────────────────────────────────
                is_safe = guard.check_safety(telemetry)
                span.set_attribute("safety_ok", is_safe)

                if not is_safe:
                    log.critical(
                        "SAFETY_BLOCK",
                        cycle=cycle,
                        telemetry=telemetry,
                        action="HALTING_PUBLISH — manual intervention required",
                    )
                    SAFETY_BLOCKS_TOTAL.labels(site_id=_cfg.SITE_ID, reason="out_of_range").inc()
                    health_server.safety_status = "BLOCKED"
                    health_server.last_cycle_ok = False
                    await asyncio.sleep(_cfg.WATCHDOG_TIMEOUT)
                    continue

                health_server.safety_status = "ok"

                # ── STEP 3: Watchdog ──────────────────────────────────────
                _ensure_watchdog(guard, driver, watchdog_ref)

                # ── STEP 4: Publicación ───────────────────────────────────
                try:
                    msg_id = await publisher.publish(telemetry)
                    log.info(
                        "cycle.published",
                        cycle=cycle,
                        message_id=msg_id,
                        telemetry=telemetry,
                    )
                except Exception as exc:
                    log.error(
                        "cycle.publish_failed",
                        cycle=cycle,
                        error=str(exc),
                    )
                    PUBLISH_ERRORS_TOTAL.labels(site_id=_cfg.SITE_ID).inc()
                    span.record_exception(exc)

                # Update cycle counters
                CYCLES_TOTAL.labels(site_id=_cfg.SITE_ID).inc()
                LAST_CYCLE_DURATION_S.labels(site_id=_cfg.SITE_ID).set(
                    time.monotonic() - cycle_start
                )
                health_server.last_cycle = cycle
                health_server.last_cycle_ok = True

                # ── STEP 5: Ritmo ─────────────────────────────────────────
                await asyncio.sleep(_cfg.WATCHDOG_TIMEOUT)

        # ── Graceful shutdown ─────────────────────────────────────────────
        log.info("shutdown.starting")

        if watchdog_ref and not watchdog_ref[0].done():
            watchdog_ref[0].cancel()
            try:
                await watchdog_ref[0]
            except (asyncio.CancelledError, Exception):
                pass

    # PubSubPublisher.__aexit__ already closed the session here.
    await driver.disconnect()
    shutdown_otel()
    log.info("shutdown.complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Handled via signal handler inside main()
