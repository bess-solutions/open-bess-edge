# Minimal stub for gymnasium — compatible with type-ignore approach used in bess_rl_env.py / marl_env.py
from __future__ import annotations

from typing import Any, SupportsFloat

# Import spaces from the sub-stub (no circular import — this is a stub file)

__version__: str

class Env:
    """Base class for gymnasium environments."""
    observation_space: Any
    action_space: Any
    np_random: Any
    reward_range: tuple[float, float]
    metadata: dict[str, Any]
    spec: Any

    def step(
        self, action: Any
    ) -> tuple[Any, SupportsFloat, bool, bool, dict[str, Any]]: ...

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]: ...

    def render(self) -> Any: ...

    def close(self) -> None: ...

class ObservationWrapper(Env): ...
class ActionWrapper(Env): ...
class RewardWrapper(Env): ...
class Wrapper(Env): ...

def make(id: str, **kwargs: Any) -> Env: ...
def register(id: str, **kwargs: Any) -> None: ...
