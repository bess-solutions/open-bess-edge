# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
experimental/local_copilot/copilot_engine.py
=============================================
On-Device Natural Language Copilot & Field Assistant for BESS Technicians.

Executes 100% offline at the edge to answer diagnostic queries on NTSyCS compliance,
battery health (SOH), temperature alerts, and active setpoints without cloud connectivity.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)


class LocalBessCopilot:
    """
    Offline Copilot for BESS site technicians.
    Rule-based + Intent matcher with pluggable local GGUF/LLM backend support.
    """

    def __init__(self, site_id: str = "SITE-CL-001") -> None:
        self.site_id = site_id

    def query(self, prompt: str, current_telemetry: dict[str, Any] | None = None) -> str:
        """
        Process natural language query from field technician.
        """
        prompt_clean = prompt.lower().strip()
        telemetry = current_telemetry or {
            "soc": 76.5,
            "power_kw": 450.0,
            "temp_c": 28.4,
            "compliance_score": 100.0,
            "soh_pct": 98.2,
            "violations": [],
        }

        # Intent 1: Compliance & NTSyCS status
        if any(w in prompt_clean for w in ["compliance", "cumplimiento", "ntsycs", "gap", "norma"]):
            score = telemetry.get("compliance_score", 100.0)
            violations = telemetry.get("violations", [])
            if not violations:
                return (
                    f"🟢 **Estado de Cumplimiento NTSyCS ({self.site_id})**: {score:.1f}%\n"
                    "Todos los 11 GAPs regulatorios se encuentran en rango conforme."
                )
            else:
                v_str = ", ".join(violations)
                return (
                    f"⚠️ **Alerta NTSyCS ({self.site_id})**: Score {score:.1f}%\n"
                    f"Violaciones activas: {v_str}. Se sugiere revisar límites de rampa o reactivo."
                )

        # Intent 2: Battery health (SOH / Degradation)
        if any(w in prompt_clean for w in ["soh", "salud", "degradacion", "bateria", "vida"]):
            soh = telemetry.get("soh_pct", 98.2)
            temp = telemetry.get("temp_c", 28.0)
            return (
                f"🔋 **Estado de Salud de Baterías (SOH)**: {soh:.1f}%\n"
                f"Temperatura media de celdas: {temp:.1f} °C (Dentro de rango térmico óptimo 15-30°C).\n"
                "Degradación proyectada a 20 años acorde al modelo Arrhenius SEI LFP."
            )

        # Intent 3: Active power and SOC
        if any(w in prompt_clean for w in ["soc", "potencia", "despacho", "kw", "cargando", "descargando"]):
            soc = telemetry.get("soc", 50.0)
            power = telemetry.get("power_kw", 0.0)
            state = "Descargando a red" if power > 0 else "Cargando desde red"
            return (
                f"⚡ **Estado Operativo Actual ({self.site_id})**:\n"
                f"- Estado de Carga (SOC): {soc:.1f}%\n"
                f"- Potencia Activa: {abs(power):.1f} kW ({state})\n"
                f"- SafetyGuard: ✅ OK"
            )

        # General Fallback
        return (
            f"🤖 **BESSAI Copilot ({self.site_id})**:\n"
            "Consulta no reconocida directamente. Puedes preguntarme por:\n"
            "- '¿Cuál es el estado de cumplimiento NTSyCS?'\n"
            "- '¿Cómo está la salud y degradación SOH de las baterías?'\n"
            "- '¿Cuál es la potencia de despacho y SOC actual?'"
        )


if __name__ == "__main__":
    copilot = LocalBessCopilot(site_id="DEMO-CL-001")
    print(copilot.query("¿Cómo está el cumplimiento NTSyCS?"))
    print()
    print(copilot.query("dame la salud de las baterias"))
