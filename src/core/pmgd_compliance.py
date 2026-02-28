# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/pmgd_compliance.py
============================
PMGD Compliance Engine — Decreto 88/2023 (GAP-007).

Verifies that BESS + PMGD (Pequeños Medios de Generación Distribuida)
installations comply with the updated Decreto 88/2023 requirements for
BESS-backed distributed generation in Chile.

Key Requirements (Decreto 88/2023)
------------------------------------
* PMGD + BESS must maintain a minimum self-consumption ratio.
* Export power ceiling: Pexport ≤ contract limit (kW) at all times.
* BESS must not export more than the PMGD generates (anti-arbitrage rule).
* Monthly energy balance must be reported to SEC.

Usage::

    pmgd = PMGDComplianceEngine(export_limit_kw=200.0, p_pmgd_kw=500.0)
    ok, reason = pmgd.check_dispatch(p_bess_kw=150.0, p_pmgd_kw=180.0,
                                     p_load_kw=80.0)
"""

from __future__ import annotations

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)


class PMGDComplianceEngine:
    """
    PMGD + BESS dispatch compliance checker.

    Parameters
    ----------
    export_limit_kw:
        Contracted export power ceiling in kW (from SEC connection agreement).
    min_self_consumption_pct:
        Minimum self-consumption ratio required (default 20 %).
    """

    def __init__(
        self,
        export_limit_kw: float = 500.0,
        min_self_consumption_pct: float = 20.0,
    ) -> None:
        if export_limit_kw < 0:
            raise ValueError("export_limit_kw must be >= 0")
        self._export_limit = export_limit_kw
        self._min_sc_pct = min_self_consumption_pct

    def check_dispatch(
        self,
        p_bess_kw: float,
        p_pmgd_kw: float,
        p_load_kw: float,
    ) -> tuple[bool, str]:
        """
        Validate a dispatch setpoint for Decreto 88/2023 compliance.

        Parameters
        ----------
        p_bess_kw:
            BESS active power (+ = discharge/export, - = charge).
        p_pmgd_kw:
            PMGD generation (positive = generating).
        p_load_kw:
            Local load consumption (positive).

        Returns
        -------
        tuple[bool, str]
            (True, "") if compliant, (False, reason) if not.
        """
        net_export = p_pmgd_kw + p_bess_kw - p_load_kw

        # Rule 1: Export ceiling
        if net_export > self._export_limit:
            reason = (
                f"Net export {net_export:.1f} kW exceeds contract limit "
                f"{self._export_limit:.1f} kW (Decreto 88/2023 Art. 5)"
            )
            log.warning("pmgd.block.export_ceiling", net_export=net_export,
                        limit=self._export_limit, norm_ref="D88/2023 Art.5")
            return False, reason

        # Rule 2: Anti-arbitrage — BESS export ≤ PMGD generation
        bess_export = max(0.0, p_bess_kw)
        if bess_export > p_pmgd_kw:
            reason = (
                f"BESS export {bess_export:.1f} kW > PMGD generation "
                f"{p_pmgd_kw:.1f} kW — arbitrage violation (Decreto 88/2023 Art. 7)"
            )
            log.warning("pmgd.block.arbitrage", bess_export=bess_export,
                        pmgd_kw=p_pmgd_kw, norm_ref="D88/2023 Art.7")
            return False, reason

        # Rule 3: Minimum self-consumption
        if p_pmgd_kw + p_bess_kw > 0:
            sc_ratio = p_load_kw / (p_pmgd_kw + max(0.0, p_bess_kw))
            sc_pct = sc_ratio * 100.0
            if sc_pct < self._min_sc_pct:
                reason = (
                    f"Self-consumption {sc_pct:.1f}% below minimum "
                    f"{self._min_sc_pct:.1f}% (Decreto 88/2023 Art. 6)"
                )
                log.warning("pmgd.block.self_consumption", sc_pct=sc_pct,
                            limit=self._min_sc_pct, norm_ref="D88/2023 Art.6")
                return False, reason

        log.debug("pmgd.check.pass", net_export=net_export)
        return True, ""

    def export_headroom_kw(self, p_bess_kw: float, p_pmgd_kw: float, p_load_kw: float) -> float:
        """Remaining export capacity in kW before ceiling is hit."""
        net_export = p_pmgd_kw + p_bess_kw - p_load_kw
        return max(0.0, self._export_limit - net_export)
