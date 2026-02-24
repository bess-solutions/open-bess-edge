"""
src/agents
==========
BESSAI Edge Gateway — BEP-0200 DRL Arbitrage Agent package.

Modules
-------
bess_rl_env      Gymnasium environment with real CMg (Chile) price data
drl_agent        Ray RLlib PPO wrapper + ONNX export / edge inference
arbitrage_policy Rule-based baseline policy for A/B benchmarking
"""

from .arbitrage_policy import ArbitragePolicy
from .bess_rl_env import BESSArbitrageEnv

__all__ = ["BESSArbitrageEnv", "ArbitragePolicy"]
