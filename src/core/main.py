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
import signal
from typing import Any

import structlog

from src.core.config import get_settings
from src.core.safety import SafetyGuard
from src.drivers.modbus_driver import UniversalDriver
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

async def _acquire(driver: UniversalDriver) -> dict[str, Any]:
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
    driver: UniversalDriver,
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

async def main() -> None:
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

    # ── Step 3 — Driver instantiation ────────────────────────────────────
    driver = UniversalDriver(
        host=_cfg.inverter_ip_str,
        port=_cfg.INVERTER_PORT,
        profile_path=_cfg.driver_profile_abs,
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

    # ── Step 5 — Safety guard, publisher, watchdog reference ─────────────
    guard = SafetyGuard(watchdog_interval_s=1.0)
    watchdog_ref: list[asyncio.Task[None]] = []   # mutable single-element ref

    async with PubSubPublisher(
        project_id=_cfg.GCP_PROJECT_ID,        # type: ignore[attr-defined]
        topic_name=_cfg.GCP_PUBSUB_TOPIC,      # type: ignore[attr-defined]
    ) as publisher:

        log.info(
            "gateway.started",
            site=_cfg.SITE_ID,
            inverter=_cfg.inverter_ip_str,
            poll_interval_s=_cfg.WATCHDOG_TIMEOUT,
        )

        cycle: int = 0

        # ── Infinite acquisition loop ─────────────────────────────────────
        while not _shutdown_event.is_set():
            cycle += 1

            with tracer.start_as_current_span("bess.cycle") as span:
                span.set_attribute("cycle", cycle)
                span.set_attribute("site_id", _cfg.SITE_ID)

                # ── STEP 1: Adquisición ───────────────────────────────────
                telemetry = await _acquire(driver)

                if not telemetry:
                    log.warning("cycle.empty_telemetry", cycle=cycle)
                    await asyncio.sleep(_cfg.WATCHDOG_TIMEOUT)
                    continue

                span.set_attribute("tags_acquired", list(telemetry.keys()))

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
                    # Do NOT publish; wait for next cycle.
                    # In a real deployment this would trigger a hardware relay.
                    await asyncio.sleep(_cfg.WATCHDOG_TIMEOUT)
                    continue

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
                    span.record_exception(exc)

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
