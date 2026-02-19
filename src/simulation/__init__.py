"""
src/simulation/__init__.py
==========================
BESSAI Edge Gateway — Simulation package.

Provides a Gymnasium-compatible environment for training DRL dispatch policies
and evaluating them against deterministic baselines.

Modules:
    bess_env:   BESSEnv — Gymnasium environment for BESS dispatch.
    bess_model: BESSPhysicsModel — battery degradation and thermal model.
"""

from .bess_env import BESSEnv
from .bess_model import BESSPhysicsModel

__all__ = ["BESSEnv", "BESSPhysicsModel"]
