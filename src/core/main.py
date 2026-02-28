# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/main.py
=================
BESSAI Edge Gateway — Main Orchestrator.

Entry point for the async acquisition loop.  Brings together:

1. ``Settings``               — reads all configuration from environment.
2. ``configure_otel``         — bootstraps distributed tracing & metrics.
3. ``UniversalDriver``        — connects to the BESS device via Modbus TCP.
4. ``SafetyGuard``            — validates telemetry + ramp rate (GAP-001).
5. ``PubSubPublisher``        — publishes safe telemetry to GCP Pub/Sub.
6. ``watchdog_loop``          — background heartbeat task (auto-restarted if it dies).
7. ``HealthServer``           — HTTP /health + /metrics endpoints on port 8000.
8. ``WatchdogManager``        — autonomous self-healing reconnection (Plan Inmortalidad Eje 1).
9. ``FrequencyResponseAgent`` — Primary Frequency Response droop (GAP-002).
10. ``PowerQualityMonitor``   — THD/Flicker gate NTCSE (GAP-010).
11. ``ReactiveController``    — Q/V droop reactive power (GAP-011).
12. ``CENPublisher``          — Telemetría CEN mTLS (GAP-003).
13. ``SL2SecurityGate``       — IEC 62443 SL-2 command auth (GAP-009).

Lifecycle
---------
::

    startup → connect → while True {
        acquire → pq_gate → safety → ramp_limit → pfr → q_v →
        watchdog → publish → cen_publish → sleep
    }
    SIGINT/SIGTERM ───────────────────────────────────── graceful shutdown

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
from src.interfaces.mqtt_publisher import MQTTConnectionError, MQTTPublisher
from src.interfaces.otel_setup import configure_otel, get_tracer, shutdown_otel
from src.interfaces.pubsub_publisher import PubSubPublisher
from src.interfaces.sep2_adapter import SEP2Error, build_adapter_from_env

# BEP-0200 — DRL Arbitrage Agent (optional, fail-safe)
try:
    from src.agents.arbitrage_policy import ArbitragePolicy
    from src.agents.drl_agent import ONNXArbitrageAgent

    _DRL_AVAILABLE = True
except ImportError:  # gymnasium not installed
    _DRL_AVAILABLE = False

# Plan de Inmortalidad Eje 1 — WatchdogManager (optional, fail-safe)
try:
    from src.core.watchdog_manager import WatchdogManager as _WatchdogManager
    _WATCHDOG_MANAGER_AVAILABLE = True
except ImportError:
    _WATCHDOG_MANAGER_AVAILABLE = False
    _WatchdogManager = None  # type: ignore[assignment]

# NTSyCS Compliance Modules (optional, fail-safe — GAP-002/003/009/010/011)
try:
    from src.core.frequency_response import FrequencyResponseAgent as _FrequencyResponseAgent
    from src.core.power_quality import PowerQualityMonitor as _PowerQualityMonitor
    from src.core.reactive_power import ReactiveController as _ReactiveController
    from src.core.publishers.cen_publisher import CENPublisher as _CENPublisher
    from src.core.iec62443 import SL2SecurityGate as _SL2SecurityGate
    _COMPLIANCE_MODULES_AVAILABLE = True
except ImportError as _compliance_err:
    _COMPLIANCE_MODULES_AVAILABLE = False
    _FrequencyResponseAgent = None  # type: ignore[assignment,misc]
    _PowerQualityMonitor = None  # type: ignore[assignment,misc]
    _ReactiveController = None  # type: ignore[assignment,misc]
    _CENPublisher = None  # type: ignore[assignment,misc]
    _SL2SecurityGate = None  # type: ignore[assignment,misc]

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
# DRL agent model path (env var or default)
# ---------------------------------------------------------------------------
_DRL_MODEL_PATH: str = os.getenv("BESSAI_DRL_MODEL_PATH", "models/drl_arbitrage_v1.onnx")
_DRL_ENABLED: bool = os.getenv("BESSAI_DRL_ENABLED", "false").lower() == "true"
_WATCHDOG_MANAGER_ENABLED: bool = os.getenv("BESSAI_WATCHDOG_ENABLED", "true").lower() == "true"

# Compliance feature flags (env-controlled, all default ON if modules available)
_PFR_ENABLED: bool = os.getenv("BESSAI_PFR_ENABLED", "true").lower() == "true"
_PQ_GATE_ENABLED: bool = os.getenv("BESSAI_PQ_GATE_ENABLED", "true").lower() == "true"
_QV_ENABLED: bool = os.getenv("BESSAI_QV_ENABLED", "true").lower() == "true"
_CEN_PUBLISH_ENABLED: bool = bool(os.getenv("CEN_ENDPOINT_URL"))
_SL2_ENABLED: bool = os.getenv("BESSAI_SL2_ENABLED", "true").lower() == "true"
_P_NOM_KW: float = float(os.getenv("BESSAI_P_NOM_KW", "1000.0"))
_Q_MAX_KVAR: float = float(os.getenv("BESSAI_Q_MAX_KVAR", "484.0"))

# ---------------------------------------------------------------------------
# Tags read on every acquisition cycle
# Compliance modules need: grid_frequency (GAP-002), ac_voltage (GAP-011),
# thd_pct/pst/plt (GAP-010), temp_c (GAP-003)
# ---------------------------------------------------------------------------
_ACQUISITION_TAGS: list[str] = [
    "active_power",
    "soc",
    "grid_frequency",  # GAP-002: Primary Frequency Response
    "ac_voltage",      # GAP-011: Reactive Power Q/V droop
    "temp_c",          # GAP-003: CEN telemetry temperature
]

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

    # ── Step 4b — WatchdogManager self-healing (Plan de Inmortalidad Eje 1) ──
    _watchdog_manager_task: asyncio.Task | None = None
    if _WATCHDOG_MANAGER_AVAILABLE and _WATCHDOG_MANAGER_ENABLED:
        try:
            _wdm = _WatchdogManager(driver=driver)  # type: ignore[call-arg]
            _watchdog_manager_task = asyncio.create_task(
                _wdm.run(), name="watchdog_manager_self_heal"
            )
            log.info(
                "watchdog_manager.enabled",
                note="Autonomous self-healing loop active — Plan de Inmortalidad Eje 1",
            )
        except Exception as exc:
            log.warning(
                "watchdog_manager.start_failed",
                error=str(exc),
                action="continuing_without_watchdog_manager",
            )
    elif not _WATCHDOG_MANAGER_AVAILABLE:
        log.debug("watchdog_manager.unavailable", reason="import_failed")
    else:
        log.debug("watchdog_manager.disabled", tip="Set BESSAI_WATCHDOG_ENABLED=true to enable")

    # ── Step 5b — Health & Metrics server ────────────────────────────────
    health_server = HealthServer(
        site_id=_cfg.SITE_ID,
        version=_GATEWAY_VERSION,
        port=_cfg.HEALTH_PORT,
    )
    # Register static info gauge
    GATEWAY_INFO.labels(site_id=_cfg.SITE_ID, version=_GATEWAY_VERSION).set(1)

    # ── Step 5 — Safety guard, publisher, watchdog reference ─────────────
    guard = SafetyGuard(watchdog_interval_s=1.0, p_nom_kw=_P_NOM_KW)

    # ── Step 5f — NTSyCS Compliance modules (GAP-002/003/009/010/011) ────
    _pfr_agent = None
    _pq_monitor = None
    _qv_controller = None
    _cen_publisher = None
    _sl2_gate = None
    _prev_power_kw: float = 0.0
    _prev_cycle_ts: float = time.monotonic()

    if _COMPLIANCE_MODULES_AVAILABLE:
        if _PFR_ENABLED:
            _pfr_agent = _FrequencyResponseAgent(  # type: ignore[misc]
                f_nominal=50.0, deadband_hz=0.1, droop_pct=5.0,
                p_nom_kw=_P_NOM_KW,
            )
            log.info("pfr_agent.enabled", p_nom_kw=_P_NOM_KW,
                     norm_ref="NTSyCS Cap. 4.3 (GAP-002)")
        if _PQ_GATE_ENABLED:
            _pq_monitor = _PowerQualityMonitor()  # type: ignore[misc]
            log.info("pq_monitor.enabled", norm_ref="NTCSE (GAP-010)")
        if _QV_ENABLED:
            _qv_controller = _ReactiveController(  # type: ignore[misc]
                q_max_kvar=_Q_MAX_KVAR, p_nom_kw=_P_NOM_KW,
            )
            log.info("qv_controller.enabled", q_max_kvar=_Q_MAX_KVAR,
                     norm_ref="NTSyCS Cap. 4.4 (GAP-011)")
        if _CEN_PUBLISH_ENABLED:
            _cen_publisher = _CENPublisher.from_env()  # type: ignore[misc]
            log.info("cen_publisher.enabled", norm_ref="NTSyCS Cap. 6.1 (GAP-003)")
        if _SL2_ENABLED:
            _sl2_gate = _SL2SecurityGate(enforce_tls=False)  # TLS enforced at network layer
            log.info("sl2_gate.enabled", norm_ref="IEC 62443 SL-2 (GAP-009)")
    else:
        log.info("compliance_modules.disabled",
                 tip="Install open-bess-edge compliance modules to enable GAP-002/003/009/010/011")
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
        _mqtt_broker = os.getenv("MQTT_BROKER_URL")
        mqtt_pub: MQTTPublisher | None = None
        if _mqtt_broker:
            mqtt_pub = MQTTPublisher(
                broker_url=_mqtt_broker,
                site_id=_cfg.SITE_ID,
            )
            try:
                await mqtt_pub.start()
                log.info(
                    "mqtt_publisher.enabled",
                    broker=_mqtt_broker,
                    site_id=_cfg.SITE_ID,
                )
            except (MQTTConnectionError, Exception) as exc:
                log.warning(
                    "mqtt_publisher.start_failed",
                    error=str(exc),
                    action="continuing_without_mqtt",
                )
                mqtt_pub = None
        else:
            log.info(
                "mqtt_publisher.disabled",
                tip="Set MQTT_BROKER_URL in .env to enable dual-channel publishing",
            )

        # ── Step 5d — Optional IEEE 2030.5 SEP 2.0 adapter (fail-safe) ───
        _sep2_adapter = build_adapter_from_env(driver)
        _sep2_task: asyncio.Task | None = None
        if _sep2_adapter is not None:
            try:
                _sep2_task = asyncio.create_task(_sep2_adapter.start(), name="sep2_server")
                log.info(
                    "sep2_adapter.enabled",
                    port=_cfg.SEP2_PORT,
                    site_id=_cfg.SITE_ID,
                    note="IEEE 2030.5 / CPUC Rule 21 / AEMO AS/NZS 4777.2",
                )
            except (SEP2Error, Exception) as exc:
                log.warning(
                    "sep2_adapter.start_failed",
                    error=str(exc),
                    action="continuing_without_sep2",
                )
                _sep2_adapter = None
        else:
            log.info(
                "sep2_adapter.disabled",
                tip="Set SEP2_ENABLED=true in .env to enable IEEE 2030.5 server",
            )

        # ── Step 5e — Optional DRL Arbitrage Agent (fail-safe, BEP-0200) ────
        _drl_agent: ONNXArbitrageAgent | None = None  # type: ignore[type-arg]
        if _DRL_AVAILABLE and _DRL_ENABLED:
            _rule_policy = ArbitragePolicy()  # type: ignore[name-defined]
            _drl_agent = ONNXArbitrageAgent(  # type: ignore[name-defined]
                model_path=_DRL_MODEL_PATH,
                fallback=_rule_policy,
            )
            if _drl_agent.is_available:
                log.info(
                    "drl_agent.enabled",
                    model=_DRL_MODEL_PATH,
                    note="BEP-0200 PPO agent active (observe-only mode)",
                )
            else:
                log.info(
                    "drl_agent.fallback_only",
                    model=_DRL_MODEL_PATH,
                    tip="ONNX model not found — using ArbitragePolicy fallback",
                )
        elif not _DRL_AVAILABLE:
            log.info(
                "drl_agent.disabled",
                reason="gymnasium not installed",
                tip="pip install 'open-bess-edge[sim]' to enable",
            )
        else:
            log.info(
                "drl_agent.disabled",
                tip="Set BESSAI_DRL_ENABLED=true in .env to enable DRL arbitrage",
            )

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

                # ── STEP 2a: Power Quality Gate (NTCSE GAP-010) ───────────
                if _pq_monitor is not None:
                    _pq_ok, _pq_reason = _pq_monitor.check(telemetry)
                    if not _pq_ok:
                        log.warning("pq_gate.block", cycle=cycle, reason=_pq_reason,
                                    norm_ref="NTCSE (GAP-010)")
                        SAFETY_BLOCKS_TOTAL.labels(site_id=_cfg.SITE_ID,
                                                   reason="power_quality").inc()
                        health_server.last_cycle_ok = False
                        await asyncio.sleep(_cfg.WATCHDOG_TIMEOUT)
                        continue

                # ── STEP 2b: Safety (SOC / Temp hard limits, GAP-001 integrated) ─
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

                # ── STEP 2c: Ramp Rate Limit (NTSyCS Cap.4.2 GAP-001) ────────
                _now_ts = time.monotonic()
                _dt_s = _now_ts - _prev_cycle_ts
                _prev_cycle_ts = _now_ts
                _current_kw = float(telemetry.get("active_power", 0.0)) / 1000.0
                _safe_kw = guard.apply_ramp_limit(_prev_power_kw, _current_kw, _dt_s)
                if abs(_safe_kw - _current_kw) > 0.1:
                    log.info("ramp_rate.limited", cycle=cycle,
                             requested_kw=round(_current_kw, 2),
                             clamped_kw=round(_safe_kw, 2),
                             norm_ref="NTSyCS Cap. 4.2 (GAP-001)")
                _prev_power_kw = _safe_kw

                # ── STEP 2d: Primary Frequency Response (NTSyCS Cap.4.3 GAP-002) ─
                _pfr_setpoint: float | None = None
                if _pfr_agent is not None and "grid_frequency" in telemetry:
                    _f_hz = float(telemetry["grid_frequency"])
                    _pfr_setpoint = _pfr_agent.compute_setpoint(_f_hz, _safe_kw)
                    span.set_attribute("pfr_setpoint_kw", round(_pfr_setpoint, 2))

                # ── STEP 2e: Reactive Power Q/V (NTSyCS Cap.4.4 GAP-011) ─────
                _q_setpoint: float | None = None
                if _qv_controller is not None and "ac_voltage" in telemetry:
                    _v_pu = float(telemetry["ac_voltage"]) / 230.0  # normalise to pu
                    _q_setpoint = _qv_controller.compute_q_setpoint(_v_pu)
                    span.set_attribute("q_setpoint_kvar", round(_q_setpoint, 2))

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

                # ── STEP 4b: MQTT dual-channel (fail-safe) ────────────────
                if mqtt_pub is not None and mqtt_pub.is_connected:
                    try:
                        await mqtt_pub.publish_telemetry(
                            soc=float(telemetry.get("soc", 0.0)),
                            power_kw=float(telemetry.get("active_power", 0.0)) / 1000.0,
                            temp_c=float(telemetry.get("temp_c", 25.0)),
                        )
                        await mqtt_pub.publish_safety(
                            is_safe=True,
                            watchdog_status="ok",
                        )
                        await mqtt_pub.publish_heartbeat()
                    except Exception as exc:
                        log.warning(
                            "cycle.mqtt_publish_failed",
                            cycle=cycle,
                            error=str(exc),
                            action="continuing_without_mqtt_this_cycle",
                        )
                # ── STEP 4c: DRL Arbitrage setpoint (BEP-0200, observe-only) ─
                if _drl_agent is not None and "soc" in telemetry:
                    import numpy as np  # local import — optional for edge

                    # Build 8-d observation vector (matches BESSArbitrageEnv)
                    _soc = float(telemetry.get("soc", 50.0)) / 100.0  # [0,1]
                    _pwr = float(telemetry.get("active_power", 0.0)) / 1000.0  # kW
                    _temp = float(telemetry.get("temp_c", 25.0))
                    # (CMg fields are 0 until CMg Predictor v2 is integrated)
                    _obs = np.array(
                        [
                            _soc,  # soc [0,1]
                            _temp / 60.0,  # temp_norm
                            0.0,  # cumulative_deg (not tracked in telemetry yet)
                            0.1,  # cmg_now_norm: placeholder ~30 USD/MWh
                            0.1,  # cmg_1h_norm: placeholder
                            0.1,  # cmg_4h_norm: placeholder
                            0.0,  # hour_sin
                            1.0,  # hour_cos
                        ],
                        dtype=np.float32,
                    )
                    _p_pu, _drl_info = _drl_agent.predict(_obs)
                    _p_kw = (
                        _p_pu * _cfg.MAX_CONTINUOUS_DISCHARGE_KW  # type: ignore[attr-defined]
                        if hasattr(_cfg, "MAX_CONTINUOUS_DISCHARGE_KW")  # type: ignore[attr-defined]
                        else _p_pu * 100.0
                    )
                    log.info(
                        "drl_agent.setpoint",
                        cycle=cycle,
                        p_pu=round(_p_pu, 3),
                        p_kw=round(_p_kw, 1),
                        source=_drl_info.get("source", "unknown"),
                        rule=_drl_info.get("rule", ""),
                        soc_pct=round(_soc * 100, 1),
                        note="observe-only — write_tag integration in BEP-0200 Phase 4",
                    )

                # ── STEP 4d: CEN Telemetry Publisher (GAP-003, async fire-forget) ─
                if _cen_publisher is not None:
                    _cen_payload = {
                        "soc_pct": float(telemetry.get("soc", 0.0)),
                        "p_kw": _pfr_setpoint if _pfr_setpoint is not None else _safe_kw,
                        "q_kvar": _q_setpoint if _q_setpoint is not None else 0.0,
                        "f_hz": float(telemetry.get("grid_frequency", 50.0)),
                        "status": "ONLINE",
                        "bess_temp_c": float(telemetry.get("temp_c", 0.0)),
                    }
                    # Fire-and-forget  (errors logged inside CENPublisher)
                    asyncio.ensure_future(_cen_publisher.publish(_cen_payload))

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
    if _watchdog_manager_task is not None and not _watchdog_manager_task.done():
        _watchdog_manager_task.cancel()
        try:
            await _watchdog_manager_task
        except (asyncio.CancelledError, Exception):
            pass
    if mqtt_pub is not None:
        await mqtt_pub.stop()
    if _sep2_adapter is not None:
        await _sep2_adapter.stop()
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
