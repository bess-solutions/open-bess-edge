# Minimal stub for gymnasium.spaces — no numpy import (not available in stub context)
from __future__ import annotations

from typing import Any, Generic, TypeVar

T = TypeVar("T")

class Space(Generic[T]):
    shape: tuple[int, ...]
    dtype: Any
    low: Any
    high: Any
    def sample(self, mask: Any = None) -> T: ...
    def contains(self, x: Any) -> bool: ...
    def seed(self, seed: int | None = None) -> list[int]: ...

class Box(Space[Any]):
    shape: tuple[int, ...]
    dtype: Any
    low: Any
    high: Any
    def __init__(
        self,
        low: Any,
        high: Any,
        shape: tuple[int, ...] | None = None,
        dtype: Any = ...,
        seed: int | None = None,
    ) -> None: ...
    def sample(self, mask: Any = None) -> Any: ...

class Discrete(Space[int]):
    n: int
    start: int
    def __init__(
        self,
        n: int,
        seed: int | None = None,
        start: int = 0,
    ) -> None: ...
    def sample(self, mask: Any = None) -> int: ...

class MultiDiscrete(Space[Any]):
    def __init__(self, nvec: Any, dtype: Any = ..., seed: int | None = None) -> None: ...

class MultiBinary(Space[Any]):
    def __init__(self, n: int | list[int], seed: int | None = None) -> None: ...

class Dict(Space[dict[str, Any]]):
    def __init__(self, spaces: dict[str, Space[Any]] | None = None, **spaces_kwargs: Space[Any]) -> None: ...

class Tuple(Space[tuple[Any, ...]]):
    def __init__(self, spaces: tuple[Space[Any], ...] | list[Space[Any]], seed: int | None = None) -> None: ...
