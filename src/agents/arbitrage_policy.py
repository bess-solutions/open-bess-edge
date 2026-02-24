"""
src/agents/arbitrage_policy.py
==============================
BESSAI Edge Gateway — BEP-0200: Rule-based Arbitrage Baseline Policy.

Provides the deterministic rule-based policy used as:
1. **A/B comparison baseline** during training evaluation.
2. **Fallback policy** when the ONNX DRL agent is unavailable.
3. **Floor guarantee** — always performs better than random.

Strategy:
    - **Solar Dump Window** (high solar, low CMg):  Charge at max rate.
    - **Evening Peak** (high CMg, SOC > threshold):  Discharge at max rate.
    - **Idle** (CMg moderate, or SOC constraints):   Hold (p_pu = 0).

This matches how most real BESS systems operate today — it sets the
baseline that the DRL agent is designed to beat by +25-35%.
"""

from __future__ import annotations

from typing import Any

import numpy as np

__all__ = ["ArbitragePolicy"]

# ---------------------------------------------------------------------------
# Observation index constants (must match BESSArbitrageEnv._observe())
# ---------------------------------------------------------------------------
OBS_SOC = 0
OBS_TEMP_NORM = 1
OBS_DEG = 2
OBS_CMG_NOW = 3
OBS_CMG_1H = 4
OBS_CMG_4H = 5
OBS_HOUR_SIN = 6
OBS_HOUR_COS = 7

# Normalisation constant used in BESSArbitrageEnv
_CMG_MAX_NORM = 300.0


class ArbitragePolicy:
    """Deterministic rule-based arbitrage policy.

    thresholds are calibrated on Chilean CMg statistics (CEN 2023-2025):
        - Low CMg  (charge opportunity): < 30 USD/MWh
        - High CMg (discharge opportunity): > 80 USD/MWh
        - SOC limits: min 0.15 (don't deep-discharge), max 0.95 (don't overcharge)

    Parameters
    ----------
    cmg_low_threshold_norm:
        Normalised CMg threshold below which the policy charges.
        Default 30/300 = 0.10.
    cmg_high_threshold_norm:
        Normalised CMg threshold above which the policy discharges.
        Default 80/300 = 0.267.
    soc_min:
        Minimum SOC before refusing to discharge further.
    soc_max:
        Maximum SOC before refusing to charge further.
    charge_pu:
        Per-unit charge power (0 to 1).
    discharge_pu:
        Per-unit discharge power (0 to 1).
    """

    def __init__(
        self,
        cmg_low_threshold_norm: float = 30.0 / _CMG_MAX_NORM,
        cmg_high_threshold_norm: float = 80.0 / _CMG_MAX_NORM,
        soc_min: float = 0.15,
        soc_max: float = 0.95,
        charge_pu: float = -1.0,       # max charge
        discharge_pu: float = 1.0,     # max discharge
    ) -> None:
        self.cmg_low = cmg_low_threshold_norm
        self.cmg_high = cmg_high_threshold_norm
        self.soc_min = soc_min
        self.soc_max = soc_max
        self.charge_pu = charge_pu
        self.discharge_pu = discharge_pu

    def predict(
        self, obs: np.ndarray
    ) -> tuple[float, dict[str, Any]]:
        """Compute rule-based action from observation.

        Parameters
        ----------
        obs:
            1-D float32 array of shape ``(8,)`` — BESSArbitrageEnv observation.

        Returns
        -------
        p_pu : float
            Per-unit power setpoint ∈ [-1, 1].
        info : dict
            Metadata dict describing which rule triggered.
        """
        soc = float(obs[OBS_SOC])
        cmg_now = float(obs[OBS_CMG_NOW])
        cmg_1h = float(obs[OBS_CMG_1H])

        # Rule 1: Solar dump / low price → charge (if room in battery)
        if cmg_now <= self.cmg_low and soc < self.soc_max:
            return self.charge_pu, {
                "source": "rule_based",
                "rule": "solar_dump_charge",
                "cmg_now": cmg_now,
                "soc": soc,
            }

        # Rule 2: Peak price + 1-hour forecast also high → discharge now
        if (
            cmg_now >= self.cmg_high
            and cmg_1h >= self.cmg_high * 0.8   # stay-in-peak confirmation
            and soc > self.soc_min
        ):
            return self.discharge_pu, {
                "source": "rule_based",
                "rule": "evening_peak_discharge",
                "cmg_now": cmg_now,
                "soc": soc,
            }

        # Rule 3: Price spike incoming (1h forecast >> now) → Pre-charge
        if cmg_1h >= self.cmg_high * 1.2 and cmg_now < self.cmg_low * 1.5 and soc < self.soc_max:
            # Charge now to sell in 1 hour
            p_pu = float(np.clip(-0.7, self.charge_pu, 0.0))  # 70% charge
            return p_pu, {
                "source": "rule_based",
                "rule": "pre_charge_spike_anticipation",
                "cmg_now": cmg_now,
                "cmg_1h": cmg_1h,
                "soc": soc,
            }

        # Rule 4: Discharge in moderate high price if SOC very high
        if cmg_now >= self.cmg_high * 0.7 and soc > 0.90:
            p_pu = float(np.clip(0.5, 0.0, self.discharge_pu))  # 50% discharge
            return p_pu, {
                "source": "rule_based",
                "rule": "high_soc_moderate_price_discharge",
                "cmg_now": cmg_now,
                "soc": soc,
            }

        # Default: hold
        return 0.0, {"source": "rule_based", "rule": "idle", "cmg_now": cmg_now, "soc": soc}
