# -*- coding: utf-8 -*-
"""
open-bess-edge/research/bpx_parameter_store.py
Módulo de Gestión de Parámetros Electroquímicos BPX v1.1.1 (Battery Parameter eXchange).
Estándar oficial de The Faraday Institution para celdas LFP/NMC.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger("OpenBESSEdge.Research.BPX")

@dataclass
class CellBPXParameters:
    cell_id: str
    chemistry: str
    nominal_capacity_ah: float
    nominal_voltage_v: float
    min_voltage_v: float
    max_voltage_v: float
    max_continuous_c_rate: float
    internal_resistance_mohm: float
    thermal_mass_j_per_k: float
    ambient_temp_ref_c: float = 25.0
    raw_bpx_schema: Dict[str, Any] = field(default_factory=dict)

class BPXParameterStore:
    """
    Repositorio de parámetros electroquímicos BPX v1.1.1 para Open BESS Edge.
    Permite cargar fichas estandarizadas de fabricantes (CATL, EVE, Gotion)
    sin revelar formulaciones propietarias.
    """
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path(__file__).parent / "bpx_definitions"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, CellBPXParameters] = {}
        self._init_default_lfp_profile()

    def _init_default_lfp_profile(self):
        """Inicializa el perfil canónico LFP 314Ah usado en proyectos BESS Solutions."""
        lfp_314ah = CellBPXParameters(
            cell_id="LFP_314Ah_Prismatic_C&I",
            chemistry="LiFePO4",
            nominal_capacity_ah=314.0,
            nominal_voltage_v=3.2,
            min_voltage_v=2.5,
            max_voltage_v=3.65,
            max_continuous_c_rate=0.5, # 0.5C para 2 horas
            internal_resistance_mohm=0.18, # 0.18 mOhm AC @ 1kHz
            thermal_mass_j_per_k=850.0,
            ambient_temp_ref_c=25.0,
            raw_bpx_schema={
                "BPX": "1.1.1",
                "Header": {
                    "Title": "LFP 314Ah Utility & C&I Cell Profile",
                    "Author": "BESS Solutions Engineering Swarm",
                    "Date": "2026-08-22"
                }
            }
        )
        self.cache[lfp_314ah.cell_id] = lfp_314ah

    def load_bpx_file(self, file_path: Path) -> CellBPXParameters:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        header = data.get("Header", {})
        cell_id = header.get("Title", file_path.stem)
        
        params = CellBPXParameters(
            cell_id=cell_id,
            chemistry=data.get("Chemistry", "LFP"),
            nominal_capacity_ah=float(data.get("NominalCapacityAh", 314.0)),
            nominal_voltage_v=float(data.get("NominalVoltageV", 3.2)),
            min_voltage_v=float(data.get("MinVoltageV", 2.5)),
            max_voltage_v=float(data.get("MaxVoltageV", 3.65)),
            max_continuous_c_rate=float(data.get("MaxContinuousCRate", 0.5)),
            internal_resistance_mohm=float(data.get("InternalResistance_mOhm", 0.18)),
            thermal_mass_j_per_k=float(data.get("ThermalMass_J_K", 850.0)),
            raw_bpx_schema=data
        )
        self.cache[cell_id] = params
        logger.info(f"[BPX] Perfil cargado exitosamente: {cell_id} ({params.nominal_capacity_ah} Ah)")
        return params

    def get_profile(self, cell_id: str) -> Optional[CellBPXParameters]:
        return self.cache.get(cell_id)

if __name__ == "__main__":
    store = BPXParameterStore()
    p = store.get_profile("LFP_314Ah_Prismatic_C&I")
    print(f"[OK] BPX Store inicializado. Perfil por defecto: {p.cell_id}, Química: {p.chemistry}, Capacidad: {p.nominal_capacity_ah} Ah")
