# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/power_quality.py
==========================
Power Quality Monitor — NTCSE / NTSyCS (GAP-010).

Monitors THD (Total Harmonic Distortion) and Flicker (Pst/Plt) at the
point of common coupling (PCC) and blocks BESS dispatch if limits are
exceeded, as required by the Chilean NTCSE (Norma Técnica de Calidad
de Servicio para Sistemas de Distribución y Transmisión).

NTCSE Limits
------------
* THD voltage: ≤ 8 % (distribution), ≤ 5 % (transmission)
* Flicker Pst: ≤ 1.0 p.u. (10-min window)
* Flicker Plt: ≤ 0.8 p.u. (2-hour window)

Usage::

    pq = PowerQualityMonitor()
    ok, reason = pq.check({"thd_pct": 3.5, "pst": 0.9, "plt": 0.7})
    # ok == True

    ok, reason = pq.check({"thd_pct": 9.0, "pst": 0.5})
    # ok == False, reason == "THD 9.0% exceeds NTCSE limit 8.0%"
"""

from __future__ import annotations

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)


class PowerQualityMonitor:
    """
    NTSyCS/NTCSE power quality compliance gate.

    Parameters
    ----------
    thd_limit_pct:
        Maximum THD voltage in % (default 8.0 for distribution).
    pst_limit:
        Maximum short-term flicker Pst in p.u. (default 1.0).
    plt_limit:
        Maximum long-term flicker Plt in p.u. (default 0.8).
    """

    THD_LIMIT_PCT: float = 8.0
    PST_LIMIT: float = 1.0
    PLT_LIMIT: float = 0.8

    def __init__(
        self,
        thd_limit_pct: float = 8.0,
        pst_limit: float = 1.0,
        plt_limit: float = 0.8,
    ) -> None:
        self._thd_limit = thd_limit_pct
        self._pst_limit = pst_limit
        self._plt_limit = plt_limit

    def check(self, telemetry: dict) -> tuple[bool, str]:
        """
        Check power quality metrics against NTCSE limits.

        Parameters
        ----------
        telemetry:
            Dict with optional keys: ``thd_pct``, ``pst``, ``plt``.

        Returns
        -------
        tuple[bool, str]
            (True, "") if within limits.
            (False, reason_str) if any limit exceeded.
        """
        if "thd_pct" in telemetry:
            thd = float(telemetry["thd_pct"])
            if thd > self._thd_limit:
                reason = f"THD {thd:.1f}% exceeds NTCSE limit {self._thd_limit:.1f}%"
                log.warning("pq.block.thd", thd_pct=thd, limit=self._thd_limit,
                            norm_ref="NTCSE Art. 8")
                return False, reason

        if "pst" in telemetry:
            pst = float(telemetry["pst"])
            if pst > self._pst_limit:
                reason = f"Flicker Pst {pst:.3f} exceeds NTCSE limit {self._pst_limit:.1f}"
                log.warning("pq.block.pst", pst=pst, limit=self._pst_limit,
                            norm_ref="NTCSE Art. 9")
                return False, reason

        if "plt" in telemetry:
            plt = float(telemetry["plt"])
            if plt > self._plt_limit:
                reason = f"Flicker Plt {plt:.3f} exceeds NTCSE limit {self._plt_limit:.1f}"
                log.warning("pq.block.plt", plt=plt, limit=self._plt_limit,
                            norm_ref="NTCSE Art. 9")
                return False, reason

        log.debug("pq.check.pass", telemetry=telemetry)
        return True, ""

    def compute_thd_headroom(self, thd_pct: float) -> float:
        """Return remaining THD headroom in % points before limit."""
        return max(0.0, self._thd_limit - thd_pct)
