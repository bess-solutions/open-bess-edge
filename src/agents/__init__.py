"""
src/agents
==========
BESSAI Edge Gateway — BEP-0200/0210/0215/0220/0225 DRL Agent package.

Modules
-------
bess_rl_env        Gymnasium environment with real CMg (Chile) price data
drl_agent          Ray RLlib PPO wrapper + ONNX export / edge inference
arbitrage_policy   Rule-based baseline policy for A/B benchmarking
degradation_model  Semi-empirical degradation model (Rainflow + Arrhenius)
milp_optimizer     MILP 24h day-ahead dispatcher (PuLP + HiGHS)
marl_env           Multi-agent VPP fleet environment (PettingZoo-compatible)
benchmark_suite    Open benchmark suite: DRL vs rule-based vs MILP vs random

Note on optional imports
------------------------
Most submodules here require optional heavy dependencies (gymnasium, ray, torch,
onnxruntime, structlog, pulp …). Import them directly from their submodule when
needed. Only lightweight items are eagerly imported here.
"""

# Lightweight module — no heavy deps
from .degradation_model import (
    BatteryChemistry,
    DegradationModel,
    DegradationResult,
    RainflowCounter,
)

__all__ = [
    # Degradation (no optional deps needed)
    "DegradationModel",
    "DegradationResult",
    "BatteryChemistry",
    "RainflowCounter",
    # Below: lazily importable from submodules
    # from src.agents.bess_rl_env import BESSArbitrageEnv
    # from src.agents.drl_agent import ONNXArbitrageAgent
    # from src.agents.milp_optimizer import MILPOptimizer, solve_milp_schedule
    # from src.agents.marl_env import BESSFleetMARLEnv, VPPSignal
    # from src.agents.benchmark_suite import BenchmarkSuite, RuleBasedAgent
    # from src.agents.arbitrage_policy import ArbitragePolicy
]
