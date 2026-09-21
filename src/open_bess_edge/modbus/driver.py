"""Driver de planta: Modbus TCP dirigido por perfil, con calidad de datos explícita.

Responsabilidades:
* Leer la telemetría necesaria (según bindings del perfil) y convertirla a la
  convención interna. Un valor no finito o no decodificable **nunca** se
  sustituye por un número plausible: el campo queda en ``None`` y se lista en
  ``Telemetry.invalid``.
* Escribir consignas P/Q con conversión de signo/escala del perfil, truncado
  hacia cero (la magnitud jamás aumenta por cuantización) y verificación por
  relectura opcional.
* Gestionar la reconexión en segundo plano con backoff exponencial y jitter, sin
  bloquear el lazo de control.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import random
import time
from typing import Callable, Iterable, Optional

from ..errors import CodecError, PlantCommError, PlantDataError, ProfileError
from ..models import Telemetry, WriteResult
from .codec import decode, encode
from .profile import (
    TELEMETRY_SIGNALS,
    Binding,
    DeviceProfile,
    RegisterSpec,
    apply_scale,
    unapply_scale,
)
from .transport import ModbusTransport

log = logging.getLogger("open_bess_edge.plant")


class ModbusPlant:
    def __init__(
        self,
        profile: DeviceProfile,
        transport: ModbusTransport,
        unit_id: int,
        *,
        max_read_gap: int = 0,
        reconnect_min_s: float = 0.5,
        reconnect_max_s: float = 30.0,
        mono: Callable[[], float] = time.monotonic,
        wall: Callable[[], float] = time.time,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.profile = profile
        self.transport = transport
        self.unit_id = unit_id
        self.max_read_gap = max_read_gap
        self._mono, self._wall = mono, wall
        self._rng = rng or random.Random()  # nosec B311
        self._min, self._max = reconnect_min_s, reconnect_max_s
        self._delay = reconnect_min_s
        self._next_attempt = 0.0
        self._connect_task: Optional[asyncio.Task[None]] = None
        self.last_connect_error: str = ""
        self.connect_attempts = 0
        self._hb = 0
        self._last_written: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------
    @property
    def connected(self) -> bool:
        return self.transport.connected

    def poll_connection(self) -> bool:
        """No bloqueante. Devuelve el estado actual y dispara (si toca) una reconexión."""
        if self.transport.connected:
            self._delay = self._min
            return True
        t = self._connect_task
        if t is not None and not t.done():
            return False
        if t is not None and t.done():
            self._connect_task = None
        if self._mono() >= self._next_attempt:
            self._connect_task = asyncio.ensure_future(self._attempt())
        return False

    async def _attempt(self) -> None:
        self.connect_attempts += 1
        try:
            await self.transport.connect()
            self.last_connect_error = ""
            self._delay = self._min
            log.info("modbus conectado")
        except PlantCommError as exc:
            self.last_connect_error = str(exc)
            jitter = self._rng.uniform(0.8, 1.2)
            self._next_attempt = self._mono() + min(self._delay * jitter, self._max)
            self._delay = min(self._delay * 2.0, self._max)
            log.warning("reconexión Modbus fallida (próximo intento en %.2fs): %s",
                        self._next_attempt - self._mono(), exc)

    async def connect_now(self, timeout_s: float) -> bool:
        """Conexión bloqueante acotada (sólo para el arranque). Usa tiempo real, no el reloj inyectado."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while loop.time() < deadline:
            if self.transport.connected:
                return True
            try:
                await self.transport.connect()
                return True
            except PlantCommError as exc:
                self.last_connect_error = str(exc)
                await asyncio.sleep(min(0.2, max(0.0, deadline - loop.time())))
        return self.transport.connected

    async def close(self) -> None:
        t, self._connect_task = self._connect_task, None
        if t is not None and not t.done():
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        await self.transport.close()

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def _decode_register(self, spec: RegisterSpec, regs: list[int]) -> float:
        raw = decode(regs, spec.rtype, self.profile.byte_order, self.profile.word_order)
        if isinstance(raw, float) and not math.isfinite(raw):
            return math.nan
        return float(raw)

    async def read_telemetry(self, signals: Optional[Iterable[str]] = None) -> Telemetry:
        wanted = [s for s in (signals or self.profile.telemetry_signals) if s in TELEMETRY_SIGNALS]
        plan = self.profile.read_plan(wanted, self.max_read_gap)
        t0_mono, t0_wall = self._mono(), self._wall()
        raw_by_reg: dict[str, float] = {}
        for block in plan:
            regs = await self.transport.read(block.function, block.start, block.count, self.unit_id)
            for spec in block.registers:
                off = spec.address - block.start
                try:
                    raw_by_reg[spec.name] = self._decode_register(spec, regs[off : off + spec.count])
                except CodecError as exc:
                    log.warning("registro %s no decodificable: %s", spec.name, exc)
                    raw_by_reg[spec.name] = math.nan

        values: dict[str, Optional[float]] = {}
        invalid: list[str] = []
        for sig in wanted:
            b = self.profile.bindings.get(sig)
            if b is None:
                continue
            val = self._to_canonical(b, raw_by_reg)
            if val is None:
                invalid.append(sig)
            values[sig] = val
        return Telemetry(t_mono=t0_mono, t_wall=t0_wall, invalid=tuple(invalid), **values)

    def _to_canonical(self, b: Binding, raw_by_reg: dict[str, float]) -> Optional[float]:
        spec = self.profile.registers[b.register]
        raw = raw_by_reg.get(spec.name, math.nan)
        if not math.isfinite(raw):
            return None
        if spec.scale_register:
            sf = raw_by_reg.get(spec.scale_register, math.nan)
            if not math.isfinite(sf) or abs(sf) > 10:
                return None
            eng = raw * (10.0 ** int(sf)) * (spec.scale if spec.scale != 1.0 else 1.0)
        else:
            eng = apply_scale(raw, spec.scale)
        eng += spec.offset
        val = b.to_canonical(eng)
        return val if math.isfinite(val) else None

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    def _encode_setpoint(self, b: Binding, canonical: float) -> tuple[RegisterSpec, list[int], float]:
        spec = self.profile.registers[b.register]
        eng = b.to_engineering(canonical) - spec.offset
        raw_val = unapply_scale(eng, spec.scale)
        if not spec.rtype.is_float:
            raw_val = float(math.trunc(raw_val))       # nunca aumentar la magnitud
        regs = encode(raw_val, spec.rtype, self.profile.byte_order, self.profile.word_order)
        back = decode(regs, spec.rtype, self.profile.byte_order, self.profile.word_order)
        effective = b.to_canonical(apply_scale(float(back), spec.scale) + spec.offset)
        return spec, regs, effective

    def check_setpoint_range(self, p_max_kw: float, q_max_kvar: float) -> None:
        """Verifica en el arranque que ±p_max y ±q_max son representables en los registros."""
        checks = [("p_setpoint_kw", p_max_kw)]
        if "q_setpoint_kvar" in self.profile.bindings:
            checks.append(("q_setpoint_kvar", q_max_kvar))
        for sig, mx in checks:
            b = self.profile.bindings.get(sig)
            if b is None:
                raise ProfileError(f"el perfil '{self.profile.name}' no define binding {sig}")
            for v in (mx, -mx):
                try:
                    self._encode_setpoint(b, v)
                except CodecError as exc:
                    raise ProfileError(
                        f"{sig}: {v} no es representable en el registro '{b.register}' del perfil "
                        f"'{self.profile.name}' ({exc}). Ajuste la escala del registro."
                    ) from exc

    async def write_setpoints(
        self, p_kw: float, q_kvar: float, *, verify: bool = False, tolerance_kw: float = 1.0
    ) -> WriteResult:
        t0 = self._mono()
        if not (math.isfinite(p_kw) and math.isfinite(q_kvar)):
            return WriteResult(False, f"consigna no finita p={p_kw!r} q={q_kvar!r}")
        bp = self.profile.bindings.get("p_setpoint_kw")
        if bp is None:
            raise PlantDataError(f"perfil '{self.profile.name}' sin consigna de P: sólo monitor")
        bq = self.profile.bindings.get("q_setpoint_kvar")

        errors: list[str] = []
        applied: dict[str, float] = {}
        expected_raw: dict[str, tuple[RegisterSpec, list[int]]] = {}
        for sig, b, val in (("p", bp, p_kw), ("q", bq, q_kvar)):
            if b is None:
                if abs(val) > 1e-9:
                    errors.append("q_sin_binding")
                continue
            try:
                spec, regs, eff = self._encode_setpoint(b, val)
            except CodecError as exc:
                errors.append(f"{sig}:codec:{exc}")
                continue
            try:
                await self.transport.write(spec.address, regs, self.unit_id)
                applied[sig] = eff
                expected_raw[sig] = (spec, regs)
                self._last_written[sig] = regs[0]
            except PlantCommError as exc:
                errors.append(f"{sig}:{exc}")

        verified: Optional[bool] = None
        if verify and expected_raw and not errors:
            verified = True
            for sig, (spec, regs) in expected_raw.items():
                try:
                    back = await self.transport.read("holding", spec.address, spec.count, self.unit_id)
                except PlantCommError as exc:
                    errors.append(f"{sig}:verify:{exc}")
                    verified = False
                    continue
                if back != regs:
                    verified = False
                    errors.append(f"{sig}:verify_mismatch esperado={regs} leído={back}")
        return WriteResult(
            ok=not errors,
            detail="; ".join(errors) if errors else "SETPOINTS_COMMITTED",
            verified=verified,
            latency_ms=(self._mono() - t0) * 1000.0,
            extra={"applied_p_kw": applied.get("p"), "applied_q_kvar": applied.get("q")},
        )

    async def write_zero(self) -> WriteResult:
        """Intenta poner P=0 y Q=0; un fallo en P no impide intentar Q."""
        t0 = self._mono()
        errors: list[str] = []
        for sig in ("p_setpoint_kw", "q_setpoint_kvar"):
            b = self.profile.bindings.get(sig)
            if b is None:
                continue
            try:
                spec, regs, _ = self._encode_setpoint(b, 0.0)
                await self.transport.write(spec.address, regs, self.unit_id)
            except (PlantCommError, CodecError) as exc:
                errors.append(f"{sig}:{exc}")
        return WriteResult(not errors, "; ".join(errors) if errors else "ZEROED",
                           latency_ms=(self._mono() - t0) * 1000.0)

    async def heartbeat(self) -> bool:
        b = self.profile.bindings.get("heartbeat")
        if b is None:
            return True
        spec = self.profile.registers[b.register]
        self._hb = (self._hb + 1) % (1 << (16 * spec.rtype.width))
        try:
            regs = encode(float(self._hb), spec.rtype, self.profile.byte_order, self.profile.word_order)
            await self.transport.write(spec.address, regs, self.unit_id)
            return True
        except (PlantCommError, CodecError) as exc:
            log.warning("heartbeat no escrito: %s", exc)
            return False
