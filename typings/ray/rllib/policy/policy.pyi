# Minimal stub for ray.rllib.policy.policy
from __future__ import annotations

from typing import Any

class Policy:
    """Minimal stub for Ray RLlib Policy class."""
    model: Any

    @classmethod
    def from_checkpoint(cls, checkpoint_path: str) -> Policy: ...

    def compute_single_action(
        self,
        obs: Any,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any, Any, Any]: ...
