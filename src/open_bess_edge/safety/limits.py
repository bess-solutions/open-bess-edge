"""Límites físicos y temporización de la envolvente de seguridad (BESS-GUARD).

Los valores por defecto reproducen ``data/bess_safety_baseline.json`` (LFP 314 Ah).
``load_limits`` es *estricto*: un archivo inexistente, ilegible, con JSON inválido
o con claves desconocidas lanza ``ConfigError``. Nunca cae silenciosamente a
valores por defecto (los límites de seguridad no pueden degradarse sin aviso).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..errors import ConfigError


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CellLimits(_Strict):
    voltage_min_v: float = Field(2.50, gt=0, lt=5)
    voltage_max_v: float = Field(3.65, gt=0, lt=5)
    voltage_nominal_v: float = Field(3.20, gt=0, lt=5)
    temp_max_c: float = Field(50.0, gt=-40, lt=120)
    temp_derate_c: float = Field(45.0, gt=-40, lt=120)
    temp_min_c: float = Field(-10.0, gt=-80, lt=60)
    temp_opt_min_c: float = Field(15.0)
    temp_opt_max_c: float = Field(35.0)
    max_cell_imbalance_mv: float = Field(50.0, gt=0)
    # Rangos de plausibilidad: fuera de ellos la lectura se considera *inválida*
    # (fallo de sensor/comunicación), no una violación física.
    plausible_voltage_v: tuple[float, float] = (0.1, 6.0)
    plausible_temp_c: tuple[float, float] = (-60.0, 200.0)

    @model_validator(mode="after")
    def _ordered(self) -> CellLimits:
        if not self.voltage_min_v < self.voltage_nominal_v < self.voltage_max_v:
            raise ValueError("cell_limits: se exige voltage_min < voltage_nominal < voltage_max")
        if not self.temp_derate_c < self.temp_max_c:
            raise ValueError("cell_limits: se exige temp_derate_c < temp_max_c")
        if not self.temp_min_c < self.temp_max_c:
            raise ValueError("cell_limits: se exige temp_min_c < temp_max_c")
        return self


class RackLimits(_Strict):
    dc_isolation_min_kohm: float = Field(500.0, gt=0)
    string_voltage_min_v: Optional[float] = Field(None, gt=0)
    string_voltage_max_v: Optional[float] = Field(None, gt=0)
    max_ambient_temp_c: Optional[float] = None
    # Estos dos se conservan del baseline para compatibilidad; los límites de
    # C-rate efectivos se toman de PlantConfig.
    max_charge_c_rate: Optional[float] = Field(None, gt=0)
    max_discharge_c_rate: Optional[float] = Field(None, gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> RackLimits:
        lo, hi = self.string_voltage_min_v, self.string_voltage_max_v
        if lo is not None and hi is not None and not lo < hi:
            raise ValueError("rack_limits: se exige string_voltage_min_v < string_voltage_max_v")
        return self


class SocLimits(_Strict):
    min_pct: float = Field(5.0, ge=0, le=100)
    max_pct: float = Field(95.0, ge=0, le=100)
    # Banda de reducción lineal de potencia previa al límite duro.
    taper_pct: float = Field(0.0, ge=0, le=50)

    @model_validator(mode="after")
    def _ordered(self) -> SocLimits:
        if not self.min_pct < self.max_pct:
            raise ValueError("soc: se exige min_pct < max_pct")
        if self.taper_pct * 2 >= (self.max_pct - self.min_pct):
            raise ValueError("soc: taper_pct demasiado grande para la ventana [min, max]")
        return self


class Timing(_Strict):
    trip_debounce_cycles: int = Field(1, ge=1, le=100)
    recovery_valid_cycles: int = Field(3, ge=1, le=10_000)
    temp_hysteresis_c: float = Field(2.0, ge=0)
    voltage_hysteresis_v: float = Field(0.02, ge=0)
    isolation_hysteresis_kohm: float = Field(50.0, ge=0)
    # None = los disparos enclavados sólo se liberan con un reset explícito del operador.
    auto_reset_after_s: Optional[float] = Field(None, gt=0)


class GridAlarms(_Strict):
    """Umbrales de alarma de red (sólo alarma; el ride-through lo decide la protección)."""

    f_alarm_low_hz: Optional[float] = None
    f_alarm_high_hz: Optional[float] = None
    v_alarm_low_pu: Optional[float] = Field(None, gt=0)
    v_alarm_high_pu: Optional[float] = Field(None, gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> GridAlarms:
        if None not in (self.f_alarm_low_hz, self.f_alarm_high_hz) and not (
            self.f_alarm_low_hz < self.f_alarm_high_hz  # type: ignore[operator]
        ):
            raise ValueError("grid_alarms: f_alarm_low_hz debe ser < f_alarm_high_hz")
        if None not in (self.v_alarm_low_pu, self.v_alarm_high_pu) and not (
            self.v_alarm_low_pu < self.v_alarm_high_pu  # type: ignore[operator]
        ):
            raise ValueError("grid_alarms: v_alarm_low_pu debe ser < v_alarm_high_pu")
        return self


_KNOWN_SIGNALS = frozenset({
    "frequency_hz", "v_grid_v", "p_kw", "q_kvar", "soc_pct", "soh_pct",
    "cell_v_min_v", "cell_v_max_v", "cell_t_max_c", "cell_t_min_c",
    "isolation_kohm", "string_v_v", "ambient_c",
})


class SafetyLimits(_Strict):
    cell: CellLimits = Field(default_factory=CellLimits)
    rack: RackLimits = Field(default_factory=RackLimits)
    soc: SocLimits = Field(default_factory=SocLimits)
    timing: Timing = Field(default_factory=Timing)
    grid: GridAlarms = Field(default_factory=GridAlarms)
    # Señales sin las cuales el control NO puede operar (fail-closed).
    required_signals: tuple[str, ...] = (
        "soc_pct",
        "cell_v_min_v",
        "cell_v_max_v",
        "cell_t_max_c",
        "isolation_kohm",
    )

    @model_validator(mode="after")
    def _signals(self) -> SafetyLimits:
        unknown = set(self.required_signals) - _KNOWN_SIGNALS
        if unknown:
            raise ValueError(f"required_signals contiene señales desconocidas: {sorted(unknown)}")
        return self


# Claves informativas del baseline histórico que no son límites.
_INFORMATIVE = {"chemistry", "guard_codes", "safety_actions", "standard_ref"}


def load_limits(path: Path | str) -> SafetyLimits:
    """Carga límites desde el JSON de baseline (formato histórico o formato v3).

    Formato histórico: ``cell_limits`` / ``rack_limits`` (+ claves informativas).
    Formato v3: claves ``cell`` / ``rack`` / ``soc`` / ``timing`` / ``grid``.
    """
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Baseline de seguridad no encontrado: {p}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"No se pudo leer el baseline de seguridad {p}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Baseline de seguridad {p} no es JSON válido: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Baseline de seguridad {p}: se esperaba un objeto JSON")

    data = {k: v for k, v in raw.items() if k not in _INFORMATIVE}
    if "cell_limits" in data:
        data["cell"] = data.pop("cell_limits")
    if "rack_limits" in data:
        data["rack"] = data.pop("rack_limits")
    try:
        return SafetyLimits.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Baseline de seguridad {p} inválido:\n{exc}") from exc
