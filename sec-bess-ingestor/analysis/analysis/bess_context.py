"""
analysis/bess_context.py — Lectura automática de docs open-bess-edge
──────────────────────────────────────────────────────────────────────
Lee los documentos de compliance de BESSAI desde:
  1. Local (si BESS_EDGE_LOCAL apunta a un clon local)
  2. GitHub raw (fallback vía HTTP)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests

from config import (
    BESS_COMPLIANCE_DOCS, BESS_EDGE_GITHUB_RAW, BESS_EDGE_LOCAL,
    SEC_REQUEST_TIMEOUT, SEC_USER_AGENT,
)

logger = logging.getLogger(__name__)


def _read_local(doc_path: str) -> Optional[str]:
    local = Path(BESS_EDGE_LOCAL) / doc_path
    if local.exists():
        logger.debug(f"Leyendo local: {local}")
        return local.read_text(encoding="utf-8", errors="replace")
    return None


def _read_remote(doc_path: str) -> Optional[str]:
    url = BESS_EDGE_GITHUB_RAW + doc_path
    try:
        resp = requests.get(
            url,
            timeout=SEC_REQUEST_TIMEOUT,
            headers={"User-Agent": SEC_USER_AGENT},
        )
        resp.raise_for_status()
        logger.debug(f"Leyendo remoto: {url}")
        return resp.text
    except Exception as exc:
        logger.warning(f"No se pudo leer {url}: {exc}")
        return None


def load_bess_doc(doc_path: str) -> Optional[str]:
    """Carga un doc desde local o GitHub raw."""
    content = _read_local(doc_path)
    if content is None:
        content = _read_remote(doc_path)
    if content is None:
        logger.error(f"No se encontró: {doc_path}")
    return content


def load_all_bess_docs() -> dict[str, str]:
    """
    Carga todos los docs de compliance definidos en config.
    Retorna dict {doc_path: contenido}.
    """
    docs: dict[str, str] = {}
    for doc_path in BESS_COMPLIANCE_DOCS:
        content = load_bess_doc(doc_path)
        if content:
            docs[doc_path] = content
        else:
            logger.warning(f"Omitido (no disponible): {doc_path}")
    logger.info(f"Docs BESSAI cargados: {len(docs)}/{len(BESS_COMPLIANCE_DOCS)}")
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Estado de implementación extraído de los docs para el analizador
# ─────────────────────────────────────────────────────────────────────────────

IMPLEMENTATION_STATUS_MATRIX = {
    # key: (descripción de qué tiene BESSAI, estado)
    # Estados: "implemented", "partial", "planned", "missing"
    "soc_management": (
        "SOC bounds enforced via SafetyGuard (10%–90% default, configurable)",
        "implemented",
        "src/core/safety_guard.py",
    ),
    "power_ramp_rate": (
        "Ramp rate limiting: listed as Gap 🔴 High → planned v2.0",
        "planned",
        "docs/compliance/ntscys_compliance.md#gap-analysis",
    ),
    "frequency_response_primary": (
        "Primary Frequency Response droop curve: Gap 🟡 → planned v2.0",
        "planned",
        "docs/compliance/ntscys_compliance.md#gap-analysis",
    ),
    "iec_60870_5_104": (
        "IEC 60870-5-104 SCADA protocol: Gap 🟡 → planned v2.0",
        "planned",
        "docs/compliance/ntscys_compliance.md#gap-analysis",
    ),
    "telemetry_cen": (
        "CEN telemetry pipeline GCP Pub/Sub → CEN: 🔄 In progress",
        "partial",
        "docs/compliance/ntscys_compliance.md",
    ),
    "tls_scada_channel": (
        "TLS SCADA channel to CEN: Gap 🟡 → planned v1.5",
        "planned",
        "docs/compliance/ntscys_compliance.md#gap-analysis",
    ),
    "modbus_tcp": (
        "Modbus TCP driver: production-tested on Huawei SUN2000",
        "implemented",
        "src/drivers/modbus_driver.py",
    ),
    "ieee_2030_5": (
        "IEEE 2030.5: listed in supported protocol list but partial",
        "partial",
        "README.md",
    ),
    "iec_61850": (
        "IEC 61850: listed in drivers, scope limited",
        "partial",
        "src/drivers/",
    ),
    "iec_62443_sl1": (
        "IEC 62443 SL-1: implemented with SafetyGuard guardrails",
        "implemented",
        "docs/compliance/iec62443_mapping.md",
    ),
    "iec_62443_sl2": (
        "IEC 62443 SL-2: certification path documented, not yet achieved",
        "planned",
        "docs/compliance/iec_62443_sl2_certification_path.md",
    ),
    "cen_formal_certification": (
        "CEN formal certification submission: Gap 🟢 → post-v2.0",
        "planned",
        "docs/compliance/ntscys_compliance.md#gap-analysis",
    ),
    "access_control": (
        "API key auth in production, no default credentials",
        "implemented",
        "src/interfaces/dashboard_api.py",
    ),
    "audit_logging": (
        "Structured logging via structlog + Cloud Logging/OTel",
        "implemented",
        "src/core/",
    ),
    "vulnerability_mgmt": (
        "Dependabot + pip-audit in CI weekly",
        "implemented",
        ".github/workflows/",
    ),
    "reactive_power_control": (
        "Reactive power: monitoring only, control via inverter firmware",
        "partial",
        "docs/compliance/ntscys_compliance.md",
    ),
    "voltage_regulation": (
        "Voltage regulation: monitoring + setpoint via LUNA2000 FC06",
        "partial",
        "docs/compliance/ntscys_compliance.md",
    ),
    "power_quality_monitoring": (
        "Power quality metrics via Prometheus/OTel",
        "implemented",
        "src/core/telemetry.py",
    ),
    "ai_dispatch": (
        "DRL arbitrage agent (PPO ONNX) for market dispatch",
        "implemented",
        "src/agents/",
    ),
    "self_improvement": (
        "BESSAIEvolve weekly evolutionary loop",
        "implemented",
        "src/agents/bessai_evolve*.py",
    ),
}
