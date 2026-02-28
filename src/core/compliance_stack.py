# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/compliance_stack.py
=============================
BESSAI Compliance Stack — Unified façade for all NTSyCS modules.

Single-import entry point that instantiates and wires all regulatory
compliance modules for a BESS installation in Chile. Designed for use
in ``main.py``, integration tests, and third-party integrations.

Usage
-----
Minimal (all defaults, env-driven)::

    from src.core.compliance_stack import ComplianceStack, ComplianceResult

    stack = ComplianceStack.from_env()
    result = await stack.run_cycle(telemetry, p_prev_kw=45.0, dt_s=5.0)

    if not result.dispatch_allowed:
        logger.warning("Dispatch blocked: %s", result.block_reason)

    # Structured setpoints ready for write_tag():
    stack.log_cycle_summary(result)

Manual configuration::

    stack = ComplianceStack(
        p_nom_kw=500.0,
        q_max_kvar=242.0,
        export_limit_kw=100.0,
        site_id="PMGD-OVALLE-001",
    )

Environment variables
---------------------
BESSAI_P_NOM_KW          Nominal power (kW). Default: 1000.0
BESSAI_Q_MAX_KVAR        Max reactive power (kVAr). Default: 484.0
BESSAI_F_NOM             Grid nominal frequency (Hz). Default: 50.0
BESSAI_DROOP_PCT         PFR droop in %. Default: 5.0
BESSAI_DEADBAND_HZ       PFR deadband (Hz). Default: 0.1
BESSAI_THD_LIMIT_PCT     THD limit (%). Default: 8.0
BESSAI_PST_LIMIT         Flicker Pst limit. Default: 1.0
BESSAI_PLT_LIMIT         Flicker Plt limit. Default: 0.8
PMGD_EXPORT_LIMIT_KW     PMGD export ceiling (kW). Default: 500.0
ERNC_SITE_ID             Site ID for ERNC certificates. Default: SITE_ID
BESSAI_SL2_TLS           Enforce TLS in SL2 gate. Default: false (network layer)
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.core.safety import SafetyGuard
from src.core.frequency_response import FrequencyResponseAgent
from src.core.reactive_power import ReactiveController
from src.core.power_quality import PowerQualityMonitor
from src.core.pmgd_compliance import PMGDComplianceEngine
from src.core.ernc_registry import ERNCRegistry
from src.core.iec62443 import SL2SecurityGate

log: structlog.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Cycle result
# ---------------------------------------------------------------------------

@dataclass
class ComplianceResult:
    """
    Output of a single compliance cycle — ready for control decisions.

    All setpoints are *recommendations*; the orchestrator decides whether
    to write them to hardware (BEP-0300 protocol).
    """

    # Gate decisions
    dispatch_allowed: bool = True
    block_reason: str = ""

    # Setpoints (kW / kVAr)
    p_ramp_limited_kw: float = 0.0   # GAP-001: ramp-clamped active power
    p_pfr_setpoint_kw: float = 0.0   # GAP-002: PFR-corrected active power
    q_setpoint_kvar: float = 0.0     # GAP-011: reactive Q setpoint

    # Metrics for telemetry
    thd_headroom_pct: float = 8.0
    pfr_active: bool = False
    qv_active: bool = False
    cycle_duration_ms: float = 0.0

    # Audit
    timestamp: float = field(default_factory=time.time)
    norm_refs: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ComplianceStack
# ---------------------------------------------------------------------------

class ComplianceStack:
    """
    Unified compliance façade — all 11 NTSyCS GAPs in one object.

    Instantiate once at startup; call ``run_cycle()`` on every control tick.

    Parameters
    ----------
    p_nom_kw            Nominal active power (kW).
    q_max_kvar          Maximum reactive power capacity (kVAr).
    f_nom               Grid nominal frequency (Hz). Default 50.0.
    droop_pct           PFR droop in %. Default 5.0.
    deadband_hz         PFR deadband ±Hz. Default 0.1.
    thd_limit_pct       THD voltage limit %. Default 8.0.
    pst_limit           Flicker Pst limit. Default 1.0.
    plt_limit           Flicker Plt limit. Default 0.8.
    export_limit_kw     PMGD export ceiling kW (Decreto 88/2023).
    site_id             Site identifier for ERNC certificates.
    sl2_enforce_tls     Whether SL2 gate requires TLS. Default False (network layer).
    """

    def __init__(
        self,
        p_nom_kw: float = 1000.0,
        q_max_kvar: float = 484.0,
        f_nom: float = 50.0,
        droop_pct: float = 5.0,
        deadband_hz: float = 0.1,
        thd_limit_pct: float = 8.0,
        pst_limit: float = 1.0,
        plt_limit: float = 0.8,
        export_limit_kw: float = 500.0,
        site_id: str = "BESS-SITE",
        sl2_enforce_tls: bool = False,
    ) -> None:
        self.p_nom_kw = p_nom_kw
        self.site_id = site_id

        # Instantiate all compliance modules
        self.safety = SafetyGuard(p_nom_kw=p_nom_kw)
        self.pfr = FrequencyResponseAgent(
            f_nominal=f_nom, deadband_hz=deadband_hz,
            droop_pct=droop_pct, p_nom_kw=p_nom_kw,
        )
        self.qv = ReactiveController(q_max_kvar=q_max_kvar, p_nom_kw=p_nom_kw)
        self.pq = PowerQualityMonitor(thd_limit_pct=thd_limit_pct,
                                      pst_limit=pst_limit, plt_limit=plt_limit)
        self.pmgd = PMGDComplianceEngine(export_limit_kw=export_limit_kw)
        self.ernc = ERNCRegistry(site_id=site_id)
        self.sl2 = SL2SecurityGate(enforce_tls=sl2_enforce_tls)

        # Optional: CEN publisher (lazy — only if CEN_ENDPOINT_URL is set)
        self._cen_publisher = None
        if os.getenv("CEN_ENDPOINT_URL"):
            try:
                from src.core.publishers.cen_publisher import CENPublisher
                self._cen_publisher = CENPublisher.from_env()
                log.info("cen_publisher.enabled", norm_ref="NTSyCS Cap. 6.1")
            except Exception as e:
                log.warning("cen_publisher.init_failed", error=str(e))

        log.info(
            "compliance_stack.initialized",
            site_id=site_id, p_nom_kw=p_nom_kw, q_max_kvar=q_max_kvar,
            f_nom=f_nom, droop_pct=droop_pct, deadband_hz=deadband_hz,
            export_limit_kw=export_limit_kw,
            modules=["GAP-001", "GAP-002", "GAP-003", "GAP-004",
                     "GAP-007", "GAP-008", "GAP-009", "GAP-010", "GAP-011"],
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "ComplianceStack":
        """Construct from environment variables."""
        return cls(
            p_nom_kw=float(os.getenv("BESSAI_P_NOM_KW", "1000.0")),
            q_max_kvar=float(os.getenv("BESSAI_Q_MAX_KVAR", "484.0")),
            f_nom=float(os.getenv("BESSAI_F_NOM", "50.0")),
            droop_pct=float(os.getenv("BESSAI_DROOP_PCT", "5.0")),
            deadband_hz=float(os.getenv("BESSAI_DEADBAND_HZ", "0.1")),
            thd_limit_pct=float(os.getenv("BESSAI_THD_LIMIT_PCT", "8.0")),
            pst_limit=float(os.getenv("BESSAI_PST_LIMIT", "1.0")),
            plt_limit=float(os.getenv("BESSAI_PLT_LIMIT", "0.8")),
            export_limit_kw=float(os.getenv("PMGD_EXPORT_LIMIT_KW", "500.0")),
            site_id=os.getenv("SITE_ID", "BESS-SITE"),
            sl2_enforce_tls=os.getenv("BESSAI_SL2_TLS", "false").lower() == "true",
        )

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    async def run_cycle(
        self,
        telemetry: dict[str, Any],
        p_prev_kw: float = 0.0,
        dt_s: float = 5.0,
        p_pmgd_kw: float = 0.0,
        p_load_kw: float = 0.0,
    ) -> ComplianceResult:
        """
        Execute all compliance checks for one control cycle.

        Parameters
        ----------
        telemetry   : Dict with BESS telemetry (soc, grid_frequency, ac_voltage, etc.)
        p_prev_kw   : Active power from previous cycle (for ramp rate calculation).
        dt_s        : Time elapsed since previous cycle (seconds).
        p_pmgd_kw   : PMGD generation (for Decreto 88/2023 anti-arbitrage check).
        p_load_kw   : Local load consumption (for PMGD self-consumption check).

        Returns
        -------
        ComplianceResult with all setpoints and gate decisions.
        """
        t0 = time.perf_counter()
        result = ComplianceResult()
        norm_refs: list[str] = []

        # ── GAP-010: Power Quality Gate (NTCSE) ──────────────────────────
        pq_ok, pq_reason = self.pq.check(telemetry)
        if not pq_ok:
            result.dispatch_allowed = False
            result.block_reason = pq_reason
            result.cycle_duration_ms = (time.perf_counter() - t0) * 1000
            return result
        norm_refs.append("NTCSE")

        # ── GAP-001 part A: Safety hard limits ───────────────────────────
        if not self.safety.check_safety(telemetry):
            result.dispatch_allowed = False
            result.block_reason = "SafetyGuard hard limit violation"
            result.cycle_duration_ms = (time.perf_counter() - t0) * 1000
            return result
        norm_refs.append("NTSyCS-SAF")

        # ── GAP-001 part B: Ramp Rate Limit ──────────────────────────────
        p_current_kw = float(telemetry.get("active_power", 0.0)) / 1000.0
        p_ramp = self.safety.apply_ramp_limit(p_prev_kw, p_current_kw, dt_s)
        result.p_ramp_limited_kw = p_ramp
        norm_refs.append("NTSyCS-4.2")

        # ── GAP-002: Primary Frequency Response ───────────────────────────
        f_hz = float(telemetry.get("grid_frequency", 50.0))
        p_pfr = self.pfr.compute_setpoint(f_hz, p_ramp)
        result.p_pfr_setpoint_kw = p_pfr
        result.pfr_active = abs(p_pfr - p_ramp) > 0.1
        norm_refs.append("NTSyCS-4.3")

        # ── GAP-011: Reactive Power Q/V ───────────────────────────────────
        v_nom = float(os.getenv("BESSAI_V_NOM_V", "230.0"))
        v_pu = float(telemetry.get("ac_voltage", v_nom)) / v_nom
        q_kvar = self.qv.compute_q_setpoint(v_pu)
        result.q_setpoint_kvar = q_kvar
        result.qv_active = abs(q_kvar) > 1.0
        norm_refs.append("NTSyCS-4.4")

        # ── GAP-007: PMGD check (if PMGD data available) ──────────────────
        if p_pmgd_kw > 0 or p_load_kw > 0:
            pmgd_ok, pmgd_reason = self.pmgd.check_dispatch(
                p_bess_kw=p_pfr, p_pmgd_kw=p_pmgd_kw, p_load_kw=p_load_kw,
            )
            if not pmgd_ok:
                result.dispatch_allowed = False
                result.block_reason = pmgd_reason
                result.cycle_duration_ms = (time.perf_counter() - t0) * 1000
                return result
            norm_refs.append("D88/2023")

        # ── GAP-010: THD headroom metric ─────────────────────────────────
        result.thd_headroom_pct = self.pq.compute_thd_headroom(
            float(telemetry.get("thd_pct", 0.0))
        )

        # ── GAP-003: CEN Publish (fire-and-forget) ────────────────────────
        if self._cen_publisher is not None:
            payload = {
                "soc_pct": float(telemetry.get("soc", 0.0)),
                "p_kw": p_pfr,
                "q_kvar": q_kvar,
                "f_hz": f_hz,
                "status": "ONLINE",
            }
            asyncio.ensure_future(self._cen_publisher.publish(payload))
            norm_refs.append("NTSyCS-6.1")

        result.norm_refs = norm_refs
        result.cycle_duration_ms = (time.perf_counter() - t0) * 1000
        return result

    def authorize_command(self, role: str, command: str, zone: str = "OT") -> tuple[bool, str]:
        """SL2 command authorization (GAP-009). Call before writing any setpoint."""
        return self.sl2.authorize_command(role, command, zone)

    def record_ernc_charge(self, energy_kwh: float, source: str) -> None:
        """Record a charging event for ERNC tracking (GAP-008)."""
        self.ernc.record_charge(energy_kwh, source)

    def generate_ernc_certificate(self):
        """Generate ERNC certificate for CNE submission (GAP-008)."""
        return self.ernc.ernc_certificate()

    def log_cycle_summary(self, result: ComplianceResult) -> None:
        """Log a structured compliance cycle summary."""
        log.info(
            "compliance_cycle",
            dispatch_allowed=result.dispatch_allowed,
            p_pfr_kw=round(result.p_pfr_setpoint_kw, 2),
            q_kvar=round(result.q_setpoint_kvar, 2),
            pfr_active=result.pfr_active,
            qv_active=result.qv_active,
            thd_headroom_pct=round(result.thd_headroom_pct, 1),
            duration_ms=round(result.cycle_duration_ms, 2),
            norm_refs=result.norm_refs,
            block_reason=result.block_reason or None,
        )
