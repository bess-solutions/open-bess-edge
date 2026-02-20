"""
src/core/safety.py
==================
Safety Guard for BESSAI Edge Gateway.

Implements two responsibilities:

1. **``SafetyGuard.check_safety``** — synchronous, fast telemetry
   validation gate.  Returns ``False`` to signal a *hard block* when
   any measured parameter falls outside safe operating limits defined
   by the NTSyCS standard and manufacturer specifications.

2. **``SafetyGuard.watchdog_loop``** — an asyncio coroutine that
   continuously writes an incrementing counter to the device watchdog
   register.  If the device does not receive a fresh heartbeat within
   the configured timeout, it triggers an autonomous safety shutdown.

Design notes
------------
* Limits are defined as class-level constants so they can be
  subclassed or overridden in unit tests without touching logic.
* The watchdog counter wraps at 65535 (max UINT16) to stay within
  the register's data type range.
* Critical failures in the watchdog are logged at CRITICAL level and
  re-raised so the caller can escalate (e.g. trigger an OS-level
  shutdown or alert).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    # Avoid circular import at runtime — only used for type hints.
    from src.drivers.modbus_driver import UniversalDriver

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Telemetry dict alias
# ---------------------------------------------------------------------------
Telemetry = dict[str, Any]


class SafetyGuard:
    """
    Hard-limit safety gate and device watchdog manager.

    All threshold constants are defined here and can be overridden in
    subclasses for site-specific configurations or unit tests.

    Parameters
    ----------
    watchdog_interval_s:
        Seconds between watchdog heartbeat writes.  Defaults to 1 s so
        the inverter's safety timer is refreshed well within its window.
    """

    # ------------------------------------------------------------------
    # Safety limits  (engineering units, same as telemetry dict values)
    # ------------------------------------------------------------------
    SOC_MIN: float = 5.0    # % — below this: deep-discharge risk
    SOC_MAX: float = 98.0   # % — above this: overcharge risk
    TEMP_MAX: float = 45.0  # °C — above this: thermal runaway risk

    # Watchdog counter wraps at UINT16 max
    _WATCHDOG_MAX: int = 65535

    def __init__(self, watchdog_interval_s: float = 1.0) -> None:
        self._watchdog_interval_s = watchdog_interval_s
        self._heartbeat_counter: int = 0

    # ------------------------------------------------------------------
    # Public API — safety check
    # ------------------------------------------------------------------

    def check_safety(self, telemetry: Telemetry) -> bool:
        """
        Validate telemetry against hard safety limits.

        Parameters
        ----------
        telemetry:
            Dictionary of measured values.  Recognised keys (all optional
            — missing keys are skipped, not considered violations):

            * ``"soc"``  (float) — State of Charge in percent.
            * ``"temp"`` (float) — Battery temperature in °C.

        Returns
        -------
        bool
            ``True``  — all present values are within safe limits.
            ``False`` — at least one value is out of bounds (hard block).

        Examples
        --------
        ::

            guard = SafetyGuard()
            ok = guard.check_safety({"soc": 50.0, "temp": 30.0})
            # ok == True

            ok = guard.check_safety({"soc": 3.0, "temp": 30.0})
            # ok == False  (SOC below minimum)
        """
        # --- State of Charge ---
        if "soc" in telemetry:
            soc: float = float(telemetry["soc"])
            if soc < self.SOC_MIN:
                log.warning(
                    "safety.block.soc_low",
                    soc=soc,
                    limit=self.SOC_MIN,
                    action="BLOCK",
                )
                return False
            if soc > self.SOC_MAX:
                log.warning(
                    "safety.block.soc_high",
                    soc=soc,
                    limit=self.SOC_MAX,
                    action="BLOCK",
                )
                return False

        # --- Temperature ---
        if "temp" in telemetry:
            temp: float = float(telemetry["temp"])
            if temp > self.TEMP_MAX:
                log.warning(
                    "safety.block.temp_high",
                    temp=temp,
                    limit=self.TEMP_MAX,
                    action="BLOCK",
                )
                return False

        log.debug("safety.check.pass", telemetry=telemetry)
        return True

    # ------------------------------------------------------------------
    # Public API — watchdog coroutine
    # ------------------------------------------------------------------

    async def watchdog_loop(self, driver: UniversalDriver) -> None:
        """
        Continuously refresh the device watchdog heartbeat register.

        The counter increments by 1 on every tick and wraps around at
        ``UINT16`` maximum (65535) to stay within the register's range.
        The loop runs indefinitely; cancel the task to stop it.

        Parameters
        ----------
        driver:
            A connected ``UniversalDriver`` instance used to write the
            ``watchdog_heartbeat`` tag.

        Raises
        ------
        asyncio.CancelledError
            Re-raised transparently when the containing task is cancelled
            (clean shutdown).

        Notes
        -----
        A *write failure* logs a CRITICAL alert but does **not** raise
        by default — the loop continues attempting to recover.  If two
        consecutive failures occur, a ``RuntimeError`` is raised to force
        the caller to handle the situation (e.g. reconnect or graceful stop).
        """
        consecutive_failures: int = 0
        _MAX_CONSECUTIVE_FAILURES: int = 2

        log.info(
            "watchdog.started",
            interval_s=self._watchdog_interval_s,
            tag="watchdog_heartbeat",
        )

        try:
            while True:
                await asyncio.sleep(self._watchdog_interval_s)

                # Wrap counter within UINT16 range
                self._heartbeat_counter = (
                    self._heartbeat_counter + 1
                ) % (self._WATCHDOG_MAX + 1)

                try:
                    await driver.write_tag(
                        "watchdog_heartbeat", float(self._heartbeat_counter)
                    )
                    consecutive_failures = 0  # reset on success
                    log.debug(
                        "watchdog.heartbeat.sent",
                        counter=self._heartbeat_counter,
                    )

                except Exception as exc:
                    consecutive_failures += 1
                    log.critical(
                        "watchdog.heartbeat.FAILED",
                        counter=self._heartbeat_counter,
                        consecutive_failures=consecutive_failures,
                        max_failures=_MAX_CONSECUTIVE_FAILURES,
                        error=str(exc),
                        action=(
                            "RAISING RuntimeError"
                            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES
                            else "RETRYING"
                        ),
                    )
                    if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                        raise RuntimeError(
                            f"Watchdog heartbeat failed {consecutive_failures} "
                            f"consecutive times. Last error: {exc}"
                        ) from exc

        except asyncio.CancelledError:
            log.info("watchdog.stopped", counter=self._heartbeat_counter)
            raise  # propagate for clean asyncio task lifecycle
