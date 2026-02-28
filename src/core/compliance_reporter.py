# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/interfaces/compliance_reporter.py
=======================================
BESSAI Compliance Reporter — Auto-generates audit reports for SEC/CEN.

Produces structured compliance reports in JSON and Markdown format,
documenting every norm checked, every block event, and every incident
for the reporting period. Designed for:

  * Monthly SEC audit submission
  * CEN SC market participation evidence
  * Internal BESSAI customer dashboard
  * CSIRT incident log (Ley 21.663/2024)

Usage::

    reporter = ComplianceReporter(site_id="PMGD-001")
    reporter.record_cycle(result)           # call every cycle
    reporter.record_incident(incident)      # from SecurityNotifier
    report = reporter.generate(period="2026-02")
    reporter.save_markdown(report, "/var/reports/2026-02-compliance.md")
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)


@dataclass
class CycleRecord:
    timestamp_iso: str
    dispatch_allowed: bool
    block_reason: str
    p_pfr_kw: float
    q_kvar: float
    pfr_active: bool
    qv_active: bool
    norm_refs: list[str]


@dataclass
class ComplianceReport:
    """Full compliance report for one period."""
    site_id: str
    period: str
    generated_at: str
    total_cycles: int
    blocked_cycles: int
    availability_pct: float
    pfr_activations: int
    qv_activations: int
    block_reasons: dict[str, int]        # reason → count
    norm_coverage: list[str]             # all norm_refs seen
    incidents: list[dict[str, Any]]
    compliance_score: float              # 0–100
    summary_md: str = ""


class ComplianceReporter:
    """
    Compliance report generator for BESSAI.

    Parameters
    ----------
    site_id     Site identifier.
    reports_dir Path to save report files. Default: reports/compliance/.
    """

    def __init__(
        self,
        site_id: str = "BESS-SITE",
        reports_dir: str | Path = "reports/compliance",
    ) -> None:
        self._site_id = site_id
        self._reports_dir = Path(reports_dir)
        self._cycles: list[CycleRecord] = []
        self._incidents: list[dict[str, Any]] = []

        log.info("compliance_reporter.initialized", site_id=site_id)

    @classmethod
    def from_env(cls) -> "ComplianceReporter":
        return cls(
            site_id=os.getenv("SITE_ID", "BESS-SITE"),
            reports_dir=os.getenv("COMPLIANCE_REPORTS_DIR", "reports/compliance"),
        )

    def record_cycle(self, result: Any) -> None:
        """Record one ComplianceStack.run_cycle() result."""
        record = CycleRecord(
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
            dispatch_allowed=getattr(result, "dispatch_allowed", True),
            block_reason=getattr(result, "block_reason", ""),
            p_pfr_kw=round(getattr(result, "p_pfr_setpoint_kw", 0.0), 2),
            q_kvar=round(getattr(result, "q_setpoint_kvar", 0.0), 2),
            pfr_active=getattr(result, "pfr_active", False),
            qv_active=getattr(result, "qv_active", False),
            norm_refs=list(getattr(result, "norm_refs", [])),
        )
        self._cycles.append(record)

    def record_incident(self, incident: Any) -> None:
        """Record a SecurityNotifier IncidentReport."""
        self._incidents.append(incident.to_dict() if hasattr(incident, "to_dict")
                               else dict(incident))

    def generate(self, period: str | None = None) -> ComplianceReport:
        """Generate the compliance report for the current data."""
        now = datetime.now(timezone.utc)
        period = period or now.strftime("%Y-%m")
        total = len(self._cycles)
        blocked = sum(1 for c in self._cycles if not c.dispatch_allowed)
        pfr_act = sum(1 for c in self._cycles if c.pfr_active)
        qv_act = sum(1 for c in self._cycles if c.qv_active)
        avail = ((total - blocked) / total * 100) if total > 0 else 100.0

        # Block reason distribution
        reasons: dict[str, int] = {}
        for c in self._cycles:
            if c.block_reason:
                reasons[c.block_reason] = reasons.get(c.block_reason, 0) + 1

        # All norm refs seen
        norm_coverage: set[str] = set()
        for c in self._cycles:
            norm_coverage.update(c.norm_refs)

        # Compliance score: weighted availability + 0 critical incidents
        crit_incidents = sum(1 for i in self._incidents
                             if i.get("severity") in ("CRITICAL", "HIGH"))
        score = max(0.0, avail - crit_incidents * 5.0)

        report = ComplianceReport(
            site_id=self._site_id,
            period=period,
            generated_at=now.isoformat(),
            total_cycles=total,
            blocked_cycles=blocked,
            availability_pct=round(avail, 2),
            pfr_activations=pfr_act,
            qv_activations=qv_act,
            block_reasons=reasons,
            norm_coverage=sorted(norm_coverage),
            incidents=self._incidents,
            compliance_score=round(score, 1),
        )
        report.summary_md = self._render_markdown(report)

        log.info(
            "compliance_reporter.report_generated",
            site_id=self._site_id, period=period,
            total_cycles=total, availability_pct=avail,
            compliance_score=score,
        )
        return report

    def _render_markdown(self, r: ComplianceReport) -> str:
        norms = ", ".join(r.norm_coverage) if r.norm_coverage else "N/A"
        incidents_summary = (
            f"{len(r.incidents)} incidente(s) registrado(s)"
            if r.incidents else "Sin incidentes"
        )
        return f"""# Informe de Compliance BESSAI
## Sitio: {r.site_id} · Período: {r.period}
**Generado:** {r.generated_at}

| Métrica | Valor |
|---|---|
| Ciclos totales | {r.total_cycles:,} |
| Ciclos bloqueados | {r.blocked_cycles:,} |
| **Disponibilidad** | **{r.availability_pct:.1f}%** |
| Activaciones PFR (GAP-002) | {r.pfr_activations:,} |
| Activaciones Q/V (GAP-011) | {r.qv_activations:,} |
| Incidentes seguridad | {incidents_summary} |
| **Score compliance** | **{r.compliance_score:.0f}/100** |

**Normas verificadas:** {norms}

{self._render_blocks(r.block_reasons)}

*Generado por BESSAI ComplianceReporter · Ley 21.663 / NTSyCS / NTCSE*
"""

    def _render_blocks(self, reasons: dict[str, int]) -> str:
        if not reasons:
            return "_Sin bloqueos de despacho en el período._"
        lines = ["### Eventos de bloqueo de despacho", "", "| Razón | Ocurrencias |", "|---|---|"]
        for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
            lines.append(f"| {r} | {c} |")
        return "\n".join(lines)

    def save_json(self, report: ComplianceReport, path: str | Path | None = None) -> Path:
        """Save report as JSON file."""
        if path is None:
            self._reports_dir.mkdir(parents=True, exist_ok=True)
            path = self._reports_dir / f"{report.site_id}_{report.period}_compliance.json"
        Path(path).write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
        log.info("compliance_reporter.json_saved", path=str(path))
        return Path(path)

    def save_markdown(self, report: ComplianceReport, path: str | Path | None = None) -> Path:
        """Save report as Markdown file (for SEC submission)."""
        if path is None:
            self._reports_dir.mkdir(parents=True, exist_ok=True)
            path = self._reports_dir / f"{report.site_id}_{report.period}_compliance.md"
        Path(path).write_text(report.summary_md, encoding="utf-8")
        log.info("compliance_reporter.md_saved", path=str(path))
        return Path(path)
