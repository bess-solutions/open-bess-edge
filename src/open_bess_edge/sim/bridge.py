"""Puente Modelo de planta <-> banco de registros, dirigido por un perfil.

Codifica las magnitudes medidas en los registros que el perfil liga a cada señal
canónica y decodifica las consignas escritas por el gateway. Sirve para emular
*cualquier* perfil con bindings (referencia o de fabricante) y así ejercitar el
driver de extremo a extremo.
"""

from __future__ import annotations

import math
from typing import Optional

from ..modbus.codec import decode, encode
from ..modbus.profile import DeviceProfile, RegisterSpec, apply_scale, unapply_scale
from .modbus_server import RegisterBank
from .plant import PlantModel


class SimBridge:
    def __init__(self, profile: DeviceProfile, plant: PlantModel, bank: RegisterBank,
                 pcs_watchdog_s: Optional[float] = None):
        self.profile, self.plant, self.bank = profile, plant, bank
        self.pcs_watchdog_s = pcs_watchdog_s
        self.watchdog_tripped = False
        self._hb_last: Optional[int] = None
        self._hb_changed_at = 0.0
        # Definir sólo los registros usados por los bindings (dirección no mapeada => excepción 02).
        for b in profile.bindings.values():
            spec = profile.registers[b.register]
            bank.define(spec.function, spec.address, spec.count)
            if spec.function == "input" and b.signal in ("p_setpoint_kw", "q_setpoint_kvar", "heartbeat"):
                bank.define("holding", spec.address, spec.count)
            if spec.scale_register:
                sf = profile.registers[spec.scale_register]
                bank.define(sf.function, sf.address, sf.count)
                # factor de escala fijo 10^0 en el emulador
                self._write_raw(sf, 0.0)
        # Los setpoints y latido son holding aunque el perfil no lo diga.
        self.sync_out()

    def _write_raw(self, spec: RegisterSpec, raw_value: float) -> None:
        if isinstance(raw_value, float) and not math.isfinite(raw_value) and spec.rtype.is_float:
            # Inyección de NaN/inf: el códec de producción los rechaza al *codificar*, el emulador debe poder emitirlos.
            import struct  # noqa: PLC0415

            from ..modbus.codec import _from_bytes  # noqa: PLC0415

            fmt = ">f" if spec.rtype.width == 2 else ">d"
            regs = _from_bytes(struct.pack(fmt, raw_value), self.profile.byte_order, self.profile.word_order)
        else:
            regs = encode(raw_value, spec.rtype, self.profile.byte_order, self.profile.word_order)
        store = self.bank.holding if spec.function == "holding" else self.bank.input
        for i, r in enumerate(regs):
            store[spec.address + i] = r

    def sync_out(self) -> None:
        """Planta -> registros (mediciones)."""
        m = self.plant.measure()
        for sig, b in self.profile.bindings.items():
            if sig not in m:
                continue
            spec = self.profile.registers[b.register]
            v = m[sig]
            if isinstance(v, float) and not math.isfinite(v):
                # inyección de valor no finito: sólo representable en FLOAT
                raw = v
            else:
                eng = b.to_engineering(v) - spec.offset
                raw = unapply_scale(eng, spec.scale)
                if not spec.rtype.is_float:
                    raw = float(round(raw))
                    lo, hi = _bounds(spec)
                    raw = max(lo, min(hi, raw))
            try:
                self._write_raw(spec, raw)
            except Exception:  # noqa: BLE001 - valor no representable: se deja el último
                pass

    def sync_in(self, now: float) -> None:
        """Registros -> planta (consignas y watchdog del PCS)."""
        for sig, attr in (("p_setpoint_kw", "p_setpoint_kw"), ("q_setpoint_kvar", "q_setpoint_kvar")):
            b = self.profile.bindings.get(sig)
            if b is None:
                continue
            spec = self.profile.registers[b.register]
            regs = [self.bank.holding[spec.address + i] for i in range(spec.count)]
            raw = decode(regs, spec.rtype, self.profile.byte_order, self.profile.word_order)
            val = b.to_canonical(apply_scale(float(raw), spec.scale) + spec.offset)
            setattr(self.plant, attr, val)
        hb = self.profile.bindings.get("heartbeat")
        if hb is not None and self.pcs_watchdog_s is not None:
            spec = self.profile.registers[hb.register]
            cur = self.bank.holding[spec.address]
            if cur != self._hb_last:
                self._hb_last, self._hb_changed_at = cur, now
                self.watchdog_tripped = False
            elif now - self._hb_changed_at > self.pcs_watchdog_s:
                # el PCS pasa a estado seguro: consigna interna a 0
                self.watchdog_tripped = True
                self.plant.p_setpoint_kw = 0.0
                self.plant.q_setpoint_kvar = 0.0


def _bounds(spec: RegisterSpec) -> tuple[float, float]:
    from ..modbus.codec import _INT_RANGE  # noqa: PLC0415

    lo, hi = _INT_RANGE[spec.rtype]
    return float(lo), float(hi)
