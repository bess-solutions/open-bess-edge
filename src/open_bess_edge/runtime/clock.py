"""Relojes inyectables: real (producción) y manual (pruebas deterministas)."""

from __future__ import annotations

import asyncio
import time


class SystemClock:
    def mono(self) -> float:
        return time.monotonic()

    def wall(self) -> float:
        return time.time()

    async def sleep(self, s: float) -> None:
        await asyncio.sleep(max(0.0, s))


class ManualClock:
    """Reloj controlado por el test. ``sleep`` avanza el tiempo sin esperar."""

    def __init__(self, t0: float = 1000.0) -> None:
        self._t = t0
        self._w = 1_700_000_000.0

    def mono(self) -> float:
        return self._t

    def wall(self) -> float:
        return self._w + (self._t - 1000.0)

    def advance(self, dt: float) -> None:
        self._t += dt

    async def sleep(self, s: float) -> None:
        self._t += max(0.0, s)
        await asyncio.sleep(0)
