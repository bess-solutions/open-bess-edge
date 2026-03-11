"""
analysis/gap_analyzer.py — Motor de análisis de brechas normativas
───────────────────────────────────────────────────────────────────
Cruza la normativa extraída de SEC Chile con el estado de
implementación de open-bess-edge para detectar brechas regulatorias.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from analysis.bess_context import IMPLEMENTATION_STATUS_MATRIX, load_all_bess_docs

logger = logging.getLogger(__name__)

# ─── Tipos ────────────────────────────────────────────────────────────────────

PRIORITY = {
    "critical": "🔴 Crítico",
    "medium": "🟡 Medio",
    "low": "🟢 Bajo",
    "info": "ℹ️ Informativo",
}

STATUS = {
    "implemented": "✅ Implementado",
    "partial": "⚠️ Parcial",
    "planned": "🔄 Planificado",
    "missing": "❌ No implementado",
}


@dataclass
class GapItem:
    gap_id: str                     # ID único
    norm_ref: str                   # Referencia normativa (ej: "NTSyCS Art. 4.3")
    sec_document_title: str         # Título del doc SEC que originó la brecha
    sec_document_url: str           # URL del doc SEC
    description: str                # Descripción de la brecha
    bess_current_state: str         # Qué hace BESSAI actualmente
    bess_code_ref: str              # Archivo o módulo relevante
    bess_implementation_status: str # "implemented" | "partial" | "planned" | "missing"
    priority: str                   # "critical" | "medium" | "low" | "info"
    technical_action: str           # Acción técnica recomendada
    estimated_effort: str           # Estimación de esfuerzo
    relevant_sec_text: str = ""     # Fragmento del texto SEC
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def priority_label(self) -> str:
        return PRIORITY.get(self.priority, self.priority)

    @property
    def status_label(self) -> str:
        return STATUS.get(self.bess_implementation_status, self.bess_implementation_status)


# ─── Base de conocimiento de brechas regulatorias ─────────────────────────────

#
# Cada regla define un patrón de normativa de SEC y cómo mapearlo
# a una brecha en open-bess-edge.
#
REGULATORY_RULES: list[dict] = [
    # ── NTSyCS / CEN ──────────────────────────────────────────────────────────
    {
        "gap_id": "GAP-001",
        "triggers": ["ramp", "rampa", "gradiente", "rate of change", "dt"],
        "norm_ref": "NTSyCS Cap. 4.2 — Control de Potencia",
        "description": (
            "La NTSyCS exige límites de rampa de potencia (MW/min) para unidades "
            "BESS conectadas al SEN. BESSAI no aplica ramp rate limiting en el "
            "driver Modbus; el setpoint se escribe directo sin gradiente."
        ),
        "bess_key": "power_ramp_rate",
        "priority": "critical",
        "technical_action": (
            "Implementar RampRateGuard en SafetyGuard que limite δP/δt "
            "según parámetro configurable (ej. 10%Pnom/min por defecto). "
            "Ver BEP-0202 pending."
        ),
        "effort": "3–5 días",
    },
    {
        "gap_id": "GAP-002",
        "triggers": ["frecuencia", "frequency", "pfr", "droop", "inercia", "inertia"],
        "norm_ref": "NTSyCS Cap. 4.3 — Respuesta de Frecuencia Primaria",
        "description": (
            "BESSAI carece de implementación de curva droop para Respuesta en "
            "Frecuencia Primaria (PFR). La NTSyCS requiere que unidades ≥1MW "
            "participen en regulación de frecuencia con tiempo de respuesta <2s."
        ),
        "bess_key": "frequency_response_primary",
        "priority": "critical",
        "technical_action": (
            "Implementar FrequencyResponseAgent que monitoree f_grid via Modbus "
            "FC03 y calcule setpoint de potencia según curva droop db±0.1Hz. "
            "Integrar con SafetyGuard para override de DRL agent en emergencia."
        ),
        "effort": "5–8 días",
    },
    {
        "gap_id": "GAP-003",
        "triggers": ["telemetría", "telemetria", "scada", "datos en tiempo real",
                     "reporte", "supervisión", "supervisión del coordinador"],
        "norm_ref": "NTSyCS Cap. 6.1 — Telemetría al Coordinador Eléctrico",
        "description": (
            "La NTSyCS exige canal de telemetría en tiempo real al Coordinador "
            "Eléctrico Nacional (CEN). El pipeline GCP Pub/Sub → CEN está marcado "
            "como 🔄 In Progress en BESSAI; no hay canal directo certificado."
        ),
        "bess_key": "telemetry_cen",
        "priority": "critical",
        "technical_action": (
            "Completar CENPublisher en src/core/publishers/cen_publisher.py "
            "con endpoint TLS dedicado. Validar formato ICCP/IEC 60870-5-101 "
            "o ICCP TCP/IP si el CEN lo admite."
        ),
        "effort": "10–15 días",
    },
    {
        "gap_id": "GAP-004",
        "triggers": ["iec 60870", "60870", "iccp", "dnp3", "scada protocol"],
        "norm_ref": "NTSyCS Cap. 6.2 — Protocolos de Comunicación SCADA",
        "description": (
            "IEC 60870-5-104 es el protocolo SCADA estándar exigido por el CEN "
            "para supervisión de unidades de generación/almacenamiento. BESSAI "
            "soporta Modbus TCP e IEC 61850 parcial, pero NO IEC 60870-5-104."
        ),
        "bess_key": "iec_60870_5_104",
        "priority": "critical",
        "technical_action": (
            "Implementar src/drivers/iec104_driver.py usando librería "
            "'lib60870-python' o 'pyiec60870'. Registrar en HardwareRegistry. "
            "Añadir tests de integración con simulador SCADA."
        ),
        "effort": "8–12 días",
    },
    {
        "gap_id": "GAP-005",
        "triggers": ["tls", "cifrado", "canal seguro", "vpn", "ssl",
                     "comunicación segura"],
        "norm_ref": "NTSyCS 2024 Anexo 8 — Ciberseguridad",
        "description": (
            "La NTSyCS 2024 requiere canal TLS dedicado entre el gateway edge "
            "y el SCADA del CEN. BESSAI usa TLS en la API dashboard, pero el "
            "canal SCADA→CEN aún no implementa TLS mutuo (mTLS)."
        ),
        "bess_key": "tls_scada_channel",
        "priority": "medium",
        "technical_action": (
            "Configurar mTLS en CENPublisher. Gestionar certificados via "
            "Let's Encrypt o CA del CEN según contrato de conexión."
        ),
        "effort": "2–3 días",
    },
    # ── IEEE 2030.5 / DER ──────────────────────────────────────────────────────
    {
        "gap_id": "GAP-006",
        "triggers": ["ieee 2030", "2030.5", "sep 2.0", "smart energy",
                     "der", "sunspec", "openadr"],
        "norm_ref": "Res. Exenta CNE — IEEE 2030.5 para DER conectados a distribución",
        "description": (
            "Para BESS conectados a redes de distribución (BTD o media tensión), "
            "la CNE recomienda IEEE 2030.5 como protocolo de comunicación con el "
            "operador de distribución. La implementación en BESSAI es parcial."
        ),
        "bess_key": "ieee_2030_5",
        "priority": "medium",
        "technical_action": (
            "Completar src/drivers/ieee2030_5_driver.py. Implementar "
            "DERProgram, DERControl y MirrorUsagePoint endpoints. "
            "Certificar con OpenADR Alliance si aplica."
        ),
        "effort": "6–10 días",
    },
    # ── Decreto 88 / PMGD ─────────────────────────────────────────────────────
    {
        "gap_id": "GAP-007",
        "triggers": ["pmgd", "pmpe", "pequeño medio", "decreto 88",
                     "generación distribuida", "autoconsumo"],
        "norm_ref": "Decreto N°88/2020 (mod. 2023) — Reglamento PMGD",
        "description": (
            "El Decreto 88 actualizado 2023 establece requisitos técnicos "
            "específicos para PMGD con almacenamiento (BESS), incluyendo "
            "parámetros de conexión, calidad de energía y reporte mensual "
            "a la SEC. BESSAI no documenta cumplimiento específico con D88."
        ),
        "bess_key": "cen_formal_certification",
        "priority": "medium",
        "technical_action": (
            "Crear docs/compliance/decreto88_pmgd_mapping.md con tabla "
            "de cumplimiento. Implementar reporte mensual automático en "
            "src/scripts/pmgd_monthly_report.py vía SEC e-Declarador API."
        ),
        "effort": "4–6 días",
    },
    # ── Ley 21.185 / ERNC ─────────────────────────────────────────────────────
    {
        "gap_id": "GAP-008",
        "triggers": ["21.185", "ernc", "energía renovable no convencional",
                     "certificado ernc", "sello verde", "mfre"],
        "norm_ref": "Ley N°21.185 — ERNC y Almacenamiento",
        "description": (
            "La Ley 21.185 actualiza el marco regulatorio de ERNC e incorpora "
            "el almacenamiento como categoría explícita. Requiere registro en "
            "el sistema MFRE de la CNE para acceder a beneficios tarifararios."
        ),
        "bess_key": "cen_formal_certification",
        "priority": "low",
        "technical_action": (
            "Documentar proceso de registro MFRE en docs/compliance/. "
            "No requiere cambios de código, pero sí checklist operacional."
        ),
        "effort": "1–2 días",
    },
    # ── Resolución Exenta SEC — Ciberseguridad ────────────────────────────────
    {
        "gap_id": "GAP-009",
        "triggers": ["ciberseguridad", "cybersecurity", "iec 62443", "62443",
                     "seguridad industrial", "ot security"],
        "norm_ref": "Res. Exenta SEC 2024 — Ciberseguridad Infraestructura Crítica",
        "description": (
            "La SEC emitió en 2024 requisitos de ciberseguridad para operadores "
            "de infraestructura eléctrica crítica alineados con IEC 62443 SL-2 "
            "(no SL-1). BESSAI implementa SL-1; la certificación SL-2 está "
            "en roadmap pero sin fecha comprometida."
        ),
        "bess_key": "iec_62443_sl2",
        "priority": "medium",
        "technical_action": (
            "Seguir docs/compliance/iec_62443_sl2_certification_path.md. "
            "Priorizar SR 1.1 (identity mgmt), SR 2.1 (authorization), "
            "SR 3.1 (communication integrity) para alcanzar SL-2."
        ),
        "effort": "15–25 días",
    },
    # ── Calidad de Energía ────────────────────────────────────────────────────
    {
        "gap_id": "GAP-010",
        "triggers": ["calidad de energía", "power quality", "thd", "armónicos",
                     "flicker", "tensión", "voltaje", "ieee 519"],
        "norm_ref": "NTCSE — Norma Técnica de Calidad de Servicio Eléctrico",
        "description": (
            "La NTCSE de la SEC/CNE establece límites de THD, flicker y "
            "desbalance de tensión para unidades conectadas. BESSAI monitorea "
            "tensión pero no valida explícitamente estos límites en tiempo real."
        ),
        "bess_key": "power_quality_monitoring",
        "priority": "medium",
        "technical_action": (
            "Añadir PowerQualityGuard en SafetyGuard con alertas si THD_V > 5% "
            "o flicker Pst > 1.0 según NTCSE. Registrar eventos en telemetría."
        ),
        "effort": "3–5 días",
    },
    # ── Potencia Reactiva ─────────────────────────────────────────────────────
    {
        "gap_id": "GAP-011",
        "triggers": ["potencia reactiva", "reactive power", "var", "factor de potencia",
                     "power factor", "compensación reactiva"],
        "norm_ref": "NTSyCS Cap. 4.4 — Control de Potencia Reactiva",
        "description": (
            "NTSyCS requiere control de potencia reactiva (Q) en generadores ≥1MW. "
            "BESSAI monitorea Q pero el control se delega al firmware del inversor "
            "sin integración directa con el agente de despacho."
        ),
        "bess_key": "reactive_power_control",
        "priority": "medium",
        "technical_action": (
            "Expandir DRL agent o implementar Volt-VAR controller separado "
            "que ajuste setpoint Q del inversor vía Modbus FC16 en función "
            "de la tensión de punto de acoplamiento común (PCC)."
        ),
        "effort": "5–7 días",
    },
]


# ─── Analizador ───────────────────────────────────────────────────────────────

class GapAnalyzer:
    """
    Analiza brechas entre la normativa de SEC extraída y open-bess-edge.
    """

    def __init__(self):
        self._bess_docs = load_all_bess_docs()
        logger.info(f"GapAnalyzer listo. Docs BESSAI: {len(self._bess_docs)}")

    def analyze(self, sec_data: dict) -> list[GapItem]:
        """
        Analiza todos los registros SEC y produce lista de GapItems.
        sec_data debe tener la estructura guardada por SECScraper.save().
        """
        records = sec_data.get("records", [])
        logger.info(f"Analizando {len(records)} registros de SEC...")

        gaps: list[GapItem] = []
        seen_gap_ids: set[str] = set()

        # 1. Brechas disparadas por contenido SEC real
        for record in records:
            combined_text = (
                record.get("title", "")
                + " "
                + record.get("body_text", "")
            ).lower()
            for rule in REGULATORY_RULES:
                if any(trigger in combined_text for trigger in rule["triggers"]):
                    gap = self._build_gap_from_rule(rule, record)
                    # Evitar duplicados (misma brecha en múltiples docs SEC)
                    if gap.gap_id not in seen_gap_ids:
                        gaps.append(gap)
                        seen_gap_ids.add(gap.gap_id)

        # 2. Brechas estructurales conocidas (independientes del scraping)
        for rule in REGULATORY_RULES:
            if rule["gap_id"] not in seen_gap_ids:
                bess_key = rule["bess_key"]
                bess_info = IMPLEMENTATION_STATUS_MATRIX.get(bess_key, (
                    "Sin información en docs BESSAI", "missing", "N/A"
                ))
                gap = GapItem(
                    gap_id=rule["gap_id"],
                    norm_ref=rule["norm_ref"],
                    sec_document_title="[Base de conocimiento normativo]",
                    sec_document_url="https://www.sec.cl",
                    description=rule["description"],
                    bess_current_state=bess_info[0],
                    bess_code_ref=bess_info[2],
                    bess_implementation_status=bess_info[1],
                    priority=rule["priority"],
                    technical_action=rule["technical_action"],
                    estimated_effort=rule["effort"],
                )
                gaps.append(gap)
                seen_gap_ids.add(gap.gap_id)

        gaps.sort(key=lambda g: {"critical": 0, "medium": 1, "low": 2, "info": 3}[g.priority])
        logger.info(
            f"Análisis completo: {len(gaps)} brechas "
            f"({sum(1 for g in gaps if g.priority == 'critical')} críticas)"
        )
        return gaps

    def _build_gap_from_rule(self, rule: dict, sec_record: dict) -> GapItem:
        bess_key = rule["bess_key"]
        bess_info = IMPLEMENTATION_STATUS_MATRIX.get(bess_key, (
            "Sin información en docs BESSAI", "missing", "N/A"
        ))
        relevant_text = self._extract_relevant_fragment(
            sec_record.get("body_text", ""), rule["triggers"]
        )
        return GapItem(
            gap_id=rule["gap_id"],
            norm_ref=rule["norm_ref"],
            sec_document_title=sec_record.get("title", "Desconocido"),
            sec_document_url=sec_record.get("url", ""),
            description=rule["description"],
            bess_current_state=bess_info[0],
            bess_code_ref=bess_info[2],
            bess_implementation_status=bess_info[1],
            priority=rule["priority"],
            technical_action=rule["technical_action"],
            estimated_effort=rule["effort"],
            relevant_sec_text=relevant_text,
        )

    def _extract_relevant_fragment(self, text: str, triggers: list[str]) -> str:
        """Extrae un fragmento de texto alrededor de la primera keyword encontrada."""
        lower = text.lower()
        for trigger in triggers:
            idx = lower.find(trigger)
            if idx != -1:
                start = max(0, idx - 100)
                end = min(len(text), idx + 300)
                return "…" + text[start:end].strip() + "…"
        return ""

    def summary_stats(self, gaps: list[GapItem]) -> dict:
        return {
            "total": len(gaps),
            "by_priority": {
                "critical": sum(1 for g in gaps if g.priority == "critical"),
                "medium": sum(1 for g in gaps if g.priority == "medium"),
                "low": sum(1 for g in gaps if g.priority == "low"),
            },
            "by_status": {
                "missing": sum(1 for g in gaps if g.bess_implementation_status == "missing"),
                "planned": sum(1 for g in gaps if g.bess_implementation_status == "planned"),
                "partial": sum(1 for g in gaps if g.bess_implementation_status == "partial"),
                "implemented": sum(1 for g in gaps if g.bess_implementation_status == "implemented"),
            },
        }
