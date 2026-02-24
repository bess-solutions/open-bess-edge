# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/alert_dispatcher.py
=============================
BESSAI Edge Gateway — Multi-channel Real-Time Alert Dispatcher.

Envía alertas a múltiples canales cuando el AI-IDS o SafetyGuard
detectan eventos críticos:

Canales soportados:
    - Slack (webhook URL)
    - Email SMTP
    - Structured log (siempre activo como fallback)

Configuración via variables de entorno:
    - ``ALERT_SLACK_WEBHOOK``   — URL del webhook de Slack
    - ``ALERT_EMAIL_FROM``      — Dirección de origen del email
    - ``ALERT_EMAIL_TO``        — Destinatario(s), separados por coma
    - ``ALERT_EMAIL_SMTP_HOST`` — Host SMTP (ej: smtp.gmail.com)
    - ``ALERT_EMAIL_SMTP_PORT`` — Puerto SMTP (default: 587)
    - ``ALERT_EMAIL_SMTP_USER`` — Usuario SMTP
    - ``ALERT_EMAIL_SMTP_PASS`` — Contraseña SMTP
    - ``ALERT_MIN_SEVERITY``    — Severidad mínima para enviar: INFO|WARNING|CRITICAL (default: WARNING)

Usage::

    from src.core.alert_dispatcher import AlertDispatcher, AlertSeverity

    dispatcher = AlertDispatcher()
    dispatcher.send(
        severity=AlertSeverity.CRITICAL,
        title="AI-IDS: Anomalía crítica detectada",
        detail="z-score=4.82 en active_power_kw — posible inyección de datos",
        source="ai_ids",
        tags={"device_id": "BESS-001", "site": "Santiago"},
    )
"""

from __future__ import annotations

import os
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from enum import Enum
from typing import Any
from datetime import datetime, timezone

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------


class AlertSeverity(str, Enum):
    """Alert severity levels, ordered from lowest to highest."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    def __ge__(self, other: "AlertSeverity") -> bool:
        order = {AlertSeverity.INFO: 0, AlertSeverity.WARNING: 1, AlertSeverity.CRITICAL: 2}
        return order[self] >= order[other]

    def __gt__(self, other: "AlertSeverity") -> bool:
        order = {AlertSeverity.INFO: 0, AlertSeverity.WARNING: 1, AlertSeverity.CRITICAL: 2}
        return order[self] > order[other]


# ---------------------------------------------------------------------------
# Alert Dispatcher
# ---------------------------------------------------------------------------

_SEVERITY_COLORS = {
    AlertSeverity.INFO: "#2196F3",       # blue
    AlertSeverity.WARNING: "#FF9800",    # orange
    AlertSeverity.CRITICAL: "#F44336",   # red
}

_SEVERITY_EMOJIS = {
    AlertSeverity.INFO: "ℹ️",
    AlertSeverity.WARNING: "⚠️",
    AlertSeverity.CRITICAL: "🚨",
}

__all__ = ["AlertDispatcher", "AlertSeverity"]


class AlertDispatcher:
    """Dispatches alerts to configured channels (Slack, email, log).

    Reads configuration from environment variables at instantiation time.
    Channels are enabled only if the corresponding env vars are set.

    Parameters
    ----------
    min_severity:
        Minimum severity to dispatch. Alerts below this level are dropped.
        Overridden by ``ALERT_MIN_SEVERITY`` env var if set.

    Examples
    --------
    ::

        dispatcher = AlertDispatcher()
        dispatcher.send(
            severity=AlertSeverity.CRITICAL,
            title="Anomalía detectada en SoC",
            detail="SoC cayó de 45% a 8% en 3 minutos — posible fallo de BMS",
            source="safety_guard",
        )
    """

    def __init__(self, min_severity: AlertSeverity = AlertSeverity.WARNING) -> None:
        env_min = os.environ.get("ALERT_MIN_SEVERITY", "").strip().upper()
        self._min_severity = AlertSeverity(env_min) if env_min in AlertSeverity._value2member_map_ else min_severity  # type: ignore[attr-defined]

        self._slack_webhook = os.environ.get("ALERT_SLACK_WEBHOOK", "").strip() or None
        self._email_from = os.environ.get("ALERT_EMAIL_FROM", "").strip() or None
        self._email_to_raw = os.environ.get("ALERT_EMAIL_TO", "").strip()
        self._email_to = [e.strip() for e in self._email_to_raw.split(",") if e.strip()]
        self._smtp_host = os.environ.get("ALERT_EMAIL_SMTP_HOST", "smtp.gmail.com")
        self._smtp_port = int(os.environ.get("ALERT_EMAIL_SMTP_PORT", "587"))
        self._smtp_user = os.environ.get("ALERT_EMAIL_SMTP_USER", "").strip() or None
        self._smtp_pass = os.environ.get("ALERT_EMAIL_SMTP_PASS", "").strip() or None

        channels = []
        if self._slack_webhook:
            channels.append("slack")
        if self._email_from and self._email_to:
            channels.append("email")
        channels.append("log")  # always active

        log.info(
            "alert_dispatcher.initialized",
            channels=channels,
            min_severity=self._min_severity.value,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        severity: AlertSeverity,
        title: str,
        detail: str,
        source: str = "bessai",
        tags: dict[str, Any] | None = None,
    ) -> None:
        """Send an alert to all configured channels.

        Parameters
        ----------
        severity:
            Alert severity level.
        title:
            Short, human-readable alert title (≤ 100 chars recommended).
        detail:
            Longer description with context, measurements, and recommended action.
        source:
            Component that generated the alert (e.g., ``"ai_ids"``, ``"safety_guard"``).
        tags:
            Optional dict of key-value metadata (e.g., device_id, site, signal_name).
        """
        if not (severity >= self._min_severity):
            log.debug(
                "alert_dispatcher.below_threshold",
                severity=severity.value,
                min_severity=self._min_severity.value,
            )
            return

        ts = datetime.now(timezone.utc).isoformat()
        tags = tags or {}

        # Always log
        log_fn = log.error if severity == AlertSeverity.CRITICAL else (
            log.warning if severity == AlertSeverity.WARNING else log.info
        )
        log_fn(
            "alert_dispatcher.alert",
            severity=severity.value,
            title=title,
            detail=detail,
            source=source,
            **tags,
        )

        # Slack
        if self._slack_webhook:
            self._send_slack(severity=severity, title=title, detail=detail, source=source, tags=tags, ts=ts)

        # Email
        if self._email_from and self._email_to:
            self._send_email(severity=severity, title=title, detail=detail, source=source, tags=tags, ts=ts)

    # ------------------------------------------------------------------
    # Private: Slack
    # ------------------------------------------------------------------

    def _send_slack(
        self,
        severity: AlertSeverity,
        title: str,
        detail: str,
        source: str,
        tags: dict[str, Any],
        ts: str,
    ) -> None:
        try:
            import urllib.request

            emoji = _SEVERITY_EMOJIS[severity]
            color = _SEVERITY_COLORS[severity]
            tag_text = "\n".join(f"• *{k}*: `{v}`" for k, v in tags.items())
            tag_section = f"\n*Tags:*\n{tag_text}" if tag_text else ""

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"{emoji} [{severity.value}] {title}",
                        "text": detail + tag_section,
                        "footer": f"BESSAI Edge Gateway · source: {source}",
                        "ts": ts,
                    }
                ]
            }

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self._slack_webhook,  # type: ignore[arg-type]
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status != 200:
                    log.error("alert_dispatcher.slack_error", status=resp.status)
                else:
                    log.debug("alert_dispatcher.slack_sent", title=title)

        except Exception as exc:  # noqa: BLE001
            log.error("alert_dispatcher.slack_failed", error=str(exc))

    # ------------------------------------------------------------------
    # Private: Email
    # ------------------------------------------------------------------

    def _send_email(
        self,
        severity: AlertSeverity,
        title: str,
        detail: str,
        source: str,
        tags: dict[str, Any],
        ts: str,
    ) -> None:
        try:
            emoji = _SEVERITY_EMOJIS[severity]
            subject = f"{emoji} BESSAI [{severity.value}] {title}"

            html_tags = "".join(
                f"<tr><td><b>{k}</b></td><td><code>{v}</code></td></tr>" for k, v in tags.items()
            )
            html_body = f"""
            <html><body>
            <h2 style="color:{_SEVERITY_COLORS[severity]}">{emoji} {title}</h2>
            <p><b>Severity:</b> {severity.value}<br>
               <b>Source:</b> {source}<br>
               <b>Timestamp:</b> {ts}</p>
            <hr>
            <p>{detail.replace(chr(10), "<br>")}</p>
            {f"<h4>Tags:</h4><table border='1'>{html_tags}</table>" if html_tags else ""}
            <hr><small>BESSAI Edge Gateway — Alert Dispatcher</small>
            </body></html>
            """

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self._email_from  # type: ignore[assignment]
            msg["To"] = ", ".join(self._email_to)
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=10) as server:
                server.ehlo()
                server.starttls()
                if self._smtp_user and self._smtp_pass:
                    server.login(self._smtp_user, self._smtp_pass)
                server.sendmail(self._email_from, self._email_to, msg.as_string())  # type: ignore[arg-type]

            log.debug("alert_dispatcher.email_sent", title=title, to=self._email_to)

        except Exception as exc:  # noqa: BLE001
            log.error("alert_dispatcher.email_failed", error=str(exc))
