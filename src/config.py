#!/usr/bin/env python3
"""
open-bess-edge/src/config.py
==============================================================================
Configuración centralizada y tipada para Open BESS Edge.
Parámetros de red del Coordinador Eléctrico Nacional (CEN) y hardware BESS.
==============================================================================
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

EDGE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_YAML_PATH = EDGE_ROOT / "config" / "edge_config.yaml"


class BESSHardwareConfig(BaseModel):
    """Parámetros de placa y hardware del sistema BESS."""

    device_id: str = Field(default="bess-node-linares-01")
    site_name: str = Field(default="S/E Linares 66/15 kV")
    chemistry: str = Field(default="LFP_314Ah")
    p_nominal_mw: float = Field(
        default=1.0, description="Potencia nominal activa en MW"
    )
    e_nominal_mwh: float = Field(default=2.0, description="Capacidad nominal en MWh")
    v_nominal_ac_v: float = Field(
        default=400.0, description="Tensión nominal AC inversor (V)"
    )
    max_charge_c_rate: float = Field(default=0.5)
    max_discharge_c_rate: float = Field(default=1.0)


class GridCodeCENConfig(BaseModel):
    """Parámetros de cumplimiento de Código de Red (NTSyCS Cap. 3 & CEN CFyDR 2026)."""

    f_nominal_hz: float = Field(default=50.0, description="Frecuencia nominal del SEN")
    deadband_hz: float = Field(
        default=0.03, description="Banda muerta primaria (+/- 30 mHz)"
    )
    droop_r: float = Field(
        default=0.03, description="Estatismo permanente (s = 3%, rango 2%-5%)"
    )
    ffr_contingency_threshold_hz: float = Field(
        default=0.30, description="Umbral de contingencia severa FFR (300 mHz)"
    )
    ffr_max_response_time_ms: float = Field(
        default=500.0, description="Tiempo máximo de respuesta FFR sub-500ms"
    )
    normal_ramp_limit_pct_min: float = Field(
        default=20.0, description="Rampa máxima de operación normal (% Pn/min)"
    )
    volt_var_deadband_pct: float = Field(
        default=2.0, description="Banda muerta Q(V) (+/- 2% Vnom)"
    )
    q_max_mvar: float = Field(
        default=0.6, description="Capacidad máxima reactiva (+/- 0.6 MVAR)"
    )


class ModbusConfig(BaseModel):
    """Parámetros de enlace de comunicación Modbus TCP/RTU con PCS/BMS."""

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=502)
    unit_id: int = Field(default=1)
    timeout_s: float = Field(default=3.0)
    reconnect_delay_s: float = Field(default=2.0)
    max_reconnect_delay_s: float = Field(default=30.0)
    simulation_mode: bool = Field(
        default=True,
        description="Modo simulación en caso de no contar con hardware físico",
    )

    # Mapeo canónico de registros de retención (Holding Registers)
    reg_f_measured_x100: int = Field(
        default=100, description="Frecuencia de red x100 (ej. 5000 = 50.00 Hz)"
    )
    reg_v_grid_v: int = Field(default=101, description="Tensión de red RMS (V)")
    reg_p_actual_kw: int = Field(
        default=102, description="Potencia activa actual (+ = carga, - = descarga)"
    )
    reg_q_actual_kvar: int = Field(
        default=103,
        description="Potencia reactiva actual (+ = inductivo, - = capacitivo)",
    )
    reg_soc_pct_x10: int = Field(default=104, description="SOC x10 (ej. 855 = 85.5%)")
    reg_soh_pct_x10: int = Field(default=105, description="SOH x10 (ej. 982 = 98.2%)")
    reg_cell_v_min_mv: int = Field(default=106, description="Voltaje celda mínima (mV)")
    reg_cell_v_max_mv: int = Field(default=107, description="Voltaje celda máxima (mV)")
    reg_cell_t_max_c_x10: int = Field(
        default=108, description="Temperatura máxima celda x10 (°C)"
    )
    reg_dc_isolation_kohm: int = Field(default=109, description="Aislamiento DC (kOhm)")
    reg_p_setpoint_kw: int = Field(
        default=200, description="Registro de consigna de potencia activa (kW)"
    )
    reg_q_setpoint_kvar: int = Field(
        default=201, description="Registro de consigna de potencia reactiva (kVAR)"
    )


class EdgeConfig(BaseModel):
    """Configuración unificada del nodo de borde."""

    bess: BESSHardwareConfig = Field(default_factory=BESSHardwareConfig)
    grid: GridCodeCENConfig = Field(default_factory=GridCodeCENConfig)
    modbus: ModbusConfig = Field(default_factory=ModbusConfig)

    @classmethod
    def load_from_yaml(cls, path: Path | None = None) -> "EdgeConfig":
        cfg_path = path or CONFIG_YAML_PATH
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as fh:
                    raw_data = yaml.safe_load(fh)
                    if isinstance(raw_data, dict):
                        return cls.model_validate(raw_data)
            except (OSError, yaml.YAMLError, ValueError):
                pass
        return cls()


# Instancia global por defecto
edge_settings = EdgeConfig.load_from_yaml()
