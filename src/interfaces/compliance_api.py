# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/interfaces/compliance_api.py
==================================
BESSAI Compliance REST API — HTTP endpoints for compliance reports.

Exposes:
  GET  /compliance/status       → current compliance state (200 / 503)
  GET  /compliance/report       → full JSON report for SEC/CEN audit
  POST /compliance/authorize    → authorize a command (RBAC check)

Integrated into the existing HealthServer on the same port (HEALTH_PORT).
"""

from __future__ import annotations

import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from typing import Any

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory state shared with main loop (updated per cycle)
# ---------------------------------------------------------------------------
_compliance_state: dict[str, Any] = {
    "site_id": "UNKNOWN",
    "timestamp": None,
    "all_ok": True,
    "compliance_score": 100.0,
    "violations": [],
    "gaps_checked": 11,
    "norm_ref": "NTSyCS CEN Chile — 11 GAPs v2.12.0",
    "cycle_count": 0,
}


def update_compliance_state(
    site_id: str,
    all_ok: bool,
    violations: list[str],
    score: float,
    cycle: int,
) -> None:
    """Called by main loop after each ComplianceStack.run_cycle()."""
    _compliance_state.update(
        {
            "site_id": site_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "all_ok": all_ok,
            "compliance_score": round(score, 1),
            "violations": violations,
            "cycle_count": cycle,
        }
    )


def make_compliance_handler(site_id: str, version: str) -> type[BaseHTTPRequestHandler]:
    """Factory: returns HTTPRequestHandler class with compliance routes."""

    class _ComplianceHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:  # noqa: N802
            """Route HTTP access log to structlog."""
            log.debug("compliance_api.request", path=self.path, args=args)

        def _send_json(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, indent=2).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/compliance/status":
                ok = _compliance_state["all_ok"]
                code = 200 if ok else 503
                self._send_json(code, {
                    "status": "compliant" if ok else "non_compliant",
                    "compliance_score": _compliance_state["compliance_score"],
                    "norm_ref": _compliance_state["norm_ref"],
                    "timestamp": _compliance_state["timestamp"],
                    "site_id": _compliance_state["site_id"],
                })

            elif self.path == "/compliance/report":
                report = {
                    "report_type": "NTSyCS_COMPLIANCE_REPORT",
                    "version": version,
                    "site_id": site_id,
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "norm_ref": _compliance_state["norm_ref"],
                    "compliance_score": _compliance_state["compliance_score"],
                    "all_gaps_compliant": _compliance_state["all_ok"],
                    "gaps_checked": _compliance_state["gaps_checked"],
                    "violations": _compliance_state["violations"],
                    "cycles_monitored": _compliance_state["cycle_count"],
                    "gaps": {
                        "GAP-001": "NTSyCS Cap.4.2 — Ramp rate ≤10%/min",
                        "GAP-002": "NTSyCS Cap.4.3 — PFR droop < 2s",
                        "GAP-003": "NTSyCS Cap.6.1 — CEN telemetry mTLS",
                        "GAP-004": "NTSyCS Cap.6.2 — SCADA IEC 60870-5-104",
                        "GAP-007": "Decreto 88/2023 — PMGD anti-arbitrage",
                        "GAP-008": "Ley 21.185 — CER ERNC tracking",
                        "GAP-009": "IEC 62443 SL-2 — RBAC + HMAC",
                        "GAP-010": "NTCSE — THD/Flicker quality gate",
                        "GAP-011": "NTSyCS Cap.4.4 — Q/V droop",
                        "SEC-01":  "Ley 21.663/2024 — CSIRT cybersecurity",
                        "SC-01":   "CEN 2024 — Servicios Complementarios",
                    },
                }
                self._send_json(200, report)

            else:
                self._send_json(404, {"error": "Not found", "path": self.path})

    return _ComplianceHandler
