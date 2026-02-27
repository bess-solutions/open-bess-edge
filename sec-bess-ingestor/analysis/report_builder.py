"""
analysis/report_builder.py — Generador de reportes Markdown
─────────────────────────────────────────────────────────────
Produce reportes ricos de brechas normativas entre SEC Chile
y open-bess-edge, listos para publicar como Pull Request.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from analysis.gap_analyzer import GapItem, GapAnalyzer, STATUS, PRIORITY
from config import REPORTS_DIR

logger = logging.getLogger(__name__)

# Fecha formateada
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class ReportBuilder:
    """Genera reportes Markdown de brechas normativas."""

    def __init__(self, analyzer: Optional[GapAnalyzer] = None):
        self.analyzer = analyzer or GapAnalyzer()

    def build_full_report(
        self,
        gaps: list[GapItem],
        sec_data: dict,
    ) -> str:
        """Genera el reporte completo en Markdown."""
        stats = self.analyzer.summary_stats(gaps)
        scraped_at = sec_data.get("scraped_at", "N/A")
        total_records = sec_data.get("total_records", 0)
        bess_relevant = sec_data.get("bess_relevant_count", 0)

        lines = [
            "# 🔍 Análisis de Brechas Normativas — SEC Chile × Open-BESS-Edge",
            "",
            f"> **Generado:** {_now_iso()}  ",
            f"> **Datos SEC:** {total_records} documentos scraped,",
            f"> {bess_relevant} relevantes a BESS  ",
            f"> **Repo analizado:** [bess-solutions/open-bess-edge](https://github.com/bess-solutions/open-bess-edge)  ",
            f"> **Fuente:** [Superintendencia de Electricidad y Combustibles](https://www.sec.cl)  ",
            "",
            "---",
            "",
            "## 📊 Resumen Ejecutivo",
            "",
            "| Indicador | Valor |",
            "|---|---|",
            f"| Total de brechas identificadas | **{stats['total']}** |",
            f"| 🔴 Críticas | **{stats['by_priority']['critical']}** |",
            f"| 🟡 Medias | **{stats['by_priority']['medium']}** |",
            f"| 🟢 Bajas | **{stats['by_priority']['low']}** |",
            f"| ❌ Sin implementar | {stats['by_status']['missing']} |",
            f"| 🔄 Planificadas | {stats['by_status']['planned']} |",
            f"| ⚠️ Parciales | {stats['by_status']['partial']} |",
            f"| ✅ Implementadas | {stats['by_status']['implemented']} |",
            "",
            "---",
            "",
            "## ⚠️ Índice de Brechas por Prioridad",
            "",
        ]

        # Índice compacto
        for priority in ["critical", "medium", "low"]:
            priority_gaps = [g for g in gaps if g.priority == priority]
            if not priority_gaps:
                continue
            icon = {"critical": "🔴", "medium": "🟡", "low": "🟢"}[priority]
            lines.append(f"### {icon} {priority.capitalize()}")
            lines.append("")
            for g in priority_gaps:
                lines.append(f"- [{g.gap_id}] **{g.norm_ref}** — {g.bess_implementation_status.upper()}")
            lines.append("")

        lines += [
            "---",
            "",
            "## 📋 Detalle de Brechas",
            "",
        ]

        for g in gaps:
            lines += self._render_gap(g)

        lines += [
            "---",
            "",
            "## 🗺️ Mapa de Acción Recomendada",
            "",
            "| Gap ID | Brecha | Esfuerzo | Prioridad | Estado BESSAI |",
            "|---|---|---|---|---|",
        ]
        for g in gaps:
            lines.append(
                f"| {g.gap_id} | {g.norm_ref} | {g.estimated_effort} "
                f"| {g.priority_label} | {g.status_label} |"
            )

        lines += [
            "",
            "---",
            "",
            "## 📚 Marco Normativo de Referencia",
            "",
            "| Norma | Organismo | Aplicabilidad BESS |",
            "|---|---|---|",
            "| NTSyCS 2022 | Coordinador Eléctrico Nacional (CEN) | ✅ Obligatoria para ≥1MW |",
            "| Decreto N°88/2020 (mod. 2023) | MEN | ✅ PMGD con almacenamiento |",
            "| Ley N°21.185 (2020) | MEN/CNE | ✅ ERNC y almacenamiento |",
            "| IEC 62443 SL-1/SL-2 | IEC → SEC 2024 | ✅ Ciberseguridad OT |",
            "| IEEE 2030.5 (SEP 2.0) | IEEE → CNE | ⚠️ Distribución DER |",
            "| IEC 60870-5-104 | IEC → CEN | ✅ SCADA obligatorio |",
            "| NTCSE | SEC/CNE | ✅ Calidad de energía |",
            "| Decreto N°125/2017 | MEN | ✅ Sistema eléctrico |",
            "",
            "---",
            "",
            "## 🤖 Metodología",
            "",
            "Este reporte fue generado por **sec-bess-ingestor**, un sistema automático que:",
            "",
            "1. **Raspa** sistemáticamente el sitio de la SEC Chile (resoluciones, circulares, normativas)",
            "2. **Analiza** el contenido contra la base de conocimiento normativa de open-bess-edge",
            "3. **Cruza** con el estado de implementación documentado en los archivos de compliance del repo",
            "4. **Publica** automáticamente este reporte como PR al repo cuando se solicita actualización",
            "",
            "```bash",
            "# Comandos disponibles",
            "python cli.py scrape      # Raspa SEC Chile",
            "python cli.py analyze     # Analiza brechas",
            "python cli.py report      # Genera este reporte",
            "python cli.py publish     # Publica al repo (requiere GITHUB_TOKEN)",
            "python cli.py update      # Todo en uno",
            "```",
            "",
            f"> *Generado automáticamente por [sec-bess-ingestor](https://github.com/bess-solutions/open-bess-edge/tree/main/sec-bess-ingestor) — {_now_iso()}*",
        ]

        return "\n".join(lines)

    def build_summary_report(self, gaps: list[GapItem]) -> str:
        """Genera resumen ejecutivo compacto (para PR description)."""
        stats = self.analyzer.summary_stats(gaps)
        critical = [g for g in gaps if g.priority == "critical"]

        lines = [
            f"## 🔍 SEC Gap Analysis Update — {_now_iso()}",
            "",
            f"**{stats['total']} brechas** identificadas entre la normativa SEC Chile y open-bess-edge.",
            "",
            "### 🔴 Brechas Críticas que Requieren Acción Inmediata",
            "",
        ]
        for g in critical:
            lines.append(f"- **{g.gap_id}** · {g.norm_ref}")
            lines.append(f"  - {g.description[:200]}…")
            lines.append(f"  - *Acción:* {g.technical_action[:150]}…")
            lines.append(f"  - *Esfuerzo:* {g.estimated_effort}")
            lines.append("")

        lines += [
            "### 📊 Estadísticas",
            "",
            f"| Prioridad | Brechas | Estado más común |",
            f"|---|---|---|",
            f"| 🔴 Crítico | {stats['by_priority']['critical']} | 🔄 Planificado |",
            f"| 🟡 Medio | {stats['by_priority']['medium']} | ⚠️ Parcial |",
            f"| 🟢 Bajo | {stats['by_priority']['low']} | 🔄 Planificado |",
        ]
        return "\n".join(lines)

    @staticmethod
    def _render_gap(g: GapItem) -> list[str]:
        lines = [
            f"### {g.gap_id} — {g.norm_ref}",
            "",
            f"**Prioridad:** {g.priority_label}  ",
            f"**Estado BESSAI:** {g.status_label}  ",
            f"**Esfuerzo estimado:** {g.estimated_effort}  ",
            "",
            f"**📄 Origen normativo:** [{g.sec_document_title}]({g.sec_document_url})",
            "",
            "#### Descripción de la Brecha",
            "",
            g.description,
            "",
            "#### Estado Actual en open-bess-edge",
            "",
            f"> {g.bess_current_state}",
            f">",
            f"> *Referencia de código:* `{g.bess_code_ref}`",
            "",
            "#### Acción Técnica Recomendada",
            "",
            f"```",
            g.technical_action,
            f"```",
            "",
        ]
        if g.relevant_sec_text:
            lines += [
                "#### Fragmento Normativo Relevante",
                "",
                f"> {g.relevant_sec_text}",
                "",
            ]
        lines.append("---")
        lines.append("")
        return lines

    def save(
        self,
        gaps: list[GapItem],
        sec_data: dict,
    ) -> tuple[str, str]:
        """
        Guarda ambos reportes (completo y resumen) en data/reports/.
        Retorna (path_full, path_summary).
        """
        tag = _now_tag()

        full_md = self.build_full_report(gaps, sec_data)
        summary_md = self.build_summary_report(gaps)

        full_path = REPORTS_DIR / f"gap_analysis_{tag}.md"
        summary_path = REPORTS_DIR / f"gap_summary_{tag}.md"

        full_path.write_text(full_md, encoding="utf-8")
        summary_path.write_text(summary_md, encoding="utf-8")

        logger.info(f"📄 Reporte completo: {full_path}")
        logger.info(f"📄 Resumen: {summary_path}")
        return str(full_path), str(summary_path)
