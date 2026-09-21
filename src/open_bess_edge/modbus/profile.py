"""Perfiles de dispositivo: mapa de registros + *bindings* a señales canónicas.

Un perfil (``registry/*.json``) describe registros Modbus (dirección, tipo,
escala, acceso). Para que el gateway *use* un dispositivo, el perfil debe
declarar además una sección ``canonical`` que liga señales canónicas (frecuencia,
tensión, P, Q, SOC, temperaturas, consignas P/Q...) con registros concretos,
indicando factor de unidad y signo respecto de la convención interna.

Capacidades derivadas (no declaradas a mano):
* ``can_control_p`` / ``can_control_q``: existen bindings de consigna escribibles.
* ``telemetry_signals``: señales canónicas realmente disponibles.

Un perfil sin bindings de consigna sólo puede usarse en modo *monitor*.
El nivel de verificación (``verification.level``) es informativo y honesto:
``reference`` (mapa de referencia del proyecto), ``simulated`` (ida y vuelta
contra un emulador construido desde el propio perfil), ``lab`` o ``field``
(sólo si existe evidencia real). Ningún perfil sube de nivel automáticamente.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from ..errors import ProfileError
from .codec import Order, RegType

TELEMETRY_SIGNALS = (
    "frequency_hz", "v_grid_v", "p_kw", "q_kvar", "soc_pct", "soh_pct",
    "cell_v_min_v", "cell_v_max_v", "cell_t_max_c", "cell_t_min_c",
    "isolation_kohm", "string_v_v", "ambient_c", "p_grid_kw",
)
CONTROL_SIGNALS = ("p_setpoint_kw", "q_setpoint_kvar", "heartbeat")
ALL_SIGNALS = TELEMETRY_SIGNALS + CONTROL_SIGNALS
VERIFICATION_LEVELS = ("reference", "simulated", "unverified", "lab", "field")

MAX_REGS_PER_READ = 125


@dataclass(frozen=True, slots=True)
class RegisterSpec:
    name: str
    address: int
    rtype: RegType
    access: str                       # "RO" | "RW"
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""
    function: str = "holding"         # "holding" | "input"
    scale_register: Optional[str] = None   # nombre de registro SF (SunSpec): valor * 10**sf

    @property
    def count(self) -> int:
        return self.rtype.width

    @property
    def writable(self) -> bool:
        return self.access == "RW"


@dataclass(frozen=True, slots=True)
class Binding:
    signal: str
    register: str
    factor: float = 1.0
    offset: float = 0.0
    sign: int = 1

    def to_canonical(self, engineering: float) -> float:
        return self.sign * self.factor * engineering + self.offset

    def to_engineering(self, canonical: float) -> float:
        return (canonical - self.offset) / (self.sign * self.factor)


@dataclass(frozen=True, slots=True)
class ReadBlock:
    function: str
    start: int
    count: int
    registers: tuple[RegisterSpec, ...]


@dataclass(frozen=True)
class DeviceProfile:
    name: str
    manufacturer: str
    model: str
    default_unit_id: Optional[int]
    byte_order: Order
    word_order: Order
    registers: dict[str, RegisterSpec]
    bindings: dict[str, Binding]
    verification_level: str
    notes: str = ""
    source: Optional[Path] = None
    _plan_cache: dict[Any, Any] = field(default_factory=dict, compare=False, repr=False)

    # -- capacidades -----------------------------------------------------
    @property
    def telemetry_signals(self) -> tuple[str, ...]:
        return tuple(s for s in TELEMETRY_SIGNALS if s in self.bindings)

    @property
    def can_control_p(self) -> bool:
        return "p_setpoint_kw" in self.bindings

    @property
    def can_control_q(self) -> bool:
        return "q_setpoint_kvar" in self.bindings

    @property
    def has_heartbeat(self) -> bool:
        return "heartbeat" in self.bindings

    def missing_signals(self, required: Iterable[str]) -> list[str]:
        return [s for s in required if s not in self.bindings]

    # -- plan de lectura -------------------------------------------------
    def read_plan(self, signals: Iterable[str], max_gap: int = 0) -> tuple[ReadBlock, ...]:
        """Agrupa en bloques contiguos los registros necesarios para ``signals``."""
        key = (tuple(sorted(set(signals))), max_gap)
        cached = self._plan_cache.get(key)
        if cached is not None:
            return tuple(cached)
        needed: dict[str, RegisterSpec] = {}
        for s in key[0]:
            b = self.bindings.get(s)
            if b is None:
                continue
            reg = self.registers[b.register]
            needed[reg.name] = reg
            if reg.scale_register:
                sf = self.registers[reg.scale_register]
                needed[sf.name] = sf
        blocks: list[ReadBlock] = []
        for function in ("holding", "input"):
            regs = sorted((r for r in needed.values() if r.function == function), key=lambda r: r.address)
            cur: list[RegisterSpec] = []
            start = end = 0
            for r in regs:
                r_end = r.address + r.count
                if cur and r.address - end <= max_gap and (r_end - start) <= MAX_REGS_PER_READ:
                    cur.append(r)
                    end = max(end, r_end)
                else:
                    if cur:
                        blocks.append(ReadBlock(function, start, end - start, tuple(cur)))
                    cur, start, end = [r], r.address, r_end
            if cur:
                blocks.append(ReadBlock(function, start, end - start, tuple(cur)))
        result = tuple(blocks)
        self._plan_cache[key] = result
        return result


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def registry_dir() -> Path:
    """Directorio de perfiles: ``OBE_REGISTRY_DIR``, datos del paquete o checkout de desarrollo."""
    env = os.environ.get("OBE_REGISTRY_DIR")
    if env:
        return Path(env)
    pkg = Path(__file__).resolve().parent.parent / "registry"
    if pkg.is_dir():
        return pkg
    return Path(__file__).resolve().parents[3] / "registry"


def resolve_profile_path(ref: str, base_dir: Optional[Path] = None) -> Path:
    if ref.endswith(".json") or "/" in ref or "\\" in ref:
        p = Path(ref)
        if not p.is_absolute() and base_dir is not None and not p.exists():
            p = base_dir / p
        return p
    return registry_dir() / f"{ref}.json"


def _order(v: object, what: str, path: str) -> Order:
    try:
        return Order(str(v).upper())
    except ValueError as exc:
        raise ProfileError(f"{path}: {what} inválido: {v!r} (BIG|LITTLE)") from exc


def load_profile(ref: str | Path, base_dir: Optional[Path] = None) -> DeviceProfile:
    path = resolve_profile_path(str(ref), base_dir)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProfileError(f"Perfil no encontrado: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ProfileError(f"No se pudo leer el perfil {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileError(f"Perfil {path} no es JSON válido: {exc}") from exc
    return parse_profile(raw, path.stem, path)


def parse_profile(raw: object, name: str, source: Optional[Path] = None) -> DeviceProfile:
    where = str(source or name)
    if not isinstance(raw, dict):
        raise ProfileError(f"{where}: se esperaba un objeto JSON")
    device = raw.get("device") or {}
    protocol = str(device.get("protocol") or (raw.get("driver") or {}).get("protocol") or "")
    if "modbus" not in protocol.lower():
        raise ProfileError(f"{where}: no es un perfil Modbus (protocol={protocol!r})")
    regs_raw = raw.get("registers")
    if not isinstance(regs_raw, dict) or not regs_raw:
        raise ProfileError(f"{where}: sin sección 'registers'")

    conn = raw.get("connection") or {}
    byte_order = _order(conn.get("byte_order", "BIG"), "byte_order", where)
    word_order = _order(conn.get("word_order", "BIG"), "word_order", where)

    registers: dict[str, RegisterSpec] = {}
    sf_refs: dict[str, object] = {}
    for rname, r in regs_raw.items():
        if not isinstance(r, dict):
            raise ProfileError(f"{where}: registro '{rname}' inválido")
        try:
            rtype = RegType(str(r["type"]).upper())
            address = int(r["address"])
        except (KeyError, ValueError) as exc:
            raise ProfileError(f"{where}: registro '{rname}': tipo/dirección inválidos ({exc})") from exc
        if not 0 <= address <= 0xFFFF:
            raise ProfileError(f"{where}: registro '{rname}': dirección fuera de rango {address}")
        if "count" in r and int(r["count"]) != rtype.width:
            raise ProfileError(
                f"{where}: registro '{rname}': count={r['count']} incompatible con {rtype.value} "
                f"(requiere {rtype.width})"
            )
        if address + rtype.width > 0x10000:
            raise ProfileError(f"{where}: registro '{rname}' excede el espacio de direcciones")
        access = str(r.get("access", "RO")).upper()
        if access not in ("RO", "RW"):
            raise ProfileError(f"{where}: registro '{rname}': access inválido {access!r}")
        scale = r.get("scale", 1.0)
        scale = 1.0 if scale is None else float(scale)
        if not math.isfinite(scale) or scale == 0.0:
            raise ProfileError(f"{where}: registro '{rname}': scale inválido {scale!r}")
        function = str(r.get("function", "holding")).lower()
        if function not in ("holding", "input"):
            raise ProfileError(f"{where}: registro '{rname}': function inválida {function!r}")
        if "scale_register" in r:
            sf_refs[rname] = r["scale_register"]
        registers[rname] = RegisterSpec(
            name=rname, address=address, rtype=rtype, access=access, scale=scale,
            offset=float(r.get("offset", 0.0)), unit=str(r.get("unit", "")), function=function,
        )

    # Resolver scale_register (por nombre o por dirección) — estricto.
    by_addr = {(s.function, s.address): s for s in registers.values()}
    for rname, ref in sf_refs.items():
        sf: Optional[RegisterSpec] = None
        if isinstance(ref, str) and ref in registers:
            sf = registers[ref]
        else:
            try:
                sf = by_addr.get((registers[rname].function, int(str(ref))))
            except (TypeError, ValueError):
                sf = None
        if sf is None or sf.rtype not in (RegType.INT16, RegType.UINT16):
            raise ProfileError(f"{where}: registro '{rname}': scale_register {ref!r} no resuelve a un registro de 16 bit")
        registers[rname] = RegisterSpec(**{**_asdict(registers[rname]), "scale_register": sf.name})

    # Bindings canónicos.
    bindings: dict[str, Binding] = {}
    canon = raw.get("canonical") or {}
    if not isinstance(canon, dict):
        raise ProfileError(f"{where}: 'canonical' debe ser un objeto")
    for sig, b in canon.items():
        if sig not in ALL_SIGNALS:
            raise ProfileError(f"{where}: señal canónica desconocida '{sig}'")
        if not isinstance(b, dict) or "register" not in b:
            raise ProfileError(f"{where}: binding '{sig}' requiere 'register'")
        if b["register"] not in registers:
            raise ProfileError(f"{where}: binding '{sig}' apunta a registro inexistente '{b['register']}'")
        factor = float(b.get("factor", 1.0))
        sign = int(b.get("sign", 1))
        if sign not in (-1, 1) or not math.isfinite(factor) or factor <= 0:
            raise ProfileError(f"{where}: binding '{sig}': sign ∈ {{-1,1}} y factor > 0")
        reg = registers[b["register"]]
        if sig in CONTROL_SIGNALS and not reg.writable:
            raise ProfileError(f"{where}: binding '{sig}' requiere un registro RW ('{reg.name}' es RO)")
        if sig == "heartbeat" and (reg.rtype.is_signed or reg.rtype.is_float):
            raise ProfileError(f"{where}: binding 'heartbeat' requiere un entero sin signo")
        if sig in CONTROL_SIGNALS and reg.scale_register:
            raise ProfileError(f"{where}: binding '{sig}' no admite scale_register")
        bindings[sig] = Binding(sig, reg.name, factor, float(b.get("offset", 0.0)), sign)

    ver = (raw.get("verification") or {}).get("level", "unverified")
    if ver not in VERIFICATION_LEVELS:
        raise ProfileError(f"{where}: verification.level inválido {ver!r}")

    unit = device.get("slave_id_default")
    if unit is None:
        unit = (raw.get("driver") or {}).get("slave_id")
    return DeviceProfile(
        name=name,
        manufacturer=str(device.get("manufacturer", "")),
        model=str(device.get("model", "")),
        default_unit_id=int(unit) if unit is not None else None,
        byte_order=byte_order,
        word_order=word_order,
        registers=registers,
        bindings=bindings,
        verification_level=ver,
        notes=str((raw.get("verification") or {}).get("notes", "")),
        source=source,
    )


def _asdict(r: RegisterSpec) -> dict[str, Any]:
    return {
        "name": r.name, "address": r.address, "rtype": r.rtype, "access": r.access,
        "scale": r.scale, "offset": r.offset, "unit": r.unit, "function": r.function,
        "scale_register": r.scale_register,
    }


def list_profiles() -> list[str]:
    d = registry_dir()
    return sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []


def apply_scale(raw: float, scale: float) -> float:
    """Aplica ``scale`` evitando ruido binario cuando 1/scale es entero (p. ej. 0.01)."""
    if scale == 1.0:
        return float(raw)
    inv = 1.0 / scale
    if abs(inv - round(inv)) < 1e-9 and round(inv) != 0:
        return raw / round(inv)
    return raw * scale


def unapply_scale(value: float, scale: float) -> float:
    if scale == 1.0:
        return value
    inv = 1.0 / scale
    if abs(inv - round(inv)) < 1e-9 and round(inv) != 0:
        return value * round(inv)
    return value / scale
