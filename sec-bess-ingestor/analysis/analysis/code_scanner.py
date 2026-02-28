"""
analysis/code_scanner.py — Escanea el código fuente de open-bess-edge
──────────────────────────────────────────────────────────────────────
Lee los archivos .py del repositorio y detecta implementaciones reales
vs. las brechas documentadas en el compliance mapping.
Esto enriquece el análisis de brechas con evidencia de código real.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Optional

from config import BESS_EDGE_LOCAL

logger = logging.getLogger(__name__)


# ─── Patrones de búsqueda en código ──────────────────────────────────────────

CODE_PATTERNS = {
    "ramp_rate": {
        "patterns": [r"ramp", r"gradient", r"delta_p", r"dP_dt", r"rate_of_change"],
        "description": "Ramp rate limiting implementation",
        "gap_id": "GAP-001",
    },
    "frequency_response": {
        "patterns": [r"droop", r"frequency", r"freq", r"pfr", r"primary.*freq", r"f_grid"],
        "description": "Frequency response / droop control",
        "gap_id": "GAP-002",
    },
    "cen_telemetry": {
        "patterns": [r"cen[_\s]", r"coordinador", r"iccp", r"telemetry.*cen", r"cen.*publish"],
        "description": "CEN telemetry channel",
        "gap_id": "GAP-003",
    },
    "iec104": {
        "patterns": [r"iec.*104", r"60870", r"iec104", r"asdu", r"apdu"],
        "description": "IEC 60870-5-104 protocol driver",
        "gap_id": "GAP-004",
    },
    "tls_scada": {
        "patterns": [r"mtls", r"mutual.*tls", r"client.*cert", r"ssl_context.*verify_mode"],
        "description": "mTLS SCADA channel",
        "gap_id": "GAP-005",
    },
    "ieee2030_5": {
        "patterns": [r"2030\.5", r"sep2", r"derprogram", r"dercontrol", r"mirror.*usage"],
        "description": "IEEE 2030.5 / SEP 2.0 protocol",
        "gap_id": "GAP-006",
    },
    "reactive_power": {
        "patterns": [r"reactive", r"q_ref", r"var_", r"volt.?var", r"power_factor"],
        "description": "Reactive power (Q) control",
        "gap_id": "GAP-011",
    },
    "thd_monitoring": {
        "patterns": [r"thd", r"harmonic", r"flicker", r"power.?quality", r"pst\b"],
        "description": "Power quality monitoring (THD/flicker)",
        "gap_id": "GAP-010",
    },
}


# ─── Scanner ─────────────────────────────────────────────────────────────────

class CodeScanner:
    """
    Escanea el código fuente de open-bess-edge buscando implementaciones
    de features relacionados con las brechas normativas.
    """

    def __init__(self, bess_root: Optional[str] = None):
        self.bess_root = Path(bess_root or BESS_EDGE_LOCAL)
        self._available = self.bess_root.exists()
        if not self._available:
            logger.warning(
                f"open-bess-edge no encontrado en {self.bess_root}. "
                "Configura BESS_EDGE_LOCAL o clona el repo al lado."
            )
        else:
            logger.info(f"CodeScanner listo: {self.bess_root}")

    def scan_all(self) -> dict[str, "FeatureEvidence"]:
        """
        Escanea todos los .py del repo y retorna evidencia por feature.
        """
        if not self._available:
            return {}

        py_files = list(self.bess_root.rglob("*.py"))
        logger.info(f"Escaneando {len(py_files)} archivos Python en {self.bess_root.name}...")

        evidence: dict[str, FeatureEvidence] = {
            key: FeatureEvidence(key=key, info=info)
            for key, info in CODE_PATTERNS.items()
        }

        for py_file in py_files:
            # Excluir tests, venv, __pycache__
            rel = py_file.relative_to(self.bess_root)
            if any(part in str(rel) for part in ("test", ".venv", "__pycache__", "venv")):
                continue

            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                self._scan_file(py_file, source, evidence)
            except Exception as exc:
                logger.debug(f"Error leyendo {py_file}: {exc}")

        for ev in evidence.values():
            ev.finalize()

        found = sum(1 for ev in evidence.values() if ev.found)
        logger.info(f"Scan completo: {found}/{len(evidence)} features encontrados en código")
        return evidence

    def _scan_file(
        self,
        path: Path,
        source: str,
        evidence: dict[str, "FeatureEvidence"],
    ) -> None:
        source_lower = source.lower()
        rel_str = str(path.relative_to(self.bess_root))

        for key, ev in evidence.items():
            for pattern in CODE_PATTERNS[key]["patterns"]:
                matches = list(re.finditer(pattern, source_lower))
                if matches:
                    for m in matches[:3]:  # Máximo 3 ejemplos por archivo
                        line_num = source[:m.start()].count("\n") + 1
                        snippet = source[max(0, m.start()-30):m.end()+60].strip()
                        ev.add_match(rel_str, line_num, snippet)

    @staticmethod
    def enrich_gaps(
        gaps: list,
        evidence: dict[str, "FeatureEvidence"],
    ) -> list:
        """
        Enriquece GapItems con evidencia de código real.
        Si se encontró código, actualiza bess_code_ref con la ruta real.
        """
        for gap in gaps:
            for key, ev in evidence.items():
                if CODE_PATTERNS[key]["gap_id"] == gap.gap_id and ev.found:
                    # Actualizar referencia de código con archivos reales
                    files = list(ev.files_found)[:3]
                    gap.bess_code_ref = ", ".join(files)
                    # Si el código existe pero el status era "missing", subir a "partial"
                    if gap.bess_implementation_status == "missing":
                        gap.bess_implementation_status = "partial"
                        logger.info(
                            f"{gap.gap_id}: actualizado missing → partial "
                            f"(encontrado en {files[0]})"
                        )
        return gaps


class FeatureEvidence:
    """Evidencia de implementación encontrada en el código fuente."""

    def __init__(self, key: str, info: dict):
        self.key = key
        self.gap_id = info["gap_id"]
        self.description = info["description"]
        self.matches: list[dict] = []
        self.files_found: set[str] = set()
        self.found: bool = False
        self.confidence: str = "none"  # "none" | "low" | "medium" | "high"

    def add_match(self, filepath: str, line: int, snippet: str) -> None:
        self.matches.append({"file": filepath, "line": line, "snippet": snippet[:120]})
        self.files_found.add(filepath)

    def finalize(self) -> None:
        self.found = len(self.matches) > 0
        if not self.found:
            self.confidence = "none"
        elif len(self.files_found) >= 3:
            self.confidence = "high"
        elif len(self.files_found) >= 2:
            self.confidence = "medium"
        else:
            self.confidence = "low"

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "gap_id": self.gap_id,
            "description": self.description,
            "found": self.found,
            "confidence": self.confidence,
            "files": list(self.files_found),
            "match_count": len(self.matches),
            "examples": self.matches[:3],
        }
