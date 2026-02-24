"""
src/agents/marl_env.py
========================
BESSAI Edge Gateway — BEP-0220: Multi-Agent RL Environment for VPP Coordination.

Implements a **Multi-Agent Gymnasium** (PettingZoo-compatible) environment
where each BESS unit is an independent agent coordinating in a Virtual Power
Plant (VPP) federation. This is the core of BESSAI's Phase 3 VPP roadmap.

Architecture: **Decentralized Execution, Centralized Training (CTDE)**
    - Each agent sees its own local BESS state + shared VPP grid signal.
    - Agents are trained jointly (Ray RLlib MARL) but execute independently
      at inference — critical for edge deployment where agents may be offline.

Why this matters:
    - OpenEMS: single-site only, no VPP coordination.
    - FlexMeasures: cloud-based VPP, cannot run offline.
    - Tesla Autobidder: closed, no federation API.
    - **BESSAI VPP**: 10-100 sites coordinated, each runs its ONNX model offline.

Compatibility:
    - PettingZoo ParallelEnv API (supports Ray RLlib MARL natively)
    - Each agent is a ``BESSArbitrageEnv`` instance

Reference: AAMAS 2024 "Federated MARL for Industrial Energy Storage Fleets"

Usage::

    from src.agents.marl_env import BESSFleetMARLEnv

    env = BESSFleetMARLEnv(n_sites=3, capacity_kwh_per_site=200)
    obs, _ = env.reset()
    # obs = {'site_0': np.ndarray, 'site_1': np.ndarray, 'site_2': np.ndarray}
    actions = {agent_id: env.action_space(agent_id).sample()
               for agent_id in env.agents}
    obs, rewards, dones, truncs, infos = env.step(actions)
"""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
    _GYM_AVAILABLE = True
except ImportError:
    _GYM_AVAILABLE = False

    class gym:  # type: ignore[no-redef]
        class Env:
            pass

    class spaces:  # type: ignore[no-redef]
        class Box:
            pass


from .bess_rl_env import BESSArbitrageEnv, _build_synthetic_cmg_profile

__all__ = ["BESSFleetMARLEnv", "VPPSignal"]


# ---------------------------------------------------------------------------
# VPP Grid Signal — Shared observable by all agents
# ---------------------------------------------------------------------------


class VPPSignal:
    """Virtual Power Plant aggregator signal.

    Produces a shared signal visible to all BESS agents representing:
    - Grid frequency deviation (mHz) — signals need for fast response
    - Aggregated fleet SoC (average) — coordination signal
    - VPP dispatch request (kW/site) — external grid operator command

    This enables emergent coordination: if fleet SoC is low, agents learn to
    charge collectively; if a frequency event occurs, agents provide FFR.

    Parameters
    ----------
    n_sites:
        Number of BESS units in the VPP fleet.
    max_power_kw_per_site:
        Maximum power per unit (kW).
    """

    def __init__(self, n_sites: int, max_power_kw_per_site: float) -> None:
        self.n_sites = n_sites
        self.max_power_kw_per_site = max_power_kw_per_site
        self._rng = np.random.default_rng(42)

        # State
        self._freq_dev_mhz: float = 0.0      # Grid frequency deviation
        self._fleet_soc_avg: float = 0.5      # Average fleet SoC
        self._dispatch_request_pu: float = 0.0  # ∈ [-1, 1]

    def update(self, socs: list[float], step: int) -> None:
        """Update VPP signal based on current fleet state.

        Parameters
        ----------
        socs:
            List of current SoC values from all sites.
        step:
            Current timestep (5-min resolution).
        """
        self._fleet_soc_avg = float(np.mean(socs))

        # Simulate grid frequency events (rare — 2% probability per step)
        if self._rng.random() < 0.02:
            # Frequency deviation event: ±50-200 mHz
            self._freq_dev_mhz = float(self._rng.uniform(-200, 200))
        else:
            # Damped recovery toward 0
            self._freq_dev_mhz *= 0.9

        # VPP dispatch request: based on price signal + frequency
        hour = (step * 5.0 / 60.0) % 24.0
        # Peak hours (18:00-22:00): request discharge; night: request charge
        if 18.0 <= hour <= 22.0:
            self._dispatch_request_pu = 0.5 + 0.3 * self._rng.random()
        elif 0.0 <= hour <= 5.0:
            self._dispatch_request_pu = -0.3 - 0.2 * self._rng.random()
        else:
            self._dispatch_request_pu *= 0.95  # Gradual decay

        self._dispatch_request_pu = float(
            np.clip(self._dispatch_request_pu, -1.0, 1.0)
        )

    def as_vector(self) -> np.ndarray:
        """Return VPP signal as normalized 3-element vector."""
        return np.array(
            [
                np.clip(self._freq_dev_mhz / 200.0, -1.0, 1.0),  # freq dev normalized
                self._fleet_soc_avg,                               # average fleet SoC
                self._dispatch_request_pu,                         # VPP dispatch request
            ],
            dtype=np.float32,
        )

    @property
    def freq_event_active(self) -> bool:
        """True if a significant frequency deviation event is active."""
        return abs(self._freq_dev_mhz) > 50.0


# ---------------------------------------------------------------------------
# Multi-Agent BESS Fleet Environment
# ---------------------------------------------------------------------------


class BESSFleetMARLEnv:
    """PettingZoo-compatible parallel multi-agent BESS VPP environment.

    Each agent controls one BESS site independently. The VPP signal provides
    a shared coordination layer visible to all agents.

    Observation space per agent (11-d):
        [soc, temp_norm, deg_norm, cmg_now, cmg_1h, cmg_4h, hour_sin, hour_cos,
         vpp_freq_dev, vpp_fleet_soc, vpp_dispatch_pu]
        ↑————————————— local BESS state (8) ————————————↑  ↑— shared VPP (3) —↑

    Action space per agent (continuous, shape=[1]):
        p_setpoint_pu ∈ [-1, +1]

    Reward structure:
        Individual reward:   revenue - degradation_cost - thermal_penalty
        Shared penalty:      VPP_coordination_bonus (reward fleet alignment)
        Safety penalty:      Hard penalty if SoC leaves band or is_safe=False

    Parameters
    ----------
    n_sites:
        Number of BESS sites in the VPP (default: 5).
    capacity_kwh_per_site:
        Battery capacity per site (kWh).
    max_power_kw_per_site:
        Maximum power per site (kW).
    cmg_profile:
        Optional price profile. If None, uses synthetic Chilean CMg.
    vpp_coordination_weight:
        Weight for the VPP coordination bonus in the reward (0 = no coordination).
    """

    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        n_sites: int = 5,
        capacity_kwh_per_site: float = 200.0,
        max_power_kw_per_site: float = 100.0,
        cmg_profile: np.ndarray | None = None,
        vpp_coordination_weight: float = 0.2,
    ) -> None:
        self.n_sites = n_sites
        self.capacity_kwh = capacity_kwh_per_site
        self.max_power_kw = max_power_kw_per_site
        self.vpp_weight = vpp_coordination_weight

        # Agent IDs
        self.possible_agents = [f"site_{i}" for i in range(n_sites)]
        self.agents: list[str] = []

        # Shared CMg profile (same price signal for all sites in same grid zone)
        self._cmg_profile = (
            cmg_profile if cmg_profile is not None else _build_synthetic_cmg_profile()
        )
        self._n_steps = len(self._cmg_profile)

        # Individual BESS environments (one per site)
        self._envs: dict[str, BESSArbitrageEnv] = {
            site: BESSArbitrageEnv(
                capacity_kwh=capacity_kwh_per_site,
                max_power_kw=max_power_kw_per_site,
                cmg_profile=self._cmg_profile.copy(),
            )
            for site in self.possible_agents
        }

        # VPP coordination signal
        self._vpp = VPPSignal(n_sites, max_power_kw_per_site)

        # Spaces (extended with VPP signal: 8 local + 3 VPP = 11-d)
        self._obs_dim = 11
        self._observation_space = spaces.Box(
            low=np.array(
                [0.0, -1.0, 0.0, 0.0, 0.0, 0.0, -1.0, -1.0, -1.0, 0.0, -1.0],
                dtype=np.float32,
            ),
            high=np.array(
                [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                dtype=np.float32,
            ),
            dtype=np.float32,
        )
        self._action_space = spaces.Box(
            low=np.array([-1.0], dtype=np.float32),
            high=np.array([1.0], dtype=np.float32),
            dtype=np.float32,
        )

        self._step_idx: int = 0

    # ------------------------------------------------------------------
    # PettingZoo ParallelEnv API
    # ------------------------------------------------------------------

    def observation_space(self, agent: str) -> spaces.Box:  # type: ignore[override]
        return self._observation_space

    def action_space(self, agent: str) -> spaces.Box:  # type: ignore[override]
        return self._action_space

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """Reset all sites to start of a new trading day."""
        self.agents = list(self.possible_agents)
        self._step_idx = 0

        # Reset all individual environments
        obs_dict: dict[str, np.ndarray] = {}
        for site, env in self._envs.items():
            local_obs, _ = env.reset(seed=seed)
            obs_dict[site] = self._augment_obs(local_obs)

        # Reset VPP signal
        socs = [float(obs_dict[site][0]) for site in self.agents]
        self._vpp.update(socs, 0)

        return obs_dict, {}

    def step(
        self, actions: dict[str, np.ndarray]
    ) -> tuple[
        dict[str, np.ndarray],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        dict[str, Any],
    ]:
        """Step all BESS agents simultaneously.

        Parameters
        ----------
        actions:
            Dict of {agent_id: action_array} for all agents.

        Returns
        -------
        observations, rewards, terminateds, truncateds, infos
        """
        next_obs: dict[str, np.ndarray] = {}
        rewards: dict[str, float] = {}
        terminateds: dict[str, bool] = {}
        truncateds: dict[str, bool] = {}
        infos: dict[str, Any] = {}

        # Step all sites
        for site in list(self.agents):
            action = actions.get(site, np.array([0.0], dtype=np.float32))
            local_obs, reward, terminated, truncated, info = self._envs[site].step(action)

            next_obs[site] = self._augment_obs(local_obs)
            rewards[site] = float(reward)
            terminateds[site] = terminated
            truncateds[site] = truncated
            infos[site] = info

        # Update VPP signal with current fleet state
        socs = [float(next_obs[site][0]) for site in self.agents]
        self._step_idx += 1
        self._vpp.update(socs, self._step_idx)

        vpp_vec = self._vpp.as_vector()

        # Augment observations with updated VPP signal
        for site in self.agents:
            obs = next_obs[site].copy()
            obs[8:11] = vpp_vec
            next_obs[site] = obs

        # VPP coordination bonus: reward agents that align with VPP dispatch request
        vpp_request = float(vpp_vec[2])  # VPP dispatch pu
        for site in self.agents:
            action_taken = float(actions.get(site, np.array([0.0]))[0])
            alignment = max(0.0, 1.0 - abs(action_taken - vpp_request))
            rewards[site] += self.vpp_weight * alignment * 0.1  # Small bonus

        # Handle episode end
        if all(terminateds.values()):
            self.agents = []

        terminateds["__all__"] = all(terminateds.values())
        truncateds["__all__"] = all(truncateds.values())

        return next_obs, rewards, terminateds, truncateds, infos  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _augment_obs(self, local_obs: np.ndarray) -> np.ndarray:
        """Augment 8-d local observation with 3-d VPP signal → 11-d."""
        vpp_vec = self._vpp.as_vector()
        return np.concatenate([local_obs, vpp_vec], dtype=np.float32)

    def render(self) -> str:
        """ANSI render of fleet state."""
        lines = [f"=== VPP Fleet — Step {self._step_idx}/{self._n_steps} ==="]
        for site in self.possible_agents:
            env = self._envs[site]
            soc = env._bess.soc
            temp = env._bess.temp_c
            rev = env._episode_revenue
            lines.append(f"  {site}: SOC={soc:.1%}  T={temp:.1f}°C  Rev={rev:.2f} USD")
        lines.append(
            f"  VPP: freq={self._vpp._freq_dev_mhz:.0f}mHz  "
            f"fleet_soc={self._vpp._fleet_soc_avg:.1%}  "
            f"dispatch={self._vpp._dispatch_request_pu:+.2f}"
        )
        return "\n".join(lines)
