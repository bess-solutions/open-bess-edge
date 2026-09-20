"""Configuración tipada y *estricta* de Open BESS Edge.

Principios:
* ``extra="forbid"``: una clave desconocida (p. ej. un typo en un parámetro de
  seguridad) es un error, no se ignora.
* Un YAML ilegible, con tipos incorrectos o incoherente lanza ``ConfigError``
  con el detalle; **nunca** se cae a valores por defecto en silencio.
* No hay valores por defecto que identifiquen un sitio físico real.
"""

from __future__ import annotations

import math
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .errors import ConfigError
from .safety.limits import SafetyLimits, load_limits


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NodeConfig(_Strict):
    device_id: str = Field("obe-node-01", pattern=r"^[A-Za-z0-9._-]{1,64}$")
    site_name: Optional[str] = Field(None, max_length=128)


class PlantConfig(_Strict):
    p_nominal_kw: float = Field(gt=0, le=1_000_000)
    e_nominal_kwh: float = Field(gt=0, le=10_000_000)
    v_nominal_v: float = Field(gt=0, le=1_000_000)
    s_max_kva: Optional[float] = Field(None, gt=0)
    max_charge_c_rate: float = Field(0.5, gt=0, le=10)
    max_discharge_c_rate: float = Field(1.0, gt=0, le=10)

    @property
    def p_discharge_cap_kw(self) -> float:
        """Límite efectivo de descarga: mínimo entre placa del PCS y C-rate de las celdas."""
        return min(self.p_nominal_kw, self.e_nominal_kwh * self.max_discharge_c_rate)

    @property
    def p_charge_cap_kw(self) -> float:
        return min(self.p_nominal_kw, self.e_nominal_kwh * self.max_charge_c_rate)


class GridConfig(_Strict):
    f_nominal_hz: float = Field(50.0, gt=40, lt=70)


class FFRConfig(_Strict):
    enabled: bool = True
    deadband_hz: float = Field(0.03, ge=0, le=0.5)
    droop_r: float = Field(0.03, ge=0.02, le=0.05)
    contingency_threshold_hz: float = Field(0.30, gt=0, le=3.0)
    ramp_pct_per_min: float = Field(20.0, gt=0, le=10_000)
    freq_invalid_hold_s: float = Field(1.0, ge=0, le=60)

    @model_validator(mode="after")
    def _ordered(self) -> FFRConfig:
        if not self.deadband_hz < self.contingency_threshold_hz:
            raise ValueError("ffr: se exige deadband_hz < contingency_threshold_hz")
        return self


class ReactiveMode(str, Enum):
    VOLT_VAR_Q_V = "VOLT_VAR_Q_V"
    FIXED_Q = "FIXED_Q"
    POWER_FACTOR = "POWER_FACTOR"
    COS_PHI_P = "COS_PHI_P"
    DISABLED = "DISABLED"


class VoltVarConfig(_Strict):
    mode: ReactiveMode = ReactiveMode.VOLT_VAR_Q_V
    q_max_kvar: float = Field(0.0, ge=0)
    deadband_pct: float = Field(2.0, ge=0, le=20)
    slope_k_q: float = Field(10.0, gt=0, le=1000)          # % Qmax por % de V
    fixed_q_kvar: float = 0.0
    power_factor: float = Field(1.0, ge=0.5, le=1.0)
    pf_excitation: str = Field("capacitive", pattern="^(capacitive|inductive)$")
    # Puntos (P/Pnom, cosφ) de la curva cosφ(P), P/Pnom creciente en [0, 1].
    cos_phi_p_curve: tuple[tuple[float, float], ...] = ((0.0, 1.0), (1.0, 1.0))
    cos_phi_p_excitation: str = Field("inductive", pattern="^(capacitive|inductive)$")
    invalid_hold_s: float = Field(1.0, ge=0, le=60)
    q_ramp_kvar_per_s: Optional[float] = Field(None, gt=0)

    @model_validator(mode="after")
    def _curve(self) -> VoltVarConfig:
        pts = self.cos_phi_p_curve
        if len(pts) < 2:
            raise ValueError("volt_var.cos_phi_p_curve requiere al menos 2 puntos")
        xs = [p[0] for p in pts]
        if any(not (0.0 <= x <= 1.0) for x in xs) or any(b <= a for a, b in zip(xs, xs[1:])):
            raise ValueError("volt_var.cos_phi_p_curve: P/Pnom debe ser estrictamente creciente en [0, 1]")
        if any(not (0.5 <= pf <= 1.0) for _, pf in pts):
            raise ValueError("volt_var.cos_phi_p_curve: cosφ debe estar en [0.5, 1.0]")
        return self


class DispatchConfig(_Strict):
    """Consigna base (despacho) sobre la cual actúa la respuesta en frecuencia."""

    p_base_kw: float = 0.0
    external_timeout_s: float = Field(30.0, gt=0, le=86_400)


class ModbusConfig(_Strict):
    host: str = Field("127.0.0.1", min_length=1, max_length=253)
    port: int = Field(502, ge=1, le=65535)
    unit_id: Optional[int] = Field(None, ge=0, le=255)   # None = valor por defecto del perfil (o 1)
    profile: str = "open_bess_edge_reference"
    timeout_s: float = Field(0.5, gt=0, le=60)
    reconnect_min_s: float = Field(0.5, gt=0, le=600)
    reconnect_max_s: float = Field(30.0, gt=0, le=3600)
    verify_writes: bool = True
    verify_every_n_cycles: int = Field(10, ge=1, le=10_000)
    verify_tolerance_kw: float = Field(1.0, ge=0)
    max_read_gap: int = Field(0, ge=0, le=120)

    @model_validator(mode="after")
    def _ordered(self) -> ModbusConfig:
        if self.reconnect_min_s > self.reconnect_max_s:
            raise ValueError("modbus: reconnect_min_s no puede superar reconnect_max_s")
        return self


class RuntimeConfig(_Strict):
    cycle_ms: int = Field(100, ge=10, le=5000)
    comm_loss_hold_s: float = Field(2.0, ge=0, le=60)
    startup_valid_cycles: int = Field(3, ge=1, le=1000)
    ffr_latency_budget_ms: float = Field(500.0, gt=0)
    write_fail_safe_after: int = Field(3, ge=1, le=1000)
    tracking_tolerance_pct: float = Field(10.0, gt=0, le=100)
    tracking_alarm_s: float = Field(10.0, gt=0)
    monitor_only: bool = False


class AuditConfig(_Strict):
    path: Optional[Path] = None
    max_bytes: int = Field(50_000_000, ge=10_000)
    backups: int = Field(5, ge=0, le=100)
    setpoint_log_interval_s: float = Field(60.0, gt=0)
    setpoint_log_delta_kw: float = Field(1.0, ge=0)


class HealthConfig(_Strict):
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = Field(8080, ge=1, le=65535)
    reset_token: Optional[str] = Field(None, min_length=8)


class SafetyConfig(_Strict):
    baseline_path: Optional[Path] = None
    limits: SafetyLimits = Field(default_factory=SafetyLimits)


class EdgeConfig(_Strict):
    node: NodeConfig = Field(default_factory=NodeConfig)
    plant: PlantConfig
    grid: GridConfig = Field(default_factory=GridConfig)
    ffr: FFRConfig = Field(default_factory=FFRConfig)
    volt_var: VoltVarConfig = Field(default_factory=VoltVarConfig)
    dispatch: DispatchConfig = Field(default_factory=DispatchConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    modbus: ModbusConfig = Field(default_factory=ModbusConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)

    @model_validator(mode="after")
    def _cross(self) -> EdgeConfig:
        p = self.plant
        s_max = self.s_max_kva
        if self.volt_var.q_max_kvar > s_max + 1e-9:
            raise ValueError(f"volt_var.q_max_kvar ({self.volt_var.q_max_kvar}) excede s_max_kva ({s_max:.1f})")
        if abs(self.dispatch.p_base_kw) > p.p_nominal_kw:
            raise ValueError("dispatch.p_base_kw excede la potencia nominal de la planta")
        if self.runtime.comm_loss_hold_s < self.runtime.cycle_ms / 1000.0 and self.runtime.comm_loss_hold_s != 0:
            raise ValueError("runtime.comm_loss_hold_s debe ser 0 o al menos un ciclo")
        if self.runtime.ffr_latency_budget_ms < self.runtime.cycle_ms:
            raise ValueError("runtime.ffr_latency_budget_ms no puede ser menor que un ciclo de control")
        lim = self.safety.limits.cell
        if not (lim.voltage_min_v < lim.voltage_max_v):
            raise ValueError("safety.limits.cell: rango de tensión inválido")
        mode = self.volt_var.mode
        if mode is ReactiveMode.VOLT_VAR_Q_V and self.volt_var.q_max_kvar == 0.0:
            # Q(V) con Qmax=0 no puede regular nada: se exige explicitar DISABLED.
            raise ValueError("volt_var: mode=VOLT_VAR_Q_V con q_max_kvar=0; use mode=DISABLED o defina q_max_kvar")
        return self

    @property
    def s_max_kva(self) -> float:
        if self.plant.s_max_kva is not None:
            return self.plant.s_max_kva
        return math.hypot(self.plant.p_nominal_kw, self.volt_var.q_max_kvar)


_ENV_PATH = "OBE_CONFIG"


def _format_validation_error(path: Path | str, exc: ValidationError) -> str:
    lines = [f"Configuración inválida ({path}):"]
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"]) or "<raíz>"
        lines.append(f"  - {loc}: {err['msg']}")
    return "\n".join(lines)


def parse_config(raw: object, *, source: str = "<dict>", base_dir: Path | None = None) -> EdgeConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"Configuración {source}: se esperaba un mapeo YAML en la raíz")
    try:
        cfg = EdgeConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(source, exc)) from exc
    except ValueError as exc:  # validadores cruzados
        raise ConfigError(f"Configuración inválida ({source}): {exc}") from exc

    # Resolución del baseline de seguridad (estricta).
    bp = cfg.safety.baseline_path
    if bp is not None:
        if not bp.is_absolute() and base_dir is not None:
            bp = (base_dir / bp).resolve()
        limits = load_limits(bp)
        safety = cfg.safety.model_copy(update={"limits": limits, "baseline_path": bp})
        cfg = cfg.model_copy(update={"safety": safety})
    return cfg


def load_config(path: Path | str | None = None) -> EdgeConfig:
    """Carga y valida la configuración. Ruta explícita o variable ``OBE_CONFIG``."""
    import os

    if path is None:
        env = os.environ.get(_ENV_PATH)
        if not env:
            raise ConfigError(
                f"No se indicó archivo de configuración (use --config o la variable {_ENV_PATH})"
            )
        path = env
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"Archivo de configuración no encontrado: {p}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"No se pudo leer la configuración {p}: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML inválido en {p}: {exc}") from exc
    return parse_config(raw, source=str(p), base_dir=p.parent)


def reference_config() -> EdgeConfig:
    """Configuración de referencia para simulación (planta de 1 MW / 2 MWh)."""
    return parse_config(
        {
            "node": {"device_id": "obe-sim-01", "site_name": "simulación"},
            "plant": {"p_nominal_kw": 1000.0, "e_nominal_kwh": 2000.0, "v_nominal_v": 400.0},
            "volt_var": {"q_max_kvar": 600.0},
        },
        source="<reference>",
    )
