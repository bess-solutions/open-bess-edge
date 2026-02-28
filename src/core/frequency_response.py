# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/frequency_response.py
================================
Primary Frequency Response (PFR) Agent — NTSyCS Cap. 4.3 (GAP-002).

Implements a droop-based frequency response controller for BESS units
≥1 MW connected to the Chilean SEN (Sistema Eléctrico Nacional).

NTSyCS requirement
------------------
* Units ≥ 1 MW must participate in primary frequency regulation.
* Response time: < 2 s from detection to setpoint delivery.
* Droop characteristic: typically 5 % (configurable per contract).
* Deadband: ±0.1 Hz around 50 Hz nominal.

Design
------
* Pure computation — no I/O, no asyncio required.
* Compatible with being called every control cycle (100 ms typical).
* Integrates with ``SafetyGuard.apply_ramp_limit`` for combined compliance.

Usage
-----
::

    pfr = FrequencyResponseAgent(f_nominal=50.0, droop_pct=5.0, p_nom_kw=1000.0)

    # Each control cycle:
    f_grid = await driver.read_tag("grid_frequency")
    p_base = current_dispatch_setpoint_kw
    p_corrected = pfr.compute_setpoint(f_grid, p_base)
    # Write p_corrected to inverter
"""

from __future__ import annotations

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)


class FrequencyResponseAgent:
    """
    Droop-based Primary Frequency Response controller.

    Parameters
    ----------
    f_nominal:
        Grid nominal frequency in Hz (default 50.0 for Chile/SEN).
    deadband_hz:
        Frequency deadband around nominal in Hz.  No response within
        ±deadband_hz.  Default 0.1 Hz per NTSyCS.
    droop_pct:
        Droop percentage (%).  5 % means 100 % of Pnom is deployed for
        a frequency deviation equal to 5 % of f_nominal.  Default 5.0 %.
    p_nom_kw:
        Nominal active power of the BESS in kW.  Used to scale the
        frequency response.  Must be > 0.
    """

    def __init__(
        self,
        f_nominal: float = 50.0,
        deadband_hz: float = 0.1,
        droop_pct: float = 5.0,
        p_nom_kw: float = 1000.0,
    ) -> None:
        if p_nom_kw <= 0:
            raise ValueError(f"p_nom_kw must be positive, got {p_nom_kw}")
        if droop_pct <= 0:
            raise ValueError(f"droop_pct must be positive, got {droop_pct}")
        if deadband_hz < 0:
            raise ValueError(f"deadband_hz must be >= 0, got {deadband_hz}")

        self._f_nominal = f_nominal
        self._deadband_hz = deadband_hz
        self._droop_pct = droop_pct
        self._p_nom_kw = p_nom_kw

        log.info(
            "pfr_agent.initialized",
            f_nominal_hz=f_nominal,
            deadband_hz=deadband_hz,
            droop_pct=droop_pct,
            p_nom_kw=p_nom_kw,
            norm_ref="NTSyCS Cap. 4.3",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_setpoint(self, f_grid_hz: float, p_base_kw: float) -> float:
        """
        Compute the frequency-corrected active power setpoint.

        Parameters
        ----------
        f_grid_hz:
            Measured grid frequency in Hz.
        p_base_kw:
            Current base dispatch setpoint in kW (from economic/DRL dispatch).

        Returns
        -------
        float
            Corrected setpoint in kW, clamped to [0, p_nom_kw].
            Returns *p_base_kw* unchanged when frequency is within deadband.

        Notes
        -----
        * Positive ΔP (underfrequency) → increase discharge (inject active power).
        * Negative ΔP (overfrequency) → decrease discharge / increase absorption.
        * The droop formula: ``ΔP = -(Δf / (droop_pct/100 · f_nom)) · p_nom``
          Note the minus sign: underfrequency (Δf < 0) → ΔP > 0 (more power).
        """
        delta_f = f_grid_hz - self._f_nominal

        # Within deadband — no response required
        # Use small epsilon to handle IEEE-754 float representation
        # e.g. 50.1 - 50.0 = 0.10000000000000142 in Python
        _EPS = 1e-9
        if abs(delta_f) <= self._deadband_hz + _EPS:
            log.debug(
                "pfr.within_deadband",
                f_grid_hz=f_grid_hz,
                delta_f=delta_f,
                deadband_hz=self._deadband_hz,
            )
            return p_base_kw

        # Droop response: ΔP = -(Δf / (droop% / 100 * f_nom)) * Pnom
        droop_ref = (self._droop_pct / 100.0) * self._f_nominal
        delta_p_kw = -(delta_f / droop_ref) * self._p_nom_kw

        corrected = p_base_kw + delta_p_kw
        # Clamp to [0, p_nom_kw]
        clamped = max(0.0, min(self._p_nom_kw, corrected))

        log.info(
            "pfr.response.applied",
            f_grid_hz=f_grid_hz,
            delta_f_hz=delta_f,
            p_base_kw=p_base_kw,
            delta_p_kw=delta_p_kw,
            corrected_kw=corrected,
            clamped_kw=clamped,
            norm_ref="NTSyCS Cap. 4.3",
        )
        return clamped

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def deadband_hz(self) -> float:
        """Current deadband in Hz."""
        return self._deadband_hz

    @property
    def droop_pct(self) -> float:
        """Current droop percentage."""
        return self._droop_pct

    @property
    def p_nom_kw(self) -> float:
        """Nominal power in kW."""
        return self._p_nom_kw
